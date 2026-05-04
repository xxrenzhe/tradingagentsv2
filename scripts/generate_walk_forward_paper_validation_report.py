from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for path in [ROOT_DIR, SCRIPTS_DIR]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from generate_mbp_history_report import _equity_curve_summary, _svg_line_chart
from tradingagents.config.env import load_project_env


def _fmt(value: object, decimals: int = 4) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{number:,.{decimals}f}"


def _percent(value: object) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return ""


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _walk_forward_cards(summary: pd.DataFrame, decisions: pd.DataFrame) -> str:
    if summary.empty:
        return '<p class="muted">尚未找到 walk-forward 汇总数据。</p>'
    raw_net = float(summary["raw_net_points"].sum())
    gate_net = float(summary["gate_net_points"].sum())
    raw_dd = float(summary["raw_max_drawdown_points"].max())
    gate_dd = float(summary["gate_max_drawdown_points"].max())
    allowed = int(decisions["allowed"].sum()) if not decisions.empty and "allowed" in decisions else 0
    blocked = int((~decisions["allowed"].astype(bool)).sum()) if not decisions.empty and "allowed" in decisions else 0
    fold_count = len(summary)
    decision_count = len(decisions)
    dd_delta = raw_dd - gate_dd
    net_delta = gate_net - raw_net
    return f"""
      <div class="metric-grid">
        <div class="metric"><strong>Walk-Forward Folds</strong><span>{fold_count}</span></div>
        <div class="metric"><strong>Test Decisions</strong><span>{decision_count:,}</span></div>
        <div class="metric"><strong>Allowed / Blocked</strong><span>{allowed:,} / {blocked:,}</span></div>
        <div class="metric"><strong>Raw Net Points</strong><span>{_fmt(raw_net)}</span></div>
        <div class="metric"><strong>Gate Net Points</strong><span>{_fmt(gate_net)}</span></div>
        <div class="metric"><strong>Net Delta</strong><span>{_fmt(net_delta)} points，gate 相对 raw 的收益变化；越大越好。</span></div>
        <div class="metric"><strong>Raw Max Fold DD</strong><span>{_fmt(raw_dd)}</span></div>
        <div class="metric"><strong>Gate Max Fold DD</strong><span>{_fmt(gate_dd)}</span></div>
        <div class="metric"><strong>DD Reduction</strong><span>{_fmt(dd_delta)} points，越大代表 gate 降低回撤越明显。</span></div>
      </div>
"""


def _paper_cards(summary: pd.DataFrame) -> str:
    if summary.empty:
        return '<p class="muted">尚未找到 paper validation 汇总数据。</p>'
    row = summary.iloc[0]
    submitted = int(row.get("ibkr_submitted", 0))
    ready = int(row.get("ibkr_ready", 0))
    blocked = int(row.get("ibkr_blocked", 0))
    outcomes = int(row.get("paper_outcomes_trades", 0))
    net_points = float(row.get("paper_outcomes_net_points", 0.0))
    readiness = str(row.get("ibkr_readiness_reasons", "") or "")
    gate_status = str(row.get("validation_gate_status", "") or "")
    status = "PASS: 已达到 paper 验证门槛" if gate_status == "pass" else "BLOCKED: 尚未达到 paper 验证门槛"
    return f"""
      <div class="metric-grid">
        <div class="metric"><strong>Paper Status</strong><span>{html.escape(status)}</span></div>
        <div class="metric"><strong>IBKR Preflights Ready</strong><span>{ready}</span></div>
        <div class="metric"><strong>IBKR Blocked</strong><span>{blocked}</span></div>
        <div class="metric"><strong>IBKR Submitted</strong><span>{submitted}</span></div>
        <div class="metric"><strong>Paper Outcomes</strong><span>{outcomes} trades</span></div>
        <div class="metric"><strong>Paper Net Points</strong><span>{_fmt(net_points)}</span></div>
        <div class="metric wide"><strong>Validation Gate</strong><span>{html.escape(status)}</span></div>
        <div class="metric wide"><strong>Readiness Blockers</strong><span>{html.escape(readiness or "None")}</span></div>
      </div>
"""


def _fold_table(summary: pd.DataFrame) -> str:
    if summary.empty:
        return '<p class="muted">无 fold 数据。</p>'
    columns = [
        "fold",
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "train_trades",
        "test_trades",
        "allowed",
        "blocked",
        "raw_net_points",
        "gate_net_points",
        "raw_max_drawdown_points",
        "gate_max_drawdown_points",
        "raw_profit_factor",
        "gate_profit_factor",
        "net_delta_points",
        "drawdown_delta_points",
    ]
    display = summary[[column for column in columns if column in summary.columns]].copy()
    for column in [
        "raw_net_points",
        "gate_net_points",
        "raw_max_drawdown_points",
        "gate_max_drawdown_points",
        "raw_profit_factor",
        "gate_profit_factor",
        "net_delta_points",
        "drawdown_delta_points",
    ]:
        if column in display:
            display[column] = display[column].map(_fmt)
    display.columns = [
        "Fold",
        "Train Start",
        "Train End",
        "Test Start",
        "Test End",
        "Train Trades",
        "Test Trades",
        "Allowed",
        "Blocked",
        "Raw Net",
        "Gate Net",
        "Raw DD",
        "Gate DD",
        "Raw PF",
        "Gate PF",
        "Net Delta",
        "DD Delta",
    ][: len(display.columns)]
    return display.to_html(index=False, classes="metrics compact", border=0, escape=True)


def _paper_table(summary: pd.DataFrame) -> str:
    if summary.empty:
        return '<p class="muted">无 paper 汇总数据。</p>'
    display = summary.copy()
    for column in display.columns:
        if column.endswith("_win_rate"):
            display[column] = display[column].map(_percent)
        elif pd.api.types.is_numeric_dtype(display[column]):
            display[column] = display[column].map(lambda value: _fmt(value) if not float(value).is_integer() else f"{int(value):,}")
    return display.to_html(index=False, classes="metrics compact", border=0, escape=True)


def _equity_points(decisions: pd.DataFrame, value_column: str) -> list[tuple[pd.Timestamp, float]]:
    if decisions.empty:
        return []
    sorted_decisions = decisions.sort_values("entry_ts").copy()
    timestamps = pd.to_datetime(sorted_decisions["entry_ts"], utc=True)
    values = pd.to_numeric(sorted_decisions[value_column], errors="coerce").fillna(0.0).cumsum().round(4)
    start_ts = timestamps.min()
    return [(start_ts, 0.0), *zip(timestamps, values)]


def _walk_forward_curves(decisions: pd.DataFrame) -> dict[str, list[tuple[pd.Timestamp, float]]]:
    if decisions.empty:
        return {}
    curves = {
        "Raw adaptive portfolio": _equity_points(decisions, "net_points"),
        "Agent gate scaled": _equity_points(decisions, "gate_net_points"),
    }
    return {name: series for name, series in curves.items() if series}


def _chart_script() -> str:
    return """
  <div class="chart-tooltip" id="chart-tooltip"></div>
  <script>
    const tooltip = document.getElementById("chart-tooltip");
    function moveTooltip(event) {
      const padding = 16;
      const rect = tooltip.getBoundingClientRect();
      let left = event.clientX + 14;
      let top = event.clientY + 14;
      if (left + rect.width + padding > window.innerWidth) left = event.clientX - rect.width - 14;
      if (top + rect.height + padding > window.innerHeight) top = event.clientY - rect.height - 14;
      tooltip.style.left = `${Math.max(padding, left)}px`;
      tooltip.style.top = `${Math.max(padding, top)}px`;
    }
    document.querySelectorAll(".chart-point").forEach((point) => {
      point.addEventListener("mouseenter", () => {
        if (point.classList.contains("is-hidden")) return;
        document.querySelectorAll(`.series-line[data-series="${CSS.escape(point.dataset.series)}"]`).forEach((element) => element.classList.add("highlighted"));
        point.classList.add("active-point");
        tooltip.textContent = [
          point.dataset.name || "",
          `Time: ${point.dataset.time || ""}`,
          `Trade: ${point.dataset.trade || ""}`,
          `Equity: ${point.dataset.equity || ""}`,
        ].join("\\n");
        tooltip.style.borderColor = point.dataset.color || "#576f8f";
        tooltip.style.display = "block";
      });
      point.addEventListener("mousemove", moveTooltip);
      point.addEventListener("mouseleave", () => {
        document.querySelectorAll(`.series-line[data-series="${CSS.escape(point.dataset.series)}"]`).forEach((element) => element.classList.remove("highlighted"));
        point.classList.remove("active-point");
        tooltip.style.display = "none";
      });
    });
    document.querySelectorAll(".legend-item").forEach((button) => {
      button.addEventListener("click", () => {
        const series = button.dataset.series;
        const nextHidden = button.getAttribute("aria-pressed") === "true";
        document.querySelectorAll(`.legend-item[data-series="${CSS.escape(series)}"]`).forEach((item) => {
          item.setAttribute("aria-pressed", String(!nextHidden));
          item.classList.toggle("is-muted", nextHidden);
        });
        document.querySelectorAll(`.series-line[data-series="${CSS.escape(series)}"], .chart-point[data-series="${CSS.escape(series)}"]`).forEach((element) => {
          element.classList.toggle("dimmed", nextHidden);
          element.classList.toggle("is-hidden", nextHidden);
          if (element.classList.contains("chart-point")) element.style.pointerEvents = nextHidden ? "none" : "all";
        });
        tooltip.style.display = "none";
      });
    });
  </script>
"""


def _verdict(summary: pd.DataFrame, paper_summary: pd.DataFrame) -> str:
    if summary.empty:
        return "walk-forward 数据缺失，不能判断。"
    raw_net = float(summary["raw_net_points"].sum())
    gate_net = float(summary["gate_net_points"].sum())
    raw_dd = float(summary["raw_max_drawdown_points"].max())
    gate_dd = float(summary["gate_max_drawdown_points"].max())
    gate_status = "" if paper_summary.empty else str(paper_summary.iloc[0].get("validation_gate_status", "") or "")
    gate_blockers = "" if paper_summary.empty else str(paper_summary.iloc[0].get("validation_gate_blockers", "") or "")
    if gate_status != "pass":
        paper_text = f"paper validation gate 仍为 BLOCKED，不能视为可实盘。阻塞项：{gate_blockers or 'unknown'}。"
    else:
        paper_text = "paper validation gate 已 PASS，可以进入更长周期 paper 观察，但仍不等同于实盘批准。"
    if gate_net < raw_net and gate_dd < raw_dd:
        wf_text = "walk-forward 显示 agent gate 降低了最大 fold 回撤，但牺牲了部分收益。"
    elif gate_net >= raw_net and gate_dd <= raw_dd:
        wf_text = "walk-forward 显示 agent gate 同时改善收益和回撤。"
    else:
        wf_text = "walk-forward 暂未证明 agent gate 的风险收益改进稳定。"
    return f"{wf_text}{paper_text}"


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Generate walk-forward and paper validation HTML report.")
    parser.add_argument("--walk-forward-summary", default=".tmp/mbp-agent-gate-walk-forward-summary.csv")
    parser.add_argument("--walk-forward-decisions", default=".tmp/mbp-agent-gate-walk-forward-decisions.csv")
    parser.add_argument("--paper-summary", default=".tmp/paper-validation-summary.csv")
    parser.add_argument("--output", default="reports/NQM6-mbp-walk-forward-paper-validation.html")
    args = parser.parse_args()

    walk_forward_summary = _read_csv(Path(args.walk_forward_summary))
    decisions = _read_csv(Path(args.walk_forward_decisions))
    paper_summary = _read_csv(Path(args.paper_summary))
    curves = _walk_forward_curves(decisions)
    chart_section = ""
    if curves:
        chart_section = f"""
      {_svg_line_chart(curves, "Walk-forward equity by trade sequence (net points)", "sequence")}
      {_svg_line_chart(curves, "Walk-forward equity by trading date (net points)", "date")}
      {_equity_curve_summary(curves)}
"""
    else:
        chart_section = '<p class="muted">无 walk-forward 决策数据，无法绘制资金曲线。</p>'

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NQM6 Walk-Forward and Paper Validation</title>
  <style>
    body {{ margin: 0; padding: 28px; background: #071018; color: #edf6fb; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 1240px; margin: 0 auto; }}
    .card {{ background: rgba(15, 25, 36, .94); border: 1px solid #263d50; border-radius: 18px; padding: 20px; margin-bottom: 18px; box-shadow: 0 16px 50px rgba(0,0,0,.28); overflow-x: auto; }}
    h1, h2 {{ margin: 0 0 12px; }}
    p {{ color: #b8cad6; line-height: 1.68; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #263d50; text-align: left; vertical-align: top; }}
    th {{ color: #d9edf8; text-transform: uppercase; letter-spacing: .04em; font-size: 12px; }}
    svg {{ width: 100%; height: auto; border-radius: 14px; overflow: hidden; }}
    .badge {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: rgba(14, 165, 233, .14); color: #7dd3fc; margin-bottom: 10px; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px; }}
    .metric {{ border: 1px solid #263d50; border-radius: 12px; padding: 12px; background: rgba(7, 16, 24, .48); }}
    .metric.wide {{ grid-column: 1 / -1; }}
    .metric strong {{ display: block; margin-bottom: 6px; color: #f6fbff; }}
    .metric span {{ color: #b8cad6; line-height: 1.55; white-space: pre-line; }}
    .muted {{ color: #8ea4b3; }}
    .compact {{ font-size: 12px; }}
    .callout {{ border-left: 4px solid #f97316; }}
    .chart-tooltip {{ position: fixed; z-index: 50; display: none; max-width: 360px; padding: 10px 12px; border: 1px solid #576f8f; border-radius: 10px; background: rgba(7, 16, 24, .96); color: #f6fbff; font-size: 12px; line-height: 1.5; white-space: pre-line; pointer-events: none; box-shadow: 0 14px 36px rgba(0,0,0,.35); }}
    .legend-bar {{ display: flex; flex-wrap: wrap; align-content: flex-start; align-items: center; gap: 8px; height: 106px; overflow-y: auto; padding: 2px 0 8px; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 6px; flex: 0 1 auto; max-width: 310px; border: 1px solid #344c62; border-radius: 999px; background: rgba(7, 16, 24, .72); color: #dcebf4; padding: 5px 9px; font: 11px/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; cursor: pointer; }}
    .legend-item span:last-child {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .legend-item.is-muted {{ opacity: .38; text-decoration: line-through; }}
    .legend-swatch {{ width: 10px; height: 10px; border-radius: 999px; box-shadow: 0 0 0 1px rgba(255,255,255,.18) inset; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <span class="badge">Walk-Forward + Paper Validation</span>
      <h1>NQM6 MBP 验证闭环报告</h1>
      <p>本报告不继续调参，而是检查策略在滚动训练/测试窗口和 IBKR paper 流程中的可验证性。walk-forward 使用历史训练窗口种子化 agent gate，再只在后续测试窗口评估决策。</p>
    </section>
    <section class="card callout">
      <h2>当前结论</h2>
      <p>{html.escape(_verdict(walk_forward_summary, paper_summary))}</p>
    </section>
    <section class="card">
      <h2>Walk-Forward 摘要</h2>
      {_walk_forward_cards(walk_forward_summary, decisions)}
    </section>
    <section class="card">
      <h2>Walk-Forward 资金曲线</h2>
      <p>第一张图横坐标为测试窗口内的交易次数，第二张图横坐标为实际交易日期。图例可点击隐藏/恢复曲线，鼠标悬浮只显示当前数据点。</p>
      {chart_section}
    </section>
    <section class="card">
      <h2>Walk-Forward Fold 明细</h2>
      {_fold_table(walk_forward_summary)}
    </section>
    <section class="card">
      <h2>Paper Validation 摘要</h2>
      {_paper_cards(paper_summary)}
    </section>
    <section class="card">
      <h2>Paper Audit 明细</h2>
      {_paper_table(paper_summary)}
    </section>
    <section class="card">
      <h2>判断标准</h2>
      <div class="metric-grid">
        <div class="metric"><strong>Net Points</strong><span>累计净点数，越大越好；但不能用牺牲过多回撤控制换取单一收益。</span></div>
        <div class="metric"><strong>Max Fold DD</strong><span>单个 walk-forward 测试 fold 内最大回撤，越小越好。</span></div>
        <div class="metric"><strong>PF</strong><span>Profit Factor，总盈利 / 总亏损绝对值，越大越好；若 gate 降低大盈利交易，PF 可能下降。</span></div>
        <div class="metric"><strong>DD Reduction</strong><span>raw 最大 fold 回撤减去 gate 最大 fold 回撤，越大越好。</span></div>
        <div class="metric"><strong>IBKR Submitted</strong><span>paper 订单真实提交数量；为 0 时还没有完成 paper trading 验证。</span></div>
        <div class="metric"><strong>Paper Outcomes</strong><span>已记录的 paper 成交/退出结果；至少需要连续多日样本才能讨论实盘。</span></div>
      </div>
    </section>
  </div>
  {_chart_script()}
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
