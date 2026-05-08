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
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.dataflows.databento import _bar_zip_path


_FRAME_CACHE: dict[int, dict[str, Any]] = {}


@dataclass(frozen=True)
class TrendCandidate:
    family: str
    timeframe_minutes: int
    session: str
    lookback: int
    threshold: float
    holding_bars: int
    direction_filter: str
    exit_profile: str
    stop_loss_points: float | None
    take_profit_points: float | None
    atr_length: int = 14
    fast: int = 9
    slow: int = 21

    @property
    def holding_minutes(self) -> int:
        return int(self.timeframe_minutes * self.holding_bars)

    @property
    def name(self) -> str:
        parts = [
            "trend",
            self.family,
            f"{self.timeframe_minutes}m",
            self.session,
            f"lb{self.lookback}",
            f"thr{self.threshold:g}",
            f"hold{self.holding_minutes}m",
            self.direction_filter,
            self.exit_profile,
        ]
        if self.family.startswith("ema"):
            parts.insert(5, f"ema{self.fast}_{self.slow}")
        if self.family.startswith("adx"):
            parts.insert(5, f"adx{self.atr_length}")
        return "_".join(parts)


def resample_ohlcv(features: pd.DataFrame, timeframe_minutes: int) -> pd.DataFrame:
    data = features[["ts", "symbol", "Open", "High", "Low", "Close", "Volume"]].copy()
    data["ts"] = pd.to_datetime(data["ts"], utc=True)
    if timeframe_minutes == 1:
        result = data.sort_values("ts").reset_index(drop=True)
    else:
        result = (
            data.set_index("ts")
            .resample(f"{timeframe_minutes}min", label="left", closed="left")
            .agg(
                Open=("Open", "first"),
                High=("High", "max"),
                Low=("Low", "min"),
                Close=("Close", "last"),
                Volume=("Volume", "sum"),
                symbol=("symbol", "last"),
            )
            .dropna(subset=["Open", "High", "Low", "Close"])
            .reset_index()
        )
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["trade_date"] = result["ts"].dt.date
    result["minute_of_day"] = result["ts"].dt.hour * 60 + result["ts"].dt.minute
    result["timeframe_minutes"] = timeframe_minutes
    return result.dropna(subset=["Open", "High", "Low", "Close"]).reset_index(drop=True)


def add_trend_features(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy().reset_index(drop=True)
    high = data["High"].astype(float)
    low = data["Low"].astype(float)
    close = data["Close"].astype(float)
    volume = data["Volume"].astype(float)
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    data["atr14"] = true_range.rolling(14, min_periods=5).mean()
    data["atr30"] = true_range.rolling(30, min_periods=10).mean()
    data["range_points"] = high - low
    data["body_points"] = (close - data["Open"].astype(float)).abs()
    data["volume_z60"] = (volume - volume.rolling(60, min_periods=20).mean()) / volume.rolling(60, min_periods=20).std()
    data["session_vwap"] = session_vwap(data)
    for period in [9, 13, 21, 34, 55, 89]:
        data[f"ema{period}"] = close.ewm(span=period, adjust=False, min_periods=period).mean()
    for period in [20, 30, 50, 60, 90]:
        data[f"roll_high_{period}"] = high.rolling(period, min_periods=period).max().shift(1)
        data[f"roll_low_{period}"] = low.rolling(period, min_periods=period).min().shift(1)
        data[f"momentum_{period}"] = close.pct_change(period)
    for period in [14, 30]:
        plus_di, minus_di, adx = directional_indicators(high, low, close, period)
        data[f"plus_di_{period}"] = plus_di
        data[f"minus_di_{period}"] = minus_di
        data[f"adx_{period}"] = adx
    return data


def session_vwap(frame: pd.DataFrame) -> pd.Series:
    price_volume = frame["Close"].astype(float) * frame["Volume"].astype(float)
    grouped_pv = price_volume.groupby(frame["trade_date"]).cumsum()
    grouped_volume = frame["Volume"].astype(float).replace(0, np.nan).groupby(frame["trade_date"]).cumsum()
    return grouped_pv / grouped_volume


def directional_indicators(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index)
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr.replace(0, np.nan)
    minus_di = 100.0 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr.replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return plus_di, minus_di, adx


def session_mask(frame: pd.DataFrame, session: str) -> np.ndarray:
    minute = frame["minute_of_day"].to_numpy()
    if session == "all":
        return np.ones(len(frame), dtype=bool)
    if session == "europe":
        return (minute >= 7 * 60) & (minute < 13 * 60 + 30)
    if session == "us_rth":
        return (minute >= 13 * 60 + 30) & (minute < 20 * 60)
    if session == "us_late":
        return (minute >= 20 * 60) & (minute < 23 * 60)
    if session == "asia":
        return (minute < 7 * 60) | (minute >= 23 * 60)
    raise ValueError(f"unknown session: {session}")


def candidate_pool(args: argparse.Namespace) -> list[TrendCandidate]:
    candidates: list[TrendCandidate] = []
    exit_profiles = [parse_exit_profile(profile) for profile in args.exit_profiles]
    for timeframe in args.timeframes:
        hold_bars_values = [max(1, int(round(minutes / timeframe))) for minutes in args.holding_minutes]
        for family in args.families:
            for session in args.sessions:
                for direction_filter in args.direction_filters:
                    for hold_bars in hold_bars_values:
                        for profile, stop_loss, take_profit in exit_profiles:
                            for candidate in family_candidates(
                                family,
                                int(timeframe),
                                session,
                                hold_bars,
                                direction_filter,
                                profile,
                                stop_loss,
                                take_profit,
                                args,
                            ):
                                candidates.append(candidate)
    return candidates


def family_candidates(
    family: str,
    timeframe: int,
    session: str,
    hold_bars: int,
    direction_filter: str,
    exit_profile: str,
    stop_loss: float | None,
    take_profit: float | None,
    args: argparse.Namespace,
) -> list[TrendCandidate]:
    candidates: list[TrendCandidate] = []
    if family in {"donchian_breakout", "donchian_atr_breakout", "vwap_trend_pullback"}:
        for lookback in args.lookbacks:
            thresholds = args.atr_thresholds if family == "donchian_atr_breakout" else [0.0]
            if family == "vwap_trend_pullback":
                thresholds = args.vwap_pullback_atr
            for threshold in thresholds:
                candidates.append(
                    TrendCandidate(
                        family=family,
                        timeframe_minutes=timeframe,
                        session=session,
                        lookback=int(lookback),
                        threshold=float(threshold),
                        holding_bars=hold_bars,
                        direction_filter=direction_filter,
                        exit_profile=exit_profile,
                        stop_loss_points=stop_loss,
                        take_profit_points=take_profit,
                    )
                )
        return candidates
    if family in {"ema_trend", "ema_pullback"}:
        for fast, slow in args.ema_pairs:
            for threshold in ([0.0] if family == "ema_trend" else args.vwap_pullback_atr):
                candidates.append(
                    TrendCandidate(
                        family=family,
                        timeframe_minutes=timeframe,
                        session=session,
                        lookback=int(slow),
                        threshold=float(threshold),
                        holding_bars=hold_bars,
                        direction_filter=direction_filter,
                        exit_profile=exit_profile,
                        stop_loss_points=stop_loss,
                        take_profit_points=take_profit,
                        fast=int(fast),
                        slow=int(slow),
                    )
                )
        return candidates
    if family == "adx_di_trend":
        for period in args.adx_periods:
            for threshold in args.adx_thresholds:
                candidates.append(
                    TrendCandidate(
                        family=family,
                        timeframe_minutes=timeframe,
                        session=session,
                        lookback=int(period),
                        threshold=float(threshold),
                        holding_bars=hold_bars,
                        direction_filter=direction_filter,
                        exit_profile=exit_profile,
                        stop_loss_points=stop_loss,
                        take_profit_points=take_profit,
                        atr_length=int(period),
                    )
                )
        return candidates
    if family == "opening_range_breakout":
        for lookback in args.opening_range_minutes:
            for threshold in args.atr_thresholds:
                candidates.append(
                    TrendCandidate(
                        family=family,
                        timeframe_minutes=timeframe,
                        session=session,
                        lookback=int(lookback),
                        threshold=float(threshold),
                        holding_bars=hold_bars,
                        direction_filter=direction_filter,
                        exit_profile=exit_profile,
                        stop_loss_points=stop_loss,
                        take_profit_points=take_profit,
                    )
                )
        return candidates
    raise ValueError(f"unknown family: {family}")


def parse_exit_profile(profile: str) -> tuple[str, float | None, float | None]:
    if profile == "time":
        return profile, None, None
    stop_text, target_text = profile.removeprefix("sl").split("_tp", 1)
    return profile, float(stop_text), float(target_text)


def build_signal(frame: pd.DataFrame, candidate: TrendCandidate) -> np.ndarray:
    close = frame["Close"].to_numpy(dtype=float)
    high = frame["High"].to_numpy(dtype=float)
    low = frame["Low"].to_numpy(dtype=float)
    signal = np.zeros(len(frame), dtype=np.int8)
    if candidate.family == "donchian_breakout":
        upper = frame[f"roll_high_{candidate.lookback}"].to_numpy(dtype=float)
        lower = frame[f"roll_low_{candidate.lookback}"].to_numpy(dtype=float)
        signal[(close > upper)] = 1
        signal[(close < lower)] = -1
    elif candidate.family == "donchian_atr_breakout":
        upper = frame[f"roll_high_{candidate.lookback}"].to_numpy(dtype=float)
        lower = frame[f"roll_low_{candidate.lookback}"].to_numpy(dtype=float)
        atr = frame["atr14"].to_numpy(dtype=float)
        signal[(close > upper + candidate.threshold * atr)] = 1
        signal[(close < lower - candidate.threshold * atr)] = -1
    elif candidate.family == "vwap_trend_pullback":
        upper = frame[f"roll_high_{candidate.lookback}"].to_numpy(dtype=float)
        lower = frame[f"roll_low_{candidate.lookback}"].to_numpy(dtype=float)
        vwap = frame["session_vwap"].to_numpy(dtype=float)
        atr = frame["atr14"].to_numpy(dtype=float)
        prior_close = np.r_[np.nan, close[:-1]]
        long_trend = close > upper
        short_trend = close < lower
        long_pullback = (low <= vwap + candidate.threshold * atr) & (close > vwap) & (close > prior_close)
        short_pullback = (high >= vwap - candidate.threshold * atr) & (close < vwap) & (close < prior_close)
        signal[long_trend & long_pullback] = 1
        signal[short_trend & short_pullback] = -1
    elif candidate.family == "ema_trend":
        fast = frame[f"ema{candidate.fast}"].to_numpy(dtype=float)
        slow = frame[f"ema{candidate.slow}"].to_numpy(dtype=float)
        signal[(fast > slow) & (close > fast)] = 1
        signal[(fast < slow) & (close < fast)] = -1
    elif candidate.family == "ema_pullback":
        fast = frame[f"ema{candidate.fast}"].to_numpy(dtype=float)
        slow = frame[f"ema{candidate.slow}"].to_numpy(dtype=float)
        atr = frame["atr14"].to_numpy(dtype=float)
        prior_close = np.r_[np.nan, close[:-1]]
        long_setup = (fast > slow) & (low <= fast + candidate.threshold * atr) & (close > fast) & (close > prior_close)
        short_setup = (fast < slow) & (high >= fast - candidate.threshold * atr) & (close < fast) & (close < prior_close)
        signal[long_setup] = 1
        signal[short_setup] = -1
    elif candidate.family == "adx_di_trend":
        adx = frame[f"adx_{candidate.atr_length}"].to_numpy(dtype=float)
        plus_di = frame[f"plus_di_{candidate.atr_length}"].to_numpy(dtype=float)
        minus_di = frame[f"minus_di_{candidate.atr_length}"].to_numpy(dtype=float)
        signal[(adx >= candidate.threshold) & (plus_di > minus_di) & (close > np.r_[np.nan, close[:-1]])] = 1
        signal[(adx >= candidate.threshold) & (minus_di > plus_di) & (close < np.r_[np.nan, close[:-1]])] = -1
    elif candidate.family == "opening_range_breakout":
        signal = opening_range_signal(frame, candidate)
    else:
        raise ValueError(candidate.family)

    if candidate.direction_filter == "long":
        signal = np.where(signal > 0, signal, 0).astype(np.int8)
    elif candidate.direction_filter == "short":
        signal = np.where(signal < 0, signal, 0).astype(np.int8)
    elif candidate.direction_filter != "both":
        raise ValueError(candidate.direction_filter)
    signal[~session_mask(frame, candidate.session)] = 0
    previous = np.empty_like(signal)
    previous[0] = 0
    previous[1:] = signal[:-1]
    return np.where(signal != previous, signal, 0).astype(np.int8)


def opening_range_signal(frame: pd.DataFrame, candidate: TrendCandidate) -> np.ndarray:
    signal = np.zeros(len(frame), dtype=np.int8)
    if candidate.session != "us_rth":
        return signal
    data = frame[["trade_date", "minute_of_day", "High", "Low", "Close", "atr14"]].copy()
    bars_in_range = max(1, int(round(candidate.lookback / candidate.timeframe_minutes)))
    rth_start = 13 * 60 + 30
    data["rth_bar"] = ((data["minute_of_day"] - rth_start) / candidate.timeframe_minutes).astype(int)
    opening = data[(data["minute_of_day"] >= rth_start) & (data["rth_bar"] >= 0) & (data["rth_bar"] < bars_in_range)]
    ranges = opening.groupby("trade_date").agg(opening_high=("High", "max"), opening_low=("Low", "min"))
    merged = data.join(ranges, on="trade_date")
    active = data["rth_bar"] >= bars_in_range
    close = data["Close"].to_numpy(dtype=float)
    atr = data["atr14"].to_numpy(dtype=float)
    upper = merged["opening_high"].to_numpy(dtype=float)
    lower = merged["opening_low"].to_numpy(dtype=float)
    active_values = active.to_numpy(dtype=bool)
    signal[active_values & (close > upper + candidate.threshold * atr)] = 1
    signal[active_values & (close < lower - candidate.threshold * atr)] = -1
    return signal


def build_trades(frame: pd.DataFrame, candidate: TrendCandidate, costs: BacktestCosts) -> pd.DataFrame:
    signal = build_signal(frame, candidate)
    entry_indexes = np.flatnonzero(signal != 0)
    if len(entry_indexes) == 0:
        return pd.DataFrame()
    hold_bars = max(1, candidate.holding_bars)
    cache = frame_cache(frame)
    open_prices = cache["open"]
    high_prices = cache["high"]
    low_prices = cache["low"]
    close_prices = cache["close"]
    timestamps = cache["timestamps"]
    symbols_text = cache["symbols_text"]
    symbols_code = cache["symbols_code"]
    rows: list[dict[str, Any]] = []
    next_available_index = 0
    for signal_index in entry_indexes:
        entry_index = int(signal_index) + 1
        exit_index = int(signal_index) + hold_bars
        if entry_index < next_available_index or exit_index >= len(frame):
            continue
        if not np.all(symbols_code[entry_index : exit_index + 1] == symbols_code[signal_index]):
            continue
        direction = int(signal[signal_index])
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
                "family": candidate.family,
                "timeframe_minutes": candidate.timeframe_minutes,
                "session": candidate.session,
                "holding_minutes": candidate.holding_minutes,
                "direction_filter": candidate.direction_filter,
                "exit_profile": candidate.exit_profile,
                "entry_ts": timestamps[signal_index],
                "exit_ts": timestamps[realized_exit_index],
                "symbol": symbols_text[signal_index],
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


def frame_cache(frame: pd.DataFrame) -> dict[str, Any]:
    cache = _FRAME_CACHE.setdefault(id(frame), {})
    if not cache:
        symbols = frame["symbol"].astype(str)
        cache["open"] = frame["Open"].to_numpy(dtype=float, copy=False)
        cache["high"] = frame["High"].to_numpy(dtype=float, copy=False)
        cache["low"] = frame["Low"].to_numpy(dtype=float, copy=False)
        cache["close"] = frame["Close"].to_numpy(dtype=float, copy=False)
        cache["timestamps"] = frame["ts"].to_numpy()
        cache["symbols_text"] = symbols.to_numpy()
        cache["symbols_code"] = pd.factorize(symbols, sort=False)[0]
    return cache


def summarize_trades(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return empty_summary()
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    wins = net[net > 0].sum()
    losses = abs(net[net < 0].sum())
    split_ts = pd.to_datetime(trades["entry_ts"], utc=True).median()
    first = net[pd.to_datetime(trades["entry_ts"], utc=True) <= split_ts]
    second = net[pd.to_datetime(trades["entry_ts"], utc=True) > split_ts]
    first_points = float(first.sum()) if not first.empty else 0.0
    second_points = float(second.sum()) if not second.empty else 0.0
    if first_points > 0 and second_points > 0:
        stability = min(first_points, second_points) / max(first_points, second_points)
    elif first_points + second_points > 0:
        stability = 0.25
    else:
        stability = 0.0
    max_drawdown = float(abs(drawdown.min()))
    tail_loss = float(net.quantile(0.05))
    risk = max(max_drawdown, abs(tail_loss), 1.0)
    score = float((float(equity.iloc[-1]) / risk) * sqrt(min(len(net), 300) / 300) * (0.65 + 0.35 * stability))
    reasons = trades["exit_reason"].astype(str)
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
        "target_exit_share": float((reasons == "take_profit").mean()),
        "stop_exit_share": float((reasons == "stop_loss").mean()),
        "first_half_points": first_points,
        "second_half_points": second_points,
        "stability": float(stability),
        "score": score,
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
        "tail_loss_p05": 0.0,
        "worst_trade_points": 0.0,
        "target_exit_share": 0.0,
        "stop_exit_share": 0.0,
        "first_half_points": 0.0,
        "second_half_points": 0.0,
        "stability": 0.0,
        "score": 0.0,
    }


def train_passes(summary: dict[str, Any], args: argparse.Namespace) -> bool:
    return (
        int(summary["trades"]) >= args.min_train_trades
        and float(summary["net_points"]) > 0
        and float(summary["profit_factor"]) >= args.min_train_profit_factor
        and float(summary["max_drawdown_points"]) <= args.max_train_drawdown_points
        and float(summary["score"]) > 0
    )


def test_passes(summary: dict[str, Any], args: argparse.Namespace) -> bool:
    return (
        int(summary["trades"]) >= args.min_test_trades
        and float(summary["net_points"]) > 0
        and float(summary["profit_factor"]) >= args.min_test_profit_factor
        and float(summary["max_drawdown_points"]) <= args.max_test_drawdown_points
    )


def build_trade_cache(
    frames_by_timeframe: dict[int, pd.DataFrame],
    candidates: list[TrendCandidate],
    costs: BacktestCosts,
) -> dict[str, tuple[TrendCandidate, pd.DataFrame]]:
    cache: dict[str, tuple[TrendCandidate, pd.DataFrame]] = {}
    for index, candidate in enumerate(candidates, start=1):
        if index == 1 or index % 100 == 0 or index == len(candidates):
            print(f"building trades {index}/{len(candidates)}: {candidate.name}", flush=True)
        frame = frames_by_timeframe[candidate.timeframe_minutes]
        trades = build_trades(frame, candidate, costs)
        if not trades.empty:
            trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
            trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
        cache[candidate.name] = (candidate, trades)
    return cache


def summarize_cached_trades(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[dict[str, Any], pd.DataFrame]:
    if trades.empty:
        return empty_summary(), trades
    selected = trades[(trades["entry_ts"] >= start) & (trades["entry_ts"] < end)].copy()
    if selected.empty:
        return empty_summary(), selected
    return summarize_trades(selected), selected


def walk_forward(
    trade_cache: dict[str, tuple[TrendCandidate, pd.DataFrame]],
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
        ranked: list[tuple[float, dict[str, Any], TrendCandidate]] = []
        for candidate, trades in trade_cache.values():
            train_summary, _ = summarize_cached_trades(trades, train_start, train_end)
            if train_passes(train_summary, args):
                ranked.append((float(train_summary["score"]), train_summary, candidate))
        ranked.sort(reverse=True, key=lambda item: (item[0], item[1]["net_points"], item[1]["profit_factor"]))
        for rank, (_, train_summary, candidate) in enumerate(ranked[: args.max_fold_candidates], start=1):
            _, cached_trades = trade_cache[candidate.name]
            test_summary, test_trades = summarize_cached_trades(cached_trades, test_start, test_end)
            passed = test_passes(test_summary, args)
            row = {
                "fold": fold,
                "fold_rank": rank,
                "candidate": candidate.name,
                "family": candidate.family,
                "timeframe_minutes": candidate.timeframe_minutes,
                "session": candidate.session,
                "lookback": candidate.lookback,
                "threshold": candidate.threshold,
                "holding_minutes": candidate.holding_minutes,
                "direction_filter": candidate.direction_filter,
                "exit_profile": candidate.exit_profile,
                "train_start": str(train_start.date()),
                "train_end": str(train_end.date()),
                "test_start": str(test_start.date()),
                "test_end": str(test_end.date()),
                "test_pass": bool(passed),
                **{f"train_{key}": value for key, value in train_summary.items()},
                **{f"test_{key}": value for key, value in test_summary.items()},
            }
            fold_rows.append(row)
            if not test_trades.empty:
                exported = test_trades.copy()
                exported["fold"] = fold
                exported["fold_rank"] = rank
                exported["candidate"] = candidate.name
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
        family=("family", "first"),
        timeframe_minutes=("timeframe_minutes", "first"),
        session=("session", "first"),
        lookback=("lookback", "first"),
        threshold=("threshold", "first"),
        holding_minutes=("holding_minutes", "first"),
        direction_filter=("direction_filter", "first"),
        exit_profile=("exit_profile", "first"),
        selected_folds=("fold", "nunique"),
        positive_test_folds=("test_net_points", lambda values: int((values > 0).sum())),
        pass_folds=("test_pass", "sum"),
        test_trades=("test_trades", "sum"),
        test_net_points=("test_net_points", "sum"),
        test_max_drawdown_points=("test_max_drawdown_points", "max"),
        avg_test_profit_factor=("test_profit_factor", "mean"),
        avg_test_win_rate=("test_win_rate", "mean"),
        avg_test_avg_points=("test_avg_points", "mean"),
        avg_test_stability=("test_stability", "mean"),
        min_test_net_points=("test_net_points", "min"),
        train_net_points=("train_net_points", "sum"),
        avg_train_score=("train_score", "mean"),
    )
    grouped["positive_test_fold_rate"] = grouped["positive_test_folds"] / grouped["selected_folds"].clip(lower=1)
    grouped["pass_fold_rate"] = grouped["pass_folds"] / grouped["selected_folds"].clip(lower=1)
    grouped["net_to_drawdown"] = grouped["test_net_points"] / grouped["test_max_drawdown_points"].clip(lower=1.0)
    grouped["stable_candidate"] = (
        (grouped["selected_folds"] >= 3)
        & (grouped["positive_test_fold_rate"] >= 0.67)
        & (grouped["test_net_points"] > 0)
        & (grouped["avg_test_profit_factor"] >= 1.1)
        & (grouped["net_to_drawdown"] >= 1.0)
        & (grouped["min_test_net_points"] >= 0)
    )
    return grouped.sort_values(
        ["stable_candidate", "test_net_points", "positive_test_fold_rate", "avg_test_profit_factor"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def full_sample_summary(
    trade_cache: dict[str, tuple[TrendCandidate, pd.DataFrame]],
    aggregate: pd.DataFrame,
    limit: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in aggregate.head(limit).iterrows():
        candidate_name = str(row["candidate"])
        candidate, trades = trade_cache[candidate_name]
        summary = summarize_trades(trades)
        rows.append(
            {
                "candidate": candidate.name,
                "family": candidate.family,
                "timeframe_minutes": candidate.timeframe_minutes,
                "session": candidate.session,
                "holding_minutes": candidate.holding_minutes,
                "direction_filter": candidate.direction_filter,
                "exit_profile": candidate.exit_profile,
                **summary,
            }
        )
    return pd.DataFrame(rows)


def write_report(
    path: Path,
    features: pd.DataFrame,
    folds: pd.DataFrame,
    aggregate: pd.DataFrame,
    full_sample: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    positive = aggregate[aggregate["test_net_points"] > 0] if not aggregate.empty else pd.DataFrame()
    stable = aggregate[aggregate["stable_candidate"]] if "stable_candidate" in aggregate.columns else pd.DataFrame()
    lines = [
        "# NQ Short-Timeframe Trend System Search",
        "",
        "## Candidate Sources",
        "",
        "Industry-standard trend archetypes translated into mechanical rules: opening range breakout, Donchian/channel breakout, VWAP trend pullback, EMA trend/pullback, and ADX/DI trend following.",
        "",
        "## Data",
        "",
        f"- Source: `{_bar_zip_path()}`.",
        f"- Base 1m span: `{features['ts'].min()}` to `{features['ts'].max()}`.",
        f"- Base rows: `{len(features):,}`.",
        f"- Costs: `{BacktestCosts().round_trip_cost_points:.3f}` NQ points round trip.",
        "",
        "## Walk-Forward",
        "",
        f"- Timeframes: `{', '.join(str(value) + 'm' for value in args.timeframes)}`.",
        f"- Train/test: `{args.train_days}` train days, `{args.purge_days}` purge days, `{args.test_days}` test days, `{args.step_days}` step days.",
        f"- Sessions: `{', '.join(args.sessions)}`.",
        f"- Direction filters: `{', '.join(args.direction_filters)}`.",
        f"- Exit profiles: `{', '.join(args.exit_profiles)}`.",
        f"- Stable gate: selected folds >= 3, positive fold rate >= 67%, aggregate net > 0, avg PF >= 1.1, net/drawdown >= 1, and no negative selected OOS fold.",
        "",
        "## Verdict",
        "",
    ]
    if stable.empty:
        lines.append("No 1m/3m trend candidate passed the stable profitability gate.")
    else:
        best = stable.iloc[0]
        lines.append(
            "Best stable candidate: "
            f"`{best['candidate']}` with `{best['test_net_points']:.2f}` OOS net points, "
            f"`{best['positive_test_fold_rate']:.2%}` positive selected folds, "
            f"`{best['avg_test_profit_factor']:.3f}` avg OOS PF, and `{int(best['test_trades']):,}` OOS trades."
        )
    if not positive.empty:
        best_positive = positive.iloc[0]
        lines.append(
            f"Best positive research candidate: `{best_positive['candidate']}` "
            f"({best_positive['test_net_points']:.2f} OOS points, stable={bool(best_positive.get('stable_candidate', False))})."
        )
    lines.extend(
        [
            "",
            "## Top Aggregate Rows",
            "",
            _markdown_table(
                aggregate[
                    [
                        "stable_candidate",
                        "candidate",
                        "family",
                        "timeframe_minutes",
                        "session",
                        "holding_minutes",
                        "direction_filter",
                        "exit_profile",
                        "selected_folds",
                        "positive_test_fold_rate",
                        "test_trades",
                        "test_net_points",
                        "test_max_drawdown_points",
                        "net_to_drawdown",
                        "avg_test_profit_factor",
                        "min_test_net_points",
                    ]
                ].head(30)
                if not aggregate.empty
                else aggregate
            ),
            "",
            "## Full-Sample Check",
            "",
            _markdown_table(
                full_sample[
                    [
                        "candidate",
                        "family",
                        "timeframe_minutes",
                        "session",
                        "holding_minutes",
                        "direction_filter",
                        "exit_profile",
                        "trades",
                        "net_points",
                        "profit_factor",
                        "win_rate",
                        "max_drawdown_points",
                    ]
                ]
                if not full_sample.empty
                else full_sample
            ),
            "",
            "## Top Future Fold Rows",
            "",
            _markdown_table(
                folds.sort_values(["test_pass", "test_net_points"], ascending=[False, False])[
                    [
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
                ].head(30)
                if not folds.empty
                else folds
            ),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _markdown_table(frame: pd.DataFrame) -> str:
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


def parse_ema_pairs(values: list[str]) -> list[tuple[int, int]]:
    pairs = []
    for value in values:
        fast, slow = value.split(":", 1)
        pairs.append((int(fast), int(slow)))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description="Search NQ 1m/3m short-term trend systems.")
    parser.add_argument("--start-date", default="2021-04-28")
    parser.add_argument("--walk-start-date", default="2022-04-28")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-short-trend-base-cache.pkl")
    parser.add_argument("--output", default=".tmp/nq-short-trend-walkforward.csv")
    parser.add_argument("--aggregate-output", default=".tmp/nq-short-trend-aggregate.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-short-trend-trades.csv")
    parser.add_argument("--full-sample-output", default=".tmp/nq-short-trend-full-sample.csv")
    parser.add_argument("--report", default="reports/NQ-short-timeframe-trend-system-search.md")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--timeframes", type=int, nargs="+", default=[1, 3])
    parser.add_argument(
        "--families",
        nargs="+",
        default=[
            "donchian_breakout",
            "donchian_atr_breakout",
            "vwap_trend_pullback",
            "ema_trend",
            "ema_pullback",
            "adx_di_trend",
            "opening_range_breakout",
        ],
    )
    parser.add_argument("--sessions", nargs="+", default=["us_rth", "us_late", "europe"])
    parser.add_argument("--direction-filters", nargs="+", default=["long", "short", "both"])
    parser.add_argument("--lookbacks", type=int, nargs="+", default=[20, 30, 50, 60])
    parser.add_argument("--holding-minutes", type=int, nargs="+", default=[6, 15, 30, 60])
    parser.add_argument("--exit-profiles", nargs="+", default=["time", "sl8_tp12", "sl12_tp24"])
    parser.add_argument("--atr-thresholds", type=float, nargs="+", default=[0.0, 0.25, 0.5])
    parser.add_argument("--vwap-pullback-atr", type=float, nargs="+", default=[0.0, 0.25, 0.5])
    parser.add_argument("--ema-pairs", nargs="+", default=["9:21", "13:34", "21:55", "34:89"])
    parser.add_argument("--adx-periods", type=int, nargs="+", default=[14, 30])
    parser.add_argument("--adx-thresholds", type=float, nargs="+", default=[18, 22, 26])
    parser.add_argument("--opening-range-minutes", type=int, nargs="+", default=[15, 30, 60])
    parser.add_argument("--train-days", type=int, default=365)
    parser.add_argument("--purge-days", type=int, default=5)
    parser.add_argument("--test-days", type=int, default=90)
    parser.add_argument("--step-days", type=int, default=90)
    parser.add_argument("--min-train-trades", type=int, default=40)
    parser.add_argument("--min-test-trades", type=int, default=5)
    parser.add_argument("--min-train-profit-factor", type=float, default=1.03)
    parser.add_argument("--min-test-profit-factor", type=float, default=1.0)
    parser.add_argument("--max-train-drawdown-points", type=float, default=10_000.0)
    parser.add_argument("--max-test-drawdown-points", type=float, default=5_000.0)
    parser.add_argument("--max-fold-candidates", type=int, default=20)
    parser.add_argument("--full-sample-limit", type=int, default=30)
    args = parser.parse_args()
    args.ema_pairs = parse_ema_pairs(args.ema_pairs)

    base_features = load_continuous_nq_bars(args)
    frames_by_timeframe: dict[int, pd.DataFrame] = {}
    for timeframe in args.timeframes:
        print(f"preparing {timeframe}m features", flush=True)
        frames_by_timeframe[int(timeframe)] = add_trend_features(resample_ohlcv(base_features, int(timeframe)))

    candidates = candidate_pool(args)
    trade_cache = build_trade_cache(frames_by_timeframe, candidates, BacktestCosts())
    folds, trades = walk_forward(trade_cache, args)
    aggregate = aggregate_results(folds)
    full_sample = full_sample_summary(trade_cache, aggregate, args.full_sample_limit)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    folds.to_csv(args.output, index=False)
    aggregate.to_csv(args.aggregate_output, index=False)
    trades.to_csv(args.trades_output, index=False)
    full_sample.to_csv(args.full_sample_output, index=False)
    write_report(Path(args.report), base_features, folds, aggregate, full_sample, args)
    result = {
        "base_rows": int(len(base_features)),
        "base_start": str(base_features["ts"].min()),
        "base_end": str(base_features["ts"].max()),
        "candidates": int(len(candidates)),
        "fold_rows": int(len(folds)),
        "aggregate_rows": int(len(aggregate)),
        "stable_candidates": int(aggregate["stable_candidate"].sum()) if "stable_candidate" in aggregate.columns else 0,
        "positive_aggregate_rows": int((aggregate["test_net_points"] > 0).sum()) if not aggregate.empty else 0,
        "output": args.output,
        "aggregate_output": args.aggregate_output,
        "trades_output": args.trades_output,
        "full_sample_output": args.full_sample_output,
        "report": args.report,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
