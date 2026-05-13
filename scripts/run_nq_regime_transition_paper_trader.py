from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.config.env import load_project_env
from tradingagents.execution import regime_transition_spec


DEFAULT_STRATEGY_ID = "optimized50_2r5_quality"


def build_command(args: argparse.Namespace) -> list[str]:
    selected_alias = args.selected_alias or args.strategy_id
    spec = regime_transition_spec(args.strategy_id, selected_alias)
    command = [
        sys.executable,
        "scripts/run_ibkr_live_paper_trader.py",
        "--signal-mode",
        "strategy",
        "--strategy-family",
        "regime_transition",
        "--strategy-id",
        args.strategy_id,
        "--selected-alias",
        selected_alias,
        "--symbol",
        args.symbol.upper(),
        "--contract-month",
        args.contract_month,
        "--quantity",
        str(args.quantity),
        "--max-hold-minutes",
        str(spec.max_hold_minutes),
        "--min-bars",
        str(spec.lookback + 121),
        "--live-signal",
        args.live_signal,
        "--state-path",
        args.state_path,
        "--history-path",
        args.history_path,
        "--agent-audit",
        args.agent_audit,
        "--ibkr-audit",
        args.ibkr_audit,
        "--min-paper-outcomes",
        str(args.min_paper_outcomes),
        "--min-paper-net-points",
        str(args.min_paper_net_points),
        "--min-paper-win-rate",
        str(args.min_paper_win_rate),
        "--max-consecutive-losses",
        str(args.max_consecutive_losses),
        "--interval-seconds",
        str(args.interval_seconds),
        "--max-iterations",
        str(args.max_iterations),
    ]
    if args.account:
        command.extend(["--account", args.account])
    if args.client_id is not None:
        command.extend(["--client-id", str(args.client_id)])
    if args.paper_validation_accrual_mode:
        command.append("--paper-validation-accrual-mode")
    if args.agent_gate:
        command.append("--agent-gate")
    if args.daemon:
        command.append("--daemon")
    if args.record_ticks:
        command.append("--record-ticks")
    if args.allow_existing_exposure:
        command.append("--allow-existing-exposure")
    if args.submit:
        command.append("--submit")
    return command


def check_parity(args: argparse.Namespace) -> dict[str, object]:
    command = [
        sys.executable,
        "scripts/check_nq_regime_transition_parity.py",
        "--parity-file",
        args.parity_file,
        "--strategy-id",
        args.strategy_id,
        "--max-mismatch-rate",
        str(args.max_mismatch_rate),
        "--min-checked-signals",
        str(args.min_checked_signals),
    ]
    completed = subprocess.run(command, cwd=ROOT_DIR, text=True, capture_output=True, check=False)
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        payload = {}
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "result": payload,
    }


def main() -> int:
    load_project_env(override=False)
    parser = argparse.ArgumentParser(description="Run promoted NQ regime-transition strategies through guarded IBKR paper trading.")
    parser.add_argument("--strategy-id", default=DEFAULT_STRATEGY_ID, choices=["optimized50_2r5_quality", "defensive45_2r5_loweff", "short45_2r25_netdd"])
    parser.add_argument("--selected-alias", default=None)
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--contract-month", default="202606")
    parser.add_argument("--account", default=None)
    parser.add_argument("--client-id", type=int, default=None)
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--live-signal", default=".tmp/nq-regime-transition-live-signal.csv")
    parser.add_argument("--state-path", default=".tmp/nq-regime-transition-paper-state.json")
    parser.add_argument("--history-path", default=".tmp/nq-regime-transition-market-history.jsonl")
    parser.add_argument("--agent-audit", default=".tmp/nq-regime-transition-agent-audit.jsonl")
    parser.add_argument("--ibkr-audit", default=".tmp/nq-regime-transition-ibkr-audit.jsonl")
    parser.add_argument("--parity-file", default=".tmp/nq-regime-transition-parity.json")
    parser.add_argument("--max-mismatch-rate", type=float, default=0.0)
    parser.add_argument("--min-checked-signals", type=int, default=1)
    parser.add_argument("--min-paper-outcomes", type=int, default=30)
    parser.add_argument("--min-paper-net-points", type=float, default=0.0)
    parser.add_argument("--min-paper-win-rate", type=float, default=35.0)
    parser.add_argument("--max-consecutive-losses", type=int, default=4)
    parser.add_argument("--paper-validation-accrual-mode", action="store_true")
    parser.add_argument("--agent-gate", action="store_true")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--max-iterations", type=int, default=1)
    parser.add_argument("--record-ticks", action="store_true")
    parser.add_argument("--allow-existing-exposure", action="store_true")
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--force-without-parity", action="store_true", help="Allow --submit without passing parity. Keep false outside controlled debugging.")
    args = parser.parse_args()

    parity = check_parity(args)
    if args.submit and not args.force_without_parity and parity["returncode"] != 0:
        result = {
            "status": "parity_blocked",
            "submitted": False,
            "strategy_id": args.strategy_id,
            "parity": parity,
        }
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 2

    command = build_command(args)
    completed = subprocess.run(command, cwd=ROOT_DIR, text=True, capture_output=True, check=False)
    result = {
        "status": "completed" if completed.returncode == 0 else "runner_failed",
        "returncode": completed.returncode,
        "strategy_id": args.strategy_id,
        "submitted_requested": bool(args.submit),
        "parity": parity,
        "command": command,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
