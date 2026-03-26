#!/usr/bin/env python3
"""任务执行器 - 根据任务状态自动执行"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')
from task_manager import TaskManager, ExecState
from pathlib import Path
import subprocess

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
TASK_LOG = WORKSPACE / 'logs' / 'task_exec.log'

# 修复任务映射
FIX_SCRIPTS = {
    'product-storer接口修复': f'{WORKSPACE}/scripts/fix_product_storer.py',
    'listing-optimizer接口修复': f'{WORKSPACE}/scripts/fix_listing_optimizer.py',
    '数据类型错误修复': f'{WORKSPACE}/scripts/fix_data_type.py',
    '模块导入路径修复': f'{WORKSPACE}/scripts/fix_import.py',
    '浏览器稳定性修复': f'{WORKSPACE}/scripts/fix_browser.py',
}

# 普通任务映射
TASK_SCRIPTS = {
    'CIRCUIT-BREAKER': f'{WORKSPACE}/scripts/circuit_breaker.sh',
    'CONFIG-ENV': f'{WORKSPACE}/scripts/create_config_env.sh',
    'COOKIES-ALERT': f'{WORKSPACE}/scripts/cookies_alert.sh',
    'PRODUCT-ANALYSIS': f'{WORKSPACE}/scripts/analyze_products.py',
    'IMPROVEMENTS-MD': f'{WORKSPACE}/scripts/update_improvements.sh',
    'TC-FLOW-001': {
        'script': f'{WORKSPACE}/skills/workflow-runner/scripts/workflow_runner.py',
        'args': ['--url', 'https://detail.1688.com/offer/1031400982378.html']
    },
}

def execute_task(task_name: str, script_path: str, task_log: Path, args: list = None) -> tuple:
    """执行任务，返回(成功bool, 输出str)"""
    if args is None:
        args = []
    
    try:
        if script_path.endswith('.py'):
            cmd = ['python3', script_path] + args
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=WORKSPACE
            )
        else:
            cmd = ['bash', script_path] + args
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=WORKSPACE
            )
        
        output = result.stdout + result.stderr
        return result.returncode == 0, output
    except Exception as e:
        return False, str(e)

def run():
    tm = TaskManager()
    
    # 获取需要处理的任务
    actionable = tm.get_actionable_tasks()
    
    if not actionable:
        print("无待执行任务")
        return
    
    results = []
    
    for task in actionable:
        task_name = task['task_name']
        exec_state = task['exec_state']
        
        print(f"\n处理任务: {task['display_name']} (状态: {exec_state})")
        
        # 标记开始
        tm.mark_start(task_name)
        
        # 确定要执行的脚本和参数
        script = None
        script_args = []
        
        # 如果是error_fix_pending，尝试执行fix脚本
        if exec_state == ExecState.ERROR_FIX_PENDING:
            fix = task.get('fix_suggestion', '')
            script = FIX_SCRIPTS.get(fix)
        
        # 否则执行对应的任务脚本
        if not script:
            task_script = TASK_SCRIPTS.get(task_name)
            if isinstance(task_script, dict):
                script = task_script.get('script')
                script_args = task_script.get('args', [])
            else:
                script = task_script
        
        if not script:
            print(f"  ⚠️ 没有找到对应脚本")
            tm.mark_requires_manual(task_name, "没有找到执行脚本")
            continue
        
        script_path = Path(script)
        if not script_path.exists():
            print(f"  ⚠️ 脚本不存在: {script_path}")
            tm.mark_requires_manual(task_name, f"脚本不存在: {script}")
            continue
        
        # 执行
        print(f"  执行: {script}")
        success, output = execute_task(task_name, script, TASK_LOG, script_args)
        
        # 追加日志
        with open(TASK_LOG, 'a') as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"任务: {task['display_name']}\n")
            f.write(f"执行脚本: {script}\n")
            f.write(f"结果: {'成功' if success else '失败'}\n")
            f.write(output[-2000:])  # 保留最后2000字符
        
        if success:
            tm.mark_end(task_name, "成功")
            print(f"  ✅ 成功")
        else:
            # 根据错误类型判断状态
            if "ModuleNotFound" in output or "ImportError" in output:
                tm.mark_error_fix_pending(task_name, output[-200:], "模块导入修复")
            elif "Permission" in output or "Access" in output:
                tm.mark_requires_manual(task_name, output[-200:])
            else:
                tm.mark_normal_crash(task_name, output[-200:])
            print(f"  ❌ 失败，将根据错误类型安排")
        
        results.append({
            'task': task['display_name'],
            'success': success,
            'exec_state': exec_state
        })
    
    tm.close()
    return results

if __name__ == '__main__':
    run()
