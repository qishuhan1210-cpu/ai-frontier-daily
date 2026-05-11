#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils/base.py — 模块基类和通用工具

为 ingest/summarize/assemble 提供公共基础设施
"""

from __future__ import annotations

import html
import json
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseModule(ABC):
    """流水线模块基类"""

    def __init__(self, date_str: str, name: str):
        self.date_str = date_str
        self.name = name
        self._config_loaded = False

    @abstractmethod
    def run(self, *args, **kwargs) -> Dict[str, Any]:
        """执行模块主逻辑，子类必须实现"""
        raise NotImplementedError

    def _ensure_config(self):
        """确保配置已加载（子类可重写）"""
        pass

    @staticmethod
    def load_jsonl(path: str) -> List[dict]:
        """加载 JSONL 文件"""
        items = []
        if not os.path.exists(path):
            return items
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return items

    @staticmethod
    def save_jsonl(path: str, items: List[dict]):
        """保存 JSONL 文件"""
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + '\n')

    @staticmethod
    def load_json(path: str) -> Optional[dict]:
        """加载 JSON 文件"""
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def save_json(path: str, data: dict):
        """保存 JSON 文件"""
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def strip_html(raw: Optional[str], limit: int = 4000) -> str:
        """去除 HTML 标签"""
        if not raw:
            return ''
        text = re.sub(r'<[^>]+>', ' ', raw)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:limit]

    @staticmethod
    def clip_text(text: str, max_chars: int, suffix: str = '…') -> str:
        """截断文本"""
        t = re.sub(r'\s+', ' ', (text or '').strip())
        if len(t) <= max_chars:
            return t
        return t[:max_chars - len(suffix)] + suffix

    @staticmethod
    def is_placeholder(text: str, patterns: tuple = ('点击查看原文', 'click to read', 'read more')) -> bool:
        """判断是否为占位符文本"""
        if not text:
            return True
        t = text.strip()
        if len(t) < 6:
            return True
        low = t.lower()
        for p in patterns:
            if p in t or p.lower() in low:
                return True
        return False

    @staticmethod
    def similarity_tokens(text: str, word_n: int = 3, char_n: int = 3) -> set:
        """生成文本的相似度 token（n-gram）"""
        text = (text or '').lower().strip()
        if not text:
            return set()
        tokens = []
        words = text.split()
        if word_n >= 1 and len(words) >= word_n:
            for i in range(len(words) - word_n + 1):
                tokens.append(' '.join(words[i:i + word_n]))
        if char_n >= 1 and len(text) >= char_n:
            for i in range(len(text) - char_n + 1):
                tokens.append(text[i:i + char_n])
        return set(tokens)

    @staticmethod
    def jaccard_similarity(set_a: set, set_b: set) -> float:
        """计算 Jaccard 相似度"""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0
