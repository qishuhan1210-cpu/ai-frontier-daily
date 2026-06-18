#!/usr/bin/env python3
"""vector_dedup.py — 基于 ChromaDB + sentence-transformers 的向量去重引擎

为 IngestModule.dedup_recent_vector() 提供向量化语义去重支持。
原 n-gram Jaccard 去重实现（dedup_recent）完整保留，可随时切换。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Set


class VectorDedupEngine:
    """向量去重引擎

    封装 ChromaDB 持久化存储和 sentence-transformers embedding 调用。
    所有属性延迟初始化，未安装依赖时不影响 ngram 模式正常运行。
    """

    def __init__(
        self,
        db_path: str,
        collection_name: str,
        model_name: str,
        similarity_threshold: float,
        logger: Optional[logging.Logger] = None,
    ):
        self._db_path = str(Path(db_path).resolve())
        self._collection_name = collection_name
        self._model_name = model_name
        self._similarity_threshold = similarity_threshold
        self._client = None
        self._collection = None
        self._model = None

        if logger is not None:
            self._log = logger
        else:
            from utils.logger import get_logger
            self._log = get_logger('vector_dedup')

        self._log.info(
            f'VectorDedupEngine 初始化: db={self._db_path}, '
            f'collection={collection_name}, model={model_name}, '
            f'threshold={similarity_threshold}'
        )

    # ------------------------------------------------------------------
    # 延迟初始化
    # ------------------------------------------------------------------

    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        import chromadb
        if self._client is None:
            Path(self._db_path).mkdir(parents=True, exist_ok=True)
            self._log.info(f'ChromaDB 连接: {self._db_path}')
            self._client = chromadb.PersistentClient(path=self._db_path)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        total = self._collection.count()
        self._log.info(f'ChromaDB 集合 "{self._collection_name}" 已就绪，当前共 {total} 条记录')
        return self._collection

    def _get_model(self):
        if self._model is None:
            self._log.info(f'加载 Embedding 模型: {self._model_name}（首次运行需下载，请稍候）')
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
            self._log.info(f'Embedding 模型加载完成: {self._model_name}')
        return self._model

    def _embed(self, texts: List[str]) -> List[List[float]]:
        return self._get_model().encode(texts, show_progress_bar=False).tolist()

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def index_date(self, date_str: str, clusters: list, force: bool = False) -> int:
        """将某日 summary.json 的 clusters 索引到 ChromaDB

        Args:
            date_str: 日期字符串，如 "2026-06-17"
            clusters: summary.json 中 clusters 列表
            force: True 时先删除该日期的旧数据再重新索引（用于 summary.json 重跑后更新）

        Returns:
            本次实际写入的条目数（0 表示已索引且未强制，跳过）
        """
        collection = self._get_collection()

        existing = collection.get(where={"date": date_str}, include=["metadatas"])
        if existing["ids"]:
            if not force:
                self._log.debug(f'index_date: {date_str} 已存在 {len(existing["ids"])} 条，跳过（force=False）')
                return 0
            self._log.info(f'index_date: {date_str} 强制重建，删除旧记录 {len(existing["ids"])} 条')
            collection.delete(ids=existing["ids"])

        texts, ids, metadatas = [], [], []
        skipped = 0
        for i, cluster in enumerate(clusters):
            title = (cluster.get("title") or "").strip()
            plain_explain = (cluster.get("plain_explain") or "").strip()
            digest = (cluster.get("digest_for_outline") or "").strip()
            text = " ".join(filter(None, [title, plain_explain, digest])).strip()
            if not text:
                skipped += 1
                continue
            ids.append(f"{date_str}_{i}")
            texts.append(text)
            metadatas.append({
                "date": date_str,
                "url": (cluster.get("url") or "").strip(),
                "title": title,
            })

        if skipped:
            self._log.debug(f'index_date: {date_str} 跳过 {skipped} 条无文本 cluster')

        if not texts:
            self._log.warning(f'index_date: {date_str} 无可索引内容（共 {len(clusters)} 个 cluster 均无文本）')
            return 0

        self._log.info(f'index_date: {date_str} 生成 {len(texts)} 条 embedding，写入 ChromaDB')
        embeddings = self._embed(texts)
        collection.add(embeddings=embeddings, ids=ids, metadatas=metadatas, documents=texts)
        self._log.info(f'index_date: {date_str} 写入完成，集合当前共 {collection.count()} 条记录')
        return len(texts)

    def cleanup_before(self, cutoff_date_str: str) -> int:
        """删除早于 cutoff_date_str 的所有历史条目，防止 ChromaDB 无限膨胀

        Args:
            cutoff_date_str: 截止日期（不含），格式 "YYYY-MM-DD"
                             早于此日期的条目将被删除

        Returns:
            实际删除的条目数
        """
        collection = self._get_collection()
        total_before = collection.count()
        if total_before == 0:
            self._log.debug('cleanup_before: 集合为空，无需清理')
            return 0

        try:
            old_entries = collection.get(
                where={"date": {"$lt": cutoff_date_str}},
                include=["metadatas"],
            )
            if not old_entries["ids"]:
                self._log.debug(f'cleanup_before: 无早于 {cutoff_date_str} 的过期条目')
                return 0
            collection.delete(ids=old_entries["ids"])
            deleted = len(old_entries["ids"])
            self._log.info(
                f'cleanup_before: 删除 {cutoff_date_str} 之前的过期条目 {deleted} 条，'
                f'集合剩余 {collection.count()} 条'
            )
            return deleted
        except Exception as e:
            self._log.error(f'cleanup_before: 清理失败: {e}')
            return 0

    def query_matches(self, item_text: str, norm_url: str, date_range: List[str]) -> Set[str]:
        """查询 item 匹配的历史日期集合

        匹配层级（优先级从高到低）：
        1. URL 元数据精确匹配（等价原 URL 精确层）
        2. 向量余弦相似度匹配（替代原标题+内容 Jaccard 层）

        Args:
            item_text: 待查询的文本（title + summary）
            norm_url: 规范化后的 URL
            date_range: 限定的历史日期列表（非空）

        Returns:
            匹配到的历史日期集合
        """
        if not date_range:
            return set()

        collection = self._get_collection()
        if collection.count() == 0:
            self._log.debug('query_matches: 集合为空，直接返回')
            return set()

        matched_dates: Set[str] = set()
        date_filter = {"date": {"$in": date_range}}

        # 层级1：URL 精确匹配
        if norm_url:
            try:
                url_result = collection.get(
                    where={"$and": [{"url": norm_url}, date_filter]},
                    include=["metadatas"],
                )
                for meta in url_result.get("metadatas") or []:
                    matched_dates.add(meta["date"])
                if matched_dates:
                    self._log.debug(
                        f'query_matches: URL精确命中 url={norm_url} → 日期={sorted(matched_dates)}'
                    )
            except Exception as e:
                self._log.debug(f'query_matches: URL查询异常: {e}')

        # 层级2：向量相似度匹配
        if not item_text:
            return matched_dates

        try:
            n_results = min(50, collection.count())
            results = collection.query(
                query_embeddings=self._embed([item_text]),
                n_results=n_results,
                where=date_filter,
                include=["metadatas", "distances"],
            )
            new_hits = 0
            for meta, distance in zip(
                results["metadatas"][0], results["distances"][0]
            ):
                # ChromaDB cosine distance: 0=identical；similarity = 1 - distance
                similarity = 1.0 - distance
                if similarity >= self._similarity_threshold:
                    is_new = meta["date"] not in matched_dates
                    matched_dates.add(meta["date"])
                    if is_new:
                        new_hits += 1
                    self._log.debug(
                        f'query_matches: 向量命中 sim={similarity:.4f} '
                        f'(≥{self._similarity_threshold}) '
                        f'title="{meta.get("title", "")[:30]}" date={meta["date"]}'
                    )
            if new_hits:
                self._log.debug(
                    f'query_matches: 向量层新增命中 {new_hits} 个日期，'
                    f'累计匹配日期={sorted(matched_dates)}'
                )
        except Exception as e:
            self._log.error(f'query_matches: 向量查询异常: {e}')

        return matched_dates
