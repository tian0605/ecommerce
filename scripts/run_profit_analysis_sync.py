#!/usr/bin/env python3
"""Fixed entry for SKU-level profit analysis sync."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
ANALYZER = WORKSPACE / 'skills' / 'profit-analyzer' / 'analyzer.py'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='一键重算利润分析并同步飞书')
    parser.add_argument('alibaba_ids', nargs='*', help='1688 商品 ID 列表')
    parser.add_argument('--ids', help='逗号分隔的 1688 商品 ID 列表')
    parser.add_argument('--profit-rate', type=float, default=0.20, help='目标利润率，默认 0.20')
    return parser.parse_args()


def normalize_ids(args: argparse.Namespace) -> list[str]:
    items: list[str] = []
    if args.ids:
        items.extend([part.strip() for part in args.ids.split(',') if part.strip()])
    items.extend([item.strip() for item in args.alibaba_ids if item.strip()])
    unique: list[str] = []
    seen = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def main() -> int:
    args = parse_args()
    alibaba_ids = normalize_ids(args)
    if not alibaba_ids:
        print('请提供至少一个 1688 商品 ID', file=sys.stderr)
        return 1

    cmd = [
        sys.executable,
        str(ANALYZER),
        '--alibaba-ids',
        *alibaba_ids,
        '--profit-rate',
        str(args.profit_rate),
    ]
    completed = subprocess.run(cmd, cwd=str(WORKSPACE))
    return completed.returncode


if __name__ == '__main__':
    raise SystemExit(main())