# NQ Lightglow Overlay Optimization Summary

## Objective

Optimize the current Lightglow leaders without rerunning slow signal construction by applying fast overlays to existing walk-forward trade streams.

Tested overlays:

- Extra round-trip costs: `0`, `0.25`, `0.5`, `1.0` points.
- Daily trade caps: no cap, `40`, `80`, `120` trades/day.
- Daily stop overlays: no stop, `-200`, `-300`, `-400` points/day.

Source:

- `.tmp/nq-lightglow-5y-walkforward-trades.csv`

Output:

- `.tmp/nq-lightglow-overlay-ranking.csv`
- `reports/NQ-lightglow-overlay-optimization.md`

## Candidates Tested

1. Raw-return leader:
   `lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time`

2. Controlled-risk leader:
   `lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time`

## Key Findings

### 1m raw leader remains strongest on headline net points

Baseline overlay:

| Metric | Value |
| --- | ---: |
| Trades | 38,836 |
| Net points | 104,031.75 |
| Max DD points | 2,323.50 |
| Net/DD | 44.7737 |
| PF | 1.9172 |
| Positive day rate | 36.69% |
| Worst day | -424.25 |
| Avg trades/day | 39.47 |

With `+1.0` point extra round-trip cost:

| Metric | Value |
| --- | ---: |
| Net points | 65,195.75 |
| Max DD points | 5,618.375 |
| Net/DD | 11.6040 |
| PF | 1.4746 |
| Positive day rate | 20.02% |
| Worst day | -488.25 |

Interpretation: the 1m strategy is still profitable under a severe extra cost assumption, but its risk quality deteriorates sharply. This confirms the edge is execution-sensitive.

### 3m controlled-risk leader is less sensitive to caps

Baseline overlay:

| Metric | Value |
| --- | ---: |
| Trades | 12,728 |
| Net points | 40,213.50 |
| Max DD points | 1,261.50 |
| Net/DD | 31.8775 |
| PF | 1.8316 |
| Positive day rate | 46.09% |
| Worst day | -327.875 |
| Avg trades/day | 13.83 |

Daily caps of `80` or `120` have no practical effect because average trade count is already well below those caps.

Interpretation: the 3m strategy has lower headline return, but its operating profile is cleaner: fewer trades, better day stability, lower drawdown, and less need for throttle overlays.

## Overlay Conclusions

1. Daily stop overlays did not materially improve the headline ranking for either candidate.
2. A `-200` daily stop can slightly improve PF in some cost-stressed 1m scenarios, but it does not solve the positive-day-rate weakness.
3. Trade caps above 40/day do not help the 3m strategy because it is naturally below that frequency.
4. The 1m strategy should not be promoted without explicit execution-cost validation and broker-realistic slippage tests.

## Current Optimized Recommendation

Use two tracks:

| Track | Candidate | Purpose |
| --- | --- | --- |
| Aggressive | `lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time` | Maximum net/PF research track; paper only until slippage is verified |
| Primary | `lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time` | Controlled-risk validation track |

Operational defaults:

- Start paper validation with MNQ 1 contract.
- Keep time exit, not fixed stop-loss/take-profit.
- For 1m track, record actual fill slippage and rerank with realized costs.
- For 3m track, no daily cap is needed initially; use a daily stop only as a hard safety fuse, not as an alpha improvement.

## Next Optimization Step

The next useful optimization is not more fixed SL/TP. It should be:

1. Slippage replay using paper-trade fills.
2. State filters for the 1m candidate:
   - time-of-day bucket,
   - distance from equilibrium,
   - realized volatility,
   - prior 3m/5m trend state,
   - scheduled event windows.
3. Dynamic exits:
   - ATR-scaled stop,
   - volatility-time exit,
   - skip trades when range/ATR is too small to pay costs.
