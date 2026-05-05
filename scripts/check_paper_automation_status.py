from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.config.env import load_project_env
from tradingagents.execution import IBKRConnectionConfig, IBKRPaperBroker, IBKRPaperTradingSession, PaperValidationGateConfig, summarize_paper_audits
from tradingagents.execution.paper_runner import _signal_freshness
from tradingagents.execution.paper_validation import load_trade_samples, select_trade_sample


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Check guarded IBKR paper automation readiness.")
    parser.add_argument("--live-signal", default=".tmp/mbp-live-signal.csv")
    parser.add_argument("--agent-audit", default=".tmp/agent-gate-audit.jsonl")
    parser.add_argument("--ibkr-audit", default=".tmp/ibkr-paper-audit.jsonl")
    parser.add_argument("--max-signal-age-minutes", type=float, default=10.0)
    parser.add_argument("--daemon-pattern", default="run_ibkr_live_paper_trader.py --daemon")
    parser.add_argument("--preflight-attempts", type=int, default=3)
    parser.add_argument("--preflight-retry-seconds", type=float, default=1.0)
    parser.add_argument("--client-id", type=int, default=None, help="Override IBKR client id for status preflight.")
    parser.add_argument("--strategy-id", default=None, help="Only count paper validation events for this strategy_id.")
    parser.add_argument("--paper-validation-accrual-mode", action="store_true")
    args = parser.parse_args()

    daemon = _daemon_status(args.daemon_pattern)
    live_signal = _live_signal_status(Path(args.live_signal), max_age_minutes=args.max_signal_age_minutes)
    preflight = _ready_preflight(attempts=args.preflight_attempts, retry_seconds=args.preflight_retry_seconds, client_id=args.client_id)
    paper_summary = summarize_paper_audits(
        agent_audit_path=args.agent_audit,
        ibkr_audit_path=args.ibkr_audit,
        gate_config=PaperValidationGateConfig(),
        strategy_id=args.strategy_id,
    )
    paper_submit_blockers = []
    if not daemon["running"]:
        paper_submit_blockers.append("daemon_not_running")
    elif not daemon.get("submit_enabled"):
        paper_submit_blockers.append("submit_daemon_not_running")
    if daemon.get("skip_paper_validation_gate_enabled"):
        paper_submit_blockers.append("skip_paper_validation_gate_daemon_running")
    if live_signal["status"] != "fresh":
        paper_submit_blockers.append(f"live_signal_{live_signal['status']}")
    if preflight["readiness"]["status"] != "ready":
        paper_submit_blockers.extend(preflight["readiness"].get("missing_requirements", []))
    live_candidate_blockers = list(paper_summary["validation_gate"].get("blockers", []))
    accrual_allowed = _paper_validation_accrual_allowed(
        paper_summary["validation_gate"],
        enabled=args.paper_validation_accrual_mode,
    )
    paper_submit_status = "ready" if not paper_submit_blockers else "blocked"
    strict_live_candidate_status = (
        "ready"
        if paper_submit_status == "ready" and not live_candidate_blockers
        else "blocked"
    )
    accrual_candidate_status = (
        "ready"
        if paper_submit_status == "ready" and (not live_candidate_blockers or accrual_allowed)
        else "blocked"
    )
    result = {
        "status": paper_submit_status,
        "paper_submit_status": paper_submit_status,
        "paper_submit_blockers": paper_submit_blockers,
        "live_candidate_status": strict_live_candidate_status,
        "strict_live_candidate_status": strict_live_candidate_status,
        "paper_validation_accrual_status": accrual_candidate_status,
        "live_candidate_blockers": live_candidate_blockers,
        "paper_validation_accrual_allowed": accrual_allowed,
        "daemon": daemon,
        "live_signal": live_signal,
        "ibkr_preflight": {
            "status": preflight["readiness"]["status"],
            "missing_requirements": preflight["readiness"].get("missing_requirements", []),
            "connection": preflight.get("connection", {}),
            "market_data": preflight.get("market_data", {}),
        },
        "paper_validation_gate": paper_summary["validation_gate"],
    }
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if paper_submit_status == "ready" else 2


def _paper_validation_accrual_allowed(gate: dict[str, object], *, enabled: bool) -> bool:
    if not enabled:
        return False
    if gate.get("status") == "pass":
        return True
    blockers = list(gate.get("blockers", []))
    return bool(blockers) and all(str(blocker).startswith("paper_outcomes_below_min:") for blocker in blockers)


def _daemon_status(pattern: str) -> dict[str, object]:
    tokens = tuple(shlex.split(pattern) if pattern else ())
    completed = subprocess.run(["ps", "-axo", "pid=,command="], text=True, capture_output=True, check=False)
    processes: list[dict[str, object]] = []
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid, _, command = stripped.partition(" ")
        if not pid or not command:
            continue
        if pid == str(os.getpid()):
            continue
        args = shlex.split(command)
        if any(Path(arg).name == Path(__file__).name for arg in args):
            continue
        if tokens and not all(token in command for token in tokens):
            continue
        submit_enabled = "--submit" in args
        accrual_mode = "--paper-validation-accrual-mode" in args
        skip_paper_validation_gate = "--skip-paper-validation-gate" in args
        processes.append(
            {
                "pid": pid,
                "command": command,
                "submit_enabled": submit_enabled,
                "paper_validation_accrual_mode": accrual_mode,
                "skip_paper_validation_gate": skip_paper_validation_gate,
            }
        )
    pids = [str(process["pid"]) for process in processes]
    submit_pids = [str(process["pid"]) for process in processes if process["submit_enabled"]]
    dry_run_pids = [str(process["pid"]) for process in processes if not process["submit_enabled"]]
    accrual_pids = [str(process["pid"]) for process in processes if process.get("paper_validation_accrual_mode")]
    skip_gate_pids = [str(process["pid"]) for process in processes if process.get("skip_paper_validation_gate")]
    return {
        "running": bool(processes),
        "submit_enabled": bool(submit_pids),
        "paper_validation_accrual_mode_enabled": bool(accrual_pids),
        "skip_paper_validation_gate_enabled": bool(skip_gate_pids),
        "pids": pids,
        "submit_pids": submit_pids,
        "dry_run_pids": dry_run_pids,
        "paper_validation_accrual_pids": accrual_pids,
        "skip_paper_validation_gate_pids": skip_gate_pids,
        "processes": processes,
    }


def _ready_preflight(*, attempts: int, retry_seconds: float, client_id: int | None = None) -> dict[str, object]:
    attempts = max(1, int(attempts))
    last_preflight: dict[str, object] = {}
    for attempt in range(attempts):
        broker = _broker_for_client_id(client_id)
        session = IBKRPaperTradingSession.from_env(broker) if broker is not None else IBKRPaperTradingSession.from_env()
        last_preflight = session.preflight()
        readiness = last_preflight.get("readiness", {})
        if isinstance(readiness, dict) and readiness.get("status") == "ready":
            return last_preflight
        if attempt + 1 < attempts:
            time.sleep(max(0.0, float(retry_seconds)))
    return last_preflight


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


def _live_signal_status(path: Path, *, max_age_minutes: float) -> dict[str, object]:
    if not path.exists():
        return {"status": "missing", "path": str(path)}
    try:
        trades = load_trade_samples(path)
        sample = select_trade_sample(trades)
    except Exception as exc:
        return {"status": "invalid", "path": str(path), "reason": str(exc) or exc.__class__.__name__}
    freshness = _signal_freshness(sample, max_age_minutes=max_age_minutes)
    return {
        "status": "fresh" if freshness["passed"] else "stale",
        "path": str(path),
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


if __name__ == "__main__":
    raise SystemExit(main())
