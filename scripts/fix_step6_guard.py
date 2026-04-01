#!/usr/bin/env python3
"""Shared safety guard for ad-hoc Step6 repair scripts."""

import os
import sys


UNSAFE_ENV_FLAG = 'ALLOW_UNSAFE_STEP6_FIX'


def require_step6_guard(script_path: str, destructive: bool) -> None:
    script_name = os.path.basename(script_path)
    if not destructive:
        print(f"[guard] {script_name}: readonly mode enabled", file=sys.stderr)
        return

    if os.getenv(UNSAFE_ENV_FLAG) == '1':
        print(
            f"[guard] {script_name}: destructive mode explicitly unlocked via {UNSAFE_ENV_FLAG}=1",
            file=sys.stderr,
        )
        return

    print(
        f"[guard] blocked destructive Step6 script: {script_name}\n"
        f"[guard] This script can publish products or write product status.\n"
        f"[guard] To run it intentionally, export {UNSAFE_ENV_FLAG}=1 and rerun.\n"
        f"[guard] Prefer readonly verification scripts unless a real repair is required.",
        file=sys.stderr,
    )
    raise SystemExit(2)