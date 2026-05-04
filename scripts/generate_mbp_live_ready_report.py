from __future__ import annotations

import argparse
import html
from pathlib import Path

import pandas as pd

from generate_mbp_history_report import _equity_curve_summary, _load_features, _svg_line_chart
from mine_mbp_advanced_patterns import AdvancedStrategySpec, build_advanced_trades, generate_advanced_specs
from tradingagents.backtesting.short_patterns import StrategySpec, build_trades, generate_strategy_specs


def _fmt(value: float, decimals: int = 4) -> str:
    return f"{value:,.{decimals}f}"


def _is_missing(value: object) -> bool:
    return pd.isna(value)


def _float_or_none(value: object) -> float | None:
    if _is_missing(value):
        return None
    return float(value)


def _int_or_none(value: object) -> int | None:
    if _is_missing(value):
        return None
    return int(float(value))


def _table(rows: pd.DataFrame) -> str:
    columns = [
        "name",
        "source",
        "family",
        "full_trades",
        "full_net_points",
        "full_profit_factor",
        "positive_fold_rate",
        "positive_window_rate",
        "min_window_net_points",
        "worst_cost_net_points",
        "local_positive_rate",
        "local_rank_score",
        "live_ready",
        "live_score",
    ]
    display = rows[columns].copy()
    for column in ["positive_fold_rate", "positive_window_rate", "local_positive_rate"]:
        display[column] = display[column].map(lambda value: f"{value:.2%}")
    for column in [
        "full_net_points",
        "full_profit_factor",
        "min_window_net_points",
        "worst_cost_net_points",
        "local_rank_score",
        "live_score",
    ]:
        display[column] = display[column].map(lambda value: _fmt(float(value)))
    display.columns = [
        "Strategy",
        "Source",
        "Family",
        "Trades",
        "Net Points",
        "PF",
        "Positive Folds",
        "Positive Windows",
        "Worst Window",
        "3x Cost Net",
        "Local Positive",
        "Local Rank",
        "Live Ready",
        "Live Score",
    ]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def _cost_table(rows: pd.DataFrame) -> str:
    columns = [
        "name",
        "cost_1x_net_points",
        "cost_2x_net_points",
        "cost_3x_net_points",
        "cost_1x_score",
        "cost_2x_score",
        "cost_3x_score",
    ]
    display = rows[columns].copy()
    for column in columns:
        if column != "name":
            display[column] = display[column].map(lambda value: _fmt(float(value)))
    display.columns = ["Strategy", "1x Net", "2x Net", "3x Net", "1x Score", "2x Score", "3x Score"]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def _equity_points(trades: pd.DataFrame, start_ts: pd.Timestamp) -> list[tuple[pd.Timestamp, float]]:
    equity = trades["net_points"].cumsum().round(4)
    timestamps = pd.to_datetime(trades["entry_ts"], utc=True)
    return [(start_ts, 0.0), *zip(timestamps, equity)]


def _base_spec_from_row(row: pd.Series) -> StrategySpec | None:
    required = {"lookback", "threshold", "holding_minutes"}
    if not required.issubset(row.index) or _is_missing(row["holding_minutes"]):
        return None
    return StrategySpec(
        name=str(row["name"]),
        family=str(row["family"]),
        lookback=int(row["lookback"]),
        threshold=float(row["threshold"]),
        holding_minutes=int(row["holding_minutes"]),
        imbalance_threshold=_float_or_none(row.get("imbalance_threshold")),
        max_spread_quantile=_float_or_none(row.get("max_spread_quantile")),
        min_depth_quantile=_float_or_none(row.get("min_depth_quantile")),
        stop_loss_points=_float_or_none(row.get("stop_loss_points")),
        take_profit_points=_float_or_none(row.get("take_profit_points")),
    )


def _advanced_spec_from_row(row: pd.Series) -> AdvancedStrategySpec | None:
    required = {"lookback", "threshold", "min_hold", "max_hold", "exit_mode", "session", "volatility_filter"}
    if not required.issubset(row.index) or _is_missing(row["min_hold"]) or _is_missing(row["max_hold"]):
        return None
    return AdvancedStrategySpec(
        name=str(row["name"]),
        family=str(row["family"]),
        lookback=int(row["lookback"]),
        threshold=float(row["threshold"]),
        min_hold=int(row["min_hold"]),
        max_hold=int(row["max_hold"]),
        exit_mode=str(row["exit_mode"]),
        session=str(row["session"]),
        volatility_filter=str(row["volatility_filter"]),
        imbalance_threshold=_float_or_none(row.get("imbalance_threshold")),
        max_spread_quantile=_float_or_none(row.get("max_spread_quantile")),
        min_depth_quantile=_float_or_none(row.get("min_depth_quantile")),
        stop_loss_points=_float_or_none(row.get("stop_loss_points")),
        take_profit_points=_float_or_none(row.get("take_profit_points")),
    )


def _curves(features: pd.DataFrame, top10: pd.DataFrame) -> dict[str, list[tuple[pd.Timestamp, float]]]:
    base_specs = {spec.name: spec for spec in generate_strategy_specs()}
    advanced_specs = {spec.name: spec for spec in generate_advanced_specs()}
    curves = {}
    for _, row in top10.iterrows():
        name = row["name"]
        if row["source"] == "base":
            spec = base_specs.get(name) or _base_spec_from_row(row)
            if spec is None:
                continue
            trades = build_trades(features, spec)
            label = f"Base: {name}"
        else:
            spec = advanced_specs.get(name) or _advanced_spec_from_row(row)
            if spec is None:
                continue
            trades = build_advanced_trades(features, spec)
            label = f"Advanced: {name}"
        if not trades.empty:
            curves[label] = _equity_points(trades, features["ts"].min())
    return curves


def _summary_cards(top: pd.Series, rows: pd.DataFrame) -> str:
    ready_count = int(rows["live_ready"].sum())
    local_positive = float(top["local_positive_rate"]) if "local_positive_rate" in top else 0.0
    return f"""
      <div class="metric-grid">
        <div class="metric"><strong>Live-Ready Top1</strong><span>{html.escape(top['name'])}</span></div>
        <div class="metric"><strong>Live Score</strong><span>{_fmt(float(top['live_score']))}</span></div>
        <div class="metric"><strong>Local Rank</strong><span>{_fmt(float(top.get('local_rank_score', top['live_score'])))}</span></div>
        <div class="metric"><strong>Net Points</strong><span>{_fmt(float(top['full_net_points']))}</span></div>
        <div class="metric"><strong>PF</strong><span>{_fmt(float(top['full_profit_factor']))}</span></div>
        <div class="metric"><strong>Positive Folds</strong><span>{float(top['positive_fold_rate']):.2%}</span></div>
        <div class="metric"><strong>Positive Windows</strong><span>{float(top['positive_window_rate']):.2%}</span></div>
        <div class="metric"><strong>Local Positive</strong><span>{local_positive:.2%}</span></div>
        <div class="metric"><strong>3x Cost Net</strong><span>{_fmt(float(top['worst_cost_net_points']))}</span></div>
        <div class="metric"><strong>Ready Count</strong><span>{ready_count} / {len(rows)}</span></div>
      </div>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate live-ready MBP strategy HTML report.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--live-results", default=".tmp/mbp-live-ready-top10.csv")
    parser.add_argument("--output", default="reports/NQM6-mbp-live-ready-top10.html")
    args = parser.parse_args()

    features = _load_features(Path(args.features_cache))
    live = pd.read_csv(args.live_results)
    if live.empty:
        raise SystemExit(f"No live-ready results found: {args.live_results}")
    top10 = live.head(10)
    top = top10.iloc[0]
    curves = _curves(features, top10)

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NQM6 Live-Ready MBP Strategy Report</title>
  <style>
    body {{ margin: 0; padding: 28px; background: #08111f; color: #e8eef6; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 1220px; margin: 0 auto; }}
    .card {{ background: rgba(17, 26, 46, .92); border: 1px solid #26344e; border-radius: 18px; padding: 20px; margin-bottom: 18px; box-shadow: 0 16px 50px rgba(0,0,0,.28); overflow-x: auto; }}
    h1, h2 {{ margin: 0 0 12px; }}
    p {{ color: #a6b3c2; line-height: 1.65; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #26344e; text-align: left; }}
    th {{ color: #cfe0f2; text-transform: uppercase; letter-spacing: .04em; font-size: 12px; }}
    svg {{ width: 100%; height: auto; border-radius: 14px; overflow: hidden; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px; }}
    .metric {{ border: 1px solid #26344e; border-radius: 12px; padding: 12px; background: rgba(8, 17, 31, .42); }}
    .metric strong {{ display: block; margin-bottom: 6px; color: #f5f7fa; }}
    .metric span {{ color: #a6b3c2; line-height: 1.55; }}
    .chart-tooltip {{ position: fixed; z-index: 50; display: none; max-width: 360px; padding: 10px 12px; border: 1px solid #38506f; border-radius: 10px; background: rgba(8, 17, 31, .96); color: #f5f7fa; font-size: 12px; line-height: 1.5; white-space: pre-line; pointer-events: none; box-shadow: 0 14px 36px rgba(0,0,0,.35); }}
    .legend-bar {{ display: flex; flex-wrap: wrap; align-content: flex-start; align-items: center; gap: 8px; height: 106px; overflow-y: auto; padding: 2px 0 8px; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 6px; flex: 0 1 auto; max-width: 310px; border: 1px solid #34445f; border-radius: 999px; background: rgba(8, 17, 31, .72); color: #d7e1ea; padding: 5px 9px; font: 11px/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; cursor: pointer; }}
    .legend-item span:last-child {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .legend-item.is-muted {{ opacity: .38; text-decoration: line-through; }}
    .legend-swatch {{ width: 10px; height: 10px; border-radius: 999px; box-shadow: 0 0 0 1px rgba(255,255,255,.18) inset; }}
    .badge {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: rgba(34,197,94,.14); color: #86efac; margin-bottom: 10px; }}
    .warning {{ border-left: 4px solid #22c55e; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <span class="badge">Live-Ready Candidates · NQM6</span>
      <h1>NQM6 实盘前候选策略报告</h1>
      <p>数据范围：{features['ts'].min()} 至 {features['ts'].max()}；分钟特征数：{len(features):,}。本报告基于 <code>.tmp/mbp-live-ready-top10.csv</code>，在 robust score 之外加入 10 交易日滚动窗口、3x 成本压力和最低交易次数门槛。</p>
    </section>
    <section class="card warning">
      <h2>结论摘要</h2>
      {_summary_cards(top, top10)}
    </section>
    <section class="card">
      <h2>Live-Ready Top10</h2>
      {_table(top10)}
    </section>
    <section class="card">
      <h2>资金曲线对比</h2>
      <p>第一张图按交易次数对齐，第二张图按实际交易日期展开。图例可点击隐藏/恢复策略；鼠标悬浮仅显示当前点数值。</p>
      {_svg_line_chart(curves, "Live-Ready Top10 equity by trade sequence (net points)", "sequence")}
      {_svg_line_chart(curves, "Live-Ready Top10 equity by trading date (net points)", "date")}
      {_equity_curve_summary(curves)}
    </section>
    <section class="card">
      <h2>成本敏感性</h2>
      {_cost_table(top10)}
    </section>
    <section class="card">
      <h2>实盘前门槛说明</h2>
      <div class="metric-grid">
        <div class="metric"><strong>Live Ready</strong><span>True 表示通过本轮硬门槛；这仍不等于可以直接真仓，只代表可以进入 paper/shadow live。</span></div>
        <div class="metric"><strong>Positive Windows</strong><span>10 交易日滚动窗口盈利比例，越高越好；用于检查短周期稳定性。</span></div>
        <div class="metric"><strong>Min Window Net</strong><span>最差 10 日窗口净点数，越高越好；负值表示仍有短期亏损阶段。</span></div>
        <div class="metric"><strong>3x Cost Net</strong><span>3 倍滑点成本后的净点数，越大越好；用于成本压力测试。</span></div>
        <div class="metric"><strong>Local Positive</strong><span>同类局部参数邻域中 robust score 为正的比例，越高越好；用于降低单点参数过拟合风险。</span></div>
        <div class="metric"><strong>Local Rank</strong><span>越大越好；在 Live Score 基础上加入局部参数稳健性惩罚，更偏向参数邻域也表现稳定的策略。</span></div>
        <div class="metric"><strong>Live Score</strong><span>越大越好；由 robust score、正收益 fold、正收益滚动窗口和成本压力共同决定。</span></div>
        <div class="metric"><strong>下一步</strong><span>固定参数后做 paper trading，不再根据纸交易期结果随意调参。</span></div>
      </div>
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
        tooltip.textContent = [
          point.dataset.name || "",
          `Time: ${{point.dataset.time || ""}}`,
          `Trade: ${{point.dataset.trade || ""}}`,
          `Equity: ${{point.dataset.equity || ""}}`,
        ].join("\\n");
        tooltip.style.borderColor = point.dataset.color || "#38506f";
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
</html>
"""
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_doc, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
