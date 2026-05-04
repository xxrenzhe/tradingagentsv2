from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from generate_mbp_live_ready_report import _advanced_spec_from_row
from mine_mbp_advanced_patterns import AdvancedStrategySpec
from optimize_mbp_robust_top10 import (
    Candidate,
    _fold_metrics,
    _load_features,
    _prefixed_summary,
    _spec_parameters,
    _window_metrics,
)
from tradingagents.backtesting.short_patterns import BacktestCosts


SELECTED_NAMES = [
    "adv_top8_enhanced_mean_reversion_lb9_thr0.6_min1_max5_reverse_all_high_imb0.35",
    "adv_refined_mean_reversion_lb7_thr0.65_min1_max6_reverse_europe_not_low_imb0.3",
    "adv_top6_enhanced_vwap_reclaim_lb10_thr0.0002_min1_max10_time_all_not_low_imb0.35",
]


def _fmt_param(value: float | int | None) -> str:
    if value is None:
        return "none"
    if isinstance(value, int):
        return str(value)
    return f"{value:.7g}"


def _stable_name(seed_label: str, spec: AdvancedStrategySpec) -> str:
    risk_suffix = ""
    if spec.stop_loss_points is not None:
        risk_suffix = f"_sl{_fmt_param(spec.stop_loss_points)}_tp{_fmt_param(spec.take_profit_points)}"
    return (
        f"adv_stable_{seed_label}_{spec.family}_lb{spec.lookback}_thr{_fmt_param(spec.threshold)}"
        f"_min{spec.min_hold}_max{spec.max_hold}_{spec.exit_mode}_{spec.session}_{spec.volatility_filter}"
        f"_imb{_fmt_param(spec.imbalance_threshold)}{risk_suffix}"
    )


def _threshold_values(spec: AdvancedStrategySpec) -> list[float]:
    if spec.family == "mean_reversion":
        deltas = [-0.15, -0.1, -0.05, 0.0, 0.05, 0.1, 0.15]
        return sorted({round(max(0.1, spec.threshold + delta), 7) for delta in deltas})
    factors = [0.65, 0.75, 0.9, 1.0, 1.1, 1.25, 1.4]
    return sorted({round(max(0.00005, spec.threshold * factor), 7) for factor in factors})


def _neighbor_specs(seed_label: str, seed: AdvancedStrategySpec) -> list[AdvancedStrategySpec]:
    specs: list[AdvancedStrategySpec] = []
    seen = set()
    base_values = {
        "lookback": seed.lookback,
        "threshold": seed.threshold,
        "min_hold": seed.min_hold,
        "max_hold": seed.max_hold,
        "exit_mode": seed.exit_mode,
        "session": seed.session,
        "volatility_filter": seed.volatility_filter,
        "imbalance_threshold": seed.imbalance_threshold,
        "risk_profile": (seed.stop_loss_points, seed.take_profit_points),
    }
    dimensions = {
        "lookback": sorted({max(2, seed.lookback + delta) for delta in [-3, -2, -1, 0, 1, 2, 3]}),
        "threshold": _threshold_values(seed),
        "min_hold": sorted({max(1, seed.min_hold + delta) for delta in [-1, 0, 1]}),
        "max_hold": sorted({max(2, seed.max_hold + delta) for delta in [-3, -2, -1, 0, 1, 2, 3]}),
        "exit_mode": sorted({seed.exit_mode, "time", "reverse", "reverse_vwap"}),
        "session": sorted({seed.session, "all", "europe", "us_rth"}),
        "volatility_filter": sorted({seed.volatility_filter, "all", "not_low", "high"}),
        "imbalance_threshold": sorted(
            {
                round(value, 7)
                for value in [
                    seed.imbalance_threshold or 0.35,
                    max(0.05, (seed.imbalance_threshold or 0.35) - 0.1),
                    max(0.05, (seed.imbalance_threshold or 0.35) - 0.05),
                    min(0.7, (seed.imbalance_threshold or 0.35) + 0.05),
                    min(0.7, (seed.imbalance_threshold or 0.35) + 0.1),
                ]
            }
        ),
        "risk_profile": sorted(
            {
                (seed.stop_loss_points, seed.take_profit_points),
                (None, None),
                (8.0, 16.0),
                (12.0, 24.0),
                (16.0, 32.0),
            },
            key=lambda pair: (-1 if pair[0] is None else pair[0], -1 if pair[1] is None else pair[1]),
        ),
    }

    candidate_values = [base_values]
    for key, values in dimensions.items():
        for value in values:
            candidate_values.append(base_values | {key: value})

    paired_keys = [
        ("lookback", "threshold"),
        ("threshold", "imbalance_threshold"),
        ("threshold", "volatility_filter"),
        ("lookback", "max_hold"),
        ("max_hold", "exit_mode"),
        ("session", "volatility_filter"),
        ("exit_mode", "risk_profile"),
    ]
    for first_key, second_key in paired_keys:
        for first_value in dimensions[first_key]:
            for second_value in dimensions[second_key]:
                candidate_values.append(base_values | {first_key: first_value, second_key: second_value})

    for values in candidate_values:
        if int(values["max_hold"]) <= int(values["min_hold"]):
            continue
        stop_loss, take_profit = values["risk_profile"]
        signature = (
            values["lookback"],
            values["threshold"],
            values["min_hold"],
            values["max_hold"],
            values["exit_mode"],
            values["session"],
            values["volatility_filter"],
            values["imbalance_threshold"],
            stop_loss,
            take_profit,
        )
        if signature in seen:
            continue
        seen.add(signature)
        spec = replace(
            seed,
            name="",
            lookback=int(values["lookback"]),
            threshold=float(values["threshold"]),
            min_hold=int(values["min_hold"]),
            max_hold=int(values["max_hold"]),
            exit_mode=str(values["exit_mode"]),
            session=str(values["session"]),
            volatility_filter=str(values["volatility_filter"]),
            imbalance_threshold=float(values["imbalance_threshold"]),
            stop_loss_points=stop_loss,
            take_profit_points=take_profit,
        )
        specs.append(replace(spec, name=_stable_name(seed_label, spec)))
    return specs


def _load_selected_rows(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        if path.exists():
            frame = pd.read_csv(path)
            if not frame.empty:
                frames.append(frame)
    if not frames:
        raise SystemExit("No result files found.")
    candidates = pd.concat(frames, ignore_index=True, sort=False)
    rows = []
    for name in SELECTED_NAMES:
        match = candidates[candidates["name"].eq(name)]
        if match.empty:
            raise SystemExit(f"Missing selected strategy: {name}")
        rows.append(match.iloc[0])
    selected = pd.DataFrame(rows).reset_index(drop=True)
    selected["seed_label"] = ["stable_yield", "refined_defensive", "vwap_aggressive"]
    return selected


def _evaluate_candidate(
    features: pd.DataFrame,
    candidate: Candidate,
    folds: int,
    window_days: int,
    window_step_days: int,
) -> dict:
    base_costs = BacktestCosts()
    costs_3x = BacktestCosts(slippage_ticks_per_side=3.0)
    full = _prefixed_summary(candidate, features, base_costs, "full")
    fold = _fold_metrics(candidate, features, folds, base_costs)
    cost_3x = _prefixed_summary(candidate, features, costs_3x, "cost_3x")
    window = _window_metrics(candidate, features, costs_3x, window_days, window_step_days)
    return {
        "name": candidate.name,
        "source": candidate.source,
        "family": candidate.spec.family,
        **_spec_parameters(candidate),
        **full,
        **fold,
        **window,
        "worst_cost_net_points": cost_3x["cost_3x_net_points"],
        "worst_cost_score": cost_3x["cost_3x_score"],
    }


def optimize_stability(
    features: pd.DataFrame,
    selected: pd.DataFrame,
    quick_top: int,
    folds: int,
    window_days: int,
    window_step_days: int,
) -> pd.DataFrame:
    rows = []
    for _, seed_row in selected.iterrows():
        seed_spec = _advanced_spec_from_row(seed_row)
        if seed_spec is None:
            raise SystemExit(f"Cannot build spec from selected row: {seed_row['name']}")
        seed_label = str(seed_row["seed_label"])
        seed_net = float(seed_row["full_net_points"])
        seed_pf = float(seed_row["full_profit_factor"])
        seed_stability = float(seed_row["full_stability"])
        seed_window_rate = float(seed_row["positive_window_rate"])
        seed_min_window = float(seed_row["min_window_net_points"])
        seed_cost = float(seed_row["worst_cost_net_points"])
        quick_rows = []
        quick_candidates = []
        specs = _neighbor_specs(seed_label, seed_spec)
        print(f"Scanning {seed_label}: {len(specs):,} neighbor specs", flush=True)
        for index, spec in enumerate(specs, start=1):
            candidate = Candidate("advanced", spec.name, spec)
            full = _prefixed_summary(candidate, features, BacktestCosts(), "full")
            if index % 1000 == 0:
                print(f"  quick {index:,}/{len(specs):,}", flush=True)
            if (
                full["full_trades"] >= 200
                and full["full_net_points"] >= seed_net * 0.80
                and full["full_profit_factor"] >= max(1.25, seed_pf * 0.88)
                and full["full_stability"] >= seed_stability
            ):
                quick_rows.append(full | {"name": spec.name})
                quick_candidates.append(candidate)
        if not quick_rows:
            continue
        quick = pd.DataFrame(quick_rows)
        quick["quick_stability_score"] = (
            quick["full_net_points"] * 0.35
            - quick["full_max_drawdown_points"] * 0.65
            + quick["full_profit_factor"] * 350
            + quick["full_stability"] * 1200
        )
        selected_names = set(
            quick.sort_values(
                ["quick_stability_score", "full_stability", "full_net_points", "full_profit_factor"],
                ascending=[False, False, False, False],
            )
            .head(quick_top)["name"]
            .tolist()
        )
        for candidate in quick_candidates:
            if candidate.name not in selected_names:
                continue
            row = _evaluate_candidate(features, candidate, folds, window_days, window_step_days)
            row["seed_label"] = seed_label
            row["seed_name"] = seed_row["name"]
            row["seed_net_points"] = seed_net
            row["seed_profit_factor"] = seed_pf
            row["seed_stability"] = seed_stability
            row["seed_positive_window_rate"] = seed_window_rate
            row["seed_min_window_net_points"] = seed_min_window
            row["seed_worst_cost_net_points"] = seed_cost
            row["net_delta"] = row["full_net_points"] - seed_net
            row["pf_delta"] = row["full_profit_factor"] - seed_pf
            row["stability_delta"] = row["full_stability"] - seed_stability
            row["min_window_delta"] = row["min_window_net_points"] - seed_min_window
            row["worst_cost_delta"] = row["worst_cost_net_points"] - seed_cost
            row["stable_ready"] = (
                row["full_net_points"] >= seed_net * 0.90
                and row["full_profit_factor"] >= max(1.25, seed_pf * 0.92)
                and row["full_stability"] > seed_stability
                and row["positive_fold_rate"] >= 0.80
                and row["positive_window_rate"] >= max(0.78, min(seed_window_rate, 1.0) - 0.12)
                and row["worst_cost_net_points"] > 0
                and row["min_window_trades"] >= 5
            )
            row["stability_rank_score"] = (
                row["full_net_points"] * 0.22
                - row["full_max_drawdown_points"] * 0.55
                + row["full_profit_factor"] * 280
                + row["full_stability"] * 1500
                + row["positive_window_rate"] * 450
                + max(row["min_window_net_points"], -500) * 0.35
                + row["worst_cost_net_points"] * 0.12
            )
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["stable_ready", "seed_label", "stability_rank_score", "full_stability", "full_net_points"],
        ascending=[False, True, False, False, False],
    ).reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Optimize selected MBP strategy stability with local parameter search.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--enhanced-results", default=".tmp/mbp-enhanced-top10.csv")
    parser.add_argument("--refined-results", default=".tmp/mbp-refined-mean-reversion.csv")
    parser.add_argument("--output", default=".tmp/mbp-selected-stability-optimized.csv")
    parser.add_argument("--quick-top", type=int, default=50)
    parser.add_argument("--folds", type=int, default=6)
    parser.add_argument("--window-days", type=int, default=10)
    parser.add_argument("--window-step-days", type=int, default=5)
    args = parser.parse_args()

    features = _load_features(Path(args.features_cache))
    selected = _load_selected_rows([Path(args.enhanced_results), Path(args.refined_results)])
    ranked = optimize_stability(
        features,
        selected,
        quick_top=args.quick_top,
        folds=args.folds,
        window_days=args.window_days,
        window_step_days=args.window_step_days,
    )
    if ranked.empty:
        raise SystemExit("No stability-optimized candidates found.")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(output, index=False)
    print(output)
    for seed_label, group in ranked.groupby("seed_label", sort=False):
        print()
        print(seed_label)
        print(
            group.head(5)[
                [
                    "name",
                    "stable_ready",
                    "full_trades",
                    "full_net_points",
                    "net_delta",
                    "full_max_drawdown_points",
                    "full_profit_factor",
                    "pf_delta",
                    "full_stability",
                    "stability_delta",
                    "positive_window_rate",
                    "min_window_net_points",
                    "worst_cost_net_points",
                    "stability_rank_score",
                ]
            ].to_string(index=False)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
