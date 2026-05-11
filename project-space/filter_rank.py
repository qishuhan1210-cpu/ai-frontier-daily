#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
filter_rank.py — 智能筛选与优先级排序模块

步骤二：对 ingest 输出的原始新闻进行智能筛选和排名
"""

from __future__ import annotations

import copy
import json
from typing import List

from utils import PROMPTS_DIR, LLMClient, load_assembly_config
from utils.base import BaseModule
from utils.prompt_loader import PromptLoader


class FilterRankModule(BaseModule):
    """智能筛选与优先级排序"""

    TEMPLATE = 'filter_ranker.md.j2'
    VALID_SUB_TOPICS = {'大模型', 'AI硬件', '行业应用', '投融资', '政策监管'}

    def __init__(self, date_str: str):
        super().__init__(date_str, 'filter_rank')
        self.llm_client = LLMClient()

    def _build_prompts(self, items: List[dict]) -> tuple:
        """构建 system/user 提示词"""
        cfg = load_assembly_config()
        coverage = cfg.get('header_coverage', '硬件芯片 · 模型 · AI工程 · 产业商业 · 政策地缘')

        rows = [{'index': i, 'title': it.get('title', ''), 'source': it.get('source', ''),
                 'url': it.get('url', ''), 'update_time': it.get('pub_time', '')}
                for i, it in enumerate(items)]

        loader = PromptLoader(PROMPTS_DIR)
        ctx = {'date_str': self.date_str, 'coverage': coverage,
               'news_json': json.dumps(rows, ensure_ascii=False, indent=2)}
        rendered = loader.render(self.TEMPLATE, ctx)
        parts = loader.parse_frontmatter(rendered or '')
        return parts.get('system', ''), parts.get('user', '')

    def _extract_items(self, data: dict, n_input: int) -> List[dict]:
        """从 LLM 响应中提取有效 items"""
        if not isinstance(data, dict):
            return []

        items = []
        for row in data.get('items', []):
            if not isinstance(row, dict):
                continue

            si = row.get('source_index')
            if si is None:
                continue
            try:
                si_int = int(si)
                if not (0 <= si_int < n_input):
                    continue
            except (ValueError, TypeError):
                continue

            sub_topic = row.get('sub_topic', '')
            if sub_topic not in self.VALID_SUB_TOPICS:
                sub_topic = '其他'

            try:
                relevance = float(row.get('relevance', 0))
                hot_level = float(row.get('hot_level', 0))
            except (ValueError, TypeError):
                continue

            items.append({
                'source_index': si_int,
                'sub_topic': sub_topic,
                'relevance': relevance,
                'hot_level': hot_level,
            })

        return items

    def run(self, input_file: str, output_file: str) -> dict:
        """执行完整流程"""
        items = self.load_jsonl(input_file)
        n_input = len(items)

        if n_input == 0:
            self.save_json(output_file, {'items': [], 'stats': {'input_count': 0, 'output_count': 0}})
            return {'count': 0, 'api_calls': 0, 'input_count': 0}

        # 调用 LLM
        system, user = self._build_prompts(items)
        data = self.llm_client.call_json(system, user, temperature=0.3, max_tokens=8192)

        # 提取并合并结果
        llm_items = self._extract_items(data, n_input)

        filtered_items = []
        for row in llm_items:
            si = row['source_index']
            original = copy.deepcopy(items[si])
            original['sub_topic'] = row['sub_topic']
            original['relevance'] = row['relevance']
            original['hot_level'] = row['hot_level']
            original['rank'] = len(filtered_items) + 1
            filtered_items.append(original)

        # 子主题数量控制：每个主题最多 10 条
        topic_counts = {}
        limited_items = []
        for it in filtered_items:
            t = it.get('sub_topic', '其他')
            if topic_counts.get(t, 0) < 10:
                limited_items.append(it)
                topic_counts[t] = topic_counts.get(t, 0) + 1

        # 重新校正 rank
        for i, it in enumerate(limited_items):
            it['rank'] = i + 1

        result = {
            'items': limited_items,
            'stats': {
                'input_count': n_input,
                'output_count': len(limited_items),
                'dropped_count': n_input - len(limited_items),
                'top_topics': sorted(topic_counts.keys(), key=lambda x: topic_counts[x], reverse=True)[:5]
            }
        }

        self.save_json(output_file, result)
        return {'count': len(limited_items), 'input_count': n_input, 'api_calls': 1}


# 向后兼容
def run_filter_rank(input_file: str, output_file: str, date_str: str) -> dict:
    return FilterRankModule(date_str).run(input_file, output_file)
