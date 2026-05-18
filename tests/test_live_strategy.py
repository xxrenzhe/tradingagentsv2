from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pandas as pd

from tradingagents.execution import (
    BA_NO_TRADE_COMBO_ALIAS,
    BA_NO_TRADE_COMBO_STRATEGY_ID,
    BEST_MEAN_REVERSION_ALIAS,
    BEST_MEAN_REVERSION_STRATEGY_ID,
    IBKRConnectionConfig,
    IBKRContractSpec,
    IBKRPaperBroker,
    IBKRPaperRiskConfig,
    LivePaperTraderConfig,
    LiveStrategySpec,
    LiveStrategySignalConfig,
    ba_no_trade_combo_spec,
    evaluate_ba_no_trade_combo_signal,
    evaluate_mean_reversion_signal,
    evaluate_regime_transition_signal,
    regime_transition_spec,
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

    def reqHistoricalData(self, contract, endDateTime, durationStr, barSizeSetting, whatToShow, useRTH, formatDate):
        return [
            SimpleNamespace(
                date=row["ts"].to_pydatetime(),
                open=row["Open"],
                high=row["High"],
                low=row["Low"],
                close=row["Close"],
                volume=row.get("Volume", 0),
                wap=row["Close"],
                barCount=1,
            )
            for _, row in _regime_bars().iterrows()
        ]

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


def _regime_bars(*, include_volume: bool = True) -> pd.DataFrame:
    start = datetime(2026, 5, 4, 20, 0, tzinfo=UTC)
    rows = []
    price = 100.0
    for index in range(180):
        timestamp = start + timedelta(minutes=index)
        if index < 179:
            open_price = price
            close = price + (0.02 if index % 2 == 0 else -0.02)
            high = max(open_price, close) + 0.08
            low = min(open_price, close) - 0.08
            price = close
            volume = 100.0
        else:
            open_price = 100.0
            close = 112.0
            high = 112.5
            low = 99.0
            volume = 400.0
            price = close
        rows.append(
            {
                "ts": timestamp,
                "Open": open_price,
                "High": high,
                "Low": low,
                "Close": close,
                "imbalance_last": 0.0,
                **({"Volume": volume} if include_volume else {}),
            }
        )
    return pd.DataFrame(rows)


def _ba_combo_bars(*, side: str = "long") -> pd.DataFrame:
    start = datetime(2026, 5, 4, 18 if side == "long" else 1, 0, tzinfo=UTC)
    rows = []
    price = 120.0 if side == "short" else 100.0
    row_count = 229 if side == "long" else 230
    for index in range(row_count):
        timestamp = start + timedelta(minutes=index)
        if side == "long":
            base = 100 + (index % 20 - 10) * 0.25
            open_price = base
            close = base + (0.2 if index % 2 == 0 else -0.2)
            high = max(open_price, close) + 2.0
            low = min(open_price, close) - 2.0
            volume = 100.0
            price = close
        else:
            open_price = price
            if index < 210:
                close = price - 0.08
                high = open_price + 2.0
                low = close - 2.0
                volume = 100.0
            else:
                close = price - 3.2
                high = open_price + 1.0
                low = close + 0.2
                volume = 300.0
            price = close
        rows.append(
            {
                "ts": timestamp,
                "Open": open_price,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": volume,
                "imbalance_last": 0.0,
            }
        )
    if side == "long":
        rows.append(
            {
                "ts": start + timedelta(minutes=229),
                "Open": 98.0,
                "High": 101.5,
                "Low": 93.0,
                "Close": 100.8,
                "Volume": 300.0,
                "imbalance_last": 0.0,
            }
        )
    return pd.DataFrame(rows)


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


def test_regime_transition_triggers_long_breakout_with_dynamic_bracket():
    spec = LiveStrategySpec(
        strategy_id="test_regime",
        selected_alias="test_regime",
        family="regime_transition",
        session="us_late",
        lookback=50,
        width_atr_max=20.0,
        efficiency_max=0.30,
        displacement_atr_min=1.0,
        body_share_min=0.50,
        volume_z_min=0.0,
        reward_risk=2.5,
        max_hold_minutes=180,
    )

    evaluation = evaluate_regime_transition_signal(_regime_bars(), spec)

    assert evaluation["triggered"]
    assert evaluation["direction"] == 1
    assert evaluation["side"] == "long_regime_transition"
    assert evaluation["stop_points"] > 4.0
    assert evaluation["target_points"] == evaluation["stop_points"] * 2.5
    assert evaluation["horizon_minutes"] == 180


def test_regime_transition_blocks_volume_filtered_strategy_without_volume():
    spec = regime_transition_spec("optimized50_2r5_quality")

    evaluation = evaluate_regime_transition_signal(_regime_bars(include_volume=False), spec)

    assert not evaluation["triggered"]
    assert evaluation["reason"] == "missing_volume_for_volume_z"


def test_ba_no_trade_combo_triggers_long_with_dynamic_bracket():
    evaluation = evaluate_ba_no_trade_combo_signal(_ba_combo_bars(side="long"), ba_no_trade_combo_spec())

    assert evaluation["triggered"]
    assert evaluation["direction"] == 1
    assert evaluation["leg"] == "BA"
    assert evaluation["stop_points"] >= 4.0
    assert evaluation["target_points"] == evaluation["stop_points"] * 2.5


def test_ba_no_trade_combo_triggers_short_with_dynamic_bracket():
    evaluation = evaluate_ba_no_trade_combo_signal(_ba_combo_bars(side="short"), ba_no_trade_combo_spec())

    assert evaluation["triggered"]
    assert evaluation["direction"] == -1
    assert evaluation["leg"] == "BA"
    assert evaluation["stop_points"] >= 4.0


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


def test_live_trader_regime_transition_uses_historical_ohlcv_bars(tmp_path, monkeypatch):
    start = datetime(2026, 5, 4, 22, 59, tzinfo=UTC)
    monkeypatch.setattr("tradingagents.execution.live_strategy._utc_now", lambda value=None: start)
    broker = _broker(tmp_path, FakeIB(bid=112.0, ask=112.25, last=112.0))

    result = run_live_paper_trader_once(
        config=LivePaperTraderConfig(
            live_signal_path=tmp_path / "signal.csv",
            state_path=tmp_path / "state.json",
            strategy_id="optimized50_2r5_quality",
            selected_alias="optimized50_2r5_quality",
            signal_mode="strategy",
            strategy_spec=regime_transition_spec("optimized50_2r5_quality"),
            contract=IBKRContractSpec(last_trade_date_or_contract_month="202606"),
            strategy_signal=LiveStrategySignalConfig(history_path=tmp_path / "history.jsonl", tick_interval_seconds=0, min_bars=171),
            max_hold_minutes=180,
        ),
        broker=broker,
    )

    assert result["status"] == "dry_run"
    assert result["live_signal"]["signal_source"].startswith("strategy:optimized50_2r5_quality:long_regime_transition")
    assert float(result["live_signal"]["strategy_stop_points"]) > 4.0
    assert float(result["live_signal"]["strategy_target_points"]) > float(result["live_signal"]["strategy_stop_points"])
    signal = pd.read_csv(tmp_path / "signal.csv")
    assert float(signal.iloc[0]["strategy_volume_z"]) >= 0.5


def test_live_trader_ba_no_trade_combo_uses_historical_ohlcv_bars(tmp_path, monkeypatch):
    start = datetime(2026, 5, 4, 21, 49, tzinfo=UTC)
    monkeypatch.setattr("tradingagents.execution.live_strategy._utc_now", lambda value=None: start)
    fake_ib = FakeIB(bid=114.0, ask=114.25, last=114.0)
    fake_ib.reqHistoricalData = lambda contract, endDateTime, durationStr, barSizeSetting, whatToShow, useRTH, formatDate: [
        SimpleNamespace(
            date=row["ts"].to_pydatetime(),
            open=row["Open"],
            high=row["High"],
            low=row["Low"],
            close=row["Close"],
            volume=row["Volume"],
            wap=row["Close"],
            barCount=1,
        )
        for _, row in _ba_combo_bars(side="long").iterrows()
    ]
    broker = _broker(tmp_path, fake_ib)

    result = run_live_paper_trader_once(
        config=LivePaperTraderConfig(
            live_signal_path=tmp_path / "signal.csv",
            state_path=tmp_path / "state.json",
            strategy_id=BA_NO_TRADE_COMBO_STRATEGY_ID,
            selected_alias=BA_NO_TRADE_COMBO_ALIAS,
            signal_mode="strategy",
            strategy_spec=ba_no_trade_combo_spec(),
            contract=IBKRContractSpec(last_trade_date_or_contract_month="202606"),
            strategy_signal=LiveStrategySignalConfig(history_path=tmp_path / "history.jsonl", tick_interval_seconds=0, min_bars=220),
            max_hold_minutes=60,
        ),
        broker=broker,
    )

    assert result["status"] == "dry_run"
    assert result["live_signal"]["signal_source"].startswith("strategy:mnq_ba_no_trade_best_combo:long_ba_")
    assert result["live_signal"]["strategy_leg"] == "BA"
    assert float(result["live_signal"]["strategy_stop_points"]) >= 4.0
    signal = pd.read_csv(tmp_path / "signal.csv")
    assert signal.iloc[0]["strategy_leg"] == "BA"


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
