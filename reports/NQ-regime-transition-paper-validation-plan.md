# NQ Regime-Transition Paper Validation Package

## Decision

Stop optimizing the screenshot three-trend strategy as a standalone system. Its best clean holdout result is too small versus the promoted regime-transition candidates. The next useful step is paper validation of the stronger range-compression to displacement-breakout family.

- Primary paper candidate: `optimized50_2r5_quality`.
- Historical sample: `2010-2026`, `442` trades, `3479.65` NQ points, PF `1.968`, max DD `210.75` points.
- Execution symbol: `MNQ` `202606`, quantity `1`.
- Machine config: `reports/NQ-regime-transition-paper-validation-config.json`.
- Candidate CSV: `reports/NQ-regime-transition-paper-validation-plan.csv`.

## Market Feature

The promoted setup is not a generic indicator signal. It is a `compression -> displacement -> trend start` pattern:

- Compression: prior rolling range width is small relative to ATR120 and directional efficiency is low.
- Displacement: the signal candle expands to at least the configured ATR30 multiple with a large real body.
- Breakout: close must exceed the prior range high plus `max(0.25, 0.05 * ATR30)`.
- Participation: optional volume z-score filter keeps the cleanest candidate away from low-participation breakouts.
- Timing: only `us_late`, meaning `20:00-22:59 UTC`.

## Strategy Rules

- Direction is long only.
- Entry is next 1-minute bar open after the qualifying breakout candle.
- Stop is the breakout candle low minus `max(0.25, 0.10 * ATR30)`; reject trades with stop distance below `4` or above `80` NQ points.
- Target is fixed R from actual stop distance; top candidates use `2.5R`, the higher-frequency fallback uses `2.25R`.
- Timeout exit is `180` or `240` minutes depending on candidate.
- Same-bar stop/target ambiguity is resolved stop-first; no overlapping trades inside this candidate family.

## Paper Gate

- Run only one candidate at a time, starting with `optimized50_2r5_quality`.
- Start dry-run with the IBKR historical 1-minute OHLCV adapter; submit only after one clean session of signal parity.
- Minimum paper sample is `30` outcomes, positive net points, PF `>= 1.20`, win rate `>= 35%`, and no more than `4` consecutive losses.
- Halt immediately at `-80` NQ points daily, `-160` weekly, any bracket/order rejection, existing exposure conflict, adapter mismatch, or real-account detection.

## Adapter Gap

`run_nq_regime_transition_paper_trader.py` is the safe operator entrypoint. It wraps the lower-level `run_ibkr_live_paper_trader.py`, uses IBKR historical `1 min` TRADES bars for OHLCV/volume, and blocks `--submit` unless the parity file passes unless `--force-without-parity` is explicitly used.

## Candidate Plan

| priority | label | trades | net_points | profit_factor | win_rate | max_drawdown_points | net_to_drawdown | positive_year_rate | positive_90d_rate | implementation_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | optimized50_2r5_quality | 442 | 3479.6521 | 1.9677 | 0.4276 | 210.7504 | 16.5108 | 0.7647 | 0.6508 | live_ohlcv_adapter_ready_needs_parity_validation |
| 2 | defensive45_2r5_loweff | 593 | 3398.3338 | 1.7051 | 0.3912 | 230.0867 | 14.7698 | 0.8750 | 0.6333 | live_ohlcv_adapter_ready_needs_parity_validation |
| 3 | short45_2r25_netdd | 1166 | 4118.2479 | 1.4229 | 0.3842 | 333.1319 | 12.3622 | 0.7059 | 0.6190 | live_ohlcv_adapter_ready_needs_parity_validation |

## Commands After Adapter

### optimized50_2r5_quality

Dry run:

```bash
.venv/bin/python scripts/run_nq_regime_transition_paper_trader.py --strategy-id optimized50_2r5_quality --selected-alias optimized50_2r5_quality --symbol MNQ --contract-month 202606 --quantity 1 --paper-validation-accrual-mode --min-paper-outcomes 30 --min-paper-net-points 0 --min-paper-win-rate 35 --max-consecutive-losses 4 --daemon --interval-seconds 30 --max-iterations 0
```

Submit:

```bash
.venv/bin/python scripts/run_nq_regime_transition_paper_trader.py --strategy-id optimized50_2r5_quality --selected-alias optimized50_2r5_quality --symbol MNQ --contract-month 202606 --quantity 1 --paper-validation-accrual-mode --min-paper-outcomes 30 --min-paper-net-points 0 --min-paper-win-rate 35 --max-consecutive-losses 4 --daemon --interval-seconds 30 --max-iterations 0 --submit
```

### defensive45_2r5_loweff

Dry run:

```bash
.venv/bin/python scripts/run_nq_regime_transition_paper_trader.py --strategy-id defensive45_2r5_loweff --selected-alias defensive45_2r5_loweff --symbol MNQ --contract-month 202606 --quantity 1 --paper-validation-accrual-mode --min-paper-outcomes 30 --min-paper-net-points 0 --min-paper-win-rate 35 --max-consecutive-losses 4 --daemon --interval-seconds 30 --max-iterations 0
```

Submit:

```bash
.venv/bin/python scripts/run_nq_regime_transition_paper_trader.py --strategy-id defensive45_2r5_loweff --selected-alias defensive45_2r5_loweff --symbol MNQ --contract-month 202606 --quantity 1 --paper-validation-accrual-mode --min-paper-outcomes 30 --min-paper-net-points 0 --min-paper-win-rate 35 --max-consecutive-losses 4 --daemon --interval-seconds 30 --max-iterations 0 --submit
```

### short45_2r25_netdd

Dry run:

```bash
.venv/bin/python scripts/run_nq_regime_transition_paper_trader.py --strategy-id short45_2r25_netdd --selected-alias short45_2r25_netdd --symbol MNQ --contract-month 202606 --quantity 1 --paper-validation-accrual-mode --min-paper-outcomes 30 --min-paper-net-points 0 --min-paper-win-rate 35 --max-consecutive-losses 4 --daemon --interval-seconds 30 --max-iterations 0
```

Submit:

```bash
.venv/bin/python scripts/run_nq_regime_transition_paper_trader.py --strategy-id short45_2r25_netdd --selected-alias short45_2r25_netdd --symbol MNQ --contract-month 202606 --quantity 1 --paper-validation-accrual-mode --min-paper-outcomes 30 --min-paper-net-points 0 --min-paper-win-rate 35 --max-consecutive-losses 4 --daemon --interval-seconds 30 --max-iterations 0 --submit
```
