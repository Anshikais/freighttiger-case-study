"""Eval harness: (A) labeled real cases, (B) adversarial synthetic notes that must NOT justify.
Run: python -m pytest tests -q   (or python tests/test_guardrails.py)"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from freighttiger.metrics import add_baselines, load_shipments, weekly_costs
from freighttiger.notes import NoteFact, parse_note
from freighttiger.run import build_output
from freighttiger.verdict import judge

# (A) hand-labeled from reading the notes + data: (route, week_of) -> (flagged, note_id)
LABELS = {
    ("Delhi-Jaipur", "2024-11-11"): ("Yes", ""),            # N007 is May 2024 + about road improvement
    ("Delhi-Jaipur", "2024-11-18"): ("Yes", ""),
    ("Ahmedabad-Mumbai", "2025-01-20"): ("No (justified)", "N002"),
    ("Chennai-Bangalore", "2025-02-24"): ("No (justified)", "N001"),
    ("Chennai-Bangalore", "2025-03-03"): ("No (justified)", "N001"),
    ("Chennai-Bangalore", "2025-03-10"): ("Yes", ""),       # roads passable again from Mar 9 -> N001 window over
    ("Chennai-Bangalore", "2025-03-17"): ("Yes", ""),       # N009 says back to normal
    ("Mumbai-Pune", "2025-09-15"): ("Yes", ""),             # N006 says stable demand
    ("Mumbai-Pune", "2025-12-08"): ("Yes", ""),
    ("Mumbai-Delhi", "2025-05-12"): ("Yes", ""),            # +11.6% exceeds N003's quoted 5-7%
}


def _output():
    return build_output().set_index(["route", "week_of"])


def test_labeled_cases():
    out = _output()
    bad = []
    for key, (flag, nid) in LABELS.items():
        r = out.loc[key]
        if (r.flagged, r.matched_note_id) != (flag, nid):
            bad.append((key, r.flagged, r.matched_note_id))
    assert not bad, bad


def test_no_justified_row_without_note_and_vice_versa():
    out = build_output().fillna("")
    assert ((out.flagged == "No (justified)") == (out.matched_note_id != "")).all()


def test_every_justified_note_covers_route_and_week():
    from freighttiger.notes import load_notes
    notes = {n.note_id: n for n in load_notes()}
    for r in build_output().itertuples():
        if r.matched_note_id:
            n = notes[r.matched_note_id]
            assert n.effect == "increase" and n.covers_route(r.route)
            assert n.overlaps_week(pd.Timestamp(r.week_of).date())


# (B) adversarial: a fake note planted next to a real anomaly must not justify it unless valid
def _row(route, week):
    w = add_baselines(weekly_costs(load_shipments()))
    return next(w[(w.route == route) & (w.week_of == pd.Timestamp(week))].itertuples())


def _note(nid, d, applies, text):
    return parse_note({"note_id": nid, "date": d, "applies_to": applies, "note": text})


def test_wrong_route_rejected():
    n = _note("X1", "2024-11-11", "Mumbai-Pune", "A surcharge led to higher costs this week.")
    assert judge(_row("Delhi-Jaipur", "2024-11-11"), [n]).flagged


def test_wrong_window_rejected():
    n = _note("X2", "2024-05-20", "Delhi-Jaipur", "A surcharge led to higher costs this week.")
    assert judge(_row("Delhi-Jaipur", "2024-11-11"), [n]).flagged


def test_negated_note_rejected():
    n = _note("X3", "2024-11-11", "Delhi-Jaipur", "A surcharge was announced but costs were not significantly affected.")
    assert judge(_row("Delhi-Jaipur", "2024-11-11"), [n]).flagged


def test_valid_note_accepted():
    n = _note("X4", "2024-11-11", "Delhi-Jaipur", "A temporary surcharge led to higher costs this week.")
    v = judge(_row("Delhi-Jaipur", "2024-11-11"), [n])
    assert v.justified and v.note_id == "X4"


def test_nationwide_note_cannot_explain_peer_gap():
    # Mumbai-Pune is +20% vs peers in the diesel window: diesel hit peers too.
    from freighttiger.notes import load_notes
    v = judge(_row("Mumbai-Pune", "2025-06-23"), load_notes())
    assert v.flagged and v.note_id == ""


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
