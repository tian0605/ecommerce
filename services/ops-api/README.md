# OpenClaw Ops API

这是 OpenClaw Agent Ops Dashboard 的查询 API 骨架。

## 当前能力

1. `GET /health`
2. `GET /agents`
3. `GET /agents/{agent_id}`
4. `GET /agents/{agent_id}/tasks`
5. `GET /agents/{agent_id}/logs`
6. `GET /agents/{agent_id}/heartbeats`
7. `GET /tasks/{task_name}`
8. `GET /tasks/{task_name}/logs`
9. `GET /dashboard/overview`
10. `GET /dashboard/alerts`

## 启动方式

在仓库根目录执行：

1. 安装依赖：`/usr/bin/python3 -m pip install -r services/ops-api/requirements.txt`
2. 启动服务：`/usr/bin/python3 -m uvicorn app.main:app --app-dir services/ops-api --host 0.0.0.0 --port 8010`

## 说明

1. 当前版本默认直接读取 `v_agent_tasks`、`v_agent_logs`、`v_agent_heartbeats` 视图。
2. 当前版本使用数据库只读查询模式，未接入控制面接口。
3. 后续可以继续扩展 `/agents/{agent_id}/metrics`、SSE streams 和写操作隔离服务。