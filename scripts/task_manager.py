#!/usr/bin/env python3
"""任务状态管理器 - 基于数据库的任务跟踪"""
import psycopg2
from datetime import datetime
from typing import Optional, List, Dict

class TaskManager:
    def __init__(self):
        self.conn = psycopg2.connect(
            host='localhost',
            database='ecommerce_data',
            user='superuser',
            password='Admin123!'
        )
    
    def close(self):
        self.conn.close()
    
    def get_task(self, task_name: str) -> Optional[Dict]:
        """获取任务详情"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT task_name, display_name, description, status,
                   last_executed_at, last_result, last_error, execution_count
            FROM tasks WHERE task_name = %s
        """, (task_name,))
        row = cur.fetchone()
        if row:
            return {
                'task_name': row[0],
                'display_name': row[1],
                'description': row[2],
                'status': row[3],
                'last_executed_at': row[4],
                'last_result': row[5],
                'last_error': row[6],
                'execution_count': row[7]
            }
        return None
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT task_name, display_name, description, status,
                   last_executed_at, last_result, last_error, execution_count
            FROM tasks ORDER BY id
        """)
        tasks = []
        for row in cur.fetchall():
            tasks.append({
                'task_name': row[0],
                'display_name': row[1],
                'description': row[2],
                'status': row[3],
                'last_executed_at': row[4],
                'last_result': row[5],
                'last_error': row[6],
                'execution_count': row[7]
            })
        return tasks
    
    def get_pending_tasks(self) -> List[Dict]:
        """获取待执行任务"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT task_name, display_name, description, status
            FROM tasks WHERE status IN ('pending', 'failed')
            ORDER BY id
        """)
        return [{'task_name': r[0], 'display_name': r[1], 'description': r[2], 'status': r[3]} 
                for r in cur.fetchall()]
    
    def update_status(self, task_name: str, status: str, 
                     result: str = None, error: str = None) -> bool:
        """更新任务状态"""
        cur = self.conn.cursor()
        now = datetime.now()
        
        if status == 'running':
            cur.execute("""
                UPDATE tasks SET status = %s, last_executed_at = %s,
                    execution_count = execution_count + 1, updated_at = %s
                WHERE task_name = %s
            """, (status, now, now, task_name))
        else:
            cur.execute("""
                UPDATE tasks SET status = %s, last_result = %s, last_error = %s,
                    updated_at = %s
                WHERE task_name = %s
            """, (status, result, error, now, task_name))
        
        self.conn.commit()
        return cur.rowcount > 0
    
    def mark_running(self, task_name: str) -> bool:
        """标记任务开始执行"""
        return self.update_status(task_name, 'running')
    
    def mark_completed(self, task_name: str, result: str = "成功") -> bool:
        """标记任务完成"""
        return self.update_status(task_name, 'completed', result=result)
    
    def mark_failed(self, task_name: str, error: str) -> bool:
        """标记任务失败"""
        return self.update_status(task_name, 'failed', error=error)

def generate_db_report() -> str:
    """生成数据库任务报告"""
    tm = TaskManager()
    tasks = tm.get_all_tasks()
    tm.close()
    
    pending = [t for t in tasks if t['status'] in ('pending', 'failed')]
    running = [t for t in tasks if t['status'] == 'running']
    completed = [t for t in tasks if t['status'] == 'completed']
    
    report = []
    report.append(f"📊 **任务状态总览** ({len(completed)}/{len(tasks)})")
    report.append("")
    
    if pending:
        report.append("⬜ **待执行/失败**")
        for t in pending:
            exec_time = t['last_executed_at'].strftime('%m-%d %H:%M') if t['last_executed_at'] else '从未执行'
            err_info = f" ❌ {t['last_error'][:30]}" if t['last_error'] else ""
            report.append(f"  • {t['display_name']} ({exec_time}){err_info}")
        report.append("")
    
    if running:
        report.append("🔄 **执行中**")
        for t in running:
            report.append(f"  • {t['display_name']}")
        report.append("")
    
    if completed:
        report.append("✅ **已完成**")
        for t in completed:
            exec_time = t['last_executed_at'].strftime('%m-%d %H:%M') if t['last_executed_at'] else ''
            report.append(f"  • {t['display_name']} ({exec_time})")
    
    return '\n'.join(report)

if __name__ == '__main__':
    print(generate_db_report())
