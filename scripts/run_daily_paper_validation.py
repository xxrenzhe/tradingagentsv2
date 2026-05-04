from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def _run(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(command, cwd=ROOT_DIR, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh walk-forward, paper summary, and validation HTML report.")
    parser.add_argument("--trades", default=".tmp/mbp-adaptive-portfolio-trades.csv")
    parser.add_argument("--train-days", type=int, default=15)
    parser.add_argument("--test-days", type=int, default=5)
    parser.add_argument("--step-days", type=int, default=5)
    parser.add_argument("--sizing-mode", choices=["scale", "block"], default="scale")
    parser.add_argument("--agent-audit", default=".tmp/agent-gate-audit.jsonl")
    parser.add_argument("--ibkr-audit", default=".tmp/ibkr-paper-audit.jsonl")
    parser.add_argument("--walk-forward-decisions", default=".tmp/mbp-agent-gate-walk-forward-decisions.csv")
    parser.add_argument("--walk-forward-summary", default=".tmp/mbp-agent-gate-walk-forward-summary.csv")
    parser.add_argument("--paper-summary", default=".tmp/paper-validation-summary.csv")
    parser.add_argument("--report-output", default="reports/NQM6-mbp-walk-forward-paper-validation.html")
    args = parser.parse_args()

    python = sys.executable
    commands = [
        [
            python,
            "scripts/walk_forward_agent_gate_on_mbp_trades.py",
            "--trades",
            args.trades,
            "--train-days",
            str(args.train_days),
            "--test-days",
            str(args.test_days),
            "--step-days",
            str(args.step_days),
            "--sizing-mode",
            args.sizing_mode,
            "--decisions-output",
            args.walk_forward_decisions,
            "--summary-output",
            args.walk_forward_summary,
        ],
        [
            python,
            "scripts/summarize_paper_validation.py",
            "--agent-audit",
            args.agent_audit,
            "--ibkr-audit",
            args.ibkr_audit,
            "--output",
            args.paper_summary,
        ],
        [
            python,
            "scripts/generate_walk_forward_paper_validation_report.py",
            "--walk-forward-summary",
            args.walk_forward_summary,
            "--walk-forward-decisions",
            args.walk_forward_decisions,
            "--paper-summary",
            args.paper_summary,
            "--output",
            args.report_output,
        ],
    ]
    results = []
    for command in commands:
        result = _run(command)
        results.append(result)
        if result["returncode"] != 0:
            print(json.dumps({"ok": False, "results": results}, indent=2, sort_keys=True))
            return int(result["returncode"])
    print(json.dumps({"ok": True, "results": results, "report_output": args.report_output}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
