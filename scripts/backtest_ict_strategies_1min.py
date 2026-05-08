#!/usr/bin/env python3
"""
Backtest ICT strategies on 5-year 1-minute data
Compare with 5-minute Kill Zone results
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from io import TextIOWrapper
from pathlib import Path
import re

import numpy as np
import pandas as pd
import zstandard as zstd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.dataflows.databento import _bar_zip_path

NQ_SYMBOL_RE = re.compile(r"^NQ[FGHJKMNQUVXZ]\d{1,2}$")
BAR_MEMBER = "glbx-mdp3-20100606-20260427.ohlcv-1m.csv.zst"


def load_nq_1min_bars(start_date: str, end_date: str, min_volume: int = 1) -> pd.DataFrame:
    """Load 1-minute NQ bars from databento archive"""
    print(f"Loading 1-minute bars from {start_date} to {end_date}...")

    source = _bar_zip_path()
    start_ts = pd.Timestamp(start_date, tz="UTC")
    end_ts = pd.Timestamp(end_date, tz="UTC")

    chunks: list[pd.DataFrame] = []
    usecols = ["ts_event", "open", "high", "low", "close", "volume", "symbol"]

    with zipfile.ZipFile(source) as archive:
        with archive.open(BAR_MEMBER) as compressed:
            stream = zstd.ZstdDecompressor().stream_reader(compressed)
            text_stream = TextIOWrapper(stream, encoding="utf-8")

            for chunk in pd.read_csv(text_stream, usecols=usecols, chunksize=100000):
                symbols = chunk["symbol"].astype(str)
                chunk = chunk[symbols.map(lambda value: bool(NQ_SYMBOL_RE.match(value)))]
                if chunk.empty:
                    continue

                chunk["timestamp"] = pd.to_datetime(chunk["ts_event"], utc=True)
                chunk = chunk[(chunk["timestamp"] >= start_ts) & (chunk["timestamp"] < end_ts)]
                if chunk.empty:
                    continue

                for column in ["open", "high", "low", "close", "volume"]:
                    chunk[column] = pd.to_numeric(chunk[column], errors="coerce")

                chunk = chunk.dropna(subset=["open", "high", "low", "close", "volume"])
                chunk = chunk[chunk["volume"] >= min_volume]

                if not chunk.empty:
                    chunks.append(chunk[["timestamp", "symbol", "open", "high", "low", "close", "volume"]])

    if not chunks:
        raise SystemExit(f"No NQ bar rows found for {start_date}..{end_date}")

    bars = pd.concat(chunks, ignore_index=True)
    bars = bars.sort_values(["timestamp", "volume"], ascending=[True, False]).drop_duplicates("timestamp", keep="first")
    bars = bars.sort_values("timestamp").reset_index(drop=True)

    print(f"Loaded {len(bars):,} bars")
    return bars


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add time-based features"""
    df = df.copy()
    df['hour'] = df['timestamp'].dt.hour
    df['minute'] = df['timestamp'].dt.minute
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    return df


def calculate_premium_discount(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """Calculate Premium/Discount zones"""
    df = df.copy()
    df['range_high'] = df['high'].rolling(lookback).max()
    df['range_low'] = df['low'].rolling(lookback).min()
    df['range_mid'] = (df['range_high'] + df['range_low']) / 2
    df['premium_discount_pct'] = ((df['close'] - df['range_low']) / (df['range_high'] - df['range_low']) * 100)
    return df


def identify_choch(df: pd.DataFrame) -> pd.DataFrame:
    """Identify CHoCH (Change of Character) signals"""
    df = df.copy()

    # Track recent swing highs and lows
    df['recent_swing_high'] = df['high'].rolling(20).max()
    df['recent_swing_low'] = df['low'].rolling(20).min()

    df['prev_swing_high'] = df['recent_swing_high'].shift(1)
    df['prev_swing_low'] = df['recent_swing_low'].shift(1)

    # Trend
    df['trend_up'] = df['high'] > df['high'].shift(10)
    df['trend_down'] = df['low'] < df['low'].shift(10)

    # CHoCH: Change of Character (trend reversal)
    df['bullish_choch'] = df['trend_down'].shift(1) & (df['close'] > df['prev_swing_high'])
    df['bearish_choch'] = df['trend_up'].shift(1) & (df['close'] < df['prev_swing_low'])

    return df


def backtest_strategy(df: pd.DataFrame, strategy_name: str, entry_signal: str, direction: str,
                     session_filter: str = None, hour_filter: int = None) -> dict:
    """Backtest a strategy and return results"""

    df = df.copy()

    # Apply session filter
    if session_filter == 'AM_LATE_EARLY':
        df = df[(df['hour'] >= 8) & (df['hour'] < 12)]
    elif hour_filter is not None:
        df = df[df['hour'] == hour_filter]

    # Get entry signals
    signals = df[df[entry_signal]].copy()

    if len(signals) == 0:
        return {
            'strategy': strategy_name,
            'signals': 0,
            'avg_return': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'total_return': 0
        }

    # Calculate returns
    signals['next_close'] = signals.groupby('symbol')['close'].shift(-1)

    if direction == 'long':
        signals['return'] = ((signals['next_close'] - signals['close']) / signals['close'] * 100)
    else:  # short
        signals['return'] = ((signals['close'] - signals['next_close']) / signals['close'] * 100)

    # Remove invalid returns
    signals = signals[signals['return'].notna()]
    signals = signals[~signals['return'].isin([np.inf, -np.inf])]

    if len(signals) == 0:
        return {
            'strategy': strategy_name,
            'signals': 0,
            'avg_return': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'total_return': 0
        }

    # Calculate metrics
    avg_return = signals['return'].mean()
    win_rate = (signals['return'] > 0).mean()

    winning = signals[signals['return'] > 0]['return']
    losing = signals[signals['return'] <= 0]['return']

    if len(winning) > 0 and len(losing) > 0:
        profit_factor = winning.sum() / abs(losing.sum())
    else:
        profit_factor = 0

    total_return = signals['return'].sum()

    return {
        'strategy': strategy_name,
        'signals': len(signals),
        'avg_return': avg_return,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'total_return': total_return
    }


def main():
    parser = argparse.ArgumentParser(description='Backtest ICT strategies on 1-minute data')
    parser.add_argument('--start-date', default='2020-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', default='2025-01-01', help='End date (YYYY-MM-DD)')
    parser.add_argument('--output', default='ict_1min_backtest_results.csv', help='Output CSV file')
    args = parser.parse_args()

    print('=' * 80)
    print('ICT Strategies 1-Minute Data Backtest')
    print('=' * 80)
    print()

    # Load data
    bars = load_nq_1min_bars(args.start_date, args.end_date)

    # Add features
    print('Calculating features...')
    bars = add_time_features(bars)
    bars = calculate_premium_discount(bars)
    bars = identify_choch(bars)

    # Define strategies to test
    strategies = [
        # Bearish CHoCH (all)
        {
            'name': 'Bearish CHoCH (全部)',
            'entry_signal': 'bearish_choch',
            'direction': 'short',
            'session_filter': None,
            'hour_filter': None
        },
        # Bearish CHoCH Hour 14
        {
            'name': 'Bearish CHoCH Hour 14',
            'entry_signal': 'bearish_choch',
            'direction': 'short',
            'session_filter': None,
            'hour_filter': 14
        },
        # Lightglow-style (Premium/Discount + AM session)
        {
            'name': 'Lightglow-style (做多)',
            'entry_signal': 'premium_discount_pct',  # Will need custom logic
            'direction': 'long',
            'session_filter': 'AM_LATE_EARLY',
            'hour_filter': None
        },
        # Bullish CHoCH (for comparison)
        {
            'name': 'Bullish CHoCH (全部)',
            'entry_signal': 'bullish_choch',
            'direction': 'long',
            'session_filter': None,
            'hour_filter': None
        },
    ]

    # Run backtests
    print()
    print('=' * 80)
    print('Running Backtests...')
    print('=' * 80)
    print()

    results = []

    for strategy in strategies:
        if strategy['name'] == 'Lightglow-style (做多)':
            # Special handling for Lightglow
            df_filtered = bars.copy()
            df_filtered = df_filtered[(df_filtered['hour'] >= 8) & (df_filtered['hour'] < 12)]
            df_filtered['entry_signal'] = df_filtered['premium_discount_pct'] < 50

            result = backtest_strategy(
                df_filtered,
                strategy['name'],
                'entry_signal',
                'long',
                None,
                None
            )
        else:
            result = backtest_strategy(
                bars,
                strategy['name'],
                strategy['entry_signal'],
                strategy['direction'],
                strategy['session_filter'],
                strategy['hour_filter']
            )

        results.append(result)

        print(f"{result['strategy']}:")
        print(f"  Signals: {result['signals']:,}")
        print(f"  Avg Return: {result['avg_return']:.4f}%")
        print(f"  Win Rate: {result['win_rate']:.1%}")
        print(f"  Profit Factor: {result['profit_factor']:.2f}")
        print(f"  Total Return: {result['total_return']:.2f}%")
        print()

    # Save results
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('profit_factor', ascending=False)
    results_df.to_csv(args.output, index=False)

    print('=' * 80)
    print('Results Summary')
    print('=' * 80)
    print()
    print(results_df.to_string(index=False))
    print()
    print(f'Results saved to {args.output}')


if __name__ == '__main__':
    main()
