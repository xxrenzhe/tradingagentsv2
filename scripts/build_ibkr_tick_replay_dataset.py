from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.config.env import load_project_env
from tradingagents.execution import TickReplayDatasetConfig, build_tick_replay_dataset


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Normalize IBKR paper tick JSONL files into a replay dataset.")
    parser.add_argument("--input-dir", default=".tmp/ibkr-paper-ticks")
    parser.add_argument("--output", default=".tmp/ibkr-paper-tick-replay.csv")
    parser.add_argument("--summary-output", default=".tmp/ibkr-paper-tick-replay-summary.csv")
    args = parser.parse_args()

    dataset, summary = build_tick_replay_dataset(
        TickReplayDatasetConfig(
            input_dir=Path(args.input_dir),
            output=Path(args.output),
            summary_output=Path(args.summary_output),
        )
    )
    result = {
        "ticks": int(len(dataset)),
        "output": args.output,
        "summary_output": args.summary_output,
        "summary": summary.to_dict(orient="records"),
    }
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
