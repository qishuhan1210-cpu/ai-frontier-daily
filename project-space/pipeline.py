#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline.py — AI Frontier Daily 早报流水线主入口

流程编排：ingest → summarize → assemble
- ingest: RSS 抓取 → 粗筛 → 去重 → ingested.jsonl
- summarize: LLM 摘要 → summary.json
- assemble: 拼版渲染 → agenda.md

使用方式:
    python3 pipeline.py --date 2026-05-11
    python3 pipeline.py --steps ingest
    python3 pipeline.py --steps summarize,assemble
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import List, Optional

# 优先使用本地 utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import default_day_paths, load_llm_config

# 导入三大模块
from ingest import IngestModule
from summarize import SummarizeModule
from assemble import AssembleModule


# 稳定顺序
ORDER = ('ingest', 'summarize', 'assemble')


def canonical_step(name: str) -> Optional[str]:
    """仅接受 ORDER 中的名字（忽略大小写）；否则返回 None"""
    key = (name or '').strip().lower()
    if not key:
        return None
    return key if key in ORDER else None


def parse_steps(steps_arg: str):
    """
    解析步骤参数：'all' 为全量 ORDER；否则逗号分隔，去重保序
    返回 (规范步骤列表, 无法识别的片段)
    """
    raw = (steps_arg or '').strip().lower()
    if raw == 'all':
        return list(ORDER), []

    seen: set = set()
    out: List[str] = []
    unknown: List[str] = []
    for part in (steps_arg or '').split(','):
        p = part.strip()
        if not p:
            continue
        c = canonical_step(p)
        if c:
            if c not in seen:
                seen.add(c)
                out.append(c)
        else:
            unknown.append(p)
    return out, unknown


def main():
    parser = argparse.ArgumentParser(description='AI Frontier Daily 早报流水线')
    parser.add_argument('--date', '-d', default=None, help='日期 YYYY-MM-DD（默认今天）')
    parser.add_argument('--steps', '-s', default='all',
                        help='执行步骤: all (默认), ingest,summarize,assemble')
    parser.add_argument('--ingested', '-i', default=None, help='输入 ingested.jsonl 路径')
    parser.add_argument('--summary', default=None, help='输入/输出 summary.json 路径')
    parser.add_argument('--agenda', '-o', default=None, help='输出 agenda.md 路径')
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime('%Y-%m-%d')
    paths = default_day_paths(date_str)

    ingested_path = args.ingested or paths['ingested']
    summary_path = args.summary or paths['summary']
    agenda_path = args.agenda or paths['agenda']

    steps, unknown = parse_steps(args.steps)
    if unknown:
        print(f'警告: 无法识别的步骤: {unknown}')
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
        result = ingest_module.run(ingested_path)
        print(f'抓取: {result["crawl"]["count"]} 条, 状态: {result["crawl"]["status"]}')
        print(f'粗筛: {result["filter"]["count"]}/{result["filter"]["total"]} 条通过')
        print(f'去重后: {result["dedup"]["count"]} 条')
        print(f'近几日去重: 剔除 {result["recent_summary_dedup"].get("dropped", 0)} 条')
        print(f'最终写入: {result["count"]} 条 → {ingested_path}')
        print()

    # 执行 summarize
    if 'summarize' in steps:
        print('=== Summarize 阶段: LLM 摘要 ===')
        if not os.path.exists(ingested_path):
            print(f'错误: 输入文件不存在: {ingested_path}')
            return
        llm_cfg = load_llm_config()
        summarize_module = SummarizeModule(date_str, llm_cfg)
        result = summarize_module.run(ingested_path, summary_path)
        print(f'处理: {result["count"]} 条')
        print(f'API 调用: {result["api_calls"]} 次')
        print(f'统一模式: {result["unified"]}')
        print(f'写入: {summary_path}')
        print()

    # 执行 assemble
    if 'assemble' in steps:
        print('=== Assemble 阶段: 拼版渲染 ===')
        if not os.path.exists(summary_path):
            print(f'错误: 输入文件不存在: {summary_path}')
            return
        assemble_module = AssembleModule(date_str)
        result = assemble_module.run(summary_path, agenda_path)
        print(f'渲染: {result["count"]} 条新闻')
        print(f'输出: {result["path"]}')
        print()

    print('=== 完成 ===')


if __name__ == '__main__':
    main()
