# 模块测试用例与目标成果 v3

**项目：** 自动采集方案 v6
**创建日期：** 2026-03-20
**版本：** v3.0（增加妙手ERP浏览器截图验收要求）
**状态：** 待审核

---

## 验收标准总则

所有涉及妙手ERP操作的测试用例，**预期结果必须包含浏览器页面截图验证**，证明操作已成功完成。

截图命名规范：`{模块}_{用例编号}_{操作类型}.png`

---

## 一、collector-scraper（采集箱爬虫模块）

### 1.1 模块目标

从妙手ERP公用采集箱爬取商品完整信息，输出规范化JSON数据

### 1.2 成果指标

- **数据完整率：** ≥ 95%（必需字段非空率）
- **采集耗时：** ≤ 30秒/商品
- **SKU解析准确率：** ≥ 98%
- **图片URL提取率：** 100%

### 1.3 测试用例

#### TC-SC-001: 单商品完整采集

**前置条件：** 妙手ERP已登录，Browser Relay可用，公用采集箱有测试商品

**测试步骤：**
1. 打开采集箱产品编辑页
2. 截图保存: tc_sc_001_page.png
3. 执行 scraper.scrape_product(product_id)
4. 截图保存: tc_sc_001_output.png
5. 验证输出JSON每个字段

**验证点：**
- [ ] alibaba_product_id 非空，8-16位数字
- [ ] product_title 长度 > 10字符
- [ ] main_images ≥ 1张
- [ ] sku_list ≥ 1个，每个含 price > 0, stock ≥ 0
- [ ] detail_images ≥ 1张
- [ ] packaging_info.weight ≥ 0

**输出文件：**
- /home/ubuntu/work/tmp/scraper_test/tc_sc_001_page.png
- /home/ubuntu/work/tmp/scraper_test/tc_sc_001_output.png
- /home/ubuntu/work/tmp/scraper_test/tc_sc_001_data.json

**预期结果:** 所有验证点通过，函数返回 True

#### TC-SC-002: 数据字段完整率检查（10商品）

**前置条件：** 采集箱中有≥10个商品

**测试步骤：**
1. 随机选取10个采集箱商品
2. 依次执行 scraper.scrape_product()
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

**前置条件：** 采集箱中有测试商品

**测试步骤：**
1. 记录开始时间
2. 执行 scraper.scrape_product()
3. 记录结束时间，计算耗时

**验证点：**
- [ ] 单次采集耗时 <= 30秒

**输出文件：** /home/ubuntu/work/tmp/scraper_test/tc_sc_003_timing.json

**预期结果:** 耗时 <= 30.0 秒

#### TC-SC-004: SKU解析准确性

**前置条件：** 采集箱商品有多个SKU

**测试步骤：**
1. 打开商品编辑页截图
2. 执行 scraper.scrape_product()
3. 对比SKU数量与页面显示

**验证点：**
- [ ] SKU总数与页面显示一致
- [ ] 每个SKU的price解析正确（误差<=0.01）
- [ ] 每个SKU的stock解析正确
- [ ] 每个SKU的properties解析正确

**截图要求：**
- tc_sc_004_page.png: 页面SKU区域截图
- tc_sc_004_output.png: 输出JSON可视化

**预期结果:** SKU解析准确率 >= 98%

---

## 二、product-storer（落库模块）

### 2.1 模块目标

将采集数据规范化落库至 ecommerce_data.products 表

### 2.2 成果指标

- **落库成功率：** ≥ 99%
- **重复数据处理：** 100%（基于alibaba_product_id去重）
- **数据完整性：** 100%
- **事务正确性：** 100%

### 2.3 测试用例

#### TC-ST-001: 新商品落库

**前置条件：** ecommerce_data 数据库可写，products表存在

**测试步骤：**
1. 准备采集数据（alibaba_product_id = 新值）
2. 执行 store.insert_product(product_data)
3. 查询数据库验证

**验证点：**
- [ ] products表新增1条记录
- [ ] alibaba_product_id 正确写入
- [ ] main_images = 有效JSON数组
- [ ] sku_list = 有效JSON数组
- [ ] status = 'pending'
- [ ] created_at 为当前时间

**SQL验证:**
```sql
SELECT id, alibaba_product_id, jsonb_array_length(main_images) as main_count,
       jsonb_array_length(sku_list) as sku_count, status, created_at
FROM products WHERE alibaba_product_id = '6012345001';
```

**预期结果:** 查询返回1条记录，所有字段值正确

#### TC-ST-002: 重复商品更新（去重验证）

**前置条件：** products表已有该alibaba_product_id记录

**测试步骤：**
1. 准备同名商品数据（修改title）
2. 执行 store.insert_product()
3. 查询数据库

**验证点：**
- [ ] products表记录总数不变（未新增）
- [ ] product_title 已更新
- [ ] updated_at 已更新
- [ ] 函数返回原有record_id

**SQL验证:**
```sql
SELECT COUNT(*) as count, product_title, updated_at > created_at as updated
FROM products WHERE alibaba_product_id = '6012345001' GROUP BY product_title;
```

**预期结果:** count = 1, updated = true

#### TC-ST-003: 必需字段校验

**前置条件：** products表结构正确

**测试步骤：**
1. 准备缺少alibaba_product_id的数据
2. 执行 store.insert_product()

**验证点：**
- [ ] 抛出 ValidationError 异常
- [ ] 异常消息包含 'alibaba_product_id'
- [ ] 数据库中无新增记录

**预期结果:** 函数返回 False，数据库无变化

#### TC-ST-004: 图片数据落库

**前置条件：** products表和product_images表存在

**测试步骤：**
1. 准备含3张主图、6个SKU图、8张详情图的商品数据
2. 执行 store.insert_product()
3. 查询 product_images 表

**验证点：**
- [ ] product_images 表新增17条记录
- [ ] 3条 image_type = 'main'
- [ ] 6条 image_type = 'sku'
- [ ] 8条 image_type = 'detail'
- [ ] 每条记录的 product_id 正确关联

**SQL验证:**
```sql
SELECT image_type, COUNT(*) as count FROM product_images
WHERE product_id = (SELECT id FROM products WHERE alibaba_product_id = '6012345001')
GROUP BY image_type;
```

**预期结果:** main=3, sku=6, detail=8

#### TC-ST-005: 事务回滚验证

**前置条件：** products表和product_images表存在

**测试步骤：**
1. 准备会导致product_images写入失败的数据
2. 执行 store.insert_product()
3. 查询两张表验证

**验证点：**
- [ ] products表无新增记录
- [ ] product_images表无新增记录
- [ ] 函数返回 False

**预期结果:** 事务100%回滚，无半条记录

---

## 三、listing-optimizer（Listing优化模块）

### 3.1 模块目标

使用LLM优化商品标题和描述，输出Shopee平台友好的Listing

### 3.2 成果指标

- **优化成功率：** ≥ 95%
- **标题长度：** 30-50字符
- **描述长度：** 100-500字符
- **关键词保留率：** ≥ 80%
- **API响应时间：** ≤ 10秒/商品

### 3.3 测试用例

#### TC-LO-001: 标题优化

**前置条件：** LLM API可用

**测试步骤：**
1. 输入原始标题
2. 执行 optimizer.optimize_title()
3. 验证输出

**验证点：**
- [ ] 输出标题长度 30-50字符
- [ ] 保留核心品类词
- [ ] 无乱码或特殊字符
- [ ] 符合Shopee标题格式

**预期结果:** 输出标题符合格式要求，status=success

#### TC-LO-002: 描述优化

**前置条件：** LLM API可用

**测试步骤：**
1. 输入原始描述
2. 执行 optimizer.optimize_description()
3. 验证输出

**验证点：**
- [ ] 输出描述长度 100-500字符
- [ ] 包含【面料】【规格】【洗涤】【售后】模块
- [ ] 无乱码或特殊字符

**预期结果:** 输出描述符合格式要求，status=success

#### TC-LO-003: LLM API失败降级

**前置条件：** 模拟LLM API不可用

**测试步骤：**
1. 模拟API返回错误
2. 执行 optimizer.optimize_title()
3. 验证降级处理

**验证点：**
- [ ] API失败时自动降级到规则匹配
- [ ] 返回基于规则的优化结果
- [ ] status = 'degraded'
- [ ] 记录降级日志

**预期结果:** 函数不抛异常，返回降级结果

#### TC-LO-004: 批量优化（10商品）

**前置条件：** LLM API可用，10个商品数据准备完毕

**测试步骤：**
1. 准备10个商品数据
2. 执行 optimizer.batch_optimize()
3. 统计结果

**验证点：**
- [ ] 95%以上商品成功优化
- [ ] 总耗时 < 120秒
- [ ] 每个成功结果包含完整字段
- [ ] 并发数控制在3以内

**预期结果:** success >= 9, total_time < 120s

---

## 四、miaoshou-updater（妙手回写模块）

### 4.1 模块目标

将优化后的标题/描述/货号回写到妙手ERP编辑页面

### 4.2 成果指标

- **回写成功率：** ≥ 95%
- **字段填写准确率：** 100%
- **页面保存稳定性：** 100%
- **操作耗时：** ≤ 60秒/商品

### 4.3 测试用例

#### TC-MU-001: 编辑页面填写

**前置条件：** 妙手ERP已登录，采集箱有测试商品

**测试步骤：**
1. 打开采集箱产品编辑页
2. 截图保存: tc_mu_001_before.png
3. 执行 updater.update_product(product_id, update_data)
4. 截图保存: tc_mu_001_after.png
5. 点击保存
6. 截图保存: tc_mu_001_success.png

**update_data示例:**
```python
{
  "optimized_title": "「品质保障」女士休闲裤 宽松直筒 透气舒适",
  "optimized_description": "【面料】优质纯棉...\n【售后】7天无理由退换",
  "main_product_code": "SP-20260320-001"
}
```

**验证点：**
- [ ] 编辑页面成功打开
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
**浏览器截图验证:** tc_mu_001_success.png 显示采集箱编辑页保存成功（标题/描述/货号已填写）

#### TC-MU-002: 保存后数据验证

**前置条件：** TC-MU-001已执行并保存成功

**测试步骤：**
1. 刷新编辑页面（或重新打开）
2. 截图: tc_mu_002_verify.png
3. 读取页面字段值
4. 查询数据库 products 表

**验证点：**
- [ ] 刷新后标题 = 填写值
- [ ] 刷新后描述 = 填写值
- [ ] 刷新后货号 = 填写值
- [ ] 数据库 optimized_title 已更新
- [ ] 数据库 status = 'optimized'

**截图要求：**
- tc_mu_002_verify.png: 刷新后页面（证明数据持久化）

**预期结果:** 页面值与数据库值一致
**浏览器截图验证:** tc_mu_002_verify.png 显示刷新后页面数据与填写值一致

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
- [ ] 同一天第1个: SP-20260320-001
- [ ] 写入 products.main_product_code 成功

**预期结果:** 货号唯一且格式正确
**浏览器截图验证:** 数据库查询显示货号 SP-YYYYMMDD-序号 生成成功

#### TC-MU-004: 批量回写（10商品）

**前置条件：** 采集箱有≥10个已优化商品

**测试步骤：**
1. 准备10个已优化商品列表
2. 执行 updater.batch_update()
3. 统计结果

**验证点：**
- [ ] 95%以上成功回写
- [ ] 每个成功的商品 main_product_code 已生成
- [ ] 每个成功的商品 status = 'optimized'
- [ ] 总耗时 < 10分钟
- [ ] 失败商品记录错误原因

**截图要求：**
- tc_mu_xxx_success.png: 每个成功商品1张截图

**预期结果:** success >= 9, total_time < 600s
**浏览器截图验证:** 每个成功回写的商品均有 tc_mu_xxx_success.png 浏览器截图验证保存成功

---

## 五、product-claimer（产品认领模块）

### 5.1 模块目标

完成妙手ERP产品认领，将商品发布到Shopee台湾站

### 5.2 成果指标

- **认领成功率：** ≥ 90%
- **Shopee商品ID获取：** 100%
- **认领耗时：** ≤ 120秒/商品
- **店铺绑定正确率：** 100%

### 5.3 测试用例

#### TC-PC-001: 单产品认领

**前置条件：** 妙手ERP已登录，商品已编辑完成

**测试步骤：**
1. 打开产品认领页面
2. 截图: tc_pc_001_before.png
3. 选中待认领产品
4. 点击认领
5. 选择目标店铺（Shopee台湾）
6. 确认分类映射
7. 完成认领
8. 截图: tc_pc_001_success.png

**验证点：**
- [ ] 产品认领页面成功打开
- [ ] 产品列表显示待认领商品
- [ ] 认领流程顺利完成
- [ ] 显示Shopee商品ID
- [ ] 无错误提示

**截图要求：**
- tc_pc_001_before.png: 认领前（选中产品）
- tc_pc_001_select_shop.png: 选择店铺页面
- tc_pc_001_mapping.png: 分类映射页面
- tc_pc_001_success.png: 认领成功页面

**预期结果:** 认领成功，获得 Shopee 商品ID
**浏览器截图验证:** tc_pc_001_success.png 显示 Shopee 商品ID（如 1234567890）且无错误提示

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
**浏览器截图验证:** tc_pc_002_verify.png 显示 Shopee 后台该商品状态为已上架

#### TC-PC-003: 认领失败处理

**前置条件：** 商品处于不可认领状态

**测试步骤：**
1. 选择未编辑完成的商品
2. 执行认领操作
3. 验证失败处理

**验证点：**
- [ ] 识别失败原因（未编辑/已认领/状态异常）
- [ ] 返回错误信息
- [ ] 不执行无效操作
- [ ] products.status 保持不变

**截图要求：**
- tc_pc_003_error.png: 错误提示截图

**预期结果:** 函数返回 False，附错误原因
**浏览器截图验证:** tc_pc_003_error.png 显示失败原因（如"商品未编辑完成"）

#### TC-PC-004: 批量认领（10商品）

**前置条件：** ≥10个已编辑商品

**测试步骤：**
1. 准备10个已编辑商品列表
2. 执行 claimer.batch_claim()
3. 统计结果

**验证点：**
- [ ] 90%以上成功认领
- [ ] 每个成功记录获得 shopee_product_id
- [ ] 每个成功记录 status='claimed'
- [ ] 总耗时 < 20分钟
- [ ] 失败记录附错误原因

**截图要求：**
- tc_pc_xxx_success.png: 每个成功认领商品1张截图

**预期结果:** success >= 9, total_time < 1200s
**浏览器截图验证:** 每个成功认领的商品均有 tc_pc_xxx_success.png 浏览器截图验证

---

## 六、miaoshou-collector（妙手采集模块）

### 6.1 模块目标

自动操作妙手ERP发起1688商品采集

### 6.2 成果指标

- **采集发起成功率：** ≥ 95%
- **1688链接解析：** 100%
- **采集箱状态验证：** 100%
- **操作耗时：** ≤ 60秒/商品

### 6.3 测试用例

#### TC-MC-001: 1688链接采集

**前置条件：** 妙手ERP已登录

**测试步骤：**
1. 进入1688采集页面
2. 截图: tc_mc_001_page.png
3. 输入1688链接
4. 点击采集
5. 等待采集完成
6. 截图: tc_mc_001_result.png

**验证点：**
- [ ] 1688链接正确解析
- [ ] 采集按钮可点击
- [ ] 显示采集成功提示
- [ ] 商品已添加到公用采集箱

**截图要求：**
- tc_mc_001_page.png: 采集页面（输入链接后）
- tc_mc_001_result.png: 采集结果（成功提示）

**预期结果:** 采集发起成功，返回采集箱产品ID
**浏览器截图验证:** tc_mc_001_result.png 显示采集成功提示且商品已添加到公用采集箱

#### TC-MC-002: 采集状态验证

**前置条件：** TC-MC-001已完成

**测试步骤：**
1. 进入公用采集箱页面
2. 查找刚才采集的商品
3. 截图: tc_mc_002_verify.png
4. 验证商品状态

**验证点：**
- [ ] 采集箱中存在该商品
- [ ] 商品状态 = "已采集"
- [ ] 商品信息完整

**截图要求：**
- tc_mc_002_verify.png: 采集箱中商品列表

**预期结果:** 采集箱验证成功
**浏览器截图验证:** tc_mc_002_verify.png 显示公用采集箱中有该商品且状态为已采集

#### TC-MC-003: 关键词搜索采集

**前置条件：** 妙手ERP已登录，1688采集页面可用

**测试步骤：**
1. 输入搜索关键词
2. 设置价格区间
3. 点击搜索
4. 截图: tc_mc_003_search.png
5. 选择商品加入采集箱

**验证点：**
- [ ] 搜索结果返回多个商品
- [ ] 价格区间过滤生效
- [ ] 商品可成功添加到采集箱

**截图要求：**
- tc_mc_003_search.png: 搜索结果列表

**预期结果:** 搜索采集成功
**浏览器截图验证:** tc_mc_003_search.png 显示搜索结果列表且商品已添加到采集箱

#### TC-MC-004: 批量采集（10链接）

**前置条件：** 妙手ERP已登录

**测试步骤：**
1. 准备10个1688商品链接
2. 执行 collector.batch_collect()
3. 统计结果

**验证点：**
- [ ] 95%以上成功添加到采集箱
- [ ] 每个成功商品在采集箱中可查
- [ ] 总耗时 < 10分钟
- [ ] 失败链接记录错误原因

**截图要求：**
- tc_mc_xxx_result.png: 每个成功采集1张截图

**预期结果:** success >= 9, total_time < 600s
**浏览器截图验证:** 每个成功采集的商品均有 tc_mc_xxx_result.png 浏览器截图验证

---

## 七、端到端测试用例

### E2E-001: 全流程采集→认领

**测试目标:** 验证从1688链接到Shopee认领的完整流程

**前置条件:** 妙手ERP已登录，Browser Relay可用，数据库正常，COS可用，LLM API可用

**输入测试数据:**
- https://detail.1688.com/offer/601234567.html（女士休闲裤）
- https://detail.1688.com/offer/601234568.html（男士T恤）
- https://detail.1688.com/offer/601234569.html（运动鞋）

**执行步骤:**

**Step 1: miaoshou-collector**
- 输入：用户提供的1688商品链接
- 动作：使用妙手ERP「产品采集」功能发起初步采集
- 输出：采集数据进入公用采集箱
- 截图: e2e_001_step1_collect.png

**验证:** 3个商品已入库采集箱

**Step 2: collector-scraper**
- 爬取3个商品完整数据
- 输出: /home/ubuntu/work/tmp/e2e_001_products.json
- 验证: 每个商品完整字段

**Step 3: product-storer**
- 落库到products表
- SQL验证: SELECT COUNT(*) = 3, status = 'pending'
- 截图: e2e_001_step3_db.png

**Step 4: listing-optimizer**
- 优化3个商品标题/描述
- 输出: /home/ubuntu/work/tmp/e2e_001_optimized.json
- 验证: 每个商品 optimized_title/description 非空

**Step 5: miaoshou-updater**
- 回写优化内容到妙手ERP
- 截图: e2e_001_step5_update.png
- 验证: 采集箱中商品标题/描述已更新

**Step 6: product-claimer**
- 认领3个商品到Shopee台湾
- 截图: e2e_001_step6_claim.png
- 验证: 获得3个 shopee_product_id

**最终验证点：**
- [ ] products表有3条记录
- [ ] 每条记录 status = 'claimed'
- [ ] 每条记录有 shopee_product_id
- [ ] 每条记录有 main_product_code
- [ ] 每条记录 claimed_at 非空
- [ ] 整体成功率 >= 90%

**截图清单:**
- e2e_001_step1_collect.png: 采集成功（妙手ERP采集箱页面）
- e2e_001_step5_update.png: 编辑保存成功（妙手ERP编辑页）
- e2e_001_step6_claim.png: 认领成功（妙手ERP认领结果页面）
- e2e_001_final_shopee.png: Shopee后台截图

**输出文件:**
- /home/ubuntu/work/tmp/e2e_001_input.json
- /home/ubuntu/work/tmp/e2e_001_products.json
- /home/ubuntu/work/tmp/e2e_001_optimized.json
- /home/ubuntu/work/tmp/e2e_001_final.json

**预期结果:** 全流程成功，3个商品全部认领到Shopee台湾
**浏览器截图验证:** 每个Step均有对应浏览器截图验证：
- e2e_001_step1_collect.png（采集成功）
- e2e_001_step5_update.png（编辑保存）
- e2e_001_step6_claim.png（认领成功）

### E2E-002: 断点续传测试

**测试目标:** 验证流程中断后可续传，不重复处理

**前置条件:** E2E-001执行到Step3后中断，products表有3条pending记录

**执行步骤:**
1. 查询 status = 'pending' 的记录
2. 从Step4继续执行
3. 验证不重复处理已完成步骤

**验证点：**
- [ ] 只处理status='pending'的记录
- [ ] status='optimized'的记录跳过Step4
- [ ] status='claimed'的记录跳过Step5-6
- [ ] 最终所有记录 status='claimed'
- [ ] 无重复操作

**预期结果:** 续传成功，流程完整闭合

---

## 八、验收签字栏

| 模块 | 目标成果 | 验收标准 | 浏览器截图要求 |
|------|----------|----------|----------------|
| collector-scraper | 数据完整率≥95% | TC-SC-001~004全部通过 | N/A（数据采集无需截图） |
| product-storer | 落库成功率≥99% | TC-ST-001~005全部通过 | N/A（数据库操作无需截图） |
| listing-optimizer | 优化成功率≥95% | TC-LO-001~004全部通过 | N/A（API调用无需截图） |
| miaoshou-updater | 回写成功率≥95% | TC-MU-001~004全部通过 | 每个成功操作需截图验证 |
| product-claimer | 认领成功率≥90% | TC-PC-001~004全部通过 | 每个成功操作需截图验证 |
| miaoshou-collector | 采集发起≥95% | TC-MC-001~004全部通过 | 每个成功操作需截图验证 |

### 测试通过标准

**单模块测试：** 所有测试用例（TC-xxx）通过率 100%

**端到端测试：** E2E-001、E2E-002 全部通过

**综合验收：** 6个模块全部通过签字 + 浏览器截图完整

---

*文档由 CommerceFlow 自动生成*
*版本：v3.0*
*最后更新：2026-03-20*
