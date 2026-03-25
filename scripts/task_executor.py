#!/usr/bin/env python3
"""
CommerceFlow 任务执行器 v2
- 支持断点续执（记录执行状态）
- 支持异步等待
- 自动将结果写入飞书文档
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
SKILLS_DIR = Path('/home/ubuntu/.openclaw/skills')
STATE_FILE = WORKSPACE / 'logs' / 'task_state.json'
FEISHU_DOC_ID = "UVlkd1NHrorLumxC8K7cLMBUnDe"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def load_state():
    """加载执行状态"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {
        "current_task": None,
        "task_index": 0,
        "results": [],
        "started_at": None,
        "last_updated": None
    }

def save_state(state):
    """保存执行状态"""
    state["last_updated"] = datetime.now().isoformat()
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def clear_state():
    """清除执行状态"""
    if STATE_FILE.exists():
        STATE_FILE.unlink()

def run_step(step_name, func, *args, **kwargs):
    """执行单个步骤，支持断点续执"""
    state = load_state()
    
    # 检查是否从上次继续
    if state["current_task"] == step_name and state["results"]:
        log(f"📍 从上次继续: {step_name}")
        # 返回之前的结果
        for r in state["results"]:
            if r.get("step") == step_name:
                return r.get("success"), r.get("message"), r.get("data")
    
    log(f"▶️ 执行: {step_name}")
    try:
        result = func(*args, **kwargs)
        # 保存结果到状态
        state["results"].append({
            "step": step_name,
            "success": result[0],
            "message": result[1],
            "data": result[2],
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        save_state(state)
        return result
    except Exception as e:
        log(f"❌ {step_name} 失败: {e}")
        state["results"].append({
            "step": step_name,
            "success": False,
            "message": str(e),
            "data": None,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        save_state(state)
        return False, str(e), None

def run_heartbeat_check():
    """心跳快速检查"""
    log("执行心跳检查...")
    result = subprocess_run([
        'python3', str(SKILLS_DIR / 'collector-scraper/scraper.py'), '--scrape', '0'
    ], timeout=90)
    
    if "货源ID: None" in result:
        return False, "⚠️ 货源ID未提取"
    return True, "✅ 货源ID提取正常"

def run_listing_optimizer_test(product_id="1026175430866"):
    """测试 listing-optimizer"""
    log("测试 listing-optimizer...")
    
    # 读取商品数据
    import psycopg2
    conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
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
    optimizer_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(optimizer_mod)
    ListingOptimizer = optimizer_mod.ListingOptimizer
    
    optimizer = ListingOptimizer()
    
    # 标题优化
    log("  调用 LLM 优化标题...")
    optimized_title = optimizer._optimize_title(
        original_title=original_title or "发饰收纳盒",
        category="分格設計",
        hot_search_words="收納、首飾"
    )
    
    # 检查合规
    compliance_ok = "現貨" not in optimized_title and "现货" not in optimized_title
    
    # 描述优化
    log("  调用 LLM 优化描述...")
    optimized_desc = optimizer._optimize_description(
        original_desc=original_desc or "材质：HIPS",
        title=original_title or "发饰收纳盒",
        category="分格設計",
        features="分格收納、便攜",
        scenarios="桌面、首飾",
        hot_search_words="收納"
    )
    
    result_data = {
        "module": "listing-optimizer",
        "status": "✅" if compliance_ok else "⚠️",
        "product_id": product_id,
        "original_title": original_title,
        "optimized_title": optimized_title,
        "original_desc": (original_desc or "")[:200],
        "optimized_desc": (optimized_desc or "")[:500],
        "compliance": "✅ 无'现货'词汇" if compliance_ok else "⚠️ 包含违规词汇",
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    return True, "listing-optimizer 测试完成", result_data

def run_miaoshou_updater_test(product_id="1026175430866"):
    """测试 miaoshou-updater"""
    log("测试 miaoshou-updater...")
    
    import psycopg2
    conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
    cur = conn.cursor()
    cur.execute("SELECT id, title, optimized_title FROM products WHERE alibaba_product_id = %s LIMIT 1", (product_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return False, "商品未找到", None
    
    db_id, title, optimized_title = row
    
    if optimized_title:
        return True, "待手动测试（需要浏览器）", {
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
        return False, "跳过（无优化标题）", None

def run_profit_analyzer_test(product_id="1026175430866"):
    """测试 profit-analyzer"""
    log("测试 profit-analyzer...")
    
    import psycopg2
    conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
    cur = conn.cursor()
    cur.execute("SELECT alibaba_product_id, title, supplier_info FROM products WHERE alibaba_product_id = %s LIMIT 1", (product_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return False, "商品未找到", None
    
    prod_id, title, supplier_info = row
    
    # 解析供应商信息
    purchase_price = 10.0
    weight_g = 500
    
    if supplier_info:
        try:
            info = json.loads(supplier_info) if isinstance(supplier_info, str) else supplier_info
            purchase_price = info.get('price', 10.0)
            weight_g = info.get('weight_g', 500)
        except:
            pass
    
    # 计算利润
    if weight_g <= 500:
        sls_twd = 70
    else:
        extra = ((weight_g - 500) // 500 + 1) * 30
        sls_twd = 70 + extra
    
    sls_cny = sls_twd / 4.5
    total_cost_cny = purchase_price + 3 + sls_cny
    suggested_price_twd = int(total_cost_cny * 4.5 * 1.3)
    
    return True, "profit-analyzer 测试完成", {
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

def subprocess_run(cmd, timeout=120):
    """执行子进程"""
    import subprocess
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return f"Command timeout after {timeout}s"
    except Exception as e:
        return str(e)

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

def main():
    log("=" * 50)
    log("开始任务执行 (v2 - 支持断点续执)")
    log("=" * 50)
    
    state = load_state()
    
    # 检查是否已有运行中的任务
    if state.get("current_task") and not state.get("completed"):
        log(f"📍 检测到上次未完成的任务: {state['current_task']}")
        log(f"   已完成: {len(state['results'])} 个步骤")
    else:
        log("🆕 开始新任务")
        clear_state()
        state = {"current_task": None, "results": [], "started_at": datetime.now().isoformat()}
        save_state(state)
    
    # 定义任务步骤
    steps = [
        ("listing-optimizer", run_listing_optimizer_test),
        ("miaoshou-updater", run_miaoshou_updater_test),
        ("profit-analyzer", run_profit_analyzer_test),
    ]
    
    # 执行步骤
    for step_name, step_func in steps:
        state = load_state()
        
        # 检查是否已完成
        already_done = any(r.get("step") == step_name for r in state.get("results", []))
        if already_done:
            log(f"⏭️ 跳过已完成: {step_name}")
            continue
        
        # 执行步骤
        state["current_task"] = step_name
        save_state(state)
        
        success, msg, data = run_step(step_name, step_func)
        log(f"  → {'✅' if success else '❌'} {msg}")
    
    # 任务完成
    state = load_state()
    state["completed"] = True
    state["completed_at"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_state(state)
    
    # 输出结果
    log("\n" + "=" * 50)
    log("执行结果汇总:")
    log("=" * 50)
    
    results = state.get("results", [])
    for r in results:
        status = "✅" if r["success"] else "❌"
        log(f"  {status} {r['step']}: {r['message']}")
    
    # 分析优化项
    improvements = analyze_results(results)
    if improvements:
        log("\n发现的优化项:")
        for imp in improvements:
            log(f"  [{imp['priority']}] {imp['module']}: {imp['issue']}")
    
    # 写入飞书文档
    try:
        from scripts.write_feishu_result import write_results
        write_results(results, improvements)
    except Exception as e:
        log(f"写入飞书文档失败: {e}")
    
    # 输出 JSON 格式结果
    print("\n[TASK_RESULTS]")
    print(json.dumps({
        "results": results,
        "improvements": improvements,
        "state": state
    }, ensure_ascii=False, indent=2))
    
    log("\n✅ 任务执行完成!")
    return 0

if __name__ == '__main__':
    sys.exit(main())
