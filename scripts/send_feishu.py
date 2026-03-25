#!/usr/bin/env python3
"""发送飞书通知"""
import sys
import json
import urllib.request

def send_feishu(webhook_url: str, message: str) -> bool:
    """发送飞书通知消息"""
    payload = {
        "msg_type": "text",
        "content": {"text": message}
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            if result.get('code') == 0 or result.get('StatusCode') == 0:
                return True
            print(f"发送失败: {result}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"发送异常: {e}", file=sys.stderr)
        return False

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("用法: send_feishu.py <webhook_url> <message>")
        sys.exit(1)
    
    webhook = sys.argv[1]
    message = sys.argv[2]
    
    if send_feishu(webhook, message):
        print("发送成功")
        sys.exit(0)
    else:
        sys.exit(1)
