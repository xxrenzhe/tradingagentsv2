# NQ Price-Action Setup Families

This adds two bar-only setup families to approximate the chart patterns shown by the user.

## Support Reclaim

Approximates a sweep-and-reclaim reversal like a low probe followed by a bounce.

- Long: price sweeps below the prior lookback low, then closes back above that support by a configurable fraction of the prior range.
- Short: price sweeps above the prior lookback high, then closes back below that resistance by a configurable fraction of the prior range.
- Candidate family: `support_reclaim`.
- Default thresholds in the NQ walk-forward search: `0.0002`, `0.0005`, `0.001`.

## Breakout Retest

Approximates breakout continuation after a level is broken and then defended.

- Long: the prior bar breaks above the lookback high, the current bar retests that level, then closes back above it by a configurable fraction of the prior range.
- Short: the prior bar breaks below the lookback low, the current bar retests that level, then closes back below it by a configurable fraction of the prior range.
- Candidate family: `breakout_retest`.
- Default thresholds in the NQ walk-forward search: `0.0002`, `0.0005`, `0.001`.

## Integration

- Signal implementation: `tradingagents/backtesting/short_patterns.py`.
- NQ 5y search CLI integration: `scripts/search_nq_bar_best_strategy_walkforward.py`.
- LLM debate rule text: `scripts/rank_nq_bar_best_strategy.py`.
- Regression tests: `tests/test_nq_price_action_setups.py`.

These setup families are now searchable in the 5-year 1-minute bar walk-forward workflow. They still require walk-forward ranking and gate checks before being considered paper or live candidates.
