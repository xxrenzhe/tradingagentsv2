from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field


ALLOWED_FEATURES = {
    "return_1m",
    "return_5m",
    "return_15m",
    "return_60m",
    "range_points",
    "body_points",
    "body_share",
    "ema_10_slope",
    "ema_20_slope",
    "vwap_distance",
    "vwap_distance_z",
    "atr_30",
    "atr_120",
    "z_30",
    "volume_z_60",
    "rsi_14",
    "boll_position",
    "doji",
    "pin_bar",
    "engulfing",
    "inside_bar",
    "outside_bar",
    "displacement_candle",
    "pd_zone",
    "pd_fade_signal",
    "pd_continue_signal",
    "sweep_signal",
    "choch_signal",
    "bos_signal",
    "fvg_signal",
    "regime",
    "minute_of_day",
}


class EntryCondition(BaseModel):
    feature: str
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    value: float | int | str


class TradingRule(BaseModel):
    pattern_name: str
    hypothesis: str
    new_or_existing: Literal["new", "variant", "existing"] = "new"
    memory_used: list[str] = Field(default_factory=list)
    why_not_reuse_existing: str = ""
    market_regime: str = "range"
    direction: Literal["long", "short", "both", "no_trade"]
    entry_conditions: list[EntryCondition]
    entry_timing: Literal["next_open", "close_confirmation", "retest"] = "next_open"
    stop_points: float = 12.0
    target_points: float = 24.0
    max_hold_bars: int = 60
    validation_bars: int = 120
    max_trades_per_validation: int = 3
    confidence: float = 0.0
    expected_failure_modes: list[str] = Field(default_factory=list)
    invalid_if: list[str] = Field(default_factory=list)


def parse_rule_payload(payload: dict[str, Any]) -> TradingRule:
    rule = TradingRule(**payload)
    invalid = [condition.feature for condition in rule.entry_conditions if condition.feature not in ALLOWED_FEATURES]
    if invalid:
        raise ValueError(f"Unsupported rule feature(s): {invalid}")
    if rule.direction == "no_trade":
        raise ValueError("no_trade rules are not stored as tradeable pattern rules")
    if rule.stop_points <= 0 or rule.target_points <= 0:
        raise ValueError("stop_points and target_points must be positive")
    if rule.max_hold_bars <= 0:
        raise ValueError("max_hold_bars must be positive")
    if rule.validation_bars < rule.max_hold_bars + 2:
        rule.validation_bars = rule.max_hold_bars + 2
    rule.validation_bars = min(rule.validation_bars, 300)
    rule.max_trades_per_validation = max(1, min(int(rule.max_trades_per_validation), 10))
    rule.confidence = max(0.0, min(float(rule.confidence), 1.0))
    return rule


def rule_to_dict(rule: TradingRule) -> dict[str, Any]:
    return rule.model_dump() if hasattr(rule, "model_dump") else rule.dict()


def rule_signature(rule: TradingRule) -> str:
    normalized_conditions = sorted(
        [
            {
                "feature": condition.feature,
                "operator": condition.operator,
                "value": _bucket_value(condition.value),
            }
            for condition in rule.entry_conditions
        ],
        key=lambda item: (str(item["feature"]), str(item["operator"]), str(item["value"])),
    )
    payload = {
        "direction": rule.direction,
        "entry_conditions": normalized_conditions,
        "entry_timing": rule.entry_timing,
        "stop_points": _bucket_number(rule.stop_points, 1.0),
        "target_points": _bucket_number(rule.target_points, 1.0),
        "max_hold_bars": int(round(rule.max_hold_bars / 5) * 5),
        "validation_bars": int(round(rule.validation_bars / 10) * 10),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "rule_" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def condition_mask(frame: pd.DataFrame, rule: TradingRule) -> pd.Series:
    if not rule.entry_conditions:
        return pd.Series(False, index=frame.index)
    mask = pd.Series(True, index=frame.index)
    for condition in rule.entry_conditions:
        if condition.feature not in frame.columns:
            return pd.Series(False, index=frame.index)
        values = frame[condition.feature]
        if isinstance(condition.value, str):
            left = values.astype(str)
            right = str(condition.value)
            if condition.operator == "==":
                current = left == right
            elif condition.operator == "!=":
                current = left != right
            else:
                raise ValueError(f"Operator {condition.operator} is invalid for string feature {condition.feature}")
        else:
            left = pd.to_numeric(values, errors="coerce")
            right = float(condition.value)
            current = _numeric_compare(left, condition.operator, right)
        mask &= current.fillna(False)
    return mask


def direction_for_row(row: pd.Series, rule: TradingRule) -> int:
    if rule.direction == "long":
        return 1
    if rule.direction == "short":
        return -1
    for column in ["pd_fade_signal", "pd_continue_signal", "sweep_signal", "choch_signal", "bos_signal", "fvg_signal"]:
        value = row.get(column)
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number != 0:
            return 1 if number > 0 else -1
    return 1


def _numeric_compare(left: pd.Series, operator: str, right: float) -> pd.Series:
    if operator == "<":
        return left < right
    if operator == "<=":
        return left <= right
    if operator == ">":
        return left > right
    if operator == ">=":
        return left >= right
    if operator == "==":
        return left == right
    if operator == "!=":
        return left != right
    raise ValueError(f"Unsupported operator: {operator}")


def _bucket_value(value: float | int | str) -> float | int | str:
    if isinstance(value, str):
        return value.strip().lower()
    return _bucket_number(float(value), 0.05)


def _bucket_number(value: float, bucket: float) -> float:
    return round(round(float(value) / bucket) * bucket, 6)
