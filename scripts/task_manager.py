#!/usr/bin/env python3
"""任务状态管理器 - 支持多级任务结构"""
import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json
from datetime import datetime
from typing import List, Dict, Optional
import hashlib
import json
import re

class TaskManager:
    def __init__(self):
        self.DB_CONFIG = {
            'host': 'localhost',
            'database': 'ecommerce_data',
            'user': 'superuser',
            'password': 'Admin123!'
        }
        self.conn = psycopg2.connect(**self.DB_CONFIG)
        self._ensure_schema()

    def _ensure_schema(self):
        """确保 tasks 表包含调度和反馈审计所需字段。"""
        cur = self.conn.cursor()
        statements = [
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS notification_status TEXT DEFAULT 'pending'",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS notification_attempts INTEGER DEFAULT 0",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS notification_success_count INTEGER DEFAULT 0",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS notification_failure_count INTEGER DEFAULT 0",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS notification_last_event TEXT",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS notification_last_message TEXT",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS notification_last_error TEXT",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS notification_last_attempt_at TIMESTAMP",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS notification_last_sent_at TIMESTAMP",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS notification_audit JSONB DEFAULT '[]'::jsonb",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS feedback_doc_url TEXT",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS feedback_markdown_file TEXT",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS error_signature TEXT",
        ]
        for statement in statements:
            cur.execute(statement)
        self.conn.commit()
        cur.close()

    def _normalize_error_signature(self, error: str, fix: str = "") -> str:
        text = f"{error}\n{fix}".strip().lower()
        text = re.sub(r"\s+", " ", text)
        return hashlib.sha1(text.encode('utf-8')).hexdigest()

    def _next_fix_subtask_name(self, parent_task_name: str) -> str:
        existing = self.get_sub_tasks(parent_task_name)
        max_suffix = 0
        pattern = re.compile(rf"^FIX-{re.escape(parent_task_name)}-(\d+)$")
        for task in existing:
            match = pattern.match(task.get('task_name', ''))
            if match:
                max_suffix = max(max_suffix, int(match.group(1)))
        return f"FIX-{parent_task_name}-{max_suffix + 1:03d}"

    def _find_open_fix_subtask(self, parent_task_name: str, error_signature: str) -> Optional[Dict]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT * FROM tasks
            WHERE parent_task_id = %s
              AND task_type = '修复'
              AND error_signature = %s
              AND exec_state NOT IN ('end', 'void')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (parent_task_name, error_signature),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            return None

        cols = [desc[0] for desc in cur.description]
        task = dict(zip(cols, row))
        cur.close()
        return task

    def record_notification(self, task_name: str, event: str, message: str,
                            success: bool, error: str = None,
                            metadata: dict = None) -> bool:
        """记录任务通知审计信息，便于统计与追责。"""
        task = self.get_task(task_name)
        if not task:
            return False

        now = datetime.now()
        audit = task.get('notification_audit') or []
        if isinstance(audit, str):
            try:
                audit = json.loads(audit)
            except Exception:
                audit = []

        entry = {
            'event': event,
            'success': success,
            'message': message,
            'error': error,
            'timestamp': now.isoformat(),
            'metadata': metadata or {},
        }
        audit.append(entry)
        audit = audit[-50:]

        self.update_task(
            task_name,
            notification_status='success' if success else 'failed',
            notification_attempts=(task.get('notification_attempts') or 0) + 1,
            notification_success_count=(task.get('notification_success_count') or 0) + (1 if success else 0),
            notification_failure_count=(task.get('notification_failure_count') or 0) + (0 if success else 1),
            notification_last_event=event,
            notification_last_message=message,
            notification_last_error=error,
            notification_last_attempt_at=now,
            notification_last_sent_at=now if success else task.get('notification_last_sent_at'),
            notification_audit=Json(audit),
        )
        return True

    def record_feedback_artifacts(self, task_name: str, doc_url: str = None,
                                  markdown_file: str = None) -> bool:
        if not self.get_task(task_name):
            return False
        payload = {}
        if doc_url:
            payload['feedback_doc_url'] = doc_url
        if markdown_file:
            payload['feedback_markdown_file'] = markdown_file
        if not payload:
            return False
        self.update_task(task_name, **payload)
        return True
    
    def close(self):
        self.conn.close()
    
    def on_task_success(self, task_name: str):
        """当任务成功时，更新文档形成长久记忆
        
        自动提取成功经验并更新：
        - skills/*/SKILL.md（相关技能文档）
        - docs/KNOWLEDGE.md（知识库）
        - docs/AGENTS.md（智能执行标准）
        """
        import os
        import json
        from datetime import datetime
        
        task = self.get_task(task_name)
        if not task:
            return
        
        workspace = '/root/.openclaw/workspace-e-commerce'
        success_record = {
            'task_name': task_name,
            'display_name': task.get('display_name', ''),
            'success_criteria': task.get('success_criteria', ''),
            'completed_at': datetime.now().isoformat(),
            'description': task.get('description', '')
        }
        
        # 1. 更新 docs/KNOWLEDGE.md
        knowledge_file = f'{workspace}/docs/KNOWLEDGE.md'
        if os.path.exists(knowledge_file):
            with open(knowledge_file, 'r') as f:
                content = f.read()
            
            # 在文件开头添加成功记录
            new_entry = f"""
## {task_name} - {task.get('display_name', '')}
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**成功标准**: {task.get('success_criteria', '')}
**描述**: {task.get('description', '')}

"""
            with open(knowledge_file, 'w') as f:
                f.write(new_entry + content)
        
        # 2. 如果是父任务，更新 AGENTS.md
        if task.get('task_level') == 1:
            agents_file = f'{workspace}/docs/AGENTS.md'
            if os.path.exists(agents_file):
                with open(agents_file, 'r') as f:
                    content = f.read()
                
                # 在成功案例部分添加记录
                new_entry = f"""
### {task_name} ({datetime.now().strftime('%Y-%m-%d')})
**描述**: {task.get('description', '')}
**成功标准**: {task.get('success_criteria', '')}
**关键执行参数**: 待补充

"""
                # 找到"成功案例"部分并插入
                if '## 成功案例' in content:
                    content = content.replace(
                        '## 成功案例',
                        f'## 成功案例{new_entry}'
                    )
                    with open(agents_file, 'w') as f:
                        f.write(content)
        
        print(f"✅ 已更新长久记忆: {task_name}")    
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
        """获取可执行的任务（修复类 > 常规类，优先P0，再子任务，最多返回limit个）
        
        优先级顺序：
        1. 修复类任务（task_type='修复'）- 优先处理机制问题
        2. 常规类任务（task_type='常规'）- 正常业务流程
        3. 创造类任务（task_type='创造'）- 最低优先级
        
        父任务（level=1）只有在其所有子任务都完成（end或void）时才返回
        """
        cur = self.conn.cursor()
        
        # 先获取所有可执行的任务
        # 修复类任务优先于临时任务，临时任务优先于常规类和创造类
        cur.execute("""
            SELECT * FROM tasks 
            WHERE exec_state IN ('error_fix_pending', 'normal_crash', 'new')
            ORDER BY 
                CASE task_type 
                    WHEN '修复' THEN 1 
                    WHEN '临时任务' THEN 2
                    WHEN '常规' THEN 3 
                    WHEN '创造' THEN 4 
                    ELSE 5
                END,
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
        """标记任务开始，增加重试计数（不更新last_executed_at，避免重置卡死检测）"""
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE tasks 
            SET status = %s, 
                exec_state = %s, 
                execution_count = COALESCE(execution_count, 0) + 1,
                retry_count = COALESCE(retry_count, 0) + 1,
                updated_at = %s
            WHERE task_name = %s
        """, ('running', 'processing', datetime.now(), task_name))
        self.conn.commit()
        cur.close()
    
    def mark_executing(self, task_name: str):
        """标记任务真正开始执行（更新last_executed_at）"""
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE tasks 
            SET last_executed_at = %s,
                updated_at = %s
            WHERE task_name = %s
        """, (datetime.now(), datetime.now(), task_name))
        self.conn.commit()
        cur.close()
    
    def mark_end(self, task_name: str, result: str = "成功"):
        """标记任务完成"""
        self.update_task(task_name,
            status='completed',
            exec_state='end',
            last_result=result
        )
    
    def skip_task(self, task_name: str, reason: str = "跳过"):
        """标记任务跳过"""
        self.update_task(task_name,
            status='skipped',
            exec_state='end',
            last_result=reason
        )
    
    def validate_parent_completion(self, parent_task_name: str):
        """验证父任务是否所有子任务都完成
        
        如果所有子任务都完成（end/void），则标记父任务为完成
        """
        children = self.get_sub_tasks(parent_task_name)
        if not children:
            return False
        
        all_completed = all(c['exec_state'] in ('end', 'void') for c in children)
        
        if all_completed:
            # 所有子任务完成，标记父任务完成
            self.update_task(parent_task_name,
                status='completed',
                exec_state='end',
                last_result='所有子任务执行完成'
            )
            print(f"  [workflow] 父任务 {parent_task_name} 验证完成")
            return True
        else:
            # 还有子任务未完成
            pending = [c['display_name'] for c in children if c['exec_state'] not in ('end', 'void')]
            print(f"  [workflow] 父任务 {parent_task_name} 还有未完成子任务: {pending}")
            return False
    
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
        
        task_type=修复，优先级高于常规任务
        """
        # 获取父任务信息
        parent = self.get_task(task_name)
        if not parent:
            return
        
        # 获取现有子任务
        seen_signatures = set()
        
        created_count = 0

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

            error_signature = self._normalize_error_signature(error_msg, fix_suggestion)
            if error_signature in seen_signatures:
                continue
            seen_signatures.add(error_signature)

            existing = self._find_open_fix_subtask(task_name, error_signature)
            if existing:
                self.update_task(
                    existing['task_name'],
                    last_error=error_msg,
                    fix_suggestion=fix_suggestion or existing.get('fix_suggestion'),
                )
                continue

            short_error = error_msg[:50]
            sub_task_name = self._next_fix_subtask_name(task_name)
            display_name = f"修复: {short_error}"
            
            # 创建子任务（task_type=修复）
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO tasks (
                    task_name, display_name, description, 
                    priority, status, exec_state, fix_suggestion,
                    parent_task_id, task_level, root_task_id,
                    execution_count, task_type,
                    success_criteria, analysis, plan, error_signature
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, '修复', %s, %s, %s, %s)
                ON CONFLICT (task_name) DO NOTHING
            """, (
                sub_task_name, display_name, f"错误: {error_msg}",
                'P0', 'pending', 'new', fix_suggestion,
                task_name, 2, parent.get('root_task_id') or task_name,
                success_criteria, analysis, plan, error_signature
            ))
            self.conn.commit()
            cur.close()
            created_count += 1
        
        # 更新父任务状态
        error_summary = f"共{len(errors)}个问题，新增{created_count}个修复子任务"
        self.update_task(task_name,
            status='failed',
            exec_state='error_fix_pending',
            last_error=error_summary,
            fix_suggestion=f"已创建{created_count}个子任务（重复错误已去重）"
        )
    
    def mark_void(self, task_name: str, reason: str = ""):
        """标记任务为作废"""
        self.update_task(task_name,
            status='voided',
            exec_state='void',
            is_void=True
        )

    def create_fix_subtask(self, task_name: str, error: str, fix: str = ""):
        """创建单个修复子任务（task_type=修复）"""
        # 获取父任务信息
        parent = self.get_task(task_name)
        if not parent:
            return False

        error_signature = self._normalize_error_signature(error, fix)
        existing = self._find_open_fix_subtask(task_name, error_signature)
        if existing:
            self.update_task(
                existing['task_name'],
                last_error=error,
                fix_suggestion=fix or existing.get('fix_suggestion'),
            )
            return True

        sub_task_name = self._next_fix_subtask_name(task_name)
        display_name = f"修复: {error[:50]}"
        
        # 修复子任务直接设置 task_type='修复'
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO tasks (
                task_name, display_name, description, 
                priority, status, exec_state, fix_suggestion,
                parent_task_id, task_level, root_task_id,
                execution_count, task_type, error_signature
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, '修复', %s)
            ON CONFLICT (task_name) DO NOTHING
        """, (
            sub_task_name, display_name, f"错误: {error}",
            'P0', 'pending', 'new', fix,
            task_name, 2, parent.get('root_task_id') or task_name, error_signature
        ))
        self.conn.commit()
        cur.close()
        return True
    
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
        """创建子任务（自动继承父任务的task_type）"""
        # 获取父任务信息
        parent = self.get_task(parent_task_id)
        if not parent:
            return False
        
        # 子任务继承父任务的task_type
        task_type = parent.get('task_type', '常规')
        
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO tasks (
                task_name, display_name, description, 
                priority, status, exec_state, fix_suggestion,
                parent_task_id, task_level, root_task_id,
                execution_count, task_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s)
            ON CONFLICT (task_name) DO NOTHING
        """, (
            task_name, display_name, description,
            priority, 'pending', 'new', fix_suggestion,
            parent_task_id, 2, parent.get('root_task_id') or parent_task_id,
            task_type
        ))
        self.conn.commit()
        cur.close()
        return True
    
    def create_task(self, task_name: str, display_name: str, 
                   task_type: str = "常规", description: str = "",
                   priority: str = "P1", success_criteria: str = "") -> bool:
        """创建父任务（level=1）
        
        Args:
            task_name: 任务名称
            display_name: 显示名称
            task_type: 任务类型 ['常规'|'修复'|'创造']
            description: 任务描述
            priority: 优先级 ['P0'|'P1'|'P2']
            success_criteria: 成功标准
        """
        if task_type not in ('常规', '修复', '创造'):
            task_type = '常规'
        
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO tasks (
                task_name, display_name, description, 
                priority, status, exec_state, 
                task_level, execution_count, task_type,
                success_criteria
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s)
            ON CONFLICT (task_name) DO NOTHING
        """, (
            task_name, display_name, description,
            priority, 'pending', 'new',
            1, task_type, success_criteria
        ))
        self.conn.commit()
        cur.close()
        return True

    # ========== 临时任务（TEMP）支持 ==========
    def create_temp_task(self, task_name: str, display_name: str,
                        description: str = "", expected_duration: int = 60,
                        priority: str = "P1", success_criteria: str = "",
                        initial_checkpoint: dict = None) -> bool:
        """
        创建临时任务（task_type='临时任务'）
        
        临时任务特点：
        - 开放式的执行方式，由agent自主决定怎么执行
        - 支持断点续传（progress_checkpoint）
        - 超时后心跳会重新激活继续执行
        
        Args:
            task_name: 任务名称
            display_name: 显示名称
            description: 任务描述
            expected_duration: 预设完成时间（分钟）
            priority: 优先级 ['P0'|'P1'|'P2']
            success_criteria: 成功标准
            initial_checkpoint: 初始断点数据（dict）
        
        Returns:
            bool: 是否创建成功
        """
        from datetime import datetime
        
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO tasks (
                task_name, display_name, description, 
                priority, status, exec_state, 
                task_level, execution_count, task_type,
                success_criteria, expected_duration,
                last_executed_at, progress_checkpoint
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s, %s, %s, %s)
            ON CONFLICT (task_name) DO NOTHING
        """, (
            task_name, display_name, description,
            priority, 'pending', 'new',
            1, '临时任务', success_criteria,
            expected_duration, None,
            json.dumps(initial_checkpoint) if initial_checkpoint else None
        ))
        self.conn.commit()
        cur.close()
        return True
    
    def update_checkpoint(self, task_name: str, checkpoint: dict):
        """
        更新任务断点信息
        
        Args:
            task_name: 任务名称
            checkpoint: 断点数据（dict），包含：
                - current_step: 当前步骤
                - completed_steps: 已完成步骤列表
                - output_data: 输出数据
                - next_action: 下一步动作
                - notes: 备注
        """
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE tasks 
            SET progress_checkpoint = %s,
                last_executed_at = %s,
                updated_at = %s
            WHERE task_name = %s
        """, (
            json.dumps(checkpoint),
            datetime.now(),
            datetime.now(),
            task_name
        ))
        self.conn.commit()
        cur.close()
        print(f"  [checkpoint] 已更新: {task_name}")
    
    def get_checkpoint(self, task_name: str) -> dict:
        """获取任务断点信息"""
        task = self.get_task(task_name)
        if not task:
            return None
        cp = task.get('progress_checkpoint')
        if isinstance(cp, str):
            try:
                return json.loads(cp)
            except:
                return None
        return cp
    
    def get_overtime_temp_tasks(self, buffer_minutes: int = 10) -> List[Dict]:
        """
        获取超时未完成的临时任务
        
        Args:
            buffer_minutes: 宽限时间（分钟），超过预设时间+宽限才算超时
        
        Returns:
            超时的临时任务列表
        """
        from datetime import datetime, timedelta
        
        cur = self.conn.cursor()
        overtime_threshold = datetime.now() - timedelta(minutes=buffer_minutes)
        
        cur.execute("""
            SELECT * FROM tasks 
            WHERE task_type = '临时任务'
            AND exec_state = 'processing'
            AND last_executed_at IS NOT NULL
            AND last_executed_at < %s
            AND expected_duration IS NOT NULL
            ORDER BY last_executed_at ASC
        """, (overtime_threshold,))
        
        cols = [desc[0] for desc in cur.description]
        tasks = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        
        # 进一步过滤：只返回真正超时的（last_executed_at + expected_duration + buffer < now）
        now = datetime.now()
        overtime_tasks = []
        for task in tasks:
            if task['last_executed_at'] and task['expected_duration']:
                expected_end = task['last_executed_at'] + timedelta(
                    minutes=task['expected_duration'] + buffer_minutes
                )
                if expected_end < now:
                    task['overtime_minutes'] = (now - expected_end).total_seconds() / 60
                    overtime_tasks.append(task)
        
        return overtime_tasks
    
    def reactivate_temp_task(self, task_name: str) -> bool:
        """
        重新激活超时的临时任务
        
        将任务从 processing 状态重置为 new，使其可以被重新执行
        
        Args:
            task_name: 任务名称
        
        Returns:
            bool: 是否成功
        """
        task = self.get_task(task_name)
        if not task:
            return False
        
        if task.get('task_type') != '临时任务':
            return False
        
        # 重置为 new 状态，保留 progress_checkpoint
        self.update_task(task_name,
            exec_state='new',
            status='pending',
            last_error=None,  # 清除错误
            fix_suggestion=f"超时自动重置，上次checkpoint已保留"
        )
        print(f"  [reactivate] 已重置超时任务: {task_name}")
        return True
    
    def get_temp_tasks(self, limit: int = 5) -> List[Dict]:
        """获取所有临时任务（包含超时的）"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM tasks 
            WHERE task_type = '临时任务'
            AND exec_state NOT IN ('end', 'void')
            ORDER BY 
                CASE exec_state WHEN 'processing' THEN 1 WHEN 'new' THEN 2 ELSE 3 END,
                created_at DESC
            LIMIT %s
        """, (limit,))
        cols = [desc[0] for desc in cur.description]
        tasks = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        return tasks
    
    def create_temp_task_with_notification(self, task_name: str, display_name: str,
                                        description: str = "", expected_duration: int = 60,
                                        priority: str = "P1", success_criteria: str = "",
                                        initial_checkpoint: dict = None) -> dict:
        """
        创建临时任务并立即发送飞书通知（原子操作）
        
        Returns:
            dict: {'task_name': str, 'notification_sent': bool}
        """
        from notification_service import send_feishu_text
        
        # 1. 创建任务
        self.create_temp_task(
            task_name=task_name,
            display_name=display_name,
            description=description,
            expected_duration=expected_duration,
            priority=priority,
            success_criteria=success_criteria,
            initial_checkpoint=initial_checkpoint
        )
        
        # 2. 发送飞书通知
        notification_sent = False
        notification_error = None
        try:
            message = f"""🔔 **临时任务已创建**

任务ID: {task_name}
描述: {description}
预计完成: {expected_duration}分钟
状态: 已创建，等待调度执行

完成后将通知你。"""
            notification_sent = send_feishu_text(message)
        except Exception as e:
            print(f"飞书通知发送失败: {e}")
            notification_error = str(e)

        self.record_notification(
            task_name=task_name,
            event='temp_task_created',
            message=message,
            success=notification_sent,
            error=notification_error if not notification_sent else None,
            metadata={'expected_duration': expected_duration},
        )
        
        return {
            'task_name': task_name,
            'notification_sent': notification_sent
        }
    
    def get_pending_temp_instructions(self) -> List[dict]:
        """获取所有待处理的临时任务指令文件"""
        import os
        import json
        
        pending_dir = Path('/root/.openclaw/workspace-e-commerce/logs')
        pending_files = list(pending_dir.glob('pending_temp_*.json'))
        
        results = []
        for pf in pending_files:
            try:
                with open(pf, 'r') as f:
                    data = json.load(f)
                    results.append(data)
            except Exception as e:
                print(f"读取待处理文件失败 {pf}: {e}")
        
        return results

    def create_workflow_task(self, task_name: str, display_name: str,
                            description: str = "", priority: str = "P0",
                            success_criteria: str = "",
                            steps: list = None) -> bool:
        """
        创建工作流任务（父任务+常规类型子任务）

        专门用于创建自动化工作流任务，如：采集→提取→落库→优化→发布

        Args:
            task_name: 任务名称
            display_name: 显示名称
            description: 任务描述
            priority: 优先级 ['P0'|'P1'|'P2']
            success_criteria: 成功标准
            steps: 步骤列表，每项为 dict:
                {
                    'step_name': 'Step1',
                    'display_name': '采集认领',
                    'description': '使用miaoshou-collector采集',
                    'fix': '调用 miaoshou-collector 技能',
                    'success_criteria': '商品进入采集箱'
                }

        Returns:
            bool: 是否创建成功
        """
        # 创建父任务（task_type='常规'）
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO tasks (
                task_name, display_name, description,
                priority, status, exec_state,
                task_level, execution_count, task_type,
                success_criteria
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s)
            ON CONFLICT (task_name) DO NOTHING
        """, (
            task_name, display_name, description,
            priority, 'pending', 'new',
            1, '常规', success_criteria
        ))
        self.conn.commit()
        cur.close()

        # 如果没有步骤，返回成功
        if not steps:
            return True

        # 创建子任务（task_type='常规'）
        for i, step in enumerate(steps):
            step_name = step.get('step_name', f'{task_name}-STEP{i+1:02d}')
            step_display = step.get('display_name', f'Step{i+1}')
            step_desc = step.get('description', '')
            step_fix = step.get('fix', '')
            step_success = step.get('success_criteria', f'Step{i+1}完成')

            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO tasks (
                    task_name, display_name, description,
                    priority, status, exec_state, fix_suggestion,
                    parent_task_id, task_level, root_task_id,
                    execution_count, task_type,
                    success_criteria
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s)
                ON CONFLICT (task_name) DO NOTHING
            """, (
                step_name, step_display, step_desc,
                priority, 'pending', 'new', step_fix,
                task_name, 2, task_name,
                '常规', step_success
            ))
            self.conn.commit()
            cur.close()

            print(f"  创建工作流步骤: {step_display} ({step_name})")

        return True

    def create_workflow_steps(self, parent_task_id: str, steps: list, priority: str = "P0") -> bool:
        """
        为已有父任务创建工作流子任务（task_type='常规')

        Args:
            parent_task_id: 父任务ID
            steps: 步骤列表，每项为 dict:
                {
                    'step_name': 'STEP1',
                    'display_name': 'Step1: 采集认领',
                    'description': '使用miaoshou-collector采集',
                    'fix': '调用 miaoshou-collector 技能',
                    'success_criteria': '商品进入采集箱'
                }
            priority: 优先级

        Returns:
            bool: 是否创建成功
        """
        parent = self.get_task(parent_task_id)
        if not parent:
            print(f"父任务不存在: {parent_task_id}")
            return False

        for i, step in enumerate(steps):
            step_name = step.get('step_name', f'{parent_task_id}-STEP{i+1:02d}')
            step_display = step.get('display_name', f'Step{i+1}')
            step_desc = step.get('description', '')
            step_fix = step.get('fix', '')
            step_success = step.get('success_criteria', f'Step{i+1}完成')

            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO tasks (
                    task_name, display_name, description,
                    priority, status, exec_state, fix_suggestion,
                    parent_task_id, task_level, root_task_id,
                    execution_count, task_type,
                    success_criteria
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s)
                ON CONFLICT (task_name) DO NOTHING
            """, (
                step_name, step_display, step_desc,
                priority, 'pending', 'new', step_fix,
                parent_task_id, 2, parent.get('root_task_id') or parent_task_id,
                '常规', step_success
            ))
            self.conn.commit()
            cur.close()

            print(f"  创建工作流步骤: {step_display}")

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

    # ========== Workflow Data 数据传递 ==========
    def save_workflow_data(self, workflow_id: str, step_name: str, data: dict):
        """保存步骤输出数据到workflow_data表"""
        import json
        cur = self.conn.cursor()
        for key, value in data.items():
            if value is not None:
                cur.execute("""
                    INSERT INTO workflow_data (workflow_id, step_name, data_key, data_value)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (workflow_id, step_name, data_key)
                    DO UPDATE SET data_value = EXCLUDED.data_value
                """, (workflow_id, step_name, key, json.dumps(value)))
        self.conn.commit()
        cur.close()

    def load_workflow_data(self, workflow_id: str, step_name: str = None) -> dict:
        """加载步骤输入数据"""
        import json
        cur = self.conn.cursor()
        if step_name:
            cur.execute("""
                SELECT data_key, data_value FROM workflow_data
                WHERE workflow_id = %s AND step_name = %s
            """, (workflow_id, step_name))
        else:
            cur.execute("""
                SELECT data_key, data_value FROM workflow_data
                WHERE workflow_id = %s
            """, (workflow_id,))

        result = {}
        for key, value in cur.fetchall():
            try:
                result[key] = json.loads(value)
            except:
                result[key] = value
        cur.close()
        return result

    def get_latest_workflow_data(self, workflow_id: str, max_steps: int = 10) -> dict:
        """获取最近steps的数据，用于数据传递"""
        import json
        cur = self.conn.cursor()
        cur.execute("""
            WITH ranked_data AS (
                SELECT
                    step_name,
                    data_key,
                    data_value,
                    created_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY step_name, data_key
                        ORDER BY created_at DESC
                    ) AS rn,
                    MAX(created_at) OVER (PARTITION BY step_name) AS step_updated_at
                FROM workflow_data
                WHERE workflow_id = %s
            ), latest_steps AS (
                SELECT DISTINCT step_name, step_updated_at
                FROM ranked_data
                ORDER BY step_updated_at DESC, step_name DESC
                LIMIT %s
            )
            SELECT rd.step_name, rd.data_key, rd.data_value
            FROM ranked_data rd
            JOIN latest_steps ls ON rd.step_name = ls.step_name
            WHERE rd.rn = 1
            ORDER BY ls.step_updated_at ASC, rd.step_name ASC, rd.data_key ASC
        """, (workflow_id, max_steps))

        result = {}
        for step_name, data_key, data_value in cur.fetchall():
            if step_name not in result:
                result[step_name] = {}
            try:
                result[step_name][data_key] = json.loads(data_value)
            except:
                result[step_name][data_key] = data_value
        cur.close()
        return result

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

