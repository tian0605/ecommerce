BEGIN;

CREATE TABLE IF NOT EXISTS public.prompt_profiles (
    id BIGSERIAL PRIMARY KEY,
    prompt_profile_code VARCHAR(64) NOT NULL,
    profile_name VARCHAR(128),
    market_code VARCHAR(64),
    site_code VARCHAR(64) NOT NULL,
    title_template TEXT,
    description_template TEXT,
    sku_name_template TEXT,
    template_variables_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_prompt_profiles_code UNIQUE (prompt_profile_code)
);

CREATE INDEX IF NOT EXISTS idx_prompt_profiles_site_default
    ON public.prompt_profiles(site_code, is_default, is_active);

CREATE TABLE IF NOT EXISTS public.fee_profiles (
    id BIGSERIAL PRIMARY KEY,
    fee_profile_code VARCHAR(64) NOT NULL,
    profile_name VARCHAR(128),
    market_code VARCHAR(64),
    site_code VARCHAR(64) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'TWD',
    commission_rate NUMERIC(10, 4),
    transaction_fee_rate NUMERIC(10, 4),
    pre_sale_service_rate NUMERIC(10, 4),
    tax_rate NUMERIC(10, 4),
    agent_fee_cny NUMERIC(10, 2),
    commission_free_days INTEGER,
    buyer_shipping_ordinary NUMERIC(10, 2),
    buyer_shipping_discount NUMERIC(10, 2),
    buyer_shipping_free NUMERIC(10, 2),
    hidden_price_mode VARCHAR(64),
    hidden_price_value NUMERIC(10, 4),
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_fee_profiles_code UNIQUE (fee_profile_code)
);

CREATE INDEX IF NOT EXISTS idx_fee_profiles_site_default
    ON public.fee_profiles(site_code, is_default, is_active);

ALTER TABLE public.content_policies
    ADD COLUMN IF NOT EXISTS prompt_profile_code VARCHAR(64);

UPDATE public.content_policies
SET prompt_profile_code = CONCAT('prompt_', content_policy_code)
WHERE COALESCE(prompt_profile_code, '') = '';

INSERT INTO public.prompt_profiles (
    prompt_profile_code,
    profile_name,
    market_code,
    site_code,
    title_template,
    description_template,
    is_default,
    is_active,
    metadata
)
SELECT
    CONCAT('prompt_', cp.content_policy_code),
    COALESCE(cp.policy_name, cp.content_policy_code),
    cp.market_code,
    cp.site_code,
    COALESCE(NULLIF(cp.prompt_title_variant, ''), NULLIF(cp.prompt_base_template, '')),
    COALESCE(NULLIF(cp.prompt_desc_variant, ''), NULLIF(cp.prompt_base_template, '')),
    cp.is_default,
    cp.is_active,
    jsonb_build_object('seeded_from_content_policy_code', cp.content_policy_code)
FROM public.content_policies cp
WHERE NOT EXISTS (
    SELECT 1 FROM public.prompt_profiles pp WHERE pp.prompt_profile_code = CONCAT('prompt_', cp.content_policy_code)
);

INSERT INTO public.fee_profiles (
    fee_profile_code,
    profile_name,
    market_code,
    site_code,
    currency,
    commission_rate,
    transaction_fee_rate,
    pre_sale_service_rate,
    agent_fee_cny,
    commission_free_days,
    buyer_shipping_ordinary,
    buyer_shipping_discount,
    buyer_shipping_free,
    is_default,
    is_active,
    metadata
)
SELECT
    CONCAT('fee_', mc.market_code),
    COALESCE(mc.config_name, mc.market_code),
    mc.market_code,
    mc.site_code,
    mc.default_currency,
    NULLIF(sp.metadata ->> 'commission_rate', '')::numeric,
    NULLIF(sp.metadata ->> 'transaction_fee_rate', '')::numeric,
    NULLIF(sp.metadata ->> 'pre_sale_service_rate', '')::numeric,
    NULLIF(sp.metadata ->> 'agent_fee_cny', '')::numeric,
    NULLIF(sp.metadata ->> 'commission_free_days', '')::integer,
    NULLIF(sp.subsidy_rules_json ->> 'ordinary_buyer_shipping', '')::numeric,
    NULLIF(sp.subsidy_rules_json ->> 'discount_buyer_shipping', '')::numeric,
    NULLIF(sp.subsidy_rules_json ->> 'free_buyer_shipping', '')::numeric,
    TRUE,
    mc.is_active,
    jsonb_build_object('seeded_from_market_code', mc.market_code, 'seeded_from_shipping_profile_code', sp.shipping_profile_code)
FROM public.market_configs mc
LEFT JOIN public.shipping_profiles sp ON sp.shipping_profile_code = mc.default_shipping_profile_code
WHERE NOT EXISTS (
    SELECT 1 FROM public.fee_profiles fp WHERE fp.fee_profile_code = CONCAT('fee_', mc.market_code)
);

COMMIT;