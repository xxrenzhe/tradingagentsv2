from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
BAR_CSV_PATH = ROOT_DIR / "data/raw/databento/glbx-mdp3-20100606-20260427.ohlcv-1m.csv"
FEATURE_CACHE = ROOT_DIR / ".tmp/nq-bar-5y-continuous-features-cache.pkl"
NQ_SYMBOL_RE = re.compile(r"^NQ[HMUZ]\d$")
POINT_VALUE = 20.0
ROUND_TRIP_COST_POINTS = 1.5


@dataclass(frozen=True)
class ComboConfig:
    ba_range_length: int = 90
    ba_momentum_lookback: int = 30
    ba_accept_bars: int = 3
    ba_accept_atr_buffer: float = 0.15
    ba_body_atr_min: float = 0.60
    ba_volume_z_min: float = 0.0
    lg_ob_tf_minutes: int = 15
    lg_hold_bars: int = 45
    lg_pivot_size: int = 5
    br_lookback: int = 30
    br_threshold: float = 0.001
    br_hold_bars: int = 60
    ba_max_hold_bars: int = 35
    ba_stop_atr: float = 1.25
    ba_target_r: float = 2.50
    protective_stop_atr: float = 4.00
    cooldown_bars: int = 5


def load_nq_1m_bars(args: argparse.Namespace) -> pd.DataFrame:
    if args.use_feature_cache and FEATURE_CACHE.exists():
        cached = pd.read_pickle(FEATURE_CACHE)
        frame = cached["features"] if isinstance(cached, dict) and "features" in cached else cached
        bars = frame[["ts", "symbol", "Open", "High", "Low", "Close", "Volume"]].copy()
        bars["ts"] = pd.to_datetime(bars["ts"], utc=True)
        start_ts = pd.Timestamp(args.start_date, tz="UTC")
        end_ts = pd.Timestamp(args.end_date, tz="UTC")
        bars = bars[(bars["ts"] >= start_ts) & (bars["ts"] < end_ts)].copy()
        return bars.sort_values("ts").reset_index(drop=True)

    cache_path = ROOT_DIR / args.cache
    source_stat = BAR_CSV_PATH.stat()
    cache_key = {
        "source": str(BAR_CSV_PATH.resolve()),
        "size": source_stat.st_size,
        "mtime": int(source_stat.st_mtime),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "min_volume": args.min_volume,
    }
    if cache_path.exists():
        cached = pd.read_pickle(cache_path)
        if cached.get("key") == cache_key:
            return cached["bars"].copy()

    start_ts = pd.Timestamp(args.start_date, tz="UTC")
    end_ts = pd.Timestamp(args.end_date, tz="UTC")
    start_text = start_ts.strftime("%Y-%m-%d")
    end_text = end_ts.strftime("%Y-%m-%d")
    usecols = ["ts_event", "open", "high", "low", "close", "volume", "symbol"]
    chunks: list[pd.DataFrame] = []
    for chunk in pd.read_csv(BAR_CSV_PATH, usecols=usecols, chunksize=args.chunk_size):
        ts_text = chunk["ts_event"].astype(str)
        if not ts_text.empty and ts_text.iloc[0] >= end_text:
            break
        if not ts_text.empty and ts_text.iloc[-1] < start_text:
            continue
        chunk = chunk[chunk["symbol"].astype(str).map(lambda value: bool(NQ_SYMBOL_RE.match(value)))]
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
        raise SystemExit("No NQ bars loaded.")
    bars = pd.concat(chunks, ignore_index=True)
    bars = bars.sort_values(["ts", "volume"], ascending=[True, False]).drop_duplicates("ts", keep="first")
    bars = bars.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    bars = bars.sort_values("ts").reset_index(drop=True)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle({"key": cache_key, "bars": bars}, cache_path)
    return bars


def resample_ohlcv(bars: pd.DataFrame, timeframe_minutes: int) -> pd.DataFrame:
    if timeframe_minutes == 1:
        out = bars.copy()
    else:
        out = (
            bars.set_index("ts")
            .resample(f"{timeframe_minutes}min", label="left", closed="left")
            .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum", "symbol": "last"})
            .dropna(subset=["Open", "High", "Low", "Close"])
            .reset_index()
        )
    out["minute_of_day"] = out["ts"].dt.hour * 60 + out["ts"].dt.minute
    out["timeframe_minutes"] = timeframe_minutes
    return out.reset_index(drop=True)


def rma(values: pd.Series, length: int) -> pd.Series:
    return values.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()


def true_range(frame: pd.DataFrame) -> pd.Series:
    high = frame["High"].astype(float)
    low = frame["Low"].astype(float)
    close = frame["Close"].astype(float)
    prev_close = close.shift(1)
    return pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)


def pivot_confirmed(values: pd.Series, left: int, right: int, kind: str) -> pd.Series:
    arr = values.to_numpy(dtype=float)
    out = np.full(len(arr), np.nan)
    for i in range(left + right, len(arr)):
        pivot_index = i - right
        window = arr[pivot_index - left : pivot_index + right + 1]
        pivot = arr[pivot_index]
        if kind == "high" and np.isfinite(pivot) and pivot >= np.nanmax(window):
            out[i] = pivot
        if kind == "low" and np.isfinite(pivot) and pivot <= np.nanmin(window):
            out[i] = pivot
    return pd.Series(out, index=values.index)


def lightglow_15m_signals(frame: pd.DataFrame, config: ComboConfig) -> pd.DataFrame:
    htf = resample_ohlcv(frame[["ts", "symbol", "Open", "High", "Low", "Close", "Volume"]], config.lg_ob_tf_minutes)
    p = config.lg_pivot_size
    htf["pivot_high"] = pivot_confirmed(htf["High"], p, p, "high")
    htf["pivot_low"] = pivot_confirmed(htf["Low"], p, p, "low")
    pivot_high_level = np.nan
    pivot_low_level = np.nan
    high_crossed = True
    low_crossed = True
    bear_block_high = np.nan
    bear_block_low = np.nan
    bull_block_high = np.nan
    bull_block_low = np.nan
    directions: list[int] = []
    highs = htf["High"].to_numpy(dtype=float)
    lows = htf["Low"].to_numpy(dtype=float)
    closes = htf["Close"].to_numpy(dtype=float)
    pivot_highs = htf["pivot_high"].to_numpy(dtype=float)
    pivot_lows = htf["pivot_low"].to_numpy(dtype=float)
    for i in range(len(htf)):
        if np.isfinite(pivot_highs[i]):
            pivot_high_level = float(pivot_highs[i])
            high_crossed = False
        if np.isfinite(pivot_lows[i]):
            pivot_low_level = float(pivot_lows[i])
            low_crossed = False
        close_prev = closes[i - 1] if i > 0 else np.nan
        bull_bos = np.isfinite(pivot_high_level) and not high_crossed and close_prev <= pivot_high_level and closes[i] > pivot_high_level
        bear_bos = np.isfinite(pivot_low_level) and not low_crossed and close_prev >= pivot_low_level and closes[i] < pivot_low_level
        start = max(0, i - p * 2 + 1)
        if bull_bos:
            high_crossed = True
            bull_block_low = float(np.nanmin(lows[start : i + 1]))
            bull_block_high = float(np.nanmax(highs[start : i + 1]))
        if bear_bos:
            low_crossed = True
            bear_block_low = float(np.nanmin(lows[start : i + 1]))
            bear_block_high = float(np.nanmax(highs[start : i + 1]))
        direction = 0
        if np.isfinite(bear_block_high) and highs[i] > bear_block_high:
            direction = 1
            bear_block_high = np.nan
            bear_block_low = np.nan
        elif np.isfinite(bull_block_low) and lows[i] < bull_block_low:
            direction = -1
            bull_block_high = np.nan
            bull_block_low = np.nan
        directions.append(direction)
    htf["lg_direction"] = directions
    return htf[["ts", "lg_direction"]]


def add_signals(frame: pd.DataFrame, config: ComboConfig) -> pd.DataFrame:
    out = frame.copy()
    close = out["Close"].astype(float)
    high = out["High"].astype(float)
    low = out["Low"].astype(float)
    open_ = out["Open"].astype(float)
    volume = out["Volume"].astype(float)
    out["atr"] = rma(true_range(out), 14)
    out["ema20"] = close.ewm(span=20, adjust=False, min_periods=20).mean()
    out["ema60"] = close.ewm(span=60, adjust=False, min_periods=60).mean()
    out["ema200"] = close.ewm(span=200, adjust=False, min_periods=200).mean()
    range_high = high.rolling(config.ba_range_length, min_periods=config.ba_range_length).max().shift(1)
    range_low = low.rolling(config.ba_range_length, min_periods=config.ba_range_length).min().shift(1)
    volume_mean = volume.rolling(60, min_periods=60).mean()
    volume_std = volume.rolling(60, min_periods=60).std(ddof=0).replace(0, np.nan)
    volume_z = ((volume - volume_mean) / volume_std).fillna(0.0)
    momentum = close - close.shift(config.ba_momentum_lookback)
    body_atr = (close - open_).abs() / out["atr"].replace(0, np.nan)
    below_range_low = close < range_low - out["atr"] * config.ba_accept_atr_buffer
    above_range_high = close > range_high + out["atr"] * config.ba_accept_atr_buffer
    accepted_below = below_range_low.astype(int).rolling(config.ba_accept_bars, min_periods=config.ba_accept_bars).sum() >= config.ba_accept_bars
    accepted_above = above_range_high.astype(int).rolling(config.ba_accept_bars, min_periods=config.ba_accept_bars).sum() >= config.ba_accept_bars
    sweep_below = (low < range_low) & (close > range_low)
    sweep_above = (high > range_high) & (close < range_high)
    minute = out["minute_of_day"]
    is_asia = (minute < 420) | (minute >= 1380)
    is_us_late = (minute >= 1200) & (minute < 1380)
    bottom_reclaim_long = sweep_below & (close > open_) & (momentum > momentum.shift(1)) & (body_atr >= config.ba_body_atr_min * 0.5)
    top_breakout_long = accepted_above & (close > open_) & (out["ema20"] > out["ema60"]) & (out["ema60"] >= out["ema200"]) & (momentum > 0) & (volume_z >= config.ba_volume_z_min) & (body_atr >= config.ba_body_atr_min)
    asia_trend_short = is_asia & accepted_below & (close < open_) & (out["ema20"] < out["ema60"]) & (out["ema60"] <= out["ema200"]) & (momentum < 0) & (volume_z >= config.ba_volume_z_min) & (body_atr >= config.ba_body_atr_min)
    ema_bull_transition = (close > out["ema20"]) & (close > out["ema60"]) & (out["ema20"] > out["ema20"].shift(1)) & (close > high.rolling(20, min_periods=20).max().shift(1)) & (momentum > 0) & (body_atr >= config.ba_body_atr_min * 0.65)
    ema_bear_transition = (close < out["ema20"]) & (close < out["ema60"]) & (out["ema20"] < out["ema20"].shift(1)) & (close < low.rolling(20, min_periods=20).min().shift(1)) & (momentum < 0) & (body_atr >= config.ba_body_atr_min * 0.65)
    ba_long = bottom_reclaim_long | top_breakout_long | ema_bull_transition
    ba_short = asia_trend_short | ema_bear_transition | (sweep_above & (close < open_) & (momentum < 0) & (body_atr >= config.ba_body_atr_min * 0.5))
    out["ba_signal"] = np.where(ba_long, 1, np.where(ba_short, -1, 0))
    lg = lightglow_15m_signals(out, config)
    out = out.merge(lg, on="ts", how="left")
    out["lg_direction"] = out["lg_direction"].fillna(0).astype(int)
    br_prior_high = high.rolling(config.br_lookback, min_periods=config.br_lookback).max().shift(2)
    br_prior_low = low.rolling(config.br_lookback, min_periods=config.br_lookback).min().shift(2)
    br_range = br_prior_high - br_prior_low
    br_long_breakout = close.shift(1) > br_prior_high
    br_long_retest = (low <= br_prior_high) & (close > br_prior_high + br_range * config.br_threshold)
    out["breakout_retest_long"] = (is_us_late & br_long_breakout & br_long_retest).fillna(False)
    out["lightglow_signal"] = is_us_late & out["lg_direction"].ne(0)
    out["overlay_signal"] = np.where(
        out["lightglow_signal"] & out["lg_direction"].gt(0) | out["breakout_retest_long"],
        1,
        np.where(out["lightglow_signal"] & out["lg_direction"].lt(0), -1, 0),
    )
    return out


def run_backtest(frame: pd.DataFrame, config: ComboConfig) -> pd.DataFrame:
    data = add_signals(frame, config)
    trades: list[dict[str, object]] = []
    position: dict[str, object] | None = None
    pending: dict[str, object] | None = None
    last_exit_index: int | None = None
    ts = data["ts"].to_numpy()
    timeframe = data["timeframe_minutes"].to_numpy(dtype=int)
    open_prices = data["Open"].to_numpy(dtype=float)
    high_prices = data["High"].to_numpy(dtype=float)
    low_prices = data["Low"].to_numpy(dtype=float)
    close_prices = data["Close"].to_numpy(dtype=float)
    atr_values = data["atr"].to_numpy(dtype=float)
    ba_signals = data["ba_signal"].to_numpy(dtype=int)
    overlay_signals = data["overlay_signal"].to_numpy(dtype=int)
    br_signals = data["breakout_retest_long"].to_numpy(dtype=bool)
    for i in range(1, len(data)):
        if pending is not None:
            position = {
                **pending,
                "entry_index": i,
                "entry_ts": ts[i],
                "entry_price": float(open_prices[i]),
            }
            pending = None
        if position is not None:
            direction = int(position["direction"])
            leg = str(position["leg"])
            bars_held = i - int(position["entry_index"])
            exit_price = np.nan
            exit_reason = ""
            if direction > 0:
                if low_prices[i] <= float(position["stop"]):
                    exit_price = float(position["stop"])
                    exit_reason = "stop"
                elif np.isfinite(float(position["target"])) and high_prices[i] >= float(position["target"]):
                    exit_price = float(position["target"])
                    exit_reason = "target"
            else:
                if high_prices[i] >= float(position["stop"]):
                    exit_price = float(position["stop"])
                    exit_reason = "stop"
                elif np.isfinite(float(position["target"])) and low_prices[i] <= float(position["target"]):
                    exit_price = float(position["target"])
                    exit_reason = "target"
            hold_bars = config.ba_max_hold_bars if leg == "BA" else config.lg_hold_bars if leg == "LG_OB" else config.br_hold_bars
            if not exit_reason and bars_held >= hold_bars:
                exit_price = float(close_prices[i])
                exit_reason = "time_exit"
            if exit_reason:
                gross = (exit_price - float(position["entry_price"])) * direction
                net = gross - ROUND_TRIP_COST_POINTS
                trades.append(
                    {
                        "timeframe_minutes": int(timeframe[i]),
                        "entry_ts": position["entry_ts"],
                        "exit_ts": ts[i],
                        "leg": leg,
                        "direction": direction,
                        "entry_price": float(position["entry_price"]),
                        "exit_price": exit_price,
                        "exit_reason": exit_reason,
                        "bars_held": bars_held,
                        "holding_minutes": bars_held * int(timeframe[i]),
                        "gross_points": gross,
                        "net_points": net,
                        "net_dollars": net * POINT_VALUE,
                        "entry_index": int(position["entry_index"]),
                        "exit_index": i,
                    }
                )
                position = None
                last_exit_index = i
        if position is None and pending is None and i + 1 < len(data):
            cooldown_ok = last_exit_index is None or i - last_exit_index >= config.cooldown_bars
            if not cooldown_ok or not np.isfinite(atr_values[i]):
                continue
            ba_signal = int(ba_signals[i])
            overlay_signal = int(overlay_signals[i]) if ba_signal == 0 else 0
            direction = ba_signal if ba_signal != 0 else overlay_signal
            if direction == 0:
                continue
            leg = "BA" if ba_signal != 0 else "BR" if bool(br_signals[i]) else "LG_OB"
            close = float(close_prices[i])
            atr = float(atr_values[i])
            if leg == "BA":
                stop = close - atr * config.ba_stop_atr if direction > 0 else close + atr * config.ba_stop_atr
                target = close + atr * config.ba_stop_atr * config.ba_target_r if direction > 0 else close - atr * config.ba_stop_atr * config.ba_target_r
            else:
                stop = close - atr * config.protective_stop_atr if direction > 0 else close + atr * config.protective_stop_atr
                target = np.nan
            pending = {"signal_index": i, "signal_ts": ts[i], "direction": direction, "leg": leg, "stop": stop, "target": target}
    return pd.DataFrame(trades)


def summarize(trades: pd.DataFrame) -> dict[str, object]:
    if trades.empty:
        return {"trades": 0, "net_points": 0.0, "profit_factor": 0.0, "win_rate": 0.0, "avg_points": 0.0, "max_drawdown_points": 0.0}
    points = trades["net_points"].astype(float)
    gross_profit = float(points[points > 0].sum())
    gross_loss = float(-points[points < 0].sum())
    equity = points.cumsum()
    drawdown = equity.cummax() - equity
    return {
        "trades": int(len(points)),
        "net_points": float(points.sum()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else float("inf"),
        "win_rate": float(points.gt(0).mean()),
        "avg_points": float(points.mean()),
        "max_drawdown_points": float(drawdown.max()),
        "worst_trade_points": float(points.min()),
        "best_trade_points": float(points.max()),
    }


def period_breakdown(trades: pd.DataFrame, column: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["timeframe_minutes", column, "trades", "net_points"])
    out = trades.copy()
    out["month"] = pd.to_datetime(out["entry_ts"], utc=True).dt.strftime("%Y-%m")
    out["year"] = pd.to_datetime(out["entry_ts"], utc=True).dt.year
    return out.groupby(["timeframe_minutes", column], as_index=False).agg(trades=("net_points", "size"), net_points=("net_points", "sum"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest current Pine BA no-trade combo approximation on 1m and 3m bars.")
    parser.add_argument("--start-date", default="2021-04-28")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--min-volume", type=int, default=1)
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--cache", default=".tmp/nq-ba-no-trade-timeframe-bars-cache.pkl")
    parser.add_argument("--use-feature-cache", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--output-prefix", default="reports/NQ-pine-ba-no-trade-best-combo-timeframe")
    args = parser.parse_args()

    config = ComboConfig()
    base = load_nq_1m_bars(args)
    all_trades: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []
    for timeframe in (1, 3):
        frame = resample_ohlcv(base, timeframe)
        trades = run_backtest(frame, config)
        if not trades.empty:
            trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
            trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
            trades["equity_points"] = trades["net_points"].cumsum()
            trades["drawdown_points"] = trades["equity_points"].cummax() - trades["equity_points"]
            all_trades.append(trades)
        summary_rows.append(
            {
                "timeframe_minutes": timeframe,
                "start_date": args.start_date,
                "end_date": args.end_date,
                "bars": int(len(frame)),
                "actual_ba_max_hold_minutes": config.ba_max_hold_bars * timeframe,
                "actual_lg_hold_minutes": config.lg_hold_bars * timeframe,
                "actual_br_hold_minutes": config.br_hold_bars * timeframe,
                "actual_cooldown_minutes": config.cooldown_bars * timeframe,
                **summarize(trades),
            }
        )
    comparison = pd.DataFrame(summary_rows)
    trades_all = pd.concat(all_trades, ignore_index=True, sort=False) if all_trades else pd.DataFrame()
    prefix = ROOT_DIR / args.output_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(prefix.with_name(f"{prefix.name}-comparison.csv"), index=False)
    trades_all.to_csv(prefix.with_name(f"{prefix.name}-trades.csv"), index=False)
    if not trades_all.empty:
        period_breakdown(trades_all, "month").to_csv(prefix.with_name(f"{prefix.name}-monthly.csv"), index=False)
        period_breakdown(trades_all, "year").to_csv(prefix.with_name(f"{prefix.name}-yearly.csv"), index=False)
    print(json.dumps({"comparison": comparison.to_dict(orient="records"), "trades_path": str(prefix.with_name(f"{prefix.name}-trades.csv").relative_to(ROOT_DIR))}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
