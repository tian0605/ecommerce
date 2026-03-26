# task-manager 使用指南

## 快速开始

### 1. 初始化 TaskManager

```python
from task_manager import TaskManager

tm = TaskManager()  # 自动连接数据库
# 使用完后
tm.close()
```

### 2. 查询任务

```python
# 获取所有任务
all_tasks = tm.get_all_tasks()

# 获取可执行任务（推荐）
actionable = tm.get_actionable_tasks()

# 获取单个任务
task = tm.get_task('TC-FLOW-001')

# 获取任务树
tree = tm.get_task_tree()
```

### 3. 更新任务状态

```python
# 标记开始执行
tm.mark_start('TASK-001')

# 标记成功完成
tm.mark_end('TASK-001', '执行成功')

# 标记需要修复（自动创建子任务）
tm.mark_error_fix_pending('TASK-001', '错误信息', '修复建议')

# 标记需要人工介入
tm.mark_requires_manual('TASK-001', '需要人工处理')

# 标记正常崩溃（可重试）
tm.mark_normal_crash('TASK-001', '网络错误')

# 重置任务状态
tm.reset_task('TASK-001', 'new', 'pending')
```

### 4. 创建子任务

```python
tm.create_sub_task(
    parent_task_id='TC-FLOW-001',
    task_name='FIX-STEP6-001',
    display_name='修复Step6参数传递问题',
    description='详细描述...',
    priority='P0',
    fix_suggestion='检查update_product方法参数'
)
```

### 5. 日志记录

```python
from logger import get_logger

log = get_logger('heartbeat')
log.set_task('TASK-001')
log.info('开始处理')
log.set_message('处理完成')
log.finish('success')
```

## 命令行使用

```bash
# 查看所有任务
python3 /root/.openclaw/workspace-e-commerce/scripts/task_manager.py

# 查看任务树
python3 -c "
import sys
sys.path.insert(0, 'scripts')
from task_manager import TaskManager
tm = TaskManager()
tree = tm.get_task_tree()
for root in tree:
    print(f\"{'[P0]' if root['priority']=='P0' else '[P1]'} {root['display_name']}\")
    for child in root.get('children', []):
        print(f\"  └── {child['display_name']}\")
tm.close()
"
```

## 常见问题

### Q: 如何区分父任务和子任务？
A: 通过 `task_level` 字段：`1` 是父任务，`2` 是子任务

### Q: 子任务失败后会自动重试吗？
A: 不会，需要通过 `prod_task_cron` 定时任务自动调度

### Q: 如何查看任务执行历史？
A: 查询 `main_logs` 表，按 `task_name` 筛选
