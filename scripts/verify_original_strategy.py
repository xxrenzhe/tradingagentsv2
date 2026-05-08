#!/usr/bin/env python3
"""
Verify Original Strategy Parameters

Check if original strategy uses ATR filter or other filters
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


def _atr(high, low, close, period=14):
    """Calculate ATR"""
    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    tr[0] = tr1[0]

    atr = np.zeros_like(tr)
    atr[period-1] = np.mean(tr[:period])

    for i in range(period, len(tr)):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period

    return atr


def main():
    print("Checking original strategy parameters...")
    print()

    # Load original trades
    orig_trades = pd.read_csv('.tmp/signals_trades.csv')
    print(f"Original trades: {len(orig_trades):,}")
    print(f"Date range: {orig_trades['entry_ts'].min()} to {orig_trades['entry_ts'].max()}")
    print()

    # Load bars and generate signals
    print("Loading bars...")
    args = type('Args', (), {
        'start_date': '2022-10-25',
        'end_date': '2026-04-28',
        'min_volume': 0,
        'cache': '.cache/nq_bars.pkl',
        'chunk_size': 100000,
    })()

    bars = load_continuous_nq_bars(args)
    bars = resample_ohlcv(bars, 1)
    bars = build_lightglow_signals(bars)

    # Calculate ATR
    high = bars["High"].to_numpy(dtype=float)
    low = bars["Low"].to_numpy(dtype=float)
    close = bars["Close"].to_numpy(dtype=float)
    atr = _atr(high, low, close, period=14)
    bars['atr'] = atr

    # Count signals with different ATR thresholds
    signal = bars["premium_discount_reversal"]
    total_signals = (signal != 0).sum()

    print(f"Total signals (no filter): {total_signals:,}")
    print()

    print("Testing ATR thresholds:")
    for threshold in [0, 5, 8, 10, 12, 15, 20]:
        atr_filter = bars['atr'] > threshold
        filtered_signals = ((signal != 0) & atr_filter).sum()
        ratio = filtered_signals / total_signals if total_signals > 0 else 0
        match = "✅ MATCH!" if abs(filtered_signals - len(orig_trades)) < 1000 else ""
        print(f"  ATR > {threshold:>2}: {filtered_signals:>7,} signals ({ratio:>5.1%}) {match}")

    print()
    print("Checking for other filters...")

    # Check if there's a volume filter
    print(f"Min volume in bars: {bars['Volume'].min()}")
    print(f"Max volume in bars: {bars['Volume'].max()}")

    # Check signal distribution
    print()
    print("Signal distribution:")
    print(f"  Long signals: {(signal > 0).sum():,}")
    print(f"  Short signals: {(signal < 0).sum():,}")
    print(f"  Total: {(signal != 0).sum():,}")


if __name__ == '__main__':
    main()
