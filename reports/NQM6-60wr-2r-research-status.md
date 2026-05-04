# NQM6 60% Win-Rate 2R Strategy Research Status

## Objective Audit

- Target: find a non-overfit, black-box-tested strategy with >=60% win rate and 2R reward/risk that can be used live for long-term profitability.
- Current verdict: not achieved. The repository now contains reproducible search and validation tooling, but no candidate passed the required gates.

## Existing Research Progress

- Full MBP feature cache covers 60,503 one-minute rows from 2026-03-02 23:59 UTC to 2026-05-01 21:00 UTC.
- Existing live-ready candidates are profitable under fold/window/cost stress and some exceed 60% historical win rate, but they mostly do not use fixed 2R brackets and did not pass the new 2R black-box gate.
- Existing adaptive portfolio candidates improve aggregate net/PF, with best win rate 56.06%; still below 60% and not fixed 2R.

## New Black-Box Evidence

- Added strict chronological 2R validation: `scripts/validate_mbp_2r_blackbox.py`.
- Tested all existing base/advanced 2R candidates: 2,448 candidates, zero passed the training gate.
- Added expanded 2R candidate search: `scripts/search_mbp_2r_expanded.py`.
- Tested expanded 2R grid: 25,000 candidates. Max test win rate was 8.70%; max test net was -41.25 points; positive-test-net candidates: 0.
- Added raw feature label-rule search: `scripts/search_mbp_2r_label_rules.py`.
- Scanned 60,000 direct 2R label rules across direction, stop size, horizon, session, volatility, setup, imbalance, VWAP side, and gap filters; zero rules passed even the relaxed training gate used for discovery.
- Added train-only purged walk-forward 2R search: `scripts/search_mbp_2r_purged_walkforward.py`.
- Ran core single-predicate purged searches for Europe, US RTH, and all sessions using stop sizes 4/8/12 points, 30/60 minute horizons, and train-only feature quantiles. Even with relaxed discovery gates (`>=50%` train win rate, PF `>=1.00`, bracket exit share `>=40%`), all 7 folds in each session learned zero train-only candidates, so black-box pass count remained zero.
- Added 2R feasibility diagnostics: `scripts/diagnose_mbp_2r_feasibility.py`.
- Ran representative oracle-style diagnostics across 72 base setups (directions, stop sizes 4/8/16, horizons 30/60/120, sessions all/Europe/US RTH/US late) and 216 train-quantile feature bins. Future feature bins passing the 60%/2R feasibility gate: zero. The best unfiltered setup win rate was 14.78%; the best future single-feature bin win rate was 47.06%, still below the required 60%.
- Extended feasibility diagnostics with train-selected pair-feature bins. The representative pair run evaluated 72 base setups and 360 single/pair bins. Future 60%/2R feasibility passes remained zero. The best future pair bin reached 59.375% win rate over 32 test events with positive net and PF 2.61, but it still failed the explicit 60% threshold and is only a diagnostic bin, not a non-overfit live strategy.
- Ran a restricted purged walk-forward follow-up around that closest pair-bin neighborhood: short-only, US late, stop 8 / take 16, horizons 30/60/120, pair predicates enabled, relaxed training discovery gates. All 7 folds learned zero train-only candidates, so the near-60% diagnostic bin did not convert into a train-selectable black-box strategy.
- Added train-only model-score search: `scripts/search_mbp_2r_model_walkforward.py`. It learns feature-bin scores only on train dates, skips purge dates, and applies the learned score model to future test dates. The representative run produced 3 training-selected model candidates and zero black-box passes; the learned short US-late SL16/TP32 candidates collapsed to 14.86% future win rate and negative net.
- Added train-only state-label search: `scripts/search_mbp_2r_state_walkforward.py`. It derives discrete regime/state labels only from train-date quantiles, skips purge dates, and applies those labels to future test dates. A focused short-only SL8/SL16 all/US-late run produced 135 training-selected state candidates and zero black-box passes; the best future win rates were below the 60% gate or below minimum test-trade requirements.
- Added long-horizon bar-only NQ continuous-contract search: `scripts/search_nq_bar_2r_walkforward.py`. It uses the local 2010-2026 Databento OHLCV zip to construct one NQ futures row per minute by highest reported volume, then applies train-only feature-threshold selection with purged future tests. A 2024-01-01 to 2026-04-27 discovery run produced 289 training-selected candidates and zero fixed-2R black-box passes; the best future win rate was 50.00%, still far below the required 60%. This is separate from the MBP strategy family and does not make the MBP/live-readiness blockers disappear.
- Added machine-readable goal readiness audit: `scripts/audit_mbp_2r_goal_readiness.py`.
- Current audit result: `blocked`. Blockers include zero 60%/2R black-box candidates, only 61 calendar days of MBP history versus a 365-day long-term threshold, missing `DATABENTO_API_KEY`, missing `IBKR_ACCOUNT`, zero submitted IBKR paper trades, zero paper outcomes, and unresolved IBKR readiness blockers.
- Added blocker handoff: `reports/NQM6-mbp-2r-blocker-handoff.md`. The active goal bead now depends on separate follow-up beads for one-year history, future paper validation, and non-minute-rule 2R research; paper validation also depends on the existing IBKR bid/ask market data blocker.

## Why This Is Not Live-Ready

- No strategy satisfied the explicit 60% win-rate + 2R + chronological black-box condition.
- The strongest existing profitable strategies rely on frequent smaller exits or flexible reverse/time exits, not a 1:2 bracket profile.
- The 2R searches show target-touch frequency is too low on the current data and rule families; this is a structural mismatch, not a small parameter miss.
- The feasibility diagnostic supports the same conclusion before full strategy construction: even optimistic single-feature bins did not reach 60% future win rate.
- Pair-feature bins came closest, but the best result still failed the 60% hard threshold and was selected from a small 32-event future sample, so it cannot be promoted to live-ready.
- The closest pair-bin neighborhood failed when forced through train-only purged walk-forward selection, which weakens the case that it represents a stable edge.
- Train-only model and state-label searches also failed to convert training edges into future 60%/2R passes, which weakens the hypothesis that a simple multi-feature classifier or discrete regime label can rescue this objective on the current MBP sample.
- A strategy cannot honestly be marked direct-live/long-term profitable without paper outcomes and out-of-sample evidence beyond this two-month NQM6 sample.

## Prompt-to-Artifact Completion Audit

| Requirement | Evidence | Status |
| --- | --- | --- |
| Understand current strategy research progress | `reports/NQM6-best-strategy-final-selection.md` and `reports/NQM6-best-strategy-ranking.md` identify the strongest non-2R candidate and its gate/walk-forward behavior. | Done |
| Find a 60% win-rate strategy | No candidate passed `test_win_rate >= 0.60` under chronological/purged black-box validation. | Not achieved |
| Fixed 2R reward/risk | `validate_mbp_2r_blackbox.py`, `search_mbp_2r_expanded.py`, `search_mbp_2r_label_rules.py`, and `search_mbp_2r_purged_walkforward.py` all enforce `take_profit_points = 2 * stop_loss_points`. | Tested, no pass |
| Avoid overfitting | Chronological split and purged walk-forward tooling exist, but no candidate survived them; therefore there is no non-overfit strategy to promote. | Not achieved |
| Black-box testing | Existing 2R candidates, expanded grid, label rules, and purged train-only rules were tested on future holdout windows. | Done |
| Feasibility before strategy construction | `reports/NQM6-mbp-2r-feasibility-representative.md` shows 72 base setups and 216 single-feature train bins produced zero future 60%/2R passes. `reports/NQM6-mbp-2r-feasibility-pair-representative.md` shows 360 single/pair bins also produced zero passes, with best future win rate 59.375%. | Done |
| Closest-bin follow-up | `reports/NQM6-mbp-2r-purged-walkforward-us-late-pair-neighborhood.md` tests the closest pair-bin neighborhood with train-only purged walk-forward; 0 training-selected candidates and 0 black-box passes. | Done |
| Train-only model search | `reports/NQM6-mbp-2r-model-walkforward.md` tests feature-bin model scores learned only on train folds; 3 tested candidates, 0 black-box passes. | Done |
| Train-only state-label search | `reports/NQM6-mbp-2r-state-walkforward-focused.md` tests train-quantile regime/state labels in a focused short-only setup; 135 tested candidates, 0 black-box passes. | Done |
| Long-horizon bar-only search | `reports/NQ-bar-2r-walkforward-discovery-small.md` tests continuous NQ OHLCV from 2024-01-01 to 2026-04-27 with train-only thresholds and purged future tests; 289 tested candidates, 0 black-box passes. | Done |
| Direct live use | No candidate passed research gates, and paper/live fills plus order-routing checks are still missing. | Not achieved |
| Long-term profitability | Current data covers only 2026-03-02 to 2026-05-01; no passing 2R candidate and no long-term out-of-sample data. | Not achieved |
| Machine completion audit | `reports/NQM6-mbp-2r-goal-readiness-audit.md` maps each explicit requirement to real artifacts and currently returns `blocked`. | Done |
| Follow-up tracking | `reports/NQM6-mbp-2r-blocker-handoff.md` maps readiness blockers to beads: `TradingAgentsV2-p6o`, `TradingAgentsV2-5ci`, `TradingAgentsV2-6ce`, and `TradingAgentsV2-qyt`. | Done |

## Repro Commands

```bash
.venv/bin/python scripts/validate_mbp_2r_blackbox.py
.venv/bin/python scripts/search_mbp_2r_expanded.py --max-candidates 25000 --shard-count 4 --shard-index 0
.venv/bin/python scripts/diagnose_mbp_2r_candidates.py --max-candidates 25000 --shard-count 4 --shard-index 0
.venv/bin/python scripts/search_mbp_2r_label_rules.py --max-rules 60000 --shard-count 6 --shard-index 0
.venv/bin/python scripts/search_mbp_2r_purged_walkforward.py --stop-loss-points 4 8 12 --horizon-minutes 30 60 --sessions europe --quantiles 0.2 0.8 --max-pair-predicates 1 --max-fold-candidates 10 --min-train-trades 20 --min-test-trades 5 --min-train-win-rate 0.50 --min-profit-factor 1.00 --min-bracket-exit-share 0.40 --report reports/NQM6-mbp-2r-purged-walkforward-europe-core.md --output .tmp/mbp-2r-purged-walkforward-europe-core.csv --trades-output .tmp/mbp-2r-purged-walkforward-europe-core-trades.csv
.venv/bin/python scripts/search_mbp_2r_purged_walkforward.py --stop-loss-points 4 8 12 --horizon-minutes 30 60 --sessions us_rth --quantiles 0.2 0.8 --max-pair-predicates 1 --max-fold-candidates 10 --min-train-trades 20 --min-test-trades 5 --min-train-win-rate 0.50 --min-profit-factor 1.00 --min-bracket-exit-share 0.40 --report reports/NQM6-mbp-2r-purged-walkforward-us-rth-core.md --output .tmp/mbp-2r-purged-walkforward-us-rth-core.csv --trades-output .tmp/mbp-2r-purged-walkforward-us-rth-core-trades.csv
.venv/bin/python scripts/search_mbp_2r_purged_walkforward.py --stop-loss-points 4 8 12 --horizon-minutes 30 60 --sessions all --quantiles 0.2 0.8 --max-pair-predicates 1 --max-fold-candidates 10 --min-train-trades 20 --min-test-trades 5 --min-train-win-rate 0.50 --min-profit-factor 1.00 --min-bracket-exit-share 0.40 --report reports/NQM6-mbp-2r-purged-walkforward-all-core.md --output .tmp/mbp-2r-purged-walkforward-all-core.csv --trades-output .tmp/mbp-2r-purged-walkforward-all-core-trades.csv
.venv/bin/python scripts/diagnose_mbp_2r_feasibility.py --stop-loss-points 4 8 16 --horizon-minutes 30 60 120 --sessions all europe us_rth us_late --min-bin-events 80 --quantile-count 7 --top-bins-per-setup 3 --setups-output .tmp/mbp-2r-feasibility-representative-setups.csv --bins-output .tmp/mbp-2r-feasibility-representative-feature-bins.csv --report reports/NQM6-mbp-2r-feasibility-representative.md
.venv/bin/python scripts/diagnose_mbp_2r_feasibility.py --stop-loss-points 4 8 16 --horizon-minutes 30 60 120 --sessions all europe us_rth us_late --min-bin-events 80 --quantile-count 7 --top-bins-per-setup 5 --include-pair-bins --pair-pool-size 8 --setups-output .tmp/mbp-2r-feasibility-pair-representative-setups.csv --bins-output .tmp/mbp-2r-feasibility-pair-representative-bins.csv --report reports/NQM6-mbp-2r-feasibility-pair-representative.md
.venv/bin/python scripts/search_mbp_2r_purged_walkforward.py --train-days 20 --purge-days 2 --test-days 5 --step-days 5 --stop-loss-points 8 --horizon-minutes 30 60 120 --sessions us_late --quantiles 0.15 0.3 0.7 0.85 --max-pair-predicates 20 --max-fold-candidates 20 --min-train-trades 25 --min-test-trades 10 --min-train-win-rate 0.45 --min-profit-factor 0.90 --min-bracket-exit-share 0.70 --report reports/NQM6-mbp-2r-purged-walkforward-us-late-pair-neighborhood.md --output .tmp/mbp-2r-purged-walkforward-us-late-pair-neighborhood.csv --trades-output .tmp/mbp-2r-purged-walkforward-us-late-pair-neighborhood-trades.csv
.venv/bin/python scripts/search_mbp_2r_model_walkforward.py --train-days 20 --purge-days 2 --test-days 5 --step-days 5 --stop-loss-points 4 8 12 16 --horizon-minutes 30 60 120 --sessions all europe us_rth us_late --score-quantiles 0.6 0.7 0.8 0.9 --min-train-events 60 --min-train-trades 20 --min-test-trades 10 --min-train-win-rate 0.45 --min-profit-factor 0.90 --min-bracket-exit-share 0.55 --min-positive-window-rate 0.50 --max-fold-candidates 40 --output .tmp/mbp-2r-model-walkforward.csv --trades-output .tmp/mbp-2r-model-walkforward-trades.csv --report reports/NQM6-mbp-2r-model-walkforward.md
.venv/bin/python scripts/search_mbp_2r_state_walkforward.py --train-days 20 --purge-days 2 --test-days 5 --step-days 5 --directions -1 --stop-loss-points 8 16 --horizon-minutes 30 60 120 --sessions us_late all --min-train-trades 10 --min-test-trades 5 --min-train-win-rate 0.40 --min-profit-factor 0.80 --min-bracket-exit-share 0.50 --min-positive-window-rate 0.50 --max-fold-candidates 20 --output .tmp/mbp-2r-state-walkforward-focused.csv --trades-output .tmp/mbp-2r-state-walkforward-focused-trades.csv --report reports/NQM6-mbp-2r-state-walkforward-focused.md
.venv/bin/python scripts/search_nq_bar_2r_walkforward.py --start-date 2024-01-01 --walk-start-date 2025-01-01 --end-date 2026-04-28 --entry-step-minutes 15 --train-days 120 --purge-days 5 --test-days 60 --step-days 90 --stop-loss-points 12 24 32 --horizon-minutes 30 60 --sessions all us_rth --quantiles 0.2 0.3 0.7 0.8 --min-train-trades 20 --min-test-trades 8 --min-train-win-rate 0.45 --min-train-profit-factor 0.70 --min-test-profit-factor 1.00 --min-bracket-exit-share 0.35 --max-fold-candidates 20 --cache .tmp/nq-bar-continuous-features-cache.pkl --output .tmp/nq-bar-2r-walkforward-discovery-small.csv --trades-output .tmp/nq-bar-2r-walkforward-discovery-small-trades.csv --report reports/NQ-bar-2r-walkforward-discovery-small.md
.venv/bin/python scripts/audit_mbp_2r_goal_readiness.py --output .tmp/mbp-2r-goal-readiness-audit.json --report reports/NQM6-mbp-2r-goal-readiness-audit.md
```

## Next Research Direction

- If 2R is mandatory, move beyond these simple MBP/minute-rule families: add event/regime labels, multi-timeframe context, and train-only model selection with purged/embargoed walk-forward validation.
- If live profitability is mandatory sooner, continue from the existing non-2R live-ready/adaptive candidates and validate them in paper trading rather than forcing a 2R bracket that current data rejects.
