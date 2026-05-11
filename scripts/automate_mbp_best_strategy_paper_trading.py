from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.config.env import load_project_env
from tradingagents.execution import (
    IBKRConnectionConfig,
    IBKRPaperBroker,
    IBKRPaperTradingSession,
    IBKRTickRecorderConfig,
    PaperDaemonConfig,
    PaperRunnerConfig,
    PaperValidationGateConfig,
    run_adaptive_portfolio_paper_daemon,
    run_adaptive_portfolio_paper_once,
    summarize_paper_audits,
)

BEST_STRATEGY_ID = "adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3"
BEST_SELECTED_ALIAS = "best_strategy"


def main() -> int:
    load_project_env(override=False)
    parser = argparse.ArgumentParser(description="Guarded automation supervisor for the selected best MBP strategy on IBKR paper.")
    parser.add_argument("--trades", default=".tmp/mbp-best-strategy-trades.csv")
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--trade-date", default=None)
    parser.add_argument("--row-index", type=int, default=None)
    parser.add_argument("--state-path", default=".tmp/mbp-best-strategy-paper-runner-state.json")
    parser.add_argument("--contract-month", default="202606")
    parser.add_argument("--account", default=None)
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--stop-loss-points", type=float, default=16.0)
    parser.add_argument("--take-profit-points", type=float, default=24.0)
    parser.add_argument("--submit", action="store_true", help="Submit to IBKR paper after all supervisor gates pass. Default is dry-run.")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip preflight inside the submit call after supervisor preflight passes.")
    parser.add_argument("--skip-paper-gate", action="store_true", help="Allow --submit without paper-validation history gate. Preflight still applies.")
    parser.add_argument("--agent-gate", action="store_true", help="Require multi-agent review before submit/dry-run.")
    parser.add_argument("--max-signal-age-minutes", type=float, default=10.0)
    parser.add_argument("--allow-stale-signal-submit", action="store_true", help="Disable stale signal blocking for --submit. Use only for controlled tests.")
    parser.add_argument("--agent-audit", default=".tmp/agent-gate-audit.jsonl")
    parser.add_argument("--ibkr-audit", default=".tmp/ibkr-paper-audit.jsonl")
    parser.add_argument("--audit-path", default=None)
    parser.add_argument("--preflight-attempts", type=int, default=3)
    parser.add_argument("--preflight-retry-seconds", type=float, default=1.0)
    parser.add_argument("--client-id", type=int, default=None, help="Override IBKR client id for supervisor preflight.")
    parser.add_argument("--min-ibkr-ready", type=int, default=1)
    parser.add_argument("--min-ibkr-submitted", type=int, default=1)
    parser.add_argument("--min-paper-outcomes", type=int, default=20)
    parser.add_argument("--min-paper-net-points", type=float, default=0.0)
    parser.add_argument("--min-paper-win-rate", type=float, default=45.0)
    parser.add_argument("--max-consecutive-losses", type=int, default=4)
    parser.add_argument("--max-allowed-blocker-count", type=int, default=0)
    parser.add_argument("--record-ticks", action="store_true")
    parser.add_argument("--tick-output-dir", default=".tmp/ibkr-paper-ticks")
    parser.add_argument("--tick-interval-seconds", type=float, default=1.0)
    parser.add_argument("--max-ticks", type=int, default=60)
    parser.add_argument("--daemon", action="store_true", help="Run the guarded loop repeatedly.")
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--max-iterations", type=int, default=1, help="Use 0 for continuous automation until stopped.")
    parser.add_argument("--no-status-snapshot", action="store_true")
    args = parser.parse_args()

    supervisor = _supervisor_gate(args)
    if args.submit and supervisor["status"] != "ready":
        print(json.dumps({"status": "blocked", "submitted": False, "supervisor": supervisor}, indent=2, sort_keys=True, default=str))
        return 2

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
                refresh_report=False,
                status_snapshot=not args.no_status_snapshot,
                trade_date=args.trade_date,
                portfolio_rule=BEST_STRATEGY_ID,
                selected_alias=BEST_SELECTED_ALIAS,
                row_index=args.row_index,
            )
        )
    else:
        result = run_adaptive_portfolio_paper_once(
            config=runner_config,
            trade_date=args.trade_date,
            portfolio_rule=BEST_STRATEGY_ID,
            selected_alias=BEST_SELECTED_ALIAS,
            row_index=args.row_index,
        )
    result["supervisor"] = supervisor
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if args.daemon:
        return 0 if result.get("status") == "completed" else 2
    if result.get("status") in {"agent_gate_rejected", "duplicate_skipped"}:
        return 0
    return 0 if result.get("status") in {"dry_run", "submitted"} else 2


def _supervisor_gate(args: argparse.Namespace) -> dict[str, object]:
    if not args.submit:
        return {
            "status": "ready",
            "mode": "dry_run",
            "strategy_id": BEST_STRATEGY_ID,
            "paper_gate_checked": False,
            "preflight_checked": False,
        }
    preflight = _ready_preflight(
        attempts=args.preflight_attempts,
        retry_seconds=args.preflight_retry_seconds,
        client_id=args.client_id,
    )
    paper_summary = summarize_paper_audits(
        agent_audit_path=args.agent_audit,
        ibkr_audit_path=args.ibkr_audit,
        strategy_id=BEST_STRATEGY_ID,
        gate_config=PaperValidationGateConfig(
            min_ibkr_ready=args.min_ibkr_ready,
            min_ibkr_submitted=args.min_ibkr_submitted,
            min_paper_outcomes=args.min_paper_outcomes,
            min_paper_net_points=args.min_paper_net_points,
            min_paper_win_rate=args.min_paper_win_rate,
            max_consecutive_losses=args.max_consecutive_losses,
            max_allowed_blocker_count=args.max_allowed_blocker_count,
        ),
    )
    blockers = []
    readiness = preflight.get("readiness", {}) if isinstance(preflight, dict) else {}
    if readiness.get("status") != "ready":
        blockers.extend(readiness.get("missing_requirements", []) or ["ibkr_preflight_not_ready"])
    paper_gate = paper_summary["validation_gate"]
    if not args.skip_paper_gate and paper_gate["status"] != "pass":
        blockers.extend(f"paper_validation:{blocker}" for blocker in paper_gate["blockers"])
    return {
        "status": "ready" if not blockers else "blocked",
        "mode": "submit",
        "strategy_id": BEST_STRATEGY_ID,
        "blockers": blockers,
        "preflight": {
            "status": readiness.get("status", "unknown"),
            "missing_requirements": readiness.get("missing_requirements", []),
        },
        "paper_gate": paper_gate,
        "paper_gate_checked": not args.skip_paper_gate,
        "preflight_checked": True,
    }


def _ready_preflight(*, attempts: int, retry_seconds: float, client_id: int | None = None) -> dict[str, object]:
    attempts = max(1, int(attempts))
    last_preflight: dict[str, object] = {}
    for attempt in range(attempts):
        broker = _broker_for_client_id(client_id)
        session = IBKRPaperTradingSession.from_env(broker) if broker is not None else IBKRPaperTradingSession.from_env()
        last_preflight = session.preflight()
        readiness = last_preflight.get("readiness", {})
        if isinstance(readiness, dict) and readiness.get("status") == "ready":
            return last_preflight
        if attempt + 1 < attempts:
            time.sleep(max(0.0, float(retry_seconds)))
    return last_preflight


def _broker_for_client_id(client_id: int | None) -> IBKRPaperBroker | None:
    if client_id is None:
        return None
    connection = IBKRConnectionConfig.from_env()
    return IBKRPaperBroker(
        connection=IBKRConnectionConfig(
            host=connection.host,
            port=connection.port,
            client_id=client_id,
            account=connection.account,
            timeout=connection.timeout,
            readonly=connection.readonly,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
