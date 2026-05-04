# NQ Bar-Only 60% Fixed-2R Walk-Forward Search

## Verdict

No long-horizon bar-only NQ candidate passed the fixed-2R black-box gate.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Continuous construction: one NQ futures row per minute, selected by highest reported volume.
- Feature span: `2024-01-01 23:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Feature rows: `819,917`.
- Distinct symbols selected: `10`.

## Gates

- Train days: `180`; purge days: `5`; test days: `45`; step days: `60`.
- Minimum train/test trades: `60` / `20`.
- Train win/PF: `0.54` / `1.0`.
- Test win/PF: `0.6` / `1.05`.
- Minimum bracket exit share: `0.55`.

## Summary

- Rows tested: `0`.
- Black-box passes: `0`.
- Test trades exported: `0`.
