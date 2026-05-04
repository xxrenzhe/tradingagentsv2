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
    _markdown_table,
    _prefixed_summary,
    _spec_parameters,
    _window_metrics,
)
from tradingagents.backtesting.short_patterns import BacktestCosts


def _fmt_param(value: float | int | None) -> str:
    if value is None:
        return "none"
    if isinstance(value, int):
        return str(value)
    return f"{value:.7g}"


def _name(seed_rank: int, spec: AdvancedStrategySpec) -> str:
    risk_suffix = ""
    if spec.stop_loss_points is not None:
        risk_suffix = f"_sl{_fmt_param(spec.stop_loss_points)}_tp{_fmt_param(spec.take_profit_points)}"
    return (
        f"adv_top{seed_rank}_enhanced_{spec.family}_lb{spec.lookback}_thr{_fmt_param(spec.threshold)}"
        f"_min{spec.min_hold}_max{spec.max_hold}_{spec.exit_mode}_{spec.session}_{spec.volatility_filter}"
        f"_imb{_fmt_param(spec.imbalance_threshold)}{risk_suffix}"
    )


def _near_int(value: int, lower: int = 2, upper: int = 20) -> list[int]:
    return sorted({min(upper, max(lower, value + delta)) for delta in [-2, -1, 0, 1, 2]})


def _near_threshold(spec: AdvancedStrategySpec) -> list[float]:
    if spec.family == "mean_reversion":
        return sorted({round(max(0.1, spec.threshold + delta), 7) for delta in [-0.1, -0.05, 0.0, 0.05, 0.1]})
    return sorted({round(max(0.00005, spec.threshold * factor), 7) for factor in [0.75, 0.9, 1.0, 1.1, 1.25]})


def _variant_specs(seed_rank: int, seed: AdvancedStrategySpec) -> list[AdvancedStrategySpec]:
    specs = []
    variants = []
    variants.extend(("lookback", value) for value in _near_int(seed.lookback) if value != seed.lookback)
    variants.extend(("threshold", value) for value in _near_threshold(seed) if value != seed.threshold)
    variants.extend(("max_hold", value) for value in sorted({max(seed.min_hold + 2, seed.max_hold + delta) for delta in [-2, -1, 1, 2]}) if value != seed.max_hold)
    variants.extend(("exit_mode", value) for value in ["reverse_vwap", "reverse", "time"] if value != seed.exit_mode)
    variants.extend(("session", value) for value in ["europe", "us_rth", "all"] if value != seed.session)
    variants.extend(("volatility_filter", value) for value in ["not_low", "high", "all"] if value != seed.volatility_filter)
    variants.extend(
        ("imbalance_threshold", value)
        for value in sorted({round(max(0.05, min(0.7, seed.imbalance_threshold + delta)), 7) for delta in [-0.1, -0.05, 0.05, 0.1]})
        if value != seed.imbalance_threshold
    )
    variants.extend(("risk_profile", value) for value in [(None, None), (8.0, 16.0), (12.0, 24.0)] if value != (seed.stop_loss_points, seed.take_profit_points))

    for key, value in variants:
        values = {
            "lookback": seed.lookback,
            "threshold": seed.threshold,
            "max_hold": seed.max_hold,
            "exit_mode": seed.exit_mode,
            "session": seed.session,
            "volatility_filter": seed.volatility_filter,
            "imbalance_threshold": seed.imbalance_threshold,
            "risk_profile": (seed.stop_loss_points, seed.take_profit_points),
        } | {key: value}
        stop_loss, take_profit = values["risk_profile"]
        spec = replace(
            seed,
            name="",
            lookback=int(values["lookback"]),
            threshold=float(values["threshold"]),
            max_hold=int(values["max_hold"]),
            exit_mode=str(values["exit_mode"]),
            session=str(values["session"]),
            volatility_filter=str(values["volatility_filter"]),
            imbalance_threshold=float(values["imbalance_threshold"]),
            stop_loss_points=stop_loss,
            take_profit_points=take_profit,
        )
        specs.append(replace(spec, name=_name(seed_rank, spec)))
    return specs


def _passes_live_ready(row: dict) -> bool:
    return (
        row["worst_cost_net_points"] > 0
        and row["positive_fold_rate"] >= 0.80
        and row["positive_window_rate"] >= 0.70
        and row["min_window_trades"] >= 5
        and row["full_trades"] >= 200
        and row["full_profit_factor"] >= 1.25
    )


def _evaluate_candidate(features: pd.DataFrame, candidate: Candidate, fold_count: int, window_days: int, window_step_days: int) -> dict:
    base_costs = BacktestCosts()
    full = _prefixed_summary(candidate, features, base_costs, "full")
    folds = _fold_metrics(candidate, features, fold_count, base_costs)
    costs_3x = BacktestCosts(slippage_ticks_per_side=3.0)
    cost_3x = _prefixed_summary(candidate, features, costs_3x, "cost_3x")
    window = _window_metrics(candidate, features, costs_3x, window_days, window_step_days)
    row = {
        "name": candidate.name,
        "source": candidate.source,
        "family": candidate.spec.family,
        **_spec_parameters(candidate),
        **full,
        **folds,
        **window,
        "worst_cost_net_points": cost_3x["cost_3x_net_points"],
        "worst_cost_score": cost_3x["cost_3x_score"],
    }
    row["live_ready"] = _passes_live_ready(row)
    return row


def _quick_candidate_rows(features: pd.DataFrame, seed_rank: int, baseline: pd.Series, quick_top: int) -> list[Candidate]:
    candidates = []
    quick_rows = []
    for spec in _variant_specs(seed_rank, _advanced_spec_from_row(baseline)):
        candidate = Candidate("advanced", spec.name, spec)
        full = _prefixed_summary(candidate, features, BacktestCosts(), "full")
        if (
            full["full_trades"] >= 200
            and full["full_net_points"] > float(baseline["full_net_points"])
            and full["full_profit_factor"] >= 1.25
        ):
            quick_rows.append({**full, "name": spec.name})
            candidates.append(candidate)
    if not quick_rows:
        return []
    ranked_names = set(
        pd.DataFrame(quick_rows)
        .sort_values(["full_net_points", "full_score", "full_profit_factor"], ascending=[False, False, False])
        .head(quick_top)["name"]
    )
    return [candidate for candidate in candidates if candidate.name in ranked_names]


def assess_enhancements(
    features: pd.DataFrame,
    live_top10: pd.DataFrame,
    quick_top: int,
    fold_count: int,
    window_days: int,
    window_step_days: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    enhanced_rows = []
    summary_rows = []
    for seed_index, baseline in live_top10.head(10).reset_index(drop=True).iterrows():
        seed_rank = seed_index + 1
        print(f"Assessing seed {seed_rank}/10: {baseline['family']} {baseline['name']}", flush=True)
        candidates = _quick_candidate_rows(features, seed_rank, baseline, quick_top)
        print(f"  quick candidates: {len(candidates)}", flush=True)
        evaluated = []
        for candidate in candidates:
            row = _evaluate_candidate(features, candidate, fold_count, window_days, window_step_days)
            evaluated.append(row)
        frame = pd.DataFrame(evaluated)
        if frame.empty:
            best = None
        else:
            frame["seed_rank"] = seed_rank
            frame["seed_name"] = baseline["name"]
            frame["net_delta"] = frame["full_net_points"] - float(baseline["full_net_points"])
            frame["dd_delta"] = frame["full_max_drawdown_points"] - float(baseline["full_max_drawdown_points"])
            frame["pf_delta"] = frame["full_profit_factor"] - float(baseline["full_profit_factor"])
            frame["worst_cost_delta"] = frame["worst_cost_net_points"] - float(baseline["worst_cost_net_points"])
            frame["min_window_delta"] = frame["min_window_net_points"] - float(baseline["min_window_net_points"])
            frame["preserves_core_edge"] = (
                frame["live_ready"]
                & (frame["positive_fold_rate"] >= float(baseline["positive_fold_rate"]))
                & (frame["positive_window_rate"] >= float(baseline["positive_window_rate"]))
                & (frame["worst_cost_net_points"] >= float(baseline["worst_cost_net_points"]))
                & (frame["min_window_net_points"] >= float(baseline["min_window_net_points"]))
            )
            enhanced_rows.append(frame)
            eligible = frame[frame["preserves_core_edge"]].copy()
            if eligible.empty:
                eligible = frame[frame["live_ready"]].copy()
            best = None if eligible.empty else eligible.sort_values(
                ["preserves_core_edge", "full_net_points", "worst_cost_net_points", "min_window_net_points"],
                ascending=[False, False, False, False],
            ).iloc[0]
        summary_rows.append(
            {
                "seed_rank": seed_rank,
                "seed_name": baseline["name"],
                "seed_family": baseline["family"],
                "seed_net_points": float(baseline["full_net_points"]),
                "seed_pf": float(baseline["full_profit_factor"]),
                "seed_min_window_net_points": float(baseline["min_window_net_points"]),
                "seed_worst_cost_net_points": float(baseline["worst_cost_net_points"]),
                "quick_candidates": len(candidates),
                "best_name": "" if best is None else best["name"],
                "best_net_points": 0.0 if best is None else float(best["full_net_points"]),
                "net_delta": 0.0 if best is None else float(best["full_net_points"] - baseline["full_net_points"]),
                "best_pf": 0.0 if best is None else float(best["full_profit_factor"]),
                "pf_delta": 0.0 if best is None else float(best["full_profit_factor"] - baseline["full_profit_factor"]),
                "best_min_window_net_points": 0.0 if best is None else float(best["min_window_net_points"]),
                "min_window_delta": 0.0 if best is None else float(best["min_window_net_points"] - baseline["min_window_net_points"]),
                "best_worst_cost_net_points": 0.0 if best is None else float(best["worst_cost_net_points"]),
                "worst_cost_delta": 0.0 if best is None else float(best["worst_cost_net_points"] - baseline["worst_cost_net_points"]),
                "best_live_ready": False if best is None else bool(best["live_ready"]),
                "preserves_core_edge": False if best is None else bool(best["preserves_core_edge"]),
            }
        )
    all_enhanced = pd.concat(enhanced_rows, ignore_index=True) if enhanced_rows else pd.DataFrame()
    return pd.DataFrame(summary_rows), all_enhanced


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess whether each live-ready Top10 strategy can be locally enhanced.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--live-results", default=".tmp/mbp-live-ready-top10.csv")
    parser.add_argument("--summary-output", default=".tmp/mbp-top10-enhancement-summary.csv")
    parser.add_argument("--candidates-output", default=".tmp/mbp-top10-enhancement-candidates.csv")
    parser.add_argument("--report", default="reports/NQM6-mbp-top10-enhancement-assessment.md")
    parser.add_argument("--quick-top", type=int, default=8)
    parser.add_argument("--folds", type=int, default=6)
    parser.add_argument("--window-days", type=int, default=10)
    parser.add_argument("--window-step-days", type=int, default=5)
    args = parser.parse_args()

    features = _load_features(Path(args.features_cache))
    live_top10 = pd.read_csv(args.live_results).head(10)
    summary, candidates = assess_enhancements(
        features,
        live_top10,
        quick_top=args.quick_top,
        fold_count=args.folds,
        window_days=args.window_days,
        window_step_days=args.window_step_days,
    )
    Path(args.summary_output).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary_output, index=False)
    candidates.to_csv(args.candidates_output, index=False)
    enhanced_count = int(summary["best_live_ready"].sum())
    preserved_count = int(summary["preserves_core_edge"].sum())
    report_lines = [
        "# NQM6 MBP Top10 Enhancement Assessment",
        "",
        f"Feature rows: {len(features):,}",
        f"Date range: {features['ts'].min()} to {features['ts'].max()}",
        f"Live-ready Top10 assessed: {len(summary)}",
        f"Enhanced while still live-ready: {enhanced_count}",
        f"Enhanced while preserving core edge: {preserved_count}",
        "",
        "Preserve core edge means: live-ready, net points higher, positive fold rate not lower, positive window rate not lower, 3x-cost net not lower, and worst 10-day window not lower.",
        "",
        _markdown_table(
            summary[
                [
                    "seed_rank",
                    "seed_family",
                    "seed_net_points",
                    "quick_candidates",
                    "best_net_points",
                    "net_delta",
                    "pf_delta",
                    "min_window_delta",
                    "worst_cost_delta",
                    "best_live_ready",
                    "preserves_core_edge",
                ]
            ]
        ),
        "",
    ]
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Summary: {args.summary_output}")
    print(f"Candidates: {args.candidates_output}")
    print(f"Report: {args.report}")
    print(summary[[
        "seed_rank",
        "seed_family",
        "seed_net_points",
        "quick_candidates",
        "best_net_points",
        "net_delta",
        "pf_delta",
        "min_window_delta",
        "worst_cost_delta",
        "best_live_ready",
        "preserves_core_edge",
    ]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
