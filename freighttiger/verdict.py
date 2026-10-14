"""Flagging rule and grounded verdicts. A 'justified' verdict needs a note that
(1) covers this route, (2) overlaps this week, (3) describes a cost increase, and
(4) is consistent in size/scope with what we observe. Otherwise: unexplained."""
from dataclasses import dataclass
from typing import Optional

from . import config
from .notes import NoteFact, closest_note


@dataclass
class Verdict:
    flagged: bool
    justified: bool
    note_id: str
    reason: str


def trigger(row) -> Optional[dict]:
    """Which criteria made this week a candidate? None => not out of the ordinary."""
    vo, vp = row.vs_own, row.vs_peer
    if vo != vo or vo < config.RISE_MIN:       # NaN (no history) or not rising
        return None
    own = vo >= config.OWN_OUTLIER
    peer = vp == vp and vp >= config.PEER_OUTLIER
    return {"own": own, "peer": peer} if (own or peer) else None


def _explains(note: NoteFact, row, trig) -> bool:
    if note.effect != "increase" or not note.covers_route(row.route):
        return False
    if not note.overlaps_week(row.week_of.date()):
        return False
    if note.applies_to == "All Routes":
        # A nationwide cost shift hit peers too, so it cannot explain a peer gap,
        # and it only explains an own-history rise of about the size it quotes.
        if trig["peer"]:
            return False
        if note.pct_hi is not None and row.vs_own > note.pct_hi + config.QUOTED_PCT_SLACK:
            return False
    return True


def judge(row, notes: list[NoteFact]) -> Optional[Verdict]:
    trig = trigger(row)
    if trig is None:
        return None
    matches = [n for n in notes if _explains(n, row, trig)]
    if matches:
        # prefer route-specific over nationwide, then earliest id (deterministic)
        n = sorted(matches, key=lambda n: (n.applies_to == "All Routes", n.note_id))[0]
        return Verdict(False, True, n.note_id, _justified_text(n, row))
    return Verdict(True, False, "", _unexplained_text(notes, row, trig))


def _justified_text(n: NoteFact, row) -> str:
    when = f"{n.start:%Y-%m-%d}" + (f" to {n.end:%Y-%m-%d}" if n.end and n.end != n.start else " onward")
    scope = "this route" if n.applies_to != "All Routes" else "all routes"
    return (f"Matches note {n.note_id} (dated {n.note_date}, covering {scope}, effective {when}): "
            f"{n.text} The week of {row.week_of:%Y-%m-%d} falls inside that window, so the cost rise has a documented explanation.")


def _unexplained_text(notes, row, trig) -> str:
    base = "No genuine justification found; flagged for human review."
    near = closest_note(notes, row.route, row.week_of.date())
    why = ""
    if near is None:
        why = "No note covers this route. "
    elif near.effect == "none":
        why = (f"The closest note ({near.note_id}, {near.note_date}) does not describe a cost rise "
               f"(it says costs were unaffected or conditions normal). ")
    elif not near.overlaps_week(row.week_of.date()):
        why = (f"The closest note ({near.note_id}, {near.note_date}) describes a cost rise but its window "
               f"({near.start} to {near.end or 'ongoing'}) does not include this week. ")
    elif trig["peer"] and near.applies_to == "All Routes":
        why = (f"Note {near.note_id} (nationwide) was in effect, but it hit similar routes too, so it cannot "
               f"explain this route being {row.vs_peer:+.1%} above them. ")
    else:
        why = (f"Note {near.note_id} was in effect but the rise ({row.vs_own:+.1%}) is larger than it "
               f"describes. ")
    return why + base
