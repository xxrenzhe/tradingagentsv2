# NQ Promotion Shortlist Recent OOS Check

This report evaluates promoted and paper-watchlist NQ candidates on the most recent trade window available in the 5-year trade rows.

- Shortlist: `.tmp/nq-feature-promotion-shortlist.csv`
- Trades input: `.tmp/nq-bar-5y-directional-walkforward-trades.csv`
- Feature cache: `.tmp/nq-bar-5y-continuous-features-cache.pkl`
- Recent months: `12`
- Rows evaluated: `10`

## passes_recent_oos

```csv
tier,candidate,filter,evidence_type,months,recent_start,recent_end,trades,net_points,profit_factor,win_rate,positive_month_rate,min_month_net_points,months_with_trades,baseline_trades,baseline_net_points,net_improvement,recent_verdict,next_action
promote_to_strict_gate,bar_best_mean_reversion_lb10_thr1_hold30_long_us_late,none,directional_walkforward,12,2025-04-06,2026-04-06,369,4483.875,1.595290251916758,0.5284552845528455,0.8571428571428571,-418.0,7,369,4483.875,0.0,passes_recent_oos,paper_trade_small_size
promote_to_strict_gate,bar_best_momentum_lb60_thr0.0006_hold60_long_us_late,none,directional_walkforward,12,2025-04-06,2026-04-06,52,2101.5,1.873486777160077,0.5576923076923077,1.0,369.25,4,52,2101.5,0.0,passes_recent_oos,paper_trade_small_size
paper_watchlist,bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,none,directional_walkforward,12,2025-04-06,2026-04-06,83,1159.875,1.237442104455078,0.5542168674698795,0.75,-49.125,4,83,1159.875,0.0,passes_recent_oos,paper_trade_small_size
```

## watch_recent_oos

```csv
tier,candidate,filter,evidence_type,months,recent_start,recent_end,trades,net_points,profit_factor,win_rate,positive_month_rate,min_month_net_points,months_with_trades,baseline_trades,baseline_net_points,net_improvement,recent_verdict,next_action
paper_watchlist,bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,return_1m_negative,past_fold_selected,12,2025-04-06,2026-04-06,74,1154.25,1.250760373669346,0.5405405405405406,0.5,-61.75,4,83,1159.875,-5.625,watch_recent_oos,prefer_unfiltered_baseline
paper_watchlist,bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,z_30_negative,past_fold_selected,12,2025-04-06,2026-04-06,80,1134.5,1.2343826666322342,0.5625,0.75,-49.125,4,83,1159.875,-25.375,watch_recent_oos,prefer_unfiltered_baseline
```

## fails_recent_oos

No rows.

## insufficient_recent_trades

```csv
tier,candidate,filter,evidence_type,months,recent_start,recent_end,trades,net_points,profit_factor,win_rate,positive_month_rate,min_month_net_points,months_with_trades,baseline_trades,baseline_net_points,net_improvement,recent_verdict,next_action
paper_watchlist,bar_best_momentum_lb60_thr0.0006_hold30_long_us_late,none,directional_walkforward,12,2025-04-06,2026-04-06,0,0.0,inf,0.0,0.0,0.0,0,0,0.0,0.0,insufficient_recent_trades,collect_more_recent_trades
paper_watchlist,bar_best_support_reclaim_lb15_thr0.0002_hold60_short_us_late,none,directional_walkforward,12,2025-04-06,2026-04-06,0,0.0,inf,0.0,0.0,0.0,0,0,0.0,0.0,insufficient_recent_trades,collect_more_recent_trades
paper_watchlist,bar_best_support_reclaim_lb15_thr0.0005_hold60_short_us_late,none,directional_walkforward,12,2025-04-06,2026-04-06,0,0.0,inf,0.0,0.0,0.0,0,0,0.0,0.0,insufficient_recent_trades,collect_more_recent_trades
paper_watchlist,bar_best_support_reclaim_lb15_thr0.001_hold60_short_us_late,none,directional_walkforward,12,2025-04-06,2026-04-06,0,0.0,inf,0.0,0.0,0.0,0,0,0.0,0.0,insufficient_recent_trades,collect_more_recent_trades
paper_watchlist,bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,z_30_negative,past_fold_selected,12,2025-04-06,2026-04-06,0,0.0,inf,0.0,0.0,0.0,0,0,0.0,0.0,insufficient_recent_trades,collect_more_recent_trades
```

## Decision

- Candidates that pass recent OOS can move to small-size paper validation.
- Candidates that fail recent OOS should not be promoted even if their 5-year aggregate looks strong.
- Insufficient recent trade counts need more live/paper observation rather than parameter mining.
