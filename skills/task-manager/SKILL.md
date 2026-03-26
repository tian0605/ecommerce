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

- 任务状态管理（NEW/PROCESSING/END/ERROR_FIX_PENDING/NORMAL_CRASH/REQUIRES_MANUAL）
- 多级任务结构（父任务/子任务）
- 统一日志记录（main_logs表）
- 任务优先级（P0/P1/P2）
- 批量子任务创建
- 自动状态回写

## 数据库表

### tasks 表
```sql
tasks (
  task_name VARCHAR PRIMARY KEY,
  display_name VARCHAR,
  description TEXT,
  priority VARCHAR(10),         -- P0/P1/P2
  status VARCHAR(20),          -- pending/running/completed/failed
  exec_state VARCHAR(30),      -- 见下方状态说明
  parent_task_id VARCHAR(50),  -- 父任务ID
  task_level INT,              -- 1=父任务, 2=子任务
  root_task_id VARCHAR(50),    -- 根任务ID
  fix_suggestion TEXT,          -- 修复建议
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
  run_status VARCHAR(20),       -- running/success/failed/skipped
  run_message TEXT,
  run_content TEXT,
  created_at TIMESTAMP
)
```

## exec_state 状态说明

| 状态 | 含义 | 触发条件 | 是否可执行 |
|------|------|----------|-----------|
| NEW | 新任务 | 初始创建 | ✅ |
| PROCESSING | 执行中 | 任务开始执行 | ❌ |
| END | 已完成 | 执行成功 | ❌ |
| ERROR_FIX_PENDING | 需要修复 | 业务逻辑错误 | ✅ |
| NORMAL_CRASH | 正常崩溃 | 网络/系统错误 | ✅ |
| REQUIRES_MANUAL | 需要人工 | 需人工介入 | ❌ |

## 状态回写规则

### 执行流程图

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
                                  │  │业务错误 │ │系统错误  │
                                  │  │ mark_   │ │ mark_    │
                                  │  │ error_  │ │ normal_  │
                                  │  │ fix_    │ │ crash    │
                                  │  │ pending │ └──────────┘
                                  │  └─────────┘
                                  │       │
                                  │       ▼
                                  │  ┌─────────────┐
                                  │  │创建子任务   │
                                  │  │自动批量创建 │
                                  │  └─────────────┘
```

### 状态回写方法

| 方法 | 触发条件 | status | exec_state | 后续动作 |
|------|----------|--------|------------|---------|
| `mark_start()` | 任务开始执行 | `running` | `processing` | - |
| `mark_end()` | 执行成功 | `completed` | `end` | ✅ 任务完成 |
| `mark_error_fix_pending()` | 业务逻辑错误 | `failed` | `error_fix_pending` | 自动创建1个子任务 |
| `mark_normal_crash()` | 网络/系统错误 | `pending` | `normal_crash` | 可自动重试 |
| `mark_requires_manual()` | 需要人工介入 | `failed` | `requires_manual` | 暂停 |

### 批量子任务创建

当一个任务有多个错误时，使用 `create_fix_subtasks` 批量创建子任务：

```python
errors = [
    {'error': 'Step4落库失败', 'fix': '检查import路径'},
    {'error': 'Step5优化失败', 'fix': '检查LLM API'},
    {'error': 'Step6回写失败', 'fix': '检查参数类型'},
]
tm.create_fix_subtasks('TC-FLOW-001', errors)
```

**效果：**
- 自动创建3个子任务（FIX-TC-FLOW-001-001/002/003）
- 父任务状态更新：`last_error = "共3个问题"`
- 父任务建议更新：`fix_suggestion = "已创建3个子任务"`

## 优先级规则

1. **先按优先级**：P0 > P1 > P2
2. **同优先级**：子任务（level=2）优先于父任务（level=1）
3. **每次最多处理**：2个任务（可通过 `limit` 参数调整）

## 自愈机制（子任务失败处理）

当子任务（level=2）执行失败时，自动触发以下流程：

```
子任务失败
    ↓
重试次数 < 3?
    ├─ Yes → mark_normal_crash() → 下次继续重试
    │
    └─ No (已达3次)
            ↓
        调用 qwen-3.5-plus LLM 分析错误
            ↓
        LLM 提出解决方案
            ↓
        创建"解决方案子任务" (SOL-xxx)
            ↓
        旧子任务标记为"作废" (is_void=True)
            ↓
        新子任务执行
            ├─ 成功 → 父任务继续
            │
            └─ 仍失败 (再3次)
                        ↓
                    requires_manual (需人工介入)
```

### 新增字段

```sql
ALTER TABLE tasks ADD COLUMN retry_count INT DEFAULT 0;  -- 重试次数
ALTER TABLE tasks ADD COLUMN solution TEXT;              -- LLM解决方案
ALTER TABLE tasks ADD COLUMN is_void BOOLEAN DEFAULT FALSE;  -- 是否作废
ALTER TABLE tasks ADD COLUMN success_criteria TEXT;      -- 成功标准
ALTER TABLE tasks ADD COLUMN analysis TEXT;              -- LLM分析
ALTER TABLE tasks ADD COLUMN plan TEXT;                  -- 修复计划
```

### 新增状态

| exec_state | 含义 |
|------------|------|
| void | 已作废（被替代） |

### 子任务执行器 (subtask_executor.py)

当子任务被执行时：

```
① 分析问题 → LLM理解错误根因
    ↓
② 思考方案 → ReAct模式思考解决路径
    ↓
③ 制定计划 → 确定是写脚本还是直接修复
    ↓
④ 执行修复 → 实际执行修复代码
    ↓
⑤ 回写结果 → 写入 tasks 表（analysis/plan字段）
```

调用方式：
```bash
python3 subtask_executor.py <task_name>
```

### 新增方法

```python
# 标记任务为作废
tm.mark_void(task_name, reason="被解决方案替代")

# 获取任务（含重试次数）
task = tm.get_task(task_name)
retry_count = task.get('retry_count', 0)

# 创建含成功标准的子任务
tm.create_fix_subtasks(task_name, [
    {
        'error': '错误描述',
        'fix': '修复建议',
        'success_criteria': '修复成功的标准',
        'analysis': 'LLM分析结果',
        'plan': '修复计划'
    }
])
```

```python
# 获取前2个可执行任务
tasks = tm.get_actionable_tasks(limit=2)
```

## 核心脚本

| 脚本 | 功能 |
|------|------|
| `task_manager.py` | 任务状态管理器 |
| `logger.py` | 统一日志记录器 |
| `prod_task_cron.py` | 独立任务执行器 |

## 使用方法

### Python调用

```python
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')
from task_manager import TaskManager

tm = TaskManager()

# 获取可执行任务（优先P0，最多2个）
tasks = tm.get_actionable_tasks(limit=2)

# 更新任务状态
tm.mark_start('TASK-001')      # 开始执行
tm.mark_end('TASK-001', '成功')  # 标记完成
tm.mark_error_fix_pending('TASK-001', '错误信息', '修复建议')

# 创建多个子任务
tm.create_fix_subtasks('TASK-001', [
    {'error': '错误1', 'fix': '修复1'},
    {'error': '错误2', 'fix': '修复2'},
])

# 获取任务树
tree = tm.get_task_tree()

tm.close()
```

### 日志记录

```python
from logger import get_logger

log = get_logger('heartbeat')
log.set_task('TASK-001').info('开始处理')
log.finish('success', '处理完成')
```

## 命令行使用

```bash
# 查看所有任务
python3 /root/.openclaw/workspace-e-commerce/scripts/task_manager.py
```

## 常见问题

### Q: 如何区分父任务和子任务？
A: 通过 `task_level` 字段：`1` 是父任务，`2` 是子任务

### Q: 子任务失败后会自动重试吗？
A: 不会，需要通过 `prod_task_cron` 定时任务自动调度

### Q: 如何查看任务执行历史？
A: 查询 `main_logs` 表，按 `task_name` 筛选

### Q: ERROR_FIX_PENDING 和 NORMAL_CRASH 的区别？
A: 
- ERROR_FIX_PENDING：业务逻辑错误，需要人工修复代码后继续
- NORMAL_CRASH：网络/系统错误，可自动重试

### Q: 多个错误如何创建多个子任务？
A: 使用 `create_fix_subtasks` 方法

### Q: 父任务完成后子任务如何处理？
A: 父任务完成后，子任务仍然独立存在，需单独处理
