-- Phase 4 formal market seed for TW/PH.
-- Purpose:
--   1. Replace runtime fallback defaults with DB-backed market config rows.
--   2. Seed default shipping/content policies for shopee_tw and shopee_ph.
-- Notes:
--   - Idempotent and safe to re-run.
--   - Shipping fee rates that do not have dedicated columns are stored in metadata.

BEGIN;

INSERT INTO public.shipping_profiles (
    shipping_profile_code,
    profile_name,
    market_code,
    site_code,
    channel_name,
    currency,
    chargeable_weight_mode,
    weight_rounding_mode,
    weight_rounding_base_g,
    volumetric_divisor,
    first_weight_g,
    first_weight_fee,
    continue_weight_g,
    continue_weight_fee,
    shipping_subsidy_rule_type,
    subsidy_rules_json,
    is_default,
    is_active,
    metadata,
    updated_at
) VALUES
    (
        'sp_shopee_tw_default',
        'Shopee TW Default SLS',
        'shopee_tw',
        'shopee_tw',
        'SLS',
        'TWD',
        'max_actual_or_volumetric',
        'ceil',
        10,
        6000,
        500,
        70,
        500,
        30,
        'buyer_shipping_by_order_type',
        '{"ordinary_buyer_shipping": 55, "discount_buyer_shipping": 30, "free_buyer_shipping": 0}'::jsonb,
        TRUE,
        TRUE,
        '{"commission_rate": 0.14, "transaction_fee_rate": 0.025, "pre_sale_service_rate": 0.03, "agent_fee_cny": 3.0, "commission_free_days": 90}'::jsonb,
        CURRENT_TIMESTAMP
    ),
    (
        'sp_shopee_ph_default',
        'Shopee PH Default SLS',
        'shopee_ph',
        'shopee_ph',
        'SLS',
        'PHP',
        'max_actual_or_volumetric',
        'ceil',
        10,
        6000,
        500,
        120,
        500,
        45,
        'buyer_shipping_by_order_type',
        '{"ordinary_buyer_shipping": 65, "discount_buyer_shipping": 35, "free_buyer_shipping": 0}'::jsonb,
        TRUE,
        TRUE,
        '{"commission_rate": 0.14, "transaction_fee_rate": 0.025, "pre_sale_service_rate": 0.03, "agent_fee_cny": 3.0, "commission_free_days": 90}'::jsonb,
        CURRENT_TIMESTAMP
    )
ON CONFLICT (shipping_profile_code) DO UPDATE SET
    profile_name = EXCLUDED.profile_name,
    market_code = EXCLUDED.market_code,
    site_code = EXCLUDED.site_code,
    channel_name = EXCLUDED.channel_name,
    currency = EXCLUDED.currency,
    chargeable_weight_mode = EXCLUDED.chargeable_weight_mode,
    weight_rounding_mode = EXCLUDED.weight_rounding_mode,
    weight_rounding_base_g = EXCLUDED.weight_rounding_base_g,
    volumetric_divisor = EXCLUDED.volumetric_divisor,
    first_weight_g = EXCLUDED.first_weight_g,
    first_weight_fee = EXCLUDED.first_weight_fee,
    continue_weight_g = EXCLUDED.continue_weight_g,
    continue_weight_fee = EXCLUDED.continue_weight_fee,
    shipping_subsidy_rule_type = EXCLUDED.shipping_subsidy_rule_type,
    subsidy_rules_json = EXCLUDED.subsidy_rules_json,
    is_default = EXCLUDED.is_default,
    is_active = EXCLUDED.is_active,
    metadata = EXCLUDED.metadata,
    updated_at = CURRENT_TIMESTAMP;

UPDATE public.shipping_profiles
SET is_default = FALSE,
    updated_at = CURRENT_TIMESTAMP
WHERE site_code = 'shopee_tw' AND shipping_profile_code <> 'sp_shopee_tw_default';

UPDATE public.shipping_profiles
SET is_default = FALSE,
    updated_at = CURRENT_TIMESTAMP
WHERE site_code = 'shopee_ph' AND shipping_profile_code <> 'sp_shopee_ph_default';

INSERT INTO public.content_policies (
    content_policy_code,
    policy_name,
    market_code,
    site_code,
    source_language,
    listing_language,
    translation_mode,
    title_min_length,
    title_max_length,
    description_min_length,
    description_max_length,
    forbidden_terms_json,
    required_sections_json,
    validation_rule_set,
    fallback_to_source_title,
    fallback_to_source_description,
    is_default,
    is_active,
    metadata,
    updated_at
) VALUES
    (
        'cp_shopee_tw_default',
        'Shopee TW Default Content Policy',
        'shopee_tw',
        'shopee_tw',
        'zh-CN',
        'zh-Hant',
        'rewrite',
        20,
        80,
        300,
        2000,
        '["现货", "現貨"]'::jsonb,
        '["特色", "规格", "用途", "注意事项", "品牌"]'::jsonb,
        '{"require_traditional_chinese": true, "allow_publish": true}'::jsonb,
        TRUE,
        TRUE,
        TRUE,
        TRUE,
        '{}'::jsonb,
        CURRENT_TIMESTAMP
    ),
    (
        'cp_shopee_ph_default',
        'Shopee PH Default Content Policy',
        'shopee_ph',
        'shopee_ph',
        'zh-CN',
        'en',
        'rewrite',
        20,
        120,
        200,
        2500,
        '["现货", "現貨"]'::jsonb,
        '["Key Features", "Specifications", "Usage", "Notes", "Brand"]'::jsonb,
        '{"require_english_listing": true, "allow_publish": true}'::jsonb,
        TRUE,
        TRUE,
        TRUE,
        TRUE,
        '{}'::jsonb,
        CURRENT_TIMESTAMP
    )
ON CONFLICT (content_policy_code) DO UPDATE SET
    policy_name = EXCLUDED.policy_name,
    market_code = EXCLUDED.market_code,
    site_code = EXCLUDED.site_code,
    source_language = EXCLUDED.source_language,
    listing_language = EXCLUDED.listing_language,
    translation_mode = EXCLUDED.translation_mode,
    title_min_length = EXCLUDED.title_min_length,
    title_max_length = EXCLUDED.title_max_length,
    description_min_length = EXCLUDED.description_min_length,
    description_max_length = EXCLUDED.description_max_length,
    forbidden_terms_json = EXCLUDED.forbidden_terms_json,
    required_sections_json = EXCLUDED.required_sections_json,
    validation_rule_set = EXCLUDED.validation_rule_set,
    fallback_to_source_title = EXCLUDED.fallback_to_source_title,
    fallback_to_source_description = EXCLUDED.fallback_to_source_description,
    is_default = EXCLUDED.is_default,
    is_active = EXCLUDED.is_active,
    metadata = EXCLUDED.metadata,
    updated_at = CURRENT_TIMESTAMP;

UPDATE public.content_policies
SET is_default = FALSE,
    updated_at = CURRENT_TIMESTAMP
WHERE site_code = 'shopee_tw' AND content_policy_code <> 'cp_shopee_tw_default';

UPDATE public.content_policies
SET is_default = FALSE,
    updated_at = CURRENT_TIMESTAMP
WHERE site_code = 'shopee_ph' AND content_policy_code <> 'cp_shopee_ph_default';

INSERT INTO public.market_configs (
    market_code,
    config_name,
    channel_code,
    site_code,
    default_currency,
    source_language,
    listing_language,
    default_shipping_profile_code,
    default_content_policy_code,
    allow_publish,
    allow_profit_analysis,
    allow_listing_optimization,
    is_active,
    metadata,
    updated_at
) VALUES
    (
        'shopee_tw',
        'Shopee Taiwan Default',
        'shopee',
        'shopee_tw',
        'TWD',
        'zh-CN',
        'zh-Hant',
        'sp_shopee_tw_default',
        'cp_shopee_tw_default',
        TRUE,
        TRUE,
        TRUE,
        TRUE,
        '{}'::jsonb,
        CURRENT_TIMESTAMP
    ),
    (
        'shopee_ph',
        'Shopee Philippines Default',
        'shopee',
        'shopee_ph',
        'PHP',
        'zh-CN',
        'en',
        'sp_shopee_ph_default',
        'cp_shopee_ph_default',
        TRUE,
        TRUE,
        TRUE,
        TRUE,
        '{}'::jsonb,
        CURRENT_TIMESTAMP
    )
ON CONFLICT (market_code) DO UPDATE SET
    config_name = EXCLUDED.config_name,
    channel_code = EXCLUDED.channel_code,
    site_code = EXCLUDED.site_code,
    default_currency = EXCLUDED.default_currency,
    source_language = EXCLUDED.source_language,
    listing_language = EXCLUDED.listing_language,
    default_shipping_profile_code = EXCLUDED.default_shipping_profile_code,
    default_content_policy_code = EXCLUDED.default_content_policy_code,
    allow_publish = EXCLUDED.allow_publish,
    allow_profit_analysis = EXCLUDED.allow_profit_analysis,
    allow_listing_optimization = EXCLUDED.allow_listing_optimization,
    is_active = EXCLUDED.is_active,
    metadata = EXCLUDED.metadata,
    updated_at = CURRENT_TIMESTAMP;

COMMIT;