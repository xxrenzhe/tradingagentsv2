from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_INPUTS = [
    (".tmp/mbp-adaptive-portfolio.csv", "adaptive_portfolio"),
    (".tmp/mbp-selected-stability-optimized.csv", "selected_stability"),
    (".tmp/mbp-best-strategy-walkforward-neighbors.csv", "walkforward_neighbors"),
    (".tmp/mbp-enhanced-top10.csv", "enhanced_top10"),
    (".tmp/mbp-live-ready-top10.csv", "live_ready_top10"),
    (".tmp/mbp-refined-mean-reversion.csv", "refined_mean_reversion"),
    (".tmp/mbp-robust-top10.csv", "robust_top10"),
]


def load_candidate_results(inputs: list[tuple[str, str]]) -> pd.DataFrame:
    frames = []
    for path_text, universe in inputs:
        path = Path(path_text)
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        if frame.empty:
            continue
        frame = frame.copy()
        _normalize_candidate_columns(frame)
        frame["candidate_universe"] = universe
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    rows = pd.concat(frames, ignore_index=True, sort=False)
    rows = rows.loc[:, ~rows.columns.duplicated()]
    return rows


def _normalize_candidate_columns(frame: pd.DataFrame) -> None:
    fallback_columns = {
        "positive_fold_rate": ["wf_positive_fold_rate"],
        "min_fold_net_points": ["wf_test_net_points"],
        "positive_window_rate": ["full_positive_window_rate"],
        "min_window_net_points": ["full_min_window_net_points"],
        "cost_3x_net_points": ["full_cost_3x_net_points", "stress_net_points"],
        "cost_3x_score": ["full_cost_3x_score"],
    }
    for target, fallbacks in fallback_columns.items():
        if target not in frame.columns:
            frame[target] = pd.NA
        for fallback in fallbacks:
            if fallback in frame.columns:
                frame[target] = frame[target].fillna(frame[fallback])


def rank_candidates(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows
    ranked = rows.copy()
    _ensure_numeric(
        ranked,
        [
            "full_trades",
            "full_net_points",
            "full_max_drawdown_points",
            "full_profit_factor",
            "full_win_rate",
            "full_stability",
            "positive_fold_rate",
            "positive_window_rate",
            "min_window_net_points",
            "worst_cost_net_points",
            "cost_3x_net_points",
        ],
    )
    ranked["stress_net_points"] = ranked["cost_3x_net_points"].fillna(ranked["worst_cost_net_points"])
    if "stress_net_points" in rows.columns:
        ranked["stress_net_points"] = ranked["stress_net_points"].fillna(pd.to_numeric(rows["stress_net_points"], errors="coerce"))
    ranked["stress_net_points"] = ranked["stress_net_points"].fillna(0.0)
    ranked["risk_denominator"] = ranked["full_max_drawdown_points"].clip(lower=1.0)
    ranked["net_to_drawdown"] = ranked["full_net_points"] / ranked["risk_denominator"]
    ranked["stress_to_drawdown"] = ranked["stress_net_points"] / ranked["risk_denominator"]
    ranked["risk_control_pass"] = (
        (ranked["full_trades"] >= 200)
        & (ranked["full_profit_factor"] >= 1.45)
        & (ranked["positive_fold_rate"] >= 0.80)
        & (ranked["positive_window_rate"] >= 0.88)
        & (ranked["min_window_net_points"] >= 0)
        & (ranked["stress_net_points"] > 0)
    )
    ranked["stability_pass"] = ranked["full_stability"].fillna(0.0) >= 0.70
    ranked["best_strategy_score"] = (
        ranked["full_net_points"].clip(lower=0) * 0.30
        + ranked["stress_net_points"].clip(lower=0) * 0.22
        + ranked["net_to_drawdown"].clip(lower=0) * 150
        + ranked["stress_to_drawdown"].clip(lower=0) * 120
        + ranked["full_profit_factor"].clip(upper=3.0).fillna(0) * 320
        + ranked["full_stability"].clip(lower=0, upper=1).fillna(0) * 900
        + ranked["positive_fold_rate"].fillna(0) * 450
        + ranked["positive_window_rate"].fillna(0) * 650
        + ranked["min_window_net_points"].clip(lower=-500, upper=500).fillna(-500) * 0.35
        - ranked["full_max_drawdown_points"].fillna(0) * 0.35
    )
    ranked["selection_tier"] = "research_only"
    ranked.loc[ranked["risk_control_pass"], "selection_tier"] = "risk_controlled"
    ranked.loc[ranked["risk_control_pass"] & ranked["stability_pass"], "selection_tier"] = "balanced_best"
    ranked = ranked.sort_values(
        ["selection_tier", "best_strategy_score", "full_net_points", "stress_net_points"],
        ascending=[True, False, False, False],
        key=lambda series: series.map({"balanced_best": 0, "risk_controlled": 1, "research_only": 2}) if series.name == "selection_tier" else series,
    ).reset_index(drop=True)
    ranked = ranked.drop_duplicates(["name", "candidate_universe"], keep="first")
    return ranked


def _ensure_numeric(frame: pd.DataFrame, columns: list[str]) -> None:
    for column in columns:
        if column not in frame.columns:
            frame[column] = pd.NA
        frame[column] = pd.to_numeric(frame[column], errors="coerce")


def write_report(path: Path, ranked: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if ranked.empty:
        path.write_text("# NQM6 Best Strategy Ranking\n\nNo candidates found.\n", encoding="utf-8")
        return
    best = ranked.iloc[0]
    columns = [
        "selection_tier",
        "candidate_universe",
        "name",
        "full_trades",
        "full_net_points",
        "full_max_drawdown_points",
        "net_to_drawdown",
        "full_profit_factor",
        "full_win_rate",
        "full_stability",
        "positive_fold_rate",
        "positive_window_rate",
        "min_window_net_points",
        "stress_net_points",
        "best_strategy_score",
    ]
    lines = [
        "# NQM6 Best Strategy Ranking",
        "",
        "## Verdict",
        "",
        f"Best balanced candidate: `{best['name']}`.",
        "",
        "- Selection prioritizes high net points and 3x-cost net points, but requires controlled drawdown, PF, fold/window consistency, positive worst rolling window, and stability.",
        "- This is a research/backtest ranking, not permission to trade live without paper validation and order-routing checks.",
        "",
        "## Best Candidate Metrics",
        "",
        _markdown_table(pd.DataFrame([best])[columns]),
        "",
        "## Top Balanced Candidates",
        "",
        _markdown_table(ranked[ranked["selection_tier"].eq("balanced_best")].head(20)[columns]),
        "",
        "## Highest Net Alternatives",
        "",
        _markdown_table(ranked.sort_values(["full_net_points", "stress_net_points"], ascending=False).head(12)[columns]),
        "",
        "## Selection Criteria",
        "",
        "- Minimum 200 trades.",
        "- PF >= 1.45.",
        "- Positive fold rate >= 80%.",
        "- Positive 10-day rolling window rate >= 88%.",
        "- Worst 10-day rolling window net >= 0.",
        "- 3x-cost/stress net > 0.",
        "- Stability >= 0.70 for the top balanced tier.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    rows = ["| " + " | ".join(frame.columns) + " |", "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    for _, row in frame.iterrows():
        values = []
        for column in frame.columns:
            value = row[column]
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank MBP strategy candidates by profit, risk control, and stability.")
    parser.add_argument("--output", default=".tmp/mbp-best-strategy-ranking.csv")
    parser.add_argument("--report", default="reports/NQM6-best-strategy-ranking.md")
    args = parser.parse_args()

    rows = load_candidate_results(DEFAULT_INPUTS)
    ranked = rank_candidates(rows)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(output, index=False)
    write_report(Path(args.report), ranked)
    print(f"Candidates ranked: {len(ranked):,}")
    print(f"CSV: {output}")
    print(f"Report: {args.report}")
    if not ranked.empty:
        print(
            ranked.head(10)[
                [
                    "selection_tier",
                    "candidate_universe",
                    "name",
                    "full_net_points",
                    "full_max_drawdown_points",
                    "full_profit_factor",
                    "full_stability",
                    "positive_window_rate",
                    "min_window_net_points",
                    "stress_net_points",
                    "best_strategy_score",
                ]
            ].to_string(index=False)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
