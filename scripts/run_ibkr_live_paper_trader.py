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
    BEST_MEAN_REVERSION_ALIAS,
    BEST_MEAN_REVERSION_STRATEGY_ID,
    IBKRConnectionConfig,
    IBKRContractSpec,
    IBKRTickRecorderConfig,
    IBKRPaperBroker,
    LivePaperTraderConfig,
    LivePaperTraderDaemonConfig,
    PaperValidationGateConfig,
    LiveStrategySpec,
    LiveStrategySignalConfig,
    ba_no_trade_combo_spec,
    run_live_paper_trader_daemon,
    run_live_paper_trader_once,
    regime_transition_spec,
)

DEFAULT_STRATEGY_ID = BEST_MEAN_REVERSION_STRATEGY_ID
DEFAULT_SELECTED_ALIAS = BEST_MEAN_REVERSION_ALIAS


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Run a strategy-gated live IBKR paper-trading loop.")
    parser.add_argument("--live-signal", default=".tmp/mbp-live-signal.csv")
    parser.add_argument("--state-path", default=".tmp/mbp-live-paper-trader-state.json")
    parser.add_argument("--strategy-id", default=DEFAULT_STRATEGY_ID)
    parser.add_argument("--selected-alias", default=DEFAULT_SELECTED_ALIAS)
    parser.add_argument(
        "--strategy-family",
        choices=["mean_reversion", "mtf_setup", "regime_transition", "ba_no_trade_combo"],
        default="mean_reversion",
    )
    parser.add_argument("--imbalance-threshold", type=float, default=None)
    parser.add_argument("--signal-mode", choices=["strategy", "manual"], default="strategy")
    parser.add_argument("--direction", choices=["buy", "sell", "BUY", "SELL"], default=None)
    parser.add_argument("--history-path", default=".tmp/mbp-live-market-history.jsonl")
    parser.add_argument("--max-history-minutes", type=int, default=120)
    parser.add_argument("--min-bars", type=int, default=7)
    parser.add_argument("--strategy-session", choices=["all", "europe"], default="all")
    parser.add_argument("--htf-mode", choices=["off", "bias", "confirm"], default="off")
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
    parser.add_argument("--skip-paper-validation-gate", action="store_true")
    parser.add_argument(
        "--paper-validation-accrual-mode",
        action="store_true",
        help="Allow paper submit while the only paper-validation blocker is insufficient outcome count.",
    )
    parser.add_argument("--min-ibkr-ready", type=int, default=1)
    parser.add_argument("--min-ibkr-submitted", type=int, default=1)
    parser.add_argument("--min-paper-outcomes", type=int, default=20)
    parser.add_argument("--min-paper-net-points", type=float, default=0.0)
    parser.add_argument("--min-paper-win-rate", type=float, default=45.0)
    parser.add_argument("--max-consecutive-losses", type=int, default=4)
    parser.add_argument("--max-allowed-blocker-count", type=int, default=0)
    parser.add_argument("--snapshot-attempts", type=int, default=3)
    parser.add_argument("--snapshot-retry-seconds", type=float, default=1.0)
    parser.add_argument("--allow-existing-exposure", action="store_true", help="Do not block when a position/open order already exists.")
    parser.add_argument("--record-ticks", action="store_true")
    parser.add_argument("--tick-output-dir", default=".tmp/ibkr-paper-ticks")
    parser.add_argument("--tick-interval-seconds", type=float, default=1.0)
    parser.add_argument("--max-ticks", type=int, default=60)
    parser.add_argument("--trade-log-dir", default="docs/Strategy/tradelogs")
    parser.add_argument("--no-sync-execution-logs", action="store_true")
    parser.add_argument("--no-sync-paper-outcomes", action="store_true")
    parser.add_argument("--agent-audit", default=".tmp/agent-gate-audit.jsonl")
    parser.add_argument("--ibkr-audit", default=".tmp/ibkr-paper-audit.jsonl")
    parser.add_argument("--update-memory-from-outcomes", action="store_true")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--max-iterations", type=int, default=1, help="Use 0 to run until stopped.")
    parser.add_argument("--status-path", default=".tmp/mbp-live-paper-trader-status.json")
    parser.add_argument("--preflight-attempts", type=int, default=3)
    parser.add_argument("--preflight-retry-seconds", type=float, default=1.0)
    parser.add_argument("--skip-startup-preflight-gate", action="store_true")
    args = parser.parse_args()
    base_connection = IBKRConnectionConfig.from_env()

    if args.signal_mode == "manual" and args.direction is None:
        raise SystemExit("--direction is required when --signal-mode manual")
    direction = 0 if args.direction is None else (1 if args.direction.lower() == "buy" else -1)
    strategy_id = args.strategy_id
    selected_alias = args.selected_alias
    if args.strategy_family == "mtf_setup" and strategy_id == DEFAULT_STRATEGY_ID and selected_alias == DEFAULT_SELECTED_ALIAS:
        strategy_id = "mtf_setup"
        selected_alias = "mtf_setup"
    if args.strategy_family == "ba_no_trade_combo" and strategy_id == DEFAULT_STRATEGY_ID and selected_alias == DEFAULT_SELECTED_ALIAS:
        strategy_id = BA_NO_TRADE_COMBO_STRATEGY_ID
        selected_alias = BA_NO_TRADE_COMBO_ALIAS
    strategy_spec = (
        regime_transition_spec(strategy_id, selected_alias)
        if args.strategy_family == "regime_transition"
        else ba_no_trade_combo_spec(strategy_id, selected_alias)
        if args.strategy_family == "ba_no_trade_combo"
        else LiveStrategySpec(
            strategy_id=strategy_id,
            selected_alias=selected_alias,
            family=args.strategy_family,
            session=args.strategy_session,
            htf_mode=args.htf_mode,
            imbalance_threshold=0.3 if args.imbalance_threshold is None else args.imbalance_threshold,
        )
    )
    config = LivePaperTraderConfig(
        live_signal_path=Path(args.live_signal),
        state_path=Path(args.state_path),
        strategy_id=strategy_id,
        selected_alias=selected_alias,
        direction=direction,
        signal_mode=args.signal_mode,
        strategy_spec=strategy_spec,
        strategy_signal=LiveStrategySignalConfig(
            history_path=Path(args.history_path),
            max_history_minutes=args.max_history_minutes,
            tick_interval_seconds=args.tick_interval_seconds,
            min_bars=args.min_bars,
        ),
        contract=IBKRContractSpec(
            symbol=args.symbol.upper(),
            last_trade_date_or_contract_month=args.contract_month,
            expected_point_value=2.0 if args.symbol.upper() == "MNQ" else 20.0,
        ),
        account=args.account or base_connection.account,
        quantity=args.quantity,
        stop_loss_points=args.stop_loss_points,
        take_profit_points=args.take_profit_points,
        max_hold_minutes=args.max_hold_minutes,
        submit=args.submit,
        require_agent_gate=args.agent_gate,
        skip_preflight=args.skip_preflight,
        paper_validation_gate_enabled=not args.skip_paper_validation_gate,
        paper_validation_accrual_mode=args.paper_validation_accrual_mode,
        paper_validation_gate=PaperValidationGateConfig(
            min_ibkr_ready=args.min_ibkr_ready,
            min_ibkr_submitted=args.min_ibkr_submitted,
            min_paper_outcomes=args.min_paper_outcomes,
            min_paper_net_points=args.min_paper_net_points,
            min_paper_win_rate=args.min_paper_win_rate,
            max_consecutive_losses=args.max_consecutive_losses,
            max_allowed_blocker_count=args.max_allowed_blocker_count,
        ),
        snapshot_attempts=args.snapshot_attempts,
        snapshot_retry_seconds=args.snapshot_retry_seconds,
        skip_when_position_open=not args.allow_existing_exposure,
        trade_log_dir=Path(args.trade_log_dir),
        sync_execution_logs=not args.no_sync_execution_logs,
        sync_paper_outcomes=not args.no_sync_paper_outcomes,
        agent_audit_path=Path(args.agent_audit),
        ibkr_audit_path=Path(args.ibkr_audit),
        update_memory_from_outcomes=args.update_memory_from_outcomes,
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
        broker = IBKRPaperBroker(
            connection=IBKRConnectionConfig(
                host=base_connection.host,
                port=base_connection.port,
                client_id=args.client_id,
                account=base_connection.account,
                timeout=base_connection.timeout,
                readonly=base_connection.readonly,
            )
        )
    if args.daemon:
        result = run_live_paper_trader_daemon(
            config=LivePaperTraderDaemonConfig(
                trader=config,
                interval_seconds=args.interval_seconds,
                max_iterations=None if args.max_iterations == 0 else args.max_iterations,
                preflight_attempts=args.preflight_attempts,
                preflight_retry_seconds=args.preflight_retry_seconds,
                require_preflight_ready=not args.skip_startup_preflight_gate,
                status_path=Path(args.status_path),
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
