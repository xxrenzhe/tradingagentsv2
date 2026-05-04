import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "export_mbp_best_strategy_trades.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("export_mbp_best_strategy_trades", SCRIPT_PATH)
export_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(export_script)

AUDIT_PATH = SCRIPTS_DIR / "audit_mbp_best_strategy_readiness.py"
AUDIT_SPEC = importlib.util.spec_from_file_location("audit_mbp_best_strategy_readiness", AUDIT_PATH)
audit_script = importlib.util.module_from_spec(AUDIT_SPEC)
assert AUDIT_SPEC.loader is not None
sys.modules["audit_mbp_best_strategy_readiness"] = audit_script
AUDIT_SPEC.loader.exec_module(audit_script)

RANK_PATH = SCRIPTS_DIR / "rank_mbp_best_strategy.py"
RANK_SPEC = importlib.util.spec_from_file_location("rank_mbp_best_strategy", RANK_PATH)
rank_script = importlib.util.module_from_spec(RANK_SPEC)
assert RANK_SPEC.loader is not None
RANK_SPEC.loader.exec_module(rank_script)


def test_export_best_strategy_trades_writes_gate_ready_columns(tmp_path, monkeypatch):
    ranking_path = tmp_path / "ranking.csv"
    output_path = tmp_path / "trades.csv"
    ranking = pd.DataFrame(
        [
            {
                "name": "adv_candidate",
                "source": "advanced",
                "family": "mean_reversion",
                "lookback": 6,
                "threshold": 0.8,
                "min_hold": 1,
                "max_hold": 6,
                "exit_mode": "reverse",
                "session": "europe",
                "volatility_filter": "not_low",
                "candidate_universe": "selected_stability",
                "selection_tier": "balanced_best",
            }
        ]
    )
    ranking.to_csv(ranking_path, index=False)
    trades = pd.DataFrame(
        [
            {
                "entry_ts": "2026-04-01 07:00:00+00:00",
                "exit_ts": "2026-04-01 07:06:00+00:00",
                "direction": 1,
                "entry_price": 18000.0,
                "exit_price": 18004.0,
                "gross_points": 4.0,
                "net_points": 3.25,
                "net_dollars": 65.0,
                "exit_reason": "reverse",
                "entry_index": 10,
                "exit_index": 16,
                "holding_minutes": 6,
            }
        ]
    )

    monkeypatch.setattr(export_script, "_load_features", lambda path: pd.DataFrame())
    monkeypatch.setattr(export_script, "_advanced_spec_from_row", lambda row: object())
    monkeypatch.setattr(export_script, "build_advanced_trades", lambda features, spec: trades)

    row, output = export_script.export_best_strategy_trades(
        ranking_path=ranking_path,
        features_cache=tmp_path / "features.pkl",
        output_path=output_path,
        strategy_rank=1,
    )

    saved = pd.read_csv(output_path)
    assert row["name"] == "adv_candidate"
    assert output["portfolio_rule"].tolist() == ["adv_candidate"]
    assert output["selected_alias"].tolist() == ["best_strategy"]
    assert output["trade_date"].tolist() == ["2026-04-01"]
    assert saved["selection_tier"].tolist() == ["balanced_best"]
    assert {"entry_ts", "exit_ts", "trade_date", "direction", "entry_price", "net_points"}.issubset(saved.columns)


def test_rank_candidates_normalizes_walkforward_neighbor_columns():
    rows = pd.DataFrame(
        [
                {
                    "name": "wf_neighbor",
                    "candidate_universe": "walkforward_neighbors",
                    "full_trades": 250,
                "full_net_points": 1000.0,
                "full_max_drawdown_points": 80.0,
                "full_profit_factor": 1.6,
                "full_win_rate": 0.55,
                "full_stability": 0.80,
                "wf_positive_fold_rate": 1.0,
                "full_positive_window_rate": 1.0,
                "full_min_window_net_points": 25.0,
                "full_cost_3x_net_points": 650.0,
            }
        ]
    )

    rank_script._normalize_candidate_columns(rows)
    ranked = rank_script.rank_candidates(rows)

    assert ranked.iloc[0]["selection_tier"] == "balanced_best"
    assert ranked.iloc[0]["positive_fold_rate"] == 1.0
    assert ranked.iloc[0]["positive_window_rate"] == 1.0
    assert ranked.iloc[0]["min_window_net_points"] == 25.0
    assert ranked.iloc[0]["stress_net_points"] == 650.0


def test_best_strategy_readiness_passes_research_but_blocks_live_without_paper(tmp_path, monkeypatch):
    ranking_path = tmp_path / "ranking.csv"
    trades_path = tmp_path / "trades.csv"
    features_path = tmp_path / "features.pkl"
    empty_audit = tmp_path / "empty.jsonl"
    empty_audit.write_text("", encoding="utf-8")
    ranking = pd.DataFrame(
        [
            {
                "name": "best",
                "selection_tier": "balanced_best",
                "full_trades": 240,
                "full_net_points": 1200.0,
                "full_max_drawdown_points": 80.0,
                "full_profit_factor": 1.8,
                "full_win_rate": 0.55,
                "full_stability": 0.80,
                "positive_fold_rate": 1.0,
                "positive_window_rate": 1.0,
                "min_window_net_points": 20.0,
                "stress_net_points": 700.0,
                "net_to_drawdown": 15.0,
                "best_strategy_score": 5000.0,
            }
        ]
    )
    ranking.to_csv(ranking_path, index=False)
    dates = pd.date_range("2026-04-01", periods=240, freq="6h", tz="UTC")
    trades = pd.DataFrame(
        {
            "entry_ts": dates,
            "exit_ts": dates + pd.Timedelta(minutes=3),
            "trade_date": dates.date.astype(str),
            "direction": [1] * 240,
            "entry_price": [100.0] * 240,
            "exit_price": [101.0] * 240,
            "net_points": [5.0] * 240,
            "exit_reason": ["reverse"] * 240,
        }
    )
    trades.to_csv(trades_path, index=False)
    pd.to_pickle(
        {
            "sample": pd.DataFrame(
                {
                    "ts": pd.date_range("2026-04-01", periods=30, freq="D", tz="UTC"),
                    "Close": range(30),
                }
            )
        },
        features_path,
    )
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    monkeypatch.delenv("IBKR_ACCOUNT", raising=False)

    class Args:
        rolling_days = 10
        min_trades = 200
        min_profit_factor = 1.45
        min_net_to_drawdown = 10.0
        min_stability = 0.70
        min_positive_fold_rate = 0.80
        min_positive_window_rate = 0.88
        min_window_net_points = 0.0
        min_stress_net_points = 0.0
        min_history_days = 365
        min_ibkr_ready = 1
        min_ibkr_submitted = 1
        min_paper_outcomes = 20
        min_paper_net_points = 0.0
        min_paper_win_rate = 45.0
        max_consecutive_losses = 4
        max_allowed_blocker_count = 0
        rolling_step_days = 5

    args = Args()
    args.ranking = str(ranking_path)
    args.trades = str(trades_path)
    args.features_cache = str(features_path)
    args.gate_summary = str(tmp_path / "missing-gate.csv")
    args.walk_forward_summary = str(tmp_path / "missing-wf.csv")
    args.agent_audit = str(empty_audit)
    args.ibkr_audit = str(empty_audit)

    result = audit_script.audit_best_strategy(args)

    assert result["research_status"] == "pass"
    assert result["live_status"] == "blocked"
    assert any(blocker.startswith("history_span_below_min") for blocker in result["live_blockers"])
    assert "ibkr_account_missing" in result["live_blockers"]


def test_best_strategy_readiness_accepts_current_ibkr_ready_without_account_env(tmp_path, monkeypatch):
    ranking_path = tmp_path / "ranking.csv"
    trades_path = tmp_path / "trades.csv"
    features_path = tmp_path / "features.pkl"
    agent_audit = tmp_path / "agent.jsonl"
    ibkr_audit = tmp_path / "ibkr.jsonl"
    agent_audit.write_text("", encoding="utf-8")
    ibkr_audit.write_text(
        '{"event_type":"ibkr_paper_preflight","readiness":{"status":"ready","missing_requirements":[]}}\n',
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "name": "best",
                "selection_tier": "balanced_best",
                "full_trades": 240,
                "full_net_points": 1200.0,
                "full_max_drawdown_points": 80.0,
                "full_profit_factor": 1.8,
                "full_win_rate": 0.55,
                "full_stability": 0.80,
                "positive_fold_rate": 1.0,
                "positive_window_rate": 1.0,
                "min_window_net_points": 20.0,
                "stress_net_points": 700.0,
                "net_to_drawdown": 15.0,
                "best_strategy_score": 5000.0,
            }
        ]
    ).to_csv(ranking_path, index=False)
    dates = pd.date_range("2025-01-01", periods=240, freq="12h", tz="UTC")
    pd.DataFrame(
        {
            "entry_ts": dates,
            "exit_ts": dates + pd.Timedelta(minutes=3),
            "trade_date": dates.date.astype(str),
            "direction": [1] * 240,
            "entry_price": [100.0] * 240,
            "exit_price": [101.0] * 240,
            "net_points": [5.0] * 240,
            "exit_reason": ["reverse"] * 240,
        }
    ).to_csv(trades_path, index=False)
    pd.to_pickle(
        {
            "sample": pd.DataFrame(
                {
                    "ts": pd.date_range("2025-01-01", periods=365, freq="D", tz="UTC"),
                    "Close": range(365),
                }
            )
        },
        features_path,
    )
    monkeypatch.delenv("IBKR_ACCOUNT", raising=False)
    monkeypatch.setenv("DATABENTO_API_KEY", "test")

    class Args:
        rolling_days = 10
        min_trades = 200
        min_profit_factor = 1.45
        min_net_to_drawdown = 10.0
        min_stability = 0.70
        min_positive_fold_rate = 0.80
        min_positive_window_rate = 0.88
        min_window_net_points = 0.0
        min_stress_net_points = 0.0
        min_history_days = 365
        min_ibkr_ready = 1
        min_ibkr_submitted = 1
        min_paper_outcomes = 20
        min_paper_net_points = 0.0
        min_paper_win_rate = 45.0
        max_consecutive_losses = 4
        max_allowed_blocker_count = 0
        rolling_step_days = 5

    args = Args()
    args.ranking = str(ranking_path)
    args.trades = str(trades_path)
    args.features_cache = str(features_path)
    args.gate_summary = str(tmp_path / "missing-gate.csv")
    args.walk_forward_summary = str(tmp_path / "missing-wf.csv")
    args.agent_audit = str(agent_audit)
    args.ibkr_audit = str(ibkr_audit)

    result = audit_script.audit_best_strategy(args)

    assert "ibkr_account_missing" not in result["live_blockers"]
    assert any(blocker.startswith("paper_validation:ibkr_submitted_below_min") for blocker in result["live_blockers"])


def test_best_strategy_readiness_accepts_latest_paper_account_with_market_data_blocked(tmp_path, monkeypatch):
    ranking_path = tmp_path / "ranking.csv"
    trades_path = tmp_path / "trades.csv"
    features_path = tmp_path / "features.pkl"
    agent_audit = tmp_path / "agent.jsonl"
    ibkr_audit = tmp_path / "ibkr.jsonl"
    agent_audit.write_text("", encoding="utf-8")
    ibkr_audit.write_text(
        '{"event_type":"ibkr_paper_preflight","account":{"account":"DU002","paper":true},"readiness":{"status":"blocked","missing_requirements":["market_data_not_ready"]}}\n',
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "name": "best",
                "selection_tier": "balanced_best",
                "full_trades": 240,
                "full_net_points": 1200.0,
                "full_max_drawdown_points": 80.0,
                "full_profit_factor": 1.8,
                "full_win_rate": 0.55,
                "full_stability": 0.80,
                "positive_fold_rate": 1.0,
                "positive_window_rate": 1.0,
                "min_window_net_points": 20.0,
                "stress_net_points": 700.0,
                "net_to_drawdown": 15.0,
                "best_strategy_score": 5000.0,
            }
        ]
    ).to_csv(ranking_path, index=False)
    dates = pd.date_range("2025-01-01", periods=240, freq="12h", tz="UTC")
    pd.DataFrame(
        {
            "entry_ts": dates,
            "exit_ts": dates + pd.Timedelta(minutes=3),
            "trade_date": dates.date.astype(str),
            "direction": [1] * 240,
            "entry_price": [100.0] * 240,
            "exit_price": [101.0] * 240,
            "net_points": [5.0] * 240,
            "exit_reason": ["reverse"] * 240,
        }
    ).to_csv(trades_path, index=False)
    pd.to_pickle(
        {
            "sample": pd.DataFrame(
                {
                    "ts": pd.date_range("2025-01-01", periods=365, freq="D", tz="UTC"),
                    "Close": range(365),
                }
            )
        },
        features_path,
    )
    monkeypatch.delenv("IBKR_ACCOUNT", raising=False)
    monkeypatch.setenv("DATABENTO_API_KEY", "test")

    class Args:
        rolling_days = 10
        min_trades = 200
        min_profit_factor = 1.45
        min_net_to_drawdown = 10.0
        min_stability = 0.70
        min_positive_fold_rate = 0.80
        min_positive_window_rate = 0.88
        min_window_net_points = 0.0
        min_stress_net_points = 0.0
        min_history_days = 365
        min_ibkr_ready = 1
        min_ibkr_submitted = 1
        min_paper_outcomes = 20
        min_paper_net_points = 0.0
        min_paper_win_rate = 45.0
        max_consecutive_losses = 4
        max_allowed_blocker_count = 0
        rolling_step_days = 5

    args = Args()
    args.ranking = str(ranking_path)
    args.trades = str(trades_path)
    args.features_cache = str(features_path)
    args.gate_summary = str(tmp_path / "missing-gate.csv")
    args.walk_forward_summary = str(tmp_path / "missing-wf.csv")
    args.agent_audit = str(agent_audit)
    args.ibkr_audit = str(ibkr_audit)

    result = audit_script.audit_best_strategy(args)

    assert "ibkr_account_missing" not in result["live_blockers"]
    assert any(blocker.startswith("paper_validation:ibkr_ready_below_min") for blocker in result["live_blockers"])


def test_best_strategy_readiness_filters_paper_events_to_top_candidate(tmp_path, monkeypatch):
    ranking_path = tmp_path / "ranking.csv"
    trades_path = tmp_path / "trades.csv"
    features_path = tmp_path / "features.pkl"
    agent_audit = tmp_path / "agent.jsonl"
    ibkr_audit = tmp_path / "ibkr.jsonl"
    pd.DataFrame(
        [
            {
                "name": "best",
                "selection_tier": "balanced_best",
                "full_trades": 240,
                "full_net_points": 1200.0,
                "full_max_drawdown_points": 80.0,
                "full_profit_factor": 1.8,
                "full_win_rate": 0.55,
                "full_stability": 0.80,
                "positive_fold_rate": 1.0,
                "positive_window_rate": 1.0,
                "min_window_net_points": 20.0,
                "stress_net_points": 700.0,
                "net_to_drawdown": 15.0,
                "best_strategy_score": 5000.0,
            }
        ]
    ).to_csv(ranking_path, index=False)
    dates = pd.date_range("2025-01-01", periods=240, freq="12h", tz="UTC")
    pd.DataFrame(
        {
            "entry_ts": dates,
            "exit_ts": dates + pd.Timedelta(minutes=3),
            "trade_date": dates.date.astype(str),
            "direction": [1] * 240,
            "entry_price": [100.0] * 240,
            "exit_price": [101.0] * 240,
            "net_points": [5.0] * 240,
            "exit_reason": ["reverse"] * 240,
        }
    ).to_csv(trades_path, index=False)
    pd.to_pickle(
        {
            "sample": pd.DataFrame(
                {
                    "ts": pd.date_range("2025-01-01", periods=365, freq="D", tz="UTC"),
                    "Close": range(365),
                }
            )
        },
        features_path,
    )
    agent_audit.write_text(
        "\n".join(
            [
                '{"event_type":"agent_gate_paper_outcome","strategy_id":"other","points":5}',
                '{"event_type":"agent_gate_paper_outcome","strategy_id":"other","points":5}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ibkr_audit.write_text(
        "\n".join(
            [
                '{"event_type":"ibkr_paper_preflight","account":{"account":"DU004","paper":true},"readiness":{"status":"ready","missing_requirements":[]}}',
                '{"status":"submitted","intent":{"strategy_id":"other"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DATABENTO_API_KEY", "test")

    class Args:
        rolling_days = 10
        min_trades = 200
        min_profit_factor = 1.45
        min_net_to_drawdown = 10.0
        min_stability = 0.70
        min_positive_fold_rate = 0.80
        min_positive_window_rate = 0.88
        min_window_net_points = 0.0
        min_stress_net_points = 0.0
        min_history_days = 365
        min_ibkr_ready = 1
        min_ibkr_submitted = 1
        min_paper_outcomes = 1
        min_paper_net_points = 0.0
        min_paper_win_rate = 45.0
        max_consecutive_losses = 4
        max_allowed_blocker_count = 0
        rolling_step_days = 5

    args = Args()
    args.ranking = str(ranking_path)
    args.trades = str(trades_path)
    args.features_cache = str(features_path)
    args.gate_summary = str(tmp_path / "missing-gate.csv")
    args.walk_forward_summary = str(tmp_path / "missing-wf.csv")
    args.agent_audit = str(agent_audit)
    args.ibkr_audit = str(ibkr_audit)

    result = audit_script.audit_best_strategy(args)

    assert result["paper_strategy_id"] == "best"
    assert result["paper_summary"]["strategy_id_filter"] == "best"
    assert result["paper_summary"]["ibkr_submitted"] == 0
    assert result["paper_summary"]["paper_outcomes"]["trades"] == 0
    assert any(blocker.startswith("paper_validation:ibkr_submitted_below_min") for blocker in result["live_blockers"])
