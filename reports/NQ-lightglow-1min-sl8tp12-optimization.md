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
- Hold bars: `2`.
- Direction modes: `reverse`.
- Exit profiles: `sl8_tp12`.
- Train gate: trades >= `40`, PF >= `1.03`, net > `0`.
- Test pass label: trades >= `5`, PF >= `1.0`, net > `0`.

## Output Summary

- Fold rows: `14`.
- Aggregated train-selected candidates: `1`.
- Positive aggregate candidates: `1`.
- Full-sample candidates evaluated: `2`.

## Best Positive Candidate By Timeframe

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | premium_discount_reversal | 1 | all | 2 | reverse | time | 14 | 1.0000 | 1.0000 | 41720 | 110253.0000 | 1843.6250 | 59.8023 | 1.9592 | 0.4308 | 2125.3750 |

## Positive Walk-Forward Ranking

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | premium_discount_reversal | 1 | all | 2 | reverse | time | 14 | 1.0000 | 1.0000 | 41720 | 110253.0000 | 1843.6250 | 59.8023 | 1.9592 | 0.4308 | 2125.3750 |

## Best Future Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 10 | 1 | 12056 | 32655.0000 | 2.0612 | 3003 | 13734.6250 | 2.7645 | 0.4252 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 13 | 1 | 12157 | 38728.3750 | 1.9190 | 3078 | 12433.0000 | 2.5936 | 0.4331 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 11 | 1 | 12035 | 37835.8750 | 2.1804 | 3032 | 10176.2500 | 1.7873 | 0.4489 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 7 | 1 | 12214 | 19463.2500 | 1.7191 | 2877 | 9388.1250 | 2.4308 | 0.4244 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 14 | 1 | 12347 | 43444.8750 | 2.1013 | 2720 | 8907.5000 | 1.8623 | 0.4596 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 6 | 1 | 12049 | 17083.8750 | 1.5958 | 2948 | 8675.7500 | 2.4774 | 0.4111 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 9 | 1 | 12066 | 27179.0000 | 2.0066 | 2977 | 7828.3750 | 1.7277 | 0.4444 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 15 | 1 | 12047 | 38526.1250 | 1.9159 | 3030 | 7698.5000 | 1.5736 | 0.4663 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 8 | 1 | 12155 | 25409.1250 | 1.9551 | 2992 | 7146.2500 | 2.0594 | 0.3961 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 12 | 1 | 12218 | 38030.2500 | 2.0138 | 3055 | 7135.6250 | 1.6851 | 0.4556 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 2 | 1 | 12054 | 1862.2500 | 1.0484 | 2884 | 6221.2500 | 1.8379 | 0.4331 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 4 | 1 | 12252 | 12941.7500 | 1.3652 | 3126 | 5575.0000 | 1.8884 | 0.4015 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 3 | 1 | 12026 | 9298.2500 | 1.2420 | 2951 | 3207.3750 | 1.4606 | 0.4243 |
| True | lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | 5 | 1 | 12247 | 19191.8750 | 1.6311 | 3047 | 2125.3750 | 1.2808 | 0.4076 |

## Full-Sample Positive Sanity Check

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | trades | net_points | profit_factor | win_rate | max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | premium_discount_reversal | 1 | all | 2 | reverse | time | 60500 | 108035.7500 | 1.6196 | 0.4278 | 6558.3750 |
