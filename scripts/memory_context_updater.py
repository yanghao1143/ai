#!/usr/bin/env python3
"""memory_context_updater.py - Update recent_context.md from memory search results."""
import subprocess, json, os, glob, re
from datetime import datetime, timedelta
from pathlib import Path

BASE = "/home/tolls/.openclaw/workspace-clean"
MEMORY_DIR = f"{BASE}/memory"
CONTEXT_FILE = f"{MEMORY_DIR}/recent_context.md"
STATE_FILE = f"{MEMORY_DIR}/.context_updater_state.json"
OPENCLAW = "/usr/bin/openclaw"


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_index": None, "last_run": None, "run_count": 0}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, Exception) as e:
        return f"[error: {e}]"


def get_today_topics():
    today = datetime.now().strftime("%Y-%m-%d")
    topics = []
    for filepath in glob.glob(f"{MEMORY_DIR}/*.md"):
        name = os.path.basename(filepath)
        if name == "recent_context.md":
            continue
        if today in name or name == f"{today}.md":
            try:
                with open(filepath) as fh:
                    for line in fh:
                        m = re.match(r"^##\s+(.+)", line)
                        if m:
                            topics.append(m.group(1).strip())
            except Exception:
                pass
    return topics if topics else ["recent work", "current tasks", "progress"]


def memory_search(query):
    return run_cmd(f'{OPENCLAW} memory search "{query}"')


def memory_index():
    return run_cmd(f"{OPENCLAW} memory index", timeout=60)


def main():
    state = load_state()
    now = datetime.now()
    os.makedirs(MEMORY_DIR, exist_ok=True)

    # Rebuild index every 30 minutes
    last_index = state.get("last_index")
    if not last_index or (now - datetime.fromisoformat(last_index)) > timedelta(minutes=30):
        print(f"[{now.strftime('%H:%M:%S')}] Rebuilding memory index...")
        memory_index()
        state["last_index"] = now.isoformat()

    # Search topics
    topics = get_today_topics()
    results = []
    for topic in topics[:5]:
        out = memory_search(topic)
        if out and "[error" not in out:
            results.append(f"### {topic}\n{out}")

    # Write context file
    with open(CONTEXT_FILE, "w") as f:
        f.write(f"# Recent Memory Context\n")
        f.write(f"_Auto-updated: {now.strftime('%Y-%m-%d %H:%M')}_\n\n")
        if results:
            f.write("\n\n".join(results) + "\n")
        else:
            f.write("No recent memory results found.\n")

    state["last_run"] = now.isoformat()
    state["run_count"] = state.get("run_count", 0) + 1
    save_state(state)
    print(f"[{now.strftime('%H:%M:%S')}] Context updated. Topics: {len(topics)}, Results: {len(results)}")


if __name__ == "__main__":
    main()
