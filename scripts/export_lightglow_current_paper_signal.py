from __future__ import annotations

import argparse
import io
import json
import os
import pickle
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from backtest_lightglow_nq_bars import build_lightglow_signals, resample_ohlcv, session_mask
from optimize_nq_lightglow_paper_executable import PAPER_SELECTED_ALIAS, PAPER_STRATEGY_ID
from search_nq_bar_2r_walkforward import load_continuous_nq_bars


def export_current_signal(args: argparse.Namespace) -> dict[str, Any]:
    bars = _load_bars(args)
    signal = build_current_signal_row(
        bars,
        max_completed_bar_age_minutes=args.max_completed_bar_age_minutes,
        now=pd.Timestamp(args.now, tz="UTC") if args.now else pd.Timestamp.now(tz="UTC"),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if signal is None:
        pd.DataFrame(columns=_paper_columns()).to_csv(output, index=False)
        return {"status": "no_signal", "rows": 0, "output": str(output)}
    pd.DataFrame([signal]).to_csv(output, index=False)
    return {
        "status": "written",
        "rows": 1,
        "output": str(output),
        "entry_ts": signal["entry_ts"],
        "direction": signal["direction"],
        "strategy_id": PAPER_STRATEGY_ID,
    }


def build_current_signal_row(
    bars: pd.DataFrame,
    *,
    max_completed_bar_age_minutes: float,
    now: pd.Timestamp,
) -> dict[str, Any] | None:
    frame = build_lightglow_signals(resample_ohlcv(bars, 1))
    if frame.empty:
        return None
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    now = pd.Timestamp(now).tz_convert("UTC") if pd.Timestamp(now).tzinfo else pd.Timestamp(now, tz="UTC")
    completed = frame[frame["ts"] <= now.floor("min") - pd.Timedelta(minutes=1)].copy()
    if completed.empty:
        return None
    latest = completed.iloc[-1]
    age_minutes = (now - latest["ts"]).total_seconds() / 60.0
    if age_minutes > float(max_completed_bar_age_minutes):
        return None
    raw_signal = int(latest.get("premium_discount_reversal") or 0)
    direction = -raw_signal
    if direction == 0:
        return None
    if not bool(session_mask(pd.DataFrame([latest]), "all").iloc[0]):
        return None
    entry_ts = latest["ts"] + pd.Timedelta(minutes=1)
    exit_ts = entry_ts + pd.Timedelta(minutes=2)
    entry_price = float(latest["Close"])
    return {
        "trade_date": entry_ts.date().isoformat(),
        "entry_ts": entry_ts.isoformat(),
        "actual_entry_ts": entry_ts.isoformat(),
        "exit_ts": exit_ts.isoformat(),
        "symbol": str(latest.get("symbol", "NQ")),
        "direction": int(direction),
        "entry_price": entry_price,
        "exit_price": entry_price,
        "exit_reason": "time",
        "holding_minutes": 2,
        "portfolio_rule": PAPER_STRATEGY_ID,
        "selected_alias": PAPER_SELECTED_ALIAS,
        "strategy_name": PAPER_STRATEGY_ID,
        "strategy_alias": PAPER_SELECTED_ALIAS,
        "source_timeframe_minutes": 1,
        "source_signal": "lightglow_current_premium_discount_reversal",
        "source_direction_mode": "reverse",
        "timecell_mode": "shadow_only",
        "strategy_stop_points": "",
        "strategy_target_points": "",
        "signal_bar_ts": latest["ts"].isoformat(),
        "signal_bar_close": entry_price,
    }


def _load_bars(args: argparse.Namespace) -> pd.DataFrame:
    if args.bars:
        path = Path(args.bars)
        if path.suffix == ".pkl":
            with path.open("rb") as file:
                payload = pickle.load(file)
            if isinstance(payload, dict) and "bars" in payload:
                return payload["bars"].copy()
            if isinstance(payload, pd.DataFrame):
                return payload.copy()
            raise ValueError(f"Unsupported pickle payload in {path}")
        return _normalize_bars(_read_csv_tail(path, args.tail_rows))
    return _normalize_bars(load_continuous_nq_bars(args).tail(args.tail_rows) if args.tail_rows > 0 else load_continuous_nq_bars(args))


def _read_csv_tail(path: Path, tail_rows: int) -> pd.DataFrame:
    if tail_rows <= 0:
        return pd.read_csv(path)
    with path.open("rb") as file:
        header = file.readline().decode("utf-8").rstrip("\r\n")
        if not header:
            return pd.DataFrame()
        file.seek(0, os.SEEK_END)
        position = file.tell()
        chunks = []
        newline_count = 0
        block_size = 1024 * 1024
        while position > 0 and newline_count <= tail_rows:
            read_size = min(block_size, position)
            position -= read_size
            file.seek(position)
            chunk = file.read(read_size)
            chunks.append(chunk)
            newline_count += chunk.count(b"\n")
    content = b"".join(reversed(chunks)).decode("utf-8")
    data_lines = content.splitlines()[-tail_rows:]
    if data_lines and data_lines[0].rstrip("\r\n") == header:
        data_lines = data_lines[1:]
    if not data_lines:
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(header + "\n" + "\n".join(data_lines) + "\n"))


def _normalize_bars(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    rename = {}
    if "ts" not in normalized.columns and "ts_event" in normalized.columns:
        rename["ts_event"] = "ts"
    for source, target in {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }.items():
        if target not in normalized.columns and source in normalized.columns:
            rename[source] = target
    normalized = normalized.rename(columns=rename)
    required = {"ts", "symbol", "Open", "High", "Low", "Close", "Volume"}
    missing = required - set(normalized.columns)
    if missing:
        raise ValueError(f"bars missing required columns: {sorted(missing)}")
    return normalized


def _paper_columns() -> list[str]:
    return [
        "trade_date",
        "entry_ts",
        "actual_entry_ts",
        "exit_ts",
        "symbol",
        "direction",
        "entry_price",
        "exit_price",
        "exit_reason",
        "holding_minutes",
        "portfolio_rule",
        "selected_alias",
        "strategy_name",
        "strategy_alias",
        "source_timeframe_minutes",
        "source_signal",
        "source_direction_mode",
        "timecell_mode",
        "strategy_stop_points",
        "strategy_target_points",
        "signal_bar_ts",
        "signal_bar_close",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the latest paper-executable Lightglow signal.")
    parser.add_argument("--bars", default="", help="Optional local OHLCV CSV/PKL. Defaults to Databento continuous bars loader.")
    parser.add_argument("--start-date", default="2021-04-28")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-lightglow-current-signal-features-cache.pkl")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--tail-rows", type=int, default=5_000, help="Read only the last N CSV rows for live export; use 0 for full history.")
    parser.add_argument("--max-completed-bar-age-minutes", type=float, default=5.0)
    parser.add_argument("--now", default="")
    parser.add_argument("--output", default=".tmp/nq-lightglow-current-paper-signal.csv")
    args = parser.parse_args()
    print(json.dumps(export_current_signal(args), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
