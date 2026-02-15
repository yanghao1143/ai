#!/usr/bin/env python3
"""Pre‑compaction script for OpenClaw memory.
   Aggregates recent mem_chunk rows for a given session, stores a combined summary
   and marks the original chunks as archived. Also updates Redis cache.
   Usage: python3 pre_compaction.py <session_id>
"""
import os, sys, json, time
import psycopg2, redis

# Environment / connection settings
PGUSER = os.getenv('PGUSER', 'tolls')
PGDB   = os.getenv('PGDATABASE', 'openclaw')
PGPASSWORD = os.getenv('PGPASSWORD')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))

if not PGPASSWORD:
    print('Error: PGPASSWORD not set', file=sys.stderr)
    sys.exit(1)

if len(sys.argv) != 2:
    print('Usage: pre_compaction.py <session_id>')
    sys.exit(1)

session_id = sys.argv[1]

# Connect to PostgreSQL
pg_conn = psycopg2.connect(dbname=PGDB, user=PGUSER, password=PGPASSWORD)
cur = pg_conn.cursor()

# Fetch unarchived chunks for this session
cur.execute(
    """SELECT id, tokens, summary FROM mem_chunk
       WHERE session_id = %s AND (metadata->>'archived') IS NULL""",
    (session_id,)
)
rows = cur.fetchall()
if not rows:
    print('No unarchived chunks found for session', session_id)
    sys.exit(0)

# Aggregate summaries (simple concatenation, truncate to 256 tokens approx.)
agg_summary = ' '.join([r[2] for r in rows])
# Truncate to 256 tokens (naive split)
agg_summary = ' '.join(agg_summary.split()[:256])

# Insert aggregated chunk (metadata marks it as aggregated)
cur.execute(
    """INSERT INTO mem_chunk (session_id, ts, tokens, summary, metadata)
       VALUES (%s, %s, %s, %s, %s)""",
    (session_id, int(time.time()*1000), None, agg_summary,
     json.dumps({"aggregated": True, "archived": False})
    )
)
agg_id = cur.fetchone() if cur.rowcount else None

# Mark original rows as archived
cur.execute(
    """UPDATE mem_chunk SET metadata = jsonb_set(
            COALESCE(metadata, '{}'::jsonb), '{archived}', 'true'::jsonb)
       WHERE id = ANY(%s)""",
    ([r[0] for r in rows],)
)
pg_conn.commit()
cur.close()
pg_conn.close()

# Update Redis cache with latest aggregated summary (TTL 1h)
redis_cli = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
redis_cli.set(f"mem:session:{session_id}:summary", agg_summary, ex=3600)
print('Pre‑compaction completed. Aggregated summary stored, original chunks archived.')
