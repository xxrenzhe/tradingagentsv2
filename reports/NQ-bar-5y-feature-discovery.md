# NQ Bar-Only Best Strategy Walk-Forward Search

## Verdict

Best long-history bar-only candidate: `bar_best_mean_reversion_lb30_thr1_hold30_us_rth` with `10694.3750` future test net points, `80.00%` positive selected folds, `1.1384` average test PF, and `2.6585` net/DD.

This is still a research candidate, not live-ready: pass fold rate is below the conservative 80% target.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Continuous construction: one NQ futures row per minute, selected by highest reported volume.
- Feature span: `2021-04-28 00:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Feature rows: `1,769,740`.
- Distinct symbols selected: `21`.

## Walk-Forward Design

- Train days: `365`; purge days: `10`; test days: `90`; step days: `90`.
- Candidate families: `mean_reversion`.
- Sessions: `us_rth`.
- Max fold candidates: `5`.
- Train gates: trades >= `120`, PF >= `1.05`, max DD <= `8000.0`.
- Test gates: trades >= `20`, PF >= `1.02`, max DD <= `5000.0`.

## Summary

- Fold rows: `37`.
- Aggregated candidates: `13`.
- Test-pass fold rows: `15`.

## Top Aggregated Candidates

| candidate | selected_folds | stable_candidate | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points | long_history_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 5 | True | 0.8000 | 0.6000 | 3137 | 10694.3750 | 4022.7500 | 2.6585 | 1.1384 | 0.5157 | -1821.5000 | 11.7583 |
| bar_best_mean_reversion_lb15_thr1.4_hold60_us_rth | 7 | True | 0.7143 | 0.4286 | 2558 | 443.2500 | 3143.0000 | 0.1410 | 0.9995 | 0.5013 | -2156.0000 | 0.5133 |
| bar_best_mean_reversion_lb60_thr1.4_hold30_us_rth | 4 | True | 0.5000 | 0.2500 | 2033 | 3335.1250 | 2870.5000 | 1.1619 | 1.0401 | 0.4984 | -1017.8750 | 3.5609 |
| bar_best_mean_reversion_lb60_thr1.4_hold60_us_rth | 7 | True | 0.2857 | 0.2857 | 2216 | -3830.5000 | 2946.6250 | -1.3000 | 0.9299 | 0.4849 | -2517.1250 | 0.0000 |
| bar_best_mean_reversion_lb60_thr1_hold30_us_rth | 3 | True | 0.0000 | 0.0000 | 1585 | -3101.3750 | 2614.1250 | -1.1864 | 0.9210 | 0.4941 | -1282.6250 | 0.0000 |
| bar_best_mean_reversion_lb30_thr0.6_hold30_us_rth | 1 | False | 1.0000 | 1.0000 | 598 | 5359.2500 | 1812.7500 | 2.9564 | 1.3603 | 0.5435 | 5359.2500 | 5.6403 |
| bar_best_mean_reversion_lb30_thr1.4_hold60_us_rth | 2 | False | 1.0000 | 1.0000 | 693 | 2751.8750 | 2028.8750 | 1.3564 | 1.1154 | 0.5096 | 291.5000 | 3.0563 |
| bar_best_mean_reversion_lb30_thr1_hold15_us_rth | 1 | False | 1.0000 | 1.0000 | 989 | 904.1250 | 1855.7500 | 0.4872 | 1.0470 | 0.5167 | 904.1250 | 0.9610 |
| bar_best_mean_reversion_lb60_thr1_hold60_us_rth | 2 | False | 1.0000 | 1.0000 | 643 | 694.6250 | 2525.5000 | 0.2750 | 1.0259 | 0.4961 | 335.5000 | 0.7505 |
| bar_best_mean_reversion_lb15_thr0.6_hold15_us_rth | 1 | False | 1.0000 | 0.0000 | 1178 | 166.2500 | 977.3750 | 0.1701 | 1.0128 | 0.4847 | 166.2500 | 0.1835 |
| bar_best_mean_reversion_lb30_thr1_hold60_us_rth | 2 | False | 0.5000 | 0.0000 | 714 | -280.0000 | 3231.3750 | -0.0867 | 0.9800 | 0.4831 | -441.8750 | 0.0000 |
| bar_best_mean_reversion_lb15_thr0.6_hold60_us_rth | 1 | False | 0.0000 | 0.0000 | 372 | -171.0000 | 2806.8750 | -0.0609 | 0.9848 | 0.4704 | -171.0000 | 0.0000 |
| bar_best_mean_reversion_lb15_thr0.6_hold30_us_rth | 1 | False | 0.0000 | 0.0000 | 685 | -1502.3750 | 2698.8750 | -0.5567 | 0.9119 | 0.4964 | -1502.3750 | 0.0000 |

## Top Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate | test_max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 11 | 2 | 2531 | 2988.6250 | 1.0654 | 640 | 5998.5000 | 1.3215 | 0.5078 | 1607.3750 |
| True | bar_best_mean_reversion_lb30_thr0.6_hold30_us_rth | 15 | 5 | 2417 | 4695.8750 | 1.0814 | 598 | 5359.2500 | 1.3603 | 0.5435 | 1812.7500 |
| True | bar_best_mean_reversion_lb60_thr1.4_hold30_us_rth | 11 | 4 | 2096 | 2313.0000 | 1.0568 | 523 | 4827.1250 | 1.3041 | 0.4818 | 1574.8750 |
| True | bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 15 | 4 | 2535 | 5995.1250 | 1.0998 | 624 | 4576.7500 | 1.2810 | 0.5449 | 1670.7500 |
| True | bar_best_mean_reversion_lb30_thr1.4_hold60_us_rth | 14 | 4 | 1415 | 3968.3750 | 1.0876 | 339 | 2460.3750 | 1.1935 | 0.5221 | 2028.8750 |
| True | bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 13 | 1 | 2524 | 8431.0000 | 1.1422 | 645 | 1893.1250 | 1.1912 | 0.5194 | 1068.7500 |
| True | bar_best_mean_reversion_lb15_thr1.4_hold60_us_rth | 15 | 3 | 1487 | 3915.8750 | 1.0746 | 366 | 1639.2500 | 1.1035 | 0.5328 | 1618.8750 |
| True | bar_best_mean_reversion_lb60_thr1.4_hold60_us_rth | 11 | 3 | 1292 | 3305.7500 | 1.0936 | 321 | 1512.1250 | 1.0947 | 0.4984 | 1814.8750 |
| True | bar_best_mean_reversion_lb30_thr1_hold15_us_rth | 15 | 2 | 4084 | 5792.0000 | 1.0867 | 989 | 904.1250 | 1.0470 | 0.5167 | 1855.7500 |
| True | bar_best_mean_reversion_lb60_thr1.4_hold60_us_rth | 2 | 1 | 1300 | 2720.7500 | 1.0669 | 309 | 863.1250 | 1.1146 | 0.5340 | 1099.7500 |
| True | bar_best_mean_reversion_lb15_thr1.4_hold60_us_rth | 4 | 1 | 1493 | 3802.6250 | 1.0902 | 370 | 511.7500 | 1.0712 | 0.5000 | 881.7500 |
| True | bar_best_mean_reversion_lb60_thr1_hold60_us_rth | 15 | 1 | 1301 | 4444.8750 | 1.0972 | 325 | 359.1250 | 1.0248 | 0.4985 | 2525.5000 |
| True | bar_best_mean_reversion_lb60_thr1_hold60_us_rth | 14 | 3 | 1301 | 3911.3750 | 1.0923 | 318 | 335.5000 | 1.0270 | 0.4937 | 2019.6250 |
| True | bar_best_mean_reversion_lb30_thr1.4_hold60_us_rth | 13 | 4 | 1424 | 3686.2500 | 1.0736 | 354 | 291.5000 | 1.0374 | 0.4972 | 965.3750 |
| True | bar_best_mean_reversion_lb15_thr1.4_hold60_us_rth | 3 | 2 | 1498 | 4122.5000 | 1.0866 | 373 | 233.1250 | 1.0267 | 0.4772 | 822.6250 |
| False | bar_best_mean_reversion_lb15_thr1.4_hold60_us_rth | 14 | 5 | 1487 | 3103.6250 | 1.0640 | 360 | 215.7500 | 1.0149 | 0.5333 | 2245.0000 |
| False | bar_best_mean_reversion_lb60_thr1.4_hold30_us_rth | 12 | 2 | 2083 | 5784.1250 | 1.1260 | 488 | 200.7500 | 1.0179 | 0.5246 | 1519.7500 |
| False | bar_best_mean_reversion_lb15_thr0.6_hold15_us_rth | 13 | 5 | 4618 | 4149.0000 | 1.0539 | 1178 | 166.2500 | 1.0128 | 0.4847 | 977.3750 |
| False | bar_best_mean_reversion_lb30_thr1_hold60_us_rth | 0 | 1 | 1399 | 2551.8750 | 1.0743 | 353 | 161.8750 | 1.0127 | 0.4788 | 3231.3750 |
| False | bar_best_mean_reversion_lb15_thr1.4_hold60_us_rth | 6 | 1 | 1494 | 3975.5000 | 1.1201 | 358 | 54.5000 | 1.0076 | 0.4916 | 613.2500 |
| False | bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 12 | 1 | 2532 | 7046.2500 | 1.1362 | 614 | 47.5000 | 1.0036 | 0.5081 | 1713.6250 |
| False | bar_best_mean_reversion_lb15_thr1.4_hold60_us_rth | 12 | 5 | 1496 | 2638.2500 | 1.0565 | 361 | -55.1250 | 0.9953 | 0.4931 | 2079.6250 |
| False | bar_best_mean_reversion_lb15_thr0.6_hold60_us_rth | 1 | 1 | 1501 | 2784.8750 | 1.0646 | 372 | -171.0000 | 0.9848 | 0.4704 | 2806.8750 |
| False | bar_best_mean_reversion_lb60_thr1.4_hold60_us_rth | 4 | 2 | 1291 | 2147.1250 | 1.0578 | 323 | -429.3750 | 0.9321 | 0.4520 | 919.2500 |
| False | bar_best_mean_reversion_lb30_thr1_hold60_us_rth | 3 | 3 | 1436 | 3089.7500 | 1.0653 | 361 | -441.8750 | 0.9474 | 0.4875 | 2118.3750 |
