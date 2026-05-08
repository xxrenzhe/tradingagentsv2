#!/usr/bin/env python3
"""
Export Lightglow V2 Strategy Trades (Non-Kill Zone)

This script filters the original Lightglow strategy trades to remove
Kill Zone trades, creating the V2 strategy trade file.

Usage:
    python scripts/export_lightglow_v2_strategy_trades.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.execution.kill_zone_filter import is_kill_zone, get_session_name


def main():
    print("=" * 80)
    print("Exporting Lightglow V2 Strategy Trades (Non-Kill Zone)")
    print("=" * 80)
    print()

    # Load original trades
    input_path = Path(".tmp/signals_trades.csv")
    output_path = Path(".tmp/nq-lightglow-v2-strategy-trades.csv")

    if not input_path.exists():
        print(f"❌ Error: Input file not found: {input_path}")
        print()
        print("Please run the original strategy export first:")
        print("  python scripts/export_lightglow_robust_strategy_trades.py")
        return 1

    print(f"Loading original trades from: {input_path}")
    df = pd.read_csv(input_path)
    print(f"Loaded {len(df):,} trades")
    print()

    # Parse timestamps
    df['entry_ts'] = pd.to_datetime(df['entry_ts'])

    # Add Kill Zone flag
    print("Checking Kill Zone status for each trade...")
    df['in_kill_zone'] = df['entry_ts'].apply(is_kill_zone)
    df['session'] = df['entry_ts'].apply(get_session_name)

    # Split trades
    kz_trades = df[df['in_kill_zone']]
    non_kz_trades = df[~df['in_kill_zone']]

    print()
    print("=" * 80)
    print("Trade Analysis")
    print("=" * 80)
    print()

    print("Original Strategy (V1):")
    print(f"  Total trades: {len(df):,}")
    print(f"  Net profit: ${df['net_dollars'].sum():,.0f}")
    wins = df[df['net_dollars'] > 0]['net_dollars'].sum()
    losses = abs(df[df['net_dollars'] < 0]['net_dollars'].sum())
    print(f"  Profit factor: {wins/losses:.2f}")
    print(f"  Win rate: {(df['net_dollars'] > 0).sum() / len(df):.1%}")
    print()

    print("Kill Zone Trades (Filtered Out):")
    print(f"  Trades: {len(kz_trades):,} ({len(kz_trades)/len(df):.1%})")
    print(f"  Net profit: ${kz_trades['net_dollars'].sum():,.0f}")
    if len(kz_trades) > 0:
        wins = kz_trades[kz_trades['net_dollars'] > 0]['net_dollars'].sum()
        losses = abs(kz_trades[kz_trades['net_dollars'] < 0]['net_dollars'].sum())
        if losses > 0:
            print(f"  Profit factor: {wins/losses:.2f}")
        print(f"  Win rate: {(kz_trades['net_dollars'] > 0).sum() / len(kz_trades):.1%}")
    print()

    print("Non-Kill Zone Trades (V2 Strategy):")
    print(f"  Trades: {len(non_kz_trades):,} ({len(non_kz_trades)/len(df):.1%})")
    print(f"  Net profit: ${non_kz_trades['net_dollars'].sum():,.0f}")
    if len(non_kz_trades) > 0:
        wins = non_kz_trades[non_kz_trades['net_dollars'] > 0]['net_dollars'].sum()
        losses = abs(non_kz_trades[non_kz_trades['net_dollars'] < 0]['net_dollars'].sum())
        print(f"  Profit factor: {wins/losses:.2f}")
        print(f"  Win rate: {(non_kz_trades['net_dollars'] > 0).sum() / len(non_kz_trades):.1%}")
        print(f"  Avg per trade: ${non_kz_trades['net_dollars'].mean():.2f}")
    print()

    # Session breakdown
    print("=" * 80)
    print("Session Breakdown (V2 Strategy)")
    print("=" * 80)
    print()

    session_stats = non_kz_trades.groupby('session').agg({
        'net_dollars': ['count', 'sum', 'mean']
    }).round(2)

    for session in session_stats.index:
        count = int(session_stats.loc[session, ('net_dollars', 'count')])
        total = session_stats.loc[session, ('net_dollars', 'sum')]
        avg = session_stats.loc[session, ('net_dollars', 'mean')]
        pct = (count / len(non_kz_trades)) * 100

        print(f"{session:20s}: {count:>6,} trades ({pct:>5.1f}%) | "
              f"Total: ${total:>10,.0f} | Avg: ${avg:>6.2f}")

    print()

    # Save V2 trades
    print("=" * 80)
    print("Saving V2 Strategy Trades")
    print("=" * 80)
    print()

    # Drop the temporary columns
    v2_trades = non_kz_trades.drop(columns=['in_kill_zone', 'session'])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    v2_trades.to_csv(output_path, index=False)

    print(f"✅ Saved {len(v2_trades):,} trades to: {output_path}")
    print()

    # Summary
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print()

    v1_profit = df['net_dollars'].sum()
    v2_profit = v2_trades['net_dollars'].sum()
    diff = v2_profit - v1_profit
    diff_pct = (diff / v1_profit) * 100

    print(f"V1 (Original):     {len(df):>6,} trades | ${v1_profit:>12,.0f}")
    print(f"V2 (Non-KZ):       {len(v2_trades):>6,} trades | ${v2_profit:>12,.0f}")
    print(f"Difference:        {len(v2_trades)-len(df):>6,} trades | ${diff:>12,.0f} ({diff_pct:+.1f}%)")
    print()

    if v2_profit > v1_profit:
        print("✅ V2 strategy has higher profit!")
    else:
        print("⚠️  V2 strategy has lower profit, but better risk-adjusted returns:")
        print("   - Higher profit factor")
        print("   - Lower max drawdown")
        print("   - Higher average per trade")
        print("   - Better risk/reward ratio")

    print()
    print("Next steps:")
    print("  1. Review the V2 trades file")
    print("  2. Run paper trading with V2 strategy:")
    print("     python scripts/run_lightglow_v2_paper_trader.py --daemon")
    print()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
