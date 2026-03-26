#!/usr/bin/env python3
"""
prod_task_cron - 独立任务执行定时器
每30分钟执行一次，从数据库读取待办任务，按优先级执行

自愈机制：
1. 子任务失败 → 重试最多3次
2. 3次仍失败 → 调用LLM分析错误
3. LLM提出方案 → 创建新的解决方案子任务
4. 旧子任务标记为"作废"
5. 新子任务重试3次仍失败 → requires_manual
"""
import sys
import subprocess
from pathlib import Path
from datetime import datetime

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
    'CIRCUIT-BREAKER': {'script': f'{WORKSPACE}/scripts/circuit_breaker.sh'},
    'CONFIG-ENV': {'script': f'{WORKSPACE}/scripts/create_config_env.sh'},
    'COOKIES-ALERT': {'script': f'{WORKSPACE}/scripts/cookies_alert.sh'},
    'PRODUCT-ANALYSIS': {'script': f'{WORKSPACE}/scripts/analyze_products.py'},
    'IMPROVEMENTS-MD': {'script': f'{WORKSPACE}/scripts/update_improvements.sh'},
}

MAX_RETRIES = 3  # 最大重试次数


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
            timeout=600,
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


def call_llm_analyzer(task_info: dict, error: str) -> dict:
    """调用LLM分析错误并返回解决方案"""
    try:
        from error_analyzer import analyze_error
        print(f"  🤖 调用LLM分析错误...")
        solution = analyze_error(task_info, error)
        if solution:
            print(f"  ✅ LLM分析完成")
            return solution
        else:
            print(f"  ❌ LLM分析失败")
            return None
    except Exception as e:
        print(f"  ❌ LLM调用异常: {e}")
        return None


def handle_subtask_failure(tm: TaskManager, task: dict, error: str) -> str:
    """
    处理子任务失败
    1. 检查重试次数
    2. 未超3次 → 标记可重试
    3. 超过3次 → 调用LLM → 创建解决方案子任务 → 旧任务作废
    4. 仍失败 → requires_manual
    """
    task_name = task['task_name']
    retry_count = task.get('retry_count', 0) or 0
    task_level = task.get('task_level', 1)
    
    print(f"  🔄 子任务 {task_name} 失败 (重试次数: {retry_count}/{MAX_RETRIES})")
    
    if retry_count < MAX_RETRIES:
        # 未超过最大重试次数，标记为可重试
        tm.update_task(task_name,
            status='pending',
            exec_state='normal_crash',
            last_error=error
        )
        print(f"  ⏳ 标记为可重试")
        return "retry"
    else:
        # 超过最大重试次数，调用LLM分析
        print(f"  🔴 超过最大重试次数，调用LLM分析...")
        
        solution = call_llm_analyzer(task, error)
        
        if solution and solution.get('solution_steps'):
            # 创建解决方案子任务
            import uuid
            sol_task_name = f"SOL-{task_name}-{uuid.uuid4().hex[:6].upper()}"
            display_name = f"解决方案: {task.get('display_name', task_name)}"
            
            # 合并解决方案步骤
            sol_steps = '\n'.join([f"{i+1}. {s}" for i, s in enumerate(solution.get('solution_steps', []))])
            solution_text = f"根因: {solution.get('root_cause', '')}\n\n修复步骤:\n{sol_steps}\n\n验证: {solution.get('verification', '')}"
            
            tm.create_sub_task(
                parent_task_id=task.get('parent_task_id') or task_name,
                task_name=sol_task_name,
                display_name=display_name,
                description=f"LLM解决方案: {error}",
                priority='P0',
                fix_suggestion=solution_text
            )
            
            # 更新任务解决方案字段
            tm.update_task(sol_task_name, solution=solution_text)
            
            # 标记旧任务为作废
            tm.mark_void(task_name, f"被解决方案任务替代: {sol_task_name}")
            
            print(f"  ✅ 已创建解决方案子任务: {sol_task_name}")
            print(f"  🗑️ 旧任务已标记为作废: {task_name}")
            
            return "solution_created"
        else:
            # LLM分析失败或无法提供方案，标记为需要人工
            tm.update_task(task_name,
                status='failed',
                exec_state='requires_manual',
                last_error=f"LLM分析失败: {error}"
            )
            print(f"  👤 标记为需要人工介入")
            return "requires_manual"


def run():
    """主执行流程"""
    log = get_logger("prod_task_cron")
    log.set_message("prod_task_cron启动")
    
    tm = TaskManager()
    actionable = tm.get_actionable_tasks(limit=1)
    
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
        
        
        # 绑定日志
        log.set_task(task_name)
        # 获取脚本
        script_info = TASK_SCRIPTS.get(task_name)
        
        # 特殊处理：解决方案任务
        if task_name.startswith('SOL-'):
            script_info = {
                'script': f'{WORKSPACE}/scripts/subtask_executor.py',
                'args': [task_name]
            }
        
        # 如果没有脚本但任务是level=2，使用subtask_executor
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
        
        # 执行
        success, output = execute_task(task_name, script_info)
        
        if success:
            # 执行成功
            tm.mark_end(task_name, "执行成功")
            print(f"  ✅ 执行成功")
            log.set_message(f"{display_name} 成功").finish("success")
        else:
            # 执行失败
            print(f"  ❌ 执行失败")
            
            if task_level == 2:
                # 子任务：使用自愈逻辑
                result = handle_subtask_failure(tm, task, output[-500:])
                log.set_message(f"{display_name} 失败: {result}")
                log.set_content(output[-2000:])
                log.finish("failed")
            else:
                # 子任务失败时写入完整错误日志
                log.set_message(f"{display_name} 失败: {result}")
                log.set_content(output[-2000:])  # 保存更多错误信息
                log.finish("failed")
                
                # 父任务：创建子任务
                tm.create_fix_subtasks(task_name, [
                    {'error': output[-200:], 'fix': output[-500:]}
                ])
                tm.update_task(task_name,
                    status='failed',
                    exec_state='error_fix_pending',
                    last_error=output[-200:]
                )
                print(f"  📝 已创建修复子任务")
    
    tm.close()
    print(f"\n{'='*60}")
    print("📋 prod_task_cron 执行完成")


if __name__ == '__main__':
    run()
