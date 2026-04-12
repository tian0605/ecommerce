#!/usr/bin/env python3
"""
product-storer: 将商品数据落库到 PostgreSQL

流程：
1. 从 collector-scraper 获取商品数据（或直接接收数据）
2. 生成主货号（18位新格式）
3. 落库到 ecommerce_data.products 表和 product_skus 表
4. 返回落库结果

新主货号格式（18位）：
- 渠道码(2位): AL(1688), TM(天猫), JD(京东)
- 供应商码(4位): 供应商唯一标识（可配置或从数据推导）
- 系列码(3位): 产品系列分类
- 年份(2位): 如26代表2026年
- 流水号(7位): 递增序列

示例：AL000100100260000001 (AL渠道+0001供应商+001系列+26年+0000001序号)
"""
import argparse
import json
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

sys.path.insert(0, str(Path(__file__).parent.parent / 'shared'))
import db
from logger import setup_logger

logger = setup_logger('product-storer')

TMP_DIR = Path('/home/ubuntu/work/tmp/product_storer_test')
TMP_DIR.mkdir(parents=True, exist_ok=True)

# ============== 配置 ==============
# 渠道码映射
CHANNEL_CODE_MAP = {
    '1688': 'AL',
    'alibaba': 'AL',
    'tmall': 'TM',
    '天猫': 'TM',
    'jd': 'JD',
    '京东': 'JD',
}

# 类目映射
CATEGORY_MAP = {
    '衣架与衣夹': '101253',
    '收纳盒、收纳包与篮子': '101254',
    '收纳盒、收纳包与篮子 (Storage Boxes, Bags & Baskets)': '101254',
    '鞋盒': '101255',
    '挂钩': '101256',
    '洗衣袋与洗衣篮': '101257',
    '桌上收纳': '101258',
    '衣橱收纳': '101259',
    '首饰收纳': '101260',
    '纸巾盒': '101261',
    '其他': '101262',
    '架子与置物架': '101254',  # 默认归入收纳盒类别
    '架子与置物架 (Shelves & Racks)': '101254',
}

# 默认供应商码和系列码（可在实例化时覆盖）
DEFAULT_SUPPLIER_CODE = '0001'  # 默认供应商
DEFAULT_SERIES_CODE = '001'     # 默认系列


class ProductStorer:
    """商品数据落库器"""
    
    def __init__(self, supplier_code: str = None, series_code: str = None):
        """
        初始化落库器
        
        Args:
            supplier_code: 供应商码(4位)，如'0001'
            series_code: 系列码(3位)，如'001'
        """
        self.supplier_code = supplier_code or DEFAULT_SUPPLIER_CODE
        self.series_code = series_code or DEFAULT_SERIES_CODE
    
    def _get_channel_code(self, source_url: str = None, alibaba_id: str = None) -> str:
        """
        根据来源URL或商品ID判断渠道码
        
        Args:
            source_url: 来源URL
            alibaba_id: 阿里巴巴商品ID
            
        Returns:
            渠道码 (2位)
        """
        if source_url:
            url_lower = source_url.lower()
            if '1688' in url_lower or 'alibaba' in url_lower:
                return 'AL'
            elif 'tmall' in url_lower:
                return 'TM'
            elif 'jd' in url_lower:
                return 'JD'
        # 默认从alibaba_id判断
        if alibaba_id and str(alibaba_id).startswith('1'):
            return 'AL'
        return 'AL'  # 默认1688渠道
    
    def _get_category_code(self, category: str = None) -> str:
        """
        根据类目名称获取类目编码
        
        Args:
            category: 类目名称
            
        Returns:
            类目编码 (6位数字字符串)
        """
        if not category:
            return '101262'  # 默认"其他"
        
        # 精确匹配
        if category in CATEGORY_MAP:
            return CATEGORY_MAP[category]
        
        # 模糊匹配
        for key, code in CATEGORY_MAP.items():
            if key in category or category in key:
                return code
        
        return '101262'  # 默认"其他"
    
    def _generate_product_id_new(self, channel_code: str = 'AL') -> str:
        """
        生成新格式主货号（18位）
        
        格式：[渠道码][供应商码][系列码][年份][流水号]
        
        Args:
            channel_code: 渠道码 (2位)
            
        Returns:
            18位主货号
        """
        year = datetime.now().strftime('%y')  # 2位年份
        
        try:
            with db.get_cursor() as cur:
                pattern = f'{channel_code}{self.supplier_code}{self.series_code}{year}%'
                cur.execute("""
                    SELECT COALESCE(MAX(CAST(RIGHT(product_id_new, 7) AS INTEGER)), 0)
                    FROM products 
                    WHERE product_id_new LIKE %s
                """, (pattern,))
                result = cur.fetchone()
                seq = (int(result[0]) if result and result[0] is not None else 0) + 1
                    
        except Exception as e:
            logger.warning(f"获取序号失败，使用默认值: {e}")
            seq = 1

        while True:
            product_id_new = f"{channel_code}{self.supplier_code}{self.series_code}{year}{seq:07d}"
            try:
                with db.get_cursor() as cur:
                    cur.execute("SELECT 1 FROM products WHERE product_id_new = %s LIMIT 1", (product_id_new,))
                    if not cur.fetchone():
                        return product_id_new
            except Exception as e:
                logger.warning(f"校验主货号唯一性失败，回退当前值: {e}")
                return product_id_new
            seq += 1
    
    def _generate_sku_id_new(self, product_id_new: str, sku_index: int) -> str:
        """
        生成SKU编码
        
        Args:
            product_id_new: 18位主货号
            sku_index: SKU索引 (从0开始)
            
        Returns:
            SKU编码字符串
        """
        return f"{product_id_new}-S{sku_index+1:03d}"
    
    def _serialize_json(self, data: Any) -> Optional[str]:
        """序列化数据为JSON字符串"""
        if data is None:
            return None
        if isinstance(data, (dict, list)):
            return json.dumps(data, ensure_ascii=False)
        return str(data)

    def _merge_logistics_payload(self, product_data: Dict[str, Any], weight_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """合并抓取物流信息与本地服务补充信息。"""
        logistics_payload = product_data.get('logistics') or {}
        if isinstance(logistics_payload, str):
            try:
                logistics_payload = json.loads(logistics_payload)
            except json.JSONDecodeError:
                logistics_payload = {'raw_logistics': logistics_payload}
        elif not isinstance(logistics_payload, dict):
            logistics_payload = {}

        freight_info = (weight_data or {}).get('freight_info')
        if freight_info:
            logistics_payload['freight_info'] = freight_info
            logistics_payload['freight_source'] = 'local-1688-weight'
            logistics_payload['freight_updated_at'] = datetime.now().isoformat()

        dimension_summary = (weight_data or {}).get('dimension_summary')
        if dimension_summary:
            logistics_payload['dimension_summary'] = dimension_summary
            logistics_payload['dimension_source_chain'] = ['local_service', 'description', 'sku_image']
            logistics_payload['dimension_updated_at'] = datetime.now().isoformat()

        return logistics_payload

    def _normalize_image_urls(self, values: Any) -> List[str]:
        urls: List[str] = []
        for value in values or []:
            if isinstance(value, str) and value.startswith(('http://', 'https://')) and value not in urls:
                urls.append(value)
        return urls

    def _build_master_display_images(self, product_data: Dict[str, Any]) -> List[str]:
        main_images = self._normalize_image_urls(product_data.get('main_images', []))
        sku_images = self._normalize_image_urls(product_data.get('sku_images', []))
        detail_images = self._normalize_image_urls(product_data.get('detail_images', []))
        filtered_main_images = [url for url in main_images if url not in sku_images]
        return [*filtered_main_images, *[url for url in detail_images if url not in filtered_main_images]]

    def _update_product_image_columns(self, product_db_id: int, master_images: List[str], sku_images: List[str]) -> None:
        with db.get_cursor() as cur:
            cur.execute(
                """
                    UPDATE products
                    SET main_images = %s,
                        sku_images = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """,
                (
                    self._serialize_json(master_images),
                    self._serialize_json(sku_images),
                    product_db_id,
                ),
            )

    def _run_post_persist_steps(
        self,
        result: Dict[str, Any],
        product_db_id: int,
        product_id_new: str,
        product_data: Dict[str, Any],
        weight_data: Dict[str, Any],
        master_display_images: List[str],
        sku_image_pool: List[str],
    ) -> None:
        skus_data = product_data.get('skus', [])
        if skus_data:
            sku_result = self.store_skus(product_id_new, skus_data, weight_data)
            result['sku_ids'] = sku_result.get('sku_ids', [])
            result['sku_message'] = sku_result.get('message', '')
            logger.info(f"SKU落库结果: {result['sku_message']}")
        else:
            result['sku_ids'] = []
            result['sku_message'] = '无SKU数据，跳过'

        try:
            cos_result = self._upload_images_to_cos(product_data, product_id_new)
            result['image_upload'] = cos_result
            if cos_result.get('success'):
                persisted_master_images = list(cos_result.get('master_images') or master_display_images)
                persisted_sku_images = list(cos_result.get('sku_images') or sku_image_pool)
                self._update_product_image_columns(
                    product_db_id,
                    persisted_master_images,
                    persisted_sku_images,
                )
        except Exception as e:
            logger.warning(f"图片上传COS失败: {e}")
            result['image_upload'] = {'success': False, 'message': str(e)}
    
    def store(self, product_data: Dict[str, Any], weight_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        将商品数据落库
        
        Args:
            product_data: 商品数据字典，包含：
                - alibaba_product_id: 阿里巴巴商品ID
                - title: 标题
                - description: 描述
                - category: 类目
                - brand: 品牌
                - origin: 产地
                - main_images: 主图列表
                - sku_images: SKU图片
                - skus: SKU列表 (包含price和stock)
                - logistics: 物流信息
                - source_url: 来源URL
                - supplier_info: 供应商信息 (dict)
            weight_data: 重量数据（来自local-1688-weight），包含：
                - success: 是否成功
                - sku_count: SKU数量
                - sku_list: SKU列表 [{sku_name, weight_g, length_cm, width_cm, height_cm}]
                
        Returns:
            结果字典，包含：
                - success: 是否成功
                - product_id: 主货号 (旧格式)
                - product_id_new: 新格式主货号 (18位)
                - message: 消息
                - sku_ids: SKU ID列表
        """
        result = {
            'success': False,
            'product_id': None,
            'product_id_new': None,
            'message': '',
            'data': product_data,
            'sku_ids': [],
            'sku_message': '',
            'image_upload': {}
        }
        
        try:
            # 获取渠道码
            source_url = product_data.get('source_url', '')
            alibaba_id = product_data.get('alibaba_product_id')
            channel_code = self._get_channel_code(source_url, alibaba_id)

            # 预先整理通用字段，便于插入和已存在商品更新复用
            category_raw = product_data.get('category', '')
            category_formatted = f"{self._get_category_code(category_raw)}-{category_raw}" if category_raw else self._get_category_code(category_raw)
            master_display_images = self._build_master_display_images(product_data)
            sku_image_pool = self._normalize_image_urls(product_data.get('sku_images', []))
            main_images = self._serialize_json(master_display_images)
            sku_images = self._serialize_json(sku_image_pool)
            skus = self._serialize_json(product_data.get('skus', []))
            logistics_payload = self._merge_logistics_payload(product_data, weight_data)
            logistics = self._serialize_json(logistics_payload)
            supplier_info = self._serialize_json(product_data.get('supplier_info', {}))
            key_attributes = self._serialize_json(product_data.get('key_attributes', []))
            purchase_cost_history = self._serialize_json(product_data.get('purchase_cost_history', []))
            
            # 生成新格式主货号（18位）
            product_id_new = self._generate_product_id_new(channel_code)
            result['product_id_new'] = product_id_new
            
            # 生成旧格式主货号（兼容）
            date_map = {
                0: '日', 1: '一', 2: '二', 3: '三', 4: '四',
                5: '五', 6: '六'
            }
            today = datetime.now().weekday()
            date_code = date_map.get(today, '日')
            
            # 获取旧格式序号
            try:
                with db.get_cursor() as cur:
                    cur.execute("""
                        SELECT product_id FROM products 
                        WHERE product_id LIKE %s
                        ORDER BY CAST(SUBSTRING(product_id FROM 2) AS INTEGER) DESC
                        LIMIT 1
                    """, (f'{date_code}%',))
                    res = cur.fetchone()
                    if res:
                        match = re.search(r'(\D)(\d{6})', res[0])
                        seq = int(match.group(2)) + 1 if match else 1
                    else:
                        seq = 1
            except:
                seq = 1
            
            product_id = f"{date_code}{seq:06d}"
            result['product_id'] = product_id
            
            logger.info(f"生成主货号: {product_id} / 新格式: {product_id_new}")
            
            existing_product_meta = None

            # 检查是否已存在
            if alibaba_id:
                with db.get_cursor() as cur:
                    cur.execute("""
                        SELECT id, product_id, product_id_new FROM products 
                                                WHERE alibaba_product_id = %s
                                                    AND COALESCE(is_deleted, 0) = 0
                                                ORDER BY id ASC
                                                LIMIT 1
                    """, (alibaba_id,))
                    existing = cur.fetchone()
                    if existing:
                        result['message'] = f"商品已存在 (ID: {existing[0]}, product_id: {existing[1]}, product_id_new: {existing[2]})"
                        logger.warning(result['message'])
                        cur.execute("""
                            UPDATE products
                            SET title = %s,
                                description = CASE
                                    WHEN NULLIF(BTRIM(COALESCE(description, '')), '') IS NULL THEN %s
                                    ELSE description
                                END,
                                category = %s,
                                brand = %s,
                                origin = %s,
                                main_images = %s,
                                sku_images = %s,
                                skus = %s,
                                logistics = %s,
                                source_url = %s,
                                supplier_info = %s,
                                key_attributes = %s,
                                purchase_cost_history = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (
                            product_data.get('title'),
                            product_data.get('description'),
                            category_formatted,
                            product_data.get('brand'),
                            product_data.get('origin'),
                            main_images,
                            sku_images,
                            skus,
                            logistics,
                            product_data.get('source_url'),
                            supplier_info,
                            key_attributes,
                            purchase_cost_history,
                            existing[0],
                        ))
                        existing_product_meta = {
                            'id': existing[0],
                            'product_id_new': existing[2],
                            'message': f"商品已存在 (ID: {existing[0]}, product_id: {existing[1]}, product_id_new: {existing[2]})",
                        }

                if existing_product_meta:
                    result['message'] = existing_product_meta['message']
                    logger.warning(result['message'])
                    result['success'] = True
                    result['main_product_no'] = existing_product_meta['product_id_new']  # 兼容 workflow_runner（使用新格式）
                    result['product_id_new'] = existing_product_meta['product_id_new']  # 使用真正的新格式货号
                    result['existing_id'] = existing_product_meta['id']
                    self._run_post_persist_steps(
                        result,
                        existing_product_meta['id'],
                        existing_product_meta['product_id_new'],
                        product_data,
                        weight_data,
                        master_display_images,
                        sku_image_pool,
                    )
                    return result
            
            # 插入数据库
            with db.get_cursor() as cur:
                cur.execute("""
                    INSERT INTO products (
                        product_id, product_id_new, alibaba_product_id, title, description,
                        category, brand, origin, main_images, sku_images,
                        skus, logistics, source_url, status,
                        listing_updated_at, published_sites, site_status,
                        optimized_title, optimized_description, optimization_version,
                        supplier_info, key_attributes, quality_score, last_reviewed_at,
                        purchase_cost_history, is_deleted,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    RETURNING id
                """, (
                    product_id,
                    product_id_new,
                    alibaba_id,
                    product_data.get('title'),
                    product_data.get('description'),
                    category_formatted,  # category with code prefix
                    product_data.get('brand'),
                    product_data.get('origin'),  # 留空，待确认
                    main_images,
                    sku_images,
                    skus,
                    logistics,
                    product_data.get('source_url'),
                    'collected',  # status enum
                    datetime.now().isoformat(),  # listing_updated_at
                    json.dumps([], ensure_ascii=False),  # published_sites
                    json.dumps({}, ensure_ascii=False),  # site_status
                    None,  # optimized_title
                    None,  # optimized_description
                    1,  # optimization_version
                    supplier_info,  # supplier_info
                    key_attributes,  # key_attributes
                    None,  # quality_score
                    None,  # last_reviewed_at
                    purchase_cost_history,  # purchase_cost_history
                    0,  # is_deleted (修复：明确写入0)
                    # created_at, updated_at 由数据库自动填充
                ))
                
                inserted_id = cur.fetchone()[0]
            
            result['success'] = True
            result['id'] = inserted_id
            result['main_product_no'] = product_id_new  # 兼容 workflow_runner
            result['message'] = f"落库成功 (ID: {inserted_id}, product_id: {product_id}, product_id_new: {product_id_new})"
            logger.info(result['message'])
            self._run_post_persist_steps(
                result,
                inserted_id,
                product_id_new,
                product_data,
                weight_data,
                master_display_images,
                sku_image_pool,
            )
            
        except Exception as e:
            result['message'] = f"落库失败: {e}"
            logger.error(result['message'])
            import traceback
            traceback.print_exc()
        
        return result
    
    def _upload_images_to_cos(self, product_data: Dict[str, Any], product_id_new: str) -> Dict[str, Any]:
        """
        下载商品图片并上传到COS
        
        目录结构：
        /{商品id}_{商品标题(截取50字符)}/
        ├── main_images/      # 主图
        ├── sku_images/       # SKU图
        └── detail_images/    # 详情图
        
        Args:
            product_data: 商品数据，包含main_images、sku_images、detail_images
            product_id_new: 18位新格式货号，用于生成COS路径
            
        Returns:
            上传结果字典
        """
        import urllib.request
        import os
        from pathlib import Path
        
        result = {
            'success': False,
            'main_images': [],
            'sku_images': [],
            'detail_images': [],
            'master_images': [],
            'message': ''
        }
        
        try:
            # 导入COS存储
            try:
                from shared.cos_storage import COSStorage
            except ImportError:
                from cos_storage import COSStorage
            cos = COSStorage()
            
            # 生成目录名：商品id_商品标题（截取50字符，UTF-8约50字节）
            title = product_data.get('title', '')
            # 清理标题中的非法字符
            title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title)
            # 按字节截取（UTF-8中中文3字节，50字节约16-17个中文字符）
            title_bytes = title.encode('utf-8')
            if len(title_bytes) > 50:
                title = title_bytes[:50].decode('utf-8', errors='ignore')
            # 目录名 = product_id_new + 下划线 + 标题
            dir_name = f"{product_id_new}_{title}"
            
            # 创建临时目录
            temp_dir = Path(f"/home/ubuntu/work/tmp/images/{dir_name}")
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # 上传主图
            sku_image_set = set(self._normalize_image_urls(product_data.get('sku_images', [])))
            main_images = [
                img_url for img_url in product_data.get('main_images', [])
                if not isinstance(img_url, str) or img_url not in sku_image_set
            ]
            main_cos_paths = []
            
            for idx, img_url in enumerate(main_images):  # 上传所有主图
                if not isinstance(img_url, str) or not img_url.startswith(('http://', 'https://')):
                    continue
                    
                local_path = temp_dir / f"main_{idx:02d}.jpg"
                
                try:
                    urllib.request.urlretrieve(img_url, str(local_path))
                    # 上传到COS
                    cos_key = f"{dir_name}/main_images/{local_path.name}"
                    if cos.upload_file(str(local_path), cos_key):
                        main_cos_paths.append(cos_key)
                        logger.info(f"主图上传成功: {cos_key}")
                except Exception as e:
                    logger.warning(f"主图下载/上传失败: {img_url}, {e}")
            
            result['main_images'] = main_cos_paths
            
            # 上传SKU图
            sku_images = product_data.get('sku_images', [])
            sku_cos_paths = []
            
            for idx, img_url in enumerate(sku_images[:20]):  # 最多20张SKU图
                if not isinstance(img_url, str) or not img_url.startswith(('http://', 'https://')):
                    continue
                    
                local_path = temp_dir / f"sku_{idx:02d}.jpg"
                
                try:
                    urllib.request.urlretrieve(img_url, str(local_path))
                    cos_key = f"{dir_name}/sku_images/{local_path.name}"
                    if cos.upload_file(str(local_path), cos_key):
                        sku_cos_paths.append(cos_key)
                        logger.info(f"SKU图上传成功: {cos_key}")
                except Exception as e:
                    logger.warning(f"SKU图下载/上传失败: {img_url}, {e}")
            
            result['sku_images'] = sku_cos_paths
            
            # 上传详情图
            detail_images = product_data.get('detail_images', [])
            detail_cos_paths = []
            
            for idx, img_url in enumerate(detail_images[:30]):  # 最多30张详情图
                if not isinstance(img_url, str) or not img_url.startswith(('http://', 'https://')):
                    continue
                    
                local_path = temp_dir / f"detail_{idx:02d}.jpg"
                
                try:
                    urllib.request.urlretrieve(img_url, str(local_path))
                    cos_key = f"{dir_name}/detail_images/{local_path.name}"
                    if cos.upload_file(str(local_path), cos_key):
                        detail_cos_paths.append(cos_key)
                        logger.info(f"详情图上传成功: {cos_key}")
                except Exception as e:
                    logger.warning(f"详情图下载/上传失败: {img_url}, {e}")
            
            result['detail_images'] = detail_cos_paths
            result['master_images'] = [*main_cos_paths, *[path for path in detail_cos_paths if path not in main_cos_paths]]
            
            result['success'] = True
            result['message'] = f"图片上传完成: 主档图{len(result['master_images'])}张, SKU图{len(sku_cos_paths)}张, 详情图{len(detail_cos_paths)}张"
            result['cos_dir'] = dir_name
            
            # 清理临时文件
            import shutil
            shutil.rmtree(str(temp_dir), ignore_errors=True)
            
            logger.info(result['message'])
            
        except Exception as e:
            result['message'] = f"图片上传失败: {e}"
            logger.error(result['message'])
        
        return result
    
    def store_skus(self, product_id_new: str, skus_data: list, weight_data: dict = None) -> Dict[str, Any]:
        """
        将SKU数据落库
        
        Args:
            product_id_new: 18位新格式主货号
            skus_data: SKU列表，每个包含 color, size, price, stock
            weight_data: 重量数据（来自local-1688-weight）
            
        Returns:
            结果字典，包含sku_ids列表
        """
        result = {
            'success': False,
            'sku_ids': [],
            'message': ''
        }
        
        if not skus_data:
            result['message'] = "无SKU数据"
            return result
        
        try:
            # 获取商品ID
            with db.get_cursor() as cur:
                cur.execute("SELECT id FROM products WHERE product_id_new = %s", (product_id_new,))
                row = cur.fetchone()
                if not row:
                    result['message'] = f"商品不存在: {product_id_new}"
                    return result
                db_product_id = row[0]
            
            # 处理重量数据 - 适配 remote_weight_caller 的返回格式
            # remote_weight_caller返回: {success, sku_count, sku_list: [{sku_name, weight_g, length_cm, width_cm, height_cm}]}
            sku_weight_list = weight_data.get('sku_list', []) if weight_data else []
            default_weight_g = 0
            
            # 如果有sku_list，构建名称到数据的映射
            if sku_weight_list:
                # 检查是否所有SKU共用同一个重量（applies_to_all逻辑）
                weights = [w.get('weight_g', 0) for w in sku_weight_list if w.get('weight_g')]
                if weights and len(set(weights)) == 1:
                    # 所有SKU重量相同
                    default_weight_g = weights[0]
                
                # 创建 sku_name -> weight_data 映射
                spec_map = {s['sku_name']: s for s in sku_weight_list}
            else:
                spec_map = {}

            def normalize_text(value: Any) -> str:
                return re.sub(r'\s+', '', str(value or ''))

            prepared_skus = []
            for idx, sku in enumerate(skus_data):
                raw_name = sku.get('name', '')
                color = sku.get('color', '') or sku.get('name', '')
                size = sku.get('size', '')

                if raw_name:
                    sku_name = raw_name
                elif color and size:
                    sku_name = f"{color}-{size}"
                elif color:
                    sku_name = color
                else:
                    sku_name = f'SKU-{idx+1}'

                price = sku.get('price')
                stock = sku.get('stock')

                matched_spec = None
                candidate_names = [
                    sku_name,
                    f"{color}-{size}" if color and size else '',
                    color,
                    size,
                ]
                normalized_candidates = [normalize_text(item) for item in candidate_names if item]

                for sku_weight_name, spec_data in spec_map.items():
                    normalized_weight_name = normalize_text(sku_weight_name)
                    if any(
                        candidate and (
                            candidate == normalized_weight_name
                            or candidate in normalized_weight_name
                            or normalized_weight_name in candidate
                        )
                        for candidate in normalized_candidates
                    ):
                        matched_spec = spec_data
                        break

                weight_g = default_weight_g
                length_cm = None
                width_cm = None
                height_cm = None

                if matched_spec:
                    weight_g = matched_spec.get('weight_g') or default_weight_g
                    length_cm = matched_spec.get('length_cm')
                    width_cm = matched_spec.get('width_cm')
                    height_cm = matched_spec.get('height_cm')
                elif default_weight_g:
                    weight_g = default_weight_g

                prepared_skus.append({
                    'index': idx,
                    'sku_name': sku_name,
                    'color': color or '',
                    'size': size or '',
                    'price': price,
                    'stock': stock,
                    'image_url': sku.get('image') if isinstance(sku.get('image'), str) else None,
                    'weight_g': weight_g,
                    'length_cm': length_cm,
                    'width_cm': width_cm,
                    'height_cm': height_cm,
                })
            
            # 插入SKU
            sku_ids = []
            with db.get_cursor() as cur:
                incoming_keys = {
                    (item['sku_name'], item['color'], item['size'])
                    for item in prepared_skus
                }
                cur.execute("""
                    SELECT id, sku_name, COALESCE(color, ''), COALESCE(size, '')
                    FROM product_skus
                    WHERE product_id = %s AND COALESCE(is_deleted, 0) = 0
                """, (db_product_id,))
                for existing_id, existing_name, existing_color, existing_size in cur.fetchall():
                    existing_key = (existing_name or '', existing_color or '', existing_size or '')
                    if existing_key not in incoming_keys:
                        cur.execute("UPDATE product_skus SET is_deleted = 1 WHERE id = %s", (existing_id,))
                        logger.info(f"标记旧SKU为删除: {existing_name}")

                for item in prepared_skus:
                    sku_name = item['sku_name']
                    color = item['color']
                    size = item['size']
                    price = item['price']
                    stock = item['stock']
                    image_url = item['image_url']
                    weight_g = item['weight_g']
                    length_cm = item['length_cm']
                    width_cm = item['width_cm']
                    height_cm = item['height_cm']

                    sku_id_new = self._generate_sku_id_new(product_id_new, item['index'])

                    cur.execute("""
                        SELECT id, package_weight FROM product_skus
                        WHERE product_id = %s
                          AND sku_name = %s
                          AND COALESCE(color, '') = %s
                          AND COALESCE(size, '') = %s
                        ORDER BY COALESCE(is_deleted, 0) ASC, id ASC
                        LIMIT 1
                    """, (db_product_id, sku_name, color, size))
                    existing_sku = cur.fetchone()
                    
                    if existing_sku:
                        existing_id, existing_weight = existing_sku
                        cur.execute("""
                            UPDATE product_skus SET
                                color = %s,
                                size = %s,
                                price = %s,
                                stock = %s,
                                image_url = COALESCE(%s, image_url),
                                package_length = COALESCE(%s, package_length),
                                package_width = COALESCE(%s, package_width),
                                package_height = COALESCE(%s, package_height),
                                package_weight = COALESCE(%s, package_weight),
                                sku_id_new = %s,
                                is_deleted = 0
                            WHERE id = %s
                        """, (color, size, price, stock, image_url, length_cm, width_cm, height_cm, weight_g, sku_id_new, existing_id))
                        if weight_g and (not existing_weight or existing_weight == 0):
                            logger.info(f"更新SKU重量: {sku_name} -> {weight_g}g")
                        else:
                            logger.info(f"更新SKU信息: {sku_name}")
                        sku_ids.append(existing_id)
                    else:
                        cur.execute("""
                            INSERT INTO product_skus (
                                product_id, sku_name, color, size, price, stock,
                                image_url,
                                package_length, package_width, package_height, package_weight,
                                currency, is_domestic_shipping, stock_updated_at, stock_source,
                                sku_id_new, is_deleted,
                                created_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                'CNY', true, %s, 'system',
                                %s, 0,
                                CURRENT_TIMESTAMP
                            )
                            RETURNING id
                        """, (
                            db_product_id,
                            sku_name,
                            color,
                            size,
                            price,
                            stock,
                            image_url,
                            length_cm,
                            width_cm,
                            height_cm,
                            weight_g,
                            datetime.now().isoformat(),
                            sku_id_new,
                        ))
                        sku_ids.append(cur.fetchone()[0])
            
            result['success'] = True
            result['sku_ids'] = sku_ids
            result['message'] = f"SKU落库成功: {len(sku_ids)}条"
            logger.info(result['message'])
            
        except Exception as e:
            result['message'] = f"SKU落库失败: {e}"
            logger.error(result['message'])
            import traceback
            traceback.print_exc()
        
        return result
    
    def get_by_alibaba_id(self, alibaba_product_id: str) -> Optional[Dict[str, Any]]:
        """根据阿里巴巴商品ID查询"""
        try:
            with db.get_cursor() as cur:
                cur.execute("""
                    SELECT id, product_id, product_id_new, alibaba_product_id, title, description,
                           category, brand, origin, main_images, sku_images,
                           skus, logistics, source_url, status, created_at
                                        FROM products
                                        WHERE alibaba_product_id = %s
                                            AND COALESCE(is_deleted, 0) = 0
                                        ORDER BY id ASC
                                        LIMIT 1
                """, (alibaba_product_id,))
                
                row = cur.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'product_id': row[1],
                        'product_id_new': row[2],
                        'alibaba_product_id': row[3],
                        'title': row[4],
                        'description': row[5],
                        'category': row[6],
                        'brand': row[7],
                        'origin': row[8],
                        'main_images': json.loads(row[9]) if isinstance(row[9], str) else (row[9] or []),
                        'sku_images': json.loads(row[10]) if isinstance(row[10], str) else (row[10] or []),
                        'skus': json.loads(row[11]) if isinstance(row[11], str) else (row[11] or []),
                        'logistics': json.loads(row[12]) if isinstance(row[12], str) else (row[12] or {}),
                        'source_url': row[13],
                        'status': row[14],
                        'created_at': row[15].isoformat() if row[15] else None
                    }
        except Exception as e:
            logger.error(f"查询失败: {e}")
        return None
    
    def update_status(self, product_id: str, status: str) -> bool:
        """更新商品状态"""
        try:
            with db.get_cursor() as cur:
                cur.execute("""
                    UPDATE products SET status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE product_id = %s OR product_id_new = %s
                """, (status, product_id, product_id))
                return True
        except Exception as e:
            logger.error(f"更新状态失败: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='商品数据落库工具')
    parser.add_argument('--alibaba-id', type=str, help='阿里巴巴商品ID')
    parser.add_argument('--product-id', type=str, help='主货号')
    parser.add_argument('--supplier-code', type=str, default='0001', help='供应商码(4位)')
    parser.add_argument('--series-code', type=str, default='001', help='系列码(3位)')
    parser.add_argument('--list', action='store_true', help='列出所有商品')
    parser.add_argument('--query', type=str, help='按阿里巴巴ID查询')
    args = parser.parse_args()
    
    storer = ProductStorer(
        supplier_code=args.supplier_code,
        series_code=args.series_code
    )
    
    if args.list:
        print("\n" + "="*60)
        print("商品列表:")
        try:
            with db.get_cursor() as cur:
                cur.execute("""
                    SELECT id, product_id, product_id_new, alibaba_product_id, title, status, created_at
                    FROM products ORDER BY id DESC LIMIT 20
                """)
                rows = cur.fetchall()
                for r in rows:
                    title = r[4][:40] + '...' if r[4] and len(r[4]) > 40 else r[4]
                    print(f"  [{r[0]}] {r[1]} | {r[2]} | {r[5]} | {title}")
                print(f"\n共 {len(rows)} 条记录")
        except Exception as e:
            print(f"查询失败: {e}")
        print("="*60)
    
    elif args.query:
        result = storer.get_by_alibaba_id(args.query)
        if result:
            print("\n" + "="*60)
            print("商品信息:")
            for k, v in result.items():
                if k in ['main_images', 'skus', 'logistics']:
                    print(f"  {k}: {json.dumps(v, ensure_ascii=False)[:200]}...")
                elif v:
                    print(f"  {k}: {v}")
            print("="*60)
        else:
            print(f"未找到商品: {args.query}")
    
    elif args.alibaba_id:
        # 模拟数据落库
        test_data = {
            'alibaba_product_id': args.alibaba_id,
            'title': '测试商品',
            'description': '测试描述',
            'category': '收纳盒、收纳包与篮子',
            'brand': '测试品牌',
            'main_images': ['https://example.com/image1.jpg'],
            'skus': [{'color': '红色', 'size': 'M', 'price': 10.0, 'stock': 100}],
            'source_url': f'https://detail.1688.com/offer/{args.alibaba_id}.html'
        }
        result = storer.store(test_data)
        print(f"\n结果: {result['message']}")
        if result.get('product_id_new'):
            print(f"新货号: {result['product_id_new']}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
