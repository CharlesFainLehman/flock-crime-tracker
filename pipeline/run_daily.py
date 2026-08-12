"""Daily pipeline: discover -> classify -> dedupe -> save -> rebuild site."""

import anthropic

from build_site import build_site
from fetch import discover_daily
from process import process_candidates
from store import load_seen_urls, load_stories, save_seen_urls, save_stories


def main() -> None:
    client = anthropic.Anthropic()
    stories = load_stories()
    seen = load_seen_urls()

    print("Discovering candidates...")
    candidates = discover_daily(days_back=3)
    print(f"Found {len(candidates)} candidate URLs "
          f"({sum(1 for c in candidates if c['url'] in seen)} already seen)\n")

    counts = process_candidates(client, candidates, stories, seen)

    save_stories(stories)
    save_seen_urls(seen)
    build_site()

    print(f"\nDone. New: {counts['new']}, duplicates: {counts['duplicates']}, "
          f"rejected: {counts['rejected']}, already seen: {counts['skipped_seen']}, "
          f"errors: {counts['errors']}. Database now has {len(stories)} incidents.")


if __name__ == "__main__":
    main()
