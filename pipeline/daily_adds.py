"""Ledger of stories added per day by the daily pipeline (data/daily_adds.csv).

The ledger is the source of truth for the site's "stories added per day"
chart. Bulk events — the launch seed, backfills, candidate imports, review
sweeps — never touch it, so it isolates the daily cadence from one-off
database surgery. run_daily.py records each run's new-story count here.

`python daily_adds.py --rebuild` regenerates the ledger from git history
instead: it walks every commit to data/stories.csv whose subject matches
"Daily update YYYY-MM-DD" and counts the record ids each one introduced.
That needs full history (the Actions checkout is shallow), so rebuilds are
a local maintenance tool, not part of the automated pipeline. Known limit:
history before the 2026-08-15 squash is invisible to a rebuild, and the
2026-08-15 morning run is folded into that day's backfill, so 08-15 is a
slight undercount.
"""

import csv
import io
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date

from config import DATA_DIR

DAILY_ADDS_CSV = DATA_DIR / "daily_adds.csv"
STORIES_REL = "data/stories.csv"  # repo-relative, for git commands

# Verified adjustments applied on top of raw git-derived counts. 2026-08-19:
# the daily run raced the candidate import (still on its own branch), so 4 of
# its 13 adds (ids 918, 919, 924, 927 in commit 781eea4) duplicated stories
# the import captured independently; dedupe would have caught them any other
# day. Verified by tracing every daily-added row's source_url into main.
REBUILD_CORRECTIONS = {
    "2026-08-19": -4,
    # Nine syndicated copies of one undated Covington, WA story (rows
    # 2189-2197) each missed their just-added twin in the dedupe shortlist;
    # 10 recorded adds were really 2 stories.
    "2026-08-29": -8,
    # Two 2026-09-02 adds repeated existing stories: 2207 duplicated 2163
    # (Marshall, TX Whataburger homicide; the older row's month-only date put
    # it outside the 21-day candidate window) and 2208 duplicated 2202 (Rusk
    # County, TX assault; the older row had no city or name, so the model
    # judged them different). Merged into 2163 and 2202.
    "2026-09-02": -2,
    # 2225 duplicated 2209 (Moody, AL kidnapping): the follow-up article's
    # new details (brother, Tuscaloosa origin) read as a different incident
    # to the dedupe model. Merged into 2209 (issue #19).
    "2026-09-05": -1,
}


def load_daily_adds() -> list[dict]:
    if not DAILY_ADDS_CSV.exists():
        return []
    with open(DAILY_ADDS_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _save(rows: list[dict]) -> None:
    DAILY_ADDS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(DAILY_ADDS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "added"])
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["date"]))


def record_run(added: int) -> None:
    """Add today's new-story count to the ledger (cumulative across re-runs)."""
    today = date.today().isoformat()
    rows = load_daily_adds()
    for r in rows:
        if r["date"] == today:
            r["added"] = str(int(r["added"]) + added)
            break
    else:
        rows.append({"date": today, "added": str(added)})
    _save(rows)


def _git(*args: str) -> str:
    repo_root = DATA_DIR.parent
    return subprocess.run(["git", "-C", str(repo_root), *args],
                          capture_output=True, text=True, check=True).stdout


def _ids_at(commit: str) -> set[str]:
    try:
        out = _git("show", f"{commit}:{STORIES_REL}")
    except subprocess.CalledProcessError:  # file absent at this commit
        return set()
    return {r["id"] for r in csv.DictReader(io.StringIO(out)) if r.get("id")}


def rebuild_from_git() -> None:
    """Regenerate the ledger from 'Daily update' commits. Needs full history."""
    log = _git("log", "HEAD", "--format=%H|%s", "--", STORIES_REL).strip()
    per_day: dict[str, int] = defaultdict(int)
    for line in log.splitlines():
        commit, subject = line.split("|", 1)
        m = re.match(r"Daily update (\d{4}-\d{2}-\d{2})", subject)
        if not m:
            continue
        per_day[m.group(1)] += len(_ids_at(commit) - _ids_at(commit + "^"))
    if not per_day:
        sys.exit("No 'Daily update' commits found — is this a shallow clone?")
    for day, delta in REBUILD_CORRECTIONS.items():
        if day in per_day:
            per_day[day] += delta
    _save([{"date": d, "added": str(n)} for d, n in per_day.items()])
    print(f"Rebuilt {DAILY_ADDS_CSV.name}: {len(per_day)} days, "
          f"{sum(per_day.values())} stories "
          f"({min(per_day)} to {max(per_day)})")


if __name__ == "__main__":
    if "--rebuild" in sys.argv:
        rebuild_from_git()
    else:
        sys.exit("Usage: python daily_adds.py --rebuild\n"
                 "(record_run() is called from run_daily.py; the rebuild "
                 "re-derives the ledger from git history)")
