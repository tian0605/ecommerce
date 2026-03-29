import requests
import base64
import json

# 读取图片
with open('/root/.openclaw/workspace-e-commerce/logs/closed3.png', 'rb') as f:
    img_bytes = f.read()

# 转换为 base64
img_base64 = base64.b64encode(img_bytes).decode('utf-8')

# 构建消息（使用 Doubao Seed /responses API 格式）
payload = {
    "model": "doubao-seed-2-0-pro-260215",
    "input": [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{img_base64}"
                },
                {
                    "type": "input_text",
                    "text": "分析这个页面：1.有哪些弹窗？2.弹窗HTML特征？3.给出Playwright关闭弹窗的Python代码"
                }
            ]
        }
    ]
}

headers = {
    "Authorization": "Bearer 05ee7f57-9541-40d1-8021-69a6a81b2c95",
    "Content-Type": "application/json"
}

print("Sending request to Doubao Seed...")
resp = requests.post(
    "https://ark.cn-beijing.volces.com/api/v3/responses",
    headers=headers,
    json=payload,
    timeout=120
)
print("Status:", resp.status_code)
d = resp.json()
if 'output' in d:
    # 提取文本输出
    for item in d['output']:
        if item.get('type') == 'message':
            print(item['content'][0]['text'][:3000])
elif 'error' in d:
    print(f"Error: {d['error']}")
else:
    print(json.dumps(d, ensure_ascii=False, indent=2)[:500])