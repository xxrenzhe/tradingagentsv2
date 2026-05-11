# NQ Lightglow 5y Bar Backtest

## Verdict

Best positive candidate: `lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time` with `110253.0000` future test net points, `100.00%` positive selected folds, `1.9592` average test PF, `1` minute bars, and `2` minute holding.

This is a research result: the script approximates the Pine indicator from `docs/Strategy/lightglow.md` on OHLCV bars and uses walk-forward selection before scoring future folds.

## Data And Method

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Requested span: `2021-04-28` to `2026-04-28`.
- Loaded 1m span: `2021-04-28 00:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- 1m rows: `1,769,740`.
- Timeframes tested: `1m`.
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
- Sessions: `all`.
- Hold bars: `2, 3, 5`.
- Direction modes: `reverse`.
- Exit profiles: `sl8_tp16, sl12_tp24, sl16_tp32, sl20_tp40, sl24_tp48`.
- Train gate: trades >= `40`, PF >= `1.03`, net > `0`.
- Test pass label: trades >= `5`, PF >= `1.0`, net > `0`.

## Output Summary

- Fold rows: `40`.
- Aggregated train-selected candidates: `3`.
- Positive aggregate candidates: `3`.
- Full-sample candidates evaluated: `18`.

## Best Positive Candidate By Timeframe

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | premium_discount_reversal | 1 | all | 2 | reverse | time | 14 | 1.0000 | 1.0000 | 41720 | 110253.0000 | 1843.6250 | 59.8023 | 1.9592 | 0.4308 | 2125.3750 |

## Positive Walk-Forward Ranking

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | premium_discount_reversal | 1 | all | 2 | reverse | time | 14 | 1.0000 | 1.0000 | 41720 | 110253.0000 | 1843.6250 | 59.8023 | 1.9592 | 0.4308 | 2125.3750 |
| lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | premium_discount_reversal | 1 | all | 3 | reverse | time | 13 | 1.0000 | 1.0000 | 35568 | 93805.5000 | 1527.5000 | 61.4111 | 1.7735 | 0.4446 | 731.1250 |
| lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | premium_discount_reversal | 1 | all | 5 | reverse | time | 13 | 1.0000 | 1.0000 | 30948 | 67863.7500 | 1800.1250 | 37.6995 | 1.5134 | 0.4534 | 1864.3750 |

## Best Future Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 10 | 2 | 11015 | 28851.6250 | 1.8870 | 2750 | 14327.5000 | 2.6286 | 0.4556 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 10 | 1 | 12056 | 32655.0000 | 2.0612 | 3003 | 13734.6250 | 2.7645 | 0.4252 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 13 | 2 | 12157 | 38728.3750 | 1.9190 | 3078 | 12433.0000 | 2.5936 | 0.4331 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 11 | 1 | 11001 | 39236.6250 | 2.1458 | 2776 | 11477.2500 | 1.8504 | 0.4694 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 9 | 3 | 11059 | 18174.3750 | 1.6265 | 2721 | 11406.8750 | 2.0300 | 0.4653 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 11 | 2 | 12035 | 37835.8750 | 2.1804 | 3032 | 10176.2500 | 1.7873 | 0.4489 |
| True | lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | 10 | 3 | 9604 | 23169.5000 | 1.6438 | 2396 | 9834.7500 | 1.9790 | 0.4449 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 7 | 1 | 12214 | 19463.2500 | 1.7191 | 2877 | 9388.1250 | 2.4308 | 0.4244 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 13 | 1 | 11101 | 42699.1250 | 1.9584 | 2809 | 8912.8750 | 2.0392 | 0.4425 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 14 | 2 | 12347 | 43444.8750 | 2.1013 | 2720 | 8907.5000 | 1.8623 | 0.4596 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 6 | 1 | 12049 | 17083.8750 | 1.5958 | 2948 | 8675.7500 | 2.4774 | 0.4111 |
| True | lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | 9 | 2 | 9647 | 16837.6250 | 1.5300 | 2371 | 8506.8750 | 1.6893 | 0.4791 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 14 | 1 | 11269 | 40269.6250 | 1.9509 | 2484 | 8294.5000 | 1.7243 | 0.4610 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 7 | 3 | 11220 | 12925.7500 | 1.4471 | 2639 | 7983.1250 | 2.1088 | 0.4422 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 9 | 1 | 12066 | 27179.0000 | 2.0066 | 2977 | 7828.3750 | 1.7277 | 0.4444 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 15 | 1 | 12047 | 38526.1250 | 1.9159 | 3030 | 7698.5000 | 1.5736 | 0.4663 |
| True | lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | 14 | 3 | 9813 | 24741.1250 | 1.5184 | 2181 | 7539.6250 | 1.6075 | 0.4649 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 15 | 2 | 10993 | 33917.1250 | 1.7473 | 2797 | 7288.1250 | 1.4934 | 0.4798 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 8 | 1 | 12155 | 25409.1250 | 1.9551 | 2992 | 7146.2500 | 2.0594 | 0.3961 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 12 | 2 | 12218 | 38030.2500 | 2.0138 | 3055 | 7135.6250 | 1.6851 | 0.4556 |
| True | lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | 11 | 3 | 9563 | 29032.3750 | 1.7597 | 2410 | 6867.7500 | 1.4580 | 0.4859 |
| True | lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | 7 | 2 | 9782 | 10969.0000 | 1.3477 | 2281 | 6485.6250 | 1.7996 | 0.4564 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 2 | 1 | 12054 | 1862.2500 | 1.0484 | 2884 | 6221.2500 | 1.8379 | 0.4331 |
| True | lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | 13 | 3 | 9654 | 27104.7500 | 1.5407 | 2454 | 5965.5000 | 1.6202 | 0.4446 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 4 | 3 | 12252 | 12941.7500 | 1.3652 | 3126 | 5575.0000 | 1.8884 | 0.4015 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 12 | 1 | 11183 | 41916.1250 | 2.0512 | 2768 | 5546.5000 | 1.5058 | 0.4552 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 8 | 3 | 11147 | 17174.3750 | 1.5987 | 2733 | 5546.1250 | 1.7693 | 0.4299 |
| True | lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | 15 | 3 | 9602 | 22204.2500 | 1.4384 | 2394 | 4886.2500 | 1.2949 | 0.4875 |
| True | lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | 4 | 2 | 11236 | 11590.0000 | 1.3031 | 2877 | 4865.3750 | 1.7206 | 0.4178 |
| True | lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | 8 | 2 | 9714 | 15623.7500 | 1.4974 | 2376 | 4509.5000 | 1.5856 | 0.4200 |

## Full-Sample Positive Sanity Check

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | trades | net_points | profit_factor | win_rate | max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | premium_discount_reversal | 1 | all | 2 | reverse | time | 60500 | 108035.7500 | 1.6196 | 0.4278 | 6558.3750 |
| lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | premium_discount_reversal | 1 | all | 3 | reverse | time | 55504 | 95878.2500 | 1.5073 | 0.4392 | 6597.0000 |
| lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | premium_discount_reversal | 1 | all | 5 | reverse | time | 48347 | 70132.1250 | 1.3357 | 0.4498 | 6396.1250 |
