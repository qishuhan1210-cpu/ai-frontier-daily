#!/usr/bin/env python3
"""AppConfig 自我测试（适配三层架构）"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.base_config import AppConfig, PROMPTS_DIR, CONFIG_YAML


def test_app_config() -> bool:
    """验证配置加载是否正常"""
    try:
        print("[Self Test] Starting AppConfig self-test...")

        # 新配置需要 date_str 参数
        config = AppConfig(date_str="2026-05-16")
        print("[Self Test] ✓ 配置实例创建成功")

        # 验证路径常量
        assert PROMPTS_DIR.exists(), f"提示词目录不存在: {PROMPTS_DIR}"
        assert CONFIG_YAML.exists(), f"配置文件不存在: {CONFIG_YAML}"
        print("[Self Test] ✓ 路径常量测试通过")

        # 验证三层配置结构存在
        assert hasattr(config, 'modules'), "modules 配置层未加载"
        assert hasattr(config, 'links'), "links 配置层未加载"
        assert hasattr(config, 'protocols'), "protocols 配置层未加载"
        assert hasattr(config, 'paths'), "paths 配置未加载"
        print("[Self Test] ✓ 三层配置结构测试通过")

        # 验证模块层配置
        assert hasattr(config.modules, 'public_feeds'), "public_feeds 配置未加载"
        assert hasattr(config.modules, 'dedup'), "dedup 配置未加载"
        assert hasattr(config.modules, 'filter_rank'), "filter_rank 配置未加载"
        assert hasattr(config.modules, 'assembly'), "assembly 配置未加载"
        print("[Self Test] ✓ 模块层配置加载测试通过")

        # 验证链接层配置
        assert hasattr(config.links, 'llm'), "llm 配置未加载"
        print("[Self Test] ✓ 链接层配置加载测试通过")

        # 验证协议层配置
        assert hasattr(config.protocols, 'protocol'), "protocol 配置未加载"
        assert hasattr(config.protocols, 'classification'), "classification 配置未加载"
        print("[Self Test] ✓ 协议层配置加载测试通过")

        # 验证数据源配置
        assert len(config.modules.public_feeds.feeds) > 0, "RSS源列表为空"
        assert config.modules.public_feeds.timeout_seconds > 0, "超时时间无效"
        print("[Self Test] ✓ Feeds配置测试通过")

        # 验证去重配置
        assert 0 <= config.modules.dedup.title_similarity_threshold <= 1, "相似度阈值无效"
        assert config.modules.dedup.word_ngram_n > 0, "n-gram长度无效"
        print("[Self Test] ✓ Dedup配置测试通过")

        # 验证组装渲染配置
        assert config.modules.assembly.max_news_per_module > 0, "最大新闻数无效"
        print("[Self Test] ✓ Assembly配置测试通过")

        # 验证LLM配置
        assert config.links.llm.default_temperature > 0, "LLM温度无效"
        assert config.links.llm.default_max_tokens > 0, "LLM max_tokens无效"
        print("[Self Test] ✓ LLM配置测试通过")

        # 验证分类配置（主板块）
        sections = config.protocols.classification.main_sections
        assert len(sections) > 0, "主板块列表为空"
        core_tech_modules = [m for m in sections if getattr(m, 'id', '') == 'core_tech']
        assert len(core_tech_modules) > 0, "core_tech 模块未找到"
        assert core_tech_modules[0].name == "大模型与核心技术", "模块名称不正确"
        print("[Self Test] ✓ 分类配置测试通过")

        # 验证标签白名单
        assert len(config.protocols.vertical_tags_whitelist) > 0, "垂类标签白名单为空"
        assert len(config.protocols.general_tags_whitelist) > 0, "通用标签白名单为空"
        print("[Self Test] ✓ 标签白名单测试通过")

        # 验证路径配置
        output_dir = config.paths.output_dir()
        assert output_dir is not None, "输出目录无效"
        day_paths = config.paths.day_paths()
        assert 'summary' in day_paths, "day_paths 缺少 summary"
        assert 'briefing' in day_paths, "day_paths 缺少 briefing"
        print("[Self Test] ✓ 路径配置测试通过")

        # 验证 secrets 加载
        assert hasattr(config, 'llm_client_cfg'), "llm_client_cfg 属性不存在"
        assert isinstance(config.llm_client_cfg, dict), "llm_client_cfg 应为字典"
        print("[Self Test] ✓ Secrets加载测试通过")

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
