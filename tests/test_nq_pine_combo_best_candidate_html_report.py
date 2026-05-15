from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_nq_pine_combo_best_candidate_html_report.py"
SPEC = importlib.util.spec_from_file_location("generate_nq_pine_combo_best_candidate_html_report", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_best_candidate_html_report_contains_core_sections(tmp_path: Path) -> None:
    ranking = pd.DataFrame(
        [
            {
                "strategy": "phase_trend_macd60_hist_deceleration_stop0.8_r1.8_h60_norisk",
                "families": "phase_up_breakout_long+phase_down_breakdown_short",
                "macd_filter": "hist_deceleration",
                "stop_atr_buffer": 0.8,
                "target_r": 1.8,
                "max_hold_bars": 60,
            },
            {
                "strategy": MODULE.BEST_STRATEGY,
                "families": "top_breakout_long+trend_transition_long",
                "macd_filter": "cross_recent_5",
                "stop_atr_buffer": 1.25,
                "target_r": 2.5,
                "max_hold_bars": 30,
            }
        ]
    )
    trades = pd.DataFrame(
        [
            {
                "entry_ts": "2026-03-27 01:29:00+00:00",
                "exit_ts": "2026-03-27 01:59:00+00:00",
                "signal_family": "trend_transition_long",
                "session": "asia",
                "direction": 1,
                "entry_price": 23864.0,
                "exit_price": 23872.0,
                "exit_reason": "max_hold",
                "bars_held": 30,
                "net_points": 6.5,
            }
        ]
    )
    bars = pd.DataFrame(
        [
            {
                "ts": "2026-03-27 01:29:00+00:00",
                "Open": 23860.0,
                "High": 23874.0,
                "Low": 23858.0,
                "Close": 23868.0,
            },
            {
                "ts": "2026-03-27 01:59:00+00:00",
                "Open": 23870.0,
                "High": 23875.0,
                "Low": 23866.0,
                "Close": 23872.0,
            },
        ]
    )
    output = tmp_path / "report.html"

    MODULE._write_report(output, ranking, trades, bars)

    html = output.read_text(encoding="utf-8")
    assert "phase_trend_macd60_hist_deceleration_stop0.8_r1.8_h60_norisk" in html
    assert "Performance Snapshot" in html
    assert "Equity Curve By Trade" in html
    assert "K-line Trade Replay" in html
    assert "trade_id" in html
    assert "TRD-" in html
    assert "trade-card" in html
    assert "trade-card-grid" in html
    assert "trade-entry" in html
    assert "trade-exit" in html
    assert "LONG IN" in html
    assert "OUT +6.50 pts" in html
    assert "NQ 1m K-line with all" not in html
    assert "Breakdown By Signal Family" in html
    assert "Trade Log" in html


def test_best_candidate_html_report_can_pin_legacy_strategy(tmp_path: Path) -> None:
    ranking = pd.DataFrame(
        [
            {
                "strategy": "phase_trend_macd60_hist_deceleration_stop0.8_r1.8_h60_norisk",
                "families": "phase_up_breakout_long+phase_down_breakdown_short",
                "macd_filter": "hist_deceleration",
                "stop_atr_buffer": 0.8,
                "target_r": 1.8,
                "max_hold_bars": 60,
            },
            {
                "strategy": MODULE.BEST_STRATEGY,
                "families": "top_breakout_long+trend_transition_long",
                "macd_filter": "cross_recent_5",
                "stop_atr_buffer": 1.25,
                "target_r": 2.5,
                "max_hold_bars": 30,
            },
        ]
    )
    trades = pd.DataFrame(
        [
            {
                "entry_ts": "2026-03-27 01:29:00+00:00",
                "exit_ts": "2026-03-27 01:59:00+00:00",
                "signal_family": "trend_transition_long",
                "session": "asia",
                "direction": 1,
                "entry_price": 23864.0,
                "exit_price": 23872.0,
                "exit_reason": "max_hold",
                "bars_held": 30,
                "net_points": 6.5,
            }
        ]
    )
    output = tmp_path / "report.html"

    MODULE._write_report(output, ranking, trades, pd.DataFrame(), MODULE.BEST_STRATEGY)

    html = output.read_text(encoding="utf-8")
    assert MODULE.BEST_STRATEGY in html
