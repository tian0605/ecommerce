#!/bin/bash
#
# 熔断机制脚本
# 连续5次失败后熔断30分钟
#

WORKSPACE="/root/.openclaw/workspace-e-commerce"
LOG_FILE="$WORKSPACE/logs/dev-heartbeat.log"
CIRCUIT_FILE="$WORKSPACE/logs/circuit_breaker.state"
MAX_FAILURES=5
COOLDOWN_MINUTES=30

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [熔断] $*" >> "$LOG_FILE"
}

# 读取当前状态
read_state() {
    if [ -f "$CIRCUIT_FILE" ]; then
        FAILURE_COUNT=$(grep "failure_count=" "$CIRCUIT_FILE" | cut -d= -f2)
        LAST_FAILURE=$(grep "last_failure=" "$CIRCUIT_FILE" | cut -d= -f2)
        STATE=$(grep "state=" "$CIRCUIT_FILE" | cut -d= -f2)
    else
        FAILURE_COUNT=0
        LAST_FAILURE=0
        STATE="closed"
    fi
}

# 写入状态
write_state() {
    echo "failure_count=$FAILURE_COUNT" > "$CIRCUIT_FILE"
    echo "last_failure=$LAST_FAILURE" >> "$CIRCUIT_FILE"
    echo "state=$STATE" >> "$CIRCUIT_FILE"
}

# 检查是否在熔断期
is_circuit_open() {
    if [ "$STATE" != "open" ]; then
        return 1
    fi
    
    # 检查熔断是否已过期
    local now=$(date +%s)
    local cooldown_end=$((LAST_FAILURE + COOLDOWN_MINUTES * 60))
    
    if [ $now -ge $cooldown_end ]; then
        # 熔断期结束，切换到半开状态
        STATE="half-open"
        FAILURE_COUNT=0
        write_state
        log "熔断恢复，进入半开状态"
        return 1
    fi
    
    local remaining=$((cooldown_end - now))
    log "熔断中，还剩 ${remaining} 秒"
    return 0
}

# 记录失败
record_failure() {
    FAILURE_COUNT=$((FAILURE_COUNT + 1))
    LAST_FAILURE=$(date +%s)
    
    if [ $FAILURE_COUNT -ge $MAX_FAILURES ]; then
        STATE="open"
        log "触发熔断！连续失败 $FAILURE_COUNT 次，熔断 $COOLDOWN_MINUTES 分钟"
    fi
    
    write_state
}

# 记录成功
record_success() {
    if [ "$STATE" = "half-open" ]; then
        log "熔断恢复成功，关闭熔断器"
        STATE="closed"
        FAILURE_COUNT=0
        write_state
    fi
}

# 主逻辑
main() {
    read_state
    
    # 检查是否有任务失败需要记录（通过参数传入）
    if [ "$1" = "failure" ]; then
        record_failure
        return 0
    elif [ "$1" = "success" ]; then
        record_success
        return 0
    fi
    
    # 检查熔断状态
    if is_circuit_open; then
        echo "熔断中，跳过任务执行"
        exit 1
    fi
    
    echo "熔断状态: $STATE (失败次数: $FAILURE_COUNT)"
    exit 0
}

main "$@"
