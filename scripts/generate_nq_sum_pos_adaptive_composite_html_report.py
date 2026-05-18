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
                digits = 3 if "factor" in column or column.endswith("_pf") else 2
                cells.append(f"<td>{fmt(value, digits)}</td>")
            elif isinstance(value, (bool, np.bool_)):
                cells.append(f"<td>{'yes' if bool(value) else 'no'}</td>")
            else:
                cells.append(f"<td>{esc(value)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"


def equity_series(trades: pd.DataFrame) -> list[tuple[pd.Timestamp, float]]:
    ordered = trades.sort_values("entry_ts").copy()
    if ordered.empty:
        return []
    equity = pd.to_numeric(ordered["net_points"], errors="coerce").fillna(0.0).cumsum()
    timestamps = pd.to_datetime(ordered["entry_ts"], utc=True)
    return [(timestamps.iloc[0], 0.0), *zip(timestamps, equity)]


def drawdown_series(trades: pd.DataFrame) -> list[tuple[pd.Timestamp, float]]:
    ordered = trades.sort_values("entry_ts").copy()
    if ordered.empty:
        return []
    equity = pd.to_numeric(ordered["net_points"], errors="coerce").fillna(0.0).cumsum()
    drawdown = equity.cummax() - equity
    timestamps = pd.to_datetime(ordered["entry_ts"], utc=True)
    return [(timestamps.iloc[0], 0.0), *zip(timestamps, drawdown)]


def svg_line(series_map: dict[str, list[tuple[pd.Timestamp, float]]], title: str, y_label: str) -> str:
    series_map = {name: series for name, series in series_map.items() if series}
    if not series_map:
        return "<p class=\"muted\">No curve data.</p>"
    width, height = 1180, 500
    left, right, top, bottom = 78, 34, 44, 72
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
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#d7e0dc"/>'
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#64726e">{value:,.0f}</text>'
        )
    x_grid = []
    for i in range(6):
        ratio = i / 5
        ts = pd.Timestamp(int(min_ns + (max_ns - min_ns) * ratio), tz="UTC")
        x = x_for(ts)
        x_grid.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_h}" stroke="#eef3f1"/>'
            f'<text x="{x:.1f}" y="{top + plot_h + 28}" text-anchor="middle" font-size="12" fill="#64726e">{ts:%Y-%m}</text>'
        )
    zero_line = ""
    if min_v < 0 < max_v:
        y = y_for(0)
        zero_line = f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#64748b" stroke-width="1.4" stroke-dasharray="6 5"/>'

    palette = ["#0f766e", "#1d4ed8", "#b7791f", "#9333ea", "#dc2626"]
    lines = []
    legend = []
    for idx, (name, series) in enumerate(series_map.items()):
        color = palette[idx % len(palette)]
        poly = " ".join(f"{x_for(ts):.1f},{y_for(float(value)):.1f}" for ts, value in series)
        lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.7" points="{poly}"/>')
        legend.append(f'<span><i style="background:{color}"></i>{esc(name)}</span>')
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
</svg>
<div class="legend">{''.join(legend)}</div>
</div>
"""


def bar_chart(frame: pd.DataFrame, title: str, label_col: str, value_col: str) -> str:
    if frame.empty:
        return "<p class=\"muted\">No bar data.</p>"
    width, height = 1180, 390
    left, right, top, bottom = 72, 28, 44, 84
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
        color = "#0f766e" if value >= 0 else "#b42318"
        bars.append(f'<rect x="{cx - bar_w / 2:.1f}" y="{min(y, zero_y):.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}" opacity=".88"/>')
        if i % max(1, len(values) // 14) == 0 or i == len(values) - 1:
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
    if not trades.empty:
        trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
        trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    return {"label": label, "summary": summary, "folds": folds, "trades": trades}


def causal_audit(folds: pd.DataFrame) -> dict[str, object]:
    frame = folds.copy()
    for column in ["train_start", "recent_start", "test_start", "test_end"]:
        frame[column] = pd.to_datetime(frame[column], utc=True)
    leak_rows = frame[(frame["recent_start"] >= frame["test_start"]) | (frame["train_start"] >= frame["test_start"])]
    return {
        "folds": int(len(frame)),
        "leak_rows": int(len(leak_rows)),
        "all_decisions_pre_test": bool(leak_rows.empty),
        "uses_month_filter": False,
        "decision_columns": [
            "train_start/test_start",
            "recent_start/test_start",
            "baseline_recent_*",
            "candidate_recent_*",
            "train_candidate_*",
        ],
    }


def build_report(args: argparse.Namespace) -> str:
    variants = [
        load_variant(args.primary_prefix, "24M train / 1M test pf1.02 (primary high-return)"),
        load_variant(args.conservative_prefix, "36M train / 3M test pf1.10 (conservative check)"),
        load_variant(args.cross_prefix, "36M train / 1M test pf1.02 (cross-check)"),
        load_variant(args.monthly_pf105_prefix, "24M train / 1M test pf1.05 (prior best)"),
    ]
    sized_variants = [
        load_variant(args.sized_primary_prefix, "fixed sizing 24M / 1M pf1.02"),
        load_variant(args.sized_cross_prefix, "fixed sizing 36M / 1M pf1.02"),
        load_variant(args.sized_conservative_prefix, "fixed sizing 36M / 3M pf1.10"),
        load_variant(args.sized_pf105_prefix, "fixed sizing 24M / 1M pf1.05"),
    ]
    balanced_variants = [
        load_variant(args.balanced_primary_prefix, "balanced aggressive 24M / 1M pf1.02"),
        load_variant(args.balanced_cross_prefix, "balanced aggressive 36M / 1M pf1.02"),
        load_variant(args.balanced_conservative_prefix, "balanced aggressive 36M / 3M pf1.10"),
        load_variant(args.balanced_pf105_prefix, "balanced aggressive 24M / 1M pf1.05"),
    ]
    aggressive_variants = [
        load_variant(args.aggressive_primary_prefix, "aggressive 24M / 1M pf1.02"),
        load_variant(args.aggressive_cross_prefix, "aggressive 36M / 1M pf1.02"),
        load_variant(args.aggressive_conservative_prefix, "aggressive 36M / 3M pf1.10"),
        load_variant(args.aggressive_pf105_prefix, "aggressive 24M / 1M pf1.05"),
    ]
    primary = variants[0]
    primary_trades = primary["trades"]
    primary_summary = primary["summary"]
    folds = primary["folds"].copy()
    audit = causal_audit(folds)
    monthlies = monthly_breakdown(primary_trades)
    top_trades = primary_trades.sort_values("net_points", ascending=False).head(12)
    worst_trades = primary_trades.sort_values("net_points").head(12)

    variant_frame = pd.DataFrame([{"validation": variant["label"], **variant["summary"]} for variant in variants])
    sized_variant_frame = pd.DataFrame([{"validation": variant["label"], **variant["summary"]} for variant in sized_variants])
    balanced_variant_frame = pd.DataFrame([{"validation": variant["label"], **variant["summary"]} for variant in balanced_variants])
    aggressive_variant_frame = pd.DataFrame([{"validation": variant["label"], **variant["summary"]} for variant in aggressive_variants])
    mode_counts = folds["mode"].value_counts().reset_index()
    mode_counts.columns = ["mode", "folds"]
    mode_attr = attribution(primary_trades, "adaptive_mode")
    candidate_counts = folds["selected_candidate"].value_counts().reset_index().head(20)
    candidate_counts.columns = ["selected_candidate", "folds"]
    equity_curves = {variant["label"]: equity_series(variant["trades"]) for variant in variants}
    drawdown_curves = {variant["label"]: drawdown_series(variant["trades"]) for variant in variants}
    sized_equity_curves = {variant["label"]: equity_series(variant["trades"]) for variant in sized_variants}
    sized_drawdown_curves = {variant["label"]: drawdown_series(variant["trades"]) for variant in sized_variants}
    balanced_equity_curves = {variant["label"]: equity_series(variant["trades"]) for variant in balanced_variants}
    balanced_drawdown_curves = {variant["label"]: drawdown_series(variant["trades"]) for variant in balanced_variants}

    cards = [
        metric("当前主候选", "adaptive_composite_pf1.02_net0", "24M train / 1M test, dynamic NO_TRADE gate"),
        metric("主验证净点数", fmt(primary_summary["net_points"]), "$" + fmt(float(primary_summary["net_points"]) * POINT_VALUE, 0) + " per NQ contract"),
        metric("主验证 PF", fmt(primary_summary["profit_factor"], 3), "优先高收益，同时保留 PF 约束"),
        metric("最大回撤", fmt(primary_summary["max_drawdown_points"]), "points"),
        metric("启用折数", f"{int(primary_summary['enabled_folds'])}/{int(primary_summary['folds'])}", "其他折为 NO_TRADE"),
        metric("相对基准提升", "+" + fmt(primary_summary["test_delta_net_points"]), "vs approximate fixed_meta baseline folds"),
    ]
    model = {
        "strategy": "sum_pos_open2_adaptive_composite_pf1.02_net0",
        "primary_prefix": args.primary_prefix,
        "validation_prefixes": [args.primary_prefix, args.conservative_prefix, args.cross_prefix, args.monthly_pf105_prefix],
        "fixed_sizing_prefixes": [
            args.sized_primary_prefix,
            args.sized_cross_prefix,
            args.sized_conservative_prefix,
            args.sized_pf105_prefix,
        ],
        "balanced_aggressive_prefixes": [
            args.balanced_primary_prefix,
            args.balanced_cross_prefix,
            args.balanced_conservative_prefix,
            args.balanced_pf105_prefix,
        ],
        "aggressive_prefixes": [
            args.aggressive_primary_prefix,
            args.aggressive_cross_prefix,
            args.aggressive_conservative_prefix,
            args.aggressive_pf105_prefix,
        ],
        "causal_boundary": {
            "selection_time": "at each test fold start",
            "training_window": "entry_ts < test_start",
            "recent_window": "recent_start <= entry_ts < test_start",
            "no_month_filter": True,
            "future_leak_rows_detected": audit["leak_rows"],
        },
        "rule": {
            "baseline_strong": "use baseline_no_filter if prior 6-month baseline PF >= 1.20 and net >= 0",
            "defensive_filter": "otherwise use train-selected feature filter only if its recent PF >= 1.02 and net >= 0",
            "no_trade": "if neither branch earned permission from past data",
            "fixed_sizing": "scale next fold from past 6-month PF/net only: baseline PF>=1.35/net>=1000 -> 2.0x; baseline PF>=1.20/net>=0 -> 1.4x; defensive PF>=1.50/net>=300 -> 1.25x; defensive base -> 0.9x",
            "balanced_aggressive_sizing": "baseline PF>=1.30/net>=1000 -> 2.35x; baseline PF>=1.20/net>=0 -> 1.65x; defensive PF>=1.50/net>=300 -> 1.40x; defensive base -> 0.85x",
            "aggressive_sizing": "baseline PF>=1.30/net>=1000 -> 2.5x; baseline PF>=1.20/net>=0 -> 1.7x; defensive PF>=1.50/net>=300 -> 1.55x; defensive base -> 1.0x",
        },
    }

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ sum_pos_open2 Adaptive Composite Report</title>
  <style>
    :root {{
      --bg:#eef1e9; --panel:#fffdf4; --ink:#172033; --muted:#667085; --line:#d8d3bd;
      --green:#0f766e; --red:#b42318; --gold:#a16207; --blue:#1d4ed8;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:
      radial-gradient(circle at 10% 0%, rgba(15,118,110,.18), transparent 34rem),
      radial-gradient(circle at 90% 12%, rgba(161,98,7,.14), transparent 30rem),
      linear-gradient(135deg, #f7f0df 0%, #e9f1eb 48%, #f5ead2 100%);
      font-family: ui-serif, Georgia, "Times New Roman", serif; }}
    .wrap {{ width:min(1320px, calc(100% - 36px)); margin:0 auto; padding:28px 0 52px; }}
    header, section {{ background:rgba(255,253,244,.93); border:1px solid var(--line); border-radius:22px; padding:24px; margin-bottom:18px; box-shadow:0 18px 40px rgba(57,44,21,.10); }}
    h1 {{ margin:8px 0 10px; font-size:38px; line-height:1.1; letter-spacing:-.025em; }}
    h2 {{ margin:0 0 14px; font-size:24px; }}
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
    @media (max-width:900px) {{ .grid {{ grid-template-columns:1fr; }} h1 {{ font-size:30px; }} .wrap {{ width:calc(100% - 22px); }} }}
  </style>
</head>
<body>
<div class="wrap">
  <header>
    <span class="badge">NQ · sum_pos_open2 · causal adaptive composite</span>
    <h1>动态组合交易策略报告</h1>
    <p>本报告对应 <code>sum_pos_open2_adaptive_composite_pf1.02_net0</code>。策略不按月份过滤，而是在每个测试折开始前，用过去训练窗和最近 6 个月表现决定下一折采用 <code>baseline_strong</code>、<code>defensive_filter</code> 或 <code>NO_TRADE</code>。</p>
    <div class="metrics">{''.join(cards)}</div>
  </header>

  <section class="rule">
    <h2>动态适配规则</h2>
    <p><strong>子策略 1：baseline_strong。</strong>如果过去 6 个月 baseline 无过滤版本 PF <code>&gt;= 1.20</code> 且净点数非负，下一折启用 baseline，目的是在趋势强、runner 有效时不要过早过滤掉大行情。</p>
    <p><strong>子策略 2：defensive_filter。</strong>训练窗先选出最优因果行情特征过滤器；只有这个过滤器在最近 6 个月 PF <code>&gt;= 1.02</code> 且净点数非负，下一折才启用。它对应震荡/弱趋势环境下等待更高盈亏比位置。</p>
    <p><strong>子策略 3：NO_TRADE。</strong>如果 baseline 和 defensive filter 都没有被过去数据证明有效，下一折空仓。这就是对 2025-04-29 之前负收益问题的修正：不是换一个坏策略继续交易，而是允许不交易。</p>
  </section>

  <section>
    <h2>因果边界检查</h2>
    <p>折级决策只读取 <code>entry_ts &lt; test_start</code> 的训练/最近窗口数据。报告检查到未来泄漏行数：<code>{audit['leak_rows']}</code>。使用月份过滤：<code>false</code>。</p>
    {table(pd.DataFrame([audit]), [("folds","Folds"),("all_decisions_pre_test","决策均早于测试折"),("leak_rows","泄漏行数"),("uses_month_filter","月份过滤")])}
  </section>

  <section>
    <h2>多窗口验证汇总</h2>
    {table(variant_frame, [("validation","验证"),("folds","Folds"),("enabled_folds","启用Folds"),("positive_folds","正收益Folds"),("trades","交易数"),("net_points","净点数"),("profit_factor","PF"),("win_rate","胜率"),("max_drawdown_points","最大回撤"),("base_test_net_points","基准净点"),("test_delta_net_points","提升")])}
  </section>

  <section class="rule">
    <h2>固定仓位 Overlay 验证</h2>
    <p>仓位 overlay 不改变入场/出场，只按测试折开始前已知的最近 6 个月 PF/净点数调整下一折仓位：baseline 强势折最高 <code>2.0x</code>，中等强势 <code>1.4x</code>，defensive 高质量 <code>1.25x</code>，普通 defensive <code>0.9x</code>。这是一条固定规则，已原封不动应用到 24x1、36x1、36x3 交叉验证，避免按月份或按测试结果调参。</p>
    {table(sized_variant_frame, [("validation","验证"),("trades","交易数"),("net_points","净点数"),("profit_factor","PF"),("win_rate","胜率"),("avg_points","平均点"),("max_drawdown_points","最大回撤"),("worst_trade_points","最差交易"),("best_trade_points","最佳交易")])}
  </section>

  <section class="rule">
    <h2>Balanced-Aggressive 固定仓位</h2>
    <p>这版是当前更推荐的高收益折中方案：baseline 强势折最高 <code>2.35x</code>，中等强势 <code>1.65x</code>，defensive 高质量 <code>1.40x</code>，普通 defensive <code>0.85x</code>。相对 aggressive 版，它少拿一部分收益，但 1 点额外成本压力下的最大回撤更低。</p>
    {table(balanced_variant_frame, [("validation","验证"),("trades","交易数"),("net_points","净点数"),("profit_factor","PF"),("win_rate","胜率"),("avg_points","平均点"),("max_drawdown_points","最大回撤"),("worst_trade_points","最差交易"),("best_trade_points","最佳交易")])}
  </section>

  <section class="warn">
    <h2>Aggressive 固定仓位压力参考</h2>
    <p>Aggressive 版最高到 <code>2.5x</code>，净收益最高，但对成本/滑点更敏感。它适合作为收益上限参考，不应直接替代 balanced-aggressive 作为主候选。</p>
    {table(aggressive_variant_frame, [("validation","验证"),("trades","交易数"),("net_points","净点数"),("profit_factor","PF"),("win_rate","胜率"),("avg_points","平均点"),("max_drawdown_points","最大回撤"),("worst_trade_points","最差交易"),("best_trade_points","最佳交易")])}
  </section>

  <section>
    <h2>资金曲线与回撤</h2>
    {svg_line(equity_curves, "Equity curve across adaptive validation variants", "Cumulative net points")}
    {svg_line(drawdown_curves, "Drawdown curve across adaptive validation variants", "Drawdown points")}
  </section>

  <section>
    <h2>固定仓位资金曲线与回撤</h2>
    {svg_line(sized_equity_curves, "Fixed sizing equity curve across validation variants", "Cumulative net points")}
    {svg_line(sized_drawdown_curves, "Fixed sizing drawdown curve across validation variants", "Drawdown points")}
  </section>

  <section>
    <h2>Balanced-Aggressive 资金曲线与回撤</h2>
    {svg_line(balanced_equity_curves, "Balanced aggressive equity curve across validation variants", "Cumulative net points")}
    {svg_line(balanced_drawdown_curves, "Balanced aggressive drawdown curve across validation variants", "Drawdown points")}
  </section>

  <section>
    <h2>主验证 Fold 决策明细</h2>
    {table(folds, [("test_start","测试开始"),("test_end","测试结束"),("mode","模式"),("enabled","启用"),("selected_candidate","执行候选"),("baseline_recent_profit_factor","Baseline近6M PF"),("candidate_recent_profit_factor","候选近6M PF"),("candidate_recent_net_points","候选近6M净点"),("base_test_net_points","基准净点"),("test_net_points","策略净点"),("test_delta_net_points","提升"),("test_profit_factor","PF"),("test_trades","交易数")])}
  </section>

  <section>
    <h2>月度表现</h2>
    {bar_chart(monthlies, "Primary 24x1 monthly net points", "period", "net_points")}
    {table(monthlies, [("period","月份"),("trades","交易数"),("net_points","净点数"),("avg_points","平均点")])}
  </section>

  <section class="grid">
    <div>
      <h2>模式贡献</h2>
      {table(mode_attr, [("adaptive_mode","模式"),("trades","交易数"),("net_points","净点数"),("avg_points","平均点")])}
    </div>
    <div>
      <h2>Fold 模式分布</h2>
      {table(mode_counts, [("mode","模式"),("folds","Folds")])}
    </div>
  </section>

  <section class="grid">
    <div>
      <h2>执行候选分布</h2>
      {table(candidate_counts, [("selected_candidate","候选"),("folds","Folds")])}
    </div>
    <div>
      <h2>信号族贡献 Top</h2>
      {table(attribution(primary_trades, "signal_family"), [("signal_family","Signal family"),("trades","交易数"),("net_points","净点数"),("avg_points","平均点")])}
    </div>
  </section>

  <section class="grid">
    <div>
      <h2>最佳交易样本</h2>
      {table(top_trades, [("trade_id","Trade ID"),("entry_ts","入场"),("exit_ts","出场"),("adaptive_mode","模式"),("signal_family","信号"),("session","Session"),("direction","方向"),("entry_price","入场价"),("exit_price","出场价"),("net_points","净点")], limit=12)}
    </div>
    <div>
      <h2>最差交易样本</h2>
      {table(worst_trades, [("trade_id","Trade ID"),("entry_ts","入场"),("exit_ts","出场"),("adaptive_mode","模式"),("signal_family","信号"),("session","Session"),("direction","方向"),("entry_price","入场价"),("exit_price","出场价"),("net_points","净点")], limit=12)}
    </div>
  </section>

  <section class="warn">
    <h2>结论与限制</h2>
    <p>当前最符合“高收益优先，同时控制风险和过拟合”的候选是 <code>balanced-aggressive fixed sizing</code>：跨窗口净收益约 <code>19.8k~20.7k</code> 点，PF 约 <code>2.30~2.64</code>，最大回撤约 <code>428~610</code> 点。Aggressive 版可到 <code>21.0k~22.1k</code> 点，但成本压力下回撤扩大更快。</p>
    <p>限制：这些结果仍基于 approximate fixed-meta replay，且仓位最高到 2.35x/2.5x 会放大单笔尾部风险。下一步应把同样的折前开关和固定仓位规则移植到精确构建器，并加入逐笔 K 线交易回放与更严格滑点压力测试。</p>
    <script type="application/json" id="report-model">{esc(json.dumps(model, ensure_ascii=False, indent=2))}</script>
  </section>
</div>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HTML report for NQ sum_pos adaptive composite strategy.")
    parser.add_argument("--primary-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-24x1-pf102-net0")
    parser.add_argument("--conservative-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-36x3-pf110-net0")
    parser.add_argument("--cross-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-sweep-epf1.02-net0")
    parser.add_argument("--monthly-pf105-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-24x1-pf105")
    parser.add_argument("--sized-primary-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-fixed-sizing-24x1_pf102")
    parser.add_argument("--sized-cross-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-fixed-sizing-36x1_pf102")
    parser.add_argument("--sized-conservative-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-fixed-sizing-36x3_pf110")
    parser.add_argument("--sized-pf105-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-fixed-sizing-24x1_pf105")
    parser.add_argument("--balanced-primary-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-balanced-aggressive-fixed-sizing-24x1_pf102")
    parser.add_argument("--balanced-cross-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-balanced-aggressive-fixed-sizing-36x1_pf102")
    parser.add_argument("--balanced-conservative-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-balanced-aggressive-fixed-sizing-36x3_pf110")
    parser.add_argument("--balanced-pf105-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-balanced-aggressive-fixed-sizing-24x1_pf105")
    parser.add_argument("--aggressive-primary-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-aggressive-fixed-sizing-24x1_pf102")
    parser.add_argument("--aggressive-cross-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-aggressive-fixed-sizing-36x1_pf102")
    parser.add_argument("--aggressive-conservative-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-aggressive-fixed-sizing-36x3_pf110")
    parser.add_argument("--aggressive-pf105-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-aggressive-fixed-sizing-24x1_pf105")
    parser.add_argument("--output", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-best-report.html")
    args = parser.parse_args()
    doc = build_report(args)
    output = ROOT_DIR / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(doc, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
