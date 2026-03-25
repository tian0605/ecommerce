#!/usr/bin/env python3
"""
飞书发送图片脚本
用法: python feishu_send_image.py <图片路径> <目标chat_id>
"""
import sys
import requests
import json
from pathlib import Path

# 飞书应用配置
APP_ID = "cli_a933f5b61d39dcb5"
APP_SECRET = "CFuYjJZtEOFVfIhXINopPe4haJUul0cY"

def get_token():
    """获取tenant access token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = {"app_id": APP_ID, "app_secret": APP_SECRET}
    resp = requests.post(url, json=data, timeout=10)
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") != 0:
        raise Exception(f"获取token失败: {result}")
    return result["tenant_access_token"]

def upload_image(token, image_path):
    """上传图片获取image_key"""
    url = "https://open.feishu.cn/open-apis/im/v1/images"
    headers = {"Authorization": f"Bearer {token}"}
    
    with open(image_path, "rb") as f:
        files = {"image_type": (None, "message"), "image": (Path(image_path).name, f, "image/jpeg")}
        resp = requests.post(url, headers=headers, files=files, timeout=30)
    
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") != 0:
        raise Exception(f"上传图片失败: {result}")
    return result["data"]["image_key"]

def send_image(token, chat_id, image_key):
    """发送图片消息"""
    url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "receive_id": chat_id,
        "msg_type": "image",
        "content": json.dumps({"image_key": image_key})
    }
    resp = requests.post(url, headers=headers, json=data, timeout=10)
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") != 0:
        raise Exception(f"发送消息失败: {result}")
    return result["data"]["message_id"]

def main():
    if len(sys.argv) < 3:
        print("用法: python feishu_send_image.py <图片路径> <目标chat_id> [消息文字]")
        sys.exit(1)
    
    image_path = sys.argv[1]
    chat_id = sys.argv[2]
    message_text = sys.argv[3] if len(sys.argv) > 3 else None
    
    print(f"图片: {image_path}")
    print(f"目标: {chat_id}")
    
    # 获取token
    print("获取access token...")
    token = get_token()
    print(f"Token获取成功")
    
    # 上传图片
    print("上传图片...")
    image_key = upload_image(token, image_path)
    print(f"图片key: {image_key}")
    
    # 发送图片
    print("发送图片...")
    msg_id = send_image(token, chat_id, image_key)
    print(f"发送成功! message_id: {msg_id}")
    
    # 如果有文字，先发文字再发图片
    if message_text:
        print(f"发送文字: {message_text}")

if __name__ == "__main__":
    main()
