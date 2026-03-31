---
name: mem0-memory
description: "mem0 本地记忆层完整实现（增强版）。基于10维触发场景体系，智能存储/检索/管理用户记忆。WAL 协议，SESSION-STATE，多级记忆（User/Session/Agent）。使用 Ollama qwen2.5:1.5b 作为LLM，Ollama nomic-embed-text 作为embedder。"
metadata:
  version: 2.2.0
---

# mem0 Memory 🧠 — 增强版（10维触发体系）

## 组件配置

| 组件 | 技术 | 配置 |
|------|------|------|
| LLM | Ollama `qwen2.5:1.5b` | localhost:11434 |
| Embedder | Ollama `nomic-embed-text` | localhost:11434 |
| 向量库 | Chroma | /root/.mem0/chroma_db |
| User ID | e-commerce | agent标识 |

## 文件路径

- **数据目录**: `/root/.mem0/`
- **Chroma DB**: `/root/.mem0/chroma_db/`
- **Wrapper脚本**: `skills/mem0-memory/scripts/mem0_wrapper.py`
- **触发引擎**: `skills/mem0-memory/scripts/trigger_engine.py`

---

## 核心架构：10维触发体系

### 存储类型分类

| 存储类型 | 说明 | 适用场景 |
|---------|------|---------|
| **mem0 add** | 长期语义记忆 | 偏好、价值观、习惯、能力边界 |
| **SESSION-STATE** | 会话级临时状态 | 目标、约束、进度、情绪、反馈 |

### 触发维度体系

#### 1️⃣ 深度认知维度
| 触发类型 | 触发模式 | 存储 |
|---------|---------|------|
| 习惯模式 | "我通常..." / "我的习惯是..." / "我每次都..." | mem0 add |
| 价值观 | "我觉得最重要..." / "我重视..." / "我不喜欢..." | mem0 add |
| 能力边界 | "我不擅长..." / "我需要学习..." | mem0 add |

#### 2️⃣ 任务执行维度
| 触发类型 | 触发模式 | 存储 |
|---------|---------|------|
| 目标设定 | "我的目标是..." / "我想要达成..." | SESSION-STATE + mem0 |
| 任务约束 | "必须在...之前完成" / "预算是..." | SESSION-STATE |
| 进度状态 | "我已经完成了..." / "下一步是..." | SESSION-STATE |

#### 3️⃣ 交互协作维度
| 触发类型 | 触发模式 | 存储 |
|---------|---------|------|
| 协作偏好 | "请按照..." / "我更倾向于..." | mem0 add |
| 质量标准 | "我要求..." / "标准是..." | SESSION-STATE + mem0 |
| 反馈机制 | "这里需要改进..." / "很好就这样..." | SESSION-STATE + mem0 |

#### 4️⃣ 上下文理解维度
| 触发类型 | 触发模式 | 存储 |
|---------|---------|------|
| 语境关联 | "就像..." / "基于之前的..." | SESSION-STATE |
| 领域知识 | "在...领域..." / "根据...理论..." | mem0 add |
| 文化背景 | "在中国..." / "按照我们的习惯..." | mem0 add |

#### 5️⃣ 情感情绪维度
| 触发类型 | 触发模式 | 存储 |
|---------|---------|------|
| 情绪状态 | "我感到..." / "让我..." | SESSION-STATE |
| 压力因素 | "时间很紧..." / "担心..." | SESSION-STATE |
| 激励因素 | "这对我很重要..." / "为了..." | mem0 add |

#### 6️⃣ 创意创新维度
| 触发类型 | 触发模式 | 存储 |
|---------|---------|------|
| 创意偏好 | "要有创意..." / "让我惊喜..." | mem0 add |
| 风险承受 | "可以大胆一点..." / "保守一点..." | mem0 add |
| 灵感来源 | "参考..." / "受...启发..." | mem0 add |

#### 7️⃣ 学习成长维度
| 触发类型 | 触发模式 | 存储 |
|---------|---------|------|
| 学习目标 | "我想学会..." / "帮我学习..." | SESSION-STATE + mem0 |
| 理解程度 | "我不太明白..." / "能解释一下..." | SESSION-STATE |
| 学习风格 | "我喜欢..." / "一步一步..." | mem0 add |

#### 8️⃣ 社交关系维度
| 触发类型 | 触发模式 | 存储 |
|---------|---------|------|
| 人际关系 | "我的..." / "我和..." | mem0 add |
| 沟通对象 | "告诉..." / "对...说..." | SESSION-STATE |
| 社会角色 | "作为..." / "我的职位是..." | mem0 add |

#### 9️⃣ 决策辅助维度
| 触发类型 | 触发模式 | 存储 |
|---------|---------|------|
| 决策标准 | "最重要的是..." / "关键因素是..." | mem0 add |
| 选择困难 | "不知道选哪个..." / "帮我决定..." | SESSION-STATE + mem0 |
| 后果考虑 | "如果..." / "我担心..." | SESSION-STATE |

#### 🔟 健康生活维度
| 触发类型 | 触发模式 | 存储 |
|---------|---------|------|
| 生活作息 | "我通常...点起床" / "我每天..." | mem0 add |
| 健康状况 | "我有..." / "医生说..." | 敏感-判断后存储 |
| 饮食运动 | "我不吃..." / "我每天运动..." | mem0 add |

---

## API 命令

```bash
# 添加记忆（自动识别触发类型）
python skills/mem0-memory/scripts/mem0_wrapper.py add <user_id> "<内容>"

# 语义搜索（快）
python skills/mem0-memory/scripts/mem0_wrapper.py search <user_id> "<query>" [--limit 5]

# 全部记忆
python skills/mem0-memory/scripts/mem0_wrapper.py get_all <user_id>

# 检索+生成回答
python skills/mem0-memory/scripts/mem0_wrapper.py chat <user_id> "<问题>" [--limit 5]
```

## 当前实现说明

- `add` 会先走触发引擎：
  - `mem0_add`：只写 mem0 长期记忆
  - `session_state`：只写 `SESSION-STATE.md`
  - `both`：同时写 mem0 和 `SESSION-STATE.md`
- mem0 写入使用 `infer=False`，默认保留原文，不再让 LLM 擅自改写成失真的“事实”
- wrapper 兼容当前 mem0 返回结构：`add/search/get_all` 解析 `results[].memory`
- wrapper 会优先检查 Ollama，必要时尝试自动拉起 `ollama serve`
- LLM 模型优先 `qwen2.5:1.5b`，缺失时回退 `qwen2.5:latest`

---

## WAL 协议（触发必做）

### 收到消息时 → 自动扫描

```
扫描触发类型
  ├─ [习惯/价值观/能力] → mem0 add
  ├─ [目标/约束/进度] → SESSION-STATE + mem0
  ├─ [偏好/标准/反馈] → SESSION-STATE + mem0
  ├─ [情绪/压力] → SESSION-STATE
  ├─ [偏好/创意/风险] → mem0 add
  ├─ [学习/理解] → SESSION-STATE + mem0
  ├─ [关系/角色] → mem0 add
  ├─ [决策/后果] → SESSION-STATE + mem0
  └─ [健康/作息] → mem0 add（敏感判断）
回复用户
```

### 回复后
```
上下文使用率 > 60%？
  └─ 是 → WORKING-BUFFER.md 激活
```

---

## 智能优先级

| 优先级 | 类型 | 说明 |
|--------|------|------|
| P0 | 目标/约束/进度 | 当前任务关键状态 |
| P1 | 偏好/标准/反馈 | 影响协作质量 |
| P2 | 习惯/价值观/能力 | 长期认知积累 |
| P3 | 创意/风险/灵感 | 可延迟处理 |

---

## 前置条件

- [x] Ollama 运行中
- [x] qwen2.5:1.5b 已安装
- [x] nomic-embed-text:latest 已安装
- [x] Chroma 数据库已初始化
- [x] mem0ai 包已安装

## 注意事项

- **添加记忆较慢**：需LLM处理（10-20秒）
- **搜索很快**：仅embedder（毫秒级）
- **隐私保护**：敏感信息需用户确认
- User ID: `e-commerce`
- 如果 OpenClaw 主运行时未识别该技能，需要同时安装到 `/home/ubuntu/.openclaw/skills/mem0-memory/`
