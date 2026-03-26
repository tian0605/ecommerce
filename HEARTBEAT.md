# HEARTBEAT.md - CommerceFlow 运营心跳（task-manager 整合版）

> **核心原则：** 工欲善其事，必先利其器。配置优先，流程为本。
> **基础架构：** task-manager 任务状态管理系统
> **适配框架：** 个人项目质量与效率决策框架 v2.0

---

## 一、核心概念：task-manager 任务状态系统

### 任务执行状态（exec_state）

| 状态 | 含义 | 是否可执行 | 处理方式 |
|------|------|-----------|----------|
| NEW | 新创建的任务 | ✅ 可执行 | 自动执行 |
| PROCESSING | 执行中 | ❌ 不可执行 | 卡死检测监控 |
| END | 已完成 | ❌ 不可执行 | 归档 |
| ERROR_FIX_PENDING | 需要修复（业务错误） | ✅ 可执行 | 最多重试3次 → 创建SOL子任务 |
| NORMAL_CRASH | 正常崩溃（系统错误） | ✅ 可执行 | 自动重试 |
| REQUIRES_MANUAL | 需要人工介入 | ❌ 需人工 | 人工处理后继续 |
| VOID | 已作废（被替换） | ❌ 不可执行 | 忽略 |

### 任务优先级（priority）

- **P0**：阻塞问题，立即处理
- **P1**：质量问题，当天处理
- **P2**：效率问题，本周处理

### 任务层级（task_level）

- **Level 1**：父任务（主任务）
- **Level 2**：子任务（分步骤或修复任务）

---

## 二、三问决策机制（整合 task-manager 版本）

### 第一问：有没有需要处理的任务？

#### 🔴 P0 立即处理的任务

**检查方法：**
```python
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')
from task_manager import TaskManager

tm = TaskManager()

# 获取所有 P0 待处理任务
p0_tasks = tm.get_actionable_tasks(limit=10)
p0_tasks = [t for t in p0_tasks if t['priority'] == 'P0']

print(f"发现 {len(p0_tasks)} 个 P0 任务")
for task in p0_tasks:
    print(f"  - {task['task_name']} ({task['display_name']}) - {task['exec_state']}")

tm.close()
```

**P0 任务处理策略：**
- NEW/ERROR_FIX_PENDING/NORMAL_CRASH 状态：立即执行
- PROCESSING 状态但超时（10分钟）：判定为卡死，自动杀进程 + 重置状态
- REQUIRES_MANUAL 状态：人工介入（90%情况下AI已尝试自动修复）

**回复格式：**
```
发现P0任务：{task_name}，状态：{exec_state}，正在处理...
```

#### 🟡 P1 当天处理的任务

**检查方法：**
```python
p1_tasks = tm.get_actionable_tasks(limit=10)
p1_tasks = [t for t in p1_tasks if t['priority'] == 'P1']

print(f"发现 {len(p1_tasks)} 个 P1 任务（今天需处理）")
```

**回复格式：**
```
今天需处理：{task_name} ({count}个P1任务)
```

#### 🟢 P2 本周处理的任务

**检查方法：**
```python
p2_tasks = tm.get_actionable_tasks(limit=10)
p2_tasks = [t for t in p2_tasks if t['priority'] == 'P2']

print(f"发现 {len(p2_tasks)} 个 P2 任务（本周优化）")
```

**回复格式：**
```
本周计划：{task_name} ({count}个P2任务)
```

---

### 第二问：任务执行是否顺畅？如何优化流程？

#### 任务执行状态检查

**检查方法：**
```python
# 获取最近10条任务执行记录
recent_tasks = tm.get_recent_tasks(limit=10)

for task in recent_tasks:
    print(f"{task['task_name']}: {task['exec_state']} - {task['last_result'] or '无结果'}")
```

#### AI 自愈效果分析

**查看自愈情况：**
```sql
-- 查询最近7天的AI自愈记录
SELECT 
    task_name,
    exec_state,
    retry_count,
    analysis,
    solution,
    created_at,
    updated_at
FROM tasks
WHERE created_at > NOW() - INTERVAL '7 days'
  AND exec_state IN ('ERROR_FIX_PENDING', 'REQUIRES_MANUAL', 'VOID')
ORDER BY created_at DESC;
```

**自愈成功率计算：**
```python
success_count = tm.count_tasks_with_state('END', days=7)
void_count = tm.count_tasks_with_state('VOID', days=7)
manual_count = tm.count_tasks_with_state('REQUIRES_MANUAL', days=7)

total_failures = void_count + manual_count
auto_heal_rate = (void_count / total_failures * 100) if total_failures > 0 else 0

print(f"AI自愈成功率：{auto_heal_rate:.1f}%")
```

#### 流程优化建议

**常见模式识别：**
```sql
-- 查找频繁失败的任务
SELECT 
    task_name,
    COUNT(*) as failure_count,
    AVG(retry_count) as avg_retries,
    MAX(last_error) as last_error
FROM tasks
WHERE exec_state IN ('ERROR_FIX_PENDING', 'REQUIRES_MANUAL')
  AND created_at > NOW() - INTERVAL '30 days'
GROUP BY task_name
ORDER BY failure_count DESC
LIMIT 10;
```

**优化行动：**
- 同一任务失败超过3次 → 创建优化任务（P1）
- 子任务经常失败 → 修改父任务逻辑（P1）
- 执行时间过长 → 优化查询或算法（P2）

---

### 第三问：上次执行的任务有哪些经验教训？

#### 成功案例沉淀（END 状态任务）

**提取成功模式：**
```sql
SELECT 
    task_name,
    success_criteria,
    duration_ms,
    run_message
FROM main_logs ml
JOIN tasks t ON ml.task_name = t.task_name
WHERE ml.run_status = 'success'
  AND ml.created_at > NOW() - INTERVAL '7 days'
ORDER BY ml.created_at DESC
LIMIT 10;
```

**记录到 KNOWLEDGE.md：**
- 成功的任务定义和参数
- 成功的执行时间范围
- 成功的错误处理策略

#### 失败教训沉淀（REQUIRES_MANUAL 状态任务）

**提取失败模式：**
```sql
SELECT 
    task_name,
    exec_state,
    fix_suggestion,
    analysis,
    last_error
FROM tasks
WHERE exec_state = 'REQUIRES_MANUAL'
  AND updated_at > NOW() - INTERVAL '30 days'
ORDER BY updated_at DESC;
```

**记录到 ERRORS.md：**
- 失败原因分类（API错误/数据错误/逻辑错误）
- AI无法修复的原因
- 人工处理方法

#### 效率问题沉淀（耗时超过阈值的任务）

**识别效率瓶颈：**
```sql
SELECT 
    task_name,
    AVG(duration_ms) as avg_duration,
    COUNT(*) as exec_count,
    MAX(duration_ms) as max_duration
FROM main_logs
WHERE created_at > NOW() - INTERVAL '7 days'
  AND log_type = 'prod_task'
GROUP BY task_name
HAVING AVG(duration_ms) > 300000
ORDER BY avg_duration DESC;
```

**记录到 TIPS.md：**
- 性能优化方法
- 数据库索引建议
- 批量处理策略

---

## 三、基于 task-manager 的自动化检查

### 1. task-manager 健康检查

```bash
python3 -c "
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')
from task_manager import TaskManager
tm = TaskManager()
print('✅ task-manager 连接正常')
actionable = tm.get_actionable_tasks(limit=1)
print(f'📊 待处理任务: {len(actionable)} 个')
tm.close()
"
```

### 2. 定时任务检查

```bash
# 检查 prod_task_cron 是否在运行
ps aux | grep prod_task_cron | grep -v grep

# 查看最近任务执行日志
python3 -c "
import psycopg2
conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
cur = conn.cursor()
cur.execute('''
    SELECT run_status, COUNT(*)
    FROM main_logs
    WHERE created_at > NOW() - INTERVAL '24 hours'
    GROUP BY run_status
''')
for row in cur.fetchall():
    print(f'{row[0]}: {row[1]} 次')
conn.close()
"
```

### 3. 卡死任务检测

```bash
python3 -c "
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')
from task_manager import TaskManager

tm = TaskManager()
stuck_tasks = tm.get_stuck_tasks(timeout_minutes=10)

if stuck_tasks:
    print(f'⚠️ 发现 {len(stuck_tasks)} 个卡死的任务:')
    for task in stuck_tasks:
        print(f'  - {task[\"task_name\"]} (上次更新: {task[\"last_executed_at\"]})')
else:
    print('✅ 无卡死任务')

tm.close()
"
```

---

## 四、常见问题诊断与自愈（task-manager 版本）

### 问题1：任务执行卡死

**诊断：**
```python
from task_manager import TaskManager
tm = TaskManager()
stuck_tasks = tm.get_stuck_tasks(timeout_minutes=10)
print(stuck_tasks)
tm.close()
```

**自愈：**
```python
from task_manager import TaskManager
tm = TaskManager()

for task in stuck_tasks:
    tm.kill_task_process(task['task_name'])  # 杀掉卡住的进程
    tm.update_task(
        task['task_name'],
        status='failed',
        exec_state='ERROR_FIX_PENDING'
    )
    print(f'✅ 已重置卡死任务: {task["task_name"]}')

tm.close()
```

### 问题2：子任务频繁失败

**诊断：**
```sql
SELECT 
    task_name,
    retry_count,
    last_error,
    fix_suggestion
FROM tasks
WHERE task_level = 2
  AND retry_count >= 2
ORDER BY retry_count DESC;
```

**自愈策略：**
- retry_count < 3：自动标记为 NORMAL_CRASH，下次重试
- retry_count == 3：
  - 调用 qwen-3.5-plus LLM 分析错误
  - LLM 生成解决方案
  - 创建 SOL-xxx 解决方案子任务
  - 原任务标记为 VOID
- SOL任务仍失败3次：标记为 REQUIRES_MANUAL，需人工介入

### 问题3：REQUIRES_MANUAL 任务处理

**诊断：**
```python
from task_manager import TaskManager
tm = TaskManager()

manual_tasks = tm.get_requires_manual_tasks()
if manual_tasks:
    print(f'⚠️ 发现 {len(manual_tasks)} 个需要人工处理的任务:')
    for task in manual_tasks:
        print(f'  - {task["task_name"]}: {task["fix_suggestion"]}')
        print(f'    分析: {task["analysis"][:100]}...')

tm.close()
```

**人工处理流程：**
1. 阅读任务的 fix_suggestion 和 analysis
2. 手动修复问题
3. 标记任务为 VOID（已解决）：`tm.mark_void(task_name)`
4. 系统会自动重试父任务

### 问题4：AI 自愈无法处理的问题

**AI 无法处理的问题类型：**
- Import 模块问题（subtask_executor 不在 exec() 上下文）
- 函数不存在（需要修改外部模块）
- API 配置错误（需要人工配置）
- 数据库表结构问题（需要手动迁移）

**处理方法：**
- 记录到 ERRORS.md，标记为"AI无法处理"
- 创建优化任务，将问题转化为可自动修复的格式
- 更新错误提示，提供更明确的解决步骤

---

## 五、AI 自愈机制详解

### 自愈流程图

```
子任务执行失败
    ↓
retry_count < 3?
    ├─ Yes → mark_normal_crash() → 自动重试
    │
    └─ No (已达3次)
            ↓
        调用 qwen-3.5-plus LLM 分析错误
            ↓
        LLM 生成解决方案
            ↓
        创建 SOL-xxx 解决方案子任务
            ↓
        原任务标记为 VOID
            ↓
        SOL 子任务执行
            ├─ 成功 → 父任务继续执行
            │
            └─ 仍失败（再3次）
                        ↓
                    标记为 REQUIRES_MANUAL
                        ↓
                    需要人工介入
```

### LLM 错误分析示例

**错误：**
```
ImportError: No module named 'listing_optimizer'
```

**LLM 分析：**
```
analysis: 模块 import 错误，subtask_executor 的 exec() 环境无法
访问外部模块。这不是代码逻辑错误，而是环境隔离问题。

solution:
1. 检查 listing_optimizer 模块路径是否正确
2. 确认模块是否已安装（pip install）
3. 如果是 skill 目录模块，需要添加 sys.path

建议：此问题AI无法自动修复，需人工处理。建议修改
subtask_executor 的 import 机制，或提前加载模块。

创建任务：
- 标记为 REQUIRES_MANUAL
- fix_suggestion: "修改 subtask_executor.py，提前加载模块"
```

### 创建 SOL 修复子任务

```python
from task_manager import TaskManager

tm = TaskManager()

# 为父任务创建修复子任务
tm.create_fix_subtasks('PARENT-001', [
    {
        'error': 'Step4 落库失败：psycopg2.ProgrammingError',
        'fix': '检查 SQL 语句，修复字段名错误',
        'success_criteria': 'Step4 落库成功，无数据库错误'
    },
    {
        'error': 'Step5 调用 listing-optimizer 失败',
        'fix': '验证 API 配置，检查端口 8080 是否可访问',
        'success_criteria': 'listing-optimizer 返回有效结果'
    }
])

tm.close()
```

---

## 六、日志系统（main_logs 表）

### 日志类型（log_type）

| 类型 | 说明 | 使用场景 |
|------|------|----------|
| heartbeat | 心跳日志 | 定时心跳检查 |
| dev_task | 开发任务日志 | 手动执行的开发任务 |
| prod_task | 生产任务日志 | 自动执行的生产任务 |
| cron | 定时任务日志 | prod_task_cron 执行日志 |
| error | 错误日志 | 系统错误记录 |

### 日志级别（log_level）

| 级别 | 说明 | 使用场景 |
|------|------|----------|
| DEBUG | 调试信息 | 开发调试 |
| INFO | 一般信息 | 正常执行 |
| WARN | 警告信息 | 潜在问题 |
| ERROR | 错误信息 | 执行失败 |

### 运行状态（run_status）

| 状态 | 含义 | 何时写入 |
|------|------|----------|
| running | 执行中 | 任务开始执行 |
| following | 监控中 | 任务执行中，定时检查仍在运行 |
| success | 执行成功 | 任务正常完成 |
| failed | 执行失败 | 任务失败或被判定为卡死 |
| skipped | 跳过 | 无待执行任务 |

### 日志查询示例

**查询最近错误日志：**
```sql
SELECT 
    log_type,
    task_name,
    run_message,
    created_at
FROM main_logs
WHERE log_level = 'ERROR'
  AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC
LIMIT 20;
```

**查询任务执行历史：**
```sql
SELECT 
    task_name,
    run_status,
    duration_ms,
    run_message,
    created_at
FROM main_logs
WHERE task_name = 'TASK-001'
ORDER BY created_at DESC;
```

**查询卡死任务：**
```sql
SELECT 
    t.task_name,
    t.last_executed_at,
    t.exec_state,
    MAX(ml.created_at) as last_log_time,
    NOW() - MAX(ml.created_at) as time_since_last_log
FROM tasks t
LEFT JOIN main_logs ml ON t.task_name = ml.task_name
WHERE t.exec_state = 'PROCESSING'
GROUP BY t.task_name, t.last_executed_at, t.exec_state
HAVING NOW() - MAX(ml.created_at) > INTERVAL '10 minutes';
```

---

## 七、回复约定（整合 task-manager）

| 情况 | 回复格式 | 示例 |
|------|----------|------|
| 所有检查通过 | HEARTBEAT_OK \| 待处理:0 \| 运行中:0 \| 需要人工:0 | HEARTBEAT_OK \| 待处理:0 \| 运行中:0 \| 需要人工:0 |
| 发现 P0 任务 | 发现P0任务：{task_name}，状态：{exec_state}，正在执行... | 发现P0任务：PARENT-001，状态：NEW，正在执行... |
| 任务执行成功 | 任务完成：{task_name} \| 耗时：{duration}s \| 状态：END | 任务完成：PARENT-001 \| 耗时：120s \| 状态：END |
| 任务执行失败 | 任务失败：{task_name} \| 错误：{error} \| 状态：{exec_state} | 任务失败：PARENT-001 \| 错误：连接超时 \| 状态：ERROR_FIX_PENDING |
| 需要人工处理 | 需要人工：{task_name} \| 原因：{reason} \| 建议：{suggestion} | 需要人工：PARENT-001 \| 原因：API配置错误 \| 建议：检查.env文件 |
| AI 自愈成功 | 自愈成功：{task_name} \| SOL任务：{sol_task} \| 耗时：{duration}s | 自愈成功：PARENT-001 \| SOL任务：SOL-001 \| 耗时：45s |
| 卡死任务恢复 | 卡死恢复：{task_name} \| 已杀进程 \| 重置状态：ERROR_FIX_PENDING | 卡死恢复：PARENT-001 \| 已杀进程 \| 重置状态：ERROR_FIX_PENDING |

---

## 八、配套文件（整合 task-manager）

### 数据库表

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| tasks | 任务状态管理 | task_name, exec_state, priority, task_level, retry_count, fix_suggestion |
| main_logs | 任务执行日志 | log_type, log_level, task_name, run_status, run_message, duration_ms |

### 核心脚本

| 脚本 | 路径 | 功能 |
|------|------|------|
| task_manager.py | scripts/ | 任务状态管理器 |
| logger.py | scripts/ | 统一日志记录器（写入 main_logs） |
| prod_task_cron.py | scripts/ | 定时任务执行器（每10分钟） |
| subtask_executor.py | scripts/ | 子任务执行器（AI自愈） |
| error_analyzer.py | scripts/ | LLM 错误分析器 |
| dev-heartbeat.sh | scripts/ | 心跳检查脚本 |

### 文档

| 文件 | 路径 | 用途 |
|------|------|------|
| SKILL.md | skills/task-manager/ | task-manager 技能文档 |
| HEARTBEAT.md | docs/ | 心跳机制文档（本文档） |
| AGENTS.md | docs/ | 智能执行标准 |
| KNOWLEDGE.md | docs/ | 成功案例、技巧 |
| ERRORS.md | docs/ | 失败教训、避坑指南 |
| TIPS.md | docs/ | 效率优化技巧 |
| PROJECT_STATUS.md | docs/ | 当前阻塞、进行中、已完成 |

---

## 九、使用示例

### 示例1：创建并执行任务

```python
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')
from task_manager import TaskManager

tm = TaskManager()

# 创建父任务
tm.create_task({
    'task_name': 'PARENT-001',
    'display_name': '采集1688商品',
    'priority': 'P0',
    'task_level': 1,
    'description': '从1688采集10个商品',
    'success_criteria': '成功采集10个商品，写入数据库'
})

# 创建子任务
tm.create_fix_subtasks('PARENT-001', [
    {
        'task_name': 'TASK-001-1',
        'display_name': 'Step1: 搜索商品',
        'error': '',
        'fix': '调用搜索API',
        'success_criteria': '成功获取商品列表'
    },
    {
        'task_name': 'TASK-001-2',
        'display_name': 'Step2: 解析详情',
        'error': '',
        'fix': '解析商品详情页',
        'success_criteria': '成功提取所有字段'
    },
    {
        'task_name': 'TASK-001-3',
        'display_name': 'Step3: 写入数据库',
        'error': '',
        'fix': 'INSERT products 表',
        'success_criteria': '无数据库错误'
    }
])

tm.close()

# 系统会自动执行：
# 1. 先执行所有子任务（TASK-001-1, TASK-001-2, TASK-001-3）
# 2. 如果子任务失败，自动重试3次
# 3. 如果3次都失败，调用LLM分析并创建SOL任务
# 4. 所有子任务完成后，执行父任务
```

### 示例2：查看任务状态

```python
from task_manager import TaskManager

tm = TaskManager()

# 获取任务树（父子关系）
tree = tm.get_task_tree()
print(tree)

# 获取特定任务的状态
task = tm.get_task_by_name('TASK-001-1')
print(f"状态: {task['exec_state']}")
print(f"重试次数: {task['retry_count']}")
print(f"最后错误: {task['last_error']}")

# 获取所有可执行任务
actionable = tm.get_actionable_tasks(limit=10)
for task in actionable:
    print(f"{task['task_name']} ({task['priority']}, level={task['task_level']})")

tm.close()
```

### 示例3：手动处理 REQUIRES_MANUAL 任务

```python
from task_manager import TaskManager

tm = TaskManager()

# 获取需要人工的任务
manual_tasks = tm.get_requires_manual_tasks()

for task in manual_tasks:
    print(f"任务: {task['task_name']}")
    print(f"原因: {task['fix_suggestion']}")
    print(f"分析: {task['analysis']}")
    
    # 人工处理后，标记任务为 VOID（已解决）
    # tm.mark_void(task['task_name'])
    print()

tm.close()
```

### 示例4：查询日志

```python
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='ecommerce_data',
    user='superuser',
    password='Admin123!'
)
cur = conn.cursor()

# 查询最近10条日志
cur.execute('''
    SELECT log_type, task_name, run_status, run_message, created_at
    FROM main_logs
    ORDER BY created_at DESC
    LIMIT 10
''')

for row in cur.fetchall():
    print(f"{row[4]} [{row[0]}] {row[1]}: {row[3]}")

conn.close()
```

---

## 十、最佳实践

### 1. 任务设计原则

- **单一职责**：每个任务只做一件事
- **可测试性**：定义清晰的 success_criteria
- **可重试性**：幂等设计，允许重复执行
- **可监控性**：充分的日志记录

### 2. 优先级分配原则

- **P0**：阻塞整个系统的问题（如数据库宕机、API不可用）
- **P1**：影响当前工作的问题（如某个功能不正常）
- **P2**：效率优化（如性能提升、代码重构）

### 3. AI 自愈使用建议

- **适合 AI 修复**：代码逻辑错误、参数错误、类型转换错误
- **不适合 AI 修复**：Import 问题、API 配置错误、数据库表结构问题
- **人工介入判断**：如果 AI 连续3次无法修复同一个问题，标记为 REQUIRES_MANUAL

### 4. 日志记录建议

- **关键节点**：任务开始、成功、失败、卡死
- **详细信息**：run_content 字段记录完整日志
- **实时性**：使用 log.log_line() 实时写入，避免丢失

---

*最后更新：2026-03-26 22:00*
*核心架构：task-manager 任务状态管理系统*
*适配框架：个人项目质量与效率决策框架 v2.0*
