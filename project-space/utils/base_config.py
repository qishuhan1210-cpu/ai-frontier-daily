#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
base_config.py — 工程根路径、配置加载器

- 路径：PROJECT_ROOT、PROMPTS_DIR、TEMPLATES_DIR、CONFIG_JSON、output/{date} 默认文件名
- 配置：从 config.json 读取非敏感配置，从 .env 读取敏感信息（API Key、Webhook 等）

业务脚本从此模块取路径与工程配置，勿写死目录名或重复解析 JSON。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    # 加载 config/.env（project-space 的兄弟目录 config 下）
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ENV_PATH = os.path.join(os.path.dirname(_PROJECT_ROOT), 'config', '.env')
    if os.path.isfile(_ENV_PATH):
        load_dotenv(_ENV_PATH)
except ImportError:
    pass  # python-dotenv 未安装时，依赖系统环境变量

# 工程根目录（project-space/）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROJECT_ROOT = _PROJECT_ROOT

# 各资源目录
PROMPTS_DIR = os.path.join(_PROJECT_ROOT, 'prompts')
TEMPLATES_DIR = os.path.join(_PROJECT_ROOT, 'templates')
CONFIG_JSON = os.path.join(_PROJECT_ROOT, 'config', 'config.json')

# 输出文件名
FN_INGESTED = 'ingested.jsonl'
FN_SUMMARY = 'summary.json'
FN_AGENDA = 'agenda.md'


def output_dir_for_date(date_str: str) -> str:
    """获取指定日期的输出目录路径"""
    return os.path.join(PROJECT_ROOT, 'output', date_str)


def default_day_paths(date_str: str) -> dict:
    """单日默认输入输出路径"""
    d = output_dir_for_date(date_str)
    return {
        'dir': d,
        'ingested': os.path.join(d, FN_INGESTED),
        'summary': os.path.join(d, FN_SUMMARY),
        'agenda': os.path.join(d, FN_AGENDA),
    }


# ----- 配置加载 -----


def _load_config() -> Dict[str, Any]:
    """加载主配置文件"""
    if not os.path.isfile(CONFIG_JSON):
        raise FileNotFoundError(f'缺少配置文件: {CONFIG_JSON}')
    with open(CONFIG_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_llm_config() -> Dict[str, str]:
    """加载 LLM 配置

    所有 LLM 配置均从 .env 环境变量读取
    """
    return {
        'api_key': os.getenv('LLM_API_KEY', ''),
        'base_url': os.getenv('LLM_BASE_URL', ''),
        'model_name': os.getenv('LLM_MODEL_NAME', ''),
    }


def load_output_config() -> Dict[str, Any]:
    """加载输出配置"""
    cfg = _load_config()
    return cfg.get('output', {})


def load_dedup_config() -> Dict[str, Any]:
    """去重阈值与 n-gram；缺键时使用内置默认"""
    defaults = {
        'title_similarity_threshold': 0.85,
        'word_ngram_n': 3,
        'char_ngram_n': 3,
        'recent_summary_enabled': True,
        'recent_summary_days': 7,
        'recent_summary_title_threshold': None,
        'recent_summary_text_threshold': 0.38,
    }
    data = _load_config().get('dedup') or {}
    cfg = defaults.copy()
    cfg.update(data)
    if cfg.get('recent_summary_title_threshold') is None:
        cfg['recent_summary_title_threshold'] = float(cfg['title_similarity_threshold'])
    return cfg


def load_assembly_config() -> Dict[str, Any]:
    """组装与摘要共用：模块列表、header_coverage、time_window、摘要条数字段等"""
    cfg = _load_config()
    asm = cfg.get('assembly')
    if not isinstance(asm, dict):
        raise ValueError('config.json 缺少 assembly 对象')
    return asm


def load_sources_config() -> Dict[str, Any]:
    """Tier 来源、排除域名、URL 模式"""
    cfg = _load_config()
    src = cfg.get('sources')
    if not isinstance(src, dict):
        raise ValueError('config.json 缺少 sources 对象')
    return src


def load_public_feeds_config() -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """RSS 拉取 settings + feeds 列表"""
    data = _load_config().get('public_feeds') or {}
    settings = data.get('settings', {})
    feeds = data.get('feeds', [])
    if not isinstance(feeds, list):
        feeds = []
    return settings, feeds


def load_modules_window_hours() -> int:
    """抓取时间窗（小时），来自 assembly.time_window_hours"""
    return int(load_assembly_config().get('time_window_hours', 72))


def load_env_config() -> Dict[str, str]:
    """加载环境变量配置（敏感信息）

    Returns:
        dict: 包含 FEISHU_BOT_WEBHOOK
        注意：飞书知识库配置（space_id、parent_node_token）由大模型根据对话上下文自行判断，
        不从此处读取。详见 post-runbook.md 发布流程。
    """
    return {
        'feishu_bot_webhook': os.getenv('FEISHU_BOT_WEBHOOK', ''),
    }
