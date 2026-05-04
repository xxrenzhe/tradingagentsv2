from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from math import sqrt
from pathlib import Path

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from mine_mbp_advanced_patterns import AdvancedStrategySpec, build_advanced_trades, summarize_advanced_trades
from optimize_mbp_robust_top10 import (
    Candidate,
    _fold_metrics,
    _load_features,
    _markdown_table,
    _prefixed_summary,
    _spec_parameters,
    _window_metrics,
)
from tradingagents.backtesting.short_patterns import BacktestCosts


SEED_SPEC = AdvancedStrategySpec(
    name="adv_local_mean_reversion_lb5_thr0.6_min1_max5_reverse_vwap_europe_not_low_imb0.35",
    family="mean_reversion",
    lookback=5,
    threshold=0.6,
    min_hold=1,
    max_hold=5,
    exit_mode="reverse_vwap",
    session="europe",
    volatility_filter="not_low",
    imbalance_threshold=0.35,
    max_spread_quantile=0.75,
    min_depth_quantile=0.25,
    stop_loss_points=None,
    take_profit_points=None,
)


def _fmt_param(value: float | int | None) -> str:
    if value is None:
        return "none"
    if isinstance(value, int):
        return str(value)
    return f"{value:.7g}"


def _name(spec: AdvancedStrategySpec) -> str:
    risk_suffix = ""
    if spec.stop_loss_points is not None:
        risk_suffix = f"_sl{_fmt_param(spec.stop_loss_points)}_tp{_fmt_param(spec.take_profit_points)}"
    return (
        f"adv_refined_{spec.family}_lb{spec.lookback}_thr{_fmt_param(spec.threshold)}"
        f"_min{spec.min_hold}_max{spec.max_hold}_{spec.exit_mode}_{spec.session}_{spec.volatility_filter}"
        f"_imb{_fmt_param(spec.imbalance_threshold)}{risk_suffix}"
    )


def generate_refined_specs() -> list[AdvancedStrategySpec]:
    specs: list[AdvancedStrategySpec] = []
    for lookback in [4, 5, 6, 7]:
        for threshold in [0.55, 0.6, 0.65]:
            for min_hold, max_hold in [(1, 4), (1, 5), (1, 6), (2, 5)]:
                for exit_mode, session, volatility_filter in [
                    ("reverse_vwap", "europe", "not_low"),
                    ("reverse", "europe", "not_low"),
                ]:
                    for imbalance_threshold in [0.3, 0.35, 0.4]:
                        for stop_loss, take_profit in [(None, None), (12.0, 24.0)]:
                            spec = replace(
                                SEED_SPEC,
                                name="",
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
    return specs


def _quick_score(summary: dict) -> float:
    net_points = float(summary["net_points"])
    max_drawdown = float(summary["max_drawdown_points"])
    profit_factor = float(summary["profit_factor"])
    trades = int(summary["trades"])
    stability = float(summary.get("stability", 0.0))
    if trades < 200 or profit_factor < 1.25 or net_points <= 0:
        return float("-inf")
    risk_penalty = max(max_drawdown, 1.0)
    return (net_points / risk_penalty) * sqrt(min(trades, 500) / 500) * (0.75 + 0.25 * stability)


def quick_rank(features: pd.DataFrame, min_net_points: float, top_n: int) -> list[Candidate]:
    rows = []
    candidates = []
    specs = generate_refined_specs()
    for index, spec in enumerate(specs, start=1):
        if index % 100 == 0:
            print(f"Quick scan: {index:,}/{len(specs):,}", flush=True)
        trades = build_advanced_trades(features, spec)
        summary = summarize_advanced_trades(spec, trades)
        if int(summary["trades"]) < 200 or float(summary["net_points"]) < min_net_points:
            continue
        score = _quick_score(summary)
        if score == float("-inf"):
            continue
        rows.append(summary | {"quick_score": score})
        candidates.append(Candidate("advanced", spec.name, spec))
    ranked = pd.DataFrame(rows).sort_values(
        ["quick_score", "net_points", "profit_factor", "max_drawdown_points"],
        ascending=[False, False, False, True],
    )
    selected_names = set(ranked.head(top_n)["name"]) if not ranked.empty else set()
    return [candidate for candidate in candidates if candidate.name in selected_names]


def _robust_score(full: dict, folds: dict, worst_cost_score: float) -> float:
    return (
        full["full_score"]
        * max(folds["positive_fold_rate"], 0.01)
        * max(min(full["full_stability"], 1.0), 0.01)
        * max(min(worst_cost_score / max(full["full_score"], 1e-9), 1.0), 0.01)
    )


def robust_rank(
    features: pd.DataFrame,
    candidates: list[Candidate],
    fold_count: int,
    cost_multipliers: list[float],
    window_days: int,
    window_step_days: int,
) -> pd.DataFrame:
    rows = []
    base_costs = BacktestCosts()
    for candidate in candidates:
        full = _prefixed_summary(candidate, features, base_costs, "full")
        folds = _fold_metrics(candidate, features, fold_count, base_costs)
        cost_rows = []
        for multiplier in cost_multipliers:
            costs = BacktestCosts(
                point_value=base_costs.point_value,
                tick_size=base_costs.tick_size,
                slippage_ticks_per_side=base_costs.slippage_ticks_per_side * multiplier,
                commission_per_contract=base_costs.commission_per_contract,
            )
            cost_rows.append(_prefixed_summary(candidate, features, costs, f"cost_{multiplier:g}x"))
        worst_cost_net = min(row[f"cost_{multiplier:g}x_net_points"] for row, multiplier in zip(cost_rows, cost_multipliers))
        worst_cost_score = min(row[f"cost_{multiplier:g}x_score"] for row, multiplier in zip(cost_rows, cost_multipliers))
        window = _window_metrics(candidate, features, BacktestCosts(slippage_ticks_per_side=3.0), window_days, window_step_days)
        live_ready = (
            worst_cost_net > 0
            and folds["positive_fold_rate"] >= 1.0
            and window["positive_window_rate"] >= 1.0
            and window["min_window_net_points"] >= 0
            and window["min_window_trades"] >= 5
            and full["full_trades"] >= 200
            and full["full_profit_factor"] >= 1.25
        )
        row = {
            "name": candidate.name,
            "source": candidate.source,
            "family": candidate.spec.family,
            **_spec_parameters(candidate),
            **full,
            **folds,
            **window,
            "worst_cost_net_points": worst_cost_net,
            "worst_cost_score": worst_cost_score,
            "robust_score": _robust_score(full, folds, worst_cost_score),
            "live_ready_strict": live_ready,
        }
        for cost_row in cost_rows:
            row.update(cost_row)
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["live_ready_strict", "full_net_points", "robust_score", "full_profit_factor"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refine the top MBP mean-reversion strategy for higher yield.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/mbp-refined-mean-reversion.csv")
    parser.add_argument("--report", default="reports/NQM6-mbp-refined-mean-reversion.md")
    parser.add_argument("--min-net-points", type=float, default=1232.375)
    parser.add_argument("--quick-top", type=int, default=80)
    parser.add_argument("--folds", type=int, default=6)
    parser.add_argument("--cost-multipliers", default="1,2,3")
    parser.add_argument("--window-days", type=int, default=10)
    parser.add_argument("--window-step-days", type=int, default=5)
    args = parser.parse_args()

    features = _load_features(Path(args.features_cache))
    cost_multipliers = [float(value) for value in args.cost_multipliers.split(",") if value.strip()]
    candidates = quick_rank(features, args.min_net_points, args.quick_top)
    ranked = robust_rank(features, candidates, args.folds, cost_multipliers, args.window_days, args.window_step_days)
    if ranked.empty:
        raise SystemExit("No refined candidates met quick filters.")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(output, index=False)

    strict = ranked[ranked["live_ready_strict"]].copy()
    top_frame = strict.head(10) if not strict.empty else ranked.head(10)
    report = [
        "# NQM6 MBP Refined Mean-Reversion Search",
        "",
        f"Feature rows: {len(features):,}",
        f"Date range: {features['ts'].min()} to {features['ts'].max()}",
        f"Refined specs: {len(generate_refined_specs()):,}",
        f"Quick candidates: {len(candidates):,}",
        f"Strict live-ready candidates: {len(strict):,}",
        "",
        "Strict live-ready requires positive 6/6 folds, positive 9/9 rolling 10-day windows, non-negative worst 10-day 3x-cost window, 3x-cost net > 0, >= 200 trades, and PF >= 1.25.",
        "",
        _markdown_table(
            top_frame[
                [
                    "name",
                    "full_trades",
                    "full_net_points",
                    "full_max_drawdown_points",
                    "full_profit_factor",
                    "positive_fold_rate",
                    "positive_window_rate",
                    "min_window_net_points",
                    "worst_cost_net_points",
                    "robust_score",
                    "live_ready_strict",
                ]
            ]
        ),
        "",
    ]
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report), encoding="utf-8")

    print(f"Refined specs: {len(generate_refined_specs())}")
    print(f"Quick candidates: {len(candidates)}")
    print(f"Strict live-ready candidates: {len(strict)}")
    print(f"CSV: {output}")
    print(f"Report: {report_path}")
    print()
    print(top_frame[[
        "name",
        "full_trades",
        "full_net_points",
        "full_max_drawdown_points",
        "full_profit_factor",
        "positive_fold_rate",
        "positive_window_rate",
        "min_window_net_points",
        "worst_cost_net_points",
        "robust_score",
        "live_ready_strict",
    ]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
