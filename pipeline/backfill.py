"""One-time historical backfill from GDELT (run locally, not in CI).

Sweeps month-by-month from START_YEAR to the present, running each month's
candidates through the same classify/dedupe path as the daily job. Progress is
checkpointed via seen_urls.json, so the script is safe to interrupt and rerun.

Usage:
    python backfill.py [--start 2017-01] [--end 2026-08]
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import anthropic

from build_site import build_site
from config import SEARCH_QUERIES
from fetch import gdelt_search
from process import process_candidates
from store import load_seen_urls, load_stories, save_seen_urls, save_stories

START_YEAR = 2017


def month_range(start: datetime, end: datetime):
    cur = start.replace(day=1)
    while cur <= end:
        if cur.month == 12:
            nxt = cur.replace(year=cur.year + 1, month=1)
        else:
            nxt = cur.replace(month=cur.month + 1)
        yield cur, min(nxt - timedelta(seconds=1), end)
        cur = nxt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=f"{START_YEAR}-01")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    parser.add_argument("--end", default=now.strftime("%Y-%m"))
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m")
    end_month = datetime.strptime(args.end, "%Y-%m")
    end = min(now, end_month.replace(day=28) + timedelta(days=4))

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set; refusing to run.")
    client = anthropic.Anthropic()
    stories = load_stories()
    seen = load_seen_urls()

    for m_start, m_end in month_range(start, end):
        label = m_start.strftime("%Y-%m")
        candidates: dict[str, dict] = {}
        for q in SEARCH_QUERIES:
            for c in gdelt_search(q, m_start, m_end):
                candidates.setdefault(c["url"], c)
            time.sleep(6)
        fresh = [c for c in candidates.values() if c["url"] not in seen]
        print(f"\n=== {label}: {len(candidates)} candidates, {len(fresh)} new ===")
        if not fresh:
            continue

        counts = process_candidates(client, fresh, stories, seen)

        # Checkpoint after every month so an interrupted run loses little work.
        save_stories(stories)
        save_seen_urls(seen)
        print(f"=== {label} done: +{counts['new']} incidents "
              f"(total {len(stories)}) ===")

    build_site()
    print(f"\nBackfill complete. Database has {len(stories)} incidents.")


if __name__ == "__main__":
    main()
