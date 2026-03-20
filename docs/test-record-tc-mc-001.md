# TC-MC-001 测试记录

## 测试目标
验证 miaoshou-collector 模块能正确采集1688商品到Shopee采集箱

## 测试时间
2026-03-20 12:50

## 测试结果
✅ **通过**

## 采集流程
1. 访问产品采集页面 (`fetchType=linkCopy`)
2. 输入1688链接
3. 点击"采集并自动认领"
4. 等待60秒让采集完成
5. 访问Shopee采集箱验证商品

## 关键URL
- 产品采集：`https://erp.91miaoshou.com/common_collect_box/index?fetchType=linkCopy`
- **Shopee采集箱：`https://erp.91miaoshou.com/shopee/collect_box/items`**（正确URL！）

## 测试数据
- 1688商品ID：1027205078815
- 采集结果：成功出现在Shopee采集箱
- 认领时间：2026-03-20 12:10:50

## 截图记录
| 步骤 | 截图 |
|------|------|
| Step 1 - 产品采集页面 | `step1_page_20260320_125040.png` |
| Step 2 - 链接已输入 | `step2_link_filled_20260320_125040.png` |
| Step 3 - 采集完成 | `step3_after_collect_20260320_125140.png` |
| Step 4 - Shopee采集箱 | `step4_shopee_box_20260320_125148.png` |
| Step 5 - 商品截图 | `product_1027205078815_20260320_125151.png` |

## 重要发现

### URL问题
- ❌ 错误URL：`https://erp.91miaoshou.com/common_collect_box/index?fetchType=shopeeCopy`
- ✅ 正确URL：`https://erp.91miaoshou.com/shopee/collect_box/items`

### 代码修复
```python
# 错误的URL（会被重定向到linkCopy）
SHOPEE_COLLECT_URL = f'{MIAOSHOU_BASE_URL}/common_collect_box/index?fetchType=shopeeCopy'

# 正确的URL
SHOPEE_COLLECT_URL = f'{MIAOSHOU_BASE_URL}/shopee/collect_box/items'
```

### 商品信息（验证数据）
- 标题：日式复古风实木竹编收纳筐客厅桌面收纳盒家居书本零食杂物框
- 货源ID：1027205078815
- 货源：1688
- 售价：CNY 36.80~76.80
- 货源价格：CNY 36.80~76.80
- 库存：1490
- 重量：0.630 kg
- 店铺：主账号
- 认领时间：2026-03-20 12:10:50

## 结论
miaoshou-collector 模块测试通过！商品成功从1688采集到妙手ERP的Shopee采集箱。
