---
name: local-1688-weight
description: 本地1688重量服务。通过SSH隧道访问本地Windows机器上运行的Flask服务，获取1688商品的准确重量和尺寸数据。触发条件：(1)product-storer需要准确物流数据 (2)执行TC-LW-001测试 (3)利润分析需要重量数据
---

# local-1688-weight

本地1688重量服务。通过SSH隧道从本地Windows机器获取1688商品的准确重量和尺寸。

**重要**：此服务运行在本地Windows机器，通过MobaXterm SSH隧道（`127.0.0.1:9090`）访问。

## 核心文件

- **服务脚本**: `/root/.openclaw/workspace-e-commerce/skills/local-1688-weight-server.py`
- **调用脚本**: `/root/.openclaw/workspace-e-commerce/skills/remote_weight_caller.py`

## 隧道建立（MobaXterm）

```
SSH隧道配置：
- 方向：Local → Remote
- 源主机：127.0.0.1
- 源端口：9090
- 远程主机：127.0.0.1
- 远程端口：8080
```

## 服务启动（本地Windows）

```bash
cd C:\path\to\project
python local-1688-weight-server.py
# 监听 127.0.0.1:8080
```

## 使用方法

```bash
# 健康检查
curl http://127.0.0.1:9090/health

# 获取重量
curl -X POST http://127.0.0.1:9090/fetch-weight \
  -H "Content-Type: application/json" \
  -d '{"product_id": "1027205078815"}'
```

## 返回数据结构

```json
{
  "success": true,
  "sku_count": 4,
  "sku_list": [
    {
      "sku_name": "组合【三件套】",
      "weight_g": 910,
      "length_cm": 41,
      "width_cm": 21.5,
      "height_cm": 36
    },
    {
      "sku_name": "斜口【小号】X3",
      "weight_g": 825,
      "length_cm": 41,
      "width_cm": 21.5,
      "height_cm": 36
    },
    {
      "sku_name": "带轮【中号】X3",
      "weight_g": 912,
      "length_cm": 41,
      "width_cm": 21.5,
      "height_cm": 36
    },
    {
      "sku_name": "带轮【大号】X3",
      "weight_g": 975,
      "length_cm": 41,
      "width_cm": 21.5,
      "height_cm": 36
    }
  ]
}
```

## 数据字段说明

**sku_list 中每个SKU的数据：**

| 字段 | 单位 | 说明 |
|------|------|------|
| `sku_name` | - | SKU名称（如 组合【三件套】、斜口【小号】X3） |
| `weight_g` | 克(g) | **per-SKU重量**，每个SKU独立重量 |
| `length_cm` | 厘米(cm) | 包装长度 |
| `width_cm` | 厘米(cm) | 包装宽度 |
| `height_cm` | 厘米(cm) | 包装高度 |

**重要**：现在支持 per-SKU 独立权重，不再是所有SKU共用一个重量。

## 前置条件

1. MobaXterm SSH隧道已建立（端口9090）
2. 本地Windows服务已启动
3. 1688 Cookie文件存在

## 数据依赖

- **输入**: 1688商品ID
- **输出**: 准确重量和尺寸（比妙手ERP更准确）
- **接收模块**: product-storer 合并落库

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| `curl` 连接失败 | 检查MobaXterm隧道状态 |
| `{"success":false}` | 检查本地1688登录状态 |
| 重量为0或null | 1688页面未加载完全，等待重试 |
