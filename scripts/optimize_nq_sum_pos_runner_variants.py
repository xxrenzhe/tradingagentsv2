from __future__ import annotations

import argparse
import itertools
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from optimize_nq_sum_pos_market_feature_filters import add_market_features, load_bars, summarize


ROOT_DIR = Path(__file__).resolve().parents[1]
ROUND_TRIP_COST_POINTS = 1.5
POINT_VALUE = 20.0


@dataclass(frozen=True)
class RunnerConfig:
    name: str
    target_fraction: float
    extra_bars: int
    trail_atr_mult: float
    lock_r: float
    maxhold_fraction: float = 0.0
    maxhold_min_r: float = 0.75
    maxhold_trend_filter: str = "none"
    eligible_trade_ids: frozenset[str] | None = None


def _to_utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True).astype("datetime64[ns, UTC]")


def _month_labels(series: pd.Series) -> pd.Series:
    # Drop timezone before to_period to avoid noisy pandas warnings; month grouping is UTC-based.
    return _to_utc(series).dt.tz_convert(None).dt.to_period("M").astype(str)


def _bar_positions(bars: pd.DataFrame) -> np.ndarray:
    return pd.to_datetime(bars["ts"], utc=True).astype("int64").to_numpy()


def _position_for_ts(ts_values: np.ndarray, ts: object, *, side: str = "left") -> int:
    key = pd.DatetimeIndex([pd.Timestamp(ts)]).astype("int64")[0]
    return int(np.searchsorted(ts_values, key, side=side))


def _risk_points(row: pd.Series) -> float:
    return max(abs(float(row["entry_price"]) - float(row["initial_stop"])), 0.25)


def _target_hit_pos(
    row: pd.Series,
    bars: pd.DataFrame,
    ts_values: np.ndarray,
    *,
    entry_pos: int,
    original_exit_pos: int,
) -> int | None:
    direction = int(row["direction"])
    target = float(row["target"])
    start = min(len(bars) - 1, entry_pos + 1)
    end = min(len(bars) - 1, max(start, original_exit_pos))
    if direction > 0:
        hits = bars.iloc[start : end + 1]["High"].astype(float).ge(target).to_numpy()
    else:
        hits = bars.iloc[start : end + 1]["Low"].astype(float).le(target).to_numpy()
    if not hits.any():
        return None
    return start + int(np.argmax(hits))


def _passes_maxhold_filter(row: pd.Series, bars: pd.DataFrame, exit_pos: int, config: RunnerConfig) -> bool:
    if config.maxhold_fraction <= 0:
        return False
    if "max_hold" not in str(row.get("exit_reason", "")):
        return False
    risk = _risk_points(row)
    progress_r = float(row["gross_points"]) / risk
    if progress_r < config.maxhold_min_r:
        return False
    if config.maxhold_trend_filter == "none":
        return True
    if exit_pos <= 0 or exit_pos >= len(bars):
        return False
    direction = int(row["direction"])
    bar = bars.iloc[exit_pos]
    trend_stack = int(bar.get("trend_stack", 0))
    mom15 = float(bar.get("mom_15_atr", np.nan)) * direction
    close_ema20 = float(bar.get("close_ema20_atr", np.nan)) * direction
    if config.maxhold_trend_filter == "trend_stack":
        return trend_stack * direction >= 0 and np.isfinite(mom15) and mom15 >= 0
    if config.maxhold_trend_filter == "trend_stack_or_ema":
        return (trend_stack * direction >= 0) or (np.isfinite(close_ema20) and close_ema20 >= 0.25)
    raise ValueError(f"unknown maxhold trend filter: {config.maxhold_trend_filter}")


def _runner_exit(
    row: pd.Series,
    bars: pd.DataFrame,
    *,
    start_pos: int,
    extra_bars: int,
    trail_atr_mult: float,
    lock_r: float,
) -> dict[str, object]:
    direction = int(row["direction"])
    entry_price = float(row["entry_price"])
    risk = _risk_points(row)
    end_pos = min(len(bars) - 1, start_pos + max(int(extra_bars), 1))
    best = float(bars.iloc[start_pos]["High"] if direction > 0 else bars.iloc[start_pos]["Low"])
    exit_pos = end_pos
    exit_price = float(bars.iloc[end_pos]["Close"])
    exit_reason = "runner_time"

    for pos in range(start_pos + 1, end_pos + 1):
        bar = bars.iloc[pos]
        high = float(bar["High"])
        low = float(bar["Low"])
        atr = float(bar.get("atr14", np.nan))
        if not np.isfinite(atr) or atr <= 0:
            atr = risk
        if direction > 0:
            best = max(best, high)
            trail_stop = best - atr * trail_atr_mult
            lock_stop = entry_price + risk * lock_r if (best - entry_price) / risk >= lock_r else -np.inf
            stop = max(trail_stop, lock_stop)
            if low <= stop:
                exit_pos = pos
                exit_price = float(stop)
                exit_reason = "runner_trail"
                break
        else:
            best = min(best, low)
            trail_stop = best + atr * trail_atr_mult
            lock_stop = entry_price - risk * lock_r if (entry_price - best) / risk >= lock_r else np.inf
            stop = min(trail_stop, lock_stop)
            if high >= stop:
                exit_pos = pos
                exit_price = float(stop)
                exit_reason = "runner_trail"
                break
    gross = (exit_price - entry_price) * direction
    return {
        "runner_exit_pos": exit_pos,
        "runner_exit_ts": pd.Timestamp(bars.iloc[exit_pos]["ts"]),
        "runner_exit_price": exit_price,
        "runner_exit_reason": exit_reason,
        "runner_gross_points": gross,
    }


def replay_runner_config(trades: pd.DataFrame, bars: pd.DataFrame, config: RunnerConfig) -> pd.DataFrame:
    ts_values = _bar_positions(bars)
    rows: list[dict[str, object]] = []
    for _, row in trades.iterrows():
        output = row.to_dict()
        output["runner_rule"] = "original"
        output["runner_target_fraction"] = np.nan
        output["runner_exit_ts"] = pd.NaT
        output["runner_exit_price"] = np.nan
        output["runner_gross_points"] = np.nan
        if config.eligible_trade_ids is not None and str(row.get("trade_id", "")) not in config.eligible_trade_ids:
            rows.append(output)
            continue

        entry_pos = _position_for_ts(ts_values, row["entry_ts"], side="left")
        original_exit_pos = _position_for_ts(ts_values, row["exit_ts"], side="right") - 1
        if entry_pos < 0 or entry_pos >= len(bars) or original_exit_pos < entry_pos:
            rows.append(output)
            continue
        if str(bars.iloc[entry_pos].get("symbol", row.get("symbol", ""))) != str(row.get("symbol", "")):
            rows.append(output)
            continue

        target_hit_pos = _target_hit_pos(row, bars, ts_values, entry_pos=entry_pos, original_exit_pos=original_exit_pos)
        scale_pos: int | None = None
        scale_price = np.nan
        target_fraction = float(config.target_fraction)
        runner_rule = ""
        if target_hit_pos is not None and 0.0 <= target_fraction < 1.0:
            scale_pos = target_hit_pos
            scale_price = float(row["target"])
            runner_rule = "target_scaleout"
        elif _passes_maxhold_filter(row, bars, original_exit_pos, config):
            scale_pos = original_exit_pos
            scale_price = float(row["exit_price"])
            target_fraction = float(config.maxhold_fraction)
            runner_rule = "maxhold_profit_runner"

        if scale_pos is None:
            rows.append(output)
            continue

        runner = _runner_exit(
            row,
            bars,
            start_pos=scale_pos,
            extra_bars=config.extra_bars,
            trail_atr_mult=config.trail_atr_mult,
            lock_r=config.lock_r,
        )
        direction = int(row["direction"])
        scale_gross = (float(scale_price) - float(row["entry_price"])) * direction
        runner_gross = float(runner["runner_gross_points"])
        gross = target_fraction * scale_gross + (1.0 - target_fraction) * runner_gross
        net = gross - ROUND_TRIP_COST_POINTS
        exit_pos = int(runner["runner_exit_pos"])
        output.update(
            {
                "exit_ts": runner["runner_exit_ts"],
                "exit_price": float(row["entry_price"]) + gross * direction,
                "exit_reason": (
                    f"{runner_rule}_f{target_fraction:g}_x{config.extra_bars}_"
                    f"trail{config.trail_atr_mult:g}_lock{config.lock_r:g}_{runner['runner_exit_reason']}"
                ),
                "bars_held": int(exit_pos - entry_pos),
                "gross_points": gross,
                "net_points": net,
                "net_dollars": net * POINT_VALUE,
                "runner_rule": runner_rule,
                "runner_target_fraction": target_fraction,
                "runner_exit_ts": runner["runner_exit_ts"],
                "runner_exit_price": runner["runner_exit_price"],
                "runner_gross_points": runner_gross,
            }
        )
        rows.append(output)
    return pd.DataFrame(rows).sort_values("entry_ts").reset_index(drop=True)


def build_configs(profile: str = "full", eligible_trade_ids: frozenset[str] | None = None) -> list[RunnerConfig]:
    if profile == "focused":
        return [
            RunnerConfig(
                name=f"focused_target_runner_f{target_fraction:g}_x{extra_bars}_trail{trail_atr_mult:g}_lock{lock_r:g}",
                target_fraction=target_fraction,
                extra_bars=extra_bars,
                trail_atr_mult=trail_atr_mult,
                lock_r=lock_r,
                eligible_trade_ids=eligible_trade_ids,
            )
            for target_fraction, extra_bars, trail_atr_mult, lock_r in itertools.product(
                [0.35, 0.5],
                [30, 45],
                [1.25, 1.5],
                [1.25, 1.5, 1.75, 2.0],
            )
        ]
    if profile != "full":
        raise ValueError(f"unknown profile: {profile}")
    configs: list[RunnerConfig] = []
    for target_fraction, extra_bars, trail_atr_mult, lock_r in itertools.product(
        [0.0, 0.15, 0.25, 0.35, 0.5],
        [15, 30, 45, 60],
        [1.0, 1.25, 1.5, 1.75, 2.0],
        [1.25, 1.5, 1.75, 2.0],
    ):
        configs.append(
            RunnerConfig(
                name=f"target_runner_f{target_fraction:g}_x{extra_bars}_trail{trail_atr_mult:g}_lock{lock_r:g}",
                target_fraction=target_fraction,
                extra_bars=extra_bars,
                trail_atr_mult=trail_atr_mult,
                lock_r=lock_r,
                eligible_trade_ids=eligible_trade_ids,
            )
        )
    for target_fraction, maxhold_fraction, extra_bars, trail_atr_mult, lock_r, trend_filter in itertools.product(
        [0.25, 0.35, 0.5],
        [0.25, 0.5],
        [30, 60],
        [1.25, 1.5],
        [1.25, 1.5],
        ["trend_stack", "trend_stack_or_ema"],
    ):
        configs.append(
            RunnerConfig(
                name=(
                    f"target_maxhold_runner_tf{target_fraction:g}_mf{maxhold_fraction:g}_x{extra_bars}_"
                    f"trail{trail_atr_mult:g}_lock{lock_r:g}_{trend_filter}"
                ),
                target_fraction=target_fraction,
                extra_bars=extra_bars,
                trail_atr_mult=trail_atr_mult,
                lock_r=lock_r,
                maxhold_fraction=maxhold_fraction,
                maxhold_trend_filter=trend_filter,
                eligible_trade_ids=eligible_trade_ids,
            )
        )
    return configs


def load_eligible_trade_ids(path: Path | None) -> frozenset[str] | None:
    if path is None:
        return None
    frame = pd.read_csv(path)
    if "trade_id" not in frame.columns:
        raise ValueError(f"eligible trades file has no trade_id column: {path}")
    if "exit_reason" in frame.columns:
        mask = frame["exit_reason"].astype(str).str.startswith("scaleout")
        frame = frame.loc[mask].copy()
    ids = frozenset(frame["trade_id"].astype(str).tolist())
    if not ids:
        raise ValueError(f"no eligible trade ids found: {path}")
    return ids


def _changed_count(result: pd.DataFrame) -> int:
    return int(result["runner_rule"].astype(str).ne("original").sum())


def _monthly_net(result: pd.DataFrame) -> dict[str, float]:
    months = _month_labels(result["entry_ts"])
    return result.assign(month=months).groupby("month")["net_points"].sum().to_dict()


def evaluate_configs(
    trades: pd.DataFrame,
    bars: pd.DataFrame,
    configs: list[RunnerConfig],
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    baseline = summarize(trades)
    outputs: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, object]] = []
    for config in configs:
        result = replay_runner_config(trades, bars, config)
        summary = summarize(result)
        monthly = _monthly_net(result)
        rows.append(
            {
                "rule": config.name,
                "target_fraction": config.target_fraction,
                "extra_bars": config.extra_bars,
                "trail_atr_mult": config.trail_atr_mult,
                "lock_r": config.lock_r,
                "maxhold_fraction": config.maxhold_fraction,
                "maxhold_min_r": config.maxhold_min_r,
                "maxhold_trend_filter": config.maxhold_trend_filter,
                **summary,
                "changed_trades": _changed_count(result),
                "positive_months": int(sum(value > 0 for value in monthly.values())),
                "worst_month_points": float(min(monthly.values())) if monthly else 0.0,
                "net_delta": float(summary["net_points"] - baseline["net_points"]),
                "pf_delta": float(summary["profit_factor"] - baseline["profit_factor"]),
                "dd_delta": float(summary["max_drawdown_points"] - baseline["max_drawdown_points"]),
            }
        )
        outputs[config.name] = result
    ranking = pd.DataFrame(rows).sort_values(["net_points", "profit_factor"], ascending=False)
    return ranking, outputs


def walk_forward_selection(ranking: pd.DataFrame, outputs: dict[str, pd.DataFrame], *, top_rules: int = 80) -> pd.DataFrame:
    selected_rules = ranking.head(top_rules)["rule"].astype(str).tolist()
    outputs = {rule: outputs[rule] for rule in selected_rules if rule in outputs}
    all_months = sorted(
        {
            month
            for result in outputs.values()
            for month in _month_labels(result["entry_ts"]).unique().tolist()
        }
    )
    rows: list[dict[str, object]] = []
    for idx in range(3, len(all_months)):
        train_months = set(all_months[:idx])
        test_month = all_months[idx]
        train_rows: list[dict[str, object]] = []
        for rule, result in outputs.items():
            months = _month_labels(result["entry_ts"])
            train = result.loc[months.isin(train_months)].copy()
            if len(train) < 120:
                continue
            summary = summarize(train)
            monthly = train.assign(month=months[months.isin(train_months)].to_numpy()).groupby("month")["net_points"].sum()
            train_rows.append(
                {
                    "rule": rule,
                    "train_net": summary["net_points"],
                    "train_pf": summary["profit_factor"],
                    "train_dd": summary["max_drawdown_points"],
                    "train_worst_month": float(monthly.min()) if len(monthly) else 0.0,
                    "train_positive_months": int((monthly > 0).sum()),
                }
            )
        if not train_rows:
            continue
        train_rank = pd.DataFrame(train_rows)
        train_rank["score"] = (
            train_rank["train_net"]
            + 150.0 * train_rank["train_pf"]
            - 0.35 * train_rank["train_dd"]
            + 0.15 * train_rank["train_worst_month"]
        )
        selected = train_rank.sort_values(["score", "train_net"], ascending=False).iloc[0]
        result = outputs[str(selected["rule"])]
        months = _month_labels(result["entry_ts"])
        test = result.loc[months.eq(test_month)].copy()
        test_summary = summarize(test)
        rows.append(
            {
                "test_month": test_month,
                "selected_rule": str(selected["rule"]),
                "train_net": float(selected["train_net"]),
                "train_pf": float(selected["train_pf"]),
                "train_dd": float(selected["train_dd"]),
                "trades": test_summary["trades"],
                "test_net": test_summary["net_points"],
                "test_pf": test_summary["profit_factor"],
                "test_dd": test_summary["max_drawdown_points"],
                "test_worst": test_summary["worst_trade_points"],
            }
        )
    return pd.DataFrame(rows)


def report_row_for_strategy(strategy: str, trades: pd.DataFrame, notes: str) -> pd.DataFrame:
    summary = summarize(trades)
    return pd.DataFrame(
        [
            {
                "strategy": strategy,
                "families": "sum_pos_open2 third-pass early-exit plus causal runner variants",
                "macd_filter": "mixed / source components",
                "macd_timeframe": 1,
                "stop_atr_buffer": "mixed",
                "target_r": "mixed",
                "max_hold_bars": "mixed",
                **summary,
                "notes": notes,
            }
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize causal runner variants for the NQ sum_pos_open2 candidate.")
    parser.add_argument("--trades", default="reports/NQ-pine-12m-sum_pos-open2-early-exit-small-best-trades.csv")
    parser.add_argument("--bars-cache", default=".tmp/nq-pine-combo-trailing-12m-bars.pkl")
    parser.add_argument("--ranking-output", default="reports/NQ-pine-12m-sum_pos-open2-runner-variant-ranking.csv")
    parser.add_argument("--best-output", default="reports/NQ-pine-12m-sum_pos-open2-runner-variant-best-trades.csv")
    parser.add_argument("--best-ranking-row", default="reports/NQ-pine-12m-sum_pos-open2-runner-variant-ranking-row.csv")
    parser.add_argument("--walk-forward-output", default="reports/NQ-pine-12m-sum_pos-open2-runner-variant-walkforward.csv")
    parser.add_argument("--walk-forward-top-rules", type=int, default=80)
    parser.add_argument("--profile", choices=["focused", "full"], default="focused")
    parser.add_argument(
        "--eligible-trades",
        default=None,
        help="Optional CSV whose trade_id values restrict runner modifications. If exit_reason exists, only scaleout rows are used.",
    )
    args = parser.parse_args()

    trades = pd.read_csv(ROOT_DIR / args.trades)
    trades["entry_ts"] = _to_utc(trades["entry_ts"])
    trades["exit_ts"] = _to_utc(trades["exit_ts"])
    bars = add_market_features(load_bars(ROOT_DIR / args.bars_cache))

    eligible_trade_ids = load_eligible_trade_ids(ROOT_DIR / args.eligible_trades) if args.eligible_trades else None
    configs = build_configs(args.profile, eligible_trade_ids=eligible_trade_ids)
    ranking, outputs = evaluate_configs(trades, bars, configs)
    best_rule = str(ranking.iloc[0]["rule"])
    best = outputs[best_rule]
    wf = walk_forward_selection(ranking, outputs, top_rules=args.walk_forward_top_rules)

    ranking_path = ROOT_DIR / args.ranking_output
    best_path = ROOT_DIR / args.best_output
    row_path = ROOT_DIR / args.best_ranking_row
    wf_path = ROOT_DIR / args.walk_forward_output
    ranking.to_csv(ranking_path, index=False)
    best.to_csv(best_path, index=False)
    wf.to_csv(wf_path, index=False)
    report_row_for_strategy(
        "sum_pos_open2_runner_variant_best",
        best,
        (
            f"No month/date filter. Selected full-sample runner variant: {best_rule}. "
            "Target hits are scaled out causally after the original target is touched; optional max-hold runners "
            "only activate from the original exit bar after positive progress and trend confirmation."
        ),
    ).to_csv(row_path, index=False)

    print(f"best_rule {best_rule}")
    print(f"wrote {ranking_path}")
    print(f"wrote {best_path}")
    print(f"wrote {row_path}")
    print(f"wrote {wf_path}")
    print(ranking.head(25).to_string(index=False))
    if not wf.empty:
        print("\nwalk_forward")
        print(wf.to_string(index=False))
        print("\nwalk_forward_total")
        print(summarize(pd.DataFrame({"net_points": wf["test_net"].astype(float)})))


if __name__ == "__main__":
    main()
