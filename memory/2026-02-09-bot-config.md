# 2026-02-09 Bot 配置与技能部署

## 400 错误诊断

**根因**：工具参数使用错误
- `write` 只接受 `file_path`，不接受 `path`
- `read`/`edit` 两者都接受
- 错误参数导致 400 "Improperly formed request"，会话损坏

**修复**：删除损坏会话 + 重启

## Bot 技能部署（已完成）

| Bot | 技能 |
|-----|------|
| opsguard | healthcheck, senior-devops, server-health, systematic-debugging |
| secguard | healthcheck, security-auditor, security-sentinel, senior-secops |
| supporter | communication-skill, internal-comms |

技能安装路径：`~/.openclaw-{bot}/workspace/skills/skills/`

## 配置验证错误

Bot 启动失败原因：
- `Unrecognized keys: write, edit` — tools 下没有这些键
- `Unrecognized key: allowlist` — 应该用 `tools.exec.safeBins`

**正确的 exec 配置 schema**：
```json
{
  "tools": {
    "exec": {
      "host": "sandbox|gateway|node",
      "security": "deny|allowlist|full",
      "ask": "off|on-miss|always",
      "safeBins": ["ls", "cat", ...]
    }
  }
}
```

## 操作审批系统

使用 `tools.exec.ask: "always"` 实现每次执行前需要审批

## 待完成

1. 修复 bot 配置（移除无效键）
2. 重启 3 个 bot
3. 验证审批系统
4. Discourse 论坛管理（clawhub 无现成 skill，需自建或用 SSH）

## 服务器信息

- 云服务器：43.154.204.91 (ubuntu / asd8841315..)
- Bot 配置路径：`~/.openclaw-{opsguard,secguard,supporter}/`
- 论坛：chiclaude.com (Discourse Docker)
