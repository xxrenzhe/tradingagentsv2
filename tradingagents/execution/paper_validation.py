from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .ibkr import IBKROrderIntent


def load_trade_samples(path: Path | str) -> pd.DataFrame:
    trades = pd.read_csv(path)
    if trades.empty:
        raise ValueError(f"No trade samples found in {path}")
    required = {"entry_ts", "exit_ts", "direction", "entry_price", "portfolio_rule", "selected_alias"}
    missing = required.difference(trades.columns)
    if missing:
        raise ValueError(f"Missing trade sample columns: {sorted(missing)}")
    return trades


def select_trade_sample(
    trades: pd.DataFrame,
    *,
    trade_date: str | None = None,
    portfolio_rule: str | None = None,
    selected_alias: str | None = None,
    row_index: int | None = None,
) -> pd.Series:
    filtered = trades
    if trade_date is not None:
        filtered = filtered[filtered["trade_date"].astype(str).eq(trade_date)]
    if portfolio_rule is not None:
        filtered = filtered[filtered["portfolio_rule"].astype(str).eq(portfolio_rule)]
    if selected_alias is not None:
        filtered = filtered[filtered["selected_alias"].astype(str).eq(selected_alias)]
    if filtered.empty:
        raise ValueError("No trade sample matched the requested filters")
    if row_index is None:
        return filtered.iloc[-1]
    normalized_index = row_index if row_index >= 0 else len(filtered) + row_index
    if normalized_index < 0 or normalized_index >= len(filtered):
        raise IndexError(f"Trade sample index out of range: {row_index}")
    return filtered.iloc[normalized_index]


def _signed_direction(value: Any) -> int:
    direction = int(float(value))
    if direction == 0:
        raise ValueError("Trade sample direction must be non-zero")
    return 1 if direction > 0 else -1


def _round_price(value: float) -> float:
    return round(float(value), 2)


def build_paper_intent_from_trade(
    trade: pd.Series,
    *,
    contract_month: str,
    account: str | None = None,
    quantity: int = 1,
    stop_loss_points: float = 16.0,
    take_profit_points: float = 24.0,
    strategy_id: str | None = None,
    symbol: str = "MNQ",
    exchange: str = "CME",
    currency: str = "USD",
    reference_price: float | None = None,
    reference_source: str | None = None,
) -> IBKROrderIntent:
    direction = _signed_direction(trade["direction"])
    entry_price = float(reference_price if reference_price is not None else trade["entry_price"])
    if direction > 0:
        action = "BUY"
        stop_loss_price = entry_price - float(stop_loss_points)
        take_profit_price = entry_price + float(take_profit_points)
    else:
        action = "SELL"
        stop_loss_price = entry_price + float(stop_loss_points)
        take_profit_price = entry_price - float(take_profit_points)
    trade_date = str(trade.get("trade_date", "unknown"))
    selected_alias = str(trade.get("selected_alias", "unknown"))
    portfolio_rule = str(trade.get("portfolio_rule", "adaptive_portfolio"))
    exit_reason = str(trade.get("exit_reason", ""))
    reason_parts = [
        "mbp adaptive portfolio paper validation",
        f"trade_date={trade_date}",
        f"portfolio_rule={portfolio_rule}",
        f"selected_alias={selected_alias}",
        f"exit_reason={exit_reason}",
        f"stop_loss_points={float(stop_loss_points):.4f}",
        f"take_profit_points={float(take_profit_points):.4f}",
    ]
    if reference_source:
        reason_parts.append(f"reference_source={reference_source}")
        reason_parts.append(f"reference_price={entry_price:.2f}")
    return IBKROrderIntent(
        action=action,
        quantity=int(quantity),
        symbol=symbol.upper(),
        exchange=exchange,
        currency=currency,
        last_trade_date_or_contract_month=str(contract_month),
        order_type="MKT",
        stop_loss_price=_round_price(stop_loss_price),
        take_profit_price=_round_price(take_profit_price),
        account=account,
        strategy_id=strategy_id or portfolio_rule,
        reason=" | ".join(reason_parts),
    )
