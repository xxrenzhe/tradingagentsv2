from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any

import pandas as pd

from tradingagents.backtesting.short_patterns import BacktestCosts, prepare_minute_features


SESSIONS = {
    "all": (0, 24 * 60),
    "asia": (0, 7 * 60),
    "europe": (7 * 60, 13 * 60 + 30),
    "us_rth": (13 * 60 + 30, 20 * 60),
    "us_late": (20 * 60, 24 * 60),
}


@dataclass(frozen=True)
class MultiTimeframeSetupSpec:
    """M1 trigger + recent M3 reclaim, with optional M15 trend confirmation."""

    name: str = "mtf_setup_m1_m3_m15_reclaim_imb0.3"
    session: str = "all"
    htf_mode: str = "off"
    htf_fast_ema: int = 2
    htf_slow_ema: int = 4
    mtf_fast_ema: int = 3
    mtf_slow_ema: int = 8
    ltf_fast_ema: int = 5
    reclaim_lookback_minutes: int = 3
    imbalance_threshold: float | None = 0.3
    max_spread_quantile: float | None = 0.75
    min_depth_quantile: float | None = 0.25
    stop_loss_points: float = 16.0
    take_profit_points: float = 24.0
    min_hold_minutes: int = 1
    max_hold_minutes: int = 6


def generate_multi_timeframe_specs() -> list[MultiTimeframeSetupSpec]:
    specs: list[MultiTimeframeSetupSpec] = []
    for session in ["all", "europe", "us_rth"]:
        for htf_mode in ["off", "confirm"]:
            for reclaim_lookback in [3, 5]:
                for imbalance in [None, 0.1, 0.2, 0.3, 0.35]:
                    for stop_loss, take_profit in [(8.0, 16.0), (12.0, 24.0), (16.0, 24.0), (16.0, 32.0)]:
                        imbalance_label = "noimb" if imbalance is None else f"imb{imbalance:g}"
                        specs.append(
                            MultiTimeframeSetupSpec(
                                name=(
                                    "mtf_setup_m1_m3_reclaim"
                                    f"_{session}_htf{htf_mode}_r{reclaim_lookback}"
                                    f"_{imbalance_label}_sl{stop_loss:g}_tp{take_profit:g}"
                                ),
                                session=session,
                                htf_mode=htf_mode,
                                reclaim_lookback_minutes=reclaim_lookback,
                                imbalance_threshold=imbalance,
                                stop_loss_points=stop_loss,
                                take_profit_points=take_profit,
                            )
                        )
    return specs


def prepare_multi_timeframe_features(
    bars: pd.DataFrame,
    microstructure: pd.DataFrame | None = None,
    *,
    spec: MultiTimeframeSetupSpec | None = None,
) -> pd.DataFrame:
    spec = spec or MultiTimeframeSetupSpec()
    if "ts" in bars.columns and {"Open", "High", "Low", "Close"}.issubset(bars.columns):
        base = bars.copy()
        if "Volume" not in base.columns:
            base["Volume"] = 1.0
        for column in ["spread_mean", "imbalance_mean", "imbalance_last", "depth_mean"]:
            if column not in base.columns:
                base[column] = pd.NA
    else:
        base = prepare_minute_features(bars, microstructure if microstructure is not None and not microstructure.empty else None)
    base = base.copy().sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    base["ts"] = pd.to_datetime(base["ts"], utc=True)
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        base[column] = pd.to_numeric(base[column], errors="coerce")
    for column in ["spread_mean", "imbalance_mean", "imbalance_last", "depth_mean"]:
        if column not in base.columns:
            base[column] = pd.NA
        base[column] = pd.to_numeric(base[column], errors="coerce")
    if "vwap" not in base.columns:
        base["vwap"] = (base["Close"] * base["Volume"]).cumsum() / base["Volume"].replace(0, pd.NA).cumsum()
    base["vwap"] = pd.to_numeric(base["vwap"], errors="coerce")
    base["minute_of_day"] = base["ts"].dt.hour * 60 + base["ts"].dt.minute
    base["ema_fast_1m"] = base["Close"].ewm(span=spec.ltf_fast_ema, adjust=False).mean()
    base["prev_close_1m"] = base["Close"].shift(1)
    base["prev_high_1m"] = base["High"].shift(1)
    base["prev_low_1m"] = base["Low"].shift(1)
    base["prev_ema_fast_1m"] = base["ema_fast_1m"].shift(1)

    features = _merge_context(base, _resample_context(base, "3min", "3m", spec.mtf_fast_ema, spec.mtf_slow_ema))
    features = _merge_context(features, _resample_context(base, "15min", "15m", spec.htf_fast_ema, spec.htf_slow_ema))
    return features.dropna(subset=["Open", "High", "Low", "Close"]).reset_index(drop=True)


def setup_signal_frame(features: pd.DataFrame, spec: MultiTimeframeSetupSpec | None = None) -> pd.DataFrame:
    spec = spec or MultiTimeframeSetupSpec()
    data = features.copy().sort_values("ts").reset_index(drop=True)
    data["ts"] = pd.to_datetime(data["ts"], utc=True)
    _ensure_signal_inputs(data, spec)
    minute = data["minute_of_day"] if "minute_of_day" in data.columns else data["ts"].dt.hour * 60 + data["ts"].dt.minute
    start_minute, end_minute = SESSIONS[spec.session]
    session_ok = (minute >= start_minute) & (minute < end_minute)

    raw_htf_long = (
        (data["Close_15m"] > data["ema_fast_15m"])
        & (data["ema_fast_15m"] > data["ema_slow_15m"])
        & (data["ema_fast_slope_15m"] > 0)
    )
    raw_htf_short = (
        (data["Close_15m"] < data["ema_fast_15m"])
        & (data["ema_fast_15m"] < data["ema_slow_15m"])
        & (data["ema_fast_slope_15m"] < 0)
    )
    if spec.htf_mode == "confirm":
        htf_long = raw_htf_long
        htf_short = raw_htf_short
    elif spec.htf_mode == "bias":
        htf_long = data["Close_15m"] >= data["ema_slow_15m"]
        htf_short = data["Close_15m"] <= data["ema_slow_15m"]
    elif spec.htf_mode == "off":
        htf_long = pd.Series(True, index=data.index)
        htf_short = pd.Series(True, index=data.index)
    else:
        raise ValueError(f"Unknown htf_mode: {spec.htf_mode}")
    mtf_long_cross = (data["Close_3m"] > data["ema_fast_3m"]) & (data["prev_close_3m"] <= data["prev_ema_fast_3m"])
    mtf_short_cross = (data["Close_3m"] < data["ema_fast_3m"]) & (data["prev_close_3m"] >= data["prev_ema_fast_3m"])
    recent_window = max(1, int(spec.reclaim_lookback_minutes))
    mtf_long_recent = mtf_long_cross.rolling(recent_window, min_periods=1).max().astype(bool)
    mtf_short_recent = mtf_short_cross.rolling(recent_window, min_periods=1).max().astype(bool)
    mtf_long_continuation = (data["Close_3m"] > data["ema_fast_3m"]) & (data["ema_fast_3m"] >= data["ema_slow_3m"])
    mtf_short_continuation = (data["Close_3m"] < data["ema_fast_3m"]) & (data["ema_fast_3m"] <= data["ema_slow_3m"])
    recent_pullback_long = (
        (data["prev_low_1m"] <= data["prev_ema_fast_1m"]) | (data["prev_low_1m"] <= data["vwap"])
    ).rolling(recent_window, min_periods=1).max().astype(bool)
    recent_pullback_short = (
        (data["prev_high_1m"] >= data["prev_ema_fast_1m"]) | (data["prev_high_1m"] >= data["vwap"])
    ).rolling(recent_window, min_periods=1).max().astype(bool)
    mtf_long = mtf_long_recent | (mtf_long_continuation & recent_pullback_long)
    mtf_short = mtf_short_recent | (mtf_short_continuation & recent_pullback_short)
    ltf_long = (
        (data["Close"] > data["ema_fast_1m"])
        & (data["Close"] > data["prev_high_1m"])
        & (data["Close"] > data["vwap"])
    )
    ltf_short = (
        (data["Close"] < data["ema_fast_1m"])
        & (data["Close"] < data["prev_low_1m"])
        & (data["Close"] < data["vwap"])
    )

    imbalance = _best_numeric(data, ["imbalance_last", "imbalance_last_3m", "imbalance_last_15m"])
    spread = _best_numeric(data, ["spread_mean", "spread_mean_3m", "spread_mean_15m"])
    depth = _best_numeric(data, ["depth_mean", "depth_mean_3m", "depth_mean_15m"])
    micro_ok = pd.Series(True, index=data.index)
    if spec.imbalance_threshold is not None:
        long_imbalance = imbalance >= spec.imbalance_threshold
        short_imbalance = imbalance <= -spec.imbalance_threshold
    else:
        long_imbalance = short_imbalance = pd.Series(True, index=data.index)
    if spec.max_spread_quantile is not None and spread.notna().any():
        micro_ok &= spread <= spread.quantile(spec.max_spread_quantile)
    if spec.min_depth_quantile is not None and depth.notna().any():
        micro_ok &= depth >= depth.quantile(spec.min_depth_quantile)

    long_signal = session_ok & micro_ok & htf_long & mtf_long & ltf_long & long_imbalance
    short_signal = session_ok & micro_ok & htf_short & mtf_short & ltf_short & short_imbalance
    signal = long_signal.astype(int) - short_signal.astype(int)
    signal = signal.where(signal != signal.shift(1), 0)

    data["setup_signal"] = signal.fillna(0).astype(int)
    data["setup_htf_trend"] = _direction_label(raw_htf_long, raw_htf_short)
    data["setup_mtf_reclaim"] = _direction_label(mtf_long, mtf_short)
    data["setup_ltf_trigger"] = _direction_label(ltf_long, ltf_short)
    data["setup_confidence"] = _confidence(long_signal, short_signal, htf_long, htf_short, mtf_long, mtf_short, ltf_long, ltf_short)
    data["setup_reason"] = "no_setup"
    data.loc[data["setup_signal"] > 0, "setup_reason"] = "m15_up_m3_reclaim_m1_breakout"
    data.loc[data["setup_signal"] < 0, "setup_reason"] = "m15_down_m3_reclaim_m1_breakdown"
    return data


def evaluate_multi_timeframe_setup_signal(
    features: pd.DataFrame,
    spec: MultiTimeframeSetupSpec | None = None,
    *,
    min_bars: int | None = None,
) -> dict[str, Any]:
    spec = spec or MultiTimeframeSetupSpec()
    required_bars = max(int(min_bars or 0), spec.max_hold_minutes + spec.ltf_fast_ema + 1, spec.htf_slow_ema * 15)
    if len(features) < required_bars:
        return {"triggered": False, "reason": "insufficient_bars", "bars": int(len(features)), "required_bars": required_bars}
    frame = setup_signal_frame(features, spec)
    last = frame.iloc[-1]
    direction = int(last.get("setup_signal") or 0)
    if direction == 0:
        return {
            "triggered": False,
            "reason": str(last.get("setup_reason") or "no_setup"),
            "bars": int(len(frame)),
            "htf_trend": last.get("setup_htf_trend"),
            "mtf_reclaim": last.get("setup_mtf_reclaim"),
            "ltf_trigger": last.get("setup_ltf_trigger"),
            "imbalance": _finite_float(last.get("imbalance_last")),
        }
    side = "long_mtf_setup" if direction > 0 else "short_mtf_setup"
    return {
        "triggered": True,
        "reason": str(last.get("setup_reason")),
        "direction": direction,
        "side": side,
        "bars": int(len(frame)),
        "htf_trend": last.get("setup_htf_trend"),
        "mtf_reclaim": last.get("setup_mtf_reclaim"),
        "ltf_trigger": last.get("setup_ltf_trigger"),
        "confidence": _finite_float(last.get("setup_confidence")),
        "imbalance": _finite_float(last.get("imbalance_last")),
        "spread": _finite_float(last.get("spread_mean")),
        "minute_of_day": int(last.get("minute_of_day")),
        "session": spec.session,
        "strategy_id": spec.name,
    }


def build_multi_timeframe_trades(
    features: pd.DataFrame,
    spec: MultiTimeframeSetupSpec | None = None,
    costs: BacktestCosts | None = None,
) -> pd.DataFrame:
    spec = spec or MultiTimeframeSetupSpec()
    costs = costs or BacktestCosts(point_value=2.0, tick_size=0.25, commission_per_contract=2.0)
    data = setup_signal_frame(features, spec).reset_index(drop=True)
    entries = data.loc[data["setup_signal"] != 0, ["ts", "Open", "High", "Low", "Close", "setup_signal"]]
    rows: list[dict[str, Any]] = []
    next_available_index = 0
    for entry_index, entry in entries.iterrows():
        if entry_index < next_available_index or entry_index + 1 >= len(data):
            continue
        direction = int(entry["setup_signal"])
        entry_price = float(data.at[entry_index + 1, "Open"])
        max_exit_index = min(entry_index + spec.max_hold_minutes, len(data) - 1)
        exit_index = max_exit_index
        exit_price = float(data.at[exit_index, "Close"])
        exit_reason = "time"

        stop_price = entry_price - spec.stop_loss_points if direction > 0 else entry_price + spec.stop_loss_points
        target_price = entry_price + spec.take_profit_points if direction > 0 else entry_price - spec.take_profit_points
        for path_index in range(entry_index + 1, max_exit_index + 1):
            high = float(data.at[path_index, "High"])
            low = float(data.at[path_index, "Low"])
            if direction > 0:
                stop_hit = low <= stop_price
                target_hit = high >= target_price
            else:
                stop_hit = high >= stop_price
                target_hit = low <= target_price
            if stop_hit:
                exit_index = path_index
                exit_price = stop_price
                exit_reason = "stop_loss"
                break
            if target_hit:
                exit_index = path_index
                exit_price = target_price
                exit_reason = "take_profit"
                break
            if path_index - entry_index >= spec.min_hold_minutes and int(data.at[path_index, "setup_signal"]) == -direction:
                exit_index = path_index
                exit_price = float(data.at[path_index, "Close"])
                exit_reason = "reverse_setup"
                break

        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points
        rows.append(
            {
                "entry_ts": data.at[entry_index, "ts"],
                "exit_ts": data.at[exit_index, "ts"],
                "exit_reason": exit_reason,
                "direction": direction,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_points": float(gross_points),
                "net_points": float(net_points),
                "net_dollars": float(net_points * costs.point_value),
                "entry_index": int(entry_index),
                "exit_index": int(exit_index),
                "holding_minutes": int(exit_index - entry_index),
                "portfolio_rule": spec.name,
                "selected_alias": "mtf_setup",
                "setup_id": spec.name,
                "setup_family": "multi_timeframe_reclaim",
                "setup_bias": "long" if direction > 0 else "short",
                "setup_confidence": float(data.at[entry_index, "setup_confidence"]),
                "setup_htf_trend": data.at[entry_index, "setup_htf_trend"],
                "setup_mtf_reclaim": data.at[entry_index, "setup_mtf_reclaim"],
                "setup_ltf_trigger": data.at[entry_index, "setup_ltf_trigger"],
                "setup_reason": data.at[entry_index, "setup_reason"],
            }
        )
        next_available_index = exit_index + 1
    return pd.DataFrame(rows)


def summarize_multi_timeframe_trades(
    spec: MultiTimeframeSetupSpec,
    trades: pd.DataFrame,
    costs: BacktestCosts | None = None,
) -> dict[str, Any]:
    costs = costs or BacktestCosts(point_value=2.0, tick_size=0.25, commission_per_contract=2.0)
    summary = {
        "name": spec.name,
        "session": spec.session,
        "htf_mode": spec.htf_mode,
        "htf_fast_ema": spec.htf_fast_ema,
        "htf_slow_ema": spec.htf_slow_ema,
        "mtf_fast_ema": spec.mtf_fast_ema,
        "mtf_slow_ema": spec.mtf_slow_ema,
        "ltf_fast_ema": spec.ltf_fast_ema,
        "reclaim_lookback_minutes": spec.reclaim_lookback_minutes,
        "imbalance_threshold": spec.imbalance_threshold,
        "stop_loss_points": spec.stop_loss_points,
        "take_profit_points": spec.take_profit_points,
        "max_hold_minutes": spec.max_hold_minutes,
        "round_trip_cost_points": costs.round_trip_cost_points,
    }
    if trades.empty:
        return summary | {
            "trades": 0,
            "net_points": 0.0,
            "net_dollars": 0.0,
            "max_drawdown_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_points": 0.0,
            "avg_holding_minutes": 0.0,
            "long_trades": 0,
            "short_trades": 0,
            "score": 0.0,
        }
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    wins = net[net > 0]
    losses = net[net < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(abs(losses.sum()))
    max_drawdown = float(abs(drawdown.min()))
    trade_count = int(len(trades))
    split_index = int(pd.to_numeric(trades["entry_index"], errors="coerce").median())
    first_half = float(net[pd.to_numeric(trades["entry_index"], errors="coerce") <= split_index].sum())
    second_half = float(net[pd.to_numeric(trades["entry_index"], errors="coerce") > split_index].sum())
    if first_half > 0 and second_half > 0:
        stability = min(first_half, second_half) / max(first_half, second_half)
    elif first_half + second_half > 0:
        stability = 0.25
    else:
        stability = 0.0
    risk = max(max_drawdown, abs(float(net.quantile(0.05))), 1.0)
    score = float((float(equity.iloc[-1]) / risk) * sqrt(min(trade_count, 100) / 100) * (0.75 + 0.25 * stability))
    return summary | {
        "trades": trade_count,
        "net_points": float(equity.iloc[-1]),
        "net_dollars": float(equity.iloc[-1] * costs.point_value),
        "max_drawdown_points": max_drawdown,
        "profit_factor": gross_profit / gross_loss if gross_loss else float("inf"),
        "win_rate": float((net > 0).mean()),
        "avg_points": float(net.mean()),
        "avg_holding_minutes": float(pd.to_numeric(trades["holding_minutes"], errors="coerce").mean()),
        "long_trades": int((trades["direction"].astype(int) > 0).sum()),
        "short_trades": int((trades["direction"].astype(int) < 0).sum()),
        "score": score,
    }


def _resample_context(
    base: pd.DataFrame,
    bucket: str,
    suffix: str,
    fast_ema: int,
    slow_ema: int,
) -> pd.DataFrame:
    source = base.set_index("ts")
    volume = source["Volume"].replace(0, pd.NA)
    context = pd.DataFrame(
        {
            "Open": source["Open"].resample(bucket, label="right", closed="right").first(),
            "High": source["High"].resample(bucket, label="right", closed="right").max(),
            "Low": source["Low"].resample(bucket, label="right", closed="right").min(),
            "Close": source["Close"].resample(bucket, label="right", closed="right").last(),
            "Volume": source["Volume"].resample(bucket, label="right", closed="right").sum(),
            "spread_mean": source["spread_mean"].resample(bucket, label="right", closed="right").mean(),
            "imbalance_last": source["imbalance_last"].resample(bucket, label="right", closed="right").last(),
            "depth_mean": source["depth_mean"].resample(bucket, label="right", closed="right").mean(),
            "weighted_close": (source["Close"] * volume).resample(bucket, label="right", closed="right").sum(),
        }
    ).dropna(subset=["Close"])
    context["vwap"] = context["weighted_close"].cumsum() / context["Volume"].replace(0, pd.NA).cumsum()
    context = context.drop(columns=["weighted_close"])
    context["ema_fast"] = context["Close"].ewm(span=fast_ema, adjust=False).mean()
    context["ema_slow"] = context["Close"].ewm(span=slow_ema, adjust=False).mean()
    context["ema_fast_slope"] = context["ema_fast"].diff()
    context["prev_close"] = context["Close"].shift(1)
    context["prev_high"] = context["High"].shift(1)
    context["prev_low"] = context["Low"].shift(1)
    context["prev_ema_fast"] = context["ema_fast"].shift(1)
    context = context.reset_index()
    rename = {column: f"{column}_{suffix}" for column in context.columns if column != "ts"}
    return context.rename(columns=rename).sort_values("ts")


def _merge_context(base: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    return pd.merge_asof(
        base.sort_values("ts"),
        context.sort_values("ts"),
        on="ts",
        direction="backward",
    )


def _ensure_signal_inputs(data: pd.DataFrame, spec: MultiTimeframeSetupSpec) -> None:
    if "vwap" not in data.columns:
        volume = pd.to_numeric(data.get("Volume", pd.Series(1.0, index=data.index)), errors="coerce").fillna(1.0)
        data["vwap"] = (data["Close"] * volume).cumsum() / volume.replace(0, pd.NA).cumsum()
    if "minute_of_day" not in data.columns:
        data["minute_of_day"] = data["ts"].dt.hour * 60 + data["ts"].dt.minute
    if "ema_fast_1m" not in data.columns:
        data["ema_fast_1m"] = pd.to_numeric(data["Close"], errors="coerce").ewm(span=spec.ltf_fast_ema, adjust=False).mean()
    _ensure_previous(data, "Close", "prev_close_1m")
    _ensure_previous(data, "High", "prev_high_1m")
    _ensure_previous(data, "Low", "prev_low_1m")
    _ensure_previous(data, "ema_fast_1m", "prev_ema_fast_1m")
    _ensure_previous(data, "Close_3m", "prev_close_3m")
    _ensure_previous(data, "ema_fast_3m", "prev_ema_fast_3m")
    if "ema_fast_slope_15m" not in data.columns and "ema_fast_15m" in data.columns:
        data["ema_fast_slope_15m"] = pd.to_numeric(data["ema_fast_15m"], errors="coerce").diff()


def _ensure_previous(data: pd.DataFrame, source: str, target: str) -> None:
    if target not in data.columns and source in data.columns:
        data[target] = pd.to_numeric(data[source], errors="coerce").shift(1)


def _best_numeric(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    result = pd.Series(float("nan"), index=frame.index, dtype="float64")
    for column in columns:
        if column in frame.columns:
            result = result.fillna(pd.to_numeric(frame[column], errors="coerce"))
    return result


def _direction_label(long_mask: pd.Series, short_mask: pd.Series) -> pd.Series:
    label = pd.Series("flat", index=long_mask.index)
    label = label.mask(long_mask, "long")
    label = label.mask(short_mask, "short")
    return label


def _confidence(
    long_signal: pd.Series,
    short_signal: pd.Series,
    htf_long: pd.Series,
    htf_short: pd.Series,
    mtf_long: pd.Series,
    mtf_short: pd.Series,
    ltf_long: pd.Series,
    ltf_short: pd.Series,
) -> pd.Series:
    any_signal = long_signal | short_signal
    htf = htf_long | htf_short
    mtf = mtf_long | mtf_short
    ltf = ltf_long | ltf_short
    return (0.25 + 0.25 * htf.astype(float) + 0.25 * mtf.astype(float) + 0.25 * ltf.astype(float)).where(any_signal, 0.0)


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None
