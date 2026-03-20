# collector-scraper 模块测试记录

> 本文档记录 collector-scraper 模块的开发、测试和验收过程。
> 文档版本：v2.0
> 创建时间：2026-03-20
> 更新时间：2026-03-20 13:54
> 测试状态：🔄 开发中（主要问题已修复）

---

## 一、模块概述

### 1.1 目标
从妙手ERP的Shopee采集箱爬取商品完整数据

### 1.2 代码位置
`/home/ubuntu/.openclaw/skills/collector-scraper/scraper.py`

---

## 二、测试用例

### TC-CS-001: 获取商品列表

**日期：** 2026-03-20  
**结果：** ✅ 通过

```
$ python3 scraper.py --list

============================================================
商品列表 (共 3 个):
  [0] 1027205078815 - N/A
  [1] 965854175819 - N/A
  [2] 1026640656479 - N/A
============================================================
```

---

### TC-CS-002: 爬取商品完整数据

**日期：** 2026-03-20 13:54  
**结果：** ⚠️ 大部分通过

**执行命令：**
```bash
$ python3 scraper.py --scrape 0
```

**提取结果（v2.0）：**

| 数据项 | 状态 | 实际值 |
|--------|------|--------|
| 货源ID | ✅ | 1027205078815 |
| 标题 | ✅ | 日式复古风实木竹编收纳筐... |
| 类目 | ✅ | 收纳盒、收纳包与篮子 |
| 品牌 | - | None |
| 主图数量 | ✅ | 14张 |
| SKU数量 | ✅ | 3个 |
| 规格 | ✅ | 颜色:深棕色, 尺寸:大号/小号/一套 |
| 描述长度 | ✅ | 354字符 |
| 物流 | ⚠️ | {} (虚拟表格限制) |

---

## 三、修复记录

### 修复1: 货源ID提取 - 2026-03-20 13:51 ✅

**问题：** 货源ID未提取，显示None

**原因：** 货源ID不在输入框中，而是在链接里：`href="http://detail.1688.com/offer/1027205078815.html"`

**修复方案：**
```python
# 从链接中提取货源ID
links = body.query_selector_all('a[href*="1688.com/offer"]')
for link in links:
    href = link.get_attribute('href') or ''
    match = re.search(r'/offer/(\d+)\.html', href)
    if match:
        data['alibaba_product_id'] = match.group(1)
```

---

### 修复2: SKU数量修正 - 2026-03-20 13:54 ✅

**问题：** SKU数量显示2个，实际应为3个

**原因：** 虚拟表格使用自定义渲染，传统table查询无效

**修复方案：**
```python
# 从输入框提取规格和选项
specs = {}
for inp in inputs:
    ph = inp.get_attribute('placeholder') or ''
    val = inp.input_value() or ''
    
    if '请输入规格名称' == ph and val:
        current_spec_name = val
        specs[current_spec_name] = []
    elif '请输入选项名称' == ph and val:
        specs[current_spec_name].append(val)

# 组合规格生成SKU
# 颜色: 深棕色
# 尺寸: 大号35*25*16cm, 小号30*20*14cm, 一套（大小号）
# = 3个SKU
```

---

## 四、技术要点

### 4.1 JavaScript点击
Vue单页应用需要JS触发点击事件：
```javascript
page.evaluate('''
    () => {
        var btns = document.querySelectorAll("button");
        for (var b of btns) {
            if (b.innerText.trim() === "编辑") {
                b.click();
                return;
            }
        }
    }
''')
```

### 4.2 虚拟表格
妙手ERP使用虚拟表格（jx-pro-virtual-table），不是标准HTML table，数据需要从输入框提取。

### 4.3 对话框选择器
```python
dialogs = page.query_selector_all('.el-dialog__wrapper')
for d in dialogs:
    cls = d.get_attribute('class') or ''
    if 'collect-box-edit' in cls and d.is_visible():
        return d
```

---

## 五、待处理问题

### 物流信息提取 ⬜

**问题：** 物流信息（重量、尺寸）未提取

**原因：** 物流Tab在虚拟表格底部，需要滚动或切换Tab

**影响：** 当前数据可用于基本展示，落库时需要手动补充或通过其他方式获取

**优先级：** P2（可延后）

---

## 六、测试环境

| 项目 | 值 |
|------|-----|
| 浏览器 | Chromium (headless) |
| 操作系统 | Ubuntu Linux |
| Playwright | 1.40+ |
| 测试链接 | Shopee采集箱 `/shopee/collect_box/items` |
| 测试商品 | 1027205078815 |

---

## 七、下一步

1. ⬜ 物流信息提取（可选，P2优先级）
2. 🔄 product-storer 模块开发
3. ⬜ listing-optimizer 模块开发

---

*创建时间：2026-03-20*
*最后更新：2026-03-20 13:54*
