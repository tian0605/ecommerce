# 待优化清单 - 2026-03-27/28

## P0 - 阻塞问题

### 1. local-1688-weight 数据不准确
- **问题**：返回 weight_g=41g（太轻），缺少尺寸数据
- **原因**：来自缓存，非实时抓取
- **解决**：需要本地服务刷新缓存，重新抓取1688页面
- **负责人**：本地Windows服务

### 2. product-storer SKU数据落库问题
- **问题**：product_skus表 weight/尺寸字段为0或NULL
- **根因**：依赖 local-1688-weight 数据源
- **解决**：等 local-1688-weight 修复后重新测试

## P1 - 质量问题

### 3. listing-optimizer DeepSeek输出不稳定
- **问题**：偶尔仍输出禁止词（免運、熱銷）
- **根因**：提示词约束不够强
- **优化方向**：
  - 进一步强化禁止词规则
  - 或考虑后处理过滤
  - 或使用更严格的system prompt

### 4. listing-optimizer 提示词优化
- **文件**：`/home/ubuntu/.openclaw/skills/listing-optimizer/optimizer.py`
- **当前提示词**：简化为短格式
- **优化空间**：
  - 结合完整v3.0提示词的质量
  - 保持DeepSeek兼容性（避免过长超时）

## P2 - 效率问题

### 5. listing-optimizer 超时问题
- **问题**：DeepSeek响应慢（30秒+）
- **当前**：超时300秒
- **优化方向**：
  - 优化网络连接
  - 或添加批量处理机制

### 6. local-1688-weight 缓存机制
- **问题**：返回缓存数据，无法获取最新数据
- **优化方向**：
  - 支持强制刷新参数
  - 或添加缓存失效机制

## 已完成 ✅

- [x] miaoshou-updater 7字段填写
- [x] miaoshou-updater 虚拟滚动选择器
- [x] miaoshou-updater 动态类目选择
- [x] listing-optimizer DeepSeek集成
- [x] listing-optimizer 降级逻辑
- [x] listing-optimizer 禁止词规则

## 下一步行动

1. **本地服务**：刷新 local-1688-weight 缓存
2. **验证**：重新测试 product-storer 落库
3. **监控**：观察 listing-optimizer 禁止词合规性
