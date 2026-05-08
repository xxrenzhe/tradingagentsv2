#!/usr/bin/env python3
"""
全面策略回测 - 1分钟数据 2010-2026
使用真实历史数据，分块处理大数据集
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json

print('=' * 80)
print('全面策略回测 - 1分钟数据 2010-2026')
print('=' * 80)
print()

# Load 1-minute data
print('加载1分钟数据...')
data_file = 'data/raw/databento/glbx-mdp3-20100606-20260427.ohlcv-1m.csv'

# Read in chunks to handle large file
chunk_size = 1000000
chunks = []
total_rows = 0

for chunk in pd.read_csv(data_file, chunksize=chunk_size):
    total_rows += len(chunk)
    chunks.append(chunk)
    print(f'  已加载 {total_rows:,} 行...')

df = pd.concat(chunks, ignore_index=True)
print(f'总共加载: {len(df):,} 行')
print()

# Parse timestamp
df['timestamp'] = pd.to_datetime(df['ts_event'], unit='ns', utc=True)
df = df.sort_values('timestamp').reset_index(drop=True)

print(f'时间范围: {df["timestamp"].min()} 到 {df["timestamp"].max()}')
print()

# Clean data
print('清理数据...')
original_len = len(df)

# Remove negative/zero prices
df = df[(df['close'] > 0) & (df['open'] > 0) & (df['high'] > 0) & (df['low'] > 0)]
print(f'  移除负价格: {original_len - len(df):,} 行')

# Calculate returns
df['next_close'] = df['close'].shift(-1)
df['return_long_pct'] = ((df['next_close'] - df['close']) / df['close'] * 100)
df['return_short_pct'] = ((df['close'] - df['next_close']) / df['close'] * 100)

# Remove inf/nan
df = df[~df['return_long_pct'].isin([np.inf, -np.inf, np.nan])]
df = df[~df['return_short_pct'].isin([np.inf, -np.inf, np.nan])]

# Filter extreme returns (likely data errors)
before_filter = len(df)
df = df[(df['return_long_pct'] > -20) & (df['return_long_pct'] < 20)]
df = df[(df['return_short_pct'] > -20) & (df['return_short_pct'] < 20)]
print(f'  过滤极端值 (±20%): {before_filter - len(df):,} 行')
print(f'  最终有效数据: {len(df):,} 行')
print()

# Calculate indicators (in chunks to save memory)
print('计算技术指标...')

def calculate_indicators_chunk(chunk_df):
    """Calculate indicators for a chunk"""
    chunk_df = chunk_df.copy()

    # Premium/Discount
    lookback = 100
    chunk_df['trailing_high'] = chunk_df['high'].rolling(lookback, min_periods=1).max()
    chunk_df['trailing_low'] = chunk_df['low'].rolling(lookback, min_periods=1).min()
    chunk_df['range_size'] = chunk_df['trailing_high'] - chunk_df['trailing_low']
    chunk_df['premium_level'] = chunk_df['trailing_low'] + 0.95 * chunk_df['range_size']
    chunk_df['discount_level'] = chunk_df['trailing_low'] + 0.05 * chunk_df['range_size']
    chunk_df['in_premium'] = chunk_df['close'] >= chunk_df['premium_level']
    chunk_df['in_discount'] = chunk_df['close'] <= chunk_df['discount_level']

    # CHoCH
    chunk_df['recent_swing_high'] = chunk_df['high'].rolling(20, min_periods=1).max()
    chunk_df['recent_swing_low'] = chunk_df['low'].rolling(20, min_periods=1).min()
    chunk_df['prev_swing_high'] = chunk_df['recent_swing_high'].shift(1)
    chunk_df['prev_swing_low'] = chunk_df['recent_swing_low'].shift(1)
    chunk_df['trend_up'] = chunk_df['high'] > chunk_df['high'].shift(10)
    chunk_df['trend_down'] = chunk_df['low'] < chunk_df['low'].shift(10)
    chunk_df['bullish_choch'] = chunk_df['trend_down'].shift(1) & (chunk_df['close'] > chunk_df['prev_swing_high'])
    chunk_df['bearish_choch'] = chunk_df['trend_up'].shift(1) & (chunk_df['close'] < chunk_df['prev_swing_low'])

    # BOS
    chunk_df['bullish_bos'] = chunk_df['trend_up'].shift(1) & (chunk_df['close'] > chunk_df['prev_swing_high'])
    chunk_df['bearish_bos'] = chunk_df['trend_down'].shift(1) & (chunk_df['close'] < chunk_df['prev_swing_low'])

    return chunk_df

# Process in chunks
chunk_size = 500000
processed_chunks = []

for i in range(0, len(df), chunk_size):
    chunk = df.iloc[i:i+chunk_size].copy()
    chunk = calculate_indicators_chunk(chunk)
    processed_chunks.append(chunk)
    print(f'  已处理 {min(i+chunk_size, len(df)):,} / {len(df):,} 行')

df = pd.concat(processed_chunks, ignore_index=True)
print('指标计算完成')
print()

# Backtest function
def backtest_strategy(name, signals_df, return_col):
    """Backtest a strategy"""
    if len(signals_df) == 0:
        return None

    signals_df = signals_df.sort_values('timestamp').copy()
    returns = signals_df[return_col]

    # Basic stats
    avg_return = returns.mean()
    win_rate = (returns > 0).mean()

    winning = returns[returns > 0]
    losing = returns[returns <= 0]

    if len(winning) > 0 and len(losing) > 0:
        profit_factor = winning.sum() / abs(losing.sum())
    else:
        profit_factor = 0

    # Sample equity curve (use every 100th trade to save memory)
    sample_size = min(10000, len(signals_df))
    sample_indices = np.linspace(0, len(signals_df)-1, sample_size, dtype=int)
    sample_returns = returns.iloc[sample_indices]

    equity = 10000 * (1 + sample_returns / 100).cumprod()
    total_return = (equity.iloc[-1] - 10000) / 10000 * 100

    # Max drawdown
    peak = equity.expanding().max()
    drawdown = (equity - peak) / peak * 100
    max_drawdown = drawdown.min()

    # Sharpe
    sharpe = returns.mean() / returns.std() * np.sqrt(252 * 390) if returns.std() > 0 else 0  # 390 minutes per trading day

    return {
        'name': name,
        'signals': len(signals_df),
        'avg_return': avg_return,
        'win_rate': win_rate * 100,
        'profit_factor': profit_factor,
        'total_return': total_return,
        'final_equity': equity.iloc[-1],
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe
    }

# Test strategies
strategies = []

print('回测策略...')
print()

# 1. Bearish CHoCH
print('1. Bearish CHoCH...')
result = backtest_strategy('Bearish CHoCH', df[df['bearish_choch']], 'return_short_pct')
if result:
    strategies.append(result)
    print(f"   PF: {result['profit_factor']:.2f}, 信号: {result['signals']:,}, 总收益: {result['total_return']:.2f}%")

# 2. Bullish CHoCH
print('2. Bullish CHoCH...')
result = backtest_strategy('Bullish CHoCH', df[df['bullish_choch']], 'return_long_pct')
if result:
    strategies.append(result)
    print(f"   PF: {result['profit_factor']:.2f}, 信号: {result['signals']:,}, 总收益: {result['total_return']:.2f}%")

# 3. Premium/Discount Long
print('3. Premium/Discount Long...')
result = backtest_strategy('Premium/Discount Long', df[df['in_discount']], 'return_long_pct')
if result:
    strategies.append(result)
    print(f"   PF: {result['profit_factor']:.2f}, 信号: {result['signals']:,}, 总收益: {result['total_return']:.2f}%")

# 4. Premium/Discount Short
print('4. Premium/Discount Short...')
result = backtest_strategy('Premium/Discount Short', df[df['in_premium']], 'return_short_pct')
if result:
    strategies.append(result)
    print(f"   PF: {result['profit_factor']:.2f}, 信号: {result['signals']:,}, 总收益: {result['total_return']:.2f}%")

# 5. Bearish BOS
print('5. Bearish BOS...')
result = backtest_strategy('Bearish BOS', df[df['bearish_bos']], 'return_short_pct')
if result:
    strategies.append(result)
    print(f"   PF: {result['profit_factor']:.2f}, 信号: {result['signals']:,}, 总收益: {result['total_return']:.2f}%")

# 6. Bullish BOS
print('6. Bullish BOS...')
result = backtest_strategy('Bullish BOS', df[df['bullish_bos']], 'return_long_pct')
if result:
    strategies.append(result)
    print(f"   PF: {result['profit_factor']:.2f}, 信号: {result['signals']:,}, 总收益: {result['total_return']:.2f}%")

print()
print('=' * 80)
print('策略汇总 (按盈利因子排序)')
print('=' * 80)
print()

results_df = pd.DataFrame(strategies)
results_df = results_df.sort_values('profit_factor', ascending=False)

print(f"{'策略':<30} {'PF':<8} {'信号数':<12} {'平均%':<10} {'胜率%':<8} {'总收益%':<12} {'最终$':<14} {'回撤%':<10} {'夏普':<8} {'状态'}")
print('-' * 135)

for idx, row in results_df.iterrows():
    status = "✅" if row['profit_factor'] > 1.0 and row['total_return'] > 0 else "❌"
    print(f"{row['name']:<30} {row['profit_factor']:<8.2f} {row['signals']:<12,} {row['avg_return']:<10.4f} {row['win_rate']:<8.1f} {row['total_return']:<12.2f} ${row['final_equity']:<13,.0f} {row['max_drawdown']:<10.2f} {row['sharpe_ratio']:<8.2f} {status}")

print()

# Save results
results_df.to_csv('reports/comprehensive_backtest_1min_2010_2026.csv', index=False)
print('已保存: reports/comprehensive_backtest_1min_2010_2026.csv')

# Save summary
summary = {
    'period': '2010-2026',
    'timeframe': '1-minute',
    'total_bars': int(len(df)),
    'date_range': {
        'start': df['timestamp'].min().strftime('%Y-%m-%d'),
        'end': df['timestamp'].max().strftime('%Y-%m-%d')
    },
    'strategies': results_df.to_dict('records')
}

with open('reports/comprehensive_backtest_1min_2010_2026.json', 'w') as f:
    json.dump(summary, f, indent=2)

print('已保存: reports/comprehensive_backtest_1min_2010_2026.json')
print()
print('完成！')
