from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd

from tradingagents.config.env import load_project_env
from tradingagents.execution import PaperValidationGateConfig, summarize_paper_audits


def _feature_span(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "rows": 0, "start": None, "end": None, "calendar_days": 0}
    cache = pd.read_pickle(path)
    frames = [frame for frame in cache.values() if isinstance(frame, pd.DataFrame) and not frame.empty]
    if not frames:
        return {"path": str(path), "exists": True, "rows": 0, "start": None, "end": None, "calendar_days": 0}
    features = pd.concat(frames, ignore_index=True, sort=False)
    timestamps = pd.to_datetime(features["ts"], utc=True)
    start = timestamps.min()
    end = timestamps.max()
    return {
        "path": str(path),
        "exists": True,
        "rows": int(len(features)),
        "start": str(start),
        "end": str(end),
        "calendar_days": int((end.date() - start.date()).days) + 1,
    }


def _load_top_candidate(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "candidate": None}
    ranking = pd.read_csv(path)
    if ranking.empty:
        return {"path": str(path), "exists": True, "candidate": None}
    top = ranking.iloc[0].to_dict()
    numeric_columns = [
        "full_trades",
        "full_net_points",
        "full_max_drawdown_points",
        "full_profit_factor",
        "full_win_rate",
        "full_stability",
        "positive_fold_rate",
        "positive_window_rate",
        "min_window_net_points",
        "stress_net_points",
        "net_to_drawdown",
        "best_strategy_score",
    ]
    for column in numeric_columns:
        if column in top and pd.notna(top[column]):
            top[column] = float(top[column])
    return {
        "path": str(path),
        "exists": True,
        "candidate_count": int(len(ranking)),
        "balanced_best_count": int(ranking.get("selection_tier", pd.Series(dtype=str)).eq("balanced_best").sum()),
        "candidate": top,
    }


def _trade_diagnostics(path: Path, *, rolling_days: int, rolling_step_days: int) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "trades": 0}
    trades = pd.read_csv(path)
    if trades.empty:
        return {"path": str(path), "exists": True, "trades": 0}
    trades = trades.copy()
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["trade_date"] = pd.to_datetime(trades["trade_date"]).dt.date
    net = pd.to_numeric(trades["net_points"], errors="coerce")
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    daily = trades.groupby("trade_date")["net_points"].sum().sort_index()
    dates = list(daily.index)
    rolling_days = max(1, min(rolling_days, len(dates))) if dates else rolling_days
    rolling_step_days = max(1, rolling_step_days)
    windows = []
    incomplete_windows = []
    for start_index in range(0, max(len(dates) - rolling_days + 1, 0), rolling_step_days):
        window_dates = dates[start_index : start_index + rolling_days]
        window = daily[daily.index.isin(window_dates)]
        if not window.empty:
            windows.append(float(window.sum()))
    for start_date in dates:
        end_date = start_date + pd.Timedelta(days=rolling_days - 1)
        window = daily[(daily.index >= start_date) & (daily.index <= end_date)]
        if 0 < len(window) < rolling_days:
            incomplete_windows.append(float(window.sum()))
    first_half = net.iloc[: len(net) // 2].sum()
    second_half = net.iloc[len(net) // 2 :].sum()
    exit_reasons = trades["exit_reason"].value_counts(normalize=True).to_dict()
    direction_share = trades["direction"].value_counts(normalize=True).to_dict()
    return {
        "path": str(path),
        "exists": True,
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "max_drawdown_points": float(abs(drawdown.min())),
        "win_rate": float((net > 0).mean()),
        "avg_points": float(net.mean()),
        "median_points": float(net.median()),
        "worst_trade_points": float(net.min()),
        "best_trade_points": float(net.max()),
        "positive_day_rate": float((daily > 0).mean()) if len(daily) else 0.0,
        "worst_day_points": float(daily.min()) if len(daily) else 0.0,
        "best_day_points": float(daily.max()) if len(daily) else 0.0,
        "rolling_window_count": int(len(windows)),
        "rolling_positive_rate": float(sum(value > 0 for value in windows) / len(windows)) if windows else 0.0,
        "worst_rolling_window_points": float(min(windows)) if windows else 0.0,
        "worst_incomplete_window_points": float(min(incomplete_windows)) if incomplete_windows else 0.0,
        "first_half_points": float(first_half),
        "second_half_points": float(second_half),
        "exit_reason_share": {str(key): float(value) for key, value in exit_reasons.items()},
        "direction_share": {str(key): float(value) for key, value in direction_share.items()},
    }


def _read_gate_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    frame = pd.read_csv(path)
    return {"path": str(path), "exists": True, "rows": int(len(frame)), "records": frame.to_dict(orient="records")}


def _check_thresholds(candidate: dict[str, Any] | None, trades: dict[str, Any], args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    if not candidate:
        return ["top_candidate_missing"]
    checks = {
        "full_trades": (candidate.get("full_trades", 0), args.min_trades),
        "full_profit_factor": (candidate.get("full_profit_factor", 0), args.min_profit_factor),
        "net_to_drawdown": (candidate.get("net_to_drawdown", 0), args.min_net_to_drawdown),
        "full_stability": (candidate.get("full_stability", 0), args.min_stability),
        "positive_fold_rate": (candidate.get("positive_fold_rate", 0), args.min_positive_fold_rate),
        "positive_window_rate": (candidate.get("positive_window_rate", 0), args.min_positive_window_rate),
        "min_window_net_points": (candidate.get("min_window_net_points", 0), args.min_window_net_points),
        "stress_net_points": (candidate.get("stress_net_points", 0), args.min_stress_net_points),
        "trade_file_count": (trades.get("trades", 0), args.min_trades),
        "rolling_positive_rate": (trades.get("rolling_positive_rate", 0), args.min_positive_window_rate),
        "worst_rolling_window_points": (trades.get("worst_rolling_window_points", 0), args.min_window_net_points),
    }
    for name, (observed, threshold) in checks.items():
        if float(observed) < float(threshold):
            blockers.append(f"{name}_below_min:{observed}<{threshold}")
    if str(candidate.get("selection_tier")) != "balanced_best":
        blockers.append(f"selection_tier_not_balanced_best:{candidate.get('selection_tier')}")
    return blockers


def audit_best_strategy(args: argparse.Namespace) -> dict[str, Any]:
    load_project_env()
    ranking = _load_top_candidate(Path(args.ranking))
    candidate = ranking.get("candidate")
    paper_strategy_id = getattr(args, "paper_strategy_id", None) or (str(candidate.get("name")) if candidate else None)
    trades = _trade_diagnostics(Path(args.trades), rolling_days=args.rolling_days, rolling_step_days=args.rolling_step_days)
    data_span = _feature_span(Path(args.features_cache))
    gate_summary = _read_gate_summary(Path(args.gate_summary))
    walk_forward_summary = _read_gate_summary(Path(args.walk_forward_summary))
    paper = summarize_paper_audits(
        agent_audit_path=args.agent_audit,
        ibkr_audit_path=args.ibkr_audit,
        strategy_id=paper_strategy_id,
        gate_config=PaperValidationGateConfig(
            min_ibkr_ready=args.min_ibkr_ready,
            min_ibkr_submitted=args.min_ibkr_submitted,
            min_paper_outcomes=args.min_paper_outcomes,
            min_paper_net_points=args.min_paper_net_points,
            min_paper_win_rate=args.min_paper_win_rate,
            max_consecutive_losses=args.max_consecutive_losses,
            max_allowed_blocker_count=args.max_allowed_blocker_count,
        ),
    )

    research_blockers = _check_thresholds(candidate, trades, args)
    live_blockers = []
    if data_span["calendar_days"] < args.min_history_days:
        live_blockers.append(f"history_span_below_min:{data_span['calendar_days']}<{args.min_history_days}")
    if not os.getenv("DATABENTO_API_KEY"):
        live_blockers.append("databento_api_key_missing")
    current_ibkr_ready = int(paper.get("ibkr_current_ready", paper.get("ibkr_ready", 0)) or 0)
    current_ibkr_account_paper = bool(paper.get("ibkr_current_account_paper"))
    if not os.getenv("IBKR_ACCOUNT") and current_ibkr_ready < args.min_ibkr_ready and not current_ibkr_account_paper:
        live_blockers.append("ibkr_account_missing")
    paper_gate = paper["validation_gate"]
    if paper_gate["status"] != "pass":
        live_blockers.extend(f"paper_validation:{reason}" for reason in paper_gate["blockers"])

    return {
        "research_status": "pass" if not research_blockers else "blocked",
        "live_status": "pass" if not research_blockers and not live_blockers else "blocked",
        "research_blockers": research_blockers,
        "live_blockers": live_blockers,
        "ranking": ranking,
        "trade_diagnostics": trades,
        "data_span": data_span,
        "gate_summary": gate_summary,
        "walk_forward_summary": walk_forward_summary,
        "paper_summary": paper,
        "paper_strategy_id": paper_strategy_id,
    }


def _markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No rows._"
    columns = list(rows[0].keys())
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        values = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _write_report(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate = result["ranking"].get("candidate") or {}
    diagnostics = result["trade_diagnostics"]
    metric_rows = [
        {"metric": "candidate", "value": candidate.get("name", "")},
        {"metric": "research_status", "value": result["research_status"]},
        {"metric": "live_status", "value": result["live_status"]},
        {"metric": "trades", "value": diagnostics.get("trades", 0)},
        {"metric": "net_points", "value": diagnostics.get("net_points", 0.0)},
        {"metric": "max_drawdown_points", "value": diagnostics.get("max_drawdown_points", 0.0)},
        {"metric": "net_to_drawdown", "value": candidate.get("net_to_drawdown", 0.0)},
        {"metric": "profit_factor", "value": candidate.get("full_profit_factor", 0.0)},
        {"metric": "win_rate", "value": diagnostics.get("win_rate", 0.0)},
        {"metric": "stability", "value": candidate.get("full_stability", 0.0)},
        {"metric": "stress_net_points", "value": candidate.get("stress_net_points", 0.0)},
        {"metric": "worst_rolling_window_points", "value": diagnostics.get("worst_rolling_window_points", 0.0)},
    ]
    lines = [
        "# NQM6 Best Strategy Readiness Audit",
        "",
        "## Verdict",
        "",
        f"- Research status: `{result['research_status']}`.",
        f"- Live status: `{result['live_status']}`.",
        f"- Best current research candidate: `{candidate.get('name', '')}`.",
        "- Live status remains blocked unless history, paper trading, and broker readiness gates all pass.",
        "",
        "## Metrics",
        "",
        _markdown_table(metric_rows),
        "",
        "## Research Blockers",
        "",
    ]
    lines.extend(f"- `{blocker}`" for blocker in result["research_blockers"]) if result["research_blockers"] else lines.append("_No research blockers._")
    lines.extend(["", "## Live Blockers", ""])
    lines.extend(f"- `{blocker}`" for blocker in result["live_blockers"]) if result["live_blockers"] else lines.append("_No live blockers._")
    lines.extend(
        [
            "",
            "## Raw Summary",
            "",
            "```json",
            json.dumps(
                {
                    "ranking": result["ranking"],
                    "trade_diagnostics": result["trade_diagnostics"],
                    "data_span": result["data_span"],
                    "paper_validation_gate": result["paper_summary"]["validation_gate"],
                },
                indent=2,
                sort_keys=True,
                default=str,
            ),
            "```",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the strongest MBP strategy candidate for research and live readiness.")
    parser.add_argument("--ranking", default=".tmp/mbp-best-strategy-ranking.csv")
    parser.add_argument("--trades", default=".tmp/mbp-best-strategy-trades.csv")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--gate-summary", default=".tmp/mbp-best-strategy-gate-summary.csv")
    parser.add_argument("--walk-forward-summary", default=".tmp/mbp-best-strategy-walk-forward-summary.csv")
    parser.add_argument("--agent-audit", default=".tmp/agent-gate-audit.jsonl")
    parser.add_argument("--ibkr-audit", default=".tmp/ibkr-paper-audit.jsonl")
    parser.add_argument("--paper-strategy-id", default=None, help="Only count paper validation events for this strategy_id. Defaults to top ranked candidate name.")
    parser.add_argument("--output", default=".tmp/mbp-best-strategy-readiness-audit.json")
    parser.add_argument("--report", default="reports/NQM6-best-strategy-readiness-audit.md")
    parser.add_argument("--rolling-days", type=int, default=10)
    parser.add_argument("--rolling-step-days", type=int, default=5)
    parser.add_argument("--min-trades", type=int, default=200)
    parser.add_argument("--min-profit-factor", type=float, default=1.45)
    parser.add_argument("--min-net-to-drawdown", type=float, default=10.0)
    parser.add_argument("--min-stability", type=float, default=0.70)
    parser.add_argument("--min-positive-fold-rate", type=float, default=0.80)
    parser.add_argument("--min-positive-window-rate", type=float, default=0.88)
    parser.add_argument("--min-window-net-points", type=float, default=0.0)
    parser.add_argument("--min-stress-net-points", type=float, default=0.0)
    parser.add_argument("--min-history-days", type=int, default=365)
    parser.add_argument("--min-ibkr-ready", type=int, default=1)
    parser.add_argument("--min-ibkr-submitted", type=int, default=1)
    parser.add_argument("--min-paper-outcomes", type=int, default=20)
    parser.add_argument("--min-paper-net-points", type=float, default=0.0)
    parser.add_argument("--min-paper-win-rate", type=float, default=45.0)
    parser.add_argument("--max-consecutive-losses", type=int, default=4)
    parser.add_argument("--max-allowed-blocker-count", type=int, default=0)
    args = parser.parse_args()

    result = audit_best_strategy(args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(Path(args.report), result)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["live_status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
