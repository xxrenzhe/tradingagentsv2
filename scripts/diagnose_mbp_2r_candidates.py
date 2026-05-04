from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from optimize_mbp_robust_top10 import _load_features
from search_mbp_2r_expanded import generate_expanded_2r_specs
from validate_mbp_2r_blackbox import BlackBoxConfig, _evaluation_row, collect_candidate_evaluations
from optimize_mbp_robust_top10 import Candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose all expanded 2R candidates without pre-filtering them away.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/mbp-2r-expanded-diagnostics.csv")
    parser.add_argument("--report", default="reports/NQM6-mbp-2r-expanded-diagnostics.md")
    parser.add_argument("--max-candidates", type=int, default=25000)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--progress-every", type=int, default=500)
    args = parser.parse_args()

    features = _load_features(Path(args.features_cache))
    specs = generate_expanded_2r_specs(max_candidates=args.max_candidates)
    if args.shard_count > 1:
        specs = [spec for index, spec in enumerate(specs) if index % args.shard_count == args.shard_index]
    candidates = [Candidate("advanced", spec.name, spec) for spec in specs]
    config = BlackBoxConfig(
        min_train_trades=0,
        min_test_trades=0,
        min_train_win_rate=0,
        min_test_win_rate=0.60,
        min_profit_factor=0,
        min_positive_window_rate=0,
        min_bracket_exit_share=0,
    )
    evaluations = collect_candidate_evaluations(features, candidates, config, progress_every=args.progress_every)
    rows = [_evaluation_row(item, config) for item in evaluations]
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["diagnostic_score"] = (
            frame["train_net_points"].clip(lower=-1000)
            + frame["test_net_points"].clip(lower=-1000)
            + frame["train_win_rate"] * 250
            + frame["test_win_rate"] * 500
            + frame["test_profit_factor"].clip(upper=5) * 100
        )
        frame = frame.sort_values(
            ["test_win_rate", "test_net_points", "train_win_rate", "diagnostic_score"],
            ascending=[False, False, False, False],
        ).reset_index(drop=True)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    _write_report(Path(args.report), frame, features, len(candidates))
    print(f"Diagnosed candidates: {len(candidates):,}")
    print(f"CSV: {output}")
    print(f"Report: {args.report}")
    if not frame.empty:
        print(frame.head(20)[["name", "train_trades", "train_win_rate", "train_net_points", "test_trades", "test_win_rate", "test_net_points", "test_profit_factor"]].to_string(index=False))
    return 0


def _write_report(output: Path, frame: pd.DataFrame, features: pd.DataFrame, candidate_count: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "name",
        "train_trades",
        "train_win_rate",
        "train_net_points",
        "train_profit_factor",
        "test_trades",
        "test_win_rate",
        "test_net_points",
        "test_profit_factor",
        "test_positive_window_rate",
    ]
    lines = [
        "# NQM6 Expanded 2R Diagnostics",
        "",
        f"Feature rows: {len(features):,}",
        f"Date range: {features['ts'].min()} to {features['ts'].max()}",
        f"Candidates diagnosed: {candidate_count:,}",
        "",
        "## Top By Test Win Rate",
        "",
        _markdown_table(frame.head(20)[columns]) if not frame.empty else "_No rows._",
        "",
        "## Top With Positive Test Net",
        "",
        _markdown_table(frame[frame["test_net_points"] > 0].head(20)[columns]) if not frame.empty else "_No rows._",
        "",
    ]
    output.write_text("\n".join(lines), encoding="utf-8")


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    rows = ["| " + " | ".join(frame.columns) + " |", "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    for _, row in frame.iterrows():
        values = []
        for column in frame.columns:
            value = row[column]
            values.append(f"{value:.4f}" if isinstance(value, float) else str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


if __name__ == "__main__":
    raise SystemExit(main())
