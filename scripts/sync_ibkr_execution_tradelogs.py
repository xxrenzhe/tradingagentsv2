from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.config.env import load_project_env
from tradingagents.execution import IBKRConnectionConfig, IBKRPaperBroker
from tradingagents.execution.trade_log import append_execution_fill_log
from tradingagents.execution.trade_outcome_inference import infer_outcomes, record_outcomes


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Sync IBKR paper execution fills into dated Chinese trade logs.")
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--client-id", type=int, default=None)
    parser.add_argument("--trade-log-dir", default="docs/Strategy/tradelogs")
    parser.add_argument("--strategy-id", default=None)
    parser.add_argument("--agent-audit", default=".tmp/agent-gate-audit.jsonl")
    parser.add_argument("--no-sync-paper-outcomes", action="store_true")
    parser.add_argument("--update-memory-from-outcomes", action="store_true")
    args = parser.parse_args()

    connection = IBKRConnectionConfig.from_env()
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(
            host=connection.host,
            port=connection.port,
            client_id=args.client_id if args.client_id is not None else connection.client_id,
            account=connection.account,
            timeout=connection.timeout,
            readonly=connection.readonly,
        )
    )
    connected = broker.connect()
    if not connected.get("connected"):
        print(json.dumps({"status": "connect_failed", "connection": connected}, indent=2, sort_keys=True, default=str))
        return 2
    fills = broker.execution_fills(symbol=args.symbol.upper())
    paths = []
    for fill in fills:
        path = append_execution_fill_log(fill, log_dir=Path(args.trade_log_dir))
        if path is not None:
            paths.append(str(path))
    outcome_sync = {"status": "disabled", "recorded": 0}
    if not args.no_sync_paper_outcomes:
        outcomes = infer_outcomes(Path(args.trade_log_dir), strategy_id=args.strategy_id)
        high_confidence = [outcome for outcome in outcomes if outcome.confidence == "target_or_stop_hit"]
        recorded = record_outcomes(
            outcomes,
            audit_path=Path(args.agent_audit),
            update_memory=args.update_memory_from_outcomes,
        )
        outcome_sync = {
            "status": "synced",
            "outcomes": len(outcomes),
            "high_confidence": len(high_confidence),
            "recorded": recorded,
            "audit_path": args.agent_audit,
        }
    print(
        json.dumps(
            {"status": "synced", "fills": len(fills), "paths": sorted(set(paths)), "paper_outcomes": outcome_sync},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
