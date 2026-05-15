#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingest.py — RSS 抓取、去重模块、关键词粗筛
"""

from __future__ import annotations

import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from utils import AppConfig, WorkModule, FN_SUMMARY

try:
    import requests
except ImportError:
    requests = None


class IngestModule(WorkModule):
    """RSS 抓取与去重"""

    def __init__(self, date_str: str, config: AppConfig):
        super().__init__(date_str, 'ingest')
        self.feeds_config = config.feeds
        self.dedup_config = config.dedup
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
                resp = requests.get(url, headers=headers, timeout=timeout, verify=verify)
                resp.raise_for_status()
                return resp.content
            except Exception:
                if attempt < retries - 1:
                    time.sleep(backoff * (attempt + 1))
        return None

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
        window = self._app_config.feeds.time_window_hours

        ua = cfg.user_agent
        headers = {'User-Agent': ua, 'Accept': 'application/rss+xml, application/xml, text/xml, */*'}

        all_items, seen, errors = [], set(), 0

        for feed in cfg.feeds:
            url = feed.get('url', '').strip()
            source = feed.get('source', urlparse(url).netloc or 'unknown')
            if not url:
                continue

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

    def dedup(self, items: List[dict]) -> Tuple[List[dict], dict]:
        """去重（URL + 标题相似度）"""
        cfg = self.dedup_config
        threshold = float(cfg.title_similarity_threshold)
        word_n = int(cfg.word_ngram_n)
        char_n = int(cfg.char_ngram_n)

        seen_urls, url_to_tokens, passed = set(), {}, []

        for it in items:
            url = it.get('url', '')
            title = it.get('title', '')

            if url in seen_urls:
                continue
            seen_urls.add(url)

            tokens = self.similarity_tokens(title, word_n, char_n)
            is_dup = any(self.jaccard_similarity(tokens, t) > threshold for t in url_to_tokens.values())
            if is_dup:
                continue

            if title:
                url_to_tokens[url] = tokens
            passed.append(it)

        return passed, {'count': len(passed)}

    def dedup_recent(self, items: List[dict]) -> Tuple[List[dict], dict]:
        """与近几日 summary 去重

        规则：
        - 近几日频繁出现的新闻视为重复（剔除）
        - 但连续/累计出现 4+ 天的新闻视为持续热点，保留
        """
        cfg = self.dedup_config
        if not cfg.recent_summary_enabled:
            return items, {'enabled': False, 'dropped': 0}

        n_days = max(0, int(cfg.recent_summary_days))
        word_n = int(cfg.word_ngram_n)
        char_n = int(cfg.char_ngram_n)
        title_thresh = float(cfg.recent_summary_title_threshold)
        body_thresh = float(cfg.recent_summary_text_threshold)
        # 持续热点阈值：出现天数 >= 4 则保留
        persistent_days_threshold = int(self.dedup_config.persistent_days_threshold)

        # 加载历史指纹：每条指纹关联其出现的日期索引
        base = datetime.strptime(self.date_str, '%Y-%m-%d')
        fingerprints_by_day = {}  # day_index -> [fingerprints]

        for i in range(1, n_days + 1):
            d = (base - timedelta(days=i)).strftime('%Y-%m-%d')
            path = self._app_config.output_dir(d) / FN_SUMMARY
            if not path.exists():
                continue
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                day_fps = []
                for it in data.get('items', []):
                    title = (it.get('title') or '').strip()
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

        if not fingerprints_by_day:
            return items, {'enabled': True, 'dropped': 0}

        # 去重：统计匹配到的历史指纹来自多少天
        kept, dropped = [], 0
        for it in items:
            url = self._norm_url(it.get('url'))
            title = (it.get('title') or '').strip()
            outline = f"{title} {it.get('summary', '')}".strip()[:self.dedup_config.outline_fingerprint_max_chars]
            title_tok = self.similarity_tokens(title, word_n, char_n)
            body_tok = self.similarity_tokens(outline, word_n, char_n)

            # 收集匹配到的日期索引
            matched_days = set()
            for day_idx, day_fps in fingerprints_by_day.items():
                for fp in day_fps:
                    # URL 完全匹配
                    if url and fp['url_norm'] and url == fp['url_norm']:
                        matched_days.add(day_idx)
                        break
                    # 标题相似度匹配
                    if title_tok and fp['title_tok'] and self.jaccard_similarity(title_tok, fp['title_tok']) >= title_thresh:
                        matched_days.add(day_idx)
                        break
                    # 正文相似度匹配
                    if len(outline) >= 48 and body_tok and fp['body_tok'] and self.jaccard_similarity(body_tok, fp['body_tok']) >= body_thresh:
                        matched_days.add(day_idx)
                        break

            # 判断：出现天数 >= 阈值则为持续热点，保留；否则剔除
            if len(matched_days) >= persistent_days_threshold:
                kept.append(it)  # 持续热点，保留
            elif len(matched_days) > 0:
                dropped += 1  # 有重复但不够持久，剔除
            else:
                kept.append(it)  # 无重复，保留

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

        deduped, dedup_meta = self.dedup(raw_items)
        final, recent_meta = self.dedup_recent(deduped)

        self.save_jsonl(output_file, final)

        return {
            'count': len(final),
            'crawl': crawl_meta,
            'dedup': dedup_meta,
            'recent_summary_dedup': recent_meta,
        }

