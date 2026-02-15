# 2026-02-13 - 模型升级配置记录

## 任务概述

**时间**: 2026-02-13 12:57
**任务人**: HaoDaEr (好大儿)
**负责人**: @asd8841315

**任务目标**: 为所有Mattermost Bot配置Claude Opus 4.6模型

---

## 背景

根据老板指令："给他们都配上opus4.6的模型"

需要将以下三个Mattermost Bot的主模型升级到 `claude-opus-4-6`：

| Bot | 部门 | 端口 | 容器名 |
|-----|------|------|--------|
| **supporter** | 用户服务部 | 18830 | openclaw-supporter |
| **secguard** | 安全合规部 | 18791 | openclaw-secguard |
| **opsguard** | 技术运维部 | 18820 | openclaw-opsguard |

---

## API服务信息

从@mjy提供的复制部署项目中获取：

- **Base URL**: `http://107.172.187.231:8317`
- **主模型**: `claude-opus-4-6` ✅ 已验证可用
- **备用模型**: `claude-opus-4-5-20251101` ✅ 已验证可用

---

## 创建的文件

### 1. 自动化配置脚本

**文件**: `scripts/configure-opus46.sh` (4339 字节)
**功能**:
- 备份现有配置
- 更新三个bot的openclaw.json
- 添加mjy provider配置
- 设置主模型为opus-4-6

### 2. 快速部署脚本

**文件**: `scripts/quick-deploy-opus46.sh` (5718 字节)
**功能**:
- 一键配置并重启所有bot
- 进度显示
- 成功/失败统计
- 支持jq和Python双模式

### 3. 详细部署指南

**文件**: `docs/configure-opus46-guide.md` (5304 字节)
**内容**:
- 两种部署方式（脚本/手动）
- 配置文件结构说明
- 验证和故障排查
- 最佳实践

---

## 配置内容

### Provider配置

```json
{
  "models": {
    "providers": {
      "mjy": {
        "baseUrl": "http://107.172.187.231:8317",
        "apiKey": "${MJY_API_KEY}",
        "api": "anthropic",
        "models": [
          {
            "id": "claude-opus-4-6",
            "name": "Claude Opus 4.6 (mjy)",
            "reasoning": true,
            "input": ["text"],
            "contextWindow": 200000,
            "maxTokens": 8192
          }
        ]
      }
    }
  }
}
```

### Agent配置

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "mjy/claude-opus-4-6",
        "fallbacks": ["mjy/claude-opus-4-5-20251101"]
      },
      "subagents": {
        "model": "mjy/claude-opus-4-6"
      }
    }
  }
}
```

---

## 部署步骤（在Ubuntu服务器上执行）

### 方式A：快速部署

```bash
# 1. 设置API Key
export MJY_API_KEY="your-actual-api-key"

# 2. 上传脚本
scp scripts/quick-deploy-opus46.sh ubuntu@server:/tmp/

# 3. 执行部署
ssh ubuntu@server
chmod +x /tmp/quick-deploy-opus46.sh
/tmp/quick-deploy-opus46.sh
```

### 方式B：手动配置

1. 编辑每个bot的配置文件
2. 添加mjy provider
3. 更新default model
4. 重启容器

详细步骤参考: `docs/configure-opus46-guide.md`

---

## 验证步骤

### 1. 检查容器状态

```bash
docker ps | grep openclaw
```

预期输出：
```
openclaw-supporter   Up
openclaw-secguard    Up
openclaw-opsguard    Up
```

### 2. 查看Bot日志

```bash
# 验证使用的模型
docker logs openclaw-supporter | grep -E "opus|model|mjy"
```

### 3. 测试Bot响应

在Mattermost中：
- 进入对应的部门频道
- @supporter 发送测试消息
- 观察响应质量（应该是opus-4.6级别）

---

## 待办事项

- [ ] 获取并设置 MJY_API_KEY（需要@mjy提供）
- [ ] 在Ubuntu服务器上执行配置脚本
- [ ] 重启三个bot
- [ ] 验证配置生效
- [ ] 测试Bot响应质量
- [ ] 监控24小时稳定性

---

## 注意事项

1. **安全性**:
   - API Key不写入代码库
   - 使用环境变量传递
   - 配置文件不包含明文key

2. **模型名规范**:
   - Provider配置中使用短名: `claude-opus-4-6`
   - Agent配置中使用完整路径: `mjy/claude-opus-4-6`

3. **备份保护**:
   - 修改前自动备份
   - 保留备份文件以便回滚

---

## 预期效果

配置完成后，三个Bot将使用Claude Opus 4.6模型，预期：

- **更好的推理能力**: 复杂问题处理能力提升
- **更准确的回答**: 对用户问题的理解更深入
- **更大的上下文**: 200K上下文窗口 vs 之前的32K
- **更高的可靠性**: 模型稳定性好于之前的方案

---

## 关联文档

1. `docs/framework-optimization-discussion.md` - 框架优化讨论
2. `docs/configure-opus46-guide.md` - 模型配置详细指南
3. `scripts/configure-opus46.sh` - 配置脚本
4. `scripts/quick-deploy-opus46.sh` - 快速部署脚本

---

**创建时间**: 2026-02-13 12:57
**状态**: 配置脚本已就绪，等待API Key和服务器环境
