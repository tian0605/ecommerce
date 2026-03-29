#!/usr/bin/env python3
"""
fix_task_cron - 修复任务执行定时器
每1分钟执行一次，优先处理修复类任务

功能：
1. 每分钟检查是否有待执行的修复任务
2. 修复类任务（task_type='修复'）优先于常规任务
3. 使用 subtask_executor.py 执行修复任务
"""
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
SCRIPTS_DIR = WORKSPACE / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

from task_manager import TaskManager
from logger import get_logger

FIX_SCRIPT = f'{SCRIPTS_DIR}/subtask_executor.py'
STUCK_TIMEOUT_MINUTES = 5  # 5分钟无日志判定为卡死


def get_task_last_log_time(task_name: str):
    """获取任务最后一次日志时间"""
    import psycopg2
    conn = psycopg2.connect(host='localhost', database='ecommerce_data', user='superuser', password='Admin123!')
    cur = conn.cursor()
    cur.execute(
        "SELECT MAX(created_at) FROM main_logs WHERE task_name = %s AND run_status = 'running'",
        (task_name,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row and row[0] else None


def is_task_stuck(task_name: str) -> bool:
    """判断任务是否卡死"""
    last_time = get_task_last_log_time(task_name)
    if not last_time:
        return False
    return (datetime.now() - last_time).total_seconds() > STUCK_TIMEOUT_MINUTES * 60


def kill_task_process(task_name: str):
    """杀掉任务相关的进程"""
    try:
        subprocess.run(['pkill', '-f', f'subtask_executor.py {task_name}'], capture_output=True)
        print(f"已杀掉进程: {task_name}")
    except:
        pass


def run_fix_task(task_name: str) -> tuple:
    """执行单个修复任务"""
    print(f"[FIX-CRON] 执行修复任务: {task_name}")
    
    # 启动子进程
    cmd = ['python3', FIX_SCRIPT, task_name]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(WORKSPACE)
    )
    
    # 实时输出
    output_lines = []
    for line in proc.stdout:
        print(line, end='')  # 实时打印
        output_lines.append(line.strip())
    
    proc.wait()
    success = proc.returncode == 0
    output = '\n'.join(output_lines)
    
    return success, output


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] fix_task_cron 启动")
    
    tm = TaskManager()
    log = get_logger('fix_cron')
    
    # 检查是否有卡死的FIX任务
    cur_tasks = tm.get_actionable_tasks(limit=5)
    
    # 只处理修复类任务
    fix_tasks = [t for t in cur_tasks if t.get('task_type') == '修复']
    
    # 如果没有修复类任务，直接退出
    if not fix_tasks:
        print("[FIX-CRON] 无待执行任务")
        tm.close()
        return
    
    # 先处理修复任务
    if fix_tasks:
        print(f"[FIX-CRON] 发现 {len(fix_tasks)} 个修复任务")
        task = fix_tasks[0]  # 只处理一个
        
        task_name = task['task_name']
        display_name = task.get('display_name', task_name)
        
        # 检查是否卡死
        if is_task_stuck(task_name):
            print(f"[FIX-CRON] 任务卡死: {task_name}")
            kill_task_process(task_name)
            tm.reset_task(task_name, exec_state='new')
        
        # 标记开始
        tm.mark_start(task_name)
        log.set_task(task_name).set_message(f"fix_cron执行").finish("running")
        
        # 执行
        success, output = run_fix_task(task_name)
        
        # 更新状态
        if success:
            tm.mark_end(task_name, "fix_cron执行成功")
            log.set_message(f"fix_cron成功").finish("success")
            print(f"[FIX-CRON] ✅ {task_name} 执行成功")
        else:
            tm.mark_error_fix_pending(task_name, "执行失败")
            log.set_message(f"fix_cron失败").finish("failed")
            print(f"[FIX-CRON] ❌ {task_name} 执行失败")
    
    tm.close()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] fix_task_cron 完成")


if __name__ == '__main__':
    main()
