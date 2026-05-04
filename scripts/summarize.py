#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
summarize.py — 统一 LLM 摘要

- Prompt：`kit/prompts&templates/01_task.md`、`02_response_protocol.md` + `unified/system.md.j2`、运行时注入
- 输出单文件 `summary.json`：`{"items":[...], "blocks":{...}}`（无 blocks 可为 null）
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from scripts.base_config import PROMPTS_DIR, TEMPLATES_DIR

# ----- 路径与常量（原 unified_digest）-----

PATH_TASK = os.path.join(PROMPTS_DIR, '01_task.md')
PATH_RESPONSE_PROTOCOL = os.path.join(PROMPTS_DIR, '02_response_protocol.md')

_TEMPLATE_SYSTEM = 'system.md.j2'
_TEMPLATE_RUNTIME_INJECTION = 'runtime_injection.md.j2'

JSON_ARTICLE_KEYS = (
    'point',
    'one_liner',
    'plain_explain',
    'impact_1',
    'impact_2',
    'digest_for_outline',
)

@lru_cache(maxsize=1)
def _jinja_env() -> Environment:
    return Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)


def _read(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def build_system_prompt() -> str:
    """System：执行约束；正文见 kit/prompts&templates/system.md.j2。"""
    text = _jinja_env().get_template(_TEMPLATE_SYSTEM).render()
    return text.strip()


def _render_runtime_injection(
    date_str: str,
    coverage: str,
    ids_str: str,
    news_json: str,
) -> str:
    return _jinja_env().get_template(_TEMPLATE_RUNTIME_INJECTION).render(
        date_str=date_str,
        coverage=coverage,
        ids_str=ids_str,
        news_json=news_json,
    )


def build_user_prompt(
    date_str: str,
    news_json: str,
    modules_data: dict,
) -> str:
    """User：事项 + 协议 + 运行时注入（清单 JSON）。"""
    task = _read(PATH_TASK)
    protocol = _read(PATH_RESPONSE_PROTOCOL)
    coverage = modules_data.get(
        'header_coverage',
        '硬件芯片 · 模型 · AI工程 · 产业商业 · 政策地缘',
    )
    ids = [m['id'] for m in modules_data.get('modules', [])]
    ids_str = ', '.join(ids)

    injection = _render_runtime_injection(date_str, coverage, ids_str, news_json)

    return (
        f'{task.strip()}\n\n---\n\n'
        f'{protocol.strip()}\n\n'
        f'{injection}'
    )


def parse_llm_json_response(text: Optional[str]) -> Dict[str, Any]:
    if not text or not text.strip():
        return {}
    raw = text.strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.IGNORECASE)
        raw = re.sub(r'\s*```$', '', raw)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r'\{[\s\S]*\}', raw)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {}


def _kept_index_list(n_items: int, data: Dict[str, Any]) -> List[int]:
    drop_raw = data.get('deduplication', {}).get('drop_indices') or []
    try:
        drop = {int(x) for x in drop_raw}
    except (TypeError, ValueError):
        drop = set()
    return [i for i in range(n_items) if i not in drop]


def validate_unified_response(
    data: Dict[str, Any],
    n_items: int,
    modules_data: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """校验 LLM 根 JSON：`articles` 与保留 index 对齐且六项字符串全非空；`blocks` 齐全。"""
    errs: List[str] = []
    if not isinstance(data, dict):
        return False, ['根对象须为 JSON 对象']

    dedup = data.get('deduplication')
    if not isinstance(dedup, dict):
        errs.append('缺少合法 deduplication 对象')
        return False, errs

    kept = _kept_index_list(n_items, data)
    articles = data.get('articles')
    if not isinstance(articles, list):
        errs.append('articles 须为数组')
        return False, errs

    by_si: Dict[int, Dict[str, Any]] = {}
    for a in articles:
        if not isinstance(a, dict):
            errs.append('articles 中存在非对象元素')
            continue
        si = a.get('source_index')
        if si is None:
            errs.append('某条 article 缺少 source_index')
            continue
        try:
            ix = int(si)
        except (TypeError, ValueError):
            errs.append(f'source_index 非法: {si!r}')
            continue
        if ix in by_si:
            errs.append(f'重复的 source_index: {ix}')
        else:
            by_si[ix] = a

    if len(articles) != len(by_si):
        errs.append(
            f'articles 中存在重复或无效 source_index（原始 {len(articles)} 条，唯一有效 {len(by_si)} 条）'
        )

    exp = set(kept)
    got = set(by_si.keys())
    if exp != got:
        if exp - got:
            errs.append(f'遗漏保留 index 的 article: {sorted(exp - got)}')
        if got - exp:
            errs.append(f'source_index 不在保留集（应已 drop）: {sorted(got - exp)}')
    if len(articles) != len(kept):
        errs.append(
            f'articles 条数 {len(articles)} 与保留条数 {len(kept)} 不一致（须一一对应）'
        )

    for i in kept:
        row = by_si.get(i)
        if not row:
            continue
        for k in JSON_ARTICLE_KEYS:
            v = row.get(k)
            if v is None or not str(v).strip():
                errs.append(f'source_index={i} 的 `{k}` 为空或缺失')

    module_ids = [
        m['id']
        for m in modules_data.get('modules', [])
        if isinstance(m, dict) and m.get('id')
    ]
    blk = data.get('blocks')
    if not isinstance(blk, dict):
        errs.append('blocks 须为对象')
    else:
        header = blk.get('header')
        if not isinstance(header, dict):
            errs.append('blocks.header 须为对象')
        else:
            if not str(header.get('tags_full') or '').strip():
                errs.append('blocks.header.tags_full 为空')
            if not str(header.get('data_sources') or '').strip():
                errs.append('blocks.header.data_sources 为空')
        footer = blk.get('footer')
        if not isinstance(footer, dict):
            errs.append('blocks.footer 须为对象')
        else:
            for mid in module_ids:
                if mid not in footer:
                    errs.append(f'blocks.footer 缺少模块键 `{mid}`')
                elif not str(footer.get(mid) or '').strip():
                    errs.append(f'blocks.footer.{mid} 为空字符串')

    return len(errs) == 0, errs


def merge_llm_articles(
    data_a: Optional[Dict[str, Any]],
    data_b: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """合并两轮返回的 articles：同一 source_index 下，非空字段后出现的覆盖先出现的（补全轮优先于首轮）。"""
    by_ix: Dict[int, Dict[str, Any]] = {}
    for src in (data_a, data_b):
        if not src:
            continue
        for row in src.get('articles') or []:
            if not isinstance(row, dict):
                continue
            try:
                ix = int(row['source_index'])
            except (KeyError, TypeError, ValueError):
                continue
            if ix not in by_ix:
                by_ix[ix] = {'source_index': ix}
            acc = by_ix[ix]
            for k in JSON_ARTICLE_KEYS:
                v = str(row.get(k) or '').strip()
                if v:
                    acc[k] = v
    return sorted(by_ix.values(), key=lambda x: x['source_index'])


def merge_llm_payload(
    data_a: Optional[Dict[str, Any]],
    data_b: Optional[Dict[str, Any]],
    modules_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    合并首轮与补全轮完整 payload：articles 按字段合并；deduplication 优先补全轮；
    blocks.header/footer 逐键择优（非空优先补全轮）。
    """
    if not data_a and not data_b:
        return {}
    if not data_b:
        return copy.deepcopy(data_a)  # type: ignore[arg-type]
    if not data_a:
        return copy.deepcopy(data_b)

    out = copy.deepcopy(data_b)
    out['articles'] = merge_llm_articles(data_a, data_b)

    if isinstance(data_b.get('deduplication'), dict):
        out['deduplication'] = copy.deepcopy(data_b['deduplication'])
    else:
        out['deduplication'] = copy.deepcopy(data_a.get('deduplication') or {})

    module_ids = [
        m['id']
        for m in modules_data.get('modules', [])
        if isinstance(m, dict) and m.get('id')
    ]
    ba = data_a.get('blocks') if isinstance(data_a.get('blocks'), dict) else {}
    bb = data_b.get('blocks') if isinstance(data_b.get('blocks'), dict) else {}
    ha = ba.get('header') if isinstance(ba.get('header'), dict) else {}
    hb = bb.get('header') if isinstance(bb.get('header'), dict) else {}
    fa = ba.get('footer') if isinstance(ba.get('footer'), dict) else {}
    fb = bb.get('footer') if isinstance(bb.get('footer'), dict) else {}

    header_out = {
        'tags_full': str(hb.get('tags_full') or '').strip()
        or str(ha.get('tags_full') or '').strip(),
        'data_sources': str(hb.get('data_sources') or '').strip()
        or str(ha.get('data_sources') or '').strip(),
    }
    footer_out: Dict[str, str] = {}
    for mid in module_ids:
        vb = str(fb.get(mid) or '').strip()
        va = str(fa.get(mid) or '').strip()
        footer_out[mid] = vb or va or '今日暂无相关报道'

    if not isinstance(out.get('blocks'), dict):
        out['blocks'] = {}
    out['blocks']['header'] = header_out
    out['blocks']['footer'] = footer_out
    return out


def _clip_outline(text: str, max_chars: int) -> str:
    t = re.sub(r'\s+', ' ', (text or '').strip())
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1] + '…'


def fill_missing_article_fields(item: dict, display_cap: int) -> List[str]:
    """
    LLM 漏条或漏字段时，用标题与 RSS 摘要做兜底，保证 summary.json 可消费。
    返回本次补全的字段名列表（写入 `_article_autofill_keys` 便于排查）。
    """
    patched: List[str] = []
    title = (item.get('title') or '').strip()
    summary = (item.get('summary') or '').strip()
    blob = summary or title

    if not str(item.get('point') or '').strip():
        item['point'] = _clip_outline(title, 42) or '（基于标题的简要标注）'
        patched.append('point')
    if not str(item.get('one_liner') or '').strip():
        item['one_liner'] = _clip_outline(title, 38) or str(item.get('point') or '')[:38]
        patched.append('one_liner')
    if not str(item.get('plain_explain') or '').strip():
        item['plain_explain'] = _clip_outline(blob, 120)
        patched.append('plain_explain')
    if not str(item.get('impact_1') or '').strip():
        item['impact_1'] = '对关注相关赛道与供应链的读者有信息增量'
        patched.append('impact_1')
    if not str(item.get('impact_2') or '').strip():
        item['impact_2'] = '具体影响需结合后续落地与独立信源核实'
        patched.append('impact_2')
    if not str(item.get('digest_for_outline') or '').strip():
        cap = max(display_cap, 260)
        item['digest_for_outline'] = _clip_outline(blob, cap)
        patched.append('digest_for_outline')

    dig = (item.get('digest_for_outline') or '').strip()
    base = (item.get('summary') or '').strip()
    item['_ai_summary'] = (dig or base or item.get('content') or '')[:display_cap]
    if patched:
        item['_article_autofill_keys'] = patched
    return patched


def build_repair_appendix(
    errors: List[str],
    kept_indices: List[int],
    module_ids: List[str],
) -> str:
    lines = errors[:35]
    body = '\n'.join(f'- {x}' for x in lines)
    ktxt = ', '.join(str(x) for x in kept_indices)
    footer_keys = '、'.join(f'`{m}`' for m in module_ids) if module_ids else '（与运行时注入一致）'
    return (
        '\n\n---\n\n【强制补全】上一轮输出未通过程序校验，你必须改正后 **重新输出完整根 JSON**（不得只返回片段）。\n'
        f'{body}\n\n'
        f'保留 index 列表（须与 `deduplication.drop_indices` 一致）：[{ktxt}]；'
        f'`articles` 必须恰好 **{len(kept_indices)}** 条，`source_index` 无重复、无遗漏；每条必须包含且六项均为非空字符串：'
        '`point`、`one_liner`、`plain_explain`、`impact_1`、`impact_2`、`digest_for_outline`。\n'
        f'`blocks.footer` 须包含键 {footer_keys}，且每键为非空字符串（无稿可写「今日暂无相关报道」）。'
    )


def merge_unified_into_items(
    items: List[dict],
    data: Dict[str, Any],
    display_cap: int,
) -> List[dict]:
    drop_raw = data.get('deduplication', {}).get('drop_indices') or []
    try:
        drop = {int(x) for x in drop_raw}
    except (TypeError, ValueError):
        drop = set()

    by_source: Dict[int, Dict[str, Any]] = {}
    for a in data.get('articles') or []:
        if not isinstance(a, dict):
            continue
        si = a.get('source_index')
        if si is None:
            continue
        try:
            by_source[int(si)] = a
        except (TypeError, ValueError):
            continue

    out: List[dict] = []
    for i, item in enumerate(items):
        if i in drop:
            continue
        row = by_source.get(i)
        if row:
            for k in JSON_ARTICLE_KEYS:
                v = row.get(k)
                if v is not None and str(v).strip():
                    item[k] = str(v).strip()
            dig = (item.get('digest_for_outline') or '').strip()
            base = (item.get('summary') or '').strip()
            # 模型给出的概要压缩稿优先于 RSS 长摘要，便于控制「概要」字数（见 02_response_protocol）
            item['_ai_summary'] = (dig or base or item.get('content') or '')[:display_cap]
        else:
            item['_ai_summary'] = (item.get('summary') or item.get('content') or '')[:display_cap]
        fill_missing_article_fields(item, display_cap)
        out.append(item)
    return out


def extract_blocks(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    blk = data.get('blocks')
    if not isinstance(blk, dict):
        return None
    return blk


# ----- 配置与入口 -----


def load_project_config() -> dict:
    from scripts.base_config import CONFIG_EXAMPLE_JSON, CONFIG_JSON

    if os.path.exists(CONFIG_JSON):
        with open(CONFIG_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    with open(CONFIG_EXAMPLE_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_modules_context() -> Dict[str, Any]:
    from scripts.base_config import load_assembly_config

    return load_assembly_config()


def load_unified_settings(modules_data: dict) -> Dict[str, int]:
    defaults = {
        'summary_max_chars': 320,
        'summary_unified_max_items': 120,
        'summary_unified_item_max_chars': 1800,
    }
    out = defaults.copy()
    for k in defaults:
        if k in modules_data:
            out[k] = int(modules_data[k])
    out['summary_unified_max_items'] = max(1, out['summary_unified_max_items'])
    out['summary_unified_item_max_chars'] = max(300, out['summary_unified_item_max_chars'])
    return out


def build_llm_client(config: dict):
    api_key = config.get('api_key', '')
    base_url = config.get('base_url', '')
    model_name = config.get('model_name', '')

    if not api_key or not base_url or not model_name:
        return None

    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url=base_url)
    except Exception:
        return None


def build_news_json_payload(items: List[dict], per_item_max: int) -> str:
    rows = []
    for i, it in enumerate(items):
        body = (it.get('content') or it.get('summary') or '').strip()
        if len(body) > per_item_max:
            body = body[:per_item_max] + '...[已截断]'
        summ = (it.get('summary') or '').strip()
        if len(summ) > per_item_max:
            summ = summ[:per_item_max] + '...[已截断]'
        rows.append({
            'index': i,
            'title': it.get('title', ''),
            'source': it.get('source', ''),
            'url': it.get('url', ''),
            'summary': summ,
            'body': body,
            'module_guess': it.get('_matched_module', 'unknown'),
        })
    return json.dumps(rows, ensure_ascii=False, indent=2)


def call_unified_llm(
    client,
    model_name: str,
    user_content: str,
    system_content: str,
) -> Optional[str]:
    try:
        response = client.chat.completions.create(
            model=model_name,
            n=1,
            messages=[
                {'role': 'system', 'content': system_content},
                {'role': 'user', 'content': user_content},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f'⚠️ 统一 LLM 调用失败: {e}')
        return None


def run_summarize(input_file: str, output_file: str, date_str: str, config: dict):
    modules_data = load_modules_context()
    settings = load_unified_settings(modules_data)
    display_cap = settings['summary_max_chars']
    max_items = settings['summary_unified_max_items']
    item_cap = settings['summary_unified_item_max_chars']

    model_name = config.get('model_name', '')
    client = build_llm_client(config)

    items: List[dict] = []
    with open(input_file, 'r', encoding='utf-8') as fin:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f'⚠️ 跳过无效 JSON 行: {e}')

    out_dir = os.path.dirname(output_file) or '.'

    def _write_bundle(
        merged_items: List[dict],
        blocks: Optional[Dict[str, Any]],
        *,
        unified: bool,
        api_calls: int,
    ) -> Dict[str, Any]:
        os.makedirs(out_dir, exist_ok=True)
        bundle = {'items': merged_items, 'blocks': blocks}
        with open(output_file, 'w', encoding='utf-8') as fout:
            json.dump(bundle, fout, ensure_ascii=False, indent=2)
        return {
            'count': len(merged_items),
            'api_calls': api_calls,
            'unified': unified,
            'blocks_written': bool(blocks),
        }

    if not client:
        for item in items:
            fill_missing_article_fields(item, display_cap)
        return _write_bundle(items, None, unified=False, api_calls=0)

    if len(items) > max_items:
        print(f'⚠️ 仅提交前 {max_items} 条（共 {len(items)}），可调 engineering.json → assembly.summary_unified_max_items')
        items = items[:max_items]

    news_json = build_news_json_payload(items, item_cap)
    user_prompt = build_user_prompt(date_str, news_json, modules_data)
    system_prompt = build_system_prompt()

    raw = call_unified_llm(client, model_name, user_prompt, system_prompt)
    api_calls = 1

    data = parse_llm_json_response(raw) if raw else {}
    module_ids = [
        m['id']
        for m in modules_data.get('modules', [])
        if isinstance(m, dict) and m.get('id')
    ]

    if not data:
        print('⚠️ 统一响应解析失败或未返回 JSON，输出退化为仅 RSS 摘要 + 字段兜底')
        for item in items:
            fill_missing_article_fields(item, display_cap)
        merged = items
        blocks_obj: Optional[Dict[str, Any]] = None
    else:
        ok, errs = validate_unified_response(data, len(items), modules_data)
        data_final: Dict[str, Any] = data
        if not ok:
            print(f'⚠️ 统一摘要 JSON 校验未通过（{len(errs)} 项）:', errs[:20])
            repair = build_repair_appendix(
                errs,
                _kept_index_list(len(items), data),
                module_ids,
            )
            raw2 = call_unified_llm(
                client, model_name, user_prompt + repair, system_prompt
            )
            api_calls += 1
            data2 = parse_llm_json_response(raw2) if raw2 else {}
            if data2:
                ok2, errs2 = validate_unified_response(data2, len(items), modules_data)
                # 按字段合并两轮 articles，避免补全轮只改正部分 index 时丢掉首轮已有字段
                data_final = merge_llm_payload(data, data2, modules_data)
                if ok2:
                    pass
                else:
                    print(
                        f'⚠️ 补全轮仍未通过校验（{len(errs2)} 项），已合并两轮 articles 并将在合并后做字段兜底:',
                        errs2[:20],
                    )
            else:
                print('⚠️ 补全轮无有效 JSON，沿用首轮')
        merged = merge_unified_into_items(items, data_final, display_cap)
        blocks_obj = extract_blocks(data_final)
        n_auto = sum(1 for it in merged if it.get('_article_autofill_keys'))
        if n_auto:
            print(
                f'⚠️ 有 {n_auto} 条使用了标题/摘要兜底字段（键名见各条 `_article_autofill_keys`）'
            )

    return _write_bundle(merged, blocks_obj, unified=True, api_calls=api_calls)


# 编排侧与旧代码：`from scripts.summarize import run`
run = run_summarize


if __name__ == '__main__':
    import argparse

    from scripts.base_config import default_day_paths

    today = datetime.now().strftime('%Y-%m-%d')
    parser = argparse.ArgumentParser(description='LLM 摘要 → summary.json')
    parser.add_argument('--date', '-d', default=today, help='日期 YYYY-MM-DD（默认今天）')
    parser.add_argument(
        '-i',
        '--input',
        default=None,
        help='输入 JSONL（默认 output/<date>/ingested.jsonl）',
    )
    parser.add_argument(
        '-o',
        '--output',
        default=None,
        help='输出 summary.json（默认 output/<date>/summary.json）',
    )
    args = parser.parse_args()
    date_str = args.date
    paths = default_day_paths(date_str)
    input_file = args.input or paths['ingested']
    output_file = args.output or paths['summary']

    cfg = load_project_config()
    result = run_summarize(input_file, output_file, date_str, cfg)
    extra = ', '.join(f'{k}={v}' for k, v in result.items() if k != 'count')
    print(f"Done. count={result['count']}, {extra}")
