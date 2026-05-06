# NQ Lightglow 5y Bar Backtest

## Verdict

Best positive candidate: `lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time` with `104031.7500` future test net points, `100.00%` positive selected folds, `1.9686` average test PF, `1` minute bars, and `2` minute holding.

This is a research result: the script approximates the Pine indicator from `docs/Strategy/lightglow.md` on OHLCV bars and uses walk-forward selection before scoring future folds.

## Data And Method

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Requested span: `2021-04-28` to `2026-04-28`.
- Loaded 1m span: `2021-04-28 00:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- 1m rows: `1,769,740`.
- Timeframes tested: `1m, 3m, 5m, 15m`.
- Continuous NQ construction: one futures row per minute, selected upstream by highest reported volume.
- Costs: one tick slippage per side plus commission from `BacktestCosts`.

## Lightglow Signals Tested

- Internal and swing BOS/CHoCH from confirmed pivot structure breaks.
- Fair value gaps, equal high/low reversals, internal/swing order block breaks.
- Premium/discount zone reversals and two confluence variants: CHoCH-zone and FVG-zone.
- Native and reverse direction variants are both tested because several SMC events can be continuation or liquidity-fade signals.

## Walk-Forward Design

- Train days: `365`; purge days: `5`; test days: `90`; step days: `90`.
- Walk-forward start: `2022-04-28`.
- Sessions: `all, us_rth, us_late`.
- Hold bars: `1, 2, 3, 5`.
- Direction modes: `native, reverse`.
- Exit profiles: `time`.
- Train gate: trades >= `40`, PF >= `1.03`, net > `0`.
- Test pass label: trades >= `5`, PF >= `1.0`, net > `0`.

## Output Summary

- Fold rows: `400`.
- Aggregated train-selected candidates: `159`.
- Positive aggregate candidates: `79`.
- Full-sample candidates evaluated: `1,056`.

## Best Positive Candidate By Timeframe

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | premium_discount_reversal | 1 | all | 2 | reverse | time | 13 | 1.0000 | 1.0000 | 38836 | 104031.7500 | 1843.6250 | 56.4278 | 1.9686 | 0.4306 | 2125.3750 |
| lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | premium_discount_reversal | 3 | all | 3 | reverse | time | 13 | 1.0000 | 1.0000 | 12728 | 40213.5000 | 1205.5000 | 33.3584 | 1.8652 | 0.4453 | 1011.5000 |
| lightglow_premium_discount_reversal_5m_all_hold5m_reverse_time | premium_discount_reversal | 5 | all | 5 | reverse | time | 9 | 1.0000 | 1.0000 | 5255 | 11685.3750 | 646.0000 | 18.0888 | 1.3976 | 0.4643 | 462.3750 |
| lightglow_internal_ob_break_15m_us_late_hold45m_native_time | internal_ob_break | 15 | us_late | 45 | native | time | 4 | 1.0000 | 1.0000 | 52 | 534.5000 | 64.8750 | 8.2389 | 2.9475 | 0.5885 | 86.7500 |

## Positive Walk-Forward Ranking

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | premium_discount_reversal | 1 | all | 2 | reverse | time | 13 | 1.0000 | 1.0000 | 38836 | 104031.7500 | 1843.6250 | 56.4278 | 1.9686 | 0.4306 | 2125.3750 |
| lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | premium_discount_reversal | 1 | all | 3 | reverse | time | 13 | 1.0000 | 1.0000 | 35568 | 93805.5000 | 1527.5000 | 61.4111 | 1.7735 | 0.4446 | 731.1250 |
| lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | premium_discount_reversal | 1 | all | 5 | reverse | time | 13 | 1.0000 | 1.0000 | 30948 | 67863.7500 | 1800.1250 | 37.6995 | 1.5134 | 0.4534 | 1864.3750 |
| lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | premium_discount_reversal | 3 | all | 3 | reverse | time | 13 | 1.0000 | 1.0000 | 12728 | 40213.5000 | 1205.5000 | 33.3584 | 1.8652 | 0.4453 | 1011.5000 |
| lightglow_premium_discount_reversal_3m_all_hold6m_reverse_time | premium_discount_reversal | 3 | all | 6 | reverse | time | 12 | 1.0000 | 1.0000 | 11466 | 32036.5000 | 1594.5000 | 20.0919 | 1.5345 | 0.4556 | 672.2500 |
| lightglow_premium_discount_reversal_3m_all_hold9m_reverse_time | premium_discount_reversal | 3 | all | 9 | reverse | time | 11 | 1.0000 | 1.0000 | 9499 | 26589.3750 | 1107.1250 | 24.0166 | 1.4225 | 0.4691 | 601.7500 |
| lightglow_premium_discount_reversal_5m_all_hold5m_reverse_time | premium_discount_reversal | 5 | all | 5 | reverse | time | 9 | 1.0000 | 1.0000 | 5255 | 11685.3750 | 646.0000 | 18.0888 | 1.3976 | 0.4643 | 462.3750 |
| lightglow_premium_discount_reversal_3m_all_hold15m_reverse_time | premium_discount_reversal | 3 | all | 15 | reverse | time | 8 | 1.0000 | 1.0000 | 5978 | 14868.2500 | 1450.1250 | 10.2531 | 1.2618 | 0.4705 | 136.7500 |
| lightglow_premium_discount_reversal_5m_all_hold15m_reverse_time | premium_discount_reversal | 5 | all | 15 | reverse | time | 11 | 0.8182 | 0.8182 | 5756 | 14091.7500 | 1197.5000 | 11.7676 | 1.3112 | 0.4728 | -649.3750 |
| lightglow_premium_discount_reversal_1m_us_late_hold2m_reverse_time | premium_discount_reversal | 1 | us_late | 2 | reverse | time | 12 | 0.8333 | 0.8333 | 2550 | 5635.2500 | 307.3750 | 18.3335 | 1.7350 | 0.4292 | -144.8750 |
| lightglow_premium_discount_reversal_1m_us_late_hold3m_reverse_time | premium_discount_reversal | 1 | us_late | 3 | reverse | time | 13 | 0.7692 | 0.7692 | 2565 | 6018.6250 | 347.7500 | 17.3073 | 1.6718 | 0.4459 | -315.0000 |
| lightglow_premium_discount_reversal_1m_us_late_hold5m_reverse_time | premium_discount_reversal | 1 | us_late | 5 | reverse | time | 8 | 0.8750 | 0.8750 | 1414 | 2566.5000 | 332.7500 | 7.7130 | 1.4437 | 0.4600 | -290.7500 |
| lightglow_premium_discount_reversal_5m_all_hold10m_reverse_time | premium_discount_reversal | 5 | all | 10 | reverse | time | 4 | 0.7500 | 0.7500 | 2268 | 6217.7500 | 1334.1250 | 4.6605 | 1.3727 | 0.4953 | -180.1250 |
| lightglow_premium_discount_reversal_5m_all_hold25m_reverse_time | premium_discount_reversal | 5 | all | 25 | reverse | time | 7 | 0.7143 | 0.7143 | 3169 | 3876.1250 | 995.0000 | 3.8956 | 1.1388 | 0.4743 | -172.6250 |
| lightglow_internal_ob_break_15m_us_late_hold45m_native_time | internal_ob_break | 15 | us_late | 45 | native | time | 4 | 1.0000 | 1.0000 | 52 | 534.5000 | 64.8750 | 8.2389 | 2.9475 | 0.5885 | 86.7500 |
| lightglow_premium_discount_reversal_3m_us_late_hold3m_reverse_time | premium_discount_reversal | 3 | us_late | 3 | reverse | time | 7 | 0.7143 | 0.7143 | 594 | 1274.7500 | 359.3750 | 3.5471 | 1.5945 | 0.4506 | -336.2500 |
| lightglow_premium_discount_reversal_15m_all_hold75m_reverse_time | premium_discount_reversal | 15 | all | 75 | reverse | time | 5 | 0.8000 | 0.8000 | 732 | 2368.0000 | 1147.7500 | 2.0632 | 1.2699 | 0.4998 | -557.5000 |
| lightglow_premium_discount_reversal_3m_us_late_hold6m_reverse_time | premium_discount_reversal | 3 | us_late | 6 | reverse | time | 7 | 0.8571 | 0.8571 | 582 | 813.0000 | 457.2500 | 1.7780 | 1.4256 | 0.4846 | -457.6250 |
| lightglow_premium_discount_reversal_15m_us_late_hold30m_reverse_time | premium_discount_reversal | 15 | us_late | 30 | reverse | time | 5 | 0.8000 | 0.8000 | 230 | 371.7500 | 244.3750 | 1.5212 | 1.5012 | 0.4892 | -251.3750 |
| lightglow_internal_ob_break_15m_us_late_hold15m_native_time | internal_ob_break | 15 | us_late | 15 | native | time | 4 | 0.7500 | 0.7500 | 61 | 147.6250 | 98.0000 | 1.5064 | 2.1314 | 0.4540 | -37.3750 |
| lightglow_internal_ob_break_5m_us_late_hold25m_native_time | internal_ob_break | 5 | us_late | 25 | native | time | 3 | 0.6667 | 0.6667 | 130 | 333.5000 | 241.5000 | 1.3810 | 1.7356 | 0.4211 | -164.1250 |
| lightglow_internal_ob_break_15m_us_late_hold30m_native_time | internal_ob_break | 15 | us_late | 30 | native | time | 4 | 0.5000 | 0.5000 | 60 | 227.0000 | 136.2500 | 1.6661 | 2.9827 | 0.4974 | -108.6250 |
| lightglow_swing_bos_5m_all_hold25m_native_time | swing_bos | 5 | all | 25 | native | time | 3 | 0.6667 | 0.6667 | 128 | 363.0000 | 418.1250 | 0.8682 | 1.4010 | 0.5085 | -62.7500 |
| lightglow_internal_bos_1m_us_late_hold3m_native_time | internal_bos | 1 | us_late | 3 | native | time | 4 | 0.5000 | 0.5000 | 706 | 264.7500 | 244.7500 | 1.0817 | 1.1816 | 0.4123 | -235.3750 |
| lightglow_internal_ob_break_15m_us_rth_hold75m_native_time | internal_ob_break | 15 | us_rth | 75 | native | time | 4 | 0.7500 | 0.7500 | 402 | 411.5000 | 1715.5000 | 0.2399 | 1.0966 | 0.5162 | -1156.6250 |
| lightglow_swing_choch_3m_all_hold15m_native_time | swing_choch | 3 | all | 15 | native | time | 3 | 0.6667 | 0.6667 | 738 | 304.7500 | 531.0000 | 0.5739 | 1.0560 | 0.4472 | -72.3750 |
| lightglow_swing_ob_break_1m_us_late_hold5m_native_time | swing_ob_break | 1 | us_late | 5 | native | time | 3 | 0.6667 | 0.6667 | 101 | 109.8750 | 106.0000 | 1.0366 | 1.3163 | 0.4709 | -23.6250 |
| lightglow_premium_discount_reversal_15m_all_hold45m_reverse_time | premium_discount_reversal | 15 | all | 45 | reverse | time | 3 | 0.6667 | 0.6667 | 548 | 220.7500 | 1110.8750 | 0.1987 | 1.1269 | 0.4778 | -806.3750 |
| lightglow_fvg_3m_us_late_hold15m_reverse_time | fvg | 3 | us_late | 15 | reverse | time | 3 | 0.6667 | 0.6667 | 188 | 107.0000 | 640.8750 | 0.1670 | 1.0630 | 0.5217 | -55.0000 |
| lightglow_premium_discount_reversal_3m_us_late_hold15m_reverse_time | premium_discount_reversal | 3 | us_late | 15 | reverse | time | 3 | 1.0000 | 1.0000 | 206 | 88.5000 | 558.3750 | 0.1585 | 1.0566 | 0.5118 | 0.1250 |

## Best Future Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 10 | 2 | 11015 | 28851.6250 | 1.8870 | 2750 | 14327.5000 | 2.6286 | 0.4556 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 10 | 1 | 12056 | 32655.0000 | 2.0612 | 3003 | 13734.6250 | 2.7645 | 0.4252 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 13 | 2 | 12157 | 38728.3750 | 1.9190 | 3078 | 12433.0000 | 2.5936 | 0.4331 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 11 | 1 | 11001 | 39236.6250 | 2.1458 | 2776 | 11477.2500 | 1.8504 | 0.4694 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 9 | 5 | 11059 | 18174.3750 | 1.6265 | 2721 | 11406.8750 | 2.0300 | 0.4653 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 11 | 2 | 12035 | 37835.8750 | 2.1804 | 3032 | 10176.2500 | 1.7873 | 0.4489 |
| True | lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | 10 | 3 | 9604 | 23169.5000 | 1.6438 | 2396 | 9834.7500 | 1.9790 | 0.4449 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 7 | 2 | 12214 | 19463.2500 | 1.7191 | 2877 | 9388.1250 | 2.4308 | 0.4244 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 13 | 1 | 11101 | 42699.1250 | 1.9584 | 2809 | 8912.8750 | 2.0392 | 0.4425 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 14 | 3 | 12347 | 43444.8750 | 2.1013 | 2720 | 8907.5000 | 1.8623 | 0.4596 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 6 | 2 | 12049 | 17083.8750 | 1.5958 | 2948 | 8675.7500 | 2.4774 | 0.4111 |
| True | lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | 9 | 4 | 9647 | 16837.6250 | 1.5300 | 2371 | 8506.8750 | 1.6893 | 0.4791 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 14 | 2 | 11269 | 40269.6250 | 1.9509 | 2484 | 8294.5000 | 1.7243 | 0.4610 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 7 | 7 | 11220 | 12925.7500 | 1.4471 | 2639 | 7983.1250 | 2.1088 | 0.4422 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 9 | 1 | 12066 | 27179.0000 | 2.0066 | 2977 | 7828.3750 | 1.7277 | 0.4444 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 15 | 2 | 12047 | 38526.1250 | 1.9159 | 3030 | 7698.5000 | 1.5736 | 0.4663 |
| True | lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | 14 | 7 | 9813 | 24741.1250 | 1.5184 | 2181 | 7539.6250 | 1.6075 | 0.4649 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 15 | 3 | 10993 | 33917.1250 | 1.7473 | 2797 | 7288.1250 | 1.4934 | 0.4798 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 8 | 2 | 12155 | 25409.1250 | 1.9551 | 2992 | 7146.2500 | 2.0594 | 0.3961 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 12 | 2 | 12218 | 38030.2500 | 2.0138 | 3055 | 7135.6250 | 1.6851 | 0.4556 |
| True | lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | 11 | 3 | 9563 | 29032.3750 | 1.7597 | 2410 | 6867.7500 | 1.4580 | 0.4859 |
| True | lightglow_premium_discount_reversal_3m_all_hold9m_reverse_time | 11 | 8 | 3490 | 8439.0000 | 1.4078 | 851 | 6641.1250 | 1.8765 | 0.5112 |
| True | lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | 7 | 5 | 9782 | 10969.0000 | 1.3477 | 2281 | 6485.6250 | 1.7996 | 0.4564 |
| True | lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | 13 | 4 | 9654 | 27104.7500 | 1.5407 | 2454 | 5965.5000 | 1.6202 | 0.4446 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 4 | 7 | 12252 | 12941.7500 | 1.3652 | 3126 | 5575.0000 | 1.8884 | 0.4015 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 12 | 1 | 11183 | 41916.1250 | 2.0512 | 2768 | 5546.5000 | 1.5058 | 0.4552 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 8 | 5 | 11147 | 17174.3750 | 1.5987 | 2733 | 5546.1250 | 1.7693 | 0.4299 |
| True | lightglow_premium_discount_reversal_3m_all_hold6m_reverse_time | 14 | 10 | 3767 | 14815.1250 | 1.6420 | 926 | 5102.2500 | 1.9024 | 0.4730 |
| True | lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | 9 | 3 | 4015 | 10183.3750 | 1.8815 | 946 | 5034.5000 | 2.1449 | 0.4619 |
| True | lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | 15 | 8 | 9602 | 22204.2500 | 1.4384 | 2394 | 4886.2500 | 1.2949 | 0.4875 |

## Full-Sample Positive Sanity Check

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | trades | net_points | profit_factor | win_rate | max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | premium_discount_reversal | 3 | all | 3 | reverse | time | 19747 | 41108.8750 | 1.5550 | 0.4417 | 2492.1250 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | premium_discount_reversal | 1 | all | 2 | reverse | time | 60500 | 108035.7500 | 1.6196 | 0.4278 | 6558.3750 |
| lightglow_premium_discount_reversal_1m_us_late_hold3m_reverse_time | premium_discount_reversal | 1 | us_late | 3 | reverse | time | 3986 | 7837.0000 | 1.5505 | 0.4388 | 521.1250 |
| lightglow_premium_discount_reversal_1m_us_late_hold2m_reverse_time | premium_discount_reversal | 1 | us_late | 2 | reverse | time | 4293 | 9194.6250 | 1.7122 | 0.4384 | 628.2500 |
| lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | premium_discount_reversal | 1 | all | 3 | reverse | time | 55504 | 95878.2500 | 1.5073 | 0.4392 | 6597.0000 |
| lightglow_premium_discount_reversal_1m_us_late_hold5m_reverse_time | premium_discount_reversal | 1 | us_late | 5 | reverse | time | 3593 | 6621.1250 | 1.4166 | 0.4581 | 518.8750 |
| lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | premium_discount_reversal | 1 | all | 5 | reverse | time | 48347 | 70132.1250 | 1.3357 | 0.4498 | 6396.1250 |
| lightglow_premium_discount_reversal_3m_all_hold6m_reverse_time | premium_discount_reversal | 3 | all | 6 | reverse | time | 19451 | 33918.6250 | 1.3353 | 0.4507 | 3171.5000 |
| lightglow_premium_discount_reversal_5m_all_hold25m_reverse_time | premium_discount_reversal | 5 | all | 25 | reverse | time | 9259 | 11690.3750 | 1.1240 | 0.4765 | 1374.6250 |
| lightglow_premium_discount_reversal_5m_all_hold10m_reverse_time | premium_discount_reversal | 5 | all | 10 | reverse | time | 11708 | 15216.7500 | 1.1948 | 0.4691 | 1763.6250 |
| lightglow_premium_discount_reversal_5m_all_hold5m_reverse_time | premium_discount_reversal | 5 | all | 5 | reverse | time | 11949 | 14340.8750 | 1.2419 | 0.4584 | 1726.3750 |
| lightglow_premium_discount_reversal_3m_all_hold15m_reverse_time | premium_discount_reversal | 3 | all | 15 | reverse | time | 15519 | 23628.8750 | 1.1927 | 0.4730 | 2923.3750 |
| lightglow_premium_discount_reversal_5m_all_hold15m_reverse_time | premium_discount_reversal | 5 | all | 15 | reverse | time | 10745 | 16840.6250 | 1.1954 | 0.4672 | 2169.8750 |
| lightglow_premium_discount_reversal_3m_all_hold9m_reverse_time | premium_discount_reversal | 3 | all | 9 | reverse | time | 17869 | 29153.3750 | 1.2603 | 0.4628 | 3896.8750 |
| lightglow_swing_ob_break_1m_us_late_hold5m_native_time | swing_ob_break | 1 | us_late | 5 | native | time | 771 | 1978.3750 | 1.3678 | 0.4981 | 308.8750 |
| lightglow_internal_bos_15m_us_rth_hold75m_native_time | internal_bos | 15 | us_rth | 75 | native | time | 742 | 5428.2500 | 1.3652 | 0.5202 | 880.1250 |
| lightglow_swing_bos_1m_us_late_hold2m_native_time | swing_bos | 1 | us_late | 2 | native | time | 345 | 800.8750 | 1.7092 | 0.4841 | 144.1250 |
| lightglow_fvg_15m_us_late_hold75m_native_time | fvg | 15 | us_late | 75 | native | time | 536 | 4219.0000 | 1.4924 | 0.5056 | 926.3750 |
| lightglow_swing_bos_5m_all_hold25m_native_time | swing_bos | 5 | all | 25 | native | time | 914 | 2695.2500 | 1.3335 | 0.4781 | 502.3750 |
| lightglow_swing_bos_1m_us_late_hold3m_native_time | swing_bos | 1 | us_late | 3 | native | time | 343 | 662.8750 | 1.5824 | 0.5277 | 153.3750 |
