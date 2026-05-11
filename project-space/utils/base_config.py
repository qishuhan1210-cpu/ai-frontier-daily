#!/usr/bin/env python3
"""base_config.py — 路径常量与配置加载"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

# === 路径常量 ===
_PROJECT_SPACE = Path(__file__).resolve().parent.parent
PROJECT_ROOT = _PROJECT_SPACE.parent

PROMPTS_DIR = _PROJECT_SPACE / 'prompts'
CONFIG_DIR = _PROJECT_SPACE / 'config'
SECRETS_JSON = PROJECT_ROOT / 'config' / 'secrets.json'
CONFIG_JSON = CONFIG_DIR / 'config.json'

# 输出文件名
FN_RAW_FETCHED = 'raw_fetched.jsonl'
FN_INGESTED = 'ingested.jsonl'
FN_FILTERED_RANKED = 'filtered_ranked.json'
FN_SUMMARY = 'summary.json'
FN_BRIEFING = 'briefing.md'


# === 路径函数 ===
def output_dir_for_date(date_str: str) -> Path:
    return PROJECT_ROOT / 'output' / date_str


def default_day_paths(date_str: str) -> dict:
    d = output_dir_for_date(date_str)
    return {
        'dir': d,
        'ingested': d / FN_INGESTED,
        'filtered': d / FN_FILTERED_RANKED,
        'summary': d / FN_SUMMARY,
        'briefing': d / FN_BRIEFING,
    }


# === 配置加载 ===
def _load_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f'缺少文件: {path}')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_secrets() -> dict:
    """加载敏感配置（API Key等）"""
    return _load_json(SECRETS_JSON)


def load_llm_config() -> dict:
    """加载 LLM 配置"""
    return load_secrets().get('llm', {})


def load_feishu_config() -> dict:
    """加载飞书配置"""
    return load_secrets().get('feishu', {})


def load_config() -> dict:
    """加载业务配置（RSS源、模块等）"""
    return _load_json(CONFIG_JSON)


def load_assembly_config() -> dict:
    """加载组装配置"""
    cfg = load_config()
    asm = cfg.get('assembly')
    if not isinstance(asm, dict):
        raise ValueError('config.json 缺少 assembly 对象')
    return asm


def load_sources_config() -> dict:
    """加载来源配置"""
    cfg = load_config()
    src = cfg.get('sources')
    if not isinstance(src, dict):
        raise ValueError('config.json 缺少 sources 对象')
    return src


def load_public_feeds_config() -> Tuple[Dict, List]:
    """加载 RSS 配置"""
    data = load_config().get('public_feeds') or {}
    return data.get('settings', {}), data.get('feeds', [])


def load_dedup_config() -> dict:
    """加载去重配置（带默认值）"""
    defaults = {
        'title_similarity_threshold': 0.85,
        'word_ngram_n': 3,
        'char_ngram_n': 3,
        'recent_summary_enabled': True,
        'recent_summary_days': 7,
        'recent_summary_text_threshold': 0.38,
        'persistent_days_threshold': 4,  # 持续热点阈值：出现 >=4 天则保留
    }
    cfg = load_config().get('dedup') or {}
    defaults.update(cfg)
    if defaults.get('recent_summary_title_threshold') is None:
        defaults['recent_summary_title_threshold'] = defaults['title_similarity_threshold']
    return defaults


def load_modules_window_hours() -> int:
    """加载抓取时间窗（小时）"""
    return int(load_assembly_config().get('time_window_hours', 72))
