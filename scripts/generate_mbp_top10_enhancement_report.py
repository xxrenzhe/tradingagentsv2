from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def _fmt(value: float, decimals: int = 4) -> str:
    return f"{value:,.{decimals}f}"


def _table(summary: pd.DataFrame) -> str:
    columns = [
        "seed_rank",
        "seed_family",
        "seed_net_points",
        "best_net_points",
        "net_delta",
        "pf_delta",
        "min_window_delta",
        "worst_cost_delta",
        "best_live_ready",
        "preserves_core_edge",
    ]
    display = summary[columns].copy()
    for column in ["seed_net_points", "best_net_points", "net_delta", "pf_delta", "min_window_delta", "worst_cost_delta"]:
        display[column] = display[column].map(lambda value: _fmt(float(value)))
    display.columns = [
        "Rank",
        "Family",
        "Original Net",
        "Enhanced Net",
        "Net Delta",
        "PF Delta",
        "Worst Window Delta",
        "3x Cost Delta",
        "Still Live-Ready",
        "Preserves Core Edge",
    ]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def _cards(summary: pd.DataFrame) -> str:
    enhanced_count = int(summary["best_live_ready"].sum())
    preserved_count = int(summary["preserves_core_edge"].sum())
    total_delta = float(summary.loc[summary["best_live_ready"], "net_delta"].sum())
    max_delta = float(summary["net_delta"].max())
    no_candidate_count = int((summary["quick_candidates"] == 0).sum())
    return f"""
      <div class="metric-grid">
        <div class="metric"><strong>Live-Ready Enhanced</strong><span>{enhanced_count} / {len(summary)}</span></div>
        <div class="metric"><strong>Core Edge Preserved</strong><span>{preserved_count} / {len(summary)}</span></div>
        <div class="metric"><strong>Total Net Delta</strong><span>{_fmt(total_delta)} points</span></div>
        <div class="metric"><strong>Best Single Delta</strong><span>{_fmt(max_delta)} points</span></div>
        <div class="metric"><strong>No Quick Candidate</strong><span>{no_candidate_count}</span></div>
        <div class="metric"><strong>Interpretation</strong><span>多数策略能增强，但不是全部；增强必须按策略族和稳定性门槛逐个验证。</span></div>
      </div>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HTML report for Top10 enhancement assessment.")
    parser.add_argument("--summary", default=".tmp/mbp-top10-enhancement-summary.csv")
    parser.add_argument("--output", default="reports/NQM6-mbp-top10-enhancement-assessment.html")
    args = parser.parse_args()

    summary = pd.read_csv(args.summary)
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NQM6 Top10 Enhancement Assessment</title>
  <style>
    body {{ margin: 0; padding: 28px; background: #0f1016; color: #f4f1ea; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 1220px; margin: 0 auto; }}
    .card {{ background: rgba(28, 29, 38, .94); border: 1px solid #3c3d4a; border-radius: 18px; padding: 20px; margin-bottom: 18px; box-shadow: 0 16px 50px rgba(0,0,0,.28); overflow-x: auto; }}
    h1, h2 {{ margin: 0 0 12px; }}
    p {{ color: #c7c1b4; line-height: 1.65; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #3c3d4a; text-align: left; }}
    th {{ color: #eee4d2; text-transform: uppercase; letter-spacing: .04em; font-size: 12px; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px; }}
    .metric {{ border: 1px solid #3c3d4a; border-radius: 12px; padding: 12px; background: rgba(15, 16, 22, .48); }}
    .metric strong {{ display: block; margin-bottom: 6px; color: #fffaf0; }}
    .metric span {{ color: #c7c1b4; line-height: 1.55; }}
    .badge {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: rgba(245,158,11,.16); color: #fbbf24; margin-bottom: 10px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <span class="badge">Top10 Enhancement · NQM6</span>
      <h1>NQM6 Live-Ready Top10 增强潜力评估</h1>
      <p>本报告逐个策略做同族一跳参数扰动，并要求增强候选仍满足 live-ready。Preserves Core Edge 进一步要求 positive fold/window、3x 成本净收益、最差 10 日窗口不低于原策略。</p>
    </section>
    <section class="card">
      <h2>结论摘要</h2>
      {_cards(summary)}
    </section>
    <section class="card">
      <h2>逐策略结果</h2>
      {_table(summary)}
    </section>
  </div>
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
