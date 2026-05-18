from __future__ import annotations

import argparse
import html
import sys
from dataclasses import dataclass
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

from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts


FAMILY_LABELS = {
    "bottom_breakdown_short": "BD",
    "top_breakout_long": "BO",
    "bottom_reclaim_long": "RC",
    "top_reject_short": "RJ",
    "trend_ignition_long": "TI_L",
    "trend_ignition_short": "TI_S",
    "trend_pullback_long": "PB_L",
    "trend_pullback_short": "PB_S",
    "trend_transition_long": "TS_L",
    "trend_transition_short": "TS_S",
    "reversal_impulse_long": "RI_L",
    "reversal_impulse_short": "RI_S",
}


@dataclass(frozen=True)
class BoundaryLightglowConfig:
    swing_length: int = 50
    premium_ratio: float = 0.95
    discount_ratio: float = 0.05
    signal_dedup: bool = True
    trade_pd_fallback: bool = False
    range_length: int = 90
    accept_bars: int = 3
    accept_atr_buffer: float = 0.15
    momentum_lookback: int = 30
    volume_length: int = 60
    body_atr_threshold: float = 0.60
    ignition_breakout_length: int = 14
    ignition_base_length: int = 45
    ignition_base_atr_max: float = 4.00
    ignition_range_pos_long_max: float = 0.45
    ignition_range_pos_short_min: float = 0.55
    ignition_body_atr_min: float = 0.35
    ignition_volume_z_min: float = -0.50
    trend_slope_lookback: int = 20
    pullback_lookback: int = 12
    pullback_atr_max: float = 2.50
    pullback_ema_atr_buffer: float = 0.35
    continuation_volume_z_min: float = -0.75
    transition_lookback: int = 20
    transition_body_atr_min: float = 0.40
    transition_volume_z_min: float = -0.50
    reversal_impulse_body_atr_min: float = 0.80
    reversal_impulse_volume_z_min: float = -0.25
    reversal_impulse_close_ratio: float = 0.70
    stop_atr_buffer: float = 1.25
    min_risk_atr: float = 0.80
    target_r: float = 1.80
    min_target_r: float = 1.00
    max_target_r: float = 3.00
    reversal_target_range_ratio: float = 0.50
    continuation_target_range_mult: float = 0.75
    breakeven_trigger_r: float = 1.50
    trail_start_r: float = 1.20
    trail_atr_mult: float = 2.00
    min_hold_bars_before_target_exit: int = 2
    max_hold_bars: int = 120
    cooldown_bars: int = 5
    max_trades_per_day: int = 8
    daily_stop_points: float = 80.0
    consecutive_loss_pause: int = 3
    pause_bars_after_loss_streak: int = 60


def load_nq_bars(args: argparse.Namespace) -> pd.DataFrame:
    loader_args = argparse.Namespace(
        start_date=args.start_date,
        end_date=args.end_date,
        cache=args.cache,
        chunk_size=args.chunk_size,
        min_volume=args.min_volume,
    )
    bars = load_continuous_nq_bars(loader_args)
    return bars.sort_values("ts").reset_index(drop=True)


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    previous_close = close.shift(1)
    true_range = pd.concat([(high - low), (high - previous_close).abs(), (low - previous_close).abs()], axis=1).max(axis=1)
    return true_range.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def pine_default_costs() -> BacktestCosts:
    """Match the TradingView strategy() defaults in the Pine script."""
    return BacktestCosts(slippage_ticks_per_side=2.0, commission_per_contract=10.0)


def add_features(bars: pd.DataFrame, config: BoundaryLightglowConfig) -> pd.DataFrame:
    frame = bars.copy().reset_index(drop=True)
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    high = frame["High"]
    low = frame["Low"]
    close = frame["Close"]
    open_ = frame["Open"]
    volume = frame["Volume"]

    frame["atr"] = _atr(high, low, close)
    frame["ema20"] = _ema(close, 20)
    frame["ema60"] = _ema(close, 60)
    frame["ema200"] = _ema(close, 200)
    frame["range_high"] = high.rolling(config.range_length, min_periods=config.range_length).max().shift(1)
    frame["range_low"] = low.rolling(config.range_length, min_periods=config.range_length).min().shift(1)
    frame["range_width"] = frame["range_high"] - frame["range_low"]
    frame["range_pos"] = (close - frame["range_low"]) / frame["range_width"].replace(0, np.nan)
    frame["volume_mean"] = volume.rolling(config.volume_length, min_periods=config.volume_length).mean()
    frame["volume_std"] = volume.rolling(config.volume_length, min_periods=config.volume_length).std()
    frame["volume_z"] = (volume - frame["volume_mean"]) / frame["volume_std"].replace(0, np.nan)
    frame["volume_z"] = frame["volume_z"].fillna(0.0)
    frame["momentum"] = close - close.shift(config.momentum_lookback)
    frame["body_atr"] = (close - open_).abs() / frame["atr"].replace(0, np.nan)

    below_range_low = close < frame["range_low"] - frame["atr"] * config.accept_atr_buffer
    above_range_high = close > frame["range_high"] + frame["atr"] * config.accept_atr_buffer
    frame["accepted_below_range"] = below_range_low.astype(int).rolling(config.accept_bars, min_periods=config.accept_bars).sum() >= config.accept_bars
    frame["accepted_above_range"] = above_range_high.astype(int).rolling(config.accept_bars, min_periods=config.accept_bars).sum() >= config.accept_bars
    frame["sweep_below_range"] = (low < frame["range_low"]) & (close > frame["range_low"])
    frame["sweep_above_range"] = (high > frame["range_high"]) & (close < frame["range_high"])

    frame["micro_breakout_high"] = high.rolling(config.ignition_breakout_length, min_periods=config.ignition_breakout_length).max().shift(1)
    frame["micro_breakdown_low"] = low.rolling(config.ignition_breakout_length, min_periods=config.ignition_breakout_length).min().shift(1)
    compression_high = high.rolling(config.ignition_base_length, min_periods=config.ignition_base_length).max().shift(1)
    compression_low = low.rolling(config.ignition_base_length, min_periods=config.ignition_base_length).min().shift(1)
    frame["compression_width_atr"] = (compression_high - compression_low) / frame["atr"].replace(0, np.nan)
    frame["compressed_base"] = frame["compression_width_atr"] <= config.ignition_base_atr_max
    frame["minute_of_day"] = frame["ts"].dt.hour * 60 + frame["ts"].dt.minute
    frame["trade_date"] = frame["ts"].dt.date
    minute = frame["minute_of_day"]
    frame["session"] = np.select(
        [
            (minute >= 7 * 60) & (minute < 13 * 60 + 30),
            (minute >= 13 * 60 + 30) & (minute < 20 * 60),
            (minute >= 20 * 60) & (minute < 23 * 60),
        ],
        ["europe", "us_rth", "us_late"],
        default="asia",
    )
    return frame


def build_signals(frame: pd.DataFrame, config: BoundaryLightglowConfig) -> pd.DataFrame:
    close = frame["Close"]
    open_ = frame["Open"]
    high = frame["High"]
    low = frame["Low"]
    atr = frame["atr"]
    ema20 = frame["ema20"]
    ema60 = frame["ema60"]
    ema200 = frame["ema200"]
    momentum = frame["momentum"]
    body_atr = frame["body_atr"]
    volume_z = frame["volume_z"]

    discount_reclaim = (
        frame["sweep_below_range"]
        & (close > open_)
        & (close > frame["range_low"])
        & (momentum > momentum.shift(1))
        & (body_atr >= config.body_atr_threshold * 0.5)
    )
    breakdown = (
        frame["accepted_below_range"]
        & (close < open_)
        & (ema20 < ema60)
        & (ema60 <= ema200)
        & (momentum < 0)
        & (volume_z >= 0)
        & (body_atr >= config.body_atr_threshold)
    )
    premium_reject = (
        frame["sweep_above_range"]
        & (close < open_)
        & (close < frame["range_high"])
        & (momentum < momentum.shift(1))
        & (body_atr >= config.body_atr_threshold * 0.5)
    )
    breakout = (
        frame["accepted_above_range"]
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
        frame["compressed_base"]
        & (frame["range_pos"] <= config.ignition_range_pos_long_max)
        & (close > frame["micro_breakout_high"])
        & ema_reclaim_long
        & (momentum > 0)
        & (volume_z >= config.ignition_volume_z_min)
        & (body_atr >= config.ignition_body_atr_min)
    )
    trend_ignition_short = (
        frame["compressed_base"]
        & (frame["range_pos"] >= config.ignition_range_pos_short_min)
        & (close < frame["micro_breakdown_low"])
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
    short_pullback_held = (high >= ema20 - atr * config.pullback_ema_atr_buffer) & (close < ema20) & (close < open_) & (high < ema60 + atr * config.pullback_ema_atr_buffer)
    trend_pullback_long = trend_up & long_pullback_held & (close > frame["micro_breakout_high"]) & (momentum > 0) & (volume_z >= config.continuation_volume_z_min) & (pullback_depth_long <= config.pullback_atr_max)
    trend_pullback_short = trend_down & short_pullback_held & (close < frame["micro_breakdown_low"]) & (momentum < 0) & (volume_z >= config.continuation_volume_z_min) & (pullback_depth_short <= config.pullback_atr_max)

    ema_bear_transition = (close < ema20) & (close < ema60) & (ema20 < ema20.shift(1)) & (close < low.rolling(config.transition_lookback, min_periods=config.transition_lookback).min().shift(1))
    ema_bull_transition = (close > ema20) & (close > ema60) & (ema20 > ema20.shift(1)) & (close > high.rolling(config.transition_lookback, min_periods=config.transition_lookback).max().shift(1))
    trend_transition_short = ema_bear_transition & (momentum < 0) & (volume_z >= config.transition_volume_z_min) & (body_atr >= config.transition_body_atr_min)
    trend_transition_long = ema_bull_transition & (momentum > 0) & (volume_z >= config.transition_volume_z_min) & (body_atr >= config.transition_body_atr_min)

    bar_range = high - low
    close_location = (close - low) / bar_range.replace(0, np.nan)
    reversal_impulse_long = (
        (frame["range_pos"] <= config.ignition_range_pos_long_max)
        & (close > open_)
        & (close > ema20)
        & (close > frame["micro_breakout_high"])
        & (momentum > 0)
        & (volume_z >= config.reversal_impulse_volume_z_min)
        & (body_atr >= config.reversal_impulse_body_atr_min)
        & (close_location >= config.reversal_impulse_close_ratio)
    )
    reversal_impulse_short = (
        (frame["range_pos"] >= config.ignition_range_pos_short_min)
        & (close < open_)
        & (close < ema20)
        & (close < frame["micro_breakdown_low"])
        & (momentum < 0)
        & (volume_z >= config.reversal_impulse_volume_z_min)
        & (body_atr >= config.reversal_impulse_body_atr_min)
        & (close_location <= 1.0 - config.reversal_impulse_close_ratio)
    )

    candidates: list[tuple[str, int, pd.Series]] = [
        ("top_breakout_long", 1, breakout & frame["session"].eq("us_rth")),
        ("trend_ignition_long", 1, trend_ignition_long & frame["session"].eq("europe")),
    ]
    signal_family = pd.Series("", index=frame.index, dtype=object)
    signal_direction = pd.Series(0, index=frame.index, dtype=np.int8)
    for family, direction, condition in candidates:
        signal = condition.fillna(False) & ~condition.fillna(False).shift(1, fill_value=False)
        mask = signal & signal_direction.eq(0)
        signal_family.loc[mask] = family
        signal_direction.loc[mask] = direction

    output = frame.copy()
    output["signal_family"] = signal_family
    output["signal_direction"] = signal_direction
    return output


def _structure_target(family: str, direction: int, entry_price: float, risk_points: float, range_high: float, range_low: float, config: BoundaryLightglowConfig) -> tuple[float, str]:
    fixed = entry_price + direction * risk_points * config.target_r
    if not np.isfinite(range_high) or not np.isfinite(range_low) or range_high <= range_low:
        return fixed, "fixed_r"
    width = range_high - range_low
    candidate = np.nan
    if family == "bottom_reclaim_long":
        candidate = range_low + width * config.reversal_target_range_ratio
    elif family == "top_reject_short":
        candidate = range_high - width * config.reversal_target_range_ratio
    elif family in {"top_breakout_long", "trend_pullback_long"}:
        candidate = range_high + width * config.continuation_target_range_mult
    elif family in {"bottom_breakdown_short", "trend_pullback_short"}:
        candidate = range_low - width * config.continuation_target_range_mult
    elif family in {"trend_ignition_long", "trend_transition_long", "reversal_impulse_long"}:
        candidate = range_high
    elif family in {"trend_ignition_short", "trend_transition_short", "reversal_impulse_short"}:
        candidate = range_low
    distance = (candidate - entry_price) * direction
    if not np.isfinite(candidate) or distance < risk_points * config.min_target_r:
        return fixed, "fixed_r"
    max_target = entry_price + direction * risk_points * config.max_target_r
    target = min(candidate, max_target) if direction > 0 else max(candidate, max_target)
    if family in {"bottom_reclaim_long", "top_reject_short"}:
        plan = "reversal_midrange"
    elif family in {"trend_pullback_long", "trend_pullback_short"}:
        plan = "trend_pullback_extension"
    elif family in {"top_breakout_long", "bottom_breakdown_short"}:
        plan = "continuation_extension"
    else:
        plan = "trend_range_target"
    return float(target), plan


def backtest_strategy(
    frame: pd.DataFrame,
    config: BoundaryLightglowConfig,
    costs: BacktestCosts,
    *,
    enabled_families: set[str] | None = None,
    enabled_family_sessions: set[tuple[str, str]] | None = None,
    use_risk_controls: bool = False,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    open_prices = frame["Open"].to_numpy(dtype=float)
    high_prices = frame["High"].to_numpy(dtype=float)
    low_prices = frame["Low"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    atr = frame["atr"].to_numpy(dtype=float)
    symbols = frame["symbol"].astype(str).to_numpy()
    families = frame["signal_family"].astype(str).to_numpy()
    sessions = frame["session"].astype(str).to_numpy()
    directions = frame["signal_direction"].to_numpy(dtype=int)

    last_exit_index = -10**9
    pause_until = -1
    consecutive_losses = 0
    day_state: dict[Any, dict[str, float]] = {}
    index = 0
    while index < len(frame) - 2:
        family = families[index]
        session = sessions[index]
        direction = int(directions[index])
        if not family or direction == 0 or (enabled_families is not None and family not in enabled_families):
            index += 1
            continue
        if enabled_family_sessions is not None and (family, session) not in enabled_family_sessions:
            index += 1
            continue
        entry_index = index + 1
        if entry_index <= last_exit_index + config.cooldown_bars or entry_index <= pause_until or entry_index >= len(frame):
            index += 1
            continue
        if symbols[entry_index] != symbols[index]:
            index += 1
            continue
        trade_day = frame["trade_date"].iat[entry_index]
        state = day_state.setdefault(trade_day, {"trades": 0.0, "net": 0.0})
        if use_risk_controls and (state["trades"] >= config.max_trades_per_day or state["net"] <= -config.daily_stop_points):
            index += 1
            continue

        entry_price = float(open_prices[entry_index])
        signal_high = float(high_prices[index])
        signal_low = float(low_prices[index])
        active_atr = float(atr[index]) if np.isfinite(atr[index]) and atr[index] > 0 else float(atr[entry_index])
        if not np.isfinite(active_atr) or active_atr <= 0:
            index += 1
            continue

        range_high = float(frame["range_high"].iat[index])
        range_low = float(frame["range_low"].iat[index])
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
        path_end = min(len(frame) - 1, entry_index + config.max_hold_bars)
        path_start = min(len(frame) - 1, entry_index + 1)
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
                "signal_ts": frame["ts"].iat[index],
                "entry_ts": frame["ts"].iat[entry_index],
                "exit_ts": frame["ts"].iat[exit_index],
                "symbol": symbols[entry_index],
                "signal_family": family,
                "session": session,
                "signal_label": FAMILY_LABELS.get(family, family),
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
        if use_risk_controls and consecutive_losses >= config.consecutive_loss_pause:
            pause_until = exit_index + config.pause_bars_after_loss_streak
            consecutive_losses = 0
        last_exit_index = exit_index
        index = exit_index + 1
    return pd.DataFrame(rows)


def summarize(trades: pd.DataFrame) -> dict[str, float | int]:
    if trades.empty:
        return {"trades": 0, "net_points": 0.0, "profit_factor": 0.0, "win_rate": 0.0, "avg_points": 0.0, "max_drawdown_points": 0.0, "worst_trade_points": 0.0}
    net = trades["net_points"].astype(float)
    equity = net.cumsum()
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


def group_summary(trades: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows = []
    for key, group in trades.groupby(group_columns, dropna=False):
        row: dict[str, Any] = {}
        if not isinstance(key, tuple):
            key = (key,)
        for column, value in zip(group_columns, key):
            row[column] = value
        row.update(summarize(group))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("net_points", ascending=False)


def select_enabled_families(train_trades: pd.DataFrame, *, min_trades: int, min_pf: float, min_avg: float) -> set[str]:
    summary_frame = group_summary(train_trades, ["signal_family"])
    if summary_frame.empty:
        return set()
    selected = summary_frame[
        (summary_frame["trades"] >= min_trades)
        & (summary_frame["profit_factor"] >= min_pf)
        & (summary_frame["avg_points"] >= min_avg)
        & (summary_frame["net_points"] > 0)
    ]
    return set(selected["signal_family"].astype(str))


def select_enabled_family_sessions(train_trades: pd.DataFrame, *, min_trades: int, min_pf: float, min_avg: float) -> set[tuple[str, str]]:
    summary_frame = group_summary(train_trades, ["signal_family", "session"])
    if summary_frame.empty:
        return set()
    selected = summary_frame[
        (summary_frame["trades"] >= min_trades)
        & (summary_frame["profit_factor"] >= min_pf)
        & (summary_frame["avg_points"] >= min_avg)
        & (summary_frame["net_points"] > 0)
    ]
    return set(zip(selected["signal_family"].astype(str), selected["session"].astype(str)))


def evaluate_independent_family_sessions(
    features: pd.DataFrame,
    config: BoundaryLightglowConfig,
    costs: BacktestCosts,
    *,
    train_end: str,
) -> pd.DataFrame:
    pairs = sorted(
        {
            (str(row.signal_family), str(row.session))
            for row in features.loc[features["signal_direction"].ne(0), ["signal_family", "session"]].itertuples(index=False)
            if str(row.signal_family)
        }
    )
    rows: list[dict[str, Any]] = []
    cutoff = pd.Timestamp(train_end, tz="UTC")
    for family, session in pairs:
        trades = backtest_strategy(features, config, costs, enabled_family_sessions={(family, session)}, use_risk_controls=False)
        if trades.empty:
            continue
        entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)
        for period, group in (("train", trades.loc[entry_ts < cutoff]), ("oos", trades.loc[entry_ts >= cutoff])):
            row = {"signal_family": family, "session": session, "period": period}
            row.update(summarize(group))
            rows.append(row)
    return pd.DataFrame(rows)


def cell_train_year_stability(
    features: pd.DataFrame,
    config: BoundaryLightglowConfig,
    costs: BacktestCosts,
    *,
    train_end: str,
) -> pd.DataFrame:
    pairs = sorted(
        {
            (str(row.signal_family), str(row.session))
            for row in features.loc[features["signal_direction"].ne(0), ["signal_family", "session"]].itertuples(index=False)
            if str(row.signal_family)
        }
    )
    cutoff = pd.Timestamp(train_end, tz="UTC")
    rows: list[dict[str, Any]] = []
    for family, session in pairs:
        trades = backtest_strategy(features, config, costs, enabled_family_sessions={(family, session)}, use_risk_controls=False)
        if trades.empty:
            continue
        trades = trades.copy()
        trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
        trades = trades[trades["entry_ts"] < cutoff]
        if trades.empty:
            continue
        yearly = group_summary(trades.assign(year=trades["entry_ts"].dt.year), ["year"])
        positive_years = int((yearly["net_points"] > 0).sum()) if not yearly.empty else 0
        rows.append(
            {
                "signal_family": family,
                "session": session,
                "train_years": int(len(yearly)),
                "positive_train_years": positive_years,
                "positive_train_year_rate": float(positive_years / len(yearly)) if len(yearly) else 0.0,
                "worst_train_year_points": float(yearly["net_points"].min()) if not yearly.empty else 0.0,
            }
        )
    return pd.DataFrame(rows)


def select_enabled_from_independent_cells(
    cell_evaluation: pd.DataFrame,
    *,
    min_trades: int,
    min_pf: float,
    min_avg: float,
    stability: pd.DataFrame | None = None,
    min_positive_year_rate: float = 0.0,
    min_worst_year_points: float | None = None,
) -> set[tuple[str, str]]:
    if cell_evaluation.empty:
        return set()
    train = cell_evaluation[cell_evaluation["period"].astype(str).eq("train")].copy()
    selected = train[
        (train["trades"] >= min_trades)
        & (train["profit_factor"] >= min_pf)
        & (train["avg_points"] >= min_avg)
        & (train["net_points"] > 0)
    ]
    if stability is not None and not stability.empty and not selected.empty:
        selected = selected.merge(stability, on=["signal_family", "session"], how="left")
        selected = selected[selected["positive_train_year_rate"].fillna(0.0) >= min_positive_year_rate]
        if min_worst_year_points is not None:
            selected = selected[selected["worst_train_year_points"].fillna(-np.inf) >= min_worst_year_points]
    return set(zip(selected["signal_family"].astype(str), selected["session"].astype(str)))


def run_walk_forward(
    features: pd.DataFrame,
    config: BoundaryLightglowConfig,
    costs: BacktestCosts,
    *,
    start_year: int,
    end_year: int,
    train_years: int,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    trade_parts: list[pd.DataFrame] = []
    selection_rows: list[dict[str, Any]] = []
    for test_year in range(start_year, end_year + 1):
        train_start = f"{test_year - train_years}-01-01"
        train_end = f"{test_year}-01-01"
        test_start = pd.Timestamp(f"{test_year}-01-01", tz="UTC")
        test_end = pd.Timestamp(f"{test_year + 1}-01-01", tz="UTC")
        train_features = features[(features["ts"] >= pd.Timestamp(train_start, tz="UTC")) & (features["ts"] < pd.Timestamp(train_end, tz="UTC"))]
        if train_features.empty:
            continue
        cell_eval = evaluate_independent_family_sessions(train_features, config, costs, train_end=train_end)
        stability = cell_train_year_stability(train_features, config, costs, train_end=train_end)
        enabled = select_enabled_from_independent_cells(
            cell_eval,
            min_trades=args.min_cell_trades,
            min_pf=args.min_cell_pf,
            min_avg=args.min_cell_avg,
            stability=stability,
            min_positive_year_rate=args.min_positive_train_year_rate,
            min_worst_year_points=args.min_worst_train_year_points,
        )
        selection_rows.append(
            {
                "test_year": test_year,
                "train_start": train_start,
                "train_end": train_end,
                "enabled_cells": ", ".join(f"{family}@{session}" for family, session in sorted(enabled)),
                "enabled_count": len(enabled),
            }
        )
        if not enabled:
            continue
        trades = backtest_strategy(features, config, costs, enabled_family_sessions=enabled, use_risk_controls=True)
        if trades.empty:
            continue
        entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)
        trades = trades[(entry_ts >= test_start) & (entry_ts < test_end)].copy()
        if not trades.empty:
            trades["test_year"] = test_year
            trade_parts.append(trades)
    return (
        pd.concat(trade_parts, ignore_index=True) if trade_parts else pd.DataFrame(),
        pd.DataFrame(selection_rows),
    )


def _fmt(value: object) -> str:
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, float):
        return f"{value:,.4f}"
    return str(value)


def html_table(frame: pd.DataFrame, columns: list[str], *, limit: int | None = None) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    data = frame[columns].head(limit) if limit else frame[columns]
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for _, row in data.iterrows():
        body.append("<tr>" + "".join(f"<td>{html.escape(_fmt(row[column]))}</td>" for column in columns) + "</tr>")
    return f"<div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"


def write_report(path: Path, *, pine_default: pd.DataFrame, baseline_oos: pd.DataFrame, optimized_oos: pd.DataFrame, train_summary: pd.DataFrame, train_session_summary: pd.DataFrame, independent_cells: pd.DataFrame, stability: pd.DataFrame, walk_forward_selections: pd.DataFrame, family_summary: pd.DataFrame, session_summary: pd.DataFrame, yearly: pd.DataFrame, enabled_pairs: set[tuple[str, str]], args: argparse.Namespace, costs: BacktestCosts) -> None:
    comparison = pd.DataFrame(
        [
            {"variant": "pine_default_full_period", **summarize(pine_default)},
            {"variant": "oos_baseline_all_families", **summarize(baseline_oos)},
            {"variant": "diagnostic_walk_forward_selected_cells", **summarize(optimized_oos)},
        ]
    )
    enabled_text = ", ".join(f"{family}@{session}" for family, session in sorted(enabled_pairs))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>NQ Boundary Lightglow Strategy Databento Backtest</title>
  <style>
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:#f8fafc; color:#111827; }}
    header, main {{ max-width:1180px; margin:0 auto; padding:24px; }}
    header {{ max-width:none; background:#0f172a; color:white; }}
    header > * {{ max-width:1180px; margin-left:auto; margin-right:auto; }}
    section {{ background:white; border:1px solid #e5e7eb; border-radius:8px; padding:18px; margin:16px 0; }}
    table {{ border-collapse:collapse; width:100%; font-size:13px; }}
    th, td {{ padding:7px 9px; border-bottom:1px solid #e5e7eb; text-align:left; }}
    th {{ background:#f1f5f9; }}
    .table-wrap {{ overflow-x:auto; }}
    code {{ background:#e5e7eb; padding:2px 4px; border-radius:4px; }}
  </style>
</head>
<body>
  <header>
    <h1>NQ Boundary Lightglow Strategy Databento Backtest</h1>
    <p>Period: {html.escape(args.start_date)} to {html.escape(args.end_date)}. Train cutoff: {html.escape(args.train_end)}. Cost: {costs.round_trip_cost_points:.4f} points/round trip, aligned to Pine <code>slippage=2</code> and <code>commission_value=5</code>.</p>
  </header>
  <main>
    <section>
      <h2>Optimization Principle</h2>
      <p><strong>Main result is the current Pine default core set.</strong> It now concentrates on the cells that survive Databento validation after pruning the late-session reversal-impulse short drag: `top_breakout_long@us_rth` plus a small `trend_ignition_long@europe` tail. ATR uses TradingView-style Wilder/RMA and costs match Pine defaults.</p>
      <p>The walk-forward selected-cell result remains a diagnostic overlay. It is useful for research, but the headline should be the narrowed Pine default core, not the old all-family basket.</p>
      <p><strong>Fixed-cutoff diagnostic cells:</strong> {html.escape(enabled_text if enabled_text else "none")}.</p>
    </section>
    <section><h2>Pine Strategy Result</h2>{html_table(comparison, ["variant", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points", "worst_trade_points"])}</section>
    <section><h2>Training Family Attribution</h2>{html_table(train_summary, ["signal_family", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points", "worst_trade_points"], limit=30)}</section>
    <section><h2>Training Family x Session Selection</h2>{html_table(train_session_summary, ["signal_family", "session", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points", "worst_trade_points"], limit=40)}</section>
    <section><h2>Independent Cell Evaluation</h2>{html_table(independent_cells, ["signal_family", "session", "period", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points", "worst_trade_points"], limit=80)}</section>
    <section><h2>Train-Year Stability</h2>{html_table(stability, ["signal_family", "session", "train_years", "positive_train_years", "positive_train_year_rate", "worst_train_year_points"], limit=80)}</section>
    <section><h2>Walk-Forward Selections</h2>{html_table(walk_forward_selections, ["test_year", "train_start", "train_end", "enabled_count", "enabled_cells"])}</section>
    <section><h2>Optimized Family Attribution</h2>{html_table(family_summary, ["signal_family", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points", "worst_trade_points"], limit=30)}</section>
    <section><h2>Optimized Family x Session Attribution</h2>{html_table(session_summary, ["signal_family", "session", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points", "worst_trade_points"], limit=40)}</section>
    <section><h2>Optimized Yearly Results</h2>{html_table(yearly, ["year", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points", "worst_trade_points"])}</section>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest and optimize current NQ Boundary Lightglow Pine strategy on Databento 1m bars.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--train-end", default="2023-01-01")
    parser.add_argument("--cache", default=".tmp/nq-boundary-lightglow-bars.pkl")
    parser.add_argument("--chunk-size", type=int, default=200_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--min-family-trades", type=int, default=50)
    parser.add_argument("--min-family-pf", type=float, default=1.05)
    parser.add_argument("--min-family-avg", type=float, default=0.0)
    parser.add_argument("--min-cell-trades", type=int, default=50)
    parser.add_argument("--min-cell-pf", type=float, default=1.12)
    parser.add_argument("--min-cell-avg", type=float, default=0.70)
    parser.add_argument("--min-positive-train-year-rate", type=float, default=0.67)
    parser.add_argument("--min-worst-train-year-points", type=float, default=-150.0)
    parser.add_argument("--walk-forward-start-year", type=int, default=2023)
    parser.add_argument("--walk-forward-end-year", type=int, default=2026)
    parser.add_argument("--walk-forward-train-years", type=int, default=3)
    parser.add_argument("--skip-diagnostics", action="store_true", help="Only run the Pine-default full-period backtest and omit Python-only selection diagnostics.")
    parser.add_argument("--trades-output", default=".tmp/nq-boundary-lightglow-optimized-trades.csv")
    parser.add_argument("--baseline-output", default=".tmp/nq-boundary-lightglow-baseline-trades.csv")
    parser.add_argument("--report", default="reports/NQ-boundary-lightglow-strategy-databento-backtest.html")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = BoundaryLightglowConfig()
    costs = pine_default_costs()
    bars = load_nq_bars(args)
    features = build_signals(add_features(bars, config), config)
    baseline = backtest_strategy(features, config, costs)
    entry_ts = pd.to_datetime(baseline["entry_ts"], utc=True) if not baseline.empty else pd.Series(dtype="datetime64[ns, UTC]")
    train_mask = entry_ts < pd.Timestamp(args.train_end, tz="UTC") if not baseline.empty else pd.Series(dtype=bool)
    oos_mask = entry_ts >= pd.Timestamp(args.train_end, tz="UTC") if not baseline.empty else pd.Series(dtype=bool)
    train_trades = baseline.loc[train_mask].copy() if not baseline.empty else baseline
    baseline_oos = baseline.loc[oos_mask].copy() if not baseline.empty else baseline
    if args.skip_diagnostics:
        enabled: set[str] = set()
        cell_evaluation = pd.DataFrame()
        stability = pd.DataFrame()
        enabled_pairs: set[tuple[str, str]] = set()
        optimized = pd.DataFrame()
        walk_forward_selections = pd.DataFrame()
    else:
        enabled = select_enabled_families(train_trades, min_trades=args.min_family_trades, min_pf=args.min_family_pf, min_avg=args.min_family_avg)
        cell_evaluation = evaluate_independent_family_sessions(features, config, costs, train_end=args.train_end)
        stability = cell_train_year_stability(features, config, costs, train_end=args.train_end)
        enabled_pairs = select_enabled_from_independent_cells(
            cell_evaluation,
            min_trades=args.min_cell_trades,
            min_pf=args.min_cell_pf,
            min_avg=args.min_cell_avg,
            stability=stability,
            min_positive_year_rate=args.min_positive_train_year_rate,
            min_worst_year_points=args.min_worst_train_year_points,
        )
        optimized, walk_forward_selections = run_walk_forward(
            features,
            config,
            costs,
            start_year=args.walk_forward_start_year,
            end_year=args.walk_forward_end_year,
            train_years=args.walk_forward_train_years,
            args=args,
        )
    baseline_path = ROOT_DIR / args.baseline_output
    optimized_path = ROOT_DIR / args.trades_output
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    optimized_path.parent.mkdir(parents=True, exist_ok=True)
    baseline.to_csv(baseline_path, index=False)
    optimized.to_csv(optimized_path, index=False)
    train_summary = group_summary(train_trades, ["signal_family"])
    train_session_summary = group_summary(train_trades, ["signal_family", "session"])
    family_summary = group_summary(optimized, ["signal_family"])
    session_summary = group_summary(optimized, ["signal_family", "session"])
    yearly = group_summary(optimized.assign(year=pd.to_datetime(optimized["entry_ts"], utc=True).dt.year) if not optimized.empty else optimized, ["year"])
    independent_display = cell_evaluation.sort_values(["period", "net_points"], ascending=[True, False]) if not cell_evaluation.empty else cell_evaluation
    stability_display = stability.sort_values(["positive_train_year_rate", "worst_train_year_points"], ascending=[False, False]) if not stability.empty else stability
    write_report(ROOT_DIR / args.report, pine_default=baseline, baseline_oos=baseline_oos, optimized_oos=optimized, train_summary=train_summary, train_session_summary=train_session_summary, independent_cells=independent_display, stability=stability_display, walk_forward_selections=walk_forward_selections, family_summary=family_summary, session_summary=session_summary, yearly=yearly, enabled_pairs=enabled_pairs, args=args, costs=costs)
    print("pine_default_full_period", summarize(baseline))
    print("baseline_oos", summarize(baseline_oos))
    print("enabled_families", sorted(enabled))
    print("enabled_family_sessions", sorted(enabled_pairs))
    print("optimized_oos", summarize(optimized))
    print(f"wrote {args.trades_output}")
    print(f"wrote {args.report}")


if __name__ == "__main__":
    main()
