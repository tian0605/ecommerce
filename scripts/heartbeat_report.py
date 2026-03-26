#!/usr/bin/env python3
"""生成心跳报告 - 基于数据库的任务状态"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')

from task_manager import TaskManager, ExecState
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
    actionable = tm.get_actionable_tasks()
    tm.close()
    
    task_result = parse_task_log()
    fixes = analyze_errors(task_result['errors']) if task_result and task_result.get('errors') else []
    
    # 按状态分组
    by_state = {}
    for t in all_tasks:
        state = t['exec_state']
        if state not in by_state:
            by_state[state] = []
        by_state[state].append(t)
    
    state_names = {
        ExecState.NEW: "🆕 新任务",
        ExecState.ERROR_FIX_PENDING: "🔧 待修复",
        ExecState.NORMAL_CRASH: "🔄 可重试",
        ExecState.REQUIRES_MANUAL: "👤 需人工",
        ExecState.PROCESSING: "⚙️ 执行中",
        ExecState.END: "✅ 已完成"
    }
    
    report = []
    report.append("📊 **CommerceFlow 心跳报告**")
    report.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append("━" * 22)
    
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
    
    # 任务状态
    report.append("📌 **任务状态**")
    total = len(all_tasks)
    pending = len(by_state.get(ExecState.NEW, [])) + \
              len(by_state.get(ExecState.ERROR_FIX_PENDING, [])) + \
              len(by_state.get(ExecState.NORMAL_CRASH, [])) + \
              len(by_state.get(ExecState.REQUIRES_MANUAL, []))
    
    report.append(f"  总计: {total} | 待执行: {pending}")
    report.append("")
    
    # 显示各状态任务
    for state in [ExecState.ERROR_FIX_PENDING, ExecState.NORMAL_CRASH, 
                  ExecState.REQUIRES_MANUAL, ExecState.NEW, 
                  ExecState.PROCESSING, ExecState.END]:
        if state in by_state:
            report.append(f"**{state_names[state]}** ({len(by_state[state])})")
            for t in by_state[state]:
                exec_time = t['last_executed_at'].strftime('%m-%d %H:%M') if t['last_executed_at'] else '从未'
                if state == ExecState.ERROR_FIX_PENDING and t.get('fix_suggestion'):
                    report.append(f"  • {t['display_name']}")
                    report.append(f"    → {t['fix_suggestion']}")
                elif state == ExecState.REQUIRES_MANUAL:
                    err = t.get('last_error', '')[:40] if t.get('last_error') else ''
                    report.append(f"  • {t['display_name']}")
                    report.append(f"    ❌ {err}")
                else:
                    report.append(f"  • {t['display_name']} ({exec_time})")
            report.append("")
    
    # 本次计划
    report.append("📋 **本次计划**")
    if actionable:
        for t in actionable[:5]:
            action = ""
            if t['exec_state'] == ExecState.ERROR_FIX_PENDING:
                action = f" → {t.get('fix_suggestion', '自动修复')}"
            elif t['exec_state'] == ExecState.REQUIRES_MANUAL:
                action = " → 需人工介入"
            elif t['exec_state'] == ExecState.NORMAL_CRASH:
                action = " → 自动重试"
            report.append(f"  ▸ {t['display_name']}{action}")
    else:
        report.append("  无待处理任务")
    
    report.append("━" * 22)
    report.append("✅ 心跳检查正常")
    return '\n'.join(report)

if __name__ == '__main__':
    print(generate_report())
