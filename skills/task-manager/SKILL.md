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
- **增强错误分析（tavily-search + agent-browser）**

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
                                  │  │创建子任务│ │重试5次 │
                                  │  │继续执行  │ │→ SOL  │
                                  │  └─────────┘ └────┬────┘
                                  │                   ▼
                                  │            ┌──────────┐
                                  │            │ requires_ │
                                  │            │ manual    │
                                  │            └──────────┘
```

## 优先级规则

1. **先按任务类型**：修复类 > 常规类 > 创造类
2. **同类型按优先级**：P0 > P1 > P2
3. **同优先级**：子任务（level=2）优先于父任务（level=1）
4. **每次最多处理**：1个任务

## 任务类型（task_type）

### 类型定义

| 类型 | task_type值 | 优先级 | 说明 |
|------|------------|--------|------|
| 【常规类】 | `常规` | 中 | 已实现功能的任务（如TC-FLOW-001端到端测试） |
| 【修复类】 | `修复` | **最高** | 修复机制问题的任务（如FIX-xxx） |
| 【创造类】 | `创造` | 最低 | 逻辑待定的新任务 |

### 执行顺序

```python
# get_actionable_tasks() 的 ORDER BY 子句
ORDER BY 
    CASE task_type 
        WHEN '修复' THEN 1 
        WHEN '常规' THEN 2 
        WHEN '创造' THEN 3 
        ELSE 4
    END,
    CASE priority 
        WHEN 'P0' THEN 1 
        WHEN 'P1' THEN 2 
        WHEN 'P2' THEN 3 
    END,
    task_level DESC,
    created_at
```

### 与其他机制的关系

- **task_monitor**：检测到critical/high错误时，创建 `FIX-xxx` 子任务，**task_type=修复**
- **subtask_executor**：执行修复任务时，**task_type=修复**
- **prod_task_cron**：调用 `get_actionable_tasks()` 时按task_type优先级排序

### 代码示例

```python
# 创建常规任务
tm.create_task(
    task_name='TC-FLOW-001',
    display_name='端到端测试',
    task_type='常规',
    priority='P1'
)

# 创建修复任务（由task_monitor自动创建）
# create_fix_subtasks() 和 create_fix_subtask() 自动设置 task_type='修复'
tm.create_fix_subtasks('TC-FLOW-001', [
    {'error': 'exec环境缺少模块', 'fix': '预加载常用模块'}
])

# 查询任务类型分布
cur.execute('SELECT task_type, COUNT(*) FROM tasks GROUP BY task_type')
```

### 数据库字段

```sql
ALTER TABLE tasks ADD COLUMN task_type VARCHAR(20) DEFAULT '常规';
```

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

**代码持久化机制（改进版 v2）：**

```
修复代码生成
    ↓
┌─────────────────────────────────────┐
│  infer_target_module() 推断修复目标   │
└─────────────────────────────────────┘
    │
    ├── framework 核心框架脚本
    │   → 直接修改源文件（subtask_executor.py等）
    │   → 追加修复记录到 SKILL.md
    │   → 同时保留副本到 fixes/source_xxx.py（追溯用）
    │
    ├── skill Skills模块
    │   → 直接修改对应脚本
    │   → 追加修复记录到 SKILL.md
    │
    └── task 任务特定fix
        → 写入 fixes/fix_xxx.py（旧机制）
```

**目标推断规则：**

| 任务名模式 | 目标类型 | 源文件 | SKILL.md |
|-----------|---------|--------|----------|
| `FIX-subtask_executor-*` | framework | subtask_executor.py | task-manager/SKILL.md |
| `FIX-task_manager-*` | framework | task_manager.py | task-manager/SKILL.md |
| `FIX-prod_task_cron-*` | framework | prod_task_cron.py | task-manager/SKILL.md |
| `FIX-error_analyzer-*` | framework | error_analyzer.py | task-monitor/SKILL.md |
| `FIX-TC-FLOW-*` | framework | workflow_runner.py | **workflow-runner/SKILL.md** ✅ 已修正 |
| 其他 `FIX-xxx-*` | task | fixes/fix_xxx.py | - |

**核心改进：**
- **修复框架bug** → 直接改源文件，下次执行就是修复后的代码
- **修复skill bug** → 直接改skill脚本 + 更新skill的SKILL.md
- **修复workflow-runner问题** → **直接改 workflow_runner.py + 更新 workflow-runner/SKILL.md**
- **修复任务特定问题** → 写到 fixes/ 目录（临时的）

**skill模块修复路径映射：**

| FIX任务 | 目标脚本 | SKILL.md |
|---------|----------|----------|
| `FIX-miaoshou_updater-*` | `/home/ubuntu/.openclaw/skills/miaoshou-updater/updater.py` | miaoshou-updater/SKILL.md |
| `FIX-product_storer-*` | `/home/ubuntu/.openclaw/skills/product-storer/storer.py` | product-storer/SKILL.md |
| `FIX-listing_optimizer-*` | `/home/ubuntu/.openclaw/skills/listing-optimizer/optimizer.py` | listing-optimizer/SKILL.md |
| `FIX-collector_scraper-*` | `/home/ubuntu/.openclaw/skills/collector-scraper/scraper.py` | collector-scraper/SKILL.md |

**旧持久化文件示例（仅用于追溯）：**
```python
# scripts/fixes/fix_FIX_TC_FLOW_001_010.py
def analyze(data):
    ...

# 执行入口
def apply_fix():
    pass
```

**新增函数（subtask_executor.py）：**

| 函数 | 功能 |
|------|------|
| `infer_target_module()` | 从任务名推断修复目标（framework/skill/task） |
| `apply_fix_to_source()` | 直接修改源文件 |
| `apply_partial_fix()` | 智能合并函数级修复（部分替换） |
| `append_fix_to_skill()` | 追加修复记录到SKILL.md |
| `persist_to_fixes_dir()` | 保留旧机制（用于追溯） |
| `search_solution_with_tavily()` | 使用tavily-search搜索解决方案 |
| `diagnose_with_agent_browser()` | 使用agent-browser诊断页面元素 |
| `enhance_error_analysis()` | 整合增强分析，返回搜索结果摘要 |

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
2. 调用 deepseek-chat LLM 分析
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

### 修复5: 直接修复根因 vs FIX循环 (2026-03-27)

**问题：** TC-FLOW-001 反复失败，FIX任务循环创建但问题依旧

**根因分析：** task_monitor + 人工排查发现真正根因：
1. `workflow_runner.py` 缺少 config 路径：`sys.path` 不包含 `/root/.openclaw/workspace-e-commerce/config`
2. `llm_config.py` 缺少向后兼容导出：`LLM_API_KEY`, `LLM_BASE_URL` 等变量不存在

**关键洞察：** 有些问题不适合用FIX子任务循环修复（如跨文件路径配置、模块导入结构问题），需要直接定位根因并修复。

**修复方法：**
```
根因定位 → 直接修复源文件 → 标记相关FIX任务为end/void
```

**修复记录：**
```python
# 1. /root/.openclaw/workspace-e-commerce/config/llm_config.py
# 新增向后兼容导出
LLM_API_KEY = LLM_CONFIG['api_key']
LLM_BASE_URL = LLM_CONFIG['base_url']
DEFAULT_MODEL = LLM_CONFIG['model']
MODELS = TASK_MODELS

# 2. /root/.openclaw/workspace-e-commerce/skills/workflow-runner/scripts/workflow_runner.py
# 新增路径
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/config')
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')
```

**经验教训：**
- FIX循环适合修复"代码逻辑错误"
- 配置问题/导入问题需要直接修复源文件
- task_monitor检测到 `name 'XXX' is not defined` 时，可能需要人工介入定位真正的导入路径问题

---

### 修复8: skill模块的module_path映射错误 (2026-03-27)

**问题：** `FIX-miaoshou_updater-*` 任务被识别为 `module_type='task'` 而非 `skill`，导致修复代码无法持久化到正确的脚本路径。

**根因：**
1. skill目录名使用连字符（如 `miaoshou-updater`），任务名使用下划线（如 `miaoshou_updater`）
2. `module_path` 错误地指向 `scripts/miaoshou_updater.py` 而非 `/home/ubuntu/.openclaw/skills/miaoshou-updater/updater.py`

**修复：** 修正 `infer_target_module()` 中 skill 类型的路径匹配逻辑：
```python
# 需要同时匹配带连字符和下划线的版本
skill_normalized = skill_name.replace('-', '_').lower()
if skill_normalized in task_clean.lower():
    # 找到对应的脚本文件
```

**验证结果：**
```
FIX-miaoshou_updater-001
  → skill: miaoshou-updater
  → 源文件: /home/ubuntu/.openclaw/skills/miaoshou-updater/updater.py
  → SKILL: .../miaoshou-updater/SKILL.md
```

---

### 修复7: FIX-TC-FLOW 映射到 workflow-runner (2026-03-27)

**问题：** `FIX-TC-FLOW-*` 任务被错误识别为 `task_type='task'`，修复代码被写到 `fixes/` 目录而非直接修改 `workflow_runner.py`。

**根因：** `infer_target_module()` 函数缺少对 `FIX-TC-FLOW-*` 模式的特殊处理。

**修复：** 在 `subtask_executor.py` 中添加特殊映射：
```python
# 特殊处理：FIX-TC-FLOW-* → workflow_runner.py (workflow-runner skill)
if task_name.startswith('FIX-TC-FLOW-'):
    return {
        'module_type': 'framework',
        'module_path': '.../workflow_runner.py',
        'skill_path': '.../workflow-runner/SKILL.md',
        'module_name': 'workflow_runner.py'
    }
```

**效果：** 现在 `FIX-TC-FLOW-*` 任务的修复会：
1. 直接修改 `workflow_runner.py` 源文件
2. 追加修复记录到 `workflow-runner/SKILL.md`

---

### 修复6: 浏览器错误截图机制 (2026-03-27)

**问题：** 浏览器自动化失败时，只有文字错误信息，无法看到页面实际状态，LLM难以精准定位问题。

**改进方案：** 浏览器相关错误发生时，自动截图并上传COS，供LLM分析。

**触发条件：** 只有错误匹配以下关键词才截图：
- `selector`, `element`, `click`, `visible`, `timeout`
- `page`, `browser`, `playwright`
- `未找到`, `找不到`, `无法点击`, `不可见`
- `no such element`, `element not found`

**截图保存位置：**
- 本地：`/root/.openclaw/workspace-e-commerce/logs/screenshots/`
- COS：`workflow-screenshots/` (Bucket: tian-cloud-file-1309014213)

**代码位置：** `workflow_runner.py`
```python
├── is_browser_error()           # 检测是否浏览器相关错误
└── capture_error_screenshot()  # 截图+上传COS
```

**返回值：**
```python
{
    'screenshot_path': '/root/.../error_step6_update_20260327.png',
    'cos_url': 'https://tian-cloud.../workflow-screenshots/...',
    'screenshot_captured': True,
    'error_context': {
        'step_name': 'step6_update',
        'error': '...',
        'page_url': '...'
    }
}
```

**已集成步骤：** step1_collect, step2_scrape, step6_update

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
retry_count < 5?
    ├─ Yes → mark_normal_crash() → 下次继续重试
    │
    └─ No (已达3次)
            ↓
        调用 deepseek-chat LLM 分析错误
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
    'api_key': 'sk-2f2c6f05d33741acb27453a828651323',
    'base_url': 'https://api.deepseek.com',
    'model': 'deepseek-chat',
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
A: 会，重试5次后自动创建修复任务。

### Q: 父任务何时执行？
A: 只有所有子任务都完成（end/void）后才能执行。

### Q: requires_manual 的任务如何处理？
A: 需要人工介入处理后，手动标记子任务为 void，然后定时任务会自动重试父任务。

### Q: 如何创建SOL任务？
A: 父任务重试5次失败后自动创建修复任务（FIX-xxx）。

## 经验记录

### FIX-002 (Step5 listing-optimizer) 调试
- **问题**：`curl failed` 但日志不完整
- **调试**：直接运行 optimizer.py，curl API 实际正常
- **结论**：subtask_executor 的 exec() 是隔离环境，无法修复模块级问题
- **解决**：人工确认 listing-optimizer 正常后，标记子任务为 end

---

## 完整自愈机制文档

### 概述

当父任务执行失败时，系统会自动进入自愈循环，直到问题解决。

### 完整流程图

```
┌─────────────────────────────────────────────────────────────┐
│                     任务执行失败                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ 重试次数 < 3?    │
                    └─────────────────┘
                      │           │
                    Yes          No
                      │           │
                      ▼           ▼
            ┌─────────────┐  ┌─────────────────────────────────┐
            │ 创建FIX子任务│  │ LLM根因分析                      │
            └─────────────┘  └─────────────────────────────────┘
                              │                                 │
                              ▼                                 │
                    ┌─────────────────┐                        │
                    │ 发现N个问题?     │                        │
                    └─────────────────┘                        │
                      │           │                           │
                    Yes          No                            │
                      │           │                           │
                      ▼           ▼                           │
            ┌─────────────┐  ┌─────────────────┐              │
            │创建N个FIX子任务│ │  使用默认Step    │              │
            └─────────────┘  │  修复子任务       │              │
                              └─────────────────┘              │
                              │                                 │
                              ▼                                 │
                    ┌─────────────────┐                        │
                    │ 子任务执行中     │◄────────────────────────┘
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ 问题解决?       │
                    └─────────────────┘
                      │           │
                    Yes          No
                      │           │
                      ▼           ▼
                    END      ┌────────────┐
                             │ 再次失败   │
                             │ retry++    │
                             │ 回到开头   │
                             └────────────┘
```

### 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 重试阈值 | 3次 | 超过此阈值触发LLM分析 |
| 分析日志数 | 50条 | 从main_logs获取最近日志数 |
| LLM模型 | deepseek-chat | 用于根因分析 |
| 子任务级别 | 2 | FIX子任务不允许再创建子任务 |

### 根因分析提示词

**System Prompt:**
```
你是一个专业的电商运营自动化系统错误分析专家。

当任务反复失败时，你需要从日志中找出真正的根本原因。

【分析要求】
1. 识别日志中的错误模式
2. 找出真正的根因（不是表面错误）
3. 如果有多个独立问题，都要找出来

【输出格式】
【根因分析】...
【问题列表】...
【修复方案】...
【优先级】...
```

### 状态转换图

```
NEW ──执行──► PROCESSING ──成功──► END
                │
                └──失败──► ERROR_FIX_PENDING ──重试成功──► END
                              │
                              └──重试>=3次──► LLM分析 ──► 多子任务
                                                          │
                                                          ▼
                                                      PROCESSING
```

### 注意事项

1. **子任务不允许再创建子任务**：task_level=2的任务不能创建新的FIX任务
2. **状态持久化**：修复代码必须写入文件，确保重启后可用
3. **多问题并行**：多个独立问题可以同时修复
4. **无限循环保护**：通过状态管理防止无限循环

---

## 独立修复任务执行器

### 问题背景

修复任务（FIX）和常规任务（TC-FLOW）混合执行导致优先级混乱。

### 解决方案

**新增 `fix_task_cron.py`：** 独立的修复任务执行器

| 脚本 | 频率 | 处理任务 |
|------|------|---------|
| `fix_task_cron.py` | 每1分钟 | `task_type='修复'` |
| `prod_task_cron.py` | 每10分钟 | `task_type='常规'`（排除修复类） |

### Crontab配置

```bash
*/1 * * * *  cd /root/.openclaw/workspace-e-commerce && python3 scripts/fix_task_cron.py >> logs/fix_task.log 2>&1
*/10 * * * * cd /root/.openclaw/workspace-e-commerce && python3 scripts/prod_task_cron.py >> logs/prod_task.log 2>&1
```

### 任务协调机制

1. `fix_task_cron` 标记任务为 `processing`
2. `prod_task_cron` 检测到 `processing` 任务
3. 输出 "任务正常运行中，等待下一次检查"
4. 不会抢执行修复任务

### 父任务重试策略（优化版）

**重试阈值：**
| 重试次数 | 行为 |
|---------|------|
| 1-2次 | 解析错误步骤，创建子任务 |
| 3-4次 | 调用根因分析器 + 解析错误步骤，创建子任务 |
| **5次及以上** | **每次都创建新的FIX任务（编号递增）+ 双重子任务（根因+步骤）** |

**流程：**
```
父任务失败
    ↓
retry_count >= 5?
    ├─ Yes: 
    │   1. 创建 FIX-taskname-NNN（递增编号）
    │   2. 调用 task_monitor 获取根因分析
    │   3. 创建双重子任务：根因修复 + 步骤修复
    │   4. return（不继续执行）
    │
    └─ No:
            ↓
        retry_count >= 3?
            ├─ Yes: 
            │   1. 调用 root_cause_analyzer
            │   2. 创建步骤修复子任务
            │
            └─ No (1-2次):
                1. 只创建步骤修复子任务
```

**编号递增示例：**
- FIX-TC-FLOW-001-001（第1次修复）
- FIX-TC-FLOW-001-002（第2次修复）
- FIX-TC-FLOW-001-003（第3次修复）

**双重子任务结构：**
```
FIX-TC-FLOW-001-003
  ├── 子任务1: 根因修复（分析失败日志）
  ├── 子任务2: 步骤修复（update）
  └── 子任务3: 步骤修复（analyze）
```

**关键优化：**
- 第5次失败时自动调用 `task_monitor` 获取系统级根因分析
- 创建 `FIX-{task_name}` 修复任务，由 `fix_task_cron` 优先处理
- 修复任务完成后，原任务状态重置并重新执行

### 关键经验教训

1. **FIX循环适合代码逻辑错误，不适合配置/导入问题**
2. **task_monitor检测到 `name 'X' is not defined` 时，需判断上下文**
   - `subtask_executor`执行时 → `exec_globals`缺少模块
   - `workflow_runner`运行时 → `sys.path`路径缺失
3. **修复任务应直接改源文件+更新SKILL.md，而非打补丁到fixes目录**

---

## 修复记录增强 (2026-03-27)

### 问题

1. `main_logs.run_content` 日志不完整，任务失败时没有记录完整错误
2. 创建子修复任务时，`last_error` 字段只记录简短摘要，不利于分析
3. 修复任务执行后没有记录修复内容的详细信息

### 修复

#### 1. logger.py - log_line函数重构

**问题：** 每行日志单独INSERT到main_logs，run_content为空

**修复：**
```python
def log_line(self, line: str):
    # 累积到self.run_content
    self.run_content += line + "\n"
    if len(self.run_content) > 100000:
        self.run_content = self.run_content[-80000:]
    print(line)  # 保持实时可见
```

#### 2. prod_task_cron.py - 完整错误信息记录

**改进：**
- 步骤失败：`步骤失败: {step}\n完整错误:\n{output[-2000:]}`
- 根因分析：`根因问题: {prob}\n完整分析:\n{result.stdout[:2000]}`
- last_error：`output[-3000:]`（保留更多错误信息）

#### 3. subtask_executor.py - 修复任务详细日志

**execute_fix_code 返回详细信息：**
```python
"框架修复: 完整替换源文件: xxx.py | 源文件修改: xxx; SKILL更新: xxx; 备份: fixes/xxx.py"
"Skill修复: 完整替换源文件: xxx.py | 源文件修改: xxx; SKILL更新: xxx; 备份: fixes/xxx.py"
```

**main() 中记录完整修复内容：**
```python
fix_content = f"""=== 修复任务执行详情 ===
任务: {task_name}
分析: {parsed['analysis']}
修复代码:
{parsed['code_fix']}
执行结果: {msg}
"""
log.set_message(f"修复成功").set_content(fix_content).finish("success")
```

### 效果

| 改进项 | 改进前 | 改进后 |
|--------|--------|--------|
| main_logs.run_content | 空 | 累积完整执行日志 |
| 子任务last_error | 简短摘要 | 完整错误详情(2000+字符) |
| 修复任务run_content | 空 | 完整分析+代码+执行结果 |

### 判断修复是否重复/无效的方法

1. **查询最近N次修复任务的run_content：**
```sql
SELECT task_name, run_content, created_at
FROM main_logs
WHERE task_name LIKE 'FIX-%' AND run_status = 'success'
ORDER BY created_at DESC
LIMIT 10
```

2. **检查修复代码是否重复：**
```python
# 从run_content中提取修复代码
import re
code_match = re.search(r'修复代码:\n(.+?)\n执行结果', run_content, re.DOTALL)
```

3. **对比源文件修改时间：**
```bash
ls -la /home/ubuntu/.openclaw/skills/miaoshou-updater/updater.py
```


---

## 修复5: 智能推断修复目标 (2026-03-27)

### 问题

FIX子任务只根据任务名推断修复目标，无法处理UI选择器等错误类型

### 改进

新增 `infer_target_from_error()` 函数，根据错误内容智能推断目标文件

### 函数逻辑

```python
def infer_target_from_error(error_msg, analysis) -> dict:
    """根据错误内容推断修复目标"""
    
    # UI/选择器错误 → miaoshou-updater
    if any(kw in error for kw in ['未找到', '编辑按钮', 'button', 'selector']):
        if 'update' in error:
            return {'module_type': 'skill', 'module_path': '.../miaoshou_updater/updater.py'}
        elif 'scrape' in error:
            return {'module_type': 'skill', 'module_path': '.../collector_scraper/scraper.py'}
    
    # 代码执行错误 → subtask_executor
    if any(kw in error for kw in ['write()', 'name.*not.*defined', 'functools']):
        return {'module_type': 'framework', 'module_path': '.../subtask_executor.py'}
    
    # 日志错误 → logger
    if 'log_line' in error or 'run_content' in error:
        return {'module_type': 'framework', 'module_path': '.../logger.py'}
    
    # 工作流错误 → workflow_runner
    if any(kw in error for kw in ['workflow', 'step']):
        return {'module_type': 'framework', 'module_path': '.../workflow_runner.py'}
    
    return None
```

### 优先级

1. **infer_target_from_error** ← 优先（根据错误内容）
2. **infer_target_module** ← 备用（根据任务名）
3. **fixes目录** ← 最后兜底

### 效果

现在FIX子任务能自动识别问题类型并修复正确的文件

### 相关文件

- scripts/subtask_executor.py
  - infer_target_from_error()
  - execute_fix_code()

