# NQ Lightglow 5y Bar Backtest

## Verdict

Best positive candidate: `lightglow_premium_discount_reversal_3m_us_rth_hold6m_reverse_time` with `1591.8750` future test net points, `66.67%` positive selected folds, `1.1925` average test PF, `3` minute bars, and `6` minute holding.

This is a research result: the script approximates the Pine indicator from `docs/Strategy/lightglow.md` on OHLCV bars and uses walk-forward selection before scoring future folds.

## Data And Method

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Requested span: `2021-04-28` to `2026-04-28`.
- Loaded 1m span: `2021-04-28 00:00:00+00:00` to `2026-04-27 23:57:00+00:00`.
- 1m rows: `589,965`.
- Timeframes tested: `3m`.
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
- Sessions: `us_rth`.
- Hold bars: `2`.
- Direction modes: `reverse`.
- Exit profiles: `time`.
- Train gate: trades >= `40`, PF >= `1.03`, net > `0`.
- Test pass label: trades >= `5`, PF >= `1.0`, net > `0`.

## Output Summary

- Fold rows: `3`.
- Aggregated train-selected candidates: `1`.
- Positive aggregate candidates: `1`.
- Full-sample candidates evaluated: `1`.

## Best Positive Candidate By Timeframe

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_3m_us_rth_hold6m_reverse_time | premium_discount_reversal | 3 | us_rth | 6 | reverse | time | 3 | 0.6667 | 0.6667 | 889 | 1591.8750 | 1314.5000 | 1.2110 | 1.1925 | 0.4694 | -434.0000 |

## Positive Walk-Forward Ranking

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_3m_us_rth_hold6m_reverse_time | premium_discount_reversal | 3 | us_rth | 6 | reverse | time | 3 | 0.6667 | 0.6667 | 889 | 1591.8750 | 1314.5000 | 1.2110 | 1.1925 | 0.4694 | -434.0000 |

## Best Future Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | lightglow_premium_discount_reversal_3m_us_rth_hold6m_reverse_time | 14 | 1 | 1094 | 1482.2500 | 1.1344 | 297 | 1942.3750 | 1.6967 | 0.5118 |
| True | lightglow_premium_discount_reversal_3m_us_rth_hold6m_reverse_time | 15 | 1 | 1139 | 3093.6250 | 1.2601 | 290 | 83.5000 | 1.0221 | 0.4793 |
| False | lightglow_premium_discount_reversal_3m_us_rth_hold6m_reverse_time | 13 | 1 | 1076 | 1515.2500 | 1.1321 | 302 | -434.0000 | 0.8586 | 0.4172 |

## Full-Sample Positive Sanity Check

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | trades | net_points | profit_factor | win_rate | max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_3m_us_rth_hold6m_reverse_time | premium_discount_reversal | 3 | us_rth | 6 | reverse | time | 5811 | 120.3750 | 1.0023 | 0.4731 | 3892.5000 |
