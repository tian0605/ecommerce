---
name: listing-optimizer
description: 商品Listing优化模块。使用LLM（通义千问）优化商品标题和描述，生成符合Shopee台湾市场的Listing。触发条件：(1)已落库商品需要优化 (2)执行TC-LO-001测试 (3)miaoshou-updater前需要优化内容
---

# listing-optimizer

商品Listing优化模块。调用通义千问LLM，将商品标题和描述优化为符合Shopee台湾市场的Listing。

## 核心文件

- **模块路径**: `/home/ubuntu/.openclaw/skills/listing-optimizer/optimizer.py`

## LLM配置

```python
LLM_API_KEY = 'sk-914c1a9a5f054ab4939464389b5b791f'
LLM_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
LLM_MODEL = 'qwen-plus'  # 可切换 qwen3-plus 等
```

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
    'model_used': 'qwen-plus'
}
```

## 提示词模板

```
你是一位專業的Shopee台灣電商運營專家。
請將以下商品信息優化為符合台灣市場的Listing：

原始標題：{原始標題}
原始描述：{原始描述}
商品類目：{類目}
重量：{重量}g

要求：
1. 標題簡潔有力，符合台灣搜尋習慣
2. 描述結構化，使用表情符號增加可讀性
3. 全部使用繁體中文
4. 標題不超過120字符
5. 包含關鍵詞但不要堆砌
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
| API余额不足 | 联系阿里云充值 |

## 费用参考

- qwen-plus: ~¥0.004/1K tokens
- qwen3-plus: ~¥0.001/1K tokens（推荐）
