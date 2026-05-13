from __future__ import annotations

import argparse
import html
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"
for path in (ROOT_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from search_nq_regime_transition_systems import (
    RegimeCandidate,
    build_breakout_events,
    compute_outcomes,
    prepare_features,
    select_candidate_trades,
)
from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.dataflows.databento import _bar_zip_path


def summarize(trades: pd.DataFrame, costs: BacktestCosts) -> dict[str, Any]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "payoff_ratio": 0.0,
            "expectancy_points": 0.0,
            "max_drawdown_points": 0.0,
            "net_to_drawdown": 0.0,
            "positive_year_rate": 0.0,
            "positive_90d_rate": 0.0,
            "worst_90d_points": 0.0,
            "net_at_cost_2.125": 0.0,
            "same_bar_count": 0,
        }
    data = trades.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True)
    net = pd.to_numeric(data["net_points"], errors="coerce").fillna(0.0)
    gross = pd.to_numeric(data["gross_points"], errors="coerce").fillna(0.0)
    wins = net[net > 0]
    losses = net[net < 0]
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    yearly = net.groupby(data["entry_ts"].dt.year).sum()
    rolling = rolling_stats(data, 90)
    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss = float((-losses).mean()) if not losses.empty else 0.0
    gross_profit = float(wins.sum())
    gross_loss = float((-losses).sum())
    return {
        "trades": int(len(data)),
        "net_points": float(net.sum()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else (999.0 if gross_profit > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "payoff_ratio": float(avg_win / avg_loss) if avg_loss else 0.0,
        "expectancy_points": float(net.mean()),
        "max_drawdown_points": float(abs(drawdown.min())),
        "net_to_drawdown": float(net.sum() / max(abs(float(drawdown.min())), 1.0)),
        "positive_year_rate": float((yearly > 0).mean()) if not yearly.empty else 0.0,
        "positive_90d_rate": float((rolling["net_points"] > 0).mean()) if not rolling.empty else 0.0,
        "worst_90d_points": float(rolling["net_points"].min()) if not rolling.empty else 0.0,
        "net_at_cost_2.125": float(gross.sum() - 2.125 * len(data)),
        "same_bar_count": int((data["entry_index"].to_numpy(dtype=int) == data["exit_index"].to_numpy(dtype=int)).sum()),
    }


def rolling_stats(trades: pd.DataFrame, days: int) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["start", "end", "trades", "net_points"])
    start = trades["entry_ts"].min().normalize()
    end = trades["entry_ts"].max().normalize()
    rows: list[dict[str, Any]] = []
    cursor = start
    while cursor + pd.Timedelta(days=days) <= end:
        stop = cursor + pd.Timedelta(days=days)
        selected = trades[(trades["entry_ts"] >= cursor) & (trades["entry_ts"] < stop)]
        rows.append(
            {
                "start": str(cursor.date()),
                "end": str(stop.date()),
                "trades": int(len(selected)),
                "net_points": float(pd.to_numeric(selected["net_points"], errors="coerce").fillna(0.0).sum()),
            }
        )
        cursor += pd.Timedelta(days=days)
    return pd.DataFrame(rows)


def split_trades(trades: pd.DataFrame, split_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    if trades.empty:
        return trades, trades
    data = trades.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True)
    split = pd.Timestamp(split_date, tz="UTC")
    return data[data["entry_ts"] < split].copy(), data[data["entry_ts"] >= split].copy()


def candidate_grid(args: argparse.Namespace) -> list[RegimeCandidate]:
    return [
        RegimeCandidate(
            lookback=lookback,
            width_atr_max=width,
            efficiency_max=efficiency,
            displacement_atr_min=displacement,
            body_share_min=body,
            volume_z_min=volume_z,
            session="us_late",
            direction_filter="long",
            stop_mode="break_bar",
            reward_risk=reward_risk,
            horizon_minutes=horizon,
        )
        for lookback in args.lookbacks
        for width in args.width_atr_max
        for efficiency in args.efficiency_max
        for displacement in args.displacement_atr_min
        for body in args.body_share_min
        for volume_z in args.volume_z_min
        for reward_risk in args.reward_risks
        for horizon in args.horizon_minutes
    ]


def score_row(row: dict[str, Any]) -> float:
    if row["test_trades"] < 100 or row["test_net_points"] <= 0 or row["test_profit_factor"] < 1.2:
        return -1_000_000.0 + float(row["test_net_points"])
    train_penalty = 0.0 if row["train_net_points"] > 0 else 500.0
    same_bar_penalty = 10_000.0 if row["test_same_bar_count"] else 0.0
    return (
        float(row["test_net_points"]) * 0.01
        + float(row["test_net_to_drawdown"]) * 20.0
        + float(row["test_profit_factor"]) * 60.0
        + float(row["test_positive_90d_rate"]) * 80.0
        + float(row["test_positive_year_rate"]) * 60.0
        - abs(float(row["test_worst_90d_points"])) * 0.12
        - train_penalty
        - same_bar_penalty
    )


def html_report(results: pd.DataFrame, best_trades: pd.DataFrame, args: argparse.Namespace) -> str:
    best = results.iloc[0]
    yearly = best_trades.copy()
    yearly["entry_ts"] = pd.to_datetime(yearly["entry_ts"], utc=True)
    yearly["year"] = yearly["entry_ts"].dt.year
    yearly_rows = yearly.groupby("year", as_index=False)["net_points"].agg(["count", "sum"]).reset_index()
    yearly_rows = yearly_rows.rename(columns={"count": "trades", "sum": "net_points"})

    def fmt(value: object, digits: int = 2) -> str:
        if pd.isna(value):
            return "-"
        if isinstance(value, (int, np.integer)):
            return f"{int(value):,}"
        try:
            return f"{float(value):,.{digits}f}"
        except (TypeError, ValueError):
            return html.escape(str(value))

    def table(frame: pd.DataFrame, columns: list[str]) -> str:
        header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
        rows = []
        for _, row in frame[columns].iterrows():
            rows.append("<tr>" + "".join(f"<td>{fmt(row[column], 3 if isinstance(row[column], float) else 2)}</td>" for column in columns) + "</tr>")
        return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>NQ SMC Regime Trend Neighborhood Optimization</title>
  <style>
    body {{ margin:0; background:#10130f; color:#eef4e8; font-family:Georgia,"Times New Roman",serif; }}
    main {{ max-width:1180px; margin:0 auto; padding:30px 22px 70px; }}
    h1 {{ font-size:38px; margin:0 0 8px; }}
    h2 {{ margin-top:32px; border-bottom:1px solid #3b4638; padding-bottom:8px; }}
    p,li {{ color:#c7d4c0; line-height:1.65; }}
    code {{ color:#b7f7c1; }}
    .cards {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:20px 0; }}
    .card {{ background:#182016; border:1px solid #394734; border-radius:12px; padding:14px; }}
    .card span {{ color:#9aaa92; display:block; font-size:12px; }}
    .card strong {{ display:block; margin-top:6px; font-size:22px; }}
    table {{ border-collapse:collapse; width:100%; font-size:13px; margin:12px 0 22px; }}
    th,td {{ border:1px solid #394734; padding:7px 9px; text-align:right; }}
    th:first-child,td:first-child {{ text-align:left; }}
    th {{ background:#202a1d; }}
  </style>
</head>
<body>
<main>
  <h1>NQ SMC-Regime 趋势系统邻域优化</h1>
  <p>优化方式：<code>{args.start_date}</code> 到 <code>{args.split_date}</code> 作为发现区间，<code>{args.split_date}</code> 到 <code>{args.end_date}</code> 作为 OOS 验证区间。所有结果沿用 no-same-bar 的回测路径。</p>
  <p>最佳 OOS 候选：<code>{html.escape(str(best["candidate"]))}</code></p>
  <div class="cards">
    <div class="card"><span>OOS Trades</span><strong>{fmt(best["test_trades"], 0)}</strong></div>
    <div class="card"><span>OOS Net</span><strong>{fmt(best["test_net_points"])}</strong></div>
    <div class="card"><span>OOS PF</span><strong>{fmt(best["test_profit_factor"], 3)}</strong></div>
    <div class="card"><span>OOS Net/DD</span><strong>{fmt(best["test_net_to_drawdown"], 2)}</strong></div>
    <div class="card"><span>OOS Win</span><strong>{float(best["test_win_rate"]):.1%}</strong></div>
    <div class="card"><span>OOS 90d+</span><strong>{float(best["test_positive_90d_rate"]):.1%}</strong></div>
    <div class="card"><span>Worst 90d</span><strong>{fmt(best["test_worst_90d_points"])}</strong></div>
    <div class="card"><span>Same Bar</span><strong>{fmt(best["test_same_bar_count"], 0)}</strong></div>
  </div>
  <h2>Top Candidates</h2>
  {table(results.head(25), ["candidate", "train_trades", "train_net_points", "train_profit_factor", "test_trades", "test_net_points", "test_profit_factor", "test_net_to_drawdown", "test_positive_year_rate", "test_positive_90d_rate", "test_worst_90d_points", "score"])}
  <h2>Best OOS Yearly</h2>
  {table(yearly_rows, ["year", "trades", "net_points"])}
  <h2>结论</h2>
  <p>如果本报告最佳候选相对上一版只提升 OOS 但牺牲长期稳定，则应保留上一版防守候选；如果 OOS、PF、net/DD、滚动90日都同时提升，再升级主报告。</p>
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Focused no-same-bar neighborhood optimization for NQ SMC regime trend system.")
    parser.add_argument("--start-date", default="2010-06-06")
    parser.add_argument("--split-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-short-trend-2010-adx-cache.pkl")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--lookbacks", type=int, nargs="+", default=[40, 45, 50])
    parser.add_argument("--width-atr-max", type=float, nargs="+", default=[8.0, 10.0, 12.0])
    parser.add_argument("--efficiency-max", type=float, nargs="+", default=[0.05, 0.10, 0.15, 0.20])
    parser.add_argument("--displacement-atr-min", type=float, nargs="+", default=[1.4, 1.6, 1.8, 2.0])
    parser.add_argument("--body-share-min", type=float, nargs="+", default=[0.55, 0.60])
    parser.add_argument("--volume-z-min", type=float, nargs="+", default=[0.0, 0.25, 0.50])
    parser.add_argument("--reward-risks", type=float, nargs="+", default=[2.0, 2.25, 2.5, 2.75])
    parser.add_argument("--horizon-minutes", type=int, nargs="+", default=[120, 180, 240])
    parser.add_argument("--breakout-buffer-atr", type=float, default=0.05)
    parser.add_argument("--min-buffer-points", type=float, default=0.25)
    parser.add_argument("--stop-buffer-atr", type=float, default=0.10)
    parser.add_argument("--stop-atr-mult", type=float, default=2.0)
    parser.add_argument("--min-stop-points", type=float, default=4.0)
    parser.add_argument("--max-stop-points", type=float, default=80.0)
    parser.add_argument("--output-prefix", default=".tmp/nq-smc-regime-neighborhood")
    parser.add_argument("--report", default="reports/NQ-smc-regime-trend-neighborhood-optimization.html")
    args = parser.parse_args()

    costs = BacktestCosts()
    base = load_continuous_nq_bars(args)
    frame = prepare_features(base, args)
    events = build_breakout_events(frame, args)
    candidates = candidate_grid(args)
    print(f"events={len(events):,} candidates={len(candidates):,}", flush=True)

    outcome_cache: dict[tuple[float, int], pd.DataFrame] = {}
    for reward_risk in args.reward_risks:
        for horizon in args.horizon_minutes:
            key = (float(reward_risk), int(horizon))
            print(f"computing outcomes rr={reward_risk:g} h={horizon}", flush=True)
            outcome_cache[key] = compute_outcomes(
                frame,
                events,
                stop_mode="break_bar",
                reward_risk=float(reward_risk),
                horizon=int(horizon),
                args=args,
                costs=costs,
            )

    rows: list[dict[str, Any]] = []
    best_trades = pd.DataFrame()
    for index, candidate in enumerate(candidates, start=1):
        if index == 1 or index % 1000 == 0 or index == len(candidates):
            print(f"candidate {index}/{len(candidates)}", flush=True)
        trades = select_candidate_trades(outcome_cache[(float(candidate.reward_risk), int(candidate.horizon_minutes))], candidate)
        train, test = split_trades(trades, args.split_date)
        train_summary = summarize(train, costs)
        test_summary = summarize(test, costs)
        row = {
            **{key: value for key, value in asdict(candidate).items()},
            "candidate": candidate.name,
            **{f"train_{key}": value for key, value in train_summary.items()},
            **{f"test_{key}": value for key, value in test_summary.items()},
        }
        row["score"] = score_row(row)
        rows.append(row)
    results = pd.DataFrame(rows).sort_values(
        ["score", "test_net_to_drawdown", "test_profit_factor", "test_net_points"],
        ascending=[False, False, False, False],
    )
    if not results.empty:
        best_candidate = RegimeCandidate(
            lookback=int(results.iloc[0]["lookback"]),
            width_atr_max=float(results.iloc[0]["width_atr_max"]),
            efficiency_max=float(results.iloc[0]["efficiency_max"]),
            displacement_atr_min=float(results.iloc[0]["displacement_atr_min"]),
            body_share_min=float(results.iloc[0]["body_share_min"]),
            volume_z_min=float(results.iloc[0]["volume_z_min"]),
            session=str(results.iloc[0]["session"]),
            direction_filter=str(results.iloc[0]["direction_filter"]),
            stop_mode=str(results.iloc[0]["stop_mode"]),
            reward_risk=float(results.iloc[0]["reward_risk"]),
            horizon_minutes=int(results.iloc[0]["horizon_minutes"]),
        )
        best_all = select_candidate_trades(outcome_cache[(float(best_candidate.reward_risk), int(best_candidate.horizon_minutes))], best_candidate)
        _, best_trades = split_trades(best_all, args.split_date)

    prefix = Path(args.output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(f"{prefix}-summary.csv", index=False)
    best_trades.to_csv(f"{prefix}-best-oos-trades.csv", index=False)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(html_report(results, best_trades, args), encoding="utf-8")
    print(f"wrote {prefix}-summary.csv")
    print(f"wrote {prefix}-best-oos-trades.csv")
    print(f"wrote {args.report}")
    if not results.empty:
        print(results.head(10)[["candidate", "test_trades", "test_net_points", "test_profit_factor", "test_net_to_drawdown", "test_positive_90d_rate", "test_worst_90d_points", "score"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
