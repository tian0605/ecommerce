# 模块测试用例与目标成果 v6

**项目：** 自动采集方案 v6
**创建日期：** 2026-03-20
**版本：** v6.0（Shopee采集箱工作流）
**状态：** 待测试

---

## 一、核心流程说明

```
1688链接 → 妙手"采集并自动认领" → Shopee采集箱 → 落库 → Listing优化 → 编辑Shopee采集箱
```

**关键变化：**
- 商品直接进入**Shopee采集箱**（不是公用采集箱）
- fetchType参数：`shopeeCopy`（不是`public`）

---

## 二、miaoshou-collector（妙手采集模块）

### 2.1 模块目标

在产品采集页面发起1688商品采集，商品自动认领到Shopee采集箱

### 2.2 成果指标

| 指标 | 目标值 | 验收条件 |
|------|--------|----------|
| 采集发起成功率 | ≥ 95% | 点击按钮后无错误 |
| 商品进入Shopee采集箱 | 100% | 在Shopee采集箱中验证 |

### 2.3 测试用例

#### TC-MC-001: 产品采集→Shopee采集箱验证

**前置条件：** 
- Playwright + Chromium 可用
- 妙手ERP Cookies 有效
- Shopee采集箱无测试商品

**测试步骤：**

**Part 1 - 产品采集页面：**
1. 启动Chromium，加载Cookies
2. 访问产品采集页面 `/common_collect_box/index?fetchType=linkCopy`
3. 截图: `tc_mc_001_page.png`
4. 输入1688链接
5. 截图: `tc_mc_001_link_filled.png`
6. 点击「采集并自动认领」按钮
7. 等待10秒
8. 截图: `tc_mc_001_result.png`

**Part 2 - Shopee采集箱验证：**
9. 访问Shopee采集箱 `/common_collect_box/index?fetchType=shopeeCopy`
10. 截图: `tc_mc_001_list.png`
11. 查找商品
12. 截图: `tc_mc_001_product.png`

**验证点：**
- [ ] 产品采集页面成功打开
- [ ] 1688链接正确输入
- [ ] 点击「采集并自动认领」无错误
- [ ] Shopee采集箱列表中有该商品

**截图要求：**
- `tc_mc_001_page.png` - 产品采集页面
- `tc_mc_001_link_filled.png` - 链接已输入
- `tc_mc_001_result.png` - 采集结果
- `tc_mc_001_list.png` - Shopee采集箱列表
- `tc_mc_001_product.png` - 找到的商品

**预期结果:** 
- 函数返回 `success=True`
- Shopee采集箱中有该商品

---

## 三、shopee-collector（Shopee采集箱爬取模块）

### 3.1 模块目标

从Shopee采集箱编辑页爬取商品完整数据

### 3.2 URL参数

| 页面 | fetchType | URL |
|------|-----------|-----|
| Shopee采集箱列表 | `shopeeCopy` | `/common_collect_box/index?fetchType=shopeeCopy` |
| Shopee采集箱编辑 | `shopeeCopy` | `/common_collect_box/edit/{id}?fetchType=shopeeCopy` |

### 3.3 测试用例

#### TC-SC-001: Shopee采集箱商品完整采集

**前置条件：** Shopee采集箱有测试商品

**测试步骤：**
1. 进入Shopee采集箱列表
2. 截图: `tc_sc_001_list.png`
3. 点击目标商品「编辑」
4. 进入编辑页 `/common_collect_box/edit/{id}?fetchType=shopeeCopy`
5. 截图: `tc_sc_001_edit_page.png`
6. 执行爬取函数
7. 截图: `tc_sc_001_output.png`
8. 验证输出

**验证点：**
- [ ] 编辑页面成功打开
- [ ] alibaba_product_id 非空
- [ ] product_title 非空
- [ ] main_images ≥ 1
- [ ] sku_list ≥ 1
- [ ] detail_images ≥ 1

**预期结果:** 所有验证点通过

---

## 四、product-storer（落库模块）

（同v5.0，无需修改）

---

## 五、listing-optimizer（Listing优化模块）

### 5.1 模块目标

生成主商品货号，AI优化标题和描述

### 5.2 成果指标

| 指标 | 目标值 |
|------|--------|
| 主货号格式 | SP-YYYYMMDD-序号 |
| 标题长度 | 30-50字符 |
| 描述长度 | 100-500字符 |
| 优化成功率 | ≥ 95% |

### 5.3 测试用例

#### TC-LO-001: 主货号生成

**验证点：**
- [ ] 货号格式 = SP-YYYYMMDD-序号
- [ ] 序号自动递增

#### TC-LO-002: 标题优化

**验证点：**
- [ ] 输出标题 30-50字符
- [ ] 保留核心品类词

#### TC-LO-003: 描述优化

**验证点：**
- [ ] 输出描述 100-500字符
- [ ] 包含【面料】【规格】【售后】模块

---

## 六、miaoshou-updater（Shopee采集箱回写模块）

### 6.1 模块目标

将主商品货号、优化后的标题/描述回写到Shopee采集箱编辑页

### 6.2 URL

`/common_collect_box/edit/{id}?fetchType=shopeeCopy`

### 6.3 测试用例

#### TC-MU-001: 编辑Shopee采集箱商品

**前置条件：** 商品在Shopee采集箱中

**测试步骤：**
1. 进入Shopee采集箱列表
2. 点击「编辑」
3. 截图: `tc_mu_001_before.png`
4. 填写主商品货号/标题/描述
5. 截图: `tc_mu_001_after.png`
6. 点击保存
7. 截图: `tc_mu_001_success.png`

**验证点：**
- [ ] 编辑页面成功打开
- [ ] 主商品货号正确填写
- [ ] 标题正确填写
- [ ] 描述正确填写
- [ ] 保存成功

**截图要求：**
- `tc_mu_001_before.png` - 填写前
- `tc_mu_001_after.png` - 填写后
- `tc_mu_001_success.png` - 保存成功

**预期结果:** 保存成功，数据持久化

---

## 七、端到端测试

### E2E-001: 全流程采集→优化→编辑

**执行步骤：**

| Step | 页面 | 操作 | 截图 |
|------|------|------|------|
| 1 | 产品采集页面 | 1688链接，点击采集并自动认领 | e2e_001_step1_*.png |
| 2 | Shopee采集箱 | 验证商品在列表中 | e2e_001_step2_*.png |
| 3 | Shopee采集箱编辑页 | 爬取商品数据 | - |
| 4 | 数据库 | 落库 | - |
| 5 | LLM API | 主货号生成+标题+描述优化 | - |
| 6 | Shopee采集箱编辑页 | 填写货号/标题/描述，保存 | e2e_001_step6_*.png |

**最终验证：**
- [ ] products表有记录
- [ ] status = 'optimized'
- [ ] 主商品货号/标题/描述已填写

---

## 八、验收签字栏

| 模块 | 页面 | 目标 | 截图要求 |
|------|------|------|----------|
| miaoshou-collector | 产品采集页面 | 采集发起≥95% | 5张 |
| shopee-collector | Shopee采集箱 | 数据完整率≥95% | 编辑页 |
| miaoshou-updater | Shopee采集箱编辑页 | 回写成功率≥95% | 保存成功 |

---

*文档由 CommerceFlow 自动生成*
*版本：v6.0*
*最后更新：2026-03-20*
