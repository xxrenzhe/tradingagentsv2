from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "discover_nq_tradeable_market_features.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("discover_nq_tradeable_market_features", SCRIPT_PATH)
script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["discover_nq_tradeable_market_features"] = script
SPEC.loader.exec_module(script)


def test_event_path_summary_scores_directional_opportunity() -> None:
    frame = pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=80, freq="min", tz="UTC"),
            "symbol": ["NQH6"] * 80,
            "Open": [100.0 + index for index in range(80)],
            "High": [101.0 + index for index in range(80)],
            "Low": [99.0 + index for index in range(80)],
            "Close": [100.0 + index for index in range(80)],
        }
    )
    feature = script.MarketFeature(
        feature_id="synthetic_trend_start",
        family="trend_start",
        direction_hint="long",
        description="Synthetic long trend event.",
        signal=pd.Series([index in {5, 25, 45} for index in range(80)]),
    )

    events = script.event_path_rows(frame, [feature], horizons=[5, 15], min_gap_minutes=1)
    summary = script.summarize_events(events, horizons=[5, 15], min_events=1)

    assert len(events) == 3
    assert not summary.empty
    top = summary.iloc[0]
    assert top["feature_id"] == "synthetic_trend_start"
    assert top["events"] == 3
    assert top["favorable_close_rate_15m"] == 1.0
    assert top["median_mfe_15m"] > top["median_mae_15m"]


def test_fallback_feature_analysis_returns_strategy_principles() -> None:
    summary = pd.DataFrame(
        [
            {
                "feature_id": "volume_price_bullish_mismatch",
                "family": "volume_price_mismatch",
                "direction_hint": "long",
                "description": "Price weak while volume confirms accumulation.",
                "events": 120,
                "opportunity_score": 4.2,
            }
        ]
    )
    args = argparse.Namespace(llm_top_n=5)

    payload = script.fallback_feature_analysis(summary, args, memory_notes=[])

    assert payload["status"] == "fallback"
    assert payload["feature_rankings"][0]["feature_id"] == "volume_price_bullish_mismatch"
    assert "confirmation" in payload["feature_rankings"][0]
    assert payload["strategy_hypotheses"][0]["setup"] == "volume_price_bullish_mismatch"
    assert payload["risk_principles"]


def test_sequence_features_capture_breakdown_v_reversal_and_pullback_continuation() -> None:
    frame = _three_wave_reversal_frame()

    features = {feature.feature_id: feature for feature in script.build_market_features(frame)}

    assert features["smc_breakdown_downtrend_wave"].signal.any()
    assert features["capitulation_v_reversal_long"].signal.any()
    assert features["selloff_reversal_pullback_continuation_long"].signal.any()


def _three_wave_reversal_frame() -> pd.DataFrame:
    periods = 180
    ts = pd.date_range("2026-01-01 13:30", periods=periods, freq="min", tz="UTC")
    close = np.full(periods, 100.0)
    close[60:80] = np.linspace(100.2, 100.0, 20)
    close[80:106] = np.linspace(96.8, 88.0, 26)
    close[106:136] = np.linspace(88.5, 96.5, 30)
    close[136:151] = np.linspace(96.0, 94.5, 15)
    close[151:] = np.linspace(95.0, 101.0, periods - 151)
    close[108] = 89.2
    close[152] = 96.8

    open_price = np.r_[close[0], close[:-1]]
    high = np.maximum(open_price, close) + 0.35
    low = np.minimum(open_price, close) - 0.35
    low[108] = 86.0
    open_price[108] = 88.0
    high[108] = 89.6
    low[152] = 94.8
    high[144:152] = np.minimum(high[144:152], 95.8)
    high[152] = 97.1

    range_points = high - low
    lower_wick = np.minimum(open_price, close) - low
    upper_wick = high - np.maximum(open_price, close)

    frame = pd.DataFrame(
        {
            "ts": ts,
            "symbol": ["NQH6"] * periods,
            "Open": open_price,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": np.full(periods, 1000.0),
            "atr_30": np.full(periods, 2.0),
            "minute_of_day": np.full(periods, 14 * 60),
            "body_share": np.abs(close - open_price) / range_points,
            "volume_z_60": np.full(periods, 0.8),
            "lower_wick_points": lower_wick,
            "upper_wick_points": upper_wick,
            "donchian_20_position": np.linspace(0.7, 0.3, periods),
            "adx_14": np.full(periods, 25.0),
            "di_spread_14": np.r_[np.full(116, -8.0), np.full(periods - 116, 8.0)],
            "cmf_20": np.r_[np.full(105, -0.1), np.full(periods - 105, 0.15)],
            "obv_slope_20": np.r_[np.full(105, -1.0), np.full(periods - 105, 1.0)],
            "mfi_14": np.r_[np.full(105, 40.0), np.full(periods - 105, 55.0)],
            "vfi_130": np.linspace(-1.0, 1.0, periods),
            "macd_hist": np.r_[np.full(105, -0.5), np.linspace(-0.4, 0.8, periods - 105)],
            "boll_position": np.linspace(-1.0, 0.5, periods),
            "range_100_position": np.linspace(0.2, 0.8, periods),
            "session_vwap_distance_atr": np.r_[np.full(116, -0.6), np.full(periods - 116, 0.2)],
            "displacement_candle": np.zeros(periods, dtype=int),
            "bullish_volume_divergence": np.zeros(periods, dtype=int),
            "bearish_volume_divergence": np.zeros(periods, dtype=int),
            "low_volume_pullback": np.zeros(periods, dtype=int),
            "ema_10": close + 0.2,
            "ema_20": close,
            "ema_50": close - 0.2,
            "session_vwap_reclaim_up": np.zeros(periods, dtype=int),
            "session_vwap_reclaim_down": np.zeros(periods, dtype=int),
        }
    )
    frame.loc[80:105, "displacement_candle"] = 1
    return frame
