from __future__ import annotations

import argparse
import json
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

from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.dataflows.databento import _bar_zip_path


BULLISH = 1
BEARISH = -1


@dataclass(frozen=True)
class LightglowCandidate:
    signal: str
    timeframe_minutes: int
    session: str
    hold_bars: int
    direction_mode: str
    stop_loss_points: float | None
    take_profit_points: float | None

    @property
    def holding_minutes(self) -> int:
        return self.timeframe_minutes * self.hold_bars

    @property
    def exit_profile(self) -> str:
        if self.stop_loss_points is None and self.take_profit_points is None:
            return "time"
        stop = "none" if self.stop_loss_points is None else f"{self.stop_loss_points:g}"
        target = "none" if self.take_profit_points is None else f"{self.take_profit_points:g}"
        return f"sl{stop}_tp{target}"

    @property
    def name(self) -> str:
        return (
            f"lightglow_{self.signal}_{self.timeframe_minutes}m_{self.session}"
            f"_hold{self.holding_minutes}m_{self.direction_mode}_{self.exit_profile}"
        )


def resample_ohlcv(features: pd.DataFrame, timeframe_minutes: int) -> pd.DataFrame:
    data = features[["ts", "symbol", "Open", "High", "Low", "Close", "Volume"]].copy()
    data["ts"] = pd.to_datetime(data["ts"], utc=True)
    if timeframe_minutes == 1:
        result = data.sort_values("ts").reset_index(drop=True)
    else:
        aggregations = {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
            "symbol": "last",
        }
        result = (
            data.set_index("ts")
            .resample(f"{timeframe_minutes}min", label="left", closed="left")
            .agg(aggregations)
            .dropna(subset=["Open", "High", "Low", "Close"])
            .reset_index()
        )
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["trade_date"] = result["ts"].dt.date
    result["minute_of_day"] = result["ts"].dt.hour * 60 + result["ts"].dt.minute
    result["timeframe_minutes"] = timeframe_minutes
    return result.dropna(subset=["Open", "High", "Low", "Close"]).reset_index(drop=True)


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, length: int = 200) -> np.ndarray:
    previous_close = np.r_[np.nan, close[:-1]]
    true_range = np.nanmax(
        np.vstack([high - low, np.abs(high - previous_close), np.abs(low - previous_close)]),
        axis=0,
    )
    return pd.Series(true_range).rolling(length, min_periods=max(5, length // 10)).mean().to_numpy(dtype=float)


def _confirmed_pivots(values: np.ndarray, size: int, find_highs: bool) -> np.ndarray:
    pivots = np.zeros(len(values), dtype=bool)
    for index in range(size, len(values)):
        pivot_index = index - size
        future_window = values[pivot_index + 1 : index + 1]
        if future_window.size == 0:
            continue
        if find_highs and values[pivot_index] > np.nanmax(future_window):
            pivots[index] = True
        elif not find_highs and values[pivot_index] < np.nanmin(future_window):
            pivots[index] = True
    return pivots


def build_lightglow_signals(bars: pd.DataFrame) -> pd.DataFrame:
    frame = bars.copy().reset_index(drop=True)
    open_prices = frame["Open"].to_numpy(dtype=float)
    high = frame["High"].to_numpy(dtype=float)
    low = frame["Low"].to_numpy(dtype=float)
    close = frame["Close"].to_numpy(dtype=float)
    atr = _atr(high, low, close)
    volatility = pd.Series(high - low).rolling(200, min_periods=20).mean().to_numpy(dtype=float)
    volatility = np.where(np.isfinite(atr), atr, volatility)
    high_volatility = (high - low) >= (2.0 * np.nan_to_num(volatility, nan=np.inf))
    parsed_high = np.where(high_volatility, low, high)
    parsed_low = np.where(high_volatility, high, low)

    signal_columns = {
        "internal_bos": np.zeros(len(frame), dtype=np.int8),
        "internal_choch": np.zeros(len(frame), dtype=np.int8),
        "swing_bos": np.zeros(len(frame), dtype=np.int8),
        "swing_choch": np.zeros(len(frame), dtype=np.int8),
        "fvg": np.zeros(len(frame), dtype=np.int8),
        "equal_level_reversal": np.zeros(len(frame), dtype=np.int8),
        "internal_ob_break": np.zeros(len(frame), dtype=np.int8),
        "swing_ob_break": np.zeros(len(frame), dtype=np.int8),
        "premium_discount_reversal": np.zeros(len(frame), dtype=np.int8),
        "internal_choch_zone": np.zeros(len(frame), dtype=np.int8),
        "fvg_zone": np.zeros(len(frame), dtype=np.int8),
    }

    state: dict[str, dict[str, Any]] = {
        "internal": {
            "size": 5,
            "trend": 0,
            "high_level": np.nan,
            "high_crossed": True,
            "high_index": -1,
            "low_level": np.nan,
            "low_crossed": True,
            "low_index": -1,
            "blocks": [],
        },
        "swing": {
            "size": 50,
            "trend": 0,
            "high_level": np.nan,
            "high_crossed": True,
            "high_index": -1,
            "low_level": np.nan,
            "low_crossed": True,
            "low_index": -1,
            "blocks": [],
        },
    }
    equal_high_level = np.nan
    equal_low_level = np.nan
    swing_top = np.nan
    swing_bottom = np.nan

    pivot_masks = {
        "internal_high": _confirmed_pivots(high, 5, True),
        "internal_low": _confirmed_pivots(low, 5, False),
        "swing_high": _confirmed_pivots(high, 50, True),
        "swing_low": _confirmed_pivots(low, 50, False),
        "equal_high": _confirmed_pivots(high, 3, True),
        "equal_low": _confirmed_pivots(low, 3, False),
    }

    cumulative_delta = 0.0
    fvg_observations = 0
    for index in range(len(frame)):
        if index >= 2:
            bar_delta = (close[index - 1] - open_prices[index - 1]) / (open_prices[index - 1] * 100.0)
            cumulative_delta += abs(bar_delta)
            fvg_observations += 1
            threshold = cumulative_delta / max(fvg_observations, 1) * 2.0
            if low[index] > high[index - 2] and close[index - 1] > high[index - 2] and bar_delta > threshold:
                signal_columns["fvg"][index] = BULLISH
            elif high[index] < low[index - 2] and close[index - 1] < low[index - 2] and -bar_delta > threshold:
                signal_columns["fvg"][index] = BEARISH

        if pivot_masks["equal_high"][index]:
            pivot_index = index - 3
            if np.isfinite(equal_high_level) and np.isfinite(atr[index]):
                if abs(equal_high_level - high[pivot_index]) < 0.1 * atr[index]:
                    signal_columns["equal_level_reversal"][index] = BEARISH
            equal_high_level = high[pivot_index]
        if pivot_masks["equal_low"][index]:
            pivot_index = index - 3
            if np.isfinite(equal_low_level) and np.isfinite(atr[index]):
                if abs(equal_low_level - low[pivot_index]) < 0.1 * atr[index]:
                    signal_columns["equal_level_reversal"][index] = BULLISH
            equal_low_level = low[pivot_index]

        for prefix, current_state in state.items():
            size = int(current_state["size"])
            if pivot_masks[f"{prefix}_high"][index]:
                pivot_index = index - size
                current_state["high_level"] = high[pivot_index]
                current_state["high_crossed"] = False
                current_state["high_index"] = pivot_index
                if prefix == "swing":
                    swing_top = high[pivot_index]
            if pivot_masks[f"{prefix}_low"][index]:
                pivot_index = index - size
                current_state["low_level"] = low[pivot_index]
                current_state["low_crossed"] = False
                current_state["low_index"] = pivot_index
                if prefix == "swing":
                    swing_bottom = low[pivot_index]

            previous_close = close[index - 1] if index > 0 else close[index]
            high_level = float(current_state["high_level"])
            if (
                np.isfinite(high_level)
                and not bool(current_state["high_crossed"])
                and previous_close <= high_level
                and close[index] > high_level
            ):
                tag = "choch" if int(current_state["trend"]) == BEARISH else "bos"
                signal_columns[f"{prefix}_{tag}"][index] = BULLISH
                current_state["high_crossed"] = True
                current_state["trend"] = BULLISH
                store_order_block(current_state, parsed_high, parsed_low, int(current_state["high_index"]), index, BULLISH)

            low_level = float(current_state["low_level"])
            if (
                np.isfinite(low_level)
                and not bool(current_state["low_crossed"])
                and previous_close >= low_level
                and close[index] < low_level
            ):
                tag = "choch" if int(current_state["trend"]) == BULLISH else "bos"
                signal_columns[f"{prefix}_{tag}"][index] = BEARISH
                current_state["low_crossed"] = True
                current_state["trend"] = BEARISH
                store_order_block(current_state, parsed_high, parsed_low, int(current_state["low_index"]), index, BEARISH)

            block_signal = delete_order_blocks(current_state, high[index], low[index])
            if block_signal:
                signal_columns[f"{prefix}_ob_break"][index] = block_signal

        if np.isfinite(swing_top) and np.isfinite(swing_bottom) and swing_top > swing_bottom:
            premium_floor = 0.95 * swing_top + 0.05 * swing_bottom
            discount_ceiling = 0.05 * swing_top + 0.95 * swing_bottom
            if close[index] >= premium_floor:
                signal_columns["premium_discount_reversal"][index] = BEARISH
            elif close[index] <= discount_ceiling:
                signal_columns["premium_discount_reversal"][index] = BULLISH

        zone_signal = signal_columns["premium_discount_reversal"][index]
        choch_signal = signal_columns["internal_choch"][index]
        fvg_signal = signal_columns["fvg"][index]
        if zone_signal and choch_signal and zone_signal == choch_signal:
            signal_columns["internal_choch_zone"][index] = zone_signal
        if zone_signal and fvg_signal and zone_signal == fvg_signal:
            signal_columns["fvg_zone"][index] = zone_signal

    for name, values in signal_columns.items():
        frame[name] = values
    return frame


def store_order_block(
    current_state: dict[str, Any],
    parsed_high: np.ndarray,
    parsed_low: np.ndarray,
    pivot_index: int,
    current_index: int,
    bias: int,
) -> None:
    if pivot_index < 0 or current_index <= pivot_index:
        return
    if bias == BEARISH:
        window = parsed_high[pivot_index:current_index]
        if window.size == 0 or np.all(~np.isfinite(window)):
            return
        parsed_index = pivot_index + int(np.nanargmax(window))
    else:
        window = parsed_low[pivot_index:current_index]
        if window.size == 0 or np.all(~np.isfinite(window)):
            return
        parsed_index = pivot_index + int(np.nanargmin(window))
    block = {
        "high": float(parsed_high[parsed_index]),
        "low": float(parsed_low[parsed_index]),
        "bias": int(bias),
    }
    blocks = current_state["blocks"]
    blocks.insert(0, block)
    del blocks[100:]


def delete_order_blocks(current_state: dict[str, Any], high: float, low: float) -> int:
    blocks = current_state["blocks"]
    signal = 0
    kept = []
    for block in blocks:
        crossed = False
        if block["bias"] == BEARISH and high > block["high"]:
            signal = BULLISH
            crossed = True
        elif block["bias"] == BULLISH and low < block["low"]:
            signal = BEARISH
            crossed = True
        if not crossed:
            kept.append(block)
    current_state["blocks"] = kept
    return signal


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
    if session == "asia":
        return (minute < 7 * 60) | (minute >= 23 * 60)
    raise ValueError(f"unknown session: {session}")


def candidate_pool(args: argparse.Namespace, signal_names: list[str]) -> list[LightglowCandidate]:
    candidates: list[LightglowCandidate] = []
    exit_profiles: list[tuple[float | None, float | None]] = [(None, None)]
    for profile in args.exit_profiles:
        if profile == "time":
            continue
        stop_text, target_text = profile.removeprefix("sl").split("_tp", 1)
        exit_profiles.append((float(stop_text), float(target_text)))
    for timeframe in args.timeframes:
        for signal in signal_names:
            for session in args.sessions:
                for hold_bars in args.hold_bars:
                    for direction_mode in args.direction_modes:
                        for stop_loss, take_profit in exit_profiles:
                            candidates.append(
                                LightglowCandidate(
                                    signal=signal,
                                    timeframe_minutes=int(timeframe),
                                    session=session,
                                    hold_bars=int(hold_bars),
                                    direction_mode=direction_mode,
                                    stop_loss_points=stop_loss,
                                    take_profit_points=take_profit,
                                )
                            )
    return candidates


def build_trades(frame: pd.DataFrame, candidate: LightglowCandidate, costs: BacktestCosts) -> pd.DataFrame:
    signal = pd.to_numeric(frame[candidate.signal], errors="coerce").fillna(0).astype(int)
    if candidate.direction_mode == "reverse":
        signal = -signal
    elif candidate.direction_mode != "native":
        raise ValueError(f"unknown direction mode: {candidate.direction_mode}")

    signal = signal.where(session_mask(frame, candidate.session), 0)
    signal = signal.where(signal != signal.shift(1), 0)
    entry_indexes = np.flatnonzero(signal.to_numpy() != 0)
    if len(entry_indexes) == 0:
        return pd.DataFrame()

    if candidate.stop_loss_points is None and candidate.take_profit_points is None:
        return build_time_exit_trades(frame, signal, candidate, costs, entry_indexes=entry_indexes)

    rows: list[dict[str, Any]] = []
    open_prices = frame["Open"].to_numpy(dtype=float)
    high_prices = frame["High"].to_numpy(dtype=float)
    low_prices = frame["Low"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    timestamps = frame["ts"].to_numpy()
    symbols = frame["symbol"].astype(str).to_numpy()
    next_available_index = 0
    hold_bars = max(1, candidate.hold_bars)
    for signal_index in entry_indexes:
        entry_index = int(signal_index) + 1
        exit_index = int(signal_index) + hold_bars
        if entry_index < next_available_index or exit_index >= len(frame):
            continue
        path_slice = slice(entry_index, exit_index + 1)
        if not np.all(symbols[path_slice] == symbols[signal_index]):
            continue
        direction = int(signal.iat[signal_index])
        entry_price = float(open_prices[entry_index])
        exit_price = float(close_prices[exit_index])
        realized_exit_index = exit_index
        exit_reason = "time"
        stop_price = None
        target_price = None
        if candidate.stop_loss_points is not None:
            stop_price = entry_price - candidate.stop_loss_points if direction > 0 else entry_price + candidate.stop_loss_points
        if candidate.take_profit_points is not None:
            target_price = entry_price + candidate.take_profit_points if direction > 0 else entry_price - candidate.take_profit_points
        if stop_price is not None or target_price is not None:
            for path_index in range(entry_index, exit_index + 1):
                if direction > 0:
                    stop_hit = stop_price is not None and low_prices[path_index] <= stop_price
                    target_hit = target_price is not None and high_prices[path_index] >= target_price
                else:
                    stop_hit = stop_price is not None and high_prices[path_index] >= stop_price
                    target_hit = target_price is not None and low_prices[path_index] <= target_price
                if stop_hit:
                    exit_price = float(stop_price)
                    realized_exit_index = path_index
                    exit_reason = "stop_loss"
                    break
                if target_hit:
                    exit_price = float(target_price)
                    realized_exit_index = path_index
                    exit_reason = "take_profit"
                    break
        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points
        rows.append(
            {
                "candidate": candidate.name,
                "signal": candidate.signal,
                "timeframe_minutes": candidate.timeframe_minutes,
                "session": candidate.session,
                "holding_minutes": candidate.holding_minutes,
                "direction_mode": candidate.direction_mode,
                "exit_profile": candidate.exit_profile,
                "entry_ts": timestamps[signal_index],
                "exit_ts": timestamps[realized_exit_index],
                "symbol": symbols[signal_index],
                "direction": direction,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "gross_points": float(gross_points),
                "net_points": float(net_points),
                "net_dollars": float(net_points * costs.point_value),
                "entry_index": int(signal_index),
                "exit_index": int(realized_exit_index),
            }
        )
        next_available_index = realized_exit_index + 1
    return pd.DataFrame(rows)


def build_time_exit_trades(
    frame: pd.DataFrame,
    signal: pd.Series,
    candidate: LightglowCandidate,
    costs: BacktestCosts,
    *,
    entry_indexes: np.ndarray | None = None,
    selected_signal_indexes: np.ndarray | None = None,
) -> pd.DataFrame:
    hold_bars = max(1, candidate.hold_bars)
    if selected_signal_indexes is None:
        if entry_indexes is None:
            entry_indexes = np.flatnonzero(signal.to_numpy() != 0)
        selected_signal_indexes = select_non_overlapping_signal_indexes(entry_indexes, len(frame), hold_bars)
    if len(selected_signal_indexes) == 0:
        return pd.DataFrame()
    signal_indexes = np.asarray(selected_signal_indexes, dtype=int)
    entry_price_indexes = signal_indexes + 1
    exit_indexes = signal_indexes + hold_bars
    symbols = frame["symbol"].astype(str).to_numpy()
    valid = symbols[exit_indexes] == symbols[signal_indexes]
    if not valid.any():
        return pd.DataFrame()
    signal_indexes = signal_indexes[valid]
    entry_price_indexes = entry_price_indexes[valid]
    exit_indexes = exit_indexes[valid]

    directions = signal.iloc[signal_indexes].to_numpy(dtype=int)
    entry_prices = frame["Open"].to_numpy(dtype=float)[entry_price_indexes]
    exit_prices = frame["Close"].to_numpy(dtype=float)[exit_indexes]
    gross_points = (exit_prices - entry_prices) * directions
    net_points = gross_points - costs.round_trip_cost_points
    timestamps = frame["ts"].to_numpy()
    return pd.DataFrame(
        {
            "candidate": candidate.name,
            "signal": candidate.signal,
            "timeframe_minutes": candidate.timeframe_minutes,
            "session": candidate.session,
            "holding_minutes": candidate.holding_minutes,
            "direction_mode": candidate.direction_mode,
            "exit_profile": candidate.exit_profile,
            "entry_ts": timestamps[signal_indexes],
            "exit_ts": timestamps[exit_indexes],
            "symbol": symbols[signal_indexes],
            "direction": directions,
            "entry_price": entry_prices,
            "exit_price": exit_prices,
            "exit_reason": "time",
            "gross_points": gross_points,
            "net_points": net_points,
            "net_dollars": net_points * costs.point_value,
            "entry_index": signal_indexes,
            "exit_index": exit_indexes,
        }
    )


def select_non_overlapping_signal_indexes(entry_indexes: np.ndarray, frame_length: int, hold_bars: int) -> np.ndarray:
    entry_indexes = np.asarray(entry_indexes, dtype=int)
    entry_indexes = entry_indexes[entry_indexes + hold_bars < frame_length]
    if len(entry_indexes) == 0:
        return np.asarray([], dtype=int)
    selected_signal_indexes: list[int] = []
    next_available_index = 0
    for signal_index in entry_indexes:
        entry_index = int(signal_index) + 1
        exit_index = int(signal_index) + hold_bars
        if entry_index < next_available_index:
            continue
        selected_signal_indexes.append(int(signal_index))
        next_available_index = exit_index + 1
    return np.asarray(selected_signal_indexes, dtype=int)


def summarize_trades(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "net_dollars": 0.0,
            "max_drawdown_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_points": 0.0,
            "tail_loss_p05": 0.0,
            "worst_trade_points": 0.0,
            "stability": 0.0,
            "score": 0.0,
        }
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    wins = net[net > 0].sum()
    losses = abs(net[net < 0].sum())
    split_ts = pd.to_datetime(trades["entry_ts"], utc=True).median()
    first_half = net[pd.to_datetime(trades["entry_ts"], utc=True) <= split_ts]
    second_half = net[pd.to_datetime(trades["entry_ts"], utc=True) > split_ts]
    first_points = float(first_half.sum()) if not first_half.empty else 0.0
    second_points = float(second_half.sum()) if not second_half.empty else 0.0
    if first_points > 0 and second_points > 0:
        stability = min(first_points, second_points) / max(first_points, second_points)
    elif first_points + second_points > 0:
        stability = 0.25
    else:
        stability = 0.0
    max_drawdown = float(abs(drawdown.min()))
    tail_loss = float(net.quantile(0.05))
    risk = max(max_drawdown, abs(tail_loss), 1.0)
    score = float((float(equity.iloc[-1]) / risk) * sqrt(min(len(net), 300) / 300) * (0.75 + 0.25 * stability))
    return {
        "trades": int(len(net)),
        "net_points": float(equity.iloc[-1]),
        "net_dollars": float(equity.iloc[-1] * BacktestCosts().point_value),
        "max_drawdown_points": max_drawdown,
        "profit_factor": float(wins / losses) if losses else (999.0 if wins > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "avg_points": float(net.mean()),
        "tail_loss_p05": tail_loss,
        "worst_trade_points": float(net.min()),
        "stability": float(stability),
        "score": score,
    }


def train_passes(summary: dict[str, Any], args: argparse.Namespace) -> bool:
    return (
        int(summary["trades"]) >= args.min_train_trades
        and float(summary["net_points"]) > 0
        and float(summary["profit_factor"]) >= args.min_train_profit_factor
        and float(summary["score"]) > 0
    )


def test_passes(summary: dict[str, Any], args: argparse.Namespace) -> bool:
    return (
        int(summary["trades"]) >= args.min_test_trades
        and float(summary["net_points"]) > 0
        and float(summary["profit_factor"]) >= args.min_test_profit_factor
    )


def walk_forward(
    frames_by_timeframe: dict[int, pd.DataFrame],
    candidates: list[LightglowCandidate],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    costs = BacktestCosts()
    trade_cache: dict[str, pd.DataFrame] = {}
    candidate_by_name = {candidate.name: candidate for candidate in candidates}
    time_exit_index_cache: dict[tuple[int, str, str, int, str], np.ndarray] = {}
    for candidate_index, candidate in enumerate(candidates, start=1):
        if candidate_index == 1 or candidate_index % 100 == 0 or candidate_index == len(candidates):
            print(f"building trades {candidate_index}/{len(candidates)}: {candidate.name}", flush=True)
        frame = frames_by_timeframe[candidate.timeframe_minutes]
        if candidate.stop_loss_points is None and candidate.take_profit_points is None:
            base_signal = pd.to_numeric(frame[candidate.signal], errors="coerce").fillna(0).astype(int)
            if candidate.direction_mode == "reverse":
                signal = -base_signal
            else:
                signal = base_signal
            signal = signal.where(session_mask(frame, candidate.session), 0)
            signal = signal.where(signal != signal.shift(1), 0)
            cache_key = (
                candidate.timeframe_minutes,
                candidate.signal,
                candidate.session,
                candidate.hold_bars,
                candidate.direction_mode,
            )
            selected_indexes = time_exit_index_cache.get(cache_key)
            if selected_indexes is None:
                selected_indexes = select_non_overlapping_signal_indexes(
                    np.flatnonzero(signal.to_numpy() != 0),
                    len(frame),
                    max(1, candidate.hold_bars),
                )
                time_exit_index_cache[cache_key] = selected_indexes
            trades = build_time_exit_trades(
                frame,
                signal,
                candidate,
                costs,
                selected_signal_indexes=selected_indexes,
            )
        else:
            trades = build_trades(frame, candidate, costs)
        if not trades.empty:
            trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
            trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
        trade_cache[candidate.name] = trades

    fold_rows: list[dict[str, Any]] = []
    selected_trades: list[pd.DataFrame] = []
    start = pd.Timestamp(args.walk_start_date, tz="UTC")
    end = pd.Timestamp(args.end_date, tz="UTC")
    fold = 0
    test_start = start
    while test_start + pd.Timedelta(days=args.test_days) <= end:
        train_start = test_start - pd.Timedelta(days=args.purge_days + args.train_days)
        train_end = test_start - pd.Timedelta(days=args.purge_days)
        test_end = test_start + pd.Timedelta(days=args.test_days)
        ranked: list[tuple[float, dict[str, Any], LightglowCandidate]] = []
        for name, trades in trade_cache.items():
            if trades.empty:
                continue
            train_trades = trades[(trades["entry_ts"] >= train_start) & (trades["entry_ts"] < train_end)]
            train_summary = summarize_trades(train_trades)
            if train_passes(train_summary, args):
                ranked.append((float(train_summary["score"]), train_summary, candidate_by_name[name]))
        ranked.sort(reverse=True, key=lambda item: (item[0], item[1]["net_points"], item[1]["profit_factor"]))
        for rank, (_, train_summary, candidate) in enumerate(ranked[: args.max_fold_candidates], start=1):
            trades = trade_cache[candidate.name]
            test_trades = trades[(trades["entry_ts"] >= test_start) & (trades["entry_ts"] < test_end)].copy()
            test_summary = summarize_trades(test_trades)
            row = {
                "fold": fold,
                "fold_rank": rank,
                "candidate": candidate.name,
                "signal": candidate.signal,
                "timeframe_minutes": candidate.timeframe_minutes,
                "session": candidate.session,
                "holding_minutes": candidate.holding_minutes,
                "direction_mode": candidate.direction_mode,
                "exit_profile": candidate.exit_profile,
                "train_start": str(train_start.date()),
                "train_end": str(train_end.date()),
                "test_start": str(test_start.date()),
                "test_end": str(test_end.date()),
                "test_pass": bool(test_passes(test_summary, args)),
                **{f"train_{key}": value for key, value in train_summary.items()},
                **{f"test_{key}": value for key, value in test_summary.items()},
            }
            fold_rows.append(row)
            if not test_trades.empty:
                test_trades["fold"] = fold
                test_trades["fold_rank"] = rank
                test_trades["test_pass"] = bool(row["test_pass"])
                selected_trades.append(test_trades)
        fold += 1
        test_start += pd.Timedelta(days=args.step_days)

    folds = pd.DataFrame(fold_rows)
    trades = pd.concat(selected_trades, ignore_index=True, sort=False) if selected_trades else pd.DataFrame()
    all_rows = []
    for candidate in candidates:
        summary = summarize_trades(trade_cache[candidate.name])
        all_rows.append(
            {
                "candidate": candidate.name,
                **candidate.__dict__,
                "holding_minutes": candidate.holding_minutes,
                "exit_profile": candidate.exit_profile,
                **summary,
            }
        )
    full_sample = pd.DataFrame(all_rows).sort_values(["score", "net_points"], ascending=[False, False])
    return folds, aggregate_results(folds), trades, full_sample


def aggregate_results(folds: pd.DataFrame) -> pd.DataFrame:
    if folds.empty:
        return pd.DataFrame()
    grouped = folds.groupby("candidate", as_index=False).agg(
        signal=("signal", "first"),
        timeframe_minutes=("timeframe_minutes", "first"),
        session=("session", "first"),
        holding_minutes=("holding_minutes", "first"),
        direction_mode=("direction_mode", "first"),
        exit_profile=("exit_profile", "first"),
        selected_folds=("fold", "nunique"),
        positive_test_folds=("test_net_points", lambda values: int((values > 0).sum())),
        pass_folds=("test_pass", "sum"),
        test_trades=("test_trades", "sum"),
        test_net_points=("test_net_points", "sum"),
        test_net_dollars=("test_net_dollars", "sum"),
        test_max_drawdown_points=("test_max_drawdown_points", "max"),
        avg_test_profit_factor=("test_profit_factor", "mean"),
        avg_test_win_rate=("test_win_rate", "mean"),
        avg_test_stability=("test_stability", "mean"),
        min_test_net_points=("test_net_points", "min"),
        train_net_points=("train_net_points", "sum"),
        avg_train_score=("train_score", "mean"),
    )
    grouped["positive_test_fold_rate"] = grouped["positive_test_folds"] / grouped["selected_folds"].clip(lower=1)
    grouped["pass_fold_rate"] = grouped["pass_folds"] / grouped["selected_folds"].clip(lower=1)
    grouped["net_to_drawdown"] = grouped["test_net_points"] / grouped["test_max_drawdown_points"].clip(lower=1.0)
    grouped["positive_return_candidate"] = grouped["test_net_points"] > 0
    grouped["stable_candidate"] = (grouped["selected_folds"] >= 3) & (grouped["positive_test_fold_rate"] >= 0.5)
    grouped["ranking_score"] = (
        grouped["test_net_points"].clip(lower=0) * 0.001
        + grouped["net_to_drawdown"].clip(lower=0)
        * grouped["positive_test_fold_rate"].clip(lower=0.01)
        * (grouped["selected_folds"].clip(upper=8) / 8)
    )
    return grouped.sort_values(
        ["positive_return_candidate", "stable_candidate", "ranking_score", "test_net_points"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    rows = ["| " + " | ".join(frame.columns) + " |", "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    for _, row in frame.iterrows():
        values = []
        for column in frame.columns:
            value = row[column]
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def write_report(
    path: Path,
    folds: pd.DataFrame,
    aggregate: pd.DataFrame,
    full_sample: pd.DataFrame,
    frames_by_timeframe: dict[int, pd.DataFrame],
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    first_frame = frames_by_timeframe[min(frames_by_timeframe)]
    top_positive = aggregate[aggregate["test_net_points"] > 0].copy() if not aggregate.empty else pd.DataFrame()
    lines = [
        "# NQ Lightglow 5y Bar Backtest",
        "",
        "## Verdict",
        "",
    ]
    if top_positive.empty:
        lines.append("No train-selected lightglow candidate produced positive aggregate future test net points.")
    else:
        top = top_positive.iloc[0]
        lines.append(
            "Best positive candidate: "
            f"`{top['candidate']}` with `{top['test_net_points']:.4f}` future test net points, "
            f"`{top['positive_test_fold_rate']:.2%}` positive selected folds, "
            f"`{top['avg_test_profit_factor']:.4f}` average test PF, "
            f"`{top['timeframe_minutes']}` minute bars, and `{top['holding_minutes']}` minute holding."
        )
        lines.append("")
        lines.append(
            "This is a research result: the script approximates the Pine indicator from "
            "`docs/Strategy/lightglow.md` on OHLCV bars and uses walk-forward selection before scoring future folds."
        )
    lines.extend(
        [
            "",
            "## Data And Method",
            "",
            f"- Source: `{_bar_zip_path()}`.",
            f"- Requested span: `{args.start_date}` to `{args.end_date}`.",
            f"- Loaded 1m span: `{first_frame['ts'].min()}` to `{first_frame['ts'].max()}`.",
            f"- 1m rows: `{len(first_frame):,}`.",
            f"- Timeframes tested: `{', '.join(str(value) + 'm' for value in args.timeframes)}`.",
            "- Continuous NQ construction: one futures row per minute, selected upstream by highest reported volume.",
            "- Costs: one tick slippage per side plus commission from `BacktestCosts`.",
            "",
            "## Lightglow Signals Tested",
            "",
            "- Internal and swing BOS/CHoCH from confirmed pivot structure breaks.",
            "- Fair value gaps, equal high/low reversals, internal/swing order block breaks.",
            "- Premium/discount zone reversals and two confluence variants: CHoCH-zone and FVG-zone.",
            "- Native and reverse direction variants are both tested because several SMC events can be continuation or liquidity-fade signals.",
            "",
            "## Walk-Forward Design",
            "",
            f"- Train days: `{args.train_days}`; purge days: `{args.purge_days}`; test days: `{args.test_days}`; step days: `{args.step_days}`.",
            f"- Walk-forward start: `{args.walk_start_date}`.",
            f"- Sessions: `{', '.join(args.sessions)}`.",
            f"- Hold bars: `{', '.join(str(value) for value in args.hold_bars)}`.",
            f"- Direction modes: `{', '.join(args.direction_modes)}`.",
            f"- Exit profiles: `{', '.join(args.exit_profiles)}`.",
            f"- Train gate: trades >= `{args.min_train_trades}`, PF >= `{args.min_train_profit_factor}`, net > `0`.",
            f"- Test pass label: trades >= `{args.min_test_trades}`, PF >= `{args.min_test_profit_factor}`, net > `0`.",
            "",
            "## Output Summary",
            "",
            f"- Fold rows: `{len(folds):,}`.",
            f"- Aggregated train-selected candidates: `{len(aggregate):,}`.",
            f"- Positive aggregate candidates: `{len(top_positive):,}`.",
            f"- Full-sample candidates evaluated: `{len(full_sample):,}`.",
            "",
        ]
    )
    if not top_positive.empty:
        display_columns = [
            "candidate",
            "signal",
            "timeframe_minutes",
            "session",
            "holding_minutes",
            "direction_mode",
            "exit_profile",
            "selected_folds",
            "positive_test_fold_rate",
            "pass_fold_rate",
            "test_trades",
            "test_net_points",
            "test_max_drawdown_points",
            "net_to_drawdown",
            "avg_test_profit_factor",
            "avg_test_win_rate",
            "min_test_net_points",
        ]
        per_timeframe = top_positive.sort_values(
            ["timeframe_minutes", "ranking_score", "test_net_points"],
            ascending=[True, False, False],
        ).groupby("timeframe_minutes", as_index=False).head(1)
        lines.extend(["## Best Positive Candidate By Timeframe", "", markdown_table(per_timeframe[display_columns]), ""])
        lines.extend(["## Positive Walk-Forward Ranking", "", markdown_table(top_positive.head(30)[display_columns]), ""])
    if not aggregate.empty:
        fold_columns = [
            "test_pass",
            "candidate",
            "fold",
            "fold_rank",
            "train_trades",
            "train_net_points",
            "train_profit_factor",
            "test_trades",
            "test_net_points",
            "test_profit_factor",
            "test_win_rate",
        ]
        top_folds = folds.sort_values(["test_pass", "test_net_points"], ascending=[False, False]).head(30)
        lines.extend(["## Best Future Fold Rows", "", markdown_table(top_folds[fold_columns]), ""])
    full_display = full_sample[full_sample["net_points"] > 0].head(20)
    if not full_display.empty:
        columns = [
            "candidate",
            "signal",
            "timeframe_minutes",
            "session",
            "holding_minutes",
            "direction_mode",
            "exit_profile",
            "trades",
            "net_points",
            "profit_factor",
            "win_rate",
            "max_drawdown_points",
        ]
        lines.extend(["## Full-Sample Positive Sanity Check", "", markdown_table(full_display[columns]), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest docs/Strategy/lightglow.md SMC signals on 5y NQ bars.")
    parser.add_argument("--start-date", default="2021-04-28")
    parser.add_argument("--walk-start-date", default="2022-04-28")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-lightglow-continuous-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/nq-lightglow-5y-walkforward.csv")
    parser.add_argument("--aggregate-output", default=".tmp/nq-lightglow-5y-walkforward-aggregate.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-lightglow-5y-walkforward-trades.csv")
    parser.add_argument("--full-sample-output", default=".tmp/nq-lightglow-5y-full-sample.csv")
    parser.add_argument("--report", default="reports/NQ-lightglow-5y-bar-backtest.md")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--timeframes", type=int, nargs="+", default=[1, 3, 5, 15])
    parser.add_argument("--sessions", nargs="+", default=["all", "europe", "us_rth", "us_late", "asia"])
    parser.add_argument("--hold-bars", type=int, nargs="+", default=[1, 2, 3, 5])
    parser.add_argument("--direction-modes", nargs="+", choices=["native", "reverse"], default=["native", "reverse"])
    parser.add_argument("--exit-profiles", nargs="+", default=["time"])
    parser.add_argument("--train-days", type=int, default=365)
    parser.add_argument("--purge-days", type=int, default=5)
    parser.add_argument("--test-days", type=int, default=90)
    parser.add_argument("--step-days", type=int, default=90)
    parser.add_argument("--max-fold-candidates", type=int, default=25)
    parser.add_argument("--min-train-trades", type=int, default=40)
    parser.add_argument("--min-test-trades", type=int, default=5)
    parser.add_argument("--min-train-profit-factor", type=float, default=1.03)
    parser.add_argument("--min-test-profit-factor", type=float, default=1.0)
    args = parser.parse_args()

    base_features = load_continuous_nq_bars(args)
    frames_by_timeframe: dict[int, pd.DataFrame] = {}
    for timeframe in args.timeframes:
        print(f"building lightglow signals for {timeframe}m", flush=True)
        bars = resample_ohlcv(base_features, int(timeframe))
        frames_by_timeframe[int(timeframe)] = build_lightglow_signals(bars)

    signal_names = [
        "internal_bos",
        "internal_choch",
        "swing_bos",
        "swing_choch",
        "fvg",
        "equal_level_reversal",
        "internal_ob_break",
        "swing_ob_break",
        "premium_discount_reversal",
        "internal_choch_zone",
        "fvg_zone",
    ]
    candidates = candidate_pool(args, signal_names)
    folds, aggregate, trades, full_sample = walk_forward(frames_by_timeframe, candidates, args)
    for output_path, frame in [
        (args.output, folds),
        (args.aggregate_output, aggregate),
        (args.trades_output, trades),
        (args.full_sample_output, full_sample),
    ]:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    write_report(Path(args.report), folds, aggregate, full_sample, frames_by_timeframe, args)
    result = {
        "source": str(_bar_zip_path()),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "timeframes": args.timeframes,
        "candidate_count": len(candidates),
        "fold_rows": len(folds),
        "aggregate_rows": len(aggregate),
        "positive_aggregate_rows": int((aggregate["test_net_points"] > 0).sum()) if not aggregate.empty else 0,
        "output": args.output,
        "aggregate_output": args.aggregate_output,
        "trades_output": args.trades_output,
        "full_sample_output": args.full_sample_output,
        "report": args.report,
    }
    if not aggregate.empty:
        positive = aggregate[aggregate["test_net_points"] > 0]
        if not positive.empty:
            result["top_positive_candidate"] = positive.iloc[0].to_dict()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
