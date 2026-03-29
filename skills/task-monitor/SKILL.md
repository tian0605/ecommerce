---
name: task-monitor
description: 任务运行质量监控技能。通过分析task_manager的任务执行日志和状态，提供优化建议，提升任务处理效率和质量。
triggers:
  - task_monitor
  - 任务质量
  - 任务监控
  - 分析优化
---

# Task Monitor - 任务运行质量监控

## 功能

分析任务执行日志和状态，识别问题，提供优化建议。

## 使用方法

### 分析最近任务执行

```bash
python3 scripts/task_monitor.py --analyze --days 1
```

### 生成优化报告

```bash
python3 scripts/task_monitor.py --report
```

## 监控指标

| 指标 | 说明 | 阈值 |
|------|------|------|
| 任务成功率 | 成功任务/总任务 | >80% |
| 子任务自愈率 | AI自动修复/需人工介入 | >90% |
| 平均执行时间 | 单任务耗时 | <5分钟 |
| 卡死率 | 卡死任务/总任务 | <5% |

## 任务类型（task_type）

### 概述

task_monitor 检测到的问题会自动创建 **【修复类】** 任务，优先级高于常规任务。

| 类型 | task_type值 | 优先级 | 说明 |
|------|------------|--------|------|
| 常规类 | `常规` | 中 | 已实现的功能任务 |
| 修复类 | `修复` | **最高** | 修复机制问题的任务 |
| 创造类 | `创造` | 最低 | 逻辑待定的新任务 |

### 执行顺序

```
修复类任务 > 常规类任务 > 创造类任务
```

### 与根因分析的关联

当根因分析检测到 `critical` 或 `high` 级别错误时：
1. 问题任务标记为 `error_fix_pending`
2. 自动创建 `FIX-xxx` 子任务，**task_type=修复**
3. 下次 `get_actionable_tasks()` 调用时，修复类任务优先执行

### 代码位置

```
scripts/task_manager.py
├── get_actionable_tasks()    # 按task_type优先级排序
├── create_task()             # 创建任务（支持task_type参数）
├── create_fix_subtask()      # 创建修复子任务（task_type=修复）
└── task_type 字段            # tasks表新增字段
```

---

## 根因分析（ERROR_ROOT_CAUSE_RULES）

### 功能说明

自动识别失败任务的根因，按照严重程度分级，并给出修复建议。

### 错误模式规则库

| 严重程度 | 错误模式 | 根因描述 | 修复建议 |
|---------|----------|----------|----------|
| 🔴 critical | `name 'X' is not defined` | exec环境缺少依赖模块（X） | 在subtask_executor的exec_globals中预加载常用模块：functools, logging, time, re, json |
| 🔴 critical | `ImportError: No module named 'X'` | exec环境缺少模块（X） | 在subtask_executor的exec_globals中添加缺失模块 |
| 🟠 high | `共N个问题` | 主任务有N个步骤失败 | 检查各子任务的exec_state和last_error，定位具体失败步骤 |
| 🟠 high | `LLM调用失败` | LLM API调用异常 | 检查LLM API配置、网络连接、API余额 |
| 🟠 high | `连接.*失败\|Connection.*failed` | 外部服务连接失败 | 检查服务可用性和网络连接 |
| 🟡 medium | `超时\|timeout\|Timeout` | 任务执行超时 | 增加超时时间或优化任务逻辑 |
| 🟡 medium | `数据库\|database\|PostgreSQL` | 数据库操作异常 | 检查数据库连接、权限、表结构 |
| ⚠️ warning | `from functools import wraps` | 代码使用了wraps装饰器但functools未预加载 | 确保subtask_executor预加载functools模块 |
| 🟠 high | `未找到.*编辑按钮\|button.*not.*found` | UI选择器未找到元素 | 使用tavily-search搜索Playwright/选择器解决方案 |
| 🟠 high | `Element.*Not.*Found\|点击.*失败` | 浏览器元素操作失败 | 使用tavily-search搜索Playwright等待元素解决方案 |
| 🟡 medium | `playwright\|Puppeteer\|query_selector` | 浏览器自动化相关错误 | 检查页面加载状态，增加waitForSelector等待元素 |
| 🟠 high | `write\(\).*str.*not.*int` | 文件写入类型错误 | 检查写入函数参数类型，确保传入字符串 |

### 严重程度定义

| 等级 | 含义 | 处理策略 |
|------|------|----------|
| critical | 阻塞性问题，AI自愈无法处理 | **必须人工修复**，修复后更新规则库 |
| high | 影响较大的问题 | 检查相关模块配置 |
| medium | 中等问题 | 优化超时或资源 |
| warning | 警告信息 | 关注但不紧急 |

### ⚠️ 重要：name 'X' is not defined 的上下文判断

**问题：** `name 'ListingOptimizer' is not defined` 可能被错误归因为 `subtask_executor exec_globals` 缺少模块

**实际根因：** 
- `workflow_runner.py` 的 `sys.path` 不包含模块所在路径
- `llm_config.py` 缺少向后兼容的变量导出

**判断方法：**
| 上下文 | 错误模式 | 真正根因 |
|--------|----------|----------|
| subtask_executor 执行修复代码时 | `name 'wraps' is not defined` | exec_globals 缺少 functools |
| workflow_runner 运行时 | `name 'ListingOptimizer' is not defined` | sys.path 路径缺失 / llm_config 导出缺失 |

**经验：** 当错误发生在**工作流执行**而非修复循环时，应该检查目标脚本的导入路径，而非 subtask_executor。

### 代码位置

```
scripts/task_monitor.py
├── ERROR_ROOT_CAUSE_RULES     # 根因规则列表
├── analyze_error_root_cause() # 单条错误根因分析
└── get_root_cause_stats()     # 批量根因统计
```

### 使用示例

```python
from task_monitor import analyze_error_root_cause

result = analyze_error_root_cause("执行错误: name 'wraps' is not defined")
# {
#     'matched': True,
#     'severity': 'critical',
#     'root_cause': 'exec环境缺少依赖模块（wraps）',
#     'fix': '在subtask_executor的exec_globals中预加载常用模块...',
#     'pattern': r"name '(\w+)' is not defined"
# }
```

## 优化方向

1. **流程优化**：减少步骤、并行处理
2. **错误自愈**：提高自愈成功率
3. **资源利用**：减少等待、优化超时
4. **日志质量**：更清晰的日志便于诊断

## 最佳实践

### 新增根因规则

当发现新的错误模式时，按以下格式添加到 `ERROR_ROOT_CAUSE_RULES`：

```python
(
    r"新的错误正则表达式",
    "severity",           # critical/high/medium/warning
    "根因描述（使用{}作为占位符）",
    "具体修复建议"
)
```

### 根因分析优先级

1. **critical问题**：立即处理，修复后验证
2. **high问题**：当天处理
3. **medium问题**：本周处理
4. **warning问题**：按需处理

### 何时用FIX循环，何时直接修复

**适合FIX循环的场景：**
- 代码逻辑错误（如类型转换、参数检查）
- 可以通过修改函数逻辑解决的错误
- subtask_executor 自身的问题

**不适合FIX循环，需要直接修复的场景：**
- sys.path 路径配置缺失
- 模块导入结构问题（跨文件的导入依赖）
- 配置文件缺少变量导出
- 需要同时修改多个源文件才能解决的问题

**判断方法：** 如果同一个 `name 'X' is not defined` 错误反复出现且FIX循环无法解决，应该考虑直接检查目标脚本的导入路径。

---

## 增强分析能力

### 集成新技能

task_monitor已集成以下技能进行增强分析：

#### 1. tavily-search（AI搜索）

**用途：** 当根因分析检测到浏览器/UI相关错误时，自动搜索解决方案

**触发条件：**
- `button.*not.*found`
- `selector.*not.*found`
- `Element.*Not.*Found`

**使用方式：**
```python
from task_monitor import search_solution_with_tavily
result = search_solution_with_tavily("Playwright button selector not found fix")
```

**配置：** 需要在 `config/config.env` 中配置 `TAVILY_API_KEY`

#### 2. agent-browser（浏览器诊断）

**用途：** 直接诊断页面元素，验证选择器是否正确

**触发条件：**
- UI选择器错误
- 元素未找到

**使用方式：**
```python
from task_monitor import diagnose_with_agent_browser
result = diagnose_with_agent_browser("https://example.com", "#submit-button")
```

**配置：** 需要安装 `agent-browser` CLI

### 增强流程

```
错误检测 → 根因分析 → 匹配增强技能？
    │
    ├─ Yes: 调用 tavily-search / agent-browser
    │
    └─ No: 返回标准修复建议
```

### 适用场景

| 场景 | 使用技能 |
|------|---------|
| Playwright选择器问题 | tavily-search + agent-browser |
| 浏览器元素等待问题 | tavily-search |
| UI交互超时 | tavily-search |
| 页面截图诊断 | agent-browser screenshot |

---

*最后更新：2026-03-27*
