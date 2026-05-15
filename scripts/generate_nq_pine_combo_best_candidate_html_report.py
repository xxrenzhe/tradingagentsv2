from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
BEST_STRATEGY = "long_bias_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk"
RANKING_PATH = ROOT_DIR / "reports/NQ-pine-indicator-combo-last-month-ranking.csv"
TRADES_PATH = ROOT_DIR / "reports/NQ-pine-indicator-combo-last-month-best-trades.csv"
REPORT_PATH = ROOT_DIR / "reports/NQ-pine-combo-best-candidate.html"


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _pct(value: float) -> str:
    return f"{value:.1%}"


def _summary(trades: pd.DataFrame) -> dict[str, float | int]:
    net = trades["net_points"].astype(float)
    equity = pd.concat([pd.Series([0.0]), net.cumsum()], ignore_index=True)
    drawdown = equity.cummax() - equity
    gross_profit = net[net > 0].sum()
    gross_loss = abs(net[net < 0].sum())
    return {
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else 0.0,
        "win_rate": float((net > 0).mean()) if len(net) else 0.0,
        "avg_points": float(net.mean()) if len(net) else 0.0,
        "max_drawdown_points": float(drawdown.max()) if len(drawdown) else 0.0,
        "worst_trade_points": float(net.min()) if len(net) else 0.0,
        "best_trade_points": float(net.max()) if len(net) else 0.0,
    }


def _group_summary(trades: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in trades.groupby(columns, dropna=False):
        row: dict[str, Any] = {}
        if not isinstance(key, tuple):
            key = (key,)
        for column, value in zip(columns, key):
            row[column] = value
        row.update(_summary(group))
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("net_points", ascending=False)


def _table(frame: pd.DataFrame, columns: list[str], *, limit: int | None = None) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    data = frame.loc[:, columns].head(limit) if limit else frame.loc[:, columns]
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    rows = []
    for _, row in data.iterrows():
        cells = []
        for column in columns:
            value = row[column]
            if column == "win_rate":
                text = _pct(float(value))
            elif isinstance(value, float):
                text = f"{value:,.2f}"
            else:
                text = str(value)
            cells.append(f"<td>{html.escape(text)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"


def _svg_line(values: list[float], *, title: str, stroke: str, fill: str = "none", height: int = 220) -> str:
    width = 960
    pad_x = 44
    pad_y = 28
    if not values:
        values = [0.0]
    min_y = min(values)
    max_y = max(values)
    if min_y == max_y:
        min_y -= 1.0
        max_y += 1.0
    denom_x = max(len(values) - 1, 1)
    denom_y = max_y - min_y
    points = []
    for idx, value in enumerate(values):
        x = pad_x + idx / denom_x * (width - pad_x * 2)
        y = pad_y + (max_y - value) / denom_y * (height - pad_y * 2)
        points.append(f"{x:.1f},{y:.1f}")
    baseline_y = pad_y + (max_y - 0.0) / denom_y * (height - pad_y * 2)
    baseline_y = max(pad_y, min(height - pad_y, baseline_y))
    return f"""
<figure class="chart-card">
  <figcaption>{html.escape(title)}</figcaption>
  <svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
    <rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="{fill if fill != 'none' else '#0b1220'}" />
    <line x1="{pad_x}" y1="{baseline_y:.1f}" x2="{width - pad_x}" y2="{baseline_y:.1f}" stroke="#334155" stroke-dasharray="5 8" />
    <polyline points="{' '.join(points)}" fill="none" stroke="{stroke}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" />
    <text x="{pad_x}" y="{pad_y - 8}" fill="#94a3b8" font-size="12">{max_y:,.1f}</text>
    <text x="{pad_x}" y="{height - 8}" fill="#94a3b8" font-size="12">{min_y:,.1f}</text>
  </svg>
</figure>
"""


def _write_report(output: Path, ranking: pd.DataFrame, trades: pd.DataFrame) -> None:
    strategy = ranking.loc[ranking["strategy"].eq(BEST_STRATEGY)].iloc[0]
    trades = trades.copy()
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    trades["entry_date"] = trades["entry_ts"].dt.date.astype(str)
    trades["equity_points"] = trades["net_points"].astype(float).cumsum()
    trades["drawdown_points"] = trades["equity_points"].cummax() - trades["equity_points"]

    summary = _summary(trades)
    daily = _group_summary(trades, ["entry_date"])
    session = _group_summary(trades, ["session"])
    family = _group_summary(trades, ["signal_family"])
    exits = _group_summary(trades, ["exit_reason"])

    cards = [
        ("Trades", _fmt(int(summary["trades"]))),
        ("Net Points", _fmt(float(summary["net_points"]))),
        ("Profit Factor", _fmt(float(summary["profit_factor"]))),
        ("Win Rate", _pct(float(summary["win_rate"]))),
        ("Avg / Trade", _fmt(float(summary["avg_points"]))),
        ("Max DD", _fmt(float(summary["max_drawdown_points"]))),
        ("Worst Trade", _fmt(float(summary["worst_trade_points"]))),
        ("Best Trade", _fmt(float(summary["best_trade_points"]))),
    ]
    card_html = "".join(
        f"<div class=\"metric\"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>"
        for label, value in cards
    )
    equity_values = [0.0, *trades["equity_points"].astype(float).tolist()]
    drawdown_values = [0.0, *(-trades["drawdown_points"].astype(float)).tolist()]

    trade_display = trades.copy()
    trade_display["entry_ts"] = trade_display["entry_ts"].dt.strftime("%Y-%m-%d %H:%M UTC")
    trade_display["exit_ts"] = trade_display["exit_ts"].dt.strftime("%Y-%m-%d %H:%M UTC")
    trade_columns = [
        "entry_ts",
        "exit_ts",
        "signal_family",
        "session",
        "direction",
        "entry_price",
        "exit_price",
        "exit_reason",
        "bars_held",
        "net_points",
        "equity_points",
    ]

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NQ Pine Combo Best Candidate Report</title>
  <style>
    :root {{
      --bg:#07111f;
      --panel:#0d1b2e;
      --panel2:#111f35;
      --ink:#e5edf8;
      --muted:#94a3b8;
      --line:#20334d;
      --cyan:#22d3ee;
      --green:#34d399;
      --amber:#fbbf24;
      --red:#fb7185;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:radial-gradient(circle at 20% 0%, #123056 0, transparent 34%), linear-gradient(135deg, #06101d, #0a1526 55%, #07111f); font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    header {{ padding:42px 28px 26px; border-bottom:1px solid var(--line); }}
    main {{ max-width:1240px; margin:0 auto; padding:24px; }}
    h1 {{ max-width:1240px; margin:0 auto 12px; font-size:clamp(30px, 4vw, 54px); line-height:1; letter-spacing:-0.045em; }}
    .subtitle {{ max-width:1240px; margin:0 auto; color:var(--muted); font-size:16px; }}
    .tag {{ display:inline-flex; align-items:center; gap:8px; padding:7px 11px; border:1px solid #1e7490; border-radius:999px; color:#a5f3fc; background:rgba(34,211,238,.08); margin-bottom:16px; }}
    section {{ margin:18px 0; padding:20px; border:1px solid var(--line); background:linear-gradient(180deg, rgba(17,31,53,.92), rgba(13,27,46,.92)); border-radius:22px; box-shadow:0 22px 60px rgba(0,0,0,.22); }}
    h2 {{ margin:0 0 14px; font-size:22px; letter-spacing:-0.02em; }}
    .metrics {{ display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:14px; }}
    .metric {{ padding:16px; border:1px solid #23415f; border-radius:18px; background:rgba(5,12,24,.58); }}
    .metric span {{ display:block; color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
    .metric strong {{ display:block; margin-top:8px; font-size:28px; letter-spacing:-0.03em; }}
    .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
    .chart-card {{ margin:0; }}
    .chart-card figcaption {{ margin:0 0 10px; color:#cbd5e1; font-weight:700; }}
    .table-wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:16px; }}
    table {{ width:100%; border-collapse:collapse; min-width:720px; font-size:13px; }}
    th, td {{ padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; white-space:nowrap; }}
    th {{ color:#cbd5e1; background:#0a1728; position:sticky; top:0; }}
    tr:nth-child(even) td {{ background:rgba(255,255,255,.018); }}
    .note {{ color:var(--muted); line-height:1.6; }}
    code {{ padding:2px 6px; border-radius:7px; background:#06101d; color:#a5f3fc; }}
    @media (max-width: 860px) {{ .metrics, .grid2 {{ grid-template-columns:1fr; }} main {{ padding:14px; }} }}
  </style>
</head>
<body>
  <header>
    <div class="tag">NQ 1m · Databento Recent Month · Best Robust Candidate</div>
    <h1>NQ Pine Combo Best Candidate Report</h1>
    <p class="subtitle"><code>{html.escape(BEST_STRATEGY)}</code><br />Families: <code>{html.escape(str(strategy["families"]))}</code> · MACD filter: <code>{html.escape(str(strategy["macd_filter"]))}</code> · Stop ATR buffer: <code>{strategy["stop_atr_buffer"]}</code> · Target: <code>{strategy["target_r"]}R</code> · Max hold: <code>{strategy["max_hold_bars"]} bars</code></p>
  </header>
  <main>
    <section>
      <h2>Performance Snapshot</h2>
      <div class="metrics">{card_html}</div>
      <p class="note">Cost model is already embedded in <code>net_points</code>. Candidate is long-biased and uses the Lightglow signal families <code>top_breakout_long</code>, <code>trend_ignition_long</code>, <code>trend_pullback_long</code>, <code>trend_transition_long</code>, and <code>reversal_impulse_long</code> with a recent 1m MACD cross filter.</p>
    </section>
    <section class="grid2">
      {_svg_line(equity_values, title="Equity Curve By Trade (net points)", stroke="var(--green)")}
      {_svg_line(drawdown_values, title="Drawdown Curve (negative points)", stroke="var(--red)")}
    </section>
    <section>
      <h2>Breakdown By Signal Family</h2>
      {_table(family, ["signal_family", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points", "worst_trade_points"])}
    </section>
    <section class="grid2">
      <div>
        <h2>Breakdown By Session</h2>
        {_table(session, ["session", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points"])}
      </div>
      <div>
        <h2>Breakdown By Exit Reason</h2>
        {_table(exits, ["exit_reason", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points"])}
      </div>
    </section>
    <section>
      <h2>Daily Results</h2>
      {_table(daily, ["entry_date", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points", "worst_trade_points"])}
    </section>
    <section>
      <h2>Trade Log</h2>
      {_table(trade_display, trade_columns)}
    </section>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an HTML report for the best NQ Pine combo candidate.")
    parser.add_argument("--ranking", default=str(RANKING_PATH))
    parser.add_argument("--trades", default=str(TRADES_PATH))
    parser.add_argument("--output", default=str(REPORT_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ranking = pd.read_csv(args.ranking)
    trades = pd.read_csv(args.trades)
    _write_report(Path(args.output), ranking, trades)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
