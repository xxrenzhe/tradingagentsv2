# NQ Lightglow Indicator-Only Ranking

## Scope

This report only ranks signals derived from `docs/Strategy/lightglow.md`: structure breaks, FVG, equal levels, order-block breaks, premium/discount zones, and Lightglow confluence variants.

It deliberately excludes external overlays such as daily stops, trade caps, event windows, volatility filters, and execution-cost stress tests.

- Source aggregate: `.tmp/nq-lightglow-5y-walkforward-aggregate.csv`.
- Signals: `internal_bos, internal_choch, swing_bos, swing_choch, fvg, equal_level_reversal, internal_ob_break, swing_ob_break, premium_discount_reversal, internal_choch_zone, fvg_zone`.
- Stable filter: selected folds >= `3`, positive fold rate >= `50.00%`, trades >= `100`, net > `0`.

## Top Indicator-Only Candidates

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | min_test_net_points | indicator_only_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | premium_discount_reversal | 1 | all | 2 | reverse | time | 13 | 1.0000 | 38836 | 104031.7500 | 1843.6250 | 56.4278 | 1.9686 | 2125.3750 | 204.3960 |
| lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | premium_discount_reversal | 1 | all | 3 | reverse | time | 13 | 1.0000 | 35568 | 93805.5000 | 1527.5000 | 61.4111 | 1.7735 | 731.1250 | 194.4137 |
| lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | premium_discount_reversal | 1 | all | 5 | reverse | time | 13 | 1.0000 | 30948 | 67863.7500 | 1800.1250 | 37.6995 | 1.5134 | 1864.3750 | 144.4257 |
| lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | premium_discount_reversal | 3 | all | 3 | reverse | time | 13 | 1.0000 | 12728 | 40213.5000 | 1205.5000 | 33.3584 | 1.8652 | 1011.5000 | 114.2470 |
| lightglow_premium_discount_reversal_3m_all_hold6m_reverse_time | premium_discount_reversal | 3 | all | 6 | reverse | time | 12 | 1.0000 | 11466 | 32036.5000 | 1594.5000 | 20.0919 | 1.5345 | 672.2500 | 88.8175 |
| lightglow_premium_discount_reversal_3m_all_hold9m_reverse_time | premium_discount_reversal | 3 | all | 9 | reverse | time | 11 | 1.0000 | 9499 | 26589.3750 | 1107.1250 | 24.0166 | 1.4225 | 601.7500 | 86.0345 |
| lightglow_premium_discount_reversal_5m_all_hold5m_reverse_time | premium_discount_reversal | 5 | all | 5 | reverse | time | 9 | 1.0000 | 5255 | 11685.3750 | 646.0000 | 18.0888 | 1.3976 | 462.3750 | 64.6745 |
| lightglow_premium_discount_reversal_3m_all_hold15m_reverse_time | premium_discount_reversal | 3 | all | 15 | reverse | time | 8 | 1.0000 | 5978 | 14868.2500 | 1450.1250 | 10.2531 | 1.2618 | 136.7500 | 58.0126 |
| lightglow_premium_discount_reversal_1m_us_late_hold2m_reverse_time | premium_discount_reversal | 1 | us_late | 2 | reverse | time | 12 | 0.8333 | 2550 | 5635.2500 | 307.3750 | 18.3335 | 1.7350 | -144.8750 | 57.9853 |
| lightglow_premium_discount_reversal_1m_us_late_hold3m_reverse_time | premium_discount_reversal | 1 | us_late | 3 | reverse | time | 13 | 0.7692 | 2565 | 6018.6250 | 347.7500 | 17.3073 | 1.6718 | -315.0000 | 55.4288 |
| lightglow_premium_discount_reversal_5m_all_hold15m_reverse_time | premium_discount_reversal | 5 | all | 15 | reverse | time | 11 | 0.8182 | 5756 | 14091.7500 | 1197.5000 | 11.7676 | 1.3112 | -649.3750 | 55.3349 |
| lightglow_premium_discount_reversal_1m_us_late_hold5m_reverse_time | premium_discount_reversal | 1 | us_late | 5 | reverse | time | 8 | 0.8750 | 1414 | 2566.5000 | 332.7500 | 7.7130 | 1.4437 | -290.7500 | 42.2163 |
| lightglow_premium_discount_reversal_5m_all_hold10m_reverse_time | premium_discount_reversal | 5 | all | 10 | reverse | time | 4 | 0.7500 | 2268 | 6217.7500 | 1334.1250 | 4.6605 | 1.3727 | -180.1250 | 39.6053 |
| lightglow_premium_discount_reversal_3m_us_late_hold3m_reverse_time | premium_discount_reversal | 3 | us_late | 3 | reverse | time | 7 | 0.7143 | 594 | 1274.7500 | 359.3750 | 3.5471 | 1.5945 | -336.2500 | 35.0529 |
| lightglow_premium_discount_reversal_3m_us_late_hold6m_reverse_time | premium_discount_reversal | 3 | us_late | 6 | reverse | time | 7 | 0.8571 | 582 | 813.0000 | 457.2500 | 1.7780 | 1.4256 | -457.6250 | 33.9898 |
| lightglow_premium_discount_reversal_5m_all_hold25m_reverse_time | premium_discount_reversal | 5 | all | 25 | reverse | time | 7 | 0.7143 | 3169 | 3876.1250 | 995.0000 | 3.8956 | 1.1388 | -172.6250 | 33.4454 |
| lightglow_premium_discount_reversal_15m_all_hold75m_reverse_time | premium_discount_reversal | 15 | all | 75 | reverse | time | 5 | 0.8000 | 732 | 2368.0000 | 1147.7500 | 2.0632 | 1.2699 | -557.5000 | 33.1304 |
| lightglow_premium_discount_reversal_15m_us_late_hold30m_reverse_time | premium_discount_reversal | 15 | us_late | 30 | reverse | time | 5 | 0.8000 | 230 | 371.7500 | 244.3750 | 1.5212 | 1.5012 | -251.3750 | 32.9053 |
| lightglow_internal_ob_break_5m_us_late_hold25m_native_time | internal_ob_break | 5 | us_late | 25 | native | time | 3 | 0.6667 | 130 | 333.5000 | 241.5000 | 1.3810 | 1.7356 | -164.1250 | 32.4041 |
| lightglow_premium_discount_reversal_3m_us_late_hold15m_reverse_time | premium_discount_reversal | 3 | us_late | 15 | reverse | time | 3 | 1.0000 | 206 | 88.5000 | 558.3750 | 0.1585 | 1.0566 | 0.1250 | 30.8136 |
| lightglow_swing_bos_5m_all_hold25m_native_time | swing_bos | 5 | all | 25 | native | time | 3 | 0.6667 | 128 | 363.0000 | 418.1250 | 0.8682 | 1.4010 | -62.7500 | 28.5749 |
| lightglow_swing_ob_break_1m_us_late_hold5m_native_time | swing_ob_break | 1 | us_late | 5 | native | time | 3 | 0.6667 | 101 | 109.8750 | 106.0000 | 1.0366 | 1.3163 | -23.6250 | 27.6432 |
| lightglow_internal_ob_break_15m_us_rth_hold75m_native_time | internal_ob_break | 15 | us_rth | 75 | native | time | 4 | 0.7500 | 402 | 411.5000 | 1715.5000 | 0.2399 | 1.0966 | -1156.6250 | 26.6170 |
| lightglow_premium_discount_reversal_15m_us_late_hold15m_reverse_time | premium_discount_reversal | 15 | us_late | 15 | reverse | time | 3 | 0.6667 | 142 | 10.0000 | 244.7500 | 0.0409 | 1.2214 | -97.5000 | 25.5979 |
| lightglow_premium_discount_reversal_15m_all_hold45m_reverse_time | premium_discount_reversal | 15 | all | 45 | reverse | time | 3 | 0.6667 | 548 | 220.7500 | 1110.8750 | 0.1987 | 1.1269 | -806.3750 | 25.0222 |
| lightglow_swing_choch_3m_all_hold15m_native_time | swing_choch | 3 | all | 15 | native | time | 3 | 0.6667 | 738 | 304.7500 | 531.0000 | 0.5739 | 1.0560 | -72.3750 | 24.7720 |
| lightglow_fvg_3m_us_late_hold15m_reverse_time | fvg | 3 | us_late | 15 | reverse | time | 3 | 0.6667 | 188 | 107.0000 | 640.8750 | 0.1670 | 1.0630 | -55.0000 | 24.2371 |
| lightglow_internal_bos_1m_us_late_hold3m_native_time | internal_bos | 1 | us_late | 3 | native | time | 4 | 0.5000 | 706 | 264.7500 | 244.7500 | 1.0817 | 1.1816 | -235.3750 | 23.1628 |

## Best Candidate By Lightglow Signal

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | min_test_net_points | indicator_only_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | premium_discount_reversal | 1 | all | 2 | reverse | time | 13 | 1.0000 | 38836 | 104031.7500 | 1843.6250 | 56.4278 | 1.9686 | 2125.3750 | 204.3960 |
| lightglow_internal_ob_break_5m_us_late_hold25m_native_time | internal_ob_break | 5 | us_late | 25 | native | time | 3 | 0.6667 | 130 | 333.5000 | 241.5000 | 1.3810 | 1.7356 | -164.1250 | 32.4041 |
| lightglow_swing_bos_5m_all_hold25m_native_time | swing_bos | 5 | all | 25 | native | time | 3 | 0.6667 | 128 | 363.0000 | 418.1250 | 0.8682 | 1.4010 | -62.7500 | 28.5749 |
| lightglow_swing_ob_break_1m_us_late_hold5m_native_time | swing_ob_break | 1 | us_late | 5 | native | time | 3 | 0.6667 | 101 | 109.8750 | 106.0000 | 1.0366 | 1.3163 | -23.6250 | 27.6432 |
| lightglow_swing_choch_3m_all_hold15m_native_time | swing_choch | 3 | all | 15 | native | time | 3 | 0.6667 | 738 | 304.7500 | 531.0000 | 0.5739 | 1.0560 | -72.3750 | 24.7720 |
| lightglow_fvg_3m_us_late_hold15m_reverse_time | fvg | 3 | us_late | 15 | reverse | time | 3 | 0.6667 | 188 | 107.0000 | 640.8750 | 0.1670 | 1.0630 | -55.0000 | 24.2371 |
| lightglow_internal_bos_1m_us_late_hold3m_native_time | internal_bos | 1 | us_late | 3 | native | time | 4 | 0.5000 | 706 | 264.7500 | 244.7500 | 1.0817 | 1.1816 | -235.3750 | 23.1628 |

## Practical Reading

- The ranking is a Lightglow-only research view, not a production readiness gate.
- If an entry/exit profile is shown, it is part of the Lightglow backtest parameterization, not an external overlay.
- The current strongest signal family is the premium/discount zone reversal used in reverse direction.
