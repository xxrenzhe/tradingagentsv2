# NQ State Filter Past-Fold Walk-Forward Validation

Each test fold selects candidate filters only from earlier folds, then evaluates the selected filters on the current future fold.

- Trades input: `.tmp/nq-short-trend-2010-state-time-input-trades.csv`
- Feature cache: `.tmp/nq-short-trend-2010-adx-cache.pkl`
- Fold rows tested: `113`
- Aggregate rows: `55`
- Total selected-filter future net points: `13510.750`
- Same candidate unfiltered future net points: `15889.875`
- Future net improvement: `-2379.125`
- Gates: min_train_folds=`3`, min_train_trades=`40`, min_train_net_points=`200.0`, min_train_profit_factor=`1.05`, min_train_win_rate=`0.42`, min_train_positive_fold_rate=`0.6`, min_train_min_fold_net_points=`-150.0`

## Top Future-Validated Filters

```csv
candidate,filter,filter_conditions,selected_folds,test_trades,test_net_points,fold_net_profit_factor,positive_selected_fold_rate,positive_test_fold_rate,min_test_fold_net_points,test_baseline_net_points,test_net_improvement,avg_train_score,avg_train_profit_factor
trend_donchian_breakout_3m_us_rth_lb30_thr0_hold90m_both_time,range_30_high,range_30_rankgt0.67,4,798,3030.75,inf,1.0,1.0,526.875,2999.125,31.625,4825.801501700527,1.194894379251318
trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold90m_both_time,minute_bucket_30_27,minute_bucket_30eq27,3,147,1805.625,inf,1.0,1.0,334.875,1551.625,254.0,4229.163545368872,1.7525963634221817
trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold90m_both_time,range_30_high,range_30_rankgt0.67,3,584,1750.0,inf,1.0,1.0,433.25,1551.625,198.375,5531.46191520814,1.2644620796870187
trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold90m_both_time,entry_candle_up,entry_candle_sideequp,3,330,1497.5,inf,1.0,1.0,7.625,1551.625,-54.125,4075.291589314216,1.3800258482855394
trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold90m_both_time,vwap_distance_high,vwap_distance_abs_rankgt0.67,3,443,1491.125,inf,1.0,1.0,182.375,1551.625,-60.5,4457.157102850691,1.269976090460063
trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold90m_both_time,volume_z_60_high,volume_z_60gt1.0,2,189,1269.125,inf,1.0,1.0,599.0,744.625,524.5,5217.579883295952,1.4724653332398794
trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold90m_both_time,entry_close_high,entry_close_zoneeqhigh,3,242,1119.5,13.13550135501355,0.6666666666666666,0.6666666666666666,-92.25,1551.625,-432.125,4380.07563784406,1.6100068029434842
trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold90m_both_time,return_1m_positive,return_1m_sideeqpositive,2,225,958.375,inf,1.0,1.0,30.375,1176.125,-217.75,3707.9401260976624,1.3728190652441563
trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold90m_both_time,entry_body_high,entry_body_rankgt0.67,1,168,474.0,inf,1.0,1.0,474.0,375.5,98.5,4179.6800552714985,1.1858407631787469
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold60m_long_time,entry_body_high,entry_body_rankgt0.67,4,64,368.5,41.38356164383562,0.75,0.75,-9.125,287.875,80.625,2011.890161662313,3.497451408620068
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr32_hold90m_long_time,vwap_stretched_above,vwap_stretch_sideeqabove,4,40,280.5,26.213483146067414,0.75,0.75,-11.125,197.625,82.875,1837.3923768408786,3.274377519483149
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold90m_long_time,vwap_stretched_above,vwap_stretch_sideeqabove,3,57,199.375,2.0370611183355005,0.6666666666666666,0.6666666666666666,-192.25,65.625,133.75,2198.7369310846298,3.2847234830146053
trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold90m_both_time,vwap_below_and_entry_close_high,vwap_sideeqbelow;entry_close_zoneeqhigh,1,23,194.625,inf,1.0,1.0,194.625,807.0,-612.375,3145.5898347792804,3.092880836948201
trend_vwap_trend_pullback_1m_us_rth_lb30_thr0_hold90m_both_time,momentum_60_positive,momentum_60gt0.0,1,30,189.0,inf,1.0,1.0,189.0,83.0,106.0,1590.044782225579,1.4914400805639476
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold90m_long_time,z_30_positive,z_30gt0.0,4,76,182.0,6.6434108527131785,0.75,0.75,-32.25,103.875,78.125,1587.7353249788007,2.5705018169112877
trend_vwap_trend_pullback_1m_us_rth_lb30_thr0_hold90m_both_time,trend_120_up_and_range_30_low_mid,trend_side_120equp;range_30_rankle0.67,3,35,178.125,7.3053097345132745,0.6666666666666666,0.6666666666666666,-28.25,233.25,-55.125,1798.9147155899707,2.2109586639749264
trend_vwap_trend_pullback_1m_us_rth_lb30_thr0_hold90m_both_time,vwap_distance_low_mid,vwap_distance_abs_rankle0.67,1,71,147.375,inf,1.0,1.0,147.375,313.75,-166.375,2522.7640592151365,1.2308163980378417
trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold90m_both_time,entry_body_high,entry_body_rankgt0.67,4,204,139.0,1.7374005305039788,0.75,0.75,-188.5,129.25,9.75,1004.3027437190797,1.3306815244762702
trend_vwap_trend_pullback_1m_us_rth_lb30_thr0_hold90m_both_time,vol_120_low_mid,vol_120_rankle0.67,3,106,101.25,1.7130281690140845,0.6666666666666666,0.6666666666666666,-142.0,1974.75,-1873.5,1852.2902191365138,1.5705953395079513
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold90m_long_time,vwap_stretched_above_and_z_30_positive,vwap_stretch_sideeqabove;z_30gt0.0,2,32,98.0,1.7466666666666666,0.5,0.5,-131.25,-16.125,114.125,2524.5848112477447,3.9623071985739076
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr32_hold90m_long_time,vwap_distance_high,vwap_distance_abs_rankgt0.67,5,60,89.0,1.4378843788437885,0.6,0.6,-192.125,-18.125,107.125,1908.2319467896086,3.1974164470606015
trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold90m_both_time,vol_120_high,vol_120_rankgt0.67,5,118,77.0,1.8837876614060258,0.6,0.6,-86.5,61.0,16.0,970.6171395883451,1.4441857061137202
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold90m_long_time,entry_close_high,entry_close_zoneeqhigh,2,32,64.75,3.1673640167364017,0.5,0.5,-29.875,72.0,-7.25,1646.9600558695433,3.157093220031001
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold90m_long_time,trend_120_up,trend_side_120equp,1,27,62.375,inf,1.0,1.0,62.375,63.875,-1.5,1356.3723854581672,2.5836653386454183
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold90m_long_time,momentum_60_positive,momentum_60gt0.0,1,26,58.75,inf,1.0,1.0,58.75,63.875,-5.125,1361.6735819327732,2.6239495798319328
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold90m_long_time,trend_120_up_and_entry_close_high,trend_side_120equp;entry_close_zoneeqhigh,2,29,45.375,2.762135922330097,0.5,0.5,-25.75,72.0,-26.625,1670.8972093118068,3.27326422863666
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr32_hold90m_long_time,z_30_positive,z_30gt0.0,1,12,33.0,inf,1.0,1.0,33.0,55.25,-22.25,1523.2614329268295,2.7307317073170734
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold60m_long_time,trend_120_up_and_range_30_low_mid,trend_side_120equp;range_30_rankle0.67,1,39,25.875,inf,1.0,1.0,25.875,19.625,6.25,1577.3892014457174,1.9530823786142935
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold90m_long_time,vol_120_high,vol_120_rankgt0.67,1,7,23.875,inf,1.0,1.0,23.875,63.875,-40.0,1328.7786113936927,2.757884028484232
trend_vwap_trend_pullback_1m_us_rth_lb30_thr0_hold90m_both_time,trend_120_up_and_vol_120_low_mid,trend_side_120equp;vol_120_rankle0.67,3,59,12.125,1.0386454183266933,0.6666666666666666,0.6666666666666666,-313.75,233.25,-221.125,1780.466823361903,2.1635368500714236
```

## Interpretation

- This is stricter than post-filter mining because the tested filter is selected before the future fold is evaluated.
- Repeated selection across multiple future folds is stronger evidence than a large result in one fold.
- These are still research candidates; the next step is integrating the strongest rules into the full bar strategy search and ranking pipeline.
