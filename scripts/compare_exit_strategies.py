#!/usr/bin/env python3
"""
Dynamic Exit Backtest - Simplified Version

Compares original strategy (2-bar exit) vs dynamic exit (MSS-based).
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


LONG = 1
SHORT = -1


def backtest_with_exit_logic(
    bars: pd.DataFrame,
    signal_column: str,
    exit_logic: str = 'fixed',  # 'fixed' or 'dynamic'
    default_hold_bars: int = 2,
    max_trend_hold_bars: int = 20,
    point_value: float = 20.0,
    commission: float = 5.0,
    slippage_points: float = 0.25,
) -> tuple[list[dict], dict]:
    """
    Backtest with configurable exit logic

    Args:
        bars: DataFrame with OHLCV and signal column
        signal_column: Column with entry signals (1=long, -1=short, 0=none)
        exit_logic: 'fixed' for 2-bar exit, 'dynamic' for MSS-based
        default_hold_bars: Default holding period
        max_trend_hold_bars: Max holding for dynamic exit
        point_value: Dollar value per point
        commission: Commission per contract per side
        slippage_points: Slippage in points per side

    Returns:
        trades: List of trade dictionaries
        stats: Performance statistics
    """

    trades = []
    position = 0
    entry_idx = 0
    entry_price = 0.0
    mss_confirmed = False
    swing_high = None
    swing_low = None

    lookback = 5  # For swing high/low calculation

    for i in range(len(bars)):
        current_bar = bars.iloc[i]
        current_price = current_bar['Close']

        # Update swing high/low for dynamic exit
        if exit_logic == 'dynamic' and i >= lookback:
            start_idx = max(0, i - lookback)
            window = bars.iloc[start_idx:i]
            swing_high = window['High'].max()
            swing_low = window['Low'].min()

        # Check exit
        if position != 0:
            bars_held = i - entry_idx
            should_exit = False
            exit_reason = ""

            if exit_logic == 'fixed':
                # Fixed 2-bar exit
                if bars_held >= default_hold_bars:
                    should_exit = True
                    exit_reason = "fixed_time"

            elif exit_logic == 'dynamic':
                # Dynamic MSS-based exit
                if not mss_confirmed and bars_held >= default_hold_bars:
                    # Check for MSS
                    if swing_high and swing_low:
                        if position == LONG and current_price > swing_high:
                            mss_confirmed = True
                        elif position == SHORT and current_price < swing_low:
                            mss_confirmed = True
                        else:
                            should_exit = True
                            exit_reason = "no_mss"

                if mss_confirmed:
                    # Check for reverse MSS
                    if swing_high and swing_low:
                        if position == LONG and current_price < swing_low:
                            should_exit = True
                            exit_reason = "reverse_mss"
                        elif position == SHORT and current_price > swing_high:
                            should_exit = True
                            exit_reason = "reverse_mss"

                    # Max holding time
                    if bars_held >= max_trend_hold_bars:
                        should_exit = True
                        exit_reason = "max_holding"

            # Execute exit
            if should_exit:
                exit_price = current_price
                pnl_points = (exit_price - entry_price) * position

                # Apply costs
                total_cost_points = slippage_points * 2 + (commission * 2) / point_value
                net_pnl_points = pnl_points - total_cost_points
                net_pnl_dollars = net_pnl_points * point_value

                trades.append({
                    'entry_time': bars.iloc[entry_idx]['ts'],
                    'entry_price': entry_price,
                    'exit_time': current_bar['ts'],
                    'exit_price': exit_price,
                    'direction': 'LONG' if position == LONG else 'SHORT',
                    'bars_held': bars_held,
                    'pnl_points': net_pnl_points,
                    'pnl_dollars': net_pnl_dollars,
                    'exit_reason': exit_reason,
                    'mss_confirmed': mss_confirmed,
                })

                position = 0
                mss_confirmed = False

        # Check entry
        if position == 0:
            signal = current_bar[signal_column]
            if pd.notna(signal) and signal != 0:
                position = int(signal)
                entry_idx = i
                entry_price = current_price
                mss_confirmed = False

    # Calculate stats
    stats = calculate_stats(trades)

    return trades, stats


def calculate_stats(trades: list[dict]) -> dict:
    """Calculate performance statistics"""
    if not trades:
        return {
            'total_trades': 0,
            'net_profit': 0.0,
            'profit_factor': 0.0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'max_drawdown': 0.0,
            'avg_bars_held': 0.0,
        }

    pnls = [t['pnl_dollars'] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    # Drawdown
    cumulative = np.cumsum(pnls)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = running_max - cumulative
    max_dd = np.max(drawdowns) if len(drawdowns) > 0 else 0.0

    # MSS stats
    mss_trades = [t for t in trades if t.get('mss_confirmed', False)]
    no_mss_trades = [t for t in trades if not t.get('mss_confirmed', False)]

    return {
        'total_trades': len(trades),
        'net_profit': sum(pnls),
        'profit_factor': sum(wins) / abs(sum(losses)) if losses else float('inf'),
        'win_rate': len(wins) / len(trades),
        'avg_win': np.mean(wins) if wins else 0.0,
        'avg_loss': np.mean(losses) if losses else 0.0,
        'max_drawdown': max_dd,
        'avg_bars_held': np.mean([t['bars_held'] for t in trades]),
        'mss_confirmed_rate': len(mss_trades) / len(trades) if trades else 0.0,
        'mss_trades': len(mss_trades),
        'no_mss_trades': len(no_mss_trades),
        'mss_profit': sum([t['pnl_dollars'] for t in mss_trades]),
        'no_mss_profit': sum([t['pnl_dollars'] for t in no_mss_trades]),
        'avg_bars_mss': np.mean([t['bars_held'] for t in mss_trades]) if mss_trades else 0.0,
        'avg_bars_no_mss': np.mean([t['bars_held'] for t in no_mss_trades]) if no_mss_trades else 0.0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='Input CSV with signals')
    parser.add_argument('--signal-column', default='premium_discount_reversal_reverse', help='Signal column name')
    parser.add_argument('--output', default='reports/dynamic_exit_comparison.json', help='Output file')

    args = parser.parse_args()

    print("=" * 80)
    print("Dynamic Exit Comparison")
    print("=" * 80)
    print()

    # Load data
    print(f"Loading data from {args.input}...")
    bars = pd.read_csv(args.input)
    bars['ts'] = pd.to_datetime(bars['ts'])
    print(f"Loaded {len(bars):,} bars")
    print()

    # Check signal column
    if args.signal_column not in bars.columns:
        print(f"ERROR: Signal column '{args.signal_column}' not found!")
        print("Available columns:", bars.columns.tolist())
        return

    signal_count = (bars[args.signal_column] != 0).sum()
    print(f"Found {signal_count:,} signals in column '{args.signal_column}'")
    print()

    # Run both backtests
    print("Running FIXED exit backtest (original strategy)...")
    trades_fixed, stats_fixed = backtest_with_exit_logic(
        bars=bars,
        signal_column=args.signal_column,
        exit_logic='fixed',
        default_hold_bars=2,
    )

    print("Running DYNAMIC exit backtest (MSS-based)...")
    trades_dynamic, stats_dynamic = backtest_with_exit_logic(
        bars=bars,
        signal_column=args.signal_column,
        exit_logic='dynamic',
        default_hold_bars=2,
        max_trend_hold_bars=20,
    )

    # Print comparison
    print()
    print("=" * 80)
    print("RESULTS COMPARISON")
    print("=" * 80)
    print()

    print("FIXED EXIT (Original Strategy):")
    print("-" * 40)
    print(f"Total Trades: {stats_fixed['total_trades']:,}")
    print(f"Net Profit: ${stats_fixed['net_profit']:,.2f}")
    print(f"Profit Factor: {stats_fixed['profit_factor']:.2f}")
    print(f"Win Rate: {stats_fixed['win_rate']:.1%}")
    print(f"Avg Bars Held: {stats_fixed['avg_bars_held']:.1f}")
    print(f"Max Drawdown: ${stats_fixed['max_drawdown']:,.2f}")
    print()

    print("DYNAMIC EXIT (MSS-Based):")
    print("-" * 40)
    print(f"Total Trades: {stats_dynamic['total_trades']:,}")
    print(f"Net Profit: ${stats_dynamic['net_profit']:,.2f}")
    print(f"Profit Factor: {stats_dynamic['profit_factor']:.2f}")
    print(f"Win Rate: {stats_dynamic['win_rate']:.1%}")
    print(f"Avg Bars Held: {stats_dynamic['avg_bars_held']:.1f}")
    print(f"Max Drawdown: ${stats_dynamic['max_drawdown']:,.2f}")
    print()
    print(f"MSS Confirmed Rate: {stats_dynamic['mss_confirmed_rate']:.1%}")
    print(f"MSS Trades: {stats_dynamic['mss_trades']:,} (${stats_dynamic['mss_profit']:,.2f})")
    print(f"No MSS Trades: {stats_dynamic['no_mss_trades']:,} (${stats_dynamic['no_mss_profit']:,.2f})")
    print(f"Avg Bars (MSS): {stats_dynamic['avg_bars_mss']:.1f}")
    print(f"Avg Bars (No MSS): {stats_dynamic['avg_bars_no_mss']:.1f}")
    print()

    print("IMPROVEMENT:")
    print("-" * 40)
    profit_change = stats_dynamic['net_profit'] - stats_fixed['net_profit']
    profit_pct = (profit_change / stats_fixed['net_profit'] * 100) if stats_fixed['net_profit'] != 0 else 0
    pf_change = stats_dynamic['profit_factor'] - stats_fixed['profit_factor']
    wr_change = (stats_dynamic['win_rate'] - stats_fixed['win_rate']) * 100

    print(f"Net Profit Change: ${profit_change:,.2f} ({profit_pct:+.1f}%)")
    print(f"Profit Factor Change: {pf_change:+.2f}")
    print(f"Win Rate Change: {wr_change:+.1f}%")
    print()

    if profit_change > 0:
        print("✅ POSITIVE EFFECT: Dynamic exit improves performance!")
    else:
        print("❌ NEGATIVE EFFECT: Dynamic exit reduces performance.")
    print()

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        'fixed_exit': stats_fixed,
        'dynamic_exit': stats_dynamic,
        'improvement': {
            'profit_change_dollars': profit_change,
            'profit_change_percent': profit_pct,
            'profit_factor_change': pf_change,
            'win_rate_change_pct': wr_change,
        }
    }

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Results saved to: {output_path}")


if __name__ == '__main__':
    main()
