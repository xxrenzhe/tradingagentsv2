from __future__ import annotations

import numpy as np
import pandas as pd


BULLISH = 1
BEARISH = -1


def prepare_evolution_features(bars: pd.DataFrame) -> pd.DataFrame:
    data = bars.copy()
    if "ts" not in data.columns:
        if "Date" in data.columns:
            data["ts"] = pd.to_datetime(data["Date"], utc=True)
        elif "ts_event" in data.columns:
            data["ts"] = pd.to_datetime(data["ts_event"], utc=True)
        else:
            raise ValueError("bars must include ts, Date, or ts_event")

    data["ts"] = pd.to_datetime(data["ts"], utc=True)
    rename = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    data = data.rename(columns={key: value for key, value in rename.items() if key in data.columns})
    if "symbol" not in data.columns:
        data["symbol"] = "NQ"
    data = data.sort_values("ts").drop_duplicates("ts").reset_index(drop=True)

    for column in ["Open", "High", "Low", "Close", "Volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["Open", "High", "Low", "Close"]).reset_index(drop=True)

    high = data["High"]
    low = data["Low"]
    close = data["Close"]
    open_ = data["Open"]
    volume = data["Volume"].fillna(0)

    data["trade_date"] = data["ts"].dt.date.astype(str)
    data["minute_of_day"] = data["ts"].dt.hour * 60 + data["ts"].dt.minute
    data["return_1m"] = close.pct_change()
    data["return_5m"] = close.pct_change(5)
    data["return_15m"] = close.pct_change(15)
    data["return_60m"] = close.pct_change(60)
    data["range_points"] = high - low
    data["body_points"] = (close - open_).abs()
    data["body_share"] = data["body_points"] / data["range_points"].replace(0, np.nan)
    data["upper_wick_points"] = high - np.maximum(open_, close)
    data["lower_wick_points"] = np.minimum(open_, close) - low

    data["ema_10"] = close.ewm(span=10, adjust=False).mean()
    data["ema_20"] = close.ewm(span=20, adjust=False).mean()
    data["ema_50"] = close.ewm(span=50, adjust=False).mean()
    data["ema_10_slope"] = data["ema_10"].diff(5)
    data["ema_20_slope"] = data["ema_20"].diff(10)
    cumulative_volume = volume.replace(0, np.nan).cumsum()
    data["vwap"] = (close * volume).cumsum() / cumulative_volume
    data["vwap_distance"] = close - data["vwap"]
    data["vwap_distance_z"] = _zscore(data["vwap_distance"], 30)
    data["signed_volume"] = volume * np.sign(close.diff().fillna(0))
    data["obv"] = data["signed_volume"].cumsum()
    data["obv_slope_20"] = data["obv"].diff(20)
    data["volume_ma_20"] = volume.rolling(20, min_periods=5).mean()
    data["relative_volume_20"] = volume / data["volume_ma_20"].replace(0, np.nan)
    money_flow_multiplier = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
    data["cmf_20"] = (money_flow_multiplier.fillna(0) * volume).rolling(20, min_periods=10).sum() / volume.rolling(20, min_periods=10).sum().replace(0, np.nan)
    typical_price = (high + low + close) / 3
    raw_money_flow = typical_price * volume
    positive_flow = raw_money_flow.where(typical_price > typical_price.shift(1), 0.0)
    negative_flow = raw_money_flow.where(typical_price < typical_price.shift(1), 0.0)
    money_ratio = positive_flow.rolling(14, min_periods=7).sum() / negative_flow.rolling(14, min_periods=7).sum().replace(0, np.nan)
    data["mfi_14"] = 100 - (100 / (1 + money_ratio))
    data["price_volume_corr_20"] = data["return_1m"].rolling(20, min_periods=10).corr(volume.pct_change())
    data["volume_price_trend"] = (volume * close.pct_change().fillna(0)).cumsum()
    data["volume_price_trend_slope_20"] = data["volume_price_trend"].diff(20)
    data["bullish_volume_divergence"] = ((close < close.shift(20)) & (data["obv"] > data["obv"].shift(20))).astype(int)
    data["bearish_volume_divergence"] = ((close > close.shift(20)) & (data["obv"] < data["obv"].shift(20))).astype(int)

    true_range = _true_range(high, low, close)
    data["atr_14"] = true_range.rolling(14, min_periods=5).mean()
    data["atr_30"] = true_range.rolling(30, min_periods=10).mean()
    data["atr_120"] = true_range.rolling(120, min_periods=30).mean()
    data["volume_breakout_signal"] = ((data["relative_volume_20"] >= 1.8) & (data["range_points"] >= data["atr_30"].fillna(data["range_points"]))).astype(int)
    data["low_volume_pullback"] = ((data["relative_volume_20"] <= 0.75) & (data["range_points"] <= data["atr_30"].fillna(data["range_points"]))).astype(int)
    data["vol_30"] = data["return_1m"].rolling(30, min_periods=10).std()
    data["vol_120"] = data["return_1m"].rolling(120, min_periods=30).std()
    data["z_30"] = _zscore(close, 30)
    data["volume_z_60"] = _zscore(volume, 60)
    data["rsi_14"] = _rsi(close, 14)
    middle = close.rolling(20, min_periods=10).mean()
    std = close.rolling(20, min_periods=10).std()
    data["boll_position"] = (close - middle) / (2 * std).replace(0, np.nan)

    data = _add_candlestick_features(data)
    data = _add_lightglow_ict_features(data)
    data = _add_regime_features(data)
    return data.reset_index(drop=True)


def summarize_segment_features(frame: pd.DataFrame) -> dict[str, object]:
    if frame.empty:
        return {}
    numeric_columns = [
        "return_1m",
        "return_15m",
        "return_60m",
        "range_points",
        "body_points",
        "body_share",
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
        "vwap_distance_z",
        "rsi_14",
        "boll_position",
    ]
    summary: dict[str, object] = {
        "start_ts": str(frame["ts"].iloc[0]),
        "end_ts": str(frame["ts"].iloc[-1]),
        "bars": int(len(frame)),
        "open": float(frame["Open"].iloc[0]),
        "close": float(frame["Close"].iloc[-1]),
        "high": float(frame["High"].max()),
        "low": float(frame["Low"].min()),
        "net_points": float(frame["Close"].iloc[-1] - frame["Open"].iloc[0]),
        "volume": float(pd.to_numeric(frame["Volume"], errors="coerce").fillna(0).sum()),
        "regime": str(frame["regime"].mode().iloc[0]) if "regime" in frame and not frame["regime"].mode().empty else "unknown",
    }
    for column in numeric_columns:
        if column in frame:
            values = pd.to_numeric(frame[column], errors="coerce").dropna()
            if not values.empty:
                summary[f"{column}_mean"] = float(values.mean())
                summary[f"{column}_last"] = float(values.iloc[-1])
    for column in [
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
        "sweep_signal",
        "choch_signal",
        "bos_signal",
        "fvg_signal",
    ]:
        if column in frame:
            summary[f"{column}_count"] = int((pd.to_numeric(frame[column], errors="coerce").fillna(0) != 0).sum())
    if "pd_zone" in frame:
        summary["pd_zone_last"] = str(frame["pd_zone"].iloc[-1])
    return summary


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    previous_close = close.shift(1)
    ranges = pd.concat([high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1)
    return ranges.max(axis=1)


def _zscore(values: pd.Series, lookback: int) -> pd.Series:
    mean = values.rolling(lookback, min_periods=max(3, lookback // 3)).mean()
    std = values.rolling(lookback, min_periods=max(3, lookback // 3)).std().replace(0, np.nan)
    return (values - mean) / std


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period // 2).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period // 2).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _add_candlestick_features(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    body = frame["body_points"]
    range_points = frame["range_points"].replace(0, np.nan)
    frame["doji"] = (body / range_points <= 0.1).fillna(False).astype(int)
    frame["pin_bar"] = (
        ((frame["upper_wick_points"] >= 2.0 * body) | (frame["lower_wick_points"] >= 2.0 * body))
        & (body / range_points <= 0.45)
    ).fillna(False).astype(int)
    bullish_engulf = (
        (frame["Close"] > frame["Open"])
        & (frame["Close"].shift(1) < frame["Open"].shift(1))
        & (frame["Close"] >= frame["Open"].shift(1))
        & (frame["Open"] <= frame["Close"].shift(1))
    )
    bearish_engulf = (
        (frame["Close"] < frame["Open"])
        & (frame["Close"].shift(1) > frame["Open"].shift(1))
        & (frame["Open"] >= frame["Close"].shift(1))
        & (frame["Close"] <= frame["Open"].shift(1))
    )
    frame["engulfing"] = np.select([bullish_engulf, bearish_engulf], [BULLISH, BEARISH], default=0).astype(np.int8)
    frame["inside_bar"] = ((frame["High"] <= frame["High"].shift(1)) & (frame["Low"] >= frame["Low"].shift(1))).fillna(False).astype(int)
    frame["outside_bar"] = ((frame["High"] >= frame["High"].shift(1)) & (frame["Low"] <= frame["Low"].shift(1))).fillna(False).astype(int)
    frame["displacement_candle"] = (
        (frame["range_points"] >= 1.2 * frame["atr_30"])
        & (frame["body_share"] >= 0.55)
        & (frame["volume_z_60"].fillna(0) >= 0)
    ).fillna(False).astype(int)
    return frame


def _add_lightglow_ict_features(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    high = frame["High"]
    low = frame["Low"]
    close = frame["Close"]
    open_ = frame["Open"]
    pd_lookback = 100
    rolling_high = high.rolling(pd_lookback, min_periods=20).max().shift(1)
    rolling_low = low.rolling(pd_lookback, min_periods=20).min().shift(1)
    rolling_range = (rolling_high - rolling_low).replace(0, np.nan)
    frame["premium_level"] = rolling_low + 0.95 * rolling_range
    frame["discount_level"] = rolling_low + 0.05 * rolling_range
    in_premium = close >= frame["premium_level"]
    in_discount = close <= frame["discount_level"]
    frame["pd_zone"] = np.select([in_premium, in_discount], ["premium", "discount"], default="equilibrium")
    frame["pd_fade_signal"] = np.select([in_discount, in_premium], [BULLISH, BEARISH], default=0).astype(np.int8)
    frame["pd_continue_signal"] = np.select([in_premium, in_discount], [BULLISH, BEARISH], default=0).astype(np.int8)

    prior_high_20 = high.rolling(20, min_periods=10).max().shift(1)
    prior_low_20 = low.rolling(20, min_periods=10).min().shift(1)
    top_sweep = (high > prior_high_20 + 0.25) & (close < prior_high_20)
    bottom_sweep = (low < prior_low_20 - 0.25) & (close > prior_low_20)
    frame["sweep_signal"] = np.select([bottom_sweep, top_sweep], [BULLISH, BEARISH], default=0).astype(np.int8)

    prior_internal_high = high.rolling(20, min_periods=10).max().shift(1)
    prior_internal_low = low.rolling(20, min_periods=10).min().shift(1)
    recent_discount = in_discount.rolling(5, min_periods=1).max().shift(1).fillna(False).astype(bool)
    recent_premium = in_premium.rolling(5, min_periods=1).max().shift(1).fillna(False).astype(bool)
    long_choch = recent_discount & (close > prior_internal_high)
    short_choch = recent_premium & (close < prior_internal_low)
    frame["choch_signal"] = np.select([long_choch, short_choch], [BULLISH, BEARISH], default=0).astype(np.int8)

    prior_high_50 = high.rolling(50, min_periods=20).max().shift(1)
    prior_low_50 = low.rolling(50, min_periods=20).min().shift(1)
    long_bos = (close > prior_high_50) & (frame["displacement_candle"] == 1)
    short_bos = (close < prior_low_50) & (frame["displacement_candle"] == 1)
    frame["bos_signal"] = np.select([long_bos, short_bos], [BULLISH, BEARISH], default=0).astype(np.int8)

    body_share = frame["body_share"]
    bullish_fvg = (
        (low > high.shift(2))
        & (close.shift(1) > high.shift(2))
        & ((close.shift(1) - open_.shift(1)) > 0)
        & (body_share.shift(1) >= 0.55)
    )
    bearish_fvg = (
        (high < low.shift(2))
        & (close.shift(1) < low.shift(2))
        & ((close.shift(1) - open_.shift(1)) < 0)
        & (body_share.shift(1) >= 0.55)
    )
    frame["fvg_signal"] = np.select([bullish_fvg, bearish_fvg], [BULLISH, BEARISH], default=0).astype(np.int8)
    return frame


def _add_regime_features(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    trend_up = (frame["ema_10"] > frame["ema_20"]) & (frame["ema_20"] > frame["ema_50"]) & (frame["ema_20_slope"] > 0)
    trend_down = (frame["ema_10"] < frame["ema_20"]) & (frame["ema_20"] < frame["ema_50"]) & (frame["ema_20_slope"] < 0)
    volatile = (frame["atr_30"] / frame["atr_120"].replace(0, np.nan)) > 1.4
    post_sweep = frame["sweep_signal"].rolling(5, min_periods=1).max().abs() > 0
    post_displacement = frame["displacement_candle"].rolling(5, min_periods=1).max() > 0
    frame["regime"] = np.select(
        [post_sweep, post_displacement, volatile, trend_up, trend_down],
        ["post_sweep_reclaim", "post_displacement", "volatile_range", "trend_up", "trend_down"],
        default="range",
    )
    return frame
