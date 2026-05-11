#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
summarize.py — LLM 摘要模块
"""

from __future__ import annotations

import copy
import json
import os
import re
from typing import Any, Dict, List, Optional

from utils import PROMPTS_DIR, load_assembly_config
from utils.base import BaseModule
from utils.prompt_loader import PromptLoader

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class SummarizeModule(BaseModule):
    """LLM 摘要"""

    TEMPLATE = 'summarizer.md.j2'
    KEYS = ('point', 'one_liner', 'plain_explain', 'impact_1', 'impact_2', 'digest_for_outline')

    def __init__(self, date_str: str, llm_config: dict):
        super().__init__(date_str, 'summarize')
        self.llm_config = llm_config
        self.model = llm_config.get('model_name', '')

    def _client(self) -> Optional[Any]:
        """创建 LLM 客户端"""
        if OpenAI is None:
            raise ImportError('需要安装 openai: pip install openai')
        key = self.llm_config.get('api_key')
        url = self.llm_config.get('base_url')
        if not (key and url and self.model):
            return None
        try:
            return OpenAI(api_key=key, base_url=url)
        except Exception:
            return None

    def _call(self, client, system: str, user: str) -> Optional[str]:
        """调用 LLM"""
        try:
            resp = client.chat.completions.create(
                model=self.model, n=1,
                messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f'LLM 调用失败: {e}')
            return None

    def _build_prompts(self, items: List[dict]) -> tuple:
        """构建 system/user 提示词"""
        cfg = load_assembly_config()
        coverage = cfg.get('header_coverage', '硬件芯片 · 模型 · AI工程 · 产业商业 · 政策地缘')
        ids = ', '.join(m['id'] for m in cfg.get('modules', []))

        # 截断内容
        item_cap = min(max(300, int(cfg.get('summary_unified_item_max_chars', 1800))), 3000)
        rows = []
        for i, it in enumerate(items):
            body = self.clip_text(it.get('content') or it.get('summary', ''), item_cap)
            summ = self.clip_text(it.get('summary', ''), item_cap)
            rows.append({
                'index': i, 'title': it.get('title', ''), 'source': it.get('source', ''),
                'url': it.get('url', ''), 'summary': summ, 'body': body,
                'module_guess': it.get('_matched_module', 'unknown')
            })

        loader = PromptLoader(PROMPTS_DIR)
        ctx = {'date_str': self.date_str, 'coverage': coverage, 'ids_str': ids, 'news_json': json.dumps(rows, ensure_ascii=False, indent=2)}
        rendered = loader.render(self.TEMPLATE, ctx)
        parts = loader.parse_frontmatter(rendered or '')
        return parts.get('system', ''), parts.get('user', '')

    def _parse_response(self, text: Optional[str]) -> dict:
        """解析 LLM 响应"""
        if not text:
            return {}
        raw = text.strip()
        if raw.startswith('```'):
            raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'\s*```$', '', raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r'\{[\s\S]*\}', raw)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        return {}

    def _validate(self, data: dict, n_items: int) -> tuple:
        """校验响应"""
        if not isinstance(data, dict):
            return False, ['根对象须为 JSON 对象']

        cfg = load_assembly_config()
        modules = [m['id'] for m in cfg.get('modules', [])]

        errs = []
        drop = set()
        try:
            drop = {int(x) for x in data.get('deduplication', {}).get('drop_indices', [])}
        except Exception:
            pass
        kept = [i for i in range(n_items) if i not in drop]
        articles = data.get('articles', [])

        by_si = {}
        for a in articles:
            if not isinstance(a, dict):
                continue
            si = a.get('source_index')
            if si is None:
                continue
            try:
                by_si[int(si)] = a
            except Exception:
                continue

        if len(articles) != len(by_si):
            errs.append('articles 中存在重复 source_index')
        if set(kept) != set(by_si.keys()):
            errs.append('articles 与保留 index 不一致')

        for i in kept:
            row = by_si.get(i, {})
            for k in self.KEYS:
                if not str(row.get(k, '')).strip():
                    errs.append(f'source_index={i} 的 {k} 为空')

        blk = data.get('blocks', {})
        if not isinstance(blk, dict) or not isinstance(blk.get('header'), dict):
            errs.append('blocks.header 不合法')
        if not isinstance(blk.get('footer'), dict):
            errs.append('blocks.footer 不合法')
        for mid in modules:
            if mid not in blk.get('footer', {}):
                errs.append(f'blocks.footer 缺少 {mid}')

        return len(errs) == 0, errs

    def _repair_prompt(self, errors: List[str], kept: List[int]) -> str:
        """生成修复提示"""
        cfg = load_assembly_config()
        modules = [m['id'] for m in cfg.get('modules', [])]
        body = '\n'.join(f'- {e}' for e in errors[:20])
        return (
            f'\n\n---\n\n【强制补全】上一轮校验未通过:\n{body}\n\n'
            f'保留 index: {kept}，articles 数量必须等于 {len(kept)}，'
            f'footer 键: {modules}'
        )

    def _merge_articles(self, a: Optional[dict], b: Optional[dict]) -> List[dict]:
        """合并两轮 articles"""
        by_ix = {}
        for src in (a, b):
            if not src:
                continue
            for row in src.get('articles', []):
                if not isinstance(row, dict):
                    continue
                try:
                    ix = int(row['source_index'])
                except Exception:
                    continue
                if ix not in by_ix:
                    by_ix[ix] = {'source_index': ix}
                for k in self.KEYS:
                    v = str(row.get(k, '')).strip()
                    if v:
                        by_ix[ix][k] = v
        return sorted(by_ix.values(), key=lambda x: x['source_index'])

    def _merge_payload(self, a: Optional[dict], b: Optional[dict]) -> dict:
        """合并两轮完整响应"""
        if not a and not b:
            return {}
        if not b:
            return copy.deepcopy(a)
        if not a:
            return copy.deepcopy(b)

        cfg = load_assembly_config()
        modules = [m['id'] for m in cfg.get('modules', [])]

        out = copy.deepcopy(b)
        out['articles'] = self._merge_articles(a, b)
        out['deduplication'] = copy.deepcopy(b.get('deduplication') or a.get('deduplication', {}))

        ba, bb = a.get('blocks', {}), b.get('blocks', {})
        header_out = {
            'tags_full': str(bb.get('header', {}).get('tags_full', '')).strip() or str(ba.get('header', {}).get('tags_full', '')).strip(),
            'data_sources': str(bb.get('header', {}).get('data_sources', '')).strip() or str(ba.get('header', {}).get('data_sources', '')).strip(),
        }
        footer_out = {}
        fa, fb = ba.get('footer', {}), bb.get('footer', {})
        for mid in modules:
            v = str(fb.get(mid, '')).strip() or str(fa.get(mid, '')).strip() or '今日暂无相关报道'
            footer_out[mid] = v

        out['blocks'] = {'header': header_out, 'footer': footer_out}
        return out

    def _fill_missing(self, item: dict, cap: int) -> None:
        """填充缺失字段"""
        title = (item.get('title') or '').strip()
        blob = (item.get('summary') or title).strip()

        if not item.get('point'):
            item['point'] = self.clip_text(title, 42) or '（基于标题的简要标注）'
        if not item.get('one_liner'):
            item['one_liner'] = self.clip_text(title, 38) or item['point'][:38]
        if not item.get('plain_explain'):
            item['plain_explain'] = self.clip_text(blob, 120)
        if not item.get('impact_1'):
            item['impact_1'] = '对关注相关赛道与供应链的读者有信息增量'
        if not item.get('impact_2'):
            item['impact_2'] = '具体影响需结合后续落地与独立信源核实'
        if not item.get('digest_for_outline'):
            item['digest_for_outline'] = self.clip_text(blob, max(cap, 260))

        dig = (item.get('digest_for_outline') or '').strip()
        base = (item.get('summary') or '').strip()
        item['_ai_summary'] = (dig or base or item.get('content', ''))[:cap]

    def run(self, input_file: str, output_file: str) -> dict:
        """执行完整流程"""
        cfg = load_assembly_config()
        max_items = min(max(1, int(cfg.get('summary_unified_max_items', 120))), 500)
        cap = max(200, int(cfg.get('summary_max_chars', 320)))

        items = self.load_jsonl(input_file)[:max_items]

        client = self._client()
        if not client:
            for it in items:
                self._fill_missing(it, cap)
            self.save_json(output_file, {'items': items, 'blocks': None})
            return {'count': len(items), 'api_calls': 0, 'unified': False}

        system, user = self._build_prompts(items)
        raw = self._call(client, system, user)
        data = self._parse_response(raw)
        api_calls = 1

        if not data:
            for it in items:
                self._fill_missing(it, cap)
            self.save_json(output_file, {'items': items, 'blocks': None})
            return {'count': len(items), 'api_calls': api_calls, 'unified': False}

        ok, errs = self._validate(data, len(items))
        if not ok:
            print(f'校验未通过 ({len(errs)} 项)，尝试修复...')
            kept = [i for i in range(len(items)) if i not in {int(x) for x in data.get('deduplication', {}).get('drop_indices', []) if str(x).isdigit()}]
            repair = self._repair_prompt(errs, kept)
            raw2 = self._call(client, system, user + repair)
            api_calls += 1
            data2 = self._parse_response(raw2)
            data = self._merge_payload(data, data2)

        # 合并结果
        drop = set()
        try:
            drop = {int(x) for x in data.get('deduplication', {}).get('drop_indices', [])}
        except Exception:
            pass

        by_source = {}
        for a in data.get('articles', []):
            if isinstance(a, dict) and a.get('source_index') is not None:
                try:
                    by_source[int(a['source_index'])] = a
                except Exception:
                    pass

        out_items = []
        for i, it in enumerate(items):
            if i in drop:
                continue
            if i in by_source:
                row = by_source[i]
                for k in self.KEYS:
                    if row.get(k):
                        it[k] = row[k]
            self._fill_missing(it, cap)
            out_items.append(it)

        self.save_json(output_file, {'items': out_items, 'blocks': data.get('blocks')})
        return {'count': len(out_items), 'api_calls': api_calls, 'unified': True}


# 向后兼容
def run_summarize(input_file: str, output_file: str, date_str: str, config: dict) -> dict:
    return SummarizeModule(date_str, config).run(input_file, output_file)
