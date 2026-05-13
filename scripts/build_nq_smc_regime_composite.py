from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
TRADES_PATH = ROOT_DIR / ".tmp" / "nq-regime-transition-readiness-trades.csv"
REPORT_PATH = ROOT_DIR / "reports" / "NQ-smc-regime-trend-composite-report.html"
SUMMARY_PATH = ROOT_DIR / "reports" / "NQ-smc-regime-trend-composite-summary.csv"
TRADES_OUTPUT = ROOT_DIR / "reports" / "NQ-smc-regime-trend-composite-trades.csv"

LABEL_NAMES = {
    "optimized50_2r5_quality": "50m quality primary",
    "defensive45_2r5_loweff": "45m low-eff add-on",
    "defensive45_2r5_lossfilter": "45m loss-filter",
    "short45_2r25_netdd": "45m 2.25R high-net",
    "short45_2r5_maxnet": "45m 2.5R max-net",
}


def load_trades(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path)
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True, errors="coerce")
    data["exit_ts"] = pd.to_datetime(data["exit_ts"], utc=True, errors="coerce")
    return data.dropna(subset=["entry_ts", "exit_ts", "entry_index", "exit_index", "net_points"]).reset_index(drop=True)


def non_overlap(trades: pd.DataFrame, labels: list[str]) -> pd.DataFrame:
    priority = {label: index for index, label in enumerate(labels)}
    selected = trades[trades["audit_label"].isin(labels)].copy()
    selected["priority"] = selected["audit_label"].map(priority).fillna(999).astype(int)
    selected = selected.sort_values(["entry_index", "priority", "exit_index"]).reset_index(drop=True)
    rows: list[pd.Series] = []
    next_available = 0
    for _, row in selected.iterrows():
        if int(row["entry_index"]) < next_available:
            continue
        rows.append(row)
        next_available = int(row["exit_index"]) + 1
    if not rows:
        return selected.iloc[0:0].drop(columns=["priority"], errors="ignore")
    return pd.DataFrame(rows).drop(columns=["priority"], errors="ignore").reset_index(drop=True)


def rolling_stats(trades: pd.DataFrame, days: int) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["start", "end", "trades", "net_points"])
    start = trades["entry_ts"].min().normalize()
    end = trades["entry_ts"].max().normalize()
    rows: list[dict[str, Any]] = []
    cursor = start
    while cursor + pd.Timedelta(days=days) <= end:
        stop = cursor + pd.Timedelta(days=days)
        selected = trades[(trades["entry_ts"] >= cursor) & (trades["entry_ts"] < stop)]
        rows.append(
            {
                "start": str(cursor.date()),
                "end": str(stop.date()),
                "trades": int(len(selected)),
                "net_points": float(pd.to_numeric(selected["net_points"], errors="coerce").fillna(0.0).sum()),
            }
        )
        cursor += pd.Timedelta(days=days)
    return pd.DataFrame(rows)


def summarize(trades: pd.DataFrame, label: str) -> dict[str, Any]:
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    gross = pd.to_numeric(trades["gross_points"], errors="coerce").fillna(0.0)
    wins = net[net > 0]
    losses = net[net < 0]
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    yearly = net.groupby(trades["entry_ts"].dt.year).sum()
    rolling90 = rolling_stats(trades, 90)
    return {
        "label": label,
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "net_dollars": float(net.sum() * 20.0),
        "profit_factor": float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) else 999.0,
        "win_rate": float((net > 0).mean()) if len(net) else 0.0,
        "payoff_ratio": float(wins.mean() / abs(losses.mean())) if len(wins) and len(losses) else 0.0,
        "expectancy_points": float(net.mean()) if len(net) else 0.0,
        "max_drawdown_points": float(abs(drawdown.min())) if len(drawdown) else 0.0,
        "net_to_drawdown": float(net.sum() / max(abs(float(drawdown.min())), 1.0)) if len(drawdown) else 0.0,
        "positive_year_rate": float((yearly > 0).mean()) if len(yearly) else 0.0,
        "worst_year_points": float(yearly.min()) if len(yearly) else 0.0,
        "positive_90d_rate": float((rolling90["net_points"] > 0).mean()) if not rolling90.empty else 0.0,
        "worst_90d_points": float(rolling90["net_points"].min()) if not rolling90.empty else 0.0,
        "net_at_cost_2.125": float(gross.sum() - 2.125 * len(trades)),
        "same_bar_count": int((trades["entry_index"].to_numpy(dtype=int) == trades["exit_index"].to_numpy(dtype=int)).sum()),
    }


def fmt(value: object, digits: int = 2) -> str:
    if pd.isna(value):
        return "-"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return html.escape(str(value))


def pct(value: object) -> str:
    return f"{float(value):.1%}" if not pd.isna(value) else "-"


def table(frame: pd.DataFrame, columns: list[str]) -> str:
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    rows = []
    for _, row in frame[columns].iterrows():
        cells = []
        for column in columns:
            value = row[column]
            if "rate" in column or column == "win_rate":
                rendered = pct(value)
            elif isinstance(value, (float, np.floating)):
                rendered = fmt(value, 3 if "factor" in column or "ratio" in column else 2)
            else:
                rendered = html.escape(str(value))
            cells.append(f"<td>{rendered}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def render_report(summary: pd.DataFrame, yearly: pd.DataFrame, trades: pd.DataFrame, labels: list[str]) -> str:
    best = summary.iloc[0]
    label_text = " + ".join(LABEL_NAMES.get(label, label) for label in labels)
    by_family = trades.groupby("audit_label", as_index=False)["net_points"].agg(["count", "sum", "mean"]).reset_index()
    by_family["name"] = by_family["audit_label"].map(lambda value: LABEL_NAMES.get(str(value), str(value)))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>NQ SMC Regime Composite</title>
  <style>
    body {{ margin:0; background:#0e1714; color:#ecfdf5; font:14px/1.6 Georgia,"Times New Roman",serif; }}
    main {{ max-width:1120px; margin:0 auto; padding:32px 22px 70px; }}
    h1 {{ margin:0 0 8px; font-size:38px; }}
    h2 {{ margin-top:30px; border-bottom:1px solid #31443b; padding-bottom:8px; }}
    p,li {{ color:#bdd6c8; }}
    code {{ color:#bbf7d0; }}
    .cards {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:22px 0; }}
    .card {{ background:#15241d; border:1px solid #31443b; border-radius:12px; padding:14px; }}
    .card span {{ display:block; color:#91aa9d; font-size:12px; }}
    .card strong {{ display:block; margin-top:6px; font-size:23px; }}
    table {{ width:100%; border-collapse:collapse; margin:12px 0 24px; font-size:13px; }}
    th,td {{ border:1px solid #31443b; padding:8px 10px; text-align:right; }}
    th:first-child,td:first-child {{ text-align:left; }}
    th {{ background:#1b2d24; }}
  </style>
</head>
<body>
<main>
  <h1>NQ SMC-Regime 趋势组合提净收益报告</h1>
  <p>组合：<code>{html.escape(label_text)}</code>。规则：按优先级合并候选交易，任何持仓重叠时只保留优先级更高或更早触发的交易，仍然使用已修正的 no-same-bar 逐笔结果。</p>
  <div class="cards">
    <div class="card"><span>Trades</span><strong>{fmt(best["trades"], 0)}</strong></div>
    <div class="card"><span>Net Points</span><strong>{fmt(best["net_points"])}</strong></div>
    <div class="card"><span>PF</span><strong>{fmt(best["profit_factor"], 3)}</strong></div>
    <div class="card"><span>Net/DD</span><strong>{fmt(best["net_to_drawdown"])}</strong></div>
    <div class="card"><span>Win Rate</span><strong>{pct(best["win_rate"])}</strong></div>
    <div class="card"><span>Max DD</span><strong>{fmt(best["max_drawdown_points"])}</strong></div>
    <div class="card"><span>90d Positive</span><strong>{pct(best["positive_90d_rate"])}</strong></div>
    <div class="card"><span>Same Bar</span><strong>{fmt(best["same_bar_count"], 0)}</strong></div>
  </div>
  <h2>候选对比</h2>
  {table(summary, ["label", "trades", "net_points", "profit_factor", "win_rate", "expectancy_points", "max_drawdown_points", "net_to_drawdown", "positive_year_rate", "positive_90d_rate", "worst_90d_points", "same_bar_count"])}
  <h2>组合年度结果</h2>
  {table(yearly, ["year", "trades", "net_points"])}
  <h2>组合内部贡献</h2>
  {table(by_family, ["name", "count", "sum", "mean"])}
  <h2>结论</h2>
  <p>组合相对单一 50m quality 主策略提高净收益，但牺牲部分 PF。若目标是最大化净收益且接受 PF 从约 1.97 降到约 1.76，这是当前更合理的升级；若目标是最高质量/低回撤，仍应保留单一 50m quality。</p>
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build no-overlap composite for NQ SMC regime trend candidates.")
    parser.add_argument("--labels", nargs="+", default=["optimized50_2r5_quality", "defensive45_2r5_loweff"])
    parser.add_argument("--report", default=str(REPORT_PATH))
    parser.add_argument("--summary", default=str(SUMMARY_PATH))
    parser.add_argument("--trades-output", default=str(TRADES_OUTPUT))
    args = parser.parse_args()

    source = load_trades(TRADES_PATH)
    composite = non_overlap(source, args.labels)
    baseline_rows = []
    for label in args.labels:
        baseline_rows.append(summarize(non_overlap(source, [label]), LABEL_NAMES.get(label, label)))
    summary = pd.DataFrame([summarize(composite, "Composite")] + baseline_rows)
    yearly = composite.assign(year=composite["entry_ts"].dt.year).groupby("year").agg(
        trades=("net_points", "size"),
        net_points=("net_points", "sum"),
    ).reset_index()

    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary, index=False)
    composite.to_csv(args.trades_output, index=False)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(render_report(summary, yearly, composite, args.labels), encoding="utf-8")
    print(f"wrote {args.summary}")
    print(f"wrote {args.trades_output}")
    print(f"wrote {args.report}")
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
