# NQ Short-Timeframe Trend System Search

## Candidate Sources

Industry-standard trend archetypes translated into mechanical rules: opening range breakout, Donchian/channel breakout, VWAP trend pullback, EMA trend/pullback, and ADX/DI trend following.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Base 1m span: `2010-06-06 22:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Base rows: `5,383,225`.
- Costs: `0.625` NQ points round trip.

## Walk-Forward

- Timeframes: `3m`.
- Train/test: `365` train days, `5` purge days, `90` test days, `90` step days.
- Sessions: `us_rth`.
- Direction filters: `both, long, short`.
- Exit profiles: `time`.
- Stable gate: selected folds >= 3, positive fold rate >= 67%, aggregate net > 0, avg PF >= 1.1, net/drawdown >= 1, and no negative selected OOS fold.

## Verdict

Best stable candidate: `trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold60m_long_time` with `2850.62` OOS net points, `100.00%` positive selected folds, `1.145` avg OOS PF, and `927` OOS trades.
Best positive research candidate: `trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold60m_long_time` (2850.62 OOS points, stable=True).

## Top Aggregate Rows

| stable_candidate | candidate | family | timeframe_minutes | session | holding_minutes | direction_filter | exit_profile | selected_folds | positive_test_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold60m_long_time | adx_di_trend | 3 | us_rth | 60 | long | time | 7 | 1.0000 | 927 | 2850.6250 | 1040.6250 | 2.7393 | 1.1448 | 37.7500 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr22_hold45m_both_time | adx_di_trend | 3 | us_rth | 45 | both | time | 3 | 1.0000 | 525 | 2439.1250 | 713.0000 | 3.4209 | 1.1816 | 62.1250 |
| False | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr22_hold75m_both_time | adx_di_trend | 3 | us_rth | 75 | both | time | 5 | 0.8000 | 1209 | 3904.8750 | 1022.5000 | 3.8189 | 1.1949 | -322.1250 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold75m_both_time | adx_di_trend | 3 | us_rth | 75 | both | time | 12 | 0.5833 | 979 | 3114.3750 | 1054.5000 | 2.9534 | 1.1004 | -388.0000 |
| False | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr24_hold75m_both_time | adx_di_trend | 3 | us_rth | 75 | both | time | 6 | 0.6667 | 1292 | 2766.7500 | 1296.5000 | 2.1340 | 1.0910 | -410.3750 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold90m_both_time | adx_di_trend | 3 | us_rth | 90 | both | time | 12 | 0.4167 | 1092 | 2754.0000 | 1421.2500 | 1.9377 | 1.0816 | -626.1250 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr22_hold75m_both_time | adx_di_trend | 3 | us_rth | 75 | both | time | 12 | 0.6667 | 1558 | 2737.5000 | 994.6250 | 2.7523 | 1.0733 | -636.1250 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold75m_short_time | adx_di_trend | 3 | us_rth | 75 | short | time | 12 | 0.5000 | 603 | 2718.6250 | 725.7500 | 3.7460 | 1.1067 | -568.5000 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold60m_both_time | adx_di_trend | 3 | us_rth | 60 | both | time | 10 | 0.5000 | 734 | 2538.0000 | 839.2500 | 3.0241 | 1.0989 | -483.1250 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold45m_both_time | adx_di_trend | 3 | us_rth | 45 | both | time | 8 | 0.7500 | 924 | 2498.7500 | 776.6250 | 3.2174 | 1.1048 | -247.0000 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold90m_short_time | adx_di_trend | 3 | us_rth | 90 | short | time | 13 | 0.5385 | 748 | 2470.7500 | 639.2500 | 3.8651 | 1.0174 | -421.7500 |
| False | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr18_hold90m_both_time | adx_di_trend | 3 | us_rth | 90 | both | time | 5 | 0.6000 | 1244 | 2186.2500 | 1207.5000 | 1.8106 | 1.0981 | -1026.3750 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 4 | 0.7500 | 823 | 2172.1250 | 583.6250 | 3.7218 | 1.1635 | -176.2500 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold60m_short_time | adx_di_trend | 3 | us_rth | 60 | short | time | 10 | 0.4000 | 630 | 2132.7500 | 1061.1250 | 2.0099 | 1.1283 | -374.5000 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr18_hold60m_both_time | adx_di_trend | 3 | us_rth | 60 | both | time | 7 | 0.8571 | 1506 | 2020.5000 | 1231.0000 | 1.6413 | 1.0490 | -433.7500 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold30m_short_time | adx_di_trend | 3 | us_rth | 30 | short | time | 10 | 0.4000 | 804 | 1686.0000 | 586.5000 | 2.8747 | 1.0546 | -297.0000 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold30m_short_time | adx_di_trend | 3 | us_rth | 30 | short | time | 6 | 0.5000 | 724 | 1664.7500 | 537.5000 | 3.0972 | 1.1273 | -372.3750 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr22_hold90m_short_time | adx_di_trend | 3 | us_rth | 90 | short | time | 7 | 0.4286 | 481 | 1479.3750 | 817.3750 | 1.8099 | 0.9697 | -361.8750 |
| False | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 4 | 1.0000 | 1321 | 1373.1250 | 1418.6250 | 0.9679 | 1.0481 | 86.6250 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold45m_both_time | adx_di_trend | 3 | us_rth | 45 | both | time | 5 | 0.8000 | 733 | 1356.6250 | 855.7500 | 1.5853 | 1.0812 | -244.2500 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold60m_long_time | adx_di_trend | 3 | us_rth | 60 | long | time | 16 | 0.8125 | 561 | 1340.3750 | 421.5000 | 3.1800 | 1.4693 | -89.0000 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold90m_both_time | adx_di_trend | 3 | us_rth | 90 | both | time | 8 | 0.5000 | 469 | 1281.6250 | 655.7500 | 1.9544 | 1.0787 | -550.1250 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold30m_short_time | adx_di_trend | 3 | us_rth | 30 | short | time | 9 | 0.4444 | 912 | 1273.2500 | 1106.0000 | 1.1512 | 1.0504 | -431.8750 |
| False | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold75m_both_time | adx_di_trend | 3 | us_rth | 75 | both | time | 8 | 0.6250 | 1555 | 1262.8750 | 1328.3750 | 0.9507 | 1.0665 | -946.8750 |
| False | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr18_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 3 | 0.3333 | 1689 | 1259.8750 | 1926.6250 | 0.6539 | 1.0345 | -282.0000 |
| False | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr18_hold60m_long_time | adx_di_trend | 3 | us_rth | 60 | long | time | 4 | 0.7500 | 873 | 1193.6250 | 2108.0000 | 0.5662 | 1.1245 | -1473.1250 |
| False | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr28_hold60m_long_time | adx_di_trend | 3 | us_rth | 60 | long | time | 10 | 0.5000 | 1112 | 1170.5000 | 887.7500 | 1.3185 | 1.0003 | -468.2500 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr32_hold75m_both_time | adx_di_trend | 3 | us_rth | 75 | both | time | 7 | 0.5714 | 250 | 1166.7500 | 470.2500 | 2.4811 | 1.2510 | -249.8750 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold90m_both_time | adx_di_trend | 3 | us_rth | 90 | both | time | 9 | 0.3333 | 635 | 1161.8750 | 1355.0000 | 0.8575 | 0.9882 | -495.0000 |
| False | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold75m_long_time | adx_di_trend | 3 | us_rth | 75 | long | time | 23 | 0.6522 | 568 | 1086.5000 | 263.7500 | 4.1194 | 1.5161 | -261.2500 |

## Full-Sample Check

| candidate | family | timeframe_minutes | session | holding_minutes | direction_filter | exit_profile | trades | net_points | profit_factor | win_rate | max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold60m_long_time | adx_di_trend | 3 | us_rth | 60 | long | time | 8727 | 5750.6250 | 1.0588 | 0.5081 | 3610.6250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr22_hold45m_both_time | adx_di_trend | 3 | us_rth | 45 | both | time | 11643 | 3423.1250 | 1.0283 | 0.4816 | 4029.5000 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr22_hold75m_both_time | adx_di_trend | 3 | us_rth | 75 | both | time | 15490 | 5695.2500 | 1.0274 | 0.4815 | 4822.1250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold75m_both_time | adx_di_trend | 3 | us_rth | 75 | both | time | 5285 | 8005.3750 | 1.1170 | 0.5041 | 1928.0000 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr24_hold75m_both_time | adx_di_trend | 3 | us_rth | 75 | both | time | 13832 | 7174.7500 | 1.0390 | 0.4832 | 4926.0000 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold90m_both_time | adx_di_trend | 3 | us_rth | 90 | both | time | 5851 | 6177.1250 | 1.0731 | 0.4953 | 2113.2500 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr22_hold75m_both_time | adx_di_trend | 3 | us_rth | 75 | both | time | 8055 | 9003.1250 | 1.0858 | 0.5016 | 1779.1250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold75m_short_time | adx_di_trend | 3 | us_rth | 75 | short | time | 3111 | 6019.1250 | 1.1298 | 0.4664 | 1713.8750 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold60m_both_time | adx_di_trend | 3 | us_rth | 60 | both | time | 4890 | 6272.7500 | 1.1131 | 0.4922 | 1807.1250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold45m_both_time | adx_di_trend | 3 | us_rth | 45 | both | time | 7530 | 6959.5000 | 1.0915 | 0.4936 | 1544.1250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold90m_short_time | adx_di_trend | 3 | us_rth | 90 | short | time | 3587 | 5085.8750 | 1.0889 | 0.4569 | 2246.1250 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr18_hold90m_both_time | adx_di_trend | 3 | us_rth | 90 | both | time | 16144 | -1644.5000 | 0.9931 | 0.4830 | 6236.5000 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 12633 | 2895.8750 | 1.0272 | 0.4713 | 3364.7500 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold60m_short_time | adx_di_trend | 3 | us_rth | 60 | short | time | 3580 | 4552.7500 | 1.0931 | 0.4642 | 2103.6250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr18_hold60m_both_time | adx_di_trend | 3 | us_rth | 60 | both | time | 14038 | 6101.7500 | 1.0366 | 0.4884 | 4976.1250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold30m_short_time | adx_di_trend | 3 | us_rth | 30 | short | time | 4449 | 3900.8750 | 1.0901 | 0.4502 | 1781.8750 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold30m_short_time | adx_di_trend | 3 | us_rth | 30 | short | time | 7145 | 272.1250 | 1.0038 | 0.4469 | 3831.3750 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr22_hold90m_short_time | adx_di_trend | 3 | us_rth | 90 | short | time | 4496 | 4553.5000 | 1.0633 | 0.4562 | 2411.5000 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 22482 | 1345.2500 | 1.0068 | 0.4671 | 7491.5000 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold45m_both_time | adx_di_trend | 3 | us_rth | 45 | both | time | 9403 | 3835.8750 | 1.0391 | 0.4822 | 2985.7500 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold60m_long_time | adx_di_trend | 3 | us_rth | 60 | long | time | 2474 | 2094.5000 | 1.0904 | 0.5218 | 2859.0000 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold90m_both_time | adx_di_trend | 3 | us_rth | 90 | both | time | 3751 | 5902.8750 | 1.1105 | 0.5081 | 2000.6250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold30m_short_time | adx_di_trend | 3 | us_rth | 30 | short | time | 5674 | 1101.0000 | 1.0193 | 0.4462 | 2956.3750 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr26_hold75m_both_time | adx_di_trend | 3 | us_rth | 75 | both | time | 12286 | 4687.2500 | 1.0283 | 0.4862 | 3763.0000 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr18_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 37497 | -5922.8750 | 0.9815 | 0.4644 | 16171.7500 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr18_hold60m_long_time | adx_di_trend | 3 | us_rth | 60 | long | time | 15123 | 2219.8750 | 1.0130 | 0.4996 | 6380.0000 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr28_hold60m_long_time | adx_di_trend | 3 | us_rth | 60 | long | time | 7407 | 5814.6250 | 1.0707 | 0.5176 | 3164.1250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr32_hold75m_both_time | adx_di_trend | 3 | us_rth | 75 | both | time | 2596 | 4840.7500 | 1.1516 | 0.5023 | 1505.5000 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold90m_both_time | adx_di_trend | 3 | us_rth | 90 | both | time | 4688 | 6980.7500 | 1.1033 | 0.5015 | 1355.0000 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold75m_long_time | adx_di_trend | 3 | us_rth | 75 | long | time | 1639 | 1999.3750 | 1.1154 | 0.5546 | 2153.0000 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold90m_long_time | adx_di_trend | 3 | us_rth | 90 | long | time | 1482 | 2247.0000 | 1.1325 | 0.5540 | 2054.6250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 7991 | 4944.8750 | 1.0766 | 0.4684 | 2163.2500 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold45m_short_time | adx_di_trend | 3 | us_rth | 45 | short | time | 5459 | 2792.8750 | 1.0433 | 0.4578 | 3148.1250 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr32_hold30m_short_time | adx_di_trend | 3 | us_rth | 30 | short | time | 7855 | 3135.3750 | 1.0407 | 0.4508 | 3619.0000 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold75m_short_time | adx_di_trend | 3 | us_rth | 75 | short | time | 3965 | 5324.6250 | 1.0905 | 0.4671 | 2124.6250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr32_hold60m_long_time | adx_di_trend | 3 | us_rth | 60 | long | time | 1465 | 2238.3750 | 1.1855 | 0.5358 | 1434.3750 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr32_hold90m_both_time | adx_di_trend | 3 | us_rth | 90 | both | time | 2297 | 5701.8750 | 1.1883 | 0.5150 | 1317.3750 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold60m_short_time | adx_di_trend | 3 | us_rth | 60 | short | time | 2787 | 4620.3750 | 1.1238 | 0.4672 | 1468.5000 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold75m_long_time | adx_di_trend | 3 | us_rth | 75 | long | time | 2147 | 1314.1250 | 1.0535 | 0.5300 | 2779.6250 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr24_hold45m_long_time | adx_di_trend | 3 | us_rth | 45 | long | time | 11879 | -107.8750 | 0.9991 | 0.4943 | 4372.3750 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr30_hold60m_long_time | adx_di_trend | 3 | us_rth | 60 | long | time | 1889 | 1985.1250 | 1.1174 | 0.5299 | 1801.8750 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr22_hold60m_both_time | adx_di_trend | 3 | us_rth | 60 | both | time | 18125 | 1707.1250 | 1.0078 | 0.4793 | 6749.0000 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr32_hold90m_long_time | adx_di_trend | 3 | us_rth | 90 | long | time | 1145 | 1930.6250 | 1.1572 | 0.5555 | 1432.2500 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold75m_both_time | adx_di_trend | 3 | us_rth | 75 | both | time | 4208 | 4871.5000 | 1.0886 | 0.4941 | 2089.5000 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold45m_short_time | adx_di_trend | 3 | us_rth | 45 | short | time | 4309 | 4310.8750 | 1.0852 | 0.4706 | 1559.1250 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr28_hold30m_both_time | adx_di_trend | 3 | us_rth | 30 | both | time | 19249 | -2857.8750 | 0.9832 | 0.4626 | 9377.0000 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr32_hold45m_short_time | adx_di_trend | 3 | us_rth | 45 | short | time | 6274 | 984.2500 | 1.0131 | 0.4511 | 3372.0000 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold60m_both_time | adx_di_trend | 3 | us_rth | 60 | both | time | 6123 | 7577.8750 | 1.1070 | 0.4934 | 1477.0000 |
| trend_adx_di_trend_3m_us_rth_lb14_adx14_thr30_hold30m_long_time | adx_di_trend | 3 | us_rth | 30 | long | time | 8781 | -1723.1250 | 0.9753 | 0.4920 | 3251.1250 |
| trend_adx_di_trend_3m_us_rth_lb30_adx30_thr32_hold30m_long_time | adx_di_trend | 3 | us_rth | 30 | long | time | 2316 | 1127.7500 | 1.0865 | 0.4991 | 1320.3750 |

## Top Future Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr22_hold75m_both_time | 46 | 18 | 972 | 4473.5000 | 1.1626 | 241 | 2263.8750 | 1.4272 | 0.5560 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr24_hold75m_both_time | 46 | 16 | 867 | 4259.8750 | 1.1745 | 210 | 2187.5000 | 1.4875 | 0.5952 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr18_hold90m_both_time | 48 | 17 | 1037 | 3115.3750 | 1.1063 | 250 | 2142.0000 | 1.5954 | 0.5720 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr18_hold75m_both_time | 48 | 4 | 1177 | 4765.1250 | 1.1565 | 281 | 1877.3750 | 1.4590 | 0.5409 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold90m_both_time | 53 | 12 | 388 | 714.5000 | 1.0846 | 90 | 1862.5000 | 1.7518 | 0.6000 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr18_hold30m_both_time | 58 | 4 | 2287 | 5489.3750 | 1.1301 | 577 | 1794.8750 | 1.1583 | 0.5251 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold90m_both_time | 53 | 14 | 319 | 714.6250 | 1.0999 | 71 | 1713.6250 | 1.9439 | 0.6056 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold30m_both_time | 44 | 11 | 809 | 1212.6250 | 1.1144 | 172 | 1617.7500 | 1.5790 | 0.5291 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold75m_short_time | 58 | 16 | 212 | 2350.7500 | 1.4168 | 57 | 1555.6250 | 1.8356 | 0.5088 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr22_hold45m_both_time | 58 | 5 | 679 | 2129.6250 | 1.1319 | 195 | 1552.6250 | 1.3422 | 0.5179 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold60m_both_time | 53 | 2 | 326 | 793.5000 | 1.1361 | 81 | 1519.6250 | 1.9776 | 0.6173 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold75m_both_time | 54 | 16 | 343 | 1818.3750 | 1.2399 | 76 | 1482.0000 | 1.9046 | 0.6053 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr28_hold90m_both_time | 44 | 14 | 595 | 1771.6250 | 1.1242 | 147 | 1409.3750 | 1.2915 | 0.5238 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold30m_both_time | 58 | 14 | 462 | 2236.7500 | 1.2493 | 140 | 1335.5000 | 1.5922 | 0.5143 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr18_hold60m_long_time | 54 | 6 | 924 | 2157.5000 | 1.1256 | 220 | 1333.0000 | 1.3459 | 0.5318 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr22_hold90m_short_time | 55 | 15 | 331 | 2417.1250 | 1.2902 | 76 | 1331.7500 | 1.5034 | 0.5000 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold75m_short_time | 55 | 4 | 237 | 2638.8750 | 1.5028 | 58 | 1324.5000 | 1.6791 | 0.6034 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold90m_both_time | 53 | 4 | 251 | 769.3750 | 1.1385 | 57 | 1236.3750 | 1.7431 | 0.6316 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold45m_short_time | 44 | 19 | 360 | 1161.2500 | 1.1804 | 76 | 1213.0000 | 1.7967 | 0.6316 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold30m_short_time | 58 | 13 | 315 | 1621.8750 | 1.2847 | 91 | 1200.1250 | 1.6554 | 0.5165 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold30m_short_time | 44 | 16 | 466 | 1324.7500 | 1.1914 | 107 | 1186.8750 | 1.6742 | 0.5514 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold30m_short_time | 46 | 6 | 459 | 2936.3750 | 1.3885 | 175 | 1154.3750 | 1.5243 | 0.5543 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold60m_short_time | 44 | 18 | 228 | 1151.5000 | 1.2577 | 58 | 1153.2500 | 1.6519 | 0.6552 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr18_hold60m_both_time | 53 | 3 | 917 | 1418.3750 | 1.0859 | 208 | 1103.0000 | 1.1832 | 0.5096 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold60m_both_time | 54 | 1 | 321 | 1770.6250 | 1.2863 | 72 | 1086.7500 | 1.6897 | 0.6250 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold45m_both_time | 58 | 12 | 437 | 2021.6250 | 1.1912 | 133 | 1080.3750 | 1.3785 | 0.5789 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr22_hold90m_both_time | 56 | 18 | 448 | 3661.7500 | 1.2834 | 106 | 1070.7500 | 1.2335 | 0.5094 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr24_hold90m_both_time | 54 | 9 | 385 | 2003.1250 | 1.2197 | 85 | 1066.8750 | 1.4522 | 0.4706 |
| True | trend_adx_di_trend_3m_us_rth_lb30_adx30_thr22_hold30m_short_time | 46 | 19 | 591 | 1662.8750 | 1.1499 | 209 | 1042.1250 | 1.3459 | 0.5120 |
| True | trend_adx_di_trend_3m_us_rth_lb14_adx14_thr32_hold30m_short_time | 59 | 3 | 499 | 2783.1250 | 1.2711 | 106 | 1040.5000 | 1.4608 | 0.4811 |
