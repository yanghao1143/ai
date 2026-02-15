#!/bin/bash
# 启动 Chromium CDP for OpenClaw browser 功能
# 原因：snap 版 Chromium 无法在 ~/.openclaw/browser/ 创建文件（AppArmor 限制）
# 解决方案：手动启动 CDP，用 snap 允许的路径

CDP_PORT=18800
USER_DATA_DIR="$HOME/snap/chromium/common/openclaw-browser"

# 检查是否已运行
if curl -s "http://localhost:$CDP_PORT/json/version" > /dev/null 2>&1; then
    echo "CDP already running on port $CDP_PORT"
    exit 0
fi

# 启动 CDP
mkdir -p "$USER_DATA_DIR"
nohup /usr/bin/chromium-browser \
    --headless \
    --no-sandbox \
    --disable-gpu \
    --disable-dev-shm-usage \
    --remote-debugging-port=$CDP_PORT \
    --user-data-dir="$USER_DATA_DIR" \
    > /tmp/chromium-cdp.log 2>&1 &

sleep 3

# 验证
if curl -s "http://localhost:$CDP_PORT/json/version" > /dev/null 2>&1; then
    echo "CDP started successfully on port $CDP_PORT"
else
    echo "Failed to start CDP"
    exit 1
fi
