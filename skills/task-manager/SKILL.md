---
name: task-manager
description: 任务状态管理器 - PostgreSQL数据库任务跟踪，支持多级父子任务结构，用于心跳机制和定时任务的任务管理
triggers:
  - task_manager
  - 任务状态
  - tasks表
---

# task-manager 技能

## 功能

- 任务状态管理（NEW/PROCESSING/END/ERROR_FIX_PENDING/NORMAL_CRASH/REQUIRES_MANUAL/VOID）
- 多级任务结构（父任务/子任务）
- 统一日志记录（main_logs表）
- 任务优先级（P0/P1/P2）
- 批量子任务创建
- AI自愈循环（subtask_executor）
- 自动状态回写

## 数据库表

### tasks 表
```sql
tasks (
  task_name VARCHAR PRIMARY KEY,
  display_name VARCHAR,
  description TEXT,
  priority VARCHAR(10),         -- P0/P1/P2
  status VARCHAR(20),           -- pending/running/completed/failed/voided
  exec_state VARCHAR(30),        -- 见下方状态说明
  parent_task_id VARCHAR(50),    -- 父任务ID
  task_level INT,               -- 1=父任务, 2=子任务
  root_task_id VARCHAR(50),      -- 根任务ID
  fix_suggestion TEXT,          -- 修复建议
  success_criteria TEXT,        -- 成功标准
  analysis TEXT,                -- LLM分析
  plan TEXT,                    -- 修复计划
  solution TEXT,                 -- LLM解决方案
  retry_count INT DEFAULT 0,    -- 重试次数
  is_void BOOLEAN DEFAULT FALSE,-- 是否作废
  last_executed_at TIMESTAMP,
  last_result TEXT,
  last_error TEXT,
  execution_count INT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
```

### main_logs 表
```sql
main_logs (
  id SERIAL PRIMARY KEY,
  log_type VARCHAR(30),         -- heartbeat/dev_task/prod_task/cron/error
  log_level VARCHAR(10),        -- DEBUG/INFO/WARN/ERROR
  task_name VARCHAR(50),
  run_start_time TIMESTAMP,
  run_end_time TIMESTAMP,
  duration_ms INT,
  run_status VARCHAR(20),        -- running/success/failed/skipped
  run_message TEXT,
  run_content TEXT,
  created_at TIMESTAMP
)
```

## exec_state 状态说明

| 状态 | 含义 | 是否可执行 |
|------|------|-----------|
| NEW | 新任务 | ✅ |
| PROCESSING | 执行中 | ❌ |
| END | 已完成 | ❌ |
| ERROR_FIX_PENDING | 需要修复 | ✅ |
| NORMAL_CRASH | 正常崩溃 | ✅ |
| REQUIRES_MANUAL | 需要人工 | ❌ (需人工介入) |
| VOID | 已作废 | ❌ |

## exec_state 状态转换图

```
                    ┌──────────────────────────────┐
                    │     任务开始执行              │
                    │     mark_start()             │
                    │  status=running              │
                    │  exec_state=processing       │
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │         执行结果？            │
                    └──────────────┬───────────────┘
                      ┌────────────┼────────────┐
                      ▼            │            ▼
               ┌──────────┐        │    ┌──────────────┐
               │  成功    │        │    │    失败      │
               │ mark_end│        │    └──────┬───────┘
               │ END     │        │       ┌───┴────┐
               └──────────┘        │       ▼        ▼
                                  │  ┌─────────┐ ┌──────────┐
                                  │  │业务错误 │ │系统错误 │
                                  │  │ mark_   │ │ mark_   │
                                  │  │ error_  │ │ normal_ │
                                  │  │ fix_pend │ │ crash   │
                                  │  └────┬────┘ └────┬────┘
                                  │       ▼           ▼
                                  │  ┌─────────┐ ┌─────────┐
                                  │  │创建子任务│ │重试3次 │
                                  │  │继续执行  │ │→ SOL  │
                                  │  └─────────┘ └────┬────┘
                                  │                   ▼
                                  │            ┌──────────┐
                                  │            │ requires_ │
                                  │            │ manual    │
                                  │            └──────────┘
```

## 优先级规则

1. **先按优先级**：P0 > P1 > P2
2. **同优先级**：子任务（level=2）优先于父任务（level=1）
3. **每次最多处理**：1个任务

## 核心流程

### 1. 任务执行流程（prod_task_cron）

```python
def run():
    tm = TaskManager()
    actionable = tm.get_actionable_tasks(limit=1)
    
    for task in actionable:
        if task['task_level'] == 2:
            # 子任务：使用 subtask_executor
            subprocess.run(['python3', 'subtask_executor.py', task_name])
        else:
            # 父任务：直接执行脚本
            execute_parent_task(task)
```

### 2. 子任务自愈循环（subtask_executor）

```
子任务执行失败
    ↓
retry_count < 3?
    ├─ Yes → mark_normal_crash() → 下次继续重试
    │
    └─ No (已达3次)
            ↓
        调用 qwen-3.5-plus LLM 分析错误
            ↓
        LLM 提出解决方案
            ↓
        创建 SOL-xxx 解决方案子任务
            ↓
        旧子任务标记为 VOID (is_void=True)
            ↓
        SOL子任务执行
            ├─ 成功 → 父任务继续
            │
            └─ 仍失败 (再3次)
                        ↓
                    requires_manual (需人工介入)
```

### 3. 父任务执行规则

```python
def get_actionable_tasks():
    # 获取所有可执行任务
    tasks = SELECT * FROM tasks 
            WHERE exec_state IN ('error_fix_pending', 'normal_crash', 'new')
            ORDER BY priority, task_level DESC
    
    # 过滤
    result = []
    for task in tasks:
        if task['task_level'] == 2:
            # 子任务：排除 requires_manual
            if task['exec_state'] != 'requires_manual':
                result.append(task)
        else:
            # 父任务：检查所有子任务是否都完成
            pending = SELECT COUNT(*) FROM tasks 
                     WHERE parent_task_id = task['task_name']
                     AND exec_state NOT IN ('end', 'void', 'requires_manual')
            if pending == 0:
                result.append(task)  # 所有子任务都完成
    
    return result[:limit]
```

## 核心脚本

| 脚本 | 功能 |
|------|------|
| `task_manager.py` | 任务状态管理器 |
| `logger.py` | 统一日志记录器 |
| `prod_task_cron.py` | 定时任务执行器（每30分钟） |
| `subtask_executor.py` | 子任务执行器（AI自愈） |
| `error_analyzer.py` | LLM错误分析器 |

## 使用方法

### Python调用

```python
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')
from task_manager import TaskManager

tm = TaskManager()

# 获取可执行任务（优先P0，每次1个）
tasks = tm.get_actionable_tasks(limit=1)

# 创建子任务
tm.create_fix_subtasks('PARENT-001', [
    {
        'error': 'Step4落库失败',
        'fix': '检查import路径',
        'success_criteria': 'Step4落库成功，无错误'
    }
])

# 标记状态
tm.mark_start('TASK-001')
tm.mark_end('TASK-001', '成功')
tm.mark_error_fix_pending('TASK-001', '错误信息', '修复建议')
tm.mark_void('TASK-001')  # 作废任务

# 获取任务树
tree = tm.get_task_tree()

tm.close()
```

### 日志记录

```python
from logger import get_logger

log = get_logger('heartbeat')
log.set_task('TASK-001').info('开始处理')
log.set_content('详细日志...')
log.finish('success', '处理完成')
```

## 调试指南

### subtask_executor 无法修复的问题

**能修复：**
- 类型转换错误
- 参数检查缺失
- 简单逻辑错误

**不能修复：**
- import 模块问题（subprocess 不在 exec() 上下文）
- 函数不存在（需要修改外部模块）
- API 配置错误

### 调试方法

```bash
# 直接测试目标模块
cd /root/.openclaw/workspace-e-commerce
python3 -c "
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/skills/listing-optimizer')
from optimizer import ListingOptimizer
result = ListingOptimizer()._optimize_title('测试')
print(result)
"
```

## 常见问题

### Q: 子任务失败后会自动重试吗？
A: 会，重试3次后调用 LLM 分析。

### Q: 父任务何时执行？
A: 只有所有子任务都完成（end/void）后才能执行。

### Q: requires_manual 的任务如何处理？
A: 需要人工介入处理后，手动标记子任务为 void，然后定时任务会自动重试父任务。

### Q: 如何创建SOL任务？
A: 子任务重试3次失败后自动创建，或手动调用 `create_fix_subtasks`。

## 经验记录

### FIX-002 (Step5 listing-optimizer) 调试
- **问题**：`curl failed` 但日志不完整
- **调试**：直接运行 optimizer.py，curl API 实际正常
- **结论**：subtask_executor 的 exec() 是隔离环境，无法修复模块级问题
- **解决**：人工确认 listing-optimizer 正常后，标记子任务为 end
