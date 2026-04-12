# OpenClaw Agent Ops Dashboard

## 1. 目标

建设一个长期稳定的 OpenClaw Agent 运维看板系统，支持按 agent 维度隔离查看任务、工作日志、心跳日志与健康指标，并在不打断现有生产任务链的前提下，逐步把 agent 归因沉淀为正式数据模型。

系统需要解决四类核心问题：

1. 当前有哪些 agent 在运行，健康度如何。
2. 每个 agent 当前承载哪些任务，阻塞点在哪里。
3. 某个任务或任务链对应的工作日志、修复日志、通知审计和反馈产物是什么。
4. 最近心跳是否异常，异常来自任务堆积、人工介入、超时 TEMP 还是心跳采集本身。

## 2. 业务范围

### 2.1 V1 范围

1. Agent 总览。
2. Agent 详情。
3. 任务列表与任务详情。
4. 工作日志浏览。
5. 心跳日志时间线。
6. 健康分析与基础聚合指标。
7. 时间范围、状态、优先级、任务类型筛选。

### 2.2 V1 不包含

1. 任务重试。
2. 人工介入状态修改。
3. 手工触发心跳。
4. 多租户权限。
5. 可视化规则配置后台。

## 3. 技术架构

采用三段式架构，而不是仅做“前端 + 薄后端”：

1. 结构化采集与归因层。
2. 查询 API 层。
3. 前端看板层。

### 3.1 结构化采集与归因层

职责：

1. 采集心跳事件并落库。
2. 对任务、日志、心跳对象进行 agent 归因。
3. 产出按 agent 维度的稳定视图或聚合数据。

原则：

1. 不替换现有生产任务链。
2. 只补结构化写入和归因能力。
3. 短期靠规则兜底，长期改为 producer-side 直接写 `agent_id`。

### 3.2 查询 API 层

建议使用 FastAPI，负责：

1. 提供稳定 DTO。
2. 封装分页、筛选、排序、时间范围。
3. 提供 dashboard 概览、alerts、metrics。
4. 提供 SSE 任务流与日志流。

### 3.3 前端看板层

建议使用 React + Vite，职责：

1. 展示 agent 总览与详情。
2. 展示任务、日志、心跳时间线。
3. 消费 API，不直接访问数据库。

## 4. 数据模型

### 4.1 agents

表示被管理的 agent 实体。

字段建议：

1. `id`
2. `code`
3. `name`
4. `type`
5. `owner`
6. `status`
7. `description`
8. `source_system`
9. `metadata`
10. `created_at`
11. `updated_at`

### 4.2 heartbeat_events

表示结构化心跳事件。

字段建议：

1. `id`
2. `agent_id`
3. `source`
4. `heartbeat_status`
5. `summary`
6. `raw_report`
7. `payload`
8. `pending_count`
9. `processing_count`
10. `requires_manual_count`
11. `overtime_temp_count`
12. `failed_recent_count`
13. `duration_ms`
14. `host_name`
15. `report_time`
16. `created_at`

### 4.3 agent_attribution_rules

表示归因规则。

字段建议：

1. `id`
2. `rule_name`
3. `match_scope`
4. `match_type`
5. `match_field`
6. `match_expr`
7. `agent_id`
8. `priority`
9. `enabled`
10. `stop_on_match`
11. `notes`
12. `created_at`
13. `updated_at`

### 4.4 dashboard_metrics

用于缓存热点聚合指标。

字段建议：

1. `id`
2. `metric_scope`
3. `agent_id`
4. `metric_name`
5. `metric_window`
6. `metric_value`
7. `metric_payload`
8. `calculated_at`
9. `expires_at`

## 5. 归因优先级

推荐归因顺序：

1. 显式 `agent_id`。
2. 结构化字段，如 `error_type`、`skill`、`action`。
3. 父任务或根任务继承。
4. 规则表命中。
5. 类型默认映射。
6. Unknown bucket。

每次归因都应记录：

1. `attribution_source`
2. `attribution_version`
3. `matched_rule_id`

## 6. API Contract 草案

### 6.1 Agents

1. `GET /agents`
2. `GET /agents/{agentId}`
3. `GET /agents/{agentId}/tasks`
4. `GET /agents/{agentId}/logs`
5. `GET /agents/{agentId}/heartbeats`
6. `GET /agents/{agentId}/metrics`

### 6.2 Tasks

1. `GET /tasks/{taskName}`
2. `GET /tasks/{taskName}/children`
3. `GET /tasks/{taskName}/logs`

### 6.3 Dashboard

1. `GET /dashboard/overview`
2. `GET /dashboard/alerts`

### 6.4 Streams

1. `GET /stream/tasks`
2. `GET /stream/logs`

## 7. 实施顺序

1. M0: 设计冻结。
2. M1: schema 与视图。
3. M2: heartbeat 结构化落库。
4. M3: attribution engine。
5. M4: FastAPI 查询服务。
6. M5: 前端 MVP。
7. M6: 聚合指标优化。
8. M7: producer-side `agent_id` 直写。
9. M8: 控制面能力。

## 8. 当前仓库接入点

1. [scripts/task_manager.py](/root/.openclaw/workspace-e-commerce/scripts/task_manager.py) 是任务生命周期主入口。
2. [scripts/logger.py](/root/.openclaw/workspace-e-commerce/scripts/logger.py) 是工作日志主入口。
3. [scripts/dev-heartbeat.sh](/root/.openclaw/workspace-e-commerce/scripts/dev-heartbeat.sh) 是心跳调度入口。
4. [scripts/root_cause_analyzer.py](/root/.openclaw/workspace-e-commerce/scripts/root_cause_analyzer.py) 已有 `error_type`、`skill`、`action` 结构化信息，可直接复用。
5. [scripts/workflow_executor.py](/root/.openclaw/workspace-e-commerce/scripts/workflow_executor.py) 已具备 structured fix 路由能力，可作为未来 task/log producer-side attribution 的接入点。