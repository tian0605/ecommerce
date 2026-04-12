#!/usr/bin/env python3
"""
prod_task_cron - 独立任务执行定时器
每30分钟执行一次

功能：
1. Popen实时输出日志
2. 10分钟无日志判断为卡死，杀掉并重置
3. 10分钟内有日志则插入运行日志
"""
import sys
import subprocess
import os
import copy
from pathlib import Path
from datetime import datetime, timedelta

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
SCRIPTS_DIR = WORKSPACE / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

from task_manager import TaskManager, TaskStage
from logger import get_logger

# 任务脚本映射
TASK_SCRIPTS = {
    'TC-FLOW-001': {
        'script': f'{WORKSPACE}/skills/workflow-runner/scripts/workflow_runner.py',
        'args': ['--url', 'https://detail.1688.com/offer/1031400982378.html']
    },
}

STUCK_TIMEOUT_MINUTES = 10  # 10分钟无日志判定为卡死


def build_site_context_args(site_context: dict, script: str) -> list[str]:
    if not isinstance(site_context, dict) or not script:
        return []

    args: list[str] = []
    script_name = Path(script).name
    if script_name == 'workflow_runner.py':
        option_map = {
            'market_code': '--market-code',
            'site_code': '--site-code',
            'shop_code': '--shop-code',
            'source_language': '--source-language',
            'listing_language': '--listing-language',
        }
        for key, option in option_map.items():
            value = site_context.get(key)
            if value not in (None, ''):
                args.extend([option, str(value)])
        return args

    if script_name in {'run_profit_analysis_sync.py', 'run_profit_analysis_init.py'}:
        if site_context.get('market_code') not in (None, ''):
            args.extend(['--market-code', str(site_context['market_code'])])
        if site_context.get('site_code') not in (None, ''):
            args.extend(['--site-code', str(site_context['site_code'])])
        return args

    return []


def enrich_script_info(tm: TaskManager, task: dict, script_info: dict | None) -> dict | None:
    if not script_info:
        return script_info

    enriched = copy.deepcopy(script_info)
    script = enriched.get('script')
    if not script:
        return enriched

    existing_args = list(enriched.get('args', []))
    site_context = tm.get_task_site_context(task)
    additional_args = build_site_context_args(site_context, script)
    for index, item in enumerate(additional_args):
        if item.startswith('--') and item in existing_args:
            continue
        if index > 0 and additional_args[index - 1].startswith('--') and additional_args[index - 1] in existing_args:
            continue
        existing_args.append(item)
    enriched['args'] = existing_args
    return enriched


def get_task_last_activity_time(task_name: str) -> datetime:
    """获取任务最后一次活动时间（运行日志或checkpoint心跳）"""
    import psycopg2
    conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            (
                SELECT MAX(created_at)
                FROM main_logs
                WHERE task_name = %s
                  AND run_status = 'running'
                  AND run_message NOT LIKE '%%等待下一次检查%%'
            ) AS last_log_time,
            (
                SELECT last_executed_at
                FROM tasks
                WHERE task_name = %s
            ) AS last_checkpoint_time
        """,
        (task_name, task_name),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None

    last_log_time, last_checkpoint_time = row
    if last_log_time and last_checkpoint_time:
        return max(last_log_time, last_checkpoint_time)
    return last_log_time or last_checkpoint_time


def is_task_stuck(task_name: str) -> bool:
    """判断任务是否卡死（10分钟无活动）"""
    last_time = get_task_last_activity_time(task_name)
    if not last_time:
        return False
    return datetime.now() - last_time > timedelta(minutes=STUCK_TIMEOUT_MINUTES)


def kill_process(task_name: str) -> bool:
    """杀掉任务相关进程"""
    # 杀掉 workflow_runner 进程
    try:
        subprocess.run(['pkill', '-f', 'workflow_runner'], stderr=subprocess.DEVNULL)
        subprocess.run(['pkill', '-f', 'miaoshou'], stderr=subprocess.DEVNULL)
        subprocess.run(['pkill', '-f', 'chromium'], stderr=subprocess.DEVNULL)
        print(f"  🔪 已杀掉 {task_name} 相关进程")
        return True
    except:
        return False


def run_with_popen(task_name: str, script_info: dict, on_line_callback=None) -> tuple:
    """使用Popen执行任务，实时输出"""
    script = script_info.get('script')
    args = script_info.get('args', [])
    
    cmd = ['python3', script] + args if script.endswith('.py') else ['bash', script] + args
    
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=WORKSPACE
        )
        
        output_lines = []
        for line in proc.stdout:
            print(line, end='')  # 实时打印
            output_lines.append(line)
            if on_line_callback:
                on_line_callback(line.rstrip())
        
        proc.wait()
        success = proc.returncode == 0
        output = ''.join(output_lines)
        return success, output
        
    except Exception as e:
        return False, str(e)


def run():
    """主执行流程"""
    log = get_logger('prod_task_cron')
    log.set_message("prod_task_cron启动")
    
    tm = TaskManager()
    
    # 检查 processing 状态的任务
    cur = tm.conn.cursor()
    cur.execute("""
        SELECT task_name, display_name, exec_state, last_executed_at
        FROM tasks 
        WHERE LOWER(COALESCE(exec_state, '')) = 'processing'
    """)
    processing_tasks = cur.fetchall()
    cur.close()
    tm.conn.commit()
    
    if processing_tasks:
        print(f"\n📋 发现 {len(processing_tasks)} 个执行中任务")
        for row in processing_tasks:
            task_name = row[0]
            display_name = row[1]
            
            if is_task_stuck(task_name):
                print(f"\n⏰ {task_name} 已卡死超过{STUCK_TIMEOUT_MINUTES}分钟")
                kill_process(task_name)
                task_info = tm.get_task(task_name) or {}
                tm.fail_stage(
                    task_name,
                    task_info.get('current_stage') or TaskStage.BUILD.value,
                    f'任务执行超时（>{STUCK_TIMEOUT_MINUTES}分钟无响应）',
                    error_type='timeout_overtime',
                )
                log.set_message(f"{display_name} 卡死，已重置").finish("failed")
            else:
                # 任务正常运行，插入日志
                print(f"\n✅ {task_name} 运行正常，等待下次检查")
                log.set_task(task_name).set_message(f"任务正常运行中，等待下一次检查").finish("following")
    
    # 获取可执行任务
    actionable = tm.claim_runnable_tasks_by_stage(limit=1, task_types=['临时任务', '常规', '创造'])
    
    if not actionable:
        print("📋 无待执行任务")
        # 只有在没有processing任务时才插入skipped
        if not processing_tasks:
            log.set_message("无待执行任务").finish("skipped")
        tm.close()
        return
    
    print(f"📋 发现 {len(actionable)} 个待执行任务")
    
    for task in actionable:
        task_name = task['task_name']
        display_name = task['display_name']
        exec_state = task['exec_state']
        task_level = task.get('task_level', 1)
        current_stage = task.get('current_stage')
        
        print(f"\n{'='*60}")
        print(f"处理任务: {display_name} (level={task_level}, state={exec_state}, stage={current_stage})")
        
        # 绑定日志
        log.set_task(task_name)
        
        # 获取脚本
        script_info = TASK_SCRIPTS.get(task_name)
        
        # 特殊处理
        if task_name.startswith('SOL-'):
            script_info = {
                'script': f'{WORKSPACE}/scripts/subtask_executor.py',
                'args': [task_name]
            }
        
        if not script_info and task_level == 2:
            # level=2 子任务使用 workflow_executor（常规工作流执行器）
            script_info = {
                'script': f'{WORKSPACE}/scripts/workflow_executor.py',
                'args': [task_name]
            }
        
        if not script_info and task_level == 1:
            task_type = task.get('task_type', '')
            if current_stage == TaskStage.RETROSPECTIVE.value:
                script_info = {
                    'script': f'{WORKSPACE}/scripts/task_monitor.py',
                    'args': ['--task', task_name]
                }
            elif task_type == '临时任务':
                script_info = {
                    'script': f'{WORKSPACE}/scripts/temp_task_executor.py',
                    'args': [task_name]
                }
            else:
                parent_flow = tm.inspect_parent_task_flow(task_name)
                if parent_flow['action'] == 'blocked':
                    pending_count = parent_flow.get('pending_count', 0)
                    print(f"  [workflow] 父任务等待 {pending_count} 个子任务")
                    log.set_message(f"父任务等待{pending_count}个子任务").finish("following")
                    continue
                if parent_flow['action'] == 'completed':
                    print(f"  ✅ 所有子任务完成，父任务结束")
                    log.set_message("所有子任务完成").finish("success")
                    continue
                if parent_flow['action'] == 'await_manual':
                    print(f"  ⚠️ 子任务已结束，但仍有人工介入项")
                    log.set_message("子任务已结束，等待人工介入收尾").finish("following")
                    continue
                if parent_flow['action'] == 'abnormal':
                    print(f"  ⚠️ 父任务子任务状态异常，跳过")
                    log.set_message("父任务子任务状态异常").finish("following")
                    continue
                else:
                    # 没有子任务，也没有配置脚本
                    print(f"  ⚠️ 没有配置执行脚本，跳过")
                    continue
        
        script_info = enrich_script_info(tm, task, script_info)

        if not script_info:
            print(f"  ⚠️ 没有配置执行脚本，跳过")
            continue
        
        # 标记开始
        tm.mark_executing(task_name)
        log.finish("running")
        
        # 使用Popen执行
        success, output = run_with_popen(task_name, script_info, on_line_callback=log.log_line)
        
        if success:
            refreshed = tm.get_task(task_name) or {}
            if refreshed.get('exec_state') == 'end':
                print(f"  ✅ 执行成功（执行器已完成任务收尾）")
                log.set_message(f"{display_name} 成功").finish("success")
                tm.on_task_success(task_name)
            elif refreshed.get('current_stage') == TaskStage.RETROSPECTIVE.value and refreshed.get('stage_status') == 'done':
                print(f"  ✅ retrospective 已完成")
                log.set_message(f"{display_name} retrospective 完成").finish("success")
            elif task_level == 2 or task.get('task_type') == '临时任务':
                tm.update_task(task_name, exec_state='new', status='pending')
                print(f"  ℹ️ 执行成功，等待后续阶段/下一轮调度")
                log.set_message(f"{display_name} 成功，等待后续阶段").finish("following")
            else:
                tm.mark_end(task_name, "执行成功")
                print(f"  ✅ 执行成功")
                log.set_message(f"{display_name} 成功").finish("success")
                tm.on_task_success(task_name)
        else:
            print(f"  ❌ 执行失败")
            failed_steps = []
            
            # level=2 任务的失败由 workflow_executor 处理（标记 error_fix_pending）
            # fix_task_cron 会自动创建 FIX 子任务
            # 无需在此处理
            if task_level == 2:
                print(f"  [workflow] level=2任务失败，由fix_task_cron处理")
                log.set_message(f"{display_name} 失败，由fix_task_cron处理").finish("failed")
            else:
                failure_result = tm.handle_execution_failure(task_name, output, current_stage=current_stage)
                if failure_result.get('action') == 'fix_subtasks_created':
                    log.set_message(f"{display_name} 失败，已创建{failure_result.get('count', 0)}个修复子任务").finish("failed")
                else:
                    log.set_message(f"{display_name} 失败: {output[-100:]}").finish("failed")
    
    tm.close()
    print(f"\n{'='*60}")
    print("📋 prod_task_cron 执行完成")


if __name__ == '__main__':
    run()
