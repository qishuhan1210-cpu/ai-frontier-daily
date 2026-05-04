#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assemble.py — 流水线第三步：**组装**终稿 `agenda.md`

- 读 `summary.json`（items + 可选 blocks），构建 Jinja 上下文，用 `agenda.md.j2` **渲染** Markdown。
- 分组 / 排序 / 字段兜底 / 头尾模型均在本模块（实现「编排后的版面组装」，区别于仅指模板引擎的 render）。
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from scripts.base_config import TEMPLATES_DIR, load_assembly_config, load_sources_config

# ----- 展示边界（与 engineering.json assembly 协作）-----

PLACEHOLDER_PENDING = '（待补）'
HEADER_TIER1_PREVIEW_COUNT = 6
MAX_TITLE_DISPLAY_CHARS = 100
SUMMARY_DISPLAY_MAX_CHARS_DEFAULT = 320
FOOTER_LINE_MAX_CHARS = 320
HEADER_TAG_DEFAULT = '#AI早报'
HEADER_STATUS_DEFAULT = '已归档'
_SUMMARY_PLACEHOLDER_PATTERNS = ('点击查看原文', 'click to read', 'read more')

_AGENDA_TEMPLATE = 'agenda.md.j2'


def load_assembly_modules() -> Tuple[List[dict], str, int, int]:
    data = load_assembly_config()
    modules = [
        {'id': m['id'], 'name': m['name'], 'abbrev': m.get('abbrev', m['id'])}
        for m in data.get('modules', [])
    ]
    coverage = data.get(
        'header_coverage',
        '硬件芯片 · 模型 · AI工程 · 产业商业 · 政策地缘',
    )
    max_per = int(data.get('max_news_per_module', 8))
    summary_cap = int(data.get('summary_max_chars', SUMMARY_DISPLAY_MAX_CHARS_DEFAULT))
    return modules, coverage, max(1, max_per), max(200, summary_cap)


def group_by_module(items: List[dict], module_ids: List[str]) -> Dict[str, List[dict]]:
    groups = {mid: [] for mid in module_ids}
    groups['unknown'] = []
    ids_set = set(module_ids)
    for item in items:
        mod_id = item.get('_matched_module', 'unknown')
        (groups[mod_id] if mod_id in ids_set else groups['unknown']).append(item)
    return groups


def parse_pub_datetime(item: dict) -> datetime:
    raw = str(item.get('pub_time') or item.get('pub_time_raw') or '').strip()
    if not raw:
        return datetime.min
    for candidate in (raw, raw.replace('Z', '+00:00')):
        try:
            dt = datetime.fromisoformat(candidate)
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            continue
    try:
        return datetime.strptime(raw[:19], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(raw)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except (TypeError, ValueError, OverflowError):
        pass
    m = re.match(r'(\d{4}-\d{2}-\d{2})', raw)
    if m:
        try:
            return datetime.strptime(m.group(1), '%Y-%m-%d')
        except ValueError:
            pass
    return datetime.min


def sort_items_by_time(items: List[dict]) -> List[dict]:
    return sorted(items, key=parse_pub_datetime, reverse=True)


def _is_placeholder_summary(text: str) -> bool:
    if not text:
        return True
    t = text.strip()
    if len(t) < 6:
        return True
    low = t.lower()
    for p in _SUMMARY_PLACEHOLDER_PATTERNS:
        if p in t or p.lower() in low:
            return True
    return False


def truncate_display_title(title: str) -> str:
    title = (title or '').strip()
    if len(title) <= MAX_TITLE_DISPLAY_CHARS:
        return title
    return title[: MAX_TITLE_DISPLAY_CHARS - 1] + '…'


def effective_summary_text(item: dict, summary_cap: int) -> str:
    raw = (item.get('_ai_summary') or item.get('summary') or '').strip()
    if raw and not _is_placeholder_summary(raw):
        return raw[:summary_cap]
    parts = [item.get('point'), item.get('one_liner'), item.get('plain_explain')]
    stitched = ' '.join(str(p).strip() for p in parts if p and str(p).strip())
    if stitched:
        return stitched[:summary_cap]
    fallback = (item.get('summary') or item.get('content') or '').strip()
    return fallback[:summary_cap] if fallback else PLACEHOLDER_PENDING


def effective_field(item: dict, key: str, fallback_first: str = '') -> str:
    v = item.get(key)
    if v is not None and str(v).strip():
        return str(v).strip()
    return fallback_first[:200] if fallback_first else PLACEHOLDER_PENDING


def news_row(letter: str, item: dict, summary_cap: int) -> Dict[str, Any]:
    title = item.get('title', '')
    title_display = truncate_display_title(title)
    url = item.get('url', '')
    source = item.get('source', '')
    summary_text = effective_summary_text(item, summary_cap)
    point = effective_field(item, 'point')
    one_liner = effective_field(item, 'one_liner', title_display or '')
    link_label = f'{source}：{title}' if source or title else PLACEHOLDER_PENDING
    return {
        'letter': letter,
        'title_display': title_display,
        'point': point,
        'one_liner': one_liner,
        'link_label': link_label,
        'url': url or '#',
        'summary': summary_text,
        'plain_explain': effective_field(item, 'plain_explain'),
        'impact_1': effective_field(item, 'impact_1'),
        'impact_2': effective_field(item, 'impact_2'),
    }


def build_header_model(
    date_str: str,
    coverage_line: str,
    sources: dict,
    blocks: Optional[dict],
) -> Dict[str, str]:
    tier1_names = sources.get('tier1', [])
    fallback_sources = ' · '.join(tier1_names[:HEADER_TIER1_PREVIEW_COUNT])
    if blocks and isinstance(blocks.get('header'), dict):
        h = blocks['header']
        header_tag = (h.get('tags_full') or '').strip() or HEADER_TAG_DEFAULT
        sources_str = (h.get('data_sources') or '').strip() or fallback_sources
    else:
        header_tag = HEADER_TAG_DEFAULT
        sources_str = fallback_sources
    return {
        'date_str': date_str,
        'coverage_line': coverage_line,
        'sources_str': sources_str,
        'header_tag': header_tag,
        'header_status': HEADER_STATUS_DEFAULT,
    }


def _truncate_footer_line(line: str) -> str:
    line = line.strip()
    if len(line) > FOOTER_LINE_MAX_CHARS:
        return line[: FOOTER_LINE_MAX_CHARS - 1] + '…'
    return line


def build_footer_model(
    groups: Dict[str, List[dict]],
    modules: List[dict],
    blocks: Optional[dict],
    max_per: int,
) -> Dict[str, Any]:
    if blocks and isinstance(blocks.get('footer'), dict):
        fd = blocks['footer']
        abbrevs = {m['id']: m['abbrev'] for m in modules}
        rows = []
        for m in modules:
            mid = m['id']
            raw = fd.get(mid)
            if raw is None or not str(raw).strip():
                lines = ['今日暂无相关报道']
            else:
                lines = [
                    _truncate_footer_line(ln)
                    for ln in str(raw).splitlines()
                    if ln.strip()
                ]
            if not lines:
                lines = ['今日暂无相关报道']
            rows.append({'abbrev': abbrevs[mid], 'lines': lines})
        return {'mode': 'blocks', 'rows': rows}

    abbrevs = {m['id']: m['abbrev'] for m in modules}
    lines: List[str] = ['> **🚀 今日速览（一句话版）：**', '>']
    for m in modules:
        mid = m['id']
        n = len(sort_items_by_time(groups[mid])[:max_per])
        lines.append(f'> **{abbrevs[mid]}：** 本模块收录 {n} 条。')
    unk = groups.get('unknown') or []
    if unk:
        n = len(sort_items_by_time(unk)[:max_per])
        lines.append(f'> **其他：** 未分类 {n} 条。')
    return {'mode': 'fallback', 'fallback_lines': lines}


def build_sections_and_unknown(
    groups: Dict[str, List[dict]],
    modules: List[dict],
    max_per: int,
    summary_cap: int,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    sections = []
    for m in modules:
        mid = m['id']
        heading = f"## {m['name']}\n"
        mod_items = sort_items_by_time(groups[mid])[:max_per]
        if not mod_items:
            sections.append({'heading': heading, 'empty': True, 'entries': []})
            continue
        entries = [
            news_row(chr(ord('a') + i), it, summary_cap)
            for i, it in enumerate(mod_items)
        ]
        sections.append({'heading': heading, 'empty': False, 'entries': entries})

    unk = sort_items_by_time(groups.get('unknown') or [])[:max_per]
    if not unk:
        return sections, None
    unknown_ctx = {
        'entries': [
            news_row(chr(ord('a') + i), it, summary_cap)
            for i, it in enumerate(unk)
        ]
    }
    return sections, unknown_ctx


def build_agenda_context(
    date_str: str,
    items: List[dict],
    blocks: Optional[dict],
) -> Dict[str, Any]:
    modules, coverage, max_per, summary_cap = load_assembly_modules()
    sources = load_sources_config()
    module_ids = [m['id'] for m in modules]
    groups = group_by_module(items, module_ids)

    header = build_header_model(date_str, coverage, sources, blocks)
    sections, unknown = build_sections_and_unknown(groups, modules, max_per, summary_cap)
    footer = build_footer_model(groups, modules, blocks, max_per)

    ctx: Dict[str, Any] = {
        'header': header,
        'sections': sections,
        'footer': footer,
    }
    if unknown:
        ctx['unknown'] = unknown
    return ctx


# ----- 加载 summary、渲染终稿 -----


def load_summary_bundle(path: str):
    """读取 `summary.json`（items + blocks）；兼容旧版 JSONL。"""
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read().strip()
    if not raw:
        return [], None
    if raw.lstrip().startswith('{'):
        data = json.loads(raw)
        if isinstance(data, dict) and 'items' in data:
            return list(data.get('items') or []), data.get('blocks')
        return [], None
    items = []
    for line in raw.splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items, None


def render_agenda_md(context: dict) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
    tpl = env.get_template(_AGENDA_TEMPLATE)
    return tpl.render(
        header=context['header'],
        sections=context['sections'],
        footer=context['footer'],
        unknown=context.get('unknown'),
    )


def run_assemble(input_path: str, output_md: str, date_str: str, _config=None):
    """读 summary、组装上下文、写出 `agenda.md`。"""
    items, blocks = load_summary_bundle(input_path)
    context = build_agenda_context(date_str, items, blocks)
    full = render_agenda_md(context)

    out_dir = os.path.dirname(os.path.abspath(output_md))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write(full)

    return {'path': output_md, 'count': len(items)}


# 旧 import：`from scripts.assemble import run`
run = run_assemble


def main():
    import argparse

    from scripts.base_config import default_day_paths

    parser = argparse.ArgumentParser(description='assemble：summary.json → agenda.md')
    parser.add_argument('--date', '-d', default=None, help='YYYY-MM-DD；默认今天')
    parser.add_argument(
        '-i',
        '--input',
        default=None,
        help='summary.json（默认 output/<date>/summary.json）',
    )
    parser.add_argument(
        '-o',
        '--output',
        default=None,
        help='输出 Markdown（默认 output/<date>/agenda.md）',
    )
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime('%Y-%m-%d')
    paths = default_day_paths(date_str)
    inp = args.input or paths['summary']
    out = args.output or paths['agenda']
    run_assemble(inp, out, date_str, None)
    print(out)


if __name__ == '__main__':
    main()
