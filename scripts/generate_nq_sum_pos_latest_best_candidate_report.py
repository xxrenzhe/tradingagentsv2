from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_nq_pine_combo_best_candidate_html_report import (  # noqa: E402
    _ensure_trade_ids,
    _group_summary,
    _load_bars_for_trades,
    _period_breakdown,
    _period_summary,
    _select_replay_trades,
    _summary,
    _svg_line,
    _table,
    _trade_kline_svg,
)


DEFAULT_TRADES = (
    "reports/"
    "NQ-pine-sum_pos-open2-adaptive-composite-balanced-aggressive-fixed-sizing-24x1_pf102-trades.csv"
)
DEFAULT_SUMMARY = (
    "reports/"
    "NQ-pine-sum_pos-open2-adaptive-composite-balanced-aggressive-fixed-sizing-24x1_pf102-summary.csv"
)
DEFAULT_OUTPUT = "reports/NQ-pine-sum_pos-open2-balanced-aggressive-fixed-sizing-best-candidate.html"


def _fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _pct(value: float) -> str:
    return f"{value:.1%}"


def _read_csv(path: str) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.is_absolute():
        csv_path = ROOT_DIR / csv_path
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)
    return pd.read_csv(csv_path)


def _strategy_metadata(summary_path: str) -> dict[str, str]:
    summary = _read_csv(summary_path).iloc[0].to_dict()
    return {
        "strategy": "sum_pos_open2_balanced_aggressive_fixed_sizing",
        "families": "adaptive composite pf1.02/net0 + causal balanced-aggressive fold sizing",
        "macd_filter": "mixed / source components",
        "stop_atr_buffer": "mixed",
        "target_r": "mixed",
        "max_hold_bars": "mixed",
        "sizing_rule": (
            "baseline PF>=1.30 and net>=1000 -> 2.35x; "
            "baseline PF>=1.20 and net>=0 -> 1.65x; "
            "defensive PF>=1.50 and net>=300 -> 1.40x; "
            "defensive base -> 0.85x; no_trade -> 0x"
        ),
        "source_summary": ", ".join(
            [
                f"net={float(summary['net_points']):,.2f}",
                f"PF={float(summary['profit_factor']):.3f}",
                f"DD={float(summary['max_drawdown_points']):,.2f}",
            ]
        ),
    }


def write_report(
    output: Path,
    trades: pd.DataFrame,
    bars: pd.DataFrame,
    metadata: dict[str, str],
) -> None:
    selected_strategy = metadata["strategy"]
    report_title = f"NQ Pine {selected_strategy} Candidate Report"
    trades = _ensure_trade_ids(trades, selected_strategy)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    trades = trades.sort_values("entry_ts").reset_index(drop=True)
    trades["entry_date"] = trades["entry_ts"].dt.date.astype(str)
    trades["equity_points"] = trades["net_points"].astype(float).cumsum()
    trades["drawdown_points"] = trades["equity_points"].cummax() - trades["equity_points"]
    if "position_scale" in trades.columns:
        trades["position_scale"] = trades["position_scale"].astype(float)
    else:
        trades["position_scale"] = 1.0

    summary = _summary(trades)
    period = _period_summary(trades)
    yearly = _period_breakdown(trades, "year")
    monthly = _period_breakdown(trades, "month")
    daily = _group_summary(trades, ["entry_date"])
    session = _group_summary(trades, ["session"])
    family = _group_summary(trades, ["signal_family"])
    exits = _group_summary(trades, ["exit_reason"])
    modes = _group_summary(trades, ["adaptive_mode"]) if "adaptive_mode" in trades.columns else pd.DataFrame()
    scales = _group_summary(trades.assign(position_bucket=trades["position_scale"].map(lambda value: f"{value:g}x")), ["position_bucket"])
    replay_trades = _select_replay_trades(trades, top_n=10, bottom_n=10)
    kline_chart = _trade_kline_svg(bars, replay_trades, replay_title="Only Top10 winning trades and Bottom10 losing trades")

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
    period_cards = [
        ("First Entry", str(period["first_entry"])),
        ("Last Entry", str(period["last_entry"])),
        ("Last Exit", str(period["last_exit"])),
        ("Calendar Days", _fmt(int(period["calendar_days"]))),
        ("Calendar Years", _fmt(float(period["calendar_years"]))),
        ("Active Months", _fmt(int(period["active_months"]))),
        ("First Month", str(period["first_month"])),
        ("Last Month", str(period["last_month"])),
    ]
    period_card_html = "".join(
        f"<div class=\"metric\"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>"
        for label, value in period_cards
    )
    equity_values = [0.0, *trades["equity_points"].astype(float).tolist()]
    drawdown_values = [0.0, *(-trades["drawdown_points"].astype(float)).tolist()]

    trade_display = trades.copy()
    trade_display["entry_ts"] = trade_display["entry_ts"].dt.strftime("%Y-%m-%d %H:%M UTC")
    trade_display["exit_ts"] = trade_display["exit_ts"].dt.strftime("%Y-%m-%d %H:%M UTC")
    trade_columns = [
        "trade_id",
        "entry_ts",
        "exit_ts",
        "adaptive_mode",
        "position_scale",
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
    trade_columns = [column for column in trade_columns if column in trade_display.columns]

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(report_title)}</title>
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
    .trade-card-grid {{ display:grid; gap:16px; }}
    .trade-card {{ border:1px solid var(--line); border-radius:20px; padding:14px; background:rgba(5,12,24,.45); }}
    .trade-card-head {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; margin-bottom:10px; color:#dbeafe; }}
    .trade-card-head span {{ color:var(--muted); font-size:12px; text-align:right; }}
    .trade-kline-svg {{ min-width:920px; width:100%; height:auto; border:1px solid var(--line); border-radius:18px; background:#07111f; }}
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
    <div class="tag">NQ 1m · Databento · Strategy Candidate</div>
    <h1>{html.escape(report_title)}</h1>
    <p class="subtitle"><code>{html.escape(selected_strategy)}</code><br />Families: <code>{html.escape(metadata["families"])}</code> · MACD filter: <code>{html.escape(metadata["macd_filter"])}</code> · Stop ATR buffer: <code>{html.escape(metadata["stop_atr_buffer"])}</code> · Target: <code>{html.escape(metadata["target_r"])}</code> · Max hold: <code>{html.escape(metadata["max_hold_bars"])}</code><br />Sizing: <code>{html.escape(metadata["sizing_rule"])}</code></p>
  </header>
  <main>
    <section>
      <h2>Performance Snapshot</h2>
      <div class="metrics">{card_html}</div>
      <p class="note">Cost model is embedded in <code>net_points</code>. This report uses the same dark candidate-report format as the prior runner-meta allocation report, but the strategy is the latest causal adaptive composite with balanced-aggressive fixed sizing. Source summary: <code>{html.escape(metadata["source_summary"])}</code>.</p>
    </section>
    <section>
      <h2>Data Coverage Period</h2>
      <div class="metrics">{period_card_html}</div>
      <p class="note">The calendar span is measured from first trade entry to last trade entry. Active months counts months with at least one executed trade.</p>
    </section>
    <section class="grid2">
      {_svg_line(equity_values, title="Equity Curve By Trade (net points)", stroke="var(--green)")}
      {_svg_line(drawdown_values, title="Drawdown Curve (negative points)", stroke="var(--red)")}
    </section>
    <section class="grid2">
      <div>
        <h2>Yearly PnL Distribution</h2>
        {_table(yearly, ["period", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points", "worst_trade_points", "best_trade_points"])}
      </div>
      <div>
        <h2>Monthly PnL Distribution</h2>
        {_table(monthly, ["period", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points", "worst_trade_points", "best_trade_points"])}
      </div>
    </section>
    <section>
      <h2>K-line Trade Replay</h2>
      <p class="note">To keep the HTML file small, only Top10 winning trades and Bottom10 losing trades are plotted on NQ 1-minute candles. Blue dot marks entry, green/red dot marks exit, labels show long/short side, entry/exit price, and sized net PnL points after costs.</p>
      {kline_chart}
    </section>
    <section>
      <h2>Breakdown By Signal Family</h2>
      {_table(family, ["signal_family", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points", "worst_trade_points"])}
    </section>
    <section class="grid2">
      <div>
        <h2>Breakdown By Adaptive Mode</h2>
        {_table(modes, ["adaptive_mode", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points"]) if not modes.empty else "<p class='note'>No adaptive mode column.</p>"}
      </div>
      <div>
        <h2>Breakdown By Position Scale</h2>
        {_table(scales, ["position_bucket", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points"])}
      </div>
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
    parser = argparse.ArgumentParser(description="Generate latest best NQ strategy report using runner-meta candidate HTML format.")
    parser.add_argument("--trades", default=DEFAULT_TRADES)
    parser.add_argument("--summary", default=DEFAULT_SUMMARY)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--bars-cache", default=".tmp/nq-sum-pos-balanced-aggressive-best-candidate-bars.pkl")
    parser.add_argument("--chunk-size", type=int, default=200_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    trades = _read_csv(args.trades)
    metadata = _strategy_metadata(args.summary)
    bars = _load_bars_for_trades(trades, args.bars_cache, args.chunk_size, args.min_volume)
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT_DIR / output
    write_report(output, trades, bars, metadata)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
