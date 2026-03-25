#!/usr/bin/env python3
"""
task-creator: 任务创建器

接收用户任务，评估清晰度，写入工作流系统
"""

import json
import sys
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
QUEUE_FILE = WORKSPACE / 'docs' / 'dev-task-queue.md'
STATE_FILE = WORKSPACE / 'logs' / 'task_state.json'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

class TaskCreator:
    """任务创建器"""
    
    def __init__(self):
        self.task_info = {
            'name': None,
            'description': None,
            'criteria': [],
            'steps': [],
            'created_at': None,
            'clarity_issues': []
        }
    
    def assess_clarity(self, task_text):
        """评估任务清晰度"""
        issues = []
        
        # 检查任务描述是否为空或太短
        if not task_text or len(task_text.strip()) < 10:
            issues.append("任务描述太简单或为空")
        
        # 检查是否包含执行主体
        executors = ['AI', 'agent', '自动', '我', '你', '手动', '心跳', 'cron']
        if not any(word in task_text for word in executors):
            issues.append("未明确执行主体（AI自动执行还是手动）")
        
        # 检查是否包含成功标准关键词
        success_keywords = ['成功', '完成', '标准', '验证', '结果', '输出']
        if not any(word in task_text for word in success_keywords):
            issues.append("未明确成功标准或验证方法")
        
        # 检查是否包含时间要求
        time_keywords = ['每天', '定时', '定期', '每周', '完成时间', '截止']
        if not any(word in task_text for word in time_keywords):
            issues.append("未明确时间要求（何时完成/执行频率）")
        
        return issues
    
    def assess_criteria_clarity(self, criteria_text):
        """评估成功标准清晰度"""
        issues = []
        
        if not criteria_text or len(criteria_text.strip()) < 5:
            issues.append("标准描述太简单")
        
        # 检查是否可量化
        if not any(char.isdigit() for char in criteria_text):
            issues.append("标准缺少具体数字指标")
        
        # 检查是否有验证方法
        verify_keywords = ['检查', '验证', '确认', '输出', '记录', '发送']
        if not any(word in criteria_text for word in verify_keywords):
            issues.append("未说明如何验证标准达成")
        
        return issues
    
    def generate_questions(self, issues):
        """根据问题生成追问"""
        questions = []
        
        if "未明确执行主体" in issues:
            questions.append("**1. 执行方式**：这个任务是由我（AI agent）自动执行，还是需要你手动操作？")
        
        if "未明确成功标准" in issues:
            questions.append("**2. 成功标准**：怎么判断任务完成了？需要验证什么具体指标或结果？")
        
        if "未明确时间要求" in issues:
            questions.append("**3. 时间要求**：什么时候需要完成？是每天定时执行还是一次性任务？")
        
        if "任务描述太简单" in issues:
            questions.append("**4. 具体步骤**：请详细描述任务的具体执行步骤")
        
        return questions
    
    def write_to_queue(self):
        """写入 dev-task-queue.md"""
        task = self.task_info
        
        # 构建新任务内容
        task_content = f"""
### {task['name']}
**创建时间：** {task['created_at']}
**状态：** 📋 待执行

**任务目标：**
{task['description']}

**成功标准：**
| # | 标准 | 验证方法 | 状态 |
|---|------|----------|------|
"""
        for i, criterion in enumerate(task['criteria'], 1):
            task_content += f"| {i} | {criterion.get('name', '')} | {criterion.get('verify', '待定')} | ⬜ |\n"
        
        task_content += f"""
**执行步骤：**
"""
        for i, step in enumerate(task['steps'], 1):
            task_content += f"{i}. {step}\n"
        
        task_content += "\n---\n"
        
        # 读取现有内容
        if QUEUE_FILE.exists():
            with open(QUEUE_FILE, 'r') as f:
                content = f.read()
        else:
            content = "# 开发任务队列\n\n"
        
        # 在 "## 📋 今日任务" 或顶部插入
        marker = "## 📋 今日任务"
        
        if marker in content:
            lines = content.split('\n')
            new_lines = []
            for line in lines:
                new_lines.append(line)
                if marker in line and not any('###' in l for l in new_lines[:-1]):
                    new_lines.append(task_content)
            content = '\n'.join(new_lines)
        else:
            content = content + '\n' + task_content
        
        # 写回文件
        with open(QUEUE_FILE, 'w') as f:
            f.write(content)
        
        log(f"已写入 {QUEUE_FILE}")
    
    def write_to_state(self):
        """写入 task_state.json"""
        state = {
            'task_name': self.task_info['name'],
            'created_at': self.task_info['created_at'],
            'description': self.task_info['description'],
            'success_criteria': self.task_info['criteria'],
            'steps': self.task_info['steps'],
            'status': 'pending',
            'current_step': 0,
            'completed': False
        }
        
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        
        log(f"已写入 {STATE_FILE}")
    
    def create_task(self, task_text, criteria_list):
        """
        创建任务
        
        Args:
            task_text: 任务描述文本
            criteria_list: 成功标准列表，每项是 {'name': '标准名', 'verify': '验证方法'}
        
        Returns:
            (success, message)
        """
        # 评估任务清晰度
        task_issues = self.assess_clarity(task_text)
        self.task_info['clarity_issues'] = task_issues
        
        if task_issues:
            questions = self.generate_questions(task_issues)
            return False, {
                'type': 'need_clarification',
                'issues': task_issues,
                'questions': questions
            }
        
        # 评估成功标准清晰度
        criteria_issues = []
        for criterion in criteria_list:
            issues = self.assess_criteria_clarity(criterion.get('name', '') + ' ' + criterion.get('verify', ''))
            criteria_issues.extend(issues)
        
        if criteria_issues:
            return False, {
                'type': 'criteria_unclear',
                'issues': criteria_issues,
                'questions': ["请明确每个成功标准的具体数字指标和验证方法"]
            }
        
        # 写入任务
        self.task_info['name'] = f"任务_{datetime.now().strftime('%Y%m%d_%H%M')}"
        self.task_info['description'] = task_text
        self.task_info['criteria'] = criteria_list
        self.task_info['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        self.write_to_queue()
        self.write_to_state()
        
        return True, {
            'type': 'success',
            'message': '任务已创建',
            'task_name': self.task_info['name']
        }

def list_tasks():
    """列出所有任务及其状态"""
    print("\n" + "=" * 60)
    print("📋 任务清单")
    print("=" * 60)
    
    # 读取 task_state.json（最新任务状态）
    print("\n【当前执行状态】")
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
            
            print(f"  任务名称: {state.get('task_name', 'N/A')}")
            print(f"  创建时间: {state.get('created_at', 'N/A')}")
            print(f"  状态: {state.get('status', 'N/A')}")
            print(f"  完成度: {state.get('current_step', 0)}/{len(state.get('steps', []))} 步骤")
            
            criteria = state.get('success_criteria', [])
            if criteria:
                print(f"\n  成功标准 ({len(criteria)} 项):")
                for i, c in enumerate(criteria, 1):
                    print(f"    {i}. {c.get('name', 'N/A')}")
        except Exception as e:
            print(f"  读取失败: {e}")
    else:
        print("  无执行中的任务")
    
    # 读取 dev-task-queue.md（任务队列）
    print("\n【任务队列】")
    if QUEUE_FILE.exists():
        try:
            with open(QUEUE_FILE, 'r') as f:
                content = f.read()
            
            lines = content.split('\n')
            current_section = None
            task_count = 0
            
            for line in lines:
                # 检测章节
                if line.startswith('## '):
                    current_section = line.replace('## ', '')
                    print(f"\n  📌 {current_section}")
                elif line.startswith('### '):
                    task_name = line.replace('### ', '').strip()
                    if task_name and task_name != 'P0 问题（立即处理）':
                        print(f"    - {task_name}")
                        task_count += 1
                elif '**状态**' in line:
                    status = line.split('**状态**')[1].split('**')[0].strip() if '**' in line else ''
                    print(f"      状态: {status}")
            
            if task_count == 0:
                print("    (空)")
        except Exception as e:
            print(f"  读取失败: {e}")
    else:
        print("  任务队列文件不存在")
    
    # 检查 task_executor 日志
    executor_log = WORKSPACE / 'logs' / 'task_executor.log'
    if executor_log.exists():
        try:
            with open(executor_log, 'r') as f:
                lines = f.readlines()
            
            # 获取最后10行
            last_lines = lines[-10:] if len(lines) > 10 else lines
            
            print("\n【最近执行日志】")
            for line in last_lines:
                line = line.strip()
                if line:
                    print(f"  {line}")
        except Exception as e:
            print(f"  读取日志失败: {e}")
    
    print("\n" + "=" * 60)
    print("📊 统计")
    print("=" * 60)
    
    # 统计 P0 问题
    if QUEUE_FILE.exists():
        try:
            with open(QUEUE_FILE, 'r') as f:
                content = f.read()
            
            p0_count = content.count('**P0]**') + content.count('[P0]')
            pending_count = content.count('⬜')
            completed_count = content.count('✅')
            
            print(f"  P0 问题: {p0_count} 个")
            print(f"  待执行: {pending_count} 个")
            print(f"  已完成: {completed_count} 个")
        except:
            pass
    
    print("\n" + "=" * 60)
    
    return True

def main():
    """命令行接口"""
    if len(sys.argv) < 2:
        # 无参数时列出任务
        list_tasks()
        sys.exit(0)
    
    command = sys.argv[1]
    
    if command == '--list' or command == 'list':
        list_tasks()
    elif command == '--help':
        print("""
task-creator 用法:

  # 列出所有任务
  python3 task_creator.py list
  
  # 创建新任务
  python3 task_creator.py '<任务描述>' '<成功标准JSON>'
  
  # 示例
  python3 task_creator.py '每日更新热搜词' '[{"name":"更新成功","verify":"数据库记录>400"}]'
        """)
    elif len(sys.argv) < 3:
        print("参数不足！用法: task_creator.py <任务描述> <成功标准JSON>")
        print("查看帮助: task_creator.py --help")
        sys.exit(1)
    else:
        task_text = sys.argv[1]
        try:
            criteria = json.loads(sys.argv[2])
        except json.JSONDecodeError:
            print("错误：成功标准JSON格式错误")
            sys.exit(1)
        
        creator = TaskCreator()
        success, result = creator.create_task(task_text, criteria)
        
        if success:
            print(f"\n✅ {result['message']}")
            print(f"任务名: {result['task_name']}")
        else:
            print("\n⚠️ 任务信息不完整，需要补充：")
            for q in result.get('questions', []):
                print(f"  {q}")
            sys.exit(1)

if __name__ == '__main__':
    main()
