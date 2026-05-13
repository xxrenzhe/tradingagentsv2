from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
import time
from typing import Any

import pandas as pd

from .ibkr import IBKRContractSpec, IBKRPaperBroker, is_paper_tradeable_market_data_type


LIVE_SIGNAL_COLUMNS = [
    "entry_ts",
    "actual_entry_ts",
    "exit_ts",
    "direction",
    "entry_price",
    "exit_price",
    "gross_points",
    "net_points",
    "net_dollars",
    "entry_index",
    "exit_index",
    "holding_minutes",
    "selected_alias",
    "strategy_name",
    "actual_entry_index",
    "trade_date",
    "cost_delta_points",
    "strategy_alias",
    "portfolio_rule",
    "session_bucket",
    "vol_bucket",
    "realized_vol_30",
    "vwap_distance",
    "ibkr_bid",
    "ibkr_ask",
    "ibkr_last",
    "ibkr_spread",
    "ibkr_market_data_type",
    "ibkr_order_ready",
    "ibkr_snapshot_time",
    "cumulative_net_points",
    "exit_reason",
    "signal_source",
    "setup_confidence",
    "setup_htf_trend",
    "setup_mtf_reclaim",
    "setup_ltf_trigger",
    "strategy_stop_points",
    "strategy_target_points",
    "strategy_horizon_minutes",
    "strategy_range_width_atr",
    "strategy_range_efficiency",
    "strategy_displacement_atr",
    "strategy_body_share",
    "strategy_volume_z",
]


@dataclass(frozen=True)
class LiveSignalConfig:
    output: Path = Path(".tmp/mbp-live-signal.csv")
    strategy_id: str = "manual_live_signal"
    selected_alias: str = "manual"
    direction: int = 0
    entry_price: float | None = None
    max_hold_minutes: int = 4
    signal_source: str = "manual"
    contract: IBKRContractSpec = IBKRContractSpec()
    snapshot_attempts: int = 3
    snapshot_retry_seconds: float = 1.0
    require_paper_tradeable_market_data: bool = True


def build_live_signal_row(
    *,
    config: LiveSignalConfig,
    broker: IBKRPaperBroker | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if config.direction == 0:
        raise ValueError("direction must be 1 for BUY or -1 for SELL")
    timestamp = now or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC)
    entry_price = config.entry_price
    signal_source = config.signal_source
    snapshot: dict[str, Any] = {}
    if entry_price is None:
        active_broker = broker or IBKRPaperBroker()
        connection = active_broker.connect()
        if not connection.get("connected"):
            raise ConnectionError(connection.get("reason") or connection.get("status") or "connect_failed")
        snapshot = _order_ready_snapshot(active_broker, config)
        if not snapshot.get("order_ready"):
            raise ValueError(f"market snapshot is not order-ready: {snapshot}")
        if config.require_paper_tradeable_market_data and not is_paper_tradeable_market_data_type(snapshot.get("market_data_type")):
            raise ValueError(f"market snapshot is not paper-tradeable: {snapshot}")
        if config.direction > 0:
            entry_price = float(snapshot["ask"])
            signal_source = f"{signal_source}:ibkr_ask"
        else:
            entry_price = float(snapshot["bid"])
            signal_source = f"{signal_source}:ibkr_bid"
    exit_ts = timestamp + timedelta(minutes=max(1, int(config.max_hold_minutes)))
    return {
        "entry_ts": timestamp.isoformat(),
        "actual_entry_ts": timestamp.isoformat(),
        "exit_ts": exit_ts.isoformat(),
        "direction": int(config.direction),
        "entry_price": float(entry_price),
        "exit_price": float(entry_price),
        "gross_points": 0.0,
        "net_points": 0.0,
        "net_dollars": 0.0,
        "entry_index": 0,
        "exit_index": 0,
        "holding_minutes": int(config.max_hold_minutes),
        "selected_alias": config.selected_alias,
        "strategy_name": config.strategy_id,
        "actual_entry_index": 0,
        "trade_date": timestamp.date().isoformat(),
        "cost_delta_points": 0.0,
        "strategy_alias": config.selected_alias,
        "portfolio_rule": config.strategy_id,
        "session_bucket": "live",
        "vol_bucket": "live",
        "realized_vol_30": 0.0,
        "vwap_distance": 0.0,
        "ibkr_bid": snapshot.get("bid", ""),
        "ibkr_ask": snapshot.get("ask", ""),
        "ibkr_last": snapshot.get("last", ""),
        "ibkr_spread": snapshot.get("spread", ""),
        "ibkr_market_data_type": snapshot.get("market_data_type", ""),
        "ibkr_order_ready": snapshot.get("order_ready", ""),
        "ibkr_snapshot_time": snapshot.get("snapshot_time", ""),
        "cumulative_net_points": 0.0,
        "exit_reason": "live_bracket",
        "signal_source": signal_source,
        "strategy_stop_points": "",
        "strategy_target_points": "",
        "strategy_horizon_minutes": int(config.max_hold_minutes),
        "strategy_range_width_atr": "",
        "strategy_range_efficiency": "",
        "strategy_displacement_atr": "",
        "strategy_body_share": "",
        "strategy_volume_z": "",
    }


def write_live_signal(row: dict[str, Any], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([{column: row.get(column, "") for column in LIVE_SIGNAL_COLUMNS}])
    temporary = output.with_suffix(output.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(output)
    return output


def _order_ready_snapshot(broker: IBKRPaperBroker, config: LiveSignalConfig) -> dict[str, Any]:
    attempts = max(1, int(config.snapshot_attempts))
    last_snapshot: dict[str, Any] = {}
    for attempt in range(attempts):
        last_snapshot = broker.tick_snapshot(config.contract)
        if last_snapshot.get("order_ready"):
            return last_snapshot
        if attempt + 1 < attempts:
            time.sleep(max(0.0, float(config.snapshot_retry_seconds)))
    return last_snapshot
