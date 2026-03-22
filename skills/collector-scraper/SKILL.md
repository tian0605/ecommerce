---
name: collector-scraper
description: 从妙手ERP的Shopee采集箱提取商品完整数据（标题、描述、SKU、主图等）。触发条件：(1)商品已在Shopee采集箱需要提取数据 (2)执行TC-CS-001测试 (3)product-storer落库前需要商品数据
---

# collector-scraper

从妙手ERP的Shopee采集箱爬取商品完整数据。提取：货源ID、标题、类目、品牌、SKU列表（含规格/价格/库存）、主图URL列表、详情图、描述。

## 核心文件

- **模块路径**: `/home/ubuntu/.openclaw/skills/collector-scraper/scraper.py`
- **Cookie文件**: `/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json`（共享）
- **临时目录**: `/home/ubuntu/work/tmp/collector_scraper_test/`

## 使用方法

```bash
cd /home/ubuntu/.openclaw/skills/collector-scraper
python scraper.py --list          # 列出采集箱商品
python scraper.py --scrape 0      # 爬取第1个商品(index=0)
python scraper.py --scrape 1      # 爬取第2个商品(index=1)
```

或Python调用：

```python
from scraper import CollectorScraper

scraper = CollectorScraper()
scraper.launch()
result = scraper.scrape(index=0)
scraper.close()
print(result)
```

## 提取数据字段

| 字段 | 说明 |
|------|------|
| `source_id` | 货源ID（从1688链接提取） |
| `title` | 商品标题 |
| `category` | 类目 |
| `brand` | 品牌（可能为None） |
| `main_image` | 主图URL |
| `images` | 所有主图URL列表 |
| `skus` | SKU列表（3个：深棕色大号/小号/一套） |
| `description` | 详情描述 |
| `物流` | `weight` (g), `length_cm`, `width_cm`, `height_cm` |

## 关键技术点

### Vue单页应用点击
妙手ERP使用Vue，部分按钮需JS触发：
```python
page.evaluate('''() => {
    var btns = document.querySelectorAll("button");
    for (var b of btns) {
        if (b.innerText.trim() === "编辑") { b.click(); return; }
    }
}()''')
```

### 虚拟表格
妙手ERP使用 `jx-pro-virtual-table` 虚拟表格，数据从输入框提取：
```python
inputs = dialog.query_selector_all('input')
for inp in inputs:
    ph = inp.get_attribute('placeholder') or ''
    val = inp.input_value() or ''
```

### SKU规格提取
从输入框 `placeholder` 区分规格名和选项：
- `placeholder="请输入规格名称"` → 规格维度名（如"颜色"、"尺寸"）
- `placeholder="请输入选项名称"` → 选项值

## 前置条件

1. miaoshou-collector 已完成采集
2. 商品已在Shopee采集箱
3. Cookie有效

## 数据依赖

- **输入**: Shopee采集箱商品列表
- **输出**: 完整商品数据结构
- **后续模块**: product-storer 落库

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| 货源ID提取None | 从 `href=".../offer/1027205078815.html"` 正则提取 |
| SKU数量不准确 | 检查输入框逻辑，3个规格组合 |
| 物流信息为空 | 由local-1688-weight服务补充 |
| 编辑对话框未出现 | 检查Vue事件，尝试JS click |
