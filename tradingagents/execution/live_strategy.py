from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from tradingagents.backtesting.multi_timeframe_setup import (
    MultiTimeframeSetupSpec,
    evaluate_multi_timeframe_setup_signal,
    prepare_multi_timeframe_features,
)

from .ibkr import IBKRContractSpec, IBKRPaperBroker, is_paper_tradeable_market_data_type
from .live_signal import LiveSignalConfig, build_live_signal_row


BEST_MEAN_REVERSION_STRATEGY_ID = "adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3"
BEST_MEAN_REVERSION_ALIAS = "best_strategy"


@dataclass(frozen=True)
class LiveStrategySpec:
    strategy_id: str = BEST_MEAN_REVERSION_STRATEGY_ID
    selected_alias: str = BEST_MEAN_REVERSION_ALIAS
    family: str = "mean_reversion"
    lookback: int = 6
    threshold: float = 0.8
    min_hold_minutes: int = 1
    max_hold_minutes: int = 6
    exit_mode: str = "reverse"
    session: str = "europe"
    htf_mode: str = "off"
    volatility_filter: str = "all"
    imbalance_threshold: float = 0.3
    width_atr_max: float = 8.0
    efficiency_max: float = 0.15
    displacement_atr_min: float = 1.8
    body_share_min: float = 0.60
    volume_z_min: float | None = 0.50
    stop_mode: str = "break_bar"
    reward_risk: float = 2.5
    breakout_buffer_atr: float = 0.05
    stop_buffer_atr: float = 0.10
    min_buffer_points: float = 0.25
    min_stop_points: float = 4.0
    max_stop_points: float = 80.0


@dataclass(frozen=True)
class LiveStrategySignalConfig:
    history_path: Path = Path(".tmp/mbp-live-market-history.jsonl")
    bootstrap_cache_path: Path | None = Path(".tmp/mbp-history-features-cache.pkl")
    max_history_minutes: int = 120
    tick_interval_seconds: float = 1.0
    min_bars: int = 7


def best_mean_reversion_spec() -> LiveStrategySpec:
    return LiveStrategySpec()


def regime_transition_spec(strategy_id: str, selected_alias: str | None = None) -> LiveStrategySpec:
    specs = {
        "optimized50_2r5_quality": dict(
            lookback=50,
            width_atr_max=8.0,
            efficiency_max=0.15,
            displacement_atr_min=1.8,
            body_share_min=0.60,
            volume_z_min=0.50,
            reward_risk=2.5,
            max_hold_minutes=180,
        ),
        "defensive45_2r5_loweff": dict(
            lookback=45,
            width_atr_max=10.0,
            efficiency_max=0.10,
            displacement_atr_min=1.6,
            body_share_min=0.55,
            volume_z_min=0.0,
            reward_risk=2.5,
            max_hold_minutes=180,
        ),
        "short45_2r25_netdd": dict(
            lookback=45,
            width_atr_max=12.0,
            efficiency_max=0.25,
            displacement_atr_min=1.2,
            body_share_min=0.55,
            volume_z_min=0.0,
            reward_risk=2.25,
            max_hold_minutes=240,
        ),
    }
    if strategy_id not in specs:
        raise ValueError(f"unsupported regime_transition strategy: {strategy_id}")
    return LiveStrategySpec(
        strategy_id=strategy_id,
        selected_alias=selected_alias or strategy_id,
        family="regime_transition",
        session="us_late",
        **specs[strategy_id],
    )


def build_strategy_live_signal_row(
    *,
    signal_config: LiveSignalConfig,
    strategy_spec: LiveStrategySpec | None = None,
    strategy_config: LiveStrategySignalConfig | None = None,
    broker: IBKRPaperBroker | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    strategy_spec = strategy_spec or best_mean_reversion_spec()
    strategy_config = strategy_config or LiveStrategySignalConfig()
    if signal_config.strategy_id != strategy_spec.strategy_id:
        raise ValueError(f"unsupported live strategy: {signal_config.strategy_id}")
    timestamp = _utc_now(now)
    active_broker = broker or IBKRPaperBroker()
    connection = active_broker.connect()
    if not connection.get("connected"):
        raise ConnectionError(connection.get("reason") or connection.get("status") or "connect_failed")
    top_snapshot = _order_ready_snapshot(active_broker, signal_config)
    if not top_snapshot.get("order_ready"):
        raise ValueError(f"market snapshot is not order-ready: {top_snapshot}")
    if signal_config.require_paper_tradeable_market_data and not is_paper_tradeable_market_data_type(top_snapshot.get("market_data_type")):
        raise ValueError(f"market snapshot is not paper-tradeable: {top_snapshot}")
    tick_events = _safe_tick_by_tick_snapshot(active_broker, signal_config.contract, strategy_config.tick_interval_seconds)
    market_event = _market_event(timestamp, top_snapshot, tick_events)
    _append_market_event(strategy_config.history_path, market_event)
    history = _load_recent_history(strategy_config.history_path, timestamp, strategy_config.max_history_minutes)
    bars = (
        _historical_bars_frame(_safe_historical_minute_bars(active_broker, signal_config.contract))
        if strategy_spec.family == "regime_transition"
        else pd.DataFrame()
    )
    if bars.empty:
        bars = _build_minute_bars(history)
    if strategy_spec.family == "mean_reversion":
        evaluation = evaluate_mean_reversion_signal(bars, strategy_spec, min_bars=strategy_config.min_bars)
    elif strategy_spec.family == "mtf_setup":
        mtf_spec = _mtf_spec(strategy_spec)
        required_bars = _required_mtf_bars(mtf_spec, strategy_config.min_bars)
        if len(bars) < required_bars:
            bootstrap = _load_bootstrap_bars(strategy_config.bootstrap_cache_path, timestamp, required_bars)
            if not bootstrap.empty:
                bars = pd.concat([bars, bootstrap], ignore_index=True)
                bars = bars.sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
        mtf_features = prepare_multi_timeframe_features(bars, spec=mtf_spec)
        evaluation = evaluate_multi_timeframe_setup_signal(
            mtf_features,
            mtf_spec,
            min_bars=strategy_config.min_bars,
        )
    elif strategy_spec.family == "regime_transition":
        required_bars = max(strategy_config.min_bars, strategy_spec.lookback + 121)
        if len(bars) < required_bars:
            bootstrap = _load_bootstrap_bars(strategy_config.bootstrap_cache_path, timestamp, required_bars)
            if not bootstrap.empty:
                bars = pd.concat([bars, bootstrap], ignore_index=True)
                bars = bars.sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
        evaluation = evaluate_regime_transition_signal(bars, strategy_spec, min_bars=strategy_config.min_bars)
    else:
        raise ValueError(f"unsupported live strategy family: {strategy_spec.family}")
    if not evaluation["triggered"]:
        raise ValueError(json.dumps({"reason": "no_strategy_signal", **evaluation}, sort_keys=True, default=str))
    direction = int(evaluation["direction"])
    row = build_live_signal_row(
        config=LiveSignalConfig(
            output=signal_config.output,
            strategy_id=signal_config.strategy_id,
            selected_alias=signal_config.selected_alias,
            direction=direction,
            entry_price=None,
            max_hold_minutes=signal_config.max_hold_minutes,
            signal_source=f"strategy:{strategy_spec.strategy_id}",
            contract=signal_config.contract,
            snapshot_attempts=signal_config.snapshot_attempts,
            snapshot_retry_seconds=signal_config.snapshot_retry_seconds,
            require_paper_tradeable_market_data=signal_config.require_paper_tradeable_market_data,
        ),
        broker=active_broker,
        now=timestamp,
    )
    dynamic_stop_points = evaluation.get("stop_points", "")
    dynamic_target_points = evaluation.get("target_points", "")
    if strategy_spec.family == "regime_transition":
        actual_entry = _finite_float(row.get("entry_price"))
        stop_price = _finite_float(evaluation.get("stop_price"))
        if actual_entry is not None and stop_price is not None and actual_entry > stop_price:
            dynamic_stop_points = actual_entry - stop_price
            dynamic_target_points = dynamic_stop_points * float(evaluation.get("reward_risk", strategy_spec.reward_risk))
    return row | {
        "session_bucket": strategy_spec.session,
        "vol_bucket": strategy_spec.volatility_filter,
        "realized_vol_30": evaluation.get("realized_vol_30", 0.0),
        "vwap_distance": evaluation.get("vwap_distance", 0.0),
        "strategy_z_score": evaluation.get("z_score"),
        "strategy_imbalance": evaluation.get("imbalance"),
        "strategy_bars": evaluation.get("bars"),
        "signal_source": f"strategy:{strategy_spec.strategy_id}:{evaluation['side']}",
        "setup_confidence": evaluation.get("confidence", ""),
        "setup_htf_trend": evaluation.get("htf_trend", ""),
        "setup_mtf_reclaim": evaluation.get("mtf_reclaim", ""),
        "setup_ltf_trigger": evaluation.get("ltf_trigger", ""),
        "strategy_stop_points": dynamic_stop_points,
        "strategy_target_points": dynamic_target_points,
        "strategy_horizon_minutes": evaluation.get("horizon_minutes", signal_config.max_hold_minutes),
        "strategy_range_width_atr": evaluation.get("range_width_atr", ""),
        "strategy_range_efficiency": evaluation.get("range_efficiency", ""),
        "strategy_displacement_atr": evaluation.get("displacement_atr", ""),
        "strategy_body_share": evaluation.get("body_share", ""),
        "strategy_volume_z": evaluation.get("volume_z", ""),
    }


def evaluate_mean_reversion_signal(
    bars: pd.DataFrame,
    spec: LiveStrategySpec | None = None,
    *,
    min_bars: int | None = None,
) -> dict[str, Any]:
    spec = spec or best_mean_reversion_spec()
    if bars.empty:
        return {"triggered": False, "reason": "no_market_history", "bars": 0}
    data = bars.sort_values("ts").reset_index(drop=True).copy()
    required_bars = max(int(min_bars or 0), spec.min_hold_minutes + spec.lookback, spec.lookback + 1)
    if len(data) < required_bars:
        return {"triggered": False, "reason": "insufficient_bars", "bars": int(len(data)), "required_bars": required_bars}
    last = data.iloc[-1]
    minute = int(last["ts"].hour * 60 + last["ts"].minute)
    if spec.session == "europe" and not (7 * 60 <= minute < 13 * 60 + 30):
        return {"triggered": False, "reason": "outside_session", "bars": int(len(data)), "minute_of_day": minute}
    close = pd.to_numeric(data["Close"], errors="coerce")
    rolling_mean = close.rolling(spec.lookback).mean()
    rolling_std = close.rolling(spec.lookback).std().replace(0, pd.NA)
    z_score = (close - rolling_mean) / rolling_std
    current_z = _finite_float(z_score.iloc[-1])
    previous_z = _finite_float(z_score.iloc[-2])
    if current_z is None:
        return {"triggered": False, "reason": "invalid_z_score", "bars": int(len(data))}
    raw_direction = 0
    side = "flat"
    if current_z < -spec.threshold:
        raw_direction = 1
        side = "long_mean_reversion"
    elif current_z > spec.threshold:
        raw_direction = -1
        side = "short_mean_reversion"
    if raw_direction == 0:
        return {"triggered": False, "reason": "z_score_below_threshold", "bars": int(len(data)), "z_score": current_z}
    previous_direction = _direction_from_z(previous_z, spec.threshold)
    imbalance = _finite_float(last.get("imbalance_last"))
    if imbalance is None:
        return {"triggered": False, "reason": "missing_imbalance", "bars": int(len(data)), "z_score": current_z}
    aligned = (raw_direction > 0 and imbalance >= spec.imbalance_threshold) or (
        raw_direction < 0 and imbalance <= -spec.imbalance_threshold
    )
    if not aligned:
        return {
            "triggered": False,
            "reason": "imbalance_not_aligned",
            "bars": int(len(data)),
            "z_score": current_z,
            "imbalance": imbalance,
        }
    return {
        "triggered": True,
        "reason": "strategy_signal",
        "direction": raw_direction,
        "side": side,
        "bars": int(len(data)),
        "z_score": current_z,
        "previous_z_score": previous_z,
        "previous_direction": previous_direction,
        "imbalance": imbalance,
        "realized_vol_30": _realized_vol_30(close),
        "vwap_distance": _vwap_distance(data),
        "minute_of_day": minute,
        "session": spec.session,
    }


def evaluate_regime_transition_signal(
    bars: pd.DataFrame,
    spec: LiveStrategySpec,
    *,
    min_bars: int | None = None,
) -> dict[str, Any]:
    if bars.empty:
        return {"triggered": False, "reason": "no_market_history", "bars": 0}
    data = bars.sort_values("ts").reset_index(drop=True).copy()
    required_bars = max(int(min_bars or 0), spec.lookback + 121)
    if len(data) < required_bars:
        return {"triggered": False, "reason": "insufficient_bars", "bars": int(len(data)), "required_bars": required_bars}
    data["ts"] = pd.to_datetime(data["ts"], utc=True, errors="coerce")
    for column in ["Open", "High", "Low", "Close"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    if data[["ts", "Open", "High", "Low", "Close"]].tail(required_bars).isna().any().any():
        return {"triggered": False, "reason": "invalid_ohlc", "bars": int(len(data))}
    last = data.iloc[-1]
    minute = int(last["ts"].hour * 60 + last["ts"].minute)
    if spec.session == "us_late" and not (20 * 60 <= minute < 23 * 60):
        return {"triggered": False, "reason": "outside_session", "bars": int(len(data)), "minute_of_day": minute}
    if spec.session == "europe" and not (7 * 60 <= minute < 13 * 60 + 30):
        return {"triggered": False, "reason": "outside_session", "bars": int(len(data)), "minute_of_day": minute}

    high = data["High"]
    low = data["Low"]
    close = data["Close"]
    open_price = data["Open"]
    previous_close = close.shift(1)
    true_range = pd.concat([high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1).max(axis=1)
    atr_30 = true_range.rolling(30, min_periods=10).mean()
    atr_120 = true_range.rolling(120, min_periods=30).mean()
    rolling_high = high.rolling(spec.lookback, min_periods=spec.lookback).max().shift(1)
    rolling_low = low.rolling(spec.lookback, min_periods=spec.lookback).min().shift(1)
    range_width_atr = (rolling_high - rolling_low) / atr_120.replace(0, pd.NA)
    tr_sum = true_range.rolling(spec.lookback, min_periods=spec.lookback).sum().shift(1)
    range_efficiency = (close.shift(1) - close.shift(spec.lookback + 1)).abs() / tr_sum.replace(0, pd.NA)
    range_points = high - low
    body_share = (close - open_price).abs() / range_points.replace(0, pd.NA)
    displacement_atr = range_points / atr_30.replace(0, pd.NA)
    volume_z = _volume_z(data)

    metrics = {
        "range_high": _finite_float(rolling_high.iloc[-1]),
        "range_low": _finite_float(rolling_low.iloc[-1]),
        "range_width_atr": _finite_float(range_width_atr.iloc[-1]),
        "range_efficiency": _finite_float(range_efficiency.iloc[-1]),
        "displacement_atr": _finite_float(displacement_atr.iloc[-1]),
        "body_share": _finite_float(body_share.iloc[-1]),
        "atr_30": _finite_float(atr_30.iloc[-1]),
        "volume_z": _finite_float(volume_z.iloc[-1]) if volume_z is not None else None,
    }
    missing = [key for key, value in metrics.items() if value is None and key != "volume_z"]
    if missing:
        return {"triggered": False, "reason": "invalid_regime_features", "missing": missing, "bars": int(len(data))}
    if spec.volume_z_min is not None and metrics["volume_z"] is None:
        return {"triggered": False, "reason": "missing_volume_for_volume_z", "bars": int(len(data))}
    if metrics["range_width_atr"] > spec.width_atr_max:
        return {"triggered": False, "reason": "range_too_wide", **metrics, "minute_of_day": minute}
    if metrics["range_efficiency"] > spec.efficiency_max:
        return {"triggered": False, "reason": "range_too_efficient", **metrics, "minute_of_day": minute}
    if metrics["displacement_atr"] < spec.displacement_atr_min:
        return {"triggered": False, "reason": "insufficient_displacement", **metrics, "minute_of_day": minute}
    if metrics["body_share"] < spec.body_share_min:
        return {"triggered": False, "reason": "insufficient_body_share", **metrics, "minute_of_day": minute}
    if spec.volume_z_min is not None and metrics["volume_z"] < spec.volume_z_min:
        return {"triggered": False, "reason": "insufficient_volume_z", **metrics, "minute_of_day": minute}
    breakout_buffer = max(spec.min_buffer_points, spec.breakout_buffer_atr * metrics["atr_30"])
    if not (float(last["Close"]) > metrics["range_high"] + breakout_buffer and float(last["Close"]) > float(last["Open"])):
        return {"triggered": False, "reason": "no_long_breakout", **metrics, "minute_of_day": minute}
    if spec.stop_mode != "break_bar":
        return {"triggered": False, "reason": "unsupported_stop_mode", "stop_mode": spec.stop_mode}
    stop_buffer = max(spec.min_buffer_points, spec.stop_buffer_atr * metrics["atr_30"])
    entry_price = float(last["Close"])
    stop_price = float(last["Low"]) - stop_buffer
    stop_points = entry_price - stop_price
    if stop_points < spec.min_stop_points or stop_points > spec.max_stop_points:
        return {
            "triggered": False,
            "reason": "stop_distance_outside_bounds",
            **metrics,
            "stop_points": float(stop_points),
            "minute_of_day": minute,
        }
    target_points = stop_points * spec.reward_risk
    return {
        "triggered": True,
        "reason": "strategy_signal",
        "direction": 1,
        "side": "long_regime_transition",
        "bars": int(len(data)),
        "minute_of_day": minute,
        "session": spec.session,
        "stop_price": float(stop_price),
        "stop_points": float(stop_points),
        "target_points": float(target_points),
        "horizon_minutes": int(spec.max_hold_minutes),
        "reward_risk": float(spec.reward_risk),
        **metrics,
    }


def _mtf_spec(spec: LiveStrategySpec) -> MultiTimeframeSetupSpec:
    return MultiTimeframeSetupSpec(
        name=spec.strategy_id,
        session=spec.session,
        htf_mode=spec.htf_mode,
        imbalance_threshold=spec.imbalance_threshold,
        min_hold_minutes=spec.min_hold_minutes,
        max_hold_minutes=spec.max_hold_minutes,
    )


def _required_mtf_bars(spec: MultiTimeframeSetupSpec, min_bars: int | None) -> int:
    return max(int(min_bars or 0), spec.max_hold_minutes + spec.ltf_fast_ema + 1, spec.htf_slow_ema * 15)


def _order_ready_snapshot(broker: IBKRPaperBroker, config: LiveSignalConfig) -> dict[str, Any]:
    attempts = max(1, int(config.snapshot_attempts))
    last_snapshot: dict[str, Any] = {}
    for attempt in range(attempts):
        last_snapshot = broker.tick_snapshot(config.contract)
        if last_snapshot.get("order_ready"):
            return last_snapshot
        if attempt + 1 < attempts:
            import time

            time.sleep(max(0.0, float(config.snapshot_retry_seconds)))
    return last_snapshot


def _safe_tick_by_tick_snapshot(broker: IBKRPaperBroker, contract: IBKRContractSpec, interval_seconds: float) -> list[dict[str, Any]]:
    try:
        return broker.tick_by_tick_snapshot(contract, interval_seconds=interval_seconds)
    except Exception:
        return []


def _safe_historical_minute_bars(broker: IBKRPaperBroker, contract: IBKRContractSpec) -> list[dict[str, Any]]:
    try:
        return broker.historical_minute_bars(contract)
    except Exception:
        return []


def _market_event(timestamp: datetime, top_snapshot: dict[str, Any], tick_events: list[dict[str, Any]]) -> dict[str, Any]:
    bid = _finite_float(top_snapshot.get("bid"))
    ask = _finite_float(top_snapshot.get("ask"))
    last = _finite_float(top_snapshot.get("last"))
    bid_sizes = [_finite_float(event.get("bid_size")) for event in tick_events]
    ask_sizes = [_finite_float(event.get("ask_size")) for event in tick_events]
    bid_size = _mean([value for value in bid_sizes if value is not None]) or _finite_float(top_snapshot.get("bid_size"))
    ask_size = _mean([value for value in ask_sizes if value is not None]) or _finite_float(top_snapshot.get("ask_size"))
    imbalance = None
    if bid_size is not None and ask_size is not None and bid_size + ask_size > 0:
        imbalance = (bid_size - ask_size) / (bid_size + ask_size)
    return {
        "event_type": "ibkr_live_market_event",
        "ts": timestamp.isoformat(),
        "bid": bid,
        "ask": ask,
        "last": last,
        "mid": (bid + ask) / 2 if bid is not None and ask is not None else last,
        "spread": top_snapshot.get("spread"),
        "market_data_type": top_snapshot.get("market_data_type"),
        "order_ready": top_snapshot.get("order_ready"),
        "bid_size": bid_size,
        "ask_size": ask_size,
        "imbalance_last": imbalance,
        "tick_events": len(tick_events),
    }


def _append_market_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")


def _load_recent_history(path: Path, timestamp: datetime, max_history_minutes: int) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    cutoff = timestamp - timedelta(minutes=max(1, int(max_history_minutes)))
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event_type") != "ibkr_live_market_event":
            continue
        event_ts = _parse_timestamp(event.get("ts"))
        if event_ts is None or event_ts < cutoff:
            continue
        event["ts"] = event_ts
        rows.append(event)
    return pd.DataFrame(rows)


def _load_bootstrap_bars(
    cache_path: Path | None,
    timestamp: datetime,
    required_bars: int,
) -> pd.DataFrame:
    if cache_path is None or not cache_path.exists():
        return pd.DataFrame()
    try:
        cache = pd.read_pickle(cache_path)
    except Exception:
        return pd.DataFrame()
    frames = [frame for frame in cache.values() if isinstance(frame, pd.DataFrame) and not frame.empty]
    if not frames:
        return pd.DataFrame()
    bars = pd.concat(frames, ignore_index=True)
    if "ts" not in bars.columns:
        return pd.DataFrame()
    bars = bars.copy()
    bars["ts"] = pd.to_datetime(bars["ts"], utc=True, errors="coerce")
    bars = bars.dropna(subset=["ts"]).sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    keep_count = min(len(bars), max(int(required_bars), 90))
    bars = bars.tail(keep_count).copy()
    if bars.empty:
        return pd.DataFrame()
    shift = (timestamp - timedelta(minutes=1)) - bars.iloc[-1]["ts"]
    bars["ts"] = bars["ts"] + shift
    bars["minute_of_day"] = bars["ts"].dt.hour * 60 + bars["ts"].dt.minute
    return bars.reset_index(drop=True)


def _build_minute_bars(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame()
    data = history.copy()
    data["ts"] = pd.to_datetime(data["ts"], utc=True, errors="coerce")
    data["price"] = pd.to_numeric(data["last"], errors="coerce").fillna(pd.to_numeric(data["mid"], errors="coerce"))
    data = data.dropna(subset=["ts", "price"]).sort_values("ts")
    if data.empty:
        return pd.DataFrame()
    data["minute"] = data["ts"].dt.floor("min")
    bars = data.groupby("minute", as_index=False).agg(
        Open=("price", "first"),
        High=("price", "max"),
        Low=("price", "min"),
        Close=("price", "last"),
        spread_mean=("spread", "mean"),
        imbalance_last=("imbalance_last", "last"),
        bid_size_mean=("bid_size", "mean"),
        ask_size_mean=("ask_size", "mean"),
    )
    bars = bars.rename(columns={"minute": "ts"})
    return bars.sort_values("ts").reset_index(drop=True)


def _historical_bars_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    bars = pd.DataFrame(rows)
    if "ts" not in bars.columns:
        return pd.DataFrame()
    bars["ts"] = pd.to_datetime(bars["ts"], utc=True, errors="coerce")
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        if column in bars.columns:
            bars[column] = pd.to_numeric(bars[column], errors="coerce")
    required = ["ts", "Open", "High", "Low", "Close", "Volume"]
    missing = [column for column in required if column not in bars.columns]
    if missing:
        return pd.DataFrame()
    bars = bars.dropna(subset=required).sort_values("ts").drop_duplicates("ts")
    return bars[required].reset_index(drop=True)


def _direction_from_z(z_score: float | None, threshold: float) -> int:
    if z_score is None:
        return 0
    if z_score < -threshold:
        return 1
    if z_score > threshold:
        return -1
    return 0


def _realized_vol_30(close: pd.Series) -> float:
    returns = close.pct_change()
    value = returns.rolling(30).std().iloc[-1]
    return float(value) if pd.notna(value) else 0.0


def _vwap_distance(data: pd.DataFrame) -> float:
    close = _finite_float(data.iloc[-1].get("Close"))
    if close is None:
        return 0.0
    vwap = _finite_float(data["Close"].mean())
    if vwap is None or vwap == 0:
        return 0.0
    return float((close - vwap) / vwap)


def _volume_z(data: pd.DataFrame) -> pd.Series | None:
    if "Volume" not in data.columns:
        return None
    volume = pd.to_numeric(data["Volume"], errors="coerce")
    if volume.isna().all():
        return None
    rolling = volume.rolling(60, min_periods=20)
    return (volume - rolling.mean()) / rolling.std().replace(0, pd.NA)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        timestamp = value
    else:
        try:
            timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _utc_now(value: datetime | None = None) -> datetime:
    timestamp = value or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)
