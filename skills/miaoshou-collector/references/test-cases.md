# TC-MC-001: 妙手采集并自动认领

## 测试命令

```bash
cd /home/ubuntu/.openclaw/skills/miaoshou-collector
python collector.py --url "https://detail.1688.com/offer/1027205078815.html"
```

## 验收标准

1. 终端输出 "采集成功" 或类似提示
2. 商品出现在 `https://erp.91miaoshou.com/shopee/collect_box/items`
3. 截图保存在 `/home/ubuntu/work/tmp/miaoshou_collector_test/`

## 成功截图命名

- `tc_mc_001_page_YYYYMMDD_HHMMSS.png` - 页面加载后
- `tc_mc_001_link_filled_YYYYMMDD_HHMMSS.png` - 链接已填写
- `tc_mc_001_result_YYYYMMDD_HHMMSS.png` - 结果提示
- `tc_mc_001_list_YYYYMMDD_HHMMSS.png` - 采集箱列表

## 关键选择器

| 元素 | 选择器 |
|------|--------|
| 1688链接输入框 | `input[placeholder*="1688"]` 或 `.el-input__inner` |
| 采集按钮 | button: contains("采集") |
| 成功提示 | `.el-message--success` |
