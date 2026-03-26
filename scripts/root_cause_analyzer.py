#!/usr/bin/env python3
"""
root_cause_analyzer.py - 根因分析器

当父任务重试3次仍失败时，调用LLM分析最近日志，找出真正根因
"""
import sys
import requests
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
sys.path.insert(0, str(WORKSPACE / 'scripts'))

import psycopg2

# 从配置加载
sys.path.insert(0, str(WORKSPACE / 'config'))
from llm_config import LLM_CONFIG

SYSTEM_PROMPT = """你是一个专业的电商运营自动化系统错误分析专家。

当任务反复失败时，你需要从日志中找出真正的根本原因。

【分析要求】
1. 识别日志中的错误模式
2. 找出真正的根因（不是表面错误）
3. 给出具体的修复方案

【输出格式】
```
【根因分析】
1-3句话说明真正的根本原因

【修复方案】
具体可执行的修复步骤

【优先级】
P0/P1/P2
```

请用中文回答，简洁明了。"""


def get_recent_logs(task_name: str, limit: int = 50) -> str:
    """获取最近日志"""
    conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
    cur = conn.cursor()
    
    cur.execute("""
        SELECT run_status, run_message, created_at
        FROM main_logs 
        WHERE task_name = %s
        ORDER BY id DESC
        LIMIT %s
    """, (task_name, limit))
    
    logs = []
    for row in cur.fetchall():
        logs.append(f"[{row[2]}] {row[0]}: {str(row[1])[:100]}")
    
    cur.close()
    conn.close()
    
    return '\n'.join(logs)


def get_task_info(task_name: str) -> dict:
    """获取任务信息"""
    conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
    cur = conn.cursor()
    
    cur.execute("""
        SELECT display_name, description, retry_count, last_error, fix_suggestion
        FROM tasks 
        WHERE task_name = %s
    """, (task_name,))
    
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if row:
        return {
            'display_name': row[0],
            'description': row[1],
            'retry_count': row[2],
            'last_error': row[3],
            'fix_suggestion': row[4]
        }
    return {}


def analyze(task_name: str) -> dict:
    """执行根因分析"""
    print(f"[{datetime.now()}] 开始根因分析: {task_name}")
    
    # 获取任务信息
    task_info = get_task_info(task_name)
    logs = get_recent_logs(task_name, 50)
    
    user_prompt = f"""任务信息：
- 任务名：{task_name}
- 显示名：{task_info.get('display_name', 'N/A')}
- 描述：{task_info.get('description', 'N/A')}
- 已重试：{task_info.get('retry_count', 0)}次
- 最后错误：{task_info.get('last_error', 'N/A')}
- 已尝试的修复：{task_info.get('fix_suggestion', 'N/A')}

最近日志：
{logs}

请分析这些日志，找出任务反复失败的真正根因。"""
    
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
                "max_tokens": LLM_CONFIG.get('max_tokens', 1500),
                "temperature": 0.3
            },
            timeout=120
        )
        
        if response.status_code != 200:
            print(f"LLM API error: {response.status_code}")
            return None
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        print(f"[{datetime.now()}] 根因分析完成")
        print(content)
        
        return parse_analysis(content)
        
    except Exception as e:
        print(f"分析失败: {e}")
        return None


def parse_analysis(content: str) -> dict:
    """解析LLM分析结果"""
    result = {
        'root_cause': '',
        'fix_steps': '',
        'priority': 'P1'
    }
    
    lines = content.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if '根因分析' in line:
            current_section = 'root'
        elif '修复方案' in line or '解决方案' in line:
            current_section = 'fix'
        elif '优先级' in line:
            current_section = 'priority'
        elif line and current_section:
            if current_section == 'root':
                result['root_cause'] += line + ' '
            elif current_section == 'fix':
                result['fix_steps'] += line + '\n'
            elif current_section == 'priority':
                if 'P0' in line:
                    result['priority'] = 'P0'
                elif 'P1' in line:
                    result['priority'] = 'P1'
    
    result['root_cause'] = result['root_cause'].strip()
    result['fix_steps'] = result['fix_steps'].strip()
    
    return result


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python root_cause_analyzer.py <task_name>")
        sys.exit(1)
    
    result = analyze(sys.argv[1])
    if result:
        print(f"\n解析结果:")
        print(f"根因: {result['root_cause']}")
        print(f"修复: {result['fix_steps']}")
        print(f"优先级: {result['priority']}")
