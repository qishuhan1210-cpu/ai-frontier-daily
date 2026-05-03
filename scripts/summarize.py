#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
summarize.py — 统一 LLM 摘要

- Prompt：`kit/prompts&templates/01_task.md`、`02_response_protocol.md` + `unified/system.md.j2`、运行时注入
- 输出单文件 `summary.json`：`{"items":[...], "blocks":{...}}`（无 blocks 可为 null）
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional

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
            dig = (row.get('digest_for_outline') or '').strip()
            base = (item.get('summary') or '').strip()
            item['_ai_summary'] = (base or dig or item.get('content') or '')[:display_cap]
        else:
            item['_ai_summary'] = (item.get('summary') or item.get('content') or '')[:display_cap]
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
        'summary_max_chars': 600,
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
            item['_ai_summary'] = (item.get('summary') or item.get('content') or '')[:display_cap]
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

    if not data:
        print('⚠️ 统一响应解析失败或未返回 JSON，输出退化为仅 RSS 摘要')
        for item in items:
            item['_ai_summary'] = (item.get('summary') or item.get('content') or '')[:display_cap]
        merged = items
        blocks_obj: Optional[Dict[str, Any]] = None
    else:
        merged = merge_unified_into_items(items, data, display_cap)
        blocks_obj = extract_blocks(data)

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
