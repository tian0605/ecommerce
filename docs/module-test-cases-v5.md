# 模块测试用例与目标成果 v5

**项目：** 自动采集方案 v6
**创建日期：** 2026-03-20
**版本：** v5.0（明确技术方案：无需Browser Relay）
**状态：** 待测试

---

## 验收标准总则

1. **技术方案：** Playwright + Chromium 直接访问妙手ERP，无需Browser Relay插件
2. **两个独立页面：** 产品采集页面、公用采集箱页面，严格先后顺序
3. **浏览器截图验证：** 所有妙手ERP操作必须截图
4. **截图命名规范：** `{模块}_{用例编号}_{操作类型}.png`

---

## 一、技术方案说明

### 1.1 为什么不需要Browser Relay？

| 问题 | 解决方案 |
|------|----------|
| 1688 IP反爬 | 妙手ERP服务器访问1688（妙手IP不受限） |
| 妙手ERP访问 | Playwright直接启动Chromium访问（服务器IP可访问） |

**已验证：** `erp.91miaoshou.com` 返回 HTTP 200

### 1.2 运行环境要求

```bash
# Playwright + Chromium
pip install playwright
playwright install chromium

# 妙手ERP Cookies
/home/ubuntu/work/config/miaoshou_cookies.json
```

---

## 二、miaoshou-collector（妙手采集模块）

### 2.1 模块目标

在**产品采集页面**发起1688商品采集，完成后验证商品已进入**公用采集箱**

### 2.2 技术实现

- **浏览器：** Playwright + Chromium（headless=False 开发模式）
- **Cookies：** `/home/ubuntu/work/config/miaoshou_cookies.json`
- **页面1：** `https://erp.91miaoshou.com/common_collect_box/index?fetchType=1688Product`
- **页面2：** `https://erp.91miaoshou.com/common_collect_box/index?fetchType=public`

### 2.3 成果指标

| 指标 | 目标值 | 验收条件 |
|------|--------|----------|
| 采集发起成功率 | ≥ 95% | 点击采集后无错误 |
| 采集成功提示检测 | 100% | 页面显示成功或无错误提示 |
| 公用采集箱验证 | 100% | 商品出现在公用采集箱列表 |
| 操作耗时 | ≤ 60秒/商品 | 从输入链接到验证完成 |

### 2.4 测试用例

#### TC-MC-001: 产品采集→公用采集箱验证（单链接）

**前置条件：** 
- Playwright + Chromium 可用
- 妙手ERP Cookies 有效
- 公用采集箱无测试商品

**测试步骤：**

**Part 1 - 产品采集页面：**
1. 启动Chromium（headless=False）
2. 加载Cookies，访问产品采集页面
3. 截图: `tc_mc_001_page.png`（页面加载完成）
4. 输入1688链接
5. 截图: `tc_mc_001_link_filled.png`（链接已输入）
6. 点击「采集」按钮
7. 等待5秒
8. 截图: `tc_mc_001_result.png`（采集结果）

**Part 2 - 公用采集箱验证：**
9. 访问公用采集箱页面
10. 截图: `tc_mc_001_list.png`（商品列表）
11. 在列表中查找商品
12. 截图: `tc_mc_001_product.png`（找到的商品）

**验证点：**
- [ ] 产品采集页面成功打开
- [ ] 1688链接正确输入
- [ ] 点击「采集」按钮无错误
- [ ] 等待后无错误提示
- [ ] 公用采集箱列表中有该商品
- [ ] 商品可正常点击进入编辑

**截图要求：**
- `tc_mc_001_page.png` - 产品采集页面初始状态
- `tc_mc_001_link_filled.png` - 链接已输入
- `tc_mc_001_result.png` - 采集操作后
- `tc_mc_001_list.png` - 公用采集箱列表
- `tc_mc_001_product.png` - 找到的商品

**预期结果:** 
- 函数返回 `success=True`
- 5张截图均已保存
- 商品ID已提取

**浏览器截图验证:** 
- `tc_mc_001_result.png` 显示采集步骤完成
- `tc_mc_001_list.png` 显示商品在公用采集箱中

#### TC-MC-002: 公用采集箱采集状态验证

**前置条件：** TC-MC-001已完成

**测试步骤：**
1. 访问公用采集箱页面
2. 截图: `tc_mc_002_list.png`
3. 点击目标商品进入编辑页
4. 截图: `tc_mc_002_edit.png`
5. 验证商品状态

**验证点：**
- [ ] 公用采集箱中存在该商品
- [ ] 商品状态为可编辑
- [ ] 可正常进入编辑页面

**截图要求：**
- `tc_mc_002_list.png` - 列表（标记目标商品）
- `tc_mc_002_edit.png` - 编辑页面

**预期结果:** 商品可正常编辑

#### TC-MC-003: 关键词搜索采集

**前置条件：** 妙手ERP产品采集页面可用

**测试步骤：**

**Part 1 - 产品采集页面搜索：**
1. 进入产品采集页面
2. 输入搜索关键词
3. 设置价格区间
4. 点击搜索
5. 截图: `tc_mc_003_search.png`

**Part 2 - 添加到公用采集箱：**
6. 选择商品
7. 点击添加
8. 截图: `tc_mc_003_added.png`

**Part 3 - 公用采集箱验证：**
9. 进入公用采集箱
10. 截图: `tc_mc_003_list.png`

**验证点：**
- [ ] 搜索结果返回多个商品
- [ ] 商品成功添加到公用采集箱
- [ ] 公用采集箱列表中有该商品

**截图要求：**
- `tc_mc_003_search.png`
- `tc_mc_003_added.png`
- `tc_mc_003_list.png`

**预期结果:** 搜索采集成功

#### TC-MC-004: 批量采集（10链接）

**前置条件：** 10个1688商品链接

**测试步骤：**
1. 准备10个1688链接
2. 依次执行采集
3. 每链接验证公用采集箱
4. 统计成功率

**验证点：**
- [ ] 95%以上成功（≥10个中≥10个）
- [ ] 每个成功商品在公用采集箱中可查
- [ ] 总耗时 < 10分钟

**截图要求：**
- 每个链接至少3张截图（采集页+结果+公用采集箱）

**预期结果:** success >= 9

---

## 三、collector-scraper（采集箱爬虫模块）

### 3.1 模块目标

从**公用采集箱编辑页面**爬取完整商品信息

### 3.2 技术实现

- **页面：** `https://erp.91miaoshou.com/common_collect_box/index?fetchType=public`
- **操作：** 进入编辑页，提取页面数据

### 3.3 采集字段

| 字段 | 必需 | 验收标准 |
|------|------|----------|
| alibaba_product_id | ✅ | 非空，8-16位数字 |
| product_title | ✅ | > 10字符 |
| main_images | ✅ | ≥1张URL |
| sku_list | ✅ | ≥1个，含price/stock |
| detail_images | ✅ | ≥1张URL |
| packaging_info | ✅ | 含weight |

### 3.4 测试用例

#### TC-SC-001: 单商品完整采集

**前置条件：** 公用采集箱有测试商品

**测试步骤：**
1. 进入公用采集箱列表
2. 点击目标商品「编辑」
3. 截图: `tc_sc_001_edit_page.png`
4. 执行爬取函数
5. 截图: `tc_sc_001_output.png`
6. 验证输出JSON

**验证点：**
- [ ] 编辑页面成功打开
- [ ] alibaba_product_id 非空，8-16位数字
- [ ] product_title > 10字符
- [ ] main_images ≥1
- [ ] sku_list ≥1，每个含price>0, stock≥0
- [ ] detail_images ≥1
- [ ] packaging_info.weight ≥0

**截图要求：**
- `tc_sc_001_edit_page.png` - 编辑页面
- `tc_sc_001_output.png` - 输出JSON

**预期结果:** 所有验证点通过

#### TC-SC-002~004: 字段完整率、性能、SKU准确性

（同v4.0）

---

## 四、product-storer（落库模块）

（同v4.0，无需修改）

---

## 五、listing-optimizer（Listing优化模块）

（同v4.0，无需修改）

---

## 六、miaoshou-updater（妙手回写模块）

### 6.1 模块目标

将优化后的标题/描述/货号回写到**公用采集箱编辑页面**

### 6.2 技术实现

- **页面：** 公用采集箱编辑页
- **操作：** 填写表单，保存

### 6.3 测试用例

#### TC-MU-001: 编辑页面填写

**前置条件：** 商品在公用采集箱中

**测试步骤：**
1. 进入公用采集箱
2. 点击「编辑」
3. 截图: `tc_mu_001_before.png`
4. 填写优化后的标题/描述/货号
5. 截图: `tc_mu_001_after.png`
6. 点击保存
7. 截图: `tc_mu_001_success.png`

**验证点：**
- [ ] 编辑页面成功打开
- [ ] 标题/描述/货号正确填写
- [ ] 保存成功

**截图要求：**
- `tc_mu_001_before.png`
- `tc_mu_001_after.png`
- `tc_mu_001_success.png`

**预期结果:** 保存成功，数据持久化

#### TC-MU-002~004: 数据验证、货号生成、批量回写

（同v4.0）

---

## 七、product-claimer（产品认领模块）

### 7.1 模块目标

在**公用采集箱列表页**选中商品，发起认领到Shopee台湾

### 7.2 测试用例

#### TC-PC-001: 产品认领

**前置条件：** 商品已编辑完成

**测试步骤：**

**Part 1 - 选择商品：**
1. 进入公用采集箱列表
2. 截图: `tc_pc_001_list.png`
3. 选中待认领商品
4. 点击「认领」

**Part 2 - 认领流程：**
5. 选择目标店铺
6. 截图: `tc_pc_001_shop.png`
7. 确认分类映射
8. 截图: `tc_pc_001_mapping.png`
9. 完成认领
10. 截图: `tc_pc_001_success.png`

**验证点：**
- [ ] 公用采集箱列表页正常显示
- [ ] 商品可被选中
- [ ] 认领流程完成
- [ ] 显示Shopee商品ID

**截图要求：**
- `tc_pc_001_list.png`
- `tc_pc_001_shop.png`
- `tc_pc_001_mapping.png`
- `tc_pc_001_success.png`

**预期结果:** 获得Shopee商品ID

#### TC-PC-002~004: 数据同步、失败处理、批量认领

（同v4.0）

---

## 八、端到端测试

### E2E-001: 全流程采集→认领

**执行步骤：**

| Step | 页面 | 操作 | 截图 |
|------|------|------|------|
| 1 | 产品采集页面 | 输入1688链接，点击采集 | e2e_001_step1_*.png |
| 2 | 公用采集箱 | 验证商品在列表中 | e2e_001_step2_*.png |
| 3 | 公用采集箱编辑页 | 爬取商品数据 | - |
| 4 | 数据库 | 落库 | - |
| 5 | LLM API | 优化标题/描述 | - |
| 6 | 公用采集箱编辑页 | 回写优化内容 | e2e_001_step6_*.png |
| 7 | 公用采集箱列表页 | 认领到Shopee | e2e_001_step7_*.png |

**最终验证：**
- [ ] products表3条记录
- [ ] 每条status='claimed'
- [ ] 每条有shopee_product_id

### E2E-002: 断点续传

（同v4.0）

---

## 九、验收签字栏

| 模块 | 技术方案 | 目标 | 截图要求 |
|------|----------|------|----------|
| miaoshou-collector | Playwright+Chromium | 采集发起≥95% | 5张/链接 |
| collector-scraper | Playwright+Chromium | 数据完整率≥95% | 编辑页 |
| miaoshou-updater | Playwright+Chromium | 回写成功率≥95% | 保存成功 |
| product-claimer | Playwright+Chromium | 认领成功率≥90% | 认领结果 |

### 测试通过标准

1. 所有测试用例通过率 100%
2. 浏览器截图完整
3. 无Browser Relay依赖

---

*文档由 CommerceFlow 自动生成*
*版本：v5.0*
*最后更新：2026-03-20*
