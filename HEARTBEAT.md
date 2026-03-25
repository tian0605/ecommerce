# HEARTBEAT.md - CommerceFlow 运营心跳

> **核心原则：** 工欲善其事，必先利其器。配置优先，流程为本。
> **适配框架：** 个人项目质量与效率决策框架 v2.0

---

## 一、三问决策机制（每次心跳必问）

### 第一问：有没有阻碍项目进度或质量的问题？

#### 🔴 P0 阻塞问题（立即处理）

| 检查项 | 检查方法 | 自愈方案 |
|--------|----------|----------|
| 前置条件 | 三个必要条件是否满足 | 见下方配置检查 |
| 模块运行 | collector-scraper是否正常 | 查看最近日志 |
| 数据库连接 | products表是否可访问 | 重连或重启服务 |
| LLM API | qwen-plus是否可用 | 检查余额/切换模型 |

**三个必要条件：**
```bash
# 1. 妙手ERP Cookies
ls -la /home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json

# 2. 本地1688服务
curl http://127.0.0.1:9090/health

# 3. SSH隧道
ss -tlnp | grep 9090
```

#### 🟡 P1 质量问题（当天处理）

| 检查项 | 检查方法 | 阈值 |
|--------|----------|------|
| 代码变更 | git status是否有未提交 | >5个文件 |
| 测试失败 | logs/最近心跳是否有ERROR | 任何ERROR |
| API异常 | LLM调用失败率 | >10% |

#### 🟢 P2 效率问题（本周处理）

| 检查项 | 检查方法 | 阈值 |
|--------|----------|------|
| 重复执行 | 心跳日志是否有重复 | 连续2次 |
| 任务堆积 | 待处理商品数量 | >20个 |
| 流程耗时 | 单次采集耗时 | >5分钟 |

---

### 第二问：哪个改进能最快提升项目质量或效率？

#### 决策矩阵

| 问题类型 | 影响范围 | 解决耗时 | 优先级 |
|----------|----------|----------|--------|
| P0阻塞问题 | 全局 | 30分钟-2小时 | P0 |
| 前置条件失败 | 全局 | 5分钟 | P0 |
| LLM API故障 | 全局 | 10分钟 | P0 |
| 代码误报（刚修复） | 开发效率 | 10分钟 | P1 |
| 流程耗时过长 | 运营效率 | 2小时 | P2 |
| 提示词需要优化 | 商品质量 | 1小时 | P2 |

#### 行动约定

- **P0问题**：立即停止当前工作，专注解决
  - 回复格式：`阻塞：[问题描述]，正在解决中，预计XX分钟`
- **P1问题**：记录到TODO，标记"今天必须完成"
  - 回复格式：`今天需处理：[问题描述]`
- **P2问题**：记录到TODO，标记"本周优化"
  - 回复格式：`本周计划：[问题描述]`
- **无问题**：`HEARTBEAT_OK`

---

### 第三问：上次做的事有没有需要反思和改进的地方？

#### 代码质量反思
- 最近运行的模块是否有ERROR？
- 是否有更好的实现方式？
- 是否引入了新的问题？

#### 效率反思
- 最近完成的任务是否可以更快完成？
- 是否有可以复用的代码模式？
- 是否有可以优化的工具或流程？

#### 知识沉淀
- 如果成功解决问题 → 记录到 `KNOWLEDGE.md`
- 如果遇到失败 → 记录到 `ERRORS.md`
- 如果发现新技巧 → 记录到 `TIPS.md`

#### ⚙️ 配置自检（每周检视）

参考 OpenClaw 配置自检方案，检视以下配置项：

| 配置项 | 检查内容 | 健康标准 |
|--------|----------|----------|
| **Memory 持久化** | MEMORY.md 与 memory/*.md 完整性 | 关键决策有记录 |
| **Knowledge Base** | KNOWLEDGE.md 知识覆盖率 | 有成功案例沉淀 |
| **Errors 错误记录** | ERRORS.md 更新频率 | 问题不重复出现 |
| **IMPROVEMENTS** | 改进清单执行率 | 季度≥5项完成 |
| **PROJECT_STATUS** | 项目状态追踪 | 阻塞问题≤1个 |
| **HEARTBEAT机制** | 心跳误报率 | <5% |

**自检执行：**
```bash
# 每周执行
bash /root/.openclaw/workspace-e-commerce/scripts/config-self-check.sh
```

**自检输出：**
- 更新 `docs/IMPROVEMENTS.md` 待办项
- 更新 `docs/PROJECT_STATUS.md` 阻塞状态
- 生成周报发送到飞书群

---

## 二、自动化检查规则

### 代码健康检查

```bash
# 检查前置条件（三个必要条件）
bash /root/.openclaw/workspace-e-commerce/scripts/check-preconditions.sh

# 检查最近日志是否有ERROR
tail -20 /root/.openclaw/workspace-e-commerce/logs/dev-heartbeat.log | grep -i error

# 检查数据库连接
python3 -c "import psycopg2; conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!'); print('DB OK')"

# 检查LLM API余额
curl -s -H "Authorization: Bearer sk-914c1a9a5f054ab4939464389b5b791f" https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions -d '{"model":"qwen-plus","messages":[{"role":"user","content":"hi"}],"max_tokens":10}' | head -100
```

### 工作流检查

```bash
# 检查待处理商品数量
python3 -c "
import psycopg2
conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
cur = conn.cursor()
cur.execute(\"SELECT COUNT(*) FROM products WHERE status = 'collected'\")
print(f'待处理: {cur.fetchone()[0]} 个商品')
conn.close()
"

# 检查今日采集数量
python3 -c "
import psycopg2
conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
cur = conn.cursor()
cur.execute(\"SELECT COUNT(*) FROM products WHERE created_at > CURRENT_DATE\")
print(f'今日新增: {cur.fetchone()[0]} 个商品')
conn.close()
"
```

---

## 三、常见问题诊断与自愈

### 问题1：心跳重复执行

**诊断：**
```bash
# 检查是否有多个心跳进程
ps aux | grep dev-heartbeat | grep -v grep
```

**自愈：**
```bash
# 杀掉重复进程
pkill -f dev-heartbeat.sh
# 等待10秒后重新启动
sleep 10 && bash /root/.openclaw/workspace-e-commerce/scripts/dev-heartbeat.sh &
```

### 问题2：LLM API调用失败

**诊断：**
```bash
# 检查API响应
curl -s https://dashscope.aliyuncs.com/compatible-mode/v1/models | jq
```

**自愈：**
- 切换到备用模型 `qwen3-plus`
- 或降低 `max_tokens` 减少单次调用量

### 问题3：数据库状态枚举错误

**诊断：**
```bash
python3 -c "
import psycopg2
conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
cur = conn.cursor()
cur.execute(\"SELECT DISTINCT status FROM products\")
print(cur.fetchall())
conn.close()
"
```

**自愈：** 直接用SQL UPDATE而不依赖status字段

### 问题4：前置条件失败

| 条件 | 症状 | 自愈方案 |
|------|------|----------|
| Cookies过期 | 采集返回空 | 重新导出Cookies |
| 本地服务宕机 | curl超时 | 重启服务 |
| SSH隧道断开 | 连接refused | 重建隧道 |

---

## 四、进化优化机制

### 自动优化触发条件

- 连续3次心跳发现相同问题 → 自动升级到P0
- 同类问题发生频率增加 → 自动生成优化任务
- 任务完成时间持续超出预期 → 自动分析瓶颈

### 学习机制

- **成功案例** → 记录模式，形成最佳实践
- **失败案例** → 分析原因，形成避坑指南
- **效率提升** → 总结方法，形成工具模板

### 持续改进

- 每周自动生成《项目健康周报》
- 每月自动生成《技术债务报告》
- 每季度自动生成《效率优化建议》

---

## 五、回复约定

| 情况 | 回复格式 |
|------|----------|
| 所有检查通过 | `HEARTBEAT_OK` |
| P0阻塞问题 | `阻塞：[问题]，正在解决，预计XX分钟` |
| P1今天需处理 | `今天需处理：[问题]` |
| P2本周计划 | `本周计划：[优化项]` |
| 自愈行动 | `自愈：[操作]，原因：[原因]` |

---

## 六、配套文件

| 文件 | 路径 | 用途 |
|------|------|------|
| 项目状态 | `docs/PROJECT_STATUS.md` | 当前阻塞、进行中、已完成 |
| 知识库 | `docs/KNOWLEDGE.md` | 成功案例、技巧 |
| 错误记录 | `docs/ERRORS.md` | 失败教训、避坑指南 |
| 改进清单 | `docs/IMPROVEMENTS.md` | 待评估改进项 |
| 开发任务 | `docs/dev-task-queue.md` | 当前开发任务队列 |

---

## 七、配置升级优先级（基于三问机制）

### 当前P0配置问题（必须立即处理）

| 问题 | 影响 | 解决耗时 | 状态 |
|------|------|----------|------|
| status枚举缺少pending/optimized | listing-optimizer无法更新状态 | 10分钟 | 🔴 需修复 |
| dev-heartbeat误报SKU数量 | 浪费监控资源 | 5分钟 | ✅ 已修复 |

### 当前P1配置问题（今天必须处理）

| 问题 | 影响 | 解决耗时 | 状态 |
|------|------|----------|------|
| 提示词硬编码 | 不便于迭代优化 | 1小时 | ⬜ 待处理 |
| 心跳双进程问题 | 重复执行浪费资源 | 30分钟 | ⬜ 待处理 |

### 当前P2配置问题（本周优化）

| 问题 | 影响 | 解决耗时 | 状态 |
|------|------|----------|------|
| LLM模型较贵 | 成本高 | 30分钟 | ⬜ 可切换qwen3-plus |
| 无监控面板 | 问题发现不及时 | 2小时 | ⬜ 待开发 |

---

*最后更新：2026-03-25 11:08*
*框架来源：个人项目质量与效率决策框架 v2.0*
