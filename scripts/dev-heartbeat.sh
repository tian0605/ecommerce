#!/bin/bash
#
# CommerceFlow 心跳脚本
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

# 主执行
run_heartbeat() {
    log "========== 心跳开始 =========="
    
    # 生成心跳报告
    REPORT=$(python3 << 'PYEOF'
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')
from task_manager import TaskManager

tm = TaskManager()
import psycopg2
conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
cur = conn.cursor()

# 1. 获取任务状态统计
cur.execute("""
    SELECT exec_state, COUNT(*) 
    FROM tasks 
    GROUP BY exec_state
""")
state_stats = {row[0]: row[1] for row in cur.fetchall()}

# 2. 获取最近30分钟日志
cur.execute("""
    SELECT id, task_name, run_status, run_message, created_at
    FROM main_logs 
    WHERE created_at > NOW() - INTERVAL '30 minutes'
    ORDER BY id DESC
    LIMIT 20
""")
recent_logs = cur.fetchall()

# 3. 检查processing状态任务
cur.execute("""
    SELECT task_name, exec_state, last_executed_at
    FROM tasks 
    WHERE exec_state = 'processing'
""")
processing = cur.fetchall()

# 4. 检查error_fix_pending任务
cur.execute("""
    SELECT task_name, display_name, retry_count, last_error
    FROM tasks 
    WHERE exec_state = 'error_fix_pending'
""")
pending_fixes = cur.fetchall()

# 5. 检查following日志（正常运行中）
cur.execute("""
    SELECT COUNT(*) FROM main_logs 
    WHERE run_status = 'following' 
    AND created_at > NOW() - INTERVAL '10 minutes'
""")
following_count = cur.fetchone()[0]

cur.close()
conn.close()

# 生成报告
report = []

# 状态概览
report.append("💓 CommerceFlow 心跳报告")
report.append("")
report.append("📊 任务状态统计:")
for state, count in sorted(state_stats.items()):
    emoji = {
        'end': '✅',
        'processing': '🔄',
        'error_fix_pending': '🔧',
        'new': '🆕',
        'void': '❌'
    }.get(state, '❓')
    report.append(f"  {emoji} {state}: {count}")

report.append("")
report.append(f"🔄 processing任务: {len(processing)}")
for row in processing:
    report.append(f"  - {row[0]}: {row[2]}")

report.append("")
report.append(f"🔧 error_fix_pending任务: {len(pending_fixes)}")
for row in pending_fixes[:5]:
    report.append(f"  - {row[0]} (retry={row[2]}): {str(row[3])[:50] if row[3] else '无错误'}")

report.append("")
report.append(f"📝 最近30分钟日志: {len(recent_logs)}条")
if recent_logs:
    latest = recent_logs[0]
    report.append(f"  最新: ID:{latest[0]} {latest[2]} {latest[3][:50] if latest[3] else ''}")

report.append("")
if following_count > 0:
    report.append(f"✅ {following_count}个任务正在正常运行")
else:
    report.append("⚠️ 无正常运行中的任务")

print('\n'.join(report))
PYEOF
)

    echo "$REPORT"
    log "$REPORT"
    
    # 发送飞书
    send_feishu "$REPORT"
    
    log "========== 心跳完成 =========="
}

run_heartbeat
