#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline.py — 单日早报流水线的**步骤名与顺序**（与 `kit` 产物链一致）。

ingest → summarize → assemble
  → ingested.jsonl → summary.json → agenda.md

业务实现分别在 `ingest` / `summarize` / `assemble` 模块；编排见 `daily_ai_frontier.py`。
"""

from __future__ import annotations

from typing import List, Optional, Tuple

# 稳定顺序：编排 `all` 与依赖说明用
ORDER: Tuple[str, ...] = ('ingest', 'summarize', 'assemble')


def canonical_step(name: str) -> Optional[str]:
    """
    仅接受 ORDER 中的名字（忽略大小写）；否则返回 None。
    """
    key = (name or '').strip().lower()
    if not key:
        return None
    return key if key in ORDER else None


def parse_steps(steps_arg: str) -> Tuple[List[str], List[str]]:
    """
    解析 `--steps`：'all' 为全量 ORDER；否则逗号分隔，去重保序。
    返回 (规范步骤列表, 无法识别的片段)，便于编排侧告警。
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
