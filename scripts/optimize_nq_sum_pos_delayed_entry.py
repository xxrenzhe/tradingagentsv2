from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from optimize_nq_sum_pos_market_feature_filters import add_market_features, load_bars, summarize


ROOT_DIR = Path(__file__).resolve().parents[1]
ROUND_TRIP_COST_POINTS = 1.5


@dataclass(frozen=True)
class DelayConfig:
    name: str
    segment: str
    wait_bars: int
    min_improve_atr: float
    stop_buffer_atr: float
    fallback_original: bool


def _max_hold(row: pd.Series) -> int:
    text = str(row.get("component_strategy", ""))
    match = re.search(r"_h(\d+)", text)
    if match:
        return int(match.group(1))
    return 30


def _target_r(row: pd.Series) -> float:
    risk = abs(float(row["entry_price"]) - float(row["initial_stop"]))
    reward = abs(float(row["target"]) - float(row["entry_price"]))
    if risk <= 0:
        return 2.5
    value = reward / risk
    if not np.isfinite(value) or value <= 0:
        return 2.5
    return float(np.clip(value, 0.75, 5.0))


def _segment_mask(trades: pd.DataFrame, segment: str) -> pd.Series:
    if segment == "all":
        return pd.Series(True, index=trades.index)
    if segment == "next_open":
        return trades["entry_mode"].astype(str).eq("next_open")
    if segment == "transition_short_asia_next_open":
        return trades["signal_family"].astype(str).eq("trend_transition_short_asia") & trades["entry_mode"].astype(str).eq("next_open")
    if segment == "transition_long_next_open":
        return trades["signal_family"].astype(str).eq("trend_transition_long") & trades["entry_mode"].astype(str).eq("next_open")
    if segment == "transition_long_micro":
        return trades["signal_family"].astype(str).eq("trend_transition_long") & trades["entry_mode"].astype(str).eq("structure_micro_rr")
    if segment == "transition_long_micro_or_next":
        return trades["signal_family"].astype(str).eq("trend_transition_long") & trades["entry_mode"].astype(str).isin(["structure_micro_rr", "next_open"])
    if segment == "chase_extreme":
        return (
            trades["directional_range_pos_60"].astype(float).ge(0.85)
            | trades["directional_range_pos_120"].astype(float).ge(0.85)
            | trades["dir_ema20_dist"].astype(float).ge(2.0)
        )
    if segment == "short_chase_extreme":
        return trades["direction"].astype(int).lt(0) & (
            trades["directional_range_pos_60"].astype(float).ge(0.85)
            | trades["directional_range_pos_120"].astype(float).ge(0.85)
        )
    if segment == "long_chase_extreme":
        return trades["direction"].astype(int).gt(0) & (
            trades["directional_range_pos_60"].astype(float).ge(0.85)
            | trades["directional_range_pos_120"].astype(float).ge(0.85)
            | trades["dir_ema20_dist"].astype(float).ge(2.0)
        )
    raise ValueError(f"unknown segment: {segment}")


def _find_delayed_entry(row: pd.Series, bars: pd.DataFrame, ts_values: np.ndarray, config: DelayConfig) -> dict[str, object] | None:
    entry_key = pd.DatetimeIndex([pd.Timestamp(row["entry_ts"])]).astype("int64")[0]
    entry_pos = int(np.searchsorted(ts_values, entry_key, side="left"))
    if entry_pos < 0 or entry_pos + 2 >= len(bars):
        return None
    direction = int(row["direction"])
    atr = float(row.get("atr14", np.nan))
    if not np.isfinite(atr) or atr <= 0:
        atr = max(abs(float(row["entry_price"]) - float(row["initial_stop"])), 1.0)
    min_improve = config.min_improve_atr * atr
    stop_buffer = config.stop_buffer_atr * atr
    original_entry = float(row["entry_price"])
    end_pos = min(len(bars) - 2, entry_pos + config.wait_bars)

    for confirm_pos in range(entry_pos + 1, end_pos + 1):
        window = bars.iloc[entry_pos:confirm_pos]
        confirm = bars.iloc[confirm_pos]
        prev = bars.iloc[confirm_pos - 1]
        if direction < 0:
            pullback_high = float(window["High"].max())
            improved = pullback_high >= original_entry + min_improve
            rejected = float(confirm["Close"]) < float(confirm["Open"]) and float(confirm["Close"]) < float(prev["Close"]) and float(confirm["High"]) <= pullback_high + 1e-9
            if improved and rejected:
                entry_bar = bars.iloc[confirm_pos + 1]
                entry_price = float(entry_bar["Open"])
                stop = pullback_high + stop_buffer
                if stop <= entry_price:
                    continue
                risk = stop - entry_price
                target = entry_price - risk * _target_r(row)
                return {
                    "entry_pos": confirm_pos + 1,
                    "entry_ts": pd.Timestamp(entry_bar["ts"]),
                    "entry_price": entry_price,
                    "initial_stop": stop,
                    "target": target,
                    "delay_reason": "short_failed_pullback",
                }
        else:
            pullback_low = float(window["Low"].min())
            improved = pullback_low <= original_entry - min_improve
            rejected = float(confirm["Close"]) > float(confirm["Open"]) and float(confirm["Close"]) > float(prev["Close"]) and float(confirm["Low"]) >= pullback_low - 1e-9
            if improved and rejected:
                entry_bar = bars.iloc[confirm_pos + 1]
                entry_price = float(entry_bar["Open"])
                stop = pullback_low - stop_buffer
                if stop >= entry_price:
                    continue
                risk = entry_price - stop
                target = entry_price + risk * _target_r(row)
                return {
                    "entry_pos": confirm_pos + 1,
                    "entry_ts": pd.Timestamp(entry_bar["ts"]),
                    "entry_price": entry_price,
                    "initial_stop": stop,
                    "target": target,
                    "delay_reason": "long_failed_pullback",
                }
    return None


def _simulate_exit(row: pd.Series, bars: pd.DataFrame, entry_plan: dict[str, object]) -> dict[str, object]:
    direction = int(row["direction"])
    entry_pos = int(entry_plan["entry_pos"])
    entry_price = float(entry_plan["entry_price"])
    stop = float(entry_plan["initial_stop"])
    target = float(entry_plan["target"])
    max_hold = _max_hold(row)
    end_pos = min(len(bars) - 1, entry_pos + max_hold)
    exit_pos = end_pos
    exit_price = float(bars.iloc[end_pos]["Close"])
    exit_reason = "delay_max_hold"
    for pos in range(entry_pos + 1, end_pos + 1):
        bar = bars.iloc[pos]
        high = float(bar["High"])
        low = float(bar["Low"])
        if direction > 0:
            if low <= stop:
                exit_pos = pos
                exit_price = stop
                exit_reason = "delay_stop"
                break
            if high >= target:
                exit_pos = pos
                exit_price = target
                exit_reason = "delay_target"
                break
        else:
            if high >= stop:
                exit_pos = pos
                exit_price = stop
                exit_reason = "delay_stop"
                break
            if low <= target:
                exit_pos = pos
                exit_price = target
                exit_reason = "delay_target"
                break
    gross = (exit_price - entry_price) * direction
    return {
        "exit_ts": pd.Timestamp(bars.iloc[exit_pos]["ts"]),
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "bars_held": int(exit_pos - entry_pos),
        "gross_points": gross,
        "net_points": gross - ROUND_TRIP_COST_POINTS,
    }


def apply_delay_config(trades: pd.DataFrame, bars: pd.DataFrame, config: DelayConfig) -> pd.DataFrame:
    ts_values = pd.to_datetime(bars["ts"], utc=True).astype("int64").to_numpy()
    segment = _segment_mask(trades, config.segment)
    rows: list[dict[str, object]] = []
    for idx, row in trades.iterrows():
        output = row.to_dict()
        if not bool(segment.loc[idx]):
            output["delay_rule"] = "original_not_in_segment"
            rows.append(output)
            continue
        plan = _find_delayed_entry(row, bars, ts_values, config)
        if plan is None:
            if config.fallback_original:
                output["delay_rule"] = "original_no_pullback"
                rows.append(output)
            continue
        exit_plan = _simulate_exit(row, bars, plan)
        output.update(
            {
                "entry_ts": plan["entry_ts"],
                "entry_price": plan["entry_price"],
                "initial_stop": plan["initial_stop"],
                "target": plan["target"],
                "exit_ts": exit_plan["exit_ts"],
                "exit_price": exit_plan["exit_price"],
                "exit_reason": exit_plan["exit_reason"],
                "bars_held": exit_plan["bars_held"],
                "gross_points": exit_plan["gross_points"],
                "net_points": exit_plan["net_points"],
                "delay_rule": plan["delay_reason"],
            }
        )
        rows.append(output)
    if not rows:
        return pd.DataFrame(columns=trades.columns)
    return pd.DataFrame(rows).sort_values("entry_ts").reset_index(drop=True)


def build_configs(
    *,
    only_segments: set[str] | None = None,
    wait_values: tuple[int, ...] = (4, 6, 8),
    improve_values: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75),
    buffer_values: tuple[float, ...] = (0.0, 0.1, 0.25),
    fallback_values: tuple[bool, ...] = (False, True),
) -> list[DelayConfig]:
    segments = [
        "transition_short_asia_next_open",
        "transition_long_next_open",
        "transition_long_micro",
        "transition_long_micro_or_next",
        "short_chase_extreme",
        "long_chase_extreme",
        "chase_extreme",
    ]
    if only_segments:
        segments = [segment for segment in segments if segment in only_segments]
    configs: list[DelayConfig] = []
    for segment in segments:
        for wait_bars in wait_values:
            for min_improve_atr in improve_values:
                for stop_buffer_atr in buffer_values:
                    for fallback in fallback_values:
                        suffix = "fallback" if fallback else "skip"
                        configs.append(
                            DelayConfig(
                                name=f"{segment}_wait{wait_bars}_improve{min_improve_atr:g}_buf{stop_buffer_atr:g}_{suffix}",
                                segment=segment,
                                wait_bars=wait_bars,
                                min_improve_atr=min_improve_atr,
                                stop_buffer_atr=stop_buffer_atr,
                                fallback_original=fallback,
                            )
                        )
    return configs


def evaluate(trades: pd.DataFrame, bars: pd.DataFrame, configs: list[DelayConfig]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    baseline = summarize(trades)
    rows = []
    outputs: dict[str, pd.DataFrame] = {}
    for config in configs:
        result = apply_delay_config(trades, bars, config)
        if result.empty or len(result) < 500:
            continue
        summary = summarize(result)
        changed = result.get("delay_rule", pd.Series(dtype=str)).astype(str).isin(["short_failed_pullback", "long_failed_pullback"])
        rows.append(
            {
                "rule": config.name,
                "segment": config.segment,
                "wait_bars": config.wait_bars,
                "min_improve_atr": config.min_improve_atr,
                "stop_buffer_atr": config.stop_buffer_atr,
                "fallback_original": config.fallback_original,
                **summary,
                "changed_trades": int(changed.sum()),
                "net_delta": float(summary["net_points"] - baseline["net_points"]),
                "pf_delta": float(summary["profit_factor"] - baseline["profit_factor"]),
                "dd_delta": float(summary["max_drawdown_points"] - baseline["max_drawdown_points"]),
            }
        )
        outputs[config.name] = result
    ranking = pd.DataFrame(rows).sort_values(["net_points", "profit_factor"], ascending=False)
    return ranking, outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize delayed pullback/retest entry rules for sum_pos_open2 candidate.")
    parser.add_argument("--trades", default="reports/NQ-pine-12m-sum_pos-open2-second-pass-entry-exit-optimized-trades.csv")
    parser.add_argument("--bars-cache", default=".tmp/nq-pine-combo-trailing-12m-bars.pkl")
    parser.add_argument("--ranking-output", default="reports/NQ-pine-12m-sum_pos-open2-delayed-entry-ranking.csv")
    parser.add_argument("--best-output", default="reports/NQ-pine-12m-sum_pos-open2-delayed-entry-best-trades.csv")
    parser.add_argument("--segments", nargs="*", default=None)
    parser.add_argument("--wait-bars", nargs="*", type=int, default=[4, 6, 8])
    parser.add_argument("--improve-atrs", nargs="*", type=float, default=[0.0, 0.25, 0.5, 0.75])
    parser.add_argument("--stop-buffer-atrs", nargs="*", type=float, default=[0.0, 0.1, 0.25])
    parser.add_argument("--fallback", choices=["skip", "fallback", "both"], default="both")
    args = parser.parse_args()

    trades = pd.read_csv(ROOT_DIR / args.trades)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True).astype("datetime64[ns, UTC]")
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True).astype("datetime64[ns, UTC]")
    bars = add_market_features(load_bars(ROOT_DIR / args.bars_cache))
    fallback_values = (False, True) if args.fallback == "both" else ((True,) if args.fallback == "fallback" else (False,))
    configs = build_configs(
        only_segments=set(args.segments) if args.segments else None,
        wait_values=tuple(args.wait_bars),
        improve_values=tuple(args.improve_atrs),
        buffer_values=tuple(args.stop_buffer_atrs),
        fallback_values=fallback_values,
    )
    ranking, outputs = evaluate(trades, bars, configs)
    ranking_path = ROOT_DIR / args.ranking_output
    best_path = ROOT_DIR / args.best_output
    ranking.to_csv(ranking_path, index=False)
    best_rule = str(ranking.iloc[0]["rule"])
    outputs[best_rule].to_csv(best_path, index=False)
    print(f"best_rule {best_rule}")
    print(f"wrote {ranking_path}")
    print(f"wrote {best_path}")
    print(ranking.head(30).to_string(index=False))


if __name__ == "__main__":
    main()
