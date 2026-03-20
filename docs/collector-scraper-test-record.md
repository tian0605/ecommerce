# collector-scraper 模块测试记录

> 本文档记录 collector-scraper 模块的开发、测试和验收过程。
> 文档版本：v1.0
> 创建时间：2026-03-20
> 测试状态：🔄 开发中

---

## 一、模块概述

### 1.1 目标
从妙手ERP的Shopee采集箱爬取商品完整数据，包括：
- 标题、描述、类目、品牌
- 主图、SKU图片
- SKU信息（价格、库存、规格）
- 物流信息

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

**说明：** 成功从Shopee采集箱列表提取3个商品的货源ID。

---

### TC-CS-002: 爬取商品完整数据

**日期：** 2026-03-20  
**结果：** ⚠️ 部分通过（SKU数量不准确）

**执行命令：**
```bash
$ python3 scraper.py --scrape 0
```

**提取结果：**

| 数据项 | 状态 | 实际值 | 预期值 |
|--------|------|--------|--------|
| 货源ID | ⚠️ | None | 1027205078815 |
| 标题 | ✅ | 日式复古风实木竹编收纳筐... | - |
| 类目 | ✅ | 收纳盒、收纳包与篮子 | - |
| 品牌 | - | None | - |
| 主图数量 | ✅ | 14张 | - |
| SKU数量 | ⚠️ | 2个 | 3个(深棕色大号/小号/一套)|
| 描述长度 | ✅ | 354字符 | - |
| 物流 | ⚠️ | {} | 有重量数据 |

**截图：**
- 列表截图：`list_before_edit_20260320_130429.png`
- 编辑对话框：`edit_dialog_20260320_130434.png`

---

## 三、页面结构分析

### 3.1 编辑对话框结构

通过调试发现，编辑对话框的class为：
```
el-dialog__wrapper jx-pro-dialog collect-box-edit-modal base-item-edit-dialog
```

**对话框内关键区域：**

| 区域 | 选择器 | 内容 |
|------|--------|------|
| 基本信息 Tab | `.el-dialog__body` | 标题、描述、类目属性 |
| 销售属性 Tab | `table.el-table` | SKU列表 |
| 产品图片 Tab | `[class*="product-image"]` | 主图列表 |
| 物流信息 Tab | `.el-dialog__body` | 重量、尺寸 |

### 3.2 提取到的数据示例

**主图列表（14张）：**
```
img[0]: https://cbu01.alicdn.com/img/ibank/O1CN01gHxh7Z1MJfA9qANq9_!!2221100551414-0-cib.jpg_.webp
img[2]: https://cbu01.alicdn.com/img/ibank/O1CN01PUY5YM1Lu0wQT3edZ_!!963601358-0-cib.jpg_.webp
img[4]: https://earth-rt.chengji-inc.com/temp_dir/d60/import_task_file/13016460/b79aae4f946896c52f36d4b348feb3cb.jpg
... (共14张)
```

**SKU数据（实际应提取到3个）：**
```
SKU[0]: 深棕色 / 大号35*25*16cm / 售价36.80 / 货源价30 / 库存495 / 重量0.63kg
SKU[1]: 深棕色 / 小号30*20*14cm / 售价76.80 / 货源价36.8 / 库存495 / 重量0.85kg
SKU[2]: 深棕色 / 一套 / 售价76.80 / 货源价25 / 库存500 / 重量1.37kg
```

**描述文本（前500字符）：**
```
材质：木制
功能：整理
产品类别：杂物收纳筐
品牌：其他
容量：45
收纳场景：其它,客厅,卧室,书房,桌上
是否进口：否
型号：1117
具体材质：松木
商品特性：其他
适用范围：CD,遥控器,首饰,手机,纸巾,其他
风格：现代简约
...
```

---

## 四、待修复问题

### 4.1 货源ID未提取
**原因：** 选择器未匹配到货源ID输入框
**位置：** 对话框body中的输入框，placeholder包含"货源ID"或"主货号"
**修复方案：** 添加对货源ID输入框的提取逻辑

### 4.2 SKU数量不准确
**原因：** SKU表格提取逻辑只匹配到了2个，实际有3个
**修复方案：** 优化SKU表格解析逻辑

### 4.3 物流信息未提取
**原因：** 对话框中物流Tab可能未激活，内容未加载
**修复方案：** 需要切换到物流Tab后再提取

---

## 五、已验证的关键技术点

### 5.1 JavaScript点击
Vue单页应用需要使用JavaScript触发点击事件：
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

### 5.2 对话框选择器
```python
dialogs = page.query_selector_all('.el-dialog__wrapper')
for d in dialogs:
    cls = d.get_attribute('class') or ''
    if 'collect-box-edit' in cls and d.is_visible():
        return d
```

### 5.3 图片提取
```python
for img in body.query_selector_all('img'):
    src = img.get_attribute('src') or ''
    if 'data:image' not in src and 'alicdn.com' in src:
        main_images.append(src)
```

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

1. 修复货源ID提取
2. 修复SKU数量（应提取到3个）
3. 修复物流信息提取
4. 完善数据落库到 PostgreSQL

---

*创建时间：2026-03-20*
*最后更新：2026-03-20*
