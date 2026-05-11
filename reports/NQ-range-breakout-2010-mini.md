# NQ Range Breakout / Continuation Strategy Search

## Purpose

This search tests bar-only rules that first identify a compressed/choppy range, then trade a breakout, retest continuation, liquidity sweep/reclaim, boundary pin, or FVG breakout. Selection is based on expectancy: win probability times average win versus loss probability times average loss.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Span: `2010-06-06 22:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Rows: `5,383,225`.
- Costs: `0.625` NQ points round trip.

## Candidate Design

- Signals: `breakout_close, breakout_retest, sweep_reclaim`.
- Lookbacks: `30` minutes.
- Range filter: width <= ATR multiple, efficiency <= threshold, min width `4.0` points.
- Reward/risk targets: `2.0`.
- Stop modes: `structure`; same-bar stop/target ambiguity is resolved stop-first.
- Candidate count: `6`.

## Walk-Forward

- Train/purge/test/step days: `730` / `5` / `180` / `90`.
- Fold rows: `0`; aggregated candidates: `0`.
- Train gates: trades >= `80`, PF >= `1.08`, expectancy >= `0.25`.
- Test gates: trades >= `20`, PF >= `1.02`, expectancy >= `0.0`.

## Verdict

No range-breakout candidate passed the stable gate on this run. The top rows remain research evidence only.