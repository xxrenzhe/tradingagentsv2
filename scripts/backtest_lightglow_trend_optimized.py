"""
Lightglow Trend-Optimized Strategy Backtest

This script implements and backtests an optimized version of the Lightglow strategy
that can capture both mean reversion AND trend following opportunities.

Optimizations:
1. Trend detection using EMA crossover (20/50)
2. Dual-mode strategy:
   - Ranging market: Mean reversion (original logic)
   - Uptrend: Long at Discount (pullback buy)
   - Downtrend: Short at Premium (rally sell)
3. Dynamic exit:
   - Reversal trades: Fast exit (2 bars)
   - Trend trades: Hold longer (5 bars or trend reversal)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts


def resample_ohlcv(features: pd.DataFrame, timeframe_minutes: int) -> pd.DataFrame:
    """Resample OHLCV data to specified timeframe."""
    data = features[["ts", "symbol", "Open", "High", "Low", "Close", "Volume"]].copy()
    data["ts"] = pd.to_datetime(data["ts"], utc=True)

    if timeframe_minutes == 1:
        result = data.sort_values("ts").reset_index(drop=True)
    else:
        aggregations = {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
            "symbol": "last",
        }
        result = (
            data.set_index("ts")
            .resample(f"{timeframe_minutes}min", label="left", closed="left")
            .agg(aggregations)
            .dropna(subset=["Open", "High", "Low", "Close"])
            .reset_index()
        )

    for column in ["Open", "High", "Low", "Close", "Volume"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    result["trade_date"] = result["ts"].dt.date
    result["minute_of_day"] = result["ts"].dt.hour * 60 + result["ts"].dt.minute
    result["timeframe_minutes"] = timeframe_minutes

    return result.dropna(subset=["Open", "High", "Low", "Close"]).reset_index(drop=True)


BULLISH = 1
BEARISH = -1
NEUTRAL = 0


@dataclass
class TrendOptimizedConfig:
    """Configuration for trend-optimized strategy."""

    # Premium/Discount parameters
    lookback: int = 100
    premium_threshold: float = 0.95
    discount_threshold: float = 0.05

    # Trend detection parameters
    ema_fast_period: int = 20
    ema_slow_period: int = 50
    trend_threshold: float = 0.002  # 0.2% difference to confirm trend

    # Exit parameters
    reversal_exit_bars: int = 2
    trend_exit_bars: int = 5

    # ATR filter
    atr_period: int = 14
    atr_threshold: float = 8.0

    # Session filter
    use_kill_zone: bool = True

    # Costs
    commission_per_contract: float = 5.0
    slippage_points: float = 2.0


def calculate_ema(values: np.ndarray, period: int) -> np.ndarray:
    """Calculate Exponential Moving Average."""
    ema = np.full(len(values), np.nan)
    alpha = 2.0 / (period + 1)

    # Find first valid value
    first_valid = 0
    for i in range(len(values)):
        if np.isfinite(values[i]):
            ema[i] = values[i]
            first_valid = i
            break

    # Calculate EMA
    for i in range(first_valid + 1, len(values)):
        if np.isfinite(values[i]):
            if np.isfinite(ema[i - 1]):
                ema[i] = alpha * values[i] + (1 - alpha) * ema[i - 1]
            else:
                ema[i] = values[i]

    return ema


def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Calculate Average True Range."""
    previous_close = np.r_[np.nan, close[:-1]]
    true_range = np.maximum.reduce([
        high - low,
        np.abs(high - previous_close),
        np.abs(low - previous_close)
    ])
    return pd.Series(true_range).rolling(period, min_periods=max(5, period // 2)).mean().to_numpy(dtype=float)


def detect_trend(close: np.ndarray, ema_fast_period: int, ema_slow_period: int, trend_threshold: float) -> np.ndarray:
    """
    Detect trend using EMA crossover.

    Returns:
        Array of trend signals: 1 (uptrend), -1 (downtrend), 0 (ranging)
    """
    ema_fast = calculate_ema(close, ema_fast_period)
    ema_slow = calculate_ema(close, ema_slow_period)

    trend = np.zeros(len(close), dtype=np.int8)

    for i in range(len(close)):
        if not np.isfinite(ema_fast[i]) or not np.isfinite(ema_slow[i]):
            trend[i] = NEUTRAL
        elif ema_fast[i] > ema_slow[i] * (1 + trend_threshold):
            trend[i] = BULLISH
        elif ema_fast[i] < ema_slow[i] * (1 - trend_threshold):
            trend[i] = BEARISH
        else:
            trend[i] = NEUTRAL

    return trend


def calculate_premium_discount(high: np.ndarray, low: np.ndarray, close: np.ndarray, lookback: int,
                                premium_threshold: float, discount_threshold: float) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculate Premium and Discount levels using range-based method.

    Returns:
        (premium_levels, discount_levels)
    """
    premium_levels = np.full(len(close), np.nan)
    discount_levels = np.full(len(close), np.nan)

    for i in range(lookback, len(close)):
        window_high = high[i - lookback:i]
        window_low = low[i - lookback:i]

        trailing_high = np.nanmax(window_high)
        trailing_low = np.nanmin(window_low)
        range_size = trailing_high - trailing_low

        if range_size > 0:
            premium_levels[i] = trailing_low + premium_threshold * range_size
            discount_levels[i] = trailing_low + discount_threshold * range_size

    return premium_levels, discount_levels


def is_kill_zone(minute_of_day: int) -> bool:
    """
    Check if current time is in NY Kill Zone.

    NY AM: 8:30-11:30 EST (510-690 minutes)
    NY PM: 13:30-16:00 EST (810-960 minutes)
    """
    return (510 <= minute_of_day <= 690) or (810 <= minute_of_day <= 960)


def generate_signals(bars: pd.DataFrame, config: TrendOptimizedConfig) -> pd.DataFrame:
    """
    Generate trading signals for trend-optimized strategy.

    Signal types:
    - reversal_long: Mean reversion long in ranging market
    - reversal_short: Mean reversion short in ranging market
    - trend_long: Trend following long in uptrend
    - trend_short: Trend following short in downtrend
    """
    df = bars.copy()

    # Extract arrays
    high = df["High"].to_numpy(dtype=float)
    low = df["Low"].to_numpy(dtype=float)
    close = df["Close"].to_numpy(dtype=float)
    minute_of_day = df["minute_of_day"].to_numpy(dtype=int)

    # Calculate indicators
    atr = calculate_atr(high, low, close, config.atr_period)
    trend = detect_trend(close, config.ema_fast_period, config.ema_slow_period, config.trend_threshold)
    premium_levels, discount_levels = calculate_premium_discount(
        high, low, close, config.lookback, config.premium_threshold, config.discount_threshold
    )

    # Initialize signal columns
    df["atr"] = atr
    df["trend"] = trend
    df["premium_level"] = premium_levels
    df["discount_level"] = discount_levels
    df["in_premium"] = close > premium_levels
    df["in_discount"] = close < discount_levels
    df["in_kill_zone"] = [is_kill_zone(m) for m in minute_of_day]

    # Generate signals
    df["signal"] = 0
    df["signal_type"] = ""

    for i in range(config.lookback, len(df)):
        # Check filters
        if not np.isfinite(atr[i]) or atr[i] <= config.atr_threshold:
            continue

        if config.use_kill_zone and not df.loc[i, "in_kill_zone"]:
            continue

        if not np.isfinite(premium_levels[i]) or not np.isfinite(discount_levels[i]):
            continue

        # Mode 1: Ranging market - Mean reversion
        if trend[i] == NEUTRAL:
            if df.loc[i, "in_premium"]:
                df.loc[i, "signal"] = BEARISH
                df.loc[i, "signal_type"] = "reversal_short"
            elif df.loc[i, "in_discount"]:
                df.loc[i, "signal"] = BULLISH
                df.loc[i, "signal_type"] = "reversal_long"

        # Mode 2: Uptrend - Long at Discount (pullback buy)
        elif trend[i] == BULLISH:
            if df.loc[i, "in_discount"]:
                df.loc[i, "signal"] = BULLISH
                df.loc[i, "signal_type"] = "trend_long"

        # Mode 3: Downtrend - Short at Premium (rally sell)
        elif trend[i] == BEARISH:
            if df.loc[i, "in_premium"]:
                df.loc[i, "signal"] = BEARISH
                df.loc[i, "signal_type"] = "trend_short"

    return df


def backtest_strategy(bars: pd.DataFrame, config: TrendOptimizedConfig) -> dict:
    """
    Backtest the trend-optimized strategy.

    Returns:
        Dictionary with backtest results
    """
    # Generate signals
    df = generate_signals(bars, config)

    # Initialize tracking
    trades = []
    position = 0
    entry_price = 0.0
    entry_index = 0
    entry_type = ""

    # Run backtest
    for i in range(len(df)):
        current_price = df.loc[i, "Close"]
        current_trend = df.loc[i, "trend"]

        # Check exit conditions
        if position != 0:
            bars_in_trade = i - entry_index
            should_exit = False
            exit_reason = ""

            # Reversal trades: Fast exit
            if "reversal" in entry_type:
                if bars_in_trade >= config.reversal_exit_bars:
                    should_exit = True
                    exit_reason = "time_exit_reversal"

            # Trend trades: Hold longer or trend reversal
            elif "trend" in entry_type:
                # Trend reversal exit
                if position == BULLISH and current_trend == BEARISH:
                    should_exit = True
                    exit_reason = "trend_reversal"
                elif position == BEARISH and current_trend == BULLISH:
                    should_exit = True
                    exit_reason = "trend_reversal"
                # Time exit
                elif bars_in_trade >= config.trend_exit_bars:
                    should_exit = True
                    exit_reason = "time_exit_trend"

            # Execute exit
            if should_exit:
                exit_price = current_price
                pnl_points = (exit_price - entry_price) * position
                pnl_dollars = pnl_points * 2.0  # MNQ multiplier

                # Apply costs
                total_commission = config.commission_per_contract * 2  # Round trip
                total_slippage = config.slippage_points * 2.0  # Entry + exit
                net_pnl = pnl_dollars - total_commission - total_slippage

                trades.append({
                    "entry_index": entry_index,
                    "entry_time": df.loc[entry_index, "ts"],
                    "entry_price": entry_price,
                    "entry_type": entry_type,
                    "exit_index": i,
                    "exit_time": df.loc[i, "ts"],
                    "exit_price": exit_price,
                    "exit_reason": exit_reason,
                    "direction": "long" if position == BULLISH else "short",
                    "bars_held": bars_in_trade,
                    "pnl_points": pnl_points,
                    "pnl_dollars": pnl_dollars,
                    "net_pnl": net_pnl,
                })

                position = 0
                entry_price = 0.0
                entry_index = 0
                entry_type = ""

        # Check entry conditions
        if position == 0 and df.loc[i, "signal"] != 0:
            position = df.loc[i, "signal"]
            entry_price = current_price
            entry_index = i
            entry_type = df.loc[i, "signal_type"]

    # Calculate statistics
    if not trades:
        return {
            "total_trades": 0,
            "net_profit": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "trades": [],
        }

    trades_df = pd.DataFrame(trades)

    # Basic stats
    total_trades = len(trades_df)
    winning_trades = trades_df[trades_df["net_pnl"] > 0]
    losing_trades = trades_df[trades_df["net_pnl"] < 0]

    win_count = len(winning_trades)
    loss_count = len(losing_trades)
    win_rate = win_count / total_trades if total_trades > 0 else 0.0

    gross_profit = winning_trades["net_pnl"].sum() if len(winning_trades) > 0 else 0.0
    gross_loss = abs(losing_trades["net_pnl"].sum()) if len(losing_trades) > 0 else 0.0
    net_profit = gross_profit - gross_loss
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

    avg_win = winning_trades["net_pnl"].mean() if len(winning_trades) > 0 else 0.0
    avg_loss = losing_trades["net_pnl"].mean() if len(losing_trades) > 0 else 0.0

    # Drawdown
    cumulative_pnl = trades_df["net_pnl"].cumsum()
    running_max = cumulative_pnl.cummax()
    drawdown = running_max - cumulative_pnl
    max_drawdown = drawdown.max()

    # Sharpe ratio (annualized)
    daily_returns = trades_df.groupby(trades_df["entry_time"].dt.date)["net_pnl"].sum()
    if len(daily_returns) > 1:
        sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() > 0 else 0.0
    else:
        sharpe_ratio = 0.0

    # Trade type breakdown
    reversal_trades = trades_df[trades_df["entry_type"].str.contains("reversal")]
    trend_trades = trades_df[trades_df["entry_type"].str.contains("trend")]

    return {
        "total_trades": total_trades,
        "net_profit": net_profit,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "win_rate": win_rate,
        "win_count": win_count,
        "loss_count": loss_count,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "reversal_trades": len(reversal_trades),
        "reversal_profit": reversal_trades["net_pnl"].sum() if len(reversal_trades) > 0 else 0.0,
        "trend_trades": len(trend_trades),
        "trend_profit": trend_trades["net_pnl"].sum() if len(trend_trades) > 0 else 0.0,
        "trades": trades,
    }


def main():
    parser = argparse.ArgumentParser(description="Backtest Lightglow Trend-Optimized Strategy")
    parser.add_argument("--start-date", default="2020-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default="2026-05-08", help="End date (YYYY-MM-DD)")
    parser.add_argument("--cache", default=".tmp/nq-trend-optimized-cache.pkl", help="Cache file")
    parser.add_argument("--chunk-size", type=int, default=500_000, help="Chunk size for loading")
    parser.add_argument("--min-volume", type=float, default=1.0, help="Minimum volume filter")
    parser.add_argument("--timeframe", type=int, default=1, help="Timeframe in minutes")
    parser.add_argument("--output", default="reports/lightglow_trend_optimized_backtest.json", help="Output file")
    args = parser.parse_args()

    print("=" * 80)
    print("Lightglow Trend-Optimized Strategy Backtest")
    print("=" * 80)
    print()

    # Load data
    print(f"Loading NQ bars from {args.start_date} to {args.end_date}...")
    bars = load_continuous_nq_bars(args)

    if args.timeframe > 1:
        print(f"Resampling to {args.timeframe}-minute bars...")
        bars = resample_ohlcv(bars, args.timeframe)

    print(f"Loaded {len(bars):,} bars")
    print()

    # Run backtest
    config = TrendOptimizedConfig()
    print("Configuration:")
    print(f"  Lookback: {config.lookback}")
    print(f"  Premium/Discount: {config.premium_threshold}/{config.discount_threshold}")
    print(f"  EMA Fast/Slow: {config.ema_fast_period}/{config.ema_slow_period}")
    print(f"  Trend Threshold: {config.trend_threshold:.3f}")
    print(f"  Reversal Exit: {config.reversal_exit_bars} bars")
    print(f"  Trend Exit: {config.trend_exit_bars} bars")
    print(f"  ATR Threshold: {config.atr_threshold}")
    print()

    print("Running backtest...")
    results = backtest_strategy(bars, config)

    # Print results
    print()
    print("=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)
    print()
    print(f"Total Trades: {results['total_trades']:,}")
    print(f"Net Profit: ${results['net_profit']:,.2f}")
    print(f"Gross Profit: ${results['gross_profit']:,.2f}")
    print(f"Gross Loss: ${results['gross_loss']:,.2f}")
    print(f"Profit Factor: {results['profit_factor']:.2f}")
    print(f"Win Rate: {results['win_rate']:.1%}")
    print(f"Wins/Losses: {results['win_count']}/{results['loss_count']}")
    print(f"Avg Win: ${results['avg_win']:,.2f}")
    print(f"Avg Loss: ${results['avg_loss']:,.2f}")
    print(f"Max Drawdown: ${results['max_drawdown']:,.2f}")
    print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print()
    print("Trade Type Breakdown:")
    print(f"  Reversal Trades: {results['reversal_trades']:,} (${results['reversal_profit']:,.2f})")
    print(f"  Trend Trades: {results['trend_trades']:,} (${results['trend_profit']:,.2f})")
    print()

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove trades from saved results (too large)
    save_results = {k: v for k, v in results.items() if k != "trades"}

    with open(output_path, "w") as f:
        json.dump(save_results, f, indent=2)

    print(f"Results saved to: {output_path}")
    print()


if __name__ == "__main__":
    main()
