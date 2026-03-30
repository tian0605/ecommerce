#!/bin/bash
# =============================================================
# check-preconditions.sh
# CommerceFlow 工作流前置条件检查（运行前必须全部通过）
# 使用方式: bash scripts/check-preconditions.sh
# =============================================================

WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_ENV="$WORKSPACE/config/config.env"
PASS=0
FAIL=0

echo "=== CommerceFlow 工作流前置条件检查 ==="
echo ""

# -----------------------------------------------------------
# 条件1: 妙手ERP Cookies
# -----------------------------------------------------------
echo "[条件1] 妙手ERP Cookies"

# 支持 config.env 中自定义路径，否则使用默认路径
COOKIES_FILE="/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json"
if [ -f "$CONFIG_ENV" ]; then
    _CF=$(grep '^MIAOSHOU_COOKIES_FILE=' "$CONFIG_ENV" | cut -d= -f2)
    [ -n "$_CF" ] && COOKIES_FILE="$_CF"
fi

if [ -f "$COOKIES_FILE" ]; then
    FILE_AGE=$(($(date +%s) - $(stat -c %Y "$COOKIES_FILE" 2>/dev/null || echo 0)))
    if [ "$FILE_AGE" -lt 86400 ]; then
        echo "  ✅ Cookies文件存在 (更新于 $((FILE_AGE/3600)) 小时前)"
        PASS=$((PASS+1))
    else
        echo "  ⚠️ Cookies文件存在但超过24小时，可能需要更新"
        FAIL=$((FAIL+1))
    fi
else
    echo "  ❌ Cookies文件不存在: $COOKIES_FILE"
    FAIL=$((FAIL+1))
fi

# -----------------------------------------------------------
# 条件2: 本地1688服务
# -----------------------------------------------------------
echo ""
echo "[条件2] 本地1688服务"
if curl -s --max-time 5 http://127.0.0.1:8080/health > /tmp/health_check.json 2>&1; then
    STATUS=$(cat /tmp/health_check.json)
    echo "  ✅ 本地服务正常"
    echo "     响应: $STATUS"
    PASS=$((PASS+1))
else
    echo "  ❌ 本地服务未启动或无响应 (http://127.0.0.1:8080/health)"
    FAIL=$((FAIL+1))
fi

# -----------------------------------------------------------
# 条件3: SSH隧道
# -----------------------------------------------------------
echo ""
echo "[条件3] SSH隧道"
if ss -tlnp 2>/dev/null | grep -qE "127\.0\.0\.1:8080|0\.0\.0\.0:8080"; then
    echo "  ✅ 隧道已建立 (127.0.0.1:8080 LISTEN)"
    PASS=$((PASS+1))
else
    echo "  ❌ 隧道未建立 (端口8080未监听)"
    FAIL=$((FAIL+1))
fi

# -----------------------------------------------------------
# 条件4: Python 关键依赖
# -----------------------------------------------------------
echo ""
echo "[条件4] Python 关键依赖"

PSYCOPG2_OK=0
PLAYWRIGHT_OK=0
REQUESTS_OK=0

if python3 -c "import psycopg2" 2>/dev/null; then
    echo "  ✅ psycopg2"
    PSYCOPG2_OK=1
else
    echo "  ❌ psycopg2  → pip3 install psycopg2-binary"
fi

if python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
    echo "  ✅ playwright"
    PLAYWRIGHT_OK=1
else
    echo "  ❌ playwright → pip3 install playwright && python3 -m playwright install chromium"
fi

if python3 -c "import requests" 2>/dev/null; then
    echo "  ✅ requests"
    REQUESTS_OK=1
else
    echo "  ❌ requests   → pip3 install requests"
fi

if [ "$PSYCOPG2_OK" -eq 1 ] && [ "$PLAYWRIGHT_OK" -eq 1 ] && [ "$REQUESTS_OK" -eq 1 ]; then
    PASS=$((PASS+1))
else
    echo "  ↳ 请运行: pip3 install -r requirements.txt"
    FAIL=$((FAIL+1))
fi

# -----------------------------------------------------------
# 条件5: 数据库连通性
# -----------------------------------------------------------
echo ""
echo "[条件5] 数据库连通性"

DB_HOST="localhost"
DB_NAME="ecommerce_data"
DB_USER="superuser"
DB_PASS="Admin123!"

if [ -f "$CONFIG_ENV" ]; then
    _H=$(grep '^DB_HOST='     "$CONFIG_ENV" | cut -d= -f2); [ -n "$_H" ] && DB_HOST="$_H"
    _N=$(grep '^DB_NAME='     "$CONFIG_ENV" | cut -d= -f2); [ -n "$_N" ] && DB_NAME="$_N"
    _U=$(grep '^DB_USER='     "$CONFIG_ENV" | cut -d= -f2); [ -n "$_U" ] && DB_USER="$_U"
    _P=$(grep '^DB_PASSWORD=' "$CONFIG_ENV" | cut -d= -f2); [ -n "$_P" ] && DB_PASS="$_P"
fi

if command -v psql &>/dev/null; then
    if PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
        -c "SELECT 1;" &>/dev/null; then
        echo "  ✅ 数据库连接成功 ($DB_USER@$DB_HOST/$DB_NAME)"
        PASS=$((PASS+1))
    else
        echo "  ❌ 数据库连接失败 ($DB_USER@$DB_HOST/$DB_NAME)"
        echo "     请检查 config/config.env 中的数据库配置"
        FAIL=$((FAIL+1))
    fi
else
    echo "  ⚠️ psql 未安装，跳过数据库连接检查"
    echo "     安装命令: apt-get install -y postgresql-client"
fi

# -----------------------------------------------------------
# 汇总
# -----------------------------------------------------------
echo ""
echo "=== 检查完成 ==="
echo ""
echo "  通过: $PASS 项  失败: $FAIL 项"
echo ""

if [ "$FAIL" -eq 0 ]; then
    echo "  ✅ 所有前置条件满足，可以开始工作流。"
else
    echo "  ❌ 有 $FAIL 项前置条件未满足，请先解决相应问题。"
    echo "  提示: 首次部署可运行 bash scripts/setup-remote-server.sh"
fi
echo ""
