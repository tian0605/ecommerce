#!/usr/bin/env python3
"""Normalize legacy task state values in the tasks table.

This script repairs historical mixed-case or inconsistent lifecycle values such as
`VOID`, `END`, uppercase stage statuses, and stale status/is_void combinations.

Default mode is dry-run. Use `--apply` to persist changes.

Examples:
  python3 scripts/normalize_task_state_values.py
  python3 scripts/normalize_task_state_values.py --apply
  python3 scripts/normalize_task_state_values.py --apply --task-name TEMP-LISTING-20260404-04
  python3 scripts/normalize_task_state_values.py --apply --prefix FIX-
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

import psycopg2

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
sys.path.insert(0, str(WORKSPACE / 'scripts'))

from task_manager import TaskManager  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='规范化 tasks 表中的历史脏状态值，默认 dry-run。'
    )
    parser.add_argument('--apply', action='store_true', help='实际写回数据库；默认仅输出将要修复的内容')
    parser.add_argument('--task-name', help='仅处理单个任务名')
    parser.add_argument('--prefix', help='仅处理指定 task_name 前缀')
    parser.add_argument('--limit', type=int, default=0, help='限制检查的任务数量，0 表示不限制')
    parser.add_argument('--verbose', action='store_true', help='输出每条任务的字段修复明细')
    return parser


def desired_values(tm: TaskManager, task: Dict) -> Dict[str, object]:
    exec_state = tm._normalize_exec_state(task.get('exec_state'))
    stage = tm._normalize_stage(task.get('current_stage')) or task.get('current_stage')
    stage_status = tm._normalize_stage_status(task.get('stage_status'))

    if exec_state == 'void':
        stage_status = tm._infer_stage_status_from_exec_state(exec_state)
    elif stage_status is None and exec_state:
        stage_status = tm._infer_stage_status_from_exec_state(exec_state)

    status = tm._normalize_status_for_state(exec_state, task.get('status'))

    desired = {
        'exec_state': exec_state,
        'current_stage': stage,
        'stage_status': stage_status,
        'status': status,
    }

    if exec_state == 'void':
        desired['is_void'] = True

    return desired


def diff_task(tm: TaskManager, task: Dict) -> Dict[str, object]:
    updates: Dict[str, object] = {}
    desired = desired_values(tm, task)
    for field, value in desired.items():
        if field == 'is_void':
            if task.get('is_void') is not True:
                updates[field] = value
            continue
        if value is None:
            continue
        current = task.get(field)
        if current != value:
            updates[field] = value
    return updates


def fetch_candidates(tm: TaskManager, task_name: Optional[str], prefix: Optional[str], limit: int) -> List[Dict]:
    cur = tm.conn.cursor()
    clauses = []
    params: List[object] = []

    if task_name:
        clauses.append('task_name = %s')
        params.append(task_name)
    if prefix:
        clauses.append('task_name LIKE %s')
        params.append(f'{prefix}%')

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ''
    sql = f"""
        SELECT * FROM tasks
        {where}
        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, task_name
    """
    if limit and limit > 0:
        sql += ' LIMIT %s'
        params.append(limit)

    cur.execute(sql, params)
    cols = [desc[0] for desc in cur.description]
    rows = [tm._hydrate_task_row(dict(zip(cols, row))) for row in cur.fetchall()]
    cur.close()
    return rows


def main() -> int:
    args = build_parser().parse_args()
    tm = TaskManager()

    candidates = fetch_candidates(tm, args.task_name, args.prefix, args.limit)
    dirty: List[tuple[Dict, Dict[str, object]]] = []

    for task in candidates:
        updates = diff_task(tm, task)
        if updates:
            dirty.append((task, updates))

    print(f'扫描任务数: {len(candidates)}')
    print(f'发现需规范化任务数: {len(dirty)}')

    if not dirty:
        tm.conn.close()
        return 0

    for task, updates in dirty:
        summary = ', '.join(f'{key}: {task.get(key)!r} -> {value!r}' for key, value in updates.items())
        print(f"- {task['task_name']}: {summary}")
        if args.apply:
            tm.update_task(task['task_name'], **updates)
        if not args.verbose and len(dirty) >= 20 and not args.apply:
            # keep dry-run output readable on large batches
            remaining = len(dirty) - dirty.index((task, updates)) - 1
            if remaining > 0:
                print(f'... 还有 {remaining} 条待规范化任务，使用 --verbose 查看全部明细')
                break

    if args.apply:
        print(f'已写回 {len(dirty)} 条任务')
    else:
        print('dry-run 完成；添加 --apply 才会写回数据库')

    tm.conn.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())