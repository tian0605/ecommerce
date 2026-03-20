# 妙手ERP自动化技能 - 云服务器部署方案 v3

**更新日期：** 2026-03-19
**目标环境：** Linux云服务器 (Ubuntu)
**数据库：** ecommerce_data（已有19张表，无需新建）
**对象存储：** 腾讯云COS（tian-cos）

---

## 一、技能模块完整清单

### 1.1 技能模块总览

| 技能 | 功能 | 主要依赖 | 本地化需求 |
|------|------|----------|------------|
| **product-collector** | 1688商品采集+图片+落库+LLM生成 | Playwright、beautifulsoup4、lxml、aiohttp | 路径适配 |
| **product-uploader** | 打包商品素材为ZIP | psycopg2、openpyxl | 路径适配 |
| **listing-generator** | 生成优化标题/描述 | psycopg2、requests(LLM) | 路径适配 |
| **listing-updater** | 批量更新Shopee listing | pandas、listing-generator | 路径适配 |
| **image-reviewer** | AI审查商品图片 | requests(VL模型API) | 无（API调用） |
| **shopee_taiwan** | 成本利润分析 | psycopg2、openpyxl | 路径适配 |
| **miaoshou-uploader** | 上传ZIP到妙手ERP | oss2 | 浏览器登录需重构 |

### 1.2 数据流向图（基于COS存储）

```
┌─────────────────┐
│  product-       │
│  collector      │───► COS: products/{id}/
│  (1688采集)     │    ├── main_images/
│                 │    ├── detail_images/
│                 │    ├── sku_images/
│                 │    └── videos/
└────────┬────────┘
         │ 落库到 ecommerce_data.products / product_skus
         ▼
┌─────────────────┐
│  listing-       │
│  generator      │───► shopee_name / shopee_description
│  (LLM生成)      │    shopee_category_id / shopee_sku_name
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  image-reviewer │───► COS: 删除异常图片
│  (AI图片审查)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  product-       │
│  uploader       │───► COS: products/{id}.zip
│  (打包ZIP)      │    本地保留临时文件
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  miaoshou-      │
│  uploader       │───► 妙手ERP采集箱
│  (上传妙手)     │
└─────────────────┘
```

**关键变化：**
- 本地 `/home/ubuntu/work/product_init/` → **COS对象存储**
- 本地只保留临时文件，处理完成后可自动清理
- COS永久存储，支持多端访问

---

## 二、COS存储配置

### 2.1 腾讯云COS配置

**rclone配置（已配置）：**
```ini
[tian-cos]
type = s3
provider = Other
access_key_id = AKID60h9NNYVEj03sTfiWHwW4PWQ6ZonZ6YQ
secret_access_key = 71h8LJ5dx3uXwCcrseCWbdUK0SgfPukM
endpoint = cos.ap-guangzhou.myqcloud.com
force_path_style = false
```

**COS基本信息：**
| 配置项 | 值 |
|--------|-----|
| Bucket | tian-cloud-file-1309014213 |
| 地域 | ap-guangzhou |
| Endpoint | cos.ap-guangzhou.myqcloud.com |
| COS地址 | https://tian-cloud-file-1309014213.cos.ap-guangzhou.myqcloud.com |

### 2.2 Python依赖

```bash
# COS Python SDK（已安装）
pip3 install --break-system-packages cos-python-sdk-v5

# 或使用boto3（S3协议兼容）
pip3 install --break-system-packages boto3
```

### 2.3 COS操作示例

**使用cos-python-sdk-v5：**
```python
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client

config = CosConfig(
    Region='ap-guangzhou',
    SecretId='AKID60h9NNYVEj03sTfiWHwW4PWQ6ZonZ6YQ',
    SecretKey='71h8LJ5dx3uXwCcrseCWbdUK0SgfPukM',
    Token=None,
    Scheme='https'
)
client = CosS3Client(config)

# 上传文件
client.upload_file(
    Bucket='tian-cloud-file-1309014213',
    Key='products/商品ID/main_images/img.jpg',
    LocalFilePath='/local/path/img.jpg'
)

# 下载文件
client.get_object(
    Bucket='tian-cloud-file-1309014213',
    Key='products/商品ID/main_images/img.jpg',
    LocalPath='/local/path/img.jpg'
)
```

**使用rclone（已配置）：**
```bash
# 上传
rclone copy /local/file.txt tian-cos:products/

# 下载
rclone copy tian-cos:products/file.txt /local/

# 列出
rclone ls tian-cos:products/
```

### 2.4 COS目录结构规划

```
tian-cloud-file-1309014213 (COS Bucket)
└── products/                         # 商品素材根目录
    └── {product_id}/
        ├── product_info.md          # 商品信息
        ├── main_images/            # 主图
        │   ├── 黑色.jpg
        │   └── 透明.jpg
        ├── detail_images/          # 详情图
        ├── sku_images/             # SKU图
        └── videos/                 # 视频
```

---

## 三、已有数据库结构（ecommerce_data）

### 2.1 核心表（已存在）

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| **products** | 商品主表 | id, source_url, title, shop_name, price_min/max, attributes, shopee_name, shopee_description, shopee_category_id, packaging_status, listing_status |
| **product_skus** | SKU表 | id, product_id, sku_name, color, size, price, stock, package_weight, shopee_sku_name |
| **product_mapping** | Shopee映射 | db_product_id, shopee_product_id, master_sku |
| **hot_search_words** | 热搜词 | keyword, category, source_file |
| **exchange_rates** | 汇率 | from_currency, to_currency, rate, effective_date |
| **product_analysis** | 利润分析 | product_id, sku_id, weight, suggested_price, profit_rate |
| **product_alerts** | 预警 | alert_type, severity, alert_message |
| **analysis_job_logs** | 任务日志 | job_type, platform, site, status |
| **profit_analysis_summary** | 汇总 | platform, site, avg_profit_rate |

### 2.2 数据库连接参数

```python
DB_CONFIG = {
    'host': 'localhost',
    'database': 'ecommerce_data',
    'user': 'postgres',  # 或 'ubuntu'
    'password': '<需确认>',
    'port': 5432
}
```

---

## 三、云服务器环境准备

### 3.1 系统依赖

```bash
# 基础工具
apt-get update && apt-get upgrade -y
apt-get install -y python3 python3-pip python3-venv
apt-get install -y google-chrome-stable  # 用于Playwright
apt-get install -y xvfb  # 虚拟显示器
apt-get install -y postgresql-client
apt-get install -y curl wget git
```

### 3.2 Python依赖（已安装部分）

```bash
pip3 install --break-system-packages \
    psycopg2-binary \
    openpyxl \
    pandas \
    requests \
    oss2 \
    pyyaml \
    websockets \
    beautifulsoup4 \
    lxml \
    aiohttp
```

### 3.3 Playwright安装

```bash
pip3 install --break-system-packages playwright
playwright install chromium
# 或指定版本
playwright install chromium --with-deps
```

---

## 四、目录结构

### 4.1 规划目录

```
/home/ubuntu/work/
├── product_init/          # 1688采集的原始素材（含图片）
│   └── 商品标题_商品ID/
│       ├── main_images/
│       ├── detail_images/
│       ├── sku_images/
│       ├── videos/
│       └── product_info.md
├── product_packages/      # 打包后的ZIP文件（上传后删除）
│   └── *.zip
├── product_update/
│   ├── download_file/    # Shopee导出的更新模板
│   └── upload_file/     # 生成的更新模板
└── market_data/          # 市场数据Excel（可选）

/home/ubuntu/.openclaw/
├── config/
│   ├── llm_models.yaml    # LLM模型配置
│   └── prompts.yaml        # Prompt模板
└── skills/
    ├── product-collector/  # 1688商品采集
    ├── product-uploader/  # 素材打包
    ├── listing-generator/  # Listing生成
    ├── listing-updater/    # Listing更新
    ├── image-reviewer/    # 图片审查
    ├── shopee_taiwan/     # 利润分析
    └── miaoshou-uploader/ # 妙手上传
```

### 4.2 创建目录命令

```bash
mkdir -p /home/ubuntu/work/product_init
mkdir -p /home/ubuntu/work/product_packages
mkdir -p /home/ubuntu/work/product_update/download_file
mkdir -p /home/ubuntu/work/product_update/upload_file
mkdir -p /home/ubuntu/work/market_data
mkdir -p /home/ubuntu/.openclaw/config
mkdir -p /home/ubuntu/.openclaw/skills
```

---

## 五、配置文件迁移

### 5.1 配置文件

| 文件 | 来源 | 目标 |
|------|------|------|
| llm_models.yaml | skill_learn/llm_models.yaml | /home/ubuntu/.openclaw/config/ |
| prompts.yaml | skill_learn/prompts.yaml | /home/ubuntu/.openclaw/config/ |

### 5.2 数据库配置修改

需要修改以下文件中的数据库连接：

| 文件 | 修改内容 |
|------|----------|
| product-collector/scrape.py | `market_data` → `ecommerce_data` |
| product-collector/listing_generator.py | `market_data` → `ecommerce_data` |
| listing-generator/listing_generator.py | `market_data` → `ecommerce_data` |
| listing-updater/listing_updater.py | `market_data` → `ecommerce_data` |
| shopee_taiwan/shopee_taiwan_profit_analyzer.py | `market_data` → `ecommerce_data` |
| product-uploader/data_transformer.py | `market_data` → `ecommerce_data` |

---

## 六、product-collector 重点说明

### 6.1 核心依赖

```bash
pip3 install --break-system-packages \
    beautifulsoup4 \
    lxml \
    aiohttp \
    playwright
playwright install chromium --with-deps
```

### 6.2 功能流程

```
1. scrape.py <1688链接> <输出目录>
   │
   ├─► Playwright动态抓取页面
   │   - 主图（SKU颜色命名）
   │   - 详情图
   │   - SKU颜色缩略图
   │   - 视频URL
   │   - 商品属性
   │   - SKU列表
   │
   ├─► 下载图片到本地
   │
   ├─► 落库到 products + product_skus
   │
   └─► 调用 LLM 生成
       - shopee_name（标题）
       - shopee_description（描述）
       - shopee_category_id（分类）
       - shopee_sku_name（SKU台湾名）
```

### 6.3 输出结构

```
product_init/
└── 家用透明鞋子收纳盒_978301673922/
    ├── product_info.md        # 商品完整信息
    ├── main_images/           # 主图（按颜色命名）
    │   ├── 黑色.jpg
    │   ├── 透明.jpg
    │   └── main_003.jpg
    ├── detail_images/         # 详情图
    │   ├── detail_001.jpg
    │   └── detail_002.jpg
    ├── sku_images/            # SKU颜色缩略图
    │   ├── 黑色.jpg
    │   └── 透明.jpg
    └── videos/                # 视频
        └── video_01.mp4
```

---

## 八、存储方案（COS vs 本地）

### 8.1 方案对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| **本地存储** | 无需额外配置 | 占用服务器空间，迁移困难 |
| **COS存储** | 容量无限，多端访问，CDN加速 | 需配置SDK，有外网流量费 |

### 8.2 推荐方案：COS为主 + 本地为辅

**COS存储：**
- 商品原始素材（图片/视频）- 永久存储
- 打包后的ZIP文件 - 上传前临时存储
- 数据库备份文件

**本地存储：**
- 临时处理目录 `/home/ubuntu/work/tmp/`
- 处理完成后自动清理
- 日志文件

### 8.3 存储容量估算

| 存储位置 | 单商品大小 | 1000商品 |
|----------|-----------|----------|
| COS | ~41 MB | ~41 GB |
| 本地临时 | ~100 MB（峰值） | 自动清理 |

**COS优势：**
- 存储容量无限制
- 上传妙手时可直接从COS下载，无需本地文件
- 支持图片CDN加速访问

### 8.4 自动清理策略

```python
# product-uploader 打包完成后
def cleanup_after_upload(product_id, local_dir, zip_path):
    """上传COS后删除本地文件"""
    import shutil
    import os

    # 1. 上传到COS
    upload_to_cos(product_id, local_dir)

    # 2. 删除本地素材目录（可选，保留供后续处理）
    # shutil.rmtree(local_dir)

    # 3. 上传完成后删除本地ZIP
    if os.path.exists(zip_path):
        os.remove(zip_path)
```

### 8.5 COS上传工具封装

```python
import os
import subprocess

COS_BUCKET = "tian-cloud-file-1309014213"
RCLONE_CMD = "/usr/bin/rclone"  # 需安装rclone

def upload_dir_to_cos(local_dir, cos_key_prefix):
    """使用rclone上传目录到COS"""
    cmd = [
        RCLONE_CMD, "copy",
        local_dir,
        f"tian-cos:{COS_BUCKET}/{cos_key_prefix}",
        "--progress"
    ]
    subprocess.run(cmd)

def download_from_cos(cos_key, local_path):
    """从COS下载到本地"""
    cmd = [
        RCLONE_CMD, "copy",
        f"tian-cos:{COS_BUCKET}/{cos_key}",
        local_path,
        "--progress"
    ]
    subprocess.run(cmd)
```

---

## 八、妙手登录方案

### 8.1 问题

本地使用Playwright打开浏览器扫码登录，云服务器无显示器。

### 8.2 解决方案

**方案A：CDP连接（推荐）**
- 服务器Chrome已监听9222端口
- 通过CDP协议获取cookies
- 实现难度：★★★

**方案B：Cookie文件（简单）**
- 用户本地Chrome导出cookies
- 上传到服务器miaoshou_cookies.json
- 实现难度：★

### 8.3 CDP方案实现

```python
# 通过CDP获取妙手cookies
import subprocess
import json

CDP_URL = "http://localhost:9222"

def get_miaoshou_cookies():
    # 1. 获取标签页
    tabs = subprocess.run(
        ['curl', '-s', f'{CDP_URL}/json'],
        capture_output=True, text=True
    ).stdout
    tabs = json.loads(tabs)
    
    # 2. 找到妙手页面
    for tab in tabs:
        if "91miaoshou.com" in tab.get("url", ""):
            # 3. 连接CDP获取cookies
            ws_url = tab["webSocketDebuggerUrl"]
            # ... websockets实现
            return cookies
    return None
```

---

## 九、部署任务清单

### Phase 1: 环境准备

| 任务 | 状态 | 说明 |
|------|------|------|
| 系统依赖安装 | 待完成 | chrome, xvfb, postgresql-client |
| Python依赖安装 | 部分完成 | 缺beautifulsoup4, playwright |
| Playwright安装 | 待完成 | chromium浏览器 |
| **rclone安装与配置** | ✅已完成 | tian-cos已配置 |
| **COS Python SDK** | ✅已安装 | cos-python-sdk-v5 |
| 目录结构创建 | 待完成 | /home/ubuntu/work/... |
| 配置文件迁移 | 待完成 | llm_models.yaml, prompts.yaml |

### Phase 2: 代码适配（COS版）

| 任务 | 状态 | 说明 |
|------|------|------|
| 数据库名修改 | 待完成 | market_data → ecommerce_data |
| 路径配置修改 | 待完成 | Windows路径 → Linux路径 |
| **COS上传模块** | 待完成 | 使用cos-python-sdk或rclone |
| **本地临时目录** | 待完成 | /home/ubuntu/work/tmp/ |
| 妙手登录方案 | 待完成 | CDP或Cookie方案 |

### Phase 3: 测试验证

| 任务 | 状态 | 说明 |
|------|------|------|
| product-collector测试 | 待完成 | 采集1个商品，上传COS |
| listing-generator测试 | 待完成 | 生成listing文字 |
| product-uploader测试 | 待完成 | 打包ZIP，上传COS |
| miaoshou-uploader测试 | 待完成 | 从COS下载，上传妙手 |

---

## 十、改造优先级

| 优先级 | 任务 | 预计时间 | 说明 |
|--------|------|----------|------|
| P0 | 安装Playwright | 30分钟 | 采集必需 |
| P0 | 创建目录结构 | 10分钟 | 基础设施 |
| P0 | 配置文件迁移 | 15分钟 | LLM/Prompt配置 |
| P0 | **COS上传模块封装** | 1小时 | 统一上传接口 |
| P1 | 数据库名修改 | 30分钟 | 多文件修改 |
| P1 | 路径配置修改 | 1小时 | 多文件修改 |
| P1 | 妙手登录方案 | 3小时 | CDP实现 |
| P2 | 自动清理功能 | 1小时 | 上传后删除本地 |

---

## 十一、风险与注意事项

| 风险 | 等级 | 缓解 |
|------|------|------|
| Playwright在Linux headless问题 | 中 | 使用xvfb或headless=True |
| 数据库连接权限 | 高 | 确认postgres/ubuntu密码 |
| 1688反爬虫 | 中 | 添加延迟，控制频率 |
| 妙手登录失效 | 高 | 定期刷新cookies |
| **COS外网流量** | 中 | 使用内网Endpoint |
| **COS上传失败** | 中 | 增加重试机制，本地备份 |

---

## 十二、COS存储工作流

### 12.1 product-collector采集流程

```
1. scrape.py <1688链接>
   │
   ├─► Playwright动态抓取
   │
   ├─► 本地临时目录 /home/ubuntu/work/tmp/{product_id}/
   │   ├── main_images/
   │   ├── detail_images/
   │   ├── sku_images/
   │   └── videos/
   │
   ├─► 落库到 products + product_skus
   │
   ├─► 调用 LLM 生成 listing
   │
   └─► 上传到 COS: products/{product_id}/
       │
       └─► 删除本地临时目录
```

### 12.2 miaoshou-uploader下载流程

```
1. 指定 product_id
   │
   ├─► 从 COS 下载: products/{product_id}/
   │   → 本地临时目录
   │
   ├─► 打包成 ZIP
   │
   ├─► 上传到妙手ERP
   │
   └─► 删除本地临时文件
```

### 12.3 COS工具封装

```python
# cos_storage.py - COS统一上传下载模块
import os
import subprocess
from pathlib import Path

COS_BUCKET = "tian-cloud-file-1309014213"
COS_ENDPOINT = "cos.ap-guangzhou.myqcloud.com"

class COSStorage:
    def __init__(self):
        self.rclone = "/usr/bin/rclone"

    def upload_dir(self, local_dir, cos_key_prefix):
        """上传整个目录到COS"""
        cmd = [
            self.rclone, "copy",
            str(local_dir),
            f"tian-cos:{COS_BUCKET}/{cos_key_prefix}",
            "--progress"
        ]
        return subprocess.run(cmd).returncode == 0

    def download_dir(self, cos_key_prefix, local_dir):
        """从COS下载整个目录"""
        cmd = [
            self.rclone, "copy",
            f"tian-cos:{COS_BUCKET}/{cos_key_prefix}",
            str(local_dir),
            "--progress"
        ]
        return subprocess.run(cmd).returncode == 0

    def upload_file(self, local_path, cos_key):
        """上传单个文件到COS"""
        cmd = [
            self.rclone, "copy",
            str(local_path),
            f"tian-cos:{COS_BUCKET}/{cos_key}"
        ]
        return subprocess.run(cmd).returncode == 0

    def delete(self, cos_key):
        """删除COS上的文件/目录"""
        cmd = [
            self.rclone, "deletefile",
            f"tian-cos:{COS_BUCKET}/{cos_key}"
        ]
        return subprocess.run(cmd).returncode == 0

    def list(self, cos_key_prefix):
        """列出COS上的文件"""
        cmd = [
            self.rclone, "ls",
            f"tian-cos:{COS_BUCKET}/{cos_key_prefix}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout
```

---

## 十三、总结

**已完成：**
- ✅ Python依赖安装（大部分）
- ✅ 数据库 ecommerce_data 已存在19张表
- ✅ **COS存储配置**（tian-cos via rclone）
- ✅ **cos-python-sdk-v5 已安装**
- ✅ 分析文档

**待完成：**
- ⏳ Playwright安装
- ⏳ 目录结构创建（含临时目录）
- ⏳ 配置文件迁移
- ⏳ 代码路径/数据库名修改
- ⏳ **COS上传模块封装**
- ⏳ 妙手登录方案

**预计总工作量：8-10小时**
