#!/usr/bin/env python3
"""Reusable agent attribution engine for tasks, logs, and heartbeat events."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    'host': 'localhost',
    'database': 'ecommerce_data',
    'user': 'superuser',
    'password': 'Admin123!',
}

ATTRIBUTION_VERSION = 'v1'

AGENT_DEFINITIONS = [
    ('workflow-runner', 'Workflow Runner', 'workflow', '负责常规工作流任务执行'),
    ('fix-executor', 'Fix Executor', 'fixer', '负责修复类任务执行'),
    ('heartbeat-monitor', 'Heartbeat Monitor', 'monitor', '负责心跳采集与监控'),
    ('temp-agent', 'Temp Agent', 'temp', '负责临时任务执行'),
    ('collector-scraper', 'Collector Scraper', 'collector', '负责采集箱商品提取'),
    ('local-1688-weight', 'Local 1688 Weight', 'collector', '负责1688重量尺寸获取'),
    ('product-storer', 'Product Storer', 'workflow', '负责商品与SKU落库'),
    ('listing-optimizer', 'Listing Optimizer', 'workflow', '负责标题描述优化'),
    ('miaoshou-updater', 'Miaoshou Updater', 'updater', '负责妙手ERP回写与发布'),
    ('profit-analyzer', 'Profit Analyzer', 'workflow', '负责利润分析'),
    ('system-unclassified', 'System Unclassified', 'system', '无法确定归因时的兜底 agent'),
]

SKILL_AGENT_MAP = {
    'miaoshou-collector': 'workflow-runner',
    'collector-scraper': 'collector-scraper',
    'local-1688-weight': 'local-1688-weight',
    'product-storer': 'product-storer',
    'listing-optimizer': 'listing-optimizer',
    'miaoshou-updater': 'miaoshou-updater',
    'profit-analyzer': 'profit-analyzer',
    'manual-triage': 'fix-executor',
}

ERROR_TYPE_AGENT_MAP = {
    'publish_flow': 'miaoshou-updater',
    'validation_error': 'miaoshou-updater',
    'collection_flow': 'workflow-runner',
    'scrape_flow': 'collector-scraper',
    'weight_service': 'local-1688-weight',
    'storage_flow': 'product-storer',
    'optimization_flow': 'listing-optimizer',
    'profit_flow': 'profit-analyzer',
    'manual_triage': 'fix-executor',
}

DEFAULT_RULES = [
    ('task-auto-listing-prefix', 'task', 'prefix', 'task_name', 'AUTO-LISTING', 'workflow-runner', 100, 'AUTO-LISTING 任务归属于 workflow-runner'),
    ('task-fix-prefix', 'task', 'prefix', 'task_name', 'FIX-', 'fix-executor', 110, 'FIX- 任务归属于 fix-executor'),
    ('task-temp-type', 'task', 'field_equals', 'task_type', '临时任务', 'temp-agent', 120, '临时任务归属于 temp-agent'),
    ('log-heartbeat-type', 'log', 'field_equals', 'log_type', 'heartbeat', 'heartbeat-monitor', 100, 'heartbeat 类型日志归属于 heartbeat-monitor'),
    ('task-updater-skill', 'task', 'field_contains', 'fix_suggestion', 'miaoshou-updater', 'miaoshou-updater', 130, '更新回写任务归属于 miaoshou-updater'),
    ('task-scraper-skill', 'task', 'field_contains', 'fix_suggestion', 'collector-scraper', 'collector-scraper', 131, '采集提取任务归属于 collector-scraper'),
    ('task-profit-skill', 'task', 'field_contains', 'fix_suggestion', 'profit-analyzer', 'profit-analyzer', 132, '利润分析任务归属于 profit-analyzer'),
]

FIELD_CANDIDATES = {
    'task': ('plan', 'fix_suggestion', 'description', 'display_name', 'task_name', 'task_type', 'last_error'),
    'log': ('run_message', 'run_content', 'task_name', 'log_type'),
    'heartbeat': ('summary', 'raw_report', 'source'),
}


@dataclass
class AttributionResult:
    agent_id: Optional[int]
    agent_code: str
    source: str
    matched_rule_id: Optional[int] = None
    matched_rule_name: Optional[str] = None


def _get_conn():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _extract_structured_metadata(record: Dict[str, Any], scope: str) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    for field in FIELD_CANDIDATES.get(scope, ()):
        raw = _normalize_text(record.get(field))
        if not raw:
            continue
        parts = re.split(r'[;\n]+', raw)
        for part in parts:
            if '=' not in part:
                continue
            key, value = part.split('=', 1)
            key = key.strip().lower()
            value = value.strip()
            if key and value and key not in metadata:
                metadata[key] = value
    payload = record.get('payload')
    if isinstance(payload, dict):
        for key in ('error_type', 'skill', 'action', 'source'):
            if payload.get(key) and key not in metadata:
                metadata[key] = str(payload[key]).strip()
    return metadata


def ensure_seed_data() -> None:
    with _get_conn() as conn:
        cur = conn.cursor()
        for code, name, agent_type, description in AGENT_DEFINITIONS:
            cur.execute(
                """
                INSERT INTO agents (code, name, type, owner, description)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    type = EXCLUDED.type,
                    description = EXCLUDED.description,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (code, name, agent_type, 'system', description),
            )
        conn.commit()

        cur.execute("SELECT id, code FROM agents")
        code_to_id = {row['code']: row['id'] for row in cur.fetchall()}

        for rule_name, match_scope, match_type, match_field, match_expr, agent_code, priority, notes in DEFAULT_RULES:
            cur.execute(
                """
                INSERT INTO agent_attribution_rules (
                    rule_name, match_scope, match_type, match_field, match_expr,
                    agent_id, priority, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (rule_name) DO UPDATE SET
                    match_scope = EXCLUDED.match_scope,
                    match_type = EXCLUDED.match_type,
                    match_field = EXCLUDED.match_field,
                    match_expr = EXCLUDED.match_expr,
                    agent_id = EXCLUDED.agent_id,
                    priority = EXCLUDED.priority,
                    notes = EXCLUDED.notes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (rule_name, match_scope, match_type, match_field, match_expr, code_to_id[agent_code], priority, notes),
            )
        conn.commit()


def load_agent_catalog(cur) -> Tuple[Dict[str, int], Dict[int, str]]:
    cur.execute("SELECT id, code FROM agents")
    rows = cur.fetchall()
    code_to_id = {row['code']: row['id'] for row in rows}
    id_to_code = {row['id']: row['code'] for row in rows}
    return code_to_id, id_to_code


def load_rules(cur, scope: str) -> List[Dict[str, Any]]:
    cur.execute(
        """
        SELECT r.id, r.rule_name, r.match_scope, r.match_type, r.match_field, r.match_expr,
               r.agent_id, r.priority, r.stop_on_match, a.code AS agent_code
        FROM agent_attribution_rules r
        JOIN agents a ON a.id = r.agent_id
        WHERE r.enabled = TRUE
          AND r.match_scope IN (%s, 'universal')
        ORDER BY r.priority ASC, r.id ASC
        """,
        (scope,),
    )
    return list(cur.fetchall())


def _field_value(record: Dict[str, Any], field: Optional[str]) -> str:
    if not field:
        return ''
    if field.startswith('payload.'):
        payload = record.get('payload') or {}
        if isinstance(payload, dict):
            return _normalize_text(payload.get(field.split('.', 1)[1]))
        return ''
    return _normalize_text(record.get(field))


def _match_rule(rule: Dict[str, Any], record: Dict[str, Any]) -> bool:
    value = _field_value(record, rule.get('match_field'))
    expr = _normalize_text(rule.get('match_expr'))
    match_type = rule.get('match_type')
    if match_type == 'field_equals':
        return value == expr
    if match_type == 'field_contains':
        return expr.lower() in value.lower()
    if match_type == 'prefix':
        return value.startswith(expr)
    if match_type == 'regex':
        return re.search(expr, value, re.IGNORECASE) is not None
    return False


def resolve_record(
    cur,
    scope: str,
    record: Dict[str, Any],
    parent_result: Optional[AttributionResult] = None,
    root_result: Optional[AttributionResult] = None,
) -> AttributionResult:
    code_to_id, id_to_code = load_agent_catalog(cur)
    explicit_agent_id = record.get('agent_id')
    if explicit_agent_id:
        return AttributionResult(explicit_agent_id, id_to_code.get(explicit_agent_id, 'system-unclassified'), 'explicit')

    metadata = _extract_structured_metadata(record, scope)
    skill = metadata.get('skill', '').strip()
    error_type = metadata.get('error_type', '').strip().lower()

    if skill in SKILL_AGENT_MAP:
        agent_code = SKILL_AGENT_MAP[skill]
        return AttributionResult(code_to_id.get(agent_code), agent_code, 'structured')

    if error_type in ERROR_TYPE_AGENT_MAP:
        agent_code = ERROR_TYPE_AGENT_MAP[error_type]
        return AttributionResult(code_to_id.get(agent_code), agent_code, 'structured')

    if parent_result and parent_result.agent_id:
        return AttributionResult(parent_result.agent_id, parent_result.agent_code, 'parent_inherit')

    if root_result and root_result.agent_id:
        return AttributionResult(root_result.agent_id, root_result.agent_code, 'root_inherit')

    for rule in load_rules(cur, scope):
        if _match_rule(rule, record):
            return AttributionResult(rule['agent_id'], rule['agent_code'], 'rule', rule['id'], rule['rule_name'])

    if scope == 'task':
        task_type = _normalize_text(record.get('task_type'))
        if task_type == '修复':
            return AttributionResult(code_to_id.get('fix-executor'), 'fix-executor', 'rule')
        if task_type == '临时任务':
            return AttributionResult(code_to_id.get('temp-agent'), 'temp-agent', 'rule')
    if scope == 'log' and _normalize_text(record.get('log_type')) == 'heartbeat':
        return AttributionResult(code_to_id.get('heartbeat-monitor'), 'heartbeat-monitor', 'rule')
    if scope == 'heartbeat':
        return AttributionResult(code_to_id.get('heartbeat-monitor'), 'heartbeat-monitor', 'rule')

    return AttributionResult(code_to_id.get('system-unclassified'), 'system-unclassified', 'fallback_unknown')


def backfill_tasks(cur) -> int:
    cur.execute(
        """
        SELECT *
        FROM tasks
        ORDER BY task_level ASC, created_at ASC, task_name ASC
        """
    )
    tasks = list(cur.fetchall())
    task_results: Dict[str, AttributionResult] = {}
    updated = 0
    for task in tasks:
        parent_result = task_results.get(task.get('parent_task_id'))
        root_result = task_results.get(task.get('root_task_id'))
        result = resolve_record(cur, 'task', task, parent_result=parent_result, root_result=root_result)
        task_results[task['task_name']] = result
        if task.get('agent_id') != result.agent_id or task.get('attribution_source') != result.source or task.get('attribution_version') != ATTRIBUTION_VERSION:
            cur.execute(
                """
                UPDATE tasks
                SET agent_id = %s,
                    attribution_source = %s,
                    attribution_version = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE task_name = %s
                """,
                (result.agent_id, result.source, ATTRIBUTION_VERSION, task['task_name']),
            )
            updated += 1
    return updated


def backfill_logs(cur) -> int:
    cur.execute(
        """
        SELECT l.*,
               t.parent_task_id,
               t.root_task_id,
               t.agent_id AS task_agent_id
        FROM main_logs l
        LEFT JOIN tasks t ON t.task_name = l.task_name
        ORDER BY l.id ASC
        """
    )
    logs = list(cur.fetchall())
    task_map: Dict[str, Dict[str, Any]] = {}
    cur.execute("SELECT task_name, agent_id FROM tasks")
    for task in cur.fetchall():
        task_map[task['task_name']] = task

    def resolve_task_from_truncated_name(task_name: str) -> Optional[Dict[str, Any]]:
        if not task_name:
            return None
        exact = task_map.get(task_name)
        if exact:
            return exact
        matches = [task for name, task in task_map.items() if name.startswith(task_name)]
        if len(matches) == 1:
            return matches[0]
        return None

    updated = 0
    for log in logs:
        parent_result = None
        root_result = None
        matched_task = resolve_task_from_truncated_name(log.get('task_name'))
        if matched_task:
            task_agent_id = matched_task['agent_id']
            if task_agent_id:
                parent_result = AttributionResult(task_agent_id, '', 'parent_inherit')
        result = resolve_record(cur, 'log', log, parent_result=parent_result, root_result=root_result)
        if log.get('agent_id') != result.agent_id or log.get('attribution_source') != result.source or log.get('attribution_version') != ATTRIBUTION_VERSION:
            cur.execute(
                """
                UPDATE main_logs
                SET agent_id = %s,
                    attribution_source = %s,
                    attribution_version = %s
                WHERE id = %s
                """,
                (result.agent_id, result.source, ATTRIBUTION_VERSION, log['id']),
            )
            updated += 1
    return updated


def backfill_heartbeats(cur) -> int:
    cur.execute("SELECT * FROM heartbeat_events ORDER BY id ASC")
    rows = list(cur.fetchall())
    updated = 0
    for row in rows:
        result = resolve_record(cur, 'heartbeat', row)
        if row.get('agent_id') != result.agent_id:
            cur.execute(
                "UPDATE heartbeat_events SET agent_id = %s WHERE id = %s",
                (result.agent_id, row['id']),
            )
            updated += 1
    return updated


def run_backfill() -> Dict[str, int]:
    ensure_seed_data()
    with _get_conn() as conn:
        cur = conn.cursor()
        task_updates = backfill_tasks(cur)
        log_updates = backfill_logs(cur)
        heartbeat_updates = backfill_heartbeats(cur)
        conn.commit()
    return {
        'tasks_updated': task_updates,
        'logs_updated': log_updates,
        'heartbeats_updated': heartbeat_updates,
    }


__all__ = [
    'ATTRIBUTION_VERSION',
    'AttributionResult',
    'ensure_seed_data',
    'resolve_record',
    'run_backfill',
]