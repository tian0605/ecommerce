#!/usr/bin/env python3
"""
trigger_engine.py - 10维触发场景引擎

自动识别消息中的记忆触发类型，决定存储位置和优先级
"""
import re
from enum import Enum
from typing import List, Dict, Tuple, Optional


class MemoryType(Enum):
    """记忆类型"""
    MEM0_ADD = "mem0_add"           # 长期语义记忆
    SESSION_STATE = "session_state"  # 会话级临时状态
    BOTH = "both"                   # 两者都需要


class TriggerPriority(Enum):
    """触发优先级"""
    P0 = 0  # 目标/约束/进度 - 当前任务关键
    P1 = 1  # 偏好/标准/反馈 - 影响协作质量
    P2 = 2  # 习惯/价值观/能力 - 长期认知
    P3 = 3  # 创意/风险/灵感 - 可延迟


# 触发模式定义
TRIGGER_PATTERNS = {
    # ===== 1. 深度认知维度 =====
    "习惯模式": {
        "patterns": [
            r"我通常", r"我的习惯是", r"我习惯",
            r"一般来说", r"按我的经验",
            r"我每次都", r"我从来都",
        ],
        "memory_type": MemoryType.MEM0_ADD,
        "priority": TriggerPriority.P2,
        "description": "行为模式、决策习惯"
    },
    "价值观": {
        "patterns": [
            r"我觉得最重要", r"我认为",
            r"对我来说", r"我重视",
            r"我不喜欢", r"我反感",
        ],
        "memory_type": MemoryType.MEM0_ADD,
        "priority": TriggerPriority.P2,
        "description": "价值判断、道德原则"
    },
    "能力边界": {
        "patterns": [
            r"我不擅长", r"我对.*不太了解",
            r"我不熟悉", r"我需要学习",
            r"我在.*方面有困难",
        ],
        "memory_type": MemoryType.MEM0_ADD,
        "priority": TriggerPriority.P2,
        "description": "技能短板、知识盲区"
    },

    # ===== 2. 任务执行维度 =====
    "目标设定": {
        "patterns": [
            r"我的目标是", r"我想要达成",
            r"我希望", r"我计划",
            r"我正在准备", r"我打算",
        ],
        "memory_type": MemoryType.BOTH,
        "priority": TriggerPriority.P0,
        "description": "短期目标、长期规划"
    },
    "任务约束": {
        "patterns": [
            r"必须在.*之前完成", r"限制是",
            r"预算是", r"时间限制",
            r"不能使用", r"避免",
        ],
        "memory_type": MemoryType.SESSION_STATE,
        "priority": TriggerPriority.P0,
        "description": "时间约束、资源限制"
    },
    "进度状态": {
        "patterns": [
            r"我已经完成了", r"目前进展到",
            r"下一步是", r"还剩下",
            r"我卡在", r"遇到的问题是",
        ],
        "memory_type": MemoryType.SESSION_STATE,
        "priority": TriggerPriority.P0,
        "description": "当前进度、阻塞点"
    },

    # ===== 3. 交互协作维度 =====
    "协作偏好": {
        "patterns": [
            r"请按照", r"我建议",
            r"我更倾向于", r"我喜欢这样的方式",
            r"能不能", r"我希望你",
        ],
        "memory_type": MemoryType.MEM0_ADD,
        "priority": TriggerPriority.P1,
        "description": "沟通风格、工作方式"
    },
    "质量标准": {
        "patterns": [
            r"我要求", r"标准是",
            r"必须达到", r"不能低于",
            r"我接受", r"我不满意",
        ],
        "memory_type": MemoryType.BOTH,
        "priority": TriggerPriority.P1,
        "description": "质量要求、验收标准"
    },
    "反馈机制": {
        "patterns": [
            r"这里需要改进", r"我觉得可以更好",
            r"这个方向不对", r"应该这样",
            r"我同意", r"很好?就(这样|办)",
        ],
        "memory_type": MemoryType.BOTH,
        "priority": TriggerPriority.P1,
        "description": "反馈模式、调整建议"
    },

    # ===== 4. 上下文理解维度 =====
    "语境关联": {
        "patterns": [
            r"就像", r"类似于",
            r"参考", r"仿照",
            r"基于之前的", r"延续",
        ],
        "memory_type": MemoryType.SESSION_STATE,
        "priority": TriggerPriority.P1,
        "description": "参考上下文、类比对象"
    },
    "领域知识": {
        "patterns": [
            r"在.*领域", r"从.*角度",
            r"根据.*理论", r"遵循.*原则",
            r"行业标准", r"最佳实践",
        ],
        "memory_type": MemoryType.MEM0_ADD,
        "priority": TriggerPriority.P2,
        "description": "专业领域、行业背景"
    },
    "文化背景": {
        "patterns": [
            r"在中国", r"按照我们的习惯",
            r"考虑到", r"结合",
            r"我们这边", r"本地",
        ],
        "memory_type": MemoryType.MEM0_ADD,
        "priority": TriggerPriority.P3,
        "description": "文化背景、地域特色"
    },

    # ===== 5. 情感情绪维度 =====
    "情绪状态": {
        "patterns": [
            r"我感到", r"我现在",
            r"我有点", r"让我",
            r"这让我", r"因为",
        ],
        "memory_type": MemoryType.SESSION_STATE,
        "priority": TriggerPriority.P1,
        "description": "当前情绪、情感倾向"
    },
    "压力因素": {
        "patterns": [
            r"时间很紧", r"压力很大",
            r"这很紧急", r"我需要尽快",
            r"担心", r"害怕",
        ],
        "memory_type": MemoryType.SESSION_STATE,
        "priority": TriggerPriority.P0,
        "description": "压力水平、紧迫程度"
    },
    "激励因素": {
        "patterns": [
            r"这对我来说很重要", r"为了",
            r"我想要", r"期待",
            r"我最在意",
        ],
        "memory_type": MemoryType.MEM0_ADD,
        "priority": TriggerPriority.P2,
        "description": "激励驱动、成就感来源"
    },

    # ===== 6. 创意创新维度 =====
    "创意偏好": {
        "patterns": [
            r"我想要一个.*的创意", r"给我一个.*的想法",
            r"要有创意", r"不要太常规",
            r"让我惊喜", r"出人意料",
        ],
        "memory_type": MemoryType.MEM0_ADD,
        "priority": TriggerPriority.P3,
        "description": "创意风格、创新偏好"
    },
    "风险承受": {
        "patterns": [
            r"可以大胆一点", r"不怕失败",
            r"保守一点", r"稳妥为好",
            r"试试", r"考虑",
        ],
        "memory_type": MemoryType.MEM0_ADD,
        "priority": TriggerPriority.P3,
        "description": "风险态度、创新意愿"
    },

    # ===== 7. 学习成长维度 =====
    "学习目标": {
        "patterns": [
            r"我想学会", r"我想掌握",
            r"我需要了解", r"我想提升",
            r"帮我学习", r"教我",
        ],
        "memory_type": MemoryType.BOTH,
        "priority": TriggerPriority.P2,
        "description": "学习目标、技能需求"
    },
    "理解程度": {
        "patterns": [
            r"我不太明白", r"能解释一下",
            r"这意味着", r"换句话说",
            r"举个例子", r"具体来说",
        ],
        "memory_type": MemoryType.SESSION_STATE,
        "priority": TriggerPriority.P1,
        "description": "理解水平、认知状态"
    },
    "学习风格": {
        "patterns": [
            r"我喜欢.*学", r"我习惯.*学",
            r"一步一步", r"直接给结果",
            r"详细一点", r"简洁一点",
        ],
        "memory_type": MemoryType.MEM0_ADD,
        "priority": TriggerPriority.P3,
        "description": "学习偏好、理解方式"
    },

    # ===== 8. 社交关系维度 =====
    "人际关系": {
        "patterns": [
            r"我的同事", r"我的朋友",
            r"我和.*关系", r"我们要发给",
            r"帮我回复",
        ],
        "memory_type": MemoryType.MEM0_ADD,
        "priority": TriggerPriority.P2,
        "description": "社交关系、重要他人"
    },
    "社会角色": {
        "patterns": [
            r"作为", r"以.*的身份",
            r"我的职位是", r"我负责",
            r"在.*公司", r"我们行业",
        ],
        "memory_type": MemoryType.MEM0_ADD,
        "priority": TriggerPriority.P2,
        "description": "职业身份、社会角色"
    },

    # ===== 9. 决策辅助维度 =====
    "决策标准": {
        "patterns": [
            r"最重要的是", r"关键因素是",
            r"我更关注", r"我考虑",
            r"权衡", r"比较",
        ],
        "memory_type": MemoryType.MEM0_ADD,
        "priority": TriggerPriority.P1,
        "description": "决策权重、评估标准"
    },
    "选择困难": {
        "patterns": [
            r"不知道选哪个", r"帮我决定",
            r"你觉得", r"给我建议",
            r"比较一下", r"分析一下",
        ],
        "memory_type": MemoryType.BOTH,
        "priority": TriggerPriority.P1,
        "description": "决策状态、犹豫因素"
    },

    # ===== 10. 健康生活维度 =====
    "生活作息": {
        "patterns": [
            r"我通常.*点起床", r"我习惯.*点",
            r"我每天", r"我的作息",
        ],
        "memory_type": MemoryType.MEM0_ADD,
        "priority": TriggerPriority.P3,
        "description": "生活习惯、作息规律"
    },
    "健康状况": {
        "patterns": [
            r"我有.*病", r"我正在.*治疗",
            r"医生说", r"注意",
            r"避免.*食物",
        ],
        "memory_type": MemoryType.MEM0_ADD,  # 敏感信息需判断
        "priority": TriggerPriority.P2,
        "description": "健康状况、医疗需求",
        "sensitive": True  # 敏感标记
    },
}


def analyze_triggers(text: str) -> List[Dict]:
    """
    分析文本中的触发场景
    
    Args:
        text: 用户输入文本
        
    Returns:
        匹配的触发列表，每项包含:
        {
            "type": 触发类型名称,
            "pattern": 匹配到的具体模式,
            "memory_type": MemoryType枚举,
            "priority": TriggerPriority枚举,
            "description": 描述
        }
    """
    triggers = []
    text_lower = text.lower()
    
    for trigger_type, config in TRIGGER_PATTERNS.items():
        for pattern in config["patterns"]:
            if re.search(pattern, text_lower):
                triggers.append({
                    "type": trigger_type,
                    "pattern": pattern,
                    "memory_type": config["memory_type"],
                    "priority": config["priority"],
                    "description": config["description"],
                    "sensitive": config.get("sensitive", False)
                })
                break  # 同类型只匹配一次
    
    # 按优先级排序
    triggers.sort(key=lambda x: x["priority"].value)
    
    return triggers


def decide_storage(text: str) -> Tuple[MemoryType, List[str], TriggerPriority]:
    """
    决定存储策略
    
    Returns:
        (memory_type, descriptions, priority)
    """
    triggers = analyze_triggers(text)
    
    if not triggers:
        # 无触发，返回未知
        return MemoryType.MEM0_ADD, ["未分类信息"], 3
    
    # 收集所有描述
    descriptions = [t["description"] for t in triggers]
    
    # 决定存储类型
    memory_types = set(t["memory_type"] for t in triggers)
    if MemoryType.BOTH in memory_types:
        memory_type = MemoryType.BOTH
    elif MemoryType.SESSION_STATE in memory_types and MemoryType.MEM0_ADD in memory_types:
        memory_type = MemoryType.BOTH
    elif MemoryType.SESSION_STATE in memory_types:
        memory_type = MemoryType.SESSION_STATE
    else:
        memory_type = MemoryType.MEM0_ADD
    
    # 取最高优先级（数值最小的）
    priority = min(t["priority"].value for t in triggers)
    
    return memory_type, descriptions, priority


def format_memory_content(text: str, triggers: List[Dict]) -> str:
    """
    格式化记忆内容，添加上下文标记
    """
    if not triggers:
        return text
    
    # 提取触发类型标签
    types = [t["type"] for t in triggers[:3]]  # 最多3个标签
    type_labels = "/".join(types)
    
    return f"[{type_labels}] {text}"


if __name__ == "__main__":
    # 测试
    test_texts = [
        "我通常每天早上8点起床",
        "我的目标是这周完成这个项目",
        "我不擅长写代码，需要学习Python",
        "我喜欢简洁明了的沟通方式",
        "这个方案我觉得可以更好",
    ]
    
    print("=== 触发引擎测试 ===\n")
    for text in test_texts:
        triggers = analyze_triggers(text)
        memory_type, desc, priority = decide_storage(text)
        formatted = format_memory_content(text, triggers)
        
        print(f"输入: {text}")
        print(f"触发: {[t['type'] for t in triggers]}")
        print(f"存储: {memory_type.value} | 优先级: P{priority}")
        print(f"格式化: {formatted}")
        print()
