# Lightglow Strategy Candidate Ranking

## Filters

- Source aggregate: `.tmp/nq-lightglow-pd-sltp-small-aggregate.csv`.
- Minimum selected folds: `1`.
- Minimum positive fold rate: `0.00%`.
- Minimum trades: `1`.
- Maximum drawdown points: `100000.0`.
- Minimum PF: `0.0`.
- Minimum net/DD: `-100.0`.
- Minimum worst fold points: `-100000.0`.

## Ranked Candidates

| candidate | signal | timeframe_minutes | session | holding_minutes | direction_mode | exit_profile | selected_folds | positive_test_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | min_test_net_points | controlled_risk_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time | premium_discount_reversal | 3 | all | 3 | reverse | time | 13 | 1.0000 | 12728 | 40213.5000 | 1205.5000 | 33.3584 | 1.8652 | 1011.5000 | 104.2470 |
| lightglow_premium_discount_reversal_3m_all_hold9m_reverse_time | premium_discount_reversal | 3 | all | 9 | reverse | time | 13 | 1.0000 | 11443 | 29520.1250 | 1107.1250 | 26.6638 | 1.4112 | 601.7500 | 81.4991 |
| lightglow_premium_discount_reversal_3m_all_hold6m_reverse_time | premium_discount_reversal | 3 | all | 6 | reverse | time | 13 | 1.0000 | 12485 | 33109.3750 | 1594.5000 | 20.7647 | 1.5126 | 672.2500 | 80.3444 |
| lightglow_premium_discount_reversal_5m_all_hold5m_reverse_time | premium_discount_reversal | 5 | all | 5 | reverse | time | 13 | 0.9231 | 7707 | 13936.3750 | 787.2500 | 17.7026 | 1.3584 | -277.6250 | 54.4540 |
| lightglow_premium_discount_reversal_5m_all_hold10m_reverse_time | premium_discount_reversal | 5 | all | 10 | reverse | time | 13 | 0.8462 | 7532 | 13290.2500 | 1334.1250 | 9.9618 | 1.2607 | -242.6250 | 44.3211 |
| lightglow_premium_discount_reversal_5m_all_hold15m_reverse_time | premium_discount_reversal | 5 | all | 15 | reverse | time | 14 | 0.7857 | 7444 | 14314.2500 | 1679.3750 | 8.5236 | 1.2668 | -1340.0000 | 43.3625 |

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
