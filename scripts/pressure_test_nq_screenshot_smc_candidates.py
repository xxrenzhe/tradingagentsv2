from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from backtest_nq_market_feature_strategy_templates import (  # noqa: E402
    StrategyTemplate,
    build_template_trades,
    summarize_trades,
)
from discover_nq_tradeable_market_features import build_market_features, load_or_prepare_features  # noqa: E402
from pressure_test_nq_ofs_candidates import summarize_net  # noqa: E402
from tradingagents.backtesting.short_patterns import BacktestCosts  # noqa: E402


def candidate_specs() -> list[StrategyTemplate]:
    configs = [
        {
            "name": "rth_long_displacement_reclaim_rr1.5",
            "feature_id": "displacement_pullback_continuation_long_us_rth",
            "family": "smc_displacement_pullback",
            "direction": 1,
            "entry_mode": "reclaim_break",
            "stop_mode": "event_extreme",
            "reward_risk": 1.5,
            "horizon_minutes": 120,
            "confirm_bars": 2,
            "pullback_atr": 0.25,
            "stop_atr_mult": 1.5,
            "context_filter": "vwap_volume",
            "exit_mode": "bracket",
            "fast_fail_bars": 3,
        },
        {
            "name": "rth_long_displacement_confirm_rr1.25",
            "feature_id": "displacement_pullback_continuation_long_us_rth",
            "family": "smc_displacement_pullback",
            "direction": 1,
            "entry_mode": "confirm_break",
            "stop_mode": "event_extreme",
            "reward_risk": 1.25,
            "horizon_minutes": 120,
            "confirm_bars": 2,
            "pullback_atr": 0.25,
            "stop_atr_mult": 1.5,
            "context_filter": "trend_vwap_volume",
            "exit_mode": "bracket_fast_fail",
            "fast_fail_bars": 5,
        },
        {
            "name": "rth_long_bos_stair_confirm_rr1.5",
            "feature_id": "bos_stair_step_continuation_long_us_rth",
            "family": "smc_bos_continuation",
            "direction": 1,
            "entry_mode": "confirm_break",
            "stop_mode": "event_extreme",
            "reward_risk": 1.5,
            "horizon_minutes": 120,
            "confirm_bars": 2,
            "pullback_atr": 0.25,
            "stop_atr_mult": 1.5,
            "context_filter": "trend_vwap_volume",
            "exit_mode": "bracket",
            "fast_fail_bars": 3,
        },
        {
            "name": "rth_long_bos_stair_midpoint_rr1.25",
            "feature_id": "bos_stair_step_continuation_long_us_rth",
            "family": "smc_bos_continuation",
            "direction": 1,
            "entry_mode": "midpoint_hold",
            "stop_mode": "event_extreme",
            "reward_risk": 1.25,
            "horizon_minutes": 120,
            "confirm_bars": 3,
            "pullback_atr": 0.25,
            "stop_atr_mult": 1.5,
            "context_filter": "vwap_volume",
            "exit_mode": "bracket_fast_fail",
            "fast_fail_bars": 5,
        },
        {
            "name": "rth_long_eql_sweep_reclaim_rr1.25",
            "feature_id": "eql_sweep_macd_reversal_long_us_rth",
            "family": "smc_liquidity_macd_reversal",
            "direction": 1,
            "entry_mode": "reclaim_break",
            "stop_mode": "event_extreme",
            "reward_risk": 1.25,
            "horizon_minutes": 120,
            "confirm_bars": 2,
            "pullback_atr": 0.25,
            "stop_atr_mult": 1.5,
            "context_filter": "vwap_volume",
            "exit_mode": "bracket",
            "fast_fail_bars": 3,
        },
        {
            "name": "rth_short_eqh_sweep_reject_rr1",
            "feature_id": "eqh_sweep_macd_reversal_short_us_rth",
            "family": "smc_liquidity_macd_reversal",
            "direction": -1,
            "entry_mode": "reclaim_break",
            "stop_mode": "event_extreme",
            "reward_risk": 1.0,
            "horizon_minutes": 60,
            "confirm_bars": 2,
            "pullback_atr": 0.25,
            "stop_atr_mult": 1.5,
            "context_filter": "vwap_volume",
            "exit_mode": "bracket_fast_fail",
            "fast_fail_bars": 3,
        },
        {
            "name": "rth_short_displacement_reject_rr1",
            "feature_id": "displacement_pullback_continuation_short_us_rth",
            "family": "smc_displacement_pullback",
            "direction": -1,
            "entry_mode": "confirm_break",
            "stop_mode": "event_extreme",
            "reward_risk": 1.0,
            "horizon_minutes": 60,
            "confirm_bars": 2,
            "pullback_atr": 0.25,
            "stop_atr_mult": 1.5,
            "context_filter": "vwap_volume",
            "exit_mode": "bracket_fast_fail",
            "fast_fail_bars": 3,
        },
        {
            "name": "rth_short_bos_stair_confirm_rr1",
            "feature_id": "bos_stair_step_continuation_short_us_rth",
            "family": "smc_bos_continuation",
            "direction": -1,
            "entry_mode": "confirm_break",
            "stop_mode": "event_extreme",
            "reward_risk": 1.0,
            "horizon_minutes": 60,
            "confirm_bars": 2,
            "pullback_atr": 0.25,
            "stop_atr_mult": 1.5,
            "context_filter": "vwap_volume",
            "exit_mode": "bracket_fast_fail",
            "fast_fail_bars": 3,
        },
    ]
    return [StrategyTemplate(**config, breakeven_trigger_r=0.75, partial_fraction=0.5) for config in configs]


def evaluate_candidates(features: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    market_features = {feature.feature_id: feature for feature in build_market_features(features)}
    rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    trade_frames: list[pd.DataFrame] = []
    costs = BacktestCosts()
    for template in candidate_specs():
        feature = market_features[template.feature_id]
        trades = build_template_trades(
            features,
            feature,
            template,
            costs=costs,
            min_gap_minutes=args.min_gap_minutes,
            min_stop_points=args.min_stop_points,
            max_stop_points=args.max_stop_points,
            stop_buffer_atr=args.stop_buffer_atr,
            min_buffer_points=args.min_buffer_points,
        )
        if not trades.empty:
            trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
            trade_frames.append(trades)
        yearly = yearly_summary(template, trades)
        rolling = rolling_summary(template, trades, args.rolling_days, args.rolling_step_days)
        yearly_rows.extend(yearly.to_dict(orient="records"))
        rolling_rows.extend(rolling.to_dict(orient="records"))
        summary = summarize_trades(trades)
        stress = cost_stress_summary(trades, costs, args.cost_multipliers)
        rolling_net = pd.to_numeric(rolling["net_points"], errors="coerce") if not rolling.empty else pd.Series(dtype=float)
        rows.append(
            {
                "template": template.name,
                **template.__dict__,
                **summary,
                **stress,
                "year_count": int(yearly["year"].nunique()) if not yearly.empty else 0,
                "positive_year_rate": float((pd.to_numeric(yearly["net_points"], errors="coerce") > 0).mean())
                if not yearly.empty
                else 0.0,
                "min_year_net_points": float(pd.to_numeric(yearly["net_points"], errors="coerce").min())
                if not yearly.empty
                else 0.0,
                "rolling_window_count": int(len(rolling)),
                "positive_rolling_rate": float((rolling_net > 0).mean()) if not rolling_net.empty else 0.0,
                "min_rolling_net_points": float(rolling_net.min()) if not rolling_net.empty else 0.0,
            }
        )
    full = pd.DataFrame(rows)
    if not full.empty:
        full["pressure_score"] = (
            full["net_points"] / full["max_drawdown_points"].clip(lower=1.0)
            + full["avg_points"] * 8.0
            + full["positive_year_rate"] * 6.0
            + full["positive_rolling_rate"] * 4.0
            + (full.get("cost_2x_profit_factor", 0.0) - 1.0).clip(lower=-1.0) * 3.0
        )
        full = full.sort_values(["pressure_score", "profit_factor", "net_points"], ascending=[False, False, False])
    trades_all = pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame()
    return full, pd.DataFrame(yearly_rows), pd.DataFrame(rolling_rows), trades_all


def yearly_summary(template: StrategyTemplate, trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    frame = trades.copy()
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    frame["year"] = frame["entry_ts"].dt.year
    for year, group in frame.groupby("year"):
        rows.append({"template": template.name, "year": int(year), **summarize_trades(group)})
    return pd.DataFrame(rows)


def rolling_summary(template: StrategyTemplate, trades: pd.DataFrame, window_days: int, step_days: int) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    frame = trades.copy()
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    start = frame["entry_ts"].min().normalize()
    end = frame["entry_ts"].max().normalize() + pd.Timedelta(days=1)
    cursor = start
    while cursor + pd.Timedelta(days=window_days) <= end:
        stop = cursor + pd.Timedelta(days=window_days)
        selected = frame[(frame["entry_ts"] >= cursor) & (frame["entry_ts"] < stop)]
        if len(selected) >= 5:
            rows.append({"template": template.name, "start": str(cursor.date()), "end": str(stop.date()), **summarize_trades(selected)})
        cursor += pd.Timedelta(days=step_days)
    return pd.DataFrame(rows)


def cost_stress_summary(trades: pd.DataFrame, base_costs: BacktestCosts, multipliers: list[float]) -> dict[str, float]:
    gross = pd.to_numeric(trades["gross_points"], errors="coerce").dropna() if not trades.empty else pd.Series(dtype=float)
    out: dict[str, float] = {}
    for multiplier in multipliers:
        net = gross - base_costs.round_trip_cost_points * float(multiplier)
        summary = summarize_net(net)
        prefix = f"cost_{multiplier:g}x"
        out[f"{prefix}_net_points"] = summary["net_points"]
        out[f"{prefix}_profit_factor"] = summary["profit_factor"]
        out[f"{prefix}_win_rate"] = summary["win_rate"]
        out[f"{prefix}_avg_points"] = summary["avg_points"]
        out[f"{prefix}_max_drawdown_points"] = summary["max_drawdown_points"]
    return out


def write_report(path: Path, full: pd.DataFrame, yearly: pd.DataFrame, rolling: pd.DataFrame, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "features_cache": args.features_cache,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "candidate_count": int(len(full)),
        "cost_multipliers": args.cost_multipliers,
        "top": full.iloc[0].to_dict() if not full.empty else None,
        "screenshot_readout": screenshot_readout(),
    }
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>NQ Screenshot SMC Candidate Pressure Test</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #172026; }}
    h1, h2 {{ margin: 0 0 12px; }}
    section {{ margin: 22px 0; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 6px 8px; vertical-align: top; }}
    th {{ background: #f6f8fa; text-align: left; position: sticky; top: 0; }}
    pre {{ white-space: pre-wrap; background: #0f1720; color: #e6edf3; padding: 14px; border-radius: 6px; overflow: auto; }}
  </style>
</head>
<body>
  <h1>NQ 截图 SMC/动量候选策略压力测试</h1>
  <section><pre>{html.escape(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))}</pre></section>
  <section><h2>Candidate Ranking</h2>{html_table(full)}</section>
  <section><h2>Yearly Stability</h2>{html_table(yearly)}</section>
  <section><h2>Rolling Windows</h2>{html_table(rolling)}</section>
</body>
</html>
""",
        encoding="utf-8",
    )


def screenshot_readout() -> list[dict[str, str]]:
    return [
        {
            "feature": "BOS stair-step trend continuation",
            "trade": "顺着连续 BOS 的方向，等回踩不破 VWAP/EMA 后再突破入场。",
            "risk": "如果回踩突破原位移/结构起点，趋势延续假设失效。",
        },
        {
            "feature": "EQL/EQH liquidity sweep with MACD repair/fade",
            "trade": "扫等低/等高后收回区间，MACD histogram 修复/转弱，等待中点收复/跌破确认。",
            "risk": "价格接受在扫荡极值外侧时退出。",
        },
        {
            "feature": "Displacement pullback continuation",
            "trade": "位移 BOS 后第一次回踩 FVG/OB/需求供给区，重新突破时参与。",
            "risk": "回踩过深或不能快速再突破，说明位移被消化。",
        },
    ]


def html_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    display = frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.4f}")
    return display.to_html(index=False, escape=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pressure test screenshot-derived NQ SMC/momentum candidates.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--bars-cache", default=".tmp/nq-market-feature-bars-2020-cache.pkl")
    parser.add_argument("--features-cache", default=".tmp/nq-market-feature-features-2020-cache.pkl")
    parser.add_argument("--source-csv")
    parser.add_argument("--source-zip")
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--rebuild-features", action="store_true")
    parser.add_argument("--full-output", default=".tmp/nq-screenshot-smc-candidate-pressure-full.csv")
    parser.add_argument("--yearly-output", default=".tmp/nq-screenshot-smc-candidate-pressure-yearly.csv")
    parser.add_argument("--rolling-output", default=".tmp/nq-screenshot-smc-candidate-pressure-rolling.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-screenshot-smc-candidate-pressure-trades.csv")
    parser.add_argument("--report", default="reports/NQ-screenshot-smc-candidate-pressure-test-2020.html")
    parser.add_argument("--cost-multipliers", type=float, nargs="+", default=[1.0, 2.0, 3.0])
    parser.add_argument("--rolling-days", type=int, default=180)
    parser.add_argument("--rolling-step-days", type=int, default=90)
    parser.add_argument("--min-gap-minutes", type=int, default=15)
    parser.add_argument("--min-stop-points", type=float, default=4.0)
    parser.add_argument("--max-stop-points", type=float, default=100.0)
    parser.add_argument("--stop-buffer-atr", type=float, default=0.10)
    parser.add_argument("--min-buffer-points", type=float, default=0.25)
    args = parser.parse_args()

    features = load_or_prepare_features(args)
    full, yearly, rolling, trades = evaluate_candidates(features, args)
    for output, frame in [
        (Path(args.full_output), full),
        (Path(args.yearly_output), yearly),
        (Path(args.rolling_output), rolling),
        (Path(args.trades_output), trades),
    ]:
        output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output, index=False)
    write_report(Path(args.report), full, yearly, rolling, args)
    print(
        json.dumps(
            {
                "candidates": int(len(full)),
                "yearly_rows": int(len(yearly)),
                "rolling_rows": int(len(rolling)),
                "trades": int(len(trades)),
                "full_output": args.full_output,
                "yearly_output": args.yearly_output,
                "rolling_output": args.rolling_output,
                "trades_output": args.trades_output,
                "report": args.report,
                "top": full.iloc[0].to_dict() if not full.empty else None,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
