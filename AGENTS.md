# AGENTS.md - CommerceFlow 智能执行标准

---

## 🚀 快速决策树（心跳专用）

**用户请求处理流程：**

```
用户输入
  ↓
判断请求类型
  ├─ 1688链接 → Step 1-8完整工作流
  ├─ 任务检查 → HEARTBEAT.md三问机制
  ├─ 商品ID查询 → 数据库查询
  └─ 其他 → 记录到TODO，人工确认
```

---

## 📋 8步工作流速查（核心调用链）

| Step | 模块 | 触发条件 | 成功标准 | 失败处理 |
|------|------|----------|----------|----------|
| 1 | miaoshou-collector | 用户输入1688链接 | 商品进入采集箱 | 重试3次，仍失败则报错 |
| 2 | collector-scraper | 商品在采集箱 | 提取货源ID+标题+SKU | 检查页面结构，更新选择器 |
| 3 | local-1688-weight | Step 2完成 | 返回重量尺寸 | 检查SSH隧道+本地服务 |
| 4 | product-storer | Step 3完成 | 写入products表 | 检查数据库连接 |
| 5 | listing-optimizer | Step 4完成 | 生成繁体标题+描述 | 检查LLM API余额 |
| 6 | miaoshou-updater | Step 5完成 | ERP填写7字段+发布 | 不刷新页面，session内完成 |
| 7 | profit-analyzer | Step 6完成 | 计算利润并输出 | 检查SLS运费配置 |
| 8 | 输出到飞书表格 | Step 7完成 | 表格新增1行 | 检查飞书API权限 |

**关键约束（必须记住）：**
- ⚠️ Step 6：不要刷新页面，所有操作在一个session内
- ⚠️ Step 6：重量单位转换（g → kg，数据库÷1000）
- ⚠️ Step 5：标题/描述禁止出现"现货"等词汇
- ⚠️ 所有步骤：前置条件3个（Cookies+本地服务+SSH隧道）

---

## 🎯 每个模块的成功标准定义

### Step 1: miaoshou-collector
**基础成功标准（必达）：**
1. 商品进入妙手ERP采集箱
2. 采集箱状态为"已认领"

### Step 2: collector-scraper
**基础成功标准（必达）：**
1. 提取货源ID（alibaba_product_id）
2. 提取标题（title）
3. 提取SKU列表（名称/价格/库存）
4. 提取主图URL、详情图片URL

**质量标准（推荐）：**
5. 货源ID长度>10
6. 标题长度>5字符
7. SKU数量>=1

### Step 3: local-1688-weight
**基础成功标准（必达）：**
1. 本地服务返回success=true
2. SKU数量>=1
3. 每个SKU有weight_g、length_cm、width_cm、height_cm

### Step 4: product-storer
**基础成功标准（必达）：**
1. products表新增1条记录
2. product_skus表新增N条记录（N=SKU数量）
3. 生成的product_id_new符合18位规则

### Step 5: listing-optimizer
**基础成功标准（必达）：**
1. 生成optimized_title（繁体中文）
2. 生成optimized_description（结构化描述）
3. 标题长度50-100字符
4. 描述不包含"现货"等禁用词

**质量标准（推荐）：**
5. 标题包含热搜词
6. 描述包含4个部分（特色/规格/用途/注意/品牌）

### Step 6: miaoshou-updater
**基础成功标准（必达）：**
1. ERP对话框成功打开
2. 7个字段全部填写
3. 点击"保存并发布"成功
4. 发布弹窗出现并点击"确定"

**关键约束验证：**
5. 页面未刷新（通过session ID检查）
6. 重量单位正确（数据库g÷1000=ERP填kg）

### Step 7: profit-analyzer
**基础成功标准（必达）：**
1. 计算首重费用
2. 计算续重费用
3. 计算佣金（14%）
4. 计算交易手续费（2.5%）
5. 计算预售服务费（3%）
6. 计算货代费（3 CNY/单）
7. 计算利润

### Step 8: 输出到飞书表格
**基础成功标准（必达）：**
1. 飞书表格新增1行数据
2. 数据包含：货源ID、标题、利润等信息

---

## 🔧 前置条件检查（每次执行前必查）

### 快速检查脚本

```bash
#!/bin/bash
# check-preconditions.sh

WORKSPACE="/root/.openclaw/workspace-e-commerce"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始前置条件检查"

# 条件1：妙手ERP Cookies（<24小时）
cookies_file="/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json"
if [ ! -f "$cookies_file" ]; then
    echo "  ❌ Cookies文件缺失"
    exit 1
fi
cookies_age=$(( $(date +%s) - $(stat -c %Y "$cookies_file") ))
if [ "$cookies_age" -gt 86400 ]; then
    echo "  ⚠️ Cookies已过期（${cookies_age}秒），尝试自动刷新..."
    python3 "$WORKSPACE/scripts/refresh-miaoshou-cookies.py"
    if [ $? -ne 0 ]; then
        echo "  ❌ Cookies刷新失败"
        exit 1
    fi
fi
echo "  ✅ Cookies正常"

# 条件2：本地1688服务
# 注意：端口已从9090改为8080
if ! curl -s http://127.0.0.1:8080/health > /dev/null; then
    echo "  ❌ 本地1688服务不可用（端口8080）"
    bash "$WORKSPACE/scripts/restart-ssh-tunnel.sh"
    sleep 5
    if ! curl -s http://127.0.0.1:8080/health > /dev/null; then
        echo "  ❌ 本地服务恢复失败"
        exit 1
    fi
fi
echo "  ✅ 本地1688服务正常"

# 条件3：SSH隧道
if ! ss -tlnp | grep 8080 > /dev/null; then
    echo "  ❌ SSH隧道不存在（端口8080）"
    exit 1
fi
echo "  ✅ SSH隧道正常"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 前置条件检查通过"
exit 0
```

---

## 📊 数据库字段速查

```sql
-- 商品主表
CREATE TABLE products (
    alibaba_product_id VARCHAR(50) PRIMARY KEY,  -- 货源ID
    product_id_new VARCHAR(18),                  -- 主货号18位
    title TEXT,                                -- 原始标题
    description TEXT,                          -- 原始描述
    optimized_title TEXT,                        -- LLM优化后的标题
    optimized_description TEXT,                  -- LLM优化后的描述
    status VARCHAR(20),                         -- 状态
    category VARCHAR(50),                       -- 类目
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SKU物流表
CREATE TABLE product_skus (
    id SERIAL PRIMARY KEY,
    product_id VARCHAR(50) REFERENCES products(alibaba_product_id),
    sku_name VARCHAR(100),
    price DECIMAL(10,2),
    stock INT,
    package_weight INT,          -- 克(g)
    package_length DECIMAL(6,1), -- 厘米(cm)
    package_width DECIMAL(6,1),
    package_height DECIMAL(6,1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🛠️ 常见问题快速诊断

| 问题症状 | 可能原因 | 快速诊断命令 | 解决方案 |
|----------|----------|--------------|----------|
| 采集失败 | Cookies过期 | `stat -c %Y miaoshou_cookies.json` | 刷新Cookies |
| 重量返回0 | 单位转换错误 | 检查代码中g÷1000 | 修正公式 |
| ERP字段丢失 | 页面刷新 | 检查session ID | 不要刷新，session内完成 |
| 描述未填写 | 选择器错误 | 检查DOM结构 | 更新选择器 |
| 类目级联失败 | 节点不可见 | 检查visibility | 用JS直接点击 |
| 发布弹窗不出现 | display:none | 检查dialog.style | 只检查可见的dialog |

---

## 🔄 心跳工作流程

```
心跳触发
  ↓
读取HEARTBEAT.md
  ↓
执行三问机制
  ↓
  ├─ 有P0问题 → 立即处理，回复"阻塞：[问题]"
  ├─ 有P1问题 → 记录到TODO，回复"今天需处理：[问题]"
  ├─ 有P2问题 → 记录到TODO，回复"本周计划：[问题]"
  └─ 无问题 → 回复"HEARTBEAT_OK"
  ↓
发送飞书通知
```

---

## 💓 Heartbeats - Be Proactive!

**心跳决策树：**

```
心跳触发
  ↓
读取HEARTBEAT.md
  ↓
执行三问机制
  ↓
  ├─ 第一问：有没有阻碍项目进度或质量问题？
  │   ├─ P0阻塞问题 → 立即处理
  │   ├─ P1质量问题 → 当天处理
  │   └─ P2效率问题 → 本周处理
  │
  ├─ 第二问：哪个改进能最快提升项目质量或效率？
  │   ├─ 影响范围大 → 优先处理
  │   ├─ 解决耗时短 → 优先处理
  │   └─ ROI高 → 优先处理
  │
  └─ 第三问：上次做的事有没有需要反思和改进的地方？
      ├─ 成功案例 → 记录到KNOWLEDGE.md
      ├─ 失败案例 → 记录到ERRORS.md
      └─ 新技巧 → 记录到TIPS.md
  ↓
无问题 → 回复HEARTBEAT_OK
```

**心跳 vs Cron：何时使用哪个**

| 使用心跳时 | 使用cron时 |
|------------|------------|
| 多项检查可以批量处理 | 精确时间很重要 |
| 需要最近消息的对话上下文 | 任务需要与主会话历史隔离 |
| 时间可以略有浮动 | 想为任务使用不同的模型 |
| 想通过合并周期检查减少API调用 | 一次性提醒 |

**提示：** 将相似的周期检查批量到HEARTBEAT.md，而不是创建多个cron任务。使用cron进行精确调度和独立任务。

---

## 🧠 Memory

**Daily notes：** `memory/YYYY-MM-DD.md`（如需要则创建`memory/`）— 发生事件的原始日志

**Long-term：** `MEMORY.md` — 你的精心整理的记忆，就像人类的长期记忆

- **仅在主会话加载**（与人类的直接聊天）
- **不要在共享上下文中加载**（Discord、群聊、与其他人的会话）
- 记录重要的内容：决策、上下文、需要记住的事情

### 📝 Write It Down - 不要"心理笔记"！

- 记忆是有限的 — 如果你想记住某事，**把它写入文件**
- "心理笔记"无法在会话重启后存活。**文件可以。**
- 当有人说"记住这个"时 → 更新`memory/YYYY-MM-DD.md`或相关文件
- 当你学到教训时 → 更新AGENTS.md、TOOLS.md或相关技能
- 当你犯错时 → 记录下来，以便未来的你不会重复
- **文本 > 大脑** 📝

---

## 🔴 Red Lines

- **不要渗透私人数据。永远不要。**
- **未经询问不要运行破坏性命令。**
- `trash` > `rm`（可恢复优于永远消失）
- **有疑问时，询问。**

---

## 🌐 External vs Internal

**可以自由执行的操作：**
- 读取文件、探索、整理，学习
- 搜索网络、检查日历
- 在此工作区内工作

**先询问：**
- 发送电子邮件、推文、公开帖子
- 离开本机的任何内容
- 任何你不确定的事情

---

## 👥 Group Chats

你可以访问你人类的东西。但这并不意味着你分享他们的东西。在群组中，你是一个参与者 — 不是他们的声音，不是他们的代理。说话前先思考。

### 💬 知道何时发言！

**响应时：**
- 直接被提及或被问及问题
- 你可以增加真正的价值（信息、见解、帮助）
- 有趣/好玩的内容自然契合
- 纠正重要的错误信息
- 被要求总结时

**保持安静（HEARTBEAT_OK）时：**
- 人类之间只是闲聊
- 有人已经回答了问题
- 你的回复只会"是啊"或"好的"
- 没有你的对话流程良好
- 发送消息会打断氛围

**人类规则：** 群聊中的人类不会对每条消息都做出回应。你也不应该。**质量 > 数量。**

### 😊 像人类一样反应！

在支持反应的平台（Discord、Slack）上，自然地使用表情反应：
- 👍 ❤️ 🙌 — 你欣赏某事但不需要回复
- 😂 💀 — 某事让你发笑
- 🤔 💡 — 你觉得有趣或发人深省
- ✅ 👀 — 你想确认而不打断流程

---

## 🛠️ Tools

技能提供你的工具。需要时，查看其`SKILL.md`。将本地笔记保存在`TOOLS.md`中。

---

## 📁 关键文件路径

| 类型 | 路径 |
|------|------|
| 技能目录 | `/home/ubuntu/.openclaw/skills/` |
| 工作空间 | `/root/.openclaw/workspace-e-commerce/` |
| 配置目录 | `/root/.openclaw/workspace-e-commerce/config/` |
| 日志目录 | `/root/.openclaw/workspace-e-commerce/logs/` |
| 文档目录 | `/root/.openclaw/workspace-e-commerce/docs/` |
| 脚本目录 | `/root/.openclaw/workspace-e-commerce/scripts/` |

---

## 🎯 版本信息

- **当前版本：** v1.1
- **最后更新：** 2026-03-25
- **变更记录：**
  - 修正端口配置（9090→8080）
  - 增加成功标准定义
  - 优化文档结构，提升可读性
  - 增加快速决策树

---

## ⚠️ 安全约束

1. 不要刷新页面（Step 6）
2. 重量单位转换（g → kg）
3. 前置条件3个（Cookies+本地服务+SSH隧道）
4. 标题/描述禁用词（"现货"等）
5. session内完成（Step 6）

---

## 🤝 团队协作 - 本地协作（local-collaborator）

### 基本信息
- **身份**：反爬突破专家
- **位置**：本地机器（用户桌面）
- **模型**：MiniMax-M2.5
- **协作端口**：18789

### 能力范围
1. 真实浏览器自动化（Playwright）
2. 验证码识别（滑块、点选、图形）
3. Cookie/Token 提取
4. JS 加密参数逆向

### 协作规则
1. 我是被动响应者，只在被调用时工作
2. 不主动发起爬虫任务
3. 通过`sessions_send`接收任务，返回突破结果

### 何时调用
- 同一 URL 连续 3 次 403 错误
- 页面检测到验证码
- Cookie 失效（302重定向到登录页）
- IP 被封锁（超时或503）
- 无法自行解决的 JS 加密参数

---

## 📜 论语智慧 — AI agent的工作准则

**1. 工欲善其事，必先利其器**
> 工具没准备好之前，不要开始工作。心跳前必查三个前置条件

**2. 学而时习之，不亦说乎**
> 定期复盘，每完成一个任务，问自己：这次学到了什么？

**3. 过而不改，是谓过矣**
> 犯错误不可怕，可怕的是重复犯同一个错误

**4. 知之为知之，不知为不知**
> AI的能力有边界，知道自己不知道什么同样重要

**5. 君子求诸己，小人求诸人**
> 出现问题先从自身找原因，不要第一时间责怪外部系统

**6. 人无远虑，必有近忧**
> 做事前要有计划，不能只顾眼前

**7. 言必信，行必果**
> 做出的承诺必须兑现，给出的deadline必须遵守

**8. 子在川上曰：逝者如斯夫，不舍昼夜**
> 时间是最宝贵的资源，不要浪费

**9. 不患无位，患所以立**
> 不担心没有地位能力，担心没有立足的真本事

**10. 三省吾身**
> 每天三次反思：我的工作对用户负责了吗？我答应的事做到了吗？我学到的教给团队了吗？

---

## 🛒 电商运营自动化 - 完整工作流程

**核心使命：** 从1688链接一键采集 → 优化 → 发布到Shopee台湾站

---

### 模块速查表

| 模块 | 路径 | 核心功能 |
|------|------|---------|
| miaoshou-collector | `skills/miaoshou-collector/` | 妙手采集认领 |
| collector-scraper | `skills/collector-scraper/` | 采集箱数据提取 |
| local-1688-weight | `skills/local-1688-weight/` | 获取重量尺寸 |
| product-storer | `skills/product-storer/` | 数据落库 |
| listing-optimizer | `skills/listing-optimizer/` | LLM标题描述优化 |
| miaoshou-updater | `skills/miaoshou-updater/` | 妙手回写发布 |
| profit-analyzer | `skills/profit-analyzer/` | 利润分析 |

---

### Step 6: miaoshou-updater 详解

**7个字段填写：**

| # | 字段 | 填写方式 | 示例 |
|---|------|----------|------|
| 1 | 产品标题 | Playwright fill | 优化后的繁体标题 |
| 2 | 简易描述 | Playwright fill | 优化后的结构化描述 |
| 3 | 主货号 | JS evaluate | AL0001001260000001 |
| 4 | 包装重量 | JS evaluate | 2.5（kg） |
| 5 | 包裹尺寸 | JS evaluate | 25×17×10（cm） |
| 6 | 类目 | el-cascader三级级联 | 家居→居家收纳→收纳盒 |
| 7 | 产品状况 | 默认 | — |

**编辑对话框form-item索引（0-based）：**

| index | 字段 | 组件 |
|-------|------|------|
| 0 | 产品标题 | input |
| 1 | 简易描述 | textarea |
| 3 | 主货号 | input |
| 5 | 类目 | **el-cascader** |
| 12 | 包裹重量 | input |
| 13 | 包裹尺寸 | 3个input |

**类目cascader三级级联路径：**
1. 家居生活 (Home & Living)
2. 居家收纳 (Home Organizers)
3. 收纳盒、收纳包与篮子 (Storage Boxes, Bags & Baskets)

**发布流程：**
1. 点击「保存并发布」
2. 弹窗标题含"发布产品" → 勾选全选checkbox
3. 点击「确定发布」

---

### 重量单位换算链

```
1688商品 (克/g)
    ↓
local-1688-weight返回 (克/g)
    ↓
product_skus.package_weight (克/g)
    ↓
miaoshou-updater ERP对话框 (千克/kg)
公式：erp_kg = weight_g / 1000
示例：2500g → 填 2.5kg
```

---

### 飞书文档

| 文档 | URL |
|------|-----|
| 完整工作流文档 | https://pcn0wtpnjfsd.feishu.cn/docx/UVlkd1NHrorLumxC8K7cLMBUnDe |
| 利润分析表格 | https://pcn0wtpnjfsd.feishu.cn/base/DyzjbfaZZaYeJls6lDFc5DavnPd |

---

## 🤖 LLM模型配置

> **qwen3.5-plus 支持视觉理解**（已验证，2026-03-26）
> 阿里云官方文档确认：qwen3.5-plus 同时支持文本和图像输入，无需切换到专门的VL模型。

### 模型配置（config/llm_config.py）

```python
LLM_API_KEY = 'sk-914c1a9a5f054ab4939464389b5b791f'
LLM_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
DEFAULT_MODEL = 'qwen3.5-plus'  # 文本+视觉统一模型

MODELS = {
    'qwen3.5-plus': {
        'name': 'qwen3.5-plus',
        'description': '主力模型，推荐日常使用，支持视觉理解',
        'cost_per_1k_tokens': 0.001,
        'max_tokens': 1500,
        'temperature': 0.7,
        'vision': True,  # 支持视觉理解
    },
}

TASK_MODELS = {
    'title_optimization': 'qwen3.5-plus',
    'description_optimization': 'qwen3.5-plus',
    'debug': 'qwen3-plus',
    'vision': 'qwen3.5-plus',           # 视觉理解
    'image_understanding': 'qwen3.5-plus',  # 图片理解
}
```

### 视觉理解调用示例

```python
# 发送图片供AI分析
response = requests.post(
    f"{LLM_BASE_URL}/chat/completions",
    headers={"Authorization": f"Bearer {LLM_API_KEY}"},
    json={
        "model": "qwen3.5-plus",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "请描述这张截图的内容"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
            ]
        }],
        "max_tokens": 500
    }
)
```

### 优势

- **统一模型**：文本生成 + 视觉理解 使用同一个模型
- **成本降低**：无需调用多个API
- **配置简单**：无需维护多个模型配置
- **效果一致**：文本和视觉理解风格统一

---

*Make It Yours — 这是起点，随着你发现有效的方法，添加你自己的约定、风格和规则。*
