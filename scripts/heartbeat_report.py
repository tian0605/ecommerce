#!/usr/bin/env python3
"""生成心跳报告 - 基于数据库的任务状态"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')

from task_manager import TaskManager, generate_db_report
import json
import re
from pathlib import Path
from datetime import datetime

TASK_LOG = Path('/root/.openclaw/workspace-e-commerce/logs/task_exec.log')

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
    tm = TaskManager()
    all_tasks = tm.get_all_tasks()
    pending_tasks = tm.get_pending_tasks()
    tm.close()
    
    task_result = parse_task_log()
    fixes = analyze_errors(task_result['errors']) if task_result and task_result.get('errors') else []
    
    total = len(all_tasks)
    pending = len(pending_tasks)
    completed = total - pending
    
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
    
    # 数据库任务状态
    report.append(f"📌 **任务状态** ({completed}/{total})")
    for t in all_tasks:
        status_icon = {'completed': '✅', 'running': '🔄', 'pending': '⬜', 'failed': '❌'}.get(t['status'], '❓')
        last_exec = t['last_executed_at'].strftime('%m-%d %H:%M') if t['last_executed_at'] else '从未'
        if t['status'] == 'failed' and t['last_error']:
            report.append(f"  {status_icon} {t['display_name']} | 上次:{last_exec}")
            report.append(f"      ❌ {t['last_error'][:50]}")
        elif t['status'] in ('pending', 'failed'):
            report.append(f"  {status_icon} {t['display_name']} | 上次:{last_exec}")
        else:
            report.append(f"  {status_icon} {t['display_name']}")
    report.append("")
    
    # 本次计划
    report.append("📋 **本次计划**")
    if fixes:
        for fix in fixes:
            report.append(f"  🔧 {fix}")
    elif pending_tasks:
        for t in pending_tasks[:3]:
            report.append(f"  ▸ {t['display_name']}")
    else:
        report.append("  无待处理任务")
    
    report.append("━" * 20)
    report.append("✅ 心跳检查正常")
    return '\n'.join(report)

if __name__ == '__main__':
    print(generate_report())
