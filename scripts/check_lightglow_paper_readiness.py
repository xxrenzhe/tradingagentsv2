from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from datetime import datetime, UTC

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.export_lightglow_optimized_strategy_trades import LIGHTGLOW_OPTIMIZED_STRATEGY_ID
from tradingagents.config.env import load_project_env
from tradingagents.execution import IBKRConnectionConfig, IBKRPaperBroker, IBKRPaperTradingSession, PaperValidationGateConfig, summarize_paper_audits
from tradingagents.execution.paper_runner import _load_state, _paper_risk_halt, _signal_freshness
from tradingagents.execution.paper_validation import load_trade_samples, select_trade_sample


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Check optimized Lightglow paper-runner readiness.")
    parser.add_argument("--trades", default=".tmp/nq-lightglow-paper-executable-optimized-trades.csv")
    parser.add_argument("--state-path", default=".tmp/nq-lightglow-optimized-paper-runner-state.json")
    parser.add_argument("--agent-audit", default=".tmp/agent-gate-audit.jsonl")
    parser.add_argument("--ibkr-audit", default=".tmp/ibkr-paper-audit.jsonl")
    parser.add_argument("--strategy-id", default=LIGHTGLOW_OPTIMIZED_STRATEGY_ID)
    parser.add_argument("--max-signal-age-minutes", type=float, default=10.0)
    parser.add_argument("--paper-consecutive-loss-halt", type=int, default=3)
    parser.add_argument("--paper-daily-loss-halt-points", type=float, default=50.0)
    parser.add_argument("--min-paper-outcomes", type=int, default=300)
    parser.add_argument("--min-paper-net-points", type=float, default=0.0)
    parser.add_argument("--min-paper-win-rate", type=float, default=35.0)
    parser.add_argument("--max-consecutive-losses", type=int, default=3)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--preflight-attempts", type=int, default=3)
    parser.add_argument("--preflight-retry-seconds", type=float, default=1.0)
    parser.add_argument("--client-id", type=int, default=None)
    args = parser.parse_args()

    signal = _signal_status(Path(args.trades), max_age_minutes=args.max_signal_age_minutes)
    state = _state_status(Path(args.state_path))
    risk_halt = _risk_halt_status(args, signal)
    paper_summary = summarize_paper_audits(
        agent_audit_path=args.agent_audit,
        ibkr_audit_path=args.ibkr_audit,
        gate_config=PaperValidationGateConfig(
            min_ibkr_ready=1,
            min_ibkr_submitted=1,
            min_paper_outcomes=args.min_paper_outcomes,
            min_paper_net_points=args.min_paper_net_points,
            min_paper_win_rate=args.min_paper_win_rate,
            max_consecutive_losses=args.max_consecutive_losses,
        ),
        strategy_id=args.strategy_id,
    )
    preflight = _ready_preflight(args) if args.preflight else {"status": "skipped"}
    execution_blockers = []
    if signal["status"] != "fresh":
        execution_blockers.append(f"signal_{signal['status']}")
    if state["pending_time_exit_close"]:
        execution_blockers.append("pending_time_exit_close_must_be_managed_before_new_entry")
    if risk_halt.get("halted"):
        execution_blockers.extend(f"risk_halt:{reason}" for reason in risk_halt.get("reasons", []))
    submit_blockers = list(execution_blockers)
    if args.preflight and preflight.get("status") != "ready":
        submit_blockers.extend(f"preflight:{reason}" for reason in preflight.get("missing_requirements", []))
    review_blockers = list(paper_summary["validation_gate"].get("blockers", []))
    dry_run_status = "ready" if not execution_blockers else "blocked"
    submit_status = "ready" if not submit_blockers else "blocked"
    review_status = "ready" if not review_blockers else "blocked"
    result = {
        "status": dry_run_status,
        "dry_run_status": dry_run_status,
        "timed_exit_submit_status": submit_status,
        "paper_review_status": review_status,
        "blockers": execution_blockers,
        "dry_run_blockers": execution_blockers,
        "timed_exit_submit_blockers": submit_blockers,
        "paper_review_blockers": review_blockers,
        "strategy_id": args.strategy_id,
        "signal": signal,
        "runner_state": state,
        "paper_risk_halt": risk_halt,
        "ibkr_preflight": preflight,
        "paper_validation_gate": paper_summary["validation_gate"],
        "paper_validation": {
            "outcomes": paper_summary["paper_outcomes"],
            "ibkr_submitted": paper_summary["ibkr_submitted"],
            "ibkr_current_ready": paper_summary["ibkr_current_ready"],
        },
        "next_commands": {
            "dry_run": (
                ".venv/bin/python scripts/run_lightglow_optimized_strategy_paper_trader.py "
                f"--trades {args.trades} --max-signal-age-minutes {args.max_signal_age_minutes:g} "
                f"--paper-consecutive-loss-halt {args.paper_consecutive_loss_halt} "
                f"--paper-daily-loss-halt-points {args.paper_daily_loss_halt_points:g}"
            ),
            "timed_exit_submit": (
                ".venv/bin/python scripts/run_lightglow_optimized_strategy_paper_trader.py "
                f"--trades {args.trades} --max-signal-age-minutes {args.max_signal_age_minutes:g} "
                f"--paper-consecutive-loss-halt {args.paper_consecutive_loss_halt} "
                f"--paper-daily-loss-halt-points {args.paper_daily_loss_halt_points:g} "
                "--submit --allow-timed-exit-submit"
            ),
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["dry_run_status"] == "ready" else 2


def _signal_status(path: Path, *, max_age_minutes: float) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "path": str(path)}
    try:
        trades = load_trade_samples(path)
        sample = select_trade_sample(trades, row_index=-1)
    except Exception as exc:
        return {"status": "invalid", "path": str(path), "reason": str(exc) or exc.__class__.__name__}
    freshness = _signal_freshness(sample, max_age_minutes=max_age_minutes)
    return {
        "status": "fresh" if freshness["passed"] else "stale",
        "path": str(path),
        "rows": int(len(trades)),
        "freshness": freshness,
        "candidate": {
            "entry_ts": sample.get("entry_ts"),
            "actual_entry_ts": sample.get("actual_entry_ts"),
            "direction": sample.get("direction"),
            "entry_price": sample.get("entry_price"),
            "portfolio_rule": sample.get("portfolio_rule"),
            "selected_alias": sample.get("selected_alias"),
        },
    }


def _state_status(path: Path) -> dict[str, Any]:
    state = _load_state(path)
    pending = state.get("pending_time_exit_close")
    return {
        "path": str(path),
        "exists": path.exists(),
        "last_candidate_key": state.get("last_candidate_key"),
        "last_time_exit_close": state.get("last_time_exit_close"),
        "pending_time_exit_close": pending if isinstance(pending, dict) else None,
    }


def _risk_halt_status(args: argparse.Namespace, signal: dict[str, Any]) -> dict[str, Any]:
    candidate = signal.get("candidate") if isinstance(signal.get("candidate"), dict) else {}
    trade_date = _trade_date(candidate.get("actual_entry_ts") or candidate.get("entry_ts"))
    return _paper_risk_halt(
        strategy_id=args.strategy_id,
        trade_date=trade_date,
        audit_path=Path(args.agent_audit),
        consecutive_loss_halt=args.paper_consecutive_loss_halt,
        daily_loss_halt_points=args.paper_daily_loss_halt_points,
    )


def _trade_date(value: Any) -> str:
    if value is None:
        return ""
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC).date().isoformat()


def _ready_preflight(args: argparse.Namespace) -> dict[str, Any]:
    last_preflight: dict[str, Any] = {}
    for attempt in range(max(1, int(args.preflight_attempts))):
        broker = _broker_for_client_id(args.client_id)
        session = IBKRPaperTradingSession.from_env(broker) if broker is not None else IBKRPaperTradingSession.from_env()
        last_preflight = session.preflight()
        readiness = last_preflight.get("readiness", {})
        if isinstance(readiness, dict) and readiness.get("status") == "ready":
            return {
                "status": "ready",
                "missing_requirements": [],
                "connection": last_preflight.get("connection", {}),
                "market_data": last_preflight.get("market_data", {}),
            }
        if attempt + 1 < int(args.preflight_attempts):
            import time

            time.sleep(max(0.0, float(args.preflight_retry_seconds)))
    readiness = last_preflight.get("readiness", {}) if isinstance(last_preflight, dict) else {}
    return {
        "status": readiness.get("status", "blocked") if isinstance(readiness, dict) else "blocked",
        "missing_requirements": readiness.get("missing_requirements", []) if isinstance(readiness, dict) else ["preflight_failed"],
        "connection": last_preflight.get("connection", {}) if isinstance(last_preflight, dict) else {},
        "market_data": last_preflight.get("market_data", {}) if isinstance(last_preflight, dict) else {},
    }


def _broker_for_client_id(client_id: int | None) -> IBKRPaperBroker | None:
    if client_id is None:
        return None
    connection = IBKRConnectionConfig.from_env()
    return IBKRPaperBroker(
        connection=IBKRConnectionConfig(
            host=connection.host,
            port=connection.port,
            client_id=client_id,
            account=connection.account,
            timeout=connection.timeout,
            readonly=connection.readonly,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
