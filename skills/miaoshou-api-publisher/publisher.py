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
import json
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
sys.path.insert(0, str(WORKSPACE / 'scripts'))
sys.path.insert(0, '/home/ubuntu/.openclaw/skills/shared')

import db

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
    
    def __init__(self):
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
    
    def _make_request(self, endpoint, data=None, method='GET'):
        """发送API请求"""
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
            return result.get('detailList', [])
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
            # 更新状态为已发布
            self.update_product_status(product.get('id'), 'published')
            return True, '商品已在采集箱（已同步状态）'
        
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
                # 更新状态为published（因为商品已经在采集箱了）
                self.update_product_status(product.get('id'), 'published')
                return True, '商品已在采集箱（数据冲突，已同步状态）'
            
            return False, reason
    
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
    import argparse
    parser = argparse.ArgumentParser(description='妙手API发布器')
    parser.add_argument('--limit', type=int, default=5, help='最多发布商品数')
    parser.add_argument('--list', action='store_true', help='列出待发布商品')
    args = parser.parse_args()
    
    publisher = MiaoshouAPIPublisher()
    
    if args.list:
        products = publisher.get_optimized_products(20)
        print(f"\n待发布商品 ({len(products)} 个):")
        print("-" * 60)
        for p in products:
            title = (p.get('optimized_title') or p.get('title') or 'N/A')[:40]
            print(f"  [{p['id']}] {p['product_id_new']} | {title}...")
        print("-" * 60)
    else:
        publisher.run(limit=args.limit)


if __name__ == '__main__':
    main()
