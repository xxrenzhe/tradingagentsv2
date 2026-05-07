# NQ Lightglow 5y Bar Backtest

## Verdict

Best positive candidate: `lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time` with `40213.5000` future test net points, `100.00%` positive selected folds, `1.8652` average test PF, `3` minute bars, and `3` minute holding.

This is a research result: the script approximates the Pine indicator from `docs/Strategy/lightglow.md` on OHLCV bars and uses walk-forward selection before scoring future folds.

## Data And Method

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Requested span: `2021-04-28` to `2026-04-28`.
- Loaded 1m span: `2021-04-28 00:00:00+00:00` to `2026-04-27 23:57:00+00:00`.
- 1m rows: `589,965`.
- Timeframes tested: `3m, 5m`.
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
- Hold bars: `1, 2, 3`.
- Direction modes: `reverse`.
- Exit profiles: `time, sl8_tp8, sl8_tp12, sl12_tp12, sl12_tp18, sl16_tp16, sl16_tp24`.
- Train gate: trades >= `40`, PF >= `1.03`, net > `0`.
- Test pass label: trades >= `5`, PF >= `1.0`, net > `0`.

## Output Summary

- Fold rows: `79`.
- Aggregated train-selected candidates: `6`.
- Positive aggregate candidates: `6`.
- Full-sample candidates evaluated: `42`.

## Best Positive Candidate By Timeframe

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | premium_discount_reversal | 3 | all | 3 | reverse | time | 13 | 1.0000 | 1.0000 | 12728 | 40213.5000 | 1205.5000 | 33.3584 | 1.8652 | 0.4453 | 1011.5000 |
| lightglow_premium_discount_reversal_5m_all_hold5m_reverse_time | premium_discount_reversal | 5 | all | 5 | reverse | time | 13 | 0.9231 | 0.9231 | 7707 | 13936.3750 | 787.2500 | 17.7026 | 1.3584 | 0.4586 | -277.6250 |

## Positive Walk-Forward Ranking

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | premium_discount_reversal | 3 | all | 3 | reverse | time | 13 | 1.0000 | 1.0000 | 12728 | 40213.5000 | 1205.5000 | 33.3584 | 1.8652 | 0.4453 | 1011.5000 |
| lightglow_premium_discount_reversal_3m_all_hold9m_reverse_time | premium_discount_reversal | 3 | all | 9 | reverse | time | 13 | 1.0000 | 1.0000 | 11443 | 29520.1250 | 1107.1250 | 26.6638 | 1.4112 | 0.4646 | 601.7500 |
| lightglow_premium_discount_reversal_3m_all_hold6m_reverse_time | premium_discount_reversal | 3 | all | 6 | reverse | time | 13 | 1.0000 | 1.0000 | 12485 | 33109.3750 | 1594.5000 | 20.7647 | 1.5126 | 0.4551 | 672.2500 |
| lightglow_premium_discount_reversal_5m_all_hold5m_reverse_time | premium_discount_reversal | 5 | all | 5 | reverse | time | 13 | 0.9231 | 0.9231 | 7707 | 13936.3750 | 787.2500 | 17.7026 | 1.3584 | 0.4586 | -277.6250 |
| lightglow_premium_discount_reversal_5m_all_hold10m_reverse_time | premium_discount_reversal | 5 | all | 10 | reverse | time | 13 | 0.8462 | 0.8462 | 7532 | 13290.2500 | 1334.1250 | 9.9618 | 1.2607 | 0.4735 | -242.6250 |
| lightglow_premium_discount_reversal_5m_all_hold15m_reverse_time | premium_discount_reversal | 5 | all | 15 | reverse | time | 14 | 0.7857 | 0.7857 | 7444 | 14314.2500 | 1679.3750 | 8.5236 | 1.2668 | 0.4687 | -1340.0000 |

## Best Future Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | lightglow_premium_discount_reversal_3m_all_hold9m_reverse_time | 11 | 2 | 3490 | 8439.0000 | 1.4078 | 851 | 6641.1250 | 1.8765 | 0.5112 |
| True | lightglow_premium_discount_reversal_3m_all_hold6m_reverse_time | 14 | 4 | 3767 | 14815.1250 | 1.6420 | 926 | 5102.2500 | 1.9024 | 0.4730 |
| True | lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | 9 | 1 | 4015 | 10183.3750 | 1.8815 | 946 | 5034.5000 | 2.1449 | 0.4619 |
| True | lightglow_premium_discount_reversal_3m_all_hold6m_reverse_time | 13 | 3 | 3734 | 13276.7500 | 1.5524 | 974 | 4711.5000 | 1.9488 | 0.4641 |
| True | lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | 13 | 1 | 3790 | 15084.5000 | 1.8594 | 984 | 4649.7500 | 2.3252 | 0.4329 |
| True | lightglow_premium_discount_reversal_3m_all_hold6m_reverse_time | 10 | 2 | 3912 | 8187.7500 | 1.4759 | 945 | 4517.8750 | 1.8728 | 0.4339 |
| True | lightglow_premium_discount_reversal_3m_all_hold9m_reverse_time | 13 | 2 | 3408 | 11988.7500 | 1.4599 | 882 | 4504.2500 | 1.8882 | 0.4785 |
| True | lightglow_premium_discount_reversal_3m_all_hold6m_reverse_time | 11 | 3 | 3810 | 10576.2500 | 1.5634 | 935 | 4170.3750 | 1.5764 | 0.4930 |
| True | lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | 10 | 1 | 4024 | 13687.7500 | 2.0669 | 959 | 4147.6250 | 2.1051 | 0.4359 |
| True | lightglow_premium_discount_reversal_5m_all_hold5m_reverse_time | 11 | 5 | 2429 | 3360.8750 | 1.2863 | 550 | 4023.2500 | 2.1255 | 0.5145 |
| True | lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | 6 | 1 | 4133 | 7348.6250 | 1.5774 | 968 | 3603.7500 | 2.5475 | 0.4339 |
| True | lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | 14 | 2 | 3813 | 14864.1250 | 1.8936 | 931 | 3528.8750 | 1.8555 | 0.4640 |
| True | lightglow_premium_discount_reversal_5m_all_hold10m_reverse_time | 14 | 3 | 2325 | 7371.8750 | 1.4263 | 558 | 3507.2500 | 1.8105 | 0.5000 |
| True | lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | 11 | 1 | 3913 | 14249.6250 | 2.0248 | 949 | 3468.1250 | 1.6313 | 0.4731 |
| True | lightglow_premium_discount_reversal_3m_all_hold6m_reverse_time | 9 | 3 | 3912 | 5761.5000 | 1.3772 | 924 | 3107.0000 | 1.5097 | 0.4697 |
| True | lightglow_premium_discount_reversal_5m_all_hold10m_reverse_time | 11 | 6 | 2374 | 2643.5000 | 1.1714 | 536 | 3002.0000 | 1.6391 | 0.5037 |
| True | lightglow_premium_discount_reversal_5m_all_hold15m_reverse_time | 11 | 4 | 2168 | 5008.7500 | 1.3048 | 498 | 2970.0000 | 1.5125 | 0.4920 |
| True | lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | 7 | 1 | 4157 | 8956.1250 | 1.7548 | 1036 | 2942.5000 | 1.8944 | 0.4353 |
| True | lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | 15 | 1 | 3828 | 14056.2500 | 1.8154 | 966 | 2838.7500 | 1.4959 | 0.4658 |
| True | lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | 4 | 1 | 4065 | 3573.6250 | 1.2307 | 1130 | 2778.2500 | 1.9399 | 0.4035 |
| True | lightglow_premium_discount_reversal_3m_all_hold9m_reverse_time | 14 | 1 | 3424 | 14788.0000 | 1.6073 | 844 | 2745.2500 | 1.4184 | 0.4680 |
| True | lightglow_premium_discount_reversal_3m_all_hold9m_reverse_time | 10 | 4 | 3594 | 6274.0000 | 1.3256 | 847 | 2665.1250 | 1.4976 | 0.4569 |
| True | lightglow_premium_discount_reversal_5m_all_hold5m_reverse_time | 14 | 5 | 2369 | 6631.3750 | 1.5069 | 564 | 2637.0000 | 1.7814 | 0.4699 |
| True | lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | 12 | 1 | 3831 | 13921.6250 | 1.8841 | 905 | 2543.8750 | 1.6684 | 0.4884 |
| True | lightglow_premium_discount_reversal_5m_all_hold15m_reverse_time | 10 | 3 | 2186 | 3525.7500 | 1.2285 | 541 | 2428.8750 | 1.5648 | 0.4677 |
| True | lightglow_premium_discount_reversal_3m_all_hold6m_reverse_time | 6 | 2 | 4074 | 6319.7500 | 1.3694 | 947 | 2367.6250 | 1.7881 | 0.4541 |
| True | lightglow_premium_discount_reversal_3m_all_hold9m_reverse_time | 8 | 5 | 3736 | 5083.7500 | 1.2996 | 851 | 2275.1250 | 1.6287 | 0.4606 |
| True | lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | 8 | 1 | 4169 | 10753.8750 | 1.8962 | 945 | 2145.6250 | 1.8610 | 0.4233 |
| True | lightglow_premium_discount_reversal_5m_all_hold15m_reverse_time | 13 | 6 | 2151 | 7785.6250 | 1.3744 | 532 | 2115.5000 | 1.5504 | 0.4793 |
| True | lightglow_premium_discount_reversal_3m_all_hold9m_reverse_time | 15 | 2 | 3462 | 14576.2500 | 1.5646 | 873 | 2053.3750 | 1.2323 | 0.4696 |

## Full-Sample Positive Sanity Check

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | trades | net_points | profit_factor | win_rate | max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | premium_discount_reversal | 3 | all | 3 | reverse | time | 19747 | 41108.8750 | 1.5550 | 0.4417 | 2492.1250 |
| lightglow_premium_discount_reversal_3m_all_hold6m_reverse_time | premium_discount_reversal | 3 | all | 6 | reverse | time | 19451 | 33918.6250 | 1.3353 | 0.4507 | 3171.5000 |
| lightglow_premium_discount_reversal_5m_all_hold10m_reverse_time | premium_discount_reversal | 5 | all | 10 | reverse | time | 11708 | 15216.7500 | 1.1948 | 0.4691 | 1763.6250 |
| lightglow_premium_discount_reversal_5m_all_hold5m_reverse_time | premium_discount_reversal | 5 | all | 5 | reverse | time | 11949 | 14340.8750 | 1.2419 | 0.4584 | 1726.3750 |
| lightglow_premium_discount_reversal_5m_all_hold15m_reverse_time | premium_discount_reversal | 5 | all | 15 | reverse | time | 10745 | 16840.6250 | 1.1954 | 0.4672 | 2169.8750 |
| lightglow_premium_discount_reversal_3m_all_hold9m_reverse_time | premium_discount_reversal | 3 | all | 9 | reverse | time | 17869 | 29153.3750 | 1.2603 | 0.4628 | 3896.8750 |
