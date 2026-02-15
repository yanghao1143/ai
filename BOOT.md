# Boot Checklist

On startup, perform these initialization steps:

## 1. Memory Check
- Run memory_search with query "最近工作 进展 决策" to load recent context
- Read memory/recent_context.md for a quick summary of recent work
- If memory_search returns no results, report: "[BOOT] Warning: memory empty"

## 2. Self-Check
- Confirm you can access workspace scripts at scripts/
- Confirm memory directory exists at memory/
- Read today's memory file if it exists: memory/YYYY-MM-DD.md

## 3. Startup Report
Send a brief notification:
"[BOOT] 网关已启动。记忆系统就绪。最近记忆已加载。"
