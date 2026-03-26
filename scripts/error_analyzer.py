#!/usr/bin/env python3
"""
LLM错误分析器
当子任务重试3次失败后，调用LLM分析错误并提出解决方案
"""
import requests
import json
from typing import Dict, List, Optional

LLM_CONFIG = {
    'api_key': 'sk-914c1a9a5f054ab4939464389b5b791f',
    'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'model': 'qwen3.5-plus'
}

SYSTEM_PROMPT = """你是一个电商运营自动化系统的错误分析专家。
当任务失败时，你需要分析错误信息并提出具体的修复方案。

输出格式要求：
1. 错误根因分析（简明扼要）
2. 修复步骤（具体可执行）
3. 验证方法（如何确认修复成功）

请用中文回答。"""

USER_TEMPLATE = """任务信息：
- 任务名：{task_name}
- 任务描述：{description}
- 错误信息：{error}
- 已尝试的修复：{fix_suggestion}

请分析错误并提出解决方案。"""


def analyze_error(task_info: Dict, error: str) -> Optional[Dict]:
    """
    调用LLM分析错误并返回解决方案
    
    Returns:
        {
            'root_cause': str,      # 根因分析
            'solution_steps': List,  # 修复步骤
            'verification': str,     # 验证方法
            'code_fix': str         # 代码修改建议（如果有）
        }
    """
    task_name = task_info.get('task_name', '')
    description = task_info.get('description', '')
    fix_suggestion = task_info.get('fix_suggestion', '')
    
    user_prompt = USER_TEMPLATE.format(
        task_name=task_name,
        description=description or '无',
        error=error,
        fix_suggestion=fix_suggestion or '无'
    )
    
    try:
        response = requests.post(
            f"{LLM_CONFIG['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_CONFIG['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": LLM_CONFIG['model'],
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 1500,
                "temperature": 0.3
            },
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"LLM API error: {response.status_code} - {response.text}")
            return None
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # 解析LLM返回的内容
        return parse_llm_response(content)
        
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return None


def parse_llm_response(content: str) -> Dict:
    """解析LLM返回的解决方案"""
    result = {
        'root_cause': '',
        'solution_steps': [],
        'verification': '',
        'code_fix': ''
    }
    
    lines = content.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if '根因' in line or '原因' in line:
            current_section = 'root_cause'
        elif '修复' in line or '步骤' in line or '方案' in line:
            current_section = 'solution_steps'
        elif '验证' in line:
            current_section = 'verification'
        elif '代码' in line or '修改' in line:
            current_section = 'code_fix'
        elif line and current_section:
            if current_section == 'root_cause':
                result['root_cause'] += line + ' '
            elif current_section == 'solution_steps':
                if line.startswith('-') or line.startswith('•') or line[0].isdigit():
                    result['solution_steps'].append(line.lstrip('-•0123456789. '))
                elif result['solution_steps']:
                    result['solution_steps'][-1] += ' ' + line
            elif current_section == 'verification':
                result['verification'] += line + ' '
            elif current_section == 'code_fix':
                result['code_fix'] += line + '\n'
    
    # 清理
    result['root_cause'] = result['root_cause'].strip()
    result['verification'] = result['verification'].strip()
    result['code_fix'] = result['code_fix'].strip()
    result['solution_steps'] = [s.strip() for s in result['solution_steps'] if s.strip()]
    
    return result


def create_solution_task_name(parent_id: str, original_task: str) -> str:
    """生成解决方案子任务的名称"""
    import datetime
    ts = datetime.datetime.now().strftime('%H%M%S')
    return f"SOL-{parent_id}-{ts}"


if __name__ == '__main__':
    # 测试
    test_task = {
        'task_name': 'FIX-TC-FLOW-001-001',
        'description': '修复Step4落库失败',
        'fix_suggestion': '检查import路径'
    }
    test_error = "ModuleNotFoundError: No module named 'shared'"
    
    print("测试LLM错误分析...")
    result = analyze_error(test_task, test_error)
    
    if result:
        print(f"\n✅ 根因分析: {result['root_cause']}")
        print(f"\n修复步骤:")
        for i, step in enumerate(result['solution_steps'], 1):
            print(f"  {i}. {step}")
        print(f"\n验证方法: {result['verification']}")
    else:
        print("❌ LLM分析失败")
