from __future__ import annotations

import argparse
import hashlib
import html
import itertools
import json
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.evolution.features import prepare_evolution_features
from tradingagents.evolution.memory import EvolutionMemory, utc_now
from tradingagents.evolution.nq_data import load_continuous_nq_bars


@dataclass(frozen=True)
class TVStructureCandidate:
    name: str
    direction: int
    trigger: str
    filters: tuple[str, ...]
    stop_points: float
    target_points: float
    hold_bars: int
    session: str


@dataclass(frozen=True)
class TradeBuildContext:
    data: pd.DataFrame
    open_prices: np.ndarray
    high_prices: np.ndarray
    low_prices: np.ndarray
    close_prices: np.ndarray
    timestamps: np.ndarray
    segment_ids: np.ndarray | None


def main() -> int:
    parser = argparse.ArgumentParser(description="Search NQ TradingView-style chart-structure strategies.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--train-end-date", default="2022-01-01")
    parser.add_argument("--cache", default=".tmp/nq-tv-structure-bars-20200101-20260428.pkl")
    parser.add_argument("--candidate-trades-cache")
    parser.add_argument("--summary-output", default=".tmp/nq-tv-structure-strategy-summary.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-tv-structure-strategy-trades.csv")
    parser.add_argument("--report", default="reports/NQ-tradingview-structure-strategy-search.html")
    parser.add_argument("--memory-db")
    parser.add_argument("--record-memory", action="store_true")
    parser.add_argument("--walk-forward", action="store_true")
    parser.add_argument("--walk-start-date", default="2022-01-01")
    parser.add_argument("--walk-output", default=".tmp/nq-tv-structure-strategy-walkforward.csv")
    parser.add_argument("--walk-aggregate-output", default=".tmp/nq-tv-structure-strategy-walkforward-aggregate.csv")
    parser.add_argument("--walk-trades-output", default=".tmp/nq-tv-structure-strategy-walkforward-trades.csv")
    parser.add_argument("--walk-report", default="reports/NQ-tradingview-structure-strategy-walkforward.html")
    parser.add_argument("--train-days", type=int, default=365)
    parser.add_argument("--purge-days", type=int, default=5)
    parser.add_argument("--test-days", type=int, default=90)
    parser.add_argument("--step-days", type=int, default=90)
    parser.add_argument("--min-train-trades", type=int, default=30)
    parser.add_argument("--min-train-win-rate", type=float, default=0.53)
    parser.add_argument("--min-train-profit-factor", type=float, default=1.0)
    parser.add_argument("--min-train-payoff-ratio", type=float, default=1.0)
    parser.add_argument("--gate-payoff-ratio", type=float, default=1.0)
    parser.add_argument("--min-selected-folds", type=int, default=3)
    parser.add_argument("--min-aggregate-test-trades", type=int, default=60)
    parser.add_argument("--min-positive-test-fold-rate", type=float, default=0.60)
    parser.add_argument("--max-candidates", type=int, default=400)
    parser.add_argument("--min-total-signals", type=int, default=0)
    parser.add_argument("--max-total-signals", type=int, default=0)
    parser.add_argument("--min-test-trades", type=int, default=30)
    parser.add_argument("--gate-win-rate", type=float, default=0.53)
    parser.add_argument("--gate-profit-factor", type=float, default=1.0)
    args = parser.parse_args()

    if args.walk_forward:
        summary = run_walk_forward_search(
            start_date=args.start_date,
            end_date=args.end_date,
            walk_start_date=args.walk_start_date,
            cache=Path(args.cache),
            candidate_trades_cache=Path(args.candidate_trades_cache) if args.candidate_trades_cache else None,
            fold_output=Path(args.walk_output),
            aggregate_output=Path(args.walk_aggregate_output),
            trades_output=Path(args.walk_trades_output),
            report=Path(args.walk_report),
            memory_db=Path(args.memory_db) if args.memory_db else None,
            record_memory=bool(args.record_memory),
            max_candidates=args.max_candidates,
            train_days=args.train_days,
            purge_days=args.purge_days,
            test_days=args.test_days,
            step_days=args.step_days,
            min_train_trades=args.min_train_trades,
            min_train_win_rate=args.min_train_win_rate,
            min_train_profit_factor=args.min_train_profit_factor,
            min_train_payoff_ratio=args.min_train_payoff_ratio,
            min_test_trades=args.min_test_trades,
            gate_win_rate=args.gate_win_rate,
            gate_profit_factor=args.gate_profit_factor,
            gate_payoff_ratio=args.gate_payoff_ratio,
            min_selected_folds=args.min_selected_folds,
            min_aggregate_test_trades=args.min_aggregate_test_trades,
            min_positive_test_fold_rate=args.min_positive_test_fold_rate,
            min_total_signals=args.min_total_signals,
            max_total_signals=args.max_total_signals,
        )
        print(json.dumps(summary, indent=2, sort_keys=True, default=str))
        return 0 if summary["passing_walkforward_candidates"] > 0 else 2

    summary = run_search(
        start_date=args.start_date,
        end_date=args.end_date,
        train_end_date=args.train_end_date,
        cache=Path(args.cache),
        candidate_trades_cache=Path(args.candidate_trades_cache) if args.candidate_trades_cache else None,
        summary_output=Path(args.summary_output),
        trades_output=Path(args.trades_output),
        report=Path(args.report),
        memory_db=Path(args.memory_db) if args.memory_db else None,
        record_memory=bool(args.record_memory),
        max_candidates=args.max_candidates,
        min_test_trades=args.min_test_trades,
        gate_win_rate=args.gate_win_rate,
        gate_profit_factor=args.gate_profit_factor,
        min_total_signals=args.min_total_signals,
        max_total_signals=args.max_total_signals,
    )
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0 if summary["passing_test_candidates"] > 0 else 2


def run_search(
    *,
    start_date: str,
    end_date: str,
    train_end_date: str,
    cache: Path,
    candidate_trades_cache: Path | None,
    summary_output: Path,
    trades_output: Path,
    report: Path,
    memory_db: Path | None,
    record_memory: bool,
    max_candidates: int,
    min_test_trades: int,
    gate_win_rate: float,
    gate_profit_factor: float,
    min_total_signals: int,
    max_total_signals: int,
) -> dict[str, Any]:
    bars = load_continuous_nq_bars(start_date=start_date, end_date=end_date, cache_path=cache)
    features = prepare_evolution_features(bars)
    candidates = select_candidate_subset(build_candidates(), max_candidates)
    candidates, signal_counts = filter_candidates_by_signal_count(
        features=features,
        candidates=candidates,
        min_total_signals=min_total_signals,
        max_total_signals=max_total_signals,
    )
    train_end = pd.Timestamp(train_end_date, tz="UTC")
    costs = BacktestCosts()
    candidate_trades = build_or_load_candidate_trades(
        features=features,
        candidates=candidates,
        costs=costs,
        cache_path=candidate_trades_cache,
    )
    rows: list[dict[str, Any]] = []
    selected_trades: list[pd.DataFrame] = []
    for candidate in candidates:
        trades = candidate_trades[candidate.name]
        train = trades[trades["entry_ts"] < train_end]
        test = trades[trades["entry_ts"] >= train_end]
        train_summary = summarize_trades(train)
        test_summary = summarize_trades(test)
        pass_test = (
            test_summary["trades"] >= min_test_trades
            and test_summary["win_rate"] > gate_win_rate
            and test_summary["profit_factor"] > gate_profit_factor
        )
        rows.append(
            {
                "passes_test_gate": bool(pass_test),
                "name": candidate.name,
                "direction": "long" if candidate.direction > 0 else "short",
                "trigger": candidate.trigger,
                "filters": " & ".join(candidate.filters),
                "session": candidate.session,
                "stop_points": candidate.stop_points,
                "target_points": candidate.target_points,
                "hold_bars": candidate.hold_bars,
                "total_signals": int(signal_counts.get(candidate.name, 0)),
                **{f"train_{key}": value for key, value in train_summary.items()},
                **{f"test_{key}": value for key, value in test_summary.items()},
            }
        )
        if pass_test or len(selected_trades) < 5:
            sample = test.copy()
            if not sample.empty:
                sample["candidate"] = candidate.name
                selected_trades.append(sample.tail(1000))

    summary_frame = pd.DataFrame(rows).sort_values(
        ["passes_test_gate", "test_net_points", "test_profit_factor", "test_trades"],
        ascending=[False, False, False, False],
    )
    trades_frame = pd.concat(selected_trades, ignore_index=True, sort=False) if selected_trades else pd.DataFrame()
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    trades_output.parent.mkdir(parents=True, exist_ok=True)
    summary_frame.to_csv(summary_output, index=False)
    trades_frame.to_csv(trades_output, index=False)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        build_report(
            summary_frame=summary_frame,
            trades_frame=trades_frame,
            start_date=start_date,
            end_date=end_date,
            train_end_date=train_end_date,
            feature_rows=len(features),
            min_test_trades=min_test_trades,
            gate_win_rate=gate_win_rate,
            gate_profit_factor=gate_profit_factor,
            summary_output=summary_output,
            trades_output=trades_output,
        ),
        encoding="utf-8",
    )
    if record_memory and memory_db is not None:
        record_search_memory(memory_db, summary_frame, min_test_trades, gate_win_rate, gate_profit_factor)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "train_end_date": train_end_date,
        "feature_rows": int(len(features)),
        "candidates": int(len(candidates)),
        "signal_filter": {
            "min_total_signals": int(min_total_signals),
            "max_total_signals": int(max_total_signals),
        },
        "passing_test_candidates": int(summary_frame["passes_test_gate"].sum()) if not summary_frame.empty else 0,
        "best": summary_frame.head(1).to_dict(orient="records")[0] if not summary_frame.empty else {},
        "summary_output": str(summary_output),
        "trades_output": str(trades_output),
        "report": str(report),
        "memory_db": str(memory_db) if memory_db else "",
        "candidate_trades_cache": str(candidate_trades_cache) if candidate_trades_cache else "",
    }


def run_walk_forward_search(
    *,
    start_date: str,
    end_date: str,
    walk_start_date: str,
    cache: Path,
    candidate_trades_cache: Path | None,
    fold_output: Path,
    aggregate_output: Path,
    trades_output: Path,
    report: Path,
    memory_db: Path | None,
    record_memory: bool,
    max_candidates: int,
    train_days: int,
    purge_days: int,
    test_days: int,
    step_days: int,
    min_train_trades: int,
    min_train_win_rate: float,
    min_train_profit_factor: float,
    min_train_payoff_ratio: float,
    min_test_trades: int,
    gate_win_rate: float,
    gate_profit_factor: float,
    gate_payoff_ratio: float,
    min_selected_folds: int,
    min_aggregate_test_trades: int,
    min_positive_test_fold_rate: float,
    min_total_signals: int,
    max_total_signals: int,
) -> dict[str, Any]:
    bars = load_continuous_nq_bars(start_date=start_date, end_date=end_date, cache_path=cache)
    features = prepare_evolution_features(bars)
    candidates = select_candidate_subset(build_candidates(), max_candidates)
    candidates, signal_counts = filter_candidates_by_signal_count(
        features=features,
        candidates=candidates,
        min_total_signals=min_total_signals,
        max_total_signals=max_total_signals,
    )
    candidate_trades = build_or_load_candidate_trades(
        features=features,
        candidates=candidates,
        costs=BacktestCosts(),
        cache_path=candidate_trades_cache,
    )
    folds, trades = walk_forward_candidates(
        candidate_trades=candidate_trades,
        candidates=candidates,
        walk_start_date=walk_start_date,
        end_date=end_date,
        train_days=train_days,
        purge_days=purge_days,
        test_days=test_days,
        step_days=step_days,
        min_train_trades=min_train_trades,
        min_train_win_rate=min_train_win_rate,
        min_train_profit_factor=min_train_profit_factor,
        min_train_payoff_ratio=min_train_payoff_ratio,
        min_test_trades=min_test_trades,
        gate_win_rate=gate_win_rate,
        gate_profit_factor=gate_profit_factor,
        gate_payoff_ratio=gate_payoff_ratio,
    )
    aggregate = aggregate_walk_forward(
        folds=folds,
        trades=trades,
        min_selected_folds=min_selected_folds,
        min_aggregate_test_trades=min_aggregate_test_trades,
        gate_win_rate=gate_win_rate,
        gate_profit_factor=gate_profit_factor,
        gate_payoff_ratio=gate_payoff_ratio,
        min_positive_test_fold_rate=min_positive_test_fold_rate,
    )
    fold_output.parent.mkdir(parents=True, exist_ok=True)
    aggregate_output.parent.mkdir(parents=True, exist_ok=True)
    trades_output.parent.mkdir(parents=True, exist_ok=True)
    folds.to_csv(fold_output, index=False)
    aggregate.to_csv(aggregate_output, index=False)
    trades.to_csv(trades_output, index=False)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        build_walk_forward_report(
            aggregate=aggregate,
            folds=folds,
            trades=trades,
            start_date=start_date,
            end_date=end_date,
            walk_start_date=walk_start_date,
            feature_rows=len(features),
            min_train_trades=min_train_trades,
            min_test_trades=min_test_trades,
            gate_win_rate=gate_win_rate,
            gate_profit_factor=gate_profit_factor,
            gate_payoff_ratio=gate_payoff_ratio,
            min_selected_folds=min_selected_folds,
            min_positive_test_fold_rate=min_positive_test_fold_rate,
            fold_output=fold_output,
            aggregate_output=aggregate_output,
            trades_output=trades_output,
        ),
        encoding="utf-8",
    )
    if record_memory and memory_db is not None:
        record_walk_forward_memory(memory_db, aggregate, folds, gate_win_rate, gate_profit_factor, gate_payoff_ratio)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "walk_start_date": walk_start_date,
        "feature_rows": int(len(features)),
        "candidates": int(len(candidates)),
        "signal_filter": {
            "min_total_signals": int(min_total_signals),
            "max_total_signals": int(max_total_signals),
        },
        "fold_rows": int(len(folds)),
        "trade_rows": int(len(trades)),
        "passing_walkforward_candidates": int(aggregate["future_pass"].sum()) if not aggregate.empty else 0,
        "best": aggregate.head(1).to_dict(orient="records")[0] if not aggregate.empty else {},
        "fold_output": str(fold_output),
        "aggregate_output": str(aggregate_output),
        "trades_output": str(trades_output),
        "report": str(report),
        "memory_db": str(memory_db) if memory_db else "",
        "candidate_trades_cache": str(candidate_trades_cache) if candidate_trades_cache else "",
    }


def walk_forward_candidates(
    *,
    candidate_trades: dict[str, pd.DataFrame],
    candidates: list[TVStructureCandidate],
    walk_start_date: str,
    end_date: str,
    train_days: int,
    purge_days: int,
    test_days: int,
    step_days: int,
    min_train_trades: int,
    min_train_win_rate: float,
    min_train_profit_factor: float,
    min_train_payoff_ratio: float,
    min_test_trades: int,
    gate_win_rate: float,
    gate_profit_factor: float,
    gate_payoff_ratio: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    start = pd.Timestamp(walk_start_date, tz="UTC")
    end = pd.Timestamp(end_date, tz="UTC")
    candidate_by_name = {candidate.name: candidate for candidate in candidates}
    fold_rows: list[dict[str, Any]] = []
    trade_rows: list[pd.DataFrame] = []
    fold_index = 0
    test_start = start
    while test_start + timedelta(days=test_days) <= end:
        train_start = test_start - timedelta(days=purge_days + train_days)
        train_end = test_start - timedelta(days=purge_days)
        test_end = test_start + timedelta(days=test_days)
        for name, trades in candidate_trades.items():
            candidate = candidate_by_name[name]
            train = _date_slice(trades, train_start, train_end)
            if len(train) < min_train_trades:
                continue
            train_stats = summarize_trades(train)
            train_pass = (
                train_stats["trades"] >= min_train_trades
                and train_stats["win_rate"] > min_train_win_rate
                and train_stats["profit_factor"] > min_train_profit_factor
                and train_stats["payoff_ratio"] > min_train_payoff_ratio
                and train_stats["net_points"] > 0
            )
            if not train_pass:
                continue
            test = _date_slice(trades, test_start, test_end)
            test_stats = summarize_trades(test)
            test_fold_pass = (
                test_stats["trades"] >= min_test_trades
                and test_stats["win_rate"] > gate_win_rate
                and test_stats["profit_factor"] > gate_profit_factor
                and test_stats["payoff_ratio"] > gate_payoff_ratio
                and test_stats["net_points"] > 0
            )
            fold_rows.append(
                {
                    "fold": fold_index,
                    "candidate": name,
                    "direction": "long" if candidate.direction > 0 else "short",
                    "trigger": candidate.trigger,
                    "filters": " & ".join(candidate.filters),
                    "session": candidate.session,
                    "stop_points": candidate.stop_points,
                    "target_points": candidate.target_points,
                    "hold_bars": candidate.hold_bars,
                    "train_start": str(train_start.date()),
                    "train_end": str(train_end.date()),
                    "test_start": str(test_start.date()),
                    "test_end": str(test_end.date()),
                    **{f"train_{key}": value for key, value in train_stats.items()},
                    **{f"test_{key}": value for key, value in test_stats.items()},
                    "test_fold_pass": bool(test_fold_pass),
                }
            )
            if not test.empty:
                exported = test.copy()
                exported["fold"] = fold_index
                exported["candidate"] = name
                exported["test_fold_pass"] = bool(test_fold_pass)
                trade_rows.append(exported)
        fold_index += 1
        test_start += timedelta(days=step_days)
    folds = pd.DataFrame(fold_rows)
    trades = pd.concat(trade_rows, ignore_index=True, sort=False) if trade_rows else pd.DataFrame()
    return folds, trades


def _date_slice(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)
    return trades[(entry_ts >= start) & (entry_ts < end)].copy()


def aggregate_walk_forward(
    *,
    folds: pd.DataFrame,
    trades: pd.DataFrame,
    min_selected_folds: int,
    min_aggregate_test_trades: int,
    gate_win_rate: float,
    gate_profit_factor: float,
    gate_payoff_ratio: float,
    min_positive_test_fold_rate: float,
) -> pd.DataFrame:
    if folds.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    trade_groups = dict(tuple(trades.groupby("candidate", sort=False))) if not trades.empty else {}
    for candidate, group in folds.groupby("candidate", sort=False):
        candidate_trades = trade_groups.get(candidate, pd.DataFrame())
        test_summary = summarize_trades(candidate_trades)
        positive_fold_rate = float((pd.to_numeric(group["test_net_points"], errors="coerce") > 0).mean())
        fold_pass_rate = float(group["test_fold_pass"].mean()) if "test_fold_pass" in group else 0.0
        first = group.iloc[0]
        future_pass = (
            len(group) >= min_selected_folds
            and test_summary["trades"] >= min_aggregate_test_trades
            and test_summary["win_rate"] > gate_win_rate
            and test_summary["profit_factor"] > gate_profit_factor
            and test_summary["payoff_ratio"] > gate_payoff_ratio
            and test_summary["net_points"] > 0
            and positive_fold_rate >= min_positive_test_fold_rate
        )
        rows.append(
            {
                "future_pass": bool(future_pass),
                "candidate": candidate,
                "direction": first["direction"],
                "trigger": first["trigger"],
                "filters": first["filters"],
                "session": first["session"],
                "stop_points": first["stop_points"],
                "target_points": first["target_points"],
                "hold_bars": first["hold_bars"],
                "selected_folds": int(len(group)),
                "test_fold_pass_rate": fold_pass_rate,
                "positive_test_fold_rate": positive_fold_rate,
                "avg_train_win_rate": float(pd.to_numeric(group["train_win_rate"], errors="coerce").mean()),
                "avg_train_profit_factor": float(pd.to_numeric(group["train_profit_factor"], errors="coerce").mean()),
                "avg_train_payoff_ratio": float(pd.to_numeric(group["train_payoff_ratio"], errors="coerce").mean()),
                **{f"test_{key}": value for key, value in test_summary.items()},
            }
        )
    result = pd.DataFrame(rows)
    result["robust_score"] = _walk_forward_score(result)
    return result.sort_values(
        ["future_pass", "robust_score", "test_net_points", "test_profit_factor", "test_win_rate"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)


def _walk_forward_score(frame: pd.DataFrame) -> pd.Series:
    net = pd.to_numeric(frame["test_net_points"], errors="coerce").fillna(0.0)
    drawdown = pd.to_numeric(frame["test_max_drawdown_points"], errors="coerce").replace(0, 1.0).fillna(1.0)
    win_component = (pd.to_numeric(frame["test_win_rate"], errors="coerce").fillna(0.0) - 0.53).clip(lower=0) * 100.0
    pf_component = (pd.to_numeric(frame["test_profit_factor"], errors="coerce").fillna(0.0) - 1.0).clip(lower=0) * 20.0
    payoff_component = (pd.to_numeric(frame["test_payoff_ratio"], errors="coerce").fillna(0.0) - 1.0).clip(lower=0) * 15.0
    fold_component = pd.to_numeric(frame["positive_test_fold_rate"], errors="coerce").fillna(0.0) * 5.0
    return net / drawdown.clip(lower=1.0) + win_component + pf_component + payoff_component + fold_component


def build_candidates() -> list[TVStructureCandidate]:
    triggers = {
        "long": [
            "choch_long",
            "bos_long",
            "eql_reclaim",
            "demand_retest",
            "session_vwap_reclaim_up",
            "boll_breakout_up",
            "donchian_breakout_up",
            "mfi_recover_up",
            "cci_recover_up",
            "rsi_recover_up",
            "vfi_zero_cross_up",
            "vfi_signal_cross_up",
        ],
        "short": [
            "choch_short",
            "bos_short",
            "eqh_reject",
            "supply_retest",
            "session_vwap_reclaim_down",
            "boll_breakout_down",
            "donchian_breakout_down",
            "mfi_fade_down",
            "cci_fade_down",
            "rsi_fade_down",
            "vfi_zero_cross_down",
            "vfi_signal_cross_down",
        ],
    }
    filter_sets = {
        "long": [
            ("vfi_positive",),
            ("vfi_positive", "di_long"),
            ("range_discount", "vfi_hist_rising"),
            ("supertrend_long", "vfi_positive"),
            ("macd_positive", "adx_active"),
            ("stoch_recovering", "range_discount"),
            ("orderflow_bullish",),
            ("price_above_session_vwap", "volume_expanding"),
            ("session_vwap_stretch_low", "orderflow_bullish"),
            ("mfi_bullish", "cmf_positive"),
            ("cci_positive", "di_long"),
            ("boll_squeeze", "volume_expanding"),
            ("donchian_upper_half", "adx_active"),
            ("trend_stack_long", "session_vwap_above"),
        ],
        "short": [
            ("vfi_negative",),
            ("vfi_negative", "di_short"),
            ("range_premium", "vfi_hist_falling"),
            ("supertrend_short", "vfi_negative"),
            ("macd_negative", "adx_active"),
            ("stoch_fading", "range_premium"),
            ("orderflow_bearish",),
            ("price_below_session_vwap", "volume_expanding"),
            ("session_vwap_stretch_high", "orderflow_bearish"),
            ("mfi_bearish", "cmf_negative"),
            ("cci_negative", "di_short"),
            ("boll_squeeze", "volume_expanding"),
            ("donchian_lower_half", "adx_active"),
            ("trend_stack_short", "session_vwap_below"),
        ],
    }
    candidates: list[TVStructureCandidate] = []
    for side, direction in [("long", 1), ("short", -1)]:
        for trigger, filters, hold_bars, risk, session in itertools.product(
            triggers[side],
            filter_sets[side],
            [8, 15, 30],
            [(4.0, 6.0), (6.0, 9.0), (8.0, 12.0)],
            ["all", "us_rth", "ldn_ny"],
        ):
            stop, target = risk
            candidates.append(
                TVStructureCandidate(
                    name=f"{side}_{trigger}_{'_'.join(filters)}_sl{stop:g}_tp{target:g}_h{hold_bars}_{session}",
                    direction=direction,
                    trigger=trigger,
                    filters=tuple(filters),
                    stop_points=stop,
                    target_points=target,
                    hold_bars=hold_bars,
                    session=session,
                )
            )
    return candidates


def select_candidate_subset(candidates: list[TVStructureCandidate], max_candidates: int) -> list[TVStructureCandidate]:
    if max_candidates <= 0 or max_candidates >= len(candidates):
        return candidates
    longs = [candidate for candidate in candidates if candidate.direction > 0]
    shorts = [candidate for candidate in candidates if candidate.direction < 0]
    selected: list[TVStructureCandidate] = []
    for long_candidate, short_candidate in itertools.zip_longest(longs, shorts):
        if long_candidate is not None and len(selected) < max_candidates:
            selected.append(long_candidate)
        if short_candidate is not None and len(selected) < max_candidates:
            selected.append(short_candidate)
        if len(selected) >= max_candidates:
            break
    return selected


def build_or_load_candidate_trades(
    *,
    features: pd.DataFrame,
    candidates: list[TVStructureCandidate],
    costs: BacktestCosts,
    cache_path: Path | None,
) -> dict[str, pd.DataFrame]:
    signature = candidate_trades_cache_signature(features, candidates)
    if cache_path is not None and cache_path.exists():
        cached = pd.read_pickle(cache_path)
        if (
            isinstance(cached, dict)
            and cached.get("cache_signature") == signature
            and isinstance(cached.get("trades"), dict)
        ):
            return cached["trades"]
    context = build_trade_context(features)
    candidate_trades = {
        candidate.name: build_candidate_trades_from_context(context, candidate, costs)
        for candidate in candidates
    }
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        pd.to_pickle({"cache_signature": signature, "trades": candidate_trades}, cache_path)
    return candidate_trades


def candidate_trades_cache_signature(features: pd.DataFrame, candidates: list[TVStructureCandidate]) -> str:
    data = features.reset_index(drop=True)
    payload = {
        "version": 2,
        "feature_rows": int(len(data)),
        "start_ts": str(data["ts"].iloc[0]) if not data.empty and "ts" in data else "",
        "end_ts": str(data["ts"].iloc[-1]) if not data.empty and "ts" in data else "",
        "candidate_names": [candidate.name for candidate in candidates],
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def filter_candidates_by_signal_count(
    *,
    features: pd.DataFrame,
    candidates: list[TVStructureCandidate],
    min_total_signals: int,
    max_total_signals: int,
) -> tuple[list[TVStructureCandidate], dict[str, int]]:
    data = features.reset_index(drop=True)
    counts: dict[str, int] = {}
    selected: list[TVStructureCandidate] = []
    for candidate in candidates:
        count = int(candidate_signal_mask(data, candidate).sum())
        counts[candidate.name] = count
        if min_total_signals > 0 and count < min_total_signals:
            continue
        if max_total_signals > 0 and count > max_total_signals:
            continue
        selected.append(candidate)
    return selected, counts


def build_candidate_trades(features: pd.DataFrame, candidate: TVStructureCandidate, costs: BacktestCosts) -> pd.DataFrame:
    return build_candidate_trades_from_context(build_trade_context(features), candidate, costs)


def build_trade_context(features: pd.DataFrame) -> TradeBuildContext:
    data = features.reset_index(drop=True)
    segment_ids: np.ndarray | None = None
    if "symbol" in data.columns:
        symbols = data["symbol"].astype(str).to_numpy()
        segment_ids = np.zeros(len(symbols), dtype=np.int64)
        if len(symbols) > 1:
            segment_ids[1:] = np.cumsum(symbols[1:] != symbols[:-1])
    return TradeBuildContext(
        data=data,
        open_prices=data["Open"].to_numpy(dtype=float),
        high_prices=data["High"].to_numpy(dtype=float),
        low_prices=data["Low"].to_numpy(dtype=float),
        close_prices=data["Close"].to_numpy(dtype=float),
        timestamps=data["ts"].to_numpy(),
        segment_ids=segment_ids,
    )


def build_candidate_trades_from_context(
    context: TradeBuildContext,
    candidate: TVStructureCandidate,
    costs: BacktestCosts,
) -> pd.DataFrame:
    data = context.data
    signal = candidate_signal_mask(data, candidate)
    signal_indexes = np.flatnonzero(signal.fillna(False).to_numpy(dtype=bool))
    entry_indexes = signal_indexes + 1
    entry_indexes = entry_indexes[entry_indexes < len(data) - 1]
    if len(entry_indexes) == 0:
        return empty_trades_frame()

    planned_exit_indexes = np.minimum(entry_indexes + candidate.hold_bars, len(data) - 1)
    if context.segment_ids is not None:
        same_symbol = context.segment_ids[entry_indexes] == context.segment_ids[planned_exit_indexes]
        entry_indexes = entry_indexes[same_symbol]
        planned_exit_indexes = planned_exit_indexes[same_symbol]
        if len(entry_indexes) == 0:
            return empty_trades_frame()

    offsets = np.arange(candidate.hold_bars + 1, dtype=np.int64)
    window_indexes = np.minimum(entry_indexes[:, None] + offsets[None, :], len(data) - 1)
    entry_prices = context.open_prices[entry_indexes]
    if candidate.direction > 0:
        stop_prices = entry_prices - candidate.stop_points
        target_prices = entry_prices + candidate.target_points
        stop_hits = context.low_prices[window_indexes] <= stop_prices[:, None]
        target_hits = context.high_prices[window_indexes] >= target_prices[:, None]
    else:
        stop_prices = entry_prices + candidate.stop_points
        target_prices = entry_prices - candidate.target_points
        stop_hits = context.high_prices[window_indexes] >= stop_prices[:, None]
        target_hits = context.low_prices[window_indexes] <= target_prices[:, None]

    no_hit_offset = candidate.hold_bars + 1
    first_stop_offsets = np.where(stop_hits.any(axis=1), stop_hits.argmax(axis=1), no_hit_offset)
    first_target_offsets = np.where(target_hits.any(axis=1), target_hits.argmax(axis=1), no_hit_offset)
    stop_first = first_stop_offsets <= first_target_offsets
    has_stop = first_stop_offsets < no_hit_offset
    has_target = first_target_offsets < no_hit_offset
    realized_offsets = np.where(
        has_stop & stop_first,
        first_stop_offsets,
        np.where(has_target, first_target_offsets, planned_exit_indexes - entry_indexes),
    ).astype(np.int64)
    realized_exit_indexes = entry_indexes + realized_offsets
    exit_prices = np.where(
        has_stop & stop_first,
        stop_prices,
        np.where(has_target, target_prices, context.close_prices[planned_exit_indexes]),
    )
    exit_reasons = np.full(len(entry_indexes), "timeout", dtype=object)
    target_first = has_target & ~(has_stop & stop_first)
    exit_reasons[target_first] = "take_profit"
    stop_only = has_stop & stop_first & ~(has_target & (first_stop_offsets == first_target_offsets))
    ambiguous = has_stop & has_target & (first_stop_offsets == first_target_offsets)
    exit_reasons[stop_only] = "stop_loss"
    exit_reasons[ambiguous] = "stop_loss_ambiguous"

    rows: list[dict[str, Any]] = []
    next_available = 0
    for array_index, entry_index in enumerate(entry_indexes):
        entry_index = int(entry_index)
        if entry_index < next_available:
            continue
        realized_exit_index = int(realized_exit_indexes[array_index])
        entry_price = float(entry_prices[array_index])
        exit_price = float(exit_prices[array_index])
        gross_points = (exit_price - entry_price) * candidate.direction
        net_points = gross_points - costs.round_trip_cost_points
        rows.append(
            {
                "entry_ts": context.timestamps[entry_index],
                "exit_ts": context.timestamps[realized_exit_index],
                "direction": candidate.direction,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_points": float(gross_points),
                "net_points": float(net_points),
                "exit_reason": str(exit_reasons[array_index]),
            }
        )
        next_available = realized_exit_index + 1
    return pd.DataFrame(rows)


def candidate_signal_mask(data: pd.DataFrame, candidate: TVStructureCandidate) -> pd.Series:
    signal = trigger_mask(data, candidate.trigger) & session_mask(data, candidate.session)
    for filter_name in candidate.filters:
        signal &= filter_mask(data, filter_name)
    return signal.fillna(False)


def empty_trades_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "entry_ts",
            "exit_ts",
            "direction",
            "entry_price",
            "exit_price",
            "gross_points",
            "net_points",
            "exit_reason",
        ]
    )


def trigger_mask(data: pd.DataFrame, trigger: str) -> pd.Series:
    if trigger == "choch_long":
        return data["choch_signal"] > 0
    if trigger == "choch_short":
        return data["choch_signal"] < 0
    if trigger == "bos_long":
        return data["bos_signal"] > 0
    if trigger == "bos_short":
        return data["bos_signal"] < 0
    if trigger == "eql_reclaim":
        return data["eql_signal"] > 0
    if trigger == "eqh_reject":
        return data["eqh_signal"] > 0
    if trigger == "demand_retest":
        return data["demand_zone_retest"] > 0
    if trigger == "supply_retest":
        return data["supply_zone_retest"] > 0
    if trigger == "session_vwap_reclaim_up":
        return data["session_vwap_reclaim_up"] > 0
    if trigger == "session_vwap_reclaim_down":
        return data["session_vwap_reclaim_down"] > 0
    if trigger == "boll_breakout_up":
        return data["boll_breakout_up"] > 0
    if trigger == "boll_breakout_down":
        return data["boll_breakout_down"] > 0
    if trigger == "donchian_breakout_up":
        return (data["donchian_20_position"] >= 1.0) & (data["donchian_20_position"].shift(1) < 1.0)
    if trigger == "donchian_breakout_down":
        return (data["donchian_20_position"] <= 0.0) & (data["donchian_20_position"].shift(1) > 0.0)
    if trigger == "mfi_recover_up":
        return (data["mfi_14"] > 30) & (data["mfi_14"].shift(1) <= 30)
    if trigger == "mfi_fade_down":
        return (data["mfi_14"] < 70) & (data["mfi_14"].shift(1) >= 70)
    if trigger == "cci_recover_up":
        return (data["cci_20"] > -100) & (data["cci_20"].shift(1) <= -100)
    if trigger == "cci_fade_down":
        return (data["cci_20"] < 100) & (data["cci_20"].shift(1) >= 100)
    if trigger == "rsi_recover_up":
        return (data["rsi_14"] > 35) & (data["rsi_14"].shift(1) <= 35)
    if trigger == "rsi_fade_down":
        return (data["rsi_14"] < 65) & (data["rsi_14"].shift(1) >= 65)
    if trigger == "vfi_zero_cross_up":
        return data["vfi_zero_cross_up"] > 0
    if trigger == "vfi_zero_cross_down":
        return data["vfi_zero_cross_down"] > 0
    if trigger == "vfi_signal_cross_up":
        return data["vfi_cross_up"] > 0
    if trigger == "vfi_signal_cross_down":
        return data["vfi_cross_down"] > 0
    raise ValueError(f"unknown trigger: {trigger}")


def filter_mask(data: pd.DataFrame, filter_name: str) -> pd.Series:
    if filter_name == "vfi_positive":
        return data["vfi_130"] > 0
    if filter_name == "vfi_negative":
        return data["vfi_130"] < 0
    if filter_name == "di_long":
        return data["di_spread_14"] > 0
    if filter_name == "di_short":
        return data["di_spread_14"] < 0
    if filter_name == "range_discount":
        return data["range_100_position"] < 0.35
    if filter_name == "range_premium":
        return data["range_100_position"] > 0.65
    if filter_name == "vfi_hist_rising":
        return data["vfi_hist"] > data["vfi_hist"].shift(3)
    if filter_name == "vfi_hist_falling":
        return data["vfi_hist"] < data["vfi_hist"].shift(3)
    if filter_name == "supertrend_long":
        return data["supertrend_direction"] > 0
    if filter_name == "supertrend_short":
        return data["supertrend_direction"] < 0
    if filter_name == "macd_positive":
        return data["macd_hist"] > 0
    if filter_name == "macd_negative":
        return data["macd_hist"] < 0
    if filter_name == "adx_active":
        return data["adx_14"] >= 20
    if filter_name == "stoch_recovering":
        return (data["stoch_rsi_k"] > data["stoch_rsi_d"]) & (data["stoch_rsi_k"] < 80)
    if filter_name == "stoch_fading":
        return (data["stoch_rsi_k"] < data["stoch_rsi_d"]) & (data["stoch_rsi_k"] > 20)
    if filter_name == "orderflow_bullish":
        return (data["cmf_20"] > 0) & (data["obv_slope_20"] > 0)
    if filter_name == "orderflow_bearish":
        return (data["cmf_20"] < 0) & (data["obv_slope_20"] < 0)
    if filter_name == "price_above_session_vwap":
        return data["Close"] > data["session_vwap"]
    if filter_name == "price_below_session_vwap":
        return data["Close"] < data["session_vwap"]
    if filter_name == "session_vwap_above":
        return data["session_vwap_distance_atr"] > 0
    if filter_name == "session_vwap_below":
        return data["session_vwap_distance_atr"] < 0
    if filter_name == "session_vwap_stretch_low":
        return data["session_vwap_distance_atr"] < -0.5
    if filter_name == "session_vwap_stretch_high":
        return data["session_vwap_distance_atr"] > 0.5
    if filter_name == "volume_expanding":
        return data["relative_volume_20"] >= 1.2
    if filter_name == "mfi_bullish":
        return data["mfi_14"] > 50
    if filter_name == "mfi_bearish":
        return data["mfi_14"] < 50
    if filter_name == "cmf_positive":
        return data["cmf_20"] > 0
    if filter_name == "cmf_negative":
        return data["cmf_20"] < 0
    if filter_name == "cci_positive":
        return data["cci_20"] > 0
    if filter_name == "cci_negative":
        return data["cci_20"] < 0
    if filter_name == "boll_squeeze":
        return data["boll_squeeze"] > 0
    if filter_name == "donchian_upper_half":
        return data["donchian_20_position"] > 0.5
    if filter_name == "donchian_lower_half":
        return data["donchian_20_position"] < 0.5
    if filter_name == "trend_stack_long":
        return (data["ema_10"] > data["ema_20"]) & (data["ema_20"] > data["ema_50"])
    if filter_name == "trend_stack_short":
        return (data["ema_10"] < data["ema_20"]) & (data["ema_20"] < data["ema_50"])
    raise ValueError(f"unknown filter: {filter_name}")


def session_mask(data: pd.DataFrame, session: str) -> pd.Series:
    minute = data["minute_of_day"]
    if session == "all":
        return pd.Series(True, index=data.index)
    if session == "us_rth":
        return (minute >= 13 * 60 + 30) & (minute < 20 * 60)
    if session == "ldn_ny":
        return (minute >= 7 * 60) & (minute < 20 * 60)
    raise ValueError(f"unknown session: {session}")


def summarize_trades(trades: pd.DataFrame) -> dict[str, float | int]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "payoff_ratio": 0.0,
            "expectancy_points": 0.0,
            "max_drawdown_points": 0.0,
        }
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0)
    wins = net[net > 0]
    losses = net[net < 0]
    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss_abs = float(-losses.mean()) if not losses.empty else 0.0
    return {
        "trades": int(len(net)),
        "net_points": float(net.sum()),
        "profit_factor": float(gross_win / gross_loss) if gross_loss else (999.0 if gross_win > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "payoff_ratio": float(avg_win / avg_loss_abs) if avg_loss_abs else (999.0 if avg_win > 0 else 0.0),
        "expectancy_points": float(net.mean()),
        "max_drawdown_points": float(drawdown.max()) if not drawdown.empty else 0.0,
    }


def build_report(
    *,
    summary_frame: pd.DataFrame,
    trades_frame: pd.DataFrame,
    start_date: str,
    end_date: str,
    train_end_date: str,
    feature_rows: int,
    min_test_trades: int,
    gate_win_rate: float,
    gate_profit_factor: float,
    summary_output: Path,
    trades_output: Path,
) -> str:
    passing = int(summary_frame["passes_test_gate"].sum()) if not summary_frame.empty else 0
    best = summary_frame.head(1).to_dict(orient="records")[0] if not summary_frame.empty else {}
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ TradingView Structure Strategy Search</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#f6f8fb; color:#17212b; margin:0; }}
    main {{ max-width:1280px; margin:0 auto; padding:28px; }}
    h1 {{ font-size:30px; margin:0 0 10px; }}
    h2 {{ font-size:20px; margin:28px 0 12px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }}
    .metric, section {{ background:white; border:1px solid #dce3ea; border-radius:8px; padding:16px; }}
    .label {{ color:#5f6b78; font-size:13px; }}
    .value {{ font-size:23px; font-weight:700; margin-top:4px; }}
    .wrap {{ max-height:650px; overflow:auto; border:1px solid #dce3ea; border-radius:8px; }}
    table {{ border-collapse:collapse; width:100%; font-size:13px; background:white; }}
    th, td {{ border-bottom:1px solid #e5e9ee; padding:8px 10px; text-align:left; vertical-align:top; }}
    th {{ background:#eef3f8; position:sticky; top:0; }}
    .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
    .pass {{ color:#08783f; font-weight:700; }}
    .fail {{ color:#a24100; font-weight:700; }}
    code {{ background:#edf2f7; padding:2px 4px; border-radius:4px; }}
  </style>
</head>
<body>
<main>
  <h1>NQ TradingView 结构/指标策略搜索</h1>
  <p>从截图抽象出 BOS/ChoCH、EQH/EQL、供需区 retest、VWAP reclaim、Bollinger/Donchian breakout、MFI/CCI/RSI 恢复、VFI 资金流、ADX/DI、MACD、Stoch RSI、Supertrend 与量价确认等可复现特征，并在 2020+ 1分钟连续 NQ 数据上做训练/测试拆分。</p>
  <div class="grid">
    {_metric("通过测试门槛", f"{passing}/{len(summary_frame)}")}
    {_metric("最佳策略", _esc(best.get("name", "N/A")))}
    {_metric("测试 Win", _fmt_pct(best.get("test_win_rate")))}
    {_metric("测试 PF", _fmt_num(best.get("test_profit_factor")))}
    {_metric("测试 Net", _fmt_num(best.get("test_net_points")))}
    {_metric("Feature Rows", f"{feature_rows:,}")}
  </div>
  <section>
    <h2>门槛</h2>
    <p>训练窗口：{_esc(start_date)} 到 {_esc(train_end_date)}；测试窗口：{_esc(train_end_date)} 到 {_esc(end_date)}。测试门槛：交易数 >= <code>{min_test_trades}</code>，胜率 &gt; <code>{gate_win_rate:.2%}</code>，PF &gt; <code>{gate_profit_factor:.2f}</code>。</p>
    <p>CSV 输出：<code>{_esc(summary_output)}</code>，<code>{_esc(trades_output)}</code>。</p>
  </section>
  <section>
    <h2>Top 候选</h2>
    <div class="wrap">{_table(summary_frame.head(100), _summary_columns())}</div>
  </section>
  <section>
    <h2>交易样本</h2>
    <div class="wrap">{_table(trades_frame.tail(300), ["candidate", "entry_ts", "exit_ts", "direction", "entry_price", "exit_price", "net_points", "exit_reason"])}</div>
  </section>
</main>
</body>
</html>
"""


def build_walk_forward_report(
    *,
    aggregate: pd.DataFrame,
    folds: pd.DataFrame,
    trades: pd.DataFrame,
    start_date: str,
    end_date: str,
    walk_start_date: str,
    feature_rows: int,
    min_train_trades: int,
    min_test_trades: int,
    gate_win_rate: float,
    gate_profit_factor: float,
    gate_payoff_ratio: float,
    min_selected_folds: int,
    min_positive_test_fold_rate: float,
    fold_output: Path,
    aggregate_output: Path,
    trades_output: Path,
) -> str:
    passing = int(aggregate["future_pass"].sum()) if not aggregate.empty else 0
    best = aggregate.head(1).to_dict(orient="records")[0] if not aggregate.empty else {}
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ TradingView Structure Walk-Forward</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#f6f8fb; color:#17212b; margin:0; }}
    main {{ max-width:1280px; margin:0 auto; padding:28px; }}
    h1 {{ font-size:30px; margin:0 0 10px; }}
    h2 {{ font-size:20px; margin:28px 0 12px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }}
    .metric, section {{ background:white; border:1px solid #dce3ea; border-radius:8px; padding:16px; }}
    .label {{ color:#5f6b78; font-size:13px; }}
    .value {{ font-size:23px; font-weight:700; margin-top:4px; }}
    .wrap {{ max-height:650px; overflow:auto; border:1px solid #dce3ea; border-radius:8px; }}
    table {{ border-collapse:collapse; width:100%; font-size:13px; background:white; }}
    th, td {{ border-bottom:1px solid #e5e9ee; padding:8px 10px; text-align:left; vertical-align:top; }}
    th {{ background:#eef3f8; position:sticky; top:0; }}
    .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
    .pass {{ color:#08783f; font-weight:700; }}
    .fail {{ color:#a24100; font-weight:700; }}
    code {{ background:#edf2f7; padding:2px 4px; border-radius:4px; }}
  </style>
</head>
<body>
<main>
  <h1>NQ TradingView 结构策略 Walk-Forward</h1>
  <p>该报告只允许策略从过去训练窗入选，再验证未来测试窗；候选池覆盖 VWAP、Bollinger、Donchian、MFI、CCI、RSI、VFI、ADX/DI、MACD、Stoch RSI、Supertrend、ICT 结构与量价关系，以降低全样本数据挖掘偏差。</p>
  <div class="grid">
    {_metric("通过聚合门槛", f"{passing}/{len(aggregate)}")}
    {_metric("最佳候选", _esc(best.get("candidate", "N/A")))}
    {_metric("测试 Win", _fmt_pct(best.get("test_win_rate")))}
    {_metric("测试 PF", _fmt_num(best.get("test_profit_factor")))}
    {_metric("测试 Payoff", _fmt_num(best.get("test_payoff_ratio")))}
    {_metric("正收益折比例", _fmt_pct(best.get("positive_test_fold_rate")))}
    {_metric("Feature Rows", f"{feature_rows:,}")}
    {_metric("Fold Rows", f"{len(folds):,}")}
  </div>
  <section>
    <h2>门槛</h2>
    <p>数据：{_esc(start_date)} 到 {_esc(end_date)}；walk-forward 起点：{_esc(walk_start_date)}。训练入选需交易数 >= <code>{min_train_trades}</code>，测试折交易数 >= <code>{min_test_trades}</code>。聚合通过需 selected folds >= <code>{min_selected_folds}</code>，胜率 &gt; <code>{gate_win_rate:.2%}</code>，PF &gt; <code>{gate_profit_factor:.2f}</code>，payoff &gt; <code>{gate_payoff_ratio:.2f}</code>，正收益折比例 >= <code>{min_positive_test_fold_rate:.2%}</code>。</p>
    <p>CSV 输出：<code>{_esc(fold_output)}</code>，<code>{_esc(aggregate_output)}</code>，<code>{_esc(trades_output)}</code>。</p>
  </section>
  <section>
    <h2>聚合排名</h2>
    <div class="wrap">{_table(aggregate.head(100), _walk_aggregate_columns())}</div>
  </section>
  <section>
    <h2>Fold 样本</h2>
    <div class="wrap">{_table(folds.head(300), _walk_fold_columns())}</div>
  </section>
  <section>
    <h2>交易样本</h2>
    <div class="wrap">{_table(trades.tail(300), ["candidate", "fold", "entry_ts", "exit_ts", "direction", "entry_price", "exit_price", "net_points", "exit_reason"])}</div>
  </section>
</main>
</body>
</html>
"""


def record_search_memory(
    memory_db: Path,
    summary_frame: pd.DataFrame,
    min_test_trades: int,
    gate_win_rate: float,
    gate_profit_factor: float,
) -> None:
    memory = EvolutionMemory(memory_db)
    try:
        now = utc_now()
        for _, row in summary_frame.head(50).iterrows():
            name = str(row["name"])
            note_type = "effective_feature" if bool(row["passes_test_gate"]) else "failure_mode"
            signature = "tv_" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:16]
            note_id = f"note_{signature}_{note_type}_{int(row['test_trades'])}"
            lesson = (
                f"TradingView-style structure search candidate {name}: test trades={int(row['test_trades'])}, "
                f"win_rate={float(row['test_win_rate']):.2%}, PF={float(row['test_profit_factor']):.2f}, "
                f"net={float(row['test_net_points']):.2f}. Gate requires trades>={min_test_trades}, "
                f"win_rate>{gate_win_rate:.2%}, PF>{gate_profit_factor:.2f}."
            )
            avoid_when = "Avoid as standalone strategy until it passes OOS win-rate/PF gate."
            if bool(row["passes_test_gate"]):
                avoid_when = "Avoid if later walk-forward folds fall below OOS gate."
            memory.connection.execute(
                """
                INSERT OR REPLACE INTO experience_notes (
                    note_id, rule_signature, note_type, regime, applies_when, avoid_when,
                    lesson, evidence_summary, confidence, status, supersedes_note_id,
                    created_at, last_used_at, use_count
                ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, 'active', NULL, ?, NULL, 0)
                """,
                (
                    note_id,
                    signature,
                    note_type,
                    f"Candidate trigger={row['trigger']}; filters={row['filters']}; session={row['session']}",
                    avoid_when,
                    lesson,
                    (
                        f"train_trades={int(row['train_trades'])}; train_pf={float(row['train_profit_factor']):.4f}; "
                        f"test_trades={int(row['test_trades'])}; test_pf={float(row['test_profit_factor']):.4f}; "
                        f"test_win_rate={float(row['test_win_rate']):.4f}; test_net={float(row['test_net_points']):.2f}"
                    ),
                    min(1.0, max(0.05, float(row["test_trades"]) / 300.0)),
                    now,
                ),
            )
        memory.limit_active_notes()
        memory.connection.commit()
    finally:
        memory.close()


def record_walk_forward_memory(
    memory_db: Path,
    aggregate: pd.DataFrame,
    folds: pd.DataFrame,
    gate_win_rate: float,
    gate_profit_factor: float,
    gate_payoff_ratio: float,
) -> None:
    memory = EvolutionMemory(memory_db)
    try:
        now = utc_now()
        for _, row in aggregate.head(50).iterrows():
            candidate = str(row["candidate"])
            note_type = "effective_feature" if bool(row["future_pass"]) else "failure_mode"
            signature = "tvwf_" + hashlib.sha1(candidate.encode("utf-8")).hexdigest()[:16]
            note_id = f"note_{signature}_{note_type}_{int(row['selected_folds'])}_{int(row['test_trades'])}"
            applies_when = f"Walk-forward candidate trigger={row['trigger']}; filters={row['filters']}; session={row['session']}"
            avoid_when = "Avoid as standalone strategy until walk-forward aggregate passes all OOS gates."
            if bool(row["future_pass"]):
                avoid_when = "Avoid if later walk-forward refresh drops below win/PF/payoff or positive-fold gates."
            lesson = (
                f"TradingView walk-forward candidate {candidate}: folds={int(row['selected_folds'])}, "
                f"test_trades={int(row['test_trades'])}, win_rate={float(row['test_win_rate']):.2%}, "
                f"PF={float(row['test_profit_factor']):.2f}, payoff={float(row['test_payoff_ratio']):.2f}, "
                f"positive_fold_rate={float(row['positive_test_fold_rate']):.2%}."
            )
            memory.connection.execute(
                """
                INSERT OR REPLACE INTO experience_notes (
                    note_id, rule_signature, note_type, regime, applies_when, avoid_when,
                    lesson, evidence_summary, confidence, status, supersedes_note_id,
                    created_at, last_used_at, use_count
                ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, 'active', NULL, ?, NULL, 0)
                """,
                (
                    note_id,
                    signature,
                    note_type,
                    applies_when,
                    avoid_when,
                    lesson,
                    (
                        f"future_pass={bool(row['future_pass'])}; selected_folds={int(row['selected_folds'])}; "
                        f"test_trades={int(row['test_trades'])}; test_win_rate={float(row['test_win_rate']):.4f}; "
                        f"test_profit_factor={float(row['test_profit_factor']):.4f}; "
                        f"test_payoff_ratio={float(row['test_payoff_ratio']):.4f}; "
                        f"gate_win>{gate_win_rate:.4f}; gate_pf>{gate_profit_factor:.4f}; gate_payoff>{gate_payoff_ratio:.4f}"
                    ),
                    min(1.0, max(0.05, float(row["selected_folds"]) / max(len(folds["fold"].unique()) if not folds.empty else 1, 1))),
                    now,
                ),
            )
        memory.limit_active_notes()
        memory.connection.commit()
    finally:
        memory.close()


def _summary_columns() -> list[str]:
    return [
        "passes_test_gate",
        "name",
        "direction",
        "trigger",
        "filters",
        "session",
        "total_signals",
        "stop_points",
        "target_points",
        "hold_bars",
        "train_trades",
        "train_net_points",
        "train_profit_factor",
        "train_win_rate",
        "test_trades",
        "test_net_points",
        "test_profit_factor",
        "test_win_rate",
        "test_payoff_ratio",
        "test_max_drawdown_points",
    ]


def _walk_aggregate_columns() -> list[str]:
    return [
        "future_pass",
        "candidate",
        "selected_folds",
        "test_trades",
        "test_net_points",
        "test_profit_factor",
        "test_win_rate",
        "test_payoff_ratio",
        "positive_test_fold_rate",
        "test_fold_pass_rate",
        "robust_score",
        "trigger",
        "filters",
        "session",
        "stop_points",
        "target_points",
        "hold_bars",
    ]


def _walk_fold_columns() -> list[str]:
    return [
        "test_fold_pass",
        "candidate",
        "fold",
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "train_trades",
        "train_win_rate",
        "train_profit_factor",
        "train_payoff_ratio",
        "test_trades",
        "test_win_rate",
        "test_profit_factor",
        "test_payoff_ratio",
        "test_net_points",
    ]


def _table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    available = [column for column in columns if column in frame.columns]
    header = "".join(f"<th>{_esc(column)}</th>" for column in available)
    body = []
    for _, row in frame[available].iterrows():
        cells = []
        for column in available:
            value = row[column]
            css = "num" if _is_number(value) and not isinstance(value, bool) else ""
            if isinstance(value, bool):
                text = "PASS" if value else "FAIL"
                css = "pass" if value else "fail"
            elif "rate" in column and _is_number(value):
                text = _fmt_pct(value)
            elif _is_number(value):
                text = _fmt_num(value)
            else:
                text = _esc(value)
            cells.append(f"<td class=\"{css}\">{text}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _metric(label: str, value: str) -> str:
    return f"<div class=\"metric\"><div class=\"label\">{_esc(label)}</div><div class=\"value\">{value}</div></div>"


def _fmt_pct(value: Any) -> str:
    return f"{float(value):.2%}" if _is_number(value) else "N/A"


def _fmt_num(value: Any) -> str:
    if not _is_number(value):
        return "N/A"
    return f"{float(value):,.3f}"


def _is_number(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return pd.notna(value)


def _esc(value: Any) -> str:
    return html.escape(str(value))


if __name__ == "__main__":
    raise SystemExit(main())
