#!/usr/bin/env python3
"""
Test Session Performance

Analyze strategy performance across different time sessions:
1. Kill Zone (NY AM + NY PM)
2. Asian Session
3. London Session
4. Other times

Find which sessions work best for this reversal strategy.
"""

from __future__ import annotations

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
)
from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts


def classify_session(timestamp):
    """Classify timestamp into trading session"""
    # Convert to NY time
    ny_time = pd.Timestamp(timestamp).tz_convert('America/New_York')
    hour = ny_time.hour
    minute = ny_time.minute

    # NY AM Kill Zone: 8:30-11:30 EST
    if (hour == 8 and minute >= 30) or (9 <= hour < 11) or (hour == 11 and minute <= 30):
        return 'NY_AM_KZ'

    # NY PM Kill Zone: 13:30-16:00 EST
    if (hour == 13 and minute >= 30) or (14 <= hour < 16):
        return 'NY_PM_KZ'

    # Asian Session: 18:00-02:00 EST (6pm-2am)
    if hour >= 18 or hour < 2:
        return 'Asian'

    # London Session: 02:00-08:30 EST (2am-8:30am)
    if 2 <= hour < 8 or (hour == 8 and minute < 30):
        return 'London'

    # London/NY Overlap: 11:30-13:30 EST
    if (hour == 11 and minute > 30) or hour == 12 or (hour == 13 and minute < 30):
        return 'London_NY_Overlap'

    # After Hours: 16:00-18:00 EST
    if 16 <= hour < 18:
        return 'After_Hours'

    return 'Other'


def build_trades_by_session(frame: pd.DataFrame, costs: BacktestCosts):
    """Build trades and classify by session"""

    # Get signals and REVERSE them
    entry_signal = frame["premium_discount_reversal"] * -1

    # Classify sessions
    frame['session'] = frame['ts'].apply(classify_session)

    entry_indexes = np.flatnonzero(entry_signal != 0)

    if len(entry_indexes) == 0:
        return pd.DataFrame()

    # Extract arrays
    open_prices = frame["Open"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    timestamps = frame["ts"].to_numpy()
    symbols = frame["symbol"].astype(str).to_numpy()
    sessions = frame["session"].to_numpy()

    rows = []
    next_available_signal_index = 0

    for signal_index in entry_indexes:
        signal_index = int(signal_index)

        # Check overlap
        if signal_index < next_available_signal_index:
            continue

        entry_index = signal_index + 1

        if entry_index >= len(frame):
            continue

        direction = int(entry_signal.iloc[signal_index])
        entry_price = float(open_prices[entry_index])
        entry_symbol = symbols[signal_index]
        entry_session = sessions[signal_index]

        # Hold for 2 bars
        exit_index = min(entry_index + 1, len(frame) - 1)
        exit_reason = "time"

        # Check symbol change
        if symbols[exit_index] != entry_symbol:
            exit_index = entry_index
            exit_reason = "symbol_change"

        # Calculate PnL
        exit_price = float(close_prices[exit_index])
        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points

        rows.append({
            "entry_ts": timestamps[signal_index],
            "exit_ts": timestamps[exit_index],
            "session": entry_session,
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
            "bars_held": exit_index - entry_index,
        })

        next_available_signal_index = exit_index + 1

    return pd.DataFrame(rows)


def analyze_session(trades_df, session_name: str):
    """Analyze performance for a specific session"""

    session_trades = trades_df[trades_df['session'] == session_name]

    if len(session_trades) == 0:
        return None

    pnls = session_trades['net_dollars'].values
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    return {
        'session': session_name,
        'trades': len(session_trades),
        'net_profit': pnls.sum(),
        'profit_factor': wins.sum() / abs(losses.sum()) if len(losses) > 0 else float('inf'),
        'win_rate': len(wins) / len(session_trades),
        'avg_win': wins.mean() if len(wins) > 0 else 0,
        'avg_loss': losses.mean() if len(losses) > 0 else 0,
        'avg_trade': pnls.mean(),
    }


def main():
    print("=" * 80)
    print("Session Performance Analysis")
    print("=" * 80)
    print()

    # Load data
    print("Loading NQ bars...")
    args = type('Args', (), {
        'start_date': '2022-10-25',
        'end_date': '2026-04-28',
        'min_volume': 0,
        'cache': '.cache/nq_bars.pkl',
        'chunk_size': 100000,
    })()

    bars = load_continuous_nq_bars(args)
    print(f"Loaded {len(bars):,} bars")
    print()

    bars = resample_ohlcv(bars, 1)
    print(f"Resampled to {len(bars):,} bars")
    print()

    print("Building Lightglow signals...")
    bars = build_lightglow_signals(bars)
    print("Signals built")
    print()

    costs = BacktestCosts(commission_per_contract=5.0, slippage_ticks_per_side=1.0)

    # Build trades with session classification
    print("Building trades by session...")
    trades = build_trades_by_session(bars, costs)
    print(f"Generated {len(trades):,} trades")
    print()

    # Analyze each session
    sessions = ['NY_AM_KZ', 'NY_PM_KZ', 'Asian', 'London', 'London_NY_Overlap', 'After_Hours', 'Other']

    results = []
    for session in sessions:
        result = analyze_session(trades, session)
        if result:
            results.append(result)

    # Sort by profit factor
    results.sort(key=lambda x: x['profit_factor'], reverse=True)

    print("=" * 80)
    print("SESSION PERFORMANCE RANKING (by Profit Factor)")
    print("=" * 80)
    print()

    print(f"{'Session':<20} {'Trades':<10} {'Net Profit':<15} {'PF':<8} {'Win%':<8} {'Avg Trade':<12}")
    print("-" * 80)

    for r in results:
        print(f"{r['session']:<20} {r['trades']:<10,} ${r['net_profit']:<14,.0f} {r['profit_factor']:<7.2f} {r['win_rate']:<7.1%} ${r['avg_trade']:<11,.2f}")

    print()

    # Group analysis
    print("=" * 80)
    print("GROUPED ANALYSIS")
    print("=" * 80)
    print()

    # Kill Zone vs Non-Kill Zone
    kz_sessions = ['NY_AM_KZ', 'NY_PM_KZ']
    non_kz_sessions = ['Asian', 'London', 'London_NY_Overlap', 'After_Hours', 'Other']

    kz_trades = trades[trades['session'].isin(kz_sessions)]
    non_kz_trades = trades[trades['session'].isin(non_kz_sessions)]

    print("Kill Zone vs Non-Kill Zone:")
    print()

    kz_pnls = kz_trades['net_dollars'].values
    kz_wins = kz_pnls[kz_pnls > 0]
    kz_losses = kz_pnls[kz_pnls < 0]

    non_kz_pnls = non_kz_trades['net_dollars'].values
    non_kz_wins = non_kz_pnls[non_kz_pnls > 0]
    non_kz_losses = non_kz_pnls[non_kz_pnls < 0]

    print(f"{'Group':<20} {'Trades':<10} {'Net Profit':<15} {'PF':<8} {'Win%':<8}")
    print("-" * 60)
    print(f"{'Kill Zone':<20} {len(kz_trades):<10,} ${kz_pnls.sum():<14,.0f} {kz_wins.sum() / abs(kz_losses.sum()):<7.2f} {len(kz_wins) / len(kz_trades):<7.1%}")
    print(f"{'Non-Kill Zone':<20} {len(non_kz_trades):<10,} ${non_kz_pnls.sum():<14,.0f} {non_kz_wins.sum() / abs(non_kz_losses.sum()):<7.2f} {len(non_kz_wins) / len(non_kz_trades):<7.1%}")
    print()

    # Best sessions
    print("=" * 80)
    print("BEST SESSIONS FOR REVERSAL STRATEGY")
    print("=" * 80)
    print()

    best_sessions = [r for r in results if r['profit_factor'] > 1.0]

    if best_sessions:
        print("Sessions with Profit Factor > 1.0:")
        print()
        for r in best_sessions:
            print(f"  {r['session']:<20} PF: {r['profit_factor']:.2f}, Trades: {r['trades']:,}, Profit: ${r['net_profit']:,.0f}")
        print()

        # Calculate combined performance
        best_session_names = [r['session'] for r in best_sessions]
        best_trades = trades[trades['session'].isin(best_session_names)]
        best_pnls = best_trades['net_dollars'].values
        best_wins = best_pnls[best_pnls > 0]
        best_losses = best_pnls[best_pnls < 0]

        print("Combined Best Sessions Performance:")
        print(f"  Trades: {len(best_trades):,}")
        print(f"  Net Profit: ${best_pnls.sum():,.0f}")
        print(f"  Profit Factor: {best_wins.sum() / abs(best_losses.sum()):.2f}")
        print(f"  Win Rate: {len(best_wins) / len(best_trades):.1%}")
        print()

        # Compare with all sessions
        all_pnls = trades['net_dollars'].values
        improvement = (best_pnls.sum() - all_pnls.sum()) / abs(all_pnls.sum()) * 100

        print(f"Improvement vs All Sessions: {improvement:+.1f}%")
        print()
    else:
        print("No sessions with Profit Factor > 1.0")
        print()

    # Worst sessions
    worst_sessions = [r for r in results if r['profit_factor'] < 1.0]

    if worst_sessions:
        print("=" * 80)
        print("WORST SESSIONS (Should Avoid)")
        print("=" * 80)
        print()

        for r in worst_sessions:
            print(f"  {r['session']:<20} PF: {r['profit_factor']:.2f}, Trades: {r['trades']:,}, Profit: ${r['net_profit']:,.0f}")
        print()

    # Save results
    output_dir = Path("reports")
    output_dir.mkdir(exist_ok=True)

    trades.to_csv(output_dir / "trades_by_session.csv", index=False)

    results_df = pd.DataFrame(results)
    results_df.to_csv(output_dir / "session_performance.csv", index=False)

    print(f"Results saved to {output_dir}/")


if __name__ == '__main__':
    main()
