#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import os
import subprocess
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LEARNING_DIR = '/home/tolls/.openclaw/workspace-clean/memory/learning'
ROADMAP_PATH = '/home/tolls/.openclaw/workspace-clean/memory/learning/roadmap.md'
STATE_PATH = '/home/tolls/.openclaw/workspace-clean/memory/.roadmap_state.json'
OPENCLAW_CONFIG = '/home/tolls/.openclaw/openclaw.json'
VECTOR_SEARCH_PATH = '/home/tolls/.openclaw/workspace-clean/scripts/vector_search.py'
NOTIFY_CMD = ['/usr/bin/openclaw', 'system', 'event', '--mode', 'now', '--text']

MAX_FILES = 5
MAX_LINES = 260

REQUIRED_HEADERS = [
    '# Weekly Priorities',
    '# Monthly Iteration Plan',
    '# Risks and Dependencies',
    '# Team Split',
    '# Acceptance Milestones',
]


def load_state():
    if not os.path.exists(STATE_PATH):
        return {'hash': '', 'updated': 0, 'source': ''}
    try:
        with open(STATE_PATH, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception:
        return {'hash': '', 'updated': 0, 'source': ''}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, 'w', encoding='utf-8') as file:
        json.dump(state, file, ensure_ascii=False, indent=2)


def notify(text):
    try:
        subprocess.run(NOTIFY_CMD + [text], check=False)
    except Exception:
        pass


def collect_learning_lines():
    if not os.path.exists(LEARNING_DIR):
        return []

    files = [name for name in os.listdir(LEARNING_DIR) if name.endswith('.md')]
    files.sort(reverse=True)

    lines = []
    for name in files[:MAX_FILES]:
        path = os.path.join(LEARNING_DIR, name)
        try:
            with open(path, 'r', encoding='utf-8') as file:
                lines.extend(file.read().splitlines())
        except OSError:
            continue
        if len(lines) >= MAX_LINES:
            break

    return lines[:MAX_LINES]


def load_vector_context(query='roadmap priorities risks team split', top_k=6):
    if not os.path.exists(VECTOR_SEARCH_PATH):
        return []

    try:
        spec = importlib.util.spec_from_file_location('vector_search_runtime', VECTOR_SEARCH_PATH)
        if not spec or not spec.loader:
            return []
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rows = module.search(query, top_k=top_k, min_score=0.28)

        snippets = []
        for row in rows:
            text = (row.get('content') or row.get('summary') or '').strip()
            if not text:
                continue
            snippets.append({
                'id': row.get('id'),
                'score': row.get('score'),
                'session_id': row.get('session_id'),
                'text': text[:350],
            })
        return snippets
    except Exception:
        return []


def load_model_runtime():
    with open(OPENCLAW_CONFIG, 'r', encoding='utf-8') as file:
        cfg = json.load(file)

    primary = cfg.get('agents', {}).get('defaults', {}).get('model', {}).get('primary')
    providers = cfg.get('models', {}).get('providers', {})

    if not primary or '/' not in primary:
        raise RuntimeError('Invalid primary model in openclaw config')

    provider_id, model_id = primary.split('/', 1)
    provider = providers.get(provider_id, {})

    base_url = provider.get('baseUrl') or cfg.get('env', {}).get('OPENAI_BASE_URL')
    api_key = provider.get('apiKey') or cfg.get('env', {}).get('OPENAI_API_KEY')

    if not base_url or not api_key:
        raise RuntimeError('Missing runtime base_url/api_key')

    return {
        'provider_id': provider_id,
        'model_id': model_id,
        'base_url': base_url.rstrip('/'),
        'api_key': api_key,
    }


def call_chat_api(runtime, system_prompt, user_prompt, timeout=120):
    endpoint = runtime['base_url'] + '/chat/completions'
    payload = {
        'model': runtime['model_id'],
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'temperature': 0.25,
        'max_tokens': 1500,
    }

    request = Request(
        endpoint,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {runtime['api_key']}",
        },
        method='POST',
    )

    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode('utf-8', errors='ignore')

    data = json.loads(body)
    choices = data.get('choices') or []
    if not choices:
        raise RuntimeError('Chat API returned no choices')

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
        raise RuntimeError('Chat API returned empty content')

    return content


def generate_with_gateway(prompt):
    command = [
        '/usr/bin/openclaw', 'agent',
        '--session-id', 'roadmap-auto',
        '--message', prompt,
        '--thinking', 'off',
        '--timeout', '120',
    ]

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    output = (result.stdout or '').strip()
    error = (result.stderr or '').strip()

    if result.returncode != 0:
        raise RuntimeError(error or f'Gateway return code: {result.returncode}')

    bad_markers = [
        'Gateway agent failed',
        'gateway closed',
        'spawn docker ENOENT',
        'Config invalid',
    ]
    if any(marker in output for marker in bad_markers) or any(marker in error for marker in bad_markers):
        raise RuntimeError('Gateway path unavailable')

    if not output:
        raise RuntimeError('Gateway returned empty output')

    return output


def is_valid_roadmap(markdown):
    if not markdown:
        return False
    return all(header in markdown for header in REQUIRED_HEADERS)


def build_prompt(learning_lines, vector_rows):
    vector_block = []
    if vector_rows:
        vector_block.append('Related memory snippets from pgvector:')
        for row in vector_rows:
            vector_block.append(
                f"- [score={row['score']}] session={row['session_id']} text={row['text']}"
            )

    prompt_lines = [
        'Generate an actionable development roadmap in Markdown.',
        'Return exactly these top-level headings:',
        '# Weekly Priorities',
        '# Monthly Iteration Plan',
        '# Risks and Dependencies',
        '# Team Split',
        '# Acceptance Milestones',
        'Each section must contain concrete actions, owners, and measurable checkpoints.',
        '',
        'Learning notes:',
        *learning_lines,
    ]

    if vector_block:
        prompt_lines.extend(['', *vector_block])

    return '\n'.join(prompt_lines)


def save_roadmap(markdown, source):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    os.makedirs(os.path.dirname(ROADMAP_PATH), exist_ok=True)
    with open(ROADMAP_PATH, 'w', encoding='utf-8') as file:
        file.write('# Development Roadmap\n\n')
        file.write(f'Updated at: {timestamp}\n')
        file.write(f'Source: {source}\n\n')
        file.write(markdown.strip())
        file.write('\n')


def main():
    learning_lines = collect_learning_lines()
    if not learning_lines:
        return

    vector_rows = load_vector_context()
    hash_source = '\n'.join(learning_lines) + '\n' + json.dumps(vector_rows, ensure_ascii=False)
    current_hash = hashlib.sha256(hash_source.encode('utf-8')).hexdigest()

    state = load_state()
    if state.get('hash') == current_hash:
        return

    prompt = build_prompt(learning_lines, vector_rows)
    runtime = load_model_runtime()

    gateway_error = None
    roadmap = None
    source = None

    try:
        candidate = generate_with_gateway(prompt)
        if is_valid_roadmap(candidate):
            roadmap = candidate
            source = 'gateway'
        else:
            gateway_error = 'gateway output missing required headers'
    except Exception as exc:
        gateway_error = str(exc)

    if roadmap is None:
        try:
            system_prompt = 'You are an engineering director. Output a strict actionable roadmap format.'
            candidate = call_chat_api(runtime, system_prompt, prompt)
            if not is_valid_roadmap(candidate):
                raise RuntimeError('api output missing required headers')
            roadmap = candidate
            source = f"api:{runtime['provider_id']}/{runtime['model_id']}"
        except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError) as api_exc:
            notify(f"[ROADMAP-ERROR] gateway={gateway_error} | api={api_exc}")
            return

    save_roadmap(roadmap, source)
    save_state({'hash': current_hash, 'updated': time.time(), 'source': source})
    notify(f"[ROADMAP] updated successfully (source={source})")


if __name__ == '__main__':
    main()
