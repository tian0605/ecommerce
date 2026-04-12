#!/usr/bin/env python3
"""Backfill agent attribution for tasks, logs, and heartbeat events."""
from __future__ import annotations

import json

from agent_attribution import run_backfill


def main() -> int:
    result = run_backfill()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())