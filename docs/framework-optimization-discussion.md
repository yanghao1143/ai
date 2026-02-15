# OpenClaw 框架优化讨论方案

## 📅 讨论时间
2026-02-13

## 🎯 讨论目标
系统性分析当前框架的痛点、瓶颈，给出统一的优化建议

---

## 一、当前技术栈梳理

### 1.1 核心架构组件

| 组件 | 技术 | 配置 | 说明 |
|------|------|------|------|
| **OpenClaw Gateway** | ghcr.io/openclaw/openclaw:latest | :18789 | 单点网关，消息路由、会话管理 |
| **Sub-Agents** | 同基础镜像 | sub1-sub7 | 7个并行worker，共享数据卷 |
| **PostgreSQL** | 持久化卷 | openclaw-pg | 主要数据库，存储会话/状态 |
| **Redis** | 持久化卷 | openclaw-redis | 上下文缓存、临时状态 |
| **Mattermost Bot** | 多实例 | 不同端口 | supporter(18830), secguard(18791), opsguard(18820) |

### 1.2 部署模式
```
┌─────────────────────────────────────────┐
│         Docker Compose Swarm            │
├─────────────────────────────────────────┤
│  ┌──────────┐    ┌──────────────────┐  │
│  │  Main    │◄──►│   Sub Agents     │  │
│  │ Gateway  │    │  (sub1-sub7)     │  │
│  └──────────┘    └──────────────────┘  │
│       │                │               │
├───────┴────────────────┴───────────────┤
│       Shared Volumes                   │
│  ┌─────────┐  ┌───────┐  ┌─────────┐  │
│  │workspace│  │   PG  │  │  Redis  │  │
│  └─────────┘  └───────┘  └─────────┘  │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Mattermost     │
│  (协作平台)     │
└─────────────────┘
```

### 1.3 记忆与协作系统
- **Memory System**: MEMORY.md + daily logs (YYYY-MM-DD.md) + vector_search
- **Collaboration API**: http://127.0.0.1:18900 (13人开发团队协作)
- **Self-Evolution**: evolution-log.md + 错误追踪 + 记忆衰减机制
- **Health Checks**: agent-health.sh (心跳监控)

---

## 二、已知问题与痛点分级

### 🔴 P0 - 紧急痛点

#### P0-1: 单点故障风险 (SPOF)
**问题**：Gateway作为单点，一旦down掉，所有sub-agent和Bot全部瘫痪
**影响**：系统不可用
**根因**：没有HA方案
**复现方式**：docker stop openclaw-main

#### P0-2: 上下文溢出导致400错误
**问题**：大输出直接塞上下文导致 400 "Improperly formed request"
**影响**：会话损坏，需清理重启
**复现频率**：多次 (根据memory/incidents.md)
**当前缓解**：手动 > /tmp/xxx.txt 再 read

#### P0-3: Agent响应不可靠
**问题**：进程online但实际不响应消息（auth-profiles未对齐 + 403代理拦截）
**影响**：90秒规则触发，用户体验差
**复现频率**：2026-02-09发生
**根因**：provider鉴权配置不一致

### 🟡 P1 - 重要问题

#### P1-1: 响应延迟
**问题**：复杂任务响应接近90秒上限
**影响**：用户体验、任务超时
**瓶颈**：LLM推理速度 + 网络延迟

#### P1-2: 记忆文件增长
**问题**：daily memory可达96KB+，无限增长
**影响**：搜索性能、上下文加载
**当前方案**：memory-decay设计（未实施）

#### P1-3: 配置冗余
**问题**：多套配置文件共存，维护困难
**影响**：配置漂移、部署不一致
**示例**：~/.openclaw-bots/ vs ~/.openclaw-xxx/

### 🟢 P2 - 优化建议

#### P2-1: 缺乏监控告警
**问题**：没有统一监控面板，故障发现滞后
**影响**：MTTR长

#### P2-2: 审计链路不足
**问题**：缺乏完整的操作审计日志
**影响**：问题追溯困难

#### P2-3: 跨会话记忆不一致
**问题**：记忆同步和上下文保持困难
**影响**：重复劳动、信息孤岛

---

## 三、优化提案

### 方案A：稳定性优化（立即执行）

#### 3A-1: Gateway高可用（HA）
**方案1: Active-Active模式**
```yaml
services:
  gateway1:
    image: ghcr.io/openclaw/openclaw:latest
    ports: ["18789:18789"]
    environment:
      - GATEWAY_ID=gateway1
      - PEER_GATEWAYS=gateway2:18790

  gateway2:
    image: ghcr.io/openclaw/openclaw:latest
    ports: ["18790:18790"]
    environment:
      - GATEWAY_ID=gateway2
      - PEER_GATEWAYS=gateway1:18789

  nginx-gateway:
    image: nginx:alpine
    ports: ["8080:80"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
```
- 通过负载均衡分发请求
- 共享PostgreSQL/Redis卷实现状态同步

**方案2: Keepalived + VIP**（更轻量）
```bash
# keepalived.conf
vrrp_script check_gateway {
    script "/usr/bin/docker ps | grep openclaw-main"
    interval 2
}

vrrp_instance VI_1 {
    virtual_router_id 51
    priority 100
    virtual_ipaddress {
        192.168.1.100
    }
}
```

**推荐**: 方案1 (Active-Active) - 更好的资源利用

#### 3A-2: 上下文保护机制
**解决方案**：
1. **自动检测大输出**
   - 修改exec工具，自动检测输出大小 > 50KB
   - 自动重定向到临时文件

2. **智能压缩上下文**
   - 实现context-compressor.sh的自动触发
   - 保留近期上下文，压缩早期历史

3. **分块读取策略**
   - 大文件分页读取（offset/limit）
   - 只读取关键部分

**代码示例**：
```bash
# scripts/protected-exec.sh
smart_exec() {
    local cmd="$1"
    local output_file="/tmp/exec-$$-$RANDOM.txt"

    # 评估命令是否可能产生大输出
    if [[ "$cmd" =~ ^(cat|grep|find|ls) ]]; then
        eval "$cmd" > "$output_file"
        echo "📄 Output saved to: $output_file"
        echo "📊 Size: $(wc -c < "$output_file") bytes"
    else
        eval "$cmd"
    fi
}
```

#### 3A-3: Agent健康检查增强
**解决方案**：
1. **端到端健康检查**
   - 不仅检查进程是否online
   - 发送测试消息验证响应能力

2. **自动恢复机制**
   - 检测到连续3次无响应 → 自动重启
   - 记录失败日志到 incidents.md

3. **Auth配置校验**
   - 启动前校阅auth-profiles与实际provider
   - 提前发现配置不一致

**代码示例**：
```bash
# scripts/enhanced-health-check.sh
check_agent_heartbeat() {
    local agent_id="$1"
    local port="$2"

    # 1. 检查进程
    if ! docker ps | grep -q "openclaw-$agent_id"; then
        log_error "Process not running: $agent_id"
        return 1
    fi

    # 2. 发送测试消息
    local test_msg='{"type":"ping","recipient":"'$agent_id'"}'
    local response=$(curl -s -X POST "http://127.0.0.1:$port/api/ping" -d "$test_msg")

    if [ $? -eq 0 ] && echo "$response" | grep -q "pong"; then
        log_info "✓ $agent_id: responsive (${port}ms)"
        return 0
    else
        log_error "✗ $agent_id: not responding"
        return 1
    fi
}
```

---

### 方案B：性能优化（短期）

#### 3B-1: 上下文缓存优化
**Prompt Caching策略**：
1. **分层缓存**
   - L1: Memory (子会话内，短期)
   - L2: Redis (跨会话，1小时TTL)
   - L3: PostgreSQL (持久化，长期)

2. **缓存命中率优化**
   - 提取稳定的prompt前缀
   - 缓存AGENTS.md、IDENTITY.md等常量

3. **成本优化**
   - 缓存读取成本为正常的10%
   - 目标：缓存命中率 > 70%

#### 3B-2: 并行执行优化
**现状**: 子agent有时串行执行
**优化**:
1. **任务分解与并行化**
   - 使用sessions_spawn并行启动多个子代理
   - 汇总结果

2. **负载均衡**
   - 动态分配任务到空闲的sub1-sub7
   - 避免某个sub过载

**代码示例**：
```python
# scripts/parallel_dispatch.py
import asyncio

async def parallel_dispatch(tasks):
    """并行分发任务到多个sub-agent"""
    async def execute_on_agent(agent_id, task):
        # 调用sessions_spawn
        result = await spawn_subagent(agent_id, task)
        return agent_id, result

    # 并行执行
    results = await asyncio.gather(*[
        execute_on_agent(f"sub{i%7+1}", task)
        for i, task in enumerate(tasks)
    ])

    return dict(results)
```

#### 3B-3: 记忆衰减机制实施
**实施计划**：
1. **部署memory-decay.sh到HEARTBEAT**
2. **设置触发规则**：
   - weekly: 压缩7天前的daily memory
   - monthly: 归档30天前的记录到archive/
   - yearly: 清理1年前的临时记录

3. **删除保护**：
   - 先移到 .trash/ 保留30天
   - 确认无用后永久删除

---

### 方案C：架构改进（中期）

#### 3C-1: 配置中心化
**问题**: 配置分散，难以维护
**方案**:
1. **统一配置仓库**
   ```
   config/
   ├── gateway/
   │   ├── main.yaml
   │   └── agents/
   ├── bots/
   │   ├── supporter.yaml
   │   ├── secguard.yaml
   │   └── opsguard.yaml
   └── templates/
       └── base.yaml
   ```

2. **配置验证工具**
   ```bash
   scripts/validate-config.sh
   - 检查必要字段
   - 验证auth-profiles一致性
   - 检测配置漂移
   ```

#### 3C-2: 可观测性增强
**实施监控系统**：
1. **指标收集**
   - API请求延迟
   - 会话成功率
   - Agent健康度
   - Token消耗

2. **告警规则**
   - Gateway down (P0)
   - 400/5xx 错误率 > 5% (P1)
   - 响应延迟 > 30s (P2)

3. **Dashboard**
   - 使用Grafana展示
   - 实时健康状态

---

### 方案D：安全加固（持续）

#### 3D-1: 敏感信息管理
**最佳实践**：
1. ** secrets管理**
   - 使用.env文件 + Docker secrets
   - 不在代码库中硬编码token
   - 使用Vault或类似工具（可选）

2. **敏感信息过滤**
   - 自动检测Git commits中的token
   - 使用git-secrets工具

3. **最小权限原则**
   - Agent权限隔离
   - exec安全白名单

#### 3D-2: 审计日志
**实施方案**：
1. **操作审计**
   - 记录所有exec调用
   - 记录config修改
   - 记录关键决策

2. **可追溯性**
   - 每个操作关联session ID
   - 提供审计查询接口

---

## 四、实施计划

### Phase 1: 紧急修复（本周）
- [ ] 3A-1: Gateway HA部署
- [ ] 3A-2: 上下文保护机制
- [ ] 3A-3: Agent健康检查增强
- [ ] 验证：故障模拟测试

### Phase 2: 性能优化（下周）
- [ ] 3B-1: 上下文缓存
- [ ] 3B-2: 并行执行优化
- [ ] 3B-3: 记忆衰减部署
- [ ] 验证：基准测试对比

### Phase 3: 架构改进（2周后）
- [ ] 3C-1: 配置中心化
- [ ] 3C-2: 监控系统
- [ ] 验证：可维护性提升

### Phase 4: 安全加固（持续）
- [ ] 3D-1: 敏感信息管理
- [ ] 3D-2: 审计日志
- [ ] 定期安全审计

---

## 五、风险评估

| 优化项 | 风险 | 可能性 | 影响 | 缓解措施 |
|--------|------|--------|------|----------|
| Gateway HA | 配置复杂度增加 | 中 | 低 | 详细文档 + 灰度发布 |
| 上下文保护 | 兼容性问题 | 低 | 中 | 保留兼容模式 |
| 健康检查 | 误杀健康实例 | 中 | 中 | 增加重试机制 |
| 监控系统 | 资源消耗 | 中 | 低 | 轻量化实现 |

---

## 六、待讨论问题

1. **Gateway HA方案选择**: Active-Active vs Keepalived？
2. **监控栈选择**: Prometheus+Grafana vs 轻量化方案？
3. **缓存策略**: 多大比例的上下文应该被缓存？
4. **并行度**: sub-agent最大并发数限制？
5. **成本控制**: Token消耗预算和告警阈值？

---

## 七、讨论记录

### 2026-02-13 12:56 - 初始提问
**发言人**: @asd8841315
**内容**: "带领所有人看看我们现在的框架哪里需要优化，进行讨论 并给出统一后的结果。"

**待补充**:
- 各位对以上方案的反馈
- 优先级排序
- 实施资源评估

---

**文档版本**: v1.0
**最后更新**: 2026-02-13 12:56
**维护者**: HaoDaEr (好大儿)
