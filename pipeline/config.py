"""Shared configuration for the Flock story tracker pipeline."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
SITE_DIR = REPO_ROOT / "site"

STORIES_CSV = DATA_DIR / "stories.csv"
SEEN_URLS_JSON = DATA_DIR / "seen_urls.json"

CLASSIFY_MODEL = "claude-haiku-4-5"

# Search queries used for both GDELT and Google News discovery.
SEARCH_QUERIES = [
    '"Flock Safety" camera',
    '"Flock camera" arrest',
    '"Flock camera" stolen',
    '"Flock Safety" arrest',
    '"Flock Safety" suspect',
    '"Flock camera" police',
]

CSV_COLUMNS = [
    "id",
    "date_added",
    "incident_date",
    "city",
    "state",
    "crime_type",
    "camera_role",
    "outcome",
    "summary",
    "source_name",
    "source_url",
    "additional_sources",
    "confidence",
]

CRIME_TYPES = [
    "vehicle theft",
    "homicide",
    "shooting",
    "robbery",
    "burglary",
    "theft/larceny",
    "carjacking",
    "abduction/missing person",
    "fugitive apprehension",
    "assault",
    "drug offense",
    "weapons offense",
    "hit and run",
    "other",
]
