#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
summarize.py — LLM 摘要模块
"""

from __future__ import annotations

import json
from typing import List, Sequence

from utils import AppConfig, LLMClient, WorkModule, PromptLoader, TEMPLATE_SUMMARIZE
from utils.domain import FilteredItem, SummaryItem


class SummarizeModule(WorkModule):
    """LLM 摘要"""

    def __init__(self, config: AppConfig):
        super().__init__('summarize')
        self.llm_client = LLMClient(config.llm_client_cfg)
        self._app_config = config

    def _load_items(self, input_file: str) -> List[FilteredItem]:
        """加载输入文件，支持 JSON (含 items) 或 JSONL 格式"""
        data = self.load_json(input_file)
        if data is not None and isinstance(data, dict):
            return [FilteredItem.from_dict(it) for it in data.get('items', [])]
        raw_items = self.load_jsonl(input_file)
        return [FilteredItem.from_dict(it) for it in raw_items]

    def _build_prompts(self, items: Sequence[FilteredItem]) -> tuple:
        """构建 system/user 提示词"""
        item_cap = int(self._app_config.links.llm.summarize_item_cap)
        rows = []
        for i, it in enumerate(items):
            body = self.clip_text(it.summary, item_cap)
            summ = self.clip_text(it.summary, item_cap)
            rows.append({
                'index': i, 'title': it.title, 'source': it.source,
                'url': it.url, 'summary': summ, 'body': body,
                'main_section': it.main_section,
                'sub_section': it.sub_section
            })

        return PromptLoader().load_with_config(
            TEMPLATE_SUMMARIZE,
            self._app_config.protocols,
            news_json=json.dumps(rows, ensure_ascii=False, indent=2),
        )

    def _merge_items(self, filtered_item: FilteredItem, llm_data: dict) -> SummaryItem:
        """合并 FilteredItem 和 LLM 数据"""
        fields = self._app_config.protocols.protocol.summarize.fields
        summarize_keys = [f.name for f in fields]
        llm_result = {}
        for k in summarize_keys:
            v = llm_data.get(k)
            if v:
                llm_result[k] = v

        for list_field in ['vertical_tags', 'general_tags']:
            v = llm_data.get(list_field)
            if v and isinstance(v, list):
                llm_result[list_field] = v
            elif v:
                llm_result[list_field] = [v] if isinstance(v, str) else []

        return SummaryItem.from_filtered_and_llm(filtered_item, llm_result)

    def run(self, input_file: str, output_file: str) -> dict:
        """执行完整流程"""
        assembly_cfg = self._app_config.modules.assembly
        max_items = min(max(1, int(assembly_cfg.summary_unified_max_items)), 500)

        filtered_items = self._load_items(input_file)[:max_items]
        n_items = len(filtered_items)

        if n_items == 0:
            self.save_json(output_file, {'items': [], 'blocks': {}})
            return {'count': 0, 'api_calls': 0, 'unified': True}

        system, user = self._build_prompts(filtered_items)
        data = self.llm_client.call_json(system, user)

        by_source, drop = SummaryItem.extract_articles(data)
        
        # 调试：打印 LLM 响应的原始统计
        raw_articles = data.get('articles', []) if isinstance(data, dict) else []
        print(f"[DEBUG] 输入 {len(filtered_items)} 条，LLM 返回 {len(raw_articles)} 条 articles")
        print(f"[DEBUG] 有效 source_index 匹配 {len(by_source)} 条，drop_indices 包含 {len(drop)} 条")
        
        out_items = []
        print(f"[DEBUG] 预计保留: {len(by_source)} 条（LLM 返回且不在 drop_indices 中）")
        for i, filtered_item in enumerate(filtered_items):
            if i in drop:
                print(f"  [DEBUG] 跳过第 {i} 条 (在 drop_indices 中)")
                continue
            if i not in by_source:
                print(f"  [DEBUG] 跳过第 {i} 条 (LLM 未返回该条数据)")
                continue
            llm_data = by_source.get(i, {})
            #print(f"  [DEBUG] 处理第 {i} 条: {filtered_item.title[:40]}...")
            summary_item = self._merge_items(filtered_item, llm_data)
            out_items.append(summary_item)

        self.save_json(output_file, {'items': [it.__dict__.copy() for it in out_items], 'blocks': data.get('blocks', {})})
        return {'count': len(out_items), 'api_calls': 1, 'unified': True}