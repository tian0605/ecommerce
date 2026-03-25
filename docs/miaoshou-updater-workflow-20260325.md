# miaoshou-updater 完整工作流程文档

> **日期：** 2026-03-25  
> **版本：** v1.0  
> **商品测试：** 1026175430866（发饰收纳盒）

---

## 一、完整操作流程

### 1.1 流程总览

```
[Step 1] 打开妙手ERP商品列表
[Step 2] 定位目标商品（按alibaba_id）
[Step 3] 点击【编辑】按钮
[Step 4] 填写7个字段（标题/描述/主货号/重量/尺寸/类目）
[Step 5] 点击【保存并发布】
[Step 6] 在发布弹窗勾选全选店铺
[Step 7] 点击【确定发布】
[Step 8] 关闭发布成功后的弹窗
```

### 1.2 详细步骤

#### Step 1-2: 打开页面并定位商品

```python
page.goto('https://erp.91miaoshou.com/shopee/collect_box/items', wait_until='domcontentloaded')
time.sleep(5)
updater._close_popups()  # 关闭新手指南弹窗
time.sleep(1)

# 定位商品 - 按货源ID搜索
page.evaluate(f'''
() => {{
    var cells = document.querySelectorAll(".jx-pro-virtual-table__row-cell");
    for (var cell of cells) {{
        if (cell.innerText.includes("{target_id}")) {{
            var row = cell.closest(".jx-pro-virtual-table__row");
            if (row) {{
                var btns = row.querySelectorAll("button");
                for (var b of btns) {{
                    if (b.innerText.trim() === "编辑") {{
                        b.click();
                        return;
                    }}
                }}
            }}
        }}
    }}
}}
''')
time.sleep(3)
```

#### Step 3: 等待编辑对话框

```python
dialog = updater._wait_for_dialog(timeout=10)
time.sleep(2)
```

#### Step 4: 填写7个字段

**4.1 产品标题**

```python
page.locator('input[placeholder="标题不能为空"]').fill(opt_title, timeout=5000)
```

**4.2 简易描述**

```python
desc_ta = page.locator('.el-dialog__body .el-form-item:nth-child(2) textarea')
desc_ta.fill('')
time.sleep(0.2)
desc_ta.fill(opt_desc, timeout=5000)
```

**4.3 主货号（form-item index 3）**

```python
dialog.evaluate(f'''() => {{
    var items = document.querySelectorAll(".el-dialog__body .el-form-item");
    var inp = items[3].querySelector("input");
    if (inp) {{ inp.value = "{main_sku}"; inp.dispatchEvent(new Event("input", {{bubbles:true}})); }}
}}''')
```

**4.4 包装重量（form-item index 12）**

> ⚠️ 单位：数据库存克(g)，ERP填KG → 公式：`dialog_value = package_weight_g / 1000`

```python
dialog.evaluate(f'''() => {{
    var items = document.querySelectorAll(".el-dialog__body .el-form-item");
    var inp = items[12].querySelector("input");
    if (inp) {{ inp.value = "2.5"; inp.dispatchEvent(new Event("input", {{bubbles:true}})); inp.dispatchEvent(new Event("change", {{bubbles:true}})); }}
}}''')
```

**4.5 包裹尺寸（form-item index 13）**

```python
dialog.evaluate('''() => {
    var items = document.querySelectorAll(".el-dialog__body .el-form-item");
    var inputs = items[13].querySelectorAll("input");
    if (inputs.length >= 3) {
        inputs[0].value = "25"; inputs[0].dispatchEvent(new Event("input", {bubbles:true}));
        inputs[1].value = "17"; inputs[1].dispatchEvent(new Event("input", {bubbles:true}));
        inputs[2].value = "10"; inputs[2].dispatchEvent(new Event("input", {bubbles:true}));
    }
}''')
```

**4.6 类目（form-item index 5）- el-cascader级联选择器**

> ⚠️ 类目组件类型是 `el-cascader`，不是 `el-dropdown`！

```python
# 打开cascader
dialog.evaluate('''() => {
    var items = document.querySelectorAll(".el-dialog__body .el-form-item");
    var cascader = items[5].querySelector(".el-cascader");
    if (cascader) cascader.click();
}''')
time.sleep(1)

# 三级级联选择：家居生活 -> 居家收纳 -> 收纳盒、收纳包与篮子
page.evaluate('''() => {
    var nodes = document.querySelectorAll(".el-cascader-node");
    for (var n of nodes) {
        var txt = n.innerText.replace(/\\n/g, "");
        if (txt.includes("家居生活")) { n.click(); return; }
    }
}''')
time.sleep(0.5)

page.evaluate('''() => {
    var nodes = document.querySelectorAll(".el-cascader-node");
    for (var n of nodes) {
        var txt = n.innerText.replace(/\\n/g, "");
        if (txt.includes("居家收纳")) { n.click(); return; }
    }
}''')
time.sleep(0.5)

page.evaluate('''() => {
    var nodes = document.querySelectorAll(".el-cascader-node");
    for (var n of nodes) {
        var txt = n.innerText.replace(/\\n/g, "");
        if (txt.includes("收纳盒")) { n.click(); return; }
    }
}''')
```

#### Step 5: 保存并发布

```python
dialog.evaluate('''() => {
    var btns = document.querySelectorAll("button");
    for (var b of btns) {
        if ((b.innerText || "").includes("保存并发布")) { b.click(); return; }
    }
}''')
print("已点击保存并发布")
time.sleep(3)
```

#### Step 6: 发布产品弹窗 - 全选店铺

```python
page.evaluate('''() => {
    var dialogs = document.querySelectorAll(".el-dialog");
    for (var d of dialogs) {
        var style = window.getComputedStyle(d);
        if (style.display !== "none") {
            var title = d.querySelector(".el-dialog__title");
            if (title && (title.innerText || "").includes("发布产品")) {
                var checkboxes = d.querySelectorAll("input[type=checkbox]");
                for (var cb of checkboxes) {
                    if (!cb.checked) { cb.checked = true; cb.dispatchEvent(new Event("change", {bubbles: true})); }
                }
            }
        }
    }
}''')
print("全选完成")
time.sleep(0.5)
```

#### Step 7: 确定发布

```python
page.evaluate('''() => {
    var btns = document.querySelectorAll("button");
    for (var b of btns) {
        if ((b.innerText || "").includes("确定发布")) { b.click(); return; }
    }
}''')
print("确定发布")
time.sleep(3)
```

#### Step 8: 关闭发布后的弹窗

```python
page.evaluate('''() => {
    var dialogs = document.querySelectorAll(".el-dialog");
    for (var d of dialogs) {
        var style = window.getComputedStyle(d);
        if (style.display !== "none") {
            var title = d.querySelector(".el-dialog__title");
            var titleText = title ? title.innerText : "";
            if (titleText.includes("发布产品")) {
                var closeBtn = d.querySelector(".el-dialog__headerbtn");
                if (closeBtn) { closeBtn.click(); return; }
            }
        }
    }
}''')
time.sleep(2)
```

---

## 二、关键HTML组件结构

### 2.1 编辑对话框 form-item 索引

| 索引 | 字段名 | 组件类型 | 选择器 |
|------|--------|----------|--------|
| 0 | 产品标题 | input | `input[placeholder="标题不能为空"]` |
| 1 | 简易描述 | textarea | `.el-dialog__body .el-form-item:nth-child(2) textarea` |
| 3 | 主货号 | input | `.el-dialog__body .el-form-item:nth-child(4) input` |
| 5 | 类目 | **el-cascader** | `.el-dialog__body .el-form-item:nth-child(6) .el-cascader` |
| 12 | 包裹重量 | input | `.el-dialog__body .el-form-item:nth-child(13) input` |
| 13 | 包裹尺寸 | 3个input | `.el-dialog__body .el-form-item:nth-child(14) input` |

> ⚠️ **注意：** nth-child是1-based索引，form-item index N = nth-child(N+1)

### 2.2 类目cascader结构

```
el-form-item[5]
  └── .el-cascader
        └── (点击触发面板)
el-cascader-panel (5个面板，display:flex)
  └── el-cascader-node (所有选项，初始不可见)
        └── 点击后下一面板展开
```

**节点文本包含特征文字时点击：**
- "家居生活" → 第一级
- "居家收纳" → 第二级
- "收纳盒" → 第三级

### 2.3 发布产品弹窗结构

```
发布产品弹窗 (.el-dialog)
  ├── .el-dialog__title = "发布产品"
  ├── .el-dialog__body
  │     ├── 选择发布店铺区域
  │     │     └── label + input[type=checkbox] (全选)
  │     └── 发布配置...
  └── .el-dialog__footer
        └── button[确定发布]
```

### 2.4 关闭按钮选择器

| 弹窗类型 | 选择器 |
|----------|--------|
| jx-dialog (编辑) | `button[aria-label="关闭此对话框"]` |
| el-dialog | `.el-dialog__headerbtn` (Close X) |

---

## 三、关键代码模式

### 3.1 关闭弹窗（通用）

```python
def _close_popups(self):
    """关闭新手指南等弹窗"""
    try:
        # 优先：jx-dialog关闭按钮
        close_btn = self.page.locator('button[aria-label="关闭此对话框"]')
        if close_btn.count() > 0:
            close_btn.first.click(force=True)
            time.sleep(0.5)
    except:
        pass
```

### 3.2 填写隐藏input（Vue响应式）

```python
# 直接设置value+dispatchEvent触发响应式
inp.value = "2.5"
inp.dispatchEvent(new Event("input", {bubbles: true}))
inp.dispatchEvent(new Event("change", {bubbles: true}))
```

### 3.3 Cascader节点点击

```python
# 用innerText包含判断 + JS click()
page.evaluate('''() => {
    var nodes = document.querySelectorAll(".el-cascader-node");
    for (var n of nodes) {
        var txt = n.innerText.replace(/\\n/g, "");
        if (txt.includes("目标文字")) { n.click(); return; }
    }
}''')
```

### 3.4 发布弹窗checkbox全选

```python
page.evaluate('''() => {
    var dialogs = document.querySelectorAll(".el-dialog");
    for (var d of dialogs) {
        if (window.getComputedStyle(d).display !== "none") {
            var title = d.querySelector(".el-dialog__title");
            if (title && title.innerText.includes("发布产品")) {
                var cbs = d.querySelectorAll("input[type=checkbox]");
                for (var cb of cbs) { if (!cb.checked) { cb.checked = true; cb.dispatchEvent(new Event("change", {bubbles:true})); } }
            }
        }
    }
}''')
```

---

## 四、数据来源与单位换算

### 4.1 数据库字段

```sql
-- 商品主数据
SELECT optimized_title, optimized_description, product_id_new 
FROM products 
WHERE alibaba_product_id = '1026175430866';

-- SKU物流数据（重量单位：克）
SELECT package_weight, package_length, package_width, package_height 
FROM product_skus 
WHERE product_id = (SELECT id FROM products WHERE alibaba_product_id = '1026175430866');
```

### 4.2 单位换算

| 字段 | 数据库单位 | ERP单位 | 换算公式 |
|------|----------|---------|---------|
| 包装重量 | 克(g) | KG | `erp_value = db_g / 1000` |
| 包裹尺寸 | 厘米(cm) | 厘米(cm) | 直接使用 |

### 4.3 测试商品数据

- 货源ID: `1026175430866`
- 主货号: `AL0001001260000001`
- 优化标题: `收納 首飾 北歐風 竹編 帶蓋 分格 桌面 髮飾 20x15x10cm 天然竹 米白 免運`
- 优化描述: `727字符`
- 包装重量: `2500g` → ERP填 `2.5`
- 包裹尺寸: `25 x 17 x 10 cm`
- 类目: `家居生活 > 居家收纳 > 收纳盒、收纳包与篮子`

---

## 五、常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 编辑按钮点不了 | 新手指南弹窗遮挡 | 先调用 `_close_popups()` |
| cascader面板不出现 | cascader节点visibility检测失败 | 用JS `.click()` 而不是 Playwright locator |
| 字段填写后丢失 | 页面刷新/重新加载 | 所有操作在一个session内完成，不刷新 |
| 描述填写失败 | textarea通过JS填充不触发响应式 | 用 Playwright locator `.fill()` |
| 发布产品弹窗找不到 | dialog在DOM里display:none | 只检查 `style.display !== "none"` 的dialog |
| 全选checkbox无效 | checkbox被el-checkbox-group包装 | 找label内包含"全选"的checkbox |

---

## 六、脚本文件

- **主脚本：** `/home/ubuntu/.openclaw/skills/miaoshou-updater/updater.py`
- **测试脚本：** `/tmp/handle_publish.py`
- **截图目录：** `/home/ubuntu/work/tmp/miaoshou_updater_test/`

---

## 七、飞书文档

- **流程文档：** https://pcn0wtpnjfsd.feishu.cn/docx/UVlkd1NHrorLumxC8K7cLMBUnDe
