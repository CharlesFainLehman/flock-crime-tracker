"""Shared candidate-processing loop used by the daily run and the backfill."""

import anthropic

from classify import classify_article
from dedupe import check_duplicate
from fetch import fetch_article_text, resolve_candidate
from store import make_row, next_story_id


def process_candidates(client: anthropic.Anthropic, candidates: list[dict],
                       stories: list[dict], seen_urls: set[str]) -> dict:
    """Classify candidates and append qualifying, non-duplicate rows to stories.

    Mutates `stories` and `seen_urls` in place. Returns counts for logging.
    """
    counts = {"new": 0, "duplicates": 0, "rejected": 0, "skipped_seen": 0, "errors": 0}

    for i, candidate in enumerate(candidates, 1):
        if candidate["url"] in seen_urls:
            counts["skipped_seen"] += 1
            continue
        resolve_candidate(candidate)  # decode Google News redirects
        url = candidate["url"]
        if url in seen_urls:
            seen_urls.add(candidate.get("google_url", url))
            counts["skipped_seen"] += 1
            continue

        print(f"[{i}/{len(candidates)}] {candidate['title'][:90]}")
        try:
            text = fetch_article_text(url)
            cls = classify_article(client, candidate, text)
        except anthropic.APIError as e:
            print(f"  API error, skipping (will retry next run): {e}")
            counts["errors"] += 1
            continue
        except Exception as e:
            print(f"  error, marking seen: {e}")
            seen_urls.add(url)
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
            print(f"  duplicate of id {dup_id}")
            counts["duplicates"] += 1
            continue

        stories.append(row)
        print(f"  ADDED: {row['city']}, {row['state']} | {row['crime_type']} | {row['outcome']}")
        counts["new"] += 1

    return counts
