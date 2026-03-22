# local-1688-weight API 文档

## 端点

### 健康检查

```
GET http://127.0.0.1:9090/health
```

响应:
```json
{"service": "1688-weight-fetcher", "status": "ok"}
```

### 获取重量

```
POST http://127.0.0.1:9090/fetch-weight
Content-Type: application/json

{
  "product_id": "1027205078815"
}
```

## 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 请求是否成功 |
| sku_count | int | SKU数量 |
| sku_list | array | SKU列表 |
| sku_list[].sku_name | string | SKU规格名称 |
| sku_list[].weight_g | float | 重量（克） |
| sku_list[].length_cm | float | 长度（厘米） |
| sku_list[].width_cm | float | 宽度（厘米） |
| sku_list[].height_cm | float | 高度（厘米） |

## 重量单位转换

- 输入: 1688页面可能显示 kg 或 g
- 输出: 统一为 g（克）

```
kg → g: value × 1000
g → g: value × 1
```

## 尺寸提取正则

```python
size_patterns = [
    r'(\d+)\s*\*\s*(\d+)\s*\*\s*(\d+)\s*(?:cm|CM|厘米)?',
    r'(\d+)\s*x\s*(\d+)\s*x\s*(\d+)\s*(?:cm|CM|厘米)?',
]
```
