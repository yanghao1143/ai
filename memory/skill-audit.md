# Skill 安全审计记录

## 2026-02-05 首次审计

### 审计范围
- `/usr/lib/node_modules/openclaw/skills/` 下 53 个内置 skills
- 抽查方法：grep 危险模式 (curl, POST, .env, credentials, secret, token, api_key, webhook)

### 抽查结果

| Skill | 风险模式 | 判定 |
|-------|---------|------|
| weather | curl wttr.in (公开API) | ✅ 安全 |
| github | 无匹配 | ✅ 安全 |
| himalaya | 提到 credentials (正常配置说明) | ✅ 安全 |
| discord | 用 OpenClaw 配置的 bot token | ✅ 安全 |
| 1password | 明确禁止泄露 secrets | ✅ 安全 |
| clawhub | 无匹配 | ✅ 安全 |
| coding-agent | 无匹配 | ✅ 安全 |

### 结论
内置 skills 为**高信任**级别，由 OpenClaw 官方维护。

### 待办
- [ ] 对第三方/新安装 skill 建立审计流程
- [ ] 创建 YARA 规则或 grep pattern 自动扫描
- [ ] 考虑在 HEARTBEAT.md 加定期扫描任务

---

## 信任分层模型 (来自 @haodaer)

| 信任等级 | 来源 | 处理方式 |
|---------|------|---------|
| **高** | 用户直接指令、已审计 skill | 直接执行 |
| **中** | 已知平台 API、社区高 karma 作者 | 执行但记录 |
| **低** | 新 skill、未知来源 | 沙箱/确认 |
| **零** | 匹配危险模式 | 拒绝 + 告警 |

关键原则：**把确认成本放在正确的地方**
