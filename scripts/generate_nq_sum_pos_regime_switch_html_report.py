from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
POINT_VALUE = 20.0


def esc(value: object) -> str:
    return html.escape(str(value))


def fmt(value: object, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, (float, np.floating)):
        return f"{float(value):,.{digits}f}"
    return esc(value)


def fmt_pct(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{float(value):.1%}"


def load_csv(path: str | Path) -> pd.DataFrame:
    csv_path = ROOT_DIR / path if not Path(path).is_absolute() else Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)
    return pd.read_csv(csv_path)


def summarize_trades(trades: pd.DataFrame) -> dict[str, float | int]:
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    equity = net.cumsum()
    drawdown = equity.cummax() - equity if len(equity) else pd.Series(dtype=float)
    gross_profit = float(net[net > 0].sum())
    gross_loss = float(-net[net < 0].sum())
    return {
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "profit_factor": gross_profit / gross_loss if gross_loss else np.inf,
        "win_rate": float((net > 0).mean()) if len(net) else 0.0,
        "avg_points": float(net.mean()) if len(net) else 0.0,
        "max_drawdown_points": float(drawdown.max()) if len(drawdown) else 0.0,
        "worst_trade_points": float(net.min()) if len(net) else 0.0,
        "best_trade_points": float(net.max()) if len(net) else 0.0,
    }


def metric(label: str, value: str, detail: str = "") -> str:
    detail_html = f"<span>{esc(detail)}</span>" if detail else ""
    return f"<div class=\"metric\"><strong>{esc(label)}</strong><b>{esc(value)}</b>{detail_html}</div>"


def table(frame: pd.DataFrame, columns: list[tuple[str, str]], limit: int | None = None) -> str:
    if frame.empty:
        return "<p class=\"muted\">No rows.</p>"
    shown = frame.head(limit).copy() if limit else frame.copy()
    header = "".join(f"<th>{esc(label)}</th>" for _, label in columns)
    rows = []
    for _, row in shown.iterrows():
        cells = []
        for column, _ in columns:
            value = row.get(column, "")
            if isinstance(value, (float, np.floating)):
                if "rate" in column or column.endswith("_pf"):
                    cells.append(f"<td>{fmt(value, 3)}</td>")
                else:
                    cells.append(f"<td>{fmt(value)}</td>")
            else:
                cells.append(f"<td>{esc(value)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"


def equity_series(trades: pd.DataFrame) -> list[tuple[pd.Timestamp, float]]:
    ordered = trades.sort_values("entry_ts").copy()
    equity = pd.to_numeric(ordered["net_points"], errors="coerce").fillna(0.0).cumsum()
    timestamps = pd.to_datetime(ordered["entry_ts"], utc=True)
    if ordered.empty:
        return []
    return [(timestamps.iloc[0], 0.0), *zip(timestamps, equity)]


def drawdown_series(trades: pd.DataFrame) -> list[tuple[pd.Timestamp, float]]:
    ordered = trades.sort_values("entry_ts").copy()
    equity = pd.to_numeric(ordered["net_points"], errors="coerce").fillna(0.0).cumsum()
    drawdown = equity.cummax() - equity
    timestamps = pd.to_datetime(ordered["entry_ts"], utc=True)
    if ordered.empty:
        return []
    return [(timestamps.iloc[0], 0.0), *zip(timestamps, drawdown)]


def svg_line(series_map: dict[str, list[tuple[pd.Timestamp, float]]], title: str, y_label: str) -> str:
    series_map = {name: series for name, series in series_map.items() if series}
    if not series_map:
        return "<p class=\"muted\">No curve data.</p>"
    width, height = 1180, 520
    left, right, top, bottom = 78, 34, 44, 74
    plot_w = width - left - right
    plot_h = height - top - bottom
    values = [float(value) for series in series_map.values() for _, value in series]
    stamps = [ts for series in series_map.values() for ts, _ in series]
    min_v, max_v = min(values), max(values)
    if min_v == max_v:
        min_v -= 1
        max_v += 1
    pad = max((max_v - min_v) * 0.08, 25.0)
    min_v -= pad
    max_v += pad
    min_ns, max_ns = min(stamps).value, max(stamps).value

    def x_for(ts: pd.Timestamp) -> float:
        return left if min_ns == max_ns else left + (ts.value - min_ns) / (max_ns - min_ns) * plot_w

    def y_for(value: float) -> float:
        return top + (max_v - value) / (max_v - min_v) * plot_h

    y_grid = []
    for i in range(6):
        value = min_v + (max_v - min_v) * i / 5
        y = y_for(value)
        y_grid.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#d6dee8"/>'
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#607085">{value:,.0f}</text>'
        )
    x_grid = []
    for i in range(6):
        ratio = i / 5
        ts = pd.Timestamp(int(min_ns + (max_ns - min_ns) * ratio), tz="UTC")
        x = x_for(ts)
        x_grid.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_h}" stroke="#edf2f7"/>'
            f'<text x="{x:.1f}" y="{top + plot_h + 28}" text-anchor="middle" font-size="12" fill="#607085">{ts:%Y-%m}</text>'
        )
    zero_line = ""
    if min_v < 0 < max_v:
        y = y_for(0)
        zero_line = f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#64748b" stroke-width="1.4" stroke-dasharray="6 5"/>'
    palette = ["#0f766e", "#2563eb", "#ea580c", "#9333ea", "#16a34a"]
    lines = []
    legend = []
    points = []
    for idx, (name, series) in enumerate(series_map.items()):
        color = palette[idx % len(palette)]
        safe = esc(name)
        poly = " ".join(f"{x_for(ts):.1f},{y_for(float(value)):.1f}" for ts, value in series)
        lines.append(f'<polyline data-series="{safe}" fill="none" stroke="{color}" stroke-width="2.7" points="{poly}"/>')
        stride = max(1, len(series) // 450)
        for point_idx, (ts, value) in enumerate(series):
            if point_idx % stride and point_idx != len(series) - 1:
                continue
            points.append(
                f'<circle class="pt" cx="{x_for(ts):.1f}" cy="{y_for(float(value)):.1f}" r="5" fill="transparent" '
                f'data-name="{safe}" data-time="{ts:%Y-%m-%d %H:%M UTC}" data-value="{float(value):,.2f} pts" />'
            )
        legend.append(f'<span><i style="background:{color}"></i>{safe}</span>')
    return f"""
<div class="chart">
<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
  <rect width="{width}" height="{height}" fill="#fff"/>
  {''.join(x_grid)}
  {''.join(y_grid)}
  {zero_line}
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#94a3b8"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#94a3b8"/>
  <text x="{left}" y="27" font-size="17" font-weight="800" fill="#172033">{esc(title)}</text>
  <text x="22" y="{top + plot_h / 2:.1f}" text-anchor="middle" transform="rotate(-90 22 {top + plot_h / 2:.1f})" font-size="12" fill="#475569">{esc(y_label)}</text>
  {''.join(lines)}
  {''.join(points)}
</svg>
<div class="legend">{''.join(legend)}</div>
</div>
"""


def bar_chart(frame: pd.DataFrame, title: str, label_col: str, value_col: str) -> str:
    if frame.empty:
        return "<p class=\"muted\">No bar data.</p>"
    width, height = 1180, 420
    left, right, top, bottom = 72, 28, 44, 92
    plot_w = width - left - right
    plot_h = height - top - bottom
    values = pd.to_numeric(frame[value_col], errors="coerce").fillna(0.0).to_numpy()
    labels = frame[label_col].astype(str).tolist()
    min_v, max_v = min(0.0, float(values.min())), max(0.0, float(values.max()))
    if min_v == max_v:
        min_v -= 1
        max_v += 1
    pad = max((max_v - min_v) * 0.08, 25)
    min_v -= pad
    max_v += pad

    def y_for(value: float) -> float:
        return top + (max_v - value) / (max_v - min_v) * plot_h

    zero_y = y_for(0)
    bar_w = plot_w / max(len(values), 1) * 0.74
    bars = []
    x_labels = []
    for i, (label, value) in enumerate(zip(labels, values)):
        cx = left + (i + 0.5) / len(values) * plot_w
        y = y_for(max(value, 0))
        h = abs(y_for(value) - zero_y)
        color = "#0f766e" if value >= 0 else "#dc2626"
        bars.append(f'<rect x="{cx - bar_w / 2:.1f}" y="{min(y, zero_y):.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}" opacity=".88"/>')
        if i % max(1, len(values) // 12) == 0 or i == len(values) - 1:
            x_labels.append(f'<text x="{cx:.1f}" y="{top + plot_h + 30}" text-anchor="middle" font-size="11" fill="#607085">{esc(label)}</text>')
    return f"""
<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
  <rect width="{width}" height="{height}" fill="#fff"/>
  <text x="{left}" y="27" font-size="17" font-weight="800" fill="#172033">{esc(title)}</text>
  <line x1="{left}" y1="{zero_y:.1f}" x2="{left + plot_w}" y2="{zero_y:.1f}" stroke="#64748b" stroke-dasharray="6 5"/>
  {''.join(bars)}
  {''.join(x_labels)}
</svg>
"""


def monthly_breakdown(trades: pd.DataFrame) -> pd.DataFrame:
    frame = trades.copy()
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    frame["period"] = frame["entry_ts"].dt.strftime("%Y-%m")
    grouped = frame.groupby("period")["net_points"].agg(["count", "sum", "mean"]).reset_index()
    grouped.columns = ["period", "trades", "net_points", "avg_points"]
    return grouped


def attribution(trades: pd.DataFrame, column: str, limit: int = 12) -> pd.DataFrame:
    grouped = trades.groupby(column)["net_points"].agg(["count", "sum", "mean"]).reset_index()
    grouped.columns = [column, "trades", "net_points", "avg_points"]
    return grouped.sort_values("net_points", ascending=False).head(limit)


def load_variant(prefix: str, label: str) -> dict[str, object]:
    summary = load_csv(f"{prefix}-summary.csv").iloc[0].to_dict()
    folds = load_csv(f"{prefix}-folds.csv")
    trades = load_csv(f"{prefix}-trades.csv")
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    return {"label": label, "summary": summary, "folds": folds, "trades": trades}


def build_report(args: argparse.Namespace) -> str:
    variants = [
        load_variant(args.prefix_36x3, "36M train / 3M test (primary)"),
        load_variant(args.prefix_24x1, "24M train / 1M test"),
        load_variant(args.prefix_36x1, "36M train / 1M test"),
    ]
    primary = variants[0]
    primary_trades = primary["trades"]
    primary_summary = primary["summary"]
    folds = primary["folds"].copy()
    monthlies = monthly_breakdown(primary_trades)
    top_trades = primary_trades.sort_values("net_points", ascending=False).head(12)
    worst_trades = primary_trades.sort_values("net_points").head(12)
    variant_rows = []
    for variant in variants:
        row = {"validation": variant["label"], **variant["summary"]}
        variant_rows.append(row)
    variant_frame = pd.DataFrame(variant_rows)
    candidate_counts = folds["candidate"].value_counts().reset_index()
    candidate_counts.columns = ["candidate", "folds"]
    guard_counts = folds["baseline_guard_triggered"].value_counts().rename(index={True: "baseline_on", False: "filter_on"}).reset_index()
    guard_counts.columns = ["mode", "folds"]
    equity_curves = {variant["label"]: equity_series(variant["trades"]) for variant in variants}
    drawdown_curves = {variant["label"]: drawdown_series(variant["trades"]) for variant in variants}

    cards = [
        metric("当前最佳策略", "sum_pos_open2_fixed_meta_recent_regime_switch_pf120_rg6", "fixed meta + causal recent-regime switch"),
        metric("主验证净点数", fmt(primary_summary["net_points"]), "$" + fmt(float(primary_summary["net_points"]) * POINT_VALUE, 0) + " per NQ contract"),
        metric("主验证 PF", fmt(primary_summary["profit_factor"], 3), "36M train / 3M test"),
        metric("主验证最大回撤", fmt(primary_summary["max_drawdown_points"]), "points"),
        metric("主验证交易数", fmt(primary_summary["trades"], 0), f"win rate {fmt_pct(primary_summary['win_rate'])}"),
        metric("相对基准提升", "+" + fmt(primary_summary["test_delta_net_points"]), "vs approximate fixed_meta baseline test folds"),
    ]
    model = {
        "strategy": "sum_pos_open2_fixed_meta_recent_regime_switch_pf120_rg6",
        "primary_prefix": args.prefix_36x3,
        "validation_prefixes": [args.prefix_36x3, args.prefix_24x1, args.prefix_36x1],
        "rule": {
            "default": "training-selected causal feature filter",
            "baseline_guard": "use baseline_no_filter if prior 6-month baseline PF >= 1.20",
            "no_month_filter": True,
        },
    }
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ sum_pos_open2 Recent Regime Switch Report</title>
  <style>
    :root {{
      --bg:#f3efe6; --panel:#fffaf0; --ink:#172033; --muted:#667085; --line:#dfd4bf;
      --green:#0f766e; --red:#b42318; --gold:#b7791f; --blue:#1d4ed8;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:
      radial-gradient(circle at top left, rgba(15,118,110,.16), transparent 34rem),
      linear-gradient(135deg, #f8f2e7 0%, #edf3f1 45%, #f7ead2 100%);
      font-family: ui-serif, Georgia, "Times New Roman", serif; }}
    .wrap {{ width:min(1320px, calc(100% - 36px)); margin:0 auto; padding:28px 0 52px; }}
    header, section {{ background:rgba(255,250,240,.92); border:1px solid var(--line); border-radius:22px; padding:24px; margin-bottom:18px; box-shadow:0 18px 40px rgba(57,44,21,.10); }}
    h1 {{ margin:8px 0 10px; font-size:38px; line-height:1.1; letter-spacing:-.025em; }}
    h2 {{ margin:0 0 14px; font-size:24px; }}
    h3 {{ margin:18px 0 8px; font-size:17px; }}
    p {{ color:var(--muted); line-height:1.68; margin:8px 0; }}
    code {{ background:#efe4cf; border:1px solid #decaa5; border-radius:7px; padding:2px 6px; }}
    .badge {{ display:inline-flex; gap:8px; align-items:center; padding:7px 11px; border-radius:999px; background:#e6f4f1; color:var(--green); font:700 13px/1.2 ui-sans-serif, system-ui; }}
    .metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:12px; margin-top:18px; }}
    .metric {{ background:#fffdf7; border:1px solid var(--line); border-radius:18px; padding:14px; min-height:116px; }}
    .metric strong {{ display:block; font:800 12px/1.2 ui-sans-serif, system-ui; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; }}
    .metric b {{ display:block; margin-top:9px; font:800 21px/1.2 ui-sans-serif, system-ui; overflow-wrap:anywhere; }}
    .metric span {{ display:block; margin-top:8px; color:var(--muted); font:13px/1.45 ui-sans-serif, system-ui; }}
    .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
    .table-wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:16px; }}
    table {{ width:100%; border-collapse:collapse; font:13px/1.35 ui-sans-serif, system-ui; background:#fffdf7; }}
    th,td {{ padding:9px 10px; border-bottom:1px solid #eadfc9; white-space:nowrap; text-align:left; }}
    th {{ background:#efe4cf; color:#344054; font-size:11px; text-transform:uppercase; letter-spacing:.04em; }}
    tr:last-child td {{ border-bottom:0; }}
    svg {{ width:100%; height:auto; border:1px solid var(--line); border-radius:16px; background:#fff; }}
    .legend {{ display:flex; flex-wrap:wrap; gap:10px; margin:8px 0 0; font:12px/1.2 ui-sans-serif, system-ui; color:#344054; }}
    .legend span {{ display:inline-flex; align-items:center; gap:6px; padding:5px 8px; border:1px solid var(--line); border-radius:999px; background:#fffdf7; }}
    .legend i {{ width:10px; height:10px; border-radius:99px; display:inline-block; }}
    .rule {{ border-left:5px solid var(--green); }}
    .warn {{ border-left:5px solid var(--gold); }}
    .muted {{ color:var(--muted); }}
    .pt {{ pointer-events:all; }}
    @media (max-width:900px) {{ .grid {{ grid-template-columns:1fr; }} h1 {{ font-size:30px; }} .wrap {{ width:calc(100% - 22px); }} }}
  </style>
</head>
<body>
<div class="wrap">
  <header>
    <span class="badge">NQ · Pine combo · fixed meta · causal regime switch</span>
    <h1>当前最佳交易策略总结报告</h1>
    <p>本报告总结当前最佳研究分支 <code>sum_pos_open2_fixed_meta_recent_regime_switch_pf120_rg6</code>。它不是按月份过滤，而是基于过去 6 个月 baseline PF 判断是否恢复高收益 runner 暴露。</p>
    <div class="metrics">{''.join(cards)}</div>
  </header>

  <section class="rule">
    <h2>策略规则</h2>
    <p><strong>基础策略：</strong><code>sum_pos_open2_runner_meta_allocation_best</code> 的 approximate fixed-meta replay。默认使用训练窗口选出的因果入场过滤器，主要是 <code>directional_range_pos_60</code> 的有利位置，以及 <code>pullback_or_strong_continuation</code> 这类动量/EMA 斜率确认。</p>
    <p><strong>Regime switch：</strong>每个测试窗口前，只看过去 6 个月 baseline 表现。如果过去 6 个月 baseline PF <code>&gt;= 1.20</code>，下一窗口启用 <code>baseline_no_filter</code>，避免强趋势阶段被低位入场过滤器砍掉大行情。</p>
    <p><strong>核心思想：</strong>弱/震荡环境等更好盈亏比位置；强趋势已被过去数据确认时，恢复 runner 暴露，优先吃大波段。</p>
  </section>

  <section>
    <h2>多窗口验证汇总</h2>
    {table(variant_frame, [("validation","验证"),("folds","Folds"),("positive_folds","正收益Folds"),("trades","交易数"),("net_points","净点数"),("profit_factor","PF"),("win_rate","胜率"),("max_drawdown_points","最大回撤"),("base_test_net_points","基准净点"),("test_delta_net_points","提升")])}
  </section>

  <section>
    <h2>资金曲线与回撤</h2>
    {svg_line(equity_curves, "Equity curve across validation variants", "Cumulative net points")}
    {svg_line(drawdown_curves, "Drawdown curve across validation variants", "Drawdown points")}
  </section>

  <section>
    <h2>主验证 Fold 明细</h2>
    {table(folds, [("test_start","测试开始"),("test_end","测试结束"),("candidate","选中规则"),("guard_profit_factor","6M Guard PF"),("baseline_guard_triggered","Baseline开关"),("base_test_net_points","基准净点"),("test_net_points","策略净点"),("test_delta_net_points","提升"),("test_profit_factor","PF"),("test_trades","交易数")])}
  </section>

  <section>
    <h2>月度表现</h2>
    {bar_chart(monthlies, "Primary 36x3 monthly net points", "period", "net_points")}
    {table(monthlies, [("period","月份"),("trades","交易数"),("net_points","净点数"),("avg_points","平均点")])}
  </section>

  <section class="grid">
    <div>
      <h2>信号族贡献 Top</h2>
      {table(attribution(primary_trades, "signal_family"), [("signal_family","Signal family"),("trades","交易数"),("net_points","净点数"),("avg_points","平均点")])}
    </div>
    <div>
      <h2>Session 贡献</h2>
      {table(attribution(primary_trades, "session"), [("session","Session"),("trades","交易数"),("net_points","净点数"),("avg_points","平均点")])}
    </div>
  </section>

  <section class="grid">
    <div>
      <h2>选中规则分布</h2>
      {table(candidate_counts, [("candidate","规则"),("folds","Folds")])}
    </div>
    <div>
      <h2>Regime 开关分布</h2>
      {table(guard_counts, [("mode","模式"),("folds","Folds")])}
    </div>
  </section>

  <section class="grid">
    <div>
      <h2>最佳交易样本</h2>
      {table(top_trades, [("trade_id","Trade ID"),("entry_ts","入场"),("exit_ts","出场"),("signal_family","信号"),("session","Session"),("direction","方向"),("entry_price","入场价"),("exit_price","出场价"),("net_points","净点")], limit=12)}
    </div>
    <div>
      <h2>最差交易样本</h2>
      {table(worst_trades, [("trade_id","Trade ID"),("entry_ts","入场"),("exit_ts","出场"),("signal_family","信号"),("session","Session"),("direction","方向"),("entry_price","入场价"),("exit_price","出场价"),("net_points","净点")], limit=12)}
    </div>
  </section>

  <section class="warn">
    <h2>限制与下一步</h2>
    <p>当前报告仍基于 approximate fixed-meta replay。它证明了 recent-regime switch 的方向有效，但还不是生产批准。下一步需要把同样的因果 switch 移植回原始精确 <code>sum_pos_open2</code> 构建器，并生成逐笔 K 线回放版报告。</p>
    <p>输入文件：<code>{esc(args.prefix_36x3)}</code>、<code>{esc(args.prefix_24x1)}</code>、<code>{esc(args.prefix_36x1)}</code>。</p>
    <script type="application/json" id="report-model">{esc(json.dumps(model, ensure_ascii=False, indent=2))}</script>
  </section>
</div>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HTML report for best NQ sum_pos fixed-meta recent-regime switch.")
    parser.add_argument("--prefix-36x3", default="reports/NQ-pine-sum_pos-open2-fixed-meta-regime-switch-wf-36x3-pf120-rg6")
    parser.add_argument("--prefix-24x1", default="reports/NQ-pine-sum_pos-open2-fixed-meta-regime-switch-wf-24x1-pf120-rg6")
    parser.add_argument("--prefix-36x1", default="reports/NQ-pine-sum_pos-open2-fixed-meta-regime-switch-wf-36x1-pf120-rg6")
    parser.add_argument("--output", default="reports/NQ-pine-sum_pos-open2-fixed-meta-regime-switch-best-report.html")
    args = parser.parse_args()
    doc = build_report(args)
    output = ROOT_DIR / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(doc, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
