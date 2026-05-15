# NQ Pine Indicator Combination Search

- Data: `2026-03-27` to `2026-04-28` from `data/raw/databento`; latest observed bar `2026-04-27 23:59:00+00:00`.
- Pine inputs: `pine_scripts/nq_lightglow_timecell_composite_paper_readiness.pine` and `pine_scripts/CM_MacD_Ult_MTF.pine`.
- Cost model: 1.50 NQ points round trip, matching Pine slippage/commission assumptions used by the Lightglow strategy.
- Search size: 36 combinations across Lightglow signal families, CM MACD MTF filters, stops, targets, holds, and risk controls.

## Best Strategy

- Name: `long_bias_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk`
- Lightglow families: `top_breakout_long+trend_ignition_long+trend_pullback_long+trend_transition_long+reversal_impulse_long`
- MACD filter: `cross_recent_5` on `1` minute aggregation
- Exit/risk: stop ATR buffer `1.25`, target `2.5R`, max hold `30` bars, risk controls `False`
- Performance: `218` trades, `1732.10` net points, PF `2.05`, win rate `55.0%`, max DD `133.54` points, worst trade `-109.49` points.

## Top Ranked Combinations

| strategy | trades | net_points | profit_factor | win_rate | avg_points | max_drawdown_points | worst_trade_points | score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| long_bias_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 218 | 1732.1003 | 2.0531 | 0.5505 | 7.9454 | 133.5368 | -109.4930 | 1416.2139 |
| selective_bidirectional_strict_short_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 280 | 1920.8863 | 1.9141 | 0.5429 | 6.8603 | 167.1788 | -109.4930 | 1260.1510 |
| selective_bidirectional_session_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 322 | 1776.5367 | 1.5897 | 0.5311 | 5.5172 | 198.4594 | -109.4930 | 992.5965 |
| selective_bidirectional_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 376 | 1351.5891 | 1.3594 | 0.4947 | 3.5947 | 271.8647 | -88.9689 | 580.4129 |
| selective_bidirectional_core_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 376 | 1351.5891 | 1.3594 | 0.4947 | 3.5947 | 271.8647 | -88.9689 | 580.4129 |
| smc_long_bias_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 370 | 1105.7168 | 1.3409 | 0.4892 | 2.9884 | 234.7754 | -109.4930 | 551.2286 |
| smc_trend_filtered_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 375 | 1132.3363 | 1.2951 | 0.4907 | 3.0196 | 271.8647 | -88.9689 | 495.7767 |
| trend_transition_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 370 | 1138.9946 | 1.3037 | 0.4919 | 3.0784 | 280.8647 | -88.9689 | 485.2764 |
| smc_bos_fvg_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 251 | 775.3133 | 1.3088 | 0.5259 | 3.0889 | 206.4625 | -88.9689 | 456.1159 |
| trend_pullback_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 65 | 414.0753 | 1.6649 | 0.5077 | 6.3704 | 139.4081 | -70.7887 | 390.5306 |
| structure_rr_selective_strict_macd1_cross_recent_5_stop1.25_r2.5_h30_rr2_wait8_norisk | 75 | 350.9724 | 1.6988 | 0.4800 | 4.6796 | 151.5335 | -36.8108 | 321.1527 |
| structure_rr_selective_strict_macd1_cross_recent_5_stop1.25_r2.5_h30_rr2.5_wait8_norisk | 75 | 350.9724 | 1.6988 | 0.4800 | 4.6796 | 151.5335 | -36.8108 | 321.1527 |
| phase_trend_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 484 | 1025.3071 | 1.2072 | 0.4793 | 2.1184 | 443.3032 | -84.3002 | 304.5285 |
| phase_long_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 294 | 758.0090 | 1.2637 | 0.5034 | 2.5783 | 342.7877 | -84.3002 | 298.1032 |
| all_lightglow_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 536 | 1026.2427 | 1.1893 | 0.4776 | 1.9146 | 525.5679 | -88.9689 | 267.2064 |
| phase_plus_fast_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 489 | 953.1766 | 1.1903 | 0.4785 | 1.9492 | 500.1990 | -84.3002 | 262.6840 |
| smc_ob_retest_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 341 | 742.9387 | 1.2476 | 0.4751 | 2.1787 | 417.9949 | -62.8327 | 252.1448 |
| smc_strict_bidirectional_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 551 | 998.8043 | 1.1825 | 0.4701 | 1.8127 | 589.7749 | -92.4097 | 240.5689 |
| boundary_reversal_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 26 | 152.9009 | 1.5024 | 0.5769 | 5.8808 | 66.8204 | -54.4737 | 202.4389 |
| phase_short_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 203 | 391.4653 | 1.1790 | 0.4581 | 1.9284 | 458.1065 | -86.1500 | 156.8041 |

## Screenshot-Inspired Early Reversal Candidates

These rows emphasize boundary sweep/reclaim/reject behavior plus MACD histogram repair/deceleration, intended to enter before waiting for a full delayed MACD line cross.

| strategy | trades | net_points | profit_factor | win_rate | avg_points | max_drawdown_points | worst_trade_points | score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| screenshot_reversal_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 32 | 89.5218 | 1.2422 | 0.5000 | 2.7976 | 107.0499 | -54.4737 | 96.3166 |
| fast_boundary_reversal_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 22 | -15.7980 | 0.9396 | 0.5000 | -0.7181 | 160.8459 | -54.4737 | -1000015.7980 |

## Bidirectional Phase Trend Candidates

These rows target fast but staged upside and downside moves using EMA phase state, micro breakouts/breakdowns, pullback reclaim/failure, and early MACD histogram filters.

| strategy | trades | net_points | profit_factor | win_rate | avg_points | max_drawdown_points | worst_trade_points | score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| phase_trend_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 484 | 1025.3071 | 1.2072 | 0.4793 | 2.1184 | 443.3032 | -84.3002 | 304.5285 |
| phase_long_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 294 | 758.0090 | 1.2637 | 0.5034 | 2.5783 | 342.7877 | -84.3002 | 298.1032 |
| phase_plus_fast_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 489 | 953.1766 | 1.1903 | 0.4785 | 1.9492 | 500.1990 | -84.3002 | 262.6840 |
| phase_short_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 203 | 391.4653 | 1.1790 | 0.4581 | 1.9284 | 458.1065 | -86.1500 | 156.8041 |

## Selective Bidirectional Candidates

These rows keep the long-biased best-candidate family set and add only high-quality short continuation/transition/breakdown structures, avoiding broad top-picking shorts.

| strategy | trades | net_points | profit_factor | win_rate | avg_points | max_drawdown_points | worst_trade_points | score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| selective_bidirectional_strict_short_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 280 | 1920.8863 | 1.9141 | 0.5429 | 6.8603 | 167.1788 | -109.4930 | 1260.1510 |
| selective_bidirectional_session_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 322 | 1776.5367 | 1.5897 | 0.5311 | 5.5172 | 198.4594 | -109.4930 | 992.5965 |
| selective_bidirectional_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 376 | 1351.5891 | 1.3594 | 0.4947 | 3.5947 | 271.8647 | -88.9689 | 580.4129 |
| selective_bidirectional_core_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 376 | 1351.5891 | 1.3594 | 0.4947 | 3.5947 | 271.8647 | -88.9689 | 580.4129 |

## Structure Risk-Reward Pullback Candidates

These rows keep the directional signal fixed, then wait for a pullback into the favorable side of the recent structure and require a minimum historical structure R/R before entering.

| strategy | trades | net_points | profit_factor | win_rate | avg_points | max_drawdown_points | worst_trade_points | score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| structure_rr_selective_strict_macd1_cross_recent_5_stop1.25_r2.5_h30_rr2_wait8_norisk | 75 | 350.9724 | 1.6988 | 0.4800 | 4.6796 | 151.5335 | -36.8108 | 321.1527 |
| structure_rr_selective_strict_macd1_cross_recent_5_stop1.25_r2.5_h30_rr2.5_wait8_norisk | 75 | 350.9724 | 1.6988 | 0.4800 | 4.6796 | 151.5335 | -36.8108 | 321.1527 |
| structure_rr_long_bias_macd1_cross_recent_5_stop1.25_r2.5_h30_rr2_wait8_norisk | 59 | 144.3324 | 1.3279 | 0.4576 | 2.4463 | 190.0871 | -36.8108 | 142.8148 |
| structure_rr_long_bias_macd1_cross_recent_5_stop1.25_r2.5_h30_rr2.5_wait8_norisk | 59 | 144.3324 | 1.3279 | 0.4576 | 2.4463 | 190.0871 | -36.8108 | 142.8148 |

## Lightglow SMC-Filtered Candidates

These rows translate the Lightglow/LuxAlgo SMC concepts into non-lookahead filters: internal/swing BOS or CHoCH, premium/discount location, recent fair value gaps, and order-block retests.

| strategy | trades | net_points | profit_factor | win_rate | avg_points | max_drawdown_points | worst_trade_points | score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| smc_long_bias_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 370 | 1105.7168 | 1.3409 | 0.4892 | 2.9884 | 234.7754 | -109.4930 | 551.2286 |
| smc_trend_filtered_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 375 | 1132.3363 | 1.2951 | 0.4907 | 3.0196 | 271.8647 | -88.9689 | 495.7767 |
| smc_bos_fvg_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 251 | 775.3133 | 1.3088 | 0.5259 | 3.0889 | 206.4625 | -88.9689 | 456.1159 |
| smc_ob_retest_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 341 | 742.9387 | 1.2476 | 0.4751 | 2.1787 | 417.9949 | -62.8327 | 252.1448 |
| smc_strict_bidirectional_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 551 | 998.8043 | 1.1825 | 0.4701 | 1.8127 | 589.7749 | -92.4097 | 240.5689 |
| smc_reversal_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk | 125 | 82.7233 | 1.0571 | 0.4000 | 0.6618 | 486.2696 | -92.4097 | 79.0857 |

## 60m MACD Candidates

These rows match the chart setup using `CM_Ult_MacD_MTF 60 12 26 9` more closely.

No rows.

## Best Trades

| entry_ts | exit_ts | signal_family | session | direction | entry_price | exit_price | exit_reason | net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-03-27 01:29:00+00:00 | 2026-03-27 01:59:00+00:00 | trend_transition_long | asia | 1 | 23864.0000 | 23872.0000 | max_hold | 6.5000 |
| 2026-03-27 04:21:00+00:00 | 2026-03-27 04:25:00+00:00 | trend_transition_long | asia | 1 | 23896.7500 | 23889.5747 | protective_stop | -8.6753 |
| 2026-03-27 04:35:00+00:00 | 2026-03-27 05:00:00+00:00 | trend_transition_long | asia | 1 | 23902.2500 | 23922.4727 | target | 18.7227 |
| 2026-03-27 15:24:00+00:00 | 2026-03-27 15:54:00+00:00 | trend_transition_long | us_rth | 1 | 23557.5000 | 23561.5000 | max_hold | 2.5000 |
| 2026-03-30 02:07:00+00:00 | 2026-03-30 02:20:00+00:00 | trend_transition_long | asia | 1 | 23221.2500 | 23196.5746 | protective_stop | -26.1754 |
| 2026-03-30 03:07:00+00:00 | 2026-03-30 03:26:00+00:00 | trend_transition_long | asia | 1 | 23277.0000 | 23290.4789 | protective_stop | 11.9789 |
| 2026-03-30 04:01:00+00:00 | 2026-03-30 04:25:00+00:00 | trend_transition_long | asia | 1 | 23300.0000 | 23330.5327 | target | 29.0327 |
| 2026-03-30 08:32:00+00:00 | 2026-03-30 09:02:00+00:00 | trend_transition_long | europe | 1 | 23438.5000 | 23443.2500 | max_hold | 3.2500 |
| 2026-03-30 10:51:00+00:00 | 2026-03-30 11:20:00+00:00 | trend_transition_long | europe | 1 | 23413.2500 | 23445.7082 | protective_stop | 30.9582 |
| 2026-03-30 13:01:00+00:00 | 2026-03-30 13:05:00+00:00 | trend_pullback_long | europe | 1 | 23517.0000 | 23493.8712 | protective_stop | -24.6288 |
| 2026-03-30 22:01:00+00:00 | 2026-03-30 22:31:00+00:00 | trend_transition_long | us_late | 1 | 23131.2500 | 23116.7500 | max_hold | -16.0000 |
| 2026-03-31 05:48:00+00:00 | 2026-03-31 06:01:00+00:00 | trend_transition_long | asia | 1 | 23323.5000 | 23296.0715 | protective_stop | -28.9285 |
| 2026-03-31 08:05:00+00:00 | 2026-03-31 08:14:00+00:00 | trend_transition_long | europe | 1 | 23382.7500 | 23342.5579 | protective_stop | -41.6921 |
| 2026-03-31 09:05:00+00:00 | 2026-03-31 09:35:00+00:00 | trend_transition_long | europe | 1 | 23337.5000 | 23319.5000 | max_hold | -19.5000 |
| 2026-03-31 11:12:00+00:00 | 2026-03-31 11:19:00+00:00 | trend_transition_long | europe | 1 | 23306.5000 | 23339.2231 | protective_stop | 31.2231 |
| 2026-03-31 11:45:00+00:00 | 2026-03-31 11:48:00+00:00 | trend_transition_long | europe | 1 | 23381.2500 | 23348.7395 | protective_stop | -34.0105 |
| 2026-03-31 12:01:00+00:00 | 2026-03-31 12:10:00+00:00 | trend_pullback_long | europe | 1 | 23374.7500 | 23399.3908 | protective_stop | 23.1408 |
| 2026-03-31 13:31:00+00:00 | 2026-03-31 13:54:00+00:00 | trend_transition_long | us_rth | 1 | 23415.7500 | 23554.9282 | target | 137.6782 |
| 2026-03-31 14:34:00+00:00 | 2026-03-31 14:36:00+00:00 | trend_pullback_long | us_rth | 1 | 23578.7500 | 23530.2853 | protective_stop | -49.9647 |
| 2026-03-31 16:39:00+00:00 | 2026-03-31 16:41:00+00:00 | trend_transition_long | us_rth | 1 | 23613.7500 | 23791.8108 | target | 176.5608 |
| 2026-03-31 18:38:00+00:00 | 2026-03-31 19:08:00+00:00 | trend_transition_long | us_rth | 1 | 23857.2500 | 23837.5000 | max_hold | -21.2500 |
| 2026-03-31 19:16:00+00:00 | 2026-03-31 19:46:00+00:00 | trend_transition_long | us_rth | 1 | 23897.7500 | 23928.5000 | max_hold | 29.2500 |
| 2026-03-31 23:18:00+00:00 | 2026-03-31 23:36:00+00:00 | trend_transition_long | asia | 1 | 23967.2500 | 24013.9876 | target | 45.2376 |
| 2026-04-01 03:34:00+00:00 | 2026-04-01 04:04:00+00:00 | trend_transition_long | asia | 1 | 23984.7500 | 23986.2500 | max_hold | 0.0000 |
| 2026-04-01 04:23:00+00:00 | 2026-04-01 04:53:00+00:00 | trend_transition_long | asia | 1 | 24000.0000 | 24021.5000 | max_hold | 20.0000 |
| 2026-04-01 05:06:00+00:00 | 2026-04-01 05:25:00+00:00 | trend_transition_long | asia | 1 | 24025.7500 | 24064.8402 | target | 37.5902 |
| 2026-04-01 10:42:00+00:00 | 2026-04-01 10:55:00+00:00 | trend_transition_long | europe | 1 | 24093.0000 | 24119.3706 | protective_stop | 24.8706 |
| 2026-04-01 11:39:00+00:00 | 2026-04-01 12:00:00+00:00 | trend_transition_long | europe | 1 | 24179.7500 | 24186.4618 | protective_stop | 5.2118 |
| 2026-04-01 12:45:00+00:00 | 2026-04-01 12:49:00+00:00 | trend_transition_long | europe | 1 | 24186.7500 | 24078.7570 | protective_stop | -109.4930 |
| 2026-04-01 14:16:00+00:00 | 2026-04-01 14:39:00+00:00 | trend_transition_long | us_rth | 1 | 24181.5000 | 24234.7500 | target | 51.7500 |
| 2026-04-01 17:04:00+00:00 | 2026-04-01 17:34:00+00:00 | trend_pullback_long | us_rth | 1 | 24338.5000 | 24313.7831 | protective_stop | -26.2169 |
| 2026-04-02 05:31:00+00:00 | 2026-04-02 05:32:00+00:00 | trend_transition_long | asia | 1 | 23823.0000 | 23804.7878 | protective_stop | -19.7122 |
| 2026-04-02 14:07:00+00:00 | 2026-04-02 14:36:00+00:00 | trend_transition_long | us_rth | 1 | 23944.5000 | 24196.8087 | target | 250.8087 |
| 2026-04-02 19:11:00+00:00 | 2026-04-02 19:16:00+00:00 | trend_transition_long | us_rth | 1 | 24174.7500 | 24149.1826 | protective_stop | -27.0674 |
| 2026-04-02 19:51:00+00:00 | 2026-04-02 20:21:00+00:00 | trend_pullback_long | us_rth | 1 | 24187.7500 | 24205.5000 | max_hold | 16.2500 |
| 2026-04-02 20:30:00+00:00 | 2026-04-02 20:34:00+00:00 | trend_transition_long | us_late | 1 | 24225.0000 | 24207.2023 | protective_stop | -19.2977 |
| 2026-04-03 00:01:00+00:00 | 2026-04-03 00:03:00+00:00 | trend_transition_long | asia | 1 | 24226.5000 | 24240.7011 | protective_stop | 12.7011 |
| 2026-04-03 04:05:00+00:00 | 2026-04-03 04:35:00+00:00 | trend_transition_long | asia | 1 | 24174.2500 | 24174.7500 | max_hold | -1.0000 |
| 2026-04-03 05:06:00+00:00 | 2026-04-03 05:18:00+00:00 | trend_transition_long | asia | 1 | 24185.5000 | 24168.9045 | protective_stop | -18.0955 |
| 2026-04-03 08:02:00+00:00 | 2026-04-03 08:22:00+00:00 | trend_transition_long | europe | 1 | 24166.0000 | 24147.5318 | protective_stop | -19.9682 |
| 2026-04-03 12:02:00+00:00 | 2026-04-03 12:07:00+00:00 | trend_pullback_long | europe | 1 | 24157.0000 | 24169.7355 | protective_stop | 11.2355 |
| 2026-04-06 00:58:00+00:00 | 2026-04-06 01:28:00+00:00 | trend_transition_long | asia | 1 | 24213.5000 | 24234.2500 | max_hold | 19.2500 |
| 2026-04-06 04:35:00+00:00 | 2026-04-06 05:05:00+00:00 | trend_pullback_long | asia | 1 | 24243.2500 | 24257.2500 | max_hold | 12.5000 |
| 2026-04-06 06:08:00+00:00 | 2026-04-06 06:12:00+00:00 | trend_transition_long | asia | 1 | 24247.2500 | 24268.0000 | target | 19.2500 |
| 2026-04-06 07:32:00+00:00 | 2026-04-06 07:52:00+00:00 | trend_pullback_long | europe | 1 | 24252.5000 | 24319.2615 | target | 65.2615 |
| 2026-04-06 12:29:00+00:00 | 2026-04-06 12:49:00+00:00 | trend_transition_long | europe | 1 | 24313.0000 | 24321.2804 | protective_stop | 6.7804 |
| 2026-04-06 13:31:00+00:00 | 2026-04-06 14:01:00+00:00 | trend_transition_long | us_rth | 1 | 24329.0000 | 24389.8843 | protective_stop | 59.3843 |
| 2026-04-06 18:11:00+00:00 | 2026-04-06 18:26:00+00:00 | trend_transition_long | us_rth | 1 | 24301.0000 | 24334.4995 | protective_stop | 31.9995 |
| 2026-04-06 19:46:00+00:00 | 2026-04-06 20:16:00+00:00 | trend_transition_long | us_rth | 1 | 24352.0000 | 24341.5000 | max_hold | -12.0000 |
| 2026-04-06 22:01:00+00:00 | 2026-04-06 22:23:00+00:00 | trend_transition_long | us_late | 1 | 24361.0000 | 24330.3041 | protective_stop | -32.1959 |
| 2026-04-07 02:47:00+00:00 | 2026-04-07 03:17:00+00:00 | trend_transition_long | asia | 1 | 24211.2500 | 24208.0000 | max_hold | -4.7500 |
| 2026-04-07 04:26:00+00:00 | 2026-04-07 04:52:00+00:00 | trend_transition_long | asia | 1 | 24232.2500 | 24250.5091 | protective_stop | 16.7591 |
| 2026-04-07 06:09:00+00:00 | 2026-04-07 06:11:00+00:00 | trend_transition_long | asia | 1 | 24237.7500 | 24220.4710 | protective_stop | -18.7790 |
| 2026-04-07 08:01:00+00:00 | 2026-04-07 08:03:00+00:00 | trend_transition_long | europe | 1 | 24269.2500 | 24319.2570 | protective_stop | 48.5070 |
| 2026-04-07 09:10:00+00:00 | 2026-04-07 09:28:00+00:00 | trend_transition_long | europe | 1 | 24374.7500 | 24392.4368 | protective_stop | 16.1868 |
| 2026-04-07 09:35:00+00:00 | 2026-04-07 09:42:00+00:00 | trend_transition_long | europe | 1 | 24418.7500 | 24394.8595 | protective_stop | -25.3905 |
| 2026-04-07 12:56:00+00:00 | 2026-04-07 13:26:00+00:00 | trend_transition_long | europe | 1 | 24261.2500 | 24236.0000 | max_hold | -26.7500 |
| 2026-04-07 15:56:00+00:00 | 2026-04-07 16:03:00+00:00 | trend_transition_long | us_rth | 1 | 24104.5000 | 24224.3963 | target | 118.3963 |
| 2026-04-07 19:45:00+00:00 | 2026-04-07 19:47:00+00:00 | trend_pullback_long | us_rth | 1 | 24240.5000 | 24281.1012 | protective_stop | 39.1012 |
| 2026-04-07 20:42:00+00:00 | 2026-04-07 22:00:00+00:00 | trend_pullback_long | us_late | 1 | 24427.7500 | 24641.0000 | target | 211.7500 |
| 2026-04-07 22:38:00+00:00 | 2026-04-07 23:07:00+00:00 | trend_transition_long | us_late | 1 | 24782.0000 | 24919.4858 | protective_stop | 135.9858 |
| 2026-04-08 00:03:00+00:00 | 2026-04-08 00:04:00+00:00 | trend_transition_long | asia | 1 | 25082.5000 | 25045.1798 | protective_stop | -38.8202 |
| 2026-04-08 03:01:00+00:00 | 2026-04-08 03:12:00+00:00 | trend_transition_long | asia | 1 | 25114.7500 | 25103.5623 | protective_stop | -12.6877 |
| 2026-04-08 05:51:00+00:00 | 2026-04-08 06:21:00+00:00 | trend_pullback_long | asia | 1 | 25175.5000 | 25176.0000 | max_hold | -1.0000 |
| 2026-04-08 08:34:00+00:00 | 2026-04-08 08:37:00+00:00 | trend_transition_long | europe | 1 | 25182.5000 | 25167.3941 | protective_stop | -16.6059 |
| 2026-04-08 08:51:00+00:00 | 2026-04-08 09:03:00+00:00 | trend_transition_long | europe | 1 | 25194.2500 | 25211.7663 | protective_stop | 16.0163 |
| 2026-04-08 09:13:00+00:00 | 2026-04-08 09:26:00+00:00 | trend_transition_long | europe | 1 | 25242.7500 | 25218.4215 | protective_stop | -25.8285 |
| 2026-04-08 11:26:00+00:00 | 2026-04-08 11:56:00+00:00 | trend_transition_long | europe | 1 | 25218.2500 | 25208.0000 | max_hold | -11.7500 |
| 2026-04-08 12:04:00+00:00 | 2026-04-08 12:08:00+00:00 | trend_transition_long | europe | 1 | 25236.2500 | 25237.9422 | protective_stop | 0.1922 |
| 2026-04-08 15:37:00+00:00 | 2026-04-08 16:01:00+00:00 | trend_transition_long | us_rth | 1 | 25050.5000 | 25096.2500 | target | 44.2500 |
| 2026-04-08 16:56:00+00:00 | 2026-04-08 17:05:00+00:00 | trend_transition_long | us_rth | 1 | 25154.5000 | 25136.5120 | protective_stop | -19.4880 |
| 2026-04-08 23:06:00+00:00 | 2026-04-08 23:32:00+00:00 | trend_transition_long | asia | 1 | 25046.2500 | 25026.7978 | protective_stop | -20.9522 |
| 2026-04-09 01:51:00+00:00 | 2026-04-09 02:10:00+00:00 | trend_transition_long | asia | 1 | 25018.2500 | 25028.7289 | protective_stop | 8.9789 |
| 2026-04-09 05:17:00+00:00 | 2026-04-09 05:40:00+00:00 | trend_transition_long | asia | 1 | 25022.0000 | 25035.7302 | protective_stop | 12.2302 |
| 2026-04-09 06:03:00+00:00 | 2026-04-09 06:22:00+00:00 | trend_transition_long | asia | 1 | 25046.2500 | 25028.4865 | protective_stop | -19.2635 |
| 2026-04-09 07:01:00+00:00 | 2026-04-09 07:03:00+00:00 | trend_transition_long | europe | 1 | 25047.5000 | 25031.5694 | protective_stop | -17.4306 |
| 2026-04-09 09:11:00+00:00 | 2026-04-09 09:34:00+00:00 | trend_transition_long | europe | 1 | 24993.0000 | 25004.7084 | protective_stop | 10.2084 |
| 2026-04-09 12:11:00+00:00 | 2026-04-09 12:14:00+00:00 | trend_transition_long | europe | 1 | 25049.2500 | 25037.2946 | protective_stop | -13.4554 |
| 2026-04-09 13:26:00+00:00 | 2026-04-09 13:30:00+00:00 | trend_pullback_long | europe | 1 | 25054.0000 | 25098.7500 | target | 43.2500 |
| 2026-04-09 15:13:00+00:00 | 2026-04-09 15:26:00+00:00 | trend_transition_long | us_rth | 1 | 25055.7500 | 25077.1537 | protective_stop | 19.9037 |
| 2026-04-09 15:49:00+00:00 | 2026-04-09 16:05:00+00:00 | trend_transition_long | us_rth | 1 | 25173.0000 | 25228.9938 | protective_stop | 54.4938 |
| 2026-04-09 19:31:00+00:00 | 2026-04-09 19:55:00+00:00 | trend_pullback_long | us_rth | 1 | 25236.0000 | 25247.0319 | protective_stop | 9.5319 |
| 2026-04-09 23:48:00+00:00 | 2026-04-10 00:02:00+00:00 | trend_transition_long | asia | 1 | 25228.5000 | 25212.4952 | protective_stop | -17.5048 |
| 2026-04-10 01:28:00+00:00 | 2026-04-10 01:43:00+00:00 | trend_transition_long | asia | 1 | 25272.2500 | 25287.7445 | protective_stop | 13.9945 |
| 2026-04-10 03:05:00+00:00 | 2026-04-10 03:10:00+00:00 | trend_transition_long | asia | 1 | 25280.5000 | 25281.4184 | protective_stop | -0.5816 |
| 2026-04-10 03:34:00+00:00 | 2026-04-10 04:04:00+00:00 | trend_pullback_long | asia | 1 | 25289.5000 | 25291.7500 | max_hold | 0.7500 |
| 2026-04-10 08:43:00+00:00 | 2026-04-10 08:47:00+00:00 | trend_transition_long | europe | 1 | 25233.0000 | 25222.3526 | protective_stop | -12.1474 |
| 2026-04-10 10:24:00+00:00 | 2026-04-10 10:29:00+00:00 | trend_transition_long | europe | 1 | 25267.5000 | 25270.1057 | protective_stop | 1.1057 |
| 2026-04-10 10:54:00+00:00 | 2026-04-10 11:06:00+00:00 | trend_transition_long | europe | 1 | 25277.5000 | 25281.5311 | protective_stop | 2.5311 |
| 2026-04-10 12:30:00+00:00 | 2026-04-10 13:00:00+00:00 | trend_pullback_long | europe | 1 | 25324.5000 | 25303.7500 | max_hold | -22.2500 |
| 2026-04-10 13:13:00+00:00 | 2026-04-10 13:25:00+00:00 | trend_pullback_long | europe | 1 | 25319.0000 | 25300.5429 | protective_stop | -19.9571 |
| 2026-04-10 13:31:00+00:00 | 2026-04-10 13:34:00+00:00 | trend_transition_long | us_rth | 1 | 25326.2500 | 25342.3504 | protective_stop | 14.6004 |
| 2026-04-10 15:13:00+00:00 | 2026-04-10 15:26:00+00:00 | trend_transition_long | us_rth | 1 | 25364.5000 | 25368.8644 | protective_stop | 2.8644 |
| 2026-04-10 20:33:00+00:00 | 2026-04-12 22:00:00+00:00 | trend_transition_long | us_late | 1 | 25311.2500 | 25328.8128 | protective_stop | 16.0628 |
| 2026-04-12 23:53:00+00:00 | 2026-04-13 00:23:00+00:00 | trend_transition_long | asia | 1 | 24971.2500 | 24995.0000 | max_hold | 22.2500 |
| 2026-04-13 00:52:00+00:00 | 2026-04-13 01:06:00+00:00 | trend_transition_long | asia | 1 | 25038.7500 | 25056.1887 | protective_stop | 15.9387 |
| 2026-04-13 04:55:00+00:00 | 2026-04-13 05:11:00+00:00 | trend_transition_long | asia | 1 | 25080.2500 | 25065.4166 | protective_stop | -16.3334 |
| 2026-04-13 05:23:00+00:00 | 2026-04-13 05:34:00+00:00 | trend_transition_long | asia | 1 | 25087.2500 | 25064.8099 | protective_stop | -23.9401 |
| 2026-04-13 06:01:00+00:00 | 2026-04-13 06:30:00+00:00 | trend_transition_long | asia | 1 | 25087.0000 | 25107.5035 | protective_stop | 19.0035 |
| 2026-04-13 08:02:00+00:00 | 2026-04-13 08:32:00+00:00 | trend_transition_long | europe | 1 | 25114.7500 | 25110.5000 | max_hold | -5.7500 |
| 2026-04-13 10:47:00+00:00 | 2026-04-13 10:56:00+00:00 | trend_pullback_long | europe | 1 | 25125.5000 | 25151.7500 | target | 24.7500 |
| 2026-04-13 13:20:00+00:00 | 2026-04-13 13:30:00+00:00 | trend_transition_long | europe | 1 | 25188.0000 | 25234.1444 | target | 44.6444 |
| 2026-04-13 13:50:00+00:00 | 2026-04-13 14:20:00+00:00 | trend_transition_long | us_rth | 1 | 25271.5000 | 25273.5000 | max_hold | 0.5000 |
| 2026-04-13 14:45:00+00:00 | 2026-04-13 15:00:00+00:00 | trend_pullback_long | us_rth | 1 | 25316.2500 | 25334.5014 | protective_stop | 16.7514 |
| 2026-04-13 16:51:00+00:00 | 2026-04-13 17:21:00+00:00 | trend_transition_long | us_rth | 1 | 25424.7500 | 25427.5000 | max_hold | 1.2500 |
| 2026-04-13 19:23:00+00:00 | 2026-04-13 19:35:00+00:00 | trend_transition_long | us_rth | 1 | 25456.2500 | 25467.0089 | protective_stop | 9.2589 |
| 2026-04-13 19:51:00+00:00 | 2026-04-13 20:21:00+00:00 | trend_pullback_long | us_rth | 1 | 25511.7500 | 25560.5000 | max_hold | 47.2500 |
| 2026-04-13 22:00:00+00:00 | 2026-04-13 22:01:00+00:00 | trend_transition_long | us_late | 1 | 25575.2500 | 25571.1543 | protective_stop | -5.5957 |
| 2026-04-13 22:41:00+00:00 | 2026-04-13 22:43:00+00:00 | trend_transition_long | us_late | 1 | 25592.0000 | 25582.4072 | protective_stop | -11.0928 |
| 2026-04-13 23:08:00+00:00 | 2026-04-13 23:38:00+00:00 | trend_transition_long | asia | 1 | 25610.2500 | 25601.5000 | max_hold | -10.2500 |
| 2026-04-14 00:32:00+00:00 | 2026-04-14 01:01:00+00:00 | trend_transition_long | asia | 1 | 25588.7500 | 25574.7077 | protective_stop | -15.5423 |
| 2026-04-14 02:08:00+00:00 | 2026-04-14 02:19:00+00:00 | trend_transition_long | asia | 1 | 25587.5000 | 25590.8243 | protective_stop | 1.8243 |
| 2026-04-14 04:18:00+00:00 | 2026-04-14 04:48:00+00:00 | trend_transition_long | asia | 1 | 25589.5000 | 25591.5000 | max_hold | 0.5000 |
| 2026-04-14 05:11:00+00:00 | 2026-04-14 05:24:00+00:00 | trend_pullback_long | asia | 1 | 25594.7500 | 25590.1853 | protective_stop | -6.0647 |
| 2026-04-14 07:03:00+00:00 | 2026-04-14 07:07:00+00:00 | trend_transition_long | europe | 1 | 25596.5000 | 25617.4910 | protective_stop | 19.4910 |
| 2026-04-14 08:28:00+00:00 | 2026-04-14 08:58:00+00:00 | trend_transition_long | europe | 1 | 25641.7500 | 25658.7500 | max_hold | 15.5000 |
| 2026-04-14 10:08:00+00:00 | 2026-04-14 10:34:00+00:00 | trend_transition_long | europe | 1 | 25644.7500 | 25632.5794 | protective_stop | -13.6706 |
| 2026-04-14 11:58:00+00:00 | 2026-04-14 12:28:00+00:00 | trend_pullback_long | europe | 1 | 25678.2500 | 25689.7500 | max_hold | 10.0000 |
| 2026-04-14 13:31:00+00:00 | 2026-04-14 13:39:00+00:00 | trend_transition_long | us_rth | 1 | 25689.0000 | 25717.5726 | protective_stop | 27.0726 |
| 2026-04-14 15:47:00+00:00 | 2026-04-14 16:17:00+00:00 | trend_transition_long | us_rth | 1 | 25882.0000 | 25898.0000 | max_hold | 14.5000 |
| 2026-04-14 16:50:00+00:00 | 2026-04-14 16:53:00+00:00 | trend_transition_long | us_rth | 1 | 25935.7500 | 25919.7981 | protective_stop | -17.4519 |
| 2026-04-14 17:17:00+00:00 | 2026-04-14 17:27:00+00:00 | trend_transition_long | us_rth | 1 | 25933.7500 | 25944.9834 | protective_stop | 9.7334 |
| 2026-04-14 17:39:00+00:00 | 2026-04-14 18:06:00+00:00 | trend_transition_long | us_rth | 1 | 25960.2500 | 25949.5101 | protective_stop | -12.2399 |
| 2026-04-14 20:00:00+00:00 | 2026-04-14 20:03:00+00:00 | trend_transition_long | us_rth | 1 | 26000.5000 | 25977.5552 | protective_stop | -24.4448 |
| 2026-04-14 20:45:00+00:00 | 2026-04-14 22:00:00+00:00 | trend_pullback_long | us_late | 1 | 25996.7500 | 25986.6951 | protective_stop | -11.5549 |
| 2026-04-14 22:06:00+00:00 | 2026-04-14 22:36:00+00:00 | trend_pullback_long | us_late | 1 | 26002.2500 | 25999.5000 | max_hold | -4.2500 |
| 2026-04-14 23:35:00+00:00 | 2026-04-15 00:05:00+00:00 | trend_pullback_long | asia | 1 | 26029.5000 | 26012.7500 | max_hold | -18.2500 |
| 2026-04-15 08:03:00+00:00 | 2026-04-15 08:33:00+00:00 | trend_transition_long | europe | 1 | 26011.2500 | 26027.0000 | max_hold | 14.2500 |
| 2026-04-15 08:55:00+00:00 | 2026-04-15 09:02:00+00:00 | trend_transition_long | europe | 1 | 26032.7500 | 26022.7221 | protective_stop | -11.5279 |
| 2026-04-15 13:26:00+00:00 | 2026-04-15 13:44:00+00:00 | trend_pullback_long | europe | 1 | 26020.2500 | 25983.8747 | protective_stop | -37.8753 |
| 2026-04-15 14:15:00+00:00 | 2026-04-15 14:38:00+00:00 | trend_transition_long | us_rth | 1 | 26090.5000 | 26127.2980 | protective_stop | 35.2980 |
| 2026-04-15 14:50:00+00:00 | 2026-04-15 15:20:00+00:00 | trend_transition_long | us_rth | 1 | 26163.0000 | 26187.5000 | max_hold | 23.0000 |
| 2026-04-15 15:43:00+00:00 | 2026-04-15 16:13:00+00:00 | trend_transition_long | us_rth | 1 | 26208.2500 | 26220.0000 | max_hold | 10.2500 |
| 2026-04-15 17:27:00+00:00 | 2026-04-15 17:57:00+00:00 | trend_transition_long | us_rth | 1 | 26193.2500 | 26204.7500 | max_hold | 10.0000 |
| 2026-04-15 18:32:00+00:00 | 2026-04-15 18:39:00+00:00 | trend_transition_long | us_rth | 1 | 26259.0000 | 26269.9080 | protective_stop | 9.4080 |
| 2026-04-15 18:51:00+00:00 | 2026-04-15 19:00:00+00:00 | trend_transition_long | us_rth | 1 | 26293.2500 | 26299.0598 | protective_stop | 4.3098 |
| 2026-04-15 19:08:00+00:00 | 2026-04-15 19:14:00+00:00 | trend_transition_long | us_rth | 1 | 26321.0000 | 26306.9331 | protective_stop | -15.5669 |
| 2026-04-15 19:26:00+00:00 | 2026-04-15 19:38:00+00:00 | trend_transition_long | us_rth | 1 | 26328.7500 | 26343.6212 | protective_stop | 13.3712 |
| 2026-04-15 20:58:00+00:00 | 2026-04-15 22:00:00+00:00 | trend_transition_long | us_late | 1 | 26359.7500 | 26351.0379 | protective_stop | -10.2121 |
| 2026-04-15 22:32:00+00:00 | 2026-04-15 22:42:00+00:00 | trend_transition_long | us_late | 1 | 26379.0000 | 26381.7356 | protective_stop | 1.2356 |
| 2026-04-16 01:43:00+00:00 | 2026-04-16 01:59:00+00:00 | trend_transition_long | asia | 1 | 26454.0000 | 26441.7679 | protective_stop | -13.7321 |
| 2026-04-16 02:40:00+00:00 | 2026-04-16 02:53:00+00:00 | trend_pullback_long | asia | 1 | 26453.2500 | 26442.8845 | protective_stop | -11.8655 |
| 2026-04-16 05:52:00+00:00 | 2026-04-16 06:13:00+00:00 | trend_transition_long | asia | 1 | 26459.5000 | 26483.6246 | target | 22.6246 |
| 2026-04-16 07:38:00+00:00 | 2026-04-16 07:46:00+00:00 | trend_transition_long | europe | 1 | 26481.7500 | 26473.8218 | protective_stop | -9.4282 |
| 2026-04-16 13:03:00+00:00 | 2026-04-16 13:23:00+00:00 | trend_transition_long | europe | 1 | 26422.5000 | 26406.7316 | protective_stop | -17.2684 |
| 2026-04-16 13:30:00+00:00 | 2026-04-16 13:31:00+00:00 | trend_transition_long | europe | 1 | 26439.0000 | 26412.4735 | protective_stop | -28.0265 |
| 2026-04-16 14:46:00+00:00 | 2026-04-16 15:16:00+00:00 | trend_transition_long | us_rth | 1 | 26410.5000 | 26484.2500 | max_hold | 72.2500 |
| 2026-04-16 15:56:00+00:00 | 2026-04-16 16:26:00+00:00 | trend_pullback_long | us_rth | 1 | 26520.0000 | 26532.0000 | max_hold | 10.5000 |
| 2026-04-16 17:26:00+00:00 | 2026-04-16 17:55:00+00:00 | trend_transition_long | us_rth | 1 | 26483.5000 | 26461.1364 | protective_stop | -23.8636 |
| 2026-04-16 19:02:00+00:00 | 2026-04-16 19:12:00+00:00 | trend_transition_long | us_rth | 1 | 26459.5000 | 26434.3421 | protective_stop | -26.6579 |
| 2026-04-16 19:36:00+00:00 | 2026-04-16 20:06:00+00:00 | trend_transition_long | us_rth | 1 | 26470.2500 | 26441.8152 | protective_stop | -29.9348 |
| 2026-04-16 22:06:00+00:00 | 2026-04-16 22:36:00+00:00 | trend_pullback_long | us_late | 1 | 26477.7500 | 26483.2500 | max_hold | 4.0000 |
| 2026-04-17 00:21:00+00:00 | 2026-04-17 00:51:00+00:00 | trend_transition_long | asia | 1 | 26487.0000 | 26487.2500 | max_hold | -1.2500 |
| 2026-04-17 01:08:00+00:00 | 2026-04-17 01:23:00+00:00 | trend_pullback_long | asia | 1 | 26494.0000 | 26481.5326 | protective_stop | -13.9674 |
| 2026-04-17 04:06:00+00:00 | 2026-04-17 04:18:00+00:00 | trend_transition_long | asia | 1 | 26463.7500 | 26476.5000 | target | 11.2500 |
| 2026-04-17 05:38:00+00:00 | 2026-04-17 06:08:00+00:00 | trend_transition_long | asia | 1 | 26461.5000 | 26471.0000 | max_hold | 8.0000 |
| 2026-04-17 07:02:00+00:00 | 2026-04-17 07:32:00+00:00 | trend_transition_long | europe | 1 | 26472.2500 | 26472.0000 | max_hold | -1.7500 |
| 2026-04-17 07:45:00+00:00 | 2026-04-17 08:15:00+00:00 | trend_pullback_long | europe | 1 | 26481.7500 | 26482.7500 | max_hold | -0.5000 |
| 2026-04-17 08:42:00+00:00 | 2026-04-17 09:09:00+00:00 | trend_transition_long | europe | 1 | 26507.2500 | 26520.1760 | protective_stop | 11.4260 |
| 2026-04-17 11:18:00+00:00 | 2026-04-17 11:40:00+00:00 | trend_transition_long | europe | 1 | 26539.0000 | 26545.1124 | protective_stop | 4.6124 |
| 2026-04-17 11:51:00+00:00 | 2026-04-17 12:05:00+00:00 | trend_transition_long | europe | 1 | 26559.7500 | 26590.2827 | target | 29.0327 |
| 2026-04-17 12:31:00+00:00 | 2026-04-17 12:59:00+00:00 | trend_transition_long | europe | 1 | 26640.5000 | 26739.5580 | target | 97.5580 |
| 2026-04-17 14:32:00+00:00 | 2026-04-17 14:55:00+00:00 | trend_pullback_long | us_rth | 1 | 26768.2500 | 26825.5241 | protective_stop | 55.7741 |
| 2026-04-17 20:39:00+00:00 | 2026-04-19 22:00:00+00:00 | trend_transition_long | us_late | 1 | 26839.7500 | 26827.1279 | protective_stop | -14.1221 |
| 2026-04-20 01:02:00+00:00 | 2026-04-20 01:32:00+00:00 | trend_transition_long | asia | 1 | 26673.0000 | 26695.5000 | max_hold | 21.0000 |
| 2026-04-20 01:40:00+00:00 | 2026-04-20 02:10:00+00:00 | trend_transition_long | asia | 1 | 26704.0000 | 26693.7500 | max_hold | -11.7500 |
| 2026-04-20 06:31:00+00:00 | 2026-04-20 06:47:00+00:00 | trend_transition_long | asia | 1 | 26665.0000 | 26648.2579 | protective_stop | -18.2421 |
| 2026-04-20 06:57:00+00:00 | 2026-04-20 07:27:00+00:00 | trend_transition_long | asia | 1 | 26690.7500 | 26691.5000 | max_hold | -0.7500 |
| 2026-04-20 08:51:00+00:00 | 2026-04-20 09:00:00+00:00 | trend_transition_long | europe | 1 | 26684.7500 | 26692.8082 | protective_stop | 6.5582 |
| 2026-04-20 09:31:00+00:00 | 2026-04-20 10:01:00+00:00 | trend_pullback_long | europe | 1 | 26708.7500 | 26697.0000 | max_hold | -13.2500 |
| 2026-04-20 12:44:00+00:00 | 2026-04-20 12:50:00+00:00 | trend_pullback_long | europe | 1 | 26737.5000 | 26765.2500 | target | 26.2500 |
| 2026-04-20 13:09:00+00:00 | 2026-04-20 13:39:00+00:00 | trend_pullback_long | europe | 1 | 26781.0000 | 26747.5000 | max_hold | -35.0000 |
| 2026-04-20 16:21:00+00:00 | 2026-04-20 16:51:00+00:00 | trend_transition_long | us_rth | 1 | 26684.2500 | 26678.5000 | max_hold | -7.2500 |
| 2026-04-20 19:59:00+00:00 | 2026-04-20 20:29:00+00:00 | trend_transition_long | us_rth | 1 | 26743.0000 | 26743.5000 | max_hold | -1.0000 |
| 2026-04-20 22:06:00+00:00 | 2026-04-20 22:36:00+00:00 | trend_transition_long | us_late | 1 | 26811.2500 | 26802.5000 | max_hold | -10.2500 |
| 2026-04-21 01:30:00+00:00 | 2026-04-21 01:43:00+00:00 | trend_transition_long | asia | 1 | 26829.7500 | 26820.3243 | protective_stop | -10.9257 |
| 2026-04-21 04:25:00+00:00 | 2026-04-21 04:55:00+00:00 | trend_transition_long | asia | 1 | 26825.0000 | 26825.5000 | max_hold | -1.0000 |
| 2026-04-21 05:05:00+00:00 | 2026-04-21 05:07:00+00:00 | trend_transition_long | asia | 1 | 26832.2500 | 26836.9339 | protective_stop | 3.1839 |
| 2026-04-21 08:43:00+00:00 | 2026-04-21 08:52:00+00:00 | trend_transition_long | europe | 1 | 26836.2500 | 26844.0707 | protective_stop | 6.3207 |
| 2026-04-21 09:50:00+00:00 | 2026-04-21 09:56:00+00:00 | trend_transition_long | europe | 1 | 26833.2500 | 26838.2818 | protective_stop | 3.5318 |
| 2026-04-21 10:09:00+00:00 | 2026-04-21 10:39:00+00:00 | trend_transition_long | europe | 1 | 26852.7500 | 26860.2500 | max_hold | 6.0000 |
| 2026-04-21 18:55:00+00:00 | 2026-04-21 19:25:00+00:00 | trend_transition_long | us_rth | 1 | 26726.7500 | 26779.7500 | max_hold | 51.5000 |
| 2026-04-21 22:01:00+00:00 | 2026-04-21 22:31:00+00:00 | trend_transition_long | us_late | 1 | 26749.2500 | 26745.5000 | max_hold | -5.2500 |
| 2026-04-21 23:39:00+00:00 | 2026-04-22 00:00:00+00:00 | trend_transition_long | asia | 1 | 26755.2500 | 26780.0995 | target | 23.3495 |
| 2026-04-22 00:10:00+00:00 | 2026-04-22 00:15:00+00:00 | trend_transition_long | asia | 1 | 26791.5000 | 26798.2538 | protective_stop | 5.2538 |
| 2026-04-22 07:28:00+00:00 | 2026-04-22 07:58:00+00:00 | trend_pullback_long | europe | 1 | 26848.5000 | 26849.0000 | max_hold | -1.0000 |
| 2026-04-22 11:50:00+00:00 | 2026-04-22 12:02:00+00:00 | trend_transition_long | europe | 1 | 26829.7500 | 26849.7500 | target | 18.5000 |
| 2026-04-22 19:48:00+00:00 | 2026-04-22 19:52:00+00:00 | trend_transition_long | us_rth | 1 | 27060.2500 | 27068.1491 | protective_stop | 6.3991 |
| 2026-04-22 20:03:00+00:00 | 2026-04-22 20:33:00+00:00 | trend_transition_long | us_late | 1 | 27101.0000 | 27108.5000 | max_hold | 6.0000 |
| 2026-04-22 23:46:00+00:00 | 2026-04-23 00:00:00+00:00 | trend_pullback_long | asia | 1 | 27094.2500 | 27086.6664 | protective_stop | -9.0836 |
| 2026-04-23 04:13:00+00:00 | 2026-04-23 04:41:00+00:00 | trend_transition_long | asia | 1 | 26923.0000 | 26939.3865 | protective_stop | 14.8865 |
| 2026-04-23 05:00:00+00:00 | 2026-04-23 05:07:00+00:00 | trend_transition_long | asia | 1 | 26956.0000 | 26956.1893 | protective_stop | -1.3107 |
| 2026-04-23 13:37:00+00:00 | 2026-04-23 13:47:00+00:00 | trend_transition_long | us_rth | 1 | 27033.2500 | 27079.7500 | target | 45.0000 |
| 2026-04-23 22:01:00+00:00 | 2026-04-23 22:31:00+00:00 | trend_transition_long | us_late | 1 | 27020.2500 | 27034.7500 | max_hold | 13.0000 |
| 2026-04-23 22:49:00+00:00 | 2026-04-23 23:19:00+00:00 | trend_transition_long | us_late | 1 | 27047.2500 | 27037.2500 | max_hold | -11.5000 |
| 2026-04-24 00:01:00+00:00 | 2026-04-24 00:04:00+00:00 | trend_transition_long | asia | 1 | 27085.7500 | 27073.8341 | protective_stop | -13.4159 |
| 2026-04-24 00:31:00+00:00 | 2026-04-24 00:42:00+00:00 | trend_transition_long | asia | 1 | 27133.5000 | 27115.8456 | protective_stop | -19.1544 |
| 2026-04-24 05:16:00+00:00 | 2026-04-24 05:46:00+00:00 | trend_transition_long | asia | 1 | 27056.2500 | 27075.5000 | max_hold | 17.7500 |
| 2026-04-24 05:53:00+00:00 | 2026-04-24 06:05:00+00:00 | trend_transition_long | asia | 1 | 27084.5000 | 27090.1922 | protective_stop | 4.1922 |
| 2026-04-24 07:03:00+00:00 | 2026-04-24 07:24:00+00:00 | trend_transition_long | europe | 1 | 27092.2500 | 27097.2473 | protective_stop | 3.4973 |
| 2026-04-24 08:16:00+00:00 | 2026-04-24 08:21:00+00:00 | trend_pullback_long | europe | 1 | 27114.5000 | 27150.7500 | target | 34.7500 |
| 2026-04-24 10:04:00+00:00 | 2026-04-24 10:26:00+00:00 | trend_transition_long | europe | 1 | 27125.7500 | 27173.0743 | target | 45.8243 |
| 2026-04-24 11:05:00+00:00 | 2026-04-24 11:07:00+00:00 | trend_pullback_long | europe | 1 | 27210.5000 | 27267.7500 | target | 55.7500 |
| 2026-04-24 15:45:00+00:00 | 2026-04-24 16:15:00+00:00 | trend_pullback_long | us_rth | 1 | 27384.2500 | 27369.5000 | max_hold | -16.2500 |
| 2026-04-24 17:37:00+00:00 | 2026-04-24 17:55:00+00:00 | trend_transition_long | us_rth | 1 | 27416.7500 | 27439.1210 | protective_stop | 20.8710 |
| 2026-04-24 19:01:00+00:00 | 2026-04-24 19:23:00+00:00 | trend_pullback_long | us_rth | 1 | 27419.0000 | 27438.7281 | protective_stop | 18.2281 |
| 2026-04-24 20:32:00+00:00 | 2026-04-26 22:00:00+00:00 | trend_transition_long | us_late | 1 | 27430.5000 | 27418.6395 | protective_stop | -13.3605 |
| 2026-04-27 00:01:00+00:00 | 2026-04-27 00:31:00+00:00 | trend_transition_long | asia | 1 | 27393.0000 | 27413.0000 | max_hold | 18.5000 |
| 2026-04-27 00:41:00+00:00 | 2026-04-27 00:58:00+00:00 | trend_transition_long | asia | 1 | 27431.7500 | 27467.6577 | target | 34.4077 |
| 2026-04-27 01:30:00+00:00 | 2026-04-27 01:57:00+00:00 | trend_transition_long | asia | 1 | 27495.7500 | 27525.6639 | protective_stop | 28.4139 |
| 2026-04-27 09:18:00+00:00 | 2026-04-27 09:20:00+00:00 | trend_transition_long | europe | 1 | 27454.0000 | 27443.7834 | protective_stop | -11.7166 |
| 2026-04-27 09:32:00+00:00 | 2026-04-27 10:02:00+00:00 | trend_transition_long | europe | 1 | 27458.0000 | 27457.0000 | max_hold | -2.5000 |
| 2026-04-27 10:37:00+00:00 | 2026-04-27 10:46:00+00:00 | trend_transition_long | europe | 1 | 27465.5000 | 27471.3477 | protective_stop | 4.3477 |
| 2026-04-27 11:24:00+00:00 | 2026-04-27 11:37:00+00:00 | trend_transition_long | europe | 1 | 27496.2500 | 27482.6587 | protective_stop | -15.0913 |
| 2026-04-27 16:36:00+00:00 | 2026-04-27 16:57:00+00:00 | trend_transition_long | us_rth | 1 | 27395.7500 | 27380.9505 | protective_stop | -16.2995 |
| 2026-04-27 18:10:00+00:00 | 2026-04-27 18:40:00+00:00 | trend_pullback_long | us_rth | 1 | 27433.5000 | 27418.2500 | max_hold | -16.7500 |
| 2026-04-27 19:32:00+00:00 | 2026-04-27 19:37:00+00:00 | trend_transition_long | us_rth | 1 | 27432.2500 | 27416.3106 | protective_stop | -17.4394 |
| 2026-04-27 22:02:00+00:00 | 2026-04-27 22:06:00+00:00 | trend_transition_long | us_late | 1 | 27444.0000 | 27482.2233 | target | 36.7233 |
