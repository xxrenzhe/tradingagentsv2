from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from mine_nq_5y_high_win_payoff_feature_sets import (
    has_filter_columns,
    payoff_summary,
    robust_score,
)
from mine_nq_state_filtered_features import (
    StateFilter,
    apply_filter,
    attach_state,
    candidate_filters,
    describe_filter,
    load_features,
    load_trades,
)


@dataclass(frozen=True)
class TrainSelection:
    test_fold: int
    candidate: str
    state_filter: StateFilter
    train_summary: dict[str, float]
    train_baseline: dict[str, float]
    train_score: float


def load_allowed_pairs(path: str | Path, *, require_negative_baseline: bool = False) -> set[tuple[str, str]]:
    frame = pd.read_csv(path)
    selected = frame[frame["evidence_type"].astype(str).eq("state_filtered")].copy()
    if require_negative_baseline and "baseline_net_points" in selected.columns:
        selected = selected[pd.to_numeric(selected["baseline_net_points"], errors="coerce") < 0.0]
    return set(zip(selected["candidate"].astype(str), selected["filter"].astype(str)))


def validate_past_folds(
    trades: pd.DataFrame,
    allowed_pairs: set[tuple[str, str]],
    *,
    min_train_folds: int,
    min_train_trades: int,
    min_train_win_rate: float,
    min_train_payoff_ratio: float,
    min_train_net_points: float,
    min_train_positive_fold_rate: float,
    max_fold_candidates: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    filters = {state_filter.name: state_filter for state_filter in candidate_filters(trades)}
    folds = sorted(int(fold) for fold in pd.to_numeric(trades["fold"], errors="coerce").dropna().unique())
    rows: list[dict[str, object]] = []
    selected_trade_rows: list[pd.DataFrame] = []
    for test_fold in folds:
        train = trades[pd.to_numeric(trades["fold"], errors="coerce") < test_fold]
        test = trades[pd.to_numeric(trades["fold"], errors="coerce") == test_fold]
        if train.empty or test.empty:
            continue
        selections = select_train_filters(
            train,
            filters=filters,
            allowed_pairs=allowed_pairs,
            test_fold=test_fold,
            min_train_folds=min_train_folds,
            min_train_trades=min_train_trades,
            min_train_win_rate=min_train_win_rate,
            min_train_payoff_ratio=min_train_payoff_ratio,
            min_train_net_points=min_train_net_points,
            min_train_positive_fold_rate=min_train_positive_fold_rate,
            max_fold_candidates=max_fold_candidates,
        )
        for selection in selections:
            test_group = test[test["candidate"].astype(str).eq(selection.candidate)]
            if test_group.empty:
                continue
            selected_test = test_group[apply_filter(test_group, selection.state_filter)].copy()
            test_summary = payoff_summary(selected_test)
            if test_summary["trades"] == 0:
                continue
            baseline = payoff_summary(test_group)
            feature_set = f"{selection.candidate} + {selection.state_filter.name}"
            rows.append(
                {
                    "fold": test_fold,
                    "candidate": selection.candidate,
                    "filter": selection.state_filter.name,
                    "filter_conditions": describe_filter(selection.state_filter),
                    "feature_set": feature_set,
                    "train_score": selection.train_score,
                    "train_trades": int(selection.train_summary["trades"]),
                    "train_net_points": selection.train_summary["net_points"],
                    "train_win_rate": selection.train_summary["win_rate"],
                    "train_payoff_ratio_r": selection.train_summary["payoff_ratio_r"],
                    "train_profit_factor": selection.train_summary["profit_factor"],
                    "train_folds": int(selection.train_summary["folds"]),
                    "train_positive_fold_rate": selection.train_summary["positive_fold_rate"],
                    "train_baseline_net_points": selection.train_baseline["net_points"],
                    "train_net_improvement": selection.train_summary["net_points"]
                    - selection.train_baseline["net_points"],
                    "test_trades": int(test_summary["trades"]),
                    "test_net_points": test_summary["net_points"],
                    "test_win_rate": test_summary["win_rate"],
                    "test_payoff_ratio_r": test_summary["payoff_ratio_r"],
                    "test_profit_factor": test_summary["profit_factor"],
                    "test_baseline_trades": int(baseline["trades"]),
                    "test_baseline_net_points": baseline["net_points"],
                    "test_net_improvement": test_summary["net_points"] - baseline["net_points"],
                }
            )
            selected_test["validated_candidate"] = selection.candidate
            selected_test["validated_filter"] = selection.state_filter.name
            selected_test["validated_feature_set"] = feature_set
            selected_test["validated_fold"] = test_fold
            selected_trade_rows.append(selected_test)
    fold_results = pd.DataFrame(rows)
    trade_results = pd.concat(selected_trade_rows, ignore_index=True, sort=False) if selected_trade_rows else pd.DataFrame()
    if not fold_results.empty:
        fold_results = fold_results.sort_values(["fold", "train_score"], ascending=[True, False]).reset_index(drop=True)
    return fold_results, trade_results


def select_train_filters(
    train: pd.DataFrame,
    *,
    filters: dict[str, StateFilter],
    allowed_pairs: set[tuple[str, str]],
    test_fold: int,
    min_train_folds: int,
    min_train_trades: int,
    min_train_win_rate: float,
    min_train_payoff_ratio: float,
    min_train_net_points: float,
    min_train_positive_fold_rate: float,
    max_fold_candidates: int,
) -> list[TrainSelection]:
    selections: list[TrainSelection] = []
    for candidate, filter_name in sorted(allowed_pairs):
        state_filter = filters.get(filter_name)
        if state_filter is None:
            continue
        group = train[train["candidate"].astype(str).eq(candidate)]
        if group.empty or not has_filter_columns(group, state_filter):
            continue
        selected = group[apply_filter(group, state_filter)]
        summary = payoff_summary(selected)
        if not train_passes(
            summary,
            min_train_folds=min_train_folds,
            min_train_trades=min_train_trades,
            min_train_win_rate=min_train_win_rate,
            min_train_payoff_ratio=min_train_payoff_ratio,
            min_train_net_points=min_train_net_points,
            min_train_positive_fold_rate=min_train_positive_fold_rate,
        ):
            continue
        baseline = payoff_summary(group)
        selections.append(
            TrainSelection(
                test_fold=test_fold,
                candidate=candidate,
                state_filter=state_filter,
                train_summary=summary,
                train_baseline=baseline,
                train_score=train_score(summary, baseline),
            )
        )
    return sorted(selections, key=lambda row: row.train_score, reverse=True)[:max_fold_candidates]


def train_passes(
    summary: dict[str, float],
    *,
    min_train_folds: int,
    min_train_trades: int,
    min_train_win_rate: float,
    min_train_payoff_ratio: float,
    min_train_net_points: float,
    min_train_positive_fold_rate: float,
) -> bool:
    return (
        summary["folds"] >= min_train_folds
        and summary["trades"] >= min_train_trades
        and summary["win_rate"] > min_train_win_rate
        and summary["payoff_ratio_r"] > min_train_payoff_ratio
        and summary["net_points"] > min_train_net_points
        and summary["positive_fold_rate"] >= min_train_positive_fold_rate
    )


def train_score(summary: dict[str, float], baseline: dict[str, float]) -> float:
    drawdown = max(summary["max_drawdown_points"], 1.0)
    return (
        summary["net_points"] / drawdown
        + (summary["win_rate"] - 0.53) * 100.0
        + (summary["payoff_ratio_r"] - 1.0) * 15.0
        + summary["positive_fold_rate"] * 4.0
        + (summary["net_points"] - baseline["net_points"]) / 1000.0
        + min(summary["min_fold_net_points"], 0.0) / 250.0
    )


def aggregate_results(fold_results: pd.DataFrame, trade_results: pd.DataFrame) -> pd.DataFrame:
    if fold_results.empty or trade_results.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for (candidate, filter_name), trades in trade_results.groupby(["validated_candidate", "validated_filter"], sort=False):
        fold_group = fold_results[
            fold_results["candidate"].astype(str).eq(str(candidate))
            & fold_results["filter"].astype(str).eq(str(filter_name))
        ]
        summary = payoff_summary(trades)
        baseline_net = float(pd.to_numeric(fold_group["test_baseline_net_points"], errors="coerce").sum())
        rows.append(
            {
                "candidate": candidate,
                "filter": filter_name,
                "filter_conditions": str(fold_group["filter_conditions"].iloc[0]) if not fold_group.empty else "",
                "feature_set": f"{candidate} + {filter_name}",
                "selected_folds": int(fold_group["fold"].nunique()),
                "test_trades": int(summary["trades"]),
                "test_net_points": summary["net_points"],
                "test_win_rate": summary["win_rate"],
                "test_payoff_ratio_r": summary["payoff_ratio_r"],
                "test_profit_factor": summary["profit_factor"],
                "positive_selected_fold_rate": float(
                    (pd.to_numeric(fold_group["test_net_points"], errors="coerce") > 0).mean()
                ),
                "min_test_fold_net_points": float(pd.to_numeric(fold_group["test_net_points"], errors="coerce").min()),
                "test_baseline_net_points": baseline_net,
                "test_net_improvement": summary["net_points"] - baseline_net,
                "avg_train_score": float(pd.to_numeric(fold_group["train_score"], errors="coerce").mean()),
                "avg_train_win_rate": float(pd.to_numeric(fold_group["train_win_rate"], errors="coerce").mean()),
                "avg_train_payoff_ratio_r": float(pd.to_numeric(fold_group["train_payoff_ratio_r"], errors="coerce").mean()),
            }
        )
    aggregate = pd.DataFrame(rows)
    aggregate["future_pass"] = (
        (pd.to_numeric(aggregate["test_net_points"], errors="coerce") > 0.0)
        & (pd.to_numeric(aggregate["test_win_rate"], errors="coerce") > 0.53)
        & (pd.to_numeric(aggregate["test_payoff_ratio_r"], errors="coerce") > 1.0)
    )
    score_frame = aggregate.rename(
        columns={
            "test_net_points": "net_points",
            "test_win_rate": "win_rate",
            "test_payoff_ratio_r": "payoff_ratio_r",
            "test_profit_factor": "profit_factor",
            "min_test_fold_net_points": "min_fold_net_points",
            "test_trades": "trades",
        }
    )
    score_frame["max_drawdown_points"] = pd.to_numeric(score_frame["net_points"], errors="coerce").abs().clip(lower=1.0)
    score_frame["positive_fold_rate"] = pd.to_numeric(score_frame["positive_selected_fold_rate"], errors="coerce")
    aggregate["future_score"] = robust_score(score_frame)
    return aggregate.sort_values(
        ["future_pass", "future_score", "test_net_points"],
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
    future_pass_count = int(aggregate["future_pass"].sum()) if not aggregate.empty else 0
    lines = [
        "# NQ High Win-Rate / 1R Payoff Past-Fold Validation",
        "",
        "This validates previously mined high-win/payoff state filters by selecting filters from past folds only, then testing them on future folds.",
        "",
        f"- Feature set input: `{args.feature_sets}`",
        f"- Trades input: `{args.trades_input}`",
        f"- Fold rows tested: `{len(fold_results):,}`",
        f"- Aggregate rows: `{len(aggregate):,}`",
        f"- Future-pass aggregate rows: `{future_pass_count:,}`",
        f"- Total selected-filter future net points: `{total_net:.3f}`",
        f"- Same candidate unfiltered future net points: `{baseline_net:.3f}`",
        f"- Future net improvement: `{total_net - baseline_net:.3f}`",
        f"- Gates: train win_rate > `{args.min_train_win_rate:.2%}`, train payoff_ratio_r > `{args.min_train_payoff_ratio:.2f}`, min_train_trades >= `{args.min_train_trades}`, min_train_folds >= `{args.min_train_folds}`",
        "",
    ]
    if aggregate.empty:
        lines.append("No filters survived past-fold selection.")
    else:
        lines.extend(
            [
                "## Future-Validated Feature Sets",
                "",
                "```csv",
                aggregate.head(args.top_n).to_csv(index=False).strip(),
                "```",
                "",
                "## Interpretation",
                "",
                "- Rows with `future_pass=True` kept win rate >53%, payoff >1R, and positive net points out of sample.",
                "- Rows selected in only one future fold remain weaker evidence even if profitable.",
                "- If a row was profitable only in post-filter mining but not here, treat it as likely overfit or regime-specific.",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate high-win/payoff NQ state filters using past-fold selection.")
    parser.add_argument("--features-cache", default=".tmp/nq-bar-5y-continuous-features-cache.pkl")
    parser.add_argument("--trades-input", default=".tmp/nq-bar-5y-directional-walkforward-trades.csv")
    parser.add_argument("--feature-sets", default="reports/NQ-5y-high-win-payoff-feature-sets.csv")
    parser.add_argument("--fold-output", default=".tmp/nq-high-win-payoff-past-fold-validation.csv")
    parser.add_argument("--aggregate-output", default=".tmp/nq-high-win-payoff-past-fold-validation-aggregate.csv")
    parser.add_argument("--report-csv", default="reports/NQ-5y-high-win-payoff-past-fold-validation.csv")
    parser.add_argument("--report", default="reports/NQ-5y-high-win-payoff-past-fold-validation.md")
    parser.add_argument("--min-train-folds", type=int, default=2)
    parser.add_argument("--min-train-trades", type=int, default=60)
    parser.add_argument("--min-train-win-rate", type=float, default=0.53)
    parser.add_argument("--min-train-payoff-ratio", type=float, default=1.0)
    parser.add_argument("--min-train-net-points", type=float, default=0.0)
    parser.add_argument("--min-train-positive-fold-rate", type=float, default=0.50)
    parser.add_argument("--max-fold-candidates", type=int, default=10)
    parser.add_argument("--require-negative-baseline", action="store_true")
    parser.add_argument("--top-n", type=int, default=30)
    args = parser.parse_args()

    features = load_features(args.features_cache)
    trades = attach_state(load_trades(args.trades_input), features)
    allowed_pairs = load_allowed_pairs(args.feature_sets, require_negative_baseline=args.require_negative_baseline)
    fold_results, trade_results = validate_past_folds(
        trades,
        allowed_pairs,
        min_train_folds=args.min_train_folds,
        min_train_trades=args.min_train_trades,
        min_train_win_rate=args.min_train_win_rate,
        min_train_payoff_ratio=args.min_train_payoff_ratio,
        min_train_net_points=args.min_train_net_points,
        min_train_positive_fold_rate=args.min_train_positive_fold_rate,
        max_fold_candidates=args.max_fold_candidates,
    )
    aggregate = aggregate_results(fold_results, trade_results)
    for output_path, frame in [
        (Path(args.fold_output), fold_results),
        (Path(args.aggregate_output), aggregate),
        (Path(args.report_csv), aggregate),
    ]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output_path, index=False)
    write_report(Path(args.report), aggregate, fold_results, args)
    print(
        json.dumps(
            {
                "allowed_pairs": len(allowed_pairs),
                "feature_rows": int(len(features)),
                "trade_rows": int(len(trades)),
                "fold_result_rows": int(len(fold_results)),
                "aggregate_rows": int(len(aggregate)),
                "future_pass_rows": int(aggregate["future_pass"].sum()) if not aggregate.empty else 0,
                "fold_output": args.fold_output,
                "aggregate_output": args.aggregate_output,
                "report_csv": args.report_csv,
                "report": args.report,
                "top_validated_feature_set": aggregate.iloc[0].to_dict() if not aggregate.empty else None,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
