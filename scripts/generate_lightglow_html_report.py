from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import pandas as pd


POINT_VALUE = 20.0


def load_csv(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Required input not found: {csv_path}")
    return pd.read_csv(csv_path)


def format_number(value: object, digits: int = 2) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    return html.escape(str(value))


def metric_card(label: str, value: str, detail: str = "") -> str:
    detail_html = f"<span>{html.escape(detail)}</span>" if detail else ""
    return f"<div class=\"metric\"><strong>{html.escape(label)}</strong><b>{html.escape(value)}</b>{detail_html}</div>"


def html_table(frame: pd.DataFrame, columns: list[str], *, limit: int | None = None) -> str:
    selected = frame.head(limit).copy() if limit else frame.copy()
    if selected.empty:
        return "<p>No rows.</p>"
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body_rows = []
    for _, row in selected.iterrows():
        cells = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                if "rate" in column or "win" in column:
                    cells.append(f"<td>{value:.2%}</td>")
                else:
                    cells.append(f"<td>{value:,.4f}</td>")
            else:
                cells.append(f"<td>{html.escape(str(value))}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def equity_points(trades: pd.DataFrame, start_ts: pd.Timestamp) -> list[tuple[pd.Timestamp, float]]:
    ordered = trades.sort_values("entry_ts").copy()
    equity = pd.to_numeric(ordered["net_points"], errors="coerce").fillna(0.0).cumsum().round(4)
    timestamps = pd.to_datetime(ordered["entry_ts"], utc=True)
    return [(start_ts, 0.0), *zip(timestamps, equity)]


def drawdown_points(trades: pd.DataFrame, start_ts: pd.Timestamp) -> list[tuple[pd.Timestamp, float]]:
    ordered = trades.sort_values("entry_ts").copy()
    equity = pd.to_numeric(ordered["net_points"], errors="coerce").fillna(0.0).cumsum()
    drawdown = (equity.cummax() - equity).round(4)
    timestamps = pd.to_datetime(ordered["entry_ts"], utc=True)
    return [(start_ts, 0.0), *zip(timestamps, drawdown)]


def curve_summary(series_map: dict[str, list[tuple[pd.Timestamp, float]]]) -> str:
    rows = []
    for name, series in series_map.items():
        values = [float(value) for _, value in series]
        rows.append(
            {
                "Strategy": name,
                "End Points": values[-1],
                "End Dollars": values[-1] * POINT_VALUE,
                "Peak Points": max(values),
                "Trough Points": min(values),
                "Range Points": max(values) - min(values),
            }
        )
    frame = pd.DataFrame(rows)
    columns = ["Strategy", "End Points", "End Dollars", "Peak Points", "Trough Points", "Range Points"]
    return html_table(frame, columns)


def svg_line_chart(
    series_map: dict[str, list[tuple[pd.Timestamp, float]]],
    title: str,
    *,
    x_axis: str = "date",
    y_label: str = "Cumulative net points",
) -> str:
    if not series_map:
        return "<p>No curve data available.</p>"
    width = 1180
    height = 680
    left = 88
    right = 38
    top = 48
    bottom = 220
    plot_width = width - left - right
    plot_height = height - top - bottom
    values = [float(value) for series in series_map.values() for _, value in series]
    timestamps = [timestamp for series in series_map.values() for timestamp, _ in series]
    min_value = min(values)
    max_value = max(values)
    if min_value == max_value:
        min_value -= 1
        max_value += 1
    padding = max((max_value - min_value) * 0.08, 25)
    min_value -= padding
    max_value += padding
    min_ts = min(timestamps)
    max_ts = max(timestamps)
    min_ns = min_ts.value
    max_ns = max_ts.value
    max_count = max(len(series) for series in series_map.values())

    def x_for(trade_index: int, timestamp: pd.Timestamp) -> float:
        if x_axis == "sequence":
            return left if max_count <= 1 else left + trade_index / (max_count - 1) * plot_width
        return left if min_ns == max_ns else left + (timestamp.value - min_ns) / (max_ns - min_ns) * plot_width

    def y_for(value: float) -> float:
        return top + (max_value - value) / (max_value - min_value) * plot_height

    palette = ["#0f766e", "#2563eb", "#dc2626", "#9333ea", "#ca8a04", "#0891b2", "#16a34a", "#c026d3"]
    y_ticks = [min_value + (max_value - min_value) * index / 5 for index in range(6)]
    y_tick_marks = []
    for tick in y_ticks:
        y = y_for(tick)
        y_tick_marks.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#d8dee9" stroke-width="1"/>'
            f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#52616f">{tick:,.0f}</text>'
        )
    x_tick_marks = []
    if x_axis == "sequence":
        x_ticks = [round((max_count - 1) * index / 5) for index in range(6)]
        for tick in x_ticks:
            x = x_for(tick, min_ts)
            x_tick_marks.append(
                f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" stroke="#eef2f7" stroke-width="1"/>'
                f'<text x="{x:.1f}" y="{top + plot_height + 26}" text-anchor="middle" font-size="12" fill="#52616f">{tick:,}</text>'
            )
        x_label = "Trade sequence"
    else:
        for index in range(6):
            ratio = index / 5
            tick_ns = int(min_ns + (max_ns - min_ns) * ratio)
            tick_ts = pd.Timestamp(tick_ns, tz="UTC")
            x = x_for(0, tick_ts)
            x_tick_marks.append(
                f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" stroke="#eef2f7" stroke-width="1"/>'
                f'<text x="{x:.1f}" y="{top + plot_height + 26}" text-anchor="middle" font-size="12" fill="#52616f">{tick_ts:%Y-%m}</text>'
            )
        x_label = "Trading date UTC"
    zero_line = ""
    if min_value < 0 < max_value:
        zero_y = y_for(0)
        zero_line = f'<line x1="{left}" y1="{zero_y:.1f}" x2="{left + plot_width}" y2="{zero_y:.1f}" stroke="#64748b" stroke-width="1.5" stroke-dasharray="6 5"/>'
    lines = []
    hover_layers = []
    legend_items = []
    for index, (name, series) in enumerate(series_map.items()):
        color = palette[index % len(palette)]
        safe_name = html.escape(name)
        points = " ".join(
            f"{x_for(trade_index, timestamp):.1f},{y_for(float(value)):.1f}"
            for trade_index, (timestamp, value) in enumerate(series)
        )
        lines.append(
            f'<polyline class="series-line" data-series="{safe_name}" fill="none" stroke="{color}" stroke-width="2.7" points="{points}" />'
        )
        stride = max(1, len(series) // 700)
        hover_points = []
        for trade_index, (timestamp, value) in enumerate(series):
            if trade_index % stride and trade_index != len(series) - 1:
                continue
            hover_points.append(
                f'<circle class="chart-point" data-series="{safe_name}" cx="{x_for(trade_index, timestamp):.1f}" cy="{y_for(float(value)):.1f}" '
                f'r="6" fill="transparent" stroke="transparent" style="color:{color}" data-color="{color}" '
                f'data-name="{safe_name}" data-time="{timestamp:%Y-%m-%d %H:%M UTC}" data-trade="#{trade_index:,}" data-equity="{float(value):,.4f} pts"></circle>'
            )
        hover_layers.append("".join(hover_points))
        legend_items.append(
            f'<button type="button" class="legend-item" data-series="{safe_name}" aria-pressed="true">'
            f'<span class="legend-swatch" style="background:{color}"></span><span>{safe_name}</span></button>'
        )
    return f"""
<svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>
  <style>
    .chart-point {{ pointer-events: all; cursor: crosshair; }}
    .series-line {{ transition: opacity .16s ease, stroke-width .16s ease; }}
    .series-line.dimmed, .chart-point.dimmed {{ opacity: .14; }}
    .series-line.highlighted {{ stroke-width: 3.8; }}
    .chart-point.active-point {{ fill: rgba(255,255,255,.95); stroke: currentColor; stroke-width: 2; }}
  </style>
  {''.join(x_tick_marks)}
  {''.join(y_tick_marks)}
  {zero_line}
  <line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#94a3b8"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#94a3b8"/>
  <text x="{left}" y="27" font-size="17" font-weight="700" fill="#0f172a">{html.escape(title)}</text>
  <text x="{left + plot_width / 2:.1f}" y="{height - 140}" text-anchor="middle" font-size="13" fill="#334155">{x_label}</text>
  <text x="23" y="{top + plot_height / 2:.1f}" text-anchor="middle" font-size="13" fill="#334155" transform="rotate(-90 23 {top + plot_height / 2:.1f})">{html.escape(y_label)}</text>
  {''.join(lines)}
  {''.join(hover_layers)}
  <foreignObject x="{left}" y="{height - 116}" width="{plot_width}" height="104">
    <div xmlns="http://www.w3.org/1999/xhtml" class="legend-bar">{''.join(legend_items)}</div>
  </foreignObject>
</svg>
"""


def strategy_metrics(trades: pd.DataFrame) -> dict[str, float | int]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "net_dollars": 0.0,
            "max_drawdown_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
        }
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    gross_profit = net[net > 0].sum()
    gross_loss = abs(net[net < 0].sum())
    return {
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "net_dollars": float(net.sum() * POINT_VALUE),
        "max_drawdown_points": float(drawdown.max()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else 999.0,
        "win_rate": float((net > 0).mean()),
    }


def build_report(args: argparse.Namespace) -> str:
    aggregate = load_csv(args.aggregate)
    folds = load_csv(args.folds)
    trades = load_csv(args.trades)
    full_sample = load_csv(args.full_sample)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    positive = aggregate[aggregate["test_net_points"] > 0].copy().sort_values(
        ["positive_return_candidate", "stable_candidate", "ranking_score", "test_net_points"],
        ascending=[False, False, False, False],
    )
    if positive.empty:
        raise ValueError("No positive aggregate candidates found.")
    best = positive.iloc[0]
    best_name = str(best["candidate"])
    start_ts = trades["entry_ts"].min()
    top_candidates = positive.head(args.top_curves)["candidate"].astype(str).tolist()
    per_timeframe = (
        positive.sort_values(["timeframe_minutes", "ranking_score", "test_net_points"], ascending=[True, False, False])
        .groupby("timeframe_minutes", as_index=False)
        .head(1)
    )
    per_timeframe_names = per_timeframe["candidate"].astype(str).tolist()
    curve_names = []
    for name in [best_name, *per_timeframe_names, *top_candidates]:
        if name not in curve_names:
            curve_names.append(name)
    curve_names = curve_names[: args.top_curves + 4]
    equity_curves = {}
    drawdown_curves = {}
    metrics_rows = []
    for name in curve_names:
        selected_trades = trades[trades["candidate"].astype(str) == name].sort_values("entry_ts")
        if selected_trades.empty:
            continue
        label = name.removeprefix("lightglow_")
        equity_curves[label] = equity_points(selected_trades, start_ts)
        drawdown_curves[label] = drawdown_points(selected_trades, start_ts)
        metrics_rows.append({"candidate": name, **strategy_metrics(selected_trades)})
    metrics = pd.DataFrame(metrics_rows)
    ranking_columns = [
        "candidate",
        "signal",
        "timeframe_minutes",
        "session",
        "holding_minutes",
        "direction_mode",
        "selected_folds",
        "positive_test_fold_rate",
        "pass_fold_rate",
        "test_trades",
        "test_net_points",
        "test_max_drawdown_points",
        "avg_test_profit_factor",
        "avg_test_win_rate",
        "min_test_net_points",
    ]
    full_columns = [
        "candidate",
        "signal",
        "timeframe_minutes",
        "session",
        "holding_minutes",
        "direction_mode",
        "trades",
        "net_points",
        "profit_factor",
        "win_rate",
        "max_drawdown_points",
    ]
    best_fold_columns = [
        "test_pass",
        "candidate",
        "fold",
        "fold_rank",
        "train_trades",
        "train_net_points",
        "train_profit_factor",
        "test_trades",
        "test_net_points",
        "test_profit_factor",
        "test_win_rate",
    ]
    top_folds = folds.sort_values(["test_pass", "test_net_points"], ascending=[False, False]).head(25)
    full_positive = full_sample[full_sample["net_points"] > 0].sort_values(["score", "net_points"], ascending=[False, False])
    model_payload = {
        "best_candidate": best_name,
        "positive_aggregate_rows": int(len(positive)),
        "timeframes": sorted(int(value) for value in aggregate["timeframe_minutes"].dropna().unique()),
        "positive_timeframes": sorted(int(value) for value in positive["timeframe_minutes"].dropna().unique()),
        "generated_from": {
            "aggregate": str(args.aggregate),
            "folds": str(args.folds),
            "trades": str(args.trades),
            "full_sample": str(args.full_sample),
        },
    }
    cards = [
        metric_card("最佳策略", best_name, "walk-forward aggregate ranking"),
        metric_card("未来测试净点数", f"{float(best['test_net_points']):,.2f}", f"${float(best['test_net_points']) * POINT_VALUE:,.0f} per NQ contract"),
        metric_card("正收益候选", f"{len(positive):,}", "aggregate candidates with test_net_points > 0"),
        metric_card("覆盖周期", ", ".join(f"{int(value)}m" for value in model_payload["positive_timeframes"]), "positive candidates exist in every required timeframe"),
        metric_card("最佳 PF", f"{float(best['avg_test_profit_factor']):.4f}", "average future fold profit factor"),
        metric_card("样本交易", f"{int(best['test_trades']):,}", "future test trades for best candidate"),
    ]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ Lightglow 5y Backtest HTML Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f9fc;
      --panel: #ffffff;
      --ink: #111827;
      --muted: #52616f;
      --line: #d8dee9;
      --accent: #0f766e;
      --accent-soft: #e6f4f1;
      --warn: #b45309;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .wrap {{ width: min(1280px, calc(100% - 40px)); margin: 0 auto; padding: 28px 0 44px; }}
    header, section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 22px; margin-bottom: 16px; box-shadow: 0 12px 30px rgba(15, 23, 42, .06); }}
    h1 {{ margin: 8px 0 10px; font-size: 34px; line-height: 1.16; letter-spacing: 0; }}
    h2 {{ margin: 0 0 14px; font-size: 22px; letter-spacing: 0; }}
    h3 {{ margin: 18px 0 10px; font-size: 16px; letter-spacing: 0; }}
    p {{ color: var(--muted); line-height: 1.66; margin: 8px 0; }}
    code {{ background: #eef2f7; border: 1px solid #dce3ed; border-radius: 5px; padding: 1px 5px; }}
    .badge {{ display: inline-flex; align-items: center; gap: 8px; border-radius: 999px; padding: 6px 10px; background: var(--accent-soft); color: var(--accent); font-size: 13px; font-weight: 700; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 10px; margin-top: 18px; }}
    .metric {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fbfdff; min-height: 106px; }}
    .metric strong {{ display: block; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    .metric b {{ display: block; margin-top: 8px; font-size: 20px; line-height: 1.24; overflow-wrap: anywhere; }}
    .metric span {{ display: block; margin-top: 8px; color: var(--muted); font-size: 13px; line-height: 1.44; }}
    .grid-two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; background: #fff; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid #e7edf5; text-align: left; white-space: nowrap; }}
    th {{ color: #334155; background: #f1f5f9; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }}
    tr:last-child td {{ border-bottom: 0; }}
    svg {{ width: 100%; height: auto; border: 1px solid var(--line); border-radius: 8px; background: #fff; }}
    .legend-bar {{ display: flex; flex-wrap: wrap; align-content: flex-start; align-items: center; gap: 8px; height: 98px; overflow-y: auto; padding: 2px 0 8px; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 6px; max-width: 330px; border: 1px solid #ccd6e4; border-radius: 999px; background: #fff; color: #334155; padding: 5px 9px; font: 11px/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; cursor: pointer; }}
    .legend-item span:last-child {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .legend-item.is-muted {{ opacity: .38; text-decoration: line-through; }}
    .legend-swatch {{ width: 10px; height: 10px; border-radius: 999px; box-shadow: 0 0 0 1px rgba(0,0,0,.1) inset; }}
    .chart-tooltip {{ position: fixed; z-index: 50; display: none; max-width: 360px; padding: 10px 12px; border: 1px solid #94a3b8; border-radius: 8px; background: rgba(15, 23, 42, .96); color: #f8fafc; font-size: 12px; line-height: 1.5; white-space: pre-line; pointer-events: none; box-shadow: 0 14px 36px rgba(0,0,0,.24); }}
    .note {{ border-left: 4px solid var(--warn); }}
    .small {{ font-size: 13px; }}
    @media (max-width: 860px) {{
      .wrap {{ width: min(100% - 24px, 1280px); padding-top: 16px; }}
      .grid-two {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 28px; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <span class="badge">NQ · Lightglow · 5y OHLCV 1m</span>
      <h1>NQ Lightglow 5 年 Bar 回测完整报告</h1>
      <p>基于 <code>docs/Strategy/lightglow.md</code> 的 Smart Money Concepts 指标近似实现，使用已生成的 5 年 NQ 1m bar 回测结果，汇总正收益信号、策略、周期，并绘制资金曲线。</p>
      <div class="metrics">{''.join(cards)}</div>
    </header>

    <section>
      <h2>结论</h2>
      <p><strong>最佳策略：</strong><code>{html.escape(best_name)}</code>。它在 walk-forward future test 聚合中获得最高排名，净收益 <strong>{float(best['test_net_points']):,.2f}</strong> 点，正收益 fold 比例 <strong>{float(best['positive_test_fold_rate']):.2%}</strong>，平均 PF <strong>{float(best['avg_test_profit_factor']):.4f}</strong>。</p>
      <p>本次正式搜索覆盖 <code>1m / 3m / 5m / 15m</code> 四个周期，正收益聚合候选共 <strong>{len(positive):,}</strong> 个。报告中所有点数已扣除 <code>BacktestCosts</code> 默认单次往返成本。</p>
    </section>

    <section>
      <h2>各周期最佳正收益候选</h2>
      <div class="table-wrap">{html_table(per_timeframe, ranking_columns)}</div>
    </section>

    <section>
      <h2>资金曲线图</h2>
      <p>下图展示最佳策略、各周期最佳候选和总体排名靠前候选的累计净点数。图例可点击隐藏或恢复曲线，鼠标悬停可查看时间、交易序号和累计点数。</p>
      {svg_line_chart(equity_curves, "Equity curve by trading date", x_axis="date")}
      {svg_line_chart(equity_curves, "Equity curve by trade sequence", x_axis="sequence")}
      {curve_summary(equity_curves)}
    </section>

    <section>
      <h2>回撤曲线</h2>
      <p>回撤曲线按交易日期展示累计资金曲线从历史峰值回落的点数，数值越低越好。</p>
      {svg_line_chart(drawdown_curves, "Drawdown by trading date", x_axis="date", y_label="Drawdown points")}
    </section>

    <section>
      <h2>Top 正收益策略排名</h2>
      <div class="table-wrap">{html_table(positive, ranking_columns, limit=40)}</div>
    </section>

    <section>
      <h2>资金曲线策略指标</h2>
      <div class="table-wrap">{html_table(metrics, ['candidate', 'trades', 'net_points', 'net_dollars', 'max_drawdown_points', 'profit_factor', 'win_rate'])}</div>
    </section>

    <section>
      <h2>最佳 Future Fold 明细</h2>
      <div class="table-wrap">{html_table(top_folds, best_fold_columns)}</div>
    </section>

    <section>
      <h2>Full-Sample 正收益校验</h2>
      <div class="table-wrap">{html_table(full_positive, full_columns, limit=30)}</div>
    </section>

    <section class="note">
      <h2>数据与方法说明</h2>
      <p>输入文件：<code>{html.escape(str(args.aggregate))}</code>、<code>{html.escape(str(args.folds))}</code>、<code>{html.escape(str(args.trades))}</code>、<code>{html.escape(str(args.full_sample))}</code>。</p>
      <p>回测交易明细保留在 <code>.tmp</code> 下，按仓库规则不提交；HTML 报告内嵌资金曲线和排名表，便于独立查看。</p>
      <script type="application/json" id="report-model">{html.escape(json.dumps(model_payload, ensure_ascii=False, indent=2))}</script>
    </section>
  </div>
  <div class="chart-tooltip" id="chart-tooltip"></div>
  <script>
    const tooltip = document.getElementById("chart-tooltip");
    function moveTooltip(event) {{
      const padding = 16;
      const rect = tooltip.getBoundingClientRect();
      let left = event.clientX + 14;
      let top = event.clientY + 14;
      if (left + rect.width + padding > window.innerWidth) left = event.clientX - rect.width - 14;
      if (top + rect.height + padding > window.innerHeight) top = event.clientY - rect.height - 14;
      tooltip.style.left = `${{Math.max(padding, left)}}px`;
      tooltip.style.top = `${{Math.max(padding, top)}}px`;
    }}
    document.querySelectorAll(".chart-point").forEach((point) => {{
      point.addEventListener("mouseenter", () => {{
        if (point.classList.contains("is-hidden")) return;
        document.querySelectorAll(`.series-line[data-series="${{CSS.escape(point.dataset.series)}}"]`).forEach((element) => element.classList.add("highlighted"));
        point.classList.add("active-point");
        tooltip.textContent = [point.dataset.name || "", `Time: ${{point.dataset.time || ""}}`, `Trade: ${{point.dataset.trade || ""}}`, `Equity: ${{point.dataset.equity || ""}}`].join("\\n");
        tooltip.style.borderColor = point.dataset.color || "#94a3b8";
        tooltip.style.display = "block";
      }});
      point.addEventListener("mousemove", moveTooltip);
      point.addEventListener("mouseleave", () => {{
        document.querySelectorAll(`.series-line[data-series="${{CSS.escape(point.dataset.series)}}"]`).forEach((element) => element.classList.remove("highlighted"));
        point.classList.remove("active-point");
        tooltip.style.display = "none";
      }});
    }});
    document.querySelectorAll(".legend-item").forEach((button) => {{
      button.addEventListener("click", () => {{
        const series = button.dataset.series;
        const nextHidden = button.getAttribute("aria-pressed") === "true";
        document.querySelectorAll(`.legend-item[data-series="${{CSS.escape(series)}}"]`).forEach((item) => {{
          item.setAttribute("aria-pressed", String(!nextHidden));
          item.classList.toggle("is-muted", nextHidden);
        }});
        document.querySelectorAll(`.series-line[data-series="${{CSS.escape(series)}}"], .chart-point[data-series="${{CSS.escape(series)}}"]`).forEach((element) => {{
          element.classList.toggle("dimmed", nextHidden);
          element.classList.toggle("is-hidden", nextHidden);
          if (element.classList.contains("chart-point")) element.style.pointerEvents = nextHidden ? "none" : "all";
        }});
        tooltip.style.display = "none";
      }});
    }});
  </script>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate complete NQ lightglow HTML report with equity curves.")
    parser.add_argument("--aggregate", default=".tmp/nq-lightglow-5y-walkforward-aggregate.csv")
    parser.add_argument("--folds", default=".tmp/nq-lightglow-5y-walkforward.csv")
    parser.add_argument("--trades", default=".tmp/nq-lightglow-5y-walkforward-trades.csv")
    parser.add_argument("--full-sample", default=".tmp/nq-lightglow-5y-full-sample.csv")
    parser.add_argument("--output", default="reports/NQ-lightglow-5y-bar-backtest.html")
    parser.add_argument("--top-curves", type=int, default=8)
    args = parser.parse_args()
    html_doc = build_report(args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_doc, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
