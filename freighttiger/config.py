"""All tunable parameters in one place (changing them changes the output; they are documented in the README)."""
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
SHIPMENTS_CSV = DATA_DIR / "shipment_records.csv"
NOTES_CSV = DATA_DIR / "context_notes.csv"

HISTORY_WEEKS = 8            # trailing window for "own history" (spec: 8 prior weeks)

# Flag rule: cost must be rising vs own history AND look out of the ordinary.
RISE_MIN = 0.05              # vs own history must be at least +5% ("rising")
OWN_OUTLIER = 0.10           # ... and either >= +10% vs own history
PEER_OUTLIER = 0.15          # ... or >= +15% vs similar routes

# "All Routes" cost-level notes (e.g. diesel) persist as a level shift; they stop
# explaining a rise once the shift is absorbed into the 8-week baseline.
LEVEL_SHIFT_WEEKS = 8
# A note quoting "5-7%" explains an own-history rise up to its upper bound plus slack.
QUOTED_PCT_SLACK = 0.03
