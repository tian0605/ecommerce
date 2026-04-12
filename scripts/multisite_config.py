#!/usr/bin/env python3
"""Helpers for loading multisite market, shipping, and content policy configs."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import psycopg2
from psycopg2 import extensions as psycopg2_extensions


DB_CONFIG = {
    'host': 'localhost',
    'database': 'ecommerce_data',
    'user': 'superuser',
    'password': 'Admin123!',
}

GLOBAL_PROMPT_PROFILE_CODE = 'prompt_global_shopee'

SITE_CONTEXT_KEYS = (
    'market_code',
    'site_code',
    'shop_code',
    'channel_code',
    'default_currency',
    'source_language',
    'listing_language',
)

SITE_DEFAULTS: Dict[str, Dict[str, str]] = {
    'shopee_tw': {
        'market_code': 'shopee_tw',
        'site_code': 'shopee_tw',
        'channel_code': 'shopee',
        'default_currency': 'TWD',
        'source_language': 'zh-CN',
        'listing_language': 'zh-Hant',
    },
    'shopee_ph': {
        'market_code': 'shopee_ph',
        'site_code': 'shopee_ph',
        'channel_code': 'shopee',
        'default_currency': 'PHP',
        'source_language': 'zh-CN',
        'listing_language': 'en',
    },
}


def normalize_site_context(payload: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    payload = dict(payload or {})
    site_code = str(payload.get('site_code') or 'shopee_tw').strip().lower()
    defaults = dict(SITE_DEFAULTS.get(site_code, SITE_DEFAULTS['shopee_tw']))

    for key in SITE_CONTEXT_KEYS:
        value = payload.get(key)
        if value not in (None, ''):
            defaults[key] = str(value).strip()

    defaults['site_code'] = str(defaults.get('site_code') or site_code).strip().lower()
    defaults['market_code'] = str(defaults.get('market_code') or defaults['site_code']).strip().lower()
    return defaults


def _json_value(value: Any, default: Any):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    return default


def _row_to_dict(cur, row) -> Dict[str, Any]:
    columns = [desc[0] for desc in cur.description]
    return dict(zip(columns, row))


def load_market_bundle(
    conn: Optional[psycopg2.extensions.connection] = None,
    *,
    market_code: Optional[str] = None,
    site_code: Optional[str] = None,
) -> Dict[str, Any]:
    context = normalize_site_context({'market_code': market_code, 'site_code': site_code})
    owns_conn = conn is None
    if conn is None:
        conn = psycopg2.connect(**DB_CONFIG)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM market_configs
                WHERE is_active = TRUE
                  AND (market_code = %s OR site_code = %s)
                ORDER BY CASE WHEN market_code = %s THEN 0 ELSE 1 END, id DESC
                LIMIT 1
                """,
                (context['market_code'], context['site_code'], context['market_code']),
            )
            market_row = cur.fetchone()
            market_config = _row_to_dict(cur, market_row) if market_row else {}

            resolved_market = dict(context)
            if market_config:
                for key in ('market_code', 'site_code', 'channel_code', 'default_currency', 'source_language', 'listing_language'):
                    value = market_config.get(key)
                    if value not in (None, ''):
                        resolved_market[key] = value

            shipping_profile_code = market_config.get('default_shipping_profile_code') if market_config else None
            if shipping_profile_code:
                cur.execute(
                    """
                    SELECT *
                    FROM shipping_profiles
                    WHERE shipping_profile_code = %s AND is_active = TRUE
                    LIMIT 1
                    """,
                    (shipping_profile_code,),
                )
            else:
                cur.execute(
                    """
                    SELECT *
                    FROM shipping_profiles
                    WHERE site_code = %s AND is_active = TRUE
                    ORDER BY is_default DESC, id DESC
                    LIMIT 1
                    """,
                    (resolved_market['site_code'],),
                )
            shipping_row = cur.fetchone()
            shipping_profile = _row_to_dict(cur, shipping_row) if shipping_row else {}
            shipping_profile['subsidy_rules_json'] = _json_value(shipping_profile.get('subsidy_rules_json'), {})
            shipping_profile['metadata'] = _json_value(shipping_profile.get('metadata'), {})

            fee_profile = {}
            try:
                fee_profile_code = market_config.get('default_fee_profile_code') if market_config else None
                if fee_profile_code:
                    cur.execute(
                        """
                        SELECT *
                        FROM fee_profiles
                        WHERE fee_profile_code = %s AND is_active = TRUE
                        LIMIT 1
                        """,
                        (fee_profile_code,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT *
                        FROM fee_profiles
                        WHERE site_code = %s AND is_active = TRUE
                        ORDER BY is_default DESC, id DESC
                        LIMIT 1
                        """,
                        (resolved_market['site_code'],),
                    )
                fee_row = cur.fetchone()
                fee_profile = _row_to_dict(cur, fee_row) if fee_row else {}
            except psycopg2.Error:
                fee_profile = {}
            fee_profile['metadata'] = _json_value(fee_profile.get('metadata'), {})

            content_policy_code = market_config.get('default_content_policy_code') if market_config else None
            if content_policy_code:
                cur.execute(
                    """
                    SELECT *
                    FROM content_policies
                    WHERE content_policy_code = %s AND is_active = TRUE
                    LIMIT 1
                    """,
                    (content_policy_code,),
                )
            else:
                cur.execute(
                    """
                    SELECT *
                    FROM content_policies
                    WHERE site_code = %s AND is_active = TRUE
                    ORDER BY is_default DESC, id DESC
                    LIMIT 1
                    """,
                    (resolved_market['site_code'],),
                )
            policy_row = cur.fetchone()
            content_policy = _row_to_dict(cur, policy_row) if policy_row else {}
            content_policy['forbidden_terms_json'] = _json_value(content_policy.get('forbidden_terms_json'), [])
            content_policy['required_sections_json'] = _json_value(content_policy.get('required_sections_json'), [])
            content_policy['term_mapping_json'] = _json_value(content_policy.get('term_mapping_json'), {})
            content_policy['validation_rule_set'] = _json_value(content_policy.get('validation_rule_set'), {})
            content_policy['metadata'] = _json_value(content_policy.get('metadata'), {})

            prompt_profile = {}
            try:
                prompt_profile_code = content_policy.get('prompt_profile_code') if content_policy else None
                if prompt_profile_code:
                    cur.execute(
                        """
                        SELECT *
                        FROM prompt_profiles
                        WHERE prompt_profile_code = %s AND is_active = TRUE
                        LIMIT 1
                        """,
                        (prompt_profile_code,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT *
                        FROM prompt_profiles
                                                WHERE is_active = TRUE
                                                    AND (prompt_profile_code = %s OR site_code = %s)
                                                ORDER BY CASE WHEN prompt_profile_code = %s THEN 0 ELSE 1 END,
                                                                 is_default DESC,
                                                                 id DESC
                        LIMIT 1
                        """,
                                                (GLOBAL_PROMPT_PROFILE_CODE, resolved_market['site_code'], GLOBAL_PROMPT_PROFILE_CODE),
                    )
                prompt_row = cur.fetchone()
                prompt_profile = _row_to_dict(cur, prompt_row) if prompt_row else {}
            except psycopg2.Error:
                prompt_profile = {}
            prompt_profile['template_variables_json'] = _json_value(prompt_profile.get('template_variables_json'), {})
            prompt_profile['metadata'] = _json_value(prompt_profile.get('metadata'), {})

            return {
                'site_context': normalize_site_context({
                    'market_code': resolved_market.get('market_code'),
                    'site_code': resolved_market.get('site_code'),
                    'shop_code': context.get('shop_code'),
                    'channel_code': resolved_market.get('channel_code'),
                    'default_currency': resolved_market.get('default_currency'),
                    'source_language': content_policy.get('source_language') or resolved_market.get('source_language'),
                    'listing_language': content_policy.get('listing_language') or resolved_market.get('listing_language'),
                }),
                'market_config': market_config,
                'shipping_profile': shipping_profile,
                'fee_profile': fee_profile,
                'content_policy': content_policy,
                'prompt_profile': prompt_profile,
            }
    finally:
        if conn is not None:
            if owns_conn:
                conn.close()
            elif conn.closed == 0 and conn.status != psycopg2_extensions.STATUS_READY:
                conn.rollback()