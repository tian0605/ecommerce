# LEARNINGS.md - 电商运营助手学习记录

---

## [LRN-20260320-001] best_practice

**Logged**: 2026-03-20T20:37:00+08:00
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
飞书发送图片需要先上传到飞书API获取image_key，不能直接用本地路径

### Details
使用 `message` 工具的 `media` 参数发送图片到飞书失败。原因是飞书要求：
1. 先获取 tenant_access_token
2. 调用 `POST /open-apis/im/v1/images` 上传图片获取 image_key
3. 再调用 `POST /open-apis/im/v1/messages` 发送图片消息

### Suggested Action
创建 `scripts/feishu_send_image.py` 脚本封装这个流程

### Metadata
- Source: error
- Related Files: scripts/feishu_send_image.py
- Tags: feishu, image, api
- See Also: ERR-20260320-001

---
## [LRN-20260320-002] best_practice

**Logged**: 2026-03-20T20:48:00+08:00
**Priority**: critical
**Status**: pending
**Area**: backend

### Summary
SLS藏价计算错误：之前用15 TWD，正确应该是45 TWD（630g商品）

### Details
根据用户提供的Shopee官方文档，SLS运费计算：
- 卖家实付 = 首重70 + 续重(每500g 30TWD)
- 买家实付 = 55 TWD（普通订单）
- 藏价 = 卖家实付 - 买家实付

630g商品：
- 卖家实付 = 70 + 30 = 100 TWD
- 藏价 = 100 - 55 = 45 TWD（不是15 TWD）

### Suggested Action
更新 profit-analyzer 模块的 SLS 计算逻辑

### Metadata
- Source: user_feedback
- Related Files: skills/profit-analyzer/analyzer.py
- Tags: shopee, sls, shipping, 藏价

---
## [LRN-20260320-003] best_practice

**Logged**: 2026-03-20T22:10:00+08:00
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Browser Relay架构：Chrome和Gateway异地时需要本地启动relay服务

### Details
Browser Relay连接失败的原因：
- Chrome在用户本地电脑
- Gateway在远程服务器
- 两者不在同一机器时，需要在本地电脑运行 `clawdbot browser serve`
- Chrome扩展连接本地Relay (127.0.0.1:18792)
- Relay再连接到远程Gateway

### Suggested Action
记录此架构问题，考虑替代方案（本地脚本）作为更简单的选项

### Metadata
- Source: error
- Tags: browser-relay, architecture, network

---
## [LRN-20260320-004] best_practice

**Logged**: 2026-03-20T21:10:00+08:00
**Priority**: critical
**Status**: pending
**Area**: backend

### Summary
collector-scraper未采集1688商品重量/包装尺寸数据

### Details
数据库中 product_skus 表的 package_weight、package_length/width/height 字段为空。
原因：1688详情页的重量信息未被抓取，可能是：
1. 1688页面动态加载，需要登录态
2. 反爬限制，内容被截断
3. 选择器不正确

### Suggested Action
在采集流程中增加：用本地浏览器（Browser Relay或本地脚本）获取1688详情页的重量尺寸信息

### Metadata
- Source: error
- Related Files: skills/collector-scraper/scraper.py, skills/profit-analyzer/analyzer.py
- Tags: 1688, weight, scrape

---
---
## [LRN-20260322-001] best_practice

**Logged**: 2026-03-22T21:56:00+08:00
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
AgentSkill标准格式：每个技能应包含SKILL.md + scripts/ + references/ 三部分

### Details
今天将8个工作流模块固化为AgentSkill标准格式：
- SKILL.md: YAML frontmatter (name/description) + 使用说明
- scripts/: 可执行脚本
- references/: 详细参考文档

关键原则：
1. SKILL.md要精简，<500行，详细内容放references/
2. frontmatter的description是触发机制，要详细描述何时使用
3. scripts/中的脚本应该能独立运行

### Metadata
- Source: self
- Related Files: skills/*/SKILL.md
- Tags: agent-skill, format, structure

---
## [LRN-20260322-002] best_practice

**Logged**: 2026-03-22T21:56:00+08:00
**Priority**: critical
**Status**: pending
**Area**: backend

### Summary
1688重量数据获取：本地服务 + SSH隧道是最佳方案

### Details
通过MobaXterm SSH隧道访问本地Windows机器上的Flask服务：
- 本地服务: 127.0.0.1:8080
- 隧道映射: 127.0.0.1:9090 → 远程
- 用户Chrome已登录1688，本地IP不受反爬限制

优势：
1. 不需要Browser Relay插件
2. 不依赖复杂架构
3. 数据准确（用户IP，无反爬）

### Metadata
- Source: success
- Related Files: skills/local-1688-weight/
- Tags: 1688, weight, ssh-tunnel, architecture

---
## [LRN-20260322-003] best_practice

**Logged**: 2026-03-22T21:56:00+08:00
**Priority**: medium
**Status**: pending
**Area**: backend

### Summary
SKU多规格组合逻辑：一个规格维度 × 另一个规格维度的选项数 = 总SKU数

### Details
测试商品1027205078815的SKU组合：
- 颜色: [深棕色] = 1个选项
- 尺寸: [大号, 小号, 一套] = 3个选项
- 总SKU = 1 × 3 = 3个

注意："一套"是组合装，应该作为一个独立SKU存在。

### Metadata
- Source: testing
- Related Files: skills/collector-scraper/scraper.py
- Tags: sku,规格, combination
