#!/usr/bin/env python3
"""
temp_task_executor.py - 临时任务执行器

用于执行开放式临时任务（TEMP task_type='临时任务'）
- 支持断点续传
- 完成后推送飞书通知

使用方式:
    python3 temp_task_executor.py <task_name>
"""
import sys
import os
import json
import re
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
WORKFLOW_RUNNER = WORKSPACE / 'skills' / 'workflow-runner' / 'scripts' / 'workflow_runner.py'
PROFIT_SYNC_RUNNER = WORKSPACE / 'scripts' / 'run_profit_analysis_sync.py'
PROFIT_INIT_RUNNER = WORKSPACE / 'scripts' / 'run_profit_analysis_init.py'
sys.path.insert(0, str(WORKSPACE / 'scripts'))

from task_manager import StageStatus, TaskManager, TaskStage
from logger import get_logger
from notification_service import send_feishu_text
from multisite_config import normalize_site_context
from workflow_executor import advance_lifecycle_after_build

SITE_CONTEXT_KEYS = ('market_code', 'site_code', 'shop_code', 'source_language', 'listing_language')
LEGACY_SITE_LABELS = {
    'shopee_tw': 'TW',
    'shopee_ph': 'PH',
}


def extract_site_context(payload: dict | None) -> dict:
    payload = payload or {}
    extracted = {
        key: str(payload.get(key)).strip()
        for key in SITE_CONTEXT_KEYS
        if payload.get(key) not in (None, '')
    }
    if not extracted:
        return {}
    return normalize_site_context(extracted)


def to_legacy_site_label(site_code: str | None) -> str:
    normalized = str(site_code or '').strip().lower()
    if not normalized:
        return 'TW'
    return LEGACY_SITE_LABELS.get(normalized, normalized.upper())


def build_workflow_runner_context_args(site_context: dict) -> list[str]:
    args: list[str] = []
    option_map = {
        'market_code': '--market-code',
        'site_code': '--site-code',
        'shop_code': '--shop-code',
        'source_language': '--source-language',
        'listing_language': '--listing-language',
    }
    for key in SITE_CONTEXT_KEYS:
        value = site_context.get(key)
        if value not in (None, ''):
            args.extend([option_map[key], str(value)])
    return args


def build_profit_context_args(site_context: dict) -> list[str]:
    args: list[str] = []
    site_code = site_context.get('site_code')
    market_code = site_context.get('market_code')
    if site_code not in (None, ''):
        args.extend(['--site-code', str(site_code)])
        args.extend(['--site', to_legacy_site_label(str(site_code))])
    if market_code not in (None, ''):
        args.extend(['--market-code', str(market_code)])
    return args


def promote_legacy_temp_stage_for_execution(tm: TaskManager, task_name: str, task: dict, script: str | None) -> dict:
    """将历史遗留的可执行 TEMP 任务从 idea/plan 提前切到 build，避免成功后被重复排回队列。"""
    if not script or script == '__stage_replay__':
        return task

    current_stage = tm._normalize_stage(task.get('current_stage')) or TaskStage.PLAN.value
    if current_stage not in {TaskStage.IDEA.value, TaskStage.PLAN.value}:
        return task

    script_name = Path(script).name if script else 'unknown'
    tm.set_stage(
        task_name,
        TaskStage.BUILD.value,
        status=StageStatus.READY.value,
        result=f'TEMP执行器接管 {script_name}，自动从 {current_stage} 切换到 build',
    )
    refreshed = tm.get_task(task_name) or task
    print(f"[stage] {task_name}: {current_stage} -> {TaskStage.BUILD.value} ({script_name})")
    return refreshed


def send_feishu(message: str):
    """发送飞书通知"""
    return send_feishu_text(message)


def update_checkpoint(tm, task_name: str, checkpoint: dict):
    """更新断点"""
    tm.update_checkpoint(task_name, checkpoint)


def ensure_terminal_state(tm, task_name: str, exec_state: str, status: str, result: str = None, error: str = None):
    """收尾后立即回读校验，避免出现日志成功但任务状态未落库。"""
    payload = {
        'exec_state': exec_state,
        'status': status,
    }
    if result is not None:
        payload['last_result'] = result
    if error is not None:
        payload['last_error'] = error

    tm.update_task(task_name, **payload)
    refreshed = tm.get_task(task_name) or {}
    actual_state = str(refreshed.get('exec_state') or '').lower()
    actual_status = str(refreshed.get('status') or '').lower()
    if actual_state != exec_state or actual_status != status:
        tm.update_task(task_name, **payload)


def build_temp_exec_result(task: dict, result: dict, checkpoint: dict) -> dict:
    payload = dict(result)
    artifacts = list(payload.get('artifacts') or [])
    output_data = checkpoint.get('output_data') if isinstance(checkpoint, dict) else None
    if output_data:
        artifacts.append({'type': 'build_output', 'payload': output_data})
    artifacts.append({
        'type': 'execution_summary',
        'payload': {
            'task_name': task.get('task_name'),
            'stage': task.get('current_stage'),
            'success': payload.get('success', False),
            'message': payload.get('output') or payload.get('error') or payload.get('message', ''),
        },
    })
    payload['artifacts'] = artifacts
    payload['message'] = payload.get('output') or payload.get('error') or payload.get('message', '')
    payload.setdefault('data', output_data or {})
    if not payload.get('success'):
        payload.setdefault('error_type', 'stage_failed')
        payload.setdefault('severity', 'P1')
    return payload


def execute_lifecycle_replay(tm, task_name: str, task: dict, checkpoint: dict) -> dict:
    """安全的生命周期回放，不触发外部业务动作。"""
    update_checkpoint(tm, task_name, {
        'current_step': '执行阶段回放',
        'completed_steps': checkpoint.get('completed_steps', []) + ['执行阶段回放'],
        'output_data': {
            'mode': 'lifecycle_replay',
            'source': checkpoint.get('source_task') or task_name,
            'published': bool(checkpoint.get('published', False)),
            'verify_published_requested': bool(checkpoint.get('verify_published_requested', False)),
        },
        'next_action': '阶段回放完成',
        'notes': f"replay @ {datetime.now().strftime('%H:%M:%S')}",
    })
    return {
        'success': True,
        'output': 'TEMP生命周期回放成功',
        'data': {
            'mode': 'lifecycle_replay',
            'source_task': checkpoint.get('source_task') or task_name,
            'published': bool(checkpoint.get('published', False)),
            'verify_published_requested': bool(checkpoint.get('verify_published_requested', False)),
        },
    }


# 任务名称到执行脚本的映射
TASK_SCRIPT_MAP = {
    'AUTO-LISTING': str(WORKFLOW_RUNNER),
    'PROFIT-SYNC': str(PROFIT_SYNC_RUNNER),
    'INIT-PROFIT': str(PROFIT_INIT_RUNNER),
    'REPAIR-': str(WORKFLOW_RUNNER),
    'TEMP-1688-': str(WORKFLOW_RUNNER),
    'TEMP-UPDATER': '/home/ubuntu/.openclaw/skills/miaoshou-updater/updater.py',
    'TEMP-LISTING': str(WORKFLOW_RUNNER),  # 修复：TEMP-LISTING应走完整工作流
}


def get_task_script(task_name: str, task: dict | None = None, checkpoint: dict | None = None):
    """根据任务名称和任务上下文获取执行脚本。"""
    checkpoint = checkpoint or {}
    if checkpoint.get('lifecycle_replay') or checkpoint.get('stage_replay'):
        return '__stage_replay__'

    for prefix, script in TASK_SCRIPT_MAP.items():
        if task_name.startswith(prefix):
            return script

    description = (task or {}).get('description', '') or ''
    if '1688商品' in description or '采集1688商品' in description:
        return str(WORKFLOW_RUNNER)
    if checkpoint.get('full_workflow') or checkpoint.get('url') or checkpoint.get('product_id') or checkpoint.get('alibaba_product_id'):
        return str(WORKFLOW_RUNNER)

    return None


def infer_1688_urls(task: dict, checkpoint: dict) -> list[str]:
    """从断点或描述中推断一个或多个 1688 商品 URL。"""
    urls: list[str] = []

    if isinstance(checkpoint, dict):
        direct_url = checkpoint.get('url')
        if isinstance(direct_url, str) and direct_url.strip():
            urls.append(direct_url.strip())

        raw_products = checkpoint.get('products') or []
        if isinstance(raw_products, list):
            for item in raw_products:
                if isinstance(item, str) and item.strip():
                    urls.append(item.strip())
                elif isinstance(item, dict):
                    candidate = item.get('url') or item.get('product_url') or item.get('offer_url')
                    if isinstance(candidate, str) and candidate.strip():
                        urls.append(candidate.strip())

    product_id = None
    if isinstance(checkpoint, dict):
        product_id = checkpoint.get('product_id') or checkpoint.get('alibaba_product_id')

    if not product_id:
        description = task.get('description', '') or ''
        match = re.search(r'(\d{10,})', description)
        if match:
            product_id = match.group(1)

    if not product_id:
        deduped = list(dict.fromkeys(urls))
        return deduped

    urls.append(f'https://detail.1688.com/offer/{product_id}.html')
    return list(dict.fromkeys(urls))


def extract_workflow_step(line: str) -> str | None:
    """从 workflow_runner 输出中提取可读步骤名。"""
    text = (line or '').strip()
    if not text:
        return None

    step_match = re.search(r'\[(步骤\d+)\]\s*(.+)', text)
    if step_match:
        return f"{step_match.group(1)} {step_match.group(2).strip()}"

    if text.startswith('处理商品 '):
        return text

    if '全部步骤成功' in text:
        return '当前商品全部步骤成功'

    return None


def execute_workflow_runner(tm, task_name: str, task: dict, checkpoint: dict) -> dict:
    """执行 Step1-8 工作流。"""
    urls = infer_1688_urls(task, checkpoint)
    if not urls:
        return {'success': False, 'error': '无法从任务断点或描述中确定1688商品链接'}

    url = urls[0]

    publish = not checkpoint.get('no_publish', False)
    lightweight = checkpoint.get('lightweight', False)
    product_id = checkpoint.get('product_id') or checkpoint.get('alibaba_product_id')
    is_batch = len(urls) > 1
    site_context = tm.get_task_site_context(task)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始执行 workflow-runner...")
    if is_batch:
        print(f"目标URL数: {len(urls)}")
        for index, item in enumerate(urls, start=1):
            print(f"  [{index}] {item}")
    else:
        print(f"目标URL: {url}")

    update_checkpoint(tm, task_name, {
        'current_step': '执行 Step1-8 完整工作流',
        'completed_steps': checkpoint.get('completed_steps', []) + ['开始执行'],
        'next_action': '运行 workflow_runner.py',
        'product_id': product_id,
        'url': url,
        'products': urls,
        'product_count': len(urls),
        'full_workflow': True,
        'site_context': site_context,
        'notes': f"开始 @ {datetime.now().strftime('%H:%M:%S')}"
    })
    tm.persist_task_site_context(task_name, task.get('current_stage') or TaskStage.BUILD.value, site_context, result='workflow_runner 站点上下文已下发')

    cmd = ['python3', str(WORKFLOW_RUNNER)]
    temp_url_file = None
    if is_batch:
        temp_url_file = tempfile.NamedTemporaryFile('w', encoding='utf-8', delete=False, suffix='.txt')
        try:
            temp_url_file.write('\n'.join(urls) + '\n')
            temp_url_file.flush()
        finally:
            temp_url_file.close()
        cmd.extend(['--url-file', temp_url_file.name])
    else:
        cmd.extend(['--url', url])

    if lightweight:
        cmd.append('--lightweight')
    if not publish:
        cmd.append('--no-publish')
    cmd.extend(build_workflow_runner_context_args(site_context))

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=WORKSPACE,
        )
        output_lines = []
        heartbeat_interval = 45.0
        last_heartbeat = time.monotonic()
        current_step = 'Step1-8 工作流执行中'
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end='')
            stripped = line.rstrip()
            output_lines.append(stripped)

            parsed_step = extract_workflow_step(stripped)
            if parsed_step:
                current_step = parsed_step

            now_monotonic = time.monotonic()
            should_heartbeat = bool(parsed_step) or (now_monotonic - last_heartbeat) >= heartbeat_interval
            if should_heartbeat:
                update_checkpoint(tm, task_name, {
                    'current_step': current_step,
                    'completed_steps': checkpoint.get('completed_steps', []) + ['开始执行'],
                    'next_action': '等待 workflow_runner.py 完成',
                    'product_id': product_id,
                    'url': url,
                    'products': urls,
                    'product_count': len(urls),
                    'full_workflow': True,
                    'output_data': {
                        'log_tail': output_lines[-10:],
                    },
                    'notes': f"心跳 @ {datetime.now().strftime('%H:%M:%S')}"
                })
                last_heartbeat = now_monotonic

        proc.wait()
        if proc.returncode == 0:
            update_checkpoint(tm, task_name, {
                'current_step': 'Step1-8 工作流执行完成',
                'completed_steps': checkpoint.get('completed_steps', []) + ['执行 Step1-8 完整工作流'],
                'output_data': {
                    'product_id': product_id,
                    'url': url,
                    'products': urls,
                    'product_count': len(urls),
                    'log_tail': output_lines[-20:],
                },
                'next_action': '任务完成',
                'url': url,
                'products': urls,
                'full_workflow': True,
            })
            return {
                'success': True,
                'output': f"完成商品工作流: {len(urls)} 个商品",
            }

        error_tail = '\n'.join(output_lines[-20:]).strip()
        return {
            'success': False,
            'error': error_tail or f'workflow_runner.py 退出码: {proc.returncode}',
        }
    except Exception as exc:
        print(f"执行异常: {exc}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(exc)}
    finally:
        if temp_url_file and temp_url_file.name:
            try:
                os.unlink(temp_url_file.name)
            except OSError:
                pass


def execute_updater(tm, task_name: str, checkpoint: dict) -> dict:
    """执行 miaoshou-updater"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始执行 miaoshou-updater...")
    
    # 更新断点
    update_checkpoint(tm, task_name, {
        'current_step': '执行 miaoshou-updater',
        'completed_steps': checkpoint.get('completed_steps', []) + ['开始执行'],
        'next_action': '运行 updater.py',
        'notes': f"开始 @ {datetime.now().strftime('%H:%M:%S')}"
    })
    
    try:
        # 动态导入并执行
        sys.path.insert(0, '/home/ubuntu/.openclaw/skills/miaoshou-updater')
        from updater import MiaoshouUpdater
        
        updater = MiaoshouUpdater(headless=True)
        updater.launch()
        
        try:
            # 获取待更新商品
            products = updater.get_optimized_products(limit=1)
            
            if not products:
                print("没有待更新的商品")
                return {'success': False, 'error': '没有待更新的商品'}
            
            print(f"获取到 {len(products)} 个待更新商品")
            
            # 执行更新
            product = products[0]
            success = updater.update_product(product)
            
            print(f"更新结果: {'成功' if success else '失败'}")
            
            # 更新状态
            if success:
                update_checkpoint(tm, task_name, {
                    'current_step': 'miaoshou-updater 执行完成',
                    'completed_steps': checkpoint.get('completed_steps', []) + ['执行 miaoshou-updater'],
                    'output_data': {'product_id': product.get('product_id')},
                    'next_action': '任务完成'
                })
            
            return {'success': success, 'output': f"更新商品: {product.get('product_id')}"}
            
        finally:
            updater.close()
            
    except Exception as e:
        print(f"执行异常: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def execute_listing(tm, task_name: str, checkpoint: dict) -> dict:
    """执行 listing-optimizer"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始执行 listing-optimizer...")
    
    # 更新断点
    update_checkpoint(tm, task_name, {
        'current_step': '执行 listing-optimizer',
        'completed_steps': checkpoint.get('completed_steps', []) + ['开始执行'],
        'next_action': '运行 optimizer.py',
        'notes': f"开始 @ {datetime.now().strftime('%H:%M:%S')}"
    })
    
    try:
        sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')
        from optimizer import ListingOptimizer
        
        optimizer = ListingOptimizer()
        results = optimizer.run(limit=1)
        
        success = len(results) > 0 and results[0].get('success')
        print(f"优化结果: {'成功' if success else '失败'}")
        
        if success:
            update_checkpoint(tm, task_name, {
                'current_step': 'listing-optimizer 执行完成',
                'completed_steps': checkpoint.get('completed_steps', []) + ['执行 listing-optimizer'],
                'output_data': {'results': len(results)},
                'next_action': '任务完成'
            })
        
        return {'success': success, 'output': f"优化 {len(results)} 个商品"}
        
    except Exception as e:
        print(f"执行异常: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def execute_profit_sync(tm, task_name: str, checkpoint: dict) -> dict:
    """执行利润分析同步脚本。"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始执行利润同步...")

    alibaba_ids = checkpoint.get('alibaba_ids') or checkpoint.get('output_data', {}).get('alibaba_ids') or []
    profit_rate = checkpoint.get('profit_rate') or checkpoint.get('output_data', {}).get('profit_rate') or 0.20
    site_context = tm.get_task_site_context(task_name)
    if not alibaba_ids:
        return {'success': False, 'error': '缺少待同步的 alibaba_ids'}

    update_checkpoint(tm, task_name, {
        'current_step': '执行利润分析同步',
        'completed_steps': checkpoint.get('completed_steps', []) + ['开始执行'],
        'next_action': '运行 run_profit_analysis_sync.py',
        'alibaba_ids': alibaba_ids,
        'product_count': len(alibaba_ids),
        'profit_rate': profit_rate,
        'site_context': site_context,
        'site_code': site_context.get('site_code'),
        'notes': f"开始 @ {datetime.now().strftime('%H:%M:%S')}"
    })

    cmd = [
        'python3',
        str(PROFIT_SYNC_RUNNER),
        '--ids',
        ','.join(str(item) for item in alibaba_ids),
        '--profit-rate',
        str(profit_rate),
    ]
    cmd.extend(build_profit_context_args(site_context))

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=WORKSPACE,
        )
        output_lines = []
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end='')
            output_lines.append(line.rstrip())
            update_checkpoint(tm, task_name, {
                'current_step': '利润分析同步执行中',
                'completed_steps': checkpoint.get('completed_steps', []) + ['开始执行'],
                'next_action': '等待利润同步完成',
                'alibaba_ids': alibaba_ids,
                'product_count': len(alibaba_ids),
                'profit_rate': profit_rate,
                'output_data': {
                    'log_tail': output_lines[-10:],
                    'alibaba_ids': alibaba_ids,
                    'product_count': len(alibaba_ids),
                    'profit_rate': profit_rate,
                    'site_context': site_context,
                    'site_code': site_context.get('site_code'),
                },
            })
        proc.wait()

        if proc.returncode == 0:
            update_checkpoint(tm, task_name, {
                'current_step': '利润分析同步完成',
                'completed_steps': checkpoint.get('completed_steps', []) + ['执行利润分析同步'],
                'next_action': '任务完成',
                'alibaba_ids': alibaba_ids,
                'product_count': len(alibaba_ids),
                'profit_rate': profit_rate,
                'output_data': {
                    'log_tail': output_lines[-20:],
                    'alibaba_ids': alibaba_ids,
                    'product_count': len(alibaba_ids),
                    'profit_rate': profit_rate,
                    'site_context': site_context,
                    'site_code': site_context.get('site_code'),
                },
            })
            return {'success': True, 'output': f'利润同步完成: {len(alibaba_ids)} 个商品'}

        return {'success': False, 'error': '\n'.join(output_lines[-20:]).strip() or f'利润同步退出码: {proc.returncode}'}
    except Exception as e:
        print(f"执行异常: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def execute_profit_init(tm, task_name: str, checkpoint: dict) -> dict:
    """执行本地利润明细初始化脚本。"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始执行利润明细初始化...")

    site_context = tm.get_task_site_context(task_name)
    scope = checkpoint.get('scope') or checkpoint.get('output_data', {}).get('scope') or 'missing_only'
    site = checkpoint.get('site') or checkpoint.get('output_data', {}).get('site') or to_legacy_site_label(site_context.get('site_code'))
    batch_size = checkpoint.get('batch_size') or checkpoint.get('output_data', {}).get('batch_size') or 20
    profit_rate = checkpoint.get('profit_rate') or checkpoint.get('output_data', {}).get('profit_rate') or 0.20
    force_recalculate = bool(checkpoint.get('force_recalculate') or checkpoint.get('output_data', {}).get('force_recalculate'))

    update_checkpoint(tm, task_name, {
        'current_step': '执行利润明细初始化',
        'completed_steps': checkpoint.get('completed_steps', []) + ['开始执行'],
        'next_action': '运行 run_profit_analysis_init.py',
        'scope': scope,
        'site': site,
        'site_context': site_context,
        'site_code': site_context.get('site_code'),
        'batch_size': batch_size,
        'force_recalculate': force_recalculate,
        'profit_rate': profit_rate,
        'candidate_count': checkpoint.get('candidate_count', 0),
        'notes': f"开始 @ {datetime.now().strftime('%H:%M:%S')}"
    })

    cmd = [
        'python3',
        str(PROFIT_INIT_RUNNER),
        '--scope',
        str(scope),
        '--site',
        str(site),
        '--profit-rate',
        str(profit_rate),
        '--batch-size',
        str(batch_size),
    ]
    cmd.extend(build_profit_context_args(site_context))
    if force_recalculate:
        cmd.append('--force-recalculate')

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=WORKSPACE,
        )
        output_lines = []
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end='')
            output_lines.append(line.rstrip())
            update_checkpoint(tm, task_name, {
                'current_step': '利润明细初始化执行中',
                'completed_steps': checkpoint.get('completed_steps', []) + ['开始执行'],
                'next_action': '等待初始化完成',
                'scope': scope,
                'site': site,
                'site_context': site_context,
                'site_code': site_context.get('site_code'),
                'batch_size': batch_size,
                'force_recalculate': force_recalculate,
                'profit_rate': profit_rate,
                'candidate_count': checkpoint.get('candidate_count', 0),
                'output_data': {
                    'log_tail': output_lines[-10:],
                    'scope': scope,
                    'site': site,
                    'site_context': site_context,
                    'site_code': site_context.get('site_code'),
                    'batch_size': batch_size,
                    'force_recalculate': force_recalculate,
                    'profit_rate': profit_rate,
                },
            })
        proc.wait()

        if proc.returncode == 0:
            update_checkpoint(tm, task_name, {
                'current_step': '利润明细初始化完成',
                'completed_steps': checkpoint.get('completed_steps', []) + ['执行利润明细初始化'],
                'next_action': '任务完成',
                'scope': scope,
                'site': site,
                'site_context': site_context,
                'site_code': site_context.get('site_code'),
                'batch_size': batch_size,
                'force_recalculate': force_recalculate,
                'profit_rate': profit_rate,
                'candidate_count': checkpoint.get('candidate_count', 0),
                'output_data': {
                    'log_tail': output_lines[-20:],
                    'scope': scope,
                    'site': site,
                    'site_context': site_context,
                    'site_code': site_context.get('site_code'),
                    'batch_size': batch_size,
                    'force_recalculate': force_recalculate,
                    'profit_rate': profit_rate,
                },
            })
            return {'success': True, 'output': '利润明细初始化完成'}

        return {'success': False, 'error': '\n'.join(output_lines[-20:]).strip() or f'利润初始化退出码: {proc.returncode}'}
    except Exception as e:
        print(f"执行异常: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def main():
    if len(sys.argv) < 2:
        print("用法: python3 temp_task_executor.py <task_name>")
        sys.exit(1)
    
    task_name = sys.argv[1]
    log = get_logger('temp_task_executor')
    log.set_task(task_name)
    
    tm = TaskManager()
    
    # 加载任务
    task = tm.get_task(task_name)
    if not task:
        print(f"❌ 任务不存在: {task_name}")
        log.set_message("任务不存在").finish("failed")
        tm.close()
        sys.exit(1)
    
    checkpoint = tm.get_checkpoint(task_name) or {}
    
    print("=" * 60)
    print(f"🎯 TEMP任务: {task_name}")
    print(f"描述: {task.get('description', '无')}")
    print(f"断点: {checkpoint.get('current_step', '新任务')}")
    print("=" * 60)
    
    # 标记开始。若由 cron 拉起，任务通常已处于 processing；手动调用时再补 mark_start。
    if tm._normalize_exec_state(task.get('exec_state')) != 'processing':
        tm.mark_start(task_name)
    tm.mark_executing(task_name)
    log.set_message("TEMP任务开始执行").finish("running")
    
    # 获取执行脚本
    script = get_task_script(task_name, task=task, checkpoint=checkpoint)

    task = promote_legacy_temp_stage_for_execution(tm, task_name, task, script)
    
    if not script:
        error_msg = "未找到执行脚本"
        print(f"❌ {error_msg}")

        notification_message = f"""⚠️ **TEMP任务执行失败**

任务: {task_name}
错误: {error_msg}
    时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        notification_sent = send_feishu(notification_message)
        tm.record_notification(
            task_name=task_name,
            event='temp_task_dispatch_failed',
            message=notification_message,
            success=notification_sent,
            error=None if notification_sent else '飞书派发失败通知发送失败',
            metadata={'dispatch_error': error_msg},
        )
        
        tm.fail_stage(task_name, task.get('current_stage') or TaskStage.PLAN.value, error_msg, error_type='manual_required')
        log.set_message(error_msg).finish("failed")
        tm.close()
        sys.exit(1)
    
    print(f"📦 执行: {script}")
    
    # 根据任务类型执行
    if script == '__stage_replay__':
        result = execute_lifecycle_replay(tm, task_name, task, checkpoint)
    elif script == str(WORKFLOW_RUNNER):
        result = execute_workflow_runner(tm, task_name, task, checkpoint)
    elif script == str(PROFIT_SYNC_RUNNER):
        result = execute_profit_sync(tm, task_name, checkpoint)
    elif script == str(PROFIT_INIT_RUNNER):
        result = execute_profit_init(tm, task_name, checkpoint)
    elif task_name.startswith('TEMP-UPDATER'):
        result = execute_updater(tm, task_name, checkpoint)
    elif task_name.startswith('TEMP-LISTING'):
        result = execute_listing(tm, task_name, checkpoint)
    else:
        result = {'success': False, 'error': '未知的任务类型'}
    
    # 更新状态
    if result['success']:
        exec_payload = build_temp_exec_result(task, result, tm.get_checkpoint(task_name) or checkpoint)
        sync_result = tm.sync_stage_from_exec_outcome(task_name, exec_payload)
        lifecycle_result = advance_lifecycle_after_build(tm, task_name, {'skill': 'temp-agent', 'action': 'temp_execute'})
        refreshed = tm.get_task(task_name) or {}
        if refreshed.get('exec_state') != 'end' and refreshed.get('current_stage') == TaskStage.RETROSPECTIVE.value:
            tm.mark_end(task_name, 'TEMP任务执行成功')
        ensure_terminal_state(tm, task_name, exec_state=str((tm.get_task(task_name) or {}).get('exec_state') or 'end'), status=str((tm.get_task(task_name) or {}).get('status') or 'completed'), result='TEMP任务执行成功')
        log.set_message(f"TEMP任务完成: {lifecycle_result.get('action', sync_result.get('action'))}").finish("success")
        print("✅ TEMP任务执行成功")

        notification_message = f"""🎉 **TEMP任务完成**

任务: {task_name}
描述: {task.get('description', '')}
结果: {result.get('output', '执行成功')}
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        notification_sent = send_feishu(notification_message)
        tm.record_notification(
            task_name=task_name,
            event='temp_task_completed',
            message=notification_message,
            success=notification_sent,
            error=None if notification_sent else '飞书完成通知发送失败',
            metadata={'result': result.get('output', '执行成功')},
        )
        tm.close()
        sys.exit(0)
    else:
        error = result.get('error', '未知错误')
        tm.fail_stage(task_name, task.get('current_stage') or TaskStage.BUILD.value, error, error_type=result.get('error_type', 'stage_failed'))
        ensure_terminal_state(tm, task_name, exec_state='error_fix_pending', status='failed', error=error)
        log.set_message(f"失败: {error}").finish("failed")
        print(f"❌ TEMP任务失败: {error}")

        notification_message = f"""⚠️ **TEMP任务执行异常**

任务: {task_name}
描述: {task.get('description', '')}
错误: {error}
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        notification_sent = send_feishu(notification_message)
        tm.record_notification(
            task_name=task_name,
            event='temp_task_failed',
            message=notification_message,
            success=notification_sent,
            error=None if notification_sent else '飞书失败通知发送失败',
            metadata={'task_error': error},
        )

        tm.close()
        sys.exit(1)


if __name__ == '__main__':
    main()
