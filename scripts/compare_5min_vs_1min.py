#!/usr/bin/env python3
"""
Compare 5-minute Kill Zone results with 1-minute full data results
"""

import pandas as pd
import numpy as np

print('=' * 80)
print('5-Minute vs 1-Minute Backtest Comparison')
print('=' * 80)
print()

# 5-minute Kill Zone results (from our tests)
results_5min = [
    {
        'strategy': 'Bearish CHoCH Hour 14',
        'timeframe': '5-min Kill Zone',
        'profit_factor': 5.50,
        'avg_return': 0.7117,
        'win_rate': 40.6,
        'signals': 96,
        'period': '2022-2026 (4 years)'
    },
    {
        'strategy': 'Bearish CHoCH (全部)',
        'timeframe': '5-min Kill Zone',
        'profit_factor': 4.92,
        'avg_return': 1.1839,
        'win_rate': 47.3,
        'signals': 1362,
        'period': '2022-2026 (4 years)'
    },
    {
        'strategy': 'Lightglow KZ-4',
        'timeframe': '5-min Kill Zone',
        'profit_factor': 1.42,
        'avg_return': None,
        'win_rate': None,
        'signals': None,
        'period': '2022-2026 (4 years)'
    },
    {
        'strategy': 'Bullish Sweep + Supply POI',
        'timeframe': '5-min Kill Zone',
        'profit_factor': 1.37,
        'avg_return': 0.1206,
        'win_rate': 48.2,
        'signals': 110,
        'period': '2022-2026 (4 years)'
    },
]

df_5min = pd.DataFrame(results_5min)

print('5-Minute Kill Zone Results (2022-2026):')
print('=' * 80)
print()
print(df_5min.to_string(index=False))
print()
print()

# Load 1-minute results
try:
    df_1min = pd.read_csv('reports/ict_1min_backtest_results.csv')
    df_1min['timeframe'] = '1-min Full'
    df_1min['period'] = '2020-2025 (5 years)'

    print('1-Minute Full Data Results (2020-2025):')
    print('=' * 80)
    print()
    print(df_1min.to_string(index=False))
    print()
    print()

    # Comparison
    print('=' * 80)
    print('Key Comparisons')
    print('=' * 80)
    print()

    # Compare Bearish CHoCH
    choch_5min = df_5min[df_5min['strategy'] == 'Bearish CHoCH (全部)'].iloc[0]
    choch_1min = df_1min[df_1min['strategy'] == 'Bearish CHoCH (全部)'].iloc[0] if 'Bearish CHoCH (全部)' in df_1min['strategy'].values else None

    if choch_1min is not None:
        print('Bearish CHoCH (全部):')
        print(f'  5-min Kill Zone: PF {choch_5min["profit_factor"]:.2f}, {choch_5min["signals"]} signals')
        print(f'  1-min Full:      PF {choch_1min["profit_factor"]:.2f}, {choch_1min["signals"]} signals')
        print(f'  Difference:      {choch_1min["profit_factor"] - choch_5min["profit_factor"]:.2f}')
        print()

    # Compare Bearish CHoCH Hour 14
    choch14_5min = df_5min[df_5min['strategy'] == 'Bearish CHoCH Hour 14'].iloc[0]
    choch14_1min = df_1min[df_1min['strategy'] == 'Bearish CHoCH Hour 14'].iloc[0] if 'Bearish CHoCH Hour 14' in df_1min['strategy'].values else None

    if choch14_1min is not None:
        print('Bearish CHoCH Hour 14:')
        print(f'  5-min Kill Zone: PF {choch14_5min["profit_factor"]:.2f}, {choch14_5min["signals"]} signals')
        print(f'  1-min Full:      PF {choch14_1min["profit_factor"]:.2f}, {choch14_1min["signals"]} signals')
        print(f'  Difference:      {choch14_1min["profit_factor"] - choch14_5min["profit_factor"]:.2f}')
        print()

    # Overall insights
    print('=' * 80)
    print('Insights')
    print('=' * 80)
    print()

    print('1. Timeframe Impact:')
    print('   - 5-min data: Fewer signals, potentially higher quality')
    print('   - 1-min data: More signals, more noise')
    print()

    print('2. Data Period:')
    print('   - 5-min: 2022-2026 (4 years, Kill Zone only)')
    print('   - 1-min: 2020-2025 (5 years, full day)')
    print()

    print('3. Signal Count:')
    print('   - 5-min has fewer signals due to Kill Zone filter')
    print('   - 1-min has more signals (full day trading)')
    print()

    # Recommendations
    print('=' * 80)
    print('Recommendations')
    print('=' * 80)
    print()

    best_1min = df_1min.loc[df_1min['profit_factor'].idxmax()]

    print(f'Best 1-min strategy: {best_1min["strategy"]}')
    print(f'  Profit Factor: {best_1min["profit_factor"]:.2f}')
    print(f'  Avg Return: {best_1min["avg_return"]:.4f}%')
    print(f'  Win Rate: {best_1min["win_rate"]:.1%}')
    print(f'  Signals: {best_1min["signals"]:,.0f}')
    print()

    if best_1min['profit_factor'] > choch_5min['profit_factor']:
        print('✅ 1-minute strategy outperforms 5-minute!')
        print('   Consider using 1-minute timeframe')
    else:
        print('⚠️ 5-minute strategy still better')
        print('   Stick with 5-minute Kill Zone approach')

except FileNotFoundError:
    print('⏳ 1-minute backtest results not yet available')
    print('   Waiting for backtest to complete...')
except Exception as e:
    print(f'Error loading 1-minute results: {e}')
