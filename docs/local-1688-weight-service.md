# 本地 1688 重量获取服务

## 背景

远程服务器无法直接访问 1688（IP反爬限制），通过 SSH 隧道调用本地服务获取准确的重量和尺寸信息。

## 架构

```
远程 collector-scraper
    ↓ HTTP POST (通过隧道 127.0.0.1:8080)
本地 1688-weight-server
    ↓ Playwright + Cookies
1688 商品详情页
    ↓
返回重量/尺寸 JSON
```

## 文件说明

| 文件 | 位置 | 说明 |
|------|------|------|
| local-1688-weight-server.py | 本地 | HTTP 服务，监听 8080 端口 |
| remote_weight_caller.py | 远程 | 远程调用本地服务的模块 |

## 本地配置步骤

### 1. 安装依赖

```bash
pip install flask playwright requests
playwright install chromium
```

### 2. 准备 1688 Cookies

在浏览器登录 1688，然后导出 cookies 到 `1688_cookies.json`：

```json
{
  "cookies": [
    {
      "name": "...",
      "value": "...",
      "domain": ".1688.com",
      "path": "/",
      "secure": true
    }
  ]
}
```

### 3. MobaXterm 隧道配置

```
隧道类型: Local
Forward Port: 8080
Remote Server: 127.0.0.1
Remote Port: 8080
```

### 4. 启动服务

```bash
cd /path/to/local-1688-weight-server
python local-1688-weight-server.py
```

服务启动后会显示：
```
==================================================
1688 重量获取服务
==================================================
监听地址: http://127.0.0.1:8080
通过隧道映射后，远程可访问

接口:
  POST /fetch-weight  - 获取单个商品重量
  POST /batch-fetch  - 批量获取
  GET  /health       - 健康检查

注意: 需要提前准备好 1688_cookies.json
==================================================
```

## 远程使用

在 `collector-scraper` 或 `product-storer` 中调用：

```python
from remote_weight_caller import fetch_weight_from_local

# 获取商品重量
result = fetch_weight_from_local("1027205078815")
if result and result['success']:
    weight = result['weight_g']
    length = result['length_cm']
    width = result['width_cm']
    height = result['height_cm']
    print(f"重量: {weight}kg, 尺寸: {length}x{width}x{height}cm")
else:
    print(f"获取失败: {result.get('error') if result else '服务不可用'}")
```

## API 接口

### POST /fetch-weight

获取单个商品重量。

**请求：**
```json
{
  "product_id": "1027205078815"
}
```

**响应：**
```json
{
  "success": true,
  "product_id": "1027205078815",
  "url": "https://detail.1688.com/offer/1027205078815.html",
  "weight_g": 1500,
  "length_cm": 30,
  "width_cm": 20,
  "height_cm": 15,
  "error": null
}
```

### POST /batch-fetch

批量获取多个商品。

**请求：**
```json
{
  "product_ids": ["1027205078815", "6023456789012"]
}
```

### GET /health

健康检查。

**响应：**
```json
{
  "status": "ok",
  "service": "1688-weight-fetcher"
}
```

## 故障排除

### 本地服务无法连接
1. 检查 MobaXterm 隧道是否建立
2. 检查本地防火墙是否允许 8080 端口
3. 确认 `python local-1688-weight-server.py` 是否在运行

### 返回 "未能提取到重量/尺寸信息"
1. 检查 1688 cookies 是否过期
2. 尝试重新登录 1688 并导出新 cookies
3. 商品可能本身没有填写重量/尺寸

### HTTP 403 错误
1. Cookies 过期，需要重新登录
2. 账号被风控
