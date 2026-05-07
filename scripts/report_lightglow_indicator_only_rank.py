from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


LIGHTGLOW_SIGNALS = [
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


def _metric_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame = frame[frame["signal"].isin(LIGHTGLOW_SIGNALS)].copy()
    for column in [
        "selected_folds",
        "positive_test_fold_rate",
        "test_trades",
        "test_net_points",
        "test_max_drawdown_points",
        "net_to_drawdown",
        "avg_test_profit_factor",
        "min_test_net_points",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    frame["indicator_only_score"] = (
        frame["test_net_points"].clip(lower=0) * 0.001
        + frame["avg_test_profit_factor"].clip(upper=5.0) * 10.0
        + frame["net_to_drawdown"].clip(lower=-50, upper=100)
        + frame["positive_test_fold_rate"].clip(lower=0, upper=1) * 20.0
        + frame["min_test_net_points"].clip(lower=0) * 0.002
    )
    return frame


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


def write_report(path: Path, frame: pd.DataFrame, args: argparse.Namespace) -> None:
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
        "indicator_only_score",
    ]
    stable = frame[
        (frame["selected_folds"] >= args.min_selected_folds)
        & (frame["positive_test_fold_rate"] >= args.min_positive_fold_rate)
        & (frame["test_trades"] >= args.min_trades)
        & (frame["test_net_points"] > 0)
    ].copy()
    by_signal = (
        stable.sort_values(["indicator_only_score", "test_net_points"], ascending=[False, False])
        .groupby("signal", as_index=False)
        .head(1)
        .sort_values(["indicator_only_score", "test_net_points"], ascending=[False, False])
    )
    lines = [
        "# NQ Lightglow Indicator-Only Ranking",
        "",
        "## Scope",
        "",
        "This report only ranks signals derived from `docs/Strategy/lightglow.md`: structure breaks, FVG, equal levels, order-block breaks, premium/discount zones, and Lightglow confluence variants.",
        "",
        "It deliberately excludes external overlays such as daily stops, trade caps, event windows, volatility filters, and execution-cost stress tests.",
        "",
        f"- Source aggregate: `{args.aggregate}`.",
        f"- Signals: `{', '.join(LIGHTGLOW_SIGNALS)}`.",
        f"- Stable filter: selected folds >= `{args.min_selected_folds}`, positive fold rate >= `{args.min_positive_fold_rate:.2%}`, trades >= `{args.min_trades}`, net > `0`.",
        "",
        "## Top Indicator-Only Candidates",
        "",
        _table(stable.sort_values(["indicator_only_score", "test_net_points"], ascending=[False, False]).head(args.top), columns),
        "",
        "## Best Candidate By Lightglow Signal",
        "",
        _table(by_signal, columns),
        "",
        "## Practical Reading",
        "",
        "- The ranking is a Lightglow-only research view, not a production readiness gate.",
        "- If an entry/exit profile is shown, it is part of the Lightglow backtest parameterization, not an external overlay.",
        "- The current strongest signal family is the premium/discount zone reversal used in reverse direction.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank only Lightglow-native indicator candidates.")
    parser.add_argument("--aggregate", default=".tmp/nq-lightglow-5y-walkforward-aggregate.csv")
    parser.add_argument("--output", default="reports/NQ-lightglow-indicator-only-ranking.md")
    parser.add_argument("--json-output", default=".tmp/nq-lightglow-indicator-only-ranking.json")
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--min-selected-folds", type=int, default=3)
    parser.add_argument("--min-positive-fold-rate", type=float, default=0.5)
    parser.add_argument("--min-trades", type=int, default=100)
    args = parser.parse_args()

    frame = _metric_frame(Path(args.aggregate))
    write_report(Path(args.output), frame, args)
    ranked = frame.sort_values(["indicator_only_score", "test_net_points"], ascending=[False, False])
    result: dict[str, Any] = {
        "status": "written",
        "output": args.output,
        "json_output": args.json_output,
        "top_candidate": ranked.iloc[0].to_dict() if not ranked.empty else None,
        "rows": int(len(frame)),
    }
    json_path = Path(args.json_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
