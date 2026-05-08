#!/usr/bin/env python3
"""
全面策略回测 - 1分钟数据 2010-2026
考虑交易成本、滑点、市场冲击等真实因素
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json

print('=' * 80)
print('全面策略回测 - 1分钟数据 2010-2026 (考虑交易成本)')
print('=' * 80)
print()

# Trading costs configuration
COMMISSION_RATE = 0.0002  # 0.02% per trade (round trip = 0.04%)
SLIPPAGE_BPS = 1.0  # 1 basis point = 0.01%
MARKET_IMPACT_BPS = 0.5  # 0.5 basis point for small orders

TOTAL_COST_PER_TRADE = (COMMISSION_RATE * 2 * 100 +  # Round trip commission
                        SLIPPAGE_BPS * 2 +  # Entry + exit slippage
                        MARKET_IMPACT_BPS)  # Market impact

print(f'交易成本配置:')
print(f'  手续费: {COMMISSION_RATE*100:.3f}% (单边), {COMMISSION_RATE*2*100:.3f}% (往返)')
print(f'  滑点: {SLIPPAGE_BPS:.1f} bps (单边), {SLIPPAGE_BPS*2:.1f} bps (往返)')
print(f'  市场冲击: {MARKET_IMPACT_BPS:.1f} bps')
print(f'  总成本: {TOTAL_COST_PER_TRADE:.2f} bps = {TOTAL_COST_PER_TRADE/100:.4f}%')
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

# Apply trading costs
df['return_long_after_costs'] = df['return_long_pct'] - (TOTAL_COST_PER_TRADE / 100)
df['return_short_after_costs'] = df['return_short_pct'] - (TOTAL_COST_PER_TRADE / 100)

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
def backtest_strategy(name, signals_df, return_col_before, return_col_after):
    """Backtest a strategy with and without costs"""
    if len(signals_df) == 0:
        return None

    signals_df = signals_df.sort_values('timestamp').copy()

    # Before costs
    returns_before = signals_df[return_col_before]
    avg_return_before = returns_before.mean()
    win_rate_before = (returns_before > 0).mean()

    winning_before = returns_before[returns_before > 0]
    losing_before = returns_before[returns_before <= 0]

    if len(winning_before) > 0 and len(losing_before) > 0:
        profit_factor_before = winning_before.sum() / abs(losing_before.sum())
    else:
        profit_factor_before = 0

    # After costs
    returns_after = signals_df[return_col_after]
    avg_return_after = returns_after.mean()
    win_rate_after = (returns_after > 0).mean()

    winning_after = returns_after[returns_after > 0]
    losing_after = returns_after[returns_after <= 0]

    if len(winning_after) > 0 and len(losing_after) > 0:
        profit_factor_after = winning_after.sum() / abs(losing_after.sum())
    else:
        profit_factor_after = 0

    # Sample equity curve (use every 100th trade to save memory)
    sample_size = min(10000, len(signals_df))
    sample_indices = np.linspace(0, len(signals_df)-1, sample_size, dtype=int)

    # Before costs
    sample_returns_before = returns_before.iloc[sample_indices]
    equity_before = 10000 * (1 + sample_returns_before / 100).cumprod()
    total_return_before = (equity_before.iloc[-1] - 10000) / 10000 * 100

    # After costs
    sample_returns_after = returns_after.iloc[sample_indices]
    equity_after = 10000 * (1 + sample_returns_after / 100).cumprod()
    total_return_after = (equity_after.iloc[-1] - 10000) / 10000 * 100

    # Max drawdown (after costs)
    peak = equity_after.expanding().max()
    drawdown = (equity_after - peak) / peak * 100
    max_drawdown = drawdown.min()

    # Sharpe (after costs)
    sharpe = returns_after.mean() / returns_after.std() * np.sqrt(252 * 390) if returns_after.std() > 0 else 0

    # Total costs
    total_cost_pct = TOTAL_COST_PER_TRADE / 100
    total_costs = len(signals_df) * total_cost_pct

    return {
        'name': name,
        'signals': len(signals_df),

        # Before costs
        'avg_return_before': avg_return_before,
        'win_rate_before': win_rate_before * 100,
        'profit_factor_before': profit_factor_before,
        'total_return_before': total_return_before,
        'final_equity_before': equity_before.iloc[-1],

        # After costs
        'avg_return_after': avg_return_after,
        'win_rate_after': win_rate_after * 100,
        'profit_factor_after': profit_factor_after,
        'total_return_after': total_return_after,
        'final_equity_after': equity_after.iloc[-1],
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe,

        # Costs
        'total_costs_pct': total_costs,
        'cost_per_trade_pct': total_cost_pct
    }

# Test strategies
strategies = []

print('回测策略...')
print()

# 1. Premium/Discount Long
print('1. Premium/Discount Long...')
result = backtest_strategy('Premium/Discount Long',
                          df[df['in_discount']],
                          'return_long_pct',
                          'return_long_after_costs')
if result:
    strategies.append(result)
    print(f"   无成本: PF {result['profit_factor_before']:.2f}, 总收益 {result['total_return_before']:.2f}%")
    print(f"   有成本: PF {result['profit_factor_after']:.2f}, 总收益 {result['total_return_after']:.2f}%")

# 2. Premium/Discount Short
print('2. Premium/Discount Short...')
result = backtest_strategy('Premium/Discount Short',
                          df[df['in_premium']],
                          'return_short_pct',
                          'return_short_after_costs')
if result:
    strategies.append(result)
    print(f"   无成本: PF {result['profit_factor_before']:.2f}, 总收益 {result['total_return_before']:.2f}%")
    print(f"   有成本: PF {result['profit_factor_after']:.2f}, 总收益 {result['total_return_after']:.2f}%")

# 3. Bearish CHoCH
print('3. Bearish CHoCH...')
result = backtest_strategy('Bearish CHoCH',
                          df[df['bearish_choch']],
                          'return_short_pct',
                          'return_short_after_costs')
if result:
    strategies.append(result)
    print(f"   无成本: PF {result['profit_factor_before']:.2f}, 总收益 {result['total_return_before']:.2f}%")
    print(f"   有成本: PF {result['profit_factor_after']:.2f}, 总收益 {result['total_return_after']:.2f}%")

# 4. Bullish CHoCH
print('4. Bullish CHoCH...')
result = backtest_strategy('Bullish CHoCH',
                          df[df['bullish_choch']],
                          'return_long_pct',
                          'return_long_after_costs')
if result:
    strategies.append(result)
    print(f"   无成本: PF {result['profit_factor_before']:.2f}, 总收益 {result['total_return_before']:.2f}%")
    print(f"   有成本: PF {result['profit_factor_after']:.2f}, 总收益 {result['total_return_after']:.2f}%")

# 5. Bearish BOS
print('5. Bearish BOS...')
result = backtest_strategy('Bearish BOS',
                          df[df['bearish_bos']],
                          'return_short_pct',
                          'return_short_after_costs')
if result:
    strategies.append(result)
    print(f"   无成本: PF {result['profit_factor_before']:.2f}, 总收益 {result['total_return_before']:.2f}%")
    print(f"   有成本: PF {result['profit_factor_after']:.2f}, 总收益 {result['total_return_after']:.2f}%")

# 6. Bullish BOS
print('6. Bullish BOS...')
result = backtest_strategy('Bullish BOS',
                          df[df['bullish_bos']],
                          'return_long_pct',
                          'return_long_after_costs')
if result:
    strategies.append(result)
    print(f"   无成本: PF {result['profit_factor_before']:.2f}, 总收益 {result['total_return_before']:.2f}%")
    print(f"   有成本: PF {result['profit_factor_after']:.2f}, 总收益 {result['total_return_after']:.2f}%")

print()
print('=' * 80)
print('策略汇总 (按考虑成本后的盈利因子排序)')
print('=' * 80)
print()

results_df = pd.DataFrame(strategies)
results_df = results_df.sort_values('profit_factor_after', ascending=False)

print(f"{'策略':<30} {'信号数':<10} {'成本前PF':<10} {'成本后PF':<10} {'成本前收益%':<15} {'成本后收益%':<15} {'最终$':<15} {'状态'}")
print('-' * 130)

for idx, row in results_df.iterrows():
    status = "✅" if row['profit_factor_after'] > 1.0 and row['total_return_after'] > 0 else "❌"
    print(f"{row['name']:<30} {row['signals']:<10,} {row['profit_factor_before']:<10.2f} {row['profit_factor_after']:<10.2f} "
          f"{row['total_return_before']:<15.2f} {row['total_return_after']:<15.2f} ${row['final_equity_after']:<14,.0f} {status}")

print()
print('成本影响分析:')
print('-' * 80)
for idx, row in results_df.iterrows():
    pf_impact = ((row['profit_factor_after'] - row['profit_factor_before']) / row['profit_factor_before'] * 100) if row['profit_factor_before'] > 0 else -100
    return_impact = row['total_return_after'] - row['total_return_before']
    print(f"{row['name']:<30}")
    print(f"  盈利因子: {row['profit_factor_before']:.2f} → {row['profit_factor_after']:.2f} ({pf_impact:+.1f}%)")
    print(f"  总收益: {row['total_return_before']:.2f}% → {row['total_return_after']:.2f}% ({return_impact:+.2f}%)")
    print(f"  总成本: {row['total_costs_pct']:.2f}% ({row['signals']:,}笔 × {row['cost_per_trade_pct']:.4f}%)")
    print()

# Save results
results_df.to_csv('reports/comprehensive_backtest_1min_with_costs.csv', index=False)
print('已保存: reports/comprehensive_backtest_1min_with_costs.csv')

# Save summary
summary = {
    'period': '2010-2026',
    'timeframe': '1-minute',
    'total_bars': int(len(df)),
    'trading_costs': {
        'commission_rate': COMMISSION_RATE,
        'slippage_bps': SLIPPAGE_BPS,
        'market_impact_bps': MARKET_IMPACT_BPS,
        'total_cost_per_trade_bps': TOTAL_COST_PER_TRADE,
        'total_cost_per_trade_pct': TOTAL_COST_PER_TRADE / 100
    },
    'date_range': {
        'start': df['timestamp'].min().strftime('%Y-%m-%d'),
        'end': df['timestamp'].max().strftime('%Y-%m-%d')
    },
    'strategies': results_df.to_dict('records')
}

with open('reports/comprehensive_backtest_1min_with_costs.json', 'w') as f:
    json.dump(summary, f, indent=2)

print('已保存: reports/comprehensive_backtest_1min_with_costs.json')
print()
print('完成！')
