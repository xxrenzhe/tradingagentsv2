from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd


WINDOWS = {
    "asia": (0, 7 * 60),
    "europe": (7 * 60, 13 * 60 + 30),
    "us_rth": (13 * 60 + 30, 20 * 60),
    "us_late": (20 * 60, 24 * 60),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run short-pattern mining over fixed UTC session windows.")
    parser.add_argument("--symbol", default="NQM6")
    parser.add_argument("--start-date", default="2026-04-27")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--min-trades", type=int, default=3)
    parser.add_argument("--output", default=".tmp/short-patterns-session-summary.csv")
    args = parser.parse_args()

    rows = []
    for name, (start_minute, end_minute) in WINDOWS.items():
        window_output = Path(f".tmp/short-patterns-{args.symbol}-{args.start_date}-{name}.csv")
        command = [
            sys.executable,
            "scripts/mine_short_patterns.py",
            "--symbol",
            args.symbol,
            "--start-date",
            args.start_date,
            "--end-date",
            args.end_date,
            "--min-trades",
            str(args.min_trades),
            "--top",
            "5",
            "--no-mbp",
            "--start-minute",
            str(start_minute),
            "--end-minute",
            str(end_minute),
            "--output",
            str(window_output),
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
        result = pd.read_csv(window_output)
        if result.empty:
            continue
        best = result.iloc[0].to_dict()
        best["window"] = name
        best["start_minute"] = start_minute
        best["end_minute"] = end_minute
        rows.append(best)

    summary = pd.DataFrame(rows)
    if summary.empty:
        raise SystemExit("No session window produced enough trades.")
    summary = summary.sort_values(["score", "net_points"], ascending=[False, False]).reset_index(drop=True)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False)
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print(f"Report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
