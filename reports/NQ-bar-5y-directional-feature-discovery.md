# NQ Bar-Only Best Strategy Walk-Forward Search

## Verdict

Best long-history bar-only candidate: `bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late` with `6205.2500` future test net points, `80.00%` positive selected folds, `1.7309` average test PF, and `2.2935` net/DD.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Continuous construction: one NQ futures row per minute, selected by highest reported volume.
- Feature span: `2021-04-28 00:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Feature rows: `1,769,740`.
- Distinct symbols selected: `21`.

## Walk-Forward Design

- Train days: `365`; purge days: `10`; test days: `90`; step days: `90`.
- Candidate families: `support_reclaim, breakout_retest, vwap_reclaim, momentum, mean_reversion`.
- Sessions: `us_late, us_rth`.
- Max fold candidates: `20`.
- Train gates: trades >= `60`, PF >= `1.03`, max DD <= `8000.0`.
- Test gates: trades >= `8`, PF >= `1.02`, max DD <= `5000.0`.

## Summary

- Fold rows: `320`.
- Aggregated candidates: `181`.
- Test-pass fold rows: `141`.

## Top Aggregated Candidates

| candidate | selected_folds | stable_candidate | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points | long_history_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late | 5 | True | 0.8000 | 0.8000 | 398 | 6205.2500 | 2705.6250 | 2.2935 | 1.7309 | 0.5591 | -1128.3750 | 7.1634 |
| bar_best_momentum_lb60_thr0.0006_hold30_long_us_late | 5 | True | 0.8000 | 0.8000 | 372 | 4563.7500 | 891.2500 | 5.1206 | 1.7967 | 0.5370 | -8.8750 | 6.7256 |
| bar_best_momentum_lb60_thr0.001_hold15_long_us_late | 5 | True | 0.8000 | 0.8000 | 426 | 1989.7500 | 1750.7500 | 1.1365 | 1.6405 | 0.5322 | -1429.2500 | 2.4617 |
| bar_best_mean_reversion_lb30_thr1_hold30_long_us_late | 4 | True | 0.7500 | 0.7500 | 500 | 4569.2500 | 3072.6250 | 1.4871 | 1.6273 | 0.5180 | -512.8750 | 5.0446 |
| bar_best_support_reclaim_lb15_thr0.0002_hold30_long_us_late | 4 | True | 0.7500 | 0.7500 | 496 | 3576.7500 | 1176.0000 | 3.0415 | 1.3423 | 0.5507 | -67.3750 | 4.6044 |
| bar_best_support_reclaim_lb15_thr0.0005_hold30_long_us_late | 4 | True | 0.7500 | 0.7500 | 496 | 3576.7500 | 1176.0000 | 3.0415 | 1.3423 | 0.5507 | -67.3750 | 4.6044 |
| bar_best_support_reclaim_lb15_thr0.001_hold30_long_us_late | 4 | True | 0.7500 | 0.7500 | 496 | 3576.7500 | 1176.0000 | 3.0415 | 1.3423 | 0.5507 | -67.3750 | 4.6044 |
| bar_best_support_reclaim_lb60_thr0.0005_hold30_long_us_late | 4 | True | 0.7500 | 0.7500 | 215 | 675.6250 | 1457.7500 | 0.4635 | 1.2326 | 0.5592 | -239.7500 | 0.8155 |
| bar_best_support_reclaim_lb60_thr0.001_hold30_long_us_late | 4 | True | 0.7500 | 0.7500 | 215 | 675.6250 | 1457.7500 | 0.4635 | 1.2326 | 0.5592 | -239.7500 | 0.8155 |
| bar_best_support_reclaim_lb60_thr0.0002_hold30_long_us_late | 4 | True | 0.7500 | 0.7500 | 215 | 658.3750 | 1457.7500 | 0.4516 | 1.2305 | 0.5592 | -239.7500 | 0.7946 |
| bar_best_mean_reversion_lb30_thr1_hold60_short_us_late | 4 | True | 0.7500 | 0.7500 | 336 | -868.2500 | 2629.8750 | -0.3301 | 0.9592 | 0.4804 | -2412.2500 | 0.0000 |
| bar_best_momentum_lb60_thr0.001_hold30_long_us_late | 3 | True | 0.6667 | 0.6667 | 218 | 1718.0000 | 1423.6250 | 1.2068 | 1.7149 | 0.4944 | -379.7500 | 1.9627 |
| bar_best_mean_reversion_lb30_thr1.4_hold30_long_us_late | 3 | True | 0.6667 | 0.6667 | 341 | 1797.3750 | 2898.2500 | 0.6202 | 1.2423 | 0.5198 | -15.5000 | 1.9310 |
| bar_best_momentum_lb15_thr0.001_hold15_short_us_late | 3 | True | 0.6667 | 0.6667 | 416 | 725.2500 | 881.6250 | 0.8226 | 1.2284 | 0.4583 | -408.1250 | 0.8909 |
| bar_best_momentum_lb30_thr0.0003_hold60_long_us_rth | 3 | True | 0.6667 | 0.3333 | 844 | 1066.5000 | 2392.5000 | 0.4458 | 1.0818 | 0.5367 | -816.0000 | 1.1604 |
| bar_best_breakout_retest_lb15_thr0.0002_hold30_long_us_late | 3 | True | 0.6667 | 0.3333 | 196 | -2996.2500 | 3842.2500 | -0.7798 | 1.0068 | 0.4910 | -3662.3750 | 0.0000 |
| bar_best_breakout_retest_lb15_thr0.0005_hold30_long_us_late | 3 | True | 0.6667 | 0.3333 | 196 | -2996.2500 | 3842.2500 | -0.7798 | 1.0068 | 0.4910 | -3662.3750 | 0.0000 |
| bar_best_momentum_lb60_thr0.0006_hold15_long_us_late | 5 | True | 0.6000 | 0.6000 | 444 | 2939.5000 | 1528.7500 | 1.9228 | 1.6399 | 0.5357 | -974.1250 | 3.5231 |
| bar_best_support_reclaim_lb30_thr0.0002_hold30_long_us_late | 5 | True | 0.6000 | 0.6000 | 427 | 1666.3750 | 1696.7500 | 0.9821 | 1.3077 | 0.5271 | -22.8750 | 1.9614 |
| bar_best_support_reclaim_lb30_thr0.0005_hold30_long_us_late | 5 | True | 0.6000 | 0.6000 | 427 | 1666.3750 | 1696.7500 | 0.9821 | 1.3077 | 0.5271 | -22.8750 | 1.9614 |
| bar_best_support_reclaim_lb30_thr0.001_hold30_long_us_late | 5 | True | 0.6000 | 0.6000 | 427 | 1626.6250 | 1736.5000 | 0.9367 | 1.3052 | 0.5248 | -60.2500 | 1.9080 |
| bar_best_mean_reversion_lb60_thr1.4_hold60_long_us_rth | 4 | True | 0.5000 | 0.5000 | 829 | 2322.3750 | 2352.3750 | 0.9872 | 1.1347 | 0.5421 | -1255.8750 | 2.5166 |
| bar_best_momentum_lb10_thr0.001_hold30_short_us_late | 4 | True | 0.5000 | 0.5000 | 380 | -66.2500 | 902.2500 | -0.0734 | 0.9960 | 0.4496 | -940.7500 | 0.0000 |
| bar_best_breakout_retest_lb60_thr0.0002_hold15_long_us_late | 4 | True | 0.5000 | 0.5000 | 131 | -162.3750 | 1195.2500 | -0.1359 | 3.7062 | 0.5188 | -1001.3750 | 0.0000 |
| bar_best_momentum_lb30_thr0.0003_hold15_short_us_late | 4 | True | 0.5000 | 0.5000 | 645 | -783.1250 | 2498.2500 | -0.3135 | 0.9787 | 0.4502 | -2174.2500 | 0.0000 |

## Top Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate | test_max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | bar_best_mean_reversion_lb10_thr1_hold30_long_us_late | 12 | 7 | 732 | 4681.0000 | 1.2351 | 184 | 3326.2500 | 1.7180 | 0.5326 | 1011.1250 |
| True | bar_best_mean_reversion_lb60_thr1.4_hold60_long_us_rth | 12 | 20 | 877 | 3411.6250 | 1.1202 | 202 | 2617.0000 | 1.4526 | 0.5644 | 1066.3750 |
| True | bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late | 6 | 4 | 311 | 4273.1250 | 1.4323 | 73 | 2300.6250 | 2.9286 | 0.5753 | 472.5000 |
| True | bar_best_mean_reversion_lb10_thr1_hold15_long_us_late | 12 | 15 | 1165 | 2825.1250 | 1.1502 | 290 | 2272.7500 | 1.5490 | 0.4655 | 830.8750 |
| True | bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late | 7 | 8 | 313 | 4388.8750 | 1.4900 | 80 | 2159.0000 | 1.8278 | 0.5125 | 421.5000 |
| True | bar_best_mean_reversion_lb30_thr0.6_hold15_long_us_late | 8 | 20 | 760 | 4677.5000 | 1.6186 | 173 | 2148.3750 | 2.1980 | 0.5260 | 426.0000 |
| True | bar_best_momentum_lb60_thr0.0006_hold60_long_us_late | 12 | 9 | 223 | 4086.1250 | 1.3212 | 52 | 2101.5000 | 1.8735 | 0.5577 | 587.7500 |
| True | bar_best_momentum_lb30_thr0.0006_hold60_long_us_rth | 12 | 16 | 1097 | 3467.3750 | 1.1032 | 274 | 1985.0000 | 1.2343 | 0.5474 | 1610.3750 |
| True | bar_best_support_reclaim_lb10_thr0.0002_hold30_long_us_late | 6 | 9 | 572 | 4498.2500 | 1.4531 | 143 | 1922.6250 | 1.7228 | 0.5664 | 578.5000 |
| True | bar_best_support_reclaim_lb10_thr0.0005_hold30_long_us_late | 6 | 10 | 572 | 4498.2500 | 1.4531 | 143 | 1922.6250 | 1.7228 | 0.5664 | 578.5000 |
| True | bar_best_support_reclaim_lb10_thr0.001_hold30_long_us_late | 6 | 11 | 572 | 4498.2500 | 1.4531 | 143 | 1922.6250 | 1.7228 | 0.5664 | 578.5000 |
| True | bar_best_mean_reversion_lb30_thr1_hold30_long_us_late | 6 | 2 | 519 | 5108.6250 | 1.5198 | 119 | 1831.6250 | 2.1572 | 0.5630 | 692.5000 |
| True | bar_best_momentum_lb30_thr0.0003_hold60_long_us_rth | 13 | 1 | 1125 | 5348.8750 | 1.1381 | 285 | 1813.1250 | 1.3061 | 0.5684 | 985.8750 |
| True | bar_best_momentum_lb30_thr0.0003_hold30_long_us_rth | 13 | 13 | 1696 | 3935.2500 | 1.0991 | 434 | 1790.5000 | 1.2848 | 0.5323 | 808.8750 |
| True | bar_best_momentum_lb60_thr0.0006_hold15_long_us_late | 9 | 3 | 360 | 3548.0000 | 2.0123 | 102 | 1780.5000 | 2.1046 | 0.5392 | 640.2500 |
| True | bar_best_mean_reversion_lb15_thr1.4_hold30_long_us_late | 6 | 12 | 601 | 3840.1250 | 1.3475 | 146 | 1780.0000 | 1.8997 | 0.5548 | 765.3750 |
| True | bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late | 8 | 12 | 319 | 5446.6250 | 1.5917 | 75 | 1714.1250 | 1.8559 | 0.6133 | 496.8750 |
| True | bar_best_mean_reversion_lb30_thr1_hold30_long_us_late | 8 | 13 | 528 | 5494.2500 | 1.5478 | 114 | 1668.7500 | 1.9285 | 0.5263 | 395.8750 |
| True | bar_best_support_reclaim_lb15_thr0.0002_hold60_short_us_late | 0 | 18 | 319 | 2486.6250 | 1.2187 | 89 | 1650.1250 | 1.3640 | 0.5393 | 1484.5000 |
| True | bar_best_support_reclaim_lb15_thr0.0005_hold60_short_us_late | 0 | 19 | 319 | 2486.6250 | 1.2187 | 89 | 1650.1250 | 1.3640 | 0.5393 | 1484.5000 |
| True | bar_best_support_reclaim_lb15_thr0.001_hold60_short_us_late | 0 | 20 | 319 | 2486.6250 | 1.2187 | 89 | 1650.1250 | 1.3640 | 0.5393 | 1484.5000 |
| True | bar_best_support_reclaim_lb15_thr0.0002_hold30_long_us_late | 9 | 16 | 483 | 5597.1250 | 1.6599 | 125 | 1639.1250 | 1.4939 | 0.5520 | 923.3750 |
| True | bar_best_support_reclaim_lb15_thr0.0005_hold30_long_us_late | 9 | 17 | 483 | 5597.1250 | 1.6599 | 125 | 1639.1250 | 1.4939 | 0.5520 | 923.3750 |
| True | bar_best_support_reclaim_lb15_thr0.001_hold30_long_us_late | 9 | 18 | 483 | 5597.1250 | 1.6599 | 125 | 1639.1250 | 1.4939 | 0.5520 | 923.3750 |
| True | bar_best_breakout_retest_lb60_thr0.0002_hold60_long_us_rth | 12 | 17 | 462 | 1937.0000 | 1.1672 | 123 | 1597.6250 | 1.5168 | 0.5122 | 610.7500 |
