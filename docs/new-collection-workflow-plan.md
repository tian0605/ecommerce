# 自动采集方案 v6 - 基于妙手ERP工作流

**创建日期：** 2026-03-20
**版本：** v6.0
**状态：** 方案设计

---

## 一、背景与目标

### 1.1 问题痛点
- **1688 IP反爬限制：** 服务器IP访问1688被拒绝（Access Denied）
- **原有方案瓶颈：** product-collector直接采集1688需要Browser Relay支持

### 1.2 新思路
利用**妙手ERP**作为中间层：
- 妙手ERP本身有1688插件，可以正常采集
- 服务器通过浏览器自动化操作妙手ERP的Web界面
- 绕过1688的IP反爬限制

### 1.3 目标
构建**全自动化**的商品采集 → 优化 → 上架 workflow

---

## 二、整体流程架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        新版自动采集工作流 v6                              │
└─────────────────────────────────────────────────────────────────────────┘

Step 1: 妙手ERP采集
    │
    │  [自动操作妙手Web界面]
    ▼
┌─────────────────────┐
│  妙手ERP 1688采集    │ ◄── 利用妙手插件绕过1688 IP限制
│  → 公用采集箱        │
└─────────┬───────────┘
          │
          │ 人工确认/自动触发
          ▼
Step 2: 采集箱数据爬取
    │
    │  [Playwright + Browser Relay]
    ▼
┌─────────────────────┐
│  爬取公用采集箱       │ ◄── 产品编辑页面
│  → 商品基础信息       │     - 标题/描述/主图/SKU图/详情图
│  → 阿里巴巴商品ID     │     - 库存/价格/SKU信息
└─────────┬───────────┘
          │
          ▼
Step 3: 数据落库
    │
    │  [Python + PostgreSQL]
    ▼
┌─────────────────────┐
│  ecommerce_data     │
│  products 表         │ ◄── 唯一索引: alibaba_product_id
└─────────┬───────────┘
          │
          ▼
Step 4: Listing优化
    │
    │  [LLM API调用]
    ▼
┌─────────────────────┐
│  标题优化            │ ◄── AI生成优质标题
│  描述优化            │
└─────────┬───────────┘
          │
          ▼
Step 5: 回写妙手ERP
    │
    │  [Playwright自动化]
    ▼
┌─────────────────────┐
│  更新编辑页面        │ ◄── 标题/描述/主编号回填
│  → 保存             │
└─────────┬───────────┘
          │
          ▼
Step 6: 产品认领
    │
    │  [Playwright自动化]
    ▼
┌─────────────────────┐
│  产品认领           │ ◄── 完成妙手ERP流程
│  → Shopee台湾       │
└─────────────────────┘
```

---

## 三、数据采集规格

### 3.1 采集字段清单

| 字段类别 | 字段名 | 说明 | 必需 |
|---------|--------|------|------|
| 基础信息 | alibaba_product_id | 阿里巴巴商品ID | ✅ |
| 基础信息 | source_url | 来源URL | ✅ |
| 基础信息 | product_title | 产品标题 | ✅ |
| 基础信息 | product_description | 产品描述 | ✅ |
| 主图 | main_images | 主图URL列表（JSON数组） | ✅ |
| SKU信息 | sku_list | SKU列表（JSON数组） | ✅ |
| SKU信息 | sku_properties | SKU属性（颜色/尺寸等） | ✅ |
| SKU信息 | sku_prices | SKU价格列表 | ✅ |
| SKU信息 | sku_stock | SKU库存列表 | ✅ |
| SKU信息 | sku_codes | SKU货号 | ✅ |
| 详情图 | detail_images | 详情图URL列表 | ✅ |
| 包装信息 | packaging_info | 包装信息（重量/尺寸） | ✅ |
| 分类信息 | category | 产品分类 | ✅ |
| 价格信息 | price_range | 价格区间 | ✅ |
| 起订量 | moq | 最小起订量 | ✅ |
| 创建时间 | created_at | 入库时间 | ✅ |
| 修改时间 | updated_at | 最后更新时间 | ✅ |

### 3.2 采集验收标准
- ✅ 阿里巴巴商品ID 非空
- ✅ 产品标题 非空
- ✅ 主图至少1张
- ✅ SKU至少1个（含价格/库存）
- ✅ 数据完整率 ≥ 95%

---

## 四、数据库设计

### 4.1 products 表（主表）

```sql
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    alibaba_product_id VARCHAR(64) UNIQUE NOT NULL,  -- 阿里巴巴商品ID（唯一索引）
    source_url TEXT,                                   -- 来源URL
    product_title TEXT,                                -- 原始标题
    optimized_title TEXT,                             -- 优化后标题
    product_description TEXT,                          -- 原始描述
    optimized_description TEXT,                       -- 优化后描述
    main_images JSONB,                                -- 主图URL列表
    detail_images JSONB,                              -- 详情图URL列表
    sku_list JSONB,                                   -- SKU列表
    sku_properties JSONB,                             -- SKU属性
    packaging_info JSONB,                             -- 包装信息
    category VARCHAR(255),                             -- 分类
    price_range VARCHAR(100),                         -- 价格区间
    moq INTEGER DEFAULT 1,                            -- 最小起订量
    status VARCHAR(32) DEFAULT 'pending',             -- 状态: pending/optimized/claimed/error
    shopee_product_id VARCHAR(64),                    -- Shopee商品ID（认领后）
    main_product_code VARCHAR(64),                    -- 主商品货号（Shopee唯一）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    claimed_at TIMESTAMP                              -- 认领时间
);

CREATE INDEX idx_alibaba_product_id ON products(alibaba_product_id);
CREATE INDEX idx_status ON products(status);
CREATE INDEX idx_created_at ON products(created_at);
```

### 4.2 product_images 表（图片表）

```sql
CREATE TABLE IF NOT EXISTS product_images (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    image_type VARCHAR(32),                           -- main/sku/detail
    image_url TEXT,
    local_path VARCHAR(512),                          -- 本地缓存路径
    cos_url VARCHAR(512),                            -- COS上传地址
    uploaded_to_miaoshou BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_product_id ON product_images(product_id);
```

### 4.3 collection_log 表（采集日志）

```sql
CREATE TABLE IF NOT EXISTS collection_log (
    id SERIAL PRIMARY KEY,
    alibaba_product_id VARCHAR(64),
    action VARCHAR(32),                              -- collect/optimize/claim
    status VARCHAR(16),                              -- success/failed
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 五、模块设计

### 5.1 模块列表

| 模块名 | 功能 | 输入 | 输出 |
|-------|------|------|------|
| `miaoshou-collector` | 操作妙手ERP采集 | 1688商品链接/关键词 | 公用采集箱 |
| `collector-scraper` | 爬取采集箱数据 | 采集箱产品URL | 原始商品数据 |
| `data-normalizer` | 数据标准化 | 原始数据 | 规范化JSON |
| `product-storer` | 落库 | 规范化数据 | products表记录 |
| `listing-optimizer` | Listing优化 | 原始标题/描述 | 优化后标题/描述 |
| `miaoshou-updater` | 回写妙手 | 优化后数据 | 更新成功 |
| `product-claimer` | 产品认领 | products记录 | Shopee商品ID |

### 5.2 核心模块详解

#### 5.2.1 miaoshou-collector（妙手采集模块）

**功能：** 自动操作妙手ERP Web界面发起1688采集

**操作流程：**
1. 登录妙手ERP（使用已保存的cookies）
2. 进入「采集管理」→「1688采集」
3. 输入1688商品链接或搜索关键词
4. 设置采集参数（分类/价格区间）
5. 点击采集，添加到公用采集箱

**技术方案：**
- Playwright 浏览器自动化
- 使用已保存的 `miaoshou_cookies.json`
- 无需处理1688反爬（妙手插件处理）

#### 5.2.2 collector-scraper（采集箱爬虫模块）

**功能：** 从妙手ERP公用采集箱爬取商品详情

**爬取页面：** `/collect/list`（公用采集箱列表）+ `/collect/edit/{id}`（编辑页面）

**采集字段：** 详见 3.1

**技术方案：**
- Playwright + Browser Relay（控制本地Chrome）
- 页面结构解析（CSS Selector / XPath）
- 反爬策略：请求间隔 2-5秒随机延迟

#### 5.2.3 listing-optimizer（Listing优化模块）

**功能：** 使用LLM优化商品标题和描述

**优化策略：**
- 标题：关键词植入 + 搜索友好 + 30-50字符
- 描述：核心卖点 + 规格参数 + 售后说明

**技术方案：**
- 调用 LLM API（智谱GLM-4 / OpenAI GPT）
- Prompt模板：`prompts.yaml` 中的 `listing_optimization`

#### 5.2.4 miaoshou-updater（妙手回写模块）

**功能：** 将优化后的标题/描述回写到妙手ERP编辑页面

**操作流程：**
1. 进入公用采集箱编辑页面
2. 填写优化后的标题
3. 填写优化后的描述
4. 填写主商品货号（系统生成）
5. 点击保存

#### 5.2.5 product-claimer（产品认领模块）

**功能：** 完成妙手ERP产品认领流程

**操作流程：**
1. 选中已编辑的产品
2. 点击「认领」
3. 选择目标店铺（Shopee台湾）
4. 确认分类映射
5. 完成认领，获取Shopee商品ID

---

## 六、技术架构

### 6.1 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 浏览器自动化 | Playwright + Browser Relay | 控制Chrome采集 |
| 数据库 | PostgreSQL (ecommerce_data) | 商品数据存储 |
| 对象存储 | 腾讯云COS | 图片 CDN |
| LLM API | 智谱GLM-4 / OpenAI | Listing优化 |
| 日志 | Python logging + 文件 | 日志记录 |
| 任务调度 | Cron / OpenClaw心跳 | 定时执行 |

### 6.2 目录结构

```
/home/ubuntu/work/
├── config/
│   ├── miaoshou_cookies.json      # 妙手ERP登录态
│   ├── llm_models.yaml            # LLM模型配置
│   └── prompts.yaml               # Prompt模板
├── products/                       # 商品素材目录
│   ├── {alibaba_id}/              # 按商品ID分目录
│   │   ├── main/                  # 主图
│   │   ├── detail/                # 详情图
│   │   └── sku/                   # SKU图
│   └── ...
├── logs/                           # 日志目录
│   ├── collector.log              # 采集日志
│   ├── optimizer.log              # 优化日志
│   └── claimer.log                # 认领日志
├── tmp/                            # 临时文件
└── dashboard.py                    # 监控面板

/home/ubuntu/.openclaw/skills/
├── shared/                         # 共享模块
│   ├── logger.py
│   ├── db.py
│   ├── cos_storage.py
│   └── retry_handler.py
├── miaoshou-collector/             # 新增：妙手采集
├── collector-scraper/              # 新增：采集箱爬虫
├── listing-optimizer/              # 现有改造
├── miaoshou-updater/               # 新增：妙手回写
└── product-claimer/                # 新增：产品认领
```

### 6.3 Browser Relay 配置

**问题：** 服务器IP被1688拒绝

**解决方案：** 使用Browser Relay通过本地Chrome访问

**架构：**
```
┌─────────────┐     WebSocket      ┌─────────────┐
│  服务器      │ ◄──────────────►  │  Browser    │
│  Playwright │                   │  Relay      │
└─────────────┘                   └──────┬──────┘
                                          │
                                    CDP协议
                                          │
                                    ┌──────▼──────┐
                                    │  本地Chrome │
                                    │  (已登录1688)│
                                    └─────────────┘
```

**配置步骤：**
1. 本地Chrome安装OpenClaw Browser Relay扩展
2. 扩展连接服务器
3. 采集时使用 `profile="chrome-relay"` 调用

---

## 七、执行计划

### Phase 1: 模块开发（1-2天）

| 序号 | 任务 | 优先级 | 说明 |
|------|------|--------|------|
| 1 | `collector-scraper` 采集箱爬虫 | P0 | 核心模块，最先实现 |
| 2 | `product-storer` 落库模块 | P0 | 数据落地 |
| 3 | `listing-optimizer` 优化模块 | P0 | LLM集成 |
| 4 | `miaoshou-updater` 回写模块 | P1 | 回写妙手编辑页 |
| 5 | `product-claimer` 认领模块 | P1 | 完成流程闭环 |
| 6 | `miaoshou-collector` 采集模块 | P2 | 自动发起采集 |

### Phase 2: 集成测试（1天）

| 序号 | 任务 | 说明 |
|------|------|------|
| 1 | 单模块测试 | 各模块独立运行测试 |
| 2 | 联调测试 | 全流程串联测试 |
| 3 | 异常处理 | 超时/重试/错误处理 |

### Phase 3: 自动化优化（1天）

| 序号 | 任务 | 说明 |
|------|------|------|
| 1 | 定时任务 | Cron配置 |
| 2 | 监控告警 | 飞书通知 |
| 3 | 仪表盘 | Streamlit面板 |

---

## 八、风险与对策

| 风险 | 概率 | 影响 | 对策 |
|------|------|------|------|
| 妙手Web界面改版 | 中 | 高 | XPath/CSS选择器参数化，定期维护 |
| Browser Relay连接不稳定 | 中 | 中 | 本地Chrome保活 + 自动重连 |
| LLM API调用失败 | 低 | 中 | 降级到规则匹配 + 重试机制 |
| COS上传超时 | 低 | 低 | 异步上传 + 失败重试 |

---

## 九、验收标准

### 9.1 功能验收

| 测试项 | 预期结果 | 验证方法 |
|--------|----------|----------|
| 采集箱爬虫 | 成功提取商品完整信息 | 单商品测试 |
| 数据落库 | 字段完整率 ≥ 95% | 数据库查询统计 |
| Listing优化 | 标题/描述非空，格式正确 | 输出文件检查 |
| 妙手回写 | 编辑页保存成功 | 页面刷新验证 |
| 产品认领 | 获得Shopee商品ID | 后台查询 |

### 9.2 性能要求

| 指标 | 要求 |
|------|------|
| 单商品处理时间 | ≤ 5分钟（不含LLM等待） |
| 日处理能力 | ≥ 100商品 |
| 成功率 | ≥ 90% |

---

## 十、后续扩展

1. **多平台支持：** 台湾虾皮 → Lazada → Shopee多站点
2. **批量采集：** 关键词批量采集 + 智能选品
3. **竞品监控：** 竞品价格/库存监控
4. **数据分析：** 爆款分析 + 趋势预测

---

*文档由 CommerceFlow 自动生成*
*最后更新：2026-03-20*
