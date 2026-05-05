from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def build_plan(recent_oos: pd.DataFrame, *, symbol: str, contract_month: str, max_candidates: int) -> pd.DataFrame:
    candidates = recent_oos[recent_oos["recent_verdict"].eq("passes_recent_oos")].copy()
    candidates = candidates.sort_values(["tier", "net_points", "profit_factor"], ascending=[True, False, False]).head(
        max_candidates
    )
    rows: list[dict[str, object]] = []
    for index, row in candidates.reset_index(drop=True).iterrows():
        strategy_id = str(row["candidate"])
        rows.append(
            {
                "priority": index + 1,
                "strategy_id": strategy_id,
                "filter": str(row["filter"]),
                "tier": str(row["tier"]),
                "symbol": symbol,
                "contract_month": contract_month,
                "quantity": 1,
                "submit_mode": "blocked_until_nq_bar_live_adapter_exists",
                "recent_trades": int(row["trades"]),
                "recent_net_points": float(row["net_points"]),
                "recent_profit_factor": float(row["profit_factor"]),
                "recent_positive_month_rate": float(row["positive_month_rate"]),
                "recent_min_month_net_points": float(row["min_month_net_points"]),
                "min_paper_outcomes": 20,
                "min_paper_net_points": 0.0,
                "min_paper_win_rate": 45.0,
                "max_consecutive_losses": 3,
                "max_daily_loss_points": 50.0,
                "max_open_positions": 1,
                "paper_duration": "20 outcomes or 4 calendar weeks, whichever comes later",
                "implementation_status": "needs_nq_bar_live_signal_adapter",
                "promotion_rule": "promote only if adapter dry-run is clean, paper gate passes, and recent OOS remains positive",
                "halt_rule": "halt if 3 consecutive losses, -50 points paper drawdown, or IBKR readiness blocker appears",
                "adapter_gap": "run_ibkr_live_paper_trader currently supports MBP live_strategy families, not these bar_best NQ strategy IDs",
                "dry_run_command_after_adapter": paper_command(strategy_id, symbol, contract_month, submit=False),
                "submit_command_after_adapter": paper_command(strategy_id, symbol, contract_month, submit=True),
                "summary_command": summary_command(strategy_id),
            }
        )
    return pd.DataFrame(rows)


def paper_command(strategy_id: str, symbol: str, contract_month: str, *, submit: bool) -> str:
    parts = [
        ".venv/bin/python scripts/run_ibkr_live_paper_trader.py",
        "--signal-mode strategy",
        f"--strategy-id {strategy_id}",
        f"--selected-alias {strategy_id}",
        f"--symbol {symbol}",
        f"--contract-month {contract_month}",
        "--quantity 1",
        "--paper-validation-accrual-mode",
        "--min-paper-outcomes 20",
        "--min-paper-net-points 0",
        "--min-paper-win-rate 45",
        "--max-consecutive-losses 3",
        "--daemon",
        "--interval-seconds 30",
        "--max-iterations 0",
    ]
    if submit:
        parts.append("--submit")
    return " ".join(parts)


def summary_command(strategy_id: str) -> str:
    return (
        ".venv/bin/python scripts/summarize_paper_validation.py "
        f"--strategy-id {strategy_id} "
        f"--output .tmp/paper-validation-{strategy_id}.csv"
    )


def write_report(path: Path, plan: pd.DataFrame, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NQ Paper Validation Plan",
        "",
        "This plan moves only recent-OOS-passing NQ candidates into small-size IBKR paper validation.",
        "",
        f"- Recent OOS input: `{args.recent_oos}`",
        f"- Symbol: `{args.symbol}`",
        f"- Contract month: `{args.contract_month}`",
        f"- Planned candidates: `{len(plan):,}`",
        "",
    ]
    if plan.empty:
        lines.extend(["No candidates passed recent OOS.", ""])
    else:
        lines.extend(["## Candidate Plan", "", "```csv", plan.to_csv(index=False).strip(), "```", ""])
    lines.extend(
        [
            "## Operating Rules",
            "",
            "- Do not submit these NQ bar strategies until a live signal adapter exists for `bar_best_*` strategy IDs.",
            "- After the adapter is implemented, start in dry-run mode for one session to verify live signal generation, IBKR readiness, and duplicate/exposure guards.",
            "- Switch to `--submit` only after dry-run events are clean and the account is confirmed paper.",
            "- Trade one candidate at a time unless separate client IDs and audit files are configured.",
            "- Do not promote any strategy to live until paper validation has at least 20 outcomes, non-negative net points, win rate >= 45%, and no more than 3 consecutive losses.",
            "- Halt immediately on IBKR readiness blockers, unexpected real account detection, existing exposure conflicts, or paper drawdown beyond 50 NQ points.",
            "",
            "## Decision",
            "",
            "- Next optimization step is implementing the NQ bar live signal adapter, not additional feature mining.",
            "- Prefer unfiltered candidates when recent state filters do not improve over baseline.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build NQ paper validation plan.")
    parser.add_argument("--recent-oos", default=".tmp/nq-promotion-recent-oos.csv")
    parser.add_argument("--output", default=".tmp/nq-paper-validation-plan.csv")
    parser.add_argument("--report", default="reports/NQ-paper-validation-plan.md")
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--contract-month", default="202606")
    parser.add_argument("--max-candidates", type=int, default=3)
    args = parser.parse_args()

    plan = build_plan(
        pd.read_csv(args.recent_oos),
        symbol=args.symbol.upper(),
        contract_month=args.contract_month,
        max_candidates=args.max_candidates,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    plan.to_csv(output, index=False)
    write_report(Path(args.report), plan, args)
    print(
        json.dumps(
            {
                "rows": int(len(plan)),
                "output": str(output),
                "report": args.report,
                "strategies": plan["strategy_id"].tolist() if not plan.empty else [],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
