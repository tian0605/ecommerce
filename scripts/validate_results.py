#!/usr/bin/env python3
"""
验证任务执行结果
检查 task_state.json 中的结果是否有效
"""

import json
import sys
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
STATE_FILE = WORKSPACE / 'logs' / 'task_state.json'
QUEUE_FILE = WORKSPACE / 'docs' / 'dev-task-queue.md'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 验证: {msg}", flush=True)

def validate_results():
    """验证任务结果"""
    
    # 读取状态文件
    if not STATE_FILE.exists():
        log("状态文件不存在")
        return "skip"
    
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
    except Exception as e:
        log(f"读取状态文件失败: {e}")
        return "skip"
    
    # 检查是否完成
    if not state.get('completed'):
        log("任务未完成，跳过验证")
        return "skip"
    
    results = state.get('results', [])
    if not results:
        log("无执行结果")
        return "skip"
    
    # 验证每个步骤
    issues = []
    
    for r in results:
        step = r.get('step', 'unknown')
        success = r.get('success', False)
        data = r.get('data', {})
        
        if not success:
            issues.append({
                'step': step,
                'issue': r.get('message', '未知错误'),
                'priority': 'P0'
            })
            continue
        
        # 检查关键字段是否存在
        if step == 'listing-optimizer':
            if not data.get('optimized_title'):
                issues.append({
                    'step': step,
                    'issue': '优化标题为空',
                    'priority': 'P0'
                })
            # 检查是否保存到数据库
            db_id = data.get('db_id')
            if db_id:
                # 验证数据库中是否有数据
                try:
                    import psycopg2
                    conn = psycopg2.connect(
                        host='localhost',
                        database='ecommerce_data',
                        user='superuser',
                        password='Admin123!'
                    )
                    cur = conn.cursor()
                    cur.execute("SELECT optimized_title FROM products WHERE id = %s", (db_id,))
                    row = cur.fetchone()
                    conn.close()
                    
                    if not row or not row[0]:
                        issues.append({
                            'step': step,
                            'issue': 'optimized_title 未保存到数据库',
                            'priority': 'P0'
                        })
                        log(f"⚠️ listing-optimizer 未保存到 DB!")
                except Exception as e:
                    log(f"数据库验证失败: {e}")
        
        if step == 'miaoshou-updater':
            if data.get('note') and '跳过' in data.get('note', ''):
                issues.append({
                    'step': step,
                    'issue': f"任务跳过: {data.get('note')}",
                    'priority': 'P0'
                })
        
        if step == 'profit-analyzer':
            price = data.get('suggested_price_twd', 0)
            if price and price < 100:
                issues.append({
                    'step': step,
                    'issue': f"建议售价过低: {price} TWD",
                    'priority': 'P1'
                })
    
    # 输出结果
    if issues:
        log(f"发现 {len(issues)} 个问题")
        
        # 更新 dev-task-queue.md
        update_queue(issues)
        
        return "has_issues"
    else:
        log("所有步骤验证通过")
        return "all_ok"

def update_queue(issues):
    """更新任务队列，添加发现的问题"""
    
    if not issues:
        return
    
    log("更新 P0 问题到任务队列...")
    
    # 构建新的 P0 问题
    new_p0_content = []
    new_p0_content.append(f"\n### {datetime.now().strftime('%Y-%m-%d %H:%M')} - 自动发现问题\n")
    
    for issue in issues:
        priority = issue.get('priority', 'P0')
        step = issue.get('step', 'unknown')
        desc = issue.get('issue', '')
        
        new_p0_content.append(f"**[{priority}] {step}:** {desc}\n")
    
    # 读取现有内容
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE, 'r') as f:
            content = f.read()
    else:
        content = "# 开发任务队列\n\n"
    
    # 在 P0 部分插入新问题
    p0_header = "## 🔴 P0 问题（立即处理）"
    
    if p0_header in content:
        # 找到 P0 部分
        lines = content.split('\n')
        new_lines = []
        in_p0 = False
        inserted = False
        
        for line in lines:
            if p0_header in line:
                in_p0 = True
                new_lines.append(line)
                continue
            
            if in_p0 and line.startswith('## ') and not inserted:
                # 在下一个章节前插入
                new_lines.extend(new_p0_content)
                new_lines.append(line)
                inserted = True
                in_p0 = False
            else:
                new_lines.append(line)
        
        if not inserted:
            new_lines.extend(new_p0_content)
        
        content = '\n'.join(new_lines)
    else:
        # 在文件开头插入
        content = p0_header + '\n\n' + ''.join(new_p0_content) + '\n\n' + content
    
    # 写回文件
    with open(QUEUE_FILE, 'w') as f:
        f.write(content)
    
    log(f"已添加 {len(issues)} 个 P0 问题")

if __name__ == '__main__':
    result = validate_results()
    sys.exit(0 if result == "all_ok" else 0)  # 总是退出0，避免影响心跳
