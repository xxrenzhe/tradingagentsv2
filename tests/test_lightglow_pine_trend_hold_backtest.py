from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

from tradingagents.backtesting.short_patterns import BacktestCosts


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "backtest_lightglow_pine_trend_hold_validation.py"
SPEC = importlib.util.spec_from_file_location("backtest_lightglow_pine_trend_hold_validation", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_trend_hold_backtest_can_hold_correct_direction_longer_than_fixed_exit():
    rows = []
    for index in range(20):
        price = 100.0 + index
        rows.append(
            {
                "ts": pd.Timestamp("2020-01-01", tz="UTC") + pd.Timedelta(minutes=index),
                "symbol": "NQH0",
                "Open": price,
                "High": price + 0.75,
                "Low": price - 0.25,
                "Close": price + 0.5,
                "Volume": 10,
                "atr": 2.0,
                "ema_fast": price,
                "ema_mid": price - 1.0,
                "dist_ema60": 1.0,
                "trend_20_60": 1.0,
            }
        )
    frame = pd.DataFrame(rows)
    signals = pd.Series([0, 1] + [0] * 18)
    config = MODULE.LightglowPineConfig(
        cooldown_bars=0,
        fixed_hold_bars=2,
        trend_max_hold_bars=10,
        initial_stop_atr=3.0,
        trail_stop_atr=10.0,
        breakeven_trigger_atr=1.0,
        exit_on_ema_break=True,
    )
    costs = BacktestCosts()

    fixed = MODULE.backtest_fixed_bars(frame, signals, config, costs)
    trend = MODULE.backtest_trend_hold(frame, signals, config, costs)

    assert len(fixed) == 1
    assert len(trend) == 1
    assert int(fixed["bars_held"].iloc[0]) == 2
    assert int(trend["bars_held"].iloc[0]) == 10
    assert trend["net_points"].iloc[0] > fixed["net_points"].iloc[0]
    assert trend["exit_reason"].iloc[0] == "max_hold"
