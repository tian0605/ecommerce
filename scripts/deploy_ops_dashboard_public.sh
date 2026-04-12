#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/root/.openclaw/workspace-e-commerce"
WEB_DIR="$ROOT_DIR/apps/ops-web"
DIST_DIR="$WEB_DIR/dist"
TARGET_DIR="/var/www/ops-dashboard"
NGINX_CONF_SOURCE="$ROOT_DIR/deploy/nginx/ops-dashboard.conf"
NGINX_CONF_TARGET="/etc/nginx/conf.d/ops-dashboard.conf"
SYSTEMD_SOURCE="$ROOT_DIR/deploy/systemd/ops-dashboard-api.service"
SYSTEMD_TARGET="/etc/systemd/system/ops-dashboard-api.service"
ENV_SOURCE="$ROOT_DIR/deploy/env/ops-dashboard.env.example"
ENV_TARGET="/etc/openclaw/ops-dashboard.env"

mkdir -p /etc/openclaw
mkdir -p "$TARGET_DIR"

if [[ ! -f "$ENV_TARGET" ]]; then
  cp "$ENV_SOURCE" "$ENV_TARGET"
  chmod 600 "$ENV_TARGET"
fi

cp "$NGINX_CONF_SOURCE" "$NGINX_CONF_TARGET"
cp "$SYSTEMD_SOURCE" "$SYSTEMD_TARGET"

cd "$WEB_DIR"
npm run build

rsync -a --delete "$DIST_DIR/" "$TARGET_DIR/"

systemctl daemon-reload
systemctl enable ops-dashboard-api.service
systemctl restart ops-dashboard-api.service

nginx -t
systemctl reload nginx

if command -v ufw >/dev/null 2>&1; then
  ufw allow 8088/tcp >/dev/null 2>&1 || true
fi

echo "Public dashboard deployed on port 8088"