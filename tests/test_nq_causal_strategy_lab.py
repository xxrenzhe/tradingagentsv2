from __future__ import annotations

import importlib.util
import sqlite3
import sys
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "evolve_nq_2020_causal_strategy_lab.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("evolve_nq_2020_causal_strategy_lab", SCRIPT_PATH)
script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["evolve_nq_2020_causal_strategy_lab"] = script
SPEC.loader.exec_module(script)


def test_runtime_future_perturbation_audit_keeps_past_unchanged() -> None:
    bars = _synthetic_bars(360)
    features = script.prepare_evolution_features(bars)

    result = script.runtime_future_perturbation_audit(
        features,
        selected_feature_ids=["trend_start_long_displacement_us_rth", "w_bottom_reclaim_us_rth"],
        rows=260,
        cutoff_row=180,
    )

    assert result["passed"]
    assert result["changed_feature_columns_before_cutoff"] == []
    assert result["changed_selected_signals_before_cutoff"] == []


def test_build_walk_forward_windows_keeps_train_before_test_with_purge() -> None:
    windows = script.build_walk_forward_windows(
        walk_start_date="2022-01-01",
        end_date="2022-12-31",
        train_days=120,
        purge_days=7,
        test_days=60,
        step_days=60,
    )

    assert not windows.empty
    assert windows["past_only"].all()
    assert (windows["train_end"] <= windows["test_start"] - pd.Timedelta(days=7)).all()
    assert (windows["test_start"] < windows["test_end"]).all()


def test_round_robin_templates_preserves_feature_diversity_under_cap() -> None:
    feature_a = script.StrategyTemplate(
        name="a1",
        feature_id="a",
        family="trend_start",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=1.0,
        horizon_minutes=30,
        confirm_bars=2,
        pullback_atr=0.25,
        stop_atr_mult=1.5,
    )
    feature_b = script.StrategyTemplate(
        **{**feature_a.__dict__, "name": "b1", "feature_id": "b", "direction": -1}
    )
    feature_c = script.StrategyTemplate(
        **{**feature_a.__dict__, "name": "a2", "feature_id": "a", "reward_risk": 1.5}
    )

    selected = script.round_robin_templates({"a": [feature_a, feature_c], "b": [feature_b]}, max_template_count=2)

    assert [item.feature_id for item in selected] == ["a", "b"]


def test_annotate_candidate_readiness_marks_research_pass() -> None:
    aggregate = pd.DataFrame(
        [
            {
                "template": "candidate_a",
                "feature_id": "feature_a",
                "family": "trend_start",
                "selected_folds": 3,
                "test_trades": 80,
                "test_net_points": 100.0,
                "test_profit_factor": 1.2,
                "positive_test_fold_rate": 2 / 3,
                "walk_forward_score": 5.0,
            },
            {
                "template": "candidate_b",
                "feature_id": "feature_b",
                "family": "trend_start",
                "selected_folds": 1,
                "test_trades": 20,
                "test_net_points": 50.0,
                "test_profit_factor": 1.5,
                "positive_test_fold_rate": 1.0,
                "walk_forward_score": 6.0,
            },
        ]
    )

    result = script.annotate_candidate_readiness(
        aggregate,
        pd.DataFrame(),
        pd.DataFrame(),
        Namespace(min_selected_folds=3, min_oos_trades=60, min_positive_fold_rate=0.55),
    )

    assert bool(result.loc[result["template"].eq("candidate_a"), "research_pass"].iloc[0])
    assert not bool(result.loc[result["template"].eq("candidate_b"), "research_pass"].iloc[0])


def test_pressure_frame_applies_cost_stress_and_rolling_summary() -> None:
    aggregate = pd.DataFrame(
        [
            {
                "template": "candidate_a",
                "feature_id": "feature_a",
                "family": "trend_start",
                "entry_mode": "next_open",
                "stop_mode": "event_extreme",
                "context_filter": "all",
                "exit_mode": "bracket",
                "reward_risk": 1.5,
                "horizon_minutes": 60,
                "selected_folds": 3,
                "positive_test_fold_rate": 1.0,
            }
        ]
    )
    trades = pd.DataFrame(
        [
            {
                "template": "candidate_a",
                "entry_ts": pd.Timestamp("2022-01-01", tz="UTC") + pd.Timedelta(days=index * 20),
                "gross_points": 8.0 if index % 3 else -4.0,
                "net_points": (8.0 if index % 3 else -4.0) - 0.625,
                "exit_reason": "take_profit" if index % 3 else "stop_loss",
            }
            for index in range(18)
        ]
    )
    folds = pd.DataFrame(
        [
            {"template": "candidate_a", "fold": fold}
            for fold in range(3)
        ]
    )

    pressure = script.build_pressure_frame(
        aggregate,
        trades,
        folds,
        Namespace(
            top_n=5,
            rolling_days=120,
            rolling_step_days=60,
            cost_multipliers=[1.0, 2.0, 3.0],
            min_selected_folds=3,
            min_oos_trades=10,
            min_positive_fold_rate=0.55,
        ),
    )

    assert not pressure.empty
    row = pressure.iloc[0]
    assert bool(row["pressure_pass"])
    assert row["cost_2x_net_points"] < row["cost_1x_net_points"]
    assert row["positive_rolling_rate"] > 0


def test_record_lab_memory_caps_active_notes(tmp_path: Path) -> None:
    memory_db = tmp_path / "memory.sqlite"
    feature_summary = pd.DataFrame(
        [
            {
                "feature_id": "feature_a",
                "family": "trend_start",
                "direction_hint": "long",
                "description": "Synthetic feature",
                "events": 100,
                "opportunity_score": 2.0,
            }
        ]
    )
    aggregate = pd.DataFrame(
        [
            {
                "template": "template_a",
                "feature_id": "feature_a",
                "context_filter": "all",
                "research_pass": True,
                "candidate_quality": "research_candidate",
                "selected_folds": 3,
                "test_trades": 60,
                "test_net_points": 90.0,
                "test_profit_factor": 1.2,
                "positive_test_fold_rate": 0.67,
            }
        ]
    )
    pressure = pd.DataFrame(
        [
            {
                "template": "template_a",
                "feature_id": "feature_a",
                "pressure_pass": True,
                "oos_trades": 60,
                "oos_net_points": 80.0,
                "oos_profit_factor": 1.15,
                "cost_2x_net_points": 60.0,
                "positive_rolling_rate": 0.75,
            }
        ]
    )

    script.record_lab_memory(
        memory_db,
        feature_summary,
        aggregate,
        pressure,
        {"passed": True},
        {"status": "fallback"},
        Namespace(memory_top_n=5, memory_note_cap_per_key=1),
    )

    with sqlite3.connect(memory_db) as connection:
        active_count = connection.execute(
            "SELECT COUNT(*) FROM experience_notes WHERE status = 'active'"
        ).fetchone()[0]

    assert active_count >= 3


def test_markdown_report_uses_internal_table_renderer(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    feature_summary = pd.DataFrame(
        [
            {
                "feature_id": "feature_a",
                "family": "trend_start",
                "direction_hint": "long",
                "events": 10,
                "opportunity_score": 1.0,
                "favorable_close_rate_60m": 0.6,
                "median_mfe_60m": 12.0,
                "median_mae_60m": 6.0,
                "hit_20pt_rate_60m": 0.2,
                "adverse_10pt_rate_60m": 0.3,
            }
        ]
    )
    aggregate = pd.DataFrame(
        [
            {
                "research_pass": True,
                "candidate_quality": "research_candidate",
                "template": "template_a",
                "feature_id": "feature_a",
                "family": "trend_start",
                "entry_mode": "next_open",
                "stop_mode": "atr",
                "context_filter": "all",
                "exit_mode": "bracket",
                "reward_risk": 1.5,
                "horizon_minutes": 60,
                "selected_folds": 3,
                "positive_test_fold_rate": 0.67,
                "test_trades": 80,
                "test_net_points": 100.0,
                "test_profit_factor": 1.2,
                "test_win_rate": 0.48,
                "test_payoff_ratio": 1.5,
                "test_max_drawdown_points": 30.0,
                "walk_forward_score": 5.0,
            }
        ]
    )
    pressure = pd.DataFrame(
        [
            {
                "pressure_pass": True,
                "template": "template_a",
                "feature_id": "feature_a",
                "selected_folds": 3,
                "positive_test_fold_rate": 0.67,
                "oos_trades": 80,
                "oos_net_points": 90.0,
                "oos_profit_factor": 1.2,
                "oos_win_rate": 0.48,
                "oos_payoff_ratio": 1.5,
                "oos_max_drawdown_points": 30.0,
                "cost_2x_net_points": 70.0,
                "cost_2x_profit_factor": 1.1,
                "cost_3x_net_points": 50.0,
                "positive_year_rate": 1.0,
                "positive_rolling_rate": 0.8,
                "min_rolling_net_points": 5.0,
                "pressure_score": 8.0,
            }
        ]
    )

    script.write_markdown_report(
        path,
        feature_summary=feature_summary,
        aggregate=aggregate,
        pressure=pressure,
        leakage={"passed": True},
        llm_payload={"summary": "ok", "production_readiness": {"ready_for_live": False}},
        selected_feature_ids=["feature_a"],
        templates=[],
        args=Namespace(start_date="2020-01-01", end_date="2026-04-28"),
    )

    text = path.read_text(encoding="utf-8")
    assert "| feature_id |" in text
    assert "template_a" in text


def _synthetic_bars(rows: int) -> pd.DataFrame:
    ts = pd.date_range("2020-01-01 13:30", periods=rows, freq="min", tz="UTC")
    base = 9000.0 + np.cumsum(np.sin(np.arange(rows) / 9.0) * 0.8 + 0.2)
    open_ = base
    close = base + np.sin(np.arange(rows) / 5.0) * 0.5
    high = np.maximum(open_, close) + 1.0
    low = np.minimum(open_, close) - 1.0
    volume = 100 + (np.arange(rows) % 30) * 3
    return pd.DataFrame(
        {
            "ts": ts,
            "symbol": "NQH0",
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }
    )
