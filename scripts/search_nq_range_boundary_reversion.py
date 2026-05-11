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


@dataclass(frozen=True)
class BoundaryCandidate:
    lookback: int
    width_atr_max: float
    efficiency_max: float
    boundary_band: float
    reclaim_strength: float
    session: str
    direction_filter: str
    stop_lookback: int
    target_mode: str
    reward_risk: float
    horizon_minutes: int

    @property
    def name(self) -> str:
        return (
            f"range_boundary_lb{self.lookback}_w{self.width_atr_max:g}_eff{self.efficiency_max:g}"
            f"_band{self.boundary_band:g}_reclaim{self.reclaim_strength:g}_{self.session}_{self.direction_filter}"
            f"_sl{self.stop_lookback}_{self.target_mode}_rr{self.reward_risk:g}_h{self.horizon_minutes}"
        )


def prepare_features(base: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    frame = base[["ts", "symbol", "Open", "High", "Low", "Close", "Volume"]].copy()
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
    previous_close = close.shift(1)
    true_range = pd.concat([high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1).max(axis=1)
    frame["atr_30"] = true_range.rolling(30, min_periods=10).mean()
    frame["atr_120"] = true_range.rolling(120, min_periods=30).mean()
    frame["range_points"] = high - low
    frame["body_points"] = (close - open_price).abs()
    frame["body_share"] = frame["body_points"] / frame["range_points"].replace(0, np.nan)
    frame["upper_wick"] = high - pd.concat([open_price, close], axis=1).max(axis=1)
    frame["lower_wick"] = pd.concat([open_price, close], axis=1).min(axis=1) - low
    for lookback in sorted(set(args.lookbacks)):
        range_high = high.rolling(lookback, min_periods=lookback).max().shift(1)
        range_low = low.rolling(lookback, min_periods=lookback).min().shift(1)
        width = range_high - range_low
        tr_sum = true_range.rolling(lookback, min_periods=lookback).sum().shift(1)
        net_move = (close.shift(1) - close.shift(lookback + 1)).abs()
        frame[f"range_high_{lookback}"] = range_high
        frame[f"range_low_{lookback}"] = range_low
        frame[f"range_mid_{lookback}"] = (range_high + range_low) / 2.0
        frame[f"range_width_{lookback}"] = width
        frame[f"range_width_atr_{lookback}"] = width / frame["atr_120"].replace(0, np.nan)
        frame[f"range_efficiency_{lookback}"] = net_move / tr_sum.replace(0, np.nan)
    for stop_lookback in sorted(set(args.stop_lookbacks)):
        frame[f"prior_low_{stop_lookback}"] = low.rolling(stop_lookback, min_periods=1).min().shift(1)
        frame[f"prior_high_{stop_lookback}"] = high.rolling(stop_lookback, min_periods=1).max().shift(1)
    return frame.dropna(subset=["Open", "High", "Low", "Close"]).reset_index(drop=True)


def candidate_pool(args: argparse.Namespace) -> list[BoundaryCandidate]:
    return [
        BoundaryCandidate(
            lookback=int(lookback),
            width_atr_max=float(width),
            efficiency_max=float(efficiency),
            boundary_band=float(boundary_band),
            reclaim_strength=float(reclaim),
            session=session,
            direction_filter=direction,
            stop_lookback=int(stop_lookback),
            target_mode=target_mode,
            reward_risk=float(reward_risk),
            horizon_minutes=int(horizon),
        )
        for lookback in args.lookbacks
        for width in args.width_atr_max
        for efficiency in args.efficiency_max
        for boundary_band in args.boundary_bands
        for reclaim in args.reclaim_strengths
        for session in args.sessions
        for direction in args.direction_filters
        for stop_lookback in args.stop_lookbacks
        for target_mode in args.target_modes
        for reward_risk in args.reward_risks
        for horizon in args.horizon_minutes
    ]


def session_array(minutes: np.ndarray, session: str) -> np.ndarray:
    if session == "all":
        return np.ones(len(minutes), dtype=bool)
    if session == "europe":
        return (minutes >= 7 * 60) & (minutes < 13 * 60 + 30)
    if session == "us_rth":
        return (minutes >= 13 * 60 + 30) & (minutes < 20 * 60)
    if session == "us_late":
        return (minutes >= 20 * 60) & (minutes < 23 * 60)
    if session == "ldn_ny":
        return (minutes >= 7 * 60) & (minutes < 20 * 60)
    if session == "asia":
        return (minutes < 7 * 60) | (minutes >= 23 * 60)
    raise ValueError(f"unknown session: {session}")


def build_boundary_events(frame: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    high = frame["High"].to_numpy(dtype=float)
    low = frame["Low"].to_numpy(dtype=float)
    close = frame["Close"].to_numpy(dtype=float)
    open_price = frame["Open"].to_numpy(dtype=float)
    lower_wick = frame["lower_wick"].to_numpy(dtype=float)
    upper_wick = frame["upper_wick"].to_numpy(dtype=float)
    body_points = frame["body_points"].to_numpy(dtype=float)
    minute = frame["minute_of_day"].to_numpy(dtype=np.int16)
    symbols = frame["symbol"].astype(str).to_numpy()
    max_horizon = max(args.horizon_minutes)
    rows: list[pd.DataFrame] = []
    for lookback in sorted(set(args.lookbacks)):
        range_high = frame[f"range_high_{lookback}"].to_numpy(dtype=float)
        range_low = frame[f"range_low_{lookback}"].to_numpy(dtype=float)
        range_mid = frame[f"range_mid_{lookback}"].to_numpy(dtype=float)
        width = frame[f"range_width_{lookback}"].to_numpy(dtype=float)
        width_atr = frame[f"range_width_atr_{lookback}"].to_numpy(dtype=float)
        efficiency = frame[f"range_efficiency_{lookback}"].to_numpy(dtype=float)
        max_width = max(args.width_atr_max)
        max_eff = max(args.efficiency_max)
        max_band = max(args.boundary_bands)
        min_reclaim = min(args.reclaim_strengths)
        band = width * max_band
        compression = (
            np.isfinite(width_atr)
            & np.isfinite(efficiency)
            & (width_atr <= max_width)
            & (efficiency <= max_eff)
            & (width >= args.min_range_points)
        )
        long_reclaim_amount = (close - range_low) / np.where(width > 0, width, np.nan)
        short_reclaim_amount = (range_high - close) / np.where(width > 0, width, np.nan)
        long_signal = (
            compression
            & (low <= range_low + band)
            & (close > range_low)
            & (close > open_price)
            & (long_reclaim_amount >= min_reclaim)
            & (lower_wick >= args.min_wick_body_mult * np.maximum(body_points, 0.25))
        )
        short_signal = (
            compression
            & (high >= range_high - band)
            & (close < range_high)
            & (close < open_price)
            & (short_reclaim_amount >= min_reclaim)
            & (upper_wick >= args.min_wick_body_mult * np.maximum(body_points, 0.25))
        )
        direction = np.zeros(len(frame), dtype=np.int8)
        direction[long_signal] = 1
        direction[short_signal] = -1
        indexes = np.flatnonzero(direction != 0)
        indexes = indexes[indexes + max_horizon < len(frame)]
        if len(indexes) == 0:
            continue
        rows.append(
            pd.DataFrame(
                {
                    "event_index": indexes,
                    "entry_index": indexes + 1,
                    "lookback": lookback,
                    "direction": direction[indexes],
                    "entry_ts": frame["ts"].to_numpy()[indexes],
                    "symbol": symbols[indexes],
                    "minute_of_day": minute[indexes],
                    "range_high": range_high[indexes],
                    "range_low": range_low[indexes],
                    "range_mid": range_mid[indexes],
                    "range_width": width[indexes],
                    "range_width_atr": width_atr[indexes],
                    "range_efficiency": efficiency[indexes],
                    "reclaim_amount": np.where(direction[indexes] > 0, long_reclaim_amount[indexes], short_reclaim_amount[indexes]),
                    "event_high": high[indexes],
                    "event_low": low[indexes],
                    "event_close": close[indexes],
                }
            )
        )
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True, sort=False).sort_values(["event_index", "lookback"]).reset_index(drop=True)


def compute_outcomes(
    frame: pd.DataFrame,
    events: pd.DataFrame,
    *,
    stop_lookback: int,
    target_mode: str,
    reward_risk: float,
    horizon: int,
    args: argparse.Namespace,
    costs: BacktestCosts,
) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    open_prices = frame["Open"].to_numpy(dtype=float)
    high_prices = frame["High"].to_numpy(dtype=float)
    low_prices = frame["Low"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    timestamps = frame["ts"].to_numpy()
    symbol_codes = pd.factorize(frame["symbol"].astype(str), sort=False)[0]
    prior_low = frame[f"prior_low_{stop_lookback}"].to_numpy(dtype=float)
    prior_high = frame[f"prior_high_{stop_lookback}"].to_numpy(dtype=float)
    event_indexes = events["event_index"].to_numpy(dtype=int)
    entry_indexes = events["entry_index"].to_numpy(dtype=int)
    timeout_indexes = event_indexes + int(horizon)
    directions = events["direction"].to_numpy(dtype=np.int8)
    entry_prices = open_prices[entry_indexes]
    buffer_points = args.stop_buffer_points
    stop_prices = np.where(directions > 0, prior_low[event_indexes] - buffer_points, prior_high[event_indexes] + buffer_points)
    stop_distances = np.where(directions > 0, entry_prices - stop_prices, stop_prices - entry_prices)
    if target_mode == "fixed_r":
        target_distances = stop_distances * float(reward_risk)
        target_prices = np.where(directions > 0, entry_prices + target_distances, entry_prices - target_distances)
    elif target_mode == "mid":
        target_prices = events["range_mid"].to_numpy(dtype=float)
        target_distances = np.abs(target_prices - entry_prices)
    elif target_mode == "opposite_edge":
        target_prices = np.where(directions > 0, events["range_high"].to_numpy(dtype=float), events["range_low"].to_numpy(dtype=float))
        target_distances = np.abs(target_prices - entry_prices)
    else:
        raise ValueError(f"unknown target mode: {target_mode}")
    valid = (
        np.isfinite(entry_prices)
        & np.isfinite(stop_distances)
        & np.isfinite(target_distances)
        & (stop_distances >= args.min_stop_points)
        & (stop_distances <= args.max_stop_points)
        & (target_distances >= args.min_target_points)
        & (timeout_indexes < len(frame))
    )
    if not valid.any():
        return pd.DataFrame()
    events = events.loc[valid].reset_index(drop=True)
    event_indexes = event_indexes[valid]
    entry_indexes = entry_indexes[valid]
    timeout_indexes = timeout_indexes[valid]
    directions = directions[valid]
    entry_prices = entry_prices[valid]
    stop_prices = stop_prices[valid]
    stop_distances = stop_distances[valid]
    target_prices = target_prices[valid]
    target_distances = target_distances[valid]

    offsets = np.arange(1, horizon + 1, dtype=int)
    realized_exit_indexes = np.empty(len(events), dtype=int)
    exit_prices = np.empty(len(events), dtype=float)
    reason_codes = np.empty(len(events), dtype=np.int8)
    chunk_size = 50_000
    for start in range(0, len(events), chunk_size):
        stop = min(start + chunk_size, len(events))
        chunk_events = event_indexes[start:stop]
        chunk_directions = directions[start:stop]
        window_indexes = chunk_events[:, None] + offsets[None, :]
        long_mask = chunk_directions > 0
        stop_hits = np.where(
            long_mask[:, None],
            low_prices[window_indexes] <= stop_prices[start:stop, None],
            high_prices[window_indexes] >= stop_prices[start:stop, None],
        )
        target_hits = np.where(
            long_mask[:, None],
            high_prices[window_indexes] >= target_prices[start:stop, None],
            low_prices[window_indexes] <= target_prices[start:stop, None],
        )
        symbol_valid = symbol_codes[window_indexes] == symbol_codes[chunk_events, None]
        first_invalid = np.where((~symbol_valid).any(axis=1), (~symbol_valid).argmax(axis=1), horizon + 1)
        first_stop = np.where(stop_hits.any(axis=1), stop_hits.argmax(axis=1), horizon + 1)
        first_target = np.where(target_hits.any(axis=1), target_hits.argmax(axis=1), horizon + 1)
        stop_first = first_stop <= first_target
        bracket_hit = (first_stop <= horizon) | (first_target <= horizon)
        exit_offsets = np.where(bracket_hit, np.minimum(first_stop, first_target) + 1, horizon)
        invalid_before_exit = first_invalid < exit_offsets
        chunk_exit_indexes = np.where(bracket_hit, chunk_events + exit_offsets, timeout_indexes[start:stop])
        chunk_exit_prices = close_prices[timeout_indexes[start:stop]]
        stop_rows = bracket_hit & stop_first
        target_rows = bracket_hit & ~stop_first
        chunk_exit_prices = np.where(stop_rows, stop_prices[start:stop], chunk_exit_prices)
        chunk_exit_prices = np.where(target_rows, target_prices[start:stop], chunk_exit_prices)
        chunk_reasons = np.zeros(stop - start, dtype=np.int8)
        chunk_reasons = np.where(stop_rows, 1, chunk_reasons)
        chunk_reasons = np.where(target_rows, 2, chunk_reasons)
        chunk_reasons = np.where(invalid_before_exit, -1, chunk_reasons)
        realized_exit_indexes[start:stop] = chunk_exit_indexes
        exit_prices[start:stop] = chunk_exit_prices
        reason_codes[start:stop] = chunk_reasons
    valid_path = reason_codes >= 0
    if not valid_path.any():
        return pd.DataFrame()
    events = events.loc[valid_path].reset_index(drop=True)
    event_indexes = event_indexes[valid_path]
    entry_indexes = entry_indexes[valid_path]
    directions = directions[valid_path]
    entry_prices = entry_prices[valid_path]
    stop_distances = stop_distances[valid_path]
    target_distances = target_distances[valid_path]
    realized_exit_indexes = realized_exit_indexes[valid_path]
    exit_prices = exit_prices[valid_path]
    reason_codes = reason_codes[valid_path]
    gross_points = (exit_prices - entry_prices) * directions
    net_points = gross_points - costs.round_trip_cost_points
    risk_points = stop_distances + costs.round_trip_cost_points
    out = events.copy()
    out["entry_ts"] = pd.to_datetime(timestamps[event_indexes], utc=True)
    out["exit_ts"] = pd.to_datetime(timestamps[realized_exit_indexes], utc=True)
    out["entry_index"] = entry_indexes
    out["exit_index"] = realized_exit_indexes
    out["stop_lookback"] = int(stop_lookback)
    out["target_mode"] = target_mode
    out["reward_risk"] = float(reward_risk)
    out["horizon_minutes"] = int(horizon)
    out["entry_price"] = entry_prices
    out["exit_price"] = exit_prices
    out["exit_reason"] = np.asarray(["timeout", "stop_loss", "take_profit"], dtype=object)[reason_codes]
    out["stop_distance_points"] = stop_distances
    out["target_distance_points"] = target_distances
    out["gross_points"] = gross_points
    out["net_points"] = net_points
    out["net_dollars"] = net_points * costs.point_value
    out["r_multiple"] = net_points / risk_points
    return out


def select_candidate_trades(outcomes: pd.DataFrame, candidate: BoundaryCandidate) -> pd.DataFrame:
    if outcomes.empty:
        return outcomes
    mask = (
        outcomes["lookback"].eq(candidate.lookback)
        & (outcomes["range_width_atr"] <= candidate.width_atr_max)
        & (outcomes["range_efficiency"] <= candidate.efficiency_max)
        & (outcomes["reclaim_amount"] >= candidate.reclaim_strength)
    )
    width = pd.to_numeric(outcomes["range_width"], errors="coerce")
    if candidate.direction_filter == "long":
        mask &= outcomes["direction"].eq(1)
    elif candidate.direction_filter == "short":
        mask &= outcomes["direction"].eq(-1)
    elif candidate.direction_filter != "both":
        raise ValueError(f"unknown direction filter: {candidate.direction_filter}")
    mask &= session_array(outcomes["minute_of_day"].to_numpy(dtype=np.int16), candidate.session)
    selected = outcomes.loc[mask].copy()
    if selected.empty:
        return selected
    boundary_distance = np.where(
        selected["direction"].to_numpy(dtype=np.int8) > 0,
        (selected["event_close"] - selected["range_low"]) / width.loc[selected.index].replace(0, np.nan),
        (selected["range_high"] - selected["event_close"]) / width.loc[selected.index].replace(0, np.nan),
    )
    selected = selected[boundary_distance <= candidate.boundary_band].sort_values("event_index").copy()
    if selected.empty:
        return selected
    positions: list[int] = []
    next_available = 0
    event_indexes = selected["event_index"].to_numpy(dtype=int)
    exit_indexes = selected["exit_index"].to_numpy(dtype=int)
    for position, event_index in enumerate(event_indexes):
        if int(event_index) + 1 < next_available:
            continue
        positions.append(position)
        next_available = int(exit_indexes[position]) + 1
    result = selected.iloc[positions].copy()
    result["candidate"] = candidate.name
    return result


def summarize_trades(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return empty_summary()
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    wins = net[net > 0]
    losses = net[net < 0]
    gross_profit = float(wins.sum())
    gross_loss = float((-losses).sum())
    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss = float((-losses).mean()) if not losses.empty else 0.0
    win_rate = float((net > 0).mean())
    expectancy = float(win_rate * avg_win - (1.0 - win_rate) * avg_loss)
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    reasons = trades["exit_reason"].astype(str)
    entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)
    split = entry_ts.median()
    first = net[entry_ts <= split]
    second = net[entry_ts > split]
    first_points = float(first.sum()) if not first.empty else 0.0
    second_points = float(second.sum()) if not second.empty else 0.0
    if first_points > 0 and second_points > 0:
        stability = min(first_points, second_points) / max(first_points, second_points)
    elif first_points + second_points > 0:
        stability = 0.25
    else:
        stability = 0.0
    max_dd = float(drawdown.max()) if not drawdown.empty else 0.0
    return {
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "net_dollars": float(net.sum() * BacktestCosts().point_value),
        "max_drawdown_points": max_dd,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else (999.0 if gross_profit > 0 else 0.0),
        "win_rate": win_rate,
        "avg_win_points": avg_win,
        "avg_loss_points": avg_loss,
        "payoff_ratio": float(avg_win / avg_loss) if avg_loss else (999.0 if avg_win > 0 else 0.0),
        "expectancy_points": expectancy,
        "avg_r_multiple": float(pd.to_numeric(trades["r_multiple"], errors="coerce").mean()),
        "target_exit_share": float((reasons == "take_profit").mean()),
        "stop_exit_share": float((reasons == "stop_loss").mean()),
        "timeout_exit_share": float((reasons == "timeout").mean()),
        "first_half_points": first_points,
        "second_half_points": second_points,
        "stability": float(stability),
        "score": score_summary(float(net.sum()), max_dd, int(len(trades)), expectancy, float(stability)),
    }


def empty_summary() -> dict[str, Any]:
    return {
        "trades": 0,
        "net_points": 0.0,
        "net_dollars": 0.0,
        "max_drawdown_points": 0.0,
        "profit_factor": 0.0,
        "win_rate": 0.0,
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


def score_summary(net_points: float, max_drawdown: float, trades: int, expectancy: float, stability: float) -> float:
    risk = max(max_drawdown, 1.0)
    evidence = sqrt(min(max(trades, 0), 500) / 500)
    return float((net_points / risk) * evidence * (0.70 + 0.30 * max(stability, 0.0)) * max(0.25, 1.0 + expectancy / 10.0))


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


def evaluate_candidates(
    outcome_cache: dict[tuple[int, str, float, int], pd.DataFrame],
    candidates: list[BoundaryCandidate],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    candidate_trades: dict[str, pd.DataFrame] = {}
    for index, candidate in enumerate(candidates, start=1):
        if index == 1 or index % 100 == 0 or index == len(candidates):
            print(f"selecting candidate {index}/{len(candidates)}: {candidate.name}", flush=True)
        outcomes = outcome_cache[
            (int(candidate.stop_lookback), str(candidate.target_mode), float(candidate.reward_risk), int(candidate.horizon_minutes))
        ]
        trades = select_candidate_trades(outcomes, candidate)
        if not trades.empty:
            trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
            trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
        candidate_trades[candidate.name] = trades

    fold_rows: list[dict[str, Any]] = []
    oos_trade_rows: list[pd.DataFrame] = []
    end = pd.Timestamp(args.end_date, tz="UTC")
    test_start = pd.Timestamp(args.walk_start_date, tz="UTC")
    fold = 0
    while test_start + pd.Timedelta(days=args.test_days) <= end:
        train_start = test_start - pd.Timedelta(days=args.train_days + args.purge_days)
        train_end = test_start - pd.Timedelta(days=args.purge_days)
        test_end = test_start + pd.Timedelta(days=args.test_days)
        ranked: list[tuple[float, dict[str, Any], BoundaryCandidate]] = []
        for candidate in candidates:
            train_summary, _ = summarize_window(candidate_trades[candidate.name], train_start, train_end)
            if train_passes(train_summary, args):
                ranked.append((float(train_summary["score"]), train_summary, candidate))
        ranked.sort(reverse=True, key=lambda item: (item[0], item[1]["expectancy_points"], item[1]["profit_factor"]))
        for rank, (_, train_summary, candidate) in enumerate(ranked[: args.max_fold_candidates], start=1):
            test_summary, test_trades = summarize_window(candidate_trades[candidate.name], test_start, test_end)
            passed = test_passes(test_summary, args)
            fold_rows.append(
                {
                    "fold": fold,
                    "fold_rank": rank,
                    "candidate": candidate.name,
                    "lookback": candidate.lookback,
                    "width_atr_max": candidate.width_atr_max,
                    "efficiency_max": candidate.efficiency_max,
                    "boundary_band": candidate.boundary_band,
                    "reclaim_strength": candidate.reclaim_strength,
                    "session": candidate.session,
                    "direction_filter": candidate.direction_filter,
                    "stop_lookback": candidate.stop_lookback,
                    "target_mode": candidate.target_mode,
                    "reward_risk": candidate.reward_risk,
                    "horizon_minutes": candidate.horizon_minutes,
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
                oos_trade_rows.append(exported)
        fold += 1
        test_start += pd.Timedelta(days=args.step_days)
    folds = pd.DataFrame(fold_rows)
    oos_trades = pd.concat(oos_trade_rows, ignore_index=True, sort=False) if oos_trade_rows else pd.DataFrame()
    return folds, oos_trades, candidate_trades


def aggregate_results(folds: pd.DataFrame) -> pd.DataFrame:
    if folds.empty:
        return pd.DataFrame()
    grouped = folds.groupby("candidate", as_index=False).agg(
        lookback=("lookback", "first"),
        width_atr_max=("width_atr_max", "first"),
        efficiency_max=("efficiency_max", "first"),
        boundary_band=("boundary_band", "first"),
        reclaim_strength=("reclaim_strength", "first"),
        session=("session", "first"),
        direction_filter=("direction_filter", "first"),
        stop_lookback=("stop_lookback", "first"),
        target_mode=("target_mode", "first"),
        reward_risk=("reward_risk", "first"),
        horizon_minutes=("horizon_minutes", "first"),
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


def full_sample_summary(candidate_trades: dict[str, pd.DataFrame], aggregate: pd.DataFrame, limit: int) -> pd.DataFrame:
    if aggregate.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for _, row in aggregate.head(limit).iterrows():
        trades = candidate_trades[str(row["candidate"])]
        summary = summarize_trades(trades)
        yearly = yearly_stats(trades)
        rolling = rolling_stats(trades, 90)
        rows.append(
            {
                "candidate": row["candidate"],
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
    entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    return net.groupby(entry_ts.dt.year).sum().reset_index(name="net_points")


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
    events: pd.DataFrame,
    candidates: list[BoundaryCandidate],
    folds: pd.DataFrame,
    aggregate: pd.DataFrame,
    full_sample: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NQ Range Boundary Reversion Search",
        "",
        "## Model",
        "",
        "This tests the box-trading idea: after a mechanically defined sideways range, buy near the lower boundary if price rejects the low, or short near the upper boundary if price rejects the high. Stop is placed beyond a recent prior low/high and is honored immediately; no averaging or holding through failure.",
        "",
        "## Data",
        "",
        f"- Source: `{_bar_zip_path()}`.",
        f"- Span: `{frame['ts'].min()}` to `{frame['ts'].max()}`.",
        f"- Rows: `{len(frame):,}`.",
        f"- Boundary events: `{len(events):,}`.",
        f"- Costs: `{BacktestCosts().round_trip_cost_points:.3f}` NQ points round trip.",
        "",
        "## Verdict",
        "",
    ]
    stable = aggregate[aggregate["stable_candidate"]] if not aggregate.empty else pd.DataFrame()
    if stable.empty:
        lines.append("No boundary-reversion candidate passed the stable gate in this run. Top rows are research candidates only.")
    else:
        top = stable.iloc[0]
        lines.append(
            f"Best stable boundary candidate: `{top['candidate']}` with `{top['test_net_points']:.2f}` selected OOS points, "
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
        lines.extend(["", "## Top Walk-Forward Rows", "", markdown_table(aggregate.head(30)[columns]), ""])
    if not full_sample.empty:
        columns = [
            "candidate",
            "trades",
            "net_points",
            "profit_factor",
            "win_rate",
            "payoff_ratio",
            "expectancy_points",
            "avg_r_multiple",
            "target_exit_share",
            "stop_exit_share",
            "max_drawdown_points",
            "positive_years",
            "years",
            "positive_90d_rate",
            "worst_90d_net",
            "first_half_points",
            "second_half_points",
        ]
        lines.extend(["## Full Sample Sanity", "", markdown_table(full_sample[columns]), ""])
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
    parser = argparse.ArgumentParser(description="Search NQ bar-only range boundary mean-reversion systems.")
    parser.add_argument("--start-date", default="2010-06-06")
    parser.add_argument("--walk-start-date", default="2012-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-short-trend-2010-adx-cache.pkl")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--output", default=".tmp/nq-range-boundary-2010-walkforward.csv")
    parser.add_argument("--aggregate-output", default=".tmp/nq-range-boundary-2010-aggregate.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-range-boundary-2010-oos-trades.csv")
    parser.add_argument("--full-sample-output", default=".tmp/nq-range-boundary-2010-full-sample.csv")
    parser.add_argument("--events-output", default=".tmp/nq-range-boundary-2010-events.csv")
    parser.add_argument("--report", default="reports/NQ-range-boundary-2010-search.md")
    parser.add_argument("--lookbacks", type=int, nargs="+", default=[30, 60, 120])
    parser.add_argument("--width-atr-max", type=float, nargs="+", default=[6.0, 8.0, 12.0])
    parser.add_argument("--efficiency-max", type=float, nargs="+", default=[0.25, 0.35, 0.50])
    parser.add_argument("--boundary-bands", type=float, nargs="+", default=[0.10, 0.20, 0.30])
    parser.add_argument("--reclaim-strengths", type=float, nargs="+", default=[0.05, 0.10, 0.20])
    parser.add_argument("--sessions", nargs="+", default=["ldn_ny", "us_rth", "us_late"])
    parser.add_argument("--direction-filters", nargs="+", choices=["both", "long", "short"], default=["both", "long", "short"])
    parser.add_argument("--stop-lookbacks", type=int, nargs="+", default=[3, 5, 10])
    parser.add_argument("--target-modes", nargs="+", choices=["fixed_r", "mid", "opposite_edge"], default=["fixed_r", "mid", "opposite_edge"])
    parser.add_argument("--reward-risks", type=float, nargs="+", default=[1.0, 1.5, 2.0, 3.0])
    parser.add_argument("--horizon-minutes", type=int, nargs="+", default=[30, 60, 120])
    parser.add_argument("--train-days", type=int, default=730)
    parser.add_argument("--purge-days", type=int, default=5)
    parser.add_argument("--test-days", type=int, default=180)
    parser.add_argument("--step-days", type=int, default=90)
    parser.add_argument("--max-fold-candidates", type=int, default=25)
    parser.add_argument("--full-sample-limit", type=int, default=40)
    parser.add_argument("--min-train-trades", type=int, default=50)
    parser.add_argument("--min-test-trades", type=int, default=10)
    parser.add_argument("--min-train-profit-factor", type=float, default=1.05)
    parser.add_argument("--min-test-profit-factor", type=float, default=1.0)
    parser.add_argument("--min-train-expectancy", type=float, default=0.10)
    parser.add_argument("--min-test-expectancy", type=float, default=0.0)
    parser.add_argument("--max-train-drawdown-points", type=float, default=6000.0)
    parser.add_argument("--max-test-drawdown-points", type=float, default=2500.0)
    parser.add_argument("--min-range-points", type=float, default=4.0)
    parser.add_argument("--min-wick-body-mult", type=float, default=0.50)
    parser.add_argument("--stop-buffer-points", type=float, default=0.25)
    parser.add_argument("--min-stop-points", type=float, default=3.0)
    parser.add_argument("--max-stop-points", type=float, default=80.0)
    parser.add_argument("--min-target-points", type=float, default=3.0)
    args = parser.parse_args()

    costs = BacktestCosts()
    base = load_continuous_nq_bars(args)
    frame = prepare_features(base, args)
    events = build_boundary_events(frame, args)
    candidates = candidate_pool(args)
    outcome_cache: dict[tuple[int, str, float, int], pd.DataFrame] = {}
    for stop_lookback in args.stop_lookbacks:
        for target_mode in args.target_modes:
            for reward_risk in args.reward_risks:
                for horizon in args.horizon_minutes:
                    key = (int(stop_lookback), str(target_mode), float(reward_risk), int(horizon))
                    print(f"computing outcomes {key}", flush=True)
                    outcome_cache[key] = compute_outcomes(
                        frame,
                        events,
                        stop_lookback=int(stop_lookback),
                        target_mode=str(target_mode),
                        reward_risk=float(reward_risk),
                        horizon=int(horizon),
                        args=args,
                        costs=costs,
                    )
    folds, oos_trades, candidate_trades = evaluate_candidates(outcome_cache, candidates, args)
    aggregate = aggregate_results(folds)
    full_sample = full_sample_summary(candidate_trades, aggregate, args.full_sample_limit)
    for output_path, data in [
        (args.output, folds),
        (args.aggregate_output, aggregate),
        (args.trades_output, oos_trades),
        (args.full_sample_output, full_sample),
        (args.events_output, events),
    ]:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data.to_csv(path, index=False)
    write_report(Path(args.report), frame, events, candidates, folds, aggregate, full_sample, args)
    result = {
        "source": str(_bar_zip_path()),
        "rows": int(len(frame)),
        "events": int(len(events)),
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
