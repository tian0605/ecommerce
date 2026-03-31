#!/usr/bin/env python3
"""发送飞书通知"""
import sys

from notification_service import send_feishu_text

def send_feishu(webhook_url: str, message: str) -> bool:
    """发送飞书通知消息"""
    return send_feishu_text(message=message, webhook_url=webhook_url)

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
