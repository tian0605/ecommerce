#!/usr/bin/env python3
"""生成心跳报告 - 包含上次执行结果、异常分析和本次计划"""
import json
import re
from pathlib import Path
from datetime import datetime

STATE_FILE = Path('/root/.openclaw/workspace-e-commerce/logs/heartbeat_state.json')
TASK_LOG = Path('/root/.openclaw/workspace-e-commerce/logs/task_exec.log')
TASK_QUEUE = Path('/root/.openclaw/workspace-e-commerce/docs/dev-task-queue.md')

# 错误到修复任务的映射
ERROR_FIX_MAP = [
    (r"ProductStorer.*no attribute.*save", "product-storer接口修复"),
    (r"ListingOptimizer.*no attribute.*optimize", "listing-optimizer接口修复"),
    (r"MiaoshouUpdater.*no attribute", "miaoshou-updater接口修复"),
    (r"ProfitAnalyzer.*no attribute", "profit-analyzer接口修复"),
    (r"'str' object has no attribute", "数据类型错误修复"),
    (r"ModuleNotFoundError|No module named", "模块导入路径修复"),
    (r"EPIPE|Browser.*crash", "浏览器稳定性修复"),
]

def load_last_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def parse_task_log():
    if not TASK_LOG.exists():
        return None
    
    content = TASK_LOG.read_text()
    if not content.strip():
        return None
    
    # 提取步骤结果
    steps = {}
    for line in content.split('\n'):
        if '工作流结果汇总' in line:
            break
        if '【步骤' in line or '[步骤' in line:
            step = line.strip()
            if '✅' in line:
                steps[step] = '✅'
            elif '❌' in line:
                steps[step] = '❌'
    
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
        if 'ERROR' in line and '失败' in line:
            # 提取关键错误信息
            match = re.search(r'❌\s*(.+?)(?:\n|$)', line)
            if match:
                err = match.group(1).strip()[:100]
                if err not in errors:
                    errors.append(err)
    
    return {
        'steps': steps,
        'summary': summary,
        'errors': errors[:5],
        'has_content': bool(content.strip())
    }

def parse_task_queue():
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
    return pending[:5]

def analyze_errors_and_suggest_fixes(errors):
    """分析错误并建议修复任务"""
    fixes = []
    for error in errors:
        for pattern, fix_task in ERROR_FIX_MAP:
            if re.search(pattern, error, re.IGNORECASE):
                if fix_task not in fixes:
                    fixes.append(fix_task)
                break
    return fixes

def generate_report():
    last_state = load_last_state()
    task_result = parse_task_log()
    pending_tasks = parse_task_queue()
    
    # 分析错误并建议修复
    suggested_fixes = []
    if task_result and task_result.get('errors'):
        suggested_fixes = analyze_errors_and_suggest_fixes(task_result['errors'])
    
    report = []
    report.append("📊 **CommerceFlow 心跳报告**")
    report.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append("━" * 20)
    
    # 上次执行结果
    if task_result and task_result.get('summary'):
        report.append("📋 **上次执行结果**")
        for name, status in task_result['summary'].items():
            report.append(f"  {status} {name}")
        
        if task_result.get('errors'):
            report.append("  ⚠️ 异常:")
            for err in task_result['errors']:
                report.append(f"    • {err[:80]}")
        report.append("")
    
    # 本次计划
    report.append("📋 **本次计划**")
    
    # 自动添加修复任务
    if suggested_fixes:
        report.append("  🔧 自动计划（基于上次错误）:")
        for fix in suggested_fixes:
            report.append(f"    ▸ {fix}")
        if pending_tasks:
            report.append("  📝 队列任务:")
            for task in pending_tasks:
                report.append(f"    ▸ {task}")
    elif pending_tasks:
        for task in pending_tasks:
            report.append(f"  ▸ {task}")
    else:
        report.append("  无待执行任务")
    
    report.append("━" * 20)
    report.append("✅ 心跳检查正常")
    
    return '\n'.join(report)

if __name__ == '__main__':
    print(generate_report())
