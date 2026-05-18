from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from walk_forward_nq_sum_pos_meta_feature_filters import build_candidates, run_walk_forward, summary_row  # noqa: E402


def parse_float_grid(value: str) -> list[float]:
    output: list[float] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if item.lower() in {"inf", "infinity"}:
            output.append(float("inf"))
        else:
            output.append(float(item))
    return output


def run_one(
    trades: pd.DataFrame,
    candidates,
    train_months: int,
    test_months: int,
    start_date: str,
    min_train_frac: float,
    min_train_delta: float,
    pf: float,
    avg: float,
    net: float,
    recent_guard_months: int,
) -> tuple[dict[str, object], pd.DataFrame]:
    folds, selected = run_walk_forward(
        trades,
        candidates,
        train_months=train_months,
        test_months=test_months,
        start_date=start_date,
        min_train_frac=min_train_frac,
        min_train_delta=min_train_delta,
        baseline_guard_pf=pf,
        baseline_guard_avg=avg,
        baseline_guard_net=net,
        recent_guard_months=recent_guard_months,
    )
    row = summary_row("regime_switch", selected, folds)
    row.update(
        {
            "train_months": train_months,
            "test_months": test_months,
            "start_date": start_date,
            "baseline_guard_pf": pf,
            "baseline_guard_avg": avg,
            "baseline_guard_net": net,
            "recent_guard_months": recent_guard_months,
            "baseline_guard_folds": int(folds["baseline_guard_triggered"].sum()) if not folds.empty else 0,
            "score": float(row["net_points"]) + 160.0 * float(row["profit_factor"]) - 0.25 * float(row["max_drawdown_points"]),
        }
    )
    return row, folds


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep causal baseline-guard regime switches for sum_pos meta feature walk-forward.")
    parser.add_argument("--trades", default="reports/NQ-pine-sum_pos-open2-fixed-meta-oos-fixed_meta-trades.csv")
    parser.add_argument("--output", default="reports/NQ-pine-sum_pos-open2-fixed-meta-regime-switch-sweep.csv")
    parser.add_argument("--fold-output", default="reports/NQ-pine-sum_pos-open2-fixed-meta-regime-switch-sweep-folds.csv")
    parser.add_argument("--train-months", default="24,36")
    parser.add_argument("--test-months", type=int, default=3)
    parser.add_argument("--start-24", default="2022-01-01")
    parser.add_argument("--start-36", default="2023-01-01")
    parser.add_argument("--pf-grid", default="1.02,1.05,1.08,1.10,1.12,1.15,1.20,inf")
    parser.add_argument("--avg-grid", default="0.25,0.5,0.75,1.0,inf")
    parser.add_argument("--net-grid", default="inf")
    parser.add_argument("--recent-guard-months-grid", default="0,3,6,9")
    parser.add_argument("--min-train-frac", type=float, default=0.18)
    parser.add_argument("--min-train-delta", type=float, default=100.0)
    parser.add_argument("--min-segment-trades", type=int, default=300)
    parser.add_argument("--min-removed-in-segment", type=int, default=80)
    args = parser.parse_args()

    trades = pd.read_csv(ROOT_DIR / args.trades)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades = trades.sort_values("entry_ts").reset_index(drop=True)
    candidates = build_candidates(trades, args.min_segment_trades, args.min_removed_in_segment)

    rows: list[dict[str, object]] = []
    fold_frames: list[pd.DataFrame] = []
    train_months_grid = [int(item.strip()) for item in args.train_months.split(",") if item.strip()]
    for train_months in train_months_grid:
        start_date = args.start_24 if train_months == 24 else args.start_36
        for pf in parse_float_grid(args.pf_grid):
            for avg in parse_float_grid(args.avg_grid):
                for net in parse_float_grid(args.net_grid):
                    for recent_guard_months in [int(item.strip()) for item in args.recent_guard_months_grid.split(",") if item.strip()]:
                        row, folds = run_one(
                            trades,
                            candidates,
                            train_months=train_months,
                            test_months=args.test_months,
                            start_date=start_date,
                            min_train_frac=args.min_train_frac,
                            min_train_delta=args.min_train_delta,
                            pf=pf,
                            avg=avg,
                            net=net,
                            recent_guard_months=recent_guard_months,
                        )
                        rows.append(row)
                        folds = folds.copy()
                        folds["train_months"] = train_months
                        folds["baseline_guard_pf_param"] = pf
                        folds["baseline_guard_avg_param"] = avg
                        folds["baseline_guard_net_param"] = net
                        folds["recent_guard_months_param"] = recent_guard_months
                        fold_frames.append(folds)

    ranking = pd.DataFrame(rows).sort_values(["train_months", "net_points", "profit_factor"], ascending=[True, False, False])
    fold_output = pd.concat(fold_frames, ignore_index=True) if fold_frames else pd.DataFrame()
    output_path = ROOT_DIR / args.output
    fold_output_path = ROOT_DIR / args.fold_output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(output_path, index=False)
    fold_output.to_csv(fold_output_path, index=False)

    print(f"candidates={len(candidates)}")
    print(ranking.groupby("train_months").head(10).to_string(index=False))
    print(f"wrote {output_path}")
    print(f"wrote {fold_output_path}")


if __name__ == "__main__":
    main()
