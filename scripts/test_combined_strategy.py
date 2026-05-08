#!/usr/bin/env python3
"""
Test Combined Strategy

Combine two strategies based on session:
1. Kill Zone sessions → Trend following (follow the signal)
2. Non-Kill Zone sessions → Reversal (reverse the signal)

This tests if we can get the best of both worlds.
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


def is_kill_zone(timestamp):
    """Check if timestamp is in kill zone"""
    ny_time = pd.Timestamp(timestamp).tz_convert('America/New_York')
    hour = ny_time.hour
    minute = ny_time.minute

    # NY AM: 8:30-11:30 EST
    ny_am = (hour == 8 and minute >= 30) or (9 <= hour < 11) or (hour == 11 and minute <= 30)

    # NY PM: 13:30-16:00 EST
    ny_pm = (hour == 13 and minute >= 30) or (14 <= hour < 16)

    return ny_am or ny_pm


def classify_session(timestamp):
    """Classify timestamp into session type"""
    ny_time = pd.Timestamp(timestamp).tz_convert('America/New_York')
    hour = ny_time.hour
    minute = ny_time.minute

    # NY AM Kill Zone: 8:30-11:30 EST
    if (hour == 8 and minute >= 30) or (9 <= hour < 11) or (hour == 11 and minute <= 30):
        return 'NY_AM_KZ'

    # NY PM Kill Zone: 13:30-16:00 EST
    if (hour == 13 and minute >= 30) or (14 <= hour < 16):
        return 'NY_PM_KZ'

    # Asian Session: 18:00-02:00 EST
    if hour >= 18 or hour < 2:
        return 'Asian'

    # London Session: 02:00-08:30 EST
    if 2 <= hour < 8 or (hour == 8 and minute < 30):
        return 'London'

    # Other
    return 'Other'


def build_combined_strategy_trades(frame: pd.DataFrame, costs: BacktestCosts):
    """
    Build trades using combined strategy:
    - Kill Zone → Trend following (use signal as-is)
    - Non-Kill Zone → Reversal (reverse signal)
    """

    # Get original signal
    original_signal = frame["premium_discount_reversal"]

    # Classify sessions
    frame['in_kill_zone'] = frame['ts'].apply(is_kill_zone)
    frame['session'] = frame['ts'].apply(classify_session)

    # Apply strategy based on session
    # Kill Zone → Trend (no reversal)
    # Non-Kill Zone → Reversal (multiply by -1)
    entry_signal = original_signal.copy()
    entry_signal = np.where(
        frame['in_kill_zone'],
        original_signal,      # Kill Zone: trend following
        original_signal * -1  # Non-Kill Zone: reversal
    )

    entry_indexes = np.flatnonzero(entry_signal != 0)

    if len(entry_indexes) == 0:
        return pd.DataFrame()

    # Extract arrays
    open_prices = frame["Open"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    timestamps = frame["ts"].to_numpy()
    symbols = frame["symbol"].astype(str).to_numpy()
    sessions = frame["session"].to_numpy()
    in_kz = frame["in_kill_zone"].to_numpy()

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

        direction = int(entry_signal[signal_index])
        entry_price = float(open_prices[entry_index])
        entry_symbol = symbols[signal_index]
        entry_session = sessions[signal_index]
        is_kz = bool(in_kz[signal_index])

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
            "in_kill_zone": is_kz,
            "strategy": "trend" if is_kz else "reversal",
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


def analyze_results(trades_df, title: str):
    """Analyze and print results"""

    pnls = trades_df['net_dollars'].values
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    cumulative = np.cumsum(pnls)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = running_max - cumulative
    max_dd = drawdowns.max() if len(drawdowns) > 0 else 0.0

    # Monthly stats
    trades_df['entry_date'] = pd.to_datetime(trades_df['entry_ts'])
    trades_df['month'] = trades_df['entry_date'].dt.to_period('M')
    monthly = trades_df.groupby('month')['net_dollars'].sum()
    sharpe = monthly.mean() / monthly.std() * np.sqrt(12) if monthly.std() > 0 else 0

    print("=" * 80)
    print(title)
    print("=" * 80)
    print()
    print(f"Total Trades: {len(trades_df):,}")
    print(f"Net Profit: ${pnls.sum():,.2f}")
    print(f"Profit Factor: {wins.sum() / abs(losses.sum()):.2f}" if len(losses) > 0 else "Profit Factor: inf")
    print(f"Win Rate: {len(wins) / len(trades_df):.1%}")
    print(f"Avg Win: ${wins.mean():,.2f}" if len(wins) > 0 else "Avg Win: $0.00")
    print(f"Avg Loss: ${losses.mean():,.2f}" if len(losses) > 0 else "Avg Loss: $0.00")
    print(f"Max Drawdown: ${max_dd:,.2f}")
    print(f"Sharpe Ratio: {sharpe:.2f}")
    print()
    print(f"Profitable Months: {(monthly > 0).sum()}/{len(monthly)} ({(monthly > 0).sum()/len(monthly):.1%})")
    print()


def main():
    print("=" * 80)
    print("Combined Strategy Test")
    print("Kill Zone → Trend Following | Non-Kill Zone → Reversal")
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

    # Build combined strategy trades
    print("Building combined strategy trades...")
    combined_trades = build_combined_strategy_trades(bars, costs)
    print(f"Generated {len(combined_trades):,} trades")
    print()

    # Analyze overall performance
    analyze_results(combined_trades, "COMBINED STRATEGY (Trend in KZ + Reversal outside KZ)")

    # Analyze by strategy type
    trend_trades = combined_trades[combined_trades['strategy'] == 'trend']
    reversal_trades = combined_trades[combined_trades['strategy'] == 'reversal']

    print("=" * 80)
    print("BREAKDOWN BY STRATEGY TYPE")
    print("=" * 80)
    print()

    if len(trend_trades) > 0:
        analyze_results(trend_trades, "Trend Following (Kill Zone)")

    if len(reversal_trades) > 0:
        analyze_results(reversal_trades, "Reversal (Non-Kill Zone)")

    # Compare with previous strategies
    print("=" * 80)
    print("COMPARISON WITH PREVIOUS STRATEGIES")
    print("=" * 80)
    print()

    combined_profit = combined_trades['net_dollars'].sum()
    combined_pf = combined_trades[combined_trades['net_dollars'] > 0]['net_dollars'].sum() / abs(combined_trades[combined_trades['net_dollars'] < 0]['net_dollars'].sum())

    print(f"{'Strategy':<40} {'Trades':<12} {'Net Profit':<18} {'PF':<8}")
    print("-" * 80)
    print(f"{'Original (KZ only, reversal)':<40} {49661:<12,} ${-436605:<17,.0f} {0.91:<7.2f}")
    print(f"{'All sessions (reversal)':<40} {207848:<12,} ${732555:<17,.0f} {1.06:<7.2f}")
    print(f"{'Best sessions (Asian+London, reversal)':<40} {142357:<12,} ${1333375:<17,.0f} {1.21:<7.2f}")
    print(f"{'COMBINED (Trend in KZ + Reversal out)':<40} {len(combined_trades):<12,} ${combined_profit:<17,.0f} {combined_pf:<7.2f}")
    print()

    # Calculate improvement
    best_previous = 1333375
    improvement = combined_profit - best_previous
    improvement_pct = (improvement / best_previous) * 100

    print(f"Improvement vs Best Previous: ${improvement:+,.0f} ({improvement_pct:+.1f}%)")
    print()

    if combined_profit > best_previous:
        print("🎉 COMBINED STRATEGY IS THE BEST! 🎉")
        print()
        print("This proves the hypothesis:")
        print("  ✅ Kill Zone → Trend following works")
        print("  ✅ Non-Kill Zone → Reversal works")
        print("  ✅ Combining them is even better!")
    elif combined_profit > 0:
        print("✅ Combined strategy is profitable")
        print("But not better than best sessions reversal")
        print()
        print("Possible reasons:")
        print("  - Trend following in Kill Zone still loses")
        print("  - Reversal in non-Kill Zone is already optimal")
        print("  - Signal not designed for trend following")
    else:
        print("❌ Combined strategy is not profitable")
        print()
        print("This means:")
        print("  - Trend following in Kill Zone doesn't work")
        print("  - Even with good reversal trades")
        print("  - The signal is designed for reversal only")

    # Save results
    output_dir = Path("reports")
    output_dir.mkdir(exist_ok=True)

    combined_trades.to_csv(output_dir / "combined_strategy_trades.csv", index=False)

    print()
    print(f"Results saved to {output_dir}/")


if __name__ == '__main__':
    main()
