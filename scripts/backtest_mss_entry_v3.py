#!/usr/bin/env python3
"""
MSS Entry V3 - Max Holding Exit (Strong Trends Only)

用户的关键洞察:
===============
"MSS入场+最大持仓出场不是盈利的吗？"

V1测试结果:
- 最大持仓出场: 10,766笔 → +$4,362,385 ✅

这些是什么交易？
- 入场后没有遇到反向MSS
- 一直持仓到最大时间（20根K线）
- 说明这些是"强趋势"交易

策略逻辑:
=========
入场: MSS确认 + Premium/Discount
出场: 只使用最大持仓时间（不检查反向MSS）

这样就能"只做强趋势交易"！
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
from scripts.backtest_mss_entry_strategy import detect_mss_signals
from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts


def build_mss_entry_max_holding_trades(
    frame: pd.DataFrame,
    costs: BacktestCosts,
    mss_lookback: int = 5,
    max_hold_bars: int = 20,
) -> pd.DataFrame:
    """
    MSS入场 + 最大持仓出场（不检查反向MSS）

    这样只做"强趋势"交易
    """

    # 检测MSS信号
    mss_signal = detect_mss_signals(frame, mss_lookback)

    # 获取Premium/Discount信号
    premium_discount_signal = frame["premium_discount_reversal"]

    # 组合入场信号
    entry_signal = np.zeros(len(frame), dtype=int)

    for i in range(len(frame)):
        pd_sig = premium_discount_signal.iloc[i]
        mss_sig = mss_signal.iloc[i]

        # 多头入场: Discount + 看涨MSS
        if pd_sig == -1 and mss_sig == 1:
            entry_signal[i] = 1
        # 空头入场: Premium + 看跌MSS
        elif pd_sig == 1 and mss_sig == -1:
            entry_signal[i] = -1

    entry_indexes = np.flatnonzero(entry_signal != 0)

    if len(entry_indexes) == 0:
        return pd.DataFrame()

    # 提取价格数组
    open_prices = frame["Open"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    timestamps = frame["ts"].to_numpy()
    symbols = frame["symbol"].astype(str).to_numpy()

    rows = []
    next_available_signal_index = 0

    for signal_index in entry_indexes:
        signal_index = int(signal_index)

        # 检查重叠
        if signal_index < next_available_signal_index:
            continue

        entry_index = signal_index + 1

        if entry_index >= len(frame):
            continue

        direction = int(entry_signal[signal_index])
        entry_price = float(open_prices[entry_index])
        entry_symbol = symbols[signal_index]

        # 最大持仓出场（不检查反向MSS）
        exit_index = min(entry_index + max_hold_bars - 1, len(frame) - 1)
        exit_reason = "max_holding"

        # 只检查合约切换
        for i in range(entry_index, exit_index + 1):
            if symbols[i] != entry_symbol:
                exit_index = i - 1 if i > entry_index else entry_index
                exit_reason = "symbol_change"
                break

        # 计算PnL
        exit_price = float(close_prices[exit_index])
        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points

        rows.append({
            "candidate": f"mss_entry_max_holding",
            "signal": "mss_entry",
            "timeframe_minutes": 1,
            "session": "all",
            "holding_minutes": (exit_index - entry_index),
            "direction_mode": "mss",
            "exit_profile": "max_holding",
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


def main():
    import argparse

    print("=" * 80)
    print("MSS Entry V3 - Max Holding Exit (Strong Trends Only)")
    print("=" * 80)
    print()

    # 加载数据
    args = argparse.Namespace(
        start_date="2021-04-28",
        end_date="2026-04-28",
        min_volume=0,
        cache=".cache/nq_bars.pkl",
        chunk_size=100000,
    )

    print("Loading NQ bars...")
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

    print("Building MSS entry + max holding trades...")
    trades = build_mss_entry_max_holding_trades(
        frame=bars,
        costs=costs,
        mss_lookback=5,
        max_hold_bars=20,
    )

    print(f"Generated {len(trades):,} trades")
    print()

    # 计算统计
    if len(trades) > 0:
        pnls = trades['net_dollars'].values
        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]

        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        max_dd = drawdowns.max() if len(drawdowns) > 0 else 0.0

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

        # 对比原始策略
        print("=" * 80)
        print("COMPARISON WITH ORIGINAL STRATEGY")
        print("=" * 80)
        print()
        print("Original Strategy:")
        print("  Trades: 41,720")
        print("  Net Profit: $2,205,060")
        print("  Profit Factor: 1.91")
        print("  Win Rate: 43.1%")
        print()
        print("MSS Entry + Max Holding:")
        print(f"  Trades: {len(trades):,}")
        print(f"  Net Profit: ${pnls.sum():,.2f}")
        print(f"  Profit Factor: {wins.sum() / abs(losses.sum()):.2f}" if len(losses) > 0 else "  Profit Factor: inf")
        print(f"  Win Rate: {len(wins) / len(trades):.1%}")
        print()

        # 保存交易
        output_path = Path("reports/mss_entry_max_holding_trades.csv")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        trades.to_csv(output_path, index=False)
        print(f"Trades saved to: {output_path}")
    else:
        print("No trades generated!")


if __name__ == '__main__':
    main()
