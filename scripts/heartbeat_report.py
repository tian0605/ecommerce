#!/usr/bin/env python3
"""生成心跳报告"""
import json
import re
from pathlib import Path
from datetime import datetime

STATE_FILE = Path('/root/.openclaw/workspace-e-commerce/logs/heartbeat_state.json')
TASK_LOG = Path('/root/.openclaw/workspace-e-commerce/logs/task_exec.log')
TASK_QUEUE = Path('/root/.openclaw/workspace-e-commerce/docs/dev-task-queue.md')

ERROR_FIX_MAP = [
    (r"ProductStorer.*no attribute.*save", "product-storer接口修复"),
    (r"ListingOptimizer.*no attribute.*optimize", "listing-optimizer接口修复"),
    (r"MiaoshouUpdater.*no attribute", "miaoshou-updater接口修复"),
    (r"ProfitAnalyzer.*no attribute", "profit-analyzer接口修复"),
    (r"'str' object has no attribute", "数据类型错误修复"),
    (r"ModuleNotFoundError|No module named", "模块导入路径修复"),
    (r"EPIPE|Browser.*crash", "浏览器稳定性修复"),
]

def parse_task_log():
    if not TASK_LOG.exists() or not TASK_LOG.read_text().strip():
        return None
    content = TASK_LOG.read_text()
    summary, errors = {}, []
    for line in content.split('\n'):
        if ': ❌' in line or ': ✅' in line:
            parts = line.split(':')
            if len(parts) >= 2:
                summary[parts[0].strip()] = parts[1].strip()
        if 'ERROR' in line and '失败' in line:
            match = re.search(r'❌\s*(.+?)(?:\n|$)', line)
            if match:
                err = match.group(1).strip()[:100]
                if err not in errors:
                    errors.append(err)
    return {'summary': summary, 'errors': errors[:5]}

def parse_all_tasks():
    """解析所有任务及状态"""
    if not TASK_QUEUE.exists():
        return [], 0
    content = TASK_QUEUE.read_text()
    lines = content.split('\n')
    tasks = []
    in_today = False
    in_table = False
    
    for line in lines:
        if '## 📋 今日任务' in line:
            in_today = True
            continue
        if in_today and line.startswith('## ') and '今日' not in line:
            break
        if in_today:
            if '| # | 任务 |' in line:
                in_table = True
                continue
            if '成功标准' in line:
                in_table = False
            if in_table and line.startswith('|') and '---' not in line:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 4 and parts[2]:
                    task = parts[2].replace('**', '')
                    status = parts[3]
                    tasks.append((task, status))
    
    total = len(tasks)
    completed = sum(1 for _, s in tasks if '✅' in s)
    return tasks, total, completed

def analyze_errors(errors):
    fixes = []
    for error in errors:
        for pattern, fix in ERROR_FIX_MAP:
            if re.search(pattern, error, re.IGNORECASE):
                if fix not in fixes:
                    fixes.append(fix)
                break
    return fixes

def generate_report():
    task_result = parse_task_log()
    tasks, total, completed = parse_all_tasks()
    fixes = analyze_errors(task_result['errors']) if task_result and task_result.get('errors') else []
    
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
    
    # 今日任务清单
    if tasks:
        report.append(f"📌 **今日任务清单** ({completed}/{total})")
        for task, status in tasks:
            emoji = "✅" if "✅" in status else "⬜"
            report.append(f"  {emoji} {task}")
        report.append("")
    
    # 本次计划
    report.append("📋 **本次计划**")
    if fixes:
        for fix in fixes:
            report.append(f"  ▸ {fix}")
    elif tasks:
        pending = [t for t, s in tasks if "⬜" in s]
        for t in pending[:5]:
            report.append(f"  ▸ {t}")
    else:
        report.append("  无待处理任务")
    
    report.append("━" * 20)
    report.append("✅ 心跳检查正常")
    return '\n'.join(report)

if __name__ == '__main__':
    print(generate_report())
