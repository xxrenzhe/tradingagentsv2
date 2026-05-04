from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.config.env import load_project_env
from tradingagents.execution import IBKRContractSpec, LiveSignalConfig, build_live_signal_row, write_live_signal
from tradingagents.execution.paper_validation import load_trade_samples, select_trade_sample


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Write a fresh live paper-trading signal from IBKR snapshot data.")
    parser.add_argument("--output", default=".tmp/mbp-live-signal.csv")
    parser.add_argument("--from-trades", default=None, help="Derive signal metadata from an exported strategy trades CSV.")
    parser.add_argument("--trade-date", default=None, help="Trade-date filter when using --from-trades.")
    parser.add_argument("--portfolio-rule", default=None, help="Portfolio-rule filter when using --from-trades.")
    parser.add_argument("--row-index", type=int, default=None, help="Row index from the filtered trades when using --from-trades.")
    parser.add_argument("--direction", default=None, choices=["buy", "sell", "BUY", "SELL"])
    parser.add_argument("--entry-price", type=float, default=None, help="Override entry reference price. Default uses IBKR ask for buy and bid for sell.")
    parser.add_argument("--strategy-id", default=None)
    parser.add_argument("--selected-alias", default=None)
    parser.add_argument("--max-hold-minutes", type=int, default=None)
    parser.add_argument("--contract-month", default="202606")
    parser.add_argument("--snapshot-attempts", type=int, default=3)
    parser.add_argument("--snapshot-retry-seconds", type=float, default=1.0)
    parser.add_argument("--write", action="store_true", help="Atomically write the signal CSV. Default only prints the row.")
    args = parser.parse_args()

    try:
        config, selected_trade = _resolve_signal_config(args)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "output": args.output,
                    "reason": str(exc) or exc.__class__.__name__,
                    "from_trades": args.from_trades,
                    "direction": args.direction.lower() if args.direction else None,
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
        return 2
    try:
        row = build_live_signal_row(config=config)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "output": args.output,
                    "reason": str(exc) or exc.__class__.__name__,
                    "from_trades": args.from_trades,
                    "direction": args.direction.lower() if args.direction else None,
                    "strategy_id": config.strategy_id,
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
        return 2
    result = {"status": "preview", "output": args.output, "row": row}
    if selected_trade is not None:
        result["selected_trade"] = selected_trade.to_dict()
    if args.write:
        write_live_signal(row, Path(args.output))
        result["status"] = "written"
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


def _resolve_signal_config(args: argparse.Namespace) -> tuple[LiveSignalConfig, object | None]:
    selected_trade = None
    if args.from_trades:
        trades = load_trade_samples(Path(args.from_trades))
        selected_trade = select_trade_sample(
            trades,
            trade_date=args.trade_date,
            portfolio_rule=args.portfolio_rule,
            selected_alias=args.selected_alias,
            row_index=args.row_index,
        )
        direction = 1 if int(float(selected_trade["direction"])) > 0 else -1
        strategy_id = args.strategy_id or str(selected_trade.get("portfolio_rule", "best_strategy"))
        selected_alias = str(selected_trade.get("selected_alias", "best_strategy"))
        max_hold_minutes = args.max_hold_minutes or int(float(selected_trade.get("holding_minutes", 4) or 4))
        signal_source = f"trades_live_cli:{Path(args.from_trades).name}"
    else:
        if args.direction is None:
            raise ValueError("--direction is required unless --from-trades is provided")
        direction = 1 if args.direction.lower() == "buy" else -1
        strategy_id = args.strategy_id or "manual_live_signal"
        selected_alias = args.selected_alias or "manual"
        max_hold_minutes = args.max_hold_minutes or 4
        signal_source = "manual_live_cli"

    return (
        LiveSignalConfig(
            output=Path(args.output),
            strategy_id=strategy_id,
            selected_alias=selected_alias,
            direction=direction,
            entry_price=args.entry_price,
            max_hold_minutes=max(1, int(max_hold_minutes)),
            signal_source=signal_source,
            contract=IBKRContractSpec(last_trade_date_or_contract_month=args.contract_month),
            snapshot_attempts=args.snapshot_attempts,
            snapshot_retry_seconds=args.snapshot_retry_seconds,
        ),
        selected_trade,
    )


if __name__ == "__main__":
    raise SystemExit(main())
