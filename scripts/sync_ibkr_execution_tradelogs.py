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


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Sync IBKR paper execution fills into dated Chinese trade logs.")
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--client-id", type=int, default=None)
    parser.add_argument("--trade-log-dir", default="docs/Strategy/tradelogs")
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
    print(json.dumps({"status": "synced", "fills": len(fills), "paths": sorted(set(paths))}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
