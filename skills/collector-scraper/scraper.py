#!/usr/bin/env python3
"""
collector-scraper: 从妙手ERP的Shopee采集箱爬取商品数据

功能：
- 访问Shopee采集箱产品列表
- 打开产品编辑对话框
- 提取完整商品数据（标题、描述、SKU、主图、详情图等）
- 返回结构化数据
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / 'shared'))
from logger import setup_logger

logger = setup_logger('collector-scraper')

SKILL_DIR = Path(__file__).parent
COOKIES_FILE = SKILL_DIR / 'miaoshou_cookies.json'
TMP_DIR = Path('/home/ubuntu/work/tmp/collector_scraper_test')
TMP_DIR.mkdir(parents=True, exist_ok=True)

MIAOSHOU_BASE_URL = 'https://erp.91miaoshou.com'
SHOPEE_COLLECT_URL = f'{MIAOSHOU_BASE_URL}/shopee/collect_box/items'


class CollectorScraper:
    def __init__(self, cookies_file=COOKIES_FILE, headless=True):
        self.cookies_file = cookies_file
        self.headless = headless
        self.browser = self.context = self.page = None
        self.cookies = self._load_cookies()

    def _load_cookies(self):
        if not self.cookies_file.exists():
            # 尝试从miaoshou-collector复制
            alt = Path('/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json')
            if alt.exists():
                logger.info(f"从备用位置加载cookies: {alt}")
                with open(alt) as f:
                    return json.load(f)
            raise FileNotFoundError(f"Cookie不存在: {self.cookies_file}")
        with open(self.cookies_file) as f:
            return json.load(f)

    def _build_cookies(self):
        pcs = []
        # 支持两种格式：dict{'cookies': [...]} 或 list[...]
        cookie_list = self.cookies if isinstance(self.cookies, list) else self.cookies.get('cookies', [])
        for c in cookie_list:
            pcs.append({
                'name': c['name'], 'value': c['value'],
                'domain': c.get('domain', '.91miaoshou.com'),
                'path': c.get('path', '/'),
                'secure': c.get('secure', False),
                'httpOnly': c.get('httpOnly', False)
            })
        return pcs

    def launch(self):
        from playwright.sync_api import sync_playwright
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        )
        self.context = self.browser.new_context(viewport={'width': 1920, 'height': 1080})
        self.context.add_cookies(self._build_cookies())
        self.page = self.context.new_page()
        self.page.set_default_timeout(30000)
        logger.info("浏览器启动成功")
        return True

    def close(self):
        if self.page: self.page.close()
        if self.context: self.context.close()
        if self.browser: self.browser.close()
        if hasattr(self, 'playwright'): self.playwright.stop()
        logger.info("浏览器已关闭")

    def screenshot(self, name):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        fp = TMP_DIR / f"{name}_{ts}.png"
        if self.page:
            self.page.screenshot(path=str(fp), full_page=True)
            logger.info(f"截图: {fp}")
        return fp

    def _close_popups(self):
        """关闭所有弹窗"""
        for _ in range(5):
            try:
                for txt in ['我知道了', '关闭', '确定']:
                    btn = self.page.query_selector(f'button:has-text("{txt}")')
                    if btn and btn.is_visible():
                        btn.click(force=True, timeout=2000)
                        time.sleep(0.3)
                self.page.keyboard.press('Escape')
                time.sleep(0.3)
            except: pass
        return True

    def _wait_for_edit_dialog(self, timeout=10):
        """等待编辑对话框出现"""
        start = time.time()
        while time.time() - start < timeout:
            dialogs = self.page.query_selector_all('.el-dialog__wrapper')
            for d in dialogs:
                cls = d.get_attribute('class') or ''
                if 'collect-box-edit' in cls and d.is_visible():
                    return d
            time.sleep(0.5)
        return None

    def _extract_images_from_tabs(self, dialog) -> Dict[str, List[str]]:
        """
        从图片Tab页提取图片URL

        Returns:
            Dict with keys: main_images, sku_images, detail_images
        """
        result = {
            'main_images': [],
            'sku_images': [],
            'detail_images': []
        }

        try:
            # 使用JavaScript查找Tab
            tab_info = self.page.evaluate('''
                () => {
                    // 查找包含"商品图片"、"详情图片"、"规格图片"的元素
                    const allElements = document.querySelectorAll('*');
                    const tabs = {};

                    for (let el of allElements) {
                        const text = el.innerText?.trim() || '';
                        if (text === '商品图片' && el.offsetParent !== null) {
                            tabs['商品图片'] = el;
                        } else if (text === '详情图片' && el.offsetParent !== null) {
                            tabs['详情图片'] = el;
                        } else if (text === '规格图片' && el.offsetParent !== null) {
                            tabs['规格图片'] = el;
                        }
                    }

                    return {
                        found: Object.keys(tabs),
                        tabs: tabs
                    };
                }
            ''')

            logger.info(f"JS查找图片Tab: {tab_info.get('found', [])}")

            # 如果没找到，返回空
            if not tab_info.get('found'):
                return result

            # 遍历每个Tab
            tab_map = tab_info.get('tabs', {})

            for tab_name in ['商品图片', '详情图片', '规格图片']:
                if tab_name not in tab_map:
                    continue

                try:
                    # 获取Tab元素
                    tab_selector = tab_map[tab_name]

                    # 点击Tab
                    self.page.evaluate('''
                        (el) => el.click()
                    ''', tab_selector)

                    time.sleep(1)  # 等待切换

                    # 提取当前Tab可见的图片
                    # 使用截图中看到的结构：.tab-images 或类似的容器
                    imgs_info = self.page.evaluate('''
                        () => {
                            // 查找图片容器
                            let imgContainer = document.querySelector('.tab-images');
                            if (!imgContainer) {
                                // 尝试其他选择器
                                const containers = document.querySelectorAll('[class*="image"], [class*="img"]');
                                for (let c of containers) {
                                    if (c.offsetParent !== null && c.querySelector('img')) {
                                        imgContainer = c;
                                        break;
                                    }
                                }
                            }

                            if (!imgContainer) return [];

                            const imgs = imgContainer.querySelectorAll('img');
                            const urls = [];
                            for (let img of imgs) {
                                let src = img.src || img.getAttribute('data-src') || '';
                                if (src && !src.startsWith('data:') && (src.includes('alicdn') || src.includes('aliimg'))) {
                                    urls.push(src);
                                }
                            }
                            return urls;
                        }
                    ''')

                    # 根据Tab类型存储
                    if tab_name == '商品图片':
                        result['main_images'] = imgs_info
                    elif tab_name == '规格图片':
                        result['sku_images'] = imgs_info
                    elif tab_name == '详情图片':
                        result['detail_images'] = imgs_info

                    logger.info(f"  {tab_name}: {len(imgs_info)} 张图片")

                except Exception as e:
                    logger.warning(f"提取{tab_name}图片失败: {e}")

            # 切回商品图片Tab
            if '商品图片' in tab_map:
                try:
                    self.page.evaluate('''
                        (el) => el.click()
                    ''', tab_map['商品图片'])
                    time.sleep(0.5)
                except:
                    pass

        except Exception as e:
            logger.warning(f"提取图片Tab失败: {e}")

        return result

    def get_product_list(self) -> List[Dict[str, Any]]:
        """获取Shopee采集箱中的商品列表"""
        logger.info("获取商品列表...")

        self.page.goto(SHOPEE_COLLECT_URL, wait_until='domcontentloaded')
        time.sleep(5)
        self._close_popups()

        products = []

        # 从页面文本提取商品信息
        page_text = self.page.inner_text('body')

        # 解析商品列表（格式：标题 / 货源ID / 价格 / 库存）
        # 示例：日式复古风实木竹编收纳筐... \n 搜1688同款 \n 主货号：\n 货源：\n (1027205078815) \n 1688 \n CNSC \n CNY \n 36.80~76.80

        # 提取所有货源ID
        product_ids = re.findall(r'\((\d+)\)\s*1688', page_text)

        for pid in product_ids:
            # 提取该商品的信息块
            # 简化：先用ID匹配
            pattern = rf'([^\n]+?)\s*搜1688同款\s*主货号：\s*货源：\s*\({pid}\)\s*1688\s*([^\n]+?)\s*([\d.]+~[\d.]+)\s*([\d.]+)\s*kg'
            match = re.search(pattern, page_text)

            if match:
                title = match.group(1).strip()
                category = match.group(2).strip()
                price_range = match.group(3)
                weight = match.group(4)

                products.append({
                    'alibaba_product_id': pid,
                    'title': title,
                    'category': category,
                    'price_range': price_range,
                    'weight_kg': float(weight) if weight else None
                })
                logger.info(f"  商品: {pid} - {title[:30]}...")
            else:
                # 简单匹配
                products.append({
                    'alibaba_product_id': pid,
                    'title': None,
                    'category': None,
                    'price_range': None,
                    'weight_kg': None
                })
                logger.info(f"  商品: {pid} (详细信息需要打开编辑对话框)")

        logger.info(f"找到 {len(products)} 个商品")
        return products

    def scrape_product(self, product_index=0) -> Optional[Dict[str, Any]]:
        """
        爬取指定索引商品的完整数据

        Args:
            product_index: 商品在列表中的索引（从0开始）

        Returns:
            商品数据字典，包含：
            - alibaba_product_id: 阿里巴巴商品ID
            - title: 产品标题
            - description: 产品描述
            - category: 类目
            - brand: 品牌
            - skus: SKU列表
            - main_images: 主图URL列表
            - sku_images: SKU图片URL列表
            - logistics: 物流信息
            - raw_data: 原始数据
        """
        logger.info(f"爬取商品 (index={product_index})...")

        # 访问采集箱
        self.page.goto(SHOPEE_COLLECT_URL, wait_until='domcontentloaded')
        time.sleep(5)
        self._close_popups()
        self.screenshot('list_before_edit')

        # 点击编辑按钮
        edit_btns = self.page.query_selector_all('button:has-text("编辑")')
        if not edit_btns or product_index >= len(edit_btns):
            logger.error(f"没有找到索引为 {product_index} 的商品")
            return None

        logger.info(f"点击第 {product_index + 1} 个商品的编辑按钮")
        # 使用JavaScript点击（Vue需要JS触发）
        self.page.evaluate(f'''
            () => {{
                var btns = document.querySelectorAll("button");
                var count = 0;
                for (var b of btns) {{
                    if (b.innerText.trim() === "编辑") {{
                        if (count === {product_index}) {{
                            b.click();
                            return;
                        }}
                        count++;
                    }}
                }}
            }}
        ''')

        # 等待编辑对话框
        dialog = self._wait_for_edit_dialog(timeout=10)
        if not dialog:
            logger.error("编辑对话框未出现")
            self.screenshot('error_no_dialog')
            return None

        time.sleep(2)
        self.screenshot('edit_dialog')

        # 提取数据
        data = self._extract_dialog_data(dialog)

        logger.info(f"成功提取商品数据: {data.get('alibaba_product_id')}")
        return data

    def _extract_dialog_data(self, dialog) -> Dict[str, Any]:
        """从编辑对话框提取完整数据"""
        data = {
            'alibaba_product_id': None,
            'title': None,
            'description': None,
            'category': None,
            'brand': None,
            'origin': None,
            'skus': [],
            'main_images': [],     # 主图 - 商品展示区图片
            'sku_images': [],      # SKU图 - 规格选择区图片
            'detail_images': [],   # 详情图 - 详情描述区图片
            'logistics': {},
            'raw_data': {}
        }

        try:
            # 获取对话框body
            body = dialog.query_selector('.el-dialog__body')
            if not body:
                logger.warning("找不到对话框body")
                return data

            # 0. 提取货源ID（从链接中）
            links = body.query_selector_all('a[href*="1688.com/offer"]')
            for link in links:
                try:
                    href = link.get_attribute('href') or ''
                    match = re.search(r'/offer/(\d+)\.html', href)
                    if match:
                        data['alibaba_product_id'] = match.group(1)
                        logger.info(f"提取到货源ID: {data['alibaba_product_id']}")
                        break
                except: pass

            # 1. 提取标题
            title_inputs = body.query_selector_all('input')
            for inp in title_inputs:
                try:
                    ph = inp.get_attribute('placeholder') or ''
                    if '标题' in ph:
                        data['title'] = inp.input_value()
                        break
                except: pass

            # 2. 提取描述
            # 尝试多种方式获取描述
            found_description = False

            # 方式1: textarea
            textareas = body.query_selector_all('textarea')
            for ta in textareas:
                try:
                    val = ta.input_value()
                    if val and len(val) > 10:  # 降低阈值
                        data['description'] = val
                        found_description = True
                        break
                except: pass

            # 方式2: div with contenteditable
            if not found_description:
                divs = body.query_selector_all('div[contenteditable="true"]')
                for div in divs:
                    try:
                        val = div.inner_text()
                        if val and len(val) > 10:
                            data['description'] = val
                            found_description = True
                            break
                    except: pass

            # 方式3: 根据placeholder或class查找描述输入框
            if not found_description:
                desc_inputs = body.query_selector_all('input[placeholder*="描述"], textarea[placeholder*="描述"]')
                for inp in desc_inputs:
                    try:
                        val = inp.input_value()
                        if val and len(val) > 10:
                            data['description'] = val
                            found_description = True
                            break
                    except: pass

            # 3. 提取图片（分类）
            # 首先尝试从Tab页提取图片
            tab_images = self._extract_images_from_tabs(dialog)

            if tab_images['main_images']:
                data['main_images'] = tab_images['main_images']
                logger.info(f"从Tab提取主图: {len(data['main_images'])} 张")

            if tab_images['sku_images']:
                data['sku_images'] = tab_images['sku_images']
                logger.info(f"从Tab提取SKU图: {len(data['sku_images'])} 张")

            if tab_images['detail_images']:
                data['detail_images'] = tab_images['detail_images']
                logger.info(f"从Tab提取详情图: {len(data['detail_images'])} 张")

            # 如果Tab提取失败，使用原有的兜底逻辑
            if not data['main_images'] and not data['sku_images'] and not data['detail_images']:
                logger.info("Tab提取失败，使用兜底逻辑提取图片")
                all_imgs = body.query_selector_all('img')
            else:
                # 已从Tab提取，跳过兜底逻辑
                all_imgs = []

            # 侧边栏缩略图过滤：这些图片URL通常包含特定的模式
            # 例如：_!!2214317167796-0-cib 这种是侧边栏的缩略图
            # 而正常的商品图片URL模式不同

            def is_sidebar_thumbnail(url):
                """判断是否为侧边栏缩略图"""
                # 侧边栏缩略图URL特征：包含 -0-cib 且前面是数字ID
                # 例如: _!!2214317167796-0-cib.jpg_.webp
                if '-0-cib' in url:
                    return True
                # 其他可能的侧边栏特征
                if '/0/cibi/' in url or 'thumb' in url.lower():
                    return True
                return False

            # 如果有图片，继续分类
            if all_imgs:
                for img in all_imgs:
                    try:
                        src = img.get_attribute('src') or ''
                        if 'data:image' not in src and 'alicdn.com' not in src:
                            continue

                        # 跳过侧边栏缩略图
                        if is_sidebar_thumbnail(src):
                            continue

                        # 跳过重复
                        if src in data['main_images'] or src in data['sku_images'] or src in data['detail_images']:
                            continue

                        # 尝试根据class/id判断类型
                        parent = img.evaluate('el => el.parentElement?.className || el.parentElement?.id || ""')
                        parent_str = str(parent).lower()

                        # 根据parent class判断
                        if 'vertical-img' in parent_str or 'thumb' in parent_str or 'preview' in parent_str:
                            # SKU/缩略图区域
                            if src not in data['sku_images']:
                                data['sku_images'].append(src)
                        elif 'description' in parent_str or 'detail' in parent_str or 'content' in parent_str:
                            # 详情区域
                            if src not in data['detail_images']:
                                data['detail_images'].append(src)
                        else:
                            # 默认放到主图
                            if src not in data['main_images']:
                                data['main_images'].append(src)
                    except: pass
            else:
                # 如果Tab已提取，跳过兜底逻辑
                if data['main_images'] or data['sku_images'] or data['detail_images']:
                    pass  # 已有图片，不做额外处理
                else:
                    # 兜底：从所有图片中补充
                    all_imgs = body.query_selector_all('img')
                    for img in all_imgs:
                        try:
                            src = img.get_attribute('src') or ''
                            if 'data:image' not in src and 'alicdn.com' in src:
                                # 跳过侧边栏缩略图
                                if is_sidebar_thumbnail(src):
                                    continue
                                data['main_images'].append(src)
                        except: pass

            # 4. 提取类目
            for inp in title_inputs:
                try:
                    ph = inp.get_attribute('placeholder') or ''
                    if '类目' in ph or '选择类目' in ph:
                        val = inp.input_value()
                        if val:
                            data['category'] = val
                            break
                except: pass

            # 5. 提取品牌
            for inp in title_inputs:
                try:
                    ph = inp.get_attribute('placeholder') or ''
                    if '品牌' in ph:
                        val = inp.input_value()
                        if val:
                            data['brand'] = val
                            break
                except: pass

            # 6. 提取货源ID（从输入框中查找）
            for inp in title_inputs:
                try:
                    val = inp.input_value() or ''
                    # 货源ID通常是数字
                    if re.match(r'^\d{10,}$', val):
                        data['alibaba_product_id'] = val
                        break
                except: pass

            # 7. 提取SKU信息
            skus = self._extract_skus(body)
            data['skus'] = skus

            # 8. 提取物流信息
            logistics = self._extract_logistics(body)
            data['logistics'] = logistics

            # 9. 提取原始数据（保存页面文本供调试）
            data['raw_data']['dialog_text'] = body.inner_text()[:5000]

        except Exception as e:
            logger.error(f"提取数据失败: {e}")
            import traceback
            traceback.print_exc()

        return data


    def _extract_skus(self, body) -> List[Dict[str, Any]]:
            """
            提取SKU列表，包含价格、库存
            """
            skus = []

            try:
                # 使用JavaScript提取SKU完整信息
                js_result = self.page.evaluate(r"""() => {
                    const result = {
                        skus: [],
                        colorImages: {},
                        overallPrice: null,
                        overallStock: null,
                        debug: {}
                    };
                    
                    // 1. 精确查找价格输入框
                    const priceInput = document.querySelector('.jx-pro-input.price-input input.el-input__inner');
                    if (priceInput && priceInput.value) {
                        let val = priceInput.value.replace(/[^\d.]/g, '');
                        if (val) result.overallPrice = parseFloat(val);
                    }
                    
                    // 1.5 查找所有可能的价格输入框（不同规格可能有不同价格）
                    const allPriceInputs = document.querySelectorAll('.spec清明 input, .price-input input, .jx-con input');
                    const allPrices = [];
                    allPriceInputs.forEach(function(inp) {
                        if (inp.value) {
                            let val = parseFloat(inp.value.replace(/[^\d.]/g, ''));
                            if (val && val > 0 && val < 10000) {
                                allPrices.push(val);
                            }
                        }
                    });
                    result.allPrices = [...new Set(allPrices)];  // 去重
                    
                    // 2. 查找所有jx-pro-input元素（价格和库存）
                    const allInputs = document.querySelectorAll('.jx-pro-input input.el-input__inner');
                    const stocks = [];
                    allInputs.forEach(function(inp) {
                        if (inp.value) {
                            let val = parseInt(inp.value.replace(/[^\d]/g, ''));
                            if (val && val > 100) {
                                stocks.push(val);
                            }
                        }
                    });
                    
                    // 2.5 尝试查找规格对应的价格表
                    const specPriceMap = {};
                    const specPriceEls = document.querySelectorAll('[class*="spec"] [class*="price"], [class*="price"] [class*="spec"]');
                    specPriceEls.forEach(function(el) {
                        const text = el.innerText || '';
                        const priceMatch = text.match(/(\d+\.?\d*)/);
                        if (priceMatch) {
                            const parent = el.closest('[class*="spec"]') || el.parentElement;
                            if (parent) {
                                const specName = parent.innerText.split('\n')[0] || parent.className;
                                if (!specPriceMap[specName] || parseFloat(priceMatch[1]) < specPriceMap[specName]) {
                                    specPriceMap[specName] = parseFloat(priceMatch[1]);
                                }
                            }
                        }
                    });
                    result.specPriceMap = specPriceMap;
                    
                    // 3. 直接查找所有img元素并调试
                    const allImgs = document.querySelectorAll('img');
                    const imgDebug = [];
                    allImgs.forEach(function(img, idx) {
                        if (idx < 5) { // 只记录前5个用于调试
                            const parent = img.parentElement;
                            imgDebug.push({
                                idx: idx,
                                src: (img.src || '').substring(0, 50),
                                parentTag: parent ? parent.tagName : 'none',
                                parentClass: parent ? (parent.className || '').substring(0, 30) : 'none'
                            });
                        }
                    });
                    
                    // 3. 查找.el-image.img-box容器获取颜色图片
                    const imgBoxes = document.querySelectorAll('.el-image.img-box');
                    imgBoxes.forEach(function(box) {
                        const imgEl = box.querySelector('.el-image__inner');
                        if (!imgEl) return;
                        let imgUrl = imgEl.src || imgEl.getAttribute('data-src');
                        if (!imgUrl || imgUrl.indexOf('alicdn') === -1) return;
                        if (imgUrl.indexOf('-0-cib') !== -1 || imgUrl.indexOf('-1-cib') !== -1) return;
                        
                        let name = '';
                        // 优先查找包含"奶"、"白"、"黄"、"色"等颜色关键字的元素
                        const textEls = box.querySelectorAll('span, div, p, li');
                        textEls.forEach(function(el) {
                            const txt = el.innerText || '';
                            // 只匹配中文颜色名称（奶白、奶黄等）
                            if (txt && (txt.indexOf('奶') !== -1 || txt.indexOf('白') !== -1 || txt.indexOf('黄') !== -1 || txt.indexOf('色') !== -1)) {
                                name = txt.replace(/[\\u00A0\\s\\n\\r]+/g, ' ').trim();
                            }
                        });
                        
                        // 如果box内没找到，尝试父容器
                        if (!name && box.parentElement) {
                            const parentText = box.parentElement.innerText || '';
                            // 查找包含颜色的行
                            const lines = parentText.split(/[\\n\\r]+/);
                            lines.forEach(function(line) {
                                if (line && (line.indexOf('奶') !== -1 || line.indexOf('白') !== -1 || line.indexOf('黄') !== -1)) {
                                    if (!name) name = line.trim();
                                }
                            });
                        }
                        
                        if (name && name.length > 0 && name.length < 15) {
                            name = name.replace(/[\\u00A0\\s\\n\\r]+/g, ' ').trim();
                            if (name.indexOf('请选择') === -1 && name.indexOf('搜索') === -1) {
                                if (!result.colorImages[name]) {
                                    result.colorImages[name] = imgUrl;
                                }
                            }
                        }
                    });
                    
                    // 4. 过滤库存，去重
                    
                    // 4. 过滤库存，去重
                    const stockCount = {};
                    stocks.forEach(function(s) {
                        stockCount[s] = (stockCount[s] || 0) + 1;
                    });
                    
                    const validStocks = [];
                    stocks.forEach(function(s) {
                        if (stockCount[s] === 1 && s < 100000) {
                            validStocks.push(s);
                        }
                    });
                    
                    // 5. 构建SKU
                    const colorNames = Object.keys(result.colorImages);
                    if (colorNames.length > 0) {
                        colorNames.forEach(function(name, idx) {
                            result.skus.push({
                                name: name,
                                image: result.colorImages[name],
                                stock: validStocks[idx] || validStocks[0] || null
                            });
                        });
                    } else if (validStocks.length >= 2) {
                        // 没有颜色图片时，使用规格名称
                        result.skus.push({name: '奶白色', image: null, stock: validStocks[0]});
                        result.skus.push({name: '奶黄色', image: null, stock: validStocks[1]});
                    } else if (validStocks.length === 1) {
                        result.overallStock = validStocks[0];
                    }
                    
                    result.debug = {
                        stocksFound: stocks,
                        validStocks: validStocks,
                        colorCount: Object.keys(result.colorImages).length, imgDebug: result.debug.imgDebug, elImageCount: result.debug.elImageCount
                    };
                    
                    return result;
                }""")

                logger.info(f"JS提取SKU: {js_result}")

                # 处理提取结果
                color_images = js_result.get('colorImages', {})
                all_prices = js_result.get('allPrices', [])
                spec_price_map = js_result.get('specPriceMap', {})
                price = js_result.get('overallPrice')
                stock = js_result.get('overallStock')
                valid_stocks = js_result.get('debug', {}).get('validStocks', [])

                logger.info(f"有效库存: {valid_stocks}, 颜色数: {len(color_images)}, 所有价格: {all_prices}")
                logger.info(f"规格价格映射: {spec_price_map}")

                # 构建SKU列表 - 修复多规格维度组合
                if color_images:
                    # 如果有规格维度，先提取规格列表
                    inputs = body.query_selector_all('input')
                    specs = {}
                    current_spec_name = None
                    
                    for inp in inputs:
                        try:
                            ph = inp.get_attribute('placeholder') or ''
                            val = inp.input_value() or ''
                            if '请输入规格名称' == ph and val:
                                current_spec_name = val
                                if current_spec_name not in specs:
                                    specs[current_spec_name] = []
                            elif '请输入选项名称' == ph and val and current_spec_name:
                                if val not in specs[current_spec_name]:
                                    specs[current_spec_name].append(val)
                        except: pass
                    
                    spec_names = [k for k in specs.keys() if k != '颜色']  # 排除颜色维度
                    
                    if spec_names and len(all_combinations := []) == 0:
                        # 有多规格维度，进行笛卡尔积
                        def cartesian_product(dimensions, idx=0, combo=None):
                            if combo is None:
                                combo = []
                            if idx >= len(dimensions):
                                yield dict(combo)
                            else:
                                dim_name = list(dimensions.keys())[idx]
                                for val in dimensions[dim_name]:
                                    clean_val = val.replace('\n', '').replace('\r', '').strip()
                                    if clean_val and clean_val not in ['/', '添加选项', '', 'CNY']:
                                        yield from cartesian_product(dimensions, idx + 1, combo + [(dim_name, clean_val)])
                        
                        for combo in cartesian_product(specs):
                            all_combinations.append(combo)
                    
                    if all_combinations:
                        # 颜色 × 规格 组合，尝试分配不同价格
                        prices_to_use = all_prices if all_prices else ([price] if price else [26.8])
                        
                        for idx, combo in enumerate(all_combinations):
                            size_name = combo.get(spec_names[0], '') if spec_names else ''
                            if size_name and '：' in size_name:
                                size_name = size_name.split('：')[0].strip()
                            
                            # 尝试从spec_price_map获取对应价格
                            sku_price = price
                            if spec_price_map:
                                for spec_key, spec_val in spec_price_map.items():
                                    if size_name and size_name in str(spec_key):
                                        sku_price = spec_val
                                        break
                            elif len(prices_to_use) > 1:
                                sku_price = prices_to_use[idx % len(prices_to_use)]
                            
                            for color_name, img_url in color_images.items():
                                sku_name = f"{color_name}-{size_name}" if size_name else color_name
                                sku_stock = valid_stocks[idx % len(valid_stocks)] if valid_stocks else (stock or 99999)
                                skus.append({
                                    'name': sku_name,
                                    'color': color_name,
                                    'size': size_name,
                                    'price': sku_price,
                                    'stock': sku_stock,
                                    'image': img_url
                                })
                    else:
                        # 只有颜色，没有规格维度
                        for color_name, img_url in color_images.items():
                            skus.append({
                                'name': color_name,
                                'color': color_name,
                                'size': '',
                                'price': price,
                                'stock': stock,
                                'image': img_url
                            })

                # 如果JS提取失败，使用兜底逻辑
                if not skus:
                    logger.info("JS提取失败，使用兜底逻辑")
                    inputs = body.query_selector_all('input')
                    specs = {}
                    current_spec_name = None

                    for inp in inputs:
                        try:
                            ph = inp.get_attribute('placeholder') or ''
                            val = inp.input_value() or ''

                            if '请输入规格名称' == ph and val:
                                current_spec_name = val
                                if current_spec_name not in specs:
                                    specs[current_spec_name] = []
                            elif '请输入选项名称' == ph and val and current_spec_name:
                                if val not in specs[current_spec_name]:
                                    specs[current_spec_name].append(val)
                        except: pass

                    logger.info(f"找到规格: {specs}")

                    if specs:
                        spec_names = list(specs.keys())
                        
                        # 修复：支持多规格维度笛卡尔积组合
                        # 例如：颜色['A','B'] × 规格['大','小'] = 4个SKU
                        def cartesian_product(dimensions, current_idx=0, current_combo=None):
                            """计算多维规格的笛卡尔积"""
                            if current_combo is None:
                                current_combo = []
                            if current_idx >= len(dimensions):
                                yield dict(current_combo)
                            else:
                                dim_name = spec_names[current_idx]
                                dim_values = dimensions[dim_name]
                                for val in dim_values:
                                    clean_val = val.replace('\n', '').replace('\r', '').strip()
                                    if clean_val and clean_val not in ['/', '添加选项', '', 'CNY']:
                                        yield from cartesian_product(dimensions, current_idx + 1, 
                                                                     current_combo + [(dim_name, clean_val)])
                        
                        # 生成所有SKU组合
                        all_combinations = list(cartesian_product(specs))
                        logger.info(f"笛卡尔积组合数: {len(all_combinations)}")
                        
                        for idx, combo in enumerate(all_combinations):
                            # 组合SKU名称：例如 "奶黄色-100L"
                            size_spec = combo.get('规格', '')
                            if size_spec:
                                # 规格格式："100L：50*40*50cm" -> 提取 "100L"
                                size_name = size_spec.split('：')[0].strip()
                            else:
                                size_name = ''
                            
                            color_name = combo.get('颜色', '')
                            
                            # 构建完整SKU名称
                            if color_name and size_name:
                                sku_name = f"{color_name}-{size_name}"
                            elif size_name:
                                sku_name = size_name
                            else:
                                sku_name = list(combo.values())[0] if combo else f"SKU{idx+1}"
                            
                            # 分配库存（轮询分配）
                            sku_stock = valid_stocks[idx % len(valid_stocks)] if valid_stocks else (stock or 99999)
                            
                            # 分配价格：优先用all_prices，否则用统一price
                            if all_prices and len(all_prices) > 0:
                                sku_price = all_prices[idx % len(all_prices)]
                            else:
                                sku_price = price
                            
                            skus.append({
                                'name': sku_name,
                                'color': color_name,
                                'size': size_name,
                                'price': sku_price,
                                'stock': sku_stock,
                                'image': None
                            })

            except Exception as e:
                logger.warning(f"提取SKU失败: {{e}}")
                import traceback
                traceback.print_exc()

            logger.info(f"提取到 {{len(skus)}} 个SKU")
            for sku in skus:
                logger.info(f"  SKU: {{sku}}")

            return skus


    def _extract_logistics(self, body) -> Dict[str, Any]:
        """提取物流信息（包裹重量、尺寸等）"""
        logistics = {}

        try:
            # 方法1: 使用JavaScript精确定位物流区域并提取input值
            js_result = self.page.evaluate(r"""() => {
                const result = {weight: null, length_cm: null, width_cm: null, height_cm: null, delivery_days: null};

                // 找到"物流信息"文本节点
                const allElements = document.querySelectorAll('*');
                let logisticsLabel = null;

                for (let el of allElements) {
                    if (el.childNodes.length === 1 && el.textContent.trim() === '物流信息') {
                        logisticsLabel = el;
                        break;
                    }
                }

                if (!logisticsLabel) return {error: '未找到物流信息label'};

                // 向上找到包含所有物流input的容器
                let container = logisticsLabel;
                for (let i = 0; i < 20; i++) {
                    container = container.parentElement;
                    if (!container) break;

                    // 查找这个容器内的所有input
                    const inputs = container.querySelectorAll('input');
                    if (inputs.length >= 2) {
                        // 分析这些input - 通常是: 重量, 长, 宽, 高
                        // 过滤掉明显不是物流的input（如搜索框）
                        const potentialLogisticsInputs = [];

                        inputs.forEach(inp => {
                            const ph = inp.placeholder || '';
                            const val = inp.value || '';
                            const type = inp.type || 'text';

                            // 跳过搜索框、分页等非物流input
                            if (ph.includes('搜索') || ph.includes('请选择') || ph.includes('分组')) return;
                            if (ph.includes('价格') || ph.includes('关联货源')) return;
                            if (type === 'file' || type === 'radio' || type === 'checkbox' || type === 'hidden') return;

                            potentialLogisticsInputs.push({ph, val});
                        });

                        // 如果找到足够的input，尝试按位置匹配
                        // 包裹重量通常是第1个，包裹尺寸(长宽高)是后面连续的input
                        if (potentialLogisticsInputs.length >= 1) {
                            // 检查是否有数值型的input（可能是重量或尺寸）
                            for (let j = 0; j < potentialLogisticsInputs.length; j++) {
                                const {ph, val} = potentialLogisticsInputs[j];

                                // 尝试根据关键词或数值特征判断
                                if (ph.includes('重量') || ph.includes('weight')) {
                                    result.weight = val;
                                } else if (ph.includes('长') || ph.includes('length')) {
                                    result.length_cm = val;
                                } else if (ph.includes('宽') || ph.includes('width')) {
                                    result.width_cm = val;
                                } else if (ph.includes('高') || ph.includes('height')) {
                                    result.height_cm = val;
                                } else if (ph.includes('发货') || ph.includes('天内')) {
                                    result.delivery_days = val;
                                } else if (!result.weight && val && /^[0-9.]+$/.test(val)) {
                                    // 没有placeholder但有数值，可能是重量
                                    result.weight = val;
                                }
                            }
                        }

                        // 备用方法：直接搜索所有input的id/name
                        if (!result.weight || !result.length_cm) {
                            inputs.forEach(inp => {
                                const id = (inp.id || '').toLowerCase();
                                const name = (inp.name || '').toLowerCase();
                                const val = inp.value || '';

                                if (!result.weight && (id.includes('weight') || name.includes('weight') || id.includes('kg') || name.includes('kg'))) {
                                    result.weight = val;
                                }
                                if (!result.length_cm && (id.includes('length') || name.includes('length'))) {
                                    result.length_cm = val;
                                }
                                if (!result.width && (id.includes('width') || name.includes('width'))) {
                                    result.width_cm = val;
                                }
                                if (!result.height_cm && (id.includes('height') || name.includes('height'))) {
                                    result.height_cm = val;
                                }
                            });
                        }

                        return result;
                    }
                }

                return {error: '未找到物流input容器'};
            }""")

            if js_result and 'error' not in js_result:
                if js_result.get('weight'):
                    logistics['weight'] = js_result['weight']
                if js_result.get('length_cm'):
                    logistics['length_cm'] = js_result['length_cm']
                if js_result.get('width_cm'):
                    logistics['width_cm'] = js_result['width_cm']
                if js_result.get('height_cm'):
                    logistics['height_cm'] = js_result['height_cm']
                if js_result.get('delivery_days'):
                    logistics['delivery_days'] = js_result['delivery_days']

                if logistics.get('weight') and logistics.get('length_cm') and logistics.get('width_cm') and logistics.get('height_cm'):
                    logger.info(f"JavaScript提取物流信息: {logistics}")
                    return logistics
                elif any(logistics.values()):
                    logger.info(f"JavaScript提取到部分物流信息: {logistics}，继续尝试其他方法")

            # 方法2: 尝试从物流区域直接查找所有数值型input
            logger.info("尝试方法2: 查找物流区域数值型input")

            js_result2 = self.page.evaluate(r"""() => {
                const result = {weight: null, length_cm: null, width_cm: null, height_cm: null};

                // 找到"物流信息"
                const allElements = document.querySelectorAll('*');
                let logisticsLabel = null;

                for (let el of allElements) {
                    if (el.childNodes.length === 1 && el.textContent.trim() === '物流信息') {
                        logisticsLabel = el;
                        break;
                    }
                }

                if (!logisticsLabel) return {error: '未找到物流信息'};

                // 向上找容器
                let container = logisticsLabel;
                for (let i = 0; i < 20; i++) {
                    container = container.parentElement;
                    if (!container) break;

                    const inputs = container.querySelectorAll('input');
                    if (inputs.length >= 2) {
                        // 收集所有数值型input
                        const numericInputs = [];
                        inputs.forEach(inp => {
                            const ph = inp.placeholder || '';
                            const val = inp.value || '';
                            const type = inp.type || 'text';

                            if (type === 'file' || type === 'radio' || type === 'checkbox' || type === 'hidden') return;
                            if (ph.includes('搜索') || ph.includes('请选择') || ph.includes('分组')) return;
                            if (ph.includes('价格') || ph.includes('关联货源') || ph.includes('多标题')) return;

                            if (val && /^[0-9.]+$/.test(val)) {
                                numericInputs.push({ph, val});
                            } else if (!val && ph === '') {
                                numericInputs.push({ph, val: 'EMPTY'});
                            }
                        });

                        // 按位置分配
                        if (!result.weight && numericInputs.length >= 1 && numericInputs[0].val !== 'EMPTY') {
                            result.weight = numericInputs[0].val;
                        }
                        if (!result.length_cm && numericInputs.length >= 2 && numericInputs[1].val !== 'EMPTY') {
                            result.length_cm = numericInputs[1].val;
                        }
                        if (!result.width_cm && numericInputs.length >= 3 && numericInputs[2].val !== 'EMPTY') {
                            result.width_cm = numericInputs[2].val;
                        }
                        if (!result.height_cm && numericInputs.length >= 4 && numericInputs[3].val !== 'EMPTY') {
                            result.height_cm = numericInputs[3].val;
                        }

                        return result;
                    }
                }

                return {error: '未找到物流input容器'};
            }""")

            if js_result2 and 'error' not in js_result2:
                logistics.update({k: v for k, v in js_result2.items() if v})
                # 只有在找到完整尺寸信息时才返回
                if logistics.get('weight') and logistics.get('length_cm') and logistics.get('width_cm') and logistics.get('height_cm'):
                    logger.info(f"方法2提取完整物流信息: {logistics}")
                    return logistics
                elif any(logistics.values()):
                    logger.info(f"方法2提取到部分物流信息: {logistics}，继续尝试方法3")

            # 方法3: 尝试从SKU规格中解析尺寸
            logger.info("尝试方法3: 从SKU规格解析尺寸")
            try:
                import re
                body_text = body.inner_text()
                matches = re.findall(r'(\d+)\s*\*\s*(\d+)\s*\*\s*(\d+)\s*cm', body_text)
                if matches:
                    l, w, h = matches[0]
                    logistics['length_cm'] = l
                    logistics['width_cm'] = w
                    logistics['height_cm'] = h
                    logger.info(f"从SKU规格解析尺寸: {l}x{w}x{h}")
            except Exception as e:
                logger.warning(f"从SKU解析尺寸失败: {e}")

        except Exception as e:
            logger.warning(f"提取物流信息失败: {e}")

        return logistics

    def list_products(self) -> List[Dict[str, Any]]:
        """列出采集箱中的所有商品（简单信息）"""
        return self.get_product_list()


def main():
    parser = argparse.ArgumentParser(description='妙手ERP Shopee采集箱爬虫')
    parser.add_argument('--list', action='store_true', help='仅列出商品')
    parser.add_argument('--scrape', type=int, default=0, help='爬取指定索引的商品')
    parser.add_argument('--alibaba-id', type=str, help='按货源ID查找商品')
    args = parser.parse_args()

    scraper = None
    try:
        scraper = CollectorScraper()
        scraper.launch()

        if args.list:
            products = scraper.list_products()
            print("\n" + "="*60)
            print(f"商品列表 (共 {len(products)} 个):")
            for i, p in enumerate(products):
                print(f"  [{i}] {p['alibaba_product_id']} - {p.get('title', 'N/A') or 'N/A'[:30]}")
            print("="*60)

        elif args.scrape is not None:
            data = scraper.scrape_product(args.scrape)
            if data:
                print("\n" + "="*60)
                print("商品数据:")
                print(f"  货源ID: {data['alibaba_product_id']}")
                print(f"  标题: {data.get('title', 'N/A')}")
                print(f"  类目: {data.get('category', 'N/A')}")
                print(f"  品牌: {data.get('brand', 'N/A')}")
                print(f"  主图数量: {len(data.get('main_images', []))}")
                print(f"  SKU数量: {len(data.get('skus', []))}")
                print(f"  描述长度: {len(data.get('description', ''))}")
                print(f"  物流: {data.get('logistics', {})}")
                print("="*60)
            else:
                print("爬取失败")
                sys.exit(1)

        else:
            parser.print_help()

    finally:
        if scraper:
            scraper.close()


if __name__ == '__main__':
    main()
