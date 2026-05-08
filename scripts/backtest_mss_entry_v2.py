#!/usr/bin/env python3
"""
MSS Entry Strategy V2 - Fixed Holding Period

关键发现:
=========
V1测试结果显示:
- 反向MSS出场: 38,635笔 → -$5,365,510 ❌
- 最大持仓出场: 10,766笔 → +$4,362,385 ✅

结论: 反向MSS不是好的出场信号！

V2改进:
=======
- 保持MSS入场逻辑 ✅
- 改变出场逻辑: 固定持仓时间
- 测试不同的持仓时间（5, 10, 15, 20根K线）
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


def build_mss_entry_fixed_exit_trades(
    frame: pd.DataFrame,
    costs: BacktestCosts,
    mss_lookback: int = 5,
    hold_bars: int = 10,
) -> pd.DataFrame:
    """
    MSS入场 + 固定持仓时间出场
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

        # 固定持仓时间
        exit_index = min(entry_index + hold_bars - 1, len(frame) - 1)
        exit_reason = "fixed_holding"

        # 检查合约切换
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
            "candidate": f"mss_entry_fixed_{hold_bars}",
            "signal": "mss_entry",
            "timeframe_minutes": 1,
            "session": "all",
            "holding_minutes": (exit_index - entry_index),
            "direction_mode": "mss",
            "exit_profile": f"fixed_{hold_bars}",
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
    print("MSS Entry Strategy V2 - Fixed Holding Period")
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

    # 测试不同的持仓时间
    hold_bars_list = [5, 10, 15, 20]
    results = []

    for hold_bars in hold_bars_list:
        print(f"Testing hold_bars={hold_bars}...")
        trades = build_mss_entry_fixed_exit_trades(
            frame=bars,
            costs=costs,
            mss_lookback=5,
            hold_bars=hold_bars,
        )

        if len(trades) > 0:
            pnls = trades['net_dollars'].values
            wins = pnls[pnls > 0]
            losses = pnls[pnls < 0]

            cumulative = np.cumsum(pnls)
            running_max = np.maximum.accumulate(cumulative)
            drawdowns = running_max - cumulative
            max_dd = drawdowns.max() if len(drawdowns) > 0 else 0.0

            result = {
                "hold_bars": hold_bars,
                "trades": len(trades),
                "net_profit": pnls.sum(),
                "profit_factor": wins.sum() / abs(losses.sum()) if len(losses) > 0 else 999.0,
                "win_rate": len(wins) / len(trades),
                "avg_win": wins.mean() if len(wins) > 0 else 0.0,
                "avg_loss": losses.mean() if len(losses) > 0 else 0.0,
                "max_drawdown": max_dd,
                "avg_bars_held": trades['bars_held'].mean(),
            }
            results.append(result)

            print(f"  Trades: {result['trades']:,}")
            print(f"  Net Profit: ${result['net_profit']:,.2f}")
            print(f"  Profit Factor: {result['profit_factor']:.2f}")
            print(f"  Win Rate: {result['win_rate']:.1%}")
            print()

    # 显示汇总结果
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()

    results_df = pd.DataFrame(results)
    print(results_df.to_string(index=False))
    print()

    # 找到最佳参数
    best = results_df.loc[results_df['net_profit'].idxmax()]
    print(f"Best: hold_bars={int(best['hold_bars'])}, Net Profit=${best['net_profit']:,.2f}")


if __name__ == '__main__':
    main()
