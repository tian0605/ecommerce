#!/usr/bin/env python3
"""Step6 修复脚本：针对指定商品执行 miaoshou-updater"""
import sys, time, json
from pathlib import Path
from fix_step6_guard import require_step6_guard

require_step6_guard(__file__, destructive=True)

sys.path.insert(0, '/home/ubuntu/.openclaw/skills/shared')
import db
from logger import setup_logger

logger = setup_logger('fix-step6')

SKILL_DIR = Path('/home/ubuntu/.openclaw/skills/miaoshou-updater')
sys.path.insert(0, str(SKILL_DIR))
from updater import MiaoshouUpdater

TARGET_IDS = ['1026754677096', '1031338618294']

def get_product_with_skus(alibaba_id):
    with db.get_cursor() as cur:
        cur.execute("""
            SELECT id, product_id, alibaba_product_id, title, description,
                   optimized_title, optimized_description, status, category,
                   product_id_new
            FROM products WHERE alibaba_product_id = %s
        """, (alibaba_id,))
        row = cur.fetchone()
        if not row:
            return None
        product = {
            'id': row[0], 'product_id': row[1], 'alibaba_product_id': row[2],
            'title': row[3], 'description': row[4], 'optimized_title': row[5],
            'optimized_description': row[6], 'status': row[7], 'category': row[8],
            'product_id_new': row[9],
        }
        # Get first SKU with weight data
        cur.execute("""
            SELECT package_weight, package_length, package_width, package_height
            FROM product_skus WHERE product_id = %s ORDER BY price ASC LIMIT 1
        """, (row[0],))
        sku_row = cur.fetchone()
        if sku_row:
            product['package_weight'] = float(sku_row[0]) if sku_row[0] else 0
            product['package_length'] = float(sku_row[1]) if sku_row[1] else 0
            product['package_width'] = float(sku_row[2]) if sku_row[2] else 0
            product['package_height'] = float(sku_row[3]) if sku_row[3] else 0
        return product

def main():
    # Get products
    products = []
    for alibaba_id in TARGET_IDS:
        p = get_product_with_skus(alibaba_id)
        if p:
            products.append(p)
            print(f"✅ 商品 {alibaba_id}: weight={p['package_weight']}g, dims={p['package_length']}x{p['package_width']}x{p['package_height']}")
        else:
            print(f"❌ 商品 {alibaba_id} 未找到")

    if not products:
        print("没有找到任何目标商品")
        return

    # Launch browser once
    updater = MiaoshouUpdater(headless=True)
    try:
        updater.launch()
        for product in products:
            alibaba_id = product['alibaba_product_id']
            print(f"\n{'='*60}")
            print(f"开始 Step6: {alibaba_id}")
            print(f"{'='*60}")
            success = updater.update_product(product)
            print(f"Step6 结果: {'✅ 成功' if success else '❌ 失败'}")
            time.sleep(3)
    finally:
        updater.close()

if __name__ == '__main__':
    main()
