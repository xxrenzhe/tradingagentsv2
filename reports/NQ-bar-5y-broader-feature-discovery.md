# NQ Bar-Only Best Strategy Walk-Forward Search

## Verdict

Best long-history bar-only candidate: `bar_best_vwap_reclaim_lb30_thr0.0002_hold30_us_late` with `4006.5000` future test net points, `80.00%` positive selected folds, `1.3542` average test PF, and `2.9306` net/DD.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Continuous construction: one NQ futures row per minute, selected by highest reported volume.
- Feature span: `2021-04-28 00:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Feature rows: `1,769,740`.
- Distinct symbols selected: `21`.

## Walk-Forward Design

- Train days: `365`; purge days: `10`; test days: `90`; step days: `90`.
- Candidate families: `mean_reversion, vwap_reclaim`.
- Sessions: `europe, us_rth, us_late`.
- Max fold candidates: `5`.
- Train gates: trades >= `120`, PF >= `1.05`, max DD <= `8000.0`.
- Test gates: trades >= `20`, PF >= `1.02`, max DD <= `5000.0`.

## Summary

- Fold rows: `80`.
- Aggregated candidates: `46`.
- Test-pass fold rows: `28`.

## Top Aggregated Candidates

| candidate | selected_folds | stable_candidate | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points | long_history_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bar_best_vwap_reclaim_lb30_thr0.0002_hold30_us_late | 5 | True | 0.8000 | 0.8000 | 614 | 4006.5000 | 1367.1250 | 2.9306 | 1.3542 | 0.5291 | -276.3750 | 5.1748 |
| bar_best_mean_reversion_lb30_thr1.4_hold60_us_late | 3 | True | 0.6667 | 0.6667 | 306 | 2155.2500 | 2409.6250 | 0.8944 | 1.1287 | 0.5285 | -1961.0000 | 2.3416 |
| bar_best_vwap_reclaim_lb30_thr0.0005_hold30_us_late | 3 | True | 0.6667 | 0.6667 | 372 | 1681.7500 | 677.8750 | 2.4809 | 1.2306 | 0.5322 | -276.3750 | 2.1571 |
| bar_best_vwap_reclaim_lb30_thr0.001_hold30_us_late | 3 | True | 0.6667 | 0.6667 | 372 | 1578.0000 | 677.8750 | 2.3279 | 1.2151 | 0.5322 | -276.3750 | 2.0352 |
| bar_best_mean_reversion_lb30_thr2_hold60_us_late | 3 | True | 0.6667 | 0.6667 | 269 | -686.8750 | 2395.5000 | -0.2867 | 0.9613 | 0.4799 | -1514.5000 | 0.0000 |
| bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 3 | True | 0.6667 | 0.3333 | 1873 | 119.1250 | 4022.7500 | 0.0296 | 1.0298 | 0.5086 | -1821.5000 | 0.1250 |
| bar_best_mean_reversion_lb30_thr1.4_hold30_us_late | 4 | True | 0.5000 | 0.5000 | 662 | 144.2500 | 2394.8750 | 0.0602 | 1.0096 | 0.5132 | -1063.8750 | 0.1562 |
| bar_best_vwap_reclaim_lb60_thr0.001_hold15_us_late | 3 | True | 0.3333 | 0.3333 | 291 | 210.6250 | 1682.7500 | 0.1252 | 3.7021 | 0.4991 | -1008.3750 | 0.2236 |
| bar_best_vwap_reclaim_lb30_thr0.001_hold15_us_late | 3 | True | 0.3333 | 0.3333 | 514 | -1368.2500 | 1316.5000 | -1.0393 | 0.8211 | 0.4566 | -1122.0000 | 0.0000 |
| bar_best_mean_reversion_lb60_thr1.4_hold30_us_rth | 3 | True | 0.3333 | 0.0000 | 1510 | -1492.0000 | 2870.5000 | -0.5198 | 0.9522 | 0.5039 | -1017.8750 | 0.0000 |
| bar_best_mean_reversion_lb60_thr2_hold60_us_late | 1 | False | 1.0000 | 1.0000 | 71 | 643.3750 | 1257.8750 | 0.5115 | 1.1366 | 0.4930 | 643.3750 | 0.6953 |
| bar_best_mean_reversion_lb60_thr1_hold60_us_late | 1 | False | 1.0000 | 1.0000 | 82 | 247.5000 | 844.2500 | 0.2932 | 1.1072 | 0.5488 | 247.5000 | 0.2773 |
| bar_best_mean_reversion_lb15_thr2_hold60_us_rth | 1 | False | 1.0000 | 0.0000 | 340 | 328.0000 | 3432.7500 | 0.0956 | 1.0199 | 0.5118 | 328.0000 | 0.3377 |
| bar_best_mean_reversion_lb15_thr1.4_hold60_us_rth | 1 | False | 1.0000 | 0.0000 | 358 | 54.5000 | 613.2500 | 0.0889 | 1.0076 | 0.4916 | 54.5000 | 0.0635 |
| bar_best_vwap_reclaim_lb60_thr0.0002_hold15_us_late | 2 | False | 0.5000 | 0.5000 | 186 | 1219.0000 | 1682.7500 | 0.7244 | 5.2292 | 0.5344 | -778.3750 | 1.2975 |
| bar_best_vwap_reclaim_lb60_thr0.0005_hold15_us_late | 2 | False | 0.5000 | 0.5000 | 186 | 1219.0000 | 1682.7500 | 0.7244 | 5.2292 | 0.5344 | -778.3750 | 1.2975 |
| bar_best_mean_reversion_lb15_thr2_hold30_us_rth | 2 | False | 0.5000 | 0.5000 | 1111 | 354.6250 | 3046.0000 | 0.1164 | 0.9936 | 0.5105 | -1093.5000 | 0.3660 |
| bar_best_vwap_reclaim_lb30_thr0.0002_hold15_us_late | 2 | False | 0.5000 | 0.5000 | 340 | 289.5000 | 1316.5000 | 0.2199 | 1.1473 | 0.4657 | -1122.0000 | 0.3129 |
| bar_best_mean_reversion_lb60_thr2_hold30_us_rth | 2 | False | 0.5000 | 0.5000 | 767 | 47.3750 | 1477.8750 | 0.0321 | 1.0115 | 0.4915 | -286.5000 | 0.0504 |
| bar_best_mean_reversion_lb60_thr1.4_hold30_us_late | 2 | False | 0.5000 | 0.5000 | 256 | -277.5000 | 1935.7500 | -0.1434 | 0.9840 | 0.4880 | -815.8750 | 0.0000 |
| bar_best_mean_reversion_lb60_thr0.6_hold60_europe | 2 | False | 0.5000 | 0.5000 | 644 | -369.2500 | 2374.6250 | -0.1555 | 1.0022 | 0.5158 | -1990.0000 | 0.0000 |
| bar_best_mean_reversion_lb60_thr0.6_hold60_us_late | 2 | False | 0.5000 | 0.5000 | 167 | -561.8750 | 1975.6250 | -0.2844 | 0.9265 | 0.5095 | -993.1250 | 0.0000 |
| bar_best_mean_reversion_lb15_thr0.6_hold30_europe | 2 | False | 0.5000 | 0.5000 | 1364 | -1129.0000 | 4024.8750 | -0.2805 | 0.9359 | 0.4786 | -3334.3750 | 0.0000 |
| bar_best_vwap_reclaim_lb60_thr0.0005_hold30_us_late | 1 | False | 0.0000 | 0.0000 | 80 | -162.5000 | 2053.3750 | -0.0791 | 0.9394 | 0.5625 | -162.5000 | 0.0000 |
| bar_best_vwap_reclaim_lb60_thr0.001_hold30_us_late | 1 | False | 0.0000 | 0.0000 | 81 | -288.8750 | 858.0000 | -0.3367 | 0.8731 | 0.4691 | -288.8750 | 0.0000 |

## Top Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate | test_max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | bar_best_mean_reversion_lb30_thr1.4_hold60_us_late | 15 | 2 | 401 | 7314.8750 | 1.3549 | 103 | 2484.6250 | 1.4028 | 0.6019 | 1334.3750 |
| True | bar_best_mean_reversion_lb15_thr0.6_hold30_europe | 12 | 2 | 2785 | 5589.6250 | 1.1339 | 673 | 2205.3750 | 1.2077 | 0.4681 | 810.2500 |
| True | bar_best_vwap_reclaim_lb30_thr0.0002_hold30_us_late | 6 | 5 | 504 | 2099.2500 | 1.1695 | 124 | 2088.7500 | 2.0280 | 0.5403 | 611.0000 |
| True | bar_best_vwap_reclaim_lb60_thr0.0002_hold15_us_late | 8 | 2 | 377 | 3697.3750 | 1.9069 | 89 | 1997.3750 | 9.7652 | 0.5843 | 47.1250 |
| True | bar_best_vwap_reclaim_lb60_thr0.0005_hold15_us_late | 8 | 3 | 377 | 3697.3750 | 1.9069 | 89 | 1997.3750 | 9.7652 | 0.5843 | 47.1250 |
| True | bar_best_vwap_reclaim_lb60_thr0.001_hold15_us_late | 8 | 4 | 377 | 3697.3750 | 1.9069 | 89 | 1997.3750 | 9.7652 | 0.5843 | 47.1250 |
| True | bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 13 | 1 | 2524 | 8431.0000 | 1.1422 | 645 | 1893.1250 | 1.1912 | 0.5194 | 1068.7500 |
| True | bar_best_mean_reversion_lb30_thr1.4_hold60_us_late | 7 | 1 | 411 | 3944.3750 | 1.3237 | 103 | 1631.6250 | 1.4180 | 0.5437 | 874.5000 |
| True | bar_best_mean_reversion_lb60_thr0.6_hold60_europe | 3 | 1 | 1276 | 5191.7500 | 1.1615 | 320 | 1620.7500 | 1.3322 | 0.5531 | 924.2500 |
| True | bar_best_mean_reversion_lb15_thr2_hold30_us_rth | 11 | 5 | 2258 | 7116.2500 | 1.1832 | 569 | 1448.1250 | 1.0787 | 0.5026 | 3046.0000 |
| True | bar_best_mean_reversion_lb30_thr1.4_hold30_us_late | 0 | 1 | 646 | 4382.5000 | 1.2794 | 165 | 1430.8750 | 1.2630 | 0.4909 | 1403.7500 |
| True | bar_best_vwap_reclaim_lb30_thr0.0002_hold15_us_late | 4 | 5 | 686 | 2814.5000 | 1.2891 | 164 | 1411.5000 | 1.6941 | 0.4939 | 375.0000 |
| True | bar_best_vwap_reclaim_lb30_thr0.0002_hold30_us_late | 4 | 2 | 508 | 3754.2500 | 1.2445 | 123 | 1328.3750 | 1.5932 | 0.5285 | 509.6250 |
| True | bar_best_vwap_reclaim_lb30_thr0.0005_hold30_us_late | 4 | 3 | 508 | 3754.2500 | 1.2445 | 123 | 1328.3750 | 1.5932 | 0.5285 | 509.6250 |
| True | bar_best_vwap_reclaim_lb30_thr0.001_hold30_us_late | 4 | 4 | 508 | 3754.2500 | 1.2445 | 123 | 1224.6250 | 1.5469 | 0.5285 | 613.3750 |
| True | bar_best_mean_reversion_lb30_thr2_hold60_us_late | 0 | 3 | 348 | 4440.0000 | 1.3475 | 87 | 744.6250 | 1.1598 | 0.5057 | 1747.6250 |
| True | bar_best_mean_reversion_lb60_thr2_hold60_us_late | 15 | 1 | 284 | 5629.5000 | 1.3078 | 71 | 643.3750 | 1.1366 | 0.4930 | 1257.8750 |
| True | bar_best_vwap_reclaim_lb30_thr0.0002_hold30_us_late | 7 | 3 | 507 | 2882.6250 | 1.2646 | 124 | 629.7500 | 1.1823 | 0.5323 | 677.8750 |
| True | bar_best_vwap_reclaim_lb30_thr0.0005_hold30_us_late | 7 | 4 | 507 | 2882.6250 | 1.2646 | 124 | 629.7500 | 1.1823 | 0.5323 | 677.8750 |
| True | bar_best_vwap_reclaim_lb30_thr0.001_hold30_us_late | 7 | 5 | 507 | 2778.8750 | 1.2551 | 124 | 629.7500 | 1.1823 | 0.5323 | 677.8750 |
| True | bar_best_mean_reversion_lb60_thr1.4_hold30_us_late | 0 | 4 | 490 | 2834.7500 | 1.2743 | 127 | 538.3750 | 1.1619 | 0.4488 | 1138.5000 |
| True | bar_best_vwap_reclaim_lb30_thr0.001_hold15_us_late | 2 | 5 | 668 | 3843.2500 | 1.3668 | 156 | 515.2500 | 1.1889 | 0.4872 | 884.5000 |
| True | bar_best_mean_reversion_lb30_thr1.4_hold30_us_late | 7 | 2 | 658 | 4248.7500 | 1.3245 | 171 | 487.6250 | 1.1072 | 0.5029 | 1425.6250 |
| True | bar_best_mean_reversion_lb60_thr0.6_hold60_us_late | 12 | 5 | 347 | 3885.3750 | 1.2470 | 82 | 431.2500 | 1.0947 | 0.5366 | 1975.6250 |
| True | bar_best_mean_reversion_lb60_thr2_hold30_us_rth | 6 | 3 | 1575 | 2925.6250 | 1.1127 | 387 | 333.8750 | 1.0684 | 0.4961 | 542.6250 |
