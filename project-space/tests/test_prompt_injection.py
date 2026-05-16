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
    template = TemplateConfig(
        classification_data={
            'main_sections': [
                {'id': 'model', 'name': '大模型', 'description': '基础模型技术', 'examples': 'GPT'},
                {'id': 'hardware', 'name': 'AI硬件', 'description': 'AI芯片与算力', 'examples': 'GPU'},
                {'id': 'application', 'name': '行业应用', 'description': 'AI落地应用', 'examples': '医疗AI'},
                {'id': 'investment', 'name': '投融资', 'description': '资本市场', 'examples': '融资'},
                {'id': 'policy', 'name': '政策监管', 'description': '政策法规', 'examples': 'AI治理'},
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

    def test_classification_rules_returns_list(self):
        config = _make_mock_config()
        rules = config.template.classification_rules
        assert isinstance(rules, list)
        assert len(rules) == 5
        assert rules[0].name == '大模型'

    def test_classification_rules_empty(self):
        t = TemplateConfig({}, {})
        assert t.classification_rules == []


class TestPromptLoaderLoadWithConfig:

    def test_renders_coverage(self, tmp_path):
        template = tmp_path / 'filter_ranker.md.j2'
        template.write_text(
            'system: $$$$|\n  sys\nsystem: |$$$$\n\nuser: $$$$|\n  coverage={{ coverage }}\nuser: |$$$$\n',
            encoding='utf-8'
        )
        config = _make_mock_config()
        _, user = PromptLoader().load_with_config(template, config, date_str='2026-05-15', news_json='[]')
        assert '大模型' in user

    def test_renders_ids_str(self, tmp_path):
        template = tmp_path / 'summarizer.md.j2'
        template.write_text(
            'system: $$$$|\n  sys\nsystem: |$$$$\n\nuser: $$$$|\n  ids={{ ids_str }}\nuser: |$$$$\n',
            encoding='utf-8'
        )
        config = _make_mock_config()
        _, user = PromptLoader().load_with_config(template, config, date_str='2026-05-15', news_json='[]')
        assert 'model' in user
        assert 'policy' in user

    def test_kwargs_override_base_vars(self, tmp_path):
        template = tmp_path / 'test.md.j2'
        template.write_text(
            'system: $$$$|\n  sys\nsystem: |$$$$\n\nuser: $$$$|\n  cov={{ coverage }}\nuser: |$$$$\n',
            encoding='utf-8'
        )
        config = _make_mock_config()
        _, user = PromptLoader().load_with_config(template, config, coverage='自定义覆盖范围')
        assert '自定义覆盖范围' in user

    def test_tag_options_injected(self, tmp_path):
        template = tmp_path / 'test.md.j2'
        template.write_text(
            'system: $$$$|\n  sys\nsystem: |$$$$\n\nuser: $$$$|\n  tags={{ tag_options }}\nuser: |$$$$\n',
            encoding='utf-8'
        )
        config = _make_mock_config()
        _, user = PromptLoader().load_with_config(template, config)
        assert '融资投资' in user
        assert '市场格局' in user
