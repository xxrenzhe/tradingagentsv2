from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from mine_nq_state_filtered_features import attach_state, candidate_filters, load_features, load_trades, summarize


def shortlist_candidates(shortlist: pd.DataFrame, tiers: set[str]) -> pd.DataFrame:
    frame = shortlist[shortlist["tier"].isin(tiers)].copy()
    return frame[["tier", "candidate", "filter", "evidence_type", "next_action"]].drop_duplicates()


def evaluate_recent(
    trades: pd.DataFrame,
    shortlist: pd.DataFrame,
    *,
    months: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    latest_ts = pd.to_datetime(trades["entry_ts"], utc=True).max()
    cutoff = latest_ts - pd.DateOffset(months=months)
    recent = trades[pd.to_datetime(trades["entry_ts"], utc=True) >= cutoff].copy()
    filters = None
    rows: list[dict[str, object]] = []
    monthly_rows: list[dict[str, object]] = []
    for _, item in shortlist.iterrows():
        candidate = str(item["candidate"])
        filter_name = str(item["filter"])
        candidate_trades = recent[recent["candidate"].eq(candidate)].copy()
        baseline = summarize(candidate_trades)
        selected = candidate_trades
        if filter_name != "none":
            if filters is None:
                filters = {state_filter.name: state_filter for state_filter in candidate_filters(trades)}
            state_filter = filters.get(filter_name)
            if state_filter is None:
                continue
            selected = candidate_trades[state_filter_mask(candidate_trades, state_filter)].copy()
        summary = summarize(selected)
        monthly = summarize_monthly(selected)
        net_improvement = summary["net_points"] - baseline["net_points"]
        verdict = recent_verdict(summary, monthly, net_improvement=net_improvement, filter_name=filter_name)
        rows.append(
            {
                "tier": item["tier"],
                "candidate": candidate,
                "filter": filter_name,
                "evidence_type": item["evidence_type"],
                "months": months,
                "recent_start": cutoff.date().isoformat(),
                "recent_end": latest_ts.date().isoformat(),
                "trades": summary["trades"],
                "net_points": summary["net_points"],
                "profit_factor": summary["profit_factor"],
                "win_rate": summary["win_rate"],
                "positive_month_rate": monthly["positive_month_rate"],
                "min_month_net_points": monthly["min_month_net_points"],
                "months_with_trades": monthly["months_with_trades"],
                "baseline_trades": baseline["trades"],
                "baseline_net_points": baseline["net_points"],
                "net_improvement": net_improvement,
                "recent_verdict": verdict,
                "next_action": recent_next_action(verdict, net_improvement=net_improvement, filter_name=filter_name),
            }
        )
        monthly_rows.extend(build_month_rows(item, selected))
    result = pd.DataFrame(rows)
    monthly_result = pd.DataFrame(monthly_rows)
    if not result.empty:
        result["verdict_rank"] = result["recent_verdict"].map(
            {
                "passes_recent_oos": 0,
                "watch_recent_oos": 1,
                "fails_recent_oos": 2,
                "insufficient_recent_trades": 3,
            }
        )
        result = result.sort_values(
            ["verdict_rank", "net_points", "profit_factor"],
            ascending=[True, False, False],
        ).drop(columns=["verdict_rank"]).reset_index(drop=True)
    return result, monthly_result


def state_filter_mask(frame: pd.DataFrame, state_filter) -> pd.Series:
    from mine_nq_state_filtered_features import apply_filter

    return apply_filter(frame, state_filter)


def summarize_monthly(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty:
        return {"months_with_trades": 0, "positive_month_rate": 0.0, "min_month_net_points": 0.0}
    monthly = (
        pd.to_numeric(frame["net_points"], errors="coerce")
        .groupby(month_labels(frame["entry_ts"]))
        .sum()
    )
    if monthly.empty:
        return {"months_with_trades": 0, "positive_month_rate": 0.0, "min_month_net_points": 0.0}
    return {
        "months_with_trades": int(len(monthly)),
        "positive_month_rate": float((monthly > 0).mean()),
        "min_month_net_points": float(monthly.min()),
    }


def build_month_rows(item: pd.Series, selected: pd.DataFrame) -> list[dict[str, object]]:
    if selected.empty:
        return []
    frame = selected.copy()
    frame["month"] = month_labels(frame["entry_ts"])
    grouped = pd.to_numeric(frame["net_points"], errors="coerce").groupby(frame["month"])
    rows: list[dict[str, object]] = []
    for month, net in grouped.sum().items():
        month_frame = frame[frame["month"].eq(month)]
        rows.append(
            {
                "tier": item["tier"],
                "candidate": item["candidate"],
                "filter": item["filter"],
                "month": month,
                "trades": int(len(month_frame)),
                "net_points": float(net),
                "win_rate": float((pd.to_numeric(month_frame["net_points"], errors="coerce") > 0).mean()),
            }
        )
    return rows


def month_labels(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, utc=True).dt.strftime("%Y-%m")


def recent_verdict(
    summary: dict[str, float],
    monthly: dict[str, float],
    *,
    net_improvement: float = 0.0,
    filter_name: str = "none",
) -> str:
    if summary["trades"] < 20 or monthly["months_with_trades"] < 3:
        return "insufficient_recent_trades"
    if (
        summary["net_points"] > 0
        and summary["profit_factor"] >= 1.20
        and monthly["positive_month_rate"] >= 0.50
        and monthly["min_month_net_points"] > -750.0
        and (filter_name == "none" or net_improvement >= 0.0)
    ):
        return "passes_recent_oos"
    if summary["net_points"] > 0 and summary["profit_factor"] >= 1.05:
        return "watch_recent_oos"
    return "fails_recent_oos"


def recent_next_action(verdict: str, *, net_improvement: float = 0.0, filter_name: str = "none") -> str:
    if verdict == "passes_recent_oos":
        return "paper_trade_small_size"
    if verdict == "watch_recent_oos":
        if filter_name != "none" and net_improvement < 0.0:
            return "prefer_unfiltered_baseline"
        return "keep_on_watchlist_with_tighter_risk"
    if verdict == "insufficient_recent_trades":
        return "collect_more_recent_trades"
    return "do_not_promote_without_rework"


def write_report(path: Path, result: pd.DataFrame, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NQ Promotion Shortlist Recent OOS Check",
        "",
        "This report evaluates promoted and paper-watchlist NQ candidates on the most recent trade window available in the 5-year trade rows.",
        "",
        f"- Shortlist: `{args.shortlist}`",
        f"- Trades input: `{args.trades_input}`",
        f"- Feature cache: `{args.features_cache}`",
        f"- Recent months: `{args.months}`",
        f"- Rows evaluated: `{len(result):,}`",
        "",
    ]
    for verdict in ["passes_recent_oos", "watch_recent_oos", "fails_recent_oos", "insufficient_recent_trades"]:
        rows = result[result["recent_verdict"].eq(verdict)].head(args.top_n)
        lines.extend([f"## {verdict}", ""])
        if rows.empty:
            lines.extend(["No rows.", ""])
        else:
            lines.extend(["```csv", rows.to_csv(index=False).strip(), "```", ""])
    lines.extend(
        [
            "## Decision",
            "",
            "- Candidates that pass recent OOS can move to small-size paper validation.",
            "- Candidates that fail recent OOS should not be promoted even if their 5-year aggregate looks strong.",
            "- Insufficient recent trade counts need more live/paper observation rather than parameter mining.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate NQ promotion shortlist on recent data.")
    parser.add_argument("--shortlist", default=".tmp/nq-feature-promotion-shortlist.csv")
    parser.add_argument("--features-cache", default=".tmp/nq-bar-5y-continuous-features-cache.pkl")
    parser.add_argument("--trades-input", default=".tmp/nq-bar-5y-directional-walkforward-trades.csv")
    parser.add_argument("--output", default=".tmp/nq-promotion-recent-oos.csv")
    parser.add_argument("--monthly-output", default=".tmp/nq-promotion-recent-oos-monthly.csv")
    parser.add_argument("--report", default="reports/NQ-promotion-recent-oos.md")
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--top-n", type=int, default=20)
    args = parser.parse_args()

    shortlist = shortlist_candidates(
        pd.read_csv(args.shortlist),
        tiers={"promote_to_strict_gate", "paper_watchlist"},
    )
    features = load_features(args.features_cache)
    trades = attach_state(load_trades(args.trades_input), features)
    result, monthly = evaluate_recent(trades, shortlist, months=args.months)
    output = Path(args.output)
    monthly_output = Path(args.monthly_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
    monthly.to_csv(monthly_output, index=False)
    write_report(Path(args.report), result, args)
    print(
        json.dumps(
            {
                "rows": int(len(result)),
                "monthly_rows": int(len(monthly)),
                "output": str(output),
                "monthly_output": str(monthly_output),
                "report": args.report,
                "verdict_counts": result["recent_verdict"].value_counts().to_dict() if not result.empty else {},
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
