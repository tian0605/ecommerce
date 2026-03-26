"""
LLM模型配置
"""
LLM_CONFIG = {
    'api_key': 'sk-914c1a9a5f054ab4939464389b5b791f',
    'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'model': 'qwen3.5-plus',
    'max_tokens': 2000,
    'temperature': 0.3,
    'timeout': 120
}

# 各任务的模型配置
TASK_MODELS = {
    'error_analyzer': 'qwen3.5-plus',
    'subtask_executor': 'qwen3.5-plus',
    'listing_optimizer': 'qwen3.5-plus',
    'profit_analyzer': 'qwen3.5-plus',
}
