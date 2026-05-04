from __future__ import annotations

import os
import zipfile
from datetime import datetime, timedelta
from io import TextIOWrapper
from pathlib import Path
from typing import Annotated

import pandas as pd
import zstandard as zstd
from stockstats import wrap

from .utils import safe_ticker_component


_BAR_ZIP = Path("data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip")
_BAR_MEMBER = "glbx-mdp3-20100606-20260427.ohlcv-1m.csv.zst"
_TICK_ZIP = Path("data/raw/databento/GLBX-20260502-QG6TRKVV9Q.zip")

_INDICATOR_DESCRIPTIONS = {
    "close_50_sma": "50 SMA: medium-term trend and support/resistance context.",
    "close_200_sma": "200 SMA: long-term trend benchmark.",
    "close_10_ema": "10 EMA: short-term responsive trend indicator.",
    "macd": "MACD: momentum from EMA differences.",
    "macds": "MACD signal line.",
    "macdh": "MACD histogram.",
    "rsi": "RSI: momentum oscillator for overbought/oversold context.",
    "boll": "Bollinger middle band.",
    "boll_ub": "Bollinger upper band.",
    "boll_lb": "Bollinger lower band.",
    "atr": "ATR: volatility via average true range.",
    "vwma": "VWMA: volume-weighted moving average.",
    "mfi": "MFI: price and volume money-flow momentum.",
}


def _bar_zip_path() -> Path:
    return Path(os.getenv("DATABENTO_BAR_ZIP", _BAR_ZIP))


def _tick_zip_path() -> Path:
    return Path(os.getenv("DATABENTO_TICK_ZIP", _TICK_ZIP))


def _databento_cache_dir() -> Path:
    base = Path(os.getenv("DATABENTO_CACHE_DIR", os.getenv("TRADINGAGENTS_CACHE_DIR", ".tmp/tradingagents-cache")))
    path = base / "databento"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_bar_window(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    path = _bar_zip_path()
    if not path.exists():
        raise FileNotFoundError(f"Databento bar zip not found: {path}")

    source_stat = path.stat()
    source_fingerprint = f"{source_stat.st_size}-{int(source_stat.st_mtime)}"
    cache_file = (
        _databento_cache_dir()
        / (
            f"bars-{safe_ticker_component(symbol.upper())}-{start_date}-{end_date}"
            f"-{source_fingerprint}.pkl"
        )
    )
    if cache_file.exists():
        return pd.read_pickle(cache_file)

    chunks: list[pd.DataFrame] = []
    read_columns = ["ts_event", "open", "high", "low", "close", "volume", "symbol"]
    with zipfile.ZipFile(path) as archive:
        with archive.open(_BAR_MEMBER) as compressed:
            stream = zstd.ZstdDecompressor().stream_reader(compressed)
            text_stream = TextIOWrapper(stream, encoding="utf-8")
            for chunk in pd.read_csv(text_stream, usecols=read_columns, chunksize=200_000):
                chunk["ts_event"] = pd.to_datetime(chunk["ts_event"], utc=True)
                chunk = chunk[
                    (chunk["symbol"].str.upper() == symbol.upper())
                    & (chunk["ts_event"].dt.strftime("%Y-%m-%d") >= start_date)
                    & (chunk["ts_event"].dt.strftime("%Y-%m-%d") < end_date)
                ]
                if not chunk.empty:
                    chunks.append(chunk)

    if not chunks:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])

    data = pd.concat(chunks, ignore_index=True)
    data = data.rename(
        columns={
            "ts_event": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )
    result = data[["Date", "Open", "High", "Low", "Close", "Volume"]].sort_values("Date")
    result.to_pickle(cache_file)
    return result


def _iter_mbp_members(start_date: str, end_date: str) -> list[str]:
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    members = []
    current = start
    while current < end:
        members.append(f"glbx-mdp3-{current:%Y%m%d}.mbp-1.csv.zst")
        current += timedelta(days=1)
    return members


def _read_mbp_window(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    path = _tick_zip_path()
    if not path.exists():
        raise FileNotFoundError(f"Databento tick zip not found: {path}")

    read_columns = [
        "ts_event",
        "price",
        "size",
        "bid_px_00",
        "ask_px_00",
        "bid_sz_00",
        "ask_sz_00",
        "bid_ct_00",
        "ask_ct_00",
        "symbol",
    ]
    chunks: list[pd.DataFrame] = []
    with zipfile.ZipFile(path) as archive:
        available = set(archive.namelist())
        for member in _iter_mbp_members(start_date, end_date):
            if member not in available:
                continue
            date_part = member.removeprefix("glbx-mdp3-").removesuffix(".mbp-1.csv.zst")
            source_stat = path.stat()
            source_fingerprint = f"{source_stat.st_size}-{int(source_stat.st_mtime)}"
            cache_file = (
                _databento_cache_dir()
                / f"mbp1-{safe_ticker_component(symbol.upper())}-{date_part}-{source_fingerprint}.pkl"
            )
            if cache_file.exists():
                day_data = pd.read_pickle(cache_file)
            else:
                day_chunks = []
                with archive.open(member) as compressed:
                    stream = zstd.ZstdDecompressor().stream_reader(compressed)
                    text_stream = TextIOWrapper(stream, encoding="utf-8")
                    for chunk in pd.read_csv(text_stream, usecols=read_columns, chunksize=200_000):
                        chunk = chunk[chunk["symbol"].str.upper() == symbol.upper()]
                        if not chunk.empty:
                            day_chunks.append(chunk)
                day_data = pd.concat(day_chunks, ignore_index=True) if day_chunks else pd.DataFrame(columns=read_columns)
                day_data.to_pickle(cache_file)
            if not day_data.empty:
                chunks.append(day_data)

    if not chunks:
        return pd.DataFrame(columns=read_columns)

    data = pd.concat(chunks, ignore_index=True)
    data["ts_event"] = pd.to_datetime(data["ts_event"], utc=True)
    data = data[
        (data["ts_event"].dt.strftime("%Y-%m-%d") >= start_date)
        & (data["ts_event"].dt.strftime("%Y-%m-%d") < end_date)
    ]
    return data.sort_values("ts_event")


def get_stock_data(
    symbol: Annotated[str, "Databento futures symbol, e.g. NQM6"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    data = _read_bar_window(symbol, start_date, end_date)
    if data.empty:
        return f"No Databento OHLCV data found for symbol '{symbol}' between {start_date} and {end_date}"

    data = data.copy()
    data["Date"] = data["Date"].dt.tz_localize(None)
    for column in ["Open", "High", "Low", "Close"]:
        data[column] = pd.to_numeric(data[column], errors="coerce").round(2)
    data["Volume"] = pd.to_numeric(data["Volume"], errors="coerce").fillna(0).astype("int64")

    header = f"# Databento GLBX.MDP3 ohlcv-1m data for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(data)}\n"
    header += f"# Source: {_bar_zip_path()}\n\n"
    return header + data.to_csv(index=False)


def get_indicator(
    symbol: Annotated[str, "Databento futures symbol, e.g. NQM6"],
    indicator: Annotated[str, "technical indicator to calculate"],
    curr_date: Annotated[str, "The current trading date, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:
    if indicator not in _INDICATOR_DESCRIPTIONS:
        raise ValueError(
            f"Indicator {indicator} is not supported. Please choose from: {list(_INDICATOR_DESCRIPTIONS.keys())}"
        )

    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_date = (curr_date_dt - pd.Timedelta(days=look_back_days)).strftime("%Y-%m-%d")
    end_date = (curr_date_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    data = _read_bar_window(symbol, start_date, end_date)
    if data.empty:
        return f"No Databento data found for {symbol} from {start_date} to {end_date}"

    data = data.copy()
    data["Date"] = data["Date"].dt.tz_localize(None)
    df = wrap(data)
    df[indicator]
    result = df[["Date", indicator]].copy()
    result["Date"] = pd.to_datetime(result["Date"]).dt.strftime("%Y-%m-%d %H:%M:%S")

    header = f"## {indicator} values for {symbol.upper()} from {start_date} to {curr_date}\n\n"
    return header + result.tail(200).to_csv(index=False) + "\n\n" + _INDICATOR_DESCRIPTIONS[indicator]


def get_orderbook_microstructure(
    symbol: Annotated[str, "Databento futures symbol, e.g. NQM6"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    bucket: Annotated[str, "Pandas resample bucket, e.g. 1min, 5min, 15min"] = "5min",
) -> str:
    data = _read_mbp_window(symbol, start_date, end_date)
    if data.empty:
        return f"No Databento MBP-1 data found for symbol '{symbol}' between {start_date} and {end_date}"

    numeric_columns = [
        "price",
        "size",
        "bid_px_00",
        "ask_px_00",
        "bid_sz_00",
        "ask_sz_00",
        "bid_ct_00",
        "ask_ct_00",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data = data.dropna(subset=["bid_px_00", "ask_px_00", "bid_sz_00", "ask_sz_00"])
    if data.empty:
        return f"No valid top-of-book quotes found for {symbol} between {start_date} and {end_date}"

    data["mid_price"] = (data["bid_px_00"] + data["ask_px_00"]) / 2
    data["spread"] = data["ask_px_00"] - data["bid_px_00"]
    total_size = data["bid_sz_00"] + data["ask_sz_00"]
    data["book_imbalance"] = (data["bid_sz_00"] - data["ask_sz_00"]) / total_size.replace(0, pd.NA)
    data["quoted_depth"] = total_size
    data = data.set_index("ts_event")

    grouped = pd.DataFrame(
        {
            "quote_count": data["mid_price"].resample(bucket).count(),
            "mid_open": data["mid_price"].resample(bucket).first(),
            "mid_close": data["mid_price"].resample(bucket).last(),
            "mid_min": data["mid_price"].resample(bucket).min(),
            "mid_max": data["mid_price"].resample(bucket).max(),
            "spread_mean": data["spread"].resample(bucket).mean(),
            "spread_max": data["spread"].resample(bucket).max(),
            "imbalance_mean": data["book_imbalance"].resample(bucket).mean(),
            "imbalance_last": data["book_imbalance"].resample(bucket).last(),
            "quoted_depth_mean": data["quoted_depth"].resample(bucket).mean(),
            "bid_size_last": data["bid_sz_00"].resample(bucket).last(),
            "ask_size_last": data["ask_sz_00"].resample(bucket).last(),
        }
    ).dropna(how="all")
    grouped = grouped[grouped["quote_count"] > 0].tail(200)
    grouped = grouped.round(6)

    header = f"# Databento GLBX.MDP3 mbp-1 microstructure for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Bucket: {bucket}; source: {_tick_zip_path()}\n"
    header += "# Features: mid price, bid/ask spread, top-of-book size imbalance, quote count, and displayed depth.\n\n"
    return header + grouped.reset_index().to_csv(index=False)
