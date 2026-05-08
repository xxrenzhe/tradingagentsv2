#!/usr/bin/env python3
"""
Dynamic Exit Backtest - Market Structure Tracking

Tests dynamic exit strategy that:
1. Enters on Premium/Discount reversal (same as original)
2. Exits after 2 bars by default
3. If MSS (Market Structure Shift) confirmed, extends holding
4. Exits on reverse MSS or max holding time

This should capture trend core profits while maintaining reversal entry advantage.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts

# Import signal building from original script
import importlib.util
spec = importlib.util.spec_from_file_location("lightglow_backtest", ROOT_DIR / "scripts" / "backtest_lightglow_nq_bars.py")
lightglow_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lightglow_module)
build_lightglow_signals = lightglow_module.build_lightglow_signals
resample_ohlcv = lightglow_module.resample_ohlcv


LONG = 1
SHORT = -1


@dataclass
class Trade:
    """Single trade record"""
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    direction: int
    bars_held: int
    pnl_points: float
    pnl_dollars: float
    exit_reason: str
    mss_confirmed: bool


class MarketStructureTracker:
    """Tracks market structure for dynamic exits"""

    def __init__(self, lookback: int = 5):
        self.lookback = lookback
        self.swing_high = None
        self.swing_low = None

    def update(self, bars: pd.DataFrame, current_idx: int):
        """Update swing highs and lows"""
        if current_idx < self.lookback:
            return

        start_idx = max(0, current_idx - self.lookback)
        window = bars.iloc[start_idx:current_idx]

        if len(window) > 0:
            self.swing_high = window['High'].max()
            self.swing_low = window['Low'].min()

    def check_mss(self, current_price: float, direction: int) -> bool:
        """Check if Market Structure Shift occurred"""
        if self.swing_high is None or self.swing_low is None:
            return False

        if direction == LONG:
            # Long position: MSS = break above swing high
            return current_price > self.swing_high
        else:
            # Short position: MSS = break below swing low
            return current_price < self.swing_low

    def check_reverse_mss(self, current_price: float, direction: int) -> bool:
        """Check if reverse MSS occurred (trend reversal)"""
        if self.swing_high is None or self.swing_low is None:
            return False

        if direction == LONG:
            # Long position: reverse MSS = break below swing low
            return current_price < self.swing_low
        else:
            # Short position: reverse MSS = break above swing high
            return current_price > self.swing_high


def backtest_dynamic_exit(
    bars: pd.DataFrame,
    signal_column: str,
    default_hold_bars: int = 2,
    max_trend_hold_bars: int = 20,
    costs: BacktestCosts = None,
) -> tuple[list[Trade], dict]:
    """
    Backtest with dynamic exit based on market structure

    Args:
        bars: OHLCV data with signal column
        signal_column: Column name for entry signals (1=long, -1=short, 0=none)
        default_hold_bars: Default holding period if no MSS
        max_trend_hold_bars: Maximum holding period even with MSS
        costs: Trading costs

    Returns:
        trades: List of Trade objects
        stats: Dictionary of performance statistics
    """
    if costs is None:
        costs = BacktestCosts()

    trades = []
    position = 0
    entry_idx = 0
    entry_price = 0.0
    entry_time = None
    mss_confirmed = False

    structure_tracker = MarketStructureTracker(lookback=5)

    for i in range(len(bars)):
        current_bar = bars.iloc[i]
        current_price = current_bar['Close']
        current_time = current_bar['ts']

        # Update market structure
        structure_tracker.update(bars, i)

        # Check exit conditions
        if position != 0:
            bars_held = i - entry_idx
            should_exit = False
            exit_reason = ""

            # Check for MSS confirmation
            if not mss_confirmed and bars_held >= default_hold_bars:
                if structure_tracker.check_mss(current_price, position):
                    mss_confirmed = True
                else:
                    # No MSS after default holding period -> exit
                    should_exit = True
                    exit_reason = "no_mss"

            # If MSS confirmed, check for reverse MSS or max holding
            if mss_confirmed:
                if structure_tracker.check_reverse_mss(current_price, position):
                    should_exit = True
                    exit_reason = "reverse_mss"
                elif bars_held >= max_trend_hold_bars:
                    should_exit = True
                    exit_reason = "max_holding"

            # Execute exit
            if should_exit:
                exit_price = current_price
                pnl_points = (exit_price - entry_price) * position

                # Apply costs
                slippage_points = costs.tick_size * costs.slippage_ticks_per_side * 2
                commission_points = (costs.commission_per_contract * 2) / costs.point_value
                net_pnl_points = pnl_points - slippage_points - commission_points
                net_pnl_dollars = net_pnl_points * costs.point_value

                trade = Trade(
                    entry_time=entry_time,
                    entry_price=entry_price,
                    exit_time=current_time,
                    exit_price=exit_price,
                    direction=position,
                    bars_held=bars_held,
                    pnl_points=net_pnl_points,
                    pnl_dollars=net_pnl_dollars,
                    exit_reason=exit_reason,
                    mss_confirmed=mss_confirmed,
                )
                trades.append(trade)

                # Reset position
                position = 0
                mss_confirmed = False

        # Check entry signals
        if position == 0:
            signal = current_bar[signal_column]
            if signal != 0:
                position = int(signal)
                entry_idx = i
                entry_price = current_price
                entry_time = current_time
                mss_confirmed = False

    # Calculate statistics
    stats = calculate_statistics(trades)

    return trades, stats


def calculate_statistics(trades: list[Trade]) -> dict:
    """Calculate performance statistics"""
    if not trades:
        return {
            'total_trades': 0,
            'net_profit_dollars': 0.0,
            'profit_factor': 0.0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'max_drawdown': 0.0,
            'mss_confirmed_rate': 0.0,
            'avg_bars_held': 0.0,
            'avg_bars_held_mss': 0.0,
            'avg_bars_held_no_mss': 0.0,
        }

    pnls = [t.pnl_dollars for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    # Calculate drawdown
    cumulative = np.cumsum(pnls)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = running_max - cumulative
    max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0.0

    # MSS statistics
    mss_trades = [t for t in trades if t.mss_confirmed]
    no_mss_trades = [t for t in trades if not t.mss_confirmed]

    stats = {
        'total_trades': len(trades),
        'net_profit_dollars': sum(pnls),
        'profit_factor': sum(wins) / abs(sum(losses)) if losses else float('inf'),
        'win_rate': len(wins) / len(trades) if trades else 0.0,
        'avg_win': np.mean(wins) if wins else 0.0,
        'avg_loss': np.mean(losses) if losses else 0.0,
        'max_drawdown': max_drawdown,
        'mss_confirmed_rate': len(mss_trades) / len(trades) if trades else 0.0,
        'avg_bars_held': np.mean([t.bars_held for t in trades]),
        'avg_bars_held_mss': np.mean([t.bars_held for t in mss_trades]) if mss_trades else 0.0,
        'avg_bars_held_no_mss': np.mean([t.bars_held for t in no_mss_trades]) if no_mss_trades else 0.0,
        'mss_trades': len(mss_trades),
        'no_mss_trades': len(no_mss_trades),
        'mss_profit': sum([t.pnl_dollars for t in mss_trades]),
        'no_mss_profit': sum([t.pnl_dollars for t in no_mss_trades]),
    }

    return stats


def main():
    parser = argparse.ArgumentParser(description='Backtest dynamic exit strategy')
    parser.add_argument('--start-date', default='2021-04-28', help='Start date YYYY-MM-DD')
    parser.add_argument('--end-date', default='2026-04-28', help='End date YYYY-MM-DD')
    parser.add_argument('--timeframe', type=int, default=1, help='Timeframe in minutes')
    parser.add_argument('--default-hold-bars', type=int, default=2, help='Default holding bars')
    parser.add_argument('--max-trend-hold-bars', type=int, default=20, help='Max trend holding bars')
    parser.add_argument('--output', default='reports/dynamic_exit_backtest.json', help='Output file')

    args = parser.parse_args()

    print("=" * 80)
    print("Dynamic Exit Backtest - Market Structure Tracking")
    print("=" * 80)
    print()
    print(f"Strategy: Premium/Discount Reversal + Dynamic Exit")
    print(f"Default Hold: {args.default_hold_bars} bars")
    print(f"Max Trend Hold: {args.max_trend_hold_bars} bars")
    print()

    # Load data
    print(f"Loading NQ bars from {args.start_date} to {args.end_date}...")
    bars = load_continuous_nq_bars(args.start_date, args.end_date)
    print(f"Loaded {len(bars):,} bars")
    print()

    # Resample if needed
    if args.timeframe > 1:
        print(f"Resampling to {args.timeframe}-minute bars...")
        bars = resample_ohlcv(bars, args.timeframe)
        print(f"Resampled to {len(bars):,} bars")
        print()

    # Build Lightglow signals
    print("Building Lightglow signals...")
    bars = build_lightglow_signals(bars)

    # Use reverse mode for premium_discount_reversal
    signal_column = 'premium_discount_reversal_reverse'

    if signal_column not in bars.columns:
        print(f"ERROR: Signal column '{signal_column}' not found!")
        print("Available columns:", bars.columns.tolist())
        return

    # Count signals
    signal_count = (bars[signal_column] != 0).sum()
    print(f"Found {signal_count:,} signals")
    print()

    # Run backtest
    print("Running backtest...")
    costs = BacktestCosts(commission_per_contract=5.0, slippage_ticks_per_side=1.0)
    trades, stats = backtest_dynamic_exit(
        bars=bars,
        signal_column=signal_column,
        default_hold_bars=args.default_hold_bars,
        max_trend_hold_bars=args.max_trend_hold_bars,
        costs=costs,
    )

    # Print results
    print()
    print("=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)
    print()
    print(f"Total Trades: {stats['total_trades']:,}")
    print(f"Net Profit: ${stats['net_profit_dollars']:,.2f}")
    print(f"Profit Factor: {stats['profit_factor']:.2f}")
    print(f"Win Rate: {stats['win_rate']:.1%}")
    print(f"Avg Win: ${stats['avg_win']:,.2f}")
    print(f"Avg Loss: ${stats['avg_loss']:,.2f}")
    print(f"Max Drawdown: ${stats['max_drawdown']:,.2f}")
    print()
    print("MSS Statistics:")
    print(f"  MSS Confirmed Rate: {stats['mss_confirmed_rate']:.1%}")
    print(f"  MSS Trades: {stats['mss_trades']:,} (${stats['mss_profit']:,.2f})")
    print(f"  No MSS Trades: {stats['no_mss_trades']:,} (${stats['no_mss_profit']:,.2f})")
    print(f"  Avg Bars Held (MSS): {stats['avg_bars_held_mss']:.1f}")
    print(f"  Avg Bars Held (No MSS): {stats['avg_bars_held_no_mss']:.1f}")
    print()

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        'config': {
            'start_date': args.start_date,
            'end_date': args.end_date,
            'timeframe_minutes': args.timeframe,
            'default_hold_bars': args.default_hold_bars,
            'max_trend_hold_bars': args.max_trend_hold_bars,
        },
        'stats': stats,
        'trades': [
            {
                'entry_time': str(t.entry_time),
                'entry_price': t.entry_price,
                'exit_time': str(t.exit_time),
                'exit_price': t.exit_price,
                'direction': 'LONG' if t.direction == LONG else 'SHORT',
                'bars_held': t.bars_held,
                'pnl_dollars': t.pnl_dollars,
                'exit_reason': t.exit_reason,
                'mss_confirmed': t.mss_confirmed,
            }
            for t in trades[:1000]  # Save first 1000 trades
        ]
    }

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Results saved to: {output_path}")
    print()


if __name__ == '__main__':
    main()
