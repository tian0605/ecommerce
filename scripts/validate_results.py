#!/usr/bin/env python3
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportMissingParameterType=false
"""
验证任务执行结果
检查 task_state.json 中的结果是否满足成功标准
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, cast

SCRIPTS_DIR = Path('/root/.openclaw/workspace-e-commerce/scripts')
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from multisite_config import load_market_bundle, normalize_site_context  # type: ignore

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
STATE_FILE = WORKSPACE / 'logs' / 'task_state.json'
QUEUE_FILE = WORKSPACE / 'docs' / 'dev-task-queue.md'
FEISHU_TABLE_URL = "https://pcn0wtpnjfsd.feishu.cn/base/DyzjbfaZZaYeJls6lDFc5DavnPd"


DEFAULT_TITLE_FORBIDDEN_TERMS = ['现货', '現貨']
DEFAULT_DESC_FORBIDDEN_TERMS = ['现货', '現貨']


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == '':
            return default
        return float(value)
    except Exception:
        return default


def parse_json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except Exception:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def shipping_profile_value(shipping_profile: Dict[str, Any], key: str) -> Any:
    direct = shipping_profile.get(key)
    if direct not in (None, ''):
        return direct
    return parse_json_object(shipping_profile.get('metadata')).get(key)


def resolve_runtime_bundle(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload_dict = payload or {}
    site_context = cast(Dict[str, Any], normalize_site_context(payload_dict))
    try:
        return load_market_bundle(None, market_code=site_context.get('market_code'), site_code=site_context.get('site_code'))
    except Exception:
        return {
            'site_context': site_context,
            'market_config': {},
            'shipping_profile': {},
            'content_policy': {},
        }


def merge_forbidden_terms(content_policy: Dict[str, Any]) -> List[str]:
    forbidden_terms = list(DEFAULT_TITLE_FORBIDDEN_TERMS)
    for term in cast(List[Any], content_policy.get('forbidden_terms_json') or []):
        normalized = str(term or '').strip()
        if normalized and normalized not in forbidden_terms:
            forbidden_terms.append(normalized)
    return forbidden_terms


def looks_traditional_chinese(text: str) -> bool:
    traditional_chars = ['顧','擔','鐵','銅','錢','錯','復','華','國','開','關','櫃','檯','術','發','飾','門','間','體','燈']
    return any(char in text for char in traditional_chars)


def looks_english_text(text: str) -> bool:
    if not text:
        return False
    latin_letters = re.findall(r'[A-Za-z]', text)
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    return len(latin_letters) >= 10 and len(latin_letters) > len(chinese_chars)

def log(msg: Any) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 验证: {msg}", flush=True)

def validate_listing_optimizer(data: Dict[str, Any], db_id: Any):
    """验证 listing-optimizer 成功标准 - 直接从数据库检查"""
    bundle = resolve_runtime_bundle(data)
    site_context = bundle.get('site_context') or {}
    content_policy = bundle.get('content_policy') or {}
    listing_language = str(content_policy.get('listing_language') or site_context.get('listing_language') or 'zh-Hant').strip()
    forbidden_terms = merge_forbidden_terms(content_policy)
    title_min_length = int(content_policy.get('title_min_length') or 20)
    title_max_length = int(content_policy.get('title_max_length') or 80)
    description_min_length = int(content_policy.get('description_min_length') or 300)
    description_max_length = int(content_policy.get('description_max_length') or 2000)

    issues: List[str] = []
    checks = {
        'title_optimized': False,
        'title_language': False,
        'title_length': False,
        'title_no_forbidden_terms': False,
        'desc_optimized': False,
        'desc_length': False,
        'desc_no_forbidden_terms': False,
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
                
                if listing_language.lower().startswith('en'):
                    checks['title_language'] = looks_english_text(optimized_title)
                else:
                    checks['title_language'] = looks_traditional_chinese(optimized_title)
                
                # 检查长度（去掉空格后的字符数）
                clean_title = optimized_title.replace(' ', '').replace('｜', '')
                if title_min_length <= len(clean_title) <= title_max_length:
                    checks['title_length'] = True
                
                if not any(term in optimized_title for term in forbidden_terms):
                    checks['title_no_forbidden_terms'] = True
            else:
                issues.append("优化标题为空")
            
            if optimized_desc and len(optimized_desc) > 50:
                checks['desc_optimized'] = True
                
                # 检查长度
                if description_min_length <= len(optimized_desc) <= description_max_length:
                    checks['desc_length'] = True
                
                if not any(term in optimized_desc for term in forbidden_terms):
                    checks['desc_no_forbidden_terms'] = True
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
        elif check == 'title_language':
            if listing_language.lower().startswith('en'):
                issues.append("标题未使用英语输出")
            else:
                issues.append("标题未使用配置要求的繁体中文")
        elif check == 'title_length':
            issues.append(f"标题长度不符合要求（应 {title_min_length}-{title_max_length} 字符）")
        elif check == 'title_no_forbidden_terms':
            issues.append("标题包含 content policy 禁用词")
        elif check == 'desc_optimized':
            issues.append("描述未被优化或太短")
        elif check == 'desc_length':
            issues.append(f"描述长度不符合 {description_min_length}-{description_max_length} 字要求")
        elif check == 'desc_no_forbidden_terms':
            issues.append("描述包含 content policy 禁用词")
        elif check == 'saved_to_db':
            issues.append("优化结果未保存到数据库")
    
    return issues, checks

def validate_miaoshou_updater(data: Dict[str, Any]):
    """验证 miaoshou-updater 成功标准"""
    issues: List[str] = []
    bundle = resolve_runtime_bundle(data)
    market_config = bundle.get('market_config') or {}
    checks = {
        'has_optimized_title': False,
        'has_optimized_desc': False,
        'publish_allowed': market_config.get('allow_publish', True) is True,
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
    note = str(data.get('note') or '')
    if note and '跳过' in note:
        issues.append(f"任务跳过: {note}")

    if not checks['publish_allowed']:
        issues.append("当前 market config 禁止发布")
    
    return issues, checks

def validate_profit_analyzer(data: Dict[str, Any]):
    """验证 profit-analyzer 成功标准"""
    bundle = resolve_runtime_bundle(data)
    market_config = bundle.get('market_config') or {}
    shipping_profile = bundle.get('shipping_profile') or {}
    local_currency = str(market_config.get('default_currency') or data.get('currency') or 'TWD').upper()
    first_weight_g = parse_float(shipping_profile_value(shipping_profile, 'first_weight_g'), 500)
    first_weight_fee = parse_float(shipping_profile_value(shipping_profile, 'first_weight_fee'), 70)
    continue_weight_g = max(parse_float(shipping_profile_value(shipping_profile, 'continue_weight_g'), 500), 1)
    continue_weight_fee = parse_float(shipping_profile_value(shipping_profile, 'continue_weight_fee'), 30)
    commission_rate = parse_float(shipping_profile_value(shipping_profile, 'commission_rate'), 0.14)
    transaction_fee_rate = parse_float(shipping_profile_value(shipping_profile, 'transaction_fee_rate'), 0.025)
    pre_sale_service_rate = parse_float(shipping_profile_value(shipping_profile, 'pre_sale_service_rate'), 0.03)

    issues: List[str] = []
    checks = {
        'has_price_data': False,
        'has_weight_data': False,
        'shipping_calculated': False,
        'commission_calculated': False,
        'has_suggested_price': False,
        'price_reasonable': False,
        'sent_to_feishu': False  # 需要手动验证
    }
    
    purchase_price = data.get('purchase_price_cny', 0)
    weight_g = data.get('chargeable_weight_g') or data.get('weight_g', 0)
    shipping_fee_local = data.get('platform_shipping_fee_local') or data.get('sls_twd', 0)
    commission_local = data.get('commission_local') or data.get('commission_twd', 0)
    suggested_price = data.get('suggested_price_local') or data.get('suggested_price_twd', 0)
    
    if purchase_price and purchase_price > 0:
        checks['has_price_data'] = True
    
    if weight_g and weight_g > 0:
        checks['has_weight_data'] = True
    
    if shipping_fee_local and shipping_fee_local > 0:
        checks['shipping_calculated'] = True
        expected_shipping = first_weight_fee if weight_g <= first_weight_g else first_weight_fee + (((weight_g - first_weight_g) // continue_weight_g) + 1) * continue_weight_fee
        if abs(parse_float(shipping_fee_local) - expected_shipping) > max(5, continue_weight_fee):
            issues.append(f"运费计算可能有误: 实际{shipping_fee_local} {local_currency}，预期{expected_shipping:.0f} {local_currency}")
    
    if commission_local and commission_local > 0:
        checks['commission_calculated'] = True
        expected_commission = suggested_price * commission_rate
        if abs(parse_float(commission_local) - expected_commission) > 5:
            issues.append(f"佣金计算可能有误: 实际{commission_local} {local_currency}，预期{expected_commission:.0f} {local_currency}")
    
    if suggested_price and suggested_price > 0:
        checks['has_suggested_price'] = True
        
        # 检查售价是否合理（至少覆盖成本）
        if purchase_price and shipping_fee_local:
            # 总成本包含佣金
            exchange_rate = parse_float(data.get('exchange_rate'), 4.5 if local_currency == 'TWD' else 7.8)
            agent_fee_cny = parse_float(data.get('agent_fee_cny'), parse_float(shipping_profile_value(shipping_profile, 'agent_fee_cny'), 3))
            total_fee_rate = commission_rate + transaction_fee_rate + pre_sale_service_rate
            total_cost_cny = purchase_price + agent_fee_cny + (parse_float(shipping_fee_local) / exchange_rate)
            min_price_local = total_cost_cny * exchange_rate * max(1.05, 1 + total_fee_rate)
            if suggested_price >= min_price_local:
                checks['price_reasonable'] = True
            else:
                issues.append(f"建议售价{suggested_price} {local_currency} 可能低于成本{min_price_local:.0f} {local_currency}")
    
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
    
    all_issues: List[Dict[str, Any]] = []
    all_checks: Dict[str, Dict[str, bool]] = {}
    
    for r in results:
        step = r.get('step', 'unknown')
        data = cast(Dict[str, Any], r.get('data', {}))
        
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

def update_queue(issues: List[Dict[str, Any]]) -> None:
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
