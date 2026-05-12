from __future__ import annotations

import re
import zipfile
from io import TextIOWrapper
from pathlib import Path
from typing import Any

import pandas as pd
import zstandard as zstd

from tradingagents.dataflows.databento import _bar_zip_path


BAR_MEMBER = "glbx-mdp3-20100606-20260427.ohlcv-1m.csv.zst"
NQ_SYMBOL_RE = re.compile(r"^NQ[HMUZ]\d$")


def load_continuous_nq_bars(
    *,
    start_date: str,
    end_date: str,
    cache_path: Path | str | None = None,
    source_csv: Path | str | None = None,
    source_zip: Path | str | None = None,
    min_volume: float = 1.0,
    chunk_size: int = 500_000,
) -> pd.DataFrame:
    """Load roll-aware continuous NQ 1-minute bars.

    The Databento export contains overlapping quarterly contracts and spread
    symbols. This loader keeps only standard NQ quarterly futures symbols and
    selects the highest-volume contract for each minute.
    """
    source = Path(source_csv) if source_csv else Path(source_zip) if source_zip else _bar_zip_path()
    cache = Path(cache_path) if cache_path else None
    cache_key = _cache_key(source, start_date, end_date, min_volume)
    if cache and cache.exists():
        payload = pd.read_pickle(cache)
        if isinstance(payload, dict) and payload.get("key") == cache_key and "bars" in payload:
            return payload["bars"]

    start_ts = pd.Timestamp(start_date, tz="UTC")
    end_ts = pd.Timestamp(end_date, tz="UTC")
    chunks = []
    for chunk in _iter_source_chunks(source, chunk_size):
        filtered = _filter_nq_chunk(chunk, start_ts, end_ts, min_volume)
        if not filtered.empty:
            chunks.append(filtered)

    if not chunks:
        raise ValueError(f"No standard NQ bars found in {source} for {start_date}..{end_date}")

    bars = pd.concat(chunks, ignore_index=True)
    bars = (
        bars.sort_values(["ts", "Volume"], ascending=[True, False])
        .drop_duplicates("ts", keep="first")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        pd.to_pickle({"key": cache_key, "bars": bars}, cache)
    return bars


def _cache_key(source: Path, start_date: str, end_date: str, min_volume: float) -> dict[str, Any]:
    stat = source.stat()
    return {
        "source": str(source.resolve()),
        "size": stat.st_size,
        "mtime": int(stat.st_mtime),
        "start_date": start_date,
        "end_date": end_date,
        "min_volume": float(min_volume),
    }


def _iter_source_chunks(source: Path, chunk_size: int):
    usecols = ["ts_event", "open", "high", "low", "close", "volume", "symbol"]
    if source.suffix == ".csv":
        yield from pd.read_csv(source, usecols=usecols, chunksize=chunk_size)
        return

    with zipfile.ZipFile(source) as archive:
        member = BAR_MEMBER if BAR_MEMBER in archive.namelist() else archive.namelist()[0]
        with archive.open(member) as compressed:
            stream = zstd.ZstdDecompressor().stream_reader(compressed)
            text_stream = TextIOWrapper(stream, encoding="utf-8")
            yield from pd.read_csv(text_stream, usecols=usecols, chunksize=chunk_size)


def _filter_nq_chunk(
    chunk: pd.DataFrame,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    min_volume: float,
) -> pd.DataFrame:
    symbols = chunk["symbol"].astype(str)
    chunk = chunk[symbols.map(lambda value: bool(NQ_SYMBOL_RE.match(value)))].copy()
    if chunk.empty:
        return pd.DataFrame()

    chunk["ts"] = pd.to_datetime(chunk["ts_event"], utc=True)
    chunk = chunk[(chunk["ts"] >= start_ts) & (chunk["ts"] < end_ts)]
    if chunk.empty:
        return pd.DataFrame()

    rename = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    chunk = chunk.rename(columns=rename)
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        chunk[column] = pd.to_numeric(chunk[column], errors="coerce")
    chunk = chunk.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
    chunk = chunk[chunk["Volume"] >= min_volume]
    return chunk[["ts", "symbol", "Open", "High", "Low", "Close", "Volume"]]
