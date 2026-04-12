#!/usr/bin/env python3
"""Collect, render, and optionally persist structured heartbeat events."""
from __future__ import annotations

import argparse
import json
import socket
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List

import psycopg2
from psycopg2.extras import Json, RealDictCursor

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
sys.path.insert(0, str(WORKSPACE / 'scripts'))

from task_manager import TaskManager
from agent_attribution import ensure_seed_data, resolve_record

DB_CONFIG = {
    'host': 'localhost',
    'database': 'ecommerce_data',
    'user': 'superuser',
    'password': 'Admin123!',
}


@dataclass
class HeartbeatSnapshot:
    report: str
    payload: Dict[str, Any]


def query_scalar(cur, sql: str, params=None, default=0):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    if not row or row[0] is None:
        return default
    return row[0]


def fetch_agent_id(cur, code: str) -> int | None:
    cur.execute("SELECT id FROM agents WHERE code = %s", (code,))
    row = cur.fetchone()
    return row[0] if row else None


def collect_snapshot() -> HeartbeatSnapshot:
    started = perf_counter()
    tm = TaskManager()
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    actionable = tm.get_actionable_tasks(limit=50)
    p0_tasks = [t for t in actionable if t.get('priority') == 'P0']
    p1_tasks = [t for t in actionable if t.get('priority') == 'P1']
    p2_tasks = [t for t in actionable if t.get('priority') == 'P2']

    cur.execute(
        """
        SELECT task_name, exec_state, last_executed_at
        FROM tasks
        WHERE LOWER(COALESCE(exec_state, '')) = 'processing'
        ORDER BY updated_at DESC
        """
    )
    processing = cur.fetchall()

    cur.execute(
        """
        SELECT task_name, display_name, fix_suggestion
        FROM tasks
        WHERE LOWER(COALESCE(exec_state, '')) = 'requires_manual'
        ORDER BY updated_at DESC
        """
    )
    manual_tasks = cur.fetchall()

    overtime_temp = tm.get_overtime_temp_tasks(buffer_minutes=10)
    for task in overtime_temp:
        tm.reactivate_temp_task(task['task_name'])

    cur.execute(
        """
        SELECT run_status, COUNT(*)
        FROM main_logs
        WHERE created_at > NOW() - INTERVAL '24 hours'
        GROUP BY run_status
        """
    )
    stats = {row[0]: row[1] for row in cur.fetchall()}

    cur.execute(
        """
        SELECT task_name, exec_state, retry_count, last_error
        FROM tasks
        WHERE LOWER(COALESCE(exec_state, '')) IN ('error_fix_pending', 'normal_crash')
          AND updated_at > NOW() - INTERVAL '24 hours'
        ORDER BY updated_at DESC
        LIMIT 5
        """
    )
    failed_recent = cur.fetchall()

    cur.execute(
        """
        SELECT COALESCE(current_stage, 'unknown') AS stage, COUNT(*)
        FROM tasks
        GROUP BY COALESCE(current_stage, 'unknown')
        ORDER BY stage ASC
        """
    )
    stage_distribution = {row[0]: row[1] for row in cur.fetchall()}

    cur.execute(
        """
        SELECT COALESCE(stage_status, 'unknown') AS stage_status, COUNT(*)
        FROM tasks
        GROUP BY COALESCE(stage_status, 'unknown')
        ORDER BY stage_status ASC
        """
    )
    stage_status_distribution = {row[0]: row[1] for row in cur.fetchall()}

    total_tasks = len(p0_tasks) + len(p1_tasks) + len(p2_tasks)
    processing_count = len(processing)
    manual_count = len(manual_tasks)
    overtime_count = len(overtime_temp)
    failed_recent_count = len(failed_recent)

    heartbeat_status = 'ok'
    if p0_tasks or manual_count or overtime_count:
        heartbeat_status = 'critical'
    elif p1_tasks or failed_recent_count:
        heartbeat_status = 'warning'

    lines: List[str] = []
    lines.append('💓 CommerceFlow 心跳报告')
    lines.append('')
    lines.append('📋 第一问：有没有需要处理的任务？')

    if p0_tasks:
        lines.append('')
        lines.append(f'🔴 P0 立即处理 ({len(p0_tasks)} 个)')
        for task in p0_tasks:
            lines.append(f"  - {task['task_name']} ({task.get('display_name', '')}) - {task['exec_state']}")

    if p1_tasks:
        lines.append('')
        lines.append(f'🟡 P1 今天处理 ({len(p1_tasks)} 个)')
        for task in p1_tasks[:5]:
            lines.append(f"  - {task['task_name']}")

    if p2_tasks:
        lines.append('')
        lines.append(f'🟢 P2 本周优化 ({len(p2_tasks)} 个)')

    if manual_tasks:
        lines.append('')
        lines.append(f'🚨 需要人工介入 ({len(manual_tasks)} 个)')
        for task_name, _, fix_suggestion in manual_tasks[:3]:
            lines.append(f"  - {task_name}: {str(fix_suggestion)[:50] if fix_suggestion else ''}")

    if overtime_temp:
        lines.append('')
        lines.append(f'⏰ 临时任务超时 ({len(overtime_temp)} 个)')
        for task in overtime_temp[:5]:
            checkpoint = task.get('progress_checkpoint', {})
            if isinstance(checkpoint, str):
                try:
                    checkpoint = json.loads(checkpoint)
                except Exception:
                    checkpoint = {}
            current_step = checkpoint.get('current_step', '未知') if checkpoint else '未知'
            lines.append(f"  - {task['task_name']}: 超时{int(task.get('overtime_minutes', 0))}分钟 | 当前: {current_step}")

    lines.append('')
    lines.append('----------')
    lines.append('')
    lines.append('📊 第二问：任务执行是否顺畅？')
    lines.append('')
    lines.append('执行统计（24小时）：')
    lines.append(f"  🔄 running: {stats.get('running', 0)}")
    lines.append(f"  ✅ success: {stats.get('success', 0)}")
    lines.append(f"  ❌ failed: {stats.get('failed', 0)}")
    lines.append(f"  👀 following: {stats.get('following', 0)}")
    lines.append(f"  ⏭️  skipped: {stats.get('skipped', 0)}")

    if failed_recent:
        lines.append('')
        lines.append('⚠️ 最近失败任务：')
        for task_name, exec_state, retry_count, _ in failed_recent[:3]:
            lines.append(f"  - {task_name} ({exec_state}, retry={retry_count})")

    lines.append('')
    lines.append('🧭 生命周期阶段分布：')
    for stage_name, count in sorted(stage_distribution.items()):
        lines.append(f"  - {stage_name}: {count}")

    lines.append('')
    lines.append('🚦 阶段状态分布：')
    for stage_name, count in sorted(stage_status_distribution.items()):
        lines.append(f"  - {stage_name}: {count}")

    lines.append('')
    lines.append('----------')
    lines.append('')
    lines.append(
        f'📈 汇总：待处理:{total_tasks} | 运行中:{processing_count} | 需人工:{manual_count} | 超时TEMP:{overtime_count}'
    )

    if total_tasks == 0 and processing_count == 0 and manual_count == 0 and overtime_count == 0:
        lines.append('')
        lines.append('HEARTBEAT_OK | 待处理:0 | 运行中:0 | 需要人工:0')

    duration_ms = int((perf_counter() - started) * 1000)
    report = '\n'.join(lines)
    payload = {
        'heartbeat_status': heartbeat_status,
        'summary': lines[-1],
        'pending_count': total_tasks,
        'processing_count': processing_count,
        'requires_manual_count': manual_count,
        'overtime_temp_count': overtime_count,
        'failed_recent_count': failed_recent_count,
        'duration_ms': duration_ms,
        'stats_24h': stats,
        'p0_tasks': [task['task_name'] for task in p0_tasks],
        'p1_tasks': [task['task_name'] for task in p1_tasks],
        'p2_tasks': [task['task_name'] for task in p2_tasks],
        'manual_tasks': [row[0] for row in manual_tasks],
        'overtime_tasks': [task['task_name'] for task in overtime_temp],
        'failed_recent': [row[0] for row in failed_recent],
        'stage_distribution': stage_distribution,
        'stage_status_distribution': stage_status_distribution,
        'host_name': socket.gethostname(),
        'report_time': datetime.now().isoformat(),
    }

    cur.close()
    conn.close()
    tm.close()
    return HeartbeatSnapshot(report=report, payload=payload)


def persist_snapshot(snapshot: HeartbeatSnapshot) -> None:
    ensure_seed_data()
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    attribution = resolve_record(cur, 'heartbeat', {'source': 'dev-heartbeat.sh', 'payload': snapshot.payload, 'summary': snapshot.payload['summary'], 'raw_report': snapshot.report})
    cur.execute(
        """
        INSERT INTO heartbeat_events (
            agent_id, source, heartbeat_status, summary, raw_report, payload,
            pending_count, processing_count, requires_manual_count,
            overtime_temp_count, failed_recent_count, duration_ms,
            host_name, report_time
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            attribution.agent_id,
            'dev-heartbeat.sh',
            snapshot.payload['heartbeat_status'],
            snapshot.payload['summary'],
            snapshot.report,
            Json(snapshot.payload),
            snapshot.payload['pending_count'],
            snapshot.payload['processing_count'],
            snapshot.payload['requires_manual_count'],
            snapshot.payload['overtime_temp_count'],
            snapshot.payload['failed_recent_count'],
            snapshot.payload['duration_ms'],
            snapshot.payload['host_name'],
            snapshot.payload['report_time'],
        ),
    )

    metric_rows = []
    for stage_name, count in (snapshot.payload.get('stage_distribution') or {}).items():
        metric_rows.append(('task-lifecycle', None, f'tasks.stage.{stage_name}', 'current', count, {'dimension': 'current_stage', 'name': stage_name}))
    for status_name, count in (snapshot.payload.get('stage_status_distribution') or {}).items():
        metric_rows.append(('task-lifecycle', None, f'tasks.stage_status.{status_name}', 'current', count, {'dimension': 'stage_status', 'name': status_name}))
    metric_rows.extend([
        ('task-lifecycle', None, 'tasks.requires_manual', 'current', snapshot.payload['requires_manual_count'], {'dimension': 'exec_state'}),
        ('task-lifecycle', None, 'tasks.processing', 'current', snapshot.payload['processing_count'], {'dimension': 'exec_state'}),
        ('task-lifecycle', None, 'tasks.overtime_temp', 'current', snapshot.payload['overtime_temp_count'], {'dimension': 'temp'}),
    ])

    for metric_scope, agent_id, metric_name, metric_window, metric_value, metric_payload in metric_rows:
        cur.execute(
            """
            INSERT INTO dashboard_metrics (
                metric_scope, agent_id, metric_name, metric_window,
                metric_value, metric_payload, calculated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (metric_scope, agent_id, metric_name, metric_window)
            DO UPDATE SET
                metric_value = EXCLUDED.metric_value,
                metric_payload = EXCLUDED.metric_payload,
                calculated_at = CURRENT_TIMESTAMP
            """,
            (
                metric_scope,
                agent_id,
                metric_name,
                metric_window,
                metric_value,
                Json(metric_payload),
            ),
        )
    conn.commit()
    cur.close()
    conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description='Collect and persist structured heartbeat events.')
    parser.add_argument('--format', choices=('text', 'json'), default='text')
    parser.add_argument('--persist', action='store_true')
    args = parser.parse_args()

    snapshot = collect_snapshot()
    if args.persist:
        persist_snapshot(snapshot)

    if args.format == 'json':
        print(json.dumps(snapshot.payload, ensure_ascii=False, indent=2))
    else:
        print(snapshot.report)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())