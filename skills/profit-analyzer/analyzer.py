#!/usr/bin/env python3
"""Shopee TW profit analysis and Feishu Bitable sync."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, cast

import psycopg2
import requests

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = WORKSPACE_ROOT / 'scripts'
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from multisite_config import load_market_bundle, normalize_site_context  # type: ignore

CONFIG_ENV_PATH = WORKSPACE_ROOT / 'config' / 'config.env'
FEISHU_CONFIG_PATH = WORKSPACE_ROOT / 'config' / 'profit_analysis_feishu.json'

DB_DEFAULTS = {
    'host': 'localhost',
    'database': 'ecommerce_data',
    'user': 'superuser',
    'password': 'Admin123!',
}

DEFAULT_FEISHU_APP_ID = 'cli_a933f5b61d39dcb5'
DEFAULT_FEISHU_APP_SECRET = 'CFuYjJZtEOFVfIhXINopPe4haJUul0cY'
DEFAULT_FEISHU_APP_NAME = 'shopee商品上架利润分析'

CHANNEL = 'shopee'
SITE = 'TW'

COMMISSION_RATE = 0.14
TRANSACTION_FEE_RATE = 0.025
PRE_SALE_SERVICE_RATE = 0.0
AGENT_FEE_CNY = 3.00
COMMISSION_FREE_DAYS = 90

FIRST_WEIGHT_G = 500
FIRST_WEIGHT_TWD = 70.00
CONTINUE_WEIGHT_G = 500
CONTINUE_WEIGHT_TWD = 30.00

BUYER_SHIPPING_ORDINARY = 55.00
BUYER_SHIPPING_DISCOUNT = 30.00
BUYER_SHIPPING_FREE = 0.00

DEFAULT_TARGET_PROFIT_RATE = 0.20

TEXT_FIELD = 1
NUMBER_FIELD = 2

REQUIRED_FIELDS: List[Tuple[str, int]] = [
    ('SKU名称', TEXT_FIELD),
    ('商品主货号', TEXT_FIELD),
    ('采购价(CNY)', NUMBER_FIELD),
    ('藏价(CNY)', NUMBER_FIELD),
    ('头程运费(CNY)', NUMBER_FIELD),
    ('货代费(CNY)', NUMBER_FIELD),
    ('是否免佣期', TEXT_FIELD),
    ('生效佣金率(%)', NUMBER_FIELD),
    ('佣金(CNY)', NUMBER_FIELD),
    ('预售服务费(CNY)', NUMBER_FIELD),
    ('交易手续费(CNY)', NUMBER_FIELD),
    ('平台费(CNY)', NUMBER_FIELD),
    ('建议售价(CNY)', NUMBER_FIELD),
    ('建议售价(TWD)', NUMBER_FIELD),
    ('预计利润(CNY)', NUMBER_FIELD),
    ('利润率(%)', NUMBER_FIELD),
    ('重量(g)', NUMBER_FIELD),
    ('重量(kg)', NUMBER_FIELD),
    ('长(cm)', NUMBER_FIELD),
    ('宽(cm)', NUMBER_FIELD),
    ('高(cm)', NUMBER_FIELD),
    ('卖家运费(TWD)', NUMBER_FIELD),
    ('买家运费(TWD)', NUMBER_FIELD),
    ('藏价(TWD)', NUMBER_FIELD),
    ('头程运费(TWD)', NUMBER_FIELD),
    ('货代费(TWD)', NUMBER_FIELD),
    ('佣金(TWD)', NUMBER_FIELD),
    ('交易手续费(TWD)', NUMBER_FIELD),
    ('预售服务费(TWD)', NUMBER_FIELD),
    ('平台费(TWD)', NUMBER_FIELD),
    ('总成本(CNY)', NUMBER_FIELD),
    ('总成本(TWD)', NUMBER_FIELD),
    ('分析状态', TEXT_FIELD),
    ('错误信息', TEXT_FIELD),
    ('货源ID', TEXT_FIELD),
    ('渠道', TEXT_FIELD),
    ('站点', TEXT_FIELD),
    ('商品状态', TEXT_FIELD),
    ('唯一键', TEXT_FIELD),
    ('目标利润率(%)', NUMBER_FIELD),
    ('同步时间', TEXT_FIELD),
]


def load_env_file(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        env[key.strip()] = value.strip()
    return env


def parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace('kg', '').replace('g', '').replace(',', '')
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def round_or_none(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(value, digits)


def parse_json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return cast(Dict[str, Any], value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return cast(Dict[str, Any], decoded) if isinstance(decoded, dict) else {}
    return {}


class FeishuBitableClient:
    def __init__(self, config_path: Path, env: Dict[str, str]):
        self.config_path = config_path
        self.app_id = os.environ.get('FEISHU_APP_ID') or env.get('FEISHU_APP_ID') or DEFAULT_FEISHU_APP_ID
        self.app_secret = os.environ.get('FEISHU_APP_SECRET') or env.get('FEISHU_APP_SECRET') or DEFAULT_FEISHU_APP_SECRET
        self.config = self._load_or_create_config()
        self.app_token = self.config['app_token']
        self.table_id = self.config['table_id']
        self.url = self.config['url']
        self.primary_field_name = '商品标题'

    def _load_or_create_config(self) -> Dict[str, str]:
        if self.config_path.exists():
            return json.loads(self.config_path.read_text(encoding='utf-8'))

        token = self._tenant_access_token()
        response = requests.post(
            'https://open.feishu.cn/open-apis/bitable/v1/apps',
            headers=self._headers(token),
            json={'name': DEFAULT_FEISHU_APP_NAME},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get('code') != 0:
            raise RuntimeError(f"创建飞书多维表失败: {payload}")

        app = payload['data']['app']
        config = {
            'document_name': DEFAULT_FEISHU_APP_NAME,
            'app_token': app['app_token'],
            'table_id': app['default_table_id'],
            'table_name': '利润分析明细',
            'url': app['url'],
        }
        self.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
        return config

    def _tenant_access_token(self) -> str:
        response = requests.post(
            'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
            json={'app_id': self.app_id, 'app_secret': self.app_secret},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get('code') != 0:
            raise RuntimeError(f"获取飞书访问令牌失败: {payload}")
        return payload['tenant_access_token']

    def _headers(self, token: Optional[str] = None) -> Dict[str, str]:
        auth_token = token or self._tenant_access_token()
        return {
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json; charset=utf-8',
        }

    def _request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        response = requests.request(
            method,
            f'https://open.feishu.cn/open-apis{path}',
            headers=self._headers(),
            params=params,
            json=json_body,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get('code') != 0:
            raise RuntimeError(f'飞书接口失败 {path}: {payload}')
        return payload

    def ensure_schema(self) -> None:
        fields = self.list_fields()
        existing_names = {item['field_name'] for item in fields}
        primary = next((item for item in fields if item.get('is_primary')), None)
        if primary and primary.get('field_name') != self.primary_field_name:
            self._request(
                'PUT',
                f'/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/fields/{primary["field_id"]}',
                json_body={'field_name': self.primary_field_name, 'type': primary['type']},
            )
            existing_names.discard(primary.get('field_name'))
            existing_names.add(self.primary_field_name)

        for field_name, field_type in REQUIRED_FIELDS:
            if field_name in existing_names:
                continue
            self._request(
                'POST',
                f'/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/fields',
                json_body={'field_name': field_name, 'type': field_type},
            )

    def delete_record(self, record_id: str) -> None:
        self._request('DELETE', f'/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/{record_id}')

    def cleanup_empty_records(self) -> int:
        removed = 0
        for item in self.list_records():
            if item.get('fields'):
                continue
            self.delete_record(item['record_id'])
            removed += 1
        return removed

    def list_fields(self) -> List[Dict[str, Any]]:
        payload = self._request('GET', f'/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/fields', params={'page_size': 500})
        return payload['data']['items']

    def list_records(self) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        while True:
            params: Dict[str, Any] = {'page_size': 500}
            if page_token:
                params['page_token'] = page_token
            payload = self._request('GET', f'/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records', params=params)
            data = payload['data']
            records.extend(data.get('items', []))
            if not data.get('has_more'):
                break
            page_token = data.get('page_token')
        return records

    def upsert_records(self, rows: List[Dict[str, Any]]) -> Dict[str, int]:
        self.ensure_schema()
        removed_empty = self.cleanup_empty_records()
        removed_stale = 0
        existing_by_key: Dict[str, str] = {}
        existing_records = self.list_records()
        incoming_keys = {str(row['唯一键']) for row in rows if row.get('唯一键')}
        target_alibaba_ids = {str(row.get('货源ID') or '') for row in rows if row.get('货源ID')}

        for item in existing_records:
            fields = item.get('fields', {})
            unique_key = fields.get('唯一键')
            if unique_key:
                existing_by_key[str(unique_key)] = item['record_id']

        if target_alibaba_ids:
            for item in existing_records:
                fields = item.get('fields', {})
                unique_key = str(fields.get('唯一键') or '')
                alibaba_id = str(fields.get('货源ID') or '')
                if alibaba_id in target_alibaba_ids and unique_key and unique_key not in incoming_keys:
                    self.delete_record(item['record_id'])
                    existing_by_key.pop(unique_key, None)
                    removed_stale += 1

        created = 0
        updated = 0
        for row in rows:
            unique_key = row['唯一键']
            fields = {self.primary_field_name: row[self.primary_field_name], **row}
            record_id = existing_by_key.get(unique_key)
            if record_id:
                self._request(
                    'PUT',
                    f'/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/{record_id}',
                    json_body={'fields': fields},
                )
                updated += 1
            else:
                self._request(
                    'POST',
                    f'/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records',
                    json_body={'fields': fields},
                )
                created += 1
        return {'created': created, 'updated': updated, 'removed_empty': removed_empty, 'removed_stale': removed_stale}


class ProfitAnalyzer:
    def __init__(self, target_profit_rate: float = DEFAULT_TARGET_PROFIT_RATE):
        self.env = load_env_file(CONFIG_ENV_PATH)
        self.db_config = {
            'host': os.environ.get('DB_HOST') or self.env.get('DB_HOST') or DB_DEFAULTS['host'],
            'database': os.environ.get('DB_NAME') or self.env.get('DB_NAME') or DB_DEFAULTS['database'],
            'user': os.environ.get('DB_USER') or self.env.get('DB_USER') or DB_DEFAULTS['user'],
            'password': os.environ.get('DB_PASSWORD') or self.env.get('DB_PASSWORD') or DB_DEFAULTS['password'],
        }
        self.target_profit_rate = target_profit_rate
        self.exchange_rate = self._get_exchange_rate()
        self.feishu = FeishuBitableClient(FEISHU_CONFIG_PATH, self.env)

    def _connect(self):
        return psycopg2.connect(**self.db_config)

    def _get_exchange_rate(self, to_currency: str = 'TWD') -> float:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT rate
                        FROM exchange_rates
                        WHERE from_currency = 'CNY' AND to_currency = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (to_currency,),
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        return float(row[0])
        except Exception:
            pass
        if str(to_currency).upper() == 'PHP':
            return 7.80
        return 4.50

    def _resolve_runtime_bundle(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        site_context = normalize_site_context(payload or {})
        try:
            return load_market_bundle(None, market_code=site_context.get('market_code'), site_code=site_context.get('site_code'))
        except Exception:
            return {
                'site_context': site_context,
                'market_config': {},
                'shipping_profile': {},
                'fee_profile': {},
                'content_policy': {},
                'prompt_profile': {},
            }

    def _fee_profile_value(self, fee_profile: Optional[Dict[str, Any]], key: str) -> Any:
        profile = fee_profile or {}
        direct = profile.get(key)
        if direct not in (None, ''):
            return direct
        metadata = parse_json_object(profile.get('metadata'))
        return metadata.get(key)

    def _runtime_value(self, fee_profile: Optional[Dict[str, Any]], shipping_profile: Optional[Dict[str, Any]], key: str) -> Any:
        fee_value = self._fee_profile_value(fee_profile, key)
        if fee_value not in (None, ''):
            return fee_value
        return self._shipping_profile_value(shipping_profile, key)

    def _shipping_profile_value(self, shipping_profile: Optional[Dict[str, Any]], key: str) -> Any:
        profile = shipping_profile or {}
        direct = profile.get(key)
        if direct not in (None, ''):
            return direct
        metadata = parse_json_object(profile.get('metadata'))
        return metadata.get(key)

    def _calculate_chargeable_weight_g(self, row: Dict[str, Any], shipping_profile: Dict[str, Any]) -> float:
        actual_weight_g = parse_float(row.get('package_weight')) or 0.0
        length = parse_float(row.get('package_length')) or 0.0
        width = parse_float(row.get('package_width')) or 0.0
        height = parse_float(row.get('package_height')) or 0.0
        divisor = parse_float(self._shipping_profile_value(shipping_profile, 'volumetric_divisor'))
        mode = str(self._shipping_profile_value(shipping_profile, 'chargeable_weight_mode') or '').strip().lower()

        volumetric_weight_g = 0.0
        if divisor and divisor > 0 and length > 0 and width > 0 and height > 0:
            volumetric_weight_g = (length * width * height / divisor) * 1000.0

        if mode in ('max_actual_or_volumetric', 'max_actual_volumetric'):
            chargeable_weight_g = max(actual_weight_g, volumetric_weight_g)
        else:
            chargeable_weight_g = actual_weight_g

        rounding_base = parse_float(self._shipping_profile_value(shipping_profile, 'weight_rounding_base_g'))
        if rounding_base and rounding_base > 0:
            chargeable_weight_g = math.ceil(chargeable_weight_g / rounding_base) * rounding_base

        return round(chargeable_weight_g, 2)

    def fetch_target_rows(self, alibaba_ids: List[str]) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                p.id AS product_db_id,
                p.alibaba_product_id,
                p.product_id,
                p.product_id_new,
                COALESCE(NULLIF(p.optimized_title, ''), NULLIF(p.title, ''), '') AS display_title,
                p.status,
                p.skus,
                p.logistics,
                p.created_at,
                p.listing_updated_at,
                ps.id AS product_sku_db_id,
                ps.sku_name,
                ps.price,
                ps.stock,
                ps.package_weight,
                ps.package_length,
                ps.package_width,
                ps.package_height
            FROM products p
            LEFT JOIN product_skus ps ON p.id = ps.product_id AND COALESCE(ps.is_deleted, 0) = 0
                        WHERE p.alibaba_product_id = ANY(%s)
                            AND COALESCE(p.is_deleted, 0) = 0
            ORDER BY p.alibaba_product_id, p.id DESC, ps.id ASC
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (alibaba_ids,))
                rows = cur.fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            product_skus = row[6]
            if isinstance(product_skus, str):
                try:
                    product_skus = json.loads(product_skus)
                except json.JSONDecodeError:
                    product_skus = []
            results.append({
                'product_db_id': row[0],
                'alibaba_product_id': row[1],
                'product_id': row[2],
                'product_id_new': row[3],
                'title': row[4],
                'status': row[5],
                'product_skus': product_skus or [],
                'logistics': row[7],
                'created_at': row[8],
                'listing_updated_at': row[9],
                'product_sku_db_id': row[10],
                'sku_name': row[11],
                'price': row[12],
                'stock': row[13],
                'package_weight': row[14],
                'package_length': row[15],
                'package_width': row[16],
                'package_height': row[17],
            })
        return results

    def _status_rank(self, status: Optional[str]) -> int:
        order = {
            'published': 5,
            'optimized': 4,
            'listed': 3,
            'collected': 2,
            'pending': 1,
        }
        return order.get((status or '').lower(), 0)

    def _fallback_price(self, row: Dict[str, Any]) -> Optional[float]:
        sku_name = (row.get('sku_name') or '').strip()
        for sku in row.get('product_skus', []):
            candidate_names = {
                str(sku.get('name') or '').strip(),
                str(sku.get('color') or '').strip(),
            }
            if sku_name and sku_name not in candidate_names:
                continue
            price = parse_float(sku.get('price') or sku.get('source_price') or sku.get('source'))
            if price is not None:
                return price
        return None

    def dedupe_rows(self, rows: Iterable[Dict[str, Any]], site_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        normalized_context = normalize_site_context(site_context or {})
        deduped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            sku_name = (row.get('sku_name') or '').strip()
            product_id_new = (row.get('product_id_new') or '').strip()
            if not sku_name or not product_id_new:
                continue
            key = f'{CHANNEL}|{normalized_context.get("site_code", "shopee_tw")}|{product_id_new}|{sku_name}'
            price = parse_float(row.get('price'))
            weight = parse_float(row.get('package_weight'))
            score = (
                self._status_rank(row.get('status')),
                1 if price is not None else 0,
                1 if weight is not None else 0,
                int(row.get('product_db_id') or 0),
            )
            previous = deduped.get(key)
            if previous is None or score > previous['_score']:
                deduped[key] = {**row, '_score': score, 'unique_key': key}
        return list(deduped.values())

    def calculate_sls_shipping(self, weight_g: float, order_type: str = 'ordinary', shipping_profile: Optional[Dict[str, Any]] = None, fee_profile: Optional[Dict[str, Any]] = None, exchange_rate: Optional[float] = None) -> Dict[str, float]:
        shipping_profile = shipping_profile or {}
        fee_profile = fee_profile or {}
        exchange_rate = exchange_rate or self.exchange_rate

        first_weight_g = parse_float(self._shipping_profile_value(shipping_profile, 'first_weight_g')) or FIRST_WEIGHT_G
        first_weight_fee = parse_float(self._shipping_profile_value(shipping_profile, 'first_weight_fee')) or FIRST_WEIGHT_TWD
        continue_weight_g = parse_float(self._shipping_profile_value(shipping_profile, 'continue_weight_g')) or CONTINUE_WEIGHT_G
        continue_weight_fee = parse_float(self._shipping_profile_value(shipping_profile, 'continue_weight_fee')) or CONTINUE_WEIGHT_TWD

        if weight_g <= first_weight_g:
            seller_pays_twd = first_weight_fee
        else:
            seller_pays_twd = first_weight_fee + math.ceil((weight_g - first_weight_g) / max(1.0, continue_weight_g)) * continue_weight_fee

        subsidy_rules = shipping_profile.get('subsidy_rules_json') or {}
        if order_type == 'discount':
            buyer_pays_twd = parse_float(self._fee_profile_value(fee_profile, 'buyer_shipping_discount')) or parse_float(subsidy_rules.get('discount_buyer_shipping')) or BUYER_SHIPPING_DISCOUNT
        elif order_type == 'free':
            buyer_pays_twd = parse_float(self._fee_profile_value(fee_profile, 'buyer_shipping_free')) or parse_float(subsidy_rules.get('free_buyer_shipping')) or BUYER_SHIPPING_FREE
        else:
            buyer_pays_twd = parse_float(self._fee_profile_value(fee_profile, 'buyer_shipping_ordinary')) or parse_float(subsidy_rules.get('ordinary_buyer_shipping')) or BUYER_SHIPPING_ORDINARY

        hidden_price_twd = seller_pays_twd - buyer_pays_twd
        return {
            'seller_pays_twd': round(seller_pays_twd, 2),
            'buyer_pays_twd': round(buyer_pays_twd, 2),
            'hidden_price_twd': round(hidden_price_twd, 2),
            'hidden_price_cny': round(hidden_price_twd / exchange_rate, 4),
        }

    def _commission_rate_for_row(self, row: Dict[str, Any], shipping_profile: Optional[Dict[str, Any]] = None, fee_profile: Optional[Dict[str, Any]] = None) -> float:
        reference = row.get('listing_updated_at') or row.get('created_at')
        if isinstance(reference, str):
            try:
                reference = datetime.fromisoformat(reference)
            except ValueError:
                reference = None
        shipping_profile = shipping_profile or {}
        commission_free_days = int(parse_float(self._runtime_value(fee_profile, shipping_profile, 'commission_free_days')) or COMMISSION_FREE_DAYS)
        commission_rate = parse_float(self._runtime_value(fee_profile, shipping_profile, 'commission_rate'))
        if isinstance(reference, datetime) and datetime.now() - reference <= timedelta(days=commission_free_days):
            return 0.0
        return commission_rate if commission_rate is not None else COMMISSION_RATE

    def _domestic_shipping_cny_for_row(self, row: Dict[str, Any]) -> float:
        logistics = row.get('logistics') or {}
        if isinstance(logistics, str):
            try:
                logistics = json.loads(logistics)
            except json.JSONDecodeError:
                logistics = {}
        if not isinstance(logistics, dict):
            return 0.0

        freight_info = logistics.get('freight_info') or {}
        if not isinstance(freight_info, dict):
            return 0.0

        total_cost = parse_float(freight_info.get('total_cost'))
        if total_cost is not None:
            return max(total_cost, 0.0)

        display_amount = str(freight_info.get('display_amount') or '').strip()
        if display_amount:
            cleaned = display_amount.replace('¥', '').replace('CNY', '').replace('起', '').strip()
            amount = parse_float(cleaned)
            if amount is not None:
                return max(amount, 0.0)

        display_text = str(freight_info.get('display_text') or '').strip()
        if display_text:
            amount = parse_float(display_text.replace('运费', '').replace('¥', '').replace('起', '').strip())
            if amount is not None:
                return max(amount, 0.0)

        return 0.0

    def analyze_row(self, row: Dict[str, Any], bundle: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        bundle = bundle or self._resolve_runtime_bundle(row)
        site_context = bundle.get('site_context') or normalize_site_context(row)
        market_config = bundle.get('market_config') or {}
        shipping_profile = bundle.get('shipping_profile') or {}
        fee_profile = bundle.get('fee_profile') or {}
        local_currency = str(market_config.get('default_currency') or site_context.get('default_currency') or 'TWD').upper()
        exchange_rate = self._get_exchange_rate(local_currency)
        price_cny = parse_float(row.get('price'))
        if price_cny is None:
            price_cny = self._fallback_price(row)
        weight_g = parse_float(row.get('package_weight'))
        unique_key = row['unique_key']
        result: Dict[str, Any] = {
            '商品标题': row.get('title') or '',
            '唯一键': unique_key,
            '渠道': CHANNEL,
            '站点': site_context.get('site_code', 'shopee_tw'),
            '商品主货号': row.get('product_id_new') or row.get('product_id') or '',
            '货源ID': row.get('alibaba_product_id') or '',
            'SKU名称': row.get('sku_name') or '',
            '商品状态': row.get('status') or '',
            '分析状态': 'success',
            '错误信息': '',
            '采购价(CNY)': None,
            '藏价(CNY)': None,
            '头程运费(CNY)': None,
            '货代费(CNY)': None,
            '是否免佣期': '',
            '生效佣金率(%)': None,
            '佣金(CNY)': None,
            '预售服务费(CNY)': None,
            '交易手续费(CNY)': None,
            '平台费(CNY)': None,
            '建议售价(CNY)': None,
            '建议售价(TWD)': None,
            '预计利润(CNY)': None,
            '利润率(%)': None,
            '重量(g)': None,
            '重量(kg)': None,
            '长(cm)': round_or_none(parse_float(row.get('package_length'))),
            '宽(cm)': round_or_none(parse_float(row.get('package_width'))),
            '高(cm)': round_or_none(parse_float(row.get('package_height'))),
            '卖家运费(TWD)': None,
            '买家运费(TWD)': None,
            '藏价(TWD)': None,
            '头程运费(TWD)': None,
            '货代费(TWD)': None,
            '佣金(TWD)': None,
            '交易手续费(TWD)': None,
            '预售服务费(TWD)': None,
            '平台费(TWD)': None,
            '总成本(CNY)': None,
            '总成本(TWD)': None,
            '目标利润率(%)': round(self.target_profit_rate * 100, 2),
            '同步时间': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        if price_cny is None:
            result['分析状态'] = 'error'
            result['错误信息'] = '缺少采购价'
            return result
        if weight_g is None:
            result['分析状态'] = 'error'
            result['错误信息'] = '缺少SKU重量'
            return result

        chargeable_weight_g = self._calculate_chargeable_weight_g(row, shipping_profile)
        shipping = self.calculate_sls_shipping(chargeable_weight_g, shipping_profile=shipping_profile, fee_profile=fee_profile, exchange_rate=exchange_rate)
        domestic_shipping_cny = self._domestic_shipping_cny_for_row(row)
        domestic_shipping_twd = domestic_shipping_cny * exchange_rate
        agent_fee_cny = parse_float(self._runtime_value(fee_profile, shipping_profile, 'agent_fee_cny')) or AGENT_FEE_CNY
        agent_fee_twd = agent_fee_cny * exchange_rate
        total_cost_cny = price_cny + domestic_shipping_cny + agent_fee_cny + shipping['hidden_price_cny']
        total_cost_twd = total_cost_cny * exchange_rate

        commission_rate = self._commission_rate_for_row(row, shipping_profile=shipping_profile, fee_profile=fee_profile)
        is_commission_free = commission_rate == 0.0
        transaction_fee_rate = parse_float(self._runtime_value(fee_profile, shipping_profile, 'transaction_fee_rate'))
        if transaction_fee_rate is None:
            transaction_fee_rate = TRANSACTION_FEE_RATE
        pre_sale_service_rate = parse_float(self._runtime_value(fee_profile, shipping_profile, 'pre_sale_service_rate'))
        if pre_sale_service_rate is None:
            pre_sale_service_rate = PRE_SALE_SERVICE_RATE
        total_fee_rate = commission_rate + transaction_fee_rate + pre_sale_service_rate
        suggested_price_raw_twd = total_cost_twd / max(0.01, 1 - total_fee_rate - self.target_profit_rate)
        suggested_price_twd = math.ceil(suggested_price_raw_twd)
        suggested_price_cny = suggested_price_twd / exchange_rate

        commission_twd = suggested_price_twd * commission_rate
        transaction_fee_twd = suggested_price_twd * transaction_fee_rate
        pre_sale_service_twd = suggested_price_twd * pre_sale_service_rate
        platform_fee_twd = commission_twd + transaction_fee_twd + pre_sale_service_twd
        profit_twd = suggested_price_twd - platform_fee_twd - total_cost_twd
        profit_cny = profit_twd / exchange_rate
        profit_rate = (profit_twd / suggested_price_twd) * 100 if suggested_price_twd else 0

        result.update({
            '采购价(CNY)': round(price_cny, 4),
            '藏价(CNY)': shipping['hidden_price_cny'],
            '头程运费(CNY)': round(domestic_shipping_cny, 4),
            '货代费(CNY)': round(agent_fee_cny, 4),
            '是否免佣期': '是' if is_commission_free else '否',
            '生效佣金率(%)': round(commission_rate * 100, 2),
            '佣金(CNY)': round(commission_twd / exchange_rate, 4),
            '预售服务费(CNY)': round(pre_sale_service_twd / exchange_rate, 4),
            '交易手续费(CNY)': round(transaction_fee_twd / exchange_rate, 4),
            '平台费(CNY)': round(platform_fee_twd / exchange_rate, 4),
            '建议售价(CNY)': round(suggested_price_cny, 4),
            '建议售价(TWD)': suggested_price_twd,
            '预计利润(CNY)': round(profit_cny, 4),
            '利润率(%)': round(profit_rate, 2),
            '重量(g)': round(chargeable_weight_g, 2),
            '重量(kg)': round(chargeable_weight_g / 1000.0, 4),
            '卖家运费(TWD)': shipping['seller_pays_twd'],
            '买家运费(TWD)': shipping['buyer_pays_twd'],
            '藏价(TWD)': shipping['hidden_price_twd'],
            '头程运费(TWD)': round(domestic_shipping_twd, 2),
            '货代费(TWD)': round(agent_fee_twd, 2),
            '佣金(TWD)': round(commission_twd, 2),
            '交易手续费(TWD)': round(transaction_fee_twd, 2),
            '预售服务费(TWD)': round(pre_sale_service_twd, 2),
            '平台费(TWD)': round(platform_fee_twd, 2),
            '总成本(CNY)': round(total_cost_cny, 4),
            '总成本(TWD)': round(total_cost_twd, 2),
        })
        return result

    def analyze_products(self, alibaba_ids: List[str], site_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        entries = self.build_analysis_entries(alibaba_ids, site_context=site_context)
        return [entry['result'] for entry in entries]

    def build_analysis_entries(self, alibaba_ids: List[str], site_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        bundle = self._resolve_runtime_bundle(site_context or {})
        rows = self.fetch_target_rows(alibaba_ids)
        deduped = self.dedupe_rows(rows, site_context=bundle.get('site_context'))
        deduped.sort(key=lambda item: (item.get('alibaba_product_id') or '', item.get('product_id_new') or '', item.get('sku_name') or ''))
        return [
            {
                'source': row,
                'site_context': dict(bundle.get('site_context') or {}),
                'result': self.analyze_row({**row, **(bundle.get('site_context') or {})}, bundle=bundle),
            }
            for row in deduped
        ]

    def save_results_to_db(self, entries: List[Dict[str, Any]]) -> Dict[str, int]:
        inserted = 0
        updated = 0
        with self._connect() as conn:
            with conn.cursor() as cur:
                for entry in entries:
                    source = entry['source']
                    result = entry['result']
                    entry_site_context = normalize_site_context(
                        entry.get('site_context')
                        or {
                            'site_code': result.get('站点'),
                            'market_code': result.get('站点'),
                        }
                    )
                    product_id = source.get('product_db_id')
                    sku_id = source.get('product_sku_db_id')
                    if not product_id:
                        continue

                    bundle = self._resolve_runtime_bundle(entry_site_context)
                    site_context = bundle.get('site_context') or {}
                    market_config = bundle.get('market_config') or {}
                    shipping_profile = bundle.get('shipping_profile') or {}
                    site = result.get('站点') or entry_site_context.get('site_code') or SITE
                    currency = str(market_config.get('default_currency') or site_context.get('default_currency') or 'TWD').upper()

                    cur.execute(
                        """
                        DELETE FROM product_analysis
                        WHERE product_id = %s
                          AND platform = %s
                          AND site = %s
                          AND (
                                (sku_id = %s)
                                OR (sku_id IS NULL AND %s IS NULL)
                          )
                        """,
                        (product_id, CHANNEL, site, sku_id, sku_id),
                    )
                    if cur.rowcount:
                        updated += cur.rowcount

                    cur.execute(
                        """
                        INSERT INTO product_analysis (
                            product_id,
                            sku_id,
                            platform,
                            site,
                            currency,
                            site_listing_id,
                            fee_profile_code,
                            shipping_profile_code,
                            price_policy_code,
                            chargeable_weight_g,
                            hidden_shipping_cost_local,
                            platform_shipping_fee_local,
                            estimated_profit_local,
                            purchase_price_cny,
                            weight_kg,
                            shipping_cn,
                            agent_fee_cny,
                            sls_fee_cny,
                            sls_fee_twd,
                            commission_cny,
                            commission_twd,
                            service_fee_cny,
                            service_fee_twd,
                            transaction_fee_cny,
                            transaction_fee_twd,
                            total_cost_cny,
                            total_cost_twd,
                            exchange_rate,
                            suggested_price_twd,
                            suggested_price_cny,
                            estimated_profit_cny,
                            profit_rate,
                            analysis_date,
                            remarks,
                            updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, %s, CURRENT_TIMESTAMP
                        )
                        """,
                        (
                            product_id,
                            sku_id,
                            CHANNEL,
                            site,
                            currency,
                            None,
                            None,
                            shipping_profile.get('shipping_profile_code'),
                            None,
                            result.get('重量(g)'),
                            result.get('藏价(TWD)'),
                            result.get('平台费(TWD)'),
                            result.get('预计利润(CNY)'),
                            result.get('采购价(CNY)'),
                            result.get('重量(kg)'),
                            result.get('头程运费(CNY)'),
                            result.get('货代费(CNY)'),
                            result.get('藏价(CNY)'),
                            result.get('藏价(TWD)'),
                            result.get('佣金(CNY)'),
                            result.get('佣金(TWD)'),
                            result.get('预售服务费(CNY)'),
                            result.get('预售服务费(TWD)'),
                            result.get('交易手续费(CNY)'),
                            result.get('交易手续费(TWD)'),
                            result.get('总成本(CNY)'),
                            result.get('总成本(TWD)'),
                            self._get_exchange_rate(currency),
                            result.get('建议售价(TWD)'),
                            result.get('建议售价(CNY)'),
                            result.get('预计利润(CNY)'),
                            round_or_none((result.get('利润率(%)') or 0) / 100.0, 4) if result.get('利润率(%)') is not None else None,
                            result.get('错误信息') or None,
                        ),
                    )
                    inserted += 1
        return {'inserted': inserted, 'replaced': updated}

    def analyze_product(self, product_payload: Dict[str, Any]) -> Dict[str, Any]:
        alibaba_product_id = str(product_payload.get('alibaba_product_id') or '').strip()
        if not alibaba_product_id:
            return {
                'status': 'error',
                'message': '缺少 alibaba_product_id',
            }

        bundle = self._resolve_runtime_bundle(product_payload)
        rows = self.analyze_products([alibaba_product_id], site_context=bundle.get('site_context'))
        success_rows = [row for row in rows if row.get('分析状态') == 'success']
        if success_rows:
            primary = success_rows[0]
            local_currency = str((bundle.get('market_config') or {}).get('default_currency') or (bundle.get('site_context') or {}).get('default_currency') or 'TWD').upper()
            return {
                'status': 'success',
                'message': '利润分析成功',
                'module': 'profit-analyzer',
                'alibaba_product_id': alibaba_product_id,
                'product_id_new': primary.get('商品主货号'),
                'sku_name': primary.get('SKU名称'),
                'weight_g': primary.get('重量(g)'),
                'weight_kg': primary.get('重量(kg)'),
                'purchase_price_cny': primary.get('采购价(CNY)'),
                'domestic_shipping_cny': primary.get('头程运费(CNY)'),
                'agent_fee_cny': primary.get('货代费(CNY)'),
                'currency': local_currency,
                'exchange_rate': self._get_exchange_rate(local_currency),
                'sls_twd': primary.get('卖家运费(TWD)'),
                'sls_shipping_twd': primary.get('卖家运费(TWD)'),
                'buyer_shipping_twd': primary.get('买家运费(TWD)'),
                'hidden_shipping_twd': primary.get('藏价(TWD)'),
                'hidden_shipping_cny': primary.get('藏价(CNY)'),
                'domestic_shipping_twd': primary.get('头程运费(TWD)'),
                'agent_fee_twd': primary.get('货代费(TWD)'),
                'commission_twd': primary.get('佣金(TWD)'),
                'commission_cny': primary.get('佣金(CNY)'),
                'transaction_fee_twd': primary.get('交易手续费(TWD)'),
                'transaction_fee_cny': primary.get('交易手续费(CNY)'),
                'pre_sale_service_fee_twd': primary.get('预售服务费(TWD)'),
                'pre_sale_service_fee_cny': primary.get('预售服务费(CNY)'),
                'platform_fee_twd': primary.get('平台费(TWD)'),
                'total_platform_fee_twd': primary.get('平台费(TWD)'),
                'platform_fee_cny': primary.get('平台费(CNY)'),
                'total_cost_twd': primary.get('总成本(TWD)'),
                'total_cost_cny': primary.get('总成本(CNY)'),
                'suggested_price_twd': primary.get('建议售价(TWD)'),
                'suggested_price_cny': primary.get('建议售价(CNY)'),
                'target_profit_rate': self.target_profit_rate,
                'profit_rate': primary.get('利润率(%)'),
                'estimated_profit_twd': round(
                    float(primary.get('建议售价(TWD)') or 0)
                    - float(primary.get('平台费(TWD)') or 0)
                    - float(primary.get('总成本(TWD)') or 0),
                    2,
                ),
                'gross_profit_twd': round(
                    float(primary.get('建议售价(TWD)') or 0)
                    - float(primary.get('平台费(TWD)') or 0)
                    - float(primary.get('总成本(TWD)') or 0),
                    2,
                ),
                'estimated_profit_cny': primary.get('预计利润(CNY)'),
                'rows': rows,
            }

        if rows:
            first_error = rows[0]
            return {
                'status': 'error',
                'message': first_error.get('错误信息') or '利润分析失败',
                'module': 'profit-analyzer',
                'alibaba_product_id': alibaba_product_id,
                'rows': rows,
            }

        return {
            'status': 'error',
            'message': f'未找到可分析的商品数据: {alibaba_product_id}',
            'module': 'profit-analyzer',
            'alibaba_product_id': alibaba_product_id,
        }

    def run(self, alibaba_ids: List[str], sync_feishu: bool = True,
            site_context: Optional[Dict[str, Any]] = None,
            write_db: bool = True) -> Dict[str, Any]:
        entries = self.build_analysis_entries(alibaba_ids, site_context=site_context)
        results = [entry['result'] for entry in entries]
        db_result = self.save_results_to_db(entries) if write_db else {'inserted': 0, 'replaced': 0}
        sync_result = self.feishu.upsert_records(results) if sync_feishu else None
        return {
            'results': results,
            'db_result': db_result,
            'sync_result': sync_result,
            'feishu_url': self.feishu.url if sync_feishu else None,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Shopee 商品上架利润分析并同步到飞书')
    parser.add_argument('--alibaba-ids', nargs='+', required=True, help='需要分析的 1688 商品 ID 列表')
    parser.add_argument('--profit-rate', type=float, default=DEFAULT_TARGET_PROFIT_RATE, help='目标利润率，默认 0.20')
    parser.add_argument('--market-code', type=str, default=None, help='市场代码，例如 shopee_tw / shopee_ph')
    parser.add_argument('--site-code', type=str, default=None, help='站点代码，例如 shopee_tw / shopee_ph')
    parser.add_argument('--skip-feishu', action='store_true', help='仅写入本地 profit_analysis，不同步飞书')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    analyzer = ProfitAnalyzer(target_profit_rate=args.profit_rate)
    outcome = analyzer.run(
        args.alibaba_ids,
        sync_feishu=not args.skip_feishu,
        site_context={
            'market_code': args.market_code,
            'site_code': args.site_code,
        },
    )
    results = outcome['results']
    print(
        f"本地写入: inserted={outcome['db_result']['inserted']}, "
        f"replaced={outcome['db_result']['replaced']}"
    )
    if outcome['sync_result']:
        print(f"飞书文档: {outcome['feishu_url']}")
        print(
            f"同步结果: created={outcome['sync_result']['created']}, "
            f"updated={outcome['sync_result']['updated']}, "
            f"removed_empty={outcome['sync_result'].get('removed_empty', 0)}"
        )
    else:
        print('飞书同步: skipped')
    print('-' * 80)
    for item in results:
        if item['分析状态'] == 'success':
            print(
                f"✅ {item['货源ID']} | {item['商品主货号']} | {item['SKU名称']} | "
                f"建议售价 {item['建议售价(TWD)']} TWD | 利润 {item['预计利润(CNY)']} CNY | 利润率 {item['利润率(%)']}%"
            )
        else:
            print(f"❌ {item['货源ID']} | {item['商品主货号']} | {item['SKU名称']} | {item['错误信息']}")


if __name__ == '__main__':
    main()