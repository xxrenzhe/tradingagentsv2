#!/usr/bin/env python3
"""
全面策略回测 - 使用真实历史数据
参考Lightglow V2回测周期: 2022-2026
数据源: 5分钟Kill Zone数据
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json

print('=' * 80)
print('全面策略回测 - 真实历史数据')
print('=' * 80)
print()
print('回测周期: 2022-2026 (与Lightglow V2相同)')
print('数据源: 5分钟Kill Zone数据')
print('初始资金: $10,000')
print()

# Load 5-minute Kill Zone data
print('加载数据...')
kz = pd.read_csv('.tmp/kz_candlestick_patterns.csv')
kz['timestamp'] = pd.to_datetime(kz['timestamp'], utc=True)
kz = kz.sort_values(['symbol', 'timestamp']).reset_index(drop=True)

print(f'总K线数: {len(kz):,}')
print(f'时间范围: {kz["timestamp"].min()} 到 {kz["timestamp"].max()}')
print()

# Calculate technical indicators
def calculate_indicators(df):
    """Calculate all technical indicators"""
    df = df.copy()

    # Premium/Discount
    lookback = 100
    df['trailing_high'] = df['high'].rolling(lookback).max()
    df['trailing_low'] = df['low'].rolling(lookback).min()
    df['range_size'] = df['trailing_high'] - df['trailing_low']
    df['premium_level'] = df['trailing_low'] + 0.95 * df['range_size']
    df['discount_level'] = df['trailing_low'] + 0.05 * df['range_size']
    df['in_premium'] = df['close'] >= df['premium_level']
    df['in_discount'] = df['close'] <= df['discount_level']

    # CHoCH
    df['recent_swing_high'] = df['high'].rolling(20).max()
    df['recent_swing_low'] = df['low'].rolling(20).min()
    df['prev_swing_high'] = df['recent_swing_high'].shift(1)
    df['prev_swing_low'] = df['recent_swing_low'].shift(1)
    df['trend_up'] = df['high'] > df['high'].shift(10)
    df['trend_down'] = df['low'] < df['low'].shift(10)
    df['bullish_choch'] = df['trend_down'].shift(1) & (df['close'] > df['prev_swing_high'])
    df['bearish_choch'] = df['trend_up'].shift(1) & (df['close'] < df['prev_swing_low'])

    # BOS
    df['bullish_bos'] = df['trend_up'].shift(1) & (df['close'] > df['prev_swing_high'])
    df['bearish_bos'] = df['trend_down'].shift(1) & (df['close'] < df['prev_swing_low'])

    # Hour
    df['hour'] = df['timestamp'].dt.hour

    return df

print('计算技术指标...')
kz_list = []
for symbol in kz['symbol'].unique():
    symbol_df = kz[kz['symbol'] == symbol].copy()
    symbol_df = calculate_indicators(symbol_df)
    kz_list.append(symbol_df)

kz = pd.concat(kz_list).sort_values('timestamp').reset_index(drop=True)

# Calculate forward returns
kz['next_close'] = kz.groupby('symbol')['close'].shift(-1)
kz['forward_return_long'] = ((kz['next_close'] - kz['close']) / kz['close'] * 100)
kz['forward_return_short'] = ((kz['close'] - kz['next_close']) / kz['close'] * 100)

# Remove inf values
kz = kz[~kz['forward_return_long'].isin([np.inf, -np.inf])]
kz = kz[~kz['forward_return_short'].isin([np.inf, -np.inf])]

print('指标计算完成')
print()

# Define strategies
strategies = []

# 1. Bearish CHoCH (All Hours)
print('=' * 80)
print('策略1: Bearish CHoCH (全部小时)')
print('=' * 80)

bearish_choch_all = kz[kz['bearish_choch'] & kz['forward_return_short'].notna()].copy()
signals = len(bearish_choch_all)
avg_return = bearish_choch_all['forward_return_short'].mean()
win_rate = (bearish_choch_all['forward_return_short'] > 0).mean()

winning = bearish_choch_all[bearish_choch_all['forward_return_short'] > 0]['forward_return_short']
losing = bearish_choch_all[bearish_choch_all['forward_return_short'] <= 0]['forward_return_short']
profit_factor = winning.sum() / abs(losing.sum()) if len(winning) > 0 and len(losing) > 0 else 0

# Calculate equity curve
bearish_choch_all = bearish_choch_all.sort_values('timestamp').reset_index(drop=True)
bearish_choch_all['cumulative_return'] = (1 + bearish_choch_all['forward_return_short'] / 100).cumprod()
bearish_choch_all['equity'] = 10000 * bearish_choch_all['cumulative_return']
total_return = (bearish_choch_all['equity'].iloc[-1] - 10000) / 10000 * 100

max_equity = bearish_choch_all['equity'].expanding().max()
drawdown = (bearish_choch_all['equity'] - max_equity) / max_equity * 100
max_drawdown = drawdown.min()

print(f'信号数: {signals:,}')
print(f'平均收益: {avg_return:.4f}%')
print(f'胜率: {win_rate:.1%}')
print(f'盈利因子: {profit_factor:.2f}')
print(f'总收益: {total_return:.2f}%')
print(f'最大回撤: {max_drawdown:.2f}%')
print()

strategies.append({
    'name': 'Bearish CHoCH (全部小时)',
    'signals': signals,
    'avg_return': avg_return,
    'win_rate': win_rate * 100,
    'profit_factor': profit_factor,
    'total_return': total_return,
    'max_drawdown': max_drawdown
})

# 2. Bullish CHoCH (All Hours)
print('=' * 80)
print('策略2: Bullish CHoCH (全部小时)')
print('=' * 80)

bullish_choch_all = kz[kz['bullish_choch'] & kz['forward_return_long'].notna()].copy()
signals = len(bullish_choch_all)
avg_return = bullish_choch_all['forward_return_long'].mean()
win_rate = (bullish_choch_all['forward_return_long'] > 0).mean()

winning = bullish_choch_all[bullish_choch_all['forward_return_long'] > 0]['forward_return_long']
losing = bullish_choch_all[bullish_choch_all['forward_return_long'] <= 0]['forward_return_long']
profit_factor = winning.sum() / abs(losing.sum()) if len(winning) > 0 and len(losing) > 0 else 0

bullish_choch_all = bullish_choch_all.sort_values('timestamp').reset_index(drop=True)
bullish_choch_all['cumulative_return'] = (1 + bullish_choch_all['forward_return_long'] / 100).cumprod()
bullish_choch_all['equity'] = 10000 * bullish_choch_all['cumulative_return']
total_return = (bullish_choch_all['equity'].iloc[-1] - 10000) / 10000 * 100

max_equity = bullish_choch_all['equity'].expanding().max()
drawdown = (bullish_choch_all['equity'] - max_equity) / max_equity * 100
max_drawdown = drawdown.min()

print(f'信号数: {signals:,}')
print(f'平均收益: {avg_return:.4f}%')
print(f'胜率: {win_rate:.1%}')
print(f'盈利因子: {profit_factor:.2f}')
print(f'总收益: {total_return:.2f}%')
print(f'最大回撤: {max_drawdown:.2f}%')
print()

strategies.append({
    'name': 'Bullish CHoCH (全部小时)',
    'signals': signals,
    'avg_return': avg_return,
    'win_rate': win_rate * 100,
    'profit_factor': profit_factor,
    'total_return': total_return,
    'max_drawdown': max_drawdown
})

# 3. Premium/Discount Long (Discount区域做多)
print('=' * 80)
print('策略3: Premium/Discount Long (Discount区域做多)')
print('=' * 80)

pd_long = kz[kz['in_discount'] & kz['forward_return_long'].notna()].copy()
signals = len(pd_long)
avg_return = pd_long['forward_return_long'].mean()
win_rate = (pd_long['forward_return_long'] > 0).mean()

winning = pd_long[pd_long['forward_return_long'] > 0]['forward_return_long']
losing = pd_long[pd_long['forward_return_long'] <= 0]['forward_return_long']
profit_factor = winning.sum() / abs(losing.sum()) if len(winning) > 0 and len(losing) > 0 else 0

pd_long = pd_long.sort_values('timestamp').reset_index(drop=True)
pd_long['cumulative_return'] = (1 + pd_long['forward_return_long'] / 100).cumprod()
pd_long['equity'] = 10000 * pd_long['cumulative_return']
total_return = (pd_long['equity'].iloc[-1] - 10000) / 10000 * 100

max_equity = pd_long['equity'].expanding().max()
drawdown = (pd_long['equity'] - max_equity) / max_equity * 100
max_drawdown = drawdown.min()

print(f'信号数: {signals:,}')
print(f'平均收益: {avg_return:.4f}%')
print(f'胜率: {win_rate:.1%}')
print(f'盈利因子: {profit_factor:.2f}')
print(f'总收益: {total_return:.2f}%')
print(f'最大回撤: {max_drawdown:.2f}%')
print()

strategies.append({
    'name': 'Premium/Discount Long',
    'signals': signals,
    'avg_return': avg_return,
    'win_rate': win_rate * 100,
    'profit_factor': profit_factor,
    'total_return': total_return,
    'max_drawdown': max_drawdown
})

# 4. Premium/Discount Short (Premium区域做空)
print('=' * 80)
print('策略4: Premium/Discount Short (Premium区域做空)')
print('=' * 80)

pd_short = kz[kz['in_premium'] & kz['forward_return_short'].notna()].copy()
signals = len(pd_short)
avg_return = pd_short['forward_return_short'].mean()
win_rate = (pd_short['forward_return_short'] > 0).mean()

winning = pd_short[pd_short['forward_return_short'] > 0]['forward_return_short']
losing = pd_short[pd_short['forward_return_short'] <= 0]['forward_return_short']
profit_factor = winning.sum() / abs(losing.sum()) if len(winning) > 0 and len(losing) > 0 else 0

pd_short = pd_short.sort_values('timestamp').reset_index(drop=True)
pd_short['cumulative_return'] = (1 + pd_short['forward_return_short'] / 100).cumprod()
pd_short['equity'] = 10000 * pd_short['cumulative_return']
total_return = (pd_short['equity'].iloc[-1] - 10000) / 10000 * 100

max_equity = pd_short['equity'].expanding().max()
drawdown = (pd_short['equity'] - max_equity) / max_equity * 100
max_drawdown = drawdown.min()

print(f'信号数: {signals:,}')
print(f'平均收益: {avg_return:.4f}%')
print(f'胜率: {win_rate:.1%}')
print(f'盈利因子: {profit_factor:.2f}')
print(f'总收益: {total_return:.2f}%')
print(f'最大回撤: {max_drawdown:.2f}%')
print()

strategies.append({
    'name': 'Premium/Discount Short',
    'signals': signals,
    'avg_return': avg_return,
    'win_rate': win_rate * 100,
    'profit_factor': profit_factor,
    'total_return': total_return,
    'max_drawdown': max_drawdown
})

# 5. Bearish BOS
print('=' * 80)
print('策略5: Bearish BOS (延续信号做空)')
print('=' * 80)

bearish_bos = kz[kz['bearish_bos'] & kz['forward_return_short'].notna()].copy()
signals = len(bearish_bos)
avg_return = bearish_bos['forward_return_short'].mean()
win_rate = (bearish_bos['forward_return_short'] > 0).mean()

winning = bearish_bos[bearish_bos['forward_return_short'] > 0]['forward_return_short']
losing = bearish_bos[bearish_bos['forward_return_short'] <= 0]['forward_return_short']
profit_factor = winning.sum() / abs(losing.sum()) if len(winning) > 0 and len(losing) > 0 else 0

bearish_bos = bearish_bos.sort_values('timestamp').reset_index(drop=True)
bearish_bos['cumulative_return'] = (1 + bearish_bos['forward_return_short'] / 100).cumprod()
bearish_bos['equity'] = 10000 * bearish_bos['cumulative_return']
total_return = (bearish_bos['equity'].iloc[-1] - 10000) / 10000 * 100

max_equity = bearish_bos['equity'].expanding().max()
drawdown = (bearish_bos['equity'] - max_equity) / max_equity * 100
max_drawdown = drawdown.min()

print(f'信号数: {signals:,}')
print(f'平均收益: {avg_return:.4f}%')
print(f'胜率: {win_rate:.1%}')
print(f'盈利因子: {profit_factor:.2f}')
print(f'总收益: {total_return:.2f}%')
print(f'最大回撤: {max_drawdown:.2f}%')
print()

strategies.append({
    'name': 'Bearish BOS',
    'signals': signals,
    'avg_return': avg_return,
    'win_rate': win_rate * 100,
    'profit_factor': profit_factor,
    'total_return': total_return,
    'max_drawdown': max_drawdown
})

# 6. Bullish BOS
print('=' * 80)
print('策略6: Bullish BOS (延续信号做多)')
print('=' * 80)

bullish_bos = kz[kz['bullish_bos'] & kz['forward_return_long'].notna()].copy()
signals = len(bullish_bos)
avg_return = bullish_bos['forward_return_long'].mean()
win_rate = (bullish_bos['forward_return_long'] > 0).mean()

winning = bullish_bos[bullish_bos['forward_return_long'] > 0]['forward_return_long']
losing = bullish_bos[bullish_bos['forward_return_long'] <= 0]['forward_return_long']
profit_factor = winning.sum() / abs(losing.sum()) if len(winning) > 0 and len(losing) > 0 else 0

bullish_bos = bullish_bos.sort_values('timestamp').reset_index(drop=True)
bullish_bos['cumulative_return'] = (1 + bullish_bos['forward_return_long'] / 100).cumprod()
bullish_bos['equity'] = 10000 * bullish_bos['cumulative_return']
total_return = (bullish_bos['equity'].iloc[-1] - 10000) / 10000 * 100

max_equity = bullish_bos['equity'].expanding().max()
drawdown = (bullish_bos['equity'] - max_equity) / max_equity * 100
max_drawdown = drawdown.min()

print(f'信号数: {signals:,}')
print(f'平均收益: {avg_return:.4f}%')
print(f'胜率: {win_rate:.1%}')
print(f'盈利因子: {profit_factor:.2f}')
print(f'总收益: {total_return:.2f}%')
print(f'最大回撤: {max_drawdown:.2f}%')
print()

strategies.append({
    'name': 'Bullish BOS',
    'signals': signals,
    'avg_return': avg_return,
    'win_rate': win_rate * 100,
    'profit_factor': profit_factor,
    'total_return': total_return,
    'max_drawdown': max_drawdown
})

# Summary
print('=' * 80)
print('策略汇总 (按盈利因子排序)')
print('=' * 80)
print()

df_strategies = pd.DataFrame(strategies)
df_strategies = df_strategies.sort_values('profit_factor', ascending=False)

print(f"{'策略':<35} {'盈利因子':<10} {'信号数':<10} {'平均收益':<12} {'胜率':<10} {'总收益':<12} {'最大回撤':<12}")
print('-' * 110)

for idx, row in df_strategies.iterrows():
    print(f"{row['name']:<35} {row['profit_factor']:<10.2f} {row['signals']:<10,} {row['avg_return']:<12.4f}% {row['win_rate']:<10.1f}% {row['total_return']:<12.2f}% {row['max_drawdown']:<12.2f}%")

print()

# Save results
df_strategies.to_csv('reports/comprehensive_backtest_results.csv', index=False)
print('已保存: reports/comprehensive_backtest_results.csv')
print()

print('完成！')
