from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd

from tradingagents.config.env import load_project_env
from tradingagents.execution.agent_gate import AgentGateConfig
from tradingagents.execution.gate_backtest import GateReplayConfig, replay_gate_on_trades


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Backtest the multi-agent gate on historical MBP trade samples.")
    parser.add_argument("--trades", default=".tmp/mbp-adaptive-portfolio-trades.csv")
    parser.add_argument("--mode", choices=["offline", "agent"], default="offline")
    parser.add_argument("--sizing-mode", choices=["scale", "block"], default="scale")
    parser.add_argument("--contract-month", default="202606")
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--stop-loss-points", type=float, default=16.0)
    parser.add_argument("--take-profit-points", type=float, default=24.0)
    parser.add_argument("--audit-path", default=".tmp/agent-gate-backtest-audit.jsonl")
    parser.add_argument("--decisions-output", default=".tmp/mbp-agent-gate-backtest-decisions.csv")
    parser.add_argument("--summary-output", default=".tmp/mbp-agent-gate-backtest-summary.csv")
    parser.add_argument("--max-trades", type=int, default=None)
    args = parser.parse_args()

    trades = pd.read_csv(args.trades)
    replay_config = GateReplayConfig(
        mode=args.mode,
        sizing_mode=args.sizing_mode,
        contract_month=args.contract_month,
        quantity=args.quantity,
        stop_loss_points=args.stop_loss_points,
        take_profit_points=args.take_profit_points,
        audit_path=Path(args.audit_path),
        decision_output=Path(args.decisions_output),
        summary_output=Path(args.summary_output),
        max_trades=args.max_trades,
    )
    gate_config = AgentGateConfig.from_env()
    decisions, summary = replay_gate_on_trades(trades, replay_config=replay_config, gate_config=gate_config)
    replay_config.decision_output.parent.mkdir(parents=True, exist_ok=True)
    replay_config.summary_output.parent.mkdir(parents=True, exist_ok=True)
    decisions.to_csv(replay_config.decision_output, index=False)
    summary.to_csv(replay_config.summary_output, index=False)
    output = {
        "mode": args.mode,
        "sizing_mode": args.sizing_mode,
        "trades": int(len(trades) if args.max_trades is None else min(len(trades), args.max_trades)),
        "allowed": int(decisions["allowed"].sum()) if not decisions.empty else 0,
        "blocked": int((~decisions["allowed"]).sum()) if not decisions.empty else 0,
        "decisions_output": str(replay_config.decision_output),
        "summary_output": str(replay_config.summary_output),
        "summary": summary.to_dict(orient="records"),
    }
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
