#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
base_config.py — 工程根路径、kit 资源路径、`config.json` 位置，以及 `engineering.json` 的加载器。

- 路径：`KIT_DIR`、`PROMPTS_DIR` / `TEMPLATES_DIR`、`CONFIG_*`、`output/{date}` 默认文件名。
- 配置：`load_assembly_config`、`load_sources_config`、`load_public_feeds_config`、`load_dedup_config`、`load_modules_window_hours`。

业务脚本从此模块取路径与工程配置，勿写死目录名或重复解析 JSON。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROJECT_ROOT = _PROJECT_ROOT

KIT_DIR = os.path.join(_PROJECT_ROOT, 'kit')
_CONTENT_DIR = os.path.join(KIT_DIR, 'prompts&templates')
ENGINEERING_JSON = os.path.join(KIT_DIR, 'engineering.json')
PROMPTS_DIR = _CONTENT_DIR
TEMPLATES_DIR = _CONTENT_DIR
CONFIG_JSON = os.path.join(KIT_DIR, 'config.json')
CONFIG_EXAMPLE_JSON = os.path.join(KIT_DIR, 'config.example.json')

FN_INGESTED = 'ingested.jsonl'
FN_SUMMARY = 'summary.json'
FN_AGENDA = 'agenda.md'


def output_dir_for_date(date_str: str) -> str:
    return os.path.join(PROJECT_ROOT, 'output', date_str)


def default_day_paths(date_str: str) -> dict:
    """单日默认输入输出路径。"""
    d = output_dir_for_date(date_str)
    return {
        'dir': d,
        'ingested': os.path.join(d, FN_INGESTED),
        'summary': os.path.join(d, FN_SUMMARY),
        'agenda': os.path.join(d, FN_AGENDA),
    }


# ----- kit/engineering.json -----


def _load_engineering() -> Dict[str, Any]:
    if not os.path.isfile(ENGINEERING_JSON):
        raise FileNotFoundError(
            f'缺少工程配置: {ENGINEERING_JSON}（见 kit/engineering.json）'
        )
    with open(ENGINEERING_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_dedup_config() -> Dict[str, Any]:
    """去重阈值与 n-gram；缺键时使用内置默认。扩展键（如 recent_summary_*）从 engineering.json 合并。"""
    defaults = {
        'title_similarity_threshold': 0.85,
        'word_ngram_n': 3,
        'char_ngram_n': 3,
        'recent_summary_enabled': True,
        'recent_summary_days': 7,
        'recent_summary_title_threshold': None,
        'recent_summary_text_threshold': 0.38,
    }
    data = _load_engineering().get('dedup') or {}
    cfg = defaults.copy()
    cfg.update(data)
    if cfg.get('recent_summary_title_threshold') is None:
        cfg['recent_summary_title_threshold'] = float(cfg['title_similarity_threshold'])
    return cfg


def load_assembly_config() -> Dict[str, Any]:
    """组装与摘要共用：模块列表、header_coverage、time_window、摘要条数字段等。"""
    eng = _load_engineering()
    asm = eng.get('assembly')
    if not isinstance(asm, dict):
        raise ValueError('engineering.json 缺少 assembly 对象')
    return asm


def load_sources_config() -> Dict[str, Any]:
    """Tier 来源、排除域名、URL 模式。"""
    eng = _load_engineering()
    src = eng.get('sources')
    if not isinstance(src, dict):
        raise ValueError('engineering.json 缺少 sources 对象')
    return src


def load_public_feeds_config() -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """RSS 拉取 settings + feeds 列表。"""
    data = _load_engineering().get('public_feeds') or {}
    settings = data.get('settings', {})
    feeds = data.get('feeds', [])
    if not isinstance(feeds, list):
        feeds = []
    return settings, feeds


def load_modules_window_hours() -> int:
    """抓取时间窗（小时），来自 assembly.time_window_hours。"""
    return int(load_assembly_config().get('time_window_hours', 72))
