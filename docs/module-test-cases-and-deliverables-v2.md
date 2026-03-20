# 模块测试用例与目标成果 v2

**项目：** 自动采集方案 v6
**创建日期：** 2026-03-20
**版本：** v2.0（细化验收条件）
**状态：** 待审核

---

## 一、collector-scraper（采集箱爬虫模块）

### 1.1 模块目标

从妙手ERP公用采集箱爬取商品完整信息，输出规范化JSON数据

### 1.2 成果指标

| 指标 | 目标值 | 验收条件 |
|------|--------|----------|
| 数据完整率 | ≥ 95% | 必需字段非空率 |
| 采集耗时 | ≤ 30秒/商品 | 从打开页面到数据解析完成 |
| SKU解析准确率 | ≥ 98% | SKU价格/库存/属性正确解析 |
| 图片URL提取率 | 100% | 主图/SKU图/详情图URL全提取 |

### 1.3 采集字段清单与验收标准

#### 基础信息

| 字段名 | 类型 | 必需 | 验收标准 | 示例值 |
|--------|------|------|----------|--------|
| `alibaba_product_id` | string | ✅ | 非空，只含数字，长度8-16位 | `6012345678` |
| `source_url` | string | ✅ | 以 `https://detail.1688.com` 开头 | `https://detail.1688.com/offer/6012345678.html` |
| `product_title` | string | ✅ | 长度10-200字符，非纯数字/符号 | `2023新款女士休闲裤 松紧腰宽松直筒长裤` |
| `product_description` | string | ✅ | 长度≥20字符 | `面料：纯棉，透气舒适...` |

#### 主图信息

| 字段名 | 类型 | 必需 | 验收标准 | 示例值 |
|--------|------|------|----------|--------|
| `main_images` | array | ✅ | 数组长度≥1，每个元素为有效URL | `["https://cbu01.alicdn.com/img/bank/..."]` |
| `main_images[].url` | string | ✅ | URL以 `https://cbu01.alicdn.com` 开头 | - |
| `main_images[].alt` | string | ❌ | 可空 | `主图1` |

#### SKU信息

| 字段名 | 类型 | 必需 | 验收标准 | 示例值 |
|--------|------|------|----------|--------|
| `sku_list` | array | ✅ | 数组长度≥1 | `[{...}, {...}]` |
| `sku_list[].sku_id` | string | ✅ | 非空 | `1234567890` |
| `sku_list[].price` | number | ✅ | > 0，格式正确 | `29.50` |
| `sku_list[].stock` | integer | ✅ | ≥ 0 | `1000` |
| `sku_list[].properties` | object | ✅ | 至少包含1组属性 | `{"颜色": "黑色", "尺码": "M"}` |
| `sku_list[].sku_code` | string | ❌ | 可空 | `SK-001` |
| `sku_list[].main_image` | string | ❌ | 有效URL或空 | `https://cbu01.alicdn.com/...` |

#### 详情图信息

| 字段名 | 类型 | 必需 | 验收标准 | 示例值 |
|--------|------|------|----------|--------|
| `detail_images` | array | ✅ | 数组长度≥1，每个元素为有效URL | `["https://cbu01.alicdn.com/img/..."]` |
| `detail_images[]` | string | ✅ | URL以 `https://cbu01.alicdn.com` 开头 | - |

#### 包装信息

| 字段名 | 类型 | 必需 | 验收标准 | 示例值 |
|--------|------|------|----------|--------|
| `packaging_info.weight` | number | ✅ | ≥ 0 | `0.5` (kg) |
| `packaging_info.length` | number | ❌ | > 0 或 null | `30` (cm) |
| `packaging_info.width` | number | ❌ | > 0 或 null | `20` (cm) |
| `packaging_info.height` | number | ❌ | > 0 或 null | `5` (cm) |

#### 其他信息

| 字段名 | 类型 | 必需 | 验收标准 | 示例值 |
|--------|------|------|----------|--------|
| `category` | string | ✅ | 非空 | `女士休闲裤` |
| `price_range` | string | ✅ | 格式如 `¥29.50 - ¥59.00` | `¥29.50 - ¥59.00` |
| `moq` | integer | ✅ | ≥ 1 | `1` |

### 1.4 测试用例

#### TC-SC-001: 单商品完整采集

```python
"""
测试名称: 单商品完整采集
前置条件: 妙手ERP已登录，Browser Relay可用，公用采集箱有测试商品
测试步骤:
  1. 打开采集箱产品编辑页 https://ms.aipaw.cn/collect/edit/{product_id}
  2. 截图保存: /home/ubuntu/work/tmp/scraper_test/tc_sc_001_before.png
  3. 执行 scraper.scrape_product(product_id)
  4. 截图保存: /home/ubuntu/work/tmp/scraper_test/tc_sc_001_after.png
  5. 验证输出JSON每个字段

验证点:
  [ ] alibaba_product_id: 正则匹配 ^\d{8,16}$，如 6012345678
  [ ] source_url: 以 https://detail.1688.com/offer/ 开头
  [ ] product_title: len() > 10，非纯数字/符号
  [ ] product_description: len() >= 20
  [ ] main_images: len(array) >= 1，每个URL以 cbu01.alicdn.com 开头
  [ ] sku_list: len(array) >= 1，每个SKU包含 price > 0, stock >= 0
  [ ] sku_list[0].properties: 至少1组属性键值对
  [ ] detail_images: len(array) >= 1，每个URL以 cbu01.alicdn.com 开头
  [ ] packaging_info.weight: >= 0
  [ ] category: 非空字符串
  [ ] price_range: 格式匹配 ¥数字 - ¥数字
  [ ] moq: >= 1

输出文件:
  - /home/ubuntu/work/tmp/scraper_test/tc_sc_001_before.png
  - /home/ubuntu/work/tmp/scraper_test/tc_sc_001_after.png
  - /home/ubuntu/work/tmp/scraper_test/tc_sc_001_output.json

预期结果: 所有验证点通过，函数返回 True
"""

# 输出JSON示例
{
  "alibaba_product_id": "6012345678",
  "source_url": "https://detail.1688.com/offer/6012345678.html",
  "product_title": "2023新款女士休闲裤 松紧腰宽松直筒长裤",
  "product_description": "面料：纯棉，透气舒适。适合日常穿着，休闲百搭。",
  "main_images": [
    {"url": "https://cbu01.alicdn.com/img/bank/20230101/abc.jpg", "alt": "主图1"},
    {"url": "https://cbu01.alicdn.com/img/bank/20230101/def.jpg", "alt": "主图2"}
  ],
  "sku_list": [
    {
      "sku_id": "1234567890",
      "price": 29.50,
      "stock": 1000,
      "properties": {"颜色": "黑色", "尺码": "M"},
      "sku_code": "SK-BL-M",
      "main_image": "https://cbu01.alicdn.com/img/bank/20230101/sku1.jpg"
    }
  ],
  "detail_images": [
    "https://cbu01.alicdn.com/img/bank/20230101/d1.jpg",
    "https://cbu01.alicdn.com/img/bank/20230101/d2.jpg"
  ],
  "packaging_info": {"weight": 0.5, "length": 30, "width": 20, "height": 5},
  "category": "女士休闲裤",
  "price_range": "¥29.50 - ¥59.00",
  "moq": 1
}
```

#### TC-SC-002: 数据字段完整率检查（10商品）

```python
"""
测试名称: 数据字段完整率检查
前置条件: 采集箱中有≥10个商品
测试步骤:
  1. 随机选取10个采集箱商品
  2. 依次执行 scraper.scrape_product() 采集
  3. 统计每个字段的非空率

验证点:
  [ ] alibaba_product_id 非空率 = 100%
  [ ] product_title 非空率 = 100%
  [ ] main_images 非空率 = 100%
  [ ] sku_list 非空率 = 100%
  [ ] detail_images 非空率 = 100%
  [ ] 整体字段完整率 >= 95%

输出文件:
  - /home/ubuntu/work/tmp/scraper_test/tc_sc_002_report.csv

预期结果: 整体字段完整率 >= 95%
"""

# CSV输出示例
字段名,非空率,目标
alibaba_product_id,100%,100%
product_title,100%,100%
main_images,100%,100%
sku_list,100%,100%
detail_images,100%,100%
overall_rate,96.5%,95%
```

#### TC-SC-003: 采集性能测试

```python
"""
测试名称: 采集性能测试
前置条件: 采集箱中有测试商品
测试步骤:
  1. 记录开始时间 start_time
  2. 执行 scraper.scrape_product(product_id)
  3. 记录结束时间 end_time
  4. 计算耗时 = end_time - start_time

验证点:
  [ ] 单次采集耗时 <= 30秒
  [ ] 页面加载时间可单独统计

输出文件:
  - /home/ubuntu/work/tmp/scraper_test/tc_sc_003_timing.json

预期结果: 耗时 <= 30.0 秒
"""

# 耗时输出示例
{
  "product_id": "123456",
  "total_time_seconds": 18.5,
  "page_load_seconds": 5.2,
  "parse_seconds": 13.3,
  "target_seconds": 30.0,
  "passed": True
}
```

#### TC-SC-004: SKU解析准确性

```python
"""
测试名称: SKU解析准确性
前置条件: 采集箱商品有多个SKU（含不同颜色/尺码）
测试步骤:
  1. 打开商品编辑页截图
  2. 执行 scraper.scrape_product()
  3. 对比SKU数量与页面显示

验证点:
  [ ] SKU总数与页面显示一致
  [ ] 每个SKU的price解析正确（误差<=0.01）
  [ ] 每个SKU的stock解析正确（与页面一致）
  [ ] 每个SKU的properties解析正确（颜色/尺码等）

截图要求:
  - tc_sc_004_page.png: 页面SKU区域截图
  - tc_sc_004_output.png: 输出JSON可视化

预期结果: SKU解析准确率 >= 98%
"""
```

---

## 二、product-storer（落库模块）

### 2.1 模块目标

将采集数据规范化落库至 ecommerce_data.products 表

### 2.2 成果指标

| 指标 | 目标值 | 验收条件 |
|------|--------|----------|
| 落库成功率 | ≥ 99% | 成功插入/更新记录数/总请求数 |
| 重复数据处理 | 100% | 基于alibaba_product_id去重，更新而非重复插入 |
| 数据完整性 | 100% | 必需字段全部写入 |
| 事务正确性 | 100% | 失败时回滚，不留半条记录 |

### 2.3 数据库字段验收

#### products 表

| 字段名 | 类型 | 必需 | 验收标准 | 数据库写入值 |
|--------|------|------|----------|--------------|
| `id` | SERIAL | ✅ | 自动生成 | 自动递增 |
| `alibaba_product_id` | VARCHAR(64) | ✅ | 唯一，非空 | 6012345678 |
| `source_url` | TEXT | ✅ | 非空 | https://detail.1688.com/offer/... |
| `product_title` | TEXT | ✅ | 非空 | 原始标题 |
| `optimized_title` | TEXT | ❌ | 可空 | 优化后标题（后续步骤填充） |
| `product_description` | TEXT | ✅ | 非空 | 原始描述 |
| `optimized_description` | TEXT | ❌ | 可空 | 优化后描述（后续步骤填充） |
| `main_images` | JSONB | ✅ | 有效JSON数组 | `[{"url":"..."}]` |
| `detail_images` | JSONB | ✅ | 有效JSON数组 | `["..."]` |
| `sku_list` | JSONB | ✅ | 有效JSON数组 | `[{...}]` |
| `sku_properties` | JSONB | ❌ | 可空 | `{...}` |
| `packaging_info` | JSONB | ✅ | 有效JSON对象 | `{"weight":0.5}` |
| `category` | VARCHAR(255) | ✅ | 非空 | 女士休闲裤 |
| `price_range` | VARCHAR(100) | ✅ | 非空 | ¥29.50 - ¥59.00 |
| `moq` | INTEGER | ✅ | >= 1 | 1 |
| `status` | VARCHAR(32) | ✅ | 枚举值 | pending/optimized/claimed/error |
| `shopee_product_id` | VARCHAR(64) | ❌ | 可空 | 认领后填充 |
| `main_product_code` | VARCHAR(64) | ❌ | 可空 | 认领后填充 |
| `created_at` | TIMESTAMP | ✅ | 自动生成 | CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMP | ✅ | 自动更新 | 自动更新 |
| `claimed_at` | TIMESTAMP | ❌ | 可空 | 认领后填充 |

### 2.4 测试用例

#### TC-ST-001: 新商品落库

```python
"""
测试名称: 新商品落库
前置条件: ecommerce_data 数据库可写，products表存在
测试步骤:
  1. 准备采集数据（alibaba_product_id = 新值，如 6012345001）
  2. 执行 store.insert_product(product_data)
  3. 查询数据库验证

验证点:
  [ ] products表新增1条记录
  [ ] id字段自动生成（非空）
  [ ] alibaba_product_id = '6012345001'
  [ ] source_url 正确写入
  [ ] product_title 正确写入
  [ ] main_images = 有效JSON（JSONB类型）
  [ ] sku_list = 有效JSON数组
  [ ] detail_images = 有效JSON数组
  [ ] packaging_info = 有效JSON对象
  [ ] status = 'pending'
  [ ] created_at 为当前时间（误差1分钟内）
  [ ] updated_at = created_at（初始状态）

SQL验证:
SELECT id, alibaba_product_id, source_url, product_title, 
       jsonb_array_length(main_images) as main_image_count,
       jsonb_array_length(sku_list) as sku_count,
       jsonb_array_length(detail_images) as detail_image_count,
       status, created_at, updated_at
FROM products 
WHERE alibaba_product_id = '6012345001';

预期结果: 查询返回1条记录，所有字段值正确
"""

# 数据库验证SQL结果示例
{
  "id": 101,
  "alibaba_product_id": "6012345001",
  "source_url": "https://detail.1688.com/offer/6012345001.html",
  "product_title": "2023新款女士休闲裤",
  "main_image_count": 3,
  "sku_count": 6,
  "detail_image_count": 8,
  "status": "pending",
  "created_at": "2026-03-20 09:00:00",
  "updated_at": "2026-03-20 09:00:00"
}
```

#### TC-ST-002: 重复商品更新（去重验证）

```python
"""
测试名称: 重复商品更新（去重验证）
前置条件: products表已有 alibaba_product_id = '6012345001' 的记录
测试步骤:
  1. 准备同名商品数据（修改 title 为 "2024新款女士休闲裤"）
  2. 执行 store.insert_product(product_data)
  3. 查询数据库

验证点:
  [ ] products表记录总数不变（未新增）
  [ ] alibaba_product_id = '6012345001' 记录仍为1条
  [ ] product_title 已更新为 "2024新款女士休闲裤"
  [ ] updated_at 已更新（晚于 created_at）
  [ ] 函数返回原有 record_id（非新建ID）

SQL验证:
SELECT COUNT(*) as count, 
       MAX(created_at) as created_at, 
       MAX(updated_at) as updated_at,
       product_title
FROM products 
WHERE alibaba_product_id = '6012345001'
GROUP BY product_title;

预期结果: count = 1，updated_at > created_at
"""

# SQL验证结果示例
{
  "count": 1,
  "created_at": "2026-03-20 09:00:00",
  "updated_at": "2026-03-20 09:10:00",
  "product_title": "2024新款女士休闲裤"
}
```

#### TC-ST-003: 必需字段校验

```python
"""
测试名称: 必需字段校验
前置条件: products表结构正确
测试步骤:
  1. 准备缺少必需字段的数据（如 alibaba_product_id 为空）
  2. 执行 store.insert_product(product_data)

验证点:
  [ ] 抛出 ValidationError 异常
  [ ] 异常消息包含 'alibaba_product_id' 字段名
  [ ] 数据库中无新增记录

预期结果: 函数返回 False，数据库无变化
"""
```

#### TC-ST-004: 图片数据落库

```python
"""
测试名称: 图片数据落库
前置条件: products表和product_images表存在
测试步骤:
  1. 准备含3张主图、6个SKU图、8张详情图的商品数据
  2. 执行 store.insert_product(product_data)
  3. 查询 product_images 表

验证点:
  [ ] product_images 表新增17条记录
  [ ] 3条 image_type = 'main'
  [ ] 6条 image_type = 'sku'
  [ ] 8条 image_type = 'detail'
  [ ] 每条记录的 product_id 正确关联
  [ ] image_url 正确写入
  [ ] local_path 为空（未下载本地）
  [ ] cos_url 为空（未上传COS）

SQL验证:
SELECT image_type, COUNT(*) as count 
FROM product_images 
WHERE product_id = (SELECT id FROM products WHERE alibaba_product_id = '6012345001')
GROUP BY image_type;

预期结果:
| image_type | count |
|------------|-------|
| main       | 3     |
| sku        | 6     |
| detail     | 8     |
"""
```

#### TC-ST-005: 事务回滚验证

```python
"""
测试名称: 事务回滚验证
前置条件: products表和product_images表存在
测试步骤:
  1. 准备商品数据（product_images表写入会失败）
  2. 执行 store.insert_product(product_data)
  3. 查询 products 和 product_images 表

验证点:
  [ ] products表无新增记录（已回滚）
  [ ] product_images表无新增记录（已回滚）
  [ ] 函数返回 False

预期结果: 事务100%回滚，无半条记录
"""
```

---

## 三、listing-optimizer（Listing优化模块）

### 3.1 模块目标

使用LLM优化商品标题和描述，输出Shopee平台友好的Listing

### 3.2 成果指标

| 指标 | 目标值 | 验收条件 |
|------|--------|----------|
| 优化成功率 | ≥ 95% | 成功返回优化结果的请求数/总请求数 |
| 标题长度 | 30-50字符 | 优化后标题字符数 |
| 描述长度 | 100-500字符 | 优化后描述字符数 |
| 关键词保留率 | ≥ 80% | 原始关键词出现在优化后内容的比例 |
| API响应时间 | ≤ 10秒/商品 | LLM API调用耗时 |

### 3.3 输出字段验收

| 字段名 | 类型 | 必需 | 验收标准 | 示例值 |
|--------|------|------|----------|--------|
| `optimized_title` | string | ✅ | 30-50字符，无特殊字符污染 | 「品质保障」女士休闲裤 宽松直筒 透气舒适 |
| `optimized_description` | string | ✅ | 100-500字符，含卖点/规格/售后 | 面料：纯棉...\n规格：M/L/XL...\n售后：7天无理由... |
| `original_title` | string | ✅ | 原始标题（原样返回） | 2023新款女士休闲裤 松紧腰宽松直筒长裤 |
| `original_description` | string | ✅ | 原始描述（原样返回） | ... |
| `keywords_extracted` | array | ✅ | 关键词数组 | ["女士休闲裤", "纯棉", "宽松"] |
| `optimization_prompt` | string | ✅ | 本次优化使用的prompt | ... |
| `llm_model` | string | ✅ | 调用的模型名 | glm-4 |
| `api_time_ms` | integer | ✅ | API耗时（毫秒） | 3500 |
| `status` | string | ✅ | success/failed/degraded | success |

### 3.4 测试用例

#### TC-LO-001: 标题优化

```python
"""
测试名称: 标题优化
前置条件: LLM API可用
测试步骤:
  1. 输入原始标题: "2023新款女士休闲裤 松紧腰宽松直筒长裤"
  2. 执行 optimizer.optimize_title(title)
  3. 验证输出

验证点:
  [ ] 输出标题长度 30-50字符（含中文和英文/数字）
  [ ] 保留核心品类词 "女士休闲裤"
  [ ] 无乱码或特殊字符
  [ ] 符合Shopee标题格式（关键词堆砌少，可读性强）
  [ ] 包含尺寸/面料/风格等属性词

输出示例:
{
  "optimized_title": "「品质保障」女士休闲裤 宽松直筒 透气舒适 纯棉面料",
  "original_title": "2023新款女士休闲裤 松紧腰宽松直筒长裤",
  "title_length": 32,
  "keywords_preserved": ["女士休闲裤", "宽松", "纯棉"],
  "llm_model": "glm-4",
  "api_time_ms": 2800,
  "status": "success"
}

预期结果: 所有验证点通过
"""
```

#### TC-LO-002: 描述优化

```python
"""
测试名称: 描述优化
前置条件: LLM API可用
测试步骤:
  1. 输入原始描述: "面料：纯棉，透气舒适。适合日常穿着，休闲百搭。洗涤说明：手洗。"
  2. 执行 optimizer.optimize_description(description, category="女士休闲裤")
  3. 验证输出

验证点:
  [ ] 输出描述长度 100-500字符
  [ ] 包含【面料】【规格】【洗涤】【售后】等模块化内容
  [ ] 保留原始描述核心卖点
  [ ] 无乱码或特殊字符
  [ ] 符合Shopee描述规范（可含emoji）

输出示例:
{
  "optimized_description": "【面料】优质纯棉，透气舒适\n【规格】M/L/XL\n【特点】松紧腰设计，宽松直筒版型\n【洗涤】手洗/机洗均可\n【售后】7天无理由退换",
  "original_description": "面料：纯棉...",
  "description_length": 186,
  "modules_present": ["面料", "规格", "特点", "洗涤", "售后"],
  "llm_model": "glm-4",
  "api_time_ms": 3200,
  "status": "success"
}

预期结果: 所有验证点通过
"""
```

#### TC-LO-003: LLM API失败降级

```python
"""
测试名称: LLM API失败降级
前置条件: 模拟LLM API不可用（超时/错误）
测试步骤:
  1. 模拟API返回错误
  2. 执行 optimizer.optimize_title(title)
  3. 验证降级处理

验证点:
  [ ] API失败时自动降级到规则匹配
  [ ] 返回基于规则的优化结果（可接受质量下降）
  [ ] 记录降级日志（level=WARNING）
  [ ] status = 'degraded'
  [ ] 返回结果仍满足基本格式要求

预期结果: 函数不抛异常，返回降级结果
"""
```

#### TC-LO-004: 批量优化（10商品）

```python
"""
测试名称: 批量优化
前置条件: LLM API可用，10个商品数据准备完毕
测试步骤:
  1. 准备10个商品数据
  2. 执行 optimizer.batch_optimize(products, max_concurrency=3)
  3. 统计结果

验证点:
  [ ] 95%以上商品成功优化（>= 10个中>=10个成功）
  [ ] 总耗时 < 120秒（不含API超时重试）
  [ ] 每个成功结果包含完整字段
  [ ] 失败结果记录错误原因
  [ ] 并发数控制在3以内

输出示例:
{
  "total": 10,
  "success": 10,
  "failed": 0,
  "degraded": 1,
  "total_time_seconds": 85.3,
  "average_time_ms": 3200,
  "results": [...]
}

预期结果: success >= 9, total_time < 120
"""
```

---

## 四、miaoshou-updater（妙手回写模块）

### 4.1 模块目标

将优化后的标题/描述/货号回写到妙手ERP编辑页面

### 4.2 成果指标

| 指标 | 目标值 | 验收条件 |
|------|--------|----------|
| 回写成功率 | ≥ 95% | 成功保存的编辑操作数/总操作数 |
| 字段填写准确率 | 100% | 标题/描述/货号正确填写 |
| 页面保存稳定性 | 100% | 保存后数据不丢失 |
| 操作耗时 | ≤ 60秒/商品 | 从打开页面到保存完成 |

### 4.3 回写字段验收

| 页面字段 | 填写值来源 | 验收标准 |
|----------|-----------|----------|
| 产品标题 | optimized_title | 字符数30-50，非空 |
| 简易描述 | optimized_description | 字符数100-500，非空 |
| 主商品货号 | main_product_code | 格式：SP-YYYYMMDD-序号，如 SP-20260320-001 |

### 4.4 测试用例

#### TC-MU-001: 编辑页面填写

```python
"""
测试名称: 编辑页面填写
前置条件: 妙手ERP已登录，采集箱有测试商品
测试步骤:
  1. 打开采集箱产品编辑页
  2. 截图保存页面原状态: tc_mu_001_before.png
  3. 执行 updater.update_product(product_id, update_data)
  4. 截图保存填写后状态: tc_mu_001_after.png
  5. 点击保存
  6. 截图保存保存后状态: tc_mu_001_saved.png

update_data示例:
{
  "optimized_title": "「品质保障」女士休闲裤 宽松直筒 透气舒适",
  "optimized_description": "【面料】优质纯棉...\n【售后】7天无理由退换",
  "main_product_code": "SP-20260320-001"
}

验证点:
  [ ] 编辑页面成功打开（无权限/404错误）
  [ ] 标题输入框值 = optimized_title
  [ ] 描述输入框值 = optimized_description
  [ ] 货号输入框值 = main_product_code
  [ ] 点击保存无错误提示
  [ ] 保存后显示成功提示

截图要求:
  - tc_mu_001_before.png: 填写前页面
  - tc_mu_001_after.png: 填写后（点击保存前）
  - tc_mu_001_saved.png: 保存后（显示成功提示）

预期结果: 所有验证点通过，函数返回 True
预期结果: 浏览器截图 tc_mu_001_success.png 显示采集箱编辑页保存成功（标题/描述/货号已填写）
"""
```

#### TC-MU-002: 保存后数据验证

```python
"""
测试名称: 保存后数据验证
前置条件: TC-MU-001已执行并保存成功
测试步骤:
  1. 刷新编辑页面（或重新打开）
  2. 截图: tc_mu_002_verify.png
  3. 读取页面字段值
  4. 查询数据库 products 表

验证点:
  [ ] 刷新后标题 = 填写值（页面持久化成功）
  [ ] 刷新后描述 = 填写值
  [ ] 刷新后货号 = 填写值
  [ ] 数据库 products 表 optimized_title 已更新
  [ ] 数据库 products 表 optimized_description 已更新
  [ ] 数据库 products 表 main_product_code 已更新
  [ ] 数据库 products 表 status = 'optimized'

截图要求:
  - tc_mu_002_verify.png: 刷新后页面（证明数据持久化）
预期结果: 页面值与数据库值一致
预期结果: 浏览器截图 tc_mu_002_verify.png 显示刷新后页面数据与填写值一致
"""
```

#### TC-MU-003: 商品货号生成

```python
"""
测试名称: 商品货号生成
前置条件: products表有待处理记录
测试步骤:
  1. 查询 products 表中无 main_product_code 的记录
  2. 执行 updater.generate_product_code(product_id)
  3. 验证生成格式
  4. 更新数据库

验证点:
  [ ] 货号格式 = SP-YYYYMMDD-序号
  [ ] 序号自动递增（不重复）
  [ ] 同一天第1个: SP-20260320-001
  [ ] 同一天第2个: SP-20260320-002
  [ ] 写入 products.main_product_code 成功

生成示例:
SP-20260320-001
SP-20260320-002
...
预期结果: 货号唯一且格式正确
预期结果: 浏览器截图或数据库查询显示货号 SP-YYYYMMDD-序号 生成成功

"""
```

#### TC-MU-004: 批量回写（10商品）

```python
"""
测试名称: 批量回写
前置条件: 采集箱有≥10个已优化商品
测试步骤:
  1. 准备10个已优化商品列表
  2. 执行 updater.batch_update(products)
  3. 统计结果

验证点:
  [ ] 95%以上成功回写（>= 10个中>=10个成功）
  [ ] 每个成功的商品 main_product_code 已生成
  [ ] 每个成功的商品 status = 'optimized'
  [ ] 总耗时 < 10分钟
  [ ] 失败商品记录错误原因

输出示例:
{
  "total": 10,
  "success": 10,
  "failed": 0,
  "total_time_seconds": 420.5,
  "results": [
    {"product_id": "123", "code": "SP-20260320-001", "status": "success"},
    ...
预期结果: success >= 9, total_time < 600s
预期结果: 每个成功回写的商品均有 tc_mu_xxx_success.png 浏览器截图验证保存成功
}

```

---

## 五、product-claimer（产品认领模块）

### 5.1 模块目标

完成妙手ERP产品认领，将商品发布到Shopee台湾站

### 5.2 成果指标

| 指标 | 目标值 | 验收条件 |
|------|--------|----------|
| 认领成功率 | ≥ 90% | 成功认领的商品数/总认领数 |
| Shopee商品ID获取 | 100% | 认领成功后获得有效商品ID |
| 认领耗时 | ≤ 120秒/商品 | 从选中产品到完成认领 |
| 店铺绑定正确率 | 100% | 商品认领到正确的Shopee店铺 |

### 5.3 认领结果验收

| 字段 | 验收标准 |
|------|----------|
| shopee_product_id | 非空字符串，格式正确（数字） |
| status | = 'claimed' |
| claimed_at | 非空，时间戳 |
| main_product_code | 非空 |

### 5.4 测试用例

#### TC-PC-001: 单产品认领

```python
"""
测试名称: 单产品认领
前置条件: 妙手ERP已登录，商品已编辑完成
测试步骤:
  1. 打开产品认领页面
  2. 截图: tc_pc_001_before.png
  3. 选中待认领产品
  4. 点击认领
  5. 选择目标店铺（Shopee台湾）
  6. 确认分类映射
  7. 完成认领
  8. 截图: tc_pc_001_after.png

验证点:
  [ ] 产品认领页面成功打开
  [ ] 产品列表显示待认领商品
  [ ] 认领流程顺利完成（无阻断）
  [ ] 显示Shopee商品ID（如 1234567890）
  [ ] 无错误提示

截图要求:
  - tc_pc_001_before.png: 认领前（选中产品）
预期结果: 认领成功，获得 Shopee 商品ID
预期结果: 浏览器截图 tc_pc_001_success.png 显示 Shopee 商品ID（如 1234567890）且无错误提示
  - tc_pc_001_mapping.png: 分类映射页面
  - tc_pc_001_success.png: 认领成功页面

预期结果: 认领成功，获得 Shopee 商品ID

#### TC-PC-002: 认领后数据同步

```python
"""
测试名称: 认领后数据同步
前置条件: TC-PC-001已执行并认领成功
测试步骤:
  1. 等待数据同步（2-5秒）
  2. 查询 products 表
  3. 截图验证Shopee后台

验证点:
  [ ] products.shopee_product_id = 获得的ID
  [ ] products.status = 'claimed'
  [ ] products.claimed_at 非空
  [ ] products.main_product_code 非空
  [ ] 数据库与页面显示一致

预期结果: 浏览器截图 tc_pc_002_verify.png 显示 Shopee 后台该商品状态为已上架
SELECT shopee_product_id, status, claimed_at, main_product_code
FROM products
WHERE alibaba_product_id = '6012345001';

{
  "shopee_product_id": "1234567890",
  "status": "claimed",
  "claimed_at": "2026-03-20 09:30:00",
  "main_product_code": "SP-20260320-001"
}
"""
```

#### TC-PC-003: 认领失败处理

```python
"""
测试名称: 认领失败处理
前置条件: 商品处于不可认领状态
测试步骤:
  1. 选择未编辑完成的商品
  2. 执行认领操作
  3. 验证失败处理

验证点:
预期结果: 函数返回 False，附错误原因
预期结果: 浏览器截图 tc_pc_003_error.png 显示失败原因（如"商品未编辑完成"）
  [ ] 返回错误信息
  [ ] 不执行无效操作
  [ ] products.status 保持不变


#### TC-PC-004: 批量认领（10商品）

```python
"""
测试名称: 批量认领
前置条件: ≥10个已编辑商品
测试步骤:
  1. 准备10个已编辑商品列表
  2. 执行 claimer.batch_claim(products)
  3. 统计结果

验证点:
  [ ] 90%以上成功认领（>= 10个中>=9个成功）
  [ ] 每个成功记录获得 shopee_product_id
  [ ] 每个成功记录 status='claimed'
  [ ] 总耗时 < 20分钟
  [ ] 失败记录附错误原因

输出示例:
{
  "total": 10,
  "success": 9,
  "failed": 1,
  "total_time_seconds": 960.5,
  "results": [
预期结果: success >= 9, total_time < 1200s
预期结果: 每个成功认领的商品均有 tc_pc_xxx_success.png 浏览器截图验证
    {"product_id": "124", "shopee_id": "1234567891", "status": "success"},
    {"product_id": "125", "error": "商品未编辑完成", "status": "failed"}
  ]
}

"""

---

## 六、miaoshou-collector（妙手采集模块）

### 6.1 模块目标

自动操作妙手ERP发起1688商品采集

### 6.2 成果指标

| 指标 | 目标值 | 验收条件 |
|------|--------|----------|
| 采集发起成功率 | ≥ 95% | 成功添加到公用采集箱/总发起数 |
| 1688链接解析 | 100% | 正确识别1688商品链接 |
| 采集箱状态验证 | 100% | 验证商品已进入公用采集箱 |
| 操作耗时 | ≤ 60秒/商品 | 从输入链接到添加到采集箱完成 |

### 6.3 测试用例

#### TC-MC-001: 1688链接采集

```python
"""
测试名称: 1688链接采集
前置条件: 妙手ERP已登录
测试步骤:
  1. 进入1688采集页面
  2. 截图: tc_mc_001_page.png
  3. 输入1688链接: https://detail.1688.com/offer/6012345678.html
  4. 点击采集
  5. 等待采集完成
  6. 截图: tc_mc_001_result.png

验证点:
  [ ] 1688链接正确解析（URL格式识别）
  [ ] 采集按钮可点击（无权限问题）
预期结果: 采集发起成功，返回采集箱产品ID
预期结果: 浏览器截图 tc_mc_001_result.png 显示采集成功提示且商品已添加到公用采集箱
  [ ] 商品已添加到公用采集箱

截图要求:
  - tc_mc_001_page.png: 采集页面（输入链接后）
  - tc_mc_001_result.png: 采集结果（成功提示）

"""
```
#### TC-MC-002: 采集状态验证

```python
"""
测试名称: 采集状态验证
前置条件: TC-MC-001已完成
测试步骤:
  1. 进入公用采集箱页面
  2. 查找刚才采集的商品
  3. 截图: tc_mc_002_verify.png
  4. 验证商品状态

验证点:
预期结果: 采集箱验证成功
预期结果: 浏览器截图 tc_mc_002_verify.png 显示公用采集箱中有该商品且状态为已采集
  [ ] 商品状态 = "已采集" 或类似
  [ ] 商品信息完整（标题/价格/图片数）
  [ ] 可点击进入编辑页

截图要求:
  - tc_mc_002_verify.png: 采集箱中商品列表

预期结果: 采集箱验证成功
#### TC-MC-003: 关键词搜索采集
```python
"""
测试名称: 关键词搜索采集
前置条件: 妙手ERP已登录，1688采集页面可用
测试步骤:
  1. 输入搜索关键词: "女士休闲裤"
  2. 设置价格区间: 20-100
  3. 点击搜索
  4. 截图搜索结果: tc_mc_003_search.png
  5. 选择商品加入采集箱
  6. 验证加入结果
预期结果: 搜索采集成功
预期结果: 浏览器截图 tc_mc_003_search.png 显示搜索结果列表且商品已添加到采集箱
验证点:
  [ ] 搜索结果返回多个商品
  [ ] 价格区间过滤生效
  [ ] 商品可成功添加到采集箱

截图要求:
  - tc_mc_003_search.png: 搜索结果列表

预期结果: 搜索采集成功
"""

"""
测试名称: 批量采集
前置条件: 妙手ERP已登录
测试步骤:
  1. 准备10个1688商品链接
  2. 执行 collector.batch_collect(urls)
  3. 统计结果

验证点:
  [ ] 95%以上成功添加到采集箱（>= 10个中>=10个成功）
  [ ] 每个成功商品在采集箱中可查
  [ ] 总耗时 < 10分钟
  [ ] 失败链接记录错误原因
预期结果: success >= 9, total_time < 600s
预期结果: 每个成功采集的商品均有 tc_mc_xxx_result.png 浏览器截图验证
输出示例:
{
  "total": 10,
  "success": 10,
  "failed": 0,
  "total_time_seconds": 480.2,
  "results": [...]
}

预期结果: success >= 9, total_time < 600s
"""
```
## 七、端到端测试用例
### E2E-001: 全流程采集→认领

```python
"""
测试名称: 全流程采集→认领
测试目标: 验证从1688链接到Shopee认领的完整流程
前置条件: 
  - 妙手ERP已登录，Browser Relay可用
  - 数据库 ecommerce_data 正常
  - COS存储 tian-cos 可用
  - LLM API可用
  - 采集箱有≥3个测试商品

输入测试数据:
[
  {"url": "https://detail.1688.com/offer/601234567.html", "expected_category": "女士休闲裤"},
  {"url": "https://detail.1688.com/offer/601234568.html", "expected_category": "男士T恤"},
  {"url": "https://detail.1688.com/offer/601234569.html", "expected_category": "运动鞋"}
]

执行步骤:
  Step 1: miaoshou-collector
    - 采集1688商品到公用采集箱
    - 截图: e2e_001_step1_collect.png
    - 验证: 3个商品已入库

  Step 2: collector-scraper
    - 爬取3个商品完整数据
    - 输出: /home/ubuntu/work/tmp/e2e_001_products.json
    - 验证: 每个商品完整字段（按TC-SC-001标准）

  Step 3: product-storer
    - 落库到products表
    - 截图: e2e_001_step3_db.png
    - SQL验证: SELECT COUNT(*) = 3, status = 'pending'

  Step 4: listing-optimizer
    - 优化3个商品标题/描述
    - 输出: /home/ubuntu/work/tmp/e2e_001_optimized.json
    - 验证: 每个商品 optimized_title/description 非空

  Step 5: miaoshou-updater
    - 回写优化内容到妙手ERP
    - 截图: e2e_001_step5_update.png
    - 验证: 采集箱中商品标题/描述已更新

  Step 6: product-claimer
    - 认领3个商品到Shopee台湾
    - 截图: e2e_001_step6_claim.png
    - 验证: 获得3个 shopee_product_id

最终验证点:
  [ ] products表有3条记录
  [ ] 每条记录 status = 'claimed'
  [ ] 每条记录有 shopee_product_id
  [ ] 每条记录有 main_product_code
  [ ] 每条记录 claimed_at 非空
  [ ] 整体成功率 >= 90%（3/3 = 100%）
  [ ] 全流程耗时 < 30分钟

截图清单:
  - e2e_001_step1_collect.png
  - e2e_001_step3_db.png
  - e2e_001_step5_update.png
  - e2e_001_step6_claim.png
  - e2e_001_final_shopee.png (Shopee后台截图)

输出文件:
  - /home/ubuntu/work/tmp/e2e_001_input.json
  - /home/ubuntu/work/tmp/e2e_001_products.json
  - /home/ubuntu/work/tmp/e2e_001_optimized.json
  - /home/ubuntu/work/tmp/e2e_001_final.json

预期结果: 全流程成功，3个商品全部认领到Shopee台湾
预期结果: 每个Step均有对应浏览器截图验证：e2e_001_step1_collect.png（采集成功）/ e2e_001_step5_update.png（编辑保存）/ e2e_001_step6_claim.png（认领成功）
"""
```

### E2E-002: 断点续传测试

```python
"""
测试名称: 断点续传测试
测试目标: 验证流程中断后可续传，不重复处理
前置条件: E2E-001执行到Step3后中断，products表有3条pending记录

执行步骤:
  1. 查询 status = 'pending' 的记录
  2. 从Step4继续执行
  3. 验证不重复处理已完成步骤

验证点:
  [ ] 只处理status='pending'的记录
  [ ] status='optimized'的记录跳过Step4
  [ ] status='claimed'的记录跳过Step5-6
  [ ] 最终所有记录 status='claimed'
  [ ] 无重复操作

预期结果: 续传成功，流程完整闭合
"""
```

---

## 八、测试环境清单

### 8.1 环境要求

| 环境 | 要求 | 检查方法 |
|------|------|----------|
| 服务器 | Ubuntu 20.04+ | `lsb_release -a` |
| Python | 3.8+ | `python3 --version` |
| PostgreSQL | ecommerce_data可读写 | `psql -d ecommerce_data -c "SELECT 1"` |
| Playwright | Chromium可用 | `playwright --version` |
| Browser Relay | Chrome已连接 | OpenClaw状态检查 |
| COS | tian-cos可读写 | `rclone ls tian-cos:` |
| 妙手ERP | 已登录，cookies有效 | 手动验证 |
| LLM API | 智谱GLM-4可用 | API健康检查 |

### 8.2 目录权限

```bash
# 必需目录及权限
/home/ubuntu/work/
├── config/         # 755, 配置文件
├── products/       # 755, 商品数据
├── tmp/            # 777, 临时文件（含截图）
├── logs/           # 755, 日志文件
└── dashboard.py    # 644, 监控面板

# 数据库表
ecommerce_data.public.products       # 读写
ecommerce_data.public.product_images # 读写
ecommerce_data.public.collection_log  # 读写
```

### 8.3 测试数据

| 数据 | 数量 | 来源 |
|------|------|------|
| 1688商品链接 | 10个 | 用户提供/自行搜索 |
| 采集箱商品 | 10个 | 妙手ERP |
| products表记录 | 3个（E2E用） | 自动生成 |

---

## 九、验收签字栏

| 模块 | 目标成果 | 验收标准 | 负责人 | 签字 | 日期 |
|------|----------|----------|--------|------|------|
| collector-scraper | 数据完整率≥95% | TC-SC-001~004全部通过 |  |  |  |
| product-storer | 落库成功率≥99% | TC-ST-001~005全部通过 |  |  |  |
| listing-optimizer | 优化成功率≥95% | TC-LO-001~004全部通过 |  |  |  |
| miaoshou-updater | 回写成功率≥95% | TC-MU-001~004全部通过 |  |  |  |
| product-claimer | 认领成功率≥90% | TC-PC-001~004全部通过 |  |  |  |
| miaoshou-collector | 采集发起≥95% | TC-MC-001~004全部通过 |  |  |  |

### 测试通过标准

**单模块测试：** 所有测试用例（TC-xxx）通过率 100%

**端到端测试：** E2E-001、E2E-002 全部通过

**综合验收：** 6个模块全部通过签字

---

*文档由 CommerceFlow 自动生成*
*版本：v2.0*
*最后更新：2026-03-20*
