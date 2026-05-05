from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def load_directional(path: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["candidate"] = frame["candidate"].astype(str)
    return frame


def load_state_filters(path: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["candidate"] = frame["candidate"].astype(str)
    frame["filter"] = frame["filter"].astype(str)
    return frame


def load_past_fold_validation(path: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["candidate"] = frame["candidate"].astype(str)
    frame["filter"] = frame["filter"].astype(str)
    return frame


def build_shortlist(directional: pd.DataFrame, state_filters: pd.DataFrame, past_fold: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, row in directional.iterrows():
        rows.append(
            {
                "tier": directional_tier(row),
                "candidate": row["candidate"],
                "filter": "none",
                "evidence_type": "directional_walkforward",
                "trades": int(row.get("full_trades", row.get("test_trades", 0))),
                "net_points": float(row.get("full_net_points", row.get("test_net_points", 0.0))),
                "profit_factor": float(row.get("full_profit_factor", row.get("avg_test_profit_factor", 0.0))),
                "positive_fold_rate": float(row.get("positive_fold_rate", row.get("positive_test_fold_rate", 0.0))),
                "stress_points": float(row.get("stress_net_points", row.get("min_test_net_points", 0.0))),
                "baseline_net_points": float(row.get("full_net_points", row.get("test_net_points", 0.0))),
                "net_improvement": 0.0,
                "selected_folds": int(row.get("selected_folds", 0)),
                "promotion_score": directional_score(row),
                "next_action": directional_next_action(row),
            }
        )
    for _, row in state_filters.iterrows():
        rows.append(
            {
                "tier": post_filter_tier(row),
                "candidate": row["candidate"],
                "filter": row["filter"],
                "evidence_type": "post_filter_mining",
                "trades": int(row["trades"]),
                "net_points": float(row["net_points"]),
                "profit_factor": float(row["profit_factor"]),
                "positive_fold_rate": float(row["positive_fold_rate"]),
                "stress_points": float(row["min_fold_net_points"]),
                "baseline_net_points": float(row["baseline_net_points"]),
                "net_improvement": float(row["net_improvement"]),
                "selected_folds": int(row["folds"]),
                "promotion_score": post_filter_score(row),
                "next_action": "validate_with_past_fold_selection",
            }
        )
    for _, row in past_fold.iterrows():
        rows.append(
            {
                "tier": past_fold_tier(row),
                "candidate": row["candidate"],
                "filter": row["filter"],
                "evidence_type": "past_fold_selected",
                "trades": int(row["test_trades"]),
                "net_points": float(row["test_net_points"]),
                "profit_factor": float(row["fold_net_profit_factor"]),
                "positive_fold_rate": float(row["positive_selected_fold_rate"]),
                "stress_points": float(row["min_test_fold_net_points"]),
                "baseline_net_points": float(row["test_baseline_net_points"]),
                "net_improvement": float(row["test_net_improvement"]),
                "selected_folds": int(row["selected_folds"]),
                "promotion_score": past_fold_score(row),
                "next_action": past_fold_next_action(row),
            }
        )
    shortlist = pd.DataFrame(rows)
    if shortlist.empty:
        return shortlist
    shortlist["tier_rank"] = shortlist["tier"].map(
        {
            "promote_to_strict_gate": 0,
            "paper_watchlist": 1,
            "validate_next": 2,
            "research_only": 3,
            "reject_for_now": 4,
        }
    )
    return shortlist.sort_values(
        ["tier_rank", "promotion_score", "net_points"],
        ascending=[True, False, False],
    ).drop(columns=["tier_rank"]).reset_index(drop=True)


def directional_tier(row: pd.Series) -> str:
    selected_folds = int(row.get("selected_folds", 0))
    trades = int(row.get("full_trades", row.get("test_trades", 0)))
    if bool(row.get("live_ready", False)):
        return "promote_to_strict_gate"
    if (
        selected_folds >= 2
        and trades >= 100
        and float(row.get("positive_fold_rate", 0.0)) >= 1.0
        and float(row.get("stress_net_points", row.get("min_test_net_points", 0.0))) > 0
        and float(row.get("full_profit_factor", row.get("avg_test_profit_factor", 0.0))) >= 1.45
    ):
        return "promote_to_strict_gate"
    if float(row.get("full_net_points", row.get("test_net_points", 0.0))) > 2500 and float(
        row.get("positive_fold_rate", row.get("positive_test_fold_rate", 0.0))
    ) >= 0.80:
        return "paper_watchlist"
    if (
        selected_folds >= 1
        and trades >= 50
        and float(row.get("positive_fold_rate", 0.0)) >= 1.0
        and float(row.get("stress_net_points", row.get("min_test_net_points", 0.0))) > 0
    ):
        return "validate_next"
    return "research_only"


def post_filter_tier(row: pd.Series) -> str:
    if (
        float(row["positive_fold_rate"]) >= 1.0
        and float(row["min_fold_net_points"]) > 0
        and float(row["profit_factor"]) >= 1.50
        and int(row["folds"]) >= 4
    ):
        return "validate_next"
    if float(row["net_points"]) > 2500 and float(row["profit_factor"]) >= 1.35:
        return "research_only"
    return "reject_for_now"


def past_fold_tier(row: pd.Series) -> str:
    selected_folds = int(row["selected_folds"])
    net_points = float(row["test_net_points"])
    positive_rate = float(row["positive_selected_fold_rate"])
    stress = float(row["min_test_fold_net_points"])
    improvement = float(row["test_net_improvement"])
    if selected_folds >= 3 and net_points > 0 and positive_rate >= 0.67 and stress > 0 and improvement > 0:
        return "promote_to_strict_gate"
    if selected_folds >= 2 and net_points > 0 and improvement > 0:
        return "paper_watchlist"
    if selected_folds >= 1 and net_points > 0:
        return "validate_next"
    return "reject_for_now"


def directional_score(row: pd.Series) -> float:
    return (
        float(row.get("full_net_points", row.get("test_net_points", 0.0))) * 0.25
        + float(row.get("full_profit_factor", row.get("avg_test_profit_factor", 0.0))) * 600.0
        + float(row.get("positive_fold_rate", row.get("positive_test_fold_rate", 0.0))) * 1200.0
        + min(float(row.get("stress_net_points", row.get("min_test_net_points", 0.0))), 0.0)
    )


def post_filter_score(row: pd.Series) -> float:
    return (
        float(row["net_points"]) * 0.20
        + float(row["profit_factor"]) * 500.0
        + float(row["positive_fold_rate"]) * 1000.0
        + float(row["net_improvement"]) * 0.10
        + min(float(row["min_fold_net_points"]), 0.0)
    )


def past_fold_score(row: pd.Series) -> float:
    return (
        float(row["test_net_points"]) * 0.40
        + float(row["fold_net_profit_factor"]) * 400.0
        + float(row["positive_selected_fold_rate"]) * 1200.0
        + float(row["test_net_improvement"]) * 0.25
        + min(float(row["min_test_fold_net_points"]), 0.0)
        + int(row["selected_folds"]) * 150.0
    )


def directional_next_action(row: pd.Series) -> str:
    if directional_tier(row) == "promote_to_strict_gate":
        return "integrate_into_strict_gate_and_recent_oos"
    if directional_tier(row) == "paper_watchlist":
        return "paper_trade_and_tighten_state_filter"
    return "keep_as_research_context"


def past_fold_next_action(row: pd.Series) -> str:
    if past_fold_tier(row) == "promote_to_strict_gate":
        return "integrate_into_strict_gate"
    if past_fold_tier(row) == "paper_watchlist":
        return "paper_trade_and_expand_oos"
    if past_fold_tier(row) == "validate_next":
        return "seek_more_repeat_folds"
    return "drop_or_rework"


def write_report(path: Path, shortlist: pd.DataFrame, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NQ Feature Promotion Shortlist",
        "",
        "This report combines directional 5-year walk-forward results, post-filter state mining, and past-fold selected validation.",
        "",
        f"- Directional ranking: `{args.directional_ranking}`",
        f"- State-filter mining: `{args.state_filters}`",
        f"- Past-fold validation: `{args.past_fold_validation}`",
        f"- Shortlist rows: `{len(shortlist):,}`",
        "",
    ]
    for tier in ["promote_to_strict_gate", "paper_watchlist", "validate_next", "research_only"]:
        tier_rows = shortlist[shortlist["tier"].eq(tier)].head(args.top_n)
        lines.extend([f"## {tier}", ""])
        if tier_rows.empty:
            lines.extend(["No rows.", ""])
        else:
            lines.extend(["```csv", tier_rows.to_csv(index=False).strip(), "```", ""])
    lines.extend(
        [
            "## Decision",
            "",
            "- Stop broad feature mining for now; it is producing many post-filter edges that do not survive strict past-fold validation.",
            "- Promote only the small set of stable base features and past-fold-positive state filters into stricter recent OOS / paper validation.",
            "- Continue optimization on validation gates, execution realism, and recency checks rather than adding more raw feature families.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build NQ feature promotion shortlist.")
    parser.add_argument("--directional-ranking", default=".tmp/nq-bar-5y-directional-strategy-ranking.csv")
    parser.add_argument("--state-filters", default=".tmp/nq-bar-5y-state-filtered-features.csv")
    parser.add_argument("--past-fold-validation", default=".tmp/nq-state-filter-past-fold-validation-aggregate.csv")
    parser.add_argument("--output", default=".tmp/nq-feature-promotion-shortlist.csv")
    parser.add_argument("--report", default="reports/NQ-feature-promotion-shortlist.md")
    parser.add_argument("--top-n", type=int, default=12)
    args = parser.parse_args()

    shortlist = build_shortlist(
        load_directional(args.directional_ranking),
        load_state_filters(args.state_filters),
        load_past_fold_validation(args.past_fold_validation),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    shortlist.to_csv(output, index=False)
    write_report(Path(args.report), shortlist, args)
    result = {
        "rows": int(len(shortlist)),
        "output": str(output),
        "report": args.report,
        "tier_counts": shortlist["tier"].value_counts().to_dict() if not shortlist.empty else {},
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
