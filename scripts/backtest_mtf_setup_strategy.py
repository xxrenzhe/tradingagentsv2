from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.backtesting.multi_timeframe_setup import (
    MultiTimeframeSetupSpec,
    build_multi_timeframe_trades,
    generate_multi_timeframe_specs,
    prepare_multi_timeframe_features,
    summarize_multi_timeframe_trades,
)
from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.dataflows.databento import _read_bar_window, _read_mbp_window


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest the M1/M3/M15 setup scanner.")
    parser.add_argument("--symbol", default="NQM6")
    parser.add_argument("--start-date", default="2026-03-03")
    parser.add_argument("--end-date", default="2026-05-02")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--use-cache", action="store_true", help="Load existing feature cache instead of raw Databento files.")
    parser.add_argument("--session", default=None, choices=["all", "asia", "europe", "us_rth", "us_late"])
    parser.add_argument("--htf-mode", default=None, choices=["off", "bias", "confirm"])
    parser.add_argument("--reclaim-lookback-minutes", type=int, default=None)
    parser.add_argument("--imbalance-threshold", type=float, default=None)
    parser.add_argument("--stop-loss-points", type=float, default=None)
    parser.add_argument("--take-profit-points", type=float, default=None)
    parser.add_argument("--min-trades", type=int, default=20)
    parser.add_argument("--fail-on-invalid", action="store_true", help="Return a non-zero exit code when no candidate passes validation.")
    parser.add_argument("--point-value", type=float, default=2.0)
    parser.add_argument("--commission", type=float, default=2.0)
    parser.add_argument("--summary-output", default=".tmp/mtf-setup-summary.csv")
    parser.add_argument("--trades-output", default=".tmp/mtf-setup-trades.csv")
    parser.add_argument("--report", default="reports/mtf-setup-backtest.md")
    args = parser.parse_args()

    features = _load_features(args)
    costs = BacktestCosts(point_value=args.point_value, tick_size=0.25, commission_per_contract=args.commission)
    specs = _select_specs(args)
    summaries = []
    trades_by_name: dict[str, pd.DataFrame] = {}
    for spec in specs:
        prepared = prepare_multi_timeframe_features(features, spec=spec)
        trades = build_multi_timeframe_trades(prepared, spec, costs)
        summary = summarize_multi_timeframe_trades(spec, trades, costs)
        summaries.append(summary)
        if not trades.empty:
            trades_by_name[spec.name] = trades
    summary_frame = pd.DataFrame(summaries).sort_values(
        ["score", "net_points", "trades"],
        ascending=[False, False, False],
    )
    qualified = summary_frame[summary_frame["trades"] >= args.min_trades]
    best_name = str((qualified if not qualified.empty else summary_frame).iloc[0]["name"])
    trades = trades_by_name.get(best_name, pd.DataFrame())
    _write_outputs(summary_frame, trades, args, best_name, features)
    display_frame = qualified if not qualified.empty else summary_frame
    print(display_frame.head(10).to_csv(index=False))
    best = summary_frame[summary_frame["name"].eq(best_name)].iloc[0]
    validation_passed = bool(best["trades"] >= args.min_trades and best["net_points"] > 0 and best["profit_factor"] > 1)
    return 1 if args.fail_on_invalid and not validation_passed else (0 if not summary_frame.empty else 2)


def _load_features(args: argparse.Namespace) -> pd.DataFrame:
    cache_path = Path(args.features_cache)
    if args.use_cache and cache_path.exists():
        cache = pd.read_pickle(cache_path)
        frames = [frame for frame in cache.values() if isinstance(frame, pd.DataFrame) and not frame.empty]
        if frames:
            features = pd.concat(frames, ignore_index=True)
            features["ts"] = pd.to_datetime(features["ts"], utc=True)
            return features.sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    bars = _read_bar_window(args.symbol, args.start_date, args.end_date)
    micro = _read_mbp_window(args.symbol, args.start_date, args.end_date)
    return prepare_multi_timeframe_features(bars, microstructure=micro if len(micro) > 10 else None)


def _select_specs(args: argparse.Namespace) -> list[MultiTimeframeSetupSpec]:
    if (
        args.session
        or args.htf_mode
        or args.reclaim_lookback_minutes is not None
        or args.imbalance_threshold is not None
        or args.stop_loss_points is not None
        or args.take_profit_points is not None
    ):
        return [
            MultiTimeframeSetupSpec(
                name=(
                    "mtf_setup_custom"
                    f"_{args.session or 'all'}"
                    f"_htf{args.htf_mode or 'off'}"
                    f"_r{args.reclaim_lookback_minutes or 3}"
                    f"_imb{args.imbalance_threshold if args.imbalance_threshold is not None else 0.3:g}"
                    f"_sl{args.stop_loss_points if args.stop_loss_points is not None else 16:g}"
                    f"_tp{args.take_profit_points if args.take_profit_points is not None else 24:g}"
                ),
                session=args.session or "all",
                htf_mode=args.htf_mode or "off",
                reclaim_lookback_minutes=3 if args.reclaim_lookback_minutes is None else args.reclaim_lookback_minutes,
                imbalance_threshold=0.3 if args.imbalance_threshold is None else args.imbalance_threshold,
                stop_loss_points=16.0 if args.stop_loss_points is None else args.stop_loss_points,
                take_profit_points=24.0 if args.take_profit_points is None else args.take_profit_points,
            )
        ]
    return generate_multi_timeframe_specs()


def _write_outputs(
    summary: pd.DataFrame,
    trades: pd.DataFrame,
    args: argparse.Namespace,
    best_name: str,
    features: pd.DataFrame,
) -> None:
    summary_path = Path(args.summary_output)
    trades_path = Path(args.trades_output)
    report_path = Path(args.report)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    trades_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)
    trades.to_csv(trades_path, index=False)

    best = summary[summary["name"].eq(best_name)].iloc[0].to_dict()
    qualified = summary[summary["trades"] >= args.min_trades]
    validation_passed = bool(
        best["trades"] >= args.min_trades
        and best["net_points"] > 0
        and best["profit_factor"] > 1
    )
    validation_notes = []
    if best["trades"] < args.min_trades:
        validation_notes.append(f"best candidate has only {int(best['trades'])} trades, below min-trades {args.min_trades}")
    if best["net_points"] <= 0:
        validation_notes.append(f"best candidate net points is {best['net_points']:.2f}, not positive")
    if best["profit_factor"] <= 1:
        validation_notes.append(f"best candidate profit factor is {best['profit_factor']:.2f}, not above 1")
    if not validation_notes:
        validation_notes.append("candidate passed sample count, net profit, and profit factor gates")
    report_lines = [
        "# MTF Setup Backtest",
        "",
        "Implements the current landing logic as script-scanned candidates: M15 direction filter, M3 reclaim, M1 trigger, then bracket-style exits.",
        "",
        f"- Symbol: `{args.symbol}`",
        f"- Window: `{args.start_date}` to `{args.end_date}`",
        f"- Feature rows: `{len(features):,}`",
        f"- Min trades gate: `{args.min_trades}`",
        f"- Qualified candidates: `{len(qualified):,}`",
        f"- Validation: `{'PASS' if validation_passed else 'FAIL'}`",
        f"- Best spec: `{best_name}`",
        f"- Trades output: `{trades_path}`",
        f"- Summary output: `{summary_path}`",
        f"- Notes: `{' ; '.join(validation_notes)}`",
        "",
        "## Best Summary",
        "",
        "```csv",
        pd.DataFrame([best]).to_csv(index=False).strip(),
        "```",
        "",
        "## Top 10",
        "",
        "```csv",
        summary.head(10).to_csv(index=False).strip(),
        "```",
    ]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
