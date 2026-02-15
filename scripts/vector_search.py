#!/usr/bin/env python3
"""
Vector Search Service for OpenClaw
Embedding generation, storage, similarity search, and tiered memory compaction
"""
import json
import zlib
import hashlib
import logging
from datetime import datetime

import numpy as np
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector
import redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "openclaw",
    "user": "tolls",
    "password": "asd8841315",
}
OLLAMA_URL = "http://127.0.0.1:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"
EMBED_DIM = 768
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
CACHE_TTL = 3600  # 1 hour
COMPRESSED_PREFIX = b"\x01"

# ── Database ───────────────────────────────────────────────────
def get_db():
    conn = psycopg2.connect(**DB_CONFIG)
    register_vector(conn)
    return conn

# ── Redis ──────────────────────────────────────────────────────
_redis_text = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
_redis_bin = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=False)

def _cache_key(query: str) -> str:
    return f"vsearch:{hashlib.sha256(query.encode()).hexdigest()[:16]}"

def _redis_set(key: str, value: str, ttl: int = CACHE_TTL):
    """Store value in Redis, compressed if large."""
    data = value.encode("utf-8")
    if len(data) > 1024:
        data = COMPRESSED_PREFIX + zlib.compress(data)
    _redis_bin.setex(key, ttl, data)

def _redis_get(key: str) -> str | None:
    """Read value from Redis, auto-decompress if needed."""
    raw = _redis_bin.get(key)
    if raw is None:
        return None
    if raw[:1] == COMPRESSED_PREFIX:
        return zlib.decompress(raw[1:]).decode("utf-8")
    return raw.decode("utf-8")

# ── Embedding ──────────────────────────────────────────────────
def embed(text: str) -> list[float]:
    """Generate embedding vector via Ollama nomic-embed-text."""
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    vec = resp.json()["embedding"]
    if len(vec) != EMBED_DIM:
        raise ValueError(f"Expected {EMBED_DIM} dims, got {len(vec)}")
    return vec

# ── Store ──────────────────────────────────────────────────────
def store(session_id: str, text: str, summary: str = "", metadata: dict | None = None):
    """Generate embedding and insert into mem_chunk with vec column."""
    vec = embed(text)
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO mem_chunk (session_id, ts, content, summary, metadata, vec)
                   VALUES (%s, %s, %s, %s, %s, %s::vector)""",
                (session_id, int(__import__('time').time() * 1000), text, summary, meta_json, str(vec)),
            )
        conn.commit()
        logger.info("Stored chunk for session=%s len=%d", session_id, len(text))
    finally:
        conn.close()

# ── Search ─────────────────────────────────────────────────────
def search(query: str, top_k: int = 5, min_score: float = 0.3) -> list[dict]:
    """Cosine similarity search with Redis caching (auto-decompress)."""
    cache_k = _cache_key(query)
    cached = _redis_get(cache_k)
    if cached:
        logger.info("Cache hit for query: %s", query[:60])
        return json.loads(cached)

    vec = embed(query)

    conn = get_db()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id, session_id, content, summary, metadata,
                          1 - (vec <=> %s::vector) AS score
                   FROM mem_chunk
                   WHERE vec IS NOT NULL
                   ORDER BY vec <=> %s::vector
                   LIMIT %s""",
                (str(vec), str(vec), top_k),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    results = []
    for r in rows:
        score = float(r["score"])
        if score < min_score:
            continue
        results.append({
            "id": r["id"],
            "session_id": r["session_id"],
            "content": r["content"],
            "summary": r["summary"],
            "metadata": r["metadata"],
            "score": round(score, 4),
        })

    # Cache results (auto-compress if large)
    _redis_set(cache_k, json.dumps(results, ensure_ascii=False, default=str))
    logger.info("Search returned %d results for: %s", len(results), query[:60])
    return results

# ── Backfill ───────────────────────────────────────────────────
def backfill(batch_size: int = 50):
    """Backfill embeddings for mem_chunk rows where vec IS NULL."""
    conn = get_db()
    total = 0
    try:
        while True:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, content, summary FROM mem_chunk WHERE vec IS NULL LIMIT %s",
                    (batch_size,),
                )
                rows = cur.fetchall()

            if not rows:
                break

            for row in rows:
                try:
                    text = row["content"] or row["summary"] or ""
                    if not text:
                        continue
                    vec = embed(text)
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE mem_chunk SET vec = %s::vector WHERE id = %s",
                            (str(vec), row["id"]),
                        )
                    total += 1
                except Exception as e:
                    logger.warning("Failed to embed id=%s: %s", row["id"], e)

            conn.commit()
            logger.info("Backfilled %d rows so far...", total)

    finally:
        conn.close()

    logger.info("Backfill complete: %d rows updated", total)
    return total

# ── MemoryCompactor ─────────────────────────────────────────
class MemoryCompactor:
    """
    Tiered progressive compression strategy.
    Instead of Redis LRU eviction, we manage memory ourselves
    with 5 escalating compression tiers based on usage ratio.
    """
    TIERS = [
        (0.60, "tier1"),  # gzip oldest 20% cache values
        (0.70, "tier2"),  # gzip 50% + truncate long text to summary
        (0.80, "tier3"),  # gzip all + DB: keep summary only, clear tokens
        (0.90, "tier4"),  # compress summary, Redis stores {score,keywords,vec_id} only
        (0.95, "tier5"),  # evict lowest-importance 30%
    ]

    def __init__(self):
        self.r = _redis_bin
        self.rt = _redis_text

    def check_memory_usage(self) -> tuple[int, int, float]:
        """Return (used_bytes, max_bytes, ratio)."""
        info = self.rt.info("memory")
        used = info.get("used_memory", 0)
        maxmem = info.get("maxmemory", 0)
        if maxmem == 0:
            return used, 0, 0.0
        return used, maxmem, used / maxmem

    def get_current_tier(self) -> tuple[str | None, float]:
        """Return (tier_name, usage_ratio) or (None, ratio) if below all thresholds."""
        _, _, ratio = self.check_memory_usage()
        current = None
        for threshold, name in self.TIERS:
            if ratio >= threshold:
                current = name
        return current, ratio

    def _get_mem_keys_sorted(self) -> list[bytes]:
        """Get mem:session:* keys sorted by idle time (oldest first)."""
        keys = list(self.r.scan_iter(match="mem:session:*", count=500))
        if not keys:
            keys = list(self.r.scan_iter(match="vsearch:*", count=500))
        decorated = []
        for k in keys:
            idle = self.r.object("idletime", k) or 0
            decorated.append((idle, k))
        decorated.sort(reverse=True)  # oldest first
        return [k for _, k in decorated]

    def _compress_key(self, key: bytes):
        """Compress a single Redis key value in-place."""
        raw = self.r.get(key)
        if raw is None or raw[:1] == COMPRESSED_PREFIX:
            return  # already compressed or missing
        ttl = self.r.ttl(key)
        compressed = COMPRESSED_PREFIX + zlib.compress(raw)
        if ttl and ttl > 0:
            self.r.setex(key, ttl, compressed)
        else:
            self.r.set(key, compressed)

    def compact(self, tier: str):
        """Execute compression for the given tier."""
        logger.info("Executing compaction: %s", tier)
        keys = self._get_mem_keys_sorted()
        total = len(keys)

        if tier == "tier1":
            # Compress oldest 20%
            n = max(1, total // 5)
            for k in keys[:n]:
                self._compress_key(k)
            logger.info("tier1: compressed %d/%d oldest keys", n, total)

        elif tier == "tier2":
            # Compress 50% + truncate long values to summary
            n = max(1, total // 2)
            for k in keys[:n]:
                self._compress_key(k)
            # Truncate uncompressed long values
            for k in keys[n:]:
                raw = self.r.get(k)
                if raw and raw[:1] != COMPRESSED_PREFIX and len(raw) > 500:
                    try:
                        obj = json.loads(raw)
                        if isinstance(obj, list):
                            for item in obj:
                                if isinstance(item, dict) and "content" in item:
                                    item["content"] = item.get("summary", item["content"][:200])
                        truncated = json.dumps(obj, ensure_ascii=False).encode()
                        ttl = self.r.ttl(k)
                        if ttl and ttl > 0:
                            self.r.setex(k, ttl, COMPRESSED_PREFIX + zlib.compress(truncated))
                        else:
                            self.r.set(k, COMPRESSED_PREFIX + zlib.compress(truncated))
                    except (json.JSONDecodeError, TypeError):
                        self._compress_key(k)
            logger.info("tier2: compressed 50%% + truncated long values")

        elif tier == "tier3":
            # Compress all Redis keys
            for k in keys:
                self._compress_key(k)
            # DB: clear tokens column, keep summary only
            conn = get_db()
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE mem_chunk SET tokens = NULL WHERE tokens IS NOT NULL")
                conn.commit()
                logger.info("tier3: all keys compressed + DB tokens cleared")
            finally:
                conn.close()

        elif tier == "tier4":
            # Compress everything, Redis stores minimal data
            for k in keys:
                raw = self.r.get(k)
                if raw is None:
                    continue
                try:
                    if raw[:1] == COMPRESSED_PREFIX:
                        data = json.loads(zlib.decompress(raw[1:]))
                    else:
                        data = json.loads(raw)
                    if isinstance(data, list):
                        minimal = []
                        for item in data:
                            if isinstance(item, dict):
                                minimal.append({
                                    "id": item.get("id"),
                                    "score": item.get("score"),
                                    "session_id": item.get("session_id"),
                                })
                        data = minimal
                    packed = COMPRESSED_PREFIX + zlib.compress(
                        json.dumps(data, ensure_ascii=False).encode()
                    )
                    ttl = self.r.ttl(k)
                    if ttl and ttl > 0:
                        self.r.setex(k, ttl, packed)
                    else:
                        self.r.set(k, packed)
                except (json.JSONDecodeError, TypeError):
                    self._compress_key(k)
            logger.info("tier4: all keys reduced to minimal {id,score,session_id}")

        elif tier == "tier5":
            # Evict lowest-importance 30% from DB + Redis
            conn = get_db()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """SELECT id FROM mem_chunk
                           ORDER BY COALESCE((metadata::json->>'importance')::float, 0) ASC
                           LIMIT (SELECT COUNT(*) * 30 / 100 FROM mem_chunk)"""
                    )
                    ids = [r["id"] for r in cur.fetchall()]
                if ids:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM mem_chunk WHERE id = ANY(%s)", (ids,))
                    conn.commit()
                    logger.info("tier5: evicted %d lowest-importance rows from DB", len(ids))
            finally:
                conn.close()
            # Flush all cache (stale after DB delete)
            for k in keys:
                self.r.delete(k)
            logger.info("tier5: flushed all cache keys")

    def run(self):
        """Main entry: check threshold → pick tier → compact → log."""
        tier, ratio = self.get_current_tier()
        used, maxmem, _ = self.check_memory_usage()
        logger.info(
            "Memory: %.1f MB / %.1f MB (%.1f%%)",
            used / 1048576, maxmem / 1048576, ratio * 100,
        )
        if tier is None:
            logger.info("Below all thresholds, no compaction needed")
            return
        self.compact(tier)
        _, _, new_ratio = self.check_memory_usage()
        logger.info("Compaction done. Usage: %.1f%% → %.1f%%", ratio * 100, new_ratio * 100)

    def status(self):
        """Print current memory status and tier."""
        used, maxmem, ratio = self.check_memory_usage()
        tier, _ = self.get_current_tier()
        print(f"Redis memory: {used / 1048576:.1f} MB / {maxmem / 1048576:.1f} MB ({ratio * 100:.1f}%)")
        print(f"Current tier: {tier or 'none (below 60%)'}")
        for threshold, name in self.TIERS:
            marker = " ◄──" if name == tier else ""
            print(f"  {name}: >= {threshold * 100:.0f}%{marker}")

# ── CLI ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    usage = """Usage:
    python3 vector_search.py search "query" [top_k]
    python3 vector_search.py store <session_id> "text" ["summary"]
    python3 vector_search.py backfill
    python3 vector_search.py compact
    python3 vector_search.py status
    python3 vector_search.py test
    """

    if len(sys.argv) < 2:
        print(usage)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "search":
        q = sys.argv[2] if len(sys.argv) > 2 else "test query"
        k = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        results = search(q, top_k=k)
        for r in results:
            print(f"[{r['score']:.4f}] id={r['id']} session={r['session_id']}")
            print(f"  {r['content'][:120] if r.get('content') else r.get('summary','')[:120]}")
            print()

    elif cmd == "store":
        if len(sys.argv) < 4:
            print("Usage: vector_search.py store <session_id> \"text\" [\"summary\"]")
            sys.exit(1)
        sid = sys.argv[2]
        text = sys.argv[3]
        summ = sys.argv[4] if len(sys.argv) > 4 else ""
        store(sid, text, summary=summ)
        print(f"Stored chunk for session={sid}")

    elif cmd == "backfill":
        backfill()

    elif cmd == "compact":
        MemoryCompactor().run()

    elif cmd == "status":
        MemoryCompactor().status()

    elif cmd == "test":
        print("Testing embedding generation...")
        vec = embed("Hello, this is a test")
        print(f"  Embedding dim: {len(vec)}, first 5: {vec[:5]}")
        print("OK")

    else:
        print(usage)
