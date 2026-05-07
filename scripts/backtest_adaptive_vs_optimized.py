#!/usr/bin/env python3
"""
Backtest Adaptive vs Optimized Strategy

Compare performance of:
1. Optimized strategy (time + volatility filters)
2. Adaptive strategy (ADX-based regime switching)

Using local Databento 1-minute bar data (2010-2026)
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
import pytz
from pathlib import Path
import json

# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_PATH = Path("data/raw/databento/glbx-mdp3-20100606-20260427.ohlcv-1m.csv")
BACKTEST_START = "2020-01-01"
BACKTEST_END = "2026-05-07"

INITIAL_CAPITAL = 25000
COMMISSION_PER_TRADE = 5  # $5 per round-trip
SLIPPAGE_POINTS = 2
POINT_VALUE = 20  # $20 per point for NQ

# Strategy Parameters
LOOKBACK_LENGTH = 100
PREMIUM_THRESHOLD = 0.95
DISCOUNT_THRESHOLD = 0.05
EXIT_BARS = 2

# Optimized Strategy Parameters
ATR_LENGTH = 14
ATR_THRESHOLD = 8.0
MAX_TRADES_PER_DAY = 50
DAILY_LOSS_LIMIT = 400  # points

# Adaptive Strategy Parameters
ADX_LENGTH = 14
ADX_THRESHOLD = 25.0
STOP_LOSS_POINTS = 50.0
MAX_CONSECUTIVE_LOSSES = 3
PAUSE_MINUTES = 30

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_data():
    """Load and prepare NQ 1-minute bar data"""
    print(f"Loading data from {DATA_PATH}...")

    df = pd.read_csv(DATA_PATH)

    # Parse timestamp
    df['timestamp'] = pd.to_datetime(df['ts_event'])
    df = df.set_index('timestamp')

    # Filter for backtest period
    df = df.loc[BACKTEST_START:BACKTEST_END]

    # Filter out spread contracts (contain '-')
    df = df[~df['symbol'].str.contains('-', na=False)]

    print(f"After removing spreads: {len(df):,} bars")
    print(f"Symbols: {sorted(df['symbol'].unique())}")

    # Build continuous contract by selecting front month at each time
    # Group by timestamp and select the contract with highest volume
    print("Building continuous contract from front month...")
    df_continuous = df.loc[df.groupby(df.index)['volume'].idxmax()]

    # Detect and handle contract rollovers
    # When symbol changes, check for price jumps
    df_continuous['symbol_changed'] = df_continuous['symbol'] != df_continuous['symbol'].shift(1)
    df_continuous['price_jump'] = abs(df_continuous['close'] - df_continuous['close'].shift(1))

    # Mark rollover points (symbol change + large price jump > 100 points)
    df_continuous['is_rollover'] = (df_continuous['symbol_changed']) & (df_continuous['price_jump'] > 100)

    rollover_count = df_continuous['is_rollover'].sum()
    print(f"Detected {rollover_count} contract rollovers")

    # For backtesting, we'll skip trading during rollover bars and the next 5 bars
    # to avoid artificial profits from price jumps
    df_continuous['skip_rollover'] = False
    rollover_indices = df_continuous[df_continuous['is_rollover']].index
    for idx in rollover_indices:
        # Find position in index
        try:
            idx_pos = df_continuous.index.get_loc(idx)
            if isinstance(idx_pos, slice):
                idx_pos = idx_pos.start
            # Skip this bar and next 5 bars
            end_pos = min(idx_pos + 6, len(df_continuous))
            skip_indices = df_continuous.index[idx_pos:end_pos]
            df_continuous.loc[skip_indices, 'skip_rollover'] = True
        except:
            pass

    print(f"Continuous contract: {len(df_continuous):,} bars from {df_continuous.index[0]} to {df_continuous.index[-1]}")
    print(f"Skipping {df_continuous['skip_rollover'].sum()} bars around rollovers")

    return df_continuous

def calculate_atr(high, low, close, period=14):
    """Calculate Average True Range"""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def calculate_adx(high, low, close, period=14):
    """Calculate Average Directional Index"""
    # Calculate directional movement
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)

    # Smooth DM
    plus_dm_smooth = plus_dm.rolling(window=period).mean()
    minus_dm_smooth = minus_dm.rolling(window=period).mean()

    # Calculate ATR for DI
    atr = calculate_atr(high, low, close, period)

    # Calculate Directional Indicators
    plus_di = 100 * plus_dm_smooth / atr
    minus_di = 100 * minus_dm_smooth / atr

    # Calculate DX and ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()

    return adx

def is_kill_zone(timestamp):
    """Check if timestamp is in kill zone (NY AM or NY PM)"""
    est = pytz.timezone('America/New_York')
    # Data is already in UTC, just convert
    if timestamp.tz is None:
        ts_est = timestamp.tz_localize('UTC').tz_convert(est)
    else:
        ts_est = timestamp.tz_convert(est)
    t = ts_est.time()

    # NY AM: 8:30-11:30
    ny_am = time(8, 30) <= t <= time(11, 30)

    # NY PM: 13:30-16:00
    ny_pm = time(13, 30) <= t <= time(16, 0)

    return ny_am or ny_pm

# ============================================================================
# STRATEGY 1: OPTIMIZED (TIME + VOLATILITY FILTERS)
# ============================================================================

def backtest_optimized(df):
    """Backtest optimized strategy with time and volatility filters"""
    print("\n" + "="*80)
    print("BACKTESTING: OPTIMIZED STRATEGY (Time + Volatility Filters)")
    print("="*80)

    # Prepare data
    data = df.copy()

    # Calculate indicators
    data['trailing_high'] = data['high'].rolling(window=LOOKBACK_LENGTH).max()
    data['trailing_low'] = data['low'].rolling(window=LOOKBACK_LENGTH).min()
    data['range'] = data['trailing_high'] - data['trailing_low']
    data['premium_level'] = data['trailing_low'] + PREMIUM_THRESHOLD * data['range']
    data['discount_level'] = data['trailing_low'] + DISCOUNT_THRESHOLD * data['range']

    data['in_premium'] = data['close'] > data['premium_level']
    data['in_discount'] = data['close'] < data['discount_level']

    # ATR filter
    data['atr'] = calculate_atr(data['high'], data['low'], data['close'], ATR_LENGTH)
    data['atr_filter'] = data['atr'] > ATR_THRESHOLD

    # Time filter
    data['kill_zone'] = data.index.map(is_kill_zone)

    # Drop NaN rows
    data = data.dropna()

    # Initialize tracking variables
    position = 0  # 1 = long, -1 = short, 0 = flat
    entry_price = 0
    entry_bar = 0
    trades = []
    equity = INITIAL_CAPITAL
    equity_curve = []

    trades_today = 0
    daily_pnl = 0
    last_date = None

    # Run backtest
    for i, (timestamp, row) in enumerate(data.iterrows()):
        current_date = timestamp.date()

        # Reset daily counters
        if current_date != last_date:
            trades_today = 0
            daily_pnl = 0
            last_date = current_date

        # Check exit conditions
        if position != 0:
            bars_in_trade = i - entry_bar

            # Time-based exit
            if bars_in_trade >= EXIT_BARS:
                exit_price = row['close']
                pnl_points = (exit_price - entry_price) * position - SLIPPAGE_POINTS
                pnl_dollars = pnl_points * POINT_VALUE - COMMISSION_PER_TRADE

                equity += pnl_dollars
                daily_pnl += pnl_points

                trades.append({
                    'entry_time': data.index[entry_bar],
                    'exit_time': timestamp,
                    'direction': 'Long' if position > 0 else 'Short',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl_points': pnl_points,
                    'pnl_dollars': pnl_dollars,
                    'exit_reason': 'Time'
                })

                position = 0

        equity_curve.append({'timestamp': timestamp, 'equity': equity})

        # Check entry conditions
        if position == 0:
            # Skip rollover periods
            if row.get('skip_rollover', False):
                continue

            # Check filters
            if not row['kill_zone']:
                continue
            if not row['atr_filter']:
                continue
            if trades_today >= MAX_TRADES_PER_DAY:
                continue
            if daily_pnl <= -DAILY_LOSS_LIMIT:
                continue

            # Entry signals (REVERSAL logic)
            if row['in_premium']:
                # Short signal
                position = -1
                entry_price = row['close']
                entry_bar = i
                trades_today += 1
            elif row['in_discount']:
                # Long signal
                position = 1
                entry_price = row['close']
                entry_bar = i
                trades_today += 1

    # Close any open position at end
    if position != 0:
        exit_price = data.iloc[-1]['close']
        pnl_points = (exit_price - entry_price) * position - SLIPPAGE_POINTS
        pnl_dollars = pnl_points * POINT_VALUE - COMMISSION_PER_TRADE
        equity += pnl_dollars

        trades.append({
            'entry_time': data.index[entry_bar],
            'exit_time': data.index[-1],
            'direction': 'Long' if position > 0 else 'Short',
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl_points': pnl_points,
            'pnl_dollars': pnl_dollars,
            'exit_reason': 'End'
        })

    return trades, equity_curve

# ============================================================================
# STRATEGY 2: ADAPTIVE (ADX-BASED REGIME SWITCHING)
# ============================================================================

def backtest_adaptive(df):
    """Backtest adaptive strategy with ADX-based regime switching"""
    print("\n" + "="*80)
    print("BACKTESTING: ADAPTIVE STRATEGY (ADX-Based Regime Switching)")
    print("="*80)

    # Prepare data
    data = df.copy()

    # Calculate indicators
    data['trailing_high'] = data['high'].rolling(window=LOOKBACK_LENGTH).max()
    data['trailing_low'] = data['low'].rolling(window=LOOKBACK_LENGTH).min()
    data['range'] = data['trailing_high'] - data['trailing_low']
    data['premium_level'] = data['trailing_low'] + PREMIUM_THRESHOLD * data['range']
    data['discount_level'] = data['trailing_low'] + DISCOUNT_THRESHOLD * data['range']

    data['in_premium'] = data['close'] > data['premium_level']
    data['in_discount'] = data['close'] < data['discount_level']

    # ATR filter
    data['atr'] = calculate_atr(data['high'], data['low'], data['close'], ATR_LENGTH)
    data['atr_filter'] = data['atr'] > ATR_THRESHOLD

    # ADX for regime detection
    data['adx'] = calculate_adx(data['high'], data['low'], data['close'], ADX_LENGTH)
    data['is_trending'] = data['adx'] > ADX_THRESHOLD

    # Time filter
    data['kill_zone'] = data.index.map(is_kill_zone)

    # Drop NaN rows
    data = data.dropna()

    # Initialize tracking variables
    position = 0
    entry_price = 0
    entry_bar = 0
    trades = []
    equity = INITIAL_CAPITAL
    equity_curve = []

    trades_today = 0
    daily_pnl = 0
    last_date = None
    consecutive_losses = 0
    pause_until = None

    # Run backtest
    for i, (timestamp, row) in enumerate(data.iterrows()):
        current_date = timestamp.date()

        # Reset daily counters
        if current_date != last_date:
            trades_today = 0
            daily_pnl = 0
            last_date = current_date

        # Check if paused
        if pause_until and timestamp < pause_until:
            equity_curve.append({'timestamp': timestamp, 'equity': equity})
            continue
        else:
            pause_until = None

        # Check exit conditions
        if position != 0:
            bars_in_trade = i - entry_bar

            # Dynamic stop loss
            if position > 0:
                stop_price = entry_price - STOP_LOSS_POINTS
                if row['close'] <= stop_price:
                    exit_price = row['close']
                    pnl_points = (exit_price - entry_price) - SLIPPAGE_POINTS
                    pnl_dollars = pnl_points * POINT_VALUE - COMMISSION_PER_TRADE

                    equity += pnl_dollars
                    daily_pnl += pnl_points

                    if pnl_dollars < 0:
                        consecutive_losses += 1
                    else:
                        consecutive_losses = 0

                    trades.append({
                        'entry_time': data.index[entry_bar],
                        'exit_time': timestamp,
                        'direction': 'Long',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_points': pnl_points,
                        'pnl_dollars': pnl_dollars,
                        'exit_reason': 'Stop Loss'
                    })

                    position = 0

                    # Check consecutive losses
                    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
                        pause_until = timestamp + pd.Timedelta(minutes=PAUSE_MINUTES)
                        consecutive_losses = 0

            elif position < 0:
                stop_price = entry_price + STOP_LOSS_POINTS
                if row['close'] >= stop_price:
                    exit_price = row['close']
                    pnl_points = (entry_price - exit_price) - SLIPPAGE_POINTS
                    pnl_dollars = pnl_points * POINT_VALUE - COMMISSION_PER_TRADE

                    equity += pnl_dollars
                    daily_pnl += pnl_points

                    if pnl_dollars < 0:
                        consecutive_losses += 1
                    else:
                        consecutive_losses = 0

                    trades.append({
                        'entry_time': data.index[entry_bar],
                        'exit_time': timestamp,
                        'direction': 'Short',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_points': pnl_points,
                        'pnl_dollars': pnl_dollars,
                        'exit_reason': 'Stop Loss'
                    })

                    position = 0

                    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
                        pause_until = timestamp + pd.Timedelta(minutes=PAUSE_MINUTES)
                        consecutive_losses = 0

            # Time-based exit
            if position != 0 and bars_in_trade >= EXIT_BARS:
                exit_price = row['close']
                pnl_points = (exit_price - entry_price) * position - SLIPPAGE_POINTS
                pnl_dollars = pnl_points * POINT_VALUE - COMMISSION_PER_TRADE

                equity += pnl_dollars
                daily_pnl += pnl_points

                if pnl_dollars < 0:
                    consecutive_losses += 1
                else:
                    consecutive_losses = 0

                trades.append({
                    'entry_time': data.index[entry_bar],
                    'exit_time': timestamp,
                    'direction': 'Long' if position > 0 else 'Short',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl_points': pnl_points,
                    'pnl_dollars': pnl_dollars,
                    'exit_reason': 'Time'
                })

                position = 0

                if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
                    pause_until = timestamp + pd.Timedelta(minutes=PAUSE_MINUTES)
                    consecutive_losses = 0

        equity_curve.append({'timestamp': timestamp, 'equity': equity})

        # Check entry conditions
        if position == 0:
            # Skip rollover periods
            if row.get('skip_rollover', False):
                continue

            # Check filters
            if not row['kill_zone']:
                continue
            if not row['atr_filter']:
                continue
            if trades_today >= MAX_TRADES_PER_DAY:
                continue
            if daily_pnl <= -DAILY_LOSS_LIMIT:
                continue

            # ADAPTIVE LOGIC: Switch based on ADX
            if row['is_trending']:
                # TREND FOLLOWING: breakout logic
                if row['in_premium']:
                    # Long signal (momentum up)
                    position = 1
                    entry_price = row['close']
                    entry_bar = i
                    trades_today += 1
                elif row['in_discount']:
                    # Short signal (momentum down)
                    position = -1
                    entry_price = row['close']
                    entry_bar = i
                    trades_today += 1
            else:
                # MEAN REVERSION: fade logic
                if row['in_premium']:
                    # Short signal (fade expensive)
                    position = -1
                    entry_price = row['close']
                    entry_bar = i
                    trades_today += 1
                elif row['in_discount']:
                    # Long signal (fade cheap)
                    position = 1
                    entry_price = row['close']
                    entry_bar = i
                    trades_today += 1

    # Close any open position at end
    if position != 0:
        exit_price = data.iloc[-1]['close']
        pnl_points = (exit_price - entry_price) * position - SLIPPAGE_POINTS
        pnl_dollars = pnl_points * POINT_VALUE - COMMISSION_PER_TRADE
        equity += pnl_dollars

        trades.append({
            'entry_time': data.index[entry_bar],
            'exit_time': data.index[-1],
            'direction': 'Long' if position > 0 else 'Short',
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl_points': pnl_points,
            'pnl_dollars': pnl_dollars,
            'exit_reason': 'End'
        })

    return trades, equity_curve

# ============================================================================
# PERFORMANCE ANALYSIS
# ============================================================================

def analyze_performance(trades, equity_curve, strategy_name):
    """Calculate performance metrics"""
    if not trades:
        print(f"\n{strategy_name}: No trades executed!")
        return None

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_curve)

    # Basic metrics
    total_trades = len(trades_df)
    winning_trades = len(trades_df[trades_df['pnl_dollars'] > 0])
    losing_trades = len(trades_df[trades_df['pnl_dollars'] < 0])

    win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0

    total_profit = trades_df[trades_df['pnl_dollars'] > 0]['pnl_dollars'].sum()
    total_loss = abs(trades_df[trades_df['pnl_dollars'] < 0]['pnl_dollars'].sum())

    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

    net_profit = trades_df['pnl_dollars'].sum()

    avg_win = total_profit / winning_trades if winning_trades > 0 else 0
    avg_loss = total_loss / losing_trades if losing_trades > 0 else 0

    # Drawdown
    equity_df['peak'] = equity_df['equity'].cummax()
    equity_df['drawdown'] = equity_df['equity'] - equity_df['peak']
    max_drawdown = equity_df['drawdown'].min()
    max_drawdown_pct = (max_drawdown / INITIAL_CAPITAL) * 100

    # Sharpe ratio (simplified)
    returns = trades_df['pnl_dollars'] / INITIAL_CAPITAL
    sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0

    metrics = {
        'strategy': strategy_name,
        'net_profit': net_profit,
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'max_drawdown': max_drawdown,
        'max_drawdown_pct': max_drawdown_pct,
        'sharpe_ratio': sharpe,
        'final_equity': equity_df.iloc[-1]['equity']
    }

    return metrics, trades_df, equity_df

def print_comparison(metrics1, metrics2):
    """Print side-by-side comparison"""
    print("\n" + "="*80)
    print("PERFORMANCE COMPARISON")
    print("="*80)

    print(f"\n{'Metric':<30} {'Optimized':<20} {'Adaptive':<20} {'Change':<15}")
    print("-" * 85)

    # Net Profit
    opt_profit = metrics1['net_profit']
    adp_profit = metrics2['net_profit']
    change = ((adp_profit - opt_profit) / opt_profit * 100) if opt_profit != 0 else 0
    print(f"{'Net Profit':<30} ${opt_profit:>18,.0f} ${adp_profit:>18,.0f} {change:>13.1f}%")

    # Profit Factor
    opt_pf = metrics1['profit_factor']
    adp_pf = metrics2['profit_factor']
    change = ((adp_pf - opt_pf) / opt_pf * 100) if opt_pf != 0 else 0
    print(f"{'Profit Factor':<30} {opt_pf:>20.2f} {adp_pf:>20.2f} {change:>13.1f}%")

    # Win Rate
    opt_wr = metrics1['win_rate']
    adp_wr = metrics2['win_rate']
    change = adp_wr - opt_wr
    print(f"{'Win Rate':<30} {opt_wr:>19.1f}% {adp_wr:>19.1f}% {change:>13.1f}%")

    # Max Drawdown
    opt_dd = metrics1['max_drawdown']
    adp_dd = metrics2['max_drawdown']
    change = ((adp_dd - opt_dd) / opt_dd * 100) if opt_dd != 0 else 0
    print(f"{'Max Drawdown':<30} ${opt_dd:>18,.0f} ${adp_dd:>18,.0f} {change:>13.1f}%")

    # Total Trades
    opt_trades = metrics1['total_trades']
    adp_trades = metrics2['total_trades']
    change = ((adp_trades - opt_trades) / opt_trades * 100) if opt_trades != 0 else 0
    print(f"{'Total Trades':<30} {opt_trades:>20,} {adp_trades:>20,} {change:>13.1f}%")

    # Sharpe Ratio
    opt_sharpe = metrics1['sharpe_ratio']
    adp_sharpe = metrics2['sharpe_ratio']
    change = ((adp_sharpe - opt_sharpe) / opt_sharpe * 100) if opt_sharpe != 0 else 0
    print(f"{'Sharpe Ratio':<30} {opt_sharpe:>20.2f} {adp_sharpe:>20.2f} {change:>13.1f}%")

    print("\n" + "="*80)

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("="*80)
    print("LIGHTGLOW STRATEGY BACKTEST: ADAPTIVE VS OPTIMIZED")
    print("="*80)
    print(f"Period: {BACKTEST_START} to {BACKTEST_END}")
    print(f"Initial Capital: ${INITIAL_CAPITAL:,}")
    print(f"Commission: ${COMMISSION_PER_TRADE} per round-trip")
    print(f"Slippage: {SLIPPAGE_POINTS} points")

    # Load data
    df = load_data()

    # Backtest both strategies
    trades_opt, equity_opt = backtest_optimized(df)
    trades_adp, equity_adp = backtest_adaptive(df)

    # Analyze performance
    metrics_opt, trades_df_opt, equity_df_opt = analyze_performance(
        trades_opt, equity_opt, "Optimized"
    )
    metrics_adp, trades_df_adp, equity_df_adp = analyze_performance(
        trades_adp, equity_adp, "Adaptive"
    )

    # Print comparison
    print_comparison(metrics_opt, metrics_adp)

    # Save results
    output_dir = Path("reports/backtest_results")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save trades
    trades_df_opt.to_csv(output_dir / f"trades_optimized_{timestamp}.csv", index=False)
    trades_df_adp.to_csv(output_dir / f"trades_adaptive_{timestamp}.csv", index=False)

    # Save equity curves
    equity_df_opt.to_csv(output_dir / f"equity_optimized_{timestamp}.csv", index=False)
    equity_df_adp.to_csv(output_dir / f"equity_adaptive_{timestamp}.csv", index=False)

    # Save metrics
    with open(output_dir / f"metrics_{timestamp}.json", 'w') as f:
        json.dump({
            'optimized': metrics_opt,
            'adaptive': metrics_adp
        }, f, indent=2, default=str)

    print(f"\nResults saved to {output_dir}/")
    print("\nBacktest complete!")

if __name__ == "__main__":
    main()
