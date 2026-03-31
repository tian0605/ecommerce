#!/usr/bin/env python3
"""Initialize already-published collect-box products into the local database."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import psycopg2

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
WORKFLOW_SCRIPTS = WORKSPACE / 'skills' / 'workflow-runner' / 'scripts'

if str(WORKFLOW_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_SCRIPTS))

from workflow_runner import WorkflowRunner  # noqa: E402


def parse_ids(positional_ids: List[str], ids_arg: str | None) -> List[str]:
    raw: List[str] = []
    raw.extend(positional_ids)
    if ids_arg:
        raw.extend(ids_arg.split(','))

    normalized: List[str] = []
    seen = set()
    for value in raw:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def mark_product_published(alibaba_product_id: str) -> Dict[str, Any]:
    conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE products
                    SET status = 'published',
                        listing_updated_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE alibaba_product_id = %s
                      AND COALESCE(is_deleted, 0) = 0
                    RETURNING id, product_id, product_id_new, status
                    """,
                    (alibaba_product_id,),
                )
                row = cur.fetchone()
                if not row:
                    return {'success': False, 'error': '数据库中未找到刚初始化的商品'}
                return {
                    'success': True,
                    'id': row[0],
                    'product_id': row[1],
                    'product_id_new': row[2],
                    'status': row[3],
                }
    finally:
        conn.close()


def process_one(runner: WorkflowRunner, alibaba_product_id: str, strict_weight: bool) -> Dict[str, Any]:
    outcome: Dict[str, Any] = {
        'alibaba_product_id': alibaba_product_id,
        'success': False,
    }

    scrape_result = runner.step2_scrape(source_item_id=alibaba_product_id, allow_index_fallback=False)
    outcome['scrape'] = scrape_result
    if not scrape_result.get('success'):
        outcome['error'] = scrape_result.get('error') or '采集箱详情抓取失败'
        return outcome

    scrape_data = scrape_result.get('data', {})
    resolved_alibaba_id = str(scrape_data.get('alibaba_product_id') or alibaba_product_id)
    weight_result = runner.step3_local_weight(resolved_alibaba_id)
    outcome['weight'] = weight_result

    weight_data = weight_result.get('data', {}) if weight_result.get('success') else None
    if strict_weight and not weight_result.get('success'):
        outcome['error'] = weight_result.get('error') or '重量尺寸获取失败'
        return outcome

    store_result = runner.step4_store(scrape_data, weight_data)
    outcome['store'] = store_result
    if not store_result.get('success'):
        outcome['error'] = store_result.get('error') or store_result.get('message') or '商品落库失败'
        return outcome

    publish_sync = mark_product_published(resolved_alibaba_id)
    outcome['publish_sync'] = publish_sync
    if not publish_sync.get('success'):
        outcome['error'] = publish_sync.get('error') or '已发布状态同步失败'
        return outcome

    outcome['success'] = True
    outcome['warning'] = None if weight_result.get('success') else (weight_result.get('error') or '重量尺寸获取失败，已按无重量模式落库')
    return outcome


def print_summary(results: List[Dict[str, Any]]) -> int:
    print('\n' + '=' * 72)
    print('历史已发布商品初始化结果')
    print('=' * 72)

    success_count = 0
    warning_count = 0
    for result in results:
        if result.get('success'):
            success_count += 1
            publish_sync = result.get('publish_sync', {})
            warning = result.get('warning')
            status_line = (
                f"✅ {result['alibaba_product_id']} | {publish_sync.get('product_id_new')} | "
                f"status={publish_sync.get('status')}"
            )
            if warning:
                warning_count += 1
                status_line += f" | warning={warning}"
            print(status_line)
        else:
            print(f"❌ {result['alibaba_product_id']} | {result.get('error', '未知错误')}")

    print('-' * 72)
    print(f"成功: {success_count} | 失败: {len(results) - success_count} | 警告: {warning_count}")
    return 0 if success_count == len(results) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description='初始化已发布但未按新规范落库的商品')
    parser.add_argument('alibaba_ids', nargs='*', help='一个或多个 1688 货源 ID')
    parser.add_argument('--ids', help='逗号分隔的 1688 货源 ID')
    parser.add_argument('--strict-weight', action='store_true', help='重量尺寸抓取失败时直接终止该商品初始化')
    args = parser.parse_args()

    alibaba_ids = parse_ids(args.alibaba_ids, args.ids)
    if not alibaba_ids:
        print('请提供至少一个 1688 货源 ID，可用位置参数或 --ids')
        return 1

    runner = WorkflowRunner()
    precheck = runner.check_preconditions(require_local_weight=True)
    if not precheck.get('success'):
        print(json.dumps(precheck, ensure_ascii=False, indent=2))
        return 1

    results: List[Dict[str, Any]] = []
    for index, alibaba_product_id in enumerate(alibaba_ids, start=1):
        print(f"\n[{index}/{len(alibaba_ids)}] 初始化 {alibaba_product_id}")
        results.append(process_one(runner, alibaba_product_id, args.strict_weight))

    return print_summary(results)


if __name__ == '__main__':
    raise SystemExit(main())