#!/usr/bin/env python3
"""模板与提示词加载器"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class TemplateRenderer:
    """模板渲染器 - 基础模板加载和渲染"""

    @staticmethod
    def load_file(path: Path) -> str | None:
        """读取模板文件内容"""
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    @staticmethod
    def render_simple(template: str, context: dict[str, Any]) -> str:
        """简单模板渲染（无 jinja2 时回退）"""
        result = template
        for key, value in context.items():
            if isinstance(value, str):
                result = result.replace(f"{{{{ {key} }}}}", value)
        return result

    def render(self, path: Path, context: dict[str, Any]) -> str | None:
        """渲染模板"""
        template = self.load_file(path)
        if not template:
            return None

        try:
            from jinja2 import Template
            return Template(template).render(**context)
        except ImportError:
            return self.render_simple(template, context)


class PromptLoader(TemplateRenderer):
    """提示词加载器 - 扩展模板渲染，支持 frontmatter 解析"""

    @staticmethod
    def parse_frontmatter(content: str) -> dict[str, str]:
        """解析 frontmatter 格式"""
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

    def render_and_parse(self, path: Path, context: dict[str, Any]) -> tuple[str, str]:
        """渲染模板并解析 frontmatter"""
        rendered = self.render(path, context)
        parts = self.parse_frontmatter(rendered or '')
        return parts.get('system', ''), parts.get('user', '')