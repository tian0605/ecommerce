# miaoshou-api-publisher - 妙手ERP API发布器

## 概述

基于 HAR 抓包分析，直接调用妙手 ERP API 发布商品到 Shopee 采集箱，比 Playwright 浏览器自动化更稳定快速。

## 核心功能

- 直接调用妙手 API 保存商品数据
- 自动检测商品是否已在采集箱
- 支持更新已存在商品
- 数据冲突自动处理

## 文件结构

```
miaoshou-api-publisher/
├── SKILL.md           # 本文档
└── publisher.py       # 核心发布脚本
```

## API 端点

| 端点 | 路径 | 方法 |
|------|------|------|
| search_collect_box | /api/platform/shopee/move/collect_box/search_collect_box_detail | GET |
| save_site_detail | /api/platform/shopee/move/collect_box/saveSiteDetailData | POST |
| get_category_tree | /api/platform/shopee/move/collect_box/getCategoryTreeBySite | GET |
| get_attribute_map | /api/platform/shopee/move/collect_box/getCollectBoxMultipleAttributeMap | GET |

## 前置条件

1. **Cookies 文件**：`/home/ubuntu/work/config/miaoshou_cookies.json`
   - 包含 `mserp_sst`, `tfstk`, `accountId` 等认证 cookie
   - 格式：`[{name, value, domain, path, secure, httpOnly}]`

2. **数据库**：商品数据已落库（products + product_skus 表）

3. **商品状态**：已优化（status = 'optimized'）且有关联 SKU

## 使用方法

### 基本用法

```bash
# 发布待发布商品（默认取最新1条）
python3 publisher.py --limit 1

# 发布指定商品
python3 publisher.py --product-id 1031400982378

# 列出待发布商品（不执行发布）
python3 publisher.py --list

# 静默模式
python3 publisher.py --limit 5 --quiet
```

### Python 模块调用

```python
from pathlib import Path
sys.path.insert(0, '/home/ubuntu/.openclaw/skills/miaoshou-api-publisher')
from publisher import MiaoshouAPIPublisher

publisher = MiaoshouAPIPublisher()
success, message = publisher.publish_product(product)
```

## saveSiteDetailData 请求格式

### 核心字段

```json
{
  "cid": "101174",                    // 类目ID
  "title": "收納盒 廚房收納...",       // 优化标题（繁体）
  "itemNum": "AL0001001260000002",    // 主货号
  "price": "",                        // 价格（留空则使用SKU价格）
  "stock": "",                        // 库存（留空则使用SKU库存）
  "colorPropName": "颜色",             //颜色属性名
  "sizePropName": "尺码",             // 尺码属性名
  "weight": 0.91,                     // 总重量(kg)
  "packageLength": "41",              // 包装长度(cm)
  "packageWidth": "21",               // 包装宽度(cm)
  "packageHeight": "36",             // 包装高度(cm)
  "colorMap": {                       // 颜色SKU映射
    "组合【三件套】": {
      "name": "组合【三件套】",
      "imgUrls": ["https://..."],
      "imgUrl": "https://...",
      "mapKey": "组合【三件套】"
    }
  },
  "skuMap": {                         // SKU数据
    ";组合【三件套】;;": {
      "price": 36,                    // 售价(TWD)
      "stock": 99999,                 // 库存
      "weight": 0.3,                  // SKU重量(kg)
      "itemNum": "1031400982378_组合【三件套】",
      "originPrice": 24,              // 原价(CNY)
      "colorPropName": "组合【三件套】",
      "sizePropName": "",
      "systemPrice": ""
    }
  },
  "imgUrls": ["https://...", ...],    // 主图URL列表
  "notes": "...",                     // 简易描述
  "richTextDesc": "<p>...</p>",      // 富文本描述(HTML)
  "attributeMaps": {                  // 类目属性
    "100037": {"attributeName": "Region of Origin", ...},
    "100134": {"attributeName": "Material", ...}
  },
  "brand": {"brandId": 0, "brandName": "NoBrand"},
  "sourceItemMetaInfo": {              // 货源信息
    "source": "1688",
    "sourceItemId": "1031400982378", // 1688商品ID
    "maxSkuPrice": "24.00"           // 最大SKU价格
  }
}
```

### 响应处理

| 响应 | 含义 | 处理 |
|------|------|------|
| `{"result":"success"}` | 发布成功 | 更新状态为 published |
| `{"result":"fail","reason":"商品已在采集箱"}` | 数据冲突 | 更新状态为 published |
| `{"result":"fail","reason":"参数错误"}` | 格式错误 | 检查数据格式 |
| `{"result":"fail","reason":"您编辑过程中产品数据发生变动..."}` | 正在编辑 | 等待或跳过 |

## 数据库依赖

### products 表

```sql
SELECT id, alibaba_product_id, optimized_title, optimized_description,
       status, product_id_new, main_images
FROM products
WHERE status = 'optimized'
  AND optimized_title IS NOT NULL
  AND alibaba_product_id IS NOT NULL
```

### product_skus 表

```sql
SELECT sku_name, price, stock, package_weight,
       package_length, package_width, package_height
FROM product_skus
WHERE product_id = ?
```

## 已知问题

1. **参数错误**：如果返回"参数错误"，检查：
   - SKU 数据格式是否正确
   - 必填字段是否完整
   - JSON 编码是否正确

2. **数据冲突**：如果商品正在被编辑，API 会拒绝更新
   - 等待几秒后重试
   - 或通过浏览器手动完成编辑

## 调试

### 查看完整请求数据

```bash
# 保存到文件
python3 -c "
import json
with open('/root/.openclaw/workspace-e-commerce/temp/api_test_data.json') as f:
    print(json.dumps(json.load(f), indent=2, ensure_ascii=False))
"
```

### 测试 API 连接

```python
import urllib.request
import json

cookies = json.load(open('/home/ubuntu/work/config/miaoshou_cookies.json'))
cookie_str = '; '.join([f\"{c['name']}={c['value']}\" for c in cookies])

url = 'https://erp.91miaoshou.com/api/platform/shopee/move/collect_box/search_collect_box_detail'
req = urllib.request.Request(url, headers={'Cookie': cookie_str})

with urllib.request.urlopen(req) as resp:
    print(json.loads(resp.read()))
```

## 更新日志

- 2026-03-29: 创建技能，基于 HAR 抓包分析实现 API 发布
