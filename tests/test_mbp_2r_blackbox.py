import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "validate_mbp_2r_blackbox.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("validate_mbp_2r_blackbox", SCRIPT_PATH)
blackbox = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["validate_mbp_2r_blackbox"] = blackbox
SPEC.loader.exec_module(blackbox)

BlackBoxConfig = blackbox.BlackBoxConfig
_passes_train_gate = blackbox._passes_train_gate
_risk_is_2r = blackbox._risk_is_2r
passes_blackbox_gate = blackbox.passes_blackbox_gate
summarize_2r_trades = blackbox.summarize_2r_trades

PURGED_PATH = SCRIPTS_DIR / "search_mbp_2r_purged_walkforward.py"
PURGED_SPEC = importlib.util.spec_from_file_location("search_mbp_2r_purged_walkforward", PURGED_PATH)
purged = importlib.util.module_from_spec(PURGED_SPEC)
assert PURGED_SPEC.loader is not None
sys.modules["search_mbp_2r_purged_walkforward"] = purged
PURGED_SPEC.loader.exec_module(purged)

FEASIBILITY_PATH = SCRIPTS_DIR / "diagnose_mbp_2r_feasibility.py"
FEASIBILITY_SPEC = importlib.util.spec_from_file_location("diagnose_mbp_2r_feasibility", FEASIBILITY_PATH)
feasibility = importlib.util.module_from_spec(FEASIBILITY_SPEC)
assert FEASIBILITY_SPEC.loader is not None
sys.modules["diagnose_mbp_2r_feasibility"] = feasibility
FEASIBILITY_SPEC.loader.exec_module(feasibility)

AUDIT_PATH = SCRIPTS_DIR / "audit_mbp_2r_goal_readiness.py"
AUDIT_SPEC = importlib.util.spec_from_file_location("audit_mbp_2r_goal_readiness", AUDIT_PATH)
audit_goal_script = importlib.util.module_from_spec(AUDIT_SPEC)
assert AUDIT_SPEC.loader is not None
sys.modules["audit_mbp_2r_goal_readiness"] = audit_goal_script
AUDIT_SPEC.loader.exec_module(audit_goal_script)

MODEL_PATH = SCRIPTS_DIR / "search_mbp_2r_model_walkforward.py"
MODEL_SPEC = importlib.util.spec_from_file_location("search_mbp_2r_model_walkforward", MODEL_PATH)
model_search = importlib.util.module_from_spec(MODEL_SPEC)
assert MODEL_SPEC.loader is not None
sys.modules["search_mbp_2r_model_walkforward"] = model_search
MODEL_SPEC.loader.exec_module(model_search)

STATE_PATH = SCRIPTS_DIR / "search_mbp_2r_state_walkforward.py"
STATE_SPEC = importlib.util.spec_from_file_location("search_mbp_2r_state_walkforward", STATE_PATH)
state_search = importlib.util.module_from_spec(STATE_SPEC)
assert STATE_SPEC.loader is not None
sys.modules["search_mbp_2r_state_walkforward"] = state_search
STATE_SPEC.loader.exec_module(state_search)


def test_risk_is_2r_requires_positive_two_to_one_ratio():
    assert _risk_is_2r(12.0, 24.0)
    assert not _risk_is_2r(12.0, 18.0)
    assert not _risk_is_2r(pd.NA, 24.0)


def test_summarize_2r_trades_tracks_bracket_exit_share():
    trades = pd.DataFrame(
        {
            "net_points": [23.375, -12.625, 3.0],
            "exit_reason": ["take_profit", "stop_loss", "time"],
        }
    )

    summary = summarize_2r_trades("candidate", trades)

    assert summary["trades"] == 3
    assert summary["win_rate"] == 2 / 3
    assert summary["bracket_exit_share"] == 2 / 3
    assert summary["target_exit_share"] == 1 / 3


def test_train_gate_blocks_weak_or_non_bracket_candidate():
    config = BlackBoxConfig(min_train_trades=10, min_train_win_rate=0.58, min_bracket_exit_share=0.70)
    summary = {
        "trades": 10,
        "net_points": 25.0,
        "win_rate": 0.60,
        "profit_factor": 1.5,
        "bracket_exit_share": 0.70,
    }

    assert _passes_train_gate(summary, config)

    summary["bracket_exit_share"] = 0.69
    assert not _passes_train_gate(summary, config)


def test_blackbox_gate_requires_test_win_rate_and_window_stability():
    config = BlackBoxConfig(min_test_trades=5, min_test_win_rate=0.60, min_positive_window_rate=0.70)
    row = {
        "test_trades": 5,
        "test_net_points": 15.0,
        "test_win_rate": 0.60,
        "test_profit_factor": 1.30,
        "test_positive_window_rate": 0.70,
        "test_min_window_trades": 5,
        "test_bracket_exit_share": 0.70,
    }

    assert passes_blackbox_gate(row, config)

    row["test_win_rate"] = 0.59
    assert not passes_blackbox_gate(row, config)


def test_purged_build_2r_events_uses_fixed_two_to_one_bracket():
    features = pd.DataFrame(
        {
            "ts": pd.date_range("2026-04-01 07:00", periods=5, freq="min", tz="UTC"),
            "trade_date": [pd.Timestamp("2026-04-01").date()] * 5,
            "minute_of_day": [420, 421, 422, 423, 424],
            "Open": [100.0, 100.0, 100.0, 100.0, 100.0],
            "High": [100.5, 101.0, 108.0, 108.0, 108.0],
            "Low": [99.5, 99.5, 99.5, 99.5, 99.5],
            "Close": [100.0, 101.0, 108.0, 108.0, 108.0],
        }
    )

    events = purged.build_2r_events(features, direction=1, stop_loss_points=4.0, horizon_minutes=3, cost_points=0.625)

    assert events.iloc[0]["exit_reason"] == "take_profit"
    assert events.iloc[0]["gross_points"] == 8.0
    assert events.iloc[0]["net_points"] == 7.375


def test_purged_blackbox_gate_requires_future_sixty_percent_win_rate():
    class Args:
        min_test_trades = 5
        min_test_win_rate = 0.60
        min_profit_factor = 1.20
        min_positive_window_rate = 0.70
        min_window_trades = 5
        min_bracket_exit_share = 0.70

    row = {
        "test_trades": 5,
        "test_net_points": 20.0,
        "test_win_rate": 0.60,
        "test_profit_factor": 1.25,
        "test_positive_window_rate": 0.70,
        "test_min_window_trades": 5,
        "test_bracket_exit_share": 0.70,
    }

    assert purged.passes_blackbox(row, Args)
    row["test_win_rate"] = 0.59
    assert not purged.passes_blackbox(row, Args)


def test_purged_select_non_overlapping_skips_overlapping_entries():
    events = pd.DataFrame(
        {
            "entry_index": [1, 2, 5],
            "exit_index": [4, 3, 6],
            "net_points": [1.0, 2.0, 3.0],
        }
    )
    mask = pd.Series([True, True, True])

    selected = purged._select_non_overlapping(events, mask, min_gap_minutes=1)

    assert selected["entry_index"].tolist() == [1, 5]


def test_feasibility_summary_tracks_target_and_stop_shares():
    events = pd.DataFrame(
        {
            "net_points": [7.375, -4.625, -0.625],
            "exit_reason": ["take_profit", "stop_loss", "timeout"],
        }
    )

    summary = feasibility.summarize_events(events)

    assert summary["events"] == 3
    assert summary["win_rate"] == 1 / 3
    assert summary["target_exit_share"] == 1 / 3
    assert summary["stop_exit_share"] == 1 / 3
    assert summary["timeout_share"] == 1 / 3


def test_feasibility_compare_builds_threshold_masks():
    values = pd.Series([1.0, 2.0, 3.0])

    assert feasibility.compare(values, "<=", 2.0).tolist() == [True, True, False]
    assert feasibility.compare(values, ">=", 2.0).tolist() == [False, True, True]


def test_feasibility_best_feature_bins_can_emit_pair_bins():
    features = pd.DataFrame(
        {
            "signal_index": range(12),
            "return_3m": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6] * 2,
            "return_5m": [0.1, 0.1, 0.2, 0.2, 0.3, 0.3] * 2,
            "range_1m": [1.0] * 12,
            "body_to_range": [0.0] * 12,
            "realized_vol_15": [0.1] * 12,
            "realized_vol_30": [0.1] * 12,
            "z_5": [0.0] * 12,
            "z_10": [0.0] * 12,
            "vwap_distance": [0.0] * 12,
            "imbalance": [0.0] * 12,
            "spread_mean": [1.0] * 12,
            "depth_mean": [10.0] * 12,
            "quote_count": [100] * 12,
        }
    )
    events = pd.DataFrame(
        {
            "signal_index": range(12),
            "trade_date": [pd.Timestamp("2026-04-01").date()] * 6 + [pd.Timestamp("2026-04-02").date()] * 6,
            "net_points": [1.0, -1.0, 1.0, -1.0, 1.0, -1.0] * 2,
            "exit_reason": ["take_profit", "stop_loss"] * 6,
        }
    )

    rows = feasibility.best_feature_bins(
        features,
        events,
        direction=1,
        stop_loss_points=4.0,
        horizon_minutes=30,
        session="all",
        min_events=1,
        quantile_count=3,
        train_fraction=0.5,
        top_n=200,
        include_pairs=True,
        pair_pool_size=20,
    )

    assert any(row["bin_type"] == "pair" for row in rows)


def test_goal_readiness_audit_blocks_without_candidate_history_and_paper(tmp_path, monkeypatch):
    feature_cache = tmp_path / "features.pkl"
    pd.to_pickle(
        {
            "sample": pd.DataFrame(
                {
                    "ts": pd.date_range("2026-04-01", periods=3, freq="D", tz="UTC"),
                    "Close": [1.0, 2.0, 3.0],
                }
            )
        },
        feature_cache,
    )
    empty_pass = tmp_path / "empty.csv"
    pd.DataFrame({"blackbox_pass": []}).to_csv(empty_pass, index=False)
    empty_oracle = tmp_path / "oracle.csv"
    pd.DataFrame({"oracle_60wr_2r_pass": []}).to_csv(empty_oracle, index=False)
    agent_audit = tmp_path / "agent.jsonl"
    ibkr_audit = tmp_path / "ibkr.jsonl"
    agent_audit.write_text("", encoding="utf-8")
    ibkr_audit.write_text("", encoding="utf-8")
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    monkeypatch.delenv("IBKR_ACCOUNT", raising=False)

    class Args:
        min_history_days = 365
        min_ibkr_ready = 1
        min_ibkr_submitted = 1
        min_paper_outcomes = 20
        min_paper_net_points = 0.0
        min_paper_win_rate = 45.0
        max_consecutive_losses = 4
        max_allowed_blocker_count = 0

    args = Args()
    args.features_cache = str(feature_cache)
    args.blackbox_csv = str(empty_pass)
    args.expanded_csv = str(empty_pass)
    args.label_rules_csv = str(empty_pass)
    args.purged_csv = str(empty_pass)
    args.feasibility_bins_csv = str(empty_oracle)
    args.pair_feasibility_bins_csv = str(empty_oracle)
    args.closest_walkforward_csv = str(empty_pass)
    args.model_walkforward_csv = str(empty_pass)
    args.state_walkforward_csv = str(empty_pass)
    args.bar_walkforward_csv = str(empty_pass)
    args.agent_audit = str(agent_audit)
    args.ibkr_audit = str(ibkr_audit)

    result = audit_goal_script.audit_goal(args)

    assert result["status"] == "blocked"
    assert "no_60wr_2r_blackbox_candidate" in result["blockers"]
    assert "databento_api_key_missing" in result["blockers"]
    assert "ibkr_account_missing" in result["blockers"]


def test_goal_readiness_audit_counts_bar_only_walkforward_pass(tmp_path, monkeypatch):
    feature_cache = tmp_path / "features.pkl"
    pd.to_pickle(
        {
            "sample": pd.DataFrame(
                {
                    "ts": pd.date_range("2025-01-01", periods=366, freq="D", tz="UTC"),
                    "Close": range(366),
                }
            )
        },
        feature_cache,
    )
    empty_pass = tmp_path / "empty.csv"
    pd.DataFrame({"blackbox_pass": []}).to_csv(empty_pass, index=False)
    bar_pass = tmp_path / "bar.csv"
    pd.DataFrame({"blackbox_pass": [True]}).to_csv(bar_pass, index=False)
    empty_oracle = tmp_path / "oracle.csv"
    pd.DataFrame({"oracle_60wr_2r_pass": []}).to_csv(empty_oracle, index=False)
    agent_audit = tmp_path / "agent.jsonl"
    ibkr_audit = tmp_path / "ibkr.jsonl"
    agent_audit.write_text("", encoding="utf-8")
    ibkr_audit.write_text("", encoding="utf-8")
    monkeypatch.setenv("DATABENTO_API_KEY", "test")
    monkeypatch.setenv("IBKR_ACCOUNT", "DU123")

    class Args:
        min_history_days = 365
        min_ibkr_ready = 0
        min_ibkr_submitted = 0
        min_paper_outcomes = 0
        min_paper_net_points = 0.0
        min_paper_win_rate = 0.0
        max_consecutive_losses = 4
        max_allowed_blocker_count = 99

    args = Args()
    args.features_cache = str(feature_cache)
    args.blackbox_csv = str(empty_pass)
    args.expanded_csv = str(empty_pass)
    args.label_rules_csv = str(empty_pass)
    args.purged_csv = str(empty_pass)
    args.feasibility_bins_csv = str(empty_oracle)
    args.pair_feasibility_bins_csv = str(empty_oracle)
    args.closest_walkforward_csv = str(empty_pass)
    args.model_walkforward_csv = str(empty_pass)
    args.state_walkforward_csv = str(empty_pass)
    args.bar_walkforward_csv = str(bar_pass)
    args.agent_audit = str(agent_audit)
    args.ibkr_audit = str(ibkr_audit)

    result = audit_goal_script.audit_goal(args)

    assert result["total_2r_passes"] == 1
    assert result["checks"]["bar_only_walkforward_2r"]["passes"] == 1
    assert "no_60wr_2r_blackbox_candidate" not in result["blockers"]


def test_model_walkforward_applies_train_feature_bins_without_test_labels():
    features = pd.DataFrame(
        {
            "signal_index": range(8),
            "return_3m": [0.1, 0.2, 0.8, 0.9, 0.15, 0.25, 0.85, 0.95],
            "return_5m": [0.0] * 8,
            "range_1m": [1.0] * 8,
            "body_to_range": [0.0] * 8,
            "realized_vol_15": [0.1] * 8,
            "realized_vol_30": [0.1] * 8,
            "z_5": [0.0] * 8,
            "z_10": [0.0] * 8,
            "vwap_distance": [0.0] * 8,
            "imbalance": [0.0] * 8,
            "spread_mean": [1.0] * 8,
            "depth_mean": [10.0] * 8,
            "quote_count": [100] * 8,
        }
    )
    train_events = pd.DataFrame(
        {
            "signal_index": [0, 1, 2, 3],
            "net_points": [-1.0, -1.0, 1.0, 1.0],
        },
        index=[0, 1, 2, 3],
    )
    test_events = pd.DataFrame(
        {
            "signal_index": [4, 5, 6, 7],
            "net_points": [1.0, 1.0, -1.0, -1.0],
        },
        index=[4, 5, 6, 7],
    )

    class Args:
        min_train_events = 4
        bin_count = 2
        max_weight_features = 3

    train_scores, _weights, feature_models = model_search.train_rank_scores(features, train_events, Args)
    candidate = model_search.ModelCandidate(
        name="model",
        direction=1,
        stop_loss_points=4.0,
        take_profit_points=8.0,
        horizon_minutes=30,
        session="all",
        threshold_quantile=0.5,
        score_threshold=0.0,
        train_score=1.0,
        train_trades=4,
        train_win_rate=0.5,
        train_net_points=1.0,
        train_profit_factor=1.0,
        train_bracket_exit_share=1.0,
        feature_weights=_weights,
        feature_models=feature_models,
    )

    test_scores = model_search.apply_rank_scores(features, test_events, candidate)

    assert not train_scores.empty
    assert test_scores.loc[6] > test_scores.loc[4]


def test_state_walkforward_applies_train_quantile_state_spec():
    train_features = pd.DataFrame(
        {
            "return_3m": [0.0, 1.0, 2.0],
            "return_10m": [0.0, 1.0, 2.0],
            "realized_vol_30": [0.0, 1.0, 2.0],
            "z_10": [0.0, 1.0, 2.0],
            "vwap_distance": [0.0, 1.0, 2.0],
            "imbalance": [0.0, 1.0, 2.0],
            "quote_count": [0.0, 1.0, 2.0],
        }
    )
    test_features = pd.DataFrame(
        {
            "return_3m": [-1.0, 3.0],
            "return_10m": [-1.0, 3.0],
            "realized_vol_30": [-1.0, 3.0],
            "z_10": [-1.0, 3.0],
            "vwap_distance": [-1.0, 3.0],
            "imbalance": [-1.0, 3.0],
            "quote_count": [-1.0, 3.0],
        }
    )

    class Args:
        state_quantiles = [0.33, 0.67]

    train_states, spec = state_search.build_state_labels(train_features, Args)
    test_states = state_search.apply_state_labels(test_features, spec)

    assert train_states.iloc[0].startswith("l|")
    assert test_states.tolist()[0].startswith("l|")
    assert test_states.tolist()[1].startswith("h|")
