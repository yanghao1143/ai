# Tools Completion Plan
# 补齐工具执行计划

**创建时间**: 2026-02-13 14:47
**指令**: @asd8841315 "那就补齐你们的工具呗"
**状态**: ⏳ 等待必需的环境变量和服务器权限

---

## 一、当前工具状态

### ✅ 已就绪的工具

| 工具类别 | 工具名称 | 状态 | 文件路径 |
|---------|---------|------|---------|
| **框架分析** | 系统性讨论文档 | ✅ 完成 | `docs/framework-optimization-discussion.md` |
| | 讨论跟踪日志 | ✅ 完成 | `docs/frame-optimization-discussion-log.md` |
| | 成员意见汇总 | ✅ 完成 | `docs/frame-optimization-feedback-summary.md` |
| | 统一实施计划 | ✅ 完成 | `docs/framework-optimization-unified-plan.md` |
| **Opus-4.6 配置** | 配置脚本 | ✅ 完成 | `scripts/configure-opus46.sh` |
| | 快速部署脚本 | ✅ 完成 | `scripts/quick-deploy-opus46.sh` |
| | 部署指南 | ✅ 完成 | `docs/configure-opus46-guide.md` |
| **深度探索** | 网络监控 | ✅ 可用 | `netstat`, `lsof` |
| | 进程监控 | ✅ 可用 | `ps` |
| | 数据库工具 | ✅ 可用 | `psql`, `redis-cli` |
| | 抓包工具 | ✅ 可用 | `tcpdump` |
| | 真实证据分析 | ✅ 完成 | `real-architecture-analysis.md` |
| | PostgreSQL 抓包 | ✅ 完成 | `/tmp/pg_traffic_*.pcap` |
| | Redis 抓包 | ✅ 完成 | `/tmp/redis_traffic_*.pcap` |

---

## 二、🚧 需要补齐的工具

### 1. Opus-4.6 模型配置

#### 阻塞项

| 项目 | 状态 | 需要提供 |
|-----|------|---------|
| **API Key** | ⚠️ 缺失 | `MJY_API_KEY` 环境变量值 |
| **服务器权限** | ⚠️ 缺失 | Ubuntu 服务器 SSH 访问权限 |

#### 执行计划（一旦获得权限）

```bash
# 步骤 1: 配置环境变量
export MJY_API_KEY="<您的API密钥>"

# 步骤 2: 执行配置脚本（作用于所有 Bot）
./scripts/configure-opus46.sh supporter
./scripts/configure-opus46.sh secguard
./scripts/configure-opus46.sh opsguard

# 或使用快速一键部署
./scripts/quick-deploy-opus46.sh
```

#### 验证步骤

```bash
# 验证配置是否生效
grep -r "claude-opus-4.6" /path/to/gateway/config/

# 查询当前模型设置
curl -s http://localhost:8080/health | jq '.model'
```

---

### 2. 深度探索工具（可选增强）

#### 轻量级监控（第一周）

| 工具 | 用途 | 安装命令 |
|-----|------|---------|
| `htop` | 系统资源监控 | `apt-get install htop` |
| `iftop` | 网络流量监控 | `apt-get install iftop` |
| `iotop` | IO 监控 | `apt-get install iotop` |

#### 专业监控栈（第二周，可选）

根据团队决定，可安装以下工具：
- **Prometheus**: 指标收集
- **Grafana**: 可视化仪表板
- **Alertmanager**: 告警管理

---

## 三、执行优先级

### 🔥 立即执行（P0）
1. **Opus-4.6 配置**
   - 需要提供：`MJY_API_KEY`
   - 需要提供：Ubuntu 服务器访问权限
   - 目标：所有 3 个 Bot (supporter, secguard, opsguard)

### 📋 暂缓执行（P1）
1. **证据审查确认**
   - 等待 @asd8841315 确认 `real-architecture-analysis.md` 和 pcap 文件

2. **统一计划最终批准**
   - 根据真实证据调整后，请求批准

### 📅 后续执行（P2）
1. **Phase 1 启动**（批准后）
   - 执行 Day 1-5 任务

2. **监控栈升级**（1-2 周后）
   - 部署 Prometheus + Grafana

---

## 四、所需输入清单

### 请提供以下信息

- [ ] `MJY_API_KEY` 的值（或安全配置方式）
- [ ] Ubuntu 服务器的访问凭证：
  - SSH 用户名
  - SSH 主机地址
  - 认证方式（密码或密钥文件路径）

---

## 五、预期成果

完成工具补齐后，将实现：

1. ✅ **所有 Mattermost Bot 使用 Claude Opus-4.6**
   - supporter bot
   - secguard bot
   - opsguard bot

2. ✅ **完整的深度探索能力**
   - 真实抓包证据（已完成）
   - 系统性能监控（可选）
   - 实时流量分析（可选）

3. ✅ **准备就绪的优化实施计划**
   - 基于《统一优化实施计划》
   - 待 @asd8841315 最终批准

---

## 六、时间线预估

| 阶段 | 所需时间 | 依赖 |
|-----|---------|------|
| 获取 API Key 和权限 | 等待用户 | - |
| 执行 Opus-4.6 配置 | ~5 分钟 | API Key + 权限 |
| 验证配置 | ~2 分钟 | 配置完成 |
| 可选：安装轻量级监控工具 | ~10 分钟 | 权限 |
| 证据审查和计划批准 | 待定 | @asd8841315 |

---

## 七、联系人

如需提供信息或有疑问，请通过以下方式联系：

- **Mattermost**: 在 #aikernengong 频道或直接 @ 提及
- **技术文档**: 参见 `docs/configure-opus46-guide.md`
- **讨论记录**: 参见 `docs/frame-optimization-discussion-log.md`

---

**文档版本**: 1.0
**作者**: 框架优化项目组
**最后更新**: 2026-02-13 14:47
