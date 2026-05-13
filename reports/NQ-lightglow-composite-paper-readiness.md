# NQ Lightglow + Timecell Paper-Readiness Audit

Status: `blocked`

This report does not approve live trading. It audits whether the research combo can enter guarded paper validation.

## Strategy Principle And Market Features

- Lightglow uses Premium/Discount location, swing zones, EMA context, volume-price pressure, and range position; action maps are selected only from train windows.
- Timecell uses a 2010-2019 trained month/hour directional map at `0.05` risk weight; current conclusion keeps it shadow-only because the contract granularity is not executable.
- Extreme Timecell long-against-downtrend cases can be detected, but reverse-short validation is `reverse_not_proven`; use it as avoid-long risk control only.

## Frozen Configuration

- Walk-forward windows: `2020-2021 -> 2022`, `2020-2022 -> 2023`, `2021-2023 -> 2024`, `2022-2024 -> 2025`.
- Lightglow paper action: MNQ validation only, starting smaller than one NQ.
- Timecell paper action: shadow-record unless a separate integer-contract rule is approved.

## Headline

- Raw trades: `13,157`
- Raw net points: `60583.62`
- Raw PF: `1.406`
- Risk-budgeted net points: `44790.42`
- Risk-budgeted PF: `2.909`
- Leakage passed: `True`
- Walk-forward rows: `4`

## Leakage, Walk-Forward, And Stress

- Future perturbation audit hashes pre-cutoff OHLCV features, Lightglow signal columns, and executable trade signatures.
- Same-bar exits and entry-before-signal violations are checked in the leakage table.
- Stress coverage includes extra cost, 1/2/3 bar latency, fixed slippage, ATR/range slippage, and session-specific slippage.

## Risk Budget And Paper Validation

- Risk budget prevents weak-edge coverage from being scaled equally with the main Lightglow component.
- The paper validation plan logs signal timestamps, order/fill fields, slippage, exit reason, PnL, risk state, reject reasons, and exception halts.
- Current status is blocked until live/paper adapters can express Lightglow and Timecell signals, exits, position sizing, and risk controls.

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

## Reverse Diagnostic

- Verdict: `reverse_not_proven`
- Selected OOS delta vs baseline: `0.00`
