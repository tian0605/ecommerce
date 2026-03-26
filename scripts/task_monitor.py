#!/usr/bin/env python3
"""
task_monitor.py - 任务运行质量监控

每6小时执行一次，分析任务执行日志，生成质量报告并发送飞书
"""
import sys
import requests
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
sys.path.insert(0, str(WORKSPACE / 'scripts'))

import psycopg2

FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/6af7d281-ca31-42c6-ab88-5ba434404fb9"


def get_task_stats(conn):
    """获取任务统计"""
    cur = conn.cursor()
    
    # 任务状态统计
    cur.execute("""
        SELECT exec_state, COUNT(*) 
        FROM tasks 
        GROUP BY exec_state
    """)
    state_stats = {row[0]: row[1] for row in cur.fetchall()}
    
    # 最近24小时任务执行情况
    cur.execute("""
        SELECT run_status, COUNT(*)
        FROM main_logs
        WHERE created_at > NOW() - INTERVAL '24 hours'
        GROUP BY run_status
    """)
    log_stats = {row[0]: row[1] for row in cur.fetchall()}
    
    # 最近失败的任务
    cur.execute("""
        SELECT task_name, exec_state, retry_count, last_error
        FROM tasks 
        WHERE exec_state IN ('ERROR_FIX_PENDING', 'NORMAL_CRASH', 'REQUIRES_MANUAL')
        ORDER BY updated_at DESC
        LIMIT 5
    """)
    failed_tasks = cur.fetchall()
    
    # 卡死任务
    cur.execute("""
        SELECT COUNT(*)
        FROM tasks 
        WHERE exec_state = 'PROCESSING'
        AND last_executed_at < NOW() - INTERVAL '10 minutes'
    """)
    stuck_count = cur.fetchone()[0]
    
    cur.close()
    return state_stats, log_stats, failed_tasks, stuck_count


def generate_report(state_stats, log_stats, failed_tasks, stuck_count):
    """生成报告"""
    report = []
    report.append("📊 CommerceFlow 任务运行质量报告")
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append("")
    
    # 任务状态
    report.append("📋 任务状态统计:")
    for state, count in sorted(state_stats.items()):
        emoji = {'end': '✅', 'processing': '🔄', 'error_fix_pending': '🔧', 'new': '🆕'}.get(state, '❓')
        report.append(f"  {emoji} {state}: {count}")
    
    report.append("")
    report.append("📈 24小时执行统计:")
    total_logs = sum(log_stats.values())
    for status, count in sorted(log_stats.items()):
        pct = count / total_logs * 100 if total_logs > 0 else 0
        emoji = {'success': '✅', 'failed': '❌', 'running': '🔄', 'following': '👀', 'skipped': '⏭️'}.get(status, '❓')
        report.append(f"  {emoji} {status}: {count} ({pct:.1f}%)")
    
    if failed_tasks:
        report.append("")
        report.append("⚠️ 待处理失败任务:")
        for task in failed_tasks:
            report.append(f"  - {task[0]}: {task[3][:50] if task[3] else '无错误'}")
    
    if stuck_count > 0:
        report.append("")
        report.append(f"🚨 卡死任务: {stuck_count}个")
    
    # 质量评估
    report.append("")
    success_count = log_stats.get('success', 0)
    failed_count = log_stats.get('failed', 0)
    total = success_count + failed_count
    if total > 0:
        success_rate = success_count / total * 100
        report.append(f"📊 任务成功率: {success_rate:.1f}%")
        
        if success_rate >= 80:
            report.append("✅ 系统运行良好")
        elif success_rate >= 60:
            report.append("⚠️ 系统需要关注")
        else:
            report.append("🔴 系统需要紧急修复")
    
    return '\n'.join(report)


def send_feishu(message):
    """发送飞书通知"""
    payload = {"msg_type": "text", "content": {"text": message}}
    try:
        requests.post(FEISHU_WEBHOOK, json=payload, timeout=10)
    except Exception as e:
        print(f"飞书发送失败: {e}")


def main():
    print(f"[{datetime.now()}] task_monitor 启动")
    
    conn = psycopg2.connect(
        host='localhost',
        database='ecommerce_data',
        user='superuser',
        password='Admin123!'
    )
    
    state_stats, log_stats, failed_tasks, stuck_count = get_task_stats(conn)
    report = generate_report(state_stats, log_stats, failed_tasks, stuck_count)
    
    print(report)
    
    # 保存报告
    report_file = WORKSPACE / 'docs' / f'TASK_MONITOR_{datetime.now().strftime("%Y%m%d_%H%M")}.md'
    with open(report_file, 'w') as f:
        f.write(f"# 任务运行质量报告\n")
        f.write(f"生成时间: {datetime.now()}\n\n")
        f.write(report)
    
    # 发送飞书
    send_feishu(report)
    
    conn.close()
    print(f"[{datetime.now()}] task_monitor 完成")


if __name__ == '__main__':
    main()
