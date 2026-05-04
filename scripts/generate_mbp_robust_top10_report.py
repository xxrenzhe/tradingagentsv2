from __future__ import annotations

import argparse
import html
from pathlib import Path

import pandas as pd

from generate_mbp_history_report import _equity_curve_summary, _load_features, _svg_line_chart
from mine_mbp_advanced_patterns import build_advanced_trades, generate_advanced_specs
from tradingagents.backtesting.short_patterns import build_trades, generate_strategy_specs


def _format_number(value: float, decimals: int = 4) -> str:
    return f"{value:,.{decimals}f}"


def _metrics_table(rows: pd.DataFrame) -> str:
    columns = [
        "name",
        "source",
        "family",
        "full_trades",
        "full_net_points",
        "full_max_drawdown_points",
        "full_profit_factor",
        "positive_fold_rate",
        "min_fold_net_points",
        "worst_cost_net_points",
        "robust_score",
    ]
    display = rows[columns].copy()
    display["positive_fold_rate"] = display["positive_fold_rate"].map(lambda value: f"{value:.2%}")
    for column in [
        "full_net_points",
        "full_max_drawdown_points",
        "full_profit_factor",
        "min_fold_net_points",
        "worst_cost_net_points",
        "robust_score",
    ]:
        display[column] = display[column].map(lambda value: _format_number(float(value)))
    display.columns = [
        "Strategy",
        "Source",
        "Family",
        "Trades",
        "Net Points",
        "Max DD",
        "PF",
        "Positive Folds",
        "Worst Fold",
        "3x Cost Net",
        "Robust Score",
    ]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def _equity_points(trades: pd.DataFrame, start_ts: pd.Timestamp) -> list[tuple[pd.Timestamp, float]]:
    equity = trades["net_points"].cumsum().round(4)
    timestamps = pd.to_datetime(trades["entry_ts"], utc=True)
    return [(start_ts, 0.0), *zip(timestamps, equity)]


def _robust_curves(features: pd.DataFrame, top10: pd.DataFrame) -> dict[str, list[tuple[pd.Timestamp, float]]]:
    base_specs = {spec.name: spec for spec in generate_strategy_specs()}
    advanced_specs = {spec.name: spec for spec in generate_advanced_specs()}
    curves = {}
    for _, row in top10.iterrows():
        name = row["name"]
        if row["source"] == "base":
            spec = base_specs[name]
            trades = build_trades(features, spec)
            label = f"Base: {name}"
        else:
            spec = advanced_specs[name]
            trades = build_advanced_trades(features, spec)
            label = f"Advanced: {name}"
        if not trades.empty:
            curves[label] = _equity_points(trades, features["ts"].min())
    return curves


def _metric_cards(top: pd.Series, rows: pd.DataFrame) -> str:
    return f"""
      <div class="metric-grid">
        <div class="metric"><strong>Top Strategy</strong><span>{html.escape(top['name'])}</span></div>
        <div class="metric"><strong>Robust Score</strong><span>{_format_number(float(top['robust_score']))}</span></div>
        <div class="metric"><strong>Net Points</strong><span>{_format_number(float(top['full_net_points']))}</span></div>
        <div class="metric"><strong>Max DD</strong><span>{_format_number(float(top['full_max_drawdown_points']))}</span></div>
        <div class="metric"><strong>PF</strong><span>{_format_number(float(top['full_profit_factor']))}</span></div>
        <div class="metric"><strong>Positive Fold Rate</strong><span>{float(top['positive_fold_rate']):.2%}</span></div>
        <div class="metric"><strong>Worst 3x Cost Net</strong><span>{_format_number(float(top['worst_cost_net_points']))}</span></div>
        <div class="metric"><strong>Top10 Mix</strong><span>{rows['source'].value_counts().to_dict()}</span></div>
      </div>
"""


def _cost_table(rows: pd.DataFrame) -> str:
    display = rows[
        [
            "name",
            "cost_1x_net_points",
            "cost_2x_net_points",
            "cost_3x_net_points",
            "cost_1x_score",
            "cost_2x_score",
            "cost_3x_score",
        ]
    ].copy()
    for column in display.columns:
        if column != "name":
            display[column] = display[column].map(lambda value: _format_number(float(value)))
    display.columns = ["Strategy", "1x Net", "2x Net", "3x Net", "1x Score", "2x Score", "3x Score"]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate robust MBP Top10 HTML report.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--robust-results", default=".tmp/mbp-robust-top10.csv")
    parser.add_argument("--output", default="reports/NQM6-mbp-robust-top10.html")
    args = parser.parse_args()

    features = _load_features(Path(args.features_cache))
    robust = pd.read_csv(args.robust_results)
    if robust.empty:
        raise SystemExit(f"No robust results found: {args.robust_results}")
    top10 = robust.head(10)
    curves = _robust_curves(features, top10)
    top = top10.iloc[0]

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NQM6 Robust MBP Top10 Strategy Report</title>
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
    .badge {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: rgba(56,189,248,.14); color: #7dd3fc; margin-bottom: 10px; }}
    .warning {{ border-left: 4px solid #38bdf8; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <span class="badge">Robust MBP Top10 · NQM6</span>
      <h1>NQM6 稳健 Top10 交易策略报告</h1>
      <p>数据范围：{features['ts'].min()} 至 {features['ts'].max()}；分钟特征数：{len(features):,}。本报告基于 <code>.tmp/mbp-robust-top10.csv</code>，用完整历史、6 折正收益率、稳定性和 1x/2x/3x 成本敏感性综合排序。</p>
    </section>
    <section class="card warning">
      <h2>结论摘要</h2>
      {_metric_cards(top, top10)}
    </section>
    <section class="card">
      <h2>稳健 Top10 排名</h2>
      {_metrics_table(top10)}
    </section>
    <section class="card">
      <h2>资金曲线对比</h2>
      <p>第一张图按交易次数对齐，第二张图按实际交易日期展开。图例可点击隐藏/恢复策略；鼠标悬浮仅显示当前点数值。</p>
      {_svg_line_chart(curves, "Robust Top10 equity by trade sequence (net points)", "sequence")}
      {_svg_line_chart(curves, "Robust Top10 equity by trading date (net points)", "date")}
      {_equity_curve_summary(curves)}
    </section>
    <section class="card">
      <h2>成本敏感性</h2>
      <p>比较 1x/2x/3x 滑点成本下的净点数和综合分数；3x 成本仍为正的策略更稳健。</p>
      {_cost_table(top10)}
    </section>
    <section class="card">
      <h2>指标说明</h2>
      <div class="metric-grid">
        <div class="metric"><strong>Robust Score</strong><span>越大越好；由完整历史分数、正收益 fold 占比、稳定性、最差成本敏感性共同决定。</span></div>
        <div class="metric"><strong>Positive Folds</strong><span>6 个时间折中盈利折数占比，越高越好；用于降低单段行情过拟合。</span></div>
        <div class="metric"><strong>Worst Fold</strong><span>最差时间折净点数，越高越好；为负说明仍有不利行情段。</span></div>
        <div class="metric"><strong>3x Cost Net</strong><span>滑点扩大到 3 倍后的净点数，越大越好；用于压力测试交易成本。</span></div>
        <div class="metric"><strong>PF</strong><span>Profit Factor，总盈利除以总亏损，越大越好；大于 1 表示盈利额超过亏损额。</span></div>
        <div class="metric"><strong>Max DD</strong><span>最大回撤点数，越小越好；代表资金曲线从峰值到低谷的最大压力。</span></div>
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
