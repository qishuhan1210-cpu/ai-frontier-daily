#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assemble.py — 拼版渲染模块
"""

from __future__ import annotations
import os
from typing import Sequence

from utils import AppConfig, TEMPLATE_BRIEFING, TemplateRenderer, WorkModule
from utils.domain import BriefingMeta, SummaryItem

_CN_NUM = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十']


class AssembleModule(WorkModule):
    """拼版渲染"""

    def __init__(self, config: AppConfig):
        super().__init__('assemble')
        self._app_config = config
        self.assembly_cfg = config.modules.assembly
        self.modules = config.protocols.classification.main_sections
        self.section_name_to_id = {m.name: m.id for m in self.modules}

    def _load_items(self, input_file: str) -> BriefingMeta:
        """加载 items 和 blocks"""
        return BriefingMeta.from_dict(self.load_json(input_file))

    def _news_row(self, number: str, it: SummaryItem, cap: int) -> dict:
        """生成新闻行数据"""
        summary = (it.digest_for_outline or it.summary)[:cap]
        vertical_tags = it.vertical_tags if isinstance(it.vertical_tags, list) else []
        general_tags = it.general_tags if isinstance(it.general_tags, list) else []

        return {
            'number': number,
            'headline': (it.headline or it.title)[:100],
            'tag': '其他',
            'link_label': f"{it.source}：{it.title}" if it.title else '（无标题）',
            'url': it.url or '#',
            'summary': summary,
            'plain_explain': it.plain_explain,
            'impact_1': it.impact_1,
            'impact_2': it.impact_2,
            'hot': it.hot,
            'vertical_tags': vertical_tags,
            'general_tags': general_tags,
        }

    def _group_items(self, items: Sequence[SummaryItem]) -> dict:
        """按 main_section 分组"""
        groups = {m.id: [] for m in self.modules}
        for it in items:
            main_section = it.main_section
            if main_section:
                section_id = self.section_name_to_id.get(main_section)
                if section_id and section_id in groups:
                    groups[section_id].append(it)

        return groups

    def _build_context(self, meta: BriefingMeta) -> dict:
        """构建渲染上下文"""
        groups = self._group_items(meta.items)
        cap = max(200, int(self.assembly_cfg.summary_max_chars))

        rules = self._app_config.protocols.classification.main_sections
        header = {
            'date_str': self._app_config.date_str,
            'coverage_line': ' · '.join(getattr(m, 'name', '') for m in rules),
            'sources_str': meta.data_sources,
            'header_tag': meta.tags_full,
        }

        sections = []
        for i, m in enumerate(self.modules, 1):
            cn = _CN_NUM[i - 1] if i <= len(_CN_NUM) else str(i)
            mod_items = groups.get(m.id, [])[:self.assembly_cfg.max_news_per_module]
            summary_items = []
            for it in mod_items:
                has_plain = bool(it.plain_explain)
                has_impact1 = bool(it.impact_1)
                has_impact2 = bool(it.impact_2)
                if has_plain or has_impact1 or has_impact2:
                    summary_items.append(it)
                else:
                    print(f"[过滤] [{m.name}] 标题: {it.title[:50]}... 原因: plain_explain={has_plain}, impact_1={has_impact1}, impact_2={has_impact2}")
            entries = [self._news_row(f"{i}.{j+1}", it, cap) for j, it in enumerate(summary_items)]
            sections.append({'heading': f"## {cn}、{m.name}\n", 'empty': not summary_items, 'entries': entries})

        footer_rows = []
        for m in self.modules:
            raw = meta.footer.get(m.id, '')
            lines = [ln.strip() for ln in str(raw).splitlines() if ln.strip()][:self.assembly_cfg.footer_max_lines_per_module]
            footer_rows.append({'abbrev': m.name, 'lines': lines or ['今日暂无相关报道']})

        return {
            'header': header,
            'sections': sections,
            'footer': {'mode': 'blocks', 'rows': footer_rows}
        }

    def run(self, input_file: str, output_file: str) -> dict:
        """执行完整流程"""
        meta = self._load_items(input_file)

        if not meta.items:
            self.save_json(output_file, {'items': [], 'blocks': {}})
            return {'path': output_file, 'count': 0}

        ctx = self._build_context(meta)
        renderer = TemplateRenderer()
        md = renderer.render(TEMPLATE_BRIEFING, ctx)

        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(md)

        return {'path': output_file, 'count': len(meta.items)}
