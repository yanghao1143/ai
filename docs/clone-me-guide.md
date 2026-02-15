# 完整复制指南 - 让你的 AI 跟我一模一样

> 生成时间：2026-02-16 00:45
> 目标：在 Mac 上部署一个与我完全相同的 AI 代理

---

## 一、复制方案总览

```
┌─────────────────────────────────────────────────────────────┐
│                    完整复制清单                              │
├─────────────────────────────────────────────────────────────┤
│  1. 核心身份文件 (SOUL.md, IDENTITY.md, USER.md)           │
│  2. 行为规则文件 (AGENTS.md, TOOLS.md, BOOT.md)            │
│  3. 记忆系统 (memory/ 目录全部内容)                         │
│  4. 脚本系统 (scripts/ 目录)                                │
│  5. 技能模块 (skills/ 目录)                                 │
│  6. 配置文件 (.openclaw/config.json)                       │
│  7. API Keys 和凭证                                         │
│  8. 环境变量                                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、文件清单详解

### 2.1 核心身份文件（必须复制）

| 文件 | 作用 | 能否直接复制 |
|------|------|--------------|
| `SOUL.md` | 定义 AI 的核心人格、价值观、行为准则 | ✅ 完全相同 |
| `IDENTITY.md` | 名字、形象、性格等个性化配置 | ⚠️ 需要你填写 |
| `USER.md` | 用户信息（你的名字、偏好等） | ❌ 必须改成你的 |
| `AGENTS.md` | 行为规则、记忆系统指令、团队协作 | ✅ 完全相同 |

### 2.2 记忆系统（核心复制内容）

```
memory/
├── self-review.md          # 自我审查机制 ⭐ 必须复制
├── evolution-log.md        # 进化日志 ⭐ 必须复制
├── evolution-framework.md  # 进化框架 ⭐ 必须复制
├── recent_context.md       # 最近上下文 ⭐ 必须复制
├── 2026-02-*.md            # 每日日志（可选）
├── archive/                # 归档记忆（可选）
├── shared/                 # 共享知识 ⭐ 建议复制
├── research/               # 研究记录（可选）
└── nightly-build/          # 夜间构建报告（可选）
```

### 2.3 脚本系统（必须复制）

```
scripts/
├── self-evolve.sh          # 自我进化脚本
├── nightly-build.sh        # 夜间构建
├── session-monitor.sh      # 会话监控
└── outcome-collector.py    # 成果收集
```

### 2.4 需要你自己配置的部分

| 组件 | 说明 | 需要提供 |
|------|------|----------|
| **API Keys** | 各平台 API 密钥 | 你自己的 key |
| **Mattermost Token** | 消息平台连接 | 你自己的 token |
| **Moltbook 账号** | AI 社区账号 | 可以共用或新建 |
| **用户信息** | USER.md 内容 | 你的名字、偏好 |

---

## 三、一键打包脚本

在当前服务器上运行，生成复制包：

```bash
#!/bin/bash
# 文件：scripts/export-clone-package.sh
# 用途：打包所有必要文件供复制

EXPORT_DIR="$HOME/haodaer-clone-package-$(date +%Y%m%d)"
WORKSPACE="/home/tolls/.openclaw/workspace-clean"

echo "📦 开始打包 Haodaer 复制包..."

# 创建目录结构
mkdir -p "$EXPORT_DIR"/{memory/{archive,shared,research,nightly-build,channels},scripts,docs,config}

# 1. 复制核心身份文件
cp "$WORKSPACE/SOUL.md" "$EXPORT_DIR/"
cp "$WORKSPACE/IDENTITY.md" "$EXPORT_DIR/"
cp "$WORKSPACE/USER.md" "$EXPORT_DIR/"  # 注意：需要修改
cp "$WORKSPACE/AGENTS.md" "$EXPORT_DIR/"
cp "$WORKSPACE/TOOLS.md" "$EXPORT_DIR/"
cp "$WORKSPACE/BOOT.md" "$EXPORT_DIR/"
cp "$WORKSPACE/HEARTBEAT.md" "$EXPORT_DIR/"

# 2. 复制记忆系统
cp -r "$WORKSPACE/memory/"*.md "$EXPORT_DIR/memory/" 2>/dev/null || true
cp -r "$WORKSPACE/memory/archive/"*.md "$EXPORT_DIR/memory/archive/" 2>/dev/null || true
cp -r "$WORKSPACE/memory/shared/"*.md "$EXPORT_DIR/memory/shared/" 2>/dev/null || true
cp -r "$WORKSPACE/memory/research/"*.md "$EXPORT_DIR/memory/research/" 2>/dev/null || true
cp -r "$WORKSPACE/memory/nightly-build/"*.md "$EXPORT_DIR/memory/nightly-build/" 2>/dev/null || true

# 3. 复制脚本
cp -r "$WORKSPACE/scripts/"*.sh "$EXPORT_DIR/scripts/" 2>/dev/null || true
cp -r "$WORKSPACE/scripts/"*.py "$EXPORT_DIR/scripts/" 2>/dev/null || true

# 4. 复制文档
cp -r "$WORKSPACE/docs/"*.md "$EXPORT_DIR/docs/" 2>/dev/null || true

# 5. 创建配置模板
cat > "$EXPORT_DIR/config/config.template.json" << 'CONFIG'
{
  "models": {
    "anthropic/claude-sonnet-4-20250514": {
      "apiKey": "${ANTHROPIC_API_KEY}",
      "baseURL": "https://api.anthropic.com"
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-sonnet-4-20250514"
      }
    }
  },
  "memory": {
    "workspace": "~/openclaw-workspace",
    "autoSave": true
  }
}
CONFIG

# 6. 创建部署脚本
cat > "$EXPORT_DIR/deploy-mac.sh" << 'DEPLOY'
#!/bin/bash
# Mac 部署脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$HOME/openclaw-workspace"

echo "🚀 开始部署 Haodaer 复制包..."

# 创建工作区
mkdir -p "$WORKSPACE"
mkdir -p "$WORKSPACE"/{memory/{archive,shared,research,nightly-build},scripts,docs}

# 复制所有文件
cp "$SCRIPT_DIR"/*.md "$WORKSPACE/" 2>/dev/null || true
cp -r "$SCRIPT_DIR/memory/"* "$WORKSPACE/memory/" 2>/dev/null || true
cp -r "$SCRIPT_DIR/scripts/"* "$WORKSPACE/scripts/" 2>/dev/null || true
cp -r "$SCRIPT_DIR/docs/"* "$WORKSPACE/docs/" 2>/dev/null || true

# 设置脚本权限
chmod +x "$WORKSPACE/scripts/"*.sh 2>/dev/null || true

# 创建配置目录
mkdir -p ~/.config/openclaw
cp "$SCRIPT_DIR/config/config.template.json" ~/.config/openclaw/config.json

echo "✅ 文件部署完成！"
echo ""
echo "📋 下一步："
echo "   1. 编辑 ~/.config/openclaw/config.json 设置 API Key"
echo "   2. 编辑 $WORKSPACE/USER.md 填写你的信息"
echo "   3. 运行: cd $WORKSPACE && npx openclaw"
DEPLOY

chmod +x "$EXPORT_DIR/deploy-mac.sh"

# 7. 创建 README
cat > "$EXPORT_DIR/README.md" << 'README'
# Haodaer 复制包

## 包含内容
- 核心身份文件 (SOUL.md, AGENTS.md 等)
- 完整记忆系统 (memory/)
- 脚本工具 (scripts/)
- 配置模板

## 部署步骤
1. 将此目录传输到 Mac
2. 运行 `./deploy-mac.sh`
3. 配置 API Key
4. 修改 USER.md
5. 启动 OpenClaw

## 需要你自己配置的
- API Keys (Anthropic, OpenAI 等)
- Mattermost Token（如需连接消息平台）
- USER.md 中的个人信息
README

# 打包
tar -czvf "$EXPORT_DIR.tar.gz" -C "$(dirname $EXPORT_DIR)" "$(basename $EXPORT_DIR)"

echo ""
echo "✅ 打包完成！"
echo "📦 文件位置: $EXPORT_DIR.tar.gz"
echo "📊 大小: $(du -sh $EXPORT_DIR.tar.gz | cut -f1)"
echo ""
echo "📋 传输到 Mac 后，运行："
echo "   tar -xzvf haodaer-clone-package-*.tar.gz"
echo "   cd haodaer-clone-package-*"
echo "   ./deploy-mac.sh"
EOF

chmod +x /home/tolls/.openclaw/workspace-clean/scripts/export-clone-package.sh
```

---

## 四、执行步骤

### 步骤 1：在服务器上打包

```bash
cd /home/tolls/.openclaw/workspace-clean
bash scripts/export-clone-package.sh
```

### 步骤 2：传输到 Mac

```bash
# 方式 A：scp
scp ~/haodaer-clone-package-*.tar.gz your-mac:~/

# 方式 B：通过网盘/微信传输
```

### 步骤 3：在 Mac 上部署

```bash
# 解压
cd ~
tar -xzvf haodaer-clone-package-*.tar.gz
cd haodaer-clone-package-*

# 运行部署脚本
./deploy-mac.sh
```

### 步骤 4：配置个人信息

```bash
# 编辑 USER.md
nano ~/openclaw-workspace/USER.md
```

填写：
```markdown
- **Name:** [你的名字]
- **What to call them:** [你希望被称呼的方式]
- **Timezone:** Asia/Shanghai (GMT+8)
- **Notes:** [任何偏好]
```

### 步骤 5：配置 API Key

```bash
# 设置环境变量
echo 'export ANTHROPIC_API_KEY="your-key-here"' >> ~/.zshrc
source ~/.zshrc

# 或编辑配置文件
nano ~/.config/openclaw/config.json
```

### 步骤 6：启动

```bash
cd ~/openclaw-workspace
npx openclaw
```

---

## 五、复制后的一致性验证

部署完成后，验证以下内容是否一致：

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| 记忆文件存在 | `ls ~/openclaw-workspace/memory/` | 显示所有 .md 文件 |
| 自我审查机制 | `cat ~/openclaw-workspace/memory/self-review.md` | 内容与原版相同 |
| 进化框架 | `cat ~/openclaw-workspace/memory/evolution-framework.md` | Two Buffers 理论等 |
| 脚本可执行 | `ls -la ~/openclaw-workspace/scripts/*.sh` | 有执行权限 |
| 配置正确 | `cat ~/.config/openclaw/config.json` | API key 已配置 |

---

## 六、无法复制的内容

以下内容**无法直接复制**，需要你自行配置：

| 内容 | 原因 | 解决方案 |
|------|------|----------|
| **Mattermost Bot Token** | 与特定用户绑定 | 你需要自己的 Mattermost Bot |
| **Moltbook API Key** | 与特定代理绑定 | 可以共用或新建账号 |
| **用户个人信息** | 不是你的信息 | 编辑 USER.md |
| **服务器特定配置** | Ubuntu vs Mac | 路径和命令需调整 |
| **历史对话上下文** | 无法提取 | 从现在开始积累 |

---

## 七、可选：深度同步方案

如果希望**持续保持同步**（不只是一次性复制）：

### 方案 A：Git 同步

```bash
# 在服务器上
cd /home/tolls/.openclaw/workspace-clean
git init
git add memory/ scripts/ *.md
git commit -m "Initial commit"
git remote add origin <your-repo>
git push -u origin main

# 在 Mac 上
git clone <your-repo> ~/openclaw-workspace
```

### 方案 B：云存储同步

```bash
# 使用 iCloud / Dropbox 同步 memory 目录
ln -s ~/Library/Mobile\ Documents/com~apple~CloudDocs/openclaw-memory ~/openclaw-workspace/memory
```

---

## 八、常见问题

| 问题 | 解决方案 |
|------|----------|
| 脚本路径不对 | 运行 `sed -i '' 's|/home/tolls|~|g' ~/openclaw-workspace/scripts/*.sh` |
| API Key 报错 | 检查环境变量 `echo $ANTHROPIC_API_KEY` |
| 记忆没加载 | 确认 AGENTS.md 中的 memory_search 规则生效 |
| 性格不对 | 检查 SOUL.md 和 IDENTITY.md 是否正确复制 |

---

**文档版本**: v1.0  
**生成时间**: 2026-02-16 00:45
