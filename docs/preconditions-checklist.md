# 工作流前置条件检查清单

## ⚠️ 每次使用自动化工作流前，必须检查以下三个条件

---

## 条件1️⃣：妙手ERP平台浏览器登录状态

**检查方式：**
1. 确认 `miaoshou_cookies.json` 存在且未过期
2. 或确认浏览器已打开并登录 https://erp.91miaoshou.com

**Cookies有效期：** 一般24小时

**位置：** `/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json`

**如果失效：** 重新登录妙手ERP并导出新Cookies

---

## 条件2️⃣：本地爬虫服务接口启用

**检查方式：**
```bash
curl http://127.0.0.1:8080/health
```

**预期响应：** `{"service":"1688-weight-fetcher","status":"ok"}`

**本地服务：** `local-1688-weight-server.py`

**启动命令：**
```bash
python local-1688-weight-server.py
```

---

## 条件3️⃣：本地和远程服务器的隧道打开

**检查方式：**
```bash
ss -tlnp | grep 8080
```

**预期：** 显示 `127.0.0.1:8080` 监听中

**MobaXterm隧道配置：**
```
类型: Local port forward
Local port: 8080
Remote server: 127.0.0.1
Remote port: 8080
```

---

## 快速检查脚本

```bash
#!/bin/bash
echo "=== 工作流前置条件检查 ==="

# 条件1: 妙手Cookies
if [ -f "/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json" ]; then
    echo "✅ 条件1: 妙手Cookies文件存在"
else
    echo "❌ 条件1: 妙手Cookies文件不存在"
fi

# 条件2: 本地服务
if curl -s --max-time 5 http://127.0.0.1:8080/health > /dev/null 2>&1; then
    echo "✅ 条件2: 本地服务正常"
else
    echo "❌ 条件2: 本地服务未启动"
fi

# 条件3: 隧道
if ss -tlnp | grep -q 8080; then
    echo "✅ 条件3: 隧道已建立"
else
    echo "❌ 条件3: 隧道未建立"
fi

echo "=== 检查完成 ==="
```

---

## 检查频率

| 时机 | 是否需要检查 |
|------|-------------|
| 开始新的采集任务前 | ✅ 必须检查 |
| 每日首次使用 | ✅ 必须检查 |
| 任务中断后恢复 | ✅ 必须检查 |

---

## 失效处理

| 条件 | 失效表现 | 处理方法 |
|------|----------|----------|
| 妙手Cookies | 采集失败，页面跳转登录 | 重新登录妙手并导出Cookies |
| 本地服务 | Health check失败 | 重启 `python local-1688-weight-server.py` |
| 隧道 | 连接拒绝 | 检查MobaXterm隧道连接 |
