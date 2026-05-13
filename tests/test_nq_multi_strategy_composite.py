from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "optimize_nq_multi_strategy_composite.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("optimize_nq_multi_strategy_composite", SCRIPT_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["optimize_nq_multi_strategy_composite"] = module
SPEC.loader.exec_module(module)


def _audit_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "strategy_source": "regime_transition",
                "strategy_label": "core_breakout",
                "candidate": "core_breakout_candidate",
                "long_term_research_pass": True,
                "readiness_tier": "promote_to_paper_validation",
                "net_points": 200.0,
                "profit_factor": 1.8,
                "net_to_drawdown": 8.0,
                "positive_year_rate": 1.0,
                "positive_180d_rate": 1.0,
                "cost_3_125_net_points": 120.0,
            },
            {
                "strategy_source": "ict_order_flow_shift",
                "strategy_label": "ofs_volume",
                "candidate": "ofs_volume",
                "long_term_research_pass": False,
                "readiness_tier": "continue_research",
                "net_points": 90.0,
                "profit_factor": 1.3,
                "net_to_drawdown": 2.0,
                "positive_year_rate": 0.7,
                "positive_180d_rate": 0.7,
                "cost_3_125_net_points": 20.0,
            },
            {
                "strategy_source": "screenshot_smc_momentum",
                "strategy_label": "bad_bos",
                "candidate": "bad_bos",
                "long_term_research_pass": False,
                "readiness_tier": "reject_current_form",
                "net_points": -20.0,
                "profit_factor": 0.8,
                "net_to_drawdown": -1.0,
                "positive_year_rate": 0.2,
                "positive_180d_rate": 0.2,
                "cost_3_125_net_points": -80.0,
            },
        ]
    )


def test_composite_optimizer_combines_core_and_research_with_conflict_resolution(tmp_path: Path) -> None:
    audit = tmp_path / "audit.csv"
    regime = tmp_path / "regime.csv"
    ofs = tmp_path / "ofs.csv"
    screenshot = tmp_path / "screenshot.csv"
    report = tmp_path / "report.html"
    selected = tmp_path / "selected.csv"
    dropped = tmp_path / "dropped.csv"
    ranking = tmp_path / "ranking.csv"
    components = tmp_path / "components.csv"
    walkforward = tmp_path / "walkforward.csv"

    _audit_rows().to_csv(audit, index=False)
    pd.DataFrame(
        [
            {
                "audit_label": "core_breakout",
                "candidate": "core_breakout_candidate",
                "entry_ts": "2020-01-03 20:00:00+00:00",
                "exit_ts": "2020-01-03 21:00:00+00:00",
                "direction": 1,
                "net_points": 30.0,
                "gross_points": 30.5,
                "entry_index": 1,
                "exit_index": 3,
            },
            {
                "audit_label": "core_breakout",
                "candidate": "core_breakout_candidate",
                "entry_ts": "2021-01-04 20:00:00+00:00",
                "exit_ts": "2021-01-04 21:00:00+00:00",
                "direction": 1,
                "net_points": 30.0,
                "gross_points": 30.5,
                "entry_index": 10,
                "exit_index": 12,
            },
            {
                "audit_label": "core_breakout",
                "candidate": "core_breakout_candidate",
                "entry_ts": "2022-01-04 20:00:00+00:00",
                "exit_ts": "2022-01-04 21:00:00+00:00",
                "direction": 1,
                "net_points": 30.0,
                "gross_points": 30.5,
                "entry_index": 20,
                "exit_index": 22,
            },
        ]
    ).to_csv(regime, index=False)
    pd.DataFrame(
        [
            {
                "template": "ofs_volume",
                "entry_ts": "2020-01-03 20:30:00+00:00",
                "exit_ts": "2020-01-03 20:45:00+00:00",
                "direction": 1,
                "net_points": 100.0,
                "gross_points": 100.5,
                "entry_index": 4,
                "exit_index": 4,
            },
            {
                "template": "ofs_volume",
                "entry_ts": "2021-02-01 16:00:00+00:00",
                "exit_ts": "2021-02-01 16:30:00+00:00",
                "direction": 1,
                "net_points": 20.0,
                "gross_points": 20.5,
                "entry_index": 30,
                "exit_index": 31,
            },
            {
                "template": "ofs_volume",
                "entry_ts": "2022-02-01 16:00:00+00:00",
                "exit_ts": "2022-02-01 16:30:00+00:00",
                "direction": 1,
                "net_points": 20.0,
                "gross_points": 20.5,
                "entry_index": 40,
                "exit_index": 41,
            },
        ]
    ).to_csv(ofs, index=False)
    pd.DataFrame(
        [
            {
                "template": "bad_bos",
                "entry_ts": "2021-03-01 16:00:00+00:00",
                "exit_ts": "2021-03-01 16:30:00+00:00",
                "direction": -1,
                "net_points": 999.0,
                "gross_points": 999.0,
            }
        ]
    ).to_csv(screenshot, index=False)

    args = Namespace(
        audit=str(audit),
        regime_trades=str(regime),
        ofs_trades=str(ofs),
        screenshot_trades=str(screenshot),
        report=str(report),
        selected_trades_output=str(selected),
        dropped_trades_output=str(dropped),
        ranking_output=str(ranking),
        components_output=str(components),
        walkforward_output=str(walkforward),
        max_combo_size=3,
        max_per_family=1,
        include_coverage_candidates=False,
        coverage_max_per_family=1,
        max_coverage_candidates=0,
        min_full_year_trades=0,
        full_year_start=2020,
        full_year_end=0,
        min_train_years=1,
        min_train_trades=1,
        rank_on_common_window=True,
        generated_at="2026-05-13 00:00 UTC",
    )

    result = module.write_outputs(args)

    assert result["best_labels"] == ["core_breakout", "ofs_volume"]
    assert result["best_eligibility"] == "research_diversified"
    assert report.exists()
    assert selected.exists()
    assert dropped.exists()
    assert ranking.exists()
    selected_frame = pd.read_csv(selected)
    dropped_frame = pd.read_csv(dropped)
    components_frame = pd.read_csv(components)
    assert set(selected_frame["strategy_label"]) == {"core_breakout", "ofs_volume"}
    assert len(dropped_frame) == 1
    assert dropped_frame["strategy_label"].iloc[0] == "ofs_volume"
    assert "risk_weight" in selected_frame.columns
    assert sorted(selected_frame["risk_weight"].round(2).unique().tolist()) == [0.3, 0.7]
    assert "bad_bos" in set(components_frame["strategy_label"])
    bad_row = components_frame[components_frame["strategy_label"].eq("bad_bos")].iloc[0]
    assert bad_row["eligible_for_composite"] in {False, "False"}
    html = report.read_text(encoding="utf-8")
    assert "NQ 多策略组合优化报告" in html
    assert "同K进出率" in html
    assert "风险预算" in html
    assert "预算净点" in html
    assert "风险预算净点曲线" in html
    assert "research_extension" in html


def _many_trades(label: str, year: int, count: int, points: float, *, start_day: int = 1) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(count):
        day = start_day + index // 12
        minute = (index % 12) * 5
        rows.append(
            {
                "template": label,
                "entry_ts": f"{year}-01-{day:02d} 14:{minute:02d}:00+00:00",
                "exit_ts": f"{year}-01-{day:02d} 14:{minute + 1:02d}:00+00:00",
                "direction": 1,
                "net_points": points,
                "gross_points": points,
                "entry_index": index * 10,
                "exit_index": index * 10 + 1,
            }
        )
    return rows


def test_annual_trade_floor_selects_coverage_combo_and_ignores_partial_year(tmp_path: Path) -> None:
    audit = tmp_path / "audit.csv"
    regime = tmp_path / "regime.csv"
    ofs = tmp_path / "ofs.csv"
    screenshot = tmp_path / "screenshot.csv"
    report = tmp_path / "report.html"
    selected = tmp_path / "selected.csv"
    dropped = tmp_path / "dropped.csv"
    ranking = tmp_path / "ranking.csv"
    components = tmp_path / "components.csv"
    walkforward = tmp_path / "walkforward.csv"

    pd.DataFrame(
        [
            {
                "strategy_source": "regime_transition",
                "strategy_label": "profitable_core",
                "candidate": "profitable_core",
                "long_term_research_pass": True,
                "readiness_tier": "promote_to_paper_validation",
                "net_points": 1000.0,
                "profit_factor": 4.0,
                "net_to_drawdown": 20.0,
                "positive_year_rate": 1.0,
                "positive_180d_rate": 1.0,
                "cost_3_125_net_points": 900.0,
            },
            {
                "strategy_source": "screenshot_smc_momentum",
                "strategy_label": "coverage_displacement",
                "candidate": "coverage_displacement",
                "long_term_research_pass": False,
                "readiness_tier": "reject_current_form",
                "net_points": -100.0,
                "profit_factor": 0.9,
                "net_to_drawdown": -1.0,
                "positive_year_rate": 0.0,
                "positive_180d_rate": 0.0,
                "cost_3_125_net_points": -200.0,
            },
        ]
    ).to_csv(audit, index=False)
    pd.DataFrame(
        [
            {
                "audit_label": "profitable_core",
                "candidate": "profitable_core",
                "entry_ts": "2020-01-01 13:00:00+00:00",
                "exit_ts": "2020-01-01 13:01:00+00:00",
                "direction": 1,
                "net_points": 500.0,
                "gross_points": 500.0,
            },
            {
                "audit_label": "profitable_core",
                "candidate": "profitable_core",
                "entry_ts": "2021-01-01 13:00:00+00:00",
                "exit_ts": "2021-01-01 13:01:00+00:00",
                "direction": 1,
                "net_points": 500.0,
                "gross_points": 500.0,
            },
            {
                "audit_label": "profitable_core",
                "candidate": "profitable_core",
                "entry_ts": "2022-01-01 13:00:00+00:00",
                "exit_ts": "2022-01-01 13:01:00+00:00",
                "direction": 1,
                "net_points": 500.0,
                "gross_points": 500.0,
            },
        ]
    ).to_csv(regime, index=False)
    pd.DataFrame(columns=["template", "entry_ts", "exit_ts", "direction", "net_points", "gross_points"]).to_csv(
        ofs, index=False
    )
    pd.DataFrame(
        _many_trades("coverage_displacement", 2020, 4, -1.0)
        + _many_trades("coverage_displacement", 2021, 4, -1.0)
        + _many_trades("coverage_displacement", 2022, 1, -1.0)
    ).to_csv(screenshot, index=False)

    args = Namespace(
        audit=str(audit),
        regime_trades=str(regime),
        ofs_trades=str(ofs),
        screenshot_trades=str(screenshot),
        report=str(report),
        selected_trades_output=str(selected),
        dropped_trades_output=str(dropped),
        ranking_output=str(ranking),
        components_output=str(components),
        walkforward_output=str(walkforward),
        max_combo_size=2,
        max_per_family=1,
        include_coverage_candidates=True,
        coverage_max_per_family=2,
        max_coverage_candidates=2,
        min_full_year_trades=4,
        full_year_start=2020,
        full_year_end=2021,
        min_train_years=1,
        min_train_trades=1,
        rank_on_common_window=True,
        generated_at="2026-05-13 00:00 UTC",
    )

    result = module.write_outputs(args)

    assert result["best_labels"] == ["profitable_core", "coverage_displacement"]
    assert result["best_eligibility"] == "coverage_research"
    assert result["annual_trade_floor_pass"] is True
    assert result["full_years_checked"] == [2020, 2021]
    assert result["best_metrics"]["min_full_year_trades"] == 5.0
    selected_frame = pd.read_csv(selected)
    assert set(selected_frame["entry_ts"].str[:4]) == {"2020", "2021", "2022"}
    ranking_frame = pd.read_csv(ranking)
    core_only = ranking_frame[ranking_frame["combo"].eq("profitable_core")].iloc[0]
    assert core_only["annual_trade_floor_pass"] == 0.0
    assert core_only["annual_trade_floor_deficit"] == 6.0
    html = report.read_text(encoding="utf-8")
    assert "完整年份交易次数" in html
    assert "coverage_research" in html
    assert "年度交易次数约束" in html
    assert "<td>2020</td>" in html
    assert "<td>2,020</td>" not in html
