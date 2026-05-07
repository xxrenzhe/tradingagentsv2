# NQ Lightglow Expanded Research Summary

## Objective

Continue Lightglow strategy discovery across signal features, entry/exit logic, bar cycles, holding periods, and fixed stop-loss/take-profit overlays. The target is not only high net points, but also high profit factor and controlled drawdown.

## Current Evidence

The existing 5-year walk-forward aggregate is:

- `.tmp/nq-lightglow-5y-walkforward-aggregate.csv`
- `.tmp/nq-lightglow-5y-walkforward-trades.csv`
- `.tmp/nq-lightglow-5y-full-sample.csv`

A ranked candidate report was generated at:

- `reports/NQ-lightglow-strategy-candidate-ranking.md`

Under filters of at least 8 selected folds, at least 80% positive future fold rate, at least 500 trades, max drawdown no more than 2,000 points, PF at least 1.25, net/DD at least 10, and worst fold above 0, 8 candidates passed.

## Best Net Profit And PF Candidate

The highest net profit and highest PF candidate in the current broad result set is:

`lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time`

Metrics:

| Metric | Value |
| --- | ---: |
| Selected folds | 13 |
| Positive future fold rate | 100.00% |
| Future trades | 38,836 |
| Future net points | 104,031.75 |
| Future max drawdown points | 1,843.625 |
| Net/DD | 56.4278 |
| Average future PF | 1.9686 |
| Worst future fold | 2,125.375 |

This is currently the raw leader if the goal is maximum points and PF. The main caveat is execution footprint: it depends on a very high trade count on 1-minute bars.

## Best Controlled-Risk Candidate

The best lower-frequency controlled-risk candidate remains:

`lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time`

Metrics:

| Metric | Value |
| --- | ---: |
| Selected folds | 13 |
| Positive future fold rate | 100.00% |
| Future trades | 12,728 |
| Future net points | 40,213.50 |
| Future max drawdown points | 1,205.50 |
| Net/DD | 33.3584 |
| Average future PF | 1.8652 |
| Worst future fold | 1,011.50 |

This remains the cleaner paper-validation candidate because it keeps 100% positive folds with materially lower trade frequency and lower drawdown pressure than the 1m raw leader.

## Timeframe Comparison

For `premium_discount_reversal`, `reverse`, `all` session, and time exit:

| Timeframe | Best Hold | Future Net Points | Future PF | Net/DD | Fold Stability |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1m | 2m | 104,031.75 | 1.9686 | 56.4278 | 13/13 positive |
| 3m | 3m | 40,213.50 | 1.8652 | 33.3584 | 13/13 positive |
| 5m | 5m | 11,685.375 | 1.3976 | 18.0888 | 9/9 positive in broad aggregate |
| 15m | 75m | 2,368.00 | 1.2699 | 2.0632 | weak and sparse |

The practical search frontier is currently 1m versus 3m. The 5m version is lower return but may be useful as a low-frequency comparator. The 15m version is not competitive.

## Stop-Loss / Take-Profit Probe

A focused SL/TP probe was run for:

- Signal: `premium_discount_reversal`
- Timeframes: `3m`, `5m`
- Session: `all`
- Direction: `reverse`
- Hold bars: `1`, `2`, `3`
- Exit profiles: `time`, `sl8_tp8`, `sl8_tp12`, `sl12_tp12`, `sl12_tp18`, `sl16_tp16`, `sl16_tp24`

Outputs:

- `.tmp/nq-lightglow-pd-sltp-small-aggregate.csv`
- `.tmp/nq-lightglow-pd-sltp-small-trades.csv`
- `reports/NQ-lightglow-premium-discount-sltp-small-search.md`
- `reports/NQ-lightglow-premium-discount-sltp-small-ranking.md`

Result: all walk-forward selected aggregate winners were still `time` exit. No fixed SL/TP candidate survived into the aggregate winners in this probe.

Conclusion: do not add fixed stop-loss/take-profit to the current P/D reverse strategy yet. The evidence still supports time exit.

## Current Recommendation

Use two parallel paper-validation tracks:

1. Aggressive raw-return track:
   `lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time`

2. Controlled-risk primary track:
   `lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time`

Both should be MNQ 1-lot paper-only before any live use. The 1m track needs extra execution-cost and throttle validation because its edge depends on high trade frequency.

## Next Search Steps

1. Optimize execution-cost sensitivity for the 1m raw leader by rerunning with higher slippage assumptions.
2. Add daily trade caps and daily stop rules to compare raw net versus controlled net.
3. Explore state filters: time-of-day, volatility regime, prior bar range, distance from equilibrium, and event windows.
4. Only after state filters are tested, revisit SL/TP with narrower dynamic profiles such as ATR-scaled exits rather than fixed 8/12/16 point brackets.
5. Keep `premium_discount_reversal` as the primary signal family; confluence variants should be tested as filters, not assumed improvements.
