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

    data = _add_tradingview_style_indicators(data)
    data = _add_candlestick_features(data)
    data = _add_lightglow_ict_features(data)
    data = _add_chart_structure_features(data)
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
        "macd_line",
        "macd_signal",
        "macd_hist",
        "adx_14",
        "plus_di_14",
        "minus_di_14",
        "di_spread_14",
        "cci_20",
        "stoch_rsi_k",
        "stoch_rsi_d",
        "donchian_20_position",
        "keltner_position",
        "supertrend_direction",
        "vfi_130",
        "vfi_signal_5",
        "vfi_hist",
        "range_100_position",
        "range_100_width_atr",
        "distance_to_demand_zone_atr",
        "distance_to_supply_zone_atr",
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
        "vfi_cross_up",
        "vfi_cross_down",
        "vfi_zero_cross_up",
        "vfi_zero_cross_down",
        "vfi_bullish_divergence",
        "vfi_bearish_divergence",
        "sweep_signal",
        "choch_signal",
        "bos_signal",
        "fvg_signal",
        "eqh_signal",
        "eql_signal",
        "liquidity_pool_signal",
        "demand_zone_retest",
        "supply_zone_retest",
        "order_block_retest_signal",
        "supertrend_flip",
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


def _add_tradingview_style_indicators(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    high = frame["High"]
    low = frame["Low"]
    close = frame["Close"]
    volume = frame["Volume"].fillna(0)
    typical_price = (high + low + close) / 3

    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    frame["macd_line"] = ema_12 - ema_26
    frame["macd_signal"] = frame["macd_line"].ewm(span=9, adjust=False).mean()
    frame["macd_hist"] = frame["macd_line"] - frame["macd_signal"]

    plus_dm = (high.diff()).where((high.diff() > -low.diff()) & (high.diff() > 0), 0.0)
    minus_dm = (-low.diff()).where((-low.diff() > high.diff()) & (-low.diff() > 0), 0.0)
    tr_14 = frame["atr_14"].replace(0, np.nan)
    frame["plus_di_14"] = 100 * plus_dm.rolling(14, min_periods=7).mean() / tr_14
    frame["minus_di_14"] = 100 * minus_dm.rolling(14, min_periods=7).mean() / tr_14
    frame["di_spread_14"] = frame["plus_di_14"] - frame["minus_di_14"]
    dx = 100 * (frame["plus_di_14"] - frame["minus_di_14"]).abs() / (frame["plus_di_14"] + frame["minus_di_14"]).replace(0, np.nan)
    frame["adx_14"] = dx.rolling(14, min_periods=7).mean()

    typical_mean = typical_price.rolling(20, min_periods=10).mean()
    typical_mad = (typical_price - typical_mean).abs().rolling(20, min_periods=10).mean()
    frame["cci_20"] = (typical_price - typical_mean) / (0.015 * typical_mad.replace(0, np.nan))

    rsi = frame["rsi_14"]
    rsi_low = rsi.rolling(14, min_periods=7).min()
    rsi_high = rsi.rolling(14, min_periods=7).max()
    stoch_rsi = 100 * (rsi - rsi_low) / (rsi_high - rsi_low).replace(0, np.nan)
    frame["stoch_rsi_k"] = stoch_rsi.rolling(3, min_periods=1).mean()
    frame["stoch_rsi_d"] = frame["stoch_rsi_k"].rolling(3, min_periods=1).mean()

    donchian_high = high.rolling(20, min_periods=10).max()
    donchian_low = low.rolling(20, min_periods=10).min()
    frame["donchian_20_position"] = (close - donchian_low) / (donchian_high - donchian_low).replace(0, np.nan)
    keltner_mid = close.ewm(span=20, adjust=False).mean()
    keltner_width = 1.5 * frame["atr_14"].replace(0, np.nan)
    frame["keltner_position"] = (close - keltner_mid) / keltner_width

    supertrend_mid = (high + low) / 2
    supertrend_width = 3.0 * frame["atr_14"].replace(0, np.nan)
    upper_band = supertrend_mid + supertrend_width
    lower_band = supertrend_mid - supertrend_width
    direction = pd.Series(0, index=frame.index, dtype="float64")
    direction = direction.mask(close > upper_band.shift(1), 1)
    direction = direction.mask(close < lower_band.shift(1), -1)
    direction = direction.replace(0, np.nan).ffill().fillna(0)
    frame["supertrend_direction"] = direction
    frame["supertrend_flip"] = direction.ne(direction.shift()).fillna(False).astype(int)

    frame = _add_vfi_features(frame, typical_price, volume)
    return frame


def _add_vfi_features(frame: pd.DataFrame, typical_price: pd.Series, volume: pd.Series) -> pd.DataFrame:
    result = frame.copy()
    length = 130
    coef = 0.2
    volume_coef = 2.5
    price_change = typical_price.diff()
    inter = np.log(typical_price.replace(0, np.nan)).diff().rolling(30, min_periods=10).std()
    cutoff = coef * inter * result["Close"]
    average_volume = volume.rolling(length, min_periods=20).mean().shift(1)
    capped_volume = pd.concat([volume, average_volume * volume_coef], axis=1).min(axis=1)
    money_flow_volume = capped_volume.where(price_change > cutoff, 0.0)
    money_flow_volume = money_flow_volume.where(price_change >= -cutoff, -capped_volume)
    result["vfi_130"] = money_flow_volume.rolling(length, min_periods=20).sum() / average_volume.replace(0, np.nan)
    result["vfi_signal_5"] = result["vfi_130"].ewm(span=5, adjust=False).mean()
    result["vfi_hist"] = result["vfi_130"] - result["vfi_signal_5"]
    result["vfi_cross_up"] = ((result["vfi_130"] > result["vfi_signal_5"]) & (result["vfi_130"].shift(1) <= result["vfi_signal_5"].shift(1))).astype(int)
    result["vfi_cross_down"] = ((result["vfi_130"] < result["vfi_signal_5"]) & (result["vfi_130"].shift(1) >= result["vfi_signal_5"].shift(1))).astype(int)
    result["vfi_zero_cross_up"] = ((result["vfi_130"] > 0) & (result["vfi_130"].shift(1) <= 0)).astype(int)
    result["vfi_zero_cross_down"] = ((result["vfi_130"] < 0) & (result["vfi_130"].shift(1) >= 0)).astype(int)
    result["vfi_bullish_divergence"] = ((result["Close"] < result["Close"].shift(30)) & (result["vfi_130"] > result["vfi_130"].shift(30))).astype(int)
    result["vfi_bearish_divergence"] = ((result["Close"] > result["Close"].shift(30)) & (result["vfi_130"] < result["vfi_130"].shift(30))).astype(int)
    return result


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


def _add_chart_structure_features(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    high = frame["High"]
    low = frame["Low"]
    close = frame["Close"]
    atr = frame["atr_30"].replace(0, np.nan)

    tolerance = (0.15 * atr).clip(lower=0.5)
    prior_high_50 = high.rolling(50, min_periods=20).max().shift(1)
    prior_low_50 = low.rolling(50, min_periods=20).min().shift(1)
    frame["eqh_signal"] = ((high.sub(prior_high_50).abs() <= tolerance) & (close < prior_high_50)).fillna(False).astype(int)
    frame["eql_signal"] = ((low.sub(prior_low_50).abs() <= tolerance) & (close > prior_low_50)).fillna(False).astype(int)
    frame["liquidity_pool_signal"] = np.select([frame["eql_signal"].astype(bool), frame["eqh_signal"].astype(bool)], [BULLISH, BEARISH], default=0).astype(np.int8)

    range_high = high.rolling(100, min_periods=30).max().shift(1)
    range_low = low.rolling(100, min_periods=30).min().shift(1)
    range_width = range_high - range_low
    frame["range_100_position"] = (close - range_low) / range_width.replace(0, np.nan)
    frame["range_100_width_atr"] = range_width / frame["atr_120"].replace(0, np.nan)

    bullish_displacement = (frame["displacement_candle"] == 1) & (close > frame["Open"])
    bearish_displacement = (frame["displacement_candle"] == 1) & (close < frame["Open"])
    demand_low = low.where(bullish_displacement).ffill()
    demand_high = frame[["Open", "Close"]].min(axis=1).where(bullish_displacement).ffill()
    supply_low = frame[["Open", "Close"]].max(axis=1).where(bearish_displacement).ffill()
    supply_high = high.where(bearish_displacement).ffill()

    frame["distance_to_demand_zone_atr"] = (close - demand_high) / atr
    frame["distance_to_supply_zone_atr"] = (supply_low - close) / atr
    frame["demand_zone_retest"] = ((low <= demand_high) & (close >= demand_low) & demand_low.notna()).fillna(False).astype(int)
    frame["supply_zone_retest"] = ((high >= supply_low) & (close <= supply_high) & supply_low.notna()).fillna(False).astype(int)
    frame["order_block_retest_signal"] = np.select(
        [frame["demand_zone_retest"].astype(bool), frame["supply_zone_retest"].astype(bool)],
        [BULLISH, BEARISH],
        default=0,
    ).astype(np.int8)
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
