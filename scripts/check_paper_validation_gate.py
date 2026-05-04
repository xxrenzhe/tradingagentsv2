from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.config.env import load_project_env
from tradingagents.execution import PaperValidationGateConfig, summarize_paper_audits


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Check whether paper validation has reached live-candidate thresholds.")
    parser.add_argument("--agent-audit", default=".tmp/agent-gate-audit.jsonl")
    parser.add_argument("--ibkr-audit", default=".tmp/ibkr-paper-audit.jsonl")
    parser.add_argument("--strategy-id", default=None, help="Only count paper events for this strategy_id.")
    parser.add_argument("--min-ibkr-ready", type=int, default=1)
    parser.add_argument("--min-ibkr-submitted", type=int, default=1)
    parser.add_argument("--min-paper-outcomes", type=int, default=20)
    parser.add_argument("--min-paper-net-points", type=float, default=0.0)
    parser.add_argument("--min-paper-win-rate", type=float, default=45.0)
    parser.add_argument("--max-consecutive-losses", type=int, default=4)
    parser.add_argument("--max-allowed-blocker-count", type=int, default=0)
    args = parser.parse_args()

    summary = summarize_paper_audits(
        agent_audit_path=args.agent_audit,
        ibkr_audit_path=args.ibkr_audit,
        strategy_id=args.strategy_id,
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
    gate = summary["validation_gate"]
    print(json.dumps({"validation_gate": gate, "summary": summary}, indent=2, sort_keys=True, default=str))
    return 0 if gate["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
