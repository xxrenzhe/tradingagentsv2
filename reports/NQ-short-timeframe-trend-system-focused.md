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
- Sessions: `us_rth`.
- Direction filters: `long, short, both`.
- Exit profiles: `time, sl8_tp12, sl12_tp24`.
- Stable gate: selected folds >= 3, positive fold rate >= 67%, aggregate net > 0, avg PF >= 1.1, net/drawdown >= 1, and no negative selected OOS fold.

## Verdict

Best stable candidate: `trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold15m_long_sl12_tp24` with `359.88` OOS net points, `100.00%` positive selected folds, `1.308` avg OOS PF, and `185` OOS trades.
Best positive research candidate: `trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold15m_long_sl12_tp24` (359.88 OOS points, stable=True).

## Top Aggregate Rows

| stable_candidate | candidate | family | timeframe_minutes | session | holding_minutes | direction_filter | exit_profile | selected_folds | positive_test_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold15m_long_sl12_tp24 | vwap_trend_pullback | 1 | us_rth | 15 | long | sl12_tp24 | 5 | 1.0000 | 185 | 359.8750 | 131.8750 | 2.7289 | 1.3085 | 13.5000 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold30m_long_sl12_tp24 | vwap_trend_pullback | 1 | us_rth | 30 | long | sl12_tp24 | 4 | 1.0000 | 146 | 236.2500 | 144.5000 | 1.6349 | 1.2206 | 5.5000 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr24_hold30m_both_time | adx_di_trend | 1 | us_rth | 30 | both | time | 8 | 0.8750 | 1619 | 3448.1250 | 899.6250 | 3.8328 | 1.1564 | -129.3750 |
| False | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold15m_both_time | adx_di_trend | 1 | us_rth | 15 | both | time | 4 | 1.0000 | 2658 | 2556.2500 | 1375.6250 | 1.8582 | 1.0606 | 25.7500 |
| False | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr28_hold15m_both_time | adx_di_trend | 1 | us_rth | 15 | both | time | 4 | 0.5000 | 2178 | 2423.7500 | 1687.8750 | 1.4360 | 1.0588 | -444.7500 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 9 | 0.6667 | 1089 | 2386.8750 | 813.0000 | 2.9359 | 1.1199 | -473.5000 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold30m_short_time | adx_di_trend | 3 | us_rth | 30 | short | time | 7 | 0.5714 | 552 | 2129.0000 | 586.5000 | 3.6300 | 1.2262 | -241.8750 |
| False | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr24_hold30m_long_time | adx_di_trend | 3 | us_rth | 30 | long | time | 4 | 0.7500 | 833 | 1564.8750 | 2175.0000 | 0.7195 | 1.1093 | -2111.1250 |
| False | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 3 | 0.6667 | 970 | 1423.7500 | 1673.5000 | 0.8508 | 1.0757 | -441.2500 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold15m_short_time | adx_di_trend | 3 | us_rth | 15 | short | time | 8 | 0.6250 | 1617 | 1318.8750 | 949.6250 | 1.3888 | 1.0559 | -355.0000 |
| False | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold30m_long_time | adx_di_trend | 1 | us_rth | 30 | long | time | 3 | 0.6667 | 807 | 1239.8750 | 1143.2500 | 1.0845 | 1.1336 | -372.7500 |
| False | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr28_hold30m_both_time | adx_di_trend | 1 | us_rth | 30 | both | time | 5 | 1.0000 | 1974 | 1230.7500 | 1302.6250 | 0.9448 | 1.0408 | 96.8750 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold30m_long_time | adx_di_trend | 3 | us_rth | 30 | long | time | 2 | 1.0000 | 121 | 1005.6250 | 1024.2500 | 0.9818 | 1.8330 | 12.1250 |
| False | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr28_hold15m_long_time | adx_di_trend | 1 | us_rth | 15 | long | time | 3 | 0.6667 | 922 | 704.0000 | 1304.7500 | 0.5396 | 1.0714 | -69.6250 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold15m_both_time | adx_di_trend | 1 | us_rth | 15 | both | time | 3 | 0.6667 | 593 | 630.8750 | 507.0000 | 1.2443 | 1.1230 | -74.7500 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold30m_both_time | adx_di_trend | 1 | us_rth | 30 | both | time | 3 | 0.6667 | 486 | 563.7500 | 739.0000 | 0.7629 | 1.0929 | -117.1250 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold15m_both_time | adx_di_trend | 1 | us_rth | 15 | both | time | 4 | 0.5000 | 1045 | 470.6250 | 674.6250 | 0.6976 | 1.0478 | -174.5000 |
| False | trend_donchian_atr_breakout_3m_us_rth_lb60_thr0.25_hold30m_long_time | donchian_atr_breakout | 3 | us_rth | 30 | long | time | 2 | 1.0000 | 201 | 462.3750 | 796.7500 | 0.5803 | 1.1200 | 36.6250 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold30m_long_time | adx_di_trend | 1 | us_rth | 30 | long | time | 3 | 0.6667 | 165 | 278.3750 | 285.3750 | 0.9755 | 1.1314 | -111.3750 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb60_thr0.25_hold30m_long_time | vwap_trend_pullback | 1 | us_rth | 30 | long | time | 1 | 1.0000 | 41 | 238.1250 | 177.6250 | 1.3406 | 1.7071 | 238.1250 |
| False | trend_donchian_atr_breakout_3m_us_rth_lb50_thr0.25_hold30m_long_time | donchian_atr_breakout | 3 | us_rth | 30 | long | time | 2 | 0.5000 | 213 | 224.6250 | 1020.3750 | 0.2201 | 1.0569 | -132.3750 |
| False | trend_donchian_atr_breakout_3m_us_rth_lb30_thr0.25_hold30m_both_time | donchian_atr_breakout | 3 | us_rth | 30 | both | time | 1 | 1.0000 | 287 | 202.6250 | 342.0000 | 0.5925 | 1.0624 | 202.6250 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold30m_short_time | adx_di_trend | 3 | us_rth | 30 | short | time | 7 | 0.4286 | 834 | 163.5000 | 670.2500 | 0.2439 | 1.0039 | -458.8750 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold15m_short_time | vwap_trend_pullback | 1 | us_rth | 15 | short | time | 3 | 0.3333 | 126 | 163.5000 | 272.6250 | 0.5997 | 1.1559 | -31.5000 |
| False | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr28_hold30m_short_time | adx_di_trend | 1 | us_rth | 30 | short | time | 3 | 0.3333 | 745 | 161.3750 | 1001.5000 | 0.1611 | 1.0119 | -809.6250 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold30m_long_sl12_tp24 | vwap_trend_pullback | 1 | us_rth | 30 | long | sl12_tp24 | 2 | 1.0000 | 88 | 142.5000 | 130.0000 | 1.0962 | 1.2138 | 51.8750 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold30m_long_time | vwap_trend_pullback | 1 | us_rth | 30 | long | time | 1 | 1.0000 | 34 | 136.2500 | 106.8750 | 1.2749 | 1.5122 | 136.2500 |
| False | trend_vwap_trend_pullback_3m_us_rth_lb50_thr0.25_hold30m_both_time | vwap_trend_pullback | 3 | us_rth | 30 | both | time | 1 | 1.0000 | 47 | 128.6250 | 271.8750 | 0.4731 | 1.1420 | 128.6250 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold30m_short_time | vwap_trend_pullback | 1 | us_rth | 30 | short | time | 4 | 0.5000 | 161 | 110.3750 | 627.1250 | 0.1760 | 1.3223 | -449.8750 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold30m_long_time | adx_di_trend | 1 | us_rth | 30 | long | time | 1 | 1.0000 | 82 | 109.0000 | 388.7500 | 0.2804 | 1.1106 | 109.0000 |

## Full-Sample Check

| candidate | family | timeframe_minutes | session | holding_minutes | direction_filter | exit_profile | trades | net_points | profit_factor | win_rate | max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold15m_long_sl12_tp24 | vwap_trend_pullback | 1 | us_rth | 15 | long | sl12_tp24 | 771 | -404.6250 | 0.9308 | 0.3619 | 604.1250 |
| trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold30m_long_sl12_tp24 | vwap_trend_pullback | 1 | us_rth | 30 | long | sl12_tp24 | 770 | -592.0000 | 0.9065 | 0.3364 | 711.3750 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr24_hold30m_both_time | adx_di_trend | 1 | us_rth | 30 | both | time | 3864 | 4814.0000 | 1.0706 | 0.5041 | 3188.2500 |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold15m_both_time | adx_di_trend | 1 | us_rth | 15 | both | time | 14188 | 3600.0000 | 1.0212 | 0.4874 | 2775.5000 |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr28_hold15m_both_time | adx_di_trend | 1 | us_rth | 15 | both | time | 12159 | 5862.1250 | 1.0408 | 0.4892 | 1871.0000 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 2516 | 6696.7500 | 1.1711 | 0.5083 | 1077.7500 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold30m_short_time | adx_di_trend | 3 | us_rth | 30 | short | time | 1566 | 5466.7500 | 1.2075 | 0.4923 | 1353.3750 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr24_hold30m_long_time | adx_di_trend | 3 | us_rth | 30 | long | time | 4446 | 2074.5000 | 1.0288 | 0.5146 | 2762.6250 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 7034 | 7083.0000 | 1.0584 | 0.4982 | 2495.0000 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold15m_short_time | adx_di_trend | 3 | us_rth | 15 | short | time | 3953 | 3869.6250 | 1.0756 | 0.4882 | 1534.8750 |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold30m_long_time | adx_di_trend | 1 | us_rth | 30 | long | time | 5944 | 4716.0000 | 1.0500 | 0.5150 | 2410.1250 |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr28_hold30m_both_time | adx_di_trend | 1 | us_rth | 30 | both | time | 7900 | 3980.7500 | 1.0297 | 0.4863 | 2926.6250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold30m_long_time | adx_di_trend | 3 | us_rth | 30 | long | time | 1371 | 1905.6250 | 1.0942 | 0.5222 | 1729.2500 |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr28_hold15m_long_time | adx_di_trend | 1 | us_rth | 15 | long | time | 6890 | 2543.2500 | 1.0330 | 0.5003 | 2613.6250 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold15m_both_time | adx_di_trend | 1 | us_rth | 15 | both | time | 3630 | 96.0000 | 1.0020 | 0.4846 | 3394.8750 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold30m_both_time | adx_di_trend | 1 | us_rth | 30 | both | time | 2983 | 1914.3750 | 1.0358 | 0.4972 | 2882.0000 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold15m_both_time | adx_di_trend | 1 | us_rth | 15 | both | time | 4787 | 1759.8750 | 1.0291 | 0.4915 | 2237.1250 |
| trend_donchian_atr_breakout_3m_us_rth_lb60_thr0.25_hold30m_long_time | donchian_atr_breakout | 3 | us_rth | 30 | long | time | 2271 | 918.8750 | 1.0254 | 0.5165 | 2335.1250 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold30m_long_time | adx_di_trend | 1 | us_rth | 30 | long | time | 1099 | -272.1250 | 0.9848 | 0.5387 | 2454.6250 |
| trend_vwap_trend_pullback_1m_us_rth_lb60_thr0.25_hold30m_long_time | vwap_trend_pullback | 1 | us_rth | 30 | long | time | 803 | 320.6250 | 1.0218 | 0.5019 | 1330.7500 |
| trend_donchian_atr_breakout_3m_us_rth_lb50_thr0.25_hold30m_long_time | donchian_atr_breakout | 3 | us_rth | 30 | long | time | 2442 | 338.7500 | 1.0086 | 0.5086 | 2501.8750 |
| trend_donchian_atr_breakout_3m_us_rth_lb30_thr0.25_hold30m_both_time | donchian_atr_breakout | 3 | us_rth | 30 | both | time | 5476 | -1651.0000 | 0.9835 | 0.4936 | 3019.3750 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold30m_short_time | adx_di_trend | 3 | us_rth | 30 | short | time | 2474 | 3450.5000 | 1.0799 | 0.4867 | 1712.3750 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold15m_short_time | vwap_trend_pullback | 1 | us_rth | 15 | short | time | 895 | 994.6250 | 1.0815 | 0.4894 | 1116.1250 |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr28_hold30m_short_time | adx_di_trend | 1 | us_rth | 30 | short | time | 5224 | -2055.5000 | 0.9785 | 0.4604 | 5173.6250 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold30m_long_sl12_tp24 | vwap_trend_pullback | 1 | us_rth | 30 | long | sl12_tp24 | 893 | -739.6250 | 0.8992 | 0.3371 | 948.6250 |
| trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold30m_long_time | vwap_trend_pullback | 1 | us_rth | 30 | long | time | 714 | 282.5000 | 1.0216 | 0.5014 | 941.2500 |
| trend_vwap_trend_pullback_3m_us_rth_lb50_thr0.25_hold30m_both_time | vwap_trend_pullback | 3 | us_rth | 30 | both | time | 911 | 798.1250 | 1.0428 | 0.4929 | 1847.1250 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold30m_short_time | vwap_trend_pullback | 1 | us_rth | 30 | short | time | 879 | 3607.6250 | 1.2221 | 0.4892 | 1009.8750 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold30m_long_time | adx_di_trend | 1 | us_rth | 30 | long | time | 1488 | 266.7500 | 1.0108 | 0.5202 | 2282.1250 |

## Top Future Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr28_hold15m_both_time | 11 | 20 | 2500 | 2158.7500 | 1.0774 | 590 | 2621.5000 | 1.2695 | 0.5102 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr24_hold30m_long_time | 11 | 14 | 872 | 1505.7500 | 1.1242 | 228 | 2346.0000 | 1.4127 | 0.5219 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold30m_both_time | 15 | 14 | 1336 | 4035.0000 | 1.1484 | 310 | 1319.0000 | 1.1795 | 0.5097 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr24_hold30m_long_time | 12 | 5 | 847 | 1967.6250 | 1.1441 | 208 | 1290.2500 | 1.4141 | 0.5625 |
| True | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold30m_long_time | 13 | 17 | 1151 | 3826.3750 | 1.1781 | 282 | 1270.2500 | 1.4040 | 0.4965 |
| True | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold15m_both_time | 12 | 16 | 2860 | 2350.0000 | 1.0643 | 669 | 1199.6250 | 1.1326 | 0.5127 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold30m_short_time | 14 | 18 | 320 | 1407.7500 | 1.2438 | 77 | 1139.8750 | 1.6946 | 0.5325 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold30m_short_time | 2 | 1 | 471 | 2704.8750 | 1.3373 | 166 | 1059.2500 | 1.5276 | 0.5301 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold30m_both_time | 11 | 16 | 512 | 2107.2500 | 1.2726 | 123 | 1036.3750 | 1.3231 | 0.5447 |
| True | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold15m_both_time | 11 | 13 | 2918 | 2384.5000 | 1.0737 | 701 | 1028.8750 | 1.0762 | 0.4836 |
| True | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr28_hold30m_short_time | 1 | 20 | 1044 | 1562.0000 | 1.0844 | 251 | 1004.6250 | 1.2467 | 0.5100 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold30m_long_time | 10 | 2 | 240 | 753.0000 | 1.2640 | 62 | 993.5000 | 2.6596 | 0.5968 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold30m_both_time | 14 | 15 | 483 | 2061.3750 | 1.2249 | 108 | 985.2500 | 1.4566 | 0.5093 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr24_hold30m_both_time | 5 | 1 | 826 | 1757.7500 | 1.1421 | 211 | 969.8750 | 1.3672 | 0.5403 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold15m_short_time | 11 | 3 | 699 | 2156.1250 | 1.2718 | 174 | 895.2500 | 1.2866 | 0.5517 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold15m_short_time | 11 | 6 | 847 | 1901.8750 | 1.1913 | 206 | 887.5000 | 1.2409 | 0.5388 |
| True | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr28_hold30m_long_time | 13 | 18 | 966 | 2589.7500 | 1.1414 | 227 | 882.8750 | 1.3891 | 0.5242 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold30m_short_time | 1 | 17 | 172 | 1212.2500 | 1.3638 | 42 | 880.0000 | 3.0300 | 0.6190 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold15m_short_time | 2 | 17 | 755 | 1468.8750 | 1.1463 | 276 | 876.7500 | 1.3339 | 0.5290 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr24_hold30m_both_time | 3 | 4 | 809 | 2191.3750 | 1.1431 | 207 | 832.8750 | 1.3214 | 0.5169 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr24_hold30m_both_time | 7 | 1 | 826 | 1833.2500 | 1.1774 | 192 | 697.0000 | 1.2954 | 0.5104 |
| True | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr28_hold15m_both_time | 14 | 12 | 2329 | 3552.6250 | 1.1117 | 528 | 655.0000 | 1.0767 | 0.4924 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold30m_both_time | 5 | 20 | 646 | 1147.2500 | 1.1150 | 164 | 647.0000 | 1.3103 | 0.5244 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold30m_short_time | 2 | 13 | 379 | 1634.6250 | 1.2412 | 139 | 628.1250 | 1.3709 | 0.5180 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr28_hold30m_both_time | 13 | 4 | 1177 | 5093.3750 | 1.2124 | 281 | 625.3750 | 1.1421 | 0.4947 |
| True | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr28_hold15m_long_time | 12 | 17 | 1354 | 1682.2500 | 1.1033 | 318 | 624.0000 | 1.1728 | 0.5409 |
| True | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr28_hold30m_both_time | 1 | 8 | 1608 | 3507.2500 | 1.1323 | 398 | 585.7500 | 1.0862 | 0.5025 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold15m_both_time | 5 | 8 | 791 | 934.3750 | 1.1141 | 205 | 562.3750 | 1.3176 | 0.5171 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold30m_short_time | 15 | 6 | 319 | 1675.3750 | 1.2633 | 61 | 546.8750 | 1.3452 | 0.5246 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold30m_both_time | 13 | 1 | 1371 | 6121.1250 | 1.2242 | 336 | 546.0000 | 1.1064 | 0.4970 |
