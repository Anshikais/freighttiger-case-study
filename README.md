# FreightTiger – Shipping Cost Watchdog

Spots routes whose cost per tonne-km is rising in an unjustified way, and explains each
flag using only the provided notes.

```
pip install -r requirements.txt
python -m freighttiger.run            # -> results/output.csv
python -m pytest tests -q             # eval harness (8 checks)
./reproducibility_check.sh            # 3 runs + diff
```

## How it works
1. **metrics.py** – group by route (origin-destination) and the given `route_type`; assign each
   shipment to its Mon–Sun week (`week_of` = Monday); weekly cost per tonne-km =
   `sum(cost) / sum(tonnes × km)` (ratio of totals, so heavy trips weigh more).
2. **Baselines (spec definitions)**
   - *own history*: mean of the weekly values of the up-to-8 weeks strictly before this week
     (`shift(1)`, no look-ahead). The first weeks of 2024 use fewer than 8 prior weeks (all available,
     no padding); the very first week has no history and is never output.
   - *similar routes*: mean of the other routes with the same `route_type` in the same week (self excluded).
3. **Flag rule (my choice – thresholds in `config.py`)**: rising ≥ +5% vs own history AND
   (≥ +10% vs own history OR ≥ +15% vs similar routes). Only these candidate weeks appear in the output
   (flagged "Yes", or "No (justified)").
4. **notes.py** – each note is parsed into a structured fact: routes covered, effective date window,
   and whether it actually describes a cost *increase*. Negations ("costs were not significantly
   affected", "without a rate change", "returned to normal") make it a non-reason.
5. **verdict.py** – "justified" requires a note that (a) covers the route, (b) overlaps that week,
   (c) describes an increase, (d) fits what we see. Nationwide notes (diesel, N003) explain an
   own-history rise of roughly the quoted size (5–7% + 3pt slack) but **cannot** explain a gap vs
   similar routes, since those routes got the same shock. No note → "unexplained", with the nearest
   note named and why it doesn't apply.

## What this is not (honest scope)
- **No LLM, no vector DB.** With 10 short notes, retrieval is an exact route + date-window match, which is
  more reliable than embeddings and fully deterministic. Reasons are templated from the matched note's
  fields, so they cannot invent a cause. I did not build the stretch Q&A goal. Natural extension: an LLM
  (temperature 0) that only receives `output.csv` rows + matched note text and answers questions.
- Hence the cost log is 0 calls / 0 tokens (`results/token_cost_log.txt`).

## Judgment calls you may want to challenge
- Own-history average = mean of weekly values (not pooled). N003's effect is assumed to last 8 weeks (`LEVEL_SHIFT_WEEKS`).
- Chennai-Bangalore 2025-03-10 and 03-17 stay **flagged**: N001's window ends Mar 8 ("passable again by Mar 9") and
  N009 says conditions normalised, yet cost stayed ~+34% vs peers. Worth a human look.
- Delhi-Jaipur Nov 2024 is unexplained (N007 is from May 2024 and about better roads).
- Mumbai-Pune is the main finding: a slow drift from mid-2025 to ~+39% vs peers by Dec, while N006 says demand was stable.
- Mumbai-Delhi 2025-05-12 (+11.6%) exceeds diesel's quoted 5–7%, so it is flagged.

## How I checked it
- `tests/test_guardrails.py`: (A) 10 hand-labeled real cases (labels written by me from the notes, so
  not independent ground truth); (B) adversarial planted notes: wrong route, wrong window, negated note must
  NOT justify; a valid note must; invariants that every justified row has a note id that covers that route and week.
- My outputs reproduce all three example rows of `sample_output_format_v2.csv` numerically.
- Reproducibility: 3 runs give identical SHA-256 (`results/reproducibility_log.txt`). Nothing is random.
