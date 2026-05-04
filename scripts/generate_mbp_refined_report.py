from __future__ import annotations

import argparse
import html
from pathlib import Path

import pandas as pd

from generate_mbp_history_report import _equity_curve_summary, _load_features, _svg_line_chart
from generate_mbp_live_ready_report import _advanced_spec_from_row
from mine_mbp_advanced_patterns import build_advanced_trades


def _fmt(value: float, decimals: int = 4) -> str:
    return f"{value:,.{decimals}f}"


def _equity_points(trades: pd.DataFrame, start_ts: pd.Timestamp) -> list[tuple[pd.Timestamp, float]]:
    equity = trades["net_points"].cumsum().round(4)
    timestamps = pd.to_datetime(trades["entry_ts"], utc=True)
    return [(start_ts, 0.0), *zip(timestamps, equity)]


def _curves(features: pd.DataFrame, rows: pd.DataFrame) -> dict[str, list[tuple[pd.Timestamp, float]]]:
    curves = {}
    for _, row in rows.iterrows():
        spec = _advanced_spec_from_row(row)
        if spec is None:
            continue
        trades = build_advanced_trades(features, spec)
        if not trades.empty:
            label = f"{row['label']}: {row['name']}"
            curves[label] = _equity_points(trades, features["ts"].min())
    return curves


def _table(rows: pd.DataFrame) -> str:
    columns = [
        "label",
        "name",
        "full_trades",
        "full_net_points",
        "full_max_drawdown_points",
        "full_profit_factor",
        "positive_fold_rate",
        "positive_window_rate",
        "min_window_net_points",
        "worst_cost_net_points",
        "robust_score",
    ]
    display = rows[columns].copy()
    for column in ["positive_fold_rate", "positive_window_rate"]:
        display[column] = display[column].map(lambda value: f"{float(value):.2%}")
    for column in [
        "full_net_points",
        "full_max_drawdown_points",
        "full_profit_factor",
        "min_window_net_points",
        "worst_cost_net_points",
        "robust_score",
    ]:
        display[column] = display[column].map(lambda value: _fmt(float(value)))
    display.columns = [
        "Candidate",
        "Strategy",
        "Trades",
        "Net Points",
        "Max DD",
        "PF",
        "Positive Folds",
        "Positive Windows",
        "Worst Window",
        "3x Cost Net",
        "Robust Score",
    ]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def _cards(best: pd.Series, baseline: pd.Series) -> str:
    net_delta = float(best["full_net_points"]) - float(baseline["full_net_points"])
    dd_delta = float(best["full_max_drawdown_points"]) - float(baseline["full_max_drawdown_points"])
    pf_delta = float(best["full_profit_factor"]) - float(baseline["full_profit_factor"])
    worst_window_delta = float(best["min_window_net_points"]) - float(baseline["min_window_net_points"])
    return f"""
      <div class="metric-grid">
        <div class="metric"><strong>Refined Top1</strong><span>{html.escape(best['name'])}</span></div>
        <div class="metric"><strong>Net Improvement</strong><span>{_fmt(net_delta)} points</span></div>
        <div class="metric"><strong>Net Points</strong><span>{_fmt(float(best['full_net_points']))}</span></div>
        <div class="metric"><strong>Max DD Change</strong><span>{_fmt(dd_delta)} points</span></div>
        <div class="metric"><strong>PF Change</strong><span>{_fmt(pf_delta)}</span></div>
        <div class="metric"><strong>Worst Window Improvement</strong><span>{_fmt(worst_window_delta)} points</span></div>
        <div class="metric"><strong>Positive Folds</strong><span>{float(best['positive_fold_rate']):.2%}</span></div>
        <div class="metric"><strong>Positive Windows</strong><span>{float(best['positive_window_rate']):.2%}</span></div>
      </div>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate refined MBP mean-reversion HTML report.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--refined-results", default=".tmp/mbp-refined-mean-reversion.csv")
    parser.add_argument("--baseline-results", default=".tmp/mbp-live-ready-top10.csv")
    parser.add_argument("--output", default="reports/NQM6-mbp-refined-mean-reversion.html")
    args = parser.parse_args()

    features = _load_features(Path(args.features_cache))
    refined = pd.read_csv(args.refined_results)
    baseline = pd.read_csv(args.baseline_results).head(1).copy()
    if refined.empty or baseline.empty:
        raise SystemExit("Refined or baseline results are empty.")

    strict = refined[refined["live_ready_strict"]].copy()
    top_refined = (strict if not strict.empty else refined).head(3).copy()
    top_refined["label"] = [f"Refined #{index}" for index in range(1, len(top_refined) + 1)]
    baseline["label"] = "Original Top1"
    baseline["robust_score"] = baseline.get("robust_score", baseline.get("live_score", 0.0))
    comparison = pd.concat([top_refined, baseline], ignore_index=True, sort=False)
    curves = _curves(features, comparison)
    best = top_refined.iloc[0]
    base = baseline.iloc[0]

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NQM6 Refined Mean-Reversion Report</title>
  <style>
    body {{ margin: 0; padding: 28px; background: #07130f; color: #edf8f1; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 1220px; margin: 0 auto; }}
    .card {{ background: rgba(13, 31, 24, .94); border: 1px solid #254338; border-radius: 18px; padding: 20px; margin-bottom: 18px; box-shadow: 0 16px 50px rgba(0,0,0,.28); overflow-x: auto; }}
    h1, h2 {{ margin: 0 0 12px; }}
    p {{ color: #b2c8bd; line-height: 1.65; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #254338; text-align: left; }}
    th {{ color: #d8eadf; text-transform: uppercase; letter-spacing: .04em; font-size: 12px; }}
    svg {{ width: 100%; height: auto; border-radius: 14px; overflow: hidden; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px; }}
    .metric {{ border: 1px solid #254338; border-radius: 12px; padding: 12px; background: rgba(7, 19, 15, .46); }}
    .metric strong {{ display: block; margin-bottom: 6px; color: #f6fbf8; }}
    .metric span {{ color: #b2c8bd; line-height: 1.55; }}
    .chart-tooltip {{ position: fixed; z-index: 50; display: none; max-width: 360px; padding: 10px 12px; border: 1px solid #476b5e; border-radius: 10px; background: rgba(7, 19, 15, .96); color: #f6fbf8; font-size: 12px; line-height: 1.5; white-space: pre-line; pointer-events: none; box-shadow: 0 14px 36px rgba(0,0,0,.35); }}
    .legend-bar {{ display: flex; flex-wrap: wrap; align-content: flex-start; align-items: center; gap: 8px; height: 106px; overflow-y: auto; padding: 2px 0 8px; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 6px; flex: 0 1 auto; max-width: 310px; border: 1px solid #365a4d; border-radius: 999px; background: rgba(7, 19, 15, .72); color: #dcece4; padding: 5px 9px; font: 11px/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; cursor: pointer; }}
    .legend-item span:last-child {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .legend-item.is-muted {{ opacity: .38; text-decoration: line-through; }}
    .legend-swatch {{ width: 10px; height: 10px; border-radius: 999px; box-shadow: 0 0 0 1px rgba(255,255,255,.18) inset; }}
    .badge {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: rgba(34,197,94,.14); color: #86efac; margin-bottom: 10px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <span class="badge">Refined Mean-Reversion · NQM6</span>
      <h1>NQM6 收益增强策略报告</h1>
      <p>目标是在保留原 Top1 的核心优势时提高整体收益。本轮只接受更严格门槛：6/6 folds 为正、9/9 滚动 10 日窗口为正、最差 10 日窗口非负、3x 成本后仍盈利、交易数不少于 200、PF 不低于 1.25。</p>
    </section>
    <section class="card">
      <h2>结论摘要</h2>
      {_cards(best, base)}
    </section>
    <section class="card">
      <h2>候选对比</h2>
      {_table(comparison)}
    </section>
    <section class="card">
      <h2>资金曲线对比</h2>
      <p>包含 refined Top3 与原 Top1。第一张图按交易次数对齐，第二张图按实际交易日期展开。鼠标悬浮仅显示当前点。</p>
      {_svg_line_chart(curves, "Refined candidates equity by trade sequence (net points)", "sequence")}
      {_svg_line_chart(curves, "Refined candidates equity by trading date (net points)", "date")}
      {_equity_curve_summary(curves)}
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
        tooltip.style.borderColor = point.dataset.color || "#476b5e";
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
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_doc, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
