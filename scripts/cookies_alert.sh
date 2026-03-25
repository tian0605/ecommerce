#!/bin/bash
#
# Cookies过期告警脚本
# 检查Cookies文件年龄，超过20小时发送预警
#

WORKSPACE="/root/.openclaw/workspace-e-commerce"
LOG_FILE="$WORKSPACE/logs/dev-heartbeat.log"
FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/6af7d281-ca31-42c6-ab88-5ba434404fb9"
COOKIES_FILE="/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Cookies告警] $*" >> "$LOG_FILE"
}

# 发送飞书通知
send_feishu() {
    local message="$1"
    python3 -c "
import requests
import json

webhook = '$FEISHU_WEBHOOK_URL'
data = {
    'msg_type': 'text',
    'content': {'text': '$message'}
}
try:
    r = requests.post(webhook, json=data, timeout=10)
    print('发送成功' if r.status_code == 200 else '发送失败')
except Exception as e:
    print(f'发送异常: {e}')
"
}

log "开始检查Cookies状态..."

# 检查Cookies文件是否存在
if [ ! -f "$COOKIES_FILE" ]; then
    log "Cookies文件不存在: $COOKIES_FILE"
    send_feishu "⚠️ Cookies文件不存在，请检查配置"
    echo "文件不存在"
    exit 1
fi

# 获取文件年龄（秒）
FILE_AGE=$(stat -c %Y "$COOKIES_FILE" 2>/dev/null)
CURRENT_TIME=$(date +%s)
AGE_SECONDS=$((CURRENT_TIME - FILE_AGE))
AGE_HOURS=$((AGE_SECONDS / 3600))
AGE_MINUTES=$(( (AGE_SECONDS % 3600) / 60 ))

log "Cookies文件年龄: ${AGE_HOURS}小时${AGE_MINUTES}分钟"

# 检查是否超过20小时
if [ $AGE_HOURS -ge 20 ]; then
    log "⚠️ Cookies已过期（${AGE_HOURS}小时），发送告警..."
    send_feishu "⚠️ 【告警】妙手ERP Cookies已过期
⏰ 当前年龄: ${AGE_HOURS}小时${AGE_MINUTES}分钟
📋 请重新导出Cookies文件
🔗 路径: $COOKIES_FILE"
    echo "已发送告警"
else
    log "✅ Cookies状态正常（${AGE_HOURS}小时${AGE_MINUTES}分钟）"
    echo "正常"
fi

exit 0
