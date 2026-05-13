# NQ Lightglow + Timecell Paper-Readiness Audit

Status: `blocked`

This report does not approve live trading. It audits whether the research combo can enter guarded paper validation.

## Headline

- Raw trades: `13,157`
- Raw net points: `60583.62`
- Raw PF: `1.406`
- Risk-budgeted net points: `44790.42`
- Risk-budgeted PF: `2.909`

## Blockers

- `missing_live_adapter_for_lightglow_and_timecell`
- `timecell_0.05_weight_not_executable_as_integer_futures_contract`
- `no_forward_paper_outcomes_for_this_strategy_id`
- `paper_adapter_readiness_missing`

## Next Action

implement adapter and run paper validation

## Loss Learning

- Verdict: `not_selected`
- Selected OOS delta points: `0.00`
