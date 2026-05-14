from __future__ import annotations

import importlib.util
import pickle
import sys
from argparse import Namespace
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "optimize_nq_lightglow_paper_executable.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("optimize_nq_lightglow_paper_executable", SCRIPT_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["optimize_nq_lightglow_paper_executable"] = module
SPEC.loader.exec_module(module)

from tradingagents.execution.paper_validation import load_trade_samples


def _bars(path: Path) -> None:
    ts = pd.date_range("2022-01-01", periods=2200, freq="min", tz="UTC")
    offset = pd.Series(range(len(ts)), dtype=float)
    frame = pd.DataFrame(
        {
            "ts": ts,
            "symbol": "NQ",
            "Open": 10000.0 + offset,
            "High": 10001.0 + offset,
            "Low": 9999.0 + offset,
            "Close": 10000.5 + offset,
            "Volume": 100,
        }
    )
    with path.open("wb") as file:
        pickle.dump({"bars": frame}, file)


def _trade(
    year: int,
    index: int,
    *,
    source: str = module.LIGHTGLOW_SOURCE,
    direction: int = 1,
    in_edge: bool = True,
) -> dict[str, object]:
    entry = pd.Timestamp(year=year, month=1, day=1, hour=15, minute=0, tz="UTC") + pd.Timedelta(minutes=index)
    net = 8.0 if in_edge else -6.0
    return {
        "entry_ts": entry,
        "exit_ts": entry + pd.Timedelta(minutes=10),
        "strategy_source": source,
        "strategy_label": "lightglow" if source == module.LIGHTGLOW_SOURCE else "timecell",
        "direction": direction,
        "entry_price": 10000.0,
        "exit_price": 10000.0 + net * direction,
        "gross_points": net + 0.625,
        "net_points": net,
        "risk_weight": 1.0 if source == module.LIGHTGLOW_SOURCE else 0.05,
        "z_30": -1.0 if in_edge else 1.0,
        "momentum_5": 0.001 if in_edge else -0.001,
        "momentum_15": 0.001 if in_edge else -0.001,
        "momentum_60": 0.001 if in_edge else -0.003,
        "vol_30": 0.003 if in_edge else 0.001,
        "vol_120": 0.001,
        "atr_ratio": 0.8 if in_edge else 1.5,
        "ema20_slope_10": 2.0 if in_edge else -2.0,
        "trend_ema20_60": 4.0 if in_edge else -4.0,
        "trend_ema60_200": 5.0 if in_edge else -5.0,
        "dist_ema20": 2.0 if in_edge else 20.0,
        "dist_ema60": 3.0 if in_edge else -15.0,
        "range_atr": 10.0,
        "box45_width_atr": 5.0,
        "box45_pos": 0.4 if in_edge else 1.4,
        "hour": 15,
        "minute": 900 + index,
    }


def _trades() -> pd.DataFrame:
    rows = []
    for year in (2022, 2023, 2024, 2025):
        for index in range(120):
            rows.append(_trade(year, index, in_edge=index < 80))
        for index in range(10):
            rows.append(_trade(year, 300 + index, source="rollstable_timecell_oos", in_edge=False))
    return pd.DataFrame(rows)


def test_load_lightglow_trades_excludes_timecell(tmp_path: Path) -> None:
    path = tmp_path / "trades.csv"
    _trades().to_csv(path, index=False)

    loaded = module.load_lightglow_trades(path)

    assert not loaded.empty
    assert set(loaded["strategy_source"]) == {module.LIGHTGLOW_SOURCE}
    assert "rollstable_timecell_oos" not in set(loaded["strategy_source"])


def test_walk_forward_selects_on_train_and_applies_to_future_years() -> None:
    trades = _trades()
    trades = trades[trades["strategy_source"].eq(module.LIGHTGLOW_SOURCE)].copy()
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    trades["year"] = trades["entry_ts"].dt.year

    filters, windows, optimized = module.walk_forward_optimize(trades)

    assert set(windows["test_year"]) == {2023, 2024, 2025}
    assert optimized["entry_ts"].dt.year.min() == 2023
    assert not filters[filters["selected_by_train"]].empty
    assert (windows["optimized_net_points"] >= windows["base_net_points"]).all()


def test_prepare_paper_runner_trades_adds_required_schema(tmp_path: Path) -> None:
    trades = _trades()
    trades = trades[trades["strategy_source"].eq(module.LIGHTGLOW_SOURCE)].copy()
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    prepared = module.prepare_paper_runner_trades(trades.head(3))
    output = tmp_path / "paper.csv"
    prepared.to_csv(output, index=False)

    loaded = load_trade_samples(output)

    assert {"portfolio_rule", "selected_alias", "trade_date", "actual_entry_ts", "holding_minutes"}.issubset(loaded.columns)
    assert set(loaded["portfolio_rule"]) == {module.PAPER_STRATEGY_ID}
    assert set(loaded["selected_alias"]) == {module.PAPER_SELECTED_ALIAS}


def test_report_generation_outputs_optimization_artifacts(tmp_path: Path) -> None:
    trades_path = tmp_path / "trades.csv"
    bars_path = tmp_path / "bars.pkl"
    report = tmp_path / "report.html"
    markdown = tmp_path / "report.md"
    filters = tmp_path / "filters.csv"
    windows = tmp_path / "windows.csv"
    stress = tmp_path / "stress.csv"
    optimized_trades = tmp_path / "optimized.csv"
    summary = tmp_path / "summary.json"
    paper_config = tmp_path / "paper_config.json"
    _trades().to_csv(trades_path, index=False)
    _bars(bars_path)

    result = module.run(
        Namespace(
            trades=str(trades_path),
            bars=str(bars_path),
            report=str(report),
            markdown=str(markdown),
            filters_output=str(filters),
            window_output=str(windows),
            stress_output=str(stress),
            trades_output=str(optimized_trades),
            summary_output=str(summary),
            paper_config_output=str(paper_config),
            generated_at="2026-05-14 00:00 UTC",
        )
    )

    html = report.read_text(encoding="utf-8")
    assert "NQ Lightglow Paper-Executable Optimization" in html
    assert "Timecell 保持 shadow-only" in html
    assert "Walk-Forward 过滤选择" in html
    assert result["optimized"]["trades"] > 0
    assert "baseline_oos" in result
    assert result["paper_config"] == str(paper_config)
    assert "--trades " + str(optimized_trades) in paper_config.read_text(encoding="utf-8")
    assert "--allow-timed-exit-submit" in paper_config.read_text(encoding="utf-8")
    assert "default --submit remains blocked" in paper_config.read_text(encoding="utf-8")
    for path in (markdown, filters, windows, stress, optimized_trades, summary, paper_config):
        assert path.exists()
