# NQ Bar-Only 60% Fixed-2R Walk-Forward Search

## Verdict

No long-horizon bar-only NQ candidate passed the fixed-2R black-box gate.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Continuous construction: one NQ futures row per minute, selected by highest reported volume.
- Feature span: `2025-01-01 23:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Feature rows: `464,893`.
- Distinct symbols selected: `6`.

## Gates

- Train days: `90`; purge days: `3`; test days: `20`; step days: `40`.
- Minimum train/test trades: `40` / `10`.
- Train win/PF: `0.5` / `1.0`.
- Test win/PF: `0.6` / `1.0`.
- Minimum bracket exit share: `0.5`.

## Summary

- Rows tested: `2`.
- Black-box passes: `0`.
- Test trades exported: `285`.

## Top Rows

| blackbox_pass | candidate | fold | train_trades | train_win_rate | train_net_points | train_profit_factor | test_trades | test_win_rate | test_net_points | test_profit_factor | test_bracket_exit_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | bar2r_long_sl24_tp48_h60_us_rth_range_mean_30<=6.83333 | 2 | 977 | 0.5015 | 2027.3750 | 1.2024 | 115 | 0.4348 | -33.6250 | 0.9675 | 0.4000 |
| False | bar2r_long_sl24_tp48_h60_us_rth_vol_120<=0.000197919 | 2 | 976 | 0.5225 | 3221.0000 | 1.3366 | 170 | 0.4235 | 140.5000 | 1.0789 | 0.5471 |
