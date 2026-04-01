#!/usr/bin/env python3
"""分析发布对话框中的按钮"""
import sys, time
from pathlib import Path
sys.path.insert(0, '/home/ubuntu/.openclaw/skills/shared')
sys.path.insert(0, '/home/ubuntu/.openclaw/skills/miaoshou-updater')
from fix_step6_guard import require_step6_guard
from updater import MiaoshouUpdater
from logger import setup_logger
import db

require_step6_guard(__file__, destructive=False)

logger = setup_logger('fix-step6-analyze')

TARGET_ID = '1026754677096'

def get_product(alibaba_id):
    with db.get_cursor() as cur:
        cur.execute("""
            SELECT id, product_id, alibaba_product_id, title, description,
                   optimized_title, optimized_description, status, category,
                   product_id_new
            FROM products WHERE alibaba_product_id = %s
        """, (alibaba_id,))
        row = cur.fetchone()
        if not row:
            return None
        product = {
            'id': row[0], 'product_id': row[1], 'alibaba_product_id': row[2],
            'title': row[3], 'description': row[4], 'optimized_title': row[5],
            'optimized_description': row[6], 'status': row[7], 'category': row[8],
            'product_id_new': row[9],
        }
        cur.execute("""
            SELECT package_weight, package_length, package_width, package_height
            FROM product_skus WHERE product_id = %s ORDER BY price ASC LIMIT 1
        """, (row[0],))
        sku_row = cur.fetchone()
        if sku_row:
            product['package_weight'] = float(sku_row[0]) if sku_row[0] else 0
            product['package_length'] = float(sku_row[1]) if sku_row[1] else 0
            product['package_width'] = float(sku_row[2]) if sku_row[2] else 0
            product['package_height'] = float(sku_row[3]) if sku_row[3] else 0
        return product

def main():
    product = get_product(TARGET_ID)
    if not product:
        print(f"❌ 商品 {TARGET_ID} 未找到")
        return
    
    updater = MiaoshouUpdater(headless=True)
    try:
        updater.launch()
        
        # 1. 访问采集箱
        updater.page.goto('https://erp.91miaoshou.com/shopee/collect_box/items', wait_until='domcontentloaded')
        time.sleep(5)
        updater._close_popups()
        time.sleep(2)
        
        # 2. 点击编辑
        with open('/tmp/js_click_edit.js', 'w') as f:
            f.write(f"""
(function() {{
    var views = document.querySelectorAll('.vue-recycle-scroller__item-view');
    for (var view of views) {{
        if (view.textContent.includes('{TARGET_ID}')) {{
            var btns = view.querySelectorAll('button');
            for (var btn of btns) {{
                if (btn.textContent.includes('编辑')) {{
                    btn.click();
                    return 'clicked';
                }}
            }}
        }}
    }}
    return null;
}})()
""")
        result = updater.page.evaluate(open('/tmp/js_click_edit.js').read())
        print(f"点击编辑: {result}")
        time.sleep(10)
        
        # 等待编辑对话框
        dialog = updater._wait_for_dialog()
        if not dialog:
            print("编辑对话框未出现")
            return
        print("编辑对话框已打开")
        time.sleep(2)
        
        # 填写表单
        body = updater.page.query_selector('.el-dialog__body')
        inputs = body.query_selector_all('input')
        for inp in inputs:
            ph = inp.get_attribute('placeholder') or ''
            if '标题' in ph:
                inp.fill(product.get('optimized_title') or product.get('title', ''))
                print("标题已填写")
                break
        
        textareas = body.query_selector_all('textarea')
        for ta in textareas:
            val = ta.input_value() or ''
            if len(val) > 50:
                ta.fill(product.get('optimized_description') or product.get('description', ''))
                print("描述已填写")
                break
        
        pid = product.get('product_id_new')
        if pid:
            with open('/tmp/js_fill_pid.js', 'w') as f:
                f.write(f"""
(function() {{
    var items = document.querySelectorAll(".el-dialog__body .el-form-item");
    var input = items[3].querySelector("input");
    if (input) {{ input.value = "{pid}"; input.dispatchEvent(new Event("input", {{bubbles: true}})); }}
}})()
""")
            updater.page.evaluate(open('/tmp/js_fill_pid.js').read())
            print(f"主货号: {pid}")
        
        category = product.get('category', '')
        cat_name = category.split('-')[1].split('(')[0].strip() if '-' in category else ''
        level3 = cat_name or '收纳盒、收纳包与篮子'
        level2 = '居家收纳'
        level1 = '家居生活'
        
        updater.page.evaluate("""
(function() {
    var items = document.querySelectorAll(".el-dialog__body .el-form-item");
    var cascader = items[5].querySelector(".el-cascader");
    if (cascader) cascader.click();
})()
""")
        time.sleep(0.8)
        
        with open('/tmp/js_lvl1.js', 'w') as f:
            f.write(f"""
(function() {{
    var nodes = document.querySelectorAll(".el-cascader-panel__node");
    if (nodes.length >= 3) {{
        for (var n of nodes[0].querySelectorAll(".el-cascader-node")) {{
            if ((n.innerText || "").indexOf("{level1}") >= 0) {{ n.click(); break; }}
        }}
    }}
}})()
""")
        updater.page.evaluate(open('/tmp/js_lvl1.js').read())
        time.sleep(0.6)
        
        with open('/tmp/js_lvl2.js', 'w') as f:
            f.write(f"""
(function() {{
    var nodes = document.querySelectorAll(".el-cascader-panel__node");
    if (nodes.length >= 3) {{
        for (var n of nodes[1].querySelectorAll(".el-cascader-node")) {{
            if ((n.innerText || "").indexOf("{level2}") >= 0) {{ n.click(); break; }}
        }}
    }}
}})()
""")
        updater.page.evaluate(open('/tmp/js_lvl2.js').read())
        time.sleep(0.6)
        
        with open('/tmp/js_lvl3.js', 'w') as f:
            f.write(f"""
(function() {{
    var nodes = document.querySelectorAll(".el-cascader-panel__node");
    if (nodes.length >= 3) {{
        for (var n of nodes[2].querySelectorAll(".el-cascader-node")) {{
            if ((n.innerText || "").indexOf("{level3}") >= 0) {{ n.click(); break; }}
        }}
    }}
}})()
""")
        updater.page.evaluate(open('/tmp/js_lvl3.js').read())
        time.sleep(0.8)
        
        updater.page.evaluate("(function() { var cascader = document.querySelector('.el-cascader'); if (cascader) cascader.click(); })()")
        time.sleep(0.5)
        print(f"类目: {level1} > {level2} > {level3}")
        
        weight = product.get('package_weight', 0)
        if weight:
            weight_kg = float(weight) / 1000
            with open('/tmp/js_weight.js', 'w') as f:
                f.write(f"""
(function() {{
    var items = document.querySelectorAll(".el-dialog__body .el-form-item");
    var input = items[12].querySelector("input");
    if (input) {{ input.value = "{weight_kg}"; input.dispatchEvent(new Event("input", {{bubbles: true}})); }}
}})()
""")
            updater.page.evaluate(open('/tmp/js_weight.js').read())
            print(f"包裹重量: {weight_kg}kg")
        
        time.sleep(1)
        updater.screenshot('analyze_form')
        
        # 点击保存并发布
        print("点击保存并发布...")
        updater._close_popups()
        time.sleep(1)
        
        updater.page.evaluate("""
(function() {
    var buttons = document.querySelectorAll('button');
    for (var btn of buttons) {
        if (btn.innerText && btn.innerText.trim().includes('保存并发布')) {
            btn.click();
            break;
        }
    }
})()
""")
        time.sleep(3)
        
        # 等待发布确认对话框
        print("等待发布确认对话框...")
        for i in range(20):
            time.sleep(1)
            try:
                all_dialogs = updater.page.query_selector_all('.el-dialog__wrapper')
                for dlg in all_dialogs:
                    title = dlg.query_selector('.el-dialog__title')
                    if title and '发布产品' in title.inner_text():
                        print("  发布对话框已出现!")
                        
                        # 分析对话框内容
                        print("\n=== 发布对话框分析 ===")
                        print(f"对话框innerText: {dlg.inner_text()[:500]}")
                        
                        # 列出所有按钮
                        all_buttons = dlg.query_selector_all('button')
                        print(f"\n对话框内按钮数量: {len(all_buttons)}")
                        for i, btn in enumerate(all_buttons):
                            try:
                                txt = btn.inner_text().strip()
                                print(f"  按钮{i}: '{txt}' | class={btn.get_attribute('class')}")
                            except: pass
                        
                        # 列出所有checkbox
                        all_cbs = dlg.query_selector_all('input[type=checkbox]')
                        print(f"\n对话框内checkbox数量: {len(all_cbs)}")
                        
                        # 列出对话框的所有直接子元素
                        children = dlg.query_selector_all('*')
                        print(f"\n对话框子元素数量: {len(children)}")
                        
                        updater.screenshot('analyze_publish_dialog')
                        print("\n截图已保存")
                        break
            except Exception as e:
                print(f"  异常: {e}")
        
    finally:
        updater.close()

if __name__ == '__main__':
    main()
