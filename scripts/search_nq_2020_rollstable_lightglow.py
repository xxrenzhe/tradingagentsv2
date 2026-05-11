from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from io import TextIOWrapper
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import zstandard as zstd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from backtest_lightglow_nq_bars import build_lightglow_signals, build_time_exit_trades
from backtest_lightglow_nq_bars import LightglowCandidate
from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.dataflows.databento import _bar_zip_path


BAR_MEMBER = "glbx-mdp3-20100606-20260427.ohlcv-1m.csv.zst"
NQ_SYMBOL_RE = re.compile(r"^NQ[HMUZ]\d$")
FULL_YEARS = list(range(2020, 2026))
POINT_VALUE = 20.0


@dataclass(frozen=True)
class PoolSpec:
    signal: str
    hold_bars: int
    session: str

    @property
    def name(self) -> str:
        return f"{self.signal}_1m_{self.session}_hold{self.hold_bars}m"


def _iter_bar_chunks(source: Path, chunk_size: int):
    usecols = ["ts_event", "open", "high", "low", "close", "volume", "symbol"]
    with zipfile.ZipFile(source) as archive:
        member = BAR_MEMBER if BAR_MEMBER in archive.namelist() else archive.namelist()[0]
        with archive.open(member) as compressed:
            stream = zstd.ZstdDecompressor().stream_reader(compressed)
            text_stream = TextIOWrapper(stream, encoding="utf-8")
            yield from pd.read_csv(text_stream, usecols=usecols, chunksize=chunk_size)


def load_daily_main_nq_bars(args: argparse.Namespace) -> pd.DataFrame:
    cache_path = Path(args.cache)
    source = _bar_zip_path()
    stat = source.stat()
    cache_key = {
        "source": str(source.resolve()),
        "size": stat.st_size,
        "mtime": int(stat.st_mtime),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "min_volume": float(args.min_volume),
        "construction": "utc_daily_top_volume_symbol",
    }
    if cache_path.exists():
        payload = pd.read_pickle(cache_path)
        if isinstance(payload, dict) and payload.get("key") == cache_key:
            return payload["features"].copy()

    start_ts = pd.Timestamp(args.start_date, tz="UTC")
    end_ts = pd.Timestamp(args.end_date, tz="UTC")
    volume_rows: list[pd.DataFrame] = []
    for chunk in _iter_bar_chunks(source, args.chunk_size):
        filtered = _filter_chunk(chunk, start_ts, end_ts, args.min_volume)
        if filtered.empty:
            continue
        filtered["trade_date"] = filtered["ts"].dt.date
        volume_rows.append(filtered.groupby(["trade_date", "symbol"], as_index=False)["Volume"].sum())
    if not volume_rows:
        raise SystemExit(f"No NQ rows found in {source} for {args.start_date}..{args.end_date}.")

    daily_volume = pd.concat(volume_rows, ignore_index=True).groupby(["trade_date", "symbol"], as_index=False)["Volume"].sum()
    daily_main = (
        daily_volume.sort_values(["trade_date", "Volume", "symbol"], ascending=[True, False, True])
        .drop_duplicates("trade_date", keep="first")
        .set_index("trade_date")["symbol"]
    )
    selected_chunks: list[pd.DataFrame] = []
    for chunk in _iter_bar_chunks(source, args.chunk_size):
        filtered = _filter_chunk(chunk, start_ts, end_ts, args.min_volume)
        if filtered.empty:
            continue
        filtered["trade_date"] = filtered["ts"].dt.date
        wanted = filtered["trade_date"].map(daily_main)
        filtered = filtered[filtered["symbol"].astype(str).eq(wanted.astype(str))].copy()
        if not filtered.empty:
            selected_chunks.append(filtered)
    if not selected_chunks:
        raise SystemExit("Daily-main symbol selection produced no bars.")

    bars = pd.concat(selected_chunks, ignore_index=True)
    bars = bars.sort_values(["ts", "symbol"]).drop_duplicates("ts", keep="first").sort_values("ts").reset_index(drop=True)
    features = prepare_features(bars)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle({"key": cache_key, "features": features}, cache_path)
    return features.copy()


def _filter_chunk(
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
    chunk = chunk.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        chunk[column] = pd.to_numeric(chunk[column], errors="coerce")
    chunk = chunk.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
    chunk = chunk[chunk["Volume"] >= min_volume]
    return chunk[["ts", "symbol", "Open", "High", "Low", "Close", "Volume"]]


def prepare_features(bars: pd.DataFrame) -> pd.DataFrame:
    features = bars.copy()
    features["ts"] = pd.to_datetime(features["ts"], utc=True)
    features = features.sort_values("ts").reset_index(drop=True)
    features["symbol_change"] = features["symbol"].astype(str).ne(features["symbol"].astype(str).shift())
    features["segment_id"] = features["symbol_change"].cumsum()
    parts = []
    for _, segment in features.groupby("segment_id", sort=False):
        part = segment.copy()
        part["trade_date"] = part["ts"].dt.date
        part["minute_of_day"] = part["ts"].dt.hour * 60 + part["ts"].dt.minute
        part["return_1m"] = part["Close"].pct_change()
        part["range_points"] = part["High"] - part["Low"]
        part["body_points"] = (part["Close"] - part["Open"]).abs()
        part["momentum_5"] = part["Close"].pct_change(5)
        part["momentum_15"] = part["Close"].pct_change(15)
        part["momentum_60"] = part["Close"].pct_change(60)
        part["vol_30"] = part["return_1m"].rolling(30).std()
        part["vol_120"] = part["return_1m"].rolling(120).std()
        rolling_mean = part["Close"].rolling(30).mean()
        rolling_std = part["Close"].rolling(30).std().replace(0, np.nan)
        part["z_30"] = (part["Close"] - rolling_mean) / rolling_std
        part["range_mean_30"] = part["range_points"].rolling(30).mean()
        volume_std = part["Volume"].rolling(60).std().replace(0, np.nan)
        part["volume_z_60"] = (part["Volume"] - part["Volume"].rolling(60).mean()) / volume_std
        previous_close = part["Close"].shift(1)
        true_range = pd.concat(
            [
                part["High"] - part["Low"],
                (part["High"] - previous_close).abs(),
                (part["Low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        part["atr_30"] = true_range.rolling(30, min_periods=10).mean()
        part["atr_120"] = true_range.rolling(120, min_periods=30).mean()
        part["ema20"] = part["Close"].ewm(span=20, adjust=False).mean()
        part["ema60"] = part["Close"].ewm(span=60, adjust=False).mean()
        part["ema200"] = part["Close"].ewm(span=200, adjust=False).mean()
        part["ema20_slope_10"] = part["ema20"] - part["ema20"].shift(10)
        part["trend_ema20_60"] = part["ema20"] - part["ema60"]
        part["trend_ema60_200"] = part["ema60"] - part["ema200"]
        part["range_atr"] = part["range_points"] / part["atr_30"].replace(0, np.nan)
        for lookback in [45, 90, 180]:
            high = part["High"].rolling(lookback, min_periods=lookback).max().shift(1)
            low = part["Low"].rolling(lookback, min_periods=lookback).min().shift(1)
            width = high - low
            part[f"box{lookback}_high"] = high
            part[f"box{lookback}_low"] = low
            part[f"box{lookback}_width_atr"] = width / part["atr_120"].replace(0, np.nan)
            part[f"box{lookback}_pos"] = (part["Close"] - low) / width.replace(0, np.nan)
        parts.append(part)
    return pd.concat(parts, ignore_index=True, sort=False).dropna(subset=["Close"]).reset_index(drop=True)


def build_segmented_lightglow(features: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for _, segment in features.groupby("segment_id", sort=False):
        if len(segment) < 300:
            parts.append(segment.copy())
            continue
        parts.append(build_lightglow_signals(segment.copy()))
    return pd.concat(parts, ignore_index=True, sort=False).sort_values("ts").reset_index(drop=True)


def session_mask(frame: pd.DataFrame, session: str) -> pd.Series:
    minute = frame["minute_of_day"]
    if session == "all":
        return pd.Series(True, index=frame.index)
    if session == "europe":
        return (minute >= 7 * 60) & (minute < 13 * 60 + 30)
    if session == "us_rth":
        return (minute >= 13 * 60 + 30) & (minute < 20 * 60)
    if session == "us_late":
        return (minute >= 20 * 60) & (minute < 23 * 60)
    if session == "asia":
        return (minute < 7 * 60) | (minute >= 23 * 60)
    if session == "ldn_ny":
        return (minute >= 7 * 60) & (minute < 20 * 60)
    raise ValueError(f"unknown session: {session}")


def build_pool_trades(frame: pd.DataFrame, spec: PoolSpec, costs: BacktestCosts) -> pd.DataFrame:
    signal = pd.to_numeric(frame[spec.signal], errors="coerce").fillna(0).astype(int)
    signal = signal.where(session_mask(frame, spec.session), 0)
    signal = signal.where(signal != signal.shift(1), 0)
    entry_indexes = np.flatnonzero(signal.to_numpy() != 0)
    if len(entry_indexes) == 0:
        return pd.DataFrame()
    candidate = LightglowCandidate(
        signal=spec.signal,
        timeframe_minutes=1,
        session=spec.session,
        hold_bars=spec.hold_bars,
        direction_mode="native",
        stop_loss_points=None,
        take_profit_points=None,
    )
    trades = build_time_exit_trades(frame, signal, candidate, costs, entry_indexes=entry_indexes)
    if trades.empty:
        return trades
    trades = trades.copy()
    trades["pool"] = spec.name
    trades["year"] = pd.to_datetime(trades["entry_ts"], utc=True).dt.year
    trades["month"] = pd.to_datetime(trades["entry_ts"], utc=True).dt.month
    trades["dow"] = pd.to_datetime(trades["entry_ts"], utc=True).dt.dayofweek
    trades["hour"] = pd.to_datetime(trades["entry_ts"], utc=True).dt.hour
    return trades[trades["year"].isin(FULL_YEARS)].reset_index(drop=True)


def summarize(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "max_drawdown_points": 0.0,
            "min_full_year_trades": 0,
            "min_full_year_net": 0.0,
            "full_year_gate": False,
        }
    data = trades.sort_values("entry_ts").copy()
    net = pd.to_numeric(data["net_points"], errors="coerce").fillna(0.0)
    wins = net[net > 0]
    losses = net[net < 0]
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    years = pd.to_datetime(data["entry_ts"], utc=True).dt.year
    yearly_net = net.groupby(years).sum().reindex(FULL_YEARS, fill_value=0.0)
    yearly_count = net.groupby(years).size().reindex(FULL_YEARS, fill_value=0)
    return {
        "trades": int(len(data)),
        "net_points": float(net.sum()),
        "profit_factor": float(wins.sum() / -losses.sum()) if len(losses) else (999.0 if len(wins) else 0.0),
        "win_rate": float((net > 0).mean()),
        "expectancy_points": float(net.mean()),
        "max_drawdown_points": float(drawdown.max()) if len(drawdown) else 0.0,
        "min_full_year_trades": int(yearly_count.min()),
        "min_full_year_net": float(yearly_net.min()),
        "full_year_gate": bool((yearly_count >= 1000).all() and (yearly_net > 0).all()),
        "yearly_net": {str(k): float(v) for k, v in yearly_net.items()},
        "yearly_count": {str(k): int(v) for k, v in yearly_count.items()},
    }


def direct_candidate_rows(pool_trades: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows = []
    for name, native in pool_trades.items():
        for action, sign in [("native", 1.0), ("reverse", -1.0)]:
            trades = native.copy()
            trades["base_direction"] = trades["direction"].astype(int)
            trades["direction"] = (trades["base_direction"].to_numpy(dtype=int) * sign).astype(int)
            gross = pd.to_numeric(native["gross_points"], errors="coerce").to_numpy(dtype=float) * sign
            trades["gross_points"] = gross
            trades["net_points"] = gross - 0.625
            stats = summarize(trades)
            rows.append({"pool": name, "action": action, **stats})
    return rows


def choose_cell_actions(
    native: pd.DataFrame,
    *,
    cell_columns: list[str],
    train_years: list[int],
    min_cell_trades: int,
    min_action_net: float,
) -> list[dict[str, Any]]:
    records = []
    data = native.copy()
    for values, group in data.groupby(cell_columns, dropna=False):
        if not isinstance(values, tuple):
            values = (values,)
        if len(group) < min_cell_trades:
            continue
        train = group[group["year"].isin(train_years)]
        if len(train) < max(10, min_cell_trades // 3):
            continue
        native_net = float(train["net_points"].sum())
        reverse_net = float((-train["gross_points"] - 0.625).sum())
        action = "native" if native_net >= reverse_net else "reverse"
        chosen_net = max(native_net, reverse_net)
        if chosen_net < min_action_net:
            continue
        row = {column: value for column, value in zip(cell_columns, values)}
        row.update(
            {
                "action": action,
                "train_net": chosen_net,
                "train_trades": int(len(train)),
                "all_trades": int(len(group)),
            }
        )
        records.append(row)
    records.sort(key=lambda item: (item["train_net"], item["train_trades"]), reverse=True)
    return records


def apply_cell_actions(native: pd.DataFrame, actions: list[dict[str, Any]], cell_columns: list[str], label: str) -> pd.DataFrame:
    if not actions:
        return pd.DataFrame()
    lookup = {
        tuple(action[column] for column in cell_columns): str(action["action"])
        for action in actions
    }
    keys = list(zip(*(native[column] for column in cell_columns)))
    mask = [key in lookup for key in keys]
    selected = native.loc[mask].copy()
    if selected.empty:
        return selected
    selected_keys = list(zip(*(selected[column] for column in cell_columns)))
    selected["action"] = [lookup[key] for key in selected_keys]
    sign = np.where(selected["action"].eq("native"), 1.0, -1.0)
    selected["base_direction"] = selected["direction"].astype(int)
    selected["direction"] = (selected["base_direction"].to_numpy(dtype=int) * sign).astype(int)
    selected["gross_points"] = selected["gross_points"].to_numpy(dtype=float) * sign
    selected["net_points"] = selected["gross_points"] - 0.625
    selected["strategy_label"] = label
    selected["rule_key"] = selected[cell_columns].astype(str).agg("-".join, axis=1)
    return selected.sort_values("entry_ts").reset_index(drop=True)


def seasonal_search(pool_trades: dict[str, pd.DataFrame], args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    rows = []
    trade_frames = []
    action_maps = []
    cell_sets = [
        ["month", "dow"],
        ["month", "hour"],
        ["dow", "hour"],
        ["month", "dow", "hour"],
    ]
    train_sets = {
        "early2020_2021": [2020, 2021],
        "all_full_years": FULL_YEARS,
        "stress2020_2022": [2020, 2021, 2022],
    }
    for pool_name, native in pool_trades.items():
        if native.empty:
            continue
        for train_label, train_years in train_sets.items():
            for cell_columns in cell_sets:
                actions = choose_cell_actions(
                    native,
                    cell_columns=cell_columns,
                    train_years=train_years,
                    min_cell_trades=args.min_cell_trades,
                    min_action_net=args.min_action_net,
                )
                if not actions:
                    continue
                label = f"{pool_name}_{train_label}_{'_'.join(cell_columns)}"
                trades = apply_cell_actions(native, actions, cell_columns, label)
                stats = summarize(trades)
                row = {
                    "label": label,
                    "pool": pool_name,
                    "train_label": train_label,
                    "cell_columns": ",".join(cell_columns),
                    "action_cells": len(actions),
                    **{key: value for key, value in stats.items() if not isinstance(value, dict)},
                }
                rows.append(row)
                if not trades.empty:
                    trade_frames.append(trades)
                    action_maps.append({"label": label, "cell_columns": cell_columns, "actions": actions, "summary": row})
    return (
        pd.DataFrame(rows).sort_values(["full_year_gate", "net_points"], ascending=[False, False]).reset_index(drop=True)
        if rows
        else pd.DataFrame(),
        pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame(),
        action_maps,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Search roll-stable 2020+ NQ Lightglow strategies.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-01-01")
    parser.add_argument("--cache", default=".tmp/nq-2020-daily-main-features-cache.pkl")
    parser.add_argument("--signals-cache", default=".tmp/nq-2020-daily-main-lightglow-cache.pkl")
    parser.add_argument("--direct-output", default=".tmp/nq-2020-rollstable-lightglow-direct.csv")
    parser.add_argument("--seasonal-output", default=".tmp/nq-2020-rollstable-lightglow-seasonal.csv")
    parser.add_argument("--seasonal-trades-output", default=".tmp/nq-2020-rollstable-lightglow-seasonal-trades.csv")
    parser.add_argument("--action-output", default=".tmp/nq-2020-rollstable-lightglow-action-maps.json")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--hold-bars", type=int, nargs="+", default=[1, 2, 3, 5, 10])
    parser.add_argument("--sessions", nargs="+", default=["all", "europe", "us_rth", "us_late", "asia", "ldn_ny"])
    parser.add_argument("--signals", nargs="+", default=[
        "premium_discount_reversal",
        "internal_choch_zone",
        "fvg_zone",
        "equal_level_reversal",
        "internal_choch",
        "internal_bos",
        "swing_choch",
        "swing_bos",
        "fvg",
        "internal_ob_break",
        "swing_ob_break",
    ])
    parser.add_argument("--min-cell-trades", type=int, default=30)
    parser.add_argument("--min-action-net", type=float, default=0.0)
    args = parser.parse_args()

    features = load_daily_main_nq_bars(args)
    signals_cache = Path(args.signals_cache)
    signal_key = {
        "feature_cache": str(Path(args.cache).resolve()),
        "feature_rows": int(len(features)),
        "feature_start": str(features["ts"].min()),
        "feature_end": str(features["ts"].max()),
        "signals": "segmented_lightglow_v1",
    }
    if signals_cache.exists():
        payload = pd.read_pickle(signals_cache)
        if isinstance(payload, dict) and payload.get("key") == signal_key:
            frame = payload["features"].copy()
        else:
            frame = build_segmented_lightglow(features)
            pd.to_pickle({"key": signal_key, "features": frame}, signals_cache)
    else:
        signals_cache.parent.mkdir(parents=True, exist_ok=True)
        frame = build_segmented_lightglow(features)
        pd.to_pickle({"key": signal_key, "features": frame}, signals_cache)

    costs = BacktestCosts()
    pool_trades: dict[str, pd.DataFrame] = {}
    for signal in args.signals:
        if signal not in frame.columns:
            continue
        for hold_bars in args.hold_bars:
            for session in args.sessions:
                spec = PoolSpec(signal=signal, hold_bars=hold_bars, session=session)
                trades = build_pool_trades(frame, spec, costs)
                if not trades.empty:
                    pool_trades[spec.name] = trades

    direct = pd.DataFrame(direct_candidate_rows(pool_trades)).sort_values(
        ["full_year_gate", "net_points"], ascending=[False, False]
    )
    seasonal, seasonal_trades, action_maps = seasonal_search(pool_trades, args)

    Path(args.direct_output).parent.mkdir(parents=True, exist_ok=True)
    direct.to_csv(args.direct_output, index=False)
    seasonal.to_csv(args.seasonal_output, index=False)
    seasonal_trades.to_csv(args.seasonal_trades_output, index=False)
    Path(args.action_output).write_text(json.dumps(action_maps[:200], indent=2, sort_keys=True), encoding="utf-8")

    print(
        json.dumps(
            {
                "feature_rows": int(len(features)),
                "feature_start": str(features["ts"].min()),
                "feature_end": str(features["ts"].max()),
                "direct_rows": int(len(direct)),
                "seasonal_rows": int(len(seasonal)),
                "direct_passes": int(direct["full_year_gate"].sum()) if "full_year_gate" in direct else 0,
                "seasonal_passes": int(seasonal["full_year_gate"].sum()) if "full_year_gate" in seasonal else 0,
                "top_direct": direct.head(5).to_dict(orient="records"),
                "top_seasonal": seasonal.head(5).to_dict(orient="records") if not seasonal.empty else [],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
