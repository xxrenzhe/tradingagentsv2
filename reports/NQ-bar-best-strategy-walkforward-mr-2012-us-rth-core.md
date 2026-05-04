# NQ Bar-Only Best Strategy Walk-Forward Search

## Verdict

Best long-history bar-only candidate: `bar_best_mean_reversion_lb30_thr1_hold30_us_rth` with `9544.0000` future test net points, `100.00%` positive selected folds, `1.1152` average test PF, and `2.4440` net/DD.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Continuous construction: one NQ futures row per minute, selected by highest reported volume.
- Feature span: `2010-06-06 22:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Feature rows: `5,383,225`.
- Distinct symbols selected: `40`.

## Walk-Forward Design

- Train days: `365`; purge days: `10`; test days: `90`; step days: `90`.
- Candidate families: `mean_reversion`.
- Sessions: `us_rth`.
- Max fold candidates: `5`.
- Train gates: trades >= `120`, PF >= `1.05`, max DD <= `8000.0`.
- Test gates: trades >= `20`, PF >= `1.02`, max DD <= `5000.0`.

## Summary

- Fold rows: `10`.
- Aggregated candidates: `5`.
- Test-pass fold rows: `6`.

## Top Aggregated Candidates

| candidate | selected_folds | stable_candidate | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points | long_history_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 5 | True | 1.0000 | 1.0000 | 3146 | 9544.0000 | 3905.1250 | 2.4440 | 1.1152 | 0.5158 | 277.5000 | 10.8220 |
| bar_best_mean_reversion_lb30_thr0.6_hold30_us_rth | 1 | False | 1.0000 | 1.0000 | 594 | 3357.5000 | 1812.7500 | 1.8522 | 1.2166 | 0.5236 | 3357.5000 | 3.5351 |
| bar_best_mean_reversion_lb15_thr1_hold15_us_rth | 1 | False | 0.0000 | 0.0000 | 1184 | -546.0000 | 2837.2500 | -0.1924 | 0.9767 | 0.4890 | -546.0000 | 0.0000 |
| bar_best_mean_reversion_lb30_thr1_hold15_us_rth | 1 | False | 0.0000 | 0.0000 | 978 | -1017.7500 | 2805.5000 | -0.3628 | 0.9492 | 0.4928 | -1017.7500 | 0.0000 |
| bar_best_mean_reversion_lb15_thr0.6_hold30_us_rth | 2 | False | 0.0000 | 0.0000 | 1352 | -2810.0000 | 2606.6250 | -1.0780 | 0.9210 | 0.4970 | -1529.5000 | 0.0000 |

## Top Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate | test_max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 53 | 1 | 2512 | 3872.2500 | 1.0839 | 622 | 5592.0000 | 1.2956 | 0.5161 | 1607.3750 |
| True | bar_best_mean_reversion_lb30_thr0.6_hold30_us_rth | 57 | 4 | 2425 | 4792.3750 | 1.0835 | 594 | 3357.5000 | 1.2166 | 0.5236 | 1812.7500 |
| True | bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 54 | 1 | 2530 | 8926.7500 | 1.1613 | 622 | 1502.7500 | 1.1294 | 0.5209 | 1713.6250 |
| True | bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 57 | 2 | 2546 | 6252.7500 | 1.1043 | 625 | 1283.8750 | 1.0717 | 0.5152 | 1670.7500 |
| True | bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 56 | 1 | 2540 | 8527.2500 | 1.1580 | 619 | 887.8750 | 1.0566 | 0.5267 | 3905.1250 |
| True | bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 55 | 1 | 2523 | 8046.3750 | 1.1350 | 658 | 277.5000 | 1.0225 | 0.5000 | 1507.7500 |
| False | bar_best_mean_reversion_lb15_thr1_hold15_us_rth | 57 | 3 | 4797 | 4875.1250 | 1.0636 | 1184 | -546.0000 | 0.9767 | 0.4890 | 2837.2500 |
| False | bar_best_mean_reversion_lb30_thr1_hold15_us_rth | 57 | 1 | 4095 | 5809.1250 | 1.0874 | 978 | -1017.7500 | 0.9492 | 0.4928 | 2805.5000 |
| False | bar_best_mean_reversion_lb15_thr0.6_hold30_us_rth | 57 | 5 | 2726 | 3680.7500 | 1.0551 | 668 | -1280.5000 | 0.9362 | 0.4955 | 2351.7500 |
| False | bar_best_mean_reversion_lb15_thr0.6_hold30_us_rth | 51 | 1 | 2735 | 2414.6250 | 1.0604 | 684 | -1529.5000 | 0.9057 | 0.4985 | 2606.6250 |
