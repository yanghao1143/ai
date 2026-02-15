#!/usr/bin/env python3
import json
import os
import subprocess
import time
from datetime import datetime

SESSIONS_DIR = '/home/tolls/.openclaw/agents/main/sessions'
STATE_PATH = '/home/tolls/.openclaw/workspace-clean/memory/.memory_stats_state.json'
LOG_PATH = '/home/tolls/.openclaw/workspace-clean/memory/learning/memory_stats.md'
JSON_PATH = '/home/tolls/.openclaw/workspace-clean/memory/learning/memory_stats.json'

WINDOW_HOURS = int(os.environ.get('MEMORY_WINDOW_HOURS', '24'))
ALERT_THRESHOLD = float(os.environ.get('MEMORY_ALERT_THRESHOLD', '0.05'))
MIN_REQUIRED_QUERIES = int(os.environ.get('MEMORY_MIN_REQUIRED', '5'))
ALERT_COOLDOWN_SECONDS = int(os.environ.get('MEMORY_ALERT_COOLDOWN', '7200'))

PG_HOST = os.environ.get('PGHOST', '127.0.0.1')
PG_PORT = int(os.environ.get('PGPORT', '5432'))
PG_DB = os.environ.get('PGDATABASE', 'openclaw')
PG_USER = os.environ.get('PGUSER', 'tolls')
PG_PASSWORD = os.environ.get('PGPASSWORD', 'asd8841315')
REDIS_HOST = os.environ.get('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))

KEYWORDS = [
    '??', '??', '??', '??', '??', '???', '??', '??',
    'before', 'earlier', 'previous', 'last time', 'you said'
]

NOTIFY_CMD = ['/usr/bin/openclaw', 'system', 'event', '--mode', 'now', '--text']


def load_state():
    if not os.path.exists(STATE_PATH):
        return {'last_alert': 0, 'last_run': 0}
    try:
        with open(STATE_PATH, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception:
        return {'last_alert': 0, 'last_run': 0}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, 'w', encoding='utf-8') as file:
        json.dump(state, file, ensure_ascii=False, indent=2)


def extract_text(message):
    content = message.get('content', [])
    if not isinstance(content, list):
        return ''
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get('type') == 'text':
            text = block.get('text', '')
            if isinstance(text, str):
                parts.append(text)
    return ''.join(parts)


def file_recent(path, cutoff):
    try:
        return os.path.getmtime(path) >= cutoff
    except OSError:
        return False


def notify(text):
    try:
        subprocess.run(NOTIFY_CMD + [text], check=False)
    except Exception:
        pass


def needs_memory(text):
    lower = text.lower()
    return any(keyword in text for keyword in KEYWORDS) or any(keyword in lower for keyword in KEYWORDS)


def get_pgvector_stats():
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASSWORD,
            connect_timeout=5,
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT COUNT(*)::bigint, COUNT(vec)::bigint FROM mem_chunk;')
                total, with_vec = cursor.fetchone()
            ratio = (with_vec / total) if total else 0.0
            return {
                'mem_chunk_total': int(total),
                'mem_chunk_with_vec': int(with_vec),
                'vec_coverage': round(ratio, 6),
            }
        finally:
            conn.close()
    except Exception:
        return {
            'mem_chunk_total': None,
            'mem_chunk_with_vec': None,
            'vec_coverage': None,
        }


def get_redis_and_compactor_stats():
    result = {
        'redis_used_memory_mb': None,
        'redis_maxmemory_mb': None,
        'redis_usage_ratio': None,
        'compaction_tier': None,
    }

    try:
        import redis
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        info = client.info('memory')
        used = int(info.get('used_memory', 0))
        maxmem = int(info.get('maxmemory', 0))
        ratio = (used / maxmem) if maxmem else 0.0
        result.update({
            'redis_used_memory_mb': round(used / 1048576, 2),
            'redis_maxmemory_mb': round(maxmem / 1048576, 2) if maxmem else 0.0,
            'redis_usage_ratio': round(ratio, 6),
        })
    except Exception:
        return result

    try:
        import importlib.util
        script_path = '/home/tolls/.openclaw/workspace-clean/scripts/vector_search.py'
        spec = importlib.util.spec_from_file_location('vector_search_runtime', script_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            compactor = module.MemoryCompactor()
            tier, _ = compactor.get_current_tier()
            result['compaction_tier'] = tier or 'none'
    except Exception:
        pass

    return result


def main():
    cutoff = time.time() - WINDOW_HOURS * 3600

    sessions_checked = 0
    required_queries = 0
    triggered_queries = 0
    memory_search_calls = 0
    memory_get_calls = 0
    total_user_messages = 0
    sessions_needing_memory = []

    if not os.path.isdir(SESSIONS_DIR):
        notify('[MEMORY-ERROR] sessions directory is missing; cannot calculate memory hit rate.')
        return

    for name in os.listdir(SESSIONS_DIR):
        if not name.endswith('.jsonl'):
            continue
        if '.deleted.' in name or name == 'sessions.json':
            continue

        path = os.path.join(SESSIONS_DIR, name)
        if not file_recent(path, cutoff):
            continue

        sessions_checked += 1
        pending_required = 0

        try:
            with open(path, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if entry.get('type') != 'message':
                        continue

                    message = entry.get('message', {})
                    role = message.get('role')

                    if role == 'user':
                        total_user_messages += 1
                        text = extract_text(message)
                        if needs_memory(text):
                            required_queries += 1
                            pending_required += 1

                    elif role == 'toolResult':
                        tool_name = message.get('toolName')
                        if tool_name == 'memory_search':
                            memory_search_calls += 1
                            if pending_required > 0:
                                pending_required -= 1
                                triggered_queries += 1
                        elif tool_name == 'memory_get':
                            memory_get_calls += 1

        except OSError:
            continue

        if pending_required > 0:
            sessions_needing_memory.append({
                'session_id': name.replace('.jsonl', ''),
                'missed_queries': pending_required,
            })

    missed_queries = max(required_queries - triggered_queries, 0)
    miss_ratio = (missed_queries / required_queries) if required_queries else 0.0
    hit_rate = (triggered_queries / required_queries) if required_queries else 0.0

    pg_stats = get_pgvector_stats()
    redis_stats = get_redis_and_compactor_stats()

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    stats = {
        'timestamp': timestamp,
        'window_hours': WINDOW_HOURS,
        'sessions_checked': sessions_checked,
        'total_user_messages': total_user_messages,
        'memory_required_queries': required_queries,
        'memory_triggered_queries': triggered_queries,
        'memory_missed_queries': missed_queries,
        'memory_search_calls': memory_search_calls,
        'memory_get_calls': memory_get_calls,
        'hit_rate': round(hit_rate, 6),
        'miss_ratio': round(miss_ratio, 6),
        'threshold': ALERT_THRESHOLD,
        'min_required_queries': MIN_REQUIRED_QUERIES,
        'alert_candidates': sessions_needing_memory[:10],
    }
    stats.update(pg_stats)
    stats.update(redis_stats)

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, 'a', encoding='utf-8') as file:
        file.write(f"## {timestamp}\n")
        file.write(f"- window_hours: {WINDOW_HOURS}\n")
        file.write(f"- sessions_checked: {sessions_checked}\n")
        file.write(f"- total_user_messages: {total_user_messages}\n")
        file.write(f"- memory_required_queries: {required_queries}\n")
        file.write(f"- memory_triggered_queries: {triggered_queries}\n")
        file.write(f"- memory_missed_queries: {missed_queries}\n")
        file.write(f"- memory_search_calls: {memory_search_calls}\n")
        file.write(f"- memory_get_calls: {memory_get_calls}\n")
        file.write(f"- hit_rate: {hit_rate:.2%}\n")
        file.write(f"- miss_ratio: {miss_ratio:.2%}\n")
        file.write(f"- threshold: {ALERT_THRESHOLD:.2%}\n")
        file.write(f"- pg_mem_chunk_total: {stats['mem_chunk_total']}\n")
        file.write(f"- pg_mem_chunk_with_vec: {stats['mem_chunk_with_vec']}\n")
        file.write(f"- pg_vec_coverage: {stats['vec_coverage']}\n")
        file.write(f"- redis_usage_ratio: {stats['redis_usage_ratio']}\n")
        file.write(f"- compaction_tier: {stats['compaction_tier']}\n\n")

    with open(JSON_PATH, 'w', encoding='utf-8') as file:
        json.dump(stats, file, ensure_ascii=False, indent=2)

    notify(
        f"[MEMORY-STATS] {WINDOW_HOURS}h | sessions={sessions_checked} | "
        f"required={required_queries} triggered={triggered_queries} hit={hit_rate:.2%} | "
        f"vec={stats['mem_chunk_with_vec']}/{stats['mem_chunk_total']} | "
        f"redis={stats['redis_usage_ratio'] if stats['redis_usage_ratio'] is not None else 'NA'}"
    )

    state = load_state()
    now = int(time.time())
    last_alert = int(state.get('last_alert', 0))

    should_alert = (
        required_queries >= MIN_REQUIRED_QUERIES
        and miss_ratio > ALERT_THRESHOLD
        and (now - last_alert) >= ALERT_COOLDOWN_SECONDS
    )

    if should_alert:
        samples = ', '.join(
            f"{item['session_id']}({item['missed_queries']})"
            for item in sessions_needing_memory[:5]
        )
        notify(
            f"[MEMORY-ALERT] miss_ratio={miss_ratio:.2%} exceeds threshold={ALERT_THRESHOLD:.2%}; "
            f"samples={samples if samples else 'none'}"
        )
        state['last_alert'] = now

    state['last_run'] = now
    save_state(state)


if __name__ == '__main__':
    main()
