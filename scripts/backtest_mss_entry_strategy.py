#!/usr/bin/env python3
"""
MSS Entry Strategy - Trend Following

基于用户的关键洞察:
"MSS交易是盈利的，那就只做MSS交易"

策略逻辑:
=========

入场条件（全部满足）:
1. 价格刚刚确认MSS（市场结构突破）
   - 多头: 价格突破swing high
   - 空头: 价格突破swing low
2. 价格在Premium/Discount区域
   - 多头: 在Discount区域（价格低于均衡）
   - 空头: 在Premium区域（价格高于均衡）
3. 趋势方向与区域一致
   - Discount + 向上MSS = 做多
   - Premium + 向下MSS = 做空

出场条件（任一满足）:
1. 反向MSS（趋势结束）
2. 最大持仓时间（20根K线）
3. 合约切换

优势:
=====
✅ 只做有趋势确认的交易
✅ 避免震荡市场
✅ 专门捕获趋势核心收益
✅ 不破坏原始反转策略
✅ 可以与反转策略组合使用

预期表现:
=========
基于动态出场测试的MSS交易数据:
- 交易数量: ~20,000笔
- 净利润: +$4M - $5M
- 盈利因子: 2.0+
- 平均持仓: 13根K线
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
    LightglowCandidate,
    build_lightglow_signals,
    resample_ohlcv,
)
from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts


def detect_mss_signals(
    frame: pd.DataFrame,
    lookback: int = 5,
) -> pd.Series:
    """
    检测MSS（市场结构突破）信号

    返回:
        Series: 1=看涨MSS, -1=看跌MSS, 0=无MSS
    """
    high_prices = frame["High"].to_numpy(dtype=float)
    low_prices = frame["Low"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)

    signals = np.zeros(len(frame), dtype=int)

    for i in range(lookback, len(frame)):
        # 计算swing high/low
        lookback_start = i - lookback
        swing_high = high_prices[lookback_start:i].max()
        swing_low = low_prices[lookback_start:i].min()

        current_close = close_prices[i]

        # 看涨MSS: 突破swing high
        if current_close > swing_high:
            signals[i] = 1
        # 看跌MSS: 突破swing low
        elif current_close < swing_low:
            signals[i] = -1

    return pd.Series(signals, index=frame.index)


def build_mss_entry_trades(
    frame: pd.DataFrame,
    costs: BacktestCosts,
    mss_lookback: int = 5,
    max_hold_bars: int = 20,
) -> pd.DataFrame:
    """
    构建MSS入场策略的交易

    Args:
        frame: OHLCV DataFrame with Lightglow signals
        costs: Trading costs
        mss_lookback: MSS检测的lookback周期
        max_hold_bars: 最大持仓时间

    Returns:
        DataFrame of trades
    """

    # 检测MSS信号
    mss_signal = detect_mss_signals(frame, mss_lookback)

    # 获取Premium/Discount信号
    premium_discount_signal = frame["premium_discount_reversal"]

    # 组合入场信号
    # 多头: Discount区域(-1) + 看涨MSS(1) = 做多
    # 空头: Premium区域(1) + 看跌MSS(-1) = 做空
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
    high_prices = frame["High"].to_numpy(dtype=float)
    low_prices = frame["Low"].to_numpy(dtype=float)
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

        # 持仓逻辑: 等待反向MSS或最大持仓时间
        exit_index = None
        exit_reason = "unknown"

        for i in range(entry_index, min(entry_index + max_hold_bars, len(frame))):
            # 检查合约切换
            if symbols[i] != entry_symbol:
                exit_index = i - 1 if i > entry_index else entry_index
                exit_reason = "symbol_change"
                break

            # 计算swing high/low
            if i >= mss_lookback:
                lookback_start = max(0, i - mss_lookback)
                swing_high = high_prices[lookback_start:i].max()
                swing_low = low_prices[lookback_start:i].min()
            else:
                swing_high = None
                swing_low = None

            current_price = close_prices[i]

            # 检查反向MSS
            if swing_high is not None and swing_low is not None:
                if direction > 0 and current_price < swing_low:
                    # 多头遇到看跌MSS
                    exit_index = i
                    exit_reason = "reverse_mss"
                    break
                elif direction < 0 and current_price > swing_high:
                    # 空头遇到看涨MSS
                    exit_index = i
                    exit_reason = "reverse_mss"
                    break

        # 如果没有找到出场点，使用最大持仓时间
        if exit_index is None:
            exit_index = min(entry_index + max_hold_bars - 1, len(frame) - 1)
            exit_reason = "max_holding"

        # 计算PnL
        exit_price = float(close_prices[exit_index])
        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points

        rows.append({
            "candidate": "mss_entry",
            "signal": "mss_entry",
            "timeframe_minutes": 1,
            "session": "all",
            "holding_minutes": (exit_index - entry_index),
            "direction_mode": "mss",
            "exit_profile": "reverse_mss",
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
    print("MSS Entry Strategy - Trend Following")
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

    # 重采样到1分钟
    bars = resample_ohlcv(bars, 1)
    print(f"Resampled to {len(bars):,} bars")
    print()

    # 构建Lightglow信号
    print("Building Lightglow signals...")
    bars = build_lightglow_signals(bars)
    print("Signals built")
    print()

    # 构建MSS入场交易
    print("Building MSS entry trades...")
    costs = BacktestCosts(commission_per_contract=5.0, slippage_ticks_per_side=1.0)
    trades = build_mss_entry_trades(
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

        # 按出场原因统计
        print("Exit Reason Statistics:")
        for reason, count in trades['exit_reason'].value_counts().items():
            reason_trades = trades[trades['exit_reason'] == reason]
            reason_pnl = reason_trades['net_dollars'].sum()
            print(f"  {reason}: {count:,} trades (${reason_pnl:,.2f})")
        print()

        # 保存交易
        output_path = Path("reports/mss_entry_trades.csv")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        trades.to_csv(output_path, index=False)
        print(f"Trades saved to: {output_path}")
    else:
        print("No trades generated!")


if __name__ == '__main__':
    main()
