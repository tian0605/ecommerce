#!/usr/bin/env python3
"""生成心跳报告 - 基于数据库的任务状态"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')

from task_manager import TaskManager
from logger import get_logger
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
            import re
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
            import re
            if re.search(pattern, error, re.IGNORECASE):
                if fix not in fixes:
                    fixes.append(fix)
                break
    return fixes

def generate_report():
    tm = TaskManager()
    
    # 获取所有任务和任务树
    all_tasks = tm.get_all_tasks()
    actionable = tm.get_actionable_tasks(limit=2)
    task_tree = tm.get_task_tree()
    
    tm.close()
    
    task_result = parse_task_log()
    fixes = analyze_errors(task_result['errors']) if task_result and task_result.get('errors') else []
    
    # 状态名称映射
    state_names = {
        'new': "🆕 新任务",
        'error_fix_pending': "🔧 待修复",
        'normal_crash': "🔄 可重试",
        'requires_manual': "👤 需人工",
        'processing': "⚙️ 执行中",
        'end': "✅ 已完成"
    }
    
    lines = []
    lines.append("📊 **CommerceFlow 心跳报告**")
    lines.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    
    # 统计
    total = len(all_tasks)
    pending = len(actionable)
    lines.append(f"📌 **任务状态**")
    lines.append(f"  总计: {total} | 待执行: {pending}")
    lines.append("")
    
    # 按状态分组显示
    by_state = {}
    for t in all_tasks:
        state = t['exec_state']
        if state not in by_state:
            by_state[state] = []
        by_state[state].append(t)
    
    # 待修复任务
    error_tasks = by_state.get('error_fix_pending', [])
    if error_tasks:
        lines.append(f"**🔧 待修复** ({len(error_tasks)})")
        for t in error_tasks:
            lines.append(f"  • {t['display_name']}")
            if t.get('fix_suggestion'):
                lines.append(f"    → {t['fix_suggestion'][:50]}")
            # 显示子任务
            for child in task_tree:
                if child['task_name'] == t['task_name']:
                    for c in child.get('children', []):
                        lines.append(f"    └── {c['display_name']} ({c['exec_state']})")
        lines.append("")
    
    # 进行中任务
    proc_tasks = by_state.get('processing', [])
    if proc_tasks:
        lines.append(f"**⚙️ 执行中** ({len(proc_tasks)})")
        for t in proc_tasks:
            lines.append(f"  • {t['display_name']}")
        lines.append("")
    
    # 其他任务
    other_tasks = [t for t in all_tasks if t['exec_state'] not in ['error_fix_pending', 'processing', 'end']]
    if other_tasks:
        lines.append(f"**🔄 其他** ({len(other_tasks)})")
        for t in other_tasks:
            lines.append(f"  • {t['display_name']} ({t['exec_state']})")
        lines.append("")
    
    # 已完成任务
    completed = by_state.get('end', [])
    if completed:
        lines.append(f"**✅ 已完成** ({len(completed)})")
        for t in completed[:5]:  # 最多显示5个
            exec_time = t['last_executed_at'].strftime('%m-%d %H:%M') if t['last_executed_at'] else ''
            lines.append(f"  • {t['display_name']} ({exec_time})")
        if len(completed) > 5:
            lines.append(f"  ... 还有 {len(completed)-5} 个")
        lines.append("")
    
    # 本次计划
    if actionable:
        lines.append("📋 **本次计划**")
        for t in actionable:
            lines.append(f"  ▸ {t['display_name']}")
            if t.get('fix_suggestion'):
                lines.append(f"    → {t['fix_suggestion'][:40]}")
    else:
        lines.append("📋 **本次计划**")
        lines.append("  无待处理任务")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    
    # 检查日志错误
    if fixes:
        lines.append(f"⚠️ **发现{len(fixes)}个已知问题**")
        for fix in fixes:
            lines.append(f"  • {fix}")
        lines.append("")
    
    lines.append("✅ 心跳检查正常")
    
    return "\n".join(lines)

if __name__ == '__main__':
    report = generate_report()
    print(report)
