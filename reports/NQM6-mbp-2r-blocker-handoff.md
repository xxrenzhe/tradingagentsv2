# NQM6 60% Fixed-2R Blocker Handoff

## Current Status

The 60% win-rate fixed-2R live-strategy objective is blocked, not complete. The machine audit in `reports/NQM6-mbp-2r-goal-readiness-audit.md` currently reports:

- `no_60wr_2r_blackbox_candidate`
- `history_span_below_min:61<365`
- `databento_api_key_missing`
- `ibkr_account_missing`
- `paper_validation:ibkr_submitted_below_min:0<1`
- `paper_validation:paper_outcomes_below_min:0<20`
- `paper_validation:readiness_blockers_above_max:14>0`

## Blocker-to-Bead Map

| Blocker | Bead | Required outcome |
| --- | --- | --- |
| `history_span_below_min:61<365` | `TradingAgentsV2-p6o` | Build at least 365 calendar days of NQM6 MBP/minute features and rerun the 2R audits. |
| `databento_api_key_missing` | `TradingAgentsV2-p6o` | Configure data access or provide an equivalent longer feature cache. |
| `ibkr_account_missing` | `TradingAgentsV2-5ci` | Configure IBKR paper account access before any live-readiness claim. |
| `paper_validation:*` | `TradingAgentsV2-5ci` | Submit bracketed paper trades, record outcomes, and pass `scripts/check_paper_validation_gate.py`. |
| `market_data_not_ready` / bid-ask blocker | `TradingAgentsV2-qyt` | Resolve NQ bid/ask market data readiness for IBKR paper execution. |
| `no_60wr_2r_blackbox_candidate` | `TradingAgentsV2-6ce` | Move beyond current MBP minute-rule families and find a candidate that passes purged black-box validation. |

## Dependency Graph

- `TradingAgentsV2-cur` depends on:
  - `TradingAgentsV2-p6o`
  - `TradingAgentsV2-5ci`
  - `TradingAgentsV2-6ce`
- `TradingAgentsV2-5ci` depends on:
  - `TradingAgentsV2-qyt`

## Completion Gate

Do not close `TradingAgentsV2-cur` or mark the goal complete until:

1. `scripts/audit_mbp_2r_goal_readiness.py` returns exit code `0`.
2. At least one fixed-2R candidate has `blackbox_pass = true`.
3. The history span is at least 365 calendar days, or the long-term threshold is explicitly revised.
4. Paper validation passes with submitted orders and recorded outcomes.
5. The selected strategy is documented as a tradeable implementation, not only a diagnostic feature bin.
