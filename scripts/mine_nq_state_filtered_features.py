from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FilterCondition:
    column: str
    op: str
    value: object


@dataclass(frozen=True)
class StateFilter:
    name: str
    conditions: tuple[FilterCondition, ...]


def load_features(cache_path: str) -> pd.DataFrame:
    cache = pd.read_pickle(cache_path)
    features = cache["features"] if isinstance(cache, dict) and "features" in cache else cache
    frame = features.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return enrich_state_features(frame)


def enrich_state_features(features: pd.DataFrame) -> pd.DataFrame:
    frame = features.copy()
    open_price = pd.to_numeric(frame["Open"], errors="coerce")
    high = pd.to_numeric(frame["High"], errors="coerce")
    low = pd.to_numeric(frame["Low"], errors="coerce")
    close = pd.to_numeric(frame["Close"], errors="coerce")
    volume = pd.to_numeric(frame["Volume"], errors="coerce").fillna(0.0)
    if "return_1m" not in frame.columns:
        frame["return_1m"] = close.pct_change()
    true_range = _true_range(high, low, close)
    if "atr_14" not in frame.columns:
        frame["atr_14"] = true_range.rolling(14, min_periods=5).mean()
    if "atr_30" not in frame.columns:
        frame["atr_30"] = true_range.rolling(30, min_periods=10).mean()
    if "range_mean_30" not in frame.columns:
        frame["range_mean_30"] = (high - low).rolling(30, min_periods=10).mean()
    if "vol_120" not in frame.columns:
        frame["vol_120"] = pd.to_numeric(frame["return_1m"], errors="coerce").rolling(120, min_periods=30).std()
    if "volume_z_60" not in frame.columns:
        frame["volume_z_60"] = _zscore(volume, 60)
    if "momentum_60" not in frame.columns:
        frame["momentum_60"] = close.diff(60)
    if "z_30" not in frame.columns:
        frame["z_30"] = _zscore(close, 30)
    if "vwap" not in frame.columns:
        if "trade_date" in frame.columns:
            grouped_volume = volume.groupby(frame["trade_date"], sort=False)
            cumulative_volume = grouped_volume.cumsum().replace(0, pd.NA)
            frame["vwap"] = (close * volume).groupby(frame["trade_date"], sort=False).cumsum() / cumulative_volume
        else:
            cumulative_volume = volume.cumsum().replace(0, pd.NA)
            frame["vwap"] = (close * volume).cumsum() / cumulative_volume
    frame["vwap_side"] = (close >= pd.to_numeric(frame["vwap"], errors="coerce")).map({True: "above", False: "below"})
    frame["ema_10"] = close.ewm(span=10, adjust=False).mean()
    frame["ema_20"] = close.ewm(span=20, adjust=False).mean()
    frame["ema_50"] = close.ewm(span=50, adjust=False).mean()
    frame["trend_stack_side"] = "flat"
    frame.loc[(frame["ema_10"] > frame["ema_20"]) & (frame["ema_20"] > frame["ema_50"]), "trend_stack_side"] = "long"
    frame.loc[(frame["ema_10"] < frame["ema_20"]) & (frame["ema_20"] < frame["ema_50"]), "trend_stack_side"] = "short"
    frame["trend_120"] = close - close.rolling(120).mean()
    frame["trend_side_120"] = (frame["trend_120"] >= 0).map({True: "up", False: "down"})
    frame["minute_bucket_30"] = (frame["minute_of_day"] // 30).astype("Int64")
    frame["vol_120_rank"] = pd.to_numeric(frame["vol_120"], errors="coerce").rank(pct=True)
    frame["range_30_rank"] = pd.to_numeric(frame["range_mean_30"], errors="coerce").rank(pct=True)
    frame["entry_range_points"] = (high - low).where((high - low) > 0)
    frame["entry_body_points"] = (close - open_price).abs()
    frame["entry_body_to_range"] = frame["entry_body_points"] / frame["entry_range_points"]
    frame["entry_body_rank"] = frame["entry_body_points"].rank(pct=True)
    frame["entry_close_location"] = (close - low) / frame["entry_range_points"]
    frame["entry_candle_side"] = (close >= open_price).map({True: "up", False: "down"})
    frame["entry_close_zone"] = "middle"
    frame.loc[frame["entry_close_location"] >= 0.70, "entry_close_zone"] = "high"
    frame.loc[frame["entry_close_location"] <= 0.30, "entry_close_zone"] = "low"
    frame["vwap_distance_points"] = close - pd.to_numeric(frame["vwap"], errors="coerce")
    frame["vwap_distance_abs_rank"] = frame["vwap_distance_points"].abs().rank(pct=True)
    frame["vwap_stretch_side"] = "neutral"
    frame.loc[(frame["vwap_distance_points"] > 0) & (frame["vwap_distance_abs_rank"] > 0.67), "vwap_stretch_side"] = "above"
    frame.loc[(frame["vwap_distance_points"] < 0) & (frame["vwap_distance_abs_rank"] > 0.67), "vwap_stretch_side"] = "below"
    frame["return_1m_side"] = (pd.to_numeric(frame["return_1m"], errors="coerce") >= 0).map({True: "positive", False: "negative"})
    frame = _enrich_price_volume_state(frame, high=high, low=low, close=close, volume=volume)
    frame = _enrich_tradingview_state(frame, high=high, low=low, close=close)
    return frame


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    previous_close = close.shift(1)
    return pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)


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


def _enrich_price_volume_state(
    frame: pd.DataFrame,
    *,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
) -> pd.DataFrame:
    result = frame.copy()
    session_key = result["trade_date"] if "trade_date" in result.columns else pd.Series("all", index=result.index)
    cumulative_session_volume = volume.groupby(session_key, sort=False).cumsum().replace(0, np.nan)
    result["session_vwap"] = (close * volume).groupby(session_key, sort=False).cumsum() / cumulative_session_volume
    result["session_vwap_distance_atr"] = (close - result["session_vwap"]) / pd.to_numeric(result["atr_30"], errors="coerce").replace(0, np.nan)
    result["session_vwap_side"] = (close >= result["session_vwap"]).map({True: "above", False: "below"})
    result["session_vwap_stretch_side"] = "neutral"
    result.loc[result["session_vwap_distance_atr"] >= 0.5, "session_vwap_stretch_side"] = "above"
    result.loc[result["session_vwap_distance_atr"] <= -0.5, "session_vwap_stretch_side"] = "below"
    result["relative_volume_20"] = volume / volume.rolling(20, min_periods=5).mean().replace(0, np.nan)
    result["relative_volume_side"] = "normal"
    result.loc[result["relative_volume_20"] >= 1.2, "relative_volume_side"] = "expanding"
    result.loc[result["relative_volume_20"] <= 0.75, "relative_volume_side"] = "drying"
    signed_volume = volume * np.sign(close.diff().fillna(0.0))
    obv = signed_volume.cumsum()
    result["obv_slope_20"] = obv.diff(20)
    result["obv_slope_side"] = (result["obv_slope_20"] >= 0).map({True: "up", False: "down"})
    money_flow_multiplier = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
    result["cmf_20"] = (money_flow_multiplier.fillna(0.0) * volume).rolling(20, min_periods=10).sum() / volume.rolling(
        20, min_periods=10
    ).sum().replace(0, np.nan)
    result["cmf_side"] = (result["cmf_20"] >= 0).map({True: "positive", False: "negative"})
    typical_price = (high + low + close) / 3.0
    raw_money_flow = typical_price * volume
    positive_flow = raw_money_flow.where(typical_price > typical_price.shift(1), 0.0)
    negative_flow = raw_money_flow.where(typical_price < typical_price.shift(1), 0.0)
    money_ratio = positive_flow.rolling(14, min_periods=7).sum() / negative_flow.rolling(14, min_periods=7).sum().replace(0, np.nan)
    result["mfi_14"] = 100 - (100 / (1 + money_ratio))
    result["mfi_side"] = "neutral"
    result.loc[result["mfi_14"] > 50, "mfi_side"] = "bullish"
    result.loc[result["mfi_14"] < 50, "mfi_side"] = "bearish"
    result["price_volume_corr_20"] = pd.to_numeric(result["return_1m"], errors="coerce").rolling(20, min_periods=10).corr(volume.pct_change())
    result["price_volume_corr_side"] = "neutral"
    result.loc[result["price_volume_corr_20"] > 0, "price_volume_corr_side"] = "positive"
    result.loc[result["price_volume_corr_20"] < 0, "price_volume_corr_side"] = "negative"
    volume_price_trend = (volume * close.pct_change().fillna(0.0)).cumsum()
    result["volume_price_trend_slope_20"] = volume_price_trend.diff(20)
    result["volume_price_trend_side"] = (result["volume_price_trend_slope_20"] >= 0).map({True: "up", False: "down"})
    result["bullish_volume_divergence"] = ((close < close.shift(20)) & (obv > obv.shift(20))).astype(int)
    result["bearish_volume_divergence"] = ((close > close.shift(20)) & (obv < obv.shift(20))).astype(int)
    result["volume_breakout_signal"] = (
        (result["relative_volume_20"] >= 1.8)
        & ((high - low) >= pd.to_numeric(result["atr_30"], errors="coerce").fillna(high - low))
    ).astype(int)
    result["low_volume_pullback"] = (
        (result["relative_volume_20"] <= 0.75)
        & ((high - low) <= pd.to_numeric(result["atr_30"], errors="coerce").fillna(high - low))
    ).astype(int)
    return result


def _enrich_tradingview_state(
    frame: pd.DataFrame,
    *,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> pd.DataFrame:
    result = frame.copy()
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    result["macd_line"] = ema_12 - ema_26
    result["macd_signal"] = result["macd_line"].ewm(span=9, adjust=False).mean()
    result["macd_hist"] = result["macd_line"] - result["macd_signal"]
    result["macd_side"] = (result["macd_hist"] >= 0).map({True: "positive", False: "negative"})
    plus_dm = high.diff().where((high.diff() > -low.diff()) & (high.diff() > 0), 0.0)
    minus_dm = (-low.diff()).where((-low.diff() > high.diff()) & (-low.diff() > 0), 0.0)
    atr_14 = pd.to_numeric(result["atr_14"], errors="coerce").replace(0, np.nan)
    result["plus_di_14"] = 100 * plus_dm.rolling(14, min_periods=7).mean() / atr_14
    result["minus_di_14"] = 100 * minus_dm.rolling(14, min_periods=7).mean() / atr_14
    result["di_spread_14"] = result["plus_di_14"] - result["minus_di_14"]
    result["di_side"] = (result["di_spread_14"] >= 0).map({True: "long", False: "short"})
    dx = 100 * result["di_spread_14"].abs() / (result["plus_di_14"] + result["minus_di_14"]).replace(0, np.nan)
    result["adx_14"] = dx.rolling(14, min_periods=7).mean()
    result["adx_state"] = "inactive"
    result.loc[result["adx_14"] >= 20, "adx_state"] = "active"
    typical_price = (high + low + close) / 3.0
    typical_mean = typical_price.rolling(20, min_periods=10).mean()
    typical_mad = (typical_price - typical_mean).abs().rolling(20, min_periods=10).mean()
    result["cci_20"] = (typical_price - typical_mean) / (0.015 * typical_mad.replace(0, np.nan))
    result["cci_side"] = "neutral"
    result.loc[result["cci_20"] > 0, "cci_side"] = "positive"
    result.loc[result["cci_20"] < 0, "cci_side"] = "negative"
    result["rsi_14"] = _rsi(close, 14)
    rsi_low = result["rsi_14"].rolling(14, min_periods=7).min()
    rsi_high = result["rsi_14"].rolling(14, min_periods=7).max()
    stoch_rsi = 100 * (result["rsi_14"] - rsi_low) / (rsi_high - rsi_low).replace(0, np.nan)
    result["stoch_rsi_k"] = stoch_rsi.rolling(3, min_periods=1).mean()
    result["stoch_rsi_d"] = result["stoch_rsi_k"].rolling(3, min_periods=1).mean()
    result["stoch_rsi_side"] = "neutral"
    result.loc[(result["stoch_rsi_k"] > result["stoch_rsi_d"]) & (result["stoch_rsi_k"] < 80), "stoch_rsi_side"] = "recovering"
    result.loc[(result["stoch_rsi_k"] < result["stoch_rsi_d"]) & (result["stoch_rsi_k"] > 20), "stoch_rsi_side"] = "fading"
    donchian_high = high.rolling(20, min_periods=10).max()
    donchian_low = low.rolling(20, min_periods=10).min()
    result["donchian_20_position"] = (close - donchian_low) / (donchian_high - donchian_low).replace(0, np.nan)
    result["donchian_zone"] = "middle"
    result.loc[result["donchian_20_position"] > 0.5, "donchian_zone"] = "upper"
    result.loc[result["donchian_20_position"] < 0.5, "donchian_zone"] = "lower"
    middle = close.rolling(20, min_periods=10).mean()
    std = close.rolling(20, min_periods=10).std()
    result["boll_position"] = (close - middle) / (2 * std).replace(0, np.nan)
    result["boll_width_atr"] = (4 * std) / pd.to_numeric(result["atr_30"], errors="coerce").replace(0, np.nan)
    result["boll_squeeze"] = (
        result["boll_width_atr"] <= result["boll_width_atr"].rolling(120, min_periods=30).quantile(0.25)
    ).fillna(False).astype(int)
    result["boll_zone"] = "middle"
    result.loc[result["boll_position"] > 0.75, "boll_zone"] = "upper"
    result.loc[result["boll_position"] < -0.75, "boll_zone"] = "lower"
    return result


def load_trades(path: str) -> pd.DataFrame:
    trades = pd.read_csv(path)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["net_points"] = pd.to_numeric(trades["net_points"], errors="coerce")
    trades["direction"] = pd.to_numeric(trades["direction"], errors="coerce")
    return trades.dropna(subset=["entry_ts", "candidate", "net_points", "direction"]).copy()


def attach_state(trades: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    state_columns = [
        "ts",
        "Close",
        "vwap",
        "vwap_side",
        "trend_side_120",
        "momentum_60",
        "z_30",
        "vol_120_rank",
        "range_30_rank",
        "volume_z_60",
        "return_1m_side",
        "entry_body_rank",
        "entry_body_to_range",
        "entry_candle_side",
        "entry_close_zone",
        "vwap_distance_abs_rank",
        "vwap_stretch_side",
        "minute_bucket_30",
        "session_vwap_distance_atr",
        "session_vwap_side",
        "session_vwap_stretch_side",
        "relative_volume_20",
        "relative_volume_side",
        "obv_slope_side",
        "cmf_20",
        "cmf_side",
        "mfi_14",
        "mfi_side",
        "price_volume_corr_side",
        "volume_price_trend_side",
        "bullish_volume_divergence",
        "bearish_volume_divergence",
        "volume_breakout_signal",
        "low_volume_pullback",
        "macd_side",
        "adx_state",
        "di_side",
        "cci_side",
        "stoch_rsi_side",
        "donchian_zone",
        "boll_squeeze",
        "boll_zone",
        "trend_stack_side",
    ]
    for column in state_columns:
        if column not in features.columns:
            features[column] = pd.NA
    state = features[state_columns].rename(columns={"ts": "entry_ts"})
    return trades.merge(state, on="entry_ts", how="left")


def candidate_filters(frame: pd.DataFrame) -> list[StateFilter]:
    def single(name: str, column: str, op: str, value: object) -> StateFilter:
        return StateFilter(name, (FilterCondition(column, op, value),))

    def combo(name: str, *conditions: FilterCondition) -> StateFilter:
        return StateFilter(name, conditions)

    filters = [
        single("vwap_above", "vwap_side", "eq", "above"),
        single("vwap_below", "vwap_side", "eq", "below"),
        single("trend_120_up", "trend_side_120", "eq", "up"),
        single("trend_120_down", "trend_side_120", "eq", "down"),
        single("momentum_60_positive", "momentum_60", "gt", 0.0),
        single("momentum_60_negative", "momentum_60", "lt", 0.0),
        single("z_30_negative", "z_30", "lt", 0.0),
        single("z_30_positive", "z_30", "gt", 0.0),
        single("vol_120_low_mid", "vol_120_rank", "le", 0.67),
        single("vol_120_high", "vol_120_rank", "gt", 0.67),
        single("range_30_low_mid", "range_30_rank", "le", 0.67),
        single("range_30_high", "range_30_rank", "gt", 0.67),
        single("volume_z_60_high", "volume_z_60", "gt", 1.0),
        single("volume_z_60_low", "volume_z_60", "lt", -1.0),
        single("return_1m_positive", "return_1m_side", "eq", "positive"),
        single("return_1m_negative", "return_1m_side", "eq", "negative"),
        single("entry_candle_up", "entry_candle_side", "eq", "up"),
        single("entry_candle_down", "entry_candle_side", "eq", "down"),
        single("entry_close_high", "entry_close_zone", "eq", "high"),
        single("entry_close_low", "entry_close_zone", "eq", "low"),
        single("entry_body_low_mid", "entry_body_rank", "le", 0.67),
        single("entry_body_high", "entry_body_rank", "gt", 0.67),
        single("vwap_distance_low_mid", "vwap_distance_abs_rank", "le", 0.67),
        single("vwap_distance_high", "vwap_distance_abs_rank", "gt", 0.67),
        single("vwap_stretched_above", "vwap_stretch_side", "eq", "above"),
        single("vwap_stretched_below", "vwap_stretch_side", "eq", "below"),
        single("session_vwap_above", "session_vwap_side", "eq", "above"),
        single("session_vwap_below", "session_vwap_side", "eq", "below"),
        single("session_vwap_stretched_above", "session_vwap_stretch_side", "eq", "above"),
        single("session_vwap_stretched_below", "session_vwap_stretch_side", "eq", "below"),
        single("relative_volume_expanding", "relative_volume_side", "eq", "expanding"),
        single("relative_volume_drying", "relative_volume_side", "eq", "drying"),
        single("obv_slope_up", "obv_slope_side", "eq", "up"),
        single("obv_slope_down", "obv_slope_side", "eq", "down"),
        single("cmf_positive", "cmf_side", "eq", "positive"),
        single("cmf_negative", "cmf_side", "eq", "negative"),
        single("mfi_bullish", "mfi_side", "eq", "bullish"),
        single("mfi_bearish", "mfi_side", "eq", "bearish"),
        single("price_volume_corr_positive", "price_volume_corr_side", "eq", "positive"),
        single("price_volume_corr_negative", "price_volume_corr_side", "eq", "negative"),
        single("volume_price_trend_up", "volume_price_trend_side", "eq", "up"),
        single("volume_price_trend_down", "volume_price_trend_side", "eq", "down"),
        single("bullish_volume_divergence", "bullish_volume_divergence", "gt", 0.0),
        single("bearish_volume_divergence", "bearish_volume_divergence", "gt", 0.0),
        single("volume_breakout_signal", "volume_breakout_signal", "gt", 0.0),
        single("low_volume_pullback", "low_volume_pullback", "gt", 0.0),
        single("macd_positive", "macd_side", "eq", "positive"),
        single("macd_negative", "macd_side", "eq", "negative"),
        single("adx_active", "adx_state", "eq", "active"),
        single("di_long", "di_side", "eq", "long"),
        single("di_short", "di_side", "eq", "short"),
        single("cci_positive", "cci_side", "eq", "positive"),
        single("cci_negative", "cci_side", "eq", "negative"),
        single("stoch_rsi_recovering", "stoch_rsi_side", "eq", "recovering"),
        single("stoch_rsi_fading", "stoch_rsi_side", "eq", "fading"),
        single("donchian_upper_half", "donchian_zone", "eq", "upper"),
        single("donchian_lower_half", "donchian_zone", "eq", "lower"),
        single("boll_squeeze", "boll_squeeze", "gt", 0.0),
        single("boll_upper_zone", "boll_zone", "eq", "upper"),
        single("boll_lower_zone", "boll_zone", "eq", "lower"),
        single("trend_stack_long", "trend_stack_side", "eq", "long"),
        single("trend_stack_short", "trend_stack_side", "eq", "short"),
        combo(
            "vwap_above_and_trend_120_up",
            FilterCondition("vwap_side", "eq", "above"),
            FilterCondition("trend_side_120", "eq", "up"),
        ),
        combo(
            "vwap_below_and_trend_120_down",
            FilterCondition("vwap_side", "eq", "below"),
            FilterCondition("trend_side_120", "eq", "down"),
        ),
        combo(
            "vwap_above_and_momentum_60_positive",
            FilterCondition("vwap_side", "eq", "above"),
            FilterCondition("momentum_60", "gt", 0.0),
        ),
        combo(
            "vwap_below_and_momentum_60_negative",
            FilterCondition("vwap_side", "eq", "below"),
            FilterCondition("momentum_60", "lt", 0.0),
        ),
        combo(
            "trend_120_up_and_z_30_negative",
            FilterCondition("trend_side_120", "eq", "up"),
            FilterCondition("z_30", "lt", 0.0),
        ),
        combo(
            "trend_120_down_and_z_30_positive",
            FilterCondition("trend_side_120", "eq", "down"),
            FilterCondition("z_30", "gt", 0.0),
        ),
        combo(
            "trend_120_up_and_vol_120_low_mid",
            FilterCondition("trend_side_120", "eq", "up"),
            FilterCondition("vol_120_rank", "le", 0.67),
        ),
        combo(
            "trend_120_down_and_vol_120_low_mid",
            FilterCondition("trend_side_120", "eq", "down"),
            FilterCondition("vol_120_rank", "le", 0.67),
        ),
        combo(
            "trend_120_up_and_range_30_low_mid",
            FilterCondition("trend_side_120", "eq", "up"),
            FilterCondition("range_30_rank", "le", 0.67),
        ),
        combo(
            "trend_120_down_and_range_30_low_mid",
            FilterCondition("trend_side_120", "eq", "down"),
            FilterCondition("range_30_rank", "le", 0.67),
        ),
        combo(
            "trend_120_up_and_entry_close_high",
            FilterCondition("trend_side_120", "eq", "up"),
            FilterCondition("entry_close_zone", "eq", "high"),
        ),
        combo(
            "trend_120_up_and_entry_close_low",
            FilterCondition("trend_side_120", "eq", "up"),
            FilterCondition("entry_close_zone", "eq", "low"),
        ),
        combo(
            "trend_120_down_and_entry_close_low",
            FilterCondition("trend_side_120", "eq", "down"),
            FilterCondition("entry_close_zone", "eq", "low"),
        ),
        combo(
            "trend_120_down_and_entry_close_high",
            FilterCondition("trend_side_120", "eq", "down"),
            FilterCondition("entry_close_zone", "eq", "high"),
        ),
        combo(
            "vwap_below_and_entry_close_high",
            FilterCondition("vwap_side", "eq", "below"),
            FilterCondition("entry_close_zone", "eq", "high"),
        ),
        combo(
            "vwap_above_and_entry_close_low",
            FilterCondition("vwap_side", "eq", "above"),
            FilterCondition("entry_close_zone", "eq", "low"),
        ),
        combo(
            "momentum_60_positive_and_entry_body_low_mid",
            FilterCondition("momentum_60", "gt", 0.0),
            FilterCondition("entry_body_rank", "le", 0.67),
        ),
        combo(
            "momentum_60_negative_and_entry_body_low_mid",
            FilterCondition("momentum_60", "lt", 0.0),
            FilterCondition("entry_body_rank", "le", 0.67),
        ),
        combo(
            "vwap_stretched_above_and_z_30_positive",
            FilterCondition("vwap_stretch_side", "eq", "above"),
            FilterCondition("z_30", "gt", 0.0),
        ),
        combo(
            "vwap_stretched_below_and_z_30_negative",
            FilterCondition("vwap_stretch_side", "eq", "below"),
            FilterCondition("z_30", "lt", 0.0),
        ),
        combo(
            "volume_z_60_high_and_entry_close_high",
            FilterCondition("volume_z_60", "gt", 1.0),
            FilterCondition("entry_close_zone", "eq", "high"),
        ),
        combo(
            "volume_z_60_high_and_entry_close_low",
            FilterCondition("volume_z_60", "gt", 1.0),
            FilterCondition("entry_close_zone", "eq", "low"),
        ),
        combo(
            "session_vwap_above_and_relative_volume_expanding",
            FilterCondition("session_vwap_side", "eq", "above"),
            FilterCondition("relative_volume_side", "eq", "expanding"),
        ),
        combo(
            "session_vwap_below_and_relative_volume_expanding",
            FilterCondition("session_vwap_side", "eq", "below"),
            FilterCondition("relative_volume_side", "eq", "expanding"),
        ),
        combo(
            "mfi_bullish_and_cmf_positive",
            FilterCondition("mfi_side", "eq", "bullish"),
            FilterCondition("cmf_side", "eq", "positive"),
        ),
        combo(
            "mfi_bearish_and_cmf_negative",
            FilterCondition("mfi_side", "eq", "bearish"),
            FilterCondition("cmf_side", "eq", "negative"),
        ),
        combo(
            "macd_positive_and_adx_active",
            FilterCondition("macd_side", "eq", "positive"),
            FilterCondition("adx_state", "eq", "active"),
        ),
        combo(
            "macd_negative_and_adx_active",
            FilterCondition("macd_side", "eq", "negative"),
            FilterCondition("adx_state", "eq", "active"),
        ),
        combo(
            "cci_positive_and_di_long",
            FilterCondition("cci_side", "eq", "positive"),
            FilterCondition("di_side", "eq", "long"),
        ),
        combo(
            "cci_negative_and_di_short",
            FilterCondition("cci_side", "eq", "negative"),
            FilterCondition("di_side", "eq", "short"),
        ),
        combo(
            "boll_squeeze_and_relative_volume_expanding",
            FilterCondition("boll_squeeze", "gt", 0.0),
            FilterCondition("relative_volume_side", "eq", "expanding"),
        ),
        combo(
            "donchian_upper_half_and_adx_active",
            FilterCondition("donchian_zone", "eq", "upper"),
            FilterCondition("adx_state", "eq", "active"),
        ),
        combo(
            "donchian_lower_half_and_adx_active",
            FilterCondition("donchian_zone", "eq", "lower"),
            FilterCondition("adx_state", "eq", "active"),
        ),
        combo(
            "trend_stack_long_and_session_vwap_above",
            FilterCondition("trend_stack_side", "eq", "long"),
            FilterCondition("session_vwap_side", "eq", "above"),
        ),
        combo(
            "trend_stack_short_and_session_vwap_below",
            FilterCondition("trend_stack_side", "eq", "short"),
            FilterCondition("session_vwap_side", "eq", "below"),
        ),
    ]
    for bucket in sorted(frame["minute_bucket_30"].dropna().unique()):
        filters.append(single(f"minute_bucket_30_{int(bucket)}", "minute_bucket_30", "eq", int(bucket)))
    return filters


def mine_filters(
    trades: pd.DataFrame,
    *,
    min_trades: int,
    min_folds: int = 1,
    min_net_points: float,
    min_profit_factor: float,
    min_win_rate: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    filters = candidate_filters(trades)
    for candidate, group in trades.groupby("candidate", sort=False):
        baseline = summarize(group)
        for state_filter in filters:
            if not has_filter_columns(group, state_filter):
                continue
            selected = group[apply_filter(group, state_filter)]
            if selected.empty:
                continue
            summary = summarize(selected)
            if (
                summary["trades"] < min_trades
                or summary["folds"] < min_folds
                or summary["net_points"] < min_net_points
                or summary["profit_factor"] < min_profit_factor
                or summary["win_rate"] < min_win_rate
            ):
                continue
            rows.append(
                {
                    "candidate": candidate,
                    "filter": state_filter.name,
                    "filter_conditions": describe_filter(state_filter),
                    "trades": summary["trades"],
                    "net_points": summary["net_points"],
                    "profit_factor": summary["profit_factor"],
                    "win_rate": summary["win_rate"],
                    "avg_points": summary["avg_points"],
                    "folds": summary["folds"],
                    "positive_fold_rate": summary["positive_fold_rate"],
                    "min_fold_net_points": summary["min_fold_net_points"],
                    "baseline_trades": baseline["trades"],
                    "baseline_net_points": baseline["net_points"],
                    "baseline_profit_factor": baseline["profit_factor"],
                    "baseline_positive_fold_rate": baseline["positive_fold_rate"],
                    "baseline_min_fold_net_points": baseline["min_fold_net_points"],
                    "net_improvement": summary["net_points"] - baseline["net_points"],
                    "profit_factor_improvement": summary["profit_factor"] - baseline["profit_factor"],
                    "retained_trade_rate": summary["trades"] / max(baseline["trades"], 1),
                }
            )
    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame(rows)
    return result.sort_values(
        ["net_points", "profit_factor", "win_rate", "trades"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def has_filter_columns(frame: pd.DataFrame, state_filter: StateFilter) -> bool:
    return all(condition.column in frame.columns for condition in state_filter.conditions)


def apply_filter(frame: pd.DataFrame, state_filter: StateFilter) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for condition in state_filter.conditions:
        mask &= apply_condition(frame, condition)
    return mask


def apply_condition(frame: pd.DataFrame, condition: FilterCondition) -> pd.Series:
    values = frame[condition.column]
    if condition.op == "eq":
        return values == condition.value
    numeric = pd.to_numeric(values, errors="coerce")
    if condition.op == "gt":
        return numeric > float(condition.value)
    if condition.op == "lt":
        return numeric < float(condition.value)
    if condition.op == "le":
        return numeric <= float(condition.value)
    if condition.op == "ge":
        return numeric >= float(condition.value)
    raise ValueError(f"unknown filter op: {condition.op}")


def describe_filter(state_filter: StateFilter) -> str:
    return ";".join(f"{condition.column}{condition.op}{condition.value}" for condition in state_filter.conditions)


def summarize(frame: pd.DataFrame) -> dict[str, float]:
    net = pd.to_numeric(frame["net_points"], errors="coerce").dropna()
    wins = net[net > 0].sum()
    losses = abs(net[net < 0].sum())
    profit_factor = float(wins / losses) if losses else float("inf")
    return {
        "trades": int(len(net)),
        "net_points": float(net.sum()),
        "profit_factor": profit_factor,
        "win_rate": float((net > 0).mean()) if len(net) else 0.0,
        "avg_points": float(net.mean()) if len(net) else 0.0,
        **summarize_folds(frame),
    }


def summarize_folds(frame: pd.DataFrame) -> dict[str, float]:
    if "fold" not in frame.columns or frame.empty:
        return {"folds": 0, "positive_fold_rate": 0.0, "min_fold_net_points": 0.0}
    fold_net = pd.to_numeric(frame["net_points"], errors="coerce").groupby(frame["fold"]).sum()
    if fold_net.empty:
        return {"folds": 0, "positive_fold_rate": 0.0, "min_fold_net_points": 0.0}
    return {
        "folds": int(len(fold_net)),
        "positive_fold_rate": float((fold_net > 0).mean()),
        "min_fold_net_points": float(fold_net.min()),
    }


def write_report(path: Path, mined: pd.DataFrame, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NQ 5y State-Filtered Feature Mining",
        "",
        "This report mines state filters over existing 5-year direction-filtered NQ 1m walk-forward trade rows.",
        "",
        f"- Trades input: `{args.trades_input}`",
        f"- Feature cache: `{args.features_cache}`",
        f"- Rows found: `{len(mined):,}`",
        f"- Gates: min_trades=`{args.min_trades}`, min_folds=`{args.min_folds}`, min_net_points=`{args.min_net_points}`, min_profit_factor=`{args.min_profit_factor}`, min_win_rate=`{args.min_win_rate}`",
        "",
    ]
    if mined.empty:
        lines.append("No state-filtered rows passed the configured gates.")
    else:
        lines.extend(
            [
                "## Top State-Filtered Edges",
                "",
                "```csv",
                mined.head(args.top_n).to_csv(index=False).strip(),
                "```",
                "",
                "## Interpretation",
                "",
                "- These are post-filtered research edges mined from already selected walk-forward trades.",
                "- Use them as LLM debate and paper-validation candidates; they are not live-ready without a fresh walk-forward that selects the filter during training.",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine state filters over NQ walk-forward trade rows.")
    parser.add_argument("--features-cache", default=".tmp/nq-bar-5y-continuous-features-cache.pkl")
    parser.add_argument("--trades-input", default=".tmp/nq-bar-5y-directional-walkforward-trades.csv")
    parser.add_argument("--output", default=".tmp/nq-bar-5y-state-filtered-features.csv")
    parser.add_argument("--report", default="reports/NQ-bar-5y-state-filtered-feature-mining.md")
    parser.add_argument("--min-trades", type=int, default=80)
    parser.add_argument("--min-folds", type=int, default=2)
    parser.add_argument("--min-net-points", type=float, default=1500.0)
    parser.add_argument("--min-profit-factor", type=float, default=1.20)
    parser.add_argument("--min-win-rate", type=float, default=0.48)
    parser.add_argument("--top-n", type=int, default=25)
    args = parser.parse_args()

    features = load_features(args.features_cache)
    trades = attach_state(load_trades(args.trades_input), features)
    mined = mine_filters(
        trades,
        min_trades=args.min_trades,
        min_folds=args.min_folds,
        min_net_points=args.min_net_points,
        min_profit_factor=args.min_profit_factor,
        min_win_rate=args.min_win_rate,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    mined.to_csv(output, index=False)
    write_report(Path(args.report), mined, args)
    result = {
        "feature_rows": int(len(features)),
        "trade_rows": int(len(trades)),
        "mined_rows": int(len(mined)),
        "output": str(output),
        "report": args.report,
    }
    if not mined.empty:
        result["top_edge"] = mined.iloc[0].to_dict()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
