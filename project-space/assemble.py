#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assemble.py — 拼版渲染模块
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader

from utils import load_assembly_config
from utils.base import BaseModule


class AssembleModule(BaseModule):
    """拼版渲染"""

    TEMPLATE = 'briefing-template.md.j2'

    def __init__(self, date_str: str):
        super().__init__(date_str, 'assemble')
        self.cfg = load_assembly_config()
        self.modules = [{'id': m['id'], 'name': m['name'], 'abbrev': m.get('abbrev', m['id'])}
                        for m in self.cfg.get('modules', [])]
        self.templates_dir = Path(__file__).resolve().parent / 'config'

    def _load_items(self, input_file: str) -> tuple:
        """加载 items 和 blocks"""
        data = self.load_json(input_file)
        if data is not None:
            return data.get('items', []), data.get('blocks', {})
        return self.load_jsonl(input_file), {}

    def _news_row(self, number: str, it: dict, cap: int) -> dict:
        """生成新闻行数据"""
        title = it.get('title', '')
        summary = (it.get('digest_for_outline') or it.get('summary', ''))[:cap]

        return {
            'number': number,
            'headline': it.get('headline', title)[:100],
            'tag': it.get('tag', '其他'),
            'link_label': f"{it.get('source', '')}：{title}" if title else '（无标题）',
            'url': it.get('url') or '#',
            'summary': summary,
            'plain_explain': it.get('plain_explain', ''),
            'impact_1': it.get('impact_1', ''),
            'impact_2': it.get('impact_2', ''),
            'hot': it.get('hot', ''),
                   }

    def _group_items(self, items: List[dict]) -> dict:
        """按 sub_topic 分组"""
        topic_to_module = {
            '大模型': 'model',
            'AI硬件': 'hardware',
            '行业应用': 'application',
            '投融资': 'investment',
            '政策监管': 'policy',
        }

        groups = {m['id']: [] for m in self.modules}
        for it in items:
            sub_topic = it.get('sub_topic', '')
            mid = topic_to_module.get(sub_topic, 'unknown')
            if mid in groups:
                groups[mid].append(it)

        return groups

    def _build_context(self, items: List[dict], blocks: dict) -> dict:
        """构建渲染上下文"""
        groups = self._group_items(items)
        cap = max(200, int(self.cfg.get('summary_max_chars', 320)))

        # header
        header = {
            'date_str': self.date_str,
            'coverage_line': self.cfg.get('header_coverage', '硬件芯片 · 模型 · AI工程 · 产业商业 · 政策地缘'),
            'sources_str': blocks.get('header', {}).get('data_sources', '多家媒体'),
            'header_tag': blocks.get('header', {}).get('tags_full', '#AI早报'),
            'header_status': '已归档',
        }

        # sections
        sections = []
        for i, m in enumerate(self.modules, 1):
            mod_items = groups.get(m['id'], [])[:8]  # 每模块最多8条
            # 过滤掉白话解释和影响字段都为空的条目
            filtered_items = []
            for it in mod_items:
                has_plain = bool(it.get('plain_explain'))
                has_impact1 = bool(it.get('impact_1'))
                has_impact2 = bool(it.get('impact_2'))
                if has_plain or has_impact1 or has_impact2:
                    filtered_items.append(it)
                else:
                    # 打印被过滤的原因
                    title = it.get('title', '无标题')
                    print(f"[过滤] [{m['name']}] 标题: {title[:50]}... 原因: plain_explain={has_plain}, impact_1={has_impact1}, impact_2={has_impact2}")
            entries = [self._news_row(f"{i}.{j+1}", it, cap) for j, it in enumerate(filtered_items)]
            sections.append({'heading': f"## {m['name']}\n", 'empty': not filtered_items, 'entries': entries})

        # footer
        footer_rows = []
        for m in self.modules:
            raw = blocks.get('footer', {}).get(m['id'], '')
            lines = [ln.strip() for ln in str(raw).splitlines() if ln.strip()][:3]
            footer_rows.append({'abbrev': m['abbrev'], 'lines': lines or ['今日暂无相关报道']})

        return {
            'header': header,
            'sections': sections,
            'footer': {'mode': 'blocks', 'rows': footer_rows}
        }

    def run(self, input_file: str, output_file: str) -> dict:
        """执行完整流程"""
        items, blocks = self._load_items(input_file)

        if not items:
            self.save_json(output_file, {'items': [], 'blocks': {}})
            return {'path': output_file, 'count': 0}

        # 渲染
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
def run_assemble(input_file: str, output_file: str, date_str: str) -> dict:
    return AssembleModule(date_str).run(input_file, output_file)