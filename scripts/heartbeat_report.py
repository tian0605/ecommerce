#!/usr/bin/env python3
"""生成心跳报告 - 包含上次执行结果和本次计划"""
import json
from pathlib import Path
from datetime import datetime

STATE_FILE = Path('/root/.openclaw/workspace-e-commerce/logs/heartbeat_state.json')
TASK_LOG = Path('/root/.openclaw/workspace-e-commerce/logs/task_exec.log')
TASK_QUEUE = Path('/root/.openclaw/workspace-e-commerce/docs/dev-task-queue.md')

def load_last_state():
    """加载上次心跳状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def save_state(state):
    """保存当前状态"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def parse_task_log():
    """解析任务执行日志"""
    if not TASK_LOG.exists():
        return None
    
    content = TASK_LOG.read_text()
    if not content.strip():
        return None
    
    # 提取步骤结果
    steps = {}
    for line in content.split('\n'):
        if '【步骤' in line and '】' in line:
            step = line.strip()
            if '✅' in line:
                steps[step] = '✅'
            elif '❌' in line:
                steps[step] = '❌'
            else:
                steps[step] = '🔄'
    
    # 提取汇总
    summary = {}
    for line in content.split('\n'):
        if ': ❌' in line or ': ✅' in line:
            parts = line.split(':')
            if len(parts) >= 2:
                name = parts[0].strip()
                status = parts[1].strip()
                summary[name] = status
    
    # 提取错误信息
    errors = []
    for line in content.split('\n'):
        if '❌' in line and ('ERROR' in line or '失败' in line):
            errors.append(line.strip()[:100])
    
    return {
        'steps': steps,
        'summary': summary,
        'errors': errors[:3],  # 最多3个错误
        'has_content': True
    }

def parse_task_queue():
    """解析任务队列"""
    if not TASK_QUEUE.exists():
        return []
    
    content = TASK_QUEUE.read_text()
    pending = []
    for line in content.split('\n'):
        if '⬜ 待执行' in line:
            parts = line.split('|')
            if len(parts) >= 3:
                task = parts[2].strip().replace('**', '')
                pending.append(task)
    return pending[:5]  # 最多5个

def generate_report():
    """生成报告"""
    last_state = load_last_state()
    task_result = parse_task_log()
    pending_tasks = parse_task_queue()
    
    report = []
    report.append("📊 **CommerceFlow 心跳报告**")
    report.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append("━" * 20)
    
    # 上次执行结果
    if task_result:
        report.append("📋 **上次执行结果**")
        if task_result.get('summary'):
            for name, status in task_result['summary'].items():
                report.append(f"  {status} {name}")
        if task_result.get('errors'):
            report.append("  ⚠️ 异常:")
            for err in task_result['errors']:
                report.append(f"    • {err}")
        report.append("")
    
    # 本次计划
    report.append("📋 **本次计划**")
    if pending_tasks:
        for task in pending_tasks:
            report.append(f"  ▸ {task}")
    else:
        report.append("  无待执行任务")
    
    report.append("━" * 20)
    report.append("✅ 心跳检查正常")
    
    return '\n'.join(report)

if __name__ == '__main__':
    print(generate_report())
