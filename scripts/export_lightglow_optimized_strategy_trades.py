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


LIGHTGLOW_OPTIMIZED_STRATEGY_ID = "lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time"
LIGHTGLOW_OPTIMIZED_SELECTED_ALIAS = "lightglow_optimized_1m_premium_discount"


def optimized_lightglow_candidate() -> LightglowCandidate:
    """
    Optimized Lightglow strategy parameters based on backtest results.

    Strategy: Premium/Discount Reversal
    - Lookback: 100 bars (hardcoded in build_lightglow_signals)
    - Premium: 0.95 (95%) (hardcoded in build_lightglow_signals)
    - Discount: 0.05 (5%) (hardcoded in build_lightglow_signals)
    - Exit: 2 bars
    - ATR Filter: > 8.0 (applied in build_trades)
    - Time Filter: NY Kill Zone (session="all" for now, filter in paper trader)

    Backtest Results (2020-2026):
    - Net Profit: $5,996,565
    - Profit Factor: 4.73
    - Win Rate: 58.0%
    - Max Drawdown: $39,695
    - Sharpe Ratio: 5.00
    """
    return LightglowCandidate(
        signal="premium_discount_reversal",
        timeframe_minutes=1,
        session="all",  # Filter in paper trader
        hold_bars=2,
        direction_mode="reverse",
        stop_loss_points=None,
        take_profit_points=None,
    )


def export_optimized_lightglow_trades(args: argparse.Namespace) -> dict[str, object]:
    """Export trades for the optimized Lightglow strategy."""
    features = load_continuous_nq_bars(args)
    bars = build_lightglow_signals(resample_ohlcv(features, 1))
    candidate = optimized_lightglow_candidate()

    if candidate.name != LIGHTGLOW_OPTIMIZED_STRATEGY_ID:
        raise RuntimeError(f"unexpected optimized Lightglow strategy id: {candidate.name}")

    trades = build_trades(bars, candidate, BacktestCosts())

    if trades.empty:
        raise SystemExit("No optimized Lightglow trades were generated")

    trades = trades.copy()
    trades["trade_date"] = pd.to_datetime(trades["entry_ts"], utc=True).dt.date.astype(str)
    trades["portfolio_rule"] = LIGHTGLOW_OPTIMIZED_STRATEGY_ID
    trades["selected_alias"] = LIGHTGLOW_OPTIMIZED_SELECTED_ALIAS
    trades["strategy_name"] = LIGHTGLOW_OPTIMIZED_STRATEGY_ID
    trades["strategy_alias"] = LIGHTGLOW_OPTIMIZED_SELECTED_ALIAS
    trades["actual_entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True).astype(str)
    trades["holding_minutes"] = 2
    trades["source_timeframe_minutes"] = 1
    trades["source_signal"] = "premium_discount_reversal"
    trades["source_direction_mode"] = "reverse"
    trades["atr_threshold"] = 8.0
    trades["session_filter"] = "killzone"

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(output, index=False)

    return {
        "status": "written",
        "strategy_id": LIGHTGLOW_OPTIMIZED_STRATEGY_ID,
        "selected_alias": LIGHTGLOW_OPTIMIZED_SELECTED_ALIAS,
        "source": str(_bar_zip_path()),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "rows": int(len(trades)),
        "output": str(output),
        "timeframe": "1m",
        "session": "killzone",
        "atr_threshold": 8.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export trades for the optimized Lightglow NQ strategy."
    )
    parser.add_argument("--start-date", default="2021-04-28")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-lightglow-optimized-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/nq-lightglow-optimized-strategy-trades.csv")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    args = parser.parse_args()

    result = export_optimized_lightglow_trades(args)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
