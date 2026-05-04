from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from tradingagents.backtesting.short_patterns import evaluate_strategies, prepare_minute_features
from tradingagents.dataflows.databento import _bar_zip_path, _read_bar_window, _read_mbp_window, _tick_zip_path


def _source_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{path.resolve()}:{stat.st_size}:{int(stat.st_mtime)}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine short-term trading patterns from local Databento data.")
    parser.add_argument("--symbol", default="NQM6")
    parser.add_argument("--start-date", default="2026-04-27")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--min-trades", type=int, default=5)
    parser.add_argument("--output", default=".tmp/short-patterns-report.csv")
    parser.add_argument("--bars-cache", default=".tmp/databento-bars-cache.pkl")
    parser.add_argument("--features-cache", default=".tmp/short-patterns-features-cache.pkl")
    parser.add_argument("--start-minute", type=int, default=None, help="UTC minute of day lower bound.")
    parser.add_argument("--end-minute", type=int, default=None, help="UTC minute of day upper bound.")
    parser.add_argument("--no-mbp", action="store_true", help="Skip MBP/order-book features.")
    args = parser.parse_args()

    bars_cache = Path(args.bars_cache)
    cache_key = f"{args.symbol.upper()}|{args.start_date}|{args.end_date}"
    if bars_cache.exists():
        cached = __import__("pandas").read_pickle(bars_cache)
        bars = cached.get(cache_key)
    else:
        cached = {}
        bars = None
    if bars is None:
        bars = _read_bar_window(args.symbol, args.start_date, args.end_date)
        bars_cache.parent.mkdir(parents=True, exist_ok=True)
        cached[cache_key] = bars
        __import__("pandas").to_pickle(cached, bars_cache)
    if bars.empty:
        raise SystemExit(f"No bar data found for {args.symbol} {args.start_date}..{args.end_date}")

    feature_cache_path = Path(args.features_cache)
    feature_cache_key_parts = [
        args.symbol.upper(),
        args.start_date,
        args.end_date,
        "no-mbp" if args.no_mbp else "with-mbp",
        _source_fingerprint(_bar_zip_path()),
    ]
    if not args.no_mbp:
        feature_cache_key_parts.append(_source_fingerprint(_tick_zip_path()))
    feature_cache_key = "|".join(feature_cache_key_parts)
    if feature_cache_path.exists():
        feature_cache = pd.read_pickle(feature_cache_path)
        cached_features = feature_cache.get(feature_cache_key)
    else:
        feature_cache = {}
        cached_features = None

    if cached_features is None:
        microstructure = None
        if not args.no_mbp:
            microstructure = _read_mbp_window(args.symbol, args.start_date, args.end_date)
        features = prepare_minute_features(bars, microstructure)
        feature_cache_path.parent.mkdir(parents=True, exist_ok=True)
        feature_cache[feature_cache_key] = {
            "features": features,
            "mbp_rows": 0 if microstructure is None else len(microstructure),
        }
        pd.to_pickle(feature_cache, feature_cache_path)
    else:
        features = cached_features["features"]
        microstructure = None

    mbp_rows = 0 if args.no_mbp else int((cached_features or feature_cache[feature_cache_key])["mbp_rows"])
    if args.start_minute is not None:
        features = features[features["minute_of_day"] >= args.start_minute]
    if args.end_minute is not None:
        features = features[features["minute_of_day"] < args.end_minute]
    features = features.reset_index(drop=True)
    results, trades_by_name = evaluate_strategies(features, min_trades=args.min_trades)
    if results.empty:
        raise SystemExit("No strategy met the minimum trade count.")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path, index=False)

    top = results.head(args.top)
    print(f"Symbol: {args.symbol}")
    print(f"Window: {args.start_date} to {args.end_date}")
    print(f"Minute bars: {len(bars)}")
    print(f"MBP rows: {mbp_rows}")
    print(f"Evaluated strategies meeting min_trades={args.min_trades}: {len(results)}")
    print(f"Report: {output_path}")
    print()
    print(top.to_string(index=False, float_format=lambda value: f"{value:.4f}"))

    best_name = str(top.iloc[0]["name"])
    best_trades = trades_by_name.get(best_name)
    if best_trades is not None and not best_trades.empty:
        print()
        print(f"Best pattern trades: {best_name}")
        print(best_trades.tail(10).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
