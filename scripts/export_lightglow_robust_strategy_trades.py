from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from backtest_lightglow_nq_bars import (
    LightglowCandidate,
    build_lightglow_signals,
    build_trades,
    resample_ohlcv,
)
from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.dataflows.databento import _bar_zip_path


LIGHTGLOW_ROBUST_STRATEGY_ID = "lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time"
LIGHTGLOW_ROBUST_SELECTED_ALIAS = "lightglow_robust_3m_premium_discount_reverse"


def robust_lightglow_candidate() -> LightglowCandidate:
    return LightglowCandidate(
        signal="premium_discount_reversal",
        timeframe_minutes=3,
        session="all",
        hold_bars=1,
        direction_mode="reverse",
        stop_loss_points=None,
        take_profit_points=None,
    )


def export_robust_lightglow_trades(args: argparse.Namespace) -> dict[str, object]:
    features = load_continuous_nq_bars(args)
    bars = build_lightglow_signals(resample_ohlcv(features, 3))
    candidate = robust_lightglow_candidate()
    if candidate.name != LIGHTGLOW_ROBUST_STRATEGY_ID:
        raise RuntimeError(f"unexpected robust Lightglow strategy id: {candidate.name}")
    trades = build_trades(bars, candidate, BacktestCosts())
    if trades.empty:
        raise SystemExit("No robust Lightglow trades were generated")
    trades = trades.copy()
    trades["trade_date"] = pd.to_datetime(trades["entry_ts"], utc=True).dt.date.astype(str)
    trades["portfolio_rule"] = LIGHTGLOW_ROBUST_STRATEGY_ID
    trades["selected_alias"] = LIGHTGLOW_ROBUST_SELECTED_ALIAS
    trades["strategy_name"] = LIGHTGLOW_ROBUST_STRATEGY_ID
    trades["strategy_alias"] = LIGHTGLOW_ROBUST_SELECTED_ALIAS
    trades["actual_entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True).astype(str)
    trades["holding_minutes"] = 3
    trades["source_timeframe_minutes"] = 3
    trades["source_signal"] = "premium_discount_reversal"
    trades["source_direction_mode"] = "reverse"
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(output, index=False)
    return {
        "status": "written",
        "strategy_id": LIGHTGLOW_ROBUST_STRATEGY_ID,
        "selected_alias": LIGHTGLOW_ROBUST_SELECTED_ALIAS,
        "source": str(_bar_zip_path()),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "rows": int(len(trades)),
        "output": str(output),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export trades for the selected robust Lightglow NQ strategy.")
    parser.add_argument("--start-date", default="2021-04-28")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-lightglow-robust-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/nq-lightglow-robust-strategy-trades.csv")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    args = parser.parse_args()

    result = export_robust_lightglow_trades(args)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
