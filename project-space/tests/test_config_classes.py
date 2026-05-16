#!/usr/bin/env python3
"""配置类单元测试"""

import pytest
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / 'project-space'))

from utils.base_config import AppConfig, ConfigDict, PROMPTS_DIR


class TestAppConfig:
    """AppConfig 类测试"""

    def test_path_constants(self):
        assert PROMPTS_DIR.exists(), f"提示词目录不存在: {PROMPTS_DIR}"

    def test_config_loading(self):
        config = AppConfig()
        assert hasattr(config, 'feeds'), "feeds 配置未加载"
        assert hasattr(config, 'dedup'), "dedup 配置未加载"
        assert hasattr(config, 'assembly'), "assembly 配置未加载"
        assert hasattr(config, 'llm'), "llm 配置未加载"

    def test_feeds_config(self):
        config = AppConfig()
        assert len(config.feeds.feeds) > 0, "RSS源列表为空"
        assert config.feeds.timeout_seconds > 0, "超时时间无效"
        assert config.feeds.max_retries > 0, "重试次数无效"

    def test_dedup_config(self):
        config = AppConfig()
        assert 0 <= config.dedup.title_similarity_threshold <= 1, "相似度阈值无效"
        assert config.dedup.word_ngram_n > 0, "n-gram长度无效"
        assert config.dedup.char_ngram_n > 0, "n-gram长度无效"

    def test_assembly_config(self):
        config = AppConfig()
        assert len(config.assembly.modules) > 0, "模块列表为空"
        assert config.assembly.max_news_per_module > 0, "最大新闻数无效"

    def test_filter_rank_config(self):
        config = AppConfig()
        assert config.filter_rank.max_news_per_topic > 0, "最大主题新闻数无效"

    def test_feeds_time_window(self):
        config = AppConfig()
        assert config.feeds.time_window_hours > 0, "时间窗无效"

    def test_module_query(self):
        config = AppConfig()
        modules = [m for m in config.assembly.modules if m.id == 'model']
        assert len(modules) > 0, "模块查询失败"
        module = modules[0]
        assert module.name == "大模型", "模块名称不正确"

    def test_template_coverage(self):
        config = AppConfig()
        rules = config.template.classification_rules
        coverage = ' · '.join(getattr(m, 'name', '') for m in rules)
        assert "大模型" in coverage, "template.classification_rules 应包含大模型"
        assert " · " in coverage, "coverage 应用 · 分隔"


class TestConfigDict:
    """ConfigDict 类测试"""

    def test_basic_access(self):
        data = {'timeout_seconds': 20, 'max_retries': 3}
        cfg = ConfigDict(data)
        assert cfg.timeout_seconds == 20
        assert cfg.max_retries == 3

    def test_defaults(self):
        data = {'timeout_seconds': 30, 'max_retries': 3}
        cfg = ConfigDict(data)
        assert cfg.timeout_seconds == 30
        assert cfg.max_retries == 3

    def test_nested_dict(self):
        data = {'settings': {'timeout': 20}, 'feeds': [{'url': 'https://example.com'}]}
        cfg = ConfigDict(data)
        assert cfg.settings.timeout == 20
        assert cfg.feeds[0].url == 'https://example.com'

    def test_empty(self):
        cfg = ConfigDict()
        assert cfg.__dict__ == {}

    def test_empty_with_defaults(self):
        data = {'timeout_seconds': 20, 'max_retries': 3}
        cfg = ConfigDict(data)
        assert cfg.timeout_seconds == 20
        assert cfg.max_retries == 3


class TestFeedsConfig:
    """Feeds 配置测试（通过 ConfigDict）"""

    def test_feeds_config_creation(self):
        data = {
            'timeout_seconds': 20,
            'max_retries': 3,
            'max_items_per_feed': 100,
            'max_items_total': 1000,
            'user_agent': 'TestAgent/1.0',
            'retry_backoff_seconds': 1.5,
        }
        cfg = ConfigDict(data)
        assert cfg.timeout_seconds == 20
        assert cfg.max_retries == 3

    def test_feeds_list(self):
        feeds = [{'source': 'Test', 'url': 'https://example.com/feed', 'verify_tls': True}]
        cfg = ConfigDict({'feeds': feeds})
        assert len(cfg.feeds) == 1
        assert cfg.feeds[0].source == 'Test'


class TestDedupConfig:
    """Dedup 配置测试（通过 ConfigDict）"""

    def test_dedup_config_creation(self):
        data = {
            'title_similarity_threshold': 0.88,
            'word_ngram_n': 3,
            'char_ngram_n': 3,
            'recent_summary_enabled': True,
            'recent_summary_days': 3,
            'recent_summary_title_threshold': 0.90,
            'recent_summary_text_threshold': 0.45,
        }
        cfg = ConfigDict(data)
        assert cfg.title_similarity_threshold == 0.88
        assert cfg.word_ngram_n == 3
        assert cfg.recent_summary_enabled is True


class TestAssemblyConfig:
    """Assembly 配置测试（通过 ConfigDict）"""

    def test_assembly_config_creation(self):
        data = {
            'max_news_per_module': 8,
        }
        cfg = ConfigDict(data)
        assert cfg.max_news_per_module == 8

    def test_modules_list(self):
        modules = [
            {'id': 'model', 'name': '大模型'},
            {'id': 'hardware', 'name': 'AI硬件'},
        ]
        cfg = ConfigDict({'modules': modules})
        assert len(cfg.modules) == 2
        assert cfg.modules[0].id == 'model'
        assert cfg.modules[0].name == '大模型'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])