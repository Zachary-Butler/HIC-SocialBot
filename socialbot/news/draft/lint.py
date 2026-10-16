"""Post-draft checks that are about rules, not voice. They produce warnings for the human, never
silent edits. The writer returns `people_named` and `officials_named` as structured fields; those
are the primary signal. A body-only regex is the backstop for officials the writer forgot to list.

- Pre-election window (until the day after the US midterms, Nov 3 2026): a draft that names an
  elected official is flagged. Several state attorneys general and members of Congress are on the
  ballot; counsel's guidance is to anchor to the action and refer to officials by role.
- Deceased-minor stories: any named person is flagged for the human to check against the family.
- Party labels in HIC's own voice are flagged.
- The call to action belongs on the closing slide, not on story slides.
"""

import re
from datetime import date

ELECTION_DAY = date(2026, 11, 3)

_OFFICIAL_IN_BODY = re.compile(
    r"\b(?:Attorney General|Sen\.|Senator|Rep\.|Representative|Gov\.|Governor|Lt\. Gov\.|Mayor|Comptroller)"
    r"\s+([A-Z][a-z]+(?:\s+[A-Z]\.)?\s+[A-Z][A-Za-z'\-]+)")
_PARTY_LABEL = re.compile(r"\((?:R|D|I)-[A-Z]{2}\)|\b(?:Republican|Democrat|Democratic|GOP)\b")
_CTA = re.compile(r"reality ?check|link in bio|sign up to present", re.I)


def pre_election_window(today: date | None = None) -> bool:
    return (today or date.today()) <= ELECTION_DAY


def lint(headline: str, body: str, risk_flags: list[str], people_named: list[str] | None = None,
         officials_named: list[str] | None = None, today: date | None = None) -> list[str]:
    text = f"{headline}\n{body}"
    warnings = []
    officials = list(officials_named or [])
    for m in _OFFICIAL_IN_BODY.finditer(body):
        if m.group(1) not in officials:
            officials.append(m.group(1))
    if pre_election_window(today) and officials:
        warnings.append("names elected official(s) during the pre-election window: " + ", ".join(officials)
                        + " (refer to them by role: \"Iowa's attorney general\")")
    for m in _PARTY_LABEL.finditer(text):
        warnings.append(f"party label in HIC's voice: \"{m.group(0)}\"")
    if "deceased_minor" in risk_flags and people_named:
        warnings.append("deceased-minor story names people: " + ", ".join(people_named)
                        + " (confirm none is the minor or the family)")
    if _CTA.search(body):
        warnings.append("story slide carries the call to action; that belongs on the closing slide")
    return warnings
