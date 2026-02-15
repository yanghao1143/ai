#!/bin/bash
# install-auto-recover.sh - 安装 400 自动恢复服务
# 用法: ./install-auto-recover.sh [install|uninstall|status]

SERVICE_NAME="openclaw-auto-recover"
SCRIPT_PATH="$HOME/.openclaw/workspace/scripts/auto-recover-400.sh"

case "$1" in
    install)
        echo "📦 安装 systemd 服务..."
        
        cat > /tmp/${SERVICE_NAME}.service << UNIT
[Unit]
Description=OpenClaw 400 Error Auto Recovery
After=network.target

[Service]
Type=simple
ExecStart=$SCRIPT_PATH
Restart=always
RestartSec=10
User=$USER

[Install]
WantedBy=multi-user.target
UNIT
        
        sudo mv /tmp/${SERVICE_NAME}.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable ${SERVICE_NAME}
        sudo systemctl start ${SERVICE_NAME}
        
        echo "✅ 服务已安装并启动"
        systemctl status ${SERVICE_NAME} --no-pager
        ;;
        
    uninstall)
        echo "🗑️ 卸载服务..."
        sudo systemctl stop ${SERVICE_NAME} 2>/dev/null
        sudo systemctl disable ${SERVICE_NAME} 2>/dev/null
        sudo rm -f /etc/systemd/system/${SERVICE_NAME}.service
        sudo systemctl daemon-reload
        echo "✅ 服务已卸载"
        ;;
        
    status)
        systemctl status ${SERVICE_NAME} --no-pager
        ;;
        
    *)
        echo "用法: $0 [install|uninstall|status]"
        exit 1
        ;;
esac
