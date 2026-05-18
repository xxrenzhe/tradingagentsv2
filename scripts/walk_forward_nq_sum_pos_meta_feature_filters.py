from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from optimize_nq_sum_pos_market_feature_filters import summarize  # noqa: E402


@dataclass(frozen=True)
class MaskCandidate:
    name: str
    mask: np.ndarray


@dataclass(frozen=True)
class FastSummary:
    trades: int
    net_points: float
    profit_factor: float
    win_rate: float
    avg_points: float
    max_drawdown_points: float
    worst_trade_points: float
    best_trade_points: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "trades": self.trades,
            "net_points": self.net_points,
            "profit_factor": self.profit_factor,
            "win_rate": self.win_rate,
            "avg_points": self.avg_points,
            "max_drawdown_points": self.max_drawdown_points,
            "worst_trade_points": self.worst_trade_points,
            "best_trade_points": self.best_trade_points,
        }


def fast_summarize_points(points: np.ndarray) -> FastSummary:
    if len(points) == 0:
        return FastSummary(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    equity = np.cumsum(points)
    drawdown = np.maximum.accumulate(equity) - equity
    gross_profit = float(points[points > 0].sum())
    gross_loss = float(-points[points < 0].sum())
    return FastSummary(
        trades=int(len(points)),
        net_points=float(points.sum()),
        profit_factor=gross_profit / gross_loss if gross_loss else float("inf"),
        win_rate=float(np.mean(points > 0)),
        avg_points=float(points.mean()),
        max_drawdown_points=float(drawdown.max()) if len(drawdown) else 0.0,
        worst_trade_points=float(points.min()),
        best_trade_points=float(points.max()),
    )


def _between(series: pd.Series, low: float, high: float) -> np.ndarray:
    return series.astype(float).between(low, high).fillna(False).to_numpy()


def _ge(series: pd.Series, threshold: float) -> np.ndarray:
    return series.astype(float).ge(threshold).fillna(False).to_numpy()


def build_candidates(trades: pd.DataFrame, min_segment_trades: int, min_removed_in_segment: int) -> list[MaskCandidate]:
    candidates: list[MaskCandidate] = [MaskCandidate("baseline_no_filter", np.ones(len(trades), dtype=bool))]
    feature_masks: list[tuple[str, np.ndarray]] = []

    for column in ("directional_range_pos_60", "directional_range_pos_120"):
        for low in (0.0, 0.05, 0.10, 0.15, 0.20, 0.25):
            for high in (0.55, 0.65, 0.75, 0.85, 0.95):
                if low < high:
                    feature_masks.append((f"{column}_between_{low:g}_{high:g}", _between(trades[column], low, high)))

    threshold_grid = {
        "dir_mom_15": (-1.0, -0.5, 0.0, 0.5, 1.0),
        "dir_mom_30": (-1.0, -0.5, 0.0, 0.5, 1.0),
        "dir_ema20_dist": (-1.0, -0.5, 0.0, 0.5, 1.0),
        "dir_ema20_slope": (0.0, 5.0, 10.0, 20.0),
        "dir_ema60_slope": (0.0, 10.0, 20.0, 40.0),
    }
    for column, thresholds in threshold_grid.items():
        for threshold in thresholds:
            feature_masks.append((f"{column}>={threshold:g}", _ge(trades[column], threshold)))

    for low in (0.0, 0.10, 0.20, 0.30):
        for high in (0.75, 0.85, 0.95, 1.0):
            if low < high:
                feature_masks.append((f"atr14_rank_240_between_{low:g}_{high:g}", _between(trades["atr14_rank_240"], low, high)))

    pullback_anchor = _between(trades["directional_range_pos_60"], 0.10, 0.65)
    for mom_threshold in (1.0, 1.5, 2.0, 2.5, 3.0):
        for slope_threshold in (0.0, 5.0, 10.0):
            for max_range_pos in (0.75, 0.85, 0.95, 1.0):
                strong_continuation = (
                    _ge(trades["dir_mom_60"], mom_threshold)
                    & _ge(trades["dir_ema20_slope"], slope_threshold)
                    & trades["directional_range_pos_60"].astype(float).le(max_range_pos).fillna(False).to_numpy()
                )
                feature_masks.append(
                    (
                        (
                            "pullback_or_strong_continuation_"
                            f"mom60{mom_threshold:g}_slope{slope_threshold:g}_maxpos{max_range_pos:g}"
                        ),
                        pullback_anchor | strong_continuation,
                    )
                )

    candidates.extend(MaskCandidate(f"global :: {name}", mask) for name, mask in feature_masks)

    for column in ("signal_family", "session", "entry_mode", "target_plan", "component_strategy"):
        for value, group in trades.groupby(column, dropna=False):
            if len(group) < min_segment_trades:
                continue
            segment_mask = trades[column].eq(value).to_numpy()
            label = f"{column}={value}"
            candidates.append(MaskCandidate(f"skip :: {label}", ~segment_mask))
            for feature_name, feature_mask in feature_masks:
                removed_in_segment = int(np.count_nonzero(segment_mask & ~feature_mask))
                if removed_in_segment < min_removed_in_segment:
                    continue
                candidates.append(MaskCandidate(f"seg_keep :: {label} :: {feature_name}", (~segment_mask) | feature_mask))

    seen: set[str] = set()
    unique: list[MaskCandidate] = []
    for candidate in candidates:
        if candidate.name in seen:
            continue
        seen.add(candidate.name)
        unique.append(candidate)
    return unique


def slice_summary(trades: pd.DataFrame, row_mask: np.ndarray) -> dict[str, float | int]:
    return fast_summarize_points(trades.loc[row_mask, "net_points"].to_numpy(dtype=float)).as_dict()


def pick_candidate(
    trades: pd.DataFrame,
    net_points: np.ndarray,
    candidates: list[MaskCandidate],
    train_mask: np.ndarray,
    min_train_trades: int,
    min_train_delta: float,
) -> tuple[MaskCandidate, dict[str, float | int]]:
    baseline = fast_summarize_points(net_points[train_mask])
    best_candidate = candidates[0]
    best_summary = baseline.as_dict()
    best_score = -np.inf

    for candidate in candidates:
        selected_mask = train_mask & candidate.mask
        selected_count = int(np.count_nonzero(selected_mask))
        if selected_count < min_train_trades:
            continue
        selected_summary_obj = fast_summarize_points(net_points[selected_mask])
        selected_summary = selected_summary_obj.as_dict()
        removed_count = int(np.count_nonzero(train_mask & ~candidate.mask))
        if candidate.name != "baseline_no_filter":
            if removed_count < 20:
                continue
            if float(selected_summary["net_points"]) < float(baseline.net_points) + min_train_delta:
                continue
        score = (
            float(selected_summary["net_points"])
            + 180.0 * min(float(selected_summary["profit_factor"]), 3.0)
            - 0.20 * float(selected_summary["max_drawdown_points"])
            + 0.02 * selected_count
        )
        if score > best_score:
            best_score = score
            best_candidate = candidate
            best_summary = selected_summary

    return best_candidate, best_summary


def run_walk_forward(
    trades: pd.DataFrame,
    candidates: list[MaskCandidate],
    train_months: int,
    test_months: int,
    start_date: str,
    min_train_frac: float,
    min_train_delta: float,
    baseline_guard_pf: float,
    baseline_guard_avg: float,
    baseline_guard_net: float,
    recent_guard_months: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)
    net_points = trades["net_points"].to_numpy(dtype=float)
    start = pd.Timestamp(start_date, tz="UTC")
    end = entry_ts.max()
    fold_rows: list[dict[str, object]] = []
    trade_frames: list[pd.DataFrame] = []

    test_start = start
    while test_start <= end:
        train_start = test_start - pd.DateOffset(months=train_months)
        test_end = test_start + pd.DateOffset(months=test_months)
        train_mask = ((entry_ts >= train_start) & (entry_ts < test_start)).to_numpy()
        test_mask = ((entry_ts >= test_start) & (entry_ts < test_end)).to_numpy()
        train_count = int(np.count_nonzero(train_mask))
        test_count = int(np.count_nonzero(test_mask))
        if train_count < 200 or test_count == 0:
            test_start = test_end
            continue

        min_train_trades = max(120, int(train_count * min_train_frac))
        baseline_train_summary = fast_summarize_points(net_points[train_mask]).as_dict()
        guard_mask = train_mask
        if recent_guard_months > 0:
            recent_start = test_start - pd.DateOffset(months=recent_guard_months)
            recent_mask = ((entry_ts >= recent_start) & (entry_ts < test_start)).to_numpy()
            if int(np.count_nonzero(recent_mask)) >= 50:
                guard_mask = recent_mask
        guard_summary = fast_summarize_points(net_points[guard_mask]).as_dict()
        baseline_guard_triggered = (
            float(guard_summary["profit_factor"]) >= baseline_guard_pf
            or float(guard_summary["avg_points"]) >= baseline_guard_avg
            or float(guard_summary["net_points"]) >= baseline_guard_net
        )
        if baseline_guard_triggered:
            candidate = candidates[0]
            train_summary = baseline_train_summary
        else:
            candidate, train_summary = pick_candidate(trades, net_points, candidates, train_mask, min_train_trades, min_train_delta)
        selected_test_mask = test_mask & candidate.mask
        base_test_summary = slice_summary(trades, test_mask)
        selected_test_summary = slice_summary(trades, selected_test_mask)

        fold_rows.append(
            {
                "test_start": test_start.date().isoformat(),
                "test_end": test_end.date().isoformat(),
                "train_start": train_start.date().isoformat(),
                "candidate": candidate.name,
                "train_trades": int(train_summary["trades"]),
                "train_net_points": float(train_summary["net_points"]),
                "train_profit_factor": float(train_summary["profit_factor"]),
                "baseline_train_net_points": float(baseline_train_summary["net_points"]),
                "baseline_train_profit_factor": float(baseline_train_summary["profit_factor"]),
                "baseline_train_avg_points": float(baseline_train_summary["avg_points"]),
                "guard_months": int(recent_guard_months),
                "guard_net_points": float(guard_summary["net_points"]),
                "guard_profit_factor": float(guard_summary["profit_factor"]),
                "guard_avg_points": float(guard_summary["avg_points"]),
                "baseline_guard_triggered": bool(baseline_guard_triggered),
                "base_test_trades": int(base_test_summary["trades"]),
                "base_test_net_points": float(base_test_summary["net_points"]),
                "base_test_profit_factor": float(base_test_summary["profit_factor"]),
                "test_trades": int(selected_test_summary["trades"]),
                "test_net_points": float(selected_test_summary["net_points"]),
                "test_profit_factor": float(selected_test_summary["profit_factor"]),
                "test_max_drawdown_points": float(selected_test_summary["max_drawdown_points"]),
                "test_delta_net_points": float(selected_test_summary["net_points"] - base_test_summary["net_points"]),
            }
        )
        selected = trades.loc[selected_test_mask].copy()
        selected["wf_candidate"] = candidate.name
        selected["wf_test_start"] = test_start.date().isoformat()
        trade_frames.append(selected)
        test_start = test_end

    folds = pd.DataFrame(fold_rows)
    selected_trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    return folds, selected_trades


def summary_row(label: str, trades: pd.DataFrame, folds: pd.DataFrame) -> dict[str, object]:
    row = {"label": label, **summarize(trades)}
    if not folds.empty:
        row["folds"] = int(len(folds))
        row["positive_folds"] = int((folds["test_net_points"] > 0).sum())
        row["base_test_net_points"] = float(folds["base_test_net_points"].sum())
        row["test_delta_net_points"] = float(folds["test_delta_net_points"].sum())
    else:
        row["folds"] = 0
        row["positive_folds"] = 0
        row["base_test_net_points"] = 0.0
        row["test_delta_net_points"] = 0.0
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward validate causal market-feature filters on fixed sum_pos meta trades.")
    parser.add_argument("--trades", default="reports/NQ-pine-sum_pos-open2-fixed-meta-oos-fixed_meta-trades.csv")
    parser.add_argument("--output-prefix", default="reports/NQ-pine-sum_pos-open2-fixed-meta-feature-wf")
    parser.add_argument("--train-months", type=int, default=24)
    parser.add_argument("--test-months", type=int, default=3)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--min-train-frac", type=float, default=0.18)
    parser.add_argument("--min-train-delta", type=float, default=100.0)
    parser.add_argument("--min-segment-trades", type=int, default=300)
    parser.add_argument("--min-removed-in-segment", type=int, default=80)
    parser.add_argument("--baseline-guard-pf", type=float, default=float("inf"))
    parser.add_argument("--baseline-guard-avg", type=float, default=float("inf"))
    parser.add_argument("--baseline-guard-net", type=float, default=float("inf"))
    parser.add_argument("--recent-guard-months", type=int, default=0)
    args = parser.parse_args()

    trades = pd.read_csv(ROOT_DIR / args.trades)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades = trades.sort_values("entry_ts").reset_index(drop=True)
    candidates = build_candidates(trades, args.min_segment_trades, args.min_removed_in_segment)
    folds, selected = run_walk_forward(
        trades,
        candidates,
        train_months=args.train_months,
        test_months=args.test_months,
        start_date=args.start_date,
        min_train_frac=args.min_train_frac,
        min_train_delta=args.min_train_delta,
        baseline_guard_pf=args.baseline_guard_pf,
        baseline_guard_avg=args.baseline_guard_avg,
        baseline_guard_net=args.baseline_guard_net,
        recent_guard_months=args.recent_guard_months,
    )

    prefix = ROOT_DIR / args.output_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    folds.to_csv(prefix.with_name(f"{prefix.name}-folds.csv"), index=False)
    selected.to_csv(prefix.with_name(f"{prefix.name}-trades.csv"), index=False)
    summary = pd.DataFrame([summary_row("feature_walk_forward", selected, folds)])
    summary.to_csv(prefix.with_name(f"{prefix.name}-summary.csv"), index=False)
    print(f"candidates={len(candidates)}")
    print(summary.to_string(index=False))
    print(folds.to_string(index=False))


if __name__ == "__main__":
    main()
