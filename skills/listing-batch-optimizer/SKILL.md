---
name: listing-batch-optimizer
description: 商品标题和描述批量优化技能。用于：(1)定期扫描数据库中需要优化/重新优化的商品 (2)检查标题和描述的一致性问题 (3)批量生成或修复优化listing (4)读取 Shopee 批量更新 Excel 模板并回写优化结果 (5)支持定时自动执行。触发条件：用户提到"批量优化"、"定期优化"、"一致性检查"、"修复描述"、"优化所有商品"、"Excel批量优化"、"批量模板优化"。
---

# Listing Batch Optimizer - 批量标题描述优化

## 核心功能

1. **一致性校验**：检查标题关键词是否在描述前300字出现
2. **批量优化**：对多个商品重新生成一致的标题和描述
3. **Excel模板优化**：读取 Shopee 批量更新模板，从第7行起回写标题/描述/失败原因
4. **定时任务**：支持cron定期执行
5. **关键词头部补强**：若描述前200字缺少标题关键词，脚本会在描述最前面自动补一行摘要，再做最终校验

## 工作流程

数据库模式：

```
[扫描数据库] → [一致性检查] → [标记问题商品] → [批量优化] → [更新数据库]
```

Excel模板模式：

```
[读取xlsx模板] → [识别列头] → [逐行生成标题/描述] → [描述头部关键词补强] → [写回失败原因] → [输出新xlsx]
```

## 使用方法

### 1. 一致性检查（不优化，只检查）

```python
from scripts.listing_consistency_checker import ConsistencyChecker

checker = ConsistencyChecker()
issues = checker.check_all_products()
# 返回所有不一致的商品列表
```

### 2. 批量优化单个商品

```python
from scripts.listing_batch_optimizer import ListingBatchOptimizer

optimizer = ListingBatchOptimizer()
result = optimizer.optimize_one('AL0001001260000018')
print(result)
```

### 3. 批量优化多个商品

```python
optimizer = ListingBatchOptimizer()
# 优化所有有问题的商品
result = optimizer.optimize_batch(limit=10)
```

### 4. 强制重新优化（不管是否一致）

```python
result = optimizer.optimize_batch(force=True, limit=20)
```

### 5. 优化 Shopee 批量更新 Excel 模板

```python
optimizer = ListingBatchOptimizer()
result = optimizer.optimize_excel_template(
		input_path='/root/Documents/mass_update_global_sku_basic_info.xlsx',
		output_path='/root/Documents/mass_update_global_sku_basic_info.optimized.xlsx',
		start_row=7,
		limit=10,
)
print(result)
```

CLI 示例：

```bash
python skills/listing-batch-optimizer/scripts/listing_batch_optimizer.py \
	--input-xlsx /root/Documents/mass_update_global_sku_basic_info.xlsx \
	--output-xlsx /root/Documents/mass_update_global_sku_basic_info.optimized.xlsx \
	--limit 10
```

关键词头部补强回归检查：

```bash
python skills/listing-batch-optimizer/scripts/regression_check_keyword_head.py \
	--input-xlsx /root/Documents/mass_update_global_sku_basic_info.xlsx \
	--rows 7,11 \
	--repeats 3
```

默认检查第 7 行和第 11 行：

1. 第 7 行覆盖长关键词场景
2. 第 11 行覆盖历史上最容易触发“前200字缺词”失败的场景

## 一致性检查规则

详见 [references/consistency_rules.md](references/consistency_rules.md)

当前脚本内的关键校验点：

1. 标题不能为空，长度需在 10-60 字之间
2. 描述长度至少 300 字
3. 描述前 200 字必须覆盖标题提取出的前 4 个关键词
4. 如模型生成的描述前段缺词，脚本会先执行“关键词头部补强”，再进入最终校验

“关键词头部补强”说明：

1. 先从标题提取最多 4 个关键词
2. 检查描述前 200 字是否已覆盖这些关键词
3. 若存在缺失关键词，则在描述最前面插入一行 `【重點整理】...` 摘要，强制补齐缺失词
4. 补强只用于提高描述与标题的一致性，不会绕过长度、禁用词等其他校验

## 提示词模板

详见 [references/prompt_templates.md](references/prompt_templates.md)

## 配置

- 数据库：PostgreSQL `ecommerce_data` 表 `products`
- LLM：当前按 `doubao-seed-2-0-pro-260215` 执行
- 每次批量限制：默认10条（避免API超时）
- Excel模板：自动识别第1行/第3行表头；默认从第7行开始处理

## 前置条件

1. 数据库连接正常
2. LLM API 可用（余额充足）
3. SSH 隧道已建立（如需调用本地服务）
4. 若 Shopee 模板带有非法 worksheet pane XML，脚本会自动修复后再读取
