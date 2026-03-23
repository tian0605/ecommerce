-- =====================================================
-- ecommerce_data 数据库重构方案
-- 执行日期: 2026-03-23
-- 描述: products表 + product_skus表 结构优化
-- =====================================================

BEGIN;

-- =====================================================
-- 第一部分: products 表重构
-- =====================================================

-- 1. 新增 status 枚举类型和字段（保持兼容性，保留旧字段）
DO $$ BEGIN
    CREATE TYPE product_status AS ENUM ('collected', 'listed', 'published', 'delisted');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 添加新状态字段
ALTER TABLE products ADD COLUMN IF NOT EXISTS status_new product_status;

-- 迁移数据: pending -> collected, published保持不变
UPDATE products SET status_new = 
    CASE 
        WHEN status = 'pending' THEN 'collected'::product_status
        WHEN status = 'published' THEN 'published'::product_status
        ELSE NULL
    END;

-- 删除旧status列并重命名新列
ALTER TABLE products DROP COLUMN IF EXISTS status;
ALTER TABLE products RENAME COLUMN status_new TO status;

-- 设置默认值
ALTER TABLE products ALTER COLUMN status SET DEFAULT 'collected'::product_status;
ALTER TABLE products ALTER COLUMN status SET NOT NULL;

-- 2. 新增 listing_updated_at（记录最近一次listing优化时间）
ALTER TABLE products ADD COLUMN IF NOT EXISTS listing_updated_at timestamp;

-- 3. 新增 published_sites（jsonb，存储已发布站点列表）
ALTER TABLE products ADD COLUMN IF NOT EXISTS published_sites jsonb DEFAULT '[]'::jsonb;

-- 4. 新增 site_status（jsonb，记录各站点独立状态）
ALTER TABLE products ADD COLUMN IF NOT EXISTS site_status jsonb DEFAULT '{}'::jsonb;

-- 5. 新增 optimized_title（优化后的标题）
ALTER TABLE products ADD COLUMN IF NOT EXISTS optimized_title text;

-- 6. 新增 optimized_description（优化后的描述）
ALTER TABLE products ADD COLUMN IF NOT EXISTS optimized_description text;

-- 7. 新增 optimization_version（迭代版本号）
ALTER TABLE products ADD COLUMN IF NOT EXISTS optimization_version int DEFAULT 1;

-- 8. 新增 supplier_info（jsonb，供应商信息）
ALTER TABLE products ADD COLUMN IF NOT EXISTS supplier_info jsonb;

-- 9. 新增 key_attributes（jsonb，商品关键属性）
ALTER TABLE products ADD COLUMN IF NOT EXISTS key_attributes jsonb DEFAULT '[]'::jsonb;

-- 10. 新增 quality_score（质量评分 0-100）
ALTER TABLE products ADD COLUMN IF NOT EXISTS quality_score numeric(5,2);

-- 11. 新增 last_reviewed_at（最近人工审核时间）
ALTER TABLE products ADD COLUMN IF NOT EXISTS last_reviewed_at timestamp;

-- 12. 新增 purchase_cost_history（jsonb，采购成本历史）
ALTER TABLE products ADD COLUMN IF NOT EXISTS purchase_cost_history jsonb DEFAULT '[]'::jsonb;

-- 13. 新增 is_deleted（软删除标记，与其他表保持一致）
ALTER TABLE products ADD COLUMN IF NOT EXISTS is_deleted smallint DEFAULT 0;

-- 14. 新增 product_id_new（18位新货号）
ALTER TABLE products ADD COLUMN IF NOT EXISTS product_id_new varchar(18);

-- 为新货号创建索引
CREATE INDEX IF NOT EXISTS idx_products_product_id_new ON products(product_id_new);
CREATE INDEX IF NOT EXISTS idx_products_supplier_info ON products USING GIN (supplier_info);
CREATE INDEX IF NOT EXISTS idx_products_key_attributes ON products USING GIN (key_attributes);
CREATE INDEX IF NOT EXISTS idx_products_published_sites ON products USING GIN (published_sites);

-- =====================================================
-- 第二部分: product_skus 表重构
-- =====================================================

-- 1. package_weight 单位从kg改为g（字段类型不变，注释说明）
COMMENT ON COLUMN product_skus.package_weight IS '包装重量，单位：克(g)，从kg改为g';

-- 2. 新增 stock_updated_at（库存更新时间）
ALTER TABLE product_skus ADD COLUMN IF NOT EXISTS stock_updated_at timestamp;

-- 3. 新增 stock_source（库存来源：manual/system/api）
ALTER TABLE product_skus ADD COLUMN IF NOT EXISTS stock_source varchar(20);

-- 4. 新增 sku_id_new（规范化SKU编码）
ALTER TABLE product_skus ADD COLUMN IF NOT EXISTS sku_id_new varchar(50);

CREATE INDEX IF NOT EXISTS idx_product_skus_sku_id_new ON product_skus(sku_id_new);

-- =====================================================
-- 第三部分: 创建新货号生成函数
-- =====================================================

CREATE OR REPLACE FUNCTION generate_product_id(
    p_channel_code VARCHAR(2),      -- 渠道码: AL/TM/JD
    p_supplier_code VARCHAR(4),     -- 供应商码: 4位
    p_series_code VARCHAR(3),      -- 系列码: 3位
    p_year VARCHAR(2),             -- 年份: 2位
    OUT new_product_id VARCHAR(18)
)
RETURNS VARCHAR(18) AS $$
DECLARE
    v_seq INT;
    v_seq_str VARCHAR(7);
BEGIN
    -- 获取当前序列值（这里需要创建一个序列）
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

-- =====================================================
-- 第四部分: 创建状态更新触发器
-- =====================================================

CREATE OR REPLACE FUNCTION update_listing_timestamp()
RETURNS TRIGGER AS $$
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

DROP TRIGGER IF EXISTS trg_products_listing_update ON products;
CREATE TRIGGER trg_products_listing_update
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_listing_timestamp();

DROP TRIGGER IF EXISTS trg_product_skus_stock_update ON product_skus;
CREATE TRIGGER trg_product_skus_stock_update
    BEFORE UPDATE ON product_skus
    FOR EACH ROW
    WHEN (NEW.stock IS DISTINCT FROM OLD.stock)
    EXECUTE FUNCTION update_listing_timestamp();

-- =====================================================
-- 第五部分: 创建视图（兼容旧代码）
-- =====================================================

-- 创建products视图，兼容旧货号字段
CREATE OR REPLACE VIEW v_products_compat AS
SELECT 
    id,
    COALESCE(product_id_new, product_id) AS product_id,
    alibaba_product_id,
    title,
    status,
    created_at,
    updated_at,
    is_deleted
FROM products;

COMMIT;

-- =====================================================
-- 验证脚本
-- =====================================================

-- SELECT 
--     column_name, 
--     data_type, 
--     is_nullable, 
--     column_default
-- FROM information_schema.columns 
-- WHERE table_name = 'products'
-- ORDER BY ordinal_position;

-- SELECT 
--     column_name, 
--     data_type, 
--     is_nullable, 
--     column_default
-- FROM information_schema.columns 
-- WHERE table_name = 'product_skus'
-- ORDER BY ordinal_position;
