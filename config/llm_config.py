# LLM 模型配置文件
# listing-optimizer 模块的模型配置

# API 配置
LLM_API_KEY = 'sk-914c1a9a5f054ab4939464389b5b791f'
LLM_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'

# 可用模型列表
MODELS = {
    # 主力模型（推荐）- 支持视觉理解
    'qwen3.5-plus': {
        'name': 'qwen3.5-plus',
        'description': '主力模型，推荐日常使用，支持视觉理解',
        'cost_per_1k_tokens': 0.001,  # ¥0.001/1K tokens
        'max_tokens': 1500,
        'temperature': 0.7,
        'speed': 'fast',
        'quality': 'high',
        'vision': True,  # 支持视觉理解
    },
    # 高配模型（效果更好但更贵）
    'qwen-plus': {
        'name': 'qwen-plus',
        'description': '高配模型，效果更好但成本较高',
        'cost_per_1k_tokens': 0.004,  # ¥0.004/1K tokens
        'max_tokens': 1500,
        'temperature': 0.7,
        'speed': 'medium',
        'quality': 'higher',
    },
    # 轻量模型（快速调试）
    'qwen3-plus': {
        'name': 'qwen3-plus',
        'description': '轻量模型，速度快，成本低',
        'cost_per_1k_tokens': 0.001,  # ¥0.001/1K tokens
        'max_tokens': 1000,
        'temperature': 0.6,
        'speed': 'very_fast',
        'quality': 'medium',
    },
}

# 默认模型（当前切换为 qwen3.5-plus）
DEFAULT_MODEL = 'qwen3.5-plus'

# 任务类型对应的推荐模型
TASK_MODELS = {
    'title_optimization': 'qwen3.5-plus',  # 标题优化
    'description_optimization': 'qwen3.5-plus',  # 描述优化
    'debug': 'qwen3-plus',  # 快速调试
    'vision': 'qwen3.5-plus',  # 视觉理解（截图分析）
    'image_understanding': 'qwen3.5-plus',  # 图片理解
}
