#!/usr/bin/env python3
"""模板与提示词加载器"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from utils.base_config import ProtocolLayerConfig


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
        """解析 frontmatter 格式

        新规范格式：
            xxxx: $$$$|
              内容
            xxxx: |$$$$
        """
        parts = {}
        for match in re.finditer(r'^(\w+):\s+\$\$\$\$\|(.*?)\n(\w+):\s+\|\$\$\$\$$', content, re.DOTALL | re.MULTILINE):
            key, value, end_key = match.groups()
            if key == end_key:
                lines = [line[2:] if line.startswith('  ') else line.lstrip() for line in value.split('\n')]
                parts[key] = '\n'.join(lines).strip()

        return parts

    def render_and_parse(self, path: Path, context: dict[str, Any]) -> tuple[str, str]:
        """渲染模板并解析 frontmatter"""
        rendered = self.render(path, context)
        parts = self.parse_frontmatter(rendered or '')
        return parts.get('system', ''), parts.get('user', '')

    def load_with_config(
        self,
        template_path: Path,
        config: ProtocolLayerConfig,
        **kwargs: Any,
    ) -> tuple[str, str]:
        """从 ProtocolLayerConfig 提取公共变量后渲染并解析提示词模板

        Args:
            template_path: 提示词模板路径（.md.j2）
            config: ProtocolLayerConfig 实例
            **kwargs: 额外运行时变量（可覆盖公共变量，如 date_str / news_json）

        Returns:
            (system_prompt, user_prompt) 元组
        """
        rules = config.classification.main_sections
        vertical_tags = config.vertical_tags_whitelist
        general_tags = config.general_tags_whitelist
        template_vars: dict[str, Any] = {
            'coverage': ' · '.join(getattr(m, 'name', '') for m in rules),
            'ids_str': ', '.join(getattr(m, 'id', '') for m in rules),
            'module_names': [getattr(m, 'name', '') for m in rules],
            'vertical_tags': '、'.join(vertical_tags),
            'general_tags': '、'.join(general_tags),
            'classification_rules': rules,
            **kwargs,
        }
        return self.render_and_parse(template_path, template_vars)
