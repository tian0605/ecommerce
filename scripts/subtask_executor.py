#!/usr/bin/env python3
"""
subtask_executor.py - 子任务执行器

AI Agent自愈循环：
1. 分析子任务问题
2. LLM思考方案 (ReAct)
3. 制定计划或直接修复
4. 执行修复
5. 回写结果到tasks表
"""
import sys
import os
import json
import re
import requests
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
SCRIPTS_DIR = WORKSPACE / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

# 从配置文件加载
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/config')
from llm_config import LLM_CONFIG

# 从配置文件加载提示词
PROMPTS_DIR = '/root/.openclaw/workspace-e-commerce/config/prompts'
with open(f'{PROMPTS_DIR}/subtask_executor_system.txt', 'r') as f:
    SYSTEM_PROMPT = f.read()

SUBTASK_USER_TEMPLATE = """任务信息：
- 任务名：{task_name}
- 任务描述：{description}
- 错误信息：{error}
- 修复建议：{fix_suggestion}

请分析并输出修复代码。"""

from task_manager import TaskManager
from logger import get_logger


def call_llm(messages: list, max_tokens: int = 2000) -> str:
    """调用LLM"""
    try:
        response = requests.post(
            f"{LLM_CONFIG['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_CONFIG['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": LLM_CONFIG['model'],
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": LLM_CONFIG.get('temperature', 0.3)
            },
            timeout=LLM_CONFIG.get('timeout', 120)
        )
        
        if response.status_code != 200:
            print(f"LLM API error: {response.status_code} - {response.text}")
            return None
        
        result = response.json()
        return result['choices'][0]['message']['content']
        
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return None


def parse_fix_response(content: str) -> dict:
    """解析LLM返回的修复代码"""
    result = {
        'analysis': '',
        'code_fix': ''
    }
    
    if not content:
        return result
    
    # 提取分析部分
    if '【分析】' in content:
        analysis = content.split('【分析】')[1].split('【修复代码】')[0].strip()
        result['analysis'] = analysis
    
    # 提取代码部分
    if '【修复代码】' in content:
        code = content.split('【修复代码】')[1].strip()
        # 去除markdown代码块标记
        if code.startswith('```'):
            code = code.split('\n', 1)[1]
        if '```' in code:
            code = code.split('```')[0]
        result['code_fix'] = code.strip()
    
    return result


def execute_fix_code(code: str, task_name: str) -> tuple:
    """执行修复代码，并持久化到文件"""
    if not code:
        return False, "没有修复代码"
    
    try:
        # 1. 持久化代码到文件
        fixes_dir = Path('/root/.openclaw/workspace-e-commerce/scripts/fixes')
        fixes_dir.mkdir(exist_ok=True)
        
        # 生成文件名：fix_{task_name}.py
        safe_name = task_name.replace('-', '_').replace(':', '_')
        fix_file = fixes_dir / f'fix_{safe_name}.py'
        
        # 写入文件（包含执行入口）
        with open(fix_file, 'w') as f:
            f.write(code)
            f.write(f'\n# 执行入口：apply_fix()\n')
            f.write('def apply_fix():\n')
            f.write('    pass  # 入口函数\n')
        
        print(f"修复代码已持久化: {fix_file}")
        
        # 2. 加载并执行
        exec_globals = {'__name__': '__fix__', 'fix_file': str(fix_file)}
        exec_locals = {}
        
        # 先加载持久化的代码
        with open(fix_file, 'r') as f:
            fix_code = f.read()
        
        # 执行代码
        exec(fix_code, exec_globals, exec_locals)
        
        return True, f"修复代码执行成功 (已持久化到 {fix_file})"
        
    except Exception as e:
        return False, f"执行错误: {str(e)}"


def main(task_name: str):
    """主函数"""
    log = get_logger('subtask')
    log.set_task(task_name).set_message(f"开始执行子任务: {task_name}").finish("running")
    
    tm = TaskManager()
    
    # 获取任务信息
    task = tm.get_task(task_name)
    if not task:
        print(f"任务不存在: {task_name}")
        return
    
    description = task.get('description', '')
    fix_suggestion = task.get('fix_suggestion', '')
    last_error = task.get('last_error', '')
    
    print(f"任务: {task_name}")
    print(f"描述: {description}")
    print(f"错误: {last_error}")
    
    # 构建prompt
    user_prompt = SUBTASK_USER_TEMPLATE.format(
        task_name=task_name,
        description=description or '无',
        error=last_error or '无',
        fix_suggestion=fix_suggestion or '无'
    )
    
    # 调用LLM
    print("\n调用LLM分析...")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    response = call_llm(messages)
    
    if not response:
        print("LLM调用失败")
        tm.mark_error_fix_pending(task_name, "LLM调用失败")
        return
    
    print(f"\nLLM返回:\n{response}")
    
    # 解析响应
    parsed = parse_fix_response(response)
    
    print(f"\n分析: {parsed['analysis']}")
    print(f"修复代码: {parsed['code_fix'][:200] if parsed['code_fix'] else '无'}...")
    
    # 执行修复代码
    if parsed['code_fix']:
        print("\n执行修复代码...")
        success, msg = execute_fix_code(parsed['code_fix'], task_name)
        print(f"执行结果: {msg}")
        
        if success:
            tm.mark_end(task_name, "修复成功")
            log.set_message(f"修复成功").finish("success")
        else:
            tm.mark_error_fix_pending(task_name, msg)
            log.set_message(f"修复失败: {msg}").finish("failed")
    else:
        print("没有可执行的修复代码")
        tm.mark_error_fix_pending(task_name, "没有可执行的修复代码")
    
    tm.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python subtask_executor.py <task_name>")
        sys.exit(1)
    
    main(sys.argv[1])
