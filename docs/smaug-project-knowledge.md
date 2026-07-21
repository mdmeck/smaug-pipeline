# Smaug — reference context

Pin this to the claude.ai Project's knowledge so daily conversations don't need to re-explain it.

## What this is
Smaug is a personal intraday SPY options scalping tool. The trader uses a **break-and-retest methodology with confluence scoring and ATR-based stops**. A daily Python pipeline pulls SPY 1-minute bars (pre-market + regular trading hours, 30-day retention), computes indicator features, and runs regression/correlation analysis against forward-return targets. A companion webapp lets the trader log actual trades (Journal), log labeled good/bad trade examples (Training Data), and displays the "entry model" (structured rule set + PineScript indicator) synthesized daily by a routine from the two combined.

## Data sources

**GitHub (public repo, fetch directly — pipeline source only):**
- `https://raw.githubusercontent.com/mdmeck/Smaug/main/smaug_pipeline.py` — the actual pipeline source. `compute_features()` is the ground truth for exactly how every feature below is calculated; `compute_targets()` for the targets.

**Supabase (query via your Supabase connector, not a plain URL):**
- `bars` — 1-minute SPY bars + computed features, ~30-day retained window (~8,000 rows). Columns: `ts, ticker, open, high, low, close, volume, features` (jsonb — keys are the feature names below). Public read — no auth needed, but there are far more than 1000 rows, so page through with `.range()`/`limit`+`offset` rather than assuming one query returns everything.
- `analysis_runs` — daily regression/correlation output. One row per pipeline run (append-only — query `order by generated_at desc limit 1` for the current one). Columns: `generated_at, ticker, bars_analyzed, date_range, targets (jsonb), notes`. Public read, same as `bars`.
- `training_examples` — the trader's labeled trade examples, each a full round-trip: `entry_at, exit_at, ticker (default 'SPY'), direction (Long/Short), quality (Good/Bad — overall quality of the trade), notes`. **Private, RLS-protected** — only readable when your connector is authenticated as the trader. May be empty. Editable/deletable by the trader in the webapp, so always re-read fresh each run rather than assuming yesterday's set still applies. Note the entry-model synthesis is SPY-specific — if an example has a different ticker, treat it as informational context rather than folding it into the SPY feature-value join.
- `daily_briefs` — morning brief (econ calendar, earnings, sentiment, bull/bear case), written by the routine: `generated_at, econ (jsonb), earnings (jsonb), sentiment (jsonb), cases (jsonb)`. Private, same auth requirement as `training_examples`. One row per user (`user_id` is unique) — overwritten each run via `upsert` with `on_conflict=user_id`, no history kept. Query with a plain `select` for the current one.
- `entry_models` — each row is one AI-synthesized entry/exit rule set + PineScript indicator, written directly by the routine (append-only, so the trader can see the model evolve day over day). Private, same auth requirement: `generated_at, bars_analyzed, examples_used, date_range, rules (jsonb), summary, confidence (low/medium/high), pinescript (text)`.

For each training example, join **two** feature snapshots — never a later bar than the timestamp in question (that would be lookahead):
- **Entry snapshot**: the `bars` row with the largest `ts <= entry_at`. Good Long examples' entry snapshots inform `long_entry` rules; Good Short examples' entry snapshots inform `short_entry` rules.
- **Exit snapshot**: the `bars` row with the largest `ts <= exit_at`. All Good examples' exit snapshots (regardless of direction) inform `exit` rules.

## Feature columns (all stationary — returns/spreads/ratios/bps-distances, never raw price levels)
| feature | meaning |
|---|---|
| `rsi14` | RSI, 14-period, 0–100 |
| `ema_spread_bps` | (EMA9 − EMA21) / close, in bps |
| `dist_ema9_bps` | distance of close from EMA9, in bps |
| `dist_ema21_bps` | distance of close from EMA21, in bps |
| `ret_1m_bps` | 1-minute return, in bps |
| `ret_5m_bps` | 5-minute return, in bps |
| `range_bps` | (high − low) / close, in bps |
| `body_ratio` | candle body / candle range, 0–1 |
| `vol_z` | volume z-score vs. the same minute-of-day's historical average |
| `min_since_open` | minutes elapsed since 9:30 ET open |
| `dist_prev_day_high_bps` / `dist_prev_day_low_bps` | distance of close from the **previous session's** RTH high/low, in bps |
| `dist_premkt_high_bps` / `dist_premkt_low_bps` | distance of close from **today's** pre-market high/low, in bps |
| `dist_or5_high_bps` / `dist_or5_low_bps` | distance of close from the 5-minute opening-range high/low (first 5 min of RTH), in bps |
| `dist_or15_high_bps` / `dist_or15_low_bps` | distance of close from the 15-minute opening-range high/low, in bps |

All `dist_*`/`ret_*`/`range_bps`/`ema_spread_bps` features are causal — computed only from information available at or before that bar (no lookahead). Opening-range features use a running high/low while the window is still forming, then hold the finalized value for the rest of the session.

## Targets
| target | meaning |
|---|---|
| `fwd_5m_bps` / `fwd_10m_bps` / `fwd_15m_bps` | forward return N minutes ahead, in bps, same-session only |
| `mfe_10m_bps` | max favorable excursion (long side) over the next 10 minutes, in bps |

## PineScript generation
Every entry-model run also produces a complete TradingView Pine Script v5 indicator implementing the same `long_entry`/`short_entry`/`exit` rules, so the trader can paste it straight into TradingView. Requirements:
- `//@version=5`, `indicator("Smaug Entry Model", overlay=true)`.
- Expose every rule threshold as an `input.float`/`input.int` (with the synthesized value as the default) so the trader can tune it without waiting for a new pasted script.
- Recompute each referenced feature from Pine primitives, using the same formulas as `compute_features()`:
  - `rsi14` → `ta.rsi(close, 14)`; `ema9`/`ema21` → `ta.ema(close, 9)`/`ta.ema(close, 21)`.
  - `ema_spread_bps`, `dist_ema9_bps`, `dist_ema21_bps`, `ret_1m_bps`, `ret_5m_bps`, `range_bps`, `body_ratio` — same algebra as the Python formulas above, computed directly from `close`/`open`/`high`/`low` and `close[1]`/`close[5]`.
  - `dist_prev_day_high_bps` / `dist_prev_day_low_bps` — previous session's RTH high/low via `request.security(syminfo.tickerid, "D", high[1])` / `low[1]`.
  - `dist_or5_*` / `dist_or15_*` — opening-range high/low tracked with a `var` that resets at each new session and updates for the first 5/15 minutes of RTH, then holds.
  - `vol_z` — exact minute-of-day historical mean/std isn't practical in Pine; approximate with a rolling z-score (e.g. `(volume - ta.sma(volume, 20)) / ta.stdev(volume, 20)`) and add a comment noting it's an approximation, not an exact match to the Python calc.
  - `dist_premkt_*` — only replicate if the chart has extended-hours data available; otherwise add a comment noting the limitation rather than guessing.
- Plot a long-entry marker (`plotshape`, up-arrow) when all `long_entry` conditions are true, a short-entry marker (down-arrow) when all `short_entry` conditions are true, and an exit marker when all `exit` conditions are true.
- Self-contained — no external requests beyond `request.security` for prior-session levels.

## Entry-model output schema
When asked to synthesize/update the entry model, write a new row to `entry_models` with:
```json
{
  "rules": {
    "long_entry": [{"feature": "name", "op": "<|<=|>|>=", "value": number, "note": "under 15 words"}],
    "short_entry": [...],
    "exit": [...]
  },
  "summary": "3-5 sentences, plain language",
  "confidence": "low|medium|high",
  "bars_analyzed": number,
  "examples_used": number,
  "date_range": [start, end],
  "pinescript": "full Pine Script v5 source, as a single string"
}
```
`bars_analyzed`, `examples_used`, and `date_range` should echo whatever you actually read from `analysis_runs`/`training_examples` — reflect what was really used, not omitted or guessed.
Only use feature names from the table above — never invent one, since these rules get translated mechanically into `pinescript`. If there are zero or very few training examples, say so explicitly in the summary and lean on the regression/decile output instead; confidence must be "low" in that case. Never invent a finding the numbers don't support.
