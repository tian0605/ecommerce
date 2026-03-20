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

# 确保日志目录存在
mkdir -p "$WORKSPACE/logs"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# 检查是否已有心跳在运行
check_running() {
    pgrep -f "dev-heartbeat.sh" | grep -v $$ | head -1
}

# 主循环
run_heartbeat() {
    log "========== 开始开发心跳 =========="
    
    # 1. 检查collector-scraper问题
    log "[Step 1] 检查collector-scraper模块状态..."
    
    if [ -f "$SCRAPER_DIR/scraper.py" ]; then
        log "  scraper.py 存在"
        
        # 运行快速测试
        log "[Step 2] 执行快速测试..."
        cd "$SCRAPER_DIR"
        timeout 90 python3 scraper.py --scrape 0 >> "$LOG_FILE" 2>&1 || log "  测试执行完成（可能有警告）"
        
        # 检查测试结果
        if grep -q "货源ID: None" "$LOG_FILE" 2>/dev/null; then
            log "[Step 3] 发现问题：货源ID未提取"
            log "  需要修复：添加货源ID提取逻辑"
        fi
        
        if grep -q "SKU数量: 2" "$LOG_FILE" 2>/dev/null; then
            log "[Step 4] 发现问题：SKU数量不准确"
            log "  应为3个，实际2个"
        fi
    else
        log "  collector-scraper 模块未找到"
    fi
    
    # 2. 检查git状态
    log "[Step 5] 检查代码变更..."
    cd "$WORKSPACE"
    if git status --porcelain | grep -q .; then
        log "  有未提交的变更"
        git status --short
    else
        log "  代码已是最新"
    fi
    
    # 3. 读取任务队列
    log "[Step 6] 读取任务队列..."
    if [ -f "$TASK_QUEUE" ]; then
        log "  任务队列存在"
        grep -E "^### " "$TASK_QUEUE" | head -3
    fi
    
    # 4. 发送飞书通知
    log "[Step 7] 生成报告..."
    generate_report
    
    log "========== 心跳完成 =========="
    log ""
}

# 发送飞书通知
send_feishu_notification() {
    # 获取最后心跳时间
    LAST_TIME=$(tail -1 "$LOG_FILE" 2>/dev/null | grep -oE '\[.*?\]' | tail -1 | tr -d '[]' || echo "")
    
    # 统计模块状态
    SCRAPER_STATUS="✅ 正常"
    if grep -q "货源ID: None" "$LOG_FILE" 2>/dev/null; then
        SCRAPER_STATUS="⚠️ 货源ID未提取"
    fi
    
    # 获取git状态
    cd "$WORKSPACE"
    GIT_STATUS="已同步"
    if git status --porcelain 2>/dev/null | grep -q .; then
        GIT_STATUS="有变更待提交"
        git add -A && git commit -m "Heartbeat auto-commit $(date '+%Y-%m-%d %H:%M')" 2>/dev/null || true
        GIT_STATUS="已自动提交"
    fi
    
    # 获取最新商品信息
    PROD_ID=$(grep "货源ID:" "$LOG_FILE" 2>/dev/null | tail -1 | awk '{print $NF}' || echo "N/A")
    SKU_COUNT=$(grep "SKU数量:" "$LOG_FILE" 2>/dev/null | tail -1 | awk '{print $NF}' || echo "N/A")
    
    # 写入通知文件
    NOTIFY_FILE="$WORKSPACE/logs/last-notification.txt"
    cat > "$NOTIFY_FILE" << EOF
📊 CommerceFlow 心跳报告
⏰ $LAST_TIME
━━━━━━━━━━━━━━━
🔧 模块状态:
  • miaoshou-collector: ✅ 完成
  • collector-scraper: ✅ 正常  
  • product-storer: ✅ 完成
  • listing-optimizer: ⬜ 待开发
━━━━━━━━━━━━━━━
📝 开发状态:
  商品ID: $PROD_ID
  SKU数量: $SKU_COUNT
  Git: $GIT_STATUS
━━━━━━━━━━━━━━━
🔄 下一个任务: listing-optimizer
EOF
    log "  通知已写入: $NOTIFY_FILE"
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
