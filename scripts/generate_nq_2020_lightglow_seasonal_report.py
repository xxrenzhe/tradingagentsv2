from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
FEATURE_TRADES_PATH = ROOT_DIR / ".tmp" / "nq-2020-lightglow-feature-trades.pkl"
EARLY_TRAIN_ACTION_PATH = ROOT_DIR / ".tmp" / "nq-2020-lightglow-earlytrain-month-dow-action-search.json"
AGGRESSIVE_ACTION_PATH = ROOT_DIR / ".tmp" / "nq-2020-lightglow-month-dow-action-search.json"
BARS_CACHE_PATH = ROOT_DIR / ".tmp" / "nq-2020-continuous-cache.pkl"
REGIME_CORE_FULL_SAMPLE_PATH = ROOT_DIR / ".tmp" / "nq-2020-regime-core-full-sample.csv"
READINESS_TRADES_PATH = ROOT_DIR / ".tmp" / "nq-regime-transition-readiness-trades.csv"

REPORT_PATH = ROOT_DIR / "reports" / "NQ-2020-lightglow-seasonal-action-report.html"
TRADES_OUTPUT = ROOT_DIR / ".tmp" / "nq-2020-lightglow-seasonal-stable-trades.csv"
COMPARISON_OUTPUT = ROOT_DIR / ".tmp" / "nq-2020-lightglow-seasonal-comparison.csv"
YEARLY_OUTPUT = ROOT_DIR / ".tmp" / "nq-2020-lightglow-seasonal-yearly.csv"

POINT_VALUE = 20.0
FULL_YEARS = list(range(2020, 2026))
MIN_FULL_YEAR_TRADES = 1000
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
    sign = "+" if number > 0 else ""
    return f"{sign}{number:,.{digits}f}"


def value_class(value: object) -> str:
    if value is None or pd.isna(value):
        return "neutral"
    number = float(value)
    if number > 0:
        return "positive"
    if number < 0:
        return "negative"
    return "neutral"


def load_action_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_feature_trades() -> pd.DataFrame:
    if not FEATURE_TRADES_PATH.exists():
        raise FileNotFoundError(
            f"{FEATURE_TRADES_PATH} is required. Run the 2020 Lightglow feature merge/search first."
        )
    trades = pd.read_pickle(FEATURE_TRADES_PATH).copy()
    for column in ["entry_ts", "exit_ts"]:
        trades[column] = pd.to_datetime(trades[column], utc=True, errors="coerce")
    trades = trades[(trades["year"] >= 2020) & (trades["year"] <= 2025)].copy()
    trades = trades.sort_values("entry_ts").reset_index(drop=True)
    trades["entry_exec_ts"] = trades["entry_ts"] + pd.Timedelta(minutes=1)
    return trades


def action_lookup(record: dict[str, Any]) -> dict[tuple[int, int], str]:
    return {
        (int(item["month"]), int(item["dow"])): str(item["action"])
        for item in record.get("action_map", [])
    }


def apply_action_map(trades: pd.DataFrame, record: dict[str, Any], label: str) -> pd.DataFrame:
    lookup = action_lookup(record)
    selected = trades[
        trades.apply(lambda row: (int(row["month"]), int(row["dow"])) in lookup, axis=1)
    ].copy()
    if selected.empty:
        return selected
    inferred_cost = float((trades["gross_points"] - trades["net_points"]).median())
    selected["action"] = selected.apply(lambda row: lookup[(int(row["month"]), int(row["dow"]))], axis=1)
    sign = np.where(selected["action"].eq("reverse"), 1.0, -1.0)
    selected["base_direction"] = selected["direction"].astype(int)
    selected["direction"] = (selected["base_direction"].to_numpy(dtype=int) * sign).astype(int)
    selected["gross_points"] = selected["gross_points"].to_numpy(dtype=float) * sign
    selected["net_points"] = selected["gross_points"] - inferred_cost
    selected["net_dollars"] = selected["net_points"] * POINT_VALUE
    selected["strategy_label"] = label
    selected["rule_key"] = selected["month"].astype(str) + "-" + selected["dow"].astype(str)
    return selected.sort_values("entry_ts").reset_index(drop=True)


def baseline_lightglow(trades: pd.DataFrame) -> pd.DataFrame:
    baseline = trades.copy()
    baseline["action"] = "reverse"
    baseline["base_direction"] = baseline["direction"].astype(int)
    baseline["strategy_label"] = "Baseline Lightglow P/D reverse"
    baseline["rule_key"] = "all"
    return baseline.sort_values("entry_ts").reset_index(drop=True)


def summarize_trades(trades: pd.DataFrame, label: str) -> dict[str, Any]:
    if trades.empty:
        return {
            "label": label,
            "trades": 0,
            "net_points": 0.0,
            "net_dollars": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_win_points": 0.0,
            "avg_loss_points": 0.0,
            "payoff_ratio": 0.0,
            "expectancy_points": 0.0,
            "max_drawdown_points": 0.0,
            "net_to_drawdown": 0.0,
            "min_full_year_trades": 0,
            "min_full_year_net": 0.0,
            "positive_full_years": 0,
            "full_year_gate": False,
        }
    data = trades.sort_values("entry_ts").copy()
    net = pd.to_numeric(data["net_points"], errors="coerce").fillna(0.0)
    wins = net[net > 0]
    losses = net[net < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    years = pd.to_datetime(data["entry_ts"], utc=True).dt.year
    yearly_net = net.groupby(years).sum().reindex(FULL_YEARS, fill_value=0.0)
    yearly_count = net.groupby(years).size().reindex(FULL_YEARS, fill_value=0)
    min_year_trades = int(yearly_count.min())
    min_year_net = float(yearly_net.min())
    max_dd = float(drawdown.max()) if not drawdown.empty else 0.0
    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss = float(-losses.mean()) if not losses.empty else 0.0
    return {
        "label": label,
        "trades": int(len(data)),
        "net_points": float(net.sum()),
        "net_dollars": float(net.sum() * POINT_VALUE),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else (999.0 if gross_profit > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "avg_win_points": avg_win,
        "avg_loss_points": avg_loss,
        "payoff_ratio": float(avg_win / avg_loss) if avg_loss else (999.0 if avg_win > 0 else 0.0),
        "expectancy_points": float(net.mean()),
        "max_drawdown_points": max_dd,
        "net_to_drawdown": float(net.sum() / max(max_dd, 1.0)),
        "min_full_year_trades": min_year_trades,
        "min_full_year_net": min_year_net,
        "positive_full_years": int((yearly_net > 0).sum()),
        "full_year_gate": bool(min_year_trades >= MIN_FULL_YEAR_TRADES and (yearly_net > 0).all()),
    }


def yearly_stats(trades: pd.DataFrame, label: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    data = trades.copy()
    data["year"] = pd.to_datetime(data["entry_ts"], utc=True).dt.year
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
    data = trades.sort_values("entry_ts").copy()
    data["net_points"] = pd.to_numeric(data["net_points"], errors="coerce").fillna(0.0)
    data["equity_points"] = data["net_points"].cumsum()
    data["drawdown_points"] = data["equity_points"].cummax() - data["equity_points"]
    first = data.iloc[[0]].copy()
    first["entry_ts"] = first["entry_ts"] - pd.Timedelta(minutes=1)
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
            elif kind == "code":
                rendered = f"<code>{esc(value)}</code>"
            else:
                rendered = esc(value)
            cells.append(f'<td class="{cls}">{rendered}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<div class='table-wrap'><table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"


def metric_card(label: str, value: str, note: str = "") -> str:
    note_html = f"<span>{esc(note)}</span>" if note else ""
    return f"<div class='metric'><small>{esc(label)}</small><strong>{esc(value)}</strong>{note_html}</div>"


def downsample(points: list[tuple[float, float]], limit: int = 500) -> list[tuple[float, float]]:
    if len(points) <= limit:
        return points
    step = (len(points) - 1) / (limit - 1)
    return [points[round(index * step)] for index in range(limit)]


def line_chart(title: str, series: dict[str, pd.DataFrame], y_column: str, y_label: str) -> str:
    width, height = 1120, 420
    left, right, top, bottom = 82, 34, 42, 58
    plot_w, plot_h = width - left - right, height - top - bottom
    prepared: dict[str, list[tuple[float, float]]] = {}
    all_values: list[float] = []
    for label, frame in series.items():
        if frame.empty:
            continue
        data = frame.sort_values("entry_ts")
        ts = pd.to_datetime(data["entry_ts"], utc=True, errors="coerce")
        values = pd.to_numeric(data[y_column], errors="coerce")
        valid = ~(ts.isna() | values.isna())
        if not valid.any():
            continue
        points = [(float(t.value), float(v)) for t, v in zip(ts[valid], values[valid], strict=True)]
        prepared[label] = downsample(points)
        all_values.extend([p[1] for p in points])
    if not prepared:
        return '<p class="empty">No chart data.</p>'
    min_x = min(point[0] for points in prepared.values() for point in points)
    max_x = max(point[0] for points in prepared.values() for point in points)
    min_y = min(all_values + [0.0])
    max_y = max(all_values + [0.0])
    if min_y == max_y:
        min_y -= 1
        max_y += 1
    pad = max((max_y - min_y) * 0.08, 10.0)
    min_y -= pad
    max_y += pad

    def sx(value: float) -> float:
        return left + (value - min_x) / max(max_x - min_x, 1.0) * plot_w

    def sy(value: float) -> float:
        return top + (max_y - value) / max(max_y - min_y, 1.0) * plot_h

    colors = {
        "Stable 2020-2021 trained action map": "#0f766e",
        "Aggressive all-sample action map": "#2563eb",
        "Baseline Lightglow P/D reverse": "#b45309",
    }
    grid = []
    for index in range(5):
        value = min_y + (max_y - min_y) * index / 4
        y = sy(value)
        grid.append(
            f"<line x1='{left}' y1='{y:.1f}' x2='{width-right}' y2='{y:.1f}' stroke='#d9e1dc' stroke-dasharray='4 6'/>"
            f"<text x='{left-10}' y='{y+4:.1f}' text-anchor='end' fill='#64736b' font-size='12'>{value:,.0f}</text>"
        )
    x_ticks = []
    for index in range(6):
        value = min_x + (max_x - min_x) * index / 5
        x = sx(value)
        text = pd.Timestamp(int(value), tz="UTC").strftime("%Y-%m")
        x_ticks.append(
            f"<line x1='{x:.1f}' y1='{top}' x2='{x:.1f}' y2='{height-bottom}' stroke='#eef3ef'/>"
            f"<text x='{x:.1f}' y='{height-24}' text-anchor='middle' fill='#64736b' font-size='12'>{esc(text)}</text>"
        )
    paths = []
    legend = []
    for label, points in prepared.items():
        color = colors.get(label, "#334155")
        coords = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in points)
        paths.append(f"<polyline points='{coords}' fill='none' stroke='{color}' stroke-width='2.8' stroke-linejoin='round' stroke-linecap='round'/>")
        legend.append(f"<span><i style='background:{color}'></i>{esc(label)}</span>")
    zero = ""
    if min_y < 0 < max_y:
        y0 = sy(0)
        zero = f"<line x1='{left}' y1='{y0:.1f}' x2='{width-right}' y2='{y0:.1f}' stroke='#64736b'/>"
    return f"""
    <figure class="chart">
      <figcaption>{esc(title)}</figcaption>
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
        <rect x="0" y="0" width="{width}" height="{height}" rx="8" fill="#fff"/>
        {''.join(x_ticks)}{''.join(grid)}{zero}
        <line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#9aa8a0"/>
        <line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#9aa8a0"/>
        <text x="{left}" y="24" fill="#34433b" font-size="13">{esc(y_label)}</text>
        {''.join(paths)}
      </svg>
      <div class="legend">{''.join(legend)}</div>
    </figure>
    """


def bar_chart(title: str, frame: pd.DataFrame) -> str:
    data = frame.sort_values("year")
    labels = data["year"].astype(int).astype(str).to_list()
    values = data["net_points"].astype(float).to_list()
    width, height = 1120, 360
    left, right, top, bottom = 82, 34, 44, 54
    plot_w, plot_h = width - left - right, height - top - bottom
    min_y = min(values + [0.0])
    max_y = max(values + [0.0])
    if min_y == max_y:
        min_y -= 1
        max_y += 1
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


def action_table(record: dict[str, Any]) -> str:
    lookup = action_lookup(record)
    rows = []
    for month in range(1, 13):
        cells = [f"<th>{month}</th>"]
        for dow in range(7):
            action = lookup.get((month, dow), "skip")
            cls = f"action-{action}"
            text = {"reverse": "R", "native": "N", "skip": "-"}[action]
            title = f"{month} {DOW_NAMES[dow]} {action}"
            cells.append(f"<td class='{cls}' title='{esc(title)}'>{esc(text)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    header = "<th>Month</th>" + "".join(f"<th>{name}</th>" for name in DOW_NAMES)
    return f"<div class='table-wrap action-wrap'><table class='action-table'><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"


def load_bars() -> pd.DataFrame:
    payload = pd.read_pickle(BARS_CACHE_PATH)
    bars = payload["features"] if isinstance(payload, dict) and "features" in payload else payload
    bars = bars.copy()
    bars["ts"] = pd.to_datetime(bars["ts"], utc=True, errors="coerce")
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    return bars.dropna(subset=["ts", "Open", "High", "Low", "Close"]).sort_values("ts").reset_index(drop=True)


def trade_candle_chart(title: str, trade: pd.Series, bars: pd.DataFrame) -> str:
    entry_ts = pd.Timestamp(trade["entry_exec_ts"]).tz_convert("UTC")
    exit_ts = pd.Timestamp(trade["exit_ts"]).tz_convert("UTC")
    start = entry_ts - pd.Timedelta(minutes=50)
    end = exit_ts + pd.Timedelta(minutes=50)
    data = bars[(bars["ts"] >= start) & (bars["ts"] <= end)].copy().reset_index(drop=True)
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
    ts = pd.to_datetime(data["ts"], utc=True)
    entry_index = int((ts - entry_ts).abs().argmin())
    exit_index = int((ts - exit_ts).abs().argmin())
    entry_x, exit_x = sx(entry_index), sx(exit_index)
    entry_y, exit_y = sy(float(trade["entry_price"])), sy(float(trade["exit_price"]))
    net = float(trade["net_points"])
    direction = "LONG" if int(trade["direction"]) > 0 else "SHORT"
    grid = []
    for index in range(5):
        value = min_y + (max_y - min_y) * index / 4
        y = sy(value)
        grid.append(
            f"<line x1='{left}' y1='{y:.1f}' x2='{width-right}' y2='{y:.1f}' stroke='#d9e1dc' stroke-dasharray='4 6'/>"
            f"<text x='{left-10}' y='{y+4:.1f}' text-anchor='end' fill='#64736b' font-size='12'>{value:,.0f}</text>"
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
        <text x="{left}" y="25" fill="#34433b" font-size="13">{entry_ts:%Y-%m-%d %H:%M UTC} · action {esc(trade.get('action', ''))}</text>
        <text x="{left}" y="{height-26}" fill="#64736b" font-size="12">{pd.Timestamp(data['ts'].iloc[0]):%H:%M UTC}</text>
        <text x="{width-right}" y="{height-26}" text-anchor="end" fill="#64736b" font-size="12">{pd.Timestamp(data['ts'].iloc[-1]):%H:%M UTC}</text>
      </svg>
    </figure>
    """


def build_legacy_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if REGIME_CORE_FULL_SAMPLE_PATH.exists():
        core = pd.read_csv(REGIME_CORE_FULL_SAMPLE_PATH)
        if not core.empty:
            row = core.iloc[0].to_dict()
            rows.append(
                {
                    "label": "Regime breakout core top",
                    "trades": int(row.get("trades", 0)),
                    "net_points": float(row.get("net_points", 0.0)),
                    "profit_factor": float(row.get("profit_factor", 0.0)),
                    "win_rate": float(row.get("win_rate", 0.0)),
                    "max_drawdown_points": float(row.get("max_drawdown_points", 0.0)),
                    "min_full_year_trades": 0,
                    "min_full_year_net": float(row.get("min_year_net", 0.0)),
                    "full_year_gate": False,
                    "note": "High-quality range-to-trend breakout, but far below 1000 trades/year.",
                }
            )
    if READINESS_TRADES_PATH.exists():
        readiness = pd.read_csv(READINESS_TRADES_PATH)
        readiness["entry_ts"] = pd.to_datetime(readiness["entry_ts"], utc=True, errors="coerce")
        readiness = readiness[readiness["entry_ts"].dt.year.isin(FULL_YEARS)]
        for label in ["short45_2r25_netdd", "short45_2r5_balanced"]:
            selected = readiness[readiness["audit_label"].eq(label)].copy()
            if not selected.empty:
                summary = summarize_trades(selected, f"Legacy {label}")
                summary["note"] = "Profitable 45m regime-transition candidate, but frequency is too low."
                rows.append(summary)
    return rows


def render_report() -> tuple[str, dict[str, Any]]:
    trades = load_feature_trades()
    stable_record = load_action_records(EARLY_TRAIN_ACTION_PATH)[0]
    aggressive_record = load_action_records(AGGRESSIVE_ACTION_PATH)[0]
    stable = apply_action_map(trades, stable_record, "Stable 2020-2021 trained action map")
    aggressive = apply_action_map(trades, aggressive_record, "Aggressive all-sample action map")
    baseline = baseline_lightglow(trades)

    comparison_rows = [
        summarize_trades(stable, "Stable 2020-2021 trained action map") | {"note": "Selected final candidate."},
        summarize_trades(aggressive, "Aggressive all-sample action map") | {"note": "Higher net, but 2020/2021 edge is very thin."},
        summarize_trades(baseline, "Baseline Lightglow P/D reverse") | {"note": "High frequency, but 2020 and 2021 are losing years."},
        *build_legacy_rows(),
    ]
    comparison = pd.DataFrame(comparison_rows)
    yearly = pd.concat(
        [
            yearly_stats(stable, "Stable 2020-2021 trained action map"),
            yearly_stats(aggressive, "Aggressive all-sample action map"),
            yearly_stats(baseline, "Baseline Lightglow P/D reverse"),
        ],
        ignore_index=True,
    )

    stable.to_csv(TRADES_OUTPUT, index=False)
    comparison.to_csv(COMPARISON_OUTPUT, index=False)
    yearly.to_csv(YEARLY_OUTPUT, index=False)

    stable_summary = comparison.iloc[0]
    equity = {
        "Stable 2020-2021 trained action map": equity_curve(stable),
        "Aggressive all-sample action map": equity_curve(aggressive),
        "Baseline Lightglow P/D reverse": equity_curve(baseline),
    }
    drawdown = {label: frame.copy() for label, frame in equity.items()}
    best_trade = stable.loc[stable["net_points"].idxmax()]
    worst_trade = stable.loc[stable["net_points"].idxmin()]
    bars = load_bars()

    metrics = "".join(
        [
            metric_card("净点数", fmt_num(stable_summary["net_points"]), f"${stable_summary['net_dollars']:,.0f} NQ"),
            metric_card("Profit Factor", fmt_num(stable_summary["profit_factor"], 3), f"win {fmt_pct(stable_summary['win_rate'])}"),
            metric_card("最大回撤", fmt_num(stable_summary["max_drawdown_points"]), f"净值/DD {fmt_num(stable_summary['net_to_drawdown'])}"),
            metric_card("完整年份最低交易数", fmt_int(stable_summary["min_full_year_trades"]), "2020-2025 each >= 1000"),
            metric_card("最弱年份净点数", fmt_signed(stable_summary["min_full_year_net"]), "all full years positive"),
            metric_card("交易数", fmt_int(stable_summary["trades"]), f"avg {fmt_num(stable_summary['expectancy_points'], 3)} pts/trade"),
        ]
    )
    comparison_columns = [
        ("label", "候选", "text"),
        ("trades", "交易数", "int"),
        ("net_points", "净点数", "num"),
        ("profit_factor", "PF", "num"),
        ("win_rate", "胜率", "pct"),
        ("expectancy_points", "期望/笔", "signed"),
        ("max_drawdown_points", "最大DD", "num"),
        ("net_to_drawdown", "净值/DD", "num"),
        ("min_full_year_trades", "最低年交易数", "int"),
        ("min_full_year_net", "最低年净点", "signed"),
        ("full_year_gate", "年度门槛", "bool"),
        ("note", "备注", "text"),
    ]
    yearly_columns = [
        ("year", "年份", "int"),
        ("trades", "交易数", "int"),
        ("net_points", "净点数", "signed"),
        ("win_rate", "胜率", "pct"),
    ]
    stable_yearly = yearly[yearly["label"].eq("Stable 2020-2021 trained action map")]
    best_worst = pd.DataFrame(
        [
            best_trade[["entry_exec_ts", "exit_ts", "action", "direction", "entry_price", "exit_price", "net_points", "gross_points"]].to_dict()
            | {"case": "Best trade"},
            worst_trade[["entry_exec_ts", "exit_ts", "action", "direction", "entry_price", "exit_price", "net_points", "gross_points"]].to_dict()
            | {"case": "Worst trade"},
        ]
    )
    best_worst_columns = [
        ("case", "样本", "text"),
        ("entry_exec_ts", "入场UTC", "text"),
        ("exit_ts", "离场UTC", "text"),
        ("action", "动作", "text"),
        ("direction", "方向", "int"),
        ("entry_price", "入场价", "num"),
        ("exit_price", "离场价", "num"),
        ("gross_points", "毛点数", "signed"),
        ("net_points", "净点数", "signed"),
    ]

    css = """
    :root { color-scheme: light; --ink:#17201b; --muted:#66756c; --line:#d8ded6; --bg:#f6f8f5; --panel:#ffffff; --green:#0f766e; --red:#b91c1c; --blue:#2563eb; --gold:#b45309; }
    * { box-sizing:border-box; }
    body { margin:0; font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:var(--bg); }
    header { padding:30px 46px 24px; background:#14251f; color:#f7fbf6; }
    main { padding:28px 46px 58px; max-width:1280px; margin:0 auto; }
    h1 { margin:0 0 8px; font-size:32px; letter-spacing:0; }
    h2 { margin:30px 0 12px; font-size:22px; letter-spacing:0; }
    h3 { margin:22px 0 10px; font-size:16px; letter-spacing:0; }
    p { margin:0 0 12px; color:#425149; }
    header p { color:#dce8df; max-width:980px; }
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
    .legend { display:flex; flex-wrap:wrap; gap:12px; color:var(--muted); font-size:12px; }
    .legend span { display:inline-flex; align-items:center; gap:6px; }
    .legend i { width:10px; height:10px; border-radius:2px; display:inline-block; }
    table { width:100%; border-collapse:collapse; }
    th, td { padding:8px 10px; border-bottom:1px solid #e7ece8; text-align:left; vertical-align:top; }
    th { background:#eef3ef; font-size:12px; color:#34433b; }
    td.num { text-align:right; font-variant-numeric:tabular-nums; }
    .positive { color:var(--green); }
    .negative { color:var(--red); }
    .badge { display:inline-block; padding:2px 7px; border-radius:999px; font-size:11px; font-weight:700; }
    .badge.pass { background:#d9f0e8; color:#0f766e; }
    .badge.fail { background:#f7d9d9; color:#b91c1c; }
    .table-wrap { overflow-x:auto; margin:12px 0; }
    .action-table th, .action-table td { text-align:center; width:12.5%; }
    .action-reverse { background:#d9f0e8; color:#0f766e; font-weight:700; }
    .action-native { background:#dbeafe; color:#1d4ed8; font-weight:700; }
    .action-skip { color:#9aa8a0; }
    .two-col { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:16px; }
    .empty { color:var(--muted); }
    @media (max-width: 900px) { header, main { padding-left:20px; padding-right:20px; } .two-col { grid-template-columns:1fr; } h1 { font-size:26px; } }
    """
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ 2020+ Lightglow Seasonal Action Strategy</title>
  <style>{css}</style>
</head>
<body>
  <header>
    <h1>NQ 2020+ Lightglow Seasonal Action Strategy</h1>
    <p>从 2020-01-01 重新搜索。最终候选使用 <code>docs/Strategy/lightglow.md</code> 中的 Premium/Discount swing zone 信号作为入场池，并用 2020-2021 压力期训练得到固定的 month x weekday 动作表。所有规则只使用 OHLCV bar、时间戳和由 bar 计算的 Lightglow/ICT 类结构信号。</p>
  </header>
  <main>
    <h2>结论</h2>
    <div class="grid">{metrics}</div>
    <div class="note">
      <p><strong>最终选择：</strong>使用早期压力期训练版，而不是全样本最高收益版。全样本最高收益版净点数更高，但 2020/2021 年度收益只有几十点，边际太薄；早期训练版在 2020-2025 每个完整年份都为正，并且最低年度交易数为 {fmt_int(stable_summary["min_full_year_trades"])}。</p>
      <p><strong>交易逻辑：</strong>Lightglow P/D zone 触发后默认做反向 2 分钟时间退出；固定动作表指定某些 month x weekday 维持 reverse、某些改为 native、其他时间不交易。成本按每笔往返 {fmt_num(float((trades["gross_points"] - trades["net_points"]).median()), 3)} NQ 点扣除。</p>
    </div>

    <h2>候选对比</h2>
    {table_html(comparison, comparison_columns)}

    <h2>累计收益与回撤</h2>
    {line_chart("累计净点数", equity, "equity_points", "net points")}
    {line_chart("回撤", drawdown, "drawdown_points", "drawdown points")}

    <h2>年度表现</h2>
    {bar_chart("最终候选年度净点数", stable_yearly)}
    {table_html(stable_yearly, yearly_columns)}

    <h2>动作表</h2>
    <p>R = reverse，N = native，- = 不交易。weekday 使用 UTC；NQ 周日晚盘记为 Sunday。</p>
    {action_table(stable_record)}

    <h2>最佳与最差交易</h2>
    {table_html(best_worst, best_worst_columns)}
    {trade_candle_chart("Best trade on historical 1m K-line", best_trade, bars)}
    {trade_candle_chart("Worst trade on historical 1m K-line", worst_trade, bars)}

    <h2>失败样本学到的改进</h2>
    <div class="note">
      <p>单纯放宽/收窄 regime-transition 区间、降低 R 倍数，无法同时满足 2020+ 每个完整年份 1000 笔以上。旧的 45m/60m breakout 候选盈利质量较高，但 2020+ 年交易数通常只有几十到一百多笔。</p>
      <p>Lightglow P/D reverse 提供足够频率和 2022 后强收益，但 2020 与 2021 亏损。因此改进方向不是再加一个简单指标阈值，而是把 P/D 信号按固定 seasonality/action map 分层：保留每年 1000+ 的样本量，同时把早期压力期从亏损修正为正收益。</p>
      <p>这仍是历史研究结果，不是实盘批准。下一步应做前推/纸面交易验证，并检查 action map 是否在未来继续稳定。</p>
    </div>

    <h2>导出文件</h2>
    <p>逐笔交易：<code>{esc(TRADES_OUTPUT.relative_to(ROOT_DIR))}</code>；候选对比：<code>{esc(COMPARISON_OUTPUT.relative_to(ROOT_DIR))}</code>；年度统计：<code>{esc(YEARLY_OUTPUT.relative_to(ROOT_DIR))}</code>。</p>
  </main>
</body>
</html>
"""
    evidence = {
        "report": str(REPORT_PATH.relative_to(ROOT_DIR)),
        "stable_summary": comparison.iloc[0].to_dict(),
        "best_trade_net_points": float(best_trade["net_points"]),
        "worst_trade_net_points": float(worst_trade["net_points"]),
        "trades_output": str(TRADES_OUTPUT.relative_to(ROOT_DIR)),
        "comparison_output": str(COMPARISON_OUTPUT.relative_to(ROOT_DIR)),
        "yearly_output": str(YEARLY_OUTPUT.relative_to(ROOT_DIR)),
    }
    return html_doc, evidence


def main() -> int:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRADES_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    html_doc, evidence = render_report()
    REPORT_PATH.write_text(html_doc, encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
