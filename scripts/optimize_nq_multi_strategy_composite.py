from __future__ import annotations

import argparse
import html
import itertools
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


CORE_TIER = "core_long_term"
RESEARCH_TIER = "research_extension"
REJECT_TIER = "reject"


@dataclass(frozen=True)
class ComboResult:
    name: str
    labels: tuple[str, ...]
    trades: pd.DataFrame
    dropped_trades: pd.DataFrame
    metrics: dict[str, float]
    objective_score: float
    eligibility: str
    window_start: pd.Timestamp | None
    window_end: pd.Timestamp | None


def read_csv(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def as_float(value: object, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def safe_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return html.escape(str(value), quote=True)


def load_audit_metadata(path: str | Path) -> pd.DataFrame:
    audit = read_csv(path)
    if audit.empty:
        return pd.DataFrame()
    frame = audit.copy()
    frame["strategy_source"] = frame["strategy_source"].astype(str)
    frame["strategy_label"] = frame["strategy_label"].astype(str)
    frame["candidate"] = frame["candidate"].astype(str)
    frame["long_term_research_pass"] = frame["long_term_research_pass"].map(as_bool)
    frame["readiness_tier"] = frame["readiness_tier"].astype(str)
    frame["deployment_tier"] = frame.apply(deployment_tier, axis=1)
    frame["feature_family"] = frame.apply(feature_family, axis=1)
    frame["priority_score"] = frame.apply(priority_score, axis=1)
    frame["eligible_for_composite"] = frame["deployment_tier"].isin({CORE_TIER, RESEARCH_TIER}) & (
        pd.to_numeric(frame["net_points"], errors="coerce").fillna(0.0) > 0.0
    )
    return frame


def deployment_tier(row: pd.Series) -> str:
    if as_bool(row.get("long_term_research_pass")):
        return CORE_TIER
    if str(row.get("readiness_tier", "")) == "continue_research":
        return RESEARCH_TIER
    return REJECT_TIER


def feature_family(row: pd.Series) -> str:
    source = str(row.get("strategy_source", ""))
    label = str(row.get("strategy_label", ""))
    candidate = str(row.get("candidate", ""))
    text = f"{label} {candidate}".lower()
    if source == "regime_transition":
        return "range_compression_displacement_breakout"
    if source == "ict_order_flow_shift":
        if "high_relative_volume" in text:
            return "ict_ofs_high_relative_volume"
        if "open_trend_volume" in text:
            return "ict_ofs_open_trend_volume"
        return "ict_order_flow_shift"
    if source == "screenshot_smc_momentum":
        if "eql" in text:
            return "smc_equal_low_sweep_reclaim"
        if "eqh" in text:
            return "smc_equal_high_sweep_reject"
        if "displacement" in text:
            return "smc_displacement_pullback"
        if "bos" in text:
            return "smc_bos_continuation"
    return source or "unknown"


def priority_score(row: pd.Series) -> float:
    net_dd = as_float(row.get("net_to_drawdown"))
    pf = as_float(row.get("profit_factor"))
    pos_year = as_float(row.get("positive_year_rate"))
    pos_180 = as_float(row.get("positive_180d_rate"))
    cost3 = as_float(row.get("cost_3_125_net_points"))
    tier_bonus = 1000.0 if as_bool(row.get("long_term_research_pass")) else 100.0
    if str(row.get("readiness_tier", "")) == "reject_current_form":
        tier_bonus = -1000.0
    cost_bonus = min(max(cost3 / 500.0, -5.0), 5.0)
    return float(tier_bonus + net_dd * 12.0 + pf * 30.0 + pos_year * 25.0 + pos_180 * 18.0 + cost_bonus)


def normalize_regime_trades(path: str | Path, audit: pd.DataFrame) -> pd.DataFrame:
    trades = read_csv(path)
    if trades.empty:
        return pd.DataFrame()
    frame = trades.copy()
    frame["strategy_source"] = "regime_transition"
    frame["strategy_label"] = frame.get("audit_label", frame.get("candidate", "")).astype(str)
    return normalize_trade_columns(frame, audit)


def normalize_template_trades(path: str | Path, strategy_source: str, audit: pd.DataFrame) -> pd.DataFrame:
    trades = read_csv(path)
    if trades.empty:
        return pd.DataFrame()
    frame = trades.copy()
    label_column = "template" if "template" in frame.columns else "candidate"
    frame["strategy_source"] = strategy_source
    frame["strategy_label"] = frame[label_column].astype(str)
    return normalize_trade_columns(frame, audit)


def normalize_trade_columns(trades: pd.DataFrame, audit: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    required = {"strategy_source", "strategy_label", "entry_ts", "exit_ts", "net_points", "direction"}
    missing = sorted(required - set(trades.columns))
    if missing:
        raise ValueError(f"trade file is missing required columns: {missing}")
    meta_cols = [
        "strategy_source",
        "strategy_label",
        "candidate",
        "deployment_tier",
        "feature_family",
        "priority_score",
        "long_term_research_pass",
        "readiness_tier",
        "profit_factor",
        "net_to_drawdown",
    ]
    meta = audit[meta_cols].copy()
    frame = trades.merge(meta, on=["strategy_source", "strategy_label"], how="inner", suffixes=("", "_meta"))
    if frame.empty:
        return frame
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    frame["exit_ts"] = pd.to_datetime(frame["exit_ts"], utc=True)
    frame["net_points"] = pd.to_numeric(frame["net_points"], errors="coerce").fillna(0.0)
    frame["gross_points"] = pd.to_numeric(frame.get("gross_points", frame["net_points"]), errors="coerce").fillna(
        frame["net_points"]
    )
    frame["direction"] = pd.to_numeric(frame["direction"], errors="coerce").fillna(0).astype(int)
    frame["priority_score"] = pd.to_numeric(frame["priority_score"], errors="coerce").fillna(0.0)
    if "entry_index" in frame.columns and "exit_index" in frame.columns:
        frame["same_bar_exit"] = (
            pd.to_numeric(frame["entry_index"], errors="coerce")
            == pd.to_numeric(frame["exit_index"], errors="coerce")
        )
    else:
        frame["same_bar_exit"] = False
    return frame.sort_values(["entry_ts", "priority_score"], ascending=[True, False]).reset_index(drop=True)


def load_trade_pool(args: argparse.Namespace, audit: pd.DataFrame) -> pd.DataFrame:
    frames = [
        normalize_regime_trades(args.regime_trades, audit),
        normalize_template_trades(args.ofs_trades, "ict_order_flow_shift", audit),
        normalize_template_trades(args.screenshot_trades, "screenshot_smc_momentum", audit),
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame()
    pool = pd.concat(frames, ignore_index=True, sort=False)
    eligible_labels = set(audit.loc[audit["eligible_for_composite"], "strategy_label"].astype(str))
    return pool[pool["strategy_label"].isin(eligible_labels)].reset_index(drop=True)


def candidate_rows(audit: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    if audit.empty:
        return pd.DataFrame()
    counts = (
        trades.groupby(["strategy_source", "strategy_label"], as_index=False)
        .agg(trade_rows=("net_points", "size"), trade_start=("entry_ts", "min"), trade_end=("entry_ts", "max"))
        if not trades.empty
        else pd.DataFrame(columns=["strategy_source", "strategy_label", "trade_rows", "trade_start", "trade_end"])
    )
    rows = audit.merge(counts, on=["strategy_source", "strategy_label"], how="left")
    rows["trade_rows"] = pd.to_numeric(rows["trade_rows"], errors="coerce").fillna(0).astype(int)
    rows["has_trade_coverage"] = rows["trade_rows"] > 0
    return rows.sort_values(
        ["eligible_for_composite", "deployment_tier", "priority_score"],
        ascending=[False, True, False],
    ).reset_index(drop=True)


def generate_combos(
    candidates: pd.DataFrame,
    *,
    max_combo_size: int,
    require_core: bool,
    max_per_family: int,
) -> list[tuple[str, ...]]:
    eligible = candidates[candidates["eligible_for_composite"] & candidates["has_trade_coverage"]].copy()
    labels = eligible["strategy_label"].astype(str).tolist()
    family_by_label = dict(zip(eligible["strategy_label"].astype(str), eligible["feature_family"].astype(str), strict=False))
    tier_by_label = dict(zip(eligible["strategy_label"].astype(str), eligible["deployment_tier"].astype(str), strict=False))
    combos: list[tuple[str, ...]] = []
    for size in range(1, min(max_combo_size, len(labels)) + 1):
        for combo in itertools.combinations(labels, size):
            if require_core and CORE_TIER not in {tier_by_label[label] for label in combo}:
                continue
            family_counts = pd.Series([family_by_label[label] for label in combo]).value_counts()
            if int(family_counts.max()) > max_per_family:
                continue
            combos.append(combo)
    return combos


def combo_window(trades: pd.DataFrame, labels: tuple[str, ...]) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    starts: list[pd.Timestamp] = []
    ends: list[pd.Timestamp] = []
    for label in labels:
        selected = trades[trades["strategy_label"].astype(str).eq(label)]
        if selected.empty:
            return None, None
        starts.append(selected["entry_ts"].min())
        ends.append(selected["entry_ts"].max())
    start = max(starts)
    end = min(ends)
    if pd.isna(start) or pd.isna(end) or start > end:
        return None, None
    # Use full trading-day boundaries for common-window ranking. Strategies often
    # operate in different intraday sessions, so minute-exact overlap would drop
    # valid same-day signals from earlier/later sessions.
    day_start = start.normalize()
    day_end = end.normalize() + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    return day_start, day_end


def resolve_conflicts(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if trades.empty:
        return trades.copy(), trades.copy()
    frame = trades.sort_values(["entry_ts", "priority_score", "exit_ts"], ascending=[True, False, True]).reset_index(drop=True)
    selected_rows: list[pd.Series] = []
    dropped_rows: list[pd.Series] = []
    active_exit: pd.Timestamp | None = None
    for _, row in frame.iterrows():
        entry_ts = row["entry_ts"]
        if active_exit is not None and entry_ts < active_exit:
            copy = row.copy()
            copy["drop_reason"] = "active_trade_conflict"
            dropped_rows.append(copy)
            continue
        selected_rows.append(row)
        active_exit = row["exit_ts"] if active_exit is None else max(active_exit, row["exit_ts"])
    selected = pd.DataFrame(selected_rows).reset_index(drop=True) if selected_rows else pd.DataFrame(columns=frame.columns)
    dropped = pd.DataFrame(dropped_rows).reset_index(drop=True) if dropped_rows else pd.DataFrame(columns=list(frame.columns) + ["drop_reason"])
    return selected, dropped


def risk_budget_map(audit: pd.DataFrame, labels: tuple[str, ...]) -> dict[str, float]:
    meta = audit[audit["strategy_label"].isin(labels)].copy()
    if meta.empty:
        return {}
    core = meta[meta["deployment_tier"].eq(CORE_TIER)].copy()
    research = meta[meta["deployment_tier"].eq(RESEARCH_TIER)].copy()
    if research.empty:
        core_budget, research_budget = 1.0, 0.0
    elif core.empty:
        core_budget, research_budget = 0.0, 1.0
    else:
        core_budget, research_budget = 0.70, 0.30

    budgets: dict[str, float] = {}

    def allocate(group: pd.DataFrame, total_budget: float) -> None:
        if group.empty or total_budget <= 0.0:
            return
        scores = pd.to_numeric(group["priority_score"], errors="coerce").fillna(0.0).clip(lower=0.0)
        weights = scores / float(scores.sum()) if float(scores.sum()) > 0.0 else pd.Series(1.0 / len(group), index=group.index)
        for index, weight in weights.items():
            budgets[str(group.loc[index, "strategy_label"])] = float(total_budget * weight)

    allocate(core, core_budget)
    allocate(research, research_budget)
    return budgets


def summarize_trades(trades: pd.DataFrame, dropped: pd.DataFrame | None = None) -> dict[str, float]:
    if trades.empty:
        return {
            "trades": 0.0,
            "net_points": 0.0,
            "max_drawdown_points": 0.0,
            "net_to_drawdown": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "payoff_ratio": 0.0,
            "avg_points": 0.0,
            "positive_month_rate": 0.0,
            "positive_year_rate": 0.0,
            "min_month_net_points": 0.0,
            "min_year_net_points": 0.0,
            "same_bar_exit_rate": 0.0,
            "conflict_dropped": float(len(dropped)) if dropped is not None else 0.0,
            "risk_budgeted_net_points": 0.0,
            "risk_budgeted_max_drawdown_points": 0.0,
            "risk_budgeted_profit_factor": 0.0,
        }
    frame = trades.sort_values(["entry_ts", "exit_ts"]).copy()
    net = pd.to_numeric(frame["net_points"], errors="coerce").fillna(0.0)
    wins = net[net > 0]
    losses = net[net < 0]
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    monthly = net.groupby(frame["entry_ts"].dt.strftime("%Y-%m")).sum()
    yearly = net.groupby(frame["entry_ts"].dt.year).sum()
    max_dd = float(drawdown.max()) if not drawdown.empty else 0.0
    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss = float(-losses.mean()) if not losses.empty else 0.0
    metrics = {
        "trades": float(len(frame)),
        "net_points": float(net.sum()),
        "max_drawdown_points": max_dd,
        "net_to_drawdown": float(net.sum() / max_dd) if max_dd else (999.0 if net.sum() > 0 else 0.0),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else (999.0 if gross_profit > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "payoff_ratio": float(avg_win / avg_loss) if avg_loss else 0.0,
        "avg_points": float(net.mean()),
        "positive_month_rate": float((monthly > 0).mean()) if not monthly.empty else 0.0,
        "positive_year_rate": float((yearly > 0).mean()) if not yearly.empty else 0.0,
        "min_month_net_points": float(monthly.min()) if not monthly.empty else 0.0,
        "min_year_net_points": float(yearly.min()) if not yearly.empty else 0.0,
        "same_bar_exit_rate": float(frame["same_bar_exit"].mean()) if "same_bar_exit" in frame else 0.0,
        "conflict_dropped": float(len(dropped)) if dropped is not None else 0.0,
    }
    if "risk_weight" in frame:
        weighted_net = net * pd.to_numeric(frame["risk_weight"], errors="coerce").fillna(1.0)
        weighted_wins = weighted_net[weighted_net > 0]
        weighted_losses = weighted_net[weighted_net < 0]
        weighted_equity = weighted_net.cumsum()
        weighted_drawdown = weighted_equity.cummax() - weighted_equity
        weighted_gross_loss = float(-weighted_losses.sum())
        metrics["risk_budgeted_net_points"] = float(weighted_net.sum())
        metrics["risk_budgeted_max_drawdown_points"] = float(weighted_drawdown.max()) if not weighted_drawdown.empty else 0.0
        metrics["risk_budgeted_profit_factor"] = (
            float(weighted_wins.sum() / weighted_gross_loss)
            if weighted_gross_loss
            else (999.0 if float(weighted_wins.sum()) > 0.0 else 0.0)
        )
    else:
        metrics["risk_budgeted_net_points"] = metrics["net_points"]
        metrics["risk_budgeted_max_drawdown_points"] = metrics["max_drawdown_points"]
        metrics["risk_budgeted_profit_factor"] = metrics["profit_factor"]
    return metrics


def objective_score(metrics: dict[str, float], *, family_count: int, research_count: int) -> float:
    if metrics["trades"] <= 0:
        return -1e9
    scored_net = metrics.get("risk_budgeted_net_points", metrics["net_points"])
    scored_drawdown = metrics.get("risk_budgeted_max_drawdown_points", metrics["max_drawdown_points"])
    risk = max(scored_drawdown, abs(metrics["min_month_net_points"]), 1.0)
    stability = (
        0.35 * metrics["positive_month_rate"]
        + 0.25 * metrics["positive_year_rate"]
        + 0.20 * min(metrics["profit_factor"] / 2.0, 1.0)
        + 0.20 * min(max(metrics["net_to_drawdown"], 0.0) / 10.0, 1.0)
    )
    diversification = 1.0 + min(max(family_count - 1, 0), 3) * 0.08
    research_penalty = 1.0 - min(research_count, 3) * 0.04
    same_bar_penalty = 1.0 - min(metrics.get("same_bar_exit_rate", 0.0), 0.5) * 0.30
    return float((scored_net / risk) * stability * diversification * research_penalty * same_bar_penalty)


def evaluate_combo(
    trades: pd.DataFrame,
    audit: pd.DataFrame,
    labels: tuple[str, ...],
    *,
    require_common_window: bool,
) -> ComboResult:
    selected = trades[trades["strategy_label"].isin(labels)].copy()
    start: pd.Timestamp | None = None
    end: pd.Timestamp | None = None
    if require_common_window:
        start, end = combo_window(trades, labels)
        if start is None or end is None:
            selected = selected.iloc[0:0]
        else:
            selected = selected[(selected["entry_ts"] >= start) & (selected["entry_ts"] <= end)]
    selected["risk_weight"] = selected["strategy_label"].map(risk_budget_map(audit, labels)).fillna(1.0)
    resolved, dropped = resolve_conflicts(selected)
    metrics = summarize_trades(resolved, dropped)
    meta = audit[audit["strategy_label"].isin(labels)]
    family_count = int(meta["feature_family"].nunique()) if not meta.empty else 0
    research_count = int((meta["deployment_tier"] == RESEARCH_TIER).sum()) if not meta.empty else 0
    eligibility = "production_core" if research_count == 0 else "research_diversified"
    name = " + ".join(labels)
    score = objective_score(metrics, family_count=family_count, research_count=research_count)
    return ComboResult(name, labels, resolved, dropped, metrics, score, eligibility, start, end)


def evaluate_combinations(
    trades: pd.DataFrame,
    candidates: pd.DataFrame,
    audit: pd.DataFrame,
    args: argparse.Namespace,
) -> list[ComboResult]:
    combos = generate_combos(
        candidates,
        max_combo_size=args.max_combo_size,
        require_core=True,
        max_per_family=args.max_per_family,
    )
    results = [
        evaluate_combo(trades, audit, combo, require_common_window=args.rank_on_common_window)
        for combo in combos
    ]
    return sorted(results, key=lambda item: item.objective_score, reverse=True)


def select_best(results: list[ComboResult]) -> ComboResult:
    diversified = [item for item in results if len(item.labels) >= 2 and item.eligibility == "research_diversified"]
    if diversified:
        return max(diversified, key=lambda item: item.objective_score)
    multi = [item for item in results if len(item.labels) >= 2]
    if multi:
        return max(multi, key=lambda item: item.objective_score)
    if results:
        return results[0]
    return ComboResult("empty", tuple(), pd.DataFrame(), pd.DataFrame(), summarize_trades(pd.DataFrame()), 0.0, "none", None, None)


def walk_forward_years(
    trades: pd.DataFrame,
    candidates: pd.DataFrame,
    audit: pd.DataFrame,
    args: argparse.Namespace,
) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    years = sorted(pd.to_datetime(trades["entry_ts"], utc=True).dt.year.unique().tolist())
    rows: list[dict[str, Any]] = []
    for year in years:
        train = trades[trades["entry_ts"].dt.year < year]
        test = trades[trades["entry_ts"].dt.year == year]
        if train["entry_ts"].dt.year.nunique() < args.min_train_years or test.empty:
            continue
        train_counts = train.groupby("strategy_label").size()
        covered = candidates[candidates["strategy_label"].isin(train_counts[train_counts >= args.min_train_trades].index)]
        train_args = argparse.Namespace(
            max_combo_size=args.max_combo_size,
            max_per_family=args.max_per_family,
            rank_on_common_window=False,
        )
        train_results = evaluate_combinations(train, covered, audit, train_args)
        if not train_results:
            continue
        selected = select_best(train_results)
        test_result = evaluate_combo(test, audit, selected.labels, require_common_window=False)
        rows.append(
            {
                "year": int(year),
                "selected_combo": selected.name,
                "train_score": selected.objective_score,
                **{f"test_{key}": value for key, value in test_result.metrics.items()},
            }
        )
    return pd.DataFrame(rows)


def source_breakdown(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows = []
    for keys, group in trades.groupby(["strategy_source", "feature_family", "strategy_label"], dropna=False):
        metrics = summarize_trades(group)
        rows.append(
            {
                "strategy_source": keys[0],
                "feature_family": keys[1],
                "strategy_label": keys[2],
                "trades": metrics["trades"],
                "net_points": metrics["net_points"],
                "profit_factor": metrics["profit_factor"],
                "win_rate": metrics["win_rate"],
                "same_bar_exit_rate": metrics["same_bar_exit_rate"],
                "risk_budgeted_net_points": metrics["risk_budgeted_net_points"],
            }
        )
    return pd.DataFrame(rows).sort_values("net_points", ascending=False)


def summarize_walk_forward(walk_forward: pd.DataFrame) -> dict[str, float]:
    if walk_forward.empty or "test_net_points" not in walk_forward:
        return {"net_points": 0.0, "positive_year_rate": 0.0}
    net = pd.to_numeric(walk_forward["test_net_points"], errors="coerce").fillna(0.0)
    return {
        "net_points": float(net.sum()),
        "positive_year_rate": float((net > 0).mean()) if not net.empty else 0.0,
    }


def equity_points(trades: pd.DataFrame, *, risk_budgeted: bool = False) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["x", "equity"])
    frame = trades.sort_values(["entry_ts", "exit_ts"]).reset_index(drop=True)
    net = pd.to_numeric(frame["net_points"], errors="coerce").fillna(0.0)
    if risk_budgeted and "risk_weight" in frame:
        net = net * pd.to_numeric(frame["risk_weight"], errors="coerce").fillna(1.0)
    return pd.DataFrame({"x": np.arange(1, len(frame) + 1), "equity": net.cumsum()})


def svg_line(points: pd.DataFrame, *, width: int = 980, height: int = 300) -> str:
    if points.empty:
        return "<p class=\"empty\">无曲线数据。</p>"
    values = pd.to_numeric(points["equity"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    low = min(0.0, float(values.min()))
    high = max(0.0, float(values.max()))
    if high <= low:
        high = low + 1.0
    pad_l, pad_r, pad_t, pad_b = 58, 20, 20, 34
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b
    denom = max(len(values) - 1, 1)
    coords = []
    for index, value in enumerate(values):
        x = pad_l + index / denom * inner_w
        y = pad_t + (high - value) / (high - low) * inner_h
        coords.append(f"{x:.1f},{y:.1f}")
    zero_y = pad_t + (high - 0.0) / (high - low) * inner_h
    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="equity curve">
      <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>
      <line x1="{pad_l}" y1="{zero_y:.1f}" x2="{width - pad_r}" y2="{zero_y:.1f}" stroke="#b8c2cc" stroke-dasharray="4 5"/>
      <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{height - pad_b}" stroke="#8592a3"/>
      <line x1="{pad_l}" y1="{height - pad_b}" x2="{width - pad_r}" y2="{height - pad_b}" stroke="#8592a3"/>
      <polyline points="{' '.join(coords)}" fill="none" stroke="#176b87" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
      <text x="8" y="{pad_t + 4}" font-size="12" fill="#51606f">高 {high:,.0f}</text>
      <text x="8" y="{height - pad_b}" font-size="12" fill="#51606f">低 {low:,.0f}</text>
    </svg>
    """


def fmt_metric(key: str, value: object) -> str:
    if key.endswith("_rate") or key in {"win_rate", "positive_month_rate", "positive_year_rate"}:
        return f"{as_float(value) * 100:.1f}%"
    if key in {"trades", "conflict_dropped"} or key.endswith("_trades") or key.endswith("_dropped"):
        return f"{int(as_float(value)):,}"
    if key == "profit_factor" or key.endswith("_profit_factor"):
        number = as_float(value)
        return "inf" if number >= 900 else f"{number:.2f}"
    if (
        key.endswith("_points")
        or key in {"net_to_drawdown", "payoff_ratio", "avg_points", "objective_score"}
        or key.endswith("_drawdown")
        or key.endswith("_to_drawdown")
    ):
        return f"{as_float(value):,.2f}"
    if key in {"risk_budget_fraction", "risk_weight"}:
        return f"{as_float(value) * 100:.1f}%"
    return safe_text(value)


def html_table(frame: pd.DataFrame, columns: list[tuple[str, str]], limit: int | None = None) -> str:
    if frame.empty:
        return "<p class=\"empty\">无记录。</p>"
    display = frame.head(limit).copy() if limit else frame.copy()
    head = "".join(f"<th>{safe_text(label)}</th>" for _, label in columns)
    rows = []
    for _, row in display.iterrows():
        cells = "".join(f"<td>{fmt_metric(key, row.get(key, ''))}</td>" for key, _ in columns)
        rows.append(f"<tr>{cells}</tr>")
    return f"<div class=\"table-wrap\"><table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"


def results_frame(results: list[ComboResult]) -> pd.DataFrame:
    rows = []
    for result in results:
        rows.append(
            {
                "combo": result.name,
                "eligibility": result.eligibility,
                "labels": json.dumps(result.labels, ensure_ascii=False),
                "window_start": str(result.window_start.date()) if result.window_start is not None else "",
                "window_end": str(result.window_end.date()) if result.window_end is not None else "",
                "objective_score": result.objective_score,
                **result.metrics,
            }
        )
    return pd.DataFrame(rows)


def build_html(
    *,
    best: ComboResult,
    ranking: pd.DataFrame,
    candidates: pd.DataFrame,
    walk_forward: pd.DataFrame,
    generated_at: str,
    source_paths: dict[str, str],
) -> str:
    metrics = best.metrics
    cards = [
        ("净点数", "net_points"),
        ("最大回撤", "max_drawdown_points"),
        ("PF", "profit_factor"),
        ("预算净点", "risk_budgeted_net_points"),
        ("胜率", "win_rate"),
        ("正年份率", "positive_year_rate"),
        ("冲突丢弃", "conflict_dropped"),
        ("同K进出率", "same_bar_exit_rate"),
    ]
    card_html = "".join(
        f"<div class=\"metric\"><span>{safe_text(label)}</span><strong>{fmt_metric(key, metrics.get(key, 0.0))}</strong></div>"
        for label, key in cards
    )
    source_items = "".join(f"<li><code>{safe_text(name)}</code>: {safe_text(path)}</li>" for name, path in source_paths.items())
    component_meta = candidates[candidates["strategy_label"].isin(best.labels)].copy()
    component_meta["risk_budget_fraction"] = component_meta["strategy_label"].map(risk_budget_map(candidates, best.labels)).fillna(0.0)
    breakdown = source_breakdown(best.trades)
    wf_summary = summarize_walk_forward(walk_forward)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ 多策略组合优化报告</title>
  <style>
    :root {{
      --ink: #17212b;
      --muted: #5d6b7a;
      --panel: #ffffff;
      --line: #d7dee8;
      --blue: #176b87;
      --teal: #1f7a68;
      --amber: #a66f00;
      --red: #b34242;
      --bg: #f4f7fb;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    header {{ padding: 34px min(5vw, 58px) 24px; background: #111827; color: #f8fafc; }}
    h1 {{ margin: 0 0 10px; font-size: 38px; line-height: 1.08; letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 23px; }}
    h3 {{ margin: 0 0 8px; font-size: 16px; }}
    p {{ margin: 0 0 10px; }}
    code {{ font-size: 12px; padding: 2px 5px; border-radius: 5px; background: #eef2f7; color: #132033; }}
    header code {{ background: #263244; color: #e7edf6; }}
    main {{ padding: 24px min(5vw, 58px) 56px; }}
    section {{ margin: 18px 0; padding: 22px; border: 1px solid var(--line); background: var(--panel); border-radius: 8px; }}
    .subtitle {{ max-width: 1050px; color: #c8d2df; font-size: 16px; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 10px; margin-top: 20px; }}
    .metric {{ padding: 13px; border: 1px solid #2f3d4f; border-radius: 8px; background: #1e293b; }}
    .metric span {{ display: block; color: #b8c3d2; font-size: 12px; }}
    .metric strong {{ display: block; margin-top: 4px; font-size: 22px; color: #ffffff; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .note {{ border-left: 4px solid var(--blue); padding: 12px 14px; background: #eef8fb; border-radius: 6px; }}
    .warn {{ border-left-color: var(--amber); background: #fff7e8; }}
    .bad {{ border-left-color: var(--red); background: #fff0f0; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 8px 7px; text-align: left; vertical-align: top; }}
    th {{ background: #edf2f7; color: #475569; }}
    svg {{ width: 100%; height: auto; border: 1px solid var(--line); border-radius: 8px; }}
    .empty, .sources {{ color: var(--muted); }}
    @media (max-width: 1050px) {{
      .metric-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .grid {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 30px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>NQ 多策略组合优化报告</h1>
    <p class="subtitle">组合目标：在长期通过的 regime-transition 核心策略上，谨慎叠加 OFS/SMC 等不同行情特征；所有组合必须经过冲突处理、共同样本窗口排名和年度 walk-forward 检查。生成时间：{safe_text(generated_at)}。</p>
    <div class="metric-grid">{card_html}</div>
  </header>
  <main>
    <section>
      <h2>最终组合</h2>
      <div class="grid">
        <div class="note">
          <p><strong>组合：</strong><code>{safe_text(best.name)}</code></p>
          <p><strong>资格：</strong>{safe_text(best.eligibility)}。如果组合包含 research_extension，它只能作为研究组合或纸盘小仓验证，不能等同于生产批准。</p>
          <p><strong>共同样本窗口：</strong>{safe_text(str(best.window_start.date()) if best.window_start is not None else "N/A")} 至 {safe_text(str(best.window_end.date()) if best.window_end is not None else "N/A")}。</p>
        </div>
        <div class="note warn">
          <p><strong>冲突处理：</strong>同一时间只允许一笔持仓；若交易重叠，按进场时间和候选优先级保留先触发/高优先级交易，其他信号记录为 conflict_dropped。</p>
          <p><strong>关键限制：</strong>OFS/SMC 候选目前仍是研究层级，且部分 1 分钟 bar 策略存在同K进出假设，正式验证需使用严格成交模型或 tick replay。</p>
        </div>
      </div>
    </section>
    <section>
      <h2>资金曲线</h2>
      <h3>原始信号净点曲线</h3>
      {svg_line(equity_points(best.trades))}
      <h3>风险预算净点曲线</h3>
      {svg_line(equity_points(best.trades, risk_budgeted=True))}
    </section>
    <section>
      <h2>组件明细</h2>
      {html_table(component_meta, [
          ("strategy_source", "来源"),
          ("strategy_label", "策略"),
          ("deployment_tier", "层级"),
          ("feature_family", "行情特征"),
          ("net_points", "单策略净点"),
          ("profit_factor", "PF"),
          ("net_to_drawdown", "净值/回撤"),
          ("risk_budget_fraction", "风险预算"),
          ("trade_rows", "逐笔覆盖"),
      ])}
    </section>
    <section>
      <h2>组合内贡献</h2>
      {html_table(breakdown, [
          ("strategy_source", "来源"),
          ("feature_family", "行情特征"),
          ("strategy_label", "策略"),
          ("trades", "交易数"),
          ("net_points", "净点"),
          ("profit_factor", "PF"),
          ("win_rate", "胜率"),
          ("risk_budgeted_net_points", "预算净点"),
          ("same_bar_exit_rate", "同K进出"),
      ])}
    </section>
    <section>
      <h2>静态组合排名</h2>
      {html_table(ranking, [
          ("combo", "组合"),
          ("eligibility", "资格"),
          ("window_start", "窗口起点"),
          ("window_end", "窗口终点"),
          ("trades", "交易数"),
          ("net_points", "净点"),
          ("max_drawdown_points", "最大回撤"),
          ("profit_factor", "PF"),
          ("risk_budgeted_net_points", "预算净点"),
          ("positive_year_rate", "正年份率"),
          ("same_bar_exit_rate", "同K进出"),
          ("conflict_dropped", "冲突丢弃"),
          ("objective_score", "评分"),
      ], limit=18)}
    </section>
    <section>
      <h2>年度 Walk-Forward 组合验证</h2>
      <p>每个测试年只用此前历史选择组合，再应用到该测试年。这个表用于检查组合调度器是否依赖未来样本。</p>
      <p class="note">年度 WF 汇总净点数：{fmt_metric("net_points", wf_summary.get("net_points", 0.0))}；正年份率：{fmt_metric("positive_year_rate", wf_summary.get("positive_year_rate", 0.0))}。</p>
      {html_table(walk_forward, [
          ("year", "测试年"),
          ("selected_combo", "训练期选择"),
          ("test_trades", "交易数"),
          ("test_net_points", "净点"),
          ("test_max_drawdown_points", "最大回撤"),
          ("test_profit_factor", "PF"),
          ("test_win_rate", "胜率"),
          ("test_conflict_dropped", "冲突丢弃"),
      ])}
    </section>
    <section>
      <h2>上线原则</h2>
      <p>1. 生产核心只允许长期通过的 <code>{CORE_TIER}</code>；包含 <code>{RESEARCH_TIER}</code> 的组合只能纸盘验证。</p>
      <p>2. 总持仓不叠加：多个策略同时触发时执行组合调度器保留下来的单一交易。</p>
      <p>3. 任何新增过滤器、止损、止盈、仓位规则都必须重新生成候选审计、组合排名和 walk-forward 表。</p>
      <p>4. 正式前必须补严格成交模型：不允许进场 K 线内止盈/止损，并用更高成本和 tick replay 压力测试。</p>
    </section>
    <section>
      <h2>数据来源</h2>
      <ul class="sources">{source_items}</ul>
    </section>
  </main>
</body>
</html>
"""


def write_outputs(args: argparse.Namespace) -> dict[str, object]:
    audit = load_audit_metadata(args.audit)
    trades = load_trade_pool(args, audit)
    candidates = candidate_rows(audit, trades)
    results = evaluate_combinations(trades, candidates, audit, args)
    best = select_best(results)
    ranking = results_frame(results)
    walk_forward = walk_forward_years(trades, candidates, audit, args)
    generated_at = args.generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    source_paths = {
        "audit": args.audit,
        "regime_trades": args.regime_trades,
        "ofs_trades": args.ofs_trades,
        "screenshot_trades": args.screenshot_trades,
    }
    html_text = build_html(
        best=best,
        ranking=ranking,
        candidates=candidates,
        walk_forward=walk_forward,
        generated_at=generated_at,
        source_paths=source_paths,
    )
    for output_path, frame in [
        (Path(args.selected_trades_output), best.trades),
        (Path(args.dropped_trades_output), best.dropped_trades),
        (Path(args.ranking_output), ranking),
        (Path(args.components_output), candidates),
        (Path(args.walkforward_output), walk_forward),
    ]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output_path, index=False)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(html_text, encoding="utf-8")
    summary = {
        "report": str(report_path),
        "selected_trades_output": args.selected_trades_output,
        "ranking_output": args.ranking_output,
        "components_output": args.components_output,
        "walkforward_output": args.walkforward_output,
        "best_combo": best.name,
        "best_labels": list(best.labels),
        "best_eligibility": best.eligibility,
        "best_metrics": best.metrics,
        "combo_count": int(len(results)),
        "candidate_count": int(len(candidates)),
    }
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Optimize a diversified NQ multi-strategy composite.")
    parser.add_argument("--audit", default=".tmp/nq-long-term-strategy-candidate-audit.csv")
    parser.add_argument("--regime-trades", default=".tmp/nq-regime-transition-readiness-trades.csv")
    parser.add_argument("--ofs-trades", default=".tmp/nq-ofs-candidate-pressure-trades.csv")
    parser.add_argument("--screenshot-trades", default=".tmp/nq-screenshot-smc-candidate-pressure-trades.csv")
    parser.add_argument("--report", default="reports/NQ-multi-strategy-composite-optimizer.html")
    parser.add_argument("--selected-trades-output", default=".tmp/nq-multi-strategy-composite-selected-trades.csv")
    parser.add_argument("--dropped-trades-output", default=".tmp/nq-multi-strategy-composite-dropped-trades.csv")
    parser.add_argument("--ranking-output", default=".tmp/nq-multi-strategy-composite-ranking.csv")
    parser.add_argument("--components-output", default=".tmp/nq-multi-strategy-composite-components.csv")
    parser.add_argument("--walkforward-output", default=".tmp/nq-multi-strategy-composite-walkforward.csv")
    parser.add_argument("--max-combo-size", type=int, default=4)
    parser.add_argument("--max-per-family", type=int, default=1)
    parser.add_argument("--min-train-years", type=int, default=3)
    parser.add_argument("--min-train-trades", type=int, default=20)
    parser.add_argument("--rank-on-common-window", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--generated-at", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    print(json.dumps(write_outputs(args), ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
