# MEMORY.md - CommerceFlow 长期记忆

## 项目状态：自动采集方案 v6（已完成✅）

### 核心成果
**2026-03-22 重大突破**：本地1688服务通过SSH隧道成功绕过IP反爬，获取准确的商品重量和尺寸数据。

---

## 一、完整工作流程（已打通）

```
┌─────────────────────────────────────────────────────────────────┐
│              妙手ERP自动采集认领落库完整流程                       │
└─────────────────────────────────────────────────────────────────┘

[步骤1] 1688商品链接
         │
         ▼
[步骤2] miaoshou-collector（妙手采集）
         │  SSH隧道转发
         │  点击"采集并自动认领"
         ▼
[步骤3] 妙手ERP自动认领
         │  商品进入Shopee采集箱
         ▼
[步骤4] collector-scraper（Shopee采集箱提取）
         │  提取货源ID、标题、SKU、主图
         │  ⚠️ 不提取物流信息
         ▼
[步骤5] 本地1688服务 ⭐前置（获取准确重量/尺寸）
         │  SSH隧道: 127.0.0.1:9090
         │  返回每个SKU的重量(g)和尺寸(cm)
         ▼
[步骤6] product-storer（数据落库）
         │  合并主数据+物流数据
         │  生成主货号
         ▼
[步骤7] listing-optimizer（LLM优化）
         │  繁体中文标题
         │  结构化描述
         ▼
[步骤8] miaoshou-updater（回写妙手）
         │  将优化内容回写到Shopee采集箱
         ▼
[步骤9] profit-analyzer（利润分析）⭐新增
         │  使用本地1688获取的准确重量
         │  计算SLS运费、佣金、利润
         │  输出到飞书表格
         ▼
[完成] 商品已完成全流程
```

---

## 二、模块清单与位置

| 模块 | 路径 | 状态 |
|------|------|------|
| miaoshou-collector | `/home/ubuntu/.openclaw/skills/miaoshou-collector/` | ✅ |
| collector-scraper | `/home/ubuntu/.openclaw/skills/collector-scraper/` | ✅ |
| product-storer | `/home/ubuntu/.openclaw/skills/product-storer/` | ✅ |
| listing-optimizer | `/home/ubuntu/.openclaw/skills/listing-optimizer/` | ✅ |
| miaoshou-updater | `/home/ubuntu/.openclaw/skills/miaoshou-updater/` | ✅ |
| profit-analyzer | `/home/ubuntu/.openclaw/skills/profit-analyzer/` | ✅ |
| local-1688-weight | `/home/ubuntu/.openclaw/skills/local-1688-weight/` | ✅ |
| workflow-runner | `/home/ubuntu/.openclaw/skills/workflow-runner/` | ✅ |

---

## 三、测试用例（已更新）

### 优化后的测试用例
| 用例 | 模块 | 状态 |
|------|------|------|
| TC-MC-001 | 妙手采集认领 | ✅ |
| TC-CS-001 | 采集箱提取（不含物流） | ✅ |
| TC-LW-001 | 本地1688服务（前置） | ✅ |
| TC-PS-001 | 数据落库 | ✅ |
| TC-LO-001 | Listing优化 | ✅ |
| TC-MU-001 | 回写妙手 | ✅ |
| TC-PA-001 | 利润分析 | 🔄 |
| TC-FLOW-001 | 端到端流程 | 🔄 |

**关键变更**：原TC-CS-002（物流提取）已冗余，由TC-LW-001替代并前置。

---

## 四、前置条件（每次工作前必查）

### 三个必要条件

| # | 条件 | 检查方法 | 处理 |
|---|------|----------|------|
| 1 | 妙手ERP已登录 | Cookies文件 <24小时 | 重新导出Cookies |
| 2 | 本地爬虫服务启用 | `curl http://127.0.0.1:9090/health` | 重启本地服务 |
| 3 | SSH隧道打开 | `ss -tlnp \| grep 9090` | 重建MobaXterm隧道 |

### 快速检查
```bash
/root/.openclaw/workspace-e-commerce/scripts/check-preconditions.sh
```

---

## 五、技术架构

### 5.1 SSH隧道配置
```
本地电脑 ──SSH──> 远程服务器(43.139.213.66)
    │
    └── L9090:127.0.0.1:9090 ──> 本地1688服务
```

### 5.2 数据库
- **Host**: localhost
- **Database**: ecommerce_data
- **表**: products

### 5.3 关键URL
| 服务 | URL |
|------|-----|
| 妙手ERP | https://erp.91miaoshou.com |
| 产品采集 | `?fetchType=linkCopy` |
| Shopee采集箱 | `/shopee/collect_box/items` |

### 5.4 技术栈
| 组件 | 技术 |
|------|------|
| 浏览器自动化 | Playwright + Chromium |
| 数据库 | PostgreSQL |
| 远程调用 | HTTP POST + SSH隧道 |
| 图片存储 | 腾讯云COS |

---

## 六、文件配置

### 6.1 Cookies
| 文件 | 位置 | 用途 |
|------|------|------|
| miaoshou_cookies.json | `/home/ubuntu/.openclaw/skills/miaoshou-collector/` | 妙手ERP登录 |
| 1688_cookies.json | 本地 | 1688登录（本地服务） |

### 6.2 数据库配置
- 用户：superuser
- 密码：Admin123!
- 数据库：localhost/ecommerce_data

---

## 七、数据字段

### 7.1 商品主数据
| 字段 | 说明 | 示例 |
|------|------|------|
| 货源ID | 1688商品ID | 1027205078815 |
| 主货号 | 生成唯一编号 | 日式078815 |
| 标题 | 商品标题 | 日式复古风... |
| SKU数 | 规格数量 | 3 |
| 主图数 | 图片数量 | 14 |

### 7.2 物流数据（来自本地1688服务）
| 字段 | 说明 | 单位 |
|------|------|------|
| weight_g | 商品重量 | 克(g) |
| length_cm | 长度 | 厘米(cm) |
| width_cm | 宽度 | 厘米(cm) |
| height_cm | 高度 | 厘米(cm) |

### 7.4 利润分析数据（profit-analyzer）
| 字段 | 说明 | 单位 |
|------|------|------|
| 采购价CNY | 1688采购价格 | 元(CNY) |
| 重量G | 商品重量 | 克(g) |
| 采购费CNY | 采购价+货代费 | 元(CNY) |
| 货代费CNY | 货代费用 | 元(CNY) |
| SLS运费TWD | Shopee物流运费 | 新台币(TWD) |
| SLS运费CNY | SLS运费折算 | 元(CNY) |
| 佣金TWD | Shopee佣金(14%) | 新台币(TWD) |
| 总成本CNY | 所有成本合计 | 元(CNY) |
| 建议售价TWD | 目标利润率20% | 新台币(TWD) |
| 预估利润CNY | 预计利润 | 元(CNY) |
| 利润率 | 利润率 | % |
| 包装尺寸CM | 长x宽x高 | cm |

### 7.5 利润分析飞书表格
| 项目 | 值 |
|------|-----|
| URL | https://pcn0wtpnjfsd.feishu.cn/base/DyzjbfaZZaYeJls6lDFc5DavnPd |
| app_token | DyzjbfaZZaYZaYeJls6lDFc5DavnPd |
| 字段数 | 27个 |

### 7.3 本地1688服务返回格式
```json
{
  "success": true,
  "sku_count": 3,
  "sku_list": [
    {
      "sku_name": "深棕色-大号35*25*16cm",
      "weight_g": 627,
      "length_cm": 32.5,
      "width_cm": 23.5,
      "height_cm": 16.5
    }
  ]
}
```

---

## 八、飞书文档

| 文档 | URL |
|------|-----|
| 工作总结与流程说明 | https://feishu.cn/docx/IoaYdHbzLo6qoaxsO1Fcb8dTnmf |
| 测试用例 | https://feishu.cn/docx/JZYLdZW9KosigExQCogcccBinUc |
| 测试报告 | https://feishu.cn/docx/PcuKdyO85oMTroxlYCScssHan5f |
| 本地1688服务方案 | https://feishu.cn/docx/LQFrd9tmBooakkxzYMPca18zn3c |
| 利润分析表格 | https://pcn0wtpnjfsd.feishu.cn/base/DyzjbfaZZaYeJls6lDFc5DavnPd |

---

## 九、已知问题

| 问题 | 状态 | 解决方案 |
|------|------|----------|
| 1688 IP反爬 | ✅ 已解决 | 本地1688服务 |
| 物流信息提取 | ✅ 已解决 | TC-LW-001替代 |
| Playwright线程冲突 | ✅ 已解决 | threaded=False |
| Flask响应超时 | 🔄 监控中 | - |

---

## 十、用户信息

- **用户ID**: ou_c70468659111ff6a4b0d3d234d14ff43
- **飞书群**: oc_cdff9eb5f5c8bd8151d20a17be309c23
- **时区**: Asia/Shanghai

## 十一、下一步优化方向

1. **数据整合**：将本地1688重量数据合并到product-storer流程
2. **利润计算**：使用准确重量计算SLS运费
3. **profit-analyzer整合**：将本地1688重量数据传入利润分析模块
4. **自动化**：完善端到端一键执行
5. **监控**：心跳监控和告警

---

## 十二、Shopee台湾SLS运费配置

### 费率配置
| 项目 | 费率 |
|------|------|
| 首重500g | 70 TWD |
| 续重每500g | 30 TWD |
| 买家实付(普通) | 55 TWD |
| 买家实付(满299) | 30 TWD |
| 买家实付(满490) | 0 TWD |

### 平台费率
| 项目 | 费率 |
|------|------|
| 佣金 | 14% |
| 交易手续费 | 2.5% |
| 预售服务费 | 3% |
| 货代费 | 3 CNY/单 |

### 计算公式
- 藏价 = 卖家实付 - 买家实付
- 总成本 = 采购价 + 货代费 + SLS运费CNY + 佣金
- 建议售价 = 目标利润20%

---

---

## 十三、AgentSkill标准化（2026-03-22新增）

将工作流每个模块固化为标准AgentSkill格式：

```
skill-name/
├── SKILL.md          # YAML frontmatter + 使用说明
├── scripts/          # 可执行脚本
└── references/       # 参考文档
```

**技能列表：**
| 技能 | 路径 | 核心功能 |
|------|------|----------|
| miaoshou-collector | `skills/miaoshou-collector/` | 妙手采集认领 |
| collector-scraper | `skills/collector-scraper/` | 采集箱数据提取 |
| local-1688-weight | `skills/local-1688-weight/` | 本地重量服务 |
| product-storer | `skills/product-storer/` | 数据落库 |
| listing-optimizer | `skills/listing-optimizer/` | LLM优化 |
| miaoshou-updater | `skills/miaoshou-updater/` | 回写妙手 |
| profit-analyzer | `skills/profit-analyzer/` | 利润分析 |
| workflow-runner | `skills/workflow-runner/` | 工作流运行器 |

---

*最后更新: 2026-03-22 21:56*
