"""Classify candidate articles with Claude Haiku.

Determines whether a story concretely describes Flock camera(s) assisting in
solving or preventing a crime, and extracts structured fields for the database.
"""

from typing import Literal, Optional

import anthropic
from pydantic import BaseModel

from config import CLASSIFY_MODEL, CRIME_TYPES


class StoryClassification(BaseModel):
    qualifies: bool
    reason: str
    incident_date: Optional[str] = None  # YYYY-MM-DD or YYYY-MM, best available
    city: Optional[str] = None
    state: Optional[str] = None  # two-letter US state/territory code
    crime_type: Optional[str] = None
    camera_role: Optional[str] = None
    outcome: Optional[str] = None
    summary: Optional[str] = None
    confidence: Literal["high", "medium", "low"] = "low"


SYSTEM_PROMPT = f"""You classify news articles for a public database tracking cases where Flock Safety cameras (automatic license plate readers) assisted in solving or preventing a specific crime.

An article QUALIFIES only if it describes a concrete incident in which a Flock camera or Flock Safety system played a role in an investigation, arrest, recovery, rescue, or crime prevention. The camera must be identified as Flock's (by brand name, or clearly the town's Flock system discussed in the article).

An article does NOT qualify if it is:
- A privacy, surveillance-policy, or legal debate about Flock cameras
- City council, procurement, contract, or camera-installation news
- A Flock Safety press release or company/business news with no specific incident
- A generic license-plate-reader story that never identifies Flock
- An opinion piece, or a story where the camera's role is speculative

Field guidance for qualifying articles:
- incident_date: date of the crime or the camera-assisted break in the case, as specific as the article allows (YYYY-MM-DD, YYYY-MM, or YYYY). Use the publication date only if nothing better is stated.
- state: two-letter US postal code.
- crime_type: choose the best fit from: {", ".join(CRIME_TYPES)}.
- camera_role: one short phrase, e.g. "LPR hit located suspect vehicle", "footage identified suspect vehicle", "real-time alert led to traffic stop".
- outcome: one short phrase, e.g. "arrest", "vehicle recovered", "missing person found", "charges filed", "suspect identified".
- summary: 1-2 factual sentences describing the incident and the camera's role.
- confidence: "high" if the article is explicit about Flock's role; "medium" if reasonably clear; "low" if you are working from limited text (e.g., headline only).

Always give a one-sentence reason for your decision."""


def classify_article(client: anthropic.Anthropic, candidate: dict,
                     article_text: str | None) -> StoryClassification:
    if article_text:
        body = f"Full article text:\n\n{article_text}"
    else:
        body = ("Full text unavailable; classify from headline and snippet only "
                "and cap confidence at 'low' unless the headline is unambiguous.\n\n"
                f"Snippet: {candidate.get('snippet') or '(none)'}")

    user_msg = (
        f"Headline: {candidate.get('title')}\n"
        f"Outlet: {candidate.get('source')}\n"
        f"Published: {candidate.get('published')}\n\n"
        f"{body}"
    )

    response = client.messages.parse(
        model=CLASSIFY_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        output_format=StoryClassification,
    )
    return response.parsed_output
