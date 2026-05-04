from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from mine_mbp_advanced_patterns import AdvancedStrategySpec
from optimize_mbp_robust_top10 import Candidate, _load_features
from validate_mbp_2r_blackbox import (
    BlackBoxConfig,
    evaluate_blackbox,
    passes_blackbox_gate,
    write_report,
)


def _fmt_param(value: float | int | None) -> str:
    if value is None:
        return "none"
    if isinstance(value, int):
        return str(value)
    return f"{value:.7g}"


def _name(spec: AdvancedStrategySpec) -> str:
    return (
        f"adv_2r_{spec.family}_lb{spec.lookback}_thr{_fmt_param(spec.threshold)}"
        f"_min{spec.min_hold}_max{spec.max_hold}_{spec.exit_mode}_{spec.session}_{spec.volatility_filter}"
        f"_imb{_fmt_param(spec.imbalance_threshold)}_sl{_fmt_param(spec.stop_loss_points)}"
        f"_tp{_fmt_param(spec.take_profit_points)}"
    )


def generate_expanded_2r_specs(max_candidates: int | None = None) -> list[AdvancedStrategySpec]:
    base = AdvancedStrategySpec(
        name="",
        family="mean_reversion",
        lookback=5,
        threshold=0.6,
        min_hold=1,
        max_hold=10,
        exit_mode="time",
        session="all",
        volatility_filter="all",
        imbalance_threshold=0.35,
        max_spread_quantile=0.75,
        min_depth_quantile=0.25,
        stop_loss_points=4.0,
        take_profit_points=8.0,
    )
    dimensions = {
        "mean_reversion": {
            "lookback": [3, 4, 5, 6, 7, 8, 9, 10],
            "threshold": [0.45, 0.55, 0.6, 0.65, 0.75, 0.9],
        },
        "vwap_reclaim": {
            "lookback": [5, 8, 10, 12, 15],
            "threshold": [0.0001, 0.00015, 0.0002, 0.0003, 0.0005],
        },
        "momentum": {
            "lookback": [5, 8, 10, 12, 15],
            "threshold": [0.0002, 0.0003, 0.00045, 0.0006, 0.0008],
        },
    }
    risk_profiles = [(2.0, 4.0), (3.0, 6.0), (4.0, 8.0), (5.0, 10.0), (6.0, 12.0), (8.0, 16.0)]
    specs: list[AdvancedStrategySpec] = []
    seen = set()
    for family, values in dimensions.items():
        for lookback in values["lookback"]:
            for threshold in values["threshold"]:
                for min_hold, max_hold in [(1, 10), (1, 20), (2, 30), (5, 60)]:
                    for exit_mode in ["time", "reverse"]:
                        for session in ["all", "europe", "us_rth"]:
                            for volatility_filter in ["all", "not_low", "high"]:
                                for imbalance_threshold in [0.2, 0.3, 0.35]:
                                    for stop_loss, take_profit in risk_profiles:
                                        signature = (
                                            family,
                                            lookback,
                                            threshold,
                                            min_hold,
                                            max_hold,
                                            exit_mode,
                                            session,
                                            volatility_filter,
                                            imbalance_threshold,
                                            stop_loss,
                                            take_profit,
                                        )
                                        if signature in seen:
                                            continue
                                        seen.add(signature)
                                        spec = replace(
                                            base,
                                            name="",
                                            family=family,
                                            lookback=lookback,
                                            threshold=threshold,
                                            min_hold=min_hold,
                                            max_hold=max_hold,
                                            exit_mode=exit_mode,
                                            session=session,
                                            volatility_filter=volatility_filter,
                                            imbalance_threshold=imbalance_threshold,
                                            stop_loss_points=stop_loss,
                                            take_profit_points=take_profit,
                                        )
                                        specs.append(replace(spec, name=_name(spec)))
                                        if max_candidates is not None and len(specs) >= max_candidates:
                                            return specs
    return specs


def _config_from_args(args: argparse.Namespace) -> BlackBoxConfig:
    return BlackBoxConfig(
        train_fraction=args.train_fraction,
        min_train_trades=args.min_train_trades,
        min_test_trades=args.min_test_trades,
        min_train_win_rate=args.min_train_win_rate,
        min_test_win_rate=args.min_test_win_rate,
        min_profit_factor=args.min_profit_factor,
        min_positive_window_rate=args.min_positive_window_rate,
        min_bracket_exit_share=args.min_bracket_exit_share,
        window_days=args.window_days,
        window_step_days=args.window_step_days,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Expanded chronological black-box search for 2R MBP strategies.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/mbp-2r-expanded-blackbox.csv")
    parser.add_argument("--report", default="reports/NQM6-mbp-2r-expanded-blackbox.md")
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--min-train-trades", type=int, default=80)
    parser.add_argument("--min-test-trades", type=int, default=40)
    parser.add_argument("--min-train-win-rate", type=float, default=0.56)
    parser.add_argument("--min-test-win-rate", type=float, default=0.60)
    parser.add_argument("--min-profit-factor", type=float, default=1.15)
    parser.add_argument("--min-positive-window-rate", type=float, default=0.60)
    parser.add_argument("--min-bracket-exit-share", type=float, default=0.50)
    parser.add_argument("--window-days", type=int, default=10)
    parser.add_argument("--window-step-days", type=int, default=5)
    parser.add_argument("--max-train-candidates", type=int, default=250)
    parser.add_argument("--max-candidates", type=int, default=25000)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--progress-every", type=int, default=500)
    args = parser.parse_args()

    features = _load_features(Path(args.features_cache))
    specs = generate_expanded_2r_specs(max_candidates=args.max_candidates)
    if args.shard_count < 1:
        raise SystemExit("--shard-count must be >= 1")
    if args.shard_index < 0 or args.shard_index >= args.shard_count:
        raise SystemExit("--shard-index must satisfy 0 <= shard-index < shard-count")
    if args.shard_count > 1:
        specs = [spec for index, spec in enumerate(specs) if index % args.shard_count == args.shard_index]
    candidates = [Candidate("advanced", spec.name, spec) for spec in specs]
    config = _config_from_args(args)
    results = evaluate_blackbox(
        features,
        candidates,
        config,
        max_train_candidates=args.max_train_candidates,
        progress_every=args.progress_every,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output, index=False)
    write_report(Path(args.report), results, features, config)
    passed = int(results["blackbox_pass"].sum()) if not results.empty else 0
    strict_passed = int(results.apply(lambda row: passes_blackbox_gate(row, replace(config, min_positive_window_rate=0.70, min_test_trades=50)), axis=1).sum()) if not results.empty else 0
    print(f"Expanded 2R candidates: {len(candidates):,}")
    print(f"Training-gated candidates tested: {len(results):,}")
    print(f"Black-box pass: {passed:,}")
    print(f"Strict 60%/2R pass: {strict_passed:,}")
    print(f"CSV: {output}")
    print(f"Report: {args.report}")
    if not results.empty:
        print(results.head(20)[["name", "test_trades", "test_win_rate", "test_net_points", "test_profit_factor", "test_positive_window_rate", "blackbox_pass"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
