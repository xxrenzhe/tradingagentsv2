#!/usr/bin/env python3
"""
Test Kill Zone Impact

Compare strategy performance:
1. With kill zone filter (original)
2. Without kill zone filter (all sessions)
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
    """Check if timestamp is in kill zone (NY AM or NY PM)"""
    # Convert to NY time
    ny_time = pd.Timestamp(timestamp).tz_convert('America/New_York')
    hour = ny_time.hour
    minute = ny_time.minute

    # NY AM: 8:30-11:30 EST
    ny_am = (hour == 8 and minute >= 30) or (9 <= hour < 11) or (hour == 11 and minute <= 30)

    # NY PM: 13:30-16:00 EST
    ny_pm = (hour == 13 and minute >= 30) or (14 <= hour < 16)

    return ny_am or ny_pm


def build_trades(frame: pd.DataFrame, costs: BacktestCosts, use_kill_zone: bool = True):
    """Build trades with optional kill zone filter"""

    # Get signals and REVERSE them (original strategy uses reverse mode)
    entry_signal = frame["premium_discount_reversal"] * -1

    # Apply kill zone filter if requested
    if use_kill_zone:
        frame['in_kill_zone'] = frame['ts'].apply(is_kill_zone)
        entry_signal = entry_signal * frame['in_kill_zone'].astype(int)

    entry_indexes = np.flatnonzero(entry_signal != 0)

    if len(entry_indexes) == 0:
        return pd.DataFrame()

    # Extract arrays
    open_prices = frame["Open"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    timestamps = frame["ts"].to_numpy()
    symbols = frame["symbol"].astype(str).to_numpy()

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
    print(f"Best Month: ${monthly.max():,.2f}")
    print(f"Worst Month: ${monthly.min():,.2f}")
    print()


def main():
    print("=" * 80)
    print("Kill Zone Impact Test")
    print("=" * 80)
    print()

    # Load data
    print("Loading NQ bars...")
    args = type('Args', (), {
        'start_date': '2022-10-25',  # Match original strategy start date
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

    # Test with kill zone (original)
    print("Testing WITH kill zone filter...")
    trades_with_kz = build_trades(bars, costs, use_kill_zone=True)
    analyze_results(trades_with_kz, "WITH Kill Zone Filter (Original)")

    # Test without kill zone
    print("Testing WITHOUT kill zone filter...")
    trades_without_kz = build_trades(bars, costs, use_kill_zone=False)
    analyze_results(trades_without_kz, "WITHOUT Kill Zone Filter (All Sessions)")

    # Comparison
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print()

    profit_with = trades_with_kz['net_dollars'].sum()
    profit_without = trades_without_kz['net_dollars'].sum()

    pf_with = trades_with_kz[trades_with_kz['net_dollars'] > 0]['net_dollars'].sum() / abs(trades_with_kz[trades_with_kz['net_dollars'] < 0]['net_dollars'].sum())
    pf_without = trades_without_kz[trades_without_kz['net_dollars'] > 0]['net_dollars'].sum() / abs(trades_without_kz[trades_without_kz['net_dollars'] < 0]['net_dollars'].sum())

    print(f"{'Metric':<30} {'With Kill Zone':<20} {'Without Kill Zone':<20} {'Difference':<15}")
    print("-" * 85)
    print(f"{'Trades':<30} {len(trades_with_kz):<20,} {len(trades_without_kz):<20,} {len(trades_without_kz) - len(trades_with_kz):<15,}")
    print(f"{'Net Profit':<30} ${profit_with:<19,.0f} ${profit_without:<19,.0f} ${profit_without - profit_with:<14,.0f}")
    print(f"{'Profit Factor':<30} {pf_with:<20.2f} {pf_without:<20.2f} {pf_without - pf_with:<15.2f}")
    print(f"{'Win Rate':<30} {len(trades_with_kz[trades_with_kz['net_dollars'] > 0]) / len(trades_with_kz):<20.1%} {len(trades_without_kz[trades_without_kz['net_dollars'] > 0]) / len(trades_without_kz):<20.1%}")
    print()

    improvement = (profit_without - profit_with) / profit_with * 100
    print(f"Profit Improvement: {improvement:+.1f}%")
    print()

    # Analyze trades outside kill zone
    trades_with_kz['in_kz'] = True
    trades_without_kz['in_kz'] = trades_without_kz['entry_ts'].apply(is_kill_zone)

    outside_kz = trades_without_kz[~trades_without_kz['in_kz']]

    if len(outside_kz) > 0:
        print("=" * 80)
        print("TRADES OUTSIDE KILL ZONE")
        print("=" * 80)
        print()

        outside_pnls = outside_kz['net_dollars'].values
        outside_wins = outside_pnls[outside_pnls > 0]
        outside_losses = outside_pnls[outside_pnls < 0]

        print(f"Trades: {len(outside_kz):,}")
        print(f"Net Profit: ${outside_pnls.sum():,.2f}")
        print(f"Profit Factor: {outside_wins.sum() / abs(outside_losses.sum()):.2f}" if len(outside_losses) > 0 else "Profit Factor: inf")
        print(f"Win Rate: {len(outside_wins) / len(outside_kz):.1%}")
        print(f"Avg Win: ${outside_wins.mean():,.2f}" if len(outside_wins) > 0 else "Avg Win: $0.00")
        print(f"Avg Loss: ${outside_losses.mean():,.2f}" if len(outside_losses) > 0 else "Avg Loss: $0.00")
        print()

        print("Conclusion:")
        if outside_pnls.sum() > 0:
            print("  ✅ Trades outside kill zone are PROFITABLE")
            print("  ✅ Removing kill zone filter improves performance")
        else:
            print("  ❌ Trades outside kill zone are UNPROFITABLE")
            print("  ✅ Kill zone filter is beneficial")

    # Save results
    output_dir = Path("reports")
    output_dir.mkdir(exist_ok=True)

    trades_with_kz.to_csv(output_dir / "trades_with_killzone.csv", index=False)
    trades_without_kz.to_csv(output_dir / "trades_without_killzone.csv", index=False)
    outside_kz.to_csv(output_dir / "trades_outside_killzone.csv", index=False)

    print(f"\nResults saved to {output_dir}/")


if __name__ == '__main__':
    main()
