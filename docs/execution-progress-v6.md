# 执行进度追踪 v6

**项目：** 自动采集方案 v6
**创建日期：** 2026-03-20
**版本：** v6.0（Shopee采集箱工作流）
**状态：** 执行中

---

## 执行概览

| 模块 | 技术方案 | 状态 | 完成度 | 备注 |
|------|----------|------|--------|------|
| miaoshou-collector | Playwright+Chromium | 🔄 开发中 | 80% | 代码完成，待测试 |
| shopee-collector | Playwright+Chromium | 🔄 待开发 | 0% | - |
| product-storer | PostgreSQL | 🔄 待开发 | 0% | - |
| listing-optimizer | LLM API | 🔄 待开发 | 0% | - |
| miaoshou-updater | Playwright+Chromium | 🔄 待开发 | 0% | - |

**总进度：** 16.7% (1/6 模块)

---

## 技术方案修正

### 关键变化：Shopee采集箱 vs 公用采集箱

| 对比项 | 旧方案 | 新方案 |
|--------|--------|--------|
| 采集后位置 | 公用采集箱 | Shopee采集箱 |
| fetchType参数 | `public` | `shopeeCopy` |
| 采集按钮 | "采集" | "采集并自动认领" |

### URL参数对照

| 页面 | fetchType | URL |
|------|-----------|-----|
| 产品采集 | `linkCopy` | `/common_collect_box/index?fetchType=linkCopy` |
| 公用采集箱 | `public` | `/common_collect_box/index?fetchType=public` |
| Shopee采集箱 | `shopeeCopy` | `/common_collect_box/index?fetchType=shopeeCopy` |

---

## 模块详情

### 🔄 1. miaoshou-collector（开发中）

**功能：** 在产品采集页面发起1688采集，商品自动认领到Shopee采集箱

**技术方案：**
- Playwright + Chromium（headless模式）
- 点击「采集并自动认领」按钮

**代码交付物：**
- ✅ `collector.py`（16KB）
- ✅ `__init__.py`
- ✅ `miaoshou_cookies.json`（软链接）

**待测试：**
- TC-MC-001：产品采集→Shopee采集箱验证

**测试交付物：**
- [ ] tc_mc_001_page.png
- [ ] tc_mc_001_link_filled.png
- [ ] tc_mc_001_result.png
- [ ] tc_mc_001_list.png
- [ ] tc_mc_001_product.png

---

### 🔄 2. shopee-collector（待开发）

**功能：** 从Shopee采集箱编辑页爬取商品完整数据

**页面：** `/common_collect_box/edit/{id}?fetchType=shopeeCopy`

**待交付：**
- [ ] `scraper.py`
- [ ] `__init__.py`

---

### 🔄 3. product-storer（待开发）

**功能：** 将采集数据落库至 products 表

**待交付：**
- [ ] `storer.py`
- [ ] `__init__.py`

---

### 🔄 4. listing-optimizer（待开发）

**功能：** 主商品货号生成 + AI标题优化 + AI描述优化

**待交付：**
- [ ] `optimizer.py`
- [ ] `__init__.py`

---

### 🔄 5. miaoshou-updater（待开发）

**功能：** 回写货号/标题/描述到Shopee采集箱编辑页

**页面：** `/common_collect_box/edit/{id}?fetchType=shopeeCopy`

**待交付：**
- [ ] `updater.py`
- [ ] `__init__.py`

---

## 执行日志

### 2026-03-20

| 时间 | 模块 | 操作 | 结果 |
|------|------|------|------|
| 11:54 | - | 用户确认正确流程 | ✅ |
| 12:06 | - | 更新方案和测试用例v6 | ✅ |

---

## 相关文档

- 方案文档：`docs/new-collection-workflow-v6.md`
- 测试用例：`docs/module-test-cases-v6.md`

---

*由 CommerceFlow 自动追踪*
*最后更新：2026-03-20 12:06*
