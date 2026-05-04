from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pandas as pd

from tradingagents.execution import (
    BEST_MEAN_REVERSION_ALIAS,
    BEST_MEAN_REVERSION_STRATEGY_ID,
    IBKRConnectionConfig,
    IBKRContractSpec,
    IBKRPaperBroker,
    IBKRPaperRiskConfig,
    LivePaperTraderConfig,
    LiveStrategySpec,
    LiveStrategySignalConfig,
    evaluate_mean_reversion_signal,
    run_live_paper_trader_once,
)


class FakeIB:
    def __init__(
        self,
        *,
        bid: float = 100.0,
        ask: float = 100.25,
        last: float = 100.0,
        bid_size: float | None = 8.0,
        ask_size: float | None = 2.0,
    ):
        self.connected = False
        self.bid = bid
        self.ask = ask
        self.last = last
        self.bid_size = bid_size
        self.ask_size = ask_size

    def connect(self, host, port, clientId, timeout, readonly):
        self.connected = True

    def isConnected(self):
        return self.connected

    def positions(self):
        return []

    def openTrades(self):
        return []

    def fills(self):
        return []

    def qualifyContracts(self, contract):
        return [contract]

    def reqMarketDataType(self, market_data_type):
        return None

    def reqMktData(self, contract, genericTickList, snapshot, regulatorySnapshot):
        return SimpleNamespace(
            bid=self.bid,
            ask=self.ask,
            last=self.last,
            bidSize=self.bid_size,
            askSize=self.ask_size,
            marketDataType="delayed",
        )

    def reqTickByTickData(self, contract, tickType, numberOfTicks, ignoreSize):
        return SimpleNamespace(
            tickByTicks=[
                SimpleNamespace(
                    time="2026-05-04T10:00:00Z",
                    bidPrice=100.0,
                    askPrice=100.25,
                    bidSize=self.bid_size,
                    askSize=self.ask_size,
                )
            ]
        )

    def cancelTickByTickData(self, ticker):
        return None

    def sleep(self, seconds):
        return None


def _bars(*, prices: list[float], imbalance: float | None, start: datetime | None = None) -> pd.DataFrame:
    start = start or datetime(2026, 5, 4, 10, 0, tzinfo=UTC)
    return pd.DataFrame(
        {
            "ts": [start + timedelta(minutes=index) for index in range(len(prices))],
            "Open": prices,
            "High": prices,
            "Low": prices,
            "Close": prices,
            "imbalance_last": [imbalance] * len(prices),
        }
    )


def _broker(tmp_path, fake_ib: FakeIB) -> IBKRPaperBroker:
    return IBKRPaperBroker(
        connection=IBKRConnectionConfig(port=7497, account="DU123"),
        risk=IBKRPaperRiskConfig(allowed_accounts=("DU123",), allowed_symbols=("MNQ",), max_quantity=1),
        ib=fake_ib,
        audit_path=tmp_path / "audit.jsonl",
    )


def test_mean_reversion_blocks_without_imbalance():
    evaluation = evaluate_mean_reversion_signal(_bars(prices=[100, 100, 100, 100, 100, 100, 98], imbalance=None))

    assert not evaluation["triggered"]
    assert evaluation["reason"] == "missing_imbalance"


def test_mean_reversion_triggers_long_when_z_and_imbalance_align():
    evaluation = evaluate_mean_reversion_signal(_bars(prices=[100, 100, 100, 100, 100, 100, 98], imbalance=0.6))

    assert evaluation["triggered"]
    assert evaluation["direction"] == 1
    assert evaluation["side"] == "long_mean_reversion"


def test_mean_reversion_triggers_short_when_z_and_imbalance_align():
    evaluation = evaluate_mean_reversion_signal(_bars(prices=[100, 100, 100, 100, 100, 100, 102], imbalance=-0.6))

    assert evaluation["triggered"]
    assert evaluation["direction"] == -1
    assert evaluation["side"] == "short_mean_reversion"


def test_mean_reversion_allows_reentry_when_signal_state_repeats():
    evaluation = evaluate_mean_reversion_signal(_bars(prices=[100, 100, 100, 100, 100, 102, 104], imbalance=-0.6))

    assert evaluation["triggered"]
    assert evaluation["direction"] == -1
    assert evaluation["previous_direction"] == -1


def test_mean_reversion_honors_configured_min_bars():
    evaluation = evaluate_mean_reversion_signal(
        _bars(prices=[100, 100, 100, 100, 100, 100, 98], imbalance=0.6),
        min_bars=8,
    )

    assert not evaluation["triggered"]
    assert evaluation["reason"] == "insufficient_bars"
    assert evaluation["required_bars"] == 8


def test_mean_reversion_all_session_allows_non_europe_window():
    start = datetime(2026, 5, 4, 20, 0, tzinfo=UTC)
    evaluation = evaluate_mean_reversion_signal(
        _bars(prices=[100, 100, 100, 100, 100, 100, 98], imbalance=0.6, start=start),
        spec=LiveStrategySpec(session="all"),
    )

    assert evaluation["triggered"]
    assert evaluation["session"] == "all"
    assert evaluation["minute_of_day"] == 20 * 60 + 6


def test_live_trader_blocks_when_strategy_history_is_insufficient(tmp_path):
    broker = _broker(tmp_path, FakeIB())
    result = run_live_paper_trader_once(
        config=LivePaperTraderConfig(
            live_signal_path=tmp_path / "signal.csv",
            state_path=tmp_path / "state.json",
            strategy_id=BEST_MEAN_REVERSION_STRATEGY_ID,
            selected_alias=BEST_MEAN_REVERSION_ALIAS,
            signal_mode="strategy",
            contract=IBKRContractSpec(last_trade_date_or_contract_month="202606"),
            strategy_signal=LiveStrategySignalConfig(history_path=tmp_path / "history.jsonl", tick_interval_seconds=0),
        ),
        broker=broker,
    )

    assert result["status"] == "signal_blocked"
    assert "insufficient_bars" in result["reason"]
    assert not result["submitted"]
    assert not (tmp_path / "signal.csv").exists()


def test_live_trader_blocks_when_live_imbalance_is_missing(tmp_path, monkeypatch):
    history_path = tmp_path / "history.jsonl"
    start = datetime(2026, 5, 4, 10, 0, tzinfo=UTC)
    monkeypatch.setattr("tradingagents.execution.live_strategy._utc_now", lambda value=None: start + timedelta(minutes=6))
    with history_path.open("w", encoding="utf-8") as handle:
        for index, price in enumerate([100, 100, 100, 100, 100, 100]):
            handle.write(
                json.dumps(
                    {
                        "event_type": "ibkr_live_market_event",
                        "ts": (start + timedelta(minutes=index)).isoformat(),
                        "bid": price,
                        "ask": price + 0.25,
                        "last": price,
                        "mid": price + 0.125,
                        "imbalance_last": 0.6,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    broker = _broker(tmp_path, FakeIB(bid=98.0, ask=98.25, last=98.0, bid_size=None, ask_size=None))
    result = run_live_paper_trader_once(
        config=LivePaperTraderConfig(
            live_signal_path=tmp_path / "signal.csv",
            state_path=tmp_path / "state.json",
            strategy_id=BEST_MEAN_REVERSION_STRATEGY_ID,
            selected_alias=BEST_MEAN_REVERSION_ALIAS,
            signal_mode="strategy",
            contract=IBKRContractSpec(last_trade_date_or_contract_month="202606"),
            strategy_signal=LiveStrategySignalConfig(history_path=history_path, max_history_minutes=10000, tick_interval_seconds=0),
        ),
        broker=broker,
    )

    assert result["status"] == "signal_blocked"
    assert "missing_imbalance" in result["reason"]
    assert not result["submitted"]


def test_live_trader_uses_snapshot_sizes_when_tick_by_tick_is_empty(tmp_path, monkeypatch):
    history_path = tmp_path / "history.jsonl"
    start = datetime(2026, 5, 4, 10, 0, tzinfo=UTC)
    monkeypatch.setattr("tradingagents.execution.live_strategy._utc_now", lambda value=None: start + timedelta(minutes=6))
    with history_path.open("w", encoding="utf-8") as handle:
        for index, price in enumerate([100, 100, 100, 100, 100, 100]):
            handle.write(
                json.dumps(
                    {
                        "event_type": "ibkr_live_market_event",
                        "ts": (start + timedelta(minutes=index)).isoformat(),
                        "bid": price,
                        "ask": price + 0.25,
                        "last": price,
                        "mid": price + 0.125,
                        "imbalance_last": 0.6,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    fake_ib = FakeIB(bid=98.0, ask=98.25, last=98.0, bid_size=8.0, ask_size=2.0)
    fake_ib.reqTickByTickData = lambda contract, tickType, numberOfTicks, ignoreSize: SimpleNamespace(tickByTicks=[])
    broker = _broker(tmp_path, fake_ib)

    result = run_live_paper_trader_once(
        config=LivePaperTraderConfig(
            live_signal_path=tmp_path / "signal.csv",
            state_path=tmp_path / "state.json",
            strategy_id=BEST_MEAN_REVERSION_STRATEGY_ID,
            selected_alias=BEST_MEAN_REVERSION_ALIAS,
            signal_mode="strategy",
            contract=IBKRContractSpec(last_trade_date_or_contract_month="202606"),
            strategy_signal=LiveStrategySignalConfig(history_path=history_path, max_history_minutes=10000, tick_interval_seconds=0),
        ),
        broker=broker,
    )

    assert result["status"] == "dry_run"
    latest_event = json.loads(history_path.read_text(encoding="utf-8").splitlines()[-1])
    assert latest_event["tick_events"] == 0
    assert latest_event["bid_size"] == 8.0
    assert latest_event["ask_size"] == 2.0
    assert latest_event["imbalance_last"] == 0.6


def test_manual_mode_requires_explicit_direction_and_can_dry_run(tmp_path):
    broker = _broker(tmp_path, FakeIB())
    result = run_live_paper_trader_once(
        config=LivePaperTraderConfig(
            live_signal_path=tmp_path / "signal.csv",
            state_path=tmp_path / "state.json",
            strategy_id=BEST_MEAN_REVERSION_STRATEGY_ID,
            selected_alias=BEST_MEAN_REVERSION_ALIAS,
            direction=1,
            signal_mode="manual",
            contract=IBKRContractSpec(last_trade_date_or_contract_month="202606"),
        ),
        broker=broker,
    )

    assert result["status"] == "dry_run"
    assert result["submitted"] is False
    assert (tmp_path / "signal.csv").exists()
