#!/usr/bin/env python3
"""
workflow_executor.py - 工作流任务执行器

专门执行 level=2 的常规子任务：
1. 读取子任务的 fix_suggestion（包含要调用的技能/模块）
2. 调用对应的技能/模块执行
3. 根据执行结果更新任务状态
4. 检查是否所有子任务完成，决定是否触发父任务验证

注意：此执行器不生成修复代码，只负责调用已有的技能模块
"""
import sys
import os
import importlib
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
SCRIPTS_DIR = WORKSPACE / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

from task_manager import TaskManager
from logger import get_logger

# 技能模块映射表
SKILL_MODULES = {
    'miaoshou-collector': 'miaoshou_collector.collector',
    'collector-scraper': 'collector_scraper.scraper',
    'local-1688-weight': 'remote_weight_caller',  # 直接用模块名，已添加到sys.path
    'product-storer': 'product_storer.storer',
    'listing-optimizer': 'listing_optimizer.optimizer',
    'miaoshou-updater': 'miaoshou_updater.updater',
    'profit-analyzer': 'profit_analyzer.analyzer',
}


def build_skill_params(skill_name: str, params: dict, upstream_data: dict) -> dict:
    """
    根据skill类型重组数据格式
    
    不同skill期望不同的数据格式：
    - product-storer: 需要 {'product_data': {...}, 'weight_data': {...}}
    - listing-optimizer: 需要 product_id 或 {'product_id': xxx}
    - miaoshou-updater: 需要 product_id 或 product dict
    """
    import json
    
    # 从上游数据中提取同一step的数据
    latest_step_data = {}
    if upstream_data:
        # 获取最后一个step的数据
        step_names = sorted(upstream_data.keys())
        if step_names:
            latest_step_data = upstream_data.get(step_names[-1], {})
    
    if skill_name in ['product-storer', 'product_storer']:
        # product-storer 期望: {'product_data': {...}, 'weight_data': {...}}
        # 从STEP2获取商品数据
        product_data = {
            'alibaba_product_id': latest_step_data.get('alibaba_product_id'),
            'title': latest_step_data.get('title'),
            'description': latest_step_data.get('description'),
            'category': latest_step_data.get('category'),
            'brand': latest_step_data.get('brand'),
            'origin': latest_step_data.get('origin'),
            'main_images': latest_step_data.get('main_images', []),
            'sku_images': latest_step_data.get('sku_images', []),
            'skus': latest_step_data.get('skus', []),
            'logistics': latest_step_data.get('logistics', {}),
            'source_url': latest_step_data.get('url'),
        }
        # 从STEP3获取重量数据
        weight_data = None
        for step_name, data in upstream_data.items():
            if 'weight' in data or 'weight_g' in str(data):
                weight_data = data
                break
        
        result = {'product_data': product_data, 'weight_data': weight_data}
        # 合并params
        result.update(params)
        return result
    
    elif skill_name in ['listing-optimizer', 'listing_optimizer']:
        # listing-optimizer 期望: product_id (string)
        product_id = params.get('product_id')
        if not product_id:
            # 尝试从STEP4数据获取
            product_id = latest_step_data.get('product_id_new') or latest_step_data.get('product_id')
        return {'product_id': product_id}
    
    elif skill_name in ['miaoshou-updater', 'miaoshou_updater']:
        # miaoshou-updater 期望: product_id 或 product dict
        product_id = params.get('product_id')
        if not product_id:
            product_id = latest_step_data.get('product_id_new') or latest_step_data.get('product_id')
        return {'product_id': product_id}
    
    elif skill_name in ['miaoshou-collector', 'miaoshou_collector']:
        # miaoshou-collector 期望: url_1688
        url = params.get('url_1688') or params.get('product_id')
        if url and not url.startswith('http'):
            url = f"https://detail.1688.com/offer/{url}.html"
        return {'url_1688': url or latest_step_data.get('url')}
    
    elif skill_name in ['collector-scraper', 'collector_scraper']:
        # collector-scraper 期望: product_index 或无参数
        return params
    
    elif skill_name in ['local-1688-weight', 'local_1688_weight']:
        # local-1688-weight 期望: product_id
        product_id = params.get('product_id')
        if not product_id:
            product_id = latest_step_data.get('alibaba_product_id')
        return {'product_id': product_id}
    
    elif skill_name in ['profit-analyzer', 'profit_analyzer']:
        # profit-analyzer 期望: product_id
        product_id = params.get('product_id')
        if not product_id:
            product_id = latest_step_data.get('product_id_new') or latest_step_data.get('product_id')
        return {'product_id': product_id}
    
    else:
        # 默认：扁平合并
        full = dict(params)
        for step_name, data in upstream_data.items():
            for key, value in data.items():
                full[key] = value
        return full


def parse_fix_suggestion(fix_suggestion: str) -> dict:
    """
    解析 fix_suggestion，提取技能和参数
    
    格式: "调用 miaoshou-collector 技能" 或 "调用 miaoshou-collector 采集商品"
    
    Returns:
        {
            'skill': 'miaoshou-collector',
            'action': 'collect_and_claim_shopee',
            'params': {...}
        }
    """
    result = {
        'skill': None,
        'action': None,
        'params': {}
    }
    
    if not fix_suggestion:
        return result
    
    # 提取技能名
    fix_lower = fix_suggestion.lower()
    for skill_key in SKILL_MODULES.keys():
        if skill_key in fix_lower:
            result['skill'] = skill_key
            break
    
    # 提取商品ID（如果存在）
    import re
    product_ids = re.findall(r'\d{10,}', fix_suggestion)
    if product_ids:
        result['params']['product_id'] = product_ids[0]
    
    return result


def execute_skill(skill_name: str, action: str = None, params: dict = None) -> dict:
    """
    执行指定的技能模块
    
    Args:
        skill_name: 技能名称（如 miaoshou-collector）
        action: 要执行的动作（函数名）
        params: 执行参数
    
    Returns:
        {
            'success': True/False,
            'message': '执行结果描述',
            'data': {...}  # 执行返回的数据
        }
    """
    if params is None:
        params = {}
    
    result = {
        'success': False,
        'message': '',
        'data': {}
    }
    
    # 查找技能模块
    skill_module = SKILL_MODULES.get(skill_name)
    if not skill_module:
        result['message'] = f"未知的技能: {skill_name}"
        return result
    
    try:
        # 添加到搜索路径
        skill_base = Path('/home/ubuntu/.openclaw/skills')
        sys.path.insert(0, str(skill_base))
        # 也添加workspace-e-commerce的skills目录（用于local-1688-weight等）
        workspace_skills = Path('/root/.openclaw/workspace-e-commerce/skills')
        if str(workspace_skills) not in sys.path:
            sys.path.insert(0, str(workspace_skills))
        # 添加local-1688-weight的scripts目录
        local_weight_scripts = Path('/root/.openclaw/workspace-e-commerce/skills/local-1688-weight/scripts')
        if str(local_weight_scripts) not in sys.path:
            sys.path.insert(0, str(local_weight_scripts))
        
        # 导入模块
        module = importlib.import_module(skill_module)
        
        # 根据技能类型决定调用方式
        if skill_name in ['miaoshou-collector', 'miaoshou_collector']:
            # miaoshou-collector: 实例化类并调用collect
            collector_class = getattr(module, 'MiaoshouCollector', None)
            if collector_class:
                collector = collector_class()
                collector.launch()
                try:
                    # 从params获取url_1688，如果没有则使用默认测试URL
                    url_1688 = params.get('url_1688') or params.get('product_id')
                    if not url_1688:
                        # 默认测试商品
                        url_1688 = 'https://detail.1688.com/offer/1031400982378.html'
                    elif not url_1688.startswith('http'):
                        url_1688 = f"https://detail.1688.com/offer/{url_1688}.html"
                    data = collector.collect(url_1688=url_1688)
                    result['success'] = data.get('success', False)
                    result['message'] = data.get('message', '执行完成')
                    result['data'] = data
                finally:
                    collector.close()
            else:
                result['message'] = 'MiaoshouCollector 类不存在'
        
        elif skill_name in ['collector-scraper', 'collector_scraper']:
            # collector-scraper: 实例化CollectorScraper，launch，然后scrape
            scraper_class = getattr(module, 'CollectorScraper', None)
            if scraper_class:
                scraper = scraper_class()
                scraper.launch()
                try:
                    data = scraper.scrape_product()
                    # 如果返回的是dict（数据），则视为成功
                    if isinstance(data, dict) and data.get('alibaba_product_id'):
                        result['success'] = True
                        result['message'] = '提取成功'
                    elif data:
                        result['success'] = True
                        result['message'] = '执行完成'
                    else:
                        result['success'] = False
                        result['message'] = '未提取到数据'
                    result['data'] = data if data else {}
                finally:
                    scraper.close()
            else:
                result['message'] = 'CollectorScraper 类不存在'
        
        elif skill_name in ['local-1688-weight', 'local_1688_weight']:
            # local-1688-weight: 调用 fetch_weight_from_local
            func = getattr(module, 'fetch_weight_from_local', None)
            if func:
                data = func(product_id=params.get('product_id'))
                result['success'] = data is not None
                result['message'] = '获取重量成功' if data else '获取重量失败'
                result['data'] = data or {}
            else:
                result['message'] = 'fetch_weight_from_local 函数不存在'
        
        elif skill_name in ['product-storer', 'product_storer']:
            # product-storer: 实例化Storer并调用store
            storer_class = getattr(module, 'ProductStorer', None)
            if storer_class:
                storer = storer_class()
                data = storer.store(params.get('product_data', {}), params.get('weight_data'))
                result['success'] = data.get('success', False)
                result['message'] = data.get('message', '执行完成')
                result['data'] = data
            else:
                result['message'] = 'ProductStorer 类不存在'
        
        elif skill_name in ['listing-optimizer', 'listing_optimizer']:
            # listing-optimizer: 实例化Optimizer并调用optimize_product
            optimizer_class = getattr(module, 'ListingOptimizer', None)
            if optimizer_class:
                optimizer = optimizer_class()
                # 获取product_id，如果没有则从数据库获取最新的
                product_id = params.get('product_id')
                if not product_id:
                    # 从数据库获取最新商品
                    import psycopg2
                    try:
                        conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
                        cur = conn.cursor()
                        cur.execute("SELECT product_id_new FROM products ORDER BY id DESC LIMIT 1")
                        row = cur.fetchone()
                        if row:
                            product_id = row[0]
                            print(f"自动获取最新商品ID: {product_id}")
                        conn.close()
                    except Exception as e:
                        print(f"获取最新商品失败: {e}")
                
                data = optimizer.optimize_product(product_id)
                result['success'] = data.get('success', False) if isinstance(data, dict) else False
                result['message'] = data.get('message', '执行完成') if isinstance(data, dict) else '执行完成'
                result['data'] = data
            else:
                result['message'] = 'ListingOptimizer 类不存在'
        
        elif skill_name in ['miaoshou-updater', 'miaoshou_updater']:
            # miaoshou-updater: 实例化Updater，launch，然后update_product
            updater_class = getattr(module, 'MiaoshouUpdater', None)
            if updater_class:
                updater = updater_class()
                updater.launch()
                try:
                    # update_product 需要 product dict 参数
                    product_data = params.get('product_data') or {'product_id': params.get('product_id')}
                    success = updater.update_product(product=product_data)
                    result['success'] = success if isinstance(success, bool) else False
                    result['message'] = '更新成功' if success else '更新失败'
                finally:
                    updater.close()
            else:
                result['message'] = 'MiaoshouUpdater 类不存在'
        
        else:
            result['message'] = f"技能 {skill_name} 暂未实现执行逻辑"
        
    except Exception as e:
        result['message'] = f"执行异常: {str(e)}"
        import traceback
        traceback.print_exc()
    
    return result


def check_all_children_completed(tm: TaskManager, parent_task_name: str) -> bool:
    """检查是否所有子任务都已完成"""
    children = tm.get_sub_tasks(parent_task_name)
    if not children:
        return False
    
    completed = [c for c in children if c['exec_state'] in ('end', 'void')]
    return len(completed) == len(children)


def main(task_name: str):
    """主函数"""
    log = get_logger('workflow')
    log.set_task(task_name).set_message(f"workflow_executor 开始执行").finish("running")
    
    tm = TaskManager()
    
    # 获取任务信息
    task = tm.get_task(task_name)
    if not task:
        print(f"任务不存在: {task_name}")
        tm.close()
        return
    
    display_name = task.get('display_name', task_name)
    fix_suggestion = task.get('fix_suggestion', '') or task.get('description', '')  # 也检查description字段
    parent_task = task.get('parent_task_id')
    
    print(f"\n{'='*60}")
    print(f"workflow_executor 执行: {display_name}")
    print(f"fix_suggestion: {fix_suggestion}")
    print(f"父任务: {parent_task}")
    print(f"{'='*60}")
    
    # 解析要执行的技能
    parsed = parse_fix_suggestion(fix_suggestion)
    print(f"解析结果: {parsed}")
    
    if not parsed['skill']:
        # 没有指定技能，标记为跳过
        print(f"未指定技能，跳过执行")
        tm.skip_task(task_name, "未指定执行技能")
        log.set_message("未指定执行技能").finish("skipped")
        tm.close()
        return
    
    # 标记开始执行
    tm.mark_start(task_name)
    
    # 获取父任务ID（作为workflow_id）
    workflow_id = parent_task or task_name
    
    # 加载上游数据（如果有）
    upstream_data = tm.get_latest_workflow_data(workflow_id, max_steps=10)
    print(f"上游数据: {upstream_data}")
    
    # 构建完整params（根据skill类型重组数据格式）
    full_params = build_skill_params(parsed['skill'], parsed['params'], upstream_data)
    print(f"完整参数: {full_params}")
    
    # 执行技能
    print(f"\n调用技能: {parsed['skill']}")
    exec_result = execute_skill(
        skill_name=parsed['skill'],
        action=parsed['action'],
        params=full_params
    )
    
    print(f"执行结果: {exec_result}")
    
    if exec_result['success']:
        # 执行成功
        tm.mark_end(task_name, exec_result.get('message', '执行成功'))
        log.set_message(f"执行成功: {exec_result.get('message')}").finish("success")
        print(f"✅ {task_name} 执行成功")
        
        # 保存步骤输出数据到 workflow_data
        if exec_result.get('data'):
            tm.save_workflow_data(workflow_id, task_name, exec_result['data'])
            print(f"已保存数据到 workflow_data: {list(exec_result['data'].keys())}")
        
        # 检查是否所有子任务完成
        if parent_task and check_all_children_completed(tm, parent_task):
            print(f"\n所有子任务完成，验证父任务: {parent_task}")
            tm.validate_parent_completion(parent_task)
    else:
        # 执行失败
        error_msg = exec_result.get('message', '执行失败')
        tm.mark_error_fix_pending(task_name, error_msg)
        log.set_message(f"执行失败: {error_msg}").finish("failed")
        print(f"❌ {task_name} 执行失败: {error_msg}")
    
    tm.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python workflow_executor.py <task_name>")
        sys.exit(1)
    
    main(sys.argv[1])
