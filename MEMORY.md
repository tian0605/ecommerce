# MEMORY.md - CommerceFlow 长期记忆

## 项目状态

### 自动采集方案 v6（新项目）
- **状态**: 🔄 执行中
- **方案版本**: v5.0
- **创建日期**: 2026-03-20

### 技术方案（v6核心变化）

**旧方案问题**: 1688 IP反爬限制

**新方案解决方案**:
- 妙手ERP自带1688采集功能（妙手服务器IP不受限）
- 我们通过Playwright+Chromium直接操作妙手ERP Web界面
- **无需Browser Relay插件**

**已验证**:
- `erp.91miaoshou.com` 返回 HTTP 200，可直接访问

### 模块进度

| 模块 | 状态 | 备注 |
|------|------|------|
| miaoshou-collector | ✅ 已测试通过 | TC-MC-001验证成功 |
| shopee-collector | 🔄 待开发 | Shopee采集箱爬取 |
| product-storer | 🔄 待开发 | - |
| listing-optimizer | 🔄 待开发 | 含主货号生成 |
| miaoshou-updater | 🔄 待开发 | 回写Shopee采集箱 |

### 关键路径
- 技能目录: `/home/ubuntu/.openclaw/skills/`
- 配置文件: `/home/ubuntu/work/config/`
- 工作目录: `/home/ubuntu/work/`
- 进度文件: `/root/.openclaw/workspace-e-commerce/docs/execution-progress-v5.md`

### 技术栈
- Python + Playwright + Chromium（无需Browser Relay）
- PostgreSQL（ecommerce_data数据库）
- 腾讯云COS（tian-cos存储）
- rclone（COS同步工具）

### 妙手ERP页面（正确URL）

| 页面 | 正确URL | 功能 |
|------|---------|------|
| 产品采集 | `?fetchType=linkCopy` | 发起1688采集 |
| **Shopee采集箱** | **`/shopee/collect_box/items`** | 存储已认领商品 |

**重要：Shopee采集箱URL不是 `fetchType=shopeeCopy`，而是 `/shopee/collect_box/items`**

### TC-MC-001 测试通过 ✅
- 1688商品ID: 1027205078815
- 采集验证: 成功出现在Shopee采集箱
- 测试时间: 2026-03-20 12:50

### 已部署模块（历史）
- shared/（logger, db, cos_storage, retry_handler）
- product-collector（1688采集）
- listing-generator（Listing生成）
- product-uploader（素材打包）
- miaoshou-uploader（妙手上专）
- image-reviewer（图片审查）
- shopee-taiwan（利润分析）

## 用户信息
- 用户ID: ou_c70468659111ff6a4b0d3d234d14ff43
- 飞书群: oc_cdff9eb5f5c8bd8151d20a17be309c23
- 时区: Asia/Shanghai

## 运营目标
- 月度盈利目标: ¥20,000（最终）
- 首月目标: ¥1,000（起步）

---

*最后更新: 2026-03-19*
