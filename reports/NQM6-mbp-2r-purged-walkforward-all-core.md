# NQM6 Purged Walk-Forward 2R Search

Feature rows: 60,200
Date range: 2026-03-02 23:59:00+00:00 to 2026-05-01 21:00:00+00:00
Train days: 20
Purge days: 2
Test days: 5
Step days: 5
Stop-loss points: 4.0, 8.0, 12.0
Horizons: 30, 60
Sessions: all

## Completion Audit

- Requirement: >=60% test win rate. Gate requires `test_win_rate >= 0.60`.
- Requirement: fixed 2R. Every candidate uses `take_profit_points = 2 * stop_loss_points`.
- Requirement: black-box testing. Every fold learns predicates only on prior train dates, skips purge dates, then evaluates future test dates.
- Requirement: not overfit. This report still cannot prove live non-overfit unless a candidate passes all folds and then survives paper/live validation.
- Requirement: directly live-ready. Not satisfied without broker paper fills, slippage, rejects, and order-routing checks.

Training-selected fold candidates tested: 0
Black-box passed rows: 0

## Verdict

No train-only purged walk-forward 60% win-rate 2R candidate passed. This adds another negative black-box result beyond the fixed grid and direct label-rule searches.

## Top Tested Candidates

_No rows._
