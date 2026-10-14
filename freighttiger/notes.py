"""Turn free-text notes into structured, checkable facts + deterministic retrieval.

Each note becomes a NoteFact: which routes it covers, the date window it describes,
and whether it actually describes a cost INCREASE. Parsing is rule-based, so it is
deterministic and every field can be audited (see `python -m freighttiger.notes`).
"""
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import pandas as pd

from . import config

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

INCREASE_CUES = re.compile(r"higher (trip )?costs?|surcharge|pushing up|prices rose|cost(s)? (rose|increase)", re.I)
# Phrases that say costs did NOT go up (checked before anything counts as a reason).
NEGATION_CUES = re.compile(
    r"not significantly affected|no significant|without a rate change|not part of this dataset|"
    r"remained (stable|normal)|no major|improved|returned to normal|absorbed by", re.I)
PCT_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*%")
DATE_RANGE = re.compile(r"from ([A-Z][a-z]{2}) (\d{1,2}) to ([A-Z][a-z]{2}) (\d{1,2})")


@dataclass(frozen=True)
class NoteFact:
    note_id: str
    note_date: date
    applies_to: str          # route like "Mumbai-Pune" or "All Routes"
    text: str
    effect: str              # "increase" | "none"
    start: date              # first day the described effect applies
    end: Optional[date]      # last day, or None => open-ended level shift
    kind: str                # "temporary" | "level_shift" | "none"
    pct_hi: Optional[float]  # upper bound of quoted % impact, if any

    def covers_route(self, route: str) -> bool:
        return self.applies_to == "All Routes" or self.applies_to == route

    def overlaps_week(self, week_of: date) -> bool:
        week_end = week_of + timedelta(days=6)
        if week_end < self.start:
            return False
        if self.end is None:  # level shift: lasts LEVEL_SHIFT_WEEKS weeks from start's week
            monday = self.start - timedelta(days=self.start.weekday())
            return week_of < monday + timedelta(weeks=config.LEVEL_SHIFT_WEEKS)
        return week_of <= self.end


def _parse_window(text: str, note_date: date):
    m = DATE_RANGE.search(text)
    if m:
        y = note_date.year
        s = date(y, MONTHS[m.group(1).lower()], int(m.group(2)))
        e = date(y, MONTHS[m.group(3).lower()], int(m.group(4)))
        return s, e, "temporary"
    if re.search(r"starting this week|rose nationwide", text, re.I):
        return note_date, None, "level_shift"
    # "a festival week": the week containing the note date
    monday = note_date - timedelta(days=note_date.weekday())
    return monday, monday + timedelta(days=6), "temporary"


def parse_note(row) -> NoteFact:
    text = row["note"]
    d = pd.Timestamp(row["date"]).date()
    increase = bool(INCREASE_CUES.search(text)) and not NEGATION_CUES.search(text)
    pct = PCT_RANGE.search(text)
    if increase:
        s, e, kind = _parse_window(text, d)
    else:
        s, e, kind = d, d, "none"
    return NoteFact(row["note_id"], d, row["applies_to"].strip(), text,
                    "increase" if increase else "none", s, e, kind,
                    float(pct.group(2)) / 100 if pct else None)


def load_notes(path=config.NOTES_CSV) -> list[NoteFact]:
    return [parse_note(r) for _, r in pd.read_csv(path).iterrows()]


# ---- retrieval -------------------------------------------------------------
def _tokens(s: str) -> set:
    return set(re.findall(r"[a-z]+", s.lower()))


def closest_note(notes: list[NoteFact], route: str, week_of: date) -> Optional[NoteFact]:
    """Best-effort 'nearest' note for explaining a non-match: must cover the route,
    ranked by lexical overlap with the route name, then by date proximity. Deterministic."""
    cands = [n for n in notes if n.covers_route(route)]
    if not cands:
        return None
    rt = _tokens(route)
    return min(cands, key=lambda n: (-len(rt & _tokens(n.text + " " + n.applies_to)),
                                     abs((n.note_date - week_of).days), n.note_id))


if __name__ == "__main__":
    for n in load_notes():
        print(n.note_id, n.applies_to, n.effect, n.kind, n.start, n.end, n.pct_hi)
