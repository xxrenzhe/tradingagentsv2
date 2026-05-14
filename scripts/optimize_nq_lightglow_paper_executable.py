from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from generate_nq_lightglow_composite_report import (
    candlestick_svg,
    fmt_pct,
    fmt_signed,
    html_table,
    line_svg,
    load_bars,
    profit_factor,
    read_trades,
    summarize_trades,
)
from generate_nq_lightglow_paper_readiness_report import LIGHTGLOW_SOURCE


DEFAULT_TRADES = ".tmp/nq-composite-with-lightglow-selected.csv"
DEFAULT_BARS = ".tmp/nq-2020-final-report-bars.pkl"
DEFAULT_REPORT = "reports/NQ-lightglow-paper-executable-optimization.html"
DEFAULT_MARKDOWN = "reports/NQ-lightglow-paper-executable-optimization.md"
DEFAULT_FILTERS = ".tmp/nq-lightglow-paper-executable-filter-results.csv"
DEFAULT_TRADES_OUTPUT = ".tmp/nq-lightglow-paper-executable-optimized-trades.csv"
DEFAULT_SUMMARY = ".tmp/nq-lightglow-paper-executable-optimization-summary.json"
DEFAULT_PAPER_CONFIG = "reports/NQ-lightglow-paper-executable-paper-config.json"
PAPER_STRATEGY_ID = "nq_lightglow_paper_executable_avoid_long_below_ema60_trend"
PAPER_SELECTED_ALIAS = "lightglow_avoid_long_ema60"


@dataclass(frozen=True)
class FilterRule:
    name: str
    description: str
    family: str
    min_keep_rate: float = 0.35


@dataclass(frozen=True)
class OptimizationWindow:
    train_start: int
    train_end: int
    test_year: int

    @property
    def label(self) -> str:
        return f"{self.train_start}-{self.train_end}->{self.test_year}"

    @property
    def train_years(self) -> list[int]:
        return list(range(self.train_start, self.train_end + 1))


WINDOWS = (
    OptimizationWindow(2022, 2022, 2023),
    OptimizationWindow(2022, 2023, 2024),
    OptimizationWindow(2022, 2024, 2025),
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


def load_lightglow_trades(path: str | Path) -> pd.DataFrame:
    trades = read_trades(path)
    frame = trades[trades["strategy_source"].astype(str).eq(LIGHTGLOW_SOURCE)].copy()
    if frame.empty:
        return frame
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    frame["exit_ts"] = pd.to_datetime(frame["exit_ts"], utc=True)
    frame["year"] = frame["entry_ts"].dt.year.astype(int)
    frame["risk_weight"] = 1.0
    for column in numeric_context_columns():
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values("entry_ts").reset_index(drop=True)


def numeric_context_columns() -> list[str]:
    return [
        "direction",
        "net_points",
        "gross_points",
        "z_30",
        "momentum_5",
        "momentum_15",
        "momentum_60",
        "vol_30",
        "vol_120",
        "atr_ratio",
        "ema20_slope_10",
        "trend_ema20_60",
        "trend_ema60_200",
        "dist_ema20",
        "dist_ema60",
        "range_atr",
        "box45_width_atr",
        "box45_pos",
        "hour",
        "minute",
    ]


def candidate_rules() -> list[FilterRule]:
    return [
        FilterRule("baseline", "No filter; Lightglow-only paper-executable baseline.", "baseline", min_keep_rate=1.0),
        FilterRule("avoid_long_below_ema60_trend", "Avoid long when price is below EMA60 and medium trend is down.", "avoid_long"),
        FilterRule("avoid_short_above_ema60_trend", "Avoid short when price is above EMA60 and medium trend is up.", "avoid_short"),
        FilterRule("trade_with_ema20_slope", "Only trade in the direction of EMA20 slope.", "trend_confirm"),
        FilterRule("trade_with_ema20_60_trend", "Only trade in the direction of EMA20-EMA60 trend.", "trend_confirm"),
        FilterRule("avoid_extreme_countertrend", "Avoid longs in strong negative momentum and shorts in strong positive momentum.", "avoid_countertrend"),
        FilterRule("avoid_chasing_far_from_ema20", "Avoid entries extended more than roughly 2 ATR from EMA20.", "location"),
        FilterRule("premium_discount_location", "Longs only below upper range half and shorts only above lower range half.", "location"),
        FilterRule("balanced_box_location", "Avoid entries outside the prior 45m box extremes.", "location"),
        FilterRule("rth_only", "Keep RTH-like 14:30-21:00 UTC entries only.", "session", min_keep_rate=0.25),
        FilterRule("avoid_opening_noise", "Skip first 15 minutes around RTH open.", "session", min_keep_rate=0.25),
        FilterRule("low_mid_volatility", "Keep low/mid ATR ratio states.", "volatility"),
        FilterRule("high_relative_volume", "Keep trades with vol_30 above vol_120.", "volume_price"),
        FilterRule("trend_location_combo", "Require trend direction and avoid stretched location.", "combo", min_keep_rate=0.25),
    ]


def rule_mask(frame: pd.DataFrame, rule_name: str) -> pd.Series:
    index = frame.index
    direction = pd.to_numeric(frame.get("direction"), errors="coerce").fillna(0.0)
    dist_ema60 = pd.to_numeric(frame.get("dist_ema60"), errors="coerce").fillna(0.0)
    dist_ema20 = pd.to_numeric(frame.get("dist_ema20"), errors="coerce").fillna(0.0)
    trend_20_60 = pd.to_numeric(frame.get("trend_ema20_60"), errors="coerce").fillna(0.0)
    slope_20 = pd.to_numeric(frame.get("ema20_slope_10"), errors="coerce").fillna(0.0)
    momentum_60 = pd.to_numeric(frame.get("momentum_60"), errors="coerce").fillna(0.0)
    atr_ratio = pd.to_numeric(frame.get("atr_ratio"), errors="coerce").fillna(1.0)
    range_atr = pd.to_numeric(frame.get("range_atr"), errors="coerce").replace(0, pd.NA)
    box45_pos = pd.to_numeric(frame.get("box45_pos"), errors="coerce").fillna(0.5)
    hour = pd.to_numeric(frame.get("hour"), errors="coerce").fillna(-1)
    minute = pd.to_numeric(frame.get("minute"), errors="coerce").fillna(-1)
    vol_30 = pd.to_numeric(frame.get("vol_30"), errors="coerce").fillna(0.0)
    vol_120 = pd.to_numeric(frame.get("vol_120"), errors="coerce").fillna(0.0)

    if rule_name == "baseline":
        return pd.Series(True, index=index)
    if rule_name == "avoid_long_below_ema60_trend":
        return ~((direction > 0) & (dist_ema60 < 0) & (trend_20_60 < 0))
    if rule_name == "avoid_short_above_ema60_trend":
        return ~((direction < 0) & (dist_ema60 > 0) & (trend_20_60 > 0))
    if rule_name == "trade_with_ema20_slope":
        return ((direction > 0) & (slope_20 >= 0)) | ((direction < 0) & (slope_20 <= 0))
    if rule_name == "trade_with_ema20_60_trend":
        return ((direction > 0) & (trend_20_60 >= 0)) | ((direction < 0) & (trend_20_60 <= 0))
    if rule_name == "avoid_extreme_countertrend":
        return ~(((direction > 0) & (momentum_60 < -0.002)) | ((direction < 0) & (momentum_60 > 0.002)))
    if rule_name == "avoid_chasing_far_from_ema20":
        stretch = (dist_ema20.abs() / range_atr).fillna(0.0)
        return stretch <= 2.0
    if rule_name == "premium_discount_location":
        return ((direction > 0) & (box45_pos <= 0.75)) | ((direction < 0) & (box45_pos >= 0.25))
    if rule_name == "balanced_box_location":
        return box45_pos.between(-0.1, 1.1)
    if rule_name == "rth_only":
        return hour.between(14, 20)
    if rule_name == "avoid_opening_noise":
        return ~minute.between(870, 884)
    if rule_name == "low_mid_volatility":
        return atr_ratio <= 1.25
    if rule_name == "high_relative_volume":
        return vol_30 > vol_120
    if rule_name == "trend_location_combo":
        trend_ok = ((direction > 0) & (trend_20_60 >= 0)) | ((direction < 0) & (trend_20_60 <= 0))
        location_ok = box45_pos.between(-0.1, 1.1)
        stretch_ok = ((dist_ema20.abs() / range_atr).fillna(0.0) <= 2.0)
        return trend_ok & location_ok & stretch_ok
    raise ValueError(f"unknown rule: {rule_name}")


def metric_row(trades: pd.DataFrame, label: str) -> dict[str, Any]:
    summary = summarize_trades(trades)
    points = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0) if not trades.empty else pd.Series(dtype=float)
    monthly = points.groupby(trades["entry_ts"].dt.strftime("%Y-%m")).sum() if not trades.empty else pd.Series(dtype=float)
    rolling = points.groupby(trades["entry_ts"].dt.floor("D")).sum().rolling(90, min_periods=20).sum() if not trades.empty else pd.Series(dtype=float)
    return {
        "label": label,
        "trades": int(summary["trades"]),
        "net_points": summary["net_points"],
        "profit_factor": summary["profit_factor"],
        "win_rate": summary["win_rate"],
        "max_drawdown_points": summary["max_drawdown_points"],
        "net_to_drawdown": summary["net_to_drawdown"],
        "avg_points": summary["avg_points"],
        "worst_trade_points": summary.get("worst_trade_points", 0.0),
        "worst_month_points": float(monthly.min()) if not monthly.empty else 0.0,
        "worst_90d_points": float(rolling.min()) if not rolling.empty else 0.0,
    }


def apply_execution_stress(trades: pd.DataFrame, *, extra_cost_points: float = 0.0, latency_bars: int = 0) -> pd.DataFrame:
    frame = trades.copy()
    if frame.empty:
        return frame
    frame["net_points"] = pd.to_numeric(frame["net_points"], errors="coerce").fillna(0.0) - extra_cost_points
    if latency_bars:
        penalty = 0.25 * latency_bars
        frame["net_points"] = frame["net_points"] - penalty
        frame["execution_note"] = f"latency_{latency_bars}_bar_penalty_{penalty:g}"
    return frame


def evaluate_rule(train: pd.DataFrame, test: pd.DataFrame, rule: FilterRule) -> dict[str, Any]:
    train_base = metric_row(train, "train_base")
    test_base = metric_row(test, "test_base")
    train_keep = train.loc[rule_mask(train, rule.name)].copy()
    test_keep = test.loc[rule_mask(test, rule.name)].copy()
    train_metrics = metric_row(train_keep, "train_keep")
    test_metrics = metric_row(test_keep, "test_keep")
    train_keep_rate = len(train_keep) / len(train) if len(train) else 0.0
    test_keep_rate = len(test_keep) / len(test) if len(test) else 0.0
    train_delta = train_metrics["net_points"] - train_base["net_points"]
    test_delta = test_metrics["net_points"] - test_base["net_points"]
    selected = (
        rule.name != "baseline"
        and train_keep_rate >= rule.min_keep_rate
        and train_metrics["trades"] >= 200
        and train_delta > 0.0
        and train_metrics["profit_factor"] >= train_base["profit_factor"]
        and train_metrics["max_drawdown_points"] <= train_base["max_drawdown_points"]
    )
    return {
        "rule": rule.name,
        "family": rule.family,
        "description": rule.description,
        "selected_by_train": selected,
        "train_keep_rate": train_keep_rate,
        "test_keep_rate": test_keep_rate,
        "train_base_trades": train_base["trades"],
        "train_kept_trades": train_metrics["trades"],
        "train_base_net_points": train_base["net_points"],
        "train_kept_net_points": train_metrics["net_points"],
        "train_delta_net_points": train_delta,
        "train_base_profit_factor": train_base["profit_factor"],
        "train_kept_profit_factor": train_metrics["profit_factor"],
        "train_base_max_drawdown_points": train_base["max_drawdown_points"],
        "train_kept_max_drawdown_points": train_metrics["max_drawdown_points"],
        "test_base_trades": test_base["trades"],
        "test_kept_trades": test_metrics["trades"],
        "test_base_net_points": test_base["net_points"],
        "test_kept_net_points": test_metrics["net_points"],
        "test_delta_net_points": test_delta,
        "test_base_profit_factor": test_base["profit_factor"],
        "test_kept_profit_factor": test_metrics["profit_factor"],
        "test_base_max_drawdown_points": test_base["max_drawdown_points"],
        "test_kept_max_drawdown_points": test_metrics["max_drawdown_points"],
        "test_worst_trade_points": test_metrics["worst_trade_points"],
        "test_worst_90d_points": test_metrics["worst_90d_points"],
        "test_positive_oos": test_delta > 0 and test_metrics["profit_factor"] >= test_base["profit_factor"],
    }


def choose_rule(rows: list[dict[str, Any]]) -> str:
    candidates = [row for row in rows if row["selected_by_train"]]
    if not candidates:
        return "baseline"
    priority = {
        "avoid_long_below_ema60_trend": 0,
        "avoid_short_above_ema60_trend": 1,
        "avoid_extreme_countertrend": 2,
        "balanced_box_location": 3,
        "avoid_opening_noise": 4,
    }
    candidates.sort(
        key=lambda row: (
            -priority.get(str(row["rule"]), 99),
            row["train_kept_profit_factor"],
            row["train_delta_net_points"],
            -row["train_kept_max_drawdown_points"],
            row["train_kept_trades"],
        ),
        reverse=True,
    )
    return str(candidates[0]["rule"])


def walk_forward_optimize(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rules = candidate_rules()
    all_rows: list[dict[str, Any]] = []
    optimized_parts: list[pd.DataFrame] = []
    window_summary: list[dict[str, Any]] = []
    for window in WINDOWS:
        train = trades[trades["year"].isin(window.train_years)].copy()
        test = trades[trades["year"].eq(window.test_year)].copy()
        window_rows = []
        for rule in rules:
            row = evaluate_rule(train, test, rule)
            row["window"] = window.label
            row["train_start"] = window.train_start
            row["train_end"] = window.train_end
            row["test_year"] = window.test_year
            window_rows.append(row)
            all_rows.append(row)
        selected_rule = choose_rule(window_rows)
        selected_mask = rule_mask(test, selected_rule)
        selected_test = test.loc[selected_mask].copy()
        selected_test["selected_rule"] = selected_rule
        selected_test["optimization_window"] = window.label
        optimized_parts.append(selected_test)
        base = metric_row(test, "baseline")
        optimized = metric_row(selected_test, "optimized")
        window_summary.append(
            {
                "window": window.label,
                "selected_rule": selected_rule,
                "test_year": window.test_year,
                "base_trades": base["trades"],
                "optimized_trades": optimized["trades"],
                "base_net_points": base["net_points"],
                "optimized_net_points": optimized["net_points"],
                "delta_net_points": optimized["net_points"] - base["net_points"],
                "base_profit_factor": base["profit_factor"],
                "optimized_profit_factor": optimized["profit_factor"],
                "base_max_drawdown_points": base["max_drawdown_points"],
                "optimized_max_drawdown_points": optimized["max_drawdown_points"],
                "optimized_worst_90d_points": optimized["worst_90d_points"],
            }
        )
    optimized_trades = pd.concat(optimized_parts, ignore_index=True, sort=False) if optimized_parts else trades.iloc[0:0].copy()
    return pd.DataFrame(all_rows), pd.DataFrame(window_summary), optimized_trades


def stress_table(trades: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for cost in (0.0, 0.5, 1.5, 2.5, 4.375):
        stressed = apply_execution_stress(trades, extra_cost_points=cost)
        row = metric_row(stressed, f"extra_cost_{cost:g}")
        row["stress_type"] = "extra_cost"
        row["parameter"] = f"+{cost:g}_points"
        rows.append(row)
    for latency in (0, 1, 2, 3):
        stressed = apply_execution_stress(trades, latency_bars=latency)
        row = metric_row(stressed, f"latency_{latency}_bar")
        row["stress_type"] = "latency"
        row["parameter"] = f"{latency}_bar"
        rows.append(row)
    return pd.DataFrame(rows)


def promotion_decision(windows: pd.DataFrame, stress: pd.DataFrame, optimized: pd.DataFrame) -> dict[str, Any]:
    blockers: list[str] = []
    if optimized.empty:
        blockers.append("no_optimized_trades")
    if not windows.empty and float(windows["delta_net_points"].sum()) <= 0:
        blockers.append("walk_forward_filter_did_not_improve_net")
    if not windows.empty and (windows["delta_net_points"] < 0).any():
        blockers.append("one_or_more_future_years_net_degraded")
    if not windows.empty and (windows["optimized_profit_factor"] < windows["base_profit_factor"]).any():
        blockers.append("one_or_more_future_years_pf_degraded")
    if not windows.empty and (windows["optimized_max_drawdown_points"] > windows["base_max_drawdown_points"]).any():
        blockers.append("one_or_more_future_years_drawdown_degraded")
    stress_25 = stress[stress["parameter"].eq("+2.5_points")]
    if not stress_25.empty and float(stress_25["profit_factor"].iloc[0]) < 1.2:
        blockers.append("optimized_strategy_not_robust_to_plus_2_5_points")
    if not windows.empty and (windows["optimized_trades"] < 300).any():
        blockers.append("one_or_more_test_years_has_too_few_trades")
    status = "promote_to_paper_candidate" if not blockers else "research-only"
    return {
        "status": status,
        "blockers": blockers,
        "next_action": "export MNQ paper config" if not blockers else "keep baseline paper plan and continue filter research",
    }


def oos_baseline_trades(trades: pd.DataFrame, optimized: pd.DataFrame) -> pd.DataFrame:
    if optimized.empty:
        return trades.iloc[0:0].copy()
    years = sorted(pd.to_datetime(optimized["entry_ts"], utc=True).dt.year.unique().tolist())
    return trades[trades["year"].isin(years)].copy()


def prepare_paper_runner_trades(trades: pd.DataFrame) -> pd.DataFrame:
    frame = trades.copy()
    if frame.empty:
        return frame
    entry_ts = pd.to_datetime(frame["entry_ts"], utc=True)
    exit_ts = pd.to_datetime(frame["exit_ts"], utc=True)
    frame["trade_date"] = entry_ts.dt.date.astype(str)
    frame["portfolio_rule"] = PAPER_STRATEGY_ID
    frame["selected_alias"] = PAPER_SELECTED_ALIAS
    frame["strategy_name"] = PAPER_STRATEGY_ID
    frame["strategy_alias"] = PAPER_SELECTED_ALIAS
    frame["actual_entry_ts"] = entry_ts.astype(str)
    frame["holding_minutes"] = ((exit_ts - entry_ts).dt.total_seconds() / 60.0).round().astype(int)
    frame["source_timeframe_minutes"] = 1
    frame["source_signal"] = "lightglow_composite_action_map"
    frame["source_direction_mode"] = "selected_action"
    frame["timecell_mode"] = "shadow_only"
    frame["strategy_stop_points"] = pd.NA
    frame["strategy_target_points"] = pd.NA
    return frame


def best_worst_panels(title_prefix: str, trades: pd.DataFrame, bars: pd.DataFrame) -> str:
    if trades.empty:
        return '<p class="empty">No trades.</p>'
    best = trades.loc[trades["net_points"].idxmax()]
    worst = trades.loc[trades["net_points"].idxmin()]
    return trade_panel(f"{title_prefix} 最佳交易", best, bars) + trade_panel(f"{title_prefix} 最差交易", worst, bars)


def trade_panel(title: str, trade: pd.Series, bars: pd.DataFrame) -> str:
    entry_ts = pd.to_datetime(trade["entry_ts"], utc=True)
    exit_ts = pd.to_datetime(trade["exit_ts"], utc=True)
    start_pos = max(0, int(bars["ts"].searchsorted(entry_ts, side="left")) - 80)
    end_pos = min(len(bars), int(bars["ts"].searchsorted(exit_ts, side="left")) + 120)
    window = bars.iloc[start_pos:end_pos].reset_index(drop=True)
    meta = (
        f"{trade.get('strategy_source', LIGHTGLOW_SOURCE)} | rule={trade.get('selected_rule', 'baseline')} | "
        f"{entry_ts} -> {exit_ts} | net {fmt_signed(trade.get('net_points'))} pts"
    )
    return f"""
    <figure class="chart">
      <figcaption>{esc(title)}</figcaption>
      <p class="muted">{esc(meta)}</p>
      {candlestick_svg(window, trade)}
    </figure>
    """


def write_markdown(path: Path, decision: dict[str, Any], base_summary: dict[str, float], opt_summary: dict[str, float]) -> None:
    blockers = "\n".join(f"- `{item}`" for item in decision["blockers"]) or "- none"
    text = f"""# NQ Lightglow Paper-Executable Optimization

Status: `{decision['status']}`

This is a causal optimization of the paper-executable Lightglow-only subset. Timecell remains shadow-only.

## Result

- OOS baseline trades: `{base_summary['trades']:.0f}`, net `{base_summary['net_points']:.2f}`, PF `{base_summary['profit_factor']:.3f}`.
- Optimized trades: `{opt_summary['trades']:.0f}`, net `{opt_summary['net_points']:.2f}`, PF `{opt_summary['profit_factor']:.3f}`.
- Decision: `{decision['status']}`.

## Blockers

{blockers}

## Guardrails

- Filters are selected on train years only and applied to the next test year.
- No Timecell trades are included in executable performance.
- Paper execution remains dry-run first; submit requires explicit `--allow-timed-exit-submit` and paper-only timed-exit close management.
- This report does not approve live trading.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_html(
    path: Path,
    trades: pd.DataFrame,
    optimized: pd.DataFrame,
    filters: pd.DataFrame,
    windows: pd.DataFrame,
    stress: pd.DataFrame,
    decision: dict[str, Any],
    bars: pd.DataFrame,
    generated_at: str,
) -> None:
    baseline_oos = oos_baseline_trades(trades, optimized)
    base_summary = summarize_trades(baseline_oos)
    opt_summary = summarize_trades(optimized)
    selected_filters = filters[filters["selected_by_train"].astype(bool)].copy()
    top_filters = filters.sort_values(["test_positive_oos", "test_delta_net_points"], ascending=[False, False]).head(30)
    equity = pd.DataFrame({"x": range(1, len(optimized) + 1), "equity": optimized["net_points"].cumsum()})
    blockers = "".join(f"<li><code>{esc(item)}</code></li>" for item in decision["blockers"]) or "<li>none</li>"
    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>NQ Lightglow Paper-Executable Optimization</title>
  <style>
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:#f7f8fb; color:#111827; }}
    header, main {{ max-width:1180px; margin:0 auto; padding:28px; }}
    header {{ background:#101827; color:white; max-width:none; }}
    header > * {{ max-width:1180px; margin-left:auto; margin-right:auto; }}
    h1 {{ margin:0 0 8px; font-size:32px; }}
    h2 {{ margin-top:0; }}
    section {{ background:white; border:1px solid #e5e7eb; border-radius:8px; padding:22px; margin:18px 0; }}
    .subtitle, .muted {{ color:#64748b; }}
    header .subtitle {{ color:#cbd5e1; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin-top:18px; }}
    .metric {{ background:#f8fafc; border:1px solid #e5e7eb; border-radius:8px; padding:14px; }}
    header .metric {{ background:#172033; border-color:#2b3650; }}
    .metric small {{ display:block; color:#64748b; margin-bottom:6px; }}
    header .metric small {{ color:#9fb0c7; }}
    .metric strong {{ display:block; font-size:22px; }}
    .note {{ border-left:4px solid #2563eb; background:#eff6ff; padding:12px 14px; border-radius:6px; margin:12px 0; }}
    .risk {{ border-left-color:#dc2626; background:#fff1f2; }}
    table {{ border-collapse:collapse; width:100%; font-size:13px; }}
    th, td {{ border-bottom:1px solid #e5e7eb; padding:8px; text-align:left; vertical-align:top; }}
    th {{ background:#f8fafc; }}
    .table-wrap {{ overflow-x:auto; }}
    .chart {{ overflow-x:auto; }}
  </style>
</head>
<body>
  <header>
    <h1>NQ Lightglow Paper-Executable Optimization</h1>
    <p class="subtitle">只优化纸盘可执行 Lightglow 子集；Timecell 保持 shadow-only。所有过滤器均训练期选择，未来年验证。生成时间：{esc(generated_at)}</p>
    <div class="grid">
      <div class="metric"><small>决策</small><strong>{esc(decision['status'])}</strong><span>{esc(decision['next_action'])}</span></div>
      <div class="metric"><small>OOS Baseline 净点</small><strong>{fmt_signed(base_summary['net_points'])}</strong><span>PF {base_summary['profit_factor']:.3f}</span></div>
      <div class="metric"><small>Optimized 净点</small><strong>{fmt_signed(opt_summary['net_points'])}</strong><span>PF {opt_summary['profit_factor']:.3f}</span></div>
      <div class="metric"><small>Optimized 交易</small><strong>{opt_summary['trades']:.0f}</strong><span>Lightglow only</span></div>
    </div>
  </header>
  <main>
    <section>
      <h2>结论</h2>
      <div class="note risk">
        <p><strong>状态：</strong><code>{esc(decision['status'])}</code>。这不是实盘批准；只有当训练期选中的过滤器在未来测试年稳定改善，并通过成本/延迟压力，才允许升级为纸盘候选。</p>
        <p><strong>Blockers:</strong></p>
        <ul>{blockers}</ul>
      </div>
    </section>
    <section>
      <h2>Walk-Forward 过滤选择</h2>
      {html_table(windows, [("window", "窗口"), ("selected_rule", "训练选中规则"), ("base_trades", "基准交易"), ("optimized_trades", "优化交易"), ("base_net_points", "基准净点"), ("optimized_net_points", "优化净点"), ("delta_net_points", "净点变化"), ("base_profit_factor", "基准PF"), ("optimized_profit_factor", "优化PF"), ("base_max_drawdown_points", "基准DD"), ("optimized_max_drawdown_points", "优化DD"), ("optimized_worst_90d_points", "优化最差90日")])}
    </section>
    <section>
      <h2>训练选中规则明细</h2>
      {html_table(selected_filters, [("window", "窗口"), ("rule", "规则"), ("family", "类别"), ("train_keep_rate", "训练保留率"), ("train_delta_net_points", "训练提升"), ("train_kept_profit_factor", "训练PF"), ("test_keep_rate", "测试保留率"), ("test_delta_net_points", "测试提升"), ("test_kept_profit_factor", "测试PF"), ("test_positive_oos", "OOS正向"), ("description", "说明")])}
      <h3>过滤器排行榜</h3>
      {html_table(top_filters, [("window", "窗口"), ("rule", "规则"), ("family", "类别"), ("selected_by_train", "训练选中"), ("train_delta_net_points", "训练提升"), ("test_delta_net_points", "测试提升"), ("test_base_profit_factor", "测试基准PF"), ("test_kept_profit_factor", "测试过滤PF"), ("test_positive_oos", "OOS正向")], limit=30)}
    </section>
    <section>
      <h2>成本/延迟压力</h2>
      {html_table(stress, [("stress_type", "类型"), ("parameter", "参数"), ("trades", "交易数"), ("net_points", "净点"), ("profit_factor", "PF"), ("win_rate", "胜率"), ("max_drawdown_points", "最大DD"), ("worst_90d_points", "最差90日")])}
    </section>
    <section>
      <h2>优化后 K线样本</h2>
      {line_svg(equity, title="优化后 Lightglow 净点曲线")}
      {best_worst_panels("优化后 Lightglow", optimized, bars)}
    </section>
  </main>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    trades = load_lightglow_trades(args.trades)
    bars = load_bars(args.bars)
    filters, windows, optimized = walk_forward_optimize(trades)
    stress = stress_table(optimized)
    decision = promotion_decision(windows, stress, optimized)
    baseline_oos = oos_baseline_trades(trades, optimized)
    paper_trades = prepare_paper_runner_trades(optimized)
    generated_at = args.generated_at or pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    Path(args.filters_output).parent.mkdir(parents=True, exist_ok=True)
    filters.to_csv(args.filters_output, index=False)
    windows.to_csv(args.window_output, index=False)
    stress.to_csv(args.stress_output, index=False)
    paper_trades.to_csv(args.trades_output, index=False)
    write_html(Path(args.report), trades, optimized, filters, windows, stress, decision, bars, generated_at)
    write_markdown(Path(args.markdown), decision, summarize_trades(baseline_oos), summarize_trades(optimized))
    paper_config = paper_validation_config(args, decision)
    Path(args.paper_config_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.paper_config_output).write_text(
        json.dumps(paper_config, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    summary = {
        "decision": decision,
        "baseline_full": summarize_trades(trades),
        "baseline_oos": summarize_trades(baseline_oos),
        "optimized": summarize_trades(optimized),
        "filters_output": args.filters_output,
        "window_output": args.window_output,
        "stress_output": args.stress_output,
        "trades_output": args.trades_output,
        "report": args.report,
        "markdown": args.markdown,
        "paper_config": args.paper_config_output,
    }
    Path(args.summary_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary_output).write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return summary


def paper_validation_config(args: argparse.Namespace, decision: dict[str, Any]) -> dict[str, Any]:
    dry_run_command = (
        ".venv/bin/python scripts/run_lightglow_optimized_strategy_paper_trader.py "
        f"--trades {args.trades_output} --symbol MNQ --quantity 1 "
        "--contract-month 202606 --max-signal-age-minutes 10"
    )
    blocked_submit_command = dry_run_command + " --submit"
    timed_exit_submit_command = dry_run_command + " --submit --allow-timed-exit-submit"
    return {
        "strategy_id": PAPER_STRATEGY_ID,
        "status": decision["status"],
        "instrument": "MNQ",
        "quantity": 1,
        "trades_path": args.trades_output,
        "timecell_mode": "shadow_only",
        "selected_alias": PAPER_SELECTED_ALIAS,
        "selected_filter": "avoid_long_below_ema60_trend",
        "paper_phase": "dry_run_first",
        "dry_run_command": dry_run_command,
        "blocked_submit_command": blocked_submit_command,
        "timed_exit_submit_command": timed_exit_submit_command,
        "submit_blocker": "default --submit remains blocked unless the operator explicitly adds --allow-timed-exit-submit for paper-only managed time exits",
        "risk_controls": {
            "max_signal_age_minutes": 10,
            "max_position_contracts": 1,
            "daily_loss_halt_points": 50,
            "consecutive_loss_halt": 3,
            "paper_min_outcomes_before_review": 300,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Optimize the NQ Lightglow paper-executable strategy subset.")
    parser.add_argument("--trades", default=DEFAULT_TRADES)
    parser.add_argument("--bars", default=DEFAULT_BARS)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--markdown", default=DEFAULT_MARKDOWN)
    parser.add_argument("--filters-output", default=DEFAULT_FILTERS)
    parser.add_argument("--window-output", default=".tmp/nq-lightglow-paper-executable-window-results.csv")
    parser.add_argument("--stress-output", default=".tmp/nq-lightglow-paper-executable-stress.csv")
    parser.add_argument("--trades-output", default=DEFAULT_TRADES_OUTPUT)
    parser.add_argument("--summary-output", default=DEFAULT_SUMMARY)
    parser.add_argument("--paper-config-output", default=DEFAULT_PAPER_CONFIG)
    parser.add_argument("--generated-at", default="")
    args = parser.parse_args()
    print(json.dumps(run(args), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
