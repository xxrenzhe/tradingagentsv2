from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from optimize_nq_sum_pos_market_feature_filters import summarize


ROOT_DIR = Path(__file__).resolve().parents[1]
POINT_VALUE = 20.0


@dataclass(frozen=True)
class Candidate:
    name: str
    mask: np.ndarray


def _to_utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True)


def _period_months(trades: pd.DataFrame) -> list[str]:
    timestamps = trades["entry_ts"].dt.tz_convert(None)
    start = timestamps.min().to_period("M")
    end = timestamps.max().to_period("M")
    return pd.period_range(start, end, freq="M").astype(str).tolist()


def _summary_points(points: np.ndarray) -> dict[str, float | int]:
    if len(points) == 0:
        return {
            "trades": 0,
            "net_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_points": 0.0,
            "max_drawdown_points": 0.0,
            "worst_trade_points": 0.0,
            "best_trade_points": 0.0,
        }
    equity = np.cumsum(points)
    drawdown = np.maximum.accumulate(equity) - equity
    gross_profit = float(points[points > 0].sum())
    gross_loss = float(-points[points < 0].sum())
    return {
        "trades": int(len(points)),
        "net_points": float(points.sum()),
        "profit_factor": gross_profit / gross_loss if gross_loss else float("inf"),
        "win_rate": float(np.mean(points > 0)),
        "avg_points": float(points.mean()),
        "max_drawdown_points": float(drawdown.max()) if len(drawdown) else 0.0,
        "worst_trade_points": float(points.min()),
        "best_trade_points": float(points.max()),
    }


def _scale_from_recent(points: np.ndarray) -> tuple[float, str]:
    summary = _summary_points(points)
    if int(summary["trades"]) < 50:
        return 0.0, "warmup_no_trade"
    pf = float(summary["profit_factor"])
    net = float(summary["net_points"])
    if pf >= 1.30 and net >= 1000.0:
        return 2.35, "baseline_high_2.35x"
    if pf >= 1.20 and net >= 0.0:
        return 1.65, "baseline_mid_1.65x"
    if pf >= 1.02 and net >= 0.0:
        return 0.85, "defensive_base_0.85x"
    return 0.0, "no_trade"


def _mask_for_values(trades: pd.DataFrame, columns: list[str], values: tuple[object, ...]) -> np.ndarray:
    mask = np.ones(len(trades), dtype=bool)
    for column, value in zip(columns, values, strict=True):
        mask &= trades[column].eq(value).to_numpy()
    return mask


def _label(columns: list[str], values: tuple[object, ...]) -> str:
    return "|".join(f"{column}={value}" for column, value in zip(columns, values, strict=True))


def _feature_masks(trades: pd.DataFrame) -> list[tuple[str, np.ndarray]]:
    specs: list[tuple[str, np.ndarray]] = []
    for column, checks in {
        "directional_range_pos_60": [
            ("between_0.05_0.75", lambda x: x.between(0.05, 0.75)),
            ("between_0.10_0.85", lambda x: x.between(0.10, 0.85)),
            ("lte_0.75", lambda x: x.le(0.75)),
            ("lte_0.85", lambda x: x.le(0.85)),
            ("gte_0.30", lambda x: x.ge(0.30)),
        ],
        "directional_range_pos_120": [
            ("between_0.05_0.75", lambda x: x.between(0.05, 0.75)),
            ("between_0.10_0.85", lambda x: x.between(0.10, 0.85)),
            ("lte_0.85", lambda x: x.le(0.85)),
        ],
        "dir_mom_15": [
            ("gte_-0.5", lambda x: x.ge(-0.5)),
            ("gte_0", lambda x: x.ge(0.0)),
            ("lte_0", lambda x: x.le(0.0)),
            ("lte_-0.5", lambda x: x.le(-0.5)),
        ],
        "dir_mom_30": [
            ("gte_-0.5", lambda x: x.ge(-0.5)),
            ("gte_0", lambda x: x.ge(0.0)),
            ("lte_0", lambda x: x.le(0.0)),
        ],
        "atr14_rank_240": [
            ("between_0.05_0.85", lambda x: x.between(0.05, 0.85)),
            ("between_0.10_0.90", lambda x: x.between(0.10, 0.90)),
            ("lte_0.85", lambda x: x.le(0.85)),
        ],
        "directional_trend_stack": [
            ("gte_0", lambda x: x.ge(0.0)),
            ("lte_0", lambda x: x.le(0.0)),
        ],
    }.items():
        if column not in trades.columns:
            continue
        values = pd.to_numeric(trades[column], errors="coerce")
        for suffix, fn in checks:
            specs.append((f"{column}_{suffix}", fn(values).fillna(False).to_numpy()))
    return specs


def build_candidates(trades: pd.DataFrame, min_total_trades: int) -> list[Candidate]:
    candidates: list[Candidate] = []
    segment_specs = [
        (["signal_family", "session", "direction"], 30),
        (["signal_family", "session", "direction", "hour"], 25),
        (["component_strategy", "signal_family", "session", "direction"], 30),
        (["component_strategy", "signal_family", "session", "direction", "hour"], 25),
    ]
    base_segments: list[tuple[str, np.ndarray]] = []
    for columns, threshold in segment_specs:
        if any(column not in trades.columns for column in columns):
            continue
        for values, group in trades.groupby(columns, dropna=False):
            values_tuple = values if isinstance(values, tuple) else (values,)
            if len(group) < max(threshold, min_total_trades):
                continue
            mask = _mask_for_values(trades, columns, values_tuple)
            name = f"cell::{_label(columns, values_tuple)}"
            candidates.append(Candidate(name, mask))
            if len(group) >= 60:
                base_segments.append((_label(columns, values_tuple), mask))

    for feature_name, feature_mask in _feature_masks(trades):
        for segment_name, segment_mask in base_segments:
            mask = segment_mask & feature_mask
            if int(np.count_nonzero(mask)) >= min_total_trades:
                candidates.append(Candidate(f"feat::{segment_name}|{feature_name}", mask))

    unique: list[Candidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.name in seen:
            continue
        seen.add(candidate.name)
        unique.append(candidate)
    return unique


def _candidate_rows(
    candidates: list[Candidate],
    net_points: np.ndarray,
    train_mask: np.ndarray,
    recent_mask: np.ndarray,
    min_train_trades: int,
    min_recent_trades: int,
    train_pf: float,
    train_net: float,
    recent_pf: float,
    recent_net: float,
    min_avg: float,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for candidate in candidates:
        train = train_mask & candidate.mask
        recent = recent_mask & candidate.mask
        if int(np.count_nonzero(train)) < min_train_trades or int(np.count_nonzero(recent)) < min_recent_trades:
            continue
        train_summary = _summary_points(net_points[train])
        recent_summary = _summary_points(net_points[recent])
        if float(train_summary["profit_factor"]) < train_pf:
            continue
        if float(train_summary["net_points"]) < train_net:
            continue
        if float(train_summary["avg_points"]) < min_avg:
            continue
        if float(recent_summary["profit_factor"]) < recent_pf:
            continue
        if float(recent_summary["net_points"]) < recent_net:
            continue
        score = (
            float(train_summary["net_points"])
            + 180.0 * min(float(train_summary["profit_factor"]), 3.0)
            + 70.0 * float(train_summary["avg_points"])
            + 0.50 * float(recent_summary["net_points"])
            + 80.0 * min(float(recent_summary["profit_factor"]), 3.0)
            - 0.20 * float(train_summary["max_drawdown_points"])
        )
        rows.append(
            {
                "candidate": candidate.name,
                "score": score,
                "mask": candidate.mask,
                "train_trades": int(train_summary["trades"]),
                "train_net_points": float(train_summary["net_points"]),
                "train_profit_factor": float(train_summary["profit_factor"]),
                "train_avg_points": float(train_summary["avg_points"]),
                "recent_trades": int(recent_summary["trades"]),
                "recent_net_points": float(recent_summary["net_points"]),
                "recent_profit_factor": float(recent_summary["profit_factor"]),
            }
        )
    return sorted(rows, key=lambda row: float(row["score"]), reverse=True)


def run_overlay(
    trades: pd.DataFrame,
    candidates: list[Candidate],
    *,
    train_months: int,
    recent_months: int,
    min_train_trades: int,
    min_recent_trades: int,
    train_pf: float,
    train_net: float,
    recent_pf: float,
    recent_net: float,
    min_avg: float,
    topk: int,
    specialist_scale: float,
    months: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    entry_ts = trades["entry_ts"]
    net_points = trades["net_points"].to_numpy(dtype=float)
    months = months or _period_months(trades)
    selected_frames: list[pd.DataFrame] = []
    fold_rows: list[dict[str, object]] = []

    for month in months:
        test_start = pd.Timestamp(f"{month}-01", tz="UTC")
        test_end = test_start + pd.DateOffset(months=1)
        train_start = test_start - pd.DateOffset(months=train_months)
        recent_start = test_start - pd.DateOffset(months=recent_months)
        test_mask = ((entry_ts >= test_start) & (entry_ts < test_end)).to_numpy()
        if int(np.count_nonzero(test_mask)) == 0:
            continue
        train_mask = ((entry_ts >= train_start) & (entry_ts < test_start)).to_numpy()
        recent_mask = ((entry_ts >= recent_start) & (entry_ts < test_start)).to_numpy()
        base_scale, base_mode = _scale_from_recent(net_points[recent_mask])
        base_test_summary = _summary_points(net_points[test_mask])
        if base_scale > 0:
            selected_mask = test_mask
            selected_scale = base_scale
            mode = base_mode
            selected_names = ["BASELINE_ALL"]
            train_best: dict[str, object] = {}
        else:
            rows = _candidate_rows(
                candidates,
                net_points,
                train_mask,
                recent_mask,
                min_train_trades=min_train_trades,
                min_recent_trades=min_recent_trades,
                train_pf=train_pf,
                train_net=train_net,
                recent_pf=recent_pf,
                recent_net=recent_net,
                min_avg=min_avg,
            )[:topk]
            selected_mask = np.zeros(len(trades), dtype=bool)
            for row in rows:
                selected_mask |= row["mask"]  # type: ignore[operator]
            selected_mask &= test_mask
            selected_scale = specialist_scale if rows else 0.0
            mode = "specialist_overlay" if rows else "no_trade"
            selected_names = [str(row["candidate"]) for row in rows]
            train_best = rows[0] if rows else {}

        selected_points = net_points[selected_mask] * selected_scale
        selected_summary = _summary_points(selected_points)
        fold_rows.append(
            {
                "month": month,
                "test_start": test_start.isoformat(),
                "train_start": train_start.isoformat(),
                "recent_start": recent_start.isoformat(),
                "mode": mode,
                "position_scale": selected_scale,
                "selected_candidates": " || ".join(selected_names),
                "candidate_count": len(selected_names) if mode == "specialist_overlay" else 0,
                "train_best_candidate": train_best.get("candidate", ""),
                "train_best_score": train_best.get("score", 0.0),
                "train_best_trades": train_best.get("train_trades", 0),
                "train_best_net_points": train_best.get("train_net_points", 0.0),
                "train_best_profit_factor": train_best.get("train_profit_factor", 0.0),
                "recent_best_trades": train_best.get("recent_trades", 0),
                "recent_best_net_points": train_best.get("recent_net_points", 0.0),
                "recent_best_profit_factor": train_best.get("recent_profit_factor", 0.0),
                "base_test_trades": int(base_test_summary["trades"]),
                "base_test_net_points": float(base_test_summary["net_points"]),
                "base_test_profit_factor": float(base_test_summary["profit_factor"]),
                "test_trades": int(selected_summary["trades"]),
                "test_net_points": float(selected_summary["net_points"]),
                "test_profit_factor": float(selected_summary["profit_factor"]),
                "test_max_drawdown_points": float(selected_summary["max_drawdown_points"]),
            }
        )
        selected = trades.loc[selected_mask].copy()
        if not selected.empty and selected_scale > 0:
            selected["overlay_mode"] = mode
            selected["overlay_test_month"] = month
            selected["position_scale"] = selected_scale
            selected["base_net_points"] = selected["net_points"].astype(float)
            selected["net_points"] = selected["base_net_points"] * selected_scale
            selected["gross_points"] = selected["gross_points"].astype(float) * selected_scale
            selected["net_dollars"] = selected["net_points"] * POINT_VALUE
            selected["overlay_candidates"] = " || ".join(selected_names)
            selected_frames.append(selected)

    folds = pd.DataFrame(fold_rows)
    selected_trades = pd.concat(selected_frames, ignore_index=True) if selected_frames else pd.DataFrame()
    if not selected_trades.empty:
        selected_trades = selected_trades.sort_values("entry_ts").reset_index(drop=True)
    return folds, selected_trades


def score_result(summary: dict[str, float | int], folds: pd.DataFrame) -> float:
    return (
        float(summary["net_points"])
        + 900.0 * min(float(summary["profit_factor"]), 3.0)
        + 45.0 * float(summary["avg_points"])
        - 0.75 * float(summary["max_drawdown_points"])
        + 15.0 * int((folds["test_net_points"] > 0).sum())
    )


def sweep(trades: pd.DataFrame, candidates: list[Candidate]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    months = _period_months(trades)
    grids = product(
        [24, 36],
        [12, 24],
        [5, 8],
        [1.05, 1.10, 1.15],
        [0.0],
        [0.90, 0.95],
        [-100.0, -50.0],
        [0.0, 0.25],
        [3, 5],
        [0.75, 1.0],
    )
    for (
        train_months,
        min_train_trades,
        min_recent_trades,
        train_pf,
        train_net,
        recent_pf,
        recent_net,
        min_avg,
        topk,
        specialist_scale,
    ) in grids:
        folds, selected = run_overlay(
            trades,
            candidates,
            train_months=train_months,
            recent_months=6,
            min_train_trades=min_train_trades,
            min_recent_trades=min_recent_trades,
            train_pf=train_pf,
            train_net=train_net,
            recent_pf=recent_pf,
            recent_net=recent_net,
            min_avg=min_avg,
            topk=topk,
            specialist_scale=specialist_scale,
            months=months,
        )
        summary = summarize(selected) if not selected.empty else _summary_points(np.array([], dtype=float))
        rows.append(
            {
                "train_months": train_months,
                "recent_months": 6,
                "min_train_trades": min_train_trades,
                "min_recent_trades": min_recent_trades,
                "train_pf": train_pf,
                "train_net": train_net,
                "recent_pf": recent_pf,
                "recent_net": recent_net,
                "min_avg": min_avg,
                "topk": topk,
                "specialist_scale": specialist_scale,
                **summary,
                "enabled_months": int((folds["test_trades"] > 0).sum()),
                "positive_months": int((folds["test_net_points"] > 0).sum()),
                "worst_month_points": float(folds["test_net_points"].min()) if not folds.empty else 0.0,
                "base_test_net_points": float(folds["base_test_net_points"].sum()) if not folds.empty else 0.0,
                "score": score_result(summary, folds),
            }
        )
    return pd.DataFrame(rows).sort_values(["score", "net_points", "profit_factor"], ascending=False)


def add_period_columns(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if trades.empty:
        return pd.DataFrame(), pd.DataFrame()
    frame = trades.copy()
    frame["year"] = frame["entry_ts"].dt.year
    frame["month"] = frame["entry_ts"].dt.to_period("M").astype(str)
    yearly = frame.groupby("year")["net_points"].agg(["count", "sum", "mean"]).reset_index()
    monthly = frame.groupby("month")["net_points"].agg(["count", "sum", "mean"]).reset_index()
    return yearly, monthly


def main() -> int:
    parser = argparse.ArgumentParser(description="Optimize causal specialist overlay for 5y runner-meta replay.")
    parser.add_argument("--trades", default="reports/NQ-pine-5y-sum_pos-open2-runner-meta-allocation-best-trades.csv")
    parser.add_argument("--output-prefix", default="reports/NQ-pine-5y-runner-meta-specialist-overlay")
    parser.add_argument("--min-total-trades", type=int, default=25)
    args = parser.parse_args()

    trades = pd.read_csv(ROOT_DIR / args.trades)
    trades["entry_ts"] = _to_utc(trades["entry_ts"])
    trades["exit_ts"] = _to_utc(trades["exit_ts"])
    trades = trades.sort_values("entry_ts").reset_index(drop=True)

    candidates = build_candidates(trades, args.min_total_trades)
    ranking = sweep(trades, candidates)
    best = ranking.iloc[0]
    folds, selected = run_overlay(
        trades,
        candidates,
        train_months=int(best["train_months"]),
        recent_months=int(best["recent_months"]),
        min_train_trades=int(best["min_train_trades"]),
        min_recent_trades=int(best["min_recent_trades"]),
        train_pf=float(best["train_pf"]),
        train_net=float(best["train_net"]),
        recent_pf=float(best["recent_pf"]),
        recent_net=float(best["recent_net"]),
        min_avg=float(best["min_avg"]),
        topk=int(best["topk"]),
        specialist_scale=float(best["specialist_scale"]),
        months=_period_months(trades),
    )
    summary = summarize(selected) if not selected.empty else _summary_points(np.array([], dtype=float))
    summary_row = {
        "label": "runner_meta_balanced_aggressive_plus_specialist_overlay",
        "candidate_count": len(candidates),
        **{key: best[key] for key in [
            "train_months",
            "recent_months",
            "min_train_trades",
            "min_recent_trades",
            "train_pf",
            "train_net",
            "recent_pf",
            "recent_net",
            "min_avg",
            "topk",
            "specialist_scale",
        ]},
        **summary,
        "enabled_months": int((folds["test_trades"] > 0).sum()),
        "positive_months": int((folds["test_net_points"] > 0).sum()),
        "base_test_net_points": float(folds["base_test_net_points"].sum()),
    }
    yearly, monthly = add_period_columns(selected)

    output_prefix = ROOT_DIR / args.output_prefix
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(output_prefix.with_name(f"{output_prefix.name}-ranking.csv"), index=False)
    folds.to_csv(output_prefix.with_name(f"{output_prefix.name}-folds.csv"), index=False)
    selected.to_csv(output_prefix.with_name(f"{output_prefix.name}-trades.csv"), index=False)
    pd.DataFrame([summary_row]).to_csv(output_prefix.with_name(f"{output_prefix.name}-summary.csv"), index=False)
    yearly.to_csv(output_prefix.with_name(f"{output_prefix.name}-yearly.csv"), index=False)
    monthly.to_csv(output_prefix.with_name(f"{output_prefix.name}-monthly.csv"), index=False)

    print(pd.DataFrame([summary_row]).to_string(index=False))
    print("\nBest ranking rows")
    print(ranking.head(20).to_string(index=False))
    print("\nEnabled folds")
    print(folds.loc[folds["test_trades"].gt(0)].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
