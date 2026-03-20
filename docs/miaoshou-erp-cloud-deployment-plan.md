# 妙手ERP自动化技能 - 云服务器部署方案

**分析日期：** 2026-03-19  
**目标环境：** Linux云服务器 (Ubuntu)

---

## 一、技能模块依赖分析

### 1.1 技能模块清单

| 技能 | 功能 | 主要依赖 | 本地化需求 |
|------|------|----------|------------|
| **miaoshou-uploader** | 上传ZIP到妙手ERP | Playwright浏览器、oss2 | 浏览器登录需重构 |
| **product-uploader** | 打包商品素材为ZIP | psycopg2、openpyxl | 路径适配 |
| **listing-generator** | 生成优化标题/描述 | psycopg2、requests(LLM) | 路径适配 |
| **listing-updater** | 批量更新Shopee listing | pandas、listing-generator | 路径适配 |
| **image-reviewer** | AI审查商品图片 | requests(VL模型API) | 无（API调用） |
| **shopee_taiwan** | 成本利润分析 | psycopg2、openpyxl | 路径适配 |

### 1.2 外部服务依赖

```
┌─────────────────────────────────────────────────────────────┐
│                     外部服务                                 │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL    │ localhost:5432  │ market_data数据库         │
│  LLM API       │ dashscope.aliyuncs.com │ 商品文案生成       │
│  VL Model API  │ dashscope.aliyuncs.com │ 图片审查          │
│  OSS存储       │ Alibaba Cloud   │ ZIP文件存储              │
│  妙手ERP       │ erp.91miaoshou.com │ 商品上传目标         │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 本地文件依赖

| 原路径(Windows) | 云服务器路径 | 说明 |
|----------------|-------------|------|
| D:\work\product_init | /home/ubuntu/work/product_init | 商品原始素材 |
| D:\work\product_packages | /home/ubuntu/work/product_packages | 打包输出 |
| D:\work\product_update | /home/ubuntu/work/product_update | listing更新文件 |
| D:\work\market_data | /home/ubuntu/work/market_data | 市场数据Excel |
| C:\Users\zhizh\.openclaw\workspace\config | /home/ubuntu/.openclaw/config | 配置文件 |

---

## 二、部署方案

### 2.1 目录结构设计

```
/home/ubuntu/work/
├── product_init/          # 商品原始素材（含图片）
├── product_packages/       # 打包后的ZIP文件
├── product_update/
│   ├── download_file/     # Shopee导出的更新模板
│   └── upload_file/       # 生成的更新模板
└── market_data/           # 市场数据Excel文件

/home/ubuntu/.openclaw/
├── config/
│   ├── llm_models.yaml    # LLM模型配置
│   └── prompts.yaml        # Prompt模板
└── skills/
    ├── miaoshou-uploader/
    ├── product-uploader/
    ├── listing-generator/
    ├── listing-updater/
    ├── image-reviewer/
    └── shopee_taiwan/
```

### 2.2 数据库配置

**PostgreSQL 连接：**
```python
# 改为环境变量或配置文件
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'database': os.environ.get('DB_NAME', 'market_data'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', ''),
}
```

**需要创建的表：**
- products
- product_skus
- product_mapping
- hot_search_words
- exchange_rates
- product_analysis
- product_alerts
- analysis_job_logs
- profit_analysis_summary

### 2.3 妙手登录方案（重点改造）

**问题：** 原方案使用Playwright打开本地浏览器扫码登录，云服务器无显示器。

**解决方案：** 复用服务器上已有的Chrome远程调试会话

```python
# miaoshou-uploader/login_miaoshou.py 改造方案
# 不再使用Playwright启动浏览器
# 而是连接服务器上已有的Chrome CDP端口获取cookies

import requests
import json

CDP_URL = "http://localhost:9223"  # 服务器Chrome调试端口

def get_cookies_from_chrome():
    """从已运行的Chrome实例获取cookies"""
    # 1. 获取所有标签页
    tabs = requests.get(f"{CDP_URL}/json").json()
    
    # 2. 找到妙手ERP页面
    miaoshou_tab = None
    for tab in tabs:
        if "91miaoshou.com" in tab.get("url", ""):
            miaoshou_tab = tab
            break
    
    if not miaoshou_tab:
        raise Exception("未找到妙手ERP页面，请先在Chrome中登录")
    
    # 3. 通过CDP执行JS获取cookies
    ws_url = miaoshou_tab["webSocketDebuggerUrl"]
    # 使用websockets或curl调用CDP协议
    ...
```

**替代简化方案：** 手动导出cookies

用户在自己的Chrome（已登录妙手）中：
1. 安装EditThisCookie等Cookie导出插件
2. 导出为JSON格式
3. 上传到服务器的 `miaoshou_cookies.json`

---

## 三、部署步骤

### 3.1 系统依赖安装

```bash
# 更新系统
apt-get update && apt-get upgrade -y

# 安装Python和pip
apt-get install -y python3 python3-pip python3-venv

# 安装Chrome浏览器（用于CDP）
apt-get install -y google-chrome-stable

# 安装PostgreSQL客户端（用于管理数据库）
apt-get install -y postgresql-client

# 安装屏幕录像（用于headless浏览器）
apt-get install -y xvfb
```

### 3.2 Python依赖

```bash
pip3 install \
    psycopg2-binary \
    openpyxl \
    pandas \
    requests \
    oss2 \
    pyyaml \
    websockets
```

### 3.3 文件同步

```bash
# 创建目录结构
mkdir -p /home/ubuntu/work/product_init
mkdir -p /home/ubuntu/work/product_packages
mkdir -p /home/ubuntu/work/product_update/{download_file,upload_file}
mkdir -p /home/ubuntu/work/market_data
mkdir -p /home/ubuntu/.openclaw/config
mkdir -p /home/ubuntu/.openclaw/skills

# 复制技能文件
cp -r /path/to/skill_learn/* /home/ubuntu/.openclaw/skills/
```

### 3.4 配置文件修改

**llm_models.yaml 路径调整：**
```yaml
# 配置文件路径改为绝对路径
config_path: "/home/ubuntu/.openclaw/config"
```

**代码路径适配（示例）：**
```python
# 原来
CONFIG_DIR = Path("C:/Users/zhizh/.openclaw/workspace/config")

# 改为
CONFIG_DIR = Path(os.environ.get('SKILL_CONFIG_DIR', '/home/ubuntu/.openclaw/config'))
SOURCE_DIR = Path(os.environ.get('PRODUCT_SOURCE_DIR', '/home/ubuntu/work/product_init'))
```

---

## 四、妙手上传自动化流程

### 4.1 当前架构（本地Windows）

```
用户手动操作:
1. 打开Chrome浏览器
2. 登录妙手ERP
3. 扫码认证
   ↓
Playwright捕获cookies
   ↓
uploader.py使用cookies调用API上传
```

### 4.2 云服务器架构

```
方案A: CDP连接（推荐）
┌─────────────────┐     CDP      ┌─────────────────┐
│  服务器Chrome   │◄───────────►│   uploader.py   │
│  (已登录妙手)   │   port 9222  │   (无头模式)     │
└─────────────────┘              └─────────────────┘

方案B: Cookie文件
┌─────────────────┐              ┌─────────────────┐
│  用户本地Chrome │ ──导出JSON──►│  miaoshou_       │
│  (已登录妙手)   │              │  cookies.json    │
└─────────────────┘              └─────────────────┘
```

### 4.3 CDP方案实现

服务器上已运行Chrome监听9222端口，可以：

```python
# 通过CDP协议获取cookies
import subprocess
import json

def get_miaoshou_cookies_via_cdp():
    """从Chrome CDP获取妙手cookies"""
    # 1. 获取标签页列表
    result = subprocess.run(
        ['curl', '-s', 'http://localhost:9222/json'],
        capture_output=True, text=True
    )
    tabs = json.loads(result.stdout)
    
    # 2. 找到妙手页面
    miaoshou_tab = None
    for tab in tabs:
        if "91miaoshou.com" in tab.get("url", ""):
            miaoshou_tab = tab
            break
    
    if not miaoshou_tab:
        return None
    
    # 3. 执行JS获取document.cookies
    # 需要用websockets连接CDP执行命令
    ws_url = miaoshou_tab["webSocketDebuggerUrl"]
    # ... websockets implementation
```

---

## 五、image-reviewer 优化

### 5.1 当前实现

- 使用base64编码图片
- 每批4张图发送给VL模型
- 串行处理多个商品

### 5.2 云服务器优化

**无需大改**，因为：
- VL模型是API调用，无需本地GPU
- base64编码在云服务器上CPU消耗可接受
- 可以增加并发数（8-16张/批）

**建议优化：**
```python
# 增加批量大小
BATCH_SIZE = 8  # 原来4

# 增加并发商品处理
MAX_CONCURRENT_PRODUCTS = 3
```

---

## 六、数据流与存储

### 6.1 数据流图

```
┌──────────────┐    ┌───────────────┐    ┌──────────────┐
│  商品采集    │───►│  product_init │───►│ image-review │
│  (1688等)    │    │   (图片+数据)  │    │   (AI审查)   │
└──────────────┘    └───────────────┘    └──────┬───────┘
                                                │
                                                ▼
┌──────────────┐    ┌───────────────┐    ┌──────────────┐
│  妙手ERP     │◄───│    OSS存储     │◄───│data_transform│
│  (上传目标)   │    │   (ZIP文件)   │    │   (打包ZIP)  │
└──────────────┘    └───────────────┘    └──────────────┘
        ▲
        │
┌───────┴───────┐
│  listing     │
│  generator   │
│  (LLM优化)   │
└──────────────┘
```

### 6.2 文件生命周期

| 阶段 | 目录 | 保留时间 |
|------|------|----------|
| 原始素材 | product_init | 永久（备份后删除） |
| 审查后素材 | product_init | 直到打包完成 |
| ZIP包 | product_packages | 直到上传成功 |
| 上传成功 | - | 可删除ZIP |

---

## 七、改造优先级

### Phase 1: 基础适配（必须）

| 任务 | 工作量 | 说明 |
|------|--------|------|
| 创建目录结构 | 5分钟 | mkdir命令 |
| 路径环境变量化 | 2小时 | 改20+处路径 |
| 数据库连接配置化 | 30分钟 | 环境变量 |
| 配置文件迁移 | 15分钟 | copy文件 |

### Phase 2: 妙手登录（核心）

| 任务 | 工作量 | 说明 |
|------|--------|------|
| CDP获取cookies | 3小时 | 实现CDP协议 |
| Cookie文件方案 | 1小时 | 简单fallback |
| 上传逻辑测试 | 2小时 | 调试 |

### Phase 3: 优化完善

| 任务 | 工作量 | 说明 |
|------|--------|------|
| image-reviewer并发 | 1小时 | 调参 |
| 异常处理增强 | 2小时 | 日志+重试 |
| 监控告警 | 3小时 | 可选 |

---

## 八、风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| Chrome CDPPort被墙 | 中 | 使用Cookie文件方案 |
| 数据库连接不稳定 | 高 | 增加重试+连接池 |
| OSS上传失败 | 中 | 增加重试+断点续传 |
| LLM API限流 | 低 | 降级+缓存 |
| 磁盘空间不足 | 中 | 定期清理+监控 |

---

## 九、总结

**云服务器部署是可行的**，主要改造点：

1. **路径适配**：Windows路径 → Linux路径 + 环境变量
2. **妙手登录**：Playwright → CDP连接 或 Cookie文件
3. **数据库**：localhost连接 → 可配置远程连接
4. **image-reviewer**：基本不改，增大并发即可

**预计改造工作量：** 6-8小时（主要在妙手登录方案）

**建议先从 Phase 1 + Phase 2 的 Cookie文件方案 开始**，快速验证流程可行性。
