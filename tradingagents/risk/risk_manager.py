"""
Risk Management Module for Trading Strategies

This module implements various risk management techniques:
1. Fixed risk percentage position sizing
2. Consecutive loss protection
3. Equity curve management
4. Dynamic position sizing based on account state

Key Principles:
- Don't change strategy logic
- Optimize risk and execution
- Data-driven decisions
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np


class RiskState(Enum):
    """Account risk state"""
    NORMAL = "normal"           # Normal trading
    REDUCED = "reduced"         # Reduced position size
    CONSERVATIVE = "conservative"  # Very small position
    PAUSED = "paused"          # No trading


@dataclass
class RiskConfig:
    """Risk management configuration"""

    # Position sizing
    risk_per_trade_pct: float = 0.01  # 1% of account per trade
    max_position_size: int = 10       # Maximum contracts
    min_position_size: int = 1        # Minimum contracts

    # Consecutive loss protection
    consecutive_loss_threshold_1: int = 3  # First threshold
    consecutive_loss_threshold_2: int = 5  # Second threshold
    consecutive_loss_threshold_3: int = 7  # Third threshold
    position_reduction_1: float = 0.5      # Reduce to 50%
    position_reduction_2: float = 0.25     # Reduce to 25%
    position_reduction_3: float = 0.0      # Pause trading

    # Equity curve management
    drawdown_threshold_1: float = 0.05  # 5% drawdown
    drawdown_threshold_2: float = 0.10  # 10% drawdown
    drawdown_threshold_3: float = 0.15  # 15% drawdown
    drawdown_threshold_4: float = 0.20  # 20% drawdown
    drawdown_reduction_1: float = 0.75  # Reduce to 75%
    drawdown_reduction_2: float = 0.50  # Reduce to 50%
    drawdown_reduction_3: float = 0.25  # Reduce to 25%
    drawdown_reduction_4: float = 0.0   # Pause trading

    # Recovery
    recovery_increment: float = 0.25    # Increase position by 25% after win
    recovery_threshold: int = 2         # Consecutive wins to recover


class RiskManager:
    """
    Risk management system for trading strategies

    Features:
    - Fixed risk percentage position sizing
    - Consecutive loss protection
    - Equity curve management
    - Dynamic position adjustment
    """

    def __init__(
        self,
        initial_capital: float,
        config: Optional[RiskConfig] = None,
    ):
        self.initial_capital = initial_capital
        self.config = config or RiskConfig()

        # State tracking
        self.current_capital = initial_capital
        self.peak_capital = initial_capital
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.position_multiplier = 1.0
        self.risk_state = RiskState.NORMAL

        # History
        self.trade_history = []
        self.capital_history = [initial_capital]
        self.state_history = [RiskState.NORMAL]

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: Optional[float] = None,
        point_value: float = 20.0,
    ) -> int:
        """
        Calculate position size based on risk management rules

        Args:
            entry_price: Entry price
            stop_loss_price: Stop loss price (optional)
            point_value: Dollar value per point

        Returns:
            Number of contracts to trade
        """

        # Check if trading is paused
        if self.risk_state == RiskState.PAUSED:
            return 0

        # Calculate base position size
        if stop_loss_price is not None:
            # Risk-based sizing
            risk_per_contract = abs(entry_price - stop_loss_price) * point_value
            if risk_per_contract > 0:
                risk_amount = self.current_capital * self.config.risk_per_trade_pct
                base_size = int(risk_amount / risk_per_contract)
            else:
                base_size = self.config.min_position_size
        else:
            # Fixed percentage of capital
            # Assume average risk per contract (e.g., $100)
            avg_risk_per_contract = 100.0
            risk_amount = self.current_capital * self.config.risk_per_trade_pct
            base_size = int(risk_amount / avg_risk_per_contract)

        # Apply position multiplier (from consecutive losses or drawdown)
        adjusted_size = int(base_size * self.position_multiplier)

        # Clamp to min/max
        position_size = max(
            self.config.min_position_size,
            min(adjusted_size, self.config.max_position_size)
        )

        return position_size

    def update_after_trade(
        self,
        pnl: float,
        is_win: bool,
    ) -> None:
        """
        Update risk manager state after a trade

        Args:
            pnl: Profit/loss from the trade
            is_win: Whether the trade was profitable
        """

        # Update capital
        self.current_capital += pnl
        self.capital_history.append(self.current_capital)

        # Update peak
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital

        # Update consecutive counters
        if is_win:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0

        # Record trade
        self.trade_history.append({
            'pnl': pnl,
            'is_win': is_win,
            'capital': self.current_capital,
            'consecutive_losses': self.consecutive_losses,
            'consecutive_wins': self.consecutive_wins,
            'position_multiplier': self.position_multiplier,
            'risk_state': self.risk_state,
        })

        # Update risk state
        self._update_risk_state()
        self.state_history.append(self.risk_state)

    def _update_risk_state(self) -> None:
        """Update risk state based on current conditions"""

        # Calculate current drawdown
        drawdown = (self.peak_capital - self.current_capital) / self.peak_capital

        # Check consecutive losses
        consecutive_multiplier = 1.0
        if self.consecutive_losses >= self.config.consecutive_loss_threshold_3:
            consecutive_multiplier = self.config.position_reduction_3
        elif self.consecutive_losses >= self.config.consecutive_loss_threshold_2:
            consecutive_multiplier = self.config.position_reduction_2
        elif self.consecutive_losses >= self.config.consecutive_loss_threshold_1:
            consecutive_multiplier = self.config.position_reduction_1

        # Check drawdown
        drawdown_multiplier = 1.0
        if drawdown >= self.config.drawdown_threshold_4:
            drawdown_multiplier = self.config.drawdown_reduction_4
        elif drawdown >= self.config.drawdown_threshold_3:
            drawdown_multiplier = self.config.drawdown_reduction_3
        elif drawdown >= self.config.drawdown_threshold_2:
            drawdown_multiplier = self.config.drawdown_reduction_2
        elif drawdown >= self.config.drawdown_threshold_1:
            drawdown_multiplier = self.config.drawdown_reduction_1

        # Use the more conservative multiplier
        self.position_multiplier = min(consecutive_multiplier, drawdown_multiplier)

        # Recovery logic
        if self.position_multiplier < 1.0 and self.consecutive_wins >= self.config.recovery_threshold:
            # Gradually recover position size
            self.position_multiplier = min(1.0, self.position_multiplier + self.config.recovery_increment)
            self.consecutive_wins = 0  # Reset counter

        # Determine risk state
        if self.position_multiplier == 0.0:
            self.risk_state = RiskState.PAUSED
        elif self.position_multiplier <= 0.25:
            self.risk_state = RiskState.CONSERVATIVE
        elif self.position_multiplier <= 0.75:
            self.risk_state = RiskState.REDUCED
        else:
            self.risk_state = RiskState.NORMAL

    def get_statistics(self) -> dict:
        """Get risk management statistics"""

        if not self.trade_history:
            return {}

        capital_array = np.array(self.capital_history)
        running_max = np.maximum.accumulate(capital_array)
        drawdowns = (running_max - capital_array) / running_max

        return {
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'peak_capital': self.peak_capital,
            'total_return': (self.current_capital - self.initial_capital) / self.initial_capital,
            'max_drawdown': drawdowns.max(),
            'current_drawdown': drawdowns[-1],
            'total_trades': len(self.trade_history),
            'consecutive_losses': self.consecutive_losses,
            'consecutive_wins': self.consecutive_wins,
            'position_multiplier': self.position_multiplier,
            'risk_state': self.risk_state.value,
            'paused_periods': sum(1 for s in self.state_history if s == RiskState.PAUSED),
            'reduced_periods': sum(1 for s in self.state_history if s == RiskState.REDUCED),
        }

    def reset(self) -> None:
        """Reset risk manager to initial state"""
        self.current_capital = self.initial_capital
        self.peak_capital = self.initial_capital
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.position_multiplier = 1.0
        self.risk_state = RiskState.NORMAL
        self.trade_history = []
        self.capital_history = [self.initial_capital]
        self.state_history = [RiskState.NORMAL]


def backtest_with_risk_management(
    trades_df,
    initial_capital: float = 100000.0,
    config: Optional[RiskConfig] = None,
) -> tuple:
    """
    Backtest trades with risk management

    Args:
        trades_df: DataFrame with trade results
        initial_capital: Starting capital
        config: Risk management configuration

    Returns:
        (risk_manager, adjusted_trades_df)
    """
    import pandas as pd

    risk_manager = RiskManager(initial_capital, config)

    adjusted_trades = []

    for idx, trade in trades_df.iterrows():
        # Calculate position size
        position_size = risk_manager.calculate_position_size(
            entry_price=trade['entry_price'],
            stop_loss_price=None,  # Original strategy doesn't use stops
            point_value=20.0,
        )

        # Skip if paused
        if position_size == 0:
            continue

        # Calculate adjusted PnL
        original_pnl = trade['net_dollars']
        adjusted_pnl = original_pnl * position_size  # Assuming original is 1 contract

        # Update risk manager
        is_win = adjusted_pnl > 0
        risk_manager.update_after_trade(adjusted_pnl, is_win)

        # Record adjusted trade
        adjusted_trade = trade.copy()
        adjusted_trade['position_size'] = position_size
        adjusted_trade['adjusted_pnl'] = adjusted_pnl
        adjusted_trade['capital'] = risk_manager.current_capital
        adjusted_trade['risk_state'] = risk_manager.risk_state.value
        adjusted_trades.append(adjusted_trade)

    adjusted_trades_df = pd.DataFrame(adjusted_trades)

    return risk_manager, adjusted_trades_df
