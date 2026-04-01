#!/usr/bin/env python3
"""修复任务：针对指定商品执行 Step6 (miaoshou-updater)"""
import sys, time, json
from pathlib import Path
from fix_step6_guard import require_step6_guard

sys.path.insert(0, '/home/ubuntu/.openclaw/skills/miaoshou-updater')
sys.path.insert(0, str(Path('/home/ubuntu/.openclaw/skills/miaoshou-updater').parent.parent / 'shared'))

require_step6_guard(__file__, destructive=False)

import db
from logger import setup_logger

logger = setup_logger('fix-step6')

TARGET_IDS = ['1026754677096', '1031338618294']

def get_product_with_skus(alibaba_id):
    """获取商品及其SKU数据"""
    with db.get_cursor() as cur:
        # 商品主数据
        cur.execute("""
            SELECT id, product_id, alibaba_product_id, title, description,
                   optimized_title, optimized_description, status, category,
                   product_id_new
            FROM products
            WHERE alibaba_product_id = %s
        """, (alibaba_id,))
        row = cur.fetchone()
        if not row:
            return None
        
        product = {
            'id': row[0],
            'product_id': row[1],
            'alibaba_product_id': row[2],
            'title': row[3],
            'description': row[4],
            'optimized_title': row[5],
            'optimized_description': row[6],
            'status': row[7],
            'category': row[8],
            'product_id_new': row[9],
        }
        
        # SKU物流数据
        cur.execute("""
            SELECT package_weight, package_length, package_width, package_height
            FROM product_skus
            WHERE product_id = %s
            ORDER BY price ASC
            LIMIT 1
        """, (row[0],))
        sku_row = cur.fetchone()
        if sku_row:
            product['package_weight'] = sku_row[0]
            product['package_length'] = sku_row[1]
            product['package_width'] = sku_row[2]
            product['package_height'] = sku_row[3]
        else:
            product['package_weight'] = 0
            product['package_length'] = 0
            product['package_width'] = 0
            product['package_height'] = 0
        
        return product

# 获取两个商品
for alibaba_id in TARGET_IDS:
    p = get_product_with_skus(alibaba_id)
    if p:
        print(f"\n=== 商品 {alibaba_id} ===")
        print(f"  product_id_new: {p['product_id_new']}")
        print(f"  status: {p['status']}")
        print(f"  optimized_title: {p['optimized_title'][:50] if p['optimized_title'] else 'N/A'}...")
        print(f"  category: {p['category']}")
        print(f"  SKU weight: {p['package_weight']}g")
        print(f"  SKU dimensions: {p['package_length']}x{p['package_width']}x{p['package_height']}cm")
    else:
        print(f"\n❌ 商品 {alibaba_id} 未找到")
