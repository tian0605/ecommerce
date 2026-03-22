# products 表结构

```sql
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    alibaba_product_id VARCHAR(50) UNIQUE,
    main_product_no VARCHAR(20) UNIQUE,
    title TEXT,
    category VARCHAR(255),
    brand VARCHAR(100),
    sku_count INTEGER,
    main_image_count INTEGER,
    main_images JSONB,
    description TEXT,
    weight_g DECIMAL(10, 2),
    length_cm DECIMAL(10, 2),
    width_cm DECIMAL(10, 2),
    height_cm DECIMAL(10, 2),
    status VARCHAR(20) DEFAULT 'pending',
    optimized_title TEXT,
    optimized_description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_products_alibaba_id ON products(alibaba_product_id);
CREATE INDEX idx_products_status ON products(status);
```

## 状态流转

```
pending → optimized → published
```

| 状态 | 说明 | 触发模块 |
|------|------|----------|
| pending | 刚落库 | product-storer |
| optimized | 已优化 | listing-optimizer |
| published | 已回写 | miaoshou-updater |
