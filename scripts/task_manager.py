#!/usr/bin/env python3
"""任务状态管理器 - 支持精确的执行状态机"""
import psycopg2
from datetime import datetime
from typing import Optional, List, Dict

# 执行状态常量
class ExecState:
    NEW = "new"                        # 任务未开始
    ERROR_FIX_PENDING = "error_fix_pending"  # 技术错误，需修复
    NORMAL_CRASH = "normal_crash"      # 客观错误，可重试
    REQUIRES_MANUAL = "requires_manual" # 需人工介入
    PROCESSING = "processing"           # 任务执行中
    END = "end"                        # 任务正常完成

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
            SELECT task_name, display_name, description, status, priority,
                   exec_state, fix_suggestion, last_executed_at, 
                   last_result, last_error, execution_count
            FROM tasks WHERE task_name = %s
        """, (task_name,))
        row = cur.fetchone()
        if row:
            return {
                'task_name': row[0],
                'display_name': row[1],
                'description': row[2],
                'status': row[3],
                'priority': row[4],
                'exec_state': row[5],
                'fix_suggestion': row[6],
                'last_executed_at': row[7],
                'last_result': row[8],
                'last_error': row[9],
                'execution_count': row[10]
            }
        return None
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT task_name, display_name, description, status, priority,
                   exec_state, fix_suggestion, last_executed_at, 
                   last_result, last_error, execution_count
            FROM tasks ORDER BY 
                CASE priority 
                    WHEN 'P0' THEN 1 
                    WHEN 'P1' THEN 2 
                    WHEN 'P2' THEN 3 
                END,
                id
        """)
        tasks = []
        for row in cur.fetchall():
            tasks.append({
                'task_name': row[0],
                'display_name': row[1],
                'description': row[2],
                'status': row[3],
                'priority': row[4],
                'exec_state': row[5],
                'fix_suggestion': row[6],
                'last_executed_at': row[7],
                'last_result': row[8],
                'last_error': row[9],
                'execution_count': row[10]
            })
        return tasks
    
    def get_tasks_by_state(self, exec_state: str) -> List[Dict]:
        """获取指定状态的任务"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT task_name, display_name, description, exec_state, fix_suggestion
            FROM tasks WHERE exec_state = %s
            ORDER BY 
                CASE priority 
                    WHEN 'P0' THEN 1 
                    WHEN 'P1' THEN 2 
                    WHEN 'P2' THEN 3 
                END
        """, (exec_state,))
        return [{'task_name': r[0], 'display_name': r[1], 
                 'description': r[2], 'exec_state': r[3], 'fix_suggestion': r[4]} 
                for r in cur.fetchall()]
    
    def get_actionable_tasks(self) -> List[Dict]:
        """获取需要执行的任务（可自动修复或需要人工介入的）"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT task_name, display_name, exec_state, fix_suggestion
            FROM tasks 
            WHERE exec_state IN ('error_fix_pending', 'normal_crash', 'requires_manual', 'new')
            ORDER BY 
                CASE priority 
                    WHEN 'P0' THEN 1 
                    WHEN 'P1' THEN 2 
                    WHEN 'P2' THEN 3 
                END
        """)
        return [{'task_name': r[0], 'display_name': r[1], 
                'exec_state': r[2], 'fix_suggestion': r[3]} for r in cur.fetchall()]
    
    def update_task(self, task_name: str, **kwargs) -> bool:
        """更新任务字段"""
        if not kwargs:
            return False
        
        # 过滤掉None值
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        if not kwargs:
            return False
        
        set_parts = [f"{k} = %s" for k in kwargs.keys()]
        set_clause = ', '.join(set_parts)
        values = list(kwargs.values())
        
        cur = self.conn.cursor()
        cur.execute(f"""
            UPDATE tasks SET {set_clause}, updated_at = %s
            WHERE task_name = %s
        """, values + [datetime.now(), task_name])
        
        self.conn.commit()
        return cur.rowcount > 0
    
    def set_state(self, task_name: str, exec_state: str, 
                  error: str = None, result: str = None,
                  fix_suggestion: str = None) -> bool:
        """设置任务执行状态"""
        status_map = {
            ExecState.NEW: 'pending',
            ExecState.ERROR_FIX_PENDING: 'failed',
            ExecState.NORMAL_CRASH: 'pending',
            ExecState.REQUIRES_MANUAL: 'failed',
            ExecState.PROCESSING: 'running',
            ExecState.END: 'completed'
        }
        
        kwargs = {
            'exec_state': exec_state,
            'status': status_map.get(exec_state, 'pending'),
            'last_error': error,
            'last_result': result,
            'fix_suggestion': fix_suggestion,
            'last_executed_at': datetime.now()
        }
        
        # 移除None值
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        
        return self.update_task(task_name, **kwargs)
    
    def mark_start(self, task_name: str) -> bool:
        """标记任务开始"""
        return self.set_state(task_name, ExecState.PROCESSING)
    
    def mark_end(self, task_name: str, result: str = "成功") -> bool:
        """标记任务正常完成"""
        return self.set_state(task_name, ExecState.END, result=result)
    
    def mark_error_fix_pending(self, task_name: str, error: str, fix_suggestion: str) -> bool:
        """标记为技术错误，需修复"""
        return self.set_state(task_name, ExecState.ERROR_FIX_PENDING, 
                            error=error, fix_suggestion=fix_suggestion)
    
    def mark_normal_crash(self, task_name: str, error: str) -> bool:
        """标记为客观错误，可重试"""
        return self.set_state(task_name, ExecState.NORMAL_CRASH, error=error)
    
    def mark_requires_manual(self, task_name: str, error: str) -> bool:
        """标记为需人工介入"""
        return self.set_state(task_name, ExecState.REQUIRES_MANUAL, error=error)


def generate_db_report() -> str:
    """生成数据库任务报告"""
    tm = TaskManager()
    tasks = tm.get_all_tasks()
    tm.close()
    
    # 按执行状态分组
    by_state = {}
    for t in tasks:
        state = t['exec_state']
        if state not in by_state:
            by_state[state] = []
        by_state[state].append(t)
    
    state_names = {
        ExecState.NEW: "🆕 新任务",
        ExecState.ERROR_FIX_PENDING: "🔧 待修复",
        ExecState.NORMAL_CRASH: "🔄 可重试",
        ExecState.REQUIRES_MANUAL: "👤 需人工",
        ExecState.PROCESSING: "⚙️ 执行中",
        ExecState.END: "✅ 已完成"
    }
    
    report = []
    report.append("📊 **任务状态总览**")
    report.append("")
    
    total = len(tasks)
    actionable = len(by_state.get(ExecState.ERROR_FIX_PENDING, [])) + \
                 len(by_state.get(ExecState.NORMAL_CRASH, [])) + \
                 len(by_state.get(ExecState.NEW, []))
    
    report.append(f"总计: {total} | 待执行: {actionable}")
    report.append("")
    
    # 按优先级显示
    for state, name in state_names.items():
        if state in by_state:
            items = by_state[state]
            report.append(f"**{name}** ({len(items)})")
            for t in items:
                exec_time = t['last_executed_at'].strftime('%m-%d %H:%M') if t['last_executed_at'] else '从未'
                if state == ExecState.ERROR_FIX_PENDING and t['fix_suggestion']:
                    report.append(f"  • {t['display_name']}")
                    report.append(f"    → {t['fix_suggestion']}")
                elif state == ExecState.REQUIRES_MANUAL:
                    report.append(f"  • {t['display_name']}")
                    report.append(f"    ❌ {t['last_error'][:50] if t['last_error'] else ''}")
                else:
                    report.append(f"  • {t['display_name']} ({exec_time})")
            report.append("")
    
    return '\n'.join(report)

if __name__ == '__main__':
    print(generate_db_report())
