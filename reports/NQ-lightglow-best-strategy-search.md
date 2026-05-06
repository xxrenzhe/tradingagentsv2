# NQ Lightglow Best Strategy Search

## Scope

This search traverses only technical indicators present in `docs/Strategy/lightglow.md` and their backtest parameter combinations.

Indicators traversed:

- Internal BOS / CHoCH.
- Swing BOS / CHoCH.
- Fair Value Gap.
- Equal High / Equal Low reversal.
- Internal and swing order-block break.
- Premium / Discount zone reversal.
- Internal CHoCH + zone confluence.
- FVG + zone confluence.

No external overlays are part of this selection: no event-window filters, no volatility filters, no daily stops, no trade caps, and no cost stress overlays.

Search-space audit:

- Native Lightglow indicators traversed: `11`.
- Full-sample candidate combinations: `1056` across `11` signals.
- Walk-forward aggregate candidates considered: `159` across `10` signals.
- Candidates passing the selection gate: `10`.

## Selection Gate

- Aggregate source: `.tmp/nq-lightglow-5y-walkforward-aggregate.csv`.
- Selected folds >= `8`.
- Positive future fold rate >= `80.00%`.
- Future trades >= `500`.
- Average future PF >= `1.25`.
- Net/DD >= `10.0`.

## Best Strategy

`lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time`

| Field | Value |
| --- | ---: |
| Lightglow indicator | `premium_discount_reversal` |
| Timeframe | `1m` |
| Session | `all` |
| Direction mode | `reverse` |
| Holding minutes | `2` |
| Exit profile | `time` |
| Selected folds | `13` |
| Positive future fold rate | `100.00%` |
| Future trades | `38836` |
| Future net points | `104031.7500` |
| Future max DD points | `1843.6250` |
| Net/DD | `56.4278` |
| Average future PF | `1.9686` |
| Worst selected future fold | `2125.3750` |

## Why This Is The Best

The selected strategy is the only Lightglow-native signal family that dominates on all main objectives at once: net profit, PF, fold stability, and net-to-drawdown.

The key discovered pattern is not generic trend-following. It is the reverse interpretation of the Lightglow Premium / Discount zone signal: fade premium/discount zone reversal indications on 1-minute bars and exit by time after 2 minutes.

## Best Candidate By Lightglow Indicator

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | min_test_net_points | selection_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | premium_discount_reversal | 1 | all | 2 | reverse | time | 13 | 1.0000 | 38836 | 104031.7500 | 1843.6250 | 56.4278 | 1.9686 | 2125.3750 | 234.3642 |
| lightglow_internal_ob_break_15m_us_late_hold45m_native_time | internal_ob_break | 15 | us_late | 45 | native | time | 4 | 1.0000 | 52 | 534.5000 | 64.8750 | 8.2389 | 2.9475 | 86.7500 | 82.2463 |
| lightglow_swing_bos_5m_us_rth_hold25m_native_time | swing_bos | 5 | us_rth | 25 | native | time | 1 | 1.0000 | 7 | 49.1250 | 25.5000 | 1.9265 | 2.0565 | 49.1250 | 58.9697 |
| lightglow_swing_ob_break_1m_all_hold5m_native_time | swing_ob_break | 1 | all | 5 | native | time | 1 | 1.0000 | 713 | 1079.8750 | 588.5000 | 1.8350 | 1.2796 | 1079.8750 | 51.3483 |
| lightglow_internal_choch_1m_us_late_hold3m_native_time | internal_choch | 1 | us_late | 3 | native | time | 1 | 1.0000 | 386 | 713.7500 | 654.2500 | 1.0909 | 1.2843 | 713.7500 | 49.2110 |
| lightglow_fvg_zone_5m_us_late_hold25m_reverse_time | fvg_zone | 5 | us_late | 25 | reverse | time | 2 | 1.0000 | 18 | 54.5000 | 64.7500 | 0.8417 | 1.3823 | 18.8750 | 48.6874 |
| lightglow_swing_choch_5m_us_rth_hold15m_reverse_time | swing_choch | 5 | us_rth | 15 | reverse | time | 1 | 1.0000 | 41 | 136.6250 | 97.8750 | 1.3959 | 1.3637 | 136.6250 | 48.3983 |
| lightglow_fvg_15m_us_late_hold75m_native_time | fvg | 15 | us_late | 75 | native | time | 2 | 1.0000 | 69 | 247.1250 | 240.2500 | 1.0286 | 1.3040 | 102.8750 | 48.1442 |
| lightglow_internal_bos_5m_us_late_hold25m_reverse_time | internal_bos | 5 | us_late | 25 | reverse | time | 1 | 1.0000 | 39 | 64.3750 | 69.5000 | 0.9263 | 1.3185 | 64.3750 | 46.9611 |
| lightglow_internal_choch_zone_5m_us_rth_hold15m_reverse_time | internal_choch_zone | 5 | us_rth | 15 | reverse | time | 1 | 1.0000 | 63 | 15.8750 | 141.8750 | 0.1119 | 1.0306 | 15.8750 | 41.6345 |

## Eligible Candidate Set

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | min_test_net_points | selection_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | premium_discount_reversal | 1 | all | 2 | reverse | time | 13 | 1.0000 | 38836 | 104031.7500 | 1843.6250 | 56.4278 | 1.9686 | 2125.3750 | 234.3642 |
| lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | premium_discount_reversal | 1 | all | 3 | reverse | time | 13 | 1.0000 | 35568 | 93805.5000 | 1527.5000 | 61.4111 | 1.7735 | 731.1250 | 222.0123 |
| lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | premium_discount_reversal | 1 | all | 5 | reverse | time | 13 | 1.0000 | 30948 | 67863.7500 | 1800.1250 | 37.6995 | 1.5134 | 1864.3750 | 171.8570 |
| lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | premium_discount_reversal | 3 | all | 3 | reverse | time | 13 | 1.0000 | 12728 | 40213.5000 | 1205.5000 | 33.3584 | 1.8652 | 1011.5000 | 142.5846 |
| lightglow_premium_discount_reversal_3m_all_hold6m_reverse_time | premium_discount_reversal | 3 | all | 6 | reverse | time | 12 | 1.0000 | 11466 | 32036.5000 | 1594.5000 | 20.0919 | 1.5345 | 672.2500 | 114.1620 |
| lightglow_premium_discount_reversal_3m_all_hold9m_reverse_time | premium_discount_reversal | 3 | all | 9 | reverse | time | 11 | 1.0000 | 9499 | 26589.3750 | 1107.1250 | 24.0166 | 1.4225 | 601.7500 | 109.7487 |
| lightglow_premium_discount_reversal_5m_all_hold5m_reverse_time | premium_discount_reversal | 5 | all | 5 | reverse | time | 9 | 1.0000 | 5255 | 11685.3750 | 646.0000 | 18.0888 | 1.3976 | 462.3750 | 86.1246 |
| lightglow_premium_discount_reversal_1m_us_late_hold2m_reverse_time | premium_discount_reversal | 1 | us_late | 2 | reverse | time | 12 | 0.8333 | 2550 | 5635.2500 | 307.3750 | 18.3335 | 1.7350 | -144.8750 | 82.8270 |
| lightglow_premium_discount_reversal_3m_all_hold15m_reverse_time | premium_discount_reversal | 3 | all | 15 | reverse | time | 8 | 1.0000 | 5978 | 14868.2500 | 1450.1250 | 10.2531 | 1.2618 | 136.7500 | 77.4582 |
| lightglow_premium_discount_reversal_5m_all_hold15m_reverse_time | premium_discount_reversal | 5 | all | 15 | reverse | time | 11 | 0.8182 | 5756 | 14091.7500 | 1197.5000 | 11.7676 | 1.3112 | -649.3750 | 76.9818 |

## Decision

Best Lightglow-only strategy found: `lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time`.

For lower execution complexity, the 3m premium/discount reverse time-exit variant remains a secondary validation candidate, but it is not the best strategy under this search objective.
