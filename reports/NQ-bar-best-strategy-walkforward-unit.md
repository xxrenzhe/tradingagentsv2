# NQ Bar-Only Best Strategy Walk-Forward Search

## Verdict

No train-selected long-history bar-only candidate produced enough future test evidence.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Continuous construction: one NQ futures row per minute, selected by highest reported volume.
- Feature span: `2026-01-01 23:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Feature rows: `112,325`.
- Distinct symbols selected: `2`.

## Walk-Forward Design

- Train days: `20`; purge days: `2`; test days: `10`; step days: `10`.
- Candidate families: `mean_reversion`.
- Sessions: `us_rth`.
- Max fold candidates: `1`.
- Train gates: trades >= `1`, PF >= `0.0`, max DD <= `10000.0`.
- Test gates: trades >= `1`, PF >= `0.0`, max DD <= `10000.0`.

## Summary

- Fold rows: `0`.
- Aggregated candidates: `0`.
- Test-pass fold rows: `0`.
