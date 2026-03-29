#!/usr/bin/env python3
"""
LLM错误分析器
当子任务重试3次失败后，调用LLM分析错误并提出解决方案
"""
import sys
import requests
from pathlib import Path

# 从配置文件加载
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/config')
from llm_config import LLM_CONFIG
from llm_caller import call_llm_with_fallback  # 使用带Fallback的LLM调用

# 从配置文件加载提示词
PROMPTS_DIR = '/root/.openclaw/workspace-e-commerce/config/prompts'
with open(f'{PROMPTS_DIR}/error_analyzer_system.txt', 'r') as f:
    SYSTEM_PROMPT = f.read()
with open(f'{PROMPTS_DIR}/error_analyzer_user.txt', 'r') as f:
    USER_TEMPLATE = f.read()


def analyze_error(task_info: dict, error: str) -> dict:
    """
    调用LLM分析错误并返回解决方案
    
    Returns:
        {
            'root_cause': str,      # 根因分析
            'solution_steps': list,  # 修复步骤
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
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        content = call_llm_with_fallback(
            messages, 
            max_tokens=LLM_CONFIG.get('max_tokens', 1500),
            timeout=LLM_CONFIG.get('timeout', 60)
        )
        
        if not content:
            print("LLM 调用失败")
            return None
        
        # 解析LLM返回的内容
        return parse_llm_response(content)
        
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return None


def parse_llm_response(content: str) -> dict:
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
