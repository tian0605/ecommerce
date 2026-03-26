#!/usr/bin/env python3
"""任务状态管理器 - 支持多级任务结构"""
import psycopg2
from psycopg2 import sql
from datetime import datetime
from typing import List, Dict, Optional
import json

class TaskManager:
    def __init__(self):
        self.DB_CONFIG = {
            'host': 'localhost',
            'database': 'ecommerce_data',
            'user': 'superuser',
            'password': 'Admin123!'
        }
        self.conn = psycopg2.connect(**self.DB_CONFIG)
    
    def close(self):
        self.conn.close()
    
    # ========== 基础CRUD ==========
    def get_task(self, task_name: str) -> Optional[Dict]:
        """获取单个任务"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_name = %s", (task_name,))
        row = cur.fetchone()
        if not row:
            return None
        
        cols = [desc[0] for desc in cur.description]
        task = dict(zip(cols, row))
        cur.close()
        return task
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM tasks ORDER BY task_level, priority, created_at")
        cols = [desc[0] for desc in cur.description]
        tasks = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        return tasks
    
    def get_tasks_by_state(self, exec_state: str) -> List[Dict]:
        """按执行状态获取任务"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE exec_state = %s", (exec_state,))
        cols = [desc[0] for desc in cur.description]
        tasks = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        return tasks
    
    # ========== 新增：层级任务查询 ==========
    def get_root_tasks(self) -> List[Dict]:
        """获取父任务（task_level=1）"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM tasks 
            WHERE task_level = 1 
            ORDER BY priority, created_at
        """)
        cols = [desc[0] for desc in cur.description]
        tasks = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        return tasks
    
    def get_sub_tasks(self, parent_task_id: str) -> List[Dict]:
        """获取子任务"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM tasks 
            WHERE parent_task_id = %s 
            ORDER BY priority, created_at
        """, (parent_task_id,))
        cols = [desc[0] for desc in cur.description]
        tasks = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        return tasks
    
    def get_actionable_tasks(self) -> List[Dict]:
        """获取可执行的任务（优先子任务，再父任务）"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM tasks 
            WHERE exec_state IN ('error_fix_pending', 'normal_crash', 'requires_manual', 'new')
            ORDER BY 
                task_level DESC,  -- 优先处理子任务(level 2)
                CASE priority 
                    WHEN 'P0' THEN 1 
                    WHEN 'P1' THEN 2 
                    WHEN 'P2' THEN 3 
                END,
                created_at
        """)
        cols = [desc[0] for desc in cur.description]
        tasks = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        return tasks
    
    # ========== 状态更新 ==========
    def update_task(self, task_name: str, **kwargs):
        """更新任务字段"""
        if not kwargs:
            return
        
        kwargs['updated_at'] = datetime.now()
        set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
        values = list(kwargs.values()) + [task_name]
        
        cur = self.conn.cursor()
        cur.execute(f"UPDATE tasks SET {set_clause} WHERE task_name = %s", values)
        self.conn.commit()
        cur.close()
    
    def mark_start(self, task_name: str):
        """标记任务开始"""
        self.update_task(task_name,
            status='running',
            exec_state='processing',
            last_executed_at=datetime.now(),
            execution_count=psycopg2.sql.SQL("COALESCE(execution_count, 0) + 1")
        )
    
    def mark_end(self, task_name: str, result: str = "成功"):
        """标记任务完成"""
        self.update_task(task_name,
            status='completed',
            exec_state='end',
            last_result=result
        )
    
    def mark_error_fix_pending(self, task_name: str, error: str, fix: str = ""):
        """标记需要修复"""
        self.update_task(task_name,
            status='failed',
            exec_state='error_fix_pending',
            last_error=error,
            fix_suggestion=fix
        )
    
    def mark_requires_manual(self, task_name: str, reason: str = ""):
        """标记需要人工介入"""
        self.update_task(task_name,
            status='failed',
            exec_state='requires_manual',
            last_error=reason
        )
    
    def mark_normal_crash(self, task_name: str, error: str = ""):
        """标记正常崩溃（可重试）"""
        self.update_task(task_name,
            status='pending',
            exec_state='normal_crash',
            last_error=error
        )
    
    # ========== 子任务管理 ==========
    def create_sub_task(self, parent_task_id: str, task_name: str, display_name: str, 
                       description: str = "", priority: str = "P0", 
                       fix_suggestion: str = "") -> bool:
        """创建子任务"""
        # 获取父任务信息
        parent = self.get_task(parent_task_id)
        if not parent:
            return False
        
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO tasks (
                task_name, display_name, description, 
                priority, status, exec_state, fix_suggestion,
                parent_task_id, task_level, root_task_id,
                execution_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
            ON CONFLICT (task_name) DO NOTHING
        """, (
            task_name, display_name, description,
            priority, 'pending', 'new', fix_suggestion,
            parent_task_id, 2, parent.get('root_task_id') or parent_task_id
        ))
        self.conn.commit()
        cur.close()
        return True
    
    # ========== 便捷查询 ==========
    def get_task_tree(self) -> Dict:
        """获取任务树结构"""
        roots = self.get_root_tasks()
        tree = []
        
        for root in roots:
            node = {
                **root,
                'children': self.get_sub_tasks(root['task_name'])
            }
            tree.append(node)
        
        return tree
    
    def reset_task(self, task_name: str, exec_state: str = 'new', 
                   status: str = 'pending', error: str = None, fix: str = None):
        """重置任务状态"""
        self.update_task(task_name,
            exec_state=exec_state,
            status=status,
            last_error=error,
            fix_suggestion=fix
        )

if __name__ == '__main__':
    tm = TaskManager()
    
    # 打印任务树
    tree = tm.get_task_tree()
    print("📋 任务树:")
    for root in tree:
        print(f"  {'[P0]' if root['priority'] == 'P0' else '[P1]'} {root['display_name']} ({root['exec_state']})")
        for child in root.get('children', []):
            print(f"      └── {child['display_name']} ({child['exec_state']})")
    
    tm.close()
