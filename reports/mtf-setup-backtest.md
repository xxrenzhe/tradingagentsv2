# MTF Setup Backtest

Implements the current landing logic as script-scanned candidates: M15 direction filter, M3 reclaim, M1 trigger, then bracket-style exits.

- Symbol: `NQM6`
- Window: `2026-03-03` to `2026-05-02`
- Feature rows: `60,503`
- Min trades gate: `20`
- Qualified candidates: `112`
- Validation: `FAIL`
- Best spec: `mtf_setup_m1_m3_reclaim_all_htfconfirm_r5_imb0.35_sl16_tp32`
- Trades output: `.tmp/mtf-setup-trades.csv`
- Summary output: `.tmp/mtf-setup-summary.csv`
- Notes: `best candidate net points is -266.00, not positive ; best candidate profit factor is 0.31, not above 1`

## Best Summary

```csv
name,session,htf_mode,htf_fast_ema,htf_slow_ema,mtf_fast_ema,mtf_slow_ema,ltf_fast_ema,reclaim_lookback_minutes,imbalance_threshold,stop_loss_points,take_profit_points,max_hold_minutes,round_trip_cost_points,trades,net_points,net_dollars,max_drawdown_points,profit_factor,win_rate,avg_points,avg_holding_minutes,long_trades,short_trades,score
mtf_setup_m1_m3_reclaim_all_htfconfirm_r5_imb0.35_sl16_tp32,all,confirm,2,4,3,8,5,5,0.35,16.0,32.0,6,1.5,27,-266.0,-532.0,261.5,0.31443298969072164,0.14814814814814814,-9.851851851851851,1.4074074074074074,18,9,-0.39641774697130905
```

## Top 10

```csv
name,session,htf_mode,htf_fast_ema,htf_slow_ema,mtf_fast_ema,mtf_slow_ema,ltf_fast_ema,reclaim_lookback_minutes,imbalance_threshold,stop_loss_points,take_profit_points,max_hold_minutes,round_trip_cost_points,trades,net_points,net_dollars,max_drawdown_points,profit_factor,win_rate,avg_points,avg_holding_minutes,long_trades,short_trades,score
mtf_setup_m1_m3_reclaim_europe_htfconfirm_r3_imb0.35_sl8_tp16,europe,confirm,2,4,3,8,5,3,0.35,8.0,16.0,6,1.5,1,-9.5,-19.0,0.0,0.0,0.0,-9.5,1.0,0,1,-0.07500000000000001
mtf_setup_m1_m3_reclaim_europe_htfconfirm_r3_imb0.35_sl12_tp24,europe,confirm,2,4,3,8,5,3,0.35,12.0,24.0,6,1.5,1,-13.5,-27.0,0.0,0.0,0.0,-13.5,1.0,0,1,-0.07500000000000001
mtf_setup_m1_m3_reclaim_europe_htfconfirm_r3_imb0.35_sl16_tp24,europe,confirm,2,4,3,8,5,3,0.35,16.0,24.0,6,1.5,1,-17.5,-35.0,0.0,0.0,0.0,-17.5,1.0,0,1,-0.07500000000000001
mtf_setup_m1_m3_reclaim_europe_htfconfirm_r3_imb0.35_sl16_tp32,europe,confirm,2,4,3,8,5,3,0.35,16.0,32.0,6,1.5,1,-17.5,-35.0,0.0,0.0,0.0,-17.5,1.0,0,1,-0.07500000000000001
mtf_setup_m1_m3_reclaim_europe_htfoff_r3_imb0.35_sl16_tp32,europe,off,2,4,3,8,5,3,0.35,16.0,32.0,6,1.5,4,-22.0,-44.0,35.0,0.580952380952381,0.25,-5.5,1.25,2,2,-0.09428571428571429
mtf_setup_m1_m3_reclaim_europe_htfoff_r3_imb0.35_sl12_tp24,europe,off,2,4,3,8,5,3,0.35,12.0,24.0,6,1.5,4,-18.0,-36.0,27.0,0.5555555555555556,0.25,-4.5,1.25,2,2,-0.1
mtf_setup_m1_m3_reclaim_europe_htfoff_r3_imb0.35_sl8_tp16,europe,off,2,4,3,8,5,3,0.35,8.0,16.0,6,1.5,4,-14.0,-28.0,19.0,0.5087719298245614,0.25,-3.5,1.0,2,2,-0.11052631578947367
mtf_setup_m1_m3_reclaim_europe_htfoff_r5_imb0.35_sl16_tp32,europe,off,2,4,3,8,5,5,0.35,16.0,32.0,6,1.5,5,-39.5,-79.0,52.5,0.4357142857142857,0.2,-7.9,1.2,3,2,-0.12617812158748815
mtf_setup_m1_m3_reclaim_europe_htfoff_r3_imb0.35_sl16_tp24,europe,off,2,4,3,8,5,3,0.35,16.0,24.0,6,1.5,4,-30.0,-60.0,35.0,0.42857142857142855,0.25,-7.5,1.25,2,2,-0.12857142857142856
mtf_setup_m1_m3_reclaim_europe_htfoff_r5_imb0.35_sl12_tp24,europe,off,2,4,3,8,5,5,0.35,12.0,24.0,6,1.5,5,-31.5,-63.0,40.5,0.4166666666666667,0.2,-6.3,1.2,3,2,-0.13043729868748774
```
