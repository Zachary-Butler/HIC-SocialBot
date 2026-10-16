"""Post-draft checks that are about rules, not voice. They produce warnings for the human (and
one hard block), never silent edits.

- Pre-election window (until the day after the US midterms, Nov 3 2026): a draft that names an
  elected official is flagged. Several state attorneys general and members of Congress are on the
  ballot; counsel's guidance is to anchor to the action and refer to officials by role.
- Deceased-minor stories: a draft that appears to name a person is flagged (names must never appear).
- Party labels in HIC's own voice are flagged.
"""

import re
from datetime import date

ELECTION_DAY = date(2026, 11, 3)

_OFFICIAL_NAME = re.compile(
    r"\b(?:Attorney General|Sen\.|Senator|Rep\.|Representative|Gov\.|Governor|Lt\. Gov\.|Mayor|Secretary|Comptroller)"
    r"\s+(?:[A-Z][a-z]+(?:\s+[A-Z]\.)?\s+[A-Z][A-Za-z'\-]+)")
_PARTY_LABEL = re.compile(r"\((?:R|D|I)-[A-Z]{2}\)|\b(?:Republican|Democrat|Democratic|GOP)\b")
_PERSON_NAME = re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+(?:'s)?\b")
_NOT_NAMES = {"Attorney General", "New York", "New Jersey", "New Hampshire", "North Carolina", "South Carolina",
              "Los Angeles", "San Francisco", "United States", "Character AI", "Reality Check", "Open AI",
              "Google DeepMind", "Silicon Valley", "Supreme Court", "White House", "Wall Street", "Oct", "Nov"}


def pre_election_window(today: date | None = None) -> bool:
    return (today or date.today()) <= ELECTION_DAY


def lint(headline: str, body: str, risk_flags: list[str], today: date | None = None) -> list[str]:
    text = f"{headline}\n{body}"
    warnings = []
    if pre_election_window(today):
        for m in _OFFICIAL_NAME.finditer(text):
            warnings.append(f"names an elected official during the pre-election window: \"{m.group(0)}\" "
                            "(refer to them by role: \"Iowa's attorney general\")")
    for m in _PARTY_LABEL.finditer(text):
        warnings.append(f"party label in HIC's voice: \"{m.group(0)}\"")
    if "deceased_minor" in risk_flags:
        names = {m.group(0) for m in _PERSON_NAME.finditer(text)} - _NOT_NAMES
        if names:
            warnings.append("deceased-minor story names people: " + ", ".join(sorted(names))
                            + " (never name the minor or the family; check every name)")
    return warnings
