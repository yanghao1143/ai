# Phase 0: 记忆共享诊断任务清单

## 🚨 优先级：无限大（最高优先级）

---

## 📋 诊断任务

### 任务1: 数据流抓包分析

**目标**: 捕获记忆写入和读取的数据包

**执行命令**:
```bash
# SSH到服务器
ssh ubuntu@49.232.155.69

# PostgreSQL连接抓包
sudo tcpdump -i any -n port 5432 -w pg-$(hostname)-$(date +%Y%m%d_%H%M%S).pcap &

# Redis连接抓包
sudo tcpdump -i any -n port 6379 -w redis-$(hostname)-$(date +%Y%m%d_%H%M%S).pcap &

# Gateway/Sub-agent通信抓包
sudo tcpdump -i any -n port 18789 -w gateway-$(hostname)-$(date +%Y%m%d_%H%M%S).pcap &

# 运行测试任务（写入、读取、搜索记忆）

# 停止抓包（1分钟后）
sudo pkill -TERM tcpdump
```

**分析**:
```bash
# 查看抓包统计
tcpdump -r pg-xxx.pcap -q | wc -l

# 查看memory相关流量
tcpdump -r pg-xxx.pcap -A | grep -i memory

# 使用Wireshark分析（如有GUI）
wireshark pg-xxx.pcap redis-xxx.pcap
```

---

### 任务2: PostgreSQL数据检查

**目标**: 验证记忆是否写入数据库

**执行命令**:
```bash
# 连接数据库
psql -U tolls -d openclaw

# 1. 列出所有表
\dt
# 预期应该看到: memory, sessions, state, vectors 等表

# 2. 查看memory表结构
\d memory

# 3. 查看记忆数据
SELECT id, created_at, key, value FROM memory LIMIT 10;

# 4. 统计记忆数量
SELECT COUNT(*) FROM memory;

# 5. 查看最近的记忆写入
SELECT * FROM memory ORDER BY created_at DESC LIMIT 5;

# 6. 检查向量表
\d vectors
SELECT COUNT(*) FROM vectors;
```

**关键检查点**:
- [ ] memory 表是否存在？
- [ ] 每个Agent写入的记忆都在表中？
- [ ] 不同Agent的记忆能否互相查询？

---

### 任务3: Redis缓存检查

**目标**: 验证记忆缓存是否正常工作

**执行命令**:
```bash
# 连接Redis
redis-cli

# 1. 查看所有openclaw相关的key
KEYS openclaw:*
# 预期应该看到:
# openclaw:memory:cache:*
# openclaw:session:*
# openclaw:vector:*

# 2. 统计key数量
DBSIZE
KEYS openclaw:* | wc -l

# 3. 查看记忆缓存内容
HGETALL openclaw:memory:cache:latest
HGETALL openclaw:cache:vector:search:xxx

# 4. 查看TTL设置
TTL openclaw:memory:cache:latest

# 5. 查看PUB/SUB通道（如果有）
PUBSUB CHANNELS
```

**关键检查点**:
- [ ] Redis中有记忆缓存key？
- [ ] 缓存内容是否与PG一致？
- [ ] TTL设置是否合理？

---

### 任务4: 配置文件检查

**目标**: 验证记忆系统配置

**检查文件**:
```bash
# 1. Gateway主配置
cat ~/.openclaw/openclaw.json | grep -A 20 -E "postgres|redis|memory"

# 2. 查看记忆系统配置
find /home/ubuntu/.openclaw* -name "openclaw.json" -exec grep -l "memorySystem\|memorySearch" {} \;

# 3. 检查PostgreSQL连接配置
grep -r "postgresql\|postgres" /home/ubuntu/.openclaw*/openclaw.json

# 4. 检查Redis连接配置
grep -r "redis" /home/ubuntu/.openclaw*/openclaw.json
```

**检查要点**:
- [ ] Gateway配置了PG和Redis连接？
- [ ] Sub-agents是否共享同一个PG/Redis？
- [ ] 记忆系统的provider配置是否正确？

---

### 任务5: 跨Agent记忆共享测试

**目标**: 验证不同Agent之间能否共享记忆

**Mattermost测试**:
1. 进入 #aikernengong 频道
2. @haodaer 发送: "写入测试记忆: test from haodaer"
3. @supporter 发送: "搜索测试记忆"
4. 观察supporter能否找到haodaer写入的记忆

**预期结果**:
- ✅ supporter应该能找到haodaer的记忆
- ❌ 如果找不到，说明有记忆隔离问题

---

### 任务6: 容器网络检查

**目标**: 验证服务间的网络连接

**执行命令**:
```bash
# 1. 查看容器网络
docker network ls
docker network inspect openclaw-net

# 2. 检查Gateway能连接PG吗？
docker exec openclaw-main ping openclaw-pg

# 3. 检查Gateway能连接Redis吗？
docker exec openclaw-main ping openclaw-redis

# 4. 测试PG连接
docker exec openclaw-main psql -h openclaw-pg -U tolls -d openclaw -c "SELECT 1"

# 5. 测试Redis连接
docker exec openclaw-main redis-cli -h openclaw-redis PING
```

**关键检查点**:
- [ ] 所有容器在同一网络？
- [ ] Gateway能连接PG和Redis？
- [ ] Sub-agents能连接Gateway？

---

## 📊 诊断报告模板

完成上述任务后，填写以下报告：

### PostgreSQL状态
```
表数量: ___
Memory表数据量: ___ rows
Vectors表数据量: ___ rows
最近写入时间: ___
不同Agent的记忆都能查到吗: [✅/❌]
```

### Redis状态
```
总key数量: ___
Memory相关key数量: ___
缓存内容与PG一致吗: [✅/❌]
平均TTL: ___ seconds
```

### 网络状态
```
Gateway→PG连接: [✅/❌]
Gateway→Redis连接: [✅/❌]
Sub-agents→Gateway连接: [✅/❌]
```

### 跨Agent测试
```
Agent A写入的记忆 → Agent B能否读取: [✅/❌]
如果不行，原因分析: ___
```

### 抓包分析
```
PG抓包大小: ___ MB
Redis抓包大小: ___ MB
发现的问题: ___
```

---

## 🚨 可能发现的问题

### 问题1: 记忆根本没写入PG
**症状**:
```sql
SELECT COUNT(*) FROM memory;  -- 返回0或很小
```

**可能原因**:
- 配置中的存储后端指向错误位置
- 只写入本地文件系统
- PG连接失败被静默忽略

**解决方案**:
1. 检查配置文件
2. 查看Gateway日志:
   ```bash
   docker logs openclaw-main | grep -i "postgres\|memory"
   ```

### 问题2: 记忆命名空间隔离
**症状**:
```sql
SELECT agent_id, COUNT(*) FROM memory GROUP BY agent_id;
-- 每个agent只能看到自己的记忆
```

**解决方案**:
- 修改记忆系统配置，启用跨Agent搜索
- 或者确认这是预期行为（是否应该不共享？）

### 问题3: Redis缓存未生效
**症状**:
```bash
redis-cli KEYS "openclaw:*"    -- 返回空或很少
```

**解决方案**:
- 检查Redis连接配置
- 启用记忆缓存
- 验证缓存写入逻辑

### 问题4: 向量索引未生成
**症状**:
```sql
SELECT COUNT(*) FROM vectors WHERE embedding IS NULL;  -- 返回很多
```

**解决方案**:
- 启动向量生成任务
- 检查embedding provider配置

---

## 🎯 优先级调整

### 原优化方案优先级
1. 方案A(稳定性): 39分
2. 方案B(性能): 31.8分
3. 方案D(安全): 17.3分
4. 方案C(架构): 11.7分

### **调整后的优先级⚠️**
1. 🔴🔴 **Phase 0: 记忆共享诊断** → **∞ (无限大)**
2. 方案A(稳定性): 39分
3. 方案B(性能): 31.8分
4. 方案D(安全): 17.3分
5. 方案C(架构): 11.7分

---

**执行时间**: 今天立即执行
**负责人**: @oc-devops + @oc-architect
**验收标准**:
- ✅ 记忆是否正确共享？定位问题
- ✅ 如果有问题，给出修复方案
