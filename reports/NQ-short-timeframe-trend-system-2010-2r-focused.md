# NQ Short-Timeframe Trend System Search

## Candidate Sources

Industry-standard trend archetypes translated into mechanical rules: opening range breakout, Donchian/channel breakout, VWAP trend pullback, EMA trend/pullback, and ADX/DI trend following.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Base 1m span: `2010-06-06 22:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Base rows: `5,383,225`.
- Costs: `0.625` NQ points round trip.

## Walk-Forward

- Timeframes: `1m, 3m`.
- Train/test: `365` train days, `5` purge days, `90` test days, `90` step days.
- Sessions: `us_rth`.
- Direction filters: `both, long, short`.
- Exit profiles: `sl8_tp16, sl12_tp24, sl16_tp32, sl20_tp40, sl24_tp48`.
- Stable gate: selected folds >= 3, positive fold rate >= 67%, aggregate net > 0, avg PF >= 1.1, net/drawdown >= 1, and no negative selected OOS fold.

## Verdict

Best stable candidate: `trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold60m_both_sl24_tp48` with `1080.38` OOS net points, `100.00%` positive selected folds, `1.101` avg OOS PF, and `765` OOS trades.
Best positive research candidate: `trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold60m_both_sl24_tp48` (1080.38 OOS points, stable=True).

## Top Aggregate Rows

| stable_candidate | candidate | family | timeframe_minutes | session | holding_minutes | direction_filter | exit_profile | selected_folds | positive_test_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold60m_both_sl24_tp48 | adx_di_trend | 1 | us_rth | 60 | both | sl24_tp48 | 4 | 1.0000 | 765 | 1080.3750 | 522.0000 | 2.0697 | 1.1014 | 126.1250 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold90m_both_sl20_tp40 | adx_di_trend | 1 | us_rth | 90 | both | sl20_tp40 | 4 | 1.0000 | 514 | 974.2500 | 425.0000 | 2.2924 | 1.1943 | 26.5000 |
| True | trend_vwap_trend_pullback_3m_us_rth_lb30_thr0_hold60m_both_sl24_tp48 | vwap_trend_pullback | 3 | us_rth | 60 | both | sl24_tp48 | 3 | 1.0000 | 204 | 630.5000 | 216.5000 | 2.9122 | 1.2954 | 112.6250 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold90m_long_sl20_tp40 | adx_di_trend | 3 | us_rth | 90 | long | sl20_tp40 | 3 | 1.0000 | 80 | 307.7500 | 67.2500 | 4.5762 | 2.5778 | 60.7500 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold90m_long_sl12_tp24 | adx_di_trend | 3 | us_rth | 90 | long | sl12_tp24 | 4 | 1.0000 | 125 | 295.3750 | 75.7500 | 3.8993 | 1.6830 | 50.2500 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold90m_both_sl16_tp32 | vwap_trend_pullback | 1 | us_rth | 90 | both | sl16_tp32 | 3 | 1.0000 | 211 | 243.8750 | 94.3750 | 2.5841 | 1.3376 | 31.3750 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold90m_both_sl24_tp48 | adx_di_trend | 1 | us_rth | 90 | both | sl24_tp48 | 6 | 0.8333 | 959 | 952.1250 | 568.7500 | 1.6741 | 1.0684 | -132.5000 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold60m_both_sl20_tp40 | adx_di_trend | 1 | us_rth | 60 | both | sl20_tp40 | 6 | 0.8333 | 737 | 934.1250 | 430.2500 | 2.1711 | 1.1137 | -206.0000 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold60m_long_sl24_tp48 | adx_di_trend | 1 | us_rth | 60 | long | sl24_tp48 | 9 | 0.7778 | 363 | 861.1250 | 358.7500 | 2.4003 | 1.3030 | -323.7500 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold60m_both_sl24_tp48 | adx_di_trend | 1 | us_rth | 60 | both | sl24_tp48 | 7 | 0.7143 | 1173 | 703.3750 | 627.2500 | 1.1214 | 1.0048 | -217.3750 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold90m_long_sl20_tp40 | adx_di_trend | 1 | us_rth | 90 | long | sl20_tp40 | 11 | 0.8182 | 483 | 624.3750 | 320.3750 | 1.9489 | 1.1850 | -324.0000 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold90m_both_sl20_tp40 | adx_di_trend | 1 | us_rth | 90 | both | sl20_tp40 | 5 | 0.8000 | 1078 | 559.0000 | 498.1250 | 1.1222 | 1.0485 | -26.6250 |
| False | trend_vwap_trend_pullback_3m_us_rth_lb20_thr0_hold60m_both_sl24_tp48 | vwap_trend_pullback | 3 | us_rth | 60 | both | sl24_tp48 | 5 | 0.8000 | 433 | 542.6250 | 290.6250 | 1.8671 | 1.1083 | -5.3750 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold60m_short_sl24_tp48 | adx_di_trend | 1 | us_rth | 60 | short | sl24_tp48 | 4 | 0.7500 | 336 | 530.2500 | 382.8750 | 1.3849 | 1.1216 | -22.7500 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold90m_both_sl24_tp48 | adx_di_trend | 1 | us_rth | 90 | both | sl24_tp48 | 4 | 0.7500 | 682 | 521.5000 | 672.2500 | 0.7758 | 1.0490 | -268.1250 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold60m_short_sl24_tp48 | adx_di_trend | 1 | us_rth | 60 | short | sl24_tp48 | 7 | 0.7143 | 633 | 508.1250 | 312.3750 | 1.6267 | 1.0731 | -233.2500 |
| False | trend_vwap_trend_pullback_3m_us_rth_lb20_thr0.25_hold60m_both_sl24_tp48 | vwap_trend_pullback | 3 | us_rth | 60 | both | sl24_tp48 | 2 | 1.0000 | 191 | 502.8750 | 264.0000 | 1.9048 | 1.2183 | 60.0000 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb20_thr0.25_hold60m_both_sl24_tp48 | vwap_trend_pullback | 1 | us_rth | 60 | both | sl24_tp48 | 6 | 0.6667 | 821 | 475.3750 | 334.6250 | 1.4206 | 1.1176 | -183.3750 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold60m_both_sl20_tp40 | adx_di_trend | 1 | us_rth | 60 | both | sl20_tp40 | 5 | 0.8000 | 1088 | 463.0000 | 549.6250 | 0.8424 | 1.0427 | -30.5000 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold90m_short_sl24_tp48 | adx_di_trend | 1 | us_rth | 90 | short | sl24_tp48 | 2 | 0.5000 | 200 | 451.5000 | 363.7500 | 1.2412 | 1.1567 | -47.1250 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold90m_short_sl20_tp40 | adx_di_trend | 1 | us_rth | 90 | short | sl20_tp40 | 3 | 0.6667 | 463 | 439.6250 | 320.6250 | 1.3712 | 1.0599 | -179.6250 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr32_hold90m_both_sl24_tp48 | adx_di_trend | 1 | us_rth | 90 | both | sl24_tp48 | 6 | 0.6667 | 482 | 430.7500 | 714.8750 | 0.6026 | 1.0840 | -679.7500 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb20_thr0.25_hold90m_short_sl24_tp48 | vwap_trend_pullback | 1 | us_rth | 90 | short | sl24_tp48 | 1 | 1.0000 | 76 | 430.2500 | 126.8750 | 3.3911 | 1.4130 | 430.2500 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold90m_long_sl16_tp32 | adx_di_trend | 3 | us_rth | 90 | long | sl16_tp32 | 5 | 0.8000 | 128 | 428.2500 | 75.8750 | 5.6442 | 2.4207 | -20.5000 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold90m_short_sl20_tp40 | adx_di_trend | 1 | us_rth | 90 | short | sl20_tp40 | 1 | 1.0000 | 125 | 424.8750 | 194.6250 | 2.1830 | 1.2875 | 424.8750 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold60m_short_sl20_tp40 | adx_di_trend | 1 | us_rth | 60 | short | sl20_tp40 | 4 | 0.7500 | 539 | 418.6250 | 335.2500 | 1.2487 | 1.0937 | -218.5000 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr22_hold60m_both_sl20_tp40 | adx_di_trend | 1 | us_rth | 60 | both | sl20_tp40 | 1 | 1.0000 | 280 | 414.5000 | 334.8750 | 1.2378 | 1.1315 | 414.5000 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold90m_short_sl24_tp48 | adx_di_trend | 1 | us_rth | 90 | short | sl24_tp48 | 8 | 0.5000 | 695 | 374.1250 | 402.7500 | 0.9289 | 1.0185 | -211.6250 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold60m_long_sl8_tp16 | adx_di_trend | 3 | us_rth | 60 | long | sl8_tp16 | 5 | 0.8000 | 198 | 353.2500 | 86.6250 | 4.0779 | 2.1491 | -30.3750 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold60m_long_sl16_tp32 | adx_di_trend | 3 | us_rth | 60 | long | sl16_tp32 | 5 | 0.6000 | 170 | 340.0000 | 71.0000 | 4.7887 | 2.3836 | -21.0000 |

## Full-Sample Check

| candidate | family | timeframe_minutes | session | holding_minutes | direction_filter | exit_profile | trades | net_points | profit_factor | win_rate | max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold60m_both_sl24_tp48 | adx_di_trend | 1 | us_rth | 60 | both | sl24_tp48 | 10334 | 3307.7500 | 1.0297 | 0.4126 | 1748.7500 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold90m_both_sl20_tp40 | adx_di_trend | 1 | us_rth | 90 | both | sl20_tp40 | 6563 | 3149.1250 | 1.0454 | 0.3960 | 1223.8750 |
| trend_vwap_trend_pullback_3m_us_rth_lb30_thr0_hold60m_both_sl24_tp48 | vwap_trend_pullback | 3 | us_rth | 60 | both | sl24_tp48 | 3906 | -45.2500 | 0.9987 | 0.4350 | 2428.1250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold90m_long_sl20_tp40 | adx_di_trend | 3 | us_rth | 90 | long | sl20_tp40 | 2111 | 1409.3750 | 1.0775 | 0.4481 | 901.1250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold90m_long_sl12_tp24 | adx_di_trend | 3 | us_rth | 90 | long | sl12_tp24 | 3651 | -249.1250 | 0.9899 | 0.3993 | 1811.8750 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold90m_both_sl16_tp32 | vwap_trend_pullback | 1 | us_rth | 90 | both | sl16_tp32 | 5206 | -992.0000 | 0.9762 | 0.4038 | 2146.5000 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold90m_both_sl24_tp48 | adx_di_trend | 1 | us_rth | 90 | both | sl24_tp48 | 9620 | 4143.7500 | 1.0365 | 0.4028 | 1629.1250 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold60m_both_sl20_tp40 | adx_di_trend | 1 | us_rth | 60 | both | sl20_tp40 | 6847 | 2953.3750 | 1.0438 | 0.4032 | 1165.1250 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold60m_long_sl24_tp48 | adx_di_trend | 1 | us_rth | 60 | long | sl24_tp48 | 2545 | 1303.6250 | 1.0580 | 0.4530 | 1310.2500 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold60m_both_sl24_tp48 | adx_di_trend | 1 | us_rth | 60 | both | sl24_tp48 | 8009 | 3807.3750 | 1.0437 | 0.4155 | 1769.2500 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold90m_long_sl20_tp40 | adx_di_trend | 1 | us_rth | 90 | long | sl20_tp40 | 2634 | 1775.7500 | 1.0736 | 0.4336 | 1255.8750 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold90m_both_sl20_tp40 | adx_di_trend | 1 | us_rth | 90 | both | sl20_tp40 | 11088 | 4941.7500 | 1.0420 | 0.3946 | 1172.5000 |
| trend_vwap_trend_pullback_3m_us_rth_lb20_thr0_hold60m_both_sl24_tp48 | vwap_trend_pullback | 3 | us_rth | 60 | both | sl24_tp48 | 5441 | 144.6250 | 1.0029 | 0.4378 | 2220.3750 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold60m_short_sl24_tp48 | adx_di_trend | 1 | us_rth | 60 | short | sl24_tp48 | 5025 | 2511.3750 | 1.0428 | 0.3926 | 1312.0000 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold90m_both_sl24_tp48 | adx_di_trend | 1 | us_rth | 90 | both | sl24_tp48 | 7546 | 3884.2500 | 1.0435 | 0.4049 | 1622.6250 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold60m_short_sl24_tp48 | adx_di_trend | 1 | us_rth | 60 | short | sl24_tp48 | 6480 | 2008.5000 | 1.0269 | 0.3931 | 1350.0000 |
| trend_vwap_trend_pullback_3m_us_rth_lb20_thr0.25_hold60m_both_sl24_tp48 | vwap_trend_pullback | 3 | us_rth | 60 | both | sl24_tp48 | 6272 | -83.0000 | 0.9986 | 0.4345 | 2698.8750 |
| trend_vwap_trend_pullback_1m_us_rth_lb20_thr0.25_hold60m_both_sl24_tp48 | vwap_trend_pullback | 1 | us_rth | 60 | both | sl24_tp48 | 8788 | 713.5000 | 1.0085 | 0.4260 | 2872.1250 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold60m_both_sl20_tp40 | adx_di_trend | 1 | us_rth | 60 | both | sl20_tp40 | 11739 | 3301.1250 | 1.0284 | 0.4024 | 1585.2500 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold90m_short_sl24_tp48 | adx_di_trend | 1 | us_rth | 90 | short | sl24_tp48 | 4817 | 2356.3750 | 1.0390 | 0.3820 | 1236.6250 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold90m_short_sl20_tp40 | adx_di_trend | 1 | us_rth | 90 | short | sl20_tp40 | 7036 | 1516.5000 | 1.0195 | 0.3768 | 1441.5000 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr32_hold90m_both_sl24_tp48 | adx_di_trend | 1 | us_rth | 90 | both | sl24_tp48 | 4321 | 2851.6250 | 1.0571 | 0.4082 | 1311.0000 |
| trend_vwap_trend_pullback_1m_us_rth_lb20_thr0.25_hold90m_short_sl24_tp48 | vwap_trend_pullback | 1 | us_rth | 90 | short | sl24_tp48 | 5013 | 1267.6250 | 1.0250 | 0.4143 | 2300.6250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold90m_long_sl16_tp32 | adx_di_trend | 3 | us_rth | 90 | long | sl16_tp32 | 2354 | 544.5000 | 1.0295 | 0.4248 | 1072.3750 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold90m_short_sl20_tp40 | adx_di_trend | 1 | us_rth | 90 | short | sl20_tp40 | 5509 | 1402.6250 | 1.0228 | 0.3741 | 1080.3750 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold60m_short_sl20_tp40 | adx_di_trend | 1 | us_rth | 60 | short | sl20_tp40 | 7338 | 1329.5000 | 1.0173 | 0.3839 | 1424.3750 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr22_hold60m_both_sl20_tp40 | adx_di_trend | 1 | us_rth | 60 | both | sl20_tp40 | 19125 | 1284.3750 | 1.0066 | 0.3944 | 2371.6250 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold90m_short_sl24_tp48 | adx_di_trend | 1 | us_rth | 90 | short | sl24_tp48 | 6152 | 1917.0000 | 1.0252 | 0.3828 | 1476.7500 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold60m_long_sl8_tp16 | adx_di_trend | 3 | us_rth | 60 | long | sl8_tp16 | 3599 | -899.3750 | 0.9471 | 0.3898 | 1661.2500 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold60m_long_sl16_tp32 | adx_di_trend | 3 | us_rth | 60 | long | sl16_tp32 | 2640 | 129.7500 | 1.0069 | 0.4250 | 1077.2500 |

## Top Future Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr32_hold90m_both_sl24_tp48 | 52 | 10 | 319 | 979.3750 | 1.2194 | 104 | 670.5000 | 1.4968 | 0.4423 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr32_hold60m_both_sl24_tp48 | 52 | 1 | 323 | 1109.8750 | 1.2580 | 106 | 662.0000 | 1.4823 | 0.4528 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb60_thr0.5_hold90m_both_sl24_tp48 | 53 | 17 | 400 | 1025.5000 | 1.1841 | 105 | 652.3750 | 1.4587 | 0.4381 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold60m_long_sl24_tp48 | 37 | 8 | 122 | 459.2500 | 1.4983 | 47 | 519.3750 | 2.0789 | 0.5532 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr22_hold90m_both_sl20_tp40 | 40 | 6 | 1591 | 2736.1250 | 1.1371 | 271 | 512.1250 | 1.1625 | 0.4133 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr22_hold90m_short_sl24_tp48 | 46 | 6 | 849 | 672.1250 | 1.0504 | 235 | 511.8750 | 1.1457 | 0.3830 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold90m_short_sl24_tp48 | 49 | 7 | 386 | 861.2500 | 1.1484 | 107 | 498.6250 | 1.3458 | 0.4206 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold60m_short_sl24_tp48 | 49 | 3 | 390 | 921.5000 | 1.1605 | 107 | 473.3750 | 1.3279 | 0.4206 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr22_hold90m_both_sl24_tp48 | 40 | 8 | 1282 | 2635.0000 | 1.1411 | 229 | 471.1250 | 1.1571 | 0.4279 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold90m_both_sl20_tp40 | 40 | 1 | 617 | 1854.6250 | 1.2477 | 102 | 452.2500 | 1.3952 | 0.4412 |
| True | trend_vwap_trend_pullback_3m_us_rth_lb20_thr0.25_hold60m_both_sl24_tp48 | 36 | 1 | 372 | 1013.7500 | 1.3254 | 89 | 442.8750 | 1.3930 | 0.4719 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr22_hold60m_short_sl24_tp48 | 46 | 9 | 860 | 664.5000 | 1.0501 | 249 | 438.6250 | 1.1223 | 0.3976 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold60m_short_sl20_tp40 | 56 | 10 | 765 | 1782.8750 | 1.1871 | 171 | 434.1250 | 1.2024 | 0.3918 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr32_hold90m_both_sl20_tp40 | 52 | 8 | 393 | 927.8750 | 1.1918 | 126 | 430.5000 | 1.2915 | 0.4127 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb20_thr0.25_hold90m_short_sl24_tp48 | 59 | 14 | 330 | 917.5000 | 1.1847 | 76 | 430.2500 | 1.4130 | 0.4342 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold90m_short_sl20_tp40 | 56 | 12 | 753 | 1894.1250 | 1.2009 | 167 | 425.6250 | 1.2023 | 0.3892 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold90m_short_sl20_tp40 | 49 | 19 | 468 | 522.7500 | 1.0859 | 125 | 424.8750 | 1.2875 | 0.4000 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold90m_both_sl24_tp48 | 46 | 16 | 825 | 706.1250 | 1.0552 | 217 | 420.1250 | 1.1263 | 0.3733 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr22_hold60m_both_sl20_tp40 | 40 | 12 | 1628 | 2578.5000 | 1.1301 | 280 | 414.5000 | 1.1315 | 0.4071 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold60m_both_sl24_tp48 | 46 | 10 | 833 | 723.1250 | 1.0570 | 218 | 411.7500 | 1.1251 | 0.3807 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr32_hold60m_both_sl20_tp40 | 52 | 9 | 394 | 934.2500 | 1.1976 | 127 | 411.6250 | 1.2745 | 0.4173 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold90m_short_sl24_tp48 | 49 | 2 | 481 | 1200.6250 | 1.1685 | 141 | 410.8750 | 1.2071 | 0.4043 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold60m_both_sl20_tp40 | 40 | 2 | 622 | 1721.0000 | 1.2320 | 104 | 393.0000 | 1.3593 | 0.4327 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold90m_both_sl12_tp24 | 42 | 5 | 860 | 1367.2500 | 1.2094 | 305 | 389.3750 | 1.1649 | 0.3869 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr32_hold90m_both_sl20_tp40 | 38 | 13 | 345 | 768.6250 | 1.1910 | 116 | 377.2500 | 1.2651 | 0.4052 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr32_hold90m_both_sl24_tp48 | 38 | 14 | 261 | 881.6250 | 1.2615 | 54 | 376.2500 | 1.5541 | 0.4444 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold90m_both_sl20_tp40 | 41 | 1 | 599 | 1838.8750 | 1.2539 | 112 | 375.5000 | 1.2912 | 0.4018 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold90m_short_sl24_tp48 | 56 | 5 | 649 | 2665.1250 | 1.2833 | 146 | 374.2500 | 1.1689 | 0.3836 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb20_thr0.5_hold60m_both_sl16_tp32 | 29 | 3 | 588 | 819.0000 | 1.2361 | 162 | 368.7500 | 1.3092 | 0.4815 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold60m_both_sl24_tp48 | 48 | 5 | 997 | 1770.8750 | 1.1191 | 186 | 368.0000 | 1.1495 | 0.4301 |
