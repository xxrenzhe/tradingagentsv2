# NQ Bar-Only Best Strategy Walk-Forward Search

## Verdict

Best long-history bar-only candidate: `bar_best_mean_reversion_lb15_thr0.6_hold15_us_rth` with `1776.0000` future test net points, `100.00%` positive selected folds, `1.0343` average test PF, and `0.6347` net/DD.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Continuous construction: one NQ futures row per minute, selected by highest reported volume.
- Feature span: `2024-01-01 23:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Feature rows: `819,917`.
- Distinct symbols selected: `10`.

## Walk-Forward Design

- Train days: `365`; purge days: `10`; test days: `90`; step days: `90`.
- Candidate families: `mean_reversion`.
- Sessions: `us_rth`.
- Max fold candidates: `5`.
- Train gates: trades >= `20`, PF >= `0.95`, max DD <= `10000.0`.
- Test gates: trades >= `5`, PF >= `1.0`, max DD <= `5000.0`.

## Summary

- Fold rows: `8`.
- Aggregated candidates: `3`.
- Test-pass fold rows: `5`.

## Top Aggregated Candidates

| candidate | selected_folds | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points | long_history_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bar_best_mean_reversion_lb15_thr0.6_hold15_us_rth | 3 | 1.0000 | 1.0000 | 3426 | 1776.0000 | 2798.3750 | 0.6347 | 1.0343 | 0.4993 | 249.3750 | 2.2828 |
| bar_best_mean_reversion_lb15_thr1_hold15_us_rth | 2 | 0.5000 | 0.5000 | 2347 | 194.3750 | 2700.0000 | 0.0720 | 1.0054 | 0.4929 | -1008.7500 | 0.2250 |
| bar_best_mean_reversion_lb15_thr1.4_hold15_us_rth | 3 | 0.3333 | 0.3333 | 3384 | 292.5000 | 3818.1250 | 0.0766 | 1.0135 | 0.4913 | -1176.5000 | 0.3119 |

## Top Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate | test_max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | bar_best_mean_reversion_lb15_thr1.4_hold15_us_rth | 5 | 3 | 4589 | 1275.6250 | 1.0170 | 1084 | 1785.2500 | 1.1002 | 0.5028 | 1078.2500 |
| True | bar_best_mean_reversion_lb15_thr1_hold15_us_rth | 4 | 2 | 4786 | 1941.2500 | 1.0258 | 1207 | 1203.1250 | 1.0640 | 0.5087 | 2181.8750 |
| True | bar_best_mean_reversion_lb15_thr0.6_hold15_us_rth | 4 | 1 | 4614 | 1743.2500 | 1.0236 | 1159 | 851.8750 | 1.0472 | 0.4901 | 2798.3750 |
| True | bar_best_mean_reversion_lb15_thr0.6_hold15_us_rth | 5 | 1 | 4633 | 5808.8750 | 1.0788 | 1100 | 674.7500 | 1.0368 | 0.5073 | 1355.1250 |
| True | bar_best_mean_reversion_lb15_thr0.6_hold15_us_rth | 3 | 1 | 4595 | 2071.3750 | 1.0274 | 1167 | 249.3750 | 1.0189 | 0.5004 | 1386.6250 |
| False | bar_best_mean_reversion_lb15_thr1.4_hold15_us_rth | 4 | 3 | 4568 | 1542.0000 | 1.0208 | 1160 | -316.2500 | 0.9831 | 0.4940 | 2140.0000 |
| False | bar_best_mean_reversion_lb15_thr1_hold15_us_rth | 5 | 2 | 4810 | 5700.7500 | 1.0754 | 1140 | -1008.7500 | 0.9468 | 0.4772 | 2700.0000 |
| False | bar_best_mean_reversion_lb15_thr1.4_hold15_us_rth | 2 | 1 | 4579 | 2057.8750 | 1.0340 | 1140 | -1176.5000 | 0.9573 | 0.4772 | 3818.1250 |
