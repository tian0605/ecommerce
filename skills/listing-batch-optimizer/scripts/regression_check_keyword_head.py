"""Keyword-head regression check for listing batch optimizer.

This script re-runs a small set of representative Excel rows through the live
generation path and verifies that title keywords appear in the description
head after the keyword-head reinforcement step.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List


WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
OPTIMIZER_PATH = WORKSPACE / 'skills/listing-batch-optimizer/scripts/listing_batch_optimizer.py'


def load_optimizer_module() -> Any:
    spec = importlib.util.spec_from_file_location('listing_batch_optimizer', OPTIMIZER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'无法加载模块: {OPTIMIZER_PATH}')

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_rows(raw: str) -> List[int]:
    rows: List[int] = []
    for part in raw.split(','):
        item = part.strip()
        if not item:
            continue
        rows.append(int(item))
    if not rows:
        raise ValueError('至少需要一个行号')
    return rows


def run_regression(input_xlsx: Path, rows: List[int], repeats: int, sheet_name: str | None) -> int:
    mod = load_optimizer_module()
    optimizer = mod.ListingBatchOptimizer()
    failures: List[Dict[str, Any]] = []

    try:
        with optimizer._open_workbook(input_xlsx) as workbook:
            sheet = workbook[sheet_name] if sheet_name else workbook.active
            if sheet is None:
                raise RuntimeError('未找到可用工作表')

            columns = optimizer._resolve_excel_columns(sheet)

            for row in rows:
                product = optimizer._build_excel_product(sheet, row, columns)
                info = optimizer._extract_product_info(product)

                for attempt in range(1, repeats + 1):
                    title = optimizer._generate_title(product, info)
                    prompt_product = dict(product)
                    prompt_product['optimized_title'] = title
                    description = optimizer._generate_description(prompt_product, info) or ''
                    missing = mod.missing_keywords_in_head(description, title)
                    valid, reason = optimizer._validate_description(description, title)

                    title_keywords = mod.extract_keywords(title, limit=4)
                    print(
                        f'[row={row} attempt={attempt}] '
                        f'keywords={title_keywords} missing={missing} '
                        f'valid={valid} title_len={len(title)} desc_len={len(description)}'
                    )

                    if not valid:
                        failures.append(
                            {
                                'row': row,
                                'attempt': attempt,
                                'reason': reason,
                                'missing': missing,
                                'title': title,
                                'desc_head': description[:180],
                            }
                        )

    finally:
        optimizer.close()

    print('\n=== 回归摘要 ===')
    print(f'input_xlsx={input_xlsx}')
    print(f'rows={rows}')
    print(f'repeats={repeats}')
    print(f'failures={len(failures)}')

    if failures:
        for item in failures:
            print(
                f"FAIL row={item['row']} attempt={item['attempt']} reason={item['reason']} "
                f"missing={item['missing']}"
            )
            print(f"title={item['title']}")
            print(f"desc_head={item['desc_head']}")
            print()
        return 1

    print('PASS: 所有回归样例均通过关键词头部校验')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='关键词头部补强回归检查')
    parser.add_argument(
        '--input-xlsx',
        default='/root/Documents/mass_update_global_sku_basic_info_5607062_20260404211907.xlsx',
        help='输入 Excel 模板路径',
    )
    parser.add_argument(
        '--rows',
        default='7,11',
        help='要检查的行号，逗号分隔；默认 7,11，覆盖长关键词和历史失败样例',
    )
    parser.add_argument('--repeats', type=int, default=3, help='每行重复生成次数，默认 3')
    parser.add_argument('--sheet-name', help='可选：指定工作表名称')
    args = parser.parse_args()

    input_xlsx = Path(args.input_xlsx)
    if not input_xlsx.exists():
        print(f'文件不存在: {input_xlsx}', file=sys.stderr)
        return 2

    rows = parse_rows(args.rows)
    return run_regression(input_xlsx, rows, args.repeats, args.sheet_name)


if __name__ == '__main__':
    raise SystemExit(main())