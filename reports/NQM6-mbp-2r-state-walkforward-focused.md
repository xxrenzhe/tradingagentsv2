# NQM6 State-Label Purged Walk-Forward 2R Search

Feature rows: 60,200
Date range: 2026-03-02 23:59:00+00:00 to 2026-05-01 21:00:00+00:00
Train days: 20
Purge days: 2
Test days: 5
Step days: 5
Stop-loss points: 8.0, 16.0
Horizons: 30, 60, 120
Sessions: us_late, all

## Completion Audit

- Requirement: >=60% test win rate. Gate requires `test_win_rate >= 0.60`.
- Requirement: fixed 2R. Every candidate uses `take_profit_points = 2 * stop_loss_points`.
- Requirement: black-box testing. Each fold derives state bins only from train dates, skips purge dates, then evaluates future test dates.
- Requirement: not overfit. A pass here would still need longer history and paper validation; no pass means the state-label family did not find a durable 2R edge.
- Requirement: directly live-ready. Not satisfied without broker paper fills, slippage, rejects, and order-routing checks.

Training-selected fold candidates tested: 135
Black-box passed rows: 0

## Verdict

No train-only state-label 60% win-rate fixed-2R candidate passed the black-box gate.

## Top Tested Candidates

| fold | name | train_trades | train_win_rate | train_net_points | test_trades | test_win_rate | test_net_points | test_profit_factor | test_positive_window_rate | test_bracket_exit_share | blackbox_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | state2r_short_sl16_tp32_h30_all_m\|m\|h\|l\|h\|l\|l | 47 | 0.5106 | 370.6250 | 7 | 0.5714 | 75.6250 | 2.5163 | 1.0000 | 1.0000 | False |
| 1 | state2r_short_sl16_tp32_h60_all_m\|m\|h\|l\|h\|l\|l | 47 | 0.5106 | 370.6250 | 7 | 0.5714 | 75.6250 | 2.5163 | 1.0000 | 1.0000 | False |
| 1 | state2r_short_sl16_tp32_h120_all_m\|m\|h\|l\|h\|l\|l | 47 | 0.5106 | 370.6250 | 7 | 0.5714 | 75.6250 | 2.5163 | 1.0000 | 1.0000 | False |
| 1 | state2r_short_sl16_tp32_h30_all_m\|m\|h\|m\|h\|h\|l | 65 | 0.5385 | 599.3750 | 11 | 0.5455 | 105.1250 | 2.2647 | 1.0000 | 1.0000 | False |
| 1 | state2r_short_sl16_tp32_h60_all_m\|m\|h\|m\|h\|h\|l | 65 | 0.5385 | 599.3750 | 11 | 0.5455 | 105.1250 | 2.2647 | 1.0000 | 1.0000 | False |
| 1 | state2r_short_sl16_tp32_h120_all_m\|m\|h\|m\|h\|h\|l | 65 | 0.5385 | 599.3750 | 11 | 0.5455 | 105.1250 | 2.2647 | 1.0000 | 1.0000 | False |
| 1 | state2r_short_sl8_tp16_h30_all_m\|m\|h\|m\|h\|h\|l | 65 | 0.5077 | 231.3750 | 11 | 0.5455 | 49.1250 | 2.1391 | 1.0000 | 1.0000 | False |
| 1 | state2r_short_sl8_tp16_h60_all_m\|m\|h\|m\|h\|h\|l | 65 | 0.5077 | 231.3750 | 11 | 0.5455 | 49.1250 | 2.1391 | 1.0000 | 1.0000 | False |
| 1 | state2r_short_sl8_tp16_h120_all_m\|m\|h\|m\|h\|h\|l | 65 | 0.5077 | 231.3750 | 11 | 0.5455 | 49.1250 | 2.1391 | 1.0000 | 1.0000 | False |
| 1 | state2r_short_sl16_tp32_h30_all_m\|m\|h\|l\|h\|h\|l | 12 | 0.6667 | 184.5000 | 2 | 0.5000 | 14.7500 | 1.8872 | 1.0000 | 1.0000 | False |
| 1 | state2r_short_sl16_tp32_h60_all_m\|m\|h\|l\|h\|h\|l | 12 | 0.6667 | 184.5000 | 2 | 0.5000 | 14.7500 | 1.8872 | 1.0000 | 1.0000 | False |
| 1 | state2r_short_sl16_tp32_h120_all_m\|m\|h\|l\|h\|h\|l | 12 | 0.6667 | 184.5000 | 2 | 0.5000 | 14.7500 | 1.8872 | 1.0000 | 1.0000 | False |
| 1 | state2r_short_sl8_tp16_h30_all_m\|m\|h\|l\|h\|h\|l | 12 | 0.5833 | 64.5000 | 2 | 0.5000 | 6.7500 | 1.7826 | 1.0000 | 1.0000 | False |
| 1 | state2r_short_sl8_tp16_h60_all_m\|m\|h\|l\|h\|h\|l | 12 | 0.5833 | 64.5000 | 2 | 0.5000 | 6.7500 | 1.7826 | 1.0000 | 1.0000 | False |
| 1 | state2r_short_sl8_tp16_h120_all_m\|m\|h\|l\|h\|h\|l | 12 | 0.5833 | 64.5000 | 2 | 0.5000 | 6.7500 | 1.7826 | 1.0000 | 1.0000 | False |
| 3 | state2r_short_sl16_tp32_h30_us_late_m\|m\|l\|m\|h\|l\|l | 64 | 0.4062 | 184.0000 | 49 | 0.2653 | -190.6250 | 0.6815 | 0.0000 | 1.0000 | False |
| 3 | state2r_short_sl16_tp32_h60_us_late_m\|m\|l\|m\|h\|l\|l | 64 | 0.4062 | 184.0000 | 49 | 0.2653 | -190.6250 | 0.6815 | 0.0000 | 1.0000 | False |
| 3 | state2r_short_sl16_tp32_h120_us_late_m\|m\|l\|m\|h\|l\|l | 64 | 0.4062 | 184.0000 | 49 | 0.2653 | -190.6250 | 0.6815 | 0.0000 | 1.0000 | False |
| 1 | state2r_short_sl16_tp32_h30_all_m\|h\|l\|h\|h\|l\|m | 52 | 0.4423 | 239.5000 | 39 | 0.1282 | -408.3750 | 0.2775 | 0.0000 | 1.0000 | False |
| 1 | state2r_short_sl16_tp32_h60_all_m\|h\|l\|h\|h\|l\|m | 52 | 0.4423 | 239.5000 | 39 | 0.1282 | -408.3750 | 0.2775 | 0.0000 | 1.0000 | False |
| 1 | state2r_short_sl16_tp32_h120_all_m\|h\|l\|h\|h\|l\|m | 52 | 0.4423 | 239.5000 | 39 | 0.1282 | -408.3750 | 0.2775 | 0.0000 | 1.0000 | False |
| 2 | state2r_short_sl16_tp32_h30_all_m\|m\|h\|l\|h\|h\|l | 11 | 0.7273 | 201.1250 | 21 | 0.0952 | -253.1250 | 0.1987 | 0.0000 | 1.0000 | False |
| 2 | state2r_short_sl16_tp32_h60_all_m\|m\|h\|l\|h\|h\|l | 11 | 0.7273 | 201.1250 | 21 | 0.0952 | -253.1250 | 0.1987 | 0.0000 | 1.0000 | False |
| 2 | state2r_short_sl16_tp32_h120_all_m\|m\|h\|l\|h\|h\|l | 11 | 0.7273 | 201.1250 | 21 | 0.0952 | -253.1250 | 0.1987 | 0.0000 | 1.0000 | False |
| 2 | state2r_short_sl16_tp32_h30_all_m\|m\|h\|m\|h\|l\|l | 108 | 0.5833 | 1228.5000 | 224 | 0.0580 | -3100.0000 | 0.1163 | 0.0000 | 1.0000 | False |
| 2 | state2r_short_sl16_tp32_h60_all_m\|m\|h\|m\|h\|l\|l | 108 | 0.5833 | 1228.5000 | 224 | 0.0580 | -3100.0000 | 0.1163 | 0.0000 | 1.0000 | False |
| 2 | state2r_short_sl16_tp32_h120_all_m\|m\|h\|m\|h\|l\|l | 108 | 0.5833 | 1228.5000 | 224 | 0.0580 | -3100.0000 | 0.1163 | 0.0000 | 1.0000 | False |
| 2 | state2r_short_sl8_tp16_h30_all_m\|m\|h\|m\|h\|l\|l | 108 | 0.5833 | 580.5000 | 225 | 0.0578 | -1628.6250 | 0.1093 | 0.0000 | 1.0000 | False |
| 2 | state2r_short_sl8_tp16_h60_all_m\|m\|h\|m\|h\|l\|l | 108 | 0.5833 | 580.5000 | 225 | 0.0578 | -1628.6250 | 0.1093 | 0.0000 | 1.0000 | False |
| 2 | state2r_short_sl8_tp16_h120_all_m\|m\|h\|m\|h\|l\|l | 108 | 0.5833 | 580.5000 | 225 | 0.0578 | -1628.6250 | 0.1093 | 0.0000 | 1.0000 | False |
