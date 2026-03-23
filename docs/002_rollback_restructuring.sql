-- =====================================================
-- 数据库重构回滚脚本
-- 执行日期: 2026-03-23
-- 描述: 回滚 products + product_skus 表结构变更
-- =====================================================

BEGIN;

-- 回滚 products 表

-- 删除新增的索引
DROP INDEX IF EXISTS idx_products_product_id_new;
DROP INDEX IF EXISTS idx_products_supplier_info;
DROP INDEX IF EXISTS idx_products_key_attributes;
DROP INDEX IF EXISTS idx_products_published_sites;

-- 删除新增字段
ALTER TABLE products DROP COLUMN IF EXISTS is_deleted;
ALTER TABLE products DROP COLUMN IF EXISTS purchase_cost_history;
ALTER TABLE products DROP COLUMN IF EXISTS last_reviewed_at;
ALTER TABLE products DROP COLUMN IF EXISTS quality_score;
ALTER TABLE products DROP COLUMN IF EXISTS key_attributes;
ALTER TABLE products DROP COLUMN IF EXISTS supplier_info;
ALTER TABLE products DROP COLUMN IF EXISTS optimization_version;
ALTER TABLE products DROP COLUMN IF EXISTS optimized_description;
ALTER TABLE products DROP COLUMN IF EXISTS optimized_title;
ALTER TABLE products DROP COLUMN IF EXISTS site_status;
ALTER TABLE products DROP COLUMN IF EXISTS published_sites;
ALTER TABLE products DROP COLUMN IF EXISTS listing_updated_at;
ALTER TABLE products DROP COLUMN IF EXISTS product_id_new;

-- 恢复旧status字段
ALTER TABLE products DROP COLUMN IF EXISTS status;
ALTER TABLE products ADD COLUMN status varchar(32) DEFAULT 'pending';

-- 回滚 product_skus 表

DROP INDEX IF EXISTS idx_product_skus_sku_id_new;
ALTER TABLE product_skus DROP COLUMN IF EXISTS sku_id_new;
ALTER TABLE product_skus DROP COLUMN IF EXISTS stock_source;
ALTER TABLE product_skus DROP COLUMN IF EXISTS stock_updated_at;

-- 恢复 package_weight 注释（如果需要）
COMMENT ON COLUMN product_skus.package_weight IS '包装重量，单位：千克(kg)';

-- 删除触发器和函数
DROP TRIGGER IF EXISTS trg_products_listing_update ON products;
DROP TRIGGER IF EXISTS trg_product_skus_stock_update ON product_skus;
DROP FUNCTION IF EXISTS update_listing_timestamp();
DROP FUNCTION IF EXISTS generate_product_id(varchar, varchar, varchar, varchar);

-- 删除视图
DROP VIEW IF EXISTS v_products_compat;

-- 删除枚举类型
DROP TYPE IF EXISTS product_status;

COMMIT;
