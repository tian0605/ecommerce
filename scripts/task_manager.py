#!/usr/bin/env python3
"""任务状态管理器 - 支持多级任务结构与阶段状态机"""
import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import json
import re


MAX_TASK_NAME_LENGTH = 50


class ExecState(str, Enum):
    NEW = 'new'
    PROCESSING = 'processing'
    END = 'end'
    ERROR_FIX_PENDING = 'error_fix_pending'
    NORMAL_CRASH = 'normal_crash'
    REQUIRES_MANUAL = 'requires_manual'
    VOID = 'void'


class TaskStage(str, Enum):
    IDEA = 'idea'
    PLAN = 'plan'
    BUILD = 'build'
    REVIEW = 'review'
    TEST = 'test'
    RELEASE = 'release'
    RETROSPECTIVE = 'retrospective'


class StageStatus(str, Enum):
    READY = 'ready'
    IN_PROGRESS = 'in_progress'
    BLOCKED = 'blocked'
    PASSED = 'passed'
    FAILED = 'failed'
    DONE = 'done'
    RETRYABLE = 'retryable'


STAGE_SEQUENCE = [stage.value for stage in TaskStage]
STAGE_SET = set(STAGE_SEQUENCE)
STAGE_STATUS_SET = {status.value for status in StageStatus}
JSON_FIELD_NAMES = {'notification_audit', 'progress_checkpoint', 'stage_context'}
SITE_CONTEXT_KEYS = ('market_code', 'site_code', 'shop_code', 'source_language', 'listing_language')
SITE_CONTEXT_DEFAULTS = {
    'shopee_tw': {
        'market_code': 'shopee_tw',
        'site_code': 'shopee_tw',
        'source_language': 'zh-CN',
        'listing_language': 'zh-Hant',
    },
    'shopee_ph': {
        'market_code': 'shopee_ph',
        'site_code': 'shopee_ph',
        'source_language': 'zh-CN',
        'listing_language': 'en',
    },
}


def _now_iso() -> str:
    return datetime.now().isoformat()

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
        """确保 tasks 表包含调度、反馈审计和阶段状态机所需字段。"""
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
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS current_stage TEXT",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS stage_status TEXT",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS stage_started_at TIMESTAMP",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS stage_updated_at TIMESTAMP",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS stage_owner TEXT",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS stage_result TEXT",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS blocked_reason TEXT",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS next_stage TEXT",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS source_stage TEXT",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS stage_context JSONB DEFAULT '{}'::jsonb",
            "CREATE INDEX IF NOT EXISTS idx_tasks_stage_exec_priority_created ON tasks(current_stage, exec_state, priority, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_root_source_stage_created ON tasks(root_task_id, source_stage, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_type_stage_exec ON tasks(task_type, current_stage, exec_state)",
        ]
        for statement in statements:
            cur.execute(statement)

        cur.execute(
            """
            UPDATE tasks
            SET current_stage = CASE
                    WHEN LOWER(COALESCE(exec_state, '')) = 'end' THEN 'retrospective'
                    WHEN task_type = '修复' THEN 'build'
                    WHEN task_type = '临时任务'
                         AND COALESCE(NULLIF(BTRIM(success_criteria), ''), NULLIF(BTRIM(plan), '')) IS NULL THEN 'idea'
                    WHEN task_type = '临时任务' THEN 'plan'
                    ELSE 'plan'
                END,
                stage_status = CASE
                    WHEN LOWER(COALESCE(exec_state, '')) = 'end' THEN 'done'
                    WHEN LOWER(COALESCE(exec_state, '')) = 'processing' THEN 'in_progress'
                    WHEN LOWER(COALESCE(exec_state, '')) IN ('error_fix_pending', 'normal_crash') THEN 'retryable'
                    WHEN LOWER(COALESCE(exec_state, '')) = 'requires_manual' THEN 'blocked'
                    ELSE 'ready'
                END,
                stage_started_at = COALESCE(stage_started_at, created_at, CURRENT_TIMESTAMP),
                stage_updated_at = COALESCE(stage_updated_at, updated_at, created_at, CURRENT_TIMESTAMP),
                next_stage = COALESCE(next_stage, CASE
                    WHEN LOWER(COALESCE(exec_state, '')) = 'end' THEN NULL
                    WHEN task_type = '修复' THEN 'review'
                    WHEN task_type = '临时任务'
                         AND COALESCE(NULLIF(BTRIM(success_criteria), ''), NULLIF(BTRIM(plan), '')) IS NULL THEN 'plan'
                    ELSE 'build'
                END),
                stage_context = COALESCE(stage_context, '{}'::jsonb)
            WHERE current_stage IS NULL
               OR stage_status IS NULL
               OR stage_started_at IS NULL
               OR stage_updated_at IS NULL
               OR stage_context IS NULL
            """
        )
        self.conn.commit()
        cur.close()

    def _normalize_stage(self, stage: Optional[str]) -> Optional[str]:
        if stage is None:
            return None
        normalized = str(stage).strip().lower()
        return normalized if normalized in STAGE_SET else None

    def _normalize_stage_status(self, stage_status: Optional[str]) -> Optional[str]:
        if stage_status is None:
            return None
        normalized = str(stage_status).strip().lower()
        return normalized if normalized in STAGE_STATUS_SET else None

    def _default_stage_context(self) -> Dict[str, Dict[str, Any]]:
        base = {}
        for stage in STAGE_SEQUENCE:
            stage_payload: Dict[str, Any] = {
                'summary': '',
                'artifacts': [],
                'issues': [],
                'decision': '',
                'entered_at': None,
                'completed_at': None,
                'actor': '',
            }
            if stage == TaskStage.RELEASE.value:
                stage_payload.update({'prepare': {}, 'execute': {}, 'verify': {}})
            if stage == TaskStage.RETROSPECTIVE.value:
                stage_payload.update({'rca': {}, 'sop': {}, 'debt': {}})
            base[stage] = stage_payload
        return base

    def _ensure_stage_context_shape(self, stage_context: Any) -> Dict[str, Any]:
        context = self._default_stage_context()
        if isinstance(stage_context, str):
            try:
                stage_context = json.loads(stage_context)
            except Exception:
                stage_context = {}
        if not isinstance(stage_context, dict):
            return context

        for stage, payload in stage_context.items():
            if stage not in context or not isinstance(payload, dict):
                continue
            merged = dict(context[stage])
            merged.update(payload)
            context[stage] = merged
        return context

    def _append_stage_artifact(self, stage_context: dict, stage: str,
                               artifact_type: str, payload: dict):
        stage_payload = stage_context.setdefault(stage, {})
        artifacts = list(stage_payload.get('artifacts') or [])
        artifacts.append({
            'type': artifact_type,
            'payload': payload,
            'timestamp': _now_iso(),
        })
        stage_payload['artifacts'] = artifacts[-20:]

    def _append_stage_issue(self, stage_context: dict, stage: str, severity: str,
                            issue_type: str, payload: dict) -> str:
        stage_payload = stage_context.setdefault(stage, {})
        issues = list(stage_payload.get('issues') or [])
        issue_id = hashlib.sha1(
            f"{stage}|{severity}|{issue_type}|{json.dumps(payload, ensure_ascii=False, sort_keys=True)}".encode('utf-8')
        ).hexdigest()[:12]
        issues.append({
            'id': issue_id,
            'severity': severity,
            'type': issue_type,
            'payload': payload,
            'resolved': False,
            'timestamp': _now_iso(),
        })
        stage_payload['issues'] = issues[-50:]
        return issue_id

    def _default_next_stage(self, current_stage: Optional[str]) -> Optional[str]:
        normalized = self._normalize_stage(current_stage)
        if not normalized:
            return None
        try:
            index = STAGE_SEQUENCE.index(normalized)
        except ValueError:
            return None
        if index >= len(STAGE_SEQUENCE) - 1:
            return None
        return STAGE_SEQUENCE[index + 1]

    def _adapt_update_value(self, key: str, value: Any) -> Any:
        if key in JSON_FIELD_NAMES and isinstance(value, (dict, list)):
            return Json(value)
        return value

    def _hydrate_task_row(self, task: Optional[Dict]) -> Optional[Dict]:
        if not task:
            return task
        if task.get('stage_context') is not None:
            task['stage_context'] = self._ensure_stage_context_shape(task.get('stage_context'))
        else:
            task['stage_context'] = self._default_stage_context()
        for field in ('progress_checkpoint', 'notification_audit'):
            value = task.get(field)
            if isinstance(value, str):
                try:
                    task[field] = json.loads(value)
                except Exception:
                    pass
        return task

    def _infer_initial_stage(self, task_type: str, success_criteria: str = '',
                             plan: str = '', initial_stage: str = None) -> str:
        normalized = self._normalize_stage(initial_stage)
        if normalized:
            return normalized
        if task_type == '修复':
            return TaskStage.BUILD.value
        if task_type == '临时任务' and not (str(success_criteria or '').strip() or str(plan or '').strip()):
            return TaskStage.IDEA.value
        return TaskStage.PLAN.value

    def _looks_like_executable_temp_task(self, checkpoint: Any = None, description: str = '') -> bool:
        if not isinstance(checkpoint, dict):
            checkpoint = {}

        executable_markers = (
            'full_workflow',
            'url',
            'products',
            'product_id',
            'alibaba_product_id',
            'alibaba_ids',
            'scope',
            'site_context',
            'lightweight',
            'no_publish',
            'lifecycle_replay',
            'stage_replay',
        )
        if any(checkpoint.get(key) not in (None, '', [], {}) for key in executable_markers):
            return True

        output_data = checkpoint.get('output_data') if isinstance(checkpoint.get('output_data'), dict) else {}
        if any(output_data.get(key) not in (None, '', [], {}) for key in ('url', 'products', 'product_id', 'alibaba_product_id', 'alibaba_ids', 'scope', 'site_context')):
            return True

        description_text = str(description or '').strip().lower()
        if not description_text:
            return False
        return any(marker in description_text for marker in (
            'ops-web',
            '1688',
            '完整工作流',
            '利润同步',
            '利润明细初始化',
        ))

    def _infer_stage_status_from_exec_state(self, exec_state: Optional[str]) -> str:
        normalized = self._normalize_exec_state(exec_state)
        if normalized == ExecState.PROCESSING.value:
            return StageStatus.IN_PROGRESS.value
        if normalized == ExecState.END.value:
            return StageStatus.DONE.value
        if normalized == ExecState.VOID.value:
            return StageStatus.DONE.value
        if normalized in {ExecState.ERROR_FIX_PENDING.value, ExecState.NORMAL_CRASH.value}:
            return StageStatus.RETRYABLE.value
        if normalized == ExecState.REQUIRES_MANUAL.value:
            return StageStatus.BLOCKED.value
        return StageStatus.READY.value

    def _normalize_error_signature(self, error: str, fix: str = "") -> str:
        text = f"{error}\n{fix}".strip().lower()
        text = re.sub(r"\s+", " ", text)
        return hashlib.sha1(text.encode('utf-8')).hexdigest()

    def _extract_structured_metadata(self, task: Dict[str, Any]) -> Dict[str, str]:
        metadata: Dict[str, str] = {}
        if not isinstance(task, dict):
            return metadata

        for field in ('plan', 'fix_suggestion', 'description'):
            raw = task.get(field) or ''
            if not raw:
                continue
            for line in str(raw).splitlines():
                if '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                if key and value and key not in metadata:
                    metadata[key] = value
        return metadata

    def _merge_site_context(self, target: Dict[str, Any], payload: Any):
        if not isinstance(target, dict) or not isinstance(payload, dict):
            return
        for key in SITE_CONTEXT_KEYS:
            value = payload.get(key)
            if value not in (None, ''):
                target[key] = str(value).strip()

    def _normalize_site_context(self, payload: Any, include_defaults: bool = True) -> Dict[str, str]:
        context: Dict[str, str] = {}
        self._merge_site_context(context, payload if isinstance(payload, dict) else {})

        site_code = context.get('site_code')
        if site_code:
            site_code = site_code.strip().lower()
            context['site_code'] = site_code

        if include_defaults:
            defaults = SITE_CONTEXT_DEFAULTS.get(site_code or 'shopee_tw', SITE_CONTEXT_DEFAULTS['shopee_tw'])
            merged = dict(defaults)
            merged.update({key: value for key, value in context.items() if value not in (None, '')})
            context = merged
        elif site_code and site_code in SITE_CONTEXT_DEFAULTS:
            defaults = SITE_CONTEXT_DEFAULTS[site_code]
            for key in ('market_code', 'source_language', 'listing_language'):
                context.setdefault(key, defaults.get(key))

        if context.get('market_code') in (None, '') and context.get('site_code'):
            context['market_code'] = context['site_code']

        return {key: value for key, value in context.items() if value not in (None, '')}

    def get_task_site_context(self, task_or_name: Any, stage: Optional[str] = None,
                              include_defaults: bool = True) -> Dict[str, str]:
        task = task_or_name if isinstance(task_or_name, dict) else self.get_task(str(task_or_name))
        if not task:
            return self._normalize_site_context({}, include_defaults=include_defaults)

        merged: Dict[str, str] = {}
        self._merge_site_context(merged, self._extract_structured_metadata(task))
        self._merge_site_context(merged, task)

        checkpoint = task.get('progress_checkpoint')
        if isinstance(checkpoint, str):
            try:
                checkpoint = json.loads(checkpoint)
            except Exception:
                checkpoint = {}
        self._merge_site_context(merged, checkpoint if isinstance(checkpoint, dict) else {})

        stage_context = self._ensure_stage_context_shape(task.get('stage_context'))
        for stage_name in (TaskStage.PLAN.value, TaskStage.BUILD.value, TaskStage.RELEASE.value):
            payload = stage_context.get(stage_name) or {}
            self._merge_site_context(merged, payload)
            self._merge_site_context(merged, payload.get('site_context') or {})

        active_stage = self._normalize_stage(stage) or self._normalize_stage(task.get('current_stage'))
        if active_stage:
            payload = stage_context.get(active_stage) or {}
            self._merge_site_context(merged, payload)
            self._merge_site_context(merged, payload.get('site_context') or {})

        return self._normalize_site_context(merged, include_defaults=include_defaults)

    def persist_task_site_context(self, task_name: str, stage: str,
                                  site_context: Dict[str, Any], result: str = None) -> bool:
        normalized_stage = self._normalize_stage(stage)
        if not normalized_stage:
            return False

        current_context = self.get_task_site_context(task_name, stage=normalized_stage, include_defaults=False)
        merged = dict(current_context)
        self._merge_site_context(merged, site_context or {})
        normalized_context = self._normalize_site_context(merged, include_defaults=True)
        payload_updates: Dict[str, Any] = {'site_context': normalized_context}
        payload_updates.update(normalized_context)
        if normalized_stage == TaskStage.RELEASE.value:
            payload_updates['publish_target'] = {
                'market_code': normalized_context.get('market_code'),
                'site_code': normalized_context.get('site_code'),
                'shop_code': normalized_context.get('shop_code'),
            }
        return self.upsert_stage_payload(task_name, normalized_stage, payload_updates, result=result)

    def _normalize_exec_state(self, exec_state: Optional[str]) -> Optional[str]:
        if exec_state is None:
            return None
        return str(exec_state).strip().lower()

    def _normalize_status_for_state(self, exec_state: Optional[str], status: Optional[str]) -> Optional[str]:
        normalized_state = self._normalize_exec_state(exec_state)
        normalized_status = str(status).strip().lower() if status is not None else None

        if normalized_state == 'processing':
            return 'running'
        if normalized_state == 'new':
            return 'pending'
        if normalized_state == 'normal_crash':
            return 'pending'
        if normalized_state == 'error_fix_pending':
            return 'failed'
        if normalized_state == 'requires_manual':
            return 'failed'
        if normalized_state == 'void':
            return 'voided'
        if normalized_state == 'end':
            if normalized_status in {'skipped', 'voided', 'completed'}:
                return normalized_status
            return 'completed'

        return normalized_status

    def _next_fix_subtask_name(self, parent_task_name: str) -> str:
        existing = self.get_sub_tasks(parent_task_name)
        max_suffix = 0
        pattern = re.compile(r"-(\d{3})$")
        for task in existing:
            match = pattern.search(task.get('task_name', ''))
            if match:
                max_suffix = max(max_suffix, int(match.group(1)))
        return self._build_fix_subtask_name(parent_task_name, max_suffix + 1)

    def _build_fix_subtask_name(self, parent_task_name: str, suffix: int) -> str:
        suffix_text = f"{suffix:03d}"
        candidate = f"FIX-{parent_task_name}-{suffix_text}"
        if len(candidate) <= MAX_TASK_NAME_LENGTH:
            return candidate

        digest = hashlib.sha1(parent_task_name.encode('utf-8')).hexdigest()[:10]
        available = MAX_TASK_NAME_LENGTH - len(f"FIX--{digest}-{suffix_text}")
        compact_parent = re.sub(r"[^A-Za-z0-9-]+", "", parent_task_name)[:max(available, 4)]
        if not compact_parent:
            compact_parent = 'TASK'
        return f"FIX-{compact_parent}-{digest}-{suffix_text}"

    def _find_open_fix_subtask(self, parent_task_name: str, error_signature: str) -> Optional[Dict]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT * FROM tasks
            WHERE parent_task_id = %s
              AND task_type = '修复'
              AND error_signature = %s
                            AND LOWER(COALESCE(exec_state, '')) NOT IN ('end', 'void')
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
        return self._hydrate_task_row(task)
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM tasks ORDER BY task_level, priority, created_at")
        cols = [desc[0] for desc in cur.description]
        tasks = [self._hydrate_task_row(dict(zip(cols, row))) for row in cur.fetchall()]
        cur.close()
        return tasks
    
    def get_tasks_by_state(self, exec_state: str) -> List[Dict]:
        """按执行状态获取任务"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE exec_state = %s", (exec_state,))
        cols = [desc[0] for desc in cur.description]
        tasks = [self._hydrate_task_row(dict(zip(cols, row))) for row in cur.fetchall()]
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
        tasks = [self._hydrate_task_row(dict(zip(cols, row))) for row in cur.fetchall()]
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
        tasks = [self._hydrate_task_row(dict(zip(cols, row))) for row in cur.fetchall()]
        cur.close()
        return tasks
    
    def get_runnable_tasks_by_stage(self, limit: int = 2, allowed_stages: List[str] = None,
                                    task_types: List[str] = None) -> List[Dict]:
        """获取可运行任务，兼顾执行态、阶段态与任务类型优先级。"""
        cur = self.conn.cursor()

        stage_filters = []
        params: List[Any] = []
        if allowed_stages:
            normalized_stages = [stage for stage in (self._normalize_stage(stage) for stage in allowed_stages) if stage]
            if normalized_stages:
                stage_filters.append("current_stage = ANY(%s)")
                params.append(normalized_stages)
        if task_types:
            stage_filters.append("task_type = ANY(%s)")
            params.append(task_types)

        where_clause = " AND ".join(stage_filters)
        if where_clause:
            where_clause = f" AND {where_clause}"

        cur.execute(f"""
            SELECT * FROM tasks
            WHERE LOWER(COALESCE(exec_state, '')) IN ('error_fix_pending', 'normal_crash', 'new')
              AND LOWER(COALESCE(stage_status, 'ready')) NOT IN ('blocked', 'done')
              {where_clause}
            ORDER BY
                CASE task_type
                    WHEN '修复' THEN 1
                    WHEN '临时任务' THEN 2
                    WHEN '常规' THEN 3
                    WHEN '创造' THEN 4
                    ELSE 5
                END,
                CASE current_stage
                    WHEN 'release' THEN 1
                    WHEN 'test' THEN 2
                    WHEN 'review' THEN 3
                    WHEN 'build' THEN 4
                    WHEN 'plan' THEN 5
                    WHEN 'idea' THEN 6
                    WHEN 'retrospective' THEN 7
                    ELSE 8
                END,
                CASE priority
                    WHEN 'P0' THEN 1
                    WHEN 'P1' THEN 2
                    WHEN 'P2' THEN 3
                    ELSE 4
                END,
                task_level DESC,
                created_at
            LIMIT %s
        """, params + [limit * 3])

        cols = [desc[0] for desc in cur.description]
        all_tasks = [self._hydrate_task_row(dict(zip(cols, row))) for row in cur.fetchall()]

        result = []
        for task in all_tasks:
            if task.get('task_level') == 2:
                if self._normalize_exec_state(task.get('exec_state')) != 'requires_manual':
                    result.append(task)
            else:
                cur.execute("""
                    SELECT COUNT(*) FROM tasks 
                    WHERE parent_task_id = %s 
                    AND LOWER(COALESCE(exec_state, '')) NOT IN ('end', 'void', 'requires_manual')
                """, (task['task_name'],))
                pending_count = cur.fetchone()[0]
                if pending_count == 0:
                    result.append(task)

        cur.close()
        return result[:limit]

    def claim_runnable_tasks_by_stage(self, limit: int = 2, allowed_stages: List[str] = None,
                                      task_types: List[str] = None) -> List[Dict]:
        """原子领取可运行任务，避免多个调度器并发启动同一任务。"""
        cur = self.conn.cursor()

        stage_filters = []
        params: List[Any] = []
        if allowed_stages:
            normalized_stages = [stage for stage in (self._normalize_stage(stage) for stage in allowed_stages) if stage]
            if normalized_stages:
                stage_filters.append("current_stage = ANY(%s)")
                params.append(normalized_stages)
        if task_types:
            stage_filters.append("task_type = ANY(%s)")
            params.append(task_types)

        where_clause = " AND ".join(stage_filters)
        if where_clause:
            where_clause = f" AND {where_clause}"

        cur.execute(f"""
            SELECT * FROM tasks
            WHERE LOWER(COALESCE(exec_state, '')) IN ('error_fix_pending', 'normal_crash', 'new')
              AND LOWER(COALESCE(stage_status, 'ready')) NOT IN ('blocked', 'done')
              {where_clause}
            ORDER BY
                CASE task_type
                    WHEN '修复' THEN 1
                    WHEN '临时任务' THEN 2
                    WHEN '常规' THEN 3
                    WHEN '创造' THEN 4
                    ELSE 5
                END,
                CASE current_stage
                    WHEN 'release' THEN 1
                    WHEN 'test' THEN 2
                    WHEN 'review' THEN 3
                    WHEN 'build' THEN 4
                    WHEN 'plan' THEN 5
                    WHEN 'idea' THEN 6
                    WHEN 'retrospective' THEN 7
                    ELSE 8
                END,
                CASE priority
                    WHEN 'P0' THEN 1
                    WHEN 'P1' THEN 2
                    WHEN 'P2' THEN 3
                    ELSE 4
                END,
                task_level DESC,
                created_at
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        """, params + [limit * 3])

        cols = [desc[0] for desc in cur.description]
        all_tasks = [self._hydrate_task_row(dict(zip(cols, row))) for row in cur.fetchall()]

        claimed: List[Dict] = []
        now = datetime.now()
        for task in all_tasks:
            if len(claimed) >= limit:
                break

            if task.get('task_level') == 2:
                if self._normalize_exec_state(task.get('exec_state')) == 'requires_manual':
                    continue
            else:
                cur.execute("""
                    SELECT COUNT(*) FROM tasks
                    WHERE parent_task_id = %s
                      AND LOWER(COALESCE(exec_state, '')) NOT IN ('end', 'void', 'requires_manual')
                """, (task['task_name'],))
                pending_count = cur.fetchone()[0]
                if pending_count != 0:
                    continue

            cur.execute("""
                UPDATE tasks
                SET status = %s,
                    exec_state = %s,
                    execution_count = COALESCE(execution_count, 0) + 1,
                    retry_count = COALESCE(retry_count, 0) + 1,
                    stage_status = COALESCE(stage_status, %s),
                    updated_at = %s
                WHERE task_name = %s
            """, ('running', 'processing', StageStatus.IN_PROGRESS.value, now, task['task_name']))

            task['status'] = 'running'
            task['exec_state'] = 'processing'
            task['execution_count'] = (task.get('execution_count') or 0) + 1
            task['retry_count'] = (task.get('retry_count') or 0) + 1
            task['stage_status'] = task.get('stage_status') or StageStatus.IN_PROGRESS.value
            task['updated_at'] = now
            claimed.append(task)

        self.conn.commit()
        cur.close()
        return claimed

    def get_actionable_tasks(self, limit: int = 2) -> List[Dict]:
        """兼容旧接口，内部转调阶段感知查询。"""
        return self.get_runnable_tasks_by_stage(limit=limit)
    
    # ========== 状态更新 ==========
    def update_task(self, task_name: str, **kwargs):
        """更新任务字段"""
        if not kwargs:
            return

        if 'exec_state' in kwargs:
            kwargs['exec_state'] = self._normalize_exec_state(kwargs.get('exec_state'))
        if 'status' in kwargs or 'exec_state' in kwargs:
            kwargs['status'] = self._normalize_status_for_state(kwargs.get('exec_state'), kwargs.get('status'))
        if 'current_stage' in kwargs:
            kwargs['current_stage'] = self._normalize_stage(kwargs.get('current_stage')) or kwargs.get('current_stage')
        if 'stage_status' in kwargs:
            kwargs['stage_status'] = self._normalize_stage_status(kwargs.get('stage_status')) or kwargs.get('stage_status')

        adapted_kwargs = {key: self._adapt_update_value(key, value) for key, value in kwargs.items()}
        
        adapted_kwargs['updated_at'] = datetime.now()
        set_clause = ", ".join([f"{k} = %s" for k in adapted_kwargs.keys()])
        values = list(adapted_kwargs.values()) + [task_name]
        
        cur = self.conn.cursor()
        cur.execute(f"UPDATE tasks SET {set_clause} WHERE task_name = %s", values)
        self.conn.commit()
        cur.close()

    def initialize_stage(self, task_name: str, stage: str = 'idea', status: str = 'ready',
                         owner: str = None, source_stage: str = None) -> bool:
        """初始化任务阶段状态与阶段上下文。"""
        normalized_stage = self._normalize_stage(stage) or TaskStage.IDEA.value
        normalized_status = self._normalize_stage_status(status) or StageStatus.READY.value
        task = self.get_task(task_name)
        if not task:
            return False

        stage_context = self._ensure_stage_context_shape(task.get('stage_context'))
        stage_payload = dict(stage_context.get(normalized_stage) or {})
        if not stage_payload.get('entered_at'):
            stage_payload['entered_at'] = _now_iso()
        if owner and not stage_payload.get('actor'):
            stage_payload['actor'] = owner
        stage_context[normalized_stage] = stage_payload

        self.update_task(
            task_name,
            current_stage=normalized_stage,
            stage_status=normalized_status,
            stage_started_at=task.get('stage_started_at') or datetime.now(),
            stage_updated_at=datetime.now(),
            stage_owner=owner or task.get('stage_owner'),
            next_stage=self._default_next_stage(normalized_stage),
            source_stage=self._normalize_stage(source_stage) or task.get('source_stage'),
            blocked_reason=None,
            stage_context=stage_context,
        )
        return True

    def set_stage(self, task_name: str, stage: str, status: str = 'ready',
                  owner: str = None, result: str = None) -> bool:
        normalized_stage = self._normalize_stage(stage)
        normalized_status = self._normalize_stage_status(status)
        task = self.get_task(task_name)
        if not task or not normalized_stage or not normalized_status:
            return False

        stage_context = self._ensure_stage_context_shape(task.get('stage_context'))
        stage_payload = dict(stage_context.get(normalized_stage) or {})
        if not stage_payload.get('entered_at'):
            stage_payload['entered_at'] = _now_iso()
        if owner:
            stage_payload['actor'] = owner
        if result:
            stage_payload['decision'] = result
        if normalized_status in {StageStatus.PASSED.value, StageStatus.DONE.value, StageStatus.FAILED.value}:
            stage_payload['completed_at'] = _now_iso()
        stage_context[normalized_stage] = stage_payload

        self.update_task(
            task_name,
            current_stage=normalized_stage,
            stage_status=normalized_status,
            stage_started_at=datetime.now() if task.get('current_stage') != normalized_stage else task.get('stage_started_at'),
            stage_updated_at=datetime.now(),
            stage_owner=owner or task.get('stage_owner'),
            stage_result=result or task.get('stage_result'),
            next_stage=self._default_next_stage(normalized_stage),
            blocked_reason=None if normalized_status != StageStatus.BLOCKED.value else task.get('blocked_reason'),
            stage_context=stage_context,
        )
        return True

    def record_stage_artifact(self, task_name: str, stage: str, artifact_type: str,
                              payload: dict) -> bool:
        normalized_stage = self._normalize_stage(stage)
        task = self.get_task(task_name)
        if not task or not normalized_stage:
            return False
        stage_context = self._ensure_stage_context_shape(task.get('stage_context'))
        self._append_stage_artifact(stage_context, normalized_stage, artifact_type, payload or {})
        self.update_task(task_name, stage_context=stage_context, stage_updated_at=datetime.now())
        return True

    def upsert_stage_payload(self, task_name: str, stage: str,
                             payload_updates: Dict[str, Any],
                             status: str = None,
                             result: str = None) -> bool:
        normalized_stage = self._normalize_stage(stage)
        task = self.get_task(task_name)
        if not task or not normalized_stage:
            return False

        stage_context = self._ensure_stage_context_shape(task.get('stage_context'))
        stage_payload = dict(stage_context.get(normalized_stage) or {})
        stage_payload.update(payload_updates or {})
        if not stage_payload.get('entered_at'):
            stage_payload['entered_at'] = _now_iso()
        if status in {StageStatus.DONE.value, StageStatus.PASSED.value, StageStatus.FAILED.value}:
            stage_payload['completed_at'] = _now_iso()
        stage_context[normalized_stage] = stage_payload

        update_kwargs: Dict[str, Any] = {
            'stage_context': stage_context,
            'stage_updated_at': datetime.now(),
        }
        if status:
            update_kwargs['current_stage'] = normalized_stage
            update_kwargs['stage_status'] = status
        if result:
            update_kwargs['stage_result'] = result
        self.update_task(task_name, **update_kwargs)
        return True

    def attach_stage_issue(self, task_name: str, stage: str, severity: str,
                           issue_type: str, payload: dict) -> Optional[str]:
        normalized_stage = self._normalize_stage(stage)
        task = self.get_task(task_name)
        if not task or not normalized_stage:
            return None
        stage_context = self._ensure_stage_context_shape(task.get('stage_context'))
        issue_id = self._append_stage_issue(stage_context, normalized_stage, severity, issue_type, payload or {})
        self.update_task(task_name, stage_context=stage_context, stage_updated_at=datetime.now())
        return issue_id

    def resolve_stage_issue(self, task_name: str, stage: str, issue_id: str) -> bool:
        normalized_stage = self._normalize_stage(stage)
        task = self.get_task(task_name)
        if not task or not normalized_stage or not issue_id:
            return False
        stage_context = self._ensure_stage_context_shape(task.get('stage_context'))
        issues = list(stage_context.get(normalized_stage, {}).get('issues') or [])
        updated = False
        for issue in issues:
            if issue.get('id') == issue_id:
                issue['resolved'] = True
                issue['resolved_at'] = _now_iso()
                updated = True
                break
        if not updated:
            return False
        stage_context[normalized_stage]['issues'] = issues
        self.update_task(task_name, stage_context=stage_context, stage_updated_at=datetime.now())
        return True

    def set_stage_blocked(self, task_name: str, reason: str, next_retry_at=None) -> bool:
        task = self.get_task(task_name)
        if not task:
            return False
        stage_context = self._ensure_stage_context_shape(task.get('stage_context'))
        current_stage = self._normalize_stage(task.get('current_stage')) or TaskStage.PLAN.value
        stage_payload = dict(stage_context.get(current_stage) or {})
        stage_payload['decision'] = reason
        if next_retry_at is not None:
            stage_payload['next_retry_at'] = str(next_retry_at)
        stage_context[current_stage] = stage_payload
        self.update_task(
            task_name,
            stage_status=StageStatus.BLOCKED.value,
            blocked_reason=reason,
            stage_updated_at=datetime.now(),
            stage_context=stage_context,
        )
        return True

    def check_stage_gate(self, task_name: str, from_stage: str, to_stage: str) -> Dict[str, Any]:
        """检查阶段迁移闸门，返回结构化结果。"""
        task = self.get_task(task_name)
        normalized_from = self._normalize_stage(from_stage)
        normalized_to = self._normalize_stage(to_stage)
        result = {
            'passed': False,
            'status': 'invalid',
            'missing_items': [],
            'blocking_issues': [],
            'recommended_action': None,
        }
        if not task or not normalized_from or not normalized_to:
            result['blocking_issues'].append('任务不存在或阶段非法')
            return result

        stage_context = self._ensure_stage_context_shape(task.get('stage_context'))

        if normalized_from == TaskStage.IDEA.value and normalized_to == TaskStage.PLAN.value:
            if not str(task.get('description') or '').strip():
                result['missing_items'].append('description')
            if not str(task.get('priority') or '').strip():
                result['missing_items'].append('priority')
        elif normalized_from == TaskStage.PLAN.value and normalized_to == TaskStage.BUILD.value:
            if not str(task.get('success_criteria') or '').strip():
                result['missing_items'].append('success_criteria')
            if not str(task.get('plan') or '').strip():
                result['missing_items'].append('plan')
            if not task.get('expected_duration') and task.get('task_type') == '临时任务':
                result['missing_items'].append('expected_duration')
        elif normalized_from == TaskStage.BUILD.value and normalized_to == TaskStage.REVIEW.value:
            has_build_artifacts = bool(stage_context.get(TaskStage.BUILD.value, {}).get('artifacts'))
            has_checkpoint = bool(task.get('progress_checkpoint'))
            has_workflow_data = bool(self.get_latest_workflow_data(task.get('parent_task_id') or task_name, max_steps=1))
            if not (has_build_artifacts or has_checkpoint or has_workflow_data):
                result['missing_items'].append('build_artifacts')
        elif normalized_from == TaskStage.REVIEW.value and normalized_to == TaskStage.TEST.value:
            issues = stage_context.get(TaskStage.REVIEW.value, {}).get('issues') or []
            unresolved = [issue for issue in issues if not issue.get('resolved') and issue.get('severity') in ('P0', 'P1', 'critical', 'high')]
            if unresolved:
                result['blocking_issues'].extend([issue.get('id') for issue in unresolved])
        elif normalized_from == TaskStage.TEST.value and normalized_to == TaskStage.RELEASE.value:
            test_artifacts = stage_context.get(TaskStage.TEST.value, {}).get('artifacts') or []
            has_test_evidence = any(artifact.get('type') in ('test_result', 'dry_run', 'save_only_validation') for artifact in test_artifacts)
            if not has_test_evidence:
                result['missing_items'].append('test_evidence')
        elif normalized_from == TaskStage.RELEASE.value and normalized_to == TaskStage.RETROSPECTIVE.value:
            release_verify = stage_context.get(TaskStage.RELEASE.value, {}).get('verify') or {}
            if not release_verify or not release_verify.get('passed'):
                result['missing_items'].append('release_verify')

        if result['missing_items'] or result['blocking_issues']:
            result['status'] = 'blocked'
            result['recommended_action'] = '补齐闸门条件后重试'
            return result

        result['passed'] = True
        result['status'] = 'passed'
        result['recommended_action'] = f'允许从 {normalized_from} 进入 {normalized_to}'
        return result

    def advance_stage(self, task_name: str, expected_from: str, target_stage: str,
                      owner: str = None) -> Dict[str, Any]:
        gate = self.check_stage_gate(task_name, expected_from, target_stage)
        if not gate.get('passed'):
            self.set_stage_blocked(task_name, '; '.join(gate.get('missing_items') or gate.get('blocking_issues') or ['stage gate blocked']))
            return gate
        self.set_stage(task_name, target_stage, status=StageStatus.READY.value, owner=owner)
        return {
            **gate,
            'current_stage': self._normalize_stage(target_stage),
        }

    def reopen_stage(self, task_name: str, target_stage: str, reason: str) -> bool:
        success = self.set_stage(task_name, target_stage, status=StageStatus.READY.value, result=reason)
        if success:
            self.update_task(task_name, blocked_reason=None)
        return success

    def fail_stage(self, task_name: str, stage: str, reason: str,
                   error_type: str = 'stage_failed', severity: str = 'P1') -> Dict[str, Any]:
        normalized_stage = self._normalize_stage(stage)
        task = self.get_task(task_name)
        if not task or not normalized_stage:
            return {'success': False, 'action': 'invalid'}

        issue_id = self.attach_stage_issue(
            task_name,
            normalized_stage,
            severity,
            error_type,
            {'reason': reason},
        )
        self.set_stage(task_name, normalized_stage, status=StageStatus.FAILED.value, result=reason)

        if error_type in {'manual_required', 'external_dependency_failure'}:
            self.mark_requires_manual(task_name, reason)
            return {'success': False, 'action': 'requires_manual', 'issue_id': issue_id}

        if error_type in {'system_crash', 'timeout_overtime'}:
            self.mark_normal_crash(task_name, reason)
            return {'success': False, 'action': 'retryable', 'issue_id': issue_id}

        self.update_task(task_name, source_stage=normalized_stage)
        self.mark_error_fix_pending(task_name, reason, f'error_type={error_type}')
        return {'success': False, 'action': 'fix_created', 'issue_id': issue_id}

    def sync_stage_from_exec_outcome(self, task_name: str, exec_result: dict) -> Dict[str, Any]:
        """根据执行器返回结果回写阶段状态。"""
        task = self.get_task(task_name)
        if not task:
            return {'success': False, 'action': 'missing_task'}

        current_stage = self._normalize_stage(task.get('current_stage')) or self._infer_initial_stage(task.get('task_type', '常规'))
        artifacts = exec_result.get('artifacts') or []
        issues = exec_result.get('issues') or []
        for artifact in artifacts:
            if isinstance(artifact, dict):
                self.record_stage_artifact(task_name, current_stage, artifact.get('type', 'artifact'), artifact.get('payload') or artifact)
        for issue in issues:
            if isinstance(issue, dict):
                self.attach_stage_issue(
                    task_name,
                    current_stage,
                    issue.get('severity', 'P1'),
                    issue.get('type', 'issue'),
                    issue.get('payload') or issue,
                )

        if not exec_result.get('success'):
            reason = exec_result.get('message') or exec_result.get('error') or '执行失败'
            return self.fail_stage(
                task_name,
                current_stage,
                reason,
                error_type=exec_result.get('error_type', 'stage_failed'),
                severity=exec_result.get('severity', 'P1'),
            )

        if current_stage == TaskStage.BUILD.value:
            return self.advance_stage(task_name, TaskStage.BUILD.value, TaskStage.REVIEW.value)
        if current_stage == TaskStage.REVIEW.value:
            return self.advance_stage(task_name, TaskStage.REVIEW.value, TaskStage.TEST.value)
        if current_stage == TaskStage.TEST.value:
            return self.advance_stage(task_name, TaskStage.TEST.value, TaskStage.RELEASE.value)
        if current_stage == TaskStage.RELEASE.value:
            self.record_stage_artifact(task_name, TaskStage.RELEASE.value, 'release_execute', exec_result)
            if exec_result.get('release_verify_passed'):
                task = self.get_task(task_name)
                stage_context = self._ensure_stage_context_shape(task.get('stage_context')) if task else self._default_stage_context()
                release_payload = dict(stage_context.get(TaskStage.RELEASE.value) or {})
                release_payload['verify'] = {
                    'passed': True,
                    'message': exec_result.get('release_verify_message', 'release.verify passed'),
                    'timestamp': _now_iso(),
                }
                stage_context[TaskStage.RELEASE.value] = release_payload
                self.update_task(task_name, stage_context=stage_context)
                return self.advance_stage(task_name, TaskStage.RELEASE.value, TaskStage.RETROSPECTIVE.value)
            self.set_stage(task_name, TaskStage.RELEASE.value, status=StageStatus.IN_PROGRESS.value, result='等待 release.verify')
            return {'success': True, 'action': 'await_release_verify'}
        if current_stage == TaskStage.RETROSPECTIVE.value:
            self.set_stage(task_name, TaskStage.RETROSPECTIVE.value, status=StageStatus.DONE.value, result=exec_result.get('message'))
            return {'success': True, 'action': 'retrospective_done'}

        self.set_stage(task_name, current_stage, status=StageStatus.PASSED.value, result=exec_result.get('message'))
        return {'success': True, 'action': 'stage_updated'}
    
    def mark_start(self, task_name: str):
        """标记任务开始，增加重试计数（不更新last_executed_at，避免重置卡死检测）"""
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE tasks 
            SET status = %s, 
                exec_state = %s, 
                execution_count = COALESCE(execution_count, 0) + 1,
                retry_count = COALESCE(retry_count, 0) + 1,
                stage_status = COALESCE(stage_status, %s),
                updated_at = %s
            WHERE task_name = %s
        """, ('running', 'processing', StageStatus.IN_PROGRESS.value, datetime.now(), task_name))
        self.conn.commit()
        cur.close()
    
    def mark_executing(self, task_name: str):
        """标记任务真正开始执行（更新last_executed_at）"""
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE tasks 
            SET last_executed_at = %s,
                stage_updated_at = COALESCE(stage_updated_at, %s),
                updated_at = %s
            WHERE task_name = %s
        """, (datetime.now(), datetime.now(), datetime.now(), task_name))
        self.conn.commit()
        cur.close()
    
    def mark_end(self, task_name: str, result: str = "成功"):
        """标记任务完成"""
        self.update_task(task_name,
            status='completed',
            exec_state='end',
            stage_status=StageStatus.DONE.value,
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
        
        all_completed = all(self._normalize_exec_state(c.get('exec_state')) in ('end', 'void') for c in children)
        
        if all_completed:
            self.set_stage(
                parent_task_name,
                TaskStage.RETROSPECTIVE.value,
                status=StageStatus.DONE.value,
                result='所有子任务执行完成'
            )
            self.update_task(parent_task_name,
                status='completed',
                exec_state='end',
                last_result='所有子任务执行完成'
            )
            print(f"  [workflow] 父任务 {parent_task_name} 验证完成")
            return True
        else:
            # 还有子任务未完成
            pending = [
                c['display_name']
                for c in children
                if self._normalize_exec_state(c.get('exec_state')) not in ('end', 'void')
            ]
            print(f"  [workflow] 父任务 {parent_task_name} 还有未完成子任务: {pending}")
            return False
    
    def mark_error_fix_pending(self, task_name: str, error: str, fix: str = ""):
        """标记需要修复（单个错误，单个子任务）"""
        task = self.get_task(task_name)
        self.update_task(task_name,
            status='failed',
            exec_state='error_fix_pending',
            stage_status=StageStatus.RETRYABLE.value,
            last_error=error,
            fix_suggestion=fix
        )
        if task and task.get('task_type') == '修复':
            self.update_task(task_name,
                status='failed',
                exec_state='requires_manual',
                last_error=error,
                fix_suggestion=fix or task.get('fix_suggestion', '')
            )
            return False
        # 自动创建一个子任务
        self.create_fix_subtask(task_name, error, fix)
        return True
    
    def mark_void(self, task_name: str, reason: str = ""):
        """标记任务为作废"""
        self.update_task(task_name,
            status='voided',
            exec_state='void',
            stage_status=StageStatus.DONE.value,
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
                error_type = error_info.get('error_type', 'manual_triage')
                priority = error_info.get('priority', 'P0')
                fix_suggestion = error_info.get('fix', '')
                success_criteria = error_info.get('success_criteria', f"修复{error_msg[:30]}成功")
                analysis = error_info.get('analysis', '')
                plan = error_info.get('plan', '')
            else:
                error_msg = str(error_info)
                error_type = 'manual_triage'
                priority = 'P0'
                fix_suggestion = ''
                success_criteria = f"修复{error_msg[:30]}成功"
                analysis = ''
                plan = ''

            if priority not in ('P0', 'P1', 'P2'):
                priority = 'P0'

            if error_type and error_type not in plan:
                plan = f"error_type={error_type}\n{plan}" if plan else f"error_type={error_type}"

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
                    success_criteria, analysis, plan, error_signature, source_stage
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, '修复', %s, %s, %s, %s, %s)
                ON CONFLICT (task_name) DO NOTHING
            """, (
                sub_task_name, display_name, f"错误: {error_msg}",
                priority, 'pending', 'new', fix_suggestion,
                task_name, 2, parent.get('root_task_id') or task_name,
                success_criteria, analysis, plan, error_signature,
                parent.get('current_stage') or TaskStage.BUILD.value,
            ))
            self.conn.commit()
            cur.close()
            self.initialize_stage(
                sub_task_name,
                stage=TaskStage.BUILD.value,
                source_stage=parent.get('current_stage') or TaskStage.BUILD.value,
            )
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
            stage_status=StageStatus.DONE.value,
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
                execution_count, task_type, error_signature, source_stage
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, '修复', %s, %s)
            ON CONFLICT (task_name) DO NOTHING
        """, (
            sub_task_name, display_name, f"错误: {error}",
            'P0', 'pending', 'new', fix,
            task_name, 2, parent.get('root_task_id') or task_name, error_signature,
            parent.get('current_stage') or TaskStage.BUILD.value,
        ))
        self.conn.commit()
        cur.close()
        self.initialize_stage(
            sub_task_name,
            stage=TaskStage.BUILD.value,
            source_stage=parent.get('current_stage') or TaskStage.BUILD.value,
        )
        return True

    def sync_parent_from_fix_result(self, fix_task_name: str, success: bool, message: str = '') -> bool:
        """修复任务结束后，将父任务恢复到来源阶段或标记人工介入。"""
        fix_task = self.get_task(fix_task_name)
        if not fix_task:
            return False
        parent_task_name = fix_task.get('parent_task_id')
        if not parent_task_name:
            return False
        parent_task = self.get_task(parent_task_name)
        if not parent_task:
            return False

        source_stage = self._normalize_stage(fix_task.get('source_stage')) or self._normalize_stage(parent_task.get('source_stage')) or TaskStage.BUILD.value
        if success:
            self.reopen_stage(parent_task_name, source_stage, f'FIX完成: {fix_task_name}')
            self.reset_task(
                parent_task_name,
                exec_state=ExecState.NEW.value,
                status='pending',
                error=None,
                fix=f'已完成修复任务 {fix_task_name}: {message}',
            )
            self.record_stage_artifact(
                parent_task_name,
                source_stage,
                'fix_resolution',
                {
                    'fix_task_name': fix_task_name,
                    'message': message,
                },
            )
            return True

        self.attach_stage_issue(
            parent_task_name,
            source_stage,
            'P1',
            'fix_failed',
            {
                'fix_task_name': fix_task_name,
                'message': message,
            },
        )
        self.mark_requires_manual(parent_task_name, f'FIX失败: {fix_task_name} - {message}')
        return False

    def inspect_parent_task_flow(self, task_name: str) -> Dict[str, Any]:
        """统一判断父任务是否应等待、完成或继续执行。"""
        children = self.get_sub_tasks(task_name)
        if not children:
            return {'action': 'no_children', 'child_count': 0}

        pending_children = [
            child for child in children
            if str(child.get('exec_state') or '').lower() in ('new', 'processing', 'error_fix_pending', 'normal_crash')
        ]
        if pending_children:
            reason = f'等待{len(pending_children)}个子任务完成'
            self.set_stage_blocked(task_name, reason)
            return {
                'action': 'blocked',
                'child_count': len(children),
                'pending_count': len(pending_children),
                'pending_children': [child.get('task_name') for child in pending_children],
            }

        all_done = all(str(child.get('exec_state') or '').lower() in ('end', 'void', 'requires_manual') for child in children)
        if all_done:
            completed = self.validate_parent_completion(task_name)
            return {
                'action': 'completed' if completed else 'await_manual',
                'child_count': len(children),
            }

        return {
            'action': 'abnormal',
            'child_count': len(children),
            'states': [str(child.get('exec_state') or '') for child in children],
        }

    def handle_execution_failure(self, task_name: str, output: str,
                                 current_stage: str = None) -> Dict[str, Any]:
        """统一处理执行失败，收口根因分析与 FIX 子任务创建。"""
        task = self.get_task(task_name)
        if not task:
            return {'success': False, 'action': 'missing_task'}

        normalized_stage = self._normalize_stage(current_stage) or self._normalize_stage(task.get('current_stage')) or TaskStage.BUILD.value
        retry_count = task.get('retry_count', 0) or 0
        failed_steps: List[Dict[str, Any]] = []

        if retry_count >= 3:
            try:
                from root_cause_analyzer import analyze as analyze_root_cause
                analysis_result = analyze_root_cause(task_name)
            except Exception as exc:
                analysis_result = None
                print(f"  [ROOT CAUSE] 根因分析执行异常: {str(exc)[:200]}")

            if analysis_result:
                for item in analysis_result.get('structured_problems') or []:
                    failed_steps.append({
                        'error': f"根因问题: {item.get('problem', '')[:80]}",
                        'error_type': item.get('error_type', 'manual_triage'),
                        'priority': item.get('priority', 'P2'),
                        'fix': item.get('fix_suggestion', ''),
                        'success_criteria': item.get('summary', '问题已解决，任务不再报此错误'),
                        'analysis': analysis_result.get('root_cause', ''),
                        'plan': '\n'.join(analysis_result.get('fix_steps') or []),
                    })

        if not failed_steps:
            for line in output.split('\n'):
                if '❌' in line and ':' in line:
                    step_name = line.split(':', 1)[0].strip().replace('❌', '').strip()
                    if step_name:
                        failed_steps.append({
                            'error': f'{step_name} 失败',
                            'error_type': 'manual_triage',
                            'priority': 'P2',
                            'fix': f'检查 {step_name} 步骤执行失败原因',
                            'success_criteria': f'{step_name} 执行成功',
                        })

        self.update_task(task_name, source_stage=normalized_stage)
        if failed_steps:
            self.create_fix_subtasks(task_name, failed_steps)
            return {
                'success': False,
                'action': 'fix_subtasks_created',
                'count': len(failed_steps),
            }

        self.mark_error_fix_pending(task_name, output[-200:] if output else '执行失败', 'error_type=manual_triage')
        return {
            'success': False,
            'action': 'single_fix_created',
        }

    def finalize_retrospective(self, task_name: str,
                               summary: str,
                               rca: Dict[str, Any] = None,
                               sop: Dict[str, Any] = None,
                               debt: Dict[str, Any] = None,
                               outcome: str = None) -> bool:
        """回写 retrospective 阶段产物。"""
        task = self.get_task(task_name)
        if not task:
            return False

        retrospective_payload = {
            'summary': summary,
            'decision': summary,
            'rca': rca or {},
            'sop': sop or {},
            'debt': debt or {},
        }
        if outcome:
            retrospective_payload['outcome'] = outcome

        self.upsert_stage_payload(
            task_name,
            TaskStage.RETROSPECTIVE.value,
            retrospective_payload,
            status=StageStatus.DONE.value,
            result=summary,
        )
        self.record_stage_artifact(
            task_name,
            TaskStage.RETROSPECTIVE.value,
            'retrospective_summary',
            {
                'summary': summary,
                'outcome': outcome,
                'rca': rca or {},
                'sop': sop or {},
                'debt': debt or {},
            },
        )
        return True
    
    def mark_requires_manual(self, task_name: str, reason: str = ""):
        """标记需要人工介入"""
        self.update_task(task_name,
            status='failed',
            exec_state='requires_manual',
            stage_status=StageStatus.BLOCKED.value,
            blocked_reason=reason,
            last_error=reason
        )
    
    def mark_normal_crash(self, task_name: str, error: str = ""):
        """标记正常崩溃（可重试）"""
        self.update_task(task_name,
            status='pending',
            exec_state='normal_crash',
            stage_status=StageStatus.RETRYABLE.value,
            last_error=error
        )
    
    # ========== 子任务管理 ==========
    def create_sub_task(self, parent_task_id: str, task_name: str, display_name: str, 
                       description: str = "", priority: str = "P0", 
                       fix_suggestion: str = "", initial_stage: str = None,
                       site_context: dict = None) -> bool:
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
        stage = self._infer_initial_stage(task_type, initial_stage=initial_stage)
        self.initialize_stage(task_name, stage=stage)
        if site_context:
            self.persist_task_site_context(task_name, stage, site_context, result='创建子任务时初始化站点上下文')
        return True
    
    def create_task(self, task_name: str, display_name: str, 
                   task_type: str = "常规", description: str = "",
                   priority: str = "P1", success_criteria: str = "",
                   initial_stage: str = None, site_context: dict = None) -> bool:
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
        stage = self._infer_initial_stage(task_type, success_criteria=success_criteria, initial_stage=initial_stage)
        self.initialize_stage(task_name, stage=stage)
        if site_context:
            self.persist_task_site_context(task_name, stage, site_context, result='创建任务时初始化站点上下文')
        return True

    # ========== 临时任务（TEMP）支持 ==========
    def create_temp_task(self, task_name: str, display_name: str,
                        description: str = "", expected_duration: int = 60,
                        priority: str = "P1", success_criteria: str = "",
                        initial_checkpoint: dict = None, initial_stage: str = None,
                        site_context: dict = None) -> bool:
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
        checkpoint_payload = dict(initial_checkpoint or {})
        if site_context:
            checkpoint_payload.setdefault('site_context', self._normalize_site_context(site_context, include_defaults=True))

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
            json.dumps(checkpoint_payload) if checkpoint_payload else None
        ))
        self.conn.commit()
        cur.close()
        normalized_initial_stage = self._normalize_stage(initial_stage)
        stage = normalized_initial_stage
        if not stage and self._looks_like_executable_temp_task(checkpoint_payload, description):
            stage = TaskStage.BUILD.value
        if not stage:
            stage = self._infer_initial_stage('临时任务', success_criteria=success_criteria, initial_stage=initial_stage)
        self.initialize_stage(task_name, stage=stage)
        if site_context:
            self.persist_task_site_context(task_name, stage, site_context, result='创建临时任务时初始化站点上下文')
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
            AND LOWER(COALESCE(exec_state, '')) = 'processing'
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
            stage_status=StageStatus.READY.value,
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
            AND LOWER(COALESCE(exec_state, '')) NOT IN ('end', 'void')
            ORDER BY 
                CASE LOWER(COALESCE(exec_state, '')) WHEN 'processing' THEN 1 WHEN 'new' THEN 2 ELSE 3 END,
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
                                        initial_checkpoint: dict = None,
                                        initial_stage: str = None,
                                        site_context: dict = None) -> dict:
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
            initial_checkpoint=initial_checkpoint,
            initial_stage=initial_stage,
            site_context=site_context,
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
                            steps: list = None,
                            site_context: dict = None) -> bool:
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
        self.initialize_stage(task_name, stage=TaskStage.PLAN.value)
        if site_context:
            self.persist_task_site_context(task_name, TaskStage.PLAN.value, site_context, result='创建工作流任务时初始化站点上下文')

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
            self.initialize_stage(step_name, stage=TaskStage.BUILD.value)
            merged_site_context = dict(site_context or {})
            if isinstance(step, dict) and step.get('site_context'):
                self._merge_site_context(merged_site_context, step.get('site_context'))
            if merged_site_context:
                self.persist_task_site_context(step_name, TaskStage.BUILD.value, merged_site_context, result='创建工作流步骤时初始化站点上下文')

            print(f"  创建工作流步骤: {step_display} ({step_name})")

        return True

    def create_workflow_steps(self, parent_task_id: str, steps: list, priority: str = "P0",
                              site_context: dict = None) -> bool:
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
            self.initialize_stage(step_name, stage=TaskStage.BUILD.value)
            merged_site_context = dict(site_context or {})
            if isinstance(step, dict) and step.get('site_context'):
                self._merge_site_context(merged_site_context, step.get('site_context'))
            if merged_site_context:
                self.persist_task_site_context(step_name, TaskStage.BUILD.value, merged_site_context, result='创建工作流步骤时初始化站点上下文')

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

