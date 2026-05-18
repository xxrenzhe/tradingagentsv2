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
    BA_NO_TRADE_COMBO_ALIAS,
    BA_NO_TRADE_COMBO_STRATEGY_ID,
    IBKRConnectionConfig,
    IBKRContractSpec,
    IBKRPaperBroker,
    IBKRTickRecorderConfig,
    LivePaperTraderConfig,
    LivePaperTraderDaemonConfig,
    LiveStrategySignalConfig,
    PaperValidationGateConfig,
    ba_no_trade_combo_spec,
    run_live_paper_trader_daemon,
    run_live_paper_trader_once,
)


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Run MNQ BA No-Trade Best Combo on IBKR paper trading.")
    parser.add_argument("--account", default=None)
    parser.add_argument("--client-id", type=int, default=None)
    parser.add_argument("--contract-month", default="202606")
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--submit", action="store_true", help="Submit paper orders. Default is dry-run.")
    parser.add_argument("--daemon", action="store_true", help="Run continuously. Default runs one iteration.")
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--max-iterations", type=int, default=1, help="Use 0 with --daemon to run until stopped.")
    parser.add_argument("--preflight-attempts", type=int, default=3)
    parser.add_argument("--preflight-retry-seconds", type=float, default=1.0)
    parser.add_argument("--skip-startup-preflight-gate", action="store_true")
    parser.add_argument("--allow-existing-exposure", action="store_true")
    parser.add_argument("--skip-paper-validation-gate", action="store_true")
    parser.add_argument("--strict-paper-validation-gate", action="store_true")
    parser.add_argument("--min-paper-outcomes", type=int, default=20)
    parser.add_argument("--min-paper-net-points", type=float, default=0.0)
    parser.add_argument("--min-paper-win-rate", type=float, default=45.0)
    parser.add_argument("--max-consecutive-losses", type=int, default=4)
    parser.add_argument("--max-allowed-blocker-count", type=int, default=0)
    parser.add_argument("--history-path", default=".tmp/mnq-ba-no-trade-live-market-history.jsonl")
    parser.add_argument("--live-signal", default=".tmp/mnq-ba-no-trade-live-signal.csv")
    parser.add_argument("--state-path", default=".tmp/mnq-ba-no-trade-paper-trader-state.json")
    parser.add_argument("--status-path", default=".tmp/mnq-ba-no-trade-paper-trader-status.json")
    parser.add_argument("--agent-audit", default=".tmp/mnq-ba-no-trade-agent-gate-audit.jsonl")
    parser.add_argument("--ibkr-audit", default=".tmp/mnq-ba-no-trade-ibkr-paper-audit.jsonl")
    parser.add_argument("--realtime-ledger", default=".tmp/mnq-ba-no-trade-realtime-trades.jsonl")
    parser.add_argument("--realtime-ledger-csv", default=".tmp/mnq-ba-no-trade-realtime-trades.csv")
    parser.add_argument("--trade-log-dir", default="docs/Strategy/tradelogs")
    parser.add_argument("--record-ticks", action="store_true")
    parser.add_argument("--tick-output-dir", default=".tmp/mnq-ba-no-trade-ibkr-paper-ticks")
    parser.add_argument("--tick-interval-seconds", type=float, default=1.0)
    parser.add_argument("--max-ticks", type=int, default=60)
    args = parser.parse_args()

    contract = IBKRContractSpec(
        symbol="MNQ",
        last_trade_date_or_contract_month=args.contract_month,
        expected_point_value=2.0,
    )
    trader_config = LivePaperTraderConfig(
        live_signal_path=Path(args.live_signal),
        state_path=Path(args.state_path),
        strategy_id=BA_NO_TRADE_COMBO_STRATEGY_ID,
        selected_alias=BA_NO_TRADE_COMBO_ALIAS,
        signal_mode="strategy",
        strategy_spec=ba_no_trade_combo_spec(),
        strategy_signal=LiveStrategySignalConfig(
            history_path=Path(args.history_path),
            max_history_minutes=240,
            tick_interval_seconds=args.tick_interval_seconds,
            min_bars=220,
        ),
        contract=contract,
        account=args.account,
        quantity=args.quantity,
        max_hold_minutes=60,
        submit=args.submit,
        skip_when_position_open=not args.allow_existing_exposure,
        paper_validation_gate_enabled=not args.skip_paper_validation_gate,
        paper_validation_accrual_mode=args.submit and not args.strict_paper_validation_gate,
        paper_validation_gate=PaperValidationGateConfig(
            min_ibkr_ready=1,
            min_ibkr_submitted=1,
            min_paper_outcomes=args.min_paper_outcomes,
            min_paper_net_points=args.min_paper_net_points,
            min_paper_win_rate=args.min_paper_win_rate,
            max_consecutive_losses=args.max_consecutive_losses,
            max_allowed_blocker_count=args.max_allowed_blocker_count,
        ),
        trade_log_dir=Path(args.trade_log_dir),
        realtime_ledger_path=Path(args.realtime_ledger),
        realtime_ledger_csv_path=Path(args.realtime_ledger_csv),
        agent_audit_path=Path(args.agent_audit),
        ibkr_audit_path=Path(args.ibkr_audit),
        tick_recorder=IBKRTickRecorderConfig(
            output_dir=Path(args.tick_output_dir),
            symbol="MNQ",
            contract_month=args.contract_month,
            interval_seconds=args.tick_interval_seconds,
            max_ticks=args.max_ticks,
            enabled=args.record_ticks,
        ),
    )
    broker = None
    if args.client_id is not None or args.account is not None:
        connection = IBKRConnectionConfig.from_env()
        broker = IBKRPaperBroker(
            connection=IBKRConnectionConfig(
                host=connection.host,
                port=connection.port,
                client_id=args.client_id if args.client_id is not None else connection.client_id,
                account=args.account or connection.account,
                timeout=connection.timeout,
                readonly=connection.readonly,
            ),
            audit_path=Path(args.ibkr_audit),
        )
    daemon_config = LivePaperTraderDaemonConfig(
        trader=trader_config,
        interval_seconds=args.interval_seconds,
        max_iterations=None if args.daemon and args.max_iterations == 0 else args.max_iterations,
        preflight_attempts=args.preflight_attempts,
        preflight_retry_seconds=args.preflight_retry_seconds,
        require_preflight_ready=not args.skip_startup_preflight_gate,
        status_path=Path(args.status_path),
    )
    result = (
        run_live_paper_trader_daemon(config=daemon_config, broker=broker)
        if args.daemon
        else run_live_paper_trader_once(config=trader_config, broker=broker)
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    ok_statuses = {"completed", "dry_run", "submitted", "duplicate_skipped", "signal_blocked"}
    return 0 if result.get("status") in ok_statuses else 2


if __name__ == "__main__":
    raise SystemExit(main())
