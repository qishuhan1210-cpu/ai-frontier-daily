"""
domain — AI-Froniteer-Daily 数据模型层

数据流程：
    ingested.jsonl (RSS原始)
        ↓
    filtered_ranked.json (筛选+分类+排序)
        ↓
    summary.json (LLM摘要增强)
        ↓
    briefing.md (最终简报)

继承关系：
    NewsItem (基类) → FilteredItem → SummaryItem
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass(frozen=True)
class NewsItem:
    """RSS 抓取的原始新闻条目"""
    title: str
    url: str
    source: str
    summary: str
    pub_time: str
    _feed_url: str = field(default='', compare=False)

    @staticmethod
    def from_dict(d: dict) -> 'NewsItem':
        return NewsItem(
            title=d.get('title', ''),
            url=d.get('url', ''),
            source=d.get('source', ''),
            summary=d.get('summary', ''),
            pub_time=d.get('pub_time', ''),
            _feed_url=d.get('_feed_url', ''),
        )


@dataclass(frozen=True)
class FilteredItem(NewsItem):
    """筛选+分类+排序后的新闻条目"""
    main_section: str = ''
    sub_section: str = ''
    relevance: float = 0.0
    hot_level: float = 0.0
    rank: int = 0

    @staticmethod
    def from_dict(d: dict) -> 'FilteredItem':
        return FilteredItem(
            title=d.get('title', ''),
            url=d.get('url', ''),
            source=d.get('source', ''),
            summary=d.get('summary', ''),
            pub_time=d.get('pub_time', ''),
            _feed_url=d.get('_feed_url', ''),
            main_section=d.get('main_section', ''),
            sub_section=d.get('sub_section', ''),
            relevance=float(d.get('relevance', 0)),
            hot_level=float(d.get('hot_level', 0)),
            rank=int(d.get('rank', 0)),
        )

    @staticmethod
    def from_llm_response(data: dict) -> List[Dict[str, Any]]:
        """从 LLM 响应中提取 items 字典（不做过滤）"""
        if not isinstance(data, dict):
            return []

        items = []
        for row in data.get('items', []):
            if not isinstance(row, dict):
                continue

            si = row.get('source_index')
            if si is None:
                continue
            try:
                si_int = int(si)
            except (ValueError, TypeError):
                continue

            items.append({
                'source_index': si_int,
                'main_section': row.get('main_section', ''),
                'sub_section': row.get('sub_section', ''),
                'relevance': float(row.get('relevance', 0)),
                'hot_level': float(row.get('hot_level', 0)),
            })

        return items

    @classmethod
    def from_news_and_llm(cls, news_item: NewsItem, llm_result: Dict[str, Any], rank: int) -> 'FilteredItem':
        """从 NewsItem 和 LLM 结果合并创建 FilteredItem"""
        return cls(
            title=news_item.title,
            url=news_item.url,
            source=news_item.source,
            summary=news_item.summary,
            pub_time=news_item.pub_time,
            _feed_url=news_item._feed_url,
            main_section=llm_result.get('main_section', ''),
            sub_section=llm_result.get('sub_section', ''),
            relevance=float(llm_result.get('relevance', 0)),
            hot_level=float(llm_result.get('hot_level', 0)),
            rank=rank,
        )


@dataclass(frozen=True)
class SummaryItem(FilteredItem):
    """LLM 摘要增强后的新闻条目"""
    headline: str = ''
    plain_explain: str = ''
    impact_1: str = ''
    impact_2: str = ''
    digest_for_outline: str = ''
    vertical_tags: List[str] = field(default_factory=list)
    general_tags: List[str] = field(default_factory=list)
    hot: str = ''

    @staticmethod
    def extract_articles(data: dict) -> tuple:
        """从 LLM 响应中提取 articles 和 drop_indices"""
        if not isinstance(data, dict):
            return {}, set()

        by_source = {}
        for a in data.get('articles', []):
            if not isinstance(a, dict):
                continue
            si = a.get('source_index')
            if si is None:
                continue
            try:
                by_source[int(si)] = a
            except (ValueError, TypeError):
                continue

        drop = set()
        for x in data.get('deduplication', {}).get('drop_indices', []):
            try:
                drop.add(int(x))
            except (ValueError, TypeError):
                continue

        return by_source, drop

    @classmethod
    def from_filtered_and_llm(cls, filtered_item: FilteredItem, llm_data: dict) -> 'SummaryItem':
        """从 FilteredItem 和 LLM 数据创建 SummaryItem"""
        vertical_tags = llm_data.get('vertical_tags', [])
        if isinstance(vertical_tags, str):
            vertical_tags = [vertical_tags] if vertical_tags else []
        general_tags = llm_data.get('general_tags', [])
        if isinstance(general_tags, str):
            general_tags = [general_tags] if general_tags else []

        return cls(
            title=filtered_item.title,
            url=filtered_item.url,
            source=filtered_item.source,
            summary=filtered_item.summary,
            pub_time=filtered_item.pub_time,
            _feed_url=filtered_item._feed_url,
            main_section=filtered_item.main_section,
            sub_section=filtered_item.sub_section,
            relevance=filtered_item.relevance,
            hot_level=filtered_item.hot_level,
            rank=filtered_item.rank,
            headline=llm_data.get('headline', ''),
            plain_explain=llm_data.get('plain_explain', ''),
            impact_1=llm_data.get('impact_1', ''),
            impact_2=llm_data.get('impact_2', ''),
            digest_for_outline=llm_data.get('digest_for_outline', ''),
            vertical_tags=vertical_tags,
            general_tags=general_tags,
            hot=llm_data.get('hot', ''),
        )

    @staticmethod
    def from_dict(d: dict) -> 'SummaryItem':
        vertical_tags = d.get('vertical_tags', [])
        if isinstance(vertical_tags, str):
            vertical_tags = [vertical_tags] if vertical_tags else []
        general_tags = d.get('general_tags', [])
        if isinstance(general_tags, str):
            general_tags = [general_tags] if general_tags else []

        return SummaryItem(
            title=d.get('title', ''),
            url=d.get('url', ''),
            source=d.get('source', ''),
            summary=d.get('summary', ''),
            pub_time=d.get('pub_time', ''),
            _feed_url=d.get('_feed_url', ''),
            main_section=d.get('main_section', ''),
            sub_section=d.get('sub_section', ''),
            relevance=float(d.get('relevance', 0)),
            hot_level=float(d.get('hot_level', 0)),
            rank=int(d.get('rank', 0)),
            headline=d.get('headline', ''),
            plain_explain=d.get('plain_explain', ''),
            impact_1=d.get('impact_1', ''),
            impact_2=d.get('impact_2', ''),
            digest_for_outline=d.get('digest_for_outline', ''),
            vertical_tags=vertical_tags,
            general_tags=general_tags,
            hot=d.get('hot', ''),
        )


@dataclass(frozen=True)
class FilterStats:
    """筛选统计信息"""
    input_count: int = 0
    output_count: int = 0
    dropped_count: int = 0
    top_topics: List[str] = field(default_factory=list)

    @staticmethod
    def from_counts(
        input_count: int,
        output_count: int,
        section_counts: Dict[str, int],
        top_n: int = 5,
    ) -> 'FilterStats':
        """从统计计数创建 FilterStats"""
        return FilterStats(
            input_count=input_count,
            output_count=output_count,
            dropped_count=input_count - output_count,
            top_topics=sorted(section_counts.keys(), key=lambda x: section_counts[x], reverse=True)[:top_n],
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'input_count': self.input_count,
            'output_count': self.output_count,
            'dropped_count': self.dropped_count,
            'top_topics': self.top_topics,
        }


@dataclass(frozen=True)
class BriefingMeta:
    """简报元数据（头部+底部+数据项）"""
    items: List[SummaryItem] = field(default_factory=list)
    tags_full: str = '#AI早报'
    data_sources: str = '多家媒体'
    footer: dict = field(default_factory=dict)

    @staticmethod
    def from_dict(d: dict) -> 'BriefingMeta':
        items = [SummaryItem.from_dict(it) for it in d.get('items', [])]
        return BriefingMeta(
            items=items,
            tags_full=d.get('tags_full', '#AI早报'),
            data_sources=d.get('data_sources', '多家媒体'),
            footer=d.get('footer', {}),
        )
