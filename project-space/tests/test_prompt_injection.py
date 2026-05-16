#!/usr/bin/env python3
"""变量注入一致性测试"""

import sys
from pathlib import Path
from types import SimpleNamespace

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from utils.base_config import ConfigDict, ProtocolLayerConfig
from utils.prompt_loader import PromptLoader


def _make_mock_protocol_config() -> ProtocolLayerConfig:
    data = {
        'protocol': {
            'summarize': {
                'fields': [
                    {'name': 'headline', 'type': 'string', 'desc': '标题'},
                    {'name': 'plain_explain', 'type': 'string', 'desc': '白话解释'},
                    {'name': 'impact_1', 'type': 'string', 'desc': '影响一'},
                    {'name': 'impact_2', 'type': 'string', 'desc': '影响二'},
                    {'name': 'digest_for_outline', 'type': 'string', 'desc': '概要'},
                    {'name': 'main_section', 'type': 'string', 'desc': '主板块'},
                    {'name': 'sub_section', 'type': 'string', 'desc': '子栏目'},
                    {'name': 'vertical_tags', 'type': 'string[]', 'desc': '垂类标签'},
                    {'name': 'general_tags', 'type': 'string[]', 'desc': '通用标签'},
                    {'name': 'hot', 'type': 'string', 'desc': '热度'},
                ]
            }
        },
        'classification': {
            'main_sections': [
                {'id': 'model', 'name': '大模型', 'description': '基础模型技术', 'examples': 'GPT'},
                {'id': 'hardware', 'name': 'AI硬件', 'description': 'AI芯片与算力', 'examples': 'GPU'},
                {'id': 'application', 'name': '行业应用', 'description': 'AI落地应用', 'examples': '医疗AI'},
                {'id': 'investment', 'name': '投融资', 'description': '资本市场', 'examples': '融资'},
                {'id': 'policy', 'name': '政策监管', 'description': '政策法规', 'examples': 'AI治理'},
            ],
            'tags': {
                'vertical_tags_whitelist': ['AI医疗', '辅助诊断', 'AIGC', '智能体'],
                'general_tags_whitelist': ['投融资', '技术突破', '行业趋势', '新品发布'],
            }
        }
    }
    return ProtocolLayerConfig(data)


class TestProtocolLayerConfig:
    """ProtocolLayerConfig 类测试"""

    def test_classification_rules_returns_list(self):
        config = _make_mock_protocol_config()
        rules = config.classification.main_sections
        assert isinstance(rules, list)
        assert len(rules) == 5
        assert rules[0].name == '大模型'

    def test_vertical_tags_whitelist(self):
        config = _make_mock_protocol_config()
        assert len(config.vertical_tags_whitelist) > 0
        assert 'AI医疗' in config.vertical_tags_whitelist

    def test_general_tags_whitelist(self):
        config = _make_mock_protocol_config()
        assert len(config.general_tags_whitelist) > 0
        assert '投融资' in config.general_tags_whitelist


class TestPromptLoaderLoadWithConfig:

    def test_renders_coverage(self, tmp_path):
        template = tmp_path / 'filter_ranker.md.j2'
        template.write_text(
            'system: $$$$|\n  sys\nsystem: |$$$$\n\nuser: $$$$|\n  coverage={{ coverage }}\nuser: |$$$$\n',
            encoding='utf-8'
        )
        config = _make_mock_protocol_config()
        _, user = PromptLoader().load_with_config(template, config, date_str='2026-05-15', news_json='[]')
        assert '大模型' in user

    def test_renders_ids_str(self, tmp_path):
        template = tmp_path / 'summarizer.md.j2'
        template.write_text(
            'system: $$$$|\n  sys\nsystem: |$$$$\n\nuser: $$$$|\n  ids={{ ids_str }}\nuser: |$$$$\n',
            encoding='utf-8'
        )
        config = _make_mock_protocol_config()
        _, user = PromptLoader().load_with_config(template, config, date_str='2026-05-15', news_json='[]')
        assert 'model' in user
        assert 'policy' in user

    def test_module_names(self, tmp_path):
        template = tmp_path / 'test.md.j2'
        template.write_text(
            'system: $$$$|\n  sys\nsystem: |$$$$\n\nuser: $$$$|\n  modules={{ module_names|join(", ") }}\nuser: |$$$$\n',
            encoding='utf-8'
        )
        config = _make_mock_protocol_config()
        _, user = PromptLoader().load_with_config(template, config, date_str='2026-05-15', news_json='[]')
        assert '大模型' in user
        assert 'AI硬件' in user

    def test_kwargs_override_base_vars(self, tmp_path):
        template = tmp_path / 'test.md.j2'
        template.write_text(
            'system: $$$$|\n  sys\nsystem: |$$$$\n\nuser: $$$$|\n  cov={{ coverage }}\nuser: |$$$$\n',
            encoding='utf-8'
        )
        config = _make_mock_protocol_config()
        _, user = PromptLoader().load_with_config(template, config, coverage='自定义覆盖范围')
        assert '自定义覆盖范围' in user

    def test_vertical_tags_injected(self, tmp_path):
        template = tmp_path / 'test.md.j2'
        template.write_text(
            'system: $$$$|\n  sys\nsystem: |$$$$\n\nuser: $$$$|\n  vtags={{ vertical_tags }}\nuser: |$$$$\n',
            encoding='utf-8'
        )
        config = _make_mock_protocol_config()
        _, user = PromptLoader().load_with_config(template, config)
        assert 'AI医疗' in user
        assert '辅助诊断' in user

    def test_general_tags_injected(self, tmp_path):
        template = tmp_path / 'test.md.j2'
        template.write_text(
            'system: $$$$|\n  sys\nsystem: |$$$$\n\nuser: $$$$|\n  gtags={{ general_tags }}\nuser: |$$$$\n',
            encoding='utf-8'
        )
        config = _make_mock_protocol_config()
        _, user = PromptLoader().load_with_config(template, config)
        assert '投融资' in user
        assert '技术突破' in user
