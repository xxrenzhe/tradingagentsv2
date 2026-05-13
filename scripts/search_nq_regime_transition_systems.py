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
class RegimeCandidate:
    lookback: int
    width_atr_max: float
    efficiency_max: float
    displacement_atr_min: float
    body_share_min: float
    volume_z_min: float
    session: str
    direction_filter: str
    stop_mode: str
    reward_risk: float
    horizon_minutes: int

    @property
    def name(self) -> str:
        return (
            f"regime_breakout_lb{self.lookback}_w{self.width_atr_max:g}_eff{self.efficiency_max:g}"
            f"_disp{self.displacement_atr_min:g}_body{self.body_share_min:g}_vol{self.volume_z_min:g}"
            f"_{self.session}_{self.direction_filter}_{self.stop_mode}_rr{self.reward_risk:g}_h{self.horizon_minutes}"
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
    frame["volume_z_60"] = (volume - volume.rolling(60, min_periods=20).mean()) / volume.rolling(
        60, min_periods=20
    ).std()
    for lookback in sorted(set(args.lookbacks)):
        rolling_high = high.rolling(lookback, min_periods=lookback).max().shift(1)
        rolling_low = low.rolling(lookback, min_periods=lookback).min().shift(1)
        width = rolling_high - rolling_low
        tr_sum = true_range.rolling(lookback, min_periods=lookback).sum().shift(1)
        net_move = (close.shift(1) - close.shift(lookback + 1)).abs()
        frame[f"range_high_{lookback}"] = rolling_high
        frame[f"range_low_{lookback}"] = rolling_low
        frame[f"range_width_atr_{lookback}"] = width / frame["atr_120"].replace(0, np.nan)
        frame[f"range_efficiency_{lookback}"] = net_move / tr_sum.replace(0, np.nan)
    return frame.dropna(subset=["Open", "High", "Low", "Close"]).reset_index(drop=True)


def candidate_pool(args: argparse.Namespace) -> list[RegimeCandidate]:
    return [
        RegimeCandidate(
            lookback=int(lookback),
            width_atr_max=float(width),
            efficiency_max=float(efficiency),
            displacement_atr_min=float(displacement),
            body_share_min=float(body),
            volume_z_min=float(volume_z),
            session=session,
            direction_filter=direction,
            stop_mode=stop_mode,
            reward_risk=float(reward_risk),
            horizon_minutes=int(horizon),
        )
        for lookback in args.lookbacks
        for width in args.width_atr_max
        for efficiency in args.efficiency_max
        for displacement in args.displacement_atr_min
        for body in args.body_share_min
        for volume_z in args.volume_z_min
        for session in args.sessions
        for direction in args.direction_filters
        for stop_mode in args.stop_modes
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


def build_breakout_events(frame: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    high = frame["High"].to_numpy(dtype=float)
    low = frame["Low"].to_numpy(dtype=float)
    close = frame["Close"].to_numpy(dtype=float)
    open_price = frame["Open"].to_numpy(dtype=float)
    body_share = frame["body_share"].to_numpy(dtype=float)
    displacement_atr = frame["range_points"].to_numpy(dtype=float) / frame["atr_30"].replace(0, np.nan).to_numpy(dtype=float)
    volume_z = frame["volume_z_60"].fillna(0.0).to_numpy(dtype=float)
    atr_30 = frame["atr_30"].to_numpy(dtype=float)
    minute = frame["minute_of_day"].to_numpy(dtype=np.int16)
    symbols = frame["symbol"].astype(str).to_numpy()
    max_horizon = max(args.horizon_minutes)
    rows: list[pd.DataFrame] = []
    max_width = max(args.width_atr_max)
    max_eff = max(args.efficiency_max)
    min_disp = min(args.displacement_atr_min)
    min_body = min(args.body_share_min)
    min_volume_z = min(args.volume_z_min)
    for lookback in sorted(set(args.lookbacks)):
        range_high = frame[f"range_high_{lookback}"].to_numpy(dtype=float)
        range_low = frame[f"range_low_{lookback}"].to_numpy(dtype=float)
        width_atr = frame[f"range_width_atr_{lookback}"].to_numpy(dtype=float)
        efficiency = frame[f"range_efficiency_{lookback}"].to_numpy(dtype=float)
        buffer_points = np.maximum(args.min_buffer_points, args.breakout_buffer_atr * atr_30)
        compression = (
            np.isfinite(width_atr)
            & np.isfinite(efficiency)
            & (width_atr <= max_width)
            & (efficiency <= max_eff)
        )
        displacement = (
            np.isfinite(displacement_atr)
            & (displacement_atr >= min_disp)
            & np.isfinite(body_share)
            & (body_share >= min_body)
            & (volume_z >= min_volume_z)
        )
        long_breakout = compression & displacement & (close > range_high + buffer_points) & (close > open_price)
        short_breakout = compression & displacement & (close < range_low - buffer_points) & (close < open_price)
        direction = np.zeros(len(frame), dtype=np.int8)
        direction[long_breakout] = 1
        direction[short_breakout] = -1
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
                    "direction": direction[indexes].astype(np.int8),
                    "entry_ts": frame["ts"].to_numpy()[indexes],
                    "symbol": symbols[indexes],
                    "minute_of_day": minute[indexes],
                    "range_high": range_high[indexes],
                    "range_low": range_low[indexes],
                    "range_width_atr": width_atr[indexes],
                    "range_efficiency": efficiency[indexes],
                    "displacement_atr": displacement_atr[indexes],
                    "body_share": body_share[indexes],
                    "volume_z_60": volume_z[indexes],
                    "event_high": high[indexes],
                    "event_low": low[indexes],
                    "atr_30": atr_30[indexes],
                }
            )
        )
    if not rows:
        return pd.DataFrame()
    events = pd.concat(rows, ignore_index=True, sort=False)
    return events.sort_values(["event_index", "lookback"]).reset_index(drop=True)


def compute_outcomes(
    frame: pd.DataFrame,
    events: pd.DataFrame,
    *,
    stop_mode: str,
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
    event_indexes = events["event_index"].to_numpy(dtype=int)
    entry_indexes = events["entry_index"].to_numpy(dtype=int)
    timeout_indexes = event_indexes + int(horizon)
    directions = events["direction"].to_numpy(dtype=np.int8)
    entry_prices = open_prices[entry_indexes]
    stop_distances = stop_distances_for_events(events, entry_prices, stop_mode, args)
    valid = (
        np.isfinite(entry_prices)
        & np.isfinite(stop_distances)
        & (stop_distances >= args.min_stop_points)
        & (stop_distances <= args.max_stop_points)
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
    stop_distances = stop_distances[valid]
    stop_prices = np.where(directions > 0, entry_prices - stop_distances, entry_prices + stop_distances)
    target_distances = stop_distances * float(reward_risk)
    target_prices = np.where(directions > 0, entry_prices + target_distances, entry_prices - target_distances)

    offsets = np.arange(2, horizon + 1, dtype=int)
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
        no_hit_offset = horizon + 1
        first_invalid = np.where((~symbol_valid).any(axis=1), offsets[(~symbol_valid).argmax(axis=1)], no_hit_offset)
        first_stop = np.where(stop_hits.any(axis=1), offsets[stop_hits.argmax(axis=1)], no_hit_offset)
        first_target = np.where(target_hits.any(axis=1), offsets[target_hits.argmax(axis=1)], no_hit_offset)
        stop_first = first_stop <= first_target
        bracket_hit = (first_stop <= horizon) | (first_target <= horizon)
        exit_offsets = np.where(bracket_hit, np.minimum(first_stop, first_target), horizon)
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
    reasons = np.asarray(["timeout", "stop_loss", "take_profit"], dtype=object)[reason_codes]
    out = events.copy()
    out["signal_ts"] = pd.to_datetime(timestamps[event_indexes], utc=True)
    out["entry_ts"] = pd.to_datetime(timestamps[entry_indexes], utc=True)
    out["exit_ts"] = pd.to_datetime(timestamps[realized_exit_indexes], utc=True)
    out["entry_index"] = entry_indexes
    out["exit_index"] = realized_exit_indexes
    out["stop_mode"] = stop_mode
    out["reward_risk"] = float(reward_risk)
    out["horizon_minutes"] = int(horizon)
    out["entry_price"] = entry_prices
    out["exit_price"] = exit_prices
    out["exit_reason"] = reasons
    out["stop_distance_points"] = stop_distances
    out["target_distance_points"] = target_distances
    out["gross_points"] = gross_points
    out["net_points"] = net_points
    out["net_dollars"] = net_points * costs.point_value
    out["r_multiple"] = net_points / risk_points
    return out


def stop_distances_for_events(events: pd.DataFrame, entry_prices: np.ndarray, stop_mode: str, args: argparse.Namespace) -> np.ndarray:
    directions = events["direction"].to_numpy(dtype=np.int8)
    event_high = events["event_high"].to_numpy(dtype=float)
    event_low = events["event_low"].to_numpy(dtype=float)
    range_high = events["range_high"].to_numpy(dtype=float)
    range_low = events["range_low"].to_numpy(dtype=float)
    atr = events["atr_30"].to_numpy(dtype=float)
    buffer_points = np.maximum(args.min_buffer_points, args.stop_buffer_atr * atr)
    if stop_mode == "break_bar":
        long_stop = event_low - buffer_points
        short_stop = event_high + buffer_points
    elif stop_mode == "box_edge":
        long_stop = range_high - buffer_points
        short_stop = range_low + buffer_points
    elif stop_mode == "box_opposite":
        long_stop = range_low - buffer_points
        short_stop = range_high + buffer_points
    elif stop_mode == "atr":
        return np.maximum(args.min_stop_points, args.stop_atr_mult * atr)
    else:
        raise ValueError(f"unknown stop mode: {stop_mode}")
    return np.where(directions > 0, entry_prices - long_stop, short_stop - entry_prices)


def select_candidate_trades(outcomes: pd.DataFrame, candidate: RegimeCandidate) -> pd.DataFrame:
    if outcomes.empty:
        return outcomes
    mask = (
        (outcomes["lookback"].eq(candidate.lookback))
        & (outcomes["range_width_atr"] <= candidate.width_atr_max)
        & (outcomes["range_efficiency"] <= candidate.efficiency_max)
        & (outcomes["displacement_atr"] >= candidate.displacement_atr_min)
        & (outcomes["body_share"] >= candidate.body_share_min)
        & (outcomes["volume_z_60"] >= candidate.volume_z_min)
    )
    minutes = outcomes["minute_of_day"].to_numpy(dtype=np.int16)
    mask &= session_array(minutes, candidate.session)
    if candidate.direction_filter == "long":
        mask &= outcomes["direction"].eq(1)
    elif candidate.direction_filter == "short":
        mask &= outcomes["direction"].eq(-1)
    elif candidate.direction_filter != "both":
        raise ValueError(f"unknown direction filter: {candidate.direction_filter}")
    selected = outcomes.loc[mask].sort_values("event_index").copy()
    if selected.empty:
        return selected
    positions: list[int] = []
    next_available = 0
    event_indexes = selected["event_index"].to_numpy(dtype=int)
    exit_indexes = selected["exit_index"].to_numpy(dtype=int)
    for position, event_index in enumerate(event_indexes):
        entry_index = int(event_index) + 1
        if entry_index < next_available:
            continue
        positions.append(position)
        next_available = int(exit_indexes[position]) + 1
    if not positions:
        return selected.iloc[0:0].copy()
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
    outcome_cache: dict[tuple[str, float, int], pd.DataFrame],
    candidates: list[RegimeCandidate],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    start = pd.Timestamp(args.walk_start_date, tz="UTC")
    end = pd.Timestamp(args.end_date, tz="UTC")
    candidate_trades: dict[str, pd.DataFrame] = {}
    for index, candidate in enumerate(candidates, start=1):
        if index == 1 or index % 100 == 0 or index == len(candidates):
            print(f"selecting candidate {index}/{len(candidates)}: {candidate.name}", flush=True)
        outcomes = outcome_cache[(candidate.stop_mode, float(candidate.reward_risk), int(candidate.horizon_minutes))]
        trades = select_candidate_trades(outcomes, candidate)
        if not trades.empty:
            trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
            trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
        candidate_trades[candidate.name] = trades

    fold_rows: list[dict[str, Any]] = []
    oos_trade_rows: list[pd.DataFrame] = []
    fold = 0
    test_start = start
    while test_start + pd.Timedelta(days=args.test_days) <= end:
        train_start = test_start - pd.Timedelta(days=args.train_days + args.purge_days)
        train_end = test_start - pd.Timedelta(days=args.purge_days)
        test_end = test_start + pd.Timedelta(days=args.test_days)
        ranked: list[tuple[float, dict[str, Any], RegimeCandidate]] = []
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
                    "displacement_atr_min": candidate.displacement_atr_min,
                    "body_share_min": candidate.body_share_min,
                    "volume_z_min": candidate.volume_z_min,
                    "session": candidate.session,
                    "direction_filter": candidate.direction_filter,
                    "stop_mode": candidate.stop_mode,
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
        displacement_atr_min=("displacement_atr_min", "first"),
        body_share_min=("body_share_min", "first"),
        volume_z_min=("volume_z_min", "first"),
        session=("session", "first"),
        direction_filter=("direction_filter", "first"),
        stop_mode=("stop_mode", "first"),
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
    grouped["stable_candidate"] = apply_stability_gate(grouped)
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


def apply_stability_gate(
    grouped: pd.DataFrame,
    *,
    min_selected_folds: int = 3,
    min_test_trades: int = 0,
    min_positive_test_fold_rate: float = 0.67,
    min_test_win_rate: float = 0.0,
    min_test_profit_factor: float = 0.0,
    min_test_payoff_ratio: float = 0.0,
    min_net_to_drawdown: float = 1.0,
) -> pd.Series:
    return (
        (pd.to_numeric(grouped["selected_folds"], errors="coerce") >= min_selected_folds)
        & (pd.to_numeric(grouped["test_trades"], errors="coerce") >= min_test_trades)
        & (pd.to_numeric(grouped["positive_test_fold_rate"], errors="coerce") >= min_positive_test_fold_rate)
        & (pd.to_numeric(grouped["test_net_points"], errors="coerce") > 0)
        & (pd.to_numeric(grouped["avg_test_expectancy_points"], errors="coerce") > 0)
        & (pd.to_numeric(grouped["avg_test_win_rate"], errors="coerce") > min_test_win_rate)
        & (pd.to_numeric(grouped["avg_test_profit_factor"], errors="coerce") > min_test_profit_factor)
        & (pd.to_numeric(grouped["avg_test_payoff_ratio"], errors="coerce") > min_test_payoff_ratio)
        & (pd.to_numeric(grouped["net_to_drawdown"], errors="coerce") >= min_net_to_drawdown)
    )


def apply_cli_stability_gate(aggregate: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    if aggregate.empty:
        return aggregate
    result = aggregate.copy()
    result["stable_candidate"] = apply_stability_gate(
        result,
        min_selected_folds=args.min_selected_folds,
        min_test_trades=args.min_aggregate_test_trades,
        min_positive_test_fold_rate=args.min_positive_test_fold_rate,
        min_test_win_rate=args.gate_win_rate,
        min_test_profit_factor=args.gate_profit_factor,
        min_test_payoff_ratio=args.gate_payoff_ratio,
        min_net_to_drawdown=args.gate_net_to_drawdown,
    )
    return result.sort_values(
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
    candidates: list[RegimeCandidate],
    folds: pd.DataFrame,
    aggregate: pd.DataFrame,
    full_sample: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NQ Regime Transition Search",
        "",
        "## Model",
        "",
        "The model is explicitly `range -> expansion -> trend start`: a prior rolling box must be narrow and inefficient, then the current candle must close outside the box with displacement. Entries are next-bar open; exits use structural or ATR stops plus fixed R targets, with same-bar stop/target ambiguity resolved stop-first.",
        "",
        "## Data",
        "",
        f"- Source: `{_bar_zip_path()}`.",
        f"- Span: `{frame['ts'].min()}` to `{frame['ts'].max()}`.",
        f"- Rows: `{len(frame):,}`.",
        f"- Breakout events: `{len(events):,}`.",
        f"- Costs: `{BacktestCosts().round_trip_cost_points:.3f}` NQ points round trip.",
        "",
        "## Search",
        "",
        f"- Candidates: `{len(candidates):,}`.",
        f"- Lookbacks: `{', '.join(str(value) for value in args.lookbacks)}`.",
        f"- Sessions: `{', '.join(args.sessions)}`.",
        f"- Stops: `{', '.join(args.stop_modes)}`; R targets: `{', '.join(str(value) for value in args.reward_risks)}`.",
        f"- Walk-forward train/purge/test/step days: `{args.train_days}` / `{args.purge_days}` / `{args.test_days}` / `{args.step_days}`.",
        f"- Stable gate: selected_folds >= `{args.min_selected_folds}`, aggregate trades >= `{args.min_aggregate_test_trades}`, positive fold rate >= `{args.min_positive_test_fold_rate:.2%}`, win rate > `{args.gate_win_rate:.2%}`, PF > `{args.gate_profit_factor:.2f}`, payoff > `{args.gate_payoff_ratio:.2f}`, net/DD >= `{args.gate_net_to_drawdown:.2f}`.",
        "",
        "## Verdict",
        "",
    ]
    stable = aggregate[aggregate["stable_candidate"]] if not aggregate.empty else pd.DataFrame()
    if stable.empty:
        lines.append("No candidate passed the stable gate in this run. Top rows are research candidates only.")
    else:
        top = stable.iloc[0]
        lines.append(
            f"Best stable candidate: `{top['candidate']}` with `{top['test_net_points']:.2f}` selected OOS points, "
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
    parser = argparse.ArgumentParser(description="Search bar-only range-to-trend regime transition systems.")
    parser.add_argument("--start-date", default="2010-06-06")
    parser.add_argument("--walk-start-date", default="2012-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-short-trend-2010-adx-cache.pkl")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--output", default=".tmp/nq-regime-transition-2010-walkforward.csv")
    parser.add_argument("--aggregate-output", default=".tmp/nq-regime-transition-2010-aggregate.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-regime-transition-2010-oos-trades.csv")
    parser.add_argument("--full-sample-output", default=".tmp/nq-regime-transition-2010-full-sample.csv")
    parser.add_argument("--events-output", default=".tmp/nq-regime-transition-2010-events.csv")
    parser.add_argument("--report", default="reports/NQ-regime-transition-2010-search.md")
    parser.add_argument("--lookbacks", type=int, nargs="+", default=[30, 60, 120])
    parser.add_argument("--width-atr-max", type=float, nargs="+", default=[6.0, 8.0, 12.0])
    parser.add_argument("--efficiency-max", type=float, nargs="+", default=[0.25, 0.35, 0.50])
    parser.add_argument("--displacement-atr-min", type=float, nargs="+", default=[0.80, 1.00, 1.20])
    parser.add_argument("--body-share-min", type=float, nargs="+", default=[0.45, 0.55])
    parser.add_argument("--volume-z-min", type=float, nargs="+", default=[-0.50, 0.00])
    parser.add_argument("--sessions", nargs="+", default=["ldn_ny", "us_rth", "us_late"])
    parser.add_argument("--direction-filters", nargs="+", choices=["both", "long", "short"], default=["both", "long", "short"])
    parser.add_argument("--stop-modes", nargs="+", choices=["break_bar", "box_edge", "box_opposite", "atr"], default=["break_bar", "box_edge"])
    parser.add_argument("--reward-risks", type=float, nargs="+", default=[1.5, 2.0, 3.0])
    parser.add_argument("--horizon-minutes", type=int, nargs="+", default=[60, 120, 240])
    parser.add_argument("--train-days", type=int, default=730)
    parser.add_argument("--purge-days", type=int, default=5)
    parser.add_argument("--test-days", type=int, default=180)
    parser.add_argument("--step-days", type=int, default=90)
    parser.add_argument("--max-fold-candidates", type=int, default=25)
    parser.add_argument("--full-sample-limit", type=int, default=40)
    parser.add_argument("--min-selected-folds", type=int, default=3)
    parser.add_argument("--min-aggregate-test-trades", type=int, default=60)
    parser.add_argument("--min-positive-test-fold-rate", type=float, default=0.67)
    parser.add_argument("--gate-win-rate", type=float, default=0.0)
    parser.add_argument("--gate-profit-factor", type=float, default=0.0)
    parser.add_argument("--gate-payoff-ratio", type=float, default=0.0)
    parser.add_argument("--gate-net-to-drawdown", type=float, default=1.0)
    parser.add_argument("--min-train-trades", type=int, default=50)
    parser.add_argument("--min-test-trades", type=int, default=10)
    parser.add_argument("--min-train-profit-factor", type=float, default=1.05)
    parser.add_argument("--min-test-profit-factor", type=float, default=1.0)
    parser.add_argument("--min-train-expectancy", type=float, default=0.10)
    parser.add_argument("--min-test-expectancy", type=float, default=0.0)
    parser.add_argument("--max-train-drawdown-points", type=float, default=6000.0)
    parser.add_argument("--max-test-drawdown-points", type=float, default=2500.0)
    parser.add_argument("--breakout-buffer-atr", type=float, default=0.05)
    parser.add_argument("--min-buffer-points", type=float, default=0.25)
    parser.add_argument("--stop-buffer-atr", type=float, default=0.10)
    parser.add_argument("--stop-atr-mult", type=float, default=2.0)
    parser.add_argument("--min-stop-points", type=float, default=4.0)
    parser.add_argument("--max-stop-points", type=float, default=80.0)
    args = parser.parse_args()

    costs = BacktestCosts()
    base = load_continuous_nq_bars(args)
    frame = prepare_features(base, args)
    events = build_breakout_events(frame, args)
    candidates = candidate_pool(args)
    outcome_cache: dict[tuple[str, float, int], pd.DataFrame] = {}
    for stop_mode in args.stop_modes:
        for reward_risk in args.reward_risks:
            for horizon in args.horizon_minutes:
                key = (str(stop_mode), float(reward_risk), int(horizon))
                print(f"computing outcomes {key}", flush=True)
                outcome_cache[key] = compute_outcomes(
                    frame,
                    events,
                    stop_mode=str(stop_mode),
                    reward_risk=float(reward_risk),
                    horizon=int(horizon),
                    args=args,
                    costs=costs,
                )
    folds, oos_trades, candidate_trades = evaluate_candidates(outcome_cache, candidates, args)
    aggregate = apply_cli_stability_gate(aggregate_results(folds), args)
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
