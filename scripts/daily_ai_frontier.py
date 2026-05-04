#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
daily_ai_frontier.py — **每日 AI 前沿早报** 编排入口

按 `pipeline.ORDER` 顺序调用：采集（ingest）→ 摘要（summarize）→ 组装（assemble）→ 当日 `agenda.md`。

用法:
    python3 scripts/daily_ai_frontier.py
    python3 scripts/daily_ai_frontier.py --date 2026-05-03
    python3 scripts/daily_ai_frontier.py --steps ingest,summarize

Steps（规范名见 `pipeline.ORDER`）:
    ingest    — 抓取 + 粗筛 + 去重 → output/{date}/ingested.jsonl
    summarize — LLM 摘要 → output/{date}/summary.json
    assemble  — 组装终稿 → output/{date}/agenda.md

    all ≡ 完整 ORDER（与 ingest,summarize,assemble 等价）
"""

import argparse
import os
import sys
from datetime import datetime
from typing import Callable, Dict, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)


def parse_args():
    parser = argparse.ArgumentParser(
        description='每日 AI 前沿早报 — 编排 ingest → summarize → assemble',
    )
    parser.add_argument('--date', type=str, default=None, help='YYYY-MM-DD，默认今天')
    parser.add_argument('--steps', type=str, default='all', help='逗号分隔，或 all')
    return parser.parse_args()


def validate_date(date_str):
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def setup_output_dirs(date_str):
    from scripts.base_config import output_dir_for_date

    output_dir = output_dir_for_date(date_str)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def load_config():
    import json
    from scripts.base_config import CONFIG_EXAMPLE_JSON, CONFIG_JSON

    if os.path.exists(CONFIG_JSON):
        with open(CONFIG_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    with open(CONFIG_EXAMPLE_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def _run_ingest(paths: Dict[str, str], date_str: str, config: dict) -> Optional[str]:
    from scripts.ingest import run_ingest

    out = paths['ingested']
    r = run_ingest(date_str, config, out)
    recent = r.get('recent_summary_dedup') or {}
    drop_n = int(recent.get('dropped') or 0)
    tail = f"，近几日 summary 对照剔除 {drop_n} 条" if drop_n else ''
    print(f"✅ ingest → {out}  ({r.get('count', 0)} 条{tail})")
    return out if r.get('count', 0) else None


def _run_summarize(paths: Dict[str, str], date_str: str, config: dict) -> Optional[str]:
    from scripts.summarize import run_summarize

    inp, out = paths['ingested'], paths['summary']
    r = run_summarize(inp, out, date_str, config)
    print(f"✅ summarize → {out}  ({r.get('count', 0)} 条)")
    return out if r.get('count', 0) else None


def _run_assemble(paths: Dict[str, str], date_str: str, config: dict) -> Optional[str]:
    from scripts.assemble import run_assemble

    inp, out = paths['summary'], paths['agenda']
    r = run_assemble(inp, out, date_str, config)
    print(f"✅ assemble → {r.get('path', out)}")
    return r.get('path')


_STEP_RUNNERS: Dict[str, Callable[[Dict[str, str], str, dict], Optional[str]]] = {
    'ingest': _run_ingest,
    'summarize': _run_summarize,
    'assemble': _run_assemble,
}


def run_step(step: str, date_str: str, config: dict) -> Optional[str]:
    from scripts.base_config import default_day_paths

    paths = default_day_paths(date_str)
    runner = _STEP_RUNNERS.get(step)
    if not runner:
        print(f'⚠️ 未知步骤: {step}')
        return None

    print(f"\n{'='*60}")
    print(f"▶ {step}  |  {date_str}")
    print(f"{'='*60}")

    return runner(paths, date_str, config)


def main():
    args = parse_args()

    if args.date:
        if not validate_date(args.date):
            print(f'❌ 日期格式错误: {args.date}')
            sys.exit(1)
        date_str = args.date
    else:
        date_str = datetime.now().strftime('%Y-%m-%d')

    output_dir = setup_output_dirs(date_str)
    print(f'📁 {output_dir}')

    config = load_config()

    from scripts.pipeline import parse_steps

    steps, unknown_tokens = parse_steps(args.steps)
    for tok in unknown_tokens:
        print(f'⚠️ 忽略未知步骤: {tok}')
    if not steps:
        print('❌ 没有可执行的规范步骤（检查 --steps 拼写，或显式使用 all）')
        sys.exit(1)

    results = {}
    for step in steps:
        try:
            results[step] = run_step(step, date_str, config)
        except Exception as e:
            print(f'❌ {step}: {e}')
            import traceback

            traceback.print_exc()
            results[step] = None

    print(f"\n{'='*60}")
    print(f'📊 {date_str}')
    print(f"{'='*60}")
    for step, result in results.items():
        mark = '✅' if result else '⚠️ '
        print(f'  {mark} {step}: {result or "(无产物)"}')
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
