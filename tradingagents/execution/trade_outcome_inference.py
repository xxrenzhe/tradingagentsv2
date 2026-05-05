from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .agent_gate import PaperTradeOutcome, record_agent_gate_outcome


SECTION_RE = re.compile(
    r"## (?P<time>[^\n]+) - (?P<label>买入开多|卖出开空|买入成交|卖出成交) (?P<quantity>[\d.]+) (?P<symbol>\S+)"
    r"(?P<body>.*?)(?=\n## |\Z)",
    re.S,
)
HIGH_CONFIDENCE_EXIT_REASONS = {"take_profit", "stop_loss"}


@dataclass(frozen=True)
class InferredOutcome:
    strategy_id: str
    intent_id: str
    symbol: str
    action: str
    quantity: int
    trade_date: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    points: float
    exit_reason: str
    confidence: str
    source_file: str


def infer_outcomes(log_dir: Path, *, strategy_id: str | None = None) -> list[InferredOutcome]:
    outcomes: list[InferredOutcome] = []
    for path in sorted(log_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        sections = list(SECTION_RE.finditer(text))
        submits = [_parse_submit(match, path) for match in sections if match.group("label") in {"买入开多", "卖出开空"}]
        fills = [_parse_fill(match) for match in sections if match.group("label") in {"买入成交", "卖出成交"}]
        fills = [fill for fill in fills if fill is not None]
        for submit in submits:
            if submit is None:
                continue
            if strategy_id and submit["strategy_id"] != strategy_id:
                continue
            inferred = _match_submit_to_exit(submit, fills, path)
            if inferred is not None:
                outcomes.append(inferred)
    return outcomes


def write_csv(path: Path, outcomes: list[InferredOutcome]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(outcomes[0]).keys()) if outcomes else list(InferredOutcome.__dataclass_fields__)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for outcome in outcomes:
            writer.writerow(asdict(outcome))


def record_outcomes(outcomes: list[InferredOutcome], *, audit_path: Path, update_memory: bool) -> int:
    count = 0
    existing = _existing_recorded_keys(audit_path)
    for outcome in outcomes:
        if outcome.confidence != "target_or_stop_hit":
            continue
        key = (outcome.strategy_id, outcome.intent_id)
        if key in existing:
            continue
        record_agent_gate_outcome(
            PaperTradeOutcome(
                strategy_id=outcome.strategy_id,
                intent_id=outcome.intent_id,
                symbol=outcome.symbol,
                action=outcome.action,
                quantity=outcome.quantity,
                trade_date=outcome.trade_date,
                entry_time=outcome.entry_time,
                exit_time=outcome.exit_time,
                entry_price=outcome.entry_price,
                exit_price=outcome.exit_price,
                points=outcome.points,
                exit_reason=outcome.exit_reason,
                source="paper_tradelog_inferred",
                notes=f"inferred_from={outcome.source_file}; confidence={outcome.confidence}",
            ),
            audit_path=audit_path,
            update_memory=update_memory,
        )
        existing.add(key)
        count += 1
    return count


def _existing_recorded_keys(audit_path: Path) -> set[tuple[str, str]]:
    if not audit_path.exists():
        return set()
    keys: set[tuple[str, str]] = set()
    with audit_path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event_type") != "agent_gate_paper_outcome":
                continue
            strategy_id = str(event.get("strategy_id") or "")
            intent_id = str(event.get("intent_id") or "")
            if strategy_id and intent_id:
                keys.add((strategy_id, intent_id))
    return keys


def _parse_submit(match: re.Match[str], path: Path) -> dict[str, Any] | None:
    body = match.group("body")
    strategy_id = _field(body, "策略")
    intent_id = _field(body, "订单ID")
    if not strategy_id or not intent_id.startswith("ibkr_intent_"):
        return None
    entry_reference = _entry_reference(body)
    stop_loss, take_profit = _stop_take(body)
    action = "BUY" if match.group("label") == "买入开多" else "SELL"
    entry_time = _parse_time(match.group("time"))
    return {
        "strategy_id": strategy_id,
        "intent_id": intent_id,
        "symbol": match.group("symbol"),
        "action": action,
        "quantity": int(float(match.group("quantity"))),
        "entry_time": entry_time,
        "trade_date": entry_time[:10],
        "entry_price": entry_reference,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "source_file": str(path),
    }


def _parse_fill(match: re.Match[str]) -> dict[str, Any] | None:
    body = match.group("body")
    price_quantity = re.search(r"成交价/数量：`([^`]*)`\s*/\s*`([^`]*)`", body)
    if not price_quantity:
        return None
    try:
        price = float(price_quantity.group(1))
        quantity = int(float(price_quantity.group(2)))
    except ValueError:
        return None
    action = "BUY" if match.group("label") == "买入成交" else "SELL"
    return {
        "time": _parse_time(match.group("time")),
        "action": action,
        "symbol": match.group("symbol"),
        "quantity": quantity,
        "price": price,
    }


def _match_submit_to_exit(submit: dict[str, Any], fills: list[dict[str, Any]], path: Path) -> InferredOutcome | None:
    opposite = "SELL" if submit["action"] == "BUY" else "BUY"
    entry_time = _to_datetime(submit["entry_time"])
    candidates = [
        fill
        for fill in fills
        if fill["symbol"] == submit["symbol"]
        and fill["action"] == opposite
        and fill["quantity"] == submit["quantity"]
        and _to_datetime(fill["time"]) > entry_time
    ]
    if not candidates:
        return None
    exit_fill = min(candidates, key=lambda fill: _to_datetime(fill["time"]))
    direction = 1 if submit["action"] == "BUY" else -1
    points = (exit_fill["price"] - submit["entry_price"]) * direction
    exit_reason = _exit_reason(exit_fill["price"], submit["stop_loss"], submit["take_profit"], submit["action"])
    confidence = "target_or_stop_hit" if exit_reason in HIGH_CONFIDENCE_EXIT_REASONS else "matched_exit_fill_review"
    return InferredOutcome(
        strategy_id=submit["strategy_id"],
        intent_id=submit["intent_id"],
        symbol=submit["symbol"],
        action=submit["action"],
        quantity=submit["quantity"],
        trade_date=submit["trade_date"],
        entry_time=submit["entry_time"],
        exit_time=exit_fill["time"],
        entry_price=submit["entry_price"],
        exit_price=exit_fill["price"],
        points=points,
        exit_reason=exit_reason,
        confidence=confidence,
        source_file=str(path),
    )


def _field(body: str, label: str) -> str:
    match = re.search(rf"- {re.escape(label)}：`([^`]*)`", body)
    return match.group(1).strip() if match else ""


def _entry_reference(body: str) -> float:
    match = re.search(r"入场：`[^`]*` @ `([^`]*)`", body)
    return float(match.group(1)) if match else 0.0


def _stop_take(body: str) -> tuple[float, float]:
    match = re.search(r"止损/止盈：`([^`]*)` / `([^`]*)`", body)
    if not match:
        return 0.0, 0.0
    return float(match.group(1)), float(match.group(2))


def _parse_time(value: str) -> str:
    return str(value).strip()


def _to_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _exit_reason(exit_price: float, stop_loss: float, take_profit: float, action: str) -> str:
    tolerance = 0.5
    if action == "BUY":
        if abs(exit_price - stop_loss) <= tolerance:
            return "stop_loss"
        if abs(exit_price - take_profit) <= tolerance:
            return "take_profit"
    else:
        if abs(exit_price - stop_loss) <= tolerance:
            return "stop_loss"
        if abs(exit_price - take_profit) <= tolerance:
            return "take_profit"
    return "matched_exit_fill"
