from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.config.env import load_project_env
from tradingagents.execution import (
    IBKRConnectionConfig,
    IBKRContractSpec,
    IBKRTickRecorderConfig,
    IBKRPaperBroker,
    LivePaperTraderConfig,
    LivePaperTraderDaemonConfig,
    run_live_paper_trader_daemon,
    run_live_paper_trader_once,
)

DEFAULT_STRATEGY_ID = "adaptive_defensive_mr_trendstable_mr_meanstable_mr_fallbackdefensive_mr_us0_eu1_gap1_cap24"
DEFAULT_SELECTED_ALIAS = "adaptive_portfolio"


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Run a live IBKR top-of-book paper-trading loop.")
    parser.add_argument("--live-signal", default=".tmp/mbp-live-signal.csv")
    parser.add_argument("--state-path", default=".tmp/mbp-live-paper-trader-state.json")
    parser.add_argument("--strategy-id", default=DEFAULT_STRATEGY_ID)
    parser.add_argument("--selected-alias", default=DEFAULT_SELECTED_ALIAS)
    parser.add_argument("--direction", choices=["buy", "sell", "BUY", "SELL"], default="buy")
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--contract-month", default="202606")
    parser.add_argument("--account", default=None)
    parser.add_argument("--client-id", type=int, default=None, help="Override IBKR client id for this live trader process.")
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--stop-loss-points", type=float, default=16.0)
    parser.add_argument("--take-profit-points", type=float, default=24.0)
    parser.add_argument("--max-hold-minutes", type=int, default=6)
    parser.add_argument("--submit", action="store_true", help="Submit to IBKR paper after preflight/risk checks. Default is dry-run.")
    parser.add_argument("--agent-gate", action="store_true", help="Require multi-agent review before submitting/dry-run.")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--snapshot-attempts", type=int, default=3)
    parser.add_argument("--snapshot-retry-seconds", type=float, default=1.0)
    parser.add_argument("--allow-existing-exposure", action="store_true", help="Do not block when a position/open order already exists.")
    parser.add_argument("--record-ticks", action="store_true")
    parser.add_argument("--tick-output-dir", default=".tmp/ibkr-paper-ticks")
    parser.add_argument("--tick-interval-seconds", type=float, default=1.0)
    parser.add_argument("--max-ticks", type=int, default=60)
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--max-iterations", type=int, default=1, help="Use 0 to run until stopped.")
    args = parser.parse_args()

    direction = 1 if args.direction.lower() == "buy" else -1
    config = LivePaperTraderConfig(
        live_signal_path=Path(args.live_signal),
        state_path=Path(args.state_path),
        strategy_id=args.strategy_id,
        selected_alias=args.selected_alias,
        direction=direction,
        contract=IBKRContractSpec(
            symbol=args.symbol.upper(),
            last_trade_date_or_contract_month=args.contract_month,
            expected_point_value=2.0 if args.symbol.upper() == "MNQ" else 20.0,
        ),
        account=args.account,
        quantity=args.quantity,
        stop_loss_points=args.stop_loss_points,
        take_profit_points=args.take_profit_points,
        max_hold_minutes=args.max_hold_minutes,
        submit=args.submit,
        require_agent_gate=args.agent_gate,
        skip_preflight=args.skip_preflight,
        snapshot_attempts=args.snapshot_attempts,
        snapshot_retry_seconds=args.snapshot_retry_seconds,
        skip_when_position_open=not args.allow_existing_exposure,
        tick_recorder=IBKRTickRecorderConfig(
            output_dir=Path(args.tick_output_dir),
            symbol=args.symbol.upper(),
            contract_month=args.contract_month,
            interval_seconds=args.tick_interval_seconds,
            max_ticks=args.max_ticks,
            enabled=args.record_ticks,
        ),
    )
    broker = None
    if args.client_id is not None:
        connection = IBKRConnectionConfig.from_env()
        broker = IBKRPaperBroker(
            connection=IBKRConnectionConfig(
                host=connection.host,
                port=connection.port,
                client_id=args.client_id,
                account=connection.account,
                timeout=connection.timeout,
                readonly=connection.readonly,
            )
        )
    if args.daemon:
        result = run_live_paper_trader_daemon(
            config=LivePaperTraderDaemonConfig(
                trader=config,
                interval_seconds=args.interval_seconds,
                max_iterations=None if args.max_iterations == 0 else args.max_iterations,
            ),
            broker=broker,
        )
    else:
        result = run_live_paper_trader_once(config=config, broker=broker)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if args.daemon:
        return 0 if result.get("status") == "completed" else 2
    return 0 if result.get("status") in {"dry_run", "submitted", "duplicate_skipped"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
