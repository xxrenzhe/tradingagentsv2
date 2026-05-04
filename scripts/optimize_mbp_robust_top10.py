from __future__ import annotations

import argparse
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Iterator

import pandas as pd

from mine_mbp_advanced_patterns import (
    AdvancedStrategySpec,
    build_advanced_trades,
    generate_advanced_specs,
    summarize_advanced_trades,
)
from tradingagents.backtesting.short_patterns import (
    BacktestCosts,
    StrategySpec,
    build_trades,
    generate_strategy_specs,
    summarize_trades,
)


@dataclass(frozen=True)
class Candidate:
    source: str
    name: str
    spec: StrategySpec | AdvancedStrategySpec


def _fmt_param(value: float | int | None) -> str:
    if value is None:
        return "none"
    if isinstance(value, int):
        return str(value)
    return f"{value:.7g}"


def _load_features(path: Path) -> pd.DataFrame:
    cache = pd.read_pickle(path)
    frames = [frame for frame in cache.values() if isinstance(frame, pd.DataFrame) and not frame.empty]
    if not frames:
        raise SystemExit(f"No feature frames found in {path}")
    features = pd.concat(frames, ignore_index=True).sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    features["ts"] = pd.to_datetime(features["ts"], utc=True)
    features["return_1m"] = pd.to_numeric(features["Close"], errors="coerce").pct_change()
    features["realized_vol_30"] = features["return_1m"].rolling(30).std()
    features["trade_date"] = features["ts"].dt.date
    return features


def _score_summary(summary: dict) -> float:
    net_points = float(summary["net_points"])
    max_drawdown = float(summary["max_drawdown_points"])
    tail_loss = abs(float(summary["tail_loss_p05"]))
    stability = float(summary.get("stability", 0.0))
    trade_count = int(summary["trades"])
    risk_denominator = max(max_drawdown, tail_loss, 1.0)
    return float((net_points / risk_denominator) * sqrt(min(trade_count, 100) / 100) * (0.75 + 0.25 * stability))


def _empty_summary(candidate: Candidate, prefix: str) -> dict:
    return {
        f"{prefix}_trades": 0,
        f"{prefix}_net_points": 0.0,
        f"{prefix}_max_drawdown_points": 0.0,
        f"{prefix}_profit_factor": 0.0,
        f"{prefix}_win_rate": 0.0,
        f"{prefix}_stability": 0.0,
        f"{prefix}_score": 0.0,
    }


def _summarize_candidate(candidate: Candidate, features: pd.DataFrame, costs: BacktestCosts) -> dict:
    if features.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "max_drawdown_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "tail_loss_p05": 0.0,
            "stability": 0.0,
            "score": 0.0,
        }
    if candidate.source == "base":
        trades = build_trades(features.reset_index(drop=True), candidate.spec, costs)
        summary = summarize_trades(candidate.spec, trades, costs)
    else:
        trades = build_advanced_trades(features.reset_index(drop=True), candidate.spec, costs)
        summary = summarize_advanced_trades(candidate.spec, trades, costs)
    summary["score"] = _score_summary(summary)
    return summary


def _prefixed_summary(candidate: Candidate, features: pd.DataFrame, costs: BacktestCosts, prefix: str) -> dict:
    summary = _summarize_candidate(candidate, features, costs)
    return {
        f"{prefix}_trades": int(summary["trades"]),
        f"{prefix}_net_points": float(summary["net_points"]),
        f"{prefix}_max_drawdown_points": float(summary["max_drawdown_points"]),
        f"{prefix}_profit_factor": float(summary["profit_factor"]),
        f"{prefix}_win_rate": float(summary["win_rate"]),
        f"{prefix}_stability": float(summary.get("stability", 0.0)),
        f"{prefix}_score": float(summary["score"]),
    }


def _spec_parameters(candidate: Candidate) -> dict:
    spec = candidate.spec
    common = {
        "lookback": spec.lookback,
        "threshold": spec.threshold,
        "imbalance_threshold": spec.imbalance_threshold,
        "max_spread_quantile": spec.max_spread_quantile,
        "min_depth_quantile": spec.min_depth_quantile,
        "stop_loss_points": spec.stop_loss_points,
        "take_profit_points": spec.take_profit_points,
    }
    if candidate.source == "base":
        return common | {
            "holding_minutes": spec.holding_minutes,
            "min_hold": pd.NA,
            "max_hold": pd.NA,
            "exit_mode": "time",
            "session": "all",
            "volatility_filter": "all",
        }
    return common | {
        "holding_minutes": pd.NA,
        "min_hold": spec.min_hold,
        "max_hold": spec.max_hold,
        "exit_mode": spec.exit_mode,
        "session": spec.session,
        "volatility_filter": spec.volatility_filter,
    }


def _fold_masks(features: pd.DataFrame, fold_count: int) -> list[pd.Series]:
    dates = pd.Series(sorted(features["trade_date"].dropna().unique()))
    if dates.empty:
        raise SystemExit("No trade dates found in feature cache.")
    fold_count = max(1, min(fold_count, len(dates)))
    fold_ids = pd.qcut(pd.RangeIndex(len(dates)), q=fold_count, labels=False, duplicates="drop")
    folds = []
    for fold_id in sorted(set(fold_ids)):
        fold_dates = set(dates[fold_ids == fold_id])
        folds.append(features["trade_date"].isin(fold_dates))
    return folds


def _fold_metrics(candidate: Candidate, features: pd.DataFrame, fold_count: int, costs: BacktestCosts) -> dict:
    folds = _fold_masks(features, fold_count)
    fold_scores = []
    fold_nets = []
    fold_drawdowns = []
    positive_folds = 0
    for index, mask in enumerate(folds, start=1):
        summary = _summarize_candidate(candidate, features.loc[mask].reset_index(drop=True), costs)
        fold_scores.append(float(summary["score"]))
        fold_nets.append(float(summary["net_points"]))
        fold_drawdowns.append(float(summary["max_drawdown_points"]))
        positive_folds += int(float(summary["net_points"]) > 0)
    return {
        "fold_count": len(folds),
        "positive_fold_count": positive_folds,
        "positive_fold_rate": positive_folds / len(folds),
        "min_fold_net_points": min(fold_nets),
        "median_fold_net_points": float(pd.Series(fold_nets).median()),
        "avg_fold_score": float(pd.Series(fold_scores).mean()),
        "min_fold_score": min(fold_scores),
        "max_fold_drawdown_points": max(fold_drawdowns),
    }


def _rolling_window_masks(features: pd.DataFrame, window_days: int, step_days: int) -> list[pd.Series]:
    dates = list(sorted(features["trade_date"].dropna().unique()))
    if not dates:
        raise SystemExit("No trade dates found in feature cache.")
    window_days = max(1, min(window_days, len(dates)))
    step_days = max(1, step_days)
    masks = []
    for start in range(0, len(dates) - window_days + 1, step_days):
        window_dates = set(dates[start : start + window_days])
        masks.append(features["trade_date"].isin(window_dates))
    if not masks:
        masks.append(features["trade_date"].isin(set(dates)))
    return masks


def _window_metrics(
    candidate: Candidate,
    features: pd.DataFrame,
    costs: BacktestCosts,
    window_days: int,
    step_days: int,
) -> dict:
    masks = _rolling_window_masks(features, window_days, step_days)
    nets = []
    drawdowns = []
    scores = []
    trades = []
    for mask in masks:
        summary = _summarize_candidate(candidate, features.loc[mask].reset_index(drop=True), costs)
        nets.append(float(summary["net_points"]))
        drawdowns.append(float(summary["max_drawdown_points"]))
        scores.append(float(summary["score"]))
        trades.append(int(summary["trades"]))
    positive_windows = sum(value > 0 for value in nets)
    return {
        "window_count": len(masks),
        "positive_window_count": positive_windows,
        "positive_window_rate": positive_windows / len(masks),
        "min_window_net_points": min(nets),
        "median_window_net_points": float(pd.Series(nets).median()),
        "max_window_drawdown_points": max(drawdowns),
        "min_window_score": min(scores),
        "min_window_trades": min(trades),
    }


def _candidate_pool(base_results: Path, advanced_results: Path, base_limit: int, advanced_limit: int) -> list[Candidate]:
    base_ranked = pd.read_csv(base_results).head(base_limit)["name"].tolist()
    advanced_ranked = pd.read_csv(advanced_results).head(advanced_limit)["name"].tolist()
    base_lookup = {spec.name: spec for spec in generate_strategy_specs()}
    advanced_lookup = {spec.name: spec for spec in generate_advanced_specs()}
    candidates: list[Candidate] = []
    for name in base_ranked:
        spec = base_lookup.get(name)
        if spec is not None:
            candidates.append(Candidate("base", name, spec))
    for name in advanced_ranked:
        spec = advanced_lookup.get(name)
        if spec is not None:
            candidates.append(Candidate("advanced", name, spec))
    return candidates


def _advanced_neighbor_name(spec: AdvancedStrategySpec) -> str:
    risk_suffix = ""
    if spec.stop_loss_points is not None:
        risk_suffix = f"_sl{_fmt_param(spec.stop_loss_points)}_tp{_fmt_param(spec.take_profit_points)}"
    return (
        f"adv_local_{spec.family}_lb{spec.lookback}_thr{_fmt_param(spec.threshold)}"
        f"_min{spec.min_hold}_max{spec.max_hold}_{spec.exit_mode}_{spec.session}_{spec.volatility_filter}"
        f"_imb{_fmt_param(spec.imbalance_threshold)}{risk_suffix}"
    )


def _advanced_neighbors(seed: AdvancedStrategySpec) -> Iterator[AdvancedStrategySpec]:
    variants = []
    variants.extend(("lookback", value) for value in sorted({max(2, seed.lookback - 2), seed.lookback + 2, seed.lookback + 5}))
    variants.extend(("threshold", value) for value in sorted({round(seed.threshold * 0.75, 7), round(seed.threshold * 1.25, 7), round(seed.threshold * 1.5, 7)}))
    variants.extend(("max_hold", value) for value in sorted({max(seed.min_hold + 2, seed.max_hold - 2), seed.max_hold + 2, seed.max_hold + 5}))
    variants.extend(("exit_mode", value) for value in ["time", "reverse", "reverse_vwap"] if value != seed.exit_mode)
    variants.extend(("session", value) for value in ["all", "us_rth", "europe"] if value != seed.session)
    variants.extend(("volatility_filter", value) for value in ["all", "not_low", "high"] if value != seed.volatility_filter)
    variants.extend(("imbalance_threshold", value) for value in [0.2, 0.5] if value != seed.imbalance_threshold)
    variants.extend(("risk_profile", value) for value in [(None, None), (8.0, 16.0), (12.0, 24.0)] if value != (seed.stop_loss_points, seed.take_profit_points))

    base_values = {
        "lookback": seed.lookback,
        "threshold": seed.threshold,
        "max_hold": seed.max_hold,
        "exit_mode": seed.exit_mode,
        "session": seed.session,
        "volatility_filter": seed.volatility_filter,
        "imbalance_threshold": seed.imbalance_threshold,
        "risk_profile": (seed.stop_loss_points, seed.take_profit_points),
    }
    for key, value in variants:
        values = base_values | {key: value}
        stop_loss, take_profit = values["risk_profile"]
        spec = AdvancedStrategySpec(
            name="",
            family=seed.family,
            lookback=int(values["lookback"]),
            threshold=float(values["threshold"]),
            min_hold=seed.min_hold,
            max_hold=int(values["max_hold"]),
            exit_mode=str(values["exit_mode"]),
            session=str(values["session"]),
            volatility_filter=str(values["volatility_filter"]),
            imbalance_threshold=float(values["imbalance_threshold"]) if values["imbalance_threshold"] is not None else None,
            max_spread_quantile=seed.max_spread_quantile,
            min_depth_quantile=seed.min_depth_quantile,
            stop_loss_points=stop_loss,
            take_profit_points=take_profit,
        )
        yield spec.__class__(**(spec.__dict__ | {"name": _advanced_neighbor_name(spec)}))


def add_local_advanced_candidates(
    candidates: list[Candidate],
    advanced_results: Path,
    seed_limit: int,
    max_neighbors: int,
) -> list[Candidate]:
    if seed_limit <= 0 or max_neighbors <= 0 or not advanced_results.exists():
        return candidates
    advanced_lookup = {spec.name: spec for spec in generate_advanced_specs()}
    seed_names = pd.read_csv(advanced_results).head(seed_limit)["name"].tolist()
    seeds = [advanced_lookup[name] for name in seed_names if name in advanced_lookup]
    existing_names = {candidate.name for candidate in candidates}
    local_candidates = []
    for seed in seeds:
        for spec in _advanced_neighbors(seed):
            if spec.name in existing_names:
                continue
            existing_names.add(spec.name)
            local_candidates.append(Candidate("advanced", spec.name, spec))
            if len(local_candidates) >= max_neighbors:
                return candidates + local_candidates
    return candidates + local_candidates


def rank_candidates(
    features: pd.DataFrame,
    candidates: list[Candidate],
    fold_count: int,
    cost_multipliers: list[float],
) -> pd.DataFrame:
    rows = []
    base_costs = BacktestCosts()
    for candidate in candidates:
        full = _prefixed_summary(candidate, features, base_costs, "full")
        if full["full_trades"] == 0:
            continue
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
        robust_score = (
            full["full_score"]
            * max(folds["positive_fold_rate"], 0.01)
            * max(min(full["full_stability"], 1.0), 0.01)
            * max(min(worst_cost_score / max(full["full_score"], 1e-9), 1.0), 0.01)
        )
        row = {
            "name": candidate.name,
            "source": candidate.source,
            "family": candidate.spec.family,
            **_spec_parameters(candidate),
            **full,
            **folds,
            "worst_cost_net_points": worst_cost_net,
            "worst_cost_score": worst_cost_score,
            "robust_score": robust_score,
        }
        for cost_row in cost_rows:
            row.update(cost_row)
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["robust_score", "full_score", "full_net_points", "positive_fold_rate"],
        ascending=[False, False, False, False],
    )


def add_live_readiness(
    features: pd.DataFrame,
    ranked: pd.DataFrame,
    candidates: list[Candidate],
    window_days: int,
    step_days: int,
) -> pd.DataFrame:
    candidate_lookup = {candidate.name: candidate for candidate in candidates}
    stress_costs = BacktestCosts(slippage_ticks_per_side=3.0)
    rows = []
    for _, row in ranked.iterrows():
        candidate = candidate_lookup.get(row["name"])
        if candidate is None:
            continue
        window = _window_metrics(candidate, features, stress_costs, window_days, step_days)
        live_score = (
            float(row["robust_score"])
            * max(window["positive_window_rate"], 0.01)
            * max(min(float(row["positive_fold_rate"]), 1.0), 0.01)
            * max(min(float(row["worst_cost_score"]) / max(float(row["full_score"]), 1e-9), 1.0), 0.01)
        )
        live_ready = (
            float(row["worst_cost_net_points"]) > 0
            and float(row["positive_fold_rate"]) >= 0.80
            and window["positive_window_rate"] >= 0.70
            and window["min_window_trades"] >= 5
            and float(row["full_trades"]) >= 200
            and float(row["full_profit_factor"]) >= 1.25
        )
        rows.append(
            {
                **row.to_dict(),
                **window,
                "live_score": live_score,
                "live_ready": live_ready,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["live_ready", "live_score", "robust_score", "full_net_points"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def deduplicate_ranked_results(results: pd.DataFrame) -> pd.DataFrame:
    deduped = results.copy()
    deduped["dedupe_key"] = deduped.apply(
        lambda row: (
            row["family"],
            int(row["full_trades"]),
            round(float(row["full_net_points"]), 4),
            round(float(row["full_max_drawdown_points"]), 4),
            round(float(row["full_profit_factor"]), 6),
        ),
        axis=1,
    )
    deduped = deduped.sort_values(
        ["robust_score", "source", "full_score"],
        ascending=[False, True, False],
    )
    return deduped.drop_duplicates("dedupe_key", keep="first").drop(columns=["dedupe_key"]).reset_index(drop=True)


def _local_robustness_metrics(results: pd.DataFrame) -> pd.DataFrame:
    local = results.copy()
    key_columns = ["source", "family", "lookback", "exit_mode", "session", "volatility_filter"]
    if not set(key_columns).issubset(local.columns):
        local["local_neighbor_count"] = 1
        local["local_positive_rate"] = (local["robust_score"] > 0).astype(float)
        local["local_median_robust_score"] = local["robust_score"]
        local["local_best_robust_score"] = local["robust_score"]
        local["local_rank_score"] = local["robust_score"]
        return local
    grouped = local.groupby(key_columns, dropna=False)
    aggregates = grouped.agg(
        local_neighbor_count=("name", "count"),
        local_positive_rate=("robust_score", lambda values: float((values > 0).mean())),
        local_median_robust_score=("robust_score", "median"),
        local_best_robust_score=("robust_score", "max"),
        local_min_window_net_points=("min_window_net_points", "median") if "min_window_net_points" in local else ("robust_score", "min"),
    ).reset_index()
    enriched = local.merge(aggregates, on=key_columns, how="left")
    enriched["local_rank_score"] = (
        enriched["robust_score"]
        * (0.70 + 0.30 * enriched["local_positive_rate"])
        * enriched["local_median_robust_score"].clip(lower=0.01)
        / enriched["local_best_robust_score"].clip(lower=0.01)
    )
    return enriched


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame.iterrows():
        values = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank robust MBP strategy Top10 using folds and cost sensitivity.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--base-results", default=".tmp/mbp-history-patterns-full.csv")
    parser.add_argument("--advanced-results", default=".tmp/mbp-advanced-patterns.csv")
    parser.add_argument("--output", default=".tmp/mbp-robust-top10.csv")
    parser.add_argument("--top-output", default="reports/NQM6-mbp-robust-top10.md")
    parser.add_argument("--live-output", default=".tmp/mbp-live-ready-top10.csv")
    parser.add_argument("--live-report", default="reports/NQM6-mbp-live-ready-top10.md")
    parser.add_argument("--base-limit", type=int, default=40)
    parser.add_argument("--advanced-limit", type=int, default=80)
    parser.add_argument("--local-seed-limit", type=int, default=12)
    parser.add_argument("--max-local-candidates", type=int, default=80)
    parser.add_argument("--folds", type=int, default=6)
    parser.add_argument("--cost-multipliers", default="1,2,3")
    parser.add_argument("--window-days", type=int, default=10)
    parser.add_argument("--window-step-days", type=int, default=5)
    args = parser.parse_args()

    features = _load_features(Path(args.features_cache))
    cost_multipliers = [float(value) for value in args.cost_multipliers.split(",") if value.strip()]
    candidates = _candidate_pool(Path(args.base_results), Path(args.advanced_results), args.base_limit, args.advanced_limit)
    candidates = add_local_advanced_candidates(
        candidates,
        Path(args.advanced_results),
        args.local_seed_limit,
        args.max_local_candidates,
    )
    raw_results = rank_candidates(features, candidates, args.folds, cost_multipliers)
    if raw_results.empty:
        raise SystemExit("No robust candidates were ranked.")
    results = deduplicate_ranked_results(raw_results)
    live_results = add_live_readiness(features, results, candidates, args.window_days, args.window_step_days)
    live_results = _local_robustness_metrics(live_results).sort_values(
        ["live_ready", "local_rank_score", "live_score", "robust_score", "full_net_points"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output, index=False)
    live_output = Path(args.live_output)
    live_output.parent.mkdir(parents=True, exist_ok=True)
    live_results.to_csv(live_output, index=False)

    top10 = results.head(10)
    markdown = [
        "# NQM6 MBP Robust Top10 Strategies",
        "",
        f"Feature rows: {len(features):,}",
        f"Date range: {features['ts'].min()} to {features['ts'].max()}",
        f"Candidates ranked: {len(raw_results):,}",
        f"Unique strategy profiles: {len(results):,}",
        f"Local advanced candidates added: {max(0, len(candidates) - args.base_limit - args.advanced_limit):,}",
        f"Folds: {args.folds}",
        f"Cost multipliers: {', '.join(f'{value:g}x' for value in cost_multipliers)}",
        "",
        "Ranking uses full-history score, positive fold rate, full-history stability, and worst cost-sensitivity score.",
        "",
        _markdown_table(top10[
            [
                "name",
                "source",
                "family",
                "full_trades",
                "full_net_points",
                "full_max_drawdown_points",
                "full_profit_factor",
                "positive_fold_rate",
                "min_fold_net_points",
                "worst_cost_net_points",
                "robust_score",
            ]
        ]),
        "",
    ]
    top_output = Path(args.top_output)
    top_output.parent.mkdir(parents=True, exist_ok=True)
    top_output.write_text("\n".join(markdown), encoding="utf-8")
    live_top10 = live_results.head(10)
    live_markdown = [
        "# NQM6 MBP Live-Ready Top10 Strategy Candidates",
        "",
        f"Feature rows: {len(features):,}",
        f"Date range: {features['ts'].min()} to {features['ts'].max()}",
        f"Window days: {args.window_days}",
        f"Window step days: {args.window_step_days}",
        "Live-ready requires: 3x-cost net > 0, positive fold rate >= 80%, rolling positive window rate >= 70%, at least 5 trades in every rolling window, >= 200 full trades, and PF >= 1.25.",
        "",
        _markdown_table(live_top10[
            [
                "name",
                "source",
                "family",
                "full_trades",
                "full_net_points",
                "full_profit_factor",
                "positive_fold_rate",
                "positive_window_rate",
                "min_window_net_points",
                "worst_cost_net_points",
                "live_ready",
                "local_positive_rate",
                "local_median_robust_score",
                "local_rank_score",
                "live_score",
            ]
        ]),
        "",
    ]
    live_report = Path(args.live_report)
    live_report.parent.mkdir(parents=True, exist_ok=True)
    live_report.write_text("\n".join(live_markdown), encoding="utf-8")

    print(f"Ranked candidates: {len(results)}")
    print(f"CSV: {output}")
    print(f"Report: {top_output}")
    print(f"Live CSV: {live_output}")
    print(f"Live report: {live_report}")
    print()
    print("Live-ready Top10")
    print(live_top10[["name", "source", "full_net_points", "positive_fold_rate", "positive_window_rate", "worst_cost_net_points", "live_ready", "live_score"]].to_string(index=False))
    print()
    print("Robust Top10")
    print(top10[["name", "source", "full_net_points", "full_max_drawdown_points", "positive_fold_rate", "worst_cost_net_points", "robust_score"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
