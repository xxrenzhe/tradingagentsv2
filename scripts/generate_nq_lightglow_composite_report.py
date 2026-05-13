from __future__ import annotations

import argparse
import html
import json
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_COMPOSITE_TRADES = ".tmp/nq-composite-with-lightglow-selected.csv"
DEFAULT_OOS_TRADES = ".tmp/nq-lightglow-oos2022-selected.csv"
DEFAULT_RANKING = ".tmp/nq-composite-with-lightglow-ranking.csv"
DEFAULT_COMPONENTS = ".tmp/nq-composite-with-lightglow-components.csv"
DEFAULT_BARS = ".tmp/nq-2020-final-report-bars.pkl"
DEFAULT_REPORT = "reports/NQ-lightglow-composite-strategy-report.html"
DEFAULT_SUMMARY = ".tmp/nq-lightglow-composite-report-summary.json"


def esc(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return html.escape(str(value), quote=True)


def as_float(value: object, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def read_trades(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    frame["exit_ts"] = pd.to_datetime(frame["exit_ts"], utc=True)
    frame["net_points"] = pd.to_numeric(frame["net_points"], errors="coerce").fillna(0.0)
    if "gross_points" in frame.columns:
        frame["gross_points"] = pd.to_numeric(frame["gross_points"], errors="coerce").fillna(frame["net_points"])
    else:
        frame["gross_points"] = frame["net_points"]
    if "direction" in frame.columns:
        frame["direction"] = pd.to_numeric(frame["direction"], errors="coerce").fillna(0).astype(int)
    else:
        frame["direction"] = 0
    if "risk_weight" in frame.columns:
        frame["risk_weight"] = pd.to_numeric(frame["risk_weight"], errors="coerce").fillna(1.0)
    else:
        frame["risk_weight"] = 1.0
    return frame.sort_values(["entry_ts", "exit_ts"]).reset_index(drop=True)


def load_bars(path: str | Path) -> pd.DataFrame:
    with Path(path).open("rb") as file:
        payload = pickle.load(file)
    if isinstance(payload, dict):
        bars = payload.get("bars", payload.get("features"))
    else:
        bars = payload
    if not isinstance(bars, pd.DataFrame):
        raise TypeError(f"Unsupported bars payload in {path}")
    frame = bars.copy()
    if "ts" not in frame.columns:
        raise ValueError("bars must include a ts column")
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        if column not in frame.columns:
            raise ValueError(f"bars missing {column}")
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values("ts").reset_index(drop=True)


def profit_factor(points: pd.Series) -> float:
    wins = points[points > 0].sum()
    losses = -points[points < 0].sum()
    if losses == 0:
        return 999.0 if wins > 0 else 0.0
    return float(wins / losses)


def max_drawdown(points: pd.Series) -> float:
    if points.empty:
        return 0.0
    equity = points.cumsum()
    return float((equity.cummax() - equity).max())


def summarize_trades(trades: pd.DataFrame, *, risk_budgeted: bool = False) -> dict[str, float]:
    if trades.empty:
        return {
            "trades": 0.0,
            "net_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "payoff_ratio": 0.0,
            "avg_points": 0.0,
            "max_drawdown_points": 0.0,
            "net_to_drawdown": 0.0,
            "min_full_year_trades": 0.0,
            "min_full_year_net_points": 0.0,
            "positive_full_year_net_rate": 0.0,
        }
    points = trades["net_points"] * trades["risk_weight"] if risk_budgeted else trades["net_points"]
    points = pd.to_numeric(points, errors="coerce").fillna(0.0)
    wins = points[points > 0]
    losses = points[points < 0]
    yearly = points.groupby(trades["entry_ts"].dt.year).agg(["count", "sum"])
    max_dd = max_drawdown(points)
    return {
        "trades": float(len(trades)),
        "net_points": float(points.sum()),
        "profit_factor": profit_factor(points),
        "win_rate": float((points > 0).mean()),
        "payoff_ratio": float(wins.mean() / -losses.mean()) if len(wins) and len(losses) else 0.0,
        "avg_points": float(points.mean()),
        "best_trade_points": float(points.max()),
        "worst_trade_points": float(points.min()),
        "max_drawdown_points": max_dd,
        "net_to_drawdown": float(points.sum() / max_dd) if max_dd else (999.0 if points.sum() > 0 else 0.0),
        "min_full_year_trades": float(yearly["count"].min()) if not yearly.empty else 0.0,
        "min_full_year_net_points": float(yearly["sum"].min()) if not yearly.empty else 0.0,
        "positive_full_year_net_rate": float((yearly["sum"] > 0).mean()) if not yearly.empty else 0.0,
    }


def annual_table(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    frame = trades.copy()
    frame["budgeted_points"] = frame["net_points"] * frame["risk_weight"]
    grouped = frame.groupby(frame["entry_ts"].dt.year).agg(
        trades=("net_points", "size"),
        net_points=("net_points", "sum"),
        budgeted_net_points=("budgeted_points", "sum"),
        win_rate=("net_points", lambda value: float((value > 0).mean())),
    )
    grouped["annual_trade_floor_pass"] = grouped["trades"] >= 1001
    return grouped.reset_index(names="year")


def monthly_table(trades: pd.DataFrame, limit: int = 24) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    grouped = trades.groupby(trades["entry_ts"].dt.strftime("%Y-%m")).agg(
        trades=("net_points", "size"),
        net_points=("net_points", "sum"),
    )
    return grouped.tail(limit).reset_index(names="month")


def source_table(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    frame = trades.copy()
    frame["budgeted_points"] = frame["net_points"] * frame["risk_weight"]
    rows: list[dict[str, object]] = []
    for (source, label), group in frame.groupby(["strategy_source", "strategy_label"], dropna=False):
        rows.append(
            {
                "strategy_source": source,
                "strategy_label": label,
                "feature_family": group.get("feature_family", pd.Series([""])).iloc[0],
                "trades": len(group),
                "net_points": group["net_points"].sum(),
                "budgeted_net_points": group["budgeted_points"].sum(),
                "profit_factor": profit_factor(group["net_points"]),
                "win_rate": float((group["net_points"] > 0).mean()),
                "risk_weight": float(group["risk_weight"].median()),
            }
        )
    return pd.DataFrame(rows).sort_values("net_points", ascending=False)


def stress_table(trades: pd.DataFrame, extras: tuple[float, ...] = (0.0, 1.5, 2.5, 4.375)) -> pd.DataFrame:
    rows = []
    for extra in extras:
        stressed = trades["net_points"] - extra
        yearly = stressed.groupby(trades["entry_ts"].dt.year).sum()
        rows.append(
            {
                "extra_cost_points": extra,
                "trades": len(stressed),
                "net_points": stressed.sum(),
                "profit_factor": profit_factor(stressed),
                "win_rate": float((stressed > 0).mean()),
                "min_year_net_points": float(yearly.min()) if not yearly.empty else 0.0,
                "positive_year_rate": float((yearly > 0).mean()) if not yearly.empty else 0.0,
            }
        )
    return pd.DataFrame(rows)


def fmt_num(value: object, digits: int = 2) -> str:
    number = as_float(value)
    return f"{number:,.{digits}f}"


def fmt_signed(value: object, digits: int = 2) -> str:
    number = as_float(value)
    sign = "+" if number > 0 else ""
    return f"{sign}{number:,.{digits}f}"


def fmt_pct(value: object) -> str:
    return f"{as_float(value) * 100:.1f}%"


def fmt_value(column: str, value: object) -> str:
    if column in {"win_rate", "positive_full_year_net_rate", "positive_year_rate"}:
        return fmt_pct(value)
    if column in {"trades", "year"}:
        return f"{int(as_float(value)):,.0f}"
    if column.endswith("_pass"):
        return "PASS" if bool(value) else "FAIL"
    if column in {"profit_factor", "payoff_ratio", "net_to_drawdown", "risk_weight"}:
        return fmt_num(value, 3)
    if "points" in column or column in {"net_points", "budgeted_net_points", "avg_points"}:
        return fmt_signed(value, 2)
    return esc(value)


def html_table(frame: pd.DataFrame, columns: list[tuple[str, str]], limit: int | None = None) -> str:
    if frame.empty:
        return '<p class="empty">无数据。</p>'
    data = frame.head(limit) if limit else frame
    head = "".join(f"<th>{esc(label)}</th>" for _, label in columns)
    rows = []
    for _, row in data.iterrows():
        cells = []
        for key, _ in columns:
            text = fmt_value(key, row.get(key, ""))
            cls = "num" if key != "strategy_label" and key != "strategy_source" and key != "feature_family" else ""
            cells.append(f'<td class="{cls}">{text}</td>')
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def metric_card(label: str, value: str, note: str = "") -> str:
    return f"""
    <div class="metric">
      <small>{esc(label)}</small>
      <strong>{esc(value)}</strong>
      <span>{esc(note)}</span>
    </div>
    """


def equity_curve(trades: pd.DataFrame, *, risk_budgeted: bool = False) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["x", "equity"])
    frame = trades.sort_values(["entry_ts", "exit_ts"]).copy()
    points = frame["net_points"] * frame["risk_weight"] if risk_budgeted else frame["net_points"]
    return pd.DataFrame({"x": np.arange(1, len(frame) + 1), "equity": points.cumsum()})


def line_svg(points: pd.DataFrame, *, title: str, width: int = 980, height: int = 300) -> str:
    if points.empty:
        return '<p class="empty">无曲线数据。</p>'
    pad_left, pad_right, pad_top, pad_bottom = 68, 22, 24, 36
    values = pd.to_numeric(points["equity"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    y_min = min(0.0, float(np.nanmin(values)))
    y_max = max(0.0, float(np.nanmax(values)))
    if y_max <= y_min:
        y_max = y_min + 1.0
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom
    x_den = max(len(values) - 1, 1)

    def x_for(index: int) -> float:
        return pad_left + (index / x_den) * plot_w

    def y_for(value: float) -> float:
        return pad_top + (y_max - value) / (y_max - y_min) * plot_h

    coords = " ".join(f"{x_for(i):.1f},{y_for(value):.1f}" for i, value in enumerate(values))
    zero_y = y_for(0.0)
    return f"""
    <figure class="chart">
      <figcaption>{esc(title)}</figcaption>
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
        <rect x="0" y="0" width="{width}" height="{height}" fill="#fff" />
        <line x1="{pad_left}" y1="{zero_y:.1f}" x2="{width - pad_right}" y2="{zero_y:.1f}" stroke="#d7dee8" stroke-dasharray="5 5" />
        <line x1="{pad_left}" y1="{pad_top}" x2="{pad_left}" y2="{height - pad_bottom}" stroke="#a8b3bf" />
        <line x1="{pad_left}" y1="{height - pad_bottom}" x2="{width - pad_right}" y2="{height - pad_bottom}" stroke="#a8b3bf" />
        <polyline points="{coords}" fill="none" stroke="#0f766e" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" />
        <text x="8" y="{pad_top + 5}" font-size="12" fill="#607080">{y_max:,.0f}</text>
        <text x="8" y="{height - pad_bottom}" font-size="12" fill="#607080">{y_min:,.0f}</text>
      </svg>
    </figure>
    """


def bar_window_for_trade(bars: pd.DataFrame, trade: pd.Series, before: int = 80, after: int = 120) -> pd.DataFrame:
    entry_ts = pd.to_datetime(trade["entry_ts"], utc=True)
    exit_ts = pd.to_datetime(trade["exit_ts"], utc=True)
    entry_pos = int(bars["ts"].searchsorted(entry_ts, side="left"))
    exit_pos = int(bars["ts"].searchsorted(exit_ts, side="left"))
    start = max(0, entry_pos - before)
    end = min(len(bars), max(exit_pos + after, entry_pos + after))
    return bars.iloc[start:end].reset_index(drop=True)


def candlestick_svg(window: pd.DataFrame, trade: pd.Series, *, width: int = 980, height: int = 340) -> str:
    if window.empty:
        return '<p class="empty">无K线窗口。</p>'
    open_ = window["Open"].to_numpy(dtype=float)
    high = window["High"].to_numpy(dtype=float)
    low = window["Low"].to_numpy(dtype=float)
    close = window["Close"].to_numpy(dtype=float)
    entry_ts = pd.to_datetime(trade["entry_ts"], utc=True)
    exit_ts = pd.to_datetime(trade["exit_ts"], utc=True)
    entry_index = int(window["ts"].searchsorted(entry_ts, side="left"))
    exit_index = int(window["ts"].searchsorted(exit_ts, side="left"))
    pad_left, pad_right, pad_top, pad_bottom = 64, 18, 24, 34
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom
    y_min = float(np.nanmin(low))
    y_max = float(np.nanmax(high))
    y_pad = max((y_max - y_min) * 0.06, 1.0)
    y_min -= y_pad
    y_max += y_pad

    def x_for(index: int) -> float:
        return pad_left + (index + 0.5) * plot_w / max(len(window), 1)

    def y_for(price: float) -> float:
        return pad_top + (y_max - price) * plot_h / (y_max - y_min)

    candle_w = max(1.8, min(7.0, plot_w / max(len(window), 1) * 0.58))
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="trade candlestick chart">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
    ]
    for grid_price in np.linspace(y_min, y_max, 5):
        y = y_for(float(grid_price))
        parts.append(f'<line x1="{pad_left}" y1="{y:.1f}" x2="{width - pad_right}" y2="{y:.1f}" stroke="#edf2f7"/>')
        parts.append(f'<text x="7" y="{y + 4:.1f}" font-size="11" fill="#607080">{grid_price:.0f}</text>')
    for index in range(len(window)):
        x = x_for(index)
        color = "#0f766e" if close[index] >= open_[index] else "#b34242"
        y_high, y_low = y_for(high[index]), y_for(low[index])
        y_open, y_close = y_for(open_[index]), y_for(close[index])
        body_y = min(y_open, y_close)
        body_h = max(abs(y_close - y_open), 1.0)
        parts.append(f'<line x1="{x:.1f}" y1="{y_high:.1f}" x2="{x:.1f}" y2="{y_low:.1f}" stroke="{color}" stroke-width="1"/>')
        parts.append(
            f'<rect x="{x - candle_w / 2:.1f}" y="{body_y:.1f}" width="{candle_w:.1f}" height="{body_h:.1f}" fill="{color}" opacity="0.9"/>'
        )
    if 0 <= entry_index < len(window):
        x = x_for(entry_index)
        parts.append(f'<line x1="{x:.1f}" y1="{pad_top}" x2="{x:.1f}" y2="{height - pad_bottom}" stroke="#2563eb" stroke-width="2"/>')
        parts.append(f'<text x="{x + 5:.1f}" y="{pad_top + 13}" font-size="12" fill="#2563eb">ENTRY</text>')
    if 0 <= exit_index < len(window):
        x = x_for(exit_index)
        parts.append(f'<line x1="{x:.1f}" y1="{pad_top}" x2="{x:.1f}" y2="{height - pad_bottom}" stroke="#7c3aed" stroke-width="2"/>')
        parts.append(f'<text x="{x + 5:.1f}" y="{pad_top + 29}" font-size="12" fill="#7c3aed">EXIT</text>')
    parts.append("</svg>")
    return "".join(parts)


def trade_chart(title: str, trade: pd.Series, bars: pd.DataFrame) -> str:
    window = bar_window_for_trade(bars, trade)
    direction = "LONG" if int(trade.get("direction", 0)) > 0 else "SHORT"
    meta = (
        f"{direction} | {trade['entry_ts']} -> {trade['exit_ts']} | "
        f"entry {fmt_num(trade.get('entry_price'))}, exit {fmt_num(trade.get('exit_price'))}, "
        f"net {fmt_signed(trade.get('net_points'))} pts"
    )
    return f"""
    <figure class="chart">
      <figcaption>{esc(title)}</figcaption>
      <p class="muted">{esc(meta)}</p>
      {candlestick_svg(window, trade)}
    </figure>
    """


def build_report(
    *,
    composite_trades: pd.DataFrame,
    oos_trades: pd.DataFrame,
    bars: pd.DataFrame,
    ranking: pd.DataFrame,
    components: pd.DataFrame,
    generated_at: str,
    source_paths: dict[str, str],
) -> tuple[str, dict[str, Any]]:
    raw_summary = summarize_trades(composite_trades)
    budget_summary = summarize_trades(composite_trades, risk_budgeted=True)
    oos_summary = summarize_trades(oos_trades)
    annual = annual_table(composite_trades)
    recent_months = monthly_table(composite_trades)
    sources = source_table(composite_trades)
    stress = stress_table(oos_trades)
    best_trade = composite_trades.loc[composite_trades["net_points"].idxmax()]
    worst_trade = composite_trades.loc[composite_trades["net_points"].idxmin()]
    best_lightglow = oos_trades.loc[oos_trades["net_points"].idxmax()] if not oos_trades.empty else best_trade
    worst_lightglow = oos_trades.loc[oos_trades["net_points"].idxmin()] if not oos_trades.empty else worst_trade
    source_items = "".join(f"<li><code>{esc(name)}</code>: {esc(path)}</li>" for name, path in source_paths.items())
    top_ranking = ranking.head(8).copy() if not ranking.empty else pd.DataFrame()
    top_components = components.head(12).copy() if not components.empty else pd.DataFrame()

    cards = "".join(
        [
            metric_card("组合交易数", f"{int(raw_summary['trades']):,}", f"最低完整年 {int(raw_summary['min_full_year_trades']):,}"),
            metric_card("组合净点数", fmt_signed(raw_summary["net_points"]), "2020-2025 raw"),
            metric_card("组合 PF", fmt_num(raw_summary["profit_factor"], 3), f"胜率 {fmt_pct(raw_summary['win_rate'])}"),
            metric_card("风险预算净点", fmt_signed(budget_summary["net_points"]), f"PF {fmt_num(budget_summary['profit_factor'], 3)}"),
            metric_card("OOS Lightglow", fmt_signed(oos_summary["net_points"]), "2022-2025 only"),
            metric_card("OOS Lightglow PF", fmt_num(oos_summary["profit_factor"], 3), f"交易 {int(oos_summary['trades']):,}"),
        ]
    )

    css = """
    :root { color-scheme: light; --ink:#17212b; --muted:#5f6f7d; --line:#d8e0e8; --bg:#f5f7fb; --panel:#ffffff; --green:#0f766e; --red:#b34242; --blue:#2563eb; --amber:#a66f00; }
    * { box-sizing:border-box; }
    body { margin:0; color:var(--ink); background:var(--bg); font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    header { padding:34px min(5vw,58px) 26px; color:#f8fafc; background:#111827; }
    main { max-width:1280px; margin:0 auto; padding:26px min(5vw,58px) 60px; }
    h1 { margin:0 0 10px; font-size:36px; line-height:1.08; letter-spacing:0; }
    h2 { margin:0 0 12px; font-size:23px; letter-spacing:0; }
    h3 { margin:20px 0 8px; font-size:16px; letter-spacing:0; }
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
    .warn { border-left-color:var(--amber); background:#fff7e8; }
    .risk { border-left-color:var(--red); background:#fff0f0; }
    .two { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:16px; }
    .table-wrap { margin:12px 0; overflow-x:auto; border:1px solid var(--line); border-radius:8px; }
    table { width:100%; border-collapse:collapse; font-size:12px; background:#fff; }
    th, td { padding:8px 10px; border-bottom:1px solid #e7edf4; text-align:left; vertical-align:top; }
    th { background:#edf2f7; color:#475569; }
    td.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
    .chart { margin:14px 0; padding:14px; border:1px solid var(--line); border-radius:8px; background:#fff; overflow-x:auto; }
    figcaption { margin:0 0 8px; font-weight:700; }
    svg { width:100%; height:auto; display:block; }
    .muted, .empty, .sources { color:var(--muted); }
    .positive { color:var(--green); }
    .negative { color:var(--red); }
    @media (max-width:900px) { .two { grid-template-columns:1fr; } h1 { font-size:28px; } }
    """
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ Lightglow + Timecell 组合策略报告</title>
  <style>{css}</style>
</head>
<body>
  <header>
    <h1>NQ Lightglow + Timecell 组合策略报告</h1>
    <p class="subtitle">报告基于 2020 年之后 NQ 1 分钟 bar 的逐笔回测输出重算。核心组合为 <code>Stable 2020-2021 trained action map</code> Lightglow 研究信号叠加 <code>rollstable_trainpf105_timecell</code> 低风险覆盖信号。生成时间：{esc(generated_at)}。</p>
    <div class="grid">{cards}</div>
  </header>
  <main>
    <section>
      <h2>结论</h2>
      <div class="note">
        <p><strong>当前最有交易潜质的组合：</strong>Lightglow Premium/Discount 反转动作表作为主收益来源，roll-stable timecell 作为低权重覆盖来源。组合 2020-2025 共 {int(raw_summary['trades']):,} 笔，原始净点 {fmt_signed(raw_summary['net_points'])}，PF {fmt_num(raw_summary['profit_factor'], 3)}，每个完整年份交易数均超过 1000。</p>
        <p><strong>实盘定位：</strong>这是研究/纸盘候选，不是生产批准。主要原因是 Lightglow 主收益来自 2022-2025 OOS 的强表现，但仍要通过前推纸盘、执行滑点、延迟和拒单验证。</p>
      </div>
      <div class="note warn">
        <p><strong>为什么保留风险预算口径：</strong>timecell PF 较低但能增加年度覆盖，因此按 0.05 权重计入风险预算；Lightglow 权重为 1。预算口径用于判断“组合风险是否值得承担”，不是替代原始回测。</p>
      </div>
    </section>

    <section>
      <h2>交易原理</h2>
      <div class="two">
        <div class="note">
          <h3>Lightglow Premium/Discount 反转</h3>
          <p>用历史 K 线确认 swing、premium/discount zone、EMA 趋势、距离均线、ATR、量价 Z-score 与箱体位置。触发后不追随原始方向，而按 2020-2021 训练出的 month x weekday 动作表决定 reverse、native 或 skip。</p>
          <p>可交易行情特征包括：跌到 discount 后卖不动反弹、涨到 premium 后涨不动回落、量价背离、短动量过热后的均值修复，以及结构区间边缘的快速回归。</p>
        </div>
        <div class="note">
          <h3>Roll-stable Timecell 覆盖</h3>
          <p>使用 2010-2019 训练出的月份 x 小时方向图，并在 2020+ OOS 验证。它不是高 PF 主边，但提供稳定频率和跨年份覆盖，组合中只按 5% 风险预算计入。</p>
          <p>可交易行情特征是统计型时段偏置：不同月份、交易时段和日内流动性结构下，NQ 会表现出可重复但边际较薄的方向倾向。</p>
        </div>
      </div>
      <div class="note risk">
        <p><strong>无未来函数原则：</strong>报告使用的逐笔交易已经按下一根或确认后的 bar 执行；K 线图仅用于展示入场前后行情，不参与信号计算。Lightglow 仍需继续做专门的未来扰动泄漏审计和纸盘前推。</p>
      </div>
    </section>

    <section>
      <h2>回测结果</h2>
      <h3>完整年份表现</h3>
      {html_table(annual, [("year", "年份"), ("trades", "交易数"), ("net_points", "原始净点"), ("budgeted_net_points", "风险预算净点"), ("win_rate", "胜率"), ("annual_trade_floor_pass", "1000+交易")])}
      <h3>策略来源贡献</h3>
      {html_table(sources, [("strategy_source", "来源"), ("strategy_label", "策略"), ("feature_family", "行情特征"), ("trades", "交易数"), ("net_points", "原始净点"), ("budgeted_net_points", "预算净点"), ("profit_factor", "PF"), ("win_rate", "胜率"), ("risk_weight", "风险权重")])}
      <h3>Lightglow OOS 成本压力</h3>
      {html_table(stress, [("extra_cost_points", "额外每笔成本"), ("trades", "交易数"), ("net_points", "净点"), ("profit_factor", "PF"), ("win_rate", "胜率"), ("min_year_net_points", "最弱年份"), ("positive_year_rate", "正年份率")])}
    </section>

    <section>
      <h2>资金曲线</h2>
      {line_svg(equity_curve(composite_trades), title="组合原始累计净点")}
      {line_svg(equity_curve(composite_trades, risk_budgeted=True), title="组合风险预算累计净点")}
    </section>

    <section>
      <h2>最佳/最差交易 K 线图</h2>
      <h3>组合样本</h3>
      {html_table(pd.DataFrame([best_trade.to_dict() | {"case": "组合最佳"}, worst_trade.to_dict() | {"case": "组合最差"}]), [("case", "样本"), ("strategy_source", "来源"), ("strategy_label", "策略"), ("entry_ts", "入场"), ("exit_ts", "出场"), ("direction", "方向"), ("entry_price", "入场价"), ("exit_price", "出场价"), ("net_points", "净点")])}
      {trade_chart("组合最佳交易真实 1 分钟 K 线", best_trade, bars)}
      {trade_chart("组合最差交易真实 1 分钟 K 线", worst_trade, bars)}
      <h3>Lightglow OOS 样本</h3>
      {html_table(pd.DataFrame([best_lightglow.to_dict() | {"case": "Lightglow OOS 最佳"}, worst_lightglow.to_dict() | {"case": "Lightglow OOS 最差"}]), [("case", "样本"), ("entry_ts", "入场"), ("exit_ts", "出场"), ("direction", "方向"), ("entry_price", "入场价"), ("exit_price", "出场价"), ("net_points", "净点"), ("volume_z_60", "量能Z"), ("z_30", "价格Z"), ("box45_pos", "45m箱体位置")])}
      {trade_chart("Lightglow OOS 最佳交易真实 1 分钟 K 线", best_lightglow, bars)}
      {trade_chart("Lightglow OOS 最差交易真实 1 分钟 K 线", worst_lightglow, bars)}
    </section>

    <section>
      <h2>最近月度表现</h2>
      {html_table(recent_months, [("month", "月份"), ("trades", "交易数"), ("net_points", "净点")])}
    </section>

    <section>
      <h2>候选与组件审计</h2>
      <h3>组合排名</h3>
      {html_table(top_ranking, [("combo", "组合"), ("trades", "交易数"), ("net_points", "净点"), ("profit_factor", "PF"), ("risk_budgeted_net_points", "预算净点"), ("risk_budgeted_profit_factor", "预算PF"), ("min_full_year_trades", "最低年交易数"), ("annual_trade_floor_pass", "年度交易达标")])}
      <h3>组件候选</h3>
      {html_table(top_components, [("strategy_source", "来源"), ("strategy_label", "策略"), ("family", "家族"), ("trades", "交易数"), ("net_points", "净点"), ("profit_factor", "PF"), ("net_to_drawdown", "净值/回撤"), ("deployment_tier", "层级")])}
    </section>

    <section>
      <h2>风险和下一步</h2>
      <div class="note risk">
        <p><strong>主要风险：</strong>Lightglow 动作表可能存在 regime 依赖；timecell 边际薄，极端新闻时段可能出现大单笔亏损；真实滑点、延迟和成交质量尚未完全反映。</p>
        <p><strong>上线前必须做：</strong>独立泄漏审计、逐日纸盘前推、NQ/MNQ 合约换月执行检查、日亏损/连续亏损暂停、重叠信号限仓，以及更高成本压力测试。</p>
      </div>
    </section>

    <section>
      <h2>数据来源</h2>
      <ul class="sources">{source_items}</ul>
    </section>
  </main>
</body>
</html>
"""
    summary = {
        "raw_summary": raw_summary,
        "risk_budgeted_summary": budget_summary,
        "oos_lightglow_summary": oos_summary,
        "best_trade_net_points": float(best_trade["net_points"]),
        "worst_trade_net_points": float(worst_trade["net_points"]),
        "report_generated_at": generated_at,
    }
    return html_doc, summary


def write_report(args: argparse.Namespace) -> dict[str, Any]:
    composite_trades = read_trades(args.composite_trades)
    oos_trades = read_trades(args.oos_trades)
    bars = load_bars(args.bars)
    ranking = pd.read_csv(args.ranking) if Path(args.ranking).exists() else pd.DataFrame()
    components = pd.read_csv(args.components) if Path(args.components).exists() else pd.DataFrame()
    generated_at = args.generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    source_paths = {
        "composite_trades": args.composite_trades,
        "lightglow_oos_trades": args.oos_trades,
        "ranking": args.ranking,
        "components": args.components,
        "bars": args.bars,
    }
    html_doc, summary = build_report(
        composite_trades=composite_trades,
        oos_trades=oos_trades,
        bars=bars,
        ranking=ranking,
        components=components,
        generated_at=generated_at,
        source_paths=source_paths,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_doc, encoding="utf-8")
    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return {"output": str(output), "summary_output": str(summary_path), **summary}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate NQ Lightglow + timecell composite HTML report.")
    parser.add_argument("--composite-trades", default=DEFAULT_COMPOSITE_TRADES)
    parser.add_argument("--oos-trades", default=DEFAULT_OOS_TRADES)
    parser.add_argument("--ranking", default=DEFAULT_RANKING)
    parser.add_argument("--components", default=DEFAULT_COMPONENTS)
    parser.add_argument("--bars", default=DEFAULT_BARS)
    parser.add_argument("--output", default=DEFAULT_REPORT)
    parser.add_argument("--summary-output", default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at", default="")
    args = parser.parse_args()
    print(json.dumps(write_report(args), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
