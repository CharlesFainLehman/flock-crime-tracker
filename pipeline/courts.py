"""Sweep CourtListener for court filings and opinions mentioning Flock cameras.

Searches the RECAP archive (federal PACER documents) and published opinions via
the CourtListener v4 search API, classifies hits with Claude, and maintains
data/court_records.csv. Runs weekly (filings move slower than news); a full
sweep with no date floor runs when --full is passed.

Requires COURTLISTENER_TOKEN and ANTHROPIC_API_KEY.
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import date, timedelta
from typing import Literal, Optional

import anthropic
import requests
from pydantic import BaseModel

from config import CLASSIFY_MODEL, CRIME_TYPES, DATA_DIR
from progress import push_progress
from store import load_stories

SEARCH_API = "https://www.courtlistener.com/api/rest/v4/search/"
BASE = "https://www.courtlistener.com"
COURT_CSV = DATA_DIR / "court_records.csv"
SEEN_JSON = DATA_DIR / "seen_court_ids.json"

COURT_QUERIES = ['"flock safety"', '"flock camera"', '"flock cameras"']

COURT_COLUMNS = [
    "id", "date_added", "record_type", "case_name", "court", "state",
    "date_filed", "crime_type", "flock_role", "summary", "source_url",
    "matched_story_id", "confidence",
]


def _headers() -> dict:
    return {"Authorization": f"Token {os.environ['COURTLISTENER_TOKEN']}"}


def _get(url: str, params: dict | None = None) -> dict:
    last_exc: Exception | None = None
    for attempt in range(5):
        try:
            resp = requests.get(url, params=params, headers=_headers(), timeout=60)
            if resp.status_code == 429:
                # Honor Retry-After; CourtListener throttles per-hour, so waits
                # here are long by design.
                wait = int(resp.headers.get("Retry-After") or 60 * (attempt + 1))
                print(f"  CourtListener 429; waiting {wait}s")
                time.sleep(min(wait, 600))
                continue
            resp.raise_for_status()
            return resp.json()
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
            time.sleep(15 * (attempt + 1))
    raise last_exc or RuntimeError(f"CourtListener rate-limited: {url}")


def search(result_type: str, query: str, filed_after: str | None,
           max_pages: int = 30) -> list[dict]:
    """Paginate the v4 search API. result_type: 'r' (RECAP) or 'o' (opinions)."""
    params: dict | None = {"q": query, "type": result_type,
                           "order_by": "dateFiled desc"}
    if filed_after and params:
        params["filed_after"] = filed_after
    url = SEARCH_API
    out: list[dict] = []
    for _ in range(max_pages):
        data = _get(url, params)
        out.extend(data.get("results", []))
        url = data.get("next")
        params = None
        if not url:
            break
        time.sleep(1)
    return out


def _get_light(url: str, params: dict) -> dict:
    """Single-retry fetch for optional enrichment (document text). Text fetches
    must never stall the sweep — the classifier falls back to the snippet."""
    for attempt in range(2):
        try:
            resp = requests.get(url, params=params, headers=_headers(), timeout=30)
            if resp.status_code == 429:
                time.sleep(20)
                continue
            resp.raise_for_status()
            return resp.json()
        except (requests.Timeout, requests.ConnectionError):
            continue
    return {}


def fetch_recap_text(doc_id: int, max_chars: int = 12000) -> str:
    data = _get_light(f"{BASE}/api/rest/v4/recap-documents/{doc_id}/",
                      {"fields": "plain_text"})
    return (data.get("plain_text") or "")[:max_chars]


def fetch_opinion_text(cluster_id: int, max_chars: int = 12000) -> str:
    data = _get_light(f"{BASE}/api/rest/v4/opinions/",
                      {"cluster__id": cluster_id, "fields": "plain_text"})
    results = data.get("results", [])
    return (results[0].get("plain_text") or "")[:max_chars] if results else ""


def collect_candidates(filed_after: str | None) -> tuple[list[dict], int]:
    """Flatten search results into per-document candidates with stable keys.
    Returns (candidates, failed_search_count)."""
    failed = 0
    candidates: dict[str, dict] = {}
    for q in COURT_QUERIES:
        try:
            recap_results = search("r", q, filed_after)
        except Exception as e:
            print(f"  search failed for {q!r} (type=r), continuing: {e}")
            failed += 1
            recap_results = []
        for r in recap_results:
            for doc in r.get("recap_documents", []) or []:
                key = f"r{doc.get('id')}"
                url = BASE + (doc.get("absolute_url") or r.get("absolute_url") or "")
                candidates.setdefault(key, {
                    "key": key, "kind": "recap", "doc_id": doc.get("id"),
                    "case_name": r.get("caseName", ""),
                    "court": r.get("court", ""),
                    "date_filed": doc.get("entry_date_filed") or r.get("dateFiled") or "",
                    "description": doc.get("description", ""),
                    "snippet": doc.get("snippet", ""),
                    "url": url,
                })
        time.sleep(2)
        try:
            opinion_results = search("o", q, filed_after)
        except Exception as e:
            print(f"  search failed for {q!r} (type=o), continuing: {e}")
            failed += 1
            opinion_results = []
        for r in opinion_results:
            key = f"o{r.get('cluster_id')}"
            candidates.setdefault(key, {
                "key": key, "kind": "opinion", "doc_id": r.get("cluster_id"),
                "case_name": r.get("caseName", ""),
                "court": r.get("court", ""),
                "date_filed": r.get("dateFiled") or "",
                "description": "court opinion",
                "snippet": (r.get("opinions") or [{}])[0].get("snippet", "")
                           if r.get("opinions") else r.get("snippet", ""),
                "url": BASE + (r.get("absolute_url") or ""),
            })
        time.sleep(2)
    return list(candidates.values()), failed


class CourtClassification(BaseModel):
    qualifies: bool
    reason: str
    record_type: Literal["warrant/affidavit", "complaint/indictment",
                         "suppression motion", "court order/opinion", "other"] = "other"
    state: Optional[str] = None  # two-letter code, blank for federal appellate
    crime_type: Optional[str] = None
    flock_role: Optional[str] = None
    summary: Optional[str] = None
    confidence: Literal["high", "medium", "low"] = "low"


COURT_SYSTEM_PROMPT = f"""You classify court documents for a public database tracking cases where Flock Safety cameras (automatic license plate readers) were used in criminal investigations or prosecutions.

A document QUALIFIES if it shows Flock camera evidence being used in the investigation or prosecution of a specific crime: search-warrant applications or affidavits citing Flock hits, criminal complaints or indictments describing Flock evidence, suppression motions or rulings about Flock evidence gathered in a specific case (these qualify: they show the cameras were used investigatively, whatever the motion's outcome), and opinions discussing Flock evidence in a specific prosecution.

A document does NOT qualify if it is:
- A civil suit about Flock privacy, surveillance policy, or the company itself
- A contract, procurement, or municipal dispute involving Flock
- A case where Flock appears only in boilerplate or an unrelated aside

Field guidance:
- state: two-letter code of the state where the underlying crime occurred (infer from the court/district when clear); blank if not inferable.
- crime_type: best fit from: {", ".join(CRIME_TYPES)}.
- flock_role: one short phrase, e.g. "LPR hits placed suspect vehicle near scene".
- summary: 1-2 factual sentences: the case, the crime, and how Flock evidence figured in it.
- confidence: "high" only when working from substantial document text; "low" when from a snippet.

Always give a one-sentence reason."""


def classify_document(client: anthropic.Anthropic, cand: dict, text: str) -> CourtClassification:
    body = f"Document text (excerpt):\n\n{text}" if text.strip() else \
        f"Full text unavailable. Search snippet:\n\n{cand['snippet']}"
    user_msg = (
        f"Case: {cand['case_name']}\nCourt: {cand['court']}\n"
        f"Filed: {cand['date_filed']}\nDocument: {cand['description']}\n\n{body}"
    )
    response = client.messages.parse(
        model=CLASSIFY_MODEL, max_tokens=1024, system=COURT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        output_format=CourtClassification,
    )
    return response.parsed_output


class StoryMatch(BaseModel):
    matches: bool
    story_id: Optional[str] = None


def match_news_story(client: anthropic.Anthropic, row: dict, stories: list[dict]) -> str:
    """Best-effort link from a court record to an existing news incident."""
    pool = [s for s in stories
            if s.get("state") == row["state"] and row["state"]
            and (s.get("crime_type") == row["crime_type"] or not row["crime_type"])][:25]
    if not pool:
        return ""
    existing = "\n".join(
        f"- id {s['id']}: {s['incident_date']} | {s['city']}, {s['state']} | "
        f"{s['crime_type']} | {s['summary']}" for s in pool)
    try:
        response = client.messages.parse(
            model=CLASSIFY_MODEL, max_tokens=256,
            system=("Decide whether this court record concerns the same real-world "
                    "incident as one of the news-database entries. Filings often "
                    "postdate the incident by weeks or months. If unsure, say no."),
            messages=[{"role": "user", "content":
                       f"News entries:\n{existing}\n\nCourt record:\n"
                       f"{row['date_filed']} | {row['case_name']} | {row['court']} | "
                       f"{row['crime_type']} | {row['summary']}"}],
            output_format=StoryMatch,
        )
        m = response.parsed_output
        if m.matches and m.story_id in {s["id"] for s in pool}:
            return m.story_id
    except anthropic.APIError:
        pass
    return ""


def load_court_records() -> list[dict]:
    if not COURT_CSV.exists():
        return []
    with open(COURT_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_court_records(rows: list[dict]) -> None:
    COURT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(COURT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COURT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true",
                        help="sweep all history instead of the last 60 days")
    parser.add_argument("--push-progress", action="store_true",
                        help="commit+push data/ at each checkpoint (CI only)")
    args = parser.parse_args()

    for var in ("COURTLISTENER_TOKEN", "ANTHROPIC_API_KEY"):
        if not os.environ.get(var):
            sys.exit(f"{var} is not set; refusing to run.")

    client = anthropic.Anthropic()
    records = load_court_records()
    stories = load_stories()
    seen = set(json.load(open(SEEN_JSON))) if SEEN_JSON.exists() else set()

    filed_after = None if args.full else (date.today() - timedelta(days=60)).isoformat()
    collected, failed_searches = collect_candidates(filed_after)
    candidates = [c for c in collected if c["key"] not in seen]
    print(f"{len(candidates)} new court-document candidates "
          f"({failed_searches} searches failed)")
    if failed_searches and not collected:
        sys.exit("Every search failed (rate limit?); failing loudly instead of "
                 "reporting an empty sweep as success.")

    counts = {"new": 0, "rejected": 0, "errors": 0}
    next_id = max((int(r["id"]) for r in records), default=0) + 1
    for i, cand in enumerate(candidates, 1):
        print(f"[{i}/{len(candidates)}] {cand['case_name'][:70]} | {cand['description'][:50]}")
        try:
            text = (fetch_recap_text(cand["doc_id"]) if cand["kind"] == "recap"
                    else fetch_opinion_text(cand["doc_id"]))
            cls = classify_document(client, cand, text)
        except Exception as e:
            print(f"  error, skipping (will retry next run): {e}")
            counts["errors"] += 1
            continue

        seen.add(cand["key"])

        # Checkpoint every 10 processed docs so interruptions lose little work.
        if i % 10 == 0:
            save_court_records(records)
            with open(SEEN_JSON, "w", encoding="utf-8") as f:
                json.dump(sorted(seen), f, indent=0)
            if args.push_progress:
                push_progress(f"Court sweep progress {i}/{len(candidates)}: "
                              f"{counts['new']} added, {counts['rejected']} rejected")

        if not cls.qualifies:
            print(f"  rejected: {cls.reason[:100]}")
            counts["rejected"] += 1
            continue

        row = {
            "id": str(next_id), "date_added": date.today().isoformat(),
            "record_type": cls.record_type, "case_name": cand["case_name"],
            "court": cand["court"], "state": cls.state or "",
            "date_filed": cand["date_filed"], "crime_type": cls.crime_type or "",
            "flock_role": cls.flock_role or "", "summary": cls.summary or "",
            "source_url": cand["url"],
            "matched_story_id": "", "confidence": cls.confidence,
        }
        row["matched_story_id"] = match_news_story(client, row, stories)
        records.append(row)
        next_id += 1
        counts["new"] += 1
        linked = f" (linked to story {row['matched_story_id']})" if row["matched_story_id"] else ""
        print(f"  ADDED: {row['record_type']} | {row['court']} | {row['crime_type']}{linked}")

    records.sort(key=lambda r: r["date_filed"], reverse=True)
    save_court_records(records)
    with open(SEEN_JSON, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=0)

    from build_site import build_site
    build_site()
    print(f"\nDone. New: {counts['new']}, rejected: {counts['rejected']}, "
          f"errors: {counts['errors']}. {len(records)} court records total.")

    processed = counts["new"] + counts["rejected"] + counts["errors"]
    if processed and counts["errors"] > processed / 2:
        sys.exit("More than half of processed documents errored; failing the run.")


if __name__ == "__main__":
    main()
