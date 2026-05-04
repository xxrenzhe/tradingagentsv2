from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class TickReplayDatasetConfig:
    input_dir: Path = Path(".tmp/ibkr-paper-ticks")
    output: Path = Path(".tmp/ibkr-paper-tick-replay.csv")
    summary_output: Path = Path(".tmp/ibkr-paper-tick-replay-summary.csv")


def build_tick_replay_dataset(config: TickReplayDatasetConfig | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = config or TickReplayDatasetConfig()
    rows = []
    errors = []
    for path in sorted(config.input_dir.glob("*.jsonl")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append({"source_file": str(path), "line_number": line_number, "reason": f"json:{exc.msg}"})
                continue
            if event.get("event_type") != "ibkr_paper_tick":
                if event.get("event_type") == "ibkr_paper_tick_error":
                    errors.append({"source_file": str(path), "line_number": line_number, "reason": str(event.get("reason", "tick_error"))})
                continue
            rows.append(_normalize_tick_event(event, path, line_number))
    dataset = pd.DataFrame(rows)
    if not dataset.empty:
        dataset["event_ts"] = pd.to_datetime(dataset["event_ts"], utc=True, errors="coerce")
        dataset = dataset.sort_values(["intent_id", "event_ts", "tick_index", "tick_event_index"], na_position="last").reset_index(drop=True)
    summary = _summary_frame(dataset, errors)
    config.output.parent.mkdir(parents=True, exist_ok=True)
    config.summary_output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(config.output, index=False)
    summary.to_csv(config.summary_output, index=False)
    return dataset, summary


def _normalize_tick_event(event: dict[str, Any], path: Path, line_number: int) -> dict[str, Any]:
    bid = _number(event.get("bid_price", event.get("bid")))
    ask = _number(event.get("ask_price", event.get("ask")))
    last = _number(event.get("last"))
    trade_price = _number(event.get("price"))
    mid = _number(event.get("mid_point"))
    if mid is None and bid is not None and ask is not None:
        mid = (bid + ask) / 2
    spread = _number(event.get("spread"))
    if spread is None and bid is not None and ask is not None:
        spread = ask - bid
    event_ts = event.get("time") or event.get("snapshot_time")
    return {
        "source_file": str(path),
        "line_number": line_number,
        "intent_id": event.get("intent_id"),
        "candidate_key": event.get("candidate_key"),
        "strategy_id": event.get("strategy_id"),
        "symbol": event.get("symbol"),
        "tick_index": _integer(event.get("tick_index")),
        "tick_event_index": _integer(event.get("tick_event_index")),
        "source_event_type": event.get("source_event_type"),
        "event_ts": event_ts,
        "bid": bid,
        "ask": ask,
        "last": last,
        "trade_price": trade_price,
        "mid": mid,
        "spread": spread,
        "bid_size": _number(event.get("bid_size")),
        "ask_size": _number(event.get("ask_size")),
        "trade_size": _number(event.get("size")),
        "exchange": event.get("exchange"),
        "market_data_type": event.get("market_data_type"),
        "order_ready": event.get("order_ready"),
    }


def _summary_frame(dataset: pd.DataFrame, errors: list[dict[str, Any]]) -> pd.DataFrame:
    if dataset.empty:
        return pd.DataFrame(
            [
                {
                    "ticks": 0,
                    "intents": 0,
                    "candidates": 0,
                    "first_ts": "",
                    "last_ts": "",
                    "avg_spread": 0.0,
                    "max_spread": 0.0,
                    "error_rows": len(errors),
                }
            ]
        )
    return pd.DataFrame(
        [
            {
                "ticks": int(len(dataset)),
                "intents": int(dataset["intent_id"].dropna().nunique()),
                "candidates": int(dataset["candidate_key"].dropna().nunique()),
                "first_ts": dataset["event_ts"].min(),
                "last_ts": dataset["event_ts"].max(),
                "avg_spread": float(dataset["spread"].dropna().mean()) if dataset["spread"].notna().any() else 0.0,
                "max_spread": float(dataset["spread"].dropna().max()) if dataset["spread"].notna().any() else 0.0,
                "error_rows": len(errors),
            }
        ]
    )


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
