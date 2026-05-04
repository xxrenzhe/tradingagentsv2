from __future__ import annotations

import argparse
import html
from pathlib import Path

import pandas as pd

from mine_mbp_advanced_patterns import build_advanced_trades, generate_advanced_specs
from tradingagents.backtesting.short_patterns import StrategySpec, evaluate_strategies, generate_strategy_specs


STRATEGY_SPECS = {
    "vwap_reclaim_lb5_thr0.0005_hold3_imb0.35": StrategySpec(
        "vwap_reclaim_lb5_thr0.0005_hold3_imb0.35",
        "vwap_reclaim",
        5,
        0.0005,
        3,
        imbalance_threshold=0.35,
        max_spread_quantile=0.75,
        min_depth_quantile=0.25,
    ),
    "vwap_reclaim_lb5_thr0.0002_hold3_imb0.35": StrategySpec(
        "vwap_reclaim_lb5_thr0.0002_hold3_imb0.35",
        "vwap_reclaim",
        5,
        0.0002,
        3,
        imbalance_threshold=0.35,
        max_spread_quantile=0.75,
        min_depth_quantile=0.25,
    ),
    "vwap_reclaim_lb10_thr0.0005_hold3_imb0.35": StrategySpec(
        "vwap_reclaim_lb10_thr0.0005_hold3_imb0.35",
        "vwap_reclaim",
        10,
        0.0005,
        3,
        imbalance_threshold=0.35,
        max_spread_quantile=0.75,
        min_depth_quantile=0.25,
    ),
    "mean_reversion_lb15_thr0.6_hold10_imb0.35": StrategySpec(
        "mean_reversion_lb15_thr0.6_hold10_imb0.35",
        "mean_reversion",
        15,
        0.6,
        10,
        imbalance_threshold=0.35,
        max_spread_quantile=0.75,
        min_depth_quantile=0.25,
    ),
    "mean_reversion_lb15_thr1.4_hold5": StrategySpec(
        "mean_reversion_lb15_thr1.4_hold5",
        "mean_reversion",
        15,
        1.4,
        5,
    ),
    "mean_reversion_lb5_thr1.4_hold10": StrategySpec(
        "mean_reversion_lb5_thr1.4_hold10",
        "mean_reversion",
        5,
        1.4,
        10,
    ),
}


def _load_features(path: Path) -> pd.DataFrame:
    cache = pd.read_pickle(path)
    if not cache:
        raise SystemExit(f"No feature cache entries found: {path}")
    frames = [features for features in cache.values() if isinstance(features, pd.DataFrame) and not features.empty]
    if not frames:
        raise SystemExit(f"Feature cache is empty: {path}")
    features = pd.concat(frames, ignore_index=True)
    features = features.sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    features["ts"] = pd.to_datetime(features["ts"], utc=True)
    features["return_1m"] = pd.to_numeric(features["Close"], errors="coerce").pct_change()
    features["realized_vol_30"] = features["return_1m"].rolling(30).std()
    return features


def _load_advanced_best(path: Path) -> pd.Series | None:
    if not path.exists():
        return None
    advanced = pd.read_csv(path)
    if advanced.empty:
        return None
    return advanced.iloc[0]


def _equity_points(trades: pd.DataFrame, start_ts: pd.Timestamp) -> list[tuple[pd.Timestamp, float]]:
    equity = trades["net_points"].cumsum().round(4)
    timestamps = pd.to_datetime(trades["entry_ts"], utc=True)
    return [(start_ts, 0.0), *zip(timestamps, equity)]


def _advanced_curves(
    features: pd.DataFrame,
    advanced_results: pd.DataFrame | None,
    top_n: int = 10,
) -> dict[str, list[tuple[pd.Timestamp, float]]]:
    if advanced_results is None or advanced_results.empty:
        return {}
    spec_lookup = {spec.name: spec for spec in generate_advanced_specs()}
    curves = {}
    for name in advanced_results.head(top_n)["name"]:
        spec = spec_lookup.get(name)
        if spec is None:
            continue
        trades = build_advanced_trades(features, spec)
        if not trades.empty:
            curves[f"Advanced: {name}"] = _equity_points(trades, features["ts"].min())
    return curves


def _equity_curve_summary(series_map: dict[str, list[tuple[pd.Timestamp, float]]]) -> str:
    rows = []
    for name, series in series_map.items():
        values = [value for _, value in series]
        rows.append(
            {
                "name": name,
                "end_points": values[-1],
                "peak_points": max(values),
                "trough_points": min(values),
                "points_range": max(values) - min(values),
                "avg_step": values[-1] / max(len(values) - 1, 1),
            }
        )
    display = pd.DataFrame(rows)
    for column in ["end_points", "peak_points", "trough_points", "points_range", "avg_step"]:
        display[column] = display[column].map(lambda value: f"{value:.4f}")
    display.columns = ["Strategy", "End Points", "Peak", "Trough", "Range", "Avg Step"]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def _svg_line_chart(series_map: dict[str, list[tuple[pd.Timestamp, float]]], title: str, x_axis: str) -> str:
    width = 1100
    height = 700
    left = 86
    right = 36
    top = 42
    bottom = 250
    plot_width = width - left - right
    plot_height = height - top - bottom
    values = [value for series in series_map.values() for _, value in series]
    timestamps = [timestamp for series in series_map.values() for timestamp, _ in series]
    min_value = min(values)
    max_value = max(values)
    if min_value == max_value:
        min_value -= 1
        max_value += 1
    value_padding = max((max_value - min_value) * 0.08, 25)
    min_value -= value_padding
    max_value += value_padding
    min_ts = min(timestamps)
    max_ts = max(timestamps)
    min_ns = min_ts.value
    max_ns = max_ts.value
    max_count = max(len(series) for series in series_map.values())
    tick_dates = sorted({timestamp.date() for timestamp in timestamps})
    date_tick_indexes = [round((len(tick_dates) - 1) * i / 5) for i in range(6)] if tick_dates else []
    x_tick_dates = [tick_dates[index] for index in dict.fromkeys(date_tick_indexes)]

    def x_for(trade_index: int, timestamp: pd.Timestamp) -> float:
        if x_axis == "sequence":
            return left if max_count <= 1 else left + trade_index / (max_count - 1) * plot_width
        return left if min_ns == max_ns else left + (timestamp.value - min_ns) / (max_ns - min_ns) * plot_width

    def y_for(value: float) -> float:
        return top + (max_value - value) / (max_value - min_value) * plot_height

    palette = ["#f97316", "#38bdf8", "#22c55e", "#ef4444", "#a78bfa", "#facc15", "#14b8a6", "#fb7185", "#84cc16", "#60a5fa", "#e879f9"]
    y_ticks = [min_value + (max_value - min_value) * i / 5 for i in range(6)]
    x_tick_marks = []
    if x_axis == "sequence":
        x_ticks = [round((max_count - 1) * i / 5) for i in range(6)]
        for tick in x_ticks:
            x = x_for(tick, min_ts)
            x_tick_marks.append(
                f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" stroke="#223149" stroke-width="1"/>'
                f'<text x="{x:.1f}" y="{top + plot_height + 24}" text-anchor="middle" font-size="12" fill="#a6b3c2">{tick:,}</text>'
            )
        x_axis_label = "Trade sequence"
    else:
        for tick_date in x_tick_dates:
            tick_ts = min(max(pd.Timestamp(tick_date, tz="UTC"), min_ts), max_ts)
            x = x_for(0, tick_ts)
            x_tick_marks.append(
                f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" stroke="#223149" stroke-width="1"/>'
                f'<text x="{x:.1f}" y="{top + plot_height + 24}" text-anchor="middle" font-size="12" fill="#a6b3c2">{tick_date:%m-%d}</text>'
            )
        x_axis_label = "Trading date (UTC)"
    y_tick_marks = []
    for tick in y_ticks:
        y = y_for(tick)
        y_tick_marks.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#223149" stroke-width="1"/>'
            f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#a6b3c2">{tick:,.0f}</text>'
        )
    zero_line = ""
    if min_value < 0 < max_value:
        zero_y = y_for(0)
        zero_line = (
            f'<line x1="{left}" y1="{zero_y:.1f}" x2="{left + plot_width}" y2="{zero_y:.1f}" '
            'stroke="#6b7280" stroke-width="1.5" stroke-dasharray="5 5"/>'
        )
    lines = []
    hover_layers = []
    legend_items = []
    for index, (name, series) in enumerate(series_map.items()):
        color = palette[index % len(palette)]
        safe_name = html.escape(name)
        line_points = " ".join(
            f"{x_for(trade_index, timestamp):.1f},{y_for(value):.1f}"
            for trade_index, (timestamp, value) in enumerate(series)
        )
        lines.append(
            f'<polyline class="series-line" data-series="{safe_name}" fill="none" stroke="{color}" stroke-width="2.6" points="{line_points}" />'
        )
        hover_points = []
        for trade_index, (timestamp, value) in enumerate(series):
            hover_points.append(
                f'<circle class="chart-point" data-series="{safe_name}" cx="{x_for(trade_index, timestamp):.1f}" cy="{y_for(value):.1f}" '
                f'r="6" fill="transparent" stroke="transparent" style="color:{color}" '
                f'data-color="{color}" data-name="{safe_name}" '
                f'data-time="{timestamp:%Y-%m-%d %H:%M UTC}" data-trade="#{trade_index:,}" '
                f'data-equity="{value:,.4f} pts"></circle>'
            )
        hover_layers.append("".join(hover_points))
        legend_items.append(
            f'<button type="button" class="legend-item" data-series="{safe_name}" aria-pressed="true">'
            f'<span class="legend-swatch" style="background:{color}"></span>'
            f'<span>{safe_name}</span></button>'
        )
    return f"""
<svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#0e1729"/>
  <style>
    .chart-point {{ pointer-events: all; cursor: crosshair; }}
    .series-line {{ transition: opacity .16s ease, stroke-width .16s ease; }}
    .series-line.dimmed, .chart-point.dimmed {{ opacity: .14; }}
    .series-line.highlighted {{ stroke-width: 3.6; }}
    .chart-point.active-point {{ fill: rgba(255,255,255,.95); stroke: currentColor; stroke-width: 2; }}
  </style>
  {''.join(x_tick_marks)}
  {''.join(y_tick_marks)}
  {zero_line}
  <line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#52606d"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#52606d"/>
  <text x="{left}" y="24" font-size="16" fill="#f5f7fa">{html.escape(title)}</text>
  <text x="{left + plot_width / 2:.1f}" y="{height - 154}" text-anchor="middle" font-size="13" fill="#cfe0f2">{x_axis_label}</text>
  <text x="22" y="{top + plot_height / 2:.1f}" text-anchor="middle" font-size="13" fill="#cfe0f2" transform="rotate(-90 22 {top + plot_height / 2:.1f})">Cumulative net points</text>
  {''.join(lines)}
  {''.join(hover_layers)}
  <foreignObject x="{left}" y="{height - 130}" width="{plot_width}" height="112">
    <div xmlns="http://www.w3.org/1999/xhtml" class="legend-bar">{''.join(legend_items)}</div>
  </foreignObject>
</svg>
"""


def _metrics_table(rows: pd.DataFrame) -> str:
    display = rows[
        [
            "name",
            "trades",
            "net_points",
            "max_drawdown_points",
            "profit_factor",
            "win_rate",
            "stability",
            "score",
        ]
    ].copy()
    display["win_rate"] = display["win_rate"].map(lambda value: f"{value:.2%}")
    for column in ["net_points", "max_drawdown_points", "profit_factor", "stability", "score"]:
        display[column] = display[column].map(lambda value: f"{value:.4f}")
    display.columns = ["Strategy", "Trades", "Net Points", "Max DD", "PF", "Win Rate", "Stability", "Score"]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def _advanced_metrics_table(rows: pd.DataFrame) -> str:
    display = rows[
        [
            "name",
            "trades",
            "net_points",
            "max_drawdown_points",
            "profit_factor",
            "win_rate",
            "stability",
            "score",
            "avg_holding_minutes",
            "exit_mode",
            "session",
            "volatility_filter",
            "early_exit_share",
        ]
    ].copy()
    display["win_rate"] = display["win_rate"].map(lambda value: f"{value:.2%}")
    display["early_exit_share"] = display["early_exit_share"].map(lambda value: f"{value:.2%}")
    for column in ["net_points", "max_drawdown_points", "profit_factor", "stability", "score", "avg_holding_minutes"]:
        display[column] = display[column].map(lambda value: f"{value:.4f}")
    display.columns = [
        "Strategy",
        "Trades",
        "Net Points",
        "Max DD",
        "PF",
        "Win Rate",
        "Stability",
        "Score",
        "Avg Hold",
        "Exit",
        "Session",
        "Vol Filter",
        "Early Exit",
    ]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def _advanced_section(advanced_results: pd.DataFrame | None, baseline: pd.Series) -> str:
    if advanced_results is None or advanced_results.empty:
        return """
    <section class="card">
      <h2>高级策略探索</h2>
      <p>尚未检测到 .tmp/mbp-advanced-patterns.csv。运行 scripts/mine_mbp_advanced_patterns.py 后，本节会自动展示灵活持仓、时段过滤和波动率过滤的探索结果。</p>
    </section>
"""
    advanced_top = advanced_results.head(10)
    best = advanced_results.iloc[0]
    delta_score = best["score"] - baseline["score"]
    delta_net = best["net_points"] - baseline["net_points"]
    verdict = (
        "高级策略的综合分数高于当前基础首选，值得作为新的候选重点复核。"
        if delta_score > 0
        else "高级策略暂未超过当前基础首选，更多是用于理解哪些维度有帮助。"
    )
    return f"""
    <section class="card">
      <h2>高级策略探索</h2>
      <p>本节探索灵活持仓时间、反向信号/VWAP 回穿提前退出、交易时段过滤、波动率分层和止盈止损组合。高级搜索结果文件：<code>.tmp/mbp-advanced-patterns.csv</code>；最佳策略逐笔交易：<code>.tmp/mbp-advanced-patterns-trades.csv</code>。</p>
      <p><strong>当前结论：</strong>{verdict} 高级最佳策略相对基础首选的 Score 差值为 {delta_score:.4f}，Net Points 差值为 {delta_net:.3f}。</p>
      {_advanced_metrics_table(advanced_top)}
    </section>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate full MBP-history HTML strategy report.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--full-results", default=".tmp/mbp-history-patterns-full.csv")
    parser.add_argument("--old-results", default=".tmp/mbp-history-three-strategy-validation.csv")
    parser.add_argument("--advanced-results", default=".tmp/mbp-advanced-patterns.csv")
    parser.add_argument("--output", default="reports/NQM6-mbp-history-strategy-report.html")
    args = parser.parse_args()

    features = _load_features(Path(args.features_cache))
    full_results = pd.read_csv(args.full_results)
    old_results = pd.read_csv(args.old_results)
    advanced_path = Path(args.advanced_results)
    advanced_results = pd.read_csv(advanced_path) if advanced_path.exists() else None
    selected_names = full_results.head(10)["name"].tolist()
    spec_lookup = {spec.name: spec for spec in [*STRATEGY_SPECS.values(), *generate_strategy_specs()]}
    missing_specs = [name for name in selected_names if name not in spec_lookup]
    if missing_specs:
        raise SystemExit(f"Missing strategy specs for: {', '.join(missing_specs)}")
    specs = [spec_lookup[name] for name in selected_names]
    _, trades_by_name = evaluate_strategies(features, specs=specs, min_trades=1)

    base_curves = {name: _equity_points(trades_by_name[name], features["ts"].min()) for name in selected_names}
    advanced_curves = _advanced_curves(features, advanced_results, top_n=10)
    curves = dict(base_curves)
    if advanced_results is not None and not advanced_results.empty:
        advanced_best = advanced_results.iloc[0]
        advanced_name = advanced_best["name"]
        advanced_trades_path = Path(".tmp/mbp-advanced-patterns-trades.csv")
        if advanced_trades_path.exists():
            advanced_trades = pd.read_csv(advanced_trades_path)
            if not advanced_trades.empty:
                curves[f"Advanced: {advanced_name}"] = _equity_points(advanced_trades, features["ts"].min())
    full_top = full_results.head(10)
    recommendation = full_results.iloc[0]
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NQM6 Full MBP History Strategy Report</title>
  <style>
    body {{ margin: 0; padding: 28px; background: #08111f; color: #e8eef6; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 1220px; margin: 0 auto; }}
    .card {{ background: rgba(17, 26, 46, .92); border: 1px solid #26344e; border-radius: 18px; padding: 20px; margin-bottom: 18px; box-shadow: 0 16px 50px rgba(0,0,0,.28); overflow-x: auto; }}
    h1, h2 {{ margin: 0 0 12px; }}
    p {{ color: #a6b3c2; line-height: 1.65; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #26344e; text-align: left; }}
    th {{ color: #cfe0f2; text-transform: uppercase; letter-spacing: .04em; font-size: 12px; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }}
    .metric {{ border: 1px solid #26344e; border-radius: 12px; padding: 12px; background: rgba(8, 17, 31, .42); }}
    .metric strong {{ display: block; margin-bottom: 6px; color: #f5f7fa; }}
    .metric span {{ color: #a6b3c2; line-height: 1.55; }}
    svg {{ width: 100%; height: auto; border-radius: 14px; overflow: hidden; }}
    .chart-tooltip {{ position: fixed; z-index: 50; display: none; max-width: 360px; padding: 10px 12px; border: 1px solid #38506f; border-radius: 10px; background: rgba(8, 17, 31, .96); color: #f5f7fa; font-size: 12px; line-height: 1.5; white-space: pre-line; pointer-events: none; box-shadow: 0 14px 36px rgba(0,0,0,.35); }}
    .legend-bar {{ display: flex; flex-wrap: wrap; align-content: flex-start; align-items: center; gap: 8px; height: 106px; overflow-y: auto; padding: 2px 0 8px; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 6px; flex: 0 1 auto; max-width: 310px; border: 1px solid #34445f; border-radius: 999px; background: rgba(8, 17, 31, .72); color: #d7e1ea; padding: 5px 9px; font: 11px/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; cursor: pointer; }}
    .legend-item span:last-child {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .legend-item.is-muted {{ opacity: .38; text-decoration: line-through; }}
    .legend-swatch {{ width: 10px; height: 10px; border-radius: 999px; box-shadow: 0 0 0 1px rgba(255,255,255,.18) inset; }}
    .badge {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: rgba(56,189,248,.14); color: #7dd3fc; margin-bottom: 10px; }}
    .warning {{ border-left: 4px solid #f97316; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <span class="badge">Full MBP History · NQM6</span>
      <h1>NQM6 完整 MBP 历史策略报告</h1>
      <p>数据范围：{features['ts'].min()} 至 {features['ts'].max()}；分钟特征数：{len(features):,}。本报告基于 52 个交易日的 MBP-derived 1m 特征，而不是单日 bar 回测。</p>
    </section>
    <section class="card">
      <h2>完整历史 Top 10</h2>
      {_metrics_table(full_top)}
    </section>
    <section class="card">
      <h2>指标说明</h2>
      <div class="metric-grid">
        <div class="metric"><strong>Trades</strong><span>交易次数。不是越大越好；样本太少可信度低，样本太多可能代表策略过于频繁，需要结合成本和回撤看。</span></div>
        <div class="metric"><strong>Net Points</strong><span>扣除滑点和手续费后的累计点数，越大越好；这是最终收益口径。</span></div>
        <div class="metric"><strong>Max DD</strong><span>最大回撤点数，越小越好；代表资金曲线从峰值到低谷的最大损失压力。</span></div>
        <div class="metric"><strong>PF</strong><span>Profit Factor，总盈利除以总亏损，越大越好；大于 1 表示盈利额超过亏损额。</span></div>
        <div class="metric"><strong>Win Rate</strong><span>盈利交易占比，通常越高越好，但不能单独判断策略优劣；低胜率也可能靠更大的盈亏比盈利。</span></div>
        <div class="metric"><strong>Stability</strong><span>前半段和后半段收益的一致性，越接近 1 越好；接近 0 表示收益集中在某一段或样本外不稳定。</span></div>
        <div class="metric"><strong>Score</strong><span>综合排序分数，越大越好；它把净收益、回撤、尾部亏损、交易数和稳定性合成一个风险调整指标。</span></div>
      </div>
    </section>
    <section class="card">
      <h2>资金曲线对比</h2>
      <p>图中显示完整两个月回测的基础 Top 10 策略，并额外加入当前最佳高级候选。第一张图按交易次数对齐，第二张图按实际交易日期展开。</p>
      {_svg_line_chart(curves, "Equity curves by trade sequence (net points)", "sequence")}
      {_svg_line_chart(curves, "Equity curves by trading date (net points)", "date")}
      {_equity_curve_summary(curves)}
    </section>
    <section class="card">
      <h2>高级策略 Top 10 资金曲线</h2>
      <p>本节只显示高级搜索 Top 10 策略，避免它们在基础 Top 10 曲线中被淹没。第一张图按交易次数对齐，第二张图按实际交易日期展开。</p>
      {_svg_line_chart(advanced_curves, "Advanced Top 10 equity by trade sequence (net points)", "sequence") if advanced_curves else "<p>未找到可绘制的高级策略资金曲线。</p>"}
      {_svg_line_chart(advanced_curves, "Advanced Top 10 equity by trading date (net points)", "date") if advanced_curves else ""}
      {_equity_curve_summary(advanced_curves) if advanced_curves else ""}
    </section>
    {_advanced_section(advanced_results, recommendation)}
    <section class="card warning">
      <h2>推荐</h2>
      <p><strong>推荐策略：</strong>{html.escape(recommendation['name'])}</p>
      <p>理由：它在完整两个月上获得最高风险调整分数，交易数 {int(recommendation['trades']):,}，净收益 {recommendation['net_points']:.3f} 点，最大回撤 {recommendation['max_drawdown_points']:.3f} 点，PF {recommendation['profit_factor']:.4f}，稳定性 {recommendation['stability']:.4f}。此前三条 mean-reversion 单日候选在完整样本中全部转负，不能继续作为推荐策略。</p>
    </section>
    <section class="card">
      <h2>此前三条单日候选的完整历史验证</h2>
      {_metrics_table(old_results)}
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
      if (left + rect.width + padding > window.innerWidth) {{
        left = event.clientX - rect.width - 14;
      }}
      if (top + rect.height + padding > window.innerHeight) {{
        top = event.clientY - rect.height - 14;
      }}
      tooltip.style.left = `${{Math.max(padding, left)}}px`;
      tooltip.style.top = `${{Math.max(padding, top)}}px`;
    }}

    document.querySelectorAll(".chart-point").forEach((point) => {{
      point.addEventListener("mouseenter", () => {{
        if (point.classList.contains("is-hidden")) {{
          return;
        }}
        document.querySelectorAll(`.series-line[data-series="${{CSS.escape(point.dataset.series)}}"]`).forEach((element) => {{
          element.classList.add("highlighted");
        }});
        point.classList.add("active-point");
        tooltip.textContent = [
          point.dataset.name || "",
          `Time: ${{point.dataset.time || ""}}`,
          `Trade: ${{point.dataset.trade || ""}}`,
          `Equity: ${{point.dataset.equity || ""}}`,
        ].join("\\n");
        tooltip.style.borderColor = point.dataset.color || "#38506f";
        tooltip.style.display = "block";
      }});
      point.addEventListener("mousemove", (event) => {{
        moveTooltip(event);
      }});
      point.addEventListener("mouseleave", () => {{
        document.querySelectorAll(`.series-line[data-series="${{CSS.escape(point.dataset.series)}}"]`).forEach((element) => {{
          element.classList.remove("highlighted");
        }});
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
          if (element.classList.contains("chart-point")) {{
            element.style.pointerEvents = nextHidden ? "none" : "all";
          }}
        }});
        tooltip.style.display = "none";
      }});
    }});
  </script>
</body>
</html>
"""
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_doc, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
