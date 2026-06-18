#!/usr/bin/env python3
"""VectorDedupEngine 单元测试

使用 tmp_path fixture 隔离 ChromaDB 目录，不污染生产数据。
依赖：chromadb, sentence-transformers
"""

import json
import sys
from pathlib import Path

import pytest

project_space = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_space))

try:
    from utils.vector_dedup import VectorDedupEngine
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

pytestmark = pytest.mark.skipif(not HAS_DEPS, reason="chromadb / sentence-transformers 未安装")

MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


@pytest.fixture
def engine(tmp_path):
    return VectorDedupEngine(
        db_path=str(tmp_path / "chroma_test"),
        collection_name="test_dedup",
        model_name=MODEL,
        similarity_threshold=0.80,
    )


CLUSTERS_DAY1 = [
    {
        "title": "OpenAI 发布 GPT-5 大模型",
        "plain_explain": "GPT-5 性能全面超越前代",
        "digest_for_outline": "OpenAI 于 2026 年正式发布 GPT-5",
        "url": "https://openai.com/gpt5",
    },
    {
        "title": "谷歌推出 Gemini Ultra 2.0",
        "plain_explain": "多模态能力大幅增强",
        "digest_for_outline": "谷歌发布 Gemini Ultra 2.0，支持视频理解",
        "url": "https://deepmind.google/gemini",
    },
]

CLUSTERS_DAY2 = [
    {
        "title": "Anthropic Claude 4 发布",
        "plain_explain": "Claude 4 推理能力领先",
        "digest_for_outline": "Anthropic 宣布发布 Claude 4",
        "url": "https://anthropic.com/claude4",
    },
]


class TestIndexDate:
    def test_index_and_count(self, engine):
        """正常索引后集合中应有对应条目"""
        n = engine.index_date("2026-06-17", CLUSTERS_DAY1)
        assert n == len(CLUSTERS_DAY1)
        assert engine._get_collection().count() == len(CLUSTERS_DAY1)

    def test_idempotent(self, engine):
        """同日期重复调用 index_date 不应增加条目"""
        engine.index_date("2026-06-17", CLUSTERS_DAY1)
        n2 = engine.index_date("2026-06-17", CLUSTERS_DAY1)
        assert n2 == 0
        assert engine._get_collection().count() == len(CLUSTERS_DAY1)

    def test_force_reindex(self, engine):
        """force=True 时应删除旧数据重新写入"""
        engine.index_date("2026-06-17", CLUSTERS_DAY1)
        n2 = engine.index_date("2026-06-17", CLUSTERS_DAY1, force=True)
        assert n2 == len(CLUSTERS_DAY1)
        # 数量应与重建后相同，不应翻倍
        assert engine._get_collection().count() == len(CLUSTERS_DAY1)

    def test_multiple_dates(self, engine):
        """不同日期均可独立索引"""
        engine.index_date("2026-06-17", CLUSTERS_DAY1)
        engine.index_date("2026-06-16", CLUSTERS_DAY2)
        assert engine._get_collection().count() == len(CLUSTERS_DAY1) + len(CLUSTERS_DAY2)

    def test_empty_clusters(self, engine):
        """空 clusters 不应写入任何条目"""
        n = engine.index_date("2026-06-17", [])
        assert n == 0
        assert engine._get_collection().count() == 0

    def test_cluster_missing_text(self, engine):
        """缺少文本字段的 cluster 应被跳过"""
        n = engine.index_date("2026-06-17", [{"url": "https://x.com"}])
        assert n == 0


class TestCleanupBefore:
    def test_cleanup_removes_old(self, engine):
        """早于 cutoff 的条目应被删除"""
        engine.index_date("2026-06-14", CLUSTERS_DAY1)
        engine.index_date("2026-06-15", CLUSTERS_DAY2)
        engine.index_date("2026-06-17", CLUSTERS_DAY1)
        # cutoff=2026-06-15，应删除 06-14 的数据
        deleted = engine.cleanup_before("2026-06-15")
        assert deleted == len(CLUSTERS_DAY1)
        assert engine._get_collection().count() == len(CLUSTERS_DAY2) + len(CLUSTERS_DAY1)

    def test_cleanup_empty_db(self, engine):
        """空库执行 cleanup 应返回 0，不报错"""
        deleted = engine.cleanup_before("2026-06-15")
        assert deleted == 0

    def test_cleanup_nothing_old(self, engine):
        """所有条目都在 cutoff 之后，应返回 0"""
        engine.index_date("2026-06-17", CLUSTERS_DAY1)
        deleted = engine.cleanup_before("2026-06-15")
        assert deleted == 0
        assert engine._get_collection().count() == len(CLUSTERS_DAY1)


class TestQueryMatches:
    def test_empty_db(self, engine):
        """空库查询应返回空集合，不抛异常"""
        result = engine.query_matches("OpenAI GPT-5", "", ["2026-06-17"])
        assert result == set()

    def test_empty_date_range(self, engine):
        """date_range 为空时直接返回空集合"""
        engine.index_date("2026-06-17", CLUSTERS_DAY1)
        result = engine.query_matches("OpenAI GPT-5", "", [])
        assert result == set()

    def test_url_exact_match(self, engine):
        """URL 精确匹配应返回对应日期"""
        engine.index_date("2026-06-17", CLUSTERS_DAY1)
        # _norm_url 规范化后 openai.com/gpt5
        result = engine.query_matches("", "openai.com/gpt5", ["2026-06-17"])
        assert "2026-06-17" in result

    def test_url_not_in_date_range(self, engine):
        """URL 精确匹配但日期不在 date_range 内，应返回空集合"""
        engine.index_date("2026-06-17", CLUSTERS_DAY1)
        result = engine.query_matches("", "openai.com/gpt5", ["2026-06-16"])
        assert result == set()

    def test_vector_similar_match(self, engine):
        """语义相近的文本应返回匹配日期"""
        engine.index_date("2026-06-17", CLUSTERS_DAY1)
        # "GPT-5 模型正式发布" 与索引中 "OpenAI 发布 GPT-5 大模型" 语义相近
        result = engine.query_matches("GPT-5 模型正式发布 超越前代", "", ["2026-06-17"])
        assert "2026-06-17" in result

    def test_vector_no_match_unrelated(self, engine):
        """语义完全不同的文本不应匹配"""
        engine.index_date("2026-06-17", CLUSTERS_DAY1)
        # 完全不相关内容
        result = engine.query_matches("今日天气晴好适合出行", "", ["2026-06-17"])
        assert result == set()

    def test_match_only_in_relevant_date(self, engine):
        """多日期索引，只有包含匹配内容的日期应被返回"""
        engine.index_date("2026-06-17", CLUSTERS_DAY1)
        engine.index_date("2026-06-16", CLUSTERS_DAY2)
        result = engine.query_matches("Claude Anthropic 发布新模型", "", ["2026-06-17", "2026-06-16"])
        # Day2 有 Claude 4，Day1 没有
        assert "2026-06-16" in result
        assert "2026-06-17" not in result
