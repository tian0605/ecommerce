#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


COOKIES_FILE = Path('/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json')
TMP_DIR = Path('/home/ubuntu/work/tmp/probe_publish_record')
TMP_DIR.mkdir(parents=True, exist_ok=True)
SHOPEE_COLLECT_URL = 'https://erp.91miaoshou.com/shopee/collect_box/items'
PUBLISH_RECORD_CANDIDATES = TMP_DIR / 'publish_record_candidates.json'


def load_cookies():
    with open(COOKIES_FILE, 'r', encoding='utf-8') as handle:
        data = json.load(handle)
    cookie_list = data if isinstance(data, list) else data.get('cookies', [])
    return [
        {
            'name': item['name'],
            'value': item['value'],
            'domain': item.get('domain', '.91miaoshou.com'),
            'path': item.get('path', '/'),
            'secure': item.get('secure', False),
            'httpOnly': item.get('httpOnly', False),
        }
        for item in cookie_list
    ]


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        context.add_cookies(load_cookies())
        page = context.new_page()
        page.goto(SHOPEE_COLLECT_URL, wait_until='domcontentloaded')
        time.sleep(5)

        for _ in range(5):
            try:
                close = page.locator('.el-dialog__headerbtn, .el-dialog__close, .el-icon-close').first
                if close.count() > 0:
                    close.click(force=True, timeout=1000)
            except Exception:
                pass
            page.keyboard.press('Escape')
            time.sleep(0.5)

        page.screenshot(path=str(TMP_DIR / 'before_publish_record.png'), full_page=True)

        link_candidates = page.evaluate(
            r'''() => {
                const visible = (el) => !!el && el.offsetParent !== null;
                return Array.from(document.querySelectorAll('a, button, div, span, li'))
                    .filter((node) => (node.innerText || '').includes('发布记录'))
                    .slice(0, 20)
                    .map((node) => ({
                        tag: node.tagName,
                        text: (node.innerText || '').trim(),
                        href: node.getAttribute('href'),
                        to: node.getAttribute('to'),
                        onclick: node.getAttribute('onclick'),
                        className: node.className,
                        visible: visible(node),
                        parentText: (node.parentElement?.innerText || '').trim().slice(0, 200),
                    }));
            }'''
        )
        PUBLISH_RECORD_CANDIDATES.write_text(json.dumps(link_candidates, ensure_ascii=False, indent=2), encoding='utf-8')
        print('publish_record_candidates_file=', str(PUBLISH_RECORD_CANDIDATES))

        publish_record = page.locator('.J_ShopeeMoveCollectHistory').first
        print('publish_record_count=', publish_record.count())
        if publish_record.count() > 0:
            page.evaluate(
                r'''() => {
                    const node = document.querySelector('.J_ShopeeMoveCollectHistory');
                    if (node) {
                        node.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                        node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                        node.click();
                    }
                }'''
            )
            time.sleep(4)

        print('current_url=', page.url)
        print('title=', page.title())
        page.screenshot(path=str(TMP_DIR / 'after_publish_record.png'), full_page=True)
        print('body_prefix=', page.locator('body').inner_text()[:2000].replace('\n', ' | '))

        edit_clicked = page.evaluate(
            r'''() => {
                for (const overlay of document.querySelectorAll('.el-dialog__wrapper, .el-dialog, .v-modal, .el-overlay, .el-overlay-dialog')) {
                    if (overlay instanceof HTMLElement) {
                        overlay.style.display = 'none';
                        overlay.remove();
                    }
                }
                const visible = (el) => !!el && el.offsetParent !== null;
                const normalize = (text) => (text || '').replace(/\s+/g, ' ').trim();
                const sourceId = '1031400982378';
                const rows = Array.from(document.querySelectorAll('tr, .el-table__row, .el-table__body tr, .jx-table-body-row, li, .list-item, .item-row, [class*="row"]'));
                for (const row of rows) {
                    const rowText = normalize(row.innerText || '');
                    if (!rowText.includes(sourceId) || !rowText.includes('编辑')) continue;
                    let target = row.querySelector('button, a, .el-button, span, div');
                    const clickables = Array.from(row.querySelectorAll('button, a, .el-button, span, div'));
                    for (const candidate of clickables) {
                        if (!visible(candidate)) continue;
                        if (normalize(candidate.innerText) === '编辑') {
                            target = candidate;
                            break;
                        }
                    }
                    if (!target) continue;
                    const dispatch = (node) => {
                        node.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                        node.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                        node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                        node.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                    };
                    dispatch(target);
                    if (target instanceof HTMLElement) target.click();
                    return true;
                }

                const buttons = Array.from(document.querySelectorAll('button, a, span, div'));
                for (const button of buttons) {
                    if (!visible(button)) continue;
                    if (normalize(button.innerText) !== '编辑') continue;
                    let container = button.parentElement;
                    for (let depth = 0; container && depth < 10; depth += 1, container = container.parentElement) {
                        const text = normalize(container.innerText || '');
                        if (text.includes(sourceId)) {
                            button.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                            button.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                            button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                            if (button instanceof HTMLElement) button.click();
                            return true;
                        }
                    }
                }
                return false;
            }'''
        )
        print('edit_clicked=', edit_clicked)
        if edit_clicked:
            time.sleep(4)
            page.screenshot(path=str(TMP_DIR / 'after_publish_record_edit.png'), full_page=True)
            print('body_after_edit_prefix=', page.locator('body').inner_text()[:3000].replace('\n', ' | '))
            print('dialog_count=', page.locator('.el-dialog__wrapper, .el-dialog, [role="dialog"]').count())

        browser.close()


if __name__ == '__main__':
    main()