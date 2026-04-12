# OpenClaw 电商运营自动化系统（前后端）运维备份手册

---

## 1. 系统简介

本系统为一套 Shopee 电商自动化运营平台，包含前端管理界面、后端 API 服务、自动化任务执行、数据采集与分析等模块。支持一键采集、内容优化、自动发布、利润分析等完整业务流程。

---

## 2. 关键代码路径

### 前端（管理后台）
- 目录：`apps/ops-web/`
- 主要入口：`apps/ops-web/src/pages/UnifiedConfigPages.tsx`（内容与提示词配置核心页面）
- 构建产物目录：`apps/ops-web/dist/`
- 生产部署目录（nginx root）：`/var/www/ops-dashboard/`

### 后端（API服务）
- 目录：`services/ops-api/`
- 主要入口：`services/ops-api/app/`（FastAPI 应用）
- 任务调度脚本：`scripts/prod_task_cron.py`、`scripts/fix_task_cron.py`、`scripts/dev-heartbeat.sh`
- 采集/优化/发布/分析等技能：`skills/` 目录下各子模块

### 配置与脚本
- LLM/环境配置：`config/llm_config.py`、`config/config.env`
- Nginx 配置：`/etc/nginx/conf.d/ops-dashboard.conf`
- 前置条件检查脚本：`scripts/check-preconditions.sh`

---

## 3. 启动与部署方式

### 前端
1. 进入前端目录：
   ```bash
   cd apps/ops-web
   ```
2. 安装依赖：
   ```bash
   npm install
   ```
3. 构建静态文件：
   ```bash
   npm run build
   ```
4. 部署到 nginx root 目录：
   ```bash
   rsync -a --delete dist/ /var/www/ops-dashboard/
   sudo systemctl reload nginx
   ```

### 后端
1. 进入后端目录：
   ```bash
   cd services/ops-api
   ```
2. 启动服务（以 systemd 为例）：
   ```bash
   sudo systemctl restart ops-dashboard-api.service
   # 或手动开发模式
   uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
   ```

### 定时任务/自动化
- 任务调度通过 crontab/systemd 定时执行 `scripts/prod_task_cron.py`、`scripts/fix_task_cron.py` 等脚本。
- 心跳/健康检查通过 `scripts/dev-heartbeat.sh`。

---

## 4. 运维与常见操作

### 日志查看
- 后端日志：`logs/prod_task.log`、`logs/dev-heartbeat.log`
- Nginx 访问/错误日志：`/var/log/nginx/access.log`、`/var/log/nginx/error.log`

### 服务重启
- 前端：
  ```bash
  sudo systemctl reload nginx
  ```
- 后端：
  ```bash
  sudo systemctl restart ops-dashboard-api.service
  ```

### 代码同步与备份
- 推送到 GitHub：
  ```bash
  git add -A && git commit -m 'update' && git push origin master
  ```
- 拉取最新：
  ```bash
  git pull origin master
  ```

### 生产环境目录关系
- 前端静态资源：`/var/www/ops-dashboard/`
- 后端服务端口：`8010`
- Nginx 监听端口：`8088`（反向代理 API，静态资源直出）

---

## 5. 重要注意事项
- 前端构建产物必须同步到 nginx root 指定目录，否则页面不会更新。
- 后端服务如有改动需重启 systemd 服务。
- 配置变更（如 LLM、API KEY）需同步到 `config/` 目录并重启相关服务。
- 生产环境建议定期备份数据库、配置和日志。

---

## 6. 参考文档
- AGENTS.md（自动化工作流与约束）
- docs/KNOWLEDGE.md（业务知识库）
- scripts/check-preconditions.sh（前置条件检查）
- /etc/nginx/conf.d/ops-dashboard.conf（nginx 配置）

---

如需详细模块说明、二次部署或故障排查，可随时联系维护人或查阅上述文档。