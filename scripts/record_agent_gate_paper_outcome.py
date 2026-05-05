from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.config.env import load_project_env
from tradingagents.execution import AgentGateConfig, PaperTradeOutcome, record_agent_gate_outcome


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Record a paper-trading outcome for the multi-agent strategy gate.")
    parser.add_argument("--strategy-id", required=True)
    parser.add_argument("--intent-id", default=None)
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--action", choices=["BUY", "SELL"], required=True)
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--trade-date", default=None)
    parser.add_argument("--entry-time", default=None)
    parser.add_argument("--exit-time", default=None)
    parser.add_argument("--entry-price", type=float, default=None)
    parser.add_argument("--exit-price", type=float, default=None)
    parser.add_argument("--points", type=float, default=None)
    parser.add_argument("--commission", type=float, default=None)
    parser.add_argument("--slippage-points", type=float, default=None)
    parser.add_argument("--exit-reason", default=None)
    parser.add_argument("--source", default="paper", choices=["paper", "shadow", "shadow_backtest", "manual"])
    parser.add_argument("--notes", default="")
    parser.add_argument("--audit-path", default=None)
    parser.add_argument("--memory-log-path", default=None)
    parser.add_argument("--no-memory-update", action="store_true")
    args = parser.parse_args()

    outcome = PaperTradeOutcome(
        strategy_id=args.strategy_id,
        intent_id=args.intent_id,
        symbol=args.symbol,
        action=args.action,
        quantity=args.quantity,
        trade_date=args.trade_date,
        entry_time=args.entry_time,
        exit_time=args.exit_time,
        entry_price=args.entry_price,
        exit_price=args.exit_price,
        points=args.points,
        commission=args.commission,
        slippage_points=args.slippage_points,
        exit_reason=args.exit_reason,
        source=args.source,
        notes=args.notes,
    )
    audit_path = args.audit_path or AgentGateConfig.from_env().audit_path
    event = record_agent_gate_outcome(
        outcome,
        audit_path=audit_path,
        memory_log_path=args.memory_log_path,
        update_memory=not args.no_memory_update,
    )
    print(json.dumps(event, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
