# local-1688-weight-server.py
# 本地运行，监听 127.0.0.1:8080
# 通过 MobaXterm SSH隧道映射到远程服务器访问

from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import logging
import json
import time
import re

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 1688 cookies 文件路径
COOKIES_FILE = "1688_cookies.json"

def load_cookies():
    """加载1688 cookies"""
    try:
        with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Cookie文件不存在: {COOKIES_FILE}")
        return None

def extract_weight_from_page(page) -> dict:
    """从1688商品详情页提取重量和尺寸"""
    result = {
        'weight_g': None,
        'length_cm': None,
        'width_cm': None,
        'height_cm': None,
        'raw_data': {}
    }
    
    try:
        page_text = page.inner_text('body')
        
        # ========== 提取重量 ==========
        # 方法1: 搜索"重量"关键词后的数值
        weight_patterns = [
            r'重量[：:\s]*([0-9.]+)\s*(?:kg|KG|千克|公斤)',
            r'毛重[：:\s]*([0-9.]+)\s*(?:kg|KG|千克|公斤)?',
            r'净重[：:\s]*([0-9.]+)\s*(?:kg|KG|千克|公斤)?',
            r'([0-9.]+)\s*kg',
        ]
        
        for pattern in weight_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                result['weight_g'] = float(match.group(1)) * 1000  # kg转g
                break
        
        # 方法2: 在SKU区域搜索
        if not result['weight_g']:
            # 搜索"毛重"或"重量"关键词周围的区域
            lines = page_text.split('\n')
            for i, line in enumerate(lines):
                if any(k in line for k in ['毛重', '净重', '重量']):
                    # 检查后续几行
                    for j in range(i+1, min(i+5, len(lines))):
                        next_line = lines[j].strip()
                        match = re.search(r'([0-9.]+)', next_line)
                        if match:
                            val = float(match.group(1))
                            if 0.01 < val < 500:  # 合理重量范围
                                result['weight_g'] = val * 1000  # kg转g
                                break
                    if result['weight_g']:
                        break
        
        # ========== 提取尺寸 ==========
        # 格式: 30*20*15 或 30x20x15 (cm)
        size_patterns = [
            r'尺寸[：:\s]*(\d+)\s*[\*xX]\s*(\d+)\s*[\*xX]\s*(\d+)\s*(?:cm|CM|厘米)?',
            r'包装尺寸[：:\s]*(\d+)\s*[\*xX]\s*(\d+)\s*[\*xX]\s*(\d+)\s*(?:cm|CM|厘米)?',
            r'外径[：:\s]*(\d+)\s*[\*xX]\s*(\d+)\s*[\*xX]\s*(\d+)',
        ]
        
        for pattern in size_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                result['length_cm'] = int(match.group(1))
                result['width_cm'] = int(match.group(2))
                result['height_cm'] = int(match.group(3))
                break
        
        # 方法2: 从SKU规格中提取
        if not result['length_cm']:
            # 匹配格式: 大号35*25*16cm
            sku_pattern = r'([\u4e00-\u9fa5]*(?:大号|小号|中号)?)\s*(\d+)\s*[\*xX]\s*(\d+)\s*[\*xX]\s*(\d+)\s*cm'
            matches = re.findall(sku_pattern, page_text)
            if matches:
                # 取第一个匹配
                m = matches[0]
                result['length_cm'] = int(m[1])
                result['width_cm'] = int(m[2])
                result['height_cm'] = int(m[3])
        
        # 保存原始数据供调试
        result['raw_data'] = {
            'page_text_length': len(page_text),
            'has_weight': result['weight_g'] is not None,
            'has_size': result['length_cm'] is not None
        }
        
    except Exception as e:
        logger.error(f"提取页面数据失败: {e}")
    
    return result

@app.route('/fetch-weight', methods=['POST'])
def fetch_weight():
    """
    接收商品ID/URL，返回重量和尺寸
    
    请求格式:
    {
        "product_id": "1027205078815"  // 或完整URL
    }
    
    返回格式:
    {
        "success": true/false,
        "product_id": "...",
        "url": "...",
        "weight_g": 1500,  # kg转g
        "length_cm": 30,
        "width_cm": 20,
        "height_cm": 15,
        "error": null
    }
    """
    data = request.get_json()
    
    if not data or 'product_id' not in data:
        return jsonify({'error': '缺少product_id参数'}), 400
    
    product_id = str(data['product_id'])
    
    # 构建完整URL
    if not product_id.startswith('http'):
        product_id = f"https://detail.1688.com/offer/{product_id}.html"
    
    logger.info(f"开始获取商品重量: {product_id}")
    
    cookies = load_cookies()
    if not cookies:
        return jsonify({
            'success': False,
            'error': '1688 cookies未配置',
            'product_id': data.get('product_id'),
            'url': product_id
        }), 200
    
    result = {
        'success': False,
        'product_id': data.get('product_id'),
        'url': product_id,
        'weight_g': None,
        'length_cm': None,
        'width_cm': None,
        'height_cm': None,
        'error': None
    }
    
    # 使用锁防止Playwright多线程冲突
    import threading
    _playwright_lock = threading.Lock()
    
    try:
        with _playwright_lock:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # 添加cookies
            pc_cookies = []
            for c in cookies.get('cookies', []):
                pc_cookies.append({
                    'name': c['name'],
                    'value': c['value'],
                    'domain': c.get('domain', '.1688.com'),
                    'path': c.get('path', '/'),
                    'secure': c.get('secure', True),
                    'httpOnly': c.get('httpOnly', False)
                })
            context.add_cookies(pc_cookies)
            
            page = context.new_page()
            page.set_default_timeout(60000)
            
            # 访问商品页面
            response = page.goto(product_id, wait_until='domcontentloaded')
            
            if response and response.status in [403, 302]:
                result['error'] = f'页面访问失败: HTTP {response.status}'
                browser.close()
                return jsonify(result), 200
            
            # 等待页面加载
            time.sleep(3)
            
            # 提取数据
            weight_data = extract_weight_from_page(page)
            result.update(weight_data)
            
            # 判断是否成功
            result['success'] = any([
                result['weight_g'],
                result['length_cm']
            ])
            
            if not result['success']:
                result['error'] = '未能提取到重量/尺寸信息'
            
            logger.info(f"提取结果: weight={result['weight_g']}, size={result['length_cm']}x{result['width_cm']}x{result['height_cm']}")
            
            browser.close()
            
    except Exception as e:
        logger.error(f"获取重量失败: {e}")
        result['error'] = str(e)
    
    return jsonify(result)

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'service': '1688-weight-fetcher'})

@app.route('/batch-fetch', methods=['POST'])
def batch_fetch():
    """
    批量获取多个商品的重量和尺寸
    
    请求格式:
    {
        "product_ids": ["1027205078815", "6023456789012"]
    }
    """
    data = request.get_json()
    
    if not data or 'product_ids' not in data:
        return jsonify({'error': '缺少product_ids参数'}), 400
    
    product_ids = data['product_ids']
    results = []
    
    for pid in product_ids:
        # 每个商品调用一次
        result = fetch_weight_internal(pid)
        results.append(result)
        time.sleep(1)  # 避免请求过快
    
    return jsonify({
        'success': True,
        'results': results
    })

def fetch_weight_internal(product_id):
    """内部方法：获取单个商品重量"""
    if not str(product_id).startswith('http'):
        product_id = f"https://detail.1688.com/offer/{product_id}.html"
    
    cookies = load_cookies()
    if not cookies:
        return {'product_id': product_id, 'success': False, 'error': 'no cookies'}
    
    result = {
        'success': False,
        'product_id': product_id,
        'weight_g': None,
        'length_cm': None,
        'width_cm': None,
        'height_cm': None
    }
    
    # 使用锁防止Playwright多线程冲突
    import threading
    _playwright_lock = threading.Lock()
    
    try:
        with _playwright_lock:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 1920, 'height': 1080})
            
            pc_cookies = []
            for c in cookies.get('cookies', []):
                pc_cookies.append({
                    'name': c['name'],
                    'value': c['value'],
                    'domain': c.get('domain', '.1688.com'),
                    'path': c.get('path', '/'),
                    'secure': c.get('secure', True),
                })
            context.add_cookies(pc_cookies)
            
            page = context.new_page()
            page.set_default_timeout(60000)
            page.goto(product_id, wait_until='domcontentloaded')
            time.sleep(3)
            
            weight_data = extract_weight_from_page(page)
            result.update(weight_data)
            result['success'] = any([result['weight_g'], result['length_cm']])
            
            browser.close()
    except Exception as e:
        result['error'] = str(e)
    
    return result

if __name__ == '__main__':
    print("=" * 50)
    print("1688 重量获取服务")
    print("=" * 50)
    print("监听地址: http://127.0.0.1:8080")
    print("通过隧道映射后，远程可访问")
    print("")
    print("接口:")
    print("  POST /fetch-weight  - 获取单个商品重量")
    print("  POST /batch-fetch  - 批量获取")
    print("  GET  /health       - 健康检查")
    print("")
    print("注意: 需要提前准备好 1688_cookies.json")
    print("=" * 50)
    
    # 使用单线程模式避免Playwright与多线程冲突
app.run(host='127.0.0.1', port=9090, debug=False, threaded=True, use_reloader=False)
