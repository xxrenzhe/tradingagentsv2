from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

from tradingagents.execution.agent_gate import build_candidate_trade_context, load_strategy_evidence
from tradingagents.execution.ibkr import IBKROrderIntent


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "rank_nq_bar_best_strategy.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("rank_nq_bar_best_strategy", SCRIPT_PATH)
rank_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(rank_script)


def test_rank_nq_bar_candidates_exports_agent_gate_evidence(tmp_path) -> None:
    aggregate_path = tmp_path / "aggregate.csv"
    ranking_path = tmp_path / "ranking.csv"
    aggregate = pd.DataFrame(
        [
            {
                "candidate": "bar_best_mean_reversion_lb30_thr1_hold30_us_rth",
                "family": "mean_reversion",
                "lookback": 30,
                "threshold": 1.0,
                "holding_minutes": 30,
                "session": "us_rth",
                "selected_folds": 5,
                "positive_test_fold_rate": 1.0,
                "pass_fold_rate": 1.0,
                "test_trades": 3146,
                "test_net_points": 9544.0,
                "test_max_drawdown_points": 3905.125,
                "avg_test_profit_factor": 1.1152,
                "avg_test_win_rate": 0.5158,
                "avg_test_stability": 0.8476,
                "min_test_net_points": 277.5,
                "long_history_score": 10.822,
            },
            {
                "candidate": "weak",
                "family": "momentum",
                "lookback": 10,
                "threshold": 0.0003,
                "holding_minutes": 60,
                "session": "us_late",
                "selected_folds": 1,
                "positive_test_fold_rate": 0.0,
                "pass_fold_rate": 0.0,
                "test_trades": 50,
                "test_net_points": -100.0,
                "test_max_drawdown_points": 500.0,
                "avg_test_profit_factor": 0.8,
                "avg_test_win_rate": 0.4,
                "avg_test_stability": 0.1,
                "min_test_net_points": -100.0,
                "long_history_score": 0.0,
            },
        ]
    )
    aggregate.to_csv(aggregate_path, index=False)

    rows = rank_script.load_candidate_results([(str(aggregate_path), "walkforward_5y_1m")])
    ranked = rank_script.rank_candidates(rows)
    debate_pack = rank_script.build_debate_pack(ranked)
    ranked.to_csv(ranking_path, index=False)

    best = ranked.iloc[0]
    assert best["name"] == "bar_best_mean_reversion_lb30_thr1_hold30_us_rth"
    assert best["selection_tier"] == "balanced_best"
    assert bool(best["live_ready"])
    assert best["candidate_universe"] == "walkforward_5y_1m"
    assert best["full_trades"] == 3146
    assert best["full_net_points"] == 9544.0
    assert debate_pack["candidates"][0]["name"] == best["name"]
    assert debate_pack["candidates"][0]["bull_case"]
    assert debate_pack["candidates"][0]["bear_case"]
    assert debate_pack["candidates"][0]["session_window_utc"] == "13:30-20:00"
    assert "rolling standard deviations" in debate_pack["candidates"][0]["signal_rule"]

    evidence = load_strategy_evidence(str(best["name"]), ranking_path)
    context = build_candidate_trade_context(
        IBKROrderIntent(
            action="BUY",
            quantity=1,
            symbol="NQ",
            last_trade_date_or_contract_month="202606",
            stop_loss_price=18000.0,
            take_profit_price=18100.0,
            strategy_id=str(best["name"]),
        ),
        {"trade_date": "2026-05-05", "entry_price": 18025.25},
        strategy_evidence=evidence,
    )

    assert evidence is not None
    assert "Historical strategy evidence" in context
    assert "candidate_universe=walkforward_5y_1m" in context
    assert "full_net_points=9544.0" in context
    assert "live_ready=True" in context
