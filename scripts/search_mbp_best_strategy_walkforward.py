from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from mine_mbp_advanced_patterns import AdvancedStrategySpec, build_advanced_trades, summarize_advanced_trades
from optimize_mbp_robust_top10 import Candidate, _load_features, _markdown_table, _prefixed_summary, _spec_parameters, _window_metrics
from tradingagents.backtesting.short_patterns import BacktestCosts


SEED_SPEC = AdvancedStrategySpec(
    name="adv_stable_refined_defensive_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_not_low_imb0.3",
    family="mean_reversion",
    lookback=6,
    threshold=0.8,
    min_hold=1,
    max_hold=6,
    exit_mode="reverse",
    session="europe",
    volatility_filter="not_low",
    imbalance_threshold=0.3,
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
        f"adv_wf_best_{spec.family}_lb{spec.lookback}_thr{_fmt_param(spec.threshold)}"
        f"_min{spec.min_hold}_max{spec.max_hold}_{spec.exit_mode}_{spec.session}_{spec.volatility_filter}"
        f"_imb{_fmt_param(spec.imbalance_threshold)}{risk_suffix}"
    )


def generate_neighbor_specs() -> list[AdvancedStrategySpec]:
    specs: list[AdvancedStrategySpec] = []
    seen = set()
    for lookback in [4, 5, 6, 7, 8]:
        for threshold in [0.7, 0.75, 0.8, 0.85, 0.9]:
            for min_hold, max_hold in [(1, 5), (1, 6), (1, 7), (2, 6)]:
                for exit_mode in ["reverse", "reverse_vwap"]:
                    for session in ["europe"]:
                        for volatility_filter in ["not_low", "all"]:
                            for imbalance_threshold in [0.25, 0.3, 0.35]:
                                for risk_profile in [(None, None), (10.0, 16.0), (16.0, 24.0)]:
                                    if max_hold <= min_hold:
                                        continue
                                    signature = (
                                        lookback,
                                        threshold,
                                        min_hold,
                                        max_hold,
                                        exit_mode,
                                        session,
                                        volatility_filter,
                                        imbalance_threshold,
                                        risk_profile,
                                    )
                                    if signature in seen:
                                        continue
                                    seen.add(signature)
                                    stop_loss, take_profit = risk_profile
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
    return sorted(specs, key=_spec_distance)


def _spec_distance(spec: AdvancedStrategySpec) -> tuple:
    return (
        abs(spec.lookback - SEED_SPEC.lookback),
        abs(float(spec.threshold) - SEED_SPEC.threshold),
        abs(spec.min_hold - SEED_SPEC.min_hold),
        abs(spec.max_hold - SEED_SPEC.max_hold),
        0 if spec.exit_mode == SEED_SPEC.exit_mode else 1,
        0 if spec.volatility_filter == SEED_SPEC.volatility_filter else 1,
        abs(float(spec.imbalance_threshold or 0) - float(SEED_SPEC.imbalance_threshold or 0)),
        0 if (spec.stop_loss_points, spec.take_profit_points) == (SEED_SPEC.stop_loss_points, SEED_SPEC.take_profit_points) else 1,
    )


def _dates(features: pd.DataFrame) -> list:
    dates = sorted(features["trade_date"].dropna().unique())
    if not dates:
        raise SystemExit("No trade dates found in feature cache.")
    return dates


def _score(summary: dict) -> float:
    trades = int(summary["trades"])
    net_points = float(summary["net_points"])
    max_drawdown = max(float(summary["max_drawdown_points"]), 1.0)
    profit_factor = float(summary["profit_factor"])
    stability = float(summary.get("stability", 0.0))
    if trades < 40 or net_points <= 0 or profit_factor < 1.2:
        return float("-inf")
    return (
        net_points * 0.18
        + (net_points / max_drawdown) * 120
        + min(profit_factor, 3.0) * 220
        + min(stability, 1.0) * 420
        - max_drawdown * 0.35
    )


def preselect_specs(features: pd.DataFrame, specs: list[AdvancedStrategySpec], limit: int) -> list[AdvancedStrategySpec]:
    if limit <= 0 or limit >= len(specs):
        return specs
    rows = []
    for index, spec in enumerate(specs, start=1):
        if index % 25 == 0:
            print(f"Preselect scan: {index:,}/{len(specs):,}", flush=True)
        trades = build_advanced_trades(features, spec)
        summary = summarize_advanced_trades(spec, trades)
        score = _score(summary)
        if score == float("-inf"):
            continue
        rows.append({"name": spec.name, "preselect_score": score, **summary})
    if not rows:
        return []
    ranked = pd.DataFrame(rows).sort_values(
        ["preselect_score", "net_points", "profit_factor", "max_drawdown_points"],
        ascending=[False, False, False, True],
    )
    selected = set(ranked.head(limit)["name"])
    return [spec for spec in specs if spec.name in selected]


def _full_summary(features: pd.DataFrame, spec: AdvancedStrategySpec, prefix: str) -> dict:
    candidate = Candidate("advanced", spec.name, spec)
    summary = _prefixed_summary(candidate, features, BacktestCosts(), prefix)
    stress = _prefixed_summary(candidate, features, BacktestCosts(slippage_ticks_per_side=3.0), f"{prefix}_cost_3x")
    window = _window_metrics(candidate, features, BacktestCosts(slippage_ticks_per_side=3.0), 10, 5)
    return summary | stress | {f"{prefix}_{key}": value for key, value in window.items()}


def train_selected_walkforward(
    features: pd.DataFrame,
    specs: list[AdvancedStrategySpec],
    *,
    train_days: int,
    test_days: int,
    step_days: int,
    quick_top: int,
) -> pd.DataFrame:
    dates = _dates(features)
    rows = []
    fold = 0
    for train_start in range(0, len(dates) - train_days - test_days + 1, step_days):
        train_dates = set(dates[train_start : train_start + train_days])
        test_dates = set(dates[train_start + train_days : train_start + train_days + test_days])
        train = features[features["trade_date"].isin(train_dates)].reset_index(drop=True)
        test = features[features["trade_date"].isin(test_dates)].reset_index(drop=True)
        fold += 1
        quick_rows = []
        for spec in specs:
            train_trades = build_advanced_trades(train, spec)
            train_summary = summarize_advanced_trades(spec, train_trades)
            score = _score(train_summary)
            if score == float("-inf"):
                continue
            quick_rows.append({"name": spec.name, "train_score": score, **train_summary})
        if not quick_rows:
            continue
        quick = pd.DataFrame(quick_rows).sort_values(
            ["train_score", "net_points", "profit_factor", "max_drawdown_points"],
            ascending=[False, False, False, True],
        )
        selected = set(quick.head(quick_top)["name"])
        for spec in specs:
            if spec.name not in selected:
                continue
            train_row = quick[quick["name"].eq(spec.name)].iloc[0].to_dict()
            test_trades = build_advanced_trades(test, spec)
            test_summary = summarize_advanced_trades(spec, test_trades)
            rows.append(
                {
                    "fold": fold,
                    "name": spec.name,
                    "train_start": min(train_dates),
                    "train_end": max(train_dates),
                    "test_start": min(test_dates),
                    "test_end": max(test_dates),
                    "train_rank": int(quick.index.get_loc(quick[quick["name"].eq(spec.name)].index[0]) + 1),
                    "train_score": float(train_row["train_score"]),
                    "train_trades": int(train_row["trades"]),
                    "train_net_points": float(train_row["net_points"]),
                    "train_max_drawdown_points": float(train_row["max_drawdown_points"]),
                    "train_profit_factor": float(train_row["profit_factor"]),
                    "train_stability": float(train_row["stability"]),
                    "test_trades": int(test_summary["trades"]),
                    "test_net_points": float(test_summary["net_points"]),
                    "test_max_drawdown_points": float(test_summary["max_drawdown_points"]),
                    "test_profit_factor": float(test_summary["profit_factor"]),
                    "test_win_rate": float(test_summary["win_rate"]),
                    "test_stability": float(test_summary["stability"]),
                }
            )
    return pd.DataFrame(rows)


def aggregate_walkforward(walkforward: pd.DataFrame, features: pd.DataFrame, specs: list[AdvancedStrategySpec]) -> pd.DataFrame:
    if walkforward.empty:
        return walkforward
    spec_lookup = {spec.name: spec for spec in specs}
    rows = []
    grouped = walkforward.groupby("name", sort=False)
    for name, group in grouped:
        spec = spec_lookup[name]
        test_nets = pd.to_numeric(group["test_net_points"], errors="coerce")
        positive_folds = int((test_nets > 0).sum())
        test_trades = int(pd.to_numeric(group["test_trades"], errors="coerce").sum())
        test_net = float(test_nets.sum())
        test_drawdown = float(pd.to_numeric(group["test_max_drawdown_points"], errors="coerce").max())
        full = _full_summary(features, spec, "full")
        stress_net = float(full.get("full_cost_3x_net_points", 0.0))
        positive_window_rate = float(full.get("full_positive_window_rate", 0.0))
        min_window_net = float(full.get("full_min_window_net_points", 0.0))
        full_net = float(full["full_net_points"])
        full_drawdown = max(float(full["full_max_drawdown_points"]), 1.0)
        robust_score = (
            test_net * 0.30
            + stress_net * 0.20
            + (full_net / full_drawdown) * 180
            + min(float(full["full_profit_factor"]), 3.0) * 320
            + min(float(full["full_stability"]), 1.0) * 900
            + (positive_folds / len(group)) * 550
            + positive_window_rate * 650
            + max(min_window_net * 0.35, -250)
            - float(full["full_max_drawdown_points"]) * 0.35
        )
        rows.append(
            {
                "name": name,
                "source": "advanced",
                "family": spec.family,
                **_spec_parameters(Candidate("advanced", name, spec)),
                "folds_selected": int(len(group)),
                "wf_positive_fold_count": positive_folds,
                "wf_positive_fold_rate": positive_folds / len(group),
                "wf_test_trades": test_trades,
                "wf_test_net_points": test_net,
                "wf_max_fold_drawdown_points": test_drawdown,
                **full,
                "stress_net_points": stress_net,
                "best_walkforward_score": robust_score,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["wf_positive_fold_rate", "best_walkforward_score", "wf_test_net_points", "stress_net_points"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def write_report(path: Path, aggregated: pd.DataFrame, walkforward: pd.DataFrame, features: pd.DataFrame, spec_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if aggregated.empty:
        path.write_text("# NQM6 Best-Strategy Walk-Forward Neighbor Search\n\nNo candidates selected.\n", encoding="utf-8")
        return
    best = aggregated.iloc[0]
    columns = [
        "name",
        "folds_selected",
        "wf_positive_fold_rate",
        "wf_test_trades",
        "wf_test_net_points",
        "full_trades",
        "full_net_points",
        "full_max_drawdown_points",
        "full_profit_factor",
        "full_win_rate",
        "full_stability",
        "full_positive_window_rate",
        "full_min_window_net_points",
        "stress_net_points",
        "best_walkforward_score",
    ]
    lines = [
        "# NQM6 Best-Strategy Walk-Forward Neighbor Search",
        "",
        "## Verdict",
        "",
        f"Best train-selected neighbor: `{best['name']}`.",
        "",
        "- Search is centered on the current best non-2R mean-reversion strategy.",
        "- Each fold ranks parameters on the training window, then evaluates the selected neighbors on future test dates.",
        "- This is still research evidence; live readiness remains blocked by history span and paper outcomes.",
        "",
        "## Run Metadata",
        "",
        f"- Feature rows: {len(features):,}",
        f"- Date range: {features['ts'].min()} to {features['ts'].max()}",
        f"- Neighbor specs: {spec_count:,}",
        f"- Fold candidate rows: {len(walkforward):,}",
        "",
        "## Top Candidates",
        "",
        _markdown_table(aggregated.head(20)[columns]),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk-forward local search around the current best MBP strategy.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/mbp-best-strategy-walkforward-neighbors.csv")
    parser.add_argument("--fold-output", default=".tmp/mbp-best-strategy-walkforward-neighbor-folds.csv")
    parser.add_argument("--report", default="reports/NQM6-best-strategy-walkforward-neighbors.md")
    parser.add_argument("--train-days", type=int, default=18)
    parser.add_argument("--test-days", type=int, default=5)
    parser.add_argument("--step-days", type=int, default=5)
    parser.add_argument("--quick-top", type=int, default=8)
    parser.add_argument("--preselect-limit", type=int, default=240)
    parser.add_argument("--max-specs", type=int, default=0)
    args = parser.parse_args()

    features = _load_features(Path(args.features_cache))
    specs = generate_neighbor_specs()
    if args.max_specs > 0:
        specs = specs[: args.max_specs]
    all_spec_count = len(specs)
    specs = preselect_specs(features, specs, args.preselect_limit)
    if not specs:
        raise SystemExit("No preselected candidates met quick filters.")
    walkforward = train_selected_walkforward(
        features,
        specs,
        train_days=args.train_days,
        test_days=args.test_days,
        step_days=args.step_days,
        quick_top=args.quick_top,
    )
    if walkforward.empty:
        raise SystemExit("No walk-forward candidates selected.")
    aggregated = aggregate_walkforward(walkforward, features, specs)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    aggregated.to_csv(output, index=False)
    fold_output = Path(args.fold_output)
    fold_output.parent.mkdir(parents=True, exist_ok=True)
    walkforward.to_csv(fold_output, index=False)
    write_report(Path(args.report), aggregated, walkforward, features, all_spec_count)

    print(f"Neighbor specs: {all_spec_count:,}")
    print(f"Preselected specs: {len(specs):,}")
    print(f"Fold candidate rows: {len(walkforward):,}")
    print(f"Aggregated candidates: {len(aggregated):,}")
    print(f"CSV: {output}")
    print(f"Report: {args.report}")
    print(
        aggregated.head(10)[
            [
                "name",
                "folds_selected",
                "wf_positive_fold_rate",
                "wf_test_net_points",
                "full_net_points",
                "full_max_drawdown_points",
                "full_profit_factor",
                "full_stability",
                "stress_net_points",
                "best_walkforward_score",
            ]
        ].to_string(index=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
