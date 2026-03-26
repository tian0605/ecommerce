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

## 核心脚本

| 脚本 | 功能 |
|------|------|
| `task_manager.py` | 任务状态管理器 |
| `logger.py` | 统一日志记录器 |
| `prod_task_cron.py` | 独立任务执行器 |

## 数据库表

### tasks 表
```sql
tasks (
  task_name VARCHAR PRIMARY KEY,
  display_name VARCHAR,
  description TEXT,
  priority VARCHAR(10),         -- P0/P1/P2
  status VARCHAR(20),          -- pending/running/completed/failed
  exec_state VARCHAR(30),       -- NEW/END/PROCESSING/ERROR_FIX_PENDING/NORMAL_CRASH/REQUIRES_MANUAL
  parent_task_id VARCHAR(50),    -- 父任务ID
  task_level INT,               -- 1=父任务, 2=子任务
  root_task_id VARCHAR(50),      -- 根任务ID
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

## 使用方法

### Python调用

```python
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')
from task_manager import TaskManager

tm = TaskManager()

# 获取可执行任务（优先子任务）
tasks = tm.get_actionable_tasks()

# 更新任务状态
tm.mark_start('TASK-001')      # 开始执行
tm.mark_end('TASK-001', '成功')  # 标记完成
tm.mark_error_fix_pending('TASK-001', '错误信息', '修复建议')  # 需要修复

# 创建子任务
tm.create_sub_task(
    parent_task_id='TASK-001',
    task_name='FIX-TASK-001-001',
    display_name='修复XXX问题',
    description='...',
    priority='P0'
)

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

## exec_state 状态说明

| 状态 | 含义 | 处理方式 |
|------|------|----------|
| NEW | 新任务 | 等待执行 |
| PROCESSING | 执行中 | 正在执行 |
| END | 已完成 | 无需处理 |
| ERROR_FIX_PENDING | 需要修复 | 优先处理 |
| NORMAL_CRASH | 正常崩溃 | 可自动重试 |
| REQUIRES_MANUAL | 需要人工 | 暂停执行 |

## 优先级规则

1. **先按优先级**：P0 > P1 > P2
2. **同优先级**：子任务（level=2）优先于父任务（level=1）
3. **每次最多处理**：2个任务（可通过 `limit` 参数调整）

```python
# 获取前2个可执行任务
tasks = tm.get_actionable_tasks(limit=2)
```
