#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingest.py — 采集 · 关键词粗筛 · 去重

四步在内存中串行：原始条目 list → 粗筛 list → 篇内去重 list → **剔除近 N 日已在 `output/<date>/summary.json` 产出过的热点** → **仅最后写入** `ingested.jsonl`。
配置与源列表：`kit/engineering.json`（`base_config` 加载）。
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    requests = None  # type: ignore

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from scripts.base_config import (
    FN_SUMMARY,
    load_assembly_config,
    load_dedup_config,
    load_modules_window_hours,
    load_public_feeds_config,
    load_sources_config,
    output_dir_for_date,
)

# =============================================================================
# RSS / 抓取（原 fetch_news）
# =============================================================================


def _local_tag(tag: str) -> str:
    if not tag:
        return ''
    return tag.split('}')[-1] if '}' in tag else tag


def strip_html(raw: Optional[str], limit: int = 4000) -> str:
    if not raw:
        return ''
    text = re.sub(r'<[^>]+>', ' ', raw)
    text = html_module.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:limit]


def parse_pub_date(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    text = text.strip()
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (TypeError, ValueError, OverflowError):
        pass
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def _text(el: Optional[ET.Element]) -> str:
    if el is None:
        return ''
    parts = [el.text or '']
    for c in el:
        parts.append(ET.tostring(c, encoding='unicode'))
    parts.append(el.tail or '')
    raw = ''.join(parts)
    return strip_html(raw, 800)


def parse_rss_atom(xml_bytes: bytes, source_label: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return items

    root_tag = _local_tag(root.tag)
    if root_tag == 'rss':
        for item in root.iter():
            if _local_tag(item.tag) != 'item':
                continue
            title_el = next((c for c in item if _local_tag(c.tag) == 'title'), None)
            link_el = next((c for c in item if _local_tag(c.tag) == 'link'), None)
            desc_el = None
            for c in item:
                lt = _local_tag(c.tag)
                if lt in ('description', 'summary', 'content') or lt == 'encoded':
                    desc_el = c
                    break
            date_el = next(
                (c for c in item if _local_tag(c.tag) in ('pubDate', 'published', 'updated', 'date')),
                None,
            )
            title = _text(title_el)
            link = ''
            if link_el is not None:
                link = (link_el.text or '').strip()
                if not link:
                    link = (link_el.attrib.get('href') or '').strip()
            if not link:
                guid_el = next((c for c in item if _local_tag(c.tag) == 'guid'), None)
                if guid_el is not None:
                    g = (guid_el.text or '').strip()
                    if g.startswith(('http://', 'https://')):
                        link = g
            summary = _text(desc_el)
            pub_raw = (date_el.text or '').strip() if date_el is not None else ''
            pub_dt = parse_pub_date(pub_raw)
            if title and link:
                items.append(
                    _make_item(title, link, source_label, summary, pub_dt, pub_raw)
                )
    elif root_tag == 'feed':
        for entry in root.iter():
            if _local_tag(entry.tag) != 'entry':
                continue
            title_el = next((c for c in entry if _local_tag(c.tag) == 'title'), None)
            title = _text(title_el)
            link = ''
            for c in entry:
                if _local_tag(c.tag) == 'link':
                    href = c.attrib.get('href', '')
                    rel = c.attrib.get('rel', 'alternate')
                    if href and rel in ('alternate', 'self'):
                        link = href
                        break
            if not link:
                for c in entry:
                    if _local_tag(c.tag) == 'link' and c.attrib.get('href'):
                        link = c.attrib.get('href', '')
                        break
            sum_el = next(
                (c for c in entry if _local_tag(c.tag) in ('summary', 'content')),
                None,
            )
            summary = _text(sum_el)
            date_el = next(
                (c for c in entry if _local_tag(c.tag) in ('published', 'updated')),
                None,
            )
            pub_raw = (date_el.text or '').strip() if date_el is not None else ''
            pub_dt = parse_pub_date(pub_raw)
            if title and link:
                items.append(
                    _make_item(title, link, source_label, summary, pub_dt, pub_raw)
                )
    return items


def _make_item(
    title: str,
    link: str,
    source: str,
    summary: str,
    pub_dt: Optional[datetime],
    pub_raw: str,
) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        'title': title,
        'url': link.strip(),
        'source': source,
        'summary': summary,
    }
    if pub_dt:
        item['pub_time'] = pub_dt.isoformat(sep=' ', timespec='seconds')
    if pub_raw:
        item['pub_time_raw'] = pub_raw
    return item


def fetch_url(
    url: str,
    headers: Dict[str, str],
    timeout: float,
    max_retries: int,
    backoff: float,
    verify: bool,
) -> Optional[bytes]:
    if requests is None:
        print('❌ 需要安装 requests: pip install requests')
        return None
    if not verify:
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except Exception:
            pass
    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(
                url,
                headers=headers,
                timeout=timeout,
                verify=verify,
            )
            resp.raise_for_status()
            return resp.content
        except (
            requests.exceptions.Timeout,
            requests.exceptions.SSLError,
            requests.exceptions.ConnectionError,
        ) as e:
            last_err = e
        except requests.exceptions.RequestException as e:
            last_err = e
        if attempt < max_retries - 1:
            time.sleep(backoff * (attempt + 1))
    if last_err:
        print(f'⚠️ 拉取失败 {url} : {last_err}')
    return None


def within_date_window(
    item: Dict[str, Any],
    date_str: str,
    window_hours: int,
) -> bool:
    raw = item.get('pub_time')
    if not raw:
        return True
    try:
        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        return True
    try:
        day = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return True
    center = day.replace(hour=12, minute=0, second=0)
    delta_sec = abs((dt - center).total_seconds())
    return delta_sec <= window_hours * 3600 * 2


def fetch_raw_items(date_str: str, _config: dict) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """步骤 1：拉取 RSS/Atom，返回条目列表（不写文件）。"""
    settings, feeds = load_public_feeds_config()
    timeout = float(settings.get('timeout_seconds', 20))
    max_retries = int(settings.get('max_retries', 3))
    backoff = float(settings.get('retry_backoff_seconds', 1.5))
    per_feed_cap = int(settings.get('max_items_per_feed', 50))
    total_cap = int(settings.get('max_items_total', 800))
    ua = settings.get(
        'user_agent',
        'Mozilla/5.0 (compatible; AIFrontierDaily/1.0)',
    )
    headers = {'User-Agent': ua, 'Accept': 'application/rss+xml, application/xml, text/xml, */*'}

    window_hours = load_modules_window_hours()

    all_items: List[Dict[str, Any]] = []
    seen_url = set()
    errors = 0

    for feed in feeds:
        url = feed.get('url', '').strip()
        source_label = feed.get('source', urlparse(url).netloc or 'unknown')
        verify = feed.get('verify_tls', True)
        if not url:
            continue

        body = fetch_url(url, headers, timeout, max_retries, backoff, verify)
        if body is None:
            errors += 1
            continue

        parsed = parse_rss_atom(body, source_label)
        kept = 0
        for it in parsed:
            if kept >= per_feed_cap:
                break
            u = it.get('url', '')
            if not u or u in seen_url:
                continue
            if not within_date_window(it, date_str, window_hours):
                continue
            seen_url.add(u)
            it['_feed_url'] = url
            all_items.append(it)
            kept += 1

    def sort_key(it: Dict[str, Any]) -> datetime:
        pt = it.get('pub_time')
        if not pt:
            return datetime.min
        try:
            return datetime.fromisoformat(pt.replace('Z', ''))
        except ValueError:
            return datetime.min

    all_items.sort(key=sort_key, reverse=True)
    all_items = all_items[:total_cap]

    meta = {
        'date': date_str,
        'crawl_ts': datetime.now().isoformat(),
        'count': len(all_items),
        'status': 'ok' if all_items else 'empty',
        'feeds_ok': len(feeds) - errors,
        'feeds_failed': errors,
        'note': 'public RSS/Atom only; see kit/engineering.json → public_feeds',
    }
    return all_items, meta


# =============================================================================
# 关键词粗筛（原 keyword_filter）
# =============================================================================


def keyword_match(text, keywords):
    if not text:
        return False
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            return True
    return False


def is_excluded_source(url, excluded_domains):
    if not url:
        return False
    for domain in excluded_domains:
        if domain in url:
            return True
    return False


_DEFAULT_FORBIDDEN = ['/index', '/list', '/channel', '/topic', '/home', '/user', 'page=']


def is_valid_url(url, allowed_patterns, forbidden_patterns=None):
    if not url:
        return False
    for pattern in allowed_patterns:
        if pattern in url:
            return True
    forbidden = forbidden_patterns if forbidden_patterns is not None else _DEFAULT_FORBIDDEN
    for f in forbidden:
        if f in url:
            return False
    return True


def _guess_module(text, module_map):
    text_lower = text.lower()
    for kw, mod_id in module_map.items():
        if kw in text_lower:
            return mod_id
    return 'unknown'


def _contains_excluded_keywords(text: str, exclude_keywords: List[str]) -> bool:
    """检查文本是否包含排除关键词（选题纠偏）"""
    if not text:
        return False
    text_lower = text.lower()
    for kw in exclude_keywords:
        if kw.lower() in text_lower:
            return True
    return False


def filter_items(items: List[Dict[str, Any]], _config: dict) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """步骤 2：关键词与 URL 规则粗筛（纯内存）。"""
    modules_data = load_assembly_config()
    sources_data = load_sources_config()

    all_keywords = []
    module_map = {}
    for m in modules_data.get('modules', []):
        for kw in m.get('keywords', []):
            all_keywords.append(kw)
            k = kw.lower()
            if k not in module_map:
                module_map[k] = m['id']

    excluded = sources_data.get('excluded', [])
    url_patterns = sources_data.get('url_patterns') or {}
    allowed_patterns = url_patterns.get('allowed', [])
    forbidden_patterns = url_patterns.get('forbidden')
    
    # 选题纠偏：排除非 AI 核心内容的关键词
    filter_keywords = sources_data.get('filter_keywords', {})
    exclude_keywords = filter_keywords.get('exclude', [])

    passed_items: List[Dict[str, Any]] = []
    passed = 0
    total = len(items)
    excluded_by_topic = 0

    for item in items:
        title = item.get('title', '')
        url = item.get('url', '')

        if is_excluded_source(url, excluded):
            continue

        if not is_valid_url(url, allowed_patterns, forbidden_patterns):
            continue

        combined_text = f"{title} {item.get('summary', '')} {item.get('content', '')}"
        
        # 选题纠偏：剔除非 AI 核心内容
        if exclude_keywords and _contains_excluded_keywords(combined_text, exclude_keywords):
            excluded_by_topic += 1
            continue

        if keyword_match(combined_text, all_keywords):
            item['_matched_module'] = _guess_module(combined_text, module_map)
            passed_items.append(item)
            passed += 1

    stats = {'count': passed, 'total': total, 'excluded_by_topic': excluded_by_topic}
    return passed_items, stats


# =============================================================================
# 去重（原 dedup）
# =============================================================================


def similarity_tokens(text: str, word_n: int, char_n: int) -> set:
    text = (text or '').lower().strip()
    if not text:
        return set()
    tokens = []
    words = text.split()
    if word_n >= 1 and len(words) >= word_n:
        for i in range(len(words) - word_n + 1):
            tokens.append(' '.join(words[i : i + word_n]))
    if char_n >= 1 and len(text) >= char_n:
        for i in range(len(text) - char_n + 1):
            tokens.append(text[i : i + char_n])
    return set(tokens)


def jaccard_similarity(set_a, set_b):
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


# 近几日已产出条目的指纹（与 output/<date>/summary.json 对照）
_OUTLINE_FINGERPRINT_MAX_CHARS = 1600
_MIN_CHARS_FOR_BODY_DEDUP = 48


def _normalize_url_for_dedup(url: Optional[str]) -> str:
    """归一化 URL，用于与历史 summary 中 `url` 对比（去尾斜杠、小写 host、去 www）。"""
    u = (url or '').strip()
    if not u:
        return ''
    try:
        p = urlparse(u)
        netloc = (p.netloc or '').lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        path = (p.path or '').rstrip('/')
        if not path:
            path = '/'
        return f'{netloc}{path}'.lower()
    except Exception:
        return u.lower()


def _prior_calendar_dates(ingest_date_str: str, n_days: int) -> List[str]:
    base = datetime.strptime(ingest_date_str, '%Y-%m-%d')
    return [(base - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, n_days + 1)]


def _outline_text_from_summary_item(item: Dict[str, Any]) -> str:
    """已产出 `summary.json` 单条：标题 + 摘要/结构化字段，拼成与 RSS 侧可对照的文本。"""
    body = (item.get('summary') or '').strip() or (item.get('_ai_summary') or '').strip()
    parts: List[str] = [x for x in (item.get('title') or '', body) if x]
    for key in ('one_liner', 'plain_explain', 'digest_for_outline'):
        t = item.get(key)
        if t and str(t).strip():
            parts.append(str(t).strip())
    return ' '.join(parts)[:_OUTLINE_FINGERPRINT_MAX_CHARS]


def load_recent_summary_fingerprints(
    ingest_date_str: str, dcfg: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    读取 **ingest 当天之前** 共 `recent_summary_days` 个日历日、各日
    `output/<date>/summary.json` 内 `items`，构造指纹（URL、标题 n-gram、正文 n-gram）。
    """
    if not dcfg.get('recent_summary_enabled', True):
        return [], {'enabled': False, 'fingerprint_count': 0}

    n_days = max(0, int(dcfg.get('recent_summary_days', 7)))
    word_n = int(dcfg['word_ngram_n'])
    char_n = int(dcfg['char_ngram_n'])
    dates = _prior_calendar_dates(ingest_date_str, n_days)
    fps: List[Dict[str, Any]] = []
    by_file: List[Dict[str, Any]] = []

    for d in dates:
        path = os.path.join(output_dir_for_date(d), FN_SUMMARY)
        if not os.path.isfile(path):
            by_file.append({'date': d, 'path': path, 'loaded': 0, 'skip': 'missing'})
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                bundle = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            by_file.append({'date': d, 'path': path, 'loaded': 0, 'skip': str(e)})
            continue
        rows = bundle.get('items')
        if not isinstance(rows, list):
            by_file.append({'date': d, 'path': path, 'loaded': 0, 'skip': 'no_items'})
            continue
        n_loaded = 0
        for it in rows:
            if not isinstance(it, dict):
                continue
            title = (it.get('title') or '').strip()
            outline = _outline_text_from_summary_item(it)
            fps.append(
                {
                    'url_norm': _normalize_url_for_dedup(it.get('url')),
                    'source': (it.get('source') or '').strip(),
                    'title_tok': similarity_tokens(title, word_n, char_n),
                    'body_tok': similarity_tokens(outline, word_n, char_n),
                    'outline_len': len(outline),
                }
            )
            n_loaded += 1
        by_file.append({'date': d, 'path': path, 'loaded': n_loaded})

    meta = {
        'enabled': True,
        'dates_scanned': dates,
        'fingerprint_count': len(fps),
        'by_file': by_file,
    }
    return fps, meta


def _rss_item_overlaps_recent(
    item: Dict[str, Any],
    fingerprints: List[Dict[str, Any]],
    dcfg: Dict[str, Any],
) -> bool:
    """是否与近几日 summary 中任一条目判定为同一热点（URL / 标题 / 正文相似）。"""
    if not fingerprints:
        return False
    word_n = int(dcfg['word_ngram_n'])
    char_n = int(dcfg['char_ngram_n'])
    tt = float(dcfg['recent_summary_title_threshold'])
    tb = float(dcfg['recent_summary_text_threshold'])

    url_n = _normalize_url_for_dedup(item.get('url'))
    title = (item.get('title') or '').strip()
    outline = f'{title} {(item.get("summary") or "")}'.strip()[:_OUTLINE_FINGERPRINT_MAX_CHARS]
    title_tok = similarity_tokens(title, word_n, char_n)
    body_tok = similarity_tokens(outline, word_n, char_n)

    for fp in fingerprints:
        fn = fp.get('url_norm') or ''
        if url_n and fn and url_n == fn:
            return True
        if title_tok and fp.get('title_tok'):
            if jaccard_similarity(title_tok, fp['title_tok']) >= tt:
                return True
        if len(outline) >= _MIN_CHARS_FOR_BODY_DEDUP and body_tok and fp.get('body_tok'):
            olen = int(fp.get('outline_len') or 0)
            if olen >= _MIN_CHARS_FOR_BODY_DEDUP:
                if jaccard_similarity(body_tok, fp['body_tok']) >= tb:
                    return True
    return False


def _count_hot_topic_occurrences(
    item: Dict[str, Any],
    fingerprints: List[Dict[str, Any]],
    dcfg: Dict[str, Any],
) -> int:
    """统计该条目在近几日热点中的出现次数（用于判断是否为连续热门）"""
    if not fingerprints:
        return 0
    word_n = int(dcfg.get('word_ngram_n', 3))
    char_n = int(dcfg.get('char_ngram_n', 3))
    threshold = float(dcfg.get('hot_topic_repeat_threshold', 0.75))

    title = (item.get('title') or '').strip()
    outline = f'{title} {(item.get("summary") or "")}'.strip()[:_OUTLINE_FINGERPRINT_MAX_CHARS]
    title_tok = similarity_tokens(title, word_n, char_n)
    body_tok = similarity_tokens(outline, word_n, char_n)

    count = 0
    for fp in fingerprints:
        if title_tok and fp.get('title_tok'):
            if jaccard_similarity(title_tok, fp['title_tok']) >= threshold:
                count += 1
                continue
        if body_tok and fp.get('body_tok'):
            olen = int(fp.get('outline_len') or 0)
            if olen >= _MIN_CHARS_FOR_BODY_DEDUP:
                if jaccard_similarity(body_tok, fp['body_tok']) >= threshold:
                    count += 1
    return count


def filter_recent_summary_overlap(
    items: List[Dict[str, Any]],
    ingest_date_str: str,
    dcfg: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """剔除与近几日 `output/.../summary.json` 已产出热点重复的条目（在篇内去重之后执行）。
    
    热点逻辑优化：如果一个话题在连续多日出现达到一定次数，视为持续热点，允许再次推送。
    """
    fps, meta = load_recent_summary_fingerprints(ingest_date_str, dcfg)
    if not meta.get('enabled', True) or not fps:
        return items, {**meta, 'dropped': 0, 'kept': len(items)}

    # 热点逻辑配置
    hot_topic_enabled = dcfg.get('hot_topic_enabled', False)
    hot_topic_days = int(dcfg.get('hot_topic_days', 3))
    
    kept: List[Dict[str, Any]] = []
    dropped = 0
    kept_as_hot = 0
    
    for it in items:
        if _rss_item_overlaps_recent(it, fps, dcfg):
            # 热点逻辑：如果是连续多日出现的热门话题，允许再次推送
            if hot_topic_enabled:
                occurrences = _count_hot_topic_occurrences(it, fps, dcfg)
                if occurrences >= hot_topic_days:
                    kept.append(it)
                    kept_as_hot += 1
                    continue
            dropped += 1
            continue
        kept.append(it)

    return kept, {**meta, 'dropped': dropped, 'kept': len(kept), 'kept_as_hot': kept_as_hot}


def dedup_items(items: List[Dict[str, Any]], _config: dict) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """步骤 3：URL 精确去重 + 标题模糊去重（纯内存）。"""
    dcfg = load_dedup_config()
    threshold = float(dcfg['title_similarity_threshold'])
    word_n = int(dcfg['word_ngram_n'])
    char_n = int(dcfg['char_ngram_n'])

    seen_urls = set()
    url_to_tokens = {}
    passed: List[Dict[str, Any]] = []

    for item in items:
        url = item.get('url', '')
        title = item.get('title', '')

        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        title_tokens = similarity_tokens(title, word_n, char_n)
        is_duplicate = False
        for _cached_url, cached_tokens in url_to_tokens.items():
            sim = jaccard_similarity(title_tokens, cached_tokens)
            if sim > threshold:
                is_duplicate = True
                break

        if is_duplicate:
            continue

        if title:
            url_to_tokens[url] = title_tokens
        passed.append(item)

    stats = {'count': len(passed)}
    return passed, stats


def run_ingest(date_str: str, config: dict, output_file: str) -> Dict[str, Any]:
    """抓取 → 粗筛 → 篇内去重 → 近几日 summary 对照剔除，只在结尾写入 `output_file` 一次。"""
    raw_items, crawl_meta = fetch_raw_items(date_str, config)
    filtered, filter_stats = filter_items(raw_items, config)
    deduped, dedup_stats = dedup_items(filtered, config)

    dcfg = load_dedup_config()
    recent_filtered, recent_meta = filter_recent_summary_overlap(deduped, date_str, dcfg)

    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as fout:
        for it in recent_filtered:
            fout.write(json.dumps(it, ensure_ascii=False) + '\n')

    return {
        'count': recent_meta.get('kept', len(recent_filtered)),
        'crawl': crawl_meta,
        'filter': filter_stats,
        'dedup': dedup_stats,
        'recent_summary_dedup': recent_meta,
    }


# =============================================================================
# CLI
# =============================================================================


def main(argv: Optional[List[str]] = None) -> None:
    from scripts.base_config import default_day_paths

    argv = argv if argv is not None else sys.argv[1:]
    today = datetime.now().strftime('%Y-%m-%d')
    parser = argparse.ArgumentParser(description='RSS 抓取 → 粗筛 → 去重 → ingested.jsonl')
    parser.add_argument('--date', '-d', default=today, help='日期 YYYY-MM-DD（默认今天）')
    parser.add_argument(
        '-o',
        '--output',
        default=None,
        help='输出 JSONL（默认 output/<date>/ingested.jsonl）',
    )
    args = parser.parse_args(argv)
    date_str = args.date
    cfg: dict = {}
    out = args.output or default_day_paths(date_str)['ingested']

    r = run_ingest(date_str, cfg, out)
    recent = r.get('recent_summary_dedup') or {}
    print(
        f"Done. ingested={r['count']}, "
        f"crawl_status={r['crawl'].get('status')}, "
        f"feeds_failed={r['crawl'].get('feeds_failed', 0)}, "
        f"recent_summary_dropped={recent.get('dropped', 0)}"
    )


if __name__ == '__main__':
    main()
