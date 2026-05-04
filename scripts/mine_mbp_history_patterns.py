from __future__ import annotations

import argparse
import re
import zipfile
from io import TextIOWrapper
from pathlib import Path

import pandas as pd
import zstandard as zstd

from tradingagents.backtesting.short_patterns import evaluate_strategies
from tradingagents.dataflows.databento import _tick_zip_path


READ_COLUMNS = [
    "ts_event",
    "price",
    "size",
    "bid_px_00",
    "ask_px_00",
    "bid_sz_00",
    "ask_sz_00",
    "symbol",
]


def _source_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{path.resolve()}:{stat.st_size}:{int(stat.st_mtime)}"


def _available_mbp_members(path: Path, start_date: str | None, end_date: str | None) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        members = []
        for name in archive.namelist():
            match = re.fullmatch(r"glbx-mdp3-(\d{8})\.mbp-1\.csv\.zst", name)
            if not match:
                continue
            date = f"{match.group(1)[:4]}-{match.group(1)[4:6]}-{match.group(1)[6:]}"
            if start_date and date < start_date:
                continue
            if end_date and date >= end_date:
                continue
            members.append(name)
    return sorted(members)


def _aggregate_chunk(chunk: pd.DataFrame, symbol: str) -> pd.DataFrame:
    chunk = chunk[chunk["symbol"].str.upper() == symbol.upper()].copy()
    if chunk.empty:
        return pd.DataFrame()

    for column in ["price", "size", "bid_px_00", "ask_px_00", "bid_sz_00", "ask_sz_00"]:
        chunk[column] = pd.to_numeric(chunk[column], errors="coerce")
    chunk["ts_event"] = pd.to_datetime(chunk["ts_event"], utc=True, errors="coerce")
    chunk = chunk.dropna(subset=["ts_event", "price", "bid_px_00", "ask_px_00", "bid_sz_00", "ask_sz_00"])
    if chunk.empty:
        return pd.DataFrame()

    chunk["mid_price"] = (chunk["bid_px_00"] + chunk["ask_px_00"]) / 2
    chunk["spread"] = chunk["ask_px_00"] - chunk["bid_px_00"]
    depth = chunk["bid_sz_00"] + chunk["ask_sz_00"]
    chunk["imbalance"] = (chunk["bid_sz_00"] - chunk["ask_sz_00"]) / depth.replace(0, pd.NA)
    chunk["depth"] = depth

    return (
        chunk.set_index("ts_event")
        .resample("1min")
        .agg(
            Open=("price", "first"),
            High=("price", "max"),
            Low=("price", "min"),
            Close=("price", "last"),
            Volume=("size", "sum"),
            mid_price=("mid_price", "last"),
            spread_mean=("spread", "mean"),
            imbalance_mean=("imbalance", "mean"),
            imbalance_last=("imbalance", "last"),
            depth_mean=("depth", "mean"),
            quote_count=("price", "count"),
        )
        .dropna(subset=["Open", "High", "Low", "Close"])
        .reset_index()
        .rename(columns={"ts_event": "ts"})
    )


def _merge_minute_groups(groups: list[pd.DataFrame]) -> pd.DataFrame:
    if not groups:
        return pd.DataFrame()
    data = pd.concat(groups, ignore_index=True).sort_values("ts")
    return (
        data.groupby("ts", as_index=False)
        .agg(
            Open=("Open", "first"),
            High=("High", "max"),
            Low=("Low", "min"),
            Close=("Close", "last"),
            Volume=("Volume", "sum"),
            mid_price=("mid_price", "last"),
            spread_mean=("spread_mean", "mean"),
            imbalance_mean=("imbalance_mean", "mean"),
            imbalance_last=("imbalance_last", "last"),
            depth_mean=("depth_mean", "mean"),
            quote_count=("quote_count", "sum"),
        )
        .sort_values("ts")
        .reset_index(drop=True)
    )


def _member_date(member: str) -> str:
    match = re.fullmatch(r"glbx-mdp3-(\d{8})\.mbp-1\.csv\.zst", member)
    if not match:
        raise ValueError(f"Unexpected MBP member name: {member}")
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def _member_cache_file(cache_dir: Path, symbol: str, member: str, source_fingerprint: str) -> Path:
    source_suffix = str(abs(hash(source_fingerprint)))
    return cache_dir / f"{symbol.upper()}-{_member_date(member)}-{source_suffix}.pkl"


def _build_member_features(
    archive: zipfile.ZipFile,
    member: str,
    symbol: str,
    cache_dir: Path,
    source_fingerprint: str,
    force: bool,
) -> pd.DataFrame:
    cache_file = _member_cache_file(cache_dir, symbol, member, source_fingerprint)
    if cache_file.exists() and not force:
        day = pd.read_pickle(cache_file)
        print(f"{member}: {len(day)} minute bars (cached)")
        return day

    chunk_groups = []
    with archive.open(member) as compressed:
        stream = zstd.ZstdDecompressor().stream_reader(compressed)
        text_stream = TextIOWrapper(stream, encoding="utf-8")
        for chunk in pd.read_csv(text_stream, usecols=READ_COLUMNS, chunksize=250_000):
            aggregated = _aggregate_chunk(chunk, symbol)
            if not aggregated.empty:
                chunk_groups.append(aggregated)
    day = _merge_minute_groups(chunk_groups)
    cache_dir.mkdir(parents=True, exist_ok=True)
    day.to_pickle(cache_file)
    print(f"{member}: {len(day)} minute bars")
    return day


def build_mbp_minute_features(
    symbol: str,
    start_date: str | None,
    end_date: str | None,
    cache_path: Path,
    day_cache_dir: Path,
    force: bool = False,
) -> pd.DataFrame:
    tick_path = _tick_zip_path()
    source_fingerprint = _source_fingerprint(tick_path)
    cache_key = f"{symbol.upper()}|{start_date or ''}|{end_date or ''}|{source_fingerprint}"
    if cache_path.exists() and not force:
        cache = pd.read_pickle(cache_path)
        cached = cache.get(cache_key)
        if isinstance(cached, pd.DataFrame) and not cached.empty:
            return cached
    else:
        cache = {}

    members = _available_mbp_members(tick_path, start_date, end_date)
    if not members:
        raise SystemExit("No MBP members found for requested date range.")

    day_frames = []
    with zipfile.ZipFile(tick_path) as archive:
        for member in members:
            day = _build_member_features(archive, member, symbol, day_cache_dir, source_fingerprint, force)
            if not day.empty:
                day_frames.append(day)

    features = _merge_minute_groups(day_frames)
    if features.empty:
        raise SystemExit(f"No MBP-derived minute features found for {symbol}.")
    features["Date"] = features["ts"]
    features["return_1m"] = features["Close"].pct_change()
    features["vwap"] = (features["Close"] * features["Volume"]).cumsum() / features["Volume"].replace(0, pd.NA).cumsum()
    features["minute_of_day"] = features["ts"].dt.hour * 60 + features["ts"].dt.minute

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache[cache_key] = features
    pd.to_pickle(cache, cache_path)
    return features


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine strategies over the full local Databento MBP history.")
    parser.add_argument("--symbol", default="NQM6")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--min-trades", type=int, default=50)
    parser.add_argument("--output", default=".tmp/mbp-history-patterns.csv")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--day-cache-dir", default=".tmp/mbp-minute-day-cache")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    features = build_mbp_minute_features(
        args.symbol,
        args.start_date,
        args.end_date,
        Path(args.features_cache),
        Path(args.day_cache_dir),
        force=args.force,
    )
    results, _ = evaluate_strategies(features, min_trades=args.min_trades)
    if results.empty:
        raise SystemExit("No strategy met the minimum trade count.")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path, index=False)
    print(f"Symbol: {args.symbol}")
    print(f"Minutes: {len(features)}")
    print(f"Date range: {features['ts'].min()} to {features['ts'].max()}")
    print(f"Strategies meeting min_trades={args.min_trades}: {len(results)}")
    print(f"Report: {output_path}")
    print()
    print(results.head(args.top).to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
