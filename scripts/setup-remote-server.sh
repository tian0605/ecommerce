#!/bin/bash
# =============================================================
# setup-remote-server.sh
# CommerceFlow 远程服务器环境一键初始化脚本
# 使用方式: bash scripts/setup-remote-server.sh
# =============================================================

set -e

# 必须以 root 权限运行（apt-get 等需要）
if [ "$(id -u)" -ne 0 ]; then
    echo "[ERROR] 请以 root 权限运行此脚本: sudo bash scripts/setup-remote-server.sh"
    exit 1
fi

WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
UBUNTU_HOME="/home/ubuntu"
SKILL_COOKIES_DIR="$UBUNTU_HOME/.openclaw/skills/miaoshou-collector"
WORK_DIR="$UBUNTU_HOME/work"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
section() { echo ""; echo -e "${GREEN}========== $* ==========${NC}"; }

# -----------------------------------------------------------
# 1. 系统依赖
# -----------------------------------------------------------
section "Step 1: 系统依赖检查与安装"

if command -v python3 &>/dev/null; then
    PYTHON_VER=$(python3 --version 2>&1)
    info "Python 已安装: $PYTHON_VER"
else
    warn "Python3 未安装，尝试安装..."
    apt-get update -qq && apt-get install -y python3 python3-pip python3-venv
fi

if command -v pip3 &>/dev/null; then
    info "pip3 已安装"
else
    warn "pip3 未安装，尝试安装..."
    apt-get install -y python3-pip
fi

if command -v psql &>/dev/null; then
    info "PostgreSQL 客户端已安装"
else
    warn "PostgreSQL 客户端未安装，尝试安装..."
    apt-get update -qq && apt-get install -y postgresql-client
fi

# -----------------------------------------------------------
# 2. Python 依赖
# -----------------------------------------------------------
section "Step 2: Python 依赖安装"

if [ -f "$WORKSPACE/requirements.txt" ]; then
    info "安装 requirements.txt 中的依赖..."
    pip3 install -q -r "$WORKSPACE/requirements.txt"
    info "Python 依赖安装完成"
else
    error "未找到 requirements.txt，跳过 Python 依赖安装"
fi

# -----------------------------------------------------------
# 3. Playwright 浏览器
# -----------------------------------------------------------
section "Step 3: Playwright Chromium 浏览器"

_install_playwright_chromium() {
    python3 -m playwright install chromium
    python3 -m playwright install-deps chromium 2>/dev/null || true
}

if python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
    info "Playwright 已安装"
    if python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    b.close()
" 2>/dev/null; then
        info "Playwright Chromium 浏览器可用"
    else
        warn "Playwright 已安装但浏览器不可用，尝试安装 Chromium..."
        _install_playwright_chromium
    fi
else
    warn "Playwright 未安装，尝试安装..."
    pip3 install -q playwright
    _install_playwright_chromium
fi

# -----------------------------------------------------------
# 4. 目录结构
# -----------------------------------------------------------
section "Step 4: 创建目录结构"

DIRS=(
    "$WORK_DIR/products"
    "$WORK_DIR/tmp"
    "$WORK_DIR/logs"
    "$WORK_DIR/config"
    "$SKILL_COOKIES_DIR"
    "$WORKSPACE/logs/miaoshou_updater_debug"
)

for dir in "${DIRS[@]}"; do
    mkdir -p "$dir"
    info "目录已就绪: $dir"
done

# -----------------------------------------------------------
# 5. 数据库连接验证
# -----------------------------------------------------------
section "Step 5: 数据库连接验证"

# 从 config.env 读取数据库配置
CONFIG_ENV="$WORKSPACE/config/config.env"
if [ -f "$CONFIG_ENV" ]; then
    DB_HOST=$(grep '^DB_HOST=' "$CONFIG_ENV" | cut -d= -f2)
    DB_NAME=$(grep '^DB_NAME=' "$CONFIG_ENV" | cut -d= -f2)
    DB_USER=$(grep '^DB_USER=' "$CONFIG_ENV" | cut -d= -f2)
    DB_PASS=$(grep '^DB_PASSWORD=' "$CONFIG_ENV" | cut -d= -f2)
else
    DB_HOST="${DB_HOST:-localhost}"
    DB_NAME="${DB_NAME:-ecommerce_data}"
    DB_USER="${DB_USER:-superuser}"
    DB_PASS="${DB_PASSWORD:-Admin123!}"
fi

if PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &>/dev/null; then
    info "数据库连接成功: $DB_USER@$DB_HOST/$DB_NAME"
else
    warn "数据库连接失败，请确认以下配置正确："
    warn "  主机: $DB_HOST"
    warn "  数据库: $DB_NAME"
    warn "  用户名: $DB_USER"
    warn "  如需修改，请编辑: $CONFIG_ENV"
fi

# -----------------------------------------------------------
# 6. 妙手 Cookies 检查
# -----------------------------------------------------------
section "Step 6: 妙手 ERP Cookies 检查"

COOKIES_FILE="$SKILL_COOKIES_DIR/miaoshou_cookies.json"
if [ -f "$COOKIES_FILE" ]; then
    FILE_AGE=$(( $(date +%s) - $(stat -c %Y "$COOKIES_FILE" 2>/dev/null || echo 0) ))
    if [ "$FILE_AGE" -lt 86400 ]; then
        info "Cookies 文件存在且有效（更新于 $((FILE_AGE / 3600)) 小时前）"
    else
        warn "Cookies 文件已超过24小时，需要刷新"
        warn "  请在本地 Chrome 登录妙手ERP后导出 Cookies 并上传到:"
        warn "  $COOKIES_FILE"
    fi
else
    warn "Cookies 文件不存在: $COOKIES_FILE"
    warn "  请在本地 Chrome 登录妙手ERP后导出 Cookies 并上传到:"
    warn "  $COOKIES_FILE"
    warn "  参考: docs/preconditions-checklist.md"
fi

# -----------------------------------------------------------
# 7. 本地1688服务 & SSH隧道检查
# -----------------------------------------------------------
section "Step 7: 本地1688服务 & SSH隧道"

if curl -s --max-time 5 http://127.0.0.1:8080/health &>/dev/null; then
    info "本地1688服务已运行（端口 8080）"
else
    warn "本地1688服务未启动"
    warn "  请在本地机器启动服务: python local-1688-weight-server.py"
    warn "  并通过 MobaXterm / ssh -L 8080:127.0.0.1:8080 建立隧道"
fi

if ss -tlnp 2>/dev/null | grep -q "127.0.0.1:8080\|0.0.0.0:8080"; then
    info "SSH 隧道已建立（端口 8080 监听中）"
else
    warn "SSH 隧道未建立（端口 8080 未监听）"
    warn "  MobaXterm隧道配置: Local 8080 → 127.0.0.1:8080"
fi

# -----------------------------------------------------------
# 8. 汇总
# -----------------------------------------------------------
section "初始化汇总"

echo ""
echo "  项目路径: $WORKSPACE"
echo "  配置文件: $CONFIG_ENV"
echo "  Cookies:  $COOKIES_FILE"
echo ""
echo "  下一步: 运行前置条件检查"
echo "  命令:   bash scripts/check-preconditions.sh"
echo ""
info "远程服务器环境初始化完成！"
