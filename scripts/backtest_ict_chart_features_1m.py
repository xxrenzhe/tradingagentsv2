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

from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.dataflows.databento import _bar_zip_path


BULLISH = 1
BEARISH = -1
_FRAME_ARRAY_CACHE: dict[int, dict[str, Any]] = {}


@dataclass(frozen=True)
class ChartIctCandidate:
    signal: str
    family: str
    session: str
    hold_bars: int
    exit_profile: str
    stop_loss_points: float | None
    take_profit_points: float | None

    @property
    def name(self) -> str:
        return (
            f"chart_ict_{self.signal}_{self.session}"
            f"_hold{self.hold_bars}m_{self.exit_profile}"
        )


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    previous_close = close.shift(1)
    ranges = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def add_chart_ict_signals(
    bars: pd.DataFrame,
    *,
    pd_lookbacks: list[int],
    sweep_lookbacks: list[int],
    internal_lookbacks: list[int],
    displacement_lookbacks: list[int],
    tick_size: float = 0.25,
) -> pd.DataFrame:
    frame = bars.copy().reset_index(drop=True)
    open_price = pd.to_numeric(frame["Open"], errors="coerce")
    high = pd.to_numeric(frame["High"], errors="coerce")
    low = pd.to_numeric(frame["Low"], errors="coerce")
    close = pd.to_numeric(frame["Close"], errors="coerce")
    volume = pd.to_numeric(frame["Volume"], errors="coerce")

    true_range = _true_range(high, low, close)
    atr_30 = true_range.rolling(30, min_periods=10).mean()
    atr_120 = true_range.rolling(120, min_periods=30).mean()
    range_points = high - low
    body_points = (close - open_price).abs()
    body_share = body_points / range_points.replace(0, np.nan)
    volume_z = (volume - volume.rolling(60, min_periods=20).mean()) / volume.rolling(60, min_periods=20).std()

    signal_descriptions: dict[str, str] = {}
    pd_zones: dict[int, tuple[pd.Series, pd.Series, pd.Series, pd.Series]] = {}

    for lookback in pd_lookbacks:
        rolling_high = high.rolling(lookback, min_periods=lookback).max().shift(1)
        rolling_low = low.rolling(lookback, min_periods=lookback).min().shift(1)
        rolling_range = (rolling_high - rolling_low).replace(0, np.nan)
        premium = rolling_low + 0.95 * rolling_range
        discount = rolling_low + 0.05 * rolling_range
        in_premium = close >= premium
        in_discount = close <= discount
        pd_zones[lookback] = (in_premium, in_discount, premium, discount)

        fade_name = f"pd_fade_lb{lookback}"
        frame[fade_name] = np.select([in_discount, in_premium], [BULLISH, BEARISH], default=0).astype(np.int8)
        signal_descriptions[fade_name] = (
            "Textbook premium/discount fade: buy discount and sell premium."
        )

        continuation_name = f"pd_continue_lb{lookback}"
        frame[continuation_name] = np.select([in_premium, in_discount], [BULLISH, BEARISH], default=0).astype(np.int8)
        signal_descriptions[continuation_name] = (
            "Premium/discount continuation: follow persistent expansion at the extreme."
        )

    for pd_lookback in pd_lookbacks:
        in_premium, in_discount, _, _ = pd_zones[pd_lookback]
        for internal_lookback in internal_lookbacks:
            prior_internal_high = high.rolling(internal_lookback, min_periods=internal_lookback).max().shift(1)
            prior_internal_low = low.rolling(internal_lookback, min_periods=internal_lookback).min().shift(1)
            recent_discount = in_discount.rolling(5, min_periods=1).max().shift(1).fillna(False).astype(bool)
            recent_premium = in_premium.rolling(5, min_periods=1).max().shift(1).fillna(False).astype(bool)
            long_choch = recent_discount & (close > prior_internal_high)
            short_choch = recent_premium & (close < prior_internal_low)
            name = f"pd_choch_lb{pd_lookback}_ib{internal_lookback}"
            frame[name] = np.select([long_choch, short_choch], [BULLISH, BEARISH], default=0).astype(np.int8)
            signal_descriptions[name] = (
                "Confirmation entry: after discount/premium POI, wait for an internal CHoCH break."
            )

    for lookback in sweep_lookbacks:
        prior_high = high.rolling(lookback, min_periods=lookback).max().shift(1)
        prior_low = low.rolling(lookback, min_periods=lookback).min().shift(1)
        top_sweep = (high > prior_high + tick_size) & (close < prior_high)
        bottom_sweep = (low < prior_low - tick_size) & (close > prior_low)

        sweep_name = f"sweep_reclaim_lb{lookback}"
        frame[sweep_name] = np.select([bottom_sweep, top_sweep], [BULLISH, BEARISH], default=0).astype(np.int8)
        signal_descriptions[sweep_name] = (
            "Liquidity sweep and reclaim: fade a stop-run above/below the prior range."
        )

        for pd_lookback in pd_lookbacks:
            if pd_lookback != lookback and pd_lookback != max(pd_lookbacks):
                continue
            in_premium, in_discount, _, _ = pd_zones[pd_lookback]
            long_pd = bottom_sweep & in_discount
            short_pd = top_sweep & in_premium
            pd_name = f"sweep_pd_lb{lookback}_pd{pd_lookback}"
            frame[pd_name] = np.select([long_pd, short_pd], [BULLISH, BEARISH], default=0).astype(np.int8)
            signal_descriptions[pd_name] = (
                "Sweep only when it happens inside the matching discount or premium POI."
            )

        mss_signal = np.zeros(len(frame), dtype=np.int8)
        top_indexes = np.flatnonzero(top_sweep.to_numpy(dtype=bool))
        bottom_indexes = np.flatnonzero(bottom_sweep.to_numpy(dtype=bool))
        high_values = high.to_numpy(dtype=float)
        low_values = low.to_numpy(dtype=float)
        close_values = close.to_numpy(dtype=float)
        for offset in range(1, 4):
            top_targets = top_indexes + offset
            top_valid = top_targets < len(frame)
            top_targets = top_targets[top_valid]
            top_source = top_indexes[top_valid]
            top_confirmed = close_values[top_targets] < low_values[top_source]
            mss_signal[top_targets[top_confirmed]] = BEARISH

            bottom_targets = bottom_indexes + offset
            bottom_valid = bottom_targets < len(frame)
            bottom_targets = bottom_targets[bottom_valid]
            bottom_source = bottom_indexes[bottom_valid]
            bottom_confirmed = close_values[bottom_targets] > high_values[bottom_source]
            mss_signal[bottom_targets[bottom_confirmed]] = BULLISH

        mss_name = f"sweep_mss_lb{lookback}_c3"
        frame[mss_name] = mss_signal
        signal_descriptions[mss_name] = (
            "LQ-EM style entry: sweep first, then require a 3-bar MSS through the sweep candle."
        )

    for lookback in displacement_lookbacks:
        prior_high = high.rolling(lookback, min_periods=lookback).max().shift(1)
        prior_low = low.rolling(lookback, min_periods=lookback).min().shift(1)
        displacement = (range_points >= 1.2 * atr_30) & (body_share >= 0.55) & (volume_z.fillna(0) >= 0)
        long_bos = (close > prior_high) & displacement
        short_bos = (close < prior_low) & displacement
        name = f"displacement_bos_lb{lookback}"
        frame[name] = np.select([long_bos, short_bos], [BULLISH, BEARISH], default=0).astype(np.int8)
        signal_descriptions[name] = (
            "Strong body/range expansion that closes through a prior range high/low."
        )

        best_pd = max(pd_lookbacks)
        in_premium, in_discount, _, _ = pd_zones[best_pd]
        pd_continue_long = long_bos & in_premium
        pd_continue_short = short_bos & in_discount
        pd_name = f"pd_displacement_continue_lb{best_pd}_bos{lookback}"
        frame[pd_name] = np.select([pd_continue_long, pd_continue_short], [BULLISH, BEARISH], default=0).astype(np.int8)
        signal_descriptions[pd_name] = (
            "Screenshot-style stair-step continuation: P/D extreme plus displacement BOS."
        )

    bullish_fvg = (
        (low > high.shift(2))
        & (close.shift(1) > high.shift(2))
        & ((close.shift(1) - open_price.shift(1)) > 0)
        & (body_share.shift(1) >= 0.55)
        & (range_points.shift(1) >= 1.0 * atr_120.shift(1))
    )
    bearish_fvg = (
        (high < low.shift(2))
        & (close.shift(1) < low.shift(2))
        & ((close.shift(1) - open_price.shift(1)) < 0)
        & (body_share.shift(1) >= 0.55)
        & (range_points.shift(1) >= 1.0 * atr_120.shift(1))
    )
    frame["fvg_displacement_continue"] = np.select(
        [bullish_fvg, bearish_fvg],
        [BULLISH, BEARISH],
        default=0,
    ).astype(np.int8)
    signal_descriptions["fvg_displacement_continue"] = (
        "FVG/imbalance continuation after a strong displacement candle."
    )

    frame.attrs["signal_descriptions"] = signal_descriptions
    return frame


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
    raise ValueError(f"unknown session: {session}")


def frame_array_cache(frame: pd.DataFrame) -> dict[str, Any]:
    cache = _FRAME_ARRAY_CACHE.setdefault(id(frame), {})
    if not cache:
        cache["open"] = frame["Open"].to_numpy(dtype=float, copy=False)
        cache["high"] = frame["High"].to_numpy(dtype=float, copy=False)
        cache["low"] = frame["Low"].to_numpy(dtype=float, copy=False)
        cache["close"] = frame["Close"].to_numpy(dtype=float, copy=False)
        cache["timestamps"] = frame["ts"].to_numpy()
        cache["symbols_text"] = frame["symbol"].astype(str).to_numpy()
        cache["symbols_code"] = pd.factorize(frame["symbol"].astype(str), sort=False)[0]
        cache["minute_of_day"] = frame["minute_of_day"].to_numpy(dtype=np.int16, copy=False)
        cache["session_masks"] = {}
    return cache


def session_mask_array(frame: pd.DataFrame, session: str) -> np.ndarray:
    cache = frame_array_cache(frame)
    session_masks = cache["session_masks"]
    if session in session_masks:
        return session_masks[session]
    minute = cache["minute_of_day"]
    if session == "all":
        mask = np.ones(len(frame), dtype=bool)
    elif session == "europe":
        mask = (minute >= 7 * 60) & (minute < 13 * 60 + 30)
    elif session == "us_rth":
        mask = (minute >= 13 * 60 + 30) & (minute < 20 * 60)
    elif session == "us_late":
        mask = (minute >= 20 * 60) & (minute < 23 * 60)
    elif session == "ldn_ny":
        mask = (minute >= 7 * 60) & (minute < 20 * 60)
    else:
        raise ValueError(f"unknown session: {session}")
    session_masks[session] = mask
    return mask


def parse_exit_profile(profile: str) -> tuple[float | None, float | None]:
    if profile == "time":
        return None, None
    match = re.fullmatch(r"sl([0-9.]+)_tp([0-9.]+)", profile)
    if not match:
        raise ValueError(f"invalid exit profile: {profile}")
    return float(match.group(1)), float(match.group(2))


def candidate_pool(args: argparse.Namespace, signal_names: list[str], families: dict[str, str]) -> list[ChartIctCandidate]:
    candidates: list[ChartIctCandidate] = []
    for signal in signal_names:
        family = families.get(signal, signal.split("_lb", 1)[0])
        for session in args.sessions:
            for hold_bars in args.hold_bars:
                for profile in args.exit_profiles:
                    stop_loss, take_profit = parse_exit_profile(profile)
                    candidates.append(
                        ChartIctCandidate(
                            signal=signal,
                            family=family,
                            session=session,
                            hold_bars=int(hold_bars),
                            exit_profile=profile,
                            stop_loss_points=stop_loss,
                            take_profit_points=take_profit,
                        )
                    )
    return candidates


def build_trades(frame: pd.DataFrame, candidate: ChartIctCandidate, costs: BacktestCosts) -> pd.DataFrame:
    raw_signal = frame[candidate.signal].to_numpy(dtype=np.int8, copy=True)
    raw_signal[~session_mask_array(frame, candidate.session)] = 0
    previous_signal = np.empty_like(raw_signal)
    previous_signal[0] = 0
    previous_signal[1:] = raw_signal[:-1]
    signal_values = np.where(raw_signal != previous_signal, raw_signal, 0).astype(np.int8, copy=False)
    entry_indexes = np.flatnonzero(signal_values != 0)
    if len(entry_indexes) == 0:
        return pd.DataFrame()

    hold_bars = max(1, candidate.hold_bars)
    if candidate.stop_loss_points is None and candidate.take_profit_points is None:
        return build_time_exit_trades(frame, signal_values, candidate, costs, entry_indexes, hold_bars)

    cache = frame_array_cache(frame)
    open_prices = cache["open"]
    high_prices = cache["high"]
    low_prices = cache["low"]
    close_prices = cache["close"]
    timestamps = cache["timestamps"]
    symbols = cache["symbols_text"]
    symbol_codes = cache["symbols_code"]

    rows: list[dict[str, Any]] = []
    next_available_index = 0
    for signal_index in entry_indexes:
        entry_index = int(signal_index) + 1
        exit_index = int(signal_index) + hold_bars
        if entry_index < next_available_index or exit_index >= len(frame):
            continue
        if not np.all(symbol_codes[entry_index : exit_index + 1] == symbol_codes[signal_index]):
            continue
        direction = int(signal_values[signal_index])
        if direction == 0:
            continue

        entry_price = float(open_prices[entry_index])
        exit_price = float(close_prices[exit_index])
        realized_exit_index = exit_index
        exit_reason = "time"
        if not np.isfinite(entry_price) or not np.isfinite(exit_price):
            continue

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
                "family": candidate.family,
                "session": candidate.session,
                "holding_minutes": hold_bars,
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
    signal_values: np.ndarray,
    candidate: ChartIctCandidate,
    costs: BacktestCosts,
    entry_indexes: np.ndarray,
    hold_bars: int,
) -> pd.DataFrame:
    selected_signal_indexes = select_non_overlapping_signal_indexes(entry_indexes, len(frame), hold_bars)
    if len(selected_signal_indexes) == 0:
        return pd.DataFrame()

    signal_indexes = np.asarray(selected_signal_indexes, dtype=int)
    entry_price_indexes = signal_indexes + 1
    exit_indexes = signal_indexes + hold_bars
    cache = frame_array_cache(frame)
    symbols = cache["symbols_text"]
    symbol_codes = cache["symbols_code"]
    valid = (
        (entry_price_indexes < len(frame))
        & (exit_indexes < len(frame))
        & (symbol_codes[exit_indexes] == symbol_codes[signal_indexes])
        & (symbol_codes[entry_price_indexes] == symbol_codes[signal_indexes])
    )
    if not valid.any():
        return pd.DataFrame()

    signal_indexes = signal_indexes[valid]
    entry_price_indexes = entry_price_indexes[valid]
    exit_indexes = exit_indexes[valid]
    directions = signal_values[signal_indexes].astype(int, copy=False)
    entry_prices = cache["open"][entry_price_indexes]
    exit_prices = cache["close"][exit_indexes]
    finite = np.isfinite(entry_prices) & np.isfinite(exit_prices) & (directions != 0)
    if not finite.any():
        return pd.DataFrame()

    signal_indexes = signal_indexes[finite]
    exit_indexes = exit_indexes[finite]
    directions = directions[finite]
    entry_prices = entry_prices[finite]
    exit_prices = exit_prices[finite]
    gross_points = (exit_prices - entry_prices) * directions
    net_points = gross_points - costs.round_trip_cost_points
    timestamps = cache["timestamps"]
    return pd.DataFrame(
        {
            "candidate": candidate.name,
            "signal": candidate.signal,
            "family": candidate.family,
            "session": candidate.session,
            "holding_minutes": hold_bars,
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
    selected: list[int] = []
    next_available_index = 0
    for signal_index in entry_indexes:
        entry_index = int(signal_index) + 1
        exit_index = int(signal_index) + hold_bars
        if entry_index < next_available_index:
            continue
        selected.append(int(signal_index))
        next_available_index = exit_index + 1
    return np.asarray(selected, dtype=int)


def summarize_trades(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return empty_summary()
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    wins = net[net > 0].sum()
    losses = abs(net[net < 0].sum())
    reasons = trades["exit_reason"].astype(str)
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
    score = score_summary(
        {
            "trades": len(net),
            "net_points": float(equity.iloc[-1]),
            "max_drawdown_points": max_drawdown,
            "tail_loss_p05": tail_loss,
            "stability": stability,
        }
    )
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
        "stability": float(stability),
        "score": float(score),
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
        "stability": 0.0,
        "score": 0.0,
    }


def score_summary(summary: dict[str, Any]) -> float:
    net_points = float(summary.get("net_points", 0.0))
    max_drawdown = float(summary.get("max_drawdown_points", 0.0))
    tail_loss = abs(float(summary.get("tail_loss_p05", 0.0)))
    stability = max(0.0, float(summary.get("stability", 0.0)))
    trades = int(summary.get("trades", 0))
    risk = max(max_drawdown, tail_loss, 1.0)
    return float((net_points / risk) * sqrt(min(trades, 300) / 300) * (0.65 + 0.35 * stability))


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


def summarize_cached_trades(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[dict[str, Any], pd.DataFrame]:
    if trades.empty:
        return empty_summary(), trades
    selected = trades[(trades["entry_ts"] >= start) & (trades["entry_ts"] < end)].copy()
    if selected.empty:
        return empty_summary(), selected
    return summarize_trades(selected), selected


def build_trade_cache(
    features: pd.DataFrame,
    candidates: list[ChartIctCandidate],
    costs: BacktestCosts,
) -> dict[str, tuple[ChartIctCandidate, pd.DataFrame]]:
    cache: dict[str, tuple[ChartIctCandidate, pd.DataFrame]] = {}
    for index, candidate in enumerate(candidates, start=1):
        if index == 1 or index % 100 == 0 or index == len(candidates):
            print(f"building trades {index}/{len(candidates)}: {candidate.name}", flush=True)
        trades = build_trades(features, candidate, costs)
        if not trades.empty:
            trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
            trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
        cache[candidate.name] = (candidate, trades)
    return cache


def walk_forward(
    trade_cache: dict[str, tuple[ChartIctCandidate, pd.DataFrame]],
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
        ranked: list[tuple[float, dict[str, Any], ChartIctCandidate, pd.DataFrame]] = []
        for candidate, trades in trade_cache.values():
            train_summary, train_trades = summarize_cached_trades(trades, train_start, train_end)
            if train_passes(train_summary, args):
                ranked.append((float(train_summary["score"]), train_summary, candidate, train_trades))
        ranked.sort(reverse=True, key=lambda item: (item[0], item[1]["net_points"], item[1]["profit_factor"]))
        for rank, (_, train_summary, candidate, _) in enumerate(ranked[: args.max_fold_candidates], start=1):
            _, cached_trades = trade_cache[candidate.name]
            test_summary, test_trades = summarize_cached_trades(cached_trades, test_start, test_end)
            passed = test_passes(test_summary, args)
            row = {
                "fold": fold,
                "fold_rank": rank,
                "candidate": candidate.name,
                "signal": candidate.signal,
                "family": candidate.family,
                "session": candidate.session,
                "holding_minutes": candidate.hold_bars,
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
        family=("family", "first"),
        session=("session", "first"),
        holding_minutes=("holding_minutes", "first"),
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
        min_test_net_points=("test_net_points", "min"),
        train_net_points=("train_net_points", "sum"),
        avg_train_score=("train_score", "mean"),
    )
    grouped["positive_test_fold_rate"] = grouped["positive_test_folds"] / grouped["selected_folds"].clip(lower=1)
    grouped["pass_fold_rate"] = grouped["pass_folds"] / grouped["selected_folds"].clip(lower=1)
    grouped["net_to_drawdown"] = grouped["test_net_points"] / grouped["test_max_drawdown_points"].clip(lower=1.0)
    return grouped.sort_values(
        ["test_net_points", "positive_test_fold_rate", "avg_test_profit_factor"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def full_sample_summary(
    trade_cache: dict[str, tuple[ChartIctCandidate, pd.DataFrame]],
    aggregate: pd.DataFrame,
    limit: int,
) -> pd.DataFrame:
    if aggregate.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for _, row in aggregate.head(limit).iterrows():
        candidate_name = str(row["candidate"])
        candidate, trades = trade_cache[candidate_name]
        summary = summarize_trades(trades)
        rows.append(
            {
                "candidate": candidate.name,
                "signal": candidate.signal,
                "family": candidate.family,
                "session": candidate.session,
                "holding_minutes": candidate.hold_bars,
                "exit_profile": candidate.exit_profile,
                **summary,
            }
        )
    return pd.DataFrame(rows)


def family_map(signal_names: list[str]) -> dict[str, str]:
    families: dict[str, str] = {}
    for name in signal_names:
        if name.startswith("pd_fade"):
            families[name] = "premium_discount_fade"
        elif name.startswith("pd_continue"):
            families[name] = "premium_discount_continuation"
        elif name.startswith("pd_choch"):
            families[name] = "pd_choch_confirmation"
        elif name.startswith("sweep_pd"):
            families[name] = "sweep_at_pd_poi"
        elif name.startswith("sweep_mss"):
            families[name] = "sweep_then_mss"
        elif name.startswith("sweep_reclaim"):
            families[name] = "liquidity_sweep_reclaim"
        elif name.startswith("pd_displacement"):
            families[name] = "pd_displacement_continuation"
        elif name.startswith("displacement_bos"):
            families[name] = "displacement_bos"
        elif name.startswith("fvg"):
            families[name] = "fvg_displacement"
        else:
            families[name] = name
    return families


def write_report(
    path: Path,
    features: pd.DataFrame,
    folds: pd.DataFrame,
    aggregate: pd.DataFrame,
    full_sample: pd.DataFrame,
    signal_descriptions: dict[str, str],
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    positive = aggregate[aggregate["test_net_points"] > 0] if not aggregate.empty else pd.DataFrame()
    lines = [
        "# NQ 1m ICT Chart Feature Backtest",
        "",
        "## Research Read",
        "",
        "The screenshots point to three repeatable trade shapes: stair-step continuation after displacement, liquidity sweep/reclaim into a reversal leg, and confirmed entries after premium/discount POIs. `docs/Strategy/ICT2022-2.md` frames those as structure, POI, liquidity sweep, and CHoCH/MSS confirmation. `docs/Strategy/lightglow.md` supplies the measurable SMC parts: internal/swing structure, FVGs, equal highs/lows, order blocks, and premium/discount zones.",
        "",
        "## Data",
        "",
        f"- Source: `{_bar_zip_path()}`.",
        f"- Loaded continuous NQ 1m span: `{features['ts'].min()}` to `{features['ts'].max()}`.",
        f"- Rows: `{len(features):,}`; symbols selected: `{features['symbol'].nunique()}`.",
        f"- Costs: `{BacktestCosts().round_trip_cost_points:.3f}` NQ points round trip.",
        "",
        "## Feature Families Tested",
        "",
    ]
    for signal, description in sorted(signal_descriptions.items()):
        lines.append(f"- `{signal}`: {description}")
    lines.extend(
        [
            "",
            "## Walk-Forward Design",
            "",
            f"- Train/test: `{args.train_days}` train days, `{args.purge_days}` purge days, `{args.test_days}` test days, `{args.step_days}` step days.",
            f"- Sessions: `{', '.join(args.sessions)}`.",
            f"- Holds: `{', '.join(str(value) for value in args.hold_bars)}` minutes.",
            f"- Exit profiles: `{', '.join(args.exit_profiles)}`.",
            f"- Train gate: trades >= `{args.min_train_trades}`, PF >= `{args.min_train_profit_factor}`, net > 0.",
            f"- Test gate: trades >= `{args.min_test_trades}`, PF >= `{args.min_test_profit_factor}`, net > 0.",
            "",
            "## Verdict",
            "",
        ]
    )
    if positive.empty:
        lines.append("No train-selected chart/ICT feature candidate produced positive aggregate future test net points.")
    else:
        best = positive.iloc[0]
        lines.append(
            "Best positive aggregate candidate: "
            f"`{best['candidate']}` with `{best['test_net_points']:.2f}` future test net points, "
            f"`{best['positive_test_fold_rate']:.2%}` positive selected folds, "
            f"`{best['avg_test_profit_factor']:.3f}` average test PF, and "
            f"`{int(best['test_trades']):,}` test trades."
        )
    lines.extend(
        [
            "",
            "## Aggregate Ranking",
            "",
            _markdown_table(
                aggregate[
                    [
                        "candidate",
                        "family",
                        "session",
                        "holding_minutes",
                        "exit_profile",
                        "selected_folds",
                        "positive_test_fold_rate",
                        "test_trades",
                        "test_net_points",
                        "test_max_drawdown_points",
                        "net_to_drawdown",
                        "avg_test_profit_factor",
                        "avg_test_win_rate",
                        "min_test_net_points",
                    ]
                ].head(25)
                if not aggregate.empty
                else aggregate
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
                ].head(25)
                if not folds.empty
                else folds
            ),
            "",
            "## Full-Sample Sanity Check",
            "",
            _markdown_table(
                full_sample[
                    [
                        "candidate",
                        "family",
                        "session",
                        "holding_minutes",
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
            "## Interpretation",
            "",
            "- Treat the result as a feature validation pass, not a live-trading approval. The strongest candidates still need roll-aware execution checks and paper-trading validation.",
            "- Any result led by very short holding periods is sensitive to slippage assumptions. Re-run with wider costs before promotion.",
            "- Sweep/MSS and CHoCH candidates with sparse selections are useful as filters even when they are weaker standalone entry systems.",
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest screenshot-derived ICT/lightglow chart features on NQ 1m bars.")
    parser.add_argument("--start-date", default="2021-04-28")
    parser.add_argument("--walk-start-date", default="2022-04-28")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-chart-ict-1m-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/nq-chart-ict-1m-walkforward.csv")
    parser.add_argument("--aggregate-output", default=".tmp/nq-chart-ict-1m-aggregate.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-chart-ict-1m-trades.csv")
    parser.add_argument("--full-sample-output", default=".tmp/nq-chart-ict-1m-full-sample.csv")
    parser.add_argument("--report", default="reports/NQ-chart-ict-lightglow-feature-backtest.md")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--pd-lookbacks", type=int, nargs="+", default=[50, 100])
    parser.add_argument("--sweep-lookbacks", type=int, nargs="+", default=[20, 50, 100])
    parser.add_argument("--internal-lookbacks", type=int, nargs="+", default=[10, 20])
    parser.add_argument("--displacement-lookbacks", type=int, nargs="+", default=[20, 50])
    parser.add_argument("--sessions", nargs="+", default=["all", "ldn_ny", "europe", "us_rth", "us_late"])
    parser.add_argument("--signals", nargs="+", default=None)
    parser.add_argument("--hold-bars", type=int, nargs="+", default=[2, 3, 5])
    parser.add_argument("--exit-profiles", nargs="+", default=["time", "sl8_tp12", "sl8_tp16", "sl12_tp24"])
    parser.add_argument("--train-days", type=int, default=365)
    parser.add_argument("--purge-days", type=int, default=5)
    parser.add_argument("--test-days", type=int, default=90)
    parser.add_argument("--step-days", type=int, default=90)
    parser.add_argument("--min-train-trades", type=int, default=40)
    parser.add_argument("--min-test-trades", type=int, default=5)
    parser.add_argument("--min-train-profit-factor", type=float, default=1.03)
    parser.add_argument("--min-test-profit-factor", type=float, default=1.0)
    parser.add_argument("--max-fold-candidates", type=int, default=15)
    parser.add_argument("--full-sample-limit", type=int, default=20)
    args = parser.parse_args()

    features = load_continuous_nq_bars(args)
    features = add_chart_ict_signals(
        features,
        pd_lookbacks=args.pd_lookbacks,
        sweep_lookbacks=args.sweep_lookbacks,
        internal_lookbacks=args.internal_lookbacks,
        displacement_lookbacks=args.displacement_lookbacks,
    )
    signal_descriptions = dict(features.attrs.get("signal_descriptions", {}))
    signal_names = list(signal_descriptions)
    if args.signals:
        requested = set(args.signals)
        unknown = sorted(requested - set(signal_names))
        if unknown:
            raise SystemExit(f"Unknown signal(s): {', '.join(unknown)}")
        signal_names = [name for name in signal_names if name in requested]
        signal_descriptions = {name: signal_descriptions[name] for name in signal_names}
    candidates = candidate_pool(args, signal_names, family_map(signal_names))
    trade_cache = build_trade_cache(features, candidates, BacktestCosts())
    folds, trades = walk_forward(trade_cache, args)
    aggregate = aggregate_results(folds)
    full_sample = full_sample_summary(trade_cache, aggregate, args.full_sample_limit)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    folds.to_csv(args.output, index=False)
    aggregate.to_csv(args.aggregate_output, index=False)
    trades.to_csv(args.trades_output, index=False)
    full_sample.to_csv(args.full_sample_output, index=False)
    write_report(Path(args.report), features, folds, aggregate, full_sample, signal_descriptions, args)

    result = {
        "feature_rows": int(len(features)),
        "feature_start": str(features["ts"].min()),
        "feature_end": str(features["ts"].max()),
        "signals": len(signal_names),
        "candidates": len(candidates),
        "fold_rows": int(len(folds)),
        "aggregate_rows": int(len(aggregate)),
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
