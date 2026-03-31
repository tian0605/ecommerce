#!/bin/bash
# workflow_health_check.sh - 工作流健康巡检
# 定时执行，验证各模块状态

LOG_FILE="/root/.openclaw/workspace-e-commerce/logs/workflow_health_check.log"
FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"  # TODO: 替换为实际webhook

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

send_feishu() {
    local message="$1"
    curl -s -X POST "$FEISHU_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "{\"msg_type\":\"text\",\"content\":{\"text\":\"$message\"}}" \
        2>/dev/null
}

log "========================================="
log "🚀 工作流健康巡检开始"
log "========================================="

# 检查1: 前置条件
log "[检查1] 前置条件检查"

# 检查妙手Cookies
COOKIES_FILE="/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json"
if [ -f "$COOKIES_FILE" ]; then
    log "  ✅ 妙手Cookies存在"
else
    log "  ❌ 妙手Cookies不存在: $COOKIES_FILE"
    send_feishu "⚠️ 工作流巡检失败: 妙手Cookies不存在"
    exit 1
fi

# 检查本地1688服务
if python3 - <<'PY' > /tmp/health.json 2>&1
import json
import urllib.request

probe = urllib.request.Request(
    'http://127.0.0.1:8080/fetch-weight',
    data=json.dumps({'product_id': '1031400982378'}).encode(),
    headers={'Content-Type': 'application/json'}
)

with urllib.request.urlopen(probe, timeout=10) as resp:
    print(resp.read().decode('utf-8', errors='replace'))
PY
then
    log "  ✅ 本地1688服务正常"
else
    log "  ❌ 本地1688服务未启动"
    send_feishu "⚠️ 工作流巡检失败: 本地1688服务未启动"
    exit 1
fi

# 检查SSH隧道
if ss -tlnp 2>/dev/null | grep -q "127.0.0.1:8080"; then
    log "  ✅ SSH隧道已建立"
else
    log "  ❌ SSH隧道未建立"
    send_feishu "⚠️ 工作流巡检失败: SSH隧道未建立"
    exit 1
fi

# 检查2: 执行轻量级工作流测试
log "[检查2] 执行工作流测试"

cd /root/.openclaw/workspace-e-commerce

# 使用轻量级模式（跳过采集），测试已有商品
python3 skills/workflow_runner.py \
    --lightweight \
    --url "https://detail.1688.com/offer/1027205078815.html" \
    > /tmp/workflow_test.log 2>&1

TEST_RESULT=$?

if [ $TEST_RESULT -eq 0 ]; then
    log "  ✅ 工作流测试通过"
    
    # 提取关键结果
    SCRAPE_OK=$(grep -c "✅.*提取成功" /tmp/workflow_test.log 2>/dev/null || echo 0)
    WEIGHT_OK=$(grep -c "✅.*获取成功" /tmp/workflow_test.log 2>/dev/null || echo 0)
    
    log "  - 提取: $SCRAPE_OK"
    log "  - 重量获取: $WEIGHT_OK"
    
    send_feishu "✅ 工作流巡检通过

时间: $(date '+%Y-%m-%d %H:%M')
- 妙手Cookies: ✅
- 本地1688服务: ✅
- SSH隧道: ✅
- 工作流测试: ✅"
else
    log "  ❌ 工作流测试失败 (exit code: $TEST_RESULT)"
    
    # 提取错误信息
    ERROR=$(tail -20 /tmp/workflow_test.log 2>/dev/null | grep -E "Error|error|失败|❌" | head -3)
    
    log "  错误信息: $ERROR"
    
    send_feishu "⚠️ 工作流巡检失败

时间: $(date '+%Y-%m-%d %H:%M')
错误: $ERROR

请检查日志: /tmp/workflow_test.log"
fi

log "========================================="
log "🏁 巡检完成"
log "========================================="

exit $TEST_RESULT
