#!/usr/bin/env python3
"""workflow_runner.py - 电商产品一体化工作流运行器"""
import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import psycopg2


WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
EXTERNAL_SKILLS = Path('/home/ubuntu/.openclaw/skills')
EXTERNAL_SHARED = EXTERNAL_SKILLS / 'shared'
WORKSPACE_SCRIPTS = WORKSPACE / 'scripts'
LOCAL_WEIGHT_SCRIPTS = WORKSPACE / 'skills' / 'local-1688-weight' / 'scripts'

for path in [
    str(EXTERNAL_SHARED),
    str(EXTERNAL_SKILLS / 'miaoshou-collector'),
    str(EXTERNAL_SKILLS / 'listing-optimizer'),
    str(EXTERNAL_SKILLS / 'profit-analyzer'),
    str(WORKSPACE / 'skills' / 'collector-scraper'),
    str(WORKSPACE / 'skills' / 'product-storer'),
    str(WORKSPACE / 'skills' / 'miaoshou_updater'),
    str(WORKSPACE_SCRIPTS),
    str(LOCAL_WEIGHT_SCRIPTS),
]:
    if path not in sys.path:
        sys.path.insert(0, path)

from logger import setup_logger

logger = setup_logger('workflow-runner')


def extract_alibaba_product_id(url: str) -> Optional[str]:
    match = re.search(r'/offer/(\d+)\.html', url or '')
    if match:
        return match.group(1)
    return None


class WorkflowRunner:
    def __init__(self):
        self._modules_loaded = False
        self._import_error = None
        self._load_modules()

    def _load_modules(self):
        try:
            from collector import MiaoshouCollector
            from scraper import CollectorScraper
            from remote_weight_caller import check_local_service_health, fetch_weight_from_local
            from storer import ProductStorer
            from optimizer import ListingOptimizer
            from updater import MiaoshouUpdater
            from analyzer import ProfitAnalyzer

            self.MiaoshouCollector = MiaoshouCollector
            self.CollectorScraper = CollectorScraper
            self.check_local_service_health = check_local_service_health
            self.fetch_weight_from_local = fetch_weight_from_local
            self.ProductStorer = ProductStorer
            self.ListingOptimizer = ListingOptimizer
            self.MiaoshouUpdater = MiaoshouUpdater
            self.ProfitAnalyzer = ProfitAnalyzer
            self._modules_loaded = True
        except Exception as exc:
            self._import_error = exc
            self._modules_loaded = False

    def _fail(self, step: str, error: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {'success': False, 'step': step, 'error': error}
        if extra:
            payload.update(extra)
        logger.error(f'[{step}] {error}')
        return payload

    def _lookup_product_row_id(self, product_payload: Dict[str, Any]) -> Optional[int]:
        identifiers = [
            ('id', product_payload.get('id')),
            ('product_id_new', product_payload.get('product_id_new')),
            ('product_id', product_payload.get('product_id')),
            ('alibaba_product_id', product_payload.get('alibaba_product_id')),
        ]

        direct_id = product_payload.get('id')
        if isinstance(direct_id, int):
            return direct_id

        try:
            conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
            cur = conn.cursor()
            for field, value in identifiers[1:]:
                if not value:
                    continue
                cur.execute(f"SELECT id FROM products WHERE {field} = %s ORDER BY id DESC LIMIT 1", (value,))
                row = cur.fetchone()
                if row:
                    cur.close()
                    conn.close()
                    return row[0]
            cur.close()
            conn.close()
        except Exception as exc:
            logger.warning(f'[lookup] 查询商品行ID失败: {exc}')

        return None

    def _lookup_product_status(self, product_identifier: Any) -> Optional[str]:
        if isinstance(product_identifier, dict):
            identifiers = [
                ('id', product_identifier.get('id')),
                ('product_id_new', product_identifier.get('product_id_new')),
                ('product_id', product_identifier.get('product_id')),
                ('alibaba_product_id', product_identifier.get('alibaba_product_id')),
            ]
        else:
            value = str(product_identifier)
            identifiers = [
                ('id', value),
                ('product_id_new', value),
                ('product_id', value),
                ('alibaba_product_id', value),
            ]

        try:
            conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
            cur = conn.cursor()
            for field, value in identifiers:
                if value in (None, ''):
                    continue
                if field == 'id':
                    cur.execute("SELECT status FROM products WHERE id::text = %s ORDER BY id DESC LIMIT 1", (str(value),))
                else:
                    cur.execute(f"SELECT status FROM products WHERE {field} = %s ORDER BY id DESC LIMIT 1", (value,))
                row = cur.fetchone()
                if row:
                    cur.close()
                    conn.close()
                    return row[0]
            cur.close()
            conn.close()
        except Exception as exc:
            logger.warning(f'[lookup] 查询商品状态失败: {exc}')

        return None

    def check_preconditions(self, require_local_weight: bool = True) -> Dict[str, Any]:
        logger.info('=' * 60)
        logger.info('[预检] 检查工作流前置条件')
        logger.info('=' * 60)

        if not self._modules_loaded:
            return self._fail('precheck', f'模块导入失败: {self._import_error}')

        cookie_candidates = [
            EXTERNAL_SKILLS / 'miaoshou-collector' / 'miaoshou_cookies.json',
            WORKSPACE / 'skills' / 'miaoshou-collector' / 'miaoshou_cookies.json',
            WORKSPACE / 'skills' / 'miaoshou-updater' / 'miaoshou_cookies.json',
        ]
        cookie_file = next((path for path in cookie_candidates if path.exists()), None)
        if not cookie_file:
            return self._fail('precheck', '未找到妙手ERP Cookies 文件')

        cookie_age_seconds = time.time() - cookie_file.stat().st_mtime
        if cookie_age_seconds > 24 * 3600:
            logger.warning(f'[precheck] Cookies 可能已过期: {cookie_file}')

        if require_local_weight and not self.check_local_service_health():
            return self._fail('precheck', '本地1688重量服务不可用，请检查 SSH 隧道和本地服务')

        logger.info(f'[precheck] Cookies: {cookie_file}')
        logger.info('[precheck] 前置条件检查通过')
        return {'success': True, 'cookie_file': str(cookie_file), 'local_weight_required': require_local_weight}

    def step1_collect(self, url: str) -> Dict[str, Any]:
        logger.info('=' * 60)
        logger.info('[步骤1] 妙手采集并自动认领')
        logger.info('=' * 60)

        collector = None
        try:
            collector = self.MiaoshouCollector()
            collector.launch()
            result = collector.collect(url)
            if result.get('success'):
                logger.info(f"[step1] 采集完成: {result.get('alibaba_product_id')}")
                return result
            return self._fail('step1_collect', result.get('error') or '采集失败', result)
        except Exception as exc:
            return self._fail('step1_collect', str(exc))
        finally:
            if collector:
                collector.close()

    def step2_scrape(self, product_index: int = 0, source_item_id: Optional[str] = None, max_attempts: int = 3, retry_delay: float = 12.0, allow_index_fallback: bool = True) -> Dict[str, Any]:
        logger.info('=' * 60)
        logger.info('[步骤2] 提取采集箱商品数据')
        logger.info('=' * 60)

        last_data: Dict[str, Any] = {}
        last_error: Optional[str] = None
        attempts = max(1, max_attempts if source_item_id else 1)

        for attempt in range(1, attempts + 1):
            scraper = None
            try:
                scraper = self.CollectorScraper()
                scraper.launch()
                data = scraper.scrape_product(
                    product_index=product_index,
                    source_item_id=source_item_id,
                    allow_index_fallback=allow_index_fallback,
                )
                if source_item_id and data and data.get('alibaba_product_id') and str(data.get('alibaba_product_id')) != str(source_item_id):
                    last_data = data
                    last_error = f"提取到了错误商品: expected={source_item_id}, actual={data.get('alibaba_product_id')}"
                    logger.warning(f"[step2] 第 {attempt}/{attempts} 次提取命中错误商品，继续重试")
                    continue
                if data and data.get('alibaba_product_id'):
                    logger.info(f"[step2] 提取成功: {data.get('alibaba_product_id')}")
                    return {'success': True, 'data': data, 'attempt': attempt}
                last_data = data or {}
                last_error = '未提取到有效商品数据'
                logger.warning(f'[step2] 第 {attempt}/{attempts} 次提取未成功')
            except Exception as exc:
                last_error = str(exc)
                logger.warning(f'[step2] 第 {attempt}/{attempts} 次提取异常: {exc}')
            finally:
                if scraper:
                    scraper.close()

            if attempt < attempts:
                time.sleep(retry_delay)

        return self._fail('step2_scrape', last_error or '未提取到有效商品数据', {'data': last_data})

    def step3_local_weight(self, alibaba_product_id: str) -> Dict[str, Any]:
        logger.info('=' * 60)
        logger.info('[步骤3] 获取本地1688重量尺寸')
        logger.info('=' * 60)

        try:
            data = self.fetch_weight_from_local(alibaba_product_id, timeout=120)
            if data and data.get('success'):
                logger.info(f"[step3] 获取成功: {data.get('sku_count', 0)} 个SKU")
                return {'success': True, 'data': data}
            return self._fail('step3_local_weight', (data or {}).get('error') or '本地重量服务返回失败', {'data': data or {}})
        except Exception as exc:
            return self._fail('step3_local_weight', str(exc))

    def step4_store(self, scrape_data: Dict[str, Any], weight_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        logger.info('=' * 60)
        logger.info('[步骤4] 商品数据落库')
        logger.info('=' * 60)

        try:
            storer = self.ProductStorer()
            product_data = dict(scrape_data or {})
            source_url = product_data.get('source_url')
            if not source_url and product_data.get('alibaba_product_id'):
                source_url = f"https://detail.1688.com/offer/{product_data['alibaba_product_id']}.html"
            product_data['source_url'] = source_url

            result = storer.store(product_data, weight_data)
            if result.get('success'):
                logger.info(f"[step4] 落库成功: {result.get('product_id_new') or result.get('main_product_no')}")
                return result
            return self._fail('step4_store', result.get('message') or '落库失败', result)
        except Exception as exc:
            return self._fail('step4_store', str(exc))

    def step5_optimize(self, product_payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info('=' * 60)
        logger.info('[步骤5] LLM 优化标题与描述')
        logger.info('=' * 60)

        try:
            optimizer = self.ListingOptimizer()
            result = optimizer.optimize_product(product_payload)
            if result.get('success'):
                row_id = self._lookup_product_row_id(product_payload)
                if row_id:
                    persisted = optimizer.update_product(
                        row_id,
                        result.get('optimized_title') or '',
                        result.get('optimized_description') or ''
                    )
                    result['persisted'] = persisted
                    if persisted:
                        product_payload['id'] = row_id
                product_payload['optimized_title'] = result.get('optimized_title')
                product_payload['optimized_description'] = result.get('optimized_description')
                logger.info('[step5] 优化成功')
                return result
            return self._fail('step5_optimize', result.get('message') or '优化失败', result)
        except Exception as exc:
            return self._fail('step5_optimize', str(exc))

    def step6_update(self, product_identifier: Any, publish: bool = True) -> Dict[str, Any]:
        logger.info('=' * 60)
        logger.info('[步骤6] 回写妙手ERP并发布' if publish else '[步骤6] 回写妙手ERP并保存')
        logger.info('=' * 60)

        updater = None
        try:
            updater = self.MiaoshouUpdater(
                headless=True,
                cdp_url=os.environ.get('MIAOSHOU_CDP_URL')
            )
            updater.launch()
            success = updater.update_product(product_identifier, publish=publish)
            if success:
                observed_status = self._lookup_product_status(product_identifier)
                is_published = observed_status == 'published'
                if publish and not is_published:
                    return self._fail('step6_update', '妙手回写完成，但未核验到 published 状态', {
                        'product_id': product_identifier,
                        'status': observed_status,
                        'published': False,
                    })
                logger.info(f'[step6] 回写成功，当前状态: {observed_status or "unknown"}')
                return {
                    'success': True,
                    'product_id': product_identifier,
                    'published': is_published,
                    'status': observed_status,
                }
            return self._fail('step6_update', '妙手回写返回失败', {'product_id': product_identifier})
        except Exception as exc:
            return self._fail('step6_update', str(exc), {'product_id': product_identifier})
        finally:
            if updater:
                updater.close()

    def step7_analyze(self, product_payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info('=' * 60)
        logger.info('[步骤7] 利润分析')
        logger.info('=' * 60)

        try:
            analyzer = self.ProfitAnalyzer()
            result = analyzer.analyze_product(product_payload)
            if result.get('status') == 'success':
                logger.info(f"[step7] 分析成功: 建议售价 {result.get('suggested_price_twd')} TWD")
                return {'success': True, 'data': result}
            return self._fail('step7_analyze', result.get('message') or '利润分析失败', {'data': result})
        except Exception as exc:
            return self._fail('step7_analyze', str(exc))

    def run_full(self, url: str, publish: bool = True) -> Dict[str, Dict[str, Any]]:
        logger.info('=' * 60)
        logger.info('🚀 全流程工作流开始')
        logger.info('=' * 60)

        results: Dict[str, Dict[str, Any]] = {}

        precheck = self.check_preconditions(require_local_weight=True)
        results['precheck'] = precheck
        if not precheck.get('success'):
            return results

        r1 = self.step1_collect(url)
        results['collect'] = r1
        if not r1.get('success'):
            return results

        time.sleep(2)

        target_source_id = r1.get('alibaba_product_id') or extract_alibaba_product_id(url)
        r2 = self.step2_scrape(source_item_id=target_source_id)
        results['scrape'] = r2
        if not r2.get('success'):
            return results

        scrape_data = r2.get('data', {})
        alibaba_product_id = scrape_data.get('alibaba_product_id') or extract_alibaba_product_id(url)
        if not alibaba_product_id:
            results['weight'] = self._fail('step3_local_weight', '无法确定1688商品ID')
            return results

        r3 = self.step3_local_weight(alibaba_product_id)
        results['weight'] = r3
        if not r3.get('success'):
            return results

        weight_data = r3.get('data', {})
        r4 = self.step4_store(scrape_data, weight_data)
        results['store'] = r4
        if not r4.get('success'):
            return results

        product_payload = dict(scrape_data)
        product_payload['id'] = r4.get('id') or r4.get('existing_id')
        product_payload['product_id'] = r4.get('product_id') or alibaba_product_id
        product_payload['product_id_new'] = r4.get('product_id_new') or r4.get('main_product_no')

        r5 = self.step5_optimize(product_payload)
        results['optimize'] = r5
        if not r5.get('success'):
            return results

        update_payload = dict(product_payload)
        update_payload['optimized_title'] = r5.get('optimized_title')
        update_payload['optimized_description'] = r5.get('optimized_description')
        r6 = self.step6_update(update_payload, publish=publish)
        results['update'] = r6
        if not r6.get('success'):
            return results

        analyze_payload = dict(product_payload)
        analyze_payload['weight_g'] = None
        if weight_data.get('sku_list'):
            analyze_payload['weight_g'] = weight_data['sku_list'][0].get('weight_g')
        r7 = self.step7_analyze(analyze_payload)
        results['analyze'] = r7

        logger.info('=' * 60)
        logger.info('🏁 全流程工作流结束')
        logger.info('=' * 60)
        return results

    def run_lightweight(self, url: str, publish: bool = True) -> Dict[str, Dict[str, Any]]:
        logger.info('=' * 60)
        logger.info('🚀 轻量工作流开始（跳过采集）')
        logger.info('=' * 60)

        results: Dict[str, Dict[str, Any]] = {}

        precheck = self.check_preconditions(require_local_weight=True)
        results['precheck'] = precheck
        if not precheck.get('success'):
            return results

        r2 = self.step2_scrape()
        results['scrape'] = r2
        if not r2.get('success'):
            return results

        scrape_data = r2.get('data', {})
        alibaba_product_id = scrape_data.get('alibaba_product_id') or extract_alibaba_product_id(url)
        if not alibaba_product_id:
            results['weight'] = self._fail('step3_local_weight', '无法确定1688商品ID')
            return results

        r3 = self.step3_local_weight(alibaba_product_id)
        results['weight'] = r3
        if not r3.get('success'):
            return results

        weight_data = r3.get('data', {})
        r4 = self.step4_store(scrape_data, weight_data)
        results['store'] = r4
        if not r4.get('success'):
            return results

        product_payload = dict(scrape_data)
        product_payload['id'] = r4.get('id') or r4.get('existing_id')
        product_payload['product_id'] = r4.get('product_id') or alibaba_product_id
        product_payload['product_id_new'] = r4.get('product_id_new') or r4.get('main_product_no')

        r5 = self.step5_optimize(product_payload)
        results['optimize'] = r5
        if not r5.get('success'):
            return results

        update_payload = dict(product_payload)
        update_payload['optimized_title'] = r5.get('optimized_title')
        update_payload['optimized_description'] = r5.get('optimized_description')
        r6 = self.step6_update(update_payload, publish=publish)
        results['update'] = r6
        if not r6.get('success'):
            return results

        analyze_payload = dict(product_payload)
        analyze_payload['weight_g'] = None
        if weight_data.get('sku_list'):
            analyze_payload['weight_g'] = weight_data['sku_list'][0].get('weight_g')
        r7 = self.step7_analyze(analyze_payload)
        results['analyze'] = r7

        logger.info('=' * 60)
        logger.info('🏁 轻量工作流结束')
        logger.info('=' * 60)
        return results


def print_summary(results: Dict[str, Dict[str, Any]]) -> int:
    print('\n' + '=' * 60)
    print('工作流结果汇总')
    print('=' * 60)

    failed_steps = []
    for step, result in results.items():
        success = result.get('success')
        status = '✅' if success else '❌'
        print(f'{step:>10}: {status}')
        if not success:
            failed_steps.append(step)
            if result.get('error'):
                print(f"  error: {result.get('error')}")

    print('=' * 60)
    if failed_steps:
        print(f"失败步骤: {', '.join(failed_steps)}")
        return 1
    print('全部步骤成功')
    return 0


def main():
    parser = argparse.ArgumentParser(description='电商产品一体化工作流运行器')
    parser.add_argument('--url', type=str, help='1688 商品 URL')
    parser.add_argument('--url-file', type=str, help='批量处理的 URL 文件')
    parser.add_argument('--lightweight', action='store_true', help='跳过采集步骤，直接从采集箱继续')
    parser.add_argument('--no-publish', action='store_true', help='执行到ERP保存为止，不做最终发布')
    args = parser.parse_args()

    runner = WorkflowRunner()

    if args.url:
        if args.lightweight:
            results = runner.run_lightweight(args.url, publish=not args.no_publish)
        else:
            results = runner.run_full(args.url, publish=not args.no_publish)
        raise SystemExit(print_summary(results))

    if args.url_file:
        with open(args.url_file, 'r', encoding='utf-8') as handle:
            urls = [line.strip() for line in handle if line.strip()]

        exit_code = 0
        for index, url in enumerate(urls, start=1):
            print(f'\n[{index}/{len(urls)}] {url}')
            if args.lightweight:
                results = runner.run_lightweight(url, publish=not args.no_publish)
            else:
                results = runner.run_full(url, publish=not args.no_publish)
            exit_code = max(exit_code, print_summary(results))
        raise SystemExit(exit_code)

    print('请使用 --url 或 --url-file 提供待执行商品链接')
    raise SystemExit(1)


if __name__ == '__main__':
    main()