# 远程服务器环境验证指南

**适用场景：** 首次在远程 Linux 服务器上部署并验证 CommerceFlow 项目

---

## 一、准备清单（开始前确认）

| 准备项 | 说明 | 是否完成 |
|--------|------|----------|
| 服务器 SSH 访问 | 确保可以 SSH 登录目标服务器 | ☐ |
| 代码已推送到 master | `git push origin master` | ☐ |
| 妙手ERP Cookies | 从本地 Chrome 导出 JSON 格式 Cookies | ☐ |
| 本地1688服务运行中 | 本地机器已启动 `local-1688-weight-server.py` | ☐ |
| MobaXterm/SSH 隧道 | 本地 8080 → 远程 8080 的端口转发已建立 | ☐ |

---

## 二、服务器环境初始化（首次部署）

### 2.1 拉取代码

```bash
# 克隆或拉取最新代码
git clone https://github.com/tian0605/ecommerce.git /root/.openclaw/workspace-e-commerce
# 或已有项目时拉取最新
cd /root/.openclaw/workspace-e-commerce && git pull origin master
```

### 2.2 运行一键初始化脚本

```bash
cd /root/.openclaw/workspace-e-commerce
bash scripts/setup-remote-server.sh
```

该脚本将自动完成：
- 系统依赖检查（Python3、psql）
- 安装 Python 依赖（psycopg2、playwright、requests 等）
- 安装 Playwright Chromium 浏览器
- 创建必要目录结构
- 验证数据库连接
- 检查 Cookies 文件和 SSH 隧道状态

### 2.3 上传妙手 Cookies

在本地机器用 Chrome 登录妙手ERP，通过 EditThisCookie 等插件导出 JSON，然后上传：

```bash
# 从本地 scp 上传（在本地机器执行）
scp miaoshou_cookies.json ubuntu@<server-ip>:/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json
```

---

## 三、运行前置条件检查

每次开始工作流前，必须先通过以下检查（5项全部通过）：

```bash
bash scripts/check-preconditions.sh
```

**预期输出示例：**

```
=== CommerceFlow 工作流前置条件检查 ===

[条件1] 妙手ERP Cookies
  ✅ Cookies文件存在 (更新于 2 小时前)

[条件2] 本地1688服务
  ✅ 本地服务正常
     响应: {"service":"1688-weight-fetcher","status":"ok"}

[条件3] SSH隧道
  ✅ 隧道已建立 (127.0.0.1:8080 LISTEN)

[条件4] Python 关键依赖
  ✅ psycopg2
  ✅ playwright
  ✅ requests

[条件5] 数据库连通性
  ✅ 数据库连接成功 (superuser@localhost/ecommerce_data)

=== 检查完成 ===

  通过: 5 项  失败: 0 项

  ✅ 所有前置条件满足，可以开始工作流。
```

---

## 四、各模块验证步骤

### 4.1 miaoshou-collector（采集模块）

```bash
cd /root/.openclaw/workspace-e-commerce
python3 skills/miaoshou-collector/collector.py \
  --url "https://detail.1688.com/offer/<product-id>.html"
```

**验证点：**
- 商品进入妙手ERP Shopee 采集箱
- 无 Cookies 过期报错

### 4.2 collector-scraper（采集箱提取）

```bash
python3 skills/collector-scraper/scraper.py --product-id <id>
```

**验证点：**
- 返回货源ID、标题、SKU列表、图片URL

### 4.3 local-1688-weight（重量尺寸）

```bash
curl http://127.0.0.1:8080/weight?product_id=<alibaba_product_id>
```

**验证点：**
- 返回 `success: true`，包含 `weight_g`、`length_cm` 等字段

### 4.4 product-storer（数据落库）

```bash
python3 skills/product-storer/storer.py --product-id <id>
```

**验证点：**
- `products` 表新增1条记录
- `product_skus` 表新增 N 条记录（N = SKU数量）

### 4.5 listing-optimizer（标题描述优化）

```bash
python3 skills/listing-optimizer/optimizer.py --product-id <id>
```

**验证点：**
- 返回繁体中文优化标题（50-100字符）
- 返回结构化描述，不含"现货"等禁用词

### 4.6 miaoshou-updater（回写发布）

```bash
python3 skills/miaoshou-updater/updater.py --product-id <id>
```

**验证点：**
- ERP对话框打开，7个字段全部填写
- 点击"保存并发布"成功

### 4.7 profit-analyzer（利润分析）

```bash
python3 skills/profit-analyzer/analyzer.py --product-id <id>
```

**验证点：**
- 输出完整利润计算（含佣金、手续费等）
- 飞书利润分析表格新增一行

---

## 五、常见问题排查

| 错误现象 | 可能原因 | 解决方案 |
|----------|----------|----------|
| `OperationalError: could not connect to server` | 数据库未启动或配置错误 | 检查 `config/config.env` 中 DB_HOST/DB_NAME/DB_USER/DB_PASSWORD |
| `FileNotFoundError: miaoshou_cookies.json` | Cookies 文件未上传 | 重新导出并上传 Cookies |
| `playwright._impl._errors.Error: Executable doesn't exist` | Playwright 浏览器未安装 | 运行 `python3 -m playwright install chromium` |
| `Connection refused: 127.0.0.1:8080` | SSH 隧道或本地服务未启动 | 检查 MobaXterm 隧道 + 本地服务 |
| `psycopg2.errors.UndefinedTable` | 数据库表未创建 | 执行 `docs/002_database_restructuring_products.sql` |

---

## 六、数据库初始化（首次部署）

如果数据库表尚未创建，需执行数据库初始化脚本：

```bash
# 读取数据库配置
source config/config.env

# 执行建表脚本
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
  -f docs/002_database_restructuring_products.sql
```

---

## 七、配置文件说明

| 文件 | 说明 |
|------|------|
| `config/config.env` | 主配置文件（数据库、API Key、飞书等） |
| `config/llm_config.py` | LLM 模型配置（Doubao / DeepSeek） |
| `config/prompts/` | 提示词模板 |

**修改数据库配置示例：**

```bash
# 编辑配置
vi config/config.env

# 修改以下字段
DB_HOST=your-db-host
DB_NAME=ecommerce_data
DB_USER=your-db-user
DB_PASSWORD=your-password
```

---

## 八、验证完成标准

完成以下所有检查即代表远程服务器环境验证通过：

- [ ] `bash scripts/check-preconditions.sh` 输出 "通过: 5 项  失败: 0 项"
- [ ] 数据库表结构存在（products、product_skus）
- [ ] 至少完成一次完整的端到端流程（Steps 1-8）
- [ ] 飞书利润分析表格成功写入数据

---

*参考文档：*
- `docs/preconditions-checklist.md` — 前置条件详细说明
- `docs/miaoshou-erp-cloud-deployment-plan.md` — 云服务器部署方案
- `AGENTS.md` — 8步工作流速查
