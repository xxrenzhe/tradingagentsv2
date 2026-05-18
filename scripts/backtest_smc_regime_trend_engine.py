from __future__ import annotations

import argparse
import html
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"
for path in (ROOT_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.dataflows.databento import _bar_zip_path


BULLISH = 1
BEARISH = -1


@dataclass(frozen=True)
class RegimeTrendConfig:
    session: str = "ldn_ny"
    adx_length: int = 14
    chop_length: int = 14
    donchian_length: int = 50
    supertrend_length: int = 14
    supertrend_mult: float = 3.0
    atr_length: int = 14
    ema_length: int = 100
    trend_lookback: int = 30
    pullback_recent_bars: int = 18
    entry_stop_atr_mult: float = 1.5
    min_stop_points: float = 8.0
    max_hold_bars: int = 90
    adx_min: float = 22.0
    chop_max: float = 50.0
    donchian_atr_min: float = 1.4
    decay_adx_bars: int = 5
    structure_source: str = "fast"


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    previous_close = close.shift(1)
    return pd.concat([high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1).max(axis=1)


def add_regime_indicators(frame: pd.DataFrame, config: RegimeTrendConfig) -> pd.DataFrame:
    out = frame.copy()
    high = out["High"].astype(float)
    low = out["Low"].astype(float)
    close = out["Close"].astype(float)
    tr = true_range(high, low, close)
    atr = tr.rolling(config.atr_length, min_periods=config.atr_length).mean()
    out["atr"] = atr
    out["ema"] = close.ewm(span=config.ema_length, adjust=False, min_periods=config.ema_length).mean()

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=out.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=out.index)
    atr_adx = tr.rolling(config.adx_length, min_periods=config.adx_length).mean()
    plus_di = 100.0 * plus_dm.rolling(config.adx_length, min_periods=config.adx_length).mean() / atr_adx.replace(0, np.nan)
    minus_di = 100.0 * minus_dm.rolling(config.adx_length, min_periods=config.adx_length).mean() / atr_adx.replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    out["plus_di"] = plus_di
    out["minus_di"] = minus_di
    out["adx"] = dx.rolling(config.adx_length, min_periods=config.adx_length).mean()

    highest = high.rolling(config.chop_length, min_periods=config.chop_length).max()
    lowest = low.rolling(config.chop_length, min_periods=config.chop_length).min()
    tr_sum = tr.rolling(config.chop_length, min_periods=config.chop_length).sum()
    out["chop"] = 100.0 * np.log10(tr_sum / (highest - lowest).replace(0, np.nan)) / np.log10(config.chop_length)

    out["donchian_high"] = high.rolling(config.donchian_length, min_periods=config.donchian_length).max().shift(1)
    out["donchian_low"] = low.rolling(config.donchian_length, min_periods=config.donchian_length).min().shift(1)
    out["donchian_mid"] = (out["donchian_high"] + out["donchian_low"]) / 2.0
    out["donchian_width_atr"] = (out["donchian_high"] - out["donchian_low"]) / atr.replace(0, np.nan)

    basic_upper = (high + low) / 2.0 + config.supertrend_mult * atr
    basic_lower = (high + low) / 2.0 - config.supertrend_mult * atr
    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    trend = np.ones(len(out), dtype=np.int8)
    supertrend = np.full(len(out), np.nan)
    for index in range(1, len(out)):
        if np.isfinite(final_upper.iat[index - 1]):
            if basic_upper.iat[index] >= final_upper.iat[index - 1] and close.iat[index - 1] <= final_upper.iat[index - 1]:
                final_upper.iat[index] = final_upper.iat[index - 1]
        if np.isfinite(final_lower.iat[index - 1]):
            if basic_lower.iat[index] <= final_lower.iat[index - 1] and close.iat[index - 1] >= final_lower.iat[index - 1]:
                final_lower.iat[index] = final_lower.iat[index - 1]
        if close.iat[index] > final_upper.iat[index - 1]:
            trend[index] = BULLISH
        elif close.iat[index] < final_lower.iat[index - 1]:
            trend[index] = BEARISH
        else:
            trend[index] = trend[index - 1]
        supertrend[index] = final_lower.iat[index] if trend[index] == BULLISH else final_upper.iat[index]
    out["supertrend"] = supertrend
    out["supertrend_dir"] = trend
    return out


def session_mask(frame: pd.DataFrame, session: str) -> pd.Series:
    minute = frame["minute_of_day"]
    if session == "all":
        return pd.Series(True, index=frame.index)
    if session == "ldn_ny":
        return (minute >= 7 * 60) & (minute < 20 * 60)
    if session == "us_rth":
        return (minute >= 13 * 60 + 30) & (minute < 20 * 60)
    if session == "us_late":
        return (minute >= 20 * 60) & (minute < 23 * 60)
    if session == "europe":
        return (minute >= 7 * 60) & (minute < 13 * 60 + 30)
    raise ValueError(f"unknown session: {session}")


def confirmed_pivots(values: np.ndarray, size: int, find_highs: bool) -> np.ndarray:
    pivots = np.zeros(len(values), dtype=bool)
    for index in range(size, len(values)):
        pivot_index = index - size
        window = values[pivot_index + 1 : index + 1]
        if window.size == 0:
            continue
        if find_highs and values[pivot_index] > np.nanmax(window):
            pivots[index] = True
        elif not find_highs and values[pivot_index] < np.nanmin(window):
            pivots[index] = True
    return pivots


def build_fast_smc_signals(bars: pd.DataFrame) -> pd.DataFrame:
    frame = bars.copy().reset_index(drop=True)
    high = frame["High"].to_numpy(dtype=float)
    low = frame["Low"].to_numpy(dtype=float)
    close = frame["Close"].to_numpy(dtype=float)

    signals = {
        "internal_bos": np.zeros(len(frame), dtype=np.int8),
        "internal_choch": np.zeros(len(frame), dtype=np.int8),
        "swing_bos": np.zeros(len(frame), dtype=np.int8),
        "swing_choch": np.zeros(len(frame), dtype=np.int8),
        "fvg": np.zeros(len(frame), dtype=np.int8),
        "premium_discount_reversal": np.zeros(len(frame), dtype=np.int8),
    }
    pivot_masks = {
        "internal_high": confirmed_pivots(high, 5, True),
        "internal_low": confirmed_pivots(low, 5, False),
        "swing_high": confirmed_pivots(high, 50, True),
        "swing_low": confirmed_pivots(low, 50, False),
    }
    state: dict[str, dict[str, Any]] = {
        "internal": {"size": 5, "trend": 0, "high_level": np.nan, "low_level": np.nan, "high_crossed": True, "low_crossed": True},
        "swing": {"size": 50, "trend": 0, "high_level": np.nan, "low_level": np.nan, "high_crossed": True, "low_crossed": True},
    }
    swing_top = np.nan
    swing_bottom = np.nan
    body_abs = np.abs(close - frame["Open"].to_numpy(dtype=float))
    body_mean = pd.Series(body_abs).rolling(100, min_periods=20).mean().to_numpy(dtype=float)

    for index in range(len(frame)):
        if index >= 2:
            if low[index] > high[index - 2] and close[index - 1] > high[index - 2] and body_abs[index - 1] > body_mean[index - 1]:
                signals["fvg"][index] = BULLISH
            elif high[index] < low[index - 2] and close[index - 1] < low[index - 2] and body_abs[index - 1] > body_mean[index - 1]:
                signals["fvg"][index] = BEARISH

        for prefix, current in state.items():
            size = int(current["size"])
            if pivot_masks[f"{prefix}_high"][index]:
                pivot_index = index - size
                current["high_level"] = high[pivot_index]
                current["high_crossed"] = False
                if prefix == "swing":
                    swing_top = high[pivot_index]
            if pivot_masks[f"{prefix}_low"][index]:
                pivot_index = index - size
                current["low_level"] = low[pivot_index]
                current["low_crossed"] = False
                if prefix == "swing":
                    swing_bottom = low[pivot_index]

            previous_close = close[index - 1] if index else close[index]
            high_level = float(current["high_level"])
            if np.isfinite(high_level) and not bool(current["high_crossed"]) and previous_close <= high_level and close[index] > high_level:
                tag = "choch" if int(current["trend"]) == BEARISH else "bos"
                signals[f"{prefix}_{tag}"][index] = BULLISH
                current["high_crossed"] = True
                current["trend"] = BULLISH

            low_level = float(current["low_level"])
            if np.isfinite(low_level) and not bool(current["low_crossed"]) and previous_close >= low_level and close[index] < low_level:
                tag = "choch" if int(current["trend"]) == BULLISH else "bos"
                signals[f"{prefix}_{tag}"][index] = BEARISH
                current["low_crossed"] = True
                current["trend"] = BEARISH

        if np.isfinite(swing_top) and np.isfinite(swing_bottom) and swing_top > swing_bottom:
            premium_floor = 0.95 * swing_top + 0.05 * swing_bottom
            discount_ceiling = 0.05 * swing_top + 0.95 * swing_bottom
            if close[index] >= premium_floor:
                signals["premium_discount_reversal"][index] = BEARISH
            elif close[index] <= discount_ceiling:
                signals["premium_discount_reversal"][index] = BULLISH

    for name, values in signals.items():
        frame[name] = values
    return frame


def build_engine_features(bars: pd.DataFrame, config: RegimeTrendConfig) -> pd.DataFrame:
    required = {"internal_bos", "internal_choch", "swing_bos", "fvg", "premium_discount_reversal"}
    out = bars.copy().reset_index(drop=True) if required.issubset(bars.columns) else build_fast_smc_signals(bars)
    out = add_regime_indicators(out, config)
    close = out["Close"].astype(float)
    high = out["High"].astype(float)
    low = out["Low"].astype(float)
    internal_bos = out["internal_bos"].astype(int)
    internal_choch = out["internal_choch"].astype(int)
    swing_bos = out["swing_bos"].astype(int)
    fvg = out["fvg"].astype(int)
    pd_zone = out["premium_discount_reversal"].astype(int)

    trend_regime = (
        (out["adx"] >= config.adx_min)
        & (out["chop"] <= config.chop_max)
        & (out["donchian_width_atr"] >= config.donchian_atr_min)
    )
    long_bias = (
        trend_regime
        & (close > out["ema"])
        & (close > out["donchian_mid"])
        & (out["plus_di"] > out["minus_di"])
        & (out["supertrend_dir"] == BULLISH)
    )
    short_bias = (
        trend_regime
        & (close < out["ema"])
        & (close < out["donchian_mid"])
        & (out["minus_di"] > out["plus_di"])
        & (out["supertrend_dir"] == BEARISH)
    )

    pullback_long = (
        (low <= out["donchian_mid"])
        | (pd_zone == BULLISH)
        | (fvg == BULLISH)
    ).rolling(config.pullback_recent_bars, min_periods=1).max().shift(1).fillna(False).astype(bool)
    pullback_short = (
        (high >= out["donchian_mid"])
        | (pd_zone == BEARISH)
        | (fvg == BEARISH)
    ).rolling(config.pullback_recent_bars, min_periods=1).max().shift(1).fillna(False).astype(bool)

    trend_start_long = long_bias & ((internal_choch == BULLISH) | (swing_bos == BULLISH)) & (close > out["donchian_high"])
    trend_start_short = short_bias & ((internal_choch == BEARISH) | (swing_bos == BEARISH)) & (close < out["donchian_low"])
    previous_trend = trend_regime.shift(1).fillna(False).astype(bool)
    trend_start_window = (trend_regime & ~previous_trend).rolling(config.trend_lookback, min_periods=1).max().fillna(False).astype(bool)
    recent_start_long = trend_start_long.rolling(config.trend_lookback, min_periods=1).max().shift(1).fillna(False).astype(bool)
    recent_start_short = trend_start_short.rolling(config.trend_lookback, min_periods=1).max().shift(1).fillna(False).astype(bool)
    continuation_long = long_bias & pullback_long & recent_start_long & (internal_bos == BULLISH)
    continuation_short = short_bias & pullback_short & recent_start_short & (internal_bos == BEARISH)

    out["range_regime"] = (~trend_regime).astype(np.int8)
    out["trend_regime"] = trend_regime.astype(np.int8)
    out["engine_signal"] = np.select(
        [(trend_start_long & trend_start_window) | continuation_long, (trend_start_short & trend_start_window) | continuation_short],
        [BULLISH, BEARISH],
        default=0,
    ).astype(np.int8)
    out["engine_family"] = np.select(
        [trend_start_long | trend_start_short, continuation_long | continuation_short],
        ["trend_start", "trend_continuation"],
        default="",
    )
    out.loc[~session_mask(out, config.session), "engine_signal"] = 0
    out["engine_signal"] = out["engine_signal"].where(out["engine_signal"] != out["engine_signal"].shift(1), 0).astype(np.int8)
    return out


def backtest_engine(frame: pd.DataFrame, config: RegimeTrendConfig, costs: BacktestCosts) -> pd.DataFrame:
    signal = frame["engine_signal"].to_numpy(dtype=np.int8)
    signal_indexes = np.flatnonzero(signal != 0)
    if len(signal_indexes) == 0:
        return pd.DataFrame()

    open_prices = frame["Open"].to_numpy(dtype=float)
    high_prices = frame["High"].to_numpy(dtype=float)
    low_prices = frame["Low"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    timestamps = frame["ts"].to_numpy()
    symbols = frame["symbol"].astype(str).to_numpy()
    atr = frame["atr"].to_numpy(dtype=float)
    supertrend = frame["supertrend"].to_numpy(dtype=float)
    supertrend_dir = frame["supertrend_dir"].to_numpy(dtype=np.int8)
    adx = frame["adx"].to_numpy(dtype=float)
    chop = frame["chop"].to_numpy(dtype=float)
    opposite_choch = frame["internal_choch"].to_numpy(dtype=np.int8)
    families = frame["engine_family"].astype(str).to_numpy()

    rows: list[dict[str, Any]] = []
    next_available_index = 0
    for signal_index in signal_indexes:
        entry_index = int(signal_index) + 1
        if entry_index <= next_available_index or entry_index >= len(frame):
            continue
        direction = int(signal[signal_index])
        entry_price = float(open_prices[entry_index])
        if not np.isfinite(entry_price):
            continue
        stop_distance = max(config.min_stop_points, float(atr[signal_index]) * config.entry_stop_atr_mult if np.isfinite(atr[signal_index]) else config.min_stop_points)
        stop_price = entry_price - stop_distance if direction > 0 else entry_price + stop_distance
        planned_exit = min(entry_index + config.max_hold_bars, len(frame) - 1)
        exit_index = planned_exit
        exit_price = float(close_prices[planned_exit])
        exit_reason = "time"

        for path_index in range(entry_index + 1, planned_exit + 1):
            if symbols[path_index] != symbols[signal_index]:
                exit_index = max(entry_index, path_index - 1)
                exit_price = float(close_prices[exit_index])
                exit_reason = "symbol_change"
                break
            if direction > 0 and low_prices[path_index] <= stop_price:
                exit_index = path_index
                exit_price = float(stop_price)
                exit_reason = "stop_loss"
                break
            if direction < 0 and high_prices[path_index] >= stop_price:
                exit_index = path_index
                exit_price = float(stop_price)
                exit_reason = "stop_loss"
                break
            if direction > 0 and supertrend_dir[path_index] == BEARISH:
                exit_index = path_index
                exit_price = float(close_prices[path_index])
                exit_reason = "supertrend_flip"
                break
            if direction < 0 and supertrend_dir[path_index] == BULLISH:
                exit_index = path_index
                exit_price = float(close_prices[path_index])
                exit_reason = "supertrend_flip"
                break
            if direction > 0 and opposite_choch[path_index] == BEARISH:
                exit_index = path_index
                exit_price = float(close_prices[path_index])
                exit_reason = "opposite_choch"
                break
            if direction < 0 and opposite_choch[path_index] == BULLISH:
                exit_index = path_index
                exit_price = float(close_prices[path_index])
                exit_reason = "opposite_choch"
                break
            if path_index >= config.decay_adx_bars:
                recent_adx = adx[path_index - config.decay_adx_bars + 1 : path_index + 1]
                if np.all(np.diff(recent_adx) < 0) and chop[path_index] > 55:
                    exit_index = path_index
                    exit_price = float(close_prices[path_index])
                    exit_reason = "trend_decay"
                    break

        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points
        rows.append(
            {
                "signal_ts": timestamps[signal_index],
                "entry_ts": timestamps[entry_index],
                "exit_ts": timestamps[exit_index],
                "symbol": symbols[signal_index],
                "direction": direction,
                "family": families[signal_index],
                "entry_price": entry_price,
                "exit_price": exit_price,
                "stop_price": float(stop_price),
                "exit_reason": exit_reason,
                "gross_points": float(gross_points),
                "net_points": float(net_points),
                "net_dollars": float(net_points * costs.point_value),
                "entry_index": int(entry_index),
                "exit_index": int(exit_index),
                "signal_index": int(signal_index),
            }
        )
        next_available_index = exit_index + 1
    return pd.DataFrame(rows)


def summarize_trades(trades: pd.DataFrame, costs: BacktestCosts) -> dict[str, Any]:
    if trades.empty:
        return {"trades": 0}
    net = trades["net_points"].astype(float)
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    wins = net[net > 0].sum()
    losses = abs(net[net < 0].sum())
    return {
        "trades": int(len(net)),
        "net_points": float(net.sum()),
        "net_dollars": float(net.sum() * costs.point_value),
        "profit_factor": float(wins / losses) if losses else 999.0,
        "win_rate": float((net > 0).mean()),
        "avg_points": float(net.mean()),
        "median_points": float(net.median()),
        "max_drawdown_points": float(abs(drawdown.min())),
        "best_trade_points": float(net.max()),
        "worst_trade_points": float(net.min()),
    }


def score_summary(summary: dict[str, Any]) -> float:
    trades = float(summary.get("trades", 0))
    net = float(summary.get("net_points", 0))
    profit_factor = float(summary.get("profit_factor", 0))
    max_drawdown = float(summary.get("max_drawdown_points", 0))
    if trades < 30 or net <= 0 or profit_factor <= 1:
        return -1_000_000.0 + net
    return net + 120.0 * (profit_factor - 1.0) - 0.8 * max_drawdown + min(trades, 350.0) * 0.25


def config_from_args(args: argparse.Namespace) -> RegimeTrendConfig:
    return RegimeTrendConfig(
        session=args.session,
        adx_min=args.adx_min,
        chop_max=args.chop_max,
        donchian_atr_min=args.donchian_atr_min,
        donchian_length=args.donchian_length,
        ema_length=args.ema_length,
        pullback_recent_bars=args.pullback_recent_bars,
        entry_stop_atr_mult=args.entry_stop_atr_mult,
        min_stop_points=args.min_stop_points,
        max_hold_bars=args.max_hold_bars,
    )


def search_configs(bars: pd.DataFrame, costs: BacktestCosts, args: argparse.Namespace) -> tuple[RegimeTrendConfig, pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    best_config: RegimeTrendConfig | None = None
    best_frame = pd.DataFrame()
    best_score = -np.inf
    base = config_from_args(args)
    structure_frame = build_fast_smc_signals(bars)
    for session in ["us_rth", "ldn_ny"]:
        for adx_min in [25.0, 28.0]:
            for chop_max in [42.0, 46.0]:
                for donchian_length in [30, 50]:
                    for max_hold_bars in [60, 120]:
                        config = RegimeTrendConfig(
                            session=session,
                            adx_min=adx_min,
                            chop_max=chop_max,
                            donchian_atr_min=base.donchian_atr_min,
                            donchian_length=donchian_length,
                            ema_length=base.ema_length,
                            pullback_recent_bars=base.pullback_recent_bars,
                            entry_stop_atr_mult=base.entry_stop_atr_mult,
                            min_stop_points=base.min_stop_points,
                            max_hold_bars=max_hold_bars,
                        )
                        frame = build_engine_features(structure_frame, config)
                        trades = backtest_engine(frame, config, costs)
                        summary = summarize_trades(trades, costs)
                        yearly = yearly_summary(trades, costs)
                        positive_years = int((yearly["net_points"] > 0).sum()) if not yearly.empty else 0
                        row = {
                            "session": session,
                            "adx_min": adx_min,
                            "chop_max": chop_max,
                            "donchian_length": donchian_length,
                            "max_hold_bars": max_hold_bars,
                            "positive_years": positive_years,
                            **summary,
                        }
                        row["score"] = score_summary(summary) + positive_years * 35.0
                        rows.append(row)
                        if row["score"] > best_score:
                            best_score = float(row["score"])
                            best_config = config
                            best_frame = frame
    if best_config is None:
        raise RuntimeError("no config searched")
    leaderboard = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    return best_config, best_frame, leaderboard


def yearly_summary(trades: pd.DataFrame, costs: BacktestCosts) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    data = trades.copy()
    data["year"] = pd.to_datetime(data["entry_ts"], utc=True).dt.year
    return pd.DataFrame([{"year": int(year), **summarize_trades(group, costs)} for year, group in data.groupby("year")])


def fmt(value: Any, digits: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return html.escape(str(value))
    if not np.isfinite(number):
        return "N/A"
    return f"{number:,.{digits}f}"


def pct(value: Any) -> str:
    return f"{float(value):.2%}" if value is not None and np.isfinite(float(value)) else "N/A"


def table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    rows = []
    for _, row in frame[columns].iterrows():
        cells = []
        for column in columns:
            value = row[column]
            text = fmt(value, 3) if isinstance(value, (float, np.floating)) else html.escape(str(value))
            cells.append(f"<td>{text}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def chart_for_trade(frame: pd.DataFrame, trade: pd.Series, title: str) -> str:
    entry_index = int(trade["entry_index"])
    exit_index = int(trade["exit_index"])
    start = max(0, entry_index - 90)
    end = min(len(frame), exit_index + 90)
    data = frame.iloc[start:end].copy()
    direction = int(trade["direction"])
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.72, 0.28])
    fig.add_trace(
        go.Candlestick(
            x=data["ts"],
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name="NQ 1m",
            increasing_line_color="#089981",
            decreasing_line_color="#f23645",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(go.Scatter(x=data["ts"], y=data["supertrend"], name="Supertrend", line={"color": "#facc15", "width": 1.5}), row=1, col=1)
    fig.add_trace(go.Scatter(x=data["ts"], y=data["donchian_mid"], name="Donchian mid", line={"color": "#38bdf8", "width": 1, "dash": "dot"}), row=1, col=1)
    fig.add_trace(go.Scatter(x=data["ts"], y=data["adx"], name="ADX", line={"color": "#22c55e", "width": 2}), row=2, col=1)
    fig.add_trace(go.Scatter(x=data["ts"], y=data["chop"], name="CHOP", line={"color": "#f97316", "width": 2}), row=2, col=1)
    fig.add_trace(
        go.Scatter(
            x=[trade["entry_ts"]],
            y=[trade["entry_price"]],
            mode="markers+text",
            marker={"size": 14, "symbol": "triangle-up" if direction > 0 else "triangle-down", "color": "#22c55e" if direction > 0 else "#ef4444"},
            text=["ENTRY"],
            textposition="top center",
            name="Entry",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=[trade["exit_ts"]],
            y=[trade["exit_price"]],
            mode="markers+text",
            marker={"size": 14, "symbol": "x", "color": "#38bdf8"},
            text=["EXIT"],
            textposition="bottom center",
            name="Exit",
        ),
        row=1,
        col=1,
    )
    fig.add_hline(y=float(trade["stop_price"]), line_dash="dot", line_color="#ef4444", annotation_text="Stop", row=1, col=1)
    fig.add_hline(y=22, line_dash="dot", line_color="#22c55e", row=2, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color="#f97316", row=2, col=1)
    fig.update_layout(title=title, template="plotly_dark", height=660, margin={"l": 40, "r": 20, "t": 58, "b": 36}, xaxis_rangeslider_visible=False)
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def build_report(
    frame: pd.DataFrame,
    trades: pd.DataFrame,
    summary: dict[str, Any],
    yearly: pd.DataFrame,
    config: RegimeTrendConfig,
    args: argparse.Namespace,
    leaderboard: pd.DataFrame | None = None,
) -> str:
    best = trades.sort_values("net_points", ascending=False).head(5).copy() if not trades.empty else pd.DataFrame()
    if not best.empty:
        best["entry_ts_text"] = pd.to_datetime(best["entry_ts"], utc=True).astype(str)
        best["exit_ts_text"] = pd.to_datetime(best["exit_ts"], utc=True).astype(str)
        best["side"] = np.where(best["direction"] > 0, "LONG", "SHORT")
    cards = [
        ("Trades", fmt(summary.get("trades", 0), 0)),
        ("Net Points", fmt(summary.get("net_points", 0))),
        ("Net Dollars", fmt(summary.get("net_dollars", 0))),
        ("PF", fmt(summary.get("profit_factor", 0), 3)),
        ("Win Rate", pct(summary.get("win_rate", 0))),
        ("Max DD", fmt(summary.get("max_drawdown_points", 0))),
        ("Avg/Trade", fmt(summary.get("avg_points", 0), 3)),
        ("Worst Trade", fmt(summary.get("worst_trade_points", 0))),
    ]
    chart_html = "\n".join(
        f"<section class='chart'>{chart_for_trade(frame, row, f'Best Trend Trade #{rank}: {row.net_points:.2f} pts')}</section>"
        for rank, (_, row) in enumerate(best.head(3).iterrows(), start=1)
    )
    family = trades.groupby(["family", "direction"], as_index=False)["net_points"].agg(["count", "sum", "mean"]).reset_index() if not trades.empty else pd.DataFrame()
    best_html = table(best, ["entry_ts_text", "exit_ts_text", "side", "family", "entry_price", "exit_price", "net_points", "exit_reason"]) if not best.empty else "<p>No trades.</p>"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>NQ SMC Regime Trend Engine</title>
  <style>
    body {{ margin:0; background:#07111f; color:#e5edf7; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ max-width:1200px; margin:0 auto; padding:32px 24px 72px; }}
    h1 {{ font-size:34px; margin:0 0 8px; }}
    h2 {{ margin-top:34px; padding-bottom:8px; border-bottom:1px solid #263246; }}
    p,li {{ color:#b8c4d6; line-height:1.65; }}
    code {{ color:#93c5fd; }}
    .cards {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin:24px 0; }}
    .card {{ background:linear-gradient(145deg,#111827,#172033); border:1px solid #263246; border-radius:14px; padding:16px; }}
    .card span {{ display:block; color:#8ea0b9; font-size:13px; }}
    .card strong {{ display:block; margin-top:8px; font-size:23px; }}
    .note {{ background:#0f1d2d; border-left:4px solid #38bdf8; padding:14px 16px; border-radius:10px; }}
    table {{ border-collapse:collapse; width:100%; margin:12px 0 24px; font-size:13px; }}
    th,td {{ border:1px solid #263246; padding:8px 10px; text-align:right; }}
    th:first-child,td:first-child {{ text-align:left; }}
    th {{ background:#162033; color:#dbeafe; }}
    .chart {{ margin-top:22px; border:1px solid #263246; border-radius:14px; overflow:hidden; background:#111827; }}
  </style>
</head>
<body>
<main>
  <h1>NQ 2020+ SMC-Regime Trend Engine</h1>
  <p>数据源：<code>{html.escape(str(_bar_zip_path()))}</code>；区间：<code>{args.start_date}</code> 到 <code>{args.end_date}</code>；实际加载：<code>{frame['ts'].min()}</code> 到 <code>{frame['ts'].max()}</code>。</p>
  <div class="cards">{''.join(f"<div class='card'><span>{label}</span><strong>{value}</strong></div>" for label, value in cards)}</div>

  <h2>系统原理</h2>
  <p class="note">这是趋势系统首版，不是直觉追单。ADX/CHOP/Donchian 先判断趋势区间，Lightglow/ICT 的 CHoCH/BOS/FVG/Premium-Discount 只负责趋势起步和中继入场，Supertrend、反向 CHoCH、ADX 衰减负责退出。</p>
  <ul>
    <li>趋势区间：ADX >= <code>{config.adx_min}</code>，CHOP <= <code>{config.chop_max}</code>，Donchian 宽度/ATR >= <code>{config.donchian_atr_min}</code>。</li>
    <li>趋势起步：趋势 regime + 偏向过滤 + internal CHoCH 或 swing BOS + Donchian 突破。</li>
    <li>趋势中继：趋势 regime + 回踩 Donchian mid / FVG / Premium-Discount 区后，internal BOS 继续。</li>
    <li>退出：硬止损、Supertrend 翻转、反向 CHoCH、ADX 连续下降且 CHOP 回升、或最长 <code>{config.max_hold_bars}</code> 分钟。</li>
    <li>执行：所有信号收盘确认，下一根开盘入场；入场 K 线内不检查出场。</li>
    <li>无未来函数约束：摆动高低点只在右侧 <code>5/50</code> 根完成后才确认；Donchian 通道整体 <code>shift(1)</code>；交易价全部使用下一根开盘；图表中的 ENTRY/EXIT 为实际成交 bar。</li>
  </ul>

  <h2>参数与搜索</h2>
  <p>最终参数：session=<code>{config.session}</code>，ADX >= <code>{config.adx_min}</code>，CHOP <= <code>{config.chop_max}</code>，Donchian=<code>{config.donchian_length}</code>，最大持仓=<code>{config.max_hold_bars}</code> 分钟。</p>
  {table(leaderboard.head(12), ["session", "adx_min", "chop_max", "donchian_length", "max_hold_bars", "trades", "net_points", "profit_factor", "win_rate", "max_drawdown_points", "positive_years", "score"]) if leaderboard is not None and not leaderboard.empty else "<p>未启用参数搜索。</p>"}

  <h2>年度结果</h2>
  {table(yearly, ["year", "trades", "net_points", "net_dollars", "profit_factor", "win_rate", "max_drawdown_points"]) if not yearly.empty else "<p>No yearly rows.</p>"}

  <h2>信号族表现</h2>
  {table(family, ["family", "direction", "count", "sum", "mean"]) if not family.empty else "<p>No family rows.</p>"}

  <h2>最佳趋势入场/出场</h2>
  {best_html}
  {chart_html}
</main>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest SMC-Regime Trend Engine on NQ 1m bars.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-smc-regime-trend-cache.pkl")
    parser.add_argument("--feature-cache", default=".tmp/nq-smc-regime-trend-features.pkl")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--trades-output", default=".tmp/nq-smc-regime-trend-trades.csv")
    parser.add_argument("--report", default="reports/NQ-smc-regime-trend-engine-2020.html")
    parser.add_argument("--search", action="store_true", help="Run a small causal parameter grid and use the top configuration.")
    parser.add_argument("--session", default="ldn_ny", choices=["all", "ldn_ny", "us_rth", "us_late", "europe"])
    parser.add_argument("--adx-min", type=float, default=22.0)
    parser.add_argument("--chop-max", type=float, default=50.0)
    parser.add_argument("--donchian-atr-min", type=float, default=1.4)
    parser.add_argument("--donchian-length", type=int, default=50)
    parser.add_argument("--ema-length", type=int, default=100)
    parser.add_argument("--pullback-recent-bars", type=int, default=18)
    parser.add_argument("--entry-stop-atr-mult", type=float, default=1.5)
    parser.add_argument("--min-stop-points", type=float, default=8.0)
    parser.add_argument("--max-hold-bars", type=int, default=90)
    args = parser.parse_args()

    costs = BacktestCosts()
    bars = load_continuous_nq_bars(args)
    leaderboard: pd.DataFrame | None = None
    config = config_from_args(args)
    feature_cache = Path(args.feature_cache)
    feature_key = {
        "start_date": args.start_date,
        "end_date": args.end_date,
        "rows": len(bars),
        "first_ts": str(bars["ts"].min()),
        "last_ts": str(bars["ts"].max()),
        "config": config.__dict__,
    }
    if args.search:
        config, frame, leaderboard = search_configs(bars, costs, args)
    elif feature_cache.exists():
        payload = pd.read_pickle(feature_cache)
        if isinstance(payload, dict) and payload.get("key") == feature_key:
            frame = payload["frame"]
        else:
            frame = build_engine_features(bars, config)
            feature_cache.parent.mkdir(parents=True, exist_ok=True)
            pd.to_pickle({"key": feature_key, "frame": frame}, feature_cache)
    else:
        frame = build_engine_features(bars, config)
        feature_cache.parent.mkdir(parents=True, exist_ok=True)
        pd.to_pickle({"key": feature_key, "frame": frame}, feature_cache)
    trades = backtest_engine(frame, config, costs)
    Path(args.trades_output).parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(args.trades_output, index=False)
    summary = summarize_trades(trades, costs)
    year = yearly_summary(trades, costs)
    report = build_report(frame, trades, summary, year, config, args, leaderboard)
    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"wrote {out}")
    print(f"wrote {args.trades_output}")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
