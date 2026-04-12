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

# 条件2: 本地1688服务（公网地址）
echo ""
echo "[条件2] 1688重量服务 (公网)"
SERVICE_URL="http://43.139.213.66:8080"
if python3 - <<'PY' > /tmp/health_check.json 2>&1
import json
import urllib.request

probe = urllib.request.Request(
    'http://43.139.213.66:8080/fetch-weight',
    data=json.dumps({'product_id': '1031400982378'}).encode(),
    headers={'Content-Type': 'application/json'}
)

with urllib.request.urlopen(probe, timeout=10) as resp:
    body = resp.read().decode('utf-8', errors='replace')
    print(body)
PY
then
    STATUS=$(cat /tmp/health_check.json)
    if echo "$STATUS" | grep -q '"success":true'; then
        echo "  ✅ 服务正常 (43.139.213.66:8080)"
        echo "     响应: $(echo $STATUS | python3 -c 'import sys,json; d=json.load(sys.stdin); print("商品:" + str(d.get("product_id","?")) + " SKU数:" + str(len(d.get("spec_list",[]))))')"
    else
        echo "  ⚠️ 服务响应异常"
        echo "     $STATUS"
    fi
else
    echo "  ❌ 服务无响应 (43.139.213.66:8080)"
fi

# 条件3: SSH隧道（已弃用，改用公网）
echo ""
echo "[条件3] SSH隧道"
echo "  ⏭️ 已弃用，改用公网地址 43.139.213.66:8080"

echo ""
echo "=== 检查完成 ==="
echo ""
echo "如果所有条件都满足，可以开始工作流。"
echo "如果有任何❌，请先解决相应问题。"
