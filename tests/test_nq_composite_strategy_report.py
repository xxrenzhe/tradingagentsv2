from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "generate_nq_composite_strategy_report.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("generate_nq_composite_strategy_report", SCRIPT_PATH)
report_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["generate_nq_composite_strategy_report"] = report_script
SPEC.loader.exec_module(report_script)


def test_composite_report_selects_strict_recent_candidates_and_writes_charts(tmp_path: Path) -> None:
    strategy_a = "bar_best_mean_reversion_lb10_thr1_hold30_long_us_late"
    strategy_b = "bar_best_momentum_lb60_thr0.0006_hold60_long_us_late"
    strategy_c = "bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late"
    trades = tmp_path / "trades.csv"
    shortlist = tmp_path / "shortlist.csv"
    recent_oos = tmp_path / "recent_oos.csv"
    output = tmp_path / "report.html"
    selected = tmp_path / "selected.csv"
    metrics = tmp_path / "metrics.csv"

    rows = []
    timestamps = pd.date_range("2026-01-01 20:00", periods=18, freq="D", tz="UTC")
    for index, ts in enumerate(timestamps):
        candidate = [strategy_a, strategy_b, strategy_c][index % 3]
        rows.append(
            {
                "entry_ts": ts,
                "exit_ts": ts + pd.Timedelta(minutes=30),
                "direction": 1,
                "net_points": 20.0 if candidate != strategy_c else 50.0,
                "candidate": candidate,
            }
        )
    pd.DataFrame(rows).to_csv(trades, index=False)
    pd.DataFrame(
        [
            {
                "tier": "promote_to_strict_gate",
                "candidate": strategy_a,
                "filter": "none",
                "net_points": 120.0,
                "profit_factor": 1.5,
                "positive_fold_rate": 1.0,
                "stress_points": 25.0,
            },
            {
                "tier": "promote_to_strict_gate",
                "candidate": strategy_b,
                "filter": "none",
                "net_points": 120.0,
                "profit_factor": 1.7,
                "positive_fold_rate": 1.0,
                "stress_points": 30.0,
            },
            {
                "tier": "paper_watchlist",
                "candidate": strategy_c,
                "filter": "none",
                "net_points": 300.0,
                "profit_factor": 1.3,
                "positive_fold_rate": 0.8,
                "stress_points": -40.0,
            },
        ]
    ).to_csv(shortlist, index=False)
    pd.DataFrame(
        [
            {
                "candidate": strategy_a,
                "filter": "none",
                "recent_verdict": "passes_recent_oos",
                "positive_month_rate": 1.0,
            },
            {
                "candidate": strategy_b,
                "filter": "none",
                "recent_verdict": "passes_recent_oos",
                "positive_month_rate": 1.0,
            },
            {
                "candidate": strategy_c,
                "filter": "none",
                "recent_verdict": "passes_recent_oos",
                "positive_month_rate": 1.0,
            },
        ]
    ).to_csv(recent_oos, index=False)

    args = Namespace(
        trades=str(trades),
        shortlist=str(shortlist),
        recent_oos=str(recent_oos),
        output=str(output),
        selected_trades_output=str(selected),
        metrics_output=str(metrics),
        max_combo_size=3,
        generated_at="2026-05-06 00:00 UTC",
    )

    result = report_script.write_report(args)

    html = output.read_text(encoding="utf-8")
    assert result["candidates"] == [strategy_a, strategy_b]
    assert "NQ 最强稳健组合策略报告" in html
    assert "累计净点数 vs 交易次数" in html
    assert "累计净点数 vs 交易日期" in html
    assert "needs" not in html
    assert "尚不支持这些" in html
    assert selected.exists()
    assert metrics.exists()
