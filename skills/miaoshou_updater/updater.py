#!/usr/bin/env python3
"""
miaoshou_updater.updater

Playwright-based updater for Miaoshou ERP Shopee collect-box items.
"""
import argparse
from contextlib import contextmanager
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

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


def _load_config_env() -> None:
    """Load variables from config/config.env into os.environ if not already set."""
    config_env_path = WORKSPACE / 'config' / 'config.env'
    if not config_env_path.exists():
        return
    with open(config_env_path, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


_load_config_env()

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

_DEFAULT_PRODUCT_FIXTURE_CANDIDATES = [
    WORKSPACE / 'skills' / 'miaoshou-api-publisher' / 'sample-debug-product.json',
]

DEFAULT_CATEGORY_PATH = ['家居生活', '居家收纳', '收纳盒']
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'database': os.environ.get('DB_NAME', 'ecommerce_data'),
    'user': os.environ.get('DB_USER', 'superuser'),
    'password': os.environ.get('DB_PASSWORD', ''),
}


def _build_cookie_candidates(extra: Optional[Path] = None) -> List[Path]:
    """Return a prioritized list of cookie file candidates.

    If *extra* is given (e.g. from ``MIAOSHOU_COOKIES_FILE`` env var or a
    constructor argument) it is prepended so it takes highest priority.
    """
    candidates: List[Path] = list(COOKIE_CANDIDATES)
    _env_val = os.environ.get('MIAOSHOU_COOKIES_FILE', '').strip()
    if _env_val:
        env_path = Path(_env_val)
        if env_path not in candidates:
            candidates.insert(0, env_path)
    if extra and extra not in candidates:
        candidates.insert(0, extra)
    return candidates


class MiaoshouUpdater:
    def __init__(
        self,
        cookies_file: Optional[Path] = None,
        headless: bool = True,
        fixture_file: Optional[Path] = None,
    ):
        self._fixture_candidates: List[Path] = list(_DEFAULT_PRODUCT_FIXTURE_CANDIDATES)
        if fixture_file:
            extra = Path(fixture_file)
            if extra not in self._fixture_candidates:
                self._fixture_candidates.insert(0, extra)
        self._cookie_candidates: List[Path] = _build_cookie_candidates()
        self.cookies_file = Path(cookies_file) if cookies_file else self._detect_cookies_file()
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.cookies = self._load_cookies() if self.cookies_file else []

    def _detect_cookies_file(self) -> Optional[Path]:
        for candidate in self._cookie_candidates:
            if candidate.exists():
                return candidate
        return None

    def _load_cookies(self) -> List[Dict[str, Any]]:
        if not self.cookies_file:
            raise FileNotFoundError('未找到妙手 Cookies 文件')
        with open(self.cookies_file, 'r', encoding='utf-8') as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, list) else payload.get('cookies', [])

    def _load_product_fixture(self, identifier: Any) -> Optional[Dict[str, Any]]:
        identifier = str(identifier)
        for candidate in self._fixture_candidates:
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
                return self._normalize_fixture_row(raw, str(candidate))
        return None

    def _normalize_fixture_row(self, raw: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Normalize a raw fixture dict into the standard product dict shape."""
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
            'fixture_source': source,
        }

    def _load_all_fixtures(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Load up to *limit* products from all fixture candidates."""
        results: List[Dict[str, Any]] = []
        for candidate in self._fixture_candidates:
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
                results.append(self._normalize_fixture_row(raw, str(candidate)))
                if len(results) >= limit:
                    return results
        return results

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

    def launch(self):
        from playwright.sync_api import sync_playwright

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
        )
        self.context = self.browser.new_context(viewport={'width': 1920, 'height': 1080})
        if self.cookies:
            self.context.add_cookies(self._build_cookies())
        self.page = self.context.new_page()
        self.page.set_default_timeout(30000)
        logger.info('浏览器启动成功')
        return True

    def close(self):
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        logger.info('浏览器已关闭')

    def screenshot(self, name: str) -> Optional[Path]:
        self._ensure_page()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = TMP_DIR / f'{name}_{timestamp}.png'
        self.page.screenshot(path=str(file_path), full_page=True)
        logger.info(f'截图: {file_path}')
        return file_path

    def get_optimized_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        try:
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
        except Exception as exc:
            fixture_products = self._load_all_fixtures(limit)
            if fixture_products:
                logger.warning(f'数据库不可用，改用样例商品数据（共{len(fixture_products)}条）: {exc}')
                return fixture_products
            raise RuntimeError(f'数据库连接失败，且未找到可用样例数据: {exc}') from exc

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
                return dict(product)
            identifier = product.get('product_id')
            if identifier:
                return self._load_product_by_identifier(identifier)
            raise ValueError('product 参数缺少 id / alibaba_product_id / product_id_new / product_id')
        return self._load_product_by_identifier(product)

    def _augment_with_sku_data(self, product: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(product)
        sku_list = self.get_skus(result['id']) if result.get('id') else []
        result['skus'] = sku_list
        primary_sku = sku_list[0] if sku_list else {}

        result['package_weight'] = result.get('package_weight') or primary_sku.get('package_weight')
        result['package_length'] = result.get('package_length') or primary_sku.get('package_length')
        result['package_width'] = result.get('package_width') or primary_sku.get('package_width')
        result['package_height'] = result.get('package_height') or primary_sku.get('package_height')

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

    def _search_source_item(self, source_item_id: str, timeout: float = 15.0) -> bool:
        self._ensure_page()
        self._close_popups()

        try:
            unpublished_tab = self.page.get_by_text('未发布', exact=False).first
            if unpublished_tab.count() > 0 and unpublished_tab.is_visible(timeout=1000):
                unpublished_tab.click(force=True)
                time.sleep(0.8)
        except Exception:
            pass

        filled = bool(self.page.evaluate(
            """(sourceId) => {
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
            self.screenshot('source_search_input_not_found')
            raise RuntimeError('未找到货源ID搜索框')

        clicked = self._click_visible_button(['搜索'])
        if not clicked:
            self.page.keyboard.press('Enter')

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                body_text = self.page.locator('body').inner_text(timeout=1000)
            except Exception:
                body_text = ''

            if str(source_item_id) in body_text:
                return True
            if '暂无数据' in body_text or '共0条' in body_text:
                break
            time.sleep(0.5)

        self.screenshot('source_search_no_result')
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
        for _ in range(4):
            self._close_popups()
            clicked = self.page.evaluate(
                """(sourceId) => {
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
                        const buttons = Array.from(root.querySelectorAll('a, button, span, div'));
                        const target = buttons.find((item) => {
                            const text = textOf(item);
                            return visible(item) && (text === '编辑' || text === '修改');
                        });
                        if (target) {
                            return clickNode(target);
                        }
                        return false;
                    };
                    const rowLike = (node) => {
                        if (!node) return false;
                        const cls = node.className || '';
                        const tag = (node.tagName || '').toLowerCase();
                        return tag === 'tr'
                            || String(cls).includes('el-table__row')
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
                const items = document.querySelectorAll('.el-dialog__body .el-form-item');
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

    def _fill_item_num(self, dialog, product: Dict[str, Any]):
        item_num = product.get('product_id_new') or ''
        if item_num:
            self._dispatch_input_value(dialog, 3, item_num)

    def _fill_weight_dimensions(self, dialog, product: Dict[str, Any]):
        weight_g = self._safe_float(product.get('package_weight'), 0.0)
        weight_kg = round(weight_g / 1000, 3) if weight_g else self._safe_float(product.get('package_weight_kg'), 0.0)
        length = product.get('package_length') or 30
        width = product.get('package_width') or 20
        height = product.get('package_height') or 10

        if weight_kg:
            self._dispatch_input_value(dialog, 12, weight_kg)
        self._dispatch_input_value(dialog, 13, length, 0)
        self._dispatch_input_value(dialog, 13, width, 1)
        self._dispatch_input_value(dialog, 13, height, 2)

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
                    """(label) => {
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
            """(dimensionText) => {
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
            """(labels) => {
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

    def _click_save_and_publish(self, dialog) -> bool:
        self._close_popups()
        return self._click_visible_button(['保存并发布', '保存修改'], container=dialog)

    def _wait_for_publish_dialog(self, timeout: float = 10.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            dialogs = self.page.locator('.el-dialog')
            if dialogs.count() > 0:
                for index in range(dialogs.count()):
                    dialog = dialogs.nth(index)
                    try:
                        if not dialog.is_visible():
                            continue
                        title = dialog.locator('.el-dialog__title').first
                        if title.count() > 0 and '发布产品' in title.inner_text():
                            return dialog
                    except Exception:
                        continue
            time.sleep(0.3)
        return None

    def _select_publish_targets(self, dialog):
        selected = False

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
                """(root) => {
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

        return bool(dialog.evaluate(
            """(root) => {
                const visible = (el) => !!el && el.offsetParent !== null;
                const inputs = Array.from(root.querySelectorAll('input[type="checkbox"]')).filter((node) => visible(node));
                if (inputs.some((input) => input.checked)) return true;
                const wrappers = Array.from(root.querySelectorAll('.el-checkbox')).filter((node) => visible(node));
                return wrappers.some((node) => (node.className || '').toString().includes('is-checked'));
            }"""
        ))

    def _confirm_publish(self, dialog) -> bool:
        return self._click_visible_button(['确定发布', '批量发布'], container=dialog)

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

    def update_product(self, product: Any) -> bool:
        normalized = self._augment_with_sku_data(self._normalize_product_input(product))
        source_item_id = normalized.get('alibaba_product_id') or normalized.get('product_id')
        if not source_item_id:
            raise ValueError('没有阿里巴巴商品ID')

        logger.info(f'开始处理商品: {source_item_id}')
        self._goto_collect_box()

        if not self._search_source_item(str(source_item_id)):
            raise RuntimeError(f'搜索后未找到商品 {source_item_id}')

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
        self._fill_weight_dimensions(dialog, normalized)
        self._fill_required_attributes(dialog, normalized)

        if not self._click_save_and_publish(dialog):
            self.screenshot('save_publish_click_failed')
            raise RuntimeError('未能触发 保存并发布')

        publish_dialog = self._wait_for_publish_dialog()
        if publish_dialog is None:
            self.screenshot('publish_dialog_not_found')
            raise RuntimeError('保存并发布后未出现发布确认对话框')

        self.screenshot('publish_dialog_open')
        if not self._select_publish_targets(publish_dialog):
            self.screenshot('publish_targets_not_selected')
            raise RuntimeError('未能勾选发布店铺')
        self.screenshot('publish_targets_selected')
        if not self._confirm_publish(publish_dialog):
            self.screenshot('publish_confirm_failed')
            raise RuntimeError('未能点击确定发布/批量发布')

        self.screenshot('publish_confirm_clicked')

        success = self._wait_for_publish_completion(timeout=30.0)
        self._close_result_dialogs()
        if not success:
            self.screenshot('publish_completion_timeout')
            raise RuntimeError('发布流程超时，未观察到成功态')

        if normalized.get('id'):
            self.update_product_status(normalized['id'], 'published')
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
    parser.add_argument(
        '--fixture',
        metavar='FILE',
        help='指定商品样例 JSON 文件路径，用于离线调试（数据库不可用时）',
    )
    args = parser.parse_args()

    updater = MiaoshouUpdater(
        headless=not args.headed,
        fixture_file=Path(args.fixture) if args.fixture else None,
    )
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