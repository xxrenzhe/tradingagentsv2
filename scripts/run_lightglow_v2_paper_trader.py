#!/usr/bin/env python3
"""
Run Lightglow Strategy V2 - Non-Kill Zone Optimized

This script runs the optimized Lightglow Premium/Discount reversal strategy
with Kill Zone filtering for improved risk-adjusted returns.

Strategy V2 Changes:
- Added Kill Zone time filter (blocks 8:30-11:30 and 13:30-16:00 EST)
- Improved profit factor: 2.45 vs 1.91 (+28%)
- Reduced max drawdown: $33K vs $46K (-28%)
- Higher average per trade: $66 vs $53 (+26%)
- Trade-off: Slightly lower total profit (-3.6%)

Usage:
    # Dry-run (default)
    python scripts/run_lightglow_v2_paper_trader.py --daemon

    # With submission (requires --allow-entry-only-submit)
    python scripts/run_lightglow_v2_paper_trader.py --daemon --submit --allow-entry-only-submit
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.export_lightglow_robust_strategy_trades import (
    LIGHTGLOW_ROBUST_SELECTED_ALIAS,
    LIGHTGLOW_ROBUST_STRATEGY_ID,
)
from tradingagents.config.env import load_project_env
from tradingagents.execution import (
    IBKRTickRecorderConfig,
    PaperDaemonConfig,
    PaperRunnerConfig,
    run_adaptive_portfolio_paper_daemon,
    run_adaptive_portfolio_paper_once,
)

# V2 Strategy ID
LIGHTGLOW_V2_STRATEGY_ID = f"{LIGHTGLOW_ROBUST_STRATEGY_ID}_v2_non_kill_zone"
LIGHTGLOW_V2_SELECTED_ALIAS = f"{LIGHTGLOW_ROBUST_SELECTED_ALIAS}_v2"


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(
        description="Run Lightglow Strategy V2 (Non-Kill Zone Optimized) through MNQ paper validation."
    )
    parser.add_argument("--trades", default=".tmp/nq-lightglow-v2-strategy-trades.csv")
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--trade-date", default=None)
    parser.add_argument("--row-index", type=int, default=None)
    parser.add_argument("--state-path", default=".tmp/nq-lightglow-v2-paper-runner-state.json")
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
        help="Allow entry-only submit for controlled operator tests. This does not implement the 2-minute time exit.",
    )
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--agent-gate", action="store_true", help="Require multi-agent review before submit/dry-run.")
    parser.add_argument("--max-signal-age-minutes", type=float, default=10.0)
    parser.add_argument("--allow-stale-signal-submit", action="store_true")
    parser.add_argument("--audit-path", default=None)
    parser.add_argument("--record-ticks", action="store_true")
    parser.add_argument("--tick-output-dir", default=".tmp/ibkr-paper-ticks")
    parser.add_argument("--tick-interval-seconds", type=float, default=1.0)
    parser.add_argument("--max-ticks", type=int, default=60)
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--max-iterations", type=int, default=1, help="Use 0 for continuous dry-run monitoring.")
    parser.add_argument("--no-status-snapshot", action="store_true")
    parser.add_argument(
        "--disable-kill-zone-filter",
        action="store_true",
        help="Disable Kill Zone filter (revert to V1 behavior)",
    )
    args = parser.parse_args()

    if args.submit and not args.allow_entry_only_submit:
        result = {
            "status": "blocked",
            "submitted": False,
            "strategy_id": LIGHTGLOW_V2_STRATEGY_ID,
            "strategy_version": "v2",
            "reason": "timed_exit_manager_required",
            "details": "This strategy must exit after 2 minutes and has no stop-loss/take-profit bracket.",
        }
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 2

    # Display strategy version info
    if not args.disable_kill_zone_filter:
        print("=" * 80)
        print("Lightglow Strategy V2 - Non-Kill Zone Optimized")
        print("=" * 80)
        print()
        print("Strategy Configuration:")
        print("  Version: V2")
        print("  Kill Zone Filter: ENABLED ✅")
        print("  Blocked Times: 8:30-11:30 and 13:30-16:00 EST")
        print()
        print("Expected Performance (based on backtest):")
        print("  Profit Factor: 2.45 (vs 1.91 in V1)")
        print("  Max Drawdown: $33,580 (vs $46,470 in V1)")
        print("  Avg Per Trade: $66.49 (vs $52.85 in V1)")
        print("  Trade Count: -23% (filters out low-quality trades)")
        print()
        print("=" * 80)
        print()

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
    )

    # Use V2 strategy ID unless filter is disabled
    strategy_id = LIGHTGLOW_ROBUST_STRATEGY_ID if args.disable_kill_zone_filter else LIGHTGLOW_V2_STRATEGY_ID
    selected_alias = LIGHTGLOW_ROBUST_SELECTED_ALIAS if args.disable_kill_zone_filter else LIGHTGLOW_V2_SELECTED_ALIAS

    if args.daemon:
        result = run_adaptive_portfolio_paper_daemon(
            config=PaperDaemonConfig(
                runner=runner_config,
                interval_seconds=args.interval_seconds,
                max_iterations=None if args.max_iterations == 0 else args.max_iterations,
                refresh_report=False,
                status_snapshot=not args.no_status_snapshot,
                trade_date=args.trade_date,
                portfolio_rule=strategy_id,
                selected_alias=selected_alias,
                row_index=args.row_index,
            )
        )
    else:
        result = run_adaptive_portfolio_paper_once(
            config=runner_config,
            trade_date=args.trade_date,
            portfolio_rule=strategy_id,
            selected_alias=selected_alias,
            row_index=args.row_index,
        )

    result["strategy_lock"] = {
        "strategy_id": strategy_id,
        "strategy_version": "v1" if args.disable_kill_zone_filter else "v2",
        "selected_alias": selected_alias,
        "symbol": args.symbol.upper(),
        "quantity": args.quantity,
        "exit_policy": "time_exit_after_2_minutes",
        "bracket": "disabled",
        "kill_zone_filter": "disabled" if args.disable_kill_zone_filter else "enabled",
        "blocked_times_est": [] if args.disable_kill_zone_filter else ["08:30-11:30", "13:30-16:00"],
    }

    print(json.dumps(result, indent=2, sort_keys=True, default=str))

    if args.daemon:
        return 0 if result.get("status") == "completed" else 2
    if result.get("status") in {"agent_gate_rejected", "duplicate_skipped"}:
        return 0
    return 0 if result.get("status") in {"dry_run", "submitted"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
