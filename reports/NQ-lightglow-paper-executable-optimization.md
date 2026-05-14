# NQ Lightglow Paper-Executable Optimization

Status: `promote_to_paper_candidate`

This is a causal optimization of the paper-executable Lightglow-only subset. Timecell remains shadow-only.

## Result

- OOS baseline trades: `5002`, net `40950.25`, PF `4.147`.
- Optimized trades: `4596`, net `41596.25`, PF `4.569`.
- Decision: `promote_to_paper_candidate`.

## Blockers

- none

## Guardrails

- Filters are selected on train years only and applied to the next test year.
- No Timecell trades are included in executable performance.
- Paper execution remains dry-run first; submit is blocked until the timed-exit manager is available.
- This report does not approve live trading.
