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
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from discover_nq_tradeable_market_features import MarketFeature, build_market_features, load_or_prepare_features
from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.config.env import load_project_env
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.evolution.memory import EvolutionMemory, utc_now
from tradingagents.execution.llm_debate_delayed_strategy import extract_json_object, invoke_aicode_streaming_json
from tradingagents.llm_clients.factory import create_llm_client


@dataclass(frozen=True)
class StrategyTemplate:
    name: str
    feature_id: str
    family: str
    direction: int
    entry_mode: str
    stop_mode: str
    reward_risk: float
    horizon_minutes: int
    confirm_bars: int
    pullback_atr: float
    stop_atr_mult: float
    exit_mode: str = "bracket"
    fast_fail_bars: int = 5


def select_feature_ids(summary: pd.DataFrame, *, explicit: list[str] | None, top_features: int) -> list[str]:
    if explicit:
        return list(dict.fromkeys(explicit))
    if summary.empty or "feature_id" not in summary.columns:
        return []
    return summary.head(top_features)["feature_id"].astype(str).drop_duplicates().tolist()


def template_pool(
    market_features: dict[str, MarketFeature],
    feature_ids: list[str],
    *,
    entry_modes: list[str],
    stop_modes: list[str],
    reward_risks: list[float],
    horizons: list[int],
    confirm_bars: list[int],
    pullback_atr: list[float],
    stop_atr_mult: list[float],
    exit_modes: list[str] | None = None,
    fast_fail_bars: list[int] | None = None,
) -> list[StrategyTemplate]:
    exit_modes = exit_modes or ["bracket"]
    fast_fail_bars = fast_fail_bars or [5]
    templates: list[StrategyTemplate] = []
    for feature_id in feature_ids:
        feature = market_features[feature_id]
        direction = 1 if feature.direction_hint == "long" else -1
        for entry_mode in entry_modes:
            for stop_mode in stop_modes:
                for rr in reward_risks:
                    for horizon in horizons:
                        for confirm in confirm_bars:
                            for pullback in pullback_atr:
                                for atr_mult in stop_atr_mult:
                                    if entry_mode not in {"pullback_reclaim", "reclaim_hold", "quality_reclaim"} and pullback != pullback_atr[0]:
                                        continue
                                    if stop_mode not in {"atr", "hybrid_event_atr"} and atr_mult != stop_atr_mult[0]:
                                        continue
                                    for exit_mode in exit_modes:
                                        for fail_bars in fast_fail_bars:
                                            if exit_mode not in {"bracket_fast_fail", "fast_fail", "staged"} and fail_bars != fast_fail_bars[0]:
                                                continue
                                            name = (
                                                f"{feature_id}_{entry_mode}_{stop_mode}_{exit_mode}_rr{rr:g}"
                                                f"_h{horizon}_c{confirm}_pb{pullback:g}_atr{atr_mult:g}_ff{fail_bars}"
                                            )
                                            templates.append(
                                                StrategyTemplate(
                                                    name=name,
                                                    feature_id=feature_id,
                                                    family=feature.family,
                                                    direction=direction,
                                                    entry_mode=entry_mode,
                                                    stop_mode=stop_mode,
                                                    reward_risk=float(rr),
                                                    horizon_minutes=int(horizon),
                                                    confirm_bars=int(confirm),
                                                    pullback_atr=float(pullback),
                                                    stop_atr_mult=float(atr_mult),
                                                    exit_mode=str(exit_mode),
                                                    fast_fail_bars=int(fail_bars),
                                                )
                                            )
    return templates


def build_template_trades(
    data: pd.DataFrame,
    feature: MarketFeature,
    template: StrategyTemplate,
    *,
    costs: BacktestCosts | None = None,
    min_gap_minutes: int = 15,
    min_stop_points: float = 4.0,
    max_stop_points: float = 100.0,
    stop_buffer_atr: float = 0.10,
    min_buffer_points: float = 0.25,
) -> pd.DataFrame:
    costs = costs or BacktestCosts()
    open_prices = pd.to_numeric(data["Open"], errors="coerce").to_numpy(dtype=float)
    high = pd.to_numeric(data["High"], errors="coerce").to_numpy(dtype=float)
    low = pd.to_numeric(data["Low"], errors="coerce").to_numpy(dtype=float)
    close = pd.to_numeric(data["Close"], errors="coerce").to_numpy(dtype=float)
    atr = pd.to_numeric(data["atr_30"], errors="coerce").to_numpy(dtype=float)
    timestamps = pd.to_datetime(data["ts"], utc=True).to_numpy()
    symbols = data["symbol"].astype(str).to_numpy() if "symbol" in data.columns else np.asarray(["NQ"] * len(data))
    event_indexes = np.flatnonzero(feature.signal.fillna(False).to_numpy(dtype=bool))
    event_indexes = _dedupe_indexes(event_indexes, min_gap_minutes)
    if len(event_indexes) == 0:
        return empty_trades()
    entry_indexes = resolve_entry_indexes(
        event_indexes=event_indexes,
        open_prices=open_prices,
        high=high,
        low=low,
        close=close,
        atr=atr,
        direction=template.direction,
        entry_mode=template.entry_mode,
        confirm_bars=template.confirm_bars,
        pullback_atr=template.pullback_atr,
    )
    valid = np.isfinite(entry_indexes)
    event_indexes = event_indexes[valid]
    entry_indexes = entry_indexes[valid].astype(int)
    if len(entry_indexes) == 0:
        return empty_trades()
    max_exit = entry_indexes + template.horizon_minutes
    valid = max_exit < len(data)
    event_indexes = event_indexes[valid]
    entry_indexes = entry_indexes[valid]
    max_exit = max_exit[valid]
    if len(entry_indexes) == 0:
        return empty_trades()
    valid_symbol = symbols[event_indexes] == symbols[max_exit]
    event_indexes = event_indexes[valid_symbol]
    entry_indexes = entry_indexes[valid_symbol]
    max_exit = max_exit[valid_symbol]
    if len(entry_indexes) == 0:
        return empty_trades()

    entry_prices = open_prices[entry_indexes]
    stop_distances = stop_distances_for_template(
        template=template,
        event_indexes=event_indexes,
        entry_prices=entry_prices,
        high=high,
        low=low,
        atr=atr,
        min_stop_points=min_stop_points,
        stop_buffer_atr=stop_buffer_atr,
        min_buffer_points=min_buffer_points,
    )
    valid = (
        np.isfinite(entry_prices)
        & np.isfinite(stop_distances)
        & (stop_distances >= min_stop_points)
        & (stop_distances <= max_stop_points)
    )
    event_indexes = event_indexes[valid]
    entry_indexes = entry_indexes[valid]
    max_exit = max_exit[valid]
    entry_prices = entry_prices[valid]
    stop_distances = stop_distances[valid]
    if len(entry_indexes) == 0:
        return empty_trades()

    direction = int(template.direction)
    stop_prices = np.where(direction > 0, entry_prices - stop_distances, entry_prices + stop_distances)
    target_distances = stop_distances * float(template.reward_risk)
    target_prices = np.where(direction > 0, entry_prices + target_distances, entry_prices - target_distances)
    offsets = np.arange(0, template.horizon_minutes + 1, dtype=int)
    window_indexes = entry_indexes[:, None] + offsets[None, :]
    if direction > 0:
        stop_hits = low[window_indexes] <= stop_prices[:, None]
        target_hits = high[window_indexes] >= target_prices[:, None]
        first_target_prices = entry_prices + stop_distances
        first_target_hits = high[window_indexes] >= first_target_prices[:, None]
        fast_fail_hits = close[window_indexes] < entry_prices[:, None]
    else:
        stop_hits = high[window_indexes] >= stop_prices[:, None]
        target_hits = low[window_indexes] <= target_prices[:, None]
        first_target_prices = entry_prices - stop_distances
        first_target_hits = low[window_indexes] <= first_target_prices[:, None]
        fast_fail_hits = close[window_indexes] > entry_prices[:, None]
    same_symbol = symbols[window_indexes] == symbols[event_indexes, None]
    stop_hits &= same_symbol
    target_hits &= same_symbol
    first_target_hits &= same_symbol
    fast_fail_hits &= same_symbol
    fast_fail_enabled = template.exit_mode in {"bracket_fast_fail", "fast_fail", "staged"} and template.fast_fail_bars > 0
    if fast_fail_enabled:
        fast_fail_hits[:, 0] = False
        max_fast_fail_offset = min(template.fast_fail_bars, template.horizon_minutes)
        if max_fast_fail_offset + 1 < fast_fail_hits.shape[1]:
            fast_fail_hits[:, max_fast_fail_offset + 1 :] = False
    else:
        fast_fail_hits[:] = False
    no_hit = template.horizon_minutes + 1
    first_stop = np.where(stop_hits.any(axis=1), stop_hits.argmax(axis=1), no_hit)
    first_target = np.where(target_hits.any(axis=1), target_hits.argmax(axis=1), no_hit)
    first_fast_fail = np.where(fast_fail_hits.any(axis=1), fast_fail_hits.argmax(axis=1), no_hit)
    if template.exit_mode == "staged":
        first_scale = np.where(first_target_hits.any(axis=1), first_target_hits.argmax(axis=1), no_hit)
        first_event = np.minimum(np.minimum(first_stop, first_scale), first_fast_fail)
        stopped_before_scale = first_stop <= np.minimum(first_scale, first_fast_fail)
        fast_fail_before_scale = first_fast_fail < np.minimum(first_stop, first_scale)
        scaled_before_exit = first_scale < np.minimum(first_stop, first_fast_fail)
        first_exit_hit = first_event < no_hit
        target_after_scale = target_hits & (offsets[None, :] >= first_scale[:, None])
        second_target = np.where(target_after_scale.any(axis=1), target_after_scale.argmax(axis=1), no_hit)
        second_target_hit = scaled_before_exit & (second_target < no_hit)
        realized_offsets = np.full(len(event_indexes), template.horizon_minutes, dtype=int)
        realized_offsets = np.where(stopped_before_scale, first_stop, realized_offsets)
        realized_offsets = np.where(fast_fail_before_scale, first_fast_fail, realized_offsets)
        realized_offsets = np.where(second_target_hit, second_target, realized_offsets)
        realized_exit_indexes = entry_indexes + realized_offsets
        final_exit_prices = close[max_exit]
        first_leg_points = np.where(scaled_before_exit, stop_distances, 0.0)
        second_leg_points = np.where(second_target_hit, target_distances, (final_exit_prices - entry_prices) * direction)
        gross_points = np.where(
            stopped_before_scale,
            -stop_distances,
            np.where(
                fast_fail_before_scale,
                (close[realized_exit_indexes] - entry_prices) * direction,
                np.where(scaled_before_exit, (first_leg_points + second_leg_points) / 2.0, second_leg_points),
            ),
        )
        gross_points = np.where(
            first_exit_hit | scaled_before_exit,
            gross_points,
            second_leg_points,
        )
        exit_prices = entry_prices + gross_points * direction
        exit_reasons = np.full(len(event_indexes), "time", dtype=object)
        exit_reasons[stopped_before_scale] = "stop_loss"
        exit_reasons[fast_fail_before_scale] = "fast_fail"
        exit_reasons[scaled_before_exit & ~second_target_hit] = "partial_time"
        exit_reasons[second_target_hit] = "partial_target"
    else:
        first_event = np.minimum(np.minimum(first_stop, first_target), first_fast_fail)
        bracket_hit = first_event < no_hit
        stop_first = first_stop <= np.minimum(first_target, first_fast_fail)
        target_first = first_target < np.minimum(first_stop, first_fast_fail)
        fast_fail_first = first_fast_fail < np.minimum(first_stop, first_target)
        realized_offsets = np.where(bracket_hit, first_event, template.horizon_minutes)
        realized_exit_indexes = entry_indexes + realized_offsets
        exit_prices = close[max_exit]
        stop_rows = bracket_hit & stop_first
        target_rows = bracket_hit & target_first
        fast_fail_rows = bracket_hit & fast_fail_first
        exit_prices = np.where(stop_rows, stop_prices, exit_prices)
        exit_prices = np.where(target_rows, target_prices, exit_prices)
        exit_prices = np.where(fast_fail_rows, close[realized_exit_indexes], exit_prices)
        exit_reasons = np.full(len(event_indexes), "time", dtype=object)
        exit_reasons[stop_rows] = "stop_loss"
        exit_reasons[target_rows] = "take_profit"
        exit_reasons[fast_fail_rows] = "fast_fail"
        gross_points = (exit_prices - entry_prices) * direction
    net_points = gross_points - costs.round_trip_cost_points
    rows: list[dict[str, Any]] = []
    next_available = 0
    for position, entry_index in enumerate(entry_indexes):
        if int(entry_index) < next_available:
            continue
        exit_index = int(realized_exit_indexes[position])
        rows.append(
            {
                "template": template.name,
                "feature_id": template.feature_id,
                "family": template.family,
                "entry_mode": template.entry_mode,
                "stop_mode": template.stop_mode,
                "exit_mode": template.exit_mode,
                "reward_risk": template.reward_risk,
                "horizon_minutes": template.horizon_minutes,
                "direction": direction,
                "event_ts": str(timestamps[event_indexes[position]]),
                "entry_ts": str(timestamps[entry_index]),
                "exit_ts": str(timestamps[exit_index]),
                "event_index": int(event_indexes[position]),
                "entry_index": int(entry_index),
                "exit_index": exit_index,
                "entry_price": float(entry_prices[position]),
                "exit_price": float(exit_prices[position]),
                "stop_distance_points": float(stop_distances[position]),
                "target_distance_points": float(target_distances[position]),
                "gross_points": float(gross_points[position]),
                "net_points": float(net_points[position]),
                "net_dollars": float(net_points[position] * costs.point_value),
                "exit_reason": str(exit_reasons[position]),
            }
        )
        next_available = exit_index + 1
    return pd.DataFrame(rows) if rows else empty_trades()


def resolve_entry_indexes(
    *,
    event_indexes: np.ndarray,
    open_prices: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray,
    direction: int,
    entry_mode: str,
    confirm_bars: int,
    pullback_atr: float,
) -> np.ndarray:
    entry_indexes = np.full(len(event_indexes), np.nan, dtype=float)
    if entry_mode == "next_open":
        return event_indexes.astype(float) + 1

    event_high = high[event_indexes]
    event_low = low[event_indexes]
    event_mid = (event_high + event_low) / 2.0
    event_close = close[event_indexes]
    event_atr = np.nan_to_num(atr[event_indexes], nan=0.0)
    for offset in range(1, confirm_bars + 1):
        probe = event_indexes + offset
        next_entry = probe + 1
        valid = np.isnan(entry_indexes) & (probe < len(close)) & (next_entry < len(open_prices))
        if not valid.any():
            continue
        valid_positions = np.flatnonzero(valid)
        valid_probe = probe[valid_positions]
        if entry_mode == "confirm_break":
            if direction > 0:
                valid_condition = (
                    close[valid_probe]
                    > event_high[valid_positions] + np.maximum(0.25, 0.05 * event_atr[valid_positions])
                )
            else:
                valid_condition = (
                    close[valid_probe]
                    < event_low[valid_positions] - np.maximum(0.25, 0.05 * event_atr[valid_positions])
                )
        elif entry_mode == "midpoint_hold":
            if direction > 0:
                valid_condition = (close[valid_probe] > event_mid[valid_positions]) & (
                    low[valid_probe] >= event_low[valid_positions]
                )
            else:
                valid_condition = (close[valid_probe] < event_mid[valid_positions]) & (
                    high[valid_probe] <= event_high[valid_positions]
                )
        elif entry_mode == "pullback_reclaim":
            if direction > 0:
                valid_condition = (
                    low[valid_probe] <= event_close[valid_positions] - pullback_atr * event_atr[valid_positions]
                ) & (close[valid_probe] > event_mid[valid_positions])
            else:
                valid_condition = (
                    high[valid_probe] >= event_close[valid_positions] + pullback_atr * event_atr[valid_positions]
                ) & (close[valid_probe] < event_mid[valid_positions])
        elif entry_mode == "confirm_hold":
            previous = valid_probe - 1
            if direction > 0:
                valid_condition = (close[previous] > event_mid[valid_positions]) & (close[valid_probe] > close[previous])
            else:
                valid_condition = (close[previous] < event_mid[valid_positions]) & (close[valid_probe] < close[previous])
        elif entry_mode == "reclaim_hold":
            previous = valid_probe - 1
            if direction > 0:
                pulled_back = low[previous] <= event_close[valid_positions] - pullback_atr * event_atr[valid_positions]
                valid_condition = pulled_back & (close[previous] > event_mid[valid_positions]) & (
                    close[valid_probe] > event_mid[valid_positions]
                )
            else:
                pulled_back = high[previous] >= event_close[valid_positions] + pullback_atr * event_atr[valid_positions]
                valid_condition = pulled_back & (close[previous] < event_mid[valid_positions]) & (
                    close[valid_probe] < event_mid[valid_positions]
                )
        elif entry_mode == "quality_reclaim":
            previous = valid_probe - 1
            probe_range = high[valid_probe] - low[valid_probe]
            close_position = np.divide(
                close[valid_probe] - low[valid_probe],
                probe_range,
                out=np.full(len(valid_probe), 0.5, dtype=float),
                where=probe_range > 0,
            )
            if direction > 0:
                pulled_back = low[valid_probe] <= event_close[valid_positions] - pullback_atr * event_atr[valid_positions]
                valid_condition = (
                    pulled_back
                    & (close[valid_probe] > event_mid[valid_positions])
                    & (close[valid_probe] > high[previous])
                    & (close_position >= 0.65)
                )
            else:
                pulled_back = high[valid_probe] >= event_close[valid_positions] + pullback_atr * event_atr[valid_positions]
                valid_condition = (
                    pulled_back
                    & (close[valid_probe] < event_mid[valid_positions])
                    & (close[valid_probe] < low[previous])
                    & (close_position <= 0.35)
                )
        else:
            raise ValueError(f"unknown entry mode: {entry_mode}")
        condition = np.zeros(len(event_indexes), dtype=bool)
        condition[valid_positions] = valid_condition
        selected = valid & condition
        entry_indexes[selected] = next_entry[selected]
    return entry_indexes


def stop_distances_for_template(
    *,
    template: StrategyTemplate,
    event_indexes: np.ndarray,
    entry_prices: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    atr: np.ndarray,
    min_stop_points: float,
    stop_buffer_atr: float,
    min_buffer_points: float,
) -> np.ndarray:
    event_atr = np.nan_to_num(atr[event_indexes], nan=min_stop_points)
    if template.stop_mode == "atr":
        return np.maximum(min_stop_points, template.stop_atr_mult * event_atr)
    buffer = np.maximum(min_buffer_points, stop_buffer_atr * event_atr)
    if template.stop_mode in {"event_extreme", "hybrid_event_atr"}:
        if template.direction > 0:
            structural = entry_prices - (low[event_indexes] - buffer)
        else:
            structural = (high[event_indexes] + buffer) - entry_prices
        if template.stop_mode == "hybrid_event_atr":
            atr_stop = np.maximum(min_stop_points, template.stop_atr_mult * event_atr)
            return np.minimum(structural, atr_stop)
        return structural
    if template.stop_mode == "event_mid":
        midpoint = (high[event_indexes] + low[event_indexes]) / 2.0
        if template.direction > 0:
            return entry_prices - (midpoint - buffer)
        return (midpoint + buffer) - entry_prices
    raise ValueError(f"unknown stop mode: {template.stop_mode}")


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


def empty_trades() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "template",
            "feature_id",
            "family",
            "entry_mode",
            "stop_mode",
            "exit_mode",
            "reward_risk",
            "horizon_minutes",
            "direction",
            "event_ts",
            "entry_ts",
            "exit_ts",
            "event_index",
            "entry_index",
            "exit_index",
            "entry_price",
            "exit_price",
            "stop_distance_points",
            "target_distance_points",
            "gross_points",
            "net_points",
            "net_dollars",
            "exit_reason",
        ]
    )


def summarize_trades(trades: pd.DataFrame) -> dict[str, float]:
    net = pd.to_numeric(trades["net_points"], errors="coerce").dropna() if not trades.empty else pd.Series(dtype=float)
    if net.empty:
        return {
            "trades": 0.0,
            "net_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "payoff_ratio": 0.0,
            "avg_points": 0.0,
            "expectancy_points": 0.0,
            "max_drawdown_points": 0.0,
            "target_exit_rate": 0.0,
            "stop_exit_rate": 0.0,
            "time_exit_rate": 0.0,
            "fast_fail_exit_rate": 0.0,
            "partial_time_exit_rate": 0.0,
            "partial_target_exit_rate": 0.0,
            "median_points": 0.0,
        }
    wins = net[net > 0]
    losses = net[net < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(-losses.mean()) if len(losses) else 0.0
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    reasons = trades["exit_reason"].astype(str) if "exit_reason" in trades.columns else pd.Series(dtype=str)
    target_like = reasons.isin(["take_profit", "partial_target"]) if len(reasons) else pd.Series(dtype=bool)
    return {
        "trades": float(len(net)),
        "net_points": float(net.sum()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else (999.0 if gross_profit > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "payoff_ratio": float(avg_win / avg_loss) if avg_loss else (999.0 if avg_win > 0 else 0.0),
        "avg_points": float(net.mean()),
        "expectancy_points": float(net.mean()),
        "max_drawdown_points": float(drawdown.max()) if not drawdown.empty else 0.0,
        "target_exit_rate": float(target_like.mean()) if len(reasons) else 0.0,
        "stop_exit_rate": float((reasons == "stop_loss").mean()) if len(reasons) else 0.0,
        "time_exit_rate": float((reasons == "time").mean()) if len(reasons) else 0.0,
        "fast_fail_exit_rate": float((reasons == "fast_fail").mean()) if len(reasons) else 0.0,
        "partial_time_exit_rate": float((reasons == "partial_time").mean()) if len(reasons) else 0.0,
        "partial_target_exit_rate": float((reasons == "partial_target").mean()) if len(reasons) else 0.0,
        "median_points": float(net.median()),
    }


def full_sample_results(
    data: pd.DataFrame,
    market_features: dict[str, MarketFeature],
    templates: list[StrategyTemplate],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    rows: list[dict[str, Any]] = []
    trades_by_template: dict[str, pd.DataFrame] = {}
    costs = BacktestCosts()
    for index, template in enumerate(templates, start=1):
        if index == 1 or index % 100 == 0 or index == len(templates):
            print(f"template {index}/{len(templates)} {template.name}", flush=True)
        trades = build_template_trades(
            data,
            market_features[template.feature_id],
            template,
            costs=costs,
            min_gap_minutes=args.min_gap_minutes,
            min_stop_points=args.min_stop_points,
            max_stop_points=args.max_stop_points,
            stop_buffer_atr=args.stop_buffer_atr,
            min_buffer_points=args.min_buffer_points,
        )
        summary = summarize_trades(trades)
        if summary["trades"] < args.min_full_sample_trades:
            continue
        rows.append({"template": template.name, **template.__dict__, **summary, "research_score": research_score(summary)})
        trades_by_template[template.name] = trades
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values(["research_score", "net_points", "trades"], ascending=[False, False, False]).reset_index(drop=True)
    return frame, trades_by_template


def research_score(summary: dict[str, float]) -> float:
    drawdown = max(float(summary["max_drawdown_points"]), 1.0)
    evidence = min(float(summary["trades"]), 500.0) / 500.0
    return float(
        (float(summary["net_points"]) / drawdown)
        + 8.0 * float(summary["avg_points"])
        + 5.0 * (float(summary["target_exit_rate"]) - float(summary["stop_exit_rate"]))
        + 2.0 * evidence
    )


def walk_forward_validate(
    trades_by_template: dict[str, pd.DataFrame],
    templates: list[StrategyTemplate],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not trades_by_template:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    template_by_name = {template.name: template for template in templates}
    start = pd.Timestamp(args.walk_start_date, tz="UTC")
    end = pd.Timestamp(args.end_date, tz="UTC")
    fold_rows: list[dict[str, Any]] = []
    selected_trades: list[pd.DataFrame] = []
    fold = 0
    test_start = start
    while test_start + pd.Timedelta(days=args.test_days) <= end:
        train_start = test_start - pd.Timedelta(days=args.train_days + args.purge_days)
        train_end = test_start - pd.Timedelta(days=args.purge_days)
        test_end = test_start + pd.Timedelta(days=args.test_days)
        ranked: list[tuple[float, str, dict[str, float]]] = []
        for template_name, trades in trades_by_template.items():
            frame = trades.copy()
            entry_ts = pd.to_datetime(frame["entry_ts"], utc=True)
            train = frame[(entry_ts >= train_start) & (entry_ts < train_end)]
            summary = summarize_trades(train)
            if summary["trades"] < args.min_train_trades:
                continue
            if summary["net_points"] < args.min_train_net_points:
                continue
            ranked.append((research_score(summary), template_name, summary))
        ranked.sort(key=lambda item: item[0], reverse=True)
        for rank, (score, template_name, train_summary) in enumerate(ranked[: args.max_fold_candidates], start=1):
            trades = trades_by_template[template_name].copy()
            entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)
            test = trades[(entry_ts >= test_start) & (entry_ts < test_end)].copy()
            test_summary = summarize_trades(test)
            template = template_by_name[template_name]
            fold_rows.append(
                {
                    "fold": fold,
                    "fold_rank": rank,
                    "template": template_name,
                    "feature_id": template.feature_id,
                    "family": template.family,
                    "entry_mode": template.entry_mode,
                    "stop_mode": template.stop_mode,
                    "exit_mode": template.exit_mode,
                    "reward_risk": template.reward_risk,
                    "horizon_minutes": template.horizon_minutes,
                    "train_start": str(train_start.date()),
                    "train_end": str(train_end.date()),
                    "test_start": str(test_start.date()),
                    "test_end": str(test_end.date()),
                    "train_research_score": score,
                    **{f"train_{key}": value for key, value in train_summary.items()},
                    **{f"test_{key}": value for key, value in test_summary.items()},
                }
            )
            if not test.empty:
                exported = test.copy()
                exported["fold"] = fold
                exported["fold_rank"] = rank
                selected_trades.append(exported)
        fold += 1
        test_start += pd.Timedelta(days=args.step_days)
    folds = pd.DataFrame(fold_rows)
    selected = pd.concat(selected_trades, ignore_index=True, sort=False) if selected_trades else pd.DataFrame()
    selected = dedupe_selected_trades(selected)
    aggregate = aggregate_walk_forward(folds, selected)
    return folds, aggregate, selected


def aggregate_walk_forward(folds: pd.DataFrame, selected_trades: pd.DataFrame) -> pd.DataFrame:
    if folds.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for template_name, group in folds.groupby("template", sort=False):
        trades = selected_trades[selected_trades["template"].astype(str).eq(str(template_name))] if not selected_trades.empty else pd.DataFrame()
        trades = dedupe_selected_trades(trades)
        summary = summarize_trades(trades)
        rows.append(
            {
                "template": template_name,
                "feature_id": str(group["feature_id"].iloc[0]),
                "family": str(group["family"].iloc[0]),
                "entry_mode": str(group["entry_mode"].iloc[0]),
                "stop_mode": str(group["stop_mode"].iloc[0]),
                "exit_mode": str(group["exit_mode"].iloc[0]) if "exit_mode" in group.columns else "bracket",
                "reward_risk": float(group["reward_risk"].iloc[0]),
                "horizon_minutes": int(group["horizon_minutes"].iloc[0]),
                "selected_folds": int(group["fold"].nunique()),
                "positive_test_fold_rate": float((pd.to_numeric(group["test_net_points"], errors="coerce") > 0).mean()),
                "min_test_fold_net_points": float(pd.to_numeric(group["test_net_points"], errors="coerce").min()),
                "avg_train_research_score": float(pd.to_numeric(group["train_research_score"], errors="coerce").mean()),
                **{f"test_{key}": value for key, value in summary.items()},
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["walk_forward_score"] = (
        pd.to_numeric(frame["test_net_points"], errors="coerce").fillna(0.0)
        / pd.to_numeric(frame["test_max_drawdown_points"], errors="coerce").clip(lower=1.0).fillna(1.0)
        + pd.to_numeric(frame["positive_test_fold_rate"], errors="coerce").fillna(0.0) * 5.0
        + pd.to_numeric(frame["test_avg_points"], errors="coerce").fillna(0.0) * 8.0
        + pd.to_numeric(frame["selected_folds"], errors="coerce").clip(upper=8).fillna(0.0) * 0.25
    )
    return frame.sort_values(
        ["walk_forward_score", "test_net_points", "positive_test_fold_rate"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def dedupe_selected_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades
    sort_columns = [column for column in ["fold", "fold_rank", "entry_index"] if column in trades.columns]
    frame = trades.sort_values(sort_columns).copy() if sort_columns else trades.copy()
    if {"template", "entry_index"}.issubset(frame.columns):
        return frame.drop_duplicates(["template", "entry_index"], keep="first")
    if {"template", "entry_ts"}.issubset(frame.columns):
        return frame.drop_duplicates(["template", "entry_ts"], keep="first")
    return frame.drop_duplicates(keep="first")


def invoke_llm_review(aggregate: pd.DataFrame, full_sample: pd.DataFrame, args: argparse.Namespace) -> dict[str, Any]:
    if args.no_llm:
        return fallback_review(aggregate, full_sample)
    load_project_env()
    provider = args.provider or DEFAULT_CONFIG["llm_provider"]
    model = args.model or DEFAULT_CONFIG["deep_think_llm"]
    base_url = args.backend_url or DEFAULT_CONFIG.get("backend_url")
    prompt = build_review_prompt(aggregate.head(args.llm_top_n), full_sample.head(args.llm_top_n), args)
    try:
        if provider.lower() == "aicode":
            content = invoke_aicode_streaming_json(prompt, model=model, base_url=base_url, timeout=args.llm_timeout)
        else:
            llm = create_llm_client(provider, model, base_url=base_url, timeout=args.llm_timeout, streaming=False).get_llm()
            response = llm.invoke(prompt)
            content = str(getattr(response, "content", response))
        payload = extract_json_object(content)
        payload.setdefault("status", "parsed")
        payload.setdefault("provider", provider)
        payload.setdefault("model", model)
        payload["raw_response"] = content
        return payload
    except Exception as exc:
        payload = fallback_review(aggregate, full_sample)
        payload["status"] = "fallback_after_error"
        payload["error"] = str(exc) or exc.__class__.__name__
        return payload


def build_review_prompt(aggregate: pd.DataFrame, full_sample: pd.DataFrame, args: argparse.Namespace) -> str:
    aggregate_rows = aggregate.replace([np.inf, -np.inf], np.nan).where(pd.notna(aggregate), None).to_dict(orient="records")
    full_rows = full_sample.replace([np.inf, -np.inf], np.nan).where(pd.notna(full_sample), None).to_dict(orient="records")
    return (
        "你是NQ 1分钟策略研究员。我们已经先做行情特征发现，现在把top特征转成策略模板回测。"
        "请不要只看胜率或PF，也不要把本结果当成实盘结论。任务是判断哪些模板值得下一轮改造，"
        "哪些失败说明结构需要更强确认、不同止损或不同退出。\n\n"
        "Return ONLY JSON with keys: template_rankings, failure_modes, next_modifications, risk_notes, summary. "
        "template_rankings should include template, verdict, reason, improvement. "
        "next_modifications should be concrete strategy changes to test next.\n\n"
        f"CONFIG: {json.dumps(vars(args), ensure_ascii=False, sort_keys=True, default=str)}\n\n"
        f"WALK_FORWARD_AGGREGATE: {json.dumps(aggregate_rows, ensure_ascii=False, sort_keys=True, default=str)}\n\n"
        f"FULL_SAMPLE_TOP: {json.dumps(full_rows, ensure_ascii=False, sort_keys=True, default=str)}"
    )


def fallback_review(aggregate: pd.DataFrame, full_sample: pd.DataFrame) -> dict[str, Any]:
    rankings = []
    for _, row in aggregate.head(10).iterrows():
        rankings.append(
            {
                "template": str(row["template"]),
                "verdict": "research",
                "reason": (
                    f"selected_folds={int(row['selected_folds'])}, test_trades={int(row['test_trades'])}, "
                    f"net={float(row['test_net_points']):.2f}, avg={float(row['test_avg_points']):.3f}, "
                    f"positive_fold_rate={float(row['positive_test_fold_rate']):.2%}."
                ),
                "improvement": "Compare stronger confirmation, retest entry, structure stop, and partial/time exits.",
            }
        )
    return {
        "status": "fallback",
        "provider": "rule",
        "model": "template_fallback",
        "template_rankings": rankings,
        "failure_modes": [
            "Large MAE after valid market-feature events means raw feature timing is not enough.",
            "Templates selected on net only can still hide poor fold stability.",
        ],
        "next_modifications": [
            "Add second-bar confirmation and failed-retest entries for top W-bottom/absorption features.",
            "Test event-family-specific stops instead of one shared event-extreme stop.",
            "Separate trend-start templates into breakout entry and first-pullback entry cohorts.",
        ],
        "risk_notes": ["Treat this as strategy-shape research; final promotion still needs OOS and paper validation."],
        "summary": "Fallback review ranked strategy templates by walk-forward research score.",
        "full_sample_rows": int(len(full_sample)),
    }


def record_memory(memory_db: Path, aggregate: pd.DataFrame, review: dict[str, Any], args: argparse.Namespace) -> None:
    memory = EvolutionMemory(memory_db)
    try:
        rankings = {
            str(item.get("template")): item
            for item in review.get("template_rankings", [])
            if isinstance(item, dict) and item.get("template")
        }
        now = utc_now()
        for _, row in aggregate.head(args.memory_top_n).iterrows():
            template = str(row["template"])
            ranking = rankings.get(template, {})
            signature = "tmpl_" + hashlib.sha1(template.encode("utf-8")).hexdigest()[:16]
            note_id = f"note_{signature}_strategy_template_{int(row['selected_folds'])}_{int(row['test_trades'])}"
            lesson = (
                f"Strategy template {template}: selected_folds={int(row['selected_folds'])}, "
                f"test_trades={int(row['test_trades'])}, net={float(row['test_net_points']):.2f}, "
                f"avg={float(row['test_avg_points']):.3f}, win_rate={float(row['test_win_rate']):.2%}, "
                f"PF={float(row['test_profit_factor']):.2f}. LLM/verdict={ranking.get('verdict', 'research')}."
            )
            memory.connection.execute(
                """
                INSERT OR REPLACE INTO experience_notes (
                    note_id, rule_signature, note_type, regime, applies_when, avoid_when,
                    lesson, evidence_summary, confidence, status, supersedes_note_id,
                    created_at, last_used_at, use_count
                ) VALUES (?, ?, 'strategy_template', NULL, ?, ?, ?, ?, ?, 'active', NULL, ?, NULL, 0)
                """,
                (
                    note_id,
                    signature,
                    f"Use when feature_id={row['feature_id']} and entry/stop mode matches {row['entry_mode']}/{row['stop_mode']}.",
                    str(ranking.get("improvement", "Avoid promotion until refreshed walk-forward and paper validation pass.")),
                    lesson,
                    json.dumps(row.replace([np.inf, -np.inf], np.nan).dropna().to_dict(), sort_keys=True, default=str),
                    min(1.0, max(0.05, float(row["selected_folds"]) / 8.0)),
                    now,
                ),
            )
        memory.limit_active_notes()
        memory.connection.commit()
    finally:
        memory.close()


def write_report(path: Path, full_sample: pd.DataFrame, aggregate: pd.DataFrame, folds: pd.DataFrame, review: dict[str, Any], args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>NQ Market Feature Strategy Templates</title>
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
  <h1>NQ 行情特征策略模板回测</h1>
  <p class="muted">这是结构到策略的研究层：训练折叠按样本、净值、回撤和稳定性选择模板，胜率/PF只作为观察指标，不作为前置硬门槛。</p>
  <section>
    <span class="metric">Full sample templates: {len(full_sample):,}</span>
    <span class="metric">Walk-forward aggregate rows: {len(aggregate):,}</span>
    <span class="metric">Fold rows: {len(folds):,}</span>
    <span class="metric">Window: {args.start_date} to {args.end_date}</span>
  </section>
  <section>
    <h2>Top Walk-Forward Templates</h2>
    {_html_table(aggregate.head(args.top_n))}
  </section>
  <section>
    <h2>Top Full-Sample Templates</h2>
    {_html_table(full_sample.head(args.top_n))}
  </section>
  <section>
    <h2>LLM / Rule Review</h2>
    <pre>{json.dumps(review, ensure_ascii=False, indent=2, sort_keys=True, default=str)}</pre>
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest strategy templates for discovered NQ market features.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--walk-start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--bars-cache", default=".tmp/nq-market-feature-bars-2020-cache.pkl")
    parser.add_argument("--features-cache", default=".tmp/nq-market-feature-features-2020-cache.pkl")
    parser.add_argument("--source-csv")
    parser.add_argument("--source-zip")
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--rebuild-features", action="store_true")
    parser.add_argument("--feature-summary", default=".tmp/nq-market-feature-summary-2020.csv")
    parser.add_argument("--feature-ids", nargs="+")
    parser.add_argument("--top-features", type=int, default=8)
    parser.add_argument("--entry-modes", nargs="+", default=["next_open", "confirm_break", "midpoint_hold", "pullback_reclaim"])
    parser.add_argument("--stop-modes", nargs="+", default=["event_extreme", "atr"])
    parser.add_argument("--reward-risks", type=float, nargs="+", default=[1.0, 1.5, 2.0])
    parser.add_argument("--horizons", type=int, nargs="+", default=[30, 60, 120])
    parser.add_argument("--confirm-bars", type=int, nargs="+", default=[2, 5])
    parser.add_argument("--pullback-atr", type=float, nargs="+", default=[0.25, 0.50])
    parser.add_argument("--stop-atr-mult", type=float, nargs="+", default=[1.5, 2.0])
    parser.add_argument("--exit-modes", nargs="+", default=["bracket"])
    parser.add_argument("--fast-fail-bars", type=int, nargs="+", default=[5])
    parser.add_argument("--min-gap-minutes", type=int, default=15)
    parser.add_argument("--min-stop-points", type=float, default=4.0)
    parser.add_argument("--max-stop-points", type=float, default=100.0)
    parser.add_argument("--stop-buffer-atr", type=float, default=0.10)
    parser.add_argument("--min-buffer-points", type=float, default=0.25)
    parser.add_argument("--min-full-sample-trades", type=int, default=20)
    parser.add_argument("--train-days", type=int, default=730)
    parser.add_argument("--purge-days", type=int, default=5)
    parser.add_argument("--test-days", type=int, default=180)
    parser.add_argument("--step-days", type=int, default=90)
    parser.add_argument("--min-train-trades", type=int, default=20)
    parser.add_argument("--min-train-net-points", type=float, default=0.0)
    parser.add_argument("--max-fold-candidates", type=int, default=10)
    parser.add_argument("--full-output", default=".tmp/nq-market-feature-template-full-sample-2020.csv")
    parser.add_argument("--fold-output", default=".tmp/nq-market-feature-template-walkforward-2020.csv")
    parser.add_argument("--aggregate-output", default=".tmp/nq-market-feature-template-aggregate-2020.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-market-feature-template-selected-trades-2020.csv")
    parser.add_argument("--llm-output", default=".tmp/nq-market-feature-template-llm-review-2020.json")
    parser.add_argument("--report", default="reports/NQ-market-feature-strategy-template-backtest-2020.html")
    parser.add_argument("--memory-db", default=".tmp/nq-trading-evolution.sqlite")
    parser.add_argument("--record-memory", action="store_true")
    parser.add_argument("--memory-top-n", type=int, default=30)
    parser.add_argument("--review-only", action="store_true", help="Load existing CSV outputs and only refresh LLM review/report/memory.")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--backend-url")
    parser.add_argument("--llm-timeout", type=float, default=90.0)
    parser.add_argument("--llm-top-n", type=int, default=30)
    parser.add_argument("--top-n", type=int, default=50)
    args = parser.parse_args()

    if args.review_only:
        full_sample = pd.read_csv(args.full_output) if Path(args.full_output).exists() else pd.DataFrame()
        folds = pd.read_csv(args.fold_output) if Path(args.fold_output).exists() else pd.DataFrame()
        aggregate = pd.read_csv(args.aggregate_output) if Path(args.aggregate_output).exists() else pd.DataFrame()
        selected_trades = pd.read_csv(args.trades_output) if Path(args.trades_output).exists() else pd.DataFrame()
        feature_ids = (
            aggregate["feature_id"].astype(str).drop_duplicates().tolist()
            if not aggregate.empty and "feature_id" in aggregate.columns
            else []
        )
        features_count = 0
        template_count = int(full_sample["template"].nunique()) if not full_sample.empty and "template" in full_sample.columns else 0
    else:
        features = load_or_prepare_features(args)
        summary = pd.read_csv(args.feature_summary) if Path(args.feature_summary).exists() else pd.DataFrame()
        feature_ids = select_feature_ids(summary, explicit=args.feature_ids, top_features=args.top_features)
        market_features = {feature.feature_id: feature for feature in build_market_features(features)}
        missing = sorted(set(feature_ids) - set(market_features))
        if missing:
            raise ValueError(f"Feature ids not available: {missing}")
        templates = template_pool(
            market_features,
            feature_ids,
            entry_modes=args.entry_modes,
            stop_modes=args.stop_modes,
            reward_risks=args.reward_risks,
            horizons=args.horizons,
            confirm_bars=args.confirm_bars,
            pullback_atr=args.pullback_atr,
            stop_atr_mult=args.stop_atr_mult,
            exit_modes=args.exit_modes,
            fast_fail_bars=args.fast_fail_bars,
        )
        full_sample, trades_by_template = full_sample_results(features, market_features, templates, args)
        folds, aggregate, selected_trades = walk_forward_validate(trades_by_template, templates, args)
        features_count = int(len(features))
        template_count = int(len(templates))
    review = invoke_llm_review(aggregate, full_sample, args)

    if not args.review_only:
        for output_path, frame in [
            (Path(args.full_output), full_sample),
            (Path(args.fold_output), folds),
            (Path(args.aggregate_output), aggregate),
            (Path(args.trades_output), selected_trades),
        ]:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(output_path, index=False)
    llm_output = Path(args.llm_output)
    llm_output.parent.mkdir(parents=True, exist_ok=True)
    llm_output.write_text(json.dumps(review, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")
    write_report(Path(args.report), full_sample, aggregate, folds, review, args)
    if args.record_memory:
        record_memory(Path(args.memory_db), aggregate, review, args)

    result = {
        "feature_rows": features_count,
        "feature_ids": feature_ids,
        "template_count": template_count,
        "full_sample_rows": int(len(full_sample)),
        "fold_rows": int(len(folds)),
        "aggregate_rows": int(len(aggregate)),
        "selected_trade_rows": int(len(selected_trades)),
        "full_output": args.full_output,
        "aggregate_output": args.aggregate_output,
        "report": args.report,
        "llm_status": review.get("status", "unknown"),
        "top_walk_forward": aggregate.iloc[0].to_dict() if not aggregate.empty else None,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
