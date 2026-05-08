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


NQ_SYMBOL_RE = re.compile(r"^NQ[FGHJKMNQUVXZ]\d{1,2}$")


@dataclass(frozen=True)
class LightglowConfig:
    lookback: int = 100
    premium_threshold: float = 0.95
    discount_threshold: float = 0.05
    exit_bars: int = 2
    atr_length: int = 14
    atr_threshold: float = 8.0
    use_non_kz_filter: bool = True
    allow_v1_mode: bool = False
    initial_capital: float = 25_000.0
    point_value: float = 20.0
    tick_size: float = 0.25
    slippage_ticks: float = 2.0
    commission_cash_per_contract_per_order: float = 5.0

    @property
    def round_trip_cost_dollars(self) -> float:
        return self.slippage_ticks * self.tick_size * 2.0 * self.point_value + self.commission_cash_per_contract_per_order * 2.0


@dataclass(frozen=True)
class PDLongConfig:
    lookback: int = 100
    discount_threshold: float = 0.05
    exit_bars: int = 1
    initial_capital: float = 25_000.0
    point_value: float = 20.0
    tick_size: float = 0.25
    slippage_ticks: float = 2.0
    commission_cash_per_contract_per_order: float = 5.0

    @property
    def round_trip_cost_dollars(self) -> float:
        return self.slippage_ticks * self.tick_size * 2.0 * self.point_value + self.commission_cash_per_contract_per_order * 2.0


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
        chunk = chunk[
            (chunk["volume"] >= args.min_volume)
            & (chunk["open"] > 0)
            & (chunk["high"] > 0)
            & (chunk["low"] > 0)
            & (chunk["close"] > 0)
        ]
        if not chunk.empty:
            chunks.append(chunk[["ts", "symbol", "open", "high", "low", "close", "volume"]])

    if not chunks:
        raise SystemExit(f"No NQ bars found in {source} for {args.start_date}..{args.end_date}")

    bars = pd.concat(chunks, ignore_index=True)
    bars = bars.sort_values(["ts", "volume"], ascending=[True, False]).drop_duplicates("ts", keep="first")
    bars = bars.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    bars = bars.sort_values("ts").reset_index(drop=True)
    bars["minute_of_day"] = bars["ts"].dt.hour * 60 + bars["ts"].dt.minute
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


def add_strategy_signals(bars: pd.DataFrame, lightglow: LightglowConfig, pdlong: PDLongConfig) -> pd.DataFrame:
    frame = bars.copy()
    high = frame["High"]
    low = frame["Low"]
    close = frame["Close"]

    pd_high = high.rolling(pdlong.lookback, min_periods=1).max()
    pd_low = low.rolling(pdlong.lookback, min_periods=1).min()
    frame["pd_discount_level"] = pd_low + pdlong.discount_threshold * (pd_high - pd_low)
    frame["pd_long_signal"] = close <= frame["pd_discount_level"]

    lg_high = high.rolling(lightglow.lookback, min_periods=1).max()
    lg_low = low.rolling(lightglow.lookback, min_periods=1).min()
    lg_range = lg_high - lg_low
    frame["lg_premium_level"] = lg_low + lightglow.premium_threshold * lg_range
    frame["lg_discount_level"] = lg_low + lightglow.discount_threshold * lg_range
    frame["lg_atr"] = atr_wilder(high, low, close, lightglow.atr_length)

    minute = frame["minute_of_day"]
    ny_am = ((minute >= 13 * 60 + 30) & (minute <= 16 * 60 + 30))
    ny_pm = ((minute >= 18 * 60 + 30) & (minute < 21 * 60))
    frame["is_kill_zone"] = ny_am | ny_pm
    if lightglow.allow_v1_mode:
        time_filter = frame["is_kill_zone"]
    elif lightglow.use_non_kz_filter:
        time_filter = ~frame["is_kill_zone"]
    else:
        time_filter = pd.Series(True, index=frame.index)

    atr_filter = frame["lg_atr"] > lightglow.atr_threshold
    frame["lg_long_signal"] = (close < frame["lg_discount_level"]) & atr_filter & time_filter
    frame["lg_short_signal"] = (close > frame["lg_premium_level"]) & atr_filter & time_filter
    return frame


def build_lightglow_trades(frame: pd.DataFrame, config: LightglowConfig) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    open_prices = frame["Open"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    timestamps = frame["ts"].to_numpy()
    symbols = frame["symbol"].astype(str).to_numpy()
    long_signal = frame["lg_long_signal"].fillna(False).to_numpy(dtype=bool)
    short_signal = frame["lg_short_signal"].fillna(False).to_numpy(dtype=bool)
    kill_zone = frame["is_kill_zone"].fillna(False).to_numpy(dtype=bool)

    equity = config.initial_capital
    next_available_index = 0
    for signal_index in range(len(frame)):
        if signal_index < next_available_index:
            continue
        direction = 1 if long_signal[signal_index] else (-1 if short_signal[signal_index] else 0)
        if direction == 0:
            continue
        entry_index = signal_index + 1
        exit_index = signal_index + config.exit_bars
        if entry_index >= len(frame) or exit_index >= len(frame):
            break
        if symbols[signal_index] != symbols[entry_index] or symbols[signal_index] != symbols[exit_index]:
            continue
        entry_price = float(open_prices[entry_index])
        exit_price = float(close_prices[exit_index])
        gross_points = (exit_price - entry_price) * direction
        gross_dollars = gross_points * config.point_value
        net_dollars = gross_dollars - config.round_trip_cost_dollars
        equity_before = equity
        equity = equity + net_dollars
        rows.append(
            {
                "strategy": "Lightglow V2 Non-Kill Zone",
                "entry_ts": timestamps[signal_index],
                "exit_ts": timestamps[exit_index],
                "symbol": symbols[signal_index],
                "direction": "long" if direction > 0 else "short",
                "hold_bars": config.exit_bars,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_points": gross_points,
                "net_points": net_dollars / config.point_value,
                "gross_dollars": gross_dollars,
                "net_dollars": net_dollars,
                "net_return": net_dollars / equity_before if equity_before else 0.0,
                "equity_before": equity_before,
                "equity_after": equity,
                "is_kill_zone": bool(kill_zone[signal_index]),
                "entry_index": signal_index,
                "exit_index": exit_index,
            }
        )
        next_available_index = exit_index + 1
    return pd.DataFrame(rows)


def build_pdlong_trades(frame: pd.DataFrame, config: PDLongConfig) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    open_prices = frame["Open"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    timestamps = frame["ts"].to_numpy()
    symbols = frame["symbol"].astype(str).to_numpy()
    signal = frame["pd_long_signal"].fillna(False).to_numpy(dtype=bool)

    equity = config.initial_capital
    next_available_index = 0
    for signal_index in range(len(frame)):
        if signal_index < next_available_index:
            continue
        if not signal[signal_index]:
            continue
        entry_index = signal_index + 1
        exit_index = signal_index + config.exit_bars
        if entry_index >= len(frame) or exit_index >= len(frame):
            break
        if symbols[signal_index] != symbols[entry_index] or symbols[signal_index] != symbols[exit_index]:
            continue
        entry_price = float(open_prices[entry_index])
        exit_price = float(close_prices[exit_index])
        gross_points = exit_price - entry_price
        gross_dollars = gross_points * config.point_value
        net_dollars = gross_dollars - config.round_trip_cost_dollars
        equity_before = equity
        equity = equity + net_dollars
        rows.append(
            {
                "strategy": "Premium/Discount Long 1m",
                "entry_ts": timestamps[signal_index],
                "exit_ts": timestamps[exit_index],
                "symbol": symbols[signal_index],
                "direction": "long",
                "hold_bars": config.exit_bars,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_points": gross_points,
                "net_points": net_dollars / config.point_value,
                "gross_dollars": gross_dollars,
                "net_dollars": net_dollars,
                "net_return": net_dollars / equity_before if equity_before else 0.0,
                "equity_before": equity_before,
                "equity_after": equity,
                "is_kill_zone": False,
                "entry_index": signal_index,
                "exit_index": exit_index,
            }
        )
        next_available_index = exit_index + 1
    return pd.DataFrame(rows)


def summarize(trades: pd.DataFrame, initial_capital: float) -> dict[str, Any]:
    if trades.empty:
        return {
            "trades": 0,
            "initial_capital": initial_capital,
            "final_equity": initial_capital,
            "net_profit": 0.0,
            "total_return": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_net_dollars": 0.0,
            "avg_net_points": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
        }
    net = pd.to_numeric(trades["net_dollars"], errors="coerce").fillna(0.0)
    equity = pd.to_numeric(trades["equity_after"], errors="coerce").fillna(initial_capital)
    equity_with_start = pd.concat([pd.Series([initial_capital]), equity], ignore_index=True)
    drawdown = equity_with_start.cummax() - equity_with_start
    drawdown_pct = drawdown / equity_with_start.cummax().replace(0, pd.NA)
    gross_profit = net[net > 0].sum()
    gross_loss = abs(net[net < 0].sum())
    final_equity = float(equity.iloc[-1])
    return {
        "trades": int(len(trades)),
        "initial_capital": float(initial_capital),
        "final_equity": final_equity,
        "net_profit": float(final_equity - initial_capital),
        "total_return": float(final_equity / initial_capital - 1.0),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else (999.0 if gross_profit > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "avg_net_dollars": float(net.mean()),
        "avg_net_points": float(pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0).mean()),
        "max_drawdown": float(drawdown.max()),
        "max_drawdown_pct": float(drawdown_pct.max()) if not drawdown_pct.dropna().empty else 0.0,
    }


def period_summary(trades: pd.DataFrame, initial_capital: float, freq: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    data = trades.copy()
    data["period"] = pd.to_datetime(data["entry_ts"], utc=True).dt.tz_convert(None).dt.to_period(freq).astype(str)
    rows = []
    for period, group in data.groupby("period", sort=True):
        start_equity = float(group["equity_before"].iloc[0])
        end_equity = float(group["equity_after"].iloc[-1])
        net = pd.to_numeric(group["net_dollars"], errors="coerce").fillna(0.0)
        net_profit = float(net.sum())
        gross_profit = net[net > 0].sum()
        gross_loss = abs(net[net < 0].sum())
        equity = pd.concat([pd.Series([start_equity]), group["equity_after"].reset_index(drop=True)], ignore_index=True)
        drawdown = equity.cummax() - equity
        rows.append(
            {
                "period": period,
                "trades": int(len(group)),
                "start_equity": start_equity,
                "end_equity": end_equity,
                "net_profit": net_profit,
                "return": net_profit / initial_capital if initial_capital else 0.0,
                "profit_factor": float(gross_profit / gross_loss) if gross_loss else (999.0 if gross_profit > 0 else 0.0),
                "win_rate": float((net > 0).mean()),
                "max_drawdown": float(drawdown.max()),
            }
        )
    return pd.DataFrame(rows)


def esc(value: object) -> str:
    return html.escape(str(value))


def fmt_money(value: float) -> str:
    return f"${value:,.2f}"


def fmt_pct(value: float) -> str:
    return f"{value:.2%}"


def fmt_num(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


def metric_card(label: str, value: str, detail: str = "") -> str:
    detail_html = f"<span>{esc(detail)}</span>" if detail else ""
    return f'<div class="metric"><strong>{esc(label)}</strong><b>{esc(value)}</b>{detail_html}</div>'


def html_table(frame: pd.DataFrame, columns: list[str], *, limit: int | None = None) -> str:
    data = frame.head(limit).copy() if limit else frame.copy()
    if data.empty:
        return "<p>No rows.</p>"
    header = "".join(f"<th>{esc(column)}</th>" for column in columns)
    rows = []
    for _, row in data.iterrows():
        cells = []
        for column in columns:
            value = row[column]
            if column in {"return", "win_rate", "total_return", "max_drawdown_pct", "avg_trade_return"}:
                cells.append(f"<td>{fmt_pct(float(value))}</td>")
            elif column in {"start_equity", "end_equity", "net_profit", "final_equity", "max_drawdown"}:
                cells.append(f"<td>{fmt_money(float(value))}</td>")
            elif column in {"avg_net_dollars"}:
                cells.append(f"<td>{fmt_money(float(value))}</td>")
            elif isinstance(value, (float, np.floating)):
                cells.append(f"<td>{float(value):,.4f}</td>")
            elif isinstance(value, (int, np.integer)):
                cells.append(f"<td>{int(value):,}</td>")
            else:
                cells.append(f"<td>{esc(value)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def equity_series(trades: pd.DataFrame, initial_capital: float) -> list[tuple[pd.Timestamp, float]]:
    if trades.empty:
        return []
    timestamps = pd.to_datetime(trades["exit_ts"], utc=True)
    values = pd.to_numeric(trades["equity_after"], errors="coerce").fillna(initial_capital)
    start_ts = pd.to_datetime(trades["entry_ts"], utc=True).min()
    return [(start_ts, initial_capital), *zip(timestamps, values)]


def svg_line_chart(series_map: dict[str, list[tuple[pd.Timestamp, float]]], title: str, y_label: str, *, normalize: bool = False) -> str:
    if not series_map:
        return "<p>No curve data.</p>"
    transformed: dict[str, list[tuple[pd.Timestamp, float]]] = {}
    for name, series in series_map.items():
        if not series:
            continue
        start_value = float(series[0][1])
        if normalize:
            transformed[name] = [(ts, value / start_value - 1.0) for ts, value in series]
        else:
            transformed[name] = [(ts, float(value)) for ts, value in series]
    if not transformed:
        return "<p>No curve data.</p>"

    width, height = 1180, 460
    left, right, top, bottom = 86, 38, 50, 62
    plot_width = width - left - right
    plot_height = height - top - bottom
    values = [value for series in transformed.values() for _, value in series]
    timestamps = [ts for series in transformed.values() for ts, _ in series]
    min_value, max_value = min(values), max(values)
    if min_value == max_value:
        min_value -= 1
        max_value += 1
    padding = max((max_value - min_value) * 0.08, 0.01 if normalize else 1.0)
    min_value -= padding
    max_value += padding
    min_ns, max_ns = min(timestamps).value, max(timestamps).value

    def x_for(timestamp: pd.Timestamp) -> float:
        return left if min_ns == max_ns else left + (timestamp.value - min_ns) / (max_ns - min_ns) * plot_width

    def y_for(value: float) -> float:
        return top + (max_value - value) / (max_value - min_value) * plot_height

    y_ticks = []
    for index in range(6):
        value = min_value + (max_value - min_value) * index / 5
        y = y_for(value)
        label = fmt_pct(value) if normalize else f"{value:,.0f}"
        y_ticks.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#e2e8f0"/>'
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#475569">{label}</text>'
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
    palette = ["#0f766e", "#2563eb", "#dc2626", "#9333ea"]
    lines = []
    legend = []
    for index, (name, series) in enumerate(transformed.items()):
        stride = max(1, len(series) // 1600)
        sampled = [series[i] for i in range(0, len(series), stride)]
        if sampled[-1] != series[-1]:
            sampled.append(series[-1])
        color = palette[index % len(palette)]
        points = " ".join(f"{x_for(ts):.1f},{y_for(value):.1f}" for ts, value in sampled)
        lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.4" points="{points}"/>')
        legend.append(f'<span><i style="background:{color}"></i>{esc(name)}</span>')
    return f"""
<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
  <rect width="{width}" height="{height}" fill="#ffffff"/>
  <style>.legend span{{margin-right:18px;font-size:13px;color:#334155}}.legend i{{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:6px;vertical-align:-1px}}</style>
  {''.join(x_ticks)}
  {''.join(y_ticks)}
  {zero_line}
  <line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#94a3b8"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#94a3b8"/>
  <text x="{left}" y="28" font-size="18" font-weight="700" fill="#0f172a">{esc(title)}</text>
  <text x="24" y="{top + plot_height / 2:.1f}" text-anchor="middle" font-size="13" fill="#334155" transform="rotate(-90 24 {top + plot_height / 2:.1f})">{esc(y_label)}</text>
  {''.join(lines)}
  <foreignObject x="{left}" y="{height - 28}" width="{plot_width}" height="24"><div xmlns="http://www.w3.org/1999/xhtml" class="legend">{''.join(legend)}</div></foreignObject>
</svg>
"""


def monthly_heatmap(monthly: pd.DataFrame, title: str) -> str:
    if monthly.empty:
        return "<p>No monthly data.</p>"
    data = monthly.copy()
    data["year"] = data["period"].str.slice(0, 4)
    data["month"] = data["period"].str.slice(5, 7)
    pivot = data.pivot(index="year", columns="month", values="return").fillna(np.nan)
    months = [f"{month:02d}" for month in range(1, 13)]
    header = "<th>Year</th>" + "".join(f"<th>{m}</th>" for m in months)
    rows = []
    for year, row in pivot.iterrows():
        cells = [f"<td>{esc(year)}</td>"]
        for month in months:
            value = row.get(month, np.nan)
            if pd.isna(value):
                cells.append("<td></td>")
                continue
            cls = "pos" if value >= 0 else "neg"
            cells.append(f'<td class="{cls}">{fmt_pct(float(value))}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<h3>{esc(title)}</h3><table class=\"heatmap\"><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def build_report(
    bars: pd.DataFrame,
    lightglow_trades: pd.DataFrame,
    pdlong_trades: pd.DataFrame,
    yearly_lg: pd.DataFrame,
    yearly_pd: pd.DataFrame,
    monthly_lg: pd.DataFrame,
    monthly_pd: pd.DataFrame,
    summary_lg: dict[str, Any],
    summary_pd: dict[str, Any],
    args: argparse.Namespace,
    lightglow: LightglowConfig,
    pdlong: PDLongConfig,
) -> str:
    css = """
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #111827; background: #f8fafc; }
main { max-width: 1240px; margin: 0 auto; padding: 32px 24px 60px; }
h1 { margin: 0 0 8px; font-size: 32px; letter-spacing: 0; }
h2 { margin: 34px 0 14px; font-size: 22px; }
h3 { margin: 18px 0 10px; font-size: 17px; }
p, li { line-height: 1.58; color: #334155; }
.badge { display: inline-flex; padding: 5px 9px; border-radius: 6px; background: #dbeafe; color: #1e40af; font-size: 13px; font-weight: 700; }
section { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-top: 18px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 12px; }
.metric { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; }
.metric strong { display: block; color: #475569; font-size: 13px; margin-bottom: 8px; }
.metric b { display: block; color: #0f172a; font-size: 22px; }
.metric span { display: block; color: #64748b; font-size: 12px; margin-top: 5px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 9px; border-bottom: 1px solid #e5e7eb; text-align: right; white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
th { color: #475569; background: #f8fafc; font-weight: 700; }
.heatmap td.pos { background: #dcfce7; color: #166534; }
.heatmap td.neg { background: #fee2e2; color: #991b1b; }
code { background: #eef2f7; padding: 2px 5px; border-radius: 5px; }
.chart { overflow-x: auto; }
.warn { border-left: 4px solid #ca8a04; padding-left: 14px; }
"""
    comparison = pd.DataFrame(
        [
            {"strategy": "Lightglow V2 Non-Kill Zone", **summary_lg},
            {"strategy": "Premium/Discount Long 1m", **summary_pd},
        ]
    )
    comparison_cols = [
        "strategy",
        "trades",
        "initial_capital",
        "final_equity",
        "net_profit",
        "total_return",
        "profit_factor",
        "win_rate",
        "avg_net_dollars",
        "avg_net_points",
        "max_drawdown",
        "max_drawdown_pct",
    ]
    yearly_cols = ["period", "trades", "start_equity", "end_equity", "net_profit", "return", "profit_factor", "win_rate", "max_drawdown"]
    series_map = {
        "Lightglow V2": equity_series(lightglow_trades, lightglow.initial_capital),
        "P/D Long 1m": equity_series(pdlong_trades, pdlong.initial_capital),
    }
    recent_cols = ["strategy", "entry_ts", "exit_ts", "symbol", "direction", "entry_price", "exit_price", "net_return", "net_dollars", "equity_after"]
    recent = pd.concat([lightglow_trades.tail(25), pdlong_trades.tail(25)], ignore_index=True).sort_values("entry_ts")
    summary_json = esc(
        json.dumps(
            {
                "lightglow": summary_lg,
                "premium_discount_long": summary_pd,
                "lightglow_config": lightglow.__dict__,
                "pdlong_config": pdlong.__dict__,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lightglow V2 vs P/D Long 1m Backtest Comparison</title>
  <style>{css}</style>
</head>
<body>
<main>
  <span class="badge">Databento NQ 1m · 2010-2026</span>
  <h1>Lightglow V2 与 Premium/Discount Long 1m 独立回测对比</h1>
  <p>数据源：<code>{esc(args.data)}</code>。连续合约构造：每个 UTC 分钟选择 NQ 合约中成交量最高的一条 OHLCV。实际覆盖：{bars["ts"].min():%Y-%m-%d %H:%M UTC} 到 {bars["ts"].max():%Y-%m-%d %H:%M UTC}，共 {len(bars):,} 根 1 分钟 K 线。</p>
  <p class="warn">按用户要求，本报告对两个策略使用完全一致的交易成本与合约单位：固定 1 张 NQ、$20/point、2 ticks/side 滑点、$5/order 手续费，即每笔往返 1.5 点 / $30。P/D Long 原 Pine 的 100% equity 仓位在这里改为固定 1 张 NQ，以保证交易成本一致。</p>

  <section>
    <h2>策略原理</h2>
    <div class="grid">
      <div>
        <h3>Lightglow V2 Non-Kill Zone</h3>
        <ul>
          <li>计算最近 100 根 K 线的高低区间，上方 95% 为 Premium，下方 5% 为 Discount。</li>
          <li>价格进入 Discount 做多，进入 Premium 做空，预期价格均值回归。</li>
          <li>要求 ATR(14) &gt; 8，避免低波动环境。</li>
          <li>避开固定 UTC 定义的 NY Kill Zone：13:30-16:30 与 18:30-21:00。</li>
          <li>持仓 2 根 1 分钟 K 线后时间退出。</li>
        </ul>
      </div>
      <div>
        <h3>Premium/Discount Long 1m</h3>
        <ul>
          <li>计算最近 100 根 K 线的高低区间，下方 5% 为 Discount。</li>
          <li>只做多：价格进入 Discount 即买入，预期 1 分钟均值回归。</li>
          <li>没有 ATR、时段、趋势过滤，交易频率更高。</li>
          <li>持仓 1 根 1 分钟 K 线后时间退出。</li>
          <li>原 Pine 使用 100% equity 仓位；本报告为公平成本对比，改用固定 1 张 NQ。</li>
        </ul>
      </div>
    </div>
  </section>

  <section>
    <h2>核心指标</h2>
    <p class="warn">解读限制：这是固定 1 张 NQ 的信号对比回测，未模拟保证金占用、账户权益低于 0 后的强平、每日止损或停机规则。因此当资金曲线跌破 0 后，后续统计只表示信号在历史样本上的持续盈亏，不代表真实账户可继续交易。</p>
    <div class="metrics">
      {metric_card("Lightglow Final Equity", fmt_money(summary_lg["final_equity"]), f'Return {fmt_pct(summary_lg["total_return"])}')}
      {metric_card("Lightglow PF / Win", f'{summary_lg["profit_factor"]:.2f}', fmt_pct(summary_lg["win_rate"]))}
      {metric_card("P/D Final Equity", fmt_money(summary_pd["final_equity"]), f'Return {fmt_pct(summary_pd["total_return"])}')}
      {metric_card("P/D PF / Win", f'{summary_pd["profit_factor"]:.2f}', fmt_pct(summary_pd["win_rate"]))}
    </div>
    {html_table(comparison[comparison_cols], comparison_cols)}
  </section>

  <section>
    <h2>资金曲线</h2>
    <div class="chart">{svg_line_chart(series_map, "Equity Curves", "Account equity", normalize=False)}</div>
    <div class="chart">{svg_line_chart(series_map, "Normalized Return Curves", "Return from initial capital", normalize=True)}</div>
  </section>

  <section>
    <h2>年度表现</h2>
    <h3>Lightglow V2</h3>
    {html_table(yearly_lg, yearly_cols)}
    <h3>Premium/Discount Long 1m</h3>
    {html_table(yearly_pd, yearly_cols)}
  </section>

  <section>
    <h2>月度表现</h2>
    {monthly_heatmap(monthly_lg, "Lightglow V2 Monthly Returns")}
    {monthly_heatmap(monthly_pd, "Premium/Discount Long 1m Monthly Returns")}
  </section>

  <section>
    <h2>优缺点分析</h2>
    <div class="grid">
      <div>
        <h3>Lightglow V2 优点</h3>
        <ul>
          <li>多空均可交易，理论上更适合双向震荡市场。</li>
          <li>ATR 与非 Kill Zone 过滤减少部分低质量时段交易。</li>
          <li>固定合约模型更接近 NQ/MNQ 实际下单语义。</li>
        </ul>
        <h3>Lightglow V2 风险</h3>
        <ul>
          <li>固定 UTC Kill Zone 未处理美国夏令时，可能与真实纽约时段有偏差。</li>
          <li>2 分钟持仓对手续费和滑点高度敏感。</li>
          <li>Premium/Discount 本质是短周期均值回归，在强趋势中可能连续逆势。</li>
        </ul>
      </div>
      <div>
        <h3>P/D Long 1m 优点</h3>
        <ul>
          <li>规则极简，信号来源清晰，便于 TradingView 与实盘复现。</li>
          <li>只做多，避免了空头保证金和隔夜融券类复杂度。</li>
          <li>1 分钟退出让单笔暴露时间很短。</li>
        </ul>
        <h3>P/D Long 1m 风险</h3>
        <ul>
          <li>交易频率极高，对手续费、滑点、成交质量极端敏感。</li>
          <li>本报告没有使用原 Pine 的百分比复利仓位，因此与 TradingView 原默认资金曲线会不同。</li>
          <li>没有时段、波动率或趋势过滤，容易在下跌趋势中持续接刀。</li>
        </ul>
      </div>
    </div>
  </section>

  <section>
    <h2>最近交易样本</h2>
    {html_table(recent, recent_cols)}
  </section>

  <section>
    <h2>回测设置</h2>
    <pre><code>{summary_json}</code></pre>
  </section>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate independent comparison report for Lightglow V2 and P/D Long 1m Pine strategies.")
    parser.add_argument("--data", default="data/raw/databento/glbx-mdp3-20100606-20260427.ohlcv-1m.csv")
    parser.add_argument("--start-date", default="2010-01-01")
    parser.add_argument("--end-date", default="2027-01-01")
    parser.add_argument("--min-volume", type=int, default=1)
    parser.add_argument("--chunk-size", type=int, default=1_000_000)
    parser.add_argument("--cache", default=".tmp/lightglow-pd-combined-1m-bars.pkl")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--report", default="reports/lightglow_vs_pdlong_1min_comparison.html")
    parser.add_argument("--summary-output", default="reports/lightglow_vs_pdlong_1min_summary.json")
    parser.add_argument("--yearly-output", default="reports/lightglow_vs_pdlong_1min_yearly.csv")
    parser.add_argument("--monthly-output", default="reports/lightglow_vs_pdlong_1min_monthly.csv")
    parser.add_argument("--trades-output", default="reports/lightglow_vs_pdlong_1min_trades.csv")
    args = parser.parse_args()

    lightglow = LightglowConfig()
    pdlong = PDLongConfig()
    bars = load_continuous_nq_csv(args)
    frame = add_strategy_signals(bars, lightglow, pdlong)
    lightglow_trades = build_lightglow_trades(frame, lightglow)
    pdlong_trades = build_pdlong_trades(frame, pdlong)

    summary_lg = summarize(lightglow_trades, lightglow.initial_capital)
    summary_pd = summarize(pdlong_trades, pdlong.initial_capital)
    yearly_lg = period_summary(lightglow_trades, lightglow.initial_capital, "Y")
    yearly_pd = period_summary(pdlong_trades, pdlong.initial_capital, "Y")
    monthly_lg = period_summary(lightglow_trades, lightglow.initial_capital, "M")
    monthly_pd = period_summary(pdlong_trades, pdlong.initial_capital, "M")
    yearly_lg.insert(0, "strategy", "Lightglow V2 Non-Kill Zone")
    yearly_pd.insert(0, "strategy", "Premium/Discount Long 1m")
    monthly_lg.insert(0, "strategy", "Lightglow V2 Non-Kill Zone")
    monthly_pd.insert(0, "strategy", "Premium/Discount Long 1m")

    summary = {
        "data": args.data,
        "period_start": str(bars["ts"].min()),
        "period_end": str(bars["ts"].max()),
        "bars": int(len(bars)),
        "lightglow": summary_lg,
        "premium_discount_long": summary_pd,
        "lightglow_config": lightglow.__dict__,
        "pdlong_config": pdlong.__dict__,
    }

    for output in [args.report, args.summary_output, args.yearly_output, args.monthly_output, args.trades_output]:
        Path(output).parent.mkdir(parents=True, exist_ok=True)

    all_trades = pd.concat([lightglow_trades, pdlong_trades], ignore_index=True)
    all_trades.to_csv(args.trades_output, index=False)
    pd.concat([yearly_lg, yearly_pd], ignore_index=True).to_csv(args.yearly_output, index=False)
    pd.concat([monthly_lg, monthly_pd], ignore_index=True).to_csv(args.monthly_output, index=False)
    Path(args.summary_output).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    Path(args.report).write_text(
        build_report(
            bars,
            lightglow_trades,
            pdlong_trades,
            yearly_lg,
            yearly_pd,
            monthly_lg,
            monthly_pd,
            summary_lg,
            summary_pd,
            args,
            lightglow,
            pdlong,
        ),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote {args.report}")


if __name__ == "__main__":
    main()
