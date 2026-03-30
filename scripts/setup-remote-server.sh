#!/bin/bash
# =============================================================
# setup-remote-server.sh
#
# 一键初始化远程服务器 43.139.213.66 的 CommerceFlow 调试环境
#
# 执行方式（在远程服务器上运行）：
#   bash setup-remote-server.sh
#
# 或从本地一键部署：
#   ssh root@43.139.213.66 'bash -s' < scripts/setup-remote-server.sh
# =============================================================

set -e

REPO_URL="git@github.com:tian0605/ecommerce.git"
WORKSPACE="/root/.openclaw/workspace-e-commerce"
SCRIPTS_DIR="$WORKSPACE/scripts"
CONFIG_DIR="$WORKSPACE/config"
SKILLS_DIR="$WORKSPACE/skills"
LOG_DIR="$WORKSPACE/logs"
TMP_DIR="/home/ubuntu/work/tmp"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
section() { echo ""; echo -e "${GREEN}========== $* ==========${NC}"; echo ""; }

# =============================================================
# Step 0: 确认运行环境
# =============================================================
section "Step 0: 检查运行环境"

[[ $(id -u) -eq 0 ]] || error "请以 root 用户运行此脚本"
OS=$(lsb_release -si 2>/dev/null || echo "unknown")
info "操作系统: $OS $(lsb_release -sr 2>/dev/null)"
info "Python 版本: $(python3 --version 2>&1)"

# =============================================================
# Step 1: 系统依赖
# =============================================================
section "Step 1: 安装系统依赖"

apt-get update -qq
apt-get install -y -qq \
    git curl wget \
    python3 python3-pip python3-venv \
    postgresql-client \
    build-essential libpq-dev \
    xvfb \
    jq

info "系统依赖安装完成"

# =============================================================
# Step 2: Python 依赖
# =============================================================
section "Step 2: 安装 Python 依赖"

pip3 install -q --upgrade pip

pip3 install -q \
    psycopg2-binary \
    playwright \
    requests \
    beautifulsoup4 \
    lxml \
    aiohttp \
    pyyaml \
    openpyxl \
    pandas

# 安装 Playwright 浏览器
python3 -m playwright install chromium --with-deps 2>/dev/null || true

info "Python 依赖安装完成"

# =============================================================
# Step 3: 目录结构
# =============================================================
section "Step 3: 创建目录结构"

mkdir -p "$WORKSPACE"
mkdir -p "$SCRIPTS_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$SKILLS_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$TMP_DIR"
mkdir -p "/home/ubuntu/.openclaw/skills/miaoshou-collector"
mkdir -p "/home/ubuntu/work/tmp/product_storer_test"

info "目录创建完成: $WORKSPACE"

# =============================================================
# Step 4: 克隆或更新代码
# =============================================================
section "Step 4: 同步代码（GitHub → 服务器）"

if [ -d "$WORKSPACE/.git" ]; then
    info "代码已存在，执行 git pull ..."
    cd "$WORKSPACE"
    git pull origin master
    info "代码已更新到最新版本"
else
    info "首次克隆代码 ..."
    # 先尝试 SSH，失败则提示
    if git clone "$REPO_URL" "$WORKSPACE" 2>/dev/null; then
        info "代码克隆完成（SSH）"
    else
        warn "SSH 克隆失败，请确保服务器 SSH 公钥已添加到 GitHub"
        warn "公钥路径: ~/.ssh/id_rsa.pub"
        warn "手动执行: git clone $REPO_URL $WORKSPACE"
    fi
fi

# =============================================================
# Step 5: 配置文件检查
# =============================================================
section "Step 5: 验证配置文件"

CONFIG_FILE="$CONFIG_DIR/config.env"
if [ -f "$CONFIG_FILE" ]; then
    info "config.env 已存在"
    # 显示当前 DB 配置（隐藏密码）
    DB_HOST=$(grep '^DB_HOST=' "$CONFIG_FILE" | cut -d= -f2)
    DB_NAME=$(grep '^DB_NAME=' "$CONFIG_FILE" | cut -d= -f2)
    DB_USER=$(grep '^DB_USER=' "$CONFIG_FILE" | cut -d= -f2)
    info "  DB_HOST=$DB_HOST | DB_NAME=$DB_NAME | DB_USER=$DB_USER"
else
    warn "config.env 不存在，请从仓库同步或手动创建"
fi

# =============================================================
# Step 6: PostgreSQL 数据库检查
# =============================================================
section "Step 6: 检查 PostgreSQL 连接"

DB_HOST=$(grep '^DB_HOST=' "$CONFIG_FILE" 2>/dev/null | cut -d= -f2 || echo "localhost")
DB_PORT=$(grep '^DB_PORT=' "$CONFIG_FILE" 2>/dev/null | cut -d= -f2 || echo "5432")
DB_NAME=$(grep '^DB_NAME=' "$CONFIG_FILE" 2>/dev/null | cut -d= -f2 || echo "ecommerce_data")
DB_USER=$(grep '^DB_USER=' "$CONFIG_FILE" 2>/dev/null | cut -d= -f2 || echo "superuser")
DB_PASS=$(grep '^DB_PASSWORD=' "$CONFIG_FILE" 2>/dev/null | cut -d= -f2 || echo "Admin123!")

if PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
    info "✅ PostgreSQL 连接成功（$DB_HOST:$DB_PORT/$DB_NAME）"
else
    warn "❌ PostgreSQL 连接失败，请检查："
    warn "   1. PostgreSQL 是否已启动: systemctl status postgresql"
    warn "   2. 数据库/用户是否存在"
    warn "   3. config.env 中的连接参数是否正确"
fi

# =============================================================
# Step 7: crontab 设置
# =============================================================
section "Step 7: 配置定时任务（crontab）"

PYTHON3=$(which python3)
CRON_TEMP=$(mktemp)

# 备份现有 crontab
crontab -l 2>/dev/null > "$CRON_TEMP" || true

# 检查是否已配置
if grep -q "prod_task_cron" "$CRON_TEMP"; then
    info "crontab 已配置，跳过"
else
    cat >> "$CRON_TEMP" << EOF

# ===== CommerceFlow 自动任务 (setup-remote-server.sh 自动生成) =====
# 常规任务 & 临时任务：每10分钟
*/10 * * * * $PYTHON3 $SCRIPTS_DIR/prod_task_cron.py >> $LOG_DIR/prod_task_cron.log 2>&1
# 修复任务：每1分钟
*/1 * * * * $PYTHON3 $SCRIPTS_DIR/fix_task_cron.py >> $LOG_DIR/fix_task_cron.log 2>&1
# 心跳检查：每30分钟
*/30 * * * * bash $SCRIPTS_DIR/dev-heartbeat.sh >> $LOG_DIR/dev-heartbeat.log 2>&1
# 健康检查：每2小时
0 */2 * * * bash $SCRIPTS_DIR/workflow_health_check.sh >> $LOG_DIR/workflow_health_check.log 2>&1
# 日志同步：每10分钟
*/10 * * * * $PYTHON3 $SCRIPTS_DIR/sync_logs_to_feishu.py >> $LOG_DIR/sync_logs.log 2>&1
EOF
    crontab "$CRON_TEMP"
    info "crontab 配置完成"
fi
rm -f "$CRON_TEMP"

# =============================================================
# Step 8: SSH 公钥检查（GitHub 绑定）
# =============================================================
section "Step 8: SSH 公钥（GitHub 绑定）"

if [ -f ~/.ssh/id_rsa.pub ] || [ -f ~/.ssh/id_ed25519.pub ]; then
    PUB_KEY=$(cat ~/.ssh/id_rsa.pub 2>/dev/null || cat ~/.ssh/id_ed25519.pub 2>/dev/null)
    info "✅ SSH 公钥已存在"
    info "   如果尚未绑定 GitHub，请将以下公钥添加到："
    info "   https://github.com/settings/keys"
    echo ""
    echo "$PUB_KEY"
    echo ""
else
    warn "SSH 公钥不存在，正在生成..."
    # Note: -N "" generates key without passphrase for automation purposes.
    # For higher security, run 'ssh-keygen -t ed25519' manually and set a passphrase.
    ssh-keygen -t ed25519 -C "root@43.139.213.66" -f ~/.ssh/id_ed25519 -N "" -q
    info "✅ SSH 公钥已生成"
    info "   请将以下公钥添加到 GitHub: https://github.com/settings/keys"
    echo ""
    cat ~/.ssh/id_ed25519.pub
    echo ""
fi

# 测试 GitHub SSH 连接
if ssh -T git@github.com -o StrictHostKeyChecking=no 2>&1 | grep -q "successfully authenticated"; then
    info "✅ GitHub SSH 连接正常"
else
    warn "⚠️ GitHub SSH 连接待验证（如已绑定可忽略）"
fi

# =============================================================
# Step 9: 前置条件检查
# =============================================================
section "Step 9: 前置条件检查"

bash "$SCRIPTS_DIR/check-preconditions.sh" 2>/dev/null || warn "前置条件检查脚本未找到，跳过"

# =============================================================
# 完成
# =============================================================
section "🎉 远程服务器初始化完成"

echo ""
echo "下一步操作："
echo "  1. 如果 PostgreSQL 未连接，先检查数据库状态"
echo "  2. 上传妙手 cookies: scp miaoshou_cookies.json root@43.139.213.66:/home/ubuntu/.openclaw/skills/miaoshou-collector/"
echo "  3. 确认 SSH 隧道（本地 Windows 1688 服务）已建立"
echo "  4. 运行调试: python3 $SKILLS_DIR/miaoshou-updater/updater.py --product-id <ID>"
echo ""
echo "查看日志:"
echo "  tail -f $LOG_DIR/prod_task_cron.log"
echo "  tail -f $LOG_DIR/dev-heartbeat.log"
echo ""
