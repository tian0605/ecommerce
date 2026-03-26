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
    
    def get_actionable_tasks(self, limit: int = 2) -> List[Dict]:
        """获取可执行的任务（优先P0，再子任务，最多返回limit个）
        
        父任务（level=1）只有在其所有子任务都完成（end或void）时才返回
        """
        cur = self.conn.cursor()
        
        # 先获取所有可执行的任务
        cur.execute("""
            SELECT * FROM tasks 
            WHERE exec_state IN ('error_fix_pending', 'normal_crash', 'new')
            ORDER BY 
                CASE priority 
                    WHEN 'P0' THEN 1 
                    WHEN 'P1' THEN 2 
                    WHEN 'P2' THEN 3 
                END,
                task_level DESC,
                created_at
            LIMIT %s
        """, (limit * 3,))  # 多取一些，后面过滤
        
        cols = [desc[0] for desc in cur.description]
        all_tasks = [dict(zip(cols, row)) for row in cur.fetchall()]
        
        # 过滤：排除父任务如果它还有未完成的子任务
        result = []
        for task in all_tasks:
            if task.get('task_level') == 2:
                # 子任务：只有 requires_manual 才跳过（需要人工介入）
                if task.get('exec_state') != 'requires_manual':
                    result.append(task)
            else:
                # 父任务：检查子任务是否都完成
                cur.execute("""
                    SELECT COUNT(*) FROM tasks 
                    WHERE parent_task_id = %s 
                    AND exec_state NOT IN ('end', 'void', 'requires_manual')
                """, (task['task_name'],))
                pending_count = cur.fetchone()[0]
                
                if pending_count == 0:
                    # 所有子任务都完成了，可以执行父任务
                    result.append(task)
                # else: 还有子任务未完成（包括 requires_manual），跳过父任务
        
        cur.close()
        return result[:limit]
    
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
        """标记任务开始，增加重试计数"""
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE tasks 
            SET status = %s, 
                exec_state = %s, 
                last_executed_at = %s,
                execution_count = COALESCE(execution_count, 0) + 1,
                retry_count = COALESCE(retry_count, 0) + 1,
                updated_at = %s
            WHERE task_name = %s
        """, ('running', 'processing', datetime.now(), datetime.now(), task_name))
        self.conn.commit()
        cur.close()
    
    def mark_end(self, task_name: str, result: str = "成功"):
        """标记任务完成"""
        self.update_task(task_name,
            status='completed',
            exec_state='end',
            last_result=result
        )
    
    def mark_error_fix_pending(self, task_name: str, error: str, fix: str = ""):
        """标记需要修复（单个错误，单个子任务）"""
        self.update_task(task_name,
            status='failed',
            exec_state='error_fix_pending',
            last_error=error,
            fix_suggestion=fix
        )
        # 自动创建一个子任务
        self.create_fix_subtask(task_name, error, fix)
    
    def mark_void(self, task_name: str, reason: str = ""):
        """标记任务为作废"""
        self.update_task(task_name,
            status='voided',
            exec_state='void',
            is_void=True
        )

    def create_fix_subtasks(self, task_name: str, errors: list):
        """批量创建修复子任务（多个错误）- 含成功标准
        
        如果对应的子任务已存在（且状态为end），则重新创建新的子任务
        """
        # 获取现有子任务
        existing_subs = self.get_sub_tasks(task_name)
        existing_names = {sub['display_name'].replace('修复: ', '').strip() for sub in existing_subs}
        
        sub_count = len(existing_subs)
        
        for error_info in errors:
            if isinstance(error_info, dict):
                error_msg = error_info.get('error', str(error_info))
                fix_suggestion = error_info.get('fix', '')
                success_criteria = error_info.get('success_criteria', f"修复{error_msg[:30]}成功")
                analysis = error_info.get('analysis', '')
                plan = error_info.get('plan', '')
            else:
                error_msg = str(error_info)
                fix_suggestion = ''
                success_criteria = f"修复{error_msg[:30]}成功"
                analysis = ''
                plan = ''
            
            # 检查是否已存在对应的子任务
            short_error = error_msg[:50]
            
            # 生成新的子任务名（避免与现有冲突）
            sub_count += 1
            sub_task_name = f"FIX-{task_name}-{sub_count:03d}"
            display_name = f"修复: {short_error}"
            
            # 创建子任务
            self.create_sub_task(
                parent_task_id=task_name,
                task_name=sub_task_name,
                display_name=display_name,
                description=f"错误: {error_msg}",
                priority='P0',
                fix_suggestion=fix_suggestion
            )
            
            # 更新成功标准和分析
            self.update_task(sub_task_name,
                success_criteria=success_criteria,
                analysis=analysis,
                plan=plan
            )
        
        # 更新父任务状态
        error_summary = f"共{len(errors)}个问题"
        self.update_task(task_name,
            status='failed',
            exec_state='error_fix_pending',
            last_error=error_summary,
            fix_suggestion=f"已创建{len(errors)}个子任务"
        )
    
    def mark_void(self, task_name: str, reason: str = ""):
        """标记任务为作废"""
        self.update_task(task_name,
            status='voided',
            exec_state='void',
            is_void=True
        )

    def create_fix_subtask(self, task_name: str, error: str, fix: str = ""):
        """创建单个修复子任务"""
        sub_task_name = f"FIX-{task_name}-001"
        display_name = f"修复: {error[:50]}"
        
        self.create_sub_task(
            parent_task_id=task_name,
            task_name=sub_task_name,
            display_name=display_name,
            description=f"错误: {error}",
            priority='P0',
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
