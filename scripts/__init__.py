# -*- coding: utf-8 -*-
"""
`scripts` 包 — 每日 AI 前沿早报管线。

**实现位置不变**：路径与 `engineering.json` 仍在 `base_config.py`；步骤名与 `parse_steps` 仍在
`pipeline.py`。本文件仅汇总对外常用符号，支持：

    from scripts import ORDER, default_day_paths, load_assembly_config

业务脚本可继续写 `from scripts.base_config import ...`，与再导出并存。
"""

from __future__ import annotations

from .base_config import (
    CONFIG_EXAMPLE_JSON,
    CONFIG_JSON,
    ENGINEERING_JSON,
    FN_AGENDA,
    FN_INGESTED,
    FN_SUMMARY,
    KIT_DIR,
    PROJECT_ROOT,
    PROMPTS_DIR,
    TEMPLATES_DIR,
    default_day_paths,
    load_assembly_config,
    load_dedup_config,
    load_modules_window_hours,
    load_public_feeds_config,
    load_sources_config,
    output_dir_for_date,
)
from .pipeline import ORDER, canonical_step, parse_steps

__all__ = [
    'CONFIG_EXAMPLE_JSON',
    'CONFIG_JSON',
    'ENGINEERING_JSON',
    'FN_AGENDA',
    'FN_INGESTED',
    'FN_SUMMARY',
    'KIT_DIR',
    'ORDER',
    'PROJECT_ROOT',
    'PROMPTS_DIR',
    'TEMPLATES_DIR',
    'canonical_step',
    'default_day_paths',
    'load_assembly_config',
    'load_dedup_config',
    'load_modules_window_hours',
    'load_public_feeds_config',
    'load_sources_config',
    'output_dir_for_date',
    'parse_steps',
]
