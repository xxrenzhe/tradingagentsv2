from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .ibkr import IBKRContractSpec, IBKRPaperBroker


@dataclass(frozen=True)
class IBKRTickRecorderConfig:
    output_dir: Path = Path(".tmp/ibkr-paper-ticks")
    symbol: str = "MNQ"
    contract_month: str = "202606"
    interval_seconds: float = 1.0
    max_ticks: int = 60
    enabled: bool = False
    prefer_tick_by_tick: bool = True


def record_ibkr_ticks(
    *,
    broker: IBKRPaperBroker,
    config: IBKRTickRecorderConfig | None = None,
    intent_id: str | None = None,
    candidate_key: str | None = None,
    strategy_id: str | None = None,
) -> dict[str, Any]:
    config = config or IBKRTickRecorderConfig()
    if not config.enabled or config.max_ticks <= 0:
        return {"status": "disabled", "ticks": 0, "output": None}
    output_path = _tick_output_path(config, intent_id=intent_id, candidate_key=candidate_key)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    contract = IBKRContractSpec(symbol=config.symbol, last_trade_date_or_contract_month=config.contract_month)
    connection = broker.connect()
    if not connection.get("connected"):
        _write_tick_error(
            output_path,
            tick_index=0,
            intent_id=intent_id,
            candidate_key=candidate_key,
            strategy_id=strategy_id,
            reason=connection.get("reason") or connection.get("status") or "connect_failed",
        )
        return {
            "status": "error",
            "ticks": 0,
            "errors": 1,
            "output": str(output_path),
            "config": asdict(config),
            "connection": connection,
        }
    count = 0
    errors = 0
    with output_path.open("a", encoding="utf-8") as handle:
        for index in range(config.max_ticks):
            try:
                events = _tick_events(broker, contract, config)
                if not events:
                    raise RuntimeError("no_tick_data")
                for event_index, event in enumerate(events):
                    source_event_type = event.get("event_type")
                    row = dict(event)
                    row.update(
                        {
                            "event_type": "ibkr_paper_tick",
                            "tick_index": index,
                            "tick_event_index": event_index,
                            "intent_id": intent_id,
                            "candidate_key": candidate_key,
                            "strategy_id": strategy_id,
                            "source_event_type": source_event_type,
                        }
                    )
                    handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
                    count += 1
            except Exception as exc:
                errors += 1
                handle.write(
                    json.dumps(
                        {
                            "event_type": "ibkr_paper_tick_error",
                            "tick_index": index,
                            "intent_id": intent_id,
                            "candidate_key": candidate_key,
                            "strategy_id": strategy_id,
                            "reason": str(exc) or exc.__class__.__name__,
                        },
                        sort_keys=True,
                        default=str,
                    )
                    + "\n"
                )
            if index + 1 < config.max_ticks:
                time.sleep(config.interval_seconds)
    return {
        "status": "recorded" if count else "error",
        "ticks": count,
        "errors": errors,
        "output": str(output_path),
        "config": asdict(config),
    }


def _write_tick_error(
    output_path: Path,
    *,
    tick_index: int,
    intent_id: str | None,
    candidate_key: str | None,
    strategy_id: str | None,
    reason: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "event_type": "ibkr_paper_tick_error",
                    "tick_index": tick_index,
                    "intent_id": intent_id,
                    "candidate_key": candidate_key,
                    "strategy_id": strategy_id,
                    "reason": reason,
                },
                sort_keys=True,
                default=str,
            )
            + "\n"
        )


def _tick_output_path(
    config: IBKRTickRecorderConfig,
    *,
    intent_id: str | None,
    candidate_key: str | None,
) -> Path:
    safe_key = _safe_component(intent_id or candidate_key or "unknown")
    return config.output_dir / f"{config.symbol.upper()}-{config.contract_month}-{safe_key}.jsonl"


def _safe_component(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in value)[:120]


def _tick_events(broker: IBKRPaperBroker, contract: IBKRContractSpec, config: IBKRTickRecorderConfig) -> list[dict[str, Any]]:
    if config.prefer_tick_by_tick:
        try:
            ticks = broker.tick_by_tick_snapshot(contract, interval_seconds=config.interval_seconds)
            if ticks:
                return ticks
        except Exception:
            pass
    return [broker.tick_snapshot(contract)]
