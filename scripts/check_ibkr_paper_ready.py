from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.execution import IBKRConnectionConfig, IBKRContractSpec, IBKRPaperBroker, IBKRPaperTradingSession
from tradingagents.config.env import load_project_env


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Check IBKR paper readiness for the configured futures contract.")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--client-id", type=int, default=None)
    parser.add_argument("--account", default=None)
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--exchange", default=None)
    parser.add_argument("--currency", default=None)
    parser.add_argument("--contract-month", default=None)
    parser.add_argument("--max-spread-ticks", type=float, default=None)
    parser.add_argument("--skip-market-data", action="store_true")
    args = parser.parse_args()

    base_connection = IBKRConnectionConfig.from_env()
    symbol = (args.symbol or os.getenv("TRADINGAGENTS_IBKR_SYMBOL", "MNQ")).upper()
    point_value = 2.0 if symbol == "MNQ" else 20.0
    contract = IBKRContractSpec(
        symbol=symbol,
        exchange=args.exchange or os.getenv("TRADINGAGENTS_IBKR_EXCHANGE", "CME"),
        currency=args.currency or os.getenv("TRADINGAGENTS_IBKR_CURRENCY", "USD"),
        last_trade_date_or_contract_month=args.contract_month
        or os.getenv("TRADINGAGENTS_IBKR_CONTRACT_MONTH", "202606"),
        expected_tick_size=float(os.getenv("TRADINGAGENTS_IBKR_TICK_SIZE", "0.25")),
        expected_point_value=float(os.getenv("TRADINGAGENTS_IBKR_POINT_VALUE", str(point_value))),
    )
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(
            host=args.host or base_connection.host,
            port=args.port or base_connection.port,
            client_id=args.client_id if args.client_id is not None else base_connection.client_id,
            account=args.account or base_connection.account,
            timeout=base_connection.timeout,
            readonly=base_connection.readonly,
        )
    )
    session = IBKRPaperTradingSession.from_env(broker)
    session.contract = contract
    if args.max_spread_ticks is not None:
        session.max_spread_ticks = args.max_spread_ticks
    result = session.preflight(include_market_data=not args.skip_market_data)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["readiness"]["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
