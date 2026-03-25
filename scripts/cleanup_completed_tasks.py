#!/usr/bin/env python3
"""
清理已完成的任务
当所有任务验证通过后自动调用
1. 备份 task_state.json 到 logs/
2. 将完成任务移到 completed-tasks.md
3. 清理 dev-task-queue.md 中的旧P0问题
"""

import json
import sys
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
TASK_STATE = WORKSPACE / 'logs' / 'task_state.json'
COMPLETED_TASKS = WORKSPACE / 'docs' / 'completed-tasks.md'
TASK_QUEUE = WORKSPACE / 'docs' / 'dev-task-queue.md'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 清理: {msg}", flush=True)

def format_timestamp(ts):
    """格式化时间戳"""
    if not ts:
        return datetime.now().strftime('%Y-%m-%d %H:%M')
    try:
        # 处理 ISO 格式
        if 'T' in ts:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M')
        return ts[:16]
    except:
        return ts[:16] if ts else datetime.now().strftime('%Y-%m-%d %H:%M')

def cleanup_completed_tasks():
    """清理已完成的任务"""
    # 检查 task_state.json 是否存在
    if not TASK_STATE.exists():
        log("task_state.json 不存在，无需清理")
        return False
    
    # 读取状态
    with open(TASK_STATE) as f:
        state = json.load(f)
    
    # 检查是否完成
    if not state.get('completed'):
        log("任务未完成，跳过清理")
        return False
    
    # 检查是否已清理过（备份文件已存在）
    timestamp = state.get('completed_at', datetime.now().strftime('%Y-%m-%d_%H%M%S'))[:16].replace(':', '')
    backup_file = WORKSPACE / 'logs' / f'task_state_{timestamp}.json'
    if backup_file.exists():
        log("任务已清理过，跳过")
        return False
    
    # 1. 备份 task_state.json
    backup_content = json.dumps(state, indent=2, ensure_ascii=False)
    with open(backup_file, 'w') as f:
        f.write(backup_content)
    log(f"✅ 已备份任务状态到 {backup_file.name}")
    
    # 2. 提取结果汇总
    results = state.get('results', [])
    if results:
        # 读取现有的 completed-tasks.md
        existing_content = ""
        if COMPLETED_TASKS.exists():
            with open(COMPLETED_TASKS) as f:
                existing_content = f.read()
        
        # 构建新记录
        completed_date = state.get('completed_at', datetime.now().isoformat())[:10]
        new_record = f"\n## {completed_date} 模块测试调优\n\n"
        new_record += "**测试商品：** 货源ID 1026175430866\n\n"
        
        for r in results:
            data = r.get('data', {})
            step = r.get('step', 'unknown')
            success = r.get('success', False)
            msg = r.get('message', '')
            ts = format_timestamp(r.get('timestamp'))
            
            status = "✅" if success else "❌"
            new_record += f"### {status} {step}（{ts} 完成）\n"
            new_record += f"- 状态: {msg}\n"
            
            if data:
                if data.get('optimized_title'):
                    new_record += f"- 优化标题: {data.get('optimized_title')[:50]}...\n"
                if data.get('suggested_price_twd'):
                    new_record += f"- 建议售价: {data.get('suggested_price_twd')} TWD\n"
                if data.get('gross_profit_twd'):
                    new_record += f"- 预估利润: {data.get('gross_profit_twd')} TWD\n"
            new_record += "\n"
        
        # 插入到 completed-tasks.md
        if existing_content:
            # 在 "## 历史记录" 之前插入
            if "## 历史记录" in existing_content:
                new_content = existing_content.replace("## 历史记录", new_record + "## 历史记录")
            else:
                new_content = existing_content + new_record
        else:
            new_content = f"""# 已完成任务记录

> 记录已完成的开发任务，保持任务队列干净
> 最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}

{new_record}
## 历史记录

（暂无）

---

*最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
        
        with open(COMPLETED_TASKS, 'w') as f:
            f.write(new_content)
        log(f"✅ 已更新 {COMPLETED_TASKS.name}")
    
    # 3. 清理 dev-task-queue.md 中的P0问题（只保留最近一次验证后的）
    if TASK_QUEUE.exists():
        with open(TASK_QUEUE) as f:
            content = f.read()
        
        # 查找 P0 问题部分
        if "## 🔴 P0 问题" in content:
            # 找到 P0 部分并清理旧的重复问题
            lines = content.split('\n')
            new_lines = []
            in_p0_section = False
            p0_header_idx = -1
            
            for i, line in enumerate(lines):
                if "## 🔴 P0 问题" in line:
                    in_p0_section = True
                    p0_header_idx = len(new_lines)
                    new_lines.append(line)
                    continue
                
                if in_p0_section:
                    # 检查是否到达下一个 ## 标题
                    if line.startswith('## ') and 'P0' not in line:
                        in_p0_section = False
                        # 在P0部分末尾添加"（无）"
                        if len(new_lines) > p0_header_idx + 1:
                            # 检查最后一行是否已经是"（无）"
                            last_line = new_lines[-1].strip()
                            if last_line not in ['（无）', '> 每次心跳执行后，必须检查此部分是否有新问题']:
                                new_lines.append('\n（无）')
                        new_lines.append('')
                        new_lines.append(line)
                        in_p0_section = False
                        continue
                    elif line.startswith('>') or line.startswith('（'):  # 跳过注释行
                        continue
                    elif '### 20' in line:  # 日期标题，表示是旧问题
                        continue  # 跳过旧问题
                    elif line.strip() == '':
                        continue  # 跳过空行
                new_lines.append(line)
            
            content = '\n'.join(new_lines)
            
            with open(TASK_QUEUE, 'w') as f:
                f.write(content)
            log(f"✅ 已清理 {TASK_QUEUE.name} 中的旧P0问题")
    
    log("✅ 清理完成")
    return True

if __name__ == '__main__':
    cleanup_completed_tasks()
