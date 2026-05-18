from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from optimize_nq_sum_pos_market_feature_filters import add_market_features, load_bars, summarize


ROOT_DIR = Path(__file__).resolve().parents[1]
ROUND_TRIP_COST_POINTS = 1.5


@dataclass(frozen=True)
class ExitRule:
    name: str
    segment_fn: Callable[[pd.Series], bool]
    stop_r: float | None = None
    time_bars: int | None = None
    time_min_r: float | None = None
    adverse_ema: bool = False
    adverse_mom15: float | None = None


def _segment_all(_: pd.Series) -> bool:
    return True


def _segment_micro(row: pd.Series) -> bool:
    return str(row.get("entry_mode")) == "structure_micro_rr"


def _segment_micro_trend_transition(row: pd.Series) -> bool:
    return str(row.get("entry_mode")) == "structure_micro_rr" and str(row.get("signal_family")) == "trend_transition_long"


def _segment_next_open(row: pd.Series) -> bool:
    return str(row.get("entry_mode")) == "next_open"


def _segment_next_open_trend_pullback(row: pd.Series) -> bool:
    return str(row.get("entry_mode")) == "next_open" and str(row.get("signal_family")) == "trend_pullback_long"


def _segment_smc_discount(row: pd.Series) -> bool:
    return str(row.get("signal_family")) == "smc_discount_choch_long"


def build_rules() -> list[ExitRule]:
    rules = [ExitRule("baseline_original_exit", _segment_all)]
    segments = [
        ("micro", _segment_micro),
        ("micro_ttl", _segment_micro_trend_transition),
        ("next_open", _segment_next_open),
        ("next_open_tpl", _segment_next_open_trend_pullback),
        ("smc_discount", _segment_smc_discount),
    ]
    for segment_name, segment_fn in segments:
        for stop_r in (0.35, 0.5, 0.65, 0.8):
            rules.append(ExitRule(f"{segment_name}_close_adverse_{stop_r:g}r", segment_fn, stop_r=stop_r))
        for bars in (3, 5, 8, 12, 16):
            for min_r in (-0.5, -0.25, 0.0, 0.25):
                rules.append(ExitRule(f"{segment_name}_tstop{bars}_min{min_r:g}r", segment_fn, time_bars=bars, time_min_r=min_r))
        for threshold in (-1.0, -0.5, 0.0):
            rules.append(ExitRule(f"{segment_name}_ema_adverse_mom15_{threshold:g}", segment_fn, adverse_ema=True, adverse_mom15=threshold))
    return rules


def _current_r(row: pd.Series, close_price: float) -> float:
    risk = max(abs(float(row["entry_price"]) - float(row["initial_stop"])), 0.25)
    return (close_price - float(row["entry_price"])) * int(row["direction"]) / risk


def _exit_price_for_close(row: pd.Series, close_price: float) -> tuple[float, float]:
    gross = (close_price - float(row["entry_price"])) * int(row["direction"])
    return close_price, gross - ROUND_TRIP_COST_POINTS


def replay_with_rule(trades: pd.DataFrame, bars: pd.DataFrame, rule: ExitRule) -> pd.DataFrame:
    if rule.name == "baseline_original_exit":
        output = trades.copy()
        output["exit_rule"] = "original"
        output["rule_exit_ts"] = output["exit_ts"]
        output["rule_exit_price"] = output["exit_price"]
        output["rule_net_points"] = output["net_points"]
        output["rule_bars_held"] = output["bars_held"]
        return output

    ts_values = pd.to_datetime(bars["ts"], utc=True).astype("int64").to_numpy()
    rows: list[dict[str, object]] = []
    for _, row in trades.iterrows():
        new_row = row.to_dict()
        original_net = float(row["net_points"])
        original_exit_ts = pd.Timestamp(row["exit_ts"])
        original_exit_price = float(row["exit_price"])
        original_bars = int(row["bars_held"])

        if not rule.segment_fn(row):
            new_row.update(
                {
                    "exit_rule": "original_not_in_segment",
                    "rule_exit_ts": original_exit_ts,
                    "rule_exit_price": original_exit_price,
                    "rule_net_points": original_net,
                    "rule_bars_held": original_bars,
                }
            )
            rows.append(new_row)
            continue

        entry_ts = pd.Timestamp(row["entry_ts"])
        entry_key = pd.DatetimeIndex([entry_ts]).astype("int64")[0]
        exit_key = pd.DatetimeIndex([original_exit_ts]).astype("int64")[0]
        entry_pos = int(np.searchsorted(ts_values, entry_key, side="left"))
        exit_pos = int(np.searchsorted(ts_values, exit_key, side="right") - 1)
        if entry_pos < 0 or exit_pos <= entry_pos:
            new_row.update(
                {
                    "exit_rule": "original_no_path",
                    "rule_exit_ts": original_exit_ts,
                    "rule_exit_price": original_exit_price,
                    "rule_net_points": original_net,
                    "rule_bars_held": original_bars,
                }
            )
            rows.append(new_row)
            continue

        selected_reason = "original"
        selected_ts = original_exit_ts
        selected_price = original_exit_price
        selected_net = original_net
        selected_bars = original_bars
        for path_pos in range(entry_pos + 1, exit_pos + 1):
            bar = bars.iloc[path_pos]
            bars_held = path_pos - entry_pos
            close_price = float(bar["Close"])
            current_r = _current_r(row, close_price)
            direction = int(row["direction"])

            should_exit = False
            reason = ""
            if rule.stop_r is not None and current_r <= -float(rule.stop_r):
                should_exit = True
                reason = f"close_adverse_{rule.stop_r:g}r"
            if not should_exit and rule.time_bars is not None and bars_held >= int(rule.time_bars) and current_r < float(rule.time_min_r):
                should_exit = True
                reason = f"time_stop_{rule.time_bars}_min_{rule.time_min_r:g}r"
            if not should_exit and rule.adverse_ema:
                trend_stack = int(bar.get("trend_stack", 0))
                mom15 = float(bar.get("mom_15_atr", np.nan)) * direction
                if trend_stack * direction < 0 and np.isfinite(mom15) and mom15 <= float(rule.adverse_mom15):
                    should_exit = True
                    reason = f"ema_adverse_mom15_{rule.adverse_mom15:g}"

            if should_exit:
                exit_price, net_points = _exit_price_for_close(row, close_price)
                selected_reason = reason
                selected_ts = pd.Timestamp(bar["ts"])
                selected_price = exit_price
                selected_net = net_points
                selected_bars = bars_held
                break

        new_row.update(
            {
                "exit_rule": selected_reason,
                "rule_exit_ts": selected_ts,
                "rule_exit_price": selected_price,
                "rule_net_points": selected_net,
                "rule_bars_held": selected_bars,
            }
        )
        rows.append(new_row)

    return pd.DataFrame(rows).sort_values("entry_ts").reset_index(drop=True)


def evaluate_rules(trades: pd.DataFrame, bars: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    rows = []
    outputs: dict[str, pd.DataFrame] = {}
    baseline = summarize(trades.rename(columns={"net_points": "net_points"}))
    for rule in build_rules():
        replay = replay_with_rule(trades, bars, rule)
        metrics_frame = replay.copy()
        metrics_frame["net_points"] = metrics_frame["rule_net_points"]
        summary = summarize(metrics_frame)
        changed = replay["exit_rule"].astype(str).ne("original") & replay["exit_rule"].astype(str).ne("original_not_in_segment") & replay["exit_rule"].astype(str).ne("original_no_path")
        rows.append(
            {
                "rule": rule.name,
                **summary,
                "changed_trades": int(changed.sum()),
                "net_delta": float(summary["net_points"] - baseline["net_points"]),
                "pf_delta": float(summary["profit_factor"] - baseline["profit_factor"]),
                "dd_delta": float(summary["max_drawdown_points"] - baseline["max_drawdown_points"]),
            }
        )
        outputs[rule.name] = replay
    ranking = pd.DataFrame(rows).sort_values(["net_points", "profit_factor"], ascending=False)
    return ranking, outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay causal early-exit rules on optimized sum_pos_open2 trades.")
    parser.add_argument("--trades", default="reports/NQ-pine-12m-sum_pos-open2-market-feature-optimized-trades.csv")
    parser.add_argument("--bars-cache", default=".tmp/nq-pine-combo-trailing-12m-bars.pkl")
    parser.add_argument("--ranking-output", default="reports/NQ-pine-12m-sum_pos-open2-exit-rule-ranking.csv")
    parser.add_argument("--best-output", default="reports/NQ-pine-12m-sum_pos-open2-exit-optimized-trades.csv")
    args = parser.parse_args()

    trades = pd.read_csv(ROOT_DIR / args.trades)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True).astype("datetime64[ns, UTC]")
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True).astype("datetime64[ns, UTC]")
    bars = add_market_features(load_bars(ROOT_DIR / args.bars_cache))
    ranking, outputs = evaluate_rules(trades, bars)
    best_rule = str(ranking.iloc[0]["rule"])
    best = outputs[best_rule].copy()

    ranking_path = ROOT_DIR / args.ranking_output
    best_path = ROOT_DIR / args.best_output
    ranking.to_csv(ranking_path, index=False)
    export = best.copy()
    export["exit_ts"] = export["rule_exit_ts"]
    export["exit_price"] = export["rule_exit_price"]
    export["net_points"] = export["rule_net_points"]
    export["gross_points"] = (export["exit_price"].astype(float) - export["entry_price"].astype(float)) * export["direction"].astype(int)
    export["bars_held"] = export["rule_bars_held"]
    export["exit_reason"] = "rule_" + export["exit_rule"].astype(str)
    export.to_csv(best_path, index=False)
    print(f"best_rule {best_rule}")
    print(f"wrote {ranking_path}")
    print(f"wrote {best_path}")
    print(ranking.head(30).to_string(index=False))


if __name__ == "__main__":
    main()
