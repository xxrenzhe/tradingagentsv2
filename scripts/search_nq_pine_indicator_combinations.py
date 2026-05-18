from __future__ import annotations

import argparse
import hashlib
import itertools
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from backtest_nq_boundary_lightglow_strategy import (  # noqa: E402
    BoundaryLightglowConfig,
    _structure_target,
    add_features,
    pine_default_costs,
    summarize,
)
from search_nq_bar_2r_walkforward import load_continuous_nq_bars  # noqa: E402
from tradingagents.backtesting.short_patterns import BacktestCosts  # noqa: E402


LATEST_CSV = ROOT_DIR / "data/raw/databento/glbx-mdp3-20100606-20260427.ohlcv-1m.csv"
LIGHTGLOW_PINE = ROOT_DIR / "pine_scripts/nq_lightglow_timecell_composite_paper_readiness.pine"
MACD_PINE = ROOT_DIR / "pine_scripts/CM_MacD_Ult_MTF.pine"

FAMILY_DIRECTIONS: dict[str, int] = {
    "bottom_breakdown_short": -1,
    "top_breakout_long": 1,
    "bottom_reclaim_long": 1,
    "top_reject_short": -1,
    "trend_ignition_long": 1,
    "trend_ignition_short": -1,
    "trend_pullback_long": 1,
    "trend_pullback_short": -1,
    "trend_transition_long": 1,
    "trend_transition_short": -1,
    "reversal_impulse_long": 1,
    "reversal_impulse_short": -1,
    "fast_reversal_long": 1,
    "fast_reversal_short": -1,
    "phase_up_breakout_long": 1,
    "phase_up_pullback_long": 1,
    "phase_down_breakdown_short": -1,
    "phase_down_pullback_short": -1,
    "trend_pullback_short_asia_europe": -1,
    "trend_transition_short_asia_rth": -1,
    "trend_transition_short_asia": -1,
    "smc_discount_choch_long": 1,
    "smc_premium_choch_short": -1,
    "smc_bos_fvg_long": 1,
    "smc_bos_fvg_short": -1,
    "smc_ob_retest_long": 1,
    "smc_ob_retest_short": -1,
    "smc_trend_transition_long": 1,
    "smc_trend_transition_short": -1,
    "smc_trend_pullback_long": 1,
    "smc_trend_pullback_short": -1,
}
FAMILY_TARGET_BASE: dict[str, str] = {
    "trend_pullback_short_asia_europe": "trend_pullback_short",
    "trend_transition_short_asia_rth": "trend_transition_short",
    "trend_transition_short_asia": "trend_transition_short",
    "smc_discount_choch_long": "bottom_reclaim_long",
    "smc_premium_choch_short": "top_reject_short",
    "smc_bos_fvg_long": "trend_transition_long",
    "smc_bos_fvg_short": "trend_transition_short",
    "smc_ob_retest_long": "trend_pullback_long",
    "smc_ob_retest_short": "trend_pullback_short",
    "smc_trend_transition_long": "trend_transition_long",
    "smc_trend_transition_short": "trend_transition_short",
    "smc_trend_pullback_long": "trend_pullback_long",
    "smc_trend_pullback_short": "trend_pullback_short",
}

PINE_DEFAULT_FAMILIES = ("top_breakout_long", "trend_ignition_long")
ALL_LIGHTGLOW_BASE_FAMILIES = (
    "bottom_breakdown_short",
    "top_breakout_long",
    "bottom_reclaim_long",
    "top_reject_short",
    "trend_ignition_long",
    "trend_ignition_short",
    "trend_pullback_long",
    "trend_pullback_short",
    "trend_transition_long",
    "trend_transition_short",
    "reversal_impulse_long",
    "reversal_impulse_short",
    "fast_reversal_long",
    "fast_reversal_short",
    "phase_up_breakout_long",
    "phase_up_pullback_long",
    "phase_down_breakdown_short",
    "phase_down_pullback_short",
)
MIN_ROBUST_TRADES = 50


@dataclass(frozen=True)
class MacdConfig:
    timeframe_minutes: int = 1
    fast_length: int = 12
    slow_length: int = 26
    signal_length: int = 9


@dataclass(frozen=True)
class ComboSpec:
    name: str
    families: tuple[str, ...]
    macd_filter: str
    macd_timeframe: int
    stop_atr_buffer: float
    target_r: float
    max_hold_bars: int
    use_risk_controls: bool
    entry_mode: str = "next_open"
    min_structure_rr: float = 0.0
    entry_wait_bars: int = 0
    risk_cap_atr: float = 0.0
    max_target_r: float = 0.0
    trail_start_r: float = 0.0
    trail_atr_mult: float = 0.0
    breakeven_trigger_r: float = 0.0
    min_target_r: float = 0.0
    time_stop_bars: int = 0
    time_stop_min_r: float = 0.0
    giveback_start_r: float = 0.0
    giveback_keep_r: float = 0.0
    avoid_loss_clusters: bool = False
    target_runner: bool = False
    adverse_reversal_exit: bool = False
    adverse_exit_max_r: float = 999.0
    target_runner_families: tuple[str, ...] = ()
    entry_quality_filter: str = "none"


STRUCTURE_CONTINUATION_BASES = {
    "top_breakout_long",
    "bottom_breakdown_short",
    "trend_ignition_long",
    "trend_ignition_short",
    "trend_pullback_long",
    "trend_pullback_short",
    "trend_transition_long",
    "trend_transition_short",
    "phase_up_breakout_long",
    "phase_up_pullback_long",
    "phase_down_breakdown_short",
    "phase_down_pullback_short",
    "smc_bos_fvg_long",
    "smc_bos_fvg_short",
    "smc_ob_retest_long",
    "smc_ob_retest_short",
    "smc_trend_transition_long",
    "smc_trend_transition_short",
    "smc_trend_pullback_long",
    "smc_trend_pullback_short",
}
STRUCTURE_REVERSAL_BASES = {
    "bottom_reclaim_long",
    "top_reject_short",
    "fast_reversal_long",
    "fast_reversal_short",
    "reversal_impulse_long",
    "reversal_impulse_short",
    "smc_discount_choch_long",
    "smc_premium_choch_short",
}


def latest_databento_window(csv_path: Path = LATEST_CSV, *, days: int = 31) -> tuple[str, str, pd.Timestamp]:
    last_line = csv_path.read_bytes().rstrip().splitlines()[-1].decode("utf-8")
    latest_ts = pd.Timestamp(last_line.split(",", 1)[0], tz="UTC")
    start_ts = latest_ts - pd.Timedelta(days=days)
    end_ts = latest_ts + pd.Timedelta(minutes=1)
    return start_ts.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d"), latest_ts


def load_recent_nq_bars(args: argparse.Namespace) -> pd.DataFrame:
    loader_args = argparse.Namespace(
        start_date=args.start_date,
        end_date=args.end_date,
        cache=args.cache,
        chunk_size=args.chunk_size,
        min_volume=args.min_volume,
    )
    return load_continuous_nq_bars(loader_args).sort_values("ts").reset_index(drop=True)


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def add_macd_features(frame: pd.DataFrame, config: MacdConfig) -> pd.DataFrame:
    output = frame.copy()
    close = pd.to_numeric(output["Close"], errors="coerce")
    if config.timeframe_minutes <= 1:
        source = pd.DataFrame({"ts": output["ts"], "close": close})
        macd_index = source.index
    else:
        source = (
            pd.DataFrame({"ts": output["ts"], "close": close})
            .set_index("ts")
            .resample(f"{config.timeframe_minutes}min", label="right", closed="right")
            .last()
            .dropna()
            .reset_index()
        )
        macd_index = source.index

    fast = _ema(source["close"], config.fast_length)
    slow = _ema(source["close"], config.slow_length)
    macd = fast - slow
    signal = macd.rolling(config.signal_length, min_periods=config.signal_length).mean()
    hist = macd - signal
    macd_frame = pd.DataFrame(
        {
            "ts": source["ts"],
            "macd": macd,
            "macd_signal": signal,
            "macd_hist": hist,
        },
        index=macd_index,
    )
    if config.timeframe_minutes <= 1:
        aligned = macd_frame[["macd", "macd_signal", "macd_hist"]].reset_index(drop=True)
    else:
        aligned = pd.merge_asof(
            output[["ts"]].sort_values("ts"),
            macd_frame.sort_values("ts"),
            on="ts",
            direction="backward",
        )[["macd", "macd_signal", "macd_hist"]]

    for column in aligned.columns:
        output[f"mtf{config.timeframe_minutes}_{column}"] = aligned[column].to_numpy()
    prefix = f"mtf{config.timeframe_minutes}"
    hist_col = output[f"{prefix}_macd_hist"]
    macd_col = output[f"{prefix}_macd"]
    signal_col = output[f"{prefix}_macd_signal"]
    output[f"{prefix}_hist_up"] = hist_col > hist_col.shift(1)
    output[f"{prefix}_hist_delta"] = hist_col - hist_col.shift(1)
    output[f"{prefix}_hist_above_zero"] = hist_col > 0
    output[f"{prefix}_hist_below_zero"] = hist_col <= 0
    output[f"{prefix}_macd_above_signal"] = macd_col >= signal_col
    output[f"{prefix}_macd_below_signal"] = macd_col < signal_col
    output[f"{prefix}_bull_cross"] = (macd_col >= signal_col) & (macd_col.shift(1) < signal_col.shift(1))
    output[f"{prefix}_bear_cross"] = (macd_col < signal_col) & (macd_col.shift(1) >= signal_col.shift(1))
    return output


def add_all_lightglow_signal_columns(frame: pd.DataFrame, config: BoundaryLightglowConfig) -> pd.DataFrame:
    output = frame.copy()
    close = output["Close"]
    open_ = output["Open"]
    high = output["High"]
    low = output["Low"]
    atr = output["atr"]
    ema20 = output["ema20"]
    ema60 = output["ema60"]
    ema200 = output["ema200"]
    momentum = output["momentum"]
    body_atr = output["body_atr"]
    volume_z = output["volume_z"]

    discount_reclaim = (
        output["sweep_below_range"]
        & (close > open_)
        & (close > output["range_low"])
        & (momentum > momentum.shift(1))
        & (body_atr >= config.body_atr_threshold * 0.5)
    )
    breakdown = (
        output["accepted_below_range"]
        & (close < open_)
        & (ema20 < ema60)
        & (ema60 <= ema200)
        & (momentum < 0)
        & (volume_z >= 0)
        & (body_atr >= config.body_atr_threshold)
    )
    premium_reject = (
        output["sweep_above_range"]
        & (close < open_)
        & (close < output["range_high"])
        & (momentum < momentum.shift(1))
        & (body_atr >= config.body_atr_threshold * 0.5)
    )
    breakout = (
        output["accepted_above_range"]
        & (close > open_)
        & (ema20 > ema60)
        & (ema60 >= ema200)
        & (momentum > 0)
        & (volume_z >= 0)
        & (body_atr >= config.body_atr_threshold)
    )

    ema_reclaim_long = (close > ema20) & (close > ema60) & (close.shift(1) <= ema20.shift(1)) & (ema20 >= ema20.shift(1))
    ema_reject_short = (close < ema20) & (close < ema60) & (close.shift(1) >= ema20.shift(1)) & (ema20 <= ema20.shift(1))
    trend_ignition_long = (
        output["compressed_base"]
        & (output["range_pos"] <= config.ignition_range_pos_long_max)
        & (close > output["micro_breakout_high"])
        & ema_reclaim_long
        & (momentum > 0)
        & (volume_z >= config.ignition_volume_z_min)
        & (body_atr >= config.ignition_body_atr_min)
    )
    trend_ignition_short = (
        output["compressed_base"]
        & (output["range_pos"] >= config.ignition_range_pos_short_min)
        & (close < output["micro_breakdown_low"])
        & ema_reject_short
        & (momentum < 0)
        & (volume_z >= config.ignition_volume_z_min)
        & (body_atr >= config.ignition_body_atr_min)
    )
    trend_up = (ema20 > ema60) & (ema60 > ema200) & (ema20 > ema20.shift(config.trend_slope_lookback)) & (close > ema60)
    trend_down = (ema20 < ema60) & (ema60 < ema200) & (ema20 < ema20.shift(config.trend_slope_lookback)) & (close < ema60)
    pullback_depth_long = (high.rolling(config.pullback_lookback, min_periods=config.pullback_lookback).max().shift(1) - low) / atr.replace(0, np.nan)
    pullback_depth_short = (high - low.rolling(config.pullback_lookback, min_periods=config.pullback_lookback).min().shift(1)) / atr.replace(0, np.nan)
    long_pullback_held = (low <= ema20 + atr * config.pullback_ema_atr_buffer) & (close > ema20) & (close > open_) & (low > ema60 - atr * config.pullback_ema_atr_buffer)
    short_pullback_held = (high >= ema20 - atr * config.pullback_ema_atr_buffer) & (close < ema20) & (high < ema60 + atr * config.pullback_ema_atr_buffer)
    trend_pullback_long = trend_up & long_pullback_held & (close > output["micro_breakout_high"]) & (momentum > 0) & (volume_z >= config.continuation_volume_z_min) & (pullback_depth_long <= config.pullback_atr_max)
    trend_pullback_short = trend_down & short_pullback_held & (close < output["micro_breakdown_low"]) & (momentum < 0) & (volume_z >= config.continuation_volume_z_min) & (pullback_depth_short <= config.pullback_atr_max)
    ema_bear_transition = (close < ema20) & (close < ema60) & (ema20 < ema20.shift(1)) & (close < low.rolling(config.transition_lookback, min_periods=config.transition_lookback).min().shift(1))
    ema_bull_transition = (close > ema20) & (close > ema60) & (ema20 > ema20.shift(1)) & (close > high.rolling(config.transition_lookback, min_periods=config.transition_lookback).max().shift(1))
    trend_transition_short = ema_bear_transition & (momentum < 0) & (volume_z >= config.transition_volume_z_min) & (body_atr >= config.transition_body_atr_min)
    trend_transition_long = ema_bull_transition & (momentum > 0) & (volume_z >= config.transition_volume_z_min) & (body_atr >= config.transition_body_atr_min)
    close_location = (close - low) / (high - low).replace(0, np.nan)
    lower_wick_ratio = (np.minimum(open_, close) - low) / (high - low).replace(0, np.nan)
    upper_wick_ratio = (high - np.maximum(open_, close)) / (high - low).replace(0, np.nan)
    fast_reversal_long = (
        output["sweep_below_range"]
        & (close > output["range_low"])
        & (close_location >= 0.62)
        & (lower_wick_ratio >= 0.35)
        & (close > close.shift(1))
        & (output["body_atr"] >= 0.20)
    )
    fast_reversal_short = (
        output["sweep_above_range"]
        & (close < output["range_high"])
        & (close_location <= 0.38)
        & (upper_wick_ratio >= 0.35)
        & (close < close.shift(1))
        & (output["body_atr"] >= 0.20)
    )
    ema20_slope = ema20 - ema20.shift(5)
    ema60_slope = ema60 - ema60.shift(12)
    phase_up = (
        (close > ema20)
        & (close > ema60)
        & ((ema20 >= ema60) | ((ema20_slope > 0) & (ema60_slope >= 0)))
        & (ema20_slope > 0)
    )
    phase_down = (
        (close < ema20)
        & (close < ema60)
        & ((ema20 <= ema60) | ((ema20_slope < 0) & (ema60_slope <= 0)))
        & (ema20_slope < 0)
    )
    micro_high = high.rolling(3, min_periods=3).max().shift(1)
    micro_low = low.rolling(3, min_periods=3).min().shift(1)
    phase_up_breakout_long = (
        phase_up
        & (close > output["micro_breakout_high"])
        & (close > micro_high)
        & (close > open_)
        & (momentum > momentum.shift(1))
        & (body_atr >= config.body_atr_threshold * 0.45)
    )
    phase_down_breakdown_short = (
        phase_down
        & (close < output["micro_breakdown_low"])
        & (close < micro_low)
        & (close < open_)
        & (momentum < momentum.shift(1))
        & (body_atr >= config.body_atr_threshold * 0.45)
    )
    phase_up_pullback_long = (
        phase_up
        & (low <= ema20 + atr * config.pullback_ema_atr_buffer)
        & (low >= ema60 - atr * config.pullback_ema_atr_buffer * 1.4)
        & (close > ema20)
        & (close > high.shift(1))
        & (close > open_)
        & (momentum > momentum.shift(1))
        & (body_atr >= 0.18)
    )
    phase_down_pullback_short = (
        phase_down
        & (high >= ema20 - atr * config.pullback_ema_atr_buffer)
        & (high <= ema60 + atr * config.pullback_ema_atr_buffer * 1.4)
        & (close < ema20)
        & (close < low.shift(1))
        & (close < open_)
        & (momentum < momentum.shift(1))
        & (body_atr >= 0.18)
    )
    internal_high = high.rolling(10, min_periods=10).max().shift(1)
    internal_low = low.rolling(10, min_periods=10).min().shift(1)
    swing_high = high.rolling(50, min_periods=50).max().shift(1)
    swing_low = low.rolling(50, min_periods=50).min().shift(1)
    bullish_choch = (close > internal_high) & (close.shift(1) <= internal_high.shift(1))
    bearish_choch = (close < internal_low) & (close.shift(1) >= internal_low.shift(1))
    bullish_bos = (close > swing_high) & (close.shift(1) <= swing_high.shift(1))
    bearish_bos = (close < swing_low) & (close.shift(1) >= swing_low.shift(1))
    bullish_fvg = low > high.shift(2)
    bearish_fvg = high < low.shift(2)
    recent_bullish_fvg = bullish_fvg.rolling(5, min_periods=1).max().astype(bool)
    recent_bearish_fvg = bearish_fvg.rolling(5, min_periods=1).max().astype(bool)
    last_bearish_high = high.where(close < open_).ffill().shift(1)
    last_bearish_low = low.where(close < open_).ffill().shift(1)
    last_bullish_high = high.where(close > open_).ffill().shift(1)
    last_bullish_low = low.where(close > open_).ffill().shift(1)
    discount_zone = output["range_pos"] <= 0.35
    premium_zone = output["range_pos"] >= 0.65
    bullish_ob_retest = (
        trend_up
        & (low <= last_bearish_high)
        & (low >= last_bearish_low - atr * 0.30)
        & (close > open_)
        & (close > ema20)
        & (close_location >= 0.55)
    )
    bearish_ob_retest = (
        trend_down
        & (high >= last_bullish_low)
        & (high <= last_bullish_high + atr * 0.30)
        & (close < open_)
        & (close < ema20)
        & (close_location <= 0.45)
    )
    smc_discount_choch_long = (
        (discount_zone | output["sweep_below_range"])
        & bullish_choch
        & (close_location >= 0.60)
        & (momentum > momentum.shift(1))
        & (body_atr >= 0.20)
    )
    smc_premium_choch_short = (
        (premium_zone | output["sweep_above_range"])
        & bearish_choch
        & (close_location <= 0.40)
        & (momentum < momentum.shift(1))
        & (body_atr >= 0.20)
    )
    smc_bos_fvg_long = (
        bullish_bos
        & recent_bullish_fvg
        & (close > open_)
        & (momentum > 0)
        & (volume_z >= config.transition_volume_z_min)
    )
    smc_bos_fvg_short = (
        bearish_bos
        & recent_bearish_fvg
        & (close < open_)
        & (momentum < 0)
        & (volume_z >= config.transition_volume_z_min)
    )
    reversal_impulse_long = (
        (output["range_pos"] <= config.ignition_range_pos_long_max)
        & (close > open_)
        & (close > ema20)
        & (close > output["micro_breakout_high"])
        & (momentum > 0)
        & (volume_z >= config.reversal_impulse_volume_z_min)
        & (body_atr >= config.reversal_impulse_body_atr_min)
        & (close_location >= config.reversal_impulse_close_ratio)
    )
    reversal_impulse_short = (
        (output["range_pos"] >= config.ignition_range_pos_short_min)
        & (close < open_)
        & (close < ema20)
        & (close < output["micro_breakdown_low"])
        & (momentum < 0)
        & (volume_z >= config.reversal_impulse_volume_z_min)
        & (body_atr >= config.reversal_impulse_body_atr_min)
        & (close_location <= 1.0 - config.reversal_impulse_close_ratio)
    )

    raw_conditions = {
        "bottom_breakdown_short": breakdown,
        "top_breakout_long": breakout & output["session"].eq("us_rth"),
        "bottom_reclaim_long": discount_reclaim,
        "top_reject_short": premium_reject,
        "trend_ignition_long": trend_ignition_long & output["session"].eq("europe"),
        "trend_ignition_short": trend_ignition_short,
        "trend_pullback_long": trend_pullback_long,
        "trend_pullback_short": trend_pullback_short,
        "trend_transition_long": trend_transition_long,
        "trend_transition_short": trend_transition_short,
        "reversal_impulse_long": reversal_impulse_long & output["session"].eq("us_late"),
        "reversal_impulse_short": reversal_impulse_short & output["session"].eq("us_late"),
        "fast_reversal_long": fast_reversal_long,
        "fast_reversal_short": fast_reversal_short,
        "phase_up_breakout_long": phase_up_breakout_long,
        "phase_up_pullback_long": phase_up_pullback_long,
        "phase_down_breakdown_short": phase_down_breakdown_short,
        "phase_down_pullback_short": phase_down_pullback_short,
        "trend_pullback_short_asia_europe": trend_pullback_short & output["session"].isin(["asia", "europe"]),
        "trend_transition_short_asia_rth": trend_transition_short & output["session"].isin(["asia", "us_rth"]),
        "trend_transition_short_asia": trend_transition_short & output["session"].eq("asia"),
        "smc_discount_choch_long": smc_discount_choch_long,
        "smc_premium_choch_short": smc_premium_choch_short,
        "smc_bos_fvg_long": smc_bos_fvg_long,
        "smc_bos_fvg_short": smc_bos_fvg_short,
        "smc_ob_retest_long": bullish_ob_retest,
        "smc_ob_retest_short": bearish_ob_retest,
        "smc_trend_transition_long": trend_transition_long & (bullish_bos | bullish_choch | recent_bullish_fvg),
        "smc_trend_transition_short": trend_transition_short & (bearish_bos | bearish_choch | recent_bearish_fvg),
        "smc_trend_pullback_long": trend_pullback_long & bullish_ob_retest,
        "smc_trend_pullback_short": trend_pullback_short & bearish_ob_retest,
    }
    for family, condition in raw_conditions.items():
        condition = condition.fillna(False)
        output[f"lg_{family}"] = condition & ~condition.shift(1, fill_value=False)
    output["strong_trend_continuation_long"] = (
        (close > open_)
        & (close >= high - (high - low).replace(0, np.nan) * 0.25)
        & (body_atr >= 0.80)
        & (volume_z >= 0.75)
        & (output["range_pos"] >= 0.95)
    ).fillna(False)
    output["strong_trend_continuation_short"] = (
        (close < open_)
        & (close <= low + (high - low).replace(0, np.nan) * 0.25)
        & (body_atr >= 0.80)
        & (volume_z >= 0.75)
        & (output["range_pos"] <= 0.05)
    ).fillna(False)
    output["adverse_reversal_long"] = (
        (close < open_)
        & (body_atr >= 0.85)
        & (volume_z >= 0.25)
        & ((close < low.shift(1)) | (close < output["range_high"].shift(1)))
        & (output["range_pos"] <= 0.75)
    ).fillna(False)
    output["adverse_reversal_short"] = (
        (close > open_)
        & (body_atr >= 0.85)
        & (volume_z >= 0.25)
        & ((close > high.shift(1)) | (close > output["range_low"].shift(1)))
        & (output["range_pos"] >= 0.25)
    ).fillna(False)
    return output


def _macd_filter_mask(frame: pd.DataFrame, direction: int, *, timeframe: int, filter_name: str) -> pd.Series:
    prefix = f"mtf{timeframe}"
    if filter_name == "none":
        return pd.Series(True, index=frame.index)
    if filter_name == "trend":
        return frame[f"{prefix}_macd_above_signal"] if direction > 0 else frame[f"{prefix}_macd_below_signal"]
    if filter_name == "trend_hist":
        if direction > 0:
            return frame[f"{prefix}_macd_above_signal"] & frame[f"{prefix}_hist_above_zero"]
        return frame[f"{prefix}_macd_below_signal"] & frame[f"{prefix}_hist_below_zero"]
    if filter_name == "hist_slope":
        return frame[f"{prefix}_hist_up"] if direction > 0 else ~frame[f"{prefix}_hist_up"]
    if filter_name == "hist_repair":
        hist = frame[f"{prefix}_macd_hist"]
        delta = frame[f"{prefix}_hist_delta"]
        return ((hist <= 0) & (delta > 0)) if direction > 0 else ((hist >= 0) & (delta < 0))
    if filter_name == "hist_deceleration":
        delta = frame[f"{prefix}_hist_delta"]
        return delta > 0 if direction > 0 else delta < 0
    if filter_name == "cross_recent_5":
        cross = frame[f"{prefix}_bull_cross"] if direction > 0 else frame[f"{prefix}_bear_cross"]
        return cross.rolling(5, min_periods=1).max().astype(bool)
    raise ValueError(f"unknown macd filter: {filter_name}")


def materialize_combo_frame(features: pd.DataFrame, spec: ComboSpec) -> pd.DataFrame:
    output = features.copy(deep=False)
    output["signal_family"] = ""
    output["signal_direction"] = 0
    for family in spec.families:
        direction = FAMILY_DIRECTIONS[family]
        mask = output[f"lg_{family}"].fillna(False)
        mask &= _macd_filter_mask(output, direction, timeframe=spec.macd_timeframe, filter_name=spec.macd_filter).fillna(False)
        mask &= output["signal_direction"].eq(0)
        output.loc[mask, "signal_family"] = family
        output.loc[mask, "signal_direction"] = direction
    return output


def _structure_entry_plan(
    features: pd.DataFrame,
    *,
    signal_index: int,
    direction: int,
    active_atr: float,
    min_structure_rr: float,
    wait_bars: int,
) -> dict[str, Any] | None:
    if wait_bars <= 0:
        return None
    lookback = 20
    start = max(0, signal_index - lookback + 1)
    structure_low = float(features["Low"].iloc[start : signal_index + 1].min())
    structure_high = float(features["High"].iloc[start : signal_index + 1].max())
    if not np.isfinite(structure_low) or not np.isfinite(structure_high) or structure_high <= structure_low:
        return None
    width = structure_high - structure_low
    buffer = max(active_atr * 0.15, 0.25)
    if direction > 0:
        limit_price = structure_low + width * 0.38
        structure_stop = structure_low - buffer
        structure_target = structure_high + width * 0.50
        risk = limit_price - structure_stop
        reward = structure_target - limit_price
    else:
        limit_price = structure_high - width * 0.38
        structure_stop = structure_high + buffer
        structure_target = structure_low - width * 0.50
        risk = structure_stop - limit_price
        reward = limit_price - structure_target
    if risk <= 0 or reward <= 0:
        return None
    structure_rr = reward / risk
    if structure_rr < min_structure_rr:
        return None
    for entry_index in range(signal_index + 1, min(len(features), signal_index + wait_bars + 1)):
        if direction > 0:
            if float(features["Low"].iat[entry_index]) <= limit_price:
                return {
                    "entry_index": entry_index,
                    "entry_price": float(limit_price),
                    "structure_stop": float(structure_stop),
                    "structure_target": float(structure_target),
                    "structure_rr": float(structure_rr),
                }
        elif float(features["High"].iat[entry_index]) >= limit_price:
            return {
                "entry_index": entry_index,
                "entry_price": float(limit_price),
                "structure_stop": float(structure_stop),
                "structure_target": float(structure_target),
                "structure_rr": float(structure_rr),
            }
    return None


def _structure_filter_plan(
    features: pd.DataFrame,
    *,
    signal_index: int,
    direction: int,
    entry_price: float,
    active_atr: float,
    min_structure_rr: float,
) -> dict[str, Any] | None:
    lookback = 20
    start = max(0, signal_index - lookback + 1)
    structure_low = float(features["Low"].iloc[start : signal_index + 1].min())
    structure_high = float(features["High"].iloc[start : signal_index + 1].max())
    if not np.isfinite(structure_low) or not np.isfinite(structure_high) or structure_high <= structure_low:
        return None
    width = structure_high - structure_low
    buffer = max(active_atr * 0.15, 0.25)
    if direction > 0:
        structure_stop = structure_low - buffer
        structure_target = structure_high + width * 0.50
        risk = entry_price - structure_stop
        reward = structure_target - entry_price
    else:
        structure_stop = structure_high + buffer
        structure_target = structure_low - width * 0.50
        risk = structure_stop - entry_price
        reward = entry_price - structure_target
    if risk <= 0 or reward <= 0:
        return None
    structure_rr = reward / risk
    if structure_rr < min_structure_rr:
        return None
    return {
        "entry_index": signal_index + 1,
        "entry_price": float(entry_price),
        "structure_stop": float(structure_stop),
        "structure_target": float(structure_target),
        "structure_rr": float(structure_rr),
    }


def _price_in_directional_zone(
    *,
    direction: int,
    entry_price: float,
    structure_low: float,
    structure_high: float,
    max_long_pos: float,
    min_short_pos: float,
) -> bool:
    width = structure_high - structure_low
    if not np.isfinite(width) or width <= 0:
        return False
    pos = (entry_price - structure_low) / width
    if direction > 0:
        return bool(pos <= max_long_pos)
    return bool(pos >= min_short_pos)


def _adaptive_structure_plan(
    features: pd.DataFrame,
    *,
    signal_index: int,
    direction: int,
    family: str,
    entry_price: float,
    active_atr: float,
    min_structure_rr: float,
    wait_bars: int,
) -> dict[str, Any] | None:
    target_family = FAMILY_TARGET_BASE.get(family, family)
    is_reversal = target_family in STRUCTURE_REVERSAL_BASES
    lookback = 34 if is_reversal else 14
    start = max(0, signal_index - lookback + 1)
    structure_low = float(features["Low"].iloc[start : signal_index + 1].min())
    structure_high = float(features["High"].iloc[start : signal_index + 1].max())
    if not np.isfinite(structure_low) or not np.isfinite(structure_high) or structure_high <= structure_low:
        return None
    width = structure_high - structure_low
    buffer = max(active_atr * (0.18 if is_reversal else 0.12), 0.25)
    max_risk_atr = 2.25 if is_reversal else 1.55
    max_long_pos = 0.55 if is_reversal else 0.72
    min_short_pos = 0.45 if is_reversal else 0.28
    if direction > 0:
        structure_stop = structure_low - buffer
        structure_target = structure_high + width * (0.45 if is_reversal else 0.65)
        risk = entry_price - structure_stop
        reward = structure_target - entry_price
    else:
        structure_stop = structure_high + buffer
        structure_target = structure_low - width * (0.45 if is_reversal else 0.65)
        risk = structure_stop - entry_price
        reward = entry_price - structure_target
    if risk <= 0 or reward <= 0:
        return None
    if risk > active_atr * max_risk_atr:
        return None
    if not _price_in_directional_zone(
        direction=direction,
        entry_price=entry_price,
        structure_low=structure_low,
        structure_high=structure_high,
        max_long_pos=max_long_pos,
        min_short_pos=min_short_pos,
    ):
        return None
    structure_rr = reward / risk
    if structure_rr >= min_structure_rr:
        return {
            "entry_index": signal_index + 1,
            "entry_price": float(entry_price),
            "structure_stop": float(structure_stop),
            "structure_target": float(structure_target),
            "structure_rr": float(structure_rr),
        }
    if wait_bars <= 0:
        return None

    pullback_fraction = 0.42 if is_reversal else 0.56
    if direction > 0:
        limit_price = min(entry_price, structure_low + width * pullback_fraction)
        risk = limit_price - structure_stop
        reward = structure_target - limit_price
    else:
        limit_price = max(entry_price, structure_high - width * pullback_fraction)
        risk = structure_stop - limit_price
        reward = limit_price - structure_target
    if risk <= 0 or reward <= 0 or risk > active_atr * max_risk_atr:
        return None
    structure_rr = reward / risk
    if structure_rr < min_structure_rr:
        return None
    for entry_index in range(signal_index + 1, min(len(features), signal_index + wait_bars + 1)):
        if direction > 0:
            if float(features["Low"].iat[entry_index]) <= limit_price:
                return {
                    "entry_index": entry_index,
                    "entry_price": float(limit_price),
                    "structure_stop": float(structure_stop),
                    "structure_target": float(structure_target),
                    "structure_rr": float(structure_rr),
                }
        elif float(features["High"].iat[entry_index]) >= limit_price:
            return {
                "entry_index": entry_index,
                "entry_price": float(limit_price),
                "structure_stop": float(structure_stop),
                "structure_target": float(structure_target),
                "structure_rr": float(structure_rr),
            }
    return None


def _micro_structure_plan(
    features: pd.DataFrame,
    config: BoundaryLightglowConfig,
    *,
    signal_index: int,
    direction: int,
    family: str,
    entry_price: float,
    active_atr: float,
    min_structure_rr: float,
    wait_bars: int,
) -> dict[str, Any] | None:
    lookback = 8 if "pullback" in family else 12
    start = max(0, signal_index - lookback + 1)
    recent_low = float(features["Low"].iloc[start : signal_index + 1].min())
    recent_high = float(features["High"].iloc[start : signal_index + 1].max())
    range_high = float(features["range_high"].iat[signal_index])
    range_low = float(features["range_low"].iat[signal_index])
    if not np.isfinite(recent_low) or not np.isfinite(recent_high) or recent_high <= recent_low:
        return None
    buffer = max(active_atr * 0.10, 0.25)
    max_risk_atr = 2.8 if family.startswith("trend_transition") else 2.2

    def build_plan(candidate_entry: float, candidate_index: int) -> dict[str, Any] | None:
        if direction > 0:
            stop = recent_low - buffer
            raw_risk = candidate_entry - stop
        else:
            stop = recent_high + buffer
            raw_risk = stop - candidate_entry
        if raw_risk <= 0 or raw_risk > active_atr * max_risk_atr:
            return None
        target_family = FAMILY_TARGET_BASE.get(family, family)
        target, target_plan = _structure_target(target_family, direction, candidate_entry, raw_risk, range_high, range_low, config)
        reward = (target - candidate_entry) * direction
        if reward <= 0:
            return None
        structure_rr = reward / raw_risk
        if structure_rr < min_structure_rr:
            return None
        return {
            "entry_index": candidate_index,
            "entry_price": float(candidate_entry),
            "structure_stop": float(stop),
            "structure_target": float(target),
            "structure_rr": float(structure_rr),
            "target_plan": f"micro_{target_plan}",
        }

    immediate = build_plan(float(entry_price), signal_index + 1)
    if immediate is not None:
        return immediate
    if wait_bars <= 0:
        return None

    width = recent_high - recent_low
    if direction > 0:
        limit_price = max(recent_low + width * 0.45, entry_price - active_atr * 0.60)
        limit_price = min(limit_price, entry_price)
    else:
        limit_price = min(recent_high - width * 0.45, entry_price + active_atr * 0.60)
        limit_price = max(limit_price, entry_price)
    for entry_index in range(signal_index + 1, min(len(features), signal_index + wait_bars + 1)):
        if direction > 0:
            if float(features["Low"].iat[entry_index]) <= limit_price:
                return build_plan(float(limit_price), entry_index)
        elif float(features["High"].iat[entry_index]) >= limit_price:
            return build_plan(float(limit_price), entry_index)
    return None


def _is_known_loss_cluster(*, family: str, session: str, entry_ts: Any) -> bool:
    hour = pd.Timestamp(entry_ts).hour
    if family == "trend_transition_long" and session == "europe" and hour in {9, 12, 13}:
        return True
    if family == "trend_transition_short_asia" and session == "asia" and hour == 3:
        return True
    return False


def _passes_entry_quality_filter(features: pd.DataFrame, signal_index: int, family: str, filter_name: str) -> bool:
    if filter_name == "none":
        return True
    row = features.iloc[signal_index]
    range_pos = float(row.get("range_pos", np.nan))
    volume_z = float(row.get("volume_z", np.nan))
    body_atr = float(row.get("body_atr", np.nan))
    compression_width_atr = float(row.get("compression_width_atr", np.nan))
    momentum = float(row.get("momentum", np.nan))
    hour = pd.Timestamp(row.get("ts")).hour if "ts" in row else -1
    session = str(row.get("session", ""))
    ema60 = float(row.get("ema60", np.nan))
    ema200 = float(row.get("ema200", np.nan))

    if filter_name in {"smc_volume_guard", "reversal_quality_guard", "defensive_quality_guard"}:
        if family == "smc_discount_choch_long" and np.isfinite(volume_z) and volume_z < 0.0:
            return False
    if filter_name in {"reversal_quality_guard", "defensive_quality_guard"}:
        if family == "bottom_reclaim_long" and np.isfinite(range_pos) and range_pos > 0.25:
            return False
    if filter_name == "reversal_loose_guard":
        if family == "smc_discount_choch_long" and np.isfinite(volume_z) and volume_z < 0.0:
            return False
        if family == "bottom_reclaim_long" and np.isfinite(range_pos) and range_pos > 0.45:
            return False
    if filter_name in {"pullback_quality_guard", "defensive_quality_guard"}:
        if family == "trend_pullback_long" and np.isfinite(range_pos) and range_pos > 0.70:
            return False
        if family == "trend_pullback_short_asia_europe" and np.isfinite(range_pos) and range_pos < 0.35:
            return False
    if filter_name == "defensive_quality_guard":
        if family == "trend_transition_long":
            weak_breakout = np.isfinite(volume_z) and volume_z < 0.0
            early_range = np.isfinite(range_pos) and range_pos < 0.35
            low_compression = np.isfinite(compression_width_atr) and compression_width_atr < 2.0
            if weak_breakout and early_range and low_compression:
                return False
        if family == "trend_transition_short_asia":
            late_range = np.isfinite(range_pos) and range_pos > 0.80
            weak_body = np.isfinite(body_atr) and body_atr < 0.35
            if late_range and weak_body:
                return False
    if filter_name == "momentum_quality_guard":
        if family in {"trend_transition_long", "trend_pullback_long"} and np.isfinite(momentum) and momentum <= 0:
            return False
        if family in {"trend_transition_short_asia", "trend_pullback_short_asia_europe"} and np.isfinite(momentum) and momentum >= 0:
            return False
        if family == "smc_discount_choch_long" and np.isfinite(volume_z) and volume_z < 0.0:
            return False
    if filter_name == "weak_hour_guard":
        if family == "smc_discount_choch_long" and hour in {0, 1, 2, 21, 22, 23}:
            return False
        if family == "trend_pullback_long" and hour in {0, 1, 2, 15, 16, 17, 21, 22, 23}:
            return False
    if filter_name in {"weak_ttl_session_guard", "weak_family_session_guard", "weak_hour_family_guard", "weak_combo2_guard"}:
        if family == "smc_discount_choch_long" and hour in {0, 1, 2, 21, 22, 23}:
            return False
        if family == "trend_pullback_long" and hour in {0, 1, 2, 15, 16, 17, 21, 22, 23}:
            return False
    if filter_name in {
        "weak_loss_cluster_guard",
        "weak_loss_cluster_ttl_asia_guard",
        "weak_loss_cluster_broad_hour_guard",
        "weak_loss_cluster_strict_guard",
        "weak_loss_cluster_ultra_guard",
        "weak_loss_cluster_ultra_plus_guard",
        "ultra_plus_trend_regime_guard",
        "ultra_plus_selective_regime_guard",
        "twelve_month_high_yield_guard",
    }:
        if family == "smc_discount_choch_long" and hour in {0, 1, 2, 21, 22, 23}:
            return False
        if family == "trend_pullback_long" and hour in {0, 1, 2, 10, 11, 13, 15, 16, 17, 19, 21, 22, 23}:
            return False
        if family == "trend_transition_long" and hour in {11, 14, 15, 19, 22}:
            return False
    if filter_name in {"weak_ttl_session_guard", "weak_family_session_guard"}:
        if family == "trend_transition_long" and session in {"us_rth", "us_late"}:
            return False
    if filter_name in {"weak_family_session_guard", "weak_combo2_guard"}:
        if family == "trend_pullback_long" and session in {"europe", "us_rth"}:
            return False
        if family == "trend_transition_long" and session in {"us_rth", "us_late"}:
            return False
    if filter_name == "weak_combo2_guard":
        if family == "smc_discount_choch_long" and session in {"asia", "europe"}:
            return False
    if filter_name == "weak_hour_family_guard":
        if family == "trend_pullback_long" and hour in {10, 11, 13, 19}:
            return False
        if family == "trend_transition_long" and hour in {11, 14, 15, 19, 22}:
            return False
    if filter_name in {
        "weak_loss_cluster_guard",
        "weak_loss_cluster_ttl_asia_guard",
        "weak_loss_cluster_broad_hour_guard",
        "weak_loss_cluster_strict_guard",
        "weak_loss_cluster_ultra_guard",
    }:
        if family == "smc_discount_choch_long" and session in {"asia", "europe"}:
            return False
        if family == "trend_transition_short_asia" and hour == 3:
            return False
    if filter_name in {
        "weak_loss_cluster_ttl_asia_guard",
        "weak_loss_cluster_strict_guard",
        "weak_loss_cluster_ultra_guard",
        "weak_loss_cluster_ultra_plus_guard",
        "ultra_plus_trend_regime_guard",
        "ultra_plus_selective_regime_guard",
    }:
        if family == "trend_transition_long" and session == "asia":
            return False
    if filter_name in {
        "weak_loss_cluster_strict_guard",
        "weak_loss_cluster_ultra_guard",
        "weak_loss_cluster_ultra_plus_guard",
        "ultra_plus_trend_regime_guard",
        "ultra_plus_selective_regime_guard",
    }:
        if family == "bottom_reclaim_long" and session in {"europe", "us_rth"}:
            return False
        if family == "trend_pullback_short_asia_europe" and session == "asia":
            return False
        if family == "top_breakout_long":
            return False
        if family == "fast_reversal_long" and session == "asia":
            return False
    if filter_name in {
        "weak_loss_cluster_broad_hour_guard",
        "weak_loss_cluster_ultra_guard",
        "weak_loss_cluster_ultra_plus_guard",
        "ultra_plus_trend_regime_guard",
        "ultra_plus_selective_regime_guard",
    }:
        if family == "trend_transition_short_asia" and hour in {0, 3, 23}:
            return False
        if family == "trend_transition_long" and hour in {1, 3, 5, 6, 16}:
            return False
        if family == "smc_discount_choch_long" and hour in {3, 10, 13, 16, 18}:
            return False
    if filter_name in {
        "weak_loss_cluster_ultra_plus_guard",
        "ultra_plus_trend_regime_guard",
        "ultra_plus_selective_regime_guard",
    }:
        if family == "trend_transition_long" and hour in {14, 17, 21, 22}:
            return False
        if family == "trend_pullback_short_asia_europe" and hour in {2, 3, 4, 5, 7, 8, 9, 12, 23}:
            return False
        if family == "bottom_reclaim_long" and hour in {0, 7, 8, 9, 10, 12, 17, 19}:
            return False
    if filter_name == "ultra_plus_trend_regime_guard":
        if np.isfinite(ema60) and np.isfinite(ema200) and ema60 < ema200:
            return False
    if filter_name == "ultra_plus_selective_regime_guard":
        if family == "trend_transition_long" and session == "europe" and np.isfinite(volume_z) and volume_z < 0.0:
            return False
        if family == "trend_transition_long" and hour in {8, 10, 18, 20}:
            return False
        if family == "smc_discount_choch_long" and session == "us_rth" and hour == 17:
            return False
        if family == "trend_transition_short_asia" and hour == 5 and np.isfinite(momentum) and momentum > 0:
            return False
    if filter_name == "twelve_month_high_yield_guard":
        if family == "top_breakout_long":
            return session == "us_rth" and hour in {13, 14, 15, 16, 19}
        if family == "smc_discount_choch_long":
            return (
                (session == "us_rth" and hour in {14, 15, 18, 19})
                or (session == "asia" and hour == 1)
                or (session == "europe" and hour == 9)
            )
        if family == "smc_ob_retest_short":
            return session == "us_rth" and hour in {15, 16}
        if family == "smc_premium_choch_short":
            return (
                (session == "us_late" and hour == 20)
                or (session == "us_rth" and hour in {13, 14})
                or (session == "asia" and hour == 4)
            )
        if family == "smc_ob_retest_long":
            return (
                (session == "us_rth" and hour == 15)
                or (session == "us_late" and hour == 20)
                or (session == "europe" and hour == 13)
            )
        return False
    return True


def backtest_combo_fast(features: pd.DataFrame, spec: ComboSpec, config: BoundaryLightglowConfig, costs: BacktestCosts) -> pd.DataFrame:
    family_array = np.full(len(features), "", dtype=object)
    direction_array = np.zeros(len(features), dtype=np.int8)
    for family in spec.families:
        direction = FAMILY_DIRECTIONS[family]
        mask = features[f"lg_{family}"].fillna(False).to_numpy(dtype=bool)
        macd_mask = _macd_filter_mask(features, direction, timeframe=spec.macd_timeframe, filter_name=spec.macd_filter).fillna(False).to_numpy(dtype=bool)
        final_mask = mask & macd_mask & (direction_array == 0)
        family_array[final_mask] = family
        direction_array[final_mask] = direction

    signal_indexes = np.flatnonzero(direction_array != 0)
    if len(signal_indexes) == 0:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    open_prices = features["Open"].to_numpy(dtype=float)
    high_prices = features["High"].to_numpy(dtype=float)
    low_prices = features["Low"].to_numpy(dtype=float)
    close_prices = features["Close"].to_numpy(dtype=float)
    atr = features["atr"].to_numpy(dtype=float)
    range_high_values = features["range_high"].to_numpy(dtype=float)
    range_low_values = features["range_low"].to_numpy(dtype=float)
    strong_trend_long = features.get("strong_trend_continuation_long", pd.Series(False, index=features.index)).fillna(False).to_numpy(dtype=bool)
    strong_trend_short = features.get("strong_trend_continuation_short", pd.Series(False, index=features.index)).fillna(False).to_numpy(dtype=bool)
    adverse_reversal_long = features.get("adverse_reversal_long", pd.Series(False, index=features.index)).fillna(False).to_numpy(dtype=bool)
    adverse_reversal_short = features.get("adverse_reversal_short", pd.Series(False, index=features.index)).fillna(False).to_numpy(dtype=bool)
    symbols = features["symbol"].astype(str).to_numpy()
    sessions = features["session"].astype(str).to_numpy()
    trade_dates = features["trade_date"].to_numpy()
    timestamps = features["ts"].to_numpy()

    last_exit_index = -10**9
    pause_until = -1
    consecutive_losses = 0
    day_state: dict[Any, dict[str, float]] = {}
    for index in signal_indexes:
        family = str(family_array[index])
        target_family = FAMILY_TARGET_BASE.get(family, family)
        direction = int(direction_array[index])
        entry_index = int(index) + 1
        if entry_index >= len(features):
            continue
        active_atr = float(atr[index]) if np.isfinite(atr[index]) and atr[index] > 0 else float(atr[entry_index])
        if not np.isfinite(active_atr) or active_atr <= 0:
            continue
        structure_plan: dict[str, Any] | None = None
        if spec.entry_mode == "structure_rr":
            structure_plan = _structure_entry_plan(
                features,
                signal_index=index,
                direction=direction,
                active_atr=active_atr,
                min_structure_rr=spec.min_structure_rr,
                wait_bars=spec.entry_wait_bars,
            )
            if structure_plan is None:
                continue
            entry_index = int(structure_plan["entry_index"])
        elif spec.entry_mode == "structure_filter":
            structure_plan = _structure_filter_plan(
                features,
                signal_index=index,
                direction=direction,
                entry_price=float(open_prices[entry_index]),
                active_atr=active_atr,
                min_structure_rr=spec.min_structure_rr,
            )
            if structure_plan is None:
                continue
        elif spec.entry_mode == "structure_adaptive":
            structure_plan = _adaptive_structure_plan(
                features,
                signal_index=index,
                direction=direction,
                family=family,
                entry_price=float(open_prices[entry_index]),
                active_atr=active_atr,
                min_structure_rr=spec.min_structure_rr,
                wait_bars=spec.entry_wait_bars,
            )
            if structure_plan is None:
                continue
            entry_index = int(structure_plan["entry_index"])
        elif spec.entry_mode == "structure_micro_rr":
            structure_plan = _micro_structure_plan(
                features,
                config,
                signal_index=index,
                direction=direction,
                family=family,
                entry_price=float(open_prices[entry_index]),
                active_atr=active_atr,
                min_structure_rr=spec.min_structure_rr,
                wait_bars=spec.entry_wait_bars,
            )
            if structure_plan is None:
                continue
            entry_index = int(structure_plan["entry_index"])
        elif spec.entry_mode not in {"next_open", "structure_risk_cap"}:
            raise ValueError(f"unknown entry mode: {spec.entry_mode}")
        if entry_index <= last_exit_index + config.cooldown_bars or entry_index <= pause_until or entry_index >= len(features):
            continue
        if symbols[entry_index] != symbols[index]:
            continue
        if not _passes_entry_quality_filter(features, index, family, spec.entry_quality_filter):
            continue
        if spec.avoid_loss_clusters and _is_known_loss_cluster(family=family, session=sessions[index], entry_ts=timestamps[entry_index]):
            continue
        trade_day = trade_dates[entry_index]
        state = day_state.setdefault(trade_day, {"trades": 0.0, "net": 0.0})
        if spec.use_risk_controls and (state["trades"] >= config.max_trades_per_day or state["net"] <= -config.daily_stop_points):
            continue

        entry_price = float(open_prices[entry_index]) if structure_plan is None else float(structure_plan["entry_price"])
        range_high = float(range_high_values[index])
        range_low = float(range_low_values[index])
        signal_high = float(high_prices[index])
        signal_low = float(low_prices[index])
        if structure_plan is not None:
            structure_stop = float(structure_plan["structure_stop"])
        elif direction > 0:
            structure_stop = range_high - active_atr * config.stop_atr_buffer if target_family == "top_breakout_long" and np.isfinite(range_high) else signal_low - active_atr * config.stop_atr_buffer
        else:
            structure_stop = range_low + active_atr * config.stop_atr_buffer if target_family == "bottom_breakdown_short" and np.isfinite(range_low) else signal_high + active_atr * config.stop_atr_buffer
        raw_risk = abs(entry_price - structure_stop)
        risk_points = max(raw_risk, 0.25) if structure_plan is not None else max(raw_risk, active_atr * config.min_risk_atr, 0.25)
        uncapped_risk_points = risk_points
        risk_cap_points = active_atr * spec.risk_cap_atr if spec.entry_mode == "structure_risk_cap" and spec.risk_cap_atr > 0 else np.nan
        if np.isfinite(risk_cap_points) and risk_points > risk_cap_points:
            risk_points = max(float(risk_cap_points), active_atr * config.min_risk_atr, 0.25)
        initial_stop = entry_price - direction * risk_points
        if structure_plan is None:
            target_risk_points = uncapped_risk_points if spec.entry_mode == "structure_risk_cap" else risk_points
            target, target_plan = _structure_target(target_family, direction, entry_price, target_risk_points, range_high, range_low, config)
            if spec.entry_mode == "structure_risk_cap" and risk_points < uncapped_risk_points:
                target_plan = f"cap_stop_preserve_{target_plan}"
            structure_rr = np.nan
        else:
            target = float(structure_plan["structure_target"])
            target_plan = str(structure_plan.get("target_plan", "structure_rr_pullback"))
            structure_rr = float(structure_plan["structure_rr"])

        best = float(high_prices[entry_index]) if direction > 0 else float(low_prices[entry_index])
        protective_stop = initial_stop
        exit_index = entry_index
        exit_price = float(close_prices[entry_index])
        exit_reason = "end_of_data"
        path_end = min(len(features) - 1, entry_index + config.max_hold_bars)
        path_start = min(len(features) - 1, entry_index + 1)
        runner_allowed = spec.target_runner and (not spec.target_runner_families or family in spec.target_runner_families)
        target_runner_armed = False
        for path_index in range(path_start, path_end + 1):
            if symbols[path_index] != symbols[entry_index]:
                exit_index = max(entry_index, path_index - 1)
                exit_price = float(close_prices[exit_index])
                exit_reason = "contract_roll"
                break
            if direction > 0:
                if low_prices[path_index] <= protective_stop:
                    exit_index = path_index
                    exit_price = float(protective_stop)
                    exit_reason = "protective_stop"
                    break
                if path_index - entry_index >= config.min_hold_bars_before_target_exit and high_prices[path_index] >= target:
                    if not (runner_allowed and target_runner_armed):
                        exit_index = path_index
                        exit_price = float(target)
                        exit_reason = "target"
                        break
                current_r = (float(close_prices[path_index]) - entry_price) / risk_points
                if spec.adverse_reversal_exit and current_r <= spec.adverse_exit_max_r and adverse_reversal_long[path_index]:
                    exit_index = path_index
                    exit_price = float(close_prices[path_index])
                    exit_reason = "adverse_reversal"
                    break
                best = max(best, float(high_prices[path_index]))
                progress_r = (best - entry_price) / risk_points
                trail_stop = best - float(atr[path_index]) * config.trail_atr_mult if progress_r >= config.trail_start_r else initial_stop
                breakeven_stop = entry_price if progress_r >= config.breakeven_trigger_r else initial_stop
                giveback_stop = entry_price + risk_points * spec.giveback_keep_r if spec.giveback_start_r > 0 and progress_r >= spec.giveback_start_r else initial_stop
                protective_stop = max(initial_stop, trail_stop, breakeven_stop, giveback_stop)
                current_r = (float(close_prices[path_index]) - entry_price) / risk_points
                if runner_allowed and strong_trend_long[path_index] and progress_r >= config.trail_start_r:
                    target_runner_armed = True
            else:
                if high_prices[path_index] >= protective_stop:
                    exit_index = path_index
                    exit_price = float(protective_stop)
                    exit_reason = "protective_stop"
                    break
                if path_index - entry_index >= config.min_hold_bars_before_target_exit and low_prices[path_index] <= target:
                    if not (runner_allowed and target_runner_armed):
                        exit_index = path_index
                        exit_price = float(target)
                        exit_reason = "target"
                        break
                current_r = (entry_price - float(close_prices[path_index])) / risk_points
                if spec.adverse_reversal_exit and current_r <= spec.adverse_exit_max_r and adverse_reversal_short[path_index]:
                    exit_index = path_index
                    exit_price = float(close_prices[path_index])
                    exit_reason = "adverse_reversal"
                    break
                best = min(best, float(low_prices[path_index]))
                progress_r = (entry_price - best) / risk_points
                trail_stop = best + float(atr[path_index]) * config.trail_atr_mult if progress_r >= config.trail_start_r else initial_stop
                breakeven_stop = entry_price if progress_r >= config.breakeven_trigger_r else initial_stop
                giveback_stop = entry_price - risk_points * spec.giveback_keep_r if spec.giveback_start_r > 0 and progress_r >= spec.giveback_start_r else initial_stop
                protective_stop = min(initial_stop, trail_stop, breakeven_stop, giveback_stop)
                current_r = (entry_price - float(close_prices[path_index])) / risk_points
                if runner_allowed and strong_trend_short[path_index] and progress_r >= config.trail_start_r:
                    target_runner_armed = True
            if spec.time_stop_bars > 0 and path_index - entry_index >= spec.time_stop_bars and current_r < spec.time_stop_min_r:
                exit_index = path_index
                exit_price = float(close_prices[path_index])
                exit_reason = "time_stop"
                break
            if path_index >= path_end:
                exit_index = path_index
                exit_price = float(close_prices[path_index])
                exit_reason = "max_hold"
                break

        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points
        trade_key = "|".join(
            [
                spec.name,
                str(timestamps[entry_index]),
                str(timestamps[exit_index]),
                family,
                str(direction),
                f"{entry_price:.2f}",
                f"{exit_price:.2f}",
                str(entry_index),
                str(exit_index),
            ]
        )
        trade_id = f"TRD-{hashlib.sha1(trade_key.encode('utf-8')).hexdigest()[:12].upper()}"
        rows.append(
            {
                "trade_id": trade_id,
                "signal_ts": timestamps[index],
                "entry_ts": timestamps[entry_index],
                "exit_ts": timestamps[exit_index],
                "symbol": symbols[entry_index],
                "signal_family": family,
                "session": sessions[index],
                "direction": direction,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "initial_stop": float(initial_stop),
                "target": float(target),
                "target_plan": target_plan,
                "entry_mode": spec.entry_mode,
                "structure_rr": float(structure_rr) if np.isfinite(structure_rr) else np.nan,
                "exit_reason": exit_reason,
                "bars_held": int(exit_index - entry_index),
                "gross_points": float(gross_points),
                "net_points": float(net_points),
                "net_dollars": float(net_points * costs.point_value),
                "entry_index": int(entry_index),
                "exit_index": int(exit_index),
            }
        )
        state["trades"] += 1
        state["net"] += net_points
        consecutive_losses = consecutive_losses + 1 if net_points < 0 else 0
        if spec.use_risk_controls and consecutive_losses >= config.consecutive_loss_pause:
            pause_until = exit_index + config.pause_bars_after_loss_streak
            consecutive_losses = 0
        last_exit_index = exit_index
    return pd.DataFrame(rows)


def build_combo_specs(args: argparse.Namespace) -> list[ComboSpec]:
    family_groups: list[tuple[str, tuple[str, ...]]] = [
        ("pine_default", PINE_DEFAULT_FAMILIES),
        ("boundary_reversal", ("bottom_reclaim_long", "top_reject_short")),
        ("fast_boundary_reversal", ("fast_reversal_long", "fast_reversal_short")),
        ("screenshot_reversal", ("fast_reversal_long", "fast_reversal_short", "bottom_reclaim_long", "top_reject_short")),
        ("boundary_continuation", ("bottom_breakdown_short", "top_breakout_long")),
        ("trend_ignition", ("trend_ignition_long", "trend_ignition_short")),
        ("trend_pullback", ("trend_pullback_long", "trend_pullback_short")),
        ("trend_transition", ("trend_transition_long", "trend_transition_short")),
        ("reversal_impulse", ("reversal_impulse_long", "reversal_impulse_short")),
        ("phase_trend", ("phase_up_breakout_long", "phase_up_pullback_long", "phase_down_breakdown_short", "phase_down_pullback_short")),
        ("phase_long", ("phase_up_breakout_long", "phase_up_pullback_long")),
        ("phase_short", ("phase_down_breakdown_short", "phase_down_pullback_short")),
        (
            "phase_plus_fast",
            (
                "phase_up_breakout_long",
                "phase_up_pullback_long",
                "phase_down_breakdown_short",
                "phase_down_pullback_short",
                "fast_reversal_long",
                "fast_reversal_short",
            ),
        ),
        ("long_bias", ("top_breakout_long", "trend_ignition_long", "trend_pullback_long", "trend_transition_long", "reversal_impulse_long")),
        ("short_bias", ("bottom_breakdown_short", "top_reject_short", "trend_pullback_short", "trend_transition_short", "reversal_impulse_short")),
        (
            "selective_bidirectional",
            (
                "top_breakout_long",
                "trend_ignition_long",
                "trend_pullback_long",
                "trend_transition_long",
                "reversal_impulse_long",
                "bottom_breakdown_short",
                "trend_pullback_short",
                "trend_transition_short",
            ),
        ),
        (
            "selective_bidirectional_core",
            (
                "top_breakout_long",
                "trend_pullback_long",
                "trend_transition_long",
                "bottom_breakdown_short",
                "trend_pullback_short",
                "trend_transition_short",
            ),
        ),
        (
            "selective_bidirectional_session",
            (
                "top_breakout_long",
                "trend_ignition_long",
                "trend_pullback_long",
                "trend_transition_long",
                "reversal_impulse_long",
                "trend_pullback_short_asia_europe",
                "trend_transition_short_asia_rth",
            ),
        ),
        (
            "selective_bidirectional_strict_short",
            (
                "top_breakout_long",
                "trend_ignition_long",
                "trend_pullback_long",
                "trend_transition_long",
                "reversal_impulse_long",
                "trend_pullback_short_asia_europe",
                "trend_transition_short_asia",
            ),
        ),
        (
            "selective_bidirectional_strict_reversal_long",
            (
                "top_breakout_long",
                "trend_ignition_long",
                "trend_pullback_long",
                "trend_transition_long",
                "reversal_impulse_long",
                "bottom_reclaim_long",
                "fast_reversal_long",
                "smc_discount_choch_long",
                "trend_pullback_short_asia_europe",
                "trend_transition_short_asia",
            ),
        ),
        ("smc_reversal", ("smc_discount_choch_long", "smc_premium_choch_short")),
        ("smc_bos_fvg", ("smc_bos_fvg_long", "smc_bos_fvg_short")),
        ("smc_ob_retest", ("smc_ob_retest_long", "smc_ob_retest_short")),
        ("smc_trend_filtered", ("smc_trend_transition_long", "smc_trend_pullback_long", "smc_trend_transition_short", "smc_trend_pullback_short")),
        (
            "smc_long_bias",
            (
                "smc_discount_choch_long",
                "smc_bos_fvg_long",
                "smc_ob_retest_long",
                "smc_trend_transition_long",
                "smc_trend_pullback_long",
            ),
        ),
        (
            "smc_strict_bidirectional",
            (
                "smc_discount_choch_long",
                "smc_bos_fvg_long",
                "smc_ob_retest_long",
                "smc_trend_transition_long",
                "smc_trend_pullback_long",
                "smc_premium_choch_short",
                "smc_bos_fvg_short",
                "smc_ob_retest_short",
                "smc_trend_transition_short",
                "smc_trend_pullback_short",
            ),
        ),
        ("all_lightglow", ALL_LIGHTGLOW_BASE_FAMILIES),
    ]
    structure_family_groups: list[tuple[str, tuple[str, ...]]] = [
        ("structure_rr_long_bias", ("top_breakout_long", "trend_ignition_long", "trend_pullback_long", "trend_transition_long", "reversal_impulse_long")),
        (
            "structure_rr_selective_strict",
            (
                "top_breakout_long",
                "trend_ignition_long",
                "trend_pullback_long",
                "trend_transition_long",
                "reversal_impulse_long",
                "trend_pullback_short_asia_europe",
                "trend_transition_short_asia",
            ),
        ),
    ]
    structure_filter_family_groups = [
        ("structure_filter_long_bias", ("top_breakout_long", "trend_ignition_long", "trend_pullback_long", "trend_transition_long", "reversal_impulse_long")),
        (
            "structure_filter_selective_strict",
            (
                "top_breakout_long",
                "trend_ignition_long",
                "trend_pullback_long",
                "trend_transition_long",
                "reversal_impulse_long",
                "trend_pullback_short_asia_europe",
                "trend_transition_short_asia",
            ),
        ),
    ]
    structure_adaptive_family_groups = [
        ("structure_adaptive_long_bias", ("top_breakout_long", "trend_ignition_long", "trend_pullback_long", "trend_transition_long", "reversal_impulse_long")),
        (
            "structure_adaptive_selective_strict",
            (
                "top_breakout_long",
                "trend_ignition_long",
                "trend_pullback_long",
                "trend_transition_long",
                "reversal_impulse_long",
                "trend_pullback_short_asia_europe",
                "trend_transition_short_asia",
            ),
        ),
        (
            "structure_adaptive_smc_strict",
            (
                "smc_discount_choch_long",
                "smc_bos_fvg_long",
                "smc_ob_retest_long",
                "smc_trend_transition_long",
                "smc_trend_pullback_long",
                "smc_premium_choch_short",
                "smc_bos_fvg_short",
                "smc_ob_retest_short",
                "smc_trend_transition_short",
                "smc_trend_pullback_short",
            ),
        ),
    ]
    structure_micro_family_groups = [
        ("structure_micro_long_bias", ("top_breakout_long", "trend_ignition_long", "trend_pullback_long", "trend_transition_long", "reversal_impulse_long")),
        (
            "structure_micro_selective_strict",
            (
                "top_breakout_long",
                "trend_ignition_long",
                "trend_pullback_long",
                "trend_transition_long",
                "reversal_impulse_long",
                "trend_pullback_short_asia_europe",
                "trend_transition_short_asia",
            ),
        ),
        ("structure_micro_trend_pullback", ("trend_pullback_long", "trend_pullback_short_asia_europe")),
    ]
    structure_risk_cap_family_groups = [
        ("structure_risk_cap_long_bias", ("top_breakout_long", "trend_ignition_long", "trend_pullback_long", "trend_transition_long", "reversal_impulse_long")),
        (
            "structure_risk_cap_selective_strict",
            (
                "top_breakout_long",
                "trend_ignition_long",
                "trend_pullback_long",
                "trend_transition_long",
                "reversal_impulse_long",
                "trend_pullback_short_asia_europe",
                "trend_transition_short_asia",
            ),
        ),
        (
            "structure_risk_cap_selective_strict_reversal_long",
            (
                "top_breakout_long",
                "trend_ignition_long",
                "trend_pullback_long",
                "trend_transition_long",
                "reversal_impulse_long",
                "bottom_reclaim_long",
                "fast_reversal_long",
                "smc_discount_choch_long",
                "trend_pullback_short_asia_europe",
                "trend_transition_short_asia",
            ),
        ),
    ]
    specs: list[ComboSpec] = []
    for group_name, families in family_groups:
        for timeframe, macd_filter, stop_atr_buffer, target_r, max_hold_bars, use_risk_controls in itertools.product(
            args.macd_timeframes,
            args.macd_filters,
            args.stop_atr_buffers,
            args.target_rs,
            args.max_hold_bars_grid,
            args.risk_control_modes,
        ):
            name = (
                f"{group_name}_macd{timeframe}_{macd_filter}"
                f"_stop{stop_atr_buffer:g}_r{target_r:g}_h{max_hold_bars}"
                f"_{'risk' if use_risk_controls else 'norisk'}"
            )
            specs.append(
                ComboSpec(
                    name=name,
                    families=families,
                    macd_filter=macd_filter,
                    macd_timeframe=timeframe,
                    stop_atr_buffer=float(stop_atr_buffer),
                    target_r=float(target_r),
                    max_hold_bars=int(max_hold_bars),
                    use_risk_controls=bool(use_risk_controls),
                )
            )
    for group_name, families in structure_family_groups:
        for timeframe, macd_filter, stop_atr_buffer, target_r, max_hold_bars, use_risk_controls, min_structure_rr in itertools.product(
            args.macd_timeframes,
            args.macd_filters,
            args.stop_atr_buffers,
            args.target_rs,
            args.max_hold_bars_grid,
            args.risk_control_modes,
            [2.0, 2.5],
        ):
            name = (
                f"{group_name}_macd{timeframe}_{macd_filter}"
                f"_stop{stop_atr_buffer:g}_r{target_r:g}_h{max_hold_bars}"
                f"_rr{min_structure_rr:g}_wait8"
                f"_{'risk' if use_risk_controls else 'norisk'}"
            )
            specs.append(
                ComboSpec(
                    name=name,
                    families=families,
                    macd_filter=macd_filter,
                    macd_timeframe=timeframe,
                    stop_atr_buffer=float(stop_atr_buffer),
                    target_r=float(target_r),
                    max_hold_bars=int(max_hold_bars),
                    use_risk_controls=bool(use_risk_controls),
                    entry_mode="structure_rr",
                    min_structure_rr=float(min_structure_rr),
                    entry_wait_bars=8,
                )
            )
    for group_name, families in structure_filter_family_groups:
        for timeframe, macd_filter, stop_atr_buffer, target_r, max_hold_bars, use_risk_controls, min_structure_rr in itertools.product(
            args.macd_timeframes,
            args.macd_filters,
            args.stop_atr_buffers,
            args.target_rs,
            args.max_hold_bars_grid,
            args.risk_control_modes,
            [1.5, 2.0, 2.5],
        ):
            name = (
                f"{group_name}_macd{timeframe}_{macd_filter}"
                f"_stop{stop_atr_buffer:g}_r{target_r:g}_h{max_hold_bars}"
                f"_rr{min_structure_rr:g}"
                f"_{'risk' if use_risk_controls else 'norisk'}"
            )
            specs.append(
                ComboSpec(
                    name=name,
                    families=families,
                    macd_filter=macd_filter,
                    macd_timeframe=timeframe,
                    stop_atr_buffer=float(stop_atr_buffer),
                    target_r=float(target_r),
                    max_hold_bars=int(max_hold_bars),
                    use_risk_controls=bool(use_risk_controls),
                    entry_mode="structure_filter",
                    min_structure_rr=float(min_structure_rr),
                    entry_wait_bars=0,
                )
            )
    for group_name, families in structure_adaptive_family_groups:
        for timeframe, macd_filter, stop_atr_buffer, target_r, max_hold_bars, use_risk_controls, min_structure_rr, wait_bars in itertools.product(
            args.macd_timeframes,
            args.macd_filters,
            args.stop_atr_buffers,
            args.target_rs,
            args.max_hold_bars_grid,
            args.risk_control_modes,
            [1.4, 1.7, 2.0],
            [3, 5],
        ):
            name = (
                f"{group_name}_macd{timeframe}_{macd_filter}"
                f"_stop{stop_atr_buffer:g}_r{target_r:g}_h{max_hold_bars}"
                f"_rr{min_structure_rr:g}_wait{wait_bars}"
                f"_{'risk' if use_risk_controls else 'norisk'}"
            )
            specs.append(
                ComboSpec(
                    name=name,
                    families=families,
                    macd_filter=macd_filter,
                    macd_timeframe=timeframe,
                    stop_atr_buffer=float(stop_atr_buffer),
                    target_r=float(target_r),
                    max_hold_bars=int(max_hold_bars),
                    use_risk_controls=bool(use_risk_controls),
                    entry_mode="structure_adaptive",
                    min_structure_rr=float(min_structure_rr),
                    entry_wait_bars=int(wait_bars),
                )
            )
    for group_name, families in structure_micro_family_groups:
        for timeframe, macd_filter, stop_atr_buffer, target_r, max_hold_bars, use_risk_controls, min_structure_rr, wait_bars in itertools.product(
            args.macd_timeframes,
            args.macd_filters,
            args.stop_atr_buffers,
            args.target_rs,
            args.max_hold_bars_grid,
            args.risk_control_modes,
            [1.0, 1.25, 1.5],
            [0, 3],
        ):
            name = (
                f"{group_name}_macd{timeframe}_{macd_filter}"
                f"_stop{stop_atr_buffer:g}_r{target_r:g}_h{max_hold_bars}"
                f"_rr{min_structure_rr:g}_wait{wait_bars}"
                f"_{'risk' if use_risk_controls else 'norisk'}"
            )
            specs.append(
                ComboSpec(
                    name=name,
                    families=families,
                    macd_filter=macd_filter,
                    macd_timeframe=timeframe,
                    stop_atr_buffer=float(stop_atr_buffer),
                    target_r=float(target_r),
                    max_hold_bars=int(max_hold_bars),
                    use_risk_controls=bool(use_risk_controls),
                    entry_mode="structure_micro_rr",
                    min_structure_rr=float(min_structure_rr),
                    entry_wait_bars=int(wait_bars),
                )
            )
    for group_name, families in structure_risk_cap_family_groups:
        for timeframe, macd_filter, stop_atr_buffer, target_r, max_hold_bars, use_risk_controls, risk_cap_atr in itertools.product(
            args.macd_timeframes,
            args.macd_filters,
            args.stop_atr_buffers,
            args.target_rs,
            args.max_hold_bars_grid,
            args.risk_control_modes,
            [2.0, 2.5, 3.0, 3.5, 4.0, 5.0],
        ):
            name = (
                f"{group_name}_macd{timeframe}_{macd_filter}"
                f"_stop{stop_atr_buffer:g}_r{target_r:g}_h{max_hold_bars}"
                f"_cap{risk_cap_atr:g}atr"
                f"_{'risk' if use_risk_controls else 'norisk'}"
            )
            specs.append(
                ComboSpec(
                    name=name,
                    families=families,
                    macd_filter=macd_filter,
                    macd_timeframe=timeframe,
                    stop_atr_buffer=float(stop_atr_buffer),
                    target_r=float(target_r),
                    max_hold_bars=int(max_hold_bars),
                    use_risk_controls=bool(use_risk_controls),
                    entry_mode="structure_risk_cap",
                    risk_cap_atr=float(risk_cap_atr),
                )
            )
    reversal_long_families = (
        "top_breakout_long",
        "trend_ignition_long",
        "trend_pullback_long",
        "trend_transition_long",
        "reversal_impulse_long",
        "bottom_reclaim_long",
        "fast_reversal_long",
        "smc_discount_choch_long",
        "trend_pullback_short_asia_europe",
        "trend_transition_short_asia",
    )
    exit_enhancements = [
        (
            "selective_yield_balanced_reversal_long",
            "next_open",
            0.0,
            30,
            2.5,
            4.0,
            1.2,
            2.0,
            1.5,
            1.0,
            0,
            0.0,
            0.0,
            0.0,
            False,
            False,
            False,
            999.0,
            (),
        ),
        (
            "selective_exit_lock_reversal_long",
            "next_open",
            0.0,
            30,
            2.5,
            4.0,
            1.2,
            2.0,
            1.5,
            1.0,
            0,
            0.0,
            1.5,
            1.0,
            False,
            False,
            False,
            999.0,
            (),
        ),
        (
            "selective_adverse_guard_reversal_long",
            "next_open",
            0.0,
            35,
            2.5,
            4.0,
            1.2,
            2.0,
            1.5,
            1.0,
            0,
            0.0,
            1.5,
            1.0,
            False,
            False,
            True,
            0.25,
            (),
        ),
        (
            "selective_long_runner_adverse_guard_reversal_long",
            "next_open",
            0.0,
            35,
            2.5,
            4.0,
            1.2,
            2.0,
            1.5,
            1.0,
            0,
            0.0,
            1.5,
            1.0,
            False,
            True,
            True,
            0.25,
            ("trend_transition_long", "trend_pullback_long"),
        ),
        (
            "selective_runner_reversal_exit_reversal_long",
            "next_open",
            0.0,
            45,
            2.5,
            4.0,
            1.2,
            2.0,
            1.5,
            1.0,
            0,
            0.0,
            1.5,
            1.0,
            False,
            True,
            True,
            0.25,
            (),
        ),
        (
            "selective_exit_lock_cluster_filter_reversal_long",
            "next_open",
            0.0,
            30,
            2.5,
            4.0,
            1.2,
            2.0,
            1.5,
            1.0,
            0,
            0.0,
            1.5,
            1.0,
            True,
            False,
            False,
            999.0,
            (),
        ),
        (
            "selective_adverse_guard_cluster_filter_reversal_long",
            "next_open",
            0.0,
            35,
            2.5,
            4.0,
            1.2,
            2.0,
            1.5,
            1.0,
            0,
            0.0,
            1.5,
            1.0,
            True,
            False,
            True,
            0.25,
            (),
        ),
        (
            "selective_long_runner_adverse_guard_cluster_filter_reversal_long",
            "next_open",
            0.0,
            35,
            2.5,
            4.0,
            1.2,
            2.0,
            1.5,
            1.0,
            0,
            0.0,
            1.5,
            1.0,
            True,
            True,
            True,
            0.25,
            ("trend_transition_long", "trend_pullback_long"),
        ),
        (
            "selective_runner_reversal_exit_cluster_filter_reversal_long",
            "next_open",
            0.0,
            45,
            2.5,
            4.0,
            1.2,
            2.0,
            1.5,
            1.0,
            0,
            0.0,
            1.5,
            1.0,
            True,
            True,
            True,
            0.25,
            (),
        ),
        (
            "selective_yield_growth_reversal_long",
            "next_open",
            0.0,
            40,
            2.75,
            3.0,
            1.2,
            3.0,
            1.5,
            1.0,
            0,
            0.0,
            0.0,
            0.0,
            False,
            False,
            False,
            999.0,
            (),
        ),
        (
            "structure_risk_cap_yield_growth_reversal_long",
            "structure_risk_cap",
            3.5,
            45,
            2.75,
            3.0,
            2.0,
            3.0,
            1.5,
            1.0,
            0,
            0.0,
            0.0,
            0.0,
            False,
            False,
            False,
            999.0,
            (),
        ),
        (
            "structure_risk_cap_exit_time_reversal_long",
            "structure_risk_cap",
            3.5,
            45,
            2.75,
            3.0,
            2.0,
            3.0,
            1.5,
            1.0,
            20,
            0.5,
            2.0,
            0.5,
            False,
            False,
            True,
            0.25,
            (),
        ),
    ]
    for (
        group_name,
        entry_mode,
        risk_cap_atr,
        max_hold_bars,
        target_r,
        max_target_r,
        trail_start_r,
        trail_atr_mult,
        breakeven_trigger_r,
        min_target_r,
        time_stop_bars,
        time_stop_min_r,
        giveback_start_r,
        giveback_keep_r,
        avoid_loss_clusters,
        target_runner,
        adverse_reversal_exit,
        adverse_exit_max_r,
        target_runner_families,
    ) in exit_enhancements:
        for timeframe, macd_filter, stop_atr_buffer, use_risk_controls in itertools.product(
            args.macd_timeframes,
            args.macd_filters,
            args.stop_atr_buffers,
            args.risk_control_modes,
        ):
            if timeframe != 1 or macd_filter != "cross_recent_5" or float(stop_atr_buffer) != 1.25:
                continue
            name = (
                f"{group_name}_macd{timeframe}_{macd_filter}"
                f"_stop{stop_atr_buffer:g}_r{target_r:g}_h{max_hold_bars}"
                f"_maxr{max_target_r:g}_trail{trail_start_r:g}x{trail_atr_mult:g}"
                f"_be{breakeven_trigger_r:g}"
            )
            if risk_cap_atr > 0:
                name += f"_cap{risk_cap_atr:g}atr"
            if time_stop_bars > 0:
                name += f"_tstop{time_stop_bars}b{time_stop_min_r:g}r"
            if giveback_start_r > 0:
                name += f"_lock{giveback_start_r:g}to{giveback_keep_r:g}r"
            if target_runner:
                name += "_runner"
            if adverse_reversal_exit:
                name += "_adverse_exit"
                if adverse_exit_max_r < 999.0:
                    name += f"{adverse_exit_max_r:g}r"
            name += f"_{'risk' if use_risk_controls else 'norisk'}"
            specs.append(
                ComboSpec(
                    name=name,
                    families=reversal_long_families,
                    macd_filter=macd_filter,
                    macd_timeframe=timeframe,
                    stop_atr_buffer=float(stop_atr_buffer),
                    target_r=float(target_r),
                    max_hold_bars=int(max_hold_bars),
                    use_risk_controls=bool(use_risk_controls),
                    entry_mode=entry_mode,
                    risk_cap_atr=float(risk_cap_atr),
                    max_target_r=float(max_target_r),
                    trail_start_r=float(trail_start_r),
                    trail_atr_mult=float(trail_atr_mult),
                    breakeven_trigger_r=float(breakeven_trigger_r),
                    min_target_r=float(min_target_r),
                    time_stop_bars=int(time_stop_bars),
                    time_stop_min_r=float(time_stop_min_r),
                    giveback_start_r=float(giveback_start_r),
                    giveback_keep_r=float(giveback_keep_r),
                    avoid_loss_clusters=bool(avoid_loss_clusters),
                    target_runner=bool(target_runner),
                    adverse_reversal_exit=bool(adverse_reversal_exit),
                    adverse_exit_max_r=float(adverse_exit_max_r),
                    target_runner_families=tuple(target_runner_families),
                )
            )
    quality_filters = [
        "smc_volume_guard",
        "reversal_loose_guard",
        "reversal_quality_guard",
        "pullback_quality_guard",
        "defensive_quality_guard",
        "momentum_quality_guard",
        "weak_hour_guard",
        "weak_ttl_session_guard",
        "weak_family_session_guard",
        "weak_hour_family_guard",
        "weak_combo2_guard",
        "weak_loss_cluster_guard",
        "weak_loss_cluster_ttl_asia_guard",
        "weak_loss_cluster_broad_hour_guard",
        "weak_loss_cluster_strict_guard",
        "weak_loss_cluster_ultra_guard",
        "weak_loss_cluster_ultra_plus_guard",
        "ultra_plus_trend_regime_guard",
        "ultra_plus_selective_regime_guard",
        "twelve_month_high_yield_guard",
    ]
    for filter_name in quality_filters:
        for timeframe, macd_filter, stop_atr_buffer, use_risk_controls in itertools.product(
            args.macd_timeframes,
            args.macd_filters,
            args.stop_atr_buffers,
            args.risk_control_modes,
        ):
            if timeframe != 1 or macd_filter != "cross_recent_5" or float(stop_atr_buffer) != 1.25:
                continue
            specs.append(
                ComboSpec(
                    name=(
                        f"selective_adverse_guard_{filter_name}_reversal_long"
                        f"_macd{timeframe}_{macd_filter}_stop{stop_atr_buffer:g}_r2.5_h35"
                        f"_maxr4_trail1.2x2_be1.5_lock1.5to1r_adverse_exit0.25r_norisk"
                    ),
                    families=reversal_long_families,
                    macd_filter=macd_filter,
                    macd_timeframe=timeframe,
                    stop_atr_buffer=float(stop_atr_buffer),
                    target_r=2.5,
                    max_hold_bars=35,
                    use_risk_controls=bool(use_risk_controls),
                    max_target_r=4.0,
                    trail_start_r=1.2,
                    trail_atr_mult=2.0,
                    breakeven_trigger_r=1.5,
                    min_target_r=1.0,
                    giveback_start_r=1.5,
                    giveback_keep_r=1.0,
                    adverse_reversal_exit=True,
                    adverse_exit_max_r=0.25,
                    entry_quality_filter=filter_name,
                )
            )
    high_yield_12m_family_groups = [
        (
            "twelve_month_high_yield_core",
            (
                "top_breakout_long",
                "smc_discount_choch_long",
                "smc_ob_retest_long",
                "smc_premium_choch_short",
                "smc_ob_retest_short",
            ),
        ),
        (
            "twelve_month_high_yield_smc_only",
            (
                "smc_discount_choch_long",
                "smc_ob_retest_long",
                "smc_premium_choch_short",
                "smc_ob_retest_short",
            ),
        ),
        (
            "twelve_month_high_yield_positive_smc",
            (
                "smc_discount_choch_long",
                "smc_premium_choch_short",
                "smc_ob_retest_short",
            ),
        ),
    ]
    for group_name, families in high_yield_12m_family_groups:
        for timeframe, macd_filter, stop_atr_buffer, min_structure_rr, wait_bars in itertools.product(
            args.macd_timeframes,
            args.macd_filters,
            args.stop_atr_buffers,
            [1.4, 1.7, 2.0],
            [3, 5],
        ):
            if timeframe != 1 or macd_filter != "cross_recent_5" or float(stop_atr_buffer) != 1.25:
                continue
            specs.append(
                ComboSpec(
                    name=(
                        f"{group_name}_macd{timeframe}_{macd_filter}_stop{stop_atr_buffer:g}"
                        f"_r2.5_h30_rr{min_structure_rr:g}_wait{wait_bars}"
                        "_12m_high_yield_guard_norisk"
                    ),
                    families=families,
                    macd_filter=macd_filter,
                    macd_timeframe=timeframe,
                    stop_atr_buffer=float(stop_atr_buffer),
                    target_r=2.5,
                    max_hold_bars=30,
                    use_risk_controls=False,
                    entry_mode="structure_adaptive",
                    min_structure_rr=float(min_structure_rr),
                    entry_wait_bars=int(wait_bars),
                    entry_quality_filter="twelve_month_high_yield_guard",
                )
            )
    return specs


def score_summary(summary: dict[str, float | int]) -> float:
    trades = int(summary["trades"])
    if trades < 3 or float(summary["net_points"]) <= 0:
        return -1_000_000.0 + float(summary["net_points"])
    net = float(summary["net_points"])
    pf = float(summary["profit_factor"])
    drawdown = max(float(summary["max_drawdown_points"]), 1.0)
    avg = float(summary["avg_points"])
    win_rate = float(summary["win_rate"])
    sample_penalty = 0.35 if trades < 10 else 0.65 if trades < MIN_ROBUST_TRADES else 1.0
    return sample_penalty * (net / drawdown * 100.0 + min(pf, 5.0) * 25.0 + avg * 4.0 + win_rate * 20.0) + min(trades, 100) * 0.25


def summarize_for_search(trades: pd.DataFrame) -> dict[str, float | int]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_points": 0.0,
            "max_drawdown_points": 0.0,
            "worst_trade_points": 0.0,
        }
    net = trades["net_points"].astype(float)
    equity = pd.concat([pd.Series([0.0]), net.cumsum()], ignore_index=True)
    drawdown = equity.cummax() - equity
    gross_profit = net[net > 0].sum()
    gross_loss = abs(net[net < 0].sum())
    return {
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else (999.0 if gross_profit > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "avg_points": float(net.mean()),
        "max_drawdown_points": float(drawdown.max()),
        "worst_trade_points": float(net.min()),
    }


def evaluate_combinations(features: pd.DataFrame, specs: list[ComboSpec], costs: BacktestCosts) -> tuple[pd.DataFrame, pd.DataFrame, ComboSpec | None]:
    rows: list[dict[str, Any]] = []
    best_trades = pd.DataFrame()
    best_spec: ComboSpec | None = None
    best_score = -np.inf
    for spec in specs:
        config = replace(
            BoundaryLightglowConfig(),
            stop_atr_buffer=spec.stop_atr_buffer,
            target_r=spec.target_r,
            max_hold_bars=spec.max_hold_bars,
            max_target_r=spec.max_target_r if spec.max_target_r > 0 else BoundaryLightglowConfig.max_target_r,
            trail_start_r=spec.trail_start_r if spec.trail_start_r > 0 else BoundaryLightglowConfig.trail_start_r,
            trail_atr_mult=spec.trail_atr_mult if spec.trail_atr_mult > 0 else BoundaryLightglowConfig.trail_atr_mult,
            breakeven_trigger_r=spec.breakeven_trigger_r if spec.breakeven_trigger_r > 0 else BoundaryLightglowConfig.breakeven_trigger_r,
            min_target_r=spec.min_target_r if spec.min_target_r > 0 else BoundaryLightglowConfig.min_target_r,
        )
        trades = backtest_combo_fast(features, spec, config, costs)
        summary = summarize_for_search(trades)
        score = score_summary(summary)
        rows.append(
            {
                "strategy": spec.name,
                "families": "+".join(spec.families),
                "macd_filter": spec.macd_filter,
                "macd_timeframe": spec.macd_timeframe,
                "stop_atr_buffer": spec.stop_atr_buffer,
                "target_r": spec.target_r,
                "max_hold_bars": spec.max_hold_bars,
                "use_risk_controls": spec.use_risk_controls,
                "entry_mode": spec.entry_mode,
                "min_structure_rr": spec.min_structure_rr,
                "entry_wait_bars": spec.entry_wait_bars,
                "risk_cap_atr": spec.risk_cap_atr,
                "max_target_r": spec.max_target_r,
                "trail_start_r": spec.trail_start_r,
                "trail_atr_mult": spec.trail_atr_mult,
                "breakeven_trigger_r": spec.breakeven_trigger_r,
                "min_target_r": spec.min_target_r,
                "time_stop_bars": spec.time_stop_bars,
                "time_stop_min_r": spec.time_stop_min_r,
                "giveback_start_r": spec.giveback_start_r,
                "giveback_keep_r": spec.giveback_keep_r,
                "avoid_loss_clusters": spec.avoid_loss_clusters,
                "target_runner": spec.target_runner,
                "adverse_reversal_exit": spec.adverse_reversal_exit,
                "adverse_exit_max_r": spec.adverse_exit_max_r,
                "entry_quality_filter": spec.entry_quality_filter,
                "score": score,
                **summary,
            }
        )
        if score > best_score:
            best_score = score
            best_trades = trades.copy()
            best_spec = spec
    results = pd.DataFrame(rows).sort_values(
        ["score", "net_points", "profit_factor", "max_drawdown_points"],
        ascending=[False, False, False, True],
    )
    return results, best_trades, best_spec


def write_markdown_report(
    path: Path,
    *,
    results: pd.DataFrame,
    best_trades: pd.DataFrame,
    best_spec: ComboSpec | None,
    args: argparse.Namespace,
    latest_ts: pd.Timestamp,
    costs: BacktestCosts,
) -> None:
    def markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
        if frame.empty:
            return "No rows."
        rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
        for _, row in frame[columns].iterrows():
            values = []
            for column in columns:
                value = row[column]
                if isinstance(value, float):
                    values.append(f"{value:.4f}")
                else:
                    values.append(str(value))
            rows.append("| " + " | ".join(values) + " |")
        return "\n".join(rows)

    path.parent.mkdir(parents=True, exist_ok=True)
    best_summary = summarize_for_search(best_trades)
    top = results.head(args.report_top_n).copy()
    columns = [
        "strategy",
        "trades",
        "net_points",
        "profit_factor",
        "win_rate",
        "avg_points",
        "max_drawdown_points",
        "worst_trade_points",
        "score",
    ]
    lines = [
        "# NQ Pine Indicator Combination Search",
        "",
        f"- Data: `{args.start_date}` to `{args.end_date}` from `data/raw/databento`; latest observed bar `{latest_ts}`.",
        f"- Pine inputs: `{LIGHTGLOW_PINE.relative_to(ROOT_DIR)}` and `{MACD_PINE.relative_to(ROOT_DIR)}`.",
        f"- Cost model: {costs.round_trip_cost_points:.2f} NQ points round trip, matching Pine slippage/commission assumptions used by the Lightglow strategy.",
        f"- Search size: {len(results)} combinations across Lightglow signal families, CM MACD MTF filters, stops, targets, holds, and risk controls.",
        "",
        "## Best Strategy",
        "",
    ]
    if best_spec is None:
        lines.append("No profitable strategy found.")
    else:
        lines.extend(
            [
                f"- Name: `{best_spec.name}`",
                f"- Lightglow families: `{'+'.join(best_spec.families)}`",
                f"- MACD filter: `{best_spec.macd_filter}` on `{best_spec.macd_timeframe}` minute aggregation",
                f"- Exit/risk: stop ATR buffer `{best_spec.stop_atr_buffer}`, target `{best_spec.target_r}R`, max hold `{best_spec.max_hold_bars}` bars, risk controls `{best_spec.use_risk_controls}`",
                f"- Performance: `{best_summary['trades']}` trades, `{best_summary['net_points']:.2f}` net points, PF `{best_summary['profit_factor']:.2f}`, win rate `{best_summary['win_rate']:.1%}`, max DD `{best_summary['max_drawdown_points']:.2f}` points, worst trade `{best_summary['worst_trade_points']:.2f}` points.",
            ]
        )
    lines.extend(["", "## Top Ranked Combinations", "", markdown_table(top, columns)])
    screenshot_rows = results[results["strategy"].astype(str).str.contains("fast_boundary_reversal|screenshot_reversal", regex=True)].head(10)
    phase_rows = results[results["strategy"].astype(str).str.contains("phase_", regex=False)].head(10)
    selective_rows = results[results["strategy"].astype(str).str.contains("selective_bidirectional", regex=False)].head(10)
    structure_rows = results[results["entry_mode"].astype(str).ne("next_open")].head(10)
    smc_rows = results[results["strategy"].astype(str).str.contains("smc_", regex=False)].head(10)
    sixty_min_rows = results[results["macd_timeframe"].eq(60)].head(10)
    lines.extend(
        [
            "",
            "## Screenshot-Inspired Early Reversal Candidates",
            "",
            "These rows emphasize boundary sweep/reclaim/reject behavior plus MACD histogram repair/deceleration, intended to enter before waiting for a full delayed MACD line cross.",
            "",
            markdown_table(screenshot_rows, columns),
            "",
            "## Bidirectional Phase Trend Candidates",
            "",
            "These rows target fast but staged upside and downside moves using EMA phase state, micro breakouts/breakdowns, pullback reclaim/failure, and early MACD histogram filters.",
            "",
            markdown_table(phase_rows, columns),
            "",
            "## Selective Bidirectional Candidates",
            "",
            "These rows keep the long-biased best-candidate family set and add only high-quality short continuation/transition/breakdown structures, avoiding broad top-picking shorts.",
            "",
            markdown_table(selective_rows, columns),
            "",
            "## Structure Risk-Reward Pullback Candidates",
            "",
            "These rows keep the directional signal fixed, then improve entry quality using only historical structure: deep pullback waits, adaptive structural zones, or micro-swing stop anchors with minimum R/R filters.",
            "",
            markdown_table(structure_rows, columns),
            "",
            "## Lightglow SMC-Filtered Candidates",
            "",
            "These rows translate the Lightglow/LuxAlgo SMC concepts into non-lookahead filters: internal/swing BOS or CHoCH, premium/discount location, recent fair value gaps, and order-block retests.",
            "",
            markdown_table(smc_rows, columns),
            "",
            "## 60m MACD Candidates",
            "",
            "These rows match the chart setup using `CM_Ult_MacD_MTF 60 12 26 9` more closely.",
            "",
            markdown_table(sixty_min_rows, columns),
            "",
            "## Best Trades",
            "",
        ]
    )
    if best_trades.empty:
        lines.append("No trades.")
    else:
        trade_cols = ["entry_ts", "exit_ts", "signal_family", "session", "direction", "entry_price", "exit_price", "exit_reason", "net_points"]
        lines.append(markdown_table(best_trades, trade_cols))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    default_start, default_end, latest_ts = latest_databento_window()
    parser = argparse.ArgumentParser(description="Search NQ strategies from two Pine indicators on the latest Databento 1m month.")
    parser.add_argument("--start-date", default=default_start)
    parser.add_argument("--end-date", default=default_end)
    parser.add_argument("--cache", default=".tmp/nq-pine-combo-last-month-bars.pkl")
    parser.add_argument("--chunk-size", type=int, default=200_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--macd-timeframes", type=int, nargs="+", default=[1, 5, 15, 60])
    parser.add_argument("--macd-filters", nargs="+", default=["none", "trend", "trend_hist", "hist_slope", "hist_repair", "hist_deceleration", "cross_recent_5"])
    parser.add_argument("--stop-atr-buffers", type=float, nargs="+", default=[0.35, 0.8, 1.25])
    parser.add_argument("--target-rs", type=float, nargs="+", default=[1.2, 1.8, 2.5])
    parser.add_argument("--max-hold-bars-grid", type=int, nargs="+", default=[30, 60, 90])
    parser.add_argument("--risk-control-modes", type=lambda value: value.lower() in {"1", "true", "yes", "y"}, nargs="+", default=[False, True])
    parser.add_argument("--results-output", default="reports/NQ-pine-indicator-combo-last-month-ranking.csv")
    parser.add_argument("--trades-output", default="reports/NQ-pine-indicator-combo-last-month-best-trades.csv")
    parser.add_argument("--report", default="reports/NQ-pine-indicator-combo-last-month-report.md")
    parser.add_argument("--report-top-n", type=int, default=20)
    parser.set_defaults(latest_ts=latest_ts)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    costs = pine_default_costs()
    bars = load_recent_nq_bars(args)
    base_config = BoundaryLightglowConfig()
    features = add_all_lightglow_signal_columns(add_features(bars, base_config), base_config)
    for timeframe in args.macd_timeframes:
        features = add_macd_features(features, MacdConfig(timeframe_minutes=timeframe))
    specs = build_combo_specs(args)
    results, best_trades, best_spec = evaluate_combinations(features, specs, costs)

    results_path = ROOT_DIR / args.results_output
    trades_path = ROOT_DIR / args.trades_output
    results_path.parent.mkdir(parents=True, exist_ok=True)
    trades_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(results_path, index=False)
    best_trades.to_csv(trades_path, index=False)
    write_markdown_report(ROOT_DIR / args.report, results=results, best_trades=best_trades, best_spec=best_spec, args=args, latest_ts=args.latest_ts, costs=costs)

    best_summary = summarize_for_search(best_trades)
    print(f"searched {len(results)} combinations")
    print(f"best_strategy {best_spec.name if best_spec else 'none'}")
    print(f"best_summary {best_summary}")
    print(f"wrote {args.results_output}")
    print(f"wrote {args.trades_output}")
    print(f"wrote {args.report}")


if __name__ == "__main__":
    main()
