from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from walk_forward_nq_sum_pos_meta_feature_filters import (  # noqa: E402
    MaskCandidate,
    build_candidates,
    fast_summarize_points,
    pick_candidate,
    slice_summary,
)
from optimize_nq_sum_pos_market_feature_filters import summarize  # noqa: E402


def _summary_for_mask(net_points: np.ndarray, mask: np.ndarray) -> dict[str, float | int]:
    return fast_summarize_points(net_points[mask]).as_dict()


def _passes_gate(summary: dict[str, float | int], min_trades: int, min_pf: float, min_net: float, min_avg: float) -> bool:
    if int(summary["trades"]) < min_trades:
        return False
    if float(summary["profit_factor"]) < min_pf:
        return False
    if float(summary["net_points"]) < min_net:
        return False
    if float(summary["avg_points"]) < min_avg:
        return False
    return True


def run_adaptive(
    trades: pd.DataFrame,
    candidates: list[MaskCandidate],
    train_months: int,
    test_months: int,
    start_date: str,
    recent_months: int,
    min_train_frac: float,
    min_train_delta: float,
    min_recent_trades: int,
    enable_pf: float,
    enable_net: float,
    enable_avg: float,
    baseline_strong_pf: float,
    baseline_strong_net: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)
    net_points = trades["net_points"].to_numpy(dtype=float)
    start = pd.Timestamp(start_date, tz="UTC")
    end = entry_ts.max()
    fold_rows: list[dict[str, object]] = []
    trade_frames: list[pd.DataFrame] = []
    baseline = candidates[0]

    test_start = start
    while test_start <= end:
        train_start = test_start - pd.DateOffset(months=train_months)
        test_end = test_start + pd.DateOffset(months=test_months)
        recent_start = test_start - pd.DateOffset(months=recent_months)
        train_mask = ((entry_ts >= train_start) & (entry_ts < test_start)).to_numpy()
        recent_mask = ((entry_ts >= recent_start) & (entry_ts < test_start)).to_numpy()
        test_mask = ((entry_ts >= test_start) & (entry_ts < test_end)).to_numpy()
        train_count = int(np.count_nonzero(train_mask))
        test_count = int(np.count_nonzero(test_mask))
        if train_count < 200 or test_count == 0:
            test_start = test_end
            continue

        min_train_trades = max(120, int(train_count * min_train_frac))
        train_candidate, train_summary = pick_candidate(
            trades,
            net_points,
            candidates,
            train_mask,
            min_train_trades=min_train_trades,
            min_train_delta=min_train_delta,
        )

        baseline_recent_summary = _summary_for_mask(net_points, recent_mask & baseline.mask)
        train_candidate_recent_summary = _summary_for_mask(net_points, recent_mask & train_candidate.mask)
        base_test_summary = slice_summary(trades, test_mask)

        if _passes_gate(
            baseline_recent_summary,
            min_trades=min_recent_trades,
            min_pf=baseline_strong_pf,
            min_net=baseline_strong_net,
            min_avg=-float("inf"),
        ):
            selected_candidate = baseline
            selected_recent_summary = baseline_recent_summary
            mode = "baseline_strong"
            enabled = True
        elif _passes_gate(
            train_candidate_recent_summary,
            min_trades=min_recent_trades,
            min_pf=enable_pf,
            min_net=enable_net,
            min_avg=enable_avg,
        ):
            selected_candidate = train_candidate
            selected_recent_summary = train_candidate_recent_summary
            mode = "defensive_filter"
            enabled = True
        else:
            selected_candidate = MaskCandidate("NO_TRADE", np.zeros(len(trades), dtype=bool))
            selected_recent_summary = train_candidate_recent_summary
            mode = "no_trade"
            enabled = False

        selected_test_mask = test_mask & selected_candidate.mask
        selected_test_summary = slice_summary(trades, selected_test_mask)
        fold_rows.append(
            {
                "test_start": test_start.date().isoformat(),
                "test_end": test_end.date().isoformat(),
                "train_start": train_start.date().isoformat(),
                "recent_start": recent_start.date().isoformat(),
                "mode": mode,
                "enabled": bool(enabled),
                "selected_candidate": selected_candidate.name,
                "train_candidate": train_candidate.name,
                "train_candidate_trades": int(train_summary["trades"]),
                "train_candidate_net_points": float(train_summary["net_points"]),
                "train_candidate_profit_factor": float(train_summary["profit_factor"]),
                "baseline_recent_trades": int(baseline_recent_summary["trades"]),
                "baseline_recent_net_points": float(baseline_recent_summary["net_points"]),
                "baseline_recent_profit_factor": float(baseline_recent_summary["profit_factor"]),
                "candidate_recent_trades": int(train_candidate_recent_summary["trades"]),
                "candidate_recent_net_points": float(train_candidate_recent_summary["net_points"]),
                "candidate_recent_profit_factor": float(train_candidate_recent_summary["profit_factor"]),
                "selected_recent_trades": int(selected_recent_summary["trades"]),
                "selected_recent_net_points": float(selected_recent_summary["net_points"]),
                "selected_recent_profit_factor": float(selected_recent_summary["profit_factor"]),
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
        if not selected.empty:
            selected["adaptive_mode"] = mode
            selected["adaptive_candidate"] = selected_candidate.name
            selected["adaptive_test_start"] = test_start.date().isoformat()
            trade_frames.append(selected)
        test_start = test_end

    folds = pd.DataFrame(fold_rows)
    selected_trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    return folds, selected_trades


def summary_row(label: str, trades: pd.DataFrame, folds: pd.DataFrame) -> dict[str, object]:
    row = {"label": label, **summarize(trades)} if not trades.empty else {
        "label": label,
        "trades": 0,
        "net_points": 0.0,
        "profit_factor": 0.0,
        "win_rate": 0.0,
        "avg_points": 0.0,
        "max_drawdown_points": 0.0,
        "worst_trade_points": 0.0,
        "best_trade_points": 0.0,
    }
    row["folds"] = int(len(folds))
    row["enabled_folds"] = int(folds["enabled"].sum()) if not folds.empty else 0
    row["positive_folds"] = int((folds["test_net_points"] > 0).sum()) if not folds.empty else 0
    row["base_test_net_points"] = float(folds["base_test_net_points"].sum()) if not folds.empty else 0.0
    row["test_delta_net_points"] = float(folds["test_delta_net_points"].sum()) if not folds.empty else 0.0
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Causal adaptive composite selector for sum_pos fixed-meta strategy family.")
    parser.add_argument("--trades", default="reports/NQ-pine-sum_pos-open2-fixed-meta-oos-fixed_meta-trades.csv")
    parser.add_argument("--output-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite")
    parser.add_argument("--train-months", type=int, default=36)
    parser.add_argument("--test-months", type=int, default=1)
    parser.add_argument("--start-date", default="2023-01-01")
    parser.add_argument("--recent-months", type=int, default=6)
    parser.add_argument("--min-train-frac", type=float, default=0.18)
    parser.add_argument("--min-train-delta", type=float, default=100.0)
    parser.add_argument("--min-recent-trades", type=int, default=30)
    parser.add_argument("--enable-pf", type=float, default=1.05)
    parser.add_argument("--enable-net", type=float, default=0.0)
    parser.add_argument("--enable-avg", type=float, default=0.0)
    parser.add_argument("--baseline-strong-pf", type=float, default=1.20)
    parser.add_argument("--baseline-strong-net", type=float, default=0.0)
    parser.add_argument("--min-segment-trades", type=int, default=300)
    parser.add_argument("--min-removed-in-segment", type=int, default=80)
    args = parser.parse_args()

    trades = pd.read_csv(ROOT_DIR / args.trades)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades = trades.sort_values("entry_ts").reset_index(drop=True)
    candidates = build_candidates(trades, args.min_segment_trades, args.min_removed_in_segment)
    folds, selected = run_adaptive(
        trades,
        candidates,
        train_months=args.train_months,
        test_months=args.test_months,
        start_date=args.start_date,
        recent_months=args.recent_months,
        min_train_frac=args.min_train_frac,
        min_train_delta=args.min_train_delta,
        min_recent_trades=args.min_recent_trades,
        enable_pf=args.enable_pf,
        enable_net=args.enable_net,
        enable_avg=args.enable_avg,
        baseline_strong_pf=args.baseline_strong_pf,
        baseline_strong_net=args.baseline_strong_net,
    )
    prefix = ROOT_DIR / args.output_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    folds.to_csv(prefix.with_name(f"{prefix.name}-folds.csv"), index=False)
    selected.to_csv(prefix.with_name(f"{prefix.name}-trades.csv"), index=False)
    summary = pd.DataFrame([summary_row("adaptive_composite", selected, folds)])
    summary.to_csv(prefix.with_name(f"{prefix.name}-summary.csv"), index=False)
    print(f"candidates={len(candidates)}")
    print(summary.to_string(index=False))
    print(folds.to_string(index=False))


if __name__ == "__main__":
    main()
