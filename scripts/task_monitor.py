#!/usr/bin/env python3
"""
task_monitor.py - 任务运行质量监控

每6小时执行一次，分析任务执行日志，生成质量报告并发送飞书
"""
import sys
import os
import requests
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
sys.path.insert(0, str(WORKSPACE / 'scripts'))

import psycopg2

FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/6af7d281-ca31-42c6-ab88-5ba434404fb9"


# ==================== 根因检测规则 ====================
ERROR_ROOT_CAUSE_RULES = [
    # (error_pattern, severity, root_cause, fix_suggestion)
    (
        r"name '(\w+)' is not defined",
        "critical",
        "exec环境缺少依赖模块（{}）",
        "在subtask_executor的exec_globals中预加载常用模块：functools, logging, time, re, json"
    ),
    (
        r"ImportError: No module named '(\w+)'",
        "critical",
        "exec环境缺少模块（{}）",
        "在subtask_executor的exec_globals中添加缺失模块"
    ),
    (
        r"from functools import wraps",
        "warning",
        "代码使用了wraps装饰器但functools未预加载",
        "确保subtask_executor预加载functools模块"
    ),
    (
        r"共(\d+)个问题",
        "high",
        "主任务有\\1个步骤失败",
        "检查各子任务的exec_state和last_error，定位具体失败步骤"
    ),
    (
        r"LLM调用失败",
        "high",
        "LLM API调用异常",
        "检查LLM API配置、网络连接、API余额"
    ),
    (
        r"超时|timeout|Timeout",
        "medium",
        "任务执行超时",
        "增加超时时间或优化任务逻辑"
    ),
    (
        r"连接.*失败|Connection.*failed",
        "high",
        "外部服务连接失败",
        "检查服务可用性和网络连接"
    ),
    (
        r"数据库|database|PostgreSQL",
        "critical",
        "数据库操作异常",
        "检查数据库连接、权限、表结构"
    ),
    # ========== 浏览器/UI相关错误 ==========
    (
        r"未找到.*编辑按钮|button.*not.*found|selector.*not.*found",
        "high",
        "UI选择器未找到元素",
        "使用tavily-search搜索Playwright/选择器解决方案，或使用agent-browser诊断页面"
    ),
    (
        r"Element.*Not.*Found|element.*not.*visible|点击.*失败",
        "high",
        "浏览器元素操作失败",
        "使用tavily-search搜索Playwright等待元素解决方案"
    ),
    (
        r"page\.query_selector|playwright|Puppeteer",
        "medium",
        "浏览器自动化相关错误",
        "检查页面加载状态，增加waitForSelector等待元素"
    ),
    (
        r"写.*失败|write\(\).*str.*not.*int",
        "high",
        "文件写入类型错误",
        "检查写入函数参数类型，确保传入字符串"
    ),
]


# ==================== 增强分析函数 ====================
def search_solution_with_tavily(query: str, max_results: int = 3) -> str:
    """
    使用tavily-search搜索解决方案
    
    Args:
        query: 搜索关键词
        max_results: 最大结果数
    
    Returns:
        str: 搜索结果摘要
    """
    import subprocess
    workspace = Path('/root/.openclaw/workspace-e-commerce')
    tavily_key = os.environ.get('TAVILY_API_KEY', '')
    if not tavily_key:
        return "[tavily-search跳过: 未配置TAVILY_API_KEY]"
    
    try:
        result = subprocess.run(
            ['node', str(workspace / 'skills/tavily-search/scripts/search.mjs'), query, '-n', str(max_results)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(workspace)
        )
        if result.returncode == 0:
            return result.stdout[:500]
        else:
            return f"[tavily-search失败: {result.stderr[:100]}]"
    except Exception as e:
        return f"[tavily-search异常: {str(e)}]"


def diagnose_with_agent_browser(url: str, selector: str) -> str:
    """
    使用agent-browser诊断页面元素
    
    Args:
        url: 页面URL
        selector: CSS选择器
    
    Returns:
        str: 诊断结果
    """
    import subprocess
    workspace = Path('/root/.openclaw/workspace-e-commerce')
    
    try:
        # 打开页面并获取快照
        cmds = [
            ['agent-browser', 'open', url],
            ['agent-browser', 'snapshot', '-i'],
        ]
        for cmd in cmds:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(workspace))
            if result.returncode != 0:
                return f"[agent-browser失败: {result.stderr[:100]}]"
        
        return result.stdout[:500]
    except Exception as e:
        return f"[agent-browser异常: {str(e)}]"


def analyze_error_root_cause(error_msg: str) -> dict:
    """
    分析错误信息，匹配根因规则，返回结构化结果
    
    Returns:
        dict: {
            'matched': bool,
            'severity': str,
            'root_cause': str,
            'fix': str,
            'pattern': str
        }
    """
    if not error_msg:
        return {'matched': False}
    
    for pattern, severity, root_cause, fix in ERROR_ROOT_CAUSE_RULES:
        import re
        match = re.search(pattern, error_msg)
        if match:
            return {
                'matched': True,
                'severity': severity,
                'root_cause': root_cause.format(*match.groups()) if match.groups() else root_cause,
                'fix': fix,
                'pattern': pattern
            }
    
    return {'matched': False}


def get_root_cause_stats(conn):
    """
    获取失败任务的根因统计
    
    Returns:
        dict: {
            'total_failed': int,
            'by_root_cause': [(root_cause, count, severity), ...],
            'critical_issues': [task_name, ...]
        }
    """
    cur = conn.cursor()
    
    # 获取最近24小时的失败任务
    cur.execute("""
        SELECT task_name, last_error
        FROM tasks 
        WHERE exec_state IN ('ERROR_FIX_PENDING', 'REQUIRES_MANUAL')
          AND updated_at > NOW() - INTERVAL '24 hours'
        ORDER BY updated_at DESC
    """)
    failed_tasks = cur.fetchall()
    
    root_cause_count = {}
    critical_issues = []
    
    for task_name, error in failed_tasks:
        result = analyze_error_root_cause(error or '')
        if result['matched']:
            key = f"[{result['severity']}] {result['root_cause']}"
            root_cause_count[key] = root_cause_count.get(key, 0) + 1
            if result['severity'] == 'critical':
                critical_issues.append(task_name)
        else:
            # 未知错误
            error_preview = (error or '无错误信息')[:50]
            key = f"[unknown] {error_preview}"
            root_cause_count[key] = root_cause_count.get(key, 0) + 1
    
    cur.close()
    
    # 排序：critical > high > medium > warning > unknown
    def sort_key(item):
        cause = item[0]
        if cause.startswith('[critical]'):
            return (0, -item[1])
        elif cause.startswith('[high]'):
            return (1, -item[1])
        elif cause.startswith('[medium]'):
            return (2, -item[1])
        elif cause.startswith('[warning]'):
            return (3, -item[1])
        else:
            return (4, -item[1])
    
    sorted_causes = sorted(root_cause_count.items(), key=sort_key)
    
    return {
        'total_failed': len(failed_tasks),
        'by_root_cause': sorted_causes,
        'critical_issues': critical_issues
    }


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


def generate_report(state_stats, log_stats, failed_tasks, stuck_count, root_cause_data=None):
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
    
    # ==================== 根因分析（新增） ====================
    if root_cause_data and root_cause_data['total_failed'] > 0:
        report.append("")
        report.append("🔍 根因分析:")
        report.append(f"  失败任务总数: {root_cause_data['total_failed']}")
        
        for cause, count in root_cause_data['by_root_cause'][:5]:
            # 提取severity和root_cause
            if cause.startswith('[critical]'):
                severity_emoji = '🔴'
            elif cause.startswith('[high]'):
                severity_emoji = '🟠'
            elif cause.startswith('[medium]'):
                severity_emoji = '🟡'
            elif cause.startswith('[warning]'):
                severity_emoji = '⚠️'
            else:
                severity_emoji = '❓'
            
            # 提取根因文本
            root_text = cause.split('] ', 1)[1] if '] ' in cause else cause
            report.append(f"  {severity_emoji} {root_text} ({count}次)")
        
        # 关键问题
        if root_cause_data['critical_issues']:
            report.append("")
            report.append("🚨 关键问题需要立即修复:")
            for task in root_cause_data['critical_issues'][:3]:
                report.append(f"  - {task}")
            
            # 检查是否有可自动修复的问题
            exec_issue = any('exec环境' in cause for cause, _ in root_cause_data['by_root_cause'])
            if exec_issue:
                report.append("")
                report.append("💡 建议: 检测到exec环境问题，检查subtask_executor模块预加载配置")
    
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
    
    # 获取根因分析
    root_cause_data = get_root_cause_stats(conn)
    
    report = generate_report(state_stats, log_stats, failed_tasks, stuck_count, root_cause_data)
    
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
