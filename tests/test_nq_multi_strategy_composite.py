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
        min_profit_factor=0.0,
        min_net_points=0.0,
        min_net_to_drawdown=0.0,
        min_positive_full_year_net_rate=0.0,
        full_year_start=2020,
        full_year_end=0,
        min_train_years=1,
        min_train_trades=1,
        skip_walkforward=True,
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
    assert "跳过年度 walk-forward" in html


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
        min_profit_factor=0.0,
        min_net_points=0.0,
        min_net_to_drawdown=0.0,
        min_positive_full_year_net_rate=0.0,
        full_year_start=2020,
        full_year_end=2021,
        min_train_years=1,
        min_train_trades=1,
        skip_walkforward=True,
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


def _rollstable_rows(year: int, count: int, win_points: float, loss_points: float) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(count):
        day = 1 + index // 10
        minute = (index % 10) * 5
        points = win_points if index % 2 == 0 else loss_points
        rows.append(
            {
                "entry_ts": f"{year}-02-{day:02d} 15:{minute:02d}:00+00:00",
                "exit_ts": f"{year}-02-{day:02d} 15:{minute + 1:02d}:00+00:00",
                "symbol": "NQH0",
                "direction": 1,
                "entry_price": 100.0,
                "exit_price": 100.0 + points,
                "gross_points": points,
                "net_points": points,
                "net_dollars": points * 20.0,
            }
        )
    return rows


def test_quality_gate_selects_rollstable_timecell_over_low_pf_coverage(tmp_path: Path) -> None:
    audit = tmp_path / "audit.csv"
    regime = tmp_path / "regime.csv"
    ofs = tmp_path / "ofs.csv"
    screenshot = tmp_path / "screenshot.csv"
    rollstable = tmp_path / "rollstable.csv"
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
                "strategy_label": "thin_core",
                "candidate": "thin_core",
                "long_term_research_pass": True,
                "readiness_tier": "promote_to_paper_validation",
                "net_points": 400.0,
                "profit_factor": 1.4,
                "net_to_drawdown": 7.0,
                "positive_year_rate": 1.0,
                "positive_180d_rate": 1.0,
                "cost_3_125_net_points": 300.0,
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
                "audit_label": "thin_core",
                "candidate": "thin_core",
                "entry_ts": "2020-01-01 13:00:00+00:00",
                "exit_ts": "2020-01-01 13:01:00+00:00",
                "direction": 1,
                "net_points": 200.0,
                "gross_points": 200.0,
            },
            {
                "audit_label": "thin_core",
                "candidate": "thin_core",
                "entry_ts": "2021-01-01 13:00:00+00:00",
                "exit_ts": "2021-01-01 13:01:00+00:00",
                "direction": 1,
                "net_points": 200.0,
                "gross_points": 200.0,
            },
        ]
    ).to_csv(regime, index=False)
    pd.DataFrame(columns=["template", "entry_ts", "exit_ts", "direction", "net_points", "gross_points"]).to_csv(
        ofs, index=False
    )
    pd.DataFrame(
        _many_trades("coverage_displacement", 2020, 4, -1.0)
        + _many_trades("coverage_displacement", 2021, 4, -1.0)
    ).to_csv(screenshot, index=False)
    pd.DataFrame(
        _rollstable_rows(2020, 4, 8.0, -2.0)
        + _rollstable_rows(2021, 4, 8.0, -2.0)
    ).to_csv(rollstable, index=False)

    args = Namespace(
        audit=str(audit),
        regime_trades=str(regime),
        ofs_trades=str(ofs),
        screenshot_trades=str(screenshot),
        rollstable_timecell_trades=str(rollstable),
        rollstable_timecell_label="rollstable_quality",
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
        max_coverage_candidates=1,
        min_full_year_trades=4,
        min_profit_factor=1.25,
        min_net_points=20.0,
        min_net_to_drawdown=1.0,
        min_positive_full_year_net_rate=1.0,
        full_year_start=2020,
        full_year_end=2021,
        min_train_years=1,
        min_train_trades=1,
        max_walkforward_years=0,
        skip_walkforward=True,
        rank_on_common_window=True,
        generated_at="2026-05-13 00:00 UTC",
    )

    result = module.write_outputs(args)

    assert result["best_labels"] == ["rollstable_quality"]
    assert result["best_eligibility"] == "research_diversified"
    assert result["annual_trade_floor_pass"] is True
    assert result["quality_gate_pass"] is True
    assert result["best_metrics"]["profit_factor"] == 4.0
    assert result["best_metrics"]["min_full_year_trades"] == 4.0
    assert result["best_metrics"]["positive_full_year_net_rate"] == 1.0
    components_frame = pd.read_csv(components)
    assert "coverage_displacement" in set(components_frame["strategy_label"].astype(str))
    assert "coverage_displacement" not in result["best_labels"]
    html = report.read_text(encoding="utf-8")
    assert "PF/收益质量优先于单纯凑交易次数" in html


def test_quality_gate_reports_no_pass_for_low_pf_high_frequency_candidate(tmp_path: Path) -> None:
    audit = tmp_path / "audit.csv"
    regime = tmp_path / "regime.csv"
    ofs = tmp_path / "ofs.csv"
    screenshot = tmp_path / "screenshot.csv"
    rollstable = tmp_path / "rollstable.csv"
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
                "strategy_label": "thin_core",
                "candidate": "thin_core",
                "long_term_research_pass": True,
                "readiness_tier": "promote_to_paper_validation",
                "net_points": 400.0,
                "profit_factor": 1.4,
                "net_to_drawdown": 7.0,
                "positive_year_rate": 1.0,
                "positive_180d_rate": 1.0,
                "cost_3_125_net_points": 300.0,
            },
        ]
    ).to_csv(audit, index=False)
    pd.DataFrame(
        [
            {
                "audit_label": "thin_core",
                "candidate": "thin_core",
                "entry_ts": "2020-01-01 13:00:00+00:00",
                "exit_ts": "2020-01-01 13:01:00+00:00",
                "direction": 1,
                "net_points": 200.0,
                "gross_points": 200.0,
            },
            {
                "audit_label": "thin_core",
                "candidate": "thin_core",
                "entry_ts": "2021-01-01 13:00:00+00:00",
                "exit_ts": "2021-01-01 13:01:00+00:00",
                "direction": 1,
                "net_points": 200.0,
                "gross_points": 200.0,
            },
        ]
    ).to_csv(regime, index=False)
    pd.DataFrame(columns=["template", "entry_ts", "exit_ts", "direction", "net_points", "gross_points"]).to_csv(
        ofs, index=False
    )
    pd.DataFrame(columns=["template", "entry_ts", "exit_ts", "direction", "net_points", "gross_points"]).to_csv(
        screenshot, index=False
    )
    pd.DataFrame(
        _rollstable_rows(2020, 4, 2.0, -1.8)
        + _rollstable_rows(2021, 4, 2.0, -1.8)
    ).to_csv(rollstable, index=False)

    args = Namespace(
        audit=str(audit),
        regime_trades=str(regime),
        ofs_trades=str(ofs),
        screenshot_trades=str(screenshot),
        rollstable_timecell_trades=str(rollstable),
        rollstable_timecell_label="rollstable_low_pf",
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
        max_coverage_candidates=1,
        min_full_year_trades=4,
        min_profit_factor=1.25,
        min_net_points=1.0,
        min_net_to_drawdown=1.0,
        min_positive_full_year_net_rate=1.0,
        full_year_start=2020,
        full_year_end=2021,
        min_train_years=1,
        min_train_trades=1,
        max_walkforward_years=0,
        skip_walkforward=True,
        rank_on_common_window=True,
        generated_at="2026-05-13 00:00 UTC",
    )

    result = module.write_outputs(args)

    assert result["best_labels"] == ["rollstable_low_pf"]
    assert result["annual_trade_floor_pass"] is True
    assert result["quality_gate_pass"] is False
    assert any("PF" in reason for reason in result["quality_gate_reasons"])
    html = report.read_text(encoding="utf-8")
    assert "收益质量：</strong>未通过" in html
    assert "未通过原因" in html


def test_bar_best_walkforward_trades_are_promoted_into_research_pool(tmp_path: Path) -> None:
    audit = tmp_path / "audit.csv"
    regime = tmp_path / "regime.csv"
    ofs = tmp_path / "ofs.csv"
    screenshot = tmp_path / "screenshot.csv"
    bar_best = tmp_path / "bar_best.csv"
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
                "strategy_label": "core_breakout",
                "candidate": "core_breakout",
                "long_term_research_pass": True,
                "readiness_tier": "promote_to_paper_validation",
                "net_points": 60.0,
                "profit_factor": 1.5,
                "net_to_drawdown": 3.0,
                "positive_year_rate": 1.0,
                "positive_180d_rate": 1.0,
                "cost_3_125_net_points": 50.0,
            }
        ]
    ).to_csv(audit, index=False)
    pd.DataFrame(
        [
            {
                "audit_label": "core_breakout",
                "candidate": "core_breakout",
                "entry_ts": "2022-01-03 14:00:00+00:00",
                "exit_ts": "2022-01-03 14:05:00+00:00",
                "direction": 1,
                "net_points": 20.0,
                "gross_points": 20.0,
            },
            {
                "audit_label": "core_breakout",
                "candidate": "core_breakout",
                "entry_ts": "2022-01-04 14:00:00+00:00",
                "exit_ts": "2022-01-04 14:05:00+00:00",
                "direction": 1,
                "net_points": 20.0,
                "gross_points": 20.0,
            },
        ]
    ).to_csv(regime, index=False)
    pd.DataFrame(columns=["template", "entry_ts", "exit_ts", "direction", "net_points", "gross_points"]).to_csv(
        ofs, index=False
    )
    pd.DataFrame(columns=["template", "entry_ts", "exit_ts", "direction", "net_points", "gross_points"]).to_csv(
        screenshot, index=False
    )
    pd.DataFrame(
        [
            {
                "candidate": "bar_best_momentum_lb60_thr0.0006_hold60_long_us_late",
                "entry_ts": "2022-02-05 15:00:00+00:00",
                "exit_ts": "2022-02-05 16:00:00+00:00",
                "direction": 1,
                "net_points": 90.0,
                "gross_points": 90.5,
                "entry_index": 100,
                "exit_index": 160,
            },
            {
                "candidate": "bar_best_momentum_lb60_thr0.0006_hold60_long_us_late",
                "entry_ts": "2022-03-06 15:00:00+00:00",
                "exit_ts": "2022-03-06 16:00:00+00:00",
                "direction": 1,
                "net_points": 90.0,
                "gross_points": 90.5,
                "entry_index": 200,
                "exit_index": 260,
            },
            {
                "candidate": "bar_best_mean_reversion_lb10_thr1_hold30_short_us_late",
                "entry_ts": "2022-04-07 15:00:00+00:00",
                "exit_ts": "2022-04-07 15:30:00+00:00",
                "direction": -1,
                "net_points": -10.0,
                "gross_points": -9.5,
                "entry_index": 300,
                "exit_index": 330,
            },
        ]
    ).to_csv(bar_best, index=False)

    args = Namespace(
        audit=str(audit),
        regime_trades=str(regime),
        ofs_trades=str(ofs),
        screenshot_trades=str(screenshot),
        bar_best_trades=str(bar_best),
        report=str(report),
        selected_trades_output=str(selected),
        dropped_trades_output=str(dropped),
        ranking_output=str(ranking),
        components_output=str(components),
        walkforward_output=str(walkforward),
        max_combo_size=2,
        max_per_family=1,
        include_coverage_candidates=False,
        coverage_max_per_family=1,
        max_coverage_candidates=0,
        min_full_year_trades=0,
        min_profit_factor=0.0,
        min_net_points=0.0,
        min_net_to_drawdown=0.0,
        min_positive_full_year_net_rate=0.0,
        full_year_start=2020,
        full_year_end=2022,
        min_train_years=1,
        min_train_trades=1,
        max_walkforward_years=0,
        skip_walkforward=True,
        rank_on_common_window=False,
        generated_at="2026-05-13 00:00 UTC",
    )

    result = module.write_outputs(args)

    assert result["best_labels"] == [
        "core_breakout",
        "bar_best_momentum_lb60_thr0.0006_hold60_long_us_late",
    ]
    selected_frame = pd.read_csv(selected)
    components_frame = pd.read_csv(components)
    assert module.BAR_BEST_SOURCE in set(selected_frame["strategy_source"])
    bar_best_rows = components_frame[components_frame["strategy_source"].eq(module.BAR_BEST_SOURCE)]
    assert set(bar_best_rows["strategy_label"]) == {
        "bar_best_momentum_lb60_thr0.0006_hold60_long_us_late",
    }
    assert bar_best_rows["feature_family"].iloc[0] == "bar_best_momentum"
    assert bar_best_rows["eligible_for_composite"].iloc[0] in {True, "True"}
    ranking_frame = pd.read_csv(ranking)
    assert any(
        "bar_best_momentum_lb60_thr0.0006_hold60_long_us_late" in combo
        for combo in ranking_frame["combo"].astype(str)
    )


def test_lightglow_research_trades_are_filtered_after_train_cutoff(tmp_path: Path) -> None:
    audit = tmp_path / "audit.csv"
    regime = tmp_path / "regime.csv"
    ofs = tmp_path / "ofs.csv"
    screenshot = tmp_path / "screenshot.csv"
    lightglow = tmp_path / "lightglow.csv"
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
                "strategy_label": "core_breakout",
                "candidate": "core_breakout",
                "long_term_research_pass": True,
                "readiness_tier": "promote_to_paper_validation",
                "net_points": 80.0,
                "profit_factor": 1.5,
                "net_to_drawdown": 3.0,
                "positive_year_rate": 1.0,
                "positive_180d_rate": 1.0,
                "cost_3_125_net_points": 60.0,
            }
        ]
    ).to_csv(audit, index=False)
    pd.DataFrame(
        [
            {
                "audit_label": "core_breakout",
                "candidate": "core_breakout",
                "entry_ts": "2022-01-03 14:00:00+00:00",
                "exit_ts": "2022-01-03 14:05:00+00:00",
                "direction": 1,
                "net_points": 30.0,
                "gross_points": 30.0,
            },
            {
                "audit_label": "core_breakout",
                "candidate": "core_breakout",
                "entry_ts": "2022-01-04 14:00:00+00:00",
                "exit_ts": "2022-01-04 14:05:00+00:00",
                "direction": 1,
                "net_points": 30.0,
                "gross_points": 30.0,
            },
        ]
    ).to_csv(regime, index=False)
    pd.DataFrame(columns=["template", "entry_ts", "exit_ts", "direction", "net_points", "gross_points"]).to_csv(
        ofs, index=False
    )
    pd.DataFrame(columns=["template", "entry_ts", "exit_ts", "direction", "net_points", "gross_points"]).to_csv(
        screenshot, index=False
    )
    pd.DataFrame(
        [
            {
                "candidate": "lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time",
                "entry_ts": "2021-12-30 15:00:00+00:00",
                "exit_ts": "2021-12-30 15:02:00+00:00",
                "direction": 1,
                "net_points": 500.0,
                "gross_points": 500.5,
                "entry_index": 10,
                "exit_index": 12,
            },
            {
                "candidate": "lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time",
                "entry_ts": "2022-02-01 15:00:00+00:00",
                "exit_ts": "2022-02-01 15:02:00+00:00",
                "direction": 1,
                "net_points": 120.0,
                "gross_points": 120.5,
                "entry_index": 20,
                "exit_index": 22,
            },
            {
                "candidate": "lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time",
                "entry_ts": "2022-03-01 15:00:00+00:00",
                "exit_ts": "2022-03-01 15:02:00+00:00",
                "direction": 1,
                "net_points": 120.0,
                "gross_points": 120.5,
                "entry_index": 30,
                "exit_index": 32,
            },
        ]
    ).to_csv(lightglow, index=False)

    args = Namespace(
        audit=str(audit),
        regime_trades=str(regime),
        ofs_trades=str(ofs),
        screenshot_trades=str(screenshot),
        lightglow_trades=str(lightglow),
        lightglow_train_end="2022-01-01",
        report=str(report),
        selected_trades_output=str(selected),
        dropped_trades_output=str(dropped),
        ranking_output=str(ranking),
        components_output=str(components),
        walkforward_output=str(walkforward),
        max_combo_size=2,
        max_per_family=1,
        include_coverage_candidates=False,
        coverage_max_per_family=1,
        max_coverage_candidates=0,
        min_full_year_trades=0,
        min_profit_factor=0.0,
        min_net_points=0.0,
        min_net_to_drawdown=0.0,
        min_positive_full_year_net_rate=0.0,
        full_year_start=2020,
        full_year_end=2022,
        min_train_years=1,
        min_train_trades=1,
        max_walkforward_years=0,
        skip_walkforward=True,
        rank_on_common_window=False,
        generated_at="2026-05-13 00:00 UTC",
    )

    result = module.write_outputs(args)

    assert result["best_labels"] == [
        "core_breakout",
        "lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time",
    ]
    selected_frame = pd.read_csv(selected)
    lightglow_rows = selected_frame[selected_frame["strategy_source"].eq(module.LIGHTGLOW_SOURCE)]
    assert len(lightglow_rows) == 2
    assert set(lightglow_rows["entry_ts"].str[:4]) == {"2022"}
    assert lightglow_rows["net_points"].sum() == 240.0
    components_frame = pd.read_csv(components)
    row = components_frame[components_frame["strategy_source"].eq(module.LIGHTGLOW_SOURCE)].iloc[0]
    assert row["feature_family"] == "lightglow_premium_discount_reversal"
    assert row["net_points"] == 240.0


def test_rollstable_timecell_budget_cap_reallocates_to_core() -> None:
    audit = pd.DataFrame(
        [
            {
                "strategy_label": "core",
                "deployment_tier": module.CORE_TIER,
                "feature_family": "range_compression_displacement_breakout",
                "priority_score": 100.0,
            },
            {
                "strategy_label": "rollstable",
                "deployment_tier": module.RESEARCH_TIER,
                "feature_family": module.ROLLSTABLE_TIMECELL_FAMILY,
                "priority_score": 50.0,
            },
        ]
    )

    budgets = module.risk_budget_map(
        audit,
        ("core", "rollstable"),
        family_caps={module.ROLLSTABLE_TIMECELL_FAMILY: 0.10},
    )

    assert budgets["rollstable"] == 0.10
    assert round(budgets["core"], 6) == 0.9
    assert round(sum(budgets.values()), 6) == 1.0


def test_risk_budget_quality_gate_uses_budgeted_metrics() -> None:
    metrics = {
        "annual_trade_floor_pass": 1.0,
        "profit_factor": 1.10,
        "net_points": 100.0,
        "net_to_drawdown": 2.0,
        "positive_full_year_net_rate": 1.0,
        "risk_budgeted_profit_factor": 1.30,
        "risk_budgeted_net_points": 80.0,
        "risk_budgeted_net_to_drawdown": 6.0,
        "risk_budgeted_positive_full_year_net_rate": 1.0,
    }
    args = Namespace(
        quality_gate_uses_risk_budget=True,
        min_profit_factor=1.25,
        min_net_points=50.0,
        min_net_to_drawdown=5.0,
        min_positive_full_year_net_rate=1.0,
    )

    assert module.quality_gate_pass(metrics, args) is True
    args.quality_gate_uses_risk_budget = False
    assert module.quality_gate_pass(metrics, args) is False


def test_select_best_fallback_prefers_quality_when_no_combo_passes_gate() -> None:
    args = Namespace(
        min_full_year_trades=1001,
        quality_gate_uses_risk_budget=True,
        min_profit_factor=1.25,
        min_net_points=10_000.0,
        min_net_to_drawdown=5.0,
        min_positive_full_year_net_rate=1.0,
    )
    lower_quality = module.ComboResult(
        name="higher objective but lower quality",
        labels=("a", "b", "c"),
        trades=pd.DataFrame(),
        dropped_trades=pd.DataFrame(),
        metrics={
            "annual_trade_floor_pass": 1.0,
            "risk_budgeted_profit_factor": 1.29,
            "risk_budgeted_net_points": 3_400.0,
            "risk_budgeted_net_to_drawdown": 21.0,
            "risk_budgeted_positive_full_year_net_rate": 1.0,
        },
        objective_score=200.0,
        eligibility="research_diversified",
        window_start=None,
        window_end=None,
    )
    higher_quality = module.ComboResult(
        name="lower objective but better quality",
        labels=("a", "b"),
        trades=pd.DataFrame(),
        dropped_trades=pd.DataFrame(),
        metrics={
            "annual_trade_floor_pass": 1.0,
            "risk_budgeted_profit_factor": 1.32,
            "risk_budgeted_net_points": 4_000.0,
            "risk_budgeted_net_to_drawdown": 18.0,
            "risk_budgeted_positive_full_year_net_rate": 1.0,
        },
        objective_score=100.0,
        eligibility="research_diversified",
        window_start=None,
        window_end=None,
    )

    selected = module.select_best([lower_quality, higher_quality], args)

    assert selected.name == "lower objective but better quality"


def test_fast_coverage_combos_greedily_adds_quality_core() -> None:
    candidates = pd.DataFrame(
        [
            {
                "strategy_label": "rollstable",
                "eligible_for_composite": True,
                "has_trade_coverage": True,
                "deployment_tier": module.RESEARCH_TIER,
                "feature_family": module.ROLLSTABLE_TIMECELL_FAMILY,
                "trade_rows": 8,
                "priority_score": 10.0,
                "coverage_candidate": False,
            },
            {
                "strategy_label": "core_a",
                "eligible_for_composite": True,
                "has_trade_coverage": True,
                "deployment_tier": module.CORE_TIER,
                "feature_family": "range_compression_displacement_breakout",
                "trade_rows": 2,
                "priority_score": 100.0,
                "coverage_candidate": False,
            },
        ]
    )
    audit = candidates.copy()
    audit["strategy_source"] = ["rollstable_timecell_oos", "regime_transition"]
    trades = pd.DataFrame(
        [
            *[
                {
                    "strategy_label": "rollstable",
                    "entry_ts": pd.Timestamp(f"2020-01-01 10:{index:02d}:00", tz="UTC"),
                    "exit_ts": pd.Timestamp(f"2020-01-01 10:{index + 1:02d}:00", tz="UTC"),
                    "net_points": 1.0,
                    "gross_points": 1.0,
                    "direction": 1,
                    "priority_score": 10.0,
                    "strategy_source": "rollstable_timecell_oos",
                    "feature_family": module.ROLLSTABLE_TIMECELL_FAMILY,
                }
                for index in range(4)
            ],
            *[
                {
                    "strategy_label": "rollstable",
                    "entry_ts": pd.Timestamp(f"2021-01-01 10:{index:02d}:00", tz="UTC"),
                    "exit_ts": pd.Timestamp(f"2021-01-01 10:{index + 1:02d}:00", tz="UTC"),
                    "net_points": 1.0,
                    "gross_points": 1.0,
                    "direction": 1,
                    "priority_score": 10.0,
                    "strategy_source": "rollstable_timecell_oos",
                    "feature_family": module.ROLLSTABLE_TIMECELL_FAMILY,
                }
                for index in range(4)
            ],
            {
                "strategy_label": "core_a",
                "entry_ts": pd.Timestamp("2020-01-02 10:00:00", tz="UTC"),
                "exit_ts": pd.Timestamp("2020-01-02 10:01:00", tz="UTC"),
                "net_points": 100.0,
                "gross_points": 100.0,
                "direction": 1,
                "priority_score": 100.0,
                "strategy_source": "regime_transition",
                "feature_family": "range_compression_displacement_breakout",
            },
            {
                "strategy_label": "core_a",
                "entry_ts": pd.Timestamp("2021-01-02 10:00:00", tz="UTC"),
                "exit_ts": pd.Timestamp("2021-01-02 10:01:00", tz="UTC"),
                "net_points": 100.0,
                "gross_points": 100.0,
                "direction": 1,
                "priority_score": 100.0,
                "strategy_source": "regime_transition",
                "feature_family": "range_compression_displacement_breakout",
            },
        ]
    )
    trades["same_bar_exit"] = False
    args = Namespace(
        rank_on_common_window=False,
        full_years=(2020, 2021),
        min_full_year_trades=4,
        coverage_objective=True,
        include_coverage_candidates=True,
        max_combo_size=2,
        max_per_family=1,
        coverage_max_per_family=2,
        max_coverage_candidates=0,
        min_profit_factor=0.0,
        min_net_points=0.0,
        min_net_to_drawdown=0.0,
        min_positive_full_year_net_rate=0.0,
        quality_gate_uses_risk_budget=True,
        rollstable_timecell_max_risk_budget=0.10,
    )

    combos = module.fast_coverage_combos(trades, candidates, audit, args)

    assert ("rollstable",) in combos
    assert ("rollstable", "core_a") in combos


def test_fast_coverage_combos_greedily_adds_quality_research_overlay() -> None:
    candidates = pd.DataFrame(
        [
            {
                "strategy_label": "rollstable",
                "eligible_for_composite": True,
                "has_trade_coverage": True,
                "deployment_tier": module.RESEARCH_TIER,
                "feature_family": module.ROLLSTABLE_TIMECELL_FAMILY,
                "trade_rows": 8,
                "priority_score": 10.0,
                "coverage_candidate": False,
            },
            {
                "strategy_label": "bar_best_momentum",
                "eligible_for_composite": True,
                "has_trade_coverage": True,
                "deployment_tier": module.RESEARCH_TIER,
                "feature_family": "bar_best_momentum",
                "trade_rows": 2,
                "priority_score": 200.0,
                "coverage_candidate": False,
            },
        ]
    )
    audit = candidates.copy()
    audit["strategy_source"] = ["rollstable_timecell_oos", module.BAR_BEST_SOURCE]
    trades = pd.DataFrame(
        [
            *[
                {
                    "strategy_label": "rollstable",
                    "entry_ts": pd.Timestamp(f"2020-01-01 10:{index:02d}:00", tz="UTC"),
                    "exit_ts": pd.Timestamp(f"2020-01-01 10:{index + 1:02d}:00", tz="UTC"),
                    "net_points": 1.0,
                    "gross_points": 1.0,
                    "direction": 1,
                    "priority_score": 10.0,
                    "strategy_source": "rollstable_timecell_oos",
                    "feature_family": module.ROLLSTABLE_TIMECELL_FAMILY,
                }
                for index in range(4)
            ],
            *[
                {
                    "strategy_label": "rollstable",
                    "entry_ts": pd.Timestamp(f"2021-01-01 10:{index:02d}:00", tz="UTC"),
                    "exit_ts": pd.Timestamp(f"2021-01-01 10:{index + 1:02d}:00", tz="UTC"),
                    "net_points": 1.0,
                    "gross_points": 1.0,
                    "direction": 1,
                    "priority_score": 10.0,
                    "strategy_source": "rollstable_timecell_oos",
                    "feature_family": module.ROLLSTABLE_TIMECELL_FAMILY,
                }
                for index in range(4)
            ],
            {
                "strategy_label": "bar_best_momentum",
                "entry_ts": pd.Timestamp("2020-02-01 10:00:00", tz="UTC"),
                "exit_ts": pd.Timestamp("2020-02-01 10:01:00", tz="UTC"),
                "net_points": 200.0,
                "gross_points": 200.0,
                "direction": 1,
                "priority_score": 200.0,
                "strategy_source": module.BAR_BEST_SOURCE,
                "feature_family": "bar_best_momentum",
            },
            {
                "strategy_label": "bar_best_momentum",
                "entry_ts": pd.Timestamp("2021-02-01 10:00:00", tz="UTC"),
                "exit_ts": pd.Timestamp("2021-02-01 10:01:00", tz="UTC"),
                "net_points": 200.0,
                "gross_points": 200.0,
                "direction": 1,
                "priority_score": 200.0,
                "strategy_source": module.BAR_BEST_SOURCE,
                "feature_family": "bar_best_momentum",
            },
        ]
    )
    trades["same_bar_exit"] = False
    args = Namespace(
        rank_on_common_window=False,
        full_years=(2020, 2021),
        min_full_year_trades=4,
        coverage_objective=True,
        include_coverage_candidates=True,
        max_combo_size=2,
        max_per_family=1,
        coverage_max_per_family=2,
        max_coverage_candidates=0,
        min_profit_factor=0.0,
        min_net_points=0.0,
        min_net_to_drawdown=0.0,
        min_positive_full_year_net_rate=0.0,
        quality_gate_uses_risk_budget=True,
        rollstable_timecell_max_risk_budget=0.10,
        max_research_overlay_candidates=24,
    )

    combos = module.fast_coverage_combos(trades, candidates, audit, args)

    assert ("rollstable",) in combos
    assert ("rollstable", "bar_best_momentum") in combos


def test_fast_coverage_overlay_candidate_limit_is_configurable() -> None:
    candidates = pd.DataFrame(
        [
            {
                "strategy_label": "rollstable",
                "eligible_for_composite": True,
                "has_trade_coverage": True,
                "deployment_tier": module.RESEARCH_TIER,
                "feature_family": module.ROLLSTABLE_TIMECELL_FAMILY,
                "trade_rows": 8,
                "priority_score": 100.0,
                "coverage_candidate": False,
            },
            {
                "strategy_label": "weak_overlay",
                "eligible_for_composite": True,
                "has_trade_coverage": True,
                "deployment_tier": module.RESEARCH_TIER,
                "feature_family": "bar_best_momentum",
                "trade_rows": 2,
                "priority_score": 90.0,
                "coverage_candidate": False,
            },
            {
                "strategy_label": "strong_overlay",
                "eligible_for_composite": True,
                "has_trade_coverage": True,
                "deployment_tier": module.RESEARCH_TIER,
                "feature_family": "bar_best_mean_reversion",
                "trade_rows": 2,
                "priority_score": 80.0,
                "coverage_candidate": False,
            },
        ]
    )
    audit = candidates.copy()
    audit["strategy_source"] = ["rollstable_timecell_oos", module.BAR_BEST_SOURCE, module.BAR_BEST_SOURCE]
    rows: list[dict[str, object]] = []
    for year in (2020, 2021):
        rows.extend(
            [
                {
                    "strategy_label": "rollstable",
                    "entry_ts": pd.Timestamp(f"{year}-01-01 10:{index:02d}:00", tz="UTC"),
                    "exit_ts": pd.Timestamp(f"{year}-01-01 10:{index + 1:02d}:00", tz="UTC"),
                    "net_points": 1.0,
                    "gross_points": 1.0,
                    "direction": 1,
                    "priority_score": 100.0,
                    "strategy_source": "rollstable_timecell_oos",
                    "feature_family": module.ROLLSTABLE_TIMECELL_FAMILY,
                    "same_bar_exit": False,
                }
                for index in range(4)
            ]
        )
        rows.append(
            {
                "strategy_label": "weak_overlay",
                "entry_ts": pd.Timestamp(f"{year}-02-01 10:00:00", tz="UTC"),
                "exit_ts": pd.Timestamp(f"{year}-02-01 10:01:00", tz="UTC"),
                "net_points": 2.0,
                "gross_points": 2.0,
                "direction": 1,
                "priority_score": 90.0,
                "strategy_source": module.BAR_BEST_SOURCE,
                "feature_family": "bar_best_momentum",
                "same_bar_exit": False,
            }
        )
        rows.append(
            {
                "strategy_label": "strong_overlay",
                "entry_ts": pd.Timestamp(f"{year}-03-01 10:00:00", tz="UTC"),
                "exit_ts": pd.Timestamp(f"{year}-03-01 10:01:00", tz="UTC"),
                "net_points": 200.0,
                "gross_points": 200.0,
                "direction": 1,
                "priority_score": 80.0,
                "strategy_source": module.BAR_BEST_SOURCE,
                "feature_family": "bar_best_mean_reversion",
                "same_bar_exit": False,
            }
        )
    trades = pd.DataFrame(rows)
    args = Namespace(
        rank_on_common_window=False,
        full_years=(2020, 2021),
        min_full_year_trades=4,
        coverage_objective=True,
        include_coverage_candidates=True,
        max_combo_size=2,
        max_per_family=1,
        coverage_max_per_family=2,
        max_coverage_candidates=0,
        min_profit_factor=0.0,
        min_net_points=0.0,
        min_net_to_drawdown=0.0,
        min_positive_full_year_net_rate=0.0,
        quality_gate_uses_risk_budget=True,
        rollstable_timecell_max_risk_budget=0.10,
        max_research_overlay_candidates=2,
    )

    limited = module.fast_coverage_combos(trades, candidates, audit, args)
    args.max_research_overlay_candidates = 0
    unlimited = module.fast_coverage_combos(trades, candidates, audit, args)

    assert ("rollstable", "strong_overlay") not in limited
    assert ("rollstable", "strong_overlay") in unlimited


def test_fast_coverage_seed_candidate_limit_is_configurable() -> None:
    candidates = pd.DataFrame(
        [
            {
                "strategy_label": "wide_low_quality",
                "eligible_for_composite": True,
                "has_trade_coverage": True,
                "deployment_tier": module.RESEARCH_TIER,
                "feature_family": "wide_low_quality",
                "trade_rows": 10,
                "priority_score": 10.0,
                "coverage_candidate": False,
            },
            {
                "strategy_label": "narrow_high_quality",
                "eligible_for_composite": True,
                "has_trade_coverage": True,
                "deployment_tier": module.RESEARCH_TIER,
                "feature_family": "narrow_high_quality",
                "trade_rows": 8,
                "priority_score": 200.0,
                "coverage_candidate": False,
            },
        ]
    )
    audit = candidates.copy()
    audit["strategy_source"] = [module.BAR_BEST_SOURCE, module.BAR_BEST_SOURCE]
    rows: list[dict[str, object]] = []
    for year in (2020, 2021):
        rows.extend(
            [
                {
                    "strategy_label": "wide_low_quality",
                    "entry_ts": pd.Timestamp(f"{year}-01-01 10:{index:02d}:00", tz="UTC"),
                    "exit_ts": pd.Timestamp(f"{year}-01-01 10:{index + 1:02d}:00", tz="UTC"),
                    "net_points": 1.0,
                    "gross_points": 1.0,
                    "direction": 1,
                    "priority_score": 10.0,
                    "strategy_source": module.BAR_BEST_SOURCE,
                    "feature_family": "wide_low_quality",
                    "same_bar_exit": False,
                }
                for index in range(5)
            ]
        )
        rows.extend(
            [
                {
                    "strategy_label": "narrow_high_quality",
                    "entry_ts": pd.Timestamp(f"{year}-02-01 10:{index:02d}:00", tz="UTC"),
                    "exit_ts": pd.Timestamp(f"{year}-02-01 10:{index + 1:02d}:00", tz="UTC"),
                    "net_points": 50.0,
                    "gross_points": 50.0,
                    "direction": 1,
                    "priority_score": 200.0,
                    "strategy_source": module.BAR_BEST_SOURCE,
                    "feature_family": "narrow_high_quality",
                    "same_bar_exit": False,
                }
                for index in range(4)
            ]
        )
    trades = pd.DataFrame(rows)
    args = Namespace(
        rank_on_common_window=False,
        full_years=(2020, 2021),
        min_full_year_trades=4,
        coverage_objective=True,
        include_coverage_candidates=True,
        max_combo_size=1,
        max_per_family=1,
        coverage_max_per_family=1,
        max_coverage_candidates=0,
        min_profit_factor=0.0,
        min_net_points=0.0,
        min_net_to_drawdown=0.0,
        min_positive_full_year_net_rate=0.0,
        quality_gate_uses_risk_budget=True,
        rollstable_timecell_max_risk_budget=0.10,
        max_fast_seed_candidates=1,
        max_research_overlay_candidates=24,
    )

    limited = module.fast_coverage_combos(trades, candidates, audit, args)
    args.max_fast_seed_candidates = 0
    unlimited = module.fast_coverage_combos(trades, candidates, audit, args)

    assert limited == [("wide_low_quality",)]
    assert unlimited == [("narrow_high_quality",)]


def test_svg_line_downsamples_large_equity_curve() -> None:
    points = pd.DataFrame({"x": range(5000), "equity": range(5000)})

    svg = module.svg_line(points)

    polyline = svg.split('<polyline points="', 1)[1].split('"', 1)[0]
    assert len(polyline.split()) == 1000
