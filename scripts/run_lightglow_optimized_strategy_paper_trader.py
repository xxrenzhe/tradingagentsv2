from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.export_lightglow_optimized_strategy_trades import (
    LIGHTGLOW_OPTIMIZED_SELECTED_ALIAS,
    LIGHTGLOW_OPTIMIZED_STRATEGY_ID,
)
from tradingagents.config.env import load_project_env
from tradingagents.execution import (
    IBKRTickRecorderConfig,
    PaperDaemonConfig,
    PaperRunnerConfig,
    run_adaptive_portfolio_paper_daemon,
    run_adaptive_portfolio_paper_once,
)


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(
        description="Run the optimized Lightglow strategy through IBKR paper trading."
    )
    parser.add_argument("--trades", default=".tmp/nq-lightglow-optimized-strategy-trades.csv")
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--trade-date", default=None)
    parser.add_argument("--row-index", type=int, default=None)
    parser.add_argument("--state-path", default=".tmp/nq-lightglow-optimized-paper-runner-state.json")
    parser.add_argument("--contract-month", default="202606")
    parser.add_argument("--account", default=None)
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Submit to IBKR paper. Blocked by default until timed exit execution is available.",
    )
    parser.add_argument(
        "--allow-entry-only-submit",
        action="store_true",
        help="Allow entry-only submit for controlled operator tests. This does not implement the 2-bar time exit.",
    )
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--agent-gate", action="store_true", help="Require multi-agent review before submit/dry-run.")
    parser.add_argument("--max-signal-age-minutes", type=float, default=10.0)
    parser.add_argument("--allow-stale-signal-submit", action="store_true")
    parser.add_argument("--audit-path", default=None)
    parser.add_argument("--record-ticks", action="store_true")
    parser.add_argument("--tick-output-dir", default=".tmp/ibkr-paper-ticks")
    parser.add_argument("--tick-interval-seconds", type=float, default=1.0)
    parser.add_argument("--max-ticks", type=int, default=120)  # 2 minutes for 2-bar exit
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--max-iterations", type=int, default=1, help="Use 0 for continuous dry-run monitoring.")
    parser.add_argument("--no-status-snapshot", action="store_true")
    args = parser.parse_args()

    if args.submit and not args.allow_entry_only_submit:
        result = {
            "status": "blocked",
            "submitted": False,
            "strategy_id": LIGHTGLOW_OPTIMIZED_STRATEGY_ID,
            "reason": "timed_exit_manager_required",
            "details": "This strategy must exit after 2 bars (2 minutes) and has no stop-loss/take-profit bracket.",
        }
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 2

    runner_config = PaperRunnerConfig(
        trades_path=Path(args.trades),
        state_path=Path(args.state_path),
        contract_month=args.contract_month,
        account=args.account,
        quantity=args.quantity,
        stop_loss_points=None,
        take_profit_points=None,
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
        allow_time_exit_without_bracket_dry_run=True,
    )

    if args.daemon:
        result = run_adaptive_portfolio_paper_daemon(
            config=PaperDaemonConfig(
                runner=runner_config,
                interval_seconds=args.interval_seconds,
                max_iterations=None if args.max_iterations == 0 else args.max_iterations,
                refresh_report=False,
                status_snapshot=not args.no_status_snapshot,
                trade_date=args.trade_date,
                row_index=args.row_index,
            )
        )
    else:
        result = run_adaptive_portfolio_paper_once(
            config=runner_config,
            trade_date=args.trade_date,
            row_index=args.row_index,
        )

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("status") in ("submitted", "dry_run", "no_signal") else 1


if __name__ == "__main__":
    raise SystemExit(main())
