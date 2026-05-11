from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.dataflows.databento import _bar_zip_path


BULLISH = 1
BEARISH = -1


@dataclass(frozen=True)
class RangeCandidate:
    signal: str
    lookback: int
    width_atr_mult: float
    max_efficiency: float
    session: str
    direction_filter: str
    reward_risk: float
    max_hold_minutes: int
    stop_mode: str

    @property
    def name(self) -> str:
        return (
            f"range_{self.signal}_lb{self.lookback}_w{self.width_atr_mult:g}"
            f"_eff{self.max_efficiency:g}_{self.session}_{self.direction_filter}"
            f"_rr{self.reward_risk:g}_h{self.max_hold_minutes}_{self.stop_mode}"
        )


def add_range_structure_features(features: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    frame = features[["ts", "symbol", "Open", "High", "Low", "Close", "Volume"]].copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values("ts").reset_index(drop=True)
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["trade_date"] = frame["ts"].dt.date
    frame["minute_of_day"] = frame["ts"].dt.hour * 60 + frame["ts"].dt.minute

    high = frame["High"]
    low = frame["Low"]
    close = frame["Close"]
    open_price = frame["Open"]
    volume = frame["Volume"]
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    frame["true_range"] = true_range
    frame["atr_30"] = true_range.rolling(30, min_periods=10).mean()
    frame["atr_120"] = true_range.rolling(120, min_periods=30).mean()
    frame["range_points"] = high - low
    frame["body_points"] = (close - open_price).abs()
    frame["body_share"] = frame["body_points"] / frame["range_points"].replace(0, np.nan)
    frame["upper_wick"] = high - pd.concat([open_price, close], axis=1).max(axis=1)
    frame["lower_wick"] = pd.concat([open_price, close], axis=1).min(axis=1) - low
    frame["volume_z_60"] = (volume - volume.rolling(60, min_periods=20).mean()) / volume.rolling(
        60, min_periods=20
    ).std()
    cumulative_pv = (close * volume).groupby(frame["trade_date"]).cumsum()
    cumulative_volume = volume.replace(0, np.nan).groupby(frame["trade_date"]).cumsum()
    frame["session_vwap"] = cumulative_pv / cumulative_volume

    for lookback in sorted(set(args.lookbacks)):
        roll_high = high.rolling(lookback, min_periods=lookback).max().shift(1)
        roll_low = low.rolling(lookback, min_periods=lookback).min().shift(1)
        roll_width = roll_high - roll_low
        tr_sum = true_range.rolling(lookback, min_periods=lookback).sum().shift(1)
        net_move = (close.shift(1) - close.shift(lookback + 1)).abs()
        efficiency = net_move / tr_sum.replace(0, np.nan)
        frame[f"range_high_{lookback}"] = roll_high
        frame[f"range_low_{lookback}"] = roll_low
        frame[f"range_mid_{lookback}"] = (roll_high + roll_low) / 2.0
        frame[f"range_width_{lookback}"] = roll_width
        frame[f"range_efficiency_{lookback}"] = efficiency

    return frame.dropna(subset=["Open", "High", "Low", "Close"]).reset_index(drop=True)


def session_mask(frame: pd.DataFrame, session: str) -> pd.Series:
    minute = frame["minute_of_day"]
    if session == "all":
        return pd.Series(True, index=frame.index)
    if session == "europe":
        return (minute >= 7 * 60) & (minute < 13 * 60 + 30)
    if session == "us_rth":
        return (minute >= 13 * 60 + 30) & (minute < 20 * 60)
    if session == "us_late":
        return (minute >= 20 * 60) & (minute < 23 * 60)
    if session == "ldn_ny":
        return (minute >= 7 * 60) & (minute < 20 * 60)
    if session == "asia":
        return (minute < 7 * 60) | (minute >= 23 * 60)
    raise ValueError(f"unknown session: {session}")


def range_ok(frame: pd.DataFrame, candidate: RangeCandidate, args: argparse.Namespace) -> pd.Series:
    width = frame[f"range_width_{candidate.lookback}"]
    efficiency = frame[f"range_efficiency_{candidate.lookback}"]
    atr = frame["atr_120"].replace(0, np.nan)
    return (
        width.notna()
        & atr.notna()
        & (width >= args.min_range_points)
        & (width <= candidate.width_atr_mult * atr)
        & (efficiency <= candidate.max_efficiency)
    )


def signal_series(frame: pd.DataFrame, candidate: RangeCandidate, args: argparse.Namespace) -> pd.Series:
    high = frame["High"]
    low = frame["Low"]
    close = frame["Close"]
    open_price = frame["Open"]
    range_high = frame[f"range_high_{candidate.lookback}"]
    range_low = frame[f"range_low_{candidate.lookback}"]
    range_mid = frame[f"range_mid_{candidate.lookback}"]
    atr = frame["atr_30"].replace(0, np.nan)
    buffer_points = (args.breakout_buffer_atr * atr).clip(lower=args.min_buffer_points)
    tolerance = (args.retest_tolerance_atr * atr).clip(lower=args.min_buffer_points)
    in_range = range_ok(frame, candidate, args)
    displacement = (
        (frame["range_points"] >= args.displacement_atr_mult * atr)
        & (frame["body_share"] >= args.min_body_share)
        & (frame["volume_z_60"].fillna(0.0) >= args.min_volume_z)
    )

    values = np.zeros(len(frame), dtype=np.int8)
    if candidate.signal == "breakout_close":
        long_signal = in_range & displacement & (close > range_high + buffer_points)
        short_signal = in_range & displacement & (close < range_low - buffer_points)
    elif candidate.signal == "fvg_breakout":
        bullish_fvg = (low > high.shift(2)) & (close.shift(1) > high.shift(2))
        bearish_fvg = (high < low.shift(2)) & (close.shift(1) < low.shift(2))
        long_signal = in_range & bullish_fvg & displacement.shift(1).fillna(False) & (close > range_high)
        short_signal = in_range & bearish_fvg & displacement.shift(1).fillna(False) & (close < range_low)
    elif candidate.signal == "sweep_reclaim":
        top_sweep = in_range & (high > range_high + buffer_points) & (close < range_high) & (close < open_price)
        bottom_sweep = in_range & (low < range_low - buffer_points) & (close > range_low) & (close > open_price)
        long_signal = bottom_sweep
        short_signal = top_sweep
    elif candidate.signal == "boundary_pin":
        top_pin = (
            in_range
            & (high >= range_high - tolerance)
            & (frame["upper_wick"] >= args.pin_wick_body_mult * frame["body_points"].clip(lower=0.25))
            & (close < open_price)
            & (close <= range_mid)
        )
        bottom_pin = (
            in_range
            & (low <= range_low + tolerance)
            & (frame["lower_wick"] >= args.pin_wick_body_mult * frame["body_points"].clip(lower=0.25))
            & (close > open_price)
            & (close >= range_mid)
        )
        long_signal = bottom_pin
        short_signal = top_pin
    elif candidate.signal == "breakout_retest":
        return breakout_retest_signal(frame, candidate, in_range, displacement, args)
    else:
        raise ValueError(f"unknown signal: {candidate.signal}")

    values[np.asarray(long_signal.fillna(False), dtype=bool)] = BULLISH
    values[np.asarray(short_signal.fillna(False), dtype=bool)] = BEARISH
    return pd.Series(values, index=frame.index)


def breakout_retest_signal(
    frame: pd.DataFrame,
    candidate: RangeCandidate,
    in_range: pd.Series,
    displacement: pd.Series,
    args: argparse.Namespace,
) -> pd.Series:
    high = frame["High"].to_numpy(dtype=float)
    low = frame["Low"].to_numpy(dtype=float)
    close = frame["Close"].to_numpy(dtype=float)
    range_high = frame[f"range_high_{candidate.lookback}"].to_numpy(dtype=float)
    range_low = frame[f"range_low_{candidate.lookback}"].to_numpy(dtype=float)
    atr = frame["atr_30"].replace(0, np.nan).to_numpy(dtype=float)
    buffer_points = np.maximum(args.breakout_buffer_atr * atr, args.min_buffer_points)
    tolerance = np.maximum(args.retest_tolerance_atr * atr, args.min_buffer_points)
    base = np.asarray((in_range & displacement).fillna(False), dtype=bool)
    long_breakouts = np.flatnonzero(base & (close > range_high + buffer_points))
    short_breakouts = np.flatnonzero(base & (close < range_low - buffer_points))
    values = np.zeros(len(frame), dtype=np.int8)

    for source_indexes, direction in [(long_breakouts, BULLISH), (short_breakouts, BEARISH)]:
        for source_index in source_indexes:
            if source_index + 1 >= len(frame):
                continue
            if direction > 0:
                level = range_high[source_index]
            else:
                level = range_low[source_index]
            if not np.isfinite(level):
                continue
            for target_index in range(source_index + 1, min(len(frame), source_index + args.retest_window_minutes + 1)):
                if direction > 0:
                    retested = low[target_index] <= level + tolerance[target_index]
                    reclaimed = close[target_index] > level
                else:
                    retested = high[target_index] >= level - tolerance[target_index]
                    reclaimed = close[target_index] < level
                if retested and reclaimed:
                    values[target_index] = direction
                    break
    return pd.Series(values, index=frame.index)


def candidate_pool(args: argparse.Namespace) -> list[RangeCandidate]:
    return [
        RangeCandidate(
            signal=signal,
            lookback=int(lookback),
            width_atr_mult=float(width_mult),
            max_efficiency=float(efficiency),
            session=session,
            direction_filter=direction,
            reward_risk=float(reward_risk),
            max_hold_minutes=int(max_hold),
            stop_mode=stop_mode,
        )
        for signal in args.signals
        for lookback in args.lookbacks
        for width_mult in args.range_width_atr_mults
        for efficiency in args.max_efficiencies
        for session in args.sessions
        for direction in args.direction_filters
        for reward_risk in args.reward_risks
        for max_hold in args.max_hold_minutes
        for stop_mode in args.stop_modes
    ]


def build_trades(frame: pd.DataFrame, candidate: RangeCandidate, args: argparse.Namespace, costs: BacktestCosts) -> pd.DataFrame:
    signal = signal_series(frame, candidate, args)
    signal = signal.where(session_mask(frame, candidate.session), 0)
    if candidate.direction_filter == "long":
        signal = signal.where(signal > 0, 0)
    elif candidate.direction_filter == "short":
        signal = signal.where(signal < 0, 0)
    elif candidate.direction_filter != "both":
        raise ValueError(f"unknown direction filter: {candidate.direction_filter}")
    signal = signal.where(signal != signal.shift(1), 0)
    signal_values = signal.to_numpy(dtype=np.int8)
    signal_indexes = np.flatnonzero(signal_values != 0)
    if len(signal_indexes) == 0:
        return pd.DataFrame()

    open_prices = frame["Open"].to_numpy(dtype=float)
    high_prices = frame["High"].to_numpy(dtype=float)
    low_prices = frame["Low"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    timestamps = frame["ts"].to_numpy()
    symbols = frame["symbol"].astype(str).to_numpy()
    symbol_codes = pd.factorize(frame["symbol"].astype(str), sort=False)[0]
    range_high = frame[f"range_high_{candidate.lookback}"].to_numpy(dtype=float)
    range_low = frame[f"range_low_{candidate.lookback}"].to_numpy(dtype=float)
    range_mid = frame[f"range_mid_{candidate.lookback}"].to_numpy(dtype=float)
    atr = frame["atr_30"].replace(0, np.nan).to_numpy(dtype=float)
    entry_indexes = signal_indexes + 1
    timeout_indexes = signal_indexes + candidate.max_hold_minutes
    valid = (entry_indexes < len(frame)) & (timeout_indexes < len(frame))
    if not valid.any():
        return pd.DataFrame()

    signal_indexes = signal_indexes[valid]
    entry_indexes = entry_indexes[valid]
    timeout_indexes = timeout_indexes[valid]
    directions = signal_values[signal_indexes].astype(np.int8, copy=False)
    entry_prices = open_prices[entry_indexes]
    stop_distances = stop_distance_points_vectorized(
        candidate,
        args,
        directions,
        entry_prices,
        signal_indexes,
        high_prices,
        low_prices,
        range_high,
        range_low,
        range_mid,
        atr,
    )
    finite = (
        np.isfinite(entry_prices)
        & np.isfinite(stop_distances)
        & (stop_distances >= args.min_stop_points)
        & (stop_distances <= args.max_stop_points)
        & (directions != 0)
    )
    if not finite.any():
        return pd.DataFrame()

    signal_indexes = signal_indexes[finite]
    entry_indexes = entry_indexes[finite]
    timeout_indexes = timeout_indexes[finite]
    directions = directions[finite].astype(int, copy=False)
    entry_prices = entry_prices[finite]
    stop_distances = stop_distances[finite]

    realized_exit_indexes = np.empty(len(signal_indexes), dtype=int)
    exit_prices = np.empty(len(signal_indexes), dtype=float)
    exit_reason_codes = np.empty(len(signal_indexes), dtype=np.int8)
    offsets = np.arange(1, candidate.max_hold_minutes + 1, dtype=int)
    chunk_size = 50_000
    for start in range(0, len(signal_indexes), chunk_size):
        stop = min(start + chunk_size, len(signal_indexes))
        chunk_signals = signal_indexes[start:stop]
        chunk_directions = directions[start:stop]
        chunk_entries = entry_prices[start:stop]
        chunk_stop_distances = stop_distances[start:stop]
        chunk_timeout_indexes = timeout_indexes[start:stop]
        chunk_stop_prices = np.where(
            chunk_directions > 0,
            chunk_entries - chunk_stop_distances,
            chunk_entries + chunk_stop_distances,
        )
        chunk_target_distances = chunk_stop_distances * candidate.reward_risk
        chunk_target_prices = np.where(
            chunk_directions > 0,
            chunk_entries + chunk_target_distances,
            chunk_entries - chunk_target_distances,
        )
        window_indexes = chunk_signals[:, None] + offsets[None, :]
        long_mask = chunk_directions > 0
        stop_hits = np.where(
            long_mask[:, None],
            low_prices[window_indexes] <= chunk_stop_prices[:, None],
            high_prices[window_indexes] >= chunk_stop_prices[:, None],
        )
        target_hits = np.where(
            long_mask[:, None],
            high_prices[window_indexes] >= chunk_target_prices[:, None],
            low_prices[window_indexes] <= chunk_target_prices[:, None],
        )
        symbol_valid = symbol_codes[window_indexes] == symbol_codes[chunk_signals, None]
        first_invalid = np.where((~symbol_valid).any(axis=1), (~symbol_valid).argmax(axis=1), candidate.max_hold_minutes + 1)
        first_stop = np.where(stop_hits.any(axis=1), stop_hits.argmax(axis=1), candidate.max_hold_minutes + 1)
        first_target = np.where(target_hits.any(axis=1), target_hits.argmax(axis=1), candidate.max_hold_minutes + 1)
        stop_first = first_stop <= first_target
        bracket_hit = (first_stop <= candidate.max_hold_minutes) | (first_target <= candidate.max_hold_minutes)
        first_exit_offsets = np.where(bracket_hit, np.minimum(first_stop, first_target) + 1, candidate.max_hold_minutes)
        invalid_before_exit = first_invalid < first_exit_offsets
        chunk_exit_indexes = np.where(bracket_hit, chunk_signals + first_exit_offsets, chunk_timeout_indexes)
        chunk_exit_prices = close_prices[chunk_timeout_indexes]
        chunk_reason_codes = np.zeros(len(chunk_signals), dtype=np.int8)
        stop_rows = bracket_hit & stop_first
        target_rows = bracket_hit & ~stop_first
        chunk_exit_prices = np.where(stop_rows, chunk_stop_prices, chunk_exit_prices)
        chunk_exit_prices = np.where(target_rows, chunk_target_prices, chunk_exit_prices)
        chunk_reason_codes = np.where(stop_rows, 1, chunk_reason_codes)
        chunk_reason_codes = np.where(target_rows, 2, chunk_reason_codes)
        chunk_reason_codes = np.where(invalid_before_exit, -1, chunk_reason_codes)
        realized_exit_indexes[start:stop] = chunk_exit_indexes
        exit_prices[start:stop] = chunk_exit_prices
        exit_reason_codes[start:stop] = chunk_reason_codes

    valid_path = exit_reason_codes >= 0
    if not valid_path.any():
        return pd.DataFrame()
    signal_indexes = signal_indexes[valid_path]
    entry_indexes = entry_indexes[valid_path]
    directions = directions[valid_path]
    entry_prices = entry_prices[valid_path]
    stop_distances = stop_distances[valid_path]
    realized_exit_indexes = realized_exit_indexes[valid_path]
    exit_prices = exit_prices[valid_path]
    exit_reason_codes = exit_reason_codes[valid_path]

    selected_positions: list[int] = []
    next_available_index = 0
    for position, signal_index in enumerate(signal_indexes):
        entry_index = int(signal_index) + 1
        if entry_index < next_available_index:
            continue
        selected_positions.append(position)
        next_available_index = int(realized_exit_indexes[position]) + 1
    if not selected_positions:
        return pd.DataFrame()
    selected = np.asarray(selected_positions, dtype=int)

    signal_indexes = signal_indexes[selected]
    directions = directions[selected]
    entry_prices = entry_prices[selected]
    stop_distances = stop_distances[selected]
    realized_exit_indexes = realized_exit_indexes[selected]
    exit_prices = exit_prices[selected]
    exit_reason_codes = exit_reason_codes[selected]
    gross_points = (exit_prices - entry_prices) * directions
    net_points = gross_points - costs.round_trip_cost_points
    risk_points = stop_distances + costs.round_trip_cost_points
    target_distances = stop_distances * candidate.reward_risk
    reason_labels = np.asarray(["timeout", "stop_loss", "take_profit"], dtype=object)[exit_reason_codes]

    return pd.DataFrame(
        {
            "candidate": candidate.name,
            "signal": candidate.signal,
            "lookback": candidate.lookback,
            "width_atr_mult": candidate.width_atr_mult,
            "max_efficiency": candidate.max_efficiency,
            "session": candidate.session,
            "direction_filter": candidate.direction_filter,
            "reward_risk": candidate.reward_risk,
            "max_hold_minutes": candidate.max_hold_minutes,
            "stop_mode": candidate.stop_mode,
            "entry_ts": timestamps[signal_indexes],
            "exit_ts": timestamps[realized_exit_indexes],
            "symbol": symbols[signal_indexes],
            "direction": directions,
            "entry_price": entry_prices,
            "exit_price": exit_prices,
            "exit_reason": reason_labels,
            "stop_distance_points": stop_distances,
            "target_distance_points": target_distances,
            "gross_points": gross_points,
            "net_points": net_points,
            "net_dollars": net_points * costs.point_value,
            "r_multiple": net_points / risk_points,
            "entry_index": signal_indexes.astype(int),
            "exit_index": realized_exit_indexes.astype(int),
        }
    )


def stop_distance_points(
    candidate: RangeCandidate,
    args: argparse.Namespace,
    direction: int,
    entry_price: float,
    signal_index: int,
    high_prices: np.ndarray,
    low_prices: np.ndarray,
    range_high: np.ndarray,
    range_low: np.ndarray,
    range_mid: np.ndarray,
    atr: np.ndarray,
) -> float | None:
    if candidate.stop_mode == "atr":
        distance = max(args.min_stop_points, args.stop_atr_mult * float(atr[signal_index]))
    elif candidate.stop_mode == "structure":
        buffer_points = max(args.min_buffer_points, args.stop_buffer_atr * float(atr[signal_index]))
        signal = candidate.signal
        if signal in {"breakout_close", "fvg_breakout"}:
            if direction > 0:
                stop_price = min(float(range_high[signal_index]) - buffer_points, entry_price - args.min_stop_points)
                distance = entry_price - stop_price
            else:
                stop_price = max(float(range_low[signal_index]) + buffer_points, entry_price + args.min_stop_points)
                distance = stop_price - entry_price
        elif signal == "breakout_retest":
            if direction > 0:
                stop_price = min(float(low_prices[signal_index]) - buffer_points, entry_price - args.min_stop_points)
                distance = entry_price - stop_price
            else:
                stop_price = max(float(high_prices[signal_index]) + buffer_points, entry_price + args.min_stop_points)
                distance = stop_price - entry_price
        else:
            if direction > 0:
                stop_price = min(float(low_prices[signal_index]) - buffer_points, entry_price - args.min_stop_points)
                distance = entry_price - stop_price
            else:
                stop_price = max(float(high_prices[signal_index]) + buffer_points, entry_price + args.min_stop_points)
                distance = stop_price - entry_price
    elif candidate.stop_mode == "range_mid":
        if direction > 0:
            distance = entry_price - float(range_mid[signal_index])
        else:
            distance = float(range_mid[signal_index]) - entry_price
        distance = max(args.min_stop_points, distance)
    else:
        raise ValueError(f"unknown stop mode: {candidate.stop_mode}")

    if not np.isfinite(distance):
        return None
    distance = float(max(distance, args.min_stop_points))
    if distance > args.max_stop_points:
        return None
    return distance


def stop_distance_points_vectorized(
    candidate: RangeCandidate,
    args: argparse.Namespace,
    directions: np.ndarray,
    entry_prices: np.ndarray,
    signal_indexes: np.ndarray,
    high_prices: np.ndarray,
    low_prices: np.ndarray,
    range_high: np.ndarray,
    range_low: np.ndarray,
    range_mid: np.ndarray,
    atr: np.ndarray,
) -> np.ndarray:
    signal_atr = atr[signal_indexes]
    distances = np.full(len(signal_indexes), np.nan, dtype=float)
    if candidate.stop_mode == "atr":
        distances = np.maximum(args.min_stop_points, args.stop_atr_mult * signal_atr)
    elif candidate.stop_mode == "structure":
        buffer_points = np.maximum(args.min_buffer_points, args.stop_buffer_atr * signal_atr)
        long_mask = directions > 0
        if candidate.signal in {"breakout_close", "fvg_breakout"}:
            long_stop = np.minimum(range_high[signal_indexes] - buffer_points, entry_prices - args.min_stop_points)
            short_stop = np.maximum(range_low[signal_indexes] + buffer_points, entry_prices + args.min_stop_points)
        elif candidate.signal == "breakout_retest":
            long_stop = np.minimum(low_prices[signal_indexes] - buffer_points, entry_prices - args.min_stop_points)
            short_stop = np.maximum(high_prices[signal_indexes] + buffer_points, entry_prices + args.min_stop_points)
        else:
            long_stop = np.minimum(low_prices[signal_indexes] - buffer_points, entry_prices - args.min_stop_points)
            short_stop = np.maximum(high_prices[signal_indexes] + buffer_points, entry_prices + args.min_stop_points)
        distances = np.where(long_mask, entry_prices - long_stop, short_stop - entry_prices)
    elif candidate.stop_mode == "range_mid":
        long_mask = directions > 0
        distances = np.where(long_mask, entry_prices - range_mid[signal_indexes], range_mid[signal_indexes] - entry_prices)
        distances = np.maximum(args.min_stop_points, distances)
    else:
        raise ValueError(f"unknown stop mode: {candidate.stop_mode}")
    distances = np.where(np.isfinite(distances), np.maximum(distances, args.min_stop_points), np.nan)
    return distances


def summarize_trades(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return empty_summary()
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    wins = net[net > 0]
    losses = net[net < 0]
    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss = float((-losses).mean()) if not losses.empty else 0.0
    gross_profit = float(wins.sum())
    gross_loss = float((-losses).sum())
    win_rate = float((net > 0).mean())
    payoff_ratio = float(avg_win / avg_loss) if avg_loss else (999.0 if avg_win > 0 else 0.0)
    expectancy = float(win_rate * avg_win - (1.0 - win_rate) * avg_loss)
    reasons = trades["exit_reason"].astype(str)
    r_multiple = pd.to_numeric(trades.get("r_multiple", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    split_ts = pd.to_datetime(trades["entry_ts"], utc=True).median()
    entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)
    first = net[entry_ts <= split_ts]
    second = net[entry_ts > split_ts]
    first_points = float(first.sum()) if not first.empty else 0.0
    second_points = float(second.sum()) if not second.empty else 0.0
    if first_points > 0 and second_points > 0:
        stability = min(first_points, second_points) / max(first_points, second_points)
    elif first_points + second_points > 0:
        stability = 0.25
    else:
        stability = 0.0
    return {
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "net_dollars": float(net.sum() * BacktestCosts().point_value),
        "max_drawdown_points": float(drawdown.max()) if not drawdown.empty else 0.0,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else (999.0 if gross_profit > 0 else 0.0),
        "win_rate": win_rate,
        "avg_points": float(net.mean()),
        "avg_win_points": avg_win,
        "avg_loss_points": avg_loss,
        "payoff_ratio": payoff_ratio,
        "expectancy_points": expectancy,
        "avg_r_multiple": float(r_multiple.mean()) if not r_multiple.empty else 0.0,
        "target_exit_share": float((reasons == "take_profit").mean()),
        "stop_exit_share": float((reasons == "stop_loss").mean()),
        "timeout_exit_share": float((reasons == "timeout").mean()),
        "first_half_points": first_points,
        "second_half_points": second_points,
        "stability": float(stability),
        "score": score_summary(
            net_points=float(net.sum()),
            max_drawdown=float(drawdown.max()) if not drawdown.empty else 0.0,
            trades=int(len(trades)),
            stability=float(stability),
            expectancy=expectancy,
        ),
    }


def empty_summary() -> dict[str, Any]:
    return {
        "trades": 0,
        "net_points": 0.0,
        "net_dollars": 0.0,
        "max_drawdown_points": 0.0,
        "profit_factor": 0.0,
        "win_rate": 0.0,
        "avg_points": 0.0,
        "avg_win_points": 0.0,
        "avg_loss_points": 0.0,
        "payoff_ratio": 0.0,
        "expectancy_points": 0.0,
        "avg_r_multiple": 0.0,
        "target_exit_share": 0.0,
        "stop_exit_share": 0.0,
        "timeout_exit_share": 0.0,
        "first_half_points": 0.0,
        "second_half_points": 0.0,
        "stability": 0.0,
        "score": 0.0,
    }


def score_summary(*, net_points: float, max_drawdown: float, trades: int, stability: float, expectancy: float) -> float:
    risk = max(max_drawdown, 1.0)
    evidence = sqrt(min(max(trades, 0), 500) / 500)
    return float((net_points / risk) * evidence * (0.65 + 0.35 * max(stability, 0.0)) * max(0.25, 1.0 + expectancy / 10.0))


def train_passes(summary: dict[str, Any], args: argparse.Namespace) -> bool:
    return (
        int(summary["trades"]) >= args.min_train_trades
        and float(summary["net_points"]) > 0
        and float(summary["profit_factor"]) >= args.min_train_profit_factor
        and float(summary["expectancy_points"]) >= args.min_train_expectancy
        and float(summary["max_drawdown_points"]) <= args.max_train_drawdown_points
    )


def test_passes(summary: dict[str, Any], args: argparse.Namespace) -> bool:
    return (
        int(summary["trades"]) >= args.min_test_trades
        and float(summary["net_points"]) > 0
        and float(summary["profit_factor"]) >= args.min_test_profit_factor
        and float(summary["expectancy_points"]) >= args.min_test_expectancy
        and float(summary["max_drawdown_points"]) <= args.max_test_drawdown_points
    )


def summarize_window(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[dict[str, Any], pd.DataFrame]:
    if trades.empty:
        return empty_summary(), trades
    selected = trades[(trades["entry_ts"] >= start) & (trades["entry_ts"] < end)].copy()
    if selected.empty:
        return empty_summary(), selected
    return summarize_trades(selected), selected


def build_trade_cache(
    frame: pd.DataFrame,
    candidates: list[RangeCandidate],
    args: argparse.Namespace,
    costs: BacktestCosts,
) -> dict[str, tuple[RangeCandidate, pd.DataFrame]]:
    cache: dict[str, tuple[RangeCandidate, pd.DataFrame]] = {}
    for index, candidate in enumerate(candidates, start=1):
        if index == 1 or index % 50 == 0 or index == len(candidates):
            print(f"building trades {index}/{len(candidates)}: {candidate.name}", flush=True)
        trades = build_trades(frame, candidate, args, costs)
        if not trades.empty:
            trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
            trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
        cache[candidate.name] = (candidate, trades)
    return cache


def walk_forward(
    trade_cache: dict[str, tuple[RangeCandidate, pd.DataFrame]],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    start = pd.Timestamp(args.walk_start_date, tz="UTC")
    end = pd.Timestamp(args.end_date, tz="UTC")
    fold_rows: list[dict[str, Any]] = []
    trade_rows: list[pd.DataFrame] = []
    fold = 0
    test_start = start
    while test_start + pd.Timedelta(days=args.test_days) <= end:
        train_start = test_start - pd.Timedelta(days=args.train_days + args.purge_days)
        train_end = test_start - pd.Timedelta(days=args.purge_days)
        test_end = test_start + pd.Timedelta(days=args.test_days)
        ranked: list[tuple[float, dict[str, Any], RangeCandidate, pd.DataFrame]] = []
        for candidate, trades in trade_cache.values():
            train_summary, train_trades = summarize_window(trades, train_start, train_end)
            if train_passes(train_summary, args):
                ranked.append((float(train_summary["score"]), train_summary, candidate, train_trades))
        ranked.sort(
            reverse=True,
            key=lambda item: (
                item[0],
                item[1]["expectancy_points"],
                item[1]["profit_factor"],
                item[1]["net_points"],
            ),
        )
        for rank, (_, train_summary, candidate, _) in enumerate(ranked[: args.max_fold_candidates], start=1):
            _, trades = trade_cache[candidate.name]
            test_summary, test_trades = summarize_window(trades, test_start, test_end)
            passed = test_passes(test_summary, args)
            fold_rows.append(
                {
                    "fold": fold,
                    "fold_rank": rank,
                    "candidate": candidate.name,
                    "signal": candidate.signal,
                    "lookback": candidate.lookback,
                    "width_atr_mult": candidate.width_atr_mult,
                    "max_efficiency": candidate.max_efficiency,
                    "session": candidate.session,
                    "direction_filter": candidate.direction_filter,
                    "reward_risk": candidate.reward_risk,
                    "max_hold_minutes": candidate.max_hold_minutes,
                    "stop_mode": candidate.stop_mode,
                    "train_start": str(train_start.date()),
                    "train_end": str(train_end.date()),
                    "test_start": str(test_start.date()),
                    "test_end": str(test_end.date()),
                    "test_pass": bool(passed),
                    **{f"train_{key}": value for key, value in train_summary.items()},
                    **{f"test_{key}": value for key, value in test_summary.items()},
                }
            )
            if not test_trades.empty:
                exported = test_trades.copy()
                exported["fold"] = fold
                exported["fold_rank"] = rank
                exported["test_pass"] = bool(passed)
                trade_rows.append(exported)
        fold += 1
        test_start += pd.Timedelta(days=args.step_days)
    folds = pd.DataFrame(fold_rows)
    trades = pd.concat(trade_rows, ignore_index=True, sort=False) if trade_rows else pd.DataFrame()
    return folds, trades


def aggregate_results(folds: pd.DataFrame) -> pd.DataFrame:
    if folds.empty:
        return pd.DataFrame()
    grouped = folds.groupby("candidate", as_index=False).agg(
        signal=("signal", "first"),
        lookback=("lookback", "first"),
        width_atr_mult=("width_atr_mult", "first"),
        max_efficiency=("max_efficiency", "first"),
        session=("session", "first"),
        direction_filter=("direction_filter", "first"),
        reward_risk=("reward_risk", "first"),
        max_hold_minutes=("max_hold_minutes", "first"),
        stop_mode=("stop_mode", "first"),
        selected_folds=("fold", "nunique"),
        positive_test_folds=("test_net_points", lambda values: int((values > 0).sum())),
        pass_folds=("test_pass", "sum"),
        test_trades=("test_trades", "sum"),
        test_net_points=("test_net_points", "sum"),
        test_max_drawdown_points=("test_max_drawdown_points", "max"),
        avg_test_profit_factor=("test_profit_factor", "mean"),
        avg_test_win_rate=("test_win_rate", "mean"),
        avg_test_payoff_ratio=("test_payoff_ratio", "mean"),
        avg_test_expectancy_points=("test_expectancy_points", "mean"),
        avg_test_target_exit_share=("test_target_exit_share", "mean"),
        min_test_net_points=("test_net_points", "min"),
        avg_train_score=("train_score", "mean"),
    )
    grouped["positive_test_fold_rate"] = grouped["positive_test_folds"] / grouped["selected_folds"].clip(lower=1)
    grouped["pass_fold_rate"] = grouped["pass_folds"] / grouped["selected_folds"].clip(lower=1)
    grouped["net_to_drawdown"] = grouped["test_net_points"] / grouped["test_max_drawdown_points"].clip(lower=1.0)
    grouped["stable_candidate"] = (
        (grouped["selected_folds"] >= 3)
        & (grouped["positive_test_fold_rate"] >= 0.67)
        & (grouped["test_net_points"] > 0)
        & (grouped["avg_test_profit_factor"] >= 1.08)
        & (grouped["avg_test_expectancy_points"] > 0)
        & (grouped["net_to_drawdown"] >= 1.0)
    )
    grouped["ranking_score"] = (
        grouped["test_net_points"].clip(lower=0) * 0.001
        + grouped["net_to_drawdown"].clip(lower=0)
        + grouped["positive_test_fold_rate"] * grouped["selected_folds"].clip(upper=8)
        + grouped["avg_test_expectancy_points"].clip(lower=0)
    )
    return grouped.sort_values(
        ["stable_candidate", "positive_test_fold_rate", "pass_fold_rate", "ranking_score", "test_net_points"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)


def full_sample_summary(
    trade_cache: dict[str, tuple[RangeCandidate, pd.DataFrame]],
    aggregate: pd.DataFrame,
    limit: int,
) -> pd.DataFrame:
    if aggregate.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for _, row in aggregate.head(limit).iterrows():
        name = str(row["candidate"])
        candidate, trades = trade_cache[name]
        summary = summarize_trades(trades)
        yearly = yearly_stats(trades)
        rolling = rolling_stats(trades, days=90)
        rows.append(
            {
                "candidate": candidate.name,
                "signal": candidate.signal,
                "lookback": candidate.lookback,
                "session": candidate.session,
                "direction_filter": candidate.direction_filter,
                "reward_risk": candidate.reward_risk,
                "max_hold_minutes": candidate.max_hold_minutes,
                "stop_mode": candidate.stop_mode,
                **summary,
                "positive_years": int((yearly["net_points"] > 0).sum()) if not yearly.empty else 0,
                "years": int(len(yearly)),
                "min_year_net": float(yearly["net_points"].min()) if not yearly.empty else 0.0,
                "positive_90d_rate": float((rolling["net_points"] > 0).mean()) if not rolling.empty else 0.0,
                "worst_90d_net": float(rolling["net_points"].min()) if not rolling.empty else 0.0,
            }
        )
    return pd.DataFrame(rows)


def yearly_stats(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["year", "net_points"])
    frame = trades.copy()
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    net = pd.to_numeric(frame["net_points"], errors="coerce").fillna(0.0)
    return net.groupby(frame["entry_ts"].dt.year).sum().reset_index(name="net_points")


def rolling_stats(trades: pd.DataFrame, days: int) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["start", "end", "net_points"])
    frame = trades.copy()
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    start = frame["entry_ts"].min().normalize()
    end = frame["entry_ts"].max().normalize()
    rows: list[dict[str, Any]] = []
    cursor = start
    while cursor + pd.Timedelta(days=days) <= end:
        stop = cursor + pd.Timedelta(days=days)
        selected = frame[(frame["entry_ts"] >= cursor) & (frame["entry_ts"] < stop)]
        net = pd.to_numeric(selected["net_points"], errors="coerce").fillna(0.0)
        rows.append({"start": str(cursor.date()), "end": str(stop.date()), "net_points": float(net.sum())})
        cursor += pd.Timedelta(days=days)
    return pd.DataFrame(rows)


def write_report(
    path: Path,
    frame: pd.DataFrame,
    candidates: list[RangeCandidate],
    folds: pd.DataFrame,
    aggregate: pd.DataFrame,
    full_sample: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NQ Range Breakout / Continuation Strategy Search",
        "",
        "## Purpose",
        "",
        "This search tests bar-only rules that first identify a compressed/choppy range, then trade a breakout, retest continuation, liquidity sweep/reclaim, boundary pin, or FVG breakout. Selection is based on expectancy: win probability times average win versus loss probability times average loss.",
        "",
        "## Data",
        "",
        f"- Source: `{_bar_zip_path()}`.",
        f"- Span: `{frame['ts'].min()}` to `{frame['ts'].max()}`.",
        f"- Rows: `{len(frame):,}`.",
        f"- Costs: `{BacktestCosts().round_trip_cost_points:.3f}` NQ points round trip.",
        "",
        "## Candidate Design",
        "",
        f"- Signals: `{', '.join(args.signals)}`.",
        f"- Lookbacks: `{', '.join(str(value) for value in args.lookbacks)}` minutes.",
        f"- Range filter: width <= ATR multiple, efficiency <= threshold, min width `{args.min_range_points}` points.",
        f"- Reward/risk targets: `{', '.join(str(value) for value in args.reward_risks)}`.",
        f"- Stop modes: `{', '.join(args.stop_modes)}`; same-bar stop/target ambiguity is resolved stop-first.",
        f"- Candidate count: `{len(candidates):,}`.",
        "",
        "## Walk-Forward",
        "",
        f"- Train/purge/test/step days: `{args.train_days}` / `{args.purge_days}` / `{args.test_days}` / `{args.step_days}`.",
        f"- Fold rows: `{len(folds):,}`; aggregated candidates: `{len(aggregate):,}`.",
        f"- Train gates: trades >= `{args.min_train_trades}`, PF >= `{args.min_train_profit_factor}`, expectancy >= `{args.min_train_expectancy}`.",
        f"- Test gates: trades >= `{args.min_test_trades}`, PF >= `{args.min_test_profit_factor}`, expectancy >= `{args.min_test_expectancy}`.",
        "",
        "## Verdict",
        "",
    ]
    stable = aggregate[aggregate["stable_candidate"]] if not aggregate.empty else pd.DataFrame()
    if stable.empty:
        lines.append("No range-breakout candidate passed the stable gate on this run. The top rows remain research evidence only.")
    else:
        top = stable.iloc[0]
        lines.append(
            f"Best stable range candidate: `{top['candidate']}` with `{top['test_net_points']:.2f}` selected OOS points, "
            f"`{top['positive_test_fold_rate']:.2%}` positive selected folds, PF `{top['avg_test_profit_factor']:.3f}`, "
            f"and expectancy `{top['avg_test_expectancy_points']:.3f}` points/trade."
        )
    if not aggregate.empty:
        columns = [
            "stable_candidate",
            "candidate",
            "selected_folds",
            "positive_test_fold_rate",
            "pass_fold_rate",
            "test_trades",
            "test_net_points",
            "net_to_drawdown",
            "avg_test_profit_factor",
            "avg_test_win_rate",
            "avg_test_payoff_ratio",
            "avg_test_expectancy_points",
            "avg_test_target_exit_share",
            "min_test_net_points",
        ]
        lines.extend(["", "## Top Walk-Forward Candidates", "", markdown_table(aggregate.head(30)[columns]), ""])
    if not full_sample.empty:
        columns = [
            "candidate",
            "trades",
            "net_points",
            "profit_factor",
            "win_rate",
            "payoff_ratio",
            "expectancy_points",
            "max_drawdown_points",
            "positive_years",
            "years",
            "positive_90d_rate",
            "worst_90d_net",
            "first_half_points",
            "second_half_points",
        ]
        lines.extend(["## Full-Sample Sanity Check", "", markdown_table(full_sample[columns]), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    rows = ["| " + " | ".join(str(column) for column in frame.columns) + " |"]
    rows.append("| " + " | ".join(["---"] * len(frame.columns)) + " |")
    for _, row in frame.iterrows():
        values = []
        for value in row.tolist():
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Search NQ bar-only range breakout/continuation systems.")
    parser.add_argument("--start-date", default="2010-06-06")
    parser.add_argument("--walk-start-date", default="2012-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-short-trend-2010-adx-cache.pkl")
    parser.add_argument("--output", default=".tmp/nq-range-breakout-2010-walkforward.csv")
    parser.add_argument("--aggregate-output", default=".tmp/nq-range-breakout-2010-aggregate.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-range-breakout-2010-trades.csv")
    parser.add_argument("--full-sample-output", default=".tmp/nq-range-breakout-2010-full-sample.csv")
    parser.add_argument("--report", default="reports/NQ-range-breakout-2010-search.md")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--lookbacks", type=int, nargs="+", default=[30, 60, 120])
    parser.add_argument("--range-width-atr-mults", type=float, nargs="+", default=[8.0, 12.0])
    parser.add_argument("--max-efficiencies", type=float, nargs="+", default=[0.35])
    parser.add_argument("--signals", nargs="+", default=["breakout_close", "breakout_retest", "sweep_reclaim", "boundary_pin", "fvg_breakout"])
    parser.add_argument("--sessions", nargs="+", default=["ldn_ny", "us_rth", "us_late"])
    parser.add_argument("--direction-filters", nargs="+", choices=["both", "long", "short"], default=["both", "long", "short"])
    parser.add_argument("--reward-risks", type=float, nargs="+", default=[1.5, 2.0, 3.0])
    parser.add_argument("--max-hold-minutes", type=int, nargs="+", default=[30, 60, 120])
    parser.add_argument("--stop-modes", nargs="+", choices=["structure", "atr", "range_mid"], default=["structure", "atr"])
    parser.add_argument("--train-days", type=int, default=730)
    parser.add_argument("--purge-days", type=int, default=5)
    parser.add_argument("--test-days", type=int, default=180)
    parser.add_argument("--step-days", type=int, default=90)
    parser.add_argument("--max-fold-candidates", type=int, default=20)
    parser.add_argument("--full-sample-limit", type=int, default=30)
    parser.add_argument("--min-train-trades", type=int, default=80)
    parser.add_argument("--min-test-trades", type=int, default=20)
    parser.add_argument("--min-train-profit-factor", type=float, default=1.08)
    parser.add_argument("--min-test-profit-factor", type=float, default=1.02)
    parser.add_argument("--min-train-expectancy", type=float, default=0.25)
    parser.add_argument("--min-test-expectancy", type=float, default=0.0)
    parser.add_argument("--max-train-drawdown-points", type=float, default=6000.0)
    parser.add_argument("--max-test-drawdown-points", type=float, default=2500.0)
    parser.add_argument("--min-range-points", type=float, default=4.0)
    parser.add_argument("--min-stop-points", type=float, default=6.0)
    parser.add_argument("--max-stop-points", type=float, default=60.0)
    parser.add_argument("--stop-atr-mult", type=float, default=2.0)
    parser.add_argument("--stop-buffer-atr", type=float, default=0.1)
    parser.add_argument("--breakout-buffer-atr", type=float, default=0.05)
    parser.add_argument("--retest-tolerance-atr", type=float, default=0.25)
    parser.add_argument("--min-buffer-points", type=float, default=0.25)
    parser.add_argument("--displacement-atr-mult", type=float, default=1.15)
    parser.add_argument("--min-body-share", type=float, default=0.55)
    parser.add_argument("--min-volume-z", type=float, default=-0.25)
    parser.add_argument("--pin-wick-body-mult", type=float, default=1.5)
    parser.add_argument("--retest-window-minutes", type=int, default=15)
    args = parser.parse_args()

    costs = BacktestCosts()
    base_features = load_continuous_nq_bars(args)
    frame = add_range_structure_features(base_features, args)
    candidates = candidate_pool(args)
    trade_cache = build_trade_cache(frame, candidates, args, costs)
    folds, trades = walk_forward(trade_cache, args)
    aggregate = aggregate_results(folds)
    full_sample = full_sample_summary(trade_cache, aggregate, args.full_sample_limit)

    for output_path, data in [
        (args.output, folds),
        (args.aggregate_output, aggregate),
        (args.trades_output, trades),
        (args.full_sample_output, full_sample),
    ]:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data.to_csv(path, index=False)
    write_report(Path(args.report), frame, candidates, folds, aggregate, full_sample, args)

    result = {
        "source": str(_bar_zip_path()),
        "feature_rows": int(len(frame)),
        "candidate_count": int(len(candidates)),
        "fold_rows": int(len(folds)),
        "aggregate_rows": int(len(aggregate)),
        "stable_candidates": int(aggregate["stable_candidate"].sum()) if "stable_candidate" in aggregate else 0,
        "output": args.output,
        "aggregate_output": args.aggregate_output,
        "full_sample_output": args.full_sample_output,
        "report": args.report,
    }
    if not aggregate.empty:
        result["top_candidate"] = aggregate.iloc[0].to_dict()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
