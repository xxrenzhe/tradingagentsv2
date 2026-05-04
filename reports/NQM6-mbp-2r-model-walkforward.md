# NQM6 Model-Based Purged Walk-Forward 2R Search

Feature rows: 60,200
Date range: 2026-03-02 23:59:00+00:00 to 2026-05-01 21:00:00+00:00
Train days: 20
Purge days: 2
Test days: 5
Step days: 5
Stop-loss points: 4.0, 8.0, 12.0, 16.0
Horizons: 30, 60, 120
Sessions: all, europe, us_rth, us_late

## Completion Audit

- Requirement: >=60% test win rate. Gate requires `test_win_rate >= 0.60`.
- Requirement: fixed 2R. Every candidate uses `take_profit_points = 2 * stop_loss_points`.
- Requirement: black-box testing. Each fold trains feature-bin model scores on prior train dates, skips purge dates, then evaluates future test dates.
- Requirement: not overfit. A pass here would still need longer history and paper validation; no pass means the current feature/model family did not find a durable 2R edge.
- Requirement: directly live-ready. Not satisfied without broker paper fills, slippage, rejects, and order-routing checks.

Training-selected fold candidates tested: 3
Black-box passed rows: 0

## Verdict

No train-only model-based 60% win-rate fixed-2R candidate passed the black-box gate.

## Top Tested Candidates

| fold | name | train_trades | train_win_rate | train_net_points | test_trades | test_win_rate | test_net_points | test_profit_factor | test_positive_window_rate | test_bracket_exit_share | blackbox_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | model2r_short_sl16_tp32_h30_us_late_q0.9 | 278 | 0.4532 | 1426.2500 | 74 | 0.1486 | -702.2500 | 0.3295 | 0.0000 | 1.0000 | False |
| 3 | model2r_short_sl16_tp32_h60_us_late_q0.9 | 278 | 0.4532 | 1426.2500 | 74 | 0.1486 | -702.2500 | 0.3295 | 0.0000 | 1.0000 | False |
| 3 | model2r_short_sl16_tp32_h120_us_late_q0.9 | 278 | 0.4532 | 1426.2500 | 74 | 0.1486 | -702.2500 | 0.3295 | 0.0000 | 1.0000 | False |
