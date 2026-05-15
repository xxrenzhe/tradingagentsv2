from __future__ import annotations

import argparse
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
}

PINE_DEFAULT_FAMILIES = ("top_breakout_long", "trend_ignition_long")
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
    }
    for family, condition in raw_conditions.items():
        condition = condition.fillna(False)
        output[f"lg_{family}"] = condition & ~condition.shift(1, fill_value=False)
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
        direction = int(direction_array[index])
        entry_index = int(index) + 1
        if entry_index <= last_exit_index + config.cooldown_bars or entry_index <= pause_until or entry_index >= len(features):
            continue
        if symbols[entry_index] != symbols[index]:
            continue
        trade_day = trade_dates[entry_index]
        state = day_state.setdefault(trade_day, {"trades": 0.0, "net": 0.0})
        if spec.use_risk_controls and (state["trades"] >= config.max_trades_per_day or state["net"] <= -config.daily_stop_points):
            continue

        entry_price = float(open_prices[entry_index])
        active_atr = float(atr[index]) if np.isfinite(atr[index]) and atr[index] > 0 else float(atr[entry_index])
        if not np.isfinite(active_atr) or active_atr <= 0:
            continue
        range_high = float(range_high_values[index])
        range_low = float(range_low_values[index])
        signal_high = float(high_prices[index])
        signal_low = float(low_prices[index])
        if direction > 0:
            structure_stop = range_high - active_atr * config.stop_atr_buffer if family == "top_breakout_long" and np.isfinite(range_high) else signal_low - active_atr * config.stop_atr_buffer
        else:
            structure_stop = range_low + active_atr * config.stop_atr_buffer if family == "bottom_breakdown_short" and np.isfinite(range_low) else signal_high + active_atr * config.stop_atr_buffer
        raw_risk = abs(entry_price - structure_stop)
        risk_points = max(raw_risk, active_atr * config.min_risk_atr, 0.25)
        initial_stop = entry_price - direction * risk_points
        target, target_plan = _structure_target(family, direction, entry_price, risk_points, range_high, range_low, config)

        best = float(high_prices[entry_index]) if direction > 0 else float(low_prices[entry_index])
        protective_stop = initial_stop
        exit_index = entry_index
        exit_price = float(close_prices[entry_index])
        exit_reason = "end_of_data"
        path_end = min(len(features) - 1, entry_index + config.max_hold_bars)
        path_start = min(len(features) - 1, entry_index + 1)
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
                    exit_index = path_index
                    exit_price = float(target)
                    exit_reason = "target"
                    break
                best = max(best, float(high_prices[path_index]))
                progress_r = (best - entry_price) / risk_points
                trail_stop = best - float(atr[path_index]) * config.trail_atr_mult if progress_r >= config.trail_start_r else initial_stop
                breakeven_stop = entry_price if progress_r >= config.breakeven_trigger_r else initial_stop
                protective_stop = max(initial_stop, trail_stop, breakeven_stop)
            else:
                if high_prices[path_index] >= protective_stop:
                    exit_index = path_index
                    exit_price = float(protective_stop)
                    exit_reason = "protective_stop"
                    break
                if path_index - entry_index >= config.min_hold_bars_before_target_exit and low_prices[path_index] <= target:
                    exit_index = path_index
                    exit_price = float(target)
                    exit_reason = "target"
                    break
                best = min(best, float(low_prices[path_index]))
                progress_r = (entry_price - best) / risk_points
                trail_stop = best + float(atr[path_index]) * config.trail_atr_mult if progress_r >= config.trail_start_r else initial_stop
                breakeven_stop = entry_price if progress_r >= config.breakeven_trigger_r else initial_stop
                protective_stop = min(initial_stop, trail_stop, breakeven_stop)
            if path_index >= path_end:
                exit_index = path_index
                exit_price = float(close_prices[path_index])
                exit_reason = "max_hold"
                break

        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points
        rows.append(
            {
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
        ("long_bias", ("top_breakout_long", "trend_ignition_long", "trend_pullback_long", "trend_transition_long", "reversal_impulse_long")),
        ("short_bias", ("bottom_breakdown_short", "top_reject_short", "trend_pullback_short", "trend_transition_short", "reversal_impulse_short")),
        ("all_lightglow", tuple(FAMILY_DIRECTIONS)),
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
