# NQM6 Short-Term Pattern Mining - 2026-04-27

## Full MBP History Result

After validating the full MBP package, the meaningful backtest is no longer the single 2026-04-27 bar day. The MBP package covers 52 trading days and was aggregated into 60,503 one-minute features from 2026-03-02 23:59 UTC to 2026-05-01 21:00 UTC.

Top full-history candidates:

| Rank | Pattern | Trades | Net Points | Max DD | PF | Win Rate | Stability | Score |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `vwap_reclaim_lb5_thr0.0005_hold3_imb0.35` | 1,355 | 2,444.125 | 302.875 | 1.3237 | 51.14% | 0.8544 | 7.7760 |
| 2 | `vwap_reclaim_lb5_thr0.0002_hold3_imb0.35` | 1,370 | 2,401.500 | 314.125 | 1.3150 | 50.95% | 0.7217 | 7.1131 |
| 3 | `vwap_reclaim_lb10_thr0.0005_hold3_imb0.35` | 1,369 | 2,760.875 | 454.375 | 1.3755 | 51.94% | 0.8230 | 5.8073 |
| 4 | `momentum_lb5_thr0.0006_hold3_imb0.35` | 854 | 2,603.750 | 490.375 | 1.4369 | 51.64% | 0.8697 | 5.1367 |
| 5 | `vwap_reclaim_lb10_thr0.0002_hold3_imb0.35` | 1,384 | 2,676.750 | 526.000 | 1.3579 | 51.73% | 0.8640 | 4.9159 |

Full-history recommendation:

- Primary: `vwap_reclaim_lb5_thr0.0005_hold3_imb0.35`
- Reason: it has the best full-history risk-adjusted score, a large trade sample, positive first-half and second-half performance, and a much smaller drawdown than the higher-net variants.
- Interpretation: use a 5-minute VWAP reclaim signal, require top-of-book imbalance confirmation of 0.35, and exit after 3 minutes.

## Advanced Full-History Exploration

I added a second full-history search pass for dimensions that were not covered by the first fixed-hold grid:

- Flexible holding windows: `min_hold` / `max_hold`, instead of only a fixed holding period.
- Early exits: reverse signal and VWAP re-cross exits, instead of only time exits.
- Session filters: all day, Asia, Europe, and US RTH UTC windows.
- Volatility filters: all, not-low volatility, and high-volatility regimes using 30-minute realized volatility.
- Risk overlays: no bracket and 12-point stop / 24-point take-profit variants.

Best advanced candidates:

| Rank | Pattern | Trades | Net Points | Max DD | PF | Win Rate | Stability | Score | Avg Hold | Exit | Session | Vol Filter | Early Exit |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | ---: |
| 1 | `adv_mean_reversion_lb3_thr0.6_min1_max10_reverse_vwap_europe_not_low_imb0.35` | 274 | 1,306.750 | 120.875 | 2.2656 | 55.47% | 0.5851 | 9.6895 | 4.354 | reverse_vwap | europe | not_low | 67.52% |
| 2 | `adv_mean_reversion_lb3_thr0.6_min1_max5_reverse_vwap_europe_not_low_imb0.35` | 293 | 1,295.875 | 154.125 | 2.1460 | 57.00% | 0.6743 | 7.7232 | 2.659 | reverse_vwap | europe | not_low | 63.14% |
| 3 | `adv_mean_reversion_lb3_thr0.6_min1_max5_reverse_all_high_imb0.35` | 686 | 2,080.500 | 278.625 | 1.4203 | 54.08% | 0.4073 | 6.3606 | 4.673 | reverse | all | high | 17.78% |
| 4 | `adv_mean_reversion_lb3_thr0.6_min1_max10_reverse_europe_not_low_imb0.35` | 225 | 992.625 | 155.500 | 1.6368 | 56.89% | 0.5844 | 5.7202 | 8.760 | reverse | europe | not_low | 24.89% |
| 5 | `adv_vwap_reclaim_lb10_thr0.0002_min1_max10_time_us_rth_high_imb0.35` | 233 | 1,491.125 | 264.875 | 1.6749 | 58.80% | 0.9278 | 5.5279 | 10.000 | time | us_rth | high | 0.00% |

Advanced interpretation:

- The best risk-adjusted advanced candidate is `adv_mean_reversion_lb3_thr0.6_min1_max10_reverse_vwap_europe_not_low_imb0.35`.
- It improves Score from the fixed-hold baseline's 7.7760 to 9.6895, cuts Max DD from 302.875 to 120.875, and raises PF from 1.3237 to 2.2656.
- The trade-off is lower total net points (1,306.750 vs 2,444.125) and a smaller sample (274 vs 1,355 trades), so this is a risk-adjusted candidate rather than an outright replacement for the broader baseline.
- The useful new dimensions are Europe-session filtering, avoiding low-volatility regimes, and allowing VWAP re-cross / reverse-signal early exits. The best candidate exits early on 67.52% of trades, with an average hold of 4.354 minutes.

Reproduce:

```bash
.venv/bin/python scripts/mine_mbp_advanced_patterns.py \
  --top 25 \
  --min-trades 80 \
  --output .tmp/mbp-advanced-patterns.csv \
  --trades-output .tmp/mbp-advanced-patterns-trades.csv
```

The previous single-day candidates fail the full-history test:

| Pattern | Trades | Net Points | Max DD | PF | Win Rate | Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `mean_reversion_lb15_thr0.6_hold10_imb0.35` | 1,360 | -175.000 | 1,852.875 | 0.9869 | 49.19% | -0.0708 |
| `mean_reversion_lb15_thr1.4_hold5` | 4,915 | -330.125 | 1,316.750 | 0.9917 | 48.85% | -0.1880 |
| `mean_reversion_lb5_thr1.4_hold10` | 4,105 | -4,381.875 | 4,956.125 | 0.9031 | 48.82% | -0.6631 |

Conclusion: the single-day mean-reversion result was overfit. Do not use those three as production candidates without additional filters.

## Scope

- Instrument: NQM6.
- Data: Databento GLBX.MDP3 `ohlcv-1m` for 2026-04-27 to 2026-04-28.
- Candidate families: VWAP reclaim, mean reversion, momentum, and breakout.
- Cost model: 1 tick slippage per side plus $2.50 commission per contract.
- Position model: one contract, one open position at a time, fixed holding period.

## Data Coverage Note

- The 95 MB bar zip only contains 2026-04-27 minute bars.
- The 14 GB MBP zip spans 52 trading days from 2026-03-03 to 2026-05-01.
- Any "full history" backtest must therefore use MBP-derived minute features, not the bar zip alone.

## Single-Day Risk-Controlled Pass

This historical section documents the earlier single-day pass. It is retained for comparison only and should not be used as the current recommendation because the full MBP-history test above invalidates the single-day mean-reversion candidates.

Best candidates from the expanded pass:

| Scope | Pattern | Trades | Net Points | Max DD | PF | Win Rate | Worst Trade | Stability | Score |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all + MBP | `mean_reversion_lb15_thr0.6_hold10_imb0.35` | 33 | 205.125 | 23.625 | 3.4493 | 63.64% | -20.875 | 0.6848 | 4.5947 |
| US RTH | `mean_reversion_lb15_thr1.4_hold5` | 30 | 155.250 | 11.125 | 2.7060 | 66.67% | -36.125 | 0.5352 | 6.7554 |
| bar-only | `vwap_reclaim_lb10_thr0.0005_hold10_sl16_tp32` | 64 | 227.500 | 43.000 | 1.7705 | 56.25% | -16.625 | 0.4376 | 3.6375 |
| Asia | `vwap_reclaim_lb10_thr0.0002_hold3_imb0.35` | 10 | 51.500 | 1.875 | 28.4667 | 90.00% | -1.875 | 0.4982 | 7.5961 |
| US late | `vwap_reclaim_lb5_thr0.0002_hold5` | 8 | 48.750 | 0.000 | inf | 100.00% | 0.375 | 0.2342 | 11.1487 |

Single-day interpretation:

1. `all + MBP` is the current best overall candidate because it uses order-book imbalance, has enough trades to be meaningful for one day, and has the strongest profit factor among the higher-trade candidates.
2. `US RTH` is the best execution-focused candidate because it trades during the most liquid session and has lower drawdown than the full-day candidate.
3. `bar-only` produces the highest net points, but its drawdown is materially larger and it does not use order-book confirmation.
4. `Asia` and `US late` score highly, but the sample size is too small to trust as a primary strategy. Treat them as hypotheses only.

Superseded single-day recommendation:

- Primary: `mean_reversion_lb15_thr0.6_hold10_imb0.35`
- Conservative execution variant: `mean_reversion_lb15_thr1.4_hold5` restricted to 13:30-20:00 UTC
- Fallback if MBP is unavailable: `vwap_reclaim_lb10_thr0.0005_hold10_sl16_tp32`

## Previous First-Pass Best Pattern

The best score in the first bar-only pass was:

- Pattern: `vwap_reclaim_lb10_thr0.0005_hold10`
- Trades: 59
- Net: 219.125 points, about $4,382.50 per NQ contract
- Max drawdown: 43.000 points
- Profit factor: 1.9680
- Win rate: 61.02%
- 5th percentile trade loss: -18.225 points

Rule interpretation:

1. Compute VWAP from the session's 1-minute bars.
2. Compute 10-minute momentum.
3. Go long when price is more than 0.05% above VWAP and 10-minute momentum is positive.
4. Exit after 10 minutes.
5. Hold at most one position at a time and exit after 10 minutes.
6. Apply the cost model above.

## Risk Notes

- This is a single-day in-sample result, not a production strategy.
- The 14GB MBP file is now readable and cached. Feature-level caching was added so repeated window searches avoid re-aggregating the same 9.8M MBP rows.
- The best current MBP pattern is still single-day in-sample. It is a candidate, not a production strategy.
- The next hard gate is walk-forward validation across more days. With only one full day, we can rank hypotheses but cannot estimate regime robustness.

## Session Window Pass

The session-window scan splits the day into UTC windows and reruns the same rule search with non-overlapping positions:

- `us_late` 20:00-24:00 UTC: best `vwap_reclaim_lb5_thr0.0002_hold5`, 8 trades, 48.75 net points, no drawdown in this single-day sample.
- `us_rth` 13:30-20:00 UTC: best `mean_reversion_lb15_thr1.4_hold5`, 30 trades, 155.25 net points, 11.125 max drawdown, 66.67% win rate.
- `asia` 00:00-07:00 UTC: best `momentum_lb3_thr0.0003_hold10`, 21 trades, 134.875 net points, 13.625 max drawdown, 71.43% win rate.
- `europe` 07:00-13:30 UTC: best `mean_reversion_lb10_thr1.0_hold10`, 25 trades, 113.375 net points, 21.75 max drawdown, 68.00% win rate.

The `us_late` result is too few trades to trust alone. The more actionable candidates are `us_rth` mean reversion and `asia` momentum because they have more observations with controlled drawdown.

## Reproduce

```bash
.venv/bin/python scripts/mine_short_patterns.py \
  --symbol NQM6 \
  --start-date 2026-04-27 \
  --end-date 2026-04-28 \
  --top 15 \
  --min-trades 10 \
  --output .tmp/short-patterns-risk-expanded.csv
```

```bash
.venv/bin/python scripts/mine_short_patterns.py \
  --symbol NQM6 \
  --start-date 2026-04-27 \
  --end-date 2026-04-28 \
  --top 10 \
  --min-trades 8 \
  --start-minute 810 \
  --end-minute 1200 \
  --output .tmp/short-patterns-risk-us-rth.csv
```
