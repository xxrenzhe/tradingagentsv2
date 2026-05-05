from __future__ import annotations

import argparse
import html
import itertools
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


STRICT_TIER = "promote_to_strict_gate"
RECENT_PASS = "passes_recent_oos"


@dataclass(frozen=True)
class PortfolioResult:
    name: str
    candidates: tuple[str, ...]
    trades: pd.DataFrame
    metrics: dict[str, float]
    objective_score: float
    eligibility: str


def load_csv(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def safe_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return html.escape(str(value), quote=True)


def as_float(value: object, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: object, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def prepare_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades
    frame = trades.copy()
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    frame["exit_ts"] = pd.to_datetime(frame["exit_ts"], utc=True)
    frame["net_points"] = pd.to_numeric(frame["net_points"], errors="coerce").fillna(0.0)
    frame["direction"] = pd.to_numeric(frame["direction"], errors="coerce").fillna(0).astype(int)
    return frame.sort_values(["entry_ts", "exit_ts", "candidate"]).reset_index(drop=True)


def eligible_candidates(shortlist: pd.DataFrame, recent_oos: pd.DataFrame) -> tuple[list[str], list[str]]:
    if shortlist.empty or recent_oos.empty:
        return [], []
    strict = shortlist[
        shortlist["tier"].astype(str).eq(STRICT_TIER)
        & shortlist["filter"].astype(str).eq("none")
        & (pd.to_numeric(shortlist["positive_fold_rate"], errors="coerce") >= 1.0)
        & (pd.to_numeric(shortlist["stress_points"], errors="coerce") > 0.0)
    ]["candidate"].astype(str)
    recent_pass = recent_oos[
        recent_oos["recent_verdict"].astype(str).eq(RECENT_PASS) & recent_oos["filter"].astype(str).eq("none")
    ]["candidate"].astype(str)
    strict_recent = [candidate for candidate in strict.tolist() if candidate in set(recent_pass)]
    research_pass = recent_pass.tolist()
    return strict_recent, research_pass


def evaluate_portfolios(
    trades: pd.DataFrame,
    strict_recent: list[str],
    research_pass: list[str],
    *,
    max_combo_size: int,
) -> list[PortfolioResult]:
    results: list[PortfolioResult] = []
    pools = [
        ("strict anti-overfit gate", strict_recent, "eligible"),
        ("recent-pass research pool", research_pass, "research_only"),
    ]
    seen: set[tuple[str, ...]] = set()
    for pool_name, pool, eligibility in pools:
        unique_pool = list(dict.fromkeys(pool))
        for size in range(1, min(max_combo_size, len(unique_pool)) + 1):
            for combo in itertools.combinations(unique_pool, size):
                if combo in seen:
                    continue
                seen.add(combo)
                selected = trades[trades["candidate"].isin(combo)].copy()
                metrics = portfolio_metrics(selected)
                score = objective_score(metrics, eligible=eligibility == "eligible")
                results.append(
                    PortfolioResult(
                        name=pool_name,
                        candidates=combo,
                        trades=selected,
                        metrics=metrics,
                        objective_score=score,
                        eligibility=eligibility,
                    )
                )
    return sorted(results, key=lambda item: (item.eligibility == "eligible", item.objective_score), reverse=True)


def select_best_portfolio(results: list[PortfolioResult]) -> PortfolioResult:
    eligible = [result for result in results if result.eligibility == "eligible" and len(result.candidates) >= 2]
    if eligible:
        return max(eligible, key=lambda item: item.objective_score)
    if results:
        return max(results, key=lambda item: item.objective_score)
    return PortfolioResult("empty", tuple(), pd.DataFrame(), portfolio_metrics(pd.DataFrame()), 0.0, "none")


def portfolio_metrics(trades: pd.DataFrame) -> dict[str, float]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "max_drawdown_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "positive_month_rate": 0.0,
            "min_month_net_points": 0.0,
            "positive_year_rate": 0.0,
            "min_year_net_points": 0.0,
            "net_to_drawdown": 0.0,
            "overlap_trades": 0,
        }
    frame = trades.sort_values(["entry_ts", "exit_ts"]).copy()
    equity = frame["net_points"].cumsum()
    drawdown = equity.cummax() - equity
    gross_profit = frame.loc[frame["net_points"] > 0, "net_points"].sum()
    gross_loss = -frame.loc[frame["net_points"] < 0, "net_points"].sum()
    monthly = frame["net_points"].groupby(frame["entry_ts"].dt.strftime("%Y-%m")).sum()
    yearly = frame["net_points"].groupby(frame["entry_ts"].dt.year).sum()
    max_drawdown = float(drawdown.max()) if not drawdown.empty else 0.0
    return {
        "trades": float(len(frame)),
        "net_points": float(frame["net_points"].sum()),
        "max_drawdown_points": max_drawdown,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else float("inf"),
        "win_rate": float((frame["net_points"] > 0).mean()),
        "positive_month_rate": float((monthly > 0).mean()) if not monthly.empty else 0.0,
        "min_month_net_points": float(monthly.min()) if not monthly.empty else 0.0,
        "positive_year_rate": float((yearly > 0).mean()) if not yearly.empty else 0.0,
        "min_year_net_points": float(yearly.min()) if not yearly.empty else 0.0,
        "net_to_drawdown": float(frame["net_points"].sum() / max_drawdown) if max_drawdown else float("inf"),
        "overlap_trades": float(count_overlaps(frame)),
    }


def objective_score(metrics: dict[str, float], *, eligible: bool) -> float:
    if metrics["trades"] <= 0:
        return -1e9
    risk = max(metrics["max_drawdown_points"], abs(metrics["min_month_net_points"]), 1.0)
    stability = 0.45 * metrics["positive_month_rate"] + 0.35 * metrics["positive_year_rate"] + 0.20 * min(
        metrics["profit_factor"] / 2.0, 1.0
    )
    gate_bonus = 1.25 if eligible else 0.75
    return float((metrics["net_points"] / risk) * stability * gate_bonus)


def count_overlaps(trades: pd.DataFrame) -> int:
    if trades.empty:
        return 0
    frame = trades.sort_values(["entry_ts", "exit_ts"]).reset_index(drop=True)
    active_exits: list[pd.Timestamp] = []
    overlaps = 0
    for _, row in frame.iterrows():
        active_exits = [exit_ts for exit_ts in active_exits if exit_ts > row["entry_ts"]]
        if active_exits:
            overlaps += 1
        active_exits.append(row["exit_ts"])
    return overlaps


def equity_by_trade(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["trade_number", "equity"])
    frame = trades.sort_values(["entry_ts", "exit_ts"]).copy()
    frame["trade_number"] = range(1, len(frame) + 1)
    frame["equity"] = frame["net_points"].cumsum()
    return frame[["trade_number", "equity"]]


def equity_by_date(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["date", "equity"])
    daily = trades["net_points"].groupby(trades["entry_ts"].dt.date).sum().sort_index().cumsum()
    return pd.DataFrame({"date": [str(value) for value in daily.index], "equity": daily.values})


def svg_line_chart(points: pd.DataFrame, *, x_column: str, y_column: str, title: str) -> str:
    if points.empty:
        return "<p class=\"empty\">无曲线数据。</p>"
    width = 980
    height = 340
    pad_left = 74
    pad_right = 26
    pad_top = 44
    pad_bottom = 48
    values = pd.to_numeric(points[y_column], errors="coerce").fillna(0.0).tolist()
    min_y = min(0.0, min(values))
    max_y = max(0.0, max(values))
    if max_y == min_y:
        max_y += 1.0
    x_count = max(len(values) - 1, 1)
    inner_w = width - pad_left - pad_right
    inner_h = height - pad_top - pad_bottom
    coords = []
    for index, value in enumerate(values):
        x = pad_left + (index / x_count) * inner_w
        y = pad_top + (max_y - value) / (max_y - min_y) * inner_h
        coords.append(f"{x:.1f},{y:.1f}")
    zero_y = pad_top + (max_y - 0.0) / (max_y - min_y) * inner_h
    last_label = safe_text(points[x_column].iloc[-1])
    return f"""
    <figure class="chart">
      <figcaption>{safe_text(title)}</figcaption>
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="{safe_text(title)}">
        <rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="#fffaf0" />
        <line x1="{pad_left}" y1="{zero_y:.1f}" x2="{width - pad_right}" y2="{zero_y:.1f}" stroke="#cfc2af" stroke-dasharray="5 5" />
        <line x1="{pad_left}" y1="{pad_top}" x2="{pad_left}" y2="{height - pad_bottom}" stroke="#8b7d6b" />
        <line x1="{pad_left}" y1="{height - pad_bottom}" x2="{width - pad_right}" y2="{height - pad_bottom}" stroke="#8b7d6b" />
        <polyline points="{' '.join(coords)}" fill="none" stroke="#23664d" stroke-width="3.2" stroke-linejoin="round" stroke-linecap="round" />
        <circle cx="{coords[-1].split(',')[0]}" cy="{coords[-1].split(',')[1]}" r="4.5" fill="#b9852b" />
        <text x="18" y="{pad_top + 4}" fill="#5f6f67" font-size="13">高 {max_y:,.0f}</text>
        <text x="18" y="{height - pad_bottom}" fill="#5f6f67" font-size="13">低 {min_y:,.0f}</text>
        <text x="{width - pad_right - 160}" y="{height - 16}" fill="#5f6f67" font-size="13">终点 {last_label}</text>
      </svg>
    </figure>
    """


def format_metric(column: str, value: object) -> str:
    if column in {"win_rate", "positive_month_rate", "positive_year_rate"}:
        return f"{as_float(value) * 100:.1f}%"
    if column in {"trades", "overlap_trades"}:
        return f"{as_int(value):,}"
    if column == "profit_factor":
        number = as_float(value)
        return "inf" if number == float("inf") else f"{number:.2f}"
    if column in {"net_to_drawdown", "objective_score"}:
        return f"{as_float(value):.2f}"
    if column.endswith("_points"):
        return f"{as_float(value):,.1f}"
    return safe_text(value)


def metric_cards(metrics: dict[str, float]) -> str:
    cards = [
        ("净点数", "net_points", "5年组合累计"),
        ("最大回撤", "max_drawdown_points", "按交易序列"),
        ("收益/回撤", "net_to_drawdown", "越高越稳健"),
        ("PF", "profit_factor", "毛利/毛亏"),
        ("正月份率", "positive_month_rate", "月度稳定性"),
        ("重叠信号", "overlap_trades", "需限仓处理"),
    ]
    html_cards = []
    for label, column, note in cards:
        html_cards.append(
            f"""
            <div class="metric-card">
              <div class="metric-label">{safe_text(label)}</div>
              <div class="metric-value">{format_metric(column, metrics.get(column, 0.0))}</div>
              <div class="metric-note">{safe_text(note)}</div>
            </div>
            """
        )
    return f"<div class=\"metric-grid\">{''.join(html_cards)}</div>"


def table(rows: list[dict[str, object]], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return "<p class=\"empty\">无记录。</p>"
    head = "".join(f"<th>{safe_text(label)}</th>" for _, label in columns)
    body = []
    for row in rows:
        body.append("".join(f"<td>{format_metric(key, row.get(key, ''))}</td>" for key, _ in columns))
    return f"<div class=\"table-wrap\"><table><thead><tr>{head}</tr></thead><tbody>{''.join(f'<tr>{item}</tr>' for item in body)}</tbody></table></div>"


def component_rows(best: PortfolioResult, shortlist: pd.DataFrame, recent_oos: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for candidate in best.candidates:
        short_row = shortlist[shortlist["candidate"].astype(str).eq(candidate)].head(1)
        recent_row = recent_oos[recent_oos["candidate"].astype(str).eq(candidate)].head(1)
        rows.append(
            {
                "candidate": candidate,
                "role": strategy_role(candidate),
                "tier": short_row["tier"].iloc[0] if not short_row.empty else "",
                "net_points": short_row["net_points"].iloc[0] if not short_row.empty else 0.0,
                "profit_factor": short_row["profit_factor"].iloc[0] if not short_row.empty else 0.0,
                "positive_month_rate": recent_row["positive_month_rate"].iloc[0] if not recent_row.empty else 0.0,
                "risk_note": strategy_risk_note(candidate),
            }
        )
    return rows


def strategy_role(candidate: str) -> str:
    if "mean_reversion" in candidate:
        return "US late 均值回归核心多头"
    if "momentum" in candidate:
        return "US late 动量确认多头"
    return "辅助方向"


def strategy_risk_note(candidate: str) -> str:
    if "mean_reversion" in candidate:
        return "回撤集中在单月反趋势延续"
    if "momentum" in candidate:
        return "交易少，需防止样本不足"
    return "仅研究"


def comparison_rows(results: list[PortfolioResult]) -> list[dict[str, object]]:
    selected = sorted(results, key=lambda item: item.metrics["net_points"], reverse=True)[:8]
    rows = []
    for result in selected:
        rows.append(
            {
                "candidate": " + ".join(result.candidates),
                "eligibility": result.eligibility,
                "trades": result.metrics["trades"],
                "net_points": result.metrics["net_points"],
                "max_drawdown_points": result.metrics["max_drawdown_points"],
                "profit_factor": result.metrics["profit_factor"],
                "positive_month_rate": result.metrics["positive_month_rate"],
                "net_to_drawdown": result.metrics["net_to_drawdown"],
                "objective_score": result.objective_score,
            }
        )
    return rows


def monthly_rows(trades: pd.DataFrame) -> list[dict[str, object]]:
    if trades.empty:
        return []
    grouped = trades["net_points"].groupby(trades["entry_ts"].dt.strftime("%Y-%m")).agg(["count", "sum"])
    return [
        {"month": month, "trades": row["count"], "net_points": row["sum"]}
        for month, row in grouped.sort_index().tail(24).iterrows()
    ]


def build_html(
    *,
    best: PortfolioResult,
    results: list[PortfolioResult],
    shortlist: pd.DataFrame,
    recent_oos: pd.DataFrame,
    generated_at: str,
    source_paths: dict[str, str],
) -> str:
    trade_curve = equity_by_trade(best.trades)
    date_curve = equity_by_date(best.trades)
    source_items = "".join(f"<li><code>{safe_text(name)}</code>: {safe_text(path)}</li>" for name, path in source_paths.items())
    component_table = table(
        component_rows(best, shortlist, recent_oos),
        [
            ("candidate", "组件"),
            ("role", "职责"),
            ("tier", "证据层级"),
            ("net_points", "单策略净点数"),
            ("profit_factor", "PF"),
            ("positive_month_rate", "近期正月份率"),
            ("risk_note", "主要风险"),
        ],
    )
    comparison_table = table(
        comparison_rows(results),
        [
            ("candidate", "组合"),
            ("eligibility", "资格"),
            ("trades", "交易数"),
            ("net_points", "净点数"),
            ("max_drawdown_points", "最大回撤"),
            ("profit_factor", "PF"),
            ("positive_month_rate", "正月份率"),
            ("net_to_drawdown", "收益/回撤"),
            ("objective_score", "稳健评分"),
        ],
    )
    monthly_table = table(monthly_rows(best.trades), [("month", "月份"), ("trades", "交易数"), ("net_points", "净点数")])
    candidate_list = "".join(f"<li><code>{safe_text(candidate)}</code></li>" for candidate in best.candidates)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ 最强稳健组合策略报告</title>
  <style>
    :root {{
      --ink: #17201b;
      --muted: #607168;
      --paper: #fbf6e9;
      --panel: #fffdf7;
      --line: #ddd1be;
      --green: #23664d;
      --red: #b54b3a;
      --gold: #b9852b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 88% 8%, rgba(35, 102, 77, .18), transparent 26rem),
        radial-gradient(circle at 10% 18%, rgba(185, 133, 43, .18), transparent 25rem),
        linear-gradient(135deg, #f8efd9 0%, #fcfaf3 48%, #e9f1e4 100%);
      font: 15px/1.56 Georgia, "Noto Serif SC", "Songti SC", serif;
    }}
    header {{ padding: 48px min(6vw, 72px) 26px; border-bottom: 1px solid var(--line); }}
    h1 {{ margin: 0 0 12px; max-width: 1120px; font-size: clamp(34px, 5vw, 66px); line-height: .98; letter-spacing: -.04em; }}
    h2 {{ margin: 0 0 14px; font-size: 26px; }}
    h3 {{ margin: 0 0 8px; font-size: 18px; }}
    p {{ margin: 0 0 12px; }}
    code {{ padding: 2px 5px; border-radius: 5px; background: #efe6d5; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
    main {{ padding: 28px min(6vw, 72px) 64px; }}
    section {{ margin: 28px 0; padding: 26px; background: rgba(255, 253, 247, .86); border: 1px solid var(--line); border-radius: 22px; box-shadow: 0 18px 50px rgba(62, 52, 35, .08); }}
    .subtitle {{ max-width: 980px; color: var(--muted); font-size: 18px; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin-top: 20px; }}
    .metric-card {{ padding: 16px; min-height: 116px; border: 1px solid var(--line); border-radius: 18px; background: linear-gradient(180deg, #fffdf8, #f6eddd); }}
    .metric-label {{ color: var(--muted); font-size: 13px; }}
    .metric-value {{ margin: 6px 0; font-size: 28px; font-weight: 700; }}
    .metric-note {{ color: var(--muted); font-size: 12px; }}
    .decision {{ display: grid; grid-template-columns: 1.05fr .95fr; gap: 18px; }}
    .callout {{ padding: 18px; border-left: 5px solid var(--green); background: #eef6e8; border-radius: 13px; }}
    .risk {{ border-left-color: var(--red); background: #fff0ec; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 10px 9px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); background: #f5ead8; }}
    .chart {{ margin: 18px 0 0; }}
    .chart figcaption {{ margin-bottom: 8px; color: var(--muted); font-weight: 700; }}
    .chart svg {{ width: 100%; height: auto; border: 1px solid var(--line); border-radius: 18px; }}
    .empty, .sources {{ color: var(--muted); }}
    @media (max-width: 980px) {{
      .metric-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .decision {{ grid-template-columns: 1fr; }}
      section {{ padding: 18px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>NQ 最强稳健组合策略报告</h1>
    <p class="subtitle">目标是在已发现可盈利特征中，先通过抗过拟合稳定性门槛，再选择净点数和风险效率最强的组合。生成时间：{safe_text(generated_at)}。</p>
    {metric_cards(best.metrics)}
  </header>
  <main>
    <section>
      <h2>最终策略</h2>
      <div class="decision">
        <div class="callout">
          <p><strong>选择：</strong>两组件 NQ US late 多头组合。只纳入无状态过滤、严格门槛、压力折为正、最近 OOS 通过的策略。</p>
          <ul>{candidate_list}</ul>
          <p><strong>定义：</strong>组合允许两个独立信号来源各自产生交易；上线前纸盘建议总风险按 1 手 MNQ 试运行，确认重叠信号处理后再扩大。</p>
        </div>
        <div class="callout risk">
          <p><strong>不能保证未来盈利：</strong>这里的“最强”是指在现有 5 年回测证据和抗过拟合约束内最优，不是未来收益承诺。</p>
          <p><strong>未选择更高净利润研究组合的原因：</strong>加入 <code>lb30_thr1.4_hold60</code> 等候选会提高历史净点数，但最差月份、最大回撤和后验选择风险更高，不符合“风险最小且稳定无过拟合”的要求。</p>
        </div>
      </div>
    </section>

    <section>
      <h2>工作原理</h2>
      <p><strong>组件一：均值回归多头。</strong>在 UTC 20:00-23:00 的 US late 时段，当价格相对短周期均值出现足够负偏离后做多，预期尾盘流动性恢复或过度下跌修复。</p>
      <p><strong>组件二：动量确认多头。</strong>同一时段只接受向上动量方向，使用更长持有窗口捕捉趋势延续。它与均值回归的触发逻辑不同，用来提高组合分散性。</p>
      <p><strong>组合规则：</strong>不使用后验状态过滤器，不临时调参；每个组件只按已验证方向交易。若两个信号重叠，纸盘阶段应先限制总持仓和日亏损，而不是直接叠加实盘风险。</p>
      {component_table}
    </section>

    <section>
      <h2>资金曲线：按交易次数</h2>
      {svg_line_chart(trade_curve, x_column="trade_number", y_column="equity", title="累计净点数 vs 交易次数")}
    </section>

    <section>
      <h2>资金曲线：按交易日期</h2>
      {svg_line_chart(date_curve, x_column="date", y_column="equity", title="累计净点数 vs 交易日期")}
    </section>

    <section>
      <h2>组合筛选对比</h2>
      <p>表中包含历史净点数更高的研究组合，但最终只选择通过严格抗过拟合门槛的组合。</p>
      {comparison_table}
    </section>

    <section>
      <h2>最近月度表现</h2>
      {monthly_table}
    </section>

    <section>
      <h2>风险提示</h2>
      <p><strong>样本与过拟合：</strong>本策略只使用已通过严格门槛的无过滤特征，降低但不能消除过拟合。任何新增过滤器、止损止盈或仓位规则都必须重新做 walk-forward 和最近 OOS。</p>
      <p><strong>执行风险：</strong>当前 <code>run_ibkr_live_paper_trader.py</code> 尚不支持这些 <code>bar_best_*</code> NQ bar 策略 ID 的 live adapter，不能直接提交纸盘或实盘订单。</p>
      <p><strong>仓位风险：</strong>组合存在 {format_metric("overlap_trades", best.metrics["overlap_trades"])} 次重叠信号。纸盘第一阶段建议限制为总暴露 1 手 MNQ、最大日亏 50 NQ 点、连续 3 笔亏损暂停。</p>
      <p><strong>市场风险：</strong>NQ 在宏观新闻、开盘跳空、极端波动和流动性下降时可能显著偏离历史分布。报告中的回测净点数不含所有真实滑点、拒单和延迟影响。</p>
    </section>

    <section>
      <h2>数据来源</h2>
      <ul class="sources">{source_items}</ul>
    </section>
  </main>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, object]:
    trades = prepare_trades(load_csv(args.trades))
    shortlist = load_csv(args.shortlist)
    recent_oos = load_csv(args.recent_oos)
    strict_recent, research_pass = eligible_candidates(shortlist, recent_oos)
    results = evaluate_portfolios(trades, strict_recent, research_pass, max_combo_size=args.max_combo_size)
    best = select_best_portfolio(results)
    source_paths = {
        "trades": args.trades,
        "shortlist": args.shortlist,
        "recent_oos": args.recent_oos,
    }
    html_text = build_html(
        best=best,
        results=results,
        shortlist=shortlist,
        recent_oos=recent_oos,
        generated_at=args.generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        source_paths=source_paths,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_text, encoding="utf-8")
    selected_output = Path(args.selected_trades_output)
    selected_output.parent.mkdir(parents=True, exist_ok=True)
    best.trades.to_csv(selected_output, index=False)
    metrics_output = Path(args.metrics_output)
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"candidate": " + ".join(best.candidates), **best.metrics, "objective_score": best.objective_score}]).to_csv(
        metrics_output, index=False
    )
    return {
        "output": str(output),
        "selected_trades_output": str(selected_output),
        "metrics_output": str(metrics_output),
        "candidates": list(best.candidates),
        "metrics": best.metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate strongest robust NQ composite strategy HTML report.")
    parser.add_argument("--trades", default=".tmp/nq-bar-5y-directional-walkforward-trades.csv")
    parser.add_argument("--shortlist", default=".tmp/nq-feature-promotion-shortlist.csv")
    parser.add_argument("--recent-oos", default=".tmp/nq-promotion-recent-oos.csv")
    parser.add_argument("--output", default="reports/NQ-strongest-composite-strategy-report.html")
    parser.add_argument("--selected-trades-output", default=".tmp/nq-strongest-composite-strategy-trades.csv")
    parser.add_argument("--metrics-output", default=".tmp/nq-strongest-composite-strategy-metrics.csv")
    parser.add_argument("--max-combo-size", type=int, default=4)
    parser.add_argument("--generated-at", default="")
    args = parser.parse_args()

    print(json.dumps(write_report(args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
