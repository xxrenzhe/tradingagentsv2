from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Any

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts, StrategySpec, build_trades, summarize_trades
from tradingagents.dataflows.databento import _bar_zip_path


@dataclass(frozen=True)
class BarStrategyCandidate:
    spec: StrategySpec
    session: str

    @property
    def name(self) -> str:
        return f"bar_best_{self.spec.name}_{self.session}"


def candidate_pool(args: argparse.Namespace) -> list[BarStrategyCandidate]:
    candidates: list[BarStrategyCandidate] = []
    for session in args.sessions:
        for family in args.families:
            for lookback in args.lookbacks:
                for threshold in _thresholds_for_family(family, args):
                    for holding_minutes in args.holding_minutes:
                        spec = StrategySpec(
                            name=(
                                f"{family}_lb{lookback}_thr{threshold:g}"
                                f"_hold{holding_minutes}"
                            ),
                            family=family,
                            lookback=int(lookback),
                            threshold=float(threshold),
                            holding_minutes=int(holding_minutes),
                        )
                        candidates.append(BarStrategyCandidate(spec=spec, session=session))
    return candidates


def _thresholds_for_family(family: str, args: argparse.Namespace) -> list[float]:
    if family == "mean_reversion":
        return [float(value) for value in args.mean_reversion_thresholds]
    if family == "momentum":
        return [float(value) for value in args.momentum_thresholds]
    if family == "vwap_reclaim":
        return [float(value) for value in args.vwap_thresholds]
    if family == "breakout":
        return [0.0]
    raise ValueError(f"unknown family: {family}")


def session_features(features: pd.DataFrame, session: str) -> pd.DataFrame:
    minute = features["minute_of_day"]
    if session == "all":
        return features
    if session == "europe":
        return features[(minute >= 7 * 60) & (minute < 13 * 60 + 30)]
    if session == "us_rth":
        return features[(minute >= 13 * 60 + 30) & (minute < 20 * 60)]
    if session == "us_late":
        return features[(minute >= 20 * 60) & (minute < 23 * 60)]
    if session == "asia":
        return features[(minute < 7 * 60) | (minute >= 23 * 60)]
    raise ValueError(f"unknown session: {session}")


def prepare_bar_strategy_features(features: pd.DataFrame) -> pd.DataFrame:
    prepared = features.copy()
    prepared["ts"] = pd.to_datetime(prepared["ts"], utc=True)
    prepared["minute_of_day"] = prepared["ts"].dt.hour * 60 + prepared["ts"].dt.minute
    if "vwap" not in prepared.columns:
        volume = pd.to_numeric(prepared["Volume"], errors="coerce").fillna(0.0)
        close = pd.to_numeric(prepared["Close"], errors="coerce")
        cumulative_volume = volume.replace(0, pd.NA).cumsum()
        prepared["vwap"] = (close * volume).cumsum() / cumulative_volume
    for column in ["spread_mean", "imbalance_mean", "imbalance_last", "depth_mean", "quote_count"]:
        if column not in prepared.columns:
            prepared[column] = pd.NA
    return prepared.reset_index(drop=True)


def summarize_candidate(candidate: BarStrategyCandidate, features: pd.DataFrame, costs: BacktestCosts) -> tuple[dict[str, Any], pd.DataFrame]:
    frame = session_features(features, candidate.session).reset_index(drop=True)
    if frame.empty:
        return empty_summary(), pd.DataFrame()
    trades = build_trades(frame, candidate.spec, costs)
    summary = summarize_trades(candidate.spec, trades, costs)
    summary["score"] = score_summary(summary)
    return summary, trades


def build_candidate_trade_cache(
    features: pd.DataFrame,
    candidates: list[BarStrategyCandidate],
    costs: BacktestCosts,
) -> dict[str, tuple[BarStrategyCandidate, pd.DataFrame]]:
    cache: dict[str, tuple[BarStrategyCandidate, pd.DataFrame]] = {}
    for candidate in candidates:
        frame = session_features(features, candidate.session).reset_index(drop=True)
        trades = build_trades(frame, candidate.spec, costs) if not frame.empty else pd.DataFrame()
        if not trades.empty:
            trades = trades.copy()
            trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
            trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
        cache[candidate.name] = (candidate, trades)
    return cache


def summarize_cached_trades(candidate: BarStrategyCandidate, trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, costs: BacktestCosts) -> tuple[dict[str, Any], pd.DataFrame]:
    if trades.empty:
        return empty_summary(), trades
    selected = trades[(trades["entry_ts"] >= start) & (trades["entry_ts"] < end)].copy()
    if selected.empty:
        return empty_summary(), selected
    return summarize_trades(candidate.spec, selected, costs) | {"score": score_summary(summarize_trades(candidate.spec, selected, costs))}, selected


def empty_summary() -> dict[str, Any]:
    return {
        "trades": 0,
        "net_points": 0.0,
        "max_drawdown_points": 0.0,
        "profit_factor": 0.0,
        "win_rate": 0.0,
        "stability": 0.0,
        "tail_loss_p05": 0.0,
        "score": 0.0,
    }


def score_summary(summary: dict[str, Any]) -> float:
    net_points = float(summary.get("net_points", 0.0))
    max_drawdown = float(summary.get("max_drawdown_points", 0.0))
    tail_loss = abs(float(summary.get("tail_loss_p05", 0.0)))
    stability = max(0.0, float(summary.get("stability", 0.0)))
    trades = int(summary.get("trades", 0))
    risk = max(max_drawdown, tail_loss, 1.0)
    return float((net_points / risk) * sqrt(min(trades, 300) / 300) * (0.65 + 0.35 * stability))


def walk_forward(features: pd.DataFrame, candidates: list[BarStrategyCandidate], args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    costs = BacktestCosts()
    trade_cache = build_candidate_trade_cache(features, candidates, costs)
    start = pd.Timestamp(args.walk_start_date, tz="UTC")
    end = pd.Timestamp(args.end_date, tz="UTC")
    fold_rows: list[dict[str, Any]] = []
    trade_rows: list[pd.DataFrame] = []
    fold = 0
    test_start = start
    while test_start + pd.Timedelta(days=args.test_days) <= end:
        train_start = test_start - pd.Timedelta(days=args.purge_days + args.train_days)
        train_end = test_start - pd.Timedelta(days=args.purge_days)
        test_end = test_start + pd.Timedelta(days=args.test_days)
        ranked: list[tuple[float, dict[str, Any], BarStrategyCandidate]] = []
        for candidate, trades in trade_cache.values():
            train_summary, _ = summarize_cached_trades(candidate, trades, train_start, train_end, costs)
            if not train_passes(train_summary, args):
                continue
            ranked.append((float(train_summary["score"]), train_summary, candidate))
        ranked.sort(reverse=True, key=lambda item: (item[0], item[1]["net_points"], item[1]["profit_factor"]))
        for rank, (_, train_summary, candidate) in enumerate(ranked[: args.max_fold_candidates], start=1):
            _, cached_trades = trade_cache[candidate.name]
            test_summary, test_trades = summarize_cached_trades(candidate, cached_trades, test_start, test_end, costs)
            test_pass = test_passes(test_summary, args)
            row = {
                "fold": fold,
                "fold_rank": rank,
                "candidate": candidate.name,
                "family": candidate.spec.family,
                "lookback": candidate.spec.lookback,
                "threshold": candidate.spec.threshold,
                "holding_minutes": candidate.spec.holding_minutes,
                "session": candidate.session,
                "train_start": str(train_start.date()),
                "train_end": str(train_end.date()),
                "test_start": str(test_start.date()),
                "test_end": str(test_end.date()),
                "test_pass": bool(test_pass),
                **{f"train_{key}": value for key, value in train_summary.items()},
                **{f"test_{key}": value for key, value in test_summary.items()},
            }
            fold_rows.append(row)
            if not test_trades.empty:
                exported = test_trades.copy()
                exported["fold"] = fold
                exported["fold_rank"] = rank
                exported["candidate"] = candidate.name
                exported["test_pass"] = bool(test_pass)
                trade_rows.append(exported)
        fold += 1
        test_start += pd.Timedelta(days=args.step_days)
    folds = pd.DataFrame(fold_rows)
    trades = pd.concat(trade_rows, ignore_index=True, sort=False) if trade_rows else pd.DataFrame()
    return folds, trades


def train_passes(summary: dict[str, Any], args: argparse.Namespace) -> bool:
    return (
        int(summary["trades"]) >= args.min_train_trades
        and float(summary["net_points"]) > 0
        and float(summary["profit_factor"]) >= args.min_train_profit_factor
        and float(summary["max_drawdown_points"]) <= args.max_train_drawdown_points
        and float(summary["score"]) > 0
    )


def test_passes(summary: dict[str, Any], args: argparse.Namespace) -> bool:
    return (
        int(summary["trades"]) >= args.min_test_trades
        and float(summary["net_points"]) > 0
        and float(summary["profit_factor"]) >= args.min_test_profit_factor
        and float(summary["max_drawdown_points"]) <= args.max_test_drawdown_points
    )


def aggregate_results(folds: pd.DataFrame) -> pd.DataFrame:
    if folds.empty:
        return pd.DataFrame()
    grouped = folds.groupby("candidate", as_index=False).agg(
        family=("family", "first"),
        lookback=("lookback", "first"),
        threshold=("threshold", "first"),
        holding_minutes=("holding_minutes", "first"),
        session=("session", "first"),
        selected_folds=("fold", "nunique"),
        positive_test_folds=("test_net_points", lambda values: int((values > 0).sum())),
        pass_folds=("test_pass", "sum"),
        test_trades=("test_trades", "sum"),
        test_net_points=("test_net_points", "sum"),
        test_max_drawdown_points=("test_max_drawdown_points", "max"),
        avg_test_profit_factor=("test_profit_factor", "mean"),
        avg_test_win_rate=("test_win_rate", "mean"),
        avg_test_stability=("test_stability", "mean"),
        min_test_net_points=("test_net_points", "min"),
        train_net_points=("train_net_points", "sum"),
        avg_train_score=("train_score", "mean"),
    )
    grouped["positive_test_fold_rate"] = grouped["positive_test_folds"] / grouped["selected_folds"].clip(lower=1)
    grouped["pass_fold_rate"] = grouped["pass_folds"] / grouped["selected_folds"].clip(lower=1)
    grouped["net_to_drawdown"] = grouped["test_net_points"] / grouped["test_max_drawdown_points"].clip(lower=1.0)
    grouped["stable_candidate"] = grouped["selected_folds"] >= 3
    grouped["long_history_score"] = (
        grouped["net_to_drawdown"].clip(lower=0)
        * grouped["positive_test_fold_rate"].clip(lower=0.01)
        * (grouped["selected_folds"].clip(upper=8) / 8)
        * (0.75 + grouped["avg_test_stability"].fillna(0).clip(lower=0) * 0.25)
        + grouped["test_net_points"].clip(lower=0) * 0.001
    )
    return grouped.sort_values(
        ["stable_candidate", "positive_test_fold_rate", "pass_fold_rate", "long_history_score", "test_net_points"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)


def write_report(path: Path, folds: pd.DataFrame, aggregate: pd.DataFrame, features: pd.DataFrame, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NQ Bar-Only Best Strategy Walk-Forward Search",
        "",
        "## Verdict",
        "",
    ]
    if aggregate.empty:
        lines.append("No train-selected long-history bar-only candidate produced enough future test evidence.")
    else:
        top = aggregate.iloc[0]
        lines.append(
            "Best long-history bar-only candidate: "
            f"`{top['candidate']}` with `{top['test_net_points']:.4f}` future test net points, "
            f"`{top['positive_test_fold_rate']:.2%}` positive selected folds, "
            f"`{top['avg_test_profit_factor']:.4f}` average test PF, "
            f"and `{top['net_to_drawdown']:.4f}` net/DD."
        )
        if float(top["pass_fold_rate"]) < 0.80:
            lines.append("")
            lines.append("This is still a research candidate, not live-ready: pass fold rate is below the conservative 80% target.")
    lines.extend(
        [
            "",
            "## Data",
            "",
            f"- Source: `{_bar_zip_path()}`.",
            "- Continuous construction: one NQ futures row per minute, selected by highest reported volume.",
            f"- Feature span: `{features['ts'].min()}` to `{features['ts'].max()}`.",
            f"- Feature rows: `{len(features):,}`.",
            f"- Distinct symbols selected: `{features['symbol'].nunique()}`.",
            "",
            "## Walk-Forward Design",
            "",
            f"- Train days: `{args.train_days}`; purge days: `{args.purge_days}`; test days: `{args.test_days}`; step days: `{args.step_days}`.",
            f"- Candidate families: `{', '.join(args.families)}`.",
            f"- Sessions: `{', '.join(args.sessions)}`.",
            f"- Max fold candidates: `{args.max_fold_candidates}`.",
            f"- Train gates: trades >= `{args.min_train_trades}`, PF >= `{args.min_train_profit_factor}`, max DD <= `{args.max_train_drawdown_points}`.",
            f"- Test gates: trades >= `{args.min_test_trades}`, PF >= `{args.min_test_profit_factor}`, max DD <= `{args.max_test_drawdown_points}`.",
            "",
            "## Summary",
            "",
            f"- Fold rows: `{len(folds):,}`.",
            f"- Aggregated candidates: `{len(aggregate):,}`.",
            f"- Test-pass fold rows: `{int(folds['test_pass'].sum()) if 'test_pass' in folds else 0:,}`.",
            "",
        ]
    )
    if not aggregate.empty:
        display_columns = [
            "candidate",
            "selected_folds",
            "stable_candidate",
            "positive_test_fold_rate",
            "pass_fold_rate",
            "test_trades",
            "test_net_points",
            "test_max_drawdown_points",
            "net_to_drawdown",
            "avg_test_profit_factor",
            "avg_test_win_rate",
            "min_test_net_points",
            "long_history_score",
        ]
        lines.extend(["## Top Aggregated Candidates", "", markdown_table(aggregate.head(25)[display_columns]), ""])
    if not folds.empty:
        fold_columns = [
            "test_pass",
            "candidate",
            "fold",
            "fold_rank",
            "train_trades",
            "train_net_points",
            "train_profit_factor",
            "test_trades",
            "test_net_points",
            "test_profit_factor",
            "test_win_rate",
            "test_max_drawdown_points",
        ]
        top_folds = folds.sort_values(["test_pass", "test_net_points"], ascending=[False, False]).head(25)
        lines.extend(["## Top Fold Rows", "", markdown_table(top_folds[fold_columns]), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    rows = ["| " + " | ".join(frame.columns) + " |", "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    for _, row in frame.iterrows():
        values = []
        for column in frame.columns:
            value = row[column]
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Long-history NQ bar-only search for profitable stable non-2R strategies.")
    parser.add_argument("--start-date", default="2018-01-01")
    parser.add_argument("--walk-start-date", default="2019-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-bar-best-continuous-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/nq-bar-best-strategy-walkforward.csv")
    parser.add_argument("--aggregate-output", default=".tmp/nq-bar-best-strategy-walkforward-aggregate.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-bar-best-strategy-walkforward-trades.csv")
    parser.add_argument("--report", default="reports/NQ-bar-best-strategy-walkforward.md")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--train-days", type=int, default=365)
    parser.add_argument("--purge-days", type=int, default=10)
    parser.add_argument("--test-days", type=int, default=90)
    parser.add_argument("--step-days", type=int, default=90)
    parser.add_argument("--max-fold-candidates", type=int, default=15)
    parser.add_argument("--families", nargs="+", default=["mean_reversion", "momentum", "vwap_reclaim", "breakout"])
    parser.add_argument("--sessions", nargs="+", default=["all", "europe", "us_rth", "us_late", "asia"])
    parser.add_argument("--lookbacks", type=int, nargs="+", default=[5, 10, 15, 30, 60])
    parser.add_argument("--holding-minutes", type=int, nargs="+", default=[3, 5, 10, 15, 30, 60])
    parser.add_argument("--mean-reversion-thresholds", type=float, nargs="+", default=[0.6, 1.0, 1.4, 2.0])
    parser.add_argument("--momentum-thresholds", type=float, nargs="+", default=[0.0003, 0.0006, 0.001, 0.0015])
    parser.add_argument("--vwap-thresholds", type=float, nargs="+", default=[0.0002, 0.0005, 0.001])
    parser.add_argument("--min-train-trades", type=int, default=120)
    parser.add_argument("--min-test-trades", type=int, default=20)
    parser.add_argument("--min-train-profit-factor", type=float, default=1.08)
    parser.add_argument("--min-test-profit-factor", type=float, default=1.05)
    parser.add_argument("--max-train-drawdown-points", type=float, default=5000.0)
    parser.add_argument("--max-test-drawdown-points", type=float, default=2000.0)
    args = parser.parse_args()

    features = prepare_bar_strategy_features(load_continuous_nq_bars(args))
    candidates = candidate_pool(args)
    folds, trades = walk_forward(features, candidates, args)
    aggregate = aggregate_results(folds)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    folds.to_csv(args.output, index=False)
    aggregate.to_csv(args.aggregate_output, index=False)
    trades.to_csv(args.trades_output, index=False)
    write_report(Path(args.report), folds, aggregate, features, args)
    result = {
        "feature_rows": int(len(features)),
        "feature_start": str(features["ts"].min()),
        "feature_end": str(features["ts"].max()),
        "candidate_count": int(len(candidates)),
        "fold_rows": int(len(folds)),
        "aggregate_rows": int(len(aggregate)),
        "test_pass_rows": int(folds["test_pass"].sum()) if "test_pass" in folds else 0,
        "output": args.output,
        "aggregate_output": args.aggregate_output,
        "trades_output": args.trades_output,
        "report": args.report,
    }
    if not aggregate.empty:
        result["top_candidate"] = aggregate.iloc[0].to_dict()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
