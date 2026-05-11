#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
summarize.py — LLM 摘要模块
"""

from __future__ import annotations

import json
from typing import List

from utils import PROMPTS_DIR, LLMClient, load_assembly_config
from utils.base import BaseModule
from utils.prompt_loader import PromptLoader


class SummarizeModule(BaseModule):
    """LLM 摘要"""

    TEMPLATE = 'summarizer.md.j2'
    KEYS = ('headline', 'plain_explain', 'impact_1', 'impact_2', 'digest_for_outline', 'tag')

    def __init__(self, date_str: str):
        super().__init__(date_str, 'summarize')
        self.llm_client = LLMClient()

    def _load_items(self, input_file: str) -> List[dict]:
        """加载输入文件，支持 JSON (含 items) 或 JSONL 格式"""
        data = self.load_json(input_file)
        if data is not None and isinstance(data, dict):
            return data.get('items', [])
        return self.load_jsonl(input_file)

    def _build_prompts(self, items: List[dict]) -> tuple:
        """构建 system/user 提示词"""
        cfg = load_assembly_config()
        coverage = cfg.get('header_coverage', '硬件芯片 · 模型 · AI工程 · 产业商业 · 政策地缘')
        ids = ', '.join(m['id'] for m in cfg.get('modules', []))

        item_cap = min(max(300, int(cfg.get('summary_unified_item_max_chars', 1800))), 3000)
        rows = []
        for i, it in enumerate(items):
            body = self.clip_text(it.get('content') or it.get('summary', ''), item_cap)
            summ = self.clip_text(it.get('summary', ''), item_cap)
            rows.append({
                'index': i, 'title': it.get('title', ''), 'source': it.get('source', ''),
                'url': it.get('url', ''), 'summary': summ, 'body': body,
                'sub_topic': it.get('sub_topic', 'unknown')
            })

        loader = PromptLoader(PROMPTS_DIR)
        ctx = {'date_str': self.date_str, 'coverage': coverage, 'ids_str': ids,
               'news_json': json.dumps(rows, ensure_ascii=False, indent=2)}
        rendered = loader.render(self.TEMPLATE, ctx)
        parts = loader.parse_frontmatter(rendered or '')
        return parts.get('system', ''), parts.get('user', '')

    def _extract_articles(self, data: dict, n_items: int) -> dict:
        """从 LLM 响应中提取 articles 和 drop_indices"""
        if not isinstance(data, dict):
            return {}, set()

        by_source = {}
        for a in data.get('articles', []):
            if not isinstance(a, dict):
                continue
            si = a.get('source_index')
            if si is None:
                continue
            try:
                by_source[int(si)] = a
            except (ValueError, TypeError):
                continue

        drop = set()
        for x in data.get('deduplication', {}).get('drop_indices', []):
            try:
                drop.add(int(x))
            except (ValueError, TypeError):
                continue

        return by_source, drop

    def run(self, input_file: str, output_file: str) -> dict:
        """执行完整流程"""
        cfg = load_assembly_config()
        max_items = min(max(1, int(cfg.get('summary_unified_max_items', 120))), 500)
        cap = max(200, int(cfg.get('summary_max_chars', 320)))

        items = self._load_items(input_file)[:max_items]
        n_items = len(items)

        if n_items == 0:
            self.save_json(output_file, {'items': [], 'blocks': {}})
            return {'count': 0, 'api_calls': 0, 'unified': True}

        # 调用 LLM
        system, user = self._build_prompts(items)
        data = self.llm_client.call_json(system, user, temperature=0.3, max_tokens=20480)

        # 提取结果
        by_source, drop = self._extract_articles(data, n_items)

        # 合并到原始 items
        out_items = []
        for i, it in enumerate(items):
            if i in drop:
                continue
            if i in by_source:
                row = by_source[i]
                for k in self.KEYS:
                    v = row.get(k)
                    if v:
                        it[k] = v
            out_items.append(it)

        self.save_json(output_file, {'items': out_items, 'blocks': data.get('blocks', {})})
        return {'count': len(out_items), 'api_calls': 1, 'unified': True}


# 向后兼容
def run_summarize(input_file: str, output_file: str, date_str: str) -> dict:
    return SummarizeModule(date_str).run(input_file, output_file)
