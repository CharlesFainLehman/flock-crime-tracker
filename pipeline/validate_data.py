"""Validate data/ integrity before any workflow commit.

Exits non-zero if a JSON file fails to parse, a CSV contains git conflict
markers, or story/court ids collide — so corruption can never be committed.
"""

import csv
import json
import sys

from config import DATA_DIR

MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


def fail(msg: str) -> None:
    sys.exit(f"DATA VALIDATION FAILED: {msg}")


def main() -> None:
    for p in DATA_DIR.glob("*.json"):
        try:
            json.load(open(p, encoding="utf-8"))
        except json.JSONDecodeError as e:
            fail(f"{p.name} is not valid JSON: {e}")

    for p in DATA_DIR.glob("*.csv"):
        text = p.read_text(encoding="utf-8")
        for m in MARKERS:
            if any(line.startswith(m) for line in text.splitlines()):
                fail(f"{p.name} contains git conflict marker {m!r}")
        rows = list(csv.DictReader(open(p, newline="", encoding="utf-8")))
        from datetime import date, timedelta
        horizon = (date.today() + timedelta(days=2)).isoformat()
        for r in rows:
            for field in ("incident_date", "date_filed"):
                v = (r.get(field) or "")
                if v and v[:10] > horizon:
                    fail(f"{p.name} id {r.get('id')}: {field} {v!r} is in the future")
        if p.name == "stories.csv":
            import re
            vendor = re.compile(r"globenewswire|flocksafety\.com|prnewswire|businesswire|"
                               r"press_release|online_features|tmt-newswire", re.I)
            bad = [r["id"] for r in rows if vendor.search(r.get("source_url", ""))]
            if bad:
                fail(f"{p.name}: vendor/press-release primary source on ids {bad[:8]} — re-source or remove")
        ids = [r["id"] for r in rows if r.get("id")]
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})[:5]
            fail(f"{p.name} has duplicate ids: {dupes}")

    print("data validation OK")


if __name__ == "__main__":
    main()
