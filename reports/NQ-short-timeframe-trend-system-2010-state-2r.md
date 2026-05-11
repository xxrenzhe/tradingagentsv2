# NQ State Filter Past-Fold Walk-Forward Validation

Each test fold selects candidate filters only from earlier folds, then evaluates the selected filters on the current future fold.

- Trades input: `.tmp/nq-short-trend-2010-state-2r-input-trades.csv`
- Feature cache: `.tmp/nq-short-trend-2010-adx-cache.pkl`
- Fold rows tested: `32`
- Aggregate rows: `22`
- Total selected-filter future net points: `559.250`
- Same candidate unfiltered future net points: `1364.000`
- Future net improvement: `-804.750`
- Gates: min_train_folds=`3`, min_train_trades=`40`, min_train_net_points=`150.0`, min_train_profit_factor=`1.05`, min_train_win_rate=`0.38`, min_train_positive_fold_rate=`0.6`, min_train_min_fold_net_points=`-150.0`

## Top Future-Validated Filters

```csv
candidate,filter,filter_conditions,selected_folds,test_trades,test_net_points,fold_net_profit_factor,positive_selected_fold_rate,positive_test_fold_rate,min_test_fold_net_points,test_baseline_net_points,test_net_improvement,avg_train_score,avg_train_profit_factor
trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold90m_both_sl20_tp40,z_30_positive,z_30gt0.0,1,68,304.5,inf,1.0,1.0,304.5,26.5,278.0,1938.7510967524217,1.6021121168810544
trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold90m_both_sl20_tp40,entry_close_high,entry_close_zoneeqhigh,1,33,126.125,inf,1.0,1.0,126.125,26.5,99.625,2097.6609606590982,2.1392305266477454
trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold60m_long_sl24_tp48,range_30_high,range_30_rankgt0.67,4,186,118.25,1.3652509652509652,0.75,0.75,-323.75,110.0,8.25,1850.0203953830985,1.536448867922032
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold90m_long_sl12_tp24,vwap_distance_high,vwap_distance_abs_rankgt0.67,1,12,91.5,inf,1.0,1.0,91.5,52.125,39.375,1571.734260948905,2.437226277372263
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold90m_long_sl12_tp24,vwap_stretched_above,vwap_stretch_sideeqabove,1,11,90.875,inf,1.0,1.0,90.875,52.125,38.75,1487.9169708029199,2.3007299270072994
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold90m_long_sl12_tp24,trend_120_up,trend_side_120equp,1,28,64.75,inf,1.0,1.0,64.75,52.125,12.625,1375.6374834967937,1.8430780837419842
trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold60m_both_sl24_tp48,minute_bucket_30_27,minute_bucket_30eq27,1,28,64.0,inf,1.0,1.0,64.0,232.75,-168.75,1936.5372809928326,1.4624369524820813
trend_vwap_trend_pullback_3m_us_rth_lb20_thr0_hold60m_both_sl24_tp48,range_30_high,range_30_rankgt0.67,1,96,63.75,inf,1.0,1.0,63.75,39.125,24.625,1597.4770344294188,1.3415832110735473
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold90m_long_sl12_tp24,z_30_positive,z_30gt0.0,1,22,60.5,inf,1.0,1.0,60.5,52.125,8.375,1396.2260308093196,2.0797057020232987
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold90m_long_sl12_tp24,momentum_60_positive,momentum_60gt0.0,1,24,43.75,inf,1.0,1.0,43.75,52.125,-8.375,1378.7006565857541,1.8698766414643853
trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold60m_both_sl20_tp40,z_30_positive,z_30gt0.0,1,66,34.5,inf,1.0,1.0,34.5,196.375,-161.875,1981.5369566999204,1.378998641749801
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold90m_long_sl12_tp24,trend_120_up_and_range_30_low_mid,trend_side_120equp;range_30_rankle0.67,1,26,27.75,inf,1.0,1.0,27.75,52.125,-24.375,1562.7208076131687,2.241255144032922
trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold60m_long_sl24_tp48,entry_close_high,entry_close_zoneeqhigh,4,125,15.625,1.040257648953301,0.75,0.75,-388.125,99.5,-83.875,1900.1842153850496,1.8434013866769101
trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold90m_long_sl12_tp24,range_30_low_mid,range_30_rankle0.67,1,27,15.125,inf,1.0,1.0,15.125,52.125,-37.0,1373.7399595267746,1.8816936488169365
trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold60m_both_sl20_tp40,minute_bucket_30_28,minute_bucket_30eq28,1,9,4.125,inf,1.0,1.0,4.125,58.625,-54.5,1949.3305510484274,2.3344982526210685
trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold90m_both_sl24_tp48,z_30_negative,z_30lt0.0,1,82,-5.25,0.0,0.0,0.0,-5.25,14.375,-19.625,2030.9671068570447,1.2607771421426115
trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold60m_both_sl20_tp40,minute_bucket_30_27,minute_bucket_30eq27,1,24,-15.0,0.0,0.0,0.0,-15.0,338.875,-353.875,1963.479695431472,2.4549492385786804
trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold60m_short_sl24_tp48,trend_120_down_and_entry_close_low,trend_side_120eqdown;entry_close_zoneeqlow,1,42,-26.25,0.0,0.0,0.0,-26.25,-22.75,-3.5,1926.8836724499486,1.5538498061248713
trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold90m_both_sl24_tp48,trend_120_down_and_entry_close_low,trend_side_120eqdown;entry_close_zoneeqlow,1,53,-85.125,0.0,0.0,0.0,-85.125,73.5,-158.625,1977.2236915632282,1.3925904789080705
trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold90m_long_sl20_tp40,entry_close_high,entry_close_zoneeqhigh,3,136,-92.25,0.6546560598970519,0.6666666666666666,0.6666666666666666,-267.125,-133.875,41.625,1945.311145963703,1.573868142687035
trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold90m_long_sl20_tp40,trend_120_up_and_entry_close_high,trend_side_120equp;entry_close_zoneeqhigh,3,128,-107.25,0.5615738375063873,0.6666666666666666,0.6666666666666666,-244.625,-133.875,26.625,1969.5854086659028,1.5955781049980906
trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold90m_both_sl24_tp48,entry_close_low,entry_close_zoneeqlow,1,62,-234.75,0.0,0.0,0.0,-234.75,73.5,-308.25,2053.2437219775034,1.3482655549437583
```

## Interpretation

- This is stricter than post-filter mining because the tested filter is selected before the future fold is evaluated.
- Repeated selection across multiple future folds is stronger evidence than a large result in one fold.
- These are still research candidates; the next step is integrating the strongest rules into the full bar strategy search and ranking pipeline.
