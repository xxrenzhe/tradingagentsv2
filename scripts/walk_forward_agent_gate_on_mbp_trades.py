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
from tradingagents.execution import AgentGateConfig, WalkForwardConfig, walk_forward_gate_replay


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Run walk-forward validation for the agent gate on MBP trades.")
    parser.add_argument("--trades", default=".tmp/mbp-adaptive-portfolio-trades.csv")
    parser.add_argument("--train-days", type=int, default=15)
    parser.add_argument("--test-days", type=int, default=5)
    parser.add_argument("--step-days", type=int, default=5)
    parser.add_argument("--sizing-mode", choices=["scale", "block"], default="scale")
    parser.add_argument("--contract-month", default="202606")
    parser.add_argument("--audit-dir", default=".tmp/walk-forward-agent-gate")
    parser.add_argument("--decisions-output", default=".tmp/mbp-agent-gate-walk-forward-decisions.csv")
    parser.add_argument("--summary-output", default=".tmp/mbp-agent-gate-walk-forward-summary.csv")
    args = parser.parse_args()

    trades = pd.read_csv(args.trades)
    decisions, summary = walk_forward_gate_replay(
        trades,
        config=WalkForwardConfig(
            train_days=args.train_days,
            test_days=args.test_days,
            step_days=args.step_days,
            sizing_mode=args.sizing_mode,
            contract_month=args.contract_month,
            audit_dir=Path(args.audit_dir),
        ),
        gate_config=AgentGateConfig.from_env(),
    )
    decisions_path = Path(args.decisions_output)
    summary_path = Path(args.summary_output)
    decisions_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    decisions.to_csv(decisions_path, index=False)
    summary.to_csv(summary_path, index=False)
    output = {
        "folds": int(len(summary)),
        "decisions": int(len(decisions)),
        "decisions_output": str(decisions_path),
        "summary_output": str(summary_path),
        "raw_net_points": float(summary["raw_net_points"].sum()) if not summary.empty else 0.0,
        "gate_net_points": float(summary["gate_net_points"].sum()) if not summary.empty else 0.0,
        "raw_max_fold_drawdown": float(summary["raw_max_drawdown_points"].max()) if not summary.empty else 0.0,
        "gate_max_fold_drawdown": float(summary["gate_max_drawdown_points"].max()) if not summary.empty else 0.0,
    }
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
