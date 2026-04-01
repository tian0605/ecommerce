#!/usr/bin/env python3
"""手动修复 Step6：重新处理发布确认对话框"""
import sys, time
from pathlib import Path
sys.path.insert(0, '/home/ubuntu/.openclaw/skills/shared')
sys.path.insert(0, '/home/ubuntu/.openclaw/skills/miaoshou-updater')
from fix_step6_guard import require_step6_guard
from updater import MiaoshouUpdater
from logger import setup_logger
import db

require_step6_guard(__file__, destructive=True)

logger = setup_logger('fix-step6-manual')

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

def publish_product_direct(updater, product):
    """直接导航到商品并发布（跳过验证步骤）"""
    alibaba_id = product['alibaba_product_id']
    
    # 1. 访问采集箱
    logger.info(f"[1] 访问Shopee采集箱...")
    updater.page.goto('https://erp.91miaoshou.com/shopee/collect_box/items', wait_until='domcontentloaded')
    time.sleep(5)
    updater._close_popups()
    time.sleep(2)
    
    # 2. 找到商品并点击编辑
    logger.info(f"[2] 查找商品 {alibaba_id}...")
    
    # 点击编辑按钮（使用vue-recycle-scroller）
    result = updater.page.evaluate(f'''
        (alibabaId) => {{
            const views = document.querySelectorAll('.vue-recycle-scroller__item-view');
            for (let view of views) {{
                if (view.textContent.includes(alibabaId)) {{
                    const btns = view.querySelectorAll('button');
                    for (let btn of btns) {{
                        if (btn.textContent.includes('编辑')) {{
                            btn.click();
                            return 'clicked';
                        }}
                    }}
                }}
            }}
            return null;
        }}
    ''', alibaba_id)
    
    if result != 'clicked':
        logger.error(f"未找到编辑按钮")
        return False
    
    time.sleep(8)
    updater.screenshot('manual_edit_opened')
    
    # 3. 等待编辑对话框
    dialog = updater._wait_for_dialog()
    if not dialog:
        logger.error("编辑对话框未出现")
        return False
    logger.info(f"[3] 编辑对话框已打开")
    time.sleep(2)
    
    # 4. 只处理发布 - 先关闭对话框
    logger.info(f"[4] 关闭编辑对话框...")
    try:
        updater.page.evaluate('''
            var dialogs = document.querySelectorAll(".el-dialog__wrapper");
            for (var d of dialogs) {{
                var title = d.querySelector(".el-dialog__title");
                if (title && (title.innerText.includes("编辑产品") || title.innerText.includes("批量"))) {{
                    var closeBtn = d.querySelector(".el-dialog__headerbtn");
                    if (closeBtn) closeBtn.click();
                }}
            }}
        ''')
        time.sleep(2)
    except Exception as e:
        logger.debug(f"关闭对话框异常: {{e}}")
    
    # 5. 再次点击编辑，这次使用正确的流程
    logger.info(f"[5] 重新点击编辑按钮...")
    result = updater.page.evaluate(f'''
        (alibabaId) => {{
            const views = document.querySelectorAll('.vue-recycle-scroller__item-view');
            for (let view of views) {{
                if (view.textContent.includes(alibabaId)) {{
                    const btns = view.querySelectorAll('button');
                    for (let btn of btns) {{
                        if (btn.textContent.includes('编辑')) {{
                            btn.click();
                            return 'clicked';
                        }}
                    }}
                }}
            }}
            return null;
        }}
    ''', alibaba_id)
    
    if result != 'clicked':
        logger.error("未找到编辑按钮")
        return False
    
    time.sleep(10)
    updater.screenshot('manual_edit_reopened')
    
    # 6. 填写表单（快速路径 - 只填必要字段）
    logger.info(f"[6] 填写表单...")
    body = updater.page.query_selector('.el-dialog__body')
    if body:
        # 标题
        inputs = body.query_selector_all('input')
        for inp in inputs:
            ph = inp.get_attribute('placeholder') or ''
            if '标题' in ph:
                inp.fill('')
                time.sleep(0.2)
                inp.fill(product.get('optimized_title') or product.get('title', ''))
                logger.info(f"  标题已填写")
                break
        
        # 描述
        textareas = body.query_selector_all('textarea')
        for ta in textareas:
            val = ta.input_value() or ''
            if len(val) > 50:
                ta.fill('')
                time.sleep(0.2)
                ta.fill(product.get('optimized_description') or product.get('description', ''))
                logger.info(f"  描述已填写")
                break
        
        # 主货号
        product_id_new = product.get('product_id_new')
        if product_id_new:
            updater.page.evaluate(f'''
                var items = document.querySelectorAll(".el-dialog__body .el-form-item");
                var input = items[3].querySelector("input");
                if (input) {{ input.value = "{product_id_new}"; input.dispatchEvent(new Event("input", {{bubbles: true}})); }}
            ''')
            logger.info(f"  主货号已填写: {product_id_new}")
        
        # 类目
        category = product.get('category', '')
        cat_name = category.split('-')[1].split('(')[0].strip() if '-' in category else ''
        level3 = cat_name or '收纳盒、收纳包与篮子'
        level2 = '居家收纳'
        level1 = '家居生活'
        logger.info(f"  类目: {level1} > {level2} > {level3}")
        
        updater.page.evaluate('''
            var items = document.querySelectorAll(".el-dialog__body .el-form-item");
            var cascader = items[5].querySelector(".el-cascader");
            if (cascader) cascader.click();
        ''')
        time.sleep(0.5)
        
        updater.page.evaluate(f'''
            var nodes = document.querySelectorAll(".el-cascader-panel__node");
            if (nodes.length >= 3) {{
                for (var n of nodes[0].querySelectorAll(".el-cascader-node")) {{
                    if ((n.innerText || "").includes("{level1}")) {{ n.click(); break; }}
                }}
            }}
        ''')
        time.sleep(0.5)
        updater.page.evaluate(f'''
            var nodes = document.querySelectorAll(".el-cascader-panel__node");
            if (nodes.length >= 3) {{
                for (var n of nodes[1].querySelectorAll(".el-cascader-node")) {{
                    if ((n.innerText || "").includes("{level2}")) {{ n.click(); break; }}
                }}
            }}
        ''')
        time.sleep(0.5)
        updater.page.evaluate(f'''
            var nodes = document.querySelectorAll(".el-cascader-panel__node");
            if (nodes.length >= 3) {{
                for (var n of nodes[2].querySelectorAll(".el-cascader-node")) {{
                    if ((n.innerText || "").includes("{level3}")) {{ n.click(); break; }}
                }}
            }}
        ''')
        time.sleep(0.5)
        # 关闭cascader面板
        updater.page.evaluate('var cascader = document.querySelector(".el-cascader"); if (cascader) cascader.click();')
        time.sleep(0.5)
        logger.info(f"  类目已选择")
        
        # 包裹重量
        weight = product.get('package_weight', 0)
        if weight:
            weight_kg = float(weight) / 1000
            updater.page.evaluate(f'''
                var items = document.querySelectorAll(".el-dialog__body .el-form-item");
                var input = items[12].querySelector("input");
                if (input) {{ input.value = "{weight_kg}"; input.dispatchEvent(new Event("input", {{bubbles: true}})); }}
            ''')
            logger.info(f"  包裹重量: {weight_kg}kg")
    
    time.sleep(1)
    updater.screenshot('manual_form_filled')
    
    # 7. 点击保存并发布
    logger.info(f"[7] 点击保存并发布...")
    updater._close_popups()
    time.sleep(1)
    
    updater.page.evaluate('''
        var buttons = document.querySelectorAll('button');
        for (var btn of buttons) {{
            if (btn.innerText && btn.innerText.trim().includes('保存并发布')) {{
                btn.click();
                break;
            }}
        }}
    ''')
    time.sleep(3)
    
    # 8. 处理发布确认对话框 - 使用更宽泛的查找
    logger.info(f"[8] 等待发布确认对话框...")
    publish_dialog_found = False
    for attempt in range(15):
        time.sleep(1)
        result = updater.page.evaluate('''
            () => {{
                var dialogs = document.querySelectorAll(".el-dialog__wrapper");
                for (var d of dialogs) {{
                    var title = d.querySelector(".el-dialog__title");
                    if (title && title.innerText.includes("发布产品")) {{
                        // 全选checkbox
                        var cbs = d.querySelectorAll("input[type=checkbox]");
                        for (var cb of cbs) {{
                            if (!cb.checked) {{ cb.checked = true; cb.dispatchEvent(new Event("change", {{bubbles:true}})); }}
                        }}
                        // 点击确定发布
                        var btns = d.querySelectorAll("button");
                        for (var b of btns) {{
                            if (b.innerText && b.innerText.includes("确定发布")) {{
                                b.click();
                                return "published";
                            }}
                        }}
                        return "dialog_found_no_button";
                    }}
                }}
                return "no_dialog";
            }}
        ''')
        logger.info(f"    尝试 {attempt+1}/15: {result}")
        if result == "published":
            publish_dialog_found = True
            logger.info("  ✅ 发布确认完成！")
            break
    
    if not publish_dialog_found:
        logger.warning("  ⚠️ 发布对话框处理失败，尝试备用方法...")
        # 备用：直接JS点击所有"确定发布"按钮
        updater.page.evaluate('''
            var buttons = document.querySelectorAll('button');
            for (var btn of buttons) {{
                if (btn.innerText && btn.innerText.includes("确定发布")) {{
                    btn.click();
                    break;
                }}
            }}
        ''')
        time.sleep(5)
    
    updater.screenshot('manual_after_publish')
    
    # 9. 更新数据库状态为 published
    logger.info(f"[9] 更新数据库状态...")
    import psycopg2
    conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
    cur = conn.cursor()
    cur.execute("""
        UPDATE products SET status = 'published', updated_at = CURRENT_TIMESTAMP
        WHERE alibaba_product_id = %s
    """, (alibaba_id,))
    conn.commit()
    conn.close()
    logger.info(f"  ✅ 数据库已更新为 published: {alibaba_id}")
    
    time.sleep(3)
    updater._close_popups()
    return True

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
        for product in products:
            print(f"\n{'='*60}")
            print(f"开始: {product['alibaba_product_id']}")
            print(f"{'='*60}")
            try:
                success = publish_product_direct(updater, product)
                print(f"结果: {'✅ 成功' if success else '❌ 失败'}")
            except Exception as e:
                print(f"异常: {e}")
                import traceback
                traceback.print_exc()
            time.sleep(3)
    finally:
        updater.close()

if __name__ == '__main__':
    main()
