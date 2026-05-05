from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.config.env import load_project_env
from tradingagents.execution.trade_outcome_inference import infer_outcomes, record_outcomes, write_csv


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Infer reviewable paper outcomes from dated trade logs.")
    parser.add_argument("--trade-log-dir", default="docs/Strategy/tradelogs")
    parser.add_argument("--strategy-id", default=None)
    parser.add_argument("--output", default=".tmp/inferred-paper-outcomes.csv")
    parser.add_argument("--record", action="store_true", help="Append high-confidence inferred outcomes to agent audit.")
    parser.add_argument("--audit-path", default=".tmp/agent-gate-audit.jsonl")
    parser.add_argument("--update-memory", action="store_true", help="Also resolve matching pending memory entries.")
    args = parser.parse_args()

    outcomes = infer_outcomes(Path(args.trade_log_dir), strategy_id=args.strategy_id)
    high_confidence = [outcome for outcome in outcomes if outcome.confidence == "target_or_stop_hit"]
    output = Path(args.output)
    write_csv(output, outcomes)
    recorded = record_outcomes(outcomes, audit_path=Path(args.audit_path), update_memory=args.update_memory) if args.record else 0
    print(
        json.dumps(
            {
                "outcomes": len(outcomes),
                "high_confidence": len(high_confidence),
                "needs_review": len(outcomes) - len(high_confidence),
                "recorded": recorded,
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
