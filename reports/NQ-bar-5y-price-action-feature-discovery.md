# NQ Bar-Only Best Strategy Walk-Forward Search

## Verdict

Best long-history bar-only candidate: `bar_best_breakout_retest_lb10_thr0.0002_hold15_us_late` with `1574.3750` future test net points, `100.00%` positive selected folds, `1.2759` average test PF, and `2.3463` net/DD.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Continuous construction: one NQ futures row per minute, selected by highest reported volume.
- Feature span: `2021-04-28 00:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Feature rows: `1,769,740`.
- Distinct symbols selected: `21`.

## Walk-Forward Design

- Train days: `365`; purge days: `10`; test days: `90`; step days: `90`.
- Candidate families: `support_reclaim, breakout_retest`.
- Sessions: `all, europe, us_rth, us_late, asia`.
- Max fold candidates: `15`.
- Train gates: trades >= `80`, PF >= `1.03`, max DD <= `8000.0`.
- Test gates: trades >= `10`, PF >= `1.02`, max DD <= `5000.0`.

## Summary

- Fold rows: `240`.
- Aggregated candidates: `116`.
- Test-pass fold rows: `110`.

## Top Aggregated Candidates

| candidate | selected_folds | stable_candidate | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points | long_history_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bar_best_breakout_retest_lb10_thr0.0002_hold15_us_late | 3 | True | 1.0000 | 1.0000 | 481 | 1574.3750 | 671.0000 | 2.3463 | 1.2759 | 0.4451 | 290.1250 | 2.2749 |
| bar_best_support_reclaim_lb60_thr0.001_hold15_us_late | 3 | True | 1.0000 | 1.0000 | 386 | 782.0000 | 367.1250 | 2.1301 | 1.2802 | 0.5050 | 76.5000 | 1.4313 |
| bar_best_support_reclaim_lb60_thr0.0002_hold60_us_rth | 5 | True | 0.8000 | 0.8000 | 1447 | 8765.1250 | 3109.5000 | 2.8188 | 1.1562 | 0.5076 | -382.0000 | 9.8969 |
| bar_best_support_reclaim_lb15_thr0.001_hold30_us_late | 13 | True | 0.7692 | 0.7692 | 2292 | 9505.7500 | 2567.6250 | 3.7022 | 1.1899 | 0.5013 | -1207.5000 | 11.8041 |
| bar_best_support_reclaim_lb15_thr0.0002_hold30_us_late | 13 | True | 0.7692 | 0.7692 | 2293 | 8914.8750 | 2567.6250 | 3.4720 | 1.1797 | 0.5011 | -1207.5000 | 11.0265 |
| bar_best_support_reclaim_lb15_thr0.0005_hold30_us_late | 13 | True | 0.7692 | 0.7692 | 2293 | 8914.8750 | 2567.6250 | 3.4720 | 1.1797 | 0.5011 | -1207.5000 | 11.0265 |
| bar_best_support_reclaim_lb60_thr0.0005_hold60_us_rth | 4 | True | 0.7500 | 0.7500 | 1143 | 2672.3750 | 3109.5000 | 0.8594 | 1.0773 | 0.4979 | -382.0000 | 2.9307 |
| bar_best_support_reclaim_lb60_thr0.0002_hold15_us_late | 4 | True | 0.7500 | 0.7500 | 517 | 726.6250 | 474.0000 | 1.5330 | 1.1994 | 0.5052 | -54.2500 | 1.1849 |
| bar_best_support_reclaim_lb60_thr0.0005_hold15_us_late | 4 | True | 0.7500 | 0.7500 | 517 | 726.6250 | 474.0000 | 1.5330 | 1.1994 | 0.5052 | -54.2500 | 1.1849 |
| bar_best_support_reclaim_lb30_thr0.001_hold30_us_late | 7 | True | 0.7143 | 0.7143 | 972 | 3268.2500 | 2077.1250 | 1.5734 | 1.1802 | 0.5261 | -354.7500 | 4.0455 |
| bar_best_support_reclaim_lb30_thr0.0002_hold30_us_late | 7 | True | 0.7143 | 0.7143 | 973 | 3234.3750 | 2074.1250 | 1.5594 | 1.1779 | 0.5255 | -354.7500 | 4.0047 |
| bar_best_support_reclaim_lb30_thr0.0005_hold30_us_late | 7 | True | 0.7143 | 0.7143 | 973 | 3234.3750 | 2074.1250 | 1.5594 | 1.1779 | 0.5255 | -354.7500 | 4.0047 |
| bar_best_breakout_retest_lb60_thr0.0002_hold15_us_late | 3 | True | 0.6667 | 0.6667 | 199 | -423.8750 | 1376.8750 | -0.3079 | 1.4374 | 0.5019 | -1177.7500 | 0.0000 |
| bar_best_breakout_retest_lb60_thr0.0005_hold15_us_late | 3 | True | 0.6667 | 0.6667 | 199 | -423.8750 | 1376.8750 | -0.3079 | 1.4374 | 0.5019 | -1177.7500 | 0.0000 |
| bar_best_breakout_retest_lb60_thr0.001_hold15_us_late | 3 | True | 0.6667 | 0.6667 | 199 | -429.3750 | 1376.8750 | -0.3118 | 1.4325 | 0.5019 | -1177.7500 | 0.0000 |
| bar_best_support_reclaim_lb10_thr0.0002_hold15_asia | 3 | True | 0.6667 | 0.3333 | 3769 | 1571.6250 | 1037.7500 | 1.5145 | 1.0837 | 0.4680 | -298.7500 | 1.8646 |
| bar_best_support_reclaim_lb10_thr0.0005_hold15_asia | 3 | True | 0.6667 | 0.3333 | 3769 | 1571.6250 | 1037.7500 | 1.5145 | 1.0837 | 0.4680 | -298.7500 | 1.8646 |
| bar_best_support_reclaim_lb60_thr0.001_hold60_us_rth | 5 | True | 0.6000 | 0.6000 | 1424 | 2519.7500 | 3109.5000 | 0.8103 | 1.0587 | 0.4958 | -382.0000 | 2.7602 |
| bar_best_support_reclaim_lb60_thr0.0002_hold30_us_late | 5 | True | 0.4000 | 0.4000 | 500 | 485.7500 | 1614.3750 | 0.3009 | 1.1162 | 0.5149 | -325.3750 | 0.5464 |
| bar_best_support_reclaim_lb60_thr0.0005_hold30_us_late | 5 | True | 0.4000 | 0.4000 | 500 | 485.7500 | 1614.3750 | 0.3009 | 1.1162 | 0.5149 | -325.3750 | 0.5464 |
| bar_best_support_reclaim_lb60_thr0.001_hold30_us_late | 5 | True | 0.4000 | 0.4000 | 499 | 467.1250 | 1614.3750 | 0.2894 | 1.1147 | 0.5140 | -325.3750 | 0.5255 |
| bar_best_breakout_retest_lb30_thr0.0002_hold60_asia | 3 | True | 0.3333 | 0.3333 | 764 | -302.2500 | 1421.5000 | -0.2126 | 0.9835 | 0.4754 | -258.3750 | 0.0000 |
| bar_best_breakout_retest_lb10_thr0.0002_hold30_us_late | 2 | False | 1.0000 | 1.0000 | 234 | 2023.2500 | 1735.8750 | 1.1656 | 1.5544 | 0.5085 | 480.7500 | 2.2707 |
| bar_best_breakout_retest_lb10_thr0.0005_hold30_us_late | 2 | False | 1.0000 | 1.0000 | 234 | 2023.2500 | 1735.8750 | 1.1656 | 1.5544 | 0.5085 | 480.7500 | 2.2707 |
| bar_best_breakout_retest_lb10_thr0.001_hold30_us_late | 2 | False | 1.0000 | 1.0000 | 234 | 2023.2500 | 1735.8750 | 1.1656 | 1.5544 | 0.5085 | 480.7500 | 2.2707 |

## Top Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate | test_max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | bar_best_support_reclaim_lb60_thr0.0002_hold60_us_rth | 11 | 15 | 1177 | 3569.6250 | 1.1099 | 304 | 6092.7500 | 1.4719 | 0.5461 | 1212.3750 |
| True | bar_best_support_reclaim_lb10_thr0.0002_hold60_europe | 14 | 14 | 1500 | 5726.0000 | 1.1502 | 356 | 2980.2500 | 1.3148 | 0.5169 | 1023.2500 |
| True | bar_best_support_reclaim_lb10_thr0.0005_hold60_europe | 14 | 15 | 1500 | 5726.0000 | 1.1502 | 356 | 2980.2500 | 1.3148 | 0.5169 | 1023.2500 |
| True | bar_best_support_reclaim_lb15_thr0.0002_hold30_us_late | 3 | 7 | 714 | 3580.5000 | 1.1696 | 181 | 2754.1250 | 2.0673 | 0.5525 | 503.8750 |
| True | bar_best_support_reclaim_lb15_thr0.0005_hold30_us_late | 3 | 8 | 714 | 3580.5000 | 1.1696 | 181 | 2754.1250 | 2.0673 | 0.5525 | 503.8750 |
| True | bar_best_support_reclaim_lb15_thr0.001_hold30_us_late | 3 | 9 | 714 | 3580.5000 | 1.1696 | 181 | 2754.1250 | 2.0673 | 0.5525 | 503.8750 |
| True | bar_best_support_reclaim_lb15_thr0.001_hold30_us_late | 7 | 13 | 710 | 3549.5000 | 1.2963 | 177 | 2604.3750 | 1.8068 | 0.5763 | 624.8750 |
| True | bar_best_support_reclaim_lb15_thr0.0002_hold30_us_late | 7 | 14 | 711 | 3549.6250 | 1.2962 | 177 | 2568.3750 | 1.7971 | 0.5706 | 660.8750 |
| True | bar_best_support_reclaim_lb15_thr0.0005_hold30_us_late | 7 | 15 | 711 | 3549.6250 | 1.2962 | 177 | 2568.3750 | 1.7971 | 0.5706 | 660.8750 |
| True | bar_best_support_reclaim_lb15_thr0.001_hold30_us_late | 11 | 4 | 711 | 5294.6250 | 1.3187 | 188 | 2247.5000 | 1.2727 | 0.4947 | 2567.6250 |
| True | bar_best_support_reclaim_lb15_thr0.0002_hold30_us_late | 11 | 5 | 711 | 4703.6250 | 1.2740 | 188 | 2247.5000 | 1.2727 | 0.4947 | 2567.6250 |
| True | bar_best_support_reclaim_lb15_thr0.0005_hold30_us_late | 11 | 6 | 711 | 4703.6250 | 1.2740 | 188 | 2247.5000 | 1.2727 | 0.4947 | 2567.6250 |
| True | bar_best_support_reclaim_lb60_thr0.0002_hold60_us_rth | 12 | 4 | 1186 | 5092.7500 | 1.1378 | 285 | 1968.3750 | 1.2208 | 0.5474 | 1225.2500 |
| True | bar_best_support_reclaim_lb60_thr0.0005_hold60_us_rth | 12 | 5 | 1186 | 5092.7500 | 1.1378 | 285 | 1968.3750 | 1.2208 | 0.5474 | 1225.2500 |
| True | bar_best_support_reclaim_lb60_thr0.001_hold60_us_rth | 12 | 9 | 1186 | 4557.0000 | 1.1224 | 285 | 1968.3750 | 1.2208 | 0.5474 | 1225.2500 |
| True | bar_best_support_reclaim_lb10_thr0.0002_hold15_asia | 8 | 8 | 5075 | 2125.1250 | 1.0928 | 1238 | 1773.0000 | 1.2743 | 0.4548 | 713.0000 |
| True | bar_best_support_reclaim_lb10_thr0.0005_hold15_asia | 8 | 9 | 5075 | 2125.1250 | 1.0928 | 1238 | 1773.0000 | 1.2743 | 0.4548 | 713.0000 |
| True | bar_best_support_reclaim_lb15_thr0.001_hold60_us_rth | 15 | 6 | 1449 | 7730.6250 | 1.1547 | 356 | 1670.0000 | 1.1123 | 0.5281 | 2087.2500 |
| True | bar_best_support_reclaim_lb15_thr0.0002_hold60_us_rth | 15 | 7 | 1449 | 7729.3750 | 1.1546 | 356 | 1670.0000 | 1.1123 | 0.5281 | 2087.2500 |
| True | bar_best_support_reclaim_lb15_thr0.0005_hold60_us_rth | 15 | 8 | 1449 | 7729.3750 | 1.1546 | 356 | 1670.0000 | 1.1123 | 0.5281 | 2087.2500 |
| True | bar_best_breakout_retest_lb10_thr0.0002_hold30_us_late | 8 | 1 | 479 | 3497.6250 | 1.4361 | 118 | 1542.5000 | 1.9707 | 0.5169 | 540.1250 |
| True | bar_best_breakout_retest_lb10_thr0.0005_hold30_us_late | 8 | 2 | 479 | 3497.6250 | 1.4361 | 118 | 1542.5000 | 1.9707 | 0.5169 | 540.1250 |
| True | bar_best_breakout_retest_lb10_thr0.001_hold30_us_late | 8 | 3 | 478 | 3110.2500 | 1.3787 | 118 | 1542.5000 | 1.9707 | 0.5169 | 540.1250 |
| True | bar_best_breakout_retest_lb15_thr0.0002_hold60_us_late | 10 | 13 | 290 | 2802.2500 | 1.2777 | 72 | 1300.2500 | 1.4183 | 0.4722 | 1261.1250 |
| True | bar_best_breakout_retest_lb15_thr0.0005_hold60_us_late | 10 | 14 | 290 | 2802.2500 | 1.2777 | 72 | 1300.2500 | 1.4183 | 0.4722 | 1261.1250 |
