from __future__ import annotations

import argparse
import html
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from backtest_nq_boundary_lightglow_strategy import (  # noqa: E402
    BoundaryLightglowConfig,
    add_features,
    build_signals,
    backtest_strategy,
    load_nq_bars,
    pine_default_costs,
    summarize,
)


def fmt(value: object, digits: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, (float, np.floating)):
        return f"{float(value):,.{digits}f}"
    return str(value)


def pct(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100:.1f}%"


def table(frame: pd.DataFrame, columns: list[str], *, percent_columns: set[str] | None = None) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    percent_columns = percent_columns or set()
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    rows = []
    for _, row in frame[columns].iterrows():
        cells = []
        for column in columns:
            value = row[column]
            rendered = pct(value) if column in percent_columns else fmt(value, 3 if isinstance(value, float) else 2)
            cells.append(f"<td>{html.escape(rendered)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def load_month_window(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    bars = load_nq_bars(args)
    config = BoundaryLightglowConfig()
    features = build_signals(add_features(bars, config), config)
    trades = backtest_strategy(features, config, pine_default_costs())
    start = pd.Timestamp(args.window_start, tz="UTC")
    end = pd.Timestamp(args.window_end, tz="UTC") + pd.Timedelta(days=1)
    bars = bars[(bars["ts"] >= start) & (bars["ts"] < end)].copy().reset_index(drop=True)
    trades = trades[(pd.to_datetime(trades["entry_ts"], utc=True) >= start) & (pd.to_datetime(trades["entry_ts"], utc=True) < end)].copy()
    trades = trades.sort_values("entry_ts").reset_index(drop=True)
    return bars, features, trades


def chart_for_trade(frame: pd.DataFrame, trade: pd.Series, title: str) -> str:
    entry_ts = pd.Timestamp(trade["entry_ts"]).tz_convert("UTC")
    exit_ts = pd.Timestamp(trade["exit_ts"]).tz_convert("UTC")
    context = frame[(frame["ts"] >= entry_ts - pd.Timedelta(minutes=45)) & (frame["ts"] <= exit_ts + pd.Timedelta(minutes=45))].copy()
    if context.empty:
        return f"<p>No chart data for {html.escape(title)}.</p>"

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.72, 0.28])
    fig.add_trace(
        go.Candlestick(
            x=context["ts"],
            open=context["Open"],
            high=context["High"],
            low=context["Low"],
            close=context["Close"],
            name="NQ 1m",
            increasing_line_color="#22c55e",
            decreasing_line_color="#ef4444",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(go.Bar(x=context["ts"], y=context["Volume"], marker_color="#64748b", name="Volume"), row=2, col=1)
    fig.add_trace(go.Scatter(x=[entry_ts], y=[float(trade["entry_price"])], mode="markers+text", text=["ENTRY"], textposition="top center", marker={"size": 14, "color": "#2563eb", "symbol": "triangle-up" if int(trade["direction"]) > 0 else "triangle-down"}, name="Entry"), row=1, col=1)
    fig.add_trace(go.Scatter(x=[exit_ts], y=[float(trade["exit_price"])], mode="markers+text", text=["EXIT"], textposition="bottom center", marker={"size": 14, "color": "#a855f7", "symbol": "x"}, name="Exit"), row=1, col=1)
    fig.add_hline(y=float(trade["entry_price"]), line_dash="dot", line_color="#2563eb", row=1, col=1)
    fig.add_hline(y=float(trade["exit_price"]), line_dash="dot", line_color="#a855f7", row=1, col=1)
    fig.update_layout(template="plotly_dark", height=700, xaxis_rangeslider_visible=False, title=title, margin={"l": 40, "r": 20, "t": 60, "b": 36})
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def build_report(bars: pd.DataFrame, trades: pd.DataFrame, args: argparse.Namespace) -> str:
    summary = summarize(trades)
    family = trades.groupby(["signal_family", "session"], as_index=False).agg(
        trades=("net_points", "size"),
        net_points=("net_points", "sum"),
        profit_factor=("net_points", lambda s: float(s[s > 0].sum() / abs(s[s < 0].sum())) if abs(s[s < 0].sum()) else (999.0 if s[s > 0].sum() > 0 else 0.0)),
        win_rate=("net_points", lambda s: float((s > 0).mean())),
        avg_points=("net_points", "mean"),
        worst_trade_points=("net_points", "min"),
    ) if not trades.empty else pd.DataFrame()
    loss_rows = trades[trades["net_points"] < 0].sort_values("net_points").copy() if not trades.empty else pd.DataFrame()
    best_rows = trades.sort_values("net_points", ascending=False).head(10).copy() if not trades.empty else pd.DataFrame()
    worst_rows = trades.sort_values("net_points").head(10).copy() if not trades.empty else pd.DataFrame()

    charts = []
    for index, row in trades.iterrows():
        charts.append(f"<section class='trade'>{chart_for_trade(bars, row, f'Trade #{index + 1}: {row.signal_family} · {row.session} · {row.net_points:.2f} pts')}</section>")

    replay_table = trades.copy()
    if not replay_table.empty:
        replay_table["entry_ts"] = pd.to_datetime(replay_table["entry_ts"], utc=True).astype(str)
        replay_table["exit_ts"] = pd.to_datetime(replay_table["exit_ts"], utc=True).astype(str)
        replay_table["result"] = np.where(replay_table["net_points"] > 0, "WIN", "LOSS")

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>NQ Pine 近1个月交易回放报告</title>
  <style>
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:#07111f; color:#e5eefb; }}
    main {{ max-width:1280px; margin:0 auto; padding:28px 22px 64px; }}
    h1 {{ margin:0 0 8px; font-size:34px; }}
    h2 {{ margin-top:32px; border-bottom:1px solid #20324d; padding-bottom:8px; }}
    p, li {{ color:#b6c4d9; line-height:1.65; }}
    table {{ border-collapse:collapse; width:100%; font-size:13px; }}
    th, td {{ border-bottom:1px solid #23334d; padding:7px 9px; text-align:left; vertical-align:top; }}
    th {{ background:#0f1d33; }}
    .grid {{ display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:12px; margin:20px 0; }}
    .card {{ background:#0f1d33; border:1px solid #20324d; border-radius:8px; padding:14px; }}
    .card span {{ display:block; color:#94a3b8; font-size:12px; }}
    .card strong {{ display:block; margin-top:6px; font-size:24px; color:#f8fafc; }}
    .trade {{ margin:18px 0 28px; padding:14px; background:#0f1d33; border:1px solid #20324d; border-radius:10px; }}
    .trade-chart figcaption {{ margin:0 0 10px; font-size:15px; color:#dbeafe; }}
    .win {{ color:#34d399; }}
    .loss {{ color:#f87171; }}
    .table-wrap {{ overflow-x:auto; }}
  </style>
</head>
<body>
<main>
  <h1>NQ Pine 近1个月交易回放报告</h1>
  <p>窗口：{html.escape(args.window_start)} 到 {html.escape(args.window_end)}。数据源：Databento 1 分钟 K 线。策略：当前 <code>pine_scripts/nq_lightglow_timecell_composite_paper_readiness.pine</code> 默认核心配置。</p>
  <div class="grid">
    <div class="card"><span>交易数</span><strong>{fmt(summary["trades"], 0)}</strong></div>
    <div class="card"><span>净点数</span><strong>{fmt(summary["net_points"], 2)}</strong></div>
    <div class="card"><span>PF</span><strong>{fmt(summary["profit_factor"], 3)}</strong></div>
    <div class="card"><span>最大回撤</span><strong>{fmt(summary["max_drawdown_points"], 2)}</strong></div>
  </div>
  <section>
    <h2>逐笔回放</h2>
    {''.join(charts) if charts else '<p>No trades.</p>'}
  </section>
  <section>
    <h2>逐笔交易表</h2>
    <div class="table-wrap">{table(replay_table, ["entry_ts", "exit_ts", "signal_family", "session", "direction", "entry_price", "exit_price", "net_points", "gross_points", "exit_reason", "result"])}</div>
  </section>
  <section>
    <h2>亏损交易</h2>
    <div class="table-wrap">{table(loss_rows, ["entry_ts", "exit_ts", "signal_family", "session", "direction", "entry_price", "exit_price", "net_points", "exit_reason"], percent_columns=set())}</div>
  </section>
  <section>
    <h2>亏损排查结论</h2>
    <div class="table-wrap">{table(family.sort_values("net_points", ascending=False), ["signal_family", "session", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "worst_trade_points"]) if not family.empty else '<p>No family rows.</p>'}</div>
  </section>
  <section>
    <h2>最优 / 最差 交易</h2>
    <h3>最优</h3>
    <div class="table-wrap">{table(best_rows, ["entry_ts", "exit_ts", "signal_family", "session", "net_points", "exit_reason"]) if not best_rows.empty else '<p>No best rows.</p>'}</div>
    <h3>最差</h3>
    <div class="table-wrap">{table(worst_rows, ["entry_ts", "exit_ts", "signal_family", "session", "net_points", "exit_reason"]) if not worst_rows.empty else '<p>No worst rows.</p>'}</div>
  </section>
</main>
</body>
</html>"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a replay report for the current NQ Pine strategy on the last month of Databento 1m bars.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-04-27")
    parser.add_argument("--cache", default=".tmp/nq-pine-replay-bars.pkl")
    parser.add_argument("--chunk-size", type=int, default=200_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--window-start", default="2026-03-28")
    parser.add_argument("--window-end", default="2026-04-27")
    parser.add_argument("--report", default="reports/NQ-pine-trade-replay-last-month.html")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = BoundaryLightglowConfig()
    bars = load_nq_bars(args)
    features = build_signals(add_features(bars, config), config)
    trades = backtest_strategy(features, config, pine_default_costs())
    start = pd.Timestamp(args.window_start, tz="UTC")
    end = pd.Timestamp(args.window_end, tz="UTC") + pd.Timedelta(days=1)
    month_bars = bars[(bars["ts"] >= start) & (bars["ts"] < end)].copy().reset_index(drop=True)
    month_trades = trades[(pd.to_datetime(trades["entry_ts"], utc=True) >= start) & (pd.to_datetime(trades["entry_ts"], utc=True) < end)].copy().reset_index(drop=True)
    report = build_report(month_bars, month_trades, args)
    report_path = ROOT_DIR / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(summarize(month_trades))
    print(f"wrote {args.report}")


if __name__ == "__main__":
    main()
