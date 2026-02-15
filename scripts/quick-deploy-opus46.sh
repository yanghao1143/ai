#!/bin/bash
#
# 快速配置Opus-4.6模型 - 一键部署版本
#

# 配置（需手动设置）
API_KEY="${MJY_API_KEY:-请设置MJY_API_KEY环境变量}"
API_BASE="http://107.172.187.231:8317"
MODEL_MAIN="claude-opus-4-6"
MODEL_BACKUP="claude-opus-4-5-20251101"

# Bot列表和端口
declare -A BOTS=(
    ["supporter"]="18830"
    ["secguard"]="18791"
    ["opsguard"]="18820"
)

# 函数：备份配置
backup_config() {
    local bot=$1
    local config_dir="/home/ubuntu/.openclaw-$bot"
    local backup_dir="$config_dir/backups"
    mkdir -p "$backup_dir"
    cp "$config_dir/openclaw.json" "$backup_dir/openclaw.json.$(date +%Y%m%d_%H%M%S)"
}

# 函数：更新配置
update_bot_config() {
    local bot=$1
    local config_dir="/home/ubuntu/.openclaw-$bot"
    local config_file="$config_dir/openclaw.json"

    if [ ! -f "$config_file" ]; then
        echo "  ✗ 配置文件不存在: $config_file"
        return 1
    fi

    # 使用jq更新配置（如果没有jq则用Python）
    if command -v jq &> /dev/null; then
        jq --arg api "$API_KEY" \
           --arg url "$API_BASE" \
           --arg model "$MODEL_MAIN" \
           --arg backup "$MODEL_BACKUP" '
        .models.providers.mjy = {
            "baseUrl": $url,
            "apiKey": $api,
            "api": "anthropic",
            "models": [
                {
                    "id": $model,
                    "name": "Claude Opus 4.6 (mjy)",
                    "reasoning": true,
                    "input": ["text"],
                    "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                    "contextWindow": 200000,
                    "maxTokens": 8192
                },
                {
                    "id": $backup,
                    "name": "Claude Opus 4.5 (mjy)",
                    "reasoning": true,
                    "input": ["text"],
                    "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                    "contextWindow": 200000,
                    "maxTokens": 8192
                }
            ]
        } |
        .agents.defaults.model = {
            "primary": ("mjy/" + $model),
            "fallbacks": ["mjy/" + $backup]
        } |
        .agents.defaults.subagents.model = ("mjy/" + $model) |
        (.agents.list // []) | map(.model = ("mjy/" + $model)) |
        .agents.list = (. + {"model": ("mjy/" + $model)} | unique)
        ' "$config_file" > "$config_file.tmp" && mv "$config_file.tmp" "$config_file"
    else
        # Fallback: 使用Python
        python3 << EOF
import json

with open('$config_file', 'r') as f:
    config = json.load(f)

# Provider
if 'models' not in config:
    config['models'] = {}
if 'providers' not in config['models']:
    config['models']['providers'] = {}

config['models']['providers']['mjy'] = {
    "baseUrl": "$API_BASE",
    "apiKey": "$API_KEY",
    "api": "anthropic",
    "models": [
        {
            "id": "$MODEL_MAIN",
            "name": "Claude Opus 4.6 (mjy)",
            "reasoning": True,
            "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 200000,
            "maxTokens": 8192
        },
        {
            "id": "$MODEL_BACKUP",
            "name": "Claude Opus 4.5 (mjy)",
            "reasoning": True,
            "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 200000,
            "maxTokens": 8192
        }
    ]
}

# Default model
if 'agents' not in config:
    config['agents'] = {}
if 'defaults' not in config['agents']:
    config['agents']['defaults'] = {}

config['agents']['defaults']['model'] = {
    "primary": "mjy/$MODEL_MAIN",
    "fallbacks": ["mjy/$MODEL_BACKUP"]
}

config['agents']['defaults']['subagents'] = {
    "maxConcurrent": 12,
    "model": "mjy/$MODEL_MAIN"
}

# Update agent list
if 'list' in config['agents']:
    for agent in config['agents']['list']:
        agent['model'] = "mjy/$MODEL_MAIN"

with open('$config_file', 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
EOF
    fi

    return $?
}

# 函数：重启Bot
restart_bot() {
    local bot=$1
    local container="openclaw-$bot"

    echo "  → 重启容器..."
    docker restart "$container" > /dev/null 2>&1

    # 等待启动
    local count=0
    while [ $count -lt 10 ]; do
        if docker ps | grep -q "$container"; then
            echo "  ✓ 已启动"
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done

    echo "  ✗ 启动失败"
    return 1
}

# 主函数
main() {
    echo "🚀 配置Opus-4.6模型"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # 检查API KEY
    if [ "$API_KEY" = "请设置MJY_API_KEY环境变量" ]; then
        echo "❌ 错误: 请先设置 MJY_API_KEY 环境变量"
        echo ""
        echo "示例:"
        echo "  export MJY_API_KEY='sk-xxx'"
        echo "  $0"
        echo ""
        exit 1
    fi

    successes=0
    failures=0

    # 遍历所有bot
    for bot in "${!BOTS[@]}"; do
        port=${BOTS[$bot]}
        echo "📦 [$bot] on port $port"

        # 备份
        backup_config "$bot" && echo "  ✓ 已备份配置"

        # 更新
        if update_bot_config "$bot"; then
            echo "  ✓ 配置已更新"

            # 重启
            if restart_bot "$bot"; then
                successes=$((successes + 1))
            else
                failures=$((failures + 1))
            fi
        else
            echo "  ✗ 配置更新失败"
            failures=$((failures + 1))
        fi

        echo ""
    done

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ 成功: $successes | ❌ 失败: $failures"
    echo ""
    echo "下一步:"
    echo "  1. 验证Bot运行状态: docker ps | grep openclaw"
    echo "  2. 查看日志: docker logs openclaw-supporter | tail -50"
    echo "  3. 在Mattermost测试响应"
    echo ""
}

# 执行
main
