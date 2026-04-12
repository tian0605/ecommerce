"""
LLM调用模块 - 支持Fallback
当主力模型(Doubao)失败时，自动切换到DeepSeek
"""
import requests
from typing import Optional, List, Dict, Any

# 从配置加载
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/config')
from llm_config import LLM_CONFIG, FALLBACK_MODELS, MODEL_CONFIGS

DOUBAO_CONFIG = MODEL_CONFIGS['doubao-seed-2-0-pro-260215']
DEEPSEEK_CONFIG = MODEL_CONFIGS['deepseek-chat']
DOUBAO_API_BASE = str(DOUBAO_CONFIG['api_base'])
DOUBAO_API_KEY = str(DOUBAO_CONFIG['api_key'])
DEEPSEEK_API_BASE = str(DEEPSEEK_CONFIG['api_base'])
DEEPSEEK_API_KEY = str(DEEPSEEK_CONFIG['api_key'])


def call_doubao_with_meta(messages: List[Dict[str, Any]], max_tokens: int = 2000, timeout: int = 120) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        'text': None,
        'model': 'doubao-seed-2-0-pro-260215',
        'provider': 'doubao',
        'used_fallback': False,
        'success': False,
    }
    try:
        payload: Dict[str, Any] = {
            'model': 'doubao-seed-2-0-pro-260215',
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': LLM_CONFIG.get('temperature', 0.3),
        }

        response = requests.post(
            f"{DOUBAO_API_BASE}/chat/completions",
            headers={
                'Authorization': f'Bearer {DOUBAO_API_KEY}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=timeout,
        )

        if response.status_code != 200:
            print(f"[Doubao] API错误: {response.status_code} - {response.text[:200]}")
            result['error'] = f'status_{response.status_code}'
            return result

        body: Dict[str, Any] = response.json()
        choices = body.get('choices')
        if isinstance(choices, list) and choices:
            message = choices[0].get('message') or {}
            content = message.get('content')
            if isinstance(content, str) and content.strip():
                result['text'] = content
                result['success'] = True
                return result

        if 'error' in body:
            print(f"[Doubao] 返回错误: {body['error']}")
            result['error'] = body['error']
        else:
            result['error'] = 'empty_response'
        return result
    except requests.exceptions.Timeout:
        print('[Doubao] 调用超时')
        result['error'] = 'timeout'
        return result
    except Exception as exc:
        print(f'[Doubao] 调用异常: {exc}')
        result['error'] = str(exc)
        return result


def call_deepseek_with_meta(messages: List[Dict[str, Any]], max_tokens: int = 2000, timeout: int = 120) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        'text': None,
        'model': 'deepseek-chat',
        'provider': 'deepseek',
        'used_fallback': False,
        'success': False,
    }
    try:
        payload: Dict[str, Any] = {
            'model': 'deepseek-chat',
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': LLM_CONFIG.get('temperature', 0.3),
        }

        response = requests.post(
            f"{DEEPSEEK_API_BASE}/chat/completions",
            headers={
                'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=timeout,
        )

        if response.status_code != 200:
            print(f"[DeepSeek] API错误: {response.status_code} - {response.text[:200]}")
            result['error'] = f'status_{response.status_code}'
            return result

        body: Dict[str, Any] = response.json()
        choices = body.get('choices')
        if isinstance(choices, list) and choices:
            message = choices[0].get('message') or {}
            content = message.get('content')
            if isinstance(content, str) and content.strip():
                result['text'] = content
                result['success'] = True
                return result

        result['error'] = 'empty_response'
        return result
    except requests.exceptions.Timeout:
        print('[DeepSeek] 调用超时')
        result['error'] = 'timeout'
        return result
    except Exception as exc:
        print(f'[DeepSeek] 调用异常: {exc}')
        result['error'] = str(exc)
        return result


def call_llm_with_fallback_meta(messages: List[Dict[str, Any]], max_tokens: int = 2000, timeout: int = 120) -> Dict[str, Any]:
    primary_model = str(LLM_CONFIG.get('model', 'doubao-seed-2-0-pro-260215'))
    print(f'[LLM] 尝试 primary model: {primary_model}')

    if 'doubao' in primary_model.lower():
        primary_result = call_doubao_with_meta(messages, max_tokens, timeout)
        if primary_result.get('success'):
            print('[LLM] Doubao 成功')
            return primary_result

        print('[LLM] Doubao 失败，尝试 DeepSeek fallback...')
        fallback_model = str(FALLBACK_MODELS.get(primary_model, 'deepseek-chat'))
        print(f'[LLM] 使用 fallback model: {fallback_model}')
        fallback_result = call_deepseek_with_meta(messages, max_tokens, timeout)
        fallback_result['used_fallback'] = True
        if fallback_result.get('success'):
            print('[LLM] DeepSeek fallback 成功')
        return fallback_result

    result = call_deepseek_with_meta(messages, max_tokens, timeout)
    if result.get('success'):
        print('[LLM] DeepSeek 成功')
    return result


def call_doubao(messages: List[Dict[str, Any]], max_tokens: int = 2000, timeout: int = 120) -> Optional[str]:
    return call_doubao_with_meta(messages, max_tokens=max_tokens, timeout=timeout).get('text')


def call_deepseek(messages: List[Dict[str, Any]], max_tokens: int = 2000, timeout: int = 120) -> Optional[str]:
    return call_deepseek_with_meta(messages, max_tokens=max_tokens, timeout=timeout).get('text')


def call_llm_with_fallback(messages: List[Dict[str, Any]], max_tokens: int = 2000, timeout: int = 120) -> Optional[str]:
    return call_llm_with_fallback_meta(messages, max_tokens=max_tokens, timeout=timeout).get('text')


def call_llm(messages: List[Dict[str, Any]], max_tokens: int = 2000, timeout: int = 120) -> Optional[str]:
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
