from pathlib import Path
import math
import json
from types import SimpleNamespace

import pandas as pd

from tradingagents.execution.ibkr import (
    IBKRConnectionConfig,
    IBKRContractSpec,
    IBKRMarketSnapshot,
    IBKROrderIntent,
    IBKRPaperBroker,
    IBKRPaperRiskConfig,
    IBKRPaperTradingSession,
    _bracket_protection_status,
    evaluate_paper_risk,
    market_reference_price,
)
from tradingagents.execution.tick_recorder import IBKRTickRecorderConfig, record_ibkr_ticks
from tradingagents.execution.tick_replay import TickReplayDatasetConfig, build_tick_replay_dataset


class FakeFuture:
    def __init__(self, symbol, lastTradeDateOrContractMonth, exchange, currency):
        self.symbol = symbol
        self.lastTradeDateOrContractMonth = lastTradeDateOrContractMonth
        self.exchange = exchange
        self.currency = currency
        self.secType = "FUT"


class FakeOrder:
    def __init__(self):
        self.action = None
        self.totalQuantity = None
        self.orderType = None
        self.lmtPrice = None
        self.account = None
        self.transmit = True


class FakeIB:
    def __init__(self, connect_error=None):
        self.connected = False
        self.placed_orders = []
        self.connect_error = connect_error
        self.client = SimpleNamespace(getReqId=lambda: 1001)

    def connect(self, host, port, clientId, timeout, readonly):
        if self.connect_error is not None:
            raise self.connect_error
        self.connected = True
        self.connection = {
            "host": host,
            "port": port,
            "clientId": clientId,
            "timeout": timeout,
            "readonly": readonly,
        }

    def qualifyContracts(self, contract):
        return [contract]

    def placeOrder(self, contract, order):
        status = "Filled" if order.orderType == "MKT" else "Submitted"
        filled = order.totalQuantity if order.orderType == "MKT" else 0
        remaining = 0 if order.orderType == "MKT" else order.totalQuantity
        trade = SimpleNamespace(order=order, orderStatus=SimpleNamespace(status=status, filled=filled, remaining=remaining))
        self.placed_orders.append((contract, order))
        return trade

    def bracketOrder(self, action, quantity, limitPrice, takeProfitPrice, stopLossPrice):
        parent = FakeOrder()
        parent.action = action
        parent.totalQuantity = quantity
        parent.orderType = "LMT"
        parent.lmtPrice = limitPrice
        parent.transmit = False
        take_profit = FakeOrder()
        take_profit.action = "SELL" if action == "BUY" else "BUY"
        take_profit.totalQuantity = quantity
        take_profit.orderType = "LMT"
        take_profit.lmtPrice = takeProfitPrice
        take_profit.transmit = False
        stop = FakeOrder()
        stop.action = take_profit.action
        stop.totalQuantity = quantity
        stop.orderType = "STP"
        stop.auxPrice = stopLossPrice
        stop.transmit = True
        return [parent, take_profit, stop]

    def isConnected(self):
        return self.connected

    def accountSummary(self):
        return [
            SimpleNamespace(account="DU123", tag="AccountType", value="paper"),
            SimpleNamespace(account="DU123", tag="NetLiquidation", value="100000"),
        ]

    def positions(self):
        return []

    def openTrades(self):
        return []

    def fills(self):
        return []

    def reqContractDetails(self, contract):
        contract.multiplier = "2" if contract.symbol == "MNQ" else "20"
        return [SimpleNamespace(contract=contract, minTick=0.25)]

    def reqMktData(self, contract, genericTickList, snapshot, regulatorySnapshot):
        return SimpleNamespace(bid=18000.0, ask=18000.25, last=18000.25, marketDataType="delayed")

    def reqTickByTickData(self, contract, tickType, numberOfTicks, ignoreSize):
        return SimpleNamespace(
            tickByTicks=[
                SimpleNamespace(time="2026-05-01T10:30:00Z", bidPrice=18000.0, askPrice=18000.25, bidSize=3, askSize=4),
                SimpleNamespace(time="2026-05-01T10:30:01Z", price=18000.25, size=1, exchange="CME"),
            ]
        )

    def cancelTickByTickData(self, ticker):
        self.cancelled_tick_ticker = ticker

    def sleep(self, seconds):
        return


class MarketDataTypeFakeIB(FakeIB):
    def __init__(self):
        super().__init__()
        self.market_data_types = []
        self.current_market_data_type = None

    def reqMarketDataType(self, market_data_type):
        self.current_market_data_type = market_data_type
        self.market_data_types.append(market_data_type)

    def reqMktData(self, contract, genericTickList, snapshot, regulatorySnapshot):
        if self.current_market_data_type == 3:
            return SimpleNamespace(bid=18000.0, ask=18000.25, last=18000.25, marketDataType="delayed")
        return SimpleNamespace(bid=None, ask=None, last=None, marketDataType=str(self.current_market_data_type))


class FailsOnSecondConnectIB(FakeIB):
    def __init__(self):
        super().__init__()
        self.connect_calls = 0

    def connect(self, host, port, clientId, timeout, readonly):
        self.connect_calls += 1
        if self.connect_calls > 1:
            raise ConnectionError("second connect failed")
        super().connect(host, port, clientId, timeout, readonly)


def _intent(**overrides):
    values = {
        "action": "BUY",
        "quantity": 1,
        "symbol": "MNQ",
        "last_trade_date_or_contract_month": "202606",
        "stop_loss_price": 18000.0,
        "take_profit_price": 18100.0,
        "account": "DU123",
    }
    values.update(overrides)
    return IBKROrderIntent(**values)


def _risk():
    return IBKRPaperRiskConfig(allowed_accounts=("DU123",), allowed_symbols=("MNQ",), max_quantity=1)


def test_paper_risk_rejects_non_paper_port():
    risk = evaluate_paper_risk(_intent().normalized(), IBKRConnectionConfig(port=7496, account="DU123"), _risk())

    assert not risk["passed"]
    assert "non_paper_port" in risk["reasons"]


def test_paper_risk_requires_bracket_for_entry():
    intent = _intent(stop_loss_price=None, take_profit_price=None).normalized()
    risk = evaluate_paper_risk(intent, IBKRConnectionConfig(port=7497, account="DU123"), _risk())

    assert not risk["passed"]
    assert "bracket_required" in risk["reasons"]


def test_dry_run_does_not_connect_or_submit(tmp_path, monkeypatch):
    monkeypatch.setattr("tradingagents.execution.ibkr._load_ib_class", lambda name: FakeFuture if name == "Future" else FakeOrder)
    fake_ib = FakeIB()
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(port=7497, account="DU123"),
        risk=_risk(),
        ib=fake_ib,
        audit_path=tmp_path / "audit.jsonl",
    )

    response = broker.submit(_intent(), dry_run=True)

    assert response["status"] == "dry_run"
    assert not fake_ib.connected
    assert not fake_ib.placed_orders
    assert response["connection"]["host"] == "127.0.0.1"
    assert (tmp_path / "audit.jsonl").exists()


def test_submit_places_bracket_order_on_fake_ib(tmp_path, monkeypatch):
    monkeypatch.setattr("tradingagents.execution.ibkr._load_ib_class", lambda name: FakeFuture if name == "Future" else FakeOrder)
    fake_ib = FakeIB()
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(port=7497, account="DU123"),
        risk=_risk(),
        ib=fake_ib,
        audit_path=tmp_path / "audit.jsonl",
    )

    response = broker.submit(_intent(), dry_run=False)

    assert response["status"] == "submitted"
    assert fake_ib.connected
    assert len(fake_ib.placed_orders) == 3
    assert response["submitted"]
    assert response["orders"][0]["orderType"] == "MKT"
    assert response["orders"][1]["openClose"] == "C"
    assert response["orders"][2]["openClose"] == "C"
    assert response["protection"]["active"]


def test_bracket_protection_requires_target_and_stop():
    stop_order = SimpleNamespace(orderType="STP")
    stop_trade = SimpleNamespace(order=stop_order, orderStatus=SimpleNamespace(status="PreSubmitted"))

    protection = _bracket_protection_status([stop_trade])

    assert not protection["active"]
    assert protection["order_types"] == ["STP"]


def test_submit_uses_created_ib_for_bracket_order(tmp_path, monkeypatch):
    fake_ib = FakeIB()

    def fake_loader(name):
        if name == "IB":
            return lambda: fake_ib
        if name == "Future":
            return FakeFuture
        return FakeOrder

    monkeypatch.setattr("tradingagents.execution.ibkr._load_ib_class", fake_loader)
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(port=7497, account="DU123"),
        risk=_risk(),
        audit_path=tmp_path / "audit.jsonl",
    )

    response = broker.submit(_intent(), dry_run=False)

    assert response["status"] == "submitted"
    assert len(fake_ib.placed_orders) == 3
    assert response["orders"][1]["orderType"] == "LMT"
    assert response["orders"][2]["orderType"] == "STP"


def test_submit_reuses_existing_ib_connection(tmp_path, monkeypatch):
    monkeypatch.setattr("tradingagents.execution.ibkr._load_ib_class", lambda name: FakeFuture if name == "Future" else FakeOrder)
    fake_ib = FailsOnSecondConnectIB()
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(port=7497, account="DU123"),
        risk=_risk(),
        ib=fake_ib,
        audit_path=tmp_path / "audit.jsonl",
    )
    broker.connect()

    response = broker.submit(_intent(), dry_run=False)

    assert response["status"] == "submitted"
    assert fake_ib.connect_calls == 1


def test_paper_session_preflight_ready_with_paper_account(tmp_path, monkeypatch):
    fake_ib = FakeIB()
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(port=7497, account="DU123"),
        risk=_risk(),
        ib=fake_ib,
        audit_path=tmp_path / "audit.jsonl",
    )
    session = IBKRPaperTradingSession(broker=broker, contract=IBKRContractSpec(last_trade_date_or_contract_month="202606"))
    monkeypatch.setattr(session, "_socket_ready", lambda: True)

    response = session.preflight()

    assert response["readiness"]["status"] == "ready"
    assert response["account"]["paper"]
    assert response["market_data"]["order_ready"]


def test_market_snapshot_qualifies_contract_and_retries_market_data_types(tmp_path):
    fake_ib = MarketDataTypeFakeIB()
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(port=7497, account="DU123"),
        risk=_risk(),
        ib=fake_ib,
        audit_path=tmp_path / "audit.jsonl",
    )

    snapshot = broker.market_snapshot(IBKRContractSpec(last_trade_date_or_contract_month="202606"))

    assert snapshot.order_ready
    assert snapshot.market_data_type == "delayed"
    assert fake_ib.market_data_types == [1, 2, 3]


def test_market_reference_price_uses_action_side():
    market_data = {"bid": 18000.0, "ask": 18001.0, "last": 18000.5}

    assert market_reference_price("BUY", market_data) == 18001.0
    assert market_reference_price("SELL", market_data) == 18000.0


def test_paper_session_reprices_bracket_from_current_market_on_preflight(tmp_path, monkeypatch):
    fake_ib = FakeIB()
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(port=7497, account="DU123"),
        risk=_risk(),
        ib=fake_ib,
        audit_path=tmp_path / "audit.jsonl",
    )
    session = IBKRPaperTradingSession(broker=broker, contract=IBKRContractSpec(last_trade_date_or_contract_month="202606"))
    monkeypatch.setattr(session, "_socket_ready", lambda: True)

    response = session.submit_intent(
        _intent(
            action="BUY",
            stop_loss_price=17990.0,
            take_profit_price=18020.0,
            reason="stop_loss_points=10.0000 | take_profit_points=20.0000",
        ),
        dry_run=True,
    )

    assert response["status"] == "dry_run"
    assert response["intent"]["stop_loss_price"] == 17990.25
    assert response["intent"]["take_profit_price"] == 18020.25
    assert "reference_source=current_market_ask" in response["intent"]["reason"]


def test_paper_session_blocks_when_socket_not_ready(tmp_path, monkeypatch):
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(port=7497, account="DU123"),
        risk=_risk(),
        ib=FakeIB(),
        audit_path=tmp_path / "audit.jsonl",
    )
    session = IBKRPaperTradingSession(broker=broker)
    monkeypatch.setattr(session, "_socket_ready", lambda: False)

    response = session.preflight()

    assert response["readiness"]["status"] == "blocked"
    assert "not_connected" in response["readiness"]["missing_requirements"]
    assert "market_data_not_ready" not in response["readiness"]["missing_requirements"]


def test_paper_session_blocks_connect_failure(tmp_path, monkeypatch):
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(port=7497, account="DU123"),
        risk=_risk(),
        ib=FakeIB(connect_error=TimeoutError("client id already in use")),
        audit_path=tmp_path / "audit.jsonl",
    )
    session = IBKRPaperTradingSession(broker=broker)
    monkeypatch.setattr(session, "_socket_ready", lambda: True)

    response = session.preflight()

    assert response["readiness"]["status"] == "blocked"
    assert response["connection"]["status"] == "connect_failed"
    assert "not_connected" in response["readiness"]["missing_requirements"]


def test_paper_session_blocks_wide_spread(tmp_path, monkeypatch):
    fake_ib = FakeIB()
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(port=7497, account="DU123"),
        risk=_risk(),
        ib=fake_ib,
        audit_path=tmp_path / "audit.jsonl",
    )
    session = IBKRPaperTradingSession(broker=broker, max_spread_ticks=1.0)
    monkeypatch.setattr(session, "_socket_ready", lambda: True)
    monkeypatch.setattr(
        broker,
        "market_snapshot",
        lambda spec: IBKRMarketSnapshot(symbol="NQ", bid=18000.0, ask=18001.0, last=18000.25, snapshot_time="now"),
    )

    response = session.preflight()

    assert response["readiness"]["status"] == "blocked"
    assert "spread_too_wide" in response["readiness"]["missing_requirements"]


def test_market_snapshot_nan_prices_are_not_order_ready():
    snapshot = IBKRMarketSnapshot(
        symbol="NQ",
        bid=math.nan,
        ask=math.nan,
        last=math.nan,
        snapshot_time="now",
    )

    assert snapshot.to_dict()["bid"] is None
    assert not snapshot.to_dict()["order_ready"]


def test_paper_session_reports_specific_missing_market_data_fields(tmp_path, monkeypatch):
    fake_ib = FakeIB()
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(port=7497, account="DU123"),
        risk=_risk(),
        ib=fake_ib,
        audit_path=tmp_path / "audit.jsonl",
    )
    session = IBKRPaperTradingSession(broker=broker)
    monkeypatch.setattr(session, "_socket_ready", lambda: True)
    monkeypatch.setattr(
        broker,
        "market_snapshot",
        lambda spec: IBKRMarketSnapshot(symbol="NQ", bid=None, ask=None, last=18000.25, snapshot_time="now"),
    )

    response = session.preflight()

    missing = response["readiness"]["missing_requirements"]
    assert "market_data_not_ready" in missing
    assert "market_data_missing_bid" in missing
    assert "market_data_missing_ask" in missing
    assert "market_data_missing_last" not in missing


def test_market_snapshot_negative_prices_are_not_order_ready():
    snapshot = IBKRMarketSnapshot(
        symbol="NQ",
        bid=-1.0,
        ask=-1.0,
        last=27783.25,
        snapshot_time="now",
    )

    assert snapshot.to_dict()["bid"] is None
    assert snapshot.to_dict()["ask"] is None
    assert not snapshot.to_dict()["order_ready"]


def test_broker_status_snapshot_includes_positions_orders_and_fills(tmp_path):
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(port=7497, account="DU123"),
        risk=_risk(),
        ib=FakeIB(),
        audit_path=tmp_path / "audit.jsonl",
    )

    snapshot = broker.status_snapshot("NQ")

    assert snapshot["positions"] == []
    assert snapshot["current_position"] == 0
    assert snapshot["open_trades"] == []
    assert snapshot["fills"] == []


def test_tick_recorder_writes_jsonl_snapshots(tmp_path):
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(port=7497, account="DU123"),
        risk=_risk(),
        ib=FakeIB(),
        audit_path=tmp_path / "audit.jsonl",
    )

    result = record_ibkr_ticks(
        broker=broker,
        config=IBKRTickRecorderConfig(output_dir=tmp_path / "ticks", enabled=True, max_ticks=2, interval_seconds=0),
        intent_id="intent-1",
        candidate_key="candidate-1",
        strategy_id="strategy-1",
    )

    assert result["status"] == "recorded"
    assert result["ticks"] == 4
    output = Path(result["output"])
    rows = output.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 4
    assert "ibkr_paper_tick" in rows[0]
    assert "intent-1" in rows[0]
    assert "ibkr_tick_by_tick" in rows[0]


def test_tick_replay_dataset_normalizes_tick_files(tmp_path):
    input_dir = tmp_path / "ticks"
    input_dir.mkdir()
    tick_file = input_dir / "NQ-202606-intent-1.jsonl"
    tick_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_type": "ibkr_paper_tick",
                        "intent_id": "intent-1",
                        "candidate_key": "candidate-1",
                        "strategy_id": "strategy-1",
                        "tick_index": 0,
                        "tick_event_index": 0,
                        "source_event_type": "ibkr_tick_by_tick",
                        "time": "2026-05-01T10:30:00Z",
                        "bid_price": 18000.0,
                        "ask_price": 18000.25,
                        "bid_size": 3,
                        "ask_size": 4,
                    }
                ),
                json.dumps(
                    {
                        "event_type": "ibkr_paper_tick",
                        "intent_id": "intent-1",
                        "candidate_key": "candidate-1",
                        "strategy_id": "strategy-1",
                        "tick_index": 1,
                        "tick_event_index": 0,
                        "source_event_type": "ibkr_tick_snapshot",
                        "snapshot_time": "2026-05-01T10:30:01Z",
                        "bid": 18000.25,
                        "ask": 18000.5,
                        "last": 18000.25,
                    }
                ),
                json.dumps({"event_type": "ibkr_paper_tick_error", "reason": "market_data_not_ready"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    dataset, summary = build_tick_replay_dataset(
        TickReplayDatasetConfig(
            input_dir=input_dir,
            output=tmp_path / "replay.csv",
            summary_output=tmp_path / "summary.csv",
        )
    )

    assert len(dataset) == 2
    assert dataset.iloc[0]["spread"] == 0.25
    assert dataset.iloc[1]["last"] == 18000.25
    assert summary.iloc[0]["ticks"] == 2
    assert summary.iloc[0]["error_rows"] == 1
    assert pd.read_csv(tmp_path / "replay.csv").shape[0] == 2


def test_paper_session_submit_uses_current_position_for_risk(tmp_path, monkeypatch):
    fake_ib = FakeIB()
    broker = IBKRPaperBroker(
        connection=IBKRConnectionConfig(port=7497, account="DU123"),
        risk=_risk(),
        ib=fake_ib,
        audit_path=tmp_path / "audit.jsonl",
    )
    session = IBKRPaperTradingSession(broker=broker)
    monkeypatch.setattr(session, "_socket_ready", lambda: True)
    monkeypatch.setattr(broker, "current_position", lambda symbol: 1)

    response = session.submit_intent(_intent(action="BUY"), dry_run=False)

    assert response["status"] == "risk_rejected"
    assert "position_after_fill_exceeds_limit" in response["risk"]["reasons"]
