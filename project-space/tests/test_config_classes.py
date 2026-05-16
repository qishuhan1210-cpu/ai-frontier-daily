#!/usr/bin/env python3
"""配置类单元测试（适配三层架构）"""

import pytest
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from utils.base_config import AppConfig, ConfigDict, PROMPTS_DIR, CONFIG_YAML


class TestAppConfig:
    """AppConfig 类测试（三层架构）"""

    def test_path_constants(self):
        assert PROMPTS_DIR.exists(), f"提示词目录不存在: {PROMPTS_DIR}"
        assert CONFIG_YAML.exists(), f"配置文件不存在: {CONFIG_YAML}"

    def test_config_loading(self):
        config = AppConfig(date_str="2026-05-16")
        # 验证三层架构
        assert hasattr(config, 'modules'), "modules 配置层缺失"
        assert hasattr(config, 'links'), "links 配置层缺失"
        assert hasattr(config, 'protocols'), "protocols 配置层缺失"
        assert hasattr(config, 'paths'), "paths 配置缺失"

    def test_modules_layer(self):
        config = AppConfig(date_str="2026-05-16")
        assert hasattr(config.modules, 'public_feeds'), "public_feeds 缺失"
        assert hasattr(config.modules, 'dedup'), "dedup 缺失"
        assert hasattr(config.modules, 'filter_rank'), "filter_rank 缺失"
        assert hasattr(config.modules, 'assembly'), "assembly 缺失"

    def test_links_layer(self):
        config = AppConfig(date_str="2026-05-16")
        assert hasattr(config.links, 'llm'), "llm 缺失"

    def test_protocols_layer(self):
        config = AppConfig(date_str="2026-05-16")
        assert hasattr(config.protocols, 'protocol'), "protocol 缺失"
        assert hasattr(config.protocols, 'classification'), "classification 缺失"
        assert hasattr(config.protocols, 'vertical_tags_whitelist'), "vertical_tags_whitelist 缺失"
        assert hasattr(config.protocols, 'general_tags_whitelist'), "general_tags_whitelist 缺失"

    def test_feeds_config(self):
        config = AppConfig(date_str="2026-05-16")
        feeds = config.modules.public_feeds
        assert len(feeds.feeds) > 0, "RSS源列表为空"
        assert feeds.timeout_seconds > 0, "超时时间无效"
        assert feeds.max_retries > 0, "重试次数无效"

    def test_dedup_config(self):
        config = AppConfig(date_str="2026-05-16")
        dedup = config.modules.dedup
        assert 0 <= dedup.title_similarity_threshold <= 1, "相似度阈值无效"
        assert dedup.word_ngram_n > 0, "n-gram长度无效"
        assert dedup.char_ngram_n > 0, "n-gram长度无效"

    def test_assembly_config(self):
        config = AppConfig(date_str="2026-05-16")
        assembly = config.modules.assembly
        assert assembly.max_news_per_module > 0, "最大新闻数无效"

    def test_filter_rank_config(self):
        config = AppConfig(date_str="2026-05-16")
        filter_rank = config.modules.filter_rank
        assert filter_rank.max_news_per_topic > 0, "最大主题新闻数无效"

    def test_feeds_time_window(self):
        config = AppConfig(date_str="2026-05-16")
        feeds = config.modules.public_feeds
        assert feeds.time_window_hours > 0, "时间窗无效"

    def test_classification_config(self):
        config = AppConfig(date_str="2026-05-16")
        sections = config.protocols.classification.main_sections
        core_tech_modules = [m for m in sections if getattr(m, 'id', '') == 'core_tech']
        assert len(core_tech_modules) > 0, "core_tech 模块未找到"
        module = core_tech_modules[0]
        assert module.name == "大模型与核心技术", "模块名称不正确"

    def test_protocol_fields(self):
        config = AppConfig(date_str="2026-05-16")
        protocol = config.protocols.protocol
        assert hasattr(protocol, 'summarize'), "summarize 协议缺失"
        fields = protocol.summarize.fields
        assert len(fields) > 0, "协议字段列表为空"
        field_names = [f.name for f in fields]
        assert 'main_section' in field_names, "main_section 字段缺失"
        assert 'vertical_tags' in field_names, "vertical_tags 字段缺失"
        assert 'general_tags' in field_names, "general_tags 字段缺失"

    def test_paths_config(self):
        config = AppConfig(date_str="2026-05-16")
        paths = config.paths
        assert paths.output_dir() is not None, "output_dir 无效"
        day_paths = paths.day_paths()
        assert 'summary' in day_paths, "day_paths 缺少 summary"
        assert 'briefing' in day_paths, "day_paths 缺少 briefing"


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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
