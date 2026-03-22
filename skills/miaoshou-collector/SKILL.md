---
name: miaoshou-collector
description: 妙手ERP商品采集模块。通过Playwright自动化操作妙手ERP Web界面，将1688商品采集并自动认领到Shopee采集箱。触发条件：(1)用户提供1688商品链接需要采集 (2)执行TC-MC-001测试 (3)需要将商品加入Shopee采集箱
---

# miaoshou-collector

妙手ERP商品采集模块。功能：输入1688商品链接，通过妙手ERP的"采集并自动认领"功能将商品采集到Shopee采集箱。

## 核心文件

- **模块路径**: `/home/ubuntu/.openclaw/skills/miaoshou-collector/collector.py`
- **Cookie文件**: `/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json`
- **临时目录**: `/home/ubuntu/work/tmp/miaoshou_collector_test/`

## 使用方法

```bash
cd /home/ubuntu/.openclaw/skills/miaoshou-collector
python collector.py --url "https://detail.1688.com/offer/1027205078815.html"
```

或Python调用：

```python
from collector import MiaoshouCollector

collector = MiaoshouCollector()
collector.launch()
result = collector.collect(url="1688链接")
collector.close()
```

## 关键URL

| 页面 | URL |
|------|-----|
| 产品采集 | `https://erp.91miaoshou.com/common_collect_box/index?fetchType=linkCopy` |
| Shopee采集箱 | `https://erp.91miaoshou.com/shopee/collect_box/items` |

## 前置条件

1. 妙手ERP已登录（Cookie文件存在且 <24小时）
2. Playwright + Chromium 已安装

## 数据依赖

- **输入**: 1688商品链接
- **输出**: 商品进入妙手ERP的Shopee采集箱
- **后续模块**: collector-scraper 从采集箱提取数据

## 流程说明

1. 加载Cookie并启动浏览器
2. 访问产品采集页面
3. 填写1688链接到输入框
4. JavaScript点击"采集并自动认领"按钮（绕过Vue事件）
5. 等待页面提示"成功"
6. 截图保存证据
7. 关闭浏览器

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| Cookie过期 | 重新登录妙手ERP，导出新Cookie |
| 采集失败 | 检查1688链接是否有效 |
| 按钮点击无响应 | 使用JavaScript `evaluate()` 绕过Vue事件绑定 |
| 浏览器启动失败 | `playwright install chromium` 重新安装 |
