from __future__ import annotations

import argparse
import html
import re
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
NQ_SYMBOL_RE = re.compile(r"^NQ[HMUZ]\d$")
BAR_CSV_PATH = ROOT_DIR / "data" / "raw" / "databento" / "glbx-mdp3-20100606-20260427.ohlcv-1m.csv"


@dataclass(frozen=True)
class StrategyConfig:
    session: str = "ldn_ny"
    compression_lookback: int = 45
    compression_confirm_bars: int = 18
    sweep_lookback: int = 60
    sweep_recent_bars: int = 12
    range_lookback: int = 45
    range_recent_bars: int = 18
    range_break_buffer_atr: float = 0.10
    absorption_recent_bars: int = 20
    shock_atr_mult: float = 2.2
    shock_body_share: float = 0.55
    trend_lookback: int = 30
    max_hold_bars: int = 60
    stop_atr_mult: float = 1.35
    target_atr_mult: float = 2.10
    min_stop_points: float = 8.0
    min_target_points: float = 12.0
    max_stop_points: float = 45.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    variant: str = "base"


SETUP_DESCRIPTIONS = {
    "compression_breakout_long": {
        "name": "蓄势突破做多",
        "features": "低波动箱体压缩，成交量不极端，随后向上突破箱体上沿并打印 bullish BOS/CHoCH，MACD 柱体转正或扩张。",
        "strategy": "信号收盘确认后下一根开盘做多；止损放在 ATR/箱体风险外，止盈按 ATR 目标或最多持仓 60 分钟。",
    },
    "eqh_distribution_short": {
        "name": "扫高分配做空",
        "features": "价格扫过前 60 分钟高点但收回，premium/高位区域出现 bearish CHoCH/BOS，再跌破近端箱体下沿。",
        "strategy": "确认跌破后下一根开盘做空；止损在扫高后防御位外，目标指向下方流动性或 ATR 目标。",
    },
    "eql_absorption_reversal_long": {
        "name": "杀跌吸收反弹做多",
        "features": "先出现大实体杀跌并扫前低，随后低位窄幅吸收，最后 bullish CHoCH/BOS 突破吸收区上沿，MACD 修复。",
        "strategy": "只做确认后的反弹，不接第一根暴跌；突破吸收区上沿后下一根开盘做多。",
    },
}


def true_range(frame: pd.DataFrame) -> pd.Series:
    high = frame["High"].astype(float)
    low = frame["Low"].astype(float)
    close = frame["Close"].astype(float)
    previous_close = close.shift(1)
    return pd.concat([high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1).max(axis=1)


def prepare_features(bars: pd.DataFrame) -> pd.DataFrame:
    features = bars.copy()
    features["trade_date"] = features["ts"].dt.date
    features["minute_of_day"] = features["ts"].dt.hour * 60 + features["ts"].dt.minute
    return features.reset_index(drop=True)


def load_nq_bars(args: argparse.Namespace) -> pd.DataFrame:
    source = BAR_CSV_PATH if BAR_CSV_PATH.exists() else _bar_zip_path()
    source_stat = source.stat()
    cache_path = Path(args.cache)
    cache_key = {
        "loader": "three_trend_csv_v1" if source == BAR_CSV_PATH else "continuous_zip_fallback",
        "source": str(source.resolve()),
        "size": source_stat.st_size,
        "mtime": int(source_stat.st_mtime),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "min_volume": args.min_volume,
    }
    if cache_path.exists():
        cache = pd.read_pickle(cache_path)
        if cache.get("key") == cache_key:
            return cache["features"]

    if source != BAR_CSV_PATH:
        features = load_continuous_nq_bars(args)
        pd.to_pickle({"key": cache_key, "features": features}, cache_path)
        return features

    start_ts = pd.Timestamp(args.start_date, tz="UTC")
    end_ts = pd.Timestamp(args.end_date, tz="UTC")
    start_text = start_ts.strftime("%Y-%m-%d")
    end_text = end_ts.strftime("%Y-%m-%d")
    usecols = ["ts_event", "open", "high", "low", "close", "volume", "symbol"]
    chunks: list[pd.DataFrame] = []
    for chunk in pd.read_csv(source, usecols=usecols, chunksize=args.chunk_size):
        ts_text = chunk["ts_event"].astype(str)
        if not ts_text.empty and ts_text.iloc[0] >= end_text:
            break
        if not ts_text.empty and ts_text.iloc[-1] < start_text:
            continue
        symbols = chunk["symbol"].astype(str)
        chunk = chunk[symbols.map(lambda value: bool(NQ_SYMBOL_RE.match(value)))]
        if chunk.empty:
            continue
        chunk["ts"] = pd.to_datetime(chunk["ts_event"], utc=True)
        chunk = chunk[(chunk["ts"] >= start_ts) & (chunk["ts"] < end_ts)]
        if chunk.empty:
            continue
        for column in ["open", "high", "low", "close", "volume"]:
            chunk[column] = pd.to_numeric(chunk[column], errors="coerce")
        chunk = chunk.dropna(subset=["open", "high", "low", "close", "volume"])
        chunk = chunk[chunk["volume"] >= args.min_volume]
        if not chunk.empty:
            chunks.append(chunk[["ts", "symbol", "open", "high", "low", "close", "volume"]])

    if not chunks:
        raise SystemExit(f"No NQ bar rows found in {source} for {args.start_date}..{args.end_date}")

    bars = pd.concat(chunks, ignore_index=True)
    bars = bars.sort_values(["ts", "volume"], ascending=[True, False]).drop_duplicates("ts", keep="first")
    bars = bars.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    bars = bars.sort_values("ts").reset_index(drop=True)
    features = prepare_features(bars)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle({"key": cache_key, "features": features}, cache_path)
    return features


def add_indicators(frame: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    out = frame.copy()
    close = out["Close"].astype(float)
    high = out["High"].astype(float)
    low = out["Low"].astype(float)
    fast = close.ewm(span=config.macd_fast, adjust=False, min_periods=config.macd_fast).mean()
    slow = close.ewm(span=config.macd_slow, adjust=False, min_periods=config.macd_slow).mean()
    out["macd"] = fast - slow
    out["macd_signal"] = out["macd"].ewm(span=config.macd_signal, adjust=False, min_periods=config.macd_signal).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    out["atr_30"] = true_range(out).rolling(30, min_periods=10).mean()
    out["atr_120"] = true_range(out).rolling(120, min_periods=30).mean()
    out["range_points"] = out["High"].astype(float) - out["Low"].astype(float)
    out["body_points"] = (out["Close"].astype(float) - out["Open"].astype(float)).abs()
    out["body_share"] = out["body_points"] / out["range_points"].replace(0, np.nan)
    out["volume_z_60"] = (
        out["Volume"].astype(float) - out["Volume"].astype(float).rolling(60, min_periods=20).mean()
    ) / out["Volume"].astype(float).rolling(60, min_periods=20).std().replace(0, np.nan)
    internal_high = high.rolling(20, min_periods=20).max().shift(1)
    internal_low = low.rolling(20, min_periods=20).min().shift(1)
    swing_high = high.rolling(80, min_periods=80).max().shift(1)
    swing_low = low.rolling(80, min_periods=80).min().shift(1)
    out["internal_bos"] = np.select([close > internal_high, close < internal_low], [BULLISH, BEARISH], default=0).astype(np.int8)
    out["internal_choch"] = np.select(
        [
            (close > internal_high) & (close.shift(config.trend_lookback) > close.shift(1)),
            (close < internal_low) & (close.shift(config.trend_lookback) < close.shift(1)),
        ],
        [BULLISH, BEARISH],
        default=0,
    ).astype(np.int8)
    out["swing_bos"] = np.select([close > swing_high, close < swing_low], [BULLISH, BEARISH], default=0).astype(np.int8)
    out["swing_choch"] = np.select(
        [
            (close > swing_high) & (close.shift(120) > close.shift(1)),
            (close < swing_low) & (close.shift(120) < close.shift(1)),
        ],
        [BULLISH, BEARISH],
        default=0,
    ).astype(np.int8)
    structure_top = high.rolling(240, min_periods=120).max().shift(1)
    structure_bottom = low.rolling(240, min_periods=120).min().shift(1)
    premium_floor = 0.95 * structure_top + 0.05 * structure_bottom
    discount_ceiling = 0.05 * structure_top + 0.95 * structure_bottom
    out["premium_discount_reversal"] = np.select(
        [close >= premium_floor, close <= discount_ceiling],
        [BEARISH, BULLISH],
        default=0,
    ).astype(np.int8)
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
    raise ValueError(f"unknown session: {session}")


def rolling_recent(mask: pd.Series, bars: int) -> pd.Series:
    return mask.rolling(bars, min_periods=1).max().shift(1).fillna(False).astype(bool)


def build_three_trend_signals(frame: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    out = add_indicators(frame, config)
    high = out["High"].astype(float)
    low = out["Low"].astype(float)
    close = out["Close"].astype(float)
    open_price = out["Open"].astype(float)
    atr = out["atr_30"].astype(float)
    atr_120 = out["atr_120"].astype(float)
    macd_hist = out["macd_hist"].astype(float)

    prior_high = high.rolling(config.sweep_lookback, min_periods=config.sweep_lookback).max().shift(1)
    prior_low = low.rolling(config.sweep_lookback, min_periods=config.sweep_lookback).min().shift(1)
    top_sweep = (high > prior_high) & (close < prior_high)
    bottom_sweep = (low < prior_low) & (close > prior_low)

    range_high = high.rolling(config.range_lookback, min_periods=config.range_lookback).max().shift(1)
    range_low = low.rolling(config.range_lookback, min_periods=config.range_lookback).min().shift(1)
    range_width = range_high - range_low
    compression = (
        (out["range_points"].rolling(config.compression_lookback, min_periods=20).mean() < 0.72 * atr_120)
        & (range_width < 3.2 * atr)
        & (out["volume_z_60"].abs() < 1.4)
    )
    recent_compression = compression.rolling(config.compression_confirm_bars, min_periods=1).max().shift(1).fillna(False).astype(bool)
    range_break_up = close > (range_high + config.range_break_buffer_atr * atr)
    range_break_down = close < (range_low - config.range_break_buffer_atr * atr)

    internal_bull = (out["internal_choch"].astype(int) == BULLISH) | (out["internal_bos"].astype(int) == BULLISH)
    internal_bear = (out["internal_choch"].astype(int) == BEARISH) | (out["internal_bos"].astype(int) == BEARISH)
    swing_bull = (out["swing_bos"].astype(int) == BULLISH) | (out["swing_choch"].astype(int) == BULLISH)
    swing_bear = (out["swing_bos"].astype(int) == BEARISH) | (out["swing_choch"].astype(int) == BEARISH)
    pd_signal = out["premium_discount_reversal"].astype(int)

    shock_down = (
        ((open_price - close) > config.shock_atr_mult * atr)
        & (out["body_share"] >= config.shock_body_share)
        & (out["volume_z_60"] > 0.5)
    )
    recent_shock_down = rolling_recent(shock_down, config.absorption_recent_bars)
    recent_bottom_sweep = rolling_recent(bottom_sweep, config.sweep_recent_bars)
    recent_top_sweep = rolling_recent(top_sweep, config.sweep_recent_bars)
    recent_bear_zone = rolling_recent(pd_signal == BEARISH, config.range_recent_bars)

    low_absorption = (
        (out["range_points"].rolling(config.absorption_recent_bars, min_periods=10).mean() < 0.85 * atr_120)
        & (close <= close.rolling(180, min_periods=60).quantile(0.25).shift(1))
    )
    recent_low_absorption = low_absorption.rolling(config.absorption_recent_bars, min_periods=1).max().shift(1).fillna(False).astype(bool)

    compression_breakout_long = (
        recent_compression
        & range_break_up
        & (internal_bull | swing_bull)
        & (macd_hist > 0)
        & (macd_hist > macd_hist.shift(1))
    )
    eqh_distribution_short = (
        recent_top_sweep
        & recent_bear_zone
        & internal_bear
        & range_break_down
        & (close - close.shift(config.trend_lookback) < 0)
        & (macd_hist < macd_hist.shift(1))
    )
    eql_absorption_reversal_long = (
        recent_shock_down
        & recent_bottom_sweep
        & recent_low_absorption
        & range_break_up
        & internal_bull
        & (out["macd"] > out["macd_signal"])
    )

    if config.variant in {"optimized_v1", "optimized_v2"}:
        ema_60 = close.ewm(span=60, adjust=False, min_periods=60).mean()
        ema_240 = close.ewm(span=240, adjust=False, min_periods=240).mean()
        momentum_60 = close - close.shift(60)
        momentum_240 = close - close.shift(240)
        compression_breakout_long = compression_breakout_long & (close > ema_240)
        eqh_distribution_short = (
            eqh_distribution_short
            & (close < ema_60)
            & (close < ema_240)
            & (momentum_60 < 0)
            & (momentum_240 < 0)
        )
        eql_absorption_reversal_long = pd.Series(False, index=out.index)
        if config.variant == "optimized_v2":
            allowed_hour = ~out["ts"].dt.hour.isin([14, 15, 17, 19, 20])
            compression_breakout_long = compression_breakout_long & allowed_hour
            eqh_distribution_short = eqh_distribution_short & allowed_hour
    elif config.variant != "base":
        raise ValueError(f"unknown strategy variant: {config.variant}")

    out["setup"] = np.select(
        [compression_breakout_long, eqh_distribution_short, eql_absorption_reversal_long],
        ["compression_breakout_long", "eqh_distribution_short", "eql_absorption_reversal_long"],
        default="",
    )
    out["direction"] = np.select(
        [compression_breakout_long, eqh_distribution_short, eql_absorption_reversal_long],
        [BULLISH, BEARISH, BULLISH],
        default=0,
    ).astype(np.int8)
    out["range_high_signal"] = range_high
    out["range_low_signal"] = range_low
    out.loc[~session_mask(out, config.session), ["setup", "direction"]] = ["", 0]
    duplicate = (out["setup"] == out["setup"].shift(1)) & (out["setup"] != "")
    out.loc[duplicate, ["setup", "direction"]] = ["", 0]
    return out


def backtest(frame: pd.DataFrame, config: StrategyConfig, costs: BacktestCosts) -> pd.DataFrame:
    signal_indexes = np.flatnonzero(frame["direction"].to_numpy(dtype=np.int8) != 0)
    if len(signal_indexes) == 0:
        return pd.DataFrame()

    open_prices = frame["Open"].to_numpy(dtype=float)
    high_prices = frame["High"].to_numpy(dtype=float)
    low_prices = frame["Low"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    atr = frame["atr_30"].to_numpy(dtype=float)
    timestamps = frame["ts"].to_numpy()
    symbols = frame["symbol"].astype(str).to_numpy()
    setups = frame["setup"].astype(str).to_numpy()
    range_high = frame["range_high_signal"].to_numpy(dtype=float)
    range_low = frame["range_low_signal"].to_numpy(dtype=float)

    rows: list[dict[str, Any]] = []
    next_available_index = 0
    for signal_index in signal_indexes:
        entry_index = int(signal_index) + 1
        if entry_index <= next_available_index or entry_index >= len(frame):
            continue
        direction = int(frame["direction"].iat[signal_index])
        entry_price = float(open_prices[entry_index])
        if not np.isfinite(entry_price):
            continue
        atr_stop = float(atr[signal_index]) * config.stop_atr_mult if np.isfinite(atr[signal_index]) else config.min_stop_points
        stop_distance = min(max(config.min_stop_points, atr_stop), config.max_stop_points)
        target_distance = max(config.min_target_points, float(atr[signal_index]) * config.target_atr_mult if np.isfinite(atr[signal_index]) else config.min_target_points)
        stop_price = entry_price - stop_distance if direction > 0 else entry_price + stop_distance
        target_price = entry_price + target_distance if direction > 0 else entry_price - target_distance
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
            if direction > 0:
                stop_hit = low_prices[path_index] <= stop_price
                target_hit = high_prices[path_index] >= target_price
            else:
                stop_hit = high_prices[path_index] >= stop_price
                target_hit = low_prices[path_index] <= target_price
            if stop_hit:
                exit_index = path_index
                exit_price = float(stop_price)
                exit_reason = "stop_loss"
                break
            if target_hit:
                exit_index = path_index
                exit_price = float(target_price)
                exit_reason = "take_profit"
                break

        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points
        rows.append(
            {
                "signal_ts": timestamps[signal_index],
                "entry_ts": timestamps[entry_index],
                "exit_ts": timestamps[exit_index],
                "symbol": symbols[signal_index],
                "setup": setups[signal_index],
                "direction": direction,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "stop_price": float(stop_price),
                "target_price": float(target_price),
                "exit_reason": exit_reason,
                "gross_points": float(gross_points),
                "net_points": float(net_points),
                "net_dollars": float(net_points * costs.point_value),
                "entry_index": int(entry_index),
                "exit_index": int(exit_index),
                "signal_index": int(signal_index),
                "signal_range_high": float(range_high[signal_index]) if np.isfinite(range_high[signal_index]) else np.nan,
                "signal_range_low": float(range_low[signal_index]) if np.isfinite(range_low[signal_index]) else np.nan,
            }
        )
        next_available_index = exit_index + 1
    return pd.DataFrame(rows)


def summarize_trades(trades: pd.DataFrame, costs: BacktestCosts) -> dict[str, Any]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "net_dollars": 0.0,
            "gross_points": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_points": 0.0,
            "median_points": 0.0,
            "max_drawdown_points": 0.0,
            "best_trade_points": 0.0,
            "worst_trade_points": 0.0,
            "take_profit_rate": 0.0,
            "stop_loss_rate": 0.0,
        }
    net = trades["net_points"].astype(float)
    gross = trades["gross_points"].astype(float)
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    wins = net[net > 0].sum()
    losses = abs(net[net < 0].sum())
    return {
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "net_dollars": float(net.sum() * costs.point_value),
        "gross_points": float(gross.sum()),
        "win_rate": float((net > 0).mean()),
        "profit_factor": float(wins / losses) if losses else 999.0,
        "avg_points": float(net.mean()),
        "median_points": float(net.median()),
        "max_drawdown_points": float(abs(drawdown.min())),
        "best_trade_points": float(net.max()),
        "worst_trade_points": float(net.min()),
        "take_profit_rate": float((trades["exit_reason"] == "take_profit").mean()),
        "stop_loss_rate": float((trades["exit_reason"] == "stop_loss").mean()),
    }


def grouped_summary(trades: pd.DataFrame, costs: BacktestCosts, group_column: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows = []
    for key, group in trades.groupby(group_column, sort=True):
        rows.append({group_column: key, **summarize_trades(group, costs)})
    return pd.DataFrame(rows)


def cost_stress(trades: pd.DataFrame, costs: BacktestCosts) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows = []
    gross = trades["gross_points"].astype(float)
    for multiplier in [1.0, 2.0, 3.0]:
        net = gross - costs.round_trip_cost_points * multiplier
        wins = net[net > 0].sum()
        losses = abs(net[net < 0].sum())
        rows.append(
            {
                "cost_multiplier": multiplier,
                "net_points": float(net.sum()),
                "profit_factor": float(wins / losses) if losses else 999.0,
                "avg_points": float(net.mean()),
            }
        )
    return pd.DataFrame(rows)


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(float(value)):
            return "N/A"
        return f"{float(value):,.{digits}f}"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    return html.escape(str(value))


def pct(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if not np.isfinite(number):
        return "N/A"
    return f"{number:.2%}"


def table_html(frame: pd.DataFrame, columns: list[str], percent_columns: set[str] | None = None) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    percent_columns = percent_columns or set()
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    rows = []
    for _, row in frame[columns].iterrows():
        cells = []
        for column in columns:
            value = row[column]
            rendered = pct(value) if column in percent_columns else fmt(value, 3 if isinstance(value, float) else 2)
            cells.append(f"<td>{rendered}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def setup_name(setup: str) -> str:
    return SETUP_DESCRIPTIONS.get(setup, {}).get("name", setup)


def make_trade_chart(frame: pd.DataFrame, trade: pd.Series, title: str) -> str:
    entry_index = int(trade["entry_index"])
    exit_index = int(trade["exit_index"])
    signal_index = int(trade["signal_index"])
    start = max(0, entry_index - 100)
    end = min(len(frame), exit_index + 100)
    data = frame.iloc[start:end].copy()
    direction = int(trade["direction"])
    entry_ts = pd.to_datetime(trade["entry_ts"], utc=True)
    exit_ts = pd.to_datetime(trade["exit_ts"], utc=True)

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
    fig.add_trace(
        go.Bar(
            x=data["ts"],
            y=data["macd_hist"],
            name="MACD hist",
            marker_color=np.where(data["macd_hist"] >= 0, "#14b8a6", "#ef4444"),
        ),
        row=2,
        col=1,
    )
    fig.add_trace(go.Scatter(x=data["ts"], y=data["macd"], name="MACD", line={"color": "#22c55e", "width": 2}), row=2, col=1)
    fig.add_trace(go.Scatter(x=data["ts"], y=data["macd_signal"], name="Signal", line={"color": "#eab308", "width": 1.5}), row=2, col=1)
    fig.add_trace(
        go.Scatter(
            x=[entry_ts],
            y=[trade["entry_price"]],
            mode="markers+text",
            marker={"size": 15, "color": "#22c55e" if direction > 0 else "#ef4444", "symbol": "triangle-up" if direction > 0 else "triangle-down"},
            text=["ENTRY"],
            textposition="top center",
            name="Entry",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=[exit_ts],
            y=[trade["exit_price"]],
            mode="markers+text",
            marker={"size": 14, "color": "#38bdf8", "symbol": "x"},
            text=["EXIT"],
            textposition="bottom center",
            name="Exit",
        ),
        row=1,
        col=1,
    )
    if np.isfinite(float(trade.get("signal_range_high", np.nan))) and np.isfinite(float(trade.get("signal_range_low", np.nan))):
        signal_ts = pd.to_datetime(frame["ts"].iat[signal_index], utc=True)
        fig.add_shape(
            type="rect",
            x0=data["ts"].iloc[0],
            x1=signal_ts,
            y0=float(trade["signal_range_low"]),
            y1=float(trade["signal_range_high"]),
            line={"color": "#f59e0b", "width": 1, "dash": "dot"},
            fillcolor="rgba(245, 158, 11, 0.08)",
            row=1,
            col=1,
        )
    fig.add_hline(y=float(trade["stop_price"]), line_dash="dot", line_color="#ef4444", annotation_text="Stop", row=1, col=1)
    fig.add_hline(y=float(trade["target_price"]), line_dash="dot", line_color="#22c55e", annotation_text="Target", row=1, col=1)
    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=660,
        margin={"l": 40, "r": 20, "t": 70, "b": 40},
        xaxis_rangeslider_visible=False,
        legend={"orientation": "h", "y": 1.02},
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def build_report(
    frame: pd.DataFrame,
    trades: pd.DataFrame,
    summary: dict[str, Any],
    by_setup: pd.DataFrame,
    by_year: pd.DataFrame,
    stress: pd.DataFrame,
    charts: list[str],
    config: StrategyConfig,
    costs: BacktestCosts,
    args: argparse.Namespace,
) -> str:
    setup_rows = by_setup.copy()
    if not setup_rows.empty:
        setup_rows["setup_name"] = setup_rows["setup"].map(setup_name)
        setup_rows = setup_rows[["setup_name", "setup", "trades", "net_points", "win_rate", "profit_factor", "avg_points", "max_drawdown_points", "take_profit_rate", "stop_loss_rate"]]
    year_rows = by_year.copy()
    trade_rows = trades.copy()
    if not trade_rows.empty:
        trade_rows["entry_ts"] = pd.to_datetime(trade_rows["entry_ts"], utc=True).astype(str)
        trade_rows["exit_ts"] = pd.to_datetime(trade_rows["exit_ts"], utc=True).astype(str)
        trade_rows["setup_name"] = trade_rows["setup"].map(setup_name)
        trade_rows["side"] = np.where(trade_rows["direction"] > 0, "LONG", "SHORT")
        selected = pd.concat([trade_rows.nlargest(3, "net_points"), trade_rows.nsmallest(3, "net_points")], ignore_index=True)
    else:
        selected = pd.DataFrame()

    cards = "".join(
        f"<div class='card'><span>{label}</span><strong>{value}</strong></div>"
        for label, value in [
            ("交易次数", fmt(summary["trades"], 0)),
            ("净点数", fmt(summary["net_points"], 2)),
            ("净美元(NQ)", fmt(summary["net_dollars"], 2)),
            ("胜率", pct(summary["win_rate"])),
            ("Profit Factor", fmt(summary["profit_factor"], 3)),
            ("最大回撤", fmt(summary["max_drawdown_points"], 2)),
            ("平均每笔", fmt(summary["avg_points"], 3)),
            ("止盈/止损率", f"{pct(summary['take_profit_rate'])} / {pct(summary['stop_loss_rate'])}"),
        ]
    )
    setup_sections = "".join(
        f"""
        <div class="setup">
          <h3>{html.escape(data["name"])}</h3>
          <p><strong>行情特征：</strong>{html.escape(data["features"])}</p>
          <p><strong>交易策略：</strong>{html.escape(data["strategy"])}</p>
        </div>
        """
        for data in SETUP_DESCRIPTIONS.values()
    )
    chart_html = "\n".join(f"<section class='chart'>{chart}</section>" for chart in charts)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>NQ 三段趋势 Lightglow/ICT 量化回测</title>
  <style>
    body {{ margin: 0; background: #08111f; color: #e8eef8; font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width: 1220px; margin: 0 auto; padding: 34px 24px 70px; }}
    h1 {{ margin: 0 0 8px; font-size: 34px; letter-spacing: -0.03em; }}
    h2 {{ margin-top: 34px; border-bottom: 1px solid #27364f; padding-bottom: 8px; }}
    h3 {{ margin-bottom: 8px; color: #f8fafc; }}
    p, li {{ color: #b8c5d8; line-height: 1.65; }}
    code {{ color: #93c5fd; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 24px 0; }}
    .card {{ background: linear-gradient(145deg, #101a2c, #15243b); border: 1px solid #2a3a55; border-radius: 14px; padding: 16px; }}
    .card span {{ display: block; color: #8ea0bb; font-size: 13px; }}
    .card strong {{ display: block; margin-top: 8px; font-size: 23px; }}
    .setup {{ background: #0f1b2e; border: 1px solid #2a3a55; border-radius: 14px; padding: 14px 18px; margin: 12px 0; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; font-size: 13px; }}
    th, td {{ border: 1px solid #2a3a55; padding: 8px 10px; text-align: right; }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
    th {{ background: #14223a; color: #dbeafe; }}
    .note {{ background: #0f1b2e; border-left: 4px solid #38bdf8; padding: 12px 16px; border-radius: 8px; }}
    .warn {{ background: #211911; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 8px; }}
    .chart {{ margin-top: 22px; border: 1px solid #2a3a55; border-radius: 14px; overflow: hidden; background: #101827; }}
  </style>
</head>
<body>
<main>
  <h1>NQ 三段趋势 Lightglow/ICT 量化回测</h1>
  <p>数据源：<code>{html.escape(str(_bar_zip_path()))}</code>。策略版本：<code>{config.variant}</code>。参数区间：<code>{args.start_date}</code> 到 <code>{args.end_date}</code>；实际加载：<code>{frame['ts'].min()}</code> 到 <code>{frame['ts'].max()}</code>，共 <code>{len(frame):,}</code> 根 1 分钟 K 线。</p>
  <div class="cards">{cards}</div>

  <h2>三类行情特征与策略</h2>
  {setup_sections}
  <div class="warn">因果约束：BOS/CHoCH 使用 rolling 高低点突破作为 Lightglow 结构代理，箱体、扫流动性、压缩/吸收条件都只使用当前或历史 1m K 线；入场统一延迟到信号后下一根开盘；不使用未来日内高低点或 TradingView lookahead。</div>
  <div class="note">优化说明：<code>optimized_v1</code> 在 base 规则上增加趋势过滤：突破做多要求价格在 EMA240 上方；扫高做空要求价格低于 EMA60/EMA240 且 60/240 分钟动量均向下；暂时禁用历史表现差的杀跌吸收反弹做多。<code>optimized_v2</code> 额外禁用历史拖累明显的 UTC 14/15/17/19/20 入场小时。</div>

  <h2>按策略分组结果</h2>
  {table_html(setup_rows, list(setup_rows.columns), {"win_rate", "take_profit_rate", "stop_loss_rate"}) if not setup_rows.empty else "<p>No setup rows.</p>"}

  <h2>年度结果</h2>
  {table_html(year_rows, ["year", "trades", "net_points", "net_dollars", "win_rate", "profit_factor", "avg_points", "max_drawdown_points"], {"win_rate"}) if not year_rows.empty else "<p>No yearly rows.</p>"}

  <h2>成本压力</h2>
  {table_html(stress, ["cost_multiplier", "net_points", "profit_factor", "avg_points"]) if not stress.empty else "<p>No stress rows.</p>"}

  <h2>最佳/最差交易</h2>
  <p>下表列出净点数最高 3 笔和最低 3 笔。K 线图展示最佳和最差各 2 笔；黄色区域是信号前近端箱体，绿色/红色虚线是目标/止损。</p>
  {table_html(selected, ["entry_ts", "exit_ts", "setup_name", "side", "entry_price", "exit_price", "net_points", "exit_reason"]) if not selected.empty else "<p>No trades.</p>"}
  {chart_html}

  <h2>如何优化</h2>
  <ul>
    <li>对三类 setup 分开优化，不要混用参数：突破类优先调压缩阈值和回踩确认；扫高做空优先调 premium/eqh sweep 与跌破确认；吸收反弹优先调 shock 后横盘时间和 MACD 修复条件。</li>
    <li>加入 walk-forward：例如 2010-2019 训练参数，2020-2026 只做 OOS 验证；避免用全样本挑最优参数。</li>
    <li>加入时段/波动过滤：NQ 在 US RTH、US late、欧洲盘表现可能完全不同，应分别统计后决定是否禁用弱时段。</li>
    <li>把 ATR 固定止盈止损升级为结构止损：突破类用箱体另一侧，扫高/扫低类用 sweep 极值外侧，反弹类用吸收区下沿。</li>
    <li>做成本压力和滑点压力：若 2x/3x 成本后 PF 接近 1 或转负，不应实盘化。</li>
  </ul>
</main>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest three screenshot-derived Lightglow/ICT NQ 1m setups.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-three-trend-lightglow-ict-cache.pkl")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--report", default="reports/NQ-three-trend-lightglow-ict-backtest.html")
    parser.add_argument("--trades-output", default="reports/NQ-three-trend-lightglow-ict-trades.csv")
    parser.add_argument("--variant", choices=["base", "optimized_v1", "optimized_v2"], default="base")
    args = parser.parse_args()

    config = StrategyConfig(variant=args.variant)
    costs = BacktestCosts()
    frame = load_nq_bars(args)
    frame = build_three_trend_signals(frame, config)
    trades = backtest(frame, config, costs)
    summary = summarize_trades(trades, costs)
    by_setup = grouped_summary(trades, costs, "setup")
    by_year = grouped_summary(
        trades.assign(year=pd.to_datetime(trades["entry_ts"], utc=True).dt.year) if not trades.empty else trades,
        costs,
        "year",
    )
    stress = cost_stress(trades, costs)

    trades_path = Path(args.trades_output)
    trades_path.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(trades_path, index=False)

    chart_trades = []
    if not trades.empty:
        chart_trades.extend(list(trades.sort_values("net_points", ascending=False).head(2).iterrows()))
        chart_trades.extend(list(trades.sort_values("net_points", ascending=True).head(2).iterrows()))
    charts = []
    for index, (_, row) in enumerate(chart_trades, start=1):
        label = "Best" if row["net_points"] >= 0 else "Worst"
        charts.append(make_trade_chart(frame, row, f"{label} Trade #{index}: {setup_name(row['setup'])}, {row['net_points']:.2f} pts"))

    report = build_report(frame, trades, summary, by_setup, by_year, stress, charts, config, costs, args)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"wrote {report_path}")
    print(f"wrote {trades_path}")
    print(summary)
    if not by_setup.empty:
        print(by_setup.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
