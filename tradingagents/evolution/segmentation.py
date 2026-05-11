from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .features import summarize_segment_features


@dataclass(frozen=True)
class SegmentConfig:
    base_bars: int = 100
    min_bars: int = 20
    max_bars: int = 300
    split_threshold: float = 0.75
    high_info_threshold: float = 0.80


@dataclass(frozen=True)
class Segment:
    segment_id: str
    start_index: int
    end_index: int
    start_ts: str
    end_ts: str
    bars: int
    symbol_start: str
    symbol_end: str
    regime: str
    split_reason: str
    high_info_score: float
    feature_json: str

    def to_dict(self) -> dict:
        return asdict(self)


REGIME_MAX_BARS = {
    "range": 300,
    "trend_up": 240,
    "trend_down": 240,
    "volatile_range": 120,
    "post_sweep_reclaim": 80,
    "post_displacement": 80,
    "breakout": 100,
    "reversal_attempt": 80,
}


def segment_market(features: pd.DataFrame, config: SegmentConfig | None = None) -> list[Segment]:
    config = config or SegmentConfig()
    if features.empty:
        return []
    frame = features.reset_index(drop=True).copy()
    scores = event_scores(frame)
    segments: list[Segment] = []
    start = 0
    for index in range(1, len(frame)):
        length = index - start
        current_regime = str(frame.at[index, "regime"])
        start_regime = str(frame.at[start, "regime"])
        regime_max = min(config.max_bars, REGIME_MAX_BARS.get(start_regime, config.base_bars))
        session_boundary = _session_label(frame.at[index, "minute_of_day"]) != _session_label(frame.at[index - 1, "minute_of_day"])
        day_boundary = str(frame.at[index, "trade_date"]) != str(frame.at[index - 1, "trade_date"])
        symbol_boundary = str(frame.at[index, "symbol"]) != str(frame.at[index - 1, "symbol"])
        regime_changed = current_regime != start_regime
        score = float(scores.iloc[index])

        reason = ""
        if length >= config.min_bars:
            if score >= config.split_threshold:
                reason = "event_score"
            elif session_boundary:
                reason = "session_boundary"
            elif day_boundary:
                reason = "day_boundary"
            elif symbol_boundary:
                reason = "symbol_boundary"
            elif regime_changed and score >= 0.35:
                reason = "regime_change"
            elif length >= regime_max:
                reason = "regime_max_bars"
        if reason:
            segments.append(_build_segment(frame, scores, start, index, reason))
            start = index

    if start < len(frame):
        segments.append(_build_segment(frame, scores, start, len(frame), "end_of_data"))
    return segments


def event_scores(frame: pd.DataFrame) -> pd.Series:
    atr_ratio = (pd.to_numeric(frame["atr_30"], errors="coerce") / pd.to_numeric(frame["atr_120"], errors="coerce").replace(0, np.nan)).fillna(1.0)
    volatility_change = ((atr_ratio - 1.0).abs() / 1.0).clip(0, 1)
    structure_event = (
        (pd.to_numeric(frame.get("sweep_signal", 0), errors="coerce").fillna(0).abs() > 0)
        | (pd.to_numeric(frame.get("choch_signal", 0), errors="coerce").fillna(0).abs() > 0)
        | (pd.to_numeric(frame.get("bos_signal", 0), errors="coerce").fillna(0).abs() > 0)
        | (pd.to_numeric(frame.get("fvg_signal", 0), errors="coerce").fillna(0).abs() > 0)
    ).astype(float)
    volume_shock = (pd.to_numeric(frame.get("volume_z_60", 0), errors="coerce").fillna(0).abs() / 3.0).clip(0, 1)
    trend_slope_change = (pd.to_numeric(frame.get("ema_20_slope", 0), errors="coerce").diff().abs().fillna(0) / 10.0).clip(0, 1)
    session_boundary = frame["minute_of_day"].map(_session_label).ne(frame["minute_of_day"].shift(1).map(_session_label)).astype(float).fillna(0)
    candle_pattern = (
        pd.to_numeric(frame.get("displacement_candle", 0), errors="coerce").fillna(0)
        + pd.to_numeric(frame.get("pin_bar", 0), errors="coerce").fillna(0)
        + pd.to_numeric(frame.get("engulfing", 0), errors="coerce").fillna(0).abs()
    ).clip(0, 1)
    score = (
        0.25 * volatility_change
        + 0.20 * structure_event
        + 0.20 * volume_shock
        + 0.15 * trend_slope_change
        + 0.10 * session_boundary
        + 0.10 * candle_pattern
    )
    return score.fillna(0.0).clip(0, 1)


def _build_segment(frame: pd.DataFrame, scores: pd.Series, start: int, end: int, reason: str) -> Segment:
    selected = frame.iloc[start:end]
    summary = summarize_segment_features(selected)
    regime = str(selected["regime"].mode().iloc[0]) if not selected["regime"].mode().empty else str(selected["regime"].iloc[-1])
    segment_id = _segment_id(selected["ts"].iloc[0], selected["ts"].iloc[-1], start, end)
    return Segment(
        segment_id=segment_id,
        start_index=int(start),
        end_index=int(end),
        start_ts=str(selected["ts"].iloc[0]),
        end_ts=str(selected["ts"].iloc[-1]),
        bars=int(len(selected)),
        symbol_start=str(selected["symbol"].iloc[0]),
        symbol_end=str(selected["symbol"].iloc[-1]),
        regime=regime,
        split_reason=reason,
        high_info_score=float(max(float(scores.iloc[start:end].max()), _summary_info_score(summary))),
        feature_json=json.dumps(summary, sort_keys=True, default=str),
    )


def _summary_info_score(summary: dict[str, object]) -> float:
    event_counts = sum(
        float(summary.get(key, 0) or 0)
        for key in ["sweep_signal_count", "choch_signal_count", "bos_signal_count", "fvg_signal_count", "displacement_candle_count"]
    )
    bars = max(float(summary.get("bars", 1) or 1), 1.0)
    event_density = min(event_counts / bars * 8.0, 1.0)
    move_score = min(abs(float(summary.get("net_points", 0.0) or 0.0)) / 80.0, 1.0)
    return float(0.65 * event_density + 0.35 * move_score)


def _session_label(minute: object) -> str:
    try:
        value = int(minute)
    except (TypeError, ValueError):
        return "unknown"
    if 7 * 60 <= value < 13 * 60 + 30:
        return "europe"
    if 13 * 60 + 30 <= value < 20 * 60:
        return "us_rth"
    if 20 * 60 <= value < 23 * 60:
        return "us_late"
    return "asia"


def _segment_id(start_ts: object, end_ts: object, start: int, end: int) -> str:
    payload = f"{start_ts}|{end_ts}|{start}|{end}"
    return "seg_" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
