"""Sweep CourtListener for court filings and opinions mentioning Flock cameras.

Searches the RECAP archive (federal PACER documents) and published opinions via
the CourtListener v4 search API, classifies hits with Claude, and maintains
data/court_records.csv. Runs weekly (filings move slower than news); a full
sweep with no date floor runs when --full is passed.

Requires COURTLISTENER_TOKEN and ANTHROPIC_API_KEY.

--reclassify-opinions re-runs opinion candidates that are already in the seen
set (use after a text-fetch or classifier fix); rows already recorded are not
duplicated. --reclassify-low re-runs the documents behind rows whose confidence
is "low" (classified from a search snippet because the text fetch failed) and
updates or removes those rows in place. --retry-rejected re-runs every candidate
not already recorded, ignoring the seen set (one-off recovery after a fetch
outage). A candidate rejected without document text is never marked seen, so
the next sweep that reaches it tries again.
"""

import argparse
import csv
import html
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
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
CANDIDATES_JSON = DATA_DIR / "court_candidates.json"

COURT_QUERIES = ['"flock safety"', '"flock camera"', '"flock cameras"',
                 '"flock lpr"', '"flock alpr"', '"flock license plate"',
                 # Opinions and filings often say just "Flock" ("the Flock system",
                 # "Flock hits"). Measured 2026-09-16 against the six phrases above:
                 # +29 opinions, +270 RECAP dockets. The bird/congregation sense
                 # rarely co-occurs with plate-reader terms; the classifier rejects
                 # what does.
                 'flock AND ("license plate" OR "plate reader" OR alpr OR lpr)']

COURT_COLUMNS = [
    "id", "date_added", "record_type", "case_name", "court", "state",
    "date_filed", "crime_type", "flock_role", "summary", "source_url",
    "matched_story_id", "confidence",
]


def _headers() -> dict:
    token = os.environ.get("COURTLISTENER_TOKEN")
    return {"Authorization": f"Token {token}"} if token else {}


def _retry_after(value: str | None, default: int) -> int:
    """Retry-After is either a delay in seconds or an HTTP-date. int() on a
    date raises ValueError outside the retry handler and kills the sweep."""
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(0, int((when - datetime.now(timezone.utc)).total_seconds()))
    except (TypeError, ValueError):
        return default


def _get(url: str, params: dict | None = None) -> dict:
    last_exc: Exception | None = None
    for attempt in range(5):
        try:
            resp = requests.get(url, params=params, headers=_headers(), timeout=60)
            if resp.status_code == 429:
                # Honor Retry-After; CourtListener throttles per-hour, so waits
                # here are long by design.
                wait = _retry_after(resp.headers.get("Retry-After"), 60 * (attempt + 1))
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
    # highlight=on makes the snippet the passage that matched instead of the
    # first 500 characters of the document (a caption, for opinions), so the
    # snippet-only fallback in classify_document actually shows the Flock mention.
    params: dict | None = {"q": query, "type": result_type,
                           "order_by": "dateFiled desc", "highlight": "on"}
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
    """Bounded-retry fetch for optional enrichment (document text). Text fetches
    must never stall the sweep — the classifier falls back to the snippet, and
    says so in the log, because a snippet-only row gets confidence "low"."""
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=_headers(), timeout=30)
            if resp.status_code == 429:
                wait = min(_retry_after(resp.headers.get("Retry-After"), 20 * (attempt + 1)), 120)
                print(f"  CourtListener 429 on document fetch; waiting {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except (requests.Timeout, requests.ConnectionError):
            continue
    print("  document text unavailable (rate limit or timeout); classifying from the snippet")
    return {}


def _strip_tags(markup: str) -> str:
    """Plain text from HTML/XML (opinion bodies, highlighted snippets)."""
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", markup, flags=re.S | re.I)
    text = re.sub(r"</(p|div|li|h\d|tr|blockquote)>|<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"[ \t\xa0]+", " ", text).strip()


def _excerpt(text: str, max_chars: int = 12000) -> str:
    """Up to max_chars of a document. A long opinion may not mention Flock in
    its first 12,000 characters, so keep the caption and centre the rest on
    the first mention instead of truncating blindly."""
    if len(text) <= max_chars:
        return text
    head = 2000
    window = max_chars - head
    m = re.search(r"flock", text, re.I)
    start = m.start() - window // 3 if m else 0
    if start <= head:
        return text[:max_chars]
    return text[:head] + "\n[...]\n" + text[start:start + window]


def fetch_recap_text(doc_id: int, max_chars: int = 12000) -> str:
    data = _get_light(f"{BASE}/api/rest/v4/recap-documents/{doc_id}/",
                      {"fields": "plain_text"})
    return _excerpt(data.get("plain_text") or "", max_chars)


# Scraped PDFs fill plain_text; HTML-sourced and Harvard-imported opinions leave
# it empty and carry their text in one of the markup fields.
OPINION_TEXT_FIELDS = ("plain_text", "html_with_citations", "html", "xml_harvard",
                       "html_lawbox", "html_columbia")


def fetch_opinion_text(cluster_id: int, max_chars: int = 12000) -> str:
    data = _get_light(f"{BASE}/api/rest/v4/opinions/",
                      {"cluster__id": cluster_id, "fields": ",".join(OPINION_TEXT_FIELDS)})
    for opinion in data.get("results", []):
        for field in OPINION_TEXT_FIELDS:
            text = opinion.get(field) or ""
            if text.strip():
                return _excerpt(text if field == "plain_text" else _strip_tags(text),
                                max_chars)
    return ""


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
                    "snippet": _strip_tags(doc.get("snippet") or ""),
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
                "snippet": _strip_tags(((r.get("opinions") or [{}])[0].get("snippet")
                                        if r.get("opinions") else r.get("snippet")) or ""),
                "url": BASE + (r.get("absolute_url") or ""),
            })
        time.sleep(2)
    return list(candidates.values()), failed


CrimeType = Literal[tuple(CRIME_TYPES)]  # type: ignore[valid-type]


class CourtClassification(BaseModel):
    qualifies: bool
    reason: str
    record_type: Literal["warrant/affidavit", "complaint/indictment",
                         "suppression motion", "court order/opinion", "other"] = "other"
    state: Optional[str] = None  # two-letter code, blank for federal appellate
    crime_type: Optional[CrimeType] = None
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


def doc_signature(kind: str, court: str, case_name: str, date_filed: str, url: str) -> tuple:
    """Identity of the underlying document, independent of CourtListener ids.
    CourtListener often carries one case under several docket ids (and one
    opinion under several clusters), so the same filing surfaces with
    different URLs. A RECAP filing is its docket entry number; attachments
    (/docket/<id>/<entry>/<att>/...) fold into their main entry."""
    if kind == "opinion":
        return ("o", court, case_name.strip().lower(), date_filed)
    m = re.search(r"/docket/\d+/(\d+)/", url)
    return ("r", court, case_name.strip().lower(), date_filed, m.group(1) if m else url)


def record_signature(row: dict) -> tuple:
    kind = "opinion" if "/opinion/" in row["source_url"] else "recap"
    return doc_signature(kind, row["court"], row["case_name"], row["date_filed"], row["source_url"])


def select_candidates(collected: list[dict], seen: set[str], records: list[dict],
                      reclassify_opinions: bool = False,
                      reclassify_low: bool = False,
                      retry_rejected: bool = False) -> list[dict]:
    """Candidates still to classify: unseen keys, plus every opinion when
    re-classifying opinions, plus the documents behind low-confidence rows when
    re-classifying those. Documents already in the records table (by URL or by
    document signature) are otherwise never re-run, so a re-classification
    cannot duplicate a row; within a run, one signature is classified once."""
    low_urls = {r["source_url"] for r in records if r["confidence"] == "low"} \
        if reclassify_low else set()
    recorded_urls = {r["source_url"] for r in records}
    taken = {record_signature(r) for r in records}
    out = []
    for c in collected:
        if c["url"] in low_urls:
            out.append(c)  # re-run in place; main() updates or removes its row
            continue
        if c["key"] in seen and not retry_rejected \
                and not (reclassify_opinions and c["kind"] == "opinion"):
            continue
        sig = doc_signature(c["kind"], c["court"], c["case_name"], c["date_filed"], c["url"])
        if c["url"] in recorded_urls or sig in taken:
            continue
        taken.add(sig)
        out.append(c)
    return out


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
    parser.add_argument("--collect-only", action="store_true",
                        help="search CourtListener and write candidates JSON; no classification")
    parser.add_argument("--from-file", action="store_true",
                        help="classify candidates from JSON file; no CourtListener search "
                             "(document text is still fetched when COURTLISTENER_TOKEN is set)")
    parser.add_argument("--reclassify-opinions", action="store_true",
                        help="re-run opinion candidates already in the seen set; "
                             "documents already recorded are skipped")
    parser.add_argument("--reclassify-low", action="store_true",
                        help="re-run the documents behind low-confidence rows and update "
                             "or remove those rows in place (use with --full to reach old rows)")
    parser.add_argument("--retry-rejected", action="store_true",
                        help="re-run every candidate not already recorded, ignoring the seen "
                             "set (one-off recovery after a text-fetch outage)")
    args = parser.parse_args()

    if args.collect_only:
        filed_after = None if args.full else (date.today() - timedelta(days=60)).isoformat()
        collected, failed_searches = collect_candidates(filed_after)
        if failed_searches and not collected:
            sys.exit("Every search failed (rate limit?).")
        with open(CANDIDATES_JSON, "w", encoding="utf-8") as f:
            json.dump(collected, f, indent=0)
        print(f"Wrote {len(collected)} candidates -> {CANDIDATES_JSON}")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set; refusing to run.")

    client = anthropic.Anthropic()
    records = load_court_records()
    stories = load_stories()
    seen = set(json.load(open(SEEN_JSON))) if SEEN_JSON.exists() else set()

    if args.from_file:
        with open(CANDIDATES_JSON, encoding="utf-8") as f:
            collected = json.load(f)
        failed_searches = 0
    else:
        if not os.environ.get("COURTLISTENER_TOKEN"):
            sys.exit("COURTLISTENER_TOKEN is not set; refusing to run.")
        filed_after = None if args.full else (date.today() - timedelta(days=60)).isoformat()
        collected, failed_searches = collect_candidates(filed_after)
    candidates = select_candidates(collected, seen, records, args.reclassify_opinions,
                                   args.reclassify_low, args.retry_rejected)
    print(f"{len(candidates)} court-document candidates to classify "
          f"({failed_searches} searches failed)")
    if failed_searches and not collected:
        sys.exit("Every search failed (rate limit?); failing loudly instead of "
                 "reporting an empty sweep as success.")

    counts = {"new": 0, "updated": 0, "removed": 0, "rejected": 0, "retry": 0, "errors": 0}
    next_id = max((int(r["id"]) for r in records), default=0) + 1
    by_url = {r["source_url"]: r for r in records}
    for i, cand in enumerate(candidates, 1):
        print(f"[{i}/{len(candidates)}] {cand['case_name'][:70]} | {cand['description'][:50]}")
        try:
            if args.from_file and not os.environ.get("COURTLISTENER_TOKEN"):
                text = ""  # no token for document-text calls; snippet only
            else:
                text = (fetch_recap_text(cand["doc_id"]) if cand["kind"] == "recap"
                        else fetch_opinion_text(cand["doc_id"]))
            cls = classify_document(client, cand, text)
        except Exception as e:
            print(f"  error, skipping (will retry next run): {e}")
            counts["errors"] += 1
            continue

        existing = by_url.get(cand["url"])
        if cls.qualifies:
            fields = {
                "record_type": cls.record_type, "case_name": cand["case_name"],
                "court": cand["court"], "state": cls.state or "",
                "date_filed": cand["date_filed"], "crime_type": cls.crime_type or "",
                "flock_role": cls.flock_role or "", "summary": cls.summary or "",
                "source_url": cand["url"], "confidence": cls.confidence,
            }
            if existing is not None:
                # Re-classification of a low-confidence row: keep id and date_added.
                existing.update(fields)
                if not existing.get("matched_story_id"):
                    existing["matched_story_id"] = match_news_story(client, existing, stories)
                counts["updated"] += 1
                print(f"  UPDATED: {existing['record_type']} | {existing['court']} | "
                      f"{existing['crime_type']} | confidence {existing['confidence']}")
                continue
            row = {"id": str(next_id), "date_added": date.today().isoformat(),
                   "matched_story_id": "", **fields}
            row["matched_story_id"] = match_news_story(client, row, stories)
            records.append(row)
            by_url[row["source_url"]] = row
            next_id += 1
            counts["new"] += 1
            linked = f" (linked to story {row['matched_story_id']})" if row["matched_story_id"] else ""
            print(f"  ADDED: {row['record_type']} | {row['court']} | {row['crime_type']}{linked}")
        else:
            print(f"  rejected: {cls.reason[:100]}")
            counts["rejected"] += 1
            if existing is not None:
                records.remove(existing)
                del by_url[cand["url"]]
                counts["removed"] += 1
                print("  REMOVED: previously recorded from a snippet; full text does not qualify")
            elif not text.strip():
                # Rejected on a search snippet because the text fetch returned
                # nothing: leave it out of `seen` so the next sweep tries again.
                print("  (no document text; not marked seen, will retry)")
                counts["retry"] += 1
                continue

        # Mark seen only once this document's row (if any) is in `records`, and
        # checkpoint both together: persisting the key first would let a crash
        # here drop a classified record permanently, since the next run skips
        # anything already in `seen`.
        seen.add(cand["key"])
        if i % 10 == 0:
            save_court_records(records)
            with open(SEEN_JSON, "w", encoding="utf-8") as f:
                json.dump(sorted(seen), f, indent=0)
            if args.push_progress:
                push_progress(f"Court sweep progress {i}/{len(candidates)}: "
                              f"{counts['new']} added, {counts['rejected']} rejected")

    records.sort(key=lambda r: r["date_filed"], reverse=True)
    save_court_records(records)
    with open(SEEN_JSON, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=0)

    from build_site import build_site
    build_site()
    print(f"\nDone. New: {counts['new']}, updated: {counts['updated']}, "
          f"removed: {counts['removed']}, rejected: {counts['rejected']} "
          f"(of which {counts['retry']} without text, kept for retry), "
          f"errors: {counts['errors']}. {len(records)} court records total.")

    processed = counts["new"] + counts["updated"] + counts["rejected"] + counts["errors"]
    if processed and counts["errors"] > processed / 2:
        sys.exit("More than half of processed documents errored; failing the run.")


if __name__ == "__main__":
    main()
