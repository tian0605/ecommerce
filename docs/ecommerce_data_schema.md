-- ecommerce_data 数据库表结构导出
-- 导出时间: 2026-04-05
-- PostgreSQL 版本: 16.13

-- ============================================================
-- 表清单 (27张表)
-- ============================================================

-- 1. agent_attribution_rules  - Agent归因规则
-- 2. agents                    - Agent信息
-- 3. analysis_job_logs          - 分析任务日志
-- 4. bulk_pricing_tasks        - 批量定价任务
-- 5. dashboard_metrics         - 仪表盘指标
-- 6. exchange_rates            - 汇率
-- 7. exchange_rates_history    - 汇率历史
-- 8. fee_config_history        - 费用配置历史
-- 9. heartbeat_events          - 心跳事件
-- 10. hot_search_words         - 热搜词
-- 11. industry_data             - 行业数据
-- 12. logistics_templates      - 物流模板
-- 13. main_logs                - 主日志
-- 14. memory                    - 记忆
-- 15. platform_rules           - 平台规则
-- 16. pricing_history          - 定价历史
-- 17. product_alerts           - 商品预警
-- 18. product_analysis         - 商品分析
-- 19. product_listing_info     - 商品上架信息
-- 20. product_mapping          - 商品映射
-- 21. product_skus             - SKU表
-- 22. products                 - 商品主表 ⭐
-- 23. profit_analysis_summary  - 利润分析汇总
-- 24. shopee_rank_import       - Shopee排名导入
-- 25. sources                  - 数据源
-- 26. tasks                    - 任务表 ⭐
-- 27. workflow_data            - 工作流数据

-- ============================================================
-- 核心表结构
-- ============================================================

-- products (商品主表)
CREATE TABLE public.products (
    id integer NOT NULL,
    product_id character varying(64),
    alibaba_product_id character varying(64),  -- 1688货源ID
    title text,
    description text,
    category character varying(255),
    brand character varying(128),
    origin character varying(128),
    main_images jsonb,                        -- 主图
    sku_images jsonb,                          -- SKU图
    skus jsonb,                                -- SKU数据
    logistics jsonb,                            -- 物流数据
    source_url text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    status public.product_status DEFAULT 'collected'::public.product_status NOT NULL,
    listing_updated_at timestamp without time zone,
    published_sites jsonb DEFAULT '[]'::jsonb,
    site_status jsonb DEFAULT '{}'::jsonb,
    optimized_title text,                       -- LLM优化标题
    optimized_description text,                -- LLM优化描述
    optimization_version integer DEFAULT 1,
    supplier_info jsonb,
    key_attributes jsonb DEFAULT '[]'::jsonb,
    quality_score numeric(5,2),
    last_reviewed_at timestamp without time zone,
    purchase_cost_history jsonb DEFAULT '[]'::jsonb,
    is_deleted smallint DEFAULT 0,
    product_id_new character varying(18)        -- 生成的主货号(18位)
);

-- product_skus (SKU表)
CREATE TABLE public.product_skus (
    id integer NOT NULL,
    product_id integer,                        -- 关联products.id
    sku_name character varying(200),
    color character varying(100),
    size character varying(50),
    price numeric(10,2),
    stock integer,
    package_length numeric(10,2),              -- 包装长度(cm)
    package_width numeric(10,2),               -- 包装宽度(cm)
    package_height numeric(10,2),               -- 包装高度(cm)
    package_weight numeric(10,2),              -- 包装重量(克g)
    image_url text,
    created_at timestamp without time zone DEFAULT now(),
    volume_weight numeric(10,2),
    currency character varying(10) DEFAULT 'CNY',
    is_domestic_shipping boolean DEFAULT true,
    requires_special_packaging boolean DEFAULT false,
    shipping_type_preference character varying(20),
    is_deleted smallint DEFAULT 0,
    sku_code character varying(50),
    sku_stock integer,
    shopee_sku_name character varying(120),
    color_code character varying(2),
    attribute_code character varying(2),
    stock_updated_at timestamp without time zone,
    stock_source character varying(20),
    sku_id_new character varying(50)
);

-- tasks (任务表)
CREATE TABLE public.tasks (
    id integer NOT NULL,
    task_name character varying(100) NOT NULL,  -- 任务名(唯一)
    display_name character varying(200),
    description text,
    status character varying(20) DEFAULT 'pending',
    last_executed_at timestamp without time zone,
    last_result text,
    last_error text,
    execution_count integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    priority character varying(10) DEFAULT 'P1',
    exec_state character varying(30) DEFAULT 'new',
    fix_suggestion text,
    parent_task_id character varying(50),
    task_level integer DEFAULT 1,
    root_task_id character varying(50),
    retry_count integer DEFAULT 0,
    solution text,
    is_void boolean DEFAULT false,
    success_criteria text,
    analysis text,
    plan text,
    task_type character varying(20) DEFAULT '常规',
    expected_duration integer,                  -- 预期时长(分钟)
    progress_checkpoint jsonb,                  -- 断点数据
    notification_status text DEFAULT 'pending',
    notification_attempts integer DEFAULT 0,
    notification_success_count integer DEFAULT 0,
    notification_failure_count integer DEFAULT 0,
    notification_last_event text,
    notification_last_message text,
    notification_last_error text,
    notification_last_attempt_at timestamp without time zone,
    notification_last_sent_at timestamp without time zone,
    notification_audit jsonb DEFAULT '[]'::jsonb,
    feedback_doc_url text,
    feedback_markdown_file text,
    error_signature text,
    agent_id bigint,
    attribution_source text,
    attribution_version text
);

-- product_listing_info (商品上架信息)
CREATE TABLE public.product_listing_info (
    id integer NOT NULL,
    alibaba_product_id character varying(50) NOT NULL,
    product_id_new character varying(20) NOT NULL,
    optimized_title text,
    optimized_description text,
    package_weight_kg numeric(8,3),
    package_length numeric(6,1),
    package_width numeric(6,1),
    package_height numeric(6,1),
    category_level1 character varying(50),
    category_level2 character varying(50),
    category_level3 character varying(50),
    status character varying(20) DEFAULT 'pending',
    rpa_attempts integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

-- product_analysis (商品利润分析)
CREATE TABLE public.product_analysis (
    id integer NOT NULL,
    product_id integer,
    sku_id integer,
    platform character varying(50),
    site character varying(50),
    currency character varying(10) DEFAULT 'TWD',
    purchase_price_cny numeric(10,2),          -- 采购价(CNY)
    weight_kg numeric(10,4),                   -- 重量(kg)
    shipping_cn numeric(10,2),                 -- 国内运费
    agent_fee_cny numeric(10,2),              -- 货代费
    sls_fee_cny numeric(10,2),                -- SLS运费(CNY)
    sls_fee_twd numeric(10,2),               -- SLS运费(TWD)
    shipping_ratio numeric(5,4),
    commission_cny numeric(10,2),             -- 佣金(CNY)
    commission_twd numeric(10,2),            -- 佣金(TWD)
    service_fee_cny numeric(10,2),           -- 服务费(CNY)
    service_fee_twd numeric(10,2),           -- 服务费(TWD)
    transaction_fee_cny numeric(10,2),       -- 交易费(CNY)
    transaction_fee_twd numeric(10,2),       -- 交易费(TWD)
    total_cost_cny numeric(10,2),           -- 总成本(CNY)
    total_cost_twd numeric(10,2),           -- 总成本(TWD)
    exchange_rate numeric(10,4),
    suggested_price_twd numeric(10,2),       -- 建议售价(TWD)
    suggested_price_cny numeric(10,2),
    estimated_profit_cny numeric(10,2),      -- 预计利润(CNY)
    profit_rate numeric(10,4),               -- 利润率
    analysis_date date,
    remarks text,
    created_at timestamp without time zone DEFAULT now(),
    is_deleted smallint DEFAULT 0,
    new_store_price_twd numeric,
    new_store_price_cny numeric,
    updated_at timestamp without time zone DEFAULT now(),
    new_store_price numeric
);

-- platform_rules (平台规则/费率配置)
CREATE TABLE public.platform_rules (
    id integer NOT NULL,
    platform character varying(50),
    site character varying(50),
    commission_rate numeric(5,4),
    service_rate numeric(5,4),
    transaction_fee numeric(5,4),
    payment_fee numeric(5,4),
    logistics_cost_base numeric(10,2),
    logistics_cost_per_kg numeric(10,2),
    first_kg_cost numeric(10,2),
    continue_kg_cost numeric(10,2),
    target_profit_rate numeric(5,4),
    remarks text,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    currency character varying(10) DEFAULT 'TWD',
    agent_fee_cny numeric DEFAULT 3.00,        -- 货代费(CNY)
    first_weight_unit numeric DEFAULT 500,     -- 首重单位(g)
    first_weight_twd numeric DEFAULT 15.00,    -- 首重费用(TWD)
    continue_weight_unit numeric DEFAULT 500,  -- 续重单位(g)
    continue_weight_twd numeric DEFAULT 30.00,-- 续重费用(TWD)
    store_shipping_twd numeric DEFAULT 50.00,
    home_delivery_twd numeric DEFAULT 70.00,
    pre_sale_service_rate numeric DEFAULT 0.03,-- 预售服务费
    commission_rate_taiwan numeric DEFAULT 0.14,-- 佣金14%
    transaction_fee_rate_taiwan numeric DEFAULT 0.025, -- 交易费2.5%
    is_deleted smallint DEFAULT 0
);

-- main_logs (主日志)
CREATE TABLE public.main_logs (
    id integer NOT NULL,
    log_type character varying(50) NOT NULL,
    log_level character varying(20) DEFAULT 'INFO',
    task_name character varying(255),
    run_start_time timestamp without time zone,
    run_end_time timestamp without time zone,
    duration_ms integer,
    run_status character varying(50),
    run_message text,
    run_content text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    agent_id bigint,
    attribution_source text,
    attribution_version text
);

-- heartbeat_events (心跳事件)
CREATE TABLE public.heartbeat_events (
    id bigint NOT NULL,
    agent_id bigint,
    source text NOT NULL,
    heartbeat_status text NOT NULL,
    summary text,
    raw_report text,
    payload jsonb DEFAULT '{}'::jsonb,
    pending_count integer DEFAULT 0,
    processing_count integer DEFAULT 0,
    requires_manual_count integer DEFAULT 0,
    overtime_temp_count integer DEFAULT 0,
    failed_recent_count integer DEFAULT 0,
    duration_ms integer DEFAULT 0,
    host_name text,
    report_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

-- agents (Agent信息)
CREATE TABLE public.agents (
    id bigint NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    type text NOT NULL,
    owner text,
    status text DEFAULT 'active',
    description text,
    source_system text DEFAULT 'openclaw',
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 枚举类型
-- ============================================================

CREATE TYPE public.product_status AS ENUM (
    'collected',   -- 已采集
    'listed',      -- 已上架
    'published',   -- 已发布
    'delisted',    -- 已下架
    'pending',     -- 待处理
    'optimized'    -- 已优化
);

-- ============================================================
-- 函数
-- ============================================================

-- generate_product_id: 生成主货号(18位)
CREATE FUNCTION public.generate_product_id(
    p_channel_code character varying,
    p_supplier_code character varying,
    p_series_code character varying,
    p_year character varying,
    OUT new_product_id character varying
) RETURNS character varying AS $$
DECLARE
    v_seq INT;
    v_seq_str VARCHAR(7);
BEGIN
    SELECT COALESCE(MAX(
        CAST(SUBSTRING(product_id_new FROM 13) AS INT)
    ), 0) + 1
    INTO v_seq
    FROM products
    WHERE product_id_new LIKE p_channel_code || p_supplier_code || p_series_code || p_year || '%';

    v_seq_str := LPAD(v_seq::TEXT, 7, '0');
    new_product_id := p_channel_code || p_supplier_code || p_series_code || p_year || v_seq_str;
END;
$$ LANGUAGE plpgsql;

-- update_listing_timestamp: 自动更新listing时间戳
CREATE FUNCTION public.update_listing_timestamp() RETURNS trigger AS $$
BEGIN
    IF TG_TABLE_NAME = 'products' THEN
        IF NEW.optimized_title != OLD.optimized_title OR 
           NEW.optimized_description != OLD.optimized_description THEN
            NEW.listing_updated_at := CURRENT_TIMESTAMP;
            NEW.optimization_version := COALESCE(OLD.optimization_version, 0) + 1;
        END IF;
    ELSIF TG_TABLE_NAME = 'product_skus' THEN
        IF NEW.stock != OLD.stock THEN
            NEW.stock_updated_at := CURRENT_TIMESTAMP;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 触发器
-- ============================================================

CREATE TRIGGER trg_products_listing_update 
    BEFORE UPDATE ON products 
    FOR EACH ROW EXECUTE FUNCTION public.update_listing_timestamp();

CREATE TRIGGER trg_product_skus_stock_update 
    BEFORE UPDATE ON product_skus 
    FOR EACH ROW 
    WHEN ((new.stock IS DISTINCT FROM old.stock))
    EXECUTE FUNCTION public.update_listing_timestamp();

-- ============================================================
-- 视图
-- ============================================================

-- v_agent_heartbeats: Agent心跳视图
CREATE VIEW public.v_agent_heartbeats AS
 SELECT h.id AS heartbeat_id,
    h.agent_id,
    a.code AS agent_code,
    a.name AS agent_name,
    h.heartbeat_status,
    h.summary,
    h.pending_count,
    h.processing_count,
    h.requires_manual_count,
    h.overtime_temp_count,
    h.failed_recent_count,
    h.duration_ms,
    h.host_name,
    h.report_time,
    h.created_at
   FROM heartbeat_events h
     LEFT JOIN agents a ON (a.id = h.agent_id);

-- v_agent_tasks: Agent任务视图
CREATE VIEW public.v_agent_tasks AS
 WITH parent_tasks AS (
         SELECT tasks.task_name, tasks.agent_id FROM tasks
     ),
     root_tasks AS (
         SELECT tasks.task_name, tasks.agent_id FROM tasks
     )
 SELECT t.task_name,
    COALESCE(t.agent_id, pt.agent_id, rt.agent_id) AS agent_id,
    a.code AS agent_code,
    a.name AS agent_name,
    t.display_name,
    t.task_type,
    t.priority,
    t.status,
    t.exec_state,
    t.task_level,
    t.parent_task_id,
    t.root_task_id,
    t.retry_count,
    t.last_error,
    t.notification_status,
    t.feedback_doc_url,
    t.feedback_markdown_file,
    t.created_at,
    t.updated_at
   FROM tasks t
     LEFT JOIN parent_tasks pt ON (pt.task_name = t.parent_task_id)
     LEFT JOIN root_tasks rt ON (rt.task_name = t.root_task_id)
     LEFT JOIN agents a ON (a.id = COALESCE(t.agent_id, pt.agent_id, rt.agent_id));

-- v_products_compat: 商品兼容视图
CREATE VIEW public.v_products_compat AS
 SELECT id,
    COALESCE(product_id_new, product_id) AS product_id,
    alibaba_product_id,
    title,
    status,
    created_at,
    updated_at,
    is_deleted
   FROM products;
