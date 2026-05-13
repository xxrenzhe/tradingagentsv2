from __future__ import annotations

import importlib.util
import pickle
import sys
from argparse import Namespace
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
SCRIPT_PATH = SCRIPTS_DIR / "generate_nq_lightglow_paper_readiness_report.py"
SPEC = importlib.util.spec_from_file_location("generate_nq_lightglow_paper_readiness_report", SCRIPT_PATH)
paper_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["generate_nq_lightglow_paper_readiness_report"] = paper_script
SPEC.loader.exec_module(paper_script)


def _bars(start: str = "2020-01-01 00:00", periods: int = 1800) -> pd.DataFrame:
    ts = pd.date_range(start, periods=periods, freq="min", tz="UTC")
    rows = []
    for index, stamp in enumerate(ts):
        base = 9000.0 + index * 0.08 + (index % 17) * 0.05
        close = base + (0.4 if index % 2 else -0.3)
        rows.append(
            {
                "ts": stamp,
                "symbol": "NQ",
                "Open": base,
                "High": max(base, close) + 0.8,
                "Low": min(base, close) - 0.7,
                "Close": close,
                "Volume": 100 + index % 200,
            }
        )
    return pd.DataFrame(rows)


def _write_bars(path: Path, bars: pd.DataFrame) -> None:
    with path.open("wb") as file:
        pickle.dump({"bars": bars}, file)


def _feature_trades() -> pd.DataFrame:
    rows = []
    for year in range(2020, 2026):
        for month in (1, 2):
            for dow in range(5):
                for sample in range(16):
                    entry = pd.Timestamp(year=year, month=month, day=3 + dow, hour=14, minute=sample, tz="UTC")
                    gross = 6.0 if dow % 2 == 0 else -2.0
                    rows.append(
                        {
                            "entry_ts": entry,
                            "exit_ts": entry + pd.Timedelta(minutes=10),
                            "year": year,
                            "month": month,
                            "dow": dow,
                            "direction": 1,
                            "entry_price": 10000.0,
                            "exit_price": 10000.0 + gross,
                            "gross_points": gross,
                            "net_points": gross - paper_script.ROUND_TRIP_COST_POINTS,
                        }
                    )
    return pd.DataFrame(rows)


def _composite_trades() -> pd.DataFrame:
    rows = []
    for year in range(2020, 2026):
        for index in range(3):
            entry = pd.Timestamp(year=year, month=1, day=3 + index, hour=15, minute=0, tz="UTC")
            rows.append(
                {
                    "entry_ts": entry,
                    "exit_ts": entry + pd.Timedelta(minutes=20),
                    "strategy_source": paper_script.LIGHTGLOW_SOURCE,
                    "strategy_label": "Stable 2020-2021 trained action map",
                    "feature_family": "lightglow_premium_discount_reversal",
                    "direction": 1,
                    "entry_price": 10000.0,
                    "exit_price": 10010.0,
                    "gross_points": 10.0,
                    "net_points": 9.375,
                    "risk_weight": 1.0,
                }
            )
        entry = pd.Timestamp(year=year, month=1, day=10, hour=16, minute=0, tz="UTC")
        rows.append(
            {
                "entry_ts": entry,
                "exit_ts": entry + pd.Timedelta(minutes=90),
                "strategy_source": paper_script.TIMECELL_SOURCE,
                "strategy_label": paper_script.TIMECELL_LABEL,
                "feature_family": "rollstable_timecell_direction_map",
                "direction": 1,
                "entry_price": 10000.0,
                "exit_price": 9990.0,
                "gross_points": -10.0,
                "net_points": -10.625,
                "risk_weight": 0.05,
            }
        )
    return pd.DataFrame(rows)


def test_runtime_future_perturbation_audit_is_causal() -> None:
    result = paper_script.runtime_future_perturbation_audit(_bars(), cutoff_index=900, sample_rows=1400)

    assert result["passed"] is True
    assert result["severity"] == "pass"
    assert result["baseline_hash"] == result["perturbed_hash"]


def test_walk_forward_uses_past_train_years_only() -> None:
    feature_trades = _feature_trades()
    composite = _composite_trades()

    wf, wf_trades = paper_script.run_walk_forward(feature_trades, composite)

    assert wf["test_year"].tolist() == [2022, 2023, 2024, 2025]
    assert set(wf_trades["entry_ts"].dt.year.unique()) == {2022, 2023, 2024, 2025}
    first = wf.iloc[0]
    assert first["train_start"] == 2020
    assert first["train_end"] == 2021
    assert first["action_cells"] > 0


def test_same_bar_and_risk_budget_guards() -> None:
    trades = _composite_trades()
    same_bar = trades.copy()
    same_bar.loc[0, "exit_ts"] = same_bar.loc[0, "entry_ts"]

    audit = paper_script.same_bar_audit(same_bar)
    mapping = paper_script.risk_budget_mapping()

    assert audit["passed"] is False
    assert audit["same_bar_trades"] == 1
    timecell = mapping[mapping["component"].eq("Timecell")].iloc[0]
    assert not bool(timecell["executable"])
    assert timecell["mnq_equivalent"] < 1


def test_loss_learning_selected_rule_must_work_oos_to_be_positive() -> None:
    bars = _bars("2020-01-01 00:00", periods=7000)
    trades = _composite_trades()
    result = paper_script.run_loss_learning_walk_forward(
        trades,
        bars,
        candidates=("lightglow_extreme_momentum_veto",),
        min_train_removed_trades=1,
    )

    assert "loss_learning_verdict" in result.columns
    assert result["loss_learning_verdict"].iloc[0] in {"not_selected", "not_proven", "positive_candidate"}


def test_report_generation_writes_outputs(tmp_path: Path) -> None:
    feature_path = tmp_path / "features.pkl"
    composite_path = tmp_path / "composite.csv"
    bars_path = tmp_path / "bars.pkl"
    output = tmp_path / "report.html"
    markdown = tmp_path / "report.md"
    summary = tmp_path / "summary.json"
    wf = tmp_path / "wf.csv"
    wf_trades = tmp_path / "wf_trades.csv"
    stress = tmp_path / "stress.csv"
    leakage = tmp_path / "leakage.csv"
    loss_learning = tmp_path / "loss_learning.csv"
    reverse_diagnostic = tmp_path / "reverse_diagnostic.csv"
    plan = tmp_path / "plan.csv"

    _feature_trades().to_pickle(feature_path)
    _composite_trades().to_csv(composite_path, index=False)
    _write_bars(bars_path, _bars(periods=2200))

    result = paper_script.write_report(
        Namespace(
            feature_trades=str(feature_path),
            composite_trades=str(composite_path),
            lightglow_oos_trades="unused.csv",
            bars=str(bars_path),
            output=str(output),
            markdown_output=str(markdown),
            summary_output=str(summary),
            walk_forward_output=str(wf),
            walk_forward_trades_output=str(wf_trades),
            stress_output=str(stress),
            leakage_output=str(leakage),
            loss_learning_output=str(loss_learning),
            reverse_diagnostic_output=str(reverse_diagnostic),
            paper_plan_output=str(plan),
            generated_at="2026-05-14 00:00 UTC",
        )
    )

    html = output.read_text(encoding="utf-8")
    assert "纸盘准备度结论" in html
    assert "亏损交易学习" in html
    assert "反手做空诊断" in html
    assert "泄漏审计" in html
    assert result["readiness"]["status"] == "blocked"
    assert result["reverse_trade_verdict"] in {"reverse_not_selected", "reverse_not_proven", "reverse_positive_candidate"}
    for path in (markdown, summary, wf, wf_trades, stress, leakage, loss_learning, reverse_diagnostic, plan):
        assert path.exists()


def test_reverse_trade_diagnostic_requires_train_selected_oos_proof() -> None:
    bars = _bars("2020-01-01 00:00", periods=7000)
    trades = _composite_trades()
    result = paper_script.run_reverse_trade_diagnostic(trades, bars, thresholds=(50.0,))

    assert "reverse_trade_verdict" in result.columns
    assert result["reverse_trade_verdict"].iloc[0] in {
        "reverse_not_selected",
        "reverse_not_proven",
        "reverse_positive_candidate",
    }


def test_apply_reverse_turns_losing_long_into_short_with_cost() -> None:
    trades = pd.DataFrame(
        [
            {
                "entry_ts": pd.Timestamp("2022-01-03 16:00", tz="UTC"),
                "exit_ts": pd.Timestamp("2022-01-03 16:30", tz="UTC"),
                "strategy_source": paper_script.TIMECELL_SOURCE,
                "strategy_label": paper_script.TIMECELL_LABEL,
                "direction": 1,
                "gross_points": -10.0,
                "net_points": -10.625,
                "risk_weight": 0.05,
            }
        ]
    )
    reversed_trades = paper_script.apply_skip_or_reverse(trades, pd.Series([True]), mode="reverse")

    assert int(reversed_trades.iloc[0]["direction"]) == -1
    assert reversed_trades.iloc[0]["net_points"] == 10.0 - paper_script.ROUND_TRIP_COST_POINTS
