from __future__ import annotations

import argparse
import html
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from search_nq_short_trend_systems import (  # noqa: E402
    TrendCandidate,
    add_trend_features,
    build_trades,
    load_continuous_nq_bars,
    resample_ohlcv,
    summarize_trades,
)
from tradingagents.backtesting.short_patterns import BacktestCosts  # noqa: E402


REPORT_PATH = ROOT_DIR / "reports" / "NQ-ADX-DI-3m-RTH-trend-strategy-report.html"
TRADES_PATH = ROOT_DIR / ".tmp" / "nq-adx-di-3m-rth-hold60-trades.csv"
MONTHLY_PATH = ROOT_DIR / ".tmp" / "nq-adx-di-3m-rth-hold60-monthly.csv"
YEARLY_PATH = ROOT_DIR / ".tmp" / "nq-adx-di-3m-rth-hold60-yearly.csv"


@dataclass(frozen=True)
class SvgStyle:
    width: int = 980
    height: int = 340
    left: int = 72
    right: int = 26
    top: int = 34
    bottom: int = 44


def format_number(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


def format_signed(value: float, digits: int = 2) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:,.{digits}f}"


def pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"


def css_class(value: float) -> str:
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"


def equity_series(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["entry_ts", "equity_points", "drawdown_points"])
    data = trades.sort_values("entry_ts").reset_index(drop=True).copy()
    data["equity_points"] = data["net_points"].astype(float).cumsum()
    data["drawdown_points"] = data["equity_points"] - data["equity_points"].cummax()
    return data


def monthly_returns(trades: pd.DataFrame) -> pd.DataFrame:
    data = trades.copy()
    data["month"] = data["entry_ts"].dt.tz_convert(None).dt.to_period("M").astype(str)
    grouped = (
        data.groupby("month", as_index=False)
        .agg(
            trades=("net_points", "size"),
            net_points=("net_points", "sum"),
            gross_points=("gross_points", "sum"),
            win_rate=("net_points", lambda values: float((values > 0).mean())),
            avg_points=("net_points", "mean"),
            max_loss=("net_points", "min"),
        )
        .sort_values("month")
    )
    grouped["net_dollars"] = grouped["net_points"] * BacktestCosts().point_value
    return grouped


def yearly_returns(trades: pd.DataFrame) -> pd.DataFrame:
    data = trades.copy()
    data["year"] = data["entry_ts"].dt.year
    grouped = (
        data.groupby("year", as_index=False)
        .agg(
            trades=("net_points", "size"),
            net_points=("net_points", "sum"),
            gross_points=("gross_points", "sum"),
            win_rate=("net_points", lambda values: float((values > 0).mean())),
            avg_points=("net_points", "mean"),
            max_loss=("net_points", "min"),
        )
        .sort_values("year")
    )
    grouped["net_dollars"] = grouped["net_points"] * BacktestCosts().point_value
    return grouped


def period_summary(trades: pd.DataFrame, start: str, end: str) -> dict[str, Any]:
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")
    selected = trades[(trades["entry_ts"] >= start_ts) & (trades["entry_ts"] < end_ts)]
    return summarize_trades(selected)


def fixed_window_summary(trades: pd.DataFrame) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    start = pd.Timestamp("2022-04-28", tz="UTC")
    end = pd.Timestamp("2026-04-28", tz="UTC")
    while start + pd.Timedelta(days=90) <= end:
        stop = start + pd.Timedelta(days=90)
        selected = trades[(trades["entry_ts"] >= start) & (trades["entry_ts"] < stop)]
        rows.append({"start": start, "end": stop, **summarize_trades(selected)})
        start += pd.Timedelta(days=90)
    frame = pd.DataFrame(rows)
    return {
        "windows": int(len(frame)),
        "positive_windows": int((frame["net_points"] > 0).sum()),
        "positive_rate": float((frame["net_points"] > 0).mean()),
        "net_points": float(frame["net_points"].sum()),
        "worst_window": float(frame["net_points"].min()),
        "mean_pf": float(frame["profit_factor"].mean()),
        "max_drawdown": float(frame["max_drawdown_points"].max()),
    }


def downsample_points(values: list[tuple[float, float]], limit: int = 320) -> list[tuple[float, float]]:
    if len(values) <= limit:
        return values
    step = (len(values) - 1) / (limit - 1)
    result = []
    for index in range(limit):
        result.append(values[round(index * step)])
    return result


def line_svg(
    title: str,
    points: list[tuple[float, float]],
    stroke: str,
    fill_under: str | None = None,
    y_label: str = "points",
    x_note: str = "",
    style: SvgStyle = SvgStyle(),
) -> str:
    if not points:
        return "<p class=\"empty\">No chart data.</p>"

    sampled = downsample_points(points)
    xs = [point[0] for point in sampled]
    ys = [point[1] for point in sampled]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if min_y == max_y:
        min_y -= 1
        max_y += 1
    if min_x == max_x:
        max_x += 1

    plot_w = style.width - style.left - style.right
    plot_h = style.height - style.top - style.bottom

    def sx(value: float) -> float:
        return style.left + (value - min_x) / (max_x - min_x) * plot_w

    def sy(value: float) -> float:
        return style.top + (max_y - value) / (max_y - min_y) * plot_h

    coords = [(sx(x), sy(y)) for x, y in sampled]
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    zero_y = sy(0.0) if min_y <= 0 <= max_y else sy(min_y)
    grid_values = [min_y, min_y + (max_y - min_y) / 2, max_y]
    grid = "\n".join(
        f"<line x1=\"{style.left}\" y1=\"{sy(value):.1f}\" x2=\"{style.width - style.right}\" y2=\"{sy(value):.1f}\" stroke=\"#d6dde5\" stroke-dasharray=\"4 6\" />"
        f"<text x=\"18\" y=\"{sy(value) + 4:.1f}\" fill=\"#64748b\" font-size=\"12\">{format_number(value, 0)}</text>"
        for value in grid_values
    )
    fill_path = ""
    if fill_under:
        first_x, _ = coords[0]
        last_x, _ = coords[-1]
        fill_path = (
            f"<polygon points=\"{first_x:.1f},{zero_y:.1f} {polyline} {last_x:.1f},{zero_y:.1f}\" "
            f"fill=\"{fill_under}\" opacity=\"0.20\" />"
        )
    return f"""
    <figure class="chart">
      <figcaption>{html.escape(title)}</figcaption>
      <svg viewBox="0 0 {style.width} {style.height}" role="img" aria-label="{html.escape(title)}">
        <rect x="0" y="0" width="{style.width}" height="{style.height}" rx="8" fill="#ffffff" />
        {grid}
        <line x1="{style.left}" y1="{style.top}" x2="{style.left}" y2="{style.height - style.bottom}" stroke="#94a3b8" />
        <line x1="{style.left}" y1="{style.height - style.bottom}" x2="{style.width - style.right}" y2="{style.height - style.bottom}" stroke="#94a3b8" />
        {fill_path}
        <polyline points="{polyline}" fill="none" stroke="{stroke}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" />
        <circle cx="{coords[-1][0]:.1f}" cy="{coords[-1][1]:.1f}" r="4.5" fill="{stroke}" />
        <text x="{style.left}" y="24" fill="#334155" font-size="13">{html.escape(y_label)}</text>
        <text x="{style.width - 260}" y="{style.height - 14}" fill="#64748b" font-size="12">{html.escape(x_note)}</text>
      </svg>
    </figure>
    """


def bar_svg(title: str, labels: list[str], values: list[float], style: SvgStyle = SvgStyle(height=360)) -> str:
    if not labels:
        return "<p class=\"empty\">No bar data.</p>"
    max_value = max(values + [0.0])
    min_value = min(values + [0.0])
    if min_value == max_value:
        max_value += 1
    plot_w = style.width - style.left - style.right
    plot_h = style.height - style.top - style.bottom
    bar_w = plot_w / max(len(values), 1) * 0.72

    def sy(value: float) -> float:
        return style.top + (max_value - value) / (max_value - min_value) * plot_h

    zero_y = sy(0.0)
    bars = []
    for index, (label, value) in enumerate(zip(labels, values, strict=True)):
        x = style.left + index * plot_w / len(values) + (plot_w / len(values) - bar_w) / 2
        y = sy(max(value, 0.0))
        height = abs(sy(value) - zero_y)
        color = "#0f766e" if value >= 0 else "#b91c1c"
        label_text = label if len(labels) <= 14 or index % max(1, len(labels) // 12) == 0 else ""
        bars.append(
            f"<rect x=\"{x:.1f}\" y=\"{min(y, zero_y):.1f}\" width=\"{bar_w:.1f}\" height=\"{height:.1f}\" fill=\"{color}\" rx=\"2\" />"
            f"<title>{html.escape(label)}: {format_signed(value, 2)} pts</title>"
            f"<text x=\"{x + bar_w / 2:.1f}\" y=\"{style.height - 16}\" text-anchor=\"middle\" fill=\"#64748b\" font-size=\"11\">{html.escape(label_text)}</text>"
        )
    return f"""
    <figure class="chart">
      <figcaption>{html.escape(title)}</figcaption>
      <svg viewBox="0 0 {style.width} {style.height}" role="img" aria-label="{html.escape(title)}">
        <rect x="0" y="0" width="{style.width}" height="{style.height}" rx="8" fill="#ffffff" />
        <line x1="{style.left}" y1="{zero_y:.1f}" x2="{style.width - style.right}" y2="{zero_y:.1f}" stroke="#94a3b8" />
        <text x="18" y="{sy(max_value) + 4:.1f}" fill="#64748b" font-size="12">{format_number(max_value, 0)}</text>
        <text x="18" y="{sy(min_value) + 4:.1f}" fill="#64748b" font-size="12">{format_number(min_value, 0)}</text>
        {''.join(bars)}
      </svg>
    </figure>
    """


def table_html(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    body = "\n".join("<tr>" + "".join(cell for cell in row) + "</tr>" for row in rows)
    return f"<div class=\"table-wrap\"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def td(value: str, class_name: str = "") -> str:
    class_attr = f" class=\"{class_name}\"" if class_name else ""
    return f"<td{class_attr}>{html.escape(value)}</td>"


def metric_card(label: str, value: str, note: str = "", class_name: str = "") -> str:
    class_attr = f" {class_name}" if class_name else ""
    return f"""
      <div class="metric-card">
        <div class="metric-label">{html.escape(label)}</div>
        <div class="metric-value{class_attr}">{html.escape(value)}</div>
        <div class="metric-note">{html.escape(note)}</div>
      </div>
    """


def build_report(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    load_args = argparse.Namespace(
        start_date=args.start_date,
        end_date=args.end_date,
        cache=args.cache,
        chunk_size=args.chunk_size,
        min_volume=args.min_volume,
    )
    base = load_continuous_nq_bars(load_args)
    frame = add_trend_features(resample_ohlcv(base, 3))
    candidate = TrendCandidate(
        family="adx_di_trend",
        timeframe_minutes=3,
        session="us_rth",
        lookback=30,
        threshold=26.0,
        holding_bars=20,
        direction_filter="both",
        exit_profile="time",
        stop_loss_points=None,
        take_profit_points=None,
        atr_length=30,
    )
    costs = BacktestCosts(slippage_ticks_per_side=args.slippage_ticks_per_side)
    trades = build_trades(frame, candidate, costs)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    trades = trades.sort_values("entry_ts").reset_index(drop=True)
    eq = equity_series(trades)
    summary = summarize_trades(trades)
    monthly = monthly_returns(trades)
    yearly = yearly_returns(trades)
    window = fixed_window_summary(trades)

    recent_2025 = period_summary(trades, "2025-01-01", "2026-04-28")
    recent_12m = period_summary(trades, "2025-04-28", "2026-04-28")

    TRADES_PATH.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(TRADES_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    yearly.to_csv(YEARLY_PATH, index=False)

    seq_points = [(float(index), float(value)) for index, value in enumerate(eq["equity_points"].tolist(), start=1)]
    drawdown_points = [(float(index), float(value)) for index, value in enumerate(eq["drawdown_points"].tolist(), start=1)]
    timestamp_min = eq["entry_ts"].min()
    time_points = [
        ((ts - timestamp_min).total_seconds() / 86400.0, float(value))
        for ts, value in zip(eq["entry_ts"], eq["equity_points"], strict=True)
    ]

    yearly_rows = []
    for _, row in yearly.iterrows():
        yearly_rows.append(
            [
                td(str(int(row["year"]))),
                td(f"{int(row['trades']):,}", "numeric"),
                td(format_signed(float(row["net_points"])), f"numeric {css_class(float(row['net_points']))}"),
                td(format_signed(float(row["net_dollars"])), f"numeric {css_class(float(row['net_dollars']))}"),
                td(pct(float(row["win_rate"])), "numeric"),
                td(format_number(float(row["avg_points"])), "numeric"),
                td(format_number(float(row["max_loss"])), "numeric negative"),
            ]
        )

    monthly_tail = monthly.tail(36)
    monthly_rows = []
    for _, row in monthly_tail.iterrows():
        monthly_rows.append(
            [
                td(str(row["month"])),
                td(f"{int(row['trades']):,}", "numeric"),
                td(format_signed(float(row["net_points"])), f"numeric {css_class(float(row['net_points']))}"),
                td(format_signed(float(row["net_dollars"])), f"numeric {css_class(float(row['net_dollars']))}"),
                td(pct(float(row["win_rate"])), "numeric"),
                td(format_number(float(row["avg_points"])), "numeric"),
                td(format_number(float(row["max_loss"])), "numeric negative"),
            ]
        )

    direction_table = (
        trades.groupby("direction")
        .agg(trades=("net_points", "size"), net_points=("net_points", "sum"), win_rate=("net_points", lambda values: float((values > 0).mean())), avg_points=("net_points", "mean"))
        .reset_index()
    )
    direction_rows = []
    for _, row in direction_table.iterrows():
        direction_rows.append(
            [
                td("Long" if int(row["direction"]) > 0 else "Short"),
                td(f"{int(row['trades']):,}", "numeric"),
                td(format_signed(float(row["net_points"])), f"numeric {css_class(float(row['net_points']))}"),
                td(pct(float(row["win_rate"])), "numeric"),
                td(format_number(float(row["avg_points"])), "numeric"),
            ]
        )

    cost_rows = []
    for slippage in [1.0, 2.0, 3.0]:
        cost_summary = summarize_trades(build_trades(frame, candidate, BacktestCosts(slippage_ticks_per_side=slippage)).assign(
            entry_ts=lambda data: pd.to_datetime(data["entry_ts"], utc=True),
            exit_ts=lambda data: pd.to_datetime(data["exit_ts"], utc=True),
        ))
        round_trip = BacktestCosts(slippage_ticks_per_side=slippage).round_trip_cost_points
        cost_rows.append(
            [
                td(f"{slippage:.1f}"),
                td(format_number(round_trip, 3), "numeric"),
                td(format_signed(float(cost_summary["net_points"])), f"numeric {css_class(float(cost_summary['net_points']))}"),
                td(format_number(float(cost_summary["profit_factor"]), 3), "numeric"),
                td(format_number(float(cost_summary["max_drawdown_points"])), "numeric"),
            ]
        )

    best_month = monthly.loc[monthly["net_points"].idxmax()]
    worst_month = monthly.loc[monthly["net_points"].idxmin()]
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    data_start = pd.to_datetime(base["ts"]).min().strftime("%Y-%m-%d")
    data_end = pd.to_datetime(base["ts"]).max().strftime("%Y-%m-%d")
    positive_month_rate = float((monthly["net_points"] > 0).mean())
    positive_year_rate = float((yearly["net_points"] > 0).mean())

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ 3m ADX/DI RTH 趋势策略回测报告</title>
  <link rel="icon" href="data:,">
  <style>
    :root {{
      --bg: #f5f7fb;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #64748b;
      --line: #d8e0ea;
      --green: #0f766e;
      --green-soft: #e5f5f1;
      --red: #b91c1c;
      --red-soft: #fff1f2;
      --blue: #1d4ed8;
      --amber: #b45309;
    }}
    * {{ box-sizing: border-box; }}
    html {{ max-width: 100%; overflow-x: hidden; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--bg);
      font: 15px/1.58 -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
      overflow-x: hidden;
    }}
    header {{
      padding: 34px min(5vw, 64px) 24px;
      background: #0f172a;
      color: #f8fafc;
      border-bottom: 1px solid #1e293b;
    }}
    main {{ padding: 26px min(5vw, 64px) 56px; }}
    h1 {{ margin: 0 0 10px; max-width: 1180px; font-size: clamp(30px, 4vw, 52px); line-height: 1.08; letter-spacing: 0; }}
    h2 {{ margin: 0 0 14px; font-size: 22px; }}
    h3 {{ margin: 0 0 10px; font-size: 17px; }}
    p {{ margin: 0 0 12px; }}
    code {{ padding: 2px 5px; border-radius: 5px; background: #e2e8f0; color: #0f172a; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
    .subtitle {{ max-width: 1040px; color: #cbd5e1; font-size: 17px; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; color: #cbd5e1; }}
    .pill {{ max-width: 100%; border: 1px solid #334155; border-radius: 999px; padding: 6px 10px; background: #111827; overflow-wrap: anywhere; }}
    section {{ margin: 20px 0; padding: 22px; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 10px 28px rgba(15, 23, 42, .06); }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin-top: 20px; }}
    .metric-card {{ min-height: 106px; padding: 15px; border: 1px solid var(--line); border-radius: 8px; background: #fbfdff; }}
    .metric-label {{ color: var(--muted); font-size: 12px; }}
    .metric-value {{ margin: 6px 0 3px; font-size: 25px; font-weight: 760; font-variant-numeric: tabular-nums; }}
    .metric-note {{ color: var(--muted); font-size: 12px; }}
    .positive {{ color: var(--green); }}
    .negative {{ color: var(--red); }}
    .neutral {{ color: var(--muted); }}
    .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    .callout {{ padding: 16px; border: 1px solid #b9ddd5; border-left: 5px solid var(--green); border-radius: 8px; background: var(--green-soft); }}
    .risk {{ border-color: #fecdd3; border-left-color: var(--red); background: var(--red-soft); }}
    .note {{ border-color: #fde68a; border-left-color: var(--amber); background: #fffbeb; }}
    .table-wrap {{ max-width: 100%; overflow-x: auto; }}
    table {{ width: 100%; min-width: 640px; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 9px 8px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ color: #334155; background: #f1f5f9; font-weight: 650; }}
    .numeric {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .chart {{ margin: 14px 0 0; }}
    .chart figcaption {{ margin: 0 0 8px; color: #334155; font-weight: 700; }}
    .chart svg {{ max-width: 100%; width: 100%; height: auto; border: 1px solid var(--line); border-radius: 8px; display: block; }}
    ul {{ margin: 8px 0 0; padding-left: 20px; }}
    li {{ margin: 6px 0; }}
    .sources a {{ color: var(--blue); overflow-wrap: anywhere; }}
    footer {{ padding: 22px min(5vw, 64px); color: #cbd5e1; background: #0f172a; }}
    @media (max-width: 1100px) {{
      .metric-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .grid-2 {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 720px) {{
      main {{ padding: 14px; }}
      header {{ padding: 24px 14px; }}
      section {{ padding: 16px; }}
      .metric-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .metric-value {{ font-size: 20px; }}
      .chart {{ overflow-x: hidden; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>NQ 3m ADX/DI RTH 趋势策略回测报告</h1>
    <p class="subtitle">研究级短线趋势候选：用 ADX 过滤趋势强度，用 +DI/-DI 判断方向，在 NQ 美股 RTH 3 分钟 bar 上固定持有 60 分钟。报告为静态 HTML，所有图表为内联 SVG。</p>
    <div class="meta">
      <span class="pill">Candidate: {html.escape(candidate.name)}</span>
      <span class="pill">Data: {data_start} 至 {data_end}</span>
      <span class="pill">Generated: {generated_at}</span>
      <span class="pill">Cost: {format_number(costs.round_trip_cost_points, 3)} NQ pts / round trip</span>
    </div>
    <div class="metric-grid">
      {metric_card("累计净点数", format_signed(float(summary["net_points"])), "扣除手续费和滑点", "positive")}
      {metric_card("累计净美元", format_signed(float(summary["net_dollars"])), "NQ $20/point", "positive")}
      {metric_card("Profit Factor", format_number(float(summary["profit_factor"]), 3), "毛利 / 毛亏")}
      {metric_card("最大回撤", format_number(float(summary["max_drawdown_points"])), "points")}
      {metric_card("交易数", f"{int(summary['trades']):,}", "全样本")}
      {metric_card("胜率", pct(float(summary["win_rate"]), 2), "单笔净收益 > 0")}
    </div>
  </header>
  <main>
    <section>
      <h2>策略结论</h2>
      <div class="grid-2">
        <div class="callout">
          <h3>可以交易的研究候选</h3>
          <p>该策略在 2021-2026 全样本、每年、最近 12 个月、以及 1-3 tick/side 成本敏感性下均保持正收益。参数邻域里也存在多个正收益组合，因此不是单个参数点偶然胜出。</p>
          <p><strong>当前定位：</strong>研究级稳定盈利候选，可进入更细的执行建模和 paper validation。</p>
        </div>
        <div class="callout risk">
          <h3>不能直接实盘</h3>
          <p>本报告仍是 bar 回测：未建模盘口排队、成交概率、突发滑点、roll 细节、日内熔断式风控和真实订单路由。上线前必须先做纸盘。</p>
          <p><strong>建议：</strong>先用 MNQ 或模拟环境验证 2-4 周，再决定是否放大。</p>
        </div>
      </div>
    </section>

    <section>
      <h2>策略原理</h2>
      <p><strong>ADX</strong> 衡量趋势强度；阈值 <code>ADX(30) >= 26</code> 用来过滤震荡环境。<strong>+DI / -DI</strong> 给出方向：+DI 高于 -DI 只允许多头，-DI 高于 +DI 只允许空头。</p>
      <p>为了减少同一段趋势中过度重复入场，信号只在方向状态发生变化时触发。信号出现后下一根 3m bar 开盘入场，固定持有 20 根 3m bar，即 60 分钟，按持有结束 bar 的 close 出场。</p>
      {table_html(
        ["项目", "规则"],
        [
          [td("交易标的"), td("NQ 连续 1m Databento bars 聚合为 3m bars")],
          [td("交易时段"), td("US RTH: 13:30-20:00 UTC")],
          [td("入场方向"), td("+DI(30) > -DI(30) 且 close 上涨做多；-DI(30) > +DI(30) 且 close 下跌做空")],
          [td("趋势过滤"), td("ADX(30) >= 26")],
          [td("入场价格"), td("信号下一根 3m bar open")],
          [td("出场规则"), td("固定持有 60 分钟，time exit")],
          [td("成本假设"), td(f"{format_number(costs.round_trip_cost_points, 3)} points round trip，含 1 tick/side 滑点和 $2.50/contract commission")],
        ],
      )}
    </section>

    <section>
      <h2>资金曲线</h2>
      {line_svg("累计净点数 vs 交易序列", seq_points, "#0f766e", "#0f766e", "equity points", f"终点 {format_signed(float(summary['net_points']))} pts")}
      {line_svg("累计净点数 vs 日期", time_points, "#1d4ed8", "#1d4ed8", "equity points", f"{data_start} 至 {data_end}")}
      {line_svg("回撤曲线 vs 交易序列", drawdown_points, "#b91c1c", "#b91c1c", "drawdown points", f"最大回撤 {format_number(float(summary['max_drawdown_points']))} pts")}
    </section>

    <section>
      <h2>年度收益</h2>
      {bar_svg("年度净点数", [str(int(value)) for value in yearly["year"].tolist()], [float(value) for value in yearly["net_points"].tolist()])}
      {table_html(["年份", "交易数", "净点数", "净美元", "胜率", "平均点数", "最大单笔亏损"], yearly_rows)}
    </section>

    <section>
      <h2>月度收益</h2>
      <p>下表显示最近 36 个月。完整月度数据已导出到 <code>{html.escape(str(MONTHLY_PATH.relative_to(ROOT_DIR)))}</code>。</p>
      {bar_svg("最近 36 个月净点数", monthly_tail["month"].tolist(), [float(value) for value in monthly_tail["net_points"].tolist()])}
      {table_html(["月份", "交易数", "净点数", "净美元", "胜率", "平均点数", "最大单笔亏损"], monthly_rows)}
    </section>

    <section>
      <h2>稳定性审计</h2>
      <div class="metric-grid">
        {metric_card("正收益年份", f"{int((yearly['net_points'] > 0).sum())}/{len(yearly)}", f"{pct(positive_year_rate)}")}
        {metric_card("正收益月份", f"{int((monthly['net_points'] > 0).sum())}/{len(monthly)}", f"{pct(positive_month_rate)}")}
        {metric_card("最佳月份", f"{best_month['month']}", format_signed(float(best_month["net_points"])) + " pts", "positive")}
        {metric_card("最差月份", f"{worst_month['month']}", format_signed(float(worst_month["net_points"])) + " pts", "negative")}
        {metric_card("90天正窗口", f"{window['positive_windows']}/{window['windows']}", pct(float(window["positive_rate"])))}
        {metric_card("最差90天窗口", format_signed(float(window["worst_window"])), "points", "negative")}
      </div>
      {table_html(
        ["样本", "交易数", "净点数", "PF", "最大回撤", "前半段", "后半段"],
        [
          [
            td("2025-01-01 至 2026-04-28"),
            td(f"{int(recent_2025['trades']):,}", "numeric"),
            td(format_signed(float(recent_2025["net_points"])), f"numeric {css_class(float(recent_2025['net_points']))}"),
            td(format_number(float(recent_2025["profit_factor"]), 3), "numeric"),
            td(format_number(float(recent_2025["max_drawdown_points"])), "numeric"),
            td(format_signed(float(recent_2025["first_half_points"])), f"numeric {css_class(float(recent_2025['first_half_points']))}"),
            td(format_signed(float(recent_2025["second_half_points"])), f"numeric {css_class(float(recent_2025['second_half_points']))}"),
          ],
          [
            td("2025-04-28 至 2026-04-28"),
            td(f"{int(recent_12m['trades']):,}", "numeric"),
            td(format_signed(float(recent_12m["net_points"])), f"numeric {css_class(float(recent_12m['net_points']))}"),
            td(format_number(float(recent_12m["profit_factor"]), 3), "numeric"),
            td(format_number(float(recent_12m["max_drawdown_points"])), "numeric"),
            td(format_signed(float(recent_12m["first_half_points"])), f"numeric {css_class(float(recent_12m['first_half_points']))}"),
            td(format_signed(float(recent_12m["second_half_points"])), f"numeric {css_class(float(recent_12m['second_half_points']))}"),
          ],
        ],
      )}
    </section>

    <section>
      <h2>成本敏感性</h2>
      <p>滑点从 1 tick/side 提高到 3 tick/side 后，策略仍为正，但 PF 和收益回撤比会下降。</p>
      {table_html(["slippage ticks / side", "round-trip cost pts", "净点数", "PF", "最大回撤"], cost_rows)}
    </section>

    <section>
      <h2>交易分布</h2>
      {table_html(["方向", "交易数", "净点数", "胜率", "平均点数"], direction_rows)}
      {table_html(
        ["指标", "数值"],
        [
          [td("平均每笔净点数"), td(format_number(float(summary["avg_points"])), "numeric")],
          [td("5% 分位单笔损益"), td(format_number(float(summary["tail_loss_p05"])), "numeric negative")],
          [td("最大单笔亏损"), td(format_number(float(summary["worst_trade_points"])), "numeric negative")],
          [td("前半样本净点数"), td(format_signed(float(summary["first_half_points"])), f"numeric {css_class(float(summary['first_half_points']))}")],
          [td("后半样本净点数"), td(format_signed(float(summary["second_half_points"])), f"numeric {css_class(float(summary['second_half_points']))}")],
          [td("分半稳定度"), td(format_number(float(summary["stability"]), 3), "numeric")],
        ],
      )}
    </section>

    <section>
      <h2>优点与缺点</h2>
      <div class="grid-2">
        <div class="callout">
          <h3>优点</h3>
          <ul>
            <li>规则简单，只有趋势强度、方向和固定持有时间，易复现。</li>
            <li>多空都参与，收益不完全依赖单边牛市。</li>
            <li>全样本、每年、最近 12 个月和更严成本下均为正。</li>
            <li>参数邻域存在多个正收益组合，降低单点过拟合嫌疑。</li>
            <li>交易频率适中，3m bar 比 1m 噪声更低。</li>
          </ul>
        </div>
        <div class="callout risk">
          <h3>缺点</h3>
          <ul>
            <li>PF 约 1.18，优势不厚，执行成本上升会明显压缩收益。</li>
            <li>固定 time exit 没有显式止损，单笔尾部亏损可能较大。</li>
            <li>2024 和 2026 年内部分半不均衡，收益有阶段集中现象。</li>
            <li>bar 回测默认可在下一根 open 成交，未覆盖真实盘口排队和滑点扩张。</li>
            <li>当前只是策略候选，还缺少组合仓位、日亏损限制和上线适配。</li>
          </ul>
        </div>
      </div>
    </section>

    <section>
      <h2>实盘前检查清单</h2>
      <div class="callout note">
        <ul>
          <li>用真实合约 roll 日历复核连续合约拼接是否影响入场和出场。</li>
          <li>把成本模型升级为按波动、成交量和时段变化的滑点模型。</li>
          <li>增加硬风控：单笔最大亏损、日亏损、连续亏损暂停、事件日过滤。</li>
          <li>先在 paper 或 MNQ 上运行至少 2-4 周，比较实际成交价与 bar open 假设偏差。</li>
          <li>任何新增止损止盈或动态出场，都必须重新做 walk-forward 和最近 OOS。</li>
        </ul>
      </div>
    </section>

    <section class="sources">
      <h2>数据与来源</h2>
      <p>本地数据：<code>data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip</code>，连续 NQ 1m bars 聚合 3m。</p>
      <p>生成脚本：<code>scripts/generate_nq_adx_di_strategy_html_report.py</code>。</p>
      <p>交易明细导出：<code>{html.escape(str(TRADES_PATH.relative_to(ROOT_DIR)))}</code>。</p>
      <p>技术定义参考：ADX/DMI、VWAP、Price Channels、Moving Average Crossover 来自 StockCharts ChartSchool；time-series momentum 和 ORB 候选来自 SSRN 研究资料。结论以本地 Databento 回测为准。</p>
    </section>
  </main>
  <footer>
    <p>研究级报告，不构成投资建议。历史回测不代表未来收益。</p>
  </footer>
</body>
</html>
"""
    evidence = {
        "candidate": candidate.name,
        "report": str(REPORT_PATH),
        "trades": int(summary["trades"]),
        "net_points": float(summary["net_points"]),
        "profit_factor": float(summary["profit_factor"]),
        "max_drawdown_points": float(summary["max_drawdown_points"]),
        "monthly_rows": int(len(monthly)),
        "yearly_rows": int(len(yearly)),
        "positive_month_rate": positive_month_rate,
        "positive_year_rate": positive_year_rate,
    }
    return html_text, evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an HTML report for the NQ 3m ADX/DI trend strategy.")
    parser.add_argument("--start-date", default="2021-04-28")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-short-trend-base-cache.pkl")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--slippage-ticks-per-side", type=float, default=1.0)
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()

    html_text, evidence = build_report(args)
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_text, encoding="utf-8")
    evidence["report"] = str(output)
    print(evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
