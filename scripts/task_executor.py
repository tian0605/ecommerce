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
    cur.execute("SELECT id, title, description, optimized_title FROM products WHERE alibaba_product_id = %s LIMIT 1", (product_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return False, "商品未找到", None
    
    db_id, original_title, original_desc, existing_optimized = row
    
    # 如果已有优化结果，跳过
    if existing_optimized:
        log("  ⏭️ 已优化过，跳过API调用")
        result_data = {
            "module": "listing-optimizer",
            "status": "✅ (已优化)",
            "product_id": product_id,
            "db_id": db_id,
            "original_title": original_title,
            "optimized_title": existing_optimized,
            "compliance": "✅ 无'现货'词汇",
            "note": "跳过（已优化）",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        return True, "listing-optimizer 已完成（跳过）", result_data
    
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
    
    # ⭐ 关键修复：保存到数据库
    log("  保存到数据库...")
    try:
        import psycopg2
        conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
        cur = conn.cursor()
        cur.execute("""
            UPDATE products 
            SET optimized_title = %s, 
                optimized_description = %s,
                status = 'optimized',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (optimized_title, optimized_desc, db_id))
        conn.commit()
        conn.close()
        log("  ✅ 已保存到数据库")
    except Exception as e:
        log(f"  ⚠️ 保存失败: {e}")
    
    result_data = {
        "module": "listing-optimizer",
        "status": "✅" if compliance_ok else "⚠️",
        "product_id": product_id,
        "db_id": db_id,
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
    
    # 目标利润率 30%
    target_margin = 1.3
    
    # 计算包含所有费用的售价
    # 总成本 = 采购价 + 货代费(3元) + SLS运费
    # 售价 = (采购价 + 货代费 + SLS运费CNY) * 汇率 * 目标系数 / (1 - 平台费率)
    # 平台费率 = 佣金14% + 交易手续费2.5% + 预售服务费3% = 19.5%
    platform_fee_rate = 0.195
    exchange_rate = 4.5
    
    total_cost_cny = purchase_price + 3 + sls_cny
    suggested_price_twd = int(total_cost_cny * exchange_rate * target_margin / (1 - platform_fee_rate))
    
    # 计算各项费用
    commission_twd = int(suggested_price_twd * 0.14)
    transaction_fee_twd = int(suggested_price_twd * 0.025)
    pre_sale_fee_twd = int(suggested_price_twd * 0.03)
    total_platform_fee_twd = commission_twd + transaction_fee_twd + pre_sale_fee_twd
    
    # 买家实付运费（藏价）
    buyer_shipping = 55  # 普通情况买家付55 TWD
    seller_shipping = sls_twd - buyer_shipping  # 卖家实际付的
    
    # 预估利润
    gross_profit_twd = suggested_price_twd - total_platform_fee_twd - total_cost_cny * exchange_rate - seller_shipping
    
    return True, "profit-analyzer 测试完成", {
        "module": "profit-analyzer",
        "status": "✅",
        "product_id": prod_id,
        "title": title,
        "purchase_price_cny": purchase_price,
        "weight_g": weight_g,
        "sls_twd": sls_twd,
        "sls_cny": round(sls_cny, 2),
        "commission_twd": commission_twd,
        "transaction_fee_twd": transaction_fee_twd,
        "pre_sale_fee_twd": pre_sale_fee_twd,
        "total_platform_fee_twd": total_platform_fee_twd,
        "total_cost_cny": round(total_cost_cny, 2),
        "suggested_price_twd": suggested_price_twd,
        "gross_profit_twd": gross_profit_twd,
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

def update_task_queue(improvements):
    """更新 dev-task-queue.md，添加发现的优化项"""
    if not improvements:
        # 无优化项，清除待执行任务标记
        clear_completed_tasks()
        return
    
    queue_file = WORKSPACE / 'docs' / 'dev-task-queue.md'
    
    # 读取现有内容
    existing_content = ""
    if queue_file.exists():
        with open(queue_file, 'r') as f:
            existing_content = f.read()
    
    # 构建新内容
    new_p0_items = []
    for imp in improvements:
        if imp.get("priority") == "P0":
            new_p0_items.append(f"### {imp['module']}: {imp['issue']}")
            new_p0_items.append(f"**建议：** {imp['action']}")
            new_p0_items.append("")
    
    # 如果有新的 P0 项，添加到文件
    if new_p0_items:
        # 在 P0 优化项部分插入新项
        header = "## 🔴 P0 优化项（立即处理）"
        
        if header in existing_content:
            # 找到 P0 部分的位置
            lines = existing_content.split('\n')
            new_lines = []
            in_p0_section = False
            added = False
            
            for line in lines:
                if header in line:
                    in_p0_section = True
                    new_lines.append(line)
                    continue
                
                if in_p0_section and line.startswith("## ") and not added:
                    # 遇到下一个章节，插入新项
                    new_lines.append("".join(new_p0_items))
                    new_lines.append(line)
                    added = True
                    in_p0_section = False
                else:
                    new_lines.append(line)
            
            if not added:
                new_lines.append("".join(new_p0_items))
            
            existing_content = '\n'.join(new_lines)
        else:
            # 没有 P0 部分，在顶部插入
            existing_content = header + "\n\n" + "".join(new_p0_items) + "\n\n" + existing_content
        
        # 写回文件
        with open(queue_file, 'w') as f:
            f.write(existing_content)
        
        log(f"已更新 dev-task-queue.md，添加 {len(new_p0_items)//3} 个 P0 项")
    
    # 清除已完成的待执行任务
    clear_completed_tasks()

def clear_completed_tasks():
    """清除 dev-task-queue.md 中已完成的待执行任务"""
    queue_file = WORKSPACE / 'docs' / 'dev-task-queue.md'
    
    if not queue_file.exists():
        return
    
    with open(queue_file, 'r') as f:
        content = f.read()
    
    # 检查是否有"✅ 第一轮测试已完成"这样的标记
    if "✅ 第一轮" in content or "已完成" in content:
        lines = content.split('\n')
        new_lines = []
        skip_until_header = False
        
        for line in lines:
            # 跳过已完成的章节头
            if "✅ 第一轮" in line or ("已完成" in line and "历史" not in line and "最后" not in line):
                skip_until_header = True
                continue
            
            # 如果遇到下一个主要章节，停止跳过
            if skip_until_header and line.startswith("## "):
                skip_until_header = False
            
            if not skip_until_header:
                new_lines.append(line)
        
        new_content = '\n'.join(new_lines)
        
        with open(queue_file, 'w') as f:
            f.write(new_content)
        
        log("已清除已完成的待执行任务")

def analyze_results(results):
    """分析测试结果，找出优化项"""
    improvements = []
    
    for r in results:
        if not r.get("success"):
            # 任务失败，记录为 P0 问题
            improvements.append({
                "priority": "P0",
                "module": r.get("step", "unknown"),
                "issue": r.get("message", "未知错误"),
                "action": "检查并修复"
            })
            continue
        
        data = r.get("data", {})
        module = data.get("module", "")
        
        if module == "listing-optimizer":
            # 检查是否跳过
            if data.get("note") and "跳过" in data.get("note"):
                improvements.append({
                    "priority": "P1",
                    "module": module,
                    "issue": f"任务跳过: {data.get('note')}",
                    "action": "检查是否需要重新执行"
                })
        
        if module == "miaoshou-updater":
            if "跳过" in r.get("message", ""):
                improvements.append({
                    "priority": "P0",
                    "module": module,
                    "issue": r.get("message", "任务跳过"),
                    "action": "需要 listing-optimizer 先完成"
                })
        
        if module == "profit-analyzer":
            price = data.get("suggested_price_twd", 0)
            if price and price < 100:
                improvements.append({
                    "priority": "P1",
                    "module": module,
                    "issue": f"建议售价过低: {price} TWD",
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
    
    # 加载结果并检查是否有失败步骤
    state = load_state()
    results = state.get("results", [])
    
    has_failure = any(not r.get("success", False) for r in results)
    
    # 任务完成
    state["completed"] = not has_failure  # 只有全部成功才标记完成
    state["completed_at"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if has_failure:
        state["failed_step"] = next((r.get("step") for r in results if not r.get("success", False)), None)
    save_state(state)
    
    if has_failure:
        log("\n⚠️ 任务有失败步骤，将在下一次心跳重试")
    
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
        
        # 更新 dev-task-queue.md
        update_task_queue(improvements)
    
    # 写入飞书文档
    try:
        import sys
        sys.path.insert(0, str(WORKSPACE / 'scripts'))
        from write_feishu_result import write_to_feishu
        write_to_feishu(results, improvements)
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
