#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assemble.py — 拼版渲染模块
"""

from __future__ import annotations
from datetime import datetime
import json
import os
from pathlib import Path
from typing import List

from utils import AppConfig, TEMPLATE_BRIEFING, TemplateRenderer, WorkModule


class AssembleModule(WorkModule):
    """拼版渲染"""

    def __init__(self, date_str: str, config: AppConfig):
        super().__init__(date_str, 'assemble')
        self._app_config = config
        self.assembly_cfg = config.assembly
        self.modules = config.template.classification_rules
        self.topic_to_module = {m.name: m.id for m in self.modules}

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
        groups = {m.id: [] for m in self.modules}
        for it in items:
            sub_topic = it.get('sub_topic', '')
            mid = self.topic_to_module.get(sub_topic, 'unknown')
            if mid in groups:
                groups[mid].append(it)

        return groups

    def _build_context(self, items: List[dict], blocks: dict) -> dict:
        """构建渲染上下文"""
        groups = self._group_items(items)
        cap = max(200, int(self.assembly_cfg.summary_max_chars))

        # header
        rules = self._app_config.template.classification_rules
        header = {
            'date_str': self.date_str,
            'coverage_line': ' · '.join(getattr(m, 'name', '') for m in rules),
            'sources_str': blocks.get('header', {}).get('data_sources', '多家媒体'),
            'header_tag': blocks.get('header', {}).get('tags_full', '#AI早报')
        }

        # sections
        sections = []
        for i, m in enumerate(self.modules, 1):
            mod_items = groups.get(m.id, [])[:self.assembly_cfg.max_news_per_module]
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
                    print(f"[过滤] [{m.name}] 标题: {title[:50]}... 原因: plain_explain={has_plain}, impact_1={has_impact1}, impact_2={has_impact2}")
            entries = [self._news_row(f"{i}.{j+1}", it, cap) for j, it in enumerate(filtered_items)]
            sections.append({'heading': f"## {m.name}\n", 'empty': not filtered_items, 'entries': entries})

        # footer
        footer_rows = []
        for m in self.modules:
            raw = blocks.get('footer', {}).get(m.id, '')
            lines = [ln.strip() for ln in str(raw).splitlines() if ln.strip()][:self.assembly_cfg.footer_max_lines_per_module]
            footer_rows.append({'abbrev': m.name, 'lines': lines or ['今日暂无相关报道']})

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
        renderer = TemplateRenderer()
        md = renderer.render(TEMPLATE_BRIEFING, ctx)

        # 写入
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(md)

        return {'path': output_file, 'count': len(items)}
