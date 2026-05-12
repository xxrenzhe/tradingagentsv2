from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.config.env import load_project_env
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.evolution.features import prepare_evolution_features
from tradingagents.evolution.memory import EvolutionMemory, utc_now
from tradingagents.evolution.nq_data import load_continuous_nq_bars
from tradingagents.execution.llm_debate_delayed_strategy import extract_json_object, invoke_aicode_streaming_json
from tradingagents.llm_clients.factory import create_llm_client


@dataclass(frozen=True)
class MarketFeature:
    feature_id: str
    family: str
    direction_hint: str
    description: str
    signal: pd.Series


def load_or_prepare_features(args: argparse.Namespace) -> pd.DataFrame:
    cache_path = Path(args.features_cache)
    if cache_path.exists() and not args.rebuild_features:
        cached = pd.read_pickle(cache_path)
        features = cached["features"] if isinstance(cached, dict) and "features" in cached else cached
        frame = features.copy()
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        return frame

    bars = load_continuous_nq_bars(
        start_date=args.start_date,
        end_date=args.end_date,
        cache_path=args.bars_cache,
        source_csv=Path(args.source_csv) if args.source_csv else None,
        source_zip=Path(args.source_zip) if args.source_zip else None,
        min_volume=args.min_volume,
    )
    features = prepare_evolution_features(bars)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle({"features": features, "created_at": utc_now()}, cache_path)
    return features


def build_market_features(data: pd.DataFrame) -> list[MarketFeature]:
    close = pd.to_numeric(data["Close"], errors="coerce")
    open_price = pd.to_numeric(data["Open"], errors="coerce")
    high = pd.to_numeric(data["High"], errors="coerce")
    low = pd.to_numeric(data["Low"], errors="coerce")
    volume = pd.to_numeric(data["Volume"], errors="coerce").fillna(0.0)
    atr = pd.to_numeric(data["atr_30"], errors="coerce").replace(0, np.nan)
    minute = pd.to_numeric(data["minute_of_day"], errors="coerce")
    rth = (minute >= 13 * 60 + 30) & (minute < 20 * 60)
    us_late = (minute >= 20 * 60) & (minute < 23 * 60)
    ldn_ny = (minute >= 7 * 60) & (minute < 20 * 60)
    range_points = high - low
    body_share = pd.to_numeric(data["body_share"], errors="coerce")
    volume_z = pd.to_numeric(data["volume_z_60"], errors="coerce").fillna(0.0)
    momentum_15_atr = close.diff(15) / atr
    momentum_30_atr = close.diff(30) / atr
    wick_lower = pd.to_numeric(data["lower_wick_points"], errors="coerce") / range_points.replace(0, np.nan)
    wick_upper = pd.to_numeric(data["upper_wick_points"], errors="coerce") / range_points.replace(0, np.nan)
    prior_low_60 = low.rolling(60, min_periods=30).min().shift(1)
    prior_high_60 = high.rolling(60, min_periods=30).max().shift(1)
    prior_low_120 = low.rolling(120, min_periods=60).min().shift(1)
    prior_high_120 = high.rolling(120, min_periods=60).max().shift(1)
    near_prior_low = (low <= prior_low_60 + 0.15 * atr) & (close > prior_low_60)
    near_prior_high = (high >= prior_high_60 - 0.15 * atr) & (close < prior_high_60)

    def numeric(column: str, default: float = np.nan) -> pd.Series:
        if column not in data:
            return pd.Series(default, index=data.index, dtype="float64")
        return pd.to_numeric(data[column], errors="coerce")

    def signal(column: str) -> pd.Series:
        if column not in data:
            return pd.Series(False, index=data.index)
        return pd.to_numeric(data[column], errors="coerce").fillna(0).ne(0)

    donch = numeric("donchian_20_position")
    adx = numeric("adx_14")
    di_spread = numeric("di_spread_14")
    cmf = numeric("cmf_20")
    obv_slope = numeric("obv_slope_20")
    mfi = numeric("mfi_14")
    vfi = numeric("vfi_130")
    macd_hist = numeric("macd_hist")
    boll_pos = numeric("boll_position")
    ichimoku_cloud_pos = numeric("ichimoku_cloud_position")
    ichimoku_cloud_thickness = numeric("ichimoku_cloud_thickness_atr")
    aroon_up = numeric("aroon_up_25")
    aroon_down = numeric("aroon_down_25")
    aroon_osc = numeric("aroon_osc_25")
    trix = numeric("trix_15")
    trix_signal = numeric("trix_signal_9")
    tsi = numeric("tsi_25_13")
    ultimate = numeric("ultimate_osc_7_14_28")
    williams = numeric("williams_r_14")
    kst = numeric("kst")
    kst_signal = numeric("kst_signal")
    roc_10 = numeric("roc_10")
    roc_20 = numeric("roc_20")
    psar_direction = numeric("psar_direction")
    psar_distance = numeric("psar_distance_atr")
    vortex_spread = numeric("vortex_spread_14")
    vwma_spread = numeric("vwma_spread_atr")
    tema_slope = numeric("tema_21_slope_atr")
    cmo = numeric("cmo_14")
    dpo = numeric("dpo_20")
    chaikin = numeric("chaikin_osc_3_10")
    chaikin_z = numeric("chaikin_osc_z_50")
    force_z = numeric("force_index_z_50")
    eom_z = numeric("eom_z_50")
    range_pos = numeric("range_100_position")
    range_width_atr = numeric("range_100_width_atr")
    sweep = numeric("sweep_signal", default=0.0)
    choch = numeric("choch_signal", default=0.0)
    bos = numeric("bos_signal", default=0.0)
    fvg = numeric("fvg_signal", default=0.0)
    ofs_position = numeric("ofs_leg_position")
    session_vwap_atr = numeric("session_vwap_distance_atr")
    down_impulse_45 = close.diff(45) / atr <= -3.0
    up_impulse_45 = close.diff(45) / atr >= 3.0
    up_impulse_30 = close.diff(30) / atr >= 2.0
    down_impulse_30 = close.diff(30) / atr <= -2.0
    recent_down_impulse = down_impulse_45.rolling(90, min_periods=1).max().shift(1).fillna(False).astype(bool)
    recent_up_impulse = up_impulse_45.rolling(90, min_periods=1).max().shift(1).fillna(False).astype(bool)
    rebound_after_down = up_impulse_30 & recent_down_impulse
    sell_response_after_up = down_impulse_30 & recent_up_impulse
    recent_rebound_after_down = rebound_after_down.rolling(45, min_periods=1).max().shift(1).fillna(False).astype(bool)
    recent_sell_response_after_up = sell_response_after_up.rolling(45, min_periods=1).max().shift(1).fillna(False).astype(bool)
    recent_pullback_depth = (high.rolling(20, min_periods=5).max().shift(1) - low) / atr
    recent_short_pullback_depth = (high - low.rolling(20, min_periods=5).min().shift(1)) / atr
    prior_downtrend_pressure = close.diff(45) / atr <= -4.0
    recent_downtrend_pressure = prior_downtrend_pressure.rolling(90, min_periods=1).max().shift(1).fillna(False).astype(bool)
    lower_high_reject = high < high.rolling(45, min_periods=15).max().shift(1) - 0.25 * atr
    selloff_extreme_probe = low <= low.rolling(90, min_periods=30).min().shift(1) + 0.15 * atr
    reversal_watch_reclaim = close > low + 0.45 * range_points
    micro_break_up = close > high.rolling(8, min_periods=4).max().shift(1)
    micro_break_down = close < low.rolling(8, min_periods=4).min().shift(1)
    macd_rising = macd_hist > macd_hist.shift(3)
    macd_falling = macd_hist < macd_hist.shift(3)
    macd_cross_up = (macd_hist > 0) & (macd_hist.shift(1) <= 0)
    macd_cross_down = (macd_hist < 0) & (macd_hist.shift(1) >= 0)
    trend_stack_up = (data["ema_10"] > data["ema_20"]) & (data["ema_20"] > data["ema_50"])
    trend_stack_down = (data["ema_10"] < data["ema_20"]) & (data["ema_20"] < data["ema_50"])
    recent_bullish_bos_count = (bos > 0).rolling(90, min_periods=1).sum().shift(1).fillna(0)
    recent_bearish_bos_count = (bos < 0).rolling(90, min_periods=1).sum().shift(1).fillna(0)
    recent_bullish_choch = (choch > 0).rolling(45, min_periods=1).max().shift(1).fillna(False).astype(bool)
    recent_bearish_choch = (choch < 0).rolling(45, min_periods=1).max().shift(1).fillna(False).astype(bool)
    bullish_step_pullback = (close - low.rolling(20, min_periods=5).min().shift(1)) / atr
    bearish_step_pullback = (high.rolling(20, min_periods=5).max().shift(1) - close) / atr
    compressed_range = (
        (range_width_atr <= 4.0)
        | (range_width_atr <= range_width_atr.rolling(240, min_periods=60).quantile(0.35))
    )
    local_base_low = low.rolling(30, min_periods=10).min().shift(1)
    local_base_high = high.rolling(30, min_periods=10).max().shift(1)
    range_close_position = ((close - low) / range_points.replace(0, np.nan)).clip(0.0, 1.0)
    range_close_position = range_close_position.fillna(0.5)
    opening_drive_rth = rth & (minute < 16 * 60)
    prior_session_impulse_30 = close.diff(30).abs() / atr
    impulse_to_pullback = prior_session_impulse_30 / recent_pullback_depth.replace(0, np.nan)
    bullish_reclaim_quality = (
        signal("bullish_order_flow_shift_setup")
        & (close > open_price)
        & (body_share >= 0.70)
        & (range_close_position >= 0.70)
        & (volume_z >= 0.25)
        & ((cmf > 0) | (force_z > 0.5) | (vfi > vfi.shift(10)))
        & (session_vwap_atr >= -0.25)
    )
    bullish_pullback_quality = (
        (ofs_position.between(0.15, 0.55))
        & (range_close_position >= 0.60)
        & (recent_pullback_depth.between(0.25, 1.75))
        & (impulse_to_pullback >= 1.25)
        & ((close > high.shift(1)) | (close > (high + low) / 2))
        & (macd_rising | (cmf > 0) | (force_z > 0.25))
    )

    features = [
        MarketFeature(
            "ict_bullish_order_flow_shift_setup",
            "ict_order_flow_shift",
            "long",
            "Liquidity sweep below a prior low is followed by bullish displacement/MSS and a bullish FVG, marking a delivery-state shift.",
            signal("bullish_order_flow_shift_setup")
            & (fvg > 0)
            & (body_share >= 0.55)
            & (close > open_price)
            & (macd_rising | (cmf > 0) | (force_z > 0) | (volume_z >= 0)),
        ),
        MarketFeature(
            "ict_bullish_order_flow_shift_quality_setup",
            "ict_order_flow_shift_quality",
            "long",
            "Bullish OFS with stronger displacement quality: dominant body, high close, constructive volume flow, and VWAP acceptance.",
            bullish_reclaim_quality,
        ),
        MarketFeature(
            "ict_bullish_order_flow_shift_opening_drive_setup",
            "ict_order_flow_shift_quality",
            "long",
            "High-quality bullish OFS during the early US RTH opening-drive window, where directional continuation is more likely.",
            bullish_reclaim_quality
            & opening_drive_rth
            & (prior_session_impulse_30 >= 1.0),
        ),
        MarketFeature(
            "ict_bearish_order_flow_shift_setup",
            "ict_order_flow_shift",
            "short",
            "Liquidity sweep above a prior high is followed by bearish displacement/MSS and a bearish FVG, marking a delivery-state shift.",
            signal("bearish_order_flow_shift_setup")
            & (fvg < 0)
            & (body_share >= 0.55)
            & (close < open_price)
            & (macd_falling | (cmf < 0) | (force_z < 0) | (volume_z >= 0)),
        ),
        MarketFeature(
            "ict_bullish_ofs_fvg_retest_entry",
            "ict_order_flow_shift_entry",
            "long",
            "After bullish OFS, price trades back into the bullish FVG/order block in discount and holds the reclaimed delivery leg.",
            (signal("bullish_fvg_retest") | signal("demand_zone_retest"))
            & (ofs_position <= 0.50)
            & (ofs_position >= 0.0)
            & ((range_pos <= 0.55) | (session_vwap_atr >= -0.50))
            & ((close > open_price) | (close > (high + low) / 2))
            & (macd_rising | (cmf > 0) | (force_z > 0)),
        ),
        MarketFeature(
            "ict_bullish_ofs_quality_pullback_reclaim",
            "ict_order_flow_shift_quality",
            "long",
            "After bullish OFS, the pullback is shallow enough, closes strong, and reclaims with favorable impulse-to-pullback quality.",
            (signal("bullish_fvg_retest") | signal("demand_zone_retest"))
            & bullish_pullback_quality,
        ),
        MarketFeature(
            "ict_bullish_ofs_opening_drive_pullback_reclaim",
            "ict_order_flow_shift_quality",
            "long",
            "Opening-drive bullish OFS pullback reclaim: retest holds the discount half and reclaims with strong close/flow confirmation.",
            (signal("bullish_fvg_retest") | signal("demand_zone_retest"))
            & bullish_pullback_quality
            & opening_drive_rth
            & (session_vwap_atr >= 0),
        ),
        MarketFeature(
            "ict_bearish_ofs_fvg_retest_entry",
            "ict_order_flow_shift_entry",
            "short",
            "After bearish OFS, price trades back into the bearish FVG/order block in premium and rejects the reclaimed delivery leg.",
            (signal("bearish_fvg_retest") | signal("supply_zone_retest"))
            & (ofs_position >= 0.50)
            & (ofs_position <= 1.0)
            & ((range_pos >= 0.45) | (session_vwap_atr <= 0.50))
            & ((close < open_price) | (close < (high + low) / 2))
            & (macd_falling | (cmf < 0) | (force_z < 0)),
        ),
        MarketFeature(
            "ict_bullish_ofs_ob_retest_entry",
            "ict_order_block_retest",
            "long",
            "Bullish OFS remains active and price retests the demand/order-block side of the displacement leg with supportive volume flow.",
            signal("demand_zone_retest")
            & (ofs_position <= 0.55)
            & (sweep >= 0)
            & ((choch > 0) | (bos > 0) | signal("bullish_fvg_retest"))
            & (cmf > -0.05)
            & (close >= open_price),
        ),
        MarketFeature(
            "ict_bearish_ofs_ob_retest_entry",
            "ict_order_block_retest",
            "short",
            "Bearish OFS remains active and price retests the supply/order-block side of the displacement leg with weak volume flow.",
            signal("supply_zone_retest")
            & (ofs_position >= 0.45)
            & (sweep <= 0)
            & ((choch < 0) | (bos < 0) | signal("bearish_fvg_retest"))
            & (cmf < 0.05)
            & (close <= open_price),
        ),
        MarketFeature(
            "smc_breakdown_downtrend_wave",
            "smc_sequence",
            "short",
            "BOS-style downside break from a local range with displacement, downside DI/MACD alignment, and price below session VWAP.",
            (data["displacement_candle"].eq(1))
            & (close < open_price)
            & (close < prior_low_60)
            & (di_spread < 0)
            & (macd_hist < 0)
            & (session_vwap_atr < 0),
        ),
        MarketFeature(
            "capitulation_v_reversal_long",
            "smc_sequence",
            "long",
            "Fast downside impulse exhausts into a fresh local low, then closes off the low with MACD/volume-price repair.",
            recent_down_impulse
            & (low <= prior_low_60 + 0.10 * atr)
            & (wick_lower >= 0.35)
            & (close > (high + low) / 2)
            & (macd_rising | (cmf > 0) | (mfi > 45)),
        ),
        MarketFeature(
            "selloff_reversal_pullback_continuation_long",
            "smc_sequence",
            "long",
            "Three-wave sequence: prior selloff, sharp rebound, controlled higher-low pullback, then upside continuation break.",
            recent_down_impulse
            & recent_rebound_after_down
            & (recent_pullback_depth >= 0.75)
            & (low > low.rolling(90, min_periods=30).min().shift(1))
            & micro_break_up
            & (macd_rising | (cmf > 0) | (vfi > vfi.shift(10))),
        ),
        MarketFeature(
            "trend_start_long_displacement",
            "trend_start",
            "long",
            "Compression resolves upward with a displacement candle, expanding volume, DI confirmation, and Donchian upper-half location.",
            (data["displacement_candle"].eq(1))
            & (close > open_price)
            & (volume_z >= 0.5)
            & (adx >= 18)
            & (di_spread > 0)
            & (donch > 0.6),
        ),
        MarketFeature(
            "trend_start_short_displacement",
            "trend_start",
            "short",
            "Compression resolves downward with a displacement candle, expanding volume, DI confirmation, and Donchian lower-half location.",
            (data["displacement_candle"].eq(1))
            & (close < open_price)
            & (volume_z >= 0.5)
            & (adx >= 18)
            & (di_spread < 0)
            & (donch < 0.4),
        ),
        MarketFeature(
            "range_compression_breakout_long",
            "range_breakout",
            "long",
            "A sideways/compressed range resolves upward with a micro break, positive momentum repair, and VWAP support.",
            compressed_range
            & micro_break_up
            & (close > open_price)
            & ((bos > 0) | data["displacement_candle"].eq(1) | signal("session_vwap_reclaim_up"))
            & (session_vwap_atr >= -0.10)
            & (macd_rising | (trix > trix_signal) | (force_z > 0)),
        ),
        MarketFeature(
            "range_compression_breakdown_short",
            "range_breakout",
            "short",
            "A sideways/compressed range resolves downward with a micro break, downside momentum repair, and VWAP resistance.",
            compressed_range
            & micro_break_down
            & (close < open_price)
            & ((bos < 0) | data["displacement_candle"].eq(1) | signal("session_vwap_reclaim_down"))
            & (session_vwap_atr <= 0.10)
            & (macd_falling | (trix < trix_signal) | (force_z < 0)),
        ),
        MarketFeature(
            "bos_stair_step_continuation_long",
            "smc_bos_continuation",
            "long",
            "Repeated bullish BOS creates a stair-step trend; a controlled pullback holds VWAP/EMA structure and breaks upward again.",
            (recent_bullish_bos_count >= 2)
            & trend_stack_up
            & (session_vwap_atr >= -0.25)
            & (bullish_step_pullback.between(0.20, 3.00))
            & (micro_break_up | (bos > 0))
            & (macd_rising | (force_z > 0) | (cmf > 0)),
        ),
        MarketFeature(
            "bos_stair_step_continuation_short",
            "smc_bos_continuation",
            "short",
            "Repeated bearish BOS creates a stair-step downtrend; a controlled bounce rejects VWAP/EMA structure and breaks downward again.",
            (recent_bearish_bos_count >= 2)
            & trend_stack_down
            & (session_vwap_atr <= 0.25)
            & (bearish_step_pullback.between(0.20, 3.00))
            & (micro_break_down | (bos < 0))
            & (macd_falling | (force_z < 0) | (cmf < 0)),
        ),
        MarketFeature(
            "failed_bearish_choch_uptrend_continuation_long",
            "smc_failed_choch_continuation",
            "long",
            "A bearish CHoCH appears inside an established bullish BOS sequence but fails to create acceptance lower; the next upside break resumes trend.",
            (recent_bullish_bos_count >= 1)
            & recent_bearish_choch
            & (session_vwap_atr >= -0.35)
            & ((low >= low.rolling(60, min_periods=20).min().shift(1) + 0.15 * atr) | trend_stack_up)
            & micro_break_up
            & (macd_rising | (force_z > 0) | (cmf > -0.05)),
        ),
        MarketFeature(
            "failed_bullish_choch_downtrend_continuation_short",
            "smc_failed_choch_continuation",
            "short",
            "A bullish CHoCH appears inside an established bearish BOS sequence but fails to create acceptance higher; the next downside break resumes trend.",
            (recent_bearish_bos_count >= 1)
            & recent_bullish_choch
            & (session_vwap_atr <= 0.35)
            & ((high <= high.rolling(60, min_periods=20).max().shift(1) - 0.15 * atr) | trend_stack_down)
            & micro_break_down
            & (macd_falling | (force_z < 0) | (cmf < 0.05)),
        ),
        MarketFeature(
            "eql_sweep_macd_reversal_long",
            "smc_liquidity_macd_reversal",
            "long",
            "Equal-low or lower-liquidity sweep rejects with lower wick, MACD histogram repair, and improving money pressure.",
            (signal("eql_signal") | (sweep > 0) | near_prior_low)
            & (wick_lower >= 0.25)
            & (close > (high + low) / 2)
            & (macd_cross_up | macd_rising)
            & ((force_z > 0) | (cmf > -0.05) | (mfi > 40)),
        ),
        MarketFeature(
            "eqh_sweep_macd_reversal_short",
            "smc_liquidity_macd_reversal",
            "short",
            "Equal-high or upper-liquidity sweep rejects with upper wick, MACD histogram deterioration, and weakening money pressure.",
            (signal("eqh_signal") | (sweep < 0) | near_prior_high)
            & (wick_upper >= 0.25)
            & (close < (high + low) / 2)
            & (macd_cross_down | macd_falling)
            & ((force_z < 0) | (cmf < 0.05) | (mfi < 60)),
        ),
        MarketFeature(
            "displacement_pullback_continuation_long",
            "smc_displacement_pullback",
            "long",
            "A bullish displacement/BOS leg leaves a demand/FVG area; the first controlled pullback holds and re-breaks upward.",
            ((bos > 0).rolling(20, min_periods=1).max().shift(1).fillna(False).astype(bool) | signal("bullish_fvg_retest") | signal("demand_zone_retest"))
            & (session_vwap_atr >= -0.30)
            & (recent_pullback_depth.between(0.25, 2.25))
            & (close >= open_price)
            & micro_break_up
            & (macd_rising | (force_z > 0) | (cmf > -0.05)),
        ),
        MarketFeature(
            "displacement_pullback_continuation_short",
            "smc_displacement_pullback",
            "short",
            "A bearish displacement/BOS leg leaves a supply/FVG area; the first controlled pullback rejects and re-breaks downward.",
            ((bos < 0).rolling(20, min_periods=1).max().shift(1).fillna(False).astype(bool) | signal("bearish_fvg_retest") | signal("supply_zone_retest"))
            & (session_vwap_atr <= 0.30)
            & (recent_short_pullback_depth.between(0.25, 2.25))
            & (close <= open_price)
            & micro_break_down
            & (macd_falling | (force_z < 0) | (cmf < 0.05)),
        ),
        MarketFeature(
            "ichimoku_cloud_breakout_long",
            "tradingview_trend",
            "long",
            "Price breaks above a thin Ichimoku cloud with Aroon and TRIX/KST momentum confirmation.",
            signal("ichimoku_bullish_breakout")
            & (ichimoku_cloud_thickness <= 2.5)
            & (aroon_osc > 20)
            & ((trix > trix_signal) | (kst > kst_signal) | (roc_10 > 0)),
        ),
        MarketFeature(
            "ichimoku_cloud_breakdown_short",
            "tradingview_trend",
            "short",
            "Price breaks below a thin Ichimoku cloud with Aroon and TRIX/KST downside momentum confirmation.",
            signal("ichimoku_bearish_breakdown")
            & (ichimoku_cloud_thickness <= 2.5)
            & (aroon_osc < -20)
            & ((trix < trix_signal) | (kst < kst_signal) | (roc_10 < 0)),
        ),
        MarketFeature(
            "aroon_trend_start_long",
            "tradingview_trend",
            "long",
            "Aroon flips to a fresh upside trend while price is above VWAP and medium momentum confirms.",
            signal("aroon_bullish_cross")
            & (aroon_up >= 70)
            & (session_vwap_atr > 0)
            & (roc_20 > 0)
            & ((tsi > 0) | (kst > kst_signal)),
        ),
        MarketFeature(
            "aroon_trend_start_short",
            "tradingview_trend",
            "short",
            "Aroon flips to a fresh downside trend while price is below VWAP and medium momentum confirms.",
            signal("aroon_bearish_cross")
            & (aroon_down >= 70)
            & (session_vwap_atr < 0)
            & (roc_20 < 0)
            & ((tsi < 0) | (kst < kst_signal)),
        ),
        MarketFeature(
            "trix_kst_momentum_reversal_long",
            "tradingview_momentum",
            "long",
            "TRIX or KST crosses up after discount/weak price, suggesting a momentum repair from oversold conditions.",
            (signal("trix_cross_up") | signal("kst_cross_up"))
            & ((range_pos <= 0.35) | (williams <= -70) | (ultimate <= 40))
            & (close > close.shift(3))
            & ((cmf > 0) | (mfi > 45) | (vfi > vfi.shift(10))),
        ),
        MarketFeature(
            "trix_kst_momentum_reversal_short",
            "tradingview_momentum",
            "short",
            "TRIX or KST crosses down after premium/strong price, suggesting upside momentum failure.",
            (signal("trix_cross_down") | signal("kst_cross_down"))
            & ((range_pos >= 0.65) | (williams >= -30) | (ultimate >= 60))
            & (close < close.shift(3))
            & ((cmf < 0) | (mfi < 55) | (vfi < vfi.shift(10))),
        ),
        MarketFeature(
            "williams_ultimate_oversold_reclaim_long",
            "tradingview_oscillator",
            "long",
            "Williams %R recovers from oversold while Ultimate Oscillator and price reclaim from a discount area.",
            signal("williams_recover_up")
            & (ultimate > ultimate.shift(3))
            & ((range_pos <= 0.35) | near_prior_low)
            & (close > (high + low) / 2)
            & ((volume_z > 0) | (cmf > 0) | (mfi > 45)),
        ),
        MarketFeature(
            "williams_ultimate_overbought_fade_short",
            "tradingview_oscillator",
            "short",
            "Williams %R fades from overbought while Ultimate Oscillator and price reject a premium area.",
            signal("williams_fade_down")
            & (ultimate < ultimate.shift(3))
            & ((range_pos >= 0.65) | near_prior_high)
            & (close < (high + low) / 2)
            & ((volume_z > 0) | (cmf < 0) | (mfi < 55)),
        ),
        MarketFeature(
            "cloud_pullback_trend_long",
            "tradingview_pullback",
            "long",
            "Price pulls back toward the Ichimoku cloud in an intact upside Aroon/TSI trend without losing VWAP.",
            (ichimoku_cloud_pos.between(0.0, 1.2))
            & (aroon_up > aroon_down)
            & (tsi > 0)
            & (roc_20 > 0)
            & (session_vwap_atr >= -0.25)
            & data["low_volume_pullback"].eq(1),
        ),
        MarketFeature(
            "cloud_pullback_trend_short",
            "tradingview_pullback",
            "short",
            "Price pulls back toward the Ichimoku cloud in an intact downside Aroon/TSI trend without reclaiming VWAP.",
            (ichimoku_cloud_pos.between(-0.2, 1.0))
            & (aroon_down > aroon_up)
            & (tsi < 0)
            & (roc_20 < 0)
            & (session_vwap_atr <= 0.25)
            & data["low_volume_pullback"].eq(1),
        ),
        MarketFeature(
            "psar_vortex_trend_start_long",
            "tradingview_trend",
            "long",
            "Parabolic SAR flips up with Vortex trend confirmation, VWMA/TEMA alignment, and positive money pressure.",
            (signal("psar_flip_up") | signal("vortex_bullish_cross"))
            & (psar_direction > 0)
            & (psar_distance >= 0)
            & (vortex_spread > 0)
            & (tema_slope > 0)
            & ((vwma_spread > 0) | (session_vwap_atr > 0))
            & ((force_z > 0) | (chaikin > 0)),
        ),
        MarketFeature(
            "psar_vortex_trend_start_short",
            "tradingview_trend",
            "short",
            "Parabolic SAR flips down with Vortex trend confirmation, VWMA/TEMA alignment, and negative money pressure.",
            (signal("psar_flip_down") | signal("vortex_bearish_cross"))
            & (psar_direction < 0)
            & (psar_distance <= 0)
            & (vortex_spread < 0)
            & (tema_slope < 0)
            & ((vwma_spread < 0) | (session_vwap_atr < 0))
            & ((force_z < 0) | (chaikin < 0)),
        ),
        MarketFeature(
            "chaikin_force_accumulation_reversal_long",
            "tradingview_volume_price",
            "long",
            "Discount-area price weakness meets Chaikin/Force accumulation and CMO repair, suggesting sell pressure is fading.",
            ((range_pos <= 0.35) | near_prior_low | (boll_pos <= -0.75))
            & ((signal("chaikin_bullish_cross")) | (chaikin_z > 0.5) | (force_z > 0.8))
            & (cmo > cmo.shift(3))
            & (close > (high + low) / 2),
        ),
        MarketFeature(
            "chaikin_force_distribution_reversal_short",
            "tradingview_volume_price",
            "short",
            "Premium-area price strength meets Chaikin/Force distribution and CMO deterioration, suggesting buy pressure is fading.",
            ((range_pos >= 0.65) | near_prior_high | (boll_pos >= 0.75))
            & ((signal("chaikin_bearish_cross")) | (chaikin_z < -0.5) | (force_z < -0.8))
            & (cmo < cmo.shift(3))
            & (close < (high + low) / 2),
        ),
        MarketFeature(
            "cmo_dpo_cycle_reversal_long",
            "tradingview_oscillator",
            "long",
            "CMO recovers from bearish momentum while DPO/EOM turn up from a discount cycle location.",
            signal("cmo_recover_up")
            & (dpo > dpo.shift(3))
            & (eom_z > eom_z.shift(3))
            & ((range_pos <= 0.4) | (williams <= -60) | (ultimate <= 45)),
        ),
        MarketFeature(
            "cmo_dpo_cycle_reversal_short",
            "tradingview_oscillator",
            "short",
            "CMO fades from bullish momentum while DPO/EOM turn down from a premium cycle location.",
            signal("cmo_fade_down")
            & (dpo < dpo.shift(3))
            & (eom_z < eom_z.shift(3))
            & ((range_pos >= 0.6) | (williams >= -40) | (ultimate >= 55)),
        ),
        MarketFeature(
            "vwma_tema_pullback_continuation_long",
            "tradingview_pullback",
            "long",
            "VWMA and TEMA stay positively aligned while a quiet pullback holds near VWAP and money pressure stays constructive.",
            data["low_volume_pullback"].eq(1)
            & (vwma_spread > 0)
            & (tema_slope > 0)
            & (psar_direction >= 0)
            & (session_vwap_atr >= -0.25)
            & ((force_z > -0.25) | (chaikin_z > -0.25)),
        ),
        MarketFeature(
            "vwma_tema_pullback_continuation_short",
            "tradingview_pullback",
            "short",
            "VWMA and TEMA stay negatively aligned while a quiet pullback stays below VWAP and money pressure stays weak.",
            data["low_volume_pullback"].eq(1)
            & (vwma_spread < 0)
            & (tema_slope < 0)
            & (psar_direction <= 0)
            & (session_vwap_atr <= 0.25)
            & ((force_z < 0.25) | (chaikin_z < 0.25)),
        ),
        MarketFeature(
            "fast_selloff_rebound",
            "exhaustion_reversal",
            "long",
            "Fast 15-minute selloff reaches prior support or discount, prints a lower wick, and closes back above the bar midpoint.",
            (momentum_15_atr <= -1.5)
            & (near_prior_low | (range_pos <= 0.25))
            & (wick_lower >= 0.45)
            & (close > (high + low) / 2),
        ),
        MarketFeature(
            "fast_rally_fade",
            "exhaustion_reversal",
            "short",
            "Fast 15-minute rally reaches prior resistance or premium, prints an upper wick, and closes back below the bar midpoint.",
            (momentum_15_atr >= 1.5)
            & (near_prior_high | (range_pos >= 0.75))
            & (wick_upper >= 0.45)
            & (close < (high + low) / 2),
        ),
        MarketFeature(
            "supply_sweep_rejection_short",
            "liquidity_reversal",
            "short",
            "Price sweeps a prior high or supply zone, fails back below the level, and momentum/volume confirms rejection.",
            (near_prior_high | signal("supply_zone_retest") | (sweep < 0))
            & (wick_upper >= 0.30)
            & ((close < open_price) | (close < (high + low) / 2))
            & (macd_falling | (cmf < 0) | (vfi < vfi.shift(10)) | (force_z < 0)),
        ),
        MarketFeature(
            "demand_sweep_reclaim_long",
            "liquidity_reversal",
            "long",
            "Price sweeps a prior low or demand zone, reclaims the level, and momentum/volume confirms absorption.",
            (near_prior_low | signal("demand_zone_retest") | (sweep > 0))
            & (wick_lower >= 0.30)
            & ((close > open_price) | (close > (high + low) / 2))
            & (macd_rising | (cmf > 0) | (vfi > vfi.shift(10)) | (force_z > 0)),
        ),
        MarketFeature(
            "sell_pressure_absorbed_rebound",
            "absorption",
            "long",
            "Price probes a prior low but selling fails to extend; CMF/OBV or MFI shows accumulation against weak price.",
            (near_prior_low | (low <= prior_low_120 + 0.20 * atr))
            & ((cmf > 0) | (obv_slope > 0) | (mfi > 45))
            & (close >= open_price),
        ),
        MarketFeature(
            "buy_pressure_absorbed_fade",
            "absorption",
            "short",
            "Price probes a prior high but buying fails to extend; CMF/OBV or MFI shows distribution against strong price.",
            (near_prior_high | (high >= prior_high_120 - 0.20 * atr))
            & ((cmf < 0) | (obv_slope < 0) | (mfi < 55))
            & (close <= open_price),
        ),
        MarketFeature(
            "w_bottom_reclaim",
            "double_bottom",
            "long",
            "A second low near the prior swing low rejects and reclaims the midpoint/VWAP area with improving money flow.",
            (low.sub(prior_low_60).abs() <= 0.25 * atr)
            & (close > open_price)
            & (session_vwap_atr > -0.25)
            & ((cmf > 0) | (vfi > 0) | (mfi > 50)),
        ),
        MarketFeature(
            "m_top_reject",
            "double_top",
            "short",
            "A second high near the prior swing high rejects and loses the midpoint/VWAP area with weakening money flow.",
            (high.sub(prior_high_60).abs() <= 0.25 * atr)
            & (close < open_price)
            & (session_vwap_atr < 0.25)
            & ((cmf < 0) | (vfi < 0) | (mfi < 50)),
        ),
        MarketFeature(
            "volume_price_bullish_mismatch",
            "volume_price_mismatch",
            "long",
            "Price is weak or at discount while OBV/CMF/VFI diverges upward, suggesting hidden accumulation.",
            ((close < close.shift(20)) | (range_pos <= 0.35) | (boll_pos <= -0.75))
            & ((data["bullish_volume_divergence"].eq(1)) | ((cmf > 0) & (obv_slope > 0)) | (vfi > vfi.shift(20))),
        ),
        MarketFeature(
            "volume_price_bearish_mismatch",
            "volume_price_mismatch",
            "short",
            "Price is strong or at premium while OBV/CMF/VFI diverges downward, suggesting hidden distribution.",
            ((close > close.shift(20)) | (range_pos >= 0.65) | (boll_pos >= 0.75))
            & ((data["bearish_volume_divergence"].eq(1)) | ((cmf < 0) & (obv_slope < 0)) | (vfi < vfi.shift(20))),
        ),
        MarketFeature(
            "low_volume_pullback_trend_long",
            "trend_pullback",
            "long",
            "An uptrend pauses on lower volume without losing trend stack; pullback may offer continuation entry.",
            (data["low_volume_pullback"].eq(1))
            & (data["ema_10"] > data["ema_20"])
            & (data["ema_20"] > data["ema_50"])
            & (session_vwap_atr >= -0.25)
            & (momentum_30_atr > 0),
        ),
        MarketFeature(
            "low_volume_pullback_trend_short",
            "trend_pullback",
            "short",
            "A downtrend pauses on lower volume without regaining trend stack; pullback may offer continuation entry.",
            (data["low_volume_pullback"].eq(1))
            & (data["ema_10"] < data["ema_20"])
            & (data["ema_20"] < data["ema_50"])
            & (session_vwap_atr <= 0.25)
            & (momentum_30_atr < 0),
        ),
        MarketFeature(
            "supply_retest_downtrend_continuation_short",
            "supply_retest_continuation",
            "short",
            "In an established downtrend, a lower-high retest into supply/VWAP rejection fails and breaks the local micro low.",
            recent_downtrend_pressure
            & (signal("supply_zone_retest") | data["low_volume_pullback"].eq(1) | (session_vwap_atr <= 0.25))
            & lower_high_reject
            & micro_break_down
            & (close < open_price)
            & (macd_falling | (cmf < 0) | (force_z < 0) | (vfi < vfi.shift(10))),
        ),
        MarketFeature(
            "selloff_liquidity_sweep_rebound_watch_long",
            "reversal_watch",
            "long",
            "After a steep downtrend sweeps lower liquidity, price starts a reclaim/rebound watch but still needs bullish structure confirmation before trend reversal.",
            recent_downtrend_pressure
            & (selloff_extreme_probe | near_prior_low | signal("demand_zone_retest") | (sweep > 0))
            & (wick_lower >= 0.20)
            & reversal_watch_reclaim
            & (macd_rising | (force_z > 0) | (cmf > -0.05) | (mfi > 35)),
        ),
        MarketFeature(
            "vwap_reclaim_after_selloff",
            "reclaim",
            "long",
            "After a selloff, price reclaims session VWAP with improving volume-price state.",
            (data["session_vwap_reclaim_up"].eq(1))
            & (momentum_30_atr < 0)
            & ((volume_z > 0) | (cmf > 0) | (mfi > 50)),
        ),
        MarketFeature(
            "vwap_loss_after_rally",
            "reclaim",
            "short",
            "After a rally, price loses session VWAP with weakening volume-price state.",
            (data["session_vwap_reclaim_down"].eq(1))
            & (momentum_30_atr > 0)
            & ((volume_z > 0) | (cmf < 0) | (mfi < 50)),
        ),
        MarketFeature(
            "low_base_reclaim_long",
            "base_reclaim",
            "long",
            "After a selloff, price stops making meaningful new lows, reclaims a local base, and momentum starts to repair.",
            recent_down_impulse
            & (range_pos <= 0.40)
            & (low >= local_base_low - 0.20 * atr)
            & (micro_break_up | (choch > 0) | signal("session_vwap_reclaim_up"))
            & (macd_rising | (cmo > cmo.shift(3)) | (force_z > 0) | (cmf > 0)),
        ),
        MarketFeature(
            "high_base_reject_short",
            "base_reclaim",
            "short",
            "After a rally, price stops making meaningful new highs, loses a local base, and momentum starts to deteriorate.",
            recent_up_impulse
            & (range_pos >= 0.60)
            & (high <= local_base_high + 0.20 * atr)
            & (micro_break_down | (choch < 0) | signal("session_vwap_reclaim_down"))
            & (macd_falling | (cmo < cmo.shift(3)) | (force_z < 0) | (cmf < 0)),
        ),
        MarketFeature(
            "rally_fade_pullback_continuation_short",
            "smc_sequence",
            "short",
            "Mirror sequence: prior rally, sharp sell response, controlled lower-high pullback, then downside continuation break.",
            recent_up_impulse
            & recent_sell_response_after_up
            & (recent_short_pullback_depth >= 0.75)
            & (high < high.rolling(90, min_periods=30).max().shift(1))
            & micro_break_down
            & (macd_falling | (cmf < 0) | (vfi < vfi.shift(10))),
        ),
    ]
    session_features: list[MarketFeature] = []
    for base in features:
        session_features.append(base)
        session_features.append(
            MarketFeature(
                f"{base.feature_id}_us_rth",
                base.family,
                base.direction_hint,
                f"{base.description} Session-filtered to US RTH.",
                base.signal & rth,
            )
        )
        session_features.append(
            MarketFeature(
                f"{base.feature_id}_us_late",
                base.family,
                base.direction_hint,
                f"{base.description} Session-filtered to US late session.",
                base.signal & us_late,
            )
        )
        session_features.append(
            MarketFeature(
                f"{base.feature_id}_ldn_ny",
                base.family,
                base.direction_hint,
                f"{base.description} Session-filtered to London/New York overlap.",
                base.signal & ldn_ny,
            )
        )
    return session_features


def event_path_rows(
    data: pd.DataFrame,
    market_features: list[MarketFeature],
    *,
    horizons: list[int],
    min_gap_minutes: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    close = pd.to_numeric(data["Close"], errors="coerce").to_numpy(dtype=float)
    high = pd.to_numeric(data["High"], errors="coerce").to_numpy(dtype=float)
    low = pd.to_numeric(data["Low"], errors="coerce").to_numpy(dtype=float)
    timestamps = pd.to_datetime(data["ts"], utc=True)
    symbols = data["symbol"].astype(str).to_numpy() if "symbol" in data.columns else np.asarray(["NQ"] * len(data))
    max_horizon = max(horizons)
    for feature in market_features:
        indexes = np.flatnonzero(feature.signal.fillna(False).to_numpy(dtype=bool))
        indexes = _dedupe_indexes(indexes, min_gap_minutes)
        indexes = indexes[indexes + max_horizon < len(data)]
        if len(indexes) == 0:
            continue
        for index in indexes:
            if symbols[index + max_horizon] != symbols[index]:
                continue
            event_close = close[index]
            if not np.isfinite(event_close):
                continue
            row: dict[str, Any] = {
                "feature_id": feature.feature_id,
                "family": feature.family,
                "direction_hint": feature.direction_hint,
                "description": feature.description,
                "event_index": int(index),
                "event_ts": str(timestamps.iloc[index]),
                "symbol": str(symbols[index]),
                "event_close": float(event_close),
            }
            direction = 1 if feature.direction_hint == "long" else -1 if feature.direction_hint == "short" else 0
            for horizon in horizons:
                end = index + horizon
                forward_close = close[end]
                window_high = np.nanmax(high[index + 1 : end + 1])
                window_low = np.nanmin(low[index + 1 : end + 1])
                if direction >= 0:
                    mfe = window_high - event_close
                    mae = event_close - window_low
                    signed_close = forward_close - event_close
                else:
                    mfe = event_close - window_low
                    mae = window_high - event_close
                    signed_close = event_close - forward_close
                row[f"close_move_{horizon}m"] = float(signed_close)
                row[f"mfe_{horizon}m"] = float(mfe)
                row[f"mae_{horizon}m"] = float(mae)
            rows.append(row)
    return pd.DataFrame(rows)


def _dedupe_indexes(indexes: np.ndarray, min_gap: int) -> np.ndarray:
    if len(indexes) == 0:
        return indexes
    selected = [int(indexes[0])]
    next_allowed = int(indexes[0]) + min_gap
    for index in indexes[1:]:
        value = int(index)
        if value >= next_allowed:
            selected.append(value)
            next_allowed = value + min_gap
    return np.asarray(selected, dtype=int)


def summarize_events(events: pd.DataFrame, *, horizons: list[int], min_events: int) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for feature_id, group in events.groupby("feature_id", sort=False):
        if len(group) < min_events:
            continue
        base = group.iloc[0]
        row: dict[str, Any] = {
            "feature_id": feature_id,
            "family": base["family"],
            "direction_hint": base["direction_hint"],
            "description": base["description"],
            "events": int(len(group)),
            "first_ts": str(group["event_ts"].min()),
            "last_ts": str(group["event_ts"].max()),
        }
        score_parts = []
        for horizon in horizons:
            close_move = pd.to_numeric(group[f"close_move_{horizon}m"], errors="coerce").dropna()
            mfe = pd.to_numeric(group[f"mfe_{horizon}m"], errors="coerce").dropna()
            mae = pd.to_numeric(group[f"mae_{horizon}m"], errors="coerce").dropna()
            if close_move.empty:
                continue
            median_close = float(close_move.median())
            mean_close = float(close_move.mean())
            hit_10 = float((mfe >= 10.0).mean()) if len(mfe) else 0.0
            hit_20 = float((mfe >= 20.0).mean()) if len(mfe) else 0.0
            adverse_10 = float((mae >= 10.0).mean()) if len(mae) else 0.0
            favorable_share = float((close_move > 0).mean())
            payoff_path = float(mfe.median() / max(mae.median(), 1.0)) if len(mfe) and len(mae) else 0.0
            row[f"mean_close_move_{horizon}m"] = mean_close
            row[f"median_close_move_{horizon}m"] = median_close
            row[f"favorable_close_rate_{horizon}m"] = favorable_share
            row[f"median_mfe_{horizon}m"] = float(mfe.median()) if len(mfe) else 0.0
            row[f"median_mae_{horizon}m"] = float(mae.median()) if len(mae) else 0.0
            row[f"hit_10pt_rate_{horizon}m"] = hit_10
            row[f"hit_20pt_rate_{horizon}m"] = hit_20
            row[f"adverse_10pt_rate_{horizon}m"] = adverse_10
            row[f"path_payoff_{horizon}m"] = payoff_path
            score_parts.append(
                favorable_share * 3.0
                + min(max(mean_close, -20.0), 20.0) / 10.0
                + hit_10 * 2.0
                + hit_20 * 2.0
                + min(payoff_path, 3.0)
                - adverse_10
            )
        row["opportunity_score"] = float(np.mean(score_parts)) if score_parts else 0.0
        rows.append(row)
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(
        ["opportunity_score", "events"],
        ascending=[False, False],
    ).reset_index(drop=True)


def invoke_feature_llm(
    summary: pd.DataFrame,
    args: argparse.Namespace,
    *,
    memory_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    if args.no_llm or summary.empty:
        return fallback_feature_analysis(summary, args, memory_notes=memory_notes)
    load_project_env()
    provider = args.provider or DEFAULT_CONFIG["llm_provider"]
    model = args.model or DEFAULT_CONFIG["deep_think_llm"]
    base_url = args.backend_url or DEFAULT_CONFIG.get("backend_url")
    prompt = build_feature_prompt(summary.head(args.llm_top_n), args, memory_notes=memory_notes)
    try:
        if provider.lower() == "aicode":
            content = invoke_aicode_streaming_json(prompt, model=model, base_url=base_url, timeout=args.llm_timeout)
        else:
            llm = create_llm_client(provider, model, base_url=base_url, timeout=args.llm_timeout, streaming=False).get_llm()
            response = llm.invoke(prompt)
            content = str(getattr(response, "content", response))
        payload = extract_json_object(content)
        payload.setdefault("provider", provider)
        payload.setdefault("model", model)
        payload.setdefault("status", "parsed")
        payload["raw_response"] = content
        return payload
    except Exception as exc:
        payload = fallback_feature_analysis(summary, args, memory_notes=memory_notes)
        payload["status"] = "fallback_after_error"
        payload["error"] = str(exc) or exc.__class__.__name__
        return payload


def build_feature_prompt(summary: pd.DataFrame, args: argparse.Namespace, *, memory_notes: list[dict[str, Any]]) -> str:
    payload = summary.replace([np.inf, -np.inf], np.nan).where(pd.notna(summary), None).to_dict(orient="records")
    return (
        "你是NQ 1分钟行情结构研究员。现在不要先追求胜率>53%或盈亏比>1，"
        "任务是从2020年之后的1分钟bar事件统计里识别哪些行情特征值得交易研究。"
        "请重点判断趋势起点、快速下杀反抽、快速上涨回落、跌不动反弹、涨不动下跌、W底、M顶、量价不匹配等结构。"
        "先描述可交易现象，再建议适配的策略类型、入场确认、止损位置、出场逻辑、失效条件和下一步回测优先级。"
        "不要编造统计表之外的结果。\n\n"
        "Return ONLY JSON with keys: feature_rankings, strategy_hypotheses, risk_principles, next_research_steps, summary. "
        "feature_rankings must be a list of objects with feature_id, tradeability, reason, preferred_strategy, confirmation, invalidation. "
        "strategy_hypotheses must include setup, direction, entry_logic, stop_logic, exit_logic, filters_to_test. "
        "risk_principles must be short actionable rules.\n\n"
        f"CONFIG: {json.dumps(vars(args), ensure_ascii=False, sort_keys=True, default=str)}\n\n"
        f"MEMORY_NOTES: {json.dumps(memory_notes, ensure_ascii=False, sort_keys=True, default=str)}\n\n"
        f"EVENT_SUMMARY_ROWS: {json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)}"
    )


def fallback_feature_analysis(
    summary: pd.DataFrame,
    args: argparse.Namespace,
    *,
    memory_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    rankings = []
    for _, row in summary.head(args.llm_top_n).iterrows():
        feature_id = str(row["feature_id"])
        family = str(row["family"])
        direction = str(row["direction_hint"])
        rankings.append(
            {
                "feature_id": feature_id,
                "tradeability": "research",
                "reason": (
                    f"{family} {direction} event has {int(row['events'])} samples and opportunity_score "
                    f"{float(row['opportunity_score']):.3f}; use as a hypothesis source, not as a complete strategy."
                ),
                "preferred_strategy": strategy_for_family(family),
                "confirmation": confirmation_for_family(family, direction),
                "invalidation": invalidation_for_family(family, direction),
            }
        )
    return {
        "provider": "rule",
        "model": "feature_fallback",
        "status": "fallback",
        "feature_rankings": rankings,
        "strategy_hypotheses": [
            {
                "setup": item["feature_id"],
                "direction": summary.loc[summary["feature_id"].eq(item["feature_id"]), "direction_hint"].iloc[0],
                "entry_logic": item["confirmation"],
                "stop_logic": item["invalidation"],
                "exit_logic": "Compare fixed R, structure target, and time stop variants after event-level opportunity is confirmed.",
                "filters_to_test": ["session", "relative_volume_20", "session_vwap_distance_atr", "adx_14", "cmf_20", "mfi_14"],
            }
            for item in rankings[:8]
        ],
        "risk_principles": [
            "先验证事件后的路径分布，再为该事件选择趋势跟随、反转或回归执行策略。",
            "每个结构都必须定义失效条件，失效时不补仓、不扩大止损。",
            "量价不匹配必须等待价格确认，不能只凭背离逆势入场。",
            "趋势起点优先用结构止损，快速反抽/回落优先用极值失效止损。",
        ],
        "next_research_steps": [
            "For top features, run bracket and time-stop strategy grids separately by family.",
            "Validate whether MFE arrives before MAE enough to support realistic entries.",
            "Split event statistics by session and volatility regime before promoting a setup.",
        ],
        "summary": "Fallback analysis ranked event families by path opportunity; LLM unavailable or disabled.",
        "memory_note_count": len(memory_notes),
    }


def strategy_for_family(family: str) -> str:
    if family in {
        "trend_start",
        "trend_pullback",
        "tradingview_trend",
        "tradingview_pullback",
        "range_breakout",
        "smc_bos_continuation",
        "smc_failed_choch_continuation",
        "smc_displacement_pullback",
    }:
        return "breakout/continuation with structure stop and trailing/time exit"
    if family in {
        "exhaustion_reversal",
        "absorption",
        "double_bottom",
        "double_top",
        "reclaim",
        "base_reclaim",
        "liquidity_reversal",
        "ict_order_flow_shift",
        "ict_order_flow_shift_entry",
        "ict_order_block_retest",
        "smc_liquidity_macd_reversal",
        "tradingview_momentum",
        "tradingview_oscillator",
    }:
        return "confirmation reversal with extreme-based stop and VWAP/range target"
    if family in {"volume_price_mismatch", "tradingview_volume_price"}:
        return "confirmation-first reversal or failed-continuation strategy"
    return "family-specific bracket and time-stop comparison"


def confirmation_for_family(family: str, direction: str) -> str:
    side = "above" if direction == "long" else "below"
    if family in {"trend_start", "tradingview_trend", "range_breakout"}:
        return f"Enter only after the next bar holds {side} the displacement midpoint or breaks continuation in the hinted direction."
    if family == "smc_bos_continuation":
        return f"Require repeated BOS in the same direction, then enter only after a controlled pullback breaks {side} the local pullback range."
    if family == "smc_failed_choch_continuation":
        return f"Treat the CHoCH as a trap only after price fails to accept beyond it and breaks {side} the post-CHoCH range."
    if family == "smc_displacement_pullback":
        return "Wait for the first pullback into the displacement/FVG/order-block area, then require rejection back with momentum in the trend direction."
    if family in {"trend_pullback", "tradingview_pullback"}:
        return f"Require the pullback to hold VWAP or VWMA/TEMA alignment, then enter after a micro break {side} the pullback range."
    if family in {"volume_price_mismatch", "tradingview_volume_price"}:
        return "Wait for price to reclaim/lose VWAP or break the prior micro swing in the hinted direction."
    if family == "liquidity_reversal":
        return "Require the sweep to fail back inside the prior range, then enter after midpoint/VWAP confirmation."
    if family == "smc_liquidity_macd_reversal":
        return "Require EQH/EQL or sweep rejection plus MACD histogram repair/fade, then enter after the sweep candle midpoint is reclaimed/rejected."
    if family == "ict_order_flow_shift":
        return "Do not chase the displacement; wait for the FVG/order-block retest in the correct premium/discount half."
    if family in {"ict_order_flow_shift_entry", "ict_order_block_retest"}:
        return "Enter on the FVG or order-block retest only after price rejects back in the shifted order-flow direction."
    if family == "base_reclaim":
        return "Require a local base break/reclaim after failed continuation, with the base low/high defining invalidation."
    if family in {"tradingview_momentum", "tradingview_oscillator"}:
        return "Require oscillator repair/fade to be followed by price reclaim/reject of the event midpoint or VWAP."
    if family in {"double_bottom", "double_top"}:
        return "Require neckline or midpoint reclaim/reject; avoid entering directly at the second touch without confirmation."
    return "Require follow-through close or failed retest in the hinted direction."


def invalidation_for_family(family: str, direction: str) -> str:
    if family in {
        "trend_start",
        "trend_pullback",
        "tradingview_trend",
        "tradingview_pullback",
        "range_breakout",
        "smc_bos_continuation",
        "smc_failed_choch_continuation",
        "smc_displacement_pullback",
    }:
        return "Invalidate if price closes back through the breakout/displacement origin or volume expansion reverses against the trade."
    if family in {"liquidity_reversal", "smc_liquidity_macd_reversal"}:
        return "Invalidate beyond the sweep extreme; do not keep the trade if price accepts outside the swept level."
    if family in {"ict_order_flow_shift", "ict_order_flow_shift_entry", "ict_order_block_retest"}:
        return "Invalidate beyond the liquidity-sweep extreme or beyond the candle that created the traded FVG/order block."
    if family == "base_reclaim":
        return "Invalidate if price breaks back through the local base after the reclaim/reject confirmation."
    if family in {"tradingview_momentum", "tradingview_oscillator"}:
        return "Invalidate if the oscillator signal reverses and price cannot hold the event midpoint or VWAP within the test horizon."
    if direction == "long":
        return "Invalidate below the event low or if rebound cannot reclaim VWAP/midpoint within the chosen time window."
    return "Invalidate above the event high or if fade cannot lose VWAP/midpoint within the chosen time window."


def load_memory_notes(memory_db: Path, limit: int) -> list[dict[str, Any]]:
    if not memory_db.exists():
        return []
    memory = EvolutionMemory(memory_db)
    try:
        return memory.active_notes(limit)
    finally:
        memory.close()


def record_feature_memory(memory_db: Path, summary: pd.DataFrame, llm_payload: dict[str, Any], args: argparse.Namespace) -> None:
    memory = EvolutionMemory(memory_db)
    try:
        now = utc_now()
        rankings = llm_payload.get("feature_rankings", [])
        ranking_by_feature = {
            str(item.get("feature_id")): item
            for item in rankings
            if isinstance(item, dict) and item.get("feature_id")
        }
        for _, row in summary.head(args.memory_top_n).iterrows():
            feature_id = str(row["feature_id"])
            ranking = ranking_by_feature.get(feature_id, {})
            signature = "mfeat_" + hashlib.sha1(feature_id.encode("utf-8")).hexdigest()[:16]
            note_id = f"note_{signature}_market_feature_{int(row['events'])}"
            lesson = (
                f"Market feature {feature_id}: family={row['family']}, direction={row['direction_hint']}, "
                f"events={int(row['events'])}, opportunity_score={float(row['opportunity_score']):.3f}. "
                f"LLM/readout tradeability={ranking.get('tradeability', 'research')}; "
                f"preferred_strategy={ranking.get('preferred_strategy', strategy_for_family(str(row['family'])))}."
            )
            memory.connection.execute(
                """
                INSERT OR REPLACE INTO experience_notes (
                    note_id, rule_signature, note_type, regime, applies_when, avoid_when,
                    lesson, evidence_summary, confidence, status, supersedes_note_id,
                    created_at, last_used_at, use_count
                ) VALUES (?, ?, 'market_feature', NULL, ?, ?, ?, ?, ?, 'active', NULL, ?, NULL, 0)
                """,
                (
                    note_id,
                    signature,
                    str(row["description"]),
                    str(ranking.get("invalidation", invalidation_for_family(str(row["family"]), str(row["direction_hint"])))),
                    lesson,
                    json.dumps(row.replace([np.inf, -np.inf], np.nan).dropna().to_dict(), sort_keys=True, default=str),
                    min(1.0, max(0.05, float(row["events"]) / 1000.0)),
                    now,
                ),
            )
        memory.limit_active_notes()
        memory.connection.commit()
    finally:
        memory.close()


def write_html_report(
    path: Path,
    summary: pd.DataFrame,
    llm_payload: dict[str, Any],
    args: argparse.Namespace,
    *,
    feature_rows: int,
    event_rows: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    top_rows = summary.head(args.top_n).copy()
    ranking_html = _html_table(top_rows)
    llm_html = _json_block(llm_payload)
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>NQ 2020+ Tradeable Market Feature Discovery</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #172026; }}
    h1, h2 {{ margin: 0 0 12px; }}
    section {{ margin: 22px 0; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 6px 8px; vertical-align: top; }}
    th {{ background: #f6f8fa; text-align: left; position: sticky; top: 0; }}
    .metric {{ display: inline-block; margin: 0 14px 10px 0; padding: 8px 10px; background: #f6f8fa; border: 1px solid #d8dee4; border-radius: 6px; }}
    pre {{ white-space: pre-wrap; background: #0f1720; color: #e6edf3; padding: 14px; border-radius: 6px; overflow: auto; }}
    .muted {{ color: #59636e; }}
  </style>
</head>
<body>
  <h1>NQ 2020+ 可交易行情特征发现</h1>
  <p class="muted">先发现行情结构与路径机会，再为结构匹配策略。当前不使用 53% 胜率或盈亏比硬门槛作为筛选条件。</p>
  <section>
    <span class="metric">Features rows: {feature_rows:,}</span>
    <span class="metric">Event rows: {event_rows:,}</span>
    <span class="metric">Summary rows: {len(summary):,}</span>
    <span class="metric">Window: {args.start_date} to {args.end_date}</span>
  </section>
  <section>
    <h2>Top Event Path Statistics</h2>
    {ranking_html}
  </section>
  <section>
    <h2>LLM / Rule Analysis</h2>
    {llm_html}
  </section>
</body>
</html>
""",
        encoding="utf-8",
    )


def _html_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    display = frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.4f}")
    return display.to_html(index=False, escape=True)


def _json_block(payload: dict[str, Any]) -> str:
    return "<pre>" + json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "</pre>"


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover tradeable NQ 1-minute market features from 2020+ bars.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--bars-cache", default=".tmp/nq-market-feature-bars-2020-cache.pkl")
    parser.add_argument("--features-cache", default=".tmp/nq-market-feature-features-2020-cache.pkl")
    parser.add_argument("--source-csv")
    parser.add_argument("--source-zip")
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--rebuild-features", action="store_true")
    parser.add_argument("--feature-ids", nargs="+", help="Optional explicit market feature ids to include.")
    parser.add_argument("--horizons", type=int, nargs="+", default=[5, 15, 30, 60, 120])
    parser.add_argument("--min-gap-minutes", type=int, default=15)
    parser.add_argument("--min-events", type=int, default=30)
    parser.add_argument("--events-output", default=".tmp/nq-market-feature-events-2020.csv")
    parser.add_argument("--summary-output", default=".tmp/nq-market-feature-summary-2020.csv")
    parser.add_argument("--llm-output", default=".tmp/nq-market-feature-llm-analysis-2020.json")
    parser.add_argument("--report", default="reports/NQ-market-feature-discovery-2020.html")
    parser.add_argument("--memory-db", default=".tmp/nq-trading-evolution.sqlite")
    parser.add_argument("--record-memory", action="store_true")
    parser.add_argument("--memory-top-n", type=int, default=30)
    parser.add_argument("--memory-note-limit", type=int, default=20)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--backend-url")
    parser.add_argument("--llm-timeout", type=float, default=90.0)
    parser.add_argument("--llm-top-n", type=int, default=30)
    parser.add_argument("--top-n", type=int, default=50)
    args = parser.parse_args()

    features = load_or_prepare_features(args)
    market_features = build_market_features(features)
    if args.feature_ids:
        requested = list(dict.fromkeys(args.feature_ids))
        available = {feature.feature_id: feature for feature in market_features}
        missing = sorted(set(requested) - set(available))
        if missing:
            raise ValueError(f"Feature ids not available: {missing}")
        market_features = [available[feature_id] for feature_id in requested]
    events = event_path_rows(
        features,
        market_features,
        horizons=args.horizons,
        min_gap_minutes=args.min_gap_minutes,
    )
    summary = summarize_events(events, horizons=args.horizons, min_events=args.min_events)
    memory_db = Path(args.memory_db)
    memory_notes = load_memory_notes(memory_db, args.memory_note_limit)
    llm_payload = invoke_feature_llm(summary, args, memory_notes=memory_notes)

    for output, frame in [(Path(args.events_output), events), (Path(args.summary_output), summary)]:
        output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output, index=False)
    llm_output = Path(args.llm_output)
    llm_output.parent.mkdir(parents=True, exist_ok=True)
    llm_output.write_text(json.dumps(llm_payload, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")
    write_html_report(Path(args.report), summary, llm_payload, args, feature_rows=len(features), event_rows=len(events))
    if args.record_memory:
        record_feature_memory(memory_db, summary, llm_payload, args)

    result = {
        "feature_rows": int(len(features)),
        "market_features": int(len(market_features)),
        "event_rows": int(len(events)),
        "summary_rows": int(len(summary)),
        "events_output": args.events_output,
        "summary_output": args.summary_output,
        "llm_output": args.llm_output,
        "report": args.report,
        "memory_db": args.memory_db if args.record_memory else "",
        "top_feature": summary.iloc[0].to_dict() if not summary.empty else None,
        "llm_status": llm_payload.get("status", "unknown"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
