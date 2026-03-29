---
name: listing-optimizer
description: 商品Listing优化模块。使用LLM（DeepSeek）优化商品标题和描述，生成符合Shopee台湾市场的Listing。触发条件：(1)已落库商品需要优化 (2)执行TC-LO-001测试 (3)miaoshou-updater前需要优化内容
---

# listing-optimizer

商品Listing优化模块。调用DeepSeekLLM，将商品标题和描述优化为符合Shopee台湾市场的Listing。

## 核心文件

- **模块路径**: `/home/ubuntu/.openclaw/skills/listing-optimizer/optimizer.py`

## LLM配置

**配置文件**: `config/llm_config.py`

### 可用模型

| 模型 | 成本 | 速度 | 用途 |
|------|------|------|------|
| **deepseek-chat**（默认） | ¥0.001/1K | 快速 | 主力推荐 |
| deepseek-coder | ¥0.001/1K | 快速 | 代码生成 |

### 配置内容

```python
from config.llm_config import DEFAULT_MODEL, MODELS
# DEFAULT_MODEL = 'deepseek-chat'
```

**注意**: API Key和Base URL也配置在 `config/llm_config.py`

## 目标市场

- **平台**: Shopee台湾
- **语言**: 繁体中文
- **字符集**: UTF-8

## 优化内容

### 标题优化
- 符合Shopee搜索SEO
- 关键词精准
- 长度 < 120 字符

### 描述优化
- 结构化展示（特点/规格/用途等）
- 符合台湾消费者习惯
- 去除违禁词
- 适当使用emoji增加可读性

## 使用方法

```python
from listing_optimizer import ListingOptimizer

optimizer = ListingOptimizer()
result = optimizer.optimize(product_id=1)
print(result['optimized_title'])
print(result['optimized_description'])
```

## 返回数据结构

```python
{
    'status': 'success',
    'optimized_title': '日式復古風竹編收納筐 大容量客廳書架整理箱...',
    'optimized_description': '✨ 商品特點\n1. 天然竹材...\n\n📐 規格尺寸\n...',
    'model_used': 'deepseek-chat'
}
```

## 提示词模板

提示词已配置化为独立文件，位于 `config/prompts/` 目录：

| 文件 | 版本 | 用途 |
|------|------|------|
| `title_prompt_v3.md` | v3.0 | 商品标题生成 |
| `desc_prompt_v3.md` | v3.0 | 商品描述生成 |

### 标题优化模板特点
- 结构化公式：热搜词→核心品类→卖点→属性→促销
- 40-55字符最佳区间
- 台湾繁体中文本地化
- 违禁词过滤（夸大、绝对化用语）
- 成功案例参考

### 描述优化模板特点
- 七段式结构：标题句→痛点→优势→材质→场景→购买理由→温馨提示
- 1500-2800字符
- 台湾本地化表达
- emoji增强可读性

### 模板配置
```python
from optimizer import ListingOptimizer
# 自动从 config/prompts/ 加载模板
optimizer = ListingOptimizer()
```

## 前置条件

1. product-storer 已完成落库
2. LLM API可用（余额充足）

## 数据依赖

- **输入**: products表记录（status='pending'）
- **输出**: 优化后的标题和描述（更新到products表，status='optimized'）
- **后续模块**: miaoshou-updater 回写

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| LLM API超时 | 增加timeout参数或重试 |
| 返回乱码 | 检查UTF-8编码 |
| 优化效果差 | 调整提示词，降低temperature |
| API余额不足 | 联系DeepSeek API充值 |

## 费用参考

- **deepseek-chat**: ~¥0.001/1K tokens（**推荐**，已设为默认）
- deepseek-chat: ~¥0.004/1K tokens
- deepseek-chat: ~¥0.001/1K tokens
 tokens
- deepseek-chat: ~¥0.001/1K tokens
