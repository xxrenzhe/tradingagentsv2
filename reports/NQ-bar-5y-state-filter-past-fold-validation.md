# NQ State Filter Past-Fold Walk-Forward Validation

Each test fold selects candidate filters only from earlier folds, then evaluates the selected filters on the current future fold.

- Trades input: `.tmp/nq-bar-5y-directional-walkforward-trades.csv`
- Feature cache: `.tmp/nq-bar-5y-continuous-features-cache.pkl`
- Fold rows tested: `14`
- Aggregate rows: `9`
- Total selected-filter future net points: `2932.500`
- Same candidate unfiltered future net points: `1867.000`
- Future net improvement: `1065.500`
- Gates: min_train_folds=`2`, min_train_trades=`120`, min_train_net_points=`1000.0`, min_train_profit_factor=`1.2`, min_train_win_rate=`0.48`, min_train_positive_fold_rate=`0.8`, min_train_min_fold_net_points=`250.0`

## Top Future-Validated Filters

```csv
candidate,filter,filter_conditions,selected_folds,test_trades,test_net_points,fold_net_profit_factor,positive_selected_fold_rate,positive_test_fold_rate,min_test_fold_net_points,test_baseline_net_points,test_net_improvement,avg_train_score,avg_train_profit_factor
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,z_30_negative,z_30lt0.0,2,238,1230.75,3.8341968911917097,0.5,0.5,-434.25,1155.875,74.875,5539.259089384803,1.8178352234620083
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,return_1m_negative,return_1m_sideeqnegative,2,230,1084.25,3.4600113442994895,0.5,0.5,-440.75,1155.875,-71.625,5739.874808980849,1.916640147452122
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,vwap_below,vwap_sideeqbelow,1,39,784.875,inf,1.0,1.0,784.875,1159.875,-375.0,6162.6276918125095,1.8653973545312734
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,return_1m_negative,return_1m_sideeqnegative,2,154,758.75,1.8299152310637135,0.5,0.5,-914.25,585.75,173.0,6639.52809705103,2.216671805127576
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,z_30_negative,z_30lt0.0,2,156,611.75,1.5861779853874716,0.5,0.5,-1043.625,585.75,26.0,6503.140202843915,2.1555848821097863
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,entry_candle_down,entry_candle_sideeqdown,2,146,488.25,1.6273690973337616,0.5,0.5,-778.25,585.75,-97.5,6193.013647083353,2.2015575552083826
bar_best_momentum_lb60_thr0.0006_hold30_long_us_late,range_30_low_mid,range_30_rankle0.67,1,35,136.875,inf,1.0,1.0,136.875,-8.875,145.75,5834.380810107782,2.194623900269454
bar_best_momentum_lb10_thr0.001_hold30_short_us_late,trend_120_down,trend_side_120eqdown,1,56,-655.75,0.0,0.0,0.0,-655.75,-940.75,285.0,3556.13125,2.134
bar_best_mean_reversion_lb30_thr1_hold60_short_us_late,entry_body_low_mid,entry_body_rankle0.67,1,58,-1507.25,0.0,0.0,0.0,-1507.25,-2412.25,905.0,5791.389379388682,1.8411296984717058
```

## Interpretation

- This is stricter than post-filter mining because the tested filter is selected before the future fold is evaluated.
- Repeated selection across multiple future folds is stronger evidence than a large result in one fold.
- These are still research candidates; the next step is integrating the strongest rules into the full bar strategy search and ranking pipeline.
