from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


PROMOTED_TIER = "promote_to_strict_gate"
RECENT_PASS = "passes_recent_oos"


def load_csv(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def load_debate(path: str | Path) -> dict[str, object]:
    debate_path = Path(path)
    if not debate_path.exists():
        return {"candidates": []}
    return json.loads(debate_path.read_text(encoding="utf-8"))


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


def format_cell(column: str, value: object) -> str:
    if pd.isna(value):
        return ""
    if column.endswith("_rate") or column in {"win_rate"}:
        return f"{as_float(value) * 100:.1f}%"
    if column == "net_points" or column == "stress_points" or column.endswith("_net_points") or column.endswith("_improvement"):
        return f"{as_float(value):,.1f}"
    if "profit_factor" in column:
        return f"{as_float(value):.2f}"
    if column.endswith("_score"):
        return f"{as_float(value):.2f}"
    if column in {"trades", "full_trades", "test_trades", "selected_folds", "months_with_trades"}:
        return f"{as_int(value):,}"
    return safe_text(value)


def top_rows(frame: pd.DataFrame, sort_columns: list[str], limit: int) -> pd.DataFrame:
    if frame.empty:
        return frame
    existing = [column for column in sort_columns if column in frame.columns]
    if existing:
        return frame.sort_values(existing, ascending=[False] * len(existing)).head(limit)
    return frame.head(limit)


def count_where(frame: pd.DataFrame, column: str, value: str) -> int:
    if frame.empty or column not in frame.columns:
        return 0
    return int(frame[column].astype(str).eq(value).sum())


def metric_cards(cards: Iterable[tuple[str, object, str]]) -> str:
    items = []
    for label, value, note in cards:
        items.append(
            f"""
            <div class="metric-card">
              <div class="metric-label">{safe_text(label)}</div>
              <div class="metric-value">{safe_text(value)}</div>
              <div class="metric-note">{safe_text(note)}</div>
            </div>
            """
        )
    return f"<div class=\"metric-grid\">{''.join(items)}</div>"


def render_table(frame: pd.DataFrame, columns: list[str], headers: dict[str, str], *, limit: int = 12) -> str:
    if frame.empty:
        return "<p class=\"empty\">无可用记录。</p>"
    display = frame[[column for column in columns if column in frame.columns]].head(limit)
    if display.empty:
        return "<p class=\"empty\">无匹配字段。</p>"
    head = "".join(f"<th>{safe_text(headers.get(column, column))}</th>" for column in display.columns)
    body_rows = []
    for _, row in display.iterrows():
        cells = "".join(f"<td>{format_cell(column, row[column])}</td>" for column in display.columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<div class=\"table-wrap\"><table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>"


def render_net_bars(frame: pd.DataFrame, *, value_column: str, label_column: str, limit: int = 8) -> str:
    if frame.empty or value_column not in frame.columns or label_column not in frame.columns:
        return "<p class=\"empty\">无可用柱状摘要。</p>"
    selected = frame.copy().head(limit)
    max_abs = max(abs(as_float(value)) for value in selected[value_column]) or 1.0
    rows = []
    for _, row in selected.iterrows():
        value = as_float(row[value_column])
        width = min(abs(value) / max_abs * 100, 100)
        css_class = "bar positive" if value >= 0 else "bar negative"
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{safe_text(row[label_column])}</div>
              <div class="bar-track"><div class="{css_class}" style="width:{width:.1f}%"></div></div>
              <div class="bar-value">{value:,.1f}</div>
            </div>
            """
        )
    return f"<div class=\"bar-list\">{''.join(rows)}</div>"


def render_debate(debate: dict[str, object], *, limit: int = 6) -> str:
    candidates = debate.get("candidates", [])
    if not isinstance(candidates, list) or not candidates:
        return "<p class=\"empty\">未找到 LLM debate JSON。</p>"
    sections = []
    for candidate in candidates[:limit]:
        if not isinstance(candidate, dict):
            continue
        bull = render_case_list(candidate.get("bull_case", []))
        bear = render_case_list(candidate.get("bear_case", []))
        sections.append(
            f"""
            <article class="debate-card">
              <div class="debate-head">
                <h3>{safe_text(candidate.get("name", ""))}</h3>
                <span>{safe_text(candidate.get("selection_tier", ""))}</span>
              </div>
              <p><strong>交易逻辑</strong>：{safe_text(candidate.get("signal_rule", ""))}</p>
              <p><strong>入场/出场</strong>：{safe_text(candidate.get("entry_point", ""))}；{safe_text(candidate.get("exit_rule", ""))}</p>
              <p><strong>交易时段</strong>：{safe_text(candidate.get("session_window_utc", ""))} UTC；方向：{safe_text(candidate.get("direction_filter", ""))}</p>
              <div class="debate-columns">
                <div><h4>多头观点</h4>{bull}</div>
                <div><h4>空头/风控观点</h4>{bear}</div>
              </div>
            </article>
            """
        )
    return "".join(sections)


def render_case_list(values: object) -> str:
    if not isinstance(values, list) or not values:
        return "<p class=\"empty\">无。</p>"
    items = "".join(f"<li>{safe_text(value)}</li>" for value in values)
    return f"<ul>{items}</ul>"


def tier_counts(shortlist: pd.DataFrame) -> str:
    if shortlist.empty or "tier" not in shortlist.columns:
        return "无 shortlist"
    counts = shortlist["tier"].astype(str).value_counts().to_dict()
    return ", ".join(f"{key}: {value}" for key, value in counts.items())


def build_report_html(
    *,
    directional: pd.DataFrame,
    shortlist: pd.DataFrame,
    state_filters: pd.DataFrame,
    past_fold: pd.DataFrame,
    recent_oos: pd.DataFrame,
    recent_monthly: pd.DataFrame,
    paper_plan: pd.DataFrame,
    debate: dict[str, object],
    generated_at: str,
    source_paths: dict[str, str],
) -> str:
    promoted = shortlist[shortlist.get("tier", pd.Series(dtype=str)).astype(str).eq(PROMOTED_TIER)] if not shortlist.empty else pd.DataFrame()
    recent_pass = recent_oos[recent_oos.get("recent_verdict", pd.Series(dtype=str)).astype(str).eq(RECENT_PASS)] if not recent_oos.empty else pd.DataFrame()
    directional_top = top_rows(directional, ["best_strategy_score", "full_net_points"], 10)
    state_top = top_rows(state_filters, ["positive_fold_rate", "profit_factor", "net_points"], 12)
    past_top = top_rows(past_fold, ["selected_folds", "test_net_points", "test_net_improvement"], 12)
    recent_top = top_rows(recent_oos, ["net_points", "profit_factor"], 12)

    cards = metric_cards(
        [
            ("5年候选数", f"{len(directional):,}", "方向性 walk-forward ranking"),
            ("严格门槛候选", f"{len(promoted):,}", tier_counts(shortlist)),
            ("最近12个月通过", f"{len(recent_pass):,}", "recent OOS verdict=passes"),
            ("LLM debate 候选", f"{len(debate.get('candidates', [])) if isinstance(debate.get('candidates', []), list) else 0:,}", "牛熊论证样本"),
        ]
    )

    source_list = "".join(f"<li><code>{safe_text(name)}</code>: {safe_text(path)}</li>" for name, path in source_paths.items())

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ 5年特征 + LLM辩论回测报告</title>
  <style>
    :root {{
      --ink: #17201b;
      --muted: #5f6f67;
      --paper: #fbf7ed;
      --panel: #fffdf7;
      --line: #ded5c4;
      --green: #247a55;
      --red: #b54b3a;
      --gold: #b9852b;
      --blue: #2f6388;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at 12% 8%, rgba(185, 133, 43, .18), transparent 28rem),
        linear-gradient(135deg, #f8efd9 0%, #fdfaf2 42%, #e8f0e6 100%);
      color: var(--ink);
      font: 15px/1.55 Georgia, "Noto Serif SC", "Songti SC", serif;
    }}
    header {{
      padding: 48px min(6vw, 72px) 28px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0 0 12px;
      max-width: 1100px;
      font-size: clamp(34px, 5vw, 68px);
      line-height: .98;
      letter-spacing: -.04em;
    }}
    .subtitle {{
      max-width: 960px;
      color: var(--muted);
      font-size: 18px;
    }}
    main {{ padding: 28px min(6vw, 72px) 64px; }}
    section {{
      margin: 28px 0;
      padding: 26px;
      background: rgba(255, 253, 247, .84);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: 0 18px 50px rgba(62, 52, 35, .08);
    }}
    h2 {{ margin: 0 0 14px; font-size: 26px; }}
    h3 {{ margin: 0; font-size: 18px; }}
    h4 {{ margin: 0 0 8px; color: var(--muted); }}
    code {{
      padding: 2px 5px;
      border-radius: 5px;
      background: #efe6d5;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 20px;
    }}
    .metric-card {{
      min-height: 124px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: linear-gradient(180deg, #fffdf8, #f6eddd);
    }}
    .metric-label {{ color: var(--muted); font-size: 13px; }}
    .metric-value {{ margin: 6px 0; font-size: 34px; font-weight: 700; }}
    .metric-note {{ color: var(--muted); font-size: 12px; }}
    .verdict {{
      display: grid;
      grid-template-columns: 1.2fr .8fr;
      gap: 20px;
    }}
    .callout {{
      padding: 18px;
      border-left: 5px solid var(--gold);
      background: #fff4d8;
      border-radius: 12px;
    }}
    .risk {{
      border-left-color: var(--red);
      background: #fff0ec;
    }}
    .table-wrap {{ overflow-x: auto; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      padding: 10px 9px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      background: #f5ead8;
      position: sticky;
      top: 0;
    }}
    .bar-list {{ display: grid; gap: 10px; }}
    .bar-row {{
      display: grid;
      grid-template-columns: minmax(220px, 1.2fr) 2fr 90px;
      align-items: center;
      gap: 12px;
    }}
    .bar-track {{
      height: 12px;
      overflow: hidden;
      border-radius: 999px;
      background: #eadfcf;
    }}
    .bar {{ height: 100%; border-radius: inherit; }}
    .positive {{ background: linear-gradient(90deg, var(--green), #6caf7a); }}
    .negative {{ background: linear-gradient(90deg, var(--red), #d78b76); }}
    .bar-label, .bar-value {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
    .debate-card {{
      margin-top: 16px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: #fffaf0;
    }}
    .debate-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: baseline;
      margin-bottom: 10px;
    }}
    .debate-head span {{
      padding: 4px 8px;
      border-radius: 999px;
      background: #e9f0e4;
      color: var(--green);
      white-space: nowrap;
      font-size: 12px;
    }}
    .debate-columns {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }}
    .empty {{ color: var(--muted); }}
    .sources {{ color: var(--muted); font-size: 13px; }}
    @media (max-width: 860px) {{
      .metric-grid, .verdict, .debate-columns {{ grid-template-columns: 1fr; }}
      .bar-row {{ grid-template-columns: 1fr; gap: 5px; }}
      section {{ padding: 18px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>NQ 5年特征、可盈利方向与 LLM 辩论回测报告</h1>
    <p class="subtitle">基于已完成的过去5年 NQ 1分钟特征挖掘、方向性 walk-forward、状态过滤、过去折选择验证、最近12个月 OOS 与 LLM 牛熊辩论证据生成。生成时间：{safe_text(generated_at)}。</p>
    {cards}
  </header>
  <main>
    <section>
      <h2>执行结论</h2>
      <div class="verdict">
        <div class="callout">
          <p><strong>当前可盈利方向优先级：</strong>优先保留无状态过滤的 <code>bar_best_mean_reversion_lb10_thr1_hold30_long_us_late</code> 与 <code>bar_best_momentum_lb60_thr0.0006_hold60_long_us_late</code>。它们在5年 walk-forward 中达到严格门槛，并在最近12个月 OOS 中继续为正。</p>
          <p><strong>状态过滤结论：</strong>部分过滤器能改善局部表现，但多数属于后验挖掘；只有经过过去折选择验证且重复出现的过滤器才应进入下一轮。</p>
        </div>
        <div class="callout risk">
          <p><strong>不能直接纸盘/实盘提交：</strong><code>run_ibkr_live_paper_trader.py</code> 当前不支持这些 <code>bar_best_*</code> NQ bar 策略 ID 的 live signal adapter。</p>
          <p><strong>下一步重点：</strong>停止扩大原始特征挖掘，优先补 live adapter、执行仿真、滑点/手续费、纸盘风控和最近 OOS 再验证。</p>
        </div>
      </div>
    </section>

    <section>
      <h2>净点数概览</h2>
      {render_net_bars(recent_top, value_column="net_points", label_column="candidate", limit=8)}
    </section>

    <section>
      <h2>严格门槛与候选分层</h2>
      {render_table(shortlist, ["tier", "candidate", "filter", "evidence_type", "trades", "net_points", "profit_factor", "positive_fold_rate", "stress_points", "selected_folds", "next_action"], {
          "tier": "层级",
          "candidate": "候选",
          "filter": "过滤",
          "evidence_type": "证据类型",
          "trades": "交易数",
          "net_points": "净点数",
          "profit_factor": "PF",
          "positive_fold_rate": "正折率",
          "stress_points": "压力净点数",
          "selected_folds": "选择折数",
          "next_action": "下一步",
      }, limit=14)}
    </section>

    <section>
      <h2>5年方向性回测 Top 候选</h2>
      {render_table(directional_top, ["candidate", "family", "direction_filter", "full_trades", "full_net_points", "full_profit_factor", "positive_fold_rate", "stress_net_points", "best_strategy_score", "selection_tier"], {
          "candidate": "候选",
          "family": "形态/家族",
          "direction_filter": "方向",
          "full_trades": "交易数",
          "full_net_points": "5年净点数",
          "full_profit_factor": "5年 PF",
          "positive_fold_rate": "正折率",
          "stress_net_points": "压力净点数",
          "best_strategy_score": "评分",
          "selection_tier": "层级",
      }, limit=10)}
    </section>

    <section>
      <h2>状态过滤挖掘</h2>
      <p>以下结果来自后验状态过滤挖掘，只能作为研究证据。可盈利但未通过过去折选择的过滤器，不应直接升级为实时交易规则。</p>
      {render_table(state_top, ["candidate", "filter", "trades", "net_points", "profit_factor", "positive_fold_rate", "min_fold_net_points", "baseline_net_points", "net_improvement", "retained_trade_rate"], {
          "candidate": "候选",
          "filter": "过滤",
          "trades": "交易数",
          "net_points": "净点数",
          "profit_factor": "PF",
          "positive_fold_rate": "正折率",
          "min_fold_net_points": "最差折",
          "baseline_net_points": "基线净点数",
          "net_improvement": "改善",
          "retained_trade_rate": "保留率",
      }, limit=12)}
    </section>

    <section>
      <h2>过去折选择验证</h2>
      <p>这部分只允许用历史折选择过滤器，再测试未来折，更接近真实上线流程。</p>
      {render_table(past_top, ["candidate", "filter", "selected_folds", "test_trades", "test_net_points", "fold_net_profit_factor", "positive_selected_fold_rate", "min_test_fold_net_points", "test_baseline_net_points", "test_net_improvement"], {
          "candidate": "候选",
          "filter": "过滤",
          "selected_folds": "未来折数",
          "test_trades": "测试交易",
          "test_net_points": "未来净点数",
          "fold_net_profit_factor": "折合 PF",
          "positive_selected_fold_rate": "正选择折率",
          "min_test_fold_net_points": "最差未来折",
          "test_baseline_net_points": "基线净点数",
          "test_net_improvement": "未来改善",
      }, limit=12)}
    </section>

    <section>
      <h2>最近12个月 OOS</h2>
      {render_table(recent_top, ["recent_verdict", "candidate", "filter", "trades", "net_points", "profit_factor", "win_rate", "positive_month_rate", "min_month_net_points", "months_with_trades", "next_action"], {
          "recent_verdict": "结论",
          "candidate": "候选",
          "filter": "过滤",
          "trades": "交易数",
          "net_points": "净点数",
          "profit_factor": "PF",
          "win_rate": "胜率",
          "positive_month_rate": "正月份率",
          "min_month_net_points": "最差月份",
          "months_with_trades": "有交易月份",
          "next_action": "下一步",
      }, limit=14)}
    </section>

    <section>
      <h2>最近月度分布</h2>
      {render_table(recent_monthly, ["candidate", "filter", "month", "trades", "net_points", "win_rate"], {
          "candidate": "候选",
          "filter": "过滤",
          "month": "月份",
          "trades": "交易数",
          "net_points": "净点数",
          "win_rate": "胜率",
      }, limit=24)}
    </section>

    <section>
      <h2>LLM 辩论证据</h2>
      <p>LLM debate 不替代回测结论，只用于把交易逻辑、牛方证据、熊方风险和决策提醒结构化，减少只看净利润的偏差。</p>
      {render_debate(debate, limit=6)}
    </section>

    <section>
      <h2>纸盘验证状态</h2>
      {render_table(paper_plan, ["priority", "strategy_id", "filter", "tier", "symbol", "quantity", "submit_mode", "recent_net_points", "recent_profit_factor", "implementation_status", "adapter_gap"], {
          "priority": "优先级",
          "strategy_id": "策略",
          "filter": "过滤",
          "tier": "层级",
          "symbol": "品种",
          "quantity": "数量",
          "submit_mode": "提交状态",
          "recent_net_points": "近期净点数",
          "recent_profit_factor": "近期 PF",
          "implementation_status": "实现状态",
          "adapter_gap": "缺口",
      }, limit=8)}
    </section>

    <section>
      <h2>建议</h2>
      <p>当前仍可继续优化，但不建议继续无约束挖掘更多原始特征。优先级应切换到：1）NQ bar 策略 live adapter；2）滑点、手续费、成交延迟和最大持仓约束；3）最近 OOS 滚动复验；4）只对过去折验证有正改善的状态过滤器做小范围参数邻域测试。</p>
      <ul class="sources">
        {source_list}
      </ul>
    </section>
  </main>
</body>
</html>
"""


def write_html_report(args: argparse.Namespace) -> str:
    source_paths = {
        "directional": args.directional_ranking,
        "shortlist": args.shortlist,
        "state_filters": args.state_filters,
        "past_fold": args.past_fold_validation,
        "recent_oos": args.recent_oos,
        "recent_monthly": args.recent_monthly,
        "paper_plan": args.paper_plan,
        "debate": args.debate,
    }
    html_text = build_report_html(
        directional=load_csv(args.directional_ranking),
        shortlist=load_csv(args.shortlist),
        state_filters=load_csv(args.state_filters),
        past_fold=load_csv(args.past_fold_validation),
        recent_oos=load_csv(args.recent_oos),
        recent_monthly=load_csv(args.recent_monthly),
        paper_plan=load_csv(args.paper_plan),
        debate=load_debate(args.debate),
        generated_at=args.generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        source_paths=source_paths,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_text, encoding="utf-8")
    return str(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate NQ 5-year feature, debate, and backtest HTML report.")
    parser.add_argument("--directional-ranking", default=".tmp/nq-bar-5y-directional-strategy-ranking.csv")
    parser.add_argument("--shortlist", default=".tmp/nq-feature-promotion-shortlist.csv")
    parser.add_argument("--state-filters", default=".tmp/nq-bar-5y-state-filtered-features.csv")
    parser.add_argument("--past-fold-validation", default=".tmp/nq-state-filter-past-fold-validation-aggregate.csv")
    parser.add_argument("--recent-oos", default=".tmp/nq-promotion-recent-oos.csv")
    parser.add_argument("--recent-monthly", default=".tmp/nq-promotion-recent-oos-monthly.csv")
    parser.add_argument("--paper-plan", default=".tmp/nq-paper-validation-plan.csv")
    parser.add_argument("--debate", default=".tmp/nq-bar-5y-directional-strategy-debate.json")
    parser.add_argument("--output", default="reports/NQ-5y-feature-debate-backtest-report.html")
    parser.add_argument("--generated-at", default="")
    args = parser.parse_args()

    output = write_html_report(args)
    print(json.dumps({"output": output}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
