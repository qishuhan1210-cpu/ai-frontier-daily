#!/usr/bin/env python3
"""变量注入一致性测试"""

import sys
from pathlib import Path
from types import SimpleNamespace

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from utils.base_config import TemplateConfig, ConfigDict
from utils.prompt_loader import PromptLoader


def _make_mock_config() -> SimpleNamespace:
    modules = [
        ConfigDict({'id': 'model', 'name': '大模型'}),
        ConfigDict({'id': 'hardware', 'name': 'AI硬件'}),
        ConfigDict({'id': 'application', 'name': '行业应用'}),
        ConfigDict({'id': 'investment', 'name': '投融资'}),
        ConfigDict({'id': 'policy', 'name': '政策监管'}),
    ]
    template = TemplateConfig(
        assembly_modules=modules,
        classification_data={
            'main_sections': [
                {'id': 'core_tech', 'name': '大模型与核心技术', 'description': '基础模型', 'examples': 'GPT'},
            ]
        },
        tags_data={
            'tag_options': [
                {'name': '融资投资', 'description': '资本动向'},
                {'name': '产品发布', 'description': '新产品/服务上市'},
                {'name': '技术突破', 'description': '核心技术进展'},
                {'name': '政策监管', 'description': '政策法规影响'},
                {'name': '企业动态', 'description': '公司战略与组织'},
                {'name': '市场格局', 'description': '行业竞争态势'},
            ]
        },
    )
    return SimpleNamespace(template=template)


class TestTemplateConfig:

    def test_coverage_matches_module_names(self):
        config = _make_mock_config()
        for name in ['大模型', 'AI硬件', '行业应用', '投融资', '政策监管']:
            assert name in config.template.coverage, f"coverage 中缺少模块名: {name}"

    def test_ids_str_matches_modules(self):
        config = _make_mock_config()
        for mid in ['model', 'hardware', 'application', 'investment', 'policy']:
            assert mid in config.template.ids_str, f"ids_str 中缺少模块 ID: {mid}"

    def test_module_names_list(self):
        config = _make_mock_config()
        assert config.template.module_names == ['大模型', 'AI硬件', '行业应用', '投融资', '政策监管']

    def test_tag_options_str_contains_all_tags(self):
        config = _make_mock_config()
        for tag in ['融资投资', '产品发布', '技术突破', '政策监管', '企业动态', '市场格局']:
            assert tag in config.template.tag_options, f"tag_options 中缺少: {tag}"

    def test_tag_options_default_separator(self):
        t = TemplateConfig([], {}, {'tag_options': [{'name': 'A'}, {'name': 'B'}]})
        assert t.tag_options == 'A、B'

    def test_tag_options_empty(self):
        t = TemplateConfig([], {}, {})
        assert t.tag_options == ''

    def test_classification_rules_returns_table(self):
        config = _make_mock_config()
        rules = config.template.classification_rules
        assert '大模型与核心技术' in rules
        assert '|' in rules

    def test_classification_rules_empty(self):
        t = TemplateConfig([], {}, {})
        assert t.classification_rules == ''


class TestPromptLoaderLoadWithConfig:

    def test_renders_coverage(self, tmp_path):
        template = tmp_path / 'filter_ranker.md.j2'
        template.write_text(
            '---\nsystem: |\n  sys\nuser: |\n  coverage={{ coverage }}\n\n---\n',
            encoding='utf-8'
        )
        config = _make_mock_config()
        _, user = PromptLoader().load_with_config(template, config, date_str='2026-05-15', news_json='[]')
        assert config.template.coverage in user

    def test_renders_ids_str(self, tmp_path):
        template = tmp_path / 'summarizer.md.j2'
        template.write_text(
            '---\nsystem: |\n  sys\nuser: |\n  ids={{ ids_str }}\n\n---\n',
            encoding='utf-8'
        )
        config = _make_mock_config()
        _, user = PromptLoader().load_with_config(template, config, date_str='2026-05-15', news_json='[]')
        assert 'model' in user
        assert 'policy' in user

    def test_kwargs_override_base_vars(self, tmp_path):
        template = tmp_path / 'test.md.j2'
        template.write_text(
            '---\nsystem: |\n  sys\nuser: |\n  cov={{ coverage }}\n\n---\n',
            encoding='utf-8'
        )
        config = _make_mock_config()
        _, user = PromptLoader().load_with_config(template, config, coverage='自定义覆盖范围')
        assert '自定义覆盖范围' in user

    def test_tag_options_injected(self, tmp_path):
        template = tmp_path / 'test.md.j2'
        template.write_text(
            '---\nsystem: |\n  sys\nuser: |\n  tags={{ tag_options }}\n\n---\n',
            encoding='utf-8'
        )
        config = _make_mock_config()
        _, user = PromptLoader().load_with_config(template, config)
        assert '融资投资' in user
        assert '市场格局' in user
