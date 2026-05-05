# NQ 5y State-Filtered Feature Summary

Scope: mined filters over existing 5-year NQ 1m direction-filtered walk-forward trade rows, using cached bar features and trade outcomes.

Important caveat: this is post-filter research mining. These rows are candidates for the next strict walk-forward where the filter must be selected inside each training window; they are not live-ready by themselves.

- Total mined rows passing gates: `249`
- Active miner gates: min_trades=`80`, min_folds=`2`, min_net_points=`1500`, min_profit_factor=`1.20`, min_win_rate=`0.48`
- Strong stable rows: `63` where fold hit-rate is 100%, every fold is positive, PF >= 1.5, trades >= 100
- Baseline improvers: `31` where net improvement >= 750 points and fold hit-rate is 100%
- Composite state rows: `47` using two-condition filters
- New candle/volume/VWAP-distance state rows: `117`

## Strong Stable Candidates

```csv
candidate,filter,trades,folds,net_points,profit_factor,win_rate,positive_fold_rate,min_fold_net_points,baseline_net_points,net_improvement,profit_factor_improvement,retained_trade_rate
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,vwap_below,203,5,5847.125,1.741,0.5764,1.0,776.875,6205.25,-358.125,0.3643,0.5101
bar_best_momentum_lb60_thr0.0006_hold30_long_us_late,range_30_low_mid,251,5,4736.625,1.8605,0.5259,1.0,136.875,4563.75,172.875,0.2533,0.6747
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,entry_close_low,351,4,4570.125,1.5275,0.5185,1.0,409.125,4569.25,0.875,0.1624,0.702
bar_best_mean_reversion_lb10_thr1_hold30_long_us_late,entry_candle_down,348,2,4476.0,1.624,0.5374,1.0,944.125,4483.875,-7.875,0.0287,0.9431
bar_best_mean_reversion_lb10_thr1_hold30_long_us_late,return_1m_negative,353,2,4407.875,1.5981,0.5354,1.0,1016.0,4483.875,-76.0,0.0028,0.9566
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,vwap_below,263,4,4281.625,1.6277,0.5209,1.0,430.75,4569.25,-287.625,0.2626,0.526
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,vol_120_high,172,4,3928.25,1.9461,0.5407,1.0,547.375,4569.25,-641.0,0.5809,0.344
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,range_30_high,124,5,3704.25,1.853,0.5726,1.0,199.375,6205.25,-2501.0,0.4763,0.3116
bar_best_mean_reversion_lb10_thr1_hold30_long_us_late,entry_body_low_mid,204,2,3558.5,1.9729,0.5392,1.0,585.75,4483.875,-925.375,0.3776,0.5528
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,trend_120_down_and_entry_close_low,201,4,3556.875,1.747,0.5522,1.0,588.625,4569.25,-1012.375,0.3819,0.402
bar_best_support_reclaim_lb15_thr0.0002_hold30_long_us_late,trend_120_up,215,4,3551.375,1.7884,0.5628,1.0,505.375,3576.75,-25.375,0.506,0.4335
bar_best_support_reclaim_lb15_thr0.0005_hold30_long_us_late,trend_120_up,215,4,3551.375,1.7884,0.5628,1.0,505.375,3576.75,-25.375,0.506,0.4335
```

## Baseline Improvers

```csv
candidate,filter,trades,folds,net_points,profit_factor,win_rate,positive_fold_rate,min_fold_net_points,baseline_net_points,net_improvement,profit_factor_improvement,retained_trade_rate
bar_best_mean_reversion_lb60_thr1.4_hold60_long_us_rth,vwap_distance_high,499,4,5688.625,1.3188,0.5671,1.0,1122.0,2322.375,3366.25,0.241,0.6019
bar_best_support_reclaim_lb15_thr0.001_hold30_short_us_late,momentum_60_negative_and_entry_body_low_mid,96,2,1634.5,1.6363,0.5104,1.0,310.125,-642.125,2276.625,0.7183,0.365
bar_best_support_reclaim_lb15_thr0.0002_hold30_short_us_late,momentum_60_negative_and_entry_body_low_mid,96,2,1634.5,1.6363,0.5104,1.0,310.125,-642.125,2276.625,0.7183,0.365
bar_best_support_reclaim_lb15_thr0.0005_hold30_short_us_late,momentum_60_negative_and_entry_body_low_mid,96,2,1634.5,1.6363,0.5104,1.0,310.125,-642.125,2276.625,0.7183,0.365
bar_best_support_reclaim_lb15_thr0.001_hold30_short_us_late,momentum_60_negative,114,2,1520.75,1.5368,0.5175,1.0,318.0,-642.125,2162.875,0.6187,0.4335
bar_best_support_reclaim_lb15_thr0.0002_hold30_short_us_late,momentum_60_negative,114,2,1520.75,1.5368,0.5175,1.0,318.0,-642.125,2162.875,0.6187,0.4335
bar_best_support_reclaim_lb15_thr0.0005_hold30_short_us_late,momentum_60_negative,114,2,1520.75,1.5368,0.5175,1.0,318.0,-642.125,2162.875,0.6187,0.4335
bar_best_momentum_lb30_thr0.0003_hold30_long_us_rth,vwap_distance_high,483,2,2288.125,1.2317,0.5466,1.0,586.375,187.625,2100.5,0.2217,0.5636
bar_best_momentum_lb60_thr0.0003_hold30_long_us_rth,vwap_distance_high,359,2,3383.625,1.3586,0.5515,1.0,414.375,1380.125,2003.5,0.2753,0.6116
bar_best_vwap_reclaim_lb30_thr0.0002_hold30_long_us_rth,vwap_stretched_above,266,2,1613.5,1.3939,0.5677,1.0,750.25,-147.625,1761.125,0.4018,0.3097
bar_best_vwap_reclaim_lb30_thr0.0005_hold30_long_us_rth,vwap_stretched_above,266,2,1613.5,1.3939,0.5677,1.0,750.25,-147.625,1761.125,0.4018,0.3097
bar_best_mean_reversion_lb30_thr1.4_hold30_long_us_late,vwap_below,194,3,3497.75,1.6886,0.5619,1.0,835.625,1797.375,1700.375,0.5049,0.5689
```

## Composite State Candidates

```csv
candidate,filter,trades,folds,net_points,profit_factor,win_rate,positive_fold_rate,min_fold_net_points,baseline_net_points,net_improvement,profit_factor_improvement,retained_trade_rate
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,trend_120_down_and_entry_close_low,201,4,3556.875,1.747,0.5522,1.0,588.625,4569.25,-1012.375,0.3819,0.402
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,vwap_stretched_below_and_z_30_negative,105,5,3350.125,1.711,0.6286,0.8,-59.375,6205.25,-2855.125,0.3343,0.2638
bar_best_momentum_lb60_thr0.0006_hold30_long_us_late,trend_120_up_and_range_30_low_mid,193,5,3267.625,1.7886,0.5285,0.8,-477.5,4563.75,-1296.125,0.1814,0.5188
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,vwap_below_and_trend_120_down,141,5,3247.625,1.5926,0.5603,1.0,220.0,6205.25,-2957.625,0.2158,0.3543
bar_best_momentum_lb30_thr0.0006_hold60_long_us_rth,trend_120_up_and_entry_close_high,226,2,2912.75,1.4344,0.5752,1.0,1278.75,2030.5,882.25,0.3291,0.4185
bar_best_support_reclaim_lb15_thr0.0002_hold30_long_us_late,trend_120_up_and_z_30_negative,156,4,2764.75,1.7622,0.5833,1.0,324.0,3576.75,-812.0,0.4798,0.3145
bar_best_support_reclaim_lb15_thr0.0005_hold30_long_us_late,trend_120_up_and_z_30_negative,156,4,2764.75,1.7622,0.5833,1.0,324.0,3576.75,-812.0,0.4798,0.3145
bar_best_support_reclaim_lb15_thr0.001_hold30_long_us_late,trend_120_up_and_z_30_negative,156,4,2764.75,1.7622,0.5833,1.0,324.0,3576.75,-812.0,0.4798,0.3145
bar_best_momentum_lb60_thr0.0006_hold30_long_us_late,momentum_60_positive_and_entry_body_low_mid,195,5,2761.375,1.5253,0.5026,0.6,-254.375,4563.75,-1802.375,-0.082,0.5242
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,trend_120_down_and_range_30_low_mid,203,4,2750.875,1.5372,0.5665,0.75,-301.75,4569.25,-1818.375,0.172,0.406
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,vwap_below_and_trend_120_down,194,4,2727.75,1.6017,0.5309,1.0,563.875,4569.25,-1841.5,0.2366,0.388
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,vwap_stretched_below_and_z_30_negative,143,4,2726.125,1.694,0.5455,1.0,346.75,4569.25,-1843.125,0.3289,0.286
```

## New State Feature Candidates

```csv
candidate,filter,trades,folds,net_points,profit_factor,win_rate,positive_fold_rate,min_fold_net_points,baseline_net_points,net_improvement,profit_factor_improvement,retained_trade_rate
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,return_1m_negative,369,5,6462.125,1.4147,0.561,0.8,-914.25,6205.25,256.875,0.0379,0.9271
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,entry_candle_down,355,5,6046.875,1.4097,0.5606,0.8,-778.25,6205.25,-158.375,0.033,0.892
bar_best_mean_reversion_lb60_thr1.4_hold60_long_us_rth,vwap_distance_high,499,4,5688.625,1.3188,0.5671,1.0,1122.0,2322.375,3366.25,0.241,0.6019
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,return_1m_negative,463,4,4869.875,1.4132,0.5227,0.75,-440.75,4569.25,300.625,0.048,0.926
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,entry_close_low,351,4,4570.125,1.5275,0.5185,1.0,409.125,4569.25,0.875,0.1624,0.702
bar_best_mean_reversion_lb10_thr1_hold30_long_us_late,entry_candle_down,348,2,4476.0,1.624,0.5374,1.0,944.125,4483.875,-7.875,0.0287,0.9431
bar_best_mean_reversion_lb10_thr1_hold30_long_us_late,return_1m_negative,353,2,4407.875,1.5981,0.5354,1.0,1016.0,4483.875,-76.0,0.0028,0.9566
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,entry_candle_down,457,4,4353.625,1.3681,0.5142,0.75,-457.5,4569.25,-215.625,0.0029,0.914
bar_best_support_reclaim_lb15_thr0.0002_hold60_short_us_late,return_1m_positive,98,2,4135.5,2.0946,0.5918,1.0,806.0,2602.875,1532.625,0.7769,0.5665
bar_best_support_reclaim_lb15_thr0.0005_hold60_short_us_late,return_1m_positive,98,2,4135.5,2.0946,0.5918,1.0,806.0,2602.875,1532.625,0.7769,0.5665
bar_best_support_reclaim_lb15_thr0.001_hold60_short_us_late,return_1m_positive,98,2,4135.5,2.0946,0.5918,1.0,806.0,2602.875,1532.625,0.7769,0.5665
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,vwap_distance_high,224,5,4059.75,1.4501,0.567,1.0,169.125,6205.25,-2145.5,0.0733,0.5628
```

## Practical Read

- Best stability filter: mean-reversion long late session below VWAP kept 203 trades across 5 folds, net 5847.125 points, PF 1.7410, and all folds positive.
- Best multi-fold true improvement: RTH mean-reversion with high VWAP distance improved from 2322.375 to 5688.625 net points across 4 folds, but PF is 1.3188, so it needs stricter validation.
- Best support-reclaim refinement: long support reclaim in 120-minute uptrend kept nearly the same net while turning every fold positive and PF from 1.2824 to 1.7884.
- Best newly added microstate by net: negative 1-minute return before entry improved the top late mean-reversion long to 6462.125 net points, but still leaves one negative fold.
