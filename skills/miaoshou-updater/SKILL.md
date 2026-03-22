---
name: miaoshou-updater
description: 妙手ERP商品回写模块。将listing-optimizer优化后的标题和描述，通过Playwright自动化回写到妙手ERP的Shopee采集箱。触发条件：(1)已优化商品需要回写 (2)执行TC-MU-001测试 (3)Shopee发布前最后一步
---

# miaoshou-updater

妙手ERP商品回写模块。将优化后的标题和描述回写到妙手ERP Shopee采集箱。

## 核心文件

- **模块路径**: `/home/ubuntu/.openclaw/skills/miaoshou-updater/updater.py`
- **Cookie文件**: `/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json`

## 使用方法

```python
from miaoshou_updater import MiaoshouUpdater

updater = MiaoshouUpdater()
updater.launch()
result = updater.update_product(product_id=1)
updater.close()
print(result)
```

## 回写流程

1. 从数据库读取已优化商品（status='optimized'）
2. 访问Shopee采集箱
3. 点击商品编辑按钮
4. 填写优化后的标题和描述
5. 保存
6. 更新数据库状态（status='published'）

## 关键URL

- Shopee采集箱: `https://erp.91miaoshou.com/shopee/collect_box/items`

## 数据依赖

- **输入**: products表（status='optimized'）
- **输出**: 妙手ERP商品已更新，数据库status='published'
- **后续模块**: profit-analyzer 利润分析

## 前置条件

1. listing-optimizer 已完成优化
2. 妙手ERP已登录
3. 商品在Shopee采集箱中

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| 编辑按钮点击无效 | 使用JavaScript evaluate绕过Vue |
| 保存失败 | 检查输入框字符限制 |
| Cookie过期 | 重新登录妙手ERP |
| 商品不在采集箱 | 检查miaoshou-collector是否成功 |
