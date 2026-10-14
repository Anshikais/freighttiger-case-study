"""Entry point: python -m freighttiger.run [--out results/output.csv]"""
import argparse
from pathlib import Path

import pandas as pd

from . import config
from .metrics import add_baselines, load_shipments, weekly_costs
from .notes import load_notes
from .verdict import judge

COLUMNS = ["route", "week_of", "cost_per_tonne_km", "vs_own_history", "vs_similar_routes",
           "flagged", "matched_note_id", "reason"]


def pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def build_output(shipments_path=config.SHIPMENTS_CSV, notes_path=config.NOTES_CSV) -> pd.DataFrame:
    w = add_baselines(weekly_costs(load_shipments(shipments_path)))
    notes = load_notes(notes_path)
    rows = []
    for r in w.itertuples():
        v = judge(r, notes)
        if v is None:
            continue
        rows.append({
            "route": r.route,
            "week_of": r.week_of.strftime("%Y-%m-%d"),
            "cost_per_tonne_km": f"{r.cpt:.2f}",
            "vs_own_history": f"{pct(r.vs_own)} vs this route's past average",
            "vs_similar_routes": (f"{pct(r.vs_peer)} vs similar-length routes this week"
                                  if r.vs_peer == r.vs_peer else "n/a (no similar routes with data this week)"),
            "flagged": "Yes" if v.flagged else "No (justified)",
            "matched_note_id": v.note_id,
            "reason": v.reason,
        })
    return pd.DataFrame(rows, columns=COLUMNS).sort_values(["week_of", "route"]).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/output.csv")
    a = ap.parse_args()
    out = build_output()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False, lineterminator="\n")
    print(f"{len(out)} rows -> {a.out}  (flagged: {(out.flagged == 'Yes').sum()}, "
          f"justified: {(out.flagged != 'Yes').sum()})")


if __name__ == "__main__":
    main()
