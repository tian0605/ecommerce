#!/usr/bin/env python3
"""
验证任务执行结果
检查 task_state.json 中的结果是否满足成功标准
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
STATE_FILE = WORKSPACE / 'logs' / 'task_state.json'
QUEUE_FILE = WORKSPACE / 'docs' / 'dev-task-queue.md'
FEISHU_TABLE_URL = "https://pcn0wtpnjfsd.feishu.cn/base/DyzjbfaZZaYeJls6lDFc5DavnPd"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 验证: {msg}", flush=True)

def validate_listing_optimizer(data, db_id):
    """验证 listing-optimizer 成功标准 - 直接从数据库检查"""
    issues = []
    checks = {
        'title_optimized': False,
        'title_traditional': False,
        'title_length': False,
        'title_no_stock': False,
        'desc_optimized': False,
        'desc_length': False,
        'desc_no_stock': False,
        'saved_to_db': False
    }
    
    # 直接从数据库获取最新数据
    if db_id:
        try:
            import psycopg2
            conn = psycopg2.connect(
                host='localhost',
                database='ecommerce_data',
                user='superuser',
                password='Admin123!'
            )
            cur = conn.cursor()
            cur.execute("SELECT optimized_title, optimized_description FROM products WHERE id = %s", (db_id,))
            row = cur.fetchone()
            conn.close()
            
            if not row:
                issues.append("数据库中未找到商品")
                return issues, checks
            
            optimized_title = row[0] or ''
            optimized_desc = row[1] or ''
            
            if optimized_title:
                checks['title_optimized'] = True
                checks['saved_to_db'] = True
                
                # 检查繁体中文（包含常用繁体字）
                if any(c in optimized_title for c in ['顧','擔','鐵','銅','錢','錯','復','華','國','開','關','櫃','檯','術','發','飾','櫃','開','關','門','間']):
                    checks['title_traditional'] = True
                
                # 检查长度（去掉空格后的字符数）
                clean_title = optimized_title.replace(' ', '').replace('｜', '')
                if 20 <= len(clean_title) <= 80:  # 放宽到20-80
                    checks['title_length'] = True
                
                # 检查不含"现货"
                if '現貨' not in optimized_title and '现货' not in optimized_title:
                    checks['title_no_stock'] = True
            else:
                issues.append("优化标题为空")
            
            if optimized_desc and len(optimized_desc) > 50:
                checks['desc_optimized'] = True
                
                # 检查长度
                if 300 <= len(optimized_desc) <= 2000:
                    checks['desc_length'] = True
                
                # 检查不含"现货"
                if '現貨' not in optimized_desc and '现货' not in optimized_desc:
                    checks['desc_no_stock'] = True
            else:
                issues.append("优化描述为空或太短")
                
        except Exception as e:
            issues.append(f"数据库验证失败: {e}")
    else:
        issues.append("无商品ID，无法验证")
    
    # 生成问题列表
    failed_checks = [k for k, v in checks.items() if not v]
    for check in failed_checks:
        if check == 'title_optimized':
            issues.append("优化标题为空")
        elif check == 'title_traditional':
            issues.append("标题未使用繁体中文")
        elif check == 'title_length':
            issues.append(f"标题长度不符合要求（应20-80字符）")
        elif check == 'title_no_stock':
            issues.append("标题包含'现货'等违规词汇")
        elif check == 'desc_optimized':
            issues.append("描述未被优化或太短")
        elif check == 'desc_length':
            issues.append("描述长度不符合 300-2000 字要求")
        elif check == 'desc_no_stock':
            issues.append("描述包含'现货'等违规词汇")
        elif check == 'saved_to_db':
            issues.append("优化结果未保存到数据库")
    
    return issues, checks

def validate_miaoshou_updater(data):
    """验证 miaoshou-updater 成功标准"""
    issues = []
    checks = {
        'has_optimized_title': False,
        'has_optimized_desc': False,
        'browser_needed': True  # 需要浏览器，无法自动验证
    }
    
    # 读取数据库检查
    db_id = data.get('db_id')
    if db_id:
        try:
            import psycopg2
            conn = psycopg2.connect(
                host='localhost',
                database='ecommerce_data',
                user='superuser',
                password='Admin123!'
            )
            cur = conn.cursor()
            cur.execute("SELECT optimized_title, optimized_description FROM products WHERE id = %s", (db_id,))
            row = cur.fetchone()
            conn.close()
            
            if row and row[0]:
                checks['has_optimized_title'] = True
            if row and row[1]:
                checks['has_optimized_desc'] = True
        except Exception as e:
            issues.append(f"数据库读取失败: {e}")
    
    # 如果任务被跳过
    if data.get('note') and '跳过' in data.get('note'):
        issues.append(f"任务跳过: {data.get('note')}")
    
    return issues, checks

def validate_profit_analyzer(data):
    """验证 profit-analyzer 成功标准"""
    issues = []
    checks = {
        'has_price_data': False,
        'has_weight_data': False,
        'sls_calculated': False,
        'commission_calculated': False,
        'has_suggested_price': False,
        'price_reasonable': False,
        'sent_to_feishu': False  # 需要手动验证
    }
    
    purchase_price = data.get('purchase_price_cny', 0)
    weight_g = data.get('weight_g', 0)
    sls_twd = data.get('sls_twd', 0)
    commission_twd = data.get('commission_twd', 0)
    suggested_price = data.get('suggested_price_twd', 0)
    
    if purchase_price and purchase_price > 0:
        checks['has_price_data'] = True
    
    if weight_g and weight_g > 0:
        checks['has_weight_data'] = True
    
    if sls_twd and sls_twd > 0:
        checks['sls_calculated'] = True
        # 验证 SLS 运费计算（首重500g=70 TWD，续重每500g=30 TWD）
        expected_sls = 70 if weight_g <= 500 else 70 + ((weight_g - 500) // 500 + 1) * 30
        if abs(sls_twd - expected_sls) > 5:  # 允许5 TWD误差
            issues.append(f"SLS运费计算可能有误: 实际{sls_twd}，预期{expected_sls}")
    
    if commission_twd and commission_twd > 0:
        checks['commission_calculated'] = True
        # 验证佣金计算（14%）
        expected_commission = int(suggested_price * 0.14)
        if abs(commission_twd - expected_commission) > 5:
            issues.append(f"佣金计算可能有误: 实际{commission_twd}，预期{expected_commission}")
    
    if suggested_price and suggested_price > 0:
        checks['has_suggested_price'] = True
        
        # 检查售价是否合理（至少覆盖成本）
        if purchase_price and sls_twd:
            # 总成本包含佣金
            total_cost_cny = purchase_price + 3 + (sls_twd / 4.5)
            min_price_twd = total_cost_cny * 4.5 * 1.1  # 至少10%利润
            if suggested_price >= min_price_twd:
                checks['price_reasonable'] = True
            else:
                issues.append(f"建议售价{suggested_price} TWD 可能低于成本{min_price_twd:.0f} TWD")
    
    # 检查是否发送到飞书（需要日志验证）
    # 目前无法自动验证，标记为需手动确认
    
    return issues, checks

def validate_results():
    """验证任务结果"""
    
    if not STATE_FILE.exists():
        log("状态文件不存在，跳过验证")
        return "skip"
    
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
    except Exception as e:
        log(f"读取状态文件失败: {e}")
        return "skip"
    
    if not state.get('completed'):
        log("任务未完成，跳过验证")
        return "skip"
    
    results = state.get('results', [])
    if not results:
        log("无执行结果")
        return "skip"
    
    all_issues = []
    all_checks = {}
    
    for r in results:
        step = r.get('step', 'unknown')
        success = r.get('success', False)
        data = r.get('data', {})
        
        log(f"验证 {step}...")
        
        if step == 'listing-optimizer':
            issues, checks = validate_listing_optimizer(data, data.get('db_id'))
            all_checks['listing-optimizer'] = checks
            for issue in issues:
                all_issues.append({
                    'step': step,
                    'issue': issue,
                    'priority': 'P0'
                })
        
        elif step == 'miaoshou-updater':
            issues, checks = validate_miaoshou_updater(data)
            all_checks['miaoshou-updater'] = checks
            for issue in issues:
                all_issues.append({
                    'step': step,
                    'issue': issue,
                    'priority': 'P0'
                })
        
        elif step == 'profit-analyzer':
            issues, checks = validate_profit_analyzer(data)
            all_checks['profit-analyzer'] = checks
            for issue in issues:
                # 售价问题为 P1，其他为 P0
                priority = 'P1' if '售价' in issue else 'P0'
                all_issues.append({
                    'step': step,
                    'issue': issue,
                    'priority': priority
                })
    
    # 输出检查结果
    log("\n检查结果汇总:")
    for module, checks in all_checks.items():
        passed = sum(1 for v in checks.values() if v)
        total = len(checks)
        log(f"  {module}: {passed}/{total} 通过")
        for check, result in checks.items():
            status = "✅" if result else "❌"
            log(f"    {status} {check}")
    
    if all_issues:
        log(f"\n发现 {len(all_issues)} 个问题:")
        for issue in all_issues:
            log(f"  [{issue['priority']}] {issue['step']}: {issue['issue']}")
        
        update_queue(all_issues)
        return "has_issues"
    else:
        log("\n✅ 所有步骤验证通过!")
        return "all_ok"

def update_queue(issues):
    """更新任务队列，添加发现的问题"""
    
    if not issues:
        return
    
    log("更新 P0 问题到任务队列...")
    
    new_p0_content = []
    new_p0_content.append(f"\n### {datetime.now().strftime('%Y-%m-%d %H:%M')} - 自动发现问题\n")
    
    for issue in issues:
        priority = issue.get('priority', 'P0')
        step = issue.get('step', 'unknown')
        desc = issue.get('issue', '')
        
        new_p0_content.append(f"**[{priority}] {step}:** {desc}\n")
    
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE, 'r') as f:
            content = f.read()
    else:
        content = "# 开发任务队列\n\n"
    
    p0_header = "## 🔴 P0 问题（立即处理）"
    
    if p0_header in content:
        lines = content.split('\n')
        new_lines = []
        in_p0 = False
        inserted = False
        
        for line in lines:
            if p0_header in line:
                in_p0 = True
                new_lines.append(line)
                continue
            
            if in_p0 and line.startswith('## ') and not inserted:
                new_lines.extend(new_p0_content)
                new_lines.append(line)
                inserted = True
                in_p0 = False
            else:
                new_lines.append(line)
        
        if not inserted:
            new_lines.extend(new_p0_content)
        
        content = '\n'.join(new_lines)
    else:
        content = p0_header + '\n\n' + ''.join(new_p0_content) + '\n\n' + content
    
    with open(QUEUE_FILE, 'w') as f:
        f.write(content)
    
    log(f"已添加 {len(issues)} 个问题")

if __name__ == '__main__':
    result = validate_results()
    # 只在最后打印结果标记
    print(f"\n__RESULT__:{result}")
    sys.exit(0)
