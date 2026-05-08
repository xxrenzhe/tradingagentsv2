# NQ Short-Timeframe Trend System Search

## Candidate Sources

Industry-standard trend archetypes translated into mechanical rules: opening range breakout, Donchian/channel breakout, VWAP trend pullback, EMA trend/pullback, and ADX/DI trend following.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Base 1m span: `2021-04-28 00:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Base rows: `1,769,740`.
- Costs: `0.625` NQ points round trip.

## Walk-Forward

- Timeframes: `1m, 3m`.
- Train/test: `365` train days, `5` purge days, `90` test days, `90` step days.
- Sessions: `us_rth, us_late`.
- Direction filters: `long, short, both`.
- Exit profiles: `time`.
- Stable gate: selected folds >= 3, positive fold rate >= 67%, aggregate net > 0, avg PF >= 1.1, net/drawdown >= 1, and no negative selected OOS fold.

## Verdict

No 1m/3m trend candidate passed the stable profitability gate.
Best positive research candidate: `trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold15m_both_time` (2254.25 OOS points, stable=False).

## Top Aggregate Rows

| stable_candidate | candidate | family | timeframe_minutes | session | holding_minutes | direction_filter | exit_profile | selected_folds | positive_test_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold15m_both_time | adx_di_trend | 1 | us_rth | 15 | both | time | 3 | 1.0000 | 2036 | 2254.2500 | 1375.6250 | 1.6387 | 1.0708 | 25.7500 |
| False | trend_adx_di_trend_1m_us_late_lb14_adx14_thr26_hold30m_both_time | adx_di_trend | 1 | us_late | 30 | both | time | 7 | 0.7143 | 931 | 1833.6250 | 1002.7500 | 1.8286 | 1.2337 | -1004.1250 |
| False | trend_ema_pullback_1m_us_rth_lb21_ema9_21_thr0_hold30m_both_time | ema_pullback | 1 | us_rth | 30 | both | time | 2 | 1.0000 | 1441 | 1770.8750 | 2368.8750 | 0.7476 | 1.0757 | 174.6250 |
| False | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 4 | 0.7500 | 1315 | 1487.6250 | 1673.5000 | 0.8889 | 1.0589 | -441.2500 |
| False | trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold15m_short_time | donchian_atr_breakout | 3 | us_rth | 15 | short | time | 2 | 1.0000 | 361 | 951.8750 | 511.8750 | 1.8596 | 1.1517 | 458.3750 |
| False | trend_opening_range_breakout_1m_us_rth_lb15_thr0.5_hold30m_both_time | opening_range_breakout | 1 | us_rth | 30 | both | time | 2 | 0.5000 | 414 | 851.2500 | 1994.5000 | 0.4268 | 1.1171 | -840.7500 |
| False | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold30m_short_time | adx_di_trend | 1 | us_rth | 30 | short | time | 3 | 0.6667 | 876 | 833.2500 | 964.0000 | 0.8644 | 1.0586 | -695.1250 |
| False | trend_ema_pullback_1m_us_rth_lb55_ema21_55_thr0_hold30m_short_time | ema_pullback | 1 | us_rth | 30 | short | time | 2 | 1.0000 | 636 | 792.5000 | 1386.0000 | 0.5718 | 1.0528 | 178.5000 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold30m_short_time | vwap_trend_pullback | 1 | us_rth | 30 | short | time | 6 | 0.6667 | 252 | 733.2500 | 627.1250 | 1.1692 | 1.3352 | -449.8750 |
| False | trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.5_hold30m_short_time | donchian_atr_breakout | 3 | us_rth | 30 | short | time | 3 | 0.3333 | 316 | 638.7500 | 807.5000 | 0.7910 | 1.1082 | -275.7500 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.25_hold30m_long_time | vwap_trend_pullback | 1 | us_rth | 30 | long | time | 3 | 0.6667 | 130 | 610.0000 | 453.7500 | 1.3444 | 1.4380 | -259.7500 |
| False | trend_donchian_atr_breakout_3m_us_rth_lb50_thr0.5_hold15m_short_time | donchian_atr_breakout | 3 | us_rth | 15 | short | time | 2 | 0.5000 | 165 | 584.1250 | 531.8750 | 1.0982 | 1.2819 | -107.3750 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.25_hold15m_long_time | vwap_trend_pullback | 1 | us_rth | 15 | long | time | 3 | 0.6667 | 147 | 540.3750 | 218.7500 | 2.4703 | 1.7139 | -66.2500 |
| False | trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.5_hold15m_short_time | donchian_atr_breakout | 3 | us_rth | 15 | short | time | 3 | 0.6667 | 373 | 497.1250 | 923.8750 | 0.5381 | 1.1030 | -653.3750 |
| False | trend_ema_pullback_1m_us_late_lb21_ema9_21_thr0_hold30m_short_time | ema_pullback | 1 | us_late | 30 | short | time | 4 | 0.7500 | 552 | 404.0000 | 405.1250 | 0.9972 | 1.1370 | -90.3750 |
| False | trend_donchian_atr_breakout_1m_us_rth_lb50_thr0.5_hold15m_short_time | donchian_atr_breakout | 1 | us_rth | 15 | short | time | 2 | 1.0000 | 394 | 384.7500 | 678.7500 | 0.5669 | 1.0663 | 69.1250 |
| False | trend_ema_pullback_3m_us_late_lb55_ema21_55_thr0.25_hold15m_short_time | ema_pullback | 3 | us_late | 15 | short | time | 4 | 0.7500 | 356 | 353.7500 | 408.3750 | 0.8662 | 1.1764 | -367.1250 |
| False | trend_ema_pullback_1m_us_late_lb21_ema9_21_thr0.25_hold30m_short_time | ema_pullback | 1 | us_late | 30 | short | time | 3 | 0.6667 | 470 | 351.7500 | 378.7500 | 0.9287 | 1.1699 | -165.8750 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.25_hold30m_both_time | vwap_trend_pullback | 1 | us_rth | 30 | both | time | 5 | 0.6000 | 461 | 315.1250 | 907.5000 | 0.3472 | 1.1154 | -730.8750 |
| False | trend_opening_range_breakout_1m_us_rth_lb15_thr0.5_hold30m_long_time | opening_range_breakout | 1 | us_rth | 30 | long | time | 3 | 0.6667 | 316 | 288.5000 | 673.8750 | 0.4281 | 1.0423 | -172.8750 |
| False | trend_ema_pullback_3m_us_late_lb55_ema21_55_thr0_hold15m_long_time | ema_pullback | 3 | us_late | 15 | long | time | 5 | 0.6000 | 356 | 243.7500 | 142.2500 | 1.7135 | 1.1641 | -30.0000 |
| False | trend_opening_range_breakout_3m_us_rth_lb15_thr0.25_hold15m_long_time | opening_range_breakout | 3 | us_rth | 15 | long | time | 3 | 0.6667 | 355 | 228.1250 | 514.7500 | 0.4432 | 1.0353 | -74.0000 |
| False | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr22_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 1 | 1.0000 | 471 | 227.6250 | 2123.6250 | 0.1072 | 1.0169 | 227.6250 |
| False | trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.5_hold30m_both_time | donchian_atr_breakout | 3 | us_rth | 30 | both | time | 1 | 1.0000 | 204 | 189.0000 | 312.6250 | 0.6046 | 1.0770 | 189.0000 |
| False | trend_opening_range_breakout_1m_us_rth_lb15_thr0.25_hold15m_long_time | opening_range_breakout | 1 | us_rth | 15 | long | time | 2 | 0.5000 | 291 | 183.3750 | 610.5000 | 0.3004 | 1.0438 | -128.2500 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold30m_both_time | vwap_trend_pullback | 1 | us_rth | 30 | both | time | 6 | 0.5000 | 501 | 172.6250 | 789.8750 | 0.2185 | 1.0757 | -750.1250 |
| False | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr22_hold30m_short_time | adx_di_trend | 1 | us_rth | 30 | short | time | 1 | 1.0000 | 397 | 167.6250 | 1002.2500 | 0.1672 | 1.0254 | 167.6250 |
| False | trend_opening_range_breakout_1m_us_rth_lb30_thr0.5_hold15m_long_time | opening_range_breakout | 1 | us_rth | 15 | long | time | 1 | 1.0000 | 108 | 150.7500 | 650.7500 | 0.2317 | 1.0645 | 150.7500 |
| False | trend_donchian_atr_breakout_1m_us_rth_lb20_thr0.5_hold15m_short_time | donchian_atr_breakout | 1 | us_rth | 15 | short | time | 1 | 1.0000 | 283 | 117.3750 | 1158.5000 | 0.1013 | 1.0292 | 117.3750 |
| False | trend_opening_range_breakout_3m_us_rth_lb30_thr0.25_hold30m_long_time | opening_range_breakout | 3 | us_rth | 30 | long | time | 1 | 1.0000 | 89 | 114.8750 | 214.6250 | 0.5352 | 1.1150 | 114.8750 |

## Full-Sample Check

| candidate | family | timeframe_minutes | session | holding_minutes | direction_filter | exit_profile | trades | net_points | profit_factor | win_rate | max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold15m_both_time | adx_di_trend | 1 | us_rth | 15 | both | time | 14188 | 3600.0000 | 1.0212 | 0.4874 | 2775.5000 |
| trend_adx_di_trend_1m_us_late_lb14_adx14_thr26_hold30m_both_time | adx_di_trend | 1 | us_late | 30 | both | time | 2705 | 614.1250 | 1.0224 | 0.4628 | 2706.0000 |
| trend_ema_pullback_1m_us_rth_lb21_ema9_21_thr0_hold30m_both_time | ema_pullback | 1 | us_rth | 30 | both | time | 14645 | -4477.6250 | 0.9819 | 0.4931 | 6758.6250 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 7034 | 7083.0000 | 1.0584 | 0.4982 | 2495.0000 |
| trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold15m_short_time | donchian_atr_breakout | 3 | us_rth | 15 | short | time | 3764 | 974.5000 | 1.0183 | 0.4769 | 2176.3750 |
| trend_opening_range_breakout_1m_us_rth_lb15_thr0.5_hold30m_both_time | opening_range_breakout | 1 | us_rth | 30 | both | time | 4301 | 1826.3750 | 1.0229 | 0.5085 | 4505.3750 |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold30m_short_time | adx_di_trend | 1 | us_rth | 30 | short | time | 6106 | -3346.5000 | 0.9701 | 0.4681 | 6503.2500 |
| trend_ema_pullback_1m_us_rth_lb55_ema21_55_thr0_hold30m_short_time | ema_pullback | 1 | us_rth | 30 | short | time | 6373 | -553.8750 | 0.9952 | 0.4731 | 3932.0000 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold30m_short_time | vwap_trend_pullback | 1 | us_rth | 30 | short | time | 879 | 3607.6250 | 1.2221 | 0.4892 | 1009.8750 |
| trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.5_hold30m_short_time | donchian_atr_breakout | 3 | us_rth | 30 | short | time | 2257 | 1317.6250 | 1.0288 | 0.4772 | 2902.6250 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.25_hold30m_long_time | vwap_trend_pullback | 1 | us_rth | 30 | long | time | 919 | -263.8750 | 0.9847 | 0.5038 | 1470.2500 |
| trend_donchian_atr_breakout_3m_us_rth_lb50_thr0.5_hold15m_short_time | donchian_atr_breakout | 3 | us_rth | 15 | short | time | 1667 | 196.8750 | 1.0075 | 0.4877 | 1377.6250 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.25_hold15m_long_time | vwap_trend_pullback | 1 | us_rth | 15 | long | time | 954 | -161.0000 | 0.9872 | 0.5021 | 890.2500 |
| trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.5_hold15m_short_time | donchian_atr_breakout | 3 | us_rth | 15 | short | time | 2529 | 1876.3750 | 1.0507 | 0.4836 | 1256.2500 |
| trend_ema_pullback_1m_us_late_lb21_ema9_21_thr0_hold30m_short_time | ema_pullback | 1 | us_late | 30 | short | time | 2905 | -607.3750 | 0.9794 | 0.4599 | 2633.7500 |
| trend_donchian_atr_breakout_1m_us_rth_lb50_thr0.5_hold15m_short_time | donchian_atr_breakout | 1 | us_rth | 15 | short | time | 3838 | -167.0000 | 0.9970 | 0.4760 | 2360.1250 |
| trend_ema_pullback_3m_us_late_lb55_ema21_55_thr0.25_hold15m_short_time | ema_pullback | 3 | us_late | 15 | short | time | 1476 | 1319.5000 | 1.1219 | 0.4695 | 903.1250 |
| trend_ema_pullback_1m_us_late_lb21_ema9_21_thr0.25_hold30m_short_time | ema_pullback | 1 | us_late | 30 | short | time | 3176 | -1272.5000 | 0.9608 | 0.4594 | 2944.5000 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.25_hold30m_both_time | vwap_trend_pullback | 1 | us_rth | 30 | both | time | 1875 | 2151.1250 | 1.0610 | 0.4912 | 1581.6250 |
| trend_opening_range_breakout_1m_us_rth_lb15_thr0.5_hold30m_long_time | opening_range_breakout | 1 | us_rth | 30 | long | time | 2310 | 1738.2500 | 1.0416 | 0.5229 | 3115.0000 |
| trend_ema_pullback_3m_us_late_lb55_ema21_55_thr0_hold15m_long_time | ema_pullback | 3 | us_late | 15 | long | time | 1396 | -744.2500 | 0.9218 | 0.4850 | 1459.0000 |
| trend_opening_range_breakout_3m_us_rth_lb15_thr0.25_hold15m_long_time | opening_range_breakout | 3 | us_rth | 15 | long | time | 2495 | -122.6250 | 0.9961 | 0.5102 | 3097.6250 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr22_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 9304 | 2007.5000 | 1.0126 | 0.4868 | 3938.7500 |
| trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.5_hold30m_both_time | donchian_atr_breakout | 3 | us_rth | 30 | both | time | 4544 | -2.5000 | 1.0000 | 0.4941 | 2767.5000 |
| trend_opening_range_breakout_1m_us_rth_lb15_thr0.25_hold15m_long_time | opening_range_breakout | 1 | us_rth | 15 | long | time | 3024 | -1130.0000 | 0.9717 | 0.5060 | 4062.2500 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold30m_both_time | vwap_trend_pullback | 1 | us_rth | 30 | both | time | 1690 | 3469.0000 | 1.1111 | 0.4959 | 1055.8750 |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr22_hold30m_short_time | adx_di_trend | 1 | us_rth | 30 | short | time | 8326 | -6163.2500 | 0.9590 | 0.4696 | 8428.6250 |
| trend_opening_range_breakout_1m_us_rth_lb30_thr0.5_hold15m_long_time | opening_range_breakout | 1 | us_rth | 15 | long | time | 2741 | 898.8750 | 1.0265 | 0.5137 | 2510.2500 |
| trend_donchian_atr_breakout_1m_us_rth_lb20_thr0.5_hold15m_short_time | donchian_atr_breakout | 1 | us_rth | 15 | short | time | 6185 | -3041.8750 | 0.9637 | 0.4677 | 3962.3750 |
| trend_opening_range_breakout_3m_us_rth_lb30_thr0.25_hold30m_long_time | opening_range_breakout | 3 | us_rth | 30 | long | time | 1905 | 173.6250 | 1.0050 | 0.5218 | 2237.0000 |

## Top Future Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | trend_adx_di_trend_1m_us_late_lb14_adx14_thr26_hold30m_both_time | 11 | 9 | 539 | 846.6250 | 1.1963 | 134 | 2207.2500 | 2.0729 | 0.4925 |
| True | trend_opening_range_breakout_1m_us_rth_lb15_thr0.5_hold30m_both_time | 14 | 11 | 843 | 3336.3750 | 1.2010 | 214 | 1692.0000 | 1.3745 | 0.5187 |
| True | trend_ema_pullback_1m_us_rth_lb21_ema9_21_thr0_hold30m_both_time | 10 | 3 | 2959 | 2452.8750 | 1.0577 | 708 | 1596.2500 | 1.1428 | 0.5254 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold30m_both_time | 15 | 18 | 1336 | 4035.0000 | 1.1484 | 310 | 1319.0000 | 1.1795 | 0.5097 |
| True | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold15m_both_time | 12 | 17 | 2860 | 2350.0000 | 1.0643 | 669 | 1199.6250 | 1.1326 | 0.5127 |
| True | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold30m_short_time | 1 | 20 | 1205 | 868.6250 | 1.0406 | 291 | 1187.8750 | 1.2614 | 0.5017 |
| True | trend_ema_pullback_1m_us_rth_lb21_ema9_21_thr0_hold30m_long_time | 8 | 8 | 2106 | 1288.2500 | 1.0524 | 508 | 1116.0000 | 1.1800 | 0.5413 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.5_hold30m_short_time | 10 | 12 | 427 | 984.1250 | 1.1386 | 107 | 1029.3750 | 1.5055 | 0.4953 |
| True | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold15m_both_time | 11 | 7 | 2918 | 2384.5000 | 1.0737 | 701 | 1028.8750 | 1.0762 | 0.4836 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold30m_short_time | 1 | 9 | 172 | 1212.2500 | 1.3638 | 42 | 880.0000 | 3.0300 | 0.6190 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.25_hold30m_both_time | 9 | 18 | 413 | 648.8750 | 1.1223 | 95 | 859.6250 | 1.4457 | 0.5368 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.5_hold15m_short_time | 10 | 17 | 478 | 977.0000 | 1.1635 | 123 | 788.1250 | 1.4870 | 0.4797 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb50_thr0.5_hold15m_short_time | 10 | 14 | 319 | 867.6250 | 1.2218 | 78 | 691.5000 | 1.6175 | 0.4744 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold30m_both_time | 9 | 6 | 362 | 986.5000 | 1.2247 | 87 | 690.6250 | 1.3744 | 0.5517 |
| True | trend_ema_pullback_1m_us_rth_lb55_ema21_55_thr0_hold30m_short_time | 11 | 20 | 1248 | 2015.5000 | 1.1019 | 334 | 614.0000 | 1.0703 | 0.4850 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold30m_both_time | 13 | 1 | 1371 | 6121.1250 | 1.2242 | 336 | 546.0000 | 1.1064 | 0.4970 |
| True | trend_ema_pullback_1m_us_rth_lb21_ema9_21_thr0_hold15m_long_time | 6 | 3 | 3110 | 1593.2500 | 1.0572 | 804 | 511.5000 | 1.0858 | 0.5299 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.25_hold30m_both_time | 8 | 20 | 411 | 533.6250 | 1.1024 | 94 | 496.0000 | 1.4850 | 0.5319 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold15m_short_time | 10 | 10 | 708 | 976.7500 | 1.1129 | 178 | 493.5000 | 1.1917 | 0.4438 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.25_hold30m_long_time | 8 | 14 | 207 | 684.6250 | 1.2817 | 45 | 481.3750 | 2.2815 | 0.6667 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold15m_short_time | 11 | 11 | 704 | 1275.2500 | 1.1394 | 183 | 458.3750 | 1.1116 | 0.4863 |
| True | trend_ema_pullback_1m_us_rth_lb21_ema9_21_thr0.25_hold30m_both_time | 10 | 1 | 3091 | 4019.8750 | 1.0928 | 739 | 431.3750 | 1.0350 | 0.5034 |
| True | trend_opening_range_breakout_1m_us_rth_lb15_thr0.5_hold30m_long_time | 14 | 7 | 451 | 3137.8750 | 1.3987 | 115 | 429.3750 | 1.1589 | 0.5304 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold30m_both_time | 8 | 4 | 358 | 952.5000 | 1.2308 | 84 | 403.0000 | 1.4115 | 0.5238 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.25_hold15m_both_time | 8 | 13 | 418 | 509.0000 | 1.1284 | 97 | 399.3750 | 1.4890 | 0.4639 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.25_hold30m_long_time | 9 | 12 | 201 | 695.6250 | 1.2836 | 47 | 388.3750 | 1.3842 | 0.5319 |
| True | trend_adx_di_trend_1m_us_late_lb14_adx14_thr22_hold30m_both_time | 13 | 19 | 713 | 2507.3750 | 1.2889 | 175 | 387.1250 | 1.3191 | 0.4400 |
| True | trend_adx_di_trend_1m_us_late_lb14_adx14_thr26_hold30m_both_time | 8 | 18 | 543 | 376.6250 | 1.1268 | 131 | 376.6250 | 1.6848 | 0.5420 |
| True | trend_ema_pullback_1m_us_late_lb21_ema9_21_thr0.25_hold30m_short_time | 1 | 8 | 627 | 1031.8750 | 1.1676 | 155 | 372.6250 | 1.4883 | 0.4645 |
| True | trend_ema_pullback_3m_us_late_lb55_ema21_55_thr0.25_hold15m_short_time | 15 | 17 | 308 | 1494.0000 | 1.5779 | 122 | 368.7500 | 1.2982 | 0.5410 |
