# NQ Bar-Only Best Strategy Walk-Forward Search

## Verdict

Best long-history bar-only candidate: `bar_best_mean_reversion_lb10_thr0.6_hold10_europe` with `-2640.0000` future test net points, `0.00%` positive selected folds, `0.8168` average test PF, and `-0.8566` net/DD.

This is still a research candidate, not live-ready: pass fold rate is below the conservative 80% target.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Continuous construction: one NQ futures row per minute, selected by highest reported volume.
- Feature span: `2010-06-06 22:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Feature rows: `5,383,225`.
- Distinct symbols selected: `40`.

## Walk-Forward Design

- Train days: `365`; purge days: `10`; test days: `90`; step days: `90`.
- Candidate families: `mean_reversion`.
- Sessions: `europe`.
- Max fold candidates: `5`.
- Train gates: trades >= `80`, PF >= `1.03`, max DD <= `8000.0`.
- Test gates: trades >= `10`, PF >= `1.01`, max DD <= `5000.0`.

## Summary

- Fold rows: `2`.
- Aggregated candidates: `2`.
- Test-pass fold rows: `0`.

## Top Aggregated Candidates

| candidate | selected_folds | stable_candidate | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points | long_history_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bar_best_mean_reversion_lb10_thr0.6_hold10_europe | 1 | False | 0.0000 | 0.0000 | 1712 | -2640.0000 | 3082.1250 | -0.8566 | 0.8168 | 0.4778 | -2640.0000 | 0.0000 |
| bar_best_mean_reversion_lb10_thr0.8_hold5_europe | 1 | False | 0.0000 | 0.0000 | 2604 | -5063.5000 | 5647.5000 | -0.8966 | 0.7223 | 0.4793 | -5063.5000 | 0.0000 |

## Top Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate | test_max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | bar_best_mean_reversion_lb10_thr0.6_hold10_europe | 42 | 1 | 6927 | 1401.3750 | 1.0339 | 1712 | -2640.0000 | 0.8168 | 0.4778 | 3082.1250 |
| False | bar_best_mean_reversion_lb10_thr0.8_hold5_europe | 56 | 1 | 10493 | 2156.3750 | 1.0366 | 2604 | -5063.5000 | 0.7223 | 0.4793 | 5647.5000 |
