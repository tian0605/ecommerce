#!/usr/bin/env python3
"""Step6 修复脚本v3：使用独立的JS脚本文件"""
import sys, time, json, subprocess
from pathlib import Path
sys.path.insert(0, '/home/ubuntu/.openclaw/skills/shared')
sys.path.insert(0, '/home/ubuntu/.openclaw/skills/miaoshou-updater')
from fix_step6_guard import require_step6_guard
from updater import MiaoshouUpdater
from logger import setup_logger
import db

require_step6_guard(__file__, destructive=True)

logger = setup_logger('fix-step6-v3')

TARGET_IDS = ['1026754677096', '1031338618294']

def get_product_with_skus(alibaba_id):
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

def js_run(updater, script):
    """通过文件执行JS避免f-string转义问题"""
    script_path = '/tmp/js_eval.js'
    with open(script_path, 'w') as f:
        f.write(script)
    with open(script_path) as f:
        content = f.read().strip()
    return updater.page.evaluate(content)

def process_product(updater, product):
    alibaba_id = product['alibaba_product_id']
    logger.info(f"开始处理: {alibaba_id}")
    
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
        if (view.textContent.includes('{alibaba_id}')) {{
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
    
    if result != 'clicked':
        logger.error(f"未找到编辑按钮: {alibaba_id}")
        return False
    
    time.sleep(10)
    updater.screenshot(f'edit_{alibaba_id}')
    
    # 3. 等待编辑对话框
    dialog = updater._wait_for_dialog()
    if not dialog:
        logger.error("编辑对话框未出现")
        return False
    logger.info("编辑对话框已打开")
    time.sleep(2)
    
    # 4. 填写表单
    body = updater.page.query_selector('.el-dialog__body')
    if not body:
        logger.error("对话框body未找到")
        return False
    
    # 标题
    inputs = body.query_selector_all('input')
    for inp in inputs:
        ph = inp.get_attribute('placeholder') or ''
        if '标题' in ph:
            inp.fill('')
            time.sleep(0.2)
            inp.fill(product.get('optimized_title') or product.get('title', ''))
            logger.info("  标题已填写")
            break
    
    # 描述
    textareas = body.query_selector_all('textarea')
    for ta in textareas:
        val = ta.input_value() or ''
        if len(val) > 50:
            ta.fill('')
            time.sleep(0.2)
            ta.fill(product.get('optimized_description') or product.get('description', ''))
            logger.info(f"  描述已填写({len(product.get('optimized_description', ''))}字符)")
            break
    
    # 主货号
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
        logger.info(f"  主货号: {pid}")
    
    # 类目
    category = product.get('category', '')
    cat_name = category.split('-')[1].split('(')[0].strip() if '-' in category else ''
    level3 = cat_name or '收纳盒、收纳包与篮子'
    level2 = '居家收纳'
    level1 = '家居生活'
    
    with open('/tmp/js_cascader.js', 'w') as f:
        f.write("""
(function() {
    var items = document.querySelectorAll(".el-dialog__body .el-form-item");
    var cascader = items[5].querySelector(".el-cascader");
    if (cascader) cascader.click();
})()
""")
    updater.page.evaluate(open('/tmp/js_cascader.js').read())
    time.sleep(0.8)
    
    # 三级类目
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
    
    # 关闭cascader
    updater.page.evaluate("""
(function() { var cascader = document.querySelector('.el-cascader'); if (cascader) cascader.click(); })()
""")
    time.sleep(0.5)
    logger.info(f"  类目: {level1} > {level2} > {level3}")
    
    # 包裹重量
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
        logger.info(f"  包裹重量: {weight_kg}kg")
    
    time.sleep(1)
    updater.screenshot(f'form_{alibaba_id}')
    
    # 5. 点击保存并发布
    logger.info("  点击保存并发布...")
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
    
    # 6. 处理发布确认对话框
    logger.info("  等待发布确认对话框...")
    dialog_appeared = False
    for i in range(20):
        time.sleep(1)
        try:
            all_dialogs = updater.page.query_selector_all('.el-dialog__wrapper')
            for dlg in all_dialogs:
                title = dlg.query_selector('.el-dialog__title')
                if title and '发布产品' in title.inner_text():
                    dialog_appeared = True
                    logger.info("  发布对话框已出现!")
                    break
        except: pass
        if dialog_appeared:
            break
        logger.info(f"    等待... ({i+1}/20)")
    
    if not dialog_appeared:
        logger.warning("  发布对话框未出现!")
        updater.screenshot(f'no_dialog_{alibaba_id}')
        return False
    
    # 7. 处理发布对话框 - 勾选并点击确定发布
    with open('/tmp/js_publish.js', 'w') as f:
        f.write("""
(function() {
    var dialogs = document.querySelectorAll('.el-dialog__wrapper');
    for (var d of dialogs) {
        var title = d.querySelector('.el-dialog__title');
        if (title && title.innerText.includes('发布产品')) {
            // 勾选所有checkbox
            var cbs = d.querySelectorAll('input[type=checkbox]');
            for (var cb of cbs) {
                if (!cb.checked) { cb.checked = true; cb.dispatchEvent(new Event('change', {bubbles: true})); }
            }
            // 找并点击确定发布按钮
            var btns = d.querySelectorAll('button');
            for (var b of btns) {
                if (b.innerText && b.innerText.trim().includes('确定发布')) {
                    b.click();
                    return 'published';
                }
            }
            // 如果按钮文本不匹配，尝试查找所有按钮
            for (var b of btns) {
                var txt = b.innerText || '';
                if (txt.includes('确定') && txt.includes('发布')) {
                    b.click();
                    return 'published_alt';
                }
            }
            return 'dialog_found_no_button';
        }
    }
    return 'no_dialog';
})()
""")
    result = updater.page.evaluate(open('/tmp/js_publish.js').read())
    logger.info(f"  发布JS结果: {result}")
    
    if result in ('published', 'published_alt'):
        time.sleep(10)
        updater.screenshot(f'after_publish_{alibaba_id}')
        # 更新数据库为published
        import psycopg2
        conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
        cur = conn.cursor()
        cur.execute("UPDATE products SET status = 'published', updated_at = CURRENT_TIMESTAMP WHERE alibaba_product_id = %s", (alibaba_id,))
        conn.commit()
        conn.close()
        logger.info(f"  ✅ 发布成功，数据库已更新: {alibaba_id}")
        return True
    else:
        logger.warning(f"  ⚠️ 发布结果: {result}")
        return False

def main():
    products = []
    for alibaba_id in TARGET_IDS:
        p = get_product_with_skus(alibaba_id)
        if p:
            products.append(p)
            print(f"✅ {alibaba_id}: weight={p['package_weight']}g")
        else:
            print(f"❌ {alibaba_id} 未找到")
    
    if not products:
        return
    
    updater = MiaoshouUpdater(headless=True)
    try:
        updater.launch()
        results = {}
        for product in products:
            print(f"\n{'='*60}")
            print(f"处理: {product['alibaba_product_id']}")
            print(f"{'='*60}")
            try:
                success = process_product(updater, product)
                results[product['alibaba_product_id']] = success
                print(f"结果: {'✅ 成功' if success else '❌ 失败'}")
            except Exception as e:
                print(f"异常: {e}")
                import traceback
                traceback.print_exc()
                results[product['alibaba_product_id']] = False
            time.sleep(3)
        
        print(f"\n{'='*60}")
        print("汇总:")
        for k, v in results.items():
            print(f"  {'✅' if v else '❌'} {k}")
    finally:
        updater.close()

if __name__ == '__main__':
    main()
