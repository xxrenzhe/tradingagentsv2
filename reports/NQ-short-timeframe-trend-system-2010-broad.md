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
- Exit profiles: `time`.
- Stable gate: selected folds >= 3, positive fold rate >= 67%, aggregate net > 0, avg PF >= 1.1, net/drawdown >= 1, and no negative selected OOS fold.

## Verdict

Best stable candidate: `trend_donchian_breakout_3m_us_rth_lb30_thr0_hold90m_both_time` with `5732.62` OOS net points, `100.00%` positive selected folds, `1.193` avg OOS PF, and `1,415` OOS trades.
Best positive research candidate: `trend_donchian_breakout_3m_us_rth_lb30_thr0_hold90m_both_time` (5732.62 OOS points, stable=True).

## Top Aggregate Rows

| stable_candidate | candidate | family | timeframe_minutes | session | holding_minutes | direction_filter | exit_profile | selected_folds | positive_test_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | trend_donchian_breakout_3m_us_rth_lb30_thr0_hold90m_both_time | donchian_breakout | 3 | us_rth | 90 | both | time | 7 | 1.0000 | 1415 | 5732.6250 | 894.3750 | 6.4096 | 1.1929 | 317.7500 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold90m_both_time | donchian_atr_breakout | 3 | us_rth | 90 | both | time | 6 | 1.0000 | 1197 | 5570.3750 | 763.1250 | 7.2994 | 1.2085 | 369.1250 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb30_thr0_hold90m_both_time | donchian_atr_breakout | 3 | us_rth | 90 | both | time | 6 | 1.0000 | 1209 | 5414.8750 | 847.5000 | 6.3892 | 1.2158 | 450.5000 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.5_hold90m_both_time | donchian_atr_breakout | 3 | us_rth | 90 | both | time | 6 | 1.0000 | 953 | 4734.1250 | 985.1250 | 4.8056 | 1.2172 | 377.5000 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb30_thr0.25_hold90m_both_time | donchian_atr_breakout | 3 | us_rth | 90 | both | time | 4 | 1.0000 | 714 | 3050.7500 | 588.5000 | 5.1839 | 1.2098 | 130.8750 |
| True | trend_opening_range_breakout_1m_us_rth_lb30_thr0_hold90m_both_time | opening_range_breakout | 1 | us_rth | 90 | both | time | 3 | 1.0000 | 386 | 2813.7500 | 929.0000 | 3.0288 | 1.3096 | 120.7500 |
| True | trend_opening_range_breakout_1m_us_rth_lb30_thr0.25_hold60m_both_time | opening_range_breakout | 1 | us_rth | 60 | both | time | 3 | 1.0000 | 427 | 1654.6250 | 987.7500 | 1.6751 | 1.1534 | 263.7500 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr22_hold60m_long_time | adx_di_trend | 1 | us_rth | 60 | long | time | 4 | 1.0000 | 395 | 1310.1250 | 819.6250 | 1.5984 | 1.1933 | 39.8750 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr30_hold30m_long_time | adx_di_trend | 3 | us_rth | 30 | long | time | 3 | 1.0000 | 390 | 851.0000 | 657.2500 | 1.2948 | 1.1352 | 58.8750 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold60m_long_time | adx_di_trend | 3 | us_rth | 60 | long | time | 8 | 1.0000 | 293 | 646.3750 | 421.5000 | 1.5335 | 1.8703 | 13.6250 |
| True | trend_ema_pullback_3m_us_rth_lb21_ema9_21_thr0_hold90m_long_time | ema_pullback | 3 | us_rth | 90 | long | time | 5 | 1.0000 | 926 | 620.7500 | 529.7500 | 1.1718 | 1.1121 | 52.2500 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb60_thr0.5_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 11 | 0.8182 | 860 | 2929.5000 | 1411.6250 | 2.0753 | 1.2661 | -324.7500 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb30_thr0_hold60m_both_time | vwap_trend_pullback | 1 | us_rth | 60 | both | time | 6 | 0.8333 | 620 | 2884.7500 | 1076.1250 | 2.6807 | 1.1944 | -4.8750 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 16 | 0.6250 | 1189 | 2308.3750 | 1161.5000 | 1.9874 | 1.1552 | -853.6250 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb30_thr0_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 9 | 0.6667 | 758 | 2264.7500 | 1100.8750 | 2.0572 | 1.1420 | -153.6250 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb20_thr0_hold60m_both_time | vwap_trend_pullback | 1 | us_rth | 60 | both | time | 10 | 0.7000 | 1102 | 2112.0000 | 1557.5000 | 1.3560 | 1.0974 | -833.2500 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr22_hold30m_both_time | adx_di_trend | 1 | us_rth | 30 | both | time | 6 | 0.8333 | 1532 | 1976.5000 | 1156.2500 | 1.7094 | 1.0832 | -747.1250 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 15 | 0.6000 | 992 | 1803.7500 | 857.6250 | 2.1032 | 1.1514 | -358.1250 |
| False | trend_donchian_atr_breakout_1m_us_rth_lb50_thr0.5_hold90m_both_time | donchian_atr_breakout | 1 | us_rth | 90 | both | time | 5 | 0.8000 | 1016 | 1786.0000 | 1190.3750 | 1.5004 | 1.0991 | -784.1250 |
| False | trend_ema_pullback_1m_us_rth_lb34_ema13_34_thr0_hold60m_both_time | ema_pullback | 1 | us_rth | 60 | both | time | 1 | 1.0000 | 381 | 1785.8750 | 628.8750 | 2.8398 | 1.2704 | 1785.8750 |
| False | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr18_hold90m_both_time | adx_di_trend | 1 | us_rth | 90 | both | time | 4 | 0.5000 | 1114 | 1620.7500 | 1264.3750 | 1.2819 | 1.0731 | -442.5000 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.5_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 11 | 0.5455 | 940 | 1595.0000 | 1151.2500 | 1.3855 | 1.1513 | -316.3750 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold60m_both_time | vwap_trend_pullback | 1 | us_rth | 60 | both | time | 4 | 0.7500 | 284 | 1490.2500 | 995.1250 | 1.4976 | 1.1442 | -25.0000 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold60m_short_time | vwap_trend_pullback | 1 | us_rth | 60 | short | time | 6 | 0.8333 | 259 | 1454.3750 | 854.2500 | 1.7025 | 1.3939 | -50.1250 |
| False | trend_ema_trend_1m_us_rth_lb21_ema9_21_thr0_hold30m_both_time | ema_trend | 1 | us_rth | 30 | both | time | 1 | 1.0000 | 696 | 1361.0000 | 1225.8750 | 1.1102 | 1.1290 | 1361.0000 |
| False | trend_donchian_breakout_3m_us_rth_lb50_thr0_hold60m_long_time | donchian_breakout | 3 | us_rth | 60 | long | time | 2 | 1.0000 | 231 | 1283.3750 | 807.2500 | 1.5898 | 1.2848 | 7.8750 |
| False | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 3 | 1.0000 | 974 | 1267.0000 | 1418.6250 | 0.8931 | 1.0596 | 86.6250 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold90m_both_time | adx_di_trend | 1 | us_rth | 90 | both | time | 5 | 0.8000 | 450 | 1238.2500 | 522.3750 | 2.3704 | 1.1397 | -120.8750 |
| False | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.25_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 8 | 0.5000 | 653 | 1106.1250 | 1274.8750 | 0.8676 | 1.0228 | -271.3750 |
| False | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr22_hold90m_long_time | adx_di_trend | 1 | us_rth | 90 | long | time | 3 | 0.6667 | 237 | 1099.6250 | 715.8750 | 1.5361 | 1.2645 | -133.0000 |

## Full-Sample Check

| candidate | family | timeframe_minutes | session | holding_minutes | direction_filter | exit_profile | trades | net_points | profit_factor | win_rate | max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| trend_donchian_breakout_3m_us_rth_lb30_thr0_hold90m_both_time | donchian_breakout | 3 | us_rth | 90 | both | time | 12887 | 4250.8750 | 1.0221 | 0.4846 | 8062.6250 |
| trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold90m_both_time | donchian_atr_breakout | 3 | us_rth | 90 | both | time | 12769 | -971.6250 | 0.9950 | 0.4783 | 7765.3750 |
| trend_donchian_atr_breakout_3m_us_rth_lb30_thr0_hold90m_both_time | donchian_atr_breakout | 3 | us_rth | 90 | both | time | 12887 | 4250.8750 | 1.0221 | 0.4846 | 8062.6250 |
| trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.5_hold90m_both_time | donchian_atr_breakout | 3 | us_rth | 90 | both | time | 10412 | 1600.7500 | 1.0100 | 0.4806 | 6573.7500 |
| trend_donchian_atr_breakout_3m_us_rth_lb30_thr0.25_hold90m_both_time | donchian_atr_breakout | 3 | us_rth | 90 | both | time | 11493 | -4096.6250 | 0.9769 | 0.4794 | 8977.7500 |
| trend_opening_range_breakout_1m_us_rth_lb30_thr0_hold90m_both_time | opening_range_breakout | 1 | us_rth | 90 | both | time | 7931 | -6083.8750 | 0.9530 | 0.4801 | 13045.7500 |
| trend_opening_range_breakout_1m_us_rth_lb30_thr0.25_hold60m_both_time | opening_range_breakout | 1 | us_rth | 60 | both | time | 9430 | 633.7500 | 1.0051 | 0.4808 | 8933.7500 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr22_hold60m_long_time | adx_di_trend | 1 | us_rth | 60 | long | time | 6606 | 5121.2500 | 1.0719 | 0.5082 | 3327.1250 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr30_hold30m_long_time | adx_di_trend | 3 | us_rth | 30 | long | time | 8781 | -1723.1250 | 0.9753 | 0.4920 | 3251.1250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold60m_long_time | adx_di_trend | 3 | us_rth | 60 | long | time | 2474 | 2094.5000 | 1.0904 | 0.5218 | 2859.0000 |
| trend_ema_pullback_3m_us_rth_lb21_ema9_21_thr0_hold90m_long_time | ema_pullback | 3 | us_rth | 90 | long | time | 11743 | -234.8750 | 0.9986 | 0.5143 | 4196.0000 |
| trend_vwap_trend_pullback_1m_us_rth_lb60_thr0.5_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 5177 | 6808.3750 | 1.0828 | 0.4960 | 2914.8750 |
| trend_vwap_trend_pullback_1m_us_rth_lb30_thr0_hold60m_both_time | vwap_trend_pullback | 1 | us_rth | 60 | both | time | 6499 | 6172.6250 | 1.0743 | 0.4864 | 1964.8750 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 4761 | 5817.1250 | 1.0767 | 0.4976 | 2810.2500 |
| trend_vwap_trend_pullback_1m_us_rth_lb30_thr0_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 5751 | 8671.8750 | 1.0982 | 0.4909 | 2467.0000 |
| trend_vwap_trend_pullback_1m_us_rth_lb20_thr0_hold60m_both_time | vwap_trend_pullback | 1 | us_rth | 60 | both | time | 7297 | 7450.3750 | 1.0808 | 0.4858 | 2317.3750 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr22_hold30m_both_time | adx_di_trend | 1 | us_rth | 30 | both | time | 16179 | 4341.1250 | 1.0313 | 0.4681 | 5498.8750 |
| trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 4285 | 5958.3750 | 1.0869 | 0.4943 | 2549.2500 |
| trend_donchian_atr_breakout_1m_us_rth_lb50_thr0.5_hold90m_both_time | donchian_atr_breakout | 1 | us_rth | 90 | both | time | 12892 | 7193.7500 | 1.0386 | 0.4797 | 6841.7500 |
| trend_ema_pullback_1m_us_rth_lb34_ema13_34_thr0_hold60m_both_time | ema_pullback | 1 | us_rth | 60 | both | time | 24402 | -3785.7500 | 0.9870 | 0.4829 | 7481.1250 |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr18_hold90m_both_time | adx_di_trend | 1 | us_rth | 90 | both | time | 18139 | 338.1250 | 1.0013 | 0.4823 | 5594.7500 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.5_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 5600 | 6057.5000 | 1.0685 | 0.4966 | 3024.0000 |
| trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold60m_both_time | vwap_trend_pullback | 1 | us_rth | 60 | both | time | 4537 | 2891.6250 | 1.0469 | 0.4836 | 2045.6250 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold60m_short_time | vwap_trend_pullback | 1 | us_rth | 60 | short | time | 2801 | 3038.8750 | 1.0814 | 0.4748 | 1976.0000 |
| trend_ema_trend_1m_us_rth_lb21_ema9_21_thr0_hold30m_both_time | ema_trend | 1 | us_rth | 30 | both | time | 44939 | -14797.8750 | 0.9615 | 0.4716 | 16934.0000 |
| trend_donchian_breakout_3m_us_rth_lb50_thr0_hold60m_long_time | donchian_breakout | 3 | us_rth | 60 | long | time | 7516 | 3030.7500 | 1.0358 | 0.5017 | 2819.6250 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 22482 | 1345.2500 | 1.0068 | 0.4671 | 7491.5000 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr26_hold90m_both_time | adx_di_trend | 1 | us_rth | 90 | both | time | 5692 | 4003.0000 | 1.0474 | 0.4866 | 2424.8750 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.25_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 5225 | 3481.3750 | 1.0415 | 0.4965 | 3583.7500 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr22_hold90m_long_time | adx_di_trend | 1 | us_rth | 90 | long | time | 5604 | 5496.7500 | 1.0741 | 0.5186 | 2192.6250 |
| trend_ema_trend_3m_us_rth_lb21_ema9_21_thr0_hold90m_both_time | ema_trend | 3 | us_rth | 90 | both | time | 15947 | 6284.6250 | 1.0272 | 0.4948 | 4717.3750 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr32_hold30m_short_time | adx_di_trend | 3 | us_rth | 30 | short | time | 7855 | 3135.3750 | 1.0407 | 0.4508 | 3619.0000 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr24_hold60m_long_time | adx_di_trend | 1 | us_rth | 60 | long | time | 5079 | 3917.8750 | 1.0722 | 0.5133 | 2061.1250 |
| trend_ema_pullback_1m_us_rth_lb55_ema21_55_thr0.25_hold60m_both_time | ema_pullback | 1 | us_rth | 60 | both | time | 23871 | -2919.1250 | 0.9897 | 0.4877 | 6147.6250 |
| trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold90m_short_time | vwap_trend_pullback | 1 | us_rth | 90 | short | time | 2418 | 4098.7500 | 1.1041 | 0.4822 | 2516.7500 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold90m_short_time | adx_di_trend | 3 | us_rth | 90 | short | time | 2812 | 4045.7500 | 1.0878 | 0.4584 | 1963.7500 |
| trend_donchian_atr_breakout_3m_us_rth_lb30_thr0.25_hold60m_both_time | donchian_atr_breakout | 3 | us_rth | 60 | both | time | 13748 | -4312.5000 | 0.9753 | 0.4764 | 8390.2500 |
| trend_vwap_trend_pullback_1m_us_rth_lb60_thr0.5_hold60m_both_time | vwap_trend_pullback | 1 | us_rth | 60 | both | time | 5591 | 3494.3750 | 1.0466 | 0.4838 | 2983.8750 |
| trend_ema_pullback_1m_us_rth_lb34_ema13_34_thr0.5_hold60m_long_time | ema_pullback | 1 | us_rth | 60 | long | time | 19924 | -996.5000 | 0.9956 | 0.5100 | 6729.5000 |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr22_hold60m_both_time | adx_di_trend | 1 | us_rth | 60 | both | time | 22301 | 2029.6250 | 1.0076 | 0.4814 | 11600.1250 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr30_hold60m_both_time | adx_di_trend | 1 | us_rth | 60 | both | time | 4065 | -230.8750 | 0.9956 | 0.4804 | 3644.1250 |
| trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.5_hold60m_both_time | donchian_atr_breakout | 3 | us_rth | 60 | both | time | 12347 | -561.3750 | 0.9964 | 0.4791 | 6394.6250 |
| trend_opening_range_breakout_1m_us_rth_lb60_thr0.25_hold90m_both_time | opening_range_breakout | 1 | us_rth | 90 | both | time | 7020 | 4414.7500 | 1.0419 | 0.5004 | 6460.3750 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold30m_short_time | vwap_trend_pullback | 1 | us_rth | 30 | short | time | 2858 | 3218.7500 | 1.1159 | 0.4643 | 1246.7500 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold60m_long_time | adx_di_trend | 3 | us_rth | 60 | long | time | 1889 | 1985.1250 | 1.1174 | 0.5299 | 1801.8750 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold60m_both_time | vwap_trend_pullback | 1 | us_rth | 60 | both | time | 5165 | 3006.3750 | 1.0434 | 0.4854 | 2221.5000 |
| trend_vwap_trend_pullback_1m_us_rth_lb60_thr0.25_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 4764 | 4410.7500 | 1.0576 | 0.4962 | 3276.5000 |
| trend_ema_pullback_1m_us_rth_lb34_ema13_34_thr0_hold60m_long_time | ema_pullback | 1 | us_rth | 60 | long | time | 18194 | -3078.0000 | 0.9852 | 0.5060 | 6651.0000 |
| trend_donchian_atr_breakout_3m_us_rth_lb30_thr0.25_hold90m_short_time | donchian_atr_breakout | 3 | us_rth | 90 | short | time | 6188 | -4316.0000 | 0.9595 | 0.4573 | 5868.5000 |
| trend_ema_pullback_1m_us_rth_lb21_ema9_21_thr0_hold60m_both_time | ema_pullback | 1 | us_rth | 60 | both | time | 25805 | -2742.6250 | 0.9910 | 0.4874 | 8387.2500 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr18_hold90m_long_time | adx_di_trend | 3 | us_rth | 90 | long | time | 6267 | 1943.6250 | 1.0227 | 0.5258 | 3264.8750 |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr32_hold60m_both_time | adx_di_trend | 1 | us_rth | 60 | both | time | 13571 | 3011.1250 | 1.0185 | 0.4781 | 5880.3750 |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr18_hold60m_both_time | adx_di_trend | 1 | us_rth | 60 | both | time | 25092 | 465.2500 | 1.0016 | 0.4801 | 11498.3750 |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr32_hold60m_long_time | adx_di_trend | 1 | us_rth | 60 | long | time | 8820 | 6844.2500 | 1.0702 | 0.5067 | 2804.5000 |
| trend_ema_pullback_1m_us_rth_lb89_ema34_89_thr0.25_hold60m_both_time | ema_pullback | 1 | us_rth | 60 | both | time | 22120 | -911.2500 | 0.9965 | 0.4812 | 5704.6250 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr28_hold90m_both_time | adx_di_trend | 1 | us_rth | 90 | both | time | 4495 | 3380.6250 | 1.0501 | 0.4912 | 3083.5000 |
| trend_donchian_atr_breakout_3m_us_rth_lb30_thr0.5_hold90m_both_time | donchian_atr_breakout | 3 | us_rth | 90 | both | time | 9260 | -1570.0000 | 0.9892 | 0.4801 | 7189.0000 |
| trend_ema_pullback_3m_us_rth_lb21_ema9_21_thr0.5_hold60m_both_time | ema_pullback | 3 | us_rth | 60 | both | time | 24447 | -6534.1250 | 0.9775 | 0.4841 | 9673.0000 |
| trend_vwap_trend_pullback_3m_us_rth_lb20_thr0.25_hold60m_short_time | vwap_trend_pullback | 3 | us_rth | 60 | short | time | 3279 | 1862.6250 | 1.0429 | 0.4721 | 3434.8750 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold90m_long_time | adx_di_trend | 3 | us_rth | 90 | long | time | 1482 | 2247.0000 | 1.1325 | 0.5540 | 2054.6250 |
| trend_vwap_trend_pullback_1m_us_rth_lb20_thr0.5_hold60m_both_time | vwap_trend_pullback | 1 | us_rth | 60 | both | time | 8085 | 6913.1250 | 1.0677 | 0.4846 | 2341.1250 |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr28_hold60m_both_time | adx_di_trend | 1 | us_rth | 60 | both | time | 17118 | -3009.5000 | 0.9856 | 0.4751 | 10032.6250 |
| trend_vwap_trend_pullback_1m_us_rth_lb60_thr0.5_hold60m_short_time | vwap_trend_pullback | 1 | us_rth | 60 | short | time | 3052 | 1883.2500 | 1.0451 | 0.4721 | 2122.2500 |
| trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold30m_both_time | vwap_trend_pullback | 1 | us_rth | 30 | both | time | 4637 | 2126.1250 | 1.0461 | 0.4824 | 2380.1250 |
| trend_ema_trend_1m_us_rth_lb21_ema9_21_thr0_hold60m_long_time | ema_trend | 1 | us_rth | 60 | long | time | 21766 | -6598.0000 | 0.9741 | 0.5071 | 9123.7500 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr22_hold90m_both_time | adx_di_trend | 1 | us_rth | 90 | both | time | 8530 | 6282.7500 | 1.0509 | 0.4897 | 2832.7500 |
| trend_vwap_trend_pullback_1m_us_rth_lb20_thr0.25_hold60m_both_time | vwap_trend_pullback | 1 | us_rth | 60 | both | time | 7754 | 7780.5000 | 1.0797 | 0.4853 | 2441.3750 |
| trend_vwap_trend_pullback_1m_us_rth_lb20_thr0.25_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 6663 | 4093.1250 | 1.0393 | 0.4897 | 2929.6250 |
| trend_vwap_trend_pullback_1m_us_rth_lb30_thr0.5_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 6466 | 6340.5000 | 1.0633 | 0.4912 | 3247.6250 |
| trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.5_hold60m_short_time | vwap_trend_pullback | 1 | us_rth | 60 | short | time | 3426 | 2609.7500 | 1.0566 | 0.4714 | 2308.0000 |
| trend_ema_pullback_1m_us_rth_lb89_ema34_89_thr0_hold60m_long_time | ema_pullback | 1 | us_rth | 60 | long | time | 13060 | 1955.7500 | 1.0135 | 0.5126 | 5079.5000 |
| trend_adx_di_trend_1m_us_rth_lb30_adx30_thr22_hold30m_long_time | adx_di_trend | 1 | us_rth | 30 | long | time | 9152 | 2006.2500 | 1.0292 | 0.4781 | 4055.0000 |
| trend_vwap_trend_pullback_1m_us_rth_lb30_thr0.25_hold90m_both_time | vwap_trend_pullback | 1 | us_rth | 90 | both | time | 6167 | 5908.6250 | 1.0617 | 0.4918 | 3004.2500 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold60m_short_time | adx_di_trend | 3 | us_rth | 60 | short | time | 3580 | 4552.7500 | 1.0931 | 0.4642 | 2103.6250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr32_hold90m_long_time | adx_di_trend | 3 | us_rth | 90 | long | time | 1145 | 1930.6250 | 1.1572 | 0.5555 | 1432.2500 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr28_hold60m_long_time | adx_di_trend | 3 | us_rth | 60 | long | time | 7407 | 5814.6250 | 1.0707 | 0.5176 | 3164.1250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold30m_short_time | adx_di_trend | 3 | us_rth | 30 | short | time | 7145 | 272.1250 | 1.0038 | 0.4469 | 3831.3750 |
| trend_donchian_atr_breakout_3m_us_rth_lb50_thr0_hold90m_both_time | donchian_atr_breakout | 3 | us_rth | 90 | both | time | 10867 | 2094.1250 | 1.0125 | 0.4869 | 8341.2500 |
| trend_donchian_breakout_3m_us_rth_lb50_thr0_hold90m_both_time | donchian_breakout | 3 | us_rth | 90 | both | time | 10867 | 2094.1250 | 1.0125 | 0.4869 | 8341.2500 |
| trend_adx_di_trend_1m_us_rth_lb14_adx14_thr26_hold60m_both_time | adx_di_trend | 1 | us_rth | 60 | both | time | 18836 | -5897.2500 | 0.9743 | 0.4725 | 12010.0000 |

## Top Future Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | trend_donchian_breakout_3m_us_rth_lb30_thr0_hold90m_both_time | 46 | 14 | 838 | 4766.5000 | 1.1951 | 191 | 1805.6250 | 1.4268 | 0.5131 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb30_thr0_hold90m_both_time | 46 | 15 | 838 | 4766.5000 | 1.1951 | 191 | 1805.6250 | 1.4268 | 0.5131 |
| True | trend_ema_pullback_1m_us_rth_lb34_ema13_34_thr0_hold60m_both_time | 52 | 4 | 1563 | 3083.3750 | 1.1222 | 381 | 1785.8750 | 1.2704 | 0.4751 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.5_hold90m_both_time | 46 | 1 | 682 | 5198.0000 | 1.2629 | 167 | 1766.8750 | 1.4661 | 0.5210 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb30_thr0_hold90m_both_time | 43 | 12 | 365 | 1962.6250 | 1.2426 | 92 | 1643.5000 | 1.5277 | 0.5543 |
| True | trend_ema_trend_3m_us_rth_lb21_ema9_21_thr0_hold90m_both_time | 36 | 5 | 1003 | 2441.8750 | 1.1964 | 248 | 1629.5000 | 1.3844 | 0.5484 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold90m_both_time | 45 | 19 | 831 | 4324.3750 | 1.1917 | 212 | 1610.5000 | 1.3146 | 0.5142 |
| True | trend_opening_range_breakout_1m_us_rth_lb30_thr0_hold90m_both_time | 54 | 3 | 535 | 2888.3750 | 1.2252 | 121 | 1557.6250 | 1.4827 | 0.4959 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb30_thr0.25_hold90m_both_time | 46 | 12 | 762 | 5149.7500 | 1.2299 | 176 | 1536.2500 | 1.3876 | 0.5227 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb20_thr0_hold60m_both_time | 55 | 2 | 498 | 3417.5000 | 1.3706 | 109 | 1521.3750 | 1.4936 | 0.5963 |
| True | trend_adx_di_trend_1m_us_rth_lb14_adx14_thr18_hold90m_both_time | 36 | 9 | 1145 | 1869.6250 | 1.1320 | 286 | 1502.7500 | 1.3106 | 0.5070 |
| True | trend_donchian_breakout_1m_us_rth_lb30_thr0_hold90m_both_time | 29 | 7 | 1018 | 1039.0000 | 1.1281 | 258 | 1472.7500 | 1.6954 | 0.5504 |
| True | trend_donchian_atr_breakout_1m_us_rth_lb30_thr0_hold90m_both_time | 29 | 8 | 1018 | 1039.0000 | 1.1281 | 258 | 1472.7500 | 1.6954 | 0.5504 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb20_thr0.25_hold90m_both_time | 46 | 2 | 841 | 6681.8750 | 1.2814 | 193 | 1468.6250 | 1.3124 | 0.4870 |
| True | trend_vwap_trend_pullback_3m_us_rth_lb20_thr0.5_hold90m_both_time | 55 | 13 | 383 | 3174.1250 | 1.3370 | 87 | 1377.8750 | 1.4463 | 0.5747 |
| True | trend_ema_trend_1m_us_rth_lb21_ema9_21_thr0_hold30m_both_time | 54 | 13 | 2852 | 3194.7500 | 1.0780 | 696 | 1361.0000 | 1.1290 | 0.4986 |
| True | trend_donchian_breakout_3m_us_rth_lb50_thr0_hold60m_long_time | 58 | 20 | 459 | 3543.3750 | 1.3555 | 116 | 1275.5000 | 1.5673 | 0.6293 |
| True | trend_vwap_trend_pullback_3m_us_rth_lb20_thr0.5_hold60m_both_time | 54 | 5 | 430 | 2313.0000 | 1.2814 | 98 | 1275.0000 | 1.7112 | 0.4592 |
| True | trend_ema_pullback_1m_us_rth_lb55_ema21_55_thr0.5_hold60m_both_time | 37 | 5 | 1543 | 2089.3750 | 1.1103 | 388 | 1258.0000 | 1.1783 | 0.5387 |
| True | trend_adx_di_trend_1m_us_rth_lb30_adx30_thr22_hold90m_long_time | 37 | 20 | 323 | 983.6250 | 1.2583 | 84 | 1206.2500 | 1.8779 | 0.5952 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb20_thr0.25_hold60m_both_time | 55 | 6 | 522 | 3015.0000 | 1.3025 | 113 | 1203.8750 | 1.3575 | 0.5929 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold30m_short_time | 46 | 13 | 459 | 2936.3750 | 1.3885 | 175 | 1154.3750 | 1.5243 | 0.5543 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb30_thr0.25_hold90m_short_time | 46 | 5 | 418 | 3882.2500 | 1.3033 | 104 | 1144.5000 | 1.5013 | 0.5481 |
| True | trend_opening_range_breakout_1m_us_rth_lb30_thr0_hold90m_both_time | 52 | 5 | 526 | 2268.0000 | 1.2111 | 131 | 1135.3750 | 1.4189 | 0.4962 |
| True | trend_donchian_breakout_3m_us_rth_lb30_thr0_hold90m_both_time | 48 | 16 | 822 | 3906.0000 | 1.1748 | 209 | 1128.8750 | 1.3123 | 0.5455 |
| True | trend_donchian_atr_breakout_3m_us_rth_lb30_thr0_hold90m_both_time | 48 | 17 | 822 | 3906.0000 | 1.1748 | 209 | 1128.8750 | 1.3123 | 0.5455 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0.25_hold90m_both_time | 52 | 19 | 334 | 1266.2500 | 1.1779 | 90 | 1095.7500 | 1.6155 | 0.5444 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb50_thr0_hold30m_short_time | 43 | 8 | 177 | 1136.1250 | 1.4713 | 43 | 1058.6250 | 2.3227 | 0.6977 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr32_hold30m_short_time | 59 | 4 | 499 | 2783.1250 | 1.2711 | 106 | 1040.5000 | 1.4608 | 0.4811 |
| True | trend_vwap_trend_pullback_1m_us_rth_lb30_thr0_hold60m_both_time | 53 | 19 | 441 | 2136.3750 | 1.3013 | 98 | 1037.7500 | 1.3715 | 0.5714 |
