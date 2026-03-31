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
from datetime import datetime
from pathlib import Path

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
sys.path.insert(0, str(WORKSPACE / 'scripts'))

from task_manager import TaskManager
from logger import get_logger
from notification_service import send_feishu_text


def send_feishu(message: str):
    """发送飞书通知"""
    return send_feishu_text(message)


def update_checkpoint(tm, task_name: str, checkpoint: dict):
    """更新断点"""
    tm.update_checkpoint(task_name, checkpoint)


# 任务名称到执行脚本的映射
TASK_SCRIPT_MAP = {
    'TEMP-UPDATER': '/home/ubuntu/.openclaw/skills/miaoshou-updater/updater.py',
    'TEMP-LISTING': '/home/ubuntu/.openclaw/skills/listing-optimizer/optimizer.py',
}


def get_task_script(task_name: str):
    """根据任务名称获取执行脚本"""
    for prefix, script in TASK_SCRIPT_MAP.items():
        if task_name.startswith(prefix):
            return script
    return None


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
        sys.path.insert(0, '/home/ubuntu/.openclaw/skills/listing-optimizer')
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
    if task.get('exec_state') != 'processing':
        tm.mark_start(task_name)
    tm.mark_executing(task_name)
    log.set_message("TEMP任务开始执行").finish("running")
    
    # 获取执行脚本
    script = get_task_script(task_name)
    
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
        
        tm.update_task(task_name, exec_state='requires_manual', last_error=error_msg)
        log.set_message(error_msg).finish("failed")
        tm.close()
        sys.exit(1)
    
    print(f"📦 执行: {script}")
    
    # 根据任务类型执行
    if task_name.startswith('TEMP-UPDATER'):
        result = execute_updater(tm, task_name, checkpoint)
    elif task_name.startswith('TEMP-LISTING'):
        result = execute_listing(tm, task_name, checkpoint)
    else:
        result = {'success': False, 'error': '未知的任务类型'}
    
    # 更新状态
    if result['success']:
        tm.mark_end(task_name, 'TEMP任务执行成功')
        log.set_message("TEMP任务完成").finish("success")
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
    else:
        error = result.get('error', '未知错误')
        tm.update_task(task_name, exec_state='error_fix_pending', last_error=error)
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


if __name__ == '__main__':
    main()
