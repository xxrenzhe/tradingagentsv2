from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backtest_lightglow_nq_bars import LightglowCandidate, build_lightglow_signals, build_trades
from generate_nq_lightglow_composite_report import (
    add_prior_trend_context,
    candlestick_svg,
    fmt_num,
    fmt_pct,
    fmt_signed,
    html_table,
    line_svg,
    load_bars,
    max_drawdown,
    profit_factor,
    read_trades,
    summarize_trades,
    timecell_trend_veto_mask,
)
from tradingagents.backtesting.short_patterns import BacktestCosts


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_FEATURE_TRADES = ".tmp/nq-2020-lightglow-feature-trades.pkl"
DEFAULT_COMPOSITE_TRADES = ".tmp/nq-composite-with-lightglow-selected.csv"
DEFAULT_LIGHTGLOW_OOS_TRADES = ".tmp/nq-lightglow-oos2022-selected.csv"
DEFAULT_BARS = ".tmp/nq-2020-final-report-bars.pkl"
DEFAULT_REPORT = "reports/NQ-lightglow-composite-paper-readiness.html"
DEFAULT_MARKDOWN = "reports/NQ-lightglow-composite-paper-readiness.md"
DEFAULT_SUMMARY = ".tmp/nq-lightglow-composite-paper-readiness-summary.json"
DEFAULT_WALK_FORWARD = ".tmp/nq-lightglow-composite-paper-readiness-walkforward.csv"
DEFAULT_STRESS = ".tmp/nq-lightglow-composite-paper-readiness-stress.csv"
DEFAULT_LEAKAGE = ".tmp/nq-lightglow-composite-paper-readiness-leakage.csv"
DEFAULT_LOSS_LEARNING = ".tmp/nq-lightglow-composite-paper-readiness-loss-learning.csv"
DEFAULT_REVERSE_DIAGNOSTIC = ".tmp/nq-lightglow-composite-paper-readiness-reverse-diagnostic.csv"
DEFAULT_PAPER_PLAN = "reports/NQ-lightglow-composite-paper-validation-plan.csv"

ROUND_TRIP_COST_POINTS = 0.625
LIGHTGLOW_LABEL = "Stable 2020-2021 trained action map"
TIMECELL_LABEL = "rollstable_trainpf105_timecell"
LIGHTGLOW_SOURCE = "lightglow_research"
TIMECELL_SOURCE = "rollstable_timecell_oos"
STATIC_SCAN_FILES = [
    "scripts/backtest_lightglow_nq_bars.py",
    "scripts/search_nq_2020_rollstable_lightglow.py",
    "scripts/generate_nq_2020_lightglow_seasonal_report.py",
    "scripts/generate_nq_lightglow_composite_report.py",
    "scripts/generate_nq_lightglow_paper_readiness_report.py",
]


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: int
    train_end: int
    test_year: int

    @property
    def label(self) -> str:
        return f"{self.train_start}-{self.train_end}->{self.test_year}"

    @property
    def train_years(self) -> list[int]:
        return list(range(self.train_start, self.train_end + 1))


WALK_FORWARD_WINDOWS = (
    WalkForwardWindow(2020, 2021, 2022),
    WalkForwardWindow(2020, 2022, 2023),
    WalkForwardWindow(2021, 2023, 2024),
    WalkForwardWindow(2022, 2024, 2025),
)


def esc(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return html.escape(str(value), quote=True)


def load_feature_trades(path: str | Path) -> pd.DataFrame:
    frame = pd.read_pickle(path).copy()
    for column in ("entry_ts", "exit_ts"):
        frame[column] = pd.to_datetime(frame[column], utc=True)
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype(int)
    frame["month"] = pd.to_numeric(frame["month"], errors="coerce").astype(int)
    frame["dow"] = pd.to_numeric(frame["dow"], errors="coerce").astype(int)
    frame["gross_points"] = pd.to_numeric(frame["gross_points"], errors="coerce").fillna(0.0)
    frame["net_points"] = pd.to_numeric(frame["net_points"], errors="coerce").fillna(0.0)
    return frame.sort_values("entry_ts").reset_index(drop=True)


def train_month_dow_action_map(
    trades: pd.DataFrame,
    train_years: list[int],
    *,
    min_cell_trades: int = 30,
    min_action_net: float = 0.0,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    train = trades[trades["year"].isin(train_years)].copy()
    for (month, dow), group in train.groupby(["month", "dow"], dropna=False):
        if len(group) < min_cell_trades:
            continue
        native_net = float(group["net_points"].sum())
        reverse_net = float((-group["gross_points"] - ROUND_TRIP_COST_POINTS).sum())
        action = "native" if native_net >= reverse_net else "reverse"
        chosen_net = max(native_net, reverse_net)
        if chosen_net < min_action_net:
            continue
        records.append(
            {
                "month": int(month),
                "dow": int(dow),
                "action": action,
                "train_net_points": chosen_net,
                "train_trades": int(len(group)),
                "native_train_net_points": native_net,
                "reverse_train_net_points": reverse_net,
            }
        )
    records.sort(key=lambda item: (item["train_net_points"], item["train_trades"]), reverse=True)
    return records


def apply_action_map(trades: pd.DataFrame, actions: list[dict[str, Any]], label: str = LIGHTGLOW_LABEL) -> pd.DataFrame:
    lookup = {(int(item["month"]), int(item["dow"])): str(item["action"]) for item in actions}
    if not lookup:
        return pd.DataFrame(columns=list(trades.columns) + ["action", "base_direction", "strategy_label", "rule_key"])
    keys = list(zip(trades["month"].astype(int), trades["dow"].astype(int)))
    selected = trades.loc[[key in lookup for key in keys]].copy()
    if selected.empty:
        return selected
    selected_keys = list(zip(selected["month"].astype(int), selected["dow"].astype(int)))
    selected["action"] = [lookup[key] for key in selected_keys]
    sign = np.where(selected["action"].eq("native"), 1.0, -1.0)
    selected["base_direction"] = selected["direction"].astype(int)
    selected["direction"] = (selected["base_direction"].to_numpy(dtype=int) * sign).astype(int)
    selected["gross_points"] = selected["gross_points"].to_numpy(dtype=float) * sign
    selected["net_points"] = selected["gross_points"] - ROUND_TRIP_COST_POINTS
    selected["strategy_source"] = LIGHTGLOW_SOURCE
    selected["strategy_label"] = label
    selected["feature_family"] = "lightglow_premium_discount_reversal"
    selected["risk_weight"] = 1.0
    selected["rule_key"] = selected["month"].astype(str) + "-" + selected["dow"].astype(str)
    selected["entry_exec_ts"] = selected["entry_ts"] + pd.Timedelta(minutes=1)
    return selected.sort_values(["entry_ts", "exit_ts"]).reset_index(drop=True)


def full_metric_row(trades: pd.DataFrame, *, label: str) -> dict[str, Any]:
    if trades.empty:
        return {
            "label": label,
            "trades": 0,
            "net_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "best_trade_points": 0.0,
            "worst_trade_points": 0.0,
            "max_drawdown_points": 0.0,
            "worst_month_points": 0.0,
            "worst_90d_points": 0.0,
            "positive_90d_rate": 0.0,
        }
    trades = trades.copy()
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    points = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    monthly = points.groupby(trades["entry_ts"].dt.strftime("%Y-%m")).sum()
    daily = points.groupby(trades["entry_ts"].dt.floor("D")).sum().sort_index()
    rolling_90d = daily.rolling(90, min_periods=min(30, len(daily))).sum().dropna()
    return {
        "label": label,
        "trades": int(len(trades)),
        "net_points": float(points.sum()),
        "profit_factor": profit_factor(points),
        "win_rate": float((points > 0).mean()),
        "best_trade_points": float(points.max()),
        "worst_trade_points": float(points.min()),
        "max_drawdown_points": max_drawdown(points),
        "worst_month_points": float(monthly.min()) if not monthly.empty else 0.0,
        "worst_90d_points": float(rolling_90d.min()) if not rolling_90d.empty else 0.0,
        "positive_90d_rate": float((rolling_90d > 0).mean()) if not rolling_90d.empty else 0.0,
    }


def run_walk_forward(feature_trades: pd.DataFrame, timecell_trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    selected_frames: list[pd.DataFrame] = []
    feature_trades = feature_trades.copy()
    timecell_trades = timecell_trades.copy()
    feature_trades["entry_ts"] = pd.to_datetime(feature_trades["entry_ts"], utc=True)
    feature_trades["exit_ts"] = pd.to_datetime(feature_trades["exit_ts"], utc=True)
    timecell_trades["entry_ts"] = pd.to_datetime(timecell_trades["entry_ts"], utc=True)
    timecell_trades["exit_ts"] = pd.to_datetime(timecell_trades["exit_ts"], utc=True)
    for window in WALK_FORWARD_WINDOWS:
        actions = train_month_dow_action_map(feature_trades, window.train_years)
        lightglow_test = apply_action_map(
            feature_trades[feature_trades["year"].eq(window.test_year)].copy(),
            actions,
            label=f"wf_{window.label}_lightglow",
        )
        timecell_test = timecell_trades[
            timecell_trades["entry_ts"].dt.year.eq(window.test_year)
            & timecell_trades["strategy_source"].astype(str).eq(TIMECELL_SOURCE)
        ].copy()
        combo = pd.concat([lightglow_test, timecell_test], ignore_index=True, sort=False)
        combo = combo.sort_values(["entry_ts", "exit_ts"]).reset_index(drop=True)
        budgeted = combo.copy()
        budgeted["net_points"] = budgeted["net_points"] * budgeted["risk_weight"].fillna(1.0)
        row = {
            "window": window.label,
            "train_start": window.train_start,
            "train_end": window.train_end,
            "test_year": window.test_year,
            "action_cells": len(actions),
            "lightglow_trades": len(lightglow_test),
            "timecell_trades": len(timecell_test),
            **{f"raw_{key}": value for key, value in full_metric_row(combo, label=window.label).items() if key != "label"},
            **{
                f"budgeted_{key}": value
                for key, value in full_metric_row(budgeted, label=f"{window.label}_budgeted").items()
                if key != "label"
            },
        }
        for extra in (0.5, 1.5, 2.5, 4.375):
            stressed = lightglow_test.copy()
            stressed["net_points"] = stressed["net_points"] - extra
            row[f"lightglow_extra_{extra:g}_net_points"] = float(stressed["net_points"].sum())
            row[f"lightglow_extra_{extra:g}_profit_factor"] = profit_factor(stressed["net_points"])
        rows.append(row)
        if not combo.empty:
            combo["walk_forward_window"] = window.label
            selected_frames.append(combo)
    selected = pd.concat(selected_frames, ignore_index=True, sort=False) if selected_frames else pd.DataFrame()
    if not selected.empty:
        selected["entry_ts"] = pd.to_datetime(selected["entry_ts"], utc=True)
        selected["exit_ts"] = pd.to_datetime(selected["exit_ts"], utc=True)
    return pd.DataFrame(rows), selected


def loss_filter_candidate_mask(trades_with_context: pd.DataFrame, candidate: str) -> pd.Series:
    if candidate.startswith("timecell_extreme_trend_veto_"):
        threshold = float(candidate.rsplit("_", maxsplit=1)[-1])
        return timecell_trend_veto_mask(trades_with_context, momentum_threshold=threshold)
    if candidate == "timecell_confirmed_trend_veto":
        return timecell_trend_veto_mask(trades_with_context, momentum_threshold=50.0)
    if candidate == "lightglow_counter_ema60_veto":
        lightglow = trades_with_context["strategy_source"].astype(str).eq(LIGHTGLOW_SOURCE)
        long_below = (
            lightglow
            & trades_with_context["direction"].eq(1)
            & (trades_with_context["Close"] < trades_with_context["ema20"])
            & (trades_with_context["ema20"] < trades_with_context["ema60"])
            & (trades_with_context["mom30"] < -25.0)
        )
        short_above = (
            lightglow
            & trades_with_context["direction"].eq(-1)
            & (trades_with_context["Close"] > trades_with_context["ema20"])
            & (trades_with_context["ema20"] > trades_with_context["ema60"])
            & (trades_with_context["mom30"] > 25.0)
        )
        return (long_below | short_above).fillna(False)
    if candidate == "lightglow_extreme_momentum_veto":
        lightglow = trades_with_context["strategy_source"].astype(str).eq(LIGHTGLOW_SOURCE)
        long_flush = lightglow & trades_with_context["direction"].eq(1) & (trades_with_context["mom60"] < -100.0)
        short_squeeze = lightglow & trades_with_context["direction"].eq(-1) & (trades_with_context["mom60"] > 100.0)
        return (long_flush | short_squeeze).fillna(False)
    raise ValueError(f"Unknown loss filter candidate: {candidate}")


def evaluate_loss_filter(base: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
    mask = mask.reindex(base.index).fillna(False).astype(bool)
    removed = base.loc[mask]
    kept = base.loc[~mask]
    base_points = pd.to_numeric(base["net_points"], errors="coerce").fillna(0.0)
    kept_points = pd.to_numeric(kept["net_points"], errors="coerce").fillna(0.0)
    removed_points = pd.to_numeric(removed["net_points"], errors="coerce").fillna(0.0)
    return {
        "base_trades": int(len(base)),
        "kept_trades": int(len(kept)),
        "removed_trades": int(len(removed)),
        "removed_net_points": float(removed_points.sum()),
        "base_net_points": float(base_points.sum()),
        "kept_net_points": float(kept_points.sum()),
        "delta_net_points": float(kept_points.sum() - base_points.sum()),
        "base_profit_factor": profit_factor(base_points),
        "kept_profit_factor": profit_factor(kept_points),
        "kept_worst_trade_points": float(kept_points.min()) if len(kept_points) else 0.0,
    }


def run_loss_learning_walk_forward(
    composite_trades: pd.DataFrame,
    bars: pd.DataFrame,
    *,
    candidates: tuple[str, ...] = (
        "timecell_extreme_trend_veto_50",
        "timecell_extreme_trend_veto_75",
        "timecell_extreme_trend_veto_100",
        "lightglow_counter_ema60_veto",
        "lightglow_extreme_momentum_veto",
    ),
    min_train_removed_trades: int = 10,
) -> pd.DataFrame:
    context = add_prior_trend_context(composite_trades, bars).sort_values(["entry_ts", "exit_ts"]).reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for window in WALK_FORWARD_WINDOWS:
        train = context[context["entry_ts"].dt.year.isin(window.train_years)].copy()
        test = context[context["entry_ts"].dt.year.eq(window.test_year)].copy()
        selected_rows: list[dict[str, Any]] = []
        for candidate in candidates:
            train_mask = loss_filter_candidate_mask(train, candidate)
            train_eval = evaluate_loss_filter(train, train_mask)
            test_mask = loss_filter_candidate_mask(test, candidate)
            test_eval = evaluate_loss_filter(test, test_mask)
            selected = (
                train_eval["removed_trades"] >= min_train_removed_trades
                and train_eval["removed_net_points"] < 0.0
                and train_eval["delta_net_points"] > 0.0
            )
            row = {
                "window": window.label,
                "candidate": candidate,
                "selected_by_train_loss": selected,
                "train_removed_trades": train_eval["removed_trades"],
                "train_removed_net_points": train_eval["removed_net_points"],
                "train_delta_net_points": train_eval["delta_net_points"],
                "train_base_profit_factor": train_eval["base_profit_factor"],
                "train_kept_profit_factor": train_eval["kept_profit_factor"],
                "test_removed_trades": test_eval["removed_trades"],
                "test_removed_net_points": test_eval["removed_net_points"],
                "test_delta_net_points": test_eval["delta_net_points"],
                "test_base_profit_factor": test_eval["base_profit_factor"],
                "test_kept_profit_factor": test_eval["kept_profit_factor"],
                "test_kept_worst_trade_points": test_eval["kept_worst_trade_points"],
            }
            rows.append(row)
            if selected:
                selected_rows.append(row)
        if selected_rows:
            best = max(selected_rows, key=lambda item: (item["train_delta_net_points"], item["train_kept_profit_factor"]))
            rows.append(
                {
                    **best,
                    "candidate": f"SELECTED::{best['candidate']}",
                    "selected_by_train_loss": True,
                    "selection_note": "best_train_loss_filter_applied_to_future_test_year",
                }
            )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["is_positive_oos"] = result["test_delta_net_points"] > 0.0
    selected = result["candidate"].astype(str).str.startswith("SELECTED::")
    if selected.any():
        selected_positive_rate = float(result.loc[selected, "is_positive_oos"].mean())
        total_test_delta = float(result.loc[selected, "test_delta_net_points"].sum())
        verdict = "positive_candidate" if selected_positive_rate >= 0.75 and total_test_delta > 0 else "not_proven"
    else:
        verdict = "not_selected"
    result["loss_learning_verdict"] = verdict
    return result


def reverse_trade_points(trades: pd.DataFrame, *, extra_cost_points: float = ROUND_TRIP_COST_POINTS) -> pd.Series:
    gross = pd.to_numeric(trades["gross_points"], errors="coerce").fillna(0.0)
    return -gross - extra_cost_points


def apply_skip_or_reverse(
    trades_with_context: pd.DataFrame,
    mask: pd.Series,
    *,
    mode: str,
) -> pd.DataFrame:
    mask = mask.reindex(trades_with_context.index).fillna(False).astype(bool)
    frame = trades_with_context.copy()
    if mode == "baseline":
        return frame
    if mode == "skip":
        return frame.loc[~mask].copy()
    if mode == "reverse":
        frame.loc[mask, "direction"] = -frame.loc[mask, "direction"].astype(int)
        frame.loc[mask, "net_points"] = reverse_trade_points(frame.loc[mask])
        frame.loc[mask, "strategy_label"] = frame.loc[mask, "strategy_label"].astype(str) + " reverse_extreme_trend"
        return frame
    raise ValueError(f"Unknown adjustment mode: {mode}")


def run_reverse_trade_diagnostic(
    composite_trades: pd.DataFrame,
    bars: pd.DataFrame,
    *,
    thresholds: tuple[float, ...] = (50.0, 75.0, 100.0, 125.0),
) -> pd.DataFrame:
    context = add_prior_trend_context(composite_trades, bars).sort_values(["entry_ts", "exit_ts"]).reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for window in WALK_FORWARD_WINDOWS:
        train = context[context["entry_ts"].dt.year.isin(window.train_years)].copy()
        test = context[context["entry_ts"].dt.year.eq(window.test_year)].copy()
        selected_rows: list[dict[str, Any]] = []
        for threshold in thresholds:
            candidate = f"timecell_reverse_extreme_trend_{threshold:g}"
            train_mask = timecell_trend_veto_mask(train, momentum_threshold=threshold)
            test_mask = timecell_trend_veto_mask(test, momentum_threshold=threshold)
            train_baseline = full_metric_row(train, label="train_baseline")
            train_skip = full_metric_row(apply_skip_or_reverse(train, train_mask, mode="skip"), label="train_skip")
            train_reverse = full_metric_row(apply_skip_or_reverse(train, train_mask, mode="reverse"), label="train_reverse")
            test_baseline = full_metric_row(test, label="test_baseline")
            test_skip = full_metric_row(apply_skip_or_reverse(test, test_mask, mode="skip"), label="test_skip")
            test_reverse = full_metric_row(apply_skip_or_reverse(test, test_mask, mode="reverse"), label="test_reverse")
            selected = (
                int(train_mask.sum()) >= 5
                and train_reverse["net_points"] > train_baseline["net_points"]
                and train_reverse["net_points"] > train_skip["net_points"]
                and train_reverse["profit_factor"] >= train_baseline["profit_factor"]
            )
            row = {
                "window": window.label,
                "candidate": candidate,
                "selected_by_train_reverse": selected,
                "threshold_points": threshold,
                "train_signal_trades": int(train_mask.sum()),
                "train_baseline_net_points": train_baseline["net_points"],
                "train_skip_net_points": train_skip["net_points"],
                "train_reverse_net_points": train_reverse["net_points"],
                "train_reverse_delta_vs_baseline": train_reverse["net_points"] - train_baseline["net_points"],
                "train_reverse_delta_vs_skip": train_reverse["net_points"] - train_skip["net_points"],
                "train_baseline_profit_factor": train_baseline["profit_factor"],
                "train_reverse_profit_factor": train_reverse["profit_factor"],
                "test_signal_trades": int(test_mask.sum()),
                "test_baseline_net_points": test_baseline["net_points"],
                "test_skip_net_points": test_skip["net_points"],
                "test_reverse_net_points": test_reverse["net_points"],
                "test_reverse_delta_vs_baseline": test_reverse["net_points"] - test_baseline["net_points"],
                "test_reverse_delta_vs_skip": test_reverse["net_points"] - test_skip["net_points"],
                "test_baseline_profit_factor": test_baseline["profit_factor"],
                "test_reverse_profit_factor": test_reverse["profit_factor"],
                "test_reverse_worst_trade_points": test_reverse["worst_trade_points"],
            }
            rows.append(row)
            if selected:
                selected_rows.append(row)
        if selected_rows:
            best = max(
                selected_rows,
                key=lambda item: (item["train_reverse_delta_vs_baseline"], item["train_reverse_profit_factor"]),
            )
            rows.append(
                {
                    **best,
                    "candidate": f"SELECTED::{best['candidate']}",
                    "selection_note": "reverse_rule_selected_on_train_only_and_applied_to_future_test_year",
                }
            )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    selected = result["candidate"].astype(str).str.startswith("SELECTED::")
    if selected.any():
        positive_rate = float((result.loc[selected, "test_reverse_delta_vs_baseline"] > 0.0).mean())
        total_delta = float(result.loc[selected, "test_reverse_delta_vs_baseline"].sum())
        verdict = "reverse_positive_candidate" if positive_rate >= 0.75 and total_delta > 0 else "reverse_not_proven"
    else:
        verdict = "reverse_not_selected"
    result["reverse_trade_verdict"] = verdict
    result["is_reverse_positive_oos"] = result["test_reverse_delta_vs_baseline"] > 0.0
    return result


def hash_frame(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "empty"
    data = frame[columns].copy()
    for column in columns:
        if pd.api.types.is_datetime64_any_dtype(data[column]):
            data[column] = pd.to_datetime(data[column], utc=True).astype("int64")
    hashed = pd.util.hash_pandas_object(data, index=True).values.tobytes()
    return hashlib.sha256(hashed).hexdigest()


def perturbation_trade_signature(signals: pd.DataFrame, *, cutoff_index: int) -> pd.DataFrame:
    frame = signals.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    if "trade_date" not in frame.columns:
        frame["trade_date"] = frame["ts"].dt.date
    if "minute_of_day" not in frame.columns:
        frame["minute_of_day"] = frame["ts"].dt.hour * 60 + frame["ts"].dt.minute
    if "timeframe_minutes" not in frame.columns:
        frame["timeframe_minutes"] = 1
    candidate = LightglowCandidate(
        signal="premium_discount_reversal",
        timeframe_minutes=1,
        session="all",
        hold_bars=10,
        direction_mode="reverse",
        stop_loss_points=None,
        take_profit_points=None,
    )
    trades = build_trades(frame, candidate, BacktestCosts())
    if trades.empty:
        return pd.DataFrame(
            columns=[
                "entry_index",
                "exit_index",
                "entry_ts",
                "exit_ts",
                "direction",
                "entry_price",
                "exit_price",
                "gross_points",
                "net_points",
            ]
        )
    pre_cutoff = trades[pd.to_numeric(trades["exit_index"], errors="coerce") <= cutoff_index].copy()
    columns = [
        "entry_index",
        "exit_index",
        "entry_ts",
        "exit_ts",
        "direction",
        "entry_price",
        "exit_price",
        "gross_points",
        "net_points",
    ]
    return pre_cutoff[columns].reset_index(drop=True)


def static_leakage_scan(files: list[str] | None = None) -> pd.DataFrame:
    patterns = {
        "negative_shift": re.compile(r"\.shift\s*\(\s*-\d+"),
        "centered_rolling": re.compile(r"rolling\s*\([^)]*center\s*=\s*True"),
        "future_window_name": re.compile(r"future_window|future_|lookahead|leak", re.IGNORECASE),
        "same_bar_exit_literal": re.compile(r"same_bar_exit"),
    }
    rows: list[dict[str, Any]] = []
    for relative in files or STATIC_SCAN_FILES:
        path = ROOT_DIR / relative
        if not path.exists():
            rows.append({"file": relative, "line": 0, "pattern": "missing_file", "severity": "warn", "snippet": ""})
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for name, pattern in patterns.items():
                if pattern.search(line):
                    severity = "fail" if name in {"negative_shift", "centered_rolling"} else "review"
                    rows.append(
                        {
                            "file": relative,
                            "line": line_number,
                            "pattern": name,
                            "severity": severity,
                            "snippet": line.strip()[:180],
                        }
                    )
    return pd.DataFrame(rows)


def runtime_future_perturbation_audit(
    bars: pd.DataFrame,
    *,
    cutoff_index: int = 1200,
    sample_rows: int = 2600,
) -> dict[str, Any]:
    subset = bars.head(sample_rows).copy().reset_index(drop=True)
    if len(subset) < 20:
        return {
            "audit": "future_ohlcv_perturbation",
            "cutoff_index": int(max(0, len(subset) - 1)),
            "sample_rows": int(len(subset)),
            "passed": False,
            "severity": "fail",
            "reason": "insufficient_bars",
        }
    max_cutoff = max(5, len(subset) - 5)
    cutoff_index = min(max(5, cutoff_index), max_cutoff)
    baseline = build_lightglow_signals(subset)
    perturbed = subset.copy()
    future_mask = perturbed.index > cutoff_index
    for column, delta in {"Open": 17.25, "High": 31.0, "Low": -29.0, "Close": -11.5}.items():
        perturbed.loc[future_mask, column] = perturbed.loc[future_mask, column].astype(float) + delta
    perturbed.loc[future_mask, "Volume"] = perturbed.loc[future_mask, "Volume"].astype(float) * 3.0 + 7.0
    changed = build_lightglow_signals(perturbed)
    signal_columns = [
        "internal_bos",
        "internal_choch",
        "swing_bos",
        "swing_choch",
        "fvg",
        "equal_level_reversal",
        "internal_ob_break",
        "swing_ob_break",
        "premium_discount_reversal",
        "internal_choch_zone",
        "fvg_zone",
    ]
    feature_columns = ["Open", "High", "Low", "Close", "Volume"]
    baseline_feature_hash = hash_frame(baseline.iloc[: cutoff_index + 1], ["ts", *feature_columns])
    changed_feature_hash = hash_frame(changed.iloc[: cutoff_index + 1], ["ts", *feature_columns])
    baseline_signal_hash = hash_frame(baseline.iloc[: cutoff_index + 1], ["ts", *signal_columns])
    changed_signal_hash = hash_frame(changed.iloc[: cutoff_index + 1], ["ts", *signal_columns])
    baseline_trades = perturbation_trade_signature(baseline, cutoff_index=cutoff_index)
    changed_trades = perturbation_trade_signature(changed, cutoff_index=cutoff_index)
    trade_columns = list(baseline_trades.columns)
    baseline_trade_hash = hash_frame(baseline_trades, trade_columns)
    changed_trade_hash = hash_frame(changed_trades, trade_columns)
    passed = (
        baseline_feature_hash == changed_feature_hash
        and baseline_signal_hash == changed_signal_hash
        and baseline_trade_hash == changed_trade_hash
    )
    return {
        "audit": "future_ohlcv_perturbation",
        "cutoff_ts": str(subset.loc[cutoff_index, "ts"]),
        "cutoff_index": int(cutoff_index),
        "sample_rows": int(len(subset)),
        "features_checked": ",".join(feature_columns),
        "columns_checked": ",".join(signal_columns),
        "trades_checked": int(len(baseline_trades)),
        "baseline_feature_hash": baseline_feature_hash,
        "perturbed_feature_hash": changed_feature_hash,
        "baseline_signal_hash": baseline_signal_hash,
        "perturbed_signal_hash": changed_signal_hash,
        "baseline_trade_hash": baseline_trade_hash,
        "perturbed_trade_hash": changed_trade_hash,
        "passed": passed,
        "severity": "pass" if passed else "fail",
    }


def same_bar_audit(trades: pd.DataFrame) -> dict[str, Any]:
    same_bar = trades["entry_ts"].eq(trades["exit_ts"])
    if "same_bar_exit" in trades.columns:
        same_bar = same_bar | trades["same_bar_exit"].fillna(False).astype(bool)
    return {
        "audit": "same_bar_exit",
        "trades": int(len(trades)),
        "same_bar_trades": int(same_bar.sum()),
        "same_bar_rate": float(same_bar.mean()) if len(trades) else 0.0,
        "passed": bool(same_bar.sum() == 0),
        "severity": "pass" if int(same_bar.sum()) == 0 else "fail",
    }


def executable_entry_audit(trades: pd.DataFrame) -> dict[str, Any]:
    signal_ts = pd.to_datetime(trades.get("signal_ts", trades["entry_ts"]), utc=True, errors="coerce")
    entry_ts = pd.to_datetime(trades["entry_ts"], utc=True, errors="coerce")
    violations = int((entry_ts < signal_ts).sum())
    return {
        "audit": "entry_after_signal",
        "trades": int(len(trades)),
        "violations": violations,
        "passed": violations == 0,
        "severity": "pass" if violations == 0 else "fail",
    }


def leakage_audit_table(composite_trades: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    runtime = runtime_future_perturbation_audit(bars)
    same_bar = same_bar_audit(composite_trades)
    entry = executable_entry_audit(composite_trades)
    static = static_leakage_scan()
    rows = [runtime, same_bar, entry]
    if not static.empty:
        fail_count = int(static["severity"].eq("fail").sum())
        review_count = int(static["severity"].eq("review").sum())
        rows.append(
            {
                "audit": "static_code_scan",
                "fail_hits": fail_count,
                "review_hits": review_count,
                "passed": fail_count == 0,
                "severity": "pass" if fail_count == 0 else "fail",
            }
        )
    return pd.DataFrame(rows)


def paper_interface_readiness_table() -> pd.DataFrame:
    run_script = ROOT_DIR / "scripts" / "run_ibkr_live_paper_trader.py"
    live_strategy = ROOT_DIR / "tradingagents" / "execution" / "live_strategy.py"
    run_text = run_script.read_text(encoding="utf-8") if run_script.exists() else ""
    strategy_text = live_strategy.read_text(encoding="utf-8") if live_strategy.exists() else ""
    supports_lightglow = "lightglow" in run_text.lower() or "lightglow" in strategy_text.lower()
    supports_timecell = "timecell" in run_text.lower() or "timecell" in strategy_text.lower()
    supports_regime = "regime_transition" in run_text and "regime_transition_spec" in strategy_text
    return pd.DataFrame(
        [
            {
                "adapter": "Lightglow action-map signal",
                "status": "ready" if supports_lightglow else "missing",
                "evidence": "live_strategy/run_ibkr supports lightglow" if supports_lightglow else "no Lightglow strategy family or adapter found",
                "paper_action": "blocked until adapter emits live signals and bracket exits",
            },
            {
                "adapter": "Rollstable timecell signal",
                "status": "ready" if supports_timecell else "missing",
                "evidence": "live_strategy/run_ibkr supports timecell" if supports_timecell else "no Timecell strategy family or adapter found",
                "paper_action": "shadow-record only until executable integer-contract rule is defined",
            },
            {
                "adapter": "Existing regime-transition path",
                "status": "ready" if supports_regime else "missing",
                "evidence": "regime_transition parser/spec present" if supports_regime else "regime_transition path not detected",
                "paper_action": "not sufficient for Lightglow + Timecell combo by itself",
            },
        ]
    )


def price_at_or_after(bars: pd.DataFrame, timestamps: pd.Series, column: str) -> pd.Series:
    positions = np.searchsorted(bars["ts"].to_numpy(), pd.to_datetime(timestamps, utc=True).to_numpy(), side="left")
    valid = positions < len(bars)
    values = np.full(len(timestamps), np.nan, dtype=float)
    if valid.any():
        values[valid] = bars[column].to_numpy(dtype=float)[positions[valid]]
    return pd.Series(values, index=timestamps.index)


def latency_stress_table(trades: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for delay in (0, 1, 2, 3):
        if delay == 0:
            model = trades.copy()
        else:
            model = trades.copy()
            delayed_ts = model["entry_ts"] + pd.to_timedelta(delay, unit="min")
            delayed_entry = price_at_or_after(bars, delayed_ts, "Open")
            executable = delayed_ts < model["exit_ts"]
            direction = model["direction"].astype(int)
            model = model.loc[executable].copy()
            delayed_entry = delayed_entry.loc[model.index]
            model["gross_points"] = (model["exit_price"].astype(float) - delayed_entry.astype(float)) * direction.loc[model.index]
            model["net_points"] = model["gross_points"] - ROUND_TRIP_COST_POINTS
        row = full_metric_row(model, label=f"delay_{delay}_bar")
        row["stress_type"] = "latency"
        row["parameter"] = f"{delay}_bar"
        rows.append(row)
    return pd.DataFrame(rows)


def slippage_stress_table(trades: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    range_atr = (
        pd.to_numeric(trades["range_atr"], errors="coerce").fillna(1.0)
        if "range_atr" in trades.columns
        else pd.Series(1.0, index=trades.index)
    )
    models: dict[str, pd.Series] = {
        "fixed_0.5": pd.Series(0.5, index=trades.index),
        "fixed_1.5": pd.Series(1.5, index=trades.index),
        "atr_range_15pct": range_atr.clip(0.25, 12.0) * 0.15,
        "session_open_rth_eth": session_slippage(trades),
    }
    for name, extra_cost in models.items():
        model = trades.copy()
        model["net_points"] = model["net_points"] - extra_cost
        row = full_metric_row(model, label=name)
        row["stress_type"] = "slippage"
        row["parameter"] = name
        rows.append(row)
    return pd.DataFrame(rows)


def extra_cost_stress_table(trades: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for extra in (0.5, 1.5, 2.5, 4.375):
        model = trades.copy()
        model["net_points"] = model["net_points"] - extra
        row = full_metric_row(model, label=f"extra_cost_{extra:g}")
        row["stress_type"] = "extra_cost"
        row["parameter"] = f"+{extra:g}_points"
        rows.append(row)
    return pd.DataFrame(rows)


def session_slippage(trades: pd.DataFrame) -> pd.Series:
    minutes = trades["entry_ts"].dt.hour * 60 + trades["entry_ts"].dt.minute
    open_mask = (minutes >= 13 * 60 + 30) & (minutes < 14 * 60 + 30)
    rth_mask = (minutes >= 13 * 60 + 30) & (minutes < 20 * 60)
    values = pd.Series(1.25, index=trades.index, dtype=float)
    values.loc[rth_mask] = 0.75
    values.loc[open_mask] = 1.5
    return values


def stress_tables(trades: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    return pd.concat(
        [
            extra_cost_stress_table(trades),
            latency_stress_table(trades, bars),
            slippage_stress_table(trades),
        ],
        ignore_index=True,
        sort=False,
    )


def risk_budget_mapping() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "component": "Lightglow",
                "risk_weight": 1.0,
                "nq_equivalent": 1.0,
                "mnq_equivalent": 10.0,
                "paper_action": "trade MNQ only during validation; start with 1 MNQ, not 1 NQ",
                "reason": "main edge, but still research-only until paper outcomes exist",
                "executable": True,
            },
            {
                "component": "Timecell",
                "risk_weight": 0.05,
                "nq_equivalent": 0.05,
                "mnq_equivalent": 0.5,
                "paper_action": "shadow-record only, or batch into 1 MNQ after independent approval",
                "reason": "0.05 NQ is below one MNQ contract; PF is thin and should not be equally scaled",
                "executable": False,
            },
        ]
    )


def paper_validation_plan() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "phase": "dry_run_signal",
                "duration": "5 trading days",
                "minimum_samples": 50,
                "pass_gate": "no stale signals, no same-bar exits, no unsupported adapter path",
                "log_fields": "strategy_id, signal_ts, confirmed_ts, side, planned_entry, adapter_status, reject_reason",
                "exception_handling": "block order emission on stale, unsupported, or same-bar signals; page operator",
                "failure_action": "blocked until signal adapter is fixed",
            },
            {
                "phase": "shadow_timecell",
                "duration": "4 weeks",
                "minimum_samples": 200,
                "pass_gate": "timecell remains positive on shadow basis and does not increase drawdown tail",
                "log_fields": "signal_ts, cell_key, side, hypothetical_entry, hypothetical_exit, net_points, veto_reason",
                "exception_handling": "record only; never place orders while 0.05 NQ cannot map to integer contracts",
                "failure_action": "keep timecell out of executable portfolio",
            },
            {
                "phase": "mnq_lightglow_paper",
                "duration": "4-8 weeks",
                "minimum_samples": 300,
                "pass_gate": "net points > 0, PF >= 1.20, max consecutive losses <= 4, no daily risk breach",
                "log_fields": "signal_ts, order_id, fill_ts, fill_price, slippage_points, exit_reason, pnl_points, risk_state",
                "exception_handling": "halt on daily loss, reject burst, data gap, abnormal spread/volatility, or drawdown trigger",
                "failure_action": "research-only; retrain is not allowed until new evaluation split is defined",
            },
        ]
    )


def paper_readiness(composite_trades: pd.DataFrame, leakage: pd.DataFrame, stress: pd.DataFrame) -> dict[str, Any]:
    blockers = []
    if leakage["severity"].eq("fail").any():
        blockers.append("leakage_audit_failed")
    if not same_bar_audit(composite_trades)["passed"]:
        blockers.append("same_bar_exit_present")
    blockers.append("missing_live_adapter_for_lightglow_and_timecell")
    blockers.append("timecell_0.05_weight_not_executable_as_integer_futures_contract")
    blockers.append("no_forward_paper_outcomes_for_this_strategy_id")
    if float(stress.loc[stress["parameter"].eq("+4.375_points"), "net_points"].min()) < 0:
        blockers.append("extreme_cost_stress_has_negative_tail")
    interface = paper_interface_readiness_table()
    if interface["status"].astype(str).eq("missing").any():
        blockers.append("paper_adapter_readiness_missing")
    status = "blocked" if blockers else "paper-ready"
    return {
        "status": status,
        "research_tier": "research-only" if blockers else "paper-ready",
        "blockers": blockers,
        "next_action": "implement adapter and run paper validation" if blockers else "start guarded MNQ paper validation",
    }


def best_worst_charts(trades: pd.DataFrame, bars: pd.DataFrame) -> str:
    if trades.empty:
        return '<p class="empty">No trade samples.</p>'
    best = trades.loc[trades["net_points"].idxmax()]
    worst = trades.loc[trades["net_points"].idxmin()]
    return "".join(
        [
            trade_panel("原始冻结组合最佳交易 K线", best, bars),
            trade_panel("原始冻结组合最差交易 K线（审计样本）", worst, bars),
        ]
    )


def paper_executable_trades(trades: pd.DataFrame) -> pd.DataFrame:
    """Trades that the current paper plan can plausibly validate with integer contracts."""
    if trades.empty or "strategy_source" not in trades.columns:
        return trades.iloc[0:0].copy()
    executable = trades[trades["strategy_source"].astype(str).eq(LIGHTGLOW_SOURCE)].copy()
    executable["risk_weight"] = executable.get("risk_weight", 1.0)
    return executable


def executable_best_worst_charts(trades: pd.DataFrame, bars: pd.DataFrame) -> str:
    executable = paper_executable_trades(trades)
    if executable.empty:
        return '<p class="empty">No paper-executable trade samples after excluding shadow-only components.</p>'
    best = executable.loc[executable["net_points"].idxmax()]
    worst = executable.loc[executable["net_points"].idxmin()]
    return "".join(
        [
            trade_panel("纸盘可执行 Lightglow 最佳交易 K线", best, bars, note="Timecell is excluded here because it is shadow-only at 0.05x."),
            trade_panel("纸盘可执行 Lightglow 最差交易 K线", worst, bars, note="This is the worst currently executable paper-validation sample, not the raw composite tail."),
        ]
    )


def trade_panel(title: str, trade: pd.Series, bars: pd.DataFrame, note: str = "") -> str:
    entry_ts = pd.to_datetime(trade["entry_ts"], utc=True)
    exit_ts = pd.to_datetime(trade["exit_ts"], utc=True)
    start_pos = max(0, int(bars["ts"].searchsorted(entry_ts, side="left")) - 80)
    end_pos = min(len(bars), int(bars["ts"].searchsorted(exit_ts, side="left")) + 120)
    window = bars.iloc[start_pos:end_pos].reset_index(drop=True)
    meta = (
        f"{trade.get('strategy_source', '')} | {entry_ts} -> {exit_ts} | "
        f"net {fmt_signed(trade.get('net_points'))} pts"
    )
    return f"""
    <figure class="chart">
      <figcaption>{esc(title)}</figcaption>
      <p class="muted">{esc(meta)}</p>
      {f'<p class="muted">{esc(note)}</p>' if note else ''}
      {candlestick_svg(window, trade)}
    </figure>
    """


def write_markdown(path: Path, readiness: dict[str, Any], summary: dict[str, Any]) -> None:
    blockers = "\n".join(f"- `{blocker}`" for blocker in readiness["blockers"]) or "- none"
    text = f"""# NQ Lightglow + Timecell Paper-Readiness Audit

Status: `{readiness['status']}`

This report does not approve live trading. It audits whether the research combo can enter guarded paper validation.

## Strategy Principle And Market Features

- Lightglow uses Premium/Discount location, swing zones, EMA context, volume-price pressure, and range position; action maps are selected only from train windows.
- Timecell uses a 2010-2019 trained month/hour directional map at `0.05` risk weight; current conclusion keeps it shadow-only because the contract granularity is not executable.
- Extreme Timecell long-against-downtrend cases can be detected, but reverse-short validation is `reverse_not_proven`; use it as avoid-long risk control only.

## Frozen Configuration

- Walk-forward windows: `2020-2021 -> 2022`, `2020-2022 -> 2023`, `2021-2023 -> 2024`, `2022-2024 -> 2025`.
- Lightglow paper action: MNQ validation only, starting smaller than one NQ.
- Timecell paper action: shadow-record unless a separate integer-contract rule is approved.

## Headline

- Raw trades: `{int(summary['raw_summary']['trades']):,}`
- Raw net points: `{summary['raw_summary']['net_points']:.2f}`
- Raw PF: `{summary['raw_summary']['profit_factor']:.3f}`
- Risk-budgeted net points: `{summary['budgeted_summary']['net_points']:.2f}`
- Risk-budgeted PF: `{summary['budgeted_summary']['profit_factor']:.3f}`
- Leakage passed: `{summary.get('leakage_passed', False)}`
- Walk-forward rows: `{summary.get('walk_forward_rows', 0)}`

## Leakage, Walk-Forward, And Stress

- Future perturbation audit hashes pre-cutoff OHLCV features, Lightglow signal columns, and executable trade signatures.
- Same-bar exits and entry-before-signal violations are checked in the leakage table.
- Stress coverage includes extra cost, 1/2/3 bar latency, fixed slippage, ATR/range slippage, and session-specific slippage.

## Risk Budget And Paper Validation

- Risk budget prevents weak-edge coverage from being scaled equally with the main Lightglow component.
- The paper validation plan logs signal timestamps, order/fill fields, slippage, exit reason, PnL, risk state, reject reasons, and exception halts.
- Current status is blocked until live/paper adapters can express Lightglow and Timecell signals, exits, position sizing, and risk controls.

## Blockers

{blockers}

## Next Action

{readiness['next_action']}

## Loss Learning

- Verdict: `{summary.get('loss_learning_verdict', 'not_run')}`
- Selected OOS delta points: `{summary.get('loss_learning_selected_oos_delta_points', 0.0):.2f}`

## Reverse Diagnostic

- Verdict: `{summary.get('reverse_trade_verdict', 'not_run')}`
- Selected OOS delta vs baseline: `{summary.get('reverse_selected_oos_delta_points', 0.0):.2f}`
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_html_report(
    *,
    composite_trades: pd.DataFrame,
    walk_forward: pd.DataFrame,
    leakage: pd.DataFrame,
    stress: pd.DataFrame,
    loss_learning: pd.DataFrame,
    reverse_diagnostic: pd.DataFrame,
    bars: pd.DataFrame,
    readiness: dict[str, Any],
    risk_mapping: pd.DataFrame,
    paper_plan: pd.DataFrame,
    paper_interface: pd.DataFrame,
    generated_at: str,
) -> tuple[str, dict[str, Any]]:
    raw_summary = summarize_trades(composite_trades)
    budgeted_summary = summarize_trades(composite_trades, risk_budgeted=True)
    annual = annual_summary(composite_trades)
    monthly = monthly_summary(composite_trades)
    source = source_summary(composite_trades)
    selected_loss_learning = (
        loss_learning[loss_learning["candidate"].astype(str).str.startswith("SELECTED::")].copy()
        if not loss_learning.empty
        else pd.DataFrame()
    )
    selected_reverse = (
        reverse_diagnostic[reverse_diagnostic["candidate"].astype(str).str.startswith("SELECTED::")].copy()
        if not reverse_diagnostic.empty
        else pd.DataFrame()
    )
    cards = "".join(
        [
            metric("结论", readiness["status"], readiness["research_tier"]),
            metric("原始净点", fmt_signed(raw_summary["net_points"]), f"PF {fmt_num(raw_summary['profit_factor'], 3)}"),
            metric("预算净点", fmt_signed(budgeted_summary["net_points"]), f"PF {fmt_num(budgeted_summary['profit_factor'], 3)}"),
            metric("WF 窗口", f"{len(walk_forward):,}", "rolling train->test"),
            metric("泄漏审计", "PASS" if not leakage["severity"].eq("fail").any() else "FAIL", "static + runtime"),
            metric("Blockers", f"{len(readiness['blockers'])}", readiness["next_action"]),
        ]
    )
    blocker_items = "".join(f"<li><code>{esc(blocker)}</code></li>" for blocker in readiness["blockers"])
    css = """
    :root { --ink:#17212b; --muted:#5f6f7d; --line:#d8e0e8; --bg:#f5f7fb; --panel:#fff; --blue:#2563eb; --red:#b34242; --amber:#a66f00; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    header { padding:34px min(5vw,58px) 26px; background:#111827; color:#f8fafc; }
    main { max-width:1280px; margin:0 auto; padding:26px min(5vw,58px) 60px; }
    h1 { margin:0 0 10px; font-size:34px; letter-spacing:0; }
    h2 { margin:0 0 12px; font-size:23px; letter-spacing:0; }
    h3 { margin:18px 0 8px; font-size:16px; letter-spacing:0; }
    p { margin:0 0 10px; }
    code { padding:2px 5px; border-radius:5px; background:#eef2f7; color:#132033; }
    header code { background:#263244; color:#e7edf6; }
    section { margin:18px 0; padding:22px; border:1px solid var(--line); border-radius:8px; background:var(--panel); }
    .subtitle { max-width:1080px; color:#c8d2df; font-size:16px; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }
    .metric { padding:14px; border:1px solid #2f3d4f; border-radius:8px; background:#1e293b; }
    .metric small { display:block; color:#b8c3d2; font-size:12px; }
    .metric strong { display:block; margin-top:5px; color:#fff; font-size:23px; }
    .metric span { color:#b8c3d2; font-size:12px; }
    .note { margin:12px 0; padding:14px 16px; border-left:4px solid var(--blue); border-radius:6px; background:#eef5ff; }
    .risk { border-left-color:var(--red); background:#fff0f0; }
    .warn { border-left-color:var(--amber); background:#fff7e8; }
    .table-wrap { margin:12px 0; overflow-x:auto; border:1px solid var(--line); border-radius:8px; }
    table { width:100%; border-collapse:collapse; font-size:12px; background:#fff; }
    th, td { padding:8px 10px; border-bottom:1px solid #e7edf4; text-align:left; vertical-align:top; }
    th { background:#edf2f7; color:#475569; }
    td.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
    .chart { margin:14px 0; padding:14px; border:1px solid var(--line); border-radius:8px; background:#fff; overflow-x:auto; }
    figcaption { margin:0 0 8px; font-weight:700; }
    svg { width:100%; height:auto; display:block; }
    .muted, .empty { color:var(--muted); }
    """
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ Lightglow + Timecell Paper-Readiness Audit</title>
  <style>{css}</style>
</head>
<body>
  <header>
    <h1>NQ Lightglow + Timecell Paper-Readiness Audit</h1>
    <p class="subtitle">目标是判断研究组合能否进入自动纸盘验证，不是批准实盘。报告冻结当前 Lightglow + Timecell 定义，执行无未来审计、滚动 walk-forward、成本/延迟/滑点压力、风险预算仓位映射和 paper adapter 检查。生成时间：{esc(generated_at)}。</p>
    <div class="grid">{cards}</div>
  </header>
  <main>
    <section>
      <h2>纸盘准备度结论</h2>
      <div class="note risk">
        <p><strong>结论：</strong><code>{esc(readiness['status'])}</code>。当前组合仍属于 <code>{esc(readiness['research_tier'])}</code>，不能视为实盘策略。</p>
        <p><strong>Blockers:</strong></p>
        <ul>{blocker_items}</ul>
      </div>
    </section>
    <section>
      <h2>冻结配置、策略原理与行情特征</h2>
      <div class="note">
        <p><strong>Lightglow:</strong> 使用 Premium/Discount、swing zone、趋势/均值偏离、量价与箱体位置。每个 walk-forward 窗口只用训练期 month x weekday 单元选择 native/reverse/skip，测试年不参与训练。</p>
        <p><strong>Timecell:</strong> 使用已存在 2010-2019 训练的 roll-stable month/hour direction map，只以 <code>risk_weight=0.05</code> 作为覆盖信号纳入预算口径。</p>
        <p><strong>冲突与风控:</strong> 纸盘阶段 Lightglow 只允许 1 MNQ 试运行，Timecell 先 shadow-record；重叠信号不叠仓，每日亏损、连续亏损、异常波动均应触发暂停。</p>
      </div>
    </section>
    <section>
      <h2>泄漏审计</h2>
      {html_table(leakage, [("audit", "审计"), ("severity", "结果"), ("passed", "通过"), ("cutoff_ts", "cutoff"), ("features_checked", "特征列"), ("columns_checked", "信号列"), ("trades_checked", "交易签名数"), ("same_bar_trades", "同K数"), ("violations", "违规数"), ("fail_hits", "静态失败"), ("review_hits", "需复核")])}
    </section>
    <section>
      <h2>滚动 Walk-Forward</h2>
      {html_table(walk_forward, [("window", "窗口"), ("action_cells", "动作单元"), ("lightglow_trades", "Lightglow"), ("timecell_trades", "Timecell"), ("raw_trades", "总交易"), ("raw_net_points", "原始净点"), ("raw_profit_factor", "PF"), ("raw_win_rate", "胜率"), ("raw_max_drawdown_points", "最大DD"), ("raw_worst_month_points", "最差月"), ("raw_worst_90d_points", "最差90日"), ("budgeted_net_points", "预算净点"), ("budgeted_profit_factor", "预算PF"), ("lightglow_extra_4.375_net_points", "+4.375成本净点")])}
    </section>
    <section>
      <h2>亏损交易学习</h2>
      <div class="note warn">
        <p><strong>方法：</strong>候选过滤器只从训练期亏损交易中选择，然后固定应用到未来测试年；测试年结果不参与规则选择。</p>
        <p><strong>判定：</strong><code>{esc(summary_loss_learning_verdict(loss_learning))}</code>。如果 SELECTED 行的未来测试年净点提升不稳定，只能说明它是尾部风险诊断，不能作为正向优化规则。</p>
      </div>
      <h3>训练选择后应用到未来年份</h3>
      {html_table(selected_loss_learning, [("window", "窗口"), ("candidate", "训练选中规则"), ("train_removed_trades", "训练过滤"), ("train_removed_net_points", "训练过滤净点"), ("train_delta_net_points", "训练提升"), ("test_removed_trades", "测试过滤"), ("test_removed_net_points", "测试过滤净点"), ("test_delta_net_points", "测试提升"), ("test_base_profit_factor", "测试原PF"), ("test_kept_profit_factor", "测试保留PF"), ("test_kept_worst_trade_points", "测试最差单笔"), ("is_positive_oos", "OOS正向")])}
      <h3>全部候选扫描</h3>
      {html_table(loss_learning, [("window", "窗口"), ("candidate", "候选"), ("selected_by_train_loss", "训练选中"), ("train_removed_trades", "训练过滤"), ("train_delta_net_points", "训练提升"), ("test_removed_trades", "测试过滤"), ("test_delta_net_points", "测试提升"), ("is_positive_oos", "OOS正向")], limit=80)}
    </section>
    <section>
      <h2>反手做空诊断</h2>
      <div class="note warn">
        <p><strong>问题：</strong>最差交易是在急跌趋势里做多。系统可以识别这种“统计时段信号逆强趋势”结构，但是否应该反手做空必须单独验证。</p>
        <p><strong>方法：</strong>对同一批极端逆趋势 timecell 信号分别测试 baseline、skip、reverse。reverse 使用原交易入场/出场价格反向计算，并额外扣一轮交易成本；规则只允许训练期选择，未来测试年只验证。</p>
        <p><strong>判定：</strong><code>{esc(summary_reverse_trade_verdict(reverse_diagnostic))}</code>。只有 SELECTED 行在未来测试年稳定优于 baseline 和 skip，才能把“避免做多”升级为“主动做空”。</p>
      </div>
      <h3>训练选中的反手规则</h3>
      {html_table(selected_reverse, [("window", "窗口"), ("candidate", "训练选中规则"), ("train_signal_trades", "训练信号数"), ("train_reverse_delta_vs_baseline", "训练反手vs原始"), ("train_reverse_delta_vs_skip", "训练反手vs跳过"), ("test_signal_trades", "测试信号数"), ("test_reverse_delta_vs_baseline", "测试反手vs原始"), ("test_reverse_delta_vs_skip", "测试反手vs跳过"), ("test_reverse_profit_factor", "测试反手PF"), ("test_reverse_worst_trade_points", "测试最差单笔"), ("is_reverse_positive_oos", "OOS正向")])}
      <h3>全部反手候选扫描</h3>
      {html_table(reverse_diagnostic, [("window", "窗口"), ("candidate", "候选"), ("selected_by_train_reverse", "训练选中"), ("threshold_points", "阈值"), ("train_signal_trades", "训练信号数"), ("train_reverse_delta_vs_baseline", "训练反手vs原始"), ("train_reverse_delta_vs_skip", "训练反手vs跳过"), ("test_signal_trades", "测试信号数"), ("test_reverse_delta_vs_baseline", "测试反手vs原始"), ("test_reverse_delta_vs_skip", "测试反手vs跳过"), ("is_reverse_positive_oos", "OOS正向")], limit=80)}
    </section>
    <section>
      <h2>成本/延迟/滑点压力</h2>
      {html_table(stress, [("stress_type", "类型"), ("parameter", "参数"), ("trades", "交易数"), ("net_points", "净点"), ("profit_factor", "PF"), ("win_rate", "胜率"), ("max_drawdown_points", "最大DD"), ("worst_month_points", "最差月"), ("worst_90d_points", "最差90日"), ("positive_90d_rate", "正90日率")])}
    </section>
    <section>
      <h2>纸盘接口检查</h2>
      {html_table(paper_interface, [("adapter", "接口"), ("status", "状态"), ("evidence", "证据"), ("paper_action", "处理")])}
    </section>
    <section>
      <h2>风险预算与真实仓位映射</h2>
      {html_table(risk_mapping, [("component", "组件"), ("risk_weight", "风险权重"), ("nq_equivalent", "NQ等价"), ("mnq_equivalent", "MNQ等价"), ("executable", "可执行"), ("paper_action", "纸盘动作"), ("reason", "原因")])}
    </section>
    <section>
      <h2>年度/月度/来源表现</h2>
      <h3>年度</h3>
      {html_table(annual, [("year", "年份"), ("trades", "交易数"), ("net_points", "净点"), ("budgeted_net_points", "预算净点"), ("win_rate", "胜率")])}
      <h3>最近月份</h3>
      {html_table(monthly, [("month", "月份"), ("trades", "交易数"), ("net_points", "净点")])}
      <h3>来源</h3>
      {html_table(source, [("strategy_source", "来源"), ("strategy_label", "策略"), ("trades", "交易数"), ("net_points", "净点"), ("budgeted_net_points", "预算净点"), ("profit_factor", "PF"), ("risk_weight", "风险权重")])}
    </section>
    <section>
      <h2>资金曲线与 K线样本</h2>
      {line_svg(pd.DataFrame({"x": range(1, len(composite_trades) + 1), "equity": composite_trades["net_points"].cumsum()}), title="组合原始净点曲线")}
      <div class="note risk">
        <p><strong>为什么原始最差交易仍然显示：</strong>这张图保留冻结组合的真实尾部风险，用于审计，而不是表示已经批准这类 Timecell 逆趋势长单进入纸盘执行。</p>
        <p><strong>纸盘执行口径：</strong>当前计划只允许 Lightglow 用 MNQ 小仓位验证；Timecell 因 <code>0.05x</code> 无法映射为整数合约且反手做空未被 OOS 证明，只能 shadow-record。下面单独展示纸盘可执行 Lightglow 样本。</p>
      </div>
      <h3>冻结原始组合审计样本</h3>
      {best_worst_charts(composite_trades, bars)}
      <h3>纸盘可执行 Lightglow 样本</h3>
      {executable_best_worst_charts(composite_trades, bars)}
    </section>
    <section>
      <h2>纸盘验证计划</h2>
      {html_table(paper_plan, [("phase", "阶段"), ("duration", "周期"), ("minimum_samples", "最低样本"), ("pass_gate", "通过门槛"), ("log_fields", "日志字段"), ("exception_handling", "异常处理"), ("failure_action", "失败处理")])}
    </section>
  </main>
</body>
</html>
"""
    summary = {
        "readiness": readiness,
        "raw_summary": raw_summary,
        "budgeted_summary": budgeted_summary,
        "walk_forward_rows": int(len(walk_forward)),
        "leakage_passed": bool(not leakage["severity"].eq("fail").any()),
        "loss_learning_verdict": summary_loss_learning_verdict(loss_learning),
        "loss_learning_selected_oos_delta_points": selected_loss_learning_delta(loss_learning),
        "reverse_trade_verdict": summary_reverse_trade_verdict(reverse_diagnostic),
        "reverse_selected_oos_delta_points": selected_reverse_trade_delta(reverse_diagnostic),
    }
    return html_doc, summary


def summary_loss_learning_verdict(loss_learning: pd.DataFrame) -> str:
    if loss_learning.empty:
        return "not_run"
    value = loss_learning["loss_learning_verdict"].dropna().astype(str)
    return value.iloc[0] if not value.empty else "not_run"


def selected_loss_learning_delta(loss_learning: pd.DataFrame) -> float:
    if loss_learning.empty:
        return 0.0
    selected = loss_learning["candidate"].astype(str).str.startswith("SELECTED::")
    if not selected.any():
        return 0.0
    return float(pd.to_numeric(loss_learning.loc[selected, "test_delta_net_points"], errors="coerce").fillna(0.0).sum())


def summary_reverse_trade_verdict(reverse_diagnostic: pd.DataFrame) -> str:
    if reverse_diagnostic.empty:
        return "not_run"
    value = reverse_diagnostic["reverse_trade_verdict"].dropna().astype(str)
    return value.iloc[0] if not value.empty else "not_run"


def selected_reverse_trade_delta(reverse_diagnostic: pd.DataFrame) -> float:
    if reverse_diagnostic.empty:
        return 0.0
    selected = reverse_diagnostic["candidate"].astype(str).str.startswith("SELECTED::")
    if not selected.any():
        return 0.0
    return float(
        pd.to_numeric(reverse_diagnostic.loc[selected, "test_reverse_delta_vs_baseline"], errors="coerce")
        .fillna(0.0)
        .sum()
    )


def metric(label: str, value: str, note: str) -> str:
    return f'<div class="metric"><small>{esc(label)}</small><strong>{esc(value)}</strong><span>{esc(note)}</span></div>'


def annual_summary(trades: pd.DataFrame) -> pd.DataFrame:
    frame = trades.copy()
    frame["budgeted_points"] = frame["net_points"] * frame["risk_weight"].fillna(1.0)
    grouped = frame.groupby(frame["entry_ts"].dt.year).agg(
        trades=("net_points", "size"),
        net_points=("net_points", "sum"),
        budgeted_net_points=("budgeted_points", "sum"),
        win_rate=("net_points", lambda values: float((values > 0).mean())),
    )
    return grouped.reset_index(names="year")


def monthly_summary(trades: pd.DataFrame) -> pd.DataFrame:
    grouped = trades.groupby(trades["entry_ts"].dt.strftime("%Y-%m")).agg(
        trades=("net_points", "size"),
        net_points=("net_points", "sum"),
    )
    return grouped.tail(24).reset_index(names="month")


def source_summary(trades: pd.DataFrame) -> pd.DataFrame:
    frame = trades.copy()
    frame["budgeted_points"] = frame["net_points"] * frame["risk_weight"].fillna(1.0)
    rows = []
    for (source, label), group in frame.groupby(["strategy_source", "strategy_label"], dropna=False):
        rows.append(
            {
                "strategy_source": source,
                "strategy_label": label,
                "trades": len(group),
                "net_points": group["net_points"].sum(),
                "budgeted_net_points": group["budgeted_points"].sum(),
                "profit_factor": profit_factor(group["net_points"]),
                "risk_weight": group["risk_weight"].median(),
            }
        )
    return pd.DataFrame(rows)


def write_report(args: argparse.Namespace) -> dict[str, Any]:
    feature_trades = load_feature_trades(args.feature_trades)
    composite_trades = read_trades(args.composite_trades)
    bars = load_bars(args.bars)
    walk_forward, wf_trades = run_walk_forward(feature_trades, composite_trades)
    leakage = leakage_audit_table(composite_trades, bars)
    stress = stress_tables(composite_trades, bars)
    loss_learning = run_loss_learning_walk_forward(composite_trades, bars)
    reverse_diagnostic = run_reverse_trade_diagnostic(composite_trades, bars)
    risk_mapping = risk_budget_mapping()
    paper_plan = paper_validation_plan()
    paper_interface = paper_interface_readiness_table()
    readiness = paper_readiness(composite_trades, leakage, stress)
    generated_at = args.generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html_doc, summary = build_html_report(
        composite_trades=composite_trades,
        walk_forward=walk_forward,
        leakage=leakage,
        stress=stress,
        loss_learning=loss_learning,
        reverse_diagnostic=reverse_diagnostic,
        bars=bars,
        readiness=readiness,
        risk_mapping=risk_mapping,
        paper_plan=paper_plan,
        paper_interface=paper_interface,
        generated_at=generated_at,
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(html_doc, encoding="utf-8")
    write_markdown(Path(args.markdown_output), readiness, summary)
    Path(args.summary_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary_output).write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    Path(args.walk_forward_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.walk_forward_trades_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.stress_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.leakage_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.loss_learning_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.reverse_diagnostic_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.paper_plan_output).parent.mkdir(parents=True, exist_ok=True)
    walk_forward.to_csv(args.walk_forward_output, index=False)
    wf_trades.to_csv(args.walk_forward_trades_output, index=False)
    stress.to_csv(args.stress_output, index=False)
    leakage.to_csv(args.leakage_output, index=False)
    loss_learning.to_csv(args.loss_learning_output, index=False)
    reverse_diagnostic.to_csv(args.reverse_diagnostic_output, index=False)
    paper_plan.to_csv(args.paper_plan_output, index=False)
    return {
        "output": args.output,
        "markdown_output": args.markdown_output,
        "summary_output": args.summary_output,
        "walk_forward_output": args.walk_forward_output,
        "stress_output": args.stress_output,
        "leakage_output": args.leakage_output,
        "loss_learning_output": args.loss_learning_output,
        "reverse_diagnostic_output": args.reverse_diagnostic_output,
        "paper_plan_output": args.paper_plan_output,
        **summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate NQ Lightglow composite paper-readiness audit report.")
    parser.add_argument("--feature-trades", default=DEFAULT_FEATURE_TRADES)
    parser.add_argument("--composite-trades", default=DEFAULT_COMPOSITE_TRADES)
    parser.add_argument("--lightglow-oos-trades", default=DEFAULT_LIGHTGLOW_OOS_TRADES)
    parser.add_argument("--bars", default=DEFAULT_BARS)
    parser.add_argument("--output", default=DEFAULT_REPORT)
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN)
    parser.add_argument("--summary-output", default=DEFAULT_SUMMARY)
    parser.add_argument("--walk-forward-output", default=DEFAULT_WALK_FORWARD)
    parser.add_argument("--walk-forward-trades-output", default=".tmp/nq-lightglow-composite-paper-readiness-wf-trades.csv")
    parser.add_argument("--stress-output", default=DEFAULT_STRESS)
    parser.add_argument("--leakage-output", default=DEFAULT_LEAKAGE)
    parser.add_argument("--loss-learning-output", default=DEFAULT_LOSS_LEARNING)
    parser.add_argument("--reverse-diagnostic-output", default=DEFAULT_REVERSE_DIAGNOSTIC)
    parser.add_argument("--paper-plan-output", default=DEFAULT_PAPER_PLAN)
    parser.add_argument("--generated-at", default="")
    args = parser.parse_args()
    print(json.dumps(write_report(args), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
