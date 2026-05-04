# NQ Bar-Only Best Strategy Walk-Forward Search

## Verdict

No train-selected long-history bar-only candidate produced enough future test evidence.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Continuous construction: one NQ futures row per minute, selected by highest reported volume.
- Feature span: `2020-01-01 23:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Feature rows: `2,230,054`.
- Distinct symbols selected: `26`.

## Walk-Forward Design

- Train days: `365`; purge days: `10`; test days: `90`; step days: `90`.
- Candidate families: `mean_reversion`.
- Sessions: `us_rth`.
- Max fold candidates: `1`.
- Train gates: trades >= `30`, PF >= `1.08`, max DD <= `5000.0`.
- Test gates: trades >= `5`, PF >= `1.05`, max DD <= `2000.0`.

## Summary

- Fold rows: `0`.
- Aggregated candidates: `0`.
- Test-pass fold rows: `0`.
