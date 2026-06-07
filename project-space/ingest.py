#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingest.py — RSS 抓取、去重模块、关键词粗筛
"""

from __future__ import annotations

import html
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from utils import AppConfig, WorkModule, FN_SUMMARY
from utils.domain import NewsItem

try:
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    requests = None


class IngestModule(WorkModule):
    """RSS 抓取与去重"""

    def __init__(self, config: AppConfig):
        super().__init__('ingest', config.date_str)
        self.feeds_config = config.modules.public_feeds
        self.dedup_config = config.modules.dedup
        self._app_config = config

    @staticmethod
    def strip_html(raw: Optional[str], limit: int = 4000) -> str:
        if not raw:
            return ''
        text = re.sub(r'<[^>]+>', ' ', raw)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:limit]

    @staticmethod
    def is_placeholder(text: str, patterns: tuple = ('点击查看原文', 'click to read', 'read more')) -> bool:
        if not text:
            return True
        t = text.strip()
        if len(t) < 6:
            return True
        low = t.lower()
        for p in patterns:
            if p in t or p.lower() in low:
                return True
        return False

    @staticmethod
    def similarity_tokens(text: str, word_n: int = 3, char_n: int = 3) -> set:
        text = (text or '').lower().strip()
        if not text:
            return set()
        tokens = []
        words = text.split()
        if word_n >= 1 and len(words) >= word_n:
            for i in range(len(words) - word_n + 1):
                tokens.append(' '.join(words[i:i + word_n]))
        if char_n >= 1 and len(text) >= char_n:
            for i in range(len(text) - char_n + 1):
                tokens.append(text[i:i + char_n])
        return set(tokens)

    @staticmethod
    def jaccard_similarity(set_a: set, set_b: set) -> float:
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def _local_tag(self, tag: str) -> str:
        return tag.split('}')[-1] if tag and '}' in tag else (tag or '')

    def _text(self, el: Optional[ET.Element]) -> str:
        if el is None:
            return ''
        parts = [el.text or '']
        for c in el:
            parts.append(ET.tostring(c, encoding='unicode'))
        parts.append(el.tail or '')
        return self.strip_html(''.join(parts), 800)

    def _parse_date(self, text: Optional[str]) -> Optional[datetime]:
        if not text:
            return None
        text = text.strip()
        try:
            dt = parsedate_to_datetime(text)
            return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
        except Exception:
            pass
        try:
            return datetime.strptime(text[:19], '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            pass
        try:
            return datetime.strptime(text[:19], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None

    def _fetch(self, url: str, headers: dict, timeout: float, retries: int, backoff: float, verify: bool) -> Optional[bytes]:
        for attempt in range(retries):
            try:
                resp = requests.get(url, headers=headers, timeout=(5, timeout), verify=verify)
                resp.raise_for_status()
                return resp.content
            except Exception:
                if attempt < retries - 1:
                    time.sleep(backoff * (attempt + 1))
        return None

    def _scrape_article_content(self, url: str, timeout: float = 10.0) -> str:
        """抓取文章页面获取正文内容"""
        headers = {
            'User-Agent': self.feeds_config.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, verify=False)
            resp.raise_for_status()
            content = resp.text
            
            # 提取正文的简单策略
            # 优先查找常见的正文标签
            text = ''
            
            # 方法1：查找 article 标签
            article_match = re.search(r'<article[^>]*>(.*?)</article>', content, re.DOTALL)
            if article_match:
                text = self.strip_html(article_match.group(1), 3000)
            
            # 方法2：查找 main 标签
            if not text:
                main_match = re.search(r'<main[^>]*>(.*?)</main>', content, re.DOTALL)
                if main_match:
                    text = self.strip_html(main_match.group(1), 3000)
            
            # 方法3：查找 content 或 post-content 类
            if not text:
                content_match = re.search(r'<div[^>]*class=["\'].*?content.*?["\'].*?>(.*?)</div>', content, re.DOTALL | re.IGNORECASE)
                if content_match:
                    text = self.strip_html(content_match.group(1), 3000)
            
            # 方法4：查找 body 中主要文本
            if not text:
                body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL)
                if body_match:
                    full_body = self.strip_html(body_match.group(1), 5000)
                    # 取前3000字符作为正文
                    text = full_body[:3000]
            
            # 清理文本
            text = re.sub(r'点击查看原文|阅读全文|了解更多', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            
            return text
        except Exception as e:
            self.logger.warning(f"抓取文章失败 {url}: {str(e)[:50]}")
            return ''

    def _parse_rss(self, xml_bytes: bytes, source: str) -> List[dict]:
        """解析 RSS/Atom XML"""
        items = []
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError:
            return items
        root_tag = self._local_tag(root.tag)
        for elem in root.iter():
            tag = self._local_tag(elem.tag)
            if root_tag == 'rss' and tag != 'item':
                continue
            if root_tag == 'feed' and tag != 'entry':
                continue

            # 提取字段
            title, link, summary, pub_raw = '', '', '', ''
            for child in elem:
                ct = self._local_tag(child.tag)
                if ct == 'title':
                    title = self._text(child)
                elif ct == 'link':
                    link = (child.text or '').strip() or child.attrib.get('href', '')
                elif ct in ('description', 'summary', 'content', 'encoded'):
                    summary = self._text(child)
                elif ct in ('pubDate', 'published', 'updated', 'date'):
                    pub_raw = (child.text or '').strip()

            # 处理 guid 作为备选 link
            if not link and root_tag == 'rss':
                for child in elem:
                    if self._local_tag(child.tag) == 'guid':
                        g = (child.text or '').strip()
                        if g.startswith(('http://', 'https://')):
                            link = g

            if title and link:
                pub_dt = self._parse_date(pub_raw)
                # 如果摘要只是占位符，尝试抓取原文
                if self.is_placeholder(summary):
                    self.logger.info(f"摘要为占位符，尝试抓取原文: {title[:30]}...")
                    scraped = self._scrape_article_content(link)
                    if scraped and len(scraped) > 50:
                        summary = scraped
                    else:
                        summary = ''  # 仍然为空
                item = {'title': title, 'url': link.strip(), 'source': source, 'summary': summary}
                if pub_dt:
                    item['pub_time'] = pub_dt.isoformat(sep=' ', timespec='seconds')
                items.append(item)

        return items

    def _in_window(self, item: dict, hours: int) -> bool:
        raw = item.get('pub_time')
        if not raw:
            return True
        try:
            dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
            day = datetime.strptime(self.date_str, '%Y-%m-%d')
            center = day.replace(hour=12, minute=0, second=0)
            return abs((dt - center).total_seconds()) <= hours * 3600 * 2
        except Exception:
            return True

    def fetch(self) -> Tuple[List[dict], dict]:
        """拉取 RSS 源"""
        cfg = self.feeds_config
        timeout = float(cfg.timeout_seconds)
        retries = int(cfg.max_retries)
        backoff = float(cfg.retry_backoff_seconds)
        per_feed = int(cfg.max_items_per_feed)
        total_cap = int(cfg.max_items_total)
        window = self.feeds_config.time_window_hours

        ua = cfg.user_agent
        headers = {'User-Agent': ua, 'Accept': 'application/rss+xml, application/xml, text/xml, */*'}

        all_items, seen, errors = [], set(), 0

        for feed in cfg.feeds:
            url = feed.get('url', '').strip()
            source = feed.get('source', urlparse(url).netloc or 'unknown')
            if not url:
                continue

            _t0 = time.monotonic()
            body = self._fetch(url, headers, timeout, retries, backoff, feed.get('verify_tls', True))
            
            if body is None:
                errors += 1
                continue

            items = self._parse_rss(body, source)
            blacklist = list(cfg.url_blacklist_patterns) if hasattr(cfg, 'url_blacklist_patterns') else []
            kept = 0
            for it in items:
                if kept >= per_feed:
                    break
                u = it['url']
                if u in seen or not self._in_window(it, window):
                    continue
                if blacklist and any(pat in u for pat in blacklist):
                    continue
                seen.add(u)
                it['_feed_url'] = url
                all_items.append(it)
                kept += 1
            self.logger.info(f"fetch {time.monotonic() - _t0:.2f}s  {url}")

        # 按时间排序
        def sort_key(it):
            pt = it.get('pub_time')
            if not pt:
                return datetime.min
            try:
                return datetime.fromisoformat(pt.replace('Z', ''))
            except Exception:
                return datetime.min

        all_items.sort(key=sort_key, reverse=True)
        all_items = all_items[:total_cap]

        meta = {
            'count': len(all_items),
            'status': 'ok' if all_items else 'empty',
            'feeds_ok': len(self.feeds_config.feeds) - errors,
            'feeds_failed': errors,
        }
        return all_items, meta

    def dedup(self, items: List[NewsItem]) -> Tuple[List[NewsItem], dict]:
        """去重（URL + 标题相似度）
        
        双层去重策略：
        1. URL 精确匹配：相同 URL 直接跳过（最快的去重方式）
        2. 标题相似度去重：使用 Jaccard 相似度对比标题的 n-gram 特征
           - 避免同一事件被不同来源报道时产生的重复
        
        算法流程：
        - 使用 word_n 和 char_n 两种 n-gram 粒度提取标题特征
        - 通过 Jaccard 相似度计算标题相似度
        - 相似度超过阈值视为重复，仅保留第一条
        
        Args:
            items: 待去重的新闻列表
        
        Returns:
            去重后的新闻列表和统计信息
        """
        cfg = self.dedup_config
        threshold = float(cfg.title_similarity_threshold)
        word_n = int(cfg.word_ngram_n)
        char_n = int(cfg.char_ngram_n)

        seen_urls, url_to_tokens, passed = set(), {}, []

        for it in items:
            url = it.url or ''

            # 第一层：URL 精确去重（同一链接只保留一次）
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # 第二层：标题相似度去重（防止同源不同链接的重复）
            tokens = self.similarity_tokens(it.title or '', word_n, char_n)
            is_dup = any(self.jaccard_similarity(tokens, t) > threshold for t in url_to_tokens.values())
            if is_dup:
                continue

            if it.title:
                url_to_tokens[url] = tokens
            passed.append(it)

        return passed, {'count': len(passed)}

    def dedup_recent(self, items: List[NewsItem]) -> Tuple[List[NewsItem], dict]:
        """与近几日历史摘要去重（跨日去重）

        核心策略：
        - 检测新闻是否在近几日的摘要中出现过
        - 已出现的新闻视为重复，予以剔除
        - 但连续/累计出现 N 天（persistent_days_threshold）以上的新闻视为持续热点，保留

        相似度匹配层级（优先级从高到低）：
        1. URL 精确匹配：相同链接直接判定为重复
        2. 标题相似度匹配：使用 Jaccard 相似度对比标题
        3. 内容摘要相似度匹配：对较长内容（≥48字符）对比正文摘要

        数据来源：从 output 目录读取近 n_days 天的 summary.json 文件

        Args:
            items: 待去重的新闻列表

        Returns:
            去重后的新闻列表和统计信息（enabled: 是否启用, dropped: 被剔除数量）
        """
        cfg = self.dedup_config
        if not cfg.recent_summary_enabled:
            return items, {'enabled': False, 'dropped': 0}

        n_days = max(0, int(cfg.recent_summary_days))
        word_n = int(cfg.word_ngram_n)
        char_n = int(cfg.char_ngram_n)
        title_thresh = float(cfg.recent_summary_title_threshold)
        body_thresh = float(cfg.recent_summary_text_threshold)
        persistent_days_threshold = int(self.dedup_config.persistent_days_threshold)

        base = datetime.strptime(self._app_config.date_str, '%Y-%m-%d')
        fingerprints_by_day = {}  # key: 天数偏移(1=昨天), value: 当天摘要的指纹列表

        # 第一步：加载近 n_days 天的历史摘要指纹
        for i in range(1, n_days + 1):
            d = (base - timedelta(days=i)).strftime('%Y-%m-%d')
            # 使用历史日期的目录，而不是当前日期的目录
            path = self._app_config.paths.output_dir().parent / d / FN_SUMMARY
            if not path.exists():
                continue
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                day_fps = []
                for it in data.get('clusters', []):
                    title = (it.get('title') or '').strip()
                    # 构建内容摘要指纹：组合多个字段，限制最大长度防止内存过大
                    outline = ' '.join(x for x in [
                        it.get('title'), it.get('summary'), it.get('one_liner'),
                        it.get('plain_explain'), it.get('digest_for_outline')
                    ] if x)[:self.dedup_config.outline_fingerprint_max_chars]
                    day_fps.append({
                        'url_norm': self._norm_url(it.get('url')),
                        'title_tok': self.similarity_tokens(title, word_n, char_n),
                        'body_tok': self.similarity_tokens(outline, word_n, char_n),
                    })
                fingerprints_by_day[i] = day_fps
            except Exception:
                continue

        # 若无历史数据，直接返回（避免误删）
        if not fingerprints_by_day:
            return items, {'enabled': True, 'dropped': 0}

        # 第二步：逐条新闻与历史指纹对比
        kept, dropped = [], 0
        for it in items:
            url = self._norm_url(it.url)
            title = (it.title or '').strip()
            outline = f"{title} {it.summary or ''}".strip()[:self.dedup_config.outline_fingerprint_max_chars]
            title_tok = self.similarity_tokens(title, word_n, char_n)
            body_tok = self.similarity_tokens(outline, word_n, char_n)

            matched_days = set()
            for day_idx, day_fps in fingerprints_by_day.items():
                for fp in day_fps:
                    matched_reason = None
                    # 层级1：URL 精确匹配（最高优先级）
                    if url and fp['url_norm'] and url == fp['url_norm']:
                        matched_reason = f"URL匹配: {url}"
                        matched_days.add(day_idx)
                        break
                    # 层级2：标题相似度匹配
                    if title_tok and fp['title_tok']:
                        title_sim = self.jaccard_similarity(title_tok, fp['title_tok'])
                        if title_sim >= title_thresh:
                            matched_reason = f"标题相似度匹配: {title_sim:.4f} >= {title_thresh}"
                            matched_days.add(day_idx)
                            break
                    # 层级3：内容摘要相似度匹配（仅对较长内容生效）
                    if len(outline) >= 48 and body_tok and fp['body_tok']:
                        body_sim = self.jaccard_similarity(body_tok, fp['body_tok'])
                        if body_sim >= body_thresh:
                            matched_reason = f"内容摘要相似度匹配: {body_sim:.4f} >= {body_thresh}"
                            matched_days.add(day_idx)
                            break
                    # 记录未匹配的原因（调试用）
                    if not matched_reason:
                        title_sim_val = self.jaccard_similarity(title_tok, fp['title_tok']) if title_tok and fp['title_tok'] else None
                        body_sim_val = self.jaccard_similarity(body_tok, fp['body_tok']) if body_tok and fp['body_tok'] else None
                        self.logger.debug(
                            f"去重检查未匹配 - URL匹配: {url == fp['url_norm'] if url and fp['url_norm'] else 'NA'}, "
                            f"标题相似度: {title_sim_val:.4f} (阈值:{title_thresh})" if title_sim_val is not None else "标题未计算, "
                            f"内容长度: {len(outline)}, 内容相似度: {body_sim_val:.4f} (阈值:{body_thresh})" if body_sim_val is not None else "内容未计算"
                        )

            # 决策逻辑：持续热点保留，单次重复剔除
            #if len(matched_days) >= persistent_days_threshold:
                # 在多个日期出现，视为持续热点，保留
                #kept.append(it)
            if len(matched_days) > 0:
                # 仅在部分日期出现，视为重复，剔除
                dropped += 1
            else:
                # 未在任何历史摘要中出现，保留
                kept.append(it)

        return kept, {'enabled': True, 'dropped': dropped}

    @staticmethod
    def _norm_url(url: Optional[str]) -> str:
        u = (url or '').strip()
        if not u:
            return ''
        try:
            p = urlparse(u)
            netloc = (p.netloc or '').lower()
            if netloc.startswith('www.'):
                netloc = netloc[4:]
            path = (p.path or '').rstrip('/')
            return f'{netloc}{path or "/"}'.lower()
        except Exception:
            return u.lower()

    def run(self, output_file: str) -> dict:
        """执行完整流程"""
        raw_items, crawl_meta = self.fetch()

        raw_items = [NewsItem.from_dict(it) for it in raw_items]

        deduped, dedup_meta = self.dedup(raw_items)
        final, recent_meta = self.dedup_recent(deduped)

        self.save_jsonl(output_file, [it.__dict__ for it in final])

        return {
            'count': len(final),
            'crawl': crawl_meta,
            'dedup': dedup_meta,
            'recent_summary_dedup': recent_meta,
        }