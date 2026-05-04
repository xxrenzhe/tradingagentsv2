from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from optimize_mbp_robust_top10 import _load_features
from search_mbp_2r_purged_walkforward import (
    SESSIONS,
    build_2r_events,
    empty_summary,
    passes_blackbox,
    prepare_features,
    rolling_window_summary,
    summarize_trades,
    _feature_columns,
    _select_non_overlapping,
    _session_mask,
)
from tradingagents.backtesting.short_patterns import BacktestCosts


@dataclass(frozen=True)
class ModelCandidate:
    name: str
    direction: int
    stop_loss_points: float
    take_profit_points: float
    horizon_minutes: int
    session: str
    threshold_quantile: float
    score_threshold: float
    train_score: float
    train_trades: int
    train_win_rate: float
    train_net_points: float
    train_profit_factor: float
    train_bracket_exit_share: float
    feature_weights: dict[str, float]
    feature_models: dict[str, tuple[list[float], list[float]]]


def run_model_walkforward(features: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(features["trade_date"].dropna().unique())
    rows = []
    trade_frames = []
    fold_index = 0
    start = 0
    while start + args.train_days + args.purge_days < len(dates):
        train_dates = dates[start : start + args.train_days]
        test_start = start + args.train_days + args.purge_days
        test_dates = dates[test_start : test_start + args.test_days]
        if not test_dates:
            break
        train_features = features[features["trade_date"].isin(set(train_dates))].reset_index(drop=True)
        test_features = features[features["trade_date"].isin(set(test_dates))].reset_index(drop=True)
        train_events = _event_cache(train_features, args)
        test_events = _event_cache(test_features, args)
        fold_candidates = []
        for direction in [1, -1]:
            for stop_loss in args.stop_loss_points:
                for horizon in args.horizon_minutes:
                    for session in args.sessions:
                        fold_candidates.extend(
                            learn_model_candidates(
                                train_features,
                                train_events[(direction, float(stop_loss), int(horizon))],
                                direction=direction,
                                stop_loss_points=float(stop_loss),
                                horizon_minutes=int(horizon),
                                session=session,
                                args=args,
                            )
                        )
        fold_candidates = sorted(fold_candidates, key=lambda candidate: candidate.train_score, reverse=True)[
            : args.max_fold_candidates
        ]
        for candidate in fold_candidates:
            test_event_frame = test_events[(candidate.direction, candidate.stop_loss_points, candidate.horizon_minutes)]
            trades, test_summary = evaluate_model_candidate(test_features, test_event_frame, candidate, args)
            windows = rolling_window_summary(trades, args.window_days, args.window_step_days)
            row = {
                "fold": fold_index,
                "train_start": str(train_dates[0]),
                "train_end": str(train_dates[-1]),
                "test_start": str(test_dates[0]),
                "test_end": str(test_dates[-1]),
                "name": candidate.name,
                "direction": candidate.direction,
                "stop_loss_points": candidate.stop_loss_points,
                "take_profit_points": candidate.take_profit_points,
                "horizon_minutes": candidate.horizon_minutes,
                "session": candidate.session,
                "threshold_quantile": candidate.threshold_quantile,
                "score_threshold": candidate.score_threshold,
                "feature_weights": ";".join(f"{key}:{value:.5f}" for key, value in candidate.feature_weights.items()),
                "train_score": candidate.train_score,
                "train_trades": candidate.train_trades,
                "train_win_rate": candidate.train_win_rate,
                "train_net_points": candidate.train_net_points,
                "train_profit_factor": candidate.train_profit_factor,
                "train_bracket_exit_share": candidate.train_bracket_exit_share,
                "test_trades": test_summary["trades"],
                "test_net_points": test_summary["net_points"],
                "test_max_drawdown_points": test_summary["max_drawdown_points"],
                "test_win_rate": test_summary["win_rate"],
                "test_profit_factor": test_summary["profit_factor"],
                "test_bracket_exit_share": test_summary["bracket_exit_share"],
                **{f"test_{key}": value for key, value in windows.items()},
            }
            row["blackbox_pass"] = passes_blackbox(row, args)
            row["test_score"] = (
                row["test_net_points"]
                - row["test_max_drawdown_points"]
                + row["test_profit_factor"] * 100
                + row["test_win_rate"] * 250
                + row["test_positive_window_rate"] * 100
            )
            rows.append(row)
            if not trades.empty:
                trade_copy = trades.copy()
                trade_copy["fold"] = fold_index
                trade_copy["strategy_name"] = candidate.name
                trade_frames.append(trade_copy)
        print(f"Fold {fold_index}: learned {len(fold_candidates):,} model candidates", flush=True)
        fold_index += 1
        start += args.step_days
    results = pd.DataFrame(rows)
    if not results.empty:
        results = results.sort_values(
            ["blackbox_pass", "test_win_rate", "test_net_points", "test_profit_factor", "test_score"],
            ascending=[False, False, False, False, False],
        ).reset_index(drop=True)
    trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    return results, trades


def learn_model_candidates(
    train_features: pd.DataFrame,
    events: pd.DataFrame,
    *,
    direction: int,
    stop_loss_points: float,
    horizon_minutes: int,
    session: str,
    args: argparse.Namespace,
) -> list[ModelCandidate]:
    if events.empty:
        return []
    session_mask = _session_mask(events["minute_of_day"], session)
    session_events = events.loc[session_mask].copy()
    if len(session_events) < args.min_train_events:
        return []
    scores, weights, feature_models = train_rank_scores(train_features, session_events, args)
    if scores.empty:
        return []
    candidates = []
    for quantile in args.score_quantiles:
        threshold = float(scores.quantile(quantile))
        mask = session_mask.copy()
        mask.loc[session_events.index] &= scores >= threshold
        trades = _select_non_overlapping(events, mask, min_gap_minutes=args.min_gap_minutes)
        summary = summarize_trades(trades)
        if not passes_training(summary, args):
            continue
        direction_name = "long" if direction > 0 else "short"
        name = (
            f"model2r_{direction_name}_sl{stop_loss_points:g}_tp{stop_loss_points * 2:g}"
            f"_h{horizon_minutes}_{session}_q{quantile:g}"
        )
        candidates.append(
            ModelCandidate(
                name=name,
                direction=direction,
                stop_loss_points=stop_loss_points,
                take_profit_points=stop_loss_points * 2.0,
                horizon_minutes=horizon_minutes,
                session=session,
                threshold_quantile=float(quantile),
                score_threshold=threshold,
                train_score=train_score(summary),
                train_trades=summary["trades"],
                train_win_rate=summary["win_rate"],
                train_net_points=summary["net_points"],
                train_profit_factor=summary["profit_factor"],
                train_bracket_exit_share=summary["bracket_exit_share"],
                feature_weights=weights,
                feature_models=feature_models,
            )
        )
    return candidates


def train_rank_scores(
    train_features: pd.DataFrame, events: pd.DataFrame, args: argparse.Namespace
) -> tuple[pd.Series, dict[str, float], dict[str, tuple[list[float], list[float]]]]:
    aligned = train_features.loc[events["signal_index"].astype(int), _feature_columns()].copy()
    aligned.index = events.index
    labels = (pd.to_numeric(events["net_points"], errors="coerce") > 0).astype(float)
    scores = pd.Series(0.0, index=events.index)
    weights: dict[str, float] = {}
    feature_models: dict[str, tuple[list[float], list[float]]] = {}
    for feature in _feature_columns():
        values = pd.to_numeric(aligned[feature], errors="coerce")
        usable = values.notna()
        if usable.sum() < args.min_train_events:
            continue
        quantiles = np.linspace(0.0, 1.0, min(args.bin_count, int(usable.sum())) + 1)
        edges = values.loc[usable].quantile(quantiles).dropna().drop_duplicates().to_numpy(dtype=float)
        if len(edges) < 3:
            continue
        bin_ids = np.searchsorted(edges[1:-1], values.loc[usable].to_numpy(dtype=float), side="right")
        grouped = labels.loc[usable].groupby(pd.Series(bin_ids, index=values.loc[usable].index), observed=True).agg(["mean", "count"])
        prior = float(labels.loc[usable].mean())
        edge_by_bin = (grouped["mean"] - prior) * np.sqrt(grouped["count"].clip(lower=1))
        feature_signal = pd.Series(0.0, index=events.index)
        bin_score = pd.Series(bin_ids, index=values.loc[usable].index).map(edge_by_bin).astype(float)
        feature_signal.loc[usable] = bin_score.to_numpy()
        weight = float(abs(edge_by_bin).mean()) if len(edge_by_bin) else 0.0
        if weight <= 0:
            continue
        scores = scores + feature_signal
        weights[feature] = weight
        ordered_scores = [float(edge_by_bin.get(index, 0.0)) for index in range(len(edges) - 1)]
        feature_models[feature] = ([float(value) for value in edges], ordered_scores)
    if not weights:
        return pd.Series(dtype=float), {}, {}
    normalized = (scores - scores.mean()) / (scores.std() if float(scores.std()) else 1.0)
    return (
        normalized.fillna(0.0),
        dict(sorted(weights.items(), key=lambda item: item[1], reverse=True)[: args.max_weight_features]),
        feature_models,
    )


def apply_rank_scores(features: pd.DataFrame, events: pd.DataFrame, candidate: ModelCandidate) -> pd.Series:
    if events.empty or not candidate.feature_models:
        return pd.Series(dtype=float)
    aligned = features.loc[events["signal_index"].astype(int), list(candidate.feature_models)].copy()
    aligned.index = events.index
    scores = pd.Series(0.0, index=events.index)
    for feature, (edges, bin_scores) in candidate.feature_models.items():
        values = pd.to_numeric(aligned[feature], errors="coerce")
        usable = values.notna()
        if not usable.any():
            continue
        edge_values = np.asarray(edges, dtype=float)
        score_values = np.asarray(bin_scores, dtype=float)
        bin_ids = np.searchsorted(edge_values[1:-1], values.loc[usable].to_numpy(dtype=float), side="right")
        bin_ids = np.clip(bin_ids, 0, len(score_values) - 1)
        feature_scores = pd.Series(0.0, index=events.index)
        feature_scores.loc[usable] = score_values[bin_ids]
        scores = scores + feature_scores
    normalized = (scores - scores.mean()) / (scores.std() if float(scores.std()) else 1.0)
    return normalized.fillna(0.0)


def evaluate_model_candidate(
    features: pd.DataFrame,
    events: pd.DataFrame,
    candidate: ModelCandidate,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, dict]:
    if events.empty:
        return pd.DataFrame(), empty_summary()
    session_mask = _session_mask(events["minute_of_day"], candidate.session)
    session_events = events.loc[session_mask].copy()
    scores = apply_rank_scores(features, session_events, candidate)
    if scores.empty:
        return pd.DataFrame(), empty_summary()
    threshold = float(scores.quantile(candidate.threshold_quantile))
    mask = session_mask.copy()
    mask.loc[session_events.index] &= scores >= threshold
    trades = _select_non_overlapping(events, mask, min_gap_minutes=args.min_gap_minutes)
    return trades, summarize_trades(trades)


def passes_training(summary: dict, args: argparse.Namespace) -> bool:
    return (
        summary["trades"] >= args.min_train_trades
        and summary["net_points"] > 0
        and summary["win_rate"] >= args.min_train_win_rate
        and summary["profit_factor"] >= args.min_profit_factor
        and summary["bracket_exit_share"] >= args.min_bracket_exit_share
    )


def train_score(summary: dict) -> float:
    return float(
        summary["net_points"]
        - summary["max_drawdown_points"]
        + summary["profit_factor"] * 90
        + summary["win_rate"] * 260
        + summary["bracket_exit_share"] * 60
    )


def _event_cache(features: pd.DataFrame, args: argparse.Namespace) -> dict[tuple[int, float, int], pd.DataFrame]:
    costs = BacktestCosts(slippage_ticks_per_side=args.slippage_ticks_per_side)
    cache = {}
    for direction in [1, -1]:
        for stop_loss in args.stop_loss_points:
            for horizon in args.horizon_minutes:
                cache[(direction, float(stop_loss), int(horizon))] = build_2r_events(
                    features,
                    direction=direction,
                    stop_loss_points=float(stop_loss),
                    horizon_minutes=int(horizon),
                    cost_points=costs.round_trip_cost_points,
                )
    return cache


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    rows = ["| " + " | ".join(frame.columns) + " |", "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    for _, row in frame.iterrows():
        values = []
        for column in frame.columns:
            value = row[column]
            text = f"{value:.4f}" if isinstance(value, float) else str(value)
            values.append(text.replace("|", "\\|"))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def write_report(path: Path, results: pd.DataFrame, features: pd.DataFrame, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    passed = results[results["blackbox_pass"]] if not results.empty else pd.DataFrame()
    columns = [
        "fold",
        "name",
        "train_trades",
        "train_win_rate",
        "train_net_points",
        "test_trades",
        "test_win_rate",
        "test_net_points",
        "test_profit_factor",
        "test_positive_window_rate",
        "test_bracket_exit_share",
        "blackbox_pass",
    ]
    lines = [
        "# NQM6 Model-Based Purged Walk-Forward 2R Search",
        "",
        f"Feature rows: {len(features):,}",
        f"Date range: {features['ts'].min()} to {features['ts'].max()}",
        f"Train days: {args.train_days}",
        f"Purge days: {args.purge_days}",
        f"Test days: {args.test_days}",
        f"Step days: {args.step_days}",
        f"Stop-loss points: {', '.join(str(value) for value in args.stop_loss_points)}",
        f"Horizons: {', '.join(str(value) for value in args.horizon_minutes)}",
        f"Sessions: {', '.join(args.sessions)}",
        "",
        "## Completion Audit",
        "",
        "- Requirement: >=60% test win rate. Gate requires `test_win_rate >= 0.60`.",
        "- Requirement: fixed 2R. Every candidate uses `take_profit_points = 2 * stop_loss_points`.",
        "- Requirement: black-box testing. Each fold trains feature-bin model scores on prior train dates, skips purge dates, then evaluates future test dates.",
        "- Requirement: not overfit. A pass here would still need longer history and paper validation; no pass means the current feature/model family did not find a durable 2R edge.",
        "- Requirement: directly live-ready. Not satisfied without broker paper fills, slippage, rejects, and order-routing checks.",
        "",
        f"Training-selected fold candidates tested: {len(results):,}",
        f"Black-box passed rows: {len(passed):,}",
        "",
    ]
    if passed.empty:
        lines.extend(
            [
                "## Verdict",
                "",
                "No train-only model-based 60% win-rate fixed-2R candidate passed the black-box gate.",
                "",
            ]
        )
    else:
        lines.extend(["## Passed Candidates", "", _markdown_table(passed.head(20)[columns]), ""])
    lines.extend(["## Top Tested Candidates", "", _markdown_table(results.head(30)[columns]) if not results.empty else "_No rows._", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Train-only model score search for 60% win-rate 2R MBP strategies.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/mbp-2r-model-walkforward.csv")
    parser.add_argument("--trades-output", default=".tmp/mbp-2r-model-walkforward-trades.csv")
    parser.add_argument("--report", default="reports/NQM6-mbp-2r-model-walkforward.md")
    parser.add_argument("--train-days", type=int, default=20)
    parser.add_argument("--purge-days", type=int, default=2)
    parser.add_argument("--test-days", type=int, default=5)
    parser.add_argument("--step-days", type=int, default=5)
    parser.add_argument("--stop-loss-points", type=float, nargs="+", default=[4.0, 8.0, 12.0, 16.0])
    parser.add_argument("--horizon-minutes", type=int, nargs="+", default=[30, 60, 120])
    parser.add_argument("--sessions", nargs="+", default=["all", "europe", "us_rth", "us_late"])
    parser.add_argument("--score-quantiles", type=float, nargs="+", default=[0.70, 0.80, 0.90, 0.95])
    parser.add_argument("--bin-count", type=int, default=10)
    parser.add_argument("--min-train-events", type=int, default=80)
    parser.add_argument("--min-train-trades", type=int, default=25)
    parser.add_argument("--min-test-trades", type=int, default=10)
    parser.add_argument("--min-window-trades", type=int, default=5)
    parser.add_argument("--min-train-win-rate", type=float, default=0.50)
    parser.add_argument("--min-test-win-rate", type=float, default=0.60)
    parser.add_argument("--min-profit-factor", type=float, default=1.00)
    parser.add_argument("--min-positive-window-rate", type=float, default=0.50)
    parser.add_argument("--min-bracket-exit-share", type=float, default=0.60)
    parser.add_argument("--min-gap-minutes", type=int, default=1)
    parser.add_argument("--max-fold-candidates", type=int, default=30)
    parser.add_argument("--max-weight-features", type=int, default=8)
    parser.add_argument("--slippage-ticks-per-side", type=float, default=1.0)
    parser.add_argument("--window-days", type=int, default=5)
    parser.add_argument("--window-step-days", type=int, default=5)
    args = parser.parse_args()

    features = prepare_features(_load_features(Path(args.features_cache)))
    results, trades = run_model_walkforward(features, args)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output, index=False)
    trades.to_csv(args.trades_output, index=False)
    write_report(Path(args.report), results, features, args)
    print(f"Rows: {len(results):,}")
    print(f"Black-box passes: {int(results['blackbox_pass'].sum()) if not results.empty else 0:,}")
    if not results.empty:
        print(results.head(20).to_string(index=False))
    return 0 if not results.empty and bool(results["blackbox_pass"].any()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
