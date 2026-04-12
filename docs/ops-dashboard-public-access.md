# Ops Dashboard 公网暴露说明

## 临时公网暴露版

直接暴露两个端口：

1. `5174`：前端 Vite dev server
2. `8010`：FastAPI 查询 API

启动命令：

```bash
cd /root/.openclaw/workspace-e-commerce && .venv/bin/python -m uvicorn services.ops-api.app.main:app --host 0.0.0.0 --port 8010
cd /root/.openclaw/workspace-e-commerce/apps/ops-web && npm run dev -- --host 0.0.0.0 --port 5174
```

需要在云平台安全组或防火墙放行：

1. `5174/tcp`
2. `8010/tcp`

## 正式可用版

建议只暴露一个 Nginx 入口端口，例如 `8088`：

1. `/`：静态前端页面
2. `/api/`：反向代理到本机 `127.0.0.1:8010`
3. 启用 Basic Auth

这样公网只需放行：

1. `8088/tcp`

Nginx 配置文件已落地到：

1. `/etc/nginx/conf.d/ops-dashboard.conf`
2. 仓库模板：`/root/.openclaw/workspace-e-commerce/deploy/nginx/ops-dashboard.conf`

基础认证密码文件路径：

1. `/etc/nginx/.htpasswd_ops_dashboard`

后端 systemd 服务文件：

1. `/etc/systemd/system/ops-dashboard-api.service`
2. 仓库模板：`/root/.openclaw/workspace-e-commerce/deploy/systemd/ops-dashboard-api.service`

环境变量文件：

1. `/etc/openclaw/ops-dashboard.env`
2. 仓库示例：`/root/.openclaw/workspace-e-commerce/deploy/env/ops-dashboard.env.example`

一键部署脚本：

1. `/root/.openclaw/workspace-e-commerce/scripts/deploy_ops_dashboard_public.sh`

## 当前上线方式

当前机器已切换为正式公网入口模式：

1. `8088/tcp` 由 Nginx 对外提供前端页面和 `/api/` 反向代理
2. `8010` 仅监听 `127.0.0.1`，由 `ops-dashboard-api.service` 托管
3. `5174` 开发端口已停用，不再用于对外访问

## 上线后必做

当前为了快速验证公网访问，已写入临时基础认证和临时应用账号。正式使用前必须替换：

1. `/etc/nginx/.htpasswd_ops_dashboard`
2. `/etc/openclaw/ops-dashboard.env` 中的 `OPS_API_AUTH_USERS_JSON`
3. `/etc/openclaw/ops-dashboard.env` 中的会话密钥和配置加密密钥

如果云厂商安全组未放行，仍需手工开放：

1. `8088/tcp`