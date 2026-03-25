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

---

## [LRN-20260323-001] best_practice

**Logged**: 2026-03-23T22:34:00+08:00
**Priority**: critical
**Status**: pending
**Area**: backend

### Summary
PostgreSQL INSERT语句必须明确列出所有字段，否则默认值可能不生效

### Details
测试中发现 products.is_deleted 和 product_skus.is_deleted 字段写入NULL而不是默认值0。

原因：INSERT语句没有明确列出这些字段，依赖数据库默认值可能失败。

解决方案：明确在INSERT语句中包含所有字段及其值，即使是默认值也要显式指定。

### Metadata
- Source: error
- Related Files: skills/product-storer/storer.py
- Tags: postgresql, insert, default-value

---
## [LRN-20260323-002] best_practice

**Logged**: 2026-03-23T22:34:00+08:00
**Priority**: high
**Status**: pending
**Area**: backend

### Summary
collector-scraper采集箱SKU与编辑对话框SKU可能不一致

### Details
测试商品1026137274944：
- 采集箱列表页SKU：["灰色","米色","灰色>53L","米色>53L",...]
- 编辑对话框SKU：["麋鹿/100L：50*40*50cm","水草/140L：50*40*70cm",...]

两者不匹配导致：
1. price/stock无法正确关联
2. sku_id_new生成失败
3. 颜色信息丢失

需要优化SKU匹配算法，基于规格尺寸关联而非名称。

### Metadata
- Source: error
- Related Files: skills/collector-scraper/scraper.py, skills/product-storer/storer.py
- Tags: sku, matching, scraper

---
## [LRN-20260323-003] best_practice

**Logged**: 2026-03-23T22:34:00+08:00
**Priority**: critical
**Status**: pending
**Area**: infra

### Summary
SSH隧道连接不稳定，需要心跳检测和自动重连机制

### Details
local-1688-weight服务在测试过程中多次断开：
- MobaXterm隧道可能意外断开
- 服务进程可能崩溃
- 网络波动导致连接中断

建议：
1. 在服务器端添加健康检查心跳
2. 用户端保持SSH会话活跃
3. 记录最后一次成功连接时间

### Metadata
- Source: error
- Related Files: skills/local-1688-weight/
- Tags: ssh-tunnel, health-check, connection

---
## [LRN-20260323-004] best_practice

**Logged**: 2026-03-23T22:34:00+08:00
**Priority**: medium
**Status**: pending
**Area**: architecture

### Summary
新货号规则（18位）设计合理，支持多渠道多供应商扩展

### Details
新货号格式：`[渠道码(2)][供应商码(4)][系列码(3)][年份(2)][流水号(7)]`

示例：`AL0001001260000001` (AL=1688渠道, 0001=供应商, 001=系列, 26=2026年, 0000001=序号)

优势：
1. 18位定长，易于索引
2. 包含渠道、供应商、系列信息，可追溯
3. 流水号支持日/周/年多种维度

### Metadata
- Source: success
- Related Files: skills/product-storer/storer.py
- Tags: product-id, format, architecture

---

## [LRN-20260325-001] best_practice

**Logged**: 2026-03-25T22:50:00+08:00
**Priority**: critical
**Status**: completed
**Area**: backend

### Summary
miaoshou-updater类目组件是el-cascader（级联选择器），不是el-dropdown

### Details
妙手ERP编辑对话框中的类目选择组件是 `el-cascader`，不是常见的 `el-dropdown`。

关键特征：
- cascader节点在DOM中存在但Playwright locator检测为不可见（visibility: hidden）
- 必须用JS `.click()` 直接点击节点，不能用Playwright locator
- 三级级联：家居生活 → 居家收纳 → 收纳盒、收纳包与篮子
- 每级点击后需等0.3-0.5秒让面板更新

选择器：`document.querySelectorAll(".el-cascader-node")`

### Metadata
- Source: testing
- Related Files: skills/miaoshou-updater/updater.py
- Tags: miaoshou, cascader, category, vue

---

## [LRN-20260325-002] best_practice

**Logged**: 2026-03-25T22:50:00+08:00
**Priority**: critical
**Status**: completed
**Area**: backend

### Summary
妙手ERP编辑对话框：所有操作在一个session内完成，不要刷新页面

### Details
测试中发现：每次page.goto()都会刷新页面，导致已填字段全部丢失。

教训：
1. 打开编辑对话框后，所有字段填写、类目选择、发布操作必须在同一个session内完成
2. 脚本运行中途不要重新加载页面
3. 如果脚本中断，已填数据丢失，只能重新开始

解决方案：一次性编写完整脚本，包含所有8个步骤（定位→填字段→cascader→保存并发布→全选→确定发布→关闭弹窗）

### Metadata
- Source: error
- Related Files: skills/miaoshou-updater/updater.py
- Tags: miaoshou, session, browser-automation

---

## [LRN-20260325-003] best_practice

**Logged**: 2026-03-25T22:50:00+08:00
**Priority**: critical
**Status**: completed
**Area**: backend

### Summary
Form item索引：0=标题, 1=描述, 3=主货号, 5=类目, 12=重量, 13=尺寸

### Details
妙手ERP编辑对话框的form-item使用0-based索引：

| index | 字段 | 组件 | 选择器 |
|-------|------|------|--------|
| 0 | 产品标题 | input | `input[placeholder="标题不能为空"]` |
| 1 | 简易描述 | textarea | `.el-dialog__body .el-form-item:nth-child(2) textarea` |
| 3 | 主货号 | input | `.el-dialog__body .el-form-item:nth-child(4) input` |
| 5 | 类目 | **el-cascader** | `.el-dialog__body .el-form-item:nth-child(6) .el-cascader` |
| 12 | 包裹重量 | input | `.el-dialog__body .el-form-item:nth-child(13) input` |
| 13 | 包裹尺寸 | 3个input | `.el-dialog__body .el-form-item:nth-child(14) input` |

注意：nth-child是1-based，所以 index N = nth-child(N+1)

### Metadata
- Source: testing
- Related Files: skills/miaoshou-updater/updater.py
- Tags: miaoshou, form-item, index, selector

---

## [LRN-20260325-004] best_practice

**Logged**: 2026-03-25T22:50:00+08:00
**Priority**: critical
**Status**: completed
**Area**: backend

### Summary
重量单位链：数据库g → ERP填kg → 公式 weight_g / 1000

### Details
重量数据流：
1. 1688商品重量单位：克(g)
2. 本地1688服务返回：克(g)
3. product_skus.package_weight：克(g)
4. ERP编辑对话框：千克(kg)

换算公式：`erp_value_kg = package_weight_g / 1000`

示例：2500g → 填 2.5

### Metadata
- Source: success
- Related Files: skills/miaoshou-updater/updater.py, skills/product-storer/storer.py
- Tags: weight, unit, conversion, g-kg

