#!/usr/bin/env python3
"""提示词加载器 - 基于 Jinja2 模板渲染"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class PromptLoader:
    """提示词加载器 - 通用模板渲染"""

    DEFAULT_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

    def __init__(self, prompt_dir: Path | None = None):
        """
        Args:
            prompt_dir: 模板目录，默认 project-space/prompts/
        """
        self.prompt_dir = prompt_dir or self.DEFAULT_PROMPT_DIR

    def load_file(self, template_name: str) -> str | None:
        """加载模板文件内容"""
        path = self.prompt_dir / template_name
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    @staticmethod
    def parse_frontmatter(content: str) -> dict[str, str]:
        """
        解析 frontmatter 格式
        格式: ---\nkey: |\n  value...\n---
        """
        parts = {}
        match = re.search(r'^---\s*\n(.*?)\n---\s*$', content, re.DOTALL | re.MULTILINE)
        if not match:
            return parts

        front = match.group(1)
        for block in re.finditer(r'^(\w+):\s*\|?\s*\n((?:  .*\n|\n)+)', front, re.MULTILINE):
            key, value = block.groups()
            lines = [line[2:] if line.startswith('  ') else line for line in value.rstrip().split('\n')]
            parts[key] = '\n'.join(lines).strip()

        return parts

    @staticmethod
    def render_simple(template: str, context: dict[str, Any]) -> str:
        """简单模板渲染（无 jinja2 时回退）"""
        result = template
        for key, value in context.items():
            if isinstance(value, str):
                result = result.replace(f"{{{{ {key} }}}}", value)
        return result

    def render(self, template_name: str, context: dict[str, Any]) -> str | None:
        """
        渲染模板

        Args:
            template_name: 模板文件名
            context: 模板变量

        Returns:
            渲染后的内容，或 None
        """
        template = self.load_file(template_name)
        if not template:
            return None

        # 尝试 jinja2 渲染
        try:
            from jinja2 import Template
            return Template(template).render(**context)
        except ImportError:
            return self.render_simple(template, context)


__all__ = ["PromptLoader"]
