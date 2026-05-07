from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


def _score_candidates(frame: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    data = frame.copy()
    data["selected_folds"] = pd.to_numeric(data["selected_folds"], errors="coerce").fillna(0)
    data["positive_test_fold_rate"] = pd.to_numeric(data["positive_test_fold_rate"], errors="coerce").fillna(0.0)
    data["test_trades"] = pd.to_numeric(data["test_trades"], errors="coerce").fillna(0)
    data["test_net_points"] = pd.to_numeric(data["test_net_points"], errors="coerce").fillna(0.0)
    data["test_max_drawdown_points"] = pd.to_numeric(data["test_max_drawdown_points"], errors="coerce").fillna(0.0)
    data["net_to_drawdown"] = pd.to_numeric(data["net_to_drawdown"], errors="coerce").fillna(0.0)
    data["avg_test_profit_factor"] = pd.to_numeric(data["avg_test_profit_factor"], errors="coerce").fillna(0.0)
    data["min_test_net_points"] = pd.to_numeric(data["min_test_net_points"], errors="coerce").fillna(0.0)
    filtered = data[
        (data["selected_folds"] >= args.min_selected_folds)
        & (data["positive_test_fold_rate"] >= args.min_positive_fold_rate)
        & (data["test_trades"] >= args.min_trades)
        & (data["test_net_points"] > 0)
        & (data["test_max_drawdown_points"] <= args.max_drawdown_points)
        & (data["avg_test_profit_factor"] >= args.min_profit_factor)
        & (data["net_to_drawdown"] >= args.min_net_to_drawdown)
        & (data["min_test_net_points"] >= args.min_worst_fold_points)
    ].copy()
    if filtered.empty:
        return filtered
    filtered["controlled_risk_score"] = (
        filtered["test_net_points"].clip(lower=0) * args.net_weight
        + filtered["avg_test_profit_factor"].clip(upper=5) * args.pf_weight
        + filtered["net_to_drawdown"].clip(upper=100) * args.net_dd_weight
        + filtered["positive_test_fold_rate"] * args.fold_weight
        + filtered["min_test_net_points"].clip(lower=0) * args.worst_fold_weight
    )
    return filtered.sort_values(
        ["controlled_risk_score", "test_net_points", "avg_test_profit_factor", "net_to_drawdown"],
        ascending=[False, False, False, False],
    )


def _markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "_No candidates passed the filters._"
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


def write_report(path: Path, ranked: pd.DataFrame, args: argparse.Namespace) -> None:
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
        "controlled_risk_score",
    ]
    available_columns = [column for column in columns if column in ranked.columns]
    lines = [
        "# Lightglow Strategy Candidate Ranking",
        "",
        "## Filters",
        "",
        f"- Source aggregate: `{args.aggregate}`.",
        f"- Minimum selected folds: `{args.min_selected_folds}`.",
        f"- Minimum positive fold rate: `{args.min_positive_fold_rate:.2%}`.",
        f"- Minimum trades: `{args.min_trades}`.",
        f"- Maximum drawdown points: `{args.max_drawdown_points}`.",
        f"- Minimum PF: `{args.min_profit_factor}`.",
        f"- Minimum net/DD: `{args.min_net_to_drawdown}`.",
        f"- Minimum worst fold points: `{args.min_worst_fold_points}`.",
        "",
        "## Ranked Candidates",
        "",
        _markdown_table(ranked.head(args.top), available_columns),
        "",
        "## Next Search Command",
        "",
        "Use a focused stop/target expansion instead of the full signal universe:",
        "",
        "```bash",
        ".venv/bin/python scripts/backtest_lightglow_nq_bars.py \\",
        "  --signals premium_discount_reversal internal_choch_zone fvg_zone \\",
        "  --timeframes 1 3 5 15 \\",
        "  --sessions all us_late us_rth \\",
        "  --hold-bars 1 2 3 5 \\",
        "  --direction-modes reverse native \\",
        "  --exit-profiles time sl8_tp8 sl8_tp12 sl8_tp16 sl12_tp12 sl12_tp18 sl12_tp24 sl16_tp16 sl16_tp24 sl16_tp32 \\",
        "  --output .tmp/nq-lightglow-expanded-walkforward.csv \\",
        "  --aggregate-output .tmp/nq-lightglow-expanded-aggregate.csv \\",
        "  --trades-output .tmp/nq-lightglow-expanded-trades.csv \\",
        "  --full-sample-output .tmp/nq-lightglow-expanded-full-sample.csv \\",
        "  --report reports/NQ-lightglow-expanded-strategy-search.md",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank Lightglow walk-forward candidates by net profit, PF, and controlled risk.")
    parser.add_argument("--aggregate", default=".tmp/nq-lightglow-5y-walkforward-aggregate.csv")
    parser.add_argument("--output", default="reports/NQ-lightglow-strategy-candidate-ranking.md")
    parser.add_argument("--json-output", default=".tmp/nq-lightglow-strategy-candidate-ranking.json")
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--min-selected-folds", type=int, default=8)
    parser.add_argument("--min-positive-fold-rate", type=float, default=0.8)
    parser.add_argument("--min-trades", type=int, default=500)
    parser.add_argument("--max-drawdown-points", type=float, default=2000.0)
    parser.add_argument("--min-profit-factor", type=float, default=1.25)
    parser.add_argument("--min-net-to-drawdown", type=float, default=10.0)
    parser.add_argument("--min-worst-fold-points", type=float, default=0.0)
    parser.add_argument("--net-weight", type=float, default=0.001)
    parser.add_argument("--pf-weight", type=float, default=10.0)
    parser.add_argument("--net-dd-weight", type=float, default=1.0)
    parser.add_argument("--fold-weight", type=float, default=10.0)
    parser.add_argument("--worst-fold-weight", type=float, default=0.002)
    args = parser.parse_args()

    aggregate = pd.read_csv(args.aggregate)
    ranked = _score_candidates(aggregate, args)
    write_report(Path(args.output), ranked, args)
    result: dict[str, Any] = {
        "status": "written",
        "aggregate": args.aggregate,
        "output": args.output,
        "json_output": args.json_output,
        "passing_candidates": int(len(ranked)),
        "top_candidate": ranked.iloc[0].to_dict() if not ranked.empty else None,
    }
    json_path = Path(args.json_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
