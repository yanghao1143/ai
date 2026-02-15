#!/bin/bash
#
# 为Mattermost Bot配置Opus-4-6模型
# 支持的Bot: supporter, secguard, opsguard
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
API_BASE_URL="http://107.172.187.231:8317"
OPUS46_MODEL="claude-opus-4-6"
OPUS45_MODEL="claude-opus-4-5-20251101"

# Bot列表
BOTS=("supporter" "secguard" "opsguard")

# 检查是否在正确的环境
if [ ! -d "/home/ubuntu" ]; then
    echo -e "${RED}✗ 错误: 此脚本应在Ubuntu服务器上运行${NC}"
    echo "请SSH到服务器后执行此脚本"
    exit 1
fi

echo -e "${GREEN}=== 开始配置Opus-4.6模型 ===${NC}\n"

# 遍历所有bot
for bot in "${BOTS[@]}"; do
    bot_config_dir="/home/ubuntu/.openclaw-$bot"
    bot_config_file="$bot_config_dir/openclaw.json"

    echo -e "${YELLOW}┌─ 处理: $bot${NC}"

    # 检查配置目录是否存在
    if [ ! -d "$bot_config_dir" ]; then
        echo -e "${RED}  ✗ 配置目录不存在: $bot_config_dir${NC}"
        continue
    fi

    # 检查配置文件是否存在
    if [ ! -f "$bot_config_file" ]; then
        echo -e "${RED}  ✗ 配置文件不存在: $bot_config_file${NC}"
        continue
    fi

    # 备份原配置
    backup_date=$(date +"%Y%m%d_%H%M%S")
    backup_file="$bot_config_file.backup.$backup_date"
    cp "$bot_config_file" "$backup_file"
    echo -e "  ✓ 已备份: $backup_file"

    # 使用Python脚本更新配置
    python3 << PYTHON_SCRIPT
import json
import sys

bot_config_file = "$bot_config_file"
api_base_url = "$API_BASE_URL"
opus46_model = "$OPUS46_MODEL"
opus45_model = "$OPUS45_MODEL"

try:
    # 读取配置
    with open(bot_config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 确保 providers 存在
    if 'models' not in config:
        config['models'] = {}
    if 'providers' not in config['models']:
        config['models']['providers'] = {}

    # 添加/更新 mjy provider
    config['models']['providers']['mjy'] = {
        "baseUrl": api_base_url,
        "apiKey": "mjy-key-placeholder",  # 需要替换为实际API key
        "api": "anthropic",
        "models": [
            {
                "id": opus46_model,
                "name": f"Claude Opus 4.6 (mjy)",
                "reasoning": True,
                "input": ["text"],
                "cost": {
                    "input": 0,
                    "output": 0,
                    "cacheRead": 0,
                    "cacheWrite": 0
                },
                "contextWindow": 200000,
                "maxTokens": 8192
            },
            {
                "id": opus45_model,
                "name": f"Claude Opus 4.5 (mjy)",
                "reasoning": True,
                "input": ["text"],
                "cost": {
                    "input": 0,
                    "output": 0,
                    "cacheRead": 0,
                    "cacheWrite": 0
                },
                "contextWindow": 200000,
                "maxTokens": 8192
            }
        ]
    }

    # 更新默认模型配置
    if 'agents' not in config:
        config['agents'] = {}
    if 'defaults' not in config['agents']:
        config['agents']['defaults'] = {}

    # 设置主模型为 opus-4-6
    config['agents']['defaults']['model'] = {
        "primary": f"mjy/{opus46_model}",
        "fallbacks": [
            f"mjy/{opus45_model}"
        ]
    }

    # 更新 agents list
    if 'list' not in config['agents']:
        config['agents']['list'] = []

    for agent in config['agents']['list']:
        if 'id' in agent:
            agent['model'] = f"mjy/{opus46_model}"
            if 'subagents' not in agent:
                agent['subagents'] = {}
            agent['subagents']['model'] = f"mjy/{opus46_model}"

    # 更新 subagents 配置
    config['agents']['defaults']['subagents'] = {
        "maxConcurrent": 12,
        "model": f"mjy/{opus46_model}"
    }

    # 保存配置
    with open(bot_config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"  ✓ 配置已更新: opus-4-6")

except Exception as e:
    print(f"  ✗ 更新失败: {str(e)}", file=sys.stderr)
    sys.exit(1)
PYTHON_SCRIPT

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✓ $bot 配置完成${NC}\n"
    else
        echo -e "${RED}  ✗ $bot 配置失败${NC}\n"
    fi
done

echo -e "${GREEN}=== 配置完成 ===${NC}"
echo ""
echo -e "${YELLOW}⚠️ 重要提示:${NC}"
echo "1. 需要在配置中替换 mjy-key-placeholder 为实际的 API Key"
echo "2. 重启所有bot使配置生效:"
echo "   docker restart openclaw-supporter"
echo "   docker restart openclaw-secguard"
echo "   docker restart openclaw-opsguard"
echo ""
