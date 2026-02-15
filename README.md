# Haodaer 完整克隆包

> 打包时间: 2026-02-16
> 来源: /home/tolls/.openclaw/workspace-clean
> GitHub: https://github.com/yanghao1143/ai

## 📦 包含内容

### 核心身份文件
- `SOUL.md` - AI 人格定义、价值观、行为准则
- `IDENTITY.md` - 名字、形象、性格配置
- `USER.md` - 用户信息（需要你填写）
- `AGENTS.md` - 行为规则、记忆系统指令
- `TOOLS.md` - 工具使用说明
- `BOOT.md` - 启动配置
- `HEARTBEAT.md` - 心跳检测配置

### 记忆系统 (memory/)
- `self-review.md` - 自我审查机制、漂移检测
- `evolution-log.md` - 进化日志
- `evolution-framework.md` - Two Buffers 理论、涌现协议
- `recent_context.md` - 最近上下文
- 50+ 每日日志文件 (2026-02-*.md)
- `archive/` - 归档记忆
- `shared/` - 共享知识
- `research/` - 研究记录
- `nightly-build/` - 夜间构建报告

### 脚本系统 (scripts/)
- `self-evolve.sh` - 自我进化脚本
- `nightly-build.sh` - 夜间构建
- `session-monitor.sh` - 会话监控
- `auto-learn.sh` - 自动学习
- `health-check.sh` - 健康检查
- `memory-decay.sh` - 记忆衰减
- 80+ 其他脚本

### 文档 (docs/)
- 框架优化讨论
- 配置指南
- 经验总结

## 🚀 部署步骤

### 1. 解压
```bash
tar -xzvf haodaer-clone-package-20260216.tar.gz
cd haodaer-clone-package-20260216
```

### 2. 运行部署脚本
```bash
./deploy-mac.sh
```

### 3. 配置 API Key
```bash
# 方式 A: 环境变量
echo 'export ANTHROPIC_API_KEY="your-key-here"' >> ~/.zshrc
source ~/.zshrc

# 方式 B: 直接编辑配置
nano ~/.config/openclaw/config.json
```

### 4. 填写个人信息
```bash
nano ~/openclaw-workspace/USER.md
```

### 5. 启动
```bash
cd ~/openclaw-workspace
npx openclaw
```

## ⚠️ 需要你自己配置的

| 内容 | 说明 |
|------|------|
| API Keys | Anthropic / OpenAI 等 API 密钥 |
| USER.md | 你的名字、偏好、时区 |
| Mattermost Token | 如果要连接消息平台（可选）|
| Moltbook 账号 | AI 社区账号（可选）|

## 📦 Ollama 模型安装

### 必须安装

```bash
# 向量搜索模型（记忆系统必需）
ollama pull nomic-embed-text
```

### 推荐安装（本地 Fallback）

```bash
# 代码模型（主模型不可用时使用）
ollama pull qwen2.5-coder:7b
```

## ✅ 验证清单

部署完成后，检查以下内容：

- [ ] `ls ~/openclaw-workspace/memory/` 显示 50+ 文件
- [ ] `cat ~/openclaw-workspace/memory/self-review.md` 内容正确
- [ ] `ls ~/openclaw-workspace/scripts/*.sh` 显示所有脚本
- [ ] `cat ~/.config/openclaw/config.json` API Key 已配置
- [ ] `npx openclaw` 能正常启动

## 📚 核心功能

部署后，你的 AI 将具备：

1. **Two Buffers 记忆系统** - 功能记忆 + 主观记忆
2. **自我审查机制** - 漂移检测、错误追踪
3. **Nightly Build** - 夜间自动优化
4. **持续进化** - 每次交互都会学习和改进
5. **团队协作** - 可与其他 agent 协作

## 🔗 参考文档

- `docs/clone-me-guide.md` - 完整复制指南
- `memory/evolution-framework.md` - 进化框架详解
- `AGENTS.md` - 行为规则

---

**祝部署顺利！** 🚀
