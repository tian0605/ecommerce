# 开发任务队列

> 记录当前开发任务、问题和待办事项
> 最后更新：2026-03-20 13:05

---

## 当前任务

### collector-scraper 模块 🔄

**优先级：** P0  
**状态：** 测试阶段  
**问题：** 3个

#### 问题列表

| # | 问题 | 优先级 | 状态 | 备注 |
|---|------|--------|------|------|
| 1 | 货源ID未提取 | P0 | 🔄 修复中 | 应提取到 `1027205078815` |
| 2 | SKU数量不准确 | P0 | 🔄 修复中 | 应提取到3个，实际2个 |
| 3 | 物流信息未提取 | P1 | ⬜ 待处理 | 重量、尺寸未提取 |

#### 修复方案

**问题1 - 货源ID提取：**
```python
# 在 _extract_dialog_data 中添加：
for inp in body.query_selector_all('input'):
    try:
        val = inp.input_value() or ''
        # 货源ID格式：纯数字，10位以上
        if re.match(r'^\d{10,}$', val):
            data['alibaba_product_id'] = val
            break
    except: pass
```

**问题2 - SKU数量：**
- 需要解析表格中的所有tr行
- 每个SKU可能有多行（多规格）

**问题3 - 物流信息：**
- 需要滚动到物流Tab区域
- 物流区域在对话框底部

---

## 下一步任务

### product-storer 模块 ⬜

**前置条件：** collector-scraper 完成  
**依赖：** 需要完整的商品数据结构

**目标：** 将商品数据落库到 PostgreSQL

**数据库表：** `ecommerce_data.products`

---

## 已完成任务

### ✅ miaoshou-collector 模块

**完成时间：** 2026-03-20 12:50  
**测试用例：** TC-MC-001 ✅ 通过  
**文档：** `docs/miaoshou-collector-completion-report.md`

### ✅ collector-scraper 基础框架

**完成时间：** 2026-03-20 13:04  
**状态：** 基础功能可用，待修复3个问题

---

## 待新增模块

| 模块 | 状态 | 备注 |
|------|------|------|
| miaoshou-collector | ✅ | TC-MC-001 通过 |
| collector-scraper | 🔄 | 3个问题待修复 |
| product-storer | ⬜ | 待开发 |
| listing-optimizer | ⬜ | 待开发 |
| miaoshou-updater | ⬜ | 待开发 |

---

*最后更新：2026-03-20 13:05*
