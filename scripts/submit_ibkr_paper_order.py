from __future__ import annotations

import argparse
import json
from pathlib import Path

from tradingagents.execution import IBKRPaperBroker, IBKRPaperTradingSession
from tradingagents.execution.ibkr import IBKROrderIntent
from tradingagents.config.env import load_project_env


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Submit or dry-run an IBKR paper-trading order intent.")
    parser.add_argument("--intent", required=True, help="Path to a JSON IBKROrderIntent payload.")
    parser.add_argument("--submit", action="store_true", help="Actually submit to IBKR paper. Default is dry-run.")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip IBKR readiness preflight before submit.")
    parser.add_argument("--audit-path", default=None, help="Override audit JSONL output path.")
    args = parser.parse_args()

    payload = json.loads(Path(args.intent).read_text(encoding="utf-8"))
    intent = IBKROrderIntent(**payload)
    broker = IBKRPaperBroker(audit_path=args.audit_path)
    if args.submit:
        response = IBKRPaperTradingSession.from_env(broker).submit_intent(
            intent,
            dry_run=False,
            skip_preflight=args.skip_preflight,
        )
    else:
        response = broker.submit(intent, dry_run=True)
    print(json.dumps(response, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
