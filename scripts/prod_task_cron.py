#!/usr/bin/env python3
"""
prod_task_cron - 独立任务执行定时器
每30分钟执行一次，从数据库读取待办任务，按优先级执行
"""
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# 添加脚本目录到路径
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
    'CIRCUIT-BREAKER': {
        'script': f'{WORKSPACE}/scripts/circuit_breaker.sh'
    },
    'CONFIG-ENV': {
        'script': f'{WORKSPACE}/scripts/create_config_env.sh'
    },
    'COOKIES-ALERT': {
        'script': f'{WORKSPACE}/scripts/cookies_alert.sh'
    },
    'PRODUCT-ANALYSIS': {
        'script': f'{WORKSPACE}/scripts/analyze_products.py'
    },
    'IMPROVEMENTS-MD': {
        'script': f'{WORKSPACE}/scripts/update_improvements.sh'
    },
    # 子任务
    'FIX-STEP6-UPDATE': {
        'script': f'{WORKSPACE}/scripts/fix_step6_update.py',
        'level': 'sub'
    },
}


def execute_task(task_name: str, script_info: dict) -> tuple:
    """执行单个任务，返回(成功bool, 输出str)"""
    script = script_info.get('script')
    args = script_info.get('args', [])
    
    if not script or not Path(script).exists():
        return False, f"脚本不存在: {script}"
    
    try:
        cmd = ['python3', script] + args if script.endswith('.py') else ['bash', script] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=WORKSPACE
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def parse_workflow_result(output: str) -> dict:
    """解析工作流输出"""
    result = {
        'success': False,
        'failed_steps': [],
        'error_type': None,
        'error_message': None
    }
    
    if '工作流结果汇总:' in output:
        for line in output.split('\n'):
            if ': ❌' in line:
                step = line.split(':')[0].strip()
                result['failed_steps'].append(step)
    
    if 'ModuleNotFoundError' in output or 'No module named' in output:
        result['error_type'] = 'error_fix_pending'
        result['error_message'] = '模块导入失败'
    elif 'EPIPE' in output or 'Browser' in output:
        result['error_type'] = 'normal_crash'
        result['error_message'] = '浏览器崩溃'
    elif 'string indices must be integers' in output:
        result['error_type'] = 'error_fix_pending'
        result['error_message'] = '数据类型错误'
    elif "'str' object has no attribute" in output:
        result['error_type'] = 'error_fix_pending'
        result['error_message'] = "str对象无get属性"
    elif result['failed_steps']:
        result['error_type'] = 'error_fix_pending'
        result['error_message'] = f"失败: {', '.join(result['failed_steps'])}"
    else:
        result['success'] = True
    
    return result


def create_fix_subtask(tm: TaskManager, parent_id: str, error_msg: str) -> str:
    """为父任务创建修复子任务"""
    task_name = f"FIX-{parent_id}-{datetime.now().strftime('%H%M%S')}"
    display_name = f"修复: {error_msg[:40]}"
    
    tm.create_sub_task(
        parent_task_id=parent_id,
        task_name=task_name,
        display_name=display_name,
        description=f"自动创建的修复任务: {error_msg}",
        priority="P0",
        fix_suggestion=error_msg
    )
    
    return task_name


def run():
    """主执行流程"""
    log = get_logger("prod_task_cron")
    log.set_message("prod_task_cron启动")
    
    tm = TaskManager()
    actionable = tm.get_actionable_tasks()
    
    if not actionable:
        log.set_message("无待执行任务").finish("skipped")
        print("📋 无待执行任务")
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
        
        # 标记开始
        tm.mark_start(task_name)
        
        # 获取可执行任务（优先P0，每次最多2个）
        script_info = TASK_SCRIPTS.get(task_name)
        if not script_info:
            print(f"  ⚠️ 没有配置执行脚本")
            tm.mark_requires_manual(task_name, "未配置执行脚本")
            continue
        
        # 执行
        success, output = execute_task(task_name, script_info)
        
        # 解析结果（针对工作流任务）
        if task_name == 'TC-FLOW-001':
            wf_result = parse_workflow_result(output)
            
            if wf_result['success']:
                tm.mark_end(task_name, "工作流全部成功")
                log.set_message(f"{display_name} 成功").finish("success")
                print(f"  ✅ 工作流成功")
            else:
                error_type = wf_result['error_type']
                error_msg = wf_result['error_message']
                
                # 创建修复子任务
                fix_task = create_fix_subtask(tm, task_name, error_msg)
                print(f"  ❌ 工作流失败: {error_msg}")
                print(f"  📝 已创建子任务: {fix_task}")
                
                tm.mark_error_fix_pending(task_name, error_msg, fix_task)
                log.set_message(f"{display_name} 失败，创建子任务").finish("failed", error_msg)
        else:
            # 其他任务简单处理
            if success:
                tm.mark_end(task_name, "成功")
                print(f"  ✅ 执行成功")
            else:
                tm.mark_normal_crash(task_name, output[-200:])
                print(f"  ⚠️ 执行失败: {output[-100:]}")
    
    tm.close()
    print(f"\n{'='*60}")
    print("📋 prod_task_cron 执行完成")


if __name__ == '__main__':
    run()
