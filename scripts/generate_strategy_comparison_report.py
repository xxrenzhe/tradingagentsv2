from __future__ import annotations

import argparse
import html
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from tradingagents.backtesting.short_patterns import (
    StrategySpec,
    evaluate_strategies,
    prepare_minute_features,
)
from tradingagents.dataflows.databento import _read_bar_window, _read_mbp_window


@dataclass(frozen=True)
class StrategyCase:
    label: str
    spec: StrategySpec
    start_minute: int | None = None
    end_minute: int | None = None


def _load_cached_features(symbol: str, start_date: str, end_date: str, cache_path: Path) -> pd.DataFrame | None:
    if not cache_path.exists():
        return None
    cache = pd.read_pickle(cache_path)
    prefix = f"{symbol.upper()}|{start_date}|{end_date}|with-mbp|"
    for key, value in cache.items():
        if str(key).startswith(prefix):
            features = value.get("features")
            if isinstance(features, pd.DataFrame) and not features.empty:
                return features
    return None


def _equity_points(trades: pd.DataFrame) -> list[float]:
    if trades.empty:
        return [0.0]
    return [0.0, *trades["net_points"].cumsum().round(4).tolist()]


def _summary_lookup(results: pd.DataFrame, name: str) -> dict:
    row = results.loc[results["name"] == name]
    if row.empty:
        raise SystemExit(f"Strategy not found in ranking: {name}")
    return row.iloc[0].to_dict()


def _trade_table(trades: pd.DataFrame, limit: int = 25) -> str:
    if trades.empty:
        return "<p>No trades generated.</p>"
    display = trades.tail(limit).copy()
    display["entry_ts"] = pd.to_datetime(display["entry_ts"]).dt.strftime("%Y-%m-%d %H:%M")
    display["exit_ts"] = pd.to_datetime(display["exit_ts"]).dt.strftime("%Y-%m-%d %H:%M")
    return display.to_html(index=False, classes="trade-table", border=0, escape=True)


def _svg_line_chart(series_map: dict[str, list[float]], title: str) -> str:
    width = 980
    height = 360
    left = 60
    right = 20
    top = 20
    bottom = 40
    plot_width = width - left - right
    plot_height = height - top - bottom

    all_values = [value for series in series_map.values() for value in series]
    min_value = min(all_values)
    max_value = max(all_values)
    if max_value == min_value:
        max_value += 1.0
        min_value -= 1.0

    def x_for(index: int, count: int) -> float:
        if count <= 1:
            return left
        return left + (index / (count - 1)) * plot_width

    def y_for(value: float) -> float:
        return top + (max_value - value) / (max_value - min_value) * plot_height

    palette = ["#e4572e", "#2e86ab", "#2ca58d"]
    lines = []
    labels = []
    for idx, (name, series) in enumerate(series_map.items()):
        points = " ".join(
            f"{x_for(i, len(series)):.1f},{y_for(value):.1f}" for i, value in enumerate(series)
        )
        color = palette[idx % len(palette)]
        lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="3" points="{points}" />')
        labels.append(
            f'<g><rect x="{left + idx * 240}" y="{height - 24}" width="14" height="14" fill="{color}"/>'
            f'<text x="{left + 20 + idx * 240}" y="{height - 12}" font-size="12" fill="#d7e1ea">{html.escape(name)}</text></g>'
        )

    axis = f"""
    <line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#52606d"/>
    <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#52606d"/>
    <text x="{left}" y="14" font-size="16" fill="#f5f7fa">{html.escape(title)}</text>
    """
    return f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">{axis}{"".join(lines)}{"".join(labels)}</svg>'


def _recommendation(rows: list[dict]) -> tuple[str, str]:
    by_label = {row["label"]: row for row in rows}
    primary = by_label["MBP mean reversion"]
    conservative = by_label["US RTH mean reversion"]
    profit_leader = max(rows, key=lambda row: row["net_points"])

    reason = (
        f"首选 `mean_reversion_lb15_thr0.6_hold10_imb0.35`，因为它在三者里兼顾了较高净利润 "
        f"({primary['net_points']:.3f} points)、较低最大回撤 ({primary['max_drawdown_points']:.3f})、"
        f"更高 profit factor ({primary['profit_factor']:.3f}) 和更好的稳定性 ({primary['stability']:.4f})。"
        f" `mean_reversion_lb15_thr1.4_hold5` 只在 US RTH 交易时，回撤更低 ({conservative['max_drawdown_points']:.3f})，"
        f"适合作为执行约束更强的备选。"
        f" `mean_reversion_lb5_thr1.4_hold10` 的净利润最高 ({profit_leader['net_points']:.3f})，"
        f"但其最大回撤显著更大 ({profit_leader['max_drawdown_points']:.3f})，更像是高收益但风险较重的版本。"
    )
    return "mean_reversion_lb15_thr0.6_hold10_imb0.35", reason


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a 3-strategy HTML comparison report.")
    parser.add_argument("--symbol", default="NQM6")
    parser.add_argument("--start-date", default="2026-04-27")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--output", default="reports/NQM6-strategy-comparison.html")
    parser.add_argument("--features-cache", default=".tmp/short-patterns-features-cache.pkl")
    args = parser.parse_args()

    cases = [
        StrategyCase(
            label="MBP mean reversion",
            spec=StrategySpec(
                name="mean_reversion_lb15_thr0.6_hold10_imb0.35",
                family="mean_reversion",
                lookback=15,
                threshold=0.6,
                holding_minutes=10,
                imbalance_threshold=0.35,
                max_spread_quantile=0.75,
                min_depth_quantile=0.25,
            ),
        ),
        StrategyCase(
            label="US RTH mean reversion",
            spec=StrategySpec(
                name="mean_reversion_lb15_thr1.4_hold5",
                family="mean_reversion",
                lookback=15,
                threshold=1.4,
                holding_minutes=5,
            ),
            start_minute=13 * 60 + 30,
            end_minute=20 * 60,
        ),
        StrategyCase(
            label="Highest net profit",
            spec=StrategySpec(
                name="mean_reversion_lb5_thr1.4_hold10",
                family="mean_reversion",
                lookback=5,
                threshold=1.4,
                holding_minutes=10,
            ),
        ),
    ]

    features = _load_cached_features(args.symbol, args.start_date, args.end_date, Path(args.features_cache))
    if features is None:
        bars = _read_bar_window(args.symbol, args.start_date, args.end_date)
        microstructure = _read_mbp_window(args.symbol, args.start_date, args.end_date)
        features = prepare_minute_features(bars, microstructure)

    rows = []
    curves = {}
    trades_by_label = {}
    for case in cases:
        case_features = features
        if case.start_minute is not None:
            case_features = case_features[case_features["minute_of_day"] >= case.start_minute]
        if case.end_minute is not None:
            case_features = case_features[case_features["minute_of_day"] < case.end_minute]
        case_features = case_features.reset_index(drop=True)
        results, trades_by_name = evaluate_strategies(case_features, specs=[case.spec], min_trades=5)
        summary = _summary_lookup(results, case.spec.name)
        summary["label"] = case.label
        if case.start_minute is None and case.end_minute is None:
            summary["scope"] = "All day"
        else:
            summary["scope"] = f"{case.start_minute // 60:02d}:{case.start_minute % 60:02d}-{case.end_minute // 60:02d}:{case.end_minute % 60:02d} UTC"
        trades = trades_by_name[case.spec.name]
        rows.append(summary)
        curves[f"{case.label}: {case.spec.name}"] = _equity_points(trades)
        trades_by_label[case.label] = trades

    winner, rationale = _recommendation(rows)

    rendered_rows = []
    for row in rows:
        rendered_rows.append(
            "<tr>"
            f"<td>{html.escape(row['label'])}</td>"
            f"<td>{html.escape(row['name'])}</td>"
            f"<td>{html.escape(row['scope'])}</td>"
            f"<td>{int(row['trades'])}</td>"
            f"<td>{row['net_points']:.3f}</td>"
            f"<td>{row['max_drawdown_points']:.3f}</td>"
            f"<td>{row['profit_factor']:.3f}</td>"
            f"<td>{row['win_rate']:.2%}</td>"
            f"<td>{row['score']:.3f}</td>"
            "</tr>"
        )

    trade_sections = []
    for case in cases:
        trade_sections.append(
            f"<section><h3>{html.escape(case.label)}: {html.escape(case.spec.name)}</h3>"
            f"<p><strong>Top trades</strong></p>{_trade_table(trades_by_label[case.label], limit=12)}</section>"
        )

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(args.symbol)} 三策略资金曲线对比</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b1220;
      --panel: #111a2e;
      --panel-2: #16233d;
      --text: #e8eef6;
      --muted: #a6b3c2;
      --accent: #58a6ff;
      --border: #25324a;
    }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #08101d, #0b1220 35%, #0f1728);
      color: var(--text);
      padding: 28px;
    }}
    .container {{
      max-width: 1180px;
      margin: 0 auto;
    }}
    .hero, .card {{
      background: rgba(17, 26, 46, 0.9);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 20px;
      box-shadow: 0 14px 50px rgba(0, 0, 0, 0.28);
      margin-bottom: 18px;
    }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    p {{ color: var(--muted); line-height: 1.6; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); text-align: left; }}
    th {{ color: #cfe0f2; font-size: 13px; text-transform: uppercase; letter-spacing: .04em; }}
    svg {{ width: 100%; height: auto; display: block; background: var(--panel); border-radius: 14px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }}
    .badge {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: rgba(88,166,255,.14); color: #9ecbff; }}
    .recommendation {{ border-left: 4px solid var(--accent); padding-left: 14px; }}
    .trade-table {{ font-size: 13px; }}
    section {{ margin-top: 18px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="hero">
      <span class="badge">Databento NQM6</span>
      <h1>三策略资金曲线对比</h1>
      <p>窗口：{html.escape(args.start_date)} 到 {html.escape(args.end_date)}。对比对象为两条已指定策略，加上一条全量回测中净利润最高的策略；其中 US RTH 策略按 13:30-20:00 UTC 独立评估。</p>
    </div>

    <div class="card">
      <h2>策略指标</h2>
      <table>
        <thead>
          <tr>
            <th>Case</th><th>Strategy</th><th>Scope</th><th>Trades</th><th>Net Points</th><th>Max DD</th><th>PF</th><th>Win Rate</th><th>Score</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rendered_rows)}
        </tbody>
      </table>
    </div>

    <div class="card">
      <h2>资金曲线</h2>
      {_svg_line_chart(curves, "Equity Curve Comparison (Net Points)")}
    </div>

    <div class="card recommendation">
      <h2>推荐</h2>
      <p><strong>推荐策略：</strong>{html.escape(winner)}</p>
      <p>{html.escape(rationale)}</p>
    </div>

    <div class="card">
      <h2>交易明细</h2>
      {''.join(trade_sections)}
    </div>
  </div>
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
