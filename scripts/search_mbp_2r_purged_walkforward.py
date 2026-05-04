from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from optimize_mbp_robust_top10 import _load_features
from tradingagents.backtesting.short_patterns import BacktestCosts


SESSIONS = {
    "all": (0, 24 * 60),
    "asia": (0, 7 * 60),
    "europe": (7 * 60, 13 * 60 + 30),
    "us_rth": (13 * 60 + 30, 20 * 60),
    "us_late": (20 * 60, 24 * 60),
}


@dataclass(frozen=True)
class Predicate:
    feature: str
    op: str
    threshold: float

    @property
    def text(self) -> str:
        return f"{self.feature}{self.op}{self.threshold:.7g}"


@dataclass(frozen=True)
class RuleCandidate:
    name: str
    direction: int
    stop_loss_points: float
    take_profit_points: float
    horizon_minutes: int
    session: str
    predicates: tuple[Predicate, ...]
    train_score: float
    train_trades: int
    train_win_rate: float
    train_net_points: float
    train_profit_factor: float
    train_bracket_exit_share: float


def prepare_features(features: pd.DataFrame) -> pd.DataFrame:
    data = features.copy().sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    data["ts"] = pd.to_datetime(data["ts"], utc=True)
    for column in [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "vwap",
        "spread_mean",
        "imbalance_mean",
        "imbalance_last",
        "depth_mean",
        "quote_count",
    ]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["trade_date"] = data["ts"].dt.date
    data["return_1m"] = data["Close"].pct_change()
    data["return_3m"] = data["Close"].pct_change(3)
    data["return_5m"] = data["Close"].pct_change(5)
    data["return_10m"] = data["Close"].pct_change(10)
    data["range_1m"] = data["High"] - data["Low"]
    data["body_1m"] = data["Close"] - data["Open"]
    data["body_to_range"] = data["body_1m"] / data["range_1m"].replace(0, pd.NA)
    data["upper_wick"] = data["High"] - data[["Open", "Close"]].max(axis=1)
    data["lower_wick"] = data[["Open", "Close"]].min(axis=1) - data["Low"]
    data["realized_vol_15"] = data["return_1m"].rolling(15).std()
    data["realized_vol_30"] = data["return_1m"].rolling(30).std()
    data["range_mean_10"] = data["range_1m"].rolling(10).mean()
    data["z_5"] = (data["Close"] - data["Close"].rolling(5).mean()) / data["Close"].rolling(5).std().replace(0, pd.NA)
    data["z_10"] = (data["Close"] - data["Close"].rolling(10).mean()) / data["Close"].rolling(10).std().replace(0, pd.NA)
    data["vwap_distance"] = (data["Close"] - data["vwap"]) / data["vwap"].replace(0, pd.NA)
    data["imbalance"] = data["imbalance_last"].fillna(data["imbalance_mean"]).fillna(0)
    data["spread_to_range"] = data["spread_mean"] / data["range_1m"].replace(0, pd.NA)
    data["depth_change_5"] = data["depth_mean"].pct_change(5)
    data["minute_sin"] = np.sin(2 * np.pi * data["minute_of_day"] / (24 * 60))
    data["minute_cos"] = np.cos(2 * np.pi * data["minute_of_day"] / (24 * 60))
    sane_prices = (data["High"] >= data[["Open", "Close"]].max(axis=1)) & (data["Low"] <= data[["Open", "Close"]].min(axis=1))
    sane_range = data["range_1m"].between(0, data["range_1m"].quantile(0.995))
    return data[sane_prices & sane_range].reset_index(drop=True)


def build_2r_events(
    features: pd.DataFrame,
    *,
    direction: int,
    stop_loss_points: float,
    horizon_minutes: int,
    cost_points: float,
) -> pd.DataFrame:
    take_profit_points = stop_loss_points * 2.0
    rows = []
    open_values = features["Open"].to_numpy(dtype=float)
    high_values = features["High"].to_numpy(dtype=float)
    low_values = features["Low"].to_numpy(dtype=float)
    close_values = features["Close"].to_numpy(dtype=float)
    timestamps = features["ts"].to_numpy()
    trade_dates = features["trade_date"].to_numpy()
    minutes = features["minute_of_day"].to_numpy(dtype=int)
    for signal_index in range(0, len(features) - 1):
        entry_index = signal_index + 1
        max_exit_index = min(entry_index + horizon_minutes, len(features) - 1)
        if entry_index >= max_exit_index:
            continue
        entry_price = float(open_values[entry_index])
        target_price = entry_price + take_profit_points if direction > 0 else entry_price - take_profit_points
        stop_price = entry_price - stop_loss_points if direction > 0 else entry_price + stop_loss_points
        exit_index = max_exit_index
        exit_price = float(close_values[max_exit_index])
        exit_reason = "timeout"
        for path_index in range(entry_index, max_exit_index + 1):
            high = float(high_values[path_index])
            low = float(low_values[path_index])
            if direction > 0:
                stop_hit = low <= stop_price
                target_hit = high >= target_price
            else:
                stop_hit = high >= stop_price
                target_hit = low <= target_price
            if stop_hit:
                exit_index = path_index
                exit_price = stop_price
                exit_reason = "stop_loss"
                break
            if target_hit:
                exit_index = path_index
                exit_price = target_price
                exit_reason = "take_profit"
                break
        gross_points = (exit_price - entry_price) * direction
        rows.append(
            {
                "signal_index": signal_index,
                "entry_index": entry_index,
                "exit_index": exit_index,
                "entry_ts": timestamps[entry_index],
                "exit_ts": timestamps[exit_index],
                "trade_date": trade_dates[entry_index],
                "minute_of_day": int(minutes[signal_index]),
                "direction": direction,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "gross_points": gross_points,
                "net_points": gross_points - cost_points,
            }
        )
    return pd.DataFrame(rows)


def learn_fold_candidates(
    train_features: pd.DataFrame,
    events: pd.DataFrame,
    *,
    direction: int,
    stop_loss_points: float,
    horizon_minutes: int,
    session: str,
    feature_columns: list[str],
    args: argparse.Namespace,
) -> list[RuleCandidate]:
    if events.empty:
        return []
    base_mask = _session_mask(events["minute_of_day"], session)
    predicates = _candidate_predicates(train_features, events, feature_columns, args.quantiles)
    single_rows = []
    predicate_masks: dict[str, pd.Series] = {}
    for predicate in predicates:
        mask = base_mask & _predicate_mask(train_features, events, predicate)
        summary = summarize_events(events, mask, min_gap_minutes=args.min_gap_minutes)
        if _passes_training(summary, args):
            predicate_masks[predicate.text] = mask
            single_rows.append((summary, (predicate,)))

    pair_rows = []
    if args.max_pair_predicates > 1:
        ranked_singles = sorted(single_rows, key=lambda item: _train_score(item[0]), reverse=True)[: args.max_pair_predicates]
        for (_, left), (_, right) in combinations(ranked_singles, 2):
            predicates_pair = (left[0], right[0])
            if predicates_pair[0].feature == predicates_pair[1].feature:
                continue
            mask = predicate_masks[predicates_pair[0].text] & predicate_masks[predicates_pair[1].text]
            summary = summarize_events(events, mask, min_gap_minutes=args.min_gap_minutes)
            if _passes_training(summary, args):
                pair_rows.append((summary, predicates_pair))

    candidates = []
    rows = sorted(single_rows + pair_rows, key=lambda item: _train_score(item[0]), reverse=True)[: args.max_fold_candidates]
    for rank, (summary, rule_predicates) in enumerate(rows, start=1):
        direction_name = "long" if direction > 0 else "short"
        predicate_text = "_and_".join(predicate.text for predicate in rule_predicates)
        name = (
            f"purged2r_{direction_name}_sl{stop_loss_points:g}_tp{stop_loss_points * 2:g}"
            f"_h{horizon_minutes}_{session}_{predicate_text}_rank{rank}"
        )
        candidates.append(
            RuleCandidate(
                name=name,
                direction=direction,
                stop_loss_points=stop_loss_points,
                take_profit_points=stop_loss_points * 2.0,
                horizon_minutes=horizon_minutes,
                session=session,
                predicates=rule_predicates,
                train_score=_train_score(summary),
                train_trades=summary["trades"],
                train_win_rate=summary["win_rate"],
                train_net_points=summary["net_points"],
                train_profit_factor=summary["profit_factor"],
                train_bracket_exit_share=summary["bracket_exit_share"],
            )
        )
    return candidates


def evaluate_candidate(
    features: pd.DataFrame,
    events: pd.DataFrame,
    candidate: RuleCandidate,
    *,
    min_gap_minutes: int,
) -> tuple[pd.DataFrame, dict]:
    if events.empty:
        return pd.DataFrame(), empty_summary()
    mask = _session_mask(events["minute_of_day"], candidate.session)
    for predicate in candidate.predicates:
        mask &= _predicate_mask(features, events, predicate)
    trades = _select_non_overlapping(events, mask, min_gap_minutes=min_gap_minutes)
    return trades, summarize_trades(trades)


def run_purged_walkforward(features: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(features["trade_date"].dropna().unique())
    rows = []
    trade_frames = []
    fold_index = 0
    start = 0
    feature_columns = _feature_columns()
    while start + args.train_days + args.purge_days < len(dates):
        train_dates = dates[start : start + args.train_days]
        test_start = start + args.train_days + args.purge_days
        test_dates = dates[test_start : test_start + args.test_days]
        if not test_dates:
            break
        train_features = features[features["trade_date"].isin(set(train_dates))].reset_index(drop=True)
        test_features = features[features["trade_date"].isin(set(test_dates))].reset_index(drop=True)
        fold_candidates = []
        train_event_cache = _event_cache(train_features, args)
        test_event_cache = _event_cache(test_features, args)
        for direction in [1, -1]:
            for stop_loss in args.stop_loss_points:
                for horizon in args.horizon_minutes:
                    for session in args.sessions:
                        fold_candidates.extend(
                            learn_fold_candidates(
                                train_features,
                                train_event_cache[(direction, stop_loss, horizon)],
                                direction=direction,
                                stop_loss_points=stop_loss,
                                horizon_minutes=horizon,
                                session=session,
                                feature_columns=feature_columns,
                                args=args,
                            )
                        )
        fold_candidates = sorted(fold_candidates, key=lambda candidate: candidate.train_score, reverse=True)[: args.max_fold_candidates]
        for candidate in fold_candidates:
            trades, test = evaluate_candidate(
                test_features,
                test_event_cache[(candidate.direction, candidate.stop_loss_points, candidate.horizon_minutes)],
                candidate,
                min_gap_minutes=args.min_gap_minutes,
            )
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
                "predicates": " & ".join(predicate.text for predicate in candidate.predicates),
                "train_score": candidate.train_score,
                "train_trades": candidate.train_trades,
                "train_win_rate": candidate.train_win_rate,
                "train_net_points": candidate.train_net_points,
                "train_profit_factor": candidate.train_profit_factor,
                "train_bracket_exit_share": candidate.train_bracket_exit_share,
                "test_trades": test["trades"],
                "test_net_points": test["net_points"],
                "test_max_drawdown_points": test["max_drawdown_points"],
                "test_win_rate": test["win_rate"],
                "test_profit_factor": test["profit_factor"],
                "test_bracket_exit_share": test["bracket_exit_share"],
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
        print(f"Fold {fold_index}: learned {len(fold_candidates):,} train-only candidates", flush=True)
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


def summarize_events(events: pd.DataFrame, mask: pd.Series, *, min_gap_minutes: int) -> dict:
    return summarize_trades(_select_non_overlapping(events, mask, min_gap_minutes=min_gap_minutes))


def summarize_trades(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return empty_summary()
    net = pd.to_numeric(trades["net_points"], errors="coerce")
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    wins = net[net > 0]
    losses = net[net < 0]
    exit_reasons = trades["exit_reason"].astype(str)
    return {
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "max_drawdown_points": float(abs(drawdown.min())),
        "profit_factor": float(wins.sum() / abs(losses.sum())) if float(losses.sum()) else float("inf"),
        "win_rate": float((net > 0).mean()),
        "target_exit_share": float((exit_reasons == "take_profit").mean()),
        "stop_exit_share": float((exit_reasons == "stop_loss").mean()),
        "timeout_share": float((exit_reasons == "timeout").mean()),
        "bracket_exit_share": float(exit_reasons.isin(["take_profit", "stop_loss"]).mean()),
        "worst_trade_points": float(net.min()),
    }


def empty_summary() -> dict:
    return {
        "trades": 0,
        "net_points": 0.0,
        "max_drawdown_points": 0.0,
        "profit_factor": 0.0,
        "win_rate": 0.0,
        "target_exit_share": 0.0,
        "stop_exit_share": 0.0,
        "timeout_share": 0.0,
        "bracket_exit_share": 0.0,
        "worst_trade_points": 0.0,
    }


def rolling_window_summary(trades: pd.DataFrame, window_days: int, step_days: int) -> dict:
    if trades.empty:
        return {"window_count": 0, "positive_window_rate": 0.0, "min_window_trades": 0, "min_window_net_points": 0.0}
    trade_dates = pd.to_datetime(trades["entry_ts"], utc=True).dt.date
    dates = sorted(trade_dates.unique())
    window_days = max(1, min(window_days, len(dates)))
    nets = []
    counts = []
    for start in range(0, len(dates) - window_days + 1, max(1, step_days)):
        window_dates = set(dates[start : start + window_days])
        values = pd.to_numeric(trades.loc[trade_dates.isin(window_dates), "net_points"], errors="coerce")
        nets.append(float(values.sum()))
        counts.append(int(values.count()))
    if not nets:
        values = pd.to_numeric(trades["net_points"], errors="coerce")
        nets = [float(values.sum())]
        counts = [int(values.count())]
    return {
        "window_count": len(nets),
        "positive_window_rate": float(sum(net > 0 for net in nets) / len(nets)),
        "min_window_trades": min(counts),
        "min_window_net_points": min(nets),
    }


def passes_blackbox(row: dict | pd.Series, args: argparse.Namespace) -> bool:
    return (
        int(row["test_trades"]) >= args.min_test_trades
        and float(row["test_net_points"]) > 0
        and float(row["test_win_rate"]) >= args.min_test_win_rate
        and float(row["test_profit_factor"]) >= args.min_profit_factor
        and float(row["test_positive_window_rate"]) >= args.min_positive_window_rate
        and int(row["test_min_window_trades"]) >= args.min_window_trades
        and float(row["test_bracket_exit_share"]) >= args.min_bracket_exit_share
    )


def _candidate_predicates(
    features: pd.DataFrame,
    events: pd.DataFrame,
    feature_columns: list[str],
    quantiles: list[float],
) -> list[Predicate]:
    aligned = features.loc[events["signal_index"].astype(int), feature_columns]
    predicates = []
    for feature in feature_columns:
        values = pd.to_numeric(aligned[feature], errors="coerce")
        thresholds = values.quantile(quantiles).dropna().drop_duplicates()
        for threshold in thresholds:
            predicates.append(Predicate(feature, "<=", float(threshold)))
            predicates.append(Predicate(feature, ">=", float(threshold)))
    return predicates


def _predicate_mask(features: pd.DataFrame, events: pd.DataFrame, predicate: Predicate) -> pd.Series:
    values = pd.to_numeric(features.loc[events["signal_index"].astype(int), predicate.feature], errors="coerce")
    if predicate.op == "<=":
        raw = values <= predicate.threshold
    elif predicate.op == ">=":
        raw = values >= predicate.threshold
    else:
        raise ValueError(f"Unsupported predicate op: {predicate.op}")
    return pd.Series(raw.fillna(False).to_numpy(), index=events.index)


def _session_mask(minutes: pd.Series, session: str) -> pd.Series:
    start, end = SESSIONS[session]
    return minutes.between(start, end - 1)


def _select_non_overlapping(events: pd.DataFrame, mask: pd.Series, *, min_gap_minutes: int) -> pd.DataFrame:
    selected_indexes = []
    next_index = 0
    selected = events.loc[mask, ["entry_index", "exit_index"]].sort_values("entry_index")
    for event in selected.itertuples():
        entry_index = int(event.entry_index)
        if entry_index < next_index:
            continue
        selected_indexes.append(event.Index)
        next_index = int(event.exit_index) + min_gap_minutes
    if not selected_indexes:
        return events.head(0).copy()
    return events.loc[selected_indexes].reset_index(drop=True)


def _passes_training(summary: dict, args: argparse.Namespace) -> bool:
    return (
        summary["trades"] >= args.min_train_trades
        and summary["net_points"] > 0
        and summary["win_rate"] >= args.min_train_win_rate
        and summary["profit_factor"] >= args.min_profit_factor
        and summary["bracket_exit_share"] >= args.min_bracket_exit_share
    )


def _train_score(summary: dict) -> float:
    return float(
        summary["net_points"]
        - summary["max_drawdown_points"]
        + summary["profit_factor"] * 90
        + summary["win_rate"] * 260
        + summary["bracket_exit_share"] * 60
    )


def _feature_columns() -> list[str]:
    return [
        "return_3m",
        "return_5m",
        "range_1m",
        "body_to_range",
        "realized_vol_15",
        "realized_vol_30",
        "z_5",
        "z_10",
        "vwap_distance",
        "imbalance",
        "spread_mean",
        "depth_mean",
        "quote_count",
    ]


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    rows = ["| " + " | ".join(frame.columns) + " |", "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    for _, row in frame.iterrows():
        values = []
        for column in frame.columns:
            value = row[column]
            values.append(f"{value:.4f}" if isinstance(value, float) else str(value))
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
        "# NQM6 Purged Walk-Forward 2R Search",
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
        "- Requirement: black-box testing. Every fold learns predicates only on prior train dates, skips purge dates, then evaluates future test dates.",
        "- Requirement: not overfit. This report still cannot prove live non-overfit unless a candidate passes all folds and then survives paper/live validation.",
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
                "No train-only purged walk-forward 60% win-rate 2R candidate passed. This adds another negative black-box result beyond the fixed grid and direct label-rule searches.",
                "",
            ]
        )
    else:
        lines.extend(["## Passed Candidates", "", _markdown_table(passed.head(20)[columns]), ""])
    lines.extend(["## Top Tested Candidates", "", _markdown_table(results.head(30)[columns]) if not results.empty else "_No rows._", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Train-only purged walk-forward search for 60% win-rate 2R MBP strategies.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/mbp-2r-purged-walkforward.csv")
    parser.add_argument("--trades-output", default=".tmp/mbp-2r-purged-walkforward-trades.csv")
    parser.add_argument("--report", default="reports/NQM6-mbp-2r-purged-walkforward.md")
    parser.add_argument("--train-days", type=int, default=20)
    parser.add_argument("--purge-days", type=int, default=2)
    parser.add_argument("--test-days", type=int, default=5)
    parser.add_argument("--step-days", type=int, default=5)
    parser.add_argument("--stop-loss-points", type=float, nargs="+", default=[4.0, 6.0, 8.0, 10.0, 12.0, 16.0])
    parser.add_argument("--horizon-minutes", type=int, nargs="+", default=[20, 30, 45, 60, 90, 120])
    parser.add_argument("--sessions", nargs="+", default=["all", "europe", "us_rth", "us_late"])
    parser.add_argument("--quantiles", type=float, nargs="+", default=[0.10, 0.20, 0.30, 0.70, 0.80, 0.90])
    parser.add_argument("--min-train-trades", type=int, default=60)
    parser.add_argument("--min-test-trades", type=int, default=20)
    parser.add_argument("--min-window-trades", type=int, default=5)
    parser.add_argument("--min-train-win-rate", type=float, default=0.56)
    parser.add_argument("--min-test-win-rate", type=float, default=0.60)
    parser.add_argument("--min-profit-factor", type=float, default=1.20)
    parser.add_argument("--min-positive-window-rate", type=float, default=0.70)
    parser.add_argument("--min-bracket-exit-share", type=float, default=0.70)
    parser.add_argument("--min-gap-minutes", type=int, default=1)
    parser.add_argument("--max-pair-predicates", type=int, default=30)
    parser.add_argument("--max-fold-candidates", type=int, default=40)
    parser.add_argument("--slippage-ticks-per-side", type=float, default=1.0)
    parser.add_argument("--window-days", type=int, default=5)
    parser.add_argument("--window-step-days", type=int, default=5)
    args = parser.parse_args()

    features = prepare_features(_load_features(Path(args.features_cache)))
    results, trades = run_purged_walkforward(features, args)
    output = Path(args.output)
    trades_output = Path(args.trades_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    trades_output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output, index=False)
    trades.to_csv(trades_output, index=False)
    write_report(Path(args.report), results, features, args)
    passed = int(results["blackbox_pass"].sum()) if not results.empty else 0
    print(f"Training-selected candidates tested: {len(results):,}")
    print(f"Black-box pass: {passed:,}")
    print(f"CSV: {output}")
    print(f"Trades CSV: {trades_output}")
    print(f"Report: {args.report}")
    if not results.empty:
        print(
            results.head(20)[
                [
                    "fold",
                    "name",
                    "test_trades",
                    "test_win_rate",
                    "test_net_points",
                    "test_profit_factor",
                    "test_positive_window_rate",
                    "test_bracket_exit_share",
                    "blackbox_pass",
                ]
            ].to_string(index=False)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
