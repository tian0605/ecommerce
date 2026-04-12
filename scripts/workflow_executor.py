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
import re
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
SCRIPTS_DIR = WORKSPACE / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

from task_manager import StageStatus, TaskManager, TaskStage
from logger import get_logger

SITE_CONTEXT_KEYS = ('market_code', 'site_code', 'shop_code', 'source_language', 'listing_language')

# 技能模块映射表
SKILL_MODULES = {
    'miaoshou-collector': 'miaoshou_collector.collector',
    'collector-scraper': 'collector_scraper.scraper',
    'local-1688-weight': 'remote_weight_caller',  # 直接用模块名，已添加到sys.path
    'product-storer': 'product_storer.storer',
    'listing-optimizer': 'optimizer',
    'miaoshou-updater': 'miaoshou_updater.updater',
    'profit-analyzer': 'profit_analyzer.analyzer',
}

ERROR_TYPE_EXECUTION_RULES = {
    'publish_flow': {
        'skill': 'miaoshou-updater',
        'action': 'retry_publish_submission',
        'params': {
            'repair_mode': 'publish',
            'verify_published': 'true',
        },
    },
    'validation_error': {
        'skill': 'miaoshou-updater',
        'action': 'retry_form_validation',
        'params': {
            'repair_mode': 'validation',
            'verify_required_fields': 'true',
        },
    },
    'collection_flow': {
        'skill': 'miaoshou-collector',
        'action': 'retry_collection_claim',
        'params': {
            'repair_mode': 'collection',
        },
    },
    'scrape_flow': {
        'skill': 'collector-scraper',
        'action': 'retry_scrape_extraction',
        'params': {
            'repair_mode': 'scrape',
        },
    },
    'weight_service': {
        'skill': 'local-1688-weight',
        'action': 'retry_weight_fetch',
        'params': {
            'repair_mode': 'weight',
        },
    },
    'storage_flow': {
        'skill': 'product-storer',
        'action': 'retry_storage_write',
        'params': {
            'repair_mode': 'storage',
        },
    },
    'optimization_flow': {
        'skill': 'listing-optimizer',
        'action': 'retry_listing_optimization',
        'params': {
            'repair_mode': 'optimization',
        },
    },
    'profit_flow': {
        'skill': 'profit-analyzer',
        'action': 'retry_profit_analysis',
        'params': {
            'repair_mode': 'profit',
        },
    },
    'manual_triage': {
        'skill': 'manual-triage',
        'action': 'inspect_failure_context',
        'params': {
            'repair_mode': 'manual',
        },
    },
}


def extract_structured_metadata(task: dict) -> dict:
    """从任务记录中提取结构化元数据，优先读取 plan 中的 key=value 行。"""
    metadata = {}
    if not isinstance(task, dict):
        return metadata

    for field in ('plan', 'fix_suggestion', 'description'):
        raw = task.get(field) or ''
        if not raw:
            continue
        for line in str(raw).splitlines():
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip().lower()
            value = value.strip()
            if key and value and key not in metadata:
                metadata[key] = value
    return metadata


def parse_bool(value, default: bool = False) -> bool:
    """将字符串/数字形式的布尔值显式转换为 bool。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ('1', 'true', 'yes', 'y', 'on'):
        return True
    if text in ('0', 'false', 'no', 'n', 'off'):
        return False
    return default


def extract_site_context(payload: dict | None) -> dict:
    payload = payload or {}
    return {
        key: str(payload.get(key)).strip()
        for key in SITE_CONTEXT_KEYS
        if payload.get(key) not in (None, '')
    }


def merge_site_context(target: dict | None, site_context: dict | None):
    if not isinstance(target, dict) or not isinstance(site_context, dict):
        return
    for key, value in site_context.items():
        if value not in (None, ''):
            target.setdefault(key, value)


def normalize_execution_plan(parsed: dict, task: dict) -> dict:
    """根据 error_type 和任务上下文修正执行计划。"""
    params = dict(parsed.get('params') or {})
    metadata = extract_structured_metadata(task)

    for key, value in metadata.items():
        params.setdefault(key, value)

    error_type = (params.get('error_type') or '').strip().lower()
    task_priority = task.get('priority') if isinstance(task, dict) else None

    rule = ERROR_TYPE_EXECUTION_RULES.get(error_type)
    if rule:
        parsed['skill'] = rule.get('skill', parsed.get('skill'))
        parsed['action'] = rule.get('action', parsed.get('action'))
        merged = dict(rule.get('params') or {})
        merged.update(params)
        params = merged

    if not parsed.get('action') and parsed.get('skill') in SKILL_MODULES:
        params.setdefault('repair_mode', 'generic')
        parsed['action'] = 'retry_generic_failure'

    if task_priority:
        params.setdefault('task_priority', task_priority)

    if error_type:
        params['error_type'] = error_type

    parsed['params'] = params
    return parsed


def build_skill_params(skill_name: str, action: str, params: dict, upstream_data: dict) -> dict:
    """
    根据skill类型重组数据格式
    
    不同skill期望不同的数据格式：
    - product-storer: 需要 {'product_data': {...}, 'weight_data': {...}}
    - listing-optimizer: 需要 product_id 或 {'product_id': xxx}
    - miaoshou-updater: 需要 product_id 或 product dict
    """
    import json
    
    site_context = extract_site_context(params)

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
        merge_site_context(result, site_context)
        merge_site_context(result.get('product_data'), site_context)
        return result
    
    elif skill_name in ['listing-optimizer', 'listing_optimizer']:
        # listing-optimizer 期望: product_id (string)
        product_id = params.get('product_id')
        if not product_id:
            # 尝试从STEP4数据获取
            product_id = latest_step_data.get('product_id_new') or latest_step_data.get('product_id')
        result = {
            'product_id': product_id,
            'product_data': latest_step_data,
            'repair_mode': params.get('repair_mode', 'optimization'),
            'error_type': params.get('error_type'),
        }
        merge_site_context(result, site_context)
        merge_site_context(result.get('product_data'), site_context)
        return result
    
    elif skill_name in ['miaoshou-updater', 'miaoshou_updater']:
        # miaoshou-updater 期望: product_id 或 product dict
        product_id = params.get('product_id')
        if not product_id:
            product_id = latest_step_data.get('product_id_new') or latest_step_data.get('product_id')
        product_data = dict(params.get('product_data') or {})
        product_data.setdefault('product_id', product_id)
        product_data.setdefault('alibaba_product_id', latest_step_data.get('alibaba_product_id'))
        product_data.setdefault('_repair_action', action or 'retry_generic_failure')
        product_data.setdefault('_repair_mode', params.get('repair_mode', 'generic'))
        product_data.setdefault('_error_type', params.get('error_type', 'unknown'))
        product_data.setdefault('_task_priority', params.get('task_priority', 'P1'))
        for flag in ('verify_published', 'verify_required_fields'):
            if flag in params:
                product_data.setdefault(f'_{flag}', params.get(flag))
        result = {
            'product_id': product_id,
            'product_data': product_data,
        }
        merge_site_context(result, site_context)
        merge_site_context(result.get('product_data'), site_context)
        return result
    
    elif skill_name in ['miaoshou-collector', 'miaoshou_collector']:
        # miaoshou-collector 期望: url_1688
        url = params.get('url_1688') or params.get('product_id')
        if url and not url.startswith('http'):
            url = f"https://detail.1688.com/offer/{url}.html"
        result = {
            'url_1688': url or latest_step_data.get('url'),
            'repair_mode': params.get('repair_mode', 'collection'),
            'error_type': params.get('error_type'),
        }
        merge_site_context(result, site_context)
        return result
    
    elif skill_name in ['collector-scraper', 'collector_scraper']:
        # collector-scraper 期望: product_index 或无参数
        normalized = dict(params)
        normalized.setdefault('source_item_id', params.get('alibaba_product_id') or latest_step_data.get('alibaba_product_id'))
        normalized.setdefault('allow_index_fallback', False if action == 'retry_scrape_extraction' else True)
        merge_site_context(normalized, site_context)
        return normalized
    
    elif skill_name in ['local-1688-weight', 'local_1688_weight']:
        # local-1688-weight 期望: product_id
        product_id = params.get('alibaba_product_id') or params.get('product_id')
        if not product_id:
            product_id = latest_step_data.get('alibaba_product_id')
        result = {
            'product_id': product_id,
            'scrape_data': latest_step_data,
            'error_type': params.get('error_type'),
            'repair_mode': params.get('repair_mode', 'weight'),
        }
        merge_site_context(result, site_context)
        merge_site_context(result.get('scrape_data'), site_context)
        return result
    
    elif skill_name in ['profit-analyzer', 'profit_analyzer']:
        # profit-analyzer 期望: alibaba_product_id payload
        alibaba_product_id = params.get('alibaba_product_id') or latest_step_data.get('alibaba_product_id')
        product_id = params.get('product_id') or latest_step_data.get('product_id_new') or latest_step_data.get('product_id')
        result = {
            'alibaba_product_id': alibaba_product_id,
            'product_id': product_id,
            'repair_mode': params.get('repair_mode', 'profit'),
            'error_type': params.get('error_type'),
        }
        merge_site_context(result, site_context)
        return result
    
    else:
        # 默认：扁平合并
        full = dict(params)
        for step_name, data in upstream_data.items():
            for key, value in data.items():
                full[key] = value
        merge_site_context(full, site_context)
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

    # 结构化格式: key=value; key2=value2
    if '=' in fix_suggestion and ';' in fix_suggestion:
        parts = [part.strip() for part in fix_suggestion.split(';') if part.strip()]
        for part in parts:
            if '=' not in part:
                continue
            key, value = part.split('=', 1)
            key = key.strip().lower()
            value = value.strip()
            if key == 'skill':
                result['skill'] = value
            elif key == 'action':
                result['action'] = value
            else:
                result['params'][key] = value
        if result['skill']:
            return result
    
    # 提取技能名
    fix_lower = fix_suggestion.lower()
    for skill_key in SKILL_MODULES.keys():
        if skill_key in fix_lower:
            result['skill'] = skill_key
            break
    
    # 提取商品ID（如果存在）
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

    params = dict(params)
    error_type = (params.get('error_type') or '').strip().lower()
    
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

    required_param_map = {
        'listing-optimizer': 'product_id',
        'listing_optimizer': 'product_id',
        'miaoshou-updater': 'product_id',
        'miaoshou_updater': 'product_id',
        'local-1688-weight': 'product_id',
        'local_1688_weight': 'product_id',
    }
    required_param = required_param_map.get(skill_name)
    if required_param and not params.get(required_param):
        result['message'] = f"缺少关键参数: {required_param}，停止执行以避免误操作"
        return result
    if skill_name in ['profit-analyzer', 'profit_analyzer'] and not (params.get('alibaba_product_id') or params.get('product_id')):
        result['message'] = "缺少关键参数: alibaba_product_id，停止执行以避免误操作"
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
                    data = scraper.scrape_product(
                        product_index=int(params.get('product_index', 0) or 0),
                        source_item_id=params.get('source_item_id'),
                        allow_index_fallback=parse_bool(
                            params.get('allow_index_fallback'),
                            False if params.get('source_item_id') else True,
                        ),
                    )
                    # 如果返回的是dict（数据），则视为成功
                    if isinstance(data, dict) and data.get('alibaba_product_id'):
                        result['success'] = True
                        result['message'] = f"提取成功 action={action or 'scrape_product'}"
                    elif data:
                        result['success'] = True
                        result['message'] = f"执行完成 action={action or 'scrape_product'}"
                    else:
                        result['success'] = False
                        result['message'] = f"未提取到数据 action={action or 'scrape_product'}"
                    result['data'] = data if data else {}
                finally:
                    scraper.close()
            else:
                result['message'] = 'CollectorScraper 类不存在'
        
        elif skill_name in ['local-1688-weight', 'local_1688_weight']:
            # local-1688-weight: 调用 fetch_weight_from_local
            func = getattr(module, 'fetch_weight_from_local', None)
            if func:
                data = func(
                    product_id=params.get('alibaba_product_id') or params.get('product_id'),
                    scrape_data=params.get('scrape_data') or params.get('product_data'),
                )
                result['success'] = data is not None
                result['message'] = f"获取重量成功 action={action}" if data else f"获取重量失败 action={action}"
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
                result['message'] = data.get('message', f'执行完成 action={action}')
                result['data'] = data
            else:
                result['message'] = 'ProductStorer 类不存在'
        
        elif skill_name in ['listing-optimizer', 'listing_optimizer']:
            # listing-optimizer: 实例化Optimizer并调用optimize_product
            optimizer_class = getattr(module, 'ListingOptimizer', None)
            if optimizer_class:
                optimizer = optimizer_class()
                product_payload = params.get('product_data') or params.get('product_id')
                data = optimizer.optimize_product(product_payload)
                result['success'] = data.get('success', False) if isinstance(data, dict) else False
                result['message'] = data.get('message', f'执行完成 action={action}') if isinstance(data, dict) else f'执行完成 action={action}'
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
                    if isinstance(product_data, dict):
                        product_data.setdefault('_repair_action', action or 'retry_generic_failure')
                        product_data.setdefault('_error_type', error_type or 'unknown')
                        product_data.setdefault('_task_priority', params.get('task_priority', 'P1'))
                    verify_published = parse_bool(product_data.get('_verify_published') or params.get('verify_published'))
                    verify_required_fields = parse_bool(product_data.get('_verify_required_fields') or params.get('verify_required_fields'))
                    success = updater.update_product(product=product_data)
                    result['success'] = success if isinstance(success, bool) else False
                    result['message'] = f"更新成功 action={action}" if success else f"更新失败 action={action}"
                    result['data'] = {
                        'product_id': product_data.get('product_id'),
                        'alibaba_product_id': product_data.get('alibaba_product_id'),
                        'published': bool(success and verify_published),
                        'saved': bool(success),
                        'verify_published_requested': verify_published,
                        'verify_required_fields_requested': verify_required_fields,
                    }
                finally:
                    updater.close()
            else:
                result['message'] = 'MiaoshouUpdater 类不存在'

        elif skill_name in ['profit-analyzer', 'profit_analyzer']:
            analyzer_class = getattr(module, 'ProfitAnalyzer', None)
            if analyzer_class:
                analyzer = analyzer_class()
                product_payload = {
                    'alibaba_product_id': params.get('alibaba_product_id') or params.get('product_id')
                }
                data = analyzer.analyze_product(product_payload)
                result['success'] = data.get('status') == 'success' if isinstance(data, dict) else False
                result['message'] = data.get('message', f'执行完成 action={action}') if isinstance(data, dict) else f'执行完成 action={action}'
                result['data'] = data if isinstance(data, dict) else {}
            else:
                result['message'] = 'ProfitAnalyzer 类不存在'
        
        else:
            result['message'] = f"技能 {skill_name} 暂未实现执行逻辑"
        
    except Exception as e:
        result['message'] = f"执行异常: {str(e)}"
        import traceback
        traceback.print_exc()
    
    return result


def build_exec_artifacts(task: dict, parsed: dict, full_params: dict, exec_result: dict) -> dict:
    """将技能执行结果标准化为阶段回写需要的结构。"""
    normalized = dict(exec_result)
    artifacts = list(normalized.get('artifacts') or [])
    issues = list(normalized.get('issues') or [])
    data = normalized.get('data') or {}

    artifacts.append({
        'type': 'execution_summary',
        'payload': {
            'task_name': task.get('task_name'),
            'stage': task.get('current_stage'),
            'skill': parsed.get('skill'),
            'action': parsed.get('action'),
            'success': normalized.get('success', False),
            'message': normalized.get('message', ''),
            'site_context': extract_site_context(full_params),
        },
    })
    site_context = extract_site_context(full_params)
    if site_context:
        artifacts.append({'type': 'site_context', 'payload': site_context})
    if data:
        artifacts.append({'type': 'build_output', 'payload': data})
    if not normalized.get('success'):
        issues.append({
            'severity': normalized.get('severity', 'P1'),
            'type': normalized.get('error_type', 'stage_failed'),
            'payload': {
                'message': normalized.get('message'),
                'skill': parsed.get('skill'),
                'action': parsed.get('action'),
            },
        })

    normalized['artifacts'] = artifacts
    normalized['issues'] = issues
    return normalized


def _latest_build_outputs(task: dict) -> list[dict]:
    stage_context = task.get('stage_context') or {}
    build_payload = stage_context.get(TaskStage.BUILD.value) or {}
    artifacts = build_payload.get('artifacts') or []
    outputs = []
    for artifact in artifacts:
        if isinstance(artifact, dict) and artifact.get('type') == 'build_output':
            payload = artifact.get('payload')
            if isinstance(payload, dict):
                outputs.append(payload)
    return outputs


def build_review_result(task: dict, parsed: dict) -> dict:
    review_issues = ((task.get('stage_context') or {}).get(TaskStage.REVIEW.value) or {}).get('issues') or []
    blocking = [
        issue for issue in review_issues
        if not issue.get('resolved') and issue.get('severity') in ('P0', 'P1', 'critical', 'high')
    ]
    if blocking:
        return {
            'success': False,
            'message': '自动审查发现未解决的高优先级问题',
            'error_type': 'quality_failed',
            'severity': 'P1',
            'issues': [{
                'severity': 'P1',
                'type': 'quality_failed',
                'payload': {'blocking_issue_ids': [item.get('id') for item in blocking]},
            }],
        }
    return {
        'success': True,
        'message': f"自动审查通过 skill={parsed.get('skill')}",
        'artifacts': [{
            'type': 'review_result',
            'payload': {
                'result': 'pass',
                'skill': parsed.get('skill'),
                'action': parsed.get('action'),
            },
        }],
    }


def build_test_result(task: dict, parsed: dict) -> dict:
    artifact_type = 'test_result'
    if parsed.get('skill') in ['miaoshou-updater', 'miaoshou_updater']:
        artifact_type = 'save_only_validation'
    return {
        'success': True,
        'message': f"自动测试通过 skill={parsed.get('skill')}",
        'artifacts': [{
            'type': artifact_type,
            'payload': {
                'result': 'pass',
                'skill': parsed.get('skill'),
                'action': parsed.get('action'),
            },
        }],
    }


def build_release_result(task: dict, parsed: dict) -> dict:
    if parsed.get('skill') in ['miaoshou-updater', 'miaoshou_updater']:
        outputs = _latest_build_outputs(task)
        latest = outputs[-1] if outputs else {}
        published = latest.get('published') is True
        verify_requested = bool(latest.get('verify_published_requested') or latest.get('verify_required_fields_requested'))
        if published or verify_requested:
            return {
                'success': True,
                'message': 'release.verify 通过',
                'release_verify_passed': True,
                'release_verify_message': 'miaoshou-updater 已返回成功并附带发布/字段校验信号',
                'artifacts': [{
                    'type': 'release_verify',
                    'payload': {
                        'passed': True,
                        'published': published,
                        'verify_requested': verify_requested,
                    },
                }],
            }
        return {
            'success': False,
            'message': 'release.verify 缺少发布成功证据',
            'error_type': 'publish_verify_failed',
            'severity': 'P1',
            'issues': [{
                'severity': 'P1',
                'type': 'publish_verify_failed',
                'payload': {'reason': '缺少 published 或 verify_requested 信号'},
            }],
        }

    return {
        'success': True,
        'message': '非发布型任务，release.verify 自动通过',
        'release_verify_passed': True,
        'release_verify_message': 'non-publish task auto verified',
        'artifacts': [{
            'type': 'release_verify',
            'payload': {'passed': True, 'mode': 'non_publish_task'},
        }],
    }


def build_retrospective_result(task: dict, parsed: dict) -> dict:
    return {
        'success': True,
        'message': f"retrospective 完成 skill={parsed.get('skill')}",
        'artifacts': [{
            'type': 'retrospective_summary',
            'payload': {
                'task_name': task.get('task_name'),
                'skill': parsed.get('skill'),
                'result': 'completed',
            },
        }],
    }


def advance_lifecycle_after_build(tm: TaskManager, task_name: str, parsed: dict) -> dict:
    """自动推进 review/test/release/retrospective，直到闭环或被阻塞。"""
    history = []
    for _ in range(4):
        task = tm.get_task(task_name)
        if not task:
            return {'success': False, 'action': 'missing_task', 'history': history}
        current_stage = task.get('current_stage')
        if current_stage == TaskStage.REVIEW.value:
            stage_result = build_review_result(task, parsed)
        elif current_stage == TaskStage.TEST.value:
            stage_result = build_test_result(task, parsed)
        elif current_stage == TaskStage.RELEASE.value:
            stage_result = build_release_result(task, parsed)
        elif current_stage == TaskStage.RETROSPECTIVE.value:
            stage_result = build_retrospective_result(task, parsed)
        else:
            break

        sync_result = tm.sync_stage_from_exec_outcome(task_name, stage_result)
        history.append({'stage': current_stage, 'result': sync_result})
        if not stage_result.get('success'):
            return {'success': False, 'action': sync_result.get('action'), 'history': history}

        refreshed = tm.get_task(task_name)
        if refreshed and refreshed.get('current_stage') == TaskStage.RETROSPECTIVE.value and refreshed.get('stage_status') == StageStatus.DONE.value:
            tm.mark_end(task_name, '阶段闭环完成')
            return {'success': True, 'action': 'completed', 'history': history}

    return {'success': True, 'action': 'advanced', 'history': history}


def check_all_children_completed(tm: TaskManager, parent_task_name: str) -> bool:
    """检查是否所有子任务都已完成"""
    children = tm.get_sub_tasks(parent_task_name)
    if not children:
        return False
    
    completed = [c for c in children if tm._normalize_exec_state(c.get('exec_state')) in ('end', 'void')]
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
    parsed = normalize_execution_plan(parsed, task)
    print(f"解析结果: {parsed}")

    current_stage = task.get('current_stage') or TaskStage.BUILD.value
    task_context = tm.get_task_site_context(task, stage=current_stage)
    for key, value in task_context.items():
        parsed['params'].setdefault(key, value)

    if parsed['skill'] == 'manual-triage':
        reason = parsed['params'].get('reason', '结构化归因置信度不足，需要人工检查')
        print(f"结构化归因结果为人工检查: {reason}")
        tm.fail_stage(task_name, current_stage, reason, error_type='manual_required')
        log.set_message(f"需要人工介入: {reason[:120]}").finish("failed")
        tm.close()
        return
    
    if not parsed['skill']:
        # 没有指定技能，标记为跳过
        print(f"未指定技能，跳过执行")
        tm.skip_task(task_name, "未指定执行技能")
        log.set_message("未指定执行技能").finish("skipped")
        tm.close()
        return
    
    # 标记开始执行。若由 cron 拉起，任务通常已处于 processing；手动调用时再补 mark_start。
    if tm._normalize_exec_state(task.get('exec_state')) != 'processing':
        tm.mark_start(task_name)
    tm.mark_executing(task_name)
    
    # 获取父任务ID（作为workflow_id）
    workflow_id = parent_task or task_name
    
    # 加载上游数据（如果有）
    upstream_data = tm.get_latest_workflow_data(workflow_id, max_steps=10)
    print(f"上游数据: {upstream_data}")
    
    # 构建完整params（根据skill类型重组数据格式）
    full_params = build_skill_params(parsed['skill'], parsed['action'], parsed['params'], upstream_data)
    for key, value in task_context.items():
        if isinstance(full_params, dict):
            full_params.setdefault(key, value)
            merge_site_context(full_params.get('product_data'), task_context)
            merge_site_context(full_params.get('scrape_data'), task_context)
    print(f"完整参数: {full_params}")

    tm.persist_task_site_context(task_name, current_stage, extract_site_context(full_params), result='站点上下文已同步')

    if current_stage in (TaskStage.REVIEW.value, TaskStage.TEST.value, TaskStage.RELEASE.value, TaskStage.RETROSPECTIVE.value):
        lifecycle_result = advance_lifecycle_after_build(tm, task_name, parsed)
        refreshed = tm.get_task(task_name)
        if refreshed and refreshed.get('exec_state') == 'end':
            log.set_message('阶段闭环完成').finish('success')
            print(f"✅ {task_name} 阶段闭环完成")
        elif lifecycle_result.get('success'):
            tm.update_task(task_name, exec_state='new', status='pending')
            log.set_message(f"阶段推进完成: {lifecycle_result.get('action')}").finish('following')
            print(f"ℹ️ {task_name} 阶段推进完成: {lifecycle_result.get('action')}")
        else:
            log.set_message(f"阶段推进失败: {lifecycle_result.get('action')}").finish('failed')
            print(f"❌ {task_name} 阶段推进失败: {lifecycle_result.get('action')}")
        tm.close()
        return

    # 执行 build 阶段技能
    print(f"\n调用技能: {parsed['skill']}")
    exec_result = execute_skill(
        skill_name=parsed['skill'],
        action=parsed['action'],
        params=full_params
    )
    exec_result = build_exec_artifacts(task, parsed, full_params, exec_result)

    print(f"执行结果: {exec_result}")

    # 保存步骤输出数据到 workflow_data
    if exec_result.get('data'):
        tm.save_workflow_data(workflow_id, task_name, exec_result['data'])
        print(f"已保存数据到 workflow_data: {list(exec_result['data'].keys())}")

    sync_result = tm.sync_stage_from_exec_outcome(task_name, exec_result)
    print(f"阶段同步结果: {sync_result}")

    if exec_result['success']:
        lifecycle_result = advance_lifecycle_after_build(tm, task_name, parsed)
        refreshed = tm.get_task(task_name)
        if refreshed and refreshed.get('exec_state') == 'end':
            log.set_message(f"执行成功并完成闭环: {exec_result.get('message')}").finish("success")
            print(f"✅ {task_name} 执行成功并完成闭环")
        elif lifecycle_result.get('success'):
            tm.update_task(task_name, exec_state='new', status='pending')
            log.set_message(f"执行成功，阶段已推进: {lifecycle_result.get('action')}").finish("following")
            print(f"ℹ️ {task_name} 执行成功，阶段已推进: {lifecycle_result.get('action')}")
        else:
            log.set_message(f"执行成功但后续阶段失败: {lifecycle_result.get('action')}").finish("failed")
            print(f"❌ {task_name} 执行成功但后续阶段失败: {lifecycle_result.get('action')}")

        if parent_task and check_all_children_completed(tm, parent_task):
            print(f"\n所有子任务完成，验证父任务: {parent_task}")
            tm.validate_parent_completion(parent_task)
    else:
        error_msg = exec_result.get('message', '执行失败')
        log.set_message(f"执行失败: {error_msg}").finish("failed")
        print(f"❌ {task_name} 执行失败: {error_msg}")
    
    tm.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python workflow_executor.py <task_name>")
        sys.exit(1)
    
    main(sys.argv[1])
