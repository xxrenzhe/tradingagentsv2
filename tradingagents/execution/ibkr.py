from __future__ import annotations

import json
import math
import os
import re
import socket
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from tradingagents.config.env import load_project_env


load_project_env()


PAPER_PORTS = {7497, 4002}
ALLOWED_ACTIONS = {"BUY", "SELL"}
ALLOWED_ORDER_TYPES = {"MKT", "LMT"}
ACTIVE_ORDER_STATUSES = {"ApiPending", "PendingSubmit", "PreSubmitted", "Submitted"}
PAPER_TRADEABLE_MARKET_DATA_TYPES = {"1", "2", "3", "live", "frozen", "delayed"}


@dataclass(frozen=True)
class IBKRConnectionConfig:
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 26
    account: str | None = None
    timeout: float = 10.0
    readonly: bool = False

    @classmethod
    def from_env(cls) -> "IBKRConnectionConfig":
        return cls(
            host=os.getenv("TRADINGAGENTS_IBKR_HOST", "127.0.0.1"),
            port=int(os.getenv("TRADINGAGENTS_IBKR_PORT", "7497")),
            client_id=int(os.getenv("TRADINGAGENTS_IBKR_CLIENT_ID", "26")),
            account=os.getenv("TRADINGAGENTS_IBKR_ACCOUNT") or None,
            timeout=float(os.getenv("TRADINGAGENTS_IBKR_TIMEOUT", "10")),
            readonly=os.getenv("TRADINGAGENTS_IBKR_READONLY", "false").lower() in {"1", "true", "yes"},
        )


@dataclass(frozen=True)
class IBKRPaperRiskConfig:
    allowed_accounts: tuple[str, ...] = ()
    allowed_symbols: tuple[str, ...] = ("MNQ",)
    max_quantity: int = 1
    max_position_after_fill: int = 1
    require_bracket: bool = True
    kill_switch: bool = False
    paper_only: bool = True
    allow_market_orders: bool = True

    @classmethod
    def from_env(cls) -> "IBKRPaperRiskConfig":
        allowed_accounts = tuple(
            value.strip()
            for value in os.getenv("TRADINGAGENTS_IBKR_ALLOWED_ACCOUNTS", "").split(",")
            if value.strip()
        )
        allowed_symbols = tuple(
            value.strip().upper()
            for value in os.getenv("TRADINGAGENTS_IBKR_ALLOWED_SYMBOLS", "MNQ").split(",")
            if value.strip()
        )
        return cls(
            allowed_accounts=allowed_accounts,
            allowed_symbols=allowed_symbols or ("MNQ",),
            max_quantity=int(os.getenv("TRADINGAGENTS_IBKR_MAX_QTY", "1")),
            max_position_after_fill=int(os.getenv("TRADINGAGENTS_IBKR_MAX_POSITION", "1")),
            require_bracket=os.getenv("TRADINGAGENTS_IBKR_REQUIRE_BRACKET", "true").lower() not in {"0", "false", "no"},
            kill_switch=os.getenv("TRADINGAGENTS_IBKR_KILL_SWITCH", "false").lower() in {"1", "true", "yes"},
            paper_only=os.getenv("TRADINGAGENTS_IBKR_PAPER_ONLY", "true").lower() not in {"0", "false", "no"},
            allow_market_orders=os.getenv("TRADINGAGENTS_IBKR_ALLOW_MARKET", "true").lower() not in {"0", "false", "no"},
        )


@dataclass(frozen=True)
class IBKROrderIntent:
    action: str
    quantity: int
    symbol: str = "MNQ"
    exchange: str = "CME"
    currency: str = "USD"
    last_trade_date_or_contract_month: str = "202606"
    order_type: str = "MKT"
    limit_price: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    account: str | None = None
    strategy_id: str = "manual"
    reason: str = ""
    intent_id: str | None = None
    idempotency_key: str | None = None

    def normalized(self) -> "IBKROrderIntent":
        return IBKROrderIntent(
            action=self.action.upper(),
            quantity=int(self.quantity),
            symbol=self.symbol.upper(),
            exchange=self.exchange,
            currency=self.currency,
            last_trade_date_or_contract_month=str(self.last_trade_date_or_contract_month),
            order_type=self.order_type.upper(),
            limit_price=self.limit_price,
            stop_loss_price=self.stop_loss_price,
            take_profit_price=self.take_profit_price,
            account=self.account,
            strategy_id=self.strategy_id,
            reason=self.reason,
            intent_id=self.intent_id or f"ibkr_intent_{uuid4().hex}",
            idempotency_key=self.idempotency_key or uuid4().hex,
        )


@dataclass(frozen=True)
class IBKRContractSpec:
    symbol: str = "MNQ"
    exchange: str = "CME"
    currency: str = "USD"
    last_trade_date_or_contract_month: str = "202606"
    expected_tick_size: float = 0.25
    expected_point_value: float = 2.0

    def to_intent_fields(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "currency": self.currency,
            "last_trade_date_or_contract_month": self.last_trade_date_or_contract_month,
        }


@dataclass(frozen=True)
class IBKRMarketSnapshot:
    symbol: str
    bid: float | None
    ask: float | None
    last: float | None
    bid_size: float | None = None
    ask_size: float | None = None
    last_size: float | None = None
    market_data_type: str = "unknown"
    snapshot_time: str = ""

    @property
    def spread(self) -> float | None:
        bid = _finite_price(self.bid)
        ask = _finite_price(self.ask)
        if bid is None or ask is None:
            return None
        return ask - bid

    @property
    def order_ready(self) -> bool:
        return _finite_price(self.bid) is not None and _finite_price(self.ask) is not None and _finite_price(self.last) is not None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {
            "bid": _finite_price(self.bid),
            "ask": _finite_price(self.ask),
            "last": _finite_price(self.last),
            "bid_size": _optional_float(self.bid_size),
            "ask_size": _optional_float(self.ask_size),
            "last_size": _optional_float(self.last_size),
            "spread": self.spread,
            "order_ready": self.order_ready,
        }


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _load_ib_class(name: str) -> type:
    try:
        import ib_insync
    except ImportError as exc:
        raise RuntimeError("ib_insync is required for IBKR paper trading. Install with `pip install ib_insync`.") from exc
    return getattr(ib_insync, name)


def build_nq_future_contract(intent: IBKROrderIntent, future_cls: type | None = None) -> Any:
    future_cls = future_cls or _load_ib_class("Future")
    return future_cls(
        symbol=intent.symbol,
        lastTradeDateOrContractMonth=intent.last_trade_date_or_contract_month,
        exchange=intent.exchange,
        currency=intent.currency,
    )


def _contract_for_broker(intent: IBKROrderIntent, ib: Any | None) -> Any:
    if ib is None:
        return build_nq_future_contract(intent)
    try:
        return build_nq_future_contract(intent)
    except RuntimeError:
        return SimpleNamespace(
            symbol=intent.symbol,
            lastTradeDateOrContractMonth=intent.last_trade_date_or_contract_month,
            exchange=intent.exchange,
            currency=intent.currency,
            secType="FUT",
        )


def _build_order(intent: IBKROrderIntent, order_cls: type | None = None) -> Any:
    order_cls = order_cls or _load_ib_class("Order")
    order = order_cls()
    order.action = intent.action
    order.totalQuantity = intent.quantity
    order.orderType = intent.order_type
    if intent.order_type == "LMT":
        order.lmtPrice = intent.limit_price
    if intent.account:
        order.account = intent.account
    order.transmit = not (intent.stop_loss_price is not None or intent.take_profit_price is not None)
    return order


def _dry_run_contract(intent: IBKROrderIntent) -> dict[str, Any]:
    return {
        "symbol": intent.symbol,
        "lastTradeDateOrContractMonth": intent.last_trade_date_or_contract_month,
        "exchange": intent.exchange,
        "currency": intent.currency,
        "secType": "FUT",
    }


def _dry_run_orders(intent: IBKROrderIntent) -> list[dict[str, Any]]:
    parent = {
        "action": intent.action,
        "totalQuantity": intent.quantity,
        "orderType": intent.order_type,
        "account": intent.account,
        "transmit": intent.stop_loss_price is None and intent.take_profit_price is None,
    }
    if intent.order_type == "LMT":
        parent["lmtPrice"] = intent.limit_price
    if intent.stop_loss_price is None or intent.take_profit_price is None:
        return [parent]
    exit_action = "SELL" if intent.action == "BUY" else "BUY"
    parent["transmit"] = False
    return [
        parent,
        {
            "action": exit_action,
            "totalQuantity": intent.quantity,
            "orderType": "LMT",
            "lmtPrice": intent.take_profit_price,
            "account": intent.account,
            "transmit": False,
        },
        {
            "action": exit_action,
            "totalQuantity": intent.quantity,
            "orderType": "STP",
            "auxPrice": intent.stop_loss_price,
            "account": intent.account,
            "transmit": True,
        },
    ]


def _build_bracket_order(intent: IBKROrderIntent, ib: Any) -> list[Any]:
    if intent.stop_loss_price is None or intent.take_profit_price is None:
        return [_build_order(intent)]
    if intent.order_type == "MKT":
        return _build_market_bracket_orders(intent, ib)
    if not hasattr(ib, "bracketOrder"):
        raise RuntimeError("IB object does not provide bracketOrder")
    if intent.order_type == "LMT":
        parent_price = intent.limit_price
    else:
        parent_price = intent.limit_price or 0
    bracket = ib.bracketOrder(
        intent.action,
        intent.quantity,
        parent_price,
        intent.take_profit_price,
        intent.stop_loss_price,
    )
    for order in bracket:
        if intent.account:
            order.account = intent.account
    if intent.order_type == "MKT":
        bracket[0].orderType = "MKT"
        if hasattr(bracket[0], "lmtPrice"):
            bracket[0].lmtPrice = 0
    return list(bracket)


def _build_market_bracket_orders(intent: IBKROrderIntent, ib: Any) -> list[Any]:
    parent = _build_order(intent)
    parent.transmit = True
    if hasattr(parent, "tif"):
        parent.tif = "DAY"
    return [parent]


def _build_oca_exit_orders(intent: IBKROrderIntent) -> list[Any]:
    exit_action = "SELL" if intent.action == "BUY" else "BUY"
    oca_group = f"{intent.symbol}_PROTECT_{uuid4().hex[:12]}"
    take_profit = _load_ib_class("Order")()
    take_profit.action = exit_action
    take_profit.totalQuantity = intent.quantity
    take_profit.orderType = "LMT"
    take_profit.lmtPrice = intent.take_profit_price
    take_profit.tif = "GTC"
    take_profit.transmit = True
    stop = _load_ib_class("Order")()
    stop.action = exit_action
    stop.totalQuantity = intent.quantity
    stop.orderType = "STP"
    stop.auxPrice = intent.stop_loss_price
    stop.tif = "GTC"
    stop.transmit = True
    for order in [take_profit, stop]:
        order.ocaGroup = oca_group
        order.ocaType = 1
        order.openClose = "C"
        order.outsideRth = True
        if intent.account:
            order.account = intent.account
    return [take_profit, stop]


def _is_market_bracket(intent: IBKROrderIntent) -> bool:
    return intent.order_type == "MKT" and intent.stop_loss_price is not None and intent.take_profit_price is not None


def _trade_status(trade: Any) -> str:
    return str(getattr(getattr(trade, "orderStatus", None), "status", "") or "")


def _trade_filled(trade: Any) -> bool:
    status = getattr(trade, "orderStatus", None)
    filled = _optional_float(getattr(status, "filled", None)) or 0.0
    remaining = _optional_float(getattr(status, "remaining", None))
    return _trade_status(trade) == "Filled" or (filled > 0 and remaining == 0)


def _trade_inactive(trade: Any) -> bool:
    return _trade_status(trade) in {"ApiCancelled", "Cancelled", "Inactive"}


def _bracket_protection_status(trades: list[Any]) -> dict[str, Any]:
    exit_trades = [
        trade
        for trade in trades
        if getattr(getattr(trade, "order", None), "orderType", None) in {"LMT", "STP"}
    ]
    if not exit_trades:
        return {}
    statuses = [_trade_status(trade) for trade in exit_trades]
    order_types = [str(getattr(getattr(trade, "order", None), "orderType", "") or "") for trade in exit_trades]
    return {
        "active": {"LMT", "STP"}.issubset(set(order_types)) and all(status in ACTIVE_ORDER_STATUSES for status in statuses),
        "statuses": statuses,
        "order_types": order_types,
        "exit_order_count": len(exit_trades),
    }


def evaluate_paper_risk(
    intent: IBKROrderIntent,
    connection: IBKRConnectionConfig,
    risk: IBKRPaperRiskConfig,
    current_position: int = 0,
) -> dict[str, Any]:
    reasons: list[str] = []
    if risk.kill_switch:
        reasons.append("kill_switch_enabled")
    if risk.paper_only and connection.port not in PAPER_PORTS:
        reasons.append("non_paper_port")
    if connection.readonly:
        reasons.append("readonly_connection")
    if intent.action not in ALLOWED_ACTIONS:
        reasons.append("unsupported_action")
    if intent.order_type not in ALLOWED_ORDER_TYPES:
        reasons.append("unsupported_order_type")
    if intent.order_type == "MKT" and not risk.allow_market_orders:
        reasons.append("market_orders_disabled")
    if intent.order_type == "LMT" and intent.limit_price is None:
        reasons.append("missing_limit_price")
    if intent.quantity <= 0:
        reasons.append("quantity_must_be_positive")
    if intent.quantity > risk.max_quantity:
        reasons.append("quantity_exceeds_limit")
    if intent.symbol not in risk.allowed_symbols:
        reasons.append("symbol_not_allowed")
    if risk.allowed_accounts and (intent.account or connection.account) not in risk.allowed_accounts:
        reasons.append("account_not_allowed")
    if risk.require_bracket and (intent.stop_loss_price is None or intent.take_profit_price is None):
        reasons.append("bracket_required")
    signed_quantity = intent.quantity if intent.action == "BUY" else -intent.quantity
    if abs(current_position + signed_quantity) > risk.max_position_after_fill:
        reasons.append("position_after_fill_exceeds_limit")
    return {
        "passed": not reasons,
        "decision": "risk_approved" if not reasons else "risk_rejected",
        "reasons": reasons,
        "checked_at": _now(),
        "paper_ports": sorted(PAPER_PORTS),
    }


class IBKRPaperBroker:
    def __init__(
        self,
        connection: IBKRConnectionConfig | None = None,
        risk: IBKRPaperRiskConfig | None = None,
        ib: Any | None = None,
        audit_path: Path | str | None = None,
    ) -> None:
        self.connection = connection or IBKRConnectionConfig.from_env()
        self.risk = risk or IBKRPaperRiskConfig.from_env()
        self.ib = ib
        self.audit_path = Path(audit_path or os.getenv("TRADINGAGENTS_IBKR_AUDIT_PATH", ".tmp/ibkr-paper-audit.jsonl"))

    def submit(self, intent: IBKROrderIntent, *, dry_run: bool = True, current_position: int = 0) -> dict[str, Any]:
        normalized = intent.normalized()
        account = normalized.account or self.connection.account
        if account != normalized.account:
            normalized = IBKROrderIntent(**(asdict(normalized) | {"account": account}))
        risk = evaluate_paper_risk(normalized, self.connection, self.risk, current_position=current_position)
        response: dict[str, Any] = {
            "intent": asdict(normalized),
            "connection": asdict(self.connection),
            "risk": risk,
            "dry_run": dry_run,
            "submitted": False,
            "orders": [],
            "trades": [],
            "created_at": _now(),
        }
        if not risk["passed"]:
            response["status"] = "risk_rejected"
            self._audit(response)
            return response
        if dry_run:
            response["orders"] = _dry_run_orders(normalized)
            response["contract"] = _dry_run_contract(normalized)
            response["status"] = "dry_run"
            self._audit(response)
            return response
        ib = self._ib()
        contract = _contract_for_broker(normalized, self.ib)
        orders = self._orders(normalized)
        response["orders"] = [_serialize_order(order) for order in orders]
        response["contract"] = _serialize_contract(contract)
        if not (hasattr(ib, "isConnected") and ib.isConnected()):
            try:
                ib.connect(
                    self.connection.host,
                    self.connection.port,
                    clientId=self.connection.client_id,
                    timeout=self.connection.timeout,
                    readonly=self.connection.readonly,
                )
            except Exception as exc:
                return {
                    "status": "connect_failed",
                    "connected": False,
                    "reason": str(exc) or exc.__class__.__name__,
                    "connection": asdict(self.connection),
                }
        qualified = ib.qualifyContracts(contract)
        live_contract = qualified[0] if qualified else contract
        trades = [ib.placeOrder(live_contract, order) for order in orders]
        if not dry_run and _is_market_bracket(normalized):
            trades = self._protect_market_entry(normalized, live_contract, trades)
            response["orders"] = [_serialize_order(getattr(trade, "order", None)) for trade in trades]
        response["submitted"] = True
        response["status"] = "submitted"
        response["trades"] = [_serialize_trade(trade) for trade in trades]
        protection = _bracket_protection_status(trades)
        if protection:
            response["protection"] = protection
            if not protection["active"]:
                response["status"] = "submitted_unprotected"
        self._audit(response)
        return response

    def connect(self) -> dict[str, Any]:
        if self.risk.paper_only and self.connection.port not in PAPER_PORTS:
            return {
                "status": "blocked",
                "connected": False,
                "reason": "non_paper_port",
                "connection": asdict(self.connection),
            }
        if self.connection.readonly:
            return {
                "status": "blocked",
                "connected": False,
                "reason": "readonly_connection",
                "connection": asdict(self.connection),
            }
        ib = self._ib()
        if hasattr(ib, "isConnected") and ib.isConnected():
            account_check = self._managed_account_check()
            if not account_check["passed"]:
                return {
                    "status": "blocked",
                    "connected": False,
                    "reason": "configured_account_not_managed",
                    "connection": asdict(self.connection),
                    "managed_accounts": account_check["managed_accounts"],
                }
            return {
                "status": "connected",
                "connected": True,
                "connection": asdict(self.connection),
                "managed_accounts": account_check["managed_accounts"],
            }
        try:
            ib.connect(
                self.connection.host,
                self.connection.port,
                clientId=self.connection.client_id,
                timeout=self.connection.timeout,
                readonly=self.connection.readonly,
            )
        except Exception as exc:
            return {
                "status": "connect_failed",
                "connected": False,
                "reason": str(exc) or exc.__class__.__name__,
                "connection": asdict(self.connection),
            }
        connected = bool(ib.isConnected()) if hasattr(ib, "isConnected") else True
        if not connected:
            return {"status": "connect_failed", "connected": False, "connection": asdict(self.connection)}
        account_check = self._managed_account_check()
        if not account_check["passed"]:
            return {
                "status": "blocked",
                "connected": False,
                "reason": "configured_account_not_managed",
                "connection": asdict(self.connection),
                "managed_accounts": account_check["managed_accounts"],
            }
        return {
            "status": "connected",
            "connected": True,
            "connection": asdict(self.connection),
            "managed_accounts": account_check["managed_accounts"],
        }

    def _managed_account_check(self) -> dict[str, Any]:
        ib = self._ib()
        managed_accounts = []
        if hasattr(ib, "managedAccounts"):
            try:
                managed_accounts = [str(account) for account in ib.managedAccounts()]
            except Exception:
                managed_accounts = []
        configured = self.connection.account
        passed = not configured or not managed_accounts or str(configured) in managed_accounts
        return {"passed": passed, "managed_accounts": managed_accounts}

    def account_summary(self) -> dict[str, Any]:
        ib = self._ib()
        rows = ib.accountSummary() if hasattr(ib, "accountSummary") else []
        summary: dict[str, Any] = {"account": self.connection.account, "account_type": "unknown"}
        for row in rows:
            tag = getattr(row, "tag", None)
            value = getattr(row, "value", None)
            account = getattr(row, "account", None)
            if account and not summary.get("account"):
                summary["account"] = account
            if tag == "AccountType":
                summary["account_type"] = value
            elif tag in {"NetLiquidation", "RealizedPnL", "UnrealizedPnL"}:
                summary[tag] = _optional_float(value)
        account = str(summary.get("account") or "")
        summary["paper"] = account.upper().startswith("DU") or str(summary.get("account_type", "")).lower() == "paper"
        return summary

    def positions(self) -> list[dict[str, Any]]:
        ib = self._ib()
        rows = ib.positions() if hasattr(ib, "positions") else []
        positions = []
        for row in rows:
            contract = getattr(row, "contract", None)
            positions.append(
                {
                    "account": getattr(row, "account", None),
                    "symbol": getattr(contract, "symbol", None),
                    "position": int(getattr(row, "position", 0) or 0),
                    "avg_cost": _optional_float(getattr(row, "avgCost", None)),
                }
            )
        return positions

    def current_position(self, symbol: str) -> int:
        total = 0
        for row in self.positions():
            if str(row.get("symbol", "")).upper() == symbol.upper():
                total += int(row.get("position") or 0)
        return total

    def open_trades(self) -> list[dict[str, Any]]:
        ib = self._ib()
        if not hasattr(ib, "openTrades"):
            return []
        if hasattr(ib, "reqAllOpenOrders"):
            try:
                ib.reqAllOpenOrders()
                if hasattr(ib, "sleep"):
                    ib.sleep(1)
            except Exception:
                pass
        return [_serialize_trade(trade) for trade in ib.openTrades()]

    def fills(self) -> list[dict[str, Any]]:
        ib = self._ib()
        if not hasattr(ib, "fills"):
            return []
        return [_serialize_fill(fill) for fill in ib.fills()]

    def execution_fills(self, *, symbol: str | None = None) -> list[dict[str, Any]]:
        ib = self._ib()
        if not hasattr(ib, "reqExecutions"):
            return self.fills()
        execution_filter = None
        try:
            execution_filter_cls = _load_ib_class("ExecutionFilter")
            execution_filter = execution_filter_cls(
                acctCode=self.connection.account or "",
                symbol=(symbol or ""),
                secType="FUT" if symbol else "",
            )
        except Exception:
            execution_filter = None
        return [_serialize_fill(fill) for fill in ib.reqExecutions(execution_filter)]

    def status_snapshot(self, symbol: str | None = None) -> dict[str, Any]:
        positions = self.positions()
        open_trades = self.open_trades()
        fills = self.fills()
        if symbol:
            open_trades = _filter_symbol_rows(open_trades, symbol)
            fills = _filter_symbol_rows(fills, symbol)
        return {
            "positions": positions,
            "current_position": self.current_position(symbol) if symbol else None,
            "open_trades": open_trades,
            "fills": fills,
        }

    def contract_details(self, spec: IBKRContractSpec) -> dict[str, Any]:
        ib = self._ib()
        intent = IBKROrderIntent(action="BUY", quantity=1, **spec.to_intent_fields())
        contract = _contract_for_broker(intent, self.ib)
        qualified = ib.qualifyContracts(contract) if hasattr(ib, "qualifyContracts") else [contract]
        live_contract = qualified[0] if qualified else contract
        details = {
            "symbol": getattr(live_contract, "symbol", spec.symbol),
            "exchange": getattr(live_contract, "exchange", spec.exchange),
            "currency": getattr(live_contract, "currency", spec.currency),
            "last_trade_date_or_contract_month": getattr(
                live_contract,
                "lastTradeDateOrContractMonth",
                spec.last_trade_date_or_contract_month,
            ),
            "local_symbol": getattr(live_contract, "localSymbol", None),
            "tick_size": spec.expected_tick_size,
            "point_value": spec.expected_point_value,
        }
        if hasattr(ib, "reqContractDetails"):
            rows = ib.reqContractDetails(live_contract)
            if rows:
                first = rows[0]
                details["tick_size"] = _optional_float(getattr(first, "minTick", None)) or details["tick_size"]
                contract_detail = getattr(first, "contract", live_contract)
                multiplier = getattr(contract_detail, "multiplier", None)
                details["point_value"] = _optional_float(multiplier) or details["point_value"]
                details["local_symbol"] = getattr(contract_detail, "localSymbol", details["local_symbol"])
        return details

    def market_snapshot(self, spec: IBKRContractSpec, *, snapshot: bool = True) -> IBKRMarketSnapshot:
        ib = self._ib()
        intent = IBKROrderIntent(action="BUY", quantity=1, **spec.to_intent_fields())
        contract = _contract_for_broker(intent, self.ib)
        if hasattr(ib, "qualifyContracts"):
            qualified = ib.qualifyContracts(contract)
            if qualified:
                contract = qualified[0]
        snapshots = []
        market_data_types = [1, 2, 3, 4] if hasattr(ib, "reqMarketDataType") else [None]
        for market_data_type in market_data_types:
            if market_data_type is not None:
                ib.reqMarketDataType(market_data_type)
            ticker = ib.reqMktData(contract, "", snapshot, False) if hasattr(ib, "reqMktData") else None
            if hasattr(ib, "sleep"):
                ib.sleep(1)
            current = IBKRMarketSnapshot(
                symbol=spec.symbol,
                bid=_optional_float(getattr(ticker, "bid", None)),
                ask=_optional_float(getattr(ticker, "ask", None)),
                last=_optional_float(getattr(ticker, "last", None)),
                bid_size=_optional_float(getattr(ticker, "bidSize", None)),
                ask_size=_optional_float(getattr(ticker, "askSize", None)),
                last_size=_optional_float(getattr(ticker, "lastSize", None)),
                market_data_type=str(getattr(ticker, "marketDataType", market_data_type or "unknown")),
                snapshot_time=_now(),
            )
            snapshots.append(current)
            if current.order_ready:
                return current
        return snapshots[-1] if snapshots else IBKRMarketSnapshot(symbol=spec.symbol, bid=None, ask=None, last=None, snapshot_time=_now())

    def tick_snapshot(self, spec: IBKRContractSpec) -> dict[str, Any]:
        snapshot = self.market_snapshot(spec, snapshot=True).to_dict()
        snapshot["event_type"] = "ibkr_tick_snapshot"
        return snapshot

    def tick_by_tick_snapshot(self, spec: IBKRContractSpec, *, tick_type: str = "BidAsk", interval_seconds: float = 1.0) -> list[dict[str, Any]]:
        ib = self._ib()
        if not hasattr(ib, "reqTickByTickData"):
            return []
        intent = IBKROrderIntent(action="BUY", quantity=1, **spec.to_intent_fields())
        contract = _contract_for_broker(intent, self.ib)
        ticker = ib.reqTickByTickData(contract, tick_type, 0, False)
        if hasattr(ib, "sleep"):
            ib.sleep(interval_seconds)
        ticks = [_serialize_tick_by_tick(tick) for tick in getattr(ticker, "tickByTicks", [])]
        if hasattr(ib, "cancelTickByTickData"):
            try:
                ib.cancelTickByTickData(ticker)
            except TypeError:
                ib.cancelTickByTickData(contract, tick_type)
        return ticks

    def _orders(self, intent: IBKROrderIntent) -> list[Any]:
        if self.ib is not None and intent.stop_loss_price is not None and intent.take_profit_price is not None:
            return _build_bracket_order(intent, self.ib)
        return [_build_order(intent)]

    def _protect_market_entry(self, intent: IBKROrderIntent, contract: Any, trades: list[Any]) -> list[Any]:
        parent_trade = trades[0] if trades else None
        if parent_trade is not None:
            self._wait_for_terminal_entry(parent_trade)
            if not _trade_filled(parent_trade):
                return trades
        if len(trades) > 1 and _bracket_protection_status(trades)["active"]:
            return trades
        ib = self._ib()
        protective_orders = _build_oca_exit_orders(intent)
        protective_trades = [ib.placeOrder(contract, order) for order in protective_orders]
        if hasattr(ib, "sleep"):
            ib.sleep(1)
        return [parent_trade] + protective_trades if parent_trade is not None else protective_trades

    def _wait_for_terminal_entry(self, trade: Any, *, timeout_seconds: float = 5.0) -> None:
        ib = self._ib()
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if _trade_filled(trade) or _trade_inactive(trade):
                return
            if hasattr(ib, "sleep"):
                ib.sleep(0.2)
            else:
                time.sleep(0.2)

    def _ib(self) -> Any:
        if self.ib is not None:
            return self.ib
        ib_cls = _load_ib_class("IB")
        self.ib = ib_cls()
        return self.ib

    def _audit(self, event: dict[str, Any]) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")


def _serialize_order(order: Any) -> dict[str, Any]:
    fields = [
        "action",
        "totalQuantity",
        "orderType",
        "lmtPrice",
        "auxPrice",
        "account",
        "transmit",
        "parentId",
        "ocaGroup",
        "ocaType",
        "openClose",
        "outsideRth",
        "tif",
    ]
    return {field: getattr(order, field) for field in fields if hasattr(order, field)}


def _serialize_contract(contract: Any) -> dict[str, Any]:
    fields = ["symbol", "lastTradeDateOrContractMonth", "exchange", "currency", "secType", "localSymbol"]
    return {field: getattr(contract, field) for field in fields if hasattr(contract, field)}


def _serialize_trade(trade: Any) -> dict[str, Any]:
    contract = getattr(trade, "contract", None)
    order = getattr(trade, "order", None)
    order_status = getattr(trade, "orderStatus", None)
    return {
        "contract": _serialize_contract(contract) if contract is not None else {},
        "order": _serialize_order(order) if order is not None else {},
        "order_status": {
            "status": getattr(order_status, "status", None),
            "filled": getattr(order_status, "filled", None),
            "remaining": getattr(order_status, "remaining", None),
        }
        if order_status is not None
        else {},
    }


def _serialize_fill(fill: Any) -> dict[str, Any]:
    contract = getattr(fill, "contract", None)
    execution = getattr(fill, "execution", None)
    commission_report = getattr(fill, "commissionReport", None)
    return {
        "contract": _serialize_contract(contract) if contract is not None else {},
        "execution": {
            "exec_id": getattr(execution, "execId", None),
            "time": getattr(execution, "time", None),
            "account": getattr(execution, "acctNumber", None),
            "side": getattr(execution, "side", None),
            "shares": getattr(execution, "shares", None),
            "price": _optional_float(getattr(execution, "price", None)),
            "order_id": getattr(execution, "orderId", None),
        }
        if execution is not None
        else {},
        "commission_report": {
            "commission": _optional_float(getattr(commission_report, "commission", None)),
            "currency": getattr(commission_report, "currency", None),
            "realized_pnl": _optional_float(getattr(commission_report, "realizedPNL", None)),
        }
        if commission_report is not None
        else {},
    }


def _filter_symbol_rows(rows: list[dict[str, Any]], symbol: str) -> list[dict[str, Any]]:
    expected = symbol.upper()
    filtered = []
    for row in rows:
        contract = row.get("contract") if isinstance(row.get("contract"), dict) else {}
        row_symbol = str(contract.get("symbol") or "").upper()
        if row_symbol == expected:
            filtered.append(row)
    return filtered


def _serialize_tick_by_tick(tick: Any) -> dict[str, Any]:
    return {
        "event_type": "ibkr_tick_by_tick",
        "time": getattr(tick, "time", None),
        "tick_type": tick.__class__.__name__,
        "price": _optional_float(getattr(tick, "price", None)),
        "size": _optional_float(getattr(tick, "size", None)),
        "bid_price": _optional_float(getattr(tick, "bidPrice", None)),
        "ask_price": _optional_float(getattr(tick, "askPrice", None)),
        "bid_size": _optional_float(getattr(tick, "bidSize", None)),
        "ask_size": _optional_float(getattr(tick, "askSize", None)),
        "mid_point": _optional_float(getattr(tick, "midPoint", None)),
        "exchange": getattr(tick, "exchange", None),
        "special_conditions": getattr(tick, "specialConditions", None),
    }


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _finite_price(value: float | None) -> float | None:
    if value is None or not math.isfinite(value) or value <= 0:
        return None
    return value


def market_reference_price(action: str, market_data: dict[str, Any] | None) -> float | None:
    if not market_data:
        return None
    preferred_field = "ask" if action.upper() == "BUY" else "bid"
    for field in [preferred_field, "last"]:
        price = _finite_price(_optional_float(market_data.get(field)))
        if price is not None:
            return price
    return None


def is_paper_tradeable_market_data_type(value: Any) -> bool:
    return str(value or "").strip().lower() in PAPER_TRADEABLE_MARKET_DATA_TYPES


def is_realtime_market_data_type(value: Any) -> bool:
    return is_paper_tradeable_market_data_type(value)


def _reason_float(reason: str, key: str) -> float | None:
    match = re.search(rf"(?:^|\s|\|){re.escape(key)}=([-+]?\d+(?:\.\d+)?)", reason)
    if not match:
        return None
    return _optional_float(match.group(1))


def submit_ibkr_paper_order(payload: dict[str, Any], *, dry_run: bool = True, ib: Any | None = None) -> dict[str, Any]:
    connection = IBKRConnectionConfig.from_env()
    risk = IBKRPaperRiskConfig.from_env()
    intent = IBKROrderIntent(**payload)
    return IBKRPaperBroker(connection=connection, risk=risk, ib=ib).submit(intent, dry_run=dry_run)


@dataclass
class IBKRPaperTradingSession:
    broker: IBKRPaperBroker
    contract: IBKRContractSpec = IBKRContractSpec()
    max_spread_ticks: float = 4.0
    require_market_data: bool = True
    require_paper_tradeable_market_data: bool = True

    @classmethod
    def from_env(cls, broker: IBKRPaperBroker | None = None) -> "IBKRPaperTradingSession":
        symbol = os.getenv("TRADINGAGENTS_IBKR_SYMBOL", "MNQ")
        point_value = 2.0 if symbol.upper() == "MNQ" else 20.0
        contract = IBKRContractSpec(
            symbol=symbol,
            exchange=os.getenv("TRADINGAGENTS_IBKR_EXCHANGE", "CME"),
            currency=os.getenv("TRADINGAGENTS_IBKR_CURRENCY", "USD"),
            last_trade_date_or_contract_month=os.getenv("TRADINGAGENTS_IBKR_CONTRACT_MONTH", "202606"),
            expected_tick_size=float(os.getenv("TRADINGAGENTS_IBKR_TICK_SIZE", "0.25")),
            expected_point_value=float(os.getenv("TRADINGAGENTS_IBKR_POINT_VALUE", str(point_value))),
        )
        return cls(
            broker=broker or IBKRPaperBroker(),
            contract=contract,
            max_spread_ticks=float(os.getenv("TRADINGAGENTS_IBKR_MAX_SPREAD_TICKS", "4")),
            require_market_data=os.getenv("TRADINGAGENTS_IBKR_REQUIRE_MARKET_DATA", "true").lower() not in {"0", "false", "no"},
            require_paper_tradeable_market_data=os.getenv("TRADINGAGENTS_IBKR_REQUIRE_PAPER_TRADEABLE_MARKET_DATA", "true").lower()
            not in {"0", "false", "no"},
        )

    def preflight(self, *, include_market_data: bool = True) -> dict[str, Any]:
        socket_ready = self._socket_ready()
        connection = self.broker.connect() if socket_ready else {
            "status": "blocked",
            "connected": False,
            "reason": "socket_not_listening",
            "connection": asdict(self.broker.connection),
        }
        account = self.broker.account_summary() if connection.get("connected") else {}
        contract_details = self.broker.contract_details(self.contract) if connection.get("connected") else {}
        market_snapshot = (
            self.broker.market_snapshot(self.contract).to_dict()
            if connection.get("connected") and include_market_data
            else {}
        )
        readiness = self._readiness(
            connection,
            account,
            contract_details,
            market_snapshot if connection.get("connected") and include_market_data else None,
        )
        event = {
            "event_type": "ibkr_paper_preflight",
            "created_at": _now(),
            "socket_ready": socket_ready,
            "connection": connection,
            "account": account,
            "contract": contract_details,
            "market_data": market_snapshot,
            "readiness": readiness,
        }
        self.broker._audit(event)
        return event

    def submit_intent(self, intent: IBKROrderIntent, *, dry_run: bool = True, skip_preflight: bool = False) -> dict[str, Any]:
        normalized = intent.normalized()
        if normalized.symbol != self.contract.symbol:
            normalized = IBKROrderIntent(**(asdict(normalized) | self.contract.to_intent_fields()))
        preflight = None if skip_preflight else self.preflight(include_market_data=not dry_run or self.require_market_data)
        if preflight is not None and preflight["readiness"]["status"] != "ready":
            event = {
                "status": "preflight_blocked",
                "submitted": False,
                "preflight": preflight,
                "intent": asdict(normalized),
                "created_at": _now(),
            }
            self.broker._audit(event)
            return event
        reference_price = market_reference_price(normalized.action, preflight.get("market_data") if preflight else None)
        if reference_price is not None and normalized.stop_loss_price is not None and normalized.take_profit_price is not None:
            stop_distance = _reason_float(normalized.reason, "stop_loss_points")
            target_distance = _reason_float(normalized.reason, "take_profit_points")
            if stop_distance is None:
                stop_distance = abs(float(normalized.stop_loss_price) - reference_price)
            if target_distance is None:
                target_distance = abs(float(normalized.take_profit_price) - reference_price)
            if normalized.action == "BUY":
                stop_loss_price = reference_price - stop_distance
                take_profit_price = reference_price + target_distance
            else:
                stop_loss_price = reference_price + stop_distance
                take_profit_price = reference_price - target_distance
            reason = f"{normalized.reason} | reference_source=current_market_{'ask' if normalized.action == 'BUY' else 'bid'} | reference_price={reference_price:.2f}"
            normalized = IBKROrderIntent(
                **(
                    asdict(normalized)
                    | {
                        "stop_loss_price": round(stop_loss_price, 2),
                        "take_profit_price": round(take_profit_price, 2),
                        "reason": reason,
                    }
                )
            )
        current_position = self.broker.current_position(normalized.symbol) if not dry_run else 0
        response = self.broker.submit(normalized, dry_run=dry_run, current_position=current_position)
        response["preflight"] = preflight
        return response

    def _readiness(
        self,
        connection: dict[str, Any],
        account: dict[str, Any],
        contract_details: dict[str, Any],
        market_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any]:
        missing = []
        if not connection.get("connected"):
            missing.append("not_connected")
        if connection.get("reason") == "configured_account_not_managed":
            missing.append("configured_account_not_managed")
        if account and not account.get("paper"):
            missing.append("paper_account_not_verified")
        if account and self.broker.risk.allowed_accounts and (account.get("account") not in self.broker.risk.allowed_accounts):
            missing.append("account_not_allowed")
        for key in ["symbol", "exchange", "currency"]:
            if contract_details and str(contract_details.get(key)) != str(getattr(self.contract, key)):
                missing.append(f"contract_{key}_mismatch")
        if contract_details:
            if abs(float(contract_details.get("tick_size") or 0) - self.contract.expected_tick_size) > 1e-9:
                missing.append("contract_tick_size_mismatch")
            if abs(float(contract_details.get("point_value") or 0) - self.contract.expected_point_value) > 1e-9:
                missing.append("contract_point_value_mismatch")
        if market_snapshot is not None and self.require_market_data:
            if not market_snapshot.get("order_ready"):
                missing.append("market_data_not_ready")
                for field in ["bid", "ask", "last"]:
                    if _finite_price(market_snapshot.get(field)) is None:
                        missing.append(f"market_data_missing_{field}")
            if self.require_paper_tradeable_market_data and not is_paper_tradeable_market_data_type(market_snapshot.get("market_data_type")):
                missing.append("market_data_not_paper_tradeable")
            spread = market_snapshot.get("spread")
            if spread is not None and spread > self.max_spread_ticks * self.contract.expected_tick_size:
                missing.append("spread_too_wide")
        return {
            "status": "ready" if not missing else "blocked",
            "missing_requirements": missing,
            "checked_at": _now(),
        }

    def _socket_ready(self) -> bool:
        try:
            with socket.create_connection((self.broker.connection.host, self.broker.connection.port), timeout=1.0):
                return True
        except OSError:
            return False
