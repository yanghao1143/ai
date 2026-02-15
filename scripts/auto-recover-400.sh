#!/bin/bash
# auto-recover-400.sh - 自动恢复 400 错误（v4 - 精确匹配）
# 
# 用法: ./auto-recover-400.sh [--trigger=message|wake|none] [agent_name]

TRIGGER="wake"
AGENT="main"
for arg in "$@"; do
    case $arg in
        --trigger=*) TRIGGER="${arg#*=}" ;;
        *) AGENT="$arg" ;;
    esac
done

SESSION_DIR="$HOME/.openclaw/agents/$AGENT/sessions"
WORKSPACE="$HOME/.openclaw/workspace"
STATE_FILE="$WORKSPACE/SESSION-STATE.md"
LOGFILE="/tmp/auto-recover-400.log"
LOCKFILE="/tmp/auto-recover-400.lock"
COOLDOWN=30

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOGFILE"
}

extract_recent_messages() {
    local session_file="$1"
    local n="${2:-20}"
    jq -r 'select(.type == "message") | select(.message.role == "user" or .message.role == "assistant") | "[\(.message.role)]: " + (.message.content[] | select(.type == "text") | .text // empty)' "$session_file" 2>/dev/null | tail -n "$n"
}

save_recovery_state() {
    local session_file="$1"
    local recent_messages
    recent_messages=$(extract_recent_messages "$session_file" 20)
    if [ -n "$recent_messages" ]; then
        cat > "$STATE_FILE" << STATEEOF
# SESSION-STATE.md — 400 自动恢复 $(date '+%Y-%m-%d %H:%M:%S')

## 恢复的对话上下文
\`\`\`
$recent_messages
\`\`\`
STATEEOF
        log "💾 已保存恢复状态"
        return 0
    fi
    return 1
}

trigger_new_session() {
    case "$TRIGGER" in
        message) openclaw message send --channel mattermost --target "#agent-learning" --message "⚠️ 400 已自动恢复" 2>&1 | tee -a "$LOGFILE" ;;
        wake) openclaw cron wake --mode now 2>&1 | tee -a "$LOGFILE" ;;
        none) log "等待用户消息" ;;
    esac
}

[ -f "$LOCKFILE" ] && kill -0 "$(cat $LOCKFILE)" 2>/dev/null && echo "已在运行" && exit 1
echo $$ > "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

log "🚀 启动监控 (agent: $AGENT, trigger: $TRIGGER)"

START_TIME=$(date -u +%Y-%m-%dT%H:%M:%S)
log "📅 只处理 $START_TIME 之后的日志"

LAST_TRIGGER=0

openclaw logs --follow 2>&1 | while read -r line; do
    # 提取日志时间戳
    LOG_TIME=$(echo "$line" | grep -oP '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}' | head -1)
    
    # 跳过启动时间之前的日志
    if [ -n "$LOG_TIME" ] && [[ "$LOG_TIME" < "$START_TIME" ]]; then
        continue
    fi
    
    # 精确匹配 API 400 错误（只匹配 API 返回的错误，不匹配讨论内容）
    # 典型格式: "error" + "400" + "invalid_request" 或 "status":400
    if echo "$line" | grep -qE '"status":\s*400|"type":\s*"invalid_request_error"|HTTP/[0-9.]+ 400'; then
        NOW=$(date +%s)
        ELAPSED=$((NOW - LAST_TRIGGER))
        
        [ $ELAPSED -lt $COOLDOWN ] && continue
        
        log "⚠️ 检测到 API 400 错误"
        log "📝 日志: $line"
        
        LATEST=$(ls -t "$SESSION_DIR"/*.jsonl 2>/dev/null | head -1)
        
        if [ -n "$LATEST" ]; then
            log "📄 处理 session: $(basename $LATEST)"
            save_recovery_state "$LATEST"
            rm "$LATEST"
            log "🗑️ 已删除损坏的 session"
            trigger_new_session
            LAST_TRIGGER=$NOW
            log "✅ 恢复完成"
        else
            log "⚠️ 找不到 session 文件"
        fi
    fi
done
