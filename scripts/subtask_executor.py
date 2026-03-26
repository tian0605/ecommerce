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
import requests
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
SCRIPTS_DIR = WORKSPACE / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

from task_manager import TaskManager
from logger import get_logger

LLM_CONFIG = {
    'api_key': 'sk-914c1a9a5f054ab4939464389b5b791f',
    'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'model': 'qwen3.5-plus'
}

SYSTEM_PROMPT = """你是一个专业的电商运营自动化工程师，负责修复子任务。

你的工作流程：
1. 分析问题：理解错误的根本原因
2. 思考方案：使用ReAct模式思考解决方案
3. 制定计划：决定是直接修复还是需要创建脚本
4. 执行修复：编写/执行修复代码
5. 验证结果：确认修复成功

输出格式要求：
- 分析：简明扼要说明问题根因
- 计划：具体可执行的步骤
- 修复：实际执行的代码或命令

请用中文回答。"""


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
                "temperature": 0.3
            },
            timeout=120
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"LLM Error: {response.status_code} - {response.text[:200]}"
    except Exception as e:
        return f"LLM Exception: {str(e)}"


def analyze_and_plan(task_info: dict) -> dict:
    """使用ReAct模式分析并制定计划"""
    task_name = task_info['task_name']
    description = task_info.get('description', '')
    error = task_info.get('last_error', '')
    success_criteria = task_info.get('success_criteria', '')
    fix_suggestion = task_info.get('fix_suggestion', '')
    
    user_prompt = f"""## 子任务信息
- 任务名：{task_name}
- 描述：{description}
- 错误信息：{error}
- 成功标准：{success_criteria}
- 已有修复建议：{fix_suggestion}

## 请按以下步骤工作：

### Step 1: 分析问题
分析错误的根本原因是什么？

### Step 2: 思考方案
使用ReAct模式：
- Thought: 思考可能的解决方案
- Action: 选择一个具体行动
- Observation: 观察行动结果
- 重复直到有清晰方案

### Step 3: 制定计划
具体的修复步骤是什么？需要修改哪些文件？

### Step 4: 执行修复
执行修复并记录结果。

### Step 5: 验证
如何验证修复成功？"""
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    print(f"  🤖 调用LLM分析问题...")
    result = call_llm(messages)
    
    # 解析结果
    analysis = ""
    plan = ""
    code_fix = ""
    
    lines = result.split('\n')
    section = None
    for line in lines:
        if any(x in line for x in ['分析', '问题', '根因']):
            section = 'analysis'
        elif any(x in line for x in ['计划', '步骤', '修复']):
            section = 'plan'
        elif any(x in line for x in ['代码', '执行', '```']):
            section = 'code'
        elif section and line.strip():
            if section == 'analysis':
                analysis += line + '\n'
            elif section == 'plan':
                plan += line + '\n'
            elif section == 'code':
                code_fix += line + '\n'
    
    return {
        'analysis': analysis.strip(),
        'plan': plan.strip(),
        'code_fix': code_fix.strip(),
        'llm_response': result
    }


def execute_fix(task_info: dict, fix_plan: dict) -> tuple:
    """执行修复并返回(成功bool, 输出str)"""
    task_name = task_info['task_name']
    code = fix_plan.get('code_fix', '')
    
    if not code:
        return False, "LLM未提供修复代码"
    
    # 如果有Python代码，执行它
    if 'python' in code.lower() or '```' in code:
        # 提取代码
        lines = code.split('\n')
        code_lines = []
        in_code = False
        for line in lines:
            if '```' in line:
                in_code = not in_code
                continue
            if in_code:
                code_lines.append(line)
        
        if code_lines:
            code_str = '\n'.join(code_lines)
            print(f"  📝 执行Python修复代码...")
            try:
                exec(code_str)
                return True, "代码执行成功"
            except Exception as e:
                return False, f"代码执行失败: {e}"
    
    return False, "无法执行修复"


def run_subtask(task_name: str):
    """执行单个子任务"""
    log = get_logger('subtask_executor')
    log.set_task(task_name)
    
    print(f"\n{'='*60}")
    print(f"执行子任务: {task_name}")
    print(f"{'='*60}")
    
    tm = TaskManager()
    task = tm.get_task(task_name)
    
    if not task:
        print(f"  ❌ 任务不存在: {task_name}")
        log.finish("failed", "任务不存在")
        tm.close()
        return False
    
    # 标记开始
    tm.mark_start(task_name)
    
    # Step 1 & 2: 分析并制定计划
    print(f"  📋 分析问题...")
    fix_plan = analyze_and_plan(task)
    
    analysis = fix_plan.get('analysis', '')
    plan = fix_plan.get('plan', '')
    llm_response = fix_plan.get('llm_response', '')
    
    # 回写分析结果
    tm.update_task(task_name,
        analysis=analysis[:2000] if analysis else '',
        plan=plan[:2000] if plan else ''
    )
    
    print(f"  ✅ 分析完成")
    if analysis:
        print(f"     分析: {analysis[:100]}...")
    if plan:
        print(f"     计划: {plan[:100]}...")
    
    # Step 3 & 4: 执行修复
    success, msg = execute_fix(task, fix_plan)
    
    # Step 5: 验证和回写
    if success:
        tm.mark_end(task_name, f"修复成功: {msg}")
        print(f"  ✅ 修复成功: {msg}")
        log.set_message(f"子任务修复成功").finish("success")
    else:
        # 记录当前重试次数
        retry_count = task.get('retry_count', 0) or 0
        
        if retry_count >= 3:
            tm.update_task(task_name,
                status='failed',
                exec_state='requires_manual',
                last_error=msg
            )
            print(f"  👤 超过重试次数，标记为需要人工")
            log.set_message(f"子任务失败，需人工").finish("failed", msg)
        else:
            tm.update_task(task_name,
                status='pending',
                exec_state='normal_crash',
                last_error=msg
            )
            print(f"  ⏳ 标记为可重试 (retry={retry_count+1})")
            log.set_message(f"子任务失败，可重试").finish("failed", msg)
    
    tm.close()
    return success


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python3 subtask_executor.py <task_name>")
        sys.exit(1)
    
    task_name = sys.argv[1]
    success = run_subtask(task_name)
    sys.exit(0 if success else 1)
