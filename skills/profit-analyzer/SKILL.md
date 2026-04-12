---
name: profit-analyzer
description: Shopee台湾站利润分析模块。根据商品重量、采购价计算SLS运费、平台费用、藏价策略，输出建议售价和利润率。触发条件：(1)已发布商品需要利润分析 (2)执行TC-PA-001测试 (3)运营决策需要利润数据
---

# profit-analyzer

Shopee台湾站利润分析器。计算商品在Shopee台湾站的利润率和建议售价。

## 核心文件

- **模块路径**: `/root/.openclaw/workspace-e-commerce/skills/profit-analyzer/analyzer.py`

## 费率配置

```python
COMMISSION_RATE = 0.14        # 佣金14%（前三个月免佣）
TRANSACTION_FEE_RATE = 0.025  # 交易手续费2.5%
PRE_SALE_SERVICE_RATE = 0.0   # 预售服务费固定为0
AGENT_FEE_CNY = 3.00          # 货代费3元/单

# 头程运费
# 来自 local-1688-weight 服务返回的 freight_info.total_cost（单位 CNY）

# SLS运费
FIRST_WEIGHT_G = 500
FIRST_WEIGHT_TWD = 70.00      # 首重500g=70TWD
CONTINUE_WEIGHT_G = 500
CONTINUE_WEIGHT_TWD = 30.00    # 续重每500g=30TWD

# 买家实付运费
BUYER_SHIPPING_ORDINARY = 55.00   # 普通订单(<299)
BUYER_SHIPPING_DISCOUNT = 30.00    # 满299
BUYER_SHIPPING_FREE = 0.00         # 满490免运

DEFAULT_TARGET_PROFIT_RATE = 0.20  # 默认目标利润率20%
```

## 利润计算公式

```
总成本 = 采购价(CNY) + 头程运费(CNY) + 货代费(CNY) + SLS运费(TWD) + 平台费(TWD)
平台费 = 售价 × (佣金14% + 交易手续费2.5% + 预售服务费3%)

SLS运费 = 首重70 + ceil((重量g - 500) / 500) × 30

建议售价 = (采购价 × 汇率 + 头程运费 × 汇率 + 货代费 + 平台费) / (1 - 佣金率 - 手续费率 - 预售费率)
```

## 使用方法

```python
from profit_analyzer import ProfitAnalyzer

analyzer = ProfitAnalyzer()
result = analyzer.analyze_product({
    'alibaba_product_id': '1027205078815',
    'weight_g': 627,
    'purchase_price_cny': 25.0
})
print(result)
```

## 返回数据结构

```python
{
    'status': 'success',
    'alibaba_product_id': '1027205078815',
    'weight_kg': 0.627,
    'purchase_price_cny': 25.0,
    'domestic_shipping_cny': 5.0,
    'agent_fee_cny': 3.0,
    'exchange_rate': 4.5,
    'sls_shipping_twd': 85.0,
    'domestic_shipping_twd': 22.5,
    'agent_fee_twd': 13.5,
    'platform_fee_twd': 87.25,
    'total_cost_twd': 407.25,
    'suggested_price_twd': 549,
    'target_profit_rate': 0.20,
    'estimated_profit_twd': 77.0,
    'estimated_profit_cny': 17.1
}
```

## 飞书表格输出

分析结果自动写入飞书多维表格：
- **文档名称**: shopee商品上架利润分析
- **app_token**: GlqObu4Z2aumBks2SPpcNKRDnWf
- **table_id**: tblHsfVWolBpeSNg
- **URL**: https://pcn0wtpnjfsd.feishu.cn/base/GlqObu4Z2aumBks2SPpcNKRDnWf

当前飞书明细中会单独输出 `货代费(CNY)` 和 `货代费(TWD)` 字段，便于运营核对固定 3 元/单的海外发运前成本。
如果本地1688服务返回 `freight_info`，飞书中还会单独输出 `头程运费(CNY)` 和 `头程运费(TWD)`。

## 调试方式

按指定 1688 商品 ID 生成 SKU 级利润分析，并按 `渠道 + 站点 + 商品主货号 + SKU名称` 做 upsert 去重：

```bash
python3 skills/profit-analyzer/analyzer.py \
    --alibaba-ids 1026640656479 965854175819 1027205078815 1026137274944

# 固定入口
python3 scripts/run_profit_analysis_sync.py --ids 1026640656479,965854175819
```

VS Code 任务：运行 `profit-analysis-sync`，输入逗号分隔的 1688 商品 ID 即可。

## 数据依赖

- **输入**: products表（status='published'）
- **输出**: 利润分析结果 + 飞书表格记录

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| 汇率获取失败 | 使用默认汇率4.5 |
| 重量异常 | 检查local-1688-weight数据 |
| 飞书写入失败 | 检查app_token权限 |
