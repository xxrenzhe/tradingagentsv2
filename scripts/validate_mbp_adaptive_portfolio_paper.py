from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.execution import AgentGateConfig, AgentStrategyGate, IBKRPaperBroker, IBKRPaperTradingSession
from tradingagents.config.env import load_project_env
from tradingagents.execution.paper_validation import build_paper_intent_from_trade, load_trade_samples, select_trade_sample


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Validate adaptive MBP portfolio paper trading with IBKR.")
    parser.add_argument("--trades", default=".tmp/mbp-adaptive-portfolio-trades.csv")
    parser.add_argument("--trade-date", default=None, help="Select a trade sample by trade_date (YYYY-MM-DD).")
    parser.add_argument("--portfolio-rule", default=None, help="Select a trade sample by portfolio_rule.")
    parser.add_argument("--selected-alias", default=None, help="Select a trade sample by selected_alias.")
    parser.add_argument("--row-index", type=int, default=None, help="Select a row index from the filtered trade samples.")
    parser.add_argument("--contract-month", default="202606", help="IBKR futures contract month, e.g. 202606.")
    parser.add_argument("--account", default=None, help="IBKR account override.")
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--stop-loss-points", type=float, default=16.0)
    parser.add_argument("--take-profit-points", type=float, default=24.0)
    parser.add_argument("--submit", action="store_true", help="Submit to IBKR paper instead of dry-run.")
    parser.add_argument("--preflight", action="store_true", help="Run IBKR readiness preflight before dry-run.")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip readiness preflight even when submitting.")
    parser.add_argument("--current-position", type=int, default=0)
    parser.add_argument("--audit-path", default=None)
    parser.add_argument("--agent-gate", action="store_true", help="Require multi-agent strategy review before paper submit.")
    parser.add_argument("--skip-agent-gate", action="store_true", help="Disable multi-agent review even if enabled in .env.")
    args = parser.parse_args()

    trades = load_trade_samples(Path(args.trades))
    sample = select_trade_sample(
        trades,
        trade_date=args.trade_date,
        portfolio_rule=args.portfolio_rule,
        selected_alias=args.selected_alias,
        row_index=args.row_index,
    )
    intent = build_paper_intent_from_trade(
        sample,
        contract_month=args.contract_month,
        account=args.account,
        quantity=args.quantity,
        stop_loss_points=args.stop_loss_points,
        take_profit_points=args.take_profit_points,
    )
    agent_gate_result = None
    gate_config = AgentGateConfig.from_env()
    use_agent_gate = (gate_config.enabled or args.agent_gate) and not args.skip_agent_gate
    if use_agent_gate:
        agent_gate_result = AgentStrategyGate(gate_config).review(
            intent,
            trade_date=str(sample.get("trade_date", "")),
            selected_trade=sample.to_dict(),
        )
        if not agent_gate_result["passed"]:
            output = {
                "selected_trade": sample.to_dict(),
                "agent_gate": agent_gate_result,
                "intent": agent_gate_result["intent"],
                "result": {
                    "status": "agent_gate_rejected",
                    "submitted": False,
                    "agent_gate": agent_gate_result,
                },
            }
            print(json.dumps(output, indent=2, sort_keys=True, default=str))
            return 0
    broker = IBKRPaperBroker(audit_path=args.audit_path)
    if args.submit or args.preflight:
        response = IBKRPaperTradingSession.from_env(broker).submit_intent(
            intent,
            dry_run=not args.submit,
            skip_preflight=args.skip_preflight,
        )
    else:
        response = broker.submit(intent, dry_run=True, current_position=args.current_position)
    output = {
        "selected_trade": sample.to_dict(),
        "agent_gate": agent_gate_result,
        "intent": response["intent"],
        "result": response,
    }
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
