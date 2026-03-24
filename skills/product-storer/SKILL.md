---
name: product-storer
description: 商品数据落库模块。将collector-scraper提取的商品数据与local-1688-weight的物流数据合并，落库到PostgreSQL数据库。触发条件：(1)需要将商品数据持久化 (2)执行TC-PS-001测试 (3)listing-optimizer前需要已落库的商品
---

# product-storer

商品数据落库模块。将商品主数据与物流数据合并，生成主货号，落库到 PostgreSQL，并上传图片到腾讯云COS。

## 核心文件

- **模块路径**: `/home/ubuntu/.openclaw/skills/product-storer/storer.py`
- **测试文件**: `/home/ubuntu/.openclaw/skills/product-storer/test_pipeline.py`
- **数据库配置**: shared/db.py
- **COS存储**: shared/cos_storage.py

## 数据库配置

```python
# shared/db.py
DB_CONFIG = {
    'host': '43.139.213.66',
    'port': 5432,
    'database': 'ecommerce_data',
    'user': 'postgres',
    'password': '...'
}
```

## 主货号生成规则

格式：`{星期代号}{6位序号}`
- 星期代号：0=日, 1=一, 2=二, 3=三, 4=四, 5=五, 6=六
- 示例：日000001, 六000002, 三000015

## 落库数据合并

```python
# 合并 collector-scraper 数据 + local-1688-weight 数据
final_data = {
    **scraper_data,      # 货源ID、标题、类目、SKU、主图
    **weight_data,       # weight_g, length_cm, width_cm, height_cm
    'main_product_no': generate_product_id(),
    'status': 'pending'
}
```

## COS图片上传

落库时自动调用 `_upload_images_to_cos()` 上传图片到腾讯云COS。

**目录结构：**
```
/{product_id_new}_{title(截取50字节)}/
├── main_images/      # 主图（最多29张）
├── sku_images/       # SKU图（暂无数据）
└── detail_images/   # 详情图（暂无数据）
```

**示例：**
```
AL0001001260000001_发饰收纳盒桌面分格发圈发夹置物儿/main_images/main_00.jpg
```

**COS桶：** `tian-cloud-file-1309014213`

## 使用方法

```python
from product_storer import ProductStorer
from collector_scraper import CollectorScraper
from remote_weight_caller import get_weight

# 1. 提取商品数据
scraper = CollectorScraper()
scraper.launch()
scraper_data = scraper.scrape(index=0)
scraper.close()

# 2. 获取物流数据
weight_data = get_weight(product_id)

# 3. 落库
storer = ProductStorer()
result = storer.save_product(scraper_data, weight_data)
print(result)
```

## 数据库表结构

**products 表主要字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| alibaba_product_id | VARCHAR(50) | 1688货源ID |
| main_product_no | VARCHAR(20) | 主货号 |
| title | TEXT | 商品标题 |
| category | VARCHAR(255) | 类目 |
| sku_count | INT | SKU数量 |
| main_image_count | INT | 主图数量 |
| weight_g | DECIMAL | 重量(克) |
| length_cm | DECIMAL | 长度(cm) |
| width_cm | DECIMAL | 宽度(cm) |
| height_cm | DECIMAL | 高度(cm) |
| status | VARCHAR(20) | 状态: pending/optimized/published |
| created_at | TIMESTAMP | 创建时间 |

## 数据依赖

- **输入**: collector-scraper数据 + local-1688-weight数据
- **输出**: products表记录
- **后续模块**: listing-optimizer 优化

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| 数据库连接失败 | 检查VPN/SSH隧道，验证DB配置 |
| 主货号重复 | 序号自增，理论上不会重复 |
| 字段不匹配 | 检查 scaper_data 和 weight_data 结构 |
