# 远程服务器调试指南

**服务器 IP：** 43.139.213.66  
**项目路径：** `/root/.openclaw/workspace-e-commerce`  
**更新日期：** 2026-03-30

---

## 一、快速开始（首次初始化）

在远程服务器上执行一键初始化脚本：

```bash
# 方法 A：SSH 登录后执行
ssh root@43.139.213.66
bash /root/.openclaw/workspace-e-commerce/scripts/setup-remote-server.sh

# 方法 B：本地一键推送（服务器已绑定 GitHub）
ssh root@43.139.213.66 'bash -s' < scripts/setup-remote-server.sh
```

脚本会自动完成：
- ✅ 安装系统依赖（git, python3, postgresql-client 等）
- ✅ 安装 Python 依赖（psycopg2, playwright 等）
- ✅ 创建目录结构
- ✅ 克隆/更新代码
- ✅ 配置 crontab 定时任务
- ✅ 检查 SSH 公钥（GitHub 绑定）
- ✅ 前置条件检查

---

## 二、日常代码同步（已绑定 GitHub）

每次代码有更新后，在服务器上执行：

```bash
cd /root/.openclaw/workspace-e-commerce
git pull origin master
```

或者用 SSH 从本地触发：

```bash
ssh root@43.139.213.66 'cd /root/.openclaw/workspace-e-commerce && git pull origin master'
```

---

## 三、配置说明

### 3.1 核心配置文件

`config/config.env` 是所有模块的统一配置源：

```ini
# 数据库（在服务器本机运行时保持 localhost）
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ecommerce_data
DB_USER=superuser
DB_PASSWORD=<your_db_password>

# LLM API
LLM_API_KEY=<your_api_key>
LLM_BASE_URL=https://dashscope.aliyuncs.com/...

# 飞书
FEISHU_WEBHOOK_URL=https://open.feishu.cn/...

# 本地 1688 服务（通过 SSH 隧道转发到本地 Windows 机器）
LOCAL_1688_URL=http://127.0.0.1:8080
```

### 3.2 如何生效

所有 Python 脚本通过 `scripts/load_env.py` 自动读取 `config/config.env`：

```python
from load_env import get_db_config, get_env

# 获取数据库配置
db = get_db_config()
conn = psycopg2.connect(**db)

# 获取单个配置项
webhook = get_env('FEISHU_WEBHOOK_URL')
```

---

## 四、前置条件检查

每次调试前运行：

```bash
bash /root/.openclaw/workspace-e-commerce/scripts/check-preconditions.sh
```

三个前置条件：

| 条件 | 检查方式 | 解决方案 |
|------|----------|----------|
| 妙手 ERP Cookies | 文件存在且 < 24小时 | 重新导出并上传 |
| 本地 1688 服务 | `curl http://127.0.0.1:8080/health` | 重建 SSH 隧道 |
| SSH 隧道 | `ss -tlnp \| grep 8080` | 重建隧道（见下） |

### SSH 隧道（将 Windows 本地服务转发到服务器）

在**本地 Windows** 机器上执行：

```bash
# 将本地 Windows 的 1688 服务（端口 8080）转发到远程服务器
ssh -R 8080:127.0.0.1:8080 root@43.139.213.66 -N
```

---

## 五、常用调试命令

### 单步测试

```bash
# 测试 miaoshou-updater（核心发布模块）
cd /root/.openclaw/workspace-e-commerce
python3 skills/miaoshou-updater/updater.py --product-id 1026137274944 --headed

# 测试 product-storer（数据落库）
python3 skills/product-storer/storer.py --alibaba-id 1031400982378

# 测试 listing-optimizer（LLM 优化）
python3 skills/listing-optimizer/optimizer.py --product-id AL000100100260000001

# 检查数据库
PGPASSWORD=$(grep DB_PASSWORD /root/.openclaw/workspace-e-commerce/config/config.env | cut -d= -f2) psql -U superuser -d ecommerce_data -c "SELECT id, status FROM products ORDER BY id DESC LIMIT 5;"
```

### 查看日志

```bash
# 实时日志
tail -f /root/.openclaw/workspace-e-commerce/logs/prod_task_cron.log
tail -f /root/.openclaw/workspace-e-commerce/logs/dev-heartbeat.log

# 查看最近任务状态
PGPASSWORD=$(grep DB_PASSWORD /root/.openclaw/workspace-e-commerce/config/config.env | cut -d= -f2) psql -U superuser -d ecommerce_data -c \
  "SELECT task_name, exec_state, updated_at FROM tasks ORDER BY updated_at DESC LIMIT 10;"
```

### 重置 & 修复

```bash
# 重置卡住的任务
PGPASSWORD=$(grep DB_PASSWORD /root/.openclaw/workspace-e-commerce/config/config.env | cut -d= -f2) psql -U superuser -d ecommerce_data -c \
  "UPDATE tasks SET exec_state='PENDING' WHERE exec_state='PROCESSING' AND updated_at < NOW() - INTERVAL '30 minutes';"

# 手动触发心跳
bash /root/.openclaw/workspace-e-commerce/scripts/dev-heartbeat.sh
```

---

## 六、妙手 Cookies 更新

Cookies 每 24 小时过期。过期后需要在**本地 Windows** 浏览器重新导出并上传：

1. 打开 Chrome，登录妙手 ERP
2. 使用 EditThisCookie 插件导出 → 保存为 `miaoshou_cookies.json`
3. 上传到服务器：

```bash
scp miaoshou_cookies.json root@43.139.213.66:/home/ubuntu/.openclaw/skills/miaoshou-collector/
```

---

## 七、目录结构

```
/root/.openclaw/workspace-e-commerce/
├── config/
│   ├── config.env          ← 核心配置（DB、API Key 等）
│   └── llm_config.py       ← LLM 模型配置
├── scripts/
│   ├── load_env.py         ← 统一配置加载器（新增）
│   ├── setup-remote-server.sh ← 初始化脚本（新增）
│   ├── task_manager.py     ← 任务管理器
│   ├── logger.py           ← 日志记录器
│   ├── check-preconditions.sh ← 前置条件检查
│   └── ...
├── skills/
│   ├── miaoshou-updater/   ← ERP 发布
│   ├── miaoshou_updater/
│   ├── product-storer/     ← 数据落库
│   ├── listing-optimizer/  ← LLM 优化
│   └── ...
└── logs/
    ├── prod_task_cron.log
    └── dev-heartbeat.log
```

---

## 八、常见问题

### Q: `psycopg2` 未安装
```bash
pip3 install psycopg2-binary
```

### Q: Playwright 未安装
```bash
pip3 install playwright && python3 -m playwright install chromium --with-deps
```

### Q: 数据库连接拒绝
1. 确认 PostgreSQL 运行：`systemctl status postgresql`
2. 确认数据库存在：`PGPASSWORD=$(grep DB_PASSWORD /root/.openclaw/workspace-e-commerce/config/config.env | cut -d= -f2) psql -U superuser -l`
3. 检查 `config.env` 中的 `DB_HOST`

### Q: SSH 公钥未绑定 GitHub
```bash
cat ~/.ssh/id_ed25519.pub
# 将输出内容粘贴到 https://github.com/settings/keys
```
