#!/bin/bash
echo "=== CommerceFlow 工作流前置条件检查 ==="
echo ""

# 条件1: 妙手Cookies
echo "[条件1] 妙手ERP Cookies"
COOKIES_FILE="/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json"
if [ -f "$COOKIES_FILE" ]; then
    # 检查文件更新时间（24小时内）
    FILE_AGE=$(($(date +%s) - $(stat -c %Y "$COOKIES_FILE" 2>/dev/null || echo 0)))
    if [ $FILE_AGE -lt 86400 ]; then
        echo "  ✅ Cookies文件存在 (更新于 $((FILE_AGE/3600)) 小时前)"
    else
        echo "  ⚠️ Cookies文件存在但超过24小时，可能需要更新"
    fi
else
    echo "  ❌ Cookies文件不存在"
fi

# 条件2: 本地服务
echo ""
echo "[条件2] 本地1688服务"
if python3 - <<'PY' > /tmp/health_check.json 2>&1
import json
import urllib.request

probe = urllib.request.Request(
    'http://127.0.0.1:8080/fetch-weight',
    data=json.dumps({'product_id': '1031400982378'}).encode(),
    headers={'Content-Type': 'application/json'}
)

with urllib.request.urlopen(probe, timeout=10) as resp:
    body = resp.read().decode('utf-8', errors='replace')
    print(body)
PY
then
    STATUS=$(cat /tmp/health_check.json)
    echo "  ✅ 本地服务正常"
    echo "     业务接口响应: $STATUS"
else
    echo "  ❌ 本地服务未启动或无响应"
fi

# 条件3: 隧道
echo ""
echo "[条件3] SSH隧道"
if ss -tlnp 2>/dev/null | grep -q "127.0.0.1:8080"; then
    echo "  ✅ 隧道已建立 (127.0.0.1:8080 LISTEN)"
else
    echo "  ❌ 隧道未建立"
fi

echo ""
echo "=== 检查完成 ==="
echo ""
echo "如果所有条件都满足，可以开始工作流。"
echo "如果有任何❌，请先解决相应问题。"
