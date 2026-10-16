"""Grounding check: every quoted string in a draft must appear verbatim in a fetched source, and
every number must appear in one. This is what lets the human approve without re-reading the
articles. It is deliberately strict and dumb: a paraphrase in quotation marks fails."""

import re
from dataclasses import dataclass, field
from datetime import datetime

_QUOTE_RE = re.compile(r'["“”]([^"“”]{12,}?)["“”]')
# A number, optionally with $ in front and a unit after. "%" needs no word boundary; word units do.
_NUMBER_RE = re.compile(r"\$?\d(?:[\d,]*\d)?(?:\.\d+)?(?:\s?(?:%|(?:percent|million|billion|trillion|k|M|B)\b))?", re.I)
_YEAR_RE = re.compile(r"^(19|20)\d{2}$")


def normalize(s: str) -> str:
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    s = s.replace("—", "-").replace("–", "-").replace("…", "...")
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def quotes_in(text: str) -> list[str]:
    return [q.strip() for q in _QUOTE_RE.findall(text)]


def numbers_in(text: str) -> list[str]:
    out = []
    for m in _NUMBER_RE.finditer(text):
        n = m.group(0).strip()
        if _YEAR_RE.match(n.replace(",", "")):       # years are dates, not claims
            continue
        out.append(n)
    return out


def _number_variants(n: str) -> list[str]:
    core = re.sub(r"[^\d.,]", "", n)
    plain = core.replace(",", "")
    variants = {core, plain}
    if plain.isdigit() and len(plain) > 3:          # 3000 -> 3,000
        variants.add(f"{int(plain):,}")
    return [v for v in variants if v]


def date_variants(iso: str | None) -> str:
    """Ways a draft may legitimately write a date that the article body never spells out
    (the body says "Tuesday"; the metadata says 2026-10-14)."""
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso[:19])
    except ValueError:
        return iso
    return " ".join([d.strftime("%Y-%m-%d"), d.strftime("%b %d").replace(" 0", " "), d.strftime("%B %d").replace(" 0", " "),
                     d.strftime("%b. %d").replace(" 0", " "), f"{d.day} {d.strftime('%B')}", f"{d.month}/{d.day}"])


@dataclass
class VerifyResult:
    quotes_found: list[str] = field(default_factory=list)
    quotes_missing: list[str] = field(default_factory=list)
    numbers_found: list[str] = field(default_factory=list)
    numbers_missing: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.quotes_missing and not self.numbers_missing

    def summary(self) -> str:
        parts = []
        if self.quotes_found or self.quotes_missing:
            parts.append(f"{len(self.quotes_found)}/{len(self.quotes_found) + len(self.quotes_missing)} quotes found")
        if self.numbers_found or self.numbers_missing:
            parts.append(f"{len(self.numbers_found)}/{len(self.numbers_found) + len(self.numbers_missing)} numbers found")
        return ", ".join(parts) or "nothing to verify"


def verify(draft_text: str, sources: list[str]) -> VerifyResult:
    corpus = normalize(" ".join(sources))
    res = VerifyResult()
    for q in quotes_in(draft_text):
        probe = normalize(q).rstrip(".,;:!?")
        (res.quotes_found if probe and probe in corpus else res.quotes_missing).append(q)
    for n in numbers_in(draft_text):
        found = any(v.lower() in corpus for v in _number_variants(n))
        (res.numbers_found if found else res.numbers_missing).append(n)
    return res
