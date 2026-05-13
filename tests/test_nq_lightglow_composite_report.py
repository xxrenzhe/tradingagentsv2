from __future__ import annotations

import importlib.util
import pickle
import sys
from argparse import Namespace
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "generate_nq_lightglow_composite_report.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("generate_nq_lightglow_composite_report", SCRIPT_PATH)
report_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["generate_nq_lightglow_composite_report"] = report_script
SPEC.loader.exec_module(report_script)


def _write_bars(path: Path) -> None:
    ts = pd.date_range("2022-01-03 14:00", periods=220, freq="min", tz="UTC")
    rows = []
    for index, stamp in enumerate(ts):
        base = 15000.0 + index * 0.5
        close = base + (1.0 if index % 3 else -0.75)
        rows.append(
            {
                "ts": stamp,
                "symbol": "NQH2",
                "Open": base,
                "High": max(base, close) + 1.25,
                "Low": min(base, close) - 1.0,
                "Close": close,
                "Volume": 100 + index,
            }
        )
    with path.open("wb") as file:
        pickle.dump({"bars": pd.DataFrame(rows)}, file)


def _trade_rows() -> list[dict[str, object]]:
    return [
        {
            "entry_ts": "2022-01-03 14:20:00+00:00",
            "exit_ts": "2022-01-03 14:22:00+00:00",
            "strategy_source": "lightglow_research",
            "strategy_label": "Stable 2020-2021 trained action map",
            "feature_family": "lightglow_premium_discount_reversal",
            "direction": 1,
            "entry_price": 15010.0,
            "exit_price": 15022.0,
            "gross_points": 12.0,
            "net_points": 11.375,
            "risk_weight": 1.0,
            "volume_z_60": 1.2,
            "z_30": -1.5,
            "box45_pos": 0.15,
        },
        {
            "entry_ts": "2022-01-03 15:20:00+00:00",
            "exit_ts": "2022-01-03 15:22:00+00:00",
            "strategy_source": "lightglow_research",
            "strategy_label": "Stable 2020-2021 trained action map",
            "feature_family": "lightglow_premium_discount_reversal",
            "direction": -1,
            "entry_price": 15060.0,
            "exit_price": 15051.0,
            "gross_points": 9.0,
            "net_points": 8.375,
            "risk_weight": 1.0,
            "volume_z_60": 2.1,
            "z_30": 2.5,
            "box45_pos": 0.88,
        },
        {
            "entry_ts": "2022-01-03 16:00:00+00:00",
            "exit_ts": "2022-01-03 17:30:00+00:00",
            "strategy_source": "rollstable_timecell_oos",
            "strategy_label": "rollstable_trainpf105_timecell",
            "feature_family": "rollstable_timecell_direction_map",
            "direction": 1,
            "entry_price": 15080.0,
            "exit_price": 15065.0,
            "gross_points": -15.0,
            "net_points": -15.625,
            "risk_weight": 0.05,
            "volume_z_60": 0.0,
            "z_30": 0.0,
            "box45_pos": 0.5,
        },
    ]


def test_lightglow_composite_report_writes_metrics_and_trade_charts(tmp_path: Path) -> None:
    composite = tmp_path / "composite.csv"
    oos = tmp_path / "oos.csv"
    ranking = tmp_path / "ranking.csv"
    components = tmp_path / "components.csv"
    bars = tmp_path / "bars.pkl"
    output = tmp_path / "report.html"
    summary = tmp_path / "summary.json"

    pd.DataFrame(_trade_rows()).to_csv(composite, index=False)
    pd.DataFrame(_trade_rows()[:2]).to_csv(oos, index=False)
    pd.DataFrame(
        [
            {
                "combo": "rollstable_trainpf105_timecell + Stable 2020-2021 trained action map",
                "trades": 3,
                "net_points": 4.125,
                "profit_factor": 1.2,
                "risk_budgeted_net_points": 18.96875,
                "risk_budgeted_profit_factor": 25.28,
                "min_full_year_trades": 3,
                "annual_trade_floor_pass": False,
            }
        ]
    ).to_csv(ranking, index=False)
    pd.DataFrame(
        [
            {
                "strategy_source": "lightglow_research",
                "strategy_label": "Stable 2020-2021 trained action map",
                "family": "lightglow_premium_discount_reversal",
                "trades": 2,
                "net_points": 19.75,
                "profit_factor": 999.0,
                "net_to_drawdown": 999.0,
                "deployment_tier": "research_extension",
            }
        ]
    ).to_csv(components, index=False)
    _write_bars(bars)

    result = report_script.write_report(
        Namespace(
            composite_trades=str(composite),
            oos_trades=str(oos),
            ranking=str(ranking),
            components=str(components),
            bars=str(bars),
            output=str(output),
            summary_output=str(summary),
            generated_at="2026-05-14 00:00 UTC",
        )
    )

    html = output.read_text(encoding="utf-8")
    assert "NQ Lightglow + Timecell 组合策略报告" in html
    assert "交易原理" in html
    assert "最佳/最差交易 K 线图" in html
    assert "ENTRY" in html
    assert "EXIT" in html
    assert "Lightglow OOS 成本压力" in html
    assert result["raw_summary"]["trades"] == 3.0
    assert result["risk_budgeted_summary"]["net_points"] > result["raw_summary"]["net_points"]
    assert summary.exists()
