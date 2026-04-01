#!/usr/bin/env python3
"""Step6 修复脚本v5：修复JS转义问题"""
import sys, time
from pathlib import Path
sys.path.insert(0, '/home/ubuntu/.openclaw/skills/shared')
sys.path.insert(0, '/home/ubuntu/.openclaw/skills/miaoshou-updater')
from fix_step6_guard import require_step6_guard
from updater import MiaoshouUpdater
from logger import setup_logger
import db

require_step6_guard(__file__, destructive=True)

logger = setup_logger('fix-step6-v5')
TARGET_IDS = ['1026754677096', '1031338618294']

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
        p = {
            'id': row[0], 'product_id': row[1], 'alibaba_product_id': row[2],
            'title': row[3], 'description': row[4], 'optimized_title': row[5],
            'optimized_description': row[6], 'status': row[7], 'category': row[8],
            'product_id_new': row[9],
        }
        cur.execute("""
            SELECT package_weight FROM product_skus
            WHERE product_id = %s ORDER BY price ASC LIMIT 1
        """, (row[0],))
        sku = cur.fetchone()
        p['package_weight'] = float(sku[0]) if sku and sku[0] else 0
        return p

def js_file(path, template, **kwargs):
    """写入JS文件（避免f-string转义问题）"""
    content = template % kwargs
    with open(path, 'w') as f:
        f.write(content)

def process_product(updater, product):
    aid = product['alibaba_product_id']
    logger.info(f"处理: {aid}")
    
    # 1. 访问
    updater.page.goto('https://erp.91miaoshou.com/shopee/collect_box/items', wait_until='domcontentloaded')
    time.sleep(5)
    updater._close_popups()
    time.sleep(2)
    
    # 2. 点击编辑
    js_file('/tmp/js1.txt', """
(function() {
    var views = document.querySelectorAll('.vue-recycle-scroller__item-view');
    for (var v of views) {
        if (v.textContent.includes('%s')) {
            var bs = v.querySelectorAll('button');
            for (var b of bs) { if (b.textContent.includes('编辑')) { b.click(); return 'ok'; } }
        }
    }
    return 'not_found';
})()
    """ % aid)
    r = updater.page.evaluate(open('/tmp/js1.txt').read())
    if r != 'ok':
        logger.error(f"未找到编辑按钮")
        return False
    time.sleep(10)
    
    # 3. 等待对话框
    d = updater._wait_for_dialog()
    if not d:
        logger.error("对话框未出现")
        return False
    time.sleep(2)
    
    body = updater.page.query_selector('.el-dialog__body')
    if not body:
        return False
    
    # 标题
    for inp in body.query_selector_all('input'):
        if '标题' in (inp.get_attribute('placeholder') or ''):
            inp.fill(product['optimized_title'] or product['title'])
            logger.info("  标题已填")
            break
    
    # 描述
    for ta in body.query_selector_all('textarea'):
        if len(ta.input_value() or '') > 50:
            ta.fill(product['optimized_description'] or product['description'])
            logger.info("  描述已填")
            break
    
    # 主货号
    pid = product['product_id_new']
    if pid:
        js_file('/tmp/js2.txt', """
(function() {
    var items = document.querySelectorAll('.el-dialog__body .el-form-item');
    var inp = items[3].querySelector('input');
    if (inp) { inp.value = '%s'; inp.dispatchEvent(new Event('input', {bubbles:true})); }
})()
        """ % pid)
        updater.page.evaluate(open('/tmp/js2.txt').read())
        logger.info(f"  主货号: {pid}")
    
    # 类目
    cat = product['category'] or ''
    cat_name = cat.split('-')[1].split('(')[0].strip() if '-' in cat else ''
    l1, l2, l3 = '家居生活', '居家收纳', cat_name or '收纳盒、收纳包与篮子'
    
    updater.page.evaluate("""
(function() {
    var c = document.querySelectorAll('.el-dialog__body .el-form-item')[5];
    if (c) { var el = c.querySelector('.el-cascader'); if (el) el.click(); }
})()
""")
    time.sleep(0.8)
    
    for lvl, idx in [(l1, 0), (l2, 1), (l3, 2)]:
        js_file('/tmp/jsc.txt', """
(function() {
    var nodes = document.querySelectorAll('.el-cascader-panel__node');
    if (nodes.length > %d) {
        var ns = nodes[%d].querySelectorAll('.el-cascader-node');
        for (var n of ns) {
            if ((n.innerText||'').indexOf('%s') >= 0) { n.click(); break; }
        }
    }
})()
        """ % (idx, idx, lvl))
        updater.page.evaluate(open('/tmp/jsc.txt').read())
        time.sleep(0.6)
    
    updater.page.evaluate("(function(){var c=document.querySelector('.el-cascader');if(c)c.click();})()")
    time.sleep(0.5)
    logger.info(f"  类目: {l1}>{l2}>{l3}")
    
    # 包裹重量
    w = product['package_weight']
    if w:
        wk = float(w) / 1000
        js_file('/tmp/js3.txt', """
(function() {
    var items = document.querySelectorAll('.el-dialog__body .el-form-item');
    var inp = items[12].querySelector('input');
    if (inp) { inp.value = '%s'; inp.dispatchEvent(new Event('input', {bubbles:true})); }
})()
        """ % wk)
        updater.page.evaluate(open('/tmp/js3.txt').read())
        logger.info(f"  重量: {wk}kg")
    
    time.sleep(1)
    updater.screenshot('form_' + aid)
    
    # 4. 保存并发布
    logger.info("  点击保存并发布...")
    updater._close_popups()
    time.sleep(1)
    
    updater.page.evaluate("""
(function() {
    var bs = document.querySelectorAll('button');
    for (var b of bs) { if ((b.innerText||'').trim().includes('保存并发布')) { b.click(); break; } }
})()
""")
    
    # 5. 发布确认对话框
    logger.info("  等待发布确认对话框...")
    for i in range(20):
        time.sleep(1)
        found = False
        for d in updater.page.query_selector_all('.el-dialog__wrapper'):
            try:
                t = d.query_selector('.el-dialog__title')
                if t and '发布产品' in t.inner_text():
                    found = True
                    break
            except: pass
        if found:
            break
    
    if not found:
        logger.warning("  发布对话框未出现")
        return False
    
    logger.info("  发布对话框已出现，点击'发布到选中店铺'...")
    
    # 6. 点击"发布到选中店铺"
    r = updater.page.evaluate("""
(function() {
    var ds = document.querySelectorAll('.el-dialog__wrapper');
    for (var d of ds) {
        var t = d.querySelector('.el-dialog__title');
        if (t && t.innerText.includes('发布产品')) {
            var bs = d.querySelectorAll('button');
            for (var b of bs) {
                if ((b.innerText||'').includes('发布到选中店铺')) { b.click(); return 'ok'; }
            }
        }
    }
    return 'not_found';
})()
""")
    
    if r == 'ok':
        time.sleep(10)
        updater.screenshot('after_' + aid)
        import psycopg2
        conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
        cur = conn.cursor()
        cur.execute("UPDATE products SET status='published', updated_at=CURRENT_TIMESTAMP WHERE alibaba_product_id=%s", (aid,))
        conn.commit()
        conn.close()
        logger.info(f"  ✅ 发布成功: {aid}")
        return True
    else:
        logger.warning(f"  ⚠️ 发布按钮未找到: {aid}")
        return False

def main():
    products = [(aid, get_product(aid)) for aid in TARGET_IDS]
    for aid, p in products:
        if p:
            print(f"✅ {aid}")
        else:
            print(f"❌ {aid} 未找到")
    
    updater = MiaoshouUpdater(headless=True)
    try:
        updater.launch()
        results = {}
        for aid, product in products:
            if not product:
                continue
            print(f"\n处理: {aid}")
            try:
                ok = process_product(updater, product)
                results[aid] = ok
                print(f"结果: {'✅' if ok else '❌'}")
            except Exception as e:
                print(f"异常: {e}")
                import traceback; traceback.print_exc()
                results[aid] = False
            time.sleep(3)
        
        print("\n汇总:")
        for k, v in results.items():
            print(f"  {'✅' if v else '❌'} {k}")
    finally:
        updater.close()

if __name__ == '__main__':
    main()
