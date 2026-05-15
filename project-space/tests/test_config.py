#!/usr/bin/env python3
"""AppConfig 自我测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.base_config import AppConfig, PROMPTS_DIR


def test_app_config() -> bool:
    """验证配置加载是否正常"""
    try:
        print("[Self Test] Starting AppConfig self-test...")

        instance1 = AppConfig()
        instance2 = AppConfig()
        assert instance1 is instance2, "单例模式失败"
        print("[Self Test] ✓ 单例模式测试通过")

        config = instance1
        assert config.TEMPLATES_DIR.exists(), f"模板目录不存在: {config.TEMPLATES_DIR}"
        assert PROMPTS_DIR.exists(), f"提示词目录不存在: {PROMPTS_DIR}"
        print("[Self Test] ✓ 路径常量测试通过")

        assert hasattr(config, 'feeds'), "feeds 配置未加载"
        assert hasattr(config, 'dedup'), "dedup 配置未加载"
        assert hasattr(config, 'assembly'), "assembly 配置未加载"
        assert hasattr(config, 'llm'), "llm 配置未加载"
        print("[Self Test] ✓ 配置加载测试通过")

        assert len(config.feeds.feeds) > 0, "RSS源列表为空"
        assert config.feeds.timeout_seconds > 0, "超时时间无效"
        print("[Self Test] ✓ Feeds配置测试通过")

        assert 0 <= config.dedup.title_similarity_threshold <= 1, "相似度阈值无效"
        assert config.dedup.word_ngram_n > 0, "n-gram长度无效"
        print("[Self Test] ✓ Dedup配置测试通过")

        assert len(config.assembly.modules) > 0, "模块列表为空"
        assert config.assembly.max_news_per_module > 0, "最大新闻数无效"
        print("[Self Test] ✓ Assembly配置测试通过")

        module = config.get_module_by_id('model')
        assert module is not None, "模块查询失败"
        assert module.name == "一、大模型", "模块名称不正确"
        print("[Self Test] ✓ 模块查询测试通过")

        assert config.llm.default_temperature > 0, "LLM温度无效"
        assert config.llm.default_max_tokens > 0, "LLM max_tokens无效"
        print("[Self Test] ✓ LLM配置测试通过")

        print("[Self Test] All tests passed!")
        return True

    except Exception as e:
        print(f"[Self Test] FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_app_config()
    sys.exit(0 if success else 1)