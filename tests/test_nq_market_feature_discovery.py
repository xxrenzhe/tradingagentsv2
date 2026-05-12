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


def test_explicit_feature_id_filter_selects_requested_market_features() -> None:
    frame = _three_wave_reversal_frame()
    features = {feature.feature_id: feature for feature in script.build_market_features(frame)}
    requested = ["w_bottom_reclaim_us_rth", "trend_start_long_displacement"]
    selected = [features[feature_id] for feature_id in requested]

    assert [feature.feature_id for feature in selected] == requested


def test_sequence_features_capture_breakdown_v_reversal_and_pullback_continuation() -> None:
    frame = _three_wave_reversal_frame()

    features = {feature.feature_id: feature for feature in script.build_market_features(frame)}

    assert features["smc_breakdown_downtrend_wave"].signal.any()
    assert features["capitulation_v_reversal_long"].signal.any()
    assert features["selloff_reversal_pullback_continuation_long"].signal.any()


def test_tradingview_indicator_feature_ids_are_registered_and_triggerable() -> None:
    frame = _three_wave_reversal_frame()
    frame["ichimoku_bullish_breakout"] = 0
    frame["ichimoku_bearish_breakdown"] = 0
    frame["aroon_bullish_cross"] = 0
    frame["aroon_bearish_cross"] = 0
    frame["trix_cross_up"] = 0
    frame["trix_cross_down"] = 0
    frame["kst_cross_up"] = 0
    frame["kst_cross_down"] = 0
    frame["williams_recover_up"] = 0
    frame["williams_fade_down"] = 0
    frame["psar_flip_up"] = 0
    frame["psar_flip_down"] = 0
    frame["vortex_bullish_cross"] = 0
    frame["vortex_bearish_cross"] = 0
    frame["chaikin_bullish_cross"] = 0
    frame["chaikin_bearish_cross"] = 0
    frame["cmo_recover_up"] = 0
    frame["cmo_fade_down"] = 0
    frame["ichimoku_cloud_position"] = 0.5
    frame["ichimoku_cloud_thickness_atr"] = 1.0
    frame["aroon_up_25"] = 80.0
    frame["aroon_down_25"] = 20.0
    frame["aroon_osc_25"] = 60.0
    frame["trix_15"] = 0.1
    frame["trix_signal_9"] = 0.0
    frame["tsi_25_13"] = 10.0
    frame["ultimate_osc_7_14_28"] = 45.0
    frame["williams_r_14"] = -50.0
    frame["kst"] = 1.0
    frame["kst_signal"] = 0.0
    frame["roc_10"] = 0.5
    frame["roc_20"] = 1.0
    frame["psar_direction"] = 1.0
    frame["psar_distance_atr"] = 0.3
    frame["vortex_spread_14"] = 0.4
    frame["vwma_spread_atr"] = 0.2
    frame["tema_21_slope_atr"] = 0.1
    frame["cmo_14"] = 15.0
    frame["dpo_20"] = 0.2
    frame["chaikin_osc_3_10"] = 1.0
    frame["chaikin_osc_z_50"] = 0.6
    frame["force_index_z_50"] = 0.8
    frame["eom_z_50"] = 0.4
    event_index = 160
    frame.loc[event_index, "ichimoku_bullish_breakout"] = 1
    frame.loc[event_index, "aroon_bullish_cross"] = 1
    frame.loc[event_index, "psar_flip_up"] = 1
    frame.loc[event_index, "chaikin_bullish_cross"] = 1
    frame.loc[event_index, "cmo_recover_up"] = 1
    frame.loc[event_index, "low_volume_pullback"] = 1
    frame.loc[event_index, "range_100_position"] = 0.25
    frame.loc[event_index - 3 : event_index - 1, "cmo_14"] = -10.0
    frame.loc[event_index - 3 : event_index - 1, "dpo_20"] = -0.2
    frame.loc[event_index - 3 : event_index - 1, "eom_z_50"] = -0.2

    features = {feature.feature_id: feature for feature in script.build_market_features(frame)}

    assert {
        "ichimoku_cloud_breakout_long",
        "ichimoku_cloud_breakdown_short",
        "aroon_trend_start_long",
        "aroon_trend_start_short",
        "trix_kst_momentum_reversal_long",
        "trix_kst_momentum_reversal_short",
        "williams_ultimate_oversold_reclaim_long",
        "williams_ultimate_overbought_fade_short",
        "cloud_pullback_trend_long",
        "cloud_pullback_trend_short",
        "psar_vortex_trend_start_long",
        "psar_vortex_trend_start_short",
        "chaikin_force_accumulation_reversal_long",
        "chaikin_force_distribution_reversal_short",
        "cmo_dpo_cycle_reversal_long",
        "cmo_dpo_cycle_reversal_short",
        "vwma_tema_pullback_continuation_long",
        "vwma_tema_pullback_continuation_short",
    } <= set(features)
    assert features["ichimoku_cloud_breakout_long"].signal.any()
    assert features["aroon_trend_start_long"].signal.any()
    assert features["psar_vortex_trend_start_long"].signal.any()
    assert features["chaikin_force_accumulation_reversal_long"].signal.any()
    assert features["cmo_dpo_cycle_reversal_long"].signal.any()
    assert features["vwma_tema_pullback_continuation_long"].signal.any()


def test_screenshot_trade_point_feature_gaps_are_covered() -> None:
    frame = _three_wave_reversal_frame()
    periods = len(frame)
    frame["range_100_width_atr"] = 2.0
    frame["sweep_signal"] = np.zeros(periods, dtype=int)
    frame["choch_signal"] = np.zeros(periods, dtype=int)
    frame["bos_signal"] = np.zeros(periods, dtype=int)
    frame["trix_15"] = 0.1
    frame["trix_signal_9"] = 0.0
    frame["force_index_z_50"] = 0.2
    frame["cmo_14"] = 10.0
    frame["supply_zone_retest"] = 0
    frame["demand_zone_retest"] = 0
    frame.loc[20:50, "Close"] = 100.0
    frame.loc[20:50, "Open"] = 99.8
    frame.loc[20:50, "High"] = 100.5
    frame.loc[20:50, "Low"] = 99.5

    breakdown_index = 54
    frame.loc[breakdown_index, ["Open", "High", "Low", "Close"]] = [99.0, 99.2, 94.0, 94.5]
    frame.loc[breakdown_index, "displacement_candle"] = 1
    frame.loc[breakdown_index, "bos_signal"] = -1
    frame.loc[breakdown_index, "session_vwap_distance_atr"] = -0.4
    frame.loc[breakdown_index, "macd_hist"] = -0.7
    frame.loc[breakdown_index, "trix_15"] = -0.2
    frame.loc[breakdown_index, "trix_signal_9"] = 0.0
    frame.loc[breakdown_index, "force_index_z_50"] = -0.7

    breakout_index = 120
    frame.loc[breakout_index - 8 : breakout_index - 1, "High"] = 96.0
    frame.loc[breakout_index, ["Open", "High", "Low", "Close"]] = [95.8, 100.2, 95.5, 99.6]
    frame.loc[breakout_index, "displacement_candle"] = 1
    frame.loc[breakout_index, "bos_signal"] = 1
    frame.loc[breakout_index, "session_vwap_distance_atr"] = 0.4
    frame.loc[breakout_index, "macd_hist"] = 0.6
    frame.loc[breakout_index - 3 : breakout_index - 1, "macd_hist"] = -0.2
    frame.loc[breakout_index, "force_index_z_50"] = 0.8

    sweep_high_index = 132
    frame.loc[sweep_high_index - 60 : sweep_high_index - 1, "High"] = 100.0
    frame.loc[breakout_index, ["Open", "High", "Low", "Close"]] = [100.2, 101.5, 99.8, 101.0]
    frame.loc[sweep_high_index, ["Open", "High", "Low", "Close"]] = [99.8, 103.5, 98.5, 99.2]
    frame.loc[sweep_high_index, "sweep_signal"] = -1
    frame.loc[sweep_high_index, "supply_zone_retest"] = 1
    frame.loc[sweep_high_index, "macd_hist"] = -0.3
    frame.loc[sweep_high_index - 3 : sweep_high_index - 1, "macd_hist"] = 0.2
    frame.loc[sweep_high_index, "cmf_20"] = -0.1

    sweep_low_index = 145
    frame.loc[sweep_low_index - 60 : sweep_low_index - 1, "Low"] = 94.0
    frame.loc[sweep_low_index, ["Open", "High", "Low", "Close"]] = [94.2, 96.4, 91.0, 96.0]
    frame.loc[sweep_low_index, "sweep_signal"] = 1
    frame.loc[sweep_low_index, "demand_zone_retest"] = 1
    frame.loc[sweep_low_index, "macd_hist"] = 0.3
    frame.loc[sweep_low_index - 3 : sweep_low_index - 1, "macd_hist"] = -0.2
    frame.loc[sweep_low_index, "cmf_20"] = 0.1

    base_reclaim_index = 160
    frame.loc[80:110, "Close"] = np.linspace(100.0, 88.0, 31)
    frame.loc[base_reclaim_index - 30 : base_reclaim_index - 1, "Low"] = 90.0
    frame.loc[base_reclaim_index - 8 : base_reclaim_index - 1, "High"] = 92.0
    frame.loc[base_reclaim_index, ["Open", "High", "Low", "Close"]] = [91.0, 94.8, 90.2, 94.2]
    frame.loc[base_reclaim_index, "choch_signal"] = 1
    frame.loc[base_reclaim_index, "range_100_position"] = 0.25
    frame.loc[base_reclaim_index, "macd_hist"] = 0.4
    frame.loc[base_reclaim_index - 3 : base_reclaim_index - 1, "macd_hist"] = -0.2
    frame.loc[base_reclaim_index, "force_index_z_50"] = 0.7

    features = {feature.feature_id: feature for feature in script.build_market_features(frame)}

    assert features["range_compression_breakdown_short"].signal.any()
    assert features["range_compression_breakout_long"].signal.any()
    assert features["supply_sweep_rejection_short"].signal.any()
    assert features["demand_sweep_reclaim_long"].signal.any()
    assert features["low_base_reclaim_long"].signal.any()


def test_updated_screenshot_downtrend_retest_and_sweep_watch_features_are_covered() -> None:
    frame = _three_wave_reversal_frame()
    periods = len(frame)
    frame["supply_zone_retest"] = 0
    frame["demand_zone_retest"] = 0
    frame["sweep_signal"] = np.zeros(periods, dtype=int)
    frame["low_volume_pullback"] = 0
    frame["session_vwap_distance_atr"] = -0.8
    frame["force_index_z_50"] = -0.5
    frame["mfi_14"] = 35.0
    frame["cmf_20"] = -0.2
    frame["macd_hist"] = -0.6
    frame["vfi_130"] = -1.0

    frame.loc[70:120, "Close"] = np.linspace(105.0, 89.0, 51)
    frame.loc[70:120, "Open"] = np.r_[105.0, frame.loc[70:119, "Close"].to_numpy()]
    frame.loc[70:120, "High"] = np.maximum(frame.loc[70:120, "Open"], frame.loc[70:120, "Close"]) + 0.4
    frame.loc[70:120, "Low"] = np.minimum(frame.loc[70:120, "Open"], frame.loc[70:120, "Close"]) - 0.4

    continuation_index = 132
    frame.loc[continuation_index - 45 : continuation_index - 1, "High"] = 103.0
    frame.loc[continuation_index - 8 : continuation_index - 1, "Low"] = 93.0
    frame.loc[continuation_index, ["Open", "High", "Low", "Close"]] = [94.5, 96.0, 90.5, 91.0]
    frame.loc[continuation_index, "supply_zone_retest"] = 1
    frame.loc[continuation_index, "low_volume_pullback"] = 1
    frame.loc[continuation_index - 3 : continuation_index - 1, "macd_hist"] = -0.1
    frame.loc[continuation_index, "macd_hist"] = -0.7
    frame.loc[continuation_index, "force_index_z_50"] = -0.8

    sweep_watch_index = 154
    frame.loc[sweep_watch_index - 90 : sweep_watch_index - 1, "Low"] = 90.0
    frame.loc[sweep_watch_index, ["Open", "High", "Low", "Close"]] = [89.5, 91.4, 87.0, 90.8]
    frame.loc[sweep_watch_index, "sweep_signal"] = 1
    frame.loc[sweep_watch_index, "demand_zone_retest"] = 1
    frame.loc[sweep_watch_index - 3 : sweep_watch_index - 1, "macd_hist"] = -0.8
    frame.loc[sweep_watch_index, "macd_hist"] = -0.2
    frame.loc[sweep_watch_index, "force_index_z_50"] = 0.4
    frame.loc[sweep_watch_index, "cmf_20"] = 0.0
    frame.loc[sweep_watch_index, "mfi_14"] = 42.0
    range_points = frame["High"] - frame["Low"]
    frame["body_share"] = (frame["Close"] - frame["Open"]).abs() / range_points
    frame["lower_wick_points"] = np.minimum(frame["Open"], frame["Close"]) - frame["Low"]
    frame["upper_wick_points"] = frame["High"] - np.maximum(frame["Open"], frame["Close"])

    features = {feature.feature_id: feature for feature in script.build_market_features(frame)}

    assert features["supply_retest_downtrend_continuation_short"].signal.any()
    assert features["selloff_liquidity_sweep_rebound_watch_long"].signal.any()


def test_ict_order_flow_shift_features_are_registered_and_triggerable() -> None:
    frame = _three_wave_reversal_frame()
    periods = len(frame)
    frame["fvg_signal"] = np.zeros(periods, dtype=int)
    frame["bullish_order_flow_shift_setup"] = np.zeros(periods, dtype=int)
    frame["bearish_order_flow_shift_setup"] = np.zeros(periods, dtype=int)
    frame["bullish_fvg_retest"] = np.zeros(periods, dtype=int)
    frame["bearish_fvg_retest"] = np.zeros(periods, dtype=int)
    frame["demand_zone_retest"] = np.zeros(periods, dtype=int)
    frame["supply_zone_retest"] = np.zeros(periods, dtype=int)
    frame["ofs_leg_position"] = np.nan
    frame["sweep_signal"] = np.zeros(periods, dtype=int)
    frame["choch_signal"] = np.zeros(periods, dtype=int)
    frame["bos_signal"] = np.zeros(periods, dtype=int)
    frame["force_index_z_50"] = 0.0

    bullish_setup = 120
    frame.loc[bullish_setup, ["Open", "High", "Low", "Close"]] = [91.0, 97.0, 90.5, 96.5]
    frame.loc[bullish_setup, "bullish_order_flow_shift_setup"] = 1
    frame.loc[bullish_setup, "fvg_signal"] = 1
    frame.loc[bullish_setup, "displacement_candle"] = 1
    frame.loc[bullish_setup, "body_share"] = 0.85
    frame.loc[bullish_setup - 3 : bullish_setup - 1, "macd_hist"] = -0.3
    frame.loc[bullish_setup, "macd_hist"] = 0.4
    frame.loc[bullish_setup, "force_index_z_50"] = 0.5

    bullish_entry = 126
    frame.loc[bullish_entry, ["Open", "High", "Low", "Close"]] = [94.0, 96.2, 93.8, 96.0]
    frame.loc[bullish_entry, "bullish_fvg_retest"] = 1
    frame.loc[bullish_entry, "demand_zone_retest"] = 1
    frame.loc[bullish_entry, "ofs_leg_position"] = 0.35
    frame.loc[bullish_entry, "range_100_position"] = 0.35
    frame.loc[bullish_entry, "cmf_20"] = 0.1
    frame.loc[bullish_entry, "choch_signal"] = 1

    bearish_setup = 145
    frame.loc[bearish_setup, ["Open", "High", "Low", "Close"]] = [101.0, 101.5, 94.0, 94.5]
    frame.loc[bearish_setup, "bearish_order_flow_shift_setup"] = 1
    frame.loc[bearish_setup, "fvg_signal"] = -1
    frame.loc[bearish_setup, "displacement_candle"] = 1
    frame.loc[bearish_setup, "body_share"] = 0.86
    frame.loc[bearish_setup - 3 : bearish_setup - 1, "macd_hist"] = 0.3
    frame.loc[bearish_setup, "macd_hist"] = -0.4
    frame.loc[bearish_setup, "force_index_z_50"] = -0.5

    bearish_entry = 151
    frame.loc[bearish_entry, ["Open", "High", "Low", "Close"]] = [97.8, 99.4, 96.8, 97.0]
    frame.loc[bearish_entry, "bearish_fvg_retest"] = 1
    frame.loc[bearish_entry, "supply_zone_retest"] = 1
    frame.loc[bearish_entry, "ofs_leg_position"] = 0.65
    frame.loc[bearish_entry, "range_100_position"] = 0.65
    frame.loc[bearish_entry, "cmf_20"] = -0.1
    frame.loc[bearish_entry, "choch_signal"] = -1

    features = {feature.feature_id: feature for feature in script.build_market_features(frame)}

    assert {
        "ict_bullish_order_flow_shift_setup",
        "ict_bearish_order_flow_shift_setup",
        "ict_bullish_ofs_fvg_retest_entry",
        "ict_bearish_ofs_fvg_retest_entry",
        "ict_bullish_ofs_ob_retest_entry",
        "ict_bearish_ofs_ob_retest_entry",
        "ict_bullish_order_flow_shift_quality_setup",
        "ict_bullish_order_flow_shift_opening_drive_setup",
        "ict_bullish_ofs_quality_pullback_reclaim",
        "ict_bullish_ofs_opening_drive_pullback_reclaim",
    } <= set(features)
    assert features["ict_bullish_order_flow_shift_setup"].signal.any()
    assert features["ict_bearish_order_flow_shift_setup"].signal.any()
    assert features["ict_bullish_ofs_fvg_retest_entry"].signal.any()
    assert features["ict_bearish_ofs_fvg_retest_entry"].signal.any()
    assert features["ict_bullish_ofs_ob_retest_entry"].signal.any()
    assert features["ict_bearish_ofs_ob_retest_entry"].signal.any()
    assert features["ict_bullish_order_flow_shift_quality_setup"].signal.any()
    assert features["ict_bullish_order_flow_shift_opening_drive_setup"].signal.any()
    assert features["ict_bullish_ofs_quality_pullback_reclaim"].signal.any()
    assert features["ict_bullish_ofs_opening_drive_pullback_reclaim"].signal.any()


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
