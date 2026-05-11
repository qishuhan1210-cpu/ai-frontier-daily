#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
summarize.py — LLM 摘要模块
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Dict, List, Optional

from utils import PROMPTS_DIR, LLMClient, load_assembly_config
from utils.base import BaseModule
from utils.prompt_loader import PromptLoader


class SummarizeModule(BaseModule):
    """LLM 摘要"""

    TEMPLATE = 'summarizer.md.j2'
    # LLM 输出的 articles[] 字段（与 summarizer.md.j2 中定义的响应协议一致）
    KEYS = ('headline', 'plain_explain', 'impact_1', 'impact_2', 'digest_for_outline', 'tag')

    def __init__(self, date_str: str):
        super().__init__(date_str, 'summarize')
        self.llm_client = LLMClient()

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
                v = str(row.get(k, '')).strip()
                if not v:
                    errs.append(f'source_index={i} 的 {k} 为空')
                # 检测无效内容（仅检测文本字段）
                elif k in ('headline', 'plain_explain', 'digest_for_outline') and self._is_invalid_content(v):
                    errs.append(f'source_index={i} 的 {k} 包含无效占位符（如"点击查看原文"），请重新生成实际内容')

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

    # 无效内容检测模式
    INVALID_PATTERNS = [
        r'点击查看原文[>\s]*',
        r'阅读全文[>\s]*',
        r'原文未提供[>\s]*',
        r'查看原文[>\s]*',
        r'点击阅读[>\s]*',
    ]

    def _is_invalid_content(self, text: str) -> bool:
        """检测内容是否为无效占位符"""
        if not text or not str(text).strip():
            return True
        text_lower = str(text).lower()
        for pattern in self.INVALID_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        # 检测是否是直接复制title（长度相似且内容重复）
        return False

    def _get_valid_blob(self, item: dict) -> str:
        """获取有效的原始内容（优先 content，其次 summary，最后 title）"""
        # 优先使用原始正文 content
        content = (item.get('content') or '').strip()
        if content and not self._is_invalid_content(content):
            return content
        # 其次使用 summary（但如果无效则跳过）
        summary = (item.get('summary') or '').strip()
        if summary and not self._is_invalid_content(summary):
            return summary
        # 最后使用 title
        return (item.get('title') or '').strip()

    def _fill_missing(self, item: dict, cap: int) -> None:
        """填充缺失字段（兜底方案，当 LLM 输出不完整或使用无效内容时使用）"""
        title = (item.get('title') or '').strip()
        # 使用有效的原始内容
        blob = self._get_valid_blob(item)

        # 新字段：headline（融合 point + one_liner 的角色）
        if not item.get('headline') or self._is_invalid_content(item.get('headline')):
            # 如果旧字段存在，优先合并使用；否则基于标题生成
            old_point = item.get('point', '').strip()
            old_one_liner = item.get('one_liner', '').strip()
            if old_point and old_one_liner:
                item['headline'] = f"{old_point}：{old_one_liner}"[:50]
            elif old_point:
                item['headline'] = old_point[:50]
            elif old_one_liner:
                item['headline'] = old_one_liner[:50]
            else:
                item['headline'] = self.clip_text(title, 50) or '（基于标题的简要标注）'

        # plain_explain：如果无效，使用有效blob重新生成
        plain = item.get('plain_explain', '')
        if not plain or self._is_invalid_content(plain):
            item['plain_explain'] = self._generate_plain_explain(blob, title)

        # 影响字段：如果是兜底文案，尝试基于模块和标题生成更有意义的
        impact_1 = item.get('impact_1', '')
        impact_2 = item.get('impact_2', '')
        if not impact_1 or impact_1 == '对关注相关赛道与供应链的读者有信息增量':
            item['impact_1'] = self._generate_impact(title, item.get('_matched_module', ''), 1)
        if not impact_2 or impact_2 == '具体影响需结合后续落地与独立信源核实':
            item['impact_2'] = self._generate_impact(title, item.get('_matched_module', ''), 2)

        # digest_for_outline：如果无效，使用有效blob重新生成
        digest = item.get('digest_for_outline', '')
        if not digest or self._is_invalid_content(digest):
            item['digest_for_outline'] = self._generate_digest(blob, cap)

        # 标签兜底：基于标题关键词推断
        tag = item.get('tag', '')
        if not tag or tag == '其他':
            item['tag'] = self._infer_tag(title)

        dig = (item.get('digest_for_outline') or '').strip()
        base = self._get_valid_blob(item)
        item['_ai_summary'] = (dig or base)[:cap]

    def _generate_impact(self, title: str, module: str, idx: int) -> str:
        """基于标题和模块生成更有针对性的影响描述"""
        # 简单启发式规则
        title_lower = title.lower()
        if '融资' in title or '投资' in title or '亿元' in title:
            return ['增强相关赛道资本信心，推动产业链扩张', '加剧细分领域竞争格局重塑'][idx-1] if idx <= 2 else '对关注相关赛道的读者有信息增量'
        elif '裁员' in title or '离职' in title:
            return ['反映行业调整压力，人才流动加速', '对团队稳定性与业务连续性带来挑战'][idx-1] if idx <= 2 else '对关注相关赛道的读者有信息增量'
        elif '发布' in title or '推出' in title or '新品' in title:
            return ['丰富产品线布局，强化市场竞争力', '为用户提供更多选择，推动行业标准升级'][idx-1] if idx <= 2 else '对关注相关赛道的读者有信息增量'
        elif '合作' in title or '联合' in title:
            return ['整合双方优势资源，拓展业务边界', '对生态伙伴产生示范效应'][idx-1] if idx <= 2 else '对关注相关赛道的读者有信息增量'
        elif '政策' in title or '监管' in title or '法规' in title:
            return ['影响行业合规成本与运营模式', '推动市场规范化发展，加速优胜劣汰'][idx-1] if idx <= 2 else '对关注相关赛道的读者有信息增量'
        elif module == 'ai_engineering':
            return ['为开发者提供新工具/方法论参考', '可能改变现有工程实践与开发流程'][idx-1] if idx <= 2 else '对关注AI工程的读者有信息增量'
        elif module == 'model':
            return ['推动大模型技术边界扩展', '为下游应用提供更强大的基础能力'][idx-1] if idx <= 2 else '对关注模型技术的读者有信息增量'
        else:
            return ['对关注相关赛道与供应链的读者有信息增量', '具体影响需结合后续落地与独立信源核实'][idx-1] if idx <= 2 else '对关注相关赛道的读者有信息增量'

    def _generate_plain_explain(self, blob: str, title: str) -> str:
        """基于原始内容生成白话解释（兜底方案）"""
        # 简单提取策略：取blob的前80字，移除常见无意义开头
        cleaned = re.sub(r'^(作者[｜\|].*?编辑[｜\|].*?)[\s]*', '', blob)
        cleaned = re.sub(r'^(今日热点导览.*?)[\s]*', '', cleaned)
        cleaned = cleaned.strip()
        if len(cleaned) > 80:
            return cleaned[:78] + '…'
        return cleaned[:80] or '（基于原文的简要说明）'

    def _generate_digest(self, blob: str, cap: int) -> str:
        """基于原始内容生成摘要（兜底方案）"""
        # 简单提取策略：清理后取前cap字
        cleaned = re.sub(r'^(作者[｜\|].*?编辑[｜\|].*?)[\s]*', '', blob)
        cleaned = cleaned.strip()
        return self.clip_text(cleaned, max(cap, 260))

    def run(self, input_file: str, output_file: str) -> dict:
        """执行完整流程"""
        cfg = load_assembly_config()
        max_items = min(max(1, int(cfg.get('summary_unified_max_items', 120))), 500)
        cap = max(200, int(cfg.get('summary_max_chars', 320)))

        items = self.load_jsonl(input_file)[:max_items]

        system, user = self._build_prompts(items)
        data = self.llm_client.call_json(system, user, temperature=0.3, max_tokens=20480)
        api_calls = 1

        ok, errs = self._validate(data, len(items))
        if not ok:
            print(f'校验未通过 ({len(errs)} 项)，尝试修复...')
            kept = [i for i in range(len(items)) if i not in {int(x) for x in data.get('deduplication', {}).get('drop_indices', []) if str(x).isdigit()}]
            repair = self._repair_prompt(errs, kept)
            data2 = self.llm_client.call_json(system, user + repair, temperature=0.3, max_tokens=20480)
            api_calls += 1
            data = self._merge_payload(data, data2)

        # 合并结果前先清理 LLM 输出的无效内容
        for a in data.get('articles', []):
            if not isinstance(a, dict):
                continue
            for k in ('headline', 'plain_explain', 'digest_for_outline'):
                v = a.get(k, '')
                if self._is_invalid_content(v):
                    a[k] = ''  # 清空无效内容，让兜底生成重新填充

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
