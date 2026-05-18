from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tradingagents.execution import IBKRConnectionConfig, IBKRContractSpec, IBKRPaperBroker, IBKRPaperTradingSession
from tradingagents.execution.ibkr import IBKROrderIntent
from tradingagents.config.env import load_project_env


def _contract_from_args(args: argparse.Namespace) -> IBKRContractSpec:
    symbol = args.symbol.upper()
    point_value = 2.0 if symbol == "MNQ" else 20.0
    return IBKRContractSpec(
        symbol=symbol,
        exchange=args.exchange,
        currency=args.currency,
        last_trade_date_or_contract_month=args.contract_month,
        expected_tick_size=float(os.getenv("TRADINGAGENTS_IBKR_TICK_SIZE", "0.25")),
        expected_point_value=float(os.getenv("TRADINGAGENTS_IBKR_POINT_VALUE", str(point_value))),
    )


def _connection_from_args(args: argparse.Namespace) -> IBKRConnectionConfig:
    base = IBKRConnectionConfig.from_env()
    return IBKRConnectionConfig(
        host=args.host or base.host,
        port=args.port or base.port,
        client_id=args.client_id if args.client_id is not None else base.client_id,
        account=args.account or base.account,
        timeout=base.timeout,
        readonly=base.readonly,
    )


def _manual_intent(args: argparse.Namespace) -> IBKROrderIntent:
    if args.action is None:
        raise SystemExit("--action is required when --intent is not provided")
    if args.stop_loss_points <= 0 or args.take_profit_points <= 0:
        raise SystemExit("--stop-loss-points and --take-profit-points must be positive")
    direction_price = 100000.0
    action = args.action.upper()
    if action == "BUY":
        stop_loss_price = direction_price - args.stop_loss_points
        take_profit_price = direction_price + args.take_profit_points
    else:
        stop_loss_price = direction_price + args.stop_loss_points
        take_profit_price = direction_price - args.take_profit_points
    reason = (
        f"manual immediate paper order | stop_loss_points={args.stop_loss_points:.4f} "
        f"| take_profit_points={args.take_profit_points:.4f}"
    )
    return IBKROrderIntent(
        action=action,
        quantity=args.quantity,
        symbol=args.symbol.upper(),
        exchange=args.exchange,
        currency=args.currency,
        last_trade_date_or_contract_month=args.contract_month,
        order_type=args.order_type,
        stop_loss_price=round(stop_loss_price, 2),
        take_profit_price=round(take_profit_price, 2),
        account=args.account,
        strategy_id=args.strategy_id,
        reason=reason,
    )


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Submit or dry-run an IBKR paper-trading order intent.")
    parser.add_argument("--intent", default=None, help="Path to a JSON IBKROrderIntent payload.")
    parser.add_argument("--action", choices=["BUY", "SELL", "buy", "sell"], default=None, help="Immediate manual order side.")
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--symbol", default=os.getenv("TRADINGAGENTS_IBKR_SYMBOL", "MNQ"))
    parser.add_argument("--exchange", default=os.getenv("TRADINGAGENTS_IBKR_EXCHANGE", "CME"))
    parser.add_argument("--currency", default=os.getenv("TRADINGAGENTS_IBKR_CURRENCY", "USD"))
    parser.add_argument("--contract-month", default=os.getenv("TRADINGAGENTS_IBKR_CONTRACT_MONTH", "202606"))
    parser.add_argument("--account", default=os.getenv("TRADINGAGENTS_IBKR_ACCOUNT") or None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--client-id", type=int, default=None)
    parser.add_argument("--order-type", choices=["MKT"], default="MKT")
    parser.add_argument("--stop-loss-points", type=float, default=16.0)
    parser.add_argument("--take-profit-points", type=float, default=24.0)
    parser.add_argument("--strategy-id", default="manual_immediate_paper_order")
    parser.add_argument("--max-spread-ticks", type=float, default=None)
    parser.add_argument("--submit", action="store_true", help="Actually submit to IBKR paper. Default is dry-run.")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip IBKR readiness preflight before submit.")
    parser.add_argument("--audit-path", default=None, help="Override audit JSONL output path.")
    args = parser.parse_args()

    if args.intent:
        payload = json.loads(Path(args.intent).read_text(encoding="utf-8"))
        intent = IBKROrderIntent(**payload)
        contract = IBKRContractSpec(
            symbol=intent.symbol,
            exchange=intent.exchange,
            currency=intent.currency,
            last_trade_date_or_contract_month=intent.last_trade_date_or_contract_month,
            expected_point_value=2.0 if intent.symbol.upper() == "MNQ" else 20.0,
        )
    else:
        intent = _manual_intent(args)
        contract = _contract_from_args(args)
    broker = IBKRPaperBroker(connection=_connection_from_args(args), audit_path=args.audit_path)
    session = IBKRPaperTradingSession(broker=broker, contract=contract)
    if args.max_spread_ticks is not None:
        session.max_spread_ticks = args.max_spread_ticks
    response = session.submit_intent(
        intent,
        dry_run=not args.submit,
        skip_preflight=args.skip_preflight,
    )
    print(json.dumps(response, indent=2, sort_keys=True, default=str))
    return 0 if response.get("status") in {"dry_run", "submitted"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
