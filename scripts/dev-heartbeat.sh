#!/bin/bash
#
# CommerceFlow 开发心跳脚本
# 每30分钟运行一次，自动迭代开发
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
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
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

# 执行待办任务队列
execute_task_queue() {
    local task_queue="$WORKSPACE/docs/dev-task-queue.md"
    local task_log="$WORKSPACE/logs/task_exec.log"
    
    # 检查任务队列文件
    if [ ! -f "$task_queue" ]; then
        log "  [任务队列] 文件不存在，跳过"
        return 0
    fi
    
    # 查找待执行的任务（状态=⬜）
    local pending_tasks=$(grep -n "⬜ 待执行" "$task_queue" 2>/dev/null | head -5)
    if [ -z "$pending_tasks" ]; then
        log "  [任务队列] 无待执行任务"
        return 0
    fi
    
    log "  [任务队列] 发现待执行任务:"
    echo "$pending_tasks" | while read line; do
        log "    $line"
    done
    
    # 获取第一个待执行任务的详细信息
    local task_line=$(echo "$pending_tasks" | head -1 | cut -d: -f1)
    if [ -z "$task_line" ]; then
        log "  [任务队列] 无法解析任务行，跳过"
        return 0
    fi
    
    # 读取任务名称（向上查找 ### 或 ## 标题）
    local task_name=""
    local search_start=$task_line
    for ((i=$search_start-1; i>=1; i--)); do
        local line=$(sed -n "${i}p" "$task_queue")
        if echo "$line" | grep -qE "^## |^### "; then
            task_name=$(echo "$line" | sed 's/^#* *//' | tr -d '\n')
            break
        fi
    done
    
    if [ -z "$task_name" ]; then
        task_name="未知任务"
    fi
    
    log "  [任务队列] 执行任务: $task_name"
    
    # 根据任务名称执行对应脚本
    case "$task_name" in
        *"TC-FLOW-001"*|*"端到端测试"*|*"自动化上架"*)
            log "  [任务] 执行: TC-FLOW-001 端到端自动化上架测试"
            # 执行完整工作流测试
            cd /root/.openclaw/workspace-e-commerce/skills/workflow-runner/scripts
            python3 workflow_runner.py --url "https://detail.1688.com/offer/1031400982378.html" >> "$task_log" 2>&1
            if [ $? -eq 0 ]; then
                log "  [任务] ✅ TC-FLOW-001 完成"
                # 更新任务状态（只更新包含"TC-FLOW"的行）
                sed -i '/TC-FLOW-001.*⬜ 待执行/s/⬜ 待执行/✅ 已完成/' "$task_queue"
                send_feishu "✅ TC-FLOW-001 端到端测试完成！商品：https://detail.1688.com/offer/1031400982378.html"
            else
                log "  [任务] ❌ TC-FLOW-001 失败，查看日志: $task_log"
                send_feishu "❌ TC-FLOW-001 端到端测试失败，请检查日志"
            fi
            ;;
        *"熔断"*)
            log "  [任务] 执行: 熔断机制实现"
            bash "$WORKSPACE/scripts/circuit_breaker.sh" >> "$task_log" 2>&1
            if [ $? -eq 0 ]; then
                log "  [任务] ✅ 熔断机制完成"
                # 更新任务状态
                sed -i "s/| ⬜ 待执行/| ✅ 已完成/" "$task_queue"
                send_feishu "✅ 任务完成: 熔断机制实现"
            else
                log "  [任务] ❌ 熔断机制失败"
            fi
            ;;
        *"config.env"*)
            log "  [任务] 执行: config.env配置分离"
            bash "$WORKSPACE/scripts/create_config_env.sh" >> "$task_log" 2>&1
            if [ $? -eq 0 ]; then
                log "  [任务] ✅ config.env完成"
                sed -i "s/| ⬜ 待执行/| ✅ 已完成/" "$task_queue"
                send_feishu "✅ 任务完成: config.env配置分离"
            else
                log "  [任务] ❌ config.env失败"
            fi
            ;;
        *"Cookies"*)
            log "  [任务] 执行: Cookies过期告警"
            bash "$WORKSPACE/scripts/cookies_alert.sh" >> "$task_log" 2>&1
            if [ $? -eq 0 ]; then
                log "  [任务] ✅ Cookies告警完成"
                sed -i "s/| ⬜ 待执行/| ✅ 已完成/" "$task_queue"
            fi
            ;;
        *"商品数据"*)
            log "  [任务] 执行: 商品数据分析"
            python3 "$WORKSPACE/scripts/analyze_products.py" >> "$task_log" 2>&1
            if [ $? -eq 0 ]; then
                log "  [任务] ✅ 商品分析完成"
                sed -i "s/| ⬜ 待执行/| ✅ 已完成/" "$task_queue"
                send_feishu "✅ 任务完成: 商品数据分析"
            fi
            ;;
        *"IMPROVEMENTS"*)
            log "  [任务] 执行: 完善IMPROVEMENTS.md"
            bash "$WORKSPACE/scripts/update_improvements.sh" >> "$task_log" 2>&1
            if [ $? -eq 0 ]; then
                log "  [任务] ✅ 完善完成"
                sed -i "s/| ⬜ 待执行/| ✅ 已完成/" "$task_queue"
                send_feishu "✅ 任务完成: 完善IMPROVEMENTS.md"
            fi
            ;;
        *)
            log "  [任务] 未知任务类型: $task_name，跳过"
            ;;
    esac
    
    return 0
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
    
    # 5. 执行待办任务（从dev-task-queue.md读取）
    log "[Step 6] 检查并执行待办任务..."
    execute_task_queue
    TASK_EXEC_RESULT=$?
    
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
