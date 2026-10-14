# FreightTiger Shipping-Cost Watchdog

A small tool that watches weekly freight cost per tonne-km on each route, flags weeks where cost
is rising in a way that looks out of the ordinary, and says *why* in plain English, using only
what the provided notes actually say. If no note supports a reason, it says "unexplained" rather
than guessing.

## Run it (2 minutes)

```
pip install -r requirements.txt
python -m freighttiger.run          # writes results/output.csv
python -m pytest tests -q           # 8 checks, should print "8 passed"
./reproducibility_check.sh          # 3 runs + diff (on Windows: run the python line 3 times and compare)
```
Needs Python 3.10+ and pandas. Runs in under a second; no API keys, no network.

## What it found

18 route-weeks were worth a look: **15 flagged for human review, 3 justified by a note.**

| Route | Weeks | Verdict | Why |
|---|---|---|---|
| Ahmedabad-Mumbai | 2025-01-20 | Justified (N002) | Festival-week surcharge on this corridor, same week |
| Chennai-Bangalore | 2025-02-24, 03-03 | Justified (N001) | Flood detours, Feb 24 to Mar 8 |
| Chennai-Bangalore | 2025-03-10, 03-17 | **Flagged** | Roads reopened Mar 9 (N001) and N009 says conditions normalised, yet cost stayed ~34% above similar routes |
| Delhi-Jaipur | 2024-11-11, 11-18 | **Flagged** | Sudden jump (+35%, +28%); the only note for this route (N007) is from May 2024 and is about *better* roads |
| Mumbai-Delhi | 2025-05-12 | **Flagged** | +11.6%, more than the 5-7% diesel rise in N003 can account for |
| Mumbai-Pune | 10 weeks, Jun-Dec 2025 | **Flagged** | Slow upward drift to ~39% above similar routes by December; N006 says demand was stable |

Mumbai-Pune is the one I would send to a human first: it is not a single spike but a steady creep,
which is exactly the "quietly rising for no good reason" case the brief describes.

## How it works

**1. Weekly cost (`metrics.py`).** Shipments are grouped by route (origin-destination) and the
provided `route_type`, and assigned to Monday-Sunday weeks (`week_of` = Monday).
Weekly cost per tonne-km = total cost / total (tonnes x km). I pool the week's shipments
rather than averaging per-shipment ratios, so heavy long trips are not under-weighted.

**2. The two baselines (exactly as the brief defines them).**
- *Own history:* the average of the route's weekly values over the up-to-8 weeks **before** the current
  week (no look-ahead). Early weeks use however many prior weeks exist (1 to 7), without padding or
  extrapolating. The very first week of each route has no history, so it is never evaluated.
- *Similar routes:* the average for the same week across the **other** routes with the same
  `route_type`. The route itself is excluded.

**3. When a week is flagged as a candidate (`verdict.py`, thresholds in `config.py`).**
Cost must be rising (at least +5% vs own history) **and** look unusual: either at least +10% vs
own history, or at least +15% vs similar routes. These cut-offs are my judgment call, picked
because normal week-to-week noise sits within about +/-4%. They are one-line changes in `config.py`.

**4. Reading the notes (`notes.py`).** Each note is turned into a structured fact: which route(s) it
covers, the dates it applies to, and whether it actually describes a cost *increase*. Notes saying
costs were unaffected ("not significantly affected", "without a rate change", "returned to normal")
are never treated as a reason.

**5. The verdict.** A week is marked "No (justified)" only if a note passes **all** of these:
1. It covers this route (or "All Routes").
2. Its date window includes this week. N001 ends Mar 8, so it does not cover the week of Mar 10.
3. It describes a cost increase.
4. It fits what we see. A nationwide note like diesel (N003) can explain an own-history rise of
   roughly the size it quotes (5-7%, plus 3 points of slack). It **cannot** explain a gap against
   similar routes, because those routes got the same price rise.

Otherwise the row is flagged, and the reason names the closest note and why it does not apply.
The justified text is built from the matched note's own fields, so a reason cannot contain a cause
that is not in the notes.

## Assumptions worth challenging
- Own-history baseline = mean of weekly values (not pooled across weeks).
- N003 (diesel, "starting this week") is treated as a level shift that explains rises for 8 weeks
  (`LEVEL_SHIFT_WEEKS`), roughly until it is absorbed into the 8-week baseline.
- N002's "festival week" is read as the single Mon-Sun week containing the note date.
- Only candidate weeks appear in the output CSV, not all 700+ route-weeks, mirroring the sample file.

## What I did not build (honest scope)
- **No LLM or vector database.** With 10 short notes, exact route + date-window matching is more
  reliable than embeddings and is fully deterministic. The trade-off is that it does not generalise
  to messy, long, or ambiguous notes, where retrieval and an LLM would earn their cost. The natural
  extension is retrieval to shortlist notes, then a temperature-0 LLM that only extracts
  route/dates/effect into the same structured fields, with rules still making the final verdict.
- **No natural-language Q&A (stretch goal).**
- Consequently the token/cost log is 0 calls, 0 tokens, Rs 0 (`results/token_cost_log.txt`).

## How I convinced myself it is right
- **Matches the sample file.** My numbers reproduce all three example rows in
  `sample_output_format_v2.csv` (e.g. Delhi-Jaipur 2024-11-11: 4.17, +35.5%, +21.0%).
- **Labeled cases** (`tests/test_guardrails.py`): 10 real route-weeks with the expected verdict and
  note id. Caveat: I wrote these labels myself from the notes, so they are a regression check, not
  independent ground truth.
- **Adversarial notes:** I plant fake notes next to a real anomaly (wrong route, wrong date window, a
  note that says costs were unaffected). None may justify the flag, while a correct note must.
- **Invariants:** every justified row has a note id, and every note id used covers that row's route
  and week.
- **Reproducibility:** nothing is random. Three untouched runs give byte-identical files (same
  SHA-256, see `results/reproducibility_log.txt`).

## Project layout
```
freighttiger/
  config.py     thresholds and windows (all tunable settings)
  metrics.py    weekly cost per tonne-km and the two baselines
  notes.py      note -> structured fact, plus nearest-note lookup
  verdict.py    flag rule and grounded verdict text
  run.py        entry point, writes the output CSV
  data/         shipment_records.csv, context_notes.csv
tests/          eval harness (labeled + adversarial cases)
results/        output.csv, reproducibility log, token/cost log
```
