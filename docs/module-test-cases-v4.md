# 模块测试用例与目标成果 v4

**项目：** 自动采集方案 v6
**创建日期：** 2026-03-20
**版本：** v4.0（区分产品采集与公用采集箱页面）
**状态：** 待审核

---

## 验收标准总则

1. **产品采集页面**和**公用采集箱页面**是两个独立的页面，有严格的先后顺序
2. 所有涉及妙手ERP操作的测试用例，预期结果必须包含浏览器页面截图验证
3. 截图命名规范：`{模块}_{用例编号}_{操作类型}.png`

---

## 一、概念说明

### 1.1 两个独立页面

| 页面 | 功能 | URL示例 | 操作 |
|------|------|---------|------|
| **产品采集** | 发起1688商品采集 | `/collect/product` | 输入链接，点击「采集」 |
| **公用采集箱** | 存储和管理已采集商品 | `/collect/list` | 查看列表，点击「编辑」 |

### 1.2 正确流程（两步）

```
Step 1: 产品采集页面
  → 输入1688链接
  → 点击「采集」
  → 等待"采集成功"提示
  截图: tc_mc_001_page.png（输入链接后）
  截图: tc_mc_001_result.png（采集成功）

Step 2: 公用采集箱页面
  → 进入公用采集箱
  → 验证商品已出现在列表中
  截图: tc_mc_002_list.png（商品列表）
  截图: tc_mc_002_verify.png（单个商品详情）
```

---

## 二、collector-scraper（采集箱爬虫模块）

### 2.1 模块目标

从妙手ERP公用采集箱的商品编辑页爬取完整信息

**注意：** 此模块操作的是公用采集箱的「编辑页面」，不是产品采集页面

### 2.2 成果指标

- **数据完整率：** ≥ 95%
- **采集耗时：** ≤ 30秒/商品
- **SKU解析准确率：** ≥ 98%
- **图片URL提取率：** 100%

### 2.3 测试用例

#### TC-SC-001: 从公用采集箱编辑页采集

**前置条件：** 妙手ERP已登录，Browser Relay可用，公用采集箱有测试商品

**测试步骤：**
1. 进入公用采集箱列表页 `/collect/list`
2. 找到目标商品，点击「编辑」
3. 进入编辑页 `/collect/edit/{product_id}`
4. 截图保存: tc_sc_001_edit_page.png
5. 执行 scraper.scrape_product(product_id)
6. 截图保存: tc_sc_001_output.png
7. 验证输出JSON每个字段

**验证点：**
- [ ] 编辑页面成功打开（公用采集箱编辑页）
- [ ] alibaba_product_id 非空，8-16位数字
- [ ] product_title 长度 > 10字符
- [ ] main_images ≥ 1张
- [ ] sku_list ≥ 1个，每个含 price > 0, stock ≥ 0
- [ ] detail_images ≥ 1张
- [ ] packaging_info.weight ≥ 0

**输出文件：**
- /home/ubuntu/work/tmp/scraper_test/tc_sc_001_edit_page.png
- /home/ubuntu/work/tmp/scraper_test/tc_sc_001_output.png
- /home/ubuntu/work/tmp/scraper_test/tc_sc_001_data.json

**预期结果:** 所有验证点通过，函数返回 True

#### TC-SC-002: 数据字段完整率检查（10商品）

**前置条件：** 公用采集箱中有≥10个商品

**测试步骤：**
1. 在公用采集箱列表随机选取10个商品
2. 依次进入编辑页，执行 scraper.scrape_product()
3. 统计每个字段的非空率

**验证点：**
- [ ] alibaba_product_id 非空率 = 100%
- [ ] product_title 非空率 = 100%
- [ ] main_images 非空率 = 100%
- [ ] sku_list 非空率 = 100%
- [ ] detail_images 非空率 = 100%
- [ ] 整体字段完整率 >= 95%

**输出文件：** /home/ubuntu/work/tmp/scraper_test/tc_sc_002_report.csv

**预期结果:** 整体字段完整率 >= 95%

#### TC-SC-003: 采集性能测试

**前置条件：** 公用采集箱中有测试商品

**测试步骤：**
1. 记录开始时间
2. 进入编辑页，执行 scraper.scrape_product()
3. 记录结束时间，计算耗时

**验证点：**
- [ ] 单次采集耗时 <= 30秒

**输出文件：** /home/ubuntu/work/tmp/scraper_test/tc_sc_003_timing.json

**预期结果:** 耗时 <= 30.0 秒

#### TC-SC-004: SKU解析准确性

**前置条件：** 公用采集箱商品有多个SKU

**测试步骤：**
1. 在公用采集箱编辑页截图SKU区域
2. 执行 scraper.scrape_product()
3. 对比SKU数量与页面显示

**验证点：**
- [ ] SKU总数与页面显示一致
- [ ] 每个SKU的price解析正确（误差<=0.01）
- [ ] 每个SKU的stock解析正确
- [ ] 每个SKU的properties解析正确

**截图要求：**
- tc_sc_004_page.png: 编辑页SKU区域截图
- tc_sc_004_output.png: 输出JSON可视化

**预期结果:** SKU解析准确率 >= 98%

---

## 三、miaoshou-collector（妙手采集模块）

### 3.1 模块目标

在**产品采集页面**发起1688商品采集，采集后数据自动进入公用采集箱

### 3.2 两个独立页面

| 页面 | URL | 功能 |
|------|-----|------|
| 产品采集 | `/collect/product` | 发起采集（输入链接，点击采集） |
| 公用采集箱 | `/collect/list` | 验证结果（查看列表） |

### 3.3 成果指标

- **采集发起成功率：** ≥ 95%
- **1688链接解析：** 100%
- **公用采集箱验证：** 100%（数据必须进入公用采集箱）
- **操作耗时：** ≤ 60秒/商品

### 3.4 测试用例

#### TC-MC-001: 产品采集页面→采集→公用采集箱验证

**前置条件：** 妙手ERP已登录

**测试步骤：**

**Part 1 - 产品采集页面操作：**
1. 进入产品采集页面 `/collect/product`
2. 截图: tc_mc_001_page.png（输入链接前）
3. 输入1688链接: `https://detail.1688.com/offer/6012345678.html`
4. 截图: tc_mc_001_link_filled.png（输入链接后）
5. 点击「采集」按钮
6. 等待采集完成（显示成功提示）
7. 截图: tc_mc_001_result.png（采集成功提示）

**Part 2 - 公用采集箱页面验证：**
8. 进入公用采集箱页面 `/collect/list`
9. 截图: tc_mc_001_list.png（商品列表）
10. 找到刚才采集的商品
11. 截图: tc_mc_001_product.png（商品条目）

**验证点：**
- [ ] 产品采集页面成功打开
- [ ] 1688链接正确输入
- [ ] 点击「采集」按钮无错误
- [ ] 显示"采集成功"提示
- [ ] 公用采集箱列表中有该商品
- [ ] 商品信息完整（标题/价格/图片）

**截图要求：**
- tc_mc_001_page.png: 产品采集页面（初始）
- tc_mc_001_link_filled.png: 输入链接后
- tc_mc_001_result.png: 采集成功提示
- tc_mc_001_list.png: 公用采集箱列表
- tc_mc_001_product.png: 商品条目详情

**预期结果:** 采集发起成功，商品已进入公用采集箱
**浏览器截图验证:** tc_mc_001_result.png 显示采集成功 + tc_mc_001_list.png 显示商品在列表中

#### TC-MC-002: 公用采集箱采集状态验证

**前置条件：** TC-MC-001已完成，商品已在公用采集箱

**测试步骤：**
1. 进入公用采集箱页面 `/collect/list`
2. 截图: tc_mc_002_list.png
3. 找到目标商品
4. 点击商品进入编辑页
5. 截图: tc_mc_002_edit.png
6. 验证商品状态

**验证点：**
- [ ] 公用采集箱中存在该商品
- [ ] 商品状态 = "已采集" 或可编辑状态
- [ ] 商品信息完整（标题/价格/图片数）
- [ ] 可正常进入编辑页面

**截图要求：**
- tc_mc_002_list.png: 公用采集箱列表（标记目标商品）
- tc_mc_002_edit.png: 编辑页面

**预期结果:** 公用采集箱验证成功
**浏览器截图验证:** tc_mc_002_list.png 显示商品在列表中 + tc_mc_002_edit.png 显示编辑页

#### TC-MC-003: 关键词搜索采集

**前置条件：** 妙手ERP已登录，产品采集页面可用

**测试步骤：**

**Part 1 - 产品采集页面搜索：**
1. 进入产品采集页面 `/collect/product`
2. 输入搜索关键词
3. 设置价格区间
4. 点击搜索
5. 截图: tc_mc_003_search.png（搜索结果）

**Part 2 - 添加到公用采集箱：**
6. 选择商品，点击添加
7. 等待添加成功
8. 截图: tc_mc_003_added.png

**Part 3 - 公用采集箱验证：**
9. 进入公用采集箱页面
10. 验证商品已在列表中
11. 截图: tc_mc_003_list.png

**验证点：**
- [ ] 搜索结果返回多个商品
- [ ] 价格区间过滤生效
- [ ] 商品成功添加到公用采集箱
- [ ] 公用采集箱列表中有该商品

**截图要求：**
- tc_mc_003_search.png: 搜索结果
- tc_mc_003_added.png: 添加成功提示
- tc_mc_003_list.png: 公用采集箱验证

**预期结果:** 搜索采集成功，商品已在公用采集箱
**浏览器截图验证:** tc_mc_003_added.png + tc_mc_003_list.png

#### TC-MC-004: 批量采集（10链接）

**前置条件：** 妙手ERP已登录

**测试步骤：**
1. 准备10个1688商品链接
2. 对每个链接执行：
   - 进入产品采集页面
   - 输入链接，点击采集
   - 等待成功
3. 进入公用采集箱页面验证
4. 统计结果

**验证点：**
- [ ] 95%以上成功添加到公用采集箱
- [ ] 每个成功商品在公用采集箱中可查
- [ ] 总耗时 < 10分钟
- [ ] 失败链接记录错误原因

**截图要求：**
- tc_mc_004_xxx_result.png: 每个链接的采集结果截图
- tc_mc_004_xxx_list.png: 每个链接的公用采集箱验证截图

**预期结果:** success >= 9, total_time < 600s
**浏览器截图验证:** 每个成功采集均有结果截图 + 公用采集箱验证截图

---

## 四、miaoshou-updater（妙手回写模块）

### 4.1 模块目标

将优化后的标题/描述/货号回写到**公用采集箱编辑页面**

### 4.2 操作页面

公用采集箱编辑页：`/collect/edit/{product_id}`

### 4.3 测试用例

#### TC-MU-001: 编辑页面填写

**前置条件：** 妙手ERP已登录，商品在公用采集箱中已编辑

**测试步骤：**
1. 进入公用采集箱页面 `/collect/list`
2. 找到目标商品，点击「编辑」
3. 进入编辑页 `/collect/edit/{product_id}`
4. 截图: tc_mu_001_before.png（填写前）
5. 执行 updater.update_product(product_id, update_data)
6. 截图: tc_mu_001_after.png（填写后）
7. 点击保存
8. 截图: tc_mu_001_success.png（保存成功）

**update_data示例:**
```python
{
  "optimized_title": "「品质保障」女士休闲裤 宽松直筒 透气舒适",
  "optimized_description": "【面料】优质纯棉...\n【售后】7天无理由退换",
  "main_product_code": "SP-20260320-001"
}
```

**验证点：**
- [ ] 编辑页面成功打开（公用采集箱编辑页）
- [ ] 标题输入框值 = optimized_title
- [ ] 描述输入框值 = optimized_description
- [ ] 货号输入框值 = main_product_code
- [ ] 点击保存无错误提示
- [ ] 保存后显示成功提示

**截图要求：**
- tc_mu_001_before.png: 填写前页面
- tc_mu_001_after.png: 填写后（点击保存前）
- tc_mu_001_success.png: 保存后（显示成功提示）

**预期结果:** 所有验证点通过，函数返回 True
**浏览器截图验证:** tc_mu_001_success.png 显示公用采集箱编辑页保存成功

#### TC-MU-002: 保存后数据验证

**前置条件：** TC-MU-001已执行并保存成功

**测试步骤：**
1. 刷新公用采集箱编辑页
2. 截图: tc_mu_002_verify.png
3. 读取页面字段值
4. 查询数据库

**验证点：**
- [ ] 刷新后标题 = 填写值
- [ ] 刷新后描述 = 填写值
- [ ] 刷新后货号 = 填写值
- [ ] 数据库 optimized_title 已更新
- [ ] 数据库 status = 'optimized'

**截图要求：**
- tc_mu_002_verify.png: 刷新后页面

**预期结果:** 页面值与数据库值一致
**浏览器截图验证:** tc_mu_002_verify.png 显示数据已持久化

#### TC-MU-003: 商品货号生成

**前置条件：** products表有待处理记录

**测试步骤：**
1. 查询 products 表中无 main_product_code 的记录
2. 执行 updater.generate_product_code()
3. 验证生成格式
4. 更新数据库

**验证点：**
- [ ] 货号格式 = SP-YYYYMMDD-序号
- [ ] 序号自动递增（不重复）
- [ ] 写入 products.main_product_code 成功

**预期结果:** 货号唯一且格式正确

#### TC-MU-004: 批量回写（10商品）

**前置条件：** 公用采集箱有≥10个已优化商品

**测试步骤：**
1. 准备10个已优化商品列表
2. 执行 updater.batch_update()
3. 统计结果

**验证点：**
- [ ] 95%以上成功回写
- [ ] 每个成功的商品 main_product_code 已生成
- [ ] 每个成功的商品 status = 'optimized'
- [ ] 总耗时 < 10分钟

**截图要求：**
- tc_mu_xxx_success.png: 每个成功商品1张截图

**预期结果:** success >= 9, total_time < 600s
**浏览器截图验证:** 每个成功回写均有 tc_mu_xxx_success.png 验证

---

## 五、product-claimer（产品认领模块）

### 5.1 模块目标

在**公用采集箱**选中商品，发起产品认领，将商品发布到Shopee台湾站

### 5.2 操作页面

公用采集箱列表页：`/collect/list`（选中商品后发起认领）

### 5.3 测试用例

#### TC-PC-001: 产品认领流程

**前置条件：** 妙手ERP已登录，商品已编辑完成（在公用采集箱中）

**测试步骤：**

**Part 1 - 公用采集箱选择：**
1. 进入公用采集箱页面 `/collect/list`
2. 截图: tc_pc_001_list.png（商品列表）
3. 选中待认领商品
4. 点击「认领」按钮

**Part 2 - 认领流程：**
5. 选择目标店铺（Shopee台湾）
6. 截图: tc_pc_001_shop.png（选择店铺）
7. 确认分类映射
8. 截图: tc_pc_001_mapping.png（分类映射）
9. 完成认领
10. 截图: tc_pc_001_success.png（认领成功）

**验证点：**
- [ ] 公用采集箱页面成功打开
- [ ] 商品列表显示待认领商品
- [ ] 认领流程顺利完成
- [ ] 显示Shopee商品ID
- [ ] 无错误提示

**截图要求：**
- tc_pc_001_list.png: 公用采集箱列表（标记选中商品）
- tc_pc_001_shop.png: 选择店铺页面
- tc_pc_001_mapping.png: 分类映射页面
- tc_pc_001_success.png: 认领成功页面

**预期结果:** 认领成功，获得 Shopee 商品ID
**浏览器截图验证:** tc_pc_001_success.png 显示 Shopee 商品ID

#### TC-PC-002: 认领后数据同步

**前置条件：** TC-PC-001已执行并认领成功

**测试步骤：**
1. 等待数据同步（2-5秒）
2. 查询 products 表
3. 截图验证Shopee后台

**验证点：**
- [ ] products.shopee_product_id = 获得的ID
- [ ] products.status = 'claimed'
- [ ] products.claimed_at 非空
- [ ] products.main_product_code 非空

**截图要求：**
- tc_pc_002_verify.png: Shopee后台截图

**SQL验证:**
```sql
SELECT shopee_product_id, status, claimed_at, main_product_code
FROM products WHERE alibaba_product_id = '6012345001';
```

**预期结果:** 数据同步成功
**浏览器截图验证:** tc_pc_002_verify.png 显示 Shopee 后台状态为已上架

#### TC-PC-003: 认领失败处理

**前置条件：** 商品处于不可认领状态

**测试步骤：**
1. 在公用采集箱中选择未编辑完成的商品
2. 执行认领操作
3. 验证失败处理

**验证点：**
- [ ] 识别失败原因（未编辑/已认领/状态异常）
- [ ] 返回错误信息
- [ ] 不执行无效操作

**截图要求：**
- tc_pc_003_error.png: 错误提示截图

**预期结果:** 函数返回 False，附错误原因
**浏览器截图验证:** tc_pc_003_error.png 显示失败原因

#### TC-PC-004: 批量认领（10商品）

**前置条件：** ≥10个已编辑商品在公用采集箱中

**测试步骤：**
1. 准备10个已编辑商品列表
2. 执行 claimer.batch_claim()
3. 统计结果

**验证点：**
- [ ] 90%以上成功认领
- [ ] 每个成功记录获得 shopee_product_id
- [ ] 每个成功记录 status='claimed'
- [ ] 总耗时 < 20分钟

**截图要求：**
- tc_pc_xxx_success.png: 每个成功认领1张截图

**预期结果:** success >= 9, total_time < 1200s
**浏览器截图验证:** 每个成功认领均有 tc_pc_xxx_success.png 验证

---

## 六、product-storer（落库模块）

### 6.1 模块目标

将采集数据规范化落库至 ecommerce_data.products 表

### 6.2 测试用例

#### TC-ST-001: 新商品落库

**前置条件：** ecommerce_data 数据库可写

**测试步骤：**
1. 准备采集数据
2. 执行 store.insert_product()
3. 查询数据库验证

**验证点：**
- [ ] products表新增1条记录
- [ ] alibaba_product_id 正确写入
- [ ] main_images = 有效JSON数组
- [ ] status = 'pending'

**预期结果:** 查询返回1条记录，所有字段值正确

#### TC-ST-002: 重复商品更新

**前置条件：** products表已有该记录

**测试步骤：**
1. 准备同名商品数据
2. 执行 store.insert_product()
3. 验证去重

**验证点：**
- [ ] 记录总数不变
- [ ] title 已更新
- [ ] updated_at 已更新

**预期结果:** count = 1, updated = true

#### TC-ST-003: 必需字段校验

**验证点：**
- [ ] 缺少 alibaba_product_id 时抛出 ValidationError
- [ ] 数据库中无新增记录

**预期结果:** 函数返回 False

#### TC-ST-004: 图片数据落库

**验证点：**
- [ ] product_images 表新增对应记录
- [ ] image_type 正确区分（main/sku/detail）

**预期结果:** 17条记录（3主图+6SKU图+8详情图）

#### TC-ST-005: 事务回滚验证

**验证点：**
- [ ] products表无新增
- [ ] product_images表无新增
- [ ] 函数返回 False

**预期结果:** 事务100%回滚

---

## 七、listing-optimizer（Listing优化模块）

### 7.1 模块目标

使用LLM优化商品标题和描述

### 7.2 测试用例

#### TC-LO-001: 标题优化

**验证点：**
- [ ] 输出标题 30-50字符
- [ ] 保留核心品类词
- [ ] 符合Shopee格式

**预期结果:** status=success

#### TC-LO-002: 描述优化

**验证点：**
- [ ] 输出描述 100-500字符
- [ ] 包含【面料】【规格】【售后】模块

**预期结果:** status=success

#### TC-LO-003: LLM API失败降级

**验证点：**
- [ ] 降级到规则匹配
- [ ] status = 'degraded'

**预期结果:** 函数不抛异常

#### TC-LO-004: 批量优化

**验证点：**
- [ ] success >= 9
- [ ] total_time < 120s

**预期结果:** success >= 9

---

## 八、端到端测试用例

### E2E-001: 全流程采集→认领

**测试目标:** 验证从1688链接到Shopee认领的完整流程

**前置条件:** 妙手ERP已登录，Browser Relay可用，数据库正常

**执行步骤:**

**Step 1: miaoshou-collector - 产品采集页面**
- 进入产品采集页面 `/collect/product`
- 输入1688链接
- 点击「采集」
- 等待成功
- 截图: e2e_001_step1_collect_page.png
- 截图: e2e_001_step1_result.png

**Step 2: miaoshou-collector - 公用采集箱验证**
- 进入公用采集箱页面 `/collect/list`
- 验证商品已在列表中
- 截图: e2e_001_step2_list.png

**Step 3: collector-scraper - 采集箱数据爬取**
- 进入公用采集箱编辑页
- 爬取商品完整数据
- 输出: /home/ubuntu/work/tmp/e2e_001_products.json

**Step 4: product-storer - 落库**
- 落库到products表
- SQL验证: SELECT COUNT(*) = 3, status = 'pending'

**Step 5: listing-optimizer - Listing优化**
- 优化标题/描述
- 输出: /home/ubuntu/work/tmp/e2e_001_optimized.json

**Step 6: miaoshou-updater - 回写公用采集箱**
- 进入公用采集箱编辑页
- 回写优化内容
- 截图: e2e_001_step6_update.png

**Step 7: product-claimer - 产品认领**
- 在公用采集箱选中商品
- 发起认领
- 截图: e2e_001_step7_claim.png

**最终验证点：**
- [ ] products表有3条记录
- [ ] 每条记录 status = 'claimed'
- [ ] 每条记录有 shopee_product_id
- [ ] 每条记录 claimed_at 非空

**截图清单（按页面分类）：**

产品采集页面:
- e2e_001_step1_collect_page.png
- e2e_001_step1_result.png

公用采集箱页面:
- e2e_001_step2_list.png
- e2e_001_step6_update.png

认领页面:
- e2e_001_step7_claim.png

**预期结果:** 全流程成功，3个商品全部认领到Shopee台湾
**浏览器截图验证:** 每个Step均有对应页面截图

### E2E-002: 断点续传测试

**验证点：**
- [ ] 只处理status='pending'的记录
- [ ] 不重复处理已完成步骤

**预期结果:** 续传成功

---

## 九、验收签字栏

| 模块 | 页面 | 目标成果 | 截图要求 |
|------|------|----------|----------|
| miaoshou-collector | 产品采集 + 公用采集箱 | 采集发起≥95% | 两个页面都要截图 |
| collector-scraper | 公用采集箱编辑页 | 数据完整率≥95% | 编辑页截图 |
| miaoshou-updater | 公用采集箱编辑页 | 回写成功率≥95% | 编辑页截图 |
| product-claimer | 公用采集箱列表页 | 认领成功率≥90% | 列表页+认领结果截图 |

### 测试通过标准

1. 所有测试用例通过率 100%
2. 浏览器截图完整（每个操作步骤）
3. 产品采集页面和公用采集箱页面分开验证

---

*文档由 CommerceFlow 自动生成*
*版本：v4.0*
*最后更新：2026-03-20*
