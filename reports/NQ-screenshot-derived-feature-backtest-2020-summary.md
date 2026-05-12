# NQ Screenshot-Derived Feature Backtest Summary

Date: 2026-05-12

## Scope

This run evaluated the screenshot-derived NQ 1-minute feature families added after manual chart review:

- `range_compression_breakout_long`
- `range_compression_breakdown_short`
- `supply_sweep_rejection_short`
- `demand_sweep_reclaim_long`
- `low_base_reclaim_long`
- `high_base_reject_short`

Data window: 2020-01-01 through 2026-04-28, Databento NQ 1-minute continuous bars.

## Feature Discovery

Full feature discovery produced:

- Feature rows: 2,230,054
- Market feature/session variants: 168
- Event rows: 2,341,450
- Summary rows: 168

Top screenshot-derived event features by opportunity score:

| Feature | Events | Score | 30m Favorable | 30m Mean Move |
|---|---:|---:|---:|---:|
| `demand_sweep_reclaim_long_us_rth` | 16,043 | 4.381 | 52.42% | +0.64 |
| `range_compression_breakout_long_us_rth` | 4,214 | 4.369 | 52.52% | +0.31 |
| `low_base_reclaim_long_us_rth` | 5,624 | 4.314 | 52.49% | +0.01 |
| `range_compression_breakdown_short_us_rth` | 3,965 | 4.256 | 47.67% | +0.35 |
| `low_base_reclaim_long_ldn_ny` | 11,280 | 4.104 | 53.13% | +0.40 |

Interpretation: the screenshot-derived features are not empty labels. Several entered the all-feature top group, especially RTH demand reclaim, compression breakout, low-base reclaim, and compression breakdown.

## Focused Template Backtest

First strategy-template pass used five highest-priority screenshot features and 360 templates.

Best walk-forward result:

- Template: `range_compression_breakdown_short_us_rth_midpoint_hold_event_extreme_bracket_rr1_h60_c2_pb0.25_atr1_ff5`
- Feature: `range_compression_breakdown_short_us_rth`
- Selected folds: 4
- Test trades: 704
- Test net points: +689.46
- Win rate: 50.85%
- Profit factor: 1.07
- Payoff ratio: 1.04
- Positive test fold rate: 100%
- Max drawdown: 820.20 points

Interpretation: this short breakdown branch is the more stable candidate, but the edge is thin and drawdown is large.

## Refined Template Backtest

Second pass narrowed to:

- `range_compression_breakdown_short_us_rth`
- `low_base_reclaim_long_us_rth`

It tested 768 core bracket templates.

Best headline result:

- Template: `low_base_reclaim_long_us_rth_confirm_break_hybrid_event_atr_bracket_rr1.5_h45_c1_pb0.25_atr1_ff5`
- Feature: `low_base_reclaim_long_us_rth`
- Selected folds: 1
- Test trades: 158
- Test net points: +421.58
- Win rate: 44.30%
- Profit factor: 1.29
- Payoff ratio: 1.62
- Positive test fold rate: 100%
- Max drawdown: 251.12 points

More stable refined short branch:

- Template: `range_compression_breakdown_short_us_rth_confirm_break_event_extreme_bracket_rr1.25_h45_c1_pb0.25_atr0.75_ff5`
- Selected folds: 4
- Test trades: 329
- Test net points: +336.05
- Win rate: 45.29%
- Profit factor: 1.06
- Payoff ratio: 1.28
- Positive test fold rate: 50%
- Max drawdown: 764.25 points

## LLM Review

LLM status: parsed.

Summary:

> 优先保留两条主线：short breakdown_confirm_break 与 long base_reclaim_confirm_break。前者样本大、全样本和WF都更稳定；后者边际更强但脆弱。其余多数模板的问题不是“方向完全错”，而是确认/止损/退出不够匹配：要么确认太多稀释信号，要么持有太久拖累效率。

Key failure modes:

- PF close to 1 means the edge is frequency-based and thin.
- Positive mean with negative median indicates right-tail dependence.
- More confirmation can dilute the signal.
- 90-minute holds often reduce efficiency compared with 45-60 minutes.
- Drawdown remains too large for promotion.

## Next Research

- Keep `range_compression_breakdown_short_us_rth` as the stable benchmark branch.
- Keep `low_base_reclaim_long_us_rth` as a convex but fragile branch.
- Test `range_compression_breakdown_short_us_rth` with confirm bars 1, 45/60-minute exits, RR 1.25/1.5, and stricter fast-fail logic.
- Test `low_base_reclaim_long_us_rth` with quality filters: volatility expansion, larger reclaim body, stronger volume/CMF/Force confirmation.
- Add staged exits: 50% at 1R, remainder at 1.5R/2R, especially for low-base reclaim.
- Split by RTH sub-session because these 1-minute structures appear session-sensitive.

## Artifacts

- Discovery report: `reports/NQ-market-feature-discovery-screenshot-gap-2020.html`
- Focused template report: `reports/NQ-market-feature-strategy-template-screenshot-gap-focused-2020.html`
- Refined template report: `reports/NQ-market-feature-strategy-template-screenshot-gap-refined-2020.html`
- Refined aggregate: `.tmp/nq-market-feature-template-aggregate-screenshot-gap-refined-2020.csv`
- LLM review: `.tmp/nq-market-feature-template-llm-screenshot-gap-refined-2020.json`
