from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.evolution import EvolutionConfig, run_evolution


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NQ 1-minute trading evolution research.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-evolution-continuous-cache.pkl")
    parser.add_argument("--memory-db", default=".tmp/nq-trading-evolution.sqlite")
    parser.add_argument("--report", default="reports/NQ-trading-evolution-report.html")
    parser.add_argument("--source-csv")
    parser.add_argument("--source-zip")
    parser.add_argument("--llm-mode", choices=["layered", "strict-every-segment"], default="layered")
    parser.add_argument("--strict-every-segment", action="store_true", help="Alias for --llm-mode strict-every-segment.")
    parser.add_argument("--mock-llm-fixture")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-segments", type=int)
    parser.add_argument("--base-bars", type=int, default=100)
    parser.add_argument("--min-bars", type=int, default=20)
    parser.add_argument("--max-bars", type=int, default=300)
    parser.add_argument("--split-threshold", type=float, default=0.75)
    parser.add_argument("--high-info-threshold", type=float, default=0.80)
    parser.add_argument("--daily-llm-call-limit", type=int, default=3)
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--backend-url")
    args = parser.parse_args()

    config = EvolutionConfig(
        start_date=args.start_date,
        end_date=args.end_date,
        cache=Path(args.cache),
        memory_db=Path(args.memory_db),
        report=Path(args.report),
        source_csv=Path(args.source_csv) if args.source_csv else None,
        source_zip=Path(args.source_zip) if args.source_zip else None,
        llm_mode="strict-every-segment" if args.strict_every_segment else args.llm_mode,
        mock_llm_fixture=Path(args.mock_llm_fixture) if args.mock_llm_fixture else None,
        no_llm=bool(args.no_llm),
        resume=bool(args.resume),
        max_segments=args.max_segments,
        base_bars=args.base_bars,
        min_bars=args.min_bars,
        max_bars=args.max_bars,
        split_threshold=args.split_threshold,
        high_info_threshold=args.high_info_threshold,
        daily_llm_call_limit=args.daily_llm_call_limit,
        provider=args.provider,
        model=args.model,
        backend_url=args.backend_url,
    )
    summary = run_evolution(config)
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
