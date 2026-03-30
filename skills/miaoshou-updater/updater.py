#!/usr/bin/env python3
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent
if str(SKILLS_DIR) not in sys.path:
    sys.path.insert(0, str(SKILLS_DIR))

from miaoshou_updater.updater import MiaoshouUpdater, main

__all__ = ['MiaoshouUpdater', 'main']


if __name__ == '__main__':
    main()