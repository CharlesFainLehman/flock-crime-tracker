"""Run an externally supplied candidate list through the standard pipeline.

Usage: python pipeline/import_candidates.py <candidates.json> [--limit N]

Each candidate: {url, title, source, published, snippet}. Reuses the exact
classify -> dedupe -> append path the daily job uses, so imported rows meet
the same bar. Checkpoints data/ every 100 candidates and logs a progress
line so long runs are observable.
"""

import argparse
import json
import sys
import time

import anthropic

from process import process_candidates
from progress import push_progress
from store import load_seen_urls, load_stories, save_seen_urls, save_stories


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--chunk", type=int, default=100)
    ap.add_argument("--push-progress", action="store_true")
    args = ap.parse_args()

    cands = json.load(open(args.candidates))
    if args.limit:
        cands = cands[: args.limit]
    client = anthropic.Anthropic()
    stories = load_stories()
    seen = load_seen_urls()
    n0 = len(stories)
    totals = {"new": 0, "duplicates": 0, "rejected": 0, "skipped_seen": 0, "errors": 0}
    t0 = time.monotonic()

    for i in range(0, len(cands), args.chunk):
        chunk = cands[i : i + args.chunk]
        counts = process_candidates(client, chunk, stories, seen)
        for k in totals:
            totals[k] += counts.get(k, 0)
        save_stories(stories)
        save_seen_urls(seen)
        done = min(i + args.chunk, len(cands))
        el = int(time.monotonic() - t0)
        line = (f"PROGRESS {done}/{len(cands)} | +{totals['new']} new, "
                f"{totals['duplicates']} dup, {totals['rejected']} rejected, "
                f"{totals['errors']} err | {el}s")
        print(f"=== {line} ===", flush=True)
        if args.push_progress:
            push_progress(f"Import progress: {line}")

    print(f"\nIMPORT DONE: {n0} -> {len(stories)} stories. {totals}")


if __name__ == "__main__":
    main()
