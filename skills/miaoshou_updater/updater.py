#!/usr/bin/env python3
"""
miaoshou_updater.updater

Playwright-based updater for Miaoshou ERP Shopee collect-box items.
"""
import argparse
from contextlib import contextmanager
from io import BytesIO
import json
import os
import sys
import tempfile
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import requests
from PIL import Image

WORKSPACE = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = WORKSPACE / 'scripts'
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    import db
except ImportError:
    db = None

try:
    import psycopg2
except ImportError:
    psycopg2 = None

from multisite_config import normalize_site_context

try:
    from logger import setup_logger
except ImportError:
    def setup_logger(name: str):
        class _FallbackLogger:
            def info(self, msg: str):
                print(f'[INFO] {msg}')

            def warning(self, msg: str):
                print(f'[WARN] {msg}')

            warn = warning

            def error(self, msg: str):
                print(f'[ERROR] {msg}')

            def debug(self, msg: str):
                print(f'[DEBUG] {msg}')

        return _FallbackLogger()


logger = setup_logger('miaoshou-updater')

MIAOSHOU_BASE_URL = 'https://erp.91miaoshou.com'
SHOPEE_COLLECT_URL = f'{MIAOSHOU_BASE_URL}/shopee/collect_box/items'
TMP_DIR = WORKSPACE / 'logs' / 'miaoshou_updater_debug'
TMP_DIR.mkdir(parents=True, exist_ok=True)

COOKIE_CANDIDATES = [
    WORKSPACE / 'skills' / 'miaoshou-updater' / 'miaoshou_cookies.json',
    WORKSPACE / 'skills' / 'miaoshou-collector' / 'miaoshou_cookies.json',
    WORKSPACE / 'config' / 'miaoshou_cookies.json',
    Path('/home/ubuntu/work/config/miaoshou_cookies.json'),
    Path('/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json'),
]

PRODUCT_FIXTURE_CANDIDATES = [
    WORKSPACE / 'skills' / 'miaoshou-api-publisher' / 'sample-debug-product.json',
]

STORAGE_STATE_CANDIDATES = [
    WORKSPACE / 'config' / 'miaoshou_storage_state.json',
]

DEFAULT_CATEGORY_PATH = ['家居生活', '居家收纳', '收纳盒']
VIDEO_VALIDATION_ERROR_FRAGMENTS = (
    '视频像素不超过1280×1280px',
    '视频时长10s~60s',
    '大小必须小于30M',
    '格式为MP4',
)
DB_CONFIG = {
    'host': 'localhost',
    'database': 'ecommerce_data',
    'user': 'superuser',
    'password': 'Admin123!',
}


class MiaoshouUpdater:
    def __init__(self, cookies_file: Optional[Path] = None, headless: bool = True, cdp_url: Optional[str] = None, storage_state_file: Optional[Path] = None):
        self.cookies_file = Path(cookies_file) if cookies_file else self._detect_cookies_file()
        self.headless = headless
        self.cdp_url = cdp_url or os.environ.get('MIAOSHOU_CDP_URL')
        self.disable_product_video = os.environ.get('MIAOSHOU_DISABLE_PRODUCT_VIDEO', '1').strip().lower() not in {'0', 'false', 'no', 'off'}
        self.storage_state_file = Path(storage_state_file) if storage_state_file else self._detect_storage_state_file()
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._owns_browser = True
        self._temp_dirs: List[Path] = []
        self.cookies = self._load_cookies() if self.cookies_file else []
        self.storage_state = self._load_storage_state() if self.storage_state_file else None

    def _detect_cookies_file(self) -> Optional[Path]:
        for candidate in COOKIE_CANDIDATES:
            if candidate.exists():
                return candidate
        return None

    def _detect_storage_state_file(self) -> Optional[Path]:
        env_path = os.environ.get('MIAOSHOU_STORAGE_STATE_FILE')
        if env_path:
            candidate = Path(env_path)
            if candidate.exists():
                return candidate
        for candidate in STORAGE_STATE_CANDIDATES:
            if candidate.exists():
                return candidate
        return None

    def _load_cookies(self) -> List[Dict[str, Any]]:
        if not self.cookies_file:
            raise FileNotFoundError('未找到妙手 Cookies 文件')
        with open(self.cookies_file, 'r', encoding='utf-8') as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, list) else payload.get('cookies', [])

    def _load_storage_state(self) -> Optional[Dict[str, Any]]:
        if not self.storage_state_file:
            return None
        with open(self.storage_state_file, 'r', encoding='utf-8') as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            return None
        return payload

    def _install_storage_init_script(self):
        if not self.context or not self.storage_state:
            return

        payload = json.dumps(self.storage_state, ensure_ascii=False)
        script = """
                (() => {
                const payload = __PAYLOAD__;
                const targetOrigin = 'https://erp.91miaoshou.com';
                const currentOrigin = window.location.origin;
                if (currentOrigin !== targetOrigin) {
                    return;
                }

                const applyStorage = (storage, values) => {
                    if (!storage || !values) return;
                    for (const [key, value] of Object.entries(values)) {
                        try {
                            storage.setItem(key, value == null ? '' : String(value));
                        } catch (e) {
                        }
                    }
                };

                applyStorage(window.localStorage, payload.localStorage || {});
                applyStorage(window.sessionStorage, payload.sessionStorage || {});
                })();
            """.replace('__PAYLOAD__', payload)
        self.context.add_init_script(
            script=script,
        )

    def _load_product_fixture(self, identifier: Any) -> Optional[Dict[str, Any]]:
        identifier = str(identifier)
        for candidate in PRODUCT_FIXTURE_CANDIDATES:
            if not candidate.exists():
                continue
            try:
                with open(candidate, 'r', encoding='utf-8') as handle:
                    payload = json.load(handle)
            except Exception as exc:
                logger.warning(f'读取商品样例失败: {candidate} | {exc}')
                continue

            items = payload if isinstance(payload, list) else [payload]
            for raw in items:
                if not isinstance(raw, dict):
                    continue
                aliases = {
                    str(raw.get('货源ID') or ''),
                    str(raw.get('alibaba_product_id') or ''),
                    str(raw.get('product_id') or ''),
                    str(raw.get('sourceItemId') or ''),
                    str(raw.get('主货号') or ''),
                    str(raw.get('product_id_new') or ''),
                }
                if identifier not in aliases:
                    continue

                package_size = raw.get('包裹尺寸') or {}
                weight_kg = self._safe_float(
                    raw.get('包装重量(kg)') or raw.get('package_weight_kg') or raw.get('weight_kg'),
                    0.0,
                )
                return {
                    'id': None,
                    'product_id': raw.get('product_id') or raw.get('货源ID') or raw.get('sourceItemId'),
                    'alibaba_product_id': raw.get('alibaba_product_id') or raw.get('货源ID') or raw.get('sourceItemId'),
                    'title': raw.get('title') or raw.get('产品标题') or '',
                    'description': raw.get('description') or raw.get('简易描述') or '',
                    'category': raw.get('category') or raw.get('类目') or '',
                    'main_images': raw.get('main_images') or raw.get('主图URL列表') or [],
                    'optimized_title': raw.get('optimized_title') or raw.get('产品标题') or raw.get('title') or '',
                    'optimized_description': raw.get('optimized_description') or raw.get('简易描述') or raw.get('description') or '',
                    'status': raw.get('status') or 'fixture',
                    'product_id_new': raw.get('product_id_new') or raw.get('主货号') or '',
                    'package_weight': weight_kg * 1000 if weight_kg else 0,
                    'package_weight_kg': weight_kg,
                    'package_length': raw.get('package_length') or package_size.get('长度(cm)') or package_size.get('length') or 0,
                    'package_width': raw.get('package_width') or package_size.get('宽度(cm)') or package_size.get('width') or 0,
                    'package_height': raw.get('package_height') or package_size.get('高度(cm)') or package_size.get('height') or 0,
                    'fixture_source': str(candidate),
                }
        return None

    def _build_cookies(self) -> List[Dict[str, Any]]:
        result = []
        for cookie in self.cookies:
            result.append({
                'name': cookie['name'],
                'value': cookie['value'],
                'domain': cookie.get('domain', '.91miaoshou.com'),
                'path': cookie.get('path', '/'),
                'secure': cookie.get('secure', False),
                'httpOnly': cookie.get('httpOnly', False),
            })
        return result

    def _ensure_db(self):
        if db is None and psycopg2 is None:
            raise RuntimeError('db 模块和 psycopg2 都不可用，当前环境不能执行数据库查询')

    @contextmanager
    def _get_cursor(self):
        self._ensure_db()
        if db is not None:
            with db.get_cursor() as cur:
                yield cur
            return

        conn = psycopg2.connect(**DB_CONFIG)
        try:
            cur = conn.cursor()
            try:
                yield cur
                conn.commit()
            finally:
                cur.close()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_page(self):
        if not self.page:
            raise RuntimeError('浏览器未启动，请先调用 launch()')

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        if value in (None, ''):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        if value in (None, ''):
            return default
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_list(value: Any) -> List[Any]:
        if value in (None, ''):
            return []
        if isinstance(value, list):
            return [item for item in value if item not in (None, '')]
        if isinstance(value, tuple):
            return [item for item in value if item not in (None, '')]
        return [value]

    @staticmethod
    def _normalize_main_image_url(image: Any) -> str:
        if isinstance(image, dict):
            for key in ['url', 'src', 'image_url', 'media_url']:
                candidate = str(image.get(key) or '').strip()
                if candidate:
                    return candidate
            return ''
        return str(image or '').strip()

    @staticmethod
    def _is_webp_image_url(image_url: str) -> bool:
        normalized_url = str(image_url or '').strip().lower()
        if not normalized_url:
            return False
        return urllib.parse.urlparse(normalized_url).path.endswith('.webp') or '.webp?' in normalized_url

    def _create_temp_dir(self, prefix: str) -> Path:
        temp_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=str(TMP_DIR)))
        self._temp_dirs.append(temp_dir)
        return temp_dir

    def _download_and_prepare_image_file(self, image_url: str, target_dir: Path, index: int) -> Optional[Path]:
        normalized_url = self._normalize_main_image_url(image_url)
        if not normalized_url:
            return None

        response = requests.get(
            normalized_url,
            timeout=30,
            headers={'User-Agent': 'Mozilla/5.0 GitHub-Copilot MiaoshouUpdater'},
        )
        response.raise_for_status()
        image_bytes = response.content
        parsed = urllib.parse.urlparse(normalized_url)
        lower_path = parsed.path.lower()
        content_type = (response.headers.get('content-type') or '').lower()
        looks_like_webp = lower_path.endswith('.webp') or 'image/webp' in content_type

        if looks_like_webp:
            with Image.open(BytesIO(image_bytes)) as image:
                has_alpha = image.mode in {'RGBA', 'LA'} or ('transparency' in image.info)
                converted = image.convert('RGBA' if has_alpha else 'RGB')
                suffix = '.png' if has_alpha else '.jpg'
                output_path = target_dir / f'main_{index:02d}{suffix}'
                save_kwargs = {} if has_alpha else {'quality': 92}
                converted.save(output_path, format='PNG' if has_alpha else 'JPEG', **save_kwargs)
            return output_path

        suffix = Path(lower_path).suffix.lower()
        if suffix not in {'.jpg', '.jpeg', '.png'}:
            with Image.open(BytesIO(image_bytes)) as image:
                has_alpha = image.mode in {'RGBA', 'LA'} or ('transparency' in image.info)
                converted = image.convert('RGBA' if has_alpha else 'RGB')
                suffix = '.png' if has_alpha else '.jpg'
                output_path = target_dir / f'main_{index:02d}{suffix}'
                save_kwargs = {} if has_alpha else {'quality': 92}
                converted.save(output_path, format='PNG' if has_alpha else 'JPEG', **save_kwargs)
            return output_path

        output_path = target_dir / f'main_{index:02d}{suffix}'
        output_path.write_bytes(image_bytes)
        return output_path

    def _open_main_image_local_upload(self, dialog):
        upload_button = dialog.locator('button.J_pictureListUpload').first
        if upload_button.count() == 0:
            return None

        upload_button.click()
        popover_upload = self.page.locator('.el-popover.el-popper .el-upload.el-upload--text input[name="uploadImgFile"]').last
        try:
            popover_upload.wait_for(state='attached', timeout=5000)
        except Exception:
            return None
        return popover_upload

    def _read_main_image_count(self, dialog) -> Optional[int]:
        try:
            count = dialog.evaluate(
                r"""(root) => {
                    const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                    const nodes = Array.from(root.querySelectorAll('*'));
                    for (const node of nodes) {
                        const text = normalize(node.innerText || '');
                        if (!text.includes('产品图片') || text.includes('SKU图片') || !text.includes('已选')) continue;
                        const match = text.match(/产品图片\s*[（(]?已选\s*(\d+)\s*张/);
                        if (match) return Number(match[1]);
                    }
                    return null;
                }"""
            )
            return int(count) if count is not None else None
        except Exception:
            return None

    def _clear_main_images_if_present(self, dialog) -> bool:
        try:
            select_button = dialog.get_by_text('选中前9张', exact=False).first
            delete_button = dialog.locator('button.J_pictureListBatchDelete').first
            if select_button.count() == 0 or delete_button.count() == 0:
                return False

            select_button.click()
            time.sleep(0.3)
            delete_button.click()

            deadline = time.time() + 10.0
            while time.time() < deadline:
                current_count = self._read_main_image_count(dialog)
                if current_count in (None, 0):
                    return True
                time.sleep(0.5)
            return False
        except Exception:
            return False

    def _fill_main_images(self, dialog, product: Dict[str, Any]) -> bool:
        image_urls = [
            self._normalize_main_image_url(image)
            for image in self._normalize_list(product.get('main_images'))
        ]
        image_urls = [url for url in image_urls if url][:9]
        if not image_urls:
            logger.warning('商品缺少主图 URL，跳过产品主图上传')
            return False

        switched = self._open_tab(dialog, '产品图片')
        if switched:
            time.sleep(0.8)

        try:
            existing_count = self._read_main_image_count(dialog)
            if existing_count and existing_count > 0:
                logger.info(f'产品图片区域已有主图，跳过上传: count={existing_count}')
                return True

            upload_input = self._open_main_image_local_upload(dialog)
            if upload_input is None or upload_input.count() == 0:
                logger.warning('未定位到产品图片 -> 本地上传控件')
                return False

            temp_dir = self._create_temp_dir('main_images_')
            prepared_files: List[Path] = []
            for index, image_url in enumerate(image_urls, start=1):
                try:
                    local_path = self._download_and_prepare_image_file(image_url, temp_dir, index)
                except Exception as exc:
                    logger.warning(f'主图下载或转换失败: {image_url} | {exc}')
                    continue
                if local_path:
                    prepared_files.append(local_path)

            if not prepared_files:
                logger.warning('未能准备任何可上传的产品主图文件')
                return False

            upload_input.set_input_files([str(path) for path in prepared_files])

            expected_count = min(len(prepared_files), 9)
            deadline = time.time() + 30.0
            while time.time() < deadline:
                current_count = self._read_main_image_count(dialog)
                if current_count is not None and current_count >= expected_count:
                    logger.info(f'产品主图上传成功: count={current_count}')
                    return True
                time.sleep(0.5)

            logger.warning(f'产品主图上传后未观察到预期数量: expected={expected_count}, actual={self._read_main_image_count(dialog)}')
            return False
        finally:
            if switched:
                self._open_tab(dialog, '基本信息')
                time.sleep(0.5)

    def _resolve_cdp_context_page(self):
        if not self.browser:
            raise RuntimeError('CDP 浏览器连接未建立')

        contexts = self.browser.contexts
        if contexts:
            self.context = contexts[0]
        else:
            self.context = self.browser.new_context(viewport={'width': 1920, 'height': 1080})

        pages = self.context.pages
        if pages:
            self.page = pages[0]
        else:
            self.page = self.context.new_page()

        self.page.set_default_timeout(30000)

    def launch(self):
        from playwright.sync_api import sync_playwright

        self.playwright = sync_playwright().start()
        if self.cdp_url:
            self.browser = self.playwright.chromium.connect_over_cdp(self.cdp_url)
            self._owns_browser = False
            self._resolve_cdp_context_page()
            self._install_storage_init_script()
            logger.info(f'已连接到现有 Chrome 会话: {self.cdp_url}')
            return True

        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
        )
        self._owns_browser = True
        self.context = self.browser.new_context(viewport={'width': 1920, 'height': 1080})
        self._install_storage_init_script()
        if self.cookies:
            self.context.add_cookies(self._build_cookies())
        self.page = self.context.new_page()
        self.page.set_default_timeout(30000)
        logger.info('浏览器启动成功')
        return True

    def close(self):
        try:
            if self.page and self._owns_browser:
                self.page.close()
            if self.context and self._owns_browser:
                self.context.close()
            if self.browser and self._owns_browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        finally:
            for temp_dir in self._temp_dirs:
                try:
                    for file_path in sorted(temp_dir.glob('**/*'), reverse=True):
                        if file_path.is_file():
                            file_path.unlink(missing_ok=True)
                        elif file_path.is_dir():
                            file_path.rmdir()
                    temp_dir.rmdir()
                except Exception:
                    pass
            self._temp_dirs = []
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
            self._owns_browser = True
            logger.info('浏览器已关闭')

    def screenshot(self, name: str) -> Optional[Path]:
        self._ensure_page()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = TMP_DIR / f'{name}_{timestamp}.png'
        self.page.screenshot(path=str(file_path), full_page=True)
        logger.info(f'截图: {file_path}')
        return file_path

    def get_optimized_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        products: List[Dict[str, Any]] = []
        with self._get_cursor() as cur:
            cur.execute(
                """
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
                """,
                (limit,),
            )
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
                    'product_id_new': row[10],
                })
        return products

    def get_skus(self, product_db_id: int) -> List[Dict[str, Any]]:
        skus: List[Dict[str, Any]] = []
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT sku_name, price, stock, package_weight,
                       package_length, package_width, package_height
                FROM product_skus
                WHERE product_id = %s
                ORDER BY id ASC
                """,
                (product_db_id,),
            )
            for row in cur.fetchall():
                skus.append({
                    'sku_name': row[0],
                    'price': row[1],
                    'stock': row[2],
                    'package_weight': row[3],
                    'package_length': row[4],
                    'package_width': row[5],
                    'package_height': row[6],
                })
        return skus

    def update_product_status(self, product_id: int, status: str):
        with self._get_cursor() as cur:
            cur.execute(
                """
                UPDATE products
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (status, product_id),
            )

    def _load_site_listing(self, product_id: int, site_context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        normalized_context = normalize_site_context(site_context or {})
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT
                    site_code,
                    shop_code,
                    listing_title,
                    listing_description,
                    short_description,
                    status,
                    publish_status,
                    listing_language_snapshot,
                    content_policy_code,
                    shipping_profile_code,
                    erp_profile_code,
                    category_profile_code,
                    suggested_price,
                    estimated_profit_local,
                    profit_rate,
                    currency
                FROM site_listings
                WHERE product_id = %s
                  AND COALESCE(site_code, 'shopee_tw') = %s
                  AND COALESCE(shop_code, 'default') = %s
                  AND is_deleted = 0
                  AND is_current = TRUE
                ORDER BY updated_at DESC NULLS LAST, id DESC
                LIMIT 1
                """,
                (
                    product_id,
                    normalized_context.get('site_code') or 'shopee_tw',
                    normalized_context.get('shop_code') or 'default',
                ),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            'site_code': row[0],
            'shop_code': row[1],
            'listing_title': row[2],
            'listing_description': row[3],
            'short_description': row[4],
            'status': row[5],
            'publish_status': row[6],
            'listing_language_snapshot': row[7],
            'content_policy_code': row[8],
            'shipping_profile_code': row[9],
            'erp_profile_code': row[10],
            'category_profile_code': row[11],
            'suggested_price': row[12],
            'estimated_profit_local': row[13],
            'profit_rate': row[14],
            'currency': row[15],
        }

    def _update_site_listing_status(self, product: Dict[str, Any], status: str, publish_status: Optional[str] = None):
        if not product.get('id'):
            return
        site_context = normalize_site_context(product)
        with self._get_cursor() as cur:
            cur.execute(
                """
                UPDATE site_listings
                SET status = %s,
                    publish_status = COALESCE(%s, publish_status),
                    updated_at = CURRENT_TIMESTAMP,
                    last_synced_at = CURRENT_TIMESTAMP,
                    is_deleted = 0
                WHERE product_id = %s
                  AND COALESCE(site_code, 'shopee_tw') = %s
                  AND COALESCE(shop_code, 'default') = %s
                  AND is_current = TRUE
                  AND is_deleted = 0
                """,
                (
                    status,
                    publish_status,
                    product['id'],
                    site_context.get('site_code') or 'shopee_tw',
                    site_context.get('shop_code') or 'default',
                ),
            )

    def _load_product_by_identifier(self, identifier: Any) -> Dict[str, Any]:
        try:
            with self._get_cursor() as cur:
                cur.execute(
                    """
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
                    """,
                    (str(identifier), str(identifier), str(identifier), str(identifier)),
                )
                row = cur.fetchone()
        except Exception as exc:
            fixture_product = self._load_product_fixture(identifier)
            if fixture_product:
                logger.warning(f'数据库不可用，改用样例商品数据: {fixture_product.get("fixture_source")} | {exc}')
                return fixture_product
            raise RuntimeError(f'数据库连接失败，且未找到可用样例数据: {exc}') from exc

        if not row:
            fixture_product = self._load_product_fixture(identifier)
            if fixture_product:
                logger.warning(f'数据库未找到商品，改用样例商品数据: {fixture_product.get("fixture_source")}')
                return fixture_product
            raise ValueError(f'未找到商品: {identifier}')

        return {
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
            'product_id_new': row[10],
        }

    def _normalize_product_input(self, product: Any) -> Dict[str, Any]:
        if isinstance(product, dict):
            if product.get('id') or product.get('alibaba_product_id') or product.get('product_id_new'):
                normalized = dict(product)
                needs_db_hydration = any(
                    not normalized.get(field)
                    for field in [
                        'id',
                        'title',
                        'description',
                        'optimized_title',
                        'optimized_description',
                        'category',
                        'product_id_new',
                        'package_weight',
                        'package_length',
                        'package_width',
                        'package_height',
                    ]
                )
                if needs_db_hydration:
                    identifier = (
                        normalized.get('id')
                        or normalized.get('alibaba_product_id')
                        or normalized.get('product_id_new')
                        or normalized.get('product_id')
                    )
                    if identifier:
                        loaded = self._load_product_by_identifier(identifier)
                        loaded.update({key: value for key, value in normalized.items() if value not in (None, '', [], {})})
                        return loaded
                return normalized
            identifier = product.get('product_id')
            if identifier:
                return self._load_product_by_identifier(identifier)
            raise ValueError('product 参数缺少 id / alibaba_product_id / product_id_new / product_id')
        return self._load_product_by_identifier(product)

    def _augment_with_sku_data(self, product: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(product)
        if not result.get('id'):
            identifier = (
                result.get('alibaba_product_id')
                or result.get('product_id_new')
                or result.get('product_id')
            )
            if identifier:
                loaded = self._load_product_by_identifier(identifier)
                loaded.update({key: value for key, value in result.items() if value not in (None, '', [], {})})
                result = loaded

        sku_list = self.get_skus(result['id']) if result.get('id') else []
        result['skus'] = sku_list
        primary_sku = sku_list[0] if sku_list else {}

        result['package_weight'] = result.get('package_weight') or primary_sku.get('package_weight')
        result['package_length'] = result.get('package_length') or primary_sku.get('package_length')
        result['package_width'] = result.get('package_width') or primary_sku.get('package_width')
        result['package_height'] = result.get('package_height') or primary_sku.get('package_height')

        site_listing = self._load_site_listing(result['id'], result) if result.get('id') else None
        if site_listing:
            result['site_listing'] = site_listing
            result['optimized_title'] = site_listing.get('listing_title') or result.get('optimized_title')
            result['optimized_description'] = site_listing.get('listing_description') or result.get('optimized_description')

        if not result.get('optimized_title'):
            result['optimized_title'] = result.get('title', '')
        if not result.get('optimized_description'):
            result['optimized_description'] = result.get('description', '')
        return result

    def _goto_collect_box(self):
        self._ensure_page()
        self.page.goto(SHOPEE_COLLECT_URL, wait_until='domcontentloaded')
        try:
            self.page.wait_for_load_state('networkidle', timeout=5000)
        except Exception:
            pass

        ui_ready = False
        for locator_text in ['Shopee采集箱', '未发布', '货源ID', '搜索']:
            try:
                locator = self.page.get_by_text(locator_text, exact=False).first
                if locator.count() > 0 and locator.is_visible(timeout=2000):
                    ui_ready = True
                    break
            except Exception:
                continue

        if not ui_ready:
            try:
                self.page.locator('body').wait_for(state='visible', timeout=5000)
            except Exception:
                self.screenshot('collect_box_load_timeout')
                raise RuntimeError('采集箱页面加载超时，未观察到关键页面元素')

        self._close_popups()

    def _search_source_item(self, source_item_id: str, timeout: float = 15.0, tab_label: str = '未发布', capture_failure: bool = True) -> bool:
        self._ensure_page()
        self._close_popups()

        try:
            tab_switched = bool(self.page.evaluate(
                r"""(label) => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                    const candidates = Array.from(document.querySelectorAll(
                        '.el-radio-button, .el-radio-button__inner, .el-tabs__item, [role="tab"], [role="radio"], button, span, div'
                    ));
                    const target = candidates.find((node) => {
                        if (!visible(node)) return false;
                        const text = normalize(node.innerText);
                        return text === label || text.startsWith(`${label}(`);
                    });
                    if (!target) return false;
                    target.click();
                    return true;
                }""",
                str(tab_label),
            ))
            if tab_switched:
                time.sleep(0.8)
        except Exception:
            pass

        filled = bool(self.page.evaluate(
            r"""(sourceId) => {
                const visible = (el) => !!el && el.offsetParent !== null;
                const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                const wrappers = Array.from(document.querySelectorAll('.el-form-item, .el-input, .search-item, .filter-item'));

                const findInput = () => {
                    for (const wrapper of wrappers) {
                        if (!visible(wrapper)) continue;
                        const text = normalize(wrapper.innerText);
                        if (!text.includes('货源ID')) continue;
                        const input = wrapper.querySelector('input');
                        if (input && visible(input)) return input;
                    }

                    const inputs = Array.from(document.querySelectorAll('input')).filter((node) => visible(node));
                    for (const input of inputs) {
                        const placeholder = normalize(input.getAttribute('placeholder') || '');
                        const parentText = normalize(input.parentElement?.parentElement?.innerText || input.parentElement?.innerText || '');
                        if (placeholder.includes('多个用逗号分隔') && parentText.includes('货源ID')) {
                            return input;
                        }
                    }
                    return null;
                };

                const input = findInput();
                if (!input) return false;
                input.focus();
                input.value = '';
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.value = String(sourceId);
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }""",
            str(source_item_id),
        ))
        if not filled:
            if capture_failure:
                self.screenshot('source_search_input_not_found')
            raise RuntimeError('未找到货源ID搜索框')

        clicked = self._click_visible_button(['搜索'])
        if not clicked:
            self.page.keyboard.press('Enter')

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                match_state = self.page.evaluate(
                    r"""(payload) => {
                        const sourceId = String(payload.sourceId);
                        const tabLabel = String(payload.tabLabel);
                        const visible = (el) => !!el && el.offsetParent !== null;
                        const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();

                        const activeTab = Array.from(document.querySelectorAll(
                            '.el-radio-button.is-active, .el-tabs__item.is-active, [role="tab"][aria-selected="true"], [role="radio"].is-active'
                        ))
                            .map((node) => normalize(node.innerText))
                            .find(Boolean) || '';

                        const itemNodes = Array.from(document.querySelectorAll(
                            '.vue-recycle-scroller__item-view, .el-table__row, .collect-item, .source-item'
                        )).filter((node) => visible(node));

                        const matchedNode = itemNodes.find((node) => normalize(node.innerText).includes(sourceId));
                        if (matchedNode) {
                            return {state: 'found', activeTab};
                        }

                        const emptyTexts = ['暂无数据', '共0条', '没有数据'];
                        const bodyText = normalize(document.body?.innerText || '');
                        if (emptyTexts.some((text) => bodyText.includes(text))) {
                            return {state: 'empty', activeTab};
                        }

                        if (activeTab && !(activeTab === tabLabel || activeTab.startsWith(`${tabLabel}(`))) {
                            return {state: 'wrong-tab', activeTab};
                        }

                        return {state: 'pending', activeTab};
                    }""",
                    {'sourceId': str(source_item_id), 'tabLabel': str(tab_label)},
                )
            except Exception:
                match_state = {'state': 'pending', 'activeTab': ''}

            if match_state.get('state') == 'found':
                return True
            if match_state.get('state') in {'empty', 'wrong-tab'}:
                break
            time.sleep(0.5)

        if capture_failure:
            self.screenshot('source_search_no_result')
        return False

    def _get_product_publish_state(self, source_item_id: str) -> Dict[str, bool]:
        self._goto_collect_box()
        in_unpublished = self._search_source_item(str(source_item_id), timeout=6.0, tab_label='未发布', capture_failure=False)

        self._goto_collect_box()
        in_published = self._search_source_item(str(source_item_id), timeout=6.0, tab_label='已发布', capture_failure=False)

        return {
            'in_unpublished': in_unpublished,
            'in_published': in_published,
        }

    def _verify_product_published(self, source_item_id: str) -> bool:
        state = self._get_product_publish_state(source_item_id)
        if state['in_unpublished']:
            self.screenshot('publish_still_in_unpublished')
            return False

        if not state['in_published']:
            self.screenshot('publish_not_found_in_published')
            return False

        return True

    def _wait_for_product_published(self, source_item_id: str, timeout: float = 60.0) -> bool:
        deadline = time.time() + timeout
        last_state = {'in_unpublished': False, 'in_published': False}
        while time.time() < deadline:
            last_state = self._get_product_publish_state(source_item_id)
            if not last_state['in_unpublished'] and last_state['in_published']:
                return True
            time.sleep(2.0)

        if last_state['in_unpublished']:
            self.screenshot('publish_still_in_unpublished')
        if not last_state['in_published']:
            self.screenshot('publish_not_found_in_published')
        return False

    def _close_popups(self):
        self._ensure_page()
        for _ in range(5):
            try:
                self.page.evaluate(
                    """() => {
                        const visible = (el) => !!el && el.offsetParent !== null;
                        const closeTexts = ['我知道了', '关闭', '取消', '确 定', '确定'];
                        for (const text of closeTexts) {
                            const buttons = Array.from(document.querySelectorAll('button, span, div'));
                            const node = buttons.find((item) => visible(item) && (item.innerText || '').trim() === text);
                            if (node) {
                                node.click();
                            }
                        }
                        for (const dialog of document.querySelectorAll('.el-dialog')) {
                            if (!visible(dialog)) continue;
                            const title = (dialog.querySelector('.el-dialog__title')?.innerText || '').trim();
                            if (title.includes('查看来源信息') || title.includes('新手') || title.includes('引导')) {
                                const closeBtn = dialog.querySelector('.el-dialog__headerbtn');
                                if (closeBtn) closeBtn.click();
                            }
                        }
                        const jxClose = document.querySelector('button[aria-label="关闭此对话框"]');
                        if (visible(jxClose)) jxClose.click();
                    }"""
                )
                self.page.keyboard.press('Escape')
            except Exception:
                pass
            time.sleep(0.3)

    def _resolve_category_path(self, category_text: Optional[str]) -> Sequence[str]:
        text = (category_text or '').replace(' ', '')
        if '收纳' in text or '收納' in text:
            return DEFAULT_CATEGORY_PATH
        return DEFAULT_CATEGORY_PATH

    def _click_edit_for_source(self, source_item_id: str) -> bool:
        self._ensure_page()
        locator_selectors = [
            f'.jx-pro-virtual-table__row:has-text("{source_item_id}")',
            f'.jx-pro-virtual-table__row-cell:has-text("{source_item_id}")',
            f'tr:has-text("{source_item_id}")',
            f'.el-table__row:has-text("{source_item_id}")',
            f'.el-table__body tr:has-text("{source_item_id}")',
            f'.el-table__body-wrapper tr:has-text("{source_item_id}")',
        ]

        def try_locator_click() -> bool:
            for selector in locator_selectors:
                rows = self.page.locator(selector)
                try:
                    count = rows.count()
                except Exception:
                    count = 0
                for index in range(count):
                    row = rows.nth(index)
                    try:
                        if not row.is_visible(timeout=800):
                            continue
                    except Exception:
                        continue

                    try:
                        row.hover(timeout=800)
                    except Exception:
                        pass

                    action_candidates = [
                        row.locator('button.J_shopeeCollectBoxEdit'),
                        row.locator('.operate-box button.J_shopeeCollectBoxEdit'),
                        row.get_by_text('编辑', exact=True),
                        row.locator('a').filter(has_text='编辑'),
                        row.locator('button').filter(has_text='编辑'),
                        row.locator('span').filter(has_text='编辑'),
                        row.locator('[class*="edit"]'),
                    ]
                    for action in action_candidates:
                        try:
                            if action.count() == 0:
                                continue
                            target = action.first
                            if not target.is_visible(timeout=800):
                                continue
                            target.click(force=True, timeout=1200)
                            if self._wait_for_edit_dialog(timeout=4.0) is not None:
                                return True
                        except Exception:
                            continue
            return False

        for _ in range(4):
            self._close_popups()
            if try_locator_click():
                return True
            clicked = self.page.evaluate(
                    r"""(sourceId) => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const textOf = (el) => (el?.innerText || '').replace(/\s+/g, ' ').trim();
                    const clickNode = (node) => {
                        if (!node || !visible(node)) return false;
                        node.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                        node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                        node.click();
                        return true;
                    };
                    const clickEditInside = (root) => {
                        if (!root) return false;
                        root.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                        root.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                        const explicitEditButton = root.querySelector('button.J_shopeeCollectBoxEdit, .operate-box button.J_shopeeCollectBoxEdit');
                        if (explicitEditButton && visible(explicitEditButton)) {
                            return clickNode(explicitEditButton);
                        }
                        const buttons = Array.from(root.querySelectorAll('a, button, span, div, i'));
                        const target = buttons.find((item) => {
                            const text = textOf(item);
                            const cls = (item.className || '').toString();
                            return visible(item) && (
                                text === '编辑'
                                || text === '修改'
                                || text.includes('编辑')
                                || text.includes('修改')
                                || cls.includes('edit')
                                || cls.includes('bianji')
                            );
                        });
                        if (target) {
                            return clickNode(target);
                        }
                        return false;
                    };
                    const clickFixedRightAction = () => {
                        const virtualRows = Array.from(document.querySelectorAll('.jx-pro-virtual-table__row'))
                            .filter((row) => visible(row));
                        const virtualRow = virtualRows.find((row) => textOf(row).includes(String(sourceId)));
                        if (virtualRow && clickEditInside(virtualRow)) return true;

                        const rowSelectors = [
                            '.el-table__body-wrapper tbody tr.el-table__row',
                            '.el-table__body tbody tr.el-table__row',
                        ];
                        const mainRows = rowSelectors
                            .flatMap((selector) => Array.from(document.querySelectorAll(selector)))
                            .filter((row) => visible(row));

                        const rowIndex = mainRows.findIndex((row) => textOf(row).includes(String(sourceId)));
                        if (rowIndex < 0) return false;

                        const fixedSelectors = [
                            '.el-table__fixed-right .el-table__fixed-body-wrapper tbody tr.el-table__row',
                            '.el-table__fixed-right .el-table__body-wrapper tbody tr.el-table__row',
                            '.el-table__fixed .el-table__fixed-body-wrapper tbody tr.el-table__row',
                        ];
                        const fixedRows = fixedSelectors
                            .flatMap((selector) => Array.from(document.querySelectorAll(selector)))
                            .filter((row) => visible(row));

                        const fixedRow = fixedRows[rowIndex];
                        if (!fixedRow) return false;
                        return clickEditInside(fixedRow);
                    };
                    const rowLike = (node) => {
                        if (!node) return false;
                        const cls = node.className || '';
                        const tag = (node.tagName || '').toLowerCase();
                        return tag === 'tr'
                            || String(cls).includes('el-table__row')
                            || String(cls).includes('jx-pro-virtual-table__row')
                            || String(cls).includes('jx-pro-virtual-table__row-cell')
                            || String(cls).includes('table-row')
                            || String(cls).includes('list-item')
                            || String(cls).includes('item-row');
                    };

                    const nodes = Array.from(document.querySelectorAll('*')).filter((node) => {
                        const text = textOf(node);
                        return visible(node) && (text.includes(`(${String(sourceId)})`) || text.includes(String(sourceId)));
                    });

                    for (const node of nodes) {
                        let current = node;
                        let row = null;
                        for (let depth = 0; depth < 8 && current; depth += 1) {
                            if (rowLike(current)) {
                                row = current;
                                break;
                            }
                            current = current.parentElement;
                        }
                        if (row && clickEditInside(row)) return true;

                        current = node;
                        for (let depth = 0; depth < 8 && current; depth += 1) {
                            if (clickEditInside(current)) return true;
                            current = current.parentElement;
                        }
                    }

                    if (clickFixedRightAction()) return true;

                    const actionButtons = Array.from(document.querySelectorAll('a, button, span, div')).filter((node) => {
                        const text = textOf(node);
                        return visible(node) && (text === '编辑' || text === '修改');
                    });
                    if (actionButtons.length === 1) {
                        return clickNode(actionButtons[0]);
                    }

                    const loneButtons = Array.from(document.querySelectorAll('a, button')).filter((button) => {
                        const text = textOf(button);
                        return visible(button) && (text === '编辑' || text === '修改');
                    });
                    if (loneButtons.length === 1) {
                        return clickNode(loneButtons[0]);
                    }
                    return false;
                }""",
                str(source_item_id),
            )
            if clicked:
                if self._wait_for_edit_dialog(timeout=4.0) is not None:
                    return True
            self.page.mouse.wheel(0, 800)
            time.sleep(0.6)
        return False

    def _wait_for_edit_dialog(self, timeout: float = 12.0):
        self._ensure_page()
        deadline = time.time() + timeout
        while time.time() < deadline:
            for selector in ['.el-dialog', '.jx-dialog', '.el-dialog__wrapper', '.ant-modal']:
                dialogs = self.page.locator(selector)
                if dialogs.count() == 0:
                    continue
                for index in range(dialogs.count()):
                    dialog = dialogs.nth(index)
                    try:
                        if not dialog.is_visible():
                            continue
                        text = dialog.inner_text(timeout=500)
                        if '基本信息' in text or '产品标题' in text or '标题不能为空' in text or '简易描述' in text:
                            return dialog
                    except Exception:
                        continue

            title_input = self.page.locator('input[placeholder="标题不能为空"]').first
            textarea = self.page.locator('textarea').first
            try:
                if title_input.count() > 0 and title_input.is_visible() and textarea.count() > 0 and textarea.is_visible():
                    container = self.page.locator('.el-dialog:has(input[placeholder="标题不能为空"])').first
                    if container.count() > 0:
                        return container
            except Exception:
                pass
            time.sleep(0.3)
        return None

    def _fill_basic_fields(self, dialog, product: Dict[str, Any]):
        title = product.get('optimized_title') or product.get('title') or ''
        description = product.get('optimized_description') or product.get('description') or ''
        dialog.locator('input[placeholder="标题不能为空"]').first.fill(title)
        dialog.locator('.el-form-item textarea').first.fill(description)

    def _dispatch_input_value(self, dialog, item_index: int, value: Any, input_index: int = 0):
        dialog.evaluate(
            """({ itemIndex, value, inputIndex }) => {
                const root = document;
                let items = root.querySelectorAll('.el-dialog__body .el-form-item');
                if (!items.length) {
                    items = root.querySelectorAll('.el-form-item');
                }
                const item = items[itemIndex];
                if (!item) return false;
                const inputs = item.querySelectorAll('input, textarea');
                const input = inputs[inputIndex];
                if (!input) return false;
                input.focus();
                input.value = value == null ? '' : String(value);
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }""",
            {'itemIndex': item_index, 'value': value, 'inputIndex': input_index},
        )

    def _dispatch_input_value_by_label(self, dialog, label_keywords: Sequence[str], value: Any, input_index: int = 0) -> bool:
        try:
            return bool(dialog.evaluate(
                r"""(root, { labels, value, inputIndex }) => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                    let items = Array.from(root.querySelectorAll('.el-dialog__body .el-form-item'));
                    if (!items.length) {
                        items = Array.from(root.querySelectorAll('.el-form-item'));
                    }
                    const target = items.find((item) => {
                        if (!visible(item)) return false;
                        const text = normalize(item.innerText || '');
                        return labels.every((label) => text.includes(label));
                    });
                    if (!target) return false;
                    const inputs = Array.from(target.querySelectorAll('input, textarea')).filter((node) => visible(node));
                    const input = inputs[inputIndex];
                    if (!input) return false;
                    input.focus();
                    input.value = value == null ? '' : String(value);
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    input.dispatchEvent(new Event('blur', { bubbles: true }));
                    return true;
                }""",
                {'labels': list(label_keywords), 'value': value, 'inputIndex': input_index},
            ))
        except Exception:
            return False

    def _read_input_values_by_label(self, dialog, label_keywords: Sequence[str]) -> List[str]:
        try:
            values = dialog.evaluate(
                r"""(root, { labels }) => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                    let items = Array.from(root.querySelectorAll('.el-dialog__body .el-form-item'));
                    if (!items.length) {
                        items = Array.from(root.querySelectorAll('.el-form-item'));
                    }
                    const target = items.find((item) => {
                        if (!visible(item)) return false;
                        const text = normalize(item.innerText || '');
                        return labels.every((label) => text.includes(label));
                    });
                    if (!target) return [];
                    return Array.from(target.querySelectorAll('input, textarea'))
                        .filter((node) => visible(node))
                        .map((node) => (node.value || '').trim());
                }""",
                {'labels': list(label_keywords)},
            )
            return values or []
        except Exception:
            return []

    def _get_logistics_pane(self, dialog):
        try:
            pane = dialog.locator('.scroll-menu-pane').filter(has_text='物流信息').last
            if pane.count() > 0 and pane.is_visible():
                return pane
        except Exception:
            pass
        return dialog

    def _set_input_locator_value(self, input_locator, value: Any) -> bool:
        try:
            if input_locator.count() == 0 or not input_locator.first.is_visible():
                return False
            target = input_locator.first
            string_value = '' if value is None else str(value)
            target.scroll_into_view_if_needed()
            target.click(force=True)
            target.fill('')
            target.evaluate(
                """(node, nextValue) => {
                    const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
                    descriptor?.set?.call(node, nextValue);
                    node.dispatchEvent(new Event('input', { bubbles: true }));
                    node.dispatchEvent(new Event('change', { bubbles: true }));
                    node.dispatchEvent(new Event('blur', { bubbles: true }));
                }""",
                string_value,
            )
            return True
        except Exception:
            return False

    @staticmethod
    def _format_decimal_text(value: Any) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        return f'{number:.2f}'

    @staticmethod
    def _numeric_texts_match(expected: Sequence[str], actual: Sequence[str]) -> bool:
        if len(actual) < len(expected):
            return False
        try:
            for expected_value, actual_value in zip(expected, actual):
                expected_number = float(expected_value)
                actual_number = float(actual_value)
                if abs(expected_number - actual_number) <= 0.011:
                    continue
                if int(expected_number) == int(actual_number):
                    continue
                return False
            return True
        except (TypeError, ValueError):
            return list(expected) == list(actual)

    def _open_tab(self, dialog, tab_label: str) -> bool:
        try:
            return bool(dialog.evaluate(
                r"""(label) => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const normalize = (text) => (text || '').replace(/\s+/g, '').trim();
                    const targets = Array.from(document.querySelectorAll('.el-tabs__item, [role="tab"], .tab-item, .tabs-item'));
                    const target = targets.find((node) => visible(node) && normalize(node.innerText || '').includes(normalize(label)));
                    if (!target) return false;
                    target.click();
                    return true;
                }""",
                tab_label,
            ))
        except Exception:
            return False

    def _fill_item_num(self, dialog, product: Dict[str, Any]):
        item_num = product.get('product_id_new') or ''
        if item_num:
            filled = self._dispatch_input_value_by_label(dialog, ['主货号'], item_num)
            if not filled:
                self._dispatch_input_value(dialog, 3, item_num)

            values = self._read_input_values_by_label(dialog, ['主货号'])
            if item_num not in values:
                logger.warning(f'主货号写入后未回读到目标值: expected={item_num}, actual={values}')
                self.screenshot('item_num_not_written')

    def _fill_weight_dimensions(self, dialog, product: Dict[str, Any]):
        weight_g = self._safe_float(product.get('package_weight'), 0.0)
        weight_kg = round(weight_g / 1000, 3) if weight_g else self._safe_float(product.get('package_weight_kg'), 0.0)
        if weight_kg <= 0:
            weight_kg = 0.01
        elif 0 < weight_kg < 0.01:
            weight_kg = 0.01
        length = product.get('package_length') or 30
        width = product.get('package_width') or 20
        height = product.get('package_height') or 10
        expected = [self._format_decimal_text(length), self._format_decimal_text(width), self._format_decimal_text(height)]

        switched = self._open_tab(dialog, '物流信息')
        if switched:
            time.sleep(0.8)

        logistics_pane = self._get_logistics_pane(dialog)

        if weight_kg:
            filled_weight = self._set_input_locator_value(
                logistics_pane.locator('.package-weight-input input, input[placeholder=""]').first,
                weight_kg,
            )
            if not filled_weight:
                filled_weight = self._dispatch_input_value_by_label(dialog, ['包裹重量'], weight_kg)
            if not filled_weight:
                self._dispatch_input_value(dialog, 12, weight_kg)

        wrote_dimensions = True
        dimension_locators = [
            logistics_pane.locator('input[placeholder="长"]'),
            logistics_pane.locator('input[placeholder="宽"]'),
            logistics_pane.locator('input[placeholder="高"]'),
        ]
        for locator, value in zip(dimension_locators, expected):
            wrote_dimensions = self._set_input_locator_value(locator, value) and wrote_dimensions

        if not wrote_dimensions:
            wrote_dimensions = self._dispatch_input_value_by_label(dialog, ['包裹尺寸'], expected[0], 0) and wrote_dimensions
            wrote_dimensions = self._dispatch_input_value_by_label(dialog, ['包裹尺寸'], expected[1], 1) and wrote_dimensions
            wrote_dimensions = self._dispatch_input_value_by_label(dialog, ['包裹尺寸'], expected[2], 2) and wrote_dimensions
        if not wrote_dimensions:
            self._dispatch_input_value(dialog, 13, length, 0)
            self._dispatch_input_value(dialog, 13, width, 1)
            self._dispatch_input_value(dialog, 13, height, 2)

        values = []
        try:
            values = [
                (dimension_locators[0].first.input_value() or '').strip(),
                (dimension_locators[1].first.input_value() or '').strip(),
                (dimension_locators[2].first.input_value() or '').strip(),
            ]
        except Exception:
            values = self._read_input_values_by_label(dialog, ['包裹尺寸'])

        if not self._numeric_texts_match(expected, values[:3]):
            logger.warning(f'包裹尺寸写入后未回读到目标值: expected={expected}, actual={values}')
            self.screenshot('package_dimensions_not_written')

        if switched:
            self._open_tab(dialog, '基本信息')
            time.sleep(0.5)

    def _clear_product_video_if_present(self, dialog) -> bool:
        switched = self._open_tab(dialog, '产品视频')
        if switched:
            time.sleep(0.8)

        try:
            cleared = bool(dialog.evaluate(
                r"""(root) => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                    const compact = (text) => normalize(text).replace(/\s+/g, '');
                    const click = (node) => {
                        if (!node || !visible(node)) return false;
                        node.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                        node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                        node.click();
                        return true;
                    };

                    const scope = Array.from(root.querySelectorAll('.upload-video-container, .info-item, .scroll-menu-pane, .el-form-item'))
                        .find((node) => {
                            if (!visible(node)) return false;
                            const text = compact(node.innerText || '');
                            return text.includes('产品视频') || text.includes('上传视频') || text.includes('mp4');
                        });
                    if (!scope) return false;

                    const explicitDeleteNodes = Array.from(scope.querySelectorAll('button, span, i, svg, .el-icon-close, .icon-close, [aria-label*="删除"], [title*="删除"], [class*="delete"], [class*="remove"], [class*="close"]'))
                        .filter((node) => visible(node))
                        .filter((node) => {
                            const text = compact(node.innerText || node.getAttribute?.('aria-label') || node.getAttribute?.('title') || '');
                            const cls = (node.className || '').toString().toLowerCase();
                            return text.includes('删除')
                                || text.includes('移除')
                                || text.includes('清空')
                                || text.includes('重传')
                                || text.includes('重新上传')
                                || cls.includes('delete')
                                || cls.includes('remove')
                                || cls.includes('close');
                        });

                    let changed = false;
                    for (const node of explicitDeleteNodes) {
                        changed = click(node) || changed;
                    }
                    return changed;
                }"""
            ))
            if cleared:
                logger.info('检测到产品视频区域，已尝试清理已有视频内容')
                time.sleep(0.8)
            return cleared
        except Exception:
            return False
        finally:
            if switched:
                self._open_tab(dialog, '基本信息')
                time.sleep(0.5)

    @staticmethod
    def _extract_video_validation_errors(errors: Sequence[str]) -> List[str]:
        matches = []
        for error in errors:
            normalized = str(error or '').replace(' ', '')
            if any(fragment.replace(' ', '') in normalized for fragment in VIDEO_VALIDATION_ERROR_FRAGMENTS):
                matches.append(str(error))
        return matches

    def _retry_publish_after_video_cleanup(self, dialog, timeout: float = 15.0):
        cleaned = self._clear_product_video_if_present(dialog)
        if cleaned:
            logger.warning('检测到视频校验错误，已清理产品视频并重试保存并发布')
        else:
            logger.warning('检测到视频校验错误，未定位到明确的视频删除控件，仍重试保存并发布')

        if not self._click_save_action(dialog, publish=True):
            return None

        self._resolve_save_warning_message_boxes()
        return self._wait_for_publish_dialog(timeout=timeout)

    def _fill_category(self, dialog, product: Dict[str, Any]):
        category_path = list(self._resolve_category_path(product.get('category')))
        def open_trigger():
            dialog.evaluate(
                """() => {
                    const items = document.querySelectorAll('.el-dialog__body .el-form-item');
                    const item = items[5];
                    const trigger = item?.querySelector('.el-cascader, .el-input, input');
                    if (trigger) trigger.click();
                }"""
            )

        open_trigger()
        time.sleep(0.8)

        for step in category_path:
            clicked = False
            for _ in range(3):
                clicked = self.page.evaluate(
                    r"""(label) => {
                        const visible = (el) => !!el && el.offsetParent !== null;
                        const normalize = (text) => (text || '').replace(/\\n/g, '').replace(/\s+/g, ' ').trim();
                        const selectors = [
                            '.el-cascader-node',
                            '.vue-recycle-scroller__item-view',
                            '.el-scrollbar__view li',
                            '.el-cascader-menu__list li',
                            '.el-cascader-panel [role="menuitem"]',
                            '.el-cascader-panel span',
                            '.el-cascader-panel div'
                        ];
                        const seen = new Set();
                        const candidates = [];
                        for (const selector of selectors) {
                            for (const node of document.querySelectorAll(selector)) {
                                if (seen.has(node) || !visible(node)) continue;
                                seen.add(node);
                                candidates.push(node);
                            }
                        }
                        const target = candidates.find((node) => normalize(node.innerText).includes(label));
                        if (!target) {
                            const scrollPanels = document.querySelectorAll('.el-scrollbar__wrap, .vue-recycle-scroller');
                            for (const panel of scrollPanels) {
                                if (visible(panel)) panel.scrollTop += 220;
                            }
                            return false;
                        }
                        target.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                        target.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                        target.click();
                        return true;
                    }""",
                    step,
                )
                if clicked:
                    break
                open_trigger()
                time.sleep(0.5)
            if not clicked:
                self.screenshot(f'category_node_not_found_{step}')
                raise RuntimeError(f'未找到类目节点: {step}')
            time.sleep(0.6)

    def _fill_required_attributes(self, dialog, product: Dict[str, Any]):
        length = product.get('package_length') or 30
        width = product.get('package_width') or 20
        height = product.get('package_height') or 10
        dimension_text = f'{length}x{width}x{height}'
        dialog.evaluate(
            r"""(dimensionText) => {
                const visible = (el) => !!el && el.offsetParent !== null;
                const items = Array.from(document.querySelectorAll('.el-dialog__body .el-form-item'));
                for (const item of items) {
                    if (!visible(item)) continue;
                    const text = (item.innerText || '').replace(/\s+/g, ' ');
                    if (!text.includes('尺寸（长 x 宽 x 高）') && !text.includes('Dimension')) continue;
                    const input = item.querySelector('input, textarea');
                    if (!input) continue;
                    if ((input.value || '').trim()) return true;
                    input.focus();
                    input.value = dimensionText;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    return true;
                }
                return false;
            }""",
            dimension_text,
        )

    def _erp_text_units(self, text: str) -> int:
        total = 0
        for char in text or '':
            total += 1 if ord(char) < 128 else 2
        return total

    def _trim_for_erp_limit(self, text: str, limit: int) -> str:
        trimmed = []
        total = 0
        for char in (text or '').strip():
            unit = 1 if ord(char) < 128 else 2
            if total + unit > limit:
                break
            trimmed.append(char)
            total += unit
        return ''.join(trimmed).strip()

    def _derive_sales_attribute_options(self, product: Dict[str, Any]) -> List[str]:
        options: List[str] = []
        for sku in product.get('skus') or []:
            sku_name = (sku.get('sku_name') or '').strip()
            if not sku_name:
                continue
            candidate = sku_name.split('-')[0].strip() or sku_name
            candidate = self._trim_for_erp_limit(candidate, 30)
            if candidate and candidate not in options:
                options.append(candidate)
        return options

    def _normalize_sales_attribute_values(self, dialog, product: Dict[str, Any]):
        options = self._derive_sales_attribute_options(product)
        try:
            updated = dialog.evaluate(
                r"""(root, { options }) => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                    const measure = (text) => {
                        let total = 0;
                        for (const char of Array.from(text || '')) {
                            total += char.charCodeAt(0) < 128 ? 1 : 2;
                        }
                        return total;
                    };
                    const trimForLimit = (text, limit) => {
                        let total = 0;
                        let result = '';
                        for (const char of Array.from((text || '').trim())) {
                            const unit = char.charCodeAt(0) < 128 ? 1 : 2;
                            if (total + unit > limit) break;
                            result += char;
                            total += unit;
                        }
                        return result.trim();
                    };
                    const ensureUnique = (text, used, limit) => {
                        const normalizedText = trimForLimit(text, limit) || '规格';
                        if (!used.has(normalizedText)) {
                            used.add(normalizedText);
                            return normalizedText;
                        }

                        let counter = 2;
                        while (counter < 1000) {
                            const suffix = `-${counter}`;
                            const uniqueValue = `${trimForLimit(normalizedText, limit - measure(suffix))}${suffix}`;
                            if (!used.has(uniqueValue)) {
                                used.add(uniqueValue);
                                return uniqueValue;
                            }
                            counter += 1;
                        }

                        used.add(normalizedText);
                        return normalizedText;
                    };
                    const setValue = (node, value) => {
                        node.focus();
                        node.select?.();
                        node.value = value;
                        node.dispatchEvent(new Event('input', { bubbles: true }));
                        node.dispatchEvent(new Event('change', { bubbles: true }));
                        node.dispatchEvent(new Event('blur', { bubbles: true }));
                    };

                    const candidates = Array.from(root.querySelectorAll('input'))
                        .filter((node) => visible(node))
                        .filter((node) => {
                            const placeholder = (node.getAttribute('placeholder') || '').trim();
                            if (placeholder !== '请输入选项名称') return false;
                            const containerText = normalize(
                                node.closest('.sale-spec-table, .sale-spec-wrapper, .el-form-item, .sku-item, .el-table__row, tr, .el-dialog__body')?.innerText
                                || node.parentElement?.parentElement?.innerText
                                || node.parentElement?.innerText
                                || ''
                            );
                            return containerText.includes('销售属性')
                                || containerText.includes('规格一')
                                || containerText.includes('添加选项')
                                || /\b\d+\s*\/30\b/.test(containerText);
                        });

                    let changed = 0;
                    const usedValues = new Set();
                    for (let index = 0; index < candidates.length; index += 1) {
                        const node = candidates[index];
                        const fallback = node.value || node.getAttribute('value') || '';
                        const nextValue = ensureUnique(options[index] || fallback, usedValues, 30);
                        if (!nextValue) continue;
                        if (normalize(fallback) !== normalize(nextValue) || measure(fallback) > 30) {
                            setValue(node, nextValue);
                            changed += 1;
                        }
                    }
                    return changed;
                }""",
                {'options': options},
            )
            if updated:
                logger.info(f'销售属性名称已规范化: {options}')
                time.sleep(0.5)
        except Exception:
            pass

    def _normalize_platform_sku_values(self, dialog, product: Dict[str, Any]):
        source_id = str(product.get('alibaba_product_id') or product.get('product_id') or '').strip()
        if not source_id:
            return

        try:
            updated = dialog.evaluate(
                r"""(root, { sourceId }) => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const measure = (text) => {
                        let total = 0;
                        for (const char of Array.from(text || '')) {
                            total += char.charCodeAt(0) < 128 ? 1 : 2;
                        }
                        return total;
                    };
                    const trimForLimit = (text, limit) => {
                        let total = 0;
                        let result = '';
                        for (const char of Array.from((text || '').trim())) {
                            const unit = char.charCodeAt(0) < 128 ? 1 : 2;
                            if (total + unit > limit) break;
                            result += char;
                            total += unit;
                        }
                        return result.trim();
                    };
                    const setValue = (node, value) => {
                        node.focus();
                        node.select?.();
                        node.value = value;
                        node.dispatchEvent(new Event('input', { bubbles: true }));
                        node.dispatchEvent(new Event('change', { bubbles: true }));
                        node.dispatchEvent(new Event('blur', { bubbles: true }));
                    };

                    const candidates = Array.from(root.querySelectorAll('input[type="text"]'))
                        .filter((node) => visible(node))
                        .filter((node) => {
                            const value = (node.value || '').trim();
                            return value.startsWith(`${sourceId}_`) && measure(value) > 30;
                        });

                    let changed = 0;
                    for (const node of candidates) {
                        const current = (node.value || '').trim();
                        const next = trimForLimit(current, 30);
                        if (!next || next === current) continue;
                        setValue(node, next);
                        changed += 1;
                    }
                    return changed;
                }""",
                {'sourceId': source_id},
            )
            if updated:
                logger.info(f'平台SKU已规范化: source_id={source_id}, updated={updated}')
                time.sleep(0.5)
        except Exception:
            pass

    def _click_visible_button(self, text_candidates: Sequence[str], container=None) -> bool:
        target = container if container is not None else self.page
        for text in text_candidates:
            locator = target.locator('button').filter(has_text=text)
            if locator.count() > 0:
                button = locator.first
                try:
                    if button.is_visible():
                        button.click(force=True)
                        return True
                except Exception:
                    pass
        clicked = target.evaluate(
            r"""(labels) => {
                const visible = (el) => !!el && el.offsetParent !== null;
                const buttons = Array.from(document.querySelectorAll('button, span, div'));
                for (const label of labels) {
                    const node = buttons.find((item) => visible(item) && (item.innerText || '').replace(/\s+/g, '').includes(label.replace(/\s+/g, '')));
                    if (node) {
                        node.click();
                        return true;
                    }
                }
                return false;
            }""",
            list(text_candidates),
        )
        return bool(clicked)

    def _click_save_action(self, dialog, publish: bool = True) -> bool:
        self._close_popups()
        if publish:
            return self._click_visible_button(['保存并发布'], container=dialog)
        return self._click_visible_button(['保存修改跨境全球', '保存修改'], container=dialog)

    def _resolve_save_warning_message_boxes(self, timeout: float = 8.0) -> bool:
        deadline = time.time() + timeout
        handled = False

        while time.time() < deadline:
            visible_wrapper = None
            wrapper_text = ''

            try:
                wrappers = self.page.locator('.el-message-box__wrapper')
                for index in range(wrappers.count()):
                    wrapper = wrappers.nth(index)
                    if not wrapper.is_visible():
                        continue
                    visible_wrapper = wrapper
                    try:
                        wrapper_text = wrapper.inner_text(timeout=500)
                    except Exception:
                        wrapper_text = ''
                    break
            except Exception:
                visible_wrapper = None

            if visible_wrapper is None:
                return handled

            if '相差超过了7倍' in wrapper_text and '仍然保存修改' in wrapper_text:
                if self._click_visible_button(['仍然保存修改'], container=visible_wrapper):
                    handled = True
                    time.sleep(0.8)
                    continue

            return handled

        return handled

    def _wait_for_publish_dialog(self, timeout: float = 10.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            for selector in ['.el-dialog', '.jx-dialog', '.ant-modal', '[role="dialog"]']:
                dialogs = self.page.locator(selector)
                if dialogs.count() == 0:
                    continue
                for index in range(dialogs.count()):
                    dialog = dialogs.nth(index)
                    try:
                        if not dialog.is_visible():
                            continue
                        title = dialog.locator('.el-dialog__title, .jx-dialog-title, .ant-modal-title').first
                        title_text = title.inner_text() if title.count() > 0 else ''
                        dialog_text = dialog.inner_text(timeout=500)
                        combined = f'{title_text}\n{dialog_text}'
                        if any(keyword in combined for keyword in ['发布产品', '选择发布店铺', '跨境全球 发布配置', '确定发布', '发布到选中店铺']):
                            return dialog
                    except Exception:
                        continue
            time.sleep(0.3)
        return None

    def _wait_for_save_only_completion(self, timeout: float = 15.0) -> bool:
        deadline = time.time() + timeout
        seen_stable_without_publish = False
        while time.time() < deadline:
            dialog = self._wait_for_edit_dialog(timeout=0.3)
            if dialog is None:
                return True

            try:
                body_text = self.page.locator('body').inner_text(timeout=1000)
            except Exception:
                body_text = ''

            if '保存成功' in body_text or '修改成功' in body_text or '操作成功' in body_text:
                return True

            publish_dialog = self._wait_for_publish_dialog(timeout=0.3)
            if publish_dialog is not None:
                return False

            if seen_stable_without_publish:
                return True
            seen_stable_without_publish = True

            time.sleep(0.5)
        return False

    def _detect_publish_blocker(self) -> Optional[str]:
        titles = self._get_visible_dialog_titles()
        title_text = ' | '.join(titles)

        try:
            body_text = self.page.locator('body').inner_text()
        except Exception:
            body_text = ''

        combined = f'{title_text}\n{body_text}'
        if '新手指南' in combined and '店铺授权' in combined:
            return '发布被阻断：当前弹出“新手指南/店铺授权”窗口，需先在本地妙手ERP完成 Shopee 店铺授权后再发布'
        if '请选择一个平台进行店铺授权' in combined:
            return '发布被阻断：妙手ERP要求先完成店铺授权，当前账号尚未就绪'
        return None

    def _dismiss_blocking_dialogs(self) -> bool:
        dismissed = False
        try:
            dismissed = bool(self.page.evaluate(
                """() => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    let changed = false;
                    for (const dialog of document.querySelectorAll('.el-dialog')) {
                        if (!visible(dialog)) continue;
                        const text = (dialog.innerText || '').trim();
                        if (!text.includes('新手指南') && !text.includes('店铺授权')) continue;
                        const closeBtn = dialog.querySelector('.el-dialog__headerbtn, .el-dialog__close');
                        if (closeBtn) {
                            closeBtn.click();
                            changed = true;
                        }
                    }
                    return changed;
                }"""
            ))
        except Exception:
            return False

        if dismissed:
            time.sleep(0.8)
        return dismissed

    def _has_selected_publish_store(self, dialog) -> bool:
        try:
            return bool(dialog.evaluate(
                r"""(root) => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                    const isChecked = (node) => {
                        if (!node) return false;
                        const className = (node.className || '').toString();
                        if (className.includes('is-checked')) return true;
                        const input = node.querySelector?.('input[type="checkbox"]');
                        return !!input && input.checked;
                    };

                    const excludedTexts = [
                        '全选',
                        '自动发布到店铺',
                        '引用妙手全球产品发布设置',
                        '过滤店铺已发布的产品',
                        '产品价格幅度',
                        '标题随机打乱',
                        '在',
                        '自动添加店铺名水印',
                        '主图随机排序',
                        '违禁词检测',
                        '用SKU重量发布',
                    ];

                    const wrappers = Array.from(root.querySelectorAll('label, .el-checkbox'))
                        .filter((node) => visible(node));

                    const storeWrappers = wrappers.filter((node) => {
                        const text = normalize(node.innerText || node.parentElement?.innerText || '');
                        if (!text) return false;
                        return !excludedTexts.some((item) => text.includes(item));
                    });

                    return storeWrappers.some((node) => {
                        const wrapper = node.closest?.('.el-checkbox') || node;
                        return isChecked(wrapper);
                    });
                }"""
            ))
        except Exception:
            return False

    def _publish_target_keywords(self, product: Optional[Dict[str, Any]] = None) -> List[str]:
        normalized = normalize_site_context(product or {})
        keywords: List[str] = []
        shop_code = str(normalized.get('shop_code') or '').strip()
        if shop_code and shop_code.lower() != 'default':
            keywords.append(shop_code)

        site_code = str(normalized.get('site_code') or '').strip().lower()
        if site_code == 'shopee_ph':
            keywords.extend(['PH', '菲律宾', 'Philippines'])
        elif site_code == 'shopee_tw':
            keywords.extend(['TW', '台湾', 'Taiwan'])

        deduped: List[str] = []
        seen = set()
        for keyword in keywords:
            normalized_keyword = keyword.strip()
            if not normalized_keyword or normalized_keyword in seen:
                continue
            seen.add(normalized_keyword)
            deduped.append(normalized_keyword)
        return deduped

    def _select_publish_targets(self, dialog, product: Optional[Dict[str, Any]] = None):
        if self._has_selected_publish_store(dialog):
            return True

        selected = False
        preferred_keywords = self._publish_target_keywords(product)

        try:
            checkbox_labels = dialog.locator('label')
            for index in range(checkbox_labels.count()):
                label = checkbox_labels.nth(index)
                try:
                    if not label.is_visible():
                        continue
                    text = (label.inner_text() or '').strip()
                    if not text or '全选' in text:
                        continue
                    if any(keyword in text for keyword in ['自动发布到店铺', '过滤店铺已发布的产品', '产品价格幅度', '标题随机打乱', '自动添加店铺名水印', '主图随机排序', '违禁词检测', '用SKU重量发布']):
                        continue
                    if preferred_keywords and not any(keyword.lower() in text.lower() for keyword in preferred_keywords):
                        continue
                    label.click(force=True)
                    time.sleep(0.3)
                    selected = True
                    break
                except Exception:
                    continue
        except Exception:
            pass

        if not selected:
            try:
                wrappers = dialog.locator('.el-checkbox')
                for index in range(wrappers.count()):
                    wrapper = wrappers.nth(index)
                    try:
                        if not wrapper.is_visible():
                            continue
                        text = (wrapper.inner_text() or '').strip()
                        if not text or '全选' in text:
                            continue
                        if any(keyword in text for keyword in ['自动发布到店铺', '过滤店铺已发布的产品', '产品价格幅度', '标题随机打乱', '自动添加店铺名水印', '主图随机排序', '违禁词检测', '用SKU重量发布']):
                            continue
                        if preferred_keywords and not any(keyword.lower() in text.lower() for keyword in preferred_keywords):
                            continue
                        wrapper.click(force=True)
                        time.sleep(0.3)
                        selected = True
                        break
                    except Exception:
                        continue
            except Exception:
                pass

        if not selected:
            selected = bool(dialog.evaluate(
                r"""(root) => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                    const markChecked = (node) => {
                        if (!node || !visible(node)) return false;
                        node.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                        node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                        node.click();
                        return true;
                    };
                    const isChecked = (wrapper) => {
                        if (!wrapper) return false;
                        if ((wrapper.className || '').toString().includes('is-checked')) return true;
                        const input = wrapper.querySelector?.('input[type="checkbox"]');
                        return !!input && input.checked;
                    };

                    const wrappers = Array.from(root.querySelectorAll('.el-checkbox, label, .el-checkbox__input'))
                        .filter((node) => visible(node));

                    const storeCandidates = wrappers.filter((node) => {
                        const text = normalize(node.innerText || node.parentElement?.innerText || '');
                        return text && !text.includes('全选');
                    });

                    for (const candidate of storeCandidates) {
                        const wrapper = candidate.closest?.('.el-checkbox') || candidate.parentElement || candidate;
                        if (isChecked(wrapper)) return true;
                        if (markChecked(candidate)) return true;
                    }

                    const fullSelect = wrappers.find((node) => normalize(node.innerText || node.parentElement?.innerText || '').includes('全选'));
                    if (fullSelect) {
                        const wrapper = fullSelect.closest?.('.el-checkbox') || fullSelect.parentElement || fullSelect;
                        if (isChecked(wrapper)) return true;
                        if (markChecked(fullSelect)) return true;
                    }

                    return false;
                }"""
            ))

        time.sleep(0.5)

        return self._has_selected_publish_store(dialog)

    def _confirm_publish(self, dialog) -> bool:
        if self._click_visible_button(['确定发布', '确认发布', '批量发布', '确定'], container=dialog):
            return True

        try:
            clicked = bool(dialog.evaluate(
                r"""(root) => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const normalize = (text) => (text || '').replace(/\s+/g, '').trim();
                    const labels = ['确定发布', '确认发布', '批量发布', '确定'];
                    const nodes = Array.from(root.querySelectorAll('button, span, div'));
                    for (const label of labels) {
                        const node = nodes.find((item) => visible(item) && normalize(item.innerText || '').includes(normalize(label)));
                        if (!node) continue;
                        node.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                        node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                        node.click();
                        return true;
                    }
                    return false;
                }"""
            ))
            if clicked:
                time.sleep(0.6)
            return clicked
        except Exception:
            return False

    def _get_visible_dialog_titles(self) -> List[str]:
        try:
            titles = self.page.evaluate(
                """() => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const result = [];
                    for (const dialog of document.querySelectorAll('.el-dialog, .jx-dialog, .ant-modal')) {
                        if (!visible(dialog)) continue;
                        const titleNode = dialog.querySelector('.el-dialog__title, .jx-dialog-title, .ant-modal-title');
                        const text = (titleNode?.innerText || dialog.innerText || '').trim();
                        if (text) result.push(text);
                    }
                    return result;
                }"""
            )
            return titles or []
        except Exception:
            return []

    def _close_result_dialogs(self):
        for _ in range(3):
            try:
                self.page.evaluate(
                    """() => {
                        const visible = (el) => !!el && el.offsetParent !== null;
                        for (const dialog of document.querySelectorAll('.el-dialog')) {
                            if (!visible(dialog)) continue;
                            const closeBtn = dialog.querySelector('.el-dialog__headerbtn');
                            if (closeBtn) closeBtn.click();
                        }
                    }"""
                )
            except Exception:
                pass
            time.sleep(0.4)

    def _get_visible_dialog_texts(self) -> List[str]:
        try:
            texts = self.page.evaluate(
                """() => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const result = [];
                    for (const dialog of document.querySelectorAll('.el-dialog, .jx-dialog, .ant-modal')) {
                        if (!visible(dialog)) continue;
                        const text = (dialog.innerText || '').trim();
                        if (text) result.push(text);
                    }
                    return result;
                }"""
            )
            return texts or []
        except Exception:
            return []

    def _get_form_validation_errors(self, dialog) -> List[str]:
        try:
            errors = dialog.evaluate(
                r"""(root) => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                    const values = [];

                    for (const node of root.querySelectorAll('.el-form-item__error, .ant-form-item-explain-error')) {
                        if (!visible(node)) continue;
                        const text = normalize(node.innerText || '');
                        if (text) values.push(text);
                    }

                    for (const node of root.querySelectorAll('.el-form-item.is-error')) {
                        if (!visible(node)) continue;
                        const text = normalize(node.innerText || '');
                        if (!text) continue;
                        const matched = text.match(/(不能为空|请选择[^\s]+|请填写[^\s]+|必填|字符数超出限制|不能小于0\.01KG|视频像素不超过1280×1280px|视频时长10s~60s|大小必须小于30M|格式为MP4)/g) || [];
                        for (const item of matched) values.push(item);
                    }

                    for (const node of root.querySelectorAll('input, textarea')) {
                        if (!visible(node)) continue;
                        const holder = normalize(node.getAttribute('placeholder') || '');
                        const parentText = normalize(node.parentElement?.innerText || node.closest('.el-form-item')?.innerText || '');
                        const over30 = parentText.match(/\b([3-9]\d|\d{3,})\s*\/\s*30\b/);
                        const over100 = parentText.match(/\b(10[1-9]|[2-9]\d{2,})\s*\/\s*100\b/);
                        const over14 = parentText.match(/\b(1[5-9]|[2-9]\d|\d{3,})\s*\/\s*14\b/);
                        const over180 = parentText.match(/\b(18[1-9]|[2-9]\d{2,})\s*\/\s*180\b/);
                        const over5000 = parentText.match(/\b(500[1-9]|50[1-9]\d|5[1-9]\d{2}|[6-9]\d{3,})\s*\/\s*5000\b/);
                        if (over30 || over100 || over14 || over180 || over5000) {
                            values.push('字符数超出限制');
                        }
                        if (holder.includes('KG') && parentText.includes('不能小于0.01KG')) {
                            values.push('不能小于0.01KG');
                        }
                    }

                    return Array.from(new Set(values));
                }"""
            )
            return errors or []
        except Exception:
            return []

    def _describe_publish_branch_after_save(self, dialog) -> Dict[str, Any]:
        titles = self._get_visible_dialog_titles()
        texts = self._get_visible_dialog_texts()
        errors = self._get_form_validation_errors(dialog)
        try:
            body_text = self.page.locator('body').inner_text(timeout=1000)
        except Exception:
            body_text = ''

        branch = 'unknown'
        if errors:
            branch = 'validation_error'
        elif any('发布产品' in title for title in titles):
            branch = 'publish_dialog_visible'
        elif any(keyword in body_text for keyword in ['保存成功', '修改成功', '操作成功']):
            branch = 'save_only_success'
        elif any(keyword in body_text for keyword in ['新手指南', '店铺授权', '请选择一个平台进行店铺授权']):
            branch = 'publish_blocked'
        elif any(keyword in title for title in titles for keyword in ['基本信息', '产品图片', '物流信息', '销售信息']):
            branch = 'still_in_edit_dialog'

        return {
            'branch': branch,
            'titles': titles,
            'errors': errors,
            'body_excerpt': body_text[:500].replace('\n', ' '),
            'dialog_excerpt': texts[0][:500].replace('\n', ' ') if texts else '',
        }

    def _wait_for_publish_completion(self, timeout: float = 15.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                body_text = self.page.locator('body').inner_text()
            except Exception:
                body_text = ''

            if '发布成功' in body_text or '成功发布' in body_text:
                return True

            dialog_titles = self._get_visible_dialog_titles()
            if dialog_titles:
                dialog_text = ' | '.join(dialog_titles)
                if '发布成功' in dialog_text or '成功发布' in dialog_text:
                    return True

            dialog = self._wait_for_publish_dialog(timeout=0.3)
            if dialog is None:
                return True

            try:
                dialog_text = dialog.inner_text(timeout=500)
            except Exception:
                dialog_text = ''

            if '发布成功' in dialog_text or '成功发布' in dialog_text:
                return True

            try:
                confirm_buttons = dialog.locator('button').filter(has_text='确定发布')
                batch_buttons = dialog.locator('button').filter(has_text='批量发布')
                visible_confirm = confirm_buttons.count() > 0 and confirm_buttons.first.is_visible()
                visible_batch = batch_buttons.count() > 0 and batch_buttons.first.is_visible()
                if not visible_confirm and not visible_batch:
                    return True
            except Exception:
                pass

            time.sleep(0.5)
        return False

    def update_product(self, product: Any, publish: bool = True) -> bool:
        normalized = self._augment_with_sku_data(self._normalize_product_input(product))
        source_item_id = normalized.get('alibaba_product_id') or normalized.get('product_id')
        if not source_item_id:
            raise ValueError('没有阿里巴巴商品ID')

        logger.info(f'开始处理商品: {source_item_id}')
        self._goto_collect_box()

        found_in_unpublished = self._search_source_item(str(source_item_id), capture_failure=False)
        found_in_published = False
        if not found_in_unpublished:
            self._goto_collect_box()
            found_in_published = self._search_source_item(str(source_item_id), tab_label='已发布', capture_failure=False)

        if not found_in_unpublished and not found_in_published:
            self.screenshot('source_search_no_result')
            raise RuntimeError(f'搜索后未找到商品 {source_item_id}')

        if found_in_published and not publish:
            logger.info(f'商品 {source_item_id} 当前位于已发布列表，将执行保存回写而不重新发布')

        if not self._click_edit_for_source(str(source_item_id)):
            self.screenshot('edit_button_not_found')
            raise RuntimeError(f'未找到商品 {source_item_id} 的编辑按钮')

        dialog = self._wait_for_edit_dialog()
        if dialog is None:
            self.screenshot('edit_dialog_not_found')
            raise RuntimeError('未能打开编辑对话框')

        self._fill_basic_fields(dialog, normalized)
        self._fill_item_num(dialog, normalized)
        self._fill_category(dialog, normalized)
        self._fill_main_images(dialog, normalized)
        self._fill_weight_dimensions(dialog, normalized)
        self._fill_required_attributes(dialog, normalized)
        self._normalize_sales_attribute_values(dialog, normalized)
        self._normalize_platform_sku_values(dialog, normalized)
        if not self._click_save_action(dialog, publish=publish):
            self.screenshot('save_action_click_failed')
            raise RuntimeError('未能触发保存动作')

        self._resolve_save_warning_message_boxes()

        if not publish:
            completed = self._wait_for_save_only_completion(timeout=20.0)
            if not completed:
                self.screenshot('save_only_completion_timeout')
                raise RuntimeError('保存修改后未观察到成功态或编辑框关闭')

            self._close_result_dialogs()
            if found_in_published and normalized.get('id'):
                self.update_product_status(normalized['id'], 'published')
                self._update_site_listing_status(normalized, 'published', publish_status='published')
            save_mode = '已发布' if found_in_published else '未发布'
            if not found_in_published:
                self._update_site_listing_status(normalized, 'draft', publish_status='saved')
            logger.info(f'商品保存成功（{save_mode}）: {source_item_id}')
            return True

        publish_dialog = self._wait_for_publish_dialog()
        if publish_dialog is None:
            blocker = self._detect_publish_blocker()
            if blocker:
                self.screenshot('publish_blocked_by_guide')
                if self._dismiss_blocking_dialogs():
                    if not self._click_save_action(dialog, publish=True):
                        raise RuntimeError(f'{blocker}；且关闭引导窗后未能重新触发保存并发布')
                    self._resolve_save_warning_message_boxes()
                    publish_dialog = self._wait_for_publish_dialog(timeout=5.0)
                    if publish_dialog is not None:
                        self.screenshot('publish_dialog_after_guide_close')
                    else:
                        raise RuntimeError(blocker)
                else:
                    raise RuntimeError(blocker)

        if publish_dialog is None:
            diagnostics = self._describe_publish_branch_after_save(dialog)
            video_errors = self._extract_video_validation_errors(diagnostics.get('errors') or [])
            if video_errors and self.disable_product_video:
                self.screenshot('video_validation_error_detected')
                logger.warning(f'检测到视频校验错误: {video_errors}')
                publish_dialog = self._retry_publish_after_video_cleanup(dialog, timeout=15.0)
                diagnostics = self._describe_publish_branch_after_save(dialog)
            if diagnostics.get('branch') == 'still_in_edit_dialog' and not diagnostics.get('errors'):
                logger.warning('保存并发布后仍停留在编辑对话框，先额外等待，再重试一次点击保存并发布')
                publish_dialog = self._wait_for_publish_dialog(timeout=12.0)
                if publish_dialog is None and self._click_save_action(dialog, publish=True):
                    self._resolve_save_warning_message_boxes()
                    publish_dialog = self._wait_for_publish_dialog(timeout=15.0)
                    if publish_dialog is not None:
                        self.screenshot('publish_dialog_open_after_retry')
                if publish_dialog is None:
                    logger.warning('重试后仍停留在编辑对话框，继续等待保存结果落地')
                    publish_dialog = self._wait_for_publish_dialog(timeout=20.0)
                    if publish_dialog is not None:
                        self.screenshot('publish_dialog_open_after_long_wait')
                if publish_dialog is None:
                    diagnostics = self._describe_publish_branch_after_save(dialog)

        if publish_dialog is None:
            diagnostics = diagnostics if 'diagnostics' in locals() else self._describe_publish_branch_after_save(dialog)
            self.screenshot('publish_dialog_not_found')
            detail_parts = [f"branch={diagnostics.get('branch')}"]
            if diagnostics.get('errors'):
                detail_parts.append(f"errors={'; '.join(diagnostics['errors'])}")
            if diagnostics.get('titles'):
                detail_parts.append(f"titles={' | '.join(diagnostics['titles'])}")
            raise RuntimeError(f"保存并发布后未出现发布确认对话框 ({', '.join(detail_parts)})")

        self.screenshot('publish_dialog_open')
        if not self._select_publish_targets(publish_dialog, normalized):
            self.screenshot('publish_targets_not_selected')
            raise RuntimeError('未能勾选发布店铺')
        self.screenshot('publish_targets_selected')
        if not self._confirm_publish(publish_dialog):
            self.screenshot('publish_confirm_failed')
            raise RuntimeError('未能点击确定发布/批量发布')

        self.screenshot('publish_confirm_clicked')

        success = self._wait_for_publish_completion(timeout=30.0)
        if not success:
            dialog_titles = ' | '.join(self._get_visible_dialog_titles())
            dialog_texts = self._get_visible_dialog_texts()
            if dialog_titles:
                logger.warning(f'发布超时，可见弹窗标题: {dialog_titles}')
            if dialog_texts:
                snippet = dialog_texts[0][:500].replace('\n', ' ')
                logger.warning(f'发布超时，可见弹窗内容: {snippet}')
            self.screenshot('publish_completion_timeout_before_close')
            self._close_result_dialogs()
            if self._wait_for_product_published(str(source_item_id), timeout=45.0):
                if normalized.get('id'):
                    self.update_product_status(normalized['id'], 'published')
                    self._update_site_listing_status(normalized, 'published', publish_status='published')
                logger.warning(f'发布确认弹窗超时，但商品已进入已发布列表，按成功处理: {source_item_id}')
                return True
            self.screenshot('publish_completion_timeout')
            raise RuntimeError('发布流程超时，未观察到成功态')

        self._close_result_dialogs()

        if not self._wait_for_product_published(str(source_item_id), timeout=60.0):
            raise RuntimeError('发布后核验失败，商品未从未发布移出或未出现在已发布列表')

        if normalized.get('id'):
            self.update_product_status(normalized['id'], 'published')
            self._update_site_listing_status(normalized, 'published', publish_status='published')
        logger.info(f'商品发布成功: {source_item_id}')
        return True

    def run(self, limit: int = 1) -> Dict[str, Any]:
        products = self.get_optimized_products(limit=limit)
        if not products:
            return {'success': False, 'message': '没有待处理商品', 'count': 0}

        success_count = 0
        failures: List[Dict[str, Any]] = []
        for product in products:
            try:
                if self.update_product(product):
                    success_count += 1
            except Exception as exc:
                failures.append({
                    'alibaba_product_id': product.get('alibaba_product_id'),
                    'error': str(exc),
                })
                logger.error(str(exc))

        return {
            'success': success_count > 0 and not failures,
            'count': success_count,
            'failures': failures,
        }


def main():
    parser = argparse.ArgumentParser(description='妙手 ERP 回写发布器')
    parser.add_argument('--limit', type=int, default=1, help='批量处理数量')
    parser.add_argument('--product-id', help='指定商品 id / 货源ID / 主货号')
    parser.add_argument('--list', action='store_true', help='仅列出待处理商品')
    parser.add_argument('--headed', action='store_true', help='使用有头浏览器')
    parser.add_argument('--cdp-url', help='连接现有 Chrome 的 CDP 地址，例如 http://127.0.0.1:9222')
    args = parser.parse_args()

    updater = MiaoshouUpdater(headless=not args.headed, cdp_url=args.cdp_url)
    if args.list:
        for product in updater.get_optimized_products(limit=max(args.limit, 20)):
            title = (product.get('optimized_title') or product.get('title') or '')[:40]
            print(f"[{product['id']}] {product.get('product_id_new')} | {product.get('alibaba_product_id')} | {title}")
        return

    updater.launch()
    try:
        if args.product_id:
            result = updater.update_product(args.product_id)
            print('成功' if result else '失败')
        else:
            print(json.dumps(updater.run(limit=args.limit), ensure_ascii=False, indent=2))
    finally:
        updater.close()


if __name__ == '__main__':
    main()