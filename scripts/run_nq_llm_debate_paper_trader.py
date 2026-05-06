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
    DebateDelayedStrategyConfig,
    FeatureScannerConfig,
    IBKRConnectionConfig,
    IBKRContractSpec,
    IBKRPaperBroker,
    RealtimeDebateTraderConfig,
    load_tradeable_feature_sets,
    planner_from_env_or_args,
    run_debate_delayed_scanner_daemon,
    run_debate_delayed_scanner_once,
    run_debate_delayed_strategy_once,
    run_realtime_debate_trader,
    select_feature_trigger,
)


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(
        description=(
            "Run one NQ feature-triggered LLM debate delayed IBKR paper-trading decision. "
            "Default is dry-run; use --submit only for paper submission."
        )
    )
    parser.add_argument("--feature-sets", default="reports/NQ-5y-high-win-payoff-past-fold-validation.csv")
    parser.add_argument("--feature-set", default=None, help="Exact feature_set to trade. Default selects first qualified row.")
    parser.add_argument("--trigger-price", type=float, default=None)
    parser.add_argument("--trigger-time", default=None, help="ISO timestamp for the script-scanned trigger. Default is now.")
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--contract-month", default="202606")
    parser.add_argument("--account", default=None)
    parser.add_argument("--client-id", type=int, default=None, help="Override IBKR client id for this process.")
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--submit", action="store_true", help="Actually submit to IBKR paper. Default is dry-run.")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--allow-existing-exposure", action="store_true")
    parser.add_argument("--min-win-rate", type=float, default=0.53, help="Strict lower bound; default requires win_rate > 53%.")
    parser.add_argument("--min-payoff-ratio", type=float, default=1.0, help="Strict lower bound; default requires payoff_ratio_r > 1R.")
    parser.add_argument("--min-net-points", type=float, default=0.0)
    parser.add_argument("--max-signal-age-seconds", type=float, default=300.0)
    parser.add_argument("--snapshot-attempts", type=int, default=3)
    parser.add_argument("--snapshot-retry-seconds", type=float, default=1.0)
    parser.add_argument("--audit-path", default=".tmp/nq-llm-debate-paper-audit.jsonl")
    parser.add_argument("--state-path", default=".tmp/nq-llm-debate-paper-state.json")
    parser.add_argument("--scan", action="store_true", help="Scan IBKR snapshots for a qualifying feature trigger before LLM debate.")
    parser.add_argument("--scanner-history", default=".tmp/nq-llm-debate-scanner-history.jsonl")
    parser.add_argument("--scanner-state", default=".tmp/nq-llm-debate-scanner-state.json")
    parser.add_argument("--scanner-min-history-points", type=int, default=7)
    parser.add_argument("--scanner-max-history-points", type=int, default=180)
    parser.add_argument("--scanner-cooldown-seconds", type=float, default=120.0)
    parser.add_argument("--support-reclaim-points", type=float, default=1.0)
    parser.add_argument("--max-support-reclaim-points", type=float, default=12.0)
    parser.add_argument("--vwap-distance-z-threshold", type=float, default=0.67)
    parser.add_argument("--allow-not-order-ready-scan", action="store_true")
    parser.add_argument("--decision-json", default=None, help="Deterministic debate JSON. Overrides LLM/env planner.")
    parser.add_argument("--llm-provider", default=None, help="LLM provider for debate planner, or env TRADINGAGENTS_NQ_DEBATE_LLM_PROVIDER.")
    parser.add_argument("--llm-model", default=None, help="LLM model for debate planner, or env TRADINGAGENTS_NQ_DEBATE_LLM_MODEL.")
    parser.add_argument("--llm-base-url", default=None)
    parser.add_argument(
        "--no-enforce-delay",
        action="store_true",
        help="Skip waiting recheck_after_seconds. Use for deterministic tests only.",
    )
    parser.add_argument("--daemon", action="store_true", help="Run scanner loop. Requires --scan.")
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--max-iterations", type=int, default=1, help="Use 0 with --daemon to run until stopped.")
    parser.add_argument("--realtime", action="store_true", help="Run the full realtime preflight + scanner + LLM debate + IBKR paper loop. Implies --scan --daemon.")
    parser.add_argument("--status-path", default=".tmp/nq-llm-debate-realtime-status.json")
    parser.add_argument("--preflight-attempts", type=int, default=3)
    parser.add_argument("--preflight-retry-seconds", type=float, default=1.0)
    parser.add_argument("--skip-startup-preflight-gate", action="store_true")
    args = parser.parse_args()

    if args.realtime:
        args.scan = True
        args.daemon = True
    if not args.scan and args.trigger_price is None:
        raise SystemExit("--trigger-price is required unless --scan is enabled")
    if args.daemon and not args.scan:
        raise SystemExit("--daemon requires --scan")

    contract = IBKRContractSpec(
        symbol=args.symbol.upper(),
        last_trade_date_or_contract_month=args.contract_month,
        expected_point_value=2.0 if args.symbol.upper() == "MNQ" else 20.0,
    )
    config = DebateDelayedStrategyConfig(
        feature_sets_path=Path(args.feature_sets),
        audit_path=Path(args.audit_path),
        state_path=Path(args.state_path),
        contract=contract,
        account=args.account,
        quantity=args.quantity,
        submit=args.submit,
        skip_preflight=args.skip_preflight,
        min_win_rate=args.min_win_rate,
        min_payoff_ratio=args.min_payoff_ratio,
        min_net_points=args.min_net_points,
        max_signal_age_seconds=args.max_signal_age_seconds,
        snapshot_attempts=args.snapshot_attempts,
        snapshot_retry_seconds=args.snapshot_retry_seconds,
        allow_existing_exposure=args.allow_existing_exposure,
        enforce_delay=not args.no_enforce_delay,
    )
    feature_sets = load_tradeable_feature_sets(
        config.feature_sets_path,
        min_win_rate=config.min_win_rate,
        min_payoff_ratio=config.min_payoff_ratio,
        min_net_points=config.min_net_points,
    )
    planner = planner_from_env_or_args(
        decision_json=args.decision_json,
        provider=args.llm_provider,
        model=args.llm_model,
        base_url=args.llm_base_url,
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
    if args.scan:
        scanner_config = FeatureScannerConfig(
            history_path=Path(args.scanner_history),
            state_path=Path(args.scanner_state),
            feature_set=args.feature_set,
            min_history_points=args.scanner_min_history_points,
            max_history_points=args.scanner_max_history_points,
            cooldown_seconds=args.scanner_cooldown_seconds,
            support_reclaim_points=args.support_reclaim_points,
            max_support_reclaim_points=args.max_support_reclaim_points,
            vwap_distance_z_threshold=args.vwap_distance_z_threshold,
            require_order_ready=not args.allow_not_order_ready_scan,
        )
        if args.realtime:
            result = run_realtime_debate_trader(
                feature_sets=feature_sets,
                planner=planner,
                config=RealtimeDebateTraderConfig(
                    strategy=config,
                    scanner=scanner_config,
                    interval_seconds=args.interval_seconds,
                    max_iterations=None if args.max_iterations == 0 else args.max_iterations,
                    preflight_attempts=args.preflight_attempts,
                    preflight_retry_seconds=args.preflight_retry_seconds,
                    require_preflight_ready=not args.skip_startup_preflight_gate,
                    status_path=Path(args.status_path),
                ),
                broker=broker,
            )
        elif args.daemon:
            result = run_debate_delayed_scanner_daemon(
                feature_sets=feature_sets,
                planner=planner,
                strategy_config=config,
                scanner_config=scanner_config,
                broker=broker,
                interval_seconds=args.interval_seconds,
                max_iterations=None if args.max_iterations == 0 else args.max_iterations,
            )
        else:
            result = run_debate_delayed_scanner_once(
                feature_sets=feature_sets,
                planner=planner,
                strategy_config=config,
                scanner_config=scanner_config,
                broker=broker,
            )
    else:
        trigger = select_feature_trigger(
            feature_sets,
            feature_set=args.feature_set,
            trigger_price=float(args.trigger_price),
            trigger_time=args.trigger_time,
        )
        result = run_debate_delayed_strategy_once(trigger=trigger, planner=planner, config=config, broker=broker)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    ok_statuses = {"completed", "dry_run", "submitted", "no_trade_after_recheck", "duplicate_skipped", "no_feature_trigger"}
    return 0 if result.get("status") in ok_statuses else 2


if __name__ == "__main__":
    raise SystemExit(main())
