"""
Lightglow Minimal Trend Filter Strategy

This script implements a MINIMAL modification to the original Lightglow strategy:
- Use original Premium/Discount signals (already validated)
- Add EMA trend filter to avoid counter-trend trades
- Keep original exit logic (2 bars)

Changes from original:
1. Add EMA 20/50 trend detection
2. Filter signals based on trend:
   - Ranging: Allow all signals (original behavior)
   - Uptrend: Only allow LONG signals
   - Downtrend: Only allow SHORT signals

Expected improvement:
- Reduce counter-trend losses
- Maintain reversal profits in ranging markets
- Should not perform worse than original
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.backtest_lightglow_nq_bars import (
    build_lightglow_signals,
    resample_ohlcv,
    BacktestCosts,
)
from search_nq_bar_2r_walkforward import load_continuous_nq_bars


BULLISH = 1
BEARISH = -1
NEUTRAL = 0


def calculate_ema(values: np.ndarray, period: int) -> np.ndarray:
    """Calculate Exponential Moving Average."""
    ema = np.full(len(values), np.nan)
    alpha = 2.0 / (period + 1)

    # Find first valid value
    first_valid = 0
    for i in range(len(values)):
        if np.isfinite(values[i]):
            ema[i] = values[i]
            first_valid = i
            break

    # Calculate EMA
    for i in range(first_valid + 1, len(values)):
        if np.isfinite(values[i]):
            if np.isfinite(ema[i - 1]):
                ema[i] = alpha * values[i] + (1 - alpha) * ema[i - 1]
            else:
                ema[i] = values[i]

    return ema


def add_trend_filter(bars: pd.DataFrame, ema_fast: int = 20, ema_slow: int = 50) -> pd.DataFrame:
    """
    Add trend filter using EMA crossover.

    Returns:
        DataFrame with added columns:
        - ema_fast: Fast EMA
        - ema_slow: Slow EMA
        - trend: 1 (uptrend), -1 (downtrend), 0 (ranging)
    """
    df = bars.copy()

    close = df["Close"].to_numpy(dtype=float)

    # Calculate EMAs
    ema_fast_values = calculate_ema(close, ema_fast)
    ema_slow_values = calculate_ema(close, ema_slow)

    # Determine trend (simple: fast > slow = uptrend)
    trend = np.zeros(len(df), dtype=np.int8)
    for i in range(len(df)):
        if not np.isfinite(ema_fast_values[i]) or not np.isfinite(ema_slow_values[i]):
            trend[i] = NEUTRAL
        elif ema_fast_values[i] > ema_slow_values[i]:
            trend[i] = BULLISH
        elif ema_fast_values[i] < ema_slow_values[i]:
            trend[i] = BEARISH
        else:
            trend[i] = NEUTRAL

    df["ema_fast"] = ema_fast_values
    df["ema_slow"] = ema_slow_values
    df["trend"] = trend

    return df


def apply_trend_filter_to_signals(bars: pd.DataFrame, signal_column: str = "premium_discount_reversal") -> pd.DataFrame:
    """
    Apply trend filter to existing signals.

    Filter rules:
    - Ranging market (trend=0): Allow all signals
    - Uptrend (trend=1): Only allow LONG signals (filter out SHORT)
    - Downtrend (trend=-1): Only allow SHORT signals (filter out LONG)
    """
    df = bars.copy()

    # Create filtered signal column
    filtered_signal = df[signal_column].copy()

    for i in range(len(df)):
        original_signal = df.loc[i, signal_column]
        trend = df.loc[i, "trend"]

        # No signal, keep as is
        if original_signal == 0:
            continue

        # Ranging market, allow all signals
        if trend == NEUTRAL:
            continue

        # Uptrend: only allow LONG signals
        if trend == BULLISH and original_signal == BEARISH:
            filtered_signal.iloc[i] = 0  # Filter out SHORT signal

        # Downtrend: only allow SHORT signals
        if trend == BEARISH and original_signal == BULLISH:
            filtered_signal.iloc[i] = 0  # Filter out LONG signal

    df[f"{signal_column}_filtered"] = filtered_signal

    return df


def backtest_with_trend_filter(
    bars: pd.DataFrame,
    signal_column: str = "premium_discount_reversal",
    hold_bars: int = 2,
    costs: BacktestCosts = BacktestCosts(),
) -> dict:
    """
    Backtest strategy with trend filter.

    Returns:
        Dictionary with results for both original and filtered strategies
    """
    # Build original signals
    print("Building Lightglow signals...")
    bars_with_signals = build_lightglow_signals(bars)

    # Add trend filter
    print("Adding trend filter...")
    bars_with_trend = add_trend_filter(bars_with_signals)

    # Apply filter to signals
    print("Applying trend filter to signals...")
    bars_filtered = apply_trend_filter_to_signals(bars_with_trend, signal_column)

    # Backtest both versions
    print("Backtesting original strategy...")
    original_results = run_backtest(bars_filtered, signal_column, hold_bars, costs)

    print("Backtesting filtered strategy...")
    filtered_results = run_backtest(bars_filtered, f"{signal_column}_filtered", hold_bars, costs)

    return {
        "original": original_results,
        "filtered": filtered_results,
        "improvement": {
            "net_profit_change": filtered_results["net_profit"] - original_results["net_profit"],
            "profit_factor_change": filtered_results["profit_factor"] - original_results["profit_factor"],
            "win_rate_change": filtered_results["win_rate"] - original_results["win_rate"],
        }
    }


def run_backtest(bars: pd.DataFrame, signal_column: str, hold_bars: int, costs: BacktestCosts) -> dict:
    """Run backtest on given signals."""
    trades = []
    position = 0
    entry_price = 0.0
    entry_index = 0

    for i in range(len(bars)):
        current_price = bars.loc[i, "Close"]

        # Check exit
        if position != 0:
            bars_in_trade = i - entry_index
            if bars_in_trade >= hold_bars:
                exit_price = current_price
                pnl_points = (exit_price - entry_price) * position
                pnl_dollars = pnl_points * 2.0  # MNQ multiplier

                # Apply costs
                total_commission = costs.commission_per_contract * 2
                total_slippage = costs.slippage_points * 2.0
                net_pnl = pnl_dollars - total_commission - total_slippage

                trades.append({
                    "entry_index": entry_index,
                    "entry_time": bars.loc[entry_index, "ts"],
                    "entry_price": entry_price,
                    "exit_index": i,
                    "exit_time": bars.loc[i, "ts"],
                    "exit_price": exit_price,
                    "direction": "long" if position == BULLISH else "short",
                    "bars_held": bars_in_trade,
                    "pnl_points": pnl_points,
                    "pnl_dollars": pnl_dollars,
                    "net_pnl": net_pnl,
                })

                position = 0
                entry_price = 0.0
                entry_index = 0

        # Check entry
        if position == 0 and bars.loc[i, signal_column] != 0:
            position = bars.loc[i, signal_column]
            entry_price = current_price
            entry_index = i

    # Calculate statistics
    if not trades:
        return {
            "total_trades": 0,
            "net_profit": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "max_drawdown": 0.0,
        }

    trades_df = pd.DataFrame(trades)

    total_trades = len(trades_df)
    winning_trades = trades_df[trades_df["net_pnl"] > 0]
    losing_trades = trades_df[trades_df["net_pnl"] < 0]

    win_count = len(winning_trades)
    loss_count = len(losing_trades)
    win_rate = win_count / total_trades if total_trades > 0 else 0.0

    gross_profit = winning_trades["net_pnl"].sum() if len(winning_trades) > 0 else 0.0
    gross_loss = abs(losing_trades["net_pnl"].sum()) if len(losing_trades) > 0 else 0.0
    net_profit = gross_profit - gross_loss
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

    avg_win = winning_trades["net_pnl"].mean() if len(winning_trades) > 0 else 0.0
    avg_loss = losing_trades["net_pnl"].mean() if len(losing_trades) > 0 else 0.0

    # Drawdown
    cumulative_pnl = trades_df["net_pnl"].cumsum()
    running_max = cumulative_pnl.cummax()
    drawdown = running_max - cumulative_pnl
    max_drawdown = drawdown.max()

    return {
        "total_trades": total_trades,
        "net_profit": net_profit,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "win_rate": win_rate,
        "win_count": win_count,
        "loss_count": loss_count,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "max_drawdown": max_drawdown,
    }


def main():
    parser = argparse.ArgumentParser(description="Backtest Lightglow with Minimal Trend Filter")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-05-08")
    parser.add_argument("--cache", default=".tmp/nq-minimal-trend-filter-cache.pkl")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--timeframe", type=int, default=1)
    parser.add_argument("--hold-bars", type=int, default=2)
    parser.add_argument("--ema-fast", type=int, default=20)
    parser.add_argument("--ema-slow", type=int, default=50)
    parser.add_argument("--output", default="reports/lightglow_minimal_trend_filter.json")
    args = parser.parse_args()

    print("=" * 80)
    print("Lightglow Minimal Trend Filter Backtest")
    print("=" * 80)
    print()
    print("Strategy: Original Premium/Discount + EMA Trend Filter")
    print(f"EMA Fast/Slow: {args.ema_fast}/{args.ema_slow}")
    print(f"Hold Bars: {args.hold_bars}")
    print()

    # Load data
    print(f"Loading NQ bars from {args.start_date} to {args.end_date}...")
    bars = load_continuous_nq_bars(args)

    if args.timeframe > 1:
        print(f"Resampling to {args.timeframe}-minute bars...")
        bars = resample_ohlcv(bars, args.timeframe)

    print(f"Loaded {len(bars):,} bars")
    print()

    # Run backtest
    costs = BacktestCosts(commission_per_contract=5.0, slippage_points=2.0)
    results = backtest_with_trend_filter(bars, hold_bars=args.hold_bars, costs=costs)

    # Print results
    print()
    print("=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)
    print()

    print("ORIGINAL STRATEGY (No Filter):")
    print("-" * 40)
    orig = results["original"]
    print(f"Total Trades: {orig['total_trades']:,}")
    print(f"Net Profit: ${orig['net_profit']:,.2f}")
    print(f"Profit Factor: {orig['profit_factor']:.2f}")
    print(f"Win Rate: {orig['win_rate']:.1%}")
    print(f"Wins/Losses: {orig['win_count']}/{orig['loss_count']}")
    print(f"Avg Win: ${orig['avg_win']:,.2f}")
    print(f"Avg Loss: ${orig['avg_loss']:,.2f}")
    print(f"Max Drawdown: ${orig['max_drawdown']:,.2f}")
    print()

    print("FILTERED STRATEGY (With Trend Filter):")
    print("-" * 40)
    filt = results["filtered"]
    print(f"Total Trades: {filt['total_trades']:,}")
    print(f"Net Profit: ${filt['net_profit']:,.2f}")
    print(f"Profit Factor: {filt['profit_factor']:.2f}")
    print(f"Win Rate: {filt['win_rate']:.1%}")
    print(f"Wins/Losses: {filt['win_count']}/{filt['loss_count']}")
    print(f"Avg Win: ${filt['avg_win']:,.2f}")
    print(f"Avg Loss: ${filt['avg_loss']:,.2f}")
    print(f"Max Drawdown: ${filt['max_drawdown']:,.2f}")
    print()

    print("IMPROVEMENT:")
    print("-" * 40)
    imp = results["improvement"]
    print(f"Net Profit Change: ${imp['net_profit_change']:,.2f}")
    print(f"Profit Factor Change: {imp['profit_factor_change']:+.2f}")
    print(f"Win Rate Change: {imp['win_rate_change']:+.1%}")
    print()

    # Determine if improvement
    if imp['net_profit_change'] > 0:
        print("✅ POSITIVE EFFECT: Trend filter improves performance!")
    elif imp['net_profit_change'] == 0:
        print("⚪ NEUTRAL EFFECT: Trend filter has no impact")
    else:
        print("❌ NEGATIVE EFFECT: Trend filter hurts performance")
    print()

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"Results saved to: {output_path}")
    print()


if __name__ == "__main__":
    main()
