from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
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
from discover_nq_tradeable_market_features import build_market_features  # noqa: E402
from tradingagents.backtesting.short_patterns import BacktestCosts  # noqa: E402


def candidate_specs() -> list[StrategyTemplate]:
    base = {
        "feature_id": "ict_bullish_order_flow_shift_setup_us_rth",
        "family": "ict_order_flow_shift",
        "direction": 1,
        "entry_mode": "pullback_reclaim",
        "stop_mode": "event_extreme",
        "horizon_minutes": 60,
        "pullback_atr": 0.25,
        "stop_atr_mult": 1.5,
        "exit_mode": "bracket",
        "fast_fail_bars": 3,
        "breakeven_trigger_r": 0.5,
    }
    configs = [
        ("baseline_all_rr1.5_c3", "all", 1.5, 3),
        ("rth_open_rr1.75_c3", "rth_open", 1.75, 3),
        ("rth_open_rr1.75_c2", "rth_open", 1.75, 2),
        ("high_relative_volume_rr1.5_c2", "high_relative_volume", 1.5, 2),
        ("high_relative_volume_rr1.5_c3", "high_relative_volume", 1.5, 3),
        ("open_trend_volume_rr1.75_c3", "open_trend_volume", 1.75, 3),
        ("atr_expanding_rr1.5_c2", "atr_expanding", 1.5, 2),
    ]
    return [
        StrategyTemplate(
            name=name,
            context_filter=context,
            reward_risk=rr,
            confirm_bars=confirm,
            **base,
        )
        for name, context, rr, confirm in configs
    ]


def load_features(path: Path) -> pd.DataFrame:
    payload = pd.read_pickle(path)
    frame = payload["features"] if isinstance(payload, dict) and "features" in payload else payload
    out = frame.copy()
    out["ts"] = pd.to_datetime(out["ts"], utc=True)
    return out


def evaluate_candidates(features: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    market_features = {feature.feature_id: feature for feature in build_market_features(features)}
    templates = candidate_specs()
    costs = BacktestCosts()
    rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []

    for template in templates:
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
        if trades.empty:
            rows.append({"template": template.name, **template.__dict__, **summarize_trades(trades)})
            continue
        trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
        summary = summarize_trades(trades)
        stress = cost_stress_summary(trades, costs, args.cost_multipliers)
        year_frame = yearly_summary(template, trades, args.cost_multipliers, costs)
        rolling_frame = rolling_summary(template, trades, args.rolling_days, args.rolling_step_days)
        yearly_rows.extend(year_frame.to_dict(orient="records"))
        rolling_rows.extend(rolling_frame.to_dict(orient="records"))
        rolling_net = pd.to_numeric(rolling_frame["net_points"], errors="coerce") if not rolling_frame.empty else pd.Series(dtype=float)
        rows.append(
            {
                "template": template.name,
                **template.__dict__,
                **summary,
                **stress,
                "year_count": int(year_frame["year"].nunique()) if not year_frame.empty else 0,
                "positive_year_rate": float((pd.to_numeric(year_frame["net_points"], errors="coerce") > 0).mean())
                if not year_frame.empty
                else 0.0,
                "min_year_net_points": float(pd.to_numeric(year_frame["net_points"], errors="coerce").min())
                if not year_frame.empty
                else 0.0,
                "rolling_window_count": int(len(rolling_frame)),
                "positive_rolling_rate": float((rolling_net > 0).mean()) if not rolling_net.empty else 0.0,
                "min_rolling_net_points": float(rolling_net.min()) if not rolling_net.empty else 0.0,
                "pressure_score": pressure_score(summary, stress, year_frame, rolling_frame),
            }
        )
    full = pd.DataFrame(rows).sort_values(
        ["pressure_score", "profit_factor", "net_points"],
        ascending=[False, False, False],
    )
    return full, pd.DataFrame(yearly_rows), pd.DataFrame(rolling_rows)


def cost_stress_summary(trades: pd.DataFrame, base_costs: BacktestCosts, multipliers: list[float]) -> dict[str, float]:
    gross = pd.to_numeric(trades["gross_points"], errors="coerce").dropna()
    out: dict[str, float] = {}
    for multiplier in multipliers:
        cost = base_costs.round_trip_cost_points * float(multiplier)
        net = gross - cost
        summary = summarize_net(net)
        prefix = f"cost_{multiplier:g}x"
        out[f"{prefix}_net_points"] = summary["net_points"]
        out[f"{prefix}_profit_factor"] = summary["profit_factor"]
        out[f"{prefix}_win_rate"] = summary["win_rate"]
        out[f"{prefix}_avg_points"] = summary["avg_points"]
        out[f"{prefix}_max_drawdown_points"] = summary["max_drawdown_points"]
    return out


def yearly_summary(
    template: StrategyTemplate,
    trades: pd.DataFrame,
    multipliers: list[float],
    base_costs: BacktestCosts,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    frame = trades.copy()
    frame["year"] = frame["entry_ts"].dt.year
    for year, group in frame.groupby("year"):
        row = {"template": template.name, "context_filter": template.context_filter, "year": int(year), **summarize_trades(group)}
        gross = pd.to_numeric(group["gross_points"], errors="coerce")
        for multiplier in multipliers:
            row[f"cost_{multiplier:g}x_net_points"] = float((gross - base_costs.round_trip_cost_points * multiplier).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def rolling_summary(
    template: StrategyTemplate,
    trades: pd.DataFrame,
    window_days: int,
    step_days: int,
) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    start = trades["entry_ts"].min().normalize()
    end = trades["entry_ts"].max().normalize() + pd.Timedelta(days=1)
    cursor = start
    while cursor + pd.Timedelta(days=window_days) <= end:
        window_end = cursor + pd.Timedelta(days=window_days)
        window = trades[(trades["entry_ts"] >= cursor) & (trades["entry_ts"] < window_end)]
        if len(window) >= 5:
            rows.append(
                {
                    "template": template.name,
                    "context_filter": template.context_filter,
                    "start": str(cursor.date()),
                    "end": str(window_end.date()),
                    **summarize_trades(window),
                }
            )
        cursor += pd.Timedelta(days=step_days)
    return pd.DataFrame(rows)


def summarize_net(net: pd.Series) -> dict[str, float]:
    if net.empty:
        return {
            "net_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_points": 0.0,
            "max_drawdown_points": 0.0,
        }
    wins = net[net > 0]
    losses = net[net < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    return {
        "net_points": float(net.sum()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else (999.0 if gross_profit > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "avg_points": float(net.mean()),
        "max_drawdown_points": float(drawdown.max()) if not drawdown.empty else 0.0,
    }


def pressure_score(
    summary: dict[str, float],
    stress: dict[str, float],
    yearly: pd.DataFrame,
    rolling: pd.DataFrame,
) -> float:
    dd = max(float(summary["max_drawdown_points"]), 1.0)
    yearly_net = pd.to_numeric(yearly["net_points"], errors="coerce") if not yearly.empty else pd.Series(dtype=float)
    rolling_net = pd.to_numeric(rolling["net_points"], errors="coerce") if not rolling.empty else pd.Series(dtype=float)
    positive_year_rate = float((yearly_net > 0).mean()) if not yearly_net.empty else 0.0
    positive_rolling_rate = float((rolling_net > 0).mean()) if not rolling_net.empty else 0.0
    stress_pf = float(stress.get("cost_2x_profit_factor", 0.0))
    return float(
        float(summary["net_points"]) / dd
        + 8.0 * float(summary["avg_points"])
        + 6.0 * positive_year_rate
        + 4.0 * positive_rolling_rate
        + 3.0 * max(stress_pf - 1.0, -1.0)
    )


def write_report(path: Path, full: pd.DataFrame, yearly: pd.DataFrame, rolling: pd.DataFrame, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "features_cache": args.features_cache,
        "cost_multipliers": args.cost_multipliers,
        "rolling_days": args.rolling_days,
        "rolling_step_days": args.rolling_step_days,
        "top_template": full.iloc[0].to_dict() if not full.empty else None,
    }
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>NQ OFS Candidate Pressure Test</title>
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
  <h1>NQ OFS 候选策略压力测试</h1>
  <section><pre>{html.escape(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))}</pre></section>
  <section><h2>Candidate Ranking</h2>{html_table(full)}</section>
  <section><h2>Yearly Stability</h2>{html_table(yearly)}</section>
  <section><h2>Rolling Windows</h2>{html_table(rolling)}</section>
</body>
</html>
""",
        encoding="utf-8",
    )


def html_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    display = frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.4f}")
    return display.to_html(index=False, escape=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pressure test selected NQ OFS candidates.")
    parser.add_argument("--features-cache", default=".tmp/nq-market-feature-features-ofs-2020.pkl")
    parser.add_argument("--full-output", default=".tmp/nq-ofs-candidate-pressure-full.csv")
    parser.add_argument("--yearly-output", default=".tmp/nq-ofs-candidate-pressure-yearly.csv")
    parser.add_argument("--rolling-output", default=".tmp/nq-ofs-candidate-pressure-rolling.csv")
    parser.add_argument("--report", default="reports/NQ-ofs-candidate-pressure-test-2020.html")
    parser.add_argument("--cost-multipliers", type=float, nargs="+", default=[1.0, 2.0, 3.0])
    parser.add_argument("--rolling-days", type=int, default=180)
    parser.add_argument("--rolling-step-days", type=int, default=90)
    parser.add_argument("--min-gap-minutes", type=int, default=15)
    parser.add_argument("--min-stop-points", type=float, default=4.0)
    parser.add_argument("--max-stop-points", type=float, default=100.0)
    parser.add_argument("--stop-buffer-atr", type=float, default=0.10)
    parser.add_argument("--min-buffer-points", type=float, default=0.25)
    args = parser.parse_args()

    features = load_features(Path(args.features_cache))
    full, yearly, rolling = evaluate_candidates(features, args)
    for path, frame in [
        (Path(args.full_output), full),
        (Path(args.yearly_output), yearly),
        (Path(args.rolling_output), rolling),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    write_report(Path(args.report), full, yearly, rolling, args)
    print(
        json.dumps(
            {
                "candidates": int(len(full)),
                "yearly_rows": int(len(yearly)),
                "rolling_rows": int(len(rolling)),
                "full_output": args.full_output,
                "yearly_output": args.yearly_output,
                "rolling_output": args.rolling_output,
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
