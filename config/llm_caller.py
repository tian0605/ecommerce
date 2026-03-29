"""
LLM调用模块 - 支持Fallback
当主力模型(Doubao)失败时，自动切换到DeepSeek
"""
import requests
import time
from typing import Optional, List, Dict, Any

# 从配置加载
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/config')
from llm_config import LLM_CONFIG, FALLBACK_MODELS

# Doubao Seed API 配置
DOUBAO_API_BASE = 'https://ark.cn-beijing.volces.com/api/v3'
DOUBAO_API_KEY = '05ee7f57-9541-40d1-8021-69a6a81b2c95'

# DeepSeek API 配置
DEEPSEEK_API_BASE = 'https://api.deepseek.com'
DEEPSEEK_API_KEY = LLM_CONFIG['api_key']


def call_doubao(messages: List[Dict], max_tokens: int = 2000, timeout: int = 120) -> Optional[str]:
    """
    调用 Doubao Seed 模型
    使用 /responses API 格式
    """
    try:
        payload = {
            "model": "doubao-seed-2-0-pro-260215",
            "input": [{"role": "user", "content": _convert_to_doubao_format(messages)}],
            "max_output_tokens": max_tokens  # Doubao uses max_output_tokens
        }
        
        response = requests.post(
            f"{DOUBAO_API_BASE}/responses",
            headers={
                "Authorization": f"Bearer {DOUBAO_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=timeout
        )
        
        if response.status_code != 200:
            print(f"[Doubao] API错误: {response.status_code} - {response.text[:200]}")
            return None
        
        result = response.json()
        
        # 提取文本输出
        if 'output' in result:
            for item in result['output']:
                if item.get('type') == 'message':
                    return item['content'][0]['text']
        
        # 检查错误
        if 'error' in result:
            print(f"[Doubao] 返回错误: {result['error']}")
            return None
            
        return None
        
    except requests.exceptions.Timeout:
        print("[Doubao] 调用超时")
        return None
    except Exception as e:
        print(f"[Doubao] 调用异常: {e}")
        return None


def _convert_to_doubao_format(messages: List[Dict]) -> List[Dict]:
    """将OpenAI格式转换为Doubao格式"""
    contents = []
    for msg in messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        
        if isinstance(content, str):
            contents.append({"type": "input_text", "text": content})
        elif isinstance(content, list):
            for item in content:
                if item.get('type') == 'text':
                    contents.append({"type": "input_text", "text": item['text']})
                elif item.get('type') == 'image_url':
                    # Doubao使用 input_image
                    contents.append({"type": "input_image", "image_url": item['image_url']['url']})
    
    return contents


def call_deepseek(messages: List[Dict], max_tokens: int = 2000, timeout: int = 120) -> Optional[str]:
    """
    调用 DeepSeek 模型
    使用 /chat/completions API 格式
    """
    try:
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": LLM_CONFIG.get('temperature', 0.3)
        }
        
        response = requests.post(
            f"{DEEPSEEK_API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=timeout
        )
        
        if response.status_code != 200:
            print(f"[DeepSeek] API错误: {response.status_code} - {response.text[:200]}")
            return None
        
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        
        return None
        
    except requests.exceptions.Timeout:
        print("[DeepSeek] 调用超时")
        return None
    except Exception as e:
        print(f"[DeepSeek] 调用异常: {e}")
        return None


def call_llm_with_fallback(messages: List[Dict], max_tokens: int = 2000, timeout: int = 120) -> Optional[str]:
    """
    调用LLM，支持Fallback
    优先使用Doubao Seed，失败时自动切换到DeepSeek
    """
    primary_model = LLM_CONFIG.get('model', 'doubao-seed-2-0-pro-260215')
    
    print(f"[LLM] 尝试 primary model: {primary_model}")
    
    # 先尝试 Doubao
    if 'doubao' in primary_model.lower():
        result = call_doubao(messages, max_tokens, timeout)
        if result:
            print(f"[LLM] Doubao 成功")
            return result
        
        print(f"[LLM] Doubao 失败，尝试 DeepSeek fallback...")
        # Fallback 到 DeepSeek
        fallback_model = FALLBACK_MODELS.get(primary_model, 'deepseek-chat')
        print(f"[LLM] 使用 fallback model: {fallback_model}")
        result = call_deepseek(messages, max_tokens, timeout)
        if result:
            print(f"[LLM] DeepSeek fallback 成功")
        return result
    else:
        # 非Doubao模型，直接调用
        result = call_deepseek(messages, max_tokens, timeout)
        if result:
            print(f"[LLM] DeepSeek 成功")
        return result


def call_llm(messages: List[Dict], max_tokens: int = 2000, timeout: int = 120) -> Optional[str]:
    """
    标准LLM调用入口（带Fallback）
    """
    return call_llm_with_fallback(messages, max_tokens, timeout)


if __name__ == '__main__':
    # 测试
    print("=" * 50)
    print("测试 call_llm_with_fallback")
    print("=" * 50)
    
    messages = [{"role": "user", "content": "说一声你好，不需要多余的话"}]
    
    result = call_llm_with_fallback(messages, max_tokens=50)
    print(f"结果: {result}")
