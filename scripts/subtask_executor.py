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

from task_manager import TaskManager
from logger import get_logger

LLM_CONFIG = {
    'api_key': 'sk-914c1a9a5f054ab4939464389b5b791f',
    'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'model': 'qwen3.5-plus'
}

SYSTEM_PROMPT = """你是一个专业的电商运营自动化工程师，负责修复Python代码bug。

【关键要求】
你必须输出【修复代码】，这是最重要的部分。

【输出格式】
必须按以下格式输出：

【分析】
1-3句话说明问题根因

【修复代码】
```python
# 这里必须输出完整的、可执行的Python代码
# 代码要能够直接运行并修复问题
```

【示例输出】
【分析】
错误是因为传入的参数是字符串但代码尝试调用.get()方法

【修复代码】
```python
import json
def fix_params(params):
    if isinstance(params, str):
        params = json.loads(params)
    return params
```"""


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


def parse_llm_response(result: str) -> dict:
    """解析LLM响应，提取分析、计划、代码"""
    
    # 用正则提取所有 python 代码块
    code_blocks = re.findall(r'```python\s*(.*?)```', result, re.DOTALL)
    code_fix = '\n'.join(code_blocks).strip() if code_blocks else ''
    
    # 清理代码中的 docstring
    if code_fix:
        code_lines = []
        skip_triple_quote = False
        for line in code_fix.split('\n'):
            stripped = line.strip()
            if '"""' in stripped or "'''" in stripped:
                skip_triple_quote = not skip_triple_quote
                continue
            if not skip_triple_quote:
                code_lines.append(line)
        code_fix = '\n'.join(code_lines).strip()
    
    # 提取分析（第一段非代码内容）
    analysis_lines = []
    plan_lines = []
    in_code = False
    
    for line in result.split('\n'):
        if '```' in line:
            in_code = not in_code
            continue
        if not in_code:
            if line.strip().startswith('【分析】'):
                analysis_lines.append(line.replace('【分析】', '').strip())
            elif line.strip().startswith('【计划】'):
                plan_lines.append(line.replace('【计划】', '').strip())
            elif line.strip().startswith('【修复代码】'):
                continue
            elif analysis_lines and not plan_lines and line.strip():
                analysis_lines.append(line.strip())
            elif plan_lines and line.strip():
                plan_lines.append(line.strip())
    
    analysis = ' '.join(analysis_lines).strip()
    plan = ' '.join(plan_lines).strip()
    
    return {
        'analysis': analysis,
        'plan': plan,
        'code_fix': code_fix,
        'llm_response': result
    }


def analyze_and_plan(task_info: dict) -> dict:
    """分析并制定计划"""
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

请分析问题并输出修复代码。"""
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    print(f"  🤖 调用LLM分析问题...")
    result = call_llm(messages)
    
    return parse_llm_response(result)


def execute_fix(code: str) -> tuple:
    """执行修复代码"""
    if not code:
        return False, "没有提供修复代码"
    
    print(f"  📝 执行修复代码...")
    try:
        exec(code)
        return True, "代码执行成功"
    except Exception as e:
        return False, f"代码执行失败: {e}"


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
    code_fix = fix_plan.get('code_fix', '')
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
    if code_fix:
        print(f"     代码: {code_fix[:100]}...")
    
    # Step 3 & 4: 执行修复
    success, msg = execute_fix(code_fix)
    
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
