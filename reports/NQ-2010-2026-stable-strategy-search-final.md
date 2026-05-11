# NQ 2010-2026 Stable Strategy Search Final

## Scope

This search used the continuous NQ 1-minute Databento bars from `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`, spanning `2010-06-06 22:00 UTC` to `2026-04-27 23:59 UTC` with `5,383,225` bars. Costs are `0.625` NQ points round trip unless otherwise stated.

The search focused on bar-computable ideas from `docs/Strategy/lightglow.md` and `docs/Strategy/ICT2022-2.md`: premium/discount, BOS/CHoCH/MSS, fair value gaps, equal highs/lows, liquidity sweeps, range compression, displacement, time windows, and structural invalidation stops.

## Verdict

The strongest new candidate found in this session is not a generic indicator rule. It is a regime transition setup:

`regime_breakout_lb120_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h240`

Mechanics:

- Define a 120-minute range.
- Require the prior range to be wide enough to matter but inefficient: width <= `12 ATR`, efficiency <= `0.25`.
- Enter only after a strong upside displacement candle: range >= `1.2 ATR30`, body share >= `0.55`, volume z >= `0`.
- Trade only `us_late`, long only.
- Enter next bar open.
- Stop below the displacement bar low.
- Target fixed `2R`, timeout `240` minutes.

Selected walk-forward future tests: `100` trades, `963.55` net points, PF `1.979`, win rate `46.7%`, payoff `2.20`, expectancy `11.17` points/trade, `4/4` selected folds positive.

Full sample sanity: `462` trades, `1,685.16` net points, PF `1.421`, max DD `266.40`, expectancy `3.65` points/trade, `12/17` positive years, rolling 90-day positive rate `60.3%`.

This is the best research-grade candidate from the new range/trend work, but it is still not production-approved. Profits are meaningfully stronger after 2020, and rolling 90-day stability is not high enough for live deployment without paper validation.

## Final Ranking

| Bucket | Full-sample read | Decision |
| --- | --- | --- |
| Lightglow P/D reverse time | `60,500` trades, `108,035.75` points, PF `1.620`; still positive under heavy cost stress. | Best existing statistical edge, but it is a short time-exit mean-reversion/microstructure effect, not a clean trend strategy. |
| Range -> trend start 2R | `462` trades, `1,685.16` points, PF `1.421`, DD `266.40`, 90d positive `60.3%`. | Best new bar-only structural candidate. Promote to paper-trading validation. |
| Range -> trend start 3R | `558` trades, `2,106.27` points, PF `1.431`, DD `288.62`, 90d positive `58.7%`. | Useful variant; higher payoff but lower hit-rate behavior. |
| Range boundary opposite-edge | `159` trades, `412.63` points, PF `1.433`, payoff `5.69`, 90d positive `31.9%`. | Confirms better payoff near range edges, but unstable standalone. |
| Range boundary fixed 2R | `223` trades, `300.63` points, PF `1.314`; turns negative under high cost stress. | Not robust enough. |
| ICT2022 event walk-forward top | Walk-forward looked strong, but full sample is `-84.82` points, PF `0.973`. | Reject as standalone; use only as a filter idea. |
| ADX/trend fixed 2R | Full-sample positive but PF around `1.03`; negative under modest cost stress. | Too thin. |
| Bar-only us_late long mean reversion | Large profit, but mostly post-2020. | Interesting regime bias, not stable enough across eras. |

## User Questions Answered

### 2R exits

Fixed `2R` works best when paired with a structural trend-start event. It did not preserve the Lightglow premium/discount edge: Lightglow remained strongest with a 2-minute reverse time exit, while fixed bracket variants were mostly negative.

### Range boundary trades

Buying the lower boundary or shorting the upper boundary can produce a better payoff ratio, especially when targeting the opposite edge. The top boundary candidate had payoff `5.69`, but only `20.1%` win rate and a rolling 90-day positive rate of `31.9%`. That is not stable enough as a standalone system.

### ICT2022 factors

The mechanized ICT chain was tested: previous-day or rolling liquidity sweep, MSS, displacement, optional FVG, premium/discount, kill-zone/RTH sessions, and PBL stop. Walk-forward selection found attractive rows, but the top selected candidate failed full-sample sanity. The FVG-required candidate had positive full sample but poor rolling stability and most profit concentrated in the second half.

## Cost Stress

Net points after raising round-trip cost from `0.625` to `2.125` points:

| Candidate family | Base net | Net at 2.125 pt cost |
| --- | ---: | ---: |
| Lightglow P/D reverse time | `108,035.75` | `17,285.75` |
| Range -> trend start 2R | `1,685.16` | `992.16` |
| Range -> trend start 3R | `2,106.27` | `1,269.27` |
| Range boundary opposite-edge | `412.63` | `174.13` |
| Range boundary fixed 2R | `300.63` | `-33.88` |
| ICT2022 event top WF | `-84.82` | `-420.82` |
| ADX/trend 2R | `3,307.75` | `-12,193.25` |

This is why the range-transition candidate is more interesting than the older simple trend 2R candidates: it survives cost stress because it trades far less and has larger average trade expectancy.

## Reports Produced

- `reports/NQ-regime-transition-2010-focused.md`
- `reports/NQ-range-boundary-2010-focused.md`
- `reports/NQ-ict2022-event-system-2010-focused.md`
- `reports/NQ-lightglow-premium-discount-2r-focused.md`
- `reports/NQ-range-breakout-2010-mini.md`
- `reports/NQ-bar-2010-selected-candidate-audit.md`
- `reports/NQ-short-timeframe-trend-system-2010-*.md`

## Next Validation Gate

Before live use, the range-transition candidate should be validated with:

- Contract-roll and session calendar audit.
- Slippage from 1 to 4 ticks per side.
- Paper trading on unseen future data.
- A combined regime switch: trade range-boundary only while range persists, switch to range-transition after displacement.
- Check whether `us_late long` is an NQ-era bias rather than a durable structural edge.
