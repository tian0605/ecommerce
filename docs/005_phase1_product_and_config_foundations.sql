-- Phase 1 foundation schema draft
-- Purpose: support product management read/write expansion and configuration center governance.
-- Status: draft for review before migration execution.

BEGIN;

CREATE TABLE IF NOT EXISTS public.site_listings (
    id BIGSERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES public.products(id),
    sku_id INTEGER NULL REFERENCES public.product_skus(id),
    site VARCHAR(20) NOT NULL,
    shop_code VARCHAR(64) NOT NULL,
    shop_name VARCHAR(128),
    platform VARCHAR(50) DEFAULT 'shopee',
    listing_title TEXT,
    listing_description TEXT,
    short_description TEXT,
    currency VARCHAR(10) DEFAULT 'TWD',
    price_amount NUMERIC(10, 2),
    promo_price_amount NUMERIC(10, 2),
    status VARCHAR(30) DEFAULT 'draft',
    publish_status VARCHAR(30) DEFAULT 'pending',
    platform_category_id VARCHAR(64),
    platform_category_path JSONB DEFAULT '[]'::jsonb,
    platform_attributes_json JSONB DEFAULT '{}'::jsonb,
    published_listing_id VARCHAR(128),
    published_url TEXT,
    sync_status VARCHAR(30) DEFAULT 'pending',
    sync_error TEXT,
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted SMALLINT DEFAULT 0,
    CONSTRAINT site_listings_unique_scope UNIQUE (product_id, sku_id, site, shop_code)
);

CREATE INDEX IF NOT EXISTS idx_site_listings_site_shop ON public.site_listings(site, shop_code);
CREATE INDEX IF NOT EXISTS idx_site_listings_status ON public.site_listings(status, publish_status);
CREATE INDEX IF NOT EXISTS idx_site_listings_product_id ON public.site_listings(product_id);

CREATE TABLE IF NOT EXISTS public.media_assets (
    id BIGSERIAL PRIMARY KEY,
    owner_type VARCHAR(32) NOT NULL,
    owner_id BIGINT NOT NULL,
    site_scope VARCHAR(20),
    shop_code VARCHAR(64),
    media_type VARCHAR(20) NOT NULL,
    usage_type VARCHAR(30) NOT NULL,
    source_url TEXT,
    oss_key TEXT,
    oss_url TEXT,
    file_name VARCHAR(255),
    mime_type VARCHAR(128),
    file_size_bytes BIGINT,
    width_px INTEGER,
    height_px INTEGER,
    duration_seconds NUMERIC(10, 2),
    sort_order INTEGER DEFAULT 0,
    status VARCHAR(30) DEFAULT 'active',
    checksum VARCHAR(128),
    uploaded_by VARCHAR(128),
    uploaded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted SMALLINT DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_media_assets_owner ON public.media_assets(owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_media_assets_scope ON public.media_assets(site_scope, usage_type);
CREATE INDEX IF NOT EXISTS idx_media_assets_sort ON public.media_assets(status, sort_order);

CREATE TABLE IF NOT EXISTS public.system_configs (
    id BIGSERIAL PRIMARY KEY,
    config_key VARCHAR(128) NOT NULL,
    config_name VARCHAR(128) NOT NULL,
    category VARCHAR(64) NOT NULL,
    environment VARCHAR(32) NOT NULL DEFAULT 'prod',
    value_type VARCHAR(32) NOT NULL,
    secret_level VARCHAR(32) NOT NULL DEFAULT 'masked',
    value_encrypted TEXT,
    value_masked TEXT,
    file_ref_id BIGINT,
    description TEXT,
    schema_json JSONB DEFAULT '{}'::jsonb,
    dependency_json JSONB DEFAULT '{}'::jsonb,
    is_required BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    rotation_days INTEGER,
    expires_at TIMESTAMP,
    last_verified_at TIMESTAMP,
    last_verify_status VARCHAR(32) DEFAULT 'unknown',
    last_verify_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(128),
    CONSTRAINT system_configs_unique_key UNIQUE (config_key, environment)
);

CREATE INDEX IF NOT EXISTS idx_system_configs_category ON public.system_configs(category, environment);
CREATE INDEX IF NOT EXISTS idx_system_configs_verify_status ON public.system_configs(last_verify_status, is_active);

CREATE TABLE IF NOT EXISTS public.config_change_logs (
    id BIGSERIAL PRIMARY KEY,
    config_id BIGINT NOT NULL REFERENCES public.system_configs(id),
    action_type VARCHAR(32) NOT NULL,
    old_value_masked TEXT,
    new_value_masked TEXT,
    change_reason TEXT,
    verify_status VARCHAR(32),
    verify_message TEXT,
    operator_id VARCHAR(64),
    operator_name VARCHAR(128),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_config_change_logs_config_id ON public.config_change_logs(config_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.uploaded_secret_files (
    id BIGSERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    storage_path TEXT NOT NULL,
    oss_key TEXT,
    checksum VARCHAR(128),
    mime_type VARCHAR(128),
    file_size_bytes BIGINT,
    file_purpose VARCHAR(32) NOT NULL,
    uploaded_by VARCHAR(128),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted SMALLINT DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_uploaded_secret_files_purpose ON public.uploaded_secret_files(file_purpose, created_at DESC);

COMMIT;