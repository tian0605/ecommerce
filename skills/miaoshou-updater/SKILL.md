---
name: miaoshou-updater
description: 妙手ERP商品回写模块。将listing-optimizer优化后的标题和描述，通过Playwright自动化回写到妙手ERP的Shopee采集箱。触发条件：(1)已优化商品需要回写 (2)执行TC-MU-001测试 (3)Shopee发布前最后一步
---

# miaoshou-updater

妙手ERP商品回写模块。将优化后的标题和描述回写到妙手ERP Shopee采集箱。

## 核心文件

- 兼容入口: `/home/ubuntu/.openclaw/skills/miaoshou-updater/updater.py`
- 实际实现: `/home/ubuntu/.openclaw/skills/miaoshou_updater/updater.py`
- Cookie文件: 优先读取 `miaoshou-updater/miaoshou_cookies.json`，其次回退到 `miaoshou-collector/miaoshou_cookies.json`

## 使用方法

```python
from miaoshou_updater import MiaoshouUpdater

updater = MiaoshouUpdater(headless=True)
updater.launch()
try:
	result = updater.update_product({'alibaba_product_id': '1031400982378'})
	print(result)
finally:
	updater.close()
```

```bash
# 列出待处理商品
python updater.py --list --limit 20

# 发布指定货源ID
python updater.py --product-id 1031400982378
```

## 回写流程

1. 从数据库读取已优化商品（status='optimized'）
2. 访问Shopee采集箱
3. 点击商品编辑按钮
4. 一次性填写 7 个关键字段（标题、描述、主货号、类目、重量、尺寸、必要属性）
5. 点击“保存并发布”
6. 处理“发布产品”确认弹窗，执行全选/确定发布
7. 更新数据库状态（status='published'）

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
| 编辑按钮点击无效 | 按货源ID定位后用 JavaScript 点击，避免 Vue 包装层拦截 |
| 保存并发布后无反应 | 先关闭“查看来源信息”等遮挡弹窗，再等待“发布产品”对话框 |
| 最后发布失败 | 确保勾选全选 checkbox，并兼容“确定发布”/“批量发布”两种按钮文案 |
| 保存失败 | 检查重量、尺寸和类目属性必填项是否已填充 |
| Cookie过期 | 重新登录妙手ERP |
| 商品不在采集箱 | 检查miaoshou-collector是否成功 |
