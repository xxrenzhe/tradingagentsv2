# Lightglow Strategy Candidate Ranking

## Filters

- Source aggregate: `.tmp/nq-lightglow-5y-walkforward-aggregate.csv`.
- Minimum selected folds: `8`.
- Minimum positive fold rate: `80.00%`.
- Minimum trades: `500`.
- Maximum drawdown points: `2000.0`.
- Minimum PF: `1.25`.
- Minimum net/DD: `10.0`.
- Minimum worst fold points: `0.0`.

## Ranked Candidates

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | min_test_net_points | controlled_risk_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | premium_discount_reversal | 1 | all | 2 | reverse | time | 13 | 1.0000 | 38836 | 104031.7500 | 1843.6250 | 56.4278 | 1.9686 | 2125.3750 | 194.3960 |
| lightglow_premium_discount_reversal_1m_all_hold3m_reverse_time | premium_discount_reversal | 1 | all | 3 | reverse | time | 13 | 1.0000 | 35568 | 93805.5000 | 1527.5000 | 61.4111 | 1.7735 | 731.1250 | 184.4137 |
| lightglow_premium_discount_reversal_1m_all_hold5m_reverse_time | premium_discount_reversal | 1 | all | 5 | reverse | time | 13 | 1.0000 | 30948 | 67863.7500 | 1800.1250 | 37.6995 | 1.5134 | 1864.3750 | 134.4257 |
| lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | premium_discount_reversal | 3 | all | 3 | reverse | time | 13 | 1.0000 | 12728 | 40213.5000 | 1205.5000 | 33.3584 | 1.8652 | 1011.5000 | 104.2470 |
| lightglow_premium_discount_reversal_3m_all_hold6m_reverse_time | premium_discount_reversal | 3 | all | 6 | reverse | time | 12 | 1.0000 | 11466 | 32036.5000 | 1594.5000 | 20.0919 | 1.5345 | 672.2500 | 78.8175 |
| lightglow_premium_discount_reversal_3m_all_hold9m_reverse_time | premium_discount_reversal | 3 | all | 9 | reverse | time | 11 | 1.0000 | 9499 | 26589.3750 | 1107.1250 | 24.0166 | 1.4225 | 601.7500 | 76.0345 |
| lightglow_premium_discount_reversal_5m_all_hold5m_reverse_time | premium_discount_reversal | 5 | all | 5 | reverse | time | 9 | 1.0000 | 5255 | 11685.3750 | 646.0000 | 18.0888 | 1.3976 | 462.3750 | 54.6745 |
| lightglow_premium_discount_reversal_3m_all_hold15m_reverse_time | premium_discount_reversal | 3 | all | 15 | reverse | time | 8 | 1.0000 | 5978 | 14868.2500 | 1450.1250 | 10.2531 | 1.2618 | 136.7500 | 48.0126 |

## Next Search Command

Use a focused stop/target expansion instead of the full signal universe:

```bash
.venv/bin/python scripts/backtest_lightglow_nq_bars.py \
  --signals premium_discount_reversal internal_choch_zone fvg_zone \
  --timeframes 1 3 5 15 \
  --sessions all us_late us_rth \
  --hold-bars 1 2 3 5 \
  --direction-modes reverse native \
  --exit-profiles time sl8_tp8 sl8_tp12 sl8_tp16 sl12_tp12 sl12_tp18 sl12_tp24 sl16_tp16 sl16_tp24 sl16_tp32 \
  --output .tmp/nq-lightglow-expanded-walkforward.csv \
  --aggregate-output .tmp/nq-lightglow-expanded-aggregate.csv \
  --trades-output .tmp/nq-lightglow-expanded-trades.csv \
  --full-sample-output .tmp/nq-lightglow-expanded-full-sample.csv \
  --report reports/NQ-lightglow-expanded-strategy-search.md
```
