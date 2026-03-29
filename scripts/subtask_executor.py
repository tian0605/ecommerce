#!/usr/bin/env python3
"""
subtask_executor.py - 子任务执行器

AI Agent自愈循环：
1. 分析子任务问题
2. LLM思考方案 (ReAct)
3. 制定计划或直接修复
4. 执行修复
5. 回写结果到tasks表
"""
import sys
import os
import json
import re
import requests
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
SCRIPTS_DIR = WORKSPACE / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

# 从配置文件加载
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/config')
from llm_config import LLM_CONFIG
from llm_caller import call_llm_with_fallback  # 使用带Fallback的LLM调用

# 从配置文件加载提示词
PROMPTS_DIR = '/root/.openclaw/workspace-e-commerce/config/prompts'
with open(f'{PROMPTS_DIR}/subtask_executor_system.txt', 'r') as f:
    SYSTEM_PROMPT = f.read()

SUBTASK_USER_TEMPLATE = """任务信息：
- 任务名：{task_name}
- 任务描述：{description}
- 错误信息：{error}
- 修复建议：{fix_suggestion}

请分析并输出修复代码。"""

from task_manager import TaskManager
from logger import get_logger


# ==================== 增强分析函数 ====================

def search_solution_with_tavily(query: str, max_results: int = 3) -> str:
    """
    使用tavily-search搜索解决方案
    """
    import subprocess
    workspace = Path('/root/.openclaw/workspace-e-commerce')
    tavily_key = os.environ.get('TAVILY_API_KEY', '')
    
    if not tavily_key:
        return "[tavily-search跳过: 未配置TAVILY_API_KEY]"
    
    try:
        result = subprocess.run(
            ['node', str(workspace / 'skills/tavily-search/scripts/search.mjs'), query, '-n', str(max_results)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(workspace)
        )
        if result.returncode == 0:
            return result.stdout[:800]
        else:
            return f"[tavily-search失败: {result.stderr[:100]}]"
    except Exception as e:
        return f"[tavily-search异常: {str(e)}]"


def diagnose_with_agent_browser(url: str, selector: str = "") -> str:
    """
    使用agent-browser诊断页面元素
    """
    import subprocess
    workspace = Path('/root/.openclaw/workspace-e-commerce')
    
    try:
        cmds = [
            ['agent-browser', 'open', url],
            ['agent-browser', 'snapshot', '-i'],
        ]
        for cmd in cmds:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(workspace))
            if result.returncode != 0:
                return f"[agent-browser失败: {result.stderr[:100]}]"
        
        return result.stdout[:800]
    except Exception as e:
        return f"[agent-browser异常: {str(e)}]"


def enhance_error_analysis(error_msg: str) -> str:
    """
    增强错误分析，整合tavily-search和agent-browser结果
    
    Returns:
        str: 增强分析结果，如果无需增强则返回空字符串
    """
    if not error_msg:
        return ""
    
    enhancements = []
    
    # 检测是否需要浏览器相关增强
    browser_patterns = [
        r"button.*not.*found",
        r"selector.*not.*found",
        r"Element.*Not.*Found",
        r"点击.*失败",
        r"未找到.*编辑按钮",
        r"playwright",
        r"Puppeteer",
    ]
    
    needs_browser_analysis = any(re.search(p, error_msg, re.I) for p in browser_patterns)
    
    if needs_browser_analysis:
        print("[增强分析] 检测到浏览器/UI相关错误，调用tavily-search...")
        tavily_result = search_solution_with_tavily(
            f"Playwright {error_msg[:100]} fix solution"
        )
        if tavily_result and not tavily_result.startswith('[tavily'):
            enhancements.append(f"【tavily-search解决方案搜索】\n{tavily_result}")
        else:
            enhancements.append(f"【tavily-search】{tavily_result}")
    
    # 检测是否需要文件写入相关增强
    write_patterns = [
        r"write\(\).*str.*not.*int",
        r"TypeError.*str.*int",
        r"编码.*错误|encoding.*error",
    ]
    
    needs_write_analysis = any(re.search(p, error_msg, re.I) for p in write_patterns)
    
    if needs_write_analysis:
        print("[增强分析] 检测到文件写入相关错误...")
        tavily_result = search_solution_with_tavily(
            f"Python {error_msg[:100]} fix"
        )
        if tavily_result and not tavily_result.startswith('[tavily'):
            enhancements.append(f"【tavily-search解决方案搜索】\n{tavily_result}")
    
    if enhancements:
        return "\n\n" + "\n\n".join(enhancements) + "\n"
    
    return ""


def call_llm(messages: list, max_tokens: int = 2000) -> str:
    """调用LLM（带Fallback: Doubao -> DeepSeek）"""
    return call_llm_with_fallback(messages, max_tokens)


def parse_fix_response(content: str) -> dict:
    """解析LLM返回的修复代码"""
    result = {
        'analysis': '',
        'code_fix': ''
    }
    
    if not content:
        return result
    
    # 提取分析部分
    if '【分析】' in content:
        analysis = content.split('【分析】')[1].split('【修复代码】')[0].strip()
        result['analysis'] = analysis
    
    # 提取代码部分
    if '【修复代码】' in content:
        code = content.split('【修复代码】')[1].strip()
        # 去除markdown代码块标记
        if code.startswith('```'):
            code = code.split('\n', 1)[1]
        if '```' in code:
            code = code.split('```')[0]
        result['code_fix'] = code.strip()
    
    return result


def infer_target_module(task_name: str, code: str = "") -> dict:
    """
    从任务名和代码内容推断修复目标模块
    
    Returns:
        dict: {
            'module_type': 'framework' | 'skill' | 'task',
            'module_path': str,       # 源文件路径
            'skill_path': str | None, # SKILL.md路径（仅framework/skill）
            'module_name': str         # 模块名称
        }
    """
    workspace = Path('/root/.openclaw/workspace-e-commerce')
    scripts_dir = workspace / 'scripts'
    skills_dir = workspace / 'skills'
    
    # 核心框架脚本列表
    framework_scripts = {
        'subtask_executor.py': 'task-manager',
        'task_manager.py': 'task-manager',
        'prod_task_cron.py': 'task-manager',
        'logger.py': 'task-manager',
        'workflow_runner.py': 'workflow-runner',
        'error_analyzer.py': 'task-monitor',
        'task_monitor.py': 'task-monitor',
    }
    
    # 从任务名推断
    # FIX-subtask_executor-xxx → subtask_executor.py
    # FIX-task_manager-xxx → task_manager.py
    # FIX-skill-xxx → skills/xxx/SKILL.md
    # FIX-TC-FLOW-001-xxx → workflow_runner.py
    
    task_clean = task_name.replace('FIX-', '').replace('-', '_')
    
    # 检查是否是核心框架脚本
    for script_name, skill_name in framework_scripts.items():
        if script_name.replace('.py', '').lower() in task_clean.lower():
            return {
                'module_type': 'framework',
                'module_path': str(scripts_dir / script_name),
                'skill_path': str(skills_dir / skill_name / 'SKILL.md'),
                'module_name': script_name
            }


def infer_target_from_error(error_msg: str = "", analysis: str = "") -> dict:
    """
    根据错误内容智能推断修复目标文件
    
    增强逻辑：
    - Import错误 → 准确定位到缺失的模块
    - UI/选择器错误 → skill 类型的 updater/scraper
    - 代码错误 → 框架文件
    
    返回值包含 confidence 字段，表示推断的置信度
    """
    error_text = (error_msg + analysis).lower()
    
    # ========== Import 错误处理（高优先级，高置信度）==========
    import_error_match = re.search(r"no module named ['\"]([^'\"]+)['\"]", error_msg, re.IGNORECASE)
    if import_error_match:
        missing_module = import_error_match.group(1).strip()
        print(f"[infer] 检测到Import错误: {missing_module}")
        
        # 检查是否是skills目录下的模块
        skills_dir = Path('/home/ubuntu/.openclaw/skills')
        for skill_path in skills_dir.glob('*/SKILL.md'):
            skill_name = skill_path.parent.name
            # 匹配：miaoshou_collector, collector_scraper, product_storer 等
            skill_normalized = skill_name.replace('-', '_')
            if missing_module == skill_normalized or missing_module == skill_name:
                return {
                    'module_type': 'skill',
                    'module_path': str(skill_path.parent / f'{skill_name.replace("-", "_")}.py'),
                    'skill_path': str(skill_path),
                    'module_name': missing_module,
                    'confidence': 'high',
                    'reason': f'Import错误直接指向模块: {missing_module}'
                }
        
        # 检查是否是scripts目录下的模块
        scripts_dir = Path('/root/.openclaw/workspace-e-commerce/scripts')
        for py_file in scripts_dir.glob('*.py'):
            if missing_module == py_file.stem:
                return {
                    'module_type': 'framework',
                    'module_path': str(py_file),
                    'skill_path': '',
                    'module_name': missing_module,
                    'confidence': 'high',
                    'reason': f'Import错误直接指向脚本: {missing_module}'
                }
        
        # 无法定位，返回None（不应该盲目修复）
        print(f"[infer] 无法定位缺失模块 {missing_module}，不进行盲目修复")
        return None
    
    # ========== UI/选择器相关错误 → miaoshou-updater ==========
    # UI/选择器相关错误 → miaoshou-updater
    if any(kw in error_text for kw in [
        '未找到', '编辑按钮', 'button', 'selector', 'element', 
        'click', 'timeout', '等待', 'wait_for', 'page.', 'dialog'
    ]):
        # 进一步判断是哪个skill
        if 'update' in error_text or '回写' in error_text or 'erp' in error_text:
            return {
                'module_type': 'skill',
                'module_path': '/home/ubuntu/.openclaw/skills/miaoshou_updater/updater.py',
                'skill_path': '/home/ubuntu/.openclaw/skills/miaoshou-updater/SKILL.md',
                'module_name': 'miaoshou_updater'
            }
        elif 'scrape' in error_text or 'extract' in error_text or '采集箱' in error_text:
            return {
                'module_type': 'skill',
                'module_path': '/home/ubuntu/.openclaw/skills/collector_scraper/scraper.py',
                'skill_path': '/home/ubuntu/.openclaw/skills/collector-scraper/SKILL.md',
                'module_name': 'collector_scraper'
            }
        elif 'collect' in error_text or '采集' in error_text:
            return {
                'module_type': 'skill',
                'module_path': '/home/ubuntu/.openclaw/skills/miaoshou_collector/collector.py',
                'skill_path': '/home/ubuntu/.openclaw/skills/miaoshou-collector/SKILL.md',
                'module_name': 'miaoshou_collector'
            }
    
    # 代码执行环境错误 → subtask_executor
    if any(kw in error_text for kw in ['exec_globals', 'write()', 'str.*not.*int', 'name.*not defined', 'functools', 'typing']):
        return {
            'module_type': 'framework',
            'module_path': '/root/.openclaw/workspace-e-commerce/scripts/subtask_executor.py',
            'skill_path': '/root/.openclaw/workspace-e-commerce/skills/task-manager/SKILL.md',
            'module_name': 'subtask_executor'
        }
    
    # 日志/输出错误 → logger
    if 'log_line' in error_text or 'run_content' in error_text:
        return {
            'module_type': 'framework',
            'module_path': '/root/.openclaw/workspace-e-commerce/scripts/logger.py',
            'skill_path': '/root/.openclaw/workspace-e-commerce/skills/task-manager/SKILL.md',
            'module_name': 'logger'
        }
    
    # 工作流整体错误 → workflow_runner
    if any(kw in error_text for kw in ['workflow', 'step1', 'step2', 'step3', '步骤']):
        return {
            'module_type': 'framework',
            'module_path': '/root/.openclaw/workspace-e-commerce/skills/workflow-runner/scripts/workflow_runner.py',
            'skill_path': '/root/.openclaw/workspace-e-commerce/skills/workflow-runner/SKILL.md',
            'module_name': 'workflow_runner'
        }
    
    return None  # 无法推断
    
    # 检查是否是 skills 模块
    # skills模块在 /home/ubuntu/.openclaw/skills/ 目录下
    skill_base_dir = Path('/home/ubuntu/.openclaw/skills')
    for skill_path in (skills_dir).glob('*/SKILL.md'):
        skill_name = skill_path.parent.name
        # 需要同时匹配带连字符和下划线的版本
        # 如: miaoshou-updater 和 miaoshou_updater 都要匹配 miaoshou_updater_001
        skill_normalized = skill_name.replace('-', '_').lower()
        if skill_normalized in task_clean.lower() or skill_name.replace('_', '-').lower() in task_clean.lower().replace('_', '-'):
            # 找到对应的脚本文件（在skill目录下）
            # 如: miaoshou_updater → /home/ubuntu/.openclaw/skills/miaoshou_updater/updater.py
            # 尝试多种可能的目录名
            possible_names = [
                skill_name,  # 原名
                skill_name.replace('-', '_'),  # 下划线版本
                skill_name.replace('_', '-'),  # 连字符版本
            ]
            
            skill_dir = None
            for name in possible_names:
                candidate = skill_base_dir / name
                if candidate.exists():
                    skill_dir = candidate
                    break
            
            if not skill_dir:
                # 尝试在 workspace 的 skills 目录下找
                for name in possible_names:
                    candidate = skills_dir / name
                    if candidate.exists():
                        skill_dir = candidate
                        break
            
            # 查找主脚本文件
            main_script = None
            if skill_dir and skill_dir.exists():
                for pattern in ['updater.py', 'scraper.py', 'collector.py', 'storer.py', 'optimizer.py', 'analyzer.py', 'runner.py', 'collector.py']:
                    candidate = skill_dir / pattern
                    if candidate.exists():
                        main_script = candidate
                        break
                
                # 备用：直接用 skill_name 查找
                if not main_script:
                    for f in skill_dir.glob('*.py'):
                        if f.name != '__init__.py':
                            main_script = f
                            break
            
            return {
                'module_type': 'skill',
                'module_path': str(main_script) if main_script else str(skill_dir) if skill_dir else None,
                'skill_path': str(skill_path),
                'module_name': skill_name
            }
    
    # 特殊处理：FIX-TC-FLOW-* → workflow_runner.py (workflow-runner skill)
    # TC-FLOW-xxx 是工作流任务，其FIX任务的修复应该直接应用到 workflow_runner.py
    if task_name.startswith('FIX-TC-FLOW-'):
        # 找到对应的脚本路径
        script_path = skills_dir / 'workflow-runner' / 'scripts' / 'workflow_runner.py'
        if not script_path.exists():
            # 备用路径
            script_path = scripts_dir / 'workflow_runner.py'
        return {
            'module_type': 'framework',
            'module_path': str(script_path),
            'skill_path': str(skills_dir / 'workflow-runner' / 'SKILL.md'),
            'module_name': 'workflow_runner.py'
        }
    
    # 默认：任务级别的fix，存放到fixes目录
    return {
        'module_type': 'task',
        'module_path': None,
        'skill_path': None,
        'module_name': task_name
    }


def apply_fix_to_source(module_path: str, code: str, backup: bool = True) -> tuple:
    """
    将修复代码应用到源文件
    
    Args:
        module_path: 源文件路径
        code: 修复代码
        backup: 是否备份原文件
    
    Returns:
        (success, message)
    """
    if not module_path or not Path(module_path).exists():
        return False, f"源文件不存在: {module_path}"
    
    try:
        module_file = Path(module_path)
        
        # 备份原文件
        if backup:
            backup_dir = module_file.parent / 'backups'
            backup_dir.mkdir(exist_ok=True)
            backup_file = backup_dir / f"{module_file.name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            with open(module_file, 'r') as src:
                content = src.read()
            with open(backup_file, 'w') as dst:
                dst.write(content)
            print(f"已备份: {backup_file}")
        
        # 分析代码：是完整文件替换还是部分替换
        if code.startswith('#!/usr/bin/env python3') or 'import ' in code[:200]:
            # 完整文件替换
            with open(module_file, 'w') as f:
                f.write(code)
            return True, f"完整替换源文件: {module_path}"
        else:
            # 部分替换：需要智能合并
            return apply_partial_fix(module_file, code)
        
    except Exception as e:
        return False, f"应用修复失败: {str(e)}"


def apply_partial_fix(module_file: Path, code: str) -> tuple:
    """
    智能合并部分修复代码到源文件
    
    分析修复代码中的函数定义，替换源文件中对应的函数
    """
    try:
        with open(module_file, 'r') as f:
            original_content = f.read()
        
        # 提取修复代码中的函数定义
        func_pattern = r'(def \w+\([^)]*\):.*?(?=\n(?:def |class |import |from |$)))'
        funcs_in_fix = re.findall(func_pattern, code, re.DOTALL)
        
        if not funcs_in_fix:
            # 没有找到函数定义，无法智能合并
            return False, "无法智能合并：修复代码不包含函数定义"
        
        modified_content = original_content
        for func_def in funcs_in_fix:
            # 提取函数名
            func_name_match = re.match(r'def (\w+)', func_def)
            if func_name_match:
                func_name = func_name_match.group(1)
                
                # 在原文件中查找并替换该函数
                func_pattern_orig = rf'(def {func_name}\([^)]*\):.*?(?=\n(?:def |class |import |from |$)))'
                
                if re.search(func_pattern_orig, modified_content, re.DOTALL):
                    modified_content = re.sub(
                        func_pattern_orig, 
                        func_def.strip(), 
                        modified_content, 
                        flags=re.DOTALL
                    )
                    print(f"已替换函数: {func_name}")
                else:
                    # 函数不存在，追加到文件末尾
                    modified_content += '\n\n' + func_def
                    print(f"已追加新函数: {func_name}")
        
        # 写入修改后的内容
        with open(module_file, 'w') as f:
            f.write(modified_content)
        
        return True, f"智能合并成功: {module_file.name}"
        
    except Exception as e:
        return False, f"智能合并失败: {str(e)}"


def append_fix_to_skill(skill_path: str, task_name: str, code: str, analysis: str = "") -> tuple:
    """
    将修复记录追加到 SKILL.md
    
    Args:
        skill_path: SKILL.md 路径
        task_name: 任务名
        code: 修复代码
        analysis: 分析说明
    
    Returns:
        (success, message)
    """
    if not skill_path or not Path(skill_path).exists():
        return False, f"SKILL文件不存在: {skill_path}"
    
    try:
        fix_record = f"""

---

### 修复: {task_name} ({datetime.now().strftime('%Y-%m-%d')})

**问题**: {analysis if analysis else '见任务描述'}

**修复代码**:
```python
{code[:500]}{'...' if len(code) > 500 else ''}
```

**持久化位置**: 源文件直接修改

"""
        
        with open(skill_path, 'a') as f:
            f.write(fix_record)
        
        return True, f"已追加修复记录到: {skill_path}"
        
    except Exception as e:
        return False, f"追加修复记录失败: {str(e)}"


def execute_fix_code(code: str, task_name: str, error_msg: str = "", analysis: str = "") -> tuple:
    """执行修复代码，智能持久化到正确位置
    
    优先级：
    1. 根据错误内容推断目标（infer_target_from_error）→ 直接修改源文件
    2. 根据任务名推断目标（infer_target_module）→ 直接修改源文件
    3. 任务特定fix → 写入 fixes/ 目录
    """
    if not code:
        return False, "没有修复代码"
    
    # 1. 优先尝试根据错误内容推断目标（更准确）
    target = None
    error_target = infer_target_from_error(
        error_msg=error_msg or "",
        analysis=analysis or ""
    )
    if error_target and error_target.get('confidence') == 'high':
        print(f"[智能推断] 根据错误内容推断目标: {error_target['module_name']} (置信度: 高)")
        target = error_target
    
    # 2. 如果无法推断，使用任务名推断
    if not target:
        target = infer_target_module(task_name, code)
    
    # 3. 最终保底：如果仍然无法确定目标，不进行盲目修复
    if not target:
        print(f"[警告] 无法确定问题位置，不进行盲目修复！")
        print(f"[建议] 人工介入检查任务: {task_name}")
        return False, "无法确定问题位置，需要人工介入"
    
    # 4. 只有在置信度足够高时才修复
    confidence = target.get('confidence', 'medium')
    if confidence != 'high':
        print(f"[警告] 置信度为 {confidence}，谨慎修复")
    
    print(f"修复目标: {target['module_name']} ({target.get('reason', 'unknown')})")
    
    print(f"修复目标: {target}")
    
    # 用于记录详细的修复信息
    fix_details = {
        'target_type': target['module_type'],
        'target_file': target.get('module_path', 'N/A'),
        'skill_file': target.get('skill_path', 'N/A'),
        'changes': []
    }
    
    # 2. 根据目标类型选择持久化策略
    if target['module_type'] == 'framework':
        # 核心框架脚本：直接修改源文件
        success, msg = apply_fix_to_source(target['module_path'], code)
        print(msg)
        fix_details['changes'].append(f"源文件修改: {msg}")
        
        # 更新 SKILL.md
        if success and target['skill_path']:
            sk_success, sk_msg = append_fix_to_skill(
                target['skill_path'], task_name, code, analysis
            )
            print(sk_msg)
            fix_details['changes'].append(f"SKILL更新: {sk_msg}")
        
        # 同时保留一份到 fixes 目录（用于追溯）
        persist_to_fixes_dir(task_name, code, prefix="source_")
        fix_details['changes'].append(f"备份: fixes/source_{task_name}.py")
        
        return success, f"框架修复: {msg} | {'; '.join(fix_details['changes'])}"
    
    elif target['module_type'] == 'skill' and target['module_path']:
        # Skills模块：直接修改源文件
        success, msg = apply_fix_to_source(target['module_path'], code)
        print(msg)
        fix_details['changes'].append(f"源文件修改: {msg}")
        
        # 更新 SKILL.md
        if success and target['skill_path']:
            sk_success, sk_msg = append_fix_to_skill(
                target['skill_path'], task_name, code, analysis
            )
            print(sk_msg)
            fix_details['changes'].append(f"SKILL更新: {sk_msg}")
        
        persist_to_fixes_dir(task_name, code, prefix="source_")
        fix_details['changes'].append(f"备份: fixes/source_{task_name}.py")
        
        return success, f"Skill修复: {msg} | {'; '.join(fix_details['changes'])}"
    
    else:
        # 任务特定fix：写入 fixes 目录（旧机制）
        success, msg = persist_to_fixes_dir(task_name, code)
        return success, f"任务修复: {msg}"


def persist_to_fixes_dir(task_name: str, code: str, prefix: str = "fix_") -> tuple:
    """持久化代码到 fixes 目录（旧机制，保留用于追溯）"""
    try:
        fixes_dir = Path('/root/.openclaw/workspace-e-commerce/scripts/fixes')
        fixes_dir.mkdir(exist_ok=True)
        
        safe_name = task_name.replace('-', '_').replace(':', '_')
        fix_file = fixes_dir / f'{prefix}{safe_name}.py'
        
        with open(fix_file, 'w') as f:
            f.write(code)
            f.write(f'\n# 执行入口：apply_fix()\n')
            f.write('def apply_fix():\n')
            f.write('    pass  # 入口函数\n')
        
        print(f"修复代码已持久化: {fix_file}")
        
        # 预加载常用模块
        import functools, logging, time, re, json
        from typing import Any, Dict, List, Optional, Tuple, Union
        exec_globals = {
            '__name__': '__fix__',
            'fix_file': str(fix_file),
            'functools': functools,
            'logging': logging,
            'time': time,
            're': re,
            'json': json,
            'Any': Any,
            'Dict': Dict,
            'List': List,
            'Optional': Optional,
            'Tuple': Tuple,
            'Union': Union,
        }
        
        exec_locals = {}
        with open(fix_file, 'r') as f:
            exec(f.read(), exec_globals, exec_locals)
        
        return True, f"修复代码执行成功 (已持久化到 {fix_file})"
        
    except Exception as e:
        return False, f"执行错误: {str(e)}"


def main(task_name: str):
    """主函数"""
    log = get_logger('subtask')
    log.set_task(task_name).set_message(f"开始执行子任务: {task_name}").finish("running")
    
    tm = TaskManager()
    
    # 获取任务信息
    task = tm.get_task(task_name)
    if not task:
        print(f"任务不存在: {task_name}")
        return
    
    description = task.get('description', '')
    fix_suggestion = task.get('fix_suggestion', '')
    last_error = task.get('last_error', '')
    
    print(f"任务: {task_name}")
    print(f"描述: {description}")
    print(f"错误: {last_error}")
    
    # 增强错误分析
    enhanced_analysis = enhance_error_analysis(last_error)
    if enhanced_analysis:
        print(f"\n增强分析结果: {enhanced_analysis[:200]}...")
    
    # 构建prompt
    user_prompt = SUBTASK_USER_TEMPLATE.format(
        task_name=task_name,
        description=description or '无',
        error=last_error or '无',
        fix_suggestion=fix_suggestion or '无'
    )
    
    # 添加增强分析结果
    if enhanced_analysis:
        user_prompt += f"\n\n【增强分析参考】（来自tavily-search和agent-browser）:\n{enhanced_analysis}"
    
    # 调用LLM
    print("\n调用LLM分析...")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    response = call_llm(messages)
    
    if not response:
        print("LLM调用失败")
        tm.mark_error_fix_pending(task_name, "LLM调用失败")
        return
    
    print(f"\nLLM返回:\n{response}")
    
    # 解析响应
    parsed = parse_fix_response(response)
    
    print(f"\n分析: {parsed['analysis']}")
    print(f"修复代码: {parsed['code_fix'][:200] if parsed['code_fix'] else '无'}...")
    
    # 执行修复代码
    if parsed['code_fix']:
        print("\n执行修复代码...")
        success, msg = execute_fix_code(
            parsed['code_fix'], 
            task_name, 
            error_msg=last_error,  # 传入last_error用于目标推断
            analysis=parsed['analysis']
        )
        print(f"执行结果: {msg}")
        
        # 构建详细日志内容
        fix_content = f"""=== 修复任务执行详情 ===
任务: {task_name}
分析: {parsed['analysis']}

修复代码:
{parsed['code_fix']}

执行结果: {msg}
"""
        
        if success:
            tm.mark_end(task_name, "修复成功")
            log.set_message(f"修复成功").set_content(fix_content).finish("success")
        else:
            tm.mark_error_fix_pending(task_name, msg)
            log.set_message(f"修复失败: {msg}").set_content(fix_content).finish("failed")
    else:
        print("没有可执行的修复代码")
        no_code_content = f"""=== 修复任务执行详情 ===
任务: {task_name}
分析: {parsed['analysis'] if parsed['analysis'] else '无'}
修复代码: 无
结果: 没有可执行的修复代码
"""
        log.set_message(f"没有可执行的修复代码").set_content(no_code_content).finish("failed")
        tm.mark_error_fix_pending(task_name, "没有可执行的修复代码")
    
    tm.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python subtask_executor.py <task_name>")
        sys.exit(1)
    
    main(sys.argv[1])
