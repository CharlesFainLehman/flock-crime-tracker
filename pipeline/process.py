"""Shared candidate-processing loop used by the daily run and the backfill."""

import re

import anthropic

from classify import classify_article
from dedupe import check_duplicate
from fetch import fetch_article_text, is_vendor_or_wire, resolve_candidate
from store import make_row, next_story_id

_VARIANT_SEGMENTS = ("/gallery/", "/newsletter/gallery/", "/newsletter/", "/amp/", "/photos/")

# Query parameters that never identify an article. Everything else is KEPT:
# some sites key articles entirely by query string (woodlandsonline.com
# story.cfm?nppage=N, ktbb.com/post/?p=N, auroragov.org ...&pageId=N), so
# stripping the whole query made every article on those sites "the same URL"
# and silently dropped real stories as duplicates.
_TRACKING_PARAMS = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "ref",
                    "ito", "share", "outputType", "taid", "cmpid")


def canonical_url(url: str) -> str:
    """Normalize an article URL for duplicate comparison: lowercase, drop the
    fragment and tracking parameters, and collapse syndication path variants
    (/gallery/, /amp/, ...) so the same article compares equal."""
    u = url.split("#")[0].strip().lower()
    base, _, query = u.partition("?")
    base = base.rstrip("/")
    for seg in _VARIANT_SEGMENTS:
        base = base.replace(seg, "/")
    if query:
        kept = [kv for kv in query.split("&")
                if kv and not any(kv.startswith(t) for t in _TRACKING_PARAMS)]
        if kept:
            return base + "?" + "&".join(sorted(kept))
    return base


_DATED_PATH_RE = re.compile(r"/\d{4}/\d{2}/\d{2}/[^/?]+$")


def syndication_path(url: str) -> str | None:
    """The /YYYY/MM/DD/slug tail of a canonical URL, if it has one. Chains
    (e.g. Sound Publishing's Puget Sound weeklies) republish one article at
    the same dated path on many sibling hostnames; a date plus slug is
    specific enough to identify the article across hosts, where full-URL
    canonicalization cannot."""
    m = _DATED_PATH_RE.search(canonical_url(url).partition("?")[0])
    return m.group(0) if m else None


def process_candidates(client: anthropic.Anthropic, candidates: list[dict],
                       stories: list[dict], seen_urls: set[str]) -> dict:
    """Classify candidates and append qualifying, non-duplicate rows to stories.

    Mutates `stories` and `seen_urls` in place. Returns counts for logging.
    """
    counts = {"new": 0, "duplicates": 0, "rejected": 0, "skipped_seen": 0, "errors": 0}
    # Canonical forms of everything already stored, to catch same-article URL variants.
    stored = {canonical_url(s_["source_url"]) for s_ in stories}
    stored |= {canonical_url(u) for s_ in stories for u in s_.get("additional_sources", "").split() if u}
    # Dated-path forms, to catch the same article syndicated across hostnames.
    stored_paths = {p for s_ in stories
                    for u in [s_["source_url"], *s_.get("additional_sources", "").split()]
                    for p in [syndication_path(u)] if p}

    for i, candidate in enumerate(candidates, 1):
        if candidate["url"] in seen_urls:
            counts["skipped_seen"] += 1
            continue
        resolve_candidate(candidate)  # decode Google News redirects
        url = candidate["url"]
        # Only now is a Google redirect's real domain visible. Vendor press
        # releases are rejected by validate_data.py, so drop them before they
        # can be written to the CSV.
        if is_vendor_or_wire(url):
            seen_urls.add(url)
            if candidate.get("google_url"):
                seen_urls.add(candidate["google_url"])
            counts["rejected"] += 1
            continue
        if canonical_url(url) in stored:   # same article, different URL form
            seen_urls.add(url)
            counts["duplicates"] += 1
            continue
        path = syndication_path(url)
        if path and path in stored_paths:  # same article, syndicated on a sibling host
            seen_urls.add(url)
            counts["duplicates"] += 1
            continue
        if url in seen_urls:
            seen_urls.add(candidate.get("google_url", url))
            counts["skipped_seen"] += 1
            continue

        print(f"[{i}/{len(candidates)}] {candidate['title'][:90]}")
        try:
            text = fetch_article_text(url)
            cls = classify_article(client, candidate, text)
        except Exception as e:
            # Never mark seen on errors: the article must be retried next run.
            print(f"  error, skipping (will retry next run): {e}")
            counts["errors"] += 1
            continue

        seen_urls.add(url)
        if candidate.get("google_url"):
            seen_urls.add(candidate["google_url"])

        if not cls or not cls.qualifies:
            reason = cls.reason if cls else "no classification"
            print(f"  rejected: {reason[:100]}")
            counts["rejected"] += 1
            continue

        row = make_row(next_story_id(stories), cls, candidate)
        try:
            dup_id = check_duplicate(client, row, stories)
        except anthropic.APIError:
            dup_id = None
        if dup_id:
            for s in stories:
                if s["id"] == dup_id:
                    extra = s.get("additional_sources", "")
                    urls = [u for u in extra.split(" ") if u]
                    if url not in urls and url != s.get("source_url"):
                        urls.append(url)
                        s["additional_sources"] = " ".join(urls)
            if path:
                stored_paths.add(path)
            print(f"  duplicate of id {dup_id}")
            counts["duplicates"] += 1
            continue

        stories.append(row)
        stored.add(canonical_url(url))
        if path:
            stored_paths.add(path)
        print(f"  ADDED: {row['city']}, {row['state']} | {row['crime_type']} | {row['outcome']}")
        counts["new"] += 1

    return counts
