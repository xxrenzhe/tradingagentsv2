# NQM6 MBP Live-Ready Top10 Strategy Candidates

Feature rows: 60,503
Date range: 2026-03-02 23:59:00+00:00 to 2026-05-01 21:00:00+00:00
Window days: 10
Window step days: 5
Live-ready requires: 3x-cost net > 0, positive fold rate >= 80%, rolling positive window rate >= 70%, at least 5 trades in every rolling window, >= 200 full trades, and PF >= 1.25.

| name | source | family | full_trades | full_net_points | full_profit_factor | positive_fold_rate | positive_window_rate | min_window_net_points | worst_cost_net_points | live_ready | local_positive_rate | local_median_robust_score | local_rank_score | live_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adv_local_mean_reversion_lb5_thr0.6_min1_max5_reverse_vwap_europe_not_low_imb0.35 | advanced | mean_reversion | 271 | 1232.3750 | 1.9791 | 1.0000 | 1.0000 | 4.5000 | 961.3750 | True | 1.0000 | 2.8757 | 2.8757 | 2.3261 |
| adv_momentum_lb10_thr0.0006_min1_max10_reverse_vwap_all_high_imb0.35 | advanced | momentum | 471 | 2039.1250 | 1.5451 | 0.8333 | 0.8889 | -401.7500 | 1568.1250 | True | 1.0000 | 2.1594 | 2.1594 | 1.5309 |
| adv_vwap_reclaim_lb10_thr0.0002_min1_max10_time_us_rth_all_imb0.35 | advanced | vwap_reclaim | 445 | 1933.3750 | 1.4210 | 1.0000 | 0.7778 | -175.2500 | 1488.3750 | True | 1.0000 | 1.4739 | 1.4739 | 1.0540 |
| adv_vwap_reclaim_lb10_thr0.0002_min1_max10_time_all_not_low_imb0.35 | advanced | vwap_reclaim | 716 | 2931.2500 | 1.4147 | 0.8333 | 0.7778 | -404.0000 | 2215.2500 | True | 1.0000 | 1.5692 | 1.4075 | 0.6050 |
| adv_vwap_reclaim_lb10_thr0.0002_min1_max10_reverse_us_rth_all_imb0.35 | advanced | vwap_reclaim | 446 | 1880.0000 | 1.4047 | 0.8333 | 0.7778 | -229.6250 | 1434.0000 | True | 1.0000 | 1.3422 | 1.3422 | 0.8283 |
| adv_vwap_reclaim_lb10_thr0.0002_min1_max10_reverse_all_not_low_imb0.35 | advanced | vwap_reclaim | 716 | 2841.7500 | 1.3986 | 0.8333 | 0.7778 | -528.6250 | 2125.7500 | True | 1.0000 | 1.3257 | 1.0594 | 0.4812 |
| adv_momentum_lb10_thr0.0003_min1_max10_reverse_vwap_all_high_imb0.35 | advanced | momentum | 609 | 1757.8750 | 1.3679 | 0.8333 | 0.7778 | -570.1250 | 1148.8750 | True | 1.0000 | 2.1594 | 0.9672 | 0.3640 |
| adv_local_mean_reversion_lb8_thr0.6_min1_max5_reverse_all_high_imb0.35 | advanced | mean_reversion | 551 | 1863.6250 | 1.4172 | 1.0000 | 0.8889 | -44.0000 | 1312.6250 | True | 1.0000 | 0.8702 | 0.8702 | 0.4040 |
| adv_mean_reversion_lb3_thr0.6_min1_max5_reverse_europe_not_low_imb0.35 | advanced | mean_reversion | 264 | 978.7500 | 1.5988 | 0.8333 | 0.7778 | -127.5000 | 714.7500 | True | 0.8333 | 0.7896 | 0.7501 | 0.9850 |
| adv_vwap_reclaim_lb10_thr0.0005_min1_max10_time_us_rth_all_imb0.35 | advanced | vwap_reclaim | 436 | 1929.7500 | 1.4257 | 1.0000 | 0.7778 | -201.8750 | 1493.7500 | True | 1.0000 | 1.4739 | 0.7252 | 0.5122 |
