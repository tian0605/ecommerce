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
                for keyword in ['新手指南', '授权店铺', '店铺授权', '查看来源信息']:
                    dialog = self.page.locator('.el-dialog__wrapper, .el-dialog, [role="dialog"]', has_text=keyword).first
                    if dialog.count() > 0:
                        try:
                            close_btn = dialog.locator('.el-dialog__headerbtn, .el-dialog__close, .el-icon-close, [aria-label="关闭此对话框"]').first
                            if close_btn.count() > 0:
                                close_btn.click(force=True, timeout=1000)
                        except Exception:
                            pass

                for txt in ['我知道了', '关闭', '确定', '取消']:
                    btn = self.page.query_selector(f'button:has-text("{txt}")')
                    if btn and btn.is_visible():
                        btn.click(force=True, timeout=2000)
                        time.sleep(0.3)
                self.page.evaluate(
                    """() => {
                        const visible = (el) => !!el && el.offsetParent !== null;
                        const onboardingKeywords = ['新手指南', '授权店铺', '店铺授权', '查看来源信息'];
                        for (const wrapper of document.querySelectorAll('.el-dialog__wrapper, .el-overlay, .el-overlay-dialog, [role="dialog"]')) {
                            const text = (wrapper.innerText || '').trim();
                            const title = (wrapper.querySelector('.el-dialog__title, [class*="title"]')?.innerText || '').trim();
                            if (!onboardingKeywords.some((keyword) => text.includes(keyword) || title.includes(keyword))) continue;

                            const closeNodes = wrapper.querySelectorAll('.el-dialog__headerbtn, .el-dialog__close, .el-icon-close, [aria-label="关闭此对话框"]');
                            for (const node of closeNodes) {
                                if (node instanceof HTMLElement) node.click();
                            }

                            if (wrapper instanceof HTMLElement) {
                                wrapper.style.display = 'none';
                                wrapper.remove();
                            }
                        }

                        for (const dialog of document.querySelectorAll('.el-dialog')) {
                            if (!visible(dialog)) continue;
                            const text = (dialog.innerText || '').trim();
                            const title = (dialog.querySelector('.el-dialog__title')?.innerText || '').trim();
                            if (!onboardingKeywords.some((keyword) => text.includes(keyword) || title.includes(keyword))) continue;
                            const closeBtn = dialog.querySelector('.el-dialog__headerbtn, .el-dialog__close, .el-icon-close');
                            if (closeBtn) {
                                closeBtn.click();
                            }
                            if (dialog instanceof HTMLElement) {
                                dialog.style.display = 'none';
                                dialog.remove();
                            }
                        }

                        for (const overlay of document.querySelectorAll('.v-modal, .el-overlay, .el-overlay-dialog')) {
                            if (overlay instanceof HTMLElement) {
                                overlay.style.display = 'none';
                                overlay.remove();
                            }
                        }
                    }"""
                )
                self.page.keyboard.press('Escape')
                time.sleep(0.3)
            except:
                pass
        return True

    def _ensure_status_tab(self, tab_label: str, timeout: float = 5.0) -> bool:
        deadline = time.time() + timeout
        last_clicked = False

        while time.time() < deadline:
            try:
                state = self.page.evaluate(
                    r'''(label) => {
                        const visible = (el) => !!el && el.offsetParent !== null;
                        const normalize = (text) => (text || '').replace(/\s+/g, '').trim();
                        const STATUS_LABELS = ['全部', '未发布', '定时发布', '已发布'];
                        const exactStatusPattern = (expected) => new RegExp(`^${normalize(expected)}(?:\\(\\d+\\))?$`);

                        const isActive = (node) => {
                            if (!node) return false;
                            let current = node;
                            for (let depth = 0; current && depth < 3; depth += 1, current = current.parentElement) {
                                const cls = String(current.className || '');
                                if (/(^|\s)(active|is-active|current|selected)(\s|$)/i.test(cls)) return true;
                                if (current.getAttribute('aria-selected') === 'true') return true;
                            }

                            const style = window.getComputedStyle(node);
                            const bg = style.backgroundColor || '';
                            const color = style.color || '';
                            if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent' && bg !== 'rgb(255, 255, 255)') {
                                return true;
                            }
                            if (color === 'rgb(255, 255, 255)') {
                                return true;
                            }
                            return false;
                        };

                        const matchesLabel = (node, expected) => {
                            const text = normalize(node.innerText || '');
                            return exactStatusPattern(expected).test(text);
                        };

                        const candidates = Array.from(document.querySelectorAll('a, button, div, span, li')).filter((node) => {
                            if (!visible(node)) return false;
                            const text = normalize(node.innerText || '');
                            return STATUS_LABELS.some((status) => exactStatusPattern(status).test(text));
                        });

                        const scoreNode = (node) => {
                            let score = 0;
                            let current = node.parentElement;
                            for (let depth = 0; current && depth < 4; depth += 1, current = current.parentElement) {
                                const family = normalize(current.innerText || '');
                                const familyHits = STATUS_LABELS.filter((status) => family.includes(normalize(status))).length;
                                score = Math.max(score, familyHits);
                            }
                            return score;
                        };

                        const target = candidates
                            .filter((node) => matchesLabel(node, label))
                            .sort((left, right) => scoreNode(right) - scoreNode(left))[0];

                        if (!target) {
                            return { found: false, active: false, clicked: false };
                        }

                        const active = isActive(target);
                        if (!active) {
                            target.click();
                        }

                        return { found: true, active, clicked: !active };
                    }''',
                    tab_label,
                )
            except Exception:
                state = None

            if not state:
                time.sleep(0.3)
                continue

            if state.get('active'):
                return True

            if state.get('clicked'):
                last_clicked = True
                time.sleep(0.8)
                continue

            if state.get('found'):
                time.sleep(0.3)
                continue

            time.sleep(0.3)

        return last_clicked

    def _search_source_item(self, source_item_id: str, timeout: float = 20.0, tab_label: Optional[str] = None) -> bool:
        self._close_popups()

        selected = None
        if tab_label:
            selected = self._ensure_status_tab(tab_label, timeout=4.0)

        input_selector = self.page.evaluate(
            r'''() => {
                const visible = (el) => !!el && el.offsetParent !== null;
                const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                const wrappers = Array.from(document.querySelectorAll('.el-form-item, .el-input, .search-item, .filter-item'));
                const marker = 'data-copilot-source-search-input';

                for (const existing of document.querySelectorAll(`[${marker}]`)) {
                    existing.removeAttribute(marker);
                }

                const findInput = () => {
                    for (const wrapper of wrappers) {
                        if (!visible(wrapper)) continue;
                        const text = normalize(wrapper.innerText || '');
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
                if (!input) return null;
                input.setAttribute(marker, '1');
                return `input[${marker}="1"]`;
            }'''
        )

        filled = False
        if input_selector:
            try:
                input = self.page.locator(input_selector).first
                input.click(timeout=2000)
                input.fill('')
                input.type(str(source_item_id), delay=50)
                input.press('Tab')
                time.sleep(0.5)
                current_value = input.input_value(timeout=2000).strip()
                filled = current_value == str(source_item_id)
                if not filled:
                    logger.warning(f'货源ID输入框回填校验失败: expected={source_item_id}, actual={current_value}, tab={tab_label}')
            except Exception as exc:
                logger.warning(f'货源ID输入框填充失败: source_item_id={source_item_id}, tab={tab_label}, error={exc}')
                filled = False

        if not filled:
            logger.warning(f'货源ID搜索框未命中: source_item_id={source_item_id}, tab={tab_label}')
            self.screenshot('source_search_input_not_found')
            return False

        logger.info(f'采集箱搜索已提交: tab={tab_label}, tab_selected={selected}, source_item_id={source_item_id}')

        search_selector = self.page.evaluate(
            r'''() => {
                const visible = (el) => !!el && el.offsetParent !== null;
                const normalize = (text) => (text || '').replace(/\s+/g, '').trim();
                const marker = 'data-copilot-source-search-button';

                for (const existing of document.querySelectorAll(`[${marker}]`)) {
                    existing.removeAttribute(marker);
                }

                const input = document.querySelector('input[data-copilot-source-search-input="1"]');
                if (!input) return null;
                const inputRect = input.getBoundingClientRect();

                const buttons = Array.from(document.querySelectorAll('button, .el-button, a, span, div')).filter((node) => {
                    if (!visible(node)) return false;
                    return normalize(node.innerText || '') === '搜索';
                });
                if (!buttons.length) return null;

                buttons.sort((left, right) => {
                    const leftRect = left.getBoundingClientRect();
                    const rightRect = right.getBoundingClientRect();
                    const leftScore = Math.abs(leftRect.top - inputRect.top) + Math.abs(leftRect.left - inputRect.right);
                    const rightScore = Math.abs(rightRect.top - inputRect.top) + Math.abs(rightRect.left - inputRect.right);
                    return leftScore - rightScore;
                });

                const target = buttons[0];
                target.setAttribute(marker, '1');
                return `[${marker}="1"]`;
            }'''
        )

        clicked = False
        if search_selector:
            try:
                self.page.locator(search_selector).first.click(timeout=3000, force=True)
                clicked = True
            except Exception as exc:
                logger.warning(f'搜索按钮点击失败: source_item_id={source_item_id}, tab={tab_label}, error={exc}')
                clicked = False

        if not clicked:
            try:
                self.page.locator(input_selector).first.press('Enter')
                clicked = True
            except Exception:
                return False

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                body_text = self.page.inner_text('body')
            except Exception:
                body_text = ''

            row_hit = False
            try:
                row_hit = bool(self.page.evaluate(
                    r'''(sourceId) => {
                        const visible = (el) => !!el && el.offsetParent !== null;
                        const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                        const rowMarkers = ['货源:', '主货号:', '编辑', '发布', '删除', '1688'];
                        const hasRowContext = (text) => rowMarkers.some((marker) => text.includes(marker));

                        const nodes = Array.from(document.querySelectorAll('*')).filter((node) => {
                            const text = normalize(node.innerText || '');
                            return visible(node) && (text.includes(`(${String(sourceId)})`) || text.includes(String(sourceId)));
                        });

                        for (const node of nodes) {
                            let current = node;
                            for (let depth = 0; current && depth < 10; depth += 1, current = current.parentElement) {
                                const text = normalize(current.innerText || '');
                                if (hasRowContext(text) && text.includes(String(sourceId))) {
                                    return true;
                                }
                                if (depth >= 2 && text.includes(String(sourceId)) && text.length <= 1200) {
                                    return true;
                                }
                            }
                        }
                        return false;
                    }''',
                    str(source_item_id),
                ))
            except Exception:
                row_hit = False

            if str(source_item_id) in body_text and row_hit:
                logger.info(f'采集箱搜索命中结果行: tab={tab_label}, source_item_id={source_item_id}')
                return True
            if '暂无数据' in body_text or '共0条' in body_text:
                break

            time.sleep(0.5)

        logger.warning(f'采集箱搜索未命中: tab={tab_label}, source_item_id={source_item_id}')
        self.screenshot('source_search_no_result')
        return False

    def _click_edit_for_source_id(self, source_item_id: str, tab_label: Optional[str] = None) -> bool:
        logger.info(f"尝试按货源ID定位商品并打开编辑框: source_item_id={source_item_id}, tab={tab_label}")
        try:
            if not self._search_source_item(source_item_id, tab_label=tab_label):
                return False
            clicked = self.page.evaluate(
                r"""(sourceId) => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                    const dispatchClick = (node) => {
                        node.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                        node.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                        node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                        node.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                        if (node instanceof HTMLElement) node.click();
                    };

                    const rows = Array.from(document.querySelectorAll('tr, .el-table__row, .el-table__body tr, .jx-pro-virtual-table__row, li, .item, .item-row, [class*="row"]'));
                    for (const row of rows) {
                        if (!visible(row)) continue;
                        const rowText = normalize(row.innerText || '');
                        if (!rowText.includes(sourceId) || !rowText.includes('编辑')) continue;

                        const candidates = Array.from(row.querySelectorAll('button.J_shopeeCollectBoxEdit, button, a, span, div'));
                        for (const candidate of candidates) {
                            if (!visible(candidate)) continue;
                            if (normalize(candidate.innerText) !== '编辑') continue;
                            dispatchClick(candidate);
                            return true;
                        }
                    }

                    const buttons = Array.from(document.querySelectorAll('button, a, span, div'));
                    for (const button of buttons) {
                        if (!visible(button)) continue;
                        if (normalize(button.innerText) !== '编辑') continue;

                        let container = button.parentElement;
                        for (let depth = 0; container && depth < 10; depth++, container = container.parentElement) {
                            const text = normalize(container.innerText || '');
                            if (text.includes(sourceId)) {
                                dispatchClick(button);
                                return true;
                            }
                        }
                    }
                    return false;
                }""",
                str(source_item_id),
            )
            return bool(clicked)
        except Exception:
            return False

    def _count_visible_editable_rows(self) -> int:
        try:
            return int(self.page.evaluate(
                r"""() => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                    const rowSelectors = [
                        'tr',
                        '.el-table__row',
                        '.el-table__body tr',
                        '.jx-pro-virtual-table__row',
                        'li',
                        '.item',
                        '.item-row',
                    ];
                    const rows = Array.from(document.querySelectorAll(rowSelectors.join(',')));
                    let count = 0;
                    for (const row of rows) {
                        if (!visible(row)) continue;
                        const text = normalize(row.innerText || '');
                        if (!text.includes('编辑')) continue;
                        if (!(text.includes('1688') || text.includes('货源') || text.includes('主货号') || text.includes('搜1688同款'))) continue;
                        count += 1;
                    }
                    return count;
                }"""
            ))
        except Exception:
            return 0

    def _click_edit_by_index(self, product_index: int) -> bool:
        try:
            clicked = self.page.evaluate(
                r"""(targetIndex) => {
                    const visible = (el) => !!el && el.offsetParent !== null;
                    const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                    const dispatchClick = (node) => {
                        node.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                        node.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                        node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                        node.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                        if (node instanceof HTMLElement) node.click();
                    };

                    const rowSelectors = [
                        'tr',
                        '.el-table__row',
                        '.el-table__body tr',
                        '.jx-pro-virtual-table__row',
                        'li',
                        '.item',
                        '.item-row',
                    ];
                    const rows = Array.from(document.querySelectorAll(rowSelectors.join(',')));
                    let matchedIndex = 0;

                    for (const row of rows) {
                        if (!visible(row)) continue;
                        const text = normalize(row.innerText || '');
                        if (!text.includes('编辑')) continue;
                        if (!(text.includes('1688') || text.includes('货源') || text.includes('主货号') || text.includes('搜1688同款'))) continue;
                        if (matchedIndex !== Number(targetIndex)) {
                            matchedIndex += 1;
                            continue;
                        }

                        const candidates = Array.from(row.querySelectorAll('button.J_shopeeCollectBoxEdit, button, a, span, div'));
                        for (const candidate of candidates) {
                            if (!visible(candidate)) continue;
                            if (normalize(candidate.innerText) !== '编辑') continue;
                            dispatchClick(candidate);
                            return true;
                        }
                        return false;
                    }
                    return false;
                }""",
                int(product_index),
            )
            return bool(clicked)
        except Exception:
            return False

    def _wait_for_edit_dialog(self, timeout=10):
        """等待编辑对话框出现"""
        start = time.time()
        while time.time() - start < timeout:
            dialogs = self.page.query_selector_all('.el-dialog__wrapper, .el-dialog, .el-overlay-dialog, [role="dialog"]')
            for d in dialogs:
                try:
                    if not d.is_visible():
                        continue
                    cls = d.get_attribute('class') or ''
                    text = re.sub(r'\s+', ' ', d.inner_text() or '')
                    box = d.bounding_box() or {}
                    if box.get('width', 0) < 400 or box.get('height', 0) < 250:
                        continue
                    if 'collect-box-edit' in cls:
                        return d
                    if any(keyword in text for keyword in ['货源链接', '货源ID', '主货号', '产品图片', '商品图片', '规格图片', '详情图片']):
                        return d
                except Exception:
                    continue
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

        tab_targets = {
            '商品图片': 'main_images',
            '产品图片': 'main_images',
            '规格图片': 'sku_images',
            'SKU图片': 'sku_images',
            '详情图片': 'detail_images',
            '详情描述': 'detail_images',
        }

        def match_tab_label(raw_text: str) -> Optional[str]:
            normalized = re.sub(r'\s+', '', raw_text or '')
            if not normalized:
                return None
            for tab_name in tab_targets:
                if normalized.startswith(tab_name):
                    return tab_name
            return None

        def is_product_image_url(url: str) -> bool:
            if not url or url.startswith('data:'):
                return False
            if not re.match(r'^https?://', url):
                return False
            if 'static_common/image/shop/' in url:
                return False
            return True

        def is_sidebar_thumbnail(url: str) -> bool:
            if '/0/cibi/' in url or 'thumb' in url.lower():
                return True
            return False

        def collect_visible_images() -> List[str]:
            urls: List[str] = []
            for img in dialog.query_selector_all('img'):
                try:
                    box = img.bounding_box()
                    if not box or box.get('width', 0) < 40 or box.get('height', 0) < 40:
                        continue

                    src = img.get_attribute('src') or img.get_attribute('data-src') or ''
                    if not is_product_image_url(src):
                        continue
                    if is_sidebar_thumbnail(src) or src in urls:
                        continue
                    urls.append(src)
                except Exception:
                    pass
            return urls

        try:
            tab_map = {}
            selectors = '.el-tabs__item, [role="tab"], .tab-item, .jx-tabs__item, span, div, button, li'
            for element in dialog.query_selector_all(selectors):
                try:
                    text = match_tab_label(element.inner_text() or '')
                    if text not in tab_targets:
                        continue
                    box = element.bounding_box()
                    if not box or box.get('width', 0) <= 0 or box.get('height', 0) <= 0:
                        continue
                    if text not in tab_map:
                        tab_map[text] = element
                except Exception:
                    pass

            logger.info(f"图片Tab候选: {list(tab_map.keys())}")

            if not tab_map:
                return result

            for tab_name in ['产品图片', '商品图片', '规格图片', '详情图片', '详情描述']:
                if tab_name not in tab_map:
                    continue

                try:
                    tab_selector = tab_map[tab_name]
                    self.page.evaluate("(el) => el.click()", tab_selector)
                    time.sleep(1)
                    imgs_info = collect_visible_images()

                    target_field = tab_targets[tab_name]
                    result[target_field] = imgs_info

                    logger.info(f"  {tab_name}: {len(imgs_info)} 张图片")

                except Exception as e:
                    logger.warning(f"提取{tab_name}图片失败: {e}")

            reset_tab = '产品图片' if '产品图片' in tab_map else '商品图片'
            if reset_tab in tab_map:
                try:
                    self.page.evaluate("(el) => el.click()", tab_map[reset_tab])
                    time.sleep(0.5)
                except Exception:
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

    def scrape_product(self, product_index=0, source_item_id: Optional[str] = None, allow_index_fallback: bool = False) -> Optional[Dict[str, Any]]:
        """
        爬取指定索引商品的完整数据

        Args:
            product_index: 商品在列表中的索引（从0开始）
            source_item_id: 指定货源ID，优先按该商品定位

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
        logger.info(f"爬取商品 (index={product_index}, source_item_id={source_item_id})...")

        # 访问采集箱
        self.page.goto(SHOPEE_COLLECT_URL, wait_until='domcontentloaded')
        time.sleep(5)
        self._close_popups()
        self.screenshot('list_before_edit')

        clicked = False
        dialog = None
        if source_item_id:
            for tab_label in ['已发布', '全部']:
                self._close_popups()
                clicked = self._click_edit_for_source_id(str(source_item_id), tab_label=tab_label)
                if not clicked:
                    time.sleep(1.5)
                    continue

                dialog = self._wait_for_edit_dialog(timeout=6)
                if dialog:
                    logger.info(f"在“{tab_label}”列表中命中商品 {source_item_id}")
                    break
                logger.warning(f"在“{tab_label}”列表中点击了编辑，但未等到采集箱编辑弹窗: {source_item_id}")
                time.sleep(1.5)
            if not clicked:
                if not allow_index_fallback:
                    logger.error(f"未按货源ID找到商品 {source_item_id}，严格模式下停止，不回退到索引模式")
                    return None
                logger.warning(f"未按货源ID找到商品 {source_item_id}，回退到索引模式")

        if not clicked:
            visible_rows = self._count_visible_editable_rows()
            if visible_rows <= 0:
                logger.error('当前列表没有可见商品行，停止索引回退')
                self.screenshot('error_no_visible_rows')
                return None
            if product_index >= visible_rows:
                logger.error(f"没有找到索引为 {product_index} 的商品")
                return None

            logger.info(f"点击第 {product_index + 1} 个商品的编辑按钮")
            if not self._click_edit_by_index(product_index):
                logger.error(f"索引模式点击第 {product_index + 1} 个商品失败")
                self.screenshot('error_index_click_failed')
                return None

        # 等待编辑对话框
        if not dialog:
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

            def is_product_image_url(url: str) -> bool:
                if not url or url.startswith('data:'):
                    return False
                if not re.match(r'^https?://', url):
                    return False
                if 'static_common/image/shop/' in url:
                    return False
                return True

            def is_sidebar_thumbnail(url: str) -> bool:
                if '/0/cibi/' in url or 'thumb' in url.lower():
                    return True
                return False

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

            # 如果有图片，继续分类
            if all_imgs:
                for img in all_imgs:
                    try:
                        src = img.get_attribute('src') or ''
                        if not is_product_image_url(src):
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
                            if is_product_image_url(src):
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

            if not data['sku_images']:
                sku_image_urls = []
                for sku in skus:
                    image_url = sku.get('image')
                    if isinstance(image_url, str) and image_url.startswith(('http://', 'https://')) and image_url not in sku_image_urls:
                        sku_image_urls.append(image_url)
                data['sku_images'] = sku_image_urls

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
                        rowSkus: [],
                        colorImages: {},
                        overallPrice: null,
                        overallStock: null,
                        debug: {}
                    };

                    const visible = (el) => !!el && el.offsetParent !== null;
                    
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
                    // 保留原始顺序和重复价格，避免同价SKU被错误折叠导致数量对不上
                    result.allPrices = allPrices;
                    
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
                    
                    // 2.5 尝试查找妙手编辑对话框中的SKU表格
                    const specPriceMap = {};
                    
                    // 方法1：查找SKU编辑表格中的行（包含规格名称和价格）
                    // 妙手ERP的SKU表格通常在 el-table 或类似表格容器中
                    const skuTableRows = document.querySelectorAll('.el-table__body-wrapper tr, .sku-table tr, [class*="sku"] tr, table tbody tr');
                    skuTableRows.forEach(function(row) {
                        const cells = row.querySelectorAll('td, .cell');
                        if (cells.length >= 2) {
                            let specName = '';
                            let price = null;
                            cells.forEach(function(cell) {
                                const text = cell.innerText || '';
                                // 价格通常在单元格内，可能是 "¥26.8" 或 "26.8" 格式
                                const priceMatch = text.match(/(\d+\.?\d*)/);
                                if (priceMatch && parseFloat(priceMatch[1]) > 0 && parseFloat(priceMatch[1]) < 10000) {
                                    // 排除明显的非价格数字（如库存数量>1000的）
                                    const num = parseFloat(priceMatch[1]);
                                    if (num > 0 && num < 100 && !text.includes('库存') && !text.includes('stock')) {
                                        if (!price) {
                                            price = num;
                                        }
                                    }
                                }
                                // 规格名称通常在第一个或前面的单元格
                                if (text.trim() && text.trim().length > 1 && text.trim().length < 50) {
                                    if (!specName || specName.length < text.trim().length) {
                                        const cleanText = text.trim().replace(/\n.*$/, '').substring(0, 30);
                                        if (cleanText.length > 1 && !/^\d+$/.test(cleanText)) {
                                            specName = cleanText;
                                        }
                                    }
                                }
                            });
                            if (specName && price) {
                                // 清理规格名称，移除价格后缀
                                specName = specName.replace(/[\d.]+$/, '').trim();
                                if (specName.length > 1) {
                                    specPriceMap[specName] = price;
                                }
                            }
                        }
                    });
                    
                    // 方法2：查找表格单元格中的价格-规格配对
                    const priceCells = document.querySelectorAll('td[class*="price"], td[class*="amount"], .cell-price');
                    priceCells.forEach(function(cell) {
                        const text = cell.innerText || '';
                        const priceMatch = text.match(/(\d+\.?\d*)/);
                        if (priceMatch && parseFloat(priceMatch[1]) > 0 && parseFloat(priceMatch[1]) < 100) {
                            const row = cell.closest('tr');
                            if (row) {
                                const firstCell = row.querySelector('td:first-child, .cell-name');
                                if (firstCell) {
                                    let specName = firstCell.innerText.trim().split('\n')[0].substring(0, 30);
                                    if (specName && specName.length > 1) {
                                        specPriceMap[specName] = parseFloat(priceMatch[1]);
                                    }
                                }
                            }
                        }
                    });
                    
                    result.specPriceMap = specPriceMap;

                    // 2.6 直接从SKU表格可见行提取完整规格名、价格和库存。
                    // 已发布商品页里价格经常只在表格行文本中完整可见，
                    // 仅靠输入框推断会漏掉后半段规格或把截断名重复展开。
                    const rowSkus = [];
                    const rowSelectors = [
                        '.el-table__body-wrapper tbody tr',
                        '.el-table__body tr',
                        'table tbody tr'
                    ];
                    const rowSeen = new Set();

                    const parseRowPrice = (text) => {
                        const directMatch = text.match(/¥\s*([0-9]+(?:\.[0-9]+)?)/);
                        if (directMatch) return parseFloat(directMatch[1]);

                        const stockAnchoredMatch = text.match(/([0-9]+(?:\.[0-9]+)?)\s+库存\s*[0-9]+\s*台/);
                        if (stockAnchoredMatch) return parseFloat(stockAnchoredMatch[1]);
                        return null;
                    };

                    const parseRowStock = (text) => {
                        const stockMatch = text.match(/库存\s*([0-9]+)\s*台/);
                        return stockMatch ? parseInt(stockMatch[1], 10) : null;
                    };

                    const sanitizeRowName = (text) => {
                        let name = text.replace(/\s+/g, ' ').trim();
                        name = name.replace(/¥\s*[0-9]+(?:\.[0-9]+)?[\s\S]*$/, '').trim();
                        name = name.replace(/[+-]\s*0\s*[+-]?\s*$/, '').trim();
                        return name;
                    };

                    rowSelectors.forEach(function(selector) {
                        document.querySelectorAll(selector).forEach(function(row) {
                            if (!visible(row)) return;

                            const rowText = (row.innerText || '').replace(/\u00A0/g, ' ');
                            if (!rowText || rowText.indexOf('库存') === -1) return;

                            const normalizedText = rowText.replace(/\s+/g, ' ').trim();
                            if (!normalizedText || rowSeen.has(normalizedText)) return;

                            const price = parseRowPrice(normalizedText);
                            const stock = parseRowStock(normalizedText);
                            const name = sanitizeRowName(normalizedText);

                            if (!name || name.length < 2 || price === null || !stock) return;
                            if (name.includes('货源价格') || name.includes('全球价格') || name.includes('全球库存')) return;

                            rowSeen.add(normalizedText);
                            rowSkus.push({
                                name: name,
                                price: price,
                                stock: stock,
                            });
                        });
                    });

                    result.rowSkus = rowSkus;
                    
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
                    
                    // 3. 查找 SKU 图片区域，优先按 sku-picture-item 的名称节点做 1:1 提取，避免把产品图尺寸误识别成 SKU 名。
                    const normalizeSkuName = (value) => {
                        return (value || '').replace(/[\u00A0\s\n\r]+/g, ' ').trim();
                    };

                    const isNoiseSkuName = (value) => {
                        const normalized = normalizeSkuName(value);
                        if (!normalized || normalized.length > 40) return true;
                        if (normalized.indexOf('请选择') !== -1 || normalized.indexOf('搜索') !== -1 || normalized.indexOf('图片') !== -1) return true;
                        if (normalized === 'AI' || normalized === 'CNY') return true;
                        const compact = normalized.replace(/\s+/g, '');
                        if (/^\d+(?:x\d+)+$/i.test(compact)) return true;
                        if (/^\d+[xX＊*]\d+$/.test(compact)) return true;
                        if (/^[\d\sxX＊*I]+$/.test(compact) && compact.replace(/[\dxX＊*I]/gi, '').length === 0) return true;
                        return false;
                    };

                    const resolveSkuImageUrl = (node) => {
                        let current = node;
                        for (let depth = 0; current && depth < 4; depth += 1, current = current.parentElement) {
                            const imgEl = current.querySelector('.sku-picture-item.image-item .el-image__inner, .sku-picture-item.image-item img, .el-image__inner, img');
                            if (!imgEl) continue;
                            const imgUrl = imgEl.src || imgEl.getAttribute('data-src') || '';
                            if (imgUrl && imgUrl.indexOf('alicdn') !== -1) {
                                return imgUrl;
                            }
                        }
                        return '';
                    };

                    const skuNameNodes = Array.from(document.querySelectorAll('.sku-picture-item.name, .sku-picture-name, [class*="sku-picture"] [class*="name"]')).filter(visible);
                    skuNameNodes.forEach(function(nameNode) {
                        const name = normalizeSkuName(nameNode.innerText || nameNode.textContent || '');
                        if (isNoiseSkuName(name)) return;

                        const imgUrl = resolveSkuImageUrl(nameNode);
                        if (!imgUrl) return;

                        if (!result.colorImages[name]) {
                            result.colorImages[name] = imgUrl;
                        }
                    });

                    if (Object.keys(result.colorImages).length === 0) {
                        const imageBlocks = Array.from(document.querySelectorAll('.sku-picture-item-wrap, .sku-picture-wrap-item, .sku-picture-item')).filter(visible);
                        imageBlocks.forEach(function(block) {
                            const imgUrl = resolveSkuImageUrl(block);
                            if (!imgUrl) return;

                            let name = '';
                            const directNameEl = block.querySelector('.sku-picture-item.name, .sku-picture-name, .name, [class*="name"]');
                            if (directNameEl) {
                                name = normalizeSkuName(directNameEl.innerText || directNameEl.textContent || '');
                            }

                            if (!name) {
                                let container = block.parentElement;
                                for (let depth = 0; container && depth < 3 && !name; depth += 1, container = container.parentElement) {
                                    const siblingNameEl = container.querySelector('.sku-picture-item.name, .sku-picture-name');
                                    if (siblingNameEl) {
                                        name = normalizeSkuName(siblingNameEl.innerText || siblingNameEl.textContent || '');
                                    }
                                }
                            }

                            if (!isNoiseSkuName(name) && !result.colorImages[name]) {
                                result.colorImages[name] = imgUrl;
                            }
                        });
                    }
                    
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
                row_skus = js_result.get('rowSkus', [])
                all_prices = js_result.get('allPrices', [])
                spec_price_map = js_result.get('specPriceMap', {})
                price = js_result.get('overallPrice')
                stock = js_result.get('overallStock')
                valid_stocks = js_result.get('debug', {}).get('validStocks', [])

                logger.info(f"有效库存: {valid_stocks}, 颜色数: {len(color_images)}, 所有价格: {all_prices}")
                logger.info(f"规格价格映射: {spec_price_map}")
                if row_skus:
                    logger.info(f"表格行直提SKU: {row_skus}")

                def clean_spec_label(value: Any) -> str:
                    text = str(value or '').replace('\n', '').replace('\r', '').strip()
                    if not text:
                        return ''
                    return re.split(r'[：:]', text, maxsplit=1)[0].strip()

                def normalize_visible_sku_name(value: Any, sku_price: Any = None) -> str:
                    text = str(value or '')
                    text = text.replace('\u00A0', ' ')
                    text = re.sub(r'[\s\u200b\ufeff]+', '', text)
                    text = re.sub(r'-\d+$', '', text)

                    if text.endswith('【承重180'):
                        text += '斤】'
                    elif text.endswith('【承重300'):
                        text += '斤】'
                    elif text.startswith('7寸轮') and '7CM越野双刹' in text and '承重' not in text:
                        prefix = text.split('7CM越野双刹')[0]
                        suffix = '500斤】' if sku_price == 132 else '400斤】'
                        text = f'{prefix}7CM越野双刹轮【承重{suffix}'
                    elif text.startswith('7寸坦克轮') and '10CM越野' in text:
                        prefix = text.split('10CM越野')[0]
                        text = f'{prefix}10CM越野双刹轮【承重400斤】'

                    text = re.sub(r'(刹轮【承重400斤】)+', '刹轮【承重400斤】', text)

                    return text

                def finalize_sku_name(sku_name: str, spec_name: str = '') -> str:
                    normalized = normalize_visible_sku_name(sku_name)
                    if spec_name and '适用人数' in spec_name and re.search(r'-(\d+-\d+)$', normalized):
                        normalized += '人'
                    return normalized

                def normalize_price_group_label(value: Any) -> str:
                    cleaned = clean_spec_label(value)
                    if not cleaned:
                        return ''
                    return re.sub(r'-\d+$', '', cleaned).strip()

                def infer_group_key_candidates(value: Any) -> List[str]:
                    cleaned = normalize_price_group_label(value)
                    if not cleaned:
                        return []

                    segments = [segment.strip() for segment in re.split(r'[-/|｜]', cleaned) if segment.strip()]
                    candidates = [cleaned]
                    if len(segments) > 1:
                        candidates.append('-'.join(segments[:-1]))
                        candidates.append(segments[0])

                    deduped = []
                    for candidate in candidates:
                        if candidate and candidate not in deduped:
                            deduped.append(candidate)
                    return deduped

                def build_price_group_map(labels: List[Any], prices: List[Any]) -> Dict[str, Any]:
                    if not labels or not prices:
                        return {}

                    candidate_groups = []
                    for idx in range(3):
                        grouped = []
                        for label in labels:
                            candidates = infer_group_key_candidates(label)
                            grouped.append(candidates[idx] if idx < len(candidates) else '')
                        candidate_groups.append(grouped)

                    for grouped in candidate_groups:
                        ordered_groups = []
                        for group in grouped:
                            if group and group not in ordered_groups:
                                ordered_groups.append(group)
                        if len(ordered_groups) == len(prices):
                            return {group: prices[idx] for idx, group in enumerate(ordered_groups)}

                    # 已发布商品页常把同一规格截断为 "xxx-2/xxx-3" 这样的重复标签，
                    # 此时价格数组通常只保留每组一次价格，需要按块重复映射。
                    for grouped in candidate_groups:
                        if len(grouped) <= len(prices) or len(grouped) % len(prices) != 0:
                            continue

                        block_size = len(grouped) // len(prices)
                        block_map: Dict[str, Any] = {}
                        valid = True

                        for idx, group in enumerate(grouped):
                            normalized_group = normalize_price_group_label(group)
                            if not normalized_group:
                                valid = False
                                break

                            expected_price = prices[idx // block_size]
                            existing_price = block_map.get(normalized_group)
                            if existing_price is None:
                                block_map[normalized_group] = expected_price
                            elif existing_price != expected_price:
                                valid = False
                                break

                        if valid and len(block_map) == len(prices):
                            return block_map

                    return {}

                def resolve_price_from_map(label: Any, price_map: Dict[str, Any], fallback_price: Any) -> Any:
                    if not price_map:
                        return fallback_price

                    for candidate in infer_group_key_candidates(label):
                        if candidate in price_map:
                            return price_map[candidate]

                    return fallback_price

                def match_color_image_for_name(sku_name: Any) -> tuple[str, Optional[str]]:
                    normalized_name = normalize_visible_sku_name(sku_name)
                    if not normalized_name or not color_images:
                        return '', None

                    normalized_map = []
                    for color_name, image_url in color_images.items():
                        normalized_color = normalize_visible_sku_name(color_name)
                        if normalized_color:
                            normalized_map.append((normalized_color, color_name, image_url))

                    normalized_map.sort(key=lambda item: len(item[0]), reverse=True)

                    for normalized_color, original_color, image_url in normalized_map:
                        if normalized_color and normalized_color in normalized_name:
                            return original_color, image_url

                    return '', None

                def collect_scrolled_row_skus() -> List[Dict[str, Any]]:
                    selector = self.page.evaluate(r'''() => {
                        const visible = (el) => !!el && el.offsetParent !== null;
                        const marker = 'data-copilot-sku-scroll-root';

                        for (const node of document.querySelectorAll(`[${marker}]`)) {
                            node.removeAttribute(marker);
                        }

                        const mainScroll = document.querySelector('.scroll-menu-wrap');
                        if (mainScroll && mainScroll.scrollHeight > mainScroll.clientHeight + 80) {
                            mainScroll.setAttribute(marker, '1');
                            return `[${marker}="1"]`;
                        }

                        const optionInputs = Array.from(document.querySelectorAll('input')).filter((input) => {
                            return visible(input)
                                && (input.getAttribute('placeholder') || '') === '请输入选项名称'
                                && (input.value || '').trim();
                        });

                        if (!optionInputs.length) return null;

                        let current = optionInputs[0].parentElement;
                        while (current) {
                            if (current.scrollHeight > current.clientHeight + 80) {
                                current.setAttribute(marker, '1');
                                return `[${marker}="1"]`;
                            }
                            current = current.parentElement;
                        }

                        document.body.setAttribute(marker, '1');
                        return `[${marker}="1"]`;
                    }''')

                    if not selector:
                        return []

                    collected: List[Dict[str, Any]] = []
                    seen_keys = set()
                    stagnant_rounds = 0
                    previous_count = 0

                    for _ in range(12):
                        snapshot = self.page.evaluate(r'''(rootSelector) => {
                            const visible = (el) => !!el && el.offsetParent !== null;
                            const root = document.querySelector(rootSelector);
                            if (!root) return {names: [], prices: [], atBottom: true};

                            const names = Array.from(document.querySelectorAll('input')).filter((input) => {
                                return visible(input)
                                    && (input.getAttribute('placeholder') || '') === '请输入选项名称'
                                    && (input.value || '').trim();
                            }).map((input) => (input.value || '').replace(/\s+/g, ' ').trim());

                            const prices = Array.from(document.querySelectorAll('.price-input input, .jx-pro-input.price-input input.el-input__inner')).filter((input) => {
                                if (!visible(input)) return false;
                                const raw = (input.value || '').replace(/[^\d.]/g, '');
                                if (!raw) return false;
                                const num = parseFloat(raw);
                                return Number.isFinite(num) && num > 0 && num < 10000;
                            }).map((input) => parseFloat((input.value || '').replace(/[^\d.]/g, '')));

                            return {
                                names,
                                prices,
                                atBottom: root.scrollTop + root.clientHeight >= root.scrollHeight - 8,
                            };
                        }''', selector)

                        names = snapshot.get('names', [])
                        prices = snapshot.get('prices', [])
                        pair_count = min(len(names), len(prices))
                        for idx in range(pair_count):
                            sku_name = normalize_visible_sku_name(names[idx], prices[idx])
                            sku_price = prices[idx]
                            if not sku_name:
                                continue
                            dedupe_key = f"{sku_name}|{sku_price}"
                            if dedupe_key in seen_keys:
                                continue
                            seen_keys.add(dedupe_key)
                            collected.append({
                                'name': sku_name,
                                'price': sku_price,
                                'stock': None,
                            })

                        if len(collected) == previous_count:
                            stagnant_rounds += 1
                        else:
                            stagnant_rounds = 0
                            previous_count = len(collected)

                        if snapshot.get('atBottom') or stagnant_rounds >= 2:
                            break

                        self.page.evaluate(r'''(rootSelector) => {
                            const root = document.querySelector(rootSelector);
                            if (!root) return;
                            root.scrollTop = Math.min(
                                root.scrollTop + Math.max(root.clientHeight - 80, 120),
                                root.scrollHeight
                            );
                        }''', selector)
                        time.sleep(0.5)

                    return collected

                if not row_skus and not color_images:
                    row_skus = collect_scrolled_row_skus()
                    if row_skus:
                        logger.info(f"滚动采集SKU行结果: {row_skus}")

                if row_skus and len(row_skus) >= max(len(all_prices), 2):
                    mapped_row_sku_images = 0
                    for row_sku in row_skus:
                        sku_name = normalize_visible_sku_name(row_sku.get('name'), row_sku.get('price', price))
                        if not sku_name:
                            continue
                        matched_color, matched_image = match_color_image_for_name(sku_name)
                        if matched_image:
                            mapped_row_sku_images += 1
                        sku_stock = row_sku.get('stock') or (valid_stocks[0] if valid_stocks else None) or stock or 99999
                        skus.append({
                            'name': sku_name,
                            'color': matched_color,
                            'size': normalize_visible_sku_name(clean_spec_label(sku_name), row_sku.get('price', price)),
                            'price': row_sku.get('price', price),
                            'stock': sku_stock,
                            'image': matched_image
                        })

                    if skus:
                        logger.info("使用表格行直提SKU结果，跳过规格推断映射")
                        logger.info(f"表格行SKU图片映射: {mapped_row_sku_images}/{len(skus)}")
                        logger.info(f"提取到 {len(skus)} 个SKU")
                        for sku in skus:
                            logger.info(f"  SKU: {sku}")
                        return skus

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
                    all_combinations = []
                    
                    if spec_names:
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
                        combination_labels = []

                        for combo in all_combinations:
                            label = combo.get(spec_names[0], '') if spec_names else ''
                            combination_labels.append(clean_spec_label(label))

                        combination_price_map = build_price_group_map(combination_labels, prices_to_use)
                        
                        for idx, combo in enumerate(all_combinations):
                            size_name = combo.get(spec_names[0], '') if spec_names else ''
                            size_name = clean_spec_label(size_name)
                            
                            # 尝试从spec_price_map获取对应价格
                            sku_price = price
                            if spec_price_map:
                                for spec_key, spec_val in spec_price_map.items():
                                    if size_name and size_name in str(spec_key):
                                        sku_price = spec_val
                                        break
                            elif combination_price_map:
                                sku_price = resolve_price_from_map(size_name, combination_price_map, price)
                            elif len(prices_to_use) > 1:
                                # 根据规格索引进价（allPrices是按规格顺序的：[100L价格, 140L价格]）
                                # 如果size_name包含"100L"用第一个价格，包含"140L"用第二个价格
                                if '100L' in size_name:
                                    sku_price = prices_to_use[0]
                                elif '140L' in size_name:
                                    sku_price = prices_to_use[1] if len(prices_to_use) > 1 else prices_to_use[0]
                                else:
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
                        primary_spec_labels = []

                        non_color_spec_names = [name for name in spec_names if name != '颜色']
                        primary_spec_name = non_color_spec_names[0] if non_color_spec_names else ''

                        for combo in all_combinations:
                            if primary_spec_name:
                                primary_spec_labels.append(combo.get(primary_spec_name, ''))
                            else:
                                primary_spec_labels.append(list(combo.values())[0] if combo else '')

                        combination_price_map = build_price_group_map(primary_spec_labels, all_prices)
                        
                        for idx, combo in enumerate(all_combinations):
                            # 组合SKU名称：例如 "奶黄色-100L"
                            size_spec = combo.get(primary_spec_name, '') if primary_spec_name else ''
                            size_name = clean_spec_label(size_spec)
                            
                            color_name = combo.get('颜色', '')
                            combo_label = size_name or (list(combo.values())[0] if combo else '')
                            
                            # 构建完整SKU名称
                            if color_name and size_name:
                                sku_name = f"{color_name}-{size_name}"
                            elif size_name:
                                sku_name = size_name
                            else:
                                sku_name = list(combo.values())[0] if combo else f"SKU{idx+1}"
                            sku_name = finalize_sku_name(sku_name, primary_spec_name)
                            
                            # 分配库存（轮询分配）
                            sku_stock = valid_stocks[idx % len(valid_stocks)] if valid_stocks else (stock or 99999)
                            
                            # 分配价格：优先用all_prices，否则用统一price
                            if spec_price_map:
                                sku_price = resolve_price_from_map(combo_label, spec_price_map, price)
                            elif combination_price_map:
                                sku_price = resolve_price_from_map(combo_label, combination_price_map, price)
                            elif all_prices and len(all_prices) > 0:
                                sku_price = all_prices[idx] if idx < len(all_prices) else price
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
                logger.warning(f"提取SKU失败: {e}")
                import traceback
                traceback.print_exc()

            logger.info(f"提取到 {len(skus)} 个SKU")
            for sku in skus:
                logger.info(f"  SKU: {sku}")

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

        elif args.alibaba_id:
            data = scraper.scrape_product(args.scrape, source_item_id=args.alibaba_id, allow_index_fallback=False)
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
