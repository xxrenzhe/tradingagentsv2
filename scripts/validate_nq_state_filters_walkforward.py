from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from mine_nq_state_filtered_features import (
    StateFilter,
    apply_filter,
    attach_state,
    candidate_filters,
    describe_filter,
    load_features,
    load_trades,
    summarize,
)


@dataclass(frozen=True)
class SelectedFilter:
    fold: int
    candidate: str
    state_filter: StateFilter
    train_summary: dict[str, float]
    train_baseline: dict[str, float]
    train_score: float


def validate_past_fold_selection(
    trades: pd.DataFrame,
    *,
    min_train_folds: int,
    min_train_trades: int,
    min_train_net_points: float,
    min_train_profit_factor: float,
    min_train_win_rate: float,
    min_train_positive_fold_rate: float,
    min_train_min_fold_net_points: float,
    max_fold_candidates: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    selected_rows: list[dict[str, object]] = []
    folds = sorted(int(fold) for fold in pd.to_numeric(trades["fold"], errors="coerce").dropna().unique())
    filters = candidate_filters(trades)
    for test_fold in folds:
        train = trades[pd.to_numeric(trades["fold"], errors="coerce") < test_fold]
        test = trades[pd.to_numeric(trades["fold"], errors="coerce") == test_fold]
        if train.empty or test.empty:
            continue
        selected = select_filters_for_fold(
            train,
            filters=filters,
            test_fold=test_fold,
            min_train_folds=min_train_folds,
            min_train_trades=min_train_trades,
            min_train_net_points=min_train_net_points,
            min_train_profit_factor=min_train_profit_factor,
            min_train_win_rate=min_train_win_rate,
            min_train_positive_fold_rate=min_train_positive_fold_rate,
            min_train_min_fold_net_points=min_train_min_fold_net_points,
            max_fold_candidates=max_fold_candidates,
        )
        for selected_filter in selected:
            test_group = test[test["candidate"] == selected_filter.candidate]
            test_selected = test_group[apply_filter(test_group, selected_filter.state_filter)]
            test_summary = summarize(test_selected)
            if test_summary["trades"] == 0:
                continue
            baseline = summarize(test_group)
            row = {
                "fold": test_fold,
                "candidate": selected_filter.candidate,
                "filter": selected_filter.state_filter.name,
                "filter_conditions": describe_filter(selected_filter.state_filter),
                "train_score": selected_filter.train_score,
                "train_trades": selected_filter.train_summary["trades"],
                "train_net_points": selected_filter.train_summary["net_points"],
                "train_profit_factor": selected_filter.train_summary["profit_factor"],
                "train_win_rate": selected_filter.train_summary["win_rate"],
                "train_folds": selected_filter.train_summary["folds"],
                "train_positive_fold_rate": selected_filter.train_summary["positive_fold_rate"],
                "train_min_fold_net_points": selected_filter.train_summary["min_fold_net_points"],
                "train_baseline_net_points": selected_filter.train_baseline["net_points"],
                "train_net_improvement": selected_filter.train_summary["net_points"]
                - selected_filter.train_baseline["net_points"],
                "test_trades": test_summary["trades"],
                "test_net_points": test_summary["net_points"],
                "test_profit_factor": test_summary["profit_factor"],
                "test_win_rate": test_summary["win_rate"],
                "test_baseline_trades": baseline["trades"],
                "test_baseline_net_points": baseline["net_points"],
                "test_net_improvement": test_summary["net_points"] - baseline["net_points"],
            }
            rows.append(row)
            selected_rows.append(
                {
                    "fold": test_fold,
                    "candidate": selected_filter.candidate,
                    "filter": selected_filter.state_filter.name,
                    "train_score": selected_filter.train_score,
                }
            )
    results = pd.DataFrame(rows)
    selections = pd.DataFrame(selected_rows)
    if not results.empty:
        results = results.sort_values(["fold", "train_score"], ascending=[True, False]).reset_index(drop=True)
    return results, selections


def select_filters_for_fold(
    train: pd.DataFrame,
    *,
    filters: list[StateFilter],
    test_fold: int,
    min_train_folds: int,
    min_train_trades: int,
    min_train_net_points: float,
    min_train_profit_factor: float,
    min_train_win_rate: float,
    min_train_positive_fold_rate: float,
    min_train_min_fold_net_points: float,
    max_fold_candidates: int,
) -> list[SelectedFilter]:
    selected: list[SelectedFilter] = []
    for candidate, group in train.groupby("candidate", sort=False):
        baseline = summarize(group)
        for state_filter in filters:
            filtered = group[apply_filter(group, state_filter)]
            if filtered.empty:
                continue
            summary = summarize(filtered)
            if not passes_train_gate(
                summary,
                min_train_folds=min_train_folds,
                min_train_trades=min_train_trades,
                min_train_net_points=min_train_net_points,
                min_train_profit_factor=min_train_profit_factor,
                min_train_win_rate=min_train_win_rate,
                min_train_positive_fold_rate=min_train_positive_fold_rate,
                min_train_min_fold_net_points=min_train_min_fold_net_points,
            ):
                continue
            selected.append(
                SelectedFilter(
                    fold=test_fold,
                    candidate=str(candidate),
                    state_filter=state_filter,
                    train_summary=summary,
                    train_baseline=baseline,
                    train_score=score_train_filter(summary, baseline),
                )
            )
    return sorted(selected, key=lambda row: row.train_score, reverse=True)[:max_fold_candidates]


def passes_train_gate(
    summary: dict[str, float],
    *,
    min_train_folds: int,
    min_train_trades: int,
    min_train_net_points: float,
    min_train_profit_factor: float,
    min_train_win_rate: float,
    min_train_positive_fold_rate: float,
    min_train_min_fold_net_points: float,
) -> bool:
    return (
        summary["folds"] >= min_train_folds
        and summary["trades"] >= min_train_trades
        and summary["net_points"] >= min_train_net_points
        and summary["profit_factor"] >= min_train_profit_factor
        and summary["win_rate"] >= min_train_win_rate
        and summary["positive_fold_rate"] >= min_train_positive_fold_rate
        and summary["min_fold_net_points"] >= min_train_min_fold_net_points
    )


def score_train_filter(summary: dict[str, float], baseline: dict[str, float]) -> float:
    return (
        summary["net_points"]
        + 750.0 * summary["positive_fold_rate"]
        + 400.0 * max(summary["profit_factor"] - 1.0, 0.0)
        + 0.25 * (summary["net_points"] - baseline["net_points"])
        + min(summary["min_fold_net_points"], 0.0)
    )


def aggregate_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for (candidate, state_filter), group in results.groupby(["candidate", "filter"], sort=False):
        test_summary = summarize(
            pd.DataFrame({"net_points": group["test_net_points"], "fold": group["fold"]})
        )
        baseline_summary = summarize(
            pd.DataFrame({"net_points": group["test_baseline_net_points"], "fold": group["fold"]})
        )
        rows.append(
            {
                "candidate": candidate,
                "filter": state_filter,
                "filter_conditions": str(group["filter_conditions"].iloc[0]),
                "selected_folds": int(group["fold"].nunique()),
                "test_trades": int(group["test_trades"].sum()),
                "test_net_points": test_summary["net_points"],
                "fold_net_profit_factor": test_summary["profit_factor"],
                "positive_selected_fold_rate": float(
                    (pd.to_numeric(group["test_net_points"], errors="coerce") > 0).mean()
                ),
                "positive_test_fold_rate": test_summary["positive_fold_rate"],
                "min_test_fold_net_points": test_summary["min_fold_net_points"],
                "test_baseline_net_points": baseline_summary["net_points"],
                "test_net_improvement": test_summary["net_points"] - baseline_summary["net_points"],
                "avg_train_score": float(pd.to_numeric(group["train_score"], errors="coerce").mean()),
                "avg_train_profit_factor": float(
                    pd.to_numeric(group["train_profit_factor"], errors="coerce").mean()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["test_net_points", "positive_test_fold_rate", "selected_folds"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def write_report(path: Path, aggregate: pd.DataFrame, fold_results: pd.DataFrame, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total_net = float(pd.to_numeric(fold_results["test_net_points"], errors="coerce").sum()) if not fold_results.empty else 0.0
    baseline_net = (
        float(pd.to_numeric(fold_results["test_baseline_net_points"], errors="coerce").sum())
        if not fold_results.empty
        else 0.0
    )
    lines = [
        "# NQ State Filter Past-Fold Walk-Forward Validation",
        "",
        "Each test fold selects candidate filters only from earlier folds, then evaluates the selected filters on the current future fold.",
        "",
        f"- Trades input: `{args.trades_input}`",
        f"- Feature cache: `{args.features_cache}`",
        f"- Fold rows tested: `{len(fold_results):,}`",
        f"- Aggregate rows: `{len(aggregate):,}`",
        f"- Total selected-filter future net points: `{total_net:.3f}`",
        f"- Same candidate unfiltered future net points: `{baseline_net:.3f}`",
        f"- Future net improvement: `{total_net - baseline_net:.3f}`",
        f"- Gates: min_train_folds=`{args.min_train_folds}`, min_train_trades=`{args.min_train_trades}`, min_train_net_points=`{args.min_train_net_points}`, min_train_profit_factor=`{args.min_train_profit_factor}`, min_train_win_rate=`{args.min_train_win_rate}`, min_train_positive_fold_rate=`{args.min_train_positive_fold_rate}`, min_train_min_fold_net_points=`{args.min_train_min_fold_net_points}`",
        "",
    ]
    if aggregate.empty:
        lines.append("No past-fold selected filters produced future test rows.")
    else:
        lines.extend(
            [
                "## Top Future-Validated Filters",
                "",
                "```csv",
                aggregate.head(args.top_n).to_csv(index=False).strip(),
                "```",
                "",
                "## Interpretation",
                "",
                "- This is stricter than post-filter mining because the tested filter is selected before the future fold is evaluated.",
                "- Repeated selection across multiple future folds is stronger evidence than a large result in one fold.",
                "- These are still research candidates; the next step is integrating the strongest rules into the full bar strategy search and ranking pipeline.",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate NQ state filters with past-fold-only selection.")
    parser.add_argument("--features-cache", default=".tmp/nq-bar-5y-continuous-features-cache.pkl")
    parser.add_argument("--trades-input", default=".tmp/nq-bar-5y-directional-walkforward-trades.csv")
    parser.add_argument("--fold-output", default=".tmp/nq-state-filter-past-fold-validation.csv")
    parser.add_argument("--aggregate-output", default=".tmp/nq-state-filter-past-fold-validation-aggregate.csv")
    parser.add_argument("--report", default="reports/NQ-bar-5y-state-filter-past-fold-validation.md")
    parser.add_argument("--min-train-folds", type=int, default=2)
    parser.add_argument("--min-train-trades", type=int, default=120)
    parser.add_argument("--min-train-net-points", type=float, default=1000.0)
    parser.add_argument("--min-train-profit-factor", type=float, default=1.20)
    parser.add_argument("--min-train-win-rate", type=float, default=0.48)
    parser.add_argument("--min-train-positive-fold-rate", type=float, default=0.80)
    parser.add_argument("--min-train-min-fold-net-points", type=float, default=250.0)
    parser.add_argument("--max-fold-candidates", type=int, default=5)
    parser.add_argument("--top-n", type=int, default=25)
    args = parser.parse_args()

    features = load_features(args.features_cache)
    trades = attach_state(load_trades(args.trades_input), features)
    fold_results, selections = validate_past_fold_selection(
        trades,
        min_train_folds=args.min_train_folds,
        min_train_trades=args.min_train_trades,
        min_train_net_points=args.min_train_net_points,
        min_train_profit_factor=args.min_train_profit_factor,
        min_train_win_rate=args.min_train_win_rate,
        min_train_positive_fold_rate=args.min_train_positive_fold_rate,
        min_train_min_fold_net_points=args.min_train_min_fold_net_points,
        max_fold_candidates=args.max_fold_candidates,
    )
    aggregate = aggregate_results(fold_results)
    fold_output = Path(args.fold_output)
    aggregate_output = Path(args.aggregate_output)
    fold_output.parent.mkdir(parents=True, exist_ok=True)
    fold_results.to_csv(fold_output, index=False)
    aggregate.to_csv(aggregate_output, index=False)
    write_report(Path(args.report), aggregate, fold_results, args)
    result = {
        "feature_rows": int(len(features)),
        "trade_rows": int(len(trades)),
        "selection_rows": int(len(selections)),
        "fold_result_rows": int(len(fold_results)),
        "aggregate_rows": int(len(aggregate)),
        "fold_output": str(fold_output),
        "aggregate_output": str(aggregate_output),
        "report": args.report,
    }
    if not aggregate.empty:
        result["top_validated_filter"] = aggregate.iloc[0].to_dict()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
