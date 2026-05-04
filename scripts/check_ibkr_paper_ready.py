from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.execution import IBKRPaperTradingSession
from tradingagents.config.env import load_project_env


def main() -> int:
    load_project_env()
    result = IBKRPaperTradingSession.from_env().preflight()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["readiness"]["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
