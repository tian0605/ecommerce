#!/usr/bin/env python3
"""
miaoshou-api-publisher - 妙手ERP API发布器

基于HAR抓包分析，直接调用妙手API发布商品到Shopee采集箱
比Playwright更稳定快速

使用方法:
    python3 publisher.py --limit 1
    python3 publisher.py --product-id 1031400982378
"""
import sys
import argparse
import json
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Tuple

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
sys.path.insert(0, str(WORKSPACE / 'scripts'))
sys.path.insert(0, '/home/ubuntu/.openclaw/skills/shared')

try:
    import db
except ImportError:
    db = None

# 妙手API配置
MIAOSHOU_BASE_URL = 'https://erp.91miaoshou.com'
COOKIES_FILE = Path('/home/ubuntu/work/config/miaoshou_cookies.json')

# API端点
API_ENDPOINTS = {
    'search_collect_box': '/api/platform/shopee/move/collect_box/search_collect_box_detail',
    'save_site_detail': '/api/platform/shopee/move/collect_box/saveSiteDetailData',
    'get_category_tree': '/api/platform/shopee/move/collect_box/getCategoryTreeBySite',
    'get_attribute_map': '/api/platform/shopee/move/collect_box/getCollectBoxMultipleAttributeMap',
}


class MiaoshouAPIPublisher:
    """妙手API发布器"""
    
    def __init__(self, require_cookies=True):
        self.require_cookies = require_cookies
        self.cookies = []
        self.cookie_str = ''
        if require_cookies:
            self.cookies = self._load_cookies()
            self.cookie_str = self._build_cookie_str()

    def _ensure_db(self):
        """确保数据库模块可用"""
        if db is None:
            raise RuntimeError('db 模块不可用，当前环境不能执行数据库相关操作')

    def _ensure_cookies(self):
        """确保Cookies已加载"""
        if not self.cookie_str:
            self.cookies = self._load_cookies()
            self.cookie_str = self._build_cookie_str()
    
    def _load_cookies(self):
        """加载Cookies"""
        if not COOKIES_FILE.exists():
            raise FileNotFoundError(f"Cookie文件不存在: {COOKIES_FILE}")
        
        with open(COOKIES_FILE) as f:
            cookies = json.load(f)
        
        if isinstance(cookies, dict):
            cookies = cookies.get('cookies', [])
        
        return cookies
    
    def _build_cookie_str(self):
        """构建Cookie字符串"""
        return '; '.join([f"{c['name']}={c['value']}" for c in self.cookies])

    @staticmethod
    def _safe_float(value, default=0.0):
        """安全转换浮点数"""
        if value in (None, ''):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value, default=0):
        """安全转换整数"""
        if value in (None, ''):
            return default
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_list(value):
        """将值标准化为列表"""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                return [value]
        return []

    def normalize_debug_input(self, raw_product: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
        """将调试样例标准化为内部product/skus结构"""
        product = {
            'id': raw_product.get('id'),
            'product_id': raw_product.get('product_id') or raw_product.get('货源ID') or raw_product.get('sourceItemId'),
            'alibaba_product_id': raw_product.get('alibaba_product_id') or raw_product.get('货源ID') or raw_product.get('sourceItemId'),
            'title': raw_product.get('title') or raw_product.get('产品标题') or '',
            'description': raw_product.get('description') or raw_product.get('简易描述') or '',
            'optimized_title': raw_product.get('optimized_title') or raw_product.get('产品标题') or raw_product.get('title') or '',
            'optimized_description': raw_product.get('optimized_description') or raw_product.get('简易描述') or raw_product.get('description') or '',
            'product_id_new': raw_product.get('product_id_new') or raw_product.get('主货号') or raw_product.get('itemNum') or '',
            'category_cid': raw_product.get('category_cid') or raw_product.get('类目') or raw_product.get('cid') or '101174',
            'main_images': self._normalize_list(
                raw_product.get('main_images')
                or raw_product.get('主图')
                or raw_product.get('主图URL列表')
                or raw_product.get('imgUrls')
            ),
        }

        raw_skus = (
            raw_product.get('skus')
            or raw_product.get('SKUs')
            or raw_product.get('sku_list')
            or raw_product.get('SKU列表')
            or []
        )
        package_size = raw_product.get('包裹尺寸') or {}
        default_weight_kg = self._safe_float(
            raw_product.get('包装重量(kg)')
            or raw_product.get('包装重量')
            or raw_product.get('weight'),
            0.0,
        )
        skus = []
        for index, sku in enumerate(raw_skus, start=1):
            sku_name = (
                sku.get('sku_name')
                or sku.get('SKU名称')
                or sku.get('名称')
                or sku.get('name')
                or f'SKU{index}'
            )
            weight_kg = self._safe_float(
                sku.get('package_weight_kg')
                or sku.get('包装重量(kg)')
                or sku.get('weight_kg'),
                None,
            )
            if weight_kg is None:
                weight_g = sku.get('package_weight') or sku.get('包装重量(g)') or sku.get('weight_g')
                if weight_g not in (None, ''):
                    weight_kg = self._safe_float(weight_g, 0.0) / 1000
                else:
                    weight_kg = default_weight_kg

            skus.append({
                'sku_name': sku_name,
                'price': self._safe_float(sku.get('price') or sku.get('售价') or sku.get('价格'), 0),
                'stock': self._safe_int(sku.get('stock') or sku.get('库存'), 99999),
                'package_weight': weight_kg * 1000 if weight_kg else 0,
                'package_length': sku.get('package_length') or sku.get('长度(cm)') or package_size.get('长度(cm)'),
                'package_width': sku.get('package_width') or sku.get('宽度(cm)') or package_size.get('宽度(cm)'),
                'package_height': sku.get('package_height') or sku.get('高度(cm)') or package_size.get('高度(cm)'),
            })

        validation_notes = []
        declared_sku_count = raw_product.get('SKU数量')
        if declared_sku_count and len(skus) != self._safe_int(declared_sku_count, len(skus)):
            validation_notes.append(
                f"样例声明SKU数量={declared_sku_count}，但提供的SKU明细={len(skus)}"
            )
        if not skus:
            validation_notes.append('样例缺少 SKU 明细，当前只能做 payload 调试，不能可靠发布到妙手 API')
        if not product['main_images']:
            validation_notes.append('样例缺少主图 URL 列表，API 实际发布时通常需要 imgUrls')

        return product, skus, validation_notes

    def validate_product_data(self, product_data: Dict[str, Any], strict=False) -> List[str]:
        """校验发布请求数据"""
        errors = []
        required_fields = {
            'cid': '类目ID',
            'title': '产品标题',
            'itemNum': '主货号',
        }
        for field, label in required_fields.items():
            if not product_data.get(field):
                errors.append(f'缺少{label}({field})')

        source_item_id = product_data.get('sourceItemMetaInfo', {}).get('sourceItemId')
        if not source_item_id:
            errors.append('缺少货源ID(sourceItemMetaInfo.sourceItemId)')

        if not product_data.get('skuMap'):
            errors.append('缺少 SKU 明细(skuMap)')
        if strict and not product_data.get('imgUrls'):
            errors.append('缺少主图 URL 列表(imgUrls)')

        return errors

    def debug_product_payload(self, raw_product: Dict[str, Any]) -> Dict[str, Any]:
        """构建调试用的发布 payload"""
        product, skus, notes = self.normalize_debug_input(raw_product)
        product_data = self.build_product_data(product, skus)
        validation_errors = self.validate_product_data(product_data, strict=False)
        return {
            'product': product,
            'skus': skus,
            'product_data': product_data,
            'notes': notes,
            'validation_errors': validation_errors,
        }
    
    def _make_request(self, endpoint, data=None, method='GET'):
        """发送API请求"""
        self._ensure_cookies()
        url = f"{MIAOSHOU_BASE_URL}{endpoint}"
        
        if data:
            if isinstance(data, dict):
                data = urllib.parse.urlencode(data)
            data = data.encode('utf-8')
        
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                'Cookie': self.cookie_str,
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://erp.91miaoshou.com/',
            }
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ''
            return {'result': 'error', 'error': f'HTTP {e.code}', 'body': error_body}
        except Exception as e:
            return {'result': 'error', 'error': str(e)}
    
    def search_collect_box(self, source_item_id=None, page=1, page_size=20):
        """搜索采集箱商品"""
        # 构建查询参数
        params = {
            'pageNo': page,
            'pageSize': page_size,
        }
        
        result = self._make_request(
            API_ENDPOINTS['search_collect_box'] + f"?pageNo={page}&pageSize={page_size}",
            method='GET'
        )
        
        if result.get('result') == 'success':
            details = result.get('detailList', [])
            if source_item_id is None:
                return details

            matched = []
            for detail in details:
                source_info = detail.get('sourceItemMetaInfo', {})
                if str(source_info.get('sourceItemId')) == str(source_item_id):
                    matched.append(detail)
            return matched
        return []
    
    def check_product_exists(self, source_item_id):
        """检查商品是否已在采集箱"""
        details = self.search_collect_box(source_item_id=source_item_id)
        
        for detail in details:
            source_info = detail.get('sourceItemMetaInfo', {})
            if str(source_info.get('sourceItemId')) == str(source_item_id):
                return True, detail
        
        return False, None
    
    def save_site_detail(self, product_data):
        """
        保存商品到采集箱
        
        Args:
            product_data: 商品数据字典
        
        Returns:
            dict: {'result': 'success'/'fail', 'reason': '...'}
        """
        # 构建请求数据
        data = {
            'siteDetailSimpleData': json.dumps(product_data, ensure_ascii=False)
        }
        
        return self._make_request(
            API_ENDPOINTS['save_site_detail'],
            data=data,
            method='POST'
        )
    
    def build_product_data(self, product, skus=None):
        """
        从数据库商品构建API请求数据
        
        Args:
            product: products表记录(dict)
            skus: product_skus表记录(list)
        
        Returns:
            dict: 符合saveSiteDetailData API格式的数据
        """
        # 获取SKU数据
        if not skus:
            skus = []
        
        # 构建SKU Map
        sku_map = {}
        for sku in skus:
            sku_key = f";{sku.get('sku_name', '')};;"
            sku_map[sku_key] = {
                'price': float(sku.get('price', 0)),
                'stock': int(sku.get('stock', 99999)),
                'weight': float(sku.get('package_weight', 0)) / 1000 if sku.get('package_weight') else 0.3,
                'packageLength': str(sku.get('package_length', '')) if sku.get('package_length') else None,
                'packageWidth': str(sku.get('package_width', '')) if sku.get('package_width') else None,
                'packageHeight': str(sku.get('package_height', '')) if sku.get('package_height') else None,
                'itemNum': f"{product.get('alibaba_product_id')}_{sku.get('sku_name', '')}",
                'originPrice': float(sku.get('price', 0)),
                'sellerStock': None,
                'colorPropName': sku.get('sku_name', ''),
                'sizePropName': '',
                'systemPrice': ''
            }
        
        # 主商品数据
        product_data = {
            'cid': str(product.get('category_cid', '101174')),  # 默认类目
            'title': product.get('optimized_title', product.get('title', '')),
            'itemNum': product.get('product_id_new', ''),
            'price': '',
            'stock': '',
            'colorPropName': '顏色',
            'sizePropName': '尺碼',
            'colorMap': {},
            'sizeMap': {},
            'skuMap': sku_map,
            'imgUrls': product.get('main_images', []),
            'weight': float(skus[0].get('package_weight', 910)) / 1000 if skus and skus[0].get('package_weight') else 0.91,
            'packageLength': str(skus[0].get('package_length', 41)) if skus else '41',
            'packageWidth': str(skus[0].get('package_width', 21)) if skus else '21',
            'packageHeight': str(skus[0].get('package_height', 36)) if skus else '36',
            'notes': product.get('optimized_description', ''),
            'richTextDesc': '',  # HTML格式描述
            'wholesaleList': [],
            'attributeMaps': {},
            'brand': {'brandId': 0, 'brandName': 'NoBrand'},
            'logisticList': [],
            'isPreOrder': 0,
            'daysToShip': 1,
            'isUse': 0,
            'sizeChart': '',
            'mainImgVideoUrl': '',
            'sourceItemMetaInfo': {
                'source': '1688',
                'sourceNameFw': 'A',
                'sourceAddress': None,
                'sourceAddressFw': None,
                'sourceItemId': str(product.get('alibaba_product_id', '')),
                'oriItemNum': None,
                'maxSkuPrice': str(skus[0].get('price', '') if skus else '')
            }
        }
        
        return product_data
    
    def get_optimized_products(self, limit=10):
        """获取待发布的商品（已优化但未发布，且有关联SKU）"""
        self._ensure_db()
        products = []
        
        with db.get_cursor() as cur:
            cur.execute("""
                SELECT 
                    p.id, p.product_id, p.alibaba_product_id, p.title,
                    p.description, p.category, p.main_images,
                    p.optimized_title, p.optimized_description,
                    p.status, p.product_id_new
                FROM products p
                INNER JOIN product_skus ps ON p.id = ps.product_id
                WHERE p.status IN ('optimized', 'collected')
                  AND p.optimized_title IS NOT NULL
                  AND p.optimized_title != ''
                  AND p.alibaba_product_id IS NOT NULL
                GROUP BY p.id
                ORDER BY p.updated_at DESC
                LIMIT %s
            """, (limit,))
            
            for row in cur.fetchall():
                products.append({
                    'id': row[0],
                    'product_id': row[1],
                    'alibaba_product_id': row[2],
                    'title': row[3],
                    'description': row[4],
                    'category': row[5],
                    'main_images': json.loads(row[6]) if isinstance(row[6], str) else (row[6] or []),
                    'optimized_title': row[7],
                    'optimized_description': row[8],
                    'status': row[9],
                    'product_id_new': row[10]
                })
        
        return products
    
    def get_skus(self, product_db_id):
        """获取商品SKU数据"""
        self._ensure_db()
        skus = []
        
        with db.get_cursor() as cur:
            cur.execute("""
                SELECT sku_name, price, stock, package_weight, 
                       package_length, package_width, package_height
                FROM product_skus
                WHERE product_id = %s
            """, (product_db_id,))
            
            for row in cur.fetchall():
                skus.append({
                    'sku_name': row[0],
                    'price': row[1],
                    'stock': row[2],
                    'package_weight': row[3],
                    'package_length': row[4],
                    'package_width': row[5],
                    'package_height': row[6]
                })
        
        return skus
    
    def update_product_status(self, product_id, status):
        """更新商品状态"""
        self._ensure_db()
        with db.get_cursor() as cur:
            cur.execute("""
                UPDATE products 
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (status, product_id))
    
    def publish_product(self, product):
        """
        发布单个商品
        
        Returns:
            tuple: (success: bool, message: str)
        """
        alibaba_id = product.get('alibaba_product_id')
        print(f"\n{'='*60}")
        print(f"发布商品: {alibaba_id}")
        print(f"标题: {product.get('optimized_title', '')[:50]}...")
        
        # 1. 检查是否已在采集箱
        exists, existing = self.check_product_exists(alibaba_id)
        if exists:
            print(f"⚠️ 商品已在采集箱，跳过")
            return False, '商品已在采集箱，未执行真实发布核验，拒绝自动标记为 published'
        
        # 2. 获取SKU数据
        skus = self.get_skus(product.get('id'))
        print(f"SKU数量: {len(skus)}")
        for sku in skus:
            print(f"  - {sku.get('sku_name')}: {sku.get('price')}")
        
        # 3. 构建API数据
        product_data = self.build_product_data(product, skus)
        
        # 4. 调用API发布
        print(f"调用API发布...")
        result = self.save_site_detail(product_data)
        
        if result.get('result') == 'success':
            print(f"✅ 发布成功!")
            
            # 5. 更新状态
            self.update_product_status(product.get('id'), 'published')
            
            return True, '发布成功'
        else:
            reason = result.get('reason', result.get('error', '未知错误'))
            print(f"❌ 发布失败: {reason}")
            
            # 检查是否是数据冲突（商品正在被编辑或刚刚发布）
            if '编辑过程中' in reason or '数据发生变动' in reason or '正在被编辑' in reason:
                return False, f'发布状态不确定: {reason}'
            
            return False, reason

    def publish_product_by_id(self, product_id):
        """发布指定商品ID或货源ID"""
        self._ensure_db()
        with db.get_cursor() as cur:
            cur.execute("""
                SELECT 
                    p.id, p.product_id, p.alibaba_product_id, p.title,
                    p.description, p.category, p.main_images,
                    p.optimized_title, p.optimized_description,
                    p.status, p.product_id_new
                FROM products p
                WHERE p.id::text = %s
                   OR p.product_id::text = %s
                   OR p.alibaba_product_id::text = %s
                   OR p.product_id_new = %s
                LIMIT 1
            """, (str(product_id), str(product_id), str(product_id), str(product_id)))
            row = cur.fetchone()

        if not row:
            return False, f'未找到商品: {product_id}'

        product = {
            'id': row[0],
            'product_id': row[1],
            'alibaba_product_id': row[2],
            'title': row[3],
            'description': row[4],
            'category': row[5],
            'main_images': json.loads(row[6]) if isinstance(row[6], str) else (row[6] or []),
            'optimized_title': row[7],
            'optimized_description': row[8],
            'status': row[9],
            'product_id_new': row[10]
        }
        return self.publish_product(product)
    
    def run(self, limit=5):
        """运行发布流程"""
        print(f"\n{'='*60}")
        print(f"🚀 妙手API发布器启动")
        print(f"{'='*60}")
        
        # 获取待发布商品
        products = self.get_optimized_products(limit)
        print(f"待发布商品数: {len(products)}")
        
        if not products:
            print("没有待发布的商品")
            return []
        
        success_count = 0
        fail_count = 0
        
        for product in products:
            success, message = self.publish_product(product)
            
            if success:
                success_count += 1
            else:
                fail_count += 1
            
            # 避免请求过快
            import time
            time.sleep(1)
        
        print(f"\n{'='*60}")
        print(f"发布完成: 成功 {success_count}, 失败 {fail_count}")
        print(f"{'='*60}")
        
        return products[:success_count]


def main():
    parser = argparse.ArgumentParser(description='妙手API发布器')
    parser.add_argument('--limit', type=int, default=5, help='最多发布商品数')
    parser.add_argument('--list', action='store_true', help='列出待发布商品')
    parser.add_argument('--product-id', help='发布指定商品ID/货源ID/主货号')
    parser.add_argument('--product-data', help='直接传入JSON样例调试发布payload')
    parser.add_argument('--product-data-file', help='从JSON文件读取调试样例')
    parser.add_argument('--dry-run', action='store_true', help='仅构建并输出payload，不调用妙手API')
    parser.add_argument('--dump-json', action='store_true', help='打印调试生成的payload JSON')
    args = parser.parse_args()
    
    require_cookies = not (args.list or args.dry_run)
    publisher = MiaoshouAPIPublisher(require_cookies=require_cookies)
    
    if args.list:
        products = publisher.get_optimized_products(20)
        print(f"\n待发布商品 ({len(products)} 个):")
        print("-" * 60)
        for p in products:
            title = (p.get('optimized_title') or p.get('title') or 'N/A')[:40]
            print(f"  [{p['id']}] {p['product_id_new']} | {title}...")
        print("-" * 60)
    elif args.product_data or args.product_data_file:
        raw_json = args.product_data
        if args.product_data_file:
            raw_json = Path(args.product_data_file).read_text(encoding='utf-8')

        raw_product = json.loads(raw_json)
        debug_result = publisher.debug_product_payload(raw_product)
        product_data = debug_result['product_data']

        print(f"\n调试商品: {product_data.get('sourceItemMetaInfo', {}).get('sourceItemId')}")
        print(f"标题: {product_data.get('title')}")
        print(f"主货号: {product_data.get('itemNum')}")
        print(f"SKU数: {len(debug_result['skus'])}")

        if debug_result['notes']:
            print("\n调试备注:")
            for note in debug_result['notes']:
                print(f"  - {note}")

        if debug_result['validation_errors']:
            print("\n校验结果:")
            for error in debug_result['validation_errors']:
                print(f"  - {error}")

        if args.dump_json:
            print("\n生成的 siteDetailSimpleData:")
            print(json.dumps(product_data, indent=2, ensure_ascii=False))

        if args.dry_run:
            print("\nDry-run 完成，未调用妙手API")
            return

        strict_errors = publisher.validate_product_data(product_data, strict=True)
        if strict_errors:
            print("\n无法调用妙手API，缺少关键字段:")
            for error in strict_errors:
                print(f"  - {error}")
            sys.exit(1)

        result = publisher.save_site_detail(product_data)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.product_id:
        success, message = publisher.publish_product_by_id(args.product_id)
        print(message)
        if not success:
            sys.exit(1)
    else:
        publisher.run(limit=args.limit)


if __name__ == '__main__':
    main()
