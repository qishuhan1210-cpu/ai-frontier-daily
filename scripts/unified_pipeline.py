#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unified_pipeline.py — **合并版早报流水线**

将 ingest → summarize → assemble 三个步骤合并为单一脚本，
实现一站式早报生成。

用法:
    python3 scripts/unified_pipeline.py
    python3 scripts/unified_pipeline.py --date 2026-05-11
    python3 scripts/unified_pipeline.py --output-dir ./output
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)


def load_config():
    """加载项目配置"""
    from scripts.base_config import CONFIG_EXAMPLE_JSON, CONFIG_JSON

    if os.path.exists(CONFIG_JSON):
        with open(CONFIG_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    with open(CONFIG_EXAMPLE_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def run_ingest(date_str: str, output_file: str) -> dict:
    """执行采集步骤"""
    from scripts.ingest import run_ingest
    return run_ingest(date_str, {}, output_file)


def run_summarize(date_str: str, input_file: str, output_file: str, config: dict) -> dict:
    """执行摘要步骤"""
    from scripts.summarize import run_summarize
    return run_summarize(input_file, output_file, date_str, config)


def run_assemble(date_str: str, input_file: str, output_file: str) -> dict:
    """执行组装步骤"""
    from scripts.assemble import run_assemble
    return run_assemble(input_file, output_file, date_str, None)


def run_full_pipeline(date_str: str, config: dict, output_base: str) -> dict:
    """
    执行完整流水线：ingest → summarize → assemble
    
    返回：各步骤结果汇总
    """
    os.makedirs(output_base, exist_ok=True)
    
    # 步骤 1: Ingest
    ingest_path = os.path.join(output_base, 'ingested.jsonl')
    print(f"\n{'='*60}")
    print(f"▶ 1/3 ingest | {date_str}")
    print(f"{'='*60}")
    ingest_result = run_ingest(date_str, ingest_path)
    ingest_count = ingest_result.get('count', 0)
    print(f"✅ ingest → {ingest_path} ({ingest_count} 条)")
    
    if ingest_count == 0:
        print("⚠️ 无采集结果，跳过后续步骤")
        return {'ingest': ingest_result, 'summarize': None, 'assemble': None}
    
    # 步骤 2: Summarize
    summary_path = os.path.join(output_base, 'summary.json')
    print(f"\n{'='*60}")
    print(f"▶ 2/3 summarize | {date_str}")
    print(f"{'='*60}")
    summarize_result = run_summarize(date_str, ingest_path, summary_path, config)
    summary_count = summarize_result.get('count', 0)
    print(f"✅ summarize → {summary_path} ({summary_count} 条)")
    
    # 步骤 3: Assemble
    agenda_path = os.path.join(output_base, 'agenda.md')
    print(f"\n{'='*60}")
    print(f"▶ 3/3 assemble | {date_str}")
    print(f"{'='*60}")
    assemble_result = run_assemble(date_str, summary_path, agenda_path)
    print(f"✅ assemble → {assemble_result.get('path', agenda_path)}")
    
    return {
        'ingest': ingest_result,
        'summarize': summarize_result,
        'assemble': assemble_result,
        'date': date_str,
        'output_dir': output_base,
        'total_articles': summary_count,
    }


def validate_date(date_str: str) -> bool:
    """验证日期格式"""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def main():
    parser = argparse.ArgumentParser(
        description='AI前沿早报 - 合并版流水线',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--date',
        type=str,
        default=None,
        help='日期 YYYY-MM-DD，默认今天'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='输出目录，默认 output/<date>'
    )
    args = parser.parse_args()
    
    # 确定日期
    if args.date:
        if not validate_date(args.date):
            print(f'❌ 日期格式错误: {args.date}', file=sys.stderr)
            sys.exit(1)
        date_str = args.date
    else:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    # 确定输出目录
    if args.output_dir:
        output_base = args.output_dir
    else:
        output_base = os.path.join(_PROJECT_ROOT, 'output', date_str)
    
    print(f'📁 输出目录: {output_base}')
    
    # 加载配置
    config = load_config()
    
    # 执行流水线
    result = run_full_pipeline(date_str, config, output_base)
    
    # 输出汇总
    print(f"\n{'='*60}")
    print(f'📊 {date_str} 早报生成完成')
    print(f"{'='*60}")
    print(f"  ingest:    {result['ingest']['count']} 条原始数据")
    if result['summarize']:
        print(f"  summarize: {result['summarize']['count']} 条摘要")
    if result['assemble']:
        print(f"  assemble:  ✅ 生成 {result['assemble']['path']}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
