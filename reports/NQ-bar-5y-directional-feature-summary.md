# NQ 5y Direction-Filtered Feature Backtest Summary

## Verdict

This search re-ran the 5-year NQ 1-minute walk-forward with direction filters (`long` / `short`) across selected profitable families and sessions.

Result: the strongest additional features are `us_late` long-only setups. They are profitable research candidates and useful LLM debate seeds, but none passed the strict `risk_controlled` / `live_ready` ranking gate because at least one selected fold stayed negative for the top rows.

## Best New Profitable Features

| Candidate | Family | Direction | Session | Rule | Trades | Net points | Avg test PF | Positive folds | Stress fold | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late` | Mean reversion | Long only | `20:00-23:00 UTC` | Buy when close is below 30m mean by more than `1.4` rolling std-dev; hold 60m | `398` | `6205.25` | `1.7309` | `80%` | `-1128.375` | Highest net points, but one bad fold blocks risk gate |
| `bar_best_momentum_lb60_thr0.0006_hold30_long_us_late` | Momentum | Long only | `20:00-23:00 UTC` | Buy when 60m return exceeds `0.0006`; hold 30m | `372` | `4563.75` | `1.7967` | `80%` | `-8.875` | Nearly risk-controlled; only slightly negative stress fold |
| `bar_best_mean_reversion_lb10_thr1_hold30_long_us_late` | Mean reversion | Long only | `20:00-23:00 UTC` | Buy when close is below 10m mean by more than `1.0` rolling std-dev; hold 30m | `369` | `4483.875` | `1.5586` | `100%` | `1157.625` | Best fold consistency among the top rows |
| `bar_best_support_reclaim_lb15_thr0.0002_hold30_long_us_late` | Support reclaim | Long only | `20:00-23:00 UTC` | Buy after sweep below prior 15m low and reclaim; hold 30m | `496` | `3576.75` | `1.3423` | `75%` | `-67.375` | Price-action feature remains profitable after long-only filter |
| `bar_best_support_reclaim_lb15_thr0.0002_hold60_short_us_late` | Support reclaim | Short only | `20:00-23:00 UTC` | Short after sweep above prior 15m high and failed reclaim; hold 60m | `173` | `2602.875` | `1.3121` | `100%` | `952.75` | Best new short-only feature in this focused search |

## Interpretation

- Direction filtering materially improves feature quality. The prior combined long/short variants often hid one profitable side behind a weak opposite side.
- The strongest common context is `us_late` (`20:00-23:00 UTC`), matching earlier price-action results.
- The best candidate for further tightening is `bar_best_mean_reversion_lb10_thr1_hold30_long_us_late`, because its selected folds and stress fold are all positive.
- The best nearly-risk-controlled candidate is `bar_best_momentum_lb60_thr0.0006_hold30_long_us_late`; it missed the strict stress gate by only `8.875` points.
- These remain research/paper-validation candidates until current-market confirmation, paper validation, and stricter stability gates pass.

## Artifacts

- Backtest report: `reports/NQ-bar-5y-directional-feature-discovery.md`.
- Ranking/debate report: `reports/NQ-bar-5y-directional-strategy-ranking.md`.
- Aggregate CSV: `.tmp/nq-bar-5y-directional-walkforward-aggregate.csv`.
- Trade rows CSV: `.tmp/nq-bar-5y-directional-walkforward-trades.csv`.
