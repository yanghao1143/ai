#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.request import Request, urlopen

OPENCLAW_CONFIG = '/home/tolls/.openclaw/openclaw.json'
VECTOR_SEARCH_PATH = '/home/tolls/.openclaw/workspace-clean/scripts/vector_search.py'
QUEUE_PATH = '/home/tolls/.openclaw/workspace-clean/memory/learning/team_queue.jsonl'
RUNS_MD_PATH = '/home/tolls/.openclaw/workspace-clean/memory/learning/team_runs.md'
RUNS_JSONL_PATH = '/home/tolls/.openclaw/workspace-clean/memory/learning/team_runs.jsonl'
ROADMAP_PATH = '/home/tolls/.openclaw/workspace-clean/memory/learning/roadmap.md'
STATE_PATH = '/home/tolls/.openclaw/workspace-clean/memory/.team_orchestrator_state.json'
NOTIFY_CMD = ['/usr/bin/openclaw', 'system', 'event', '--mode', 'now', '--text']


_VECTOR_MODULE = None


def notify(text):
    try:
        subprocess.run(NOTIFY_CMD + [text], check=False)
    except Exception:
        pass


def now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def load_json(path, default_value):
    if not os.path.exists(path):
        return default_value
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception:
        return default_value


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def load_config():
    with open(OPENCLAW_CONFIG, 'r', encoding='utf-8') as file:
        return json.load(file)


def get_agents(config):
    return [item.get('id') for item in config.get('agents', {}).get('list', []) if item.get('id')]


def resolve_agent_model(agent_id, config):
    for item in config.get('agents', {}).get('list', []):
        if item.get('id') == agent_id and item.get('model'):
            return item.get('model')
    return config.get('agents', {}).get('defaults', {}).get('model', {}).get('primary')


def resolve_runtime(model_ref, config):
    if not model_ref or '/' not in model_ref:
        raise RuntimeError(f'Invalid model ref: {model_ref}')

    provider_id, model_id = model_ref.split('/', 1)
    provider = config.get('models', {}).get('providers', {}).get(provider_id, {})
    env = config.get('env', {})

    base_url = provider.get('baseUrl') or env.get('OPENAI_BASE_URL')
    api_key = provider.get('apiKey') or env.get('OPENAI_API_KEY')

    if not base_url or not api_key:
        raise RuntimeError(f'Missing runtime config for provider: {provider_id}')

    return {
        'provider_id': provider_id,
        'model_id': model_id,
        'base_url': base_url.rstrip('/'),
        'api_key': api_key,
    }


def call_chat(runtime, system_prompt, user_prompt, temperature=0.25, max_tokens=1200, timeout=120):
    endpoint = runtime['base_url'] + '/chat/completions'
    payload = {
        'model': runtime['model_id'],
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'temperature': temperature,
        'max_tokens': max_tokens,
    }

    req = Request(
        endpoint,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {runtime['api_key']}",
        },
        method='POST',
    )

    with urlopen(req, timeout=timeout) as response:
        body = response.read().decode('utf-8', errors='ignore')

    data = json.loads(body)
    choices = data.get('choices') or []
    if not choices:
        raise RuntimeError('No choices in model response')

    message = choices[0].get('message', {})
    content = message.get('content', '')

    if isinstance(content, list):
        chunks = []
        for chunk in content:
            if isinstance(chunk, dict):
                chunks.append(str(chunk.get('text', '')))
        content = ''.join(chunks)

    content = str(content).strip()
    if not content:
        raise RuntimeError('Empty model response content')

    return content


def load_vector_module():
    global _VECTOR_MODULE
    if _VECTOR_MODULE is not None:
        return _VECTOR_MODULE

    if not os.path.exists(VECTOR_SEARCH_PATH):
        return None

    try:
        spec = importlib.util.spec_from_file_location('vector_search_runtime', VECTOR_SEARCH_PATH)
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _VECTOR_MODULE = module
        return module
    except Exception:
        return None


def fetch_related_memory(task, top_k=4):
    module = load_vector_module()
    if not module:
        return []

    try:
        rows = module.search(task, top_k=top_k, min_score=0.3)
        context = []
        for row in rows:
            text = (row.get('content') or row.get('summary') or '').strip()
            if not text:
                continue
            context.append({
                'score': row.get('score'),
                'session_id': row.get('session_id'),
                'text': text[:280],
            })
        return context
    except Exception:
        return []


def store_team_memory(task, merged_summary, source):
    module = load_vector_module()
    if not module:
        return False

    try:
        payload = (
            f"Task:\n{task}\n\n"
            f"Source: {source}\n\n"
            f"Merged Summary:\n{merged_summary[:4000]}"
        )
        module.store(
            session_id='team-orchestrator',
            text=payload,
            summary=merged_summary[:600],
            metadata={
                'origin': 'team_orchestrator',
                'timestamp': now_str(),
                'source': source,
            },
        )
        return True
    except Exception:
        return False


def infer_complexity(task):
    low = task.lower()
    keywords = [
        'fullstack', 'architecture', 'refactor', 'migration', 'deploy',
        'parallel', 'team', 'system', 'pipeline',
        '??', '??', '??', '??', '??', '??', '??'
    ]
    score = sum(1 for key in keywords if key in low)
    if score >= 2 or len(task) >= 80:
        return 'complex'
    return 'simple'


def pick_first(preferred_ids, available_ids, used_ids):
    for agent_id in preferred_ids:
        if agent_id in available_ids and agent_id not in used_ids:
            return agent_id
    for agent_id in available_ids:
        if agent_id not in used_ids:
            return agent_id
    return None


def choose_team(available_ids):
    used = set()
    selected = []

    implementer = pick_first(['codex', 'tools', 'deep'], available_ids, used)
    if implementer:
        selected.append(('implementer', implementer))
        used.add(implementer)

    architect = pick_first(['claude', 'deep', 'pro'], available_ids, used)
    if architect:
        selected.append(('architect', architect))
        used.add(architect)

    reviewer = pick_first(['gemini', 'pro', 'tools'], available_ids, used)
    if reviewer:
        selected.append(('reviewer', reviewer))
        used.add(reviewer)

    while len(selected) < 3:
        extra = pick_first([], available_ids, used)
        if not extra:
            break
        selected.append(('specialist', extra))
        used.add(extra)

    return selected


def role_system_prompt(role):
    prompts = {
        'implementer': 'You are the implementation lead. Provide concrete executable actions.',
        'architect': 'You are the architecture lead. Focus on structure, dependencies, and boundaries.',
        'reviewer': 'You are the risk reviewer. Focus on security, data safety, availability, and performance.',
        'specialist': 'You are a technical specialist. Provide pragmatic and high-impact advice.',
    }
    return prompts.get(role, prompts['specialist'])


def role_user_prompt(task, role, agent_id, memory_context):
    parts = [
        f"Task: {task}",
        f"Role: {role}",
        f"Agent: {agent_id}",
        '',
    ]

    if memory_context:
        parts.append('Relevant memory context from pgvector:')
        for row in memory_context:
            parts.append(f"- score={row['score']} session={row['session_id']} text={row['text']}")
        parts.append('')

    parts.extend([
        'Return exactly:',
        '1) Core judgement',
        '2) Action list in priority order',
        '3) Fallback plan if this fails',
        '4) Coordination points with other agents',
    ])

    return '\n'.join(parts)


def merge_outputs(task, outputs, config):
    primary_ref = config.get('agents', {}).get('defaults', {}).get('model', {}).get('primary')
    runtime = resolve_runtime(primary_ref, config)

    sections = [f"Task: {task}", '', 'Agent outputs:']
    for item in outputs:
        sections.append(f"## {item['role']} ({item['agent_id']})")
        sections.append(item.get('output', '').strip())
        sections.append('')

    system_prompt = 'You are a team orchestrator. Merge outputs into one conflict-free execution plan.'
    user_prompt = (
        '\n'.join(sections)
        + '\nReturn Markdown with headings:\n'
          '# Unified Conclusion\n# Execution Plan\n# Risks and Fallback\n# Next Immediate Actions'
    )

    try:
        return call_chat(runtime, system_prompt, user_prompt, temperature=0.2, max_tokens=1500)
    except Exception:
        fallback = ['# Unified Conclusion', 'Model merge failed, using concatenated summary.', '', '# Execution Plan']
        for item in outputs:
            preview = item.get('output', '').replace('\n', ' ')[:260]
            fallback.append(f"- [{item['role']}/{item['agent_id']}] {preview}")
        fallback.extend([
            '',
            '# Risks and Fallback',
            '- Manually review conflicting actions before execution.',
            '',
            '# Next Immediate Actions',
            '- Execute implementer actions first, then reviewer checks.',
        ])
        return '\n'.join(fallback)


def read_queue_items():
    if not os.path.exists(QUEUE_PATH):
        return []
    items = []
    with open(QUEUE_PATH, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def write_queue_items(items):
    os.makedirs(os.path.dirname(QUEUE_PATH), exist_ok=True)
    with open(QUEUE_PATH, 'w', encoding='utf-8') as file:
        for item in items:
            file.write(json.dumps(item, ensure_ascii=False) + '\n')


def next_pending_item():
    items = read_queue_items()
    for item in items:
        if item.get('status', 'pending') == 'pending' and item.get('task'):
            return item, items
    return None, items


def patch_queue_item(items, item_id, patch):
    for item in items:
        if item.get('id') == item_id:
            item.update(patch)
            break
    write_queue_items(items)


def parse_bullet_task(line):
    stripped = line.strip()
    if not stripped:
        return None

    if stripped.startswith('- '):
        return stripped[2:].strip()
    if stripped.startswith('* '):
        return stripped[2:].strip()

    numbered = re.match(r'^\d+[\.)]\s+(.+)$', stripped)
    if numbered:
        return numbered.group(1).strip()

    return None


def extract_roadmap_task():
    if not os.path.exists(ROADMAP_PATH):
        return None, None

    with open(ROADMAP_PATH, 'r', encoding='utf-8') as file:
        content = file.read()

    roadmap_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
    lines = content.splitlines()

    weekly_headers = {'# Weekly Priorities', '# ??????'}
    inside_weekly = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('# '):
            inside_weekly = stripped in weekly_headers
            continue

        if inside_weekly:
            task = parse_bullet_task(stripped)
            if task:
                return task, roadmap_hash

    for line in lines:
        task = parse_bullet_task(line)
        if task:
            return task, roadmap_hash

    return None, roadmap_hash


def append_run_entry(entry):
    os.makedirs(os.path.dirname(RUNS_MD_PATH), exist_ok=True)

    with open(RUNS_MD_PATH, 'a', encoding='utf-8') as file:
        file.write(f"## {entry['timestamp']}\n")
        file.write(f"- task_id: {entry['task_id']}\n")
        file.write(f"- source: {entry['source']}\n")
        file.write(f"- complexity: {entry['complexity']}\n")
        file.write(f"- agents: {', '.join(entry['agents'])}\n")
        file.write(f"- duration_sec: {entry['duration_sec']}\n")
        file.write(f"- status: {entry['status']}\n")
        file.write(f"- memory_context_items: {entry['memory_context_items']}\n")
        file.write(f"- vector_store_written: {entry['vector_store_written']}\n\n")
        file.write(entry['summary'].strip()[:2600] + '\n\n')

    with open(RUNS_JSONL_PATH, 'a', encoding='utf-8') as file:
        file.write(json.dumps(entry, ensure_ascii=False) + '\n')


def run_team(task, complexity, source, config):
    agents = get_agents(config)
    if not agents:
        raise RuntimeError('No agents found in openclaw config')

    selected = choose_team(agents)
    if complexity == 'simple':
        selected = selected[:1]
    if not selected:
        raise RuntimeError('Could not select agents')

    selected_ids = [agent_id for _, agent_id in selected]
    memory_context = fetch_related_memory(task, top_k=4)

    notify(
        f"[TEAM-RUN] start | complexity={complexity} | agents={','.join(selected_ids)} | "
        f"memory_context={len(memory_context)}"
    )

    start_ts = time.time()
    outputs = []

    def worker(role, agent_id):
        model_ref = resolve_agent_model(agent_id, config)
        runtime = resolve_runtime(model_ref, config)
        output = call_chat(
            runtime,
            role_system_prompt(role),
            role_user_prompt(task, role, agent_id, memory_context),
            temperature=0.25,
            max_tokens=1100,
            timeout=150,
        )
        return {
            'role': role,
            'agent_id': agent_id,
            'model_ref': model_ref,
            'output': output,
        }

    with ThreadPoolExecutor(max_workers=min(len(selected), 3)) as executor:
        future_map = {executor.submit(worker, role, agent_id): (role, agent_id) for role, agent_id in selected}
        for future in as_completed(future_map):
            role, agent_id = future_map[future]
            try:
                outputs.append(future.result())
            except Exception as exc:
                outputs.append({
                    'role': role,
                    'agent_id': agent_id,
                    'model_ref': 'unknown',
                    'output': f'ERROR: {exc}',
                })

    merged = merge_outputs(task, outputs, config)
    duration = round(time.time() - start_ts, 2)
    failed = sum(1 for item in outputs if item.get('output', '').startswith('ERROR:'))
    status = 'partial_failed' if failed else 'ok'

    vector_store_written = store_team_memory(task, merged, source)

    notify(
        f"[TEAM-RUN] done | status={status} | duration={duration}s | "
        f"vector_store={vector_store_written}"
    )

    return {
        'task': task,
        'complexity': complexity,
        'source': source,
        'outputs': outputs,
        'summary': merged,
        'duration_sec': duration,
        'status': status,
        'memory_context_items': len(memory_context),
        'vector_store_written': vector_store_written,
    }


def main():
    parser = argparse.ArgumentParser(description='OpenClaw team orchestrator')
    parser.add_argument('--task', help='Task text to run immediately')
    parser.add_argument('--complexity', choices=['auto', 'simple', 'complex'], default='auto')
    parser.add_argument('--source', default='manual')
    parser.add_argument('--no-auto-roadmap', action='store_true')
    args = parser.parse_args()

    config = load_config()
    state = load_json(STATE_PATH, {'last_roadmap_hash': ''})

    task = args.task.strip() if args.task else ''
    source = args.source
    queue_id = None
    queue_items = None

    if not task:
        pending, queue_items = next_pending_item()
        if pending:
            task = str(pending.get('task', '')).strip()
            source = pending.get('source', 'queue')
            queue_id = pending.get('id')
            patch_queue_item(queue_items, queue_id, {'status': 'running', 'started_at': now_str()})

    if not task and not args.no_auto_roadmap:
        roadmap_task, roadmap_hash = extract_roadmap_task()
        if roadmap_task and roadmap_hash and roadmap_hash != state.get('last_roadmap_hash'):
            task = roadmap_task
            source = 'roadmap'
            state['last_roadmap_hash'] = roadmap_hash

    if not task:
        return

    complexity = args.complexity
    if complexity == 'auto':
        complexity = infer_complexity(task)

    task_id = hashlib.md5(f"{task}|{int(time.time())}".encode('utf-8')).hexdigest()[:12]

    try:
        result = run_team(task, complexity, source, config)

        entry = {
            'timestamp': now_str(),
            'task_id': task_id,
            'task': task,
            'source': source,
            'complexity': complexity,
            'agents': [f"{item['role']}:{item['agent_id']}" for item in result['outputs']],
            'duration_sec': result['duration_sec'],
            'status': result['status'],
            'memory_context_items': result['memory_context_items'],
            'vector_store_written': result['vector_store_written'],
            'summary': result['summary'],
        }
        append_run_entry(entry)

        if queue_id and queue_items is not None:
            patch_queue_item(queue_items, queue_id, {
                'status': 'done',
                'finished_at': now_str(),
                'result': result['summary'][:500],
            })

        save_json(STATE_PATH, state)

    except Exception as exc:
        notify(f"[TEAM-RUN-ERROR] {exc}")
        if queue_id and queue_items is not None:
            patch_queue_item(queue_items, queue_id, {
                'status': 'failed',
                'finished_at': now_str(),
                'error': str(exc),
            })
        raise


if __name__ == '__main__':
    main()
