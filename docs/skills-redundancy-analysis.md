# 技能代码功能分析与冗余检测

**分析日期：** 2026-03-19
**分析范围：** /home/ubuntu/Documents/skill_learn/

---

## 一、整体数据流

```
1688商品链接
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  product-collector   (scrape.py)                           │
│  - Playwright动态抓取                                        │
│  - 下载图片/视频                                            │
│  - 落库 products + product_skus                            │
│  - 调用 listing_generator 生成文字                          │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  listing文字（已落库）                                       │
│  shopee_name / shopee_description /                        │
│  shopee_category_id / shopee_sku_name                      │
└─────────────────────────────────────────────────────────────┘
    │
    ├──────────────────────────────────────────────┐
    ▼                                              ▼
┌─────────────────────┐              ┌─────────────────────────┐
│  image-reviewer    │              │  listing-updater       │
│  AI审查商品图片     │              │  批量更新Shopee listing │
│  (已有listing跳过)  │              │  (从Shopee导出模板)     │
└─────────────────────┘              └─────────────────────────┘
    │                                              │
    ▼                                              ▼
┌─────────────────────┐              ┌─────────────────────────┐
│  product-uploader   │              │  输出 mass_update_*.xlsx │
│  打包ZIP            │              │  (上传Shopee)           │
└─────────────────────┘              └─────────────────────────┘
    │
    ▼
┌─────────────────────┐
│  miaoshou-uploader │
│  上传到妙手ERP     │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  shopee_taiwan     │
│  成本利润分析      │
└─────────────────────┘
```

---

## 二、核心技能文件清单

### 2.1 product-collector（采集）

| 文件 | 行数 | 用途 | 是否必需 |
|------|------|------|----------|
| scrape.py | 485 | **主入口**：采集+落库+LLM生成 | ✅ 核心 |
| dynamic_scraper.py | 1461 | Playwright爬虫引擎 | ✅ 核心 |
| listing_generator.py | 307 | LLM文字生成 | ✅ 核心 |
| base.py | 140 | 爬虫基类+数据模型 | ✅ 核心 |
| image_processor.py | 238 | 图片处理工具 | ⚠️ 可能未使用 |
| scrape_quiet.py | 99 | 静默采集（无日志） | ❌ 冗余 |
| scrape_all.py | 71 | 批量采集 | ❌ 冗余（可用循环） |
| run_scrape.py | 55 | 调试用批量采集 | ❌ 冗余 |
| debug_scrape.py | 47 | 调试脚本 | ❌ 冗余 |
| test_run.py | 35 | 测试脚本 | ❌ 冗余 |
| migrate_listing_fields.py | 21 | DB字段迁移 | ⚠️ 一次性 |
| __init__.py | 0 | 空文件 | ❌ 无用 |

**冗余问题：**
- `scrape_quiet.py`, `scrape_all.py`, `run_scrape.py` 功能重复，都是批量采集
- `listing_generator.py` 存在于两处（见下文）

### 2.2 listing-generator（独立）

| 文件 | 行数 | 用途 | 是否必需 |
|------|------|------|----------|
| listing_generator.py | ~307+ | **独立LLM生成器** | ✅ 核心 |

**问题：`listing_generator.py` 存在两个版本**

| 位置 | 差异 |
|------|------|
| product-collector/listing_generator.py | 基础版，缺少 `get_hot_search_words_by_similarity` |
| listing-generator/listing_generator.py | 增强版，多了 `get_hot_search_words_by_similarity` 相似度搜索 |

**结论：** product-collector 的 scrape.py 应该引用独立的 listing-generator，而不是内置版本。

### 2.3 listing-updater（批量更新）

| 文件 | 行数 | 用途 | 是否必需 |
|------|------|------|----------|
| listing_updater.py | 485 | **核心**：读取Shopee导出→优化→生成更新模板 | ✅ 核心 |

**冗余问题：**
- `listing_updater.py` 内部实现了 `LLMClient` 和 `optimize_title`，与 `listing_generator.py` 重复
- 它 import 了 `listing_generator`，但同时自己写了一套 LLM 调用逻辑

### 2.4 image-reviewer（图片审查）

| 文件 | 行数 | 用途 | 是否必需 |
|------|------|------|----------|
| image_reviewer.py | 600+ | AI审查商品图片 | ✅ 核心 |

**评价：** 独立模块，无明显冗余。

### 2.5 product-uploader（打包）

| 文件 | 行数 | 用途 | 是否必需 |
|------|------|------|----------|
| data_transformer.py | 500+ | **核心**：生成Excel+整理图片+打包ZIP | ✅ 核心 |
| fix_and_upload.py | 60 | 重置状态+重新打包+上传 | ⚠️ 便捷脚本 |
| _setup_db.py | 40 | DB扩展脚本 | ⚠️ 一次性 |

**冗余问题：**
- `_setup_db.py` 和 `migrate_listing_fields.py` 功能重复（都是一次性DB脚本）

### 2.6 miaoshou-uploader（上传妙手）

| 文件 | 行数 | 用途 | 是否必需 |
|------|------|------|----------|
| uploader.py | 192 | **核心**：ZIP上传妙手ERP | ✅ 核心 |
| login_miaoshou.py | 123 | 登录（Playwright） | ✅ 核心 |
| test_api.py | 24 | API测试 | ❌ 冗余 |
| run_test.py | 9 | 测试运行 | ❌ 冗余 |

### 2.7 shopee_taiwan（利润分析）

| 文件 | 行数 | 用途 | 是否必需 |
|------|------|------|----------|
| shopee_taiwan_profit_analyzer.py | 773 | **核心**：成本利润计算 | ✅ 核心 |
| export_report.py | 66 | 报告导出 | ⚠️ 便捷脚本 |
| check_db.py | 42 | DB检查 | ❌ 冗余 |
| check_tables.py | 20 | 表检查 | ❌ 冗余 |

---

## 三、冗余功能详细分析

### 3.1 LLM Client 重复实现（严重）

| 文件 | 类名 | async | 说明 |
|------|------|-------|------|
| listing-generator/listing_generator.py | `_LLMClient` | ✅ | 异步调用 |
| product-collector/listing_generator.py | `_LLMClient` | ✅ | 异步调用（重复） |
| listing-updater/listing_updater.py | `LLMClient` | ❌ | 同步调用（重复） |

**问题：** 三个地方实现了几乎相同的 LLM 调用逻辑。

**建议：** 统一为一个 `LLMClient` 模块，所有技能共享。

### 3.2 listing_generator 重复（严重）

**两个版本：**
1. `product-collector/listing_generator.py` - 被 scrape.py 引用
2. `listing-generator/listing_generator.py` - 被 listing-updater 引用

**差异：**
- 独立版多了 `get_hot_search_words_by_similarity` 方法（使用 pg_trgm 相似度搜索）
- 产品采集版是简化版

**建议：**
- 合并为一个统一的 `listing_generator`
- scrape.py 应引用 `listing-generator/listing_generator.py`

### 3.3 Prompt 加载重复

| 文件 | 实现 |
|------|------|
| listing-generator/listing_generator.py | `_PromptLoader` class |
| listing-updater/listing_updater.py | 直接用 `yaml.load()` |

**建议：** 统一用 `prompts.yaml` 加载工具函数。

### 3.4 数据库连接重复

几乎每个涉及数据库的文件都有自己的 `_db_conn()` 或 `DB` 类：

| 文件 | 实现方式 |
|------|----------|
| product-collector/scrape.py | `_db_conn()` 函数 |
| product-collector/listing_generator.py | `_DB` 类 |
| listing-generator/listing_generator.py | `_DB` 类（重复） |
| listing-updater/listing_updater.py | `DB` 类（重复） |
| shopee_taiwan_profit_analyzer.py | `get_conn()` 函数 |

**建议：** 统一为一个 `db.py` 共享模块。

### 3.5 一次性调试/测试脚本（建议删除）

| 文件 | 问题 |
|------|------|
| check_db.py | 调试用 |
| check_tables.py | 调试用 |
| test_run.py | 调试用 |
| debug_scrape.py | 调试用 |
| test_api.py | 调试用 |
| run_test.py | 调试用 |
| __init__.py | 空文件 |

---

## 四、建议的精简方案

### 4.1 合并重复模块

```
建议结构：
/skills/
├── shared/                    # 共享模块
│   ├── db.py                # 统一数据库连接
│   ├── llm_client.py        # 统一LLM调用
│   └── prompts.py           # 统一Prompt加载
│
├── product-collector/        # 采集技能
│   ├── scrape.py           # 主入口
│   ├── dynamic_scraper.py   # 爬虫引擎
│   ├── base.py             # 数据模型
│   └── SKILL.md
│
├── listing-generator/         # Listing生成（唯一版本）
│   ├── listing_generator.py
│   └── SKILL.md
│
├── image-reviewer/           # 图片审查
│   ├── image_reviewer.py
│   └── SKILL.md
│
├── product-uploader/         # 打包上传
│   ├── data_transformer.py
│   ├── SKILL.md
│   └── _setup_db.py         # 一次性（可选）
│
├── listing-updater/          # Listing更新
│   ├── listing_updater.py
│   └── SKILL.md
│
├── miaoshou-uploader/        # 妙手上传
│   ├── uploader.py
│   ├── login_miaoshou.py
│   └── SKILL.md
│
└── shopee-taiwan/          # 利润分析
    ├── shopee_taiwan_profit_analyzer.py
    └── SKILL.md
```

### 4.2 可删除文件清单

| 文件 | 原因 |
|------|------|
| product-collector/scrape_quiet.py | 功能与scrape.py重复 |
| product-collector/scrape_all.py | 功能与scrape.py重复 |
| product-collector/run_scrape.py | 调试用一次性脚本 |
| product-collector/debug_scrape.py | 调试用一次性脚本 |
| product-collector/test_run.py | 调试用一次性脚本 |
| product-collector/__init__.py | 空文件 |
| product-collector/listing_generator.py | 与独立版重复，应引用独立版 |
| miaoshou-uploader/test_api.py | 调试用一次性脚本 |
| miaoshou-uploader/run_test.py | 调试用一次性脚本 |
| shopee_taiwan/check_db.py | 调试用一次性脚本 |
| shopee_taiwan/check_tables.py | 调试用一次性脚本 |
| product-uploader/fix_and_upload.py | 与data_transformer+uploader流程重复 |

### 4.3 需要重构的文件

| 文件 | 重构内容 |
|------|----------|
| scrape.py | 改 import listing_generator 为独立版 |
| listing_updater.py | 删除内部LLMClient，使用共享模块 |
| 所有文件 | 统一数据库连接为 shared/db.py |

---

## 五、工作量估算

| 任务 | 时间 | 说明 |
|------|------|------|
| 删除冗余文件 | 15分钟 | 批量删除 |
| 合并 listing_generator | 30分钟 | 统一为一个版本 |
| 创建 shared 模块 | 2小时 | db.py + llm_client.py + prompts.py |
| 重构 listing_updater | 1小时 | 使用 shared 模块 |
| 更新所有 import | 1小时 | 路径修改 |
| 测试验证 | 2小时 | 全流程测试 |

**总计：约 7 小时**

---

## 六、核心流程确认

精简后，每个技能的职责非常清晰：

```
1688链接
  │
  ▼
product-collector (scrape.py)
  ├─► dynamic_scraper: 抓取页面
  ├─► 下载图片/视频到本地
  ├─► 保存 products + product_skus
  └─► listing_generator: 生成listing文字
  │
  ▼
local files + DB
  │
  ├────────────┬────────────┐
  ▼            ▼            ▼
image-reviewer listing-    product-
  │         updater         uploader
  │             │              │
  │         导出模板    打包ZIP
  │             │              │
  │             ▼              ▼
  │         mass_       miaoshou-
  │         update.xlsx  uploader
  │             │              │
  └────────────┴────────────►shopee
                                    │
                                    ▼
                              shopee_taiwan
                              (利润分析)
```

---

## 七、结论

**冗余程度：中等**

主要问题：
1. `listing_generator.py` 有两个版本，需要合并
2. LLM Client 实现了三次，需要统一
3. 存在大量一次性调试脚本
4. 数据库连接逻辑分散在各处

**建议优先级：**
1. **高**：合并 listing_generator（影响采集流程）
2. **高**：创建 shared 模块统一 db 和 llm_client
3. **中**：删除所有调试/测试脚本
4. **低**：重构 listing_updater 使用 shared 模块
