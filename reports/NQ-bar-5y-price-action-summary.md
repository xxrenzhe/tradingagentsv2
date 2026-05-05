# NQ 5y Price-Action Setup Backtest Summary

## Verdict

The newly added price-action setup families were backtested on the 5-year NQ 1-minute bar history from `2021-04-28` through `2026-04-27`.

Result: two candidates passed the `risk_controlled` ranking tier, but no candidate reached `balanced_best` / `live_ready`.

## Best Risk-Controlled Candidates

| Candidate | Setup | Session | Rule | Trades | Net points | Profit factor | Positive fold rate | Worst selected fold | Direction skew | Readiness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `bar_best_breakout_retest_lb10_thr0.0002_hold15_us_late` | Breakout retest | `20:00-23:00 UTC` | Prior bar breaks 10m high/low, current bar retests the level and closes back beyond it by `0.0002` of prior range | `481` | `1574.375` | `1.2759` | `100%` | `290.125` | Short side carries most edge: `1530.5` net points vs long `43.875` | `risk_controlled` |
| `bar_best_support_reclaim_lb60_thr0.001_hold15_us_late` | Support reclaim | `20:00-23:00 UTC` | Sweep prior 60m low/high, then close back beyond support/resistance by `0.001` of prior range | `386` | `782.0` | `1.2802` | `100%` | `76.5` | Long side carries edge: `1081.875` net points vs short `-299.875` | `risk_controlled` |

## Interpretation

- The user-provided breakout image maps best to `breakout_retest`; the current 5-year result says the short version is much stronger than the long version in this specific parameter set.
- The user-provided reversal image maps best to `support_reclaim`; the current 5-year result says the long version is stronger and short attempts should be filtered.
- Both candidates are useful LLM debate seeds because they have positive fold coverage, positive stress fold net points, and explicit long/short directional evidence.
- Neither candidate is live-ready because stability did not pass the `balanced_best` tier. Use them for paper validation and LLM debate, not automatic live orders.

## Artifacts

- Backtest report: `reports/NQ-bar-5y-price-action-feature-discovery.md`.
- Ranking and debate pack report: `reports/NQ-bar-5y-price-action-strategy-ranking.md`.
- Setup family documentation: `reports/NQ-price-action-setup-families.md`.
- Aggregate CSV: `.tmp/nq-bar-5y-price-action-walkforward-aggregate.csv`.
- Trade rows CSV: `.tmp/nq-bar-5y-price-action-walkforward-trades.csv`.
