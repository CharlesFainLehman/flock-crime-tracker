"""Discover candidate news articles about Flock cameras.

Two sources:
  - GDELT DOC 2.0 API: free full-text news search with direct article URLs.
    Works for both daily updates and historical backfill (coverage to 2017).
  - Google News RSS: catches smaller local outlets GDELT sometimes misses.
    Google wraps links in redirect URLs; we decode the older base64 format
    when possible and otherwise keep the Google link as the source URL.
"""

import base64
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import feedparser
import requests
import trafilatura
from googlenewsdecoder import gnewsdecoder

from config import SEARCH_QUERIES

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) FlockTracker/1.0"

# Domains that produce noise, not news coverage.
SKIP_DOMAINS = ("flocksafety.com", "prnewswire.com", "businesswire.com",
                "globenewswire.com", "streetinsider.com")


def _normalize(candidate: dict) -> dict:
    candidate["url"] = candidate["url"].strip()
    candidate["title"] = re.sub(r"\s+", " ", candidate.get("title", "")).strip()
    return candidate


def gdelt_search(query: str, start: datetime, end: datetime, max_records: int = 250) -> list[dict]:
    """Full-text search of GDELT's news archive for a date window."""
    params = {
        "query": f'{query} sourcelang:english',
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(max_records),
        "sort": "datedesc",
        "startdatetime": start.strftime("%Y%m%d%H%M%S"),
        "enddatetime": end.strftime("%Y%m%d%H%M%S"),
    }
    articles = None
    for attempt in range(3):
        try:
            resp = requests.get(GDELT_DOC_API, params=params,
                                headers={"User-Agent": USER_AGENT}, timeout=30)
            if resp.status_code == 429:
                time.sleep(45 * (attempt + 1))
                continue
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            break
        except (requests.RequestException, ValueError) as e:
            print(f"  GDELT error for {query!r}: {e}")
            time.sleep(10)
    if articles is None:
        print(f"  GDELT gave up on {query!r}")
        return []

    out = []
    for a in articles:
        domain = a.get("domain", "")
        if any(skip in domain for skip in SKIP_DOMAINS):
            continue
        seendate = a.get("seendate", "")  # e.g. 20250811T120000Z
        published = ""
        if len(seendate) >= 8:
            published = f"{seendate[:4]}-{seendate[4:6]}-{seendate[6:8]}"
        out.append(_normalize({
            "url": a.get("url", ""),
            "title": a.get("title", ""),
            "source": domain,
            "published": published,
            "snippet": "",
        }))
    return out


def _decode_google_news_url(url: str) -> str | None:
    """Best-effort decode of a Google News redirect URL to the real article URL.

    Older-format IDs base64-decode to a payload containing the URL. Newer
    opaque IDs can't be decoded offline; return None for those.
    """
    m = re.search(r"news\.google\.com/rss/articles/([^?/]+)", url)
    if not m:
        return None
    try:
        raw = base64.urlsafe_b64decode(m.group(1) + "==")
        text = raw.decode("latin-1", errors="ignore")
        urls = re.findall(r"https?://[^\x00-\x1f\x7f-\xff\"]+", text)
        for u in urls:
            if "news.google.com" not in u:
                return u.rstrip("R")
    except Exception:
        pass
    return None


def google_news_search(query: str) -> list[dict]:
    feed_url = ("https://news.google.com/rss/search?q="
                f"{quote(query)}&hl=en-US&gl=US&ceid=US:en")
    feed = feedparser.parse(feed_url)
    out = []
    for entry in feed.entries:
        link = entry.get("link", "")
        decoded = _decode_google_news_url(link)
        source = entry.get("source", {}).get("title", "")
        published = ""
        if entry.get("published_parsed"):
            published = time.strftime("%Y-%m-%d", entry.published_parsed)
        snippet = re.sub(r"<[^>]+>", " ", entry.get("summary", ""))
        out.append(_normalize({
            "url": decoded or link,
            "title": entry.get("title", ""),
            "source": source,
            "published": published,
            "snippet": snippet,
        }))
    return out


def discover_daily(days_back: int = 3) -> list[dict]:
    """All candidates from the last `days_back` days, both sources, deduped by URL."""
    end = datetime.now(timezone.utc).replace(tzinfo=None)
    start = end - timedelta(days=days_back)
    candidates: dict[str, dict] = {}
    for q in SEARCH_QUERIES:
        for c in gdelt_search(q, start, end):
            candidates.setdefault(c["url"], c)
        time.sleep(6)  # GDELT asks for ~1 request per 5s
    for q in SEARCH_QUERIES:
        for c in google_news_search(q):
            candidates.setdefault(c["url"], c)
        time.sleep(1)
    return list(candidates.values())


def resolve_candidate(candidate: dict) -> None:
    """Decode a Google News redirect URL to the real article URL, in place.

    Keeps the original under `google_url` so both can be marked seen. No-op
    for non-Google URLs or when decoding fails.
    """
    url = candidate["url"]
    if "news.google.com" not in url:
        return
    try:
        res = gnewsdecoder(url, interval=1)
        decoded = res.get("decoded_url") if res.get("status") else None
        if decoded and "news.google.com" not in decoded:
            candidate["google_url"] = url
            candidate["url"] = decoded.strip()
    except Exception:
        pass


def fetch_article_text(url: str, max_chars: int = 12000) -> str | None:
    """Download and extract the main text of an article. None on failure."""
    if "news.google.com" in url:
        return None  # undecoded redirect; caller falls back to title/snippet
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        text = trafilatura.extract(downloaded, include_comments=False)
        if text and len(text) > 200:
            return text[:max_chars]
    except Exception:
        pass
    return None
