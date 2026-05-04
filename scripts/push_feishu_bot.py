#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_feishu_bot.py — §4 群机器人：交互式卡片推送

组装 `msg_type: interactive` 请求体（标题含日期、链接《早报链接》、摘要来自 summary.json → blocks.footer），
POST 至飞书自定义机器人 Webhook。见 skill 根目录 `post-runbook.md`。

用法:
    export FEISHU_BOT_WEBHOOK='https://open.feishu.cn/open-apis/bot/v2/hook/…'
    python3 scripts/push_feishu_bot.py --date 2026-05-04 --doc-url 'https://xxx.feishu.cn/…'
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.base_config import default_day_paths, load_assembly_config

# 与 summary.json blocks.footer 字段顺序一致
_FOOTER_KEYS: Tuple[str, ...] = (
    'hardware',
    'model',
    'ai_engineering',
    'industry',
    'policy',
)

_MAX_BODY_BYTES = 20 * 1024


def _module_abbrev_by_id() -> Dict[str, str]:
    """与 assemble 一致：`assembly.modules[].id` → 中文简称 `abbrev`。"""
    asm = load_assembly_config()
    out: Dict[str, str] = {}
    for m in asm.get('modules') or []:
        if not isinstance(m, dict):
            continue
        mid = m.get('id')
        if not mid:
            continue
        ab = (m.get('abbrev') or '').strip() or str(mid)
        out[str(mid)] = ab
    return out


def _footer_module_paragraphs(blocks: Dict[str, Any], abbrev_by_id: Dict[str, str]) -> List[str]:
    """
    按 `blocks.footer` 顺序拆成多段，每段首行带中文模块名（与早报「今日速览」一致：`abbrev：首行`）。
    """
    footer = (blocks or {}).get('footer') or {}
    paragraphs: List[str] = []
    for key in _FOOTER_KEYS:
        val = footer.get(key)
        if val is None or not str(val).strip():
            continue
        label = abbrev_by_id.get(key) or key
        raw_lines = [ln.strip() for ln in str(val).splitlines() if ln.strip()]
        if not raw_lines:
            continue
        head = f'{label}：{raw_lines[0]}'
        if len(raw_lines) == 1:
            paragraphs.append(head)
        else:
            paragraphs.append(head + '\n' + '\n'.join(raw_lines[1:]))
    return paragraphs


def build_payload(date_str: str, doc_url: str, summary_path: str) -> Dict[str, Any]:
    with open(summary_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    blocks = data.get('blocks') or {}
    abbrev_by_id = _module_abbrev_by_id()
    paras = _footer_module_paragraphs(blocks, abbrev_by_id)

    elements: List[Dict[str, Any]] = []
    if not paras:
        elements.append(
            {
                'tag': 'div',
                'text': {
                    'tag': 'lark_md',
                    'content': '（blocks.footer 无有效段落）',
                },
            }
        )
    else:
        for p in paras:
            elements.append(
                {
                    'tag': 'div',
                    'text': {
                        'tag': 'lark_md',
                        'content': p,
                    },
                }
            )
    elements.append(
        {
            'tag': 'action',
            'actions': [
                {
                    'tag': 'button',
                    'text': {
                        'tag': 'plain_text',
                        'content': '立即查看',
                    },
                    'type': 'primary',
                    'url': doc_url,
                }
            ],
        }
    )

    return {
        'msg_type': 'interactive',
        'card': {
            'header': {
                'title': {
                    'tag': 'plain_text',
                    'content': f'早报：AI 前沿早报（{date_str}）',
                },
                'template': 'blue',
            },
            'elements': elements,
        },
    }


def _post_webhook(url: str, payload: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        headers={'Content-Type': 'application/json; charset=utf-8'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode('utf-8')
    return json.loads(raw) if raw.strip() else {}


def main() -> int:
    parser = argparse.ArgumentParser(
        description='飞书自定义机器人：interactive 卡片推送早报链接与 summary footer',
    )
    parser.add_argument('--date', required=True, help='YYYY-MM-DD，对应 output/<DATE>/')
    parser.add_argument('--doc-url', required=True, dest='doc_url', help='§2 得到的飞书文档 URL')
    parser.add_argument(
        '--webhook',
        default=os.environ.get('FEISHU_BOT_WEBHOOK', ''),
        help='Webhook；默认环境变量 FEISHU_BOT_WEBHOOK',
    )
    parser.add_argument(
        '--summary-json',
        dest='summary_json',
        default=None,
        help='summary.json 路径；默认 output/<date>/summary.json',
    )
    args = parser.parse_args()

    webhook = (args.webhook or '').strip()
    if not webhook:
        print('error: 请传入 --webhook 或设置环境变量 FEISHU_BOT_WEBHOOK', file=sys.stderr)
        return 1

    paths = default_day_paths(args.date)
    summary_path = args.summary_json or paths['summary']
    if not os.path.isfile(summary_path):
        print(f'error: 找不到 {summary_path}', file=sys.stderr)
        return 1

    payload = build_payload(args.date, args.doc_url.strip(), summary_path)
    n = len(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
    if n > _MAX_BODY_BYTES:
        print(f'error: 请求体约 {n} 字节，超过 20KB', file=sys.stderr)
        return 1

    try:
        out = _post_webhook(webhook, payload)
    except urllib.error.HTTPError as e:
        print(f'error: HTTP {e.code}', file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f'error: {e.reason}', file=sys.stderr)
        return 1

    if out.get('code') != 0:
        print(f'error: 飞书响应 {out}', file=sys.stderr)
        return 1
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
