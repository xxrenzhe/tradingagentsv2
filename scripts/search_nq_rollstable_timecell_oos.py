from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from io import TextIOWrapper
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import zstandard as zstd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BAR_MEMBER = "glbx-mdp3-20100606-20260427.ohlcv-1m.csv.zst"
DEFAULT_SOURCE = ROOT_DIR / "data" / "raw" / "databento" / "GLBX-20260428-YXQY7CP9FT.zip"
DEFAULT_ZST_SOURCE = ROOT_DIR / "data" / "raw" / "databento" / "glbx-mdp3-20100606-20260427.ohlcv-1m.csv.zst"
DEFAULT_CSV_SOURCE = ROOT_DIR / "data" / "raw" / "databento" / "glbx-mdp3-20100606-20260427.ohlcv-1m.csv"
NQ_SYMBOL_RE = re.compile(r"^NQ[HMUZ]\d$")
POINT_VALUE = 20.0
ROUND_TRIP_COST_POINTS = 0.625
BASE_KEY_SETS = ("month/hour", "dow/hour", "month/dow/hour")
FEATURE_KEY_SETS = (
    "hour/mom15_bin",
    "hour/mom60_bin",
    "hour/trend_bin",
    "hour/slope_bin",
    "hour/pos_bin",
    "hour/vol_bin",
    "hour/range_bin",
    "month/hour/mom60_bin",
    "dow/hour/trend_bin",
    "dow/hour/vol_bin",
    "hour/mom15_bin/trend_bin",
    "hour/pos_bin/vol_bin",
)


def parse_years(text: str | Iterable[int]) -> list[int]:
    if not isinstance(text, str):
        return sorted({int(year) for year in text})
    years: set[int] = set()
    for raw_part in text.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            years.update(range(int(start), int(end) + 1))
        else:
            years.add(int(part))
    return sorted(years)


def source_path(raw_source: str | Path = "") -> Path:
    if raw_source:
        return Path(raw_source)
    env_source = os.getenv("DATABENTO_BAR_ZIP")
    if env_source:
        return Path(env_source)
    if DEFAULT_SOURCE.exists():
        return DEFAULT_SOURCE
    if DEFAULT_ZST_SOURCE.exists():
        return DEFAULT_ZST_SOURCE
    return DEFAULT_CSV_SOURCE


def iter_bar_chunks(source: str | Path, chunk_size: int) -> Iterable[pd.DataFrame]:
    path = Path(source)
    read_columns = {"ts_event", "open", "high", "low", "close", "volume", "symbol"}
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            member = BAR_MEMBER if BAR_MEMBER in names else next(name for name in names if name.endswith(".ohlcv-1m.csv.zst"))
            with archive.open(member) as compressed:
                stream = zstd.ZstdDecompressor().stream_reader(compressed)
                text_stream = TextIOWrapper(stream, encoding="utf-8")
                yield from pd.read_csv(
                    text_stream,
                    usecols=lambda column: column in read_columns,
                    chunksize=chunk_size,
                )
        return
    if path.suffix == ".zst":
        with path.open("rb") as compressed:
            stream = zstd.ZstdDecompressor().stream_reader(compressed)
            text_stream = TextIOWrapper(stream, encoding="utf-8")
            yield from pd.read_csv(
                text_stream,
                usecols=lambda column: column in read_columns,
                chunksize=chunk_size,
            )
        return
    yield from pd.read_csv(path, usecols=lambda column: column in read_columns, chunksize=chunk_size)


def normalize_bars(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["ts", "trade_date", "symbol", "Open", "High", "Low", "Close", "Volume"])
    data = frame.rename(
        columns={
            "ts_event": "ts",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    ).copy()
    data["ts"] = pd.to_datetime(data["ts"], utc=True, errors="coerce")
    data["symbol"] = data["symbol"].astype(str)
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["ts", "Open", "High", "Low", "Close", "Volume"])
    if "trade_date" not in data:
        data["trade_date"] = data["ts"].dt.date
    base_columns = ["ts", "trade_date", "symbol", "Open", "High", "Low", "Close", "Volume"]
    raw_columns = {"ts_event", "open", "high", "low", "close", "volume"}
    extra_columns = [column for column in data.columns if column not in set(base_columns) | raw_columns]
    return data[base_columns + extra_columns].sort_values("ts").reset_index(drop=True)


def event_frame(bars: pd.DataFrame) -> pd.DataFrame:
    required = {"ts", "trade_date", "symbol", "Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(bars.columns):
        return normalize_bars(bars)
    frame = bars
    if not pd.api.types.is_datetime64_any_dtype(frame["ts"]):
        frame = frame.copy()
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True, errors="coerce")
    if not frame["ts"].is_monotonic_increasing:
        frame = frame.sort_values("ts").reset_index(drop=True)
    elif not isinstance(frame.index, pd.RangeIndex) or frame.index.start != 0 or frame.index.step != 1:
        frame = frame.reset_index(drop=True)
    return frame


def filter_raw_chunk(
    chunk: pd.DataFrame,
    *,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    min_volume: float,
    symbol_re: re.Pattern[str] = NQ_SYMBOL_RE,
) -> pd.DataFrame:
    if chunk.empty:
        return pd.DataFrame()
    symbols = chunk["symbol"].astype(str)
    data = chunk[symbols.map(lambda value: bool(symbol_re.match(value)))].copy()
    if data.empty:
        return pd.DataFrame()
    data = normalize_bars(data)
    data = data[(data["ts"] >= start_ts) & (data["ts"] < end_ts)]
    data = data[data["Volume"] >= float(min_volume)]
    return data.reset_index(drop=True)


def build_daily_main_from_source(
    *,
    source: str | Path,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    min_volume: float,
    chunk_size: int,
) -> pd.DataFrame:
    volume_rows: list[pd.DataFrame] = []
    for chunk in iter_bar_chunks(source, chunk_size):
        filtered = filter_raw_chunk(chunk, start_ts=start_ts, end_ts=end_ts, min_volume=min_volume)
        if filtered.empty:
            continue
        volume_rows.append(filtered.groupby(["trade_date", "symbol"], as_index=False)["Volume"].sum())
    if not volume_rows:
        raise SystemExit(f"No NQ OHLCV rows found in {source}.")

    daily_volume = pd.concat(volume_rows, ignore_index=True).groupby(["trade_date", "symbol"], as_index=False)["Volume"].sum()
    daily_main = (
        daily_volume.sort_values(["trade_date", "Volume", "symbol"], ascending=[True, False, True])
        .drop_duplicates("trade_date", keep="first")
        .set_index("trade_date")["symbol"]
    )

    selected_chunks: list[pd.DataFrame] = []
    for chunk in iter_bar_chunks(source, chunk_size):
        filtered = filter_raw_chunk(chunk, start_ts=start_ts, end_ts=end_ts, min_volume=min_volume)
        if filtered.empty:
            continue
        selected_symbol = filtered["trade_date"].map(daily_main)
        filtered = filtered[filtered["symbol"].astype(str).eq(selected_symbol.astype(str))].copy()
        if not filtered.empty:
            selected_chunks.append(filtered)
    if not selected_chunks:
        raise SystemExit("Daily-main selection produced no bars.")

    bars = pd.concat(selected_chunks, ignore_index=True)
    return (
        bars.sort_values(["ts", "symbol"])
        .drop_duplicates("ts", keep="first")
        .sort_values("ts")
        .reset_index(drop=True)
    )


def load_rollstable_bars(
    *,
    cache: str | Path,
    source: str | Path,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    min_volume: float,
    chunk_size: int,
) -> pd.DataFrame:
    cache_path = Path(cache)
    if cache_path.exists():
        payload = pd.read_pickle(cache_path)
        data = payload.get("bars", payload.get("features")) if isinstance(payload, dict) else payload
        bars = normalize_bars(data)
        bars = bars[(bars["ts"] >= start_ts) & (bars["ts"] < end_ts)].reset_index(drop=True)
        if not bars.empty:
            return bars

    bars = build_daily_main_from_source(
        source=source,
        start_ts=start_ts,
        end_ts=end_ts,
        min_volume=min_volume,
        chunk_size=chunk_size,
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle(bars, cache_path)
    return bars


def _three_bin(values: pd.Series, *, low: float = -1.0, high: float = 1.0) -> pd.Series:
    return pd.Series(
        np.select([values <= low, values >= high], ["down", "up"], default="mid"),
        index=values.index,
        dtype="object",
    ).where(values.notna(), "na")


def add_causal_feature_bins(bars: pd.DataFrame) -> pd.DataFrame:
    frame = normalize_bars(bars)
    frame["segment_id"] = frame["symbol"].ne(frame["symbol"].shift()).cumsum()
    parts: list[pd.DataFrame] = []
    for _, segment in frame.groupby("segment_id", sort=False):
        part = segment.copy()
        previous_close = part["Close"].shift(1)
        true_range = pd.concat(
            [
                part["High"] - part["Low"],
                (part["High"] - previous_close).abs(),
                (part["Low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr60 = true_range.rolling(60, min_periods=20).mean().replace(0, np.nan)
        ema20 = part["Close"].ewm(span=20, adjust=False).mean()
        ema60 = part["Close"].ewm(span=60, adjust=False).mean()
        high120 = part["High"].rolling(120, min_periods=30).max()
        low120 = part["Low"].rolling(120, min_periods=30).min()
        width120 = (high120 - low120).replace(0, np.nan)
        vol_median = part["Volume"].rolling(60, min_periods=20).median().replace(0, np.nan)

        part["mom15_bin"] = _three_bin((part["Close"] - part["Close"].shift(15)) / atr60)
        part["mom60_bin"] = _three_bin((part["Close"] - part["Close"].shift(60)) / atr60)
        part["trend_bin"] = _three_bin((ema20 - ema60) / atr60, low=-0.6, high=0.6)
        part["slope_bin"] = _three_bin((ema20 - ema20.shift(10)) / atr60, low=-0.25, high=0.25)
        position = (part["Close"] - low120) / width120
        part["pos_bin"] = pd.Series(
            np.select([position <= 0.33, position >= 0.67], ["low", "high"], default="mid"),
            index=part.index,
            dtype="object",
        ).where(position.notna(), "na")
        volume_ratio = part["Volume"] / vol_median
        part["vol_bin"] = pd.Series(
            np.select([volume_ratio <= 0.75, volume_ratio >= 1.50], ["low", "high"], default="mid"),
            index=part.index,
            dtype="object",
        ).where(volume_ratio.notna(), "na")
        range_ratio = (part["High"] - part["Low"]) / atr60
        part["range_bin"] = pd.Series(
            np.select([range_ratio <= 0.50, range_ratio >= 1.50], ["low", "high"], default="mid"),
            index=part.index,
            dtype="object",
        ).where(range_ratio.notna(), "na")
        parts.append(part)
    return pd.concat(parts, ignore_index=True, sort=False).drop(columns=["segment_id"], errors="ignore")


def session_mask(minutes: np.ndarray, session: str) -> np.ndarray:
    if session == "all":
        return np.ones(len(minutes), dtype=bool)
    if session == "ldn_ny":
        return (minutes >= 7 * 60) & (minutes < 20 * 60)
    if session == "us_rth":
        return (minutes >= 13 * 60 + 30) & (minutes < 20 * 60)
    if session == "us_late":
        return (minutes >= 20 * 60) & (minutes < 23 * 60)
    if session == "ict_silver":
        return (
            ((minutes >= 7 * 60) & (minutes < 9 * 60))
            | ((minutes >= 14 * 60) & (minutes < 16 * 60))
            | ((minutes >= 18 * 60) & (minutes < 20 * 60))
        )
    raise ValueError(f"unsupported session: {session}")


def build_events(
    bars: pd.DataFrame,
    *,
    step: int,
    hold: int,
    session: str,
    key_columns: list[str],
    prevent_overlap: bool = True,
) -> pd.DataFrame:
    frame = event_frame(bars)
    missing = sorted(set(key_columns) - set(frame.columns) - {"month", "dow", "hour", "minute"})
    if missing:
        raise ValueError(f"bars are missing key columns: {missing}")

    ts = frame["ts"].reset_index(drop=True)
    minutes = ts.dt.hour.to_numpy() * 60 + ts.dt.minute.to_numpy()
    minute_in_hour = ts.dt.minute.to_numpy()
    indexes = np.flatnonzero(session_mask(minutes, session) & ((minute_in_hour % int(step)) == 0))
    indexes = indexes[indexes + int(hold) < len(frame)]
    if len(indexes):
        symbols = frame["symbol"].astype(str).to_numpy()
        signal_ts = ts.iloc[indexes].reset_index(drop=True)
        entry_ts = ts.iloc[indexes + 1].reset_index(drop=True)
        exit_ts = ts.iloc[indexes + int(hold)].reset_index(drop=True)
        valid = (symbols[indexes] == symbols[indexes + 1]) & (symbols[indexes] == symbols[indexes + int(hold)])
        valid &= ((entry_ts - signal_ts) == pd.Timedelta(minutes=1)).to_numpy()
        valid &= ((exit_ts - signal_ts) == pd.Timedelta(minutes=int(hold))).to_numpy()
        indexes = indexes[valid]

    if prevent_overlap and len(indexes):
        selected: list[int] = []
        next_available = 0
        for index in indexes:
            if int(index) + 1 < next_available:
                continue
            selected.append(int(index))
            next_available = int(index) + int(hold) + 1
        indexes = np.asarray(selected, dtype=int)

    opens = frame["Open"].to_numpy(dtype=float)
    closes = frame["Close"].to_numpy(dtype=float)
    event = pd.DataFrame(
        {
            "signal_index": indexes,
            "entry_index": indexes + 1,
            "exit_index": indexes + int(hold),
            "signal_ts": ts.iloc[indexes].to_numpy(),
            "entry_ts": ts.iloc[indexes + 1].to_numpy(),
            "exit_ts": ts.iloc[indexes + int(hold)].to_numpy(),
            "symbol": frame["symbol"].astype(str).to_numpy()[indexes],
            "year": ts.iloc[indexes].dt.year.to_numpy(),
            "month": ts.iloc[indexes].dt.month.to_numpy(),
            "dow": ts.iloc[indexes].dt.dayofweek.to_numpy(),
            "hour": ts.iloc[indexes].dt.hour.to_numpy(),
            "minute": ts.iloc[indexes].dt.minute.to_numpy(),
            "entry_price": opens[indexes + 1],
            "exit_price": closes[indexes + int(hold)],
            "gross_long": closes[indexes + int(hold)] - opens[indexes + 1],
        }
    )
    for column in key_columns:
        if column not in event and column in frame:
            event[column] = frame[column].iloc[indexes].to_numpy()
    return event


def key_tuple(raw_key: Any) -> tuple[Any, ...]:
    return raw_key if isinstance(raw_key, tuple) else (raw_key,)


def train_action_map(
    events: pd.DataFrame,
    *,
    key_columns: list[str],
    train_years: list[int],
    min_cell: int,
    min_train_net: float = 0.0,
    min_train_pf: float = 0.0,
    min_train_avg: float = -1_000_000.0,
    min_train_positive_year_rate: float = 0.0,
) -> dict[tuple[Any, ...], int]:
    train = events[events["year"].isin(train_years)].copy()
    actions: dict[tuple[Any, ...], int] = {}
    if train.empty:
        return actions
    for raw_key, group in train.groupby(key_columns, dropna=False):
        key = key_tuple(raw_key)
        if len(group) < int(min_cell):
            continue
        best_direction = 0
        best_metrics: dict[str, float] | None = None
        for direction in (1, -1):
            net = group["gross_long"].astype(float) * direction - ROUND_TRIP_COST_POINTS
            wins = net[net > 0]
            losses = net[net < 0]
            gross_loss = float(-losses.sum())
            yearly = net.groupby(group["year"]).sum().reindex(train_years, fill_value=0.0)
            metrics = {
                "net": float(net.sum()),
                "pf": float(wins.sum() / gross_loss) if gross_loss else (999.0 if float(wins.sum()) > 0.0 else 0.0),
                "avg": float(net.mean()) if len(net) else 0.0,
                "positive_year_rate": float((yearly > 0.0).mean()) if not yearly.empty else 0.0,
            }
            if best_metrics is None or metrics["net"] > best_metrics["net"]:
                best_direction = direction
                best_metrics = metrics
        if best_metrics is None:
            continue
        if best_metrics["net"] <= float(min_train_net):
            continue
        if best_metrics["pf"] < float(min_train_pf):
            continue
        if best_metrics["avg"] < float(min_train_avg):
            continue
        if best_metrics["positive_year_rate"] < float(min_train_positive_year_rate):
            continue
        actions[key] = int(best_direction)
    return actions


def apply_actions(
    events: pd.DataFrame,
    actions: dict[tuple[Any, ...], int],
    *,
    key_columns: list[str],
    test_years: list[int],
    label: str,
) -> pd.DataFrame:
    if events.empty or not actions:
        return pd.DataFrame()
    keys = [tuple(row) for row in events[key_columns].itertuples(index=False, name=None)]
    in_action = np.asarray([key in actions for key in keys], dtype=bool)
    in_test = events["year"].isin(test_years).to_numpy(dtype=bool)
    mask = in_action & in_test
    selected = events.loc[mask].copy()
    if selected.empty:
        return selected
    selected_keys = [tuple(row) for row in selected[key_columns].itertuples(index=False, name=None)]
    signs = np.asarray([actions[key] for key in selected_keys], dtype=int)
    selected["direction"] = signs
    selected["gross_points"] = selected["gross_long"].to_numpy(dtype=float) * signs
    selected["net_points"] = selected["gross_points"] - ROUND_TRIP_COST_POINTS
    selected["net_dollars"] = selected["net_points"] * POINT_VALUE
    selected["strategy_label"] = label
    selected["rule_key"] = selected[key_columns].astype(str).agg("-".join, axis=1)
    return selected.sort_values("entry_ts").reset_index(drop=True)


def summarize_trades(trades: pd.DataFrame, *, test_years: list[int], annual_floor: int) -> dict[str, Any]:
    if trades.empty:
        return {
            "trades": 0,
            "net": 0.0,
            "pf": 0.0,
            "wr": 0.0,
            "dd": 0.0,
            "net_to_drawdown": 0.0,
            "mincnt": 0,
            "minnet": 0.0,
            "gate": False,
            "positive_year_rate": 0.0,
        }
    data = trades.sort_values("entry_ts").copy()
    net = pd.to_numeric(data["net_points"], errors="coerce").fillna(0.0)
    wins = net[net > 0]
    losses = net[net < 0]
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    years = pd.to_datetime(data["entry_ts"], utc=True).dt.year
    yearly_net = net.groupby(years).sum().reindex(test_years, fill_value=0.0)
    yearly_count = net.groupby(years).size().reindex(test_years, fill_value=0)
    gross_loss = float(-losses.sum())
    max_dd = float(drawdown.max()) if not drawdown.empty else 0.0
    return {
        "trades": int(len(data)),
        "net": float(net.sum()),
        "pf": float(wins.sum() / gross_loss) if gross_loss else (999.0 if float(wins.sum()) > 0.0 else 0.0),
        "wr": float((net > 0).mean()),
        "dd": max_dd,
        "net_to_drawdown": float(net.sum() / max_dd) if max_dd else (999.0 if float(net.sum()) > 0.0 else 0.0),
        "mincnt": int(yearly_count.min()) if not yearly_count.empty else 0,
        "minnet": float(yearly_net.min()) if not yearly_net.empty else 0.0,
        "gate": bool((yearly_count >= int(annual_floor)).all() and (yearly_net > 0.0).all()),
        "positive_year_rate": float((yearly_net > 0.0).mean()) if not yearly_net.empty else 0.0,
    }


def search_timecells(
    bars: pd.DataFrame,
    *,
    train_years: list[int],
    test_years: list[int],
    steps: list[int],
    holds: list[int],
    sessions: list[str],
    key_sets: list[str],
    min_cells: list[int],
    annual_floor: int,
    min_train_net: float = 0.0,
    min_train_pfs: list[float] | None = None,
    min_train_avgs: list[float] | None = None,
    min_train_positive_year_rates: list[float] | None = None,
    min_profit_factor: float = 1.25,
    min_net_to_drawdown: float = 5.0,
    prevent_overlap: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[tuple[Any, ...], int]]:
    rows: list[dict[str, Any]] = []
    best_trades = pd.DataFrame()
    best_actions: dict[tuple[Any, ...], int] = {}
    best_sort: tuple[float, ...] | None = None
    key_columns_list = [key_set.split("/") for key_set in key_sets]
    train_pf_values = min_train_pfs or [0.0]
    train_avg_values = min_train_avgs or [-1_000_000.0]
    train_pos_year_values = min_train_positive_year_rates or [0.0]
    needs_features = any(any(column.endswith("_bin") for column in columns) for columns in key_columns_list)
    prepared = add_causal_feature_bins(bars) if needs_features else normalize_bars(bars)

    for step in steps:
        for hold in holds:
            for session in sessions:
                unique_key_columns = sorted({column for columns in key_columns_list for column in columns})
                try:
                    events = build_events(
                        prepared,
                        step=int(step),
                        hold=int(hold),
                        session=session,
                        key_columns=unique_key_columns,
                        prevent_overlap=prevent_overlap,
                    )
                except ValueError:
                    continue
                if events.empty:
                    continue
                for key_columns in key_columns_list:
                    key_name = "/".join(key_columns)
                    for min_cell in min_cells:
                        for min_train_pf in train_pf_values:
                            for min_train_avg in train_avg_values:
                                for min_train_pos_year in train_pos_year_values:
                                    actions = train_action_map(
                                        events,
                                        key_columns=key_columns,
                                        train_years=train_years,
                                        min_cell=int(min_cell),
                                        min_train_net=min_train_net,
                                        min_train_pf=float(min_train_pf),
                                        min_train_avg=float(min_train_avg),
                                        min_train_positive_year_rate=float(min_train_pos_year),
                                    )
                                    label = (
                                        f"oos{train_years[0]}_{train_years[-1]}_step{int(step)}_hold{int(hold)}_"
                                        f"{session}_mc{int(min_cell)}"
                                        f"_tpf{float(min_train_pf):g}_tavg{float(min_train_avg):g}_"
                                        f"tpos{float(min_train_pos_year):g}_{key_name.replace('/', '-')}"
                                    )
                                    trades = apply_actions(
                                        events,
                                        actions,
                                        key_columns=key_columns,
                                        test_years=test_years,
                                        label=label,
                                    )
                                    summary = summarize_trades(trades, test_years=test_years, annual_floor=annual_floor)
                                    quality_gate = bool(
                                        summary["gate"]
                                        and summary["pf"] >= float(min_profit_factor)
                                        and summary["net_to_drawdown"] >= float(min_net_to_drawdown)
                                    )
                                    row = {
                                        "label": label,
                                        "step": int(step),
                                        "hold": int(hold),
                                        "session": session,
                                        "keys": key_name,
                                        "min_cell": int(min_cell),
                                        "min_train_pf": float(min_train_pf),
                                        "min_train_avg": float(min_train_avg),
                                        "min_train_positive_year_rate": float(min_train_pos_year),
                                        "cells": int(len(actions)),
                                        "quality_gate": quality_gate,
                                        **summary,
                                    }
                                    rows.append(row)
                                    sort_key = (
                                        float(quality_gate),
                                        float(summary["gate"]),
                                        float(summary["net"]),
                                        float(summary["pf"]),
                                        float(summary["net_to_drawdown"]),
                                        float(summary["mincnt"]),
                                    )
                                    if best_sort is None or sort_key > best_sort:
                                        best_sort = sort_key
                                        best_trades = trades
                                        best_actions = actions

    search = pd.DataFrame(rows)
    if search.empty:
        return search, best_trades, best_actions
    search = search.sort_values(
        ["quality_gate", "gate", "net", "pf", "net_to_drawdown", "mincnt"],
        ascending=[False, False, False, False, False, False],
    ).reset_index(drop=True)
    return search, best_trades, best_actions


def build_key_sets(args: argparse.Namespace) -> list[str]:
    key_sets = list(args.key_sets)
    if args.enable_feature_bins:
        key_sets.extend(list(args.feature_key_sets)[: int(args.max_feature_key_sets)])
    seen: set[str] = set()
    output: list[str] = []
    for key_set in key_sets:
        normalized = "/".join(part.strip() for part in str(key_set).split("/") if part.strip())
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def write_outputs(args: argparse.Namespace) -> dict[str, Any]:
    train_years = parse_years(args.train_years)
    test_years = parse_years(args.test_years)
    if not train_years or not test_years:
        raise SystemExit("Both --train-years and --test-years must contain at least one year.")
    start_ts = pd.Timestamp(f"{min(train_years + test_years)}-01-01", tz="UTC")
    end_ts = pd.Timestamp(f"{max(train_years + test_years) + 1}-01-01", tz="UTC")
    bars = load_rollstable_bars(
        cache=args.cache,
        source=source_path(args.source),
        start_ts=start_ts,
        end_ts=end_ts,
        min_volume=args.min_volume,
        chunk_size=args.chunk_size,
    )
    key_sets = build_key_sets(args)
    search, best_trades, best_actions = search_timecells(
        bars,
        train_years=train_years,
        test_years=test_years,
        steps=[int(value) for value in args.steps],
        holds=[int(value) for value in args.holds],
        sessions=list(args.sessions),
        key_sets=key_sets,
        min_cells=[int(value) for value in args.min_cells],
        annual_floor=int(args.annual_floor),
        min_train_net=float(args.min_train_net),
        min_train_pfs=[float(value) for value in args.min_train_pfs],
        min_train_avgs=[float(value) for value in args.min_train_avgs],
        min_train_positive_year_rates=[float(value) for value in args.min_train_positive_year_rates],
        min_profit_factor=float(args.min_profit_factor),
        min_net_to_drawdown=float(args.min_net_to_drawdown),
        prevent_overlap=not args.allow_overlap,
    )

    search_path = Path(args.search_output)
    trades_path = Path(args.trades_output)
    action_path = Path(args.action_output)
    for output_path in [search_path, trades_path, action_path]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    search.to_csv(search_path, index=False)
    best_trades.to_csv(trades_path, index=False)

    top = search.iloc[0].to_dict() if not search.empty else {}
    action_payload = {
        "top": top,
        "train_years": train_years,
        "test_years": test_years,
        "actions": [
            {"key": list(key), "direction": int(direction)}
            for key, direction in sorted(best_actions.items(), key=lambda item: str(item[0]))
        ],
    }
    action_path.write_text(json.dumps(action_payload, indent=2, ensure_ascii=False, sort_keys=True, default=str), encoding="utf-8")

    summary = {
        "bars": int(len(bars)),
        "bar_start": str(bars["ts"].min()) if not bars.empty else "",
        "bar_end": str(bars["ts"].max()) if not bars.empty else "",
        "train_years": train_years,
        "test_years": test_years,
        "search_rows": int(len(search)),
        "best_trades": int(len(best_trades)),
        "search_output": str(search_path),
        "trades_output": str(trades_path),
        "action_output": str(action_path),
        "top": top,
    }
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Strict OOS roll-stable NQ timecell direction search.")
    parser.add_argument("--source", default="")
    parser.add_argument("--cache", default=".tmp/nq-2010-2025-daily-main-bars-cache.pkl")
    parser.add_argument("--search-output", default=".tmp/nq-2010train-2020test-timecell-search.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-2010train-2020test-timecell-best-trades.csv")
    parser.add_argument("--action-output", default=".tmp/nq-2010train-2020test-timecell-actions.json")
    parser.add_argument("--train-years", default="2010-2019")
    parser.add_argument("--test-years", default="2020-2025")
    parser.add_argument("--steps", type=int, nargs="+", default=[5, 10, 15, 30])
    parser.add_argument("--holds", type=int, nargs="+", default=[30, 60, 90, 120])
    parser.add_argument("--sessions", nargs="+", default=["all", "ict_silver", "ldn_ny", "us_late", "us_rth"])
    parser.add_argument("--key-sets", nargs="+", default=list(BASE_KEY_SETS))
    parser.add_argument("--enable-feature-bins", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--feature-key-sets", nargs="+", default=list(FEATURE_KEY_SETS))
    parser.add_argument("--max-feature-key-sets", type=int, default=12)
    parser.add_argument("--min-cells", type=int, nargs="+", default=[20, 50, 100, 200])
    parser.add_argument("--min-train-net", type=float, default=0.0)
    parser.add_argument("--min-train-pfs", type=float, nargs="+", default=[0.0])
    parser.add_argument("--min-train-avgs", type=float, nargs="+", default=[-1_000_000.0])
    parser.add_argument("--min-train-positive-year-rates", type=float, nargs="+", default=[0.0])
    parser.add_argument("--annual-floor", type=int, default=1001)
    parser.add_argument("--min-profit-factor", type=float, default=1.25)
    parser.add_argument("--min-net-to-drawdown", type=float, default=5.0)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--allow-overlap", action=argparse.BooleanOptionalAction, default=False)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    print(json.dumps(write_outputs(args), indent=2, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
