# TC-CS-001: collector-scraper 提取商品数据

## 测试命令

```bash
cd /home/ubuntu/.openclaw/skills/collector-scraper
python scraper.py --list          # 先列出商品
python scraper.py --scrape 0       # 爬取第1个
```

## 验收标准

```json
{
  "货源ID": "1027205078815",
  "标题": "日式复古风实木竹编收纳筐客厅桌面收纳盒家居书本零食杂物收纳框",
  "类目": "收纳盒、收纳包与篮子",
  "SKU数量": 3,
  "主图数量": 14,
  "物流": {
    "weight": "39.80",
    "length_cm": "35",
    "width_cm": "25",
    "height_cm": "16"
  }
}
```

## SKU组合逻辑

```
规格1: 颜色 = [深棕色]
规格2: 尺寸 = [大号35*25*16cm, 小号30*20*14cm, 一套（大小号）]
组合数 = 1 × 3 = 3 个SKU
```

## 关键选择器

| 元素 | 选择器 |
|------|--------|
| 商品行 | `.jx-pro-virtual-table tr` 或 `tr[data-row-index]` |
| 编辑按钮 | `button: contains("编辑")` |
| 规格输入框 | `input[placeholder="请输入规格名称"]` |
| 选项输入框 | `input[placeholder="请输入选项名称"]` |
| 对话框 | `.el-dialog__wrapper: visible` |

## 物流信息提取优先级

1. **JavaScript提取**: `page.evaluate('...')` 获取 SKU weight
2. **方法2**: 查找物流区域数值型input
3. **方法3**: 从SKU规格解析尺寸（格式: `35*25*16cm`）
