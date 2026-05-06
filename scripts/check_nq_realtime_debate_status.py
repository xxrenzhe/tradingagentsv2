from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.config.env import load_project_env
from tradingagents.execution import IBKRConnectionConfig, IBKRPaperBroker, IBKRPaperTradingSession


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Check NQ LLM debate realtime paper-trading status.")
    parser.add_argument("--status-path", default=".tmp/nq-llm-debate-realtime-status.json")
    parser.add_argument("--audit-path", default=".tmp/nq-llm-debate-paper-audit.jsonl")
    parser.add_argument("--trade-log-dir", default="docs/Strategy/tradelogs")
    parser.add_argument("--daemon-pattern", default="run_nq_llm_debate_paper_trader.py --realtime")
    parser.add_argument("--preflight-attempts", type=int, default=3)
    parser.add_argument("--preflight-retry-seconds", type=float, default=1.0)
    parser.add_argument("--client-id", type=int, default=None)
    parser.add_argument("--max-status-age-seconds", type=float, default=300.0)
    parser.add_argument("--require-submit-daemon", action="store_true")
    args = parser.parse_args()

    daemon = daemon_status(args.daemon_pattern)
    status_file = load_status_file(Path(args.status_path), max_age_seconds=args.max_status_age_seconds)
    latest_audit = latest_jsonl_event(Path(args.audit_path))
    latest_trade_log = latest_trade_log_entry(Path(args.trade_log_dir))
    preflight = ready_preflight(
        attempts=args.preflight_attempts,
        retry_seconds=args.preflight_retry_seconds,
        client_id=args.client_id,
    )
    blockers = []
    if not daemon["running"]:
        blockers.append("daemon_not_running")
    if args.require_submit_daemon and not daemon["submit_enabled"]:
        blockers.append("submit_daemon_not_running")
    if status_file["status"] != "fresh":
        blockers.append(f"status_file_{status_file['status']}")
    if preflight["readiness"].get("status") != "ready":
        blockers.extend(preflight["readiness"].get("missing_requirements", []) or ["ibkr_preflight_not_ready"])
    result = {
        "status": "ready" if not blockers else "blocked",
        "blockers": blockers,
        "daemon": daemon,
        "status_file": status_file,
        "ibkr_preflight": {
            "status": preflight["readiness"].get("status"),
            "missing_requirements": preflight["readiness"].get("missing_requirements", []),
            "connection": preflight.get("connection", {}),
            "market_data": preflight.get("market_data", {}),
        },
        "latest_audit": summarize_audit_event(latest_audit),
        "latest_trade_log": latest_trade_log,
    }
    print(json.dumps(result, indent=2, sort_keys=True, default=str, ensure_ascii=False))
    return 0 if result["status"] == "ready" else 2


def daemon_status(pattern: str) -> dict[str, Any]:
    tokens = tuple(shlex.split(pattern) if pattern else ())
    completed = subprocess.run(["ps", "-axo", "pid=,command="], text=True, capture_output=True, check=False)
    processes = []
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid, _, command = stripped.partition(" ")
        if not pid or not command or pid == str(os.getpid()):
            continue
        args = shlex.split(command)
        if any(Path(arg).name == Path(__file__).name for arg in args):
            continue
        if tokens and not all(token in command for token in tokens):
            continue
        processes.append(
            {
                "pid": pid,
                "command": command,
                "submit_enabled": "--submit" in args,
                "dry_run": "--submit" not in args,
            }
        )
    return {
        "running": bool(processes),
        "submit_enabled": any(process["submit_enabled"] for process in processes),
        "dry_run_enabled": any(process["dry_run"] for process in processes),
        "pids": [process["pid"] for process in processes],
        "processes": processes,
    }


def load_status_file(path: Path, *, max_age_seconds: float) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "path": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "invalid", "path": str(path), "reason": f"json:{exc.msg}"}
    updated_at = parse_timestamp(payload.get("updated_at"))
    age_seconds = None if updated_at is None else max(0.0, time.time() - updated_at.timestamp())
    status = "fresh" if age_seconds is not None and age_seconds <= max_age_seconds else "stale"
    return {
        "status": status,
        "path": str(path),
        "age_seconds": age_seconds,
        "updated_at": payload.get("updated_at"),
        "loop_status": payload.get("status"),
        "mode": payload.get("mode"),
        "iterations": payload.get("iterations"),
        "last_event": last_event_summary(payload.get("events")),
    }


def latest_jsonl_event(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    latest: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            latest = value
    return latest


def summarize_audit_event(event: dict[str, Any]) -> dict[str, Any]:
    if not event:
        return {"status": "missing"}
    trigger = event.get("trigger") if isinstance(event.get("trigger"), dict) else {}
    plan = event.get("plan") if isinstance(event.get("plan"), dict) else {}
    route = event.get("route") if isinstance(event.get("route"), dict) else {}
    return {
        "status": event.get("status"),
        "submitted": event.get("submitted"),
        "feature_set": trigger.get("feature_set"),
        "decision_id": plan.get("decision_id"),
        "action": route.get("action"),
        "reason": event.get("reason") or route.get("reason"),
        "recheck_price": event.get("recheck_price"),
    }


def latest_trade_log_entry(log_dir: Path) -> dict[str, Any]:
    files = sorted(log_dir.glob("*.md"))
    if not files:
        return {"status": "missing", "dir": str(log_dir)}
    latest = files[-1]
    content = latest.read_text(encoding="utf-8")
    headings = [line for line in content.splitlines() if line.startswith("## ")]
    return {
        "status": "found",
        "path": str(latest),
        "entries": len(headings),
        "latest_heading": headings[-1] if headings else "",
    }


def last_event_summary(events: Any) -> dict[str, Any]:
    if not isinstance(events, list) or not events:
        return {}
    event = events[-1]
    if not isinstance(event, dict):
        return {}
    trigger = event.get("trigger") if isinstance(event.get("trigger"), dict) else {}
    route = event.get("route") if isinstance(event.get("route"), dict) else {}
    return {
        "status": event.get("status"),
        "submitted": event.get("submitted"),
        "feature_set": trigger.get("feature_set"),
        "action": route.get("action"),
        "reason": event.get("reason") or route.get("reason"),
    }


def ready_preflight(*, attempts: int, retry_seconds: float, client_id: int | None = None) -> dict[str, Any]:
    last_preflight: dict[str, Any] = {}
    for attempt in range(max(1, int(attempts))):
        broker = broker_for_client_id(client_id)
        session = IBKRPaperTradingSession.from_env(broker) if broker is not None else IBKRPaperTradingSession.from_env()
        last_preflight = session.preflight()
        readiness = last_preflight.get("readiness", {})
        if isinstance(readiness, dict) and readiness.get("status") == "ready":
            return last_preflight
        if attempt + 1 < attempts:
            time.sleep(max(0.0, float(retry_seconds)))
    return last_preflight


def broker_for_client_id(client_id: int | None) -> IBKRPaperBroker | None:
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


def parse_timestamp(value: Any):
    if not value:
        return None
    from datetime import UTC, datetime

    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
