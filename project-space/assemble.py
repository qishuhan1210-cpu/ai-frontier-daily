#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assemble.py — 拼版渲染模块
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple

from utils import load_assembly_config, load_sources_config
from utils.base import BaseModule

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    Environment = None
    FileSystemLoader = None


class AssembleModule(BaseModule):
    """拼版渲染"""

    TEMPLATE = 'briefing-template.md.j2'
    PLACEHOLDER = '（待补）'

    def __init__(self, date_str: str):
        super().__init__(date_str, 'assemble')
        self.cfg = None
        self.modules = None
        self.max_per = 8
        self.summary_cap = 320

        project_root = os.path.dirname(os.path.abspath(__file__))
        self.templates_dir = os.path.join(project_root, 'config')

    def _load(self):
        """加载配置"""
        if self.cfg:
            return
        self.cfg = load_assembly_config()
        self.modules = [
            {'id': m['id'], 'name': m['name'], 'abbrev': m.get('abbrev', m['id'])}
            for m in self.cfg.get('modules', [])
        ]
        self.max_per = max(1, int(self.cfg.get('max_news_per_module', 8)))
        self.summary_cap = max(200, int(self.cfg.get('summary_max_chars', 320)))

    def _parse_time(self, it: dict) -> datetime:
        """解析发布时间"""
        raw = str(it.get('pub_time') or it.get('pub_time_raw') or '').strip()
        if not raw:
            return datetime.min
        for cand in (raw, raw.replace('Z', '+00:00')):
            try:
                dt = datetime.fromisoformat(cand)
                return dt.replace(tzinfo=None) if dt.tzinfo else dt
            except ValueError:
                continue
        for fmt in ('%Y-%m-%d %H:%M:%S',):
            try:
                return datetime.strptime(raw[:19], fmt)
            except ValueError:
                continue
        try:
            dt = parsedate_to_datetime(raw)
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except Exception:
            pass
        m = re.match(r'(\d{4}-\d{2}-\d{2})', raw)
        if m:
            try:
                return datetime.strptime(m.group(1), '%Y-%m-%d')
            except ValueError:
                pass
        return datetime.min

    def _sort(self, items: List[dict]) -> List[dict]:
        """按时间排序"""
        return sorted(items, key=self._parse_time, reverse=True)

    def _news_row(self, letter: str, it: dict) -> dict:
        """生成新闻行数据"""
        title = it.get('title', '')
        title_disp = self.clip_text(title, 100)

        # 摘要文本
        raw = (it.get('_ai_summary') or it.get('summary', '')).strip()
        if raw and not self.is_placeholder(raw):
            summary = raw[:self.summary_cap]
        else:
            parts = [it.get('point'), it.get('one_liner'), it.get('plain_explain')]
            stitched = ' '.join(str(p).strip() for p in parts if p and str(p).strip())
            summary = stitched[:self.summary_cap] if stitched else (it.get('summary', '')[:self.summary_cap] or self.PLACEHOLDER)

        def field(k: str, fb: str = '') -> str:
            v = it.get(k)
            return str(v).strip() if v and str(v).strip() else (fb[:200] if fb else self.PLACEHOLDER)

        return {
            'letter': letter,
            'title_display': title_disp,
            'point': field('point'),
            'one_liner': field('one_liner', title_disp),
            'link_label': f"{it.get('source', '')}：{title}" if it.get('source') or title else self.PLACEHOLDER,
            'url': it.get('url') or '#',
            'summary': summary,
            'plain_explain': field('plain_explain'),
            'impact_1': field('impact_1'),
            'impact_2': field('impact_2'),
        }

    def _group(self, items: List[dict]) -> Dict[str, List[dict]]:
        """按模块分组"""
        ids = [m['id'] for m in self.modules]
        groups = {mid: [] for mid in ids}
        groups['unknown'] = []
        for it in items:
            mid = it.get('_matched_module', 'unknown')
            groups[mid if mid in ids else 'unknown'].append(it)
        return groups

    def _build_context(self, items: List[dict], blocks: Optional[dict]) -> dict:
        """构建渲染上下文"""
        self._load()
        groups = self._group(items)

        # header
        sources = load_sources_config()
        tier1 = sources.get('tier1', [])[:6]
        header_fallback = ' · '.join(tier1)
        h = blocks.get('header', {}) if blocks else {}
        header = {
            'date_str': self.date_str,
            'coverage_line': self.cfg.get('header_coverage', '硬件芯片 · 模型 · AI工程 · 产业商业 · 政策地缘'),
            'sources_str': (h.get('data_sources') or '').strip() or header_fallback,
            'header_tag': (h.get('tags_full') or '').strip() or '#AI早报',
            'header_status': '已归档',
        }

        # sections
        sections = []
        for m in self.modules:
            mid = m['id']
            mod_items = self._sort(groups[mid])[:self.max_per]
            sections.append({
                'heading': f"## {m['name']}\n",
                'empty': not mod_items,
                'entries': [self._news_row(chr(ord('a') + i), it) for i, it in enumerate(mod_items)]
            })

        # unknown
        unk_items = self._sort(groups.get('unknown', []))[:self.max_per]
        unknown = {'entries': [self._news_row(chr(ord('a') + i), it) for i, it in enumerate(unk_items)]} if unk_items else None

        # footer
        if blocks and blocks.get('footer'):
            fd = blocks['footer']
            abbrevs = {m['id']: m['abbrev'] for m in self.modules}
            rows = []
            for m in self.modules:
                raw = fd.get(m['id'])
                lines = [self.clip_text(ln, 320) for ln in str(raw or '').splitlines() if ln.strip()] if raw else []
                rows.append({'abbrev': abbrevs[m['id']], 'lines': lines or ['今日暂无相关报道']})
            footer = {'mode': 'blocks', 'rows': rows}
        else:
            abbrevs = {m['id']: m['abbrev'] for m in self.modules}
            lines = ['> **今日速览（一句话版）：**', '>']
            for m in self.modules:
                n = len(self._sort(groups[m['id']])[:self.max_per])
                lines.append(f"> **{abbrevs[m['id']]}：** 本模块收录 {n} 条。")
            if unk_items:
                lines.append(f"> **其他：** 未分类 {len(unk_items)} 条。")
            footer = {'mode': 'fallback', 'fallback_lines': lines}

        ctx = {'header': header, 'sections': sections, 'footer': footer}
        if unknown:
            ctx['unknown'] = unknown
        return ctx

    def run(self, input_file: str, output_file: str) -> dict:
        """执行完整流程"""
        self._load()

        # 读取数据
        with open(input_file, 'r', encoding='utf-8') as f:
            raw = f.read().strip()

        if raw.startswith('{'):
            data = json.loads(raw)
            items, blocks = list(data.get('items', [])), data.get('blocks')
        else:
            items = [json.loads(line) for line in raw.splitlines() if line.strip()]
            blocks = None

        # 渲染
        if Environment is None or FileSystemLoader is None:
            raise ImportError('需要安装 jinja2: pip install jinja2')

        ctx = self._build_context(items, blocks)
        env = Environment(loader=FileSystemLoader(self.templates_dir), autoescape=False)
        tpl = env.get_template(self.TEMPLATE)
        md = tpl.render(**ctx)

        # 写入
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(md)

        return {'path': output_file, 'count': len(items)}


# 向后兼容
def run_assemble(input_file: str, output_file: str, date_str: str, _config=None) -> dict:
    return AssembleModule(date_str).run(input_file, output_file)


# 延迟导入 json
import json
