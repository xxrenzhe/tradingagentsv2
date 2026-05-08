#!/usr/bin/env python3
"""
Dynamic Exit Backtest - Modified from original

Adds MSS-based dynamic exit to the original backtest framework.
This ensures data consistency by using the same data source and processing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import from original script
from scripts.backtest_lightglow_nq_bars import (
    LightglowCandidate,
    build_lightglow_signals,
    resample_ohlcv,
    select_non_overlapping_signal_indexes,
)
from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts


def build_dynamic_exit_trades(
    frame: pd.DataFrame,
    signal: pd.Series,
    candidate: LightglowCandidate,
    costs: BacktestCosts,
    max_hold_bars: int = 20,
    mss_lookback: int = 5,
) -> pd.DataFrame:
    """
    Build trades with dynamic MSS-based exit logic

    Args:
        frame: OHLCV DataFrame
        signal: Signal series (1=long, -1=short, 0=none)
        candidate: Strategy candidate
        costs: Trading costs
        max_hold_bars: Maximum holding period
        mss_lookback: Lookback period for swing high/low

    Returns:
        DataFrame of trades
    """

    # Get entry signals
    entry_indexes = np.flatnonzero(signal.to_numpy() != 0)
    default_hold_bars = max(1, candidate.hold_bars)

    # Use minimum holding period for pre-selection to avoid obvious overlaps
    # This ensures at least default_hold_bars spacing between entries
    selected_signal_indexes = select_non_overlapping_signal_indexes(
        entry_indexes, len(frame), default_hold_bars
    )

    if len(selected_signal_indexes) == 0:
        return pd.DataFrame()

    # Extract price arrays
    open_prices = frame["Open"].to_numpy(dtype=float)
    high_prices = frame["High"].to_numpy(dtype=float)
    low_prices = frame["Low"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    timestamps = frame["ts"].to_numpy()
    symbols = frame["symbol"].astype(str).to_numpy()

    rows = []
    next_available_index = 0

    for signal_index in selected_signal_indexes:
        entry_index = int(signal_index) + 1

        # Check if entry is valid
        if entry_index < next_available_index or entry_index >= len(frame):
            continue

        direction = int(signal.iat[signal_index])
        entry_price = float(open_prices[entry_index])
        entry_symbol = symbols[signal_index]

        # Dynamic exit logic
        mss_confirmed = False
        exit_index = None
        exit_reason = "unknown"

        for i in range(entry_index, min(entry_index + max_hold_bars, len(frame))):
            # Check symbol continuity
            if symbols[i] != entry_symbol:
                exit_index = i - 1 if i > entry_index else entry_index
                exit_reason = "symbol_change"
                break

            bars_held = i - entry_index
            current_price = close_prices[i]

            # Calculate swing high/low
            if i >= mss_lookback:
                lookback_start = max(0, i - mss_lookback)
                swing_high = high_prices[lookback_start:i].max()
                swing_low = low_prices[lookback_start:i].min()
            else:
                swing_high = None
                swing_low = None

            # Check exit conditions
            should_exit = False

            if not mss_confirmed and bars_held >= default_hold_bars:
                # Check for MSS confirmation
                if swing_high is not None and swing_low is not None:
                    if direction > 0 and current_price > swing_high:
                        mss_confirmed = True
                    elif direction < 0 and current_price < swing_low:
                        mss_confirmed = True
                    else:
                        # No MSS, exit with default holding
                        should_exit = True
                        exit_reason = "no_mss"
                else:
                    # Not enough data for MSS check
                    should_exit = True
                    exit_reason = "no_mss"

            if mss_confirmed and not should_exit:
                # Check for reverse MSS
                if swing_high is not None and swing_low is not None:
                    if direction > 0 and current_price < swing_low:
                        should_exit = True
                        exit_reason = "reverse_mss"
                    elif direction < 0 and current_price > swing_high:
                        should_exit = True
                        exit_reason = "reverse_mss"

                # Max holding time
                if bars_held >= max_hold_bars - 1:
                    should_exit = True
                    exit_reason = "max_holding"

            if should_exit:
                exit_index = i
                break

        # If no exit was found, use max holding
        if exit_index is None:
            exit_index = min(entry_index + max_hold_bars - 1, len(frame) - 1)
            if exit_reason == "unknown":
                exit_reason = "max_holding"

        # Calculate PnL
        exit_price = float(close_prices[exit_index])
        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points

        rows.append({
            "candidate": candidate.name + "_dynamic",
            "signal": candidate.signal,
            "timeframe_minutes": candidate.timeframe_minutes,
            "session": candidate.session,
            "holding_minutes": (exit_index - entry_index) * candidate.timeframe_minutes,
            "direction_mode": candidate.direction_mode,
            "exit_profile": "dynamic_mss",
            "entry_ts": timestamps[signal_index],
            "exit_ts": timestamps[exit_index],
            "symbol": entry_symbol,
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "gross_points": float(gross_points),
            "net_points": float(net_points),
            "net_dollars": float(net_points * costs.point_value),
            "entry_index": int(signal_index),
            "exit_index": int(exit_index),
            "mss_confirmed": mss_confirmed,
            "bars_held": exit_index - entry_index,
        })

        next_available_index = exit_index + 1

    return pd.DataFrame(rows)


def main():
    import argparse

    print("=" * 80)
    print("Dynamic Exit Backtest - Using Original Framework")
    print("=" * 80)
    print()

    # Create args object for load_continuous_nq_bars
    args = argparse.Namespace(
        start_date="2021-04-28",
        end_date="2026-04-28",
        min_volume=0,
        cache=".cache/nq_bars.pkl",
        chunk_size=100000,
    )

    # Load data using original method
    print("Loading NQ bars...")
    bars = load_continuous_nq_bars(args)
    print(f"Loaded {len(bars):,} bars")
    print()

    # Resample to 1-minute (already 1-minute, but ensures consistency)
    bars = resample_ohlcv(bars, 1)
    print(f"Resampled to {len(bars):,} bars")
    print()

    # Build signals using original method
    print("Building Lightglow signals...")
    bars = build_lightglow_signals(bars)
    print("Signals built")
    print()

    # Create candidate
    candidate = LightglowCandidate(
        signal="premium_discount_reversal",
        timeframe_minutes=1,
        session="all",
        hold_bars=2,
        direction_mode="reverse",
        stop_loss_points=None,
        take_profit_points=None,
    )

    # Get signal column
    base_signal = pd.to_numeric(bars[candidate.signal], errors="coerce").fillna(0).astype(int)

    # Apply direction mode
    if candidate.direction_mode == "reverse":
        signal = -base_signal
    elif candidate.direction_mode == "native":
        signal = base_signal
    else:
        raise ValueError(f"Unknown direction mode: {candidate.direction_mode}")

    signal_count = (signal != 0).sum()
    print(f"Found {signal_count:,} signals")
    print()

    # Build trades with dynamic exit
    print("Building trades with dynamic exit...")
    costs = BacktestCosts(commission_per_contract=5.0, slippage_ticks_per_side=1.0)
    trades = build_dynamic_exit_trades(
        frame=bars,
        signal=signal,
        candidate=candidate,
        costs=costs,
        max_hold_bars=20,
        mss_lookback=5,
    )

    print(f"Generated {len(trades):,} trades")
    print()

    # Calculate statistics
    if len(trades) > 0:
        pnls = trades['net_dollars'].values
        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]

        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        max_dd = drawdowns.max() if len(drawdowns) > 0 else 0.0

        mss_trades = trades[trades['mss_confirmed'] == True]
        no_mss_trades = trades[trades['mss_confirmed'] == False]

        print("=" * 80)
        print("RESULTS")
        print("=" * 80)
        print()
        print(f"Total Trades: {len(trades):,}")
        print(f"Net Profit: ${pnls.sum():,.2f}")
        print(f"Profit Factor: {wins.sum() / abs(losses.sum()):.2f}" if len(losses) > 0 else "Profit Factor: inf")
        print(f"Win Rate: {len(wins) / len(trades):.1%}")
        print(f"Avg Win: ${wins.mean():,.2f}" if len(wins) > 0 else "Avg Win: $0.00")
        print(f"Avg Loss: ${losses.mean():,.2f}" if len(losses) > 0 else "Avg Loss: $0.00")
        print(f"Max Drawdown: ${max_dd:,.2f}")
        print(f"Avg Bars Held: {trades['bars_held'].mean():.1f}")
        print()
        print("MSS Statistics:")
        print(f"  MSS Confirmed Rate: {len(mss_trades) / len(trades):.1%}")
        print(f"  MSS Trades: {len(mss_trades):,} (${mss_trades['net_dollars'].sum():,.2f})")
        print(f"  No MSS Trades: {len(no_mss_trades):,} (${no_mss_trades['net_dollars'].sum():,.2f})")
        print(f"  Avg Bars (MSS): {mss_trades['bars_held'].mean():.1f}" if len(mss_trades) > 0 else "  Avg Bars (MSS): N/A")
        print(f"  Avg Bars (No MSS): {no_mss_trades['bars_held'].mean():.1f}" if len(no_mss_trades) > 0 else "  Avg Bars (No MSS): N/A")
        print()

        # Save trades
        output_path = Path("reports/dynamic_exit_trades_corrected.csv")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        trades.to_csv(output_path, index=False)
        print(f"Trades saved to: {output_path}")
    else:
        print("No trades generated!")


if __name__ == '__main__':
    main()
