from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from generate_mbp_history_report import _equity_curve_summary, _load_features, _svg_line_chart
from generate_mbp_live_ready_report import _advanced_spec_from_row
from mine_mbp_advanced_patterns import build_advanced_trades


BENCHMARK_NAME = "adv_refined_mean_reversion_lb7_thr0.65_min1_max6_reverse_europe_not_low_imb0.3"


def _fmt(value: float, decimals: int = 4) -> str:
    return f"{value:,.{decimals}f}"


def _load_candidates(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        if path.exists():
            frame = pd.read_csv(path)
            if not frame.empty:
                frames.append(frame)
    if not frames:
        raise SystemExit("No enhanced candidate files found.")
    candidates = pd.concat(frames, ignore_index=True, sort=False)
    if "live_ready_strict" in candidates.columns:
        candidates["live_ready"] = candidates.get("live_ready", False) | candidates["live_ready_strict"].fillna(False)
    candidates["live_ready"] = candidates["live_ready"].fillna(False).astype(bool)
    candidates["preserves_core_edge"] = candidates.get("preserves_core_edge", False).fillna(False).astype(bool)
    if "live_ready_strict" in candidates.columns:
        candidates["preserves_core_edge"] = candidates["preserves_core_edge"] | candidates["live_ready_strict"].fillna(False).astype(bool)
    if "full_score" not in candidates.columns:
        candidates["full_score"] = 0.0
    if "robust_score" not in candidates.columns:
        candidates["robust_score"] = candidates["full_score"]
    candidates["robust_score"] = candidates["robust_score"].fillna(candidates["full_score"])
    candidates = candidates[candidates["live_ready"]].copy()
    candidates = candidates[candidates["full_trades"] >= 200].copy()
    candidates = candidates[candidates["full_profit_factor"] >= 1.25].copy()
    if candidates.empty:
        raise SystemExit("No live-ready enhanced candidates found.")
    candidates["enhanced_rank_score"] = (
        candidates["full_net_points"].astype(float)
        + candidates["worst_cost_net_points"].astype(float) * 0.25
        + candidates["min_window_net_points"].astype(float).clip(lower=-500) * 0.50
        - candidates["full_max_drawdown_points"].astype(float) * 0.20
        + candidates["preserves_core_edge"].astype(int) * 250.0
    )
    dedupe_columns = [
        "family",
        "lookback",
        "threshold",
        "min_hold",
        "max_hold",
        "exit_mode",
        "session",
        "volatility_filter",
        "imbalance_threshold",
        "stop_loss_points",
        "take_profit_points",
    ]
    candidates = candidates.sort_values(
        ["preserves_core_edge", "enhanced_rank_score", "full_net_points", "worst_cost_net_points"],
        ascending=[False, False, False, False],
    )
    return candidates.drop_duplicates(dedupe_columns, keep="first").reset_index(drop=True)


def _table(rows: pd.DataFrame) -> str:
    columns = [
        "name",
        "family",
        "full_trades",
        "full_net_points",
        "full_max_drawdown_points",
        "full_profit_factor",
        "positive_fold_rate",
        "positive_window_rate",
        "min_window_net_points",
        "worst_cost_net_points",
        "preserves_core_edge",
        "enhanced_rank_score",
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
        "enhanced_rank_score",
    ]:
        display[column] = display[column].map(lambda value: _fmt(float(value)))
    display.columns = [
        "Strategy",
        "Family",
        "Trades",
        "Net Points",
        "Max DD",
        "PF",
        "Positive Folds",
        "Positive Windows",
        "Worst Window",
        "3x Cost Net",
        "Core Edge",
        "Rank Score",
    ]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def _comparison_table(top10: pd.DataFrame, benchmark: pd.Series | None = None, adaptive: pd.Series | None = None) -> str:
    frames = []
    if adaptive is not None:
        frames.append(pd.DataFrame([adaptive.to_dict() | {"comparison_label": "Best Adaptive Portfolio"}]))
    if benchmark is not None:
        frames.append(pd.DataFrame([benchmark.to_dict() | {"comparison_label": "Benchmark Refined"}]))
    frames.append(top10.assign(comparison_label=[f"Enhanced #{index}" for index in range(1, len(top10) + 1)]))
    rows = pd.concat(frames, ignore_index=True, sort=False)
    columns = [
        "comparison_label",
        "name",
        "family",
        "full_trades",
        "full_net_points",
        "full_max_drawdown_points",
        "full_profit_factor",
        "positive_fold_rate",
        "positive_window_rate",
        "min_window_net_points",
        "worst_cost_net_points",
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
    ]:
        display[column] = display[column].map(lambda value: _fmt(float(value)))
    display.columns = [
        "Label",
        "Strategy",
        "Family",
        "Trades",
        "Net Points",
        "Max DD",
        "PF",
        "Positive Folds",
        "Positive Windows",
        "Worst Window",
        "3x Cost Net",
    ]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def _equity_points(trades: pd.DataFrame, start_ts: pd.Timestamp) -> list[tuple[pd.Timestamp, float]]:
    equity = trades["net_points"].cumsum().round(4)
    timestamps = pd.to_datetime(trades["entry_ts"], utc=True)
    return [(start_ts, 0.0), *zip(timestamps, equity)]


def _curves(
    features: pd.DataFrame,
    top10: pd.DataFrame,
    benchmark: pd.Series | None = None,
    adaptive_trades: pd.DataFrame | None = None,
) -> dict[str, list[tuple[pd.Timestamp, float]]]:
    curves = {}
    if adaptive_trades is not None and not adaptive_trades.empty:
        curves["Best Adaptive Portfolio"] = _equity_points(adaptive_trades, features["ts"].min())
    for rank, (_, row) in enumerate(top10.iterrows(), start=1):
        spec = _advanced_spec_from_row(row)
        if spec is None:
            continue
        trades = build_advanced_trades(features, spec)
        if not trades.empty:
            curves[f"Enhanced #{rank}: {row['name']}"] = _equity_points(trades, features["ts"].min())
    if benchmark is not None:
        spec = _advanced_spec_from_row(benchmark)
        if spec is not None:
            trades = build_advanced_trades(features, spec)
            if not trades.empty:
                curves[f"Benchmark: {benchmark['name']}"] = _equity_points(trades, features["ts"].min())
    return curves


def _load_adaptive_portfolio(summary_path: Path, trades_path: Path) -> tuple[pd.Series | None, pd.DataFrame | None]:
    if not summary_path.exists() or not trades_path.exists():
        return None, None
    summary = pd.read_csv(summary_path)
    trades = pd.read_csv(trades_path)
    if summary.empty or trades.empty:
        return None, None
    row = summary.iloc[0].copy()
    row["family"] = "adaptive_portfolio"
    row["preserves_core_edge"] = True
    row["enhanced_rank_score"] = row.get("portfolio_score", row.get("full_net_points", 0.0))
    row["worst_cost_net_points"] = row.get("cost_3x_net_points", row.get("worst_cost_net_points", 0.0))
    return row, trades


def _benchmark_delta_cards(top10: pd.DataFrame, benchmark: pd.Series) -> str:
    best = top10.iloc[0]
    return f"""
      <div class="metric-grid">
        <div class="metric"><strong>Benchmark Net Rank</strong><span>{int((top10['full_net_points'] > benchmark['full_net_points']).sum() + 1)} vs Top10</span></div>
        <div class="metric"><strong>Benchmark PF Rank</strong><span>{int((top10['full_profit_factor'] > benchmark['full_profit_factor']).sum() + 1)} vs Top10</span></div>
        <div class="metric"><strong>Benchmark DD Rank</strong><span>{int((top10['full_max_drawdown_points'] < benchmark['full_max_drawdown_points']).sum() + 1)} vs Top10</span></div>
        <div class="metric"><strong>Benchmark Worst Window Rank</strong><span>{int((top10['min_window_net_points'] > benchmark['min_window_net_points']).sum() + 1)} vs Top10</span></div>
        <div class="metric"><strong>Net Gap To Enhanced Top1</strong><span>{_fmt(float(best['full_net_points'] - benchmark['full_net_points']))} points</span></div>
        <div class="metric"><strong>3x Cost Gap To Enhanced Top1</strong><span>{_fmt(float(best['worst_cost_net_points'] - benchmark['worst_cost_net_points']))} points</span></div>
      </div>
"""


def _cards(top10: pd.DataFrame, full_count: int, benchmark: pd.Series | None = None) -> str:
    best = top10.iloc[0]
    core_count = int(top10["preserves_core_edge"].sum())
    benchmark_text = "Included" if benchmark is not None else "Not included"
    return f"""
      <div class="metric-grid">
        <div class="metric"><strong>Enhanced Top1</strong><span>{html.escape(best['name'])}</span></div>
        <div class="metric"><strong>Top1 Net Points</strong><span>{_fmt(float(best['full_net_points']))}</span></div>
        <div class="metric"><strong>Top1 PF</strong><span>{_fmt(float(best['full_profit_factor']))}</span></div>
        <div class="metric"><strong>Top1 Worst Window</strong><span>{_fmt(float(best['min_window_net_points']))}</span></div>
        <div class="metric"><strong>Top1 3x Cost Net</strong><span>{_fmt(float(best['worst_cost_net_points']))}</span></div>
        <div class="metric"><strong>Core Edge Count</strong><span>{core_count} / {len(top10)}</span></div>
        <div class="metric"><strong>Candidate Pool</strong><span>{full_count} live-ready enhanced candidates</span></div>
        <div class="metric"><strong>Benchmark Refined</strong><span>{benchmark_text}</span></div>
        <div class="metric"><strong>Ranking</strong><span>按净收益、3x 成本、最差窗口、回撤和核心边际综合排序。</span></div>
      </div>
"""


def _adaptive_cards(adaptive: pd.Series | None) -> str:
    if adaptive is None:
        return ""
    return f"""
      <div class="metric-grid">
        <div class="metric"><strong>Best Adaptive Portfolio</strong><span>{html.escape(str(adaptive['name']))}</span></div>
        <div class="metric"><strong>Adaptive Net Points</strong><span>{_fmt(float(adaptive['full_net_points']))}</span></div>
        <div class="metric"><strong>Adaptive Max DD</strong><span>{_fmt(float(adaptive['full_max_drawdown_points']))}</span></div>
        <div class="metric"><strong>Adaptive PF</strong><span>{_fmt(float(adaptive['full_profit_factor']))}</span></div>
        <div class="metric"><strong>Adaptive Stability</strong><span>{_fmt(float(adaptive.get('full_stability', 0.0)))}</span></div>
        <div class="metric"><strong>Adaptive 3x Cost Net</strong><span>{_fmt(float(adaptive.get('worst_cost_net_points', 0.0)))}</span></div>
      </div>
"""


def _load_benchmark(candidate_files: list[Path], benchmark_name: str) -> pd.Series | None:
    for path in candidate_files:
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        match = frame[frame["name"].eq(benchmark_name)]
        if not match.empty:
            row = match.iloc[0].copy()
            if "live_ready_strict" in row.index and bool(row["live_ready_strict"]):
                row["live_ready"] = True
                row["preserves_core_edge"] = True
            if "preserves_core_edge" not in row.index or pd.isna(row["preserves_core_edge"]):
                row["preserves_core_edge"] = False
            if "enhanced_rank_score" not in row.index or pd.isna(row["enhanced_rank_score"]):
                row["enhanced_rank_score"] = (
                    float(row["full_net_points"])
                    + float(row["worst_cost_net_points"]) * 0.25
                    + max(float(row["min_window_net_points"]), -500.0) * 0.50
                    - float(row["full_max_drawdown_points"]) * 0.20
                    + (250.0 if bool(row["preserves_core_edge"]) else 0.0)
                )
            return row
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate enhanced MBP Top10 HTML report.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--candidate-files", nargs="*", default=[
        ".tmp/mbp-top10-enhancement-candidates.csv",
        ".tmp/mbp-refined-mean-reversion.csv",
    ])
    parser.add_argument("--top-output", default=".tmp/mbp-enhanced-top10.csv")
    parser.add_argument("--adaptive-results", default=".tmp/mbp-adaptive-portfolio.csv")
    parser.add_argument("--adaptive-trades", default=".tmp/mbp-adaptive-portfolio-trades.csv")
    parser.add_argument("--markdown", default="reports/NQM6-mbp-enhanced-top10.md")
    parser.add_argument("--output", default="reports/NQM6-mbp-enhanced-top10.html")
    parser.add_argument("--benchmark-name", default=BENCHMARK_NAME)
    args = parser.parse_args()

    features = _load_features(Path(args.features_cache))
    candidate_paths = [Path(path) for path in args.candidate_files]
    candidates = _load_candidates(candidate_paths)
    top10 = candidates.head(10).copy()
    benchmark = _load_benchmark(candidate_paths, args.benchmark_name)
    adaptive, adaptive_trades = _load_adaptive_portfolio(Path(args.adaptive_results), Path(args.adaptive_trades))
    curves = _curves(features, top10, benchmark, adaptive_trades)

    Path(args.top_output).parent.mkdir(parents=True, exist_ok=True)
    top10.to_csv(args.top_output, index=False)

    markdown = [
        "# NQM6 MBP Enhanced Top10",
        "",
        f"Feature rows: {len(features):,}",
        f"Date range: {features['ts'].min()} to {features['ts'].max()}",
        f"Live-ready enhanced candidate pool: {len(candidates):,}",
        f"Best adaptive portfolio included: {'yes' if adaptive is not None else 'no'}",
        "",
        _table(top10),
        "",
        "## Best Adaptive Portfolio",
        "",
        _comparison_table(top10.head(0), adaptive=adaptive) if adaptive is not None else "Adaptive portfolio not found.",
        "",
        "## Benchmark Refined Comparison",
        "",
        _comparison_table(top10, benchmark, adaptive) if benchmark is not None else f"Benchmark not found: {args.benchmark_name}",
        "",
    ]
    Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
    Path(args.markdown).write_text("\n".join(markdown), encoding="utf-8")

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NQM6 Enhanced MBP Top10</title>
  <style>
    body {{ margin: 0; padding: 28px; background: #080f16; color: #edf6fb; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 1220px; margin: 0 auto; }}
    .card {{ background: rgba(14, 25, 36, .94); border: 1px solid #24384d; border-radius: 18px; padding: 20px; margin-bottom: 18px; box-shadow: 0 16px 50px rgba(0,0,0,.28); overflow-x: auto; }}
    h1, h2 {{ margin: 0 0 12px; }}
    p {{ color: #adc0cf; line-height: 1.65; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #24384d; text-align: left; }}
    th {{ color: #d6e7f2; text-transform: uppercase; letter-spacing: .04em; font-size: 12px; }}
    svg {{ width: 100%; height: auto; border-radius: 14px; overflow: hidden; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px; }}
    .metric {{ border: 1px solid #24384d; border-radius: 12px; padding: 12px; background: rgba(8, 15, 22, .48); }}
    .metric strong {{ display: block; margin-bottom: 6px; color: #f7fbff; }}
    .metric span {{ color: #adc0cf; line-height: 1.55; }}
    .chart-tooltip {{ position: fixed; z-index: 50; display: none; max-width: 360px; padding: 10px 12px; border: 1px solid #3a5875; border-radius: 10px; background: rgba(8, 15, 22, .96); color: #f7fbff; font-size: 12px; line-height: 1.5; white-space: pre-line; pointer-events: none; box-shadow: 0 14px 36px rgba(0,0,0,.35); }}
    .legend-bar {{ display: flex; flex-wrap: wrap; align-content: flex-start; align-items: center; gap: 8px; height: 106px; overflow-y: auto; padding: 2px 0 8px; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 6px; flex: 0 1 auto; max-width: 310px; border: 1px solid #34506d; border-radius: 999px; background: rgba(8, 15, 22, .72); color: #d9e8f2; padding: 5px 9px; font: 11px/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; cursor: pointer; }}
    .legend-item span:last-child {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .legend-item.is-muted {{ opacity: .38; text-decoration: line-through; }}
    .legend-swatch {{ width: 10px; height: 10px; border-radius: 999px; box-shadow: 0 0 0 1px rgba(255,255,255,.18) inset; }}
    .badge {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: rgba(56,189,248,.14); color: #7dd3fc; margin-bottom: 10px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <span class="badge">Enhanced Live-Ready · NQM6</span>
      <h1>NQM6 增强后 Top10 策略报告</h1>
      <p>候选池来自 Top10 一跳增强搜索和 mean-reversion 定向 refined 搜索。这里只保留 live-ready 增强候选，并按净收益、3x 成本、最差窗口、回撤和核心边际综合排序。</p>
    </section>
    <section class="card">
      <h2>结论摘要</h2>
      {_cards(top10, len(candidates), benchmark)}
    </section>
    {f'''<section class="card">
      <h2>Best Adaptive Portfolio</h2>
      <p>该组合不是单一策略，而是按 session、波动率和 VWAP regime 在稳定均值回归、防守均值回归和趋势 VWAP 候选之间切换。它作为当前最佳策略候选纳入本报告和资金曲线。</p>
      {_adaptive_cards(adaptive)}
    </section>''' if adaptive is not None else ''}
    {f'''<section class="card">
      <h2>Benchmark Refined 对比</h2>
      <p>该 refined 策略不改变 Enhanced Top10 排名，作为主候选/低回撤稳定性基准加入表格和资金曲线。</p>
      {_benchmark_delta_cards(top10, benchmark)}
      {_comparison_table(top10, benchmark, adaptive)}
    </section>''' if benchmark is not None else ''}
    <section class="card">
      <h2>Enhanced Top10</h2>
      {_table(top10)}
    </section>
    <section class="card">
      <h2>资金曲线对比</h2>
      <p>第一张图按交易次数对齐，第二张图按实际交易日期展开。图例可点击隐藏/恢复策略；鼠标悬浮仅显示当前点。若 Benchmark 和 Adaptive Portfolio 存在，则图中包含 Enhanced Top10 + Benchmark + Adaptive 共 12 条曲线。</p>
      {_svg_line_chart(curves, "Enhanced Top10 + Benchmark equity by trade sequence (net points)", "sequence")}
      {_svg_line_chart(curves, "Enhanced Top10 + Benchmark equity by trading date (net points)", "date")}
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
        tooltip.style.borderColor = point.dataset.color || "#3a5875";
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
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(html_doc, encoding="utf-8")
    print(args.top_output)
    print(args.markdown)
    print(args.output)
    if benchmark is not None:
        print(f"Benchmark: {benchmark['name']}")
    if adaptive is not None:
        print(f"Adaptive: {adaptive['name']}")
    print(top10[["name", "family", "full_trades", "full_net_points", "full_max_drawdown_points", "full_profit_factor", "min_window_net_points", "worst_cost_net_points", "preserves_core_edge", "enhanced_rank_score"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
