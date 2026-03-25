import requests
import base64
import json

# 读取图片
with open('/root/.openclaw/workspace-e-commerce/logs/closed3.png', 'rb') as f:
    img_bytes = f.read()

# 转换为 base64
img_base64 = base64.b64encode(img_bytes).decode('utf-8')

# 构造 image_url
image_url = "data:image/png;base64," + img_base64

# 构建消息
messages = [
    {
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": image_url}},
            {"type": "text", "text": "分析这个页面：1.有哪些弹窗？2.弹窗HTML特征？3.给出Playwright关闭弹窗的Python代码"}
        ]
    }
]

payload = {
    "model": "qwen-vl-plus",
    "messages": messages,
    "max_tokens": 1000
}

headers = {
    "Authorization": "Bearer sk-914c1a9a5f054ab4939464389b5b791f",
    "Content-Type": "application/json"
}

print("Sending request to Qwen-VL...")
resp = requests.post(
    "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    headers=headers,
    json=payload,
    timeout=120
)
print("Status:", resp.status_code)
d = resp.json()
if 'choices' in d:
    print(d['choices'][0]['message']['content'][:3000])
else:
    print(json.dumps(d, ensure_ascii=False, indent=2)[:500])
