# FEATURE_REQUESTS.md - 功能请求

---

## [FEAT-20260320-001] local_1688_weight_scraper

**Logged**: 2026-03-20T21:10:00+08:00
**Priority**: high
**Status**: pending
**Area**: backend

### Requested Capability
用本地浏览器（用户IP）采集1688商品详情页的重量和包装尺寸信息

### User Context
collector-scraper无法从服务器IP抓取1688的重量数据，因为：
1. 1688有反爬限制
2. 重量信息需要登录态或动态加载
用户希望通过本地浏览器绕过反爬，获取准确的重量/包装尺寸

### Complexity Estimate
medium

### Suggested Implementation
1. **Browser Relay方案**：用户本地Chrome + relay服务
   - 需要用户安装OpenClaw Chrome扩展
   - 需要在本地运行relay服务
   - 架构复杂，跨机器有网络限制

2. **本地脚本方案**（推荐）：
   - 用户本地Python + Playwright
   - 直接用用户IP访问1688
   - 提取重量和包装尺寸
   - 更新到数据库或生成CSV

### Metadata
- Frequency: recurring
- Related Features: collector-scraper, profit-analyzer
- Tags: 1688, weight, local-browser, playwright

---
## [FEAT-20260320-002] sku_weight_auto_fill

**Logged**: 2026-03-20T21:30:00+08:00
**Priority**: high
**Status**: pending
**Area**: backend

### Requested Capability
自动用尺寸计算体积重，作为缺失重量的估算值

### User Context
当前数据库中7个SKU缺失重量数据。用户提到"尺码不准影响很大"，需要准确的重量数据来计算SLS运费。

### Complexity Estimate
simple

### Suggested Implementation
在 profit-analyzer 模块增加逻辑：
1. 如果 package_weight 为空但有 package_length/width/height
2. 计算体积重 = 长 × 宽 × 高 ÷ 5000
3. 用体积重作为估算值（偏保守）

注意：对于轻抛货（收纳筐），实际重量可能比体积重轻很多。

### Metadata
- Frequency: first_time
- Related Features: local_1688_weight_scraper, profit-analyzer
- Tags: volume-weight, estimation, sku

---

---
## [FEAT-20260322-001] skill_standardization

**Logged**: 2026-03-22T21:56:00+08:00
**Priority**: medium
**Status**: completed
**Area**: infra

### Requested Capability
将每个工作流模块固化为AgentSkill标准格式

### Resolution
- **Completed**: 2026-03-22T21:56:00+08:00
- **Result**: 
  - 创建了8个AgentSkill: miaoshou-collector, collector-scraper, local-1688-weight, product-storer, listing-optimizer, miaoshou-updater, profit-analyzer, workflow-runner
  - 每个技能包含: SKILL.md + scripts/ + references/
  - 遵循AgentSkill标准格式

### Metadata
- Related Files: skills/*/
- Tags: agent-skill, standardization

---
## [FEAT-20260322-002] workflow_runner_script

**Logged**: 2026-03-22T21:56:00+08:00
**Priority**: high
**Status**: completed
**Area**: backend

### Requested Capability
一键执行完整工作流（8步骤）

### Resolution
- **Completed**: 2026-03-22T21:56:00+08:00
- **Result**: 创建了 skills/workflow-runner/scripts/workflow_runner.py
  - 支持完整模式: --url "1688链接"
  - 支持轻量模式: --lightweight（跳过采集）
  - 支持批量处理: --url-file urls.txt

### Metadata
- Related Files: skills/workflow-runner/scripts/workflow_runner.py
- Tags: workflow, automation, runner

## 2026-04-04 用户反馈的问题

### 问题1：标题和描述不一致
**现象**：商品发布后，存在标题和描述内容不一致的情况，没有校验处理
**影响**：降低转化率，影响买家体验
**建议方案**：
- 在Step 5 (listing-optimizer) 完成后，增加一致性校验模块
- 校验逻辑：描述中提到的SKU规格、颜色、数量等是否与标题一致
- 如不一致，标记警告并要求重新核对

### 问题2：成本利润计算不完整
**现象**：当前利润计算缺少头程运费（1688采购运费）和货代费用（2-3 CNY）
**影响**：利润计算偏低，实际盈利可能不如预期
**建议方案**：
- 在 profit-analyzer 模块增加"头程运费"字段
- 头程运费来源：从 local-1688-weight 服务获取1688商品的实际运费数据
- 货代费用固定为 2-3 CNY/单（可在配置中设置）
- 更新利润公式：总成本 = 采购价 + 头程运费 + 货代费 + SLS运费 + 佣金 + 手续费

### 问题3：库存更新不及时
**现象**：部分1688厂家不更新库存，导致Shopee显示有货但实际缺货
**影响**：客户下单后无法发货，影响店铺评分
**建议方案**：
- 在商品列表增加"库存风险"标记
- 库存来源优先级：1688实时API > 1688页面爬虫 > 固定默认值（如99）
- 低于10件的SKU标记"低库存警告"
- 0件的SKU标记"缺货"，不下单或自动下架
- 用户可设置库存同步频率（每1/6/12/24小时）
- 考虑增加"库存异常"标志：1688有库存但价格大幅下降，可能为假货

