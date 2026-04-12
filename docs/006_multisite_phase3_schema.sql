-- Phase 3 multisite schema migration
-- Purpose: land the database foundation for market_configs, shipping_profiles,
--          content_policies and the formal site_listings model.
-- Notes:
--   1. This migration is idempotent and safe to re-run.
--   2. It can coexist with the earlier 005 draft objects.
--   3. It does not seed market data; Phase 4 will attach runtime config loading.

BEGIN;

CREATE TABLE IF NOT EXISTS public.market_configs (
    id BIGSERIAL PRIMARY KEY,
    market_code VARCHAR(64) NOT NULL,
    config_name VARCHAR(128),
    channel_code VARCHAR(32) NOT NULL DEFAULT 'shopee',
    site_code VARCHAR(64) NOT NULL,
    default_currency VARCHAR(10) NOT NULL DEFAULT 'TWD',
    source_language VARCHAR(32) NOT NULL DEFAULT 'zh-CN',
    listing_language VARCHAR(32) NOT NULL DEFAULT 'zh-Hant',
    default_shipping_profile_code VARCHAR(64),
    default_content_policy_code VARCHAR(64),
    default_fee_profile_code VARCHAR(64),
    default_erp_profile_code VARCHAR(64),
    default_category_profile_code VARCHAR(64),
    default_price_policy_code VARCHAR(64),
    allow_publish BOOLEAN NOT NULL DEFAULT TRUE,
    allow_profit_analysis BOOLEAN NOT NULL DEFAULT TRUE,
    allow_listing_optimization BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    effective_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_to TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_market_configs_market_code UNIQUE (market_code),
    CONSTRAINT uq_market_configs_channel_site UNIQUE (channel_code, site_code)
);

CREATE INDEX IF NOT EXISTS idx_market_configs_site_active
    ON public.market_configs(site_code, is_active);

CREATE TABLE IF NOT EXISTS public.shipping_profiles (
    id BIGSERIAL PRIMARY KEY,
    shipping_profile_code VARCHAR(64) NOT NULL,
    profile_name VARCHAR(128),
    market_code VARCHAR(64),
    site_code VARCHAR(64) NOT NULL,
    channel_name VARCHAR(64) NOT NULL DEFAULT 'SLS',
    currency VARCHAR(10) NOT NULL DEFAULT 'TWD',
    chargeable_weight_mode VARCHAR(64) NOT NULL DEFAULT 'max_actual_or_volumetric',
    weight_rounding_mode VARCHAR(32) NOT NULL DEFAULT 'ceil',
    weight_rounding_base_g NUMERIC(10, 2) NOT NULL DEFAULT 10,
    volumetric_divisor NUMERIC(10, 2),
    first_weight_g NUMERIC(10, 2),
    first_weight_fee NUMERIC(10, 2),
    continue_weight_g NUMERIC(10, 2),
    continue_weight_fee NUMERIC(10, 2),
    max_weight_g NUMERIC(10, 2),
    shipping_subsidy_rule_type VARCHAR(64),
    subsidy_rules_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    hidden_shipping_formula TEXT,
    hidden_shipping_continue_fee NUMERIC(10, 2),
    platform_shipping_fee_rate NUMERIC(10, 4),
    platform_shipping_fee_cap NUMERIC(10, 2),
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_shipping_profiles_code UNIQUE (shipping_profile_code)
);

CREATE INDEX IF NOT EXISTS idx_shipping_profiles_site_default
    ON public.shipping_profiles(site_code, is_default, is_active);

CREATE TABLE IF NOT EXISTS public.content_policies (
    id BIGSERIAL PRIMARY KEY,
    content_policy_code VARCHAR(64) NOT NULL,
    policy_name VARCHAR(128),
    market_code VARCHAR(64),
    site_code VARCHAR(64) NOT NULL,
    source_language VARCHAR(32) NOT NULL DEFAULT 'zh-CN',
    listing_language VARCHAR(32) NOT NULL DEFAULT 'zh-Hant',
    translation_mode VARCHAR(32) NOT NULL DEFAULT 'rewrite',
    title_min_length INTEGER,
    title_max_length INTEGER,
    description_min_length INTEGER,
    description_max_length INTEGER,
    forbidden_terms_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_sections_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    term_mapping_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_rule_set JSONB NOT NULL DEFAULT '{}'::jsonb,
    prompt_base_template TEXT,
    prompt_title_variant TEXT,
    prompt_desc_variant TEXT,
    fallback_to_source_title BOOLEAN NOT NULL DEFAULT TRUE,
    fallback_to_source_description BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_content_policies_code UNIQUE (content_policy_code)
);

CREATE INDEX IF NOT EXISTS idx_content_policies_site_default
    ON public.content_policies(site_code, is_default, is_active);

CREATE TABLE IF NOT EXISTS public.site_listings (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES public.products(id),
    sku_id INTEGER NULL REFERENCES public.product_skus(id),
    market_code VARCHAR(64) NOT NULL DEFAULT 'shopee_tw',
    site_code VARCHAR(64) NOT NULL DEFAULT 'shopee_tw',
    shop_code VARCHAR(64) NOT NULL DEFAULT 'default',
    shop_name VARCHAR(128),
    platform VARCHAR(50) NOT NULL DEFAULT 'shopee',
    alibaba_product_id VARCHAR(64),
    product_id_new VARCHAR(32),
    source_language_snapshot VARCHAR(32) NOT NULL DEFAULT 'zh-CN',
    listing_language_snapshot VARCHAR(32) NOT NULL DEFAULT 'zh-Hant',
    title_source VARCHAR(32) NOT NULL DEFAULT 'master',
    description_source VARCHAR(32) NOT NULL DEFAULT 'master',
    original_title_snapshot TEXT,
    original_description_snapshot TEXT,
    listing_title TEXT,
    listing_description TEXT,
    short_description TEXT,
    content_policy_code VARCHAR(64),
    shipping_profile_code VARCHAR(64),
    fee_profile_code VARCHAR(64),
    price_policy_code VARCHAR(64),
    erp_profile_code VARCHAR(64),
    category_profile_code VARCHAR(64),
    platform_category_id VARCHAR(64),
    platform_category_path JSONB NOT NULL DEFAULT '[]'::jsonb,
    platform_attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    currency VARCHAR(10) NOT NULL DEFAULT 'TWD',
    price_amount NUMERIC(10, 2),
    promo_price_amount NUMERIC(10, 2),
    suggested_price NUMERIC(10, 2),
    exchange_rate_used NUMERIC(12, 6),
    chargeable_weight_g NUMERIC(10, 2),
    estimated_profit_cny NUMERIC(10, 2),
    estimated_profit_local NUMERIC(10, 2),
    profit_rate NUMERIC(10, 4),
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    publish_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    sync_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    published_listing_id VARCHAR(128),
    published_url TEXT,
    error_code VARCHAR(64),
    error_message TEXT,
    sync_error TEXT,
    last_synced_at TIMESTAMP,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted SMALLINT NOT NULL DEFAULT 0
);

ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS market_code VARCHAR(64) DEFAULT 'shopee_tw';
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS site_code VARCHAR(64) DEFAULT 'shopee_tw';
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS alibaba_product_id VARCHAR(64);
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS product_id_new VARCHAR(32);
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS source_language_snapshot VARCHAR(32) DEFAULT 'zh-CN';
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS listing_language_snapshot VARCHAR(32) DEFAULT 'zh-Hant';
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS title_source VARCHAR(32) DEFAULT 'master';
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS description_source VARCHAR(32) DEFAULT 'master';
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS original_title_snapshot TEXT;
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS original_description_snapshot TEXT;
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS content_policy_code VARCHAR(64);
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS shipping_profile_code VARCHAR(64);
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS fee_profile_code VARCHAR(64);
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS price_policy_code VARCHAR(64);
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS erp_profile_code VARCHAR(64);
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS category_profile_code VARCHAR(64);
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS suggested_price NUMERIC(10, 2);
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS exchange_rate_used NUMERIC(12, 6);
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS chargeable_weight_g NUMERIC(10, 2);
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS estimated_profit_cny NUMERIC(10, 2);
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS estimated_profit_local NUMERIC(10, 2);
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS profit_rate NUMERIC(10, 4);
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS error_code VARCHAR(64);
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE public.site_listings
    ADD COLUMN IF NOT EXISTS is_current BOOLEAN DEFAULT TRUE;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'site_listings'
          AND column_name = 'site'
    ) THEN
        EXECUTE $sql$
            UPDATE public.site_listings
            SET site_code = COALESCE(NULLIF(site_code, ''), NULLIF(site, ''), 'shopee_tw')
            WHERE site_code IS NULL OR site_code = ''
        $sql$;
    ELSE
        UPDATE public.site_listings
        SET site_code = COALESCE(NULLIF(site_code, ''), 'shopee_tw')
        WHERE site_code IS NULL OR site_code = '';
    END IF;
END $$;

UPDATE public.site_listings
SET market_code = COALESCE(NULLIF(market_code, ''), site_code, 'shopee_tw')
WHERE market_code IS NULL OR market_code = '';

UPDATE public.site_listings
SET source_language_snapshot = COALESCE(NULLIF(source_language_snapshot, ''), 'zh-CN')
WHERE source_language_snapshot IS NULL OR source_language_snapshot = '';

UPDATE public.site_listings
SET listing_language_snapshot = CASE
        WHEN site_code = 'shopee_ph' THEN 'en'
        ELSE COALESCE(NULLIF(listing_language_snapshot, ''), 'zh-Hant')
    END
WHERE listing_language_snapshot IS NULL OR listing_language_snapshot = '';

CREATE INDEX IF NOT EXISTS idx_site_listings_market_site_shop
    ON public.site_listings(market_code, site_code, shop_code);
CREATE INDEX IF NOT EXISTS idx_site_listings_status_publish
    ON public.site_listings(status, publish_status);
CREATE INDEX IF NOT EXISTS idx_site_listings_product_id
    ON public.site_listings(product_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_site_listings_scope_current
    ON public.site_listings(product_id, COALESCE(sku_id, -1), site_code, shop_code)
    WHERE is_deleted = 0 AND is_current = TRUE;

ALTER TABLE public.products
    ADD COLUMN IF NOT EXISTS source_language VARCHAR(32) DEFAULT 'zh-CN';
ALTER TABLE public.products
    ADD COLUMN IF NOT EXISTS master_content_status VARCHAR(32) DEFAULT 'draft';
ALTER TABLE public.products
    ADD COLUMN IF NOT EXISTS original_description_structured JSONB DEFAULT '{}'::jsonb;
ALTER TABLE public.products
    ADD COLUMN IF NOT EXISTS content_source_version INTEGER DEFAULT 1;
ALTER TABLE public.products
    ADD COLUMN IF NOT EXISTS default_listing_site VARCHAR(64) DEFAULT 'shopee_tw';
ALTER TABLE public.products
    ADD COLUMN IF NOT EXISTS last_content_synced_at TIMESTAMP;

UPDATE public.products
SET source_language = COALESCE(NULLIF(source_language, ''), 'zh-CN'),
    master_content_status = COALESCE(NULLIF(master_content_status, ''), 'draft'),
    content_source_version = COALESCE(content_source_version, 1),
    default_listing_site = COALESCE(NULLIF(default_listing_site, ''), 'shopee_tw')
WHERE source_language IS NULL
   OR master_content_status IS NULL
   OR content_source_version IS NULL
   OR default_listing_site IS NULL;

CREATE INDEX IF NOT EXISTS idx_products_default_listing_site
    ON public.products(default_listing_site, source_language);

ALTER TABLE public.product_analysis
    ADD COLUMN IF NOT EXISTS site_listing_id BIGINT;
ALTER TABLE public.product_analysis
    ADD COLUMN IF NOT EXISTS fee_profile_code VARCHAR(64);
ALTER TABLE public.product_analysis
    ADD COLUMN IF NOT EXISTS shipping_profile_code VARCHAR(64);
ALTER TABLE public.product_analysis
    ADD COLUMN IF NOT EXISTS price_policy_code VARCHAR(64);
ALTER TABLE public.product_analysis
    ADD COLUMN IF NOT EXISTS chargeable_weight_g NUMERIC(10, 2);
ALTER TABLE public.product_analysis
    ADD COLUMN IF NOT EXISTS hidden_shipping_cost_local NUMERIC(10, 2);
ALTER TABLE public.product_analysis
    ADD COLUMN IF NOT EXISTS platform_shipping_fee_local NUMERIC(10, 2);
ALTER TABLE public.product_analysis
    ADD COLUMN IF NOT EXISTS estimated_profit_local NUMERIC(10, 2);

CREATE INDEX IF NOT EXISTS idx_product_analysis_site_listing_id
    ON public.product_analysis(site_listing_id);
CREATE INDEX IF NOT EXISTS idx_product_analysis_shipping_profile_code
    ON public.product_analysis(shipping_profile_code);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_product_analysis_site_listing'
    ) THEN
        ALTER TABLE public.product_analysis
            ADD CONSTRAINT fk_product_analysis_site_listing
            FOREIGN KEY (site_listing_id) REFERENCES public.site_listings(id);
    END IF;
END $$;

COMMIT;