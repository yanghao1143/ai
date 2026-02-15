#!/bin/bash
# -------------------------------------------------
# Mac 端一键部署脚本 - 部署 Haodaer 完整克隆
# -------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="${HOME}/openclaw-workspace"

echo "🚀 开始部署 Haodaer 复制包..."

# 创建工作区结构
mkdir -p "${WORKSPACE}"/{memory/{archive,shared,research,nightly-build,channels},scripts,docs,skills}

# 复制核心文件
cp "${SCRIPT_DIR}"/*.md "${WORKSPACE}/" 2>/dev/null || true

# 复制记忆系统
cp -r "${SCRIPT_DIR}/memory/"* "${WORKSPACE}/memory/" 2>/dev/null || true

# 复制脚本
cp -r "${SCRIPT_DIR}/scripts/"* "${WORKSPACE}/scripts/" 2>/dev/null || true

# 复制文档
cp -r "${SCRIPT_DIR}/docs/"* "${WORKSPACE}/docs/" 2>/dev/null || true

# 设置脚本执行权限
chmod +x "${WORKSPACE}/scripts/"*.sh 2>/dev/null || true
chmod +x "${WORKSPACE}/scripts/"*.py 2>/dev/null || true

# 创建配置目录
mkdir -p ~/.config/openclaw
cp "${SCRIPT_DIR}/config/config.template.json" ~/.config/openclaw/config.json

# 创建 NOW.md（如果不存在）
if [ ! -f "${WORKSPACE}/NOW.md" ]; then
    cat > "${WORKSPACE}/NOW.md" << 'EOF'
# NOW - 当前焦点

> 每次会话开始时读取此文件

## 当前任务
- [ ] 开始使用自主进化框架

## 关键信息
- 工作区: ~/openclaw-workspace
- 记忆目录: ~/openclaw-workspace/memory
EOF
fi

echo ""
echo "✅ 部署完成！"
echo ""
echo "📂 工作区位置: ${WORKSPACE}"
echo ""
echo "📋 下一步："
echo "   1. 设置 API Key:"
echo "      nano ~/.config/openclaw/config.json"
echo "      # 将 \${ANTHROPIC_API_KEY} 替换为你的真实 key"
echo ""
echo "   2. 编辑个人信息:"
echo "      nano ${WORKSPACE}/USER.md"
echo ""
echo "   3. 启动 OpenClaw:"
echo "      cd ${WORKSPACE} && npx openclaw"
echo ""
echo "   4. (可选) 设置环境变量:"
echo "      echo 'export ANTHROPIC_API_KEY=\"your-key\"' >> ~/.zshrc"
echo "      source ~/.zshrc"
