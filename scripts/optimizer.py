#!/usr/bin/env python3
"""Workspace-local ListingOptimizer wrapper for workflow Step 5."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
BATCH_OPTIMIZER_SCRIPTS = WORKSPACE / 'skills' / 'listing-batch-optimizer' / 'scripts'

if str(BATCH_OPTIMIZER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(BATCH_OPTIMIZER_SCRIPTS))
if str(WORKSPACE / 'scripts') not in sys.path:
    sys.path.insert(0, str(WORKSPACE / 'scripts'))

from listing_batch_optimizer import ListingBatchOptimizer, normalize_text  # type: ignore
from multisite_config import load_market_bundle, normalize_site_context  # type: ignore


DB_CONFIG = {
    'host': 'localhost',
    'database': 'ecommerce_data',
    'user': 'superuser',
    'password': 'Admin123!',
}


class ListingOptimizer:
    def __init__(self):
        self.batch_optimizer = ListingBatchOptimizer()
        self.conn = psycopg2.connect(**DB_CONFIG)

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        self.batch_optimizer.close()

    def _resolve_runtime_bundle(self, product: Dict[str, Any]) -> Dict[str, Any]:
        site_context = normalize_site_context(product)
        try:
            return load_market_bundle(
                self.conn,
                market_code=site_context.get('market_code'),
                site_code=site_context.get('site_code'),
            )
        except Exception:
            return {
                'site_context': site_context,
                'market_config': {},
                'shipping_profile': {},
                'content_policy': {},
            }

    def _load_product(self, product_identifier: Any) -> Optional[Dict[str, Any]]:
        lookup = {
            'id': None,
            'product_id_new': None,
            'alibaba_product_id': None,
        }
        site_context: Dict[str, Any] = {}
        if isinstance(product_identifier, dict):
            lookup['id'] = product_identifier.get('id')
            lookup['product_id_new'] = product_identifier.get('product_id_new') or product_identifier.get('product_id')
            lookup['alibaba_product_id'] = product_identifier.get('alibaba_product_id')
            for key in ('market_code', 'site_code', 'shop_code', 'source_language', 'listing_language'):
                if product_identifier.get(key) not in (None, ''):
                    site_context[key] = product_identifier.get(key)
        else:
            lookup['product_id_new'] = product_identifier

        cur = self.conn.cursor()
        product_row = None
        if lookup['id']:
            cur.execute(
                """
                SELECT id, product_id_new, alibaba_product_id, title, description,
                       optimized_title, optimized_description, COALESCE(skus, '[]'::jsonb)
                FROM products
                WHERE id = %s AND COALESCE(is_deleted, 0) = 0
                """,
                (lookup['id'],),
            )
            product_row = cur.fetchone()

        if not product_row and lookup['product_id_new']:
            cur.execute(
                """
                SELECT id, product_id_new, alibaba_product_id, title, description,
                       optimized_title, optimized_description, COALESCE(skus, '[]'::jsonb)
                FROM products
                WHERE (product_id_new = %s OR product_id = %s)
                  AND COALESCE(is_deleted, 0) = 0
                ORDER BY id DESC
                LIMIT 1
                """,
                (lookup['product_id_new'], lookup['product_id_new']),
            )
            product_row = cur.fetchone()

        if not product_row and lookup['alibaba_product_id']:
            cur.execute(
                """
                SELECT id, product_id_new, alibaba_product_id, title, description,
                       optimized_title, optimized_description, COALESCE(skus, '[]'::jsonb)
                FROM products
                WHERE alibaba_product_id = %s
                  AND COALESCE(is_deleted, 0) = 0
                ORDER BY id DESC
                LIMIT 1
                """,
                (lookup['alibaba_product_id'],),
            )
            product_row = cur.fetchone()

        if not product_row:
            cur.close()
            return None

        product_id = product_row[0]
        raw_skus = product_row[7]
        if isinstance(raw_skus, str):
            try:
                raw_skus = json.loads(raw_skus)
            except json.JSONDecodeError:
                raw_skus = []
        if not isinstance(raw_skus, list):
            raw_skus = []

        cur.execute(
            """
            SELECT id, sku_name, shopee_sku_name, color, size, price, stock,
                   package_length, package_width, package_height, image_url
            FROM product_skus
            WHERE product_id = %s AND COALESCE(is_deleted, 0) = 0
            ORDER BY id ASC
            """,
            (product_id,),
        )
        db_skus = []
        for row in cur.fetchall():
            db_skus.append({
                'id': row[0],
                'sku_name': row[1],
                'shopee_sku_name': row[2],
                'color': row[3],
                'size': row[4],
                'price': row[5],
                'stock': row[6],
                'package_length': row[7],
                'package_width': row[8],
                'package_height': row[9],
                'image_url': row[10],
            })
        cur.close()

        product = {
            'id': product_row[0],
            'item_no': product_row[1],
            'product_id_new': product_row[1],
            'alibaba_id': product_row[2],
            'alibaba_product_id': product_row[2],
            'title': product_row[3],
            'description': product_row[4],
            'optimized_title': product_row[5],
            'optimized_description': product_row[6],
            'skus': raw_skus,
            'db_skus': db_skus,
        }
        product.update(site_context)
        return product

    def update_product(
        self,
        product_id: int,
        product_id_new: str,
        alibaba_product_id: str,
        optimized_title: str,
        optimized_description: str,
        optimized_skus: Optional[List[Dict[str, Any]]] = None,
        site_context: Optional[Dict[str, Any]] = None,
        source_title: Optional[str] = None,
        source_description: Optional[str] = None,
    ) -> bool:
        normalized_context = normalize_site_context(site_context or {})
        bundle = self._resolve_runtime_bundle({
            'market_code': normalized_context.get('market_code'),
            'site_code': normalized_context.get('site_code'),
            'shop_code': normalized_context.get('shop_code'),
            'source_language': normalized_context.get('source_language'),
            'listing_language': normalized_context.get('listing_language'),
        })
        market_config = bundle.get('market_config') or {}
        shipping_profile = bundle.get('shipping_profile') or {}
        content_policy = bundle.get('content_policy') or {}

        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE products
            SET optimized_title = %s,
                optimized_description = %s,
                optimization_version = COALESCE(optimization_version, 0) + 1,
                updated_at = NOW()
            WHERE id = %s
            """,
            (optimized_title, optimized_description, product_id),
        )
        cur.execute(
            """
            UPDATE product_listing_info
            SET optimized_title = %s,
                optimized_description = %s,
                updated_at = NOW()
            WHERE product_id_new = %s OR alibaba_product_id = %s
            """,
            (optimized_title, optimized_description, product_id_new, alibaba_product_id),
        )

        current_site_sql = """
            UPDATE site_listings
            SET market_code = %s,
                site_code = %s,
                shop_code = %s,
                alibaba_product_id = %s,
                product_id_new = %s,
                source_language_snapshot = %s,
                listing_language_snapshot = %s,
                title_source = 'optimizer',
                description_source = 'optimizer',
                original_title_snapshot = %s,
                original_description_snapshot = %s,
                listing_title = %s,
                listing_description = %s,
                short_description = %s,
                content_policy_code = %s,
                shipping_profile_code = %s,
                fee_profile_code = %s,
                price_policy_code = %s,
                erp_profile_code = %s,
                category_profile_code = %s,
                currency = %s,
                status = %s,
                publish_status = CASE WHEN publish_status = 'published' THEN publish_status ELSE 'pending' END,
                sync_status = 'pending',
                is_current = TRUE,
                updated_at = NOW(),
                is_deleted = 0
            WHERE product_id = %s
              AND COALESCE(sku_id, -1) = -1
              AND site_code = %s
              AND shop_code = %s
              AND is_deleted = 0
              AND is_current = TRUE
        """
        short_description = optimized_description[:120] if optimized_description else None
        listing_status = 'published' if str(site_context.get('status') or '').lower() == 'published' else 'draft'
        update_params = (
            normalized_context.get('market_code') or 'shopee_tw',
            normalized_context.get('site_code') or 'shopee_tw',
            normalized_context.get('shop_code') or 'default',
            alibaba_product_id,
            product_id_new,
            normalized_context.get('source_language') or 'zh-CN',
            normalized_context.get('listing_language') or 'zh-Hant',
            source_title,
            source_description,
            optimized_title,
            optimized_description,
            short_description,
            content_policy.get('content_policy_code'),
            shipping_profile.get('shipping_profile_code'),
            market_config.get('default_fee_profile_code'),
            market_config.get('default_price_policy_code'),
            market_config.get('default_erp_profile_code'),
            market_config.get('default_category_profile_code'),
            market_config.get('default_currency') or 'TWD',
            listing_status,
            product_id,
            normalized_context.get('site_code') or 'shopee_tw',
            normalized_context.get('shop_code') or 'default',
        )
        cur.execute(current_site_sql, update_params)
        if cur.rowcount == 0:
            cur.execute(
                """
                INSERT INTO site_listings (
                    product_id,
                    market_code,
                    site_code,
                    shop_code,
                    platform,
                    alibaba_product_id,
                    product_id_new,
                    source_language_snapshot,
                    listing_language_snapshot,
                    title_source,
                    description_source,
                    original_title_snapshot,
                    original_description_snapshot,
                    listing_title,
                    listing_description,
                    short_description,
                    content_policy_code,
                    shipping_profile_code,
                    fee_profile_code,
                    price_policy_code,
                    erp_profile_code,
                    category_profile_code,
                    currency,
                    status,
                    publish_status,
                    sync_status,
                    is_current,
                    is_deleted,
                    created_at,
                    updated_at
                ) VALUES (
                    %s, %s, %s, %s, 'shopee', %s, %s, %s, %s, 'optimizer', 'optimizer', %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, 'pending', 'pending', TRUE, 0, NOW(), NOW()
                )
                """,
                (
                    product_id,
                    normalized_context.get('market_code') or 'shopee_tw',
                    normalized_context.get('site_code') or 'shopee_tw',
                    normalized_context.get('shop_code') or 'default',
                    alibaba_product_id,
                    product_id_new,
                    normalized_context.get('source_language') or 'zh-CN',
                    normalized_context.get('listing_language') or 'zh-Hant',
                    source_title,
                    source_description,
                    optimized_title,
                    optimized_description,
                    short_description,
                    content_policy.get('content_policy_code'),
                    shipping_profile.get('shipping_profile_code'),
                    market_config.get('default_fee_profile_code'),
                    market_config.get('default_price_policy_code'),
                    market_config.get('default_erp_profile_code'),
                    market_config.get('default_category_profile_code'),
                    market_config.get('default_currency') or 'TWD',
                    listing_status,
                ),
            )

        for sku in optimized_skus or []:
            if sku.get('sku_id'):
                cur.execute(
                    "UPDATE product_skus SET shopee_sku_name = %s WHERE id = %s",
                    (sku.get('shopee_sku_name'), sku.get('sku_id')),
                )
            elif sku.get('sku_name'):
                cur.execute(
                    "UPDATE product_skus SET shopee_sku_name = %s WHERE product_id = %s AND sku_name = %s",
                    (sku.get('shopee_sku_name'), product_id, sku.get('sku_name')),
                )

        self.conn.commit()
        cur.close()
        return True

    def optimize_product(self, product_identifier: Any) -> Dict[str, Any]:
        product = self._load_product(product_identifier)
        if not product:
            return {'success': False, 'message': '商品不存在'}

        new_content = self.batch_optimizer.generate_optimized_content(product)
        if not new_content:
            return {'success': False, 'message': 'LLM调用失败或生成结果未通过校验'}

        optimized_title = normalize_text(new_content.get('optimized_title'))
        optimized_description = normalize_text(new_content.get('optimized_description'))
        optimized_skus = new_content.get('optimized_skus') or []

        self.update_product(
            product['id'],
            product['product_id_new'],
            product['alibaba_product_id'],
            optimized_title,
            optimized_description,
            optimized_skus,
            site_context=product,
            source_title=product.get('title'),
            source_description=product.get('description'),
        )

        return {
            'success': True,
            'message': '优化成功',
            'optimized_title': optimized_title,
            'optimized_description': optimized_description,
            'optimized_skus': optimized_skus,
            'persisted': True,
            'product_id': product['product_id_new'],
        }

    def run(self, limit: int = 1) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id
            FROM products
            WHERE COALESCE(is_deleted, 0) = 0
            ORDER BY updated_at DESC NULLS LAST, id DESC
            LIMIT %s
            """,
            (limit,),
        )
        product_ids = [row[0] for row in cur.fetchall()]
        cur.close()
        return [self.optimize_product(product_id) for product_id in product_ids]


if __name__ == '__main__':
    optimizer = ListingOptimizer()
    try:
        results = optimizer.run(limit=1)
        print(results)
    finally:
        optimizer.close()