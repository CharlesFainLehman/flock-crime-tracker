"""Incident-level deduplication.

Multiple outlets cover the same incident. Before adding a new row, compare it
against existing rows in the same state within a date window (nationwide when
the new row has no city); if candidates exist, ask Haiku whether it is the
same incident. Duplicates attach their URL
to the existing row's additional_sources instead of creating a new row.
"""

import calendar
import re
from datetime import date, datetime
from typing import Optional
from urllib.parse import urlparse

import anthropic
from pydantic import BaseModel

from config import CLASSIFY_MODEL

DATE_WINDOW_DAYS = 21
SHORTLIST_SIZE = 20
NATIONWIDE_EXTRA = 10


class DedupeResult(BaseModel):
    is_duplicate: bool
    matching_id: Optional[str] = None


def _parse_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def _day_precision(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def _date_span(value: str) -> tuple[date, date] | None:
    """The (first, last) day a date string could refer to: a full date is a
    one-day span, "YYYY-MM" spans the month, "YYYY" spans the year."""
    d = _parse_date(value)
    if d is None:
        return None
    if _day_precision(value):
        return (d, d)
    try:
        datetime.strptime(value, "%Y-%m")
        return (d, d.replace(day=calendar.monthrange(d.year, d.month)[1]))
    except (ValueError, TypeError):
        return (d, d.replace(month=12, day=31))


def _span_gap(a: tuple[date, date], b: tuple[date, date]) -> int:
    """Days between two date spans; 0 when they overlap."""
    if a[0] > b[1]:
        return (a[0] - b[1]).days
    if b[0] > a[1]:
        return (b[0] - a[1]).days
    return 0


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def _row_domains(s: dict) -> set[str]:
    urls = [s.get("source_url", ""), *s.get("additional_sources", "").split()]
    return {_domain(u) for u in urls if u} - {""}


STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana",
    "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}


def _names_state(text: str, abbr: str) -> bool:
    """True when the text spells out the state's full name."""
    name = STATE_NAMES.get(abbr)
    return bool(name and re.search(rf"\b{name}\b", text, re.I))


def find_candidates(new_row: dict, stories: list[dict]) -> list[dict]:
    new_val = new_row.get("incident_date", "")
    new_span = _date_span(new_val)
    new_dom = _domain(new_row.get("source_url", ""))
    new_state = new_row.get("state") or ""
    new_summary = new_row.get("summary") or ""
    # A row with no city was classified from a headline or a text that never
    # placed the incident; its state, if any, may be the syndicating
    # station's. Such rows used to get no candidates (no state) or only
    # wrong-state ones, so 31 affiliate copies of record 2231 were all added
    # as new incidents. They also get the nearest rows from anywhere.
    nationwide = not new_state or not (new_row.get("city") or "").strip()
    out, local_ids = [], set()
    for s in stories:
        old_state = s.get("state") or ""
        # Same-state rows are always candidates. An interstate case (an
        # abduction that ends in a traffic stop two states away, a fugitive
        # tracked across a border) gets filed under either end by different
        # outlets, and a strict same-state filter compared nothing: 2149/2136
        # (NC vs GA), 2230/2227 (FL vs AR), 2047/498 (SC vs NC). Admit a row
        # from another state when either summary spells out the other's state.
        local = bool(new_state) and (
            old_state == new_state
            or _names_state(new_summary, old_state)
            or _names_state(s.get("summary") or "", new_state))
        if not (local or nationwide):
            continue
        old_val = s.get("incident_date", "")
        # Hard-exclude on the window only when BOTH dates carry day precision:
        # a month-only date parses to the 1st, which put a late-July incident
        # ("2026-07") outside the window of its own September follow-up
        # (2207/2163). Imprecise dates stay in and rank by span gap instead.
        if (new_span and _day_precision(new_val) and _day_precision(old_val)
                and _span_gap(new_span, _date_span(old_val)) > DATE_WINDOW_DAYS):
            continue
        out.append(s)
        if local:
            local_ids.add(s["id"])
    # Rank by date proximity before truncating: CSV order is neither
    # chronological nor relevance-ranked, so a plain slice can drop the very
    # row the new story duplicates. Imprecise dates compare by span gap, so
    # "2026-07" sits 0 days from any July date rather than being pinned to
    # July 1. Ties (and pairs missing a date entirely) break toward the most
    # recently ADDED row: when the new story has no incident date the
    # proximity ranking is inert, and a plain slice kept the 20 oldest
    # same-state rows — nine syndicated copies of one undated story each
    # missed their just-added twin at the end of the list (rows 2189-2197).
    def _distance(s: dict) -> tuple[int, int, int]:
        added = _parse_date(s.get("date_added", ""))
        recency = -(added.toordinal() if added else 0)
        old_span = _date_span(s.get("incident_date", ""))
        if not new_span or not old_span:
            return (1, 0, recency)
        return (0, _span_gap(new_span, old_span), recency)
    out.sort(key=_distance)
    local = [s for s in out if s["id"] in local_ids]
    # Two follow-up signals are strong enough that crowding must never
    # truncate them out of the shortlist: a row sharing the new story's
    # source domain (2225 repeated 2209 from the same station's site), and a
    # row with the same city and crime type (2207 repeated 2163 — same
    # Marshall, TX homicide — but the old row's month-only date ranked it
    # past the cap in a busy state).
    same_dom = [s for s in local if new_dom and new_dom in _row_domains(s)][:5]
    city = (new_row.get("city") or "").strip().lower()
    same_city = [s for s in local
                 if city and (s.get("city") or "").strip().lower() == city
                 and s.get("crime_type") == new_row.get("crime_type")][:5]
    shortlist = _take(same_dom + same_city + local, SHORTLIST_SIZE, set())
    if nationwide:
        # Fills the shortlist to 30 after the same-state rows, which a
        # cityless row's state may still justify (2183 duplicated Florida
        # record 2151), so it is a strict superset of the same-state
        # comparison. Month- and
        # year-only rows from every state sit 0 days from any date in their
        # span, so nationally they rank after day-precise rows at equal gap.
        national = sorted(out, key=lambda s: (
            _distance(s)[:2]
            + (int(not _day_precision(s.get("incident_date", ""))),)
            + _distance(s)[2:]))
        room = SHORTLIST_SIZE + NATIONWIDE_EXTRA - len(shortlist)
        shortlist += _take(national, room, {s["id"] for s in shortlist})
    return shortlist


def _take(rows: list[dict], n: int, seen: set[str]) -> list[dict]:
    """The first n rows whose ids are not in `seen`, without repeats."""
    taken = []
    for s in rows:
        if len(taken) == n:
            break
        if s["id"] not in seen:
            seen.add(s["id"])
            taken.append(s)
    return taken


def check_duplicate(client: anthropic.Anthropic, new_row: dict,
                    stories: list[dict]) -> str | None:
    """Return the id of the matching existing row, or None if this is new."""
    candidates = find_candidates(new_row, stories)
    if not candidates:
        return None

    existing = "\n".join(
        f"- id {s['id']}: {s['incident_date']} | {s['city']}, {s['state']} | "
        f"{s['crime_type']} | {s['summary']} | src: {s['source_url']} "
        f"(added {s.get('date_added', '?')})"
        for s in candidates
    )
    new_desc = (
        f"{new_row['incident_date']} | {new_row['city']}, {new_row['state']} | "
        f"{new_row['crime_type']} | {new_row['summary']} | "
        f"src: {new_row.get('source_url', '')}"
    )

    response = client.messages.parse(
        model=CLASSIFY_MODEL,
        max_tokens=256,
        system=("You deduplicate a crime-incident database. Different news outlets "
                "often cover the same incident. Decide whether the new entry "
                "describes the same real-world incident as one of the existing "
                "entries. Same incident means same crime event, not merely "
                "similar crimes in the same area. Watch for follow-up coverage: "
                "a later story about the same case often adds or changes details "
                "— a newly named suspect or victim, additional victims, an origin "
                "city for a chase or abduction, updated charges, or a corrected "
                "date. Matching location and crime type with dates within a few "
                "days of each other usually means the same incident; an interstate "
                "case is often filed under a different city and state by each "
                "outlet (the abduction's origin in one, the traffic stop or "
                "recovery in another) and is still one incident. A story "
                "from the same outlet or domain as an existing entry's source is "
                "very often follow-up coverage of it. A recorded incident date "
                "may be the date of resolution or of publication rather than of "
                "the crime, so a small date mismatch is weak evidence of a "
                "different incident. An entry with no city was classified "
                "without a stated location; its state may be the publishing "
                "station's, so judge it on the crime, date, and details rather "
                "than on location. If still unsure after weighing these, treat "
                "it as new."),
        messages=[{
            "role": "user",
            "content": f"Existing entries:\n{existing}\n\nNew entry:\n{new_desc}",
        }],
        output_format=DedupeResult,
    )
    result = response.parsed_output
    if result.is_duplicate and result.matching_id:
        known = {s["id"] for s in candidates}
        if result.matching_id in known:
            return result.matching_id
    return None
