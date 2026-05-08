from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.backtesting.short_patterns import BacktestCosts


NQ_SYMBOL_RE = re.compile(r"^NQ[FGHJKMNQUVXZ]\d{1,2}$")


@dataclass(frozen=True)
class CombinedConfig:
    pd_lookback: int = 100
    pd_discount_threshold: float = 0.05
    pd_exit_bars: int = 1
    lg_lookback: int = 100
    lg_premium_threshold: float = 0.95
    lg_discount_threshold: float = 0.05
    lg_exit_bars: int = 2
    lg_atr_length: int = 14
    lg_atr_threshold: float = 8.0
    use_non_kz_filter: bool = True
    allow_v1_mode: bool = False
    initial_capital: float = 25_000.0


def load_continuous_nq_csv(args: argparse.Namespace) -> pd.DataFrame:
    cache_path = Path(args.cache)
    source = Path(args.data)
    source_stat = source.stat()
    cache_key = {
        "source": str(source.resolve()),
        "size": source_stat.st_size,
        "mtime": int(source_stat.st_mtime),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "min_volume": args.min_volume,
    }
    if cache_path.exists() and not args.refresh_cache:
        cache = pd.read_pickle(cache_path)
        if cache.get("key") == cache_key:
            return cache["bars"]

    start_ts = pd.Timestamp(args.start_date, tz="UTC")
    end_ts = pd.Timestamp(args.end_date, tz="UTC")
    usecols = ["ts_event", "open", "high", "low", "close", "volume", "symbol"]
    chunks: list[pd.DataFrame] = []
    for chunk in pd.read_csv(source, usecols=usecols, chunksize=args.chunk_size):
        symbols = chunk["symbol"].astype(str)
        chunk = chunk[symbols.map(lambda value: bool(NQ_SYMBOL_RE.match(value)))]
        if chunk.empty:
            continue
        chunk["ts"] = pd.to_datetime(chunk["ts_event"], utc=True)
        chunk = chunk[(chunk["ts"] >= start_ts) & (chunk["ts"] < end_ts)]
        if chunk.empty:
            continue
        for column in ["open", "high", "low", "close", "volume"]:
            chunk[column] = pd.to_numeric(chunk[column], errors="coerce")
        chunk = chunk.dropna(subset=["open", "high", "low", "close", "volume"])
        chunk = chunk[(chunk["volume"] >= args.min_volume) & (chunk["open"] > 0) & (chunk["high"] > 0) & (chunk["low"] > 0) & (chunk["close"] > 0)]
        if not chunk.empty:
            chunks.append(chunk[["ts", "symbol", "open", "high", "low", "close", "volume"]])

    if not chunks:
        raise SystemExit(f"No NQ bars found in {source} for {args.start_date}..{args.end_date}")

    bars = pd.concat(chunks, ignore_index=True)
    bars = bars.sort_values(["ts", "volume"], ascending=[True, False]).drop_duplicates("ts", keep="first")
    bars = bars.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    bars = bars.sort_values("ts").reset_index(drop=True)
    bars["minute_of_day"] = bars["ts"].dt.hour * 60 + bars["ts"].dt.minute
    bars["year"] = bars["ts"].dt.year
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle({"key": cache_key, "bars": bars}, cache_path)
    return bars


def atr_wilder(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def add_signals(bars: pd.DataFrame, config: CombinedConfig) -> pd.DataFrame:
    frame = bars.copy()
    high = frame["High"]
    low = frame["Low"]
    close = frame["Close"]

    pd_high = high.rolling(config.pd_lookback, min_periods=config.pd_lookback).max()
    pd_low = low.rolling(config.pd_lookback, min_periods=config.pd_lookback).min()
    pd_range = pd_high - pd_low
    frame["pd_discount_level"] = pd_low + config.pd_discount_threshold * pd_range
    frame["pd_long_signal"] = close <= frame["pd_discount_level"]

    lg_high = high.rolling(config.lg_lookback, min_periods=config.lg_lookback).max()
    lg_low = low.rolling(config.lg_lookback, min_periods=config.lg_lookback).min()
    lg_range = lg_high - lg_low
    frame["lg_premium_level"] = lg_low + config.lg_premium_threshold * lg_range
    frame["lg_discount_level"] = lg_low + config.lg_discount_threshold * lg_range
    frame["atr"] = atr_wilder(high, low, close, config.lg_atr_length)

    minute = frame["minute_of_day"]
    ny_am = ((minute >= 13 * 60 + 30) & (minute <= 16 * 60 + 30))
    ny_pm = ((minute >= 18 * 60 + 30) & (minute < 21 * 60))
    frame["is_kill_zone"] = ny_am | ny_pm
    if config.allow_v1_mode:
        time_filter = frame["is_kill_zone"]
    elif config.use_non_kz_filter:
        time_filter = ~frame["is_kill_zone"]
    else:
        time_filter = pd.Series(True, index=frame.index)

    atr_filter = frame["atr"] > config.lg_atr_threshold
    frame["lg_long_signal"] = (close < frame["lg_discount_level"]) & atr_filter & time_filter
    frame["lg_short_signal"] = (close > frame["lg_premium_level"]) & atr_filter & time_filter
    return frame


def build_trades(frame: pd.DataFrame, config: CombinedConfig, costs: BacktestCosts) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    open_prices = frame["Open"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    timestamps = frame["ts"].to_numpy()
    symbols = frame["symbol"].astype(str).to_numpy()
    pd_long = frame["pd_long_signal"].fillna(False).to_numpy(dtype=bool)
    lg_long = frame["lg_long_signal"].fillna(False).to_numpy(dtype=bool)
    lg_short = frame["lg_short_signal"].fillna(False).to_numpy(dtype=bool)
    kill_zone = frame["is_kill_zone"].fillna(False).to_numpy(dtype=bool)

    next_available_index = 0
    for signal_index in range(len(frame)):
        if signal_index < next_available_index:
            continue
        source = ""
        direction = 0
        hold_bars = 0
        if pd_long[signal_index]:
            source = "PD Long 1m"
            direction = 1
            hold_bars = config.pd_exit_bars
        elif lg_long[signal_index]:
            source = "Lightglow V2 Long"
            direction = 1
            hold_bars = config.lg_exit_bars
        elif lg_short[signal_index]:
            source = "Lightglow V2 Short"
            direction = -1
            hold_bars = config.lg_exit_bars
        if not source:
            continue

        entry_index = signal_index + 1
        exit_index = signal_index + hold_bars
        if entry_index >= len(frame) or exit_index >= len(frame):
            break
        if symbols[signal_index] != symbols[entry_index] or symbols[signal_index] != symbols[exit_index]:
            continue

        entry_price = float(open_prices[entry_index])
        exit_price = float(close_prices[exit_index])
        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points
        rows.append(
            {
                "source": source,
                "entry_ts": timestamps[signal_index],
                "exit_ts": timestamps[exit_index],
                "symbol": symbols[signal_index],
                "direction": "long" if direction > 0 else "short",
                "hold_bars": hold_bars,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_points": gross_points,
                "net_points": net_points,
                "gross_dollars": gross_points * costs.point_value,
                "net_dollars": net_points * costs.point_value,
                "is_kill_zone": bool(kill_zone[signal_index]),
                "entry_index": signal_index,
                "exit_index": exit_index,
            }
        )
        next_available_index = exit_index + 1
    return pd.DataFrame(rows)


def summarize_trades(trades: pd.DataFrame, costs: BacktestCosts) -> dict[str, Any]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "net_dollars": 0.0,
            "gross_points": 0.0,
            "gross_dollars": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_net_points": 0.0,
            "max_drawdown_points": 0.0,
            "max_drawdown_dollars": 0.0,
            "sharpe_per_trade": 0.0,
        }
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    gross = pd.to_numeric(trades["gross_points"], errors="coerce").fillna(0.0)
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    gross_profit = net[net > 0].sum()
    gross_loss = abs(net[net < 0].sum())
    sharpe = (net.mean() / net.std() * np.sqrt(len(net))) if net.std() > 0 else 0.0
    return {
        "trades": int(len(net)),
        "net_points": float(net.sum()),
        "net_dollars": float(net.sum() * costs.point_value),
        "gross_points": float(gross.sum()),
        "gross_dollars": float(gross.sum() * costs.point_value),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else (999.0 if gross_profit > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "avg_net_points": float(net.mean()),
        "max_drawdown_points": float(drawdown.max()),
        "max_drawdown_dollars": float(drawdown.max() * costs.point_value),
        "sharpe_per_trade": float(sharpe),
    }


def source_summary(trades: pd.DataFrame, costs: BacktestCosts) -> pd.DataFrame:
    rows = []
    for source, group in trades.groupby("source", sort=False):
        rows.append({"source": source, **summarize_trades(group, costs)})
    return pd.DataFrame(rows).sort_values("net_points", ascending=False)


def yearly_summary(trades: pd.DataFrame, costs: BacktestCosts) -> pd.DataFrame:
    data = trades.copy()
    data["year"] = pd.to_datetime(data["entry_ts"], utc=True).dt.year
    rows = []
    for year, group in data.groupby("year"):
        rows.append({"year": int(year), **summarize_trades(group, costs)})
    return pd.DataFrame(rows)


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


def html_table(frame: pd.DataFrame, columns: list[str], limit: int | None = None) -> str:
    data = frame.head(limit).copy() if limit else frame.copy()
    if data.empty:
        return "<p>No rows.</p>"
    header = "".join(f"<th>{esc(column)}</th>" for column in columns)
    rows = []
    for _, row in data.iterrows():
        cells = []
        for column in columns:
            value = row[column]
            if "rate" in column and isinstance(value, (float, np.floating)):
                cells.append(f"<td>{float(value):.2%}</td>")
            elif isinstance(value, (float, np.floating)):
                cells.append(f"<td>{float(value):,.4f}</td>")
            elif isinstance(value, (int, np.integer)):
                cells.append(f"<td>{int(value):,}</td>")
            else:
                cells.append(f"<td>{esc(value)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def metric_card(label: str, value: str, detail: str = "") -> str:
    detail_html = f"<span>{esc(detail)}</span>" if detail else ""
    return f"<div class=\"metric\"><strong>{esc(label)}</strong><b>{esc(value)}</b>{detail_html}</div>"


def svg_curve(trades: pd.DataFrame, value_column: str, title: str, y_label: str) -> str:
    if trades.empty:
        return "<p>No curve data available.</p>"
    data = trades.sort_values("entry_ts").copy()
    timestamps = pd.to_datetime(data["entry_ts"], utc=True)
    values = pd.to_numeric(data["net_points"], errors="coerce").fillna(0.0).cumsum()
    if value_column == "drawdown":
        values = values.cummax() - values
    width, height = 1120, 420
    left, right, top, bottom = 76, 30, 46, 58
    plot_width = width - left - right
    plot_height = height - top - bottom
    series = list(zip(timestamps, values))
    stride = max(1, len(series) // 1600)
    sampled = [series[index] for index in range(0, len(series), stride)]
    if sampled[-1] != series[-1]:
        sampled.append(series[-1])
    min_value = min(float(value) for _, value in sampled)
    max_value = max(float(value) for _, value in sampled)
    if min_value == max_value:
        min_value -= 1
        max_value += 1
    padding = max((max_value - min_value) * 0.08, 1.0)
    min_value -= padding
    max_value += padding
    min_ns = timestamps.min().value
    max_ns = timestamps.max().value

    def x_for(timestamp: pd.Timestamp) -> float:
        return left if min_ns == max_ns else left + (timestamp.value - min_ns) / (max_ns - min_ns) * plot_width

    def y_for(value: float) -> float:
        return top + (max_value - value) / (max_value - min_value) * plot_height

    points = " ".join(f"{x_for(ts):.1f},{y_for(float(value)):.1f}" for ts, value in sampled)
    y_ticks = []
    for index in range(5):
        value = min_value + (max_value - min_value) * index / 4
        y = y_for(value)
        y_ticks.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#e2e8f0"/>'
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#475569">{value:,.0f}</text>'
        )
    x_ticks = []
    for index in range(6):
        ratio = index / 5
        tick_ns = int(min_ns + (max_ns - min_ns) * ratio)
        tick_ts = pd.Timestamp(tick_ns, tz="UTC")
        x = x_for(tick_ts)
        x_ticks.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" stroke="#f1f5f9"/>'
            f'<text x="{x:.1f}" y="{top + plot_height + 28}" text-anchor="middle" font-size="12" fill="#475569">{tick_ts:%Y-%m}</text>'
        )
    zero_line = ""
    if min_value < 0 < max_value:
        y = y_for(0.0)
        zero_line = f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#64748b" stroke-dasharray="6 5"/>'
    return f"""
<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
  <rect width="{width}" height="{height}" fill="#ffffff"/>
  {''.join(x_ticks)}
  {''.join(y_ticks)}
  {zero_line}
  <line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#94a3b8"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#94a3b8"/>
  <text x="{left}" y="27" font-size="18" font-weight="700" fill="#0f172a">{esc(title)}</text>
  <text x="22" y="{top + plot_height / 2:.1f}" text-anchor="middle" font-size="13" fill="#334155" transform="rotate(-90 22 {top + plot_height / 2:.1f})">{esc(y_label)}</text>
  <polyline fill="none" stroke="#0f766e" stroke-width="2.4" points="{points}"/>
</svg>
"""


def build_report(
    bars: pd.DataFrame,
    trades: pd.DataFrame,
    source_stats: pd.DataFrame,
    yearly_stats: pd.DataFrame,
    summary: dict[str, Any],
    args: argparse.Namespace,
    config: CombinedConfig,
    costs: BacktestCosts,
) -> str:
    report_css = """
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #111827; background: #f8fafc; }
main { max-width: 1220px; margin: 0 auto; padding: 32px 24px 56px; }
h1 { margin: 0 0 8px; font-size: 32px; letter-spacing: 0; }
h2 { margin: 34px 0 14px; font-size: 21px; }
p { line-height: 1.55; color: #334155; }
.badge { display: inline-flex; padding: 5px 9px; border-radius: 6px; background: #dbeafe; color: #1e40af; font-size: 13px; font-weight: 700; }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 22px 0; }
.metric { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; }
.metric strong { display: block; color: #475569; font-size: 13px; margin-bottom: 8px; }
.metric b { display: block; color: #0f172a; font-size: 23px; }
.metric span { display: block; color: #64748b; font-size: 12px; margin-top: 5px; }
section { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-top: 18px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 9px 10px; border-bottom: 1px solid #e5e7eb; text-align: right; white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
th { color: #475569; background: #f8fafc; font-weight: 700; }
code { background: #eef2f7; padding: 2px 5px; border-radius: 5px; }
.chart { overflow-x: auto; }
.note { border-left: 4px solid #0f766e; padding-left: 14px; }
"""
    columns_source = [
        "source",
        "trades",
        "net_points",
        "net_dollars",
        "profit_factor",
        "win_rate",
        "avg_net_points",
        "max_drawdown_points",
    ]
    columns_year = ["year", "trades", "net_points", "net_dollars", "profit_factor", "win_rate", "max_drawdown_points"]
    recent_columns = [
        "source",
        "entry_ts",
        "exit_ts",
        "symbol",
        "direction",
        "entry_price",
        "exit_price",
        "net_points",
        "net_dollars",
    ]
    recent = trades.sort_values("entry_ts", ascending=False).head(50).sort_values("entry_ts")
    config_json = html.escape(json.dumps(config.__dict__, indent=2, ensure_ascii=False))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lightglow + Premium/Discount Combined 1m Backtest</title>
  <style>{report_css}</style>
</head>
<body>
<main>
  <span class="badge">Databento NQ 1m · 2010-2026</span>
  <h1>Lightglow V2 + Premium/Discount Long 整合策略回测</h1>
  <p>数据源：<code>{esc(args.data)}</code>。连续合约构造：每个 UTC 分钟保留 NQ 合约中成交量最高的一条 OHLCV。周期：{bars["ts"].min():%Y-%m-%d %H:%M UTC} 到 {bars["ts"].max():%Y-%m-%d %H:%M UTC}。</p>
  <p class="note">执行口径：信号在当前 1 分钟 K 线收盘确认，下一根开盘入场，按各信号的持仓根数在对应 K 线收盘离场；同一时刻最多一仓，P/D Long 与 Lightglow Long 同时触发时优先 P/D Long。</p>

  <div class="metrics">
    {metric_card("Bars", fmt(len(bars), 0), "continuous NQ 1m")}
    {metric_card("Trades", fmt(summary["trades"], 0), "non-overlapping")}
    {metric_card("Net Points", fmt(summary["net_points"], 2), f'${summary["net_dollars"]:,.0f}')}
    {metric_card("Profit Factor", fmt(summary["profit_factor"], 2), f'Win rate {summary["win_rate"]:.2%}')}
    {metric_card("Avg Net / Trade", fmt(summary["avg_net_points"], 4), "points after costs")}
    {metric_card("Max Drawdown", fmt(summary["max_drawdown_points"], 2), f'${summary["max_drawdown_dollars"]:,.0f}')}
  </div>

  <section>
    <h2>Equity Curve</h2>
    <div class="chart">{svg_curve(trades, "net_points", "Cumulative Net Points", "Net points")}</div>
  </section>

  <section>
    <h2>Drawdown</h2>
    <div class="chart">{svg_curve(trades, "drawdown", "Drawdown Points", "Drawdown points")}</div>
  </section>

  <section>
    <h2>Signal Source Breakdown</h2>
    {html_table(source_stats, columns_source)}
  </section>

  <section>
    <h2>Yearly Results</h2>
    {html_table(yearly_stats, columns_year)}
  </section>

  <section>
    <h2>Recent Trades Sample</h2>
    {html_table(recent, recent_columns)}
  </section>

  <section>
    <h2>Backtest Settings</h2>
    <p>Cost model: point value ${costs.point_value:g}, tick size {costs.tick_size:g}, slippage {costs.slippage_ticks_per_side:g} ticks per side, round-trip commission ${costs.commission_per_contract:g} per contract. Round-trip cost: {costs.round_trip_cost_points:.4f} points.</p>
    <pre><code>{config_json}</code></pre>
  </section>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest combined Lightglow V2 + P/D Long Pine strategy on 1m Databento NQ bars.")
    parser.add_argument("--data", default="data/raw/databento/glbx-mdp3-20100606-20260427.ohlcv-1m.csv")
    parser.add_argument("--start-date", default="2010-01-01")
    parser.add_argument("--end-date", default="2027-01-01")
    parser.add_argument("--min-volume", type=int, default=1)
    parser.add_argument("--chunk-size", type=int, default=1_000_000)
    parser.add_argument("--cache", default=".tmp/lightglow-pd-combined-1m-bars.pkl")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--trades-output", default="reports/lightglow_pd_combined_1min_trades.csv")
    parser.add_argument("--summary-output", default="reports/lightglow_pd_combined_1min_summary.json")
    parser.add_argument("--source-output", default="reports/lightglow_pd_combined_1min_source_summary.csv")
    parser.add_argument("--yearly-output", default="reports/lightglow_pd_combined_1min_yearly.csv")
    parser.add_argument("--report", default="reports/lightglow_pd_combined_1min_backtest.html")
    args = parser.parse_args()

    config = CombinedConfig()
    costs = BacktestCosts(point_value=20.0, tick_size=0.25, slippage_ticks_per_side=2.0, commission_per_contract=10.0)
    bars = load_continuous_nq_csv(args)
    frame = add_signals(bars, config)
    trades = build_trades(frame, config, costs)
    if trades.empty:
        raise SystemExit("No trades generated.")

    summary = summarize_trades(trades, costs)
    summary.update(
        {
            "period_start": str(bars["ts"].min()),
            "period_end": str(bars["ts"].max()),
            "bars": int(len(bars)),
            "data": args.data,
            "costs": costs.__dict__,
            "config": config.__dict__,
        }
    )
    source_stats = source_summary(trades, costs)
    yearly_stats = yearly_summary(trades, costs)

    for path_text in [args.trades_output, args.summary_output, args.source_output, args.yearly_output, args.report]:
        Path(path_text).parent.mkdir(parents=True, exist_ok=True)

    trades.to_csv(args.trades_output, index=False)
    source_stats.to_csv(args.source_output, index=False)
    yearly_stats.to_csv(args.yearly_output, index=False)
    Path(args.summary_output).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    Path(args.report).write_text(build_report(bars, trades, source_stats, yearly_stats, summary, args, config, costs), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote {args.report}")


if __name__ == "__main__":
    main()
