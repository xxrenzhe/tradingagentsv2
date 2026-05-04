from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

BEST_STRATEGY = "adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3"
ADAPTIVE_STRATEGY = "adaptive_defensive_mr_trendstable_mr_meanstable_mr_fallbackdefensive_mr_us0_eu1_gap1_cap24"
IMPROVED_STRATEGY = "adaptive_defensive_mr_trendtrend_vwap_meanstable_mr_fallbackdefensive_mr_us1_eu1_gap1_cap0"
POINT_VALUE = 20.0


@dataclass(frozen=True)
class StrategyReport:
    label: str
    strategy_id: str
    trades: pd.DataFrame
    metrics: dict[str, float | int | str]


def _load_trades(path: Path, strategy_id: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    trades = pd.read_csv(path)
    if "portfolio_rule" not in trades.columns:
        raise ValueError(f"{path} does not contain portfolio_rule")
    trades = trades.loc[trades["portfolio_rule"].astype(str) == strategy_id].copy()
    if trades.empty:
        raise ValueError(f"No trades for strategy {strategy_id} in {path}")
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True, errors="coerce")
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True, errors="coerce")
    trades["trade_date"] = pd.to_datetime(trades["trade_date"], errors="coerce").dt.date
    for column in ["net_points", "gross_points", "net_dollars", "direction", "holding_minutes"]:
        if column in trades.columns:
            trades[column] = pd.to_numeric(trades[column], errors="coerce")
    trades = trades.sort_values(["entry_ts", "exit_ts"]).reset_index(drop=True)
    trades["net_points"] = trades["net_points"].fillna(0.0)
    trades["equity_points"] = trades["net_points"].cumsum()
    trades["drawdown_points"] = trades["equity_points"].cummax() - trades["equity_points"]
    trades["trade_number"] = range(1, len(trades) + 1)
    return trades


def _build_adaptive_candidate_trades(
    *,
    strategy_id: str,
    features_cache: Path,
    enhanced_results: Path,
    refined_results: Path,
    stability_results: Path,
    output_path: Path,
) -> pd.DataFrame:
    from optimize_mbp_adaptive_portfolio import (
        OPTIMIZED_NAMES,
        _attach_regime,
        _build_portfolio_trades,
        _build_strategy_trades,
        _load_features,
        _load_strategy_rows,
        _rule_grid,
    )
    from tradingagents.backtesting.short_patterns import BacktestCosts

    features = _attach_regime(_load_features(features_cache))
    strategy_rows = _load_strategy_rows([enhanced_results, refined_results, stability_results], OPTIMIZED_NAMES)
    trades_by_alias = _build_strategy_trades(features, strategy_rows)
    rules = {rule.name: rule for rule in _rule_grid()}
    if strategy_id not in rules:
        raise ValueError(f"Unknown adaptive portfolio rule: {strategy_id}")
    trades = _build_portfolio_trades(features, trades_by_alias, rules[strategy_id], BacktestCosts())
    if trades.empty:
        raise ValueError(f"Adaptive portfolio rule produced no trades: {strategy_id}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(output_path, index=False)
    return _load_trades(output_path, strategy_id)


def _load_or_build_candidate_trades(
    *,
    path: Path,
    strategy_id: str,
    features_cache: Path,
    enhanced_results: Path,
    refined_results: Path,
    stability_results: Path,
) -> pd.DataFrame:
    if path.exists():
        try:
            return _load_trades(path, strategy_id)
        except ValueError:
            pass
    return _build_adaptive_candidate_trades(
        strategy_id=strategy_id,
        features_cache=features_cache,
        enhanced_results=enhanced_results,
        refined_results=refined_results,
        stability_results=stability_results,
        output_path=path,
    )


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    running_max = equity.cummax()
    return float((running_max - equity).max())


def _profit_factor(net_points: pd.Series) -> float:
    gross_profit = float(net_points[net_points > 0].sum())
    gross_loss = abs(float(net_points[net_points < 0].sum()))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _longest_streak(values: Iterable[float], *, wins: bool) -> int:
    best = current = 0
    for value in values:
        matched = value > 0 if wins else value < 0
        if matched:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _rolling_window_min(trades: pd.DataFrame, days: int = 10) -> float:
    if trades.empty:
        return 0.0
    daily = trades.groupby(pd.to_datetime(trades["trade_date"]))["net_points"].sum().sort_index()
    if daily.empty:
        return 0.0
    full_index = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(full_index, fill_value=0.0)
    if len(daily) < days:
        return float(daily.sum())
    return float(daily.rolling(days).sum().dropna().min())


def _metrics(trades: pd.DataFrame) -> dict[str, float | int | str]:
    net = trades["net_points"]
    equity = net.cumsum()
    wins = int((net > 0).sum())
    losses = int((net < 0).sum())
    daily = trades.groupby(pd.to_datetime(trades["trade_date"]))["net_points"].sum().sort_index()
    net_points = float(net.sum())
    max_dd = _max_drawdown(equity)
    return {
        "start": str(trades["entry_ts"].min()),
        "end": str(trades["exit_ts"].max()),
        "calendar_days": int((trades["exit_ts"].max().date() - trades["entry_ts"].min().date()).days) + 1,
        "trades": int(len(trades)),
        "net_points": net_points,
        "net_dollars": net_points * POINT_VALUE,
        "max_drawdown_points": max_dd,
        "net_to_drawdown": net_points / max_dd if max_dd > 0 else float("inf"),
        "profit_factor": _profit_factor(net),
        "win_rate": wins / len(trades) if len(trades) else 0.0,
        "avg_trade_points": float(net.mean()),
        "median_trade_points": float(net.median()),
        "best_trade_points": float(net.max()),
        "worst_trade_points": float(net.min()),
        "positive_days": int((daily > 0).sum()),
        "trading_days": int(len(daily)),
        "positive_day_rate": float((daily > 0).mean()) if len(daily) else 0.0,
        "worst_day_points": float(daily.min()) if len(daily) else 0.0,
        "best_day_points": float(daily.max()) if len(daily) else 0.0,
        "worst_10d_points": _rolling_window_min(trades, days=10),
        "longest_win_streak": _longest_streak(net, wins=True),
        "longest_loss_streak": _longest_streak(net, wins=False),
        "short_share": float((trades["direction"] < 0).mean()) if "direction" in trades else 0.0,
        "long_share": float((trades["direction"] > 0).mean()) if "direction" in trades else 0.0,
        "avg_holding_minutes": float(trades["holding_minutes"].mean()) if "holding_minutes" in trades else 0.0,
        "losses": losses,
        "wins": wins,
    }


def _curve_points(trades: pd.DataFrame, mode: str) -> list[tuple[float, float]]:
    if mode == "date":
        daily = trades.groupby(pd.to_datetime(trades["trade_date"]))["net_points"].sum().sort_index()
        if daily.empty:
            return [(0.0, 0.0)]
        cumulative = daily.cumsum()
        start = daily.index.min()
        return [(0.0, 0.0), *[((date - start).days + 1, float(value)) for date, value in cumulative.items()]]
    return [(0.0, 0.0), *[(float(row.trade_number), float(row.equity_points)) for row in trades.itertuples()]]


def _drawdown_points(trades: pd.DataFrame) -> list[tuple[float, float]]:
    return [(0.0, 0.0), *[(float(row.trade_number), float(row.drawdown_points)) for row in trades.itertuples()]]


def _svg_line_chart(
    series_map: dict[str, list[tuple[float, float]]],
    title: str,
    *,
    y_label: str,
    invert_y: bool = False,
) -> str:
    width, height = 1120, 420
    left, right, top, bottom = 74, 34, 42, 62
    plot_width = width - left - right
    plot_height = height - top - bottom
    all_x = [point[0] for series in series_map.values() for point in series]
    all_y = [point[1] for series in series_map.values() for point in series]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    if min_y == max_y:
        min_y -= 1
        max_y += 1
    if min_x == max_x:
        max_x += 1

    def x_for(value: float) -> float:
        return left + (value - min_x) / (max_x - min_x) * plot_width

    def y_for(value: float) -> float:
        ratio = (value - min_y) / (max_y - min_y)
        if not invert_y:
            ratio = 1 - ratio
        return top + ratio * plot_height

    palette = ["#e85d3f", "#2fb8ac", "#8ab4ff", "#f4c95d"]
    grid = []
    for index in range(5):
        value = min_y + (max_y - min_y) * index / 4
        y = y_for(value)
        grid.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#20313b" stroke-width="1"/>'
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#9fb5bd">{value:.0f}</text>'
        )
    lines = []
    legends = []
    for index, (name, points) in enumerate(series_map.items()):
        color = palette[index % len(palette)]
        polyline = " ".join(f"{x_for(x):.1f},{y_for(y):.1f}" for x, y in points)
        lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.8" points="{polyline}"/>')
        legends.append(
            f'<span class="legend-item"><span style="background:{color}"></span>{html.escape(name)}</span>'
        )
    return f"""
    <figure class="chart-card">
      <figcaption>
        <strong>{html.escape(title)}</strong>
        <small>{html.escape(y_label)}</small>
      </figcaption>
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
        <rect x="0" y="0" width="{width}" height="{height}" fill="#07110f"/>
        {''.join(grid)}
        <line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#66818c"/>
        <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#66818c"/>
        <text x="{left}" y="25" font-size="17" fill="#ecfdf5">{html.escape(title)}</text>
        <text x="{left + plot_width - 8}" y="{top + plot_height + 34}" text-anchor="end" font-size="12" fill="#9fb5bd">Trade sequence / days</text>
        {''.join(lines)}
      </svg>
      <div class="legend">{''.join(legends)}</div>
    </figure>
    """


def _metric_rows(reports: list[StrategyReport]) -> str:
    labels = [report.label for report in reports]
    metrics = [
        ("交易数", "trades", "{:.0f}"),
        ("净点数", "net_points", "{:.2f}"),
        ("估算净美元", "net_dollars", "${:,.0f}"),
        ("最大回撤点数", "max_drawdown_points", "{:.2f}"),
        ("净点数 / 最大回撤", "net_to_drawdown", "{:.2f}"),
        ("Profit Factor", "profit_factor", "{:.3f}"),
        ("胜率", "win_rate", "{:.2%}"),
        ("平均每笔点数", "avg_trade_points", "{:.2f}"),
        ("中位每笔点数", "median_trade_points", "{:.2f}"),
        ("最差单笔点数", "worst_trade_points", "{:.2f}"),
        ("最差单日点数", "worst_day_points", "{:.2f}"),
        ("最差 10 日滚动点数", "worst_10d_points", "{:.2f}"),
        ("正收益日比例", "positive_day_rate", "{:.2%}"),
        ("最长连续亏损", "longest_loss_streak", "{:.0f}"),
        ("平均持仓分钟", "avg_holding_minutes", "{:.2f}"),
        ("多头占比", "long_share", "{:.2%}"),
        ("空头占比", "short_share", "{:.2%}"),
    ]
    header = "<tr><th>指标</th>" + "".join(f"<th>{html.escape(label)}</th>" for label in labels) + "</tr>"
    rows = []
    for metric_label, key, formatter in metrics:
        cells = []
        for report in reports:
            value = report.metrics[key]
            cells.append(f"<td>{formatter.format(value)}</td>")
        rows.append(f"<tr><td>{html.escape(metric_label)}</td>{''.join(cells)}</tr>")
    return f"<table>{header}{''.join(rows)}</table>"


def _trade_distribution(reports: list[StrategyReport]) -> str:
    cards = []
    for report in reports:
        by_exit = report.trades["exit_reason"].value_counts(normalize=True).mul(100).round(1).to_dict()
        by_alias = (
            report.trades["selected_alias"].value_counts(normalize=True).mul(100).round(1).to_dict()
            if "selected_alias" in report.trades
            else {}
        )
        cards.append(
            f"""
            <section class="mini-card">
              <h3>{html.escape(report.label)}</h3>
              <p><strong>Exit reason:</strong> {html.escape(json.dumps(by_exit, ensure_ascii=False))}</p>
              <p><strong>Selected alias:</strong> {html.escape(json.dumps(by_alias, ensure_ascii=False))}</p>
              <p><strong>Time span:</strong> {html.escape(str(report.metrics['start']))} 至 {html.escape(str(report.metrics['end']))}</p>
            </section>
            """
        )
    return "".join(cards)


def _recent_trades_table(report: StrategyReport, limit: int = 18) -> str:
    columns = ["entry_ts", "exit_ts", "direction", "entry_price", "exit_price", "net_points", "exit_reason", "selected_alias"]
    existing = [column for column in columns if column in report.trades.columns]
    display = report.trades.tail(limit)[existing].copy()
    for column in ["entry_ts", "exit_ts"]:
        if column in display:
            display[column] = pd.to_datetime(display[column]).dt.strftime("%Y-%m-%d %H:%M")
    return display.to_html(index=False, classes="trade-table", border=0, escape=True)


def _write_report(reports: list[StrategyReport], output: Path) -> None:
    report_by_id = {report.strategy_id: report for report in reports}
    best = report_by_id[BEST_STRATEGY]
    adaptive = report_by_id[ADAPTIVE_STRATEGY]
    improved = report_by_id[IMPROVED_STRATEGY]
    sequence_curves = {report.label: _curve_points(report.trades, "sequence") for report in reports}
    date_curves = {report.label: _curve_points(report.trades, "date") for report in reports}
    drawdowns = {report.label: _drawdown_points(report.trades) for report in reports}
    verdict = (
        "新增候选策略显著提高了总净点数，但最大回撤也同步放大；"
        "当前 best strategy 仍是回撤效率最优，适合作为风险优先首选。"
    )
    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>NQM6 Best vs Adaptive Strategy Report</title>
  <style>
    :root {{
      --bg: #06100d;
      --panel: #0d1b17;
      --panel-2: #10241f;
      --ink: #eaf7ef;
      --muted: #9fb5ad;
      --line: #203d34;
      --accent: #f0b35a;
      --green: #2fb8ac;
      --red: #e85d3f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at 10% 0%, rgba(240, 179, 90, .14), transparent 30%),
        radial-gradient(circle at 90% 10%, rgba(47, 184, 172, .12), transparent 28%),
        var(--bg);
      color: var(--ink);
      font: 15px/1.55 "Avenir Next", "Futura", "Trebuchet MS", sans-serif;
    }}
    main {{ width: min(1180px, calc(100vw - 32px)); margin: 0 auto; padding: 44px 0 72px; }}
    header {{ padding: 28px; border: 1px solid var(--line); border-radius: 26px; background: linear-gradient(135deg, rgba(13,27,23,.92), rgba(16,36,31,.82)); }}
    h1 {{ margin: 0 0 10px; font-size: clamp(30px, 5vw, 58px); line-height: .98; letter-spacing: -1.8px; }}
    h2 {{ margin: 34px 0 14px; font-size: 24px; }}
    h3 {{ margin: 0 0 8px; }}
    .badge {{ display: inline-flex; padding: 6px 10px; border-radius: 999px; background: rgba(240,179,90,.14); color: #ffd796; border: 1px solid rgba(240,179,90,.35); font-size: 12px; margin-bottom: 18px; }}
    .lead {{ max-width: 920px; color: var(--muted); font-size: 17px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 18px; }}
    .card, .chart-card, .mini-card {{ border: 1px solid var(--line); border-radius: 20px; background: rgba(13,27,23,.86); box-shadow: 0 22px 70px rgba(0,0,0,.22); }}
    .card {{ padding: 22px; }}
    .kpi {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 22px 0; }}
    .kpi div {{ padding: 16px; border: 1px solid var(--line); border-radius: 18px; background: rgba(16,36,31,.76); }}
    .kpi strong {{ display: block; font-size: 24px; color: var(--accent); }}
    .kpi span {{ color: var(--muted); font-size: 12px; }}
    table {{ width: 100%; border-collapse: collapse; overflow: hidden; border-radius: 16px; background: rgba(13,27,23,.75); }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ color: #cbe3da; background: rgba(32,61,52,.62); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    td {{ color: #eaf7ef; }}
    figcaption {{ padding: 16px 18px 0; display: flex; justify-content: space-between; gap: 16px; color: var(--muted); }}
    figcaption strong {{ color: var(--ink); }}
    svg {{ width: 100%; height: auto; display: block; border-radius: 0 0 18px 18px; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 12px; padding: 0 18px 16px; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 7px; color: var(--muted); font-size: 12px; }}
    .legend-item span {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
    .mini-card {{ padding: 18px; }}
    .mini-card p {{ margin: 7px 0; color: var(--muted); overflow-wrap: anywhere; }}
    .trade-table {{ font-size: 12px; }}
    .note {{ color: var(--muted); border-left: 3px solid var(--accent); padding-left: 14px; }}
    @media (max-width: 820px) {{
      .grid, .kpi {{ grid-template-columns: 1fr; }}
      th, td {{ font-size: 12px; padding: 8px; }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <div class="badge">NQM6 MBP strategy comparison · generated from local trade CSVs</div>
    <h1>Best Strategy vs Adaptive Candidates</h1>
    <p class="lead">{html.escape(verdict)} 本报告只评价本地回测/纸盘输入样本，不构成实盘许可；live readiness 仍取决于 365 天 MBP 历史和至少 20 笔 paper outcomes。</p>
  </header>

  <section class="kpi">
    <div><strong>{best.metrics['net_points']:.0f}</strong><span>Best strategy net points</span></div>
    <div><strong>{adaptive.metrics['net_points']:.0f}</strong><span>Adaptive cap24 net points</span></div>
    <div><strong>{improved.metrics['net_points']:.0f}</strong><span>New candidate net points</span></div>
    <div><strong>{best.metrics['net_to_drawdown']:.2f}</strong><span>Best net/DD</span></div>
  </section>

  <h2>结论</h2>
  <section class="card">
    <p>新增候选 <code>{html.escape(improved.strategy_id)}</code> 是本轮找到的高收益版本：净点数达到 {improved.metrics['net_points']:.2f}，高于当前 best 的 {best.metrics['net_points']:.2f} 和旧 adaptive cap24 的 {adaptive.metrics['net_points']:.2f}。</p>
    <p>它不是全维度替代：最大回撤 {improved.metrics['max_drawdown_points']:.2f} 点，明显高于当前 best 的 {best.metrics['max_drawdown_points']:.2f} 点；净点数/最大回撤为 {improved.metrics['net_to_drawdown']:.2f}，低于当前 best 的 {best.metrics['net_to_drawdown']:.2f}。</p>
    <p>因此推荐分层使用：风险优先继续用 <code>{html.escape(best.strategy_id)}</code>；若目标是提高总收益且能接受约 {improved.metrics['max_drawdown_points']:.0f} 点历史最大回撤，可把新增候选作为进攻型组合版本进入 paper 验证。</p>
    <p class="note">两者都仍是研究/验证候选。当前 live blockers 包括 MBP 长历史不足和 paper outcomes 不足。</p>
  </section>

  <h2>核心指标对比</h2>
  {_metric_rows(reports)}

  <h2>资金曲线</h2>
  {_svg_line_chart(sequence_curves, "资金曲线：按交易序列累计净点数", y_label="Net points")}
  {_svg_line_chart(date_curves, "资金曲线：按交易日期累计净点数", y_label="Net points")}
  {_svg_line_chart(drawdowns, "回撤曲线：按交易序列", y_label="Drawdown points", invert_y=True)}

  <h2>交易结构</h2>
  <section class="grid">{_trade_distribution(reports)}</section>

  <h2>最近交易样本</h2>
  <section class="grid">
    {''.join(f'<div class="card"><h3>{html.escape(report.label)}</h3>{_recent_trades_table(report)}</div>' for report in reports)}
  </section>
</main>
</body>
</html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HTML report comparing best MBP strategy and adaptive cap24.")
    parser.add_argument("--best-trades", default=".tmp/mbp-best-strategy-trades.csv")
    parser.add_argument("--adaptive-trades", default=".tmp/mbp-adaptive-portfolio-trades.csv")
    parser.add_argument("--improved-trades", default=".tmp/mbp-improved-adaptive-candidate-trades.csv")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--enhanced-results", default=".tmp/mbp-enhanced-top10.csv")
    parser.add_argument("--refined-results", default=".tmp/mbp-refined-mean-reversion.csv")
    parser.add_argument("--stability-results", default=".tmp/mbp-selected-stability-optimized.csv")
    parser.add_argument("--output", default="reports/NQM6-best-vs-adaptive-strategy-report.html")
    args = parser.parse_args()

    reports = [
        StrategyReport(
            label="Best MBP mean reversion",
            strategy_id=BEST_STRATEGY,
            trades=_load_trades(Path(args.best_trades), BEST_STRATEGY),
            metrics={},
        ),
        StrategyReport(
            label="Adaptive defensive/stable cap24",
            strategy_id=ADAPTIVE_STRATEGY,
            trades=_load_trades(Path(args.adaptive_trades), ADAPTIVE_STRATEGY),
            metrics={},
        ),
        StrategyReport(
            label="New high-net adaptive candidate",
            strategy_id=IMPROVED_STRATEGY,
            trades=_load_or_build_candidate_trades(
                path=Path(args.improved_trades),
                strategy_id=IMPROVED_STRATEGY,
                features_cache=Path(args.features_cache),
                enhanced_results=Path(args.enhanced_results),
                refined_results=Path(args.refined_results),
                stability_results=Path(args.stability_results),
            ),
            metrics={},
        ),
    ]
    reports = [
        StrategyReport(report.label, report.strategy_id, report.trades, _metrics(report.trades))
        for report in reports
    ]
    _write_report(reports, Path(args.output))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
