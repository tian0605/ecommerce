#!/usr/bin/env python3
"""Initialize local profit_analysis rows for products already in the local products table."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import psycopg2


WORKSPACE = Path(__file__).resolve().parents[1]
ANALYZER_ROOT = WORKSPACE / 'skills' / 'profit-analyzer'
if str(ANALYZER_ROOT) not in sys.path:
    sys.path.insert(0, str(ANALYZER_ROOT))

from analyzer import ProfitAnalyzer  # noqa: E402
from multisite_config import normalize_site_context  # noqa: E402


DB_CONFIG = {
    'host': 'localhost',
    'database': 'ecommerce_data',
    'user': 'superuser',
    'password': 'Admin123!',
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='初始化本地利润明细')
    parser.add_argument('--scope', choices=['missing_only', 'all_products'], default='missing_only')
    parser.add_argument('--site', default='TW')
    parser.add_argument('--site-code', default=None)
    parser.add_argument('--market-code', default=None)
    parser.add_argument('--profit-rate', type=float, default=0.20)
    parser.add_argument('--batch-size', type=int, default=20)
    parser.add_argument('--force-recalculate', action='store_true')
    return parser.parse_args()


def legacy_site_label(site_code: str) -> str:
    normalized = str(site_code or '').strip().lower()
    if normalized == 'shopee_ph':
        return 'PH'
    return 'TW' if normalized == 'shopee_tw' else normalized.upper()


def fetch_candidate_ids(site_context: dict[str, str], scope: str, force_recalculate: bool) -> list[str]:
    site_code = str(site_context.get('site_code') or 'shopee_tw').strip().lower()
    legacy_site = legacy_site_label(site_code).lower()
    query = """
        SELECT DISTINCT p.alibaba_product_id
        FROM products p
        LEFT JOIN product_analysis pa
          ON pa.product_id = p.id
         AND (
               LOWER(COALESCE(pa.site_code, '')) = %s
               OR LOWER(COALESCE(pa.site, '')) = %s
         )
         AND COALESCE(pa.is_deleted, 0) = 0
        WHERE COALESCE(p.is_deleted, 0) = 0
          AND COALESCE(p.alibaba_product_id, '') <> ''
          AND (%s = 'all_products' OR %s = TRUE OR pa.id IS NULL)
        ORDER BY p.alibaba_product_id ASC
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (site_code, legacy_site, scope, force_recalculate))
            return [str(row[0]) for row in cur.fetchall() if row and row[0]]


def chunked(items: list[str], batch_size: int):
    for index in range(0, len(items), batch_size):
        yield items[index:index + batch_size]


def main() -> int:
    args = parse_args()
    site_context = normalize_site_context({
        'market_code': args.market_code,
        'site_code': args.site_code or args.site,
    })
    analyzer = ProfitAnalyzer(target_profit_rate=args.profit_rate)
    candidate_ids = fetch_candidate_ids(site_context, args.scope, args.force_recalculate)
    total = len(candidate_ids)
    print(
        f'CANDIDATES total={total} scope={args.scope} '
        f'site={legacy_site_label(site_context["site_code"])} '
        f'site_code={site_context["site_code"]} '
        f'force_recalculate={args.force_recalculate}'
    )
    if total == 0:
      print('没有需要初始化的商品')
      return 0

    batch_total = math.ceil(total / args.batch_size)
    success_count = 0
    failed_count = 0

    for batch_index, batch in enumerate(chunked(candidate_ids, args.batch_size), start=1):
        print(f'BATCH {batch_index}/{batch_total} size={len(batch)} start={batch[0]}')
        outcome = analyzer.run(batch, sync_feishu=False, site_context=site_context)
        batch_results = outcome.get('results', [])
        batch_success = sum(1 for item in batch_results if item.get('分析状态') == 'success')
        batch_failed = len(batch_results) - batch_success
        success_count += batch_success
        failed_count += batch_failed
        print(
            'BATCH_RESULT '
            f'index={batch_index} inserted={outcome.get("db_result", {}).get("inserted", 0)} '
            f'replaced={outcome.get("db_result", {}).get("replaced", 0)} '
            f'success={batch_success} failed={batch_failed}'
        )

    print(f'SUMMARY success={success_count} failed={failed_count} total={total}')
    return 0 if failed_count == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())