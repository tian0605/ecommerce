# 自动采集方案 v6 - 基于妙手ERP工作流

**创建日期：** 2026-03-20
**版本：** v5.0（明确技术方案：无需Browser Relay）
**状态：** 方案设计

---

## 一、背景与目标

### 1.1 问题痛点
- **1688 IP反爬限制：** 服务器IP直接访问1688被拒绝（Access Denied）
- **妙手ERP解决方案：** 妙手ERP服务器自带1688插件，可正常访问1688

### 1.2 技术方案

**核心思路：**
- 妙手ERP服务器访问1688（不受IP限制）
- 我们通过Playwright直接操作妙手ERP的Web管理界面
- **无需Browser Relay插件**

**已验证：**
- `erp.91miaoshou.com` 服务器可正常访问（HTTP 200）
- 妙手ERP自带「链接采集」功能，可采集1688商品

### 1.3 目标
构建**全自动化**的商品采集 → 优化 → 上架 workflow

---

## 二、技术架构

### 2.1 技术选型

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 浏览器自动化 | Playwright + Chromium | 直接启动Chromium，无需Browser Relay |
| 数据库 | PostgreSQL (ecommerce_data) | 商品数据存储 |
| 对象存储 | 腾讯云COS | 图片CDN |
| LLM API | 智谱GLM-4 / OpenAI | Listing优化 |
| 日志 | Python logging | 日志记录 |

### 2.2 为什么不需要Browser Relay？

| 对比项 | 旧方案（否决） | 新方案（采用） |
|--------|---------------|---------------|
| 1688访问 | Browser Relay通过本地Chrome | 妙手ERP服务器访问1688 |
| 妙手ERP访问 | 需要Browser Relay | Playwright直接访问 |
| 插件依赖 | 需要安装Browser Relay扩展 | 无需插件 |

**结论：**
- 1688的IP反爬问题 → 由妙手ERP解决（妙手服务器IP不受限）
- 妙手ERP的Web界面 → 我们直接访问（服务器IP可访问）

### 2.3 目录结构

```
/home/ubuntu/.openclaw/skills/
├── shared/                      # 共享模块
│   ├── logger.py              # 日志
│   ├── db.py                  # 数据库
│   └── retry_handler.py       # 重试
├── miaoshou-collector/        # ✅ 已开发
│   ├── __init__.py
│   ├── collector.py            # 妙手ERP采集
│   └── miaoshou_cookies.json  # 链接到配置
├── collector-scraper/          # 待开发
├── product-storer/             # 待开发
├── listing-optimizer/         # 待开发
├── miaoshou-updater/           # 待开发
└── product-claimer/           # 待开发
```

---

## 三、整体流程架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        新版自动采集工作流 v6                              │
└─────────────────────────────────────────────────────────────────────────┘

Step 1: 产品采集页面
    │
    │  [Playwright → erp.91miaoshou.com]
    ▼
┌─────────────────────────────────┐
│  产品采集页面                     │ ◄── URL: /common_collect_box/index?fetchType=1688Product
│  → 输入1688商品链接               │
│  → 点击「采集」                   │
│  → 妙手ERP服务器访问1688           │ ← 关键：妙手IP访问1688，不受反爬限制
│  → 采集成功提示                   │
└───────────────┬─────────────────┘
                │
                │ 数据自动进入
                ▼
Step 2: 公用采集箱页面
    │
    │  [Playwright → erp.91miaoshou.com]
    ▼
┌─────────────────────────────────┐
│  公用采集箱                       │ ◄── URL: /common_collect_box/index?fetchType=public
│  → 验证商品已在列表中              │
│  → 点击「编辑」进入编辑页面         │
└───────────────┬─────────────────┘
                │
                ▼
Step 3: 采集箱数据爬取
    │
    │  [Playwright → erp.91miaoshou.com/collect/edit/{id}]
    ▼
┌─────────────────────────────────┐
│  公用采集箱编辑页面                │ ◄── 从页面提取完整商品信息
│  → 标题/描述/主图/SKU图/详情图     │
│  → 阿里巴巴商品ID                │
│  → 库存/价格/SKU信息             │
└───────────────┬─────────────────┘
                │
                ▼
Step 4: 数据落库
    │
    │  [Python + PostgreSQL]
    ▼
┌─────────────────────────────────┐
│  ecommerce_data.products 表     │ ◄── 唯一索引: alibaba_product_id
│  → 原始数据落库                  │
│  → status = 'pending'           │
└───────────────┬─────────────────┘
                │
                ▼
Step 5: Listing优化
    │
    │  [LLM API调用]
    ▼
┌─────────────────────────────────┐
│  标题优化                        │ ◄── AI生成优质标题
│  描述优化                        │
│  → optimized_title/description  │
│  → status = 'optimized'         │
└───────────────┬─────────────────┘
                │
                ▼
Step 6: 回写妙手ERP
    │
    │  [Playwright → 公用采集箱编辑页]
    ▼
┌─────────────────────────────────┐
│  公用采集箱编辑页面               │ ◄── 填写优化后的标题/描述/货号
│  → 保存                          │
└───────────────┬─────────────────┘
                │
                ▼
Step 7: 产品认领
    │
    │  [Playwright → 公用采集箱列表页]
    ▼
┌─────────────────────────────────┐
│  产品认领                        │ ◄── 选中商品，点击认领
│  → Shopee台湾                   │
│  → 获得 shopee_product_id       │
│  → status = 'claimed'           │
└─────────────────────────────────┘
```

---

## 四、妙手ERP页面说明

### 4.1 两个独立页面

| 页面 | URL参数 | 功能 | 操作 |
|------|---------|------|------|
| **产品采集** | `?fetchType=1688Product` | 发起1688采集 | 输入链接，点击「采集」 |
| **公用采集箱** | `?fetchType=public` | 存储已采集商品 | 查看列表，点击「编辑」 |

### 4.2 流程说明

```
1. 在「产品采集」页面输入1688链接，点击「采集」
   ↓
2. 妙手ERP服务器访问1688，获取商品信息
   ↓
3. 采集完成后，商品自动进入「公用采集箱」
   ↓
4. 在「公用采集箱」查看商品列表，点击「编辑」进行后续操作
```

---

## 五、执行计划

### Phase 1: 模块开发

| 序号 | 模块 | 优先级 | 说明 |
|------|------|--------|------|
| 1 | miaoshou-collector | ✅ 已完成 | 产品采集页面操作 |
| 2 | collector-scraper | 🔄 待开发 | 公用采集箱编辑页爬取 |
| 3 | product-storer | 🔄 待开发 | 落库模块 |
| 4 | listing-optimizer | 🔄 待开发 | LLM优化 |
| 5 | miaoshou-updater | 🔄 待开发 | 回写公用采集箱 |
| 6 | product-claimer | 🔄 待开发 | 产品认领 |

### Phase 2: 测试验证

按测试用例文档执行（见 `module-test-cases-v4.md`）

---

## 六、技术要点

### 6.1 Playwright配置

```python
from playwright.sync_api import sync_playwright

# 启动Chromium（无需Browser Relay）
browser = playwright.chromium.launch(
    headless=False,  # 开发模式显示窗口，部署时改为True
    args=['--no-sandbox', '--disable-dev-shm-usage']
)

# 设置妙手ERP cookies
context.add_cookies(playwright_cookies)

# 访问妙手ERP
page.goto('https://erp.91miaoshou.com/common_collect_box/index?fetchType=1688Product')
```

### 6.2 Cookies配置

Cookies文件：`/home/ubuntu/work/config/miaoshou_cookies.json`

导出方法：
1. 在浏览器登录 `erp.91miaoshou.com`
2. 开发者工具 → Application → Cookies
3. 导出为JSON格式

---

## 七、风险与对策

| 风险 | 概率 | 影响 | 对策 |
|------|------|------|------|
| 妙手ERP页面改版 | 中 | 高 | 选择器参数化，定期维护 |
| Cookies过期 | 低 | 高 | 定期更新cookies |
| 采集超时/失败 | 中 | 中 | 添加重试机制，状态检查 |

---

*文档由 CommerceFlow 自动生成*
*版本：v5.0*
*最后更新：2026-03-20*
