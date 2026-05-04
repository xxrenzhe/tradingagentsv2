from __future__ import annotations

import argparse
from dataclasses import dataclass
from math import sqrt
from pathlib import Path

import pandas as pd

from tradingagents.backtesting.short_patterns import BacktestCosts


SESSIONS = {
    "all": (0, 24 * 60),
    "asia": (0, 7 * 60),
    "europe": (7 * 60, 13 * 60 + 30),
    "us_rth": (13 * 60 + 30, 20 * 60),
    "us_late": (20 * 60, 24 * 60),
}


@dataclass(frozen=True)
class AdvancedStrategySpec:
    name: str
    family: str
    lookback: int
    threshold: float
    min_hold: int
    max_hold: int
    exit_mode: str
    session: str
    volatility_filter: str
    imbalance_threshold: float | None
    max_spread_quantile: float | None
    min_depth_quantile: float | None
    stop_loss_points: float | None
    take_profit_points: float | None


def _load_features(path: Path) -> pd.DataFrame:
    cache = pd.read_pickle(path)
    frames = [frame for frame in cache.values() if isinstance(frame, pd.DataFrame) and not frame.empty]
    if not frames:
        raise SystemExit(f"No feature frames found in {path}")
    features = pd.concat(frames, ignore_index=True).sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    features["ts"] = pd.to_datetime(features["ts"], utc=True)
    features["return_1m"] = pd.to_numeric(features["Close"], errors="coerce").pct_change()
    features["realized_vol_30"] = features["return_1m"].rolling(30).std()
    return features


def _base_signal(features: pd.DataFrame, spec: AdvancedStrategySpec) -> pd.Series:
    close = pd.to_numeric(features["Close"], errors="coerce")
    if spec.family == "momentum":
        momentum = close.pct_change(spec.lookback)
        return ((momentum > spec.threshold).astype(int) - (momentum < -spec.threshold).astype(int)).astype(float)
    if spec.family == "mean_reversion":
        rolling_mean = close.rolling(spec.lookback).mean()
        rolling_std = close.rolling(spec.lookback).std().replace(0, pd.NA)
        z_score = (close - rolling_mean) / rolling_std
        return ((z_score < -spec.threshold).astype(int) - (z_score > spec.threshold).astype(int)).astype(float)
    if spec.family == "vwap_reclaim":
        vwap_distance = (close - features["vwap"]) / features["vwap"]
        momentum = close.pct_change(spec.lookback)
        return (((vwap_distance > spec.threshold) & (momentum > 0)).astype(int) - ((vwap_distance < -spec.threshold) & (momentum < 0)).astype(int)).astype(float)
    if spec.family == "breakout":
        prior_high = pd.to_numeric(features["High"], errors="coerce").rolling(spec.lookback).max().shift(1)
        prior_low = pd.to_numeric(features["Low"], errors="coerce").rolling(spec.lookback).min().shift(1)
        return ((close > prior_high).astype(int) - (close < prior_low).astype(int)).astype(float)
    raise ValueError(f"Unknown strategy family: {spec.family}")


def _apply_dimension_filters(signal: pd.Series, features: pd.DataFrame, spec: AdvancedStrategySpec) -> pd.Series:
    filtered = signal.copy()
    start_minute, end_minute = SESSIONS[spec.session]
    minute = features["minute_of_day"]
    filtered = filtered.where((minute >= start_minute) & (minute < end_minute), 0)

    if spec.volatility_filter != "all":
        volatility = pd.to_numeric(features["realized_vol_30"], errors="coerce")
        low_cutoff = volatility.quantile(0.33)
        high_cutoff = volatility.quantile(0.67)
        if spec.volatility_filter == "not_low":
            filtered = filtered.where(volatility >= low_cutoff, 0)
        elif spec.volatility_filter == "high":
            filtered = filtered.where(volatility >= high_cutoff, 0)
        elif spec.volatility_filter == "low":
            filtered = filtered.where(volatility <= low_cutoff, 0)
        else:
            raise ValueError(f"Unknown volatility filter: {spec.volatility_filter}")

    if spec.imbalance_threshold is not None:
        imbalance = pd.to_numeric(features["imbalance_last"].fillna(features["imbalance_mean"]), errors="coerce")
        aligned = ((filtered > 0) & (imbalance >= spec.imbalance_threshold)) | (
            (filtered < 0) & (imbalance <= -spec.imbalance_threshold)
        )
        filtered = filtered.where(aligned, 0)
    if spec.max_spread_quantile is not None and features["spread_mean"].notna().any():
        spread = pd.to_numeric(features["spread_mean"], errors="coerce")
        filtered = filtered.where(spread <= spread.quantile(spec.max_spread_quantile), 0)
    if spec.min_depth_quantile is not None and features["depth_mean"].notna().any():
        depth = pd.to_numeric(features["depth_mean"], errors="coerce")
        filtered = filtered.where(depth >= depth.quantile(spec.min_depth_quantile), 0)
    return filtered.fillna(0)


def _should_exit_early(features: pd.DataFrame, spec: AdvancedStrategySpec, direction: float, path_index: int, signal: pd.Series) -> bool:
    if spec.exit_mode == "time":
        return False
    if spec.exit_mode == "reverse":
        return signal.at[path_index] == -direction
    if spec.exit_mode == "reverse_vwap":
        close = features.at[path_index, "Close"]
        vwap = features.at[path_index, "vwap"]
        crossed_vwap = (direction > 0 and close < vwap) or (direction < 0 and close > vwap)
        return crossed_vwap or signal.at[path_index] == -direction
    raise ValueError(f"Unknown exit mode: {spec.exit_mode}")


def build_advanced_trades(features: pd.DataFrame, spec: AdvancedStrategySpec, costs: BacktestCosts | None = None) -> pd.DataFrame:
    costs = costs or BacktestCosts()
    data = features.reset_index(drop=True).copy()
    signal = _apply_dimension_filters(_base_signal(data, spec), data, spec)
    signal = signal.where(signal != signal.shift(1), 0)
    entries = data.loc[signal != 0, ["ts", "Open", "High", "Low", "Close"]]
    rows = []
    next_available_index = 0
    for entry_index, entry in entries.iterrows():
        if entry_index < next_available_index:
            continue
        if entry_index + 1 >= len(data):
            continue
        entry_price = data.at[entry_index + 1, "Open"]
        direction = float(signal.at[entry_index])
        max_exit_index = min(entry_index + spec.max_hold, len(data) - 1)
        exit_index = max_exit_index
        exit_price = data.at[exit_index, "Close"]
        exit_reason = "time"

        for path_index in range(entry_index + 1, max_exit_index + 1):
            high = data.at[path_index, "High"]
            low = data.at[path_index, "Low"]
            if direction > 0:
                stop_hit = spec.stop_loss_points is not None and low <= entry_price - spec.stop_loss_points
                target_hit = spec.take_profit_points is not None and high >= entry_price + spec.take_profit_points
            else:
                stop_hit = spec.stop_loss_points is not None and high >= entry_price + spec.stop_loss_points
                target_hit = spec.take_profit_points is not None and low <= entry_price - spec.take_profit_points
            if stop_hit:
                exit_index = path_index
                exit_price = entry_price - spec.stop_loss_points if direction > 0 else entry_price + spec.stop_loss_points
                exit_reason = "stop_loss"
                break
            if target_hit:
                exit_index = path_index
                exit_price = entry_price + spec.take_profit_points if direction > 0 else entry_price - spec.take_profit_points
                exit_reason = "take_profit"
                break
            if path_index - entry_index >= spec.min_hold and _should_exit_early(data, spec, direction, path_index, signal):
                exit_index = path_index
                exit_price = data.at[path_index, "Close"]
                exit_reason = spec.exit_mode
                break

        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points
        rows.append(
            {
                "entry_ts": data.at[entry_index, "ts"],
                "exit_ts": data.at[exit_index, "ts"],
                "exit_reason": exit_reason,
                "direction": int(direction),
                "entry_price": float(entry_price),
                "exit_price": float(exit_price),
                "gross_points": float(gross_points),
                "net_points": float(net_points),
                "net_dollars": float(net_points * costs.point_value),
                "entry_index": int(entry_index),
                "exit_index": int(exit_index),
                "holding_minutes": int(exit_index - entry_index),
            }
        )
        next_available_index = exit_index + 1
    return pd.DataFrame(rows)


def summarize_advanced_trades(spec: AdvancedStrategySpec, trades: pd.DataFrame, costs: BacktestCosts | None = None) -> dict:
    costs = costs or BacktestCosts()
    base = {
        "name": spec.name,
        "family": spec.family,
        "lookback": spec.lookback,
        "threshold": spec.threshold,
        "min_hold": spec.min_hold,
        "max_hold": spec.max_hold,
        "exit_mode": spec.exit_mode,
        "session": spec.session,
        "volatility_filter": spec.volatility_filter,
        "imbalance_threshold": spec.imbalance_threshold,
        "stop_loss_points": spec.stop_loss_points,
        "take_profit_points": spec.take_profit_points,
    }
    if trades.empty:
        return base | {
            "trades": 0,
            "net_points": 0.0,
            "net_dollars": 0.0,
            "max_drawdown_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_points": 0.0,
            "avg_holding_minutes": 0.0,
            "tail_loss_p05": 0.0,
            "worst_trade_points": 0.0,
            "stability": 0.0,
            "score": 0.0,
            "time_exit_share": 0.0,
            "early_exit_share": 0.0,
        }

    net = trades["net_points"]
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    wins = net[net > 0]
    losses = net[net < 0]
    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())
    max_drawdown = float(abs(drawdown.min()))
    split_index = int(trades["entry_index"].median())
    first_half_points = float(net[trades["entry_index"] <= split_index].sum())
    second_half_points = float(net[trades["entry_index"] > split_index].sum())
    if first_half_points > 0 and second_half_points > 0:
        stability = float(min(first_half_points, second_half_points) / max(first_half_points, second_half_points))
    elif first_half_points + second_half_points > 0:
        stability = 0.25
    else:
        stability = 0.0
    tail_loss = float(net.quantile(0.05))
    trade_count = int(len(trades))
    risk_denominator = max(max_drawdown, abs(tail_loss), 1.0)
    score = float((equity.iloc[-1] / risk_denominator) * sqrt(min(trade_count, 100) / 100) * (0.75 + 0.25 * stability))
    time_exit_share = float((trades["exit_reason"] == "time").mean())
    return base | {
        "trades": trade_count,
        "net_points": float(equity.iloc[-1]),
        "net_dollars": float(equity.iloc[-1] * costs.point_value),
        "max_drawdown_points": max_drawdown,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else float("inf"),
        "win_rate": float((net > 0).mean()),
        "avg_points": float(net.mean()),
        "avg_holding_minutes": float(trades["holding_minutes"].mean()),
        "tail_loss_p05": tail_loss,
        "worst_trade_points": float(net.min()),
        "stability": stability,
        "score": score,
        "time_exit_share": time_exit_share,
        "early_exit_share": 1.0 - time_exit_share,
    }


def generate_advanced_specs() -> list[AdvancedStrategySpec]:
    bases = [
        ("vwap_reclaim", 5, 0.0002),
        ("vwap_reclaim", 5, 0.0005),
        ("vwap_reclaim", 10, 0.0002),
        ("vwap_reclaim", 10, 0.0005),
        ("vwap_reclaim", 15, 0.0002),
        ("vwap_reclaim", 15, 0.0005),
        ("momentum", 5, 0.0006),
        ("momentum", 10, 0.0003),
        ("momentum", 10, 0.0006),
        ("mean_reversion", 3, 0.6),
    ]
    risk_profiles = [(None, None), (12.0, 24.0)]
    specs = []
    for family, lookback, threshold in bases:
        for session in ["all", "asia", "europe", "us_rth"]:
            for volatility_filter in ["all", "not_low", "high"]:
                for exit_mode in ["time", "reverse", "reverse_vwap"]:
                    for min_hold, max_hold in [(1, 5), (1, 10)]:
                        for stop_loss, take_profit in risk_profiles:
                            risk_suffix = "" if stop_loss is None else f"_sl{stop_loss:g}_tp{take_profit:g}"
                            name = (
                                f"adv_{family}_lb{lookback}_thr{threshold}_min{min_hold}_max{max_hold}"
                                f"_{exit_mode}_{session}_{volatility_filter}_imb0.35{risk_suffix}"
                            )
                            specs.append(
                                AdvancedStrategySpec(
                                    name=name,
                                    family=family,
                                    lookback=lookback,
                                    threshold=threshold,
                                    min_hold=min_hold,
                                    max_hold=max_hold,
                                    exit_mode=exit_mode,
                                    session=session,
                                    volatility_filter=volatility_filter,
                                    imbalance_threshold=0.35,
                                    max_spread_quantile=0.75,
                                    min_depth_quantile=0.25,
                                    stop_loss_points=stop_loss,
                                    take_profit_points=take_profit,
                                )
                            )
    return specs


def evaluate_advanced_strategies(features: pd.DataFrame, min_trades: int) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    rows = []
    trades_by_name = {}
    for spec in generate_advanced_specs():
        trades = build_advanced_trades(features, spec)
        summary = summarize_advanced_trades(spec, trades)
        if summary["trades"] >= min_trades:
            rows.append(summary)
            trades_by_name[spec.name] = trades
    if not rows:
        return pd.DataFrame(), trades_by_name
    results = pd.DataFrame(rows).sort_values(
        ["score", "net_points", "profit_factor", "max_drawdown_points"],
        ascending=[False, False, False, True],
    )
    return results.reset_index(drop=True), trades_by_name


def main() -> int:
    parser = argparse.ArgumentParser(description="Explore advanced MBP strategy variants with flexible exits.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/mbp-advanced-patterns.csv")
    parser.add_argument("--trades-output", default=".tmp/mbp-advanced-patterns-trades.csv")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--min-trades", type=int, default=80)
    args = parser.parse_args()

    features = _load_features(Path(args.features_cache))
    print(f"Advanced strategy specs: {len(generate_advanced_specs())}")
    results, trades_by_name = evaluate_advanced_strategies(features, min_trades=args.min_trades)
    if results.empty:
        raise SystemExit("No advanced strategy met the minimum trade count.")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path, index=False)
    best_name = results.iloc[0]["name"]
    trades_path = Path(args.trades_output)
    trades_by_name[best_name].to_csv(trades_path, index=False)

    print(f"Minutes: {len(features)}")
    print(f"Date range: {features['ts'].min()} to {features['ts'].max()}")
    print(f"Advanced strategies meeting min_trades={args.min_trades}: {len(results)}")
    print(f"Results: {output_path}")
    print(f"Best trades: {trades_path}")
    print()
    print(results.head(args.top).to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
