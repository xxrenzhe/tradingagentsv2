from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import math
import pandas as pd

from .memory import EvolutionMemory
from .segmentation import Segment


def write_html_report(
    *,
    path: Path | str,
    features: pd.DataFrame,
    segments: list[Segment],
    memory: EvolutionMemory,
    summary: dict[str, Any],
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    top_stats = memory.top_pattern_stats(10)
    all_stats = memory.all_pattern_stats()
    recent_validations = memory.recent_validations(20)
    counts = memory.counts()
    notes = memory.active_notes(10)
    retired = memory.retired_patterns(10)
    html_text = build_report_html(
        features=features,
        segments=segments,
        top_stats=top_stats,
        all_stats=all_stats,
        recent_validations=recent_validations,
        top_notes=notes,
        retired_patterns=retired,
        counts=counts,
        summary=summary,
    )
    output.write_text(html_text, encoding="utf-8")
    return output


def build_report_html(
    *,
    features: pd.DataFrame,
    segments: list[Segment],
    top_stats: list[dict[str, Any]],
    recent_validations: list[dict[str, Any]],
    all_stats: list[dict[str, Any]] | None = None,
    top_notes: list[dict[str, Any]] | None = None,
    retired_patterns: list[dict[str, Any]] | None = None,
    counts: dict[str, int],
    summary: dict[str, Any],
) -> str:
    all_stats = all_stats or top_stats
    top_notes = top_notes or []
    retired_patterns = retired_patterns or []
    segment_rows = "".join(
        "<tr>"
        f"<td>{safe(segment.segment_id)}</td>"
        f"<td>{safe(segment.start_ts)}</td>"
        f"<td>{safe(segment.end_ts)}</td>"
        f"<td>{segment.bars}</td>"
        f"<td>{safe(segment.regime)}</td>"
        f"<td>{safe(segment.split_reason)}</td>"
        f"<td>{segment.high_info_score:.2f}</td>"
        "</tr>"
        for segment in segments[:40]
    )
    stats_rows = table_rows(
        top_stats,
        ["rule_signature", "status", "validations", "trades", "net_points", "profit_factor", "win_rate", "positive_validation_rate", "edge_score"],
    )
    validation_rows = table_rows(
        recent_validations,
        ["validation_id", "rule_signature", "trades", "net_points", "profit_factor", "win_rate", "avg_win_points", "avg_loss_points", "exit_reason_json", "validation_status", "failure_reason"],
    )
    note_rows = table_rows(top_notes, ["note_id", "rule_signature", "note_type", "confidence", "use_count", "lesson"])
    retired_rows = table_rows(retired_patterns, ["rule_signature", "status", "validations", "trades", "net_points", "retired_reason"])
    counts_cards = "".join(f"<div class='metric'><span>{safe(key)}</span><strong>{value:,}</strong></div>" for key, value in counts.items())
    status_counts = _status_counts(all_stats)
    status_cards = "".join(f"<div class='metric'><span>{safe(key)}</span><strong>{value:,}</strong></div>" for key, value in status_counts.items())
    prompt_avg = _average_memory_tokens(summary)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ 交易进化系统报告</title>
  <style>
    body {{ margin:0; font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:#17201b; background:#f7f8f5; }}
    header {{ padding:32px 48px; background:#15251f; color:#f6fbf7; }}
    main {{ padding:28px 48px 56px; }}
    h1 {{ margin:0 0 10px; font-size:34px; }}
    h2 {{ margin:28px 0 12px; font-size:22px; }}
    h3 {{ margin:22px 0 10px; font-size:16px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; }}
    .metric {{ background:white; border:1px solid #d8ded6; border-radius:8px; padding:14px; }}
    .metric span {{ display:block; color:#66756c; font-size:12px; }}
    .metric strong {{ font-size:22px; }}
    table {{ width:100%; border-collapse:collapse; background:white; border:1px solid #d8ded6; }}
    th, td {{ padding:8px 10px; border-bottom:1px solid #e7ebe4; text-align:left; vertical-align:top; }}
    th {{ background:#edf2ed; font-size:12px; color:#3d4b43; }}
    code, pre {{ background:#eef3ee; padding:2px 4px; border-radius:4px; }}
    .chart {{ background:white; border:1px solid #d8ded6; border-radius:8px; padding:14px; overflow-x:auto; }}
    .bar {{ fill:#247a55; opacity:.72; }}
    .bar.high {{ fill:#b9852b; opacity:.9; }}
    .two-col {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:18px; }}
    @media (max-width: 900px) {{ header, main {{ padding-left:20px; padding-right:20px; }} .two-col {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <header>
    <h1>NQ 1分钟交易进化系统报告</h1>
    <p>动态窗口、LLM规则生成、后续验证、SQLite记忆与反膨胀审计。</p>
  </header>
  <main>
    <h2>运行摘要</h2>
    <p>数据从Databento NQ 1分钟OHLCV构造连续合约序列；重叠季度合约按每分钟最高成交量选择，避免把价差符号纳入研究。</p>
    <div class="grid">
      {metric("feature_rows", len(features))}
      {metric("segments", len(segments))}
      {metric("llm_calls", summary.get("llm_calls", 0))}
      {metric("llm_successes", summary.get("llm_successes", 0))}
      {metric("llm_parse_errors", summary.get("llm_parse_errors", 0))}
      {metric("fallback_rules", summary.get("llm_fallback_rules", 0))}
      {metric("validations", counts.get("validations", 0))}
      {metric("trades", counts.get("validation_trades", 0))}
      {metric("avg_memory_tokens", f"{prompt_avg:.0f}")}
    </div>
    <h2>记忆系统状态</h2>
    <div class="grid">{status_cards}</div>
    <div class="grid">{counts_cards}</div>
    <h3>Top 经验Note</h3>
    <table><thead>{header_row(["note_id","rule_signature","note_type","confidence","use_count","lesson"])}</thead><tbody>{note_rows}</tbody></table>
    <h2>动态窗口概览</h2>
    <div class="chart">{segment_svg(segments)}</div>
    <h3>全周期降采样K线概览</h3>
    <div class="chart">{ohlc_svg(features)}</div>
    <table>
      <thead><tr><th>segment</th><th>start</th><th>end</th><th>bars</th><th>regime</th><th>split</th><th>info</th></tr></thead>
      <tbody>{segment_rows}</tbody>
    </table>
    <h2>Top 模式统计</h2>
    <table><thead>{header_row(["rule_signature","status","validations","trades","net_points","profit_factor","win_rate","positive_validation_rate","edge_score"])}</thead><tbody>{stats_rows}</tbody></table>
    <h2>策略组合表现</h2>
    <div class="grid">
      {metric("active_research", status_counts.get("research", 0))}
      {metric("candidate", status_counts.get("candidate", 0))}
      {metric("stable", status_counts.get("stable", 0))}
      {metric("retired", status_counts.get("retired", 0))}
    </div>
    <h2>最近验证</h2>
    <table><thead>{header_row(["validation_id","rule_signature","trades","net_points","profit_factor","win_rate","avg_win_points","avg_loss_points","exit_reason_json","validation_status","failure_reason"])}</thead><tbody>{validation_rows}</tbody></table>
    <h2>失败模式总结</h2>
    <table><thead>{header_row(["rule_signature","status","validations","trades","net_points","retired_reason"])}</thead><tbody>{retired_rows}</tbody></table>
    <h2>可复现实验参数</h2>
    <pre>{safe(json.dumps(summary, indent=2, sort_keys=True, default=str))}</pre>
  </main>
</body>
</html>"""


def metric(label: str, value: Any) -> str:
    return f"<div class='metric'><span>{safe(label)}</span><strong>{safe(value)}</strong></div>"


def header_row(columns: list[str]) -> str:
    return "<tr>" + "".join(f"<th>{safe(column)}</th>" for column in columns) + "</tr>"


def table_rows(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return f"<tr><td colspan='{len(columns)}'>无记录</td></tr>"
    rendered = []
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column, "")
            if isinstance(value, float):
                value = f"{value:.4f}"
            cells.append(f"<td>{safe(value)}</td>")
        rendered.append("<tr>" + "".join(cells) + "</tr>")
    return "".join(rendered)


def segment_svg(segments: list[Segment]) -> str:
    if not segments:
        return "<p>无segment。</p>"
    width = max(720, min(1800, len(segments) * 18))
    height = 180
    max_bars = max(segment.bars for segment in segments) or 1
    bar_w = max(width / len(segments) * 0.72, 2)
    bars = []
    for index, segment in enumerate(segments):
        x = index * width / len(segments)
        h = max(4, segment.bars / max_bars * 120)
        y = height - h - 24
        cls = "bar high" if segment.high_info_score >= 0.8 else "bar"
        bars.append(f"<rect class='{cls}' x='{x:.1f}' y='{y:.1f}' width='{bar_w:.1f}' height='{h:.1f}'><title>{safe(segment.segment_id)} {segment.bars} bars {segment.regime}</title></rect>")
    return f"<svg viewBox='0 0 {width} {height}' width='100%' height='180' role='img' aria-label='segment bars'>{''.join(bars)}<line x1='0' y1='{height-24}' x2='{width}' y2='{height-24}' stroke='#89958d'/></svg>"


def ohlc_svg(features: pd.DataFrame, max_points: int = 220) -> str:
    if features.empty:
        return "<p>无K线数据。</p>"
    frame = features[["Open", "High", "Low", "Close"]].dropna().copy()
    if frame.empty:
        return "<p>无K线数据。</p>"
    bucket = max(1, math.ceil(len(frame) / max_points))
    grouped = frame.groupby(frame.index // bucket).agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"))
    width = 1100
    height = 260
    high = float(grouped["High"].max())
    low = float(grouped["Low"].min())
    scale = max(high - low, 1.0)
    candle_w = max(width / len(grouped) * 0.55, 1.5)

    def y(price: float) -> float:
        return 18 + (high - float(price)) / scale * (height - 42)

    candles = []
    for index, row in enumerate(grouped.itertuples(index=False)):
        x = index * width / len(grouped) + width / len(grouped) / 2
        open_y = y(row.Open)
        close_y = y(row.Close)
        high_y = y(row.High)
        low_y = y(row.Low)
        color = "#247a55" if row.Close >= row.Open else "#b04432"
        body_y = min(open_y, close_y)
        body_h = max(abs(open_y - close_y), 1.0)
        candles.append(
            f"<line x1='{x:.1f}' y1='{high_y:.1f}' x2='{x:.1f}' y2='{low_y:.1f}' stroke='{color}' stroke-width='1'/>"
            f"<rect x='{x - candle_w / 2:.1f}' y='{body_y:.1f}' width='{candle_w:.1f}' height='{body_h:.1f}' fill='{color}' opacity='.78'/>"
        )
    return f"<svg viewBox='0 0 {width} {height}' width='100%' height='260' role='img' aria-label='downsampled ohlc candles'>{''.join(candles)}</svg>"


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {"new": 0, "research": 0, "candidate": 0, "stable": 0, "watch": 0, "retired": 0}
    for row in rows:
        status = str(row.get("status", "new"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def _average_memory_tokens(summary: dict[str, Any]) -> float:
    counts = summary.get("counts", {})
    packets = float(counts.get("memory_packets", 0) or 0)
    if packets <= 0:
        return 0.0
    return float(summary.get("memory_token_total", 0.0) or 0.0) / packets


def safe(value: Any) -> str:
    return html.escape(str(value), quote=True)
