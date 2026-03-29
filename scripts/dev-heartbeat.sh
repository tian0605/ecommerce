#!/bin/bash
#
# CommerceFlow 心跳脚本（task-manager 整合版）
#
# 基于 HEARTBEAT.md 规范
# 监控 task_manager 产出结果，只做检测和报告，不执行任务
#
# 任务执行由 prod_task_cron.py 负责
# 心跳只负责监控和分析
#

WORKSPACE="/root/.openclaw/workspace-e-commerce"
LOG_FILE="$WORKSPACE/logs/dev-heartbeat.log"
FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/6af7d281-ca31-42c6-ab88-5ba434404fb9"

mkdir -p "$WORKSPACE/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

send_feishu() {
    local message="$1"
    python3 -c "
import urllib.request
import json
msg = '''$message'''
webhook = '$FEISHU_WEBHOOK_URL'
payload = {'msg_type': 'text', 'content': {'text': msg}}
req = urllib.request.Request(webhook, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as resp:
    print(resp.read().decode())
" 2>/dev/null || log "飞书发送失败"
}

# ============================================================
# 生成心跳报告（Python版本）
# ============================================================
generate_report() {
    python3 << 'PYEOF'
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')
from task_manager import TaskManager
import psycopg2

tm = TaskManager()
conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
cur = conn.cursor()

# ========== 第一问：有没有需要处理的任务？ ==========

# 获取所有可执行任务
actionable = tm.get_actionable_tasks(limit=50)

# 按优先级分类
p0_tasks = [t for t in actionable if t.get('priority') == 'P0']
p1_tasks = [t for t in actionable if t.get('priority') == 'P1']
p2_tasks = [t for t in actionable if t.get('priority') == 'P2']

# 检查processing状态
cur.execute("""
    SELECT task_name, exec_state, last_executed_at
    FROM tasks 
    WHERE exec_state = 'PROCESSING'
""")
processing = cur.fetchall()

# 检查requires_manual状态
cur.execute("""
    SELECT task_name, display_name, fix_suggestion
    FROM tasks 
    WHERE exec_state = 'REQUIRES_MANUAL'
""")
manual_tasks = cur.fetchall()

# ========== 临时任务（TEMP）超时检测 ==========
overtime_temp = tm.get_overtime_temp_tasks(buffer_minutes=10)

# 自动重置超时任务（让其可以被重新执行）
for ot in overtime_temp:
    tm.reactivate_temp_task(ot['task_name'])

# ========== 第二问：任务执行是否顺畅？ ==========

# 检查最近24小时日志统计
cur.execute("""
    SELECT run_status, COUNT(*)
    FROM main_logs
    WHERE created_at > NOW() - INTERVAL '24 hours'
    GROUP BY run_status
""")
stats = {row[0]: row[1] for row in cur.fetchall()}

# 检查最近失败的任务
cur.execute("""
    SELECT task_name, exec_state, retry_count, last_error
    FROM tasks 
    WHERE exec_state IN ('ERROR_FIX_PENDING', 'NORMAL_CRASH')
    AND updated_at > NOW() - INTERVAL '24 hours'
    ORDER BY updated_at DESC
    LIMIT 5
""")
failed_recent = cur.fetchall()

cur.close()
conn.close()
tm.close()

# ========== 生成报告 ==========

report = []
report.append("💓 CommerceFlow 心跳报告")
report.append("")
report.append("📋 第一问：有没有需要处理的任务？")

if p0_tasks:
    report.append("")
    report.append(f"🔴 P0 立即处理 ({len(p0_tasks)} 个)")
    for t in p0_tasks:
        report.append(f"  - {t['task_name']} ({t.get('display_name', '')}) - {t['exec_state']}")

if p1_tasks:
    report.append("")
    report.append(f"🟡 P1 今天处理 ({len(p1_tasks)} 个)")
    for t in p1_tasks[:5]:
        report.append(f"  - {t['task_name']}")

if p2_tasks:
    report.append("")
    report.append(f"🟢 P2 本周优化 ({len(p2_tasks)} 个)")

if manual_tasks:
    report.append("")
    report.append(f"🚨 需要人工介入 ({len(manual_tasks)} 个)")
    for t in manual_tasks[:3]:
        report.append(f"  - {t[0]}: {str(t[2])[:50] if t[2] else ''}")

if overtime_temp:
    report.append("")
    report.append(f"⏰ 临时任务超时 ({len(overtime_temp)} 个)")
    for t in overtime_temp[:5]:
        cp = t.get('progress_checkpoint', {})
        if isinstance(cp, str):
            try:
                import json
                cp = json.loads(cp)
            except:
                cp = {}
        current_step = cp.get('current_step', '未知') if cp else '未知'
        report.append(f"  - {t['task_name']}: 超时{int(t.get('overtime_minutes', 0))}分钟 | 当前: {current_step}")
        report.append(f"    断点: {json.dumps(cp) if cp else '无'}")

report.append("")
report.append("----------")
report.append("")
report.append("📊 第二问：任务执行是否顺畅？")
report.append("")
report.append("执行统计（24小时）：")
report.append(f"  🔄 running: {stats.get('running', 0)}")
report.append(f"  ✅ success: {stats.get('success', 0)}")
report.append(f"  ❌ failed: {stats.get('failed', 0)}")
report.append(f"  👀 following: {stats.get('following', 0)}")
report.append(f"  ⏭️  skipped: {stats.get('skipped', 0)}")

if failed_recent:
    report.append("")
    report.append("⚠️ 最近失败任务：")
    for f in failed_recent[:3]:
        report.append(f"  - {f[0]} ({f[1]}, retry={f[2]})")

report.append("")
report.append("----------")
report.append("")

# 汇总
total_tasks = len(p0_tasks) + len(p1_tasks) + len(p2_tasks)
report.append(f"📈 汇总：待处理:{total_tasks} | 运行中:{len(processing)} | 需人工:{len(manual_tasks)} | 超时TEMP:{len(overtime_temp)}")

# 回复格式（符合HEARTBEAT.md规范）
if total_tasks == 0 and len(processing) == 0 and len(manual_tasks) == 0 and len(overtime_temp) == 0:
    report.append("")
    report.append("HEARTBEAT_OK | 待处理:0 | 运行中:0 | 需要人工:0")

print('\n'.join(report))
PYEOF
}

# ============================================================
# 主执行
# ============================================================
run_heartbeat() {
    log "========== 心跳开始 =========="
    
    REPORT=$(generate_report)
    
    echo "$REPORT"
    log "$REPORT"
    
    # 发送飞书
    send_feishu "$REPORT"
    
    log "========== 心跳完成 =========="
}

run_heartbeat
