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

**代码持久化机制：**
```
自愈生成的修复代码
    ↓
写入 scripts/fixes/fix_{task_name}.py
    ↓
加载并执行
    ↓
确保下次重试时代码仍可用
```

**持久化文件示例：**
```python
# scripts/fixes/fix_FIX_TC_FLOW_001_010.py
def analyze(data):
    ...

# 执行入口
def apply_fix():
    pass
```

### 2.1 状态管理规范

**状态更新时机：**
- `mark_end()` 必须在所有验证完成后调用
- 禁止在验证完成前上报成功
- 每次状态更新需记录到 main_logs

### 修复4: 根因分析机制 (2026-03-27)

**问题：** 父任务反复失败（重试>3次），FIX子任务一直在打补丁，没有找到真正根因

**改进方案：**
```
父任务失败
    ↓
重试次数 < 3 → 创建FIX子任务（原有逻辑）
    ↓
重试次数 >= 3 → LLM根因分析 → 找出真正根因
                ↓
         如果N个问题 → 创建N个修复子任务
                ↓
         修复后验证 → 新问题再次分析
                ↓
         循环直到所有问题解决 ✅
```

**持续循环机制：**
1. 重试>=3次 → 调用LLM分析
2. 发现N个问题 → 创建N个修复子任务
3. 修复后验证 → 继续监控
4. 新问题出现 → 触发新一轮LLM分析
5. 循环直到所有问题解决

**多问题处理：**
- LLM可能发现多个独立问题
- 每个问题单独创建一个FIX子任务
- 并行修复，互不干扰

**新增脚本：** `scripts/root_cause_analyzer.py`

**分析流程：**
1. 获取任务最近50条日志
2. 调用 qwen3.5-plus LLM 分析
3. 解析返回的根因和修复方案
4. 生成详细分析报告

**SKILL.md更新记录：**
- P0问题修复记录

## P0问题修复记录

### 修复1: 代码持久化 (2026-03-27)

**问题：** 自愈代码只在内存执行，重启后丢失

**修复方案：**
```python
# subtask_executor.py execute_fix_code() 函数
fix_file = scripts/fixes/fix_{task_name}.py

# 1. 持久化到文件
with open(fix_file, 'w') as f:
    f.write(code)

# 2. 从文件加载执行
with open(fix_file, 'r') as f:
    exec(f.read(), exec_globals, exec_locals)
```

**持久化目录：** `scripts/fixes/`

**验证：** 重启后FIX任务不再报 `name 'analyze' is not defined`

---

### 修复2: 状态管理规范 (2026-03-27)

**问题：** 任务状态更新早于验证完成

**检查结果：** FIX-010执行流程正常，未发现竞态条件

**规范要求：**
- `mark_end()` 必须在所有验证完成后调用
- 禁止在验证完成前上报成功
- 每次状态更新需记录到 main_logs

---

### 修复3: 提示词优化 (2026-03-27)

**文件：** `config/prompts/subtask_executor_system.txt`

**改进：** 要求LLM生成完整可持久化的函数定义，而非代码片段

---

## P0优化建议（待处理）

| 优先级 | 问题 | 建议 | 状态 |
|--------|------|------|------|
| P1 | 重试策略过长 | 10分钟→30秒 | 待处理 |
| P1 | 日志冗余 | 禁止打印代码 | 待处理 |
| P2 | 预检机制缺失 | 先检查函数是否存在 | 待处理 |

### 2.2 常见问题

**Q: 代码执行成功但功能不正常？**
A: 检查是否需要在主流程中加载持久化的修复代码

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

## 配置文件

### LLM模型配置

```python
# config/llm_config.py
LLM_CONFIG = {
    'api_key': 'sk-914c1a9a5f054ab4939464389b5b791f',
    'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'model': 'qwen3.5-plus',
    'max_tokens': 2000,
    'temperature': 0.3,
    'timeout': 120
}
```

### 提示词配置

提示词独立管理在 `config/prompts/` 目录：

| 文件 | 用途 |
|------|------|
| `error_analyzer_system.txt` | 错误分析系统提示词 |
| `error_analyzer_user.txt` | 错误分析用户模板 |
| `subtask_executor_system.txt` | 子任务执行系统提示词 |

### 修改提示词

修改提示词只需编辑对应的 `.txt` 文件，无需修改代码。

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

## 卡死检测与自动修复

### 检测逻辑

```python
STUCK_TIMEOUT_MINUTES = 10  # 10分钟无工作日志判定为卡死

def is_task_stuck(task_name: str) -> bool:
    """判断任务是否卡死（排除following日志）"""
    last_time = get_task_last_log_time(task_name)
    if not last_time:
        return False
    return datetime.now() - last_time > timedelta(minutes=STUCK_TIMEOUT_MINUTES)
```

### 卡死处理流程

当检测到任务卡死时，自动执行以下操作：

```
1. 杀掉相关进程
   kill_process(task_name)
       ↓
2. 创建子任务追踪修复
   FIX-{task_name}-STUCK
       ↓
3. 父任务标记为 error_fix_pending
   exec_state = 'error_fix_pending'
       ↓
4. 写入日志
   "任务卡死，已创建修复子任务 FIX-xxx"
```

### 卡死 vs following

| 场景 | 判断 | 动作 |
|------|------|------|
| 10分钟内有工作日志 | following | 正常，插入日志 |
| 10分钟内无工作日志 | stuck | 杀进程+创建子任务+重置 |

### 自动创建的卡死修复子任务

```python
fix_task_name = f"FIX-{task_name}-STUCK"
tm.create_fix_subtasks(task_name, [{
    'error': f'任务执行卡死（>{STUCK_TIMEOUT_MINUTES}分钟无响应）',
    'fix': '检查Playwright浏览器稳定性，增加超时控制',
    'success_criteria': '浏览器操作稳定，无卡死'
}])
```

## 日志机制

### 日志写入时机

| 场景 | 写入 | 内容 |
|------|------|------|
| 任务开始执行 | ✅ | `task_name` + "开始执行" |
| 执行成功 | ✅ | `task_name` + "执行成功" |
| 执行失败 | ✅ | `task_name` + "失败原因" |
| 执行跳过 | ✅ | `task_name` + "跳过原因" |
| 任务执行中 | ✅ | `following` + "任务正常运行中" |
| 任务卡死 | ✅ | `failed` + "任务执行超时" |

### main_logs 表状态值

| run_status | 含义 | 说明 |
|------------|------|------|
| running | 执行中 | 任务刚开始执行 |
| following | 监控中 | 任务执行中，定时任务检查到仍在运行 |
| success | 执行成功 | 任务正常完成 |
| failed | 执行失败 | 任务失败或被判定为卡死 |
| skipped | 跳过 | 无待执行任务 |

### Logger.finish() 状态更新

**重要：** `log.finish()` 方法会强制更新 `run_status`，允许多次调用时状态被后续调用覆盖。

```python
# 错误示例（会导致状态不一致）
log.finish("running")  # 第一次调用
# ... 执行任务 ...
log.finish("success")  # 第二次调用会覆盖

# 正确示例：使用不同的Logger实例
log_start = get_logger('task')
log_start.set_task(task_name).finish("running")

# 任务执行...

log_end = get_logger('task')
log_end.set_task(task_name).finish("success")
```

**注意：** 当前 prod_task_cron 使用单例Logger，在同一个任务执行流程中多次调用 `finish()`。修复后的代码会强制覆盖状态，确保最终状态正确。

### prod_task_cron 监控机制

**功能：**
1. **Popen实时输出**: 使用 `subprocess.Popen` 实时打印任务stdout
2. **实时日志写入**: 每行stdout实时写入main_logs（通过on_line_callback）
3. **卡死检测**: 10分钟无日志判定为卡死
4. **自动处理**: 卡死任务自动杀掉进程 + 重置为 error_fix_pending
5. **following状态**: 执行中任务插入"正常运行"日志

**Popen实时日志实现：**
```python
def run_with_popen(task_name: str, script_info: dict, on_line_callback=None) -> tuple:
    """使用Popen执行任务，实时输出
    
    Args:
        on_line_callback: 每行输出的回调函数，签名为 (line: str) -> None
    """
    proc = subprocess.Popen(cmd, stdout=PIPE, stderr=STDOUT, text=True, bufsize=1)
    
    for line in proc.stdout:
        print(line, end='')  # 实时打印到控制台
        if on_line_callback:
            on_line_callback(line.rstrip())  # 实时写入main_logs
    
    proc.wait()
    return success, output

# 调用时传入log.log_line作为回调（不是log.info！）
run_with_popen(task_name, script_info, on_line_callback=log.log_line)
```

**重要：必须使用 `log.log_line()` 而不是 `log.info()`**

| 方法 | 功能 | 说明 |
|------|------|------|
| `log.info()` | 打印到控制台 | 不写入数据库 |
| `log.log_line()` | 写入main_logs | 每行实时写入 |

**Logger.log_line() 实现：**
```python
def log_line(self, line: str):
    """写入一行日志到main_logs（用于Popen实时回调）"""
    if not line:
        return
    try:
        conn = psycopg2.connect(**self.DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO main_logs (log_type, task_name, run_status, run_message, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (self.log_type, self.task_name, 'running', line[:500]))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[WARN] log_line failed: {e}")
```

**卡死检测逻辑：**
```python
STUCK_TIMEOUT_MINUTES = 10

def is_task_stuck(task_name: str) -> bool:
    last_time = get_task_last_log_time(task_name)
    if not last_time:
        return False
    return datetime.now() - last_time > timedelta(minutes=STUCK_TIMEOUT_MINUTES)

def handle_processing_task(task_name):
    if is_task_stuck(task_name):
        kill_process(task_name)  # 杀掉进程
        tm.update_task(task_name, status='failed', exec_state='error_fix_pending')
        log.finish("failed")
    else:
        log.set_task(task_name).set_message("任务正常运行中").finish("following")
```

**执行流程：**
```
1. 检查 processing 状态任务
   ↓
2. is_task_stuck(task_name)?
   ├─ Yes → 判定卡死 → 杀掉进程 → 重置状态 → failed日志
   │
   └─ No → 插入 following 日志
           ↓
3. 检查待执行任务 (get_actionable_tasks)
   ↓
4. 无任务 → skipped日志（仅当无processing任务时）
```

### prod_task_cron 日志写入点

```python
# 1. 任务开始执行
log.set_task(task_name)
tm.mark_start(task_name)      # 数据库更新
log.finish("running")         # main_logs 写入

# 2. 执行成功
if success:
    tm.mark_end(task_name)
    log.set_message(f"{display_name} 成功").finish("success")

# 3. 执行失败
else:
    log.set_message(f"{display_name} 失败").finish("failed")

# 4. 执行跳过
if not actionable:
    log.set_message("无待执行任务").finish("skipped")
```

### main_logs 表状态值

| run_status | 含义 |
|------------|------|
| running | 执行中 |
| success | 执行成功 |
| failed | 执行失败 |
| skipped | 跳过（无任务） |

### 执行中日志的挑战

workflow_runner 是长时间运行的子进程，stdout/stderr 被捕获但无法实时流式返回。

**解决方案：**
1. workflow_runner 使用 `print()` 直接输出到 stdout
2. 主进程捕获输出并实时打印
3. 使用 `subprocess.Popen` 而非 `subprocess.run`

```python
# 使用 Popen 实现实时输出
proc = subprocess.Popen(
    cmd, 
    stdout=subprocess.PIPE, 
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

for line in proc.stdout:
    print(line, end='')  # 实时打印
    log.info(line)        # 可选：写入日志

proc.wait()
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
