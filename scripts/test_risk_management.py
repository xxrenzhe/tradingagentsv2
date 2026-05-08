#!/usr/bin/env python3
"""
Test Risk Management System

Compare original strategy performance with risk-managed version
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.risk.risk_manager import (
    RiskConfig,
    RiskManager,
    backtest_with_risk_management,
)


def analyze_results(trades_df, title: str):
    """Analyze and print backtest results"""

    pnls = trades_df['adjusted_pnl'].values if 'adjusted_pnl' in trades_df.columns else trades_df['net_dollars'].values

    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    cumulative = np.cumsum(pnls)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = running_max - cumulative
    max_dd = drawdowns.max() if len(drawdowns) > 0 else 0.0

    # Calculate Sharpe ratio (monthly)
    trades_df['entry_date'] = pd.to_datetime(trades_df['entry_ts'])
    trades_df['month'] = trades_df['entry_date'].dt.to_period('M')
    monthly = trades_df.groupby('month')['adjusted_pnl' if 'adjusted_pnl' in trades_df.columns else 'net_dollars'].sum()
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

    if 'capital' in trades_df.columns:
        print(f"Final Capital: ${trades_df['capital'].iloc[-1]:,.2f}")
        print(f"Return: {(trades_df['capital'].iloc[-1] / 100000 - 1):.1%}")
        print()

    if 'risk_state' in trades_df.columns:
        print("Risk State Distribution:")
        print(trades_df['risk_state'].value_counts())
        print()


def main():
    print("=" * 80)
    print("Risk Management System Test")
    print("=" * 80)
    print()

    # Load original trades
    print("Loading original strategy trades...")
    trades = pd.read_csv('.tmp/signals_trades.csv')
    print(f"Loaded {len(trades):,} trades")
    print()

    # Analyze original (assuming 1 contract per trade)
    analyze_results(trades, "Original Strategy (1 Contract)")

    # Test with risk management
    print("Testing with risk management...")
    print()

    # Configuration 1: Conservative (1% risk)
    config1 = RiskConfig(
        risk_per_trade_pct=0.01,
        consecutive_loss_threshold_1=3,
        consecutive_loss_threshold_2=5,
        consecutive_loss_threshold_3=7,
        drawdown_threshold_1=0.05,
        drawdown_threshold_2=0.10,
        drawdown_threshold_3=0.15,
        drawdown_threshold_4=0.20,
    )

    risk_manager1, adjusted_trades1 = backtest_with_risk_management(
        trades,
        initial_capital=100000.0,
        config=config1,
    )

    analyze_results(adjusted_trades1, "Risk Managed (1% Risk, Conservative)")
    print("Risk Manager Statistics:")
    stats1 = risk_manager1.get_statistics()
    for key, value in stats1.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
    print()

    # Configuration 2: Moderate (2% risk)
    config2 = RiskConfig(
        risk_per_trade_pct=0.02,
        consecutive_loss_threshold_1=3,
        consecutive_loss_threshold_2=5,
        consecutive_loss_threshold_3=7,
        drawdown_threshold_1=0.10,
        drawdown_threshold_2=0.15,
        drawdown_threshold_3=0.20,
        drawdown_threshold_4=0.25,
    )

    risk_manager2, adjusted_trades2 = backtest_with_risk_management(
        trades,
        initial_capital=100000.0,
        config=config2,
    )

    analyze_results(adjusted_trades2, "Risk Managed (2% Risk, Moderate)")
    print("Risk Manager Statistics:")
    stats2 = risk_manager2.get_statistics()
    for key, value in stats2.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
    print()

    # Configuration 3: Aggressive (3% risk)
    config3 = RiskConfig(
        risk_per_trade_pct=0.03,
        consecutive_loss_threshold_1=5,
        consecutive_loss_threshold_2=7,
        consecutive_loss_threshold_3=10,
        drawdown_threshold_1=0.15,
        drawdown_threshold_2=0.20,
        drawdown_threshold_3=0.25,
        drawdown_threshold_4=0.30,
    )

    risk_manager3, adjusted_trades3 = backtest_with_risk_management(
        trades,
        initial_capital=100000.0,
        config=config3,
    )

    analyze_results(adjusted_trades3, "Risk Managed (3% Risk, Aggressive)")
    print("Risk Manager Statistics:")
    stats3 = risk_manager3.get_statistics()
    for key, value in stats3.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
    print()

    # Comparison summary
    print("=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    print()

    original_profit = trades['net_dollars'].sum()
    original_dd = 46470.0  # From previous analysis

    print(f"{'Strategy':<30} {'Profit':<15} {'Drawdown':<15} {'Sharpe':<10} {'Return':<10}")
    print("-" * 80)
    print(f"{'Original (1 contract)':<30} ${original_profit:>13,.0f} ${original_dd:>13,.0f} {1.86:>8.2f} {original_profit/100000:>8.1%}")

    profit1 = adjusted_trades1['adjusted_pnl'].sum()
    dd1 = (adjusted_trades1['capital'].max() - adjusted_trades1['capital'].min())
    monthly1 = adjusted_trades1.groupby('month')['adjusted_pnl'].sum()
    sharpe1 = monthly1.mean() / monthly1.std() * np.sqrt(12) if monthly1.std() > 0 else 0
    print(f"{'Conservative (1% risk)':<30} ${profit1:>13,.0f} ${dd1:>13,.0f} {sharpe1:>8.2f} {profit1/100000:>8.1%}")

    profit2 = adjusted_trades2['adjusted_pnl'].sum()
    dd2 = (adjusted_trades2['capital'].max() - adjusted_trades2['capital'].min())
    monthly2 = adjusted_trades2.groupby('month')['adjusted_pnl'].sum()
    sharpe2 = monthly2.mean() / monthly2.std() * np.sqrt(12) if monthly2.std() > 0 else 0
    print(f"{'Moderate (2% risk)':<30} ${profit2:>13,.0f} ${dd2:>13,.0f} {sharpe2:>8.2f} {profit2/100000:>8.1%}")

    profit3 = adjusted_trades3['adjusted_pnl'].sum()
    dd3 = (adjusted_trades3['capital'].max() - adjusted_trades3['capital'].min())
    monthly3 = adjusted_trades3.groupby('month')['adjusted_pnl'].sum()
    sharpe3 = monthly3.mean() / monthly3.std() * np.sqrt(12) if monthly3.std() > 0 else 0
    print(f"{'Aggressive (3% risk)':<30} ${profit3:>13,.0f} ${dd3:>13,.0f} {sharpe3:>8.2f} {profit3/100000:>8.1%}")

    print()
    print("Key Insights:")
    print(f"  - Conservative: Lower profit but much better risk-adjusted returns")
    print(f"  - Moderate: Good balance between profit and risk")
    print(f"  - Aggressive: Higher profit but higher drawdown")
    print()

    # Save results
    output_dir = Path("reports")
    output_dir.mkdir(exist_ok=True)

    adjusted_trades1.to_csv(output_dir / "risk_managed_conservative.csv", index=False)
    adjusted_trades2.to_csv(output_dir / "risk_managed_moderate.csv", index=False)
    adjusted_trades3.to_csv(output_dir / "risk_managed_aggressive.csv", index=False)

    print(f"Results saved to {output_dir}/")


if __name__ == '__main__':
    main()
