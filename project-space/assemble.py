#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assemble.py — 拼版渲染模块

输入格式：{'clusters': [...], 'blocks': {...}}
"""

from __future__ import annotations
import os
import webbrowser
from typing import Sequence, List

from utils import AppConfig, TEMPLATE_BRIEFING, TEMPLATE_BRIEFING_WECHAT, TEMPLATE_BRIEFING_REDBOOK, FN_BRIEFING_FEISHU, FN_BRIEFING_WECHAT, FN_REDBOOK, TemplateRenderer, WorkModule
from utils.domain import SummaryCluster

_CN_NUM = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十']


class AssembleModule(WorkModule):
    """拼版渲染"""

    def __init__(self, config: AppConfig):
        super().__init__('assemble', config.date_str)
        self._app_config = config
        self.assembly_cfg = config.modules.assembly
        self.modules = config.protocols.classification.main_sections
        self.section_name_to_id = {m.name: m.id for m in self.modules}

    def _load_clusters(self, input_file: str) -> tuple:
        """加载 clusters 数据
        
        Returns:
            (clusters: List[SummaryCluster], blocks: dict)
        """
        data = self.load_json(input_file)
        blocks = data.get('blocks', {})
        
        clusters = [SummaryCluster.from_dict(c) for c in data.get('clusters', [])]
        return clusters, blocks

    def _news_row(self, number: str, sc: SummaryCluster, cap: int) -> dict:
        """生成新闻行数据"""
        summary = (sc.digest_for_outline or sc.summary)[:cap]
        vertical_tags = sc.vertical_tags if isinstance(sc.vertical_tags, list) else []
        general_tags = sc.general_tags if isinstance(sc.general_tags, list) else []

        return {
            'number': number,
            'headline': (sc.headline or sc.title)[:100],
            'tag': '其他',
            'link_label': f"{sc.source}：{sc.title}" if sc.title else '（无标题）',
            'url': sc.url or '#',
            'summary': summary,
            'plain_explain': sc.plain_explain,
            'impacts': sc.impacts if isinstance(sc.impacts, list) else [],
            'hot': sc.hot,
            'vertical_tags': vertical_tags,
            'general_tags': general_tags,
        }

    def _group_clusters(self, clusters: Sequence[SummaryCluster]) -> dict:
        """按 main_section 分组"""
        groups = {m.id: [] for m in self.modules}
        for sc in clusters:
            main_section = sc.main_section
            if main_section:
                section_id = self.section_name_to_id.get(main_section)
                if section_id and section_id in groups:
                    groups[section_id].append(sc)

        return groups

    def _build_context(self, clusters: List[SummaryCluster], blocks: dict) -> dict:
        """构建渲染上下文"""
        groups = self._group_clusters(clusters)
        cap = max(200, int(self.assembly_cfg.summary_max_chars))

        rules = self._app_config.protocols.classification.main_sections
        header_data = blocks.get('header', {})
        header = {
            'date_str': self._app_config.date_str,
            'coverage_line': ' · '.join(getattr(m, 'name', '') for m in rules),
            'sources_str': header_data.get('data_sources', '多家媒体'),
            'header_tag': header_data.get('tags_full', '#AI早报'),
        }

        sections = []
        for i, m in enumerate(self.modules, 1):
            cn = _CN_NUM[i - 1] if i <= len(_CN_NUM) else str(i)
            mod_items = groups.get(m.id, [])[:self.assembly_cfg.max_news_per_module]
            summary_items = []
            for sc in mod_items:
                has_plain = bool(sc.plain_explain)
                has_impacts = bool(sc.impacts)
                if has_plain or has_impacts:
                    summary_items.append(sc)
                else:
                    self.logger.debug(f"[过滤] [{m.name}] 标题: {sc.title[:50]}... 原因: plain_explain={has_plain}, impacts={has_impacts}")
            entries = [self._news_row(f"{i}.{j+1}", sc, cap) for j, sc in enumerate(summary_items)]
            sections.append({'heading': f"{cn}、{m.name}", 'empty': not summary_items, 'entries': entries})

        footer_data = blocks.get('footer', {})
        footer_rows = []
        for m in self.modules:
            raw = footer_data.get(m.id, '')
            lines = [ln.strip() for ln in str(raw).splitlines() if ln.strip()][:self.assembly_cfg.footer_max_lines_per_module]
            footer_rows.append({'abbrev': m.name, 'lines': lines or ['今日暂无相关报道']})

        return {
            'header': header,
            'sections': sections,
            'footer': {'mode': 'blocks', 'rows': footer_rows}
        }

    def _render_redbook_cards(self, clusters: List[SummaryCluster], footer: dict, output_dir: str) -> List[str]:
        """小红书截图：生成 news card + quick-view card"""
        cap = max(200, int(self.assembly_cfg.summary_max_chars))
        cards_dir = os.path.join(output_dir, FN_REDBOOK)
        os.makedirs(cards_dir, exist_ok=True)
        paths = []

        def _render(card_type: str, data: dict, filename: str) -> str:
            html = self._renderer.render(TEMPLATE_BRIEFING_REDBOOK, {'card_type': card_type, 'data': data})
            fpath = os.path.join(cards_dir, filename)
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(html)
            paths.append(fpath)
            return fpath

        # quick-view card
        _render('quick_view', footer, 'quick-view.html')

        # news cards
        for idx, sc in enumerate(clusters, 1):
            if not sc.plain_explain and not sc.impacts:
                continue
            row = self._news_row(f"{idx}", sc, cap)
            _render('news', row, f'card-{idx:03d}.html')

        return paths

    def _open_file(self, path: str):
        webbrowser.open(f"file://{os.path.abspath(path)}")

    def run(self, input_file: str, output_file: str) -> dict:
        """执行完整流程"""
        clusters, blocks = self._load_clusters(input_file)

        if not clusters:
            self.save_json(output_file, {'clusters': [], 'blocks': {}})
            return {'path': output_file, 'count': 0}

        ctx = self._build_context(clusters, blocks)
        self._renderer = TemplateRenderer()

        output_dir = os.path.dirname(output_file) or '.'
        os.makedirs(output_dir, exist_ok=True)

        # === 1. 飞书：Markdown 文件 ===
        md = self._renderer.render(TEMPLATE_BRIEFING, ctx)
        feishu_file = os.path.join(output_dir, FN_BRIEFING_FEISHU)
        with open(feishu_file, 'w', encoding='utf-8') as f:
            f.write(md)

        # === 2. 微信：HTML 文件 ===
        html = self._renderer.render(TEMPLATE_BRIEFING_WECHAT, ctx)
        wechat_file = os.path.join(output_dir, FN_BRIEFING_WECHAT)
        with open(wechat_file, 'w', encoding='utf-8') as f:
            f.write(html)

        # === 3. 小红书：目录（redbook/ 下多个 HTML） ===
        redbook_paths = self._render_redbook_cards(clusters, ctx['footer'], output_dir)

        ## 自动打开文件
        # self._open_file(wechat_file)

        return {
            'path': feishu_file,
            'feishu_path': feishu_file,
            'wechat_path': wechat_file,
            'count': len(clusters),
            'redbook_paths': redbook_paths,
        }
