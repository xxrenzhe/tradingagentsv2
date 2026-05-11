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
from tradingagents.execution import (
    IBKRTickRecorderConfig,
    PaperDaemonConfig,
    PaperRunnerConfig,
    run_adaptive_portfolio_paper_daemon,
    run_adaptive_portfolio_paper_once,
)


def main() -> int:
    load_project_env(override=False)
    parser = argparse.ArgumentParser(description="Run the adaptive MBP portfolio paper trader once.")
    parser.add_argument("--trades", default=".tmp/mbp-adaptive-portfolio-trades.csv")
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--trade-date", default=None)
    parser.add_argument("--portfolio-rule", default=None)
    parser.add_argument("--selected-alias", default=None)
    parser.add_argument("--row-index", type=int, default=None)
    parser.add_argument("--state-path", default=".tmp/mbp-paper-runner-state.json")
    parser.add_argument("--contract-month", default="202606")
    parser.add_argument("--account", default=None)
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--stop-loss-points", type=float, default=16.0)
    parser.add_argument("--take-profit-points", type=float, default=24.0)
    parser.add_argument("--submit", action="store_true", help="Actually submit to IBKR paper. Default is dry-run.")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--agent-gate", action="store_true", help="Require multi-agent review before submit/dry-run.")
    parser.add_argument("--max-signal-age-minutes", type=float, default=10.0, help="Block --submit when the selected signal is older than this many minutes.")
    parser.add_argument("--allow-stale-signal-submit", action="store_true", help="Disable signal freshness blocking for --submit. Use only for controlled tests.")
    parser.add_argument("--audit-path", default=None)
    parser.add_argument("--refresh-report", action="store_true", help="Refresh walk-forward/paper validation report after runner execution.")
    parser.add_argument("--record-ticks", action="store_true", help="Record IBKR bid/ask/last snapshots for replay.")
    parser.add_argument("--tick-output-dir", default=".tmp/ibkr-paper-ticks")
    parser.add_argument("--tick-interval-seconds", type=float, default=1.0)
    parser.add_argument("--max-ticks", type=int, default=60)
    parser.add_argument("--daemon", action="store_true", help="Run continuously until max-iterations is reached or the process is stopped.")
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--max-iterations", type=int, default=1, help="Maximum daemon iterations. Use 0 to run until stopped.")
    parser.add_argument("--no-status-snapshot", action="store_true")
    args = parser.parse_args()

    runner_config = PaperRunnerConfig(
        trades_path=Path(args.trades),
        state_path=Path(args.state_path),
        contract_month=args.contract_month,
        account=args.account,
        quantity=args.quantity,
        stop_loss_points=args.stop_loss_points,
        take_profit_points=args.take_profit_points,
        submit=args.submit,
        skip_preflight=args.skip_preflight,
        require_agent_gate=args.agent_gate,
        max_signal_age_minutes=None if args.allow_stale_signal_submit else args.max_signal_age_minutes,
        audit_path=Path(args.audit_path) if args.audit_path else None,
        tick_recorder=IBKRTickRecorderConfig(
            output_dir=Path(args.tick_output_dir),
            symbol=args.symbol.upper(),
            contract_month=args.contract_month,
            interval_seconds=args.tick_interval_seconds,
            max_ticks=args.max_ticks,
            enabled=args.record_ticks,
        ),
    )
    if args.daemon:
        result = run_adaptive_portfolio_paper_daemon(
            config=PaperDaemonConfig(
                runner=runner_config,
                interval_seconds=args.interval_seconds,
                max_iterations=None if args.max_iterations == 0 else args.max_iterations,
                refresh_report=args.refresh_report,
                status_snapshot=not args.no_status_snapshot,
                trade_date=args.trade_date,
                portfolio_rule=args.portfolio_rule,
                selected_alias=args.selected_alias,
                row_index=args.row_index,
            )
        )
    else:
        result = run_adaptive_portfolio_paper_once(
            config=runner_config,
            trade_date=args.trade_date,
            portfolio_rule=args.portfolio_rule,
            selected_alias=args.selected_alias,
            row_index=args.row_index,
        )
        if args.refresh_report:
            refresh = subprocess.run(
                [sys.executable, "scripts/run_daily_paper_validation.py"],
                cwd=ROOT_DIR,
                text=True,
                capture_output=True,
                check=False,
            )
            result["refresh_report"] = {
                "returncode": refresh.returncode,
                "stdout": refresh.stdout.strip(),
                "stderr": refresh.stderr.strip(),
            }
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if args.daemon:
        return 0 if result.get("status") == "completed" else 2
    if result["status"] in {"agent_gate_rejected", "duplicate_skipped"}:
        return 0
    return 0 if result.get("status") in {"dry_run", "submitted"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
