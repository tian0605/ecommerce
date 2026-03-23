# ecommerce_data 数据库结构导出

## 导出时间
2026-03-23 17:48 GMT+8

---

## 表清单（共19张）

| 序号 | 表名 | 说明 |
|------|------|------|
| 1 | products | 商品主表 |
| 2 | product_skus | SKU详情表 |
| 3 | product_analysis | 商品利润分析表 |
| 4 | product_mapping | 商品映射表 |
| 5 | product_alerts | 商品预警表 |
| 6 | logistics_templates | 物流模板表 |
| 7 | exchange_rates | 汇率表 |
| 8 | sources | 数据源表 |
| 9 | industry_data | 行业数据表 |
| 10 | hot_search_words | 热门搜索词表 |
| 11 | platform_rules | 平台规则表 |
| 12 | bulk_pricing_tasks | 批量定价任务表 |
| 13 | analysis_job_logs | 分析任务日志表 |
| 14 | fee_config_history | 费率配置历史表 |
| 15 | pricing_history | 定价历史表 |
| 16 | shopee_rank_import | Shopee排名导入表 |
| 17 | profit_analysis_summary | 利润分析汇总表 |
| 18 | memory | 记忆表 |
| 19 | bulk_pricing_tasks | 批量定价任务 |

---

## 1. products（商品主表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| product_id | varchar(64) | UNIQUE | 主货号 |
| alibaba_product_id | varchar(64) | INDEX | 1688货源ID |
| title | text | | 商品标题 |
| description | text | | 商品描述 |
| category | varchar(255) | | 类目 |
| brand | varchar(128) | | 品牌 |
| origin | varchar(128) | | 产地 |
| main_images | jsonb | | 主图列表 |
| sku_images | jsonb | | SKU图片列表 |
| skus | jsonb | | SKU规格列表 |
| logistics | jsonb | | 物流信息 |
| source_url | text | | 来源URL |
| status | varchar(32) | DEFAULT 'pending' | 状态 |
| created_at | timestamp | | 创建时间 |
| updated_at | timestamp | | 更新时间 |

### 索引
- PRIMARY KEY (id)
- UNIQUE CONSTRAINT (product_id)
- INDEX (alibaba_product_id)
- INDEX (status)

### 示例数据
```
id | product_id | alibaba_product_id | title | status
1  | 测试999999  | 999999999999       | 测试商品 | pending
2  | 日式078815  | 1027205078815      | 【日式復古風】... | published
3  | 日000001    | 1026137274944      | 脏衣服收纳袋... | pending
```

---

## 2. product_skus（SKU详情表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| product_id | integer | | 商品ID |
| sku_name | varchar(200) | | SKU名称 |
| color | varchar(100) | | 颜色 |
| size | varchar(50) | | 尺寸 |
| price | numeric(10,2) | | 价格 |
| stock | integer | | 库存 |
| package_length | numeric(10,2) | | 包装长度(cm) |
| package_width | numeric(10,2) | | 包装宽度(cm) |
| package_height | numeric(10,2) | | 包装高度(cm) |
| package_weight | numeric(10,2) | | 包装重量(kg) |
| image_url | text | | 图片URL |
| volume_weight | numeric(10,2) | | 体积重量 |
| currency | varchar(10) | DEFAULT 'CNY' | 货币 |
| is_domestic_shipping | boolean | DEFAULT true | 国内包邮 |
| requires_special_packaging | boolean | DEFAULT false | 特殊包装 |
| shipping_type_preference | varchar(20) | | 物流偏好 |
| is_deleted | smallint | NOT NULL, DEFAULT 0 | 已删除标记 |
| sku_code | varchar(50) | | SKU编码 |
| sku_stock | integer | | SKU库存 |
| shopee_sku_name | varchar(120) | | Shopee SKU名称 |
| color_code | varchar(2) | | 颜色代码 |
| attribute_code | varchar(2) | | 属性代码 |
| created_at | timestamp | DEFAULT now() | 创建时间 |

### 索引
- PRIMARY KEY (id)

### 外键
- product_analysis.sku_id -> product_skus.id

---

## 3. product_analysis（商品利润分析表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| product_id | integer | | 商品ID |
| sku_id | integer | FK | SKU ID |
| platform | varchar(50) | | 平台 |
| site | varchar(50) | | 站点 |
| currency | varchar(10) | DEFAULT 'TWD' | 货币 |
| purchase_price_cny | numeric(10,2) | | 采购价(CNY) |
| weight_kg | numeric(10,4) | | 重量(kg) |
| shipping_cn | numeric(10,2) | | 国内运费 |
| agent_fee_cny | numeric(10,2) | | 货代费 |
| sls_fee_cny | numeric(10,2) | | SLS运费(CNY) |
| sls_fee_twd | numeric(10,2) | | SLS运费(TWD) |
| shipping_ratio | numeric(5,4) | | 运费比例 |
| commission_cny | numeric(10,2) | | 佣金(CNY) |
| commission_twd | numeric(10,2) | | 佣金(TWD) |
| service_fee_cny | numeric(10,2) | | 服务费(CNY) |
| service_fee_twd | numeric(10,2) | | 服务费(TWD) |
| transaction_fee_cny | numeric(10,2) | | 交易费(CNY) |
| transaction_fee_twd | numeric(10,2) | | 交易费(TWD) |
| total_cost_cny | numeric(10,2) | | 总成本(CNY) |
| total_cost_twd | numeric(10,2) | | 总成本(TWD) |
| exchange_rate | numeric(10,4) | | 汇率 |
| suggested_price_twd | numeric(10,2) | | 建议售价(TWD) |
| suggested_price_cny | numeric(10,2) | | 建议售价(CNY) |
| estimated_profit_cny | numeric(10,2) | | 预估利润(CNY) |
| profit_rate | numeric(10,4) | | 利润率 |
| analysis_date | date | NOT NULL | 分析日期 |
| remarks | text | | 备注 |
| created_at | timestamp | DEFAULT now() | 创建时间 |
| is_deleted | smallint | NOT NULL, DEFAULT 0 | 已删除标记 |
| new_store_price_twd | numeric | | 新商店价(TWD) |
| new_store_price_cny | numeric | | 新商店价(CNY) |
| updated_at | timestamp | DEFAULT now() | 更新时间 |
| new_store_price | numeric | | 新商店价 |

### 索引
- PRIMARY KEY (id)
- UNIQUE CONSTRAINT (product_id, sku_id, platform, site, is_deleted)

### 外键
- sku_id -> product_skus.id (ON DELETE SET NULL)

---

## 4. product_mapping（商品映射表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| db_product_id | integer | | 数据库商品ID |
| shopee_product_id | varchar(50) | | Shopee商品ID |
| shopee_parent_sku | varchar(50) | | Shopee父SKU |
| master_sku | varchar(20) | | 主SKU |
| created_at | timestamp | DEFAULT now() | 创建时间 |

### 索引
- PRIMARY KEY (id)

---

## 5. product_alerts（商品预警表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| product_id | integer | NOT NULL | 商品ID |
| sku_id | integer | | SKU ID |
| alert_type | varchar(50) | NOT NULL | 预警类型 |
| severity | varchar(20) | NOT NULL | 严重程度 |
| alert_message | text | NOT NULL | 预警消息 |
| current_value | numeric | | 当前值 |
| threshold_value | numeric | | 阈值 |
| difference_value | numeric | | 差值 |
| status | varchar(20) | DEFAULT 'active' | 状态 |
| resolved_at | timestamp | | 解决时间 |
| resolved_by | varchar(100) | | 解决人 |
| resolution_notes | text | | 解决备注 |
| analysis_id | integer | | 分析ID |
| analysis_date | date | NOT NULL | 分析日期 |
| platform | varchar(20) | | 平台 |
| site | varchar(20) | | 站点 |
| created_at | timestamp | DEFAULT now() | 创建时间 |
| is_deleted | smallint | NOT NULL, DEFAULT 0 | 已删除标记 |

### 索引
- PRIMARY KEY (id)
- INDEX (analysis_date)
- INDEX (product_id, status)
- INDEX (status, severity)

---

## 6. logistics_templates（物流模板表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| platform | varchar(20) | NOT NULL | 平台 |
| site | varchar(20) | NOT NULL | 站点 |
| template_name | varchar(100) | NOT NULL | 模板名称 |
| template_type | varchar(20) | NOT NULL | 模板类型 |
| first_weight_unit | numeric | NOT NULL | 首重单位(g) |
| first_weight_price | numeric | NOT NULL | 首重价格 |
| continue_weight_unit | numeric | NOT NULL | 续重单位(g) |
| continue_weight_price | numeric | NOT NULL | 续重价格 |
| base_shipping_fee | numeric | | 基础运费 |
| max_weight | numeric | | 最大重量 |
| is_active | boolean | DEFAULT true | 是否启用 |
| effective_date | date | DEFAULT CURRENT_DATE | 生效日期 |
| expiry_date | date | | 失效日期 |
| created_at | timestamp | DEFAULT now() | 创建时间 |
| updated_at | timestamp | DEFAULT now() | 更新时间 |
| is_deleted | smallint | NOT NULL, DEFAULT 0 | 已删除标记 |

### 索引
- PRIMARY KEY (id)
- INDEX (platform, site, is_active)

### 示例数据
```
platform | site | template_name | first_weight_price | continue_weight_price
Shopee   | TW   | 7-11 Store Shipping | 15.0 | 30.0
Shopee   | TW   | FamilyMart Store Shipping | 15.0 | 30.0
Shopee   | TW   | Hi-Life Store Shipping | 60.0 | 30.0
```

---

## 7. exchange_rates（汇率表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| from_currency | varchar(10) | | 源货币 |
| to_currency | varchar(10) | | 目标货币 |
| rate | numeric(10,4) | | 汇率 |
| effective_date | date | | 生效日期 |
| created_at | timestamp | DEFAULT now() | 创建时间 |
| is_deleted | smallint | NOT NULL, DEFAULT 0 | 已删除标记 |

### 索引
- PRIMARY KEY (id)

---

## 8. sources（数据源表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| platform | varchar(50) | NOT NULL | 平台 |
| site | varchar(10) | NOT NULL | 站点 |
| category | varchar(100) | NOT NULL | 类目 |
| time_range | varchar(20) | | 时间范围 |
| description | text | | 描述 |
| created_at | timestamp | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| is_deleted | smallint | NOT NULL, DEFAULT 0 | 已删除标记 |

### 索引
- PRIMARY KEY (id)
- UNIQUE CONSTRAINT (platform, site, category, time_range)

---

## 9. industry_data（行业数据表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| source_id | integer | FK | 数据源ID |
| data_date | date | NOT NULL | 数据日期 |
| industry | varchar(200) | NOT NULL | 行业 |
| product_count | integer | | 商品数量 |
| sold_product_count | integer | | 销售商品数 |
| sales_rate | varchar(20) | | 销售率 |
| sales_volume | integer | | 销量 |
| sales_amount | bigint | | 销售额 |
| product_increase_30d | integer | | 30天商品增长 |
| shop_increase_30d | integer | | 30天店铺增长 |
| created_at | timestamp | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| is_deleted | smallint | NOT NULL, DEFAULT 0 | 已删除标记 |

### 索引
- PRIMARY KEY (id)
- INDEX (data_date)
- INDEX (industry)
- INDEX (source_id)

### 外键
- source_id -> sources.id

---

## 10. hot_search_words（热门搜索词表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| keyword | varchar(255) | NOT NULL | 关键词 |
| product_count | integer | | 商品数量 |
| category | varchar(100) | | 类目 |
| source_file | varchar(255) | | 来源文件 |
| created_at | timestamp | DEFAULT now() | 创建时间 |

### 索引
- PRIMARY KEY (id)

---

## 11. platform_rules（平台规则表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| platform | varchar(50) | | 平台 |
| site | varchar(50) | | 站点 |
| commission_rate | numeric(5,4) | | 佣金率 |
| service_rate | numeric(5,4) | | 服务费率 |
| transaction_fee | numeric(5,4) | | 交易费率 |
| payment_fee | numeric(5,4) | | 支付费率 |
| logistics_cost_base | numeric(10,2) | | 物流成本基础 |
| logistics_cost_per_kg | numeric(10,2) | | 物流成本/kg |
| first_kg_cost | numeric(10,2) | | 首重成本 |
| continue_kg_cost | numeric(10,2) | | 续重成本 |
| target_profit_rate | numeric(5,4) | | 目标利润率 |
| remarks | text | | 备注 |
| is_active | boolean | DEFAULT true | 是否启用 |
| created_at | timestamp | DEFAULT now() | 创建时间 |
| updated_at | timestamp | DEFAULT now() | 更新时间 |
| currency | varchar(10) | DEFAULT 'TWD' | 货币 |
| agent_fee_cny | numeric | DEFAULT 3.00 | 货代费(CNY) |
| first_weight_unit | numeric | DEFAULT 500 | 首重单位 |
| first_weight_twd | numeric | DEFAULT 15.00 | 首重价格(TWD) |
| continue_weight_unit | numeric | DEFAULT 500 | 续重单位 |
| continue_weight_twd | numeric | DEFAULT 30.00 | 续重价格(TWD) |
| store_shipping_twd | numeric | DEFAULT 50.00 | 店配运费(TWD) |
| home_delivery_twd | numeric | DEFAULT 70.00 | 宅配运费(TWD) |
| pre_sale_service_rate | numeric | DEFAULT 0.03 | 预售服务费率 |
| commission_rate_taiwan | numeric | DEFAULT 0.14 | 台湾佣金率 |
| transaction_fee_rate_taiwan | numeric | DEFAULT 0.025 | 台湾交易费率 |
| is_deleted | smallint | NOT NULL, DEFAULT 0 | 已删除标记 |

### 索引
- PRIMARY KEY (id)

---

## 12. bulk_pricing_tasks（批量定价任务表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| task_name | varchar(200) | NOT NULL | 任务名称 |
| platform | varchar(20) | NOT NULL | 平台 |
| site | varchar(20) | NOT NULL | 站点 |
| pricing_strategy | varchar(50) | NOT NULL | 定价策略 |
| target_profit_rate | numeric | | 目标利润率 |
| price_adjustment_percent | numeric | | 价格调整百分比 |
| include_product_ids | integer[] | | 包含商品ID列表 |
| exclude_product_ids | integer[] | | 排除商品ID列表 |
| category_filter | varchar(100) | | 类目过滤 |
| status | varchar(20) | DEFAULT 'pending' | 状态 |
| start_time | timestamp | | 开始时间 |
| end_time | timestamp | | 结束时间 |
| total_products | integer | DEFAULT 0 | 总商品数 |
| processed_products | integer | DEFAULT 0 | 已处理数 |
| successful_updates | integer | DEFAULT 0 | 成功更新数 |
| failed_updates | integer | DEFAULT 0 | 失败更新数 |
| task_parameters | jsonb | | 任务参数 |
| created_by | varchar(100) | NOT NULL | 创建人 |
| created_at | timestamp | DEFAULT now() | 创建时间 |
| updated_at | timestamp | DEFAULT now() | 更新时间 |
| is_deleted | smallint | NOT NULL, DEFAULT 0 | 已删除标记 |

### 索引
- PRIMARY KEY (id)
- INDEX (platform, site)
- INDEX (status)

---

## 13. analysis_job_logs（分析任务日志表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| job_type | varchar(50) | NOT NULL | 任务类型 |
| platform | varchar(20) | | 平台 |
| site | varchar(20) | | 站点 |
| start_time | timestamp | NOT NULL | 开始时间 |
| end_time | timestamp | | 结束时间 |
| status | varchar(20) | NOT NULL | 状态 |
| total_products | integer | DEFAULT 0 | 总商品数 |
| successful_analyses | integer | DEFAULT 0 | 成功分析数 |
| failed_analyses | integer | DEFAULT 0 | 失败分析数 |
| error_message | text | | 错误消息 |
| parameters | jsonb | | 参数 |
| created_at | timestamp | DEFAULT now() | 创建时间 |
| is_deleted | smallint | NOT NULL, DEFAULT 0 | 已删除标记 |

### 索引
- PRIMARY KEY (id)
- INDEX (status)
- INDEX (job_type, start_time)

---

## 14. fee_config_history（费率配置历史表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| config_type | varchar(50) | NOT NULL | 配置类型 |
| platform | varchar(20) | NOT NULL | 平台 |
| site | varchar(20) | NOT NULL | 站点 |
| old_rate_value | numeric | | 旧费率值 |
| old_config_json | jsonb | | 旧配置JSON |
| new_rate_value | numeric | | 新费率值 |
| new_config_json | jsonb | | 新配置JSON |
| change_reason | text | | 变更原因 |
| changed_by | varchar(100) | | 变更人 |
| effective_date | date | NOT NULL | 生效日期 |
| created_at | timestamp | DEFAULT now() | 创建时间 |
| is_deleted | smallint | NOT NULL, DEFAULT 0 | 已删除标记 |

### 索引
- PRIMARY KEY (id)
- INDEX (config_type, effective_date)

---

## 15. pricing_history（定价历史表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| product_id | integer | NOT NULL | 商品ID |
| sku_id | integer | | SKU ID |
| platform | varchar(20) | NOT NULL | 平台 |
| site | varchar(20) | NOT NULL | 站点 |
| currency | varchar(10) | NOT NULL | 货币 |
| purchase_price_cny | numeric | | 采购价(CNY) |
| agent_fee_cny | numeric | | 货代费(CNY) |
| domestic_shipping_cny | numeric | | 国内运费(CNY) |
| sls_shipping_cny | numeric | | SLS运费(CNY) |
| sls_shipping_twd | numeric | | SLS运费(TWD) |
| commission_cny | numeric | | 佣金(CNY) |
| commission_twd | numeric | | 佣金(TWD) |
| transaction_fee_cny | numeric | | 交易费(CNY) |
| transaction_fee_twd | numeric | | 交易费(TWD) |
| service_fee_cny | numeric | | 服务费(CNY) |
| service_fee_twd | numeric | | 服务费(TWD) |
| exchange_rate | numeric | | 汇率 |
| suggested_price_twd | numeric | | 建议售价(TWD) |
| suggested_price_cny | numeric | | 建议售价(CNY) |
| actual_selling_price | numeric | | 实际售价 |
| estimated_profit_cny | numeric | | 预估利润(CNY) |
| profit_rate | numeric | | 利润率 |
| total_cost_cny | numeric | | 总成本(CNY) |
| total_cost_twd | numeric | | 总成本(TWD) |
| weight_kg | numeric | | 重量(kg) |
| shipping_type | varchar(20) | | 物流类型 |
| analysis_date | date | NOT NULL | 分析日期 |
| pricing_strategy | varchar(50) | | 定价策略 |
| remarks | text | | 备注 |
| created_at | timestamp | DEFAULT now() | 创建时间 |
| is_deleted | smallint | NOT NULL, DEFAULT 0 | 已删除标记 |

### 索引
- PRIMARY KEY (id)
- INDEX (analysis_date)
- INDEX (product_id, analysis_date)
- INDEX (platform, site)

---

## 16. shopee_rank_import（Shopee排名导入表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| file_id | varchar(10) | | 文件ID |
| rank | integer | | 排名 |
| shop_name | varchar(500) | | 店铺名称 |
| product_id | varchar(100) | | 商品ID |
| sales_volume | integer | | 销量 |
| sales_ratio | varchar(20) | | 销售比例 |
| revenue | bigint | | 收入 |
| revenue_30d | bigint | | 30天收入 |
| product_count_30d | integer | | 30天商品数 |
| active_product_count | integer | | 活跃商品数 |
| import_date | timestamp | DEFAULT now() | 导入日期 |

### 索引
- PRIMARY KEY (id)

---

## 17. profit_analysis_summary（利润分析汇总表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| platform | varchar(20) | NOT NULL | 平台 |
| site | varchar(20) | NOT NULL | 站点 |
| analysis_date | date | NOT NULL | 分析日期 |
| total_products_analyzed | integer | DEFAULT 0 | 分析商品数 |
| total_skus_analyzed | integer | DEFAULT 0 | 分析SKU数 |
| avg_purchase_price_cny | numeric | | 平均采购价(CNY) |
| avg_total_cost_cny | numeric | | 平均总成本(CNY) |
| avg_sls_shipping_cny | numeric | | 平均SLS运费(CNY) |
| avg_agent_fee_cny | numeric | | 平均货代费(CNY) |
| avg_commission_twd | numeric | | 平均佣金(TWD) |
| avg_transaction_fee_twd | numeric | | 平均交易费(TWD) |
| avg_service_fee_twd | numeric | | 平均服务费(TWD) |
| avg_suggested_price_twd | numeric | | 平均建议售价(TWD) |
| avg_estimated_profit_cny | numeric | | 平均预估利润(CNY) |
| avg_profit_rate | numeric | | 平均利润率 |
| high_profit_products | integer | DEFAULT 0 | 高利润商品数 |
| medium_profit_products | integer | DEFAULT 0 | 中利润商品数 |
| low_profit_products | integer | DEFAULT 0 | 低利润商品数 |
| loss_products | integer | DEFAULT 0 | 亏损商品数 |
| exchange_rate_used | numeric | | 使用汇率 |
| analysis_period | varchar(20) | | 分析周期 |
| remarks | text | | 备注 |
| created_at | timestamp | DEFAULT now() | 创建时间 |
| is_deleted | smallint | NOT NULL, DEFAULT 0 | 已删除标记 |

### 索引
- PRIMARY KEY (id)
- INDEX (analysis_date)
- INDEX (platform, site)
- UNIQUE CONSTRAINT (platform, site, analysis_date)

---

## 18. memory（记忆表）

### 字段定义
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | integer | PK, NOT NULL | 主键 |
| user_id | varchar(255) | | 用户ID |
| session_key | varchar(255) | | 会话Key |
| role | varchar(50) | | 角色 |
| content | text | | 内容 |
| keywords | text | | 关键词 |
| created_at | timestamp | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| is_deleted | smallint | NOT NULL, DEFAULT 0 | 已删除标记 |

### 索引
- PRIMARY KEY (id)
- INDEX (created_at DESC)
- INDEX (user_id)

---

## 表关系图

```
products (1) ──────< product_skus (N)
    │                    │
    │                    │
    └────< product_analysis (N)
                     │
                     │
              product_mapping (N)
              
product_alerts (N) ──> product_analysis (1)
platform_rules (1) ────> 各个分析表 (N)
logistics_templates (1) ──> 各个分析表 (N)
```

---

## 关键约束说明

### 软删除
所有表都有 `is_deleted` 字段（smallint, DEFAULT 0），用于软删除。

### 时间戳
- `created_at`: 创建时间
- `updated_at`: 更新时间（部分表）

### 状态字段
- `products.status`: pending（待优化）/ optimized（已优化）/ published（已发布）
- `bulk_pricing_tasks.status`: pending（待执行）/ running（执行中）/ completed（已完成）/ failed（失败）
- `product_alerts.status`: active（活跃）/ resolved（已解决）

---

## 备注

此文档由系统自动生成，导出了 ecommerce_data 数据库的完整结构。
如需修改请联系开发者。
