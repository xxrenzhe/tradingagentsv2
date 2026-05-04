from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.config.env import load_project_env
from tradingagents.execution import paper_summary_frame, summarize_paper_audits


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Summarize agent-gate and IBKR paper validation audit logs.")
    parser.add_argument("--agent-audit", default=".tmp/agent-gate-audit.jsonl")
    parser.add_argument("--ibkr-audit", default=".tmp/ibkr-paper-audit.jsonl")
    parser.add_argument("--output", default=".tmp/paper-validation-summary.csv")
    parser.add_argument("--strategy-id", default=None, help="Only count paper events for this strategy_id.")
    args = parser.parse_args()

    summary = summarize_paper_audits(
        agent_audit_path=args.agent_audit,
        ibkr_audit_path=args.ibkr_audit,
        strategy_id=args.strategy_id,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    paper_summary_frame(summary).to_csv(output_path, index=False)
    print(json.dumps(summary | {"output": str(output_path)}, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
