from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from search_nq_bar_2r_walkforward import load_continuous_nq_bars  # noqa: E402

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


def _load_bars_for_trades(trades: pd.DataFrame, cache: str, chunk_size: int, min_volume: float) -> pd.DataFrame:
    start = pd.to_datetime(trades["entry_ts"], utc=True).min().floor("D")
    end = (pd.to_datetime(trades["exit_ts"], utc=True).max() + pd.Timedelta(days=1)).ceil("D")
    args = argparse.Namespace(
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
        cache=cache,
        chunk_size=chunk_size,
        min_volume=min_volume,
    )
    return load_continuous_nq_bars(args).sort_values("ts").reset_index(drop=True)


def _trade_kline_svg(bars: pd.DataFrame, trades: pd.DataFrame) -> str:
    if bars.empty or trades.empty:
        return "<p>No K-line data available.</p>"
    width = 1380
    height = 720
    pad_left = 68
    pad_right = 34
    pad_top = 30
    pad_bottom = 72
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    bars = bars.copy().reset_index(drop=True)
    for column in ["Open", "High", "Low", "Close"]:
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    bars = bars.dropna(subset=["Open", "High", "Low", "Close"]).reset_index(drop=True)
    if bars.empty:
        return "<p>No K-line data available.</p>"
    price_min = min(float(bars["Low"].min()), float(trades[["entry_price", "exit_price"]].min().min()))
    price_max = max(float(bars["High"].max()), float(trades[["entry_price", "exit_price"]].max().max()))
    padding = max((price_max - price_min) * 0.06, 1.0)
    price_min -= padding
    price_max += padding
    price_span = price_max - price_min

    ts_values = pd.to_datetime(bars["ts"], utc=True)
    ts_to_index = {ts.value: idx for idx, ts in enumerate(ts_values)}

    def x_for_index(index: int) -> float:
        return pad_left + index / max(len(bars) - 1, 1) * plot_w

    def y_for_price(price: float) -> float:
        return pad_top + (price_max - price) / price_span * plot_h

    def index_for_ts(ts: pd.Timestamp) -> int:
        value = ts.value
        if value in ts_to_index:
            return ts_to_index[value]
        pos = ts_values.searchsorted(ts)
        return int(max(0, min(len(bars) - 1, pos)))

    max_bars_to_draw = 2600
    step = max(1, len(bars) // max_bars_to_draw)
    candle_parts: list[str] = []
    candle_width = max(1.0, plot_w / max(len(bars) / step, 1) * 0.62)
    for index in range(0, len(bars), step):
        row = bars.iloc[index]
        x = x_for_index(index)
        y_high = y_for_price(float(row["High"]))
        y_low = y_for_price(float(row["Low"]))
        y_open = y_for_price(float(row["Open"]))
        y_close = y_for_price(float(row["Close"]))
        up = float(row["Close"]) >= float(row["Open"])
        color = "#2dd4bf" if up else "#fb7185"
        body_y = min(y_open, y_close)
        body_h = max(abs(y_close - y_open), 1.2)
        candle_parts.append(
            f'<line x1="{x:.1f}" y1="{y_high:.1f}" x2="{x:.1f}" y2="{y_low:.1f}" stroke="{color}" stroke-width="1.1" opacity="0.72" />'
            f'<rect x="{x - candle_width / 2:.1f}" y="{body_y:.1f}" width="{candle_width:.1f}" height="{body_h:.1f}" rx="1" fill="{color}" opacity="0.72" />'
        )

    trade_parts: list[str] = []
    label_rows: list[str] = []
    for trade_no, row in enumerate(trades.itertuples(index=False), start=1):
        entry_ts = pd.Timestamp(row.entry_ts)
        exit_ts = pd.Timestamp(row.exit_ts)
        entry_index = index_for_ts(entry_ts)
        exit_index = index_for_ts(exit_ts)
        entry_x = x_for_index(entry_index)
        exit_x = x_for_index(exit_index)
        entry_y = y_for_price(float(row.entry_price))
        exit_y = y_for_price(float(row.exit_price))
        is_long = int(row.direction) > 0
        net = float(row.net_points)
        pnl_color = "#34d399" if net >= 0 else "#fb7185"
        direction_text = "LONG" if is_long else "SHORT"
        marker = "▲" if is_long else "▼"
        entry_label_y = entry_y - 12 if is_long else entry_y + 18
        exit_label_y = exit_y - 12 if net >= 0 else exit_y + 18
        trade_parts.append(
            f'<line class="trade-link" x1="{entry_x:.1f}" y1="{entry_y:.1f}" x2="{exit_x:.1f}" y2="{exit_y:.1f}" stroke="{pnl_color}" stroke-width="1.4" opacity="0.62" />'
            f'<circle class="trade-entry" cx="{entry_x:.1f}" cy="{entry_y:.1f}" r="4.2" fill="#38bdf8" stroke="#e0f2fe" stroke-width="1.2" />'
            f'<text x="{entry_x + 5:.1f}" y="{entry_label_y:.1f}" fill="#bae6fd" font-size="10">#{trade_no} {direction_text} IN {float(row.entry_price):,.2f}</text>'
            f'<circle class="trade-exit" cx="{exit_x:.1f}" cy="{exit_y:.1f}" r="4.5" fill="{pnl_color}" stroke="#fff7ed" stroke-width="1.1" />'
            f'<text x="{exit_x + 5:.1f}" y="{exit_label_y:.1f}" fill="{pnl_color}" font-size="10">{marker} OUT {net:+.2f} pts</text>'
        )
        label_rows.append(
            f"<tr><td>{trade_no}</td><td>{html.escape(entry_ts.strftime('%m-%d %H:%M'))}</td><td>{direction_text}</td><td>{float(row.entry_price):,.2f}</td><td>{html.escape(exit_ts.strftime('%m-%d %H:%M'))}</td><td>{float(row.exit_price):,.2f}</td><td class=\"{'gain' if net >= 0 else 'loss'}\">{net:+.2f}</td></tr>"
        )

    grid_lines = []
    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = pad_top + frac * plot_h
        price = price_max - frac * price_span
        grid_lines.append(f'<line x1="{pad_left}" y1="{y:.1f}" x2="{width - pad_right}" y2="{y:.1f}" stroke="#1f3653" stroke-width="1" />')
        grid_lines.append(f'<text x="12" y="{y + 4:.1f}" fill="#94a3b8" font-size="12">{price:,.0f}</text>')
    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        x = pad_left + frac * plot_w
        idx = int(frac * (len(bars) - 1))
        label = ts_values.iloc[idx].strftime("%m-%d")
        grid_lines.append(f'<line x1="{x:.1f}" y1="{pad_top}" x2="{x:.1f}" y2="{height - pad_bottom}" stroke="#132842" stroke-width="1" />')
        grid_lines.append(f'<text x="{x - 18:.1f}" y="{height - 34}" fill="#94a3b8" font-size="12">{label}</text>')

    return f"""
<div class="kline-wrap">
  <svg class="kline-svg" viewBox="0 0 {width} {height}" role="img" aria-label="NQ 1-minute K-line chart with trade entry and exit markers">
    <rect x="0" y="0" width="{width}" height="{height}" rx="20" fill="#07111f" />
    {''.join(grid_lines)}
    <g class="candles">{''.join(candle_parts)}</g>
    <g class="trade-markers">{''.join(trade_parts)}</g>
    <text x="{pad_left}" y="22" fill="#e5edf8" font-size="15" font-weight="700">NQ 1m K-line with all {len(trades)} trades: blue = entry, green/red = exit PnL, line = entry-to-exit path</text>
  </svg>
  <details>
    <summary>Marker index table</summary>
    <div class="table-wrap mini"><table><thead><tr><th>#</th><th>Entry</th><th>Side</th><th>Entry Px</th><th>Exit</th><th>Exit Px</th><th>PnL pts</th></tr></thead><tbody>{''.join(label_rows)}</tbody></table></div>
  </details>
</div>
"""


def _write_report(output: Path, ranking: pd.DataFrame, trades: pd.DataFrame, bars: pd.DataFrame | None = None) -> None:
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
    if bars is None:
        bars = pd.DataFrame()
    kline_chart = _trade_kline_svg(bars, trades)

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
    .kline-wrap {{ overflow-x:auto; }}
    .kline-svg {{ min-width:1180px; width:100%; height:auto; border:1px solid var(--line); border-radius:22px; background:#07111f; }}
    details {{ margin-top:12px; color:var(--muted); }}
    summary {{ cursor:pointer; color:#cbd5e1; font-weight:700; }}
    .mini table {{ min-width:900px; }}
    .gain {{ color:var(--green); font-weight:700; }}
    .loss {{ color:var(--red); font-weight:700; }}
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
      <h2>K-line Trade Replay</h2>
      <p class="note">Each trade is plotted directly on the NQ 1-minute candles: blue dot marks entry, green/red dot marks exit, labels show long/short side, entry/exit price, and net PnL points after costs.</p>
      {kline_chart}
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
    parser.add_argument("--bars-cache", default=".tmp/nq-pine-combo-best-candidate-bars.pkl")
    parser.add_argument("--chunk-size", type=int, default=200_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ranking = pd.read_csv(args.ranking)
    trades = pd.read_csv(args.trades)
    bars = _load_bars_for_trades(trades, args.bars_cache, args.chunk_size, args.min_volume)
    _write_report(Path(args.output), ranking, trades, bars)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
