# NQM6 Best Strategy Ranking

## Verdict

Best balanced candidate: `adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3`.

- Selection prioritizes high net points and 3x-cost net points, but requires controlled drawdown, PF, fold/window consistency, positive worst rolling window, and stability.
- This is a research/backtest ranking, not permission to trade live without paper validation and order-routing checks.

## Best Candidate Metrics

| selection_tier | candidate_universe | name | full_trades | full_net_points | full_max_drawdown_points | net_to_drawdown | full_profit_factor | full_win_rate | full_stability | positive_fold_rate | positive_window_rate | min_window_net_points | stress_net_points | best_strategy_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| balanced_best | walkforward_neighbors | adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3 | 942 | 3318.0000 | 190.8750 | 17.3831 | 1.6891 | 0.5488 | 0.8476 | 1.0000 | 1.0000 | 28.3750 | 2376.0000 | 7965.7789 |

## Top Balanced Candidates

| selection_tier | candidate_universe | name | full_trades | full_net_points | full_max_drawdown_points | net_to_drawdown | full_profit_factor | full_win_rate | full_stability | positive_fold_rate | positive_window_rate | min_window_net_points | stress_net_points | best_strategy_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| balanced_best | walkforward_neighbors | adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3 | 942 | 3318.0000 | 190.8750 | 17.3831 | 1.6891 | 0.5488 | 0.8476 | 1.0000 | 1.0000 | 28.3750 | 2376.0000 | 7965.7789 |
| balanced_best | walkforward_neighbors | adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.25 | 943 | 3203.3750 | 190.8750 | 16.7826 | 1.6504 | 0.5483 | 0.8842 | 1.0000 | 1.0000 | 28.3750 | 2260.3750 | 7763.7752 |
| balanced_best | selected_stability | adv_stable_refined_defensive_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_not_low_imb0.3 | 544 | 2276.7500 | 128.0000 | 17.7871 | 1.8446 | 0.5515 | 0.7860 | 1.0000 | 1.0000 | 128.6250 | 1732.7500 | 7754.6886 |
| balanced_best | walkforward_neighbors | adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_not_low_imb0.3 | 544 | 2276.7500 | 128.0000 | 17.7871 | 1.8446 | 0.5515 | 0.7860 | 1.0000 | 1.0000 | 128.6250 | 1732.7500 | 7754.6886 |
| balanced_best | walkforward_neighbors | adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_not_low_imb0.25 | 544 | 2276.7500 | 128.0000 | 17.7871 | 1.8446 | 0.5515 | 0.7860 | 1.0000 | 1.0000 | 128.6250 | 1732.7500 | 7754.6886 |
| balanced_best | adaptive_portfolio | adaptive_defensive_mr_trendstable_mr_meanstable_mr_fallbackdefensive_mr_us0_eu1_gap1_cap0 | 1088 | 4324.5000 | 347.2500 | 12.4536 | 1.6593 | 0.5460 | 0.7243 | 0.8333 | 1.0000 | 268.6250 | 3236.5000 | 7176.1862 |
| balanced_best | adaptive_portfolio | adaptive_defensive_mr_trendstable_mr_meanstable_mr_fallbackdefensive_mr_us0_eu1_gap1_cap24 | 751 | 3173.3750 | 259.1250 | 12.2465 | 1.7578 | 0.5606 | 0.9930 | 0.8333 | 1.0000 | 278.6250 | 2422.3750 | 6931.7443 |
| balanced_best | adaptive_portfolio | adaptive_defensive_mr_trendstable_mr_meanstable_mr_fallbackdefensive_mr_us0_eu1_gap3_cap0 | 959 | 3164.3750 | 291.5000 | 10.8555 | 1.5394 | 0.5360 | 0.7201 | 0.8333 | 1.0000 | 294.1250 | 2205.3750 | 6137.3213 |
| balanced_best | selected_stability | adv_stable_refined_defensive_mean_reversion_lb5_thr0.8_min1_max6_reverse_europe_not_low_imb0.3 | 560 | 2435.0000 | 224.1250 | 10.8645 | 1.8273 | 0.5625 | 0.7613 | 1.0000 | 1.0000 | 68.7500 | 1875.0000 | 6092.0957 |
| balanced_best | adaptive_portfolio | adaptive_stable_mr_trendtrend_vwap_meanstable_mr_fallbackdefensive_mr_us1_eu1_gap3_cap0 | 980 | 3271.0000 | 316.2500 | 10.3431 | 1.4778 | 0.5388 | 0.7284 | 0.8333 | 1.0000 | 304.3750 | 2291.0000 | 6055.3950 |
| balanced_best | selected_stability | adv_stable_refined_defensive_mean_reversion_lb7_thr0.65_min1_max6_reverse_europe_all_imb0.3 | 1014 | 2859.2500 | 298.7500 | 9.5707 | 1.5069 | 0.5454 | 0.8523 | 1.0000 | 1.0000 | 87.2500 | 1845.2500 | 5715.7607 |
| balanced_best | selected_stability | adv_stable_refined_defensive_mean_reversion_lb6_thr0.75_min1_max6_reverse_europe_not_low_imb0.3 | 559 | 2070.3750 | 205.6250 | 10.0687 | 1.7033 | 0.5438 | 0.8076 | 1.0000 | 1.0000 | 179.2500 | 1511.3750 | 5708.5924 |
| balanced_best | adaptive_portfolio | adaptive_defensive_mr_trendtrend_vwap_meanstable_mr_fallbackdefensive_mr_us1_eu1_gap1_cap24 | 752 | 2852.7500 | 349.8750 | 8.1536 | 1.6026 | 0.5519 | 0.9002 | 0.8333 | 1.0000 | 131.1250 | 2100.7500 | 5533.0404 |
| balanced_best | adaptive_portfolio | adaptive_defensive_mr_trendtrend_vwap_meanstable_mr_fallbackstable_mr_us1_eu1_gap1_cap24 | 752 | 2852.7500 | 349.8750 | 8.1536 | 1.6026 | 0.5519 | 0.9002 | 0.8333 | 1.0000 | 131.1250 | 2100.7500 | 5533.0404 |
| balanced_best | adaptive_portfolio | adaptive_defensive_mr_trendtrend_vwap_meandefensive_mr_fallbackstable_mr_us1_eu1_gap1_cap24 | 752 | 2852.7500 | 349.8750 | 8.1536 | 1.6026 | 0.5519 | 0.9002 | 0.8333 | 1.0000 | 131.1250 | 2100.7500 | 5533.0404 |
| balanced_best | selected_stability | adv_stable_refined_defensive_mean_reversion_lb7_thr0.7_min1_max6_reverse_europe_not_low_imb0.3 | 567 | 2018.8750 | 215.3750 | 9.3738 | 1.6441 | 0.5362 | 0.8772 | 1.0000 | 1.0000 | 44.5000 | 1451.8750 | 5495.8213 |
| balanced_best | selected_stability | adv_stable_refined_defensive_mean_reversion_lb7_thr0.7_min1_max6_reverse_europe_not_low_imb0.25 | 567 | 2018.8750 | 215.3750 | 9.3738 | 1.6441 | 0.5362 | 0.8772 | 1.0000 | 1.0000 | 44.5000 | 1451.8750 | 5495.8213 |
| balanced_best | adaptive_portfolio | adaptive_stable_mr_trendtrend_vwap_meanstable_mr_fallbackdefensive_mr_us1_eu1_gap1_cap24 | 752 | 2836.7500 | 347.1250 | 8.1721 | 1.6079 | 0.5519 | 0.7611 | 0.8333 | 1.0000 | 124.5000 | 2084.7500 | 5402.8061 |
| balanced_best | walkforward_neighbors | adv_wf_best_mean_reversion_lb6_thr0.8_min1_max5_reverse_europe_not_low_imb0.3 | 569 | 1799.3750 | 180.8750 | 9.9482 | 1.5845 | 0.5308 | 0.7098 | 1.0000 | 1.0000 | 10.7500 | 1230.3750 | 5305.3460 |
| balanced_best | walkforward_neighbors | adv_wf_best_mean_reversion_lb6_thr0.8_min1_max5_reverse_europe_not_low_imb0.25 | 569 | 1799.3750 | 180.8750 | 9.9482 | 1.5845 | 0.5308 | 0.7098 | 1.0000 | 1.0000 | 10.7500 | 1230.3750 | 5305.3460 |

## Highest Net Alternatives

| selection_tier | candidate_universe | name | full_trades | full_net_points | full_max_drawdown_points | net_to_drawdown | full_profit_factor | full_win_rate | full_stability | positive_fold_rate | positive_window_rate | min_window_net_points | stress_net_points | best_strategy_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| research_only | live_ready_top10 | adv_local_mean_reversion_lb3_thr0.6_min1_max5_reverse_all_high_imb0.2 | 1460 | 4737.2500 | 321.0000 | 14.7578 | 1.4857 | 0.5479 | 0.5572 | 1.0000 | 0.8889 | -207.8750 | 3277.2500 | 7400.5112 |
| research_only | robust_top10 | adv_local_mean_reversion_lb3_thr0.6_min1_max5_reverse_all_high_imb0.2 | 1460 | 4737.2500 | 321.0000 | 14.7578 | 1.4857 | 0.5479 | 0.5572 | 1.0000 | nan | nan | 3277.2500 | 6720.4897 |
| risk_controlled | adaptive_portfolio | adaptive_defensive_mr_trendtrend_vwap_meanstable_mr_fallbackdefensive_mr_us1_eu1_gap1_cap0 | 1107 | 4586.6250 | 349.8750 | 13.1093 | 1.5984 | 0.5501 | 0.6212 | 0.8333 | 1.0000 | 268.2500 | 3479.6250 | 7368.3477 |
| risk_controlled | adaptive_portfolio | adaptive_defensive_mr_trendtrend_vwap_meanstable_mr_fallbackstable_mr_us1_eu1_gap1_cap0 | 1107 | 4586.6250 | 349.8750 | 13.1093 | 1.5984 | 0.5501 | 0.6212 | 0.8333 | 1.0000 | 268.2500 | 3479.6250 | 7368.3477 |
| risk_controlled | adaptive_portfolio | adaptive_defensive_mr_trendtrend_vwap_meandefensive_mr_fallbackstable_mr_us1_eu1_gap1_cap0 | 1107 | 4586.6250 | 349.8750 | 13.1093 | 1.5984 | 0.5501 | 0.6212 | 0.8333 | 1.0000 | 268.2500 | 3479.6250 | 7368.3477 |
| risk_controlled | adaptive_portfolio | adaptive_stable_mr_trendtrend_vwap_meanstable_mr_fallbackdefensive_mr_us1_eu1_gap1_cap0 | 1107 | 4548.8750 | 347.1250 | 13.1044 | 1.5980 | 0.5492 | 0.6742 | 0.8333 | 1.0000 | 290.2500 | 3441.8750 | 7400.5593 |
| balanced_best | adaptive_portfolio | adaptive_defensive_mr_trendstable_mr_meanstable_mr_fallbackdefensive_mr_us0_eu1_gap1_cap0 | 1088 | 4324.5000 | 347.2500 | 12.4536 | 1.6593 | 0.5460 | 0.7243 | 0.8333 | 1.0000 | 268.6250 | 3236.5000 | 7176.1862 |
| research_only | live_ready_top10 | adv_mean_reversion_lb3_thr0.6_min1_max10_reverse_all_all_imb0.35 | 1660 | 3805.7500 | 993.3750 | 3.8311 | 1.2763 | 0.5355 | 0.2500 | 0.5000 | 0.3333 | -909.6250 | 2145.7500 | 3000.0818 |
| research_only | robust_top10 | adv_mean_reversion_lb3_thr0.6_min1_max10_reverse_all_all_imb0.35 | 1660 | 3805.7500 | 993.3750 | 3.8311 | 1.2763 | 0.5355 | 0.2500 | 0.5000 | nan | nan | 2145.7500 | 2783.4152 |
| research_only | live_ready_top10 | momentum_lb10_thr0.0006_hold3_imb0.35 | 1150 | 3527.5000 | 729.1250 | 4.8380 | 1.4648 | 0.5209 | 0.5625 | 1.0000 | 0.6667 | -631.2500 | 2377.5000 | 4126.3978 |
| research_only | robust_top10 | momentum_lb10_thr0.0006_hold3_imb0.35 | 1150 | 3527.5000 | 729.1250 | 4.8380 | 1.4648 | 0.5209 | 0.5625 | 1.0000 | nan | nan | 2377.5000 | 3693.0645 |
| research_only | live_ready_top10 | momentum_lb10_thr0.0003_hold3_imb0.35 | 1710 | 3420.0000 | 693.2500 | 4.9333 | 1.3206 | 0.5088 | 0.9833 | 0.6667 | 0.5556 | -781.3750 | 1710.0000 | 3989.2645 |

## Selection Criteria

- Minimum 200 trades.
- PF >= 1.45.
- Positive fold rate >= 80%.
- Positive 10-day rolling window rate >= 88%.
- Worst 10-day rolling window net >= 0.
- 3x-cost/stress net > 0.
- Stability >= 0.70 for the top balanced tier.
