#!/usr/bin/env python3
"""任务执行器 - 根据任务状态和实际执行结果自动执行"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')
from task_manager import TaskManager, ExecState
from pathlib import Path
import subprocess
import re

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
TASK_LOG = WORKSPACE / 'logs' / 'task_exec.log'

# 修复任务映射
FIX_SCRIPTS = {
    'product-storer接口修复': f'{WORKSPACE}/scripts/fix_product_storer.py',
    'listing-optimizer接口修复': f'{WORKSPACE}/scripts/fix_listing_optimizer.py',
    '数据类型错误修复': f'{WORKSPACE}/scripts/fix_data_type.py',
    '模块导入路径修复': f'{WORKSPACE}/scripts/fix_import.py',
}

# 普通任务映射
TASK_SCRIPTS = {
    'CIRCUIT-BREAKER': {'script': f'{WORKSPACE}/scripts/circuit_breaker.sh'},
    'CONFIG-ENV': {'script': f'{WORKSPACE}/scripts/create_config_env.sh'},
    'COOKIES-ALERT': {'script': f'{WORKSPACE}/scripts/cookies_alert.sh'},
    'PRODUCT-ANALYSIS': {'script': f'{WORKSPACE}/scripts/analyze_products.py'},
    'IMPROVEMENTS-MD': {'script': f'{WORKSPACE}/scripts/update_improvements.sh'},
    'TC-FLOW-001': {
        'script': f'{WORKSPACE}/skills/workflow-runner/scripts/workflow_runner.py',
        'args': ['--url', 'https://detail.1688.com/offer/1031400982378.html']
    },
}

def parse_workflow_result(output: str) -> dict:
    """解析工作流输出，判断各步骤是否成功"""
    result = {
        'success': False,
        'failed_steps': [],
        'error_type': None,
        'error_message': None
    }
    
    # 检查工作流是否成功完成
    if '工作流结果汇总:' in output:
        # 提取汇总信息
        lines = output.split('\n')
        for i, line in enumerate(lines):
            if '工作流结果汇总:' in line:
                # 解析后续的汇总行
                for j in range(i+1, min(i+10, len(lines))):
                    summary_line = lines[j]
                    if ': ❌' in summary_line:
                        step_name = summary_line.split(':')[0].strip()
                        result['failed_steps'].append(step_name)
                break
    
    # 判断错误类型
    if 'ModuleNotFoundError' in output or 'No module named' in output:
        result['error_type'] = 'error_fix_pending'
        result['error_message'] = '模块导入失败'
    elif 'EPIPE' in output or 'Browser' in output.lower():
        result['error_type'] = 'normal_crash'
        result['error_message'] = '浏览器崩溃'
    elif 'string indices must be integers' in output:
        result['error_type'] = 'error_fix_pending'
        result['error_message'] = '数据类型错误(string indices)'
    elif "'str' object has no attribute" in output:
        result['error_type'] = 'error_fix_pending'
        result['error_message'] = "数据类型错误(str object)"
    elif result['failed_steps']:
        if len(result['failed_steps']) <= 2:
            result['error_type'] = 'error_fix_pending'
            result['error_message'] = f"步骤失败: {', '.join(result['failed_steps'])}"
        else:
            result['error_type'] = 'error_fix_pending'
            result['error_message'] = '多个步骤失败'
    else:
        result['success'] = True
    
    return result

def execute_task(task_name: str, script: str, args: list, task_log: Path) -> tuple:
    """执行任务，返回(成功bool, 输出str)"""
    try:
        cmd = []
        if script.endswith('.py'):
            cmd = ['python3', script] + args
        else:
            cmd = ['bash', script] + args
        
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
    actionable = tm.get_actionable_tasks()
    
    if not actionable:
        print("无待执行任务")
        tm.close()
        return
    
    for task in actionable:
        task_name = task['task_name']
        exec_state = task['exec_state']
        fix_suggestion = task.get('fix_suggestion', '')
        
        print(f"\n处理任务: {task['display_name']} (状态: {exec_state})")
        
        # 标记开始执行
        tm.mark_start(task_name)
        
        # 确定脚本
        script_info = TASK_SCRIPTS.get(task_name, {})
        if isinstance(script_info, dict):
            script = script_info.get('script')
            args = script_info.get('args', [])
        else:
            script = script_info
            args = []
        
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
        success, output = execute_task(task_name, script, args, TASK_LOG)
        
        # 追加日志
        with open(TASK_LOG, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"任务: {task['display_name']}\n")
            f.write(f"执行脚本: {script}\n")
            f.write(f"退出码: {0 if success else 1}\n")
            f.write(f"{'='*60}\n")
            f.write(output[-3000:])
        
        # 解析工作流结果
        if task_name == 'TC-FLOW-001':
            wf_result = parse_workflow_result(output)
            
            if wf_result['success']:
                tm.mark_end(task_name, f"成功")
                print(f"  ✅ 工作流全部成功")
            else:
                error_type = wf_result['error_type']
                error_msg = wf_result['error_message']
                
                if error_type == 'error_fix_pending':
                    tm.mark_error_fix_pending(task_name, error_msg, fix_suggestion or error_msg)
                elif error_type == 'normal_crash':
                    tm.mark_normal_crash(task_name, error_msg)
                else:
                    tm.mark_requires_manual(task_name, error_msg)
                
                print(f"  ❌ 工作流失败: {error_msg}")
                print(f"     状态标记为: {error_type}")
        else:
            # 其他任务简单处理
            if success:
                tm.mark_end(task_name, "成功")
                print(f"  ✅ 成功")
            else:
                tm.mark_normal_crash(task_name, output[-200:])
                print(f"  ⚠️ 失败但可重试")
    
    tm.close()

if __name__ == '__main__':
    run()
