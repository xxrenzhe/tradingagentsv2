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


DEFAULT_BA_TRADES = "reports/NQ-pine-5y-runner-meta-balanced-aggressive-sizing-trades.csv"
DEFAULT_OVERLAY_TRADES = "reports/NQ-pine-5y-ba-no-trade-live-candidates-recommended-overlay-trades.csv"
DEFAULT_SUMMARY = "reports/NQ-pine-5y-ba-no-trade-live-candidates-summary.csv"
DEFAULT_COST_STRESS = "reports/NQ-pine-5y-ba-no-trade-live-candidates-recommended-cost-stress.csv"
DEFAULT_VARIANTS = "reports/NQ-pine-5y-ba-no-trade-live-candidates-deployment-variants.csv"
DEFAULT_FEATURES = "reports/NQ-pine-5y-ba-no-trade-live-candidates-market-features.csv"
DEFAULT_OUTPUT = "reports/NQ-pine-5y-ba-no-trade-best-combo-candidate.html"
DEFAULT_FULL_TRADES = "reports/NQ-pine-5y-ba-no-trade-best-combo-full-trades.csv"


def _resolve(path: str) -> Path:
    resolved = Path(path)
    return resolved if resolved.is_absolute() else ROOT_DIR / resolved


def _fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _pct(value: float) -> str:
    return f"{value:.1%}"


def _normalise_ba_trades(path: Path) -> pd.DataFrame:
    trades = pd.read_csv(path)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    trades["net_points"] = pd.to_numeric(trades["sized_net_points"], errors="coerce")
    trades["net_dollars"] = pd.to_numeric(trades["sized_net_dollars"], errors="coerce")
    trades["source_pool"] = "ba_overlay"
    trades["candidate_key"] = "BA::runner_meta_balanced_aggressive"
    trades["candidate"] = trades.get("component_strategy", "runner_meta_balanced_aggressive").astype(str)
    trades["overlay_family"] = "BA main"
    trades["position_scale"] = pd.to_numeric(trades.get("position_scale", 1.0), errors="coerce").fillna(1.0)
    trades["month"] = trades["entry_ts"].dt.strftime("%Y-%m")
    trades["year"] = trades["entry_ts"].dt.year
    return trades


def _normalise_overlay_trades(path: Path) -> pd.DataFrame:
    trades = pd.read_csv(path)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    trades["net_points"] = pd.to_numeric(trades["net_points"], errors="coerce")
    if "net_dollars" not in trades.columns:
        trades["net_dollars"] = trades["net_points"] * 20.0
    trades["candidate"] = trades["candidate"].astype(str)
    trades["candidate_key"] = trades["candidate_key"].astype(str)
    trades["source_pool"] = trades["source_pool"].astype(str)
    trades["overlay_family"] = trades["source_pool"].map(
        {
            "lightglow": "BA no-trade overlay: Lightglow late OB",
            "bar_directional": "BA no-trade overlay: US-late breakout retest",
        }
    ).fillna("BA no-trade overlay")
    trades["signal_family"] = trades.get("signal", trades["candidate"]).fillna(trades["candidate"]).astype(str)
    trades["session"] = trades.get("session", trades["source_pool"]).fillna(trades["source_pool"]).astype(str)
    trades["bars_held"] = pd.to_numeric(trades.get("exit_index", 0), errors="coerce") - pd.to_numeric(
        trades.get("entry_index", 0), errors="coerce"
    )
    trades["position_scale"] = 1.0
    trades["month"] = trades["entry_ts"].dt.strftime("%Y-%m")
    trades["year"] = trades["entry_ts"].dt.year
    return trades


def build_full_combo(ba_path: Path, overlay_path: Path) -> pd.DataFrame:
    ba = _normalise_ba_trades(ba_path)
    overlay = _normalise_overlay_trades(overlay_path)
    preferred_columns = [
        "trade_id",
        "entry_ts",
        "exit_ts",
        "symbol",
        "source_pool",
        "overlay_family",
        "candidate_key",
        "candidate",
        "signal_family",
        "session",
        "direction",
        "entry_price",
        "exit_price",
        "exit_reason",
        "bars_held",
        "position_scale",
        "gross_points",
        "net_points",
        "net_dollars",
        "entry_index",
        "exit_index",
        "month",
        "year",
    ]
    all_columns = list(dict.fromkeys(preferred_columns + ba.columns.tolist() + overlay.columns.tolist()))
    combo = pd.concat([ba.reindex(columns=all_columns), overlay.reindex(columns=all_columns)], ignore_index=True, sort=False)
    combo = combo.dropna(subset=["entry_ts", "exit_ts", "entry_price", "exit_price", "direction", "net_points"])
    combo = combo.sort_values("entry_ts").reset_index(drop=True)
    combo = _ensure_trade_ids(combo, "ba_no_trade_best_combo")
    combo["entry_date"] = combo["entry_ts"].dt.date.astype(str)
    combo["equity_points"] = combo["net_points"].astype(float).cumsum()
    combo["drawdown_points"] = combo["equity_points"].cummax() - combo["equity_points"]
    return combo


def _metric_cards(cards: list[tuple[str, str]]) -> str:
    return "".join(
        f"<div class=\"metric\"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>"
        for label, value in cards
    )


def _read_optional(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def write_report(
    output: Path,
    full_trades_path: Path,
    trades: pd.DataFrame,
    bars: pd.DataFrame,
    summary: pd.DataFrame,
    cost_stress: pd.DataFrame,
    variants: pd.DataFrame,
    features: pd.DataFrame,
) -> None:
    title = "NQ BA No-Trade Best Combo Candidate Report"
    summary_stats = _summary(trades)
    period = _period_summary(trades)
    yearly = _period_breakdown(trades, "year")
    monthly = _period_breakdown(trades, "month")
    daily = _group_summary(trades, ["entry_date"])
    source = _group_summary(trades, ["source_pool"])
    family = _group_summary(trades, ["overlay_family"])
    candidate = _group_summary(trades, ["candidate_key"])
    session = _group_summary(trades, ["session"])
    exits = _group_summary(trades, ["exit_reason"])
    direction = _group_summary(trades, ["direction"])
    replay_trades = _select_replay_trades(trades, top_n=10, bottom_n=10)
    kline_chart = _trade_kline_svg(bars, replay_trades, replay_title="Only Top10 winning trades and Bottom10 losing trades")
    equity_values = [0.0, *trades["equity_points"].astype(float).tolist()]
    drawdown_values = [0.0, *(-trades["drawdown_points"].astype(float)).tolist()]

    cards = _metric_cards(
        [
            ("Trades", _fmt(int(summary_stats["trades"]))),
            ("Net Points", _fmt(float(summary_stats["net_points"]))),
            ("Profit Factor", _fmt(float(summary_stats["profit_factor"]))),
            ("Win Rate", _pct(float(summary_stats["win_rate"]))),
            ("Avg / Trade", _fmt(float(summary_stats["avg_points"]))),
            ("Max DD", _fmt(float(summary_stats["max_drawdown_points"]))),
            ("Worst Trade", _fmt(float(summary_stats["worst_trade_points"]))),
            ("Best Trade", _fmt(float(summary_stats["best_trade_points"]))),
        ]
    )
    period_cards = _metric_cards(
        [
            ("First Entry", str(period["first_entry"])),
            ("Last Entry", str(period["last_entry"])),
            ("Last Exit", str(period["last_exit"])),
            ("Calendar Days", _fmt(int(period["calendar_days"]))),
            ("Calendar Years", _fmt(float(period["calendar_years"]))),
            ("Active Months", _fmt(int(period["active_months"]))),
            ("First Month", str(period["first_month"])),
            ("Last Month", str(period["last_month"])),
        ]
    )
    summary_cards = ""
    if not summary.empty:
        row = summary.iloc[0]
        summary_cards = _metric_cards(
            [
                ("BA Net / PF", f"{float(row['ba_net_points']):,.2f} / {float(row['ba_profit_factor']):.3f}"),
                (
                    "Recommended Overlay",
                    f"{float(row['recommended_overlay_net_points']):,.2f} / PF {float(row['recommended_overlay_profit_factor']):.3f}",
                ),
                (
                    "Recommended Combo",
                    f"{float(row['recommended_combo_net_points']):,.2f} / PF {float(row['recommended_combo_profit_factor']):.3f}",
                ),
                ("BA No-Trade Months", _fmt(int(row["ba_no_trade_months"]))),
            ]
        )

    trade_display = trades.copy()
    trade_display["entry_ts"] = trade_display["entry_ts"].dt.strftime("%Y-%m-%d %H:%M UTC")
    trade_display["exit_ts"] = trade_display["exit_ts"].dt.strftime("%Y-%m-%d %H:%M UTC")
    trade_columns = [
        "trade_id",
        "entry_ts",
        "exit_ts",
        "source_pool",
        "overlay_family",
        "candidate_key",
        "session",
        "direction",
        "entry_price",
        "exit_price",
        "exit_reason",
        "bars_held",
        "position_scale",
        "net_points",
        "equity_points",
    ]
    trade_columns = [column for column in trade_columns if column in trade_display.columns]

    cost_columns = [
        "overlay_scale",
        "extra_cost_points",
        "combo_net_points",
        "combo_profit_factor",
        "combo_max_drawdown_points",
        "overlay_net_points",
        "overlay_profit_factor",
    ]
    variant_columns = [
        "variant",
        "overlay_months",
        "overlay_trades",
        "overlay_net_points",
        "overlay_profit_factor",
        "overlay_max_drawdown_points",
        "combo_trades",
        "combo_net_points",
        "combo_profit_factor",
        "combo_max_drawdown_points",
    ]
    feature_columns = [
        "month",
        "recommended_active",
        "recommended_overlay_net",
        "month_net_points",
        "trend_efficiency",
        "realized_vol_per_bar",
        "avg_range_points",
        "p90_range_points",
        "us_late_abs_move",
        "rth_abs_move",
        "volume_z_p90",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg:#07111f; --panel:#0d1b2e; --ink:#e5edf8; --muted:#94a3b8; --line:#20334d;
      --cyan:#22d3ee; --green:#34d399; --amber:#fbbf24; --red:#fb7185;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:radial-gradient(circle at 18% 0%, #123056 0, transparent 34%), linear-gradient(135deg, #06101d, #0a1526 55%, #07111f); font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    header {{ padding:42px 28px 26px; border-bottom:1px solid var(--line); }}
    main {{ max-width:1240px; margin:0 auto; padding:24px; }}
    h1 {{ max-width:1240px; margin:0 auto 12px; font-size:clamp(30px, 4vw, 54px); line-height:1; letter-spacing:-0.045em; }}
    .subtitle {{ max-width:1240px; margin:0 auto; color:var(--muted); font-size:16px; line-height:1.6; }}
    .tag {{ display:inline-flex; align-items:center; gap:8px; padding:7px 11px; border:1px solid #1e7490; border-radius:999px; color:#a5f3fc; background:rgba(34,211,238,.08); margin-bottom:16px; }}
    section {{ margin:18px 0; padding:20px; border:1px solid var(--line); background:linear-gradient(180deg, rgba(17,31,53,.92), rgba(13,27,46,.92)); border-radius:22px; box-shadow:0 22px 60px rgba(0,0,0,.22); }}
    h2 {{ margin:0 0 14px; font-size:22px; letter-spacing:-0.02em; }}
    .metrics {{ display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:14px; }}
    .metric {{ padding:16px; border:1px solid #23415f; border-radius:18px; background:rgba(5,12,24,.58); }}
    .metric span {{ display:block; color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
    .metric strong {{ display:block; margin-top:8px; font-size:24px; letter-spacing:-0.03em; }}
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
    <div class="tag">NQ 1m · BA Main + No-Trade Feature Overlay · Candidate</div>
    <h1>{html.escape(title)}</h1>
    <p class="subtitle">组合逻辑：保留 BA runner-meta balanced-aggressive 主策略；仅在 BA 空窗月份启用因果筛选后的补充腿。推荐实盘候选剔除了 ICT 腿，只保留 <code>Lightglow late-session internal OB break</code> 和 <code>US-late long breakout-retest</code>。完整交易表：<code>{html.escape(str(full_trades_path.relative_to(ROOT_DIR)))}</code></p>
  </header>
  <main>
    <section>
      <h2>Performance Snapshot</h2>
      <div class="metrics">{cards}</div>
      <p class="note">所有指标使用 <code>net_points</code>，成本已内嵌。该报告不是基于月份过滤；月份只用于 walk-forward 空窗启用验证和分布展示。</p>
    </section>
    <section>
      <h2>BA vs Recommended Overlay</h2>
      <div class="metrics">{summary_cards}</div>
      <p class="note">推荐版为 <code>causal_no_ict</code>，因为 ICT 在静态全周期表现好，但在逐月因果启用后的真实贡献为负。</p>
    </section>
    <section>
      <h2>Data Coverage Period</h2>
      <div class="metrics">{period_cards}</div>
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
      <p class="note">为避免文件过大，仅展示 Top10 盈利和 Bottom10 亏损交易的逐笔 K 线回放。完整 976 笔交易保留在 Trade Log 和 CSV 中。</p>
      {kline_chart}
    </section>
    <section class="grid2">
      <div>
        <h2>Deployment Variant Comparison</h2>
        {_table(variants, variant_columns) if not variants.empty else "<p class='note'>No variant data.</p>"}
      </div>
      <div>
        <h2>Cost Stress</h2>
        {_table(cost_stress, cost_columns) if not cost_stress.empty else "<p class='note'>No cost-stress data.</p>"}
      </div>
    </section>
    <section class="grid2">
      <div>
        <h2>Breakdown By Source</h2>
        {_table(source, ["source_pool", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points"])}
      </div>
      <div>
        <h2>Breakdown By Direction</h2>
        {_table(direction, ["direction", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points"])}
      </div>
    </section>
    <section>
      <h2>Breakdown By Candidate</h2>
      {_table(candidate, ["candidate_key", "trades", "net_points", "profit_factor", "win_rate", "avg_points", "max_drawdown_points", "worst_trade_points"])}
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
      <h2>BA No-Trade Month Market Features</h2>
      {_table(features, feature_columns) if not features.empty else "<p class='note'>No market feature diagnostics.</p>"}
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
    parser = argparse.ArgumentParser(description="Generate HTML report for the current BA no-trade best combo candidate.")
    parser.add_argument("--ba-trades", default=DEFAULT_BA_TRADES)
    parser.add_argument("--overlay-trades", default=DEFAULT_OVERLAY_TRADES)
    parser.add_argument("--summary", default=DEFAULT_SUMMARY)
    parser.add_argument("--cost-stress", default=DEFAULT_COST_STRESS)
    parser.add_argument("--variants", default=DEFAULT_VARIANTS)
    parser.add_argument("--features", default=DEFAULT_FEATURES)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--full-trades-output", default=DEFAULT_FULL_TRADES)
    parser.add_argument("--bars-cache", default=".tmp/nq-ba-no-trade-best-combo-bars.pkl")
    parser.add_argument("--chunk-size", type=int, default=200_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    combo = build_full_combo(_resolve(args.ba_trades), _resolve(args.overlay_trades))
    full_trades_output = _resolve(args.full_trades_output)
    full_trades_output.parent.mkdir(parents=True, exist_ok=True)
    combo.to_csv(full_trades_output, index=False)
    bars = _load_bars_for_trades(combo, args.bars_cache, args.chunk_size, args.min_volume)
    write_report(
        _resolve(args.output),
        full_trades_output,
        combo,
        bars,
        _read_optional(_resolve(args.summary)),
        _read_optional(_resolve(args.cost_stress)),
        _read_optional(_resolve(args.variants)),
        _read_optional(_resolve(args.features)),
    )
    print(_resolve(args.output))
    print(full_trades_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
