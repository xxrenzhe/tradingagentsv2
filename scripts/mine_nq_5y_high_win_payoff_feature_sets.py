from __future__ import annotations

import argparse
import json
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
)


def payoff_summary(frame: pd.DataFrame) -> dict[str, float]:
    net = pd.to_numeric(frame["net_points"], errors="coerce").dropna()
    if net.empty:
        return empty_summary()
    wins = net[net > 0]
    losses = net[net < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(abs(losses.sum()))
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(abs(losses.mean())) if len(losses) else 0.0
    payoff_ratio = float(avg_win / avg_loss) if avg_loss else float("inf")
    profit_factor = float(gross_profit / gross_loss) if gross_loss else float("inf")
    return {
        "trades": float(len(net)),
        "net_points": float(net.sum()),
        "win_rate": float((net > 0).mean()),
        "avg_win_points": avg_win,
        "avg_loss_points": avg_loss,
        "payoff_ratio_r": payoff_ratio,
        "profit_factor": profit_factor,
        "avg_points": float(net.mean()),
        "max_drawdown_points": max_drawdown(net),
        **fold_summary(frame),
    }


def empty_summary() -> dict[str, float]:
    return {
        "trades": 0.0,
        "net_points": 0.0,
        "win_rate": 0.0,
        "avg_win_points": 0.0,
        "avg_loss_points": 0.0,
        "payoff_ratio_r": 0.0,
        "profit_factor": 0.0,
        "avg_points": 0.0,
        "max_drawdown_points": 0.0,
        "folds": 0.0,
        "positive_fold_rate": 0.0,
        "min_fold_net_points": 0.0,
    }


def max_drawdown(net: pd.Series) -> float:
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    return float(drawdown.max()) if not drawdown.empty else 0.0


def fold_summary(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty or "fold" not in frame.columns:
        return {"folds": 0.0, "positive_fold_rate": 0.0, "min_fold_net_points": 0.0}
    fold_net = pd.to_numeric(frame["net_points"], errors="coerce").groupby(frame["fold"]).sum()
    if fold_net.empty:
        return {"folds": 0.0, "positive_fold_rate": 0.0, "min_fold_net_points": 0.0}
    return {
        "folds": float(len(fold_net)),
        "positive_fold_rate": float((fold_net > 0).mean()),
        "min_fold_net_points": float(fold_net.min()),
    }


def passes_gates(
    summary: dict[str, float],
    *,
    min_trades: int,
    min_folds: int,
    min_win_rate: float,
    min_payoff_ratio: float,
    min_net_points: float,
) -> bool:
    return (
        summary["trades"] >= min_trades
        and summary["folds"] >= min_folds
        and summary["win_rate"] > min_win_rate
        and summary["payoff_ratio_r"] > min_payoff_ratio
        and summary["net_points"] > min_net_points
    )


def mine_feature_sets(
    trades: pd.DataFrame,
    *,
    min_trades: int,
    min_folds: int,
    min_win_rate: float,
    min_payoff_ratio: float,
    min_net_points: float,
) -> pd.DataFrame:
    filters = candidate_filters(trades)
    rows: list[dict[str, object]] = []
    for candidate, group in trades.groupby("candidate", sort=False):
        baseline = payoff_summary(group)
        if passes_gates(
            baseline,
            min_trades=min_trades,
            min_folds=min_folds,
            min_win_rate=min_win_rate,
            min_payoff_ratio=min_payoff_ratio,
            min_net_points=min_net_points,
        ):
            rows.append(build_row(candidate, "none", "", group, baseline, baseline))
        for state_filter in filters:
            if not has_filter_columns(group, state_filter):
                continue
            selected = group[apply_filter(group, state_filter)].copy()
            summary = payoff_summary(selected)
            if not passes_gates(
                summary,
                min_trades=min_trades,
                min_folds=min_folds,
                min_win_rate=min_win_rate,
                min_payoff_ratio=min_payoff_ratio,
                min_net_points=min_net_points,
            ):
                continue
            rows.append(build_row(candidate, state_filter.name, describe_filter(state_filter), selected, summary, baseline))
    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame(rows)
    result["robust_score"] = robust_score(result)
    return result.sort_values(
        ["robust_score", "net_points", "win_rate", "payoff_ratio_r"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def has_filter_columns(frame: pd.DataFrame, state_filter: StateFilter) -> bool:
    return all(condition.column in frame.columns for condition in state_filter.conditions)


def build_row(
    candidate: str,
    filter_name: str,
    filter_conditions: str,
    selected: pd.DataFrame,
    summary: dict[str, float],
    baseline: dict[str, float],
) -> dict[str, object]:
    return {
        "candidate": candidate,
        "filter": filter_name,
        "filter_conditions": filter_conditions,
        "feature_set": candidate if filter_name == "none" else f"{candidate} + {filter_name}",
        "direction": direction_label(selected),
        "trades": int(summary["trades"]),
        "net_points": summary["net_points"],
        "win_rate": summary["win_rate"],
        "payoff_ratio_r": summary["payoff_ratio_r"],
        "avg_win_points": summary["avg_win_points"],
        "avg_loss_points": summary["avg_loss_points"],
        "profit_factor": summary["profit_factor"],
        "avg_points": summary["avg_points"],
        "max_drawdown_points": summary["max_drawdown_points"],
        "net_to_drawdown": summary["net_points"] / summary["max_drawdown_points"] if summary["max_drawdown_points"] else float("inf"),
        "folds": int(summary["folds"]),
        "positive_fold_rate": summary["positive_fold_rate"],
        "min_fold_net_points": summary["min_fold_net_points"],
        "baseline_trades": int(baseline["trades"]),
        "baseline_net_points": baseline["net_points"],
        "baseline_win_rate": baseline["win_rate"],
        "baseline_payoff_ratio_r": baseline["payoff_ratio_r"],
        "net_improvement": summary["net_points"] - baseline["net_points"],
        "retained_trade_rate": summary["trades"] / max(baseline["trades"], 1.0),
        "evidence_type": "base_strategy" if filter_name == "none" else "state_filtered",
    }


def direction_label(frame: pd.DataFrame) -> str:
    if frame.empty or "direction" not in frame.columns:
        return "unknown"
    directions = set(pd.to_numeric(frame["direction"], errors="coerce").dropna().astype(int).tolist())
    if directions == {1}:
        return "long"
    if directions == {-1}:
        return "short"
    if directions == {-1, 1}:
        return "both"
    return "unknown"


def robust_score(frame: pd.DataFrame) -> pd.Series:
    drawdown = pd.to_numeric(frame["max_drawdown_points"], errors="coerce").clip(lower=1.0)
    net_to_drawdown = pd.to_numeric(frame["net_points"], errors="coerce") / drawdown
    win_component = (pd.to_numeric(frame["win_rate"], errors="coerce") - 0.53).clip(lower=0.0) * 100.0
    payoff_component = (pd.to_numeric(frame["payoff_ratio_r"], errors="coerce") - 1.0).clip(lower=0.0) * 15.0
    fold_component = pd.to_numeric(frame["positive_fold_rate"], errors="coerce").fillna(0.0) * 4.0
    stress_penalty = pd.to_numeric(frame["min_fold_net_points"], errors="coerce").clip(upper=0.0).abs() / 250.0
    return net_to_drawdown + win_component + payoff_component + fold_component - stress_penalty


def format_number(value: object, digits: int = 2) -> str:
    number = float(value)
    if number == float("inf"):
        return "inf"
    return f"{number:.{digits}f}"


def write_report(path: Path, mined: pd.DataFrame, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NQ 5y High Win-Rate / 1R Payoff Feature Sets",
        "",
        "This report mines feature sets from existing 5-year NQ walk-forward trade rows.",
        "",
        f"- Trades input: `{args.trades_input}`",
        f"- Feature cache: `{args.features_cache}`",
        f"- Output: `{args.output}`",
        f"- Rows found: `{len(mined):,}`",
        f"- Gates: win_rate > `{args.min_win_rate:.2%}`, payoff_ratio_r > `{args.min_payoff_ratio:.2f}`, min_trades >= `{args.min_trades}`, min_folds >= `{args.min_folds}`, net_points > `{args.min_net_points}`",
        "",
        "Definitions:",
        "",
        "- `payoff_ratio_r` = average winning trade points / average losing trade points.",
        "- `feature_set` is either the base candidate itself or candidate plus a state filter.",
        "- State-filtered rows are post-filter research features and need past-fold selection before live use.",
        "",
    ]
    if mined.empty:
        lines.append("No feature sets passed the gates.")
    else:
        top = mined.head(args.top_n)
        lines.extend(
            [
                "## Top Feature Sets",
                "",
                "```csv",
                top.to_csv(index=False).strip(),
                "```",
                "",
                "## Practical Readout",
                "",
            ]
        )
        base_count = int((mined["evidence_type"] == "base_strategy").sum())
        filtered_count = int((mined["evidence_type"] == "state_filtered").sum())
        best = mined.iloc[0]
        lines.extend(
            [
                f"- Passing base strategies: `{base_count}`.",
                f"- Passing state-filtered feature sets: `{filtered_count}`.",
                f"- Top row: `{best['feature_set']}` with win_rate `{float(best['win_rate']):.2%}`, payoff_ratio_r `{format_number(best['payoff_ratio_r'])}`, net_points `{format_number(best['net_points'], 1)}`.",
                "- Treat high-scoring state filters as research candidates, not production rules, until selected only from prior folds and rechecked on recent OOS.",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine NQ 5y feature sets with win rate > 53% and payoff ratio > 1R.")
    parser.add_argument("--features-cache", default=".tmp/nq-bar-5y-continuous-features-cache.pkl")
    parser.add_argument("--trades-input", default=".tmp/nq-bar-5y-directional-walkforward-trades.csv")
    parser.add_argument("--output", default=".tmp/nq-5y-high-win-payoff-feature-sets.csv")
    parser.add_argument("--report-csv", default="reports/NQ-5y-high-win-payoff-feature-sets.csv")
    parser.add_argument("--report", default="reports/NQ-5y-high-win-payoff-feature-sets.md")
    parser.add_argument("--min-trades", type=int, default=80)
    parser.add_argument("--min-folds", type=int, default=2)
    parser.add_argument("--min-win-rate", type=float, default=0.53)
    parser.add_argument("--min-payoff-ratio", type=float, default=1.0)
    parser.add_argument("--min-net-points", type=float, default=0.0)
    parser.add_argument("--top-n", type=int, default=30)
    args = parser.parse_args()

    features = load_features(args.features_cache)
    trades = attach_state(load_trades(args.trades_input), features)
    mined = mine_feature_sets(
        trades,
        min_trades=args.min_trades,
        min_folds=args.min_folds,
        min_win_rate=args.min_win_rate,
        min_payoff_ratio=args.min_payoff_ratio,
        min_net_points=args.min_net_points,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    mined.to_csv(output, index=False)
    report_csv = Path(args.report_csv)
    report_csv.parent.mkdir(parents=True, exist_ok=True)
    mined.to_csv(report_csv, index=False)
    write_report(Path(args.report), mined, args)
    print(
        json.dumps(
            {
                "feature_rows": int(len(features)),
                "trade_rows": int(len(trades)),
                "mined_rows": int(len(mined)),
                "base_rows": int((mined["evidence_type"] == "base_strategy").sum()) if not mined.empty else 0,
                "state_filtered_rows": int((mined["evidence_type"] == "state_filtered").sum()) if not mined.empty else 0,
                "output": str(output),
                "report_csv": str(report_csv),
                "report": args.report,
                "top_feature_set": mined.iloc[0].to_dict() if not mined.empty else None,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
