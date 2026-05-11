from __future__ import annotations

import hashlib
import json
import re
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
    "relative_volume_20",
    "obv_slope_20",
    "cmf_20",
    "mfi_14",
    "price_volume_corr_20",
    "volume_price_trend_slope_20",
    "rsi_14",
    "boll_position",
    "doji",
    "pin_bar",
    "engulfing",
    "inside_bar",
    "outside_bar",
    "displacement_candle",
    "volume_breakout_signal",
    "low_volume_pullback",
    "bullish_volume_divergence",
    "bearish_volume_divergence",
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
    payload = normalize_rule_payload(payload)
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


def normalize_rule_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if not isinstance(normalized.get("memory_used"), list):
        value = normalized.get("memory_used")
        normalized["memory_used"] = [] if value in {None, False, "", "none", "None", "N/A", "n/a"} else [str(value)]
    for key in ["expected_failure_modes", "invalid_if"]:
        if not isinstance(normalized.get(key), list):
            value = normalized.get(key)
            normalized[key] = [] if value in {None, False, "", "none", "None", "N/A", "n/a"} else [str(value)]
    normalized["new_or_existing"] = _normalize_choice(
        normalized.get("new_or_existing"),
        allowed={"new", "variant", "existing"},
        default="new",
    )
    if not isinstance(normalized.get("why_not_reuse_existing"), str):
        value = normalized.get("why_not_reuse_existing")
        normalized["why_not_reuse_existing"] = "; ".join(str(item) for item in value) if isinstance(value, list) else str(value or "")
    normalized["direction"] = _normalize_choice(
        normalized.get("direction"),
        allowed={"long", "short", "both", "no_trade"},
        default=_direction_from_text(normalized),
    )
    normalized["entry_timing"] = _normalize_entry_timing(normalized.get("entry_timing"))
    normalized["entry_conditions"] = _normalize_conditions(normalized.get("entry_conditions"))
    for key, default in [("stop_points", 12.0), ("target_points", 24.0), ("max_hold_bars", 60), ("validation_bars", 120), ("max_trades_per_validation", 3), ("confidence", 0.0)]:
        if normalized.get(key) in {None, ""}:
            normalized[key] = default
    return normalized


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


def _normalize_conditions(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    conditions: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            condition = _condition_from_text(item)
            if condition is None:
                continue
        elif isinstance(item, dict):
            condition = dict(item)
        else:
            continue
        feature = str(condition.get("feature", "")).strip()
        if feature not in ALLOWED_FEATURES:
            feature = _feature_alias(feature)
        operator = str(condition.get("operator", "==")).strip()
        value_obj = condition.get("value")
        if operator.lower() in {"above", "greater_than", "gt"}:
            operator = ">"
        elif operator.lower() in {"below", "less_than", "lt"}:
            operator = "<"
        elif operator.lower() in {"gte", "at_least", "greater_or_equal"}:
            operator = ">="
        elif operator.lower() in {"lte", "at_most", "less_or_equal"}:
            operator = "<="
        elif operator in {"=", "equals"}:
            operator = "=="
        if feature in ALLOWED_FEATURES and operator in {"<", "<=", ">", ">=", "==", "!="}:
            conditions.append({"feature": feature, "operator": operator, "value": value_obj})
    return conditions


def _condition_from_text(text: str) -> dict[str, Any] | None:
    match = re.match(r"^\s*([A-Za-z0-9_ .-]+)\s*(<=|>=|==|!=|=|<|>)\s*(.+?)\s*$", text)
    if not match:
        return None
    feature, operator, value = match.groups()
    if operator == "=":
        operator = "=="
    return {"feature": feature.strip(), "operator": operator, "value": _coerce_condition_value(value)}


def _coerce_condition_value(value: str) -> float | str:
    stripped = value.strip().strip("\"'")
    try:
        return float(stripped)
    except ValueError:
        return stripped


def _feature_alias(feature: str) -> str:
    compact = feature.strip().lower().replace(" ", "_").replace("-", "_")
    for suffix in ["_last", "_mean", "_count"]:
        if compact.endswith(suffix):
            compact = compact[: -len(suffix)]
    aliases = {
        "volume_zscore": "volume_z_60",
        "volume_z": "volume_z_60",
        "relative_volume": "relative_volume_20",
        "rel_volume": "relative_volume_20",
        "obv_slope": "obv_slope_20",
        "cmf": "cmf_20",
        "mfi": "mfi_14",
        "price_volume_corr": "price_volume_corr_20",
        "vpt_slope": "volume_price_trend_slope_20",
        "volume_breakout": "volume_breakout_signal",
        "low_volume_pullback_signal": "low_volume_pullback",
        "bullish_obv_divergence": "bullish_volume_divergence",
        "bearish_obv_divergence": "bearish_volume_divergence",
        "vwap_z": "vwap_distance_z",
    }
    return aliases.get(compact, compact)


def _normalize_choice(value: Any, *, allowed: set[str], default: str) -> str:
    if value is None:
        return default
    compact = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    return compact if compact in allowed else default


def _normalize_entry_timing(value: Any) -> str:
    if value is None:
        return "next_open"
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"next_open", "next_bar_open", "enter_at_next_open", "enter_next_open"}:
        return "next_open"
    if text in {"close_confirmation", "close_confirm", "on_close", "close"}:
        return "close_confirmation"
    if text in {"retest", "on_retest", "pullback_retest"}:
        return "retest"
    if "next" in text and "open" in text:
        return "next_open"
    if "retest" in text:
        return "retest"
    if "close" in text:
        return "close_confirmation"
    return "next_open"


def _direction_from_text(payload: dict[str, Any]) -> str:
    text = " ".join(str(payload.get(key, "")) for key in ["pattern_name", "hypothesis", "entry_timing"]).lower()
    if "short" in text or "sell" in text:
        return "short"
    if "long" in text or "buy" in text:
        return "long"
    return "both"


def _bucket_value(value: float | int | str) -> float | int | str:
    if isinstance(value, str):
        return value.strip().lower()
    return _bucket_number(float(value), 0.05)


def _bucket_number(value: float, bucket: float) -> float:
    return round(round(float(value) / bucket) * bucket, 6)
