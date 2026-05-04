# NQM6 60% 2R Goal Readiness Audit

Status: `blocked`

## Blockers

- `no_60wr_2r_blackbox_candidate`
- `history_span_below_min:61<365`
- `databento_api_key_missing`
- `ibkr_account_missing`
- `paper_validation:ibkr_submitted_below_min:0<1`
- `paper_validation:paper_outcomes_below_min:0<20`
- `paper_validation:readiness_blockers_above_max:19>0`

## Checklist

### >=60% win rate with fixed 2R

Status: `blocked`

```json
{
  "bar_only_walkforward_2r": {
    "exists": true,
    "passes": 0,
    "path": ".tmp/nq-bar-2r-walkforward-discovery-small.csv",
    "rows": 289
  },
  "closest_pair_neighborhood": {
    "exists": true,
    "passes": 0,
    "path": ".tmp/mbp-2r-purged-walkforward-us-late-pair-neighborhood.csv",
    "rows": 0
  },
  "expanded_2r_blackbox": {
    "exists": true,
    "passes": 0,
    "path": ".tmp/mbp-2r-expanded-diagnostics-merged.csv",
    "rows": 25000
  },
  "label_rule_2r_blackbox": {
    "exists": true,
    "passes": 0,
    "path": ".tmp/mbp-2r-label-rules-merged.csv",
    "rows": 0
  },
  "model_walkforward_2r": {
    "exists": true,
    "passes": 0,
    "path": ".tmp/mbp-2r-model-walkforward.csv",
    "rows": 3
  },
  "pair_feature_feasibility": {
    "exists": true,
    "passes": 0,
    "path": ".tmp/mbp-2r-feasibility-pair-representative-bins.csv",
    "rows": 360
  },
  "purged_walkforward_2r": {
    "exists": true,
    "passes": 0,
    "path": ".tmp/mbp-2r-purged-walkforward-all-core.csv",
    "rows": 0
  },
  "single_feature_feasibility": {
    "exists": true,
    "passes": 0,
    "path": ".tmp/mbp-2r-feasibility-representative-feature-bins.csv",
    "rows": 216
  },
  "state_walkforward_2r": {
    "exists": true,
    "passes": 0,
    "path": ".tmp/mbp-2r-state-walkforward-focused.csv",
    "rows": 135
  },
  "strict_2r_blackbox": {
    "exists": true,
    "passes": 0,
    "path": ".tmp/mbp-2r-blackbox.csv",
    "rows": 0
  }
}
```

### black-box / purged validation

Status: `blocked`

```json
{
  "bar_only_walkforward_rows": 289,
  "closest_followup_rows": 0,
  "model_walkforward_rows": 3,
  "purged_rows": 0,
  "state_walkforward_rows": 135,
  "strict_split_rows": 0
}
```

### long-term evidence

Status: `blocked`

```json
{
  "calendar_days": 61,
  "end": "2026-05-01 21:00:00+00:00",
  "exists": true,
  "path": ".tmp/mbp-history-features-cache.pkl",
  "rows": 60503,
  "start": "2026-03-02 23:59:00+00:00"
}
```

### direct live/paper readiness

Status: `blocked`

```json
{
  "databento_api_key_present": false,
  "ibkr_account_present": false,
  "paper_gate": {
    "blockers": [
      "ibkr_submitted_below_min:0<1",
      "paper_outcomes_below_min:0<20",
      "readiness_blockers_above_max:19>0"
    ],
    "metrics": {
      "consecutive_losses": 0,
      "ibkr_ready": 1,
      "ibkr_submitted": 0,
      "paper_net_points": 0.0,
      "paper_outcomes": 0,
      "paper_win_rate": 0.0,
      "readiness_blocker_count": 19
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
    "warnings": [
      "market_data_not_ready:IBKR market data is not order-ready",
      "not_connected:IBKR socket/API connection is not consistently available"
    ]
  }
}
```

## Raw Summary

```json
{
  "checks": {
    "bar_only_walkforward_2r": {
      "exists": true,
      "passes": 0,
      "path": ".tmp/nq-bar-2r-walkforward-discovery-small.csv",
      "rows": 289
    },
    "closest_pair_neighborhood": {
      "exists": true,
      "passes": 0,
      "path": ".tmp/mbp-2r-purged-walkforward-us-late-pair-neighborhood.csv",
      "rows": 0
    },
    "expanded_2r_blackbox": {
      "exists": true,
      "passes": 0,
      "path": ".tmp/mbp-2r-expanded-diagnostics-merged.csv",
      "rows": 25000
    },
    "label_rule_2r_blackbox": {
      "exists": true,
      "passes": 0,
      "path": ".tmp/mbp-2r-label-rules-merged.csv",
      "rows": 0
    },
    "model_walkforward_2r": {
      "exists": true,
      "passes": 0,
      "path": ".tmp/mbp-2r-model-walkforward.csv",
      "rows": 3
    },
    "pair_feature_feasibility": {
      "exists": true,
      "passes": 0,
      "path": ".tmp/mbp-2r-feasibility-pair-representative-bins.csv",
      "rows": 360
    },
    "purged_walkforward_2r": {
      "exists": true,
      "passes": 0,
      "path": ".tmp/mbp-2r-purged-walkforward-all-core.csv",
      "rows": 0
    },
    "single_feature_feasibility": {
      "exists": true,
      "passes": 0,
      "path": ".tmp/mbp-2r-feasibility-representative-feature-bins.csv",
      "rows": 216
    },
    "state_walkforward_2r": {
      "exists": true,
      "passes": 0,
      "path": ".tmp/mbp-2r-state-walkforward-focused.csv",
      "rows": 135
    },
    "strict_2r_blackbox": {
      "exists": true,
      "passes": 0,
      "path": ".tmp/mbp-2r-blackbox.csv",
      "rows": 0
    }
  },
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
      "ibkr_submitted_below_min:0<1",
      "paper_outcomes_below_min:0<20",
      "readiness_blockers_above_max:19>0"
    ],
    "metrics": {
      "consecutive_losses": 0,
      "ibkr_ready": 1,
      "ibkr_submitted": 0,
      "paper_net_points": 0.0,
      "paper_outcomes": 0,
      "paper_win_rate": 0.0,
      "readiness_blocker_count": 19
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
    "warnings": [
      "market_data_not_ready:IBKR market data is not order-ready",
      "not_connected:IBKR socket/API connection is not consistently available"
    ]
  },
  "total_2r_passes": 0
}
```
