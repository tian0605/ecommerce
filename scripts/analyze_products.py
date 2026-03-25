#!/usr/bin/env python3
"""
商品数据分析脚本
查询数据库，生成商品状态报告
"""

import psycopg2
import json
from datetime import datetime

DB_CONFIG = {
    'host': 'localhost',
    'database': 'ecommerce_data',
    'user': 'superuser',
    'password': 'Admin123!'
}

def analyze_products():
    """分析商品数据"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # 1. 商品总数
        cur.execute('SELECT COUNT(*) FROM products')
        total = cur.fetchone()[0]
        
        # 2. 各状态商品数量
        cur.execute('SELECT status, COUNT(*) FROM products GROUP BY status')
        status_dist = dict(cur.fetchall())
        
        # 3. 待处理商品（collected状态）
        pending = status_dist.get('collected', 0)
        
        # 4. 已发布商品
        published = status_dist.get('published', 0)
        
        # 5. 最新商品
        cur.execute('''
            SELECT alibaba_product_id, title, status, created_at 
            FROM products 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        recent = cur.fetchall()
        
        # 6. SKU统计
        cur.execute('SELECT COUNT(*) FROM product_skus')
        total_skus = cur.fetchone()[0]
        
        conn.close()
        
        # 生成报告
        report = f"""📊 商品数据报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━
商品总数: {total}
  - 待处理(collected): {pending}
  - 已发布(published): {published}
  - 其他: {total - pending - published}
━━━━━━━━━━━━━━━
SKU总数: {total_skus}
━━━━━━━━━━━━━━━
最近商品:
"""
        for item in recent:
            report += f"  • {item[0]}: {item[2]} ({item[3].strftime('%m-%d') if item[3] else 'N/A'})\n"
        
        print(report)
        return True
        
    except Exception as e:
        print(f"分析失败: {e}")
        return False

if __name__ == '__main__':
    success = analyze_products()
    exit(0 if success else 1)
