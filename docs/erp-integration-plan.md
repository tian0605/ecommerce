# 妙手ERP + OpenClaw 集成方案

## 一、系统架构

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   妙手ERP       │────▶│  OpenClaw    │────▶│  飞书/数据库    │
│  (数据源)       │     │  (自动化)    │     │  (存储/通知)    │
└─────────────────┘     └──────────────┘     └─────────────────┘
       │                        │
       ▼                        ▼
┌─────────────────┐     ┌──────────────┐
│  虾皮店铺       │     │  数据分析    │
│  (商品/订单)    │     │  (报表/预警) │
└─────────────────┘     └──────────────┘
```

## 二、数据流设计

### 2.1 妙手ERP → OpenClaw 数据类型

| 数据类型 | 频率 | 用途 |
|----------|------|------|
| 商品信息 | 实时/每日 | 库存监控、价格调整 |
| 订单数据 | 实时 | 销售分析、异常检测 |
| 采购信息 | 每日 | 成本计算、利润分析 |
| 库存预警 | 实时 | 自动补货提醒 |

### 2.2 OpenClaw → 自动化动作

| 触发条件 | 自动动作 |
|----------|----------|
| 库存低于阈值 | 飞书推送补货建议 |
| 价格低于成本价 | 预警通知 |
| 订单异常 | 标记处理 |
| 每日数据汇总 | 生成运营日报 |

## 三、技术实现

### 3.1 妙手ERP API 对接（需确认）

```python
# 预期API接口（需验证）
# 基础URL: https://api.miaoshouerp.com/v1

# 商品列表接口
GET /products?shop_id={shop_id}&page=1&page_size=50

# 订单列表接口  
GET /orders?shop_id={shop_id}&start_date={}&end_date={}

# 库存查询
GET /inventory?product_id={}

# 价格修改
POST /products/{id}/price
{"price": 99.00}
```

### 3.2 OpenClaw 自动化流程

```yaml
# 自动化任务配置
daily_tasks:
  - name: "商品数据同步"
    schedule: "0 9 * * *"  # 每日9点
    action: sync_products
    
  - name: "订单数据分析"
    schedule: "0 10 * * *"
    action: analyze_orders
    
  - name: "库存预警检查"
    schedule: "0 */4 * * *"  # 每4小时
    action: check_inventory

realtime_tasks:
  - name: "价格异常监控"
    trigger: price_change
    action: alert_if_needed
```

### 3.3 数据存储设计

```sql
-- 商品表
CREATE TABLE products (
    id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(255),
    sku VARCHAR(64),
    price DECIMAL(10,2),
    stock INT,
    category VARCHAR(64),
    source VARCHAR(32),  -- '妙手ERP'
    created_at DATETIME,
    updated_at DATETIME
);

-- 订单表
CREATE TABLE orders (
    order_id VARCHAR(64) PRIMARY KEY,
    product_id VARCHAR(32),
    quantity INT,
    amount DECIMAL(10,2),
    profit DECIMAL(10,2),
    status VARCHAR(16),
    created_at DATETIME
);

-- 价格历史
CREATE TABLE price_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id VARCHAR(32),
    price DECIMAL(10,2),
    recorded_at DATETIME
);
```

## 四、实施步骤

### 第一阶段：基础对接（Week 1）
- [ ] 获取妙手ERP API密钥
- [ ] 确认API接口文档
- [ ] 搭建本地数据存储（MySQL/CSV）

### 第二阶段：数据同步（Week 2）
- [ ] 开发商品数据同步脚本
- [ ] 开发订单数据同步脚本
- [ ] 配置定时任务

### 第三阶段：自动化（Week 3）
- [ ] 库存预警通知
- [ ] 运营日报自动生成
- [ ] 飞书/微信推送集成

### 第四阶段：智能分析（Week 4）
- [ ] 利润分析
- [ ] 选品建议
- [ ] 策略优化

## 五、所需工具

| 工具 | 用途 | 状态 |
|------|------|------|
| 妙手ERP | 店铺管理 | 待配置 |
| MySQL/PostgreSQL | 数据存储 | 待搭建 |
| OpenClaw | 自动化引擎 | ✅ 已就绪 |
| 飞书 | 消息通知 | 待集成 |

## 六、风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| API调用限制 | 数据同步中断 | 本地缓存+重试机制 |
| 数据格式变化 | 解析失败 | 版本校验+日志告警 |
| 网络不稳定 | 同步失败 | 断点续传 |

---

**下一步行动：**
1. 用户需提供妙手ERP的API密钥
2. 确认妙手ERP开放API接口文档
3. 搭建本地数据库环境
