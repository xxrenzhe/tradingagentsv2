#!/usr/bin/env python3
"""
Dynamic Exit Comparison - Using Trades Data

Compares original strategy (fixed 2-bar exit) with dynamic exit (MSS-based)
by re-simulating exits from the original trades data.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def simulate_dynamic_exit(trades_df: pd.DataFrame, bars_df: pd.DataFrame, max_hold_bars: int = 20) -> list[dict]:
    """
    Re-simulate trades with dynamic exit logic

    Uses the same entry points as original trades, but applies MSS-based exit logic.
    """

    # Group bars by timestamp for fast lookup
    bars_dict = {ts: row for ts, row in bars_df.set_index('ts').iterrows()}

    new_trades = []
    lookback = 5

    for _, trade in trades_df.iterrows():
        entry_ts = pd.to_datetime(trade['entry_ts'])
        direction = 1 if trade['direction'] == 1 else -1
        entry_price = trade['entry_price']

        # Find entry bar index
        entry_bar = bars_df[bars_df['ts'] == entry_ts]
        if len(entry_bar) == 0:
            continue

        entry_idx = entry_bar.index[0]

        # Simulate holding with dynamic exit
        mss_confirmed = False
        bars_held = 0
        exit_idx = entry_idx
        exit_reason = "unknown"

        for i in range(entry_idx + 1, min(entry_idx + max_hold_bars + 1, len(bars_df))):
            bars_held = i - entry_idx
            current_bar = bars_df.iloc[i]
            current_price = current_bar['Close']

            # Calculate swing high/low
            if i >= lookback:
                window = bars_df.iloc[max(0, i - lookback):i]
                swing_high = window['High'].max()
                swing_low = window['Low'].min()
            else:
                swing_high = None
                swing_low = None

            # Check exit conditions
            should_exit = False

            if not mss_confirmed and bars_held >= 2:
                # Check for MSS
                if swing_high and swing_low:
                    if direction == 1 and current_price > swing_high:
                        mss_confirmed = True
                    elif direction == -1 and current_price < swing_low:
                        mss_confirmed = True
                    else:
                        should_exit = True
                        exit_reason = "no_mss"
                else:
                    should_exit = True
                    exit_reason = "no_mss"

            if mss_confirmed and not should_exit:
                # Check for reverse MSS
                if swing_high and swing_low:
                    if direction == 1 and current_price < swing_low:
                        should_exit = True
                        exit_reason = "reverse_mss"
                    elif direction == -1 and current_price > swing_high:
                        should_exit = True
                        exit_reason = "reverse_mss"

                # Max holding time
                if bars_held >= max_hold_bars:
                    should_exit = True
                    exit_reason = "max_holding"

            if should_exit:
                exit_idx = i
                break

        # Calculate PnL
        exit_bar = bars_df.iloc[exit_idx]
        exit_price = exit_bar['Close']
        exit_ts = exit_bar['ts']

        pnl_points = (exit_price - entry_price) * direction

        # Apply costs (same as original)
        slippage_points = 0.25 * 2  # 0.25 per side
        commission_points = (5.0 * 2) / 20.0  # $5 per side, $20 per point
        net_pnl_points = pnl_points - slippage_points - commission_points
        net_pnl_dollars = net_pnl_points * 20.0

        new_trades.append({
            'entry_ts': entry_ts,
            'entry_price': entry_price,
            'exit_ts': exit_ts,
            'exit_price': exit_price,
            'direction': 'LONG' if direction == 1 else 'SHORT',
            'bars_held': bars_held,
            'pnl_points': net_pnl_points,
            'pnl_dollars': net_pnl_dollars,
            'exit_reason': exit_reason,
            'mss_confirmed': mss_confirmed,
        })

    return new_trades


def calculate_stats(trades: list[dict]) -> dict:
    """Calculate performance statistics"""
    if not trades:
        return {'total_trades': 0}

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
    parser.add_argument('--trades', default='.tmp/signals_trades.csv', help='Original trades CSV')
    parser.add_argument('--bars', required=True, help='Bars CSV with OHLCV')
    parser.add_argument('--output', default='reports/dynamic_exit_comparison.json', help='Output file')

    args = parser.parse_args()

    print("=" * 80)
    print("Dynamic Exit Comparison - Using Trades Data")
    print("=" * 80)
    print()

    # Load trades
    print(f"Loading original trades from {args.trades}...")
    trades_df = pd.read_csv(args.trades)
    trades_df['entry_ts'] = pd.to_datetime(trades_df['entry_ts'])
    trades_df['exit_ts'] = pd.to_datetime(trades_df['exit_ts'])
    print(f"Loaded {len(trades_df):,} trades")

    # Calculate original stats
    original_pnls = trades_df['net_dollars'].values
    original_wins = original_pnls[original_pnls > 0]
    original_losses = original_pnls[original_pnls < 0]
    original_cumulative = np.cumsum(original_pnls)
    original_running_max = np.maximum.accumulate(original_cumulative)
    original_drawdowns = original_running_max - original_cumulative

    stats_original = {
        'total_trades': len(trades_df),
        'net_profit': trades_df['net_dollars'].sum(),
        'profit_factor': original_wins.sum() / abs(original_losses.sum()) if len(original_losses) > 0 else float('inf'),
        'win_rate': len(original_wins) / len(trades_df),
        'avg_win': original_wins.mean() if len(original_wins) > 0 else 0.0,
        'avg_loss': original_losses.mean() if len(original_losses) > 0 else 0.0,
        'max_drawdown': original_drawdowns.max() if len(original_drawdowns) > 0 else 0.0,
        'avg_bars_held': 2.0,  # Fixed 2-bar exit
    }

    # Load bars
    print(f"Loading bars from {args.bars}...")
    bars_df = pd.read_csv(args.bars)
    bars_df['ts'] = pd.to_datetime(bars_df['ts'])
    print(f"Loaded {len(bars_df):,} bars")
    print()

    # Simulate dynamic exit
    print("Simulating dynamic exit strategy...")
    dynamic_trades = simulate_dynamic_exit(trades_df, bars_df, max_hold_bars=20)
    stats_dynamic = calculate_stats(dynamic_trades)

    # Print comparison
    print()
    print("=" * 80)
    print("RESULTS COMPARISON")
    print("=" * 80)
    print()

    print("ORIGINAL STRATEGY (Fixed 2-bar exit):")
    print("-" * 40)
    print(f"Total Trades: {stats_original['total_trades']:,}")
    print(f"Net Profit: ${stats_original['net_profit']:,.2f}")
    print(f"Profit Factor: {stats_original['profit_factor']:.2f}")
    print(f"Win Rate: {stats_original['win_rate']:.1%}")
    print(f"Avg Bars Held: {stats_original['avg_bars_held']:.1f}")
    print(f"Max Drawdown: ${stats_original['max_drawdown']:,.2f}")
    print()

    print("DYNAMIC EXIT STRATEGY (MSS-based):")
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
    profit_change = stats_dynamic['net_profit'] - stats_original['net_profit']
    profit_pct = (profit_change / stats_original['net_profit'] * 100) if stats_original['net_profit'] != 0 else 0
    pf_change = stats_dynamic['profit_factor'] - stats_original['profit_factor']
    wr_change = (stats_dynamic['win_rate'] - stats_original['win_rate']) * 100

    print(f"Net Profit Change: ${profit_change:,.2f} ({profit_pct:+.1f}%)")
    print(f"Profit Factor Change: {pf_change:+.2f}")
    print(f"Win Rate Change: {wr_change:+.1f}%")
    print()

    if profit_change > 0:
        print("✅ SUCCESS: Dynamic exit improves performance!")
    else:
        print("❌ FAILURE: Dynamic exit reduces performance.")
    print()

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        'original_strategy': stats_original,
        'dynamic_exit_strategy': stats_dynamic,
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
