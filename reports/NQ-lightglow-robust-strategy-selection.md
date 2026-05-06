# NQ Lightglow Robust Strategy Selection

## Verdict

The best robust strategy from the current lightglow backtest set is:

`lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time`

This is not the highest-return candidate. The raw highest-return candidate is `lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time`, but it depends on very high trade frequency and shows weak calendar stability. For a high-return, lower-risk, more stable, less-overfit strategy, the 3-minute version is the cleaner choice.

## Final Strategy Rules

| Field | Rule |
| --- | --- |
| Symbol | NQ continuous bar stream from Databento OHLCV 1m source |
| Base data | 1-minute OHLCV bars resampled to 3-minute bars |
| Indicator family | `docs/Strategy/lightglow.md` premium/discount zone signal |
| Signal | `premium_discount_reversal` |
| Direction | `reverse` of the raw zone reversal signal |
| Entry | Enter on the next 3-minute bar open after a valid signal |
| Exit | Time exit after 1 bar, equal to 3 minutes |
| Session | `all` in backtest; production should initially cap exposure during known event windows |
| Position size | Start with 1 MNQ for paper validation, not 1 NQ |
| Daily risk stop | Stop trading for the day after approximately -200 to -400 NQ points per NQ-equivalent strategy PnL |
| Trade throttle | No hard throttle needed in backtest; production can cap at 80 trades/day as a guardrail |

The rule is intentionally simple: one signal family, one timeframe, one direction mode, one holding period. That reduces the degrees of freedom and makes it less likely that the result is curve-fit.

## Why This Beats The Raw Top Strategy

| Candidate | Net Points | Max DD | Net/DD | PF | Positive Days | Positive Months | Worst Month |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1m premium/discount reverse, hold 2m | 104,031.75 | 2,323.50 | 44.77 | 1.9172 | 36.69% | 35.00% | -841.25 |
| 3m premium/discount reverse, hold 3m | 40,213.50 | 1,261.50 | 31.88 | 1.8316 | 46.09% | 55.00% | -755.88 |

The 1m strategy has higher total net points and better net/DD, but it wins through a very large number of trades. Its positive-month rate is only 35%, which is a serious stability warning. The 3m version earns less, but has better calendar stability, fewer trades, lower drawdown, and a more plausible execution footprint.

## Walk-Forward Evidence

| Metric | 3m Robust Strategy |
| --- | ---: |
| Selected folds | 13 |
| Positive future fold rate | 100.00% |
| Future test trades | 12,728 |
| Future test net points | 40,213.50 |
| Average future PF | 1.8652 |
| Future max drawdown | 1,205.50 |
| Worst selected future fold | +1,011.50 |

The most important anti-overfit feature is the worst selected future fold: it remains positive. This matters more than the headline net points.

## Risk-Control Variant

The preferred live/paper variant is:

`lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time`

with these operational overlays:

1. Trade only one open position per strategy instance.
2. Enter at next 3-minute open after signal confirmation.
3. Exit strictly after one 3-minute bar.
4. Pause for the day if cumulative realized strategy PnL reaches -200 to -400 NQ points.
5. Cap to 80 trades/day during paper validation, even though the 3m backtest did not need the cap.
6. Do not add stop-loss/take-profit brackets until separately tested; the current evidence is for time exit.
7. Disable around major scheduled macro events until a dedicated event-window study is complete.

## Rejection Rules

Do not promote a variant if any of these fail in future validation:

| Gate | Required |
| --- | --- |
| Future folds | At least 8 selected folds |
| Positive fold rate | At least 80% |
| Worst selected future fold | Greater than 0 |
| Net/DD | At least 20 |
| Profit factor | At least 1.25 |
| Positive months | At least 50% |
| Full-sample net | Greater than 0 |

Under stricter requirements that also demand strong monthly stability and very high net/DD, no candidate passed. That is why this should be treated as a paper-validation candidate, not a live-ready production strategy.

## Implementation Notes

The current research artifacts supporting this selection are:

- `.tmp/nq-lightglow-5y-walkforward-aggregate.csv`
- `.tmp/nq-lightglow-5y-walkforward.csv`
- `.tmp/nq-lightglow-5y-walkforward-trades.csv`
- `.tmp/nq-lightglow-5y-full-sample.csv`
- `reports/NQ-lightglow-5y-bar-backtest.md`
- `reports/NQ-lightglow-5y-bar-backtest.html`

The strategy should be implemented as a deterministic adapter around the existing `backtest_lightglow_nq_bars.py` signal logic, then run in paper mode before any live use.

## Bottom Line

Best raw return:

`lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time`

Best robust strategy to build:

`lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time`

The 3m strategy gives up headline return to reduce trade frequency, drawdown pressure, and overfit risk. That is the better engineering choice for the stated requirement: high return, lower risk, stable, and not obviously overfit.
