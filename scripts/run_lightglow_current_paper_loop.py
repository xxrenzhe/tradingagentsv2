from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.config.env import load_project_env


PAPER_STRATEGY_ID = "nq_lightglow_paper_executable_avoid_long_below_ema60_trend"


def run_command(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=ROOT_DIR, text=True, capture_output=True, check=False)
    payload = _parse_json(completed.stdout)
    return {
        "command": command,
        "returncode": int(completed.returncode),
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "json": payload,
    }


def build_export_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        "scripts/export_lightglow_current_paper_signal.py",
        "--output",
        args.current_signal,
        "--tail-rows",
        str(args.tail_rows),
        "--max-completed-bar-age-minutes",
        str(args.max_completed_bar_age_minutes),
    ]
    if args.bars:
        command.extend(["--bars", args.bars])
    if args.now:
        command.extend(["--now", args.now])
    return command


def build_readiness_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        "scripts/check_lightglow_paper_readiness.py",
        "--trades",
        args.current_signal,
        "--state-path",
        args.state_path,
        "--agent-audit",
        args.agent_audit,
        "--ibkr-audit",
        args.ibkr_audit,
        "--strategy-id",
        args.strategy_id,
        "--max-signal-age-minutes",
        str(args.max_signal_age_minutes),
        "--paper-consecutive-loss-halt",
        str(args.paper_consecutive_loss_halt),
        "--paper-daily-loss-halt-points",
        str(args.paper_daily_loss_halt_points),
    ]
    if args.submit:
        command.append("--preflight")
    if args.client_id is not None:
        command.extend(["--client-id", str(args.client_id)])
    return command


def build_runner_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        "scripts/run_lightglow_optimized_strategy_paper_trader.py",
        "--trades",
        args.current_signal,
        "--symbol",
        args.symbol.upper(),
        "--quantity",
        str(args.quantity),
        "--contract-month",
        args.contract_month,
        "--state-path",
        args.state_path,
        "--agent-audit",
        args.agent_audit,
        "--max-signal-age-minutes",
        str(args.max_signal_age_minutes),
        "--paper-consecutive-loss-halt",
        str(args.paper_consecutive_loss_halt),
        "--paper-daily-loss-halt-points",
        str(args.paper_daily_loss_halt_points),
        "--timed-exit-sleep-scale",
        str(args.timed_exit_sleep_scale),
    ]
    if args.account:
        command.extend(["--account", args.account])
    if args.submit:
        command.extend(["--submit", "--allow-timed-exit-submit"])
    if args.skip_preflight:
        command.append("--skip-preflight")
    if args.record_ticks:
        command.append("--record-ticks")
    return command


def run_iteration(args: argparse.Namespace, iteration: int) -> dict[str, Any]:
    export = run_command(build_export_command(args))
    export_json = export.get("json") if isinstance(export.get("json"), dict) else {}
    if export["returncode"] == 0 and export_json.get("status") == "no_signal":
        readiness = {"status": "skipped", "reason": "no_signal", "returncode": None, "json": None, "stderr": ""}
        runner = {"status": "skipped", "reason": "no_signal", "returncode": None, "json": None, "stderr": ""}
    else:
        readiness = run_command(build_readiness_command(args))
        runner = _maybe_run_runner(args, export, readiness)
    event = {
        "event_type": "lightglow_current_paper_loop",
        "timestamp": datetime.now(UTC).isoformat(),
        "iteration": iteration,
        "submit_requested": bool(args.submit),
        "export": _compact_command_result(export),
        "readiness": _compact_command_result(readiness),
        "runner": _compact_command_result(runner),
    }
    _append_jsonl(Path(args.loop_audit), event)
    return event


def _maybe_run_runner(args: argparse.Namespace, export: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    readiness_json = readiness.get("json") if isinstance(readiness.get("json"), dict) else {}
    readiness_key = "timed_exit_submit_status" if args.submit else "dry_run_status"
    gate_status = readiness_json.get(readiness_key) or readiness_json.get("status")
    should_run = export["returncode"] == 0 and readiness["returncode"] == 0
    if args.submit:
        should_run = should_run and gate_status == "ready"
    return run_command(build_runner_command(args)) if should_run else {"status": "skipped", "reason": "readiness_blocked", "returncode": None, "json": None, "stderr": ""}


def run_loop(args: argparse.Namespace) -> dict[str, Any]:
    events = []
    iteration = 0
    while args.max_iterations == 0 or iteration < args.max_iterations:
        iteration += 1
        events.append(run_iteration(args, iteration))
        if args.max_iterations != 0 and iteration >= args.max_iterations:
            break
        time.sleep(max(0.0, float(args.interval_seconds)))
    return {
        "status": "completed",
        "iterations": iteration,
        "submit_requested": bool(args.submit),
        "current_signal": args.current_signal,
        "loop_audit": args.loop_audit,
        "events": events,
    }


def _compact_command_result(result: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "returncode": result.get("returncode"),
        "json": result.get("json"),
        "stderr": result.get("stderr", ""),
    }
    if "status" in result:
        compact["status"] = result["status"]
    if "reason" in result:
        compact["reason"] = result["reason"]
    return compact


def _parse_json(text: str) -> dict[str, Any] | None:
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _append_jsonl(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")


def main() -> int:
    load_project_env(override=False)
    parser = argparse.ArgumentParser(description="Refresh and run the current Lightglow paper signal loop.")
    parser.add_argument("--bars", default="data/raw/databento/glbx-mdp3-20100606-20260427.ohlcv-1m.csv")
    parser.add_argument("--current-signal", default=".tmp/nq-lightglow-current-paper-signal.csv")
    parser.add_argument("--tail-rows", type=int, default=5_000)
    parser.add_argument("--max-completed-bar-age-minutes", type=float, default=5.0)
    parser.add_argument("--now", default="")
    parser.add_argument("--strategy-id", default=PAPER_STRATEGY_ID)
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--contract-month", default="202606")
    parser.add_argument("--account", default=None)
    parser.add_argument("--client-id", type=int, default=None)
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--state-path", default=".tmp/nq-lightglow-optimized-paper-runner-state.json")
    parser.add_argument("--agent-audit", default=".tmp/agent-gate-audit.jsonl")
    parser.add_argument("--ibkr-audit", default=".tmp/ibkr-paper-audit.jsonl")
    parser.add_argument("--loop-audit", default=".tmp/nq-lightglow-current-paper-loop.jsonl")
    parser.add_argument("--max-signal-age-minutes", type=float, default=10.0)
    parser.add_argument("--paper-consecutive-loss-halt", type=int, default=3)
    parser.add_argument("--paper-daily-loss-halt-points", type=float, default=50.0)
    parser.add_argument("--timed-exit-sleep-scale", type=float, default=1.0)
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--record-ticks", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--max-iterations", type=int, default=1, help="Use 0 for continuous loop until stopped.")
    args = parser.parse_args()
    result = run_loop(args)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    failures = [
        event
        for event in result["events"]
        if event["export"].get("returncode") != 0
        or (event["readiness"].get("returncode") not in (0, None) and event["submit_requested"])
        or event["runner"].get("returncode") not in (0, None)
    ]
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
