from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import sqrt
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class BacktestCosts:
    point_value: float = 20.0
    tick_size: float = 0.25
    slippage_ticks_per_side: float = 1.0
    commission_per_contract: float = 2.5

    @property
    def round_trip_cost_points(self) -> float:
        slippage_points = self.tick_size * self.slippage_ticks_per_side * 2
        commission_points = self.commission_per_contract / self.point_value
        return slippage_points + commission_points


@dataclass(frozen=True)
class StrategySpec:
    name: str
    family: str
    lookback: int
    threshold: float
    holding_minutes: int
    imbalance_threshold: float | None = None
    max_spread_quantile: float | None = None
    min_depth_quantile: float | None = None
    stop_loss_points: float | None = None
    take_profit_points: float | None = None


def prepare_minute_features(bars: pd.DataFrame, microstructure: pd.DataFrame | None = None) -> pd.DataFrame:
    data = bars.copy()
    if "Date" in data.columns:
        data["ts"] = pd.to_datetime(data["Date"], utc=True)
    elif "ts_event" in data.columns:
        data["ts"] = pd.to_datetime(data["ts_event"], utc=True)
    else:
        raise ValueError("bars must include Date or ts_event")

    rename = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    data = data.rename(columns={k: v for k, v in rename.items() if k in data.columns})
    data = data.sort_values("ts").drop_duplicates("ts")
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data["return_1m"] = data["Close"].pct_change()
    data["vwap"] = (data["Close"] * data["Volume"]).cumsum() / data["Volume"].replace(0, pd.NA).cumsum()
    data["minute_of_day"] = data["ts"].dt.hour * 60 + data["ts"].dt.minute

    if microstructure is not None and not microstructure.empty:
        micro = microstructure.copy()
        micro["ts_event"] = pd.to_datetime(micro["ts_event"], utc=True)
        numeric_columns = ["bid_px_00", "ask_px_00", "bid_sz_00", "ask_sz_00"]
        for column in numeric_columns:
            micro[column] = pd.to_numeric(micro[column], errors="coerce")
        micro = micro.dropna(subset=numeric_columns)
        if not micro.empty:
            micro["mid_price"] = (micro["bid_px_00"] + micro["ask_px_00"]) / 2
            micro["spread"] = micro["ask_px_00"] - micro["bid_px_00"]
            total_size = micro["bid_sz_00"] + micro["ask_sz_00"]
            micro["imbalance"] = (micro["bid_sz_00"] - micro["ask_sz_00"]) / total_size.replace(0, pd.NA)
            micro["depth"] = total_size
            aggregated = (
                micro.set_index("ts_event")
                .resample("1min")
                .agg(
                    mid_price=("mid_price", "last"),
                    spread_mean=("spread", "mean"),
                    imbalance_mean=("imbalance", "mean"),
                    imbalance_last=("imbalance", "last"),
                    depth_mean=("depth", "mean"),
                    quote_count=("mid_price", "count"),
                )
                .reset_index()
                .rename(columns={"ts_event": "ts"})
            )
            data = data.merge(aggregated, on="ts", how="left")

    for column in ["spread_mean", "imbalance_mean", "imbalance_last", "depth_mean", "quote_count"]:
        if column not in data.columns:
            data[column] = pd.NA

    return data.reset_index(drop=True)


def generate_strategy_specs(include_microstructure: bool = True) -> list[StrategySpec]:
    specs: list[StrategySpec] = []
    families = {
        "momentum": [0.0003, 0.0006, 0.0010],
        "mean_reversion": [0.6, 1.0, 1.4],
        "breakout": [0.0],
        "vwap_reclaim": [0.0002, 0.0005],
    }
    for family, thresholds in families.items():
        for lookback, threshold, holding_minutes in product([3, 5, 10, 15], thresholds, [3, 5, 10, 15]):
            risk_profiles = [(None, None), (8.0, 16.0), (12.0, 24.0), (16.0, 32.0)]
            for stop_loss, take_profit in risk_profiles:
                risk_suffix = "" if stop_loss is None else f"_sl{stop_loss:g}_tp{take_profit:g}"
                specs.append(
                    StrategySpec(
                        name=f"{family}_lb{lookback}_thr{threshold}_hold{holding_minutes}{risk_suffix}",
                        family=family,
                        lookback=lookback,
                        threshold=threshold,
                        holding_minutes=holding_minutes,
                        stop_loss_points=stop_loss,
                        take_profit_points=take_profit,
                    )
                )
                if include_microstructure:
                    for imbalance_threshold in [0.1, 0.2, 0.35]:
                        specs.append(
                            StrategySpec(
                                name=(
                                    f"{family}_lb{lookback}_thr{threshold}_hold{holding_minutes}"
                                    f"_imb{imbalance_threshold}{risk_suffix}"
                                ),
                                family=family,
                                lookback=lookback,
                                threshold=threshold,
                                holding_minutes=holding_minutes,
                                imbalance_threshold=imbalance_threshold,
                                max_spread_quantile=0.75,
                                min_depth_quantile=0.25,
                                stop_loss_points=stop_loss,
                                take_profit_points=take_profit,
                            )
                        )
    return specs


def _base_signal(features: pd.DataFrame, spec: StrategySpec) -> pd.Series:
    close = features["Close"]
    if spec.family == "momentum":
        momentum = close.pct_change(spec.lookback)
        return ((momentum > spec.threshold).astype(int) - (momentum < -spec.threshold).astype(int)).astype(float)

    if spec.family == "mean_reversion":
        rolling_mean = close.rolling(spec.lookback).mean()
        rolling_std = close.rolling(spec.lookback).std().replace(0, pd.NA)
        z_score = (close - rolling_mean) / rolling_std
        return ((z_score < -spec.threshold).astype(int) - (z_score > spec.threshold).astype(int)).astype(float)

    if spec.family == "breakout":
        prior_high = features["High"].rolling(spec.lookback).max().shift(1)
        prior_low = features["Low"].rolling(spec.lookback).min().shift(1)
        return ((close > prior_high).astype(int) - (close < prior_low).astype(int)).astype(float)

    if spec.family == "vwap_reclaim":
        vwap_distance = (close - features["vwap"]) / features["vwap"]
        momentum = close.pct_change(spec.lookback)
        long_signal = (vwap_distance > spec.threshold) & (momentum > 0)
        short_signal = (vwap_distance < -spec.threshold) & (momentum < 0)
        return (long_signal.astype(int) - short_signal.astype(int)).astype(float)

    raise ValueError(f"Unknown strategy family: {spec.family}")


def _apply_microstructure_filters(signal: pd.Series, features: pd.DataFrame, spec: StrategySpec) -> pd.Series:
    filtered = signal.copy()
    if spec.imbalance_threshold is not None:
        imbalance = pd.to_numeric(features["imbalance_last"].fillna(features["imbalance_mean"]), errors="coerce")
        aligned = ((filtered > 0) & (imbalance >= spec.imbalance_threshold)) | (
            (filtered < 0) & (imbalance <= -spec.imbalance_threshold)
        )
        filtered = filtered.where(aligned, 0)

    if spec.max_spread_quantile is not None and features["spread_mean"].notna().any():
        spread_limit = pd.to_numeric(features["spread_mean"], errors="coerce").quantile(spec.max_spread_quantile)
        filtered = filtered.where(pd.to_numeric(features["spread_mean"], errors="coerce") <= spread_limit, 0)

    if spec.min_depth_quantile is not None and features["depth_mean"].notna().any():
        depth_floor = pd.to_numeric(features["depth_mean"], errors="coerce").quantile(spec.min_depth_quantile)
        filtered = filtered.where(pd.to_numeric(features["depth_mean"], errors="coerce") >= depth_floor, 0)

    return filtered.fillna(0)


def build_trades(features: pd.DataFrame, spec: StrategySpec, costs: BacktestCosts | None = None) -> pd.DataFrame:
    costs = costs or BacktestCosts()
    data = features.copy()
    signal = _apply_microstructure_filters(_base_signal(data, spec), data, spec)
    signal = signal.where(signal != signal.shift(1), 0)

    entries = data.loc[signal != 0, ["ts", "Open", "High", "Low", "Close"]].copy()
    if entries.empty:
        return pd.DataFrame(
            columns=[
                "entry_ts",
                "exit_ts",
                "exit_reason",
                "direction",
                "entry_price",
                "exit_price",
                "gross_points",
                "net_points",
                "net_dollars",
                "entry_index",
                "exit_index",
            ]
        )

    rows = []
    next_available_index = 0
    for entry_index, entry in entries.iterrows():
        if entry_index < next_available_index:
            continue
        exit_index = entry_index + spec.holding_minutes
        if exit_index >= len(data):
            continue
        entry_price = data.at[entry_index + 1, "Open"] if entry_index + 1 < len(data) else entry["Close"]
        direction = float(signal.at[entry_index])
        exit_price = data.at[exit_index, "Close"]
        exit_reason = "time"
        realized_exit_index = exit_index

        if spec.stop_loss_points is not None or spec.take_profit_points is not None:
            stop_price = None
            target_price = None
            if spec.stop_loss_points is not None:
                stop_price = entry_price - spec.stop_loss_points if direction > 0 else entry_price + spec.stop_loss_points
            if spec.take_profit_points is not None:
                target_price = entry_price + spec.take_profit_points if direction > 0 else entry_price - spec.take_profit_points

            for path_index in range(entry_index + 1, exit_index + 1):
                high = data.at[path_index, "High"]
                low = data.at[path_index, "Low"]
                if direction > 0:
                    stop_hit = stop_price is not None and low <= stop_price
                    target_hit = target_price is not None and high >= target_price
                else:
                    stop_hit = stop_price is not None and high >= stop_price
                    target_hit = target_price is not None and low <= target_price

                if stop_hit:
                    exit_price = stop_price
                    exit_reason = "stop_loss"
                    realized_exit_index = path_index
                    break
                if target_hit:
                    exit_price = target_price
                    exit_reason = "take_profit"
                    realized_exit_index = path_index
                    break

        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points
        rows.append(
            {
                "entry_ts": data.at[entry_index, "ts"],
                "exit_ts": data.at[realized_exit_index, "ts"],
                "exit_reason": exit_reason,
                "direction": int(direction),
                "entry_price": float(entry_price),
                "exit_price": float(exit_price),
                "gross_points": float(gross_points),
                "net_points": float(net_points),
                "net_dollars": float(net_points * costs.point_value),
                "entry_index": int(entry_index),
                "exit_index": int(realized_exit_index),
            }
        )
        next_available_index = realized_exit_index + 1
    return pd.DataFrame(rows)


def summarize_trades(spec: StrategySpec, trades: pd.DataFrame, costs: BacktestCosts | None = None) -> dict:
    costs = costs or BacktestCosts()
    if trades.empty:
        return {
            "name": spec.name,
            "family": spec.family,
            "trades": 0,
            "net_points": 0.0,
            "net_dollars": 0.0,
            "max_drawdown_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_points": 0.0,
            "tail_loss_p05": 0.0,
            "worst_trade_points": 0.0,
            "median_points": 0.0,
            "first_half_points": 0.0,
            "second_half_points": 0.0,
            "stability": 0.0,
            "score": 0.0,
        }

    net = trades["net_points"]
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    wins = net[net > 0]
    losses = net[net < 0]
    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())
    profit_factor = float(gross_profit / gross_loss) if gross_loss else float("inf")
    max_drawdown = float(abs(drawdown.min()))
    tail_loss = float(net.quantile(0.05))
    worst_trade = float(net.min())
    median_points = float(net.median())
    avg_points = float(net.mean())
    trade_count = int(len(trades))
    split_index = int(trades["entry_index"].median()) if "entry_index" in trades.columns else int(len(trades) / 2)
    first_half = net[trades["entry_index"] <= split_index] if "entry_index" in trades.columns else net.iloc[:split_index]
    second_half = net[trades["entry_index"] > split_index] if "entry_index" in trades.columns else net.iloc[split_index:]
    first_half_points = float(first_half.sum()) if not first_half.empty else 0.0
    second_half_points = float(second_half.sum()) if not second_half.empty else 0.0
    if first_half_points > 0 and second_half_points > 0:
        stability = float(min(first_half_points, second_half_points) / max(first_half_points, second_half_points))
    elif first_half_points + second_half_points > 0:
        stability = 0.25
    else:
        stability = 0.0
    risk_denominator = max(max_drawdown, abs(tail_loss), 1.0)
    score = float((equity.iloc[-1] / risk_denominator) * sqrt(min(trade_count, 100) / 100) * (0.75 + 0.25 * stability))

    return {
        "name": spec.name,
        "family": spec.family,
        "trades": trade_count,
        "net_points": float(equity.iloc[-1]),
        "net_dollars": float(equity.iloc[-1] * costs.point_value),
        "max_drawdown_points": max_drawdown,
        "profit_factor": profit_factor,
        "win_rate": float((net > 0).mean()),
        "avg_points": avg_points,
        "tail_loss_p05": tail_loss,
        "worst_trade_points": worst_trade,
        "median_points": median_points,
        "first_half_points": first_half_points,
        "second_half_points": second_half_points,
        "stability": stability,
        "score": score,
    }


def evaluate_strategies(
    features: pd.DataFrame,
    specs: Iterable[StrategySpec] | None = None,
    costs: BacktestCosts | None = None,
    min_trades: int = 5,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    specs = list(specs or generate_strategy_specs(features["imbalance_last"].notna().any()))
    summaries = []
    trades_by_name = {}
    for spec in specs:
        trades = build_trades(features, spec, costs)
        summary = summarize_trades(spec, trades, costs)
        if summary["trades"] >= min_trades:
            summaries.append(summary)
            trades_by_name[spec.name] = trades

    if not summaries:
        return pd.DataFrame(), trades_by_name

    results = pd.DataFrame(summaries)
    results = results.sort_values(
        ["score", "net_points", "profit_factor", "max_drawdown_points"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    return results, trades_by_name
