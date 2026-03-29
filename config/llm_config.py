"""
LLM模型配置
"""
LLM_CONFIG = {
    'api_key': 'sk-2f2c6f05d33741acb27453a828651323',
    'base_url': 'https://api.deepseek.com',
    'model': 'deepseek-chat',  # 默认使用DeepSeek
    'max_tokens': 2000,
    'temperature': 0.3,
    'timeout': 120
}

# 各任务的模型配置（task_name -> model_name）
TASK_MODELS = {
    'error_analyzer': 'doubao-seed-2-0-pro-260215',
    'subtask_executor': 'doubao-seed-2-0-pro-260215',
    'listing_optimizer': 'deepseek-chat',  # listing优化用DeepSeek（稳定）
    'profit_analyzer': 'doubao-seed-2-0-pro-260215',
}

# 模型配置（model_name -> config）
MODEL_CONFIGS = {
    'doubao-seed-2-0-pro-260215': {
        'max_tokens': 2000,
        'temperature': 0.3,
        'api_base': 'https://ark.cn-beijing.volces.com/api/v3',
        'api_key': '05ee7f57-9541-40d1-8021-69a6a81b2c95',
    },
    'deepseek-chat': {
        'max_tokens': 2000,
        'temperature': 0.3,
        'api_base': 'https://api.deepseek.com',
        'api_key': 'sk-2f2c6f05d33741acb27453a828651323',
    },
}

# Fallback 配置
FALLBACK_MODELS = {
    'doubao-seed-2-0-pro-260215': 'deepseek-chat',  # Doubao失败时切换到DeepSeek
}

# 向后兼容的单独变量导出（供 listing_optimizer 等模块使用）
LLM_API_KEY = LLM_CONFIG['api_key']
LLM_BASE_URL = LLM_CONFIG['base_url']
DEFAULT_MODEL = LLM_CONFIG['model']
MODELS = MODEL_CONFIGS  # 使用模型配置
