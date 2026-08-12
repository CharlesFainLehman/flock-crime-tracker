"""Incident-level deduplication.

Multiple outlets cover the same incident. Before adding a new row, compare it
against existing rows in the same state within a date window; if candidates
exist, ask Haiku whether it is the same incident. Duplicates attach their URL
to the existing row's additional_sources instead of creating a new row.
"""

from datetime import date, datetime
from typing import Optional

import anthropic
from pydantic import BaseModel

from config import CLASSIFY_MODEL

DATE_WINDOW_DAYS = 21


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


def find_candidates(new_row: dict, stories: list[dict]) -> list[dict]:
    new_date = _parse_date(new_row.get("incident_date", ""))
    out = []
    for s in stories:
        if s.get("state") != new_row.get("state") or not new_row.get("state"):
            continue
        old_date = _parse_date(s.get("incident_date", ""))
        if new_date and old_date and abs((new_date - old_date).days) > DATE_WINDOW_DAYS:
            continue
        out.append(s)
    return out[:20]


def check_duplicate(client: anthropic.Anthropic, new_row: dict,
                    stories: list[dict]) -> str | None:
    """Return the id of the matching existing row, or None if this is new."""
    candidates = find_candidates(new_row, stories)
    if not candidates:
        return None

    existing = "\n".join(
        f"- id {s['id']}: {s['incident_date']} | {s['city']}, {s['state']} | "
        f"{s['crime_type']} | {s['summary']}"
        for s in candidates
    )
    new_desc = (
        f"{new_row['incident_date']} | {new_row['city']}, {new_row['state']} | "
        f"{new_row['crime_type']} | {new_row['summary']}"
    )

    response = client.messages.parse(
        model=CLASSIFY_MODEL,
        max_tokens=256,
        system=("You deduplicate a crime-incident database. Different news outlets "
                "often cover the same incident. Decide whether the new entry "
                "describes the same real-world incident as one of the existing "
                "entries. Same incident means same crime event, not merely "
                "similar crimes in the same area. If unsure, treat it as new."),
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
