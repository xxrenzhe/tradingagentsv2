# NQ 5y 1m Trading Logic Audit

## Conclusion

The intended trading logic is correct as a research workflow:

1. Use historical 1-minute bars to discover repeatable long/short feature triggers.
2. Convert the best backtest candidates into structured evidence and an LLM debate pack.
3. Let the LLM debate the bull case, bear case, and risk case before choosing long, short, or no-trade.
4. Submit orders only if the deterministic strategy gate and current-market checks both pass.

The current 5-year NQ bar-only research does not produce an automatic live-trading candidate. All ranked candidates are `research_only`; no candidate passed the conservative risk-control/live-ready gate.

## Evidence

- Base ranking report: `reports/NQ-bar-5y-strategy-ranking.md`.
- Broader ranking report: `reports/NQ-bar-5y-broader-strategy-ranking.md`.
- Full ranking report: `reports/NQ-bar-5y-full-strategy-ranking.md`.
- Ranking implementation: `scripts/rank_nq_bar_best_strategy.py`.
- Regression test: `tests/test_nq_bar_best_strategy_rank.py`.
- Directional evidence: ranking reports include long/short trade-count, net-points, profit-factor, win-rate, and average-points splits for each top candidate.

## Best Research Features

| Search | Best candidate | Signal | Session | Entry point | Exit | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| Base | `bar_best_mean_reversion_lb30_thr1_hold30_us_rth` | Long below 30m mean by more than 1 rolling standard deviation; short above 30m mean by more than 1 rolling standard deviation | `13:30-20:00` UTC | Next minute open after signal bar | 30 minute time exit | `research_only` |
| Broader | `bar_best_vwap_reclaim_lb30_thr0.0002_hold30_us_late` | Long above cumulative VWAP by 0.0002 with positive 30m momentum; short below cumulative VWAP by 0.0002 with negative 30m momentum | `20:00-23:00` UTC | Next minute open after signal bar | 30 minute time exit | `research_only` |
| Full | `bar_best_momentum_lb10_thr0.0003_hold60_us_late` | Long when 10m return is above 0.0003; short when it is below -0.0003 | `20:00-23:00` UTC | Next minute open after signal bar | 60 minute time exit | `research_only` |

## Gate Result

The 5-year bar-only backtests found useful trading-opportunity features, but not a live-ready strategy:

- Base ranking: `0` balanced candidates.
- Broader ranking: `0` balanced candidates.
- Full ranking: `0` balanced candidates.
- Best candidates include LLM debate seed data, but their `live_ready` flag is `False`.
- Best candidates now include direction-specific evidence so the LLM can challenge whether the current signal should be acted on long, short, or filtered.

Therefore, the system should use these features as LLM debate context and paper-validation candidates only. It should not automatically submit live long/short orders from these bar-only results until a candidate passes risk-control gates, paper validation, and current-market confirmation.
