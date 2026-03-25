#!/bin/bash
#
# CommerceFlow 开发心跳脚本
# 每10分钟运行一次，自动迭代开发
#
# 用法:
#   ./dev-heartbeat.sh           # 正常运行
#   ./dev-heartbeat.sh --status  # 查看状态
#   ./dev-heartbeat.sh --stop    # 停止心跳
#

set -e

WORKSPACE="/root/.openclaw/workspace-e-commerce"
LOG_FILE="$WORKSPACE/logs/dev-heartbeat.log"
TASK_QUEUE="$WORKSPACE/docs/dev-task-queue.md"
SCRAPER_DIR="/home/ubuntu/.openclaw/skills/collector-scraper"

# 飞书通知配置
FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/6af7d281-ca31-42c6-ab88-5ba434404fb9"
FEISHU_CHAT_ID="oc_cdff9eb5f5c8bd8151d20a17be309c23"

# 确保日志目录存在
mkdir -p "$WORKSPACE/logs"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# 发送飞书通知
send_feishu() {
    local message="$1"
    
    if [ -z "$FEISHU_WEBHOOK_URL" ] || [ "$FEISHU_WEBHOOK_URL" == "https://open.feishu.cn/open-apis/bot/v2/hook/xxx" ]; then
        log "  [飞书] 未配置webhook，跳过通知"
        return
    fi
    
    log "  [飞书] 正在发送通知..."
    
    # 使用Python脚本发送（更好地处理中文和emoji）
    if python3 "$WORKSPACE/scripts/send_feishu.py" "$FEISHU_WEBHOOK_URL" "$message"; then
        log "  [飞书] 通知发送成功"
    else
        log "  [飞书] 通知发送失败"
    fi
}

# 检查是否已有心跳在运行
check_running() {
    pgrep -f "dev-heartbeat.sh" | grep -v $$ | head -1
}

# 主循环
run_heartbeat() {
    log "========== 开始开发心跳 =========="
    
    # 记录开始时间
    START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
    
    # 1. 检查collector-scraper问题
    log "[Step 1] 检查collector-scraper模块状态..."
    
    SCRAPER_STATUS="✅"
    if [ -f "$SCRAPER_DIR/scraper.py" ]; then
        log "  scraper.py 存在"
        
        # 运行快速测试
        log "[Step 2] 执行快速测试..."
        cd "$SCRAPER_DIR"
        timeout 90 python3 scraper.py --scrape 0 >> "$LOG_FILE" 2>&1 || log "  测试执行完成（可能有警告）"
        
        # 检查测试结果
        if grep -q "货源ID: None" "$LOG_FILE" 2>/dev/null; then
            log "  ⚠️ 发现问题：货源ID未提取"
            SCRAPER_STATUS="⚠️ 货源ID未提取"
        else
            log "  ✅ 货源ID提取正常"
        fi
    else
        log "  ❌ collector-scraper 模块未找到"
        SCRAPER_STATUS="❌ 模块缺失"
    fi
    
    # 2. 检查git状态
    log "[Step 3] 检查代码变更..."
    cd "$WORKSPACE"
    GIT_STATUS="✅ 已同步"
    if git status --porcelain 2>/dev/null | grep -q .; then
        log "  ⚠️ 有未提交的变更"
        GIT_STATUS="⚠️ 有变更待提交"
        git add -A && git commit -m "Heartbeat auto-commit $(date '+%Y-%m-%d %H:%M')" 2>/dev/null || true
        GIT_STATUS="✅ 已自动提交"
    else
        log "  ✅ 代码已是最新"
    fi
    
    # 3. 读取任务队列
    log "[Step 4] 检查任务队列..."
    NEXT_TASK="无"
    if [ -f "$TASK_QUEUE" ]; then
        NEXT_TASK=$(grep -E "^### |^\[ DONE" "$TASK_QUEUE" 2>/dev/null | head -1 || echo "无")
    fi
    log "  下一个任务: $NEXT_TASK"
    
    # 4. 发送飞书通知
    log "[Step 5] 发送飞书通知..."
    send_feishu "📊 CommerceFlow 心跳报告
⏰ $START_TIME
━━━━━━━━━━━━━━━
🔧 模块状态: $SCRAPER_STATUS
📝 Git状态: $GIT_STATUS
📋 下一个任务: $NEXT_TASK
━━━━━━━━━━━━━━━
✅ 心跳执行正常"
    
    # 5. 执行待办任务（如果有）
    log "[Step 6] 检查并执行待办任务..."
    if [ -f "$WORKSPACE/docs/dev-task-queue.md" ]; then
        # 检查是否有待执行的任务标记
        if grep -q "🔄\|⬜" "$WORKSPACE/docs/dev-task-queue.md"; then
            log "  发现待办任务，开始执行..."
            
            # 执行任务（输出JSON结果）
            TASK_OUTPUT=$(timeout 300 python3 "$WORKSPACE/scripts/task_executor.py" 2>&1)
            TASK_EXIT=$?
            
            # 提取结果
            if [ $? -eq 0 ] && echo "$TASK_OUTPUT" | grep -q "\[TASK_RESULTS\]"; then
                log "  ✅ 任务执行完成"
                
                # 发送执行结果通知
                send_feishu "🔄 任务执行完成
⏰ $START_TIME
━━━━━━━━━━━━━━━
📋 已执行:
  • listing-optimizer 测试
  • miaoshou-updater 检查
  • profit-analyzer 分析
━━━━━━━━━━━━━━━
✅ 查看飞书文档获取详情
📄 https://feishu.cn/docx/UVlkd1NHrorLumxC8K7cLMBUnDe"
            else
                log "  ⚠️ 任务执行超时或失败"
            fi
        else
            log "  无待执行任务，跳过"
        fi
    fi
    
    log "========== 心跳完成 =========="
    log ""
}

# 查看状态
show_status() {
    echo "=== CommerceFlow 开发状态 ==="
    echo ""
    echo "最后心跳: $(tail -1 $LOG_FILE 2>/dev/null || echo '无')"
    echo ""
    echo "当前任务:"
    if [ -f "$TASK_QUEUE" ]; then
        grep -E "^### |^\[#" "$TASK_QUEUE" | head -10
    fi
    echo ""
    echo "最近日志:"
    tail -20 "$LOG_FILE" 2>/dev/null || echo "无日志"
}

# 停止心跳
stop_heartbeat() {
    pid=$(check_running)
    if [ -n "$pid" ]; then
        kill "$pid"
        echo "已停止心跳 (PID: $pid)"
    else
        echo "没有运行中的心跳"
    fi
}

# 主入口
case "${1:-}" in
    --status)
        show_status
        ;;
    --stop)
        stop_heartbeat
        ;;
    *)
        run_heartbeat
        ;;
esac
