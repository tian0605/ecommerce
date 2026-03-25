#!/usr/bin/env python3
"""
CommerceFlow 任务执行器
自动执行 dev-task-queue.md 中的任务，并将结果写入飞书文档
"""

import sys
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
SKILLS_DIR = Path('/home/ubuntu/.openclaw/skills')
FEISHU_DOC_ID = "UVlkd1NHrorLumxC8K7cLMBUnDe"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def run_heartbeat_check():
    """执行心跳快速检查"""
    log("执行心跳检查...")
    
    # collector-scraper 快速测试
    result = subprocess.run(
        ['python3', str(SKILLS_DIR / 'collector-scraper/scraper.py'), '--scrape', '0'],
        capture_output=True,
        text=True,
        timeout=90
    )
    
    if "货源ID: None" in result.stdout or "货源ID: None" in result.stderr:
        return False, "⚠️ 货源ID未提取"
    return True, "✅ 货源ID提取正常"

def run_listing_optimizer_test(product_id="1026175430866"):
    """测试 listing-optimizer"""
    log("测试 listing-optimizer...")
    
    # 读取商品数据
    import psycopg2
    conn = psycopg2.connect(
        host='localhost',
        database='ecommerce_data',
        user='superuser',
        password='Admin123!'
    )
    cur = conn.cursor()
    cur.execute("SELECT title, description FROM products WHERE alibaba_product_id = %s LIMIT 1", (product_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return False, "商品未找到", None
    
    original_title, original_desc = row
    
    # 调用 optimizer
    sys.path.insert(0, str(WORKSPACE / 'config'))
    sys.path.insert(0, str(SKILLS_DIR / 'listing-optimizer'))
    import importlib.util
    spec = importlib.util.spec_from_file_location("optimizer", SKILLS_DIR / 'listing-optimizer/optimizer.py')
    optimizer_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(optimizer_module)
    ListingOptimizer = optimizer_module.ListingOptimizer
    
    optimizer = ListingOptimizer()
    
    # 标题优化
    optimized_title = optimizer._optimize_title(
        original_title=original_title or "发饰收纳盒",
        category="分格設計",
        hot_search_words="收納、首飾"
    )
    
    # 检查合规
    compliance_ok = "現貨" not in optimized_title and "现货" not in optimized_title
    
    # 描述优化
    optimized_desc = optimizer._optimize_description(
        original_desc=original_desc or "材质：HIPS",
        title=original_title or "发饰收纳盒",
        category="分格設計",
        features="分格收納、便攜",
        scenarios="桌面、首飾",
        hot_search_words="收納"
    )
    
    result = {
        "module": "listing-optimizer",
        "status": "✅" if compliance_ok else "⚠️",
        "product_id": product_id,
        "original_title": original_title,
        "optimized_title": optimized_title,
        "original_desc": original_desc[:200] if original_desc else "",
        "optimized_desc": optimized_desc[:500] if optimized_desc else "",
        "compliance": "✅ 无'现货'词汇" if compliance_ok else "⚠️ 包含违规词汇",
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    return True, "listing-optimizer 测试完成", result

def run_miaoshou_updater_test(product_id="1026175430866"):
    """测试 miaoshou-updater"""
    log("测试 miaoshou-updater...")
    
    # 读取商品数据
    import psycopg2
    conn = psycopg2.connect(
        host='localhost',
        database='ecommerce_data',
        user='superuser',
        password='Admin123!'
    )
    cur = conn.cursor()
    cur.execute("SELECT id, title, optimized_title FROM products WHERE alibaba_product_id = %s LIMIT 1", (product_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return False, "商品未找到", None
    
    db_id, title, optimized_title = row
    
    # miaoshou-updater 需要实际浏览器操作，这里只做检查
    # 检查优化后的标题是否存在
    if optimized_title:
        return True, "miaoshou-updater 待手动测试（需要浏览器）", {
            "module": "miaoshou-updater",
            "status": "🔄",
            "product_id": product_id,
            "db_id": db_id,
            "title": title,
            "optimized_title": optimized_title,
            "note": "需要手动在妙手ERP中测试回写功能",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    else:
        return False, "miaoshou-updater 跳过（无优化标题）", None

def run_profit_analyzer_test(product_id="1026175430866"):
    """测试 profit-analyzer"""
    log("测试 profit-analyzer...")
    
    # 读取商品数据
    import psycopg2
    conn = psycopg2.connect(
        host='localhost',
        database='ecommerce_data',
        user='superuser',
        password='Admin123!'
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT alibaba_product_id, title, supplier_info
        FROM products 
        WHERE alibaba_product_id = %s LIMIT 1
    """, (product_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return False, "商品未找到", None
    
    prod_id, title, supplier_info = row
    
    # 解析供应商信息获取价格和重量
    purchase_price = 10.0  # 默认值
    weight_g = 500  # 默认值
    
    if supplier_info:
        try:
            import json
            info = json.loads(supplier_info) if isinstance(supplier_info, str) else supplier_info
            purchase_price = info.get('price', 10.0)
            weight_g = info.get('weight_g', 500)
        except:
            pass
    
    # profit-analyzer 计算
    if price and weight:
        # 基本利润计算
        purchase_price = float(price) if price else 10.0
        weight_g = float(weight) if weight else 500
        
        # SLS运费计算（台湾站）
        if weight_g <= 500:
            sls_twd = 70
        else:
            extra = ((weight_g - 500) // 500 + 1) * 30
            sls_twd = 70 + extra
        
        sls_cny = sls_twd / 4.5  # 汇率估算
        commission_twd = 0  # 待计算
        total_cost_cny = purchase_price + 3 + sls_cny  # 货代费3元
        suggested_price_twd = int(total_cost_cny * 4.5 * 1.3)  # 30%利润
        
        result = {
            "module": "profit-analyzer",
            "status": "✅",
            "product_id": prod_id,
            "title": title,
            "purchase_price_cny": purchase_price,
            "weight_g": weight_g,
            "sls_twd": sls_twd,
            "sls_cny": round(sls_cny, 2),
            "total_cost_cny": round(total_cost_cny, 2),
            "suggested_price_twd": suggested_price_twd,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        return True, "profit-analyzer 测试完成", result
    else:
        return False, "profit-analyzer 跳过（无价格/重量数据）", None

def analyze_results(results):
    """分析测试结果，找出优化项"""
    improvements = []
    
    for r in results:
        if not r.get("success"):
            continue
        
        data = r.get("data", {})
        module = data.get("module", "")
        
        if module == "listing-optimizer":
            if "⚠️" in data.get("status", ""):
                improvements.append({
                    "priority": "P0",
                    "module": module,
                    "issue": data.get("compliance", "合规问题"),
                    "action": "检查并修复提示词"
                })
        
        if module == "profit-analyzer":
            if data.get("suggested_price_twd", 0) < 100:
                improvements.append({
                    "priority": "P1",
                    "module": module,
                    "issue": "建议售价过低",
                    "action": "调整利润率和藏价策略"
                })
    
    return improvements

def format_feishu_content(results, improvements):
    """格式化结果为飞书文档内容"""
    lines = [
        "# Agent自动执行结果\n",
        f"**执行时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "---\n",
        "## 测试结果\n",
    ]
    
    for r in results:
        data = r.get("data", {})
        if data:
            lines.append(f"### {data.get('module', 'Unknown')}\n")
            lines.append(f"- **状态：** {data.get('status', '-')}\n")
            lines.append(f"- **商品ID：** {data.get('product_id', '-')}\n")
            if data.get('optimized_title'):
                lines.append(f"- **优化标题：** {data.get('optimized_title', '-')}\n")
            if data.get('suggested_price_twd'):
                lines.append(f"- **建议售价：** {data.get('suggested_price_twd')} TWD\n")
            if data.get('compliance'):
                lines.append(f"- **合规检查：** {data.get('compliance', '-')}\n")
            lines.append(f"- **时间：** {data.get('timestamp', '-')}\n")
            lines.append("\n")
    
    if improvements:
        lines.append("---\n")
        lines.append("## 发现的优化项\n")
        for imp in improvements:
            lines.append(f"- **[{imp['priority']}]** {imp['module']}: {imp['issue']}\n")
            lines.append(f"  - 建议：{imp['action']}\n")
    
    return "".join(lines)

def main():
    log("=" * 50)
    log("开始任务执行")
    log("=" * 50)
    
    results = []
    
    # 1. listing-optimizer 测试
    success, msg, data = run_listing_optimizer_test()
    results.append({"step": "listing-optimizer", "success": success, "message": msg, "data": data})
    log(f"listing-optimizer: {msg}")
    
    # 2. miaoshou-updater 测试
    success, msg, data = run_miaoshou_updater_test()
    results.append({"step": "miaoshou-updater", "success": success, "message": msg, "data": data})
    log(f"miaoshou-updater: {msg}")
    
    # 3. profit-analyzer 测试
    success, msg, data = run_profit_analyzer_test()
    results.append({"step": "profit-analyzer", "success": success, "message": msg, "data": data})
    log(f"profit-analyzer: {msg}")
    
    # 分析优化项
    improvements = analyze_results(results)
    
    # 输出结果
    print("\n" + "=" * 50)
    print("执行结果汇总:")
    print("=" * 50)
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"{status} {r['step']}: {r['message']}")
    
    if improvements:
        print("\n发现的优化项:")
        for imp in improvements:
            print(f"  [{imp['priority']}] {imp['module']}: {imp['issue']}")
    
    # 返回JSON格式结果供shell脚本处理
    print("\n[TASK_RESULTS]")
    print(json.dumps({
        "results": results,
        "improvements": improvements
    }, ensure_ascii=False))
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
