# NQM6 MBP Refined Mean-Reversion Search

Feature rows: 60,503
Date range: 2026-03-02 23:59:00+00:00 to 2026-05-01 21:00:00+00:00
Refined specs: 576
Quick candidates: 80
Strict live-ready candidates: 3

Strict live-ready requires positive 6/6 folds, positive 9/9 rolling 10-day windows, non-negative worst 10-day 3x-cost window, 3x-cost net > 0, >= 200 trades, and PF >= 1.25.

| name | full_trades | full_net_points | full_max_drawdown_points | full_profit_factor | positive_fold_rate | positive_window_rate | min_window_net_points | worst_cost_net_points | robust_score | live_ready_strict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adv_refined_mean_reversion_lb7_thr0.65_min1_max6_reverse_europe_not_low_imb0.3 | 582 | 1979.7500 | 215.3750 | 1.6083 | 1.0000 | 1.0000 | 55.7500 | 1397.7500 | 3.9901 | True |
| adv_refined_mean_reversion_lb5_thr0.65_min1_max6_reverse_europe_not_low_imb0.3 | 598 | 1945.0000 | 280.8750 | 1.5641 | 1.0000 | 1.0000 | 57.6250 | 1347.0000 | 2.5513 | True |
| adv_refined_mean_reversion_lb6_thr0.6_min1_max6_reverse_vwap_europe_not_low_imb0.3 | 746 | 1663.5000 | 250.0000 | 1.5562 | 1.0000 | 1.0000 | 7.0000 | 917.5000 | 2.1726 | True |
