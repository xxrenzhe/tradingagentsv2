# NQ Bar-Only Best Strategy Walk-Forward Search

## Verdict

Best long-history bar-only candidate: `bar_best_mean_reversion_lb30_thr1_hold30_us_rth` with `10929.5000` future test net points, `85.71%` positive selected folds, `1.1090` average test PF, and `2.7169` net/DD.

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
- Max fold candidates: `8`.
- Train gates: trades >= `40`, PF >= `0.98`, max DD <= `10000.0`.
- Test gates: trades >= `8`, PF >= `1.0`, max DD <= `5000.0`.

## Summary

- Fold rows: `135`.
- Aggregated candidates: `36`.
- Test-pass fold rows: `48`.

## Top Aggregated Candidates

| candidate | selected_folds | stable_candidate | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points | long_history_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 7 | True | 0.8571 | 0.8571 | 4370 | 10929.5000 | 4022.7500 | 2.7169 | 1.1090 | 0.5112 | -2063.8750 | 12.5553 |
| bar_best_mean_reversion_lb10_thr0.6_hold30_us_rth | 12 | True | 0.8333 | 0.8333 | 8455 | 4082.8750 | 3714.6250 | 1.0991 | 1.0269 | 0.4894 | -3058.7500 | 4.8170 |
| bar_best_mean_reversion_lb15_thr0.6_hold15_us_rth | 3 | True | 0.6667 | 0.6667 | 3460 | 945.7500 | 2798.3750 | 0.3380 | 1.0211 | 0.4990 | -428.7500 | 1.0149 |
| bar_best_mean_reversion_lb15_thr0.6_hold30_us_rth | 5 | True | 0.6000 | 0.6000 | 3335 | 17.6250 | 3047.3750 | 0.0058 | 0.9940 | 0.4975 | -1384.7500 | 0.0193 |
| bar_best_mean_reversion_lb15_thr2_hold30_us_rth | 12 | True | 0.5000 | 0.5000 | 6685 | 1922.1250 | 3122.2500 | 0.6156 | 1.0184 | 0.5081 | -2176.0000 | 2.1655 |
| bar_best_mean_reversion_lb5_thr0.6_hold30_us_rth | 9 | True | 0.4444 | 0.4444 | 6627 | -2704.3750 | 4574.1250 | -0.5912 | 0.9835 | 0.5024 | -3048.6250 | 0.0000 |
| bar_best_mean_reversion_lb10_thr1.4_hold15_us_rth | 8 | True | 0.3750 | 0.3750 | 9725 | -3049.1250 | 2618.8750 | -1.1643 | 0.9683 | 0.4903 | -2352.1250 | 0.0000 |
| bar_best_mean_reversion_lb30_thr1.4_hold30_us_rth | 6 | True | 0.3333 | 0.3333 | 3687 | 979.6250 | 2892.3750 | 0.3387 | 1.0058 | 0.4868 | -1286.1250 | 1.0462 |
| bar_best_mean_reversion_lb30_thr2_hold10_us_rth | 6 | True | 0.3333 | 0.3333 | 4639 | -1200.8750 | 1670.5000 | -0.7189 | 0.9727 | 0.5050 | -1157.6250 | 0.0000 |
| bar_best_mean_reversion_lb15_thr1.4_hold30_us_rth | 6 | True | 0.3333 | 0.3333 | 4040 | -6020.5000 | 4260.6250 | -1.4131 | 0.9384 | 0.4836 | -2945.5000 | 0.0000 |
| bar_best_mean_reversion_lb15_thr2_hold15_us_rth | 4 | True | 0.2500 | 0.2500 | 3420 | -3251.0000 | 2586.1250 | -1.2571 | 0.9224 | 0.4831 | -1923.3750 | 0.0000 |
| bar_best_mean_reversion_lb10_thr1.4_hold5_us_rth | 5 | True | 0.2000 | 0.2000 | 11813 | -1846.6250 | 1576.8750 | -1.1711 | 0.9747 | 0.4859 | -1473.2500 | 0.0000 |
| bar_best_mean_reversion_lb30_thr2_hold30_us_rth | 7 | True | 0.1429 | 0.1429 | 3585 | -4305.8750 | 2823.1250 | -1.5252 | 0.9380 | 0.4959 | -1828.1250 | 0.0000 |
| bar_best_mean_reversion_lb30_thr2_hold15_us_rth | 4 | True | 0.0000 | 0.0000 | 2781 | -2105.6250 | 1650.1250 | -1.2760 | 0.9340 | 0.4908 | -980.2500 | 0.0000 |
| bar_best_mean_reversion_lb5_thr1.4_hold30_us_rth | 3 | True | 0.0000 | 0.0000 | 2142 | -3087.2500 | 2636.6250 | -1.1709 | 0.9251 | 0.4820 | -1434.6250 | 0.0000 |
| bar_best_mean_reversion_lb10_thr0.6_hold10_us_rth | 3 | True | 0.0000 | 0.0000 | 5002 | -3427.5000 | 2988.8750 | -1.1468 | 0.9516 | 0.4868 | -1948.1250 | 0.0000 |
| bar_best_mean_reversion_lb10_thr1_hold30_us_rth | 4 | True | 0.0000 | 0.0000 | 2866 | -4468.5000 | 2362.7500 | -1.8912 | 0.8913 | 0.4829 | -1681.7500 | 0.0000 |
| bar_best_mean_reversion_lb10_thr2_hold30_us_rth | 5 | True | 0.0000 | 0.0000 | 2655 | -7195.8750 | 5192.2500 | -1.3859 | 0.9128 | 0.5070 | -4781.7500 | 0.0000 |
| bar_best_mean_reversion_lb30_thr0.6_hold30_us_rth | 1 | False | 1.0000 | 1.0000 | 588 | 3547.2500 | 1812.7500 | 1.9568 | 1.2733 | 0.5306 | 3547.2500 | 3.7371 |
| bar_best_mean_reversion_lb30_thr1_hold15_us_rth | 1 | False | 1.0000 | 1.0000 | 968 | 2728.7500 | 1145.1250 | 2.3829 | 1.1716 | 0.5145 | 2728.7500 | 2.9713 |
| bar_best_mean_reversion_lb15_thr1_hold10_us_rth | 1 | False | 1.0000 | 1.0000 | 1513 | 142.8750 | 1529.5000 | 0.0934 | 1.0067 | 0.4924 | 142.8750 | 0.1524 |
| bar_best_mean_reversion_lb15_thr1_hold15_us_rth | 2 | False | 0.5000 | 0.5000 | 2375 | 713.1250 | 3207.5000 | 0.2223 | 1.0191 | 0.4946 | -360.7500 | 0.7348 |
| bar_best_mean_reversion_lb5_thr1.4_hold15_us_rth | 2 | False | 0.5000 | 0.5000 | 2546 | -1195.5000 | 3121.6250 | -0.3830 | 0.9764 | 0.4986 | -2583.1250 | 0.0000 |
| bar_best_mean_reversion_lb10_thr2_hold15_us_rth | 1 | False | 0.0000 | 0.0000 | 810 | -264.0000 | 967.5000 | -0.2729 | 0.9603 | 0.5123 | -264.0000 | 0.0000 |
| bar_best_mean_reversion_lb10_thr1.4_hold10_us_rth | 1 | False | 0.0000 | 0.0000 | 1609 | -768.6250 | 1546.6250 | -0.4970 | 0.9503 | 0.4730 | -768.6250 | 0.0000 |

## Top Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate | test_max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 20 | 4 | 2551 | 5310.1250 | 1.0887 | 606 | 4397.2500 | 1.3141 | 0.5578 | 1670.7500 |
| True | bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 16 | 3 | 2522 | 2279.5000 | 1.0514 | 598 | 3823.2500 | 1.2746 | 0.4933 | 1077.1250 |
| True | bar_best_mean_reversion_lb30_thr0.6_hold30_us_rth | 20 | 7 | 2428 | 2169.5000 | 1.0364 | 588 | 3547.2500 | 1.2733 | 0.5306 | 1812.7500 |
| True | bar_best_mean_reversion_lb30_thr1_hold30_us_rth | 17 | 2 | 2525 | 5130.1250 | 1.1058 | 626 | 3366.0000 | 1.1821 | 0.5032 | 1607.3750 |
| True | bar_best_mean_reversion_lb10_thr1.4_hold15_us_rth | 7 | 4 | 4991 | 313.3750 | 1.0045 | 1230 | 3023.0000 | 1.1996 | 0.5236 | 849.3750 |
| True | bar_best_mean_reversion_lb30_thr1.4_hold30_us_rth | 17 | 8 | 2458 | 660.2500 | 1.0133 | 610 | 2873.0000 | 1.1603 | 0.5049 | 2194.2500 |
| True | bar_best_mean_reversion_lb30_thr1_hold15_us_rth | 20 | 3 | 4113 | 4025.6250 | 1.0595 | 968 | 2728.7500 | 1.1716 | 0.5145 | 1145.1250 |
| True | bar_best_mean_reversion_lb15_thr2_hold30_us_rth | 4 | 5 | 2278 | 383.0000 | 1.0122 | 579 | 2564.6250 | 1.1786 | 0.5406 | 936.6250 |
| True | bar_best_mean_reversion_lb15_thr2_hold30_us_rth | 15 | 1 | 2249 | 4081.8750 | 1.1148 | 569 | 2230.3750 | 1.2424 | 0.5483 | 1309.1250 |
| True | bar_best_mean_reversion_lb10_thr0.6_hold30_us_rth | 17 | 3 | 2849 | 2833.1250 | 1.0508 | 699 | 2203.3750 | 1.1042 | 0.5064 | 2686.3750 |
| True | bar_best_mean_reversion_lb10_thr0.6_hold30_us_rth | 15 | 6 | 2854 | 802.5000 | 1.0173 | 715 | 1831.1250 | 1.1555 | 0.5147 | 1033.7500 |
| True | bar_best_mean_reversion_lb10_thr0.6_hold30_us_rth | 16 | 4 | 2857 | 1846.8750 | 1.0371 | 678 | 1784.7500 | 1.1005 | 0.5000 | 2097.2500 |
| True | bar_best_mean_reversion_lb15_thr0.6_hold30_us_rth | 20 | 8 | 2730 | 1342.2500 | 1.0195 | 651 | 1671.3750 | 1.1030 | 0.5346 | 1908.7500 |
| True | bar_best_mean_reversion_lb15_thr2_hold30_us_rth | 14 | 4 | 2258 | 1724.5000 | 1.0520 | 555 | 1669.3750 | 1.1414 | 0.4901 | 926.0000 |
| True | bar_best_mean_reversion_lb10_thr0.6_hold30_us_rth | 10 | 5 | 2849 | 465.8750 | 1.0097 | 702 | 1568.5000 | 1.1642 | 0.5199 | 814.3750 |
| True | bar_best_mean_reversion_lb30_thr2_hold10_us_rth | 19 | 8 | 3125 | 1227.1250 | 1.0289 | 758 | 1417.5000 | 1.1311 | 0.5290 | 1670.5000 |
| True | bar_best_mean_reversion_lb5_thr1.4_hold15_us_rth | 4 | 4 | 5069 | 520.1250 | 1.0108 | 1295 | 1387.6250 | 1.0664 | 0.5112 | 1239.7500 |
| True | bar_best_mean_reversion_lb30_thr2_hold30_us_rth | 3 | 3 | 2091 | 438.8750 | 1.0152 | 507 | 1234.3750 | 1.1521 | 0.5266 | 1059.8750 |
| True | bar_best_mean_reversion_lb15_thr1_hold15_us_rth | 20 | 1 | 4810 | 4350.7500 | 1.0560 | 1149 | 1073.8750 | 1.0563 | 0.4891 | 1283.1250 |
| True | bar_best_mean_reversion_lb5_thr0.6_hold30_us_rth | 5 | 4 | 3030 | 1693.2500 | 1.0353 | 743 | 1054.3750 | 1.0594 | 0.5410 | 3006.0000 |
| True | bar_best_mean_reversion_lb5_thr0.6_hold30_us_rth | 6 | 1 | 3026 | 5916.5000 | 1.1095 | 744 | 1010.5000 | 1.0744 | 0.4960 | 948.8750 |
| True | bar_best_mean_reversion_lb15_thr0.6_hold15_us_rth | 19 | 5 | 4633 | 2551.8750 | 1.0347 | 1181 | 871.3750 | 1.0473 | 0.4945 | 2798.3750 |
| True | bar_best_mean_reversion_lb15_thr0.6_hold30_us_rth | 16 | 8 | 2725 | 685.6250 | 1.0143 | 644 | 850.0000 | 1.0481 | 0.4829 | 2682.3750 |
| True | bar_best_mean_reversion_lb15_thr2_hold30_us_rth | 0 | 4 | 2186 | 2419.0000 | 1.0745 | 554 | 623.2500 | 1.0666 | 0.5487 | 1030.2500 |
| True | bar_best_mean_reversion_lb10_thr1.4_hold15_us_rth | 6 | 2 | 4998 | 1764.5000 | 1.0284 | 1227 | 554.6250 | 1.0351 | 0.4906 | 1248.6250 |
