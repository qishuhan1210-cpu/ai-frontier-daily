#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline.py — AI Frontier Daily 早报流水线主入口

流程编排：ingest → filter_rank → summarize → assemble
- ingest: RSS 抓取 → 去重 → ingested.jsonl
- filter_rank: LLM 智能筛选排序 → filtered_ranked.json
- summarize: LLM 摘要 → summary.json
- assemble: 拼版渲染 → 早报 Markdown 终稿

使用方式:
    python3 pipeline.py --date 2026-05-11
    python3 pipeline.py --steps ingest
    python3 pipeline.py --steps filter_rank,summarize
    python3 pipeline.py --steps summarize,assemble
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# 优先使用本地 utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import default_day_paths

# 导入四大模块
from ingest import IngestModule
from filter_rank import FilterRankModule
from summarize import SummarizeModule
from assemble import AssembleModule


# 稳定顺序
ORDER = ('ingest', 'filter_rank', 'summarize', 'assemble')


def canonical_step(name: str) -> Optional[str]:
    """仅接受 ORDER 中的名字（忽略大小写）；否则返回 None"""
    key = (name or '').strip().lower()
    if not key:
        return None
    return key if key in ORDER else None


def parse_steps(steps_arg: str) -> List[str]:
    """
    解析步骤参数：'all' 为全量 ORDER；否则逗号分隔，去重保序
    """
    raw = (steps_arg or '').strip().lower()
    if raw == 'all':
        return list(ORDER)

    seen: set = set()
    out: List[str] = []
    for part in (steps_arg or '').split(','):
        p = part.strip()
        if not p:
            continue
        c = canonical_step(p)
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def main():
    parser = argparse.ArgumentParser(description='AI Frontier Daily 早报流水线')
    parser.add_argument('--date', '-d', default=None, help='日期 YYYY-MM-DD（默认今天）')
    parser.add_argument('--steps', '-s', default='all',
                        help='执行步骤: all (默认), ingest,filter_rank,summarize,assemble')
    parser.add_argument('--ingested', '-i', default=None, help='输入 ingested.jsonl 路径')
    parser.add_argument('--filtered', '-f', default=None, help='输入/输出 filtered_ranked.json 路径')
    parser.add_argument('--summary', default=None, help='输入/输出 summary.json 路径')
    parser.add_argument('--output', '-o', default=None, help='输出早报 Markdown 文件路径')
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime('%Y-%m-%d')
    paths = default_day_paths(date_str)

    ingested_path = Path(args.ingested) if args.ingested else paths['ingested']
    filtered_path = Path(args.filtered) if args.filtered else paths['filtered']
    summary_path = Path(args.summary) if args.summary else paths['summary']
    output_path = Path(args.output) if args.output else paths['briefing']

    steps = parse_steps(args.steps)
    if not steps:
        print('错误: 没有有效的步骤可执行')
        return

    print(f'日期: {date_str}')
    print(f'步骤: {", ".join(steps)}')
    print(f'输出目录: {paths["dir"]}')
    print()

    # 执行 ingest
    if 'ingest' in steps:
        print('=== Ingest 阶段: RSS 抓取与去重 ===')
        ingest_module = IngestModule(date_str)
        result = ingest_module.run(str(ingested_path))
        print(f'抓取: {result["crawl"]["count"]} 条, 状态: {result["crawl"]["status"]}')
        print(f'去重后: {result["dedup"]["count"]} 条')
        print(f'近几日去重: 剔除 {result["recent_summary_dedup"].get("dropped", 0)} 条')
        print(f'最终写入: {result["count"]} 条 → {ingested_path}')
        print()

    # 执行 filter_rank
    if 'filter_rank' in steps:
        print('=== Filter Rank 阶段: 智能筛选与排序 ===')
        if not ingested_path.exists():
            print(f'错误: 输入文件不存在: {ingested_path}')
            return
        filter_module = FilterRankModule(date_str)
        result = filter_module.run(str(ingested_path), str(filtered_path))
        print(f'输入: {result["input_count"]} 条')
        print(f'保留: {result["count"]} 条')
        print(f'API 调用: {result["api_calls"]} 次')
        print(f'写入: {filtered_path}')
        print()

    # 执行 summarize
    if 'summarize' in steps:
        print('=== Summarize 阶段: LLM 摘要 ===')
        summarize_module = SummarizeModule(date_str)
        result = summarize_module.run(str(filtered_path), str(summary_path))
        print(f'处理: {result["count"]} 条')
        print(f'API 调用: {result["api_calls"]} 次')
        print(f'统一模式: {result["unified"]}')
        print(f'写入: {summary_path}')
        print()

    # 执行 assemble
    if 'assemble' in steps:
        print('=== Assemble 阶段: 拼版渲染 ===')
        if not summary_path.exists():
            print(f'错误: 输入文件不存在: {summary_path}')
            return
        assemble_module = AssembleModule(date_str)
        result = assemble_module.run(str(summary_path), str(output_path))
        print(f'渲染: {result["count"]} 条新闻')
        print(f'输出: {result["path"]}')
        print()

    print('=== 完成 ===')


if __name__ == '__main__':
    main()
