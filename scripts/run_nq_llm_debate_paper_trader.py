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
    IBKRConnectionConfig,
    IBKRContractSpec,
    IBKRPaperBroker,
    load_tradeable_feature_sets,
    planner_from_env_or_args,
    run_debate_delayed_strategy_once,
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
    parser.add_argument("--trigger-price", type=float, required=True)
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
    parser.add_argument("--decision-json", default=None, help="Deterministic debate JSON. Overrides LLM/env planner.")
    parser.add_argument("--llm-provider", default=None, help="LLM provider for debate planner, or env TRADINGAGENTS_NQ_DEBATE_LLM_PROVIDER.")
    parser.add_argument("--llm-model", default=None, help="LLM model for debate planner, or env TRADINGAGENTS_NQ_DEBATE_LLM_MODEL.")
    parser.add_argument("--llm-base-url", default=None)
    parser.add_argument(
        "--no-enforce-delay",
        action="store_true",
        help="Skip waiting recheck_after_seconds. Use for deterministic tests only.",
    )
    args = parser.parse_args()

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
    trigger = select_feature_trigger(
        feature_sets,
        feature_set=args.feature_set,
        trigger_price=args.trigger_price,
        trigger_time=args.trigger_time,
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
    result = run_debate_delayed_strategy_once(trigger=trigger, planner=planner, config=config, broker=broker)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("status") in {"dry_run", "submitted", "no_trade_after_recheck", "duplicate_skipped"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
