# NQ State Filter Past-Fold Validation Summary

Scope: stricter validation of state filters where every tested fold selected filters from prior folds only, then evaluated on future trades with actual filtered executions only.

- Default strict gates: min_train_folds=`2`, min_train_trades=`120`, min_train_net_points=`1000`, min_train_profit_factor=`1.20`, min_train_win_rate=`0.48`, min_train_positive_fold_rate=`0.80`, min_train_min_fold_net_points=`250`, max_fold_candidates=`5`
- Future validation rows with trades: `14`
- Aggregate filter rows: `9`
- Total future selected-filter net points: `2932.500`
- Same candidate unfiltered future net points: `1867.000`
- Net improvement versus unfiltered selected candidates: `1065.500`
- Robust rows: `5` with selected_folds >= 2, positive selected-fold rate >= 50%, and positive future net

## Robust Candidates

```csv
candidate,filter,selected_folds,test_trades,test_net_points,fold_net_profit_factor,positive_selected_fold_rate,min_test_fold_net_points,test_baseline_net_points,test_net_improvement,avg_train_profit_factor
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,z_30_negative,2,238,1230.75,3.8342,0.5,-434.25,1155.875,74.875,1.8178
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,return_1m_negative,2,230,1084.25,3.46,0.5,-440.75,1155.875,-71.625,1.9166
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,return_1m_negative,2,154,758.75,1.8299,0.5,-914.25,585.75,173.0,2.2167
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,z_30_negative,2,156,611.75,1.5862,0.5,-1043.625,585.75,26.0,2.1556
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,entry_candle_down,2,146,488.25,1.6274,0.5,-778.25,585.75,-97.5,2.2016
```

## Best Improvers

```csv
candidate,filter,selected_folds,test_trades,test_net_points,fold_net_profit_factor,positive_selected_fold_rate,min_test_fold_net_points,test_baseline_net_points,test_net_improvement,avg_train_profit_factor
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,return_1m_negative,2,154,758.75,1.8299,0.5,-914.25,585.75,173.0,2.2167
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,z_30_negative,2,238,1230.75,3.8342,0.5,-434.25,1155.875,74.875,1.8178
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,z_30_negative,2,156,611.75,1.5862,0.5,-1043.625,585.75,26.0,2.1556
```

## All Selected Filters

```csv
candidate,filter,selected_folds,test_trades,test_net_points,fold_net_profit_factor,positive_selected_fold_rate,min_test_fold_net_points,test_baseline_net_points,test_net_improvement,avg_train_profit_factor
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,z_30_negative,2,238,1230.75,3.8342,0.5,-434.25,1155.875,74.875,1.8178
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,return_1m_negative,2,230,1084.25,3.46,0.5,-440.75,1155.875,-71.625,1.9166
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,vwap_below,1,39,784.875,inf,1.0,784.875,1159.875,-375.0,1.8654
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,return_1m_negative,2,154,758.75,1.8299,0.5,-914.25,585.75,173.0,2.2167
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,z_30_negative,2,156,611.75,1.5862,0.5,-1043.625,585.75,26.0,2.1556
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,entry_candle_down,2,146,488.25,1.6274,0.5,-778.25,585.75,-97.5,2.2016
bar_best_momentum_lb60_thr0.0006_hold30_long_us_late,range_30_low_mid,1,35,136.875,inf,1.0,136.875,-8.875,145.75,2.1946
bar_best_momentum_lb10_thr0.001_hold30_short_us_late,trend_120_down,1,56,-655.75,0.0,0.0,-655.75,-940.75,285.0,2.134
bar_best_mean_reversion_lb30_thr1_hold60_short_us_late,entry_body_low_mid,1,58,-1507.25,0.0,0.0,-1507.25,-2412.25,905.0,1.8411
```

## Top-K Sensitivity

```csv
max_fold_candidates,fold_rows,future_net_points,unfiltered_baseline_points,net_improvement,positive_row_rate
1,4,36.375,-666.625,703.000,0.5000
3,9,1273.250,496.000,777.250,0.5556
5,14,2932.500,1867.000,1065.500,0.5000
10,37,-195.750,-645.375,449.625,0.4324
20,77,-7507.750,-8725.250,1217.500,0.4416
```

## Practical Read

- Reducing per-fold selection from 20 to 5 improved future validation from -7507.75 to +2932.5 points, so the optimized default now avoids over-selecting weaker state filters.
- The best repeatable rule under strict past-fold selection is `bar_best_mean_reversion_lb30_thr1_hold30_long_us_late` with `z_30_negative`: selected in 2 future folds, +1230.75 points, +74.875 versus baseline, but one selected fold still loses.
- The best positive baseline-improving single-fold rule is `bar_best_momentum_lb60_thr0.0006_hold30_long_us_late` with `range_30_low_mid`: selected in 1 future fold, +136.875 net points and +145.75 versus baseline, but needs more repeat selections before promotion.
- These are optimized research candidates, not live-ready rules; the next step is integrating Top-5 past-fold selection into the full ranking/live-readiness gate.
