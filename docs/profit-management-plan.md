# 成本利润管理首版执行方案

## 目标

首版将成本利润管理拆成两个独立页面：

1. 利润明细
2. 飞书同步管理

并新增本地利润明细初始化任务，范围限定为本地 `products` 表中的全部有效商品。

## 范围确认

1. 旧路由 `/profit-analysis` 直接跳转到新“利润明细”页。
2. 利润明细页支持按商品编码、商品名称、1688 商品 ID、SKU 名称统一关键词搜索。
3. 利润明细页支持按站点、利润率区间筛选与分页。
4. 飞书同步管理不再和利润明细同页展示。
5. 初始化默认只写本地 `product_analysis`，不自动推飞书。

## 交付拆分

### 第一批

1. 菜单与路由拆分
2. 利润明细页独立
3. 飞书同步管理页独立

### 第二批

1. 初始化任务接口
2. 初始化执行脚本
3. 初始化任务历史与日志

### 第三批

1. 明细页全量可见模型优化
2. 更多筛选条件
3. 详情抽屉与差异提示

## 后端主链

1. `GET /profit-analysis/summary`
2. `GET /profit-analysis/items`
3. `GET /profit-analysis/init/candidates/summary`
4. `POST /profit-analysis/init`
5. `GET /profit-analysis/init/recent`
6. `POST /profit-analysis/sync`
7. `GET /profit-analysis/sync/recent`

## 任务前缀

1. `PROFIT-SYNC-`：飞书同步任务
2. `INIT-PROFIT-`：本地利润初始化任务

## 数据归属

1. 本地 `product_analysis` 是利润明细页唯一主数据源。
2. 飞书只作为同步目标，不替代本地数据。

## 风险控制

1. 初始化任务默认 `skip_feishu=true`，避免把全量商品误同步到飞书。
2. 初始化按批次执行，避免长任务一次性压满资源。
3. 首版利润明细列表默认展示已初始化数据，未初始化数量通过候选统计与初始化任务面板呈现。