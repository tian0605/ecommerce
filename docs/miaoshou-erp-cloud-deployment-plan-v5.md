# 妙手ERP自动化技能 - 云服务器部署方案 v5（整合优化版）

**更新日期：** 2026-03-19
**版本：** v5（基于v3实用架构 + v4重构理念整合优化）
**目标环境：** Linux云服务器 (Ubuntu)
**数据库：** ecommerce_data
**对象存储：** 腾讯云COS（tian-cos）

---

## 一、方案概述

### 1.1 整合背景

| 版本 | 特点 | 不足 |
|------|------|------|
| **v3** | 实用架构清晰，COS存储方案完整 | 缺乏统一调度、错误处理、监控 |
| **v4** | 架构完善、调度中心、监控告警 | 过于复杂，部分设计过于理想化 |
| **v5** | **整合精华 + 去掉糟粕** | 平衡实用性与稳定性 |

### 1.2 v5整合原则

```
✅ 保留v3实用架构（COS方案、目录结构、存储流程）
✅ 增加v4核心功能（统一调度中心、错误处理、重试机制）
✅ 增加监控面板（简化版Streamlit）
✅ 增加日志系统
✅ 去掉v4过度设计（加密体系、多平台适配器等过于复杂的部分）
✅ 保持方案简洁实用
```

---

## 二、COS存储配置

### 2.1 腾讯云COS配置（已就绪）

```ini
[tian-cos]
type = s3
provider = Other
access_key_id = AKID60h9NNYVEj03sTfiWHwW4PWQ6ZonZ6YQ
secret_access_key = 71h8LJ5dx3uXwCcrseCWbdUK0SgfPukM
endpoint = cos.ap-guangzhou.myqcloud.com
```

**COS基本信息：**

| 配置项 | 值 |
|--------|-----|
| Bucket | tian-cloud-file-1309014213 |
| 地域 | ap-guangzhou |
| Endpoint | cos.ap-guangzhou.myqcloud.com |
| COS地址 | https://tian-cloud-file-1309014213.cos.ap-guangzhou.myqcloud.com |

### 2.2 COS目录结构

```
tian-cloud-file-1309014213/
└── products/                         # 商品素材根目录
    └── {product_id}/
        ├── product_info.md          # 商品信息
        ├── main_images/            # 主图
        ├── detail_images/          # 详情图
        ├── sku_images/             # SKU图
        └── videos/                 # 视频
```

---

## 三、系统架构

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     OpenClaw调度中心                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐ │
│  │  任务编排器     │  │  状态管理器      │  │  错误处理器    │ │
│  │  TaskQueue     │  │  StateManager   │  │  ErrorHandler  │ │
│  │  - 任务队列     │  │  - 状态跟踪     │  │  - 重试机制    │ │
│  │  - 依赖管理     │  │  - 进度记录     │  │  - 告警触发    │ │
│  └─────────────────┘  └─────────────────┘  └────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  日志管理器 LogManager                                      │ │
│  │  - 结构化日志 | 日志聚合 | 日志查询                          │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│     数据层         │ │     存储层         │ │     平台层        │
│  PostgreSQL      │ │  腾讯云COS        │ │  Shopee          │
│  ecommerce_data  │ │  tian-cos        │ │  妙手ERP         │
│  Redis缓存       │ │  本地临时存储     │ │                  │
└───────────────────┘ └───────────────────┘ └───────────────────┘
```

### 3.2 技能模块目录结构（整合版）

```
/home/ubuntu/.openclaw/skills/
├── shared/                          # ⭐ 新增：共享模块
│   ├── __init__.py
│   ├── db.py                       # 统一数据库连接
│   ├── llm_client.py               # 统一LLM调用
│   ├── prompts.py                   # 统一Prompt加载
│   ├── cos_storage.py               # ⭐ COS上传下载封装
│   ├── retry_handler.py              # ⭐ 重试机制
│   └── logger.py                    # ⭐ 日志封装
│
├── product-collector/               # 1688商品采集
│   ├── scrape.py                   # 主入口
│   ├── dynamic_scraper.py           # Playwright爬虫
│   ├── base.py                      # 数据模型
│   └── SKILL.md
│
├── listing-generator/                # Listing生成（唯一版本）
│   ├── listing_generator.py
│   ├── prompts.py                   # ⭐ 格式化输出
│   └── SKILL.md
│
├── image-reviewer/                  # AI图片审查
│   ├── image_reviewer.py
│   └── SKILL.md
│
├── product-uploader/                # 打包上传
│   ├── data_transformer.py
│   ├── cos_uploader.py              # ⭐ COS上传
│   └── SKILL.md
│
├── listing-updater/                  # Listing更新
│   ├── listing_updater.py
│   └── SKILL.md
│
├── miaoshou-uploader/               # 妙手上传
│   ├── uploader.py
│   ├── login_miaoshou.py
│   └── SKILL.md
│
└── shopee-taiwan/                  # 利润分析
    ├── shopee_taiwan_profit_analyzer.py
    └── SKILL.md
```

**vs v3变化：**
- ✅ 增加 `shared/` 共享模块（db、llm_client、cos_storage等）
- ✅ 增加 `cos_uploader.py` 到 product-uploader
- ✅ 增加 `prompts.py` 到 listing-generator
- ✅ 删除冗余文件（保留核心功能）

---

## 四、数据流

### 4.1 完整业务流程

```
1688链接
    │
    ▼
┌─────────────────────────────────────────┐
│  product-collector                     │
│  1. Playwright动态抓取                 │
│  2. 下载图片/视频到本地临时目录        │
│  3. 落库到 products + product_skus     │
│  4. 调用 listing_generator             │
│  5. 上传到 COS                         │
│  6. 删除本地临时文件                   │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  listing-generator                     │
│  - shopee_name（标题）                 │
│  - shopee_description（描述）          │
│  - shopee_category_id（分类）          │
│  - shopee_sku_name（SKU台湾名）        │
└─────────────────────────────────────────┘
    │
    ├───────────────┬───────────────┐
    ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│image-reviewer│ │listing-    │ │product-     │
│AI图片审查   │ │updater     │ │uploader    │
│删除异常图片 │ │批量更新    │ │打包ZIP     │
└─────────────┘ └─────────────┘ └─────────────┘
    │               │               │
    │           mass_update    products/{id}.zip
    │               │               │
    │               └───────┬───────┘
    │                       ▼
    └───────────────────────────► Shopee / 妙手ERP
                                        │
                                        ▼
                                ┌─────────────┐
                                │shopee-taiwan│
                                │利润分析    │
                                └─────────────┘
```

### 4.2 存储策略

| 存储位置 | 用途 | 生命周期 |
|----------|------|----------|
| **COS** | 商品素材（图片/视频） | 永久 |
| **COS** | ZIP包（上传前） | 上传后删除COS副本 |
| **本地** | 临时处理目录 | 处理完自动清理 |
| **本地** | 日志文件 | 保留7天 |

---

## 五、核心模块实现

### 5.1 shared/cos_storage.py（COS统一存储）

```python
# cos_storage.py - COS统一上传下载模块
import os
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

COS_BUCKET = "tian-cloud-file-1309014213"
RCLONE_CMD = "/usr/bin/rclone"

class COSStorage:
    """COS统一存储封装"""

    def __init__(self):
        self.rclone = RCLONE_CMD
        self.bucket = COS_BUCKET

    def upload_dir(self, local_dir: str, cos_key_prefix: str) -> bool:
        """上传整个目录到COS"""
        try:
            cmd = [
                self.rclone, "copy",
                str(local_dir),
                f"tian-cos:{self.bucket}/{cos_key_prefix}",
                "--progress"
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            if result.returncode != 0:
                logger.error(f"Upload failed: {result.stderr.decode()}")
                return False
            logger.info(f"Uploaded {local_dir} to COS/{cos_key_prefix}")
            return True
        except Exception as e:
            logger.error(f"Upload error: {e}")
            raise

    def download_dir(self, cos_key_prefix: str, local_dir: str) -> bool:
        """从COS下载整个目录"""
        try:
            Path(local_dir).mkdir(parents=True, exist_ok=True)
            cmd = [
                self.rclone, "copy",
                f"tian-cos:{self.bucket}/{cos_key_prefix}",
                str(local_dir),
                "--progress"
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            if result.returncode != 0:
                logger.error(f"Download failed: {result.stderr.decode()}")
                return False
            logger.info(f"Downloaded COS/{cos_key_prefix} to {local_dir}")
            return True
        except Exception as e:
            logger.error(f"Download error: {e}")
            raise

    def upload_file(self, local_path: str, cos_key: str) -> bool:
        """上传单个文件"""
        try:
            cmd = [
                self.rclone, "copy",
                str(local_path),
                f"tian-cos:{self.bucket}/{cos_key}"
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Upload file error: {e}")
            return False

    def delete(self, cos_key: str) -> bool:
        """删除COS上的文件"""
        try:
            cmd = [self.rclone, "deletefile", f"tian-cos:{self.bucket}/{cos_key}"]
            result = subprocess.run(cmd, capture_output=True)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Delete error: {e}")
            return False
```

### 5.2 shared/retry_handler.py（重试机制）

```python
# retry_handler.py - 重试机制
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def retry(max_retries=3, backoff_factor=2, exceptions=(Exception,)):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        logger.error(f"{func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    wait_time = backoff_factor ** attempt
                    logger.warning(f"{func.__name__} retry {attempt+1}/{max_retries}, waiting {wait_time}s: {e}")
                    time.sleep(wait_time)
        return wrapper
    return decorator

class RetryHandler:
    """带重试的执行器"""

    def __init__(self, max_retries=3, backoff_factor=2):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def execute(self, func, *args, **kwargs):
        """执行带重试"""
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                wait_time = self.backoff_factor ** attempt
                logger.warning(f"Retry {attempt+1}/{self.max_retries}, waiting {wait_time}s: {e}")
                time.sleep(wait_time)
```

### 5.3 shared/logger.py（日志系统）

```python
# logger.py - 日志封装
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

LOG_DIR = "/home/ubuntu/work/logs"
LOG_FILE = f"{LOG_DIR}/skills_{datetime.now().strftime('%Y%m%d')}.log"
LOG_LEVEL = logging.INFO

def setup_logger(name: str) -> logging.Logger:
    """创建日志记录器"""
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    if not logger.handlers:
        # 文件处理器
        fh = RotatingFileHandler(
            LOG_FILE, maxBytes=10*1024*1024, backupCount=7
        )
        fh.setLevel(LOG_LEVEL)

        # 控制台处理器
        ch = logging.StreamHandler()
        ch.setLevel(LOG_LEVEL)

        # 格式
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger
```

### 5.4 shared/db.py（统一数据库）

```python
# db.py - 统一数据库连接
import psycopg2
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'database': os.environ.get('DB_NAME', 'ecommerce_data'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', 'postgres'),
    'port': int(os.environ.get('DB_PORT', 5432))
}

@contextmanager
def get_conn():
    """获取数据库连接"""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()

@contextmanager
def get_cursor():
    """获取数据库cursor"""
    with get_conn() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"DB error: {e}")
            raise
        finally:
            cursor.close()
```

---

## 六、部署任务清单

### Phase 1: 环境准备（预计1小时）

| 任务 | 状态 | 说明 |
|------|------|------|
| 系统依赖安装 | 待完成 | chrome, xvfb, postgresql-client |
| Python依赖安装 | 部分完成 | 缺beautifulsoup4, playwright |
| Playwright安装 | 待完成 | chromium浏览器 |
| rclone安装与配置 | ✅已完成 | tian-cos已配置 |
| COS Python SDK | ✅已安装 | cos-python-sdk-v5 |
| **创建shared模块** | ⭐新增 | db.py, cos_storage.py, logger.py, retry_handler.py |
| 目录结构创建 | 待完成 | /home/ubuntu/work/... |
| 配置文件迁移 | 待完成 | llm_models.yaml, prompts.yaml |

### Phase 2: 代码适配（预计4小时）

| 任务 | 状态 | 说明 |
|------|------|------|
| 数据库名修改 | 待完成 | market_data → ecommerce_data |
| 路径配置修改 | 待完成 | Windows路径 → Linux路径 |
| **统一import为shared模块** | ⭐新增 | 替换散落的db/llm_client |
| **删除冗余文件** | ⭐精简 | 按冗余分析报告删除14个文件 |
| 妙手登录方案 | 待完成 | CDP或Cookie方案 |

### Phase 3: 测试验证（预计2小时）

| 任务 | 状态 | 说明 |
|------|------|------|
| product-collector测试 | 待完成 | 采集+上传COS |
| listing-generator测试 | 待完成 | 生成listing文字 |
| product-uploader测试 | 待完成 | 打包ZIP+上传COS |
| miaoshou-uploader测试 | 待完成 | 从COS下载，上传妙手 |

### Phase 4: 监控（预计1小时）

| 任务 | 状态 | 说明 |
|------|------|------|
| 日志系统测试 | ⭐新增 | 验证日志记录 |
| 监控面板 | ⭐简化版 | Streamlit简易仪表盘 |

---

## 七、改造优先级

| 优先级 | 任务 | 预计时间 | 说明 |
|--------|------|----------|------|
| P0 | 安装Playwright | 30分钟 | 采集必需 |
| P0 | 创建目录结构 | 10分钟 | 基础设施 |
| P0 | **创建shared模块** | 1小时 | 统一db/cos/logger |
| P0 | 配置文件迁移 | 15分钟 | LLM/Prompt配置 |
| P1 | 数据库名修改 | 30分钟 | 多文件修改 |
| P1 | 路径配置修改 | 1小时 | 多文件修改 |
| P1 | **删除冗余文件** | 15分钟 | 按冗余报告删除 |
| P1 | 妙手登录方案 | 3小时 | CDP实现 |
| P2 | 监控面板 | 1小时 | Streamlit简易版 |

**v5总工作量：约8小时**

---

## 八、v3 vs v4 vs v5对比

| 特性 | v3 | v4 | v5 |
|------|:--:|:--:|:--:|
| COS存储 | ✅ | ✅ | ✅ |
| 目录结构 | ✅ | ✅ | ✅ |
| **shared共享模块** | ❌ | ✅ | ✅ |
| **统一调度中心** | ❌ | ✅ | ❌ (过于复杂) |
| **重试机制** | ❌ | ✅ | ✅ |
| **日志系统** | ❌ | ✅ | ✅ |
| **监控面板** | ❌ | ✅ | ✅ (简化版) |
| 加密体系 | ❌ | ✅ | ❌ (过度设计) |
| 多平台适配器 | ❌ | ✅ | ❌ (暂不需要) |
| 方案复杂度 | 低 | 高 | **中** |
| 实用度 | 高 | 中 | **高** |

---

## 九、总结

**v5核心改进：**
1. ✅ **shared共享模块**：统一db、cos_storage、logger、retry_handler
2. ✅ **重试机制**：网络异常自动重试，提高稳定性
3. ✅ **日志系统**：结构化日志，便于排查问题
4. ✅ **监控面板**：简化版Streamlit仪表盘
5. ✅ **删除冗余**：按冗余分析报告精简代码
6. ✅ **保持简洁**：去掉v4过度设计，保持实用

**待完成：**
- ⏳ Playwright安装
- ⏳ 创建shared模块
- ⏳ 配置文件迁移
- ⏳ 代码路径/数据库名修改
- ⏳ 删除冗余文件
- ⏳ 妙手登录方案
