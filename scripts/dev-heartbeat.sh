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
    /usr/bin/python3 "$WORKSPACE/scripts/heartbeat_collector.py" --format text --persist
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
