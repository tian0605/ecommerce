#!/usr/bin/env python3
"""获取下一个待执行的任务"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace-e-commerce/scripts')

from task_manager import TaskManager, ExecState

tm = TaskManager()
actionable = tm.get_actionable_tasks()
tm.close()

if not actionable:
    print("无待执行任务")
else:
    print(f"待执行任务 ({len(actionable)}):")
    for t in actionable[:3]:
        state_emoji = {
            ExecState.ERROR_FIX_PENDING: "🔧",
            ExecState.NORMAL_CRASH: "🔄",
            ExecState.REQUIRES_MANUAL: "👤",
            ExecState.NEW: "🆕"
        }.get(t['exec_state'], "❓")
        print(f"  {state_emoji} {t['display_name']}")
