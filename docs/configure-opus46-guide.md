# 为Mattermost Bot配置Opus-4.6模型

## 📋 概述

本文档说明如何为supporter、secguard、opsguard三个Mattermost Bot配置claude-opus-4-6模型。

**API服务信息:**
- **Base URL**: `http://107.172.187.231:8317`
- **主模型**: `claude-opus-4-6`
- **备用模型**: `claude-opus-4-5-20251101`

---

## 🚀 快速部署（在Ubuntu服务器上执行）

### 方式一：使用自动化脚本

1. **准备API Key**
   ```bash
   # 请将以下变量设置为实际的API Key
   export MJY_API_KEY="your-actual-api-key-here"
   ```

2. **下载并运行配置脚本**
   ```bash
   # 从工作区复制脚本到服务器
   scp scripts/configure-opus46.sh ubuntu@your-server:/tmp/

   # SSH登录服务器
   ssh ubuntu@your-server

   # 运行脚本，替换API Key
   sed -i "s/mjy-key-placeholder/$MJY_API_KEY/g" /tmp/configure-opus46.sh
   chmod +x /tmp/configure-opus46.sh
   sudo -u ubuntu /tmp/configure-opus46.sh
   ```

3. **重启Bot**
   ```bash
   sudo docker restart openclaw-supporter
   sudo docker restart openclaw-secguard
   sudo docker restart openclaw-opsguard
   ```

4. **验证配置**
   ```bash
   # 查看Bot日志确认使用了opus-4-6
   sudo docker logs --tail 50 openclaw-supporter | grep -E "opus|model"
   ```

---

### 方式二：手动配置

如果需要手动配置每个bot，可以按照以下步骤：

#### 1. 配置supporter

```bash
# 编辑配置
vim /home/ubuntu/.openclaw-supporter/openclaw.json
```

添加或更新以下配置：

```json
{
  "models": {
    "providers": {
      "mjy": {
        "baseUrl": "http://107.172.187.231:8317",
        "apiKey": "your-actual-api-key",
        "api": "anthropic",
        "models": [
          {
            "id": "claude-opus-4-6",
            "name": "Claude Opus 4.6 (mjy)",
            "reasoning": true,
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
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "mjy/claude-opus-4-6",
        "fallbacks": []
      }
    }
  }
}
```

#### 2. 重启Bot

```bash
sudo docker restart openclaw-supporter
```

#### 3. 重复步骤1-2对secguard和opsguard

---

## 🔍 配置说明

### 模型配置结构

```json
{
  "id": "claude-opus-4-6",           // 模型ID（短名，不带provider前缀）
  "name": "Claude Opus 4.6 (mjy)",  // 显示名称
  "reasoning": true,                // 是否支持推理
  "input": ["text"],                // 支持的输入类型
  "contextWindow": 200000,          // 上下文窗口
  "maxTokens": 8192                 // 最大输出token数
}
```

### Provider配置

```json
{
  "baseUrl": "http://107.172.187.231:8317",  // API端点
  "apiKey": "your-api-key",                 // API密钥
  "api": "anthropic"                        // API协议类型
}
```

### Agent配置

```json
{
  "primary": "mjy/claude-opus-4-6",  // 主模型: provider/model
  "fallbacks": []                    // 备用模型列表
}
```

---

## ✅ 验证部署

### 1. 检查Bot状态

```bash
# 查看所有OpenClaw容器状态
sudo docker ps | grep openclaw

# 预期输出:
# CONTAINER ID   IMAGE                            STATUS
# abc123        openclaw-supporter               Up X hours
# def456        openclaw-secguard                Up X hours
# ghi789        openclaw-opsguard                Up X hours
```

### 2. 查看Bot日志

```bash
# 查看supporter日志
sudo docker logs --tail 100 openclaw-supporter

# 查找模型相关日志
sudo docker logs openclaw-supporter 2>&1 | grep -E "model|provider|opus"
```

### 3. 测试Bot响应

在Mattermost中:
1. 进入对应的部门频道
2. @supporter 测试消息
3. 观察响应质量和速度

---

## 🐛 故障排查

### 问题1: Bot启动失败

**症状**: `docker restart` 后容器退出

**排查**:
```bash
# 查看详细日志
sudo docker logs openclaw-supporter

# 检查配置文件语法
python3 -m json.tool /home/ubuntu/.openclaw-supporter/openclaw.json
```

### 问题2: 模型调用失败

**症状**: Bot响应时报错 "No API key found" 或 "model not found"

**排查**:
1. 检查API Key是否正确设置
   ```bash
   grep -r "apiKey" /home/ubuntu/.openclaw-*/openclaw.json
   ```

2. 检查模型名是否正确（不带provider前缀）
   - 正确: `claude-opus-4-6`
   - 错误: `mjy/claude-opus-4-6`

3. 检查API服务是否可达
   ```bash
   curl -I http://107.172.187.231:8317
   ```

### 问题3: 容器配置未生效

**症状**: 配置已修改但Bot仍使用旧模型

**解决**:
```bash
 # 强制重新挂载配置卷
 sudo docker compose down
 sudo docker compose up -d

# 或者删除容器并重建
 sudo docker stop openclaw-supporter
 sudo docker rm openclaw-supporter
 # Docker Compose会自动重建
```

---

## 📊 配置文件对比

### 配置前（使用默认模型）

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "ollama/qwen2.5-coder:7b"
      }
    }
  }
}
```

### 配置后（使用Opus-4.6）

```json
{
  "models": {
    "providers": {
      "mjy": {
        "baseUrl": "http://107.172.187.231:8317",
        "apiKey": "sk-xxx",
        "api": "anthropic",
        "models": [...]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "mjy/claude-opus-4-6",
        "fallbacks": ["mjy/claude-opus-4-5-20251101"]
      }
    }
  }
}
```

---

## 💡 最佳实践

1. **备份配置**: 修改前 always backup
   ```bash
   cp openclaw.json openclaw.json.backup.$(date +%Y%m%d)
   ```

2. **逐步部署**: 先部署一个bot，验证后再批量部署
   ```bash
   # 测试流程
   1. 配置supporter → 2. 重启 → 3. 测试 → 4. 推广到其他bot
   ```

3. **监控日志**: 部署后持续观察24小时

4. **回滚方案**: 保留备份以备回滚
   ```bash
   # 回滚到备份
   cp openclaw.json.backup.20260213 openclaw.json
   sudo docker restart openclaw-supporter
   ```

---

## 📝 配置清单

- [ ] 获取并验证API Key
- [ ] 连接到Ubuntu服务器
- [ ] 运行配置脚本或手动配置
- [ ] 重启三个bot (supporter, secguard, opsguard)
- [ ] 验证Bot正常运行
- [ ] 测试Bot响应（Mattermost消息）
- [ ] 检查日志确认使用opus-4-6
- [ ] 监控24小时稳定性

---

**文档版本**: v1.0
**更新时间**: 2026-02-13
**维护者**: HaoDaEr (好大儿)
