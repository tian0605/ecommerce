#!/usr/bin/env python3
"""
持续调试脚本 - 直到发布成功
"""
import sys
import os
import time
import base64
import requests
from pathlib import Path

# 添加skills路径
sys.path.insert(0, '/home/ubuntu/.openclaw/skills')

def analyze_screenshot(img_path, label="分析"):
    """用视觉模型分析截图"""
    try:
        img_bytes = open(img_path, 'rb').read()
        img_base64 = base64.b64encode(img_bytes).decode()
        
        response = requests.post(
            "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
            headers={"Authorization": "Bearer 05ee7f57-9541-40d1-8021-69a6a81b2c95", "Content-Type": "application/json"},
            json={
                "model": "doubao-seed-2-0-pro-260215",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{label}：对话框标题？有没有发布成功提示？"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                    ]
                }],
                "max_tokens": 80
            },
            timeout=30
        )
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"分析失败: {e}"

def check_product_status():
    """检查商品状态"""
    import psycopg2
    from load_env import get_db_config
    conn = psycopg2.connect(**get_db_config())
    cur = conn.cursor()
    cur.execute("SELECT status FROM products WHERE alibaba_product_id='1031400982378'")
    status = cur.fetchone()[0]
    conn.close()
    return status

def reset_product():
    """重置商品状态"""
    import psycopg2
    from load_env import get_db_config
    conn = psycopg2.connect(**get_db_config())
    cur = conn.cursor()
    cur.execute("UPDATE products SET status='collected' WHERE alibaba_product_id='1031400982378'")
    conn.commit()
    conn.close()

def run_publish_test():
    """运行发布测试"""
    from miaoshou_updater.updater import MiaoshouUpdater
    
    updater = MiaoshouUpdater()
    updater.launch()
    try:
        result = updater.update_product({
            'alibaba_product_id': '1031400982378',
            'product_id_new': 'AL0001001260000002',
            'title': '厨房多功能收纳篮',
            'description': '材质：PP',
            'optimized_title': '廚房多功能收納篮',
            'optimized_description': '品質：PP 耐用時尚',
            'category': '收纳盒、收纳包与篮子',
            'package_length': 30,
            'package_width': 20,
            'package_height': 10
        })
        return result
    finally:
        updater.close()

def main():
    max_attempts = 999  # 足够多
    attempt = 0
    
    print("="*60)
    print("持续调试模式 - 直到发布成功")
    print("="*60)
    
    while attempt < max_attempts:
        attempt += 1
        print(f"\n{'='*60}")
        print(f"第 {attempt} 次尝试")
        print(f"{'='*60}")
        
        # 重置商品状态
        reset_product()
        
        # 运行发布测试
        print("运行发布测试...")
        try:
            result = run_publish_test()
            print(f"测试结果: {result}")
        except Exception as e:
            print(f"测试异常: {e}")
            result = False
        
        # 检查最终状态
        time.sleep(2)
        final_status = check_product_status()
        print(f"最终状态: {final_status}")
        
        if final_status == 'published':
            print("\n" + "🎉"*20)
            print("发布成功！！！")
            print("🎉"*20)
            return True
        else:
            print(f"发布失败，继续调试...")
            
            # 分析最新截图
            screenshot_dir = Path('/home/ubuntu/work/tmp/miaoshou_updater_test')
            if screenshot_dir.exists():
                screenshots = sorted(screenshot_dir.glob('step6*.png'))
                if screenshots:
                    latest = screenshots[-1]
                    print(f"分析截图: {latest.name}")
                    analysis = analyze_screenshot(str(latest), f"第{attempt}次尝试step6")
                    print(f"分析结果: {analysis}")
            
            # 等待一段时间后重试
            print("等待 5 秒后重试...")
            time.sleep(5)
    
    print(f"达到最大尝试次数 {max_attempts}")
    return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
