from __future__ import annotations

import pandas as pd
import pytest

from tradingagents.backtesting.multi_timeframe_setup import (
    MultiTimeframeSetupSpec,
    build_multi_timeframe_trades,
    prepare_multi_timeframe_features,
    setup_signal_frame,
)


@pytest.mark.unit
def test_setup_signal_frame_detects_m15_m3_m1_long_trigger() -> None:
    frame = _manual_context_frame()
    signal = setup_signal_frame(frame, MultiTimeframeSetupSpec(imbalance_threshold=0.3))

    row = signal.iloc[70]
    assert row["setup_signal"] == 1
    assert row["setup_reason"] == "m15_up_m3_reclaim_m1_breakout"
    assert row["setup_htf_trend"] == "long"
    assert row["setup_mtf_reclaim"] == "long"
    assert row["setup_ltf_trigger"] == "long"


@pytest.mark.unit
def test_build_multi_timeframe_trades_uses_bracket_exit() -> None:
    frame = _manual_context_frame()
    spec = MultiTimeframeSetupSpec(imbalance_threshold=0.3, stop_loss_points=1.0, take_profit_points=2.0, max_hold_minutes=6)
    trades = build_multi_timeframe_trades(frame, spec)

    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["direction"] == 1
    assert trade["exit_reason"] == "take_profit"
    assert trade["portfolio_rule"] == spec.name
    assert trade["selected_alias"] == "mtf_setup"


@pytest.mark.unit
def test_prepare_multi_timeframe_features_accepts_live_style_ts_bars() -> None:
    timestamps = pd.date_range("2026-05-05T12:00:00Z", periods=90, freq="min")
    bars = pd.DataFrame(
        {
            "ts": timestamps,
            "Open": [100 + i * 0.1 for i in range(90)],
            "High": [100.2 + i * 0.1 for i in range(90)],
            "Low": [99.8 + i * 0.1 for i in range(90)],
            "Close": [100 + i * 0.1 for i in range(90)],
            "imbalance_last": [0.4] * 90,
            "spread_mean": [0.5] * 90,
            "depth_mean": [10] * 90,
        }
    )
    features = prepare_multi_timeframe_features(bars)

    assert {"Close_3m", "Close_15m", "ema_fast_3m", "ema_fast_15m"}.issubset(features.columns)
    assert len(features) == 90


def _manual_context_frame() -> pd.DataFrame:
    timestamps = pd.date_range("2026-05-05T12:00:00Z", periods=90, freq="min")
    close = [100.0] * 90
    for index in range(71, 77):
        close[index] = 101.0 + (index - 71) * 0.5
    frame = pd.DataFrame(
        {
            "ts": timestamps,
            "Open": close,
            "High": [value + 0.4 for value in close],
            "Low": [value - 0.4 for value in close],
            "Close": close,
            "Volume": [100] * 90,
            "vwap": [99.0] * 90,
            "minute_of_day": [timestamp.hour * 60 + timestamp.minute for timestamp in timestamps],
            "ema_fast_1m": [99.8] * 90,
            "prev_high_1m": [99.9] * 90,
            "prev_low_1m": [99.5] * 90,
            "imbalance_last": [0.1] * 90,
            "spread_mean": [0.5] * 90,
            "depth_mean": [10.0] * 90,
            "Close_3m": [100.0] * 90,
            "ema_fast_3m": [100.0] * 90,
            "ema_slow_3m": [99.5] * 90,
            "prev_close_3m": [100.0] * 90,
            "prev_ema_fast_3m": [99.5] * 90,
            "Close_15m": [101.0] * 90,
            "ema_fast_15m": [100.0] * 90,
            "ema_slow_15m": [99.0] * 90,
            "ema_fast_slope_15m": [0.1] * 90,
        }
    )
    frame.loc[70, "Close"] = 101.0
    frame.loc[70, "Open"] = 100.8
    frame.loc[70, "High"] = 101.2
    frame.loc[70, "Low"] = 100.6
    frame.loc[70, "Close_3m"] = 100.8
    frame.loc[70, "ema_fast_3m"] = 100.2
    frame.loc[70, "prev_close_3m"] = 99.8
    frame.loc[70, "prev_ema_fast_3m"] = 100.0
    frame.loc[70, "imbalance_last"] = 0.45
    frame.loc[71, "Open"] = 101.0
    frame.loc[71, "High"] = 103.2
    frame.loc[71, "Low"] = 100.8
    frame.loc[71, "Close"] = 102.9
    return frame
