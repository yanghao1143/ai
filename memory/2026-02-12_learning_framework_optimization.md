# 学习框架优化方案

> 设计时间：2026-02-12 13:06
> 目标：解决子代理协作、进度追踪、成果记录的系统性问题

---

## 一、问题诊断

### 1.1 当前问题

| 问题 | 现象 | 影响 |
|------|------|------|
| 子代理输出不可见 | `sessions_history` 返回空数组 | 无法获取子代理学习成果 |
| 缺乏进度监控 | 启动后不知道子代理在做什么 | 用户无法了解任务进度 |
| 记忆更新延迟 | 依赖 boot check 触发 | 学习成果容易丢失 |
| 框架内部错误 | `TypeError: Cannot read properties of undefined` | 子代理任务失败 |

### 1.2 根因分析

```
OpenClaw 框架层
  └─ sessions_spawn 创建子会话
      └─ 子代理运行
          ├─ 输出写入 sessions/*.jsonl
          └─ ❌ 主会话无法直接读取
              └─ sessions_history 返回空的原因：
                - 跨 agent 隔离（不同 workspace）
                - JSONL 文件写入有延迟
                - 文件权限或路径问题
```

---

## 二、优化架构设计

### 2.1 整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        主控制器                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ 任务调度器    │  │ 进度监控器    │  │ 成果收集器    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
   ┌──────────┐      ┌─────────────┐      ┌─────────────┐
   │ 学习计划  │      │ 状态追踪表   │      │ 记忆写入器   │
   │ 生成器    │      │ (JSON)      │      │             │
   └──────────┘      └─────────────┘      └─────────────┘
```

### 2.2 核心组件

#### 2.2.1 任务调度器 (Task Scheduler)

```typescript
interface Task {
  id: string;
  type: 'learn' | 'review' | 'synthesize';
  priority: number; // 1-10, 10 最高
  assignedTo?: string; // 子代理 ID
  status: 'pending' | 'running' | 'completed' | 'failed' | 'timed_out';
  createdAt: number;
  startedAt?: number;
  completedAt?: number;
  timeout: number; // 毫秒
  retries: number;
  maxRetries: number;
  input: any;
  output?: any;
  error?: string;
}
```

#### 2.2.2 进度监控器 (Progress Monitor)

监控策略：
- **轮询模式**：每 30 秒检查一次子代理状态
- **超时检测**：5 分钟无响应 → 标记为超时
- **心跳回报**：子代理每 1 分钟发送一次状态

```typescript
interface ProgressUpdate {
  sessionKey: string;
  timestamp: number;
  status: 'working' | 'waiting' | 'blocked' | 'done';
  currentStep: string;
  progress: number; // 0-100
  notes?: string;
}
```

#### 2.2.3 成果收集器 (Outcome Collector)

数据来源：
1. **子代理 JSONL 文件**：读取 `/home/tolls/.openclaw/agents/{agentId}/sessions/{sessionId}.jsonl`
2. **主会话历史**：`sessions_history` API
3. **内部日志**：错误日志、运行时状态

---

## 三、实现方案

### 3.1 会话追踪表

创建 `memory/session-tracker.json`：

```json
{
  "sessions": {},
  "stats": {
    "total": 0,
    "running": 0,
    "completed": 0,
    "failed": 0
  }
}
```

每次启动子代理时注册：
```json
{
  "agent:architect:subagent:3523fb91-...": {
    "task": "学习框架优化",
    "startTime": 1770870980000,
    "lastCheckTime": 1770870980000,
    "status": "running",
    "outputPath": "/home/tolls/.openclaw/agents/architect/sessions/..."
  }
}
```

### 3.2 主动进度汇报机制

实现脚本 `scripts/session-monitor.sh`：

```bash
#!/bin/bash
# 会话监控脚本
# 每 30 秒检查一次子代理状态

TRACKER_FILE="$WORKSPACE/memory/session-tracker.json"
SESSION_DIR="$HOME/.openclaw/agents"

while true; do
  CURRENT_TIME=$(date +%s%N | cut -b1-13)
  
  # 读取追踪表
  for sessionKey in $(jq -r '.sessions | keys[]' "$TRACKER_FILE"); do
    agentId=$(echo "$sessionKey" | cut -d: -f1)
    sessionId=$(echo "$sessionKey" | cut -d: -f4)
    jsonlPath="$SESSION_DIR/$agentId/sessions/$sessionId.jsonl"
    
    # 检查文件是否存在且有内容
    if [ -f "$jsonlPath" ]; then
      lastLine=$(tail -1 "$jsonlPath" 2>/dev/null)
      if [ -n "$lastLine" ]; then
        # 更新状态
        jq --arg key "$sessionKey" \
           --arg time "$CURRENT_TIME" \
           '.sessions[$key].lastCheckTime = $time' \
           "$TRACKER_FILE" > "$TRACKER_FILE.tmp" && mv "$TRACKER_FILE.tmp" "$TRACKER_FILE"
      fi
    fi
  done
  
  sleep 30
done
```

### 3.3 成果自动收集

实现脚本 `scripts/outcome-collector.py`：

```python
#!/usr/bin/env python3
"""
成果收集器 - 自动从子代理会话中提取学习成果
"""

import json
import os
from pathlib import Path
from datetime import datetime

def extract_assistant_messages(jsonl_path):
    """从 JSONL 文件中提取 assistant 消息"""
    messages = []
    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    if data.get('role') == 'assistant':
                        messages.append(data.get('content', ''))
    except Exception as e:
        print(f"Error reading {jsonl_path}: {e}")
    return messages

def format_learning_outcome(messages):
    """将消息格式化为学习成果"""
    if not messages:
        return None
    
    # 最后一条消息作为主要输出
    main_output = messages[-1]
    
    return f"""## {datetime.now().strftime('%H:%M')} - 子代理学习成果

{main_output}

---
来源: 子代理会话
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

def collect_outcomes(session_dir, memory_dir):
    """收集所有子代理的成果"""
    today_md = os.path.join(memory_dir, f"{datetime.now().strftime('%Y-%m-%d')}.md")
    
    for agent_dir in Path(session_dir).iterdir():
        if agent_dir.is_dir() and agent_dir.name != 'main':
            sessions_dir = agent_dir / 'sessions'
            if sessions_dir.exists():
                for jsonl_file in sessions_dir.glob('*.jsonl'):
                    messages = extract_assistant_messages(jsonl_file)
                    outcome = format_learning_outcome(messages)
                    
                    if outcome:
                        # 追加到今日记忆
                        with open(today_md, 'a', encoding='utf-8') as f:
                            f.write(outcome + '\n')
                        
                        print(f"Collected outcome from {jsonl_file.name}")

if __name__ == '__main__':
    session_dir = os.path.expanduser('~/.openclaw/agents')
    memory_dir = os.path.expanduser('~/.openclaw/workspace-clean/memory')
    
    collect_outcomes(session_dir, memory_dir)
```

### 3.4 记忆写入流程

建立统一接口 `memory/write-learning.ts`：

```typescript
interface LearningEntry {
  timestamp: string;
  source: 'main' | 'subagent' | 'cron' | 'auto-learn';
  category?: 'concept' | 'skill' | 'insight' | 'practice';
  title: string;
  content: string;
  tags?: string[];
}

async function writeLearning(entry: LearningEntry) {
  // 1. 写入今日记忆
  await appendToDailyLog(entry);

  // 2. 如果是核心概念，写入 MEMORY.md
  if (entry.category === 'concept' || entry.category === 'insight') {
    await appendToCoreMemory(entry);
  }

  // 3. 如果是实用技能，更新 shared/skills.md
  if (entry.category === 'skill') {
    await updateSkillLibrary(entry);
  }

  // 4. 更新 recent_context.md
  await updateRecentContext(entry);
}
```

---

## 四、优化后的工作流程

### 4.1 启动学习任务

```
1. 用户发起学习请求
   ↓
2. 任务调度器生成学习计划
   ↓
3. 注册到 session-tracker.json
   ↓
4. 启动子代理
   ↓
5. 进度监控器开始轮询
```

### 4.2 执行中的监控

```
每 30 秒：
  ├─ 检查子代理 JSONL 文件更新
  ├─ 更新 session-tracker.json
  ├─ 如果超时 → 标记并通知用户
  └─ 如果完成 → 触发成果收集器
```

### 4.3 任务完成后的处理

```
1. 成果收集器提取输出
   ↓
2. 格式化为 Markdown
   ↓
3. 写入 memory/2026-02-12.md
   ↓
4. 如果重要 → 更新 MEMORY.md 和 shared/skills.md
   ↓
5. 向用户发送完成通知
```

---

## 五、关键指标

### 5.1 成功标准

| 指标 | 目标 | 当前 | 改进 |
|------|------|------|------|
| 子代理输出获取率 | 100% | 0% | +100% |
| 进度可见性 | 实时 | 无 | ✅ |
| 记忆自动更新 | 任务完成后 | boot check | 即时 |
| 框架错误率 | < 5% | 未知 | 需监控 |

### 5.2 监控指标

- 任务完成时间
- 子代理响应延迟
- 记忆写入成功率
- 错误类型分布

---

## 六、实施计划

### Phase 1: 基础设施 (1-2天)
- [ ] 创建 session-tracker.json 结构
- [ ] 实现 session-monitor.sh
- [ ] 部署为后台服务

### Phase 2: 成果收集 (1天)
- [ ] 实现 outcome-collector.py
- [ ] 测试 JSONL 文件读取
- [ ] 验证格式化输出

### Phase 3: 记忆集成 (1天)
- [ ] 统一写入接口
- [ ] 去重逻辑
- [ ] 标签系统

### Phase 4: 测试和优化 (1-2天)
- [ ] 端到端测试
- [ ] 性能优化
- [ ] 错误处理

---

## 七、风险和备选方案

### 7.1 风险

| 风险 | 可能性 | 影响 | 缓解 |
|------|--------|------|------|
| 文件权限问题 | 中 | 高 | 使用 sudo 或修改权限 |
| JSONL 锁竞争 | 低 | 低 | 使用文件锁或重试 |
| 内存溢出 | 低 | 中 | 限制单文件大小 |

### 7.2 备选方案

如果框架层面问题无法解决，采用：
1. **独立脚本监控**：完全绕过 OpenClaw 的会话系统
2. **外部消息队列**：使用 Redis 作为中间层
3. **直接调用 LLM API**：不使用子代理，直接调用

---

## 八、后续优化方向

1. **学习计划自动生成**：基于历史表现生成个性化学习路径
2. **成效评估**：量化学习成果的应用情况
3. **知识图谱**：建立学习内容之间的关联
4. **跨会话记忆**：支持长期记忆的跨会话复用

---

**文档版本**: v1.0
**最后更新**: 2026-02-12 13:06
