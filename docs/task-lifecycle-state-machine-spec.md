# 任务生命周期状态机规范

生成时间: 2026-04-06
适用范围: CommerceFlow 任务系统
状态: Draft v1

---

## 1. 文档目的

本文档用于定义 CommerceFlow 的统一任务生命周期规范，把现有任务系统从“可执行任务队列”升级为“可治理、可回退、可复盘”的阶段化状态机。

本规范同时覆盖以下对象：

- 常规任务
- 临时任务（TEMP）
- 修复任务（FIX）
- 创造任务

本文档聚焦三类内容：

1. 业务阶段状态机定义
2. 数据库与任务管理接口映射
3. 调度器与执行器职责边界

---

## 2. 设计目标

当前任务系统已经具备以下能力：

- 基于 `tasks` 表的任务存储
- 基于 `exec_state` 的执行状态管理
- `prod_task_cron` 与 `fix_task_cron` 的异步调度
- `workflow_executor`、`temp_task_executor`、`subtask_executor` 的执行链路
- `progress_checkpoint`、`notification_audit`、`error_signature` 的补充能力

现阶段的主要问题不是“不能执行”，而是“阶段语义不清”。

典型表现如下：

- `status`、`exec_state`、`plan`、`analysis`、`progress_checkpoint` 承担了部分重叠语义
- 调度器承担了过多业务判断
- 审查、测试、发布、反思尚未被统一纳入任务生命周期
- FIX 任务和主任务之间存在“能修复但难回写”的断层
- 发布成功与实际业务成功之间仍可能出现假阳性

因此，本规范的目标是：

1. 统一任务生命周期语言
2. 拆分业务阶段与执行状态
3. 为每个阶段定义产物、闸门、回退规则和责任主体
4. 为后续数据库、TaskManager、cron 重构提供统一依据

---

## 3. 核心设计原则

### 3.1 双层状态机原则

任务状态分为两层：

1. 业务阶段 `stage`
2. 执行状态 `exec_state`

两者的职责必须严格分离。

`stage` 只回答：

- 任务当前位于哪个业务阶段
- 下一步应该做什么
- 是否允许进入下一个阶段

`exec_state` 只回答：

- 任务当前是否正在执行
- 任务是否可被 cron 拾取
- 任务是否需要修复或人工介入

### 3.2 阶段优先于脚本原则

执行器不是生命周期的定义者，只是阶段产物的生产者。

例如：

- `workflow_executor` 负责 build 阶段执行
- `temp_task_executor` 负责 TEMP 任务的 plan/build 试点执行
- `task_monitor` 负责 retrospective 阶段的根因分析输入

任务是否推进阶段，不能由执行器自行宣布，而应由任务状态机统一判断。

### 3.3 闸门优先原则

阶段之间不能直接跳转，必须满足对应闸门条件。

例如：

- 计划未完成，不能直接进入构建
- 审查未通过，不能进入测试
- 测试未通过，不能进入发布
- 发布未核验，不能进入反思

### 3.4 回退优先于终止原则

任务失败不是唯一去向。系统应优先判断：

1. 是否可以回退到上一个业务阶段
2. 是否应生成 FIX 子任务
3. 是否需要人工介入

---

## 4. 双层状态机定义

### 4.1 业务阶段 `stage`

业务阶段固定为以下七个值：

| 阶段值 | 中文名称 | 含义 |
|---|---|---|
| `idea` | 构思 | 明确问题、目标、边界、优先级 |
| `plan` | 计划 | 形成方案、依赖、风险、验证方式 |
| `build` | 构建 | 执行实现、产出构建结果与中间数据 |
| `review` | 审查 | 对实现、规则、数据进行审查 |
| `test` | 测试 | 对行为与结果进行验证 |
| `release` | 发布 | 执行发布并完成发布后核验 |
| `retrospective` | 反思 | 沉淀 RCA、SOP、长期债务 |

### 4.2 执行状态 `exec_state`

执行状态继续沿用现有体系：

| 状态值 | 含义 |
|---|---|
| `new` | 新建，待执行 |
| `processing` | 执行中 |
| `end` | 已完成 |
| `error_fix_pending` | 待修复 |
| `normal_crash` | 系统异常，可重试 |
| `requires_manual` | 需要人工处理 |
| `void` | 作废 |

### 4.3 状态组合规则

允许存在如下组合：

- `current_stage='build'` + `exec_state='processing'`
- `current_stage='review'` + `exec_state='new'`
- `current_stage='release'` + `exec_state='error_fix_pending'`
- `current_stage='retrospective'` + `exec_state='end'`

不推荐出现如下情况：

- `current_stage='test'` 但没有 review 结论
- `current_stage='release'` 但没有 test 结果
- `exec_state='end'` 但 `current_stage` 仍停留在 `build`

---

## 5. 状态表

| Stage | 业务目标 | 进入条件 | 阶段产物 | 退出条件 | 默认下一阶段 | 默认失败去向 | 责任主体 |
|---|---|---|---|---|---|---|---|
| `idea` | 明确问题与目标 | 需求产生或任务被创建 | 问题定义、目标、范围、优先级 | 目标和范围明确 | `plan` | 留在本阶段或 `requires_manual` | 发起者 / 主代理 |
| `plan` | 形成可执行方案 | 已完成构思 | `success_criteria`、依赖、风险、验证方式、预估时长 | 方案可执行 | `build` | 回退 `idea` 或阻塞 | 计划代理 |
| `build` | 执行方案并产出实现结果 | 计划通过 | 构建产物、日志、checkpoint、步骤数据 | 有可审查产物 | `review` | 回退 `plan` 或生成 FIX | 执行器 |
| `review` | 审查实现质量与业务规则 | 已有构建产物 | 审查结论、问题清单、严重级别 | `pass` 或 `conditional_pass` | `test` | 回退 `build` 或生成 FIX | 审查代理 / 规则系统 |
| `test` | 验证行为与结果 | 审查通过 | 测试矩阵、测试结果、失败样本 | 最低测试集通过 | `release` | 回退 `build`/`review` 或生成 FIX | 测试执行器 |
| `release` | 执行发布并校验真实结果 | 测试通过 | 发布记录、校验结果、回执 | 发布后真值核验通过 | `retrospective` | 回退 `test`/`build`、生成 FIX 或人工介入 | 发布执行器 |
| `retrospective` | 沉淀经验与根因 | 发布完成或任务终止 | RCA、SOP、Debt、后续动作 | 复盘结论完整 | `end` | 留在本阶段 | task_monitor / 知识沉淀器 |

---

## 6. 迁移表

| From | To | Trigger | Preconditions | Success Action | Failure Action |
|---|---|---|---|---|---|
| `idea` | `plan` | 目标确认 | 目标、范围、优先级明确 | 建立计划骨架 | 留在 `idea` |
| `plan` | `build` | 方案通过 | `success_criteria`、依赖、风险、验证方式齐全 | 允许执行 | 回退 `idea` 或阻塞 |
| `build` | `review` | 构建完成 | 有构建产物、checkpoint、步骤数据 | 送入审查 | 回退 `plan` 或创建 FIX |
| `review` | `test` | 审查通过 | 无 P0/P1 未解决问题，或满足 `conditional_pass` 附加条件 | 进入测试 | 回退 `build` 或创建 FIX |
| `test` | `release` | 测试通过 | 最低测试集通过；高风险路径已通过 no-publish/save-only | 允许发布 | 回退 `build`/`review` 或创建 FIX |
| `release` | `retrospective` | 发布核验通过 | 发布真值、DB 状态、必要同步结果已确认 | 进入复盘 | 回退 `test`/`build`，或创建 FIX，或人工处理 |
| `retrospective` | `end` | 复盘完成 | RCA/SOP/Debt 已形成归档结论 | 标记完成 | 留在 `retrospective` |

补充规则：

- `review`、`test`、`release` 是高风险阶段，必须允许失败后回退
- `release` 不允许“执行成功即完成”，必须经过 verify
- `retrospective` 不是可选阶段，是任务生命周期的正式组成部分

---

## 7. 闸门表

| 迁移 | 必须满足的闸门 | 主要证据来源 |
|---|---|---|
| `idea -> plan` | 目标明确、范围明确、优先级明确 | `description`、`analysis`、任务模板 |
| `plan -> build` | `success_criteria`、依赖、风险、验证方式、预估时长齐全 | `plan`、`success_criteria`、`expected_duration` |
| `build -> review` | 有实现产物、运行日志、checkpoint、上游数据 | `progress_checkpoint`、`workflow_data` |
| `review -> test` | 无 P0/P1 未关闭问题，或 `conditional_pass` 条件已满足 | review 结果与问题列表 |
| `test -> release` | 最低测试集通过，发布前仿真通过 | test 结果、仿真记录 |
| `release -> retrospective` | 发布后真值核验通过，不存在假阳性 | 发布回执、站点状态、DB 状态、同步结果 |
| `retrospective -> end` | RCA/SOP/Debt 至少一项完成 | retrospective 输出 |

建议实现要求：

1. 所有闸门统一由 `TaskManager.check_stage_gate()` 判断
2. cron 和执行器不能绕过闸门直接推进阶段
3. 闸门应返回结构化结果，而不是只返回布尔值

---

## 8. 异常表

| 异常类型 | 典型信号 | 所属阶段 | 默认去向 | 自动恢复 | 是否创建 FIX | 是否需要人工 |
|---|---|---|---|---|---|---|
| `validation_failed` | 必填字段缺失、禁用词、结构不合规 | `review` / `test` | 回退 `build` | 否 | 是 | 否 |
| `quality_failed` | 审查不通过、数据异常、价格异常 | `review` | 回退 `build` | 否 | 是 | 视情况 |
| `system_crash` | 导入失败、进程崩溃、运行时异常 | 任意执行阶段 | `normal_crash` | 是 | 否 | 否 |
| `external_dependency_failure` | 第三方接口失败、Cookies 过期、本地服务不可用 | `build` / `release` | `error_fix_pending` 或 `requires_manual` | 部分 | 是 | 可能 |
| `timeout_overtime` | 长时间无日志、TEMP 超时 | `build` / `release` | 重新激活或回退 | 是 | 否 | 否 |
| `publish_verify_failed` | 脚本成功但实际上未发布 | `release` | 回退 `test`/`build` | 否 | 是 | 可能 |
| `duplicate_fix` | 相同错误被重复创建 FIX | 任意 | 合并到既有 FIX | 是 | 否 | 否 |
| `manual_required` | 平台前端异常、人机验证、权限阻塞 | 任意 | `requires_manual` | 否 | 否 | 是 |

异常处理优先级：

1. 先判断是否可自动恢复
2. 再判断是否应创建 FIX
3. 最后才转人工处理

---

## 9. 任务类型映射

### 9.1 常规任务

默认完整走七阶段：

`idea -> plan -> build -> review -> test -> release -> retrospective -> end`

### 9.2 临时任务（TEMP）

TEMP 任务允许从 `idea` 或 `plan` 起步。

推荐规则：

- 只有描述，没有明确成功标准时，初始化为 `idea`
- 已给出成功标准、范围、预估时长时，初始化为 `plan`

TEMP 任务即使是开放式任务，也不能绕过 `review`、`test`、`retrospective` 的治理要求。

### 9.3 修复任务（FIX）

FIX 任务通常从 `build` 起步，但必须记录 `source_stage`，用于在修复完成后回写原任务来源阶段。

例如：

- 原任务在 `review` 失败，生成 FIX
- FIX 完成后，原任务回到 `review` 或推进 `test`

FIX 任务不是独立世界，必须服务于原任务生命周期。

### 9.4 创造任务

创造任务允许在 `idea`、`plan` 停留更久，但进入 `build` 后必须遵守与其他任务相同的闸门规则。

---

## 10. 数据库映射草案

### 10.1 tasks 表新增字段建议

| 字段名 | 类型 | 说明 |
|---|---|---|
| `current_stage` | TEXT | 当前业务阶段 |
| `stage_status` | TEXT | 当前阶段内部状态 |
| `stage_started_at` | TIMESTAMP | 当前阶段开始时间 |
| `stage_updated_at` | TIMESTAMP | 当前阶段最近更新时间 |
| `stage_owner` | TEXT | 当前阶段责任主体 |
| `stage_result` | TEXT | 当前阶段结论摘要 |
| `blocked_reason` | TEXT | 阻塞原因 |
| `next_stage` | TEXT | 预期下一阶段 |
| `source_stage` | TEXT | FIX 子任务来源阶段 |
| `stage_context` | JSONB | 阶段上下文 |

### 10.2 建议复用的既有字段

| 字段名 | 用途 |
|---|---|
| `success_criteria` | plan 阶段闸门证据 |
| `plan` | 计划正文 |
| `analysis` | idea / retrospective 分析正文 |
| `expected_duration` | plan / TEMP 预估时长 |
| `progress_checkpoint` | build 阶段断点 |
| `notification_*` | 通知审计 |
| `error_signature` | 错误聚类与 FIX 去重 |

### 10.3 stage_context 结构建议

```json
{
  "idea": {
    "summary": "",
    "artifacts": [],
    "issues": [],
    "decision": "",
    "entered_at": null,
    "completed_at": null,
    "actor": ""
  },
  "plan": {
    "summary": "",
    "artifacts": [],
    "issues": [],
    "decision": "",
    "entered_at": null,
    "completed_at": null,
    "actor": ""
  },
  "build": {
    "summary": "",
    "artifacts": [],
    "issues": [],
    "decision": "",
    "entered_at": null,
    "completed_at": null,
    "actor": ""
  },
  "review": {
    "summary": "",
    "artifacts": [],
    "issues": [],
    "decision": "",
    "entered_at": null,
    "completed_at": null,
    "actor": ""
  },
  "test": {
    "summary": "",
    "artifacts": [],
    "issues": [],
    "decision": "",
    "entered_at": null,
    "completed_at": null,
    "actor": ""
  },
  "release": {
    "prepare": {},
    "execute": {},
    "verify": {},
    "summary": "",
    "artifacts": [],
    "issues": [],
    "decision": "",
    "entered_at": null,
    "completed_at": null,
    "actor": ""
  },
  "retrospective": {
    "rca": {},
    "sop": {},
    "debt": {},
    "summary": "",
    "artifacts": [],
    "issues": [],
    "decision": "",
    "entered_at": null,
    "completed_at": null,
    "actor": ""
  }
}
```

### 10.4 workflow_data 边界说明

边界建议如下：

- `workflow_data` 保存运行明细与步骤输出
- `stage_context` 保存阶段治理所需摘要和证据引用

不要把全量运行数据复制到 `stage_context` 中。

---

## 11. TaskManager 接口草案

### 11.1 现有接口职责收口

现有接口保留，但职责限定为执行态与兼容逻辑：

- `create_task`
- `create_temp_task`
- `update_task`
- `mark_start`
- `mark_executing`
- `mark_end`
- `mark_error_fix_pending`
- `mark_requires_manual`
- `mark_normal_crash`
- `update_checkpoint`
- `reactivate_temp_task`
- `create_fix_subtask`
- `create_fix_subtasks`
- `reset_task`

### 11.2 新增阶段接口建议

```python
def initialize_stage(task_name: str, stage: str = 'idea') -> bool: ...
def set_stage(task_name: str, stage: str, status: str = 'ready') -> bool: ...
def advance_stage(task_name: str, expected_from: str, target_stage: str) -> dict: ...
def fail_stage(task_name: str, stage: str, reason: str, error_type: str) -> dict: ...
def reopen_stage(task_name: str, target_stage: str, reason: str) -> bool: ...
def record_stage_artifact(task_name: str, stage: str, artifact_type: str, payload: dict) -> bool: ...
def check_stage_gate(task_name: str, from_stage: str, to_stage: str) -> dict: ...
def attach_stage_issue(task_name: str, stage: str, severity: str, issue_type: str, payload: dict) -> bool: ...
def resolve_stage_issue(task_name: str, stage: str, issue_id: str) -> bool: ...
def set_stage_blocked(task_name: str, reason: str, next_retry_at=None) -> bool: ...
def sync_stage_from_exec_outcome(task_name: str, exec_result: dict) -> dict: ...
def get_runnable_tasks_by_stage(limit: int = 10, allowed_stages=None, task_types=None) -> list[dict]: ...
```

### 11.3 接口职责分层规则

必须遵守以下规则：

1. `mark_*` 接口不直接推进业务阶段
2. `advance_stage()` 是唯一合法阶段迁移入口
3. `check_stage_gate()` 是唯一闸门判断入口
4. `fail_stage()` 负责判断回退、FIX 或 manual
5. `create_fix_subtask()` 必须记录 `source_stage`
6. 父任务完成判断不能只依赖子任务 `end/void`

### 11.4 执行结果回写规则

建议统一由 `sync_stage_from_exec_outcome()` 处理：

- build 成功：记录 artifact，尝试推进到 `review`
- review 成功：推进到 `test`
- test 成功：推进到 `release`
- release 成功：只记录 `release.execute`，不能直接结束
- release verify 成功：推进到 `retrospective`

---

## 12. cron 职责边界

### 12.1 prod_task_cron

重构后的 `prod_task_cron` 只负责：

1. 查询可执行任务
2. 检测 `processing` 卡死
3. 选择执行器
4. 落运行日志
5. 调用 `sync_stage_from_exec_outcome()` 回写结果

不再负责：

- 判断父任务是否该推进
- 判断发布是否成功
- 判断主任务是否应直接完成
- 直接修改复杂业务阶段语义

### 12.2 fix_task_cron

重构后的 `fix_task_cron` 只负责：

1. 查询修复任务
2. 检测修复任务卡死
3. 调用修复执行器
4. 回传执行结果给 TaskManager

不再负责：

- 决定原任务进入哪个阶段
- 直接宣布原任务修复完成
- 用 FIX 自身结束态替代主任务阶段回写

### 12.3 heartbeat 与 TEMP 恢复

heartbeat 继续负责：

- 前置条件检查
- 超时 TEMP 重新激活
- 总体健康汇总

新增建议：

- 各阶段队列数量统计
- blocked 数量统计
- manual 数量统计
- release verify 失败数量统计

TEMP 超时恢复要求：

- 保留 `current_stage`
- 保留 `stage_context`
- 保留 `progress_checkpoint`
- 不允许粗暴重置为初始阶段

---

## 13. 执行器角色定义

| 组件 | 新角色定义 |
|---|---|
| `workflow_executor.py` | build 阶段执行器 |
| `temp_task_executor.py` | TEMP 的 plan/build 试点执行器 |
| `subtask_executor.py` | FIX / build 执行器 |
| `task_monitor.py` | retrospective 阶段分析器 |

统一约束：

执行器只返回：

- 执行结果 `exec outcome`
- 产物 `artifacts`
- 问题 `issues`
- 建议动作 `recommendations`

执行器不直接终结业务阶段。

---

## 14. 增量实施建议

### 第一阶段

- 新增 `tasks` 阶段字段
- 新增 `stage_context`
- 新增阶段接口空壳
- 不改变现有 cron 主行为

### 第二阶段

- TEMP 任务接入 `idea/plan/build` 阶段
- Step 6 发布链路接入 `review/test/release`
- 引入 `release.verify` 校验

### 第三阶段

- `get_actionable_tasks()` 逐步转调 `get_runnable_tasks_by_stage()`
- `prod_task_cron` 与 `fix_task_cron` 下沉业务判断到 TaskManager
- FIX 回写原任务来源阶段

### 第四阶段

- retrospective 自动化
- retrospective batch 允许自动纳入 `requires_manual` 且尚未进入 `retrospective` 的任务，用于补齐 RCA 与 Debt
- 如果一个失败父任务下面还有 `requires_manual` 子任务，batch 可能在一次运行中同时处理父任务和子任务，因此 `processed=2` 这类结果不一定是异常
- retrospective batch 的预期筛选集合应理解为“待复盘对象”，而不是“仅统计显式处于 retrospective 阶段的父任务数”
- 阶段指标统计
- heartbeat 与 dashboard 接入阶段维度数据

---

## 15. 验收标准

本规范落地后，至少应满足以下验收标准：

1. 任意任务都能清楚回答“当前阶段是什么、下一步是什么、为什么不能前进”
2. `exec_state` 与 `stage` 不再混用
3. 审查未通过的任务不能进入测试
4. 测试未通过的任务不能进入发布
5. 发布执行成功但核验失败的任务不能被视为完成
6. FIX 任务完成后能准确回写原任务的来源阶段
7. TEMP 超时恢复不会丢失当前阶段与上下文
8. retrospective 成为任务生命周期的一部分，而不是可有可无的附属记录

---

## 16. 后续配套文档建议

建议后续配套补充以下文档：

1. 数据库迁移 SQL 草案
2. TaskManager 接口实现说明
3. prod_task_cron / fix_task_cron 重构说明
4. Step 6 发布校验规范
5. retrospective 输出模板

---

## 17. 结论

本规范的核心不是新增更多任务类型，而是为现有任务系统补齐生命周期治理能力。

一旦 `stage`、闸门、回退、FIX 回写、release verify、retrospective 这几条线真正落地，当前任务系统将从“能跑”演进到“可控、可审计、可持续优化”。