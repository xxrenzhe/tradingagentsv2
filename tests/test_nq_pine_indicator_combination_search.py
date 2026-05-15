from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "search_nq_pine_indicator_combinations.py"
SPEC = importlib.util.spec_from_file_location("search_nq_pine_indicator_combinations", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_macd_hist_repair_enters_before_line_cross() -> None:
    frame = pd.DataFrame(
        {
            "mtf60_macd_hist": [-3.0, -2.0, -1.0],
            "mtf60_hist_delta": [pd.NA, 1.0, 1.0],
            "mtf60_macd_above_signal": [False, False, False],
            "mtf60_macd_below_signal": [True, True, True],
        }
    )

    mask = MODULE._macd_filter_mask(frame, 1, timeframe=60, filter_name="hist_repair")

    assert mask.tolist() == [False, True, True]
    assert not frame["mtf60_macd_above_signal"].any()


def test_score_penalizes_tiny_samples_below_robust_candidate() -> None:
    tiny = {
        "trades": 5,
        "net_points": 135.0,
        "profit_factor": 6.5,
        "win_rate": 0.8,
        "avg_points": 27.0,
        "max_drawdown_points": 24.0,
        "worst_trade_points": -24.0,
    }
    robust = {
        "trades": 218,
        "net_points": 1732.0,
        "profit_factor": 2.05,
        "win_rate": 0.55,
        "avg_points": 7.94,
        "max_drawdown_points": 133.5,
        "worst_trade_points": -109.0,
    }

    assert MODULE.score_summary(robust) > MODULE.score_summary(tiny)


def test_build_combo_specs_includes_screenshot_fast_reversal_and_hist_repair() -> None:
    args = type(
        "Args",
        (),
        {
            "macd_timeframes": [60],
            "macd_filters": ["hist_repair"],
            "stop_atr_buffers": [0.8],
            "target_rs": [1.2],
            "max_hold_bars_grid": [30],
            "risk_control_modes": [False],
        },
    )()

    specs = MODULE.build_combo_specs(args)
    names = {spec.name for spec in specs}

    assert any("screenshot_reversal_macd60_hist_repair" in name for name in names)
    assert any("fast_boundary_reversal_macd60_hist_repair" in name for name in names)
