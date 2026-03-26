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
from pathlib import Path
from datetime import datetime, timedelta

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
SCRIPTS_DIR = WORKSPACE / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

from task_manager import TaskManager
from logger import get_logger

# 任务脚本映射
TASK_SCRIPTS = {
    'TC-FLOW-001': {
        'script': f'{WORKSPACE}/skills/workflow-runner/scripts/workflow_runner.py',
        'args': ['--url', 'https://detail.1688.com/offer/1031400982378.html']
    },
}

STUCK_TIMEOUT_MINUTES = 10  # 10分钟无日志判定为卡死


def get_task_last_log_time(task_name: str) -> datetime:
    """获取任务最后一次真正的工作日志时间（排除following状态）"""
    import psycopg2
    conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
    cur = conn.cursor()
    sql = "SELECT MAX(created_at) FROM main_logs WHERE task_name = %s AND run_status = 'running' AND run_message NOT LIKE '%%等待下一次检查%%'"
    cur.execute(sql, (task_name,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row and row[0] else None


def is_task_stuck(task_name: str) -> bool:
    """判断任务是否卡死（10分钟无日志）"""
    last_time = get_task_last_log_time(task_name)
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
        WHERE exec_state = 'processing'
    """)
    processing_tasks = cur.fetchall()
    cur.close()
    
    if processing_tasks:
        print(f"\n📋 发现 {len(processing_tasks)} 个执行中任务")
        for row in processing_tasks:
            task_name = row[0]
            display_name = row[1]
            
            if is_task_stuck(task_name):
                print(f"\n⏰ {task_name} 已卡死超过{STUCK_TIMEOUT_MINUTES}分钟")
                kill_process(task_name)
                
                # 重置状态
                tm.update_task(task_name,
                    status='failed',
                    exec_state='error_fix_pending',
                    last_error=f'任务执行超时（>{STUCK_TIMEOUT_MINUTES}分钟无响应）'
                )
                log.set_message(f"{display_name} 卡死，已重置").finish("failed")
            else:
                # 任务正常运行，插入日志
                print(f"\n✅ {task_name} 运行正常，等待下次检查")
                log.set_task(task_name).set_message(f"任务正常运行中，等待下一次检查").finish("following")
    
    # 获取可执行任务
    actionable = tm.get_actionable_tasks(limit=1)
    
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
        
        print(f"\n{'='*60}")
        print(f"处理任务: {display_name} (level={task_level}, state={exec_state})")
        
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
            script_info = {
                'script': f'{WORKSPACE}/scripts/subtask_executor.py',
                'args': [task_name]
            }
        
        if not script_info:
            print(f"  ⚠️ 没有配置执行脚本，跳过")
            continue
        
        # 标记开始
        tm.mark_start(task_name)
        log.finish("running")
        
        # 使用Popen执行
        success, output = run_with_popen(task_name, script_info, on_line_callback=log.log_line)
        
        if success:
            tm.mark_end(task_name, "执行成功")
            print(f"  ✅ 执行成功")
            log.set_message(f"{display_name} 成功").finish("success")
            # 更新长久记忆
            tm.on_task_success(task_name)
        else:
            print(f"  ❌ 执行失败")
            
            if task_level == 2:
                from prod_task_cron import handle_subtask_failure
                result = handle_subtask_failure(tm, task, output[-500:])
                log.set_message(f"{display_name} 失败: {result}").finish("failed")
            else:
                # 父任务失败处理
                # 获取重试次数
                task_info = tm.get_task(task_name)
                retry_count = task_info.get('retry_count', 0) if task_info else 0
                
                if retry_count >= 3:
                    # 重试3次以上，先进行根因分析
                    print(f"  ⚠️ 父任务重试{retry_count}次，先进行根因分析...")
                    
                    # 调用根因分析器
                    import subprocess
                    result = subprocess.run(
                        ['python3', f'{WORKSPACE}/scripts/root_cause_analyzer.py', task_name],
                        capture_output=True, text=True, cwd=str(WORKSPACE)
                    )
                    
                    if result.returncode == 0:
                        print(f"  📊 根因分析完成，请查看日志")
                    else:
                        print(f"  ⚠️ 根因分析执行异常: {result.stderr[:200]}")
                
                # 解析失败步骤，创建多个子任务
                # 父任务失败：解析失败步骤，创建多个子任务
                failed_steps = []
                for line in output.split('\n'):
                    if '❌' in line and ':' in line:
                        step_name = line.split(':')[0].strip().replace('❌', '').strip()
                        if step_name:
                            failed_steps.append({
                                'error': f"{step_name} 失败",
                                'fix': f"检查 {step_name} 步骤执行失败原因",
                                'success_criteria': f"{step_name} 执行成功"
                            })
                
                if failed_steps:
                    # 创建多个修复子任务
                    tm.create_fix_subtasks(task_name, failed_steps)
                    log.set_message(f"{display_name} 失败，{len(failed_steps)}个步骤有问题，已创建子任务").finish("failed")
                else:
                    # 无法解析失败步骤
                    tm.update_task(task_name,
                        status='failed',
                        exec_state='error_fix_pending',
                        last_error=output[-200:]
                    )
                    log.set_message(f"{display_name} 失败: {output[-100:]}").finish("failed")
    
    tm.close()
    print(f"\n{'='*60}")
    print("📋 prod_task_cron 执行完成")


if __name__ == '__main__':
    run()
