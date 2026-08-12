"""Read/write helpers for the stories CSV database and the seen-URL cache."""

import csv
import json
from datetime import date

from config import CSV_COLUMNS, SEEN_URLS_JSON, STORIES_CSV


def load_stories() -> list[dict]:
    if not STORIES_CSV.exists():
        return []
    with open(STORIES_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_stories(stories: list[dict]) -> None:
    STORIES_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(STORIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(stories)


def next_story_id(stories: list[dict]) -> int:
    return max((int(s["id"]) for s in stories), default=0) + 1


def load_seen_urls() -> set[str]:
    if not SEEN_URLS_JSON.exists():
        return set()
    with open(SEEN_URLS_JSON, encoding="utf-8") as f:
        return set(json.load(f))


def save_seen_urls(urls: set[str]) -> None:
    SEEN_URLS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_URLS_JSON, "w", encoding="utf-8") as f:
        json.dump(sorted(urls), f, indent=0)


def make_row(story_id: int, cls, candidate: dict) -> dict:
    """Build a CSV row from a classification result and its source candidate."""
    return {
        "id": str(story_id),
        "date_added": date.today().isoformat(),
        "incident_date": cls.incident_date or "",
        "city": cls.city or "",
        "state": cls.state or "",
        "crime_type": cls.crime_type or "",
        "camera_role": cls.camera_role or "",
        "outcome": cls.outcome or "",
        "summary": cls.summary or "",
        "source_name": candidate.get("source", ""),
        "source_url": candidate["url"],
        "additional_sources": "",
        "confidence": cls.confidence,
    }
