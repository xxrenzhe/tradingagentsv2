# NQM6 Best Strategy Readiness Audit

## Verdict

- Research status: `pass`.
- Live status: `blocked`.
- Best current research candidate: `adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3`.
- Live status remains blocked unless history, paper trading, and broker readiness gates all pass.

## Metrics

| metric | value |
| --- | --- |
| candidate | adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3 |
| research_status | pass |
| live_status | blocked |
| trades | 942 |
| net_points | 3318.0000 |
| max_drawdown_points | 190.8750 |
| net_to_drawdown | 17.3831 |
| profit_factor | 1.6891 |
| win_rate | 0.5488 |
| stability | 0.8476 |
| stress_net_points | 2376.0000 |
| worst_rolling_window_points | 494.6250 |

## Research Blockers

_No research blockers._

## Live Blockers

- `history_span_below_min:61<365`
- `databento_api_key_missing`
- `paper_validation:paper_outcomes_below_min:0<20`

## Raw Summary

```json
{
  "data_span": {
    "calendar_days": 61,
    "end": "2026-05-01 21:00:00+00:00",
    "exists": true,
    "path": ".tmp/mbp-history-features-cache.pkl",
    "rows": 60503,
    "start": "2026-03-02 23:59:00+00:00"
  },
  "paper_validation_gate": {
    "blockers": [
      "paper_outcomes_below_min:0<20"
    ],
    "metrics": {
      "consecutive_losses": 0,
      "ibkr_ready": 1,
      "ibkr_submitted": 1,
      "paper_net_points": 0.0,
      "paper_outcomes": 0,
      "paper_win_rate": 0.0,
      "readiness_blocker_count": 0
    },
    "status": "blocked",
    "thresholds": {
      "max_allowed_blocker_count": 0,
      "max_consecutive_losses": 4,
      "min_ibkr_ready": 1,
      "min_ibkr_submitted": 1,
      "min_paper_net_points": 0.0,
      "min_paper_outcomes": 20,
      "min_paper_win_rate": 45.0
    },
    "warnings": []
  },
  "ranking": {
    "balanced_best_count": 30,
    "candidate": {
      "avg_fold_score": NaN,
      "best_strategy_score": 7965.778861291979,
      "best_walkforward_score": 6483.912029268404,
      "candidate_universe": "walkforward_neighbors",
      "cost_1x_max_drawdown_points": NaN,
      "cost_1x_net_points": NaN,
      "cost_1x_profit_factor": NaN,
      "cost_1x_score": NaN,
      "cost_1x_stability": NaN,
      "cost_1x_trades": NaN,
      "cost_1x_win_rate": NaN,
      "cost_2x_max_drawdown_points": NaN,
      "cost_2x_net_points": NaN,
      "cost_2x_profit_factor": NaN,
      "cost_2x_score": NaN,
      "cost_2x_stability": NaN,
      "cost_2x_trades": NaN,
      "cost_2x_win_rate": NaN,
      "cost_3x_max_drawdown_points": NaN,
      "cost_3x_net_points": 2376.0,
      "cost_3x_profit_factor": NaN,
      "cost_3x_score": 8.384244762011335,
      "cost_3x_stability": NaN,
      "cost_3x_trades": NaN,
      "cost_3x_win_rate": NaN,
      "dd_delta": NaN,
      "defensive_mr_share": NaN,
      "enhanced_rank_score": NaN,
      "exit_mode": "reverse",
      "fallback": NaN,
      "family": "mean_reversion",
      "first_half_points": NaN,
      "fold_count": NaN,
      "folds_selected": 4.0,
      "full_cost_3x_max_drawdown_points": 268.75,
      "full_cost_3x_net_points": 2376.0,
      "full_cost_3x_profit_factor": 1.4520332936979785,
      "full_cost_3x_score": 8.384244762011335,
      "full_cost_3x_stability": 0.7933767336541183,
      "full_cost_3x_trades": 942.0,
      "full_cost_3x_win_rate": 0.5159235668789809,
      "full_max_drawdown_points": 190.875,
      "full_max_window_drawdown_points": 215.75,
      "full_median_window_net_points": 262.625,
      "full_min_window_net_points": 28.375,
      "full_min_window_score": 0.1623569542253521,
      "full_min_window_trades": 87.0,
      "full_net_points": 3318.0,
      "full_positive_window_count": 9.0,
      "full_positive_window_rate": 1.0,
      "full_profit_factor": 1.689078684353989,
      "full_score": 16.72066593343209,
      "full_stability": 0.8475673418250157,
      "full_trades": 942.0,
      "full_win_rate": 0.5488322717622081,
      "full_window_count": 9.0,
      "holding_minutes": NaN,
      "imbalance_threshold": 0.3,
      "live_ready": NaN,
      "live_ready_strict": NaN,
      "live_score": NaN,
      "local_best_robust_score": NaN,
      "local_median_robust_score": NaN,
      "local_min_window_net_points": NaN,
      "local_neighbor_count": NaN,
      "local_positive_rate": NaN,
      "local_rank_score": NaN,
      "lookback": 6.0,
      "max_fold_drawdown_points": NaN,
      "max_hold": 6.0,
      "max_spread_quantile": 0.75,
      "max_trades_per_day": NaN,
      "max_window_drawdown_points": NaN,
      "mean_high": NaN,
      "median_fold_net_points": NaN,
      "median_window_net_points": NaN,
      "min_depth_quantile": 0.25,
      "min_fold_net_points": 1444.375,
      "min_fold_score": NaN,
      "min_gap_minutes": NaN,
      "min_hold": 1.0,
      "min_window_delta": NaN,
      "min_window_net_points": 28.375,
      "min_window_score": NaN,
      "min_window_trades": NaN,
      "name": "adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3",
      "net_delta": NaN,
      "net_to_drawdown": 17.38310412573674,
      "pf_delta": NaN,
      "portfolio_score": NaN,
      "positive_fold_count": NaN,
      "positive_fold_rate": 1.0,
      "positive_window_count": NaN,
      "positive_window_rate": 1.0,
      "preserves_core_edge": NaN,
      "risk_control_pass": true,
      "risk_denominator": 190.875,
      "risk_first": NaN,
      "robust_score": NaN,
      "second_half_points": NaN,
      "seed_label": NaN,
      "seed_min_window_net_points": NaN,
      "seed_name": NaN,
      "seed_net_points": NaN,
      "seed_positive_window_rate": NaN,
      "seed_profit_factor": NaN,
      "seed_rank": NaN,
      "seed_stability": NaN,
      "seed_worst_cost_net_points": NaN,
      "selection_tier": "balanced_best",
      "session": "europe",
      "source": "advanced",
      "stability_delta": NaN,
      "stability_pass": true,
      "stability_rank_score": NaN,
      "stable_mr_share": NaN,
      "stable_ready": NaN,
      "stop_loss_points": NaN,
      "stress_net_points": 2376.0,
      "stress_to_drawdown": 12.447937131630647,
      "take_profit_points": NaN,
      "threshold": 0.8,
      "trend_high": NaN,
      "trend_vwap_share": NaN,
      "use_europe_defensive": NaN,
      "use_us_rth_trend": NaN,
      "volatility_filter": "all",
      "wf_max_fold_drawdown_points": 139.125,
      "wf_positive_fold_count": 4.0,
      "wf_positive_fold_rate": 1.0,
      "wf_test_net_points": 1444.375,
      "wf_test_trades": 329.0,
      "window_count": NaN,
      "worst_cost_delta": NaN,
      "worst_cost_net_points": NaN,
      "worst_cost_score": NaN
    },
    "candidate_count": 522,
    "exists": true,
    "path": ".tmp/mbp-best-strategy-ranking.csv"
  },
  "trade_diagnostics": {
    "avg_points": 3.522292993630573,
    "best_day_points": 304.25,
    "best_trade_points": 98.875,
    "direction_share": {
      "-1": 0.529723991507431,
      "1": 0.470276008492569
    },
    "exists": true,
    "exit_reason_share": {
      "reverse": 0.22717622080679406,
      "time": 0.772823779193206
    },
    "first_half_points": 1522.125,
    "max_drawdown_points": 190.875,
    "median_points": 1.375,
    "net_points": 3318.0,
    "path": ".tmp/mbp-best-strategy-trades.csv",
    "positive_day_rate": 0.8857142857142857,
    "rolling_positive_rate": 1.0,
    "rolling_window_count": 6,
    "second_half_points": 1795.875,
    "trades": 942,
    "win_rate": 0.5488322717622081,
    "worst_day_points": -64.5,
    "worst_incomplete_window_points": 59.5,
    "worst_rolling_window_points": 494.625,
    "worst_trade_points": -81.875
  }
}
```
