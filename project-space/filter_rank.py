#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
filter_rank.py — 智能筛选与优先级排序模块

步骤二：对 ingest 输出的原始新闻进行智能筛选和排名
"""

from __future__ import annotations

import json
from typing import Sequence

from utils import AppConfig, LLMClient, WorkModule, PromptLoader, TEMPLATE_FILTER_RANK
from utils.domain import NewsItem, FilteredItem, FilterStats


class FilterRankModule(WorkModule):
    """智能筛选与优先级排序"""


    def __init__(self, config: AppConfig):
        super().__init__('filter_rank')
        self.llm_client = LLMClient(config.llm_client_cfg)
        self._app_config = config
        self.valid_main_sections = [getattr(m, 'name', '') for m in config.protocols.classification.main_sections]
        self.max_news_per_topic = config.modules.filter_rank.max_news_per_topic

    def _build_prompts(self, items: Sequence[NewsItem]) -> tuple:
        """构建 system/user 提示词"""
        rows = [
                {
                    'index': i,
                    'title': it.title,
                    'source': it.source,
                    'url': it.url,
                    'update_time': it.pub_time
                } for i, it in enumerate(items)
            ]

        return PromptLoader().load_with_config(
            TEMPLATE_FILTER_RANK,
            self._app_config.protocols,

            news_json=json.dumps(rows, ensure_ascii=False, indent=2),
        )

    def run(self, input_file: str, output_file: str) -> dict:
        """执行完整流程"""
        raw_items = self.load_jsonl(input_file)
        news_items = [NewsItem.from_dict(it) for it in raw_items]
        n_input = len(news_items)

        if n_input == 0:
            self.save_json(output_file, {'items': [], 'stats': {'input_count': 0, 'output_count': 0}})
            return {'count': 0, 'api_calls': 0, 'input_count': 0}

        system, user = self._build_prompts(news_items)
        data = self.llm_client.call_json(system, user)

        llm_items = FilteredItem.from_llm_response(data)

        section_counts = {}
        filtered_items = []
        for row in llm_items:
            si = row['source_index']
            if not (0 <= si < n_input):
                continue
            main_section = row['main_section']
            if main_section not in self.valid_main_sections:
                main_section = 'AI 产业与观察'
            sub_section = row['sub_section']
            if not sub_section:
                sub_section = '其他'
            row['main_section'] = main_section
            row['sub_section'] = sub_section

            original = news_items[si]
            rank = len(filtered_items) + 1
            filtered_item = FilteredItem.from_news_and_llm(original, row, rank)
            if section_counts.get(main_section, 0) < self.max_news_per_topic:
                filtered_items.append(filtered_item)
                section_counts[main_section] = section_counts.get(main_section, 0) + 1

        limited_items = filtered_items

        stats = FilterStats.from_counts(n_input, len(limited_items), section_counts)

        result = {
            'items': [it.__dict__.copy() for it in limited_items],
            'stats': stats.to_dict()
        }

        self.save_json(output_file, result)
        return {'count': len(limited_items), 'input_count': n_input, 'api_calls': 1}
