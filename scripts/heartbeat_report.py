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
            match = re.search(r'❌\s*(.+?)(?:\n|$)', line)
            if match:
                err = match.group(1).strip()[:100]
                if err not in errors:
                    errors.append(err)
    
    return {
        'summary': summary,
        'errors': errors[:5],
        'has_content': bool(content.strip())
    }

def parse_today_tasks():
    """解析今日待完成任务清单"""
    if not TASK_QUEUE.exists():
        return [], 0, 0
    
    content = TASK_QUEUE.read_text()
    lines = content.split('\n')
    
    pending = []  # 待执行任务
    completed = 0   # 已完成任务计数
    in_today_section = False
    in_task_table = False
    
    for line in lines:
        # 进入今日任务区域
        if '## 📋 今日任务' in line:
            in_today_section = True
            continue
        
        # 离开今日任务区域
        if in_today_section and line.startswith('## ') and '今日' not in line:
            break
        
        if in_today_section:
            # 检测表格开始
            if '| # | 任务 |' in line:
                in_task_table = True
                continue
            
            # 检测表格结束
            if in_task_table and line.startswith('|') and '---' not in line and '成功标准' not in line:
                # 解析任务行
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 4:
                    status = parts[3]
                    task_name = parts[2].replace('**', '')
                    if '⬜ 待执行' in status:
                        pending.append(task_name)
                    elif '✅ 已完成' in status:
                        completed += 1
            elif '成功标准' in line:
                in_task_table = False
    
    total = len(pending) + completed
    return pending, total, completed

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
    pending_tasks, total_tasks, completed = parse_today_tasks()
    
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
    
    # 今日任务清单
    if total_tasks > 0:
        report.append(f"📌 **今日任务** (已完成 {completed}/{total_tasks})")
        if pending_tasks:
            for task in pending_tasks[:10]:
                report.append(f"  ⬜ {task}")
        else:
            report.append("  ✅ 全部完成！")
        report.append("")
    
    # 本次计划
    report.append("📋 **本次计划**")
    
    if suggested_fixes:
        report.append("  🔧 修复任务:")
        for fix in suggested_fixes:
            report.append(f"    ▸ {fix}")
    elif pending_tasks:
        report.append("  📝 待执行任务:")
        for task in pending_tasks[:5]:
            report.append(f"    ▸ {task}")
    else:
        report.append("  无待处理任务")
    
    report.append("━" * 20)
    report.append("✅ 心跳检查正常")
    
    return '\n'.join(report)

if __name__ == '__main__':
    print(generate_report())
