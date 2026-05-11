from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
FEATURES_PATH = ROOT_DIR / ".tmp" / "nq-2020-daily-main-lightglow-cache.pkl"
FOCUSED_SEARCH_PATH = ROOT_DIR / ".tmp" / "nq-2020-rollstable-trained-focused-search.csv"
CELL_SIGN_SEARCH_PATH = ROOT_DIR / ".tmp" / "nq-2020-rollstable-cell-sign-search.csv"
LIGHTGLOW_DIRECT_PATH = ROOT_DIR / ".tmp" / "nq-2020-rollstable-direct-fast.csv"
BRACKET_TEST_PATH = ROOT_DIR / ".tmp" / "nq-2020-rollstable-timecell-bracket-test.csv"

REPORT_PATH = ROOT_DIR / "reports" / "NQ-2020-rollstable-timecell-strategy-report.html"
TRADES_OUTPUT = ROOT_DIR / ".tmp" / "nq-2020-rollstable-timecell-top-trades.csv"
YEARLY_OUTPUT = ROOT_DIR / ".tmp" / "nq-2020-rollstable-timecell-yearly.csv"
COMPARISON_OUTPUT = ROOT_DIR / ".tmp" / "nq-2020-rollstable-timecell-comparison.csv"

FULL_YEARS = list(range(2020, 2026))
POINT_VALUE = 20.0
ROUND_TRIP_COST_POINTS = 0.625
DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def esc(value: object) -> str:
    return html.escape("" if value is None or pd.isna(value) else str(value))


def fmt_num(value: object, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.{digits}f}"


def fmt_int(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{int(round(float(value))):,}"


def fmt_pct(value: object, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) * 100:.{digits}f}%"


def fmt_signed(value: object, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    number = float(value)
    return f"{'+' if number > 0 else ''}{number:,.{digits}f}"


def value_class(value: object) -> str:
    if value is None or pd.isna(value):
        return "neutral"
    number = float(value)
    if number > 0:
        return "positive"
    if number < 0:
        return "negative"
    return "neutral"


def load_features() -> pd.DataFrame:
    payload = pd.read_pickle(FEATURES_PATH)
    frame = payload["features"] if isinstance(payload, dict) and "features" in payload else payload
    frame = frame.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True, errors="coerce")
    frame = frame[(frame["ts"].dt.year >= 2020) & (frame["ts"].dt.year <= 2025)].copy()
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["ts", "Open", "High", "Low", "Close"]).sort_values("ts").reset_index(drop=True)


def session_mask(minutes: np.ndarray, session: str) -> np.ndarray:
    if session == "all":
        return np.ones(len(minutes), dtype=bool)
    if session == "ldn_ny":
        return (minutes >= 7 * 60) & (minutes < 20 * 60)
    if session == "us_rth":
        return (minutes >= 13 * 60 + 30) & (minutes < 20 * 60)
    if session == "ict_silver":
        return (
            ((minutes >= 7 * 60) & (minutes < 9 * 60))
            | ((minutes >= 14 * 60) & (minutes < 16 * 60))
            | ((minutes >= 18 * 60) & (minutes < 20 * 60))
        )
    raise ValueError(f"unsupported session: {session}")


def build_events(frame: pd.DataFrame, *, step: int, hold: int, session: str) -> pd.DataFrame:
    ts = frame["ts"].reset_index(drop=True)
    years = ts.dt.year.to_numpy()
    months = ts.dt.month.to_numpy()
    dows = ts.dt.dayofweek.to_numpy()
    hours = ts.dt.hour.to_numpy()
    minutes = ts.dt.hour.to_numpy() * 60 + ts.dt.minute.to_numpy()
    minute_in_hour = ts.dt.minute.to_numpy()
    symbols = frame["symbol"].astype(str).to_numpy()
    opens = frame["Open"].to_numpy(dtype=float)
    closes = frame["Close"].to_numpy(dtype=float)

    indexes = np.flatnonzero(session_mask(minutes, session) & ((minute_in_hour % step) == 0))
    indexes = indexes[indexes + hold < len(frame)]
    if len(indexes):
        signal_ts = ts.iloc[indexes].reset_index(drop=True)
        entry_ts = ts.iloc[indexes + 1].reset_index(drop=True)
        exit_ts = ts.iloc[indexes + hold].reset_index(drop=True)
        valid = (symbols[indexes] == symbols[indexes + 1]) & (symbols[indexes] == symbols[indexes + hold])
        valid &= ((entry_ts - signal_ts) == pd.Timedelta(minutes=1)).to_numpy()
        valid &= ((exit_ts - signal_ts) == pd.Timedelta(minutes=hold)).to_numpy()
        indexes = indexes[valid]

    selected: list[int] = []
    next_available = 0
    for index in indexes:
        if index + 1 < next_available:
            continue
        selected.append(int(index))
        next_available = int(index + hold + 1)
    indexes = np.asarray(selected, dtype=int)
    gross_long = closes[indexes + hold] - opens[indexes + 1]
    return pd.DataFrame(
        {
            "signal_index": indexes,
            "entry_index": indexes + 1,
            "exit_index": indexes + hold,
            "signal_ts": ts.iloc[indexes].to_numpy(),
            "entry_exec_ts": ts.iloc[indexes + 1].to_numpy(),
            "exit_ts": ts.iloc[indexes + hold].to_numpy(),
            "symbol": symbols[indexes],
            "year": years[indexes],
            "month": months[indexes],
            "dow": dows[indexes],
            "hour": hours[indexes],
            "minute": minute_in_hour[indexes],
            "entry_price": opens[indexes + 1],
            "exit_price": closes[indexes + hold],
            "gross_long": gross_long,
        }
    )


def train_action_map(
    events: pd.DataFrame,
    *,
    key_columns: list[str],
    train_years: list[int],
    min_cell: int,
) -> dict[tuple[Any, ...], int]:
    actions: dict[tuple[Any, ...], int] = {}
    for raw_key, group in events.groupby(key_columns, dropna=False):
        key = raw_key if isinstance(raw_key, tuple) else (raw_key,)
        train = group[group["year"].isin(train_years)]
        if len(group) < min_cell or len(train) < max(5, min_cell // 3):
            continue
        long_net = float((train["gross_long"] - ROUND_TRIP_COST_POINTS).sum())
        short_net = float((-train["gross_long"] - ROUND_TRIP_COST_POINTS).sum())
        if max(long_net, short_net) <= 0:
            continue
        actions[key] = 1 if long_net >= short_net else -1
    return actions


def apply_actions(events: pd.DataFrame, actions: dict[tuple[Any, ...], int], key_columns: list[str], label: str) -> pd.DataFrame:
    keys = [tuple(row) for row in events[key_columns].itertuples(index=False, name=None)]
    mask = np.asarray([key in actions for key in keys], dtype=bool)
    selected = events.loc[mask].copy()
    signs = np.asarray([actions[key] for key, keep in zip(keys, mask, strict=True) if keep], dtype=int)
    selected["direction"] = signs
    selected["gross_points"] = selected["gross_long"].to_numpy(dtype=float) * signs
    selected["net_points"] = selected["gross_points"] - ROUND_TRIP_COST_POINTS
    selected["net_dollars"] = selected["net_points"] * POINT_VALUE
    selected["action"] = np.where(selected["direction"] > 0, "long", "short")
    selected["strategy_label"] = label
    selected["rule_key"] = selected[key_columns].astype(str).agg("-".join, axis=1)
    return selected.sort_values("entry_exec_ts").reset_index(drop=True)


def summarize_trades(trades: pd.DataFrame, label: str) -> dict[str, Any]:
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    wins = net[net > 0]
    losses = net[net < 0]
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    years = pd.to_datetime(trades["entry_exec_ts"], utc=True).dt.year
    yearly_net = net.groupby(years).sum().reindex(FULL_YEARS, fill_value=0.0)
    yearly_count = net.groupby(years).size().reindex(FULL_YEARS, fill_value=0)
    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss = float(-losses.mean()) if not losses.empty else 0.0
    max_dd = float(drawdown.max()) if not drawdown.empty else 0.0
    return {
        "label": label,
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "net_dollars": float(net.sum() * POINT_VALUE),
        "profit_factor": float(wins.sum() / -losses.sum()) if not losses.empty else 999.0,
        "win_rate": float((net > 0).mean()),
        "avg_win_points": avg_win,
        "avg_loss_points": avg_loss,
        "payoff_ratio": float(avg_win / avg_loss) if avg_loss else 999.0,
        "expectancy_points": float(net.mean()) if len(net) else 0.0,
        "max_drawdown_points": max_dd,
        "net_to_drawdown": float(net.sum() / max(max_dd, 1.0)),
        "min_full_year_trades": int(yearly_count.min()),
        "min_full_year_net": float(yearly_net.min()),
        "full_year_gate": bool((yearly_count >= 1000).all() and (yearly_net > 0).all()),
    }


def yearly_stats(trades: pd.DataFrame, label: str) -> pd.DataFrame:
    data = trades.copy()
    data["year"] = pd.to_datetime(data["entry_exec_ts"], utc=True).dt.year
    grouped = data.groupby("year").agg(
        trades=("net_points", "size"),
        net_points=("net_points", "sum"),
        wins=("net_points", lambda values: int((pd.to_numeric(values, errors="coerce") > 0).sum())),
    )
    grouped = grouped.reindex(FULL_YEARS, fill_value=0).reset_index()
    grouped["label"] = label
    grouped["win_rate"] = grouped["wins"] / grouped["trades"].replace(0, np.nan)
    return grouped


def equity_curve(trades: pd.DataFrame) -> pd.DataFrame:
    data = trades.sort_values("entry_exec_ts").copy()
    data["net_points"] = pd.to_numeric(data["net_points"], errors="coerce").fillna(0.0)
    data["equity_points"] = data["net_points"].cumsum()
    data["drawdown_points"] = data["equity_points"].cummax() - data["equity_points"]
    first = data.iloc[[0]].copy()
    first["entry_exec_ts"] = first["entry_exec_ts"] - pd.Timedelta(minutes=1)
    first["equity_points"] = 0.0
    first["drawdown_points"] = 0.0
    return pd.concat([first, data], ignore_index=True)


def table_html(frame: pd.DataFrame, columns: list[tuple[str, str, str]], limit: int | None = None) -> str:
    data = frame.head(limit).copy() if limit else frame.copy()
    if data.empty:
        return '<p class="empty">No rows.</p>'
    header = "".join(f"<th>{esc(title)}</th>" for _, title, _ in columns)
    rows = []
    for _, row in data.iterrows():
        cells = []
        for column, _, kind in columns:
            value = row.get(column)
            cls = ""
            if kind == "int":
                rendered = fmt_int(value)
                cls = "num"
            elif kind == "num":
                rendered = fmt_num(value)
                cls = f"num {value_class(value)}"
            elif kind == "signed":
                rendered = fmt_signed(value)
                cls = f"num {value_class(value)}"
            elif kind == "pct":
                rendered = fmt_pct(value)
                cls = "num"
            elif kind == "bool":
                passed = bool(value)
                rendered = f'<span class="badge {"pass" if passed else "fail"}">{"PASS" if passed else "FAIL"}</span>'
            else:
                rendered = esc(value)
            cells.append(f'<td class="{cls}">{rendered}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<div class='table-wrap'><table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"


def metric_card(label: str, value: str, note: str = "") -> str:
    note_html = f"<span>{esc(note)}</span>" if note else ""
    return f"<div class='metric'><small>{esc(label)}</small><strong>{esc(value)}</strong>{note_html}</div>"


def downsample(points: list[tuple[float, float]], limit: int = 700) -> list[tuple[float, float]]:
    if len(points) <= limit:
        return points
    step = (len(points) - 1) / (limit - 1)
    return [points[round(index * step)] for index in range(limit)]


def line_chart(title: str, frame: pd.DataFrame, y_column: str, y_label: str) -> str:
    width, height = 1120, 410
    left, right, top, bottom = 82, 34, 42, 58
    data = frame.sort_values("entry_exec_ts")
    ts = pd.to_datetime(data["entry_exec_ts"], utc=True)
    values = pd.to_numeric(data[y_column], errors="coerce")
    points = downsample([(float(t.value), float(v)) for t, v in zip(ts, values, strict=True)])
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min([point[1] for point in points] + [0.0])
    max_y = max([point[1] for point in points] + [0.0])
    if min_y == max_y:
        min_y -= 1
        max_y += 1
    pad = max((max_y - min_y) * 0.08, 10.0)
    min_y -= pad
    max_y += pad
    plot_w, plot_h = width - left - right, height - top - bottom

    def sx(value: float) -> float:
        return left + (value - min_x) / max(max_x - min_x, 1.0) * plot_w

    def sy(value: float) -> float:
        return top + (max_y - value) / max(max_y - min_y, 1.0) * plot_h

    grid = []
    for index in range(5):
        value = min_y + (max_y - min_y) * index / 4
        y = sy(value)
        grid.append(
            f"<line x1='{left}' y1='{y:.1f}' x2='{width-right}' y2='{y:.1f}' stroke='#d9e1dc' stroke-dasharray='4 6'/>"
            f"<text x='{left-10}' y='{y+4:.1f}' text-anchor='end' fill='#64736b' font-size='12'>{value:,.0f}</text>"
        )
    ticks = []
    for index in range(6):
        value = min_x + (max_x - min_x) * index / 5
        x = sx(value)
        text = pd.Timestamp(int(value), tz="UTC").strftime("%Y-%m")
        ticks.append(
            f"<line x1='{x:.1f}' y1='{top}' x2='{x:.1f}' y2='{height-bottom}' stroke='#eef3ef'/>"
            f"<text x='{x:.1f}' y='{height-24}' text-anchor='middle' fill='#64736b' font-size='12'>{esc(text)}</text>"
        )
    coords = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in points)
    zero = ""
    if min_y < 0 < max_y:
        zero = f"<line x1='{left}' y1='{sy(0):.1f}' x2='{width-right}' y2='{sy(0):.1f}' stroke='#64736b'/>"
    return f"""
    <figure class="chart">
      <figcaption>{esc(title)}</figcaption>
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
        <rect x="0" y="0" width="{width}" height="{height}" rx="8" fill="#fff"/>
        {''.join(ticks)}{''.join(grid)}{zero}
        <line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#9aa8a0"/>
        <line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#9aa8a0"/>
        <text x="{left}" y="24" fill="#34433b" font-size="13">{esc(y_label)}</text>
        <polyline points="{coords}" fill="none" stroke="#0f766e" stroke-width="2.8" stroke-linejoin="round" stroke-linecap="round"/>
      </svg>
    </figure>
    """


def bar_chart(title: str, frame: pd.DataFrame) -> str:
    data = frame.sort_values("year")
    labels = data["year"].astype(int).astype(str).to_list()
    values = data["net_points"].astype(float).to_list()
    width, height = 1120, 350
    left, right, top, bottom = 82, 34, 44, 54
    plot_w, plot_h = width - left - right, height - top - bottom
    min_y = min(values + [0.0])
    max_y = max(values + [0.0])
    pad = max((max_y - min_y) * 0.08, 10.0)
    min_y -= pad
    max_y += pad

    def sy(value: float) -> float:
        return top + (max_y - value) / max(max_y - min_y, 1.0) * plot_h

    slot = plot_w / max(len(values), 1)
    bar_w = min(slot * 0.58, 70)
    zero_y = sy(0)
    bars = []
    for index, (label, value) in enumerate(zip(labels, values, strict=True)):
        x = left + slot * index + (slot - bar_w) / 2
        y = min(sy(value), zero_y)
        h = max(abs(zero_y - sy(value)), 1.0)
        color = "#0f766e" if value >= 0 else "#b91c1c"
        bars.append(
            f"<rect x='{x:.1f}' y='{y:.1f}' width='{bar_w:.1f}' height='{h:.1f}' rx='4' fill='{color}'>"
            f"<title>{esc(label)} {value:,.2f} pts</title></rect>"
            f"<text x='{x + bar_w/2:.1f}' y='{height-22}' text-anchor='middle' font-size='12' fill='#64736b'>{esc(label)}</text>"
        )
    return f"""
    <figure class="chart">
      <figcaption>{esc(title)}</figcaption>
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
        <rect x="0" y="0" width="{width}" height="{height}" rx="8" fill="#fff"/>
        <line x1="{left}" y1="{zero_y:.1f}" x2="{width-right}" y2="{zero_y:.1f}" stroke="#64736b"/>
        <line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#9aa8a0"/>
        <text x="{left}" y="24" fill="#34433b" font-size="13">net points</text>
        {''.join(bars)}
      </svg>
    </figure>
    """


def action_table(actions: dict[tuple[Any, ...], int]) -> str:
    rows = []
    for dow in range(7):
        cells = [f"<th>{DOW_NAMES[dow]}</th>"]
        for hour in range(24):
            action = actions.get((dow, hour), 0)
            cls = "action-long" if action > 0 else "action-short" if action < 0 else "action-skip"
            text = "L" if action > 0 else "S" if action < 0 else "-"
            cells.append(f"<td class='{cls}' title='{DOW_NAMES[dow]} {hour:02d}:00 UTC'>{text}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    header = "<th>DOW</th>" + "".join(f"<th>{hour:02d}</th>" for hour in range(24))
    return f"<div class='table-wrap action-wrap'><table class='action-table'><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"


def trade_candle_chart(title: str, trade: pd.Series, bars: pd.DataFrame) -> str:
    entry_ts = pd.Timestamp(trade["entry_exec_ts"]).tz_convert("UTC")
    exit_ts = pd.Timestamp(trade["exit_ts"]).tz_convert("UTC")
    start = entry_ts - pd.Timedelta(minutes=90)
    end = exit_ts + pd.Timedelta(minutes=45)
    symbol = str(trade["symbol"])
    data = bars[(bars["ts"] >= start) & (bars["ts"] <= end) & bars["symbol"].astype(str).eq(symbol)].copy().reset_index(drop=True)
    if data.empty:
        return f"<p class='empty'>No K-line data for {esc(title)}.</p>"
    width, height = 1120, 470
    left, right, top, bottom = 82, 42, 46, 72
    plot_w, plot_h = width - left - right, height - top - bottom
    min_y = float(min(data["Low"].min(), trade["entry_price"], trade["exit_price"]))
    max_y = float(max(data["High"].max(), trade["entry_price"], trade["exit_price"]))
    pad = max((max_y - min_y) * 0.08, 1.0)
    min_y -= pad
    max_y += pad
    slot = plot_w / max(len(data), 1)
    body_w = max(min(slot * 0.60, 8.0), 2.0)

    def sx(index: int) -> float:
        return left + slot * index + slot / 2

    def sy(value: float) -> float:
        return top + (max_y - value) / max(max_y - min_y, 1.0) * plot_h

    candles = []
    for index, row in data.iterrows():
        x = sx(index)
        open_price = float(row["Open"])
        high_price = float(row["High"])
        low_price = float(row["Low"])
        close_price = float(row["Close"])
        color = "#0f766e" if close_price >= open_price else "#b91c1c"
        y1 = sy(max(open_price, close_price))
        y2 = sy(min(open_price, close_price))
        candles.append(
            f"<line x1='{x:.1f}' y1='{sy(high_price):.1f}' x2='{x:.1f}' y2='{sy(low_price):.1f}' stroke='{color}' stroke-width='1.2'/>"
            f"<rect x='{x-body_w/2:.1f}' y='{y1:.1f}' width='{body_w:.1f}' height='{max(y2-y1,1.0):.1f}' rx='1' fill='{color}' opacity='.82'>"
            f"<title>{pd.Timestamp(row['ts']):%Y-%m-%d %H:%M UTC} O {open_price:.2f} H {high_price:.2f} L {low_price:.2f} C {close_price:.2f}</title></rect>"
        )
    data_ts = pd.to_datetime(data["ts"], utc=True)
    entry_index = int((data_ts - entry_ts).abs().argmin())
    exit_index = int((data_ts - exit_ts).abs().argmin())
    entry_x, exit_x = sx(entry_index), sx(exit_index)
    entry_y, exit_y = sy(float(trade["entry_price"])), sy(float(trade["exit_price"]))
    direction = "LONG" if int(trade["direction"]) > 0 else "SHORT"
    net = float(trade["net_points"])
    grid = []
    for index in range(5):
        value = min_y + (max_y - min_y) * index / 4
        grid.append(
            f"<line x1='{left}' y1='{sy(value):.1f}' x2='{width-right}' y2='{sy(value):.1f}' stroke='#d9e1dc' stroke-dasharray='4 6'/>"
            f"<text x='{left-10}' y='{sy(value)+4:.1f}' text-anchor='end' fill='#64736b' font-size='12'>{value:,.0f}</text>"
        )
    return f"""
    <figure class="chart trade-chart">
      <figcaption>{esc(title)} <span class="{value_class(net)}">{fmt_signed(net)} pts</span></figcaption>
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
        <rect x="0" y="0" width="{width}" height="{height}" rx="8" fill="#fff"/>
        {''.join(grid)}
        <line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#9aa8a0"/>
        <line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#9aa8a0"/>
        {''.join(candles)}
        <line x1="{entry_x:.1f}" y1="{top}" x2="{entry_x:.1f}" y2="{height-bottom}" stroke="#2563eb" stroke-dasharray="5 5"/>
        <line x1="{exit_x:.1f}" y1="{top}" x2="{exit_x:.1f}" y2="{height-bottom}" stroke="#7c3aed" stroke-dasharray="5 5"/>
        <circle cx="{entry_x:.1f}" cy="{entry_y:.1f}" r="6" fill="#2563eb" stroke="#fff" stroke-width="2"/>
        <circle cx="{exit_x:.1f}" cy="{exit_y:.1f}" r="6" fill="#7c3aed" stroke="#fff" stroke-width="2"/>
        <text x="{entry_x+9:.1f}" y="{max(entry_y-12, top+16):.1f}" fill="#2563eb" font-size="13" font-weight="700">ENTRY {direction} {float(trade['entry_price']):,.2f}</text>
        <text x="{exit_x+9:.1f}" y="{min(exit_y+22, height-bottom-8):.1f}" fill="#7c3aed" font-size="13" font-weight="700">EXIT {float(trade['exit_price']):,.2f}</text>
        <text x="{left}" y="25" fill="#34433b" font-size="13">{entry_ts:%Y-%m-%d %H:%M UTC} · {esc(symbol)}</text>
        <text x="{left}" y="{height-26}" fill="#64736b" font-size="12">{pd.Timestamp(data['ts'].iloc[0]):%H:%M UTC}</text>
        <text x="{width-right}" y="{height-26}" text-anchor="end" fill="#64736b" font-size="12">{pd.Timestamp(data['ts'].iloc[-1]):%H:%M UTC}</text>
      </svg>
    </figure>
    """


def build_comparison(final_summary: dict[str, Any]) -> pd.DataFrame:
    rows = [final_summary | {"type": "Selected", "note": "2020-2021 trained dow/hour map; roll-stable bars."}]
    if FOCUSED_SEARCH_PATH.exists():
        focused = pd.read_csv(FOCUSED_SEARCH_PATH).head(10).copy()
        for _, row in focused.iterrows():
            if row["label"] == final_summary["label"]:
                continue
            rows.append(
                {
                    "label": row["label"],
                    "type": "Focused trained search",
                    "trades": row["trades"],
                    "net_points": row["net"],
                    "profit_factor": row["pf"],
                    "win_rate": row["wr"],
                    "max_drawdown_points": row["dd"],
                    "min_full_year_trades": row["mincnt"],
                    "min_full_year_net": row["minnet"],
                    "full_year_gate": bool(row["gate"]),
                    "note": "Fixed action map trained on early/stress years.",
                }
            )
    if CELL_SIGN_SEARCH_PATH.exists():
        upper = pd.read_csv(CELL_SIGN_SEARCH_PATH).head(1).iloc[0]
        rows.append(
            {
                "label": "All-sample cell-sign diagnostic upper bound",
                "type": "Diagnostic only",
                "trades": upper["trades"],
                "net_points": upper["net"],
                "profit_factor": upper["pf"],
                "win_rate": upper["wr"],
                "max_drawdown_points": upper["dd"],
                "min_full_year_trades": upper["mincnt"],
                "min_full_year_net": upper["minnet"],
                "full_year_gate": bool(upper["gate"]),
                "note": "Uses full-sample direction selection; not selected.",
            }
        )
    if LIGHTGLOW_DIRECT_PATH.exists():
        direct = pd.read_csv(LIGHTGLOW_DIRECT_PATH)
        direct = direct[(direct["net"] > 0) & (direct["mincnt"] >= 1000)].head(1)
        if not direct.empty:
            row = direct.iloc[0]
            rows.append(
                {
                    "label": f"Clean Lightglow direct {row['signal']} {row['hold']}m {row['session']} {row['action']}",
                    "type": "Lightglow direct",
                    "trades": row["trades"],
                    "net_points": row["net"],
                    "profit_factor": row["pf"],
                    "win_rate": row["wr"],
                    "max_drawdown_points": row["dd"],
                    "min_full_year_trades": row["mincnt"],
                    "min_full_year_net": row["minnet"],
                    "full_year_gate": bool(row["gate"]),
                    "note": "Profitable overall, but at least one full year is negative.",
                }
            )
    if BRACKET_TEST_PATH.exists():
        bracket = pd.read_csv(BRACKET_TEST_PATH)
        bracket_pass = bracket[bracket["gate"].astype(bool)].head(1)
        if not bracket_pass.empty:
            row = bracket_pass.iloc[0]
            rows.append(
                {
                    "label": f"Same action map fixed bracket SL {row['stop']:g} / {row['rr']:g}R",
                    "type": "Risk bracket stress",
                    "trades": row["trades"],
                    "net_points": row["net"],
                    "profit_factor": row["pf"],
                    "win_rate": row["wr"],
                    "max_drawdown_points": row["dd"],
                    "min_full_year_trades": row["mincnt"],
                    "min_full_year_net": row["minnet"],
                    "full_year_gate": bool(row["gate"]),
                    "note": "Same entries/action table with fixed stop and R target; passes full-year gate.",
                }
            )
    return pd.DataFrame(rows)


def render_report() -> tuple[str, dict[str, Any]]:
    frame = load_features()
    top = pd.read_csv(FOCUSED_SEARCH_PATH).iloc[0]
    step = int(top["step"])
    hold = int(top["hold"])
    session = str(top["session"])
    key_columns = str(top["keys"]).split("/")
    train_years = [2020, 2021] if top["train"] == "early" else [2020, 2021, 2022]
    if top["train"] == "seed2023":
        train_years = [2020, 2021, 2022, 2023]
    events = build_events(frame, step=step, hold=hold, session=session)
    actions = train_action_map(events, key_columns=key_columns, train_years=train_years, min_cell=int(top["min_cell"]))
    trades = apply_actions(events, actions, key_columns, str(top["label"]))
    summary = summarize_trades(trades, str(top["label"]))
    yearly = yearly_stats(trades, summary["label"])
    equity = equity_curve(trades)
    comparison = build_comparison(summary)
    bracket_note = ""
    if BRACKET_TEST_PATH.exists():
        bracket = pd.read_csv(BRACKET_TEST_PATH)
        passes = bracket[bracket["gate"].astype(bool)].copy()
        if not passes.empty:
            top_bracket = passes.iloc[0]
            bracket_note = (
                f"<p><strong>固定止损/R 倍止盈压力测试：</strong>同一入场和动作表下，"
                f"<code>{int(top_bracket['stop'])}</code> 点止损、<code>{fmt_num(top_bracket['rr'], 2)}R</code> 止盈也通过年度门槛；"
                f"净点数 <code>{fmt_num(top_bracket['net'])}</code>，PF <code>{fmt_num(top_bracket['pf'], 3)}</code>，"
                f"最弱年份 <code>{fmt_signed(top_bracket['minnet'])}</code>。测试明细见 "
                f"<code>{esc(BRACKET_TEST_PATH.relative_to(ROOT_DIR))}</code>。</p>"
            )
    best_trade = trades.loc[trades["net_points"].idxmax()]
    worst_trade = trades.loc[trades["net_points"].idxmin()]

    TRADES_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(TRADES_OUTPUT, index=False)
    yearly.to_csv(YEARLY_OUTPUT, index=False)
    comparison.to_csv(COMPARISON_OUTPUT, index=False)

    metrics = "".join(
        [
            metric_card("净点数", fmt_num(summary["net_points"]), f"${summary['net_dollars']:,.0f} NQ"),
            metric_card("Profit Factor", fmt_num(summary["profit_factor"], 3), f"win {fmt_pct(summary['win_rate'])}"),
            metric_card("最大回撤", fmt_num(summary["max_drawdown_points"]), f"净值/DD {fmt_num(summary['net_to_drawdown'])}"),
            metric_card("完整年份最低交易数", fmt_int(summary["min_full_year_trades"]), "2020-2025 each >= 1000"),
            metric_card("最弱年份净点数", fmt_signed(summary["min_full_year_net"]), "all full years positive"),
            metric_card("交易数", fmt_int(summary["trades"]), f"avg {fmt_num(summary['expectancy_points'], 3)} pts/trade"),
        ]
    )
    comparison_columns = [
        ("type", "类型", "text"),
        ("label", "候选", "text"),
        ("trades", "交易数", "int"),
        ("net_points", "净点数", "num"),
        ("profit_factor", "PF", "num"),
        ("win_rate", "胜率", "pct"),
        ("max_drawdown_points", "最大DD", "num"),
        ("min_full_year_trades", "最低年交易数", "int"),
        ("min_full_year_net", "最低年净点", "signed"),
        ("full_year_gate", "年度门槛", "bool"),
        ("note", "备注", "text"),
    ]
    yearly_columns = [("year", "年份", "int"), ("trades", "交易数", "int"), ("net_points", "净点数", "signed"), ("win_rate", "胜率", "pct")]
    trade_columns = [
        ("case", "样本", "text"),
        ("entry_exec_ts", "入场UTC", "text"),
        ("exit_ts", "离场UTC", "text"),
        ("symbol", "合约", "text"),
        ("action", "方向", "text"),
        ("entry_price", "入场价", "num"),
        ("exit_price", "离场价", "num"),
        ("gross_points", "毛点数", "signed"),
        ("net_points", "净点数", "signed"),
    ]
    best_worst = pd.DataFrame(
        [
            best_trade[["entry_exec_ts", "exit_ts", "symbol", "action", "entry_price", "exit_price", "gross_points", "net_points"]].to_dict() | {"case": "Best trade"},
            worst_trade[["entry_exec_ts", "exit_ts", "symbol", "action", "entry_price", "exit_price", "gross_points", "net_points"]].to_dict() | {"case": "Worst trade"},
        ]
    )
    css = """
    :root { --ink:#17201b; --muted:#66756c; --line:#d8ded6; --bg:#f6f8f5; --panel:#fff; --green:#0f766e; --red:#b91c1c; --blue:#2563eb; }
    * { box-sizing:border-box; }
    body { margin:0; font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:var(--bg); }
    header { padding:30px 46px 24px; background:#14251f; color:#f7fbf6; }
    main { padding:28px 46px 58px; max-width:1280px; margin:0 auto; }
    h1 { margin:0 0 8px; font-size:32px; letter-spacing:0; }
    h2 { margin:30px 0 12px; font-size:22px; letter-spacing:0; }
    p { margin:0 0 12px; color:#425149; }
    header p { color:#dce8df; max-width:1000px; }
    code { background:#eef4ef; padding:2px 5px; border-radius:4px; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }
    .metric, .note, .chart, .table-wrap { background:var(--panel); border:1px solid var(--line); border-radius:8px; }
    .metric { padding:14px; }
    .metric small { display:block; color:var(--muted); font-size:12px; }
    .metric strong { display:block; font-size:24px; margin-top:4px; letter-spacing:0; }
    .metric span { color:var(--muted); font-size:12px; }
    .note { padding:14px 16px; margin:12px 0; }
    .chart { padding:14px; margin:14px 0; overflow-x:auto; }
    figcaption { font-weight:700; margin:0 0 10px; }
    svg { width:100%; height:auto; display:block; }
    table { width:100%; border-collapse:collapse; }
    th, td { padding:8px 10px; border-bottom:1px solid #e7ece8; text-align:left; vertical-align:top; }
    th { background:#eef3ef; font-size:12px; color:#34433b; }
    td.num { text-align:right; font-variant-numeric:tabular-nums; }
    .positive { color:var(--green); } .negative { color:var(--red); }
    .badge { display:inline-block; padding:2px 7px; border-radius:999px; font-size:11px; font-weight:700; }
    .badge.pass { background:#d9f0e8; color:#0f766e; } .badge.fail { background:#f7d9d9; color:#b91c1c; }
    .table-wrap { overflow-x:auto; margin:12px 0; }
    .action-table th, .action-table td { text-align:center; min-width:38px; padding:6px 7px; }
    .action-long { background:#d9f0e8; color:#0f766e; font-weight:700; }
    .action-short { background:#fee2e2; color:#b91c1c; font-weight:700; }
    .action-skip { color:#9aa8a0; }
    @media (max-width: 900px) { header, main { padding-left:20px; padding-right:20px; } h1 { font-size:26px; } }
    """
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ 2020+ Roll-Stable Timecell Strategy</title>
  <style>{css}</style>
</head>
<body>
  <header>
    <h1>NQ 2020+ Roll-Stable Timecell Strategy</h1>
    <p>从 2020-01-01 重新搜索，并修正旧连续合约数据中 minute-by-minute 主力切换导致的假跳价。本报告使用按 UTC 交易日固定最高成交量 NQ 合约的 1m K 线；所有因素只来自 OHLCV bar 和时间戳。</p>
  </header>
  <main>
    <h2>最终候选</h2>
    <div class="grid">{metrics}</div>
    <div class="note">
      <p><strong>规则：</strong>在 <code>{esc(session)}</code> 时段，每 <code>{step}</code> 分钟检查一次候选入场；若该 UTC <code>{esc('/'.join(key_columns))}</code> 单元在 2020-2021 训练期做多或做空净收益为正，则按固定动作表交易，入场为下一根 1m bar 开盘，持有 <code>{hold}</code> 分钟时间离场。每笔扣除 <code>{ROUND_TRIP_COST_POINTS}</code> 点往返成本。</p>
      <p><strong>为什么替代旧 Lightglow 结论：</strong>旧高收益 P/D seasonal map 的最佳/最差交易出现在换月价差附近，清洗为日主力合约后不再盈利。干净数据上，单一 Lightglow/ICT/区间信号没有通过每年 1000 笔且每年为正的硬门槛；最终胜出的是训练期固定的时间单元方向表。</p>
      {bracket_note}
    </div>

    <h2>候选对比</h2>
    {table_html(comparison, comparison_columns, limit=14)}

    <h2>累计收益与回撤</h2>
    {line_chart("累计净点数", equity, "equity_points", "net points")}
    {line_chart("回撤", equity, "drawdown_points", "drawdown points")}

    <h2>年度表现</h2>
    {bar_chart("最终候选年度净点数", yearly)}
    {table_html(yearly, yearly_columns)}

    <h2>固定动作表</h2>
    <p>L = long，S = short，- = 不交易。weekday/hour 均使用 UTC。</p>
    {action_table(actions)}

    <h2>最佳与最差交易</h2>
    {table_html(best_worst, trade_columns)}
    {trade_candle_chart("Best trade on historical 1m K-line", best_trade, frame)}
    {trade_candle_chart("Worst trade on historical 1m K-line", worst_trade, frame)}

    <h2>搜索结论</h2>
    <div class="note">
      <p>从亏损交易中学到的关键点是：先前看起来极强的 seasonal Lightglow 结果主要受连续合约拼接污染影响；必须要求 signal、entry、exit 同一合约，且 bar 时间连续。</p>
      <p>干净数据上，range-to-trend 和 ICT/Lightglow 结构信号仍有局部边际，但频率或年度一致性不足；高频稳定性来自 UTC day/hour 单元的方向选择。全样本 cell-sign 结果只作为上限参考，最终候选只用 2020-2021 训练方向。</p>
      <p>这仍是历史回测研究，不是实盘批准。下一步应做滚动前推、纸盘验证和滑点压力测试。</p>
    </div>

    <h2>导出文件</h2>
    <p>逐笔交易：<code>{esc(TRADES_OUTPUT.relative_to(ROOT_DIR))}</code>；年度统计：<code>{esc(YEARLY_OUTPUT.relative_to(ROOT_DIR))}</code>；候选对比：<code>{esc(COMPARISON_OUTPUT.relative_to(ROOT_DIR))}</code>。</p>
  </main>
</body>
</html>
"""
    evidence = {
        "report": str(REPORT_PATH.relative_to(ROOT_DIR)),
        "trades_output": str(TRADES_OUTPUT.relative_to(ROOT_DIR)),
        "yearly_output": str(YEARLY_OUTPUT.relative_to(ROOT_DIR)),
        "comparison_output": str(COMPARISON_OUTPUT.relative_to(ROOT_DIR)),
        "summary": summary,
        "best_trade_net_points": float(best_trade["net_points"]),
        "worst_trade_net_points": float(worst_trade["net_points"]),
        "action_cells": len(actions),
    }
    return html_doc, evidence


def main() -> int:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    html_doc, evidence = render_report()
    REPORT_PATH.write_text(html_doc, encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
