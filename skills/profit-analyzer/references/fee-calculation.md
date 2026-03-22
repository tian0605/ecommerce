# 利润计算详解

## 费率表

### Shopee台湾站

| 费用项 | 费率 | 说明 |
|--------|------|------|
| 佣金 | 14% | 按售价计算 |
| 交易手续费 | 2.5% | 按售价计算 |
| 预售服务费 | 3% | 按售价计算 |
| **平台总费率** | **19.5%** | |
| 货代费 | ¥3/单 | 固定 |
| SLS运费 | 见下表 | 按重量计算 |

### SLS运费（台湾）

| 重量段 | 费用(TWD) |
|--------|------------|
| 首重500g | 70 |
| 续重每500g | 30 |

### 买家实付运费

| 条件 | 运费(TWD) |
|------|-----------|
| 普通订单(<299) | 55 |
| 满299 | 30 |
| 满490 | 0 |

## 计算公式

```python
def calculate_sls_shipping(weight_g):
    """计算SLS运费"""
    if weight_g <= 500:
        return 70.0
    extra = math.ceil((weight_g - 500) / 500)
    return 70.0 + extra * 30.0

def calculate_platform_fee(price_twd):
    """计算平台费"""
    return price_twd * (COMMISSION_RATE + TRANSACTION_FEE_RATE + PRE_SALE_SERVICE_RATE)

def calculate_total_cost(purchase_cny, weight_g, exchange_rate=4.5):
    """计算总成本"""
    sls_shipping = calculate_sls_shipping(weight_g)
    agent_fee_cny = AGENT_FEE_CNY
    cost_cny = purchase_cny + agent_fee_cny
    cost_twd = cost_cny * exchange_rate + sls_shipping
    return cost_twd

def calculate_suggested_price(cost_twd, target_profit_rate=0.20):
    """反推建议售价"""
    # total_cost = price * (1 - platform_rate) - shipping
    # price = (total_cost + shipping) / (1 - platform_rate)
    platform_rate = COMMISSION_RATE + TRANSACTION_FEE_RATE + PRE_SALE_SERVICE_RATE
    return cost_twd / (1 - platform_rate - target_profit_rate)
```

## 示例计算

```
采购价: ¥25
重量: 627g
汇率: 4.5

SLS运费 = 70 + ceil((627-500)/500) × 30 = 70 + 30 = 100 TWD
总成本 = 25 × 4.5 + 3 × 4.5 + 100 = 112.5 + 13.5 + 100 = 226 TWD
建议售价 = 226 / (1 - 0.195 - 0.20) = 226 / 0.605 ≈ 374 TWD
```
