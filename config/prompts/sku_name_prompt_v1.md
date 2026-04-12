# Shopee 全站点 SKU 规格命名提示词 v1.0

## 运行上下文
- 站点：{site_code}
- 语言：{listing_language}
- 商品标题：{product_title}
- 商品描述：{product_description}
- 原始SKU名称：{original_sku_name}
- 尺寸提示：{dimension_hint}
- 最大长度：{max_length}

## 任务目标
输出一个适合买家阅读的SKU名称。

---

## 语言硬约束

根据 `{listing_language}` 参数输出对应语言的SKU名称：

| listing_language | 输出要求 |
|-----------------|---------|
| zh-Hant | 台湾繁体中文 |
| en | 英文 |
| id | 印尼语 |
| th | 泰语 |
| vi | 越南语 |
| ms | 马来语 |
| pt | 巴西葡萄牙语 |
| es | 墨西哥西班牙语 |

---

## SKU命名原则

### 信息优先级
```
颜色 > 尺寸 > 型号 > 材质 > 其他差异
```

### 信息提取来源
1. 优先从 `{original_sku_name}` 提取关键差异信息
2. 其次从 `{dimension_hint}` 获取尺寸信息
3. 最后从 `{product_title}` 和 `{product_description}` 补充

### 命名规范
✅ 保留关键差异信息（颜色/尺寸/型号）
✅ 自然、简洁、买家易理解
✅ 长度不超过 {max_length} 个字符
✅ 如有多个差异，用空格或 `-` 分隔

❌ 不要重复整条商品标题
❌ 不要包含营销词汇
❌ 不要过于技术化或内部编码

---

## 命名格式建议

### 单一差异
```
颜色：White / 白色 / Putih
尺寸：30cm / 30x20cm / Medium
型号：Model A / Type 1
```

### 多重差异
```
颜色+尺寸：White 30cm / 白色 30cm
颜色+型号：Black Model A / 黑色 A款
尺寸+材质：Large Cotton / 大号 棉质
```

### 站点本地化示例

| 站点 | SKU命名示例 |
|-----|------------|
| 台湾 | 白色 30cm / 黑色 L號 / 灰色 3層 |
| 菲律宾 | White 30cm / Black Large / Grey 3-Tier |
| 印尼 | Putih 30cm / Hitam Besar / Abu 3-Lapis |
| 泰国 | สีขาว 30cm / สีดำ ไซส์ใหญ่ |
| 越南 | Trắng 30cm / Đen Cỡ lớn |
| 巴西 | Branco 30cm / Preto Grande |

---

## 长度控制

**最大长度：** {max_length} 个字符

**建议长度：**
- 中文站点：10-25字符
- 英文站点：10-30字符
- 其他语言：15-35字符

**过长处理：**
- 优先保留最重要的差异信息
- 省略次要信息
- 使用缩写（如 L/XL/XXL, S/M/L）

---

## 跨境合规禁止事项

### 绝对禁止（所有站点）
```
❌ 本地库存暗示：
   现货/現貨/Ready Stock
   
❌ 营销词汇：
   热销/爆款/Best Seller/限量/Limited
   
❌ 物流优惠：
   包邮/免运/Free Shipping
```

---

## 输出要求

**只输出一个SKU名称。**

❌ 不要输出解释
❌ 不要输出多个候选
❌ 不要输出引号或项目符号

**输出格式：** 直接输出SKU名称文本，无任何额外内容。