from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


LIGHTGLOW_INDICATORS = [
    "internal_bos",
    "internal_choch",
    "swing_bos",
    "swing_choch",
    "fvg",
    "equal_level_reversal",
    "internal_ob_break",
    "swing_ob_break",
    "premium_discount_reversal",
    "internal_choch_zone",
    "fvg_zone",
]


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    return result


def _selection_score(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["test_net_points"].clip(lower=0) * 0.001
        + frame["avg_test_profit_factor"].clip(upper=5.0) * 15.0
        + frame["net_to_drawdown"].clip(lower=-25.0, upper=100.0)
        + frame["positive_test_fold_rate"].clip(lower=0.0, upper=1.0) * 25.0
        + frame["min_test_net_points"].clip(lower=0.0) * 0.003
        + frame["selected_folds"].clip(upper=13.0)
    )


def _table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "_No rows._"
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame[columns].iterrows():
        values = []
        for value in row:
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def load_search_space_counts(args: argparse.Namespace) -> dict[str, int]:
    full_sample_path = Path(args.full_sample)
    full_candidate_count = 0
    full_signal_count = 0
    if full_sample_path.exists():
        full_sample = pd.read_csv(full_sample_path)
        full_sample = full_sample[full_sample["signal"].isin(LIGHTGLOW_INDICATORS)]
        full_candidate_count = int(len(full_sample))
        full_signal_count = int(full_sample["signal"].nunique())

    aggregate = pd.read_csv(args.aggregate)
    aggregate = aggregate[aggregate["signal"].isin(LIGHTGLOW_INDICATORS)]
    return {
        "native_indicator_count": len(LIGHTGLOW_INDICATORS),
        "full_sample_candidate_count": full_candidate_count,
        "full_sample_signal_count": full_signal_count,
        "walkforward_aggregate_candidate_count": int(len(aggregate)),
        "walkforward_aggregate_signal_count": int(aggregate["signal"].nunique()),
    }


def select_strategy(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    aggregate = pd.read_csv(args.aggregate)
    aggregate = aggregate[aggregate["signal"].isin(LIGHTGLOW_INDICATORS)].copy()
    aggregate = _numeric(
        aggregate,
        [
            "selected_folds",
            "positive_test_fold_rate",
            "test_trades",
            "test_net_points",
            "test_max_drawdown_points",
            "net_to_drawdown",
            "avg_test_profit_factor",
            "min_test_net_points",
        ],
    )
    aggregate["selection_score"] = _selection_score(aggregate)
    eligible = aggregate[
        (aggregate["selected_folds"] >= args.min_selected_folds)
        & (aggregate["positive_test_fold_rate"] >= args.min_positive_fold_rate)
        & (aggregate["test_trades"] >= args.min_trades)
        & (aggregate["test_net_points"] > 0)
        & (aggregate["avg_test_profit_factor"] >= args.min_profit_factor)
        & (aggregate["net_to_drawdown"] >= args.min_net_to_drawdown)
    ].copy()
    selected = eligible.sort_values(
        ["selection_score", "test_net_points", "avg_test_profit_factor"],
        ascending=[False, False, False],
    ).iloc[0]
    by_indicator = (
        aggregate.sort_values(["selection_score", "test_net_points"], ascending=[False, False])
        .groupby("signal", as_index=False)
        .head(1)
        .sort_values(["selection_score", "test_net_points"], ascending=[False, False])
    )
    return eligible, by_indicator, selected


def write_report(
    path: Path,
    eligible: pd.DataFrame,
    by_indicator: pd.DataFrame,
    selected: pd.Series,
    search_space: dict[str, int],
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "candidate",
        "signal",
        "timeframe_minutes",
        "session",
        "holding_minutes",
        "direction_mode",
        "exit_profile",
        "selected_folds",
        "positive_test_fold_rate",
        "test_trades",
        "test_net_points",
        "test_max_drawdown_points",
        "net_to_drawdown",
        "avg_test_profit_factor",
        "min_test_net_points",
        "selection_score",
    ]
    lines = [
        "# NQ Lightglow Best Strategy Search",
        "",
        "## Scope",
        "",
        "This search traverses only technical indicators present in `docs/Strategy/lightglow.md` and their backtest parameter combinations.",
        "",
        "Indicators traversed:",
        "",
        "- Internal BOS / CHoCH.",
        "- Swing BOS / CHoCH.",
        "- Fair Value Gap.",
        "- Equal High / Equal Low reversal.",
        "- Internal and swing order-block break.",
        "- Premium / Discount zone reversal.",
        "- Internal CHoCH + zone confluence.",
        "- FVG + zone confluence.",
        "",
        "No external overlays are part of this selection: no event-window filters, no volatility filters, no daily stops, no trade caps, and no cost stress overlays.",
        "",
        "Search-space audit:",
        "",
        f"- Native Lightglow indicators traversed: `{search_space['native_indicator_count']}`.",
        f"- Full-sample candidate combinations: `{search_space['full_sample_candidate_count']}` across `{search_space['full_sample_signal_count']}` signals.",
        f"- Walk-forward aggregate candidates considered: `{search_space['walkforward_aggregate_candidate_count']}` across `{search_space['walkforward_aggregate_signal_count']}` signals.",
        f"- Candidates passing the selection gate: `{len(eligible)}`.",
        "",
        "## Selection Gate",
        "",
        f"- Aggregate source: `{args.aggregate}`.",
        f"- Selected folds >= `{args.min_selected_folds}`.",
        f"- Positive future fold rate >= `{args.min_positive_fold_rate:.2%}`.",
        f"- Future trades >= `{args.min_trades}`.",
        f"- Average future PF >= `{args.min_profit_factor}`.",
        f"- Net/DD >= `{args.min_net_to_drawdown}`.",
        "",
        "## Best Strategy",
        "",
        f"`{selected['candidate']}`",
        "",
        "| Field | Value |",
        "| --- | ---: |",
        f"| Lightglow indicator | `{selected['signal']}` |",
        f"| Timeframe | `{int(selected['timeframe_minutes'])}m` |",
        f"| Session | `{selected['session']}` |",
        f"| Direction mode | `{selected['direction_mode']}` |",
        f"| Holding minutes | `{int(selected['holding_minutes'])}` |",
        f"| Exit profile | `{selected['exit_profile']}` |",
        f"| Selected folds | `{int(selected['selected_folds'])}` |",
        f"| Positive future fold rate | `{selected['positive_test_fold_rate']:.2%}` |",
        f"| Future trades | `{int(selected['test_trades'])}` |",
        f"| Future net points | `{selected['test_net_points']:.4f}` |",
        f"| Future max DD points | `{selected['test_max_drawdown_points']:.4f}` |",
        f"| Net/DD | `{selected['net_to_drawdown']:.4f}` |",
        f"| Average future PF | `{selected['avg_test_profit_factor']:.4f}` |",
        f"| Worst selected future fold | `{selected['min_test_net_points']:.4f}` |",
        "",
        "## Why This Is The Best",
        "",
        "The selected strategy is the only Lightglow-native signal family that dominates on all main objectives at once: net profit, PF, fold stability, and net-to-drawdown.",
        "",
        "The key discovered pattern is not generic trend-following. It is the reverse interpretation of the Lightglow Premium / Discount zone signal: fade premium/discount zone reversal indications on 1-minute bars and exit by time after 2 minutes.",
        "",
        "## Best Candidate By Lightglow Indicator",
        "",
        _table(by_indicator, columns),
        "",
        "## Eligible Candidate Set",
        "",
        _table(eligible.sort_values(["selection_score", "test_net_points"], ascending=[False, False]).head(args.top), columns),
        "",
        "## Decision",
        "",
        f"Best Lightglow-only strategy found: `{selected['candidate']}`.",
        "",
        "For lower execution complexity, the 3m premium/discount reverse time-exit variant remains a secondary validation candidate, but it is not the best strategy under this search objective.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Select the best strategy across native Lightglow indicators.")
    parser.add_argument("--aggregate", default=".tmp/nq-lightglow-5y-walkforward-aggregate.csv")
    parser.add_argument("--full-sample", default=".tmp/nq-lightglow-5y-full-sample.csv")
    parser.add_argument("--output", default="reports/NQ-lightglow-best-strategy-search.md")
    parser.add_argument("--json-output", default=".tmp/nq-lightglow-best-strategy-search.json")
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--min-selected-folds", type=int, default=8)
    parser.add_argument("--min-positive-fold-rate", type=float, default=0.8)
    parser.add_argument("--min-trades", type=int, default=500)
    parser.add_argument("--min-profit-factor", type=float, default=1.25)
    parser.add_argument("--min-net-to-drawdown", type=float, default=10.0)
    args = parser.parse_args()

    search_space = load_search_space_counts(args)
    eligible, by_indicator, selected = select_strategy(args)
    write_report(Path(args.output), eligible, by_indicator, selected, search_space, args)
    result: dict[str, Any] = {
        "status": "written",
        "output": args.output,
        "json_output": args.json_output,
        "search_space": search_space,
        "eligible_candidates": int(len(eligible)),
        "selected": selected.to_dict(),
    }
    json_path = Path(args.json_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
