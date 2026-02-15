#!/usr/bin/env python3
"""Token Saver script for OpenClaw.
   Compresses token list, generates summary & importance using OpenAI Codex,
   stores compressed tokens and metadata into PostgreSQL and caches recent summary in Redis.
   Usage: python3 token_saver.py <session_id> <json_token_list>
"""
import os, sys, json, time, zlib, base64
import psycopg2, redis
from openai import OpenAI

# Environment variables (ensure they exist)
PGUSER = os.getenv("PGUSER", "tolls")
PGDB   = os.getenv("PGDATABASE", "openclaw")
PGPASSWORD = os.getenv("PGPASSWORD")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

if not PGPASSWORD:
    print("Error: PGPASSWORD not set", file=sys.stderr)
    sys.exit(1)

# Initialise clients
client = OpenAI()  # assumes CODex API key already configured via env or openai config
pg_conn = psycopg2.connect(dbname=PGDB, user=PGUSER, password=PGPASSWORD)
redis_cli = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def compress_tokens(tokens):
    """Compress token list using gzip + base64."""
    raw = " ".join(tokens).encode()
    return base64.b64encode(zlib.compress(raw)).decode()

def summarize(tokens):
    prompt = "Summarize the following conversation in <=256 tokens:\n" + " ".join(tokens)
    try:
        resp = client.chat.completions.create(
            model="code-davinci-002",
            messages=[{"role": "system", "content": "You are a summarizer."},
                      {"role": "user", "content": prompt}],
            max_tokens=256,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        # Fallback to simple concatenation if LLM fails
        sys.stderr.write(f"Summarize error: {e}\n")
        return " ".join(tokens)[:250]


def importance_score(tokens):
    prompt = "Rate the importance of the above text on a 0-1 scale."
    try:
        resp = client.chat.completions.create(
            model="code-davinci-002",
            messages=[{"role": "system", "content": "You are a scorer."},
                      {"role": "user", "content": prompt}],
            max_tokens=4,
        )
        return float(resp.choices[0].message.content.strip())
    except Exception as e:
        sys.stderr.write(f"Importance error: {e}\n")
        return 0.5

def save_chunk(session_id, token_list):
    # 1. filter tokens (remove empty/system markers)
    filtered = [t for t in token_list if t.strip() and not t.startswith("<SYS>")]
    if not filtered:
        return
    # 2. compress
    comp = compress_tokens(filtered)
    # 3. summary & importance
    summary = summarize(filtered)
    importance = importance_score(filtered)
    # 4. write to PostgreSQL
    cur = pg_conn.cursor()
    cur.execute(
        """INSERT INTO mem_chunk (session_id, ts, tokens, summary, metadata)
           VALUES (%s, %s, %s, %s, %s)""",
        (session_id, int(time.time()*1000), comp, summary,
         json.dumps({"importance": importance})
        )
    )
    pg_conn.commit()
    # 5. cache in Redis (list for recent tokens & summaries)
    redis_cli.rpush(f"mem:session:{session_id}:tokens", comp)
    redis_cli.rpush(f"mem:session:{session_id}:summary", summary)
    redis_cli.expire(f"mem:session:{session_id}:tokens", 3600)
    redis_cli.expire(f"mem:session:{session_id}:summary", 3600)
    # optional print for test verification
    print("OK")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: token_saver.py <session_id> <json_token_list>")
        sys.exit(1)
    sess = sys.argv[1]
    try:
        toks = json.loads(sys.argv[2])
    except Exception as e:
        print(f"Failed to parse token list: {e}", file=sys.stderr)
        sys.exit(1)
    save_chunk(sess, toks)
