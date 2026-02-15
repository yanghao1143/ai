#!/usr/bin/env python3
import json
import os
import random
import re
import socket
import time
import hashlib
from datetime import datetime
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import subprocess

STATE_PATH = os.environ.get('LEARN_STATE', '/home/tolls/.openclaw/workspace-clean/memory/.learning_state.json')
MEMORY_DIR = '/home/tolls/.openclaw/workspace-clean/memory/learning'
LOG_PATH = os.environ.get('LEARN_LOG', '/home/tolls/.openclaw/workspace-clean/memory/learning/auto_learn.log')
NOTIFY_CMD = ['/usr/bin/openclaw', 'system', 'event', '--mode', 'now', '--text']
OPENCLAW_CONFIG_PATH = '/home/tolls/.openclaw/openclaw.json'

# multi-endpoint fallback per source to reduce intermittent timeout failures
SOURCES = {
    'skills': [
        'https://skills.sh/',
        'https://skills.sh/skills',
    ],
    'moltbook': [
        'https://www.moltbook.com/',
        'https://moltbook.com/skill.md',
    ],
}

FETCH_TIMEOUT = int(os.environ.get('AUTO_LEARN_TIMEOUT', '25'))
FETCH_RETRIES = int(os.environ.get('AUTO_LEARN_RETRIES', '3'))
RETRY_BACKOFF_SECONDS = float(os.environ.get('AUTO_LEARN_BACKOFF', '1.4'))
ERROR_NOTIFY_COOLDOWN = int(os.environ.get('AUTO_LEARN_ERROR_COOLDOWN', '7200'))

STOPWORDS = {
    'sign in', 'login', 'sign up', 'subscribe', 'privacy', 'terms',
    'contact', 'about', 'help', 'home', 'blog', 'docs', 'pricing',
    'menu', 'search', 'more', 'new', 'popular', 'latest',
}


class TextCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.items = []
        self.buffer = []
        self.tags = {'h1', 'h2', 'h3', 'a', 'title'}

    def handle_starttag(self, tag, attrs):
        if tag in self.tags:
            self.capture = True
            self.buffer = []

    def handle_endtag(self, tag):
        if tag in self.tags and self.capture:
            text = ''.join(self.buffer).strip()
            if text:
                self.items.append(text)
            self.capture = False
            self.buffer = []

    def handle_data(self, data):
        if self.capture:
            self.buffer.append(data)


def write_log(line):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_PATH, 'a', encoding='utf-8') as file:
        file.write(f'[{ts}] {line}\n')


def notify(message):
    try:
        subprocess.run(NOTIFY_CMD + [message], check=False)
    except Exception:
        pass


def load_state():
    if not os.path.exists(STATE_PATH):
        return {
            'sources': {},
            'last_notify': 0,
            'last_health': 0,
            'last_error_notify': 0,
        }
    try:
        with open(STATE_PATH, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception:
        return {
            'sources': {},
            'last_notify': 0,
            'last_health': 0,
            'last_error_notify': 0,
        }


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, 'w', encoding='utf-8') as file:
        json.dump(state, file, ensure_ascii=False, indent=2)


def clean_text(value):
    return re.sub(r'\s+', ' ', value).strip()


def extract_candidates(raw_text, limit=25):
    parser = TextCollector()
    parser.feed(raw_text)
    seen = set()
    results = []

    for item in parser.items:
        text = clean_text(item)
        if len(text) < 3 or len(text) > 100:
            continue
        lower = text.lower()
        if lower in STOPWORDS:
            continue
        if lower in seen:
            continue
        seen.add(lower)
        results.append(text)
        if len(results) >= limit:
            break

    return results


_cached_moltbook_key = None


def get_moltbook_key():
    global _cached_moltbook_key
    if _cached_moltbook_key is not None:
        return _cached_moltbook_key

    env_key = os.environ.get('MOLTBOOK_API_KEY')
    if env_key:
        _cached_moltbook_key = env_key
        return _cached_moltbook_key

    try:
        with open(OPENCLAW_CONFIG_PATH, 'r', encoding='utf-8') as file:
            cfg = json.load(file)
        key = (cfg.get('env') or {}).get('MOLTBOOK_API_KEY')
        _cached_moltbook_key = key or ''
        return _cached_moltbook_key
    except Exception:
        _cached_moltbook_key = ''
        return _cached_moltbook_key

def build_headers(url):
    headers = {'User-Agent': 'OpenClaw-AutoLearn/2.0'}
    moltbook_key = get_moltbook_key()
    if 'moltbook.com' in url and moltbook_key:
        headers['Authorization'] = f'Bearer {moltbook_key}'
        headers['X-API-Key'] = moltbook_key
    return headers


def fetch_once(url, timeout):
    request = Request(url, headers=build_headers(url))
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode('utf-8', errors='ignore')


def fetch_with_retries(url, retries=FETCH_RETRIES, timeout=FETCH_TIMEOUT):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            html = fetch_once(url, timeout=timeout)
            return html, None
        except (HTTPError, URLError, TimeoutError, socket.timeout, OSError) as exc:
            last_error = exc
            if attempt < retries:
                sleep_for = RETRY_BACKOFF_SECONDS * attempt + random.uniform(0.0, 0.4)
                time.sleep(sleep_for)
    return None, last_error


def hash_items(items):
    return hashlib.sha256('\n'.join(items).encode('utf-8')).hexdigest()


def append_memory(source_name, items):
    os.makedirs(MEMORY_DIR, exist_ok=True)
    date_str = datetime.now().strftime('%Y-%m-%d')
    path = os.path.join(MEMORY_DIR, f'{date_str}.md')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    lines = [f'## {timestamp} | {source_name}', '']
    for item in items[:15]:
        lines.append(f'- {item}')
    lines.append('')

    with open(path, 'a', encoding='utf-8') as file:
        file.write('\n'.join(lines))


def fetch_source(source_name, urls):
    endpoint_errors = []
    for url in urls:
        html, err = fetch_with_retries(url)
        if err is not None:
            endpoint_errors.append(f'{url}: {err}')
            continue

        items = extract_candidates(html)
        if items:
            write_log(f'source={source_name} endpoint={url} items={len(items)} status=ok')
            return items, url, None

        endpoint_errors.append(f'{url}: no items extracted')

    err_msg = '; '.join(endpoint_errors) if endpoint_errors else 'unknown fetch error'
    write_log(f'source={source_name} status=failed detail={err_msg}')
    return None, None, err_msg


def main():
    state = load_state()
    source_state = state.get('sources', {})

    updated_sources = []
    unchanged_sources = []
    failed_sources = []

    for source_name, urls in SOURCES.items():
        items, endpoint, err = fetch_source(source_name, urls)

        if err is not None:
            failed_sources.append((source_name, err))
            continue

        current_hash = hash_items(items)
        prev_hash = source_state.get(source_name, {}).get('hash')

        if current_hash != prev_hash:
            append_memory(source_name, items)
            source_state[source_name] = {
                'hash': current_hash,
                'updated': int(time.time()),
                'endpoint': endpoint,
            }
            updated_sources.append((source_name, items, endpoint))
        else:
            unchanged_sources.append((source_name, endpoint))

    state['sources'] = source_state
    now = int(time.time())

    if updated_sources:
        summary = []
        for source_name, items, endpoint in updated_sources:
            preview = '?'.join(items[:5])
            summary.append(f'{source_name}@{endpoint} updated: {preview}')
        notify('[AUTO-LEARN] update\n' + '\n'.join(summary))
        state['last_notify'] = now
        write_log(f'notify=update updated={len(updated_sources)} failed={len(failed_sources)}')

    elif failed_sources and not unchanged_sources:
        # all sources failed: raise error with cooldown
        last_error_notify = int(state.get('last_error_notify', 0))
        if now - last_error_notify >= ERROR_NOTIFY_COOLDOWN:
            text = '\n'.join(f'{name}: {err}' for name, err in failed_sources[:4])
            notify('[AUTO-LEARN] failed\n' + text)
            state['last_error_notify'] = now
        write_log(f'notify=failed failed_sources={len(failed_sources)}')

    elif failed_sources and unchanged_sources:
        # partial failure but still healthy enough; do not spam hard failures
        details = ', '.join(name for name, _ in failed_sources)
        write_log(f'partial_failure={details} unchanged={len(unchanged_sources)}')

    else:
        last_health = int(state.get('last_health', 0))
        if now - last_health >= 3600:
            notify('[HEALTH] auto-learn healthy: no new updates.')
            state['last_health'] = now
        write_log('notify=health')

    save_state(state)


if __name__ == '__main__':
    main()
