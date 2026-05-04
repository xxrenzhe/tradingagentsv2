from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from datetime import timedelta
from io import TextIOWrapper
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import zstandard as zstd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.dataflows.databento import _bar_zip_path


BAR_MEMBER = "glbx-mdp3-20100606-20260427.ohlcv-1m.csv.zst"
NQ_SYMBOL_RE = re.compile(r"^NQ[HMUZ]\d$")


@dataclass(frozen=True)
class Candidate:
    name: str
    direction: int
    stop_loss_points: float
    take_profit_points: float
    horizon_minutes: int
    session: str
    feature: str
    op: str
    threshold: float


def load_continuous_nq_bars(args: argparse.Namespace) -> pd.DataFrame:
    cache_path = Path(args.cache)
    source = _bar_zip_path()
    source_stat = source.stat()
    cache_key = {
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

    start_ts = pd.Timestamp(args.start_date, tz="UTC")
    end_ts = pd.Timestamp(args.end_date, tz="UTC")
    chunks: list[pd.DataFrame] = []
    usecols = ["ts_event", "open", "high", "low", "close", "volume", "symbol"]
    with zipfile.ZipFile(source) as archive:
        with archive.open(BAR_MEMBER) as compressed:
            stream = zstd.ZstdDecompressor().stream_reader(compressed)
            text_stream = TextIOWrapper(stream, encoding="utf-8")
            for chunk in pd.read_csv(text_stream, usecols=usecols, chunksize=args.chunk_size):
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


def prepare_features(bars: pd.DataFrame) -> pd.DataFrame:
    features = bars.copy()
    features["trade_date"] = features["ts"].dt.date
    features["minute_of_day"] = features["ts"].dt.hour * 60 + features["ts"].dt.minute
    features["return_1m"] = features["Close"].pct_change()
    features["range_points"] = features["High"] - features["Low"]
    features["body_points"] = (features["Close"] - features["Open"]).abs()
    features["momentum_5"] = features["Close"].pct_change(5)
    features["momentum_15"] = features["Close"].pct_change(15)
    features["momentum_60"] = features["Close"].pct_change(60)
    features["vol_30"] = features["return_1m"].rolling(30).std()
    features["vol_120"] = features["return_1m"].rolling(120).std()
    rolling_mean = features["Close"].rolling(30).mean()
    rolling_std = features["Close"].rolling(30).std().replace(0, pd.NA)
    features["z_30"] = (features["Close"] - rolling_mean) / rolling_std
    features["range_mean_30"] = features["range_points"].rolling(30).mean()
    features["volume_z_60"] = (
        features["Volume"] - features["Volume"].rolling(60).mean()
    ) / features["Volume"].rolling(60).std().replace(0, pd.NA)
    return features.dropna(subset=["Close"]).reset_index(drop=True)


def _session_mask(frame: pd.DataFrame, session: str) -> pd.Series:
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
    raise ValueError(f"unknown session: {session}")


def build_2r_events(
    features: pd.DataFrame,
    direction: int,
    stop_loss_points: float,
    horizon_minutes: int,
    *,
    entry_step_minutes: int,
) -> pd.DataFrame:
    costs = BacktestCosts()
    take_profit_points = stop_loss_points * 2.0
    rows: list[dict[str, Any]] = []
    timestamps = features["ts"].to_numpy()
    symbols = features["symbol"].astype(str).to_numpy()
    open_prices = pd.to_numeric(features["Open"], errors="coerce").to_numpy(dtype=float)
    high_prices = pd.to_numeric(features["High"], errors="coerce").to_numpy(dtype=float)
    low_prices = pd.to_numeric(features["Low"], errors="coerce").to_numpy(dtype=float)
    close_prices = pd.to_numeric(features["Close"], errors="coerce").to_numpy(dtype=float)
    feature_columns = [
        "ts",
        "symbol",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "trade_date",
        "minute_of_day",
        "return_1m",
        "range_points",
        "body_points",
        "momentum_5",
        "momentum_15",
        "momentum_60",
        "vol_30",
        "vol_120",
        "z_30",
        "range_mean_30",
        "volume_z_60",
    ]
    records = features[feature_columns].to_dict(orient="records")
    limit = len(features) - horizon_minutes - 1
    entry_step_minutes = max(1, int(entry_step_minutes))
    entry_indexes = np.arange(0, limit, entry_step_minutes, dtype=int)
    if len(entry_indexes) == 0:
        return pd.DataFrame(rows)
    offsets = np.arange(1, horizon_minutes + 1, dtype=int)
    window_indexes = entry_indexes[:, None] + offsets[None, :]
    entry_prices = open_prices[entry_indexes + 1]
    timeout_indexes = entry_indexes + horizon_minutes
    timeout_prices = close_prices[timeout_indexes]
    if direction > 0:
        target_prices = entry_prices + take_profit_points
        stop_prices = entry_prices - stop_loss_points
        target_hits = high_prices[window_indexes] >= target_prices[:, None]
        stop_hits = low_prices[window_indexes] <= stop_prices[:, None]
    else:
        target_prices = entry_prices - take_profit_points
        stop_prices = entry_prices + stop_loss_points
        target_hits = low_prices[window_indexes] <= target_prices[:, None]
        stop_hits = high_prices[window_indexes] >= stop_prices[:, None]
    symbol_valid = symbols[window_indexes] == symbols[entry_indexes, None]
    finite_valid = np.isfinite(entry_prices) & np.isfinite(timeout_prices)
    first_target = np.where(target_hits.any(axis=1), target_hits.argmax(axis=1), horizon_minutes + 1)
    first_stop = np.where(stop_hits.any(axis=1), stop_hits.argmax(axis=1), horizon_minutes + 1)
    first_invalid = np.where((~symbol_valid).any(axis=1), (~symbol_valid).argmax(axis=1), horizon_minutes + 1)
    for position, entry_index in enumerate(entry_indexes):
        first_exit = min(first_target[position], first_stop[position], horizon_minutes)
        if not finite_valid[position] or first_invalid[position] <= first_exit:
            continue
        entry_price = float(entry_prices[position])
        target_price = float(target_prices[position])
        stop_price = float(stop_prices[position])
        exit_price = float(timeout_prices[position])
        exit_reason = "timeout"
        exit_index = entry_index + horizon_minutes
        if first_stop[position] <= horizon_minutes or first_target[position] <= horizon_minutes:
            if first_stop[position] <= first_target[position]:
                exit_price = stop_price
                exit_reason = "stop_loss_ambiguous" if first_stop[position] == first_target[position] else "stop_loss"
                exit_index = int(entry_index + first_stop[position] + 1)
            else:
                exit_price = target_price
                exit_reason = "take_profit"
                exit_index = int(entry_index + first_target[position] + 1)
        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points
        row = dict(records[entry_index])
        row.update(
            {
                "entry_index": entry_index,
                "entry_ts": timestamps[entry_index],
                "exit_ts": timestamps[exit_index],
                "direction": direction,
                "stop_loss_points": stop_loss_points,
                "take_profit_points": take_profit_points,
                "horizon_minutes": horizon_minutes,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "gross_points": gross_points,
                "net_points": net_points,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(frame: pd.DataFrame) -> dict[str, float | int]:
    if frame.empty:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "net_points": 0.0,
            "profit_factor": 0.0,
            "target_exit_share": 0.0,
            "bracket_exit_share": 0.0,
        }
    net = pd.to_numeric(frame["net_points"], errors="coerce").fillna(0.0)
    wins = net[net > 0].sum()
    losses = abs(net[net < 0].sum())
    reasons = frame["exit_reason"].astype(str)
    return {
        "trades": int(len(frame)),
        "win_rate": float((net > 0).mean()),
        "net_points": float(net.sum()),
        "profit_factor": float(wins / losses) if losses > 0 else (999.0 if wins > 0 else 0.0),
        "target_exit_share": float((reasons == "take_profit").mean()),
        "bracket_exit_share": float(reasons.str.contains("take_profit|stop_loss").mean()),
    }


def generate_candidates(train_events: pd.DataFrame, args: argparse.Namespace) -> list[Candidate]:
    candidates: list[Candidate] = []
    features = ["momentum_5", "momentum_15", "momentum_60", "vol_30", "vol_120", "z_30", "range_mean_30", "volume_z_60"]
    for session in args.sessions:
        session_events = train_events[_session_mask(train_events, session)]
        if len(session_events) < args.min_train_trades:
            continue
        for feature in features:
            values = pd.to_numeric(session_events[feature], errors="coerce").dropna()
            if len(values) < args.min_train_trades:
                continue
            for quantile in args.quantiles:
                threshold = float(values.quantile(float(quantile)))
                for op in ["<=", ">="]:
                    mask = pd.to_numeric(session_events[feature], errors="coerce") <= threshold
                    if op == ">=":
                        mask = pd.to_numeric(session_events[feature], errors="coerce") >= threshold
                    selected = session_events[mask]
                    stats = summarize(selected)
                    if (
                        stats["trades"] >= args.min_train_trades
                        and stats["win_rate"] >= args.min_train_win_rate
                        and stats["profit_factor"] >= args.min_train_profit_factor
                        and stats["bracket_exit_share"] >= args.min_bracket_exit_share
                    ):
                        direction_label = "long" if int(session_events["direction"].iloc[0]) > 0 else "short"
                        stop = float(session_events["stop_loss_points"].iloc[0])
                        horizon = int(session_events["horizon_minutes"].iloc[0])
                        candidates.append(
                            Candidate(
                                name=(
                                    f"bar2r_{direction_label}_sl{stop:g}_tp{stop * 2:g}_h{horizon}"
                                    f"_{session}_{feature}{op}{threshold:.6g}"
                                ),
                                direction=int(session_events["direction"].iloc[0]),
                                stop_loss_points=stop,
                                take_profit_points=stop * 2.0,
                                horizon_minutes=horizon,
                                session=session,
                                feature=feature,
                                op=op,
                                threshold=threshold,
                            )
                        )
    return candidates


def apply_candidate(events: pd.DataFrame, candidate: Candidate) -> pd.DataFrame:
    selected = events[_session_mask(events, candidate.session)].copy()
    values = pd.to_numeric(selected[candidate.feature], errors="coerce")
    if candidate.op == "<=":
        selected = selected[values <= candidate.threshold]
    else:
        selected = selected[values >= candidate.threshold]
    return selected


def walk_forward(features: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    start = pd.Timestamp(args.walk_start_date, tz="UTC")
    end = pd.Timestamp(args.end_date, tz="UTC")
    fold_rows: list[dict[str, Any]] = []
    trade_rows: list[pd.DataFrame] = []
    event_cache: dict[tuple[int, float, int], pd.DataFrame] = {}
    for direction in args.directions:
        for stop_loss in args.stop_loss_points:
            for horizon in args.horizon_minutes:
                event_cache[(int(direction), float(stop_loss), int(horizon))] = build_2r_events(
                    features,
                    direction=int(direction),
                    stop_loss_points=float(stop_loss),
                    horizon_minutes=int(horizon),
                    entry_step_minutes=args.entry_step_minutes,
                )

    fold = 0
    test_start = start
    while test_start + timedelta(days=args.test_days) <= end:
        train_start = test_start - timedelta(days=args.purge_days + args.train_days)
        train_end = test_start - timedelta(days=args.purge_days)
        test_end = test_start + timedelta(days=args.test_days)
        for key, events in event_cache.items():
            direction, stop_loss, horizon = key
            train = events[(events["entry_ts"] >= train_start) & (events["entry_ts"] < train_end)]
            test = events[(events["entry_ts"] >= test_start) & (events["entry_ts"] < test_end)]
            if len(train) < args.min_train_trades or len(test) < args.min_test_trades:
                continue
            candidates = generate_candidates(train, args)
            ranked_candidates = []
            for candidate in candidates:
                train_selected = apply_candidate(train, candidate)
                train_stats = summarize(train_selected)
                ranked_candidates.append((train_stats["profit_factor"], train_stats["win_rate"], train_stats["trades"], candidate))
            ranked_candidates.sort(reverse=True, key=lambda item: (item[0], item[1], item[2]))
            for _, _, _, candidate in ranked_candidates[: args.max_fold_candidates]:
                test_selected = apply_candidate(test, candidate)
                train_selected = apply_candidate(train, candidate)
                train_stats = summarize(train_selected)
                test_stats = summarize(test_selected)
                blackbox_pass = (
                    test_stats["trades"] >= args.min_test_trades
                    and test_stats["win_rate"] >= args.min_test_win_rate
                    and test_stats["net_points"] > 0
                    and test_stats["profit_factor"] >= args.min_test_profit_factor
                    and test_stats["bracket_exit_share"] >= args.min_bracket_exit_share
                )
                row = {
                    "fold": fold,
                    "candidate": candidate.name,
                    "direction": direction,
                    "stop_loss_points": stop_loss,
                    "take_profit_points": stop_loss * 2.0,
                    "horizon_minutes": horizon,
                    "session": candidate.session,
                    "feature": candidate.feature,
                    "op": candidate.op,
                    "threshold": candidate.threshold,
                    "train_start": str(train_start.date()),
                    "train_end": str(train_end.date()),
                    "test_start": str(test_start.date()),
                    "test_end": str(test_end.date()),
                    **{f"train_{key}": value for key, value in train_stats.items()},
                    **{f"test_{key}": value for key, value in test_stats.items()},
                    "blackbox_pass": bool(blackbox_pass),
                }
                fold_rows.append(row)
                if not test_selected.empty:
                    trades = test_selected.copy()
                    trades["fold"] = fold
                    trades["candidate"] = candidate.name
                    trades["blackbox_pass"] = bool(blackbox_pass)
                    trade_rows.append(trades)
        fold += 1
        test_start += timedelta(days=args.step_days)
    results = pd.DataFrame(fold_rows)
    trades = pd.concat(trade_rows, ignore_index=True, sort=False) if trade_rows else pd.DataFrame()
    return results, trades


def write_report(path: Path, results: pd.DataFrame, trades: pd.DataFrame, features: pd.DataFrame, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    passed = results[results["blackbox_pass"]] if not results.empty else pd.DataFrame()
    lines = [
        "# NQ Bar-Only 60% Fixed-2R Walk-Forward Search",
        "",
        "## Verdict",
        "",
    ]
    if passed.empty:
        lines.append("No long-horizon bar-only NQ candidate passed the fixed-2R black-box gate.")
    else:
        lines.append(f"Found {len(passed):,} fold-level fixed-2R black-box passes. These still require contract-roll and paper validation before live use.")
    lines.extend(
        [
            "",
            "## Data",
            "",
            f"- Source: `{_bar_zip_path()}`.",
            f"- Continuous construction: one NQ futures row per minute, selected by highest reported volume.",
            f"- Feature span: `{features['ts'].min()}` to `{features['ts'].max()}`.",
            f"- Feature rows: `{len(features):,}`.",
            f"- Distinct symbols selected: `{features['symbol'].nunique()}`.",
            "",
            "## Gates",
            "",
            f"- Train days: `{args.train_days}`; purge days: `{args.purge_days}`; test days: `{args.test_days}`; step days: `{args.step_days}`.",
            f"- Minimum train/test trades: `{args.min_train_trades}` / `{args.min_test_trades}`.",
            f"- Train win/PF: `{args.min_train_win_rate}` / `{args.min_train_profit_factor}`.",
            f"- Test win/PF: `{args.min_test_win_rate}` / `{args.min_test_profit_factor}`.",
            f"- Minimum bracket exit share: `{args.min_bracket_exit_share}`.",
            "",
            "## Summary",
            "",
            f"- Rows tested: `{len(results):,}`.",
            f"- Black-box passes: `{len(passed):,}`.",
            f"- Test trades exported: `{len(trades):,}`.",
            "",
        ]
    )
    if not results.empty:
        display_columns = [
            "blackbox_pass",
            "candidate",
            "fold",
            "train_trades",
            "train_win_rate",
            "train_net_points",
            "train_profit_factor",
            "test_trades",
            "test_win_rate",
            "test_net_points",
            "test_profit_factor",
            "test_bracket_exit_share",
        ]
        top = results.sort_values(["blackbox_pass", "test_win_rate", "test_net_points"], ascending=[False, False, False]).head(20)
        lines.extend(["## Top Rows", "", _markdown_table(top[display_columns]), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    rows = ["| " + " | ".join(frame.columns) + " |", "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    for _, row in frame.iterrows():
        values = []
        for column in frame.columns:
            value = row[column]
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Long-horizon bar-only NQ fixed-2R purged walk-forward search.")
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--walk-start-date", default="2024-09-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-bar-continuous-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/nq-bar-2r-walkforward.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-bar-2r-walkforward-trades.csv")
    parser.add_argument("--report", default="reports/NQ-bar-2r-walkforward.md")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--entry-step-minutes", type=int, default=5)
    parser.add_argument("--train-days", type=int, default=180)
    parser.add_argument("--purge-days", type=int, default=5)
    parser.add_argument("--test-days", type=int, default=30)
    parser.add_argument("--step-days", type=int, default=30)
    parser.add_argument("--directions", type=int, nargs="+", default=[1, -1])
    parser.add_argument("--stop-loss-points", type=float, nargs="+", default=[8.0, 12.0, 16.0, 24.0, 32.0])
    parser.add_argument("--horizon-minutes", type=int, nargs="+", default=[15, 30, 60, 120])
    parser.add_argument("--sessions", nargs="+", default=["all", "europe", "us_rth", "us_late", "asia"])
    parser.add_argument("--quantiles", type=float, nargs="+", default=[0.1, 0.2, 0.3, 0.7, 0.8, 0.9])
    parser.add_argument("--min-train-trades", type=int, default=80)
    parser.add_argument("--min-test-trades", type=int, default=20)
    parser.add_argument("--min-train-win-rate", type=float, default=0.58)
    parser.add_argument("--min-test-win-rate", type=float, default=0.60)
    parser.add_argument("--min-train-profit-factor", type=float, default=1.15)
    parser.add_argument("--min-test-profit-factor", type=float, default=1.20)
    parser.add_argument("--min-bracket-exit-share", type=float, default=0.70)
    parser.add_argument("--max-fold-candidates", type=int, default=20)
    args = parser.parse_args()

    features = load_continuous_nq_bars(args)
    results, trades = walk_forward(features, args)
    output = Path(args.output)
    trades_output = Path(args.trades_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output, index=False)
    trades.to_csv(trades_output, index=False)
    write_report(Path(args.report), results, trades, features, args)
    passed = int(results["blackbox_pass"].sum()) if "blackbox_pass" in results.columns else 0
    print(
        json.dumps(
            {
                "feature_rows": int(len(features)),
                "feature_start": str(features["ts"].min()),
                "feature_end": str(features["ts"].max()),
                "distinct_symbols": int(features["symbol"].nunique()),
                "result_rows": int(len(results)),
                "blackbox_passes": passed,
                "output": str(output),
                "trades_output": str(trades_output),
                "report": args.report,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
