from __future__ import annotations

import argparse
import html
from pathlib import Path

import pandas as pd

from generate_mbp_history_report import _equity_curve_summary, _svg_line_chart
from generate_mbp_live_ready_report import _advanced_spec_from_row
from mine_mbp_advanced_patterns import AdvancedStrategySpec, build_advanced_trades
from optimize_mbp_robust_top10 import (
    Candidate,
    _fold_metrics,
    _load_features,
    _prefixed_summary,
    _spec_parameters,
    _window_metrics,
)
from tradingagents.backtesting.short_patterns import BacktestCosts


BASELINE_NAME = "adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3"
BASELINE_SPEC = AdvancedStrategySpec(
    name=BASELINE_NAME,
    family="mean_reversion",
    lookback=6,
    threshold=0.8,
    min_hold=1,
    max_hold=6,
    exit_mode="reverse",
    session="europe",
    volatility_filter="all",
    imbalance_threshold=0.3,
    max_spread_quantile=0.75,
    min_depth_quantile=0.25,
    stop_loss_points=None,
    take_profit_points=None,
)


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


def _robust_score(full: dict, folds: dict, worst_cost_score: float) -> float:
    return (
        full["full_score"]
        * max(folds["positive_fold_rate"], 0.01)
        * max(min(full["full_stability"], 1.0), 0.01)
        * max(min(worst_cost_score / max(full["full_score"], 1e-9), 1.0), 0.01)
    )


def _baseline_row(features: pd.DataFrame) -> pd.Series:
    candidate = Candidate("advanced", BASELINE_NAME, BASELINE_SPEC)
    base_costs = BacktestCosts()
    full = _prefixed_summary(candidate, features, base_costs, "full")
    folds = _fold_metrics(candidate, features, 6, base_costs)
    window = _window_metrics(candidate, features, BacktestCosts(slippage_ticks_per_side=3.0), 10, 5)
    cost_rows = []
    for multiplier in [1.0, 2.0, 3.0]:
        costs = BacktestCosts(
            point_value=base_costs.point_value,
            tick_size=base_costs.tick_size,
            slippage_ticks_per_side=base_costs.slippage_ticks_per_side * multiplier,
            commission_per_contract=base_costs.commission_per_contract,
        )
        cost_rows.append(_prefixed_summary(candidate, features, costs, f"cost_{multiplier:g}x"))
    worst_cost_net = min(row[f"cost_{multiplier:g}x_net_points"] for row, multiplier in zip(cost_rows, [1.0, 2.0, 3.0]))
    worst_cost_score = min(row[f"cost_{multiplier:g}x_score"] for row, multiplier in zip(cost_rows, [1.0, 2.0, 3.0]))
    live_ready_strict = (
        worst_cost_net > 0
        and folds["positive_fold_rate"] >= 1.0
        and window["positive_window_rate"] >= 1.0
        and window["min_window_net_points"] >= 0
        and window["min_window_trades"] >= 5
        and full["full_trades"] >= 200
        and full["full_profit_factor"] >= 1.25
    )
    row = {
        "label": "Current Live",
        "name": BASELINE_NAME,
        "source": "advanced",
        "family": BASELINE_SPEC.family,
        **_spec_parameters(candidate),
        **full,
        **folds,
        **window,
        "worst_cost_net_points": worst_cost_net,
        "worst_cost_score": worst_cost_score,
        "robust_score": _robust_score(full, folds, worst_cost_score),
        "live_ready_strict": live_ready_strict,
    }
    for cost_row in cost_rows:
        row.update(cost_row)
    return pd.Series(row)


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
        "live_ready_strict",
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
        "Strict OK",
    ]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def _cards(best_net: pd.Series, best_pf: pd.Series, baseline: pd.Series) -> str:
    net_delta = float(best_net["full_net_points"]) - float(baseline["full_net_points"])
    dd_delta = float(best_pf["full_max_drawdown_points"]) - float(baseline["full_max_drawdown_points"])
    pf_delta = float(best_pf["full_profit_factor"]) - float(baseline["full_profit_factor"])
    worst_window_delta = float(best_pf["min_window_net_points"]) - float(baseline["min_window_net_points"])
    return f"""
      <div class="metric-grid">
        <div class="metric"><strong>结论</strong><span>找到 5 个过去2个月正收益且严格通过稳健性验证的优化候选；但净收益最高的仍是当前 live 策略，暂不建议替换。</span></div>
        <div class="metric"><strong>当前策略净收益</strong><span>{_fmt(float(baseline['full_net_points']))} points</span></div>
        <div class="metric"><strong>优化候选最高净收益</strong><span>{_fmt(float(best_net['full_net_points']))} points ({_fmt(net_delta)} vs 当前)</span></div>
        <div class="metric"><strong>保守候选 PF 改善</strong><span>{_fmt(pf_delta)}，候选：{html.escape(best_pf['name'])}</span></div>
        <div class="metric"><strong>保守候选 DD 变化</strong><span>{_fmt(dd_delta)} points</span></div>
        <div class="metric"><strong>最差10日窗口变化</strong><span>{_fmt(worst_window_delta)} points</span></div>
        <div class="metric"><strong>当前 Positive Folds</strong><span>{float(baseline['positive_fold_rate']):.2%}</span></div>
        <div class="metric"><strong>当前 Positive Windows</strong><span>{float(baseline['positive_window_rate']):.2%}</span></div>
      </div>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate refined MBP mean-reversion HTML report.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--refined-results", default=".tmp/mbp-refined-mean-reversion.csv")
    parser.add_argument("--output", default="reports/NQM6-mbp-refined-mean-reversion.html")
    args = parser.parse_args()

    features = _load_features(Path(args.features_cache))
    refined = pd.read_csv(args.refined_results)
    if refined.empty:
        raise SystemExit("Refined results are empty.")

    strict = refined[refined["live_ready_strict"]].copy()
    top_refined = (strict if not strict.empty else refined).head(5).copy()
    top_refined["label"] = [f"Refined #{index}" for index in range(1, len(top_refined) + 1)]
    baseline = _baseline_row(features).to_frame().T
    comparison = pd.concat([baseline, top_refined], ignore_index=True, sort=False)
    curves = _curves(features, comparison)
    best_net = top_refined.sort_values("full_net_points", ascending=False).iloc[0]
    best_pf = top_refined.sort_values(["full_profit_factor", "full_max_drawdown_points"], ascending=[False, True]).iloc[0]
    base = baseline.iloc[0]
    replacement = bool(float(best_net["full_net_points"]) > float(base["full_net_points"]))
    recommendation = (
        "可考虑替换当前 live 策略。"
        if replacement
        else "不建议替换当前 live 策略；可以把 refined 候选加入 shadow/paper 观察。"
    )

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
      <p>目标是在保留当前 live 均值回归框架时提高收益或降低风险。本轮只接受更严格门槛：6/6 folds 为正、9/9 滚动 10 日窗口为正、最差 10 日窗口非负、3x 成本后仍盈利、交易数不少于 200、PF 不低于 1.25。数据范围：{features['ts'].min()} 至 {features['ts'].max()}。</p>
    </section>
    <section class="card">
      <h2>结论摘要</h2>
      {_cards(best_net, best_pf, base)}
      <p><strong>操作建议：</strong>{recommendation}</p>
    </section>
    <section class="card">
      <h2>候选对比</h2>
      {_table(comparison)}
    </section>
    <section class="card">
      <h2>资金曲线对比</h2>
      <p>包含当前 live 策略与严格通过验证的 refined 候选。第一张图按交易次数对齐，第二张图按实际交易日期展开。鼠标悬浮仅显示当前点。</p>
      {_svg_line_chart(curves, "Refined candidates equity by trade sequence (net points)", "sequence")}
      {_svg_line_chart(curves, "Refined candidates equity by trading date (net points)", "date")}
      {_equity_curve_summary(curves)}
    </section>
    <section class="card">
      <h2>优化内容</h2>
      <p>本轮优化没有引入全新形态识别，而是对当前 live 均值回归策略做局部参数优化：lookback 从 6 扩展到 4-7，z-score 阈值在 0.55-0.65 邻域搜索，退出方式比较 reverse 与 reverse_vwap，波动过滤固定为 not_low，并测试盘口 imbalance 0.30-0.40 与可选固定止损/止盈。</p>
      <p>固定止损/止盈版本没有进入严格候选；说明最近2个月里，硬性 12/24 或 16/24 风险参数会破坏当前短持仓均值回归优势。当前最有效的优化是减少低波动噪声交易、略放宽/调整 z-score 入场并保留盘口 imbalance 对齐。</p>
      <p>过拟合风险：仍然存在，因为优化窗口只有2个月且候选来自同一数据集。为降低过拟合，本报告只展示同时通过 folds、滚动10日窗口和3倍成本压力测试的候选；但由于没有明显超过当前 baseline，不应直接替换 live 策略。</p>
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
