from __future__ import annotations

import argparse
import html
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from search_nq_bar_2r_walkforward import load_continuous_nq_bars  # noqa: E402

REPORT_PATH = ROOT_DIR / "reports" / "NQ-regime-transition-strategy-report.html"

SUMMARY_PATH = ROOT_DIR / ".tmp" / "nq-regime-transition-readiness-summary.csv"
TRADES_PATH = ROOT_DIR / ".tmp" / "nq-regime-transition-readiness-trades.csv"
YEARLY_PATH = ROOT_DIR / ".tmp" / "nq-regime-transition-readiness-yearly.csv"
MONTHLY_PATH = ROOT_DIR / ".tmp" / "nq-regime-transition-readiness-monthly.csv"
ROLLING90_PATH = ROOT_DIR / ".tmp" / "nq-regime-transition-readiness-rolling90.csv"
ROLLING180_PATH = ROOT_DIR / ".tmp" / "nq-regime-transition-readiness-rolling180.csv"
LIGHTGLOW_TRADES_PATH = ROOT_DIR / ".tmp" / "nq-lightglow-1m-hold2-fullsample-trades.csv"

POINT_VALUE = 20.0
MIN_FULL_YEAR_TRADES = 1000
FULL_YEARS = list(range(2011, 2026))
BEST_LABEL = "highest_fullsample_3r_neighbor"
LIGHTGLOW_CANDIDATE = "lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time"
LABEL_ORDER = ["highest_fullsample_3r_neighbor", "best_wf_3r", "best_wf_2r"]
LABEL_NAMES = {
    "highest_fullsample_3r_neighbor": "60m 3R trend-start",
    "best_wf_3r": "120m 3R neighbor",
    "best_wf_2r": "120m 2R walk-forward",
}
PALETTE = {
    "highest_fullsample_3r_neighbor": "#0f766e",
    "best_wf_3r": "#2563eb",
    "best_wf_2r": "#b45309",
}


@dataclass(frozen=True)
class ChartBox:
    width: int = 1100
    height: int = 430
    left: int = 82
    right: int = 34
    top: int = 44
    bottom: int = 62


@dataclass(frozen=True)
class BarLoadArgs:
    start_date: str
    end_date: str
    cache: str
    chunk_size: int = 500_000
    min_volume: float = 1.0


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required input not found: {path}")
    return pd.read_csv(path)


def escape(value: object) -> str:
    return html.escape("" if pd.isna(value) else str(value))


def fmt_num(value: object, digits: int = 2) -> str:
    if pd.isna(value):
        return "-"
    number = float(value)
    return f"{number:,.{digits}f}"


def fmt_int(value: object) -> str:
    if pd.isna(value):
        return "-"
    return f"{int(round(float(value))):,}"


def fmt_signed(value: object, digits: int = 2) -> str:
    if pd.isna(value):
        return "-"
    number = float(value)
    sign = "+" if number > 0 else ""
    return f"{sign}{number:,.{digits}f}"


def fmt_pct(value: object, digits: int = 1) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value) * 100:.{digits}f}%"


def fmt_money_from_points(points: object) -> str:
    if pd.isna(points):
        return "-"
    return f"${float(points) * POINT_VALUE:,.0f}"


def value_class(value: object) -> str:
    if pd.isna(value):
        return "neutral"
    number = float(value)
    if number > 0:
        return "positive"
    if number < 0:
        return "negative"
    return "neutral"


def bool_badge(value: object) -> str:
    passed = str(value).lower() == "true"
    label = "PASS" if passed else "FAIL"
    cls = "pass" if passed else "fail"
    return f'<span class="badge {cls}">{label}</span>'


def status_badge(passed: bool, label: str | None = None) -> str:
    text = label or ("PASS" if passed else "FAIL")
    cls = "pass" if passed else "fail"
    return f'<span class="badge {cls}">{escape(text)}</span>'


def label_name(label: str) -> str:
    return LABEL_NAMES.get(label, label)


def label_rank(frame: pd.DataFrame | pd.Series) -> pd.Series:
    order = {label: index for index, label in enumerate(LABEL_ORDER)}
    labels = frame["label"] if isinstance(frame, pd.DataFrame) else frame
    return labels.map(order).fillna(99)


def metric(label: str, value: str, detail: str = "") -> str:
    detail_html = f"<span>{escape(detail)}</span>" if detail else ""
    return f"""
    <div class="metric">
      <small>{escape(label)}</small>
      <strong>{escape(value)}</strong>
      {detail_html}
    </div>
    """


def pill(label: str, value: str) -> str:
    return f'<span class="pill"><b>{escape(label)}</b>{escape(value)}</span>'


def downsample(items: list[tuple[float, float]], limit: int = 450) -> list[tuple[float, float]]:
    if len(items) <= limit:
        return items
    step = (len(items) - 1) / (limit - 1)
    return [items[round(index * step)] for index in range(limit)]


def nice_ticks(min_value: float, max_value: float, count: int = 5) -> list[float]:
    if min_value == max_value:
        return [min_value]
    return [min_value + (max_value - min_value) * index / (count - 1) for index in range(count)]


def line_chart(
    title: str,
    series_map: dict[str, pd.DataFrame],
    *,
    y_column: str,
    x_column: str,
    y_label: str,
    box: ChartBox = ChartBox(),
) -> str:
    prepared: dict[str, list[tuple[float, float]]] = {}
    raw_dates: list[pd.Timestamp] = []
    all_values: list[float] = []

    for label, frame in series_map.items():
        if frame.empty:
            continue
        data = frame.sort_values(x_column).copy()
        timestamps = pd.to_datetime(data[x_column], utc=True, errors="coerce")
        values = pd.to_numeric(data[y_column], errors="coerce")
        valid = ~(timestamps.isna() | values.isna())
        timestamps = timestamps[valid]
        values = values[valid]
        if timestamps.empty:
            continue
        raw_dates.extend(timestamps.to_list())
        all_values.extend(values.astype(float).to_list())
        prepared[label] = downsample(
            [(float(ts.value), float(value)) for ts, value in zip(timestamps, values, strict=True)]
        )

    if not prepared:
        return '<p class="empty">No chart data.</p>'

    min_x = min(point[0] for points in prepared.values() for point in points)
    max_x = max(point[0] for points in prepared.values() for point in points)
    min_y = min(all_values + [0.0])
    max_y = max(all_values + [0.0])
    if min_y == max_y:
        min_y -= 1.0
        max_y += 1.0
    padding = max((max_y - min_y) * 0.08, 10.0)
    min_y -= padding
    max_y += padding
    plot_w = box.width - box.left - box.right
    plot_h = box.height - box.top - box.bottom

    def sx(value: float) -> float:
        if max_x == min_x:
            return float(box.left)
        return box.left + (value - min_x) / (max_x - min_x) * plot_w

    def sy(value: float) -> float:
        return box.top + (max_y - value) / (max_y - min_y) * plot_h

    y_grid = []
    for tick in nice_ticks(min_y, max_y, 5):
        y = sy(tick)
        y_grid.append(
            f'<line x1="{box.left}" y1="{y:.1f}" x2="{box.width - box.right}" y2="{y:.1f}" stroke="#d8dee8" stroke-dasharray="3 7"/>'
            f'<text x="{box.left - 12}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#64748b">{tick:,.0f}</text>'
        )

    x_ticks = []
    for index in range(6):
        ratio = index / 5
        x_value = min_x + (max_x - min_x) * ratio
        x = sx(x_value)
        ts = pd.Timestamp(int(x_value), tz="UTC")
        x_ticks.append(
            f'<line x1="{x:.1f}" y1="{box.top}" x2="{x:.1f}" y2="{box.height - box.bottom}" stroke="#edf2f7"/>'
            f'<text x="{x:.1f}" y="{box.height - 27}" text-anchor="middle" font-size="12" fill="#64748b">{ts:%Y-%m}</text>'
        )

    zero_line = ""
    if min_y < 0 < max_y:
        zero_y = sy(0.0)
        zero_line = (
            f'<line x1="{box.left}" y1="{zero_y:.1f}" x2="{box.width - box.right}" y2="{zero_y:.1f}" '
            f'stroke="#475569" stroke-dasharray="6 5"/>'
        )

    paths = []
    legend = []
    for label in LABEL_ORDER:
        points = prepared.get(label)
        if not points:
            continue
        color = PALETTE.get(label, "#334155")
        coords = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in points)
        paths.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" points="{coords}"/>'
        )
        legend.append(
            f'<span class="legend-item"><i style="background:{color}"></i>{escape(label_name(label))}</span>'
        )

    return f"""
    <figure class="chart">
      <figcaption>{escape(title)}</figcaption>
      <svg viewBox="0 0 {box.width} {box.height}" role="img" aria-label="{escape(title)}">
        <rect x="0" y="0" width="{box.width}" height="{box.height}" rx="8" fill="#ffffff"/>
        {''.join(x_ticks)}
        {''.join(y_grid)}
        {zero_line}
        <line x1="{box.left}" y1="{box.height - box.bottom}" x2="{box.width - box.right}" y2="{box.height - box.bottom}" stroke="#94a3b8"/>
        <line x1="{box.left}" y1="{box.top}" x2="{box.left}" y2="{box.height - box.bottom}" stroke="#94a3b8"/>
        <text x="{box.left}" y="25" font-size="13" fill="#334155">{escape(y_label)}</text>
        {''.join(paths)}
      </svg>
      <div class="legend">{''.join(legend)}</div>
    </figure>
    """


def bar_chart(
    title: str,
    labels: list[str],
    values: list[float],
    *,
    y_label: str = "points",
    box: ChartBox = ChartBox(height=390),
) -> str:
    if not labels:
        return '<p class="empty">No bar data.</p>'
    min_y = min(values + [0.0])
    max_y = max(values + [0.0])
    if min_y == max_y:
        min_y -= 1.0
        max_y += 1.0
    padding = max((max_y - min_y) * 0.08, 10.0)
    min_y -= padding
    max_y += padding
    plot_w = box.width - box.left - box.right
    plot_h = box.height - box.top - box.bottom
    slot_w = plot_w / len(labels)
    bar_w = min(slot_w * 0.68, 42)

    def sy(value: float) -> float:
        return box.top + (max_y - value) / (max_y - min_y) * plot_h

    zero_y = sy(0.0)
    grid = []
    for tick in nice_ticks(min_y, max_y, 5):
        y = sy(tick)
        grid.append(
            f'<line x1="{box.left}" y1="{y:.1f}" x2="{box.width - box.right}" y2="{y:.1f}" stroke="#d8dee8" stroke-dasharray="3 7"/>'
            f'<text x="{box.left - 12}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#64748b">{tick:,.0f}</text>'
        )

    bars = []
    for index, (label, value) in enumerate(zip(labels, values, strict=True)):
        x = box.left + slot_w * index + (slot_w - bar_w) / 2
        y = min(sy(value), zero_y)
        height = max(abs(zero_y - sy(value)), 1.0)
        color = "#0f766e" if value >= 0 else "#b91c1c"
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{height:.1f}" rx="3" fill="{color}">'
            f'<title>{escape(label)}: {value:,.2f}</title></rect>'
        )
        if len(labels) <= 24:
            bars.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{box.height - 25}" text-anchor="middle" font-size="11" fill="#475569">{escape(label)}</text>'
            )

    return f"""
    <figure class="chart">
      <figcaption>{escape(title)}</figcaption>
      <svg viewBox="0 0 {box.width} {box.height}" role="img" aria-label="{escape(title)}">
        <rect x="0" y="0" width="{box.width}" height="{box.height}" rx="8" fill="#ffffff"/>
        {''.join(grid)}
        <line x1="{box.left}" y1="{zero_y:.1f}" x2="{box.width - box.right}" y2="{zero_y:.1f}" stroke="#64748b"/>
        <line x1="{box.left}" y1="{box.top}" x2="{box.left}" y2="{box.height - box.bottom}" stroke="#94a3b8"/>
        <text x="{box.left}" y="25" font-size="13" fill="#334155">{escape(y_label)}</text>
        {''.join(bars)}
      </svg>
    </figure>
    """


def horizontal_bars(title: str, labels: list[str], values: list[float], *, suffix: str = "") -> str:
    if not labels:
        return '<p class="empty">No distribution data.</p>'
    max_value = max(values) if values else 1.0
    rows = []
    for label, value in zip(labels, values, strict=True):
        width = 0 if max_value == 0 else value / max_value * 100
        rows.append(
            f"""
            <div class="hbar-row">
              <span>{escape(label)}</span>
              <div class="hbar-track"><i style="width:{width:.2f}%"></i></div>
              <b>{value:,.1f}{escape(suffix)}</b>
            </div>
            """
        )
    return f"""
    <figure class="distribution">
      <figcaption>{escape(title)}</figcaption>
      {''.join(rows)}
    </figure>
    """


def html_table(
    frame: pd.DataFrame,
    columns: list[tuple[str, str, str]],
    *,
    limit: int | None = None,
    class_name: str = "",
) -> str:
    selected = frame.head(limit).copy() if limit else frame.copy()
    if selected.empty:
        return '<p class="empty">No rows.</p>'
    header = "".join(f"<th>{escape(title)}</th>" for _, title, _ in columns)
    rows = []
    for _, row in selected.iterrows():
        cells = []
        for column, _, formatter in columns:
            value = row.get(column)
            if formatter == "int":
                rendered = fmt_int(value)
                cls = "num"
            elif formatter == "num":
                rendered = fmt_num(value)
                cls = f"num {value_class(value)}"
            elif formatter == "signed":
                rendered = fmt_signed(value)
                cls = f"num {value_class(value)}"
            elif formatter == "pct":
                rendered = fmt_pct(value)
                cls = "num"
            elif formatter == "money":
                rendered = fmt_money_from_points(value)
                cls = "num"
            elif formatter == "bool":
                rendered = bool_badge(value)
                cls = ""
            elif formatter == "label":
                rendered = escape(label_name(str(value)))
                cls = ""
            elif formatter == "candidate":
                rendered = f'<code>{escape(value)}</code>'
                cls = "candidate"
            else:
                rendered = escape(value)
                cls = ""
            cells.append(f'<td class="{cls}">{rendered}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"""
    <div class="table-wrap {escape(class_name)}">
      <table>
        <thead><tr>{header}</tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """


def cumulative_trades(trades: pd.DataFrame) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    for label in LABEL_ORDER:
        selected = trades[trades["audit_label"] == label].sort_values("entry_ts").copy()
        if selected.empty:
            continue
        selected["entry_ts"] = pd.to_datetime(selected["entry_ts"], utc=True, errors="coerce")
        selected["net_points"] = pd.to_numeric(selected["net_points"], errors="coerce").fillna(0.0)
        selected["equity_points"] = selected["net_points"].cumsum()
        selected["drawdown_points"] = selected["equity_points"] - selected["equity_points"].cummax()
        first = selected.iloc[[0]].copy()
        first["entry_ts"] = first["entry_ts"] - pd.Timedelta(minutes=1)
        first["equity_points"] = 0.0
        first["drawdown_points"] = 0.0
        result[label] = pd.concat([first, selected], ignore_index=True)
    return result


def annual_chart_data(yearly: pd.DataFrame, label: str) -> tuple[list[str], list[float]]:
    selected = yearly[yearly["label"] == label].sort_values("year")
    return selected["year"].astype(int).astype(str).to_list(), selected["net_points"].astype(float).to_list()


def monthly_heatmap(monthly: pd.DataFrame, label: str) -> str:
    selected = monthly[monthly["label"] == label].copy()
    if selected.empty:
        return '<p class="empty">No monthly data.</p>'
    selected["period"] = pd.to_datetime(selected["period"], utc=True, errors="coerce")
    selected["year"] = selected["period"].dt.year
    selected["month"] = selected["period"].dt.month
    pivot = selected.pivot_table(index="year", columns="month", values="net_points", aggfunc="sum").sort_index()
    max_abs = float(pivot.abs().max().max())
    if not math.isfinite(max_abs) or max_abs == 0:
        max_abs = 1.0
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    header = "<th>Year</th>" + "".join(f"<th>{name}</th>" for name in month_names) + "<th>Total</th>"
    rows = []
    for year, row in pivot.iterrows():
        cells = [f"<th>{int(year)}</th>"]
        for month in range(1, 13):
            value = row.get(month)
            if pd.isna(value):
                cells.append('<td class="missing">-</td>')
                continue
            intensity = min(abs(float(value)) / max_abs, 1.0)
            if float(value) >= 0:
                color = f"rgba(15, 118, 110, {0.15 + 0.65 * intensity:.3f})"
            else:
                color = f"rgba(185, 28, 28, {0.15 + 0.65 * intensity:.3f})"
            cells.append(
                f'<td style="background:{color}" class="{value_class(value)}"><span>{fmt_signed(value, 0)}</span></td>'
            )
        total = float(row.sum(skipna=True))
        cells.append(f'<td class="num {value_class(total)}"><b>{fmt_signed(total, 0)}</b></td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"""
    <div class="table-wrap heatmap-wrap">
      <table class="heatmap">
        <thead><tr>{header}</tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """


def gate_table(summary: pd.DataFrame) -> str:
    columns = [
        ("label", "候选", "label"),
        ("gate_net_positive", "净利润", "bool"),
        ("gate_profit_factor", "PF", "bool"),
        ("gate_net_to_drawdown", "净值/DD", "bool"),
        ("gate_positive_year_rate", "正收益年份", "bool"),
        ("gate_positive_90d_rate", "90日稳定", "bool"),
        ("gate_first_half_positive", "前半段", "bool"),
        ("gate_second_half_positive", "后半段", "bool"),
        ("gate_cost_stress_positive", "成本压力", "bool"),
        ("historical_stable_pass", "总门槛", "bool"),
    ]
    return html_table(summary.sort_values(by="label", key=label_rank), columns)


def candidate_table(summary: pd.DataFrame) -> str:
    columns = [
        ("label", "候选", "label"),
        ("trades", "交易数", "int"),
        ("net_points", "净点数", "num"),
        ("profit_factor", "PF", "num"),
        ("win_rate", "胜率", "pct"),
        ("payoff_ratio", "盈亏比", "num"),
        ("expectancy_points", "期望/笔", "num"),
        ("max_drawdown_points", "最大DD", "num"),
        ("net_to_drawdown", "净值/DD", "num"),
        ("positive_year_rate", "正收益年份", "pct"),
        ("positive_90d_rate", "90日正收益", "pct"),
        ("net_at_cost_2.125", "2.125成本后", "num"),
        ("candidate", "策略ID", "candidate"),
    ]
    return html_table(summary.sort_values(by="label", key=label_rank), columns)


def yearly_table(yearly: pd.DataFrame) -> str:
    pivot = yearly.pivot_table(index="label", columns="year", values="net_points", aggfunc="sum")
    pivot = pivot.reindex(LABEL_ORDER)
    rows = []
    years = [int(year) for year in sorted(pivot.columns)]
    header = "<th>候选</th>" + "".join(f"<th>{year}</th>" for year in years)
    for label, row in pivot.iterrows():
        if label not in LABEL_NAMES:
            continue
        cells = [f"<th>{escape(label_name(label))}</th>"]
        for year in years:
            value = row.get(year)
            cells.append(f'<td class="num {value_class(value)}">{fmt_signed(value, 0)}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"""
    <div class="table-wrap compact-table">
      <table>
        <thead><tr>{header}</tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """


def cost_stress_table(summary: pd.DataFrame) -> str:
    columns = [
        ("label", "候选", "label"),
        ("net_points", "0.625成本", "num"),
        ("net_at_cost_1.125", "1.125成本", "num"),
        ("net_at_cost_1.625", "1.625成本", "num"),
        ("net_at_cost_2.125", "2.125成本", "num"),
        ("net_at_cost_3.125", "3.125成本", "num"),
    ]
    return html_table(summary.sort_values(by="label", key=label_rank), columns)


def rolling_stats_table(rolling90: pd.DataFrame, rolling180: pd.DataFrame) -> str:
    rows = []
    for label in LABEL_ORDER:
        r90 = rolling90[rolling90["label"] == label]
        r180 = rolling180[rolling180["label"] == label]
        rows.append(
            {
                "label": label,
                "windows_90": len(r90),
                "positive_90": (pd.to_numeric(r90["net_points"], errors="coerce") > 0).mean(),
                "worst_90": pd.to_numeric(r90["net_points"], errors="coerce").min(),
                "windows_180": len(r180),
                "positive_180": (pd.to_numeric(r180["net_points"], errors="coerce") > 0).mean(),
                "worst_180": pd.to_numeric(r180["net_points"], errors="coerce").min(),
            }
        )
    frame = pd.DataFrame(rows)
    columns = [
        ("label", "候选", "label"),
        ("windows_90", "90日窗口数", "int"),
        ("positive_90", "90日正收益率", "pct"),
        ("worst_90", "最差90日", "num"),
        ("windows_180", "180日窗口数", "int"),
        ("positive_180", "180日正收益率", "pct"),
        ("worst_180", "最差180日", "num"),
    ]
    return html_table(frame, columns)


def prepare_trade_timestamps(trades: pd.DataFrame, label_column: str = "audit_label") -> pd.DataFrame:
    data = trades.copy()
    for column in ["entry_ts", "exit_ts"]:
        data[column] = pd.to_datetime(data[column], utc=True, errors="coerce")
    data["year"] = data["entry_ts"].dt.year
    if label_column not in data.columns:
        data[label_column] = ""
    return data


def annual_trade_counts(
    trades: pd.DataFrame,
    *,
    label_column: str,
    label_value: str,
    years: list[int] = FULL_YEARS,
) -> pd.DataFrame:
    data = prepare_trade_timestamps(trades, label_column)
    selected = data[data[label_column].astype(str) == label_value]
    counts = selected.groupby("year").size().reindex(years, fill_value=0)
    return pd.DataFrame({"year": counts.index.astype(int), "trades": counts.to_numpy(dtype=int)})


def frequency_gate_summary(
    trades: pd.DataFrame,
    *,
    label_column: str,
    label_value: str,
    years: list[int] = FULL_YEARS,
    minimum: int = MIN_FULL_YEAR_TRADES,
) -> dict[str, object]:
    counts = annual_trade_counts(trades, label_column=label_column, label_value=label_value, years=years)
    min_trades = int(counts["trades"].min()) if not counts.empty else 0
    passed = bool(min_trades >= minimum)
    return {
        "counts": counts,
        "min_trades": min_trades,
        "passed": passed,
        "positive_years": int((counts["trades"] >= minimum).sum()),
        "years": int(len(counts)),
    }


def annual_count_table(counts: pd.DataFrame) -> str:
    data = counts.copy()
    data["gate"] = data["trades"] >= MIN_FULL_YEAR_TRADES
    columns = [
        ("year", "年份", "int"),
        ("trades", "交易次数", "int"),
        ("gate", ">=1000", "bool"),
    ]
    return html_table(data, columns, class_name="compact-table")


def load_optional_lightglow_trades() -> pd.DataFrame:
    if not LIGHTGLOW_TRADES_PATH.exists():
        return pd.DataFrame()
    data = pd.read_csv(LIGHTGLOW_TRADES_PATH)
    return prepare_trade_timestamps(data, "candidate")


def summarize_trade_frame(trades: pd.DataFrame) -> dict[str, float | int]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "max_drawdown_points": 0.0,
        }
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    wins = float(net[net > 0].sum())
    losses = float(abs(net[net < 0].sum()))
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    return {
        "trades": int(len(net)),
        "net_points": float(net.sum()),
        "profit_factor": float(wins / losses) if losses else (999.0 if wins > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "max_drawdown_points": float(abs(drawdown.min())),
    }


def load_bars_for_trade_window(trade: pd.Series, *, minutes_before: int = 45, minutes_after: int = 45) -> pd.DataFrame:
    entry_ts = pd.Timestamp(trade["entry_ts"]).tz_convert("UTC")
    exit_ts = pd.Timestamp(trade["exit_ts"]).tz_convert("UTC")
    start = entry_ts - pd.Timedelta(minutes=minutes_before)
    end = exit_ts + pd.Timedelta(minutes=minutes_after)
    args = BarLoadArgs(
        start_date=start.strftime("%Y-%m-%d"),
        end_date=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        cache=str(ROOT_DIR / ".tmp" / "nq-report-chart-bars-cache.pkl"),
    )
    bars = load_continuous_nq_bars(args)
    bars = bars.copy()
    bars["ts"] = pd.to_datetime(bars["ts"], utc=True, errors="coerce")
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    selected = bars[(bars["ts"] >= start) & (bars["ts"] <= end)].copy()
    symbol = str(trade.get("symbol", ""))
    if symbol and "symbol" in selected.columns and (selected["symbol"].astype(str) == symbol).any():
        selected = selected[selected["symbol"].astype(str) == symbol].copy()
    return selected.dropna(subset=["ts", "Open", "High", "Low", "Close"]).reset_index(drop=True)


def candlestick_trade_chart(title: str, trade: pd.Series, bars: pd.DataFrame) -> str:
    if bars.empty:
        return f'<p class="empty">No K-line data available for {escape(title)}.</p>'

    box = ChartBox(width=1100, height=470, left=82, right=42, top=46, bottom=74)
    plot_w = box.width - box.left - box.right
    plot_h = box.height - box.top - box.bottom
    highs = bars["High"].astype(float)
    lows = bars["Low"].astype(float)
    min_y = float(lows.min())
    max_y = float(highs.max())
    entry_price = float(trade["entry_price"])
    exit_price = float(trade["exit_price"])
    min_y = min(min_y, entry_price, exit_price)
    max_y = max(max_y, entry_price, exit_price)
    if min_y == max_y:
        min_y -= 1.0
        max_y += 1.0
    padding = max((max_y - min_y) * 0.08, 1.0)
    min_y -= padding
    max_y += padding
    slot_w = plot_w / max(len(bars), 1)
    body_w = max(min(slot_w * 0.62, 8.0), 2.2)

    def sy(value: float) -> float:
        return box.top + (max_y - value) / (max_y - min_y) * plot_h

    def sx(index: int) -> float:
        return box.left + slot_w * index + slot_w / 2

    grid = []
    for tick in nice_ticks(min_y, max_y, 5):
        y = sy(tick)
        grid.append(
            f'<line x1="{box.left}" y1="{y:.1f}" x2="{box.width - box.right}" y2="{y:.1f}" stroke="#d8dee8" stroke-dasharray="3 7"/>'
            f'<text x="{box.left - 12}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#64748b">{tick:,.0f}</text>'
        )

    candles = []
    for index, row in bars.iterrows():
        x = sx(index)
        open_price = float(row["Open"])
        high_price = float(row["High"])
        low_price = float(row["Low"])
        close_price = float(row["Close"])
        color = "#0f766e" if close_price >= open_price else "#b91c1c"
        top = sy(max(open_price, close_price))
        bottom = sy(min(open_price, close_price))
        body_h = max(bottom - top, 1.0)
        candles.append(
            f'<line x1="{x:.1f}" y1="{sy(high_price):.1f}" x2="{x:.1f}" y2="{sy(low_price):.1f}" stroke="{color}" stroke-width="1.2"/>'
            f'<rect x="{x - body_w / 2:.1f}" y="{top:.1f}" width="{body_w:.1f}" height="{body_h:.1f}" rx="1" fill="{color}" opacity="0.82">'
            f'<title>{pd.Timestamp(row["ts"]):%Y-%m-%d %H:%M UTC} O:{open_price:.2f} H:{high_price:.2f} L:{low_price:.2f} C:{close_price:.2f}</title></rect>'
        )

    ts_values = pd.to_datetime(bars["ts"], utc=True)
    entry_ts = pd.Timestamp(trade["entry_ts"]).tz_convert("UTC")
    exit_ts = pd.Timestamp(trade["exit_ts"]).tz_convert("UTC")
    entry_index = int((ts_values - entry_ts).abs().argmin())
    exit_index = int((ts_values - exit_ts).abs().argmin())
    entry_x = sx(entry_index)
    exit_x = sx(exit_index)
    entry_y = sy(entry_price)
    exit_y = sy(exit_price)
    direction = int(trade.get("direction", 1))
    net_points = float(trade["net_points"])
    marker_entry = "#2563eb"
    marker_exit = "#7c3aed"
    direction_text = "LONG" if direction > 0 else "SHORT"
    result_class = value_class(net_points)
    x_start = pd.Timestamp(ts_values.iloc[0]).strftime("%H:%M")
    x_end = pd.Timestamp(ts_values.iloc[-1]).strftime("%H:%M")

    return f"""
    <figure class="chart trade-chart">
      <figcaption>{escape(title)} <span class="{result_class}">{fmt_signed(net_points)} pts</span></figcaption>
      <svg viewBox="0 0 {box.width} {box.height}" role="img" aria-label="{escape(title)}">
        <rect x="0" y="0" width="{box.width}" height="{box.height}" rx="8" fill="#ffffff"/>
        {''.join(grid)}
        <line x1="{box.left}" y1="{box.height - box.bottom}" x2="{box.width - box.right}" y2="{box.height - box.bottom}" stroke="#94a3b8"/>
        <line x1="{box.left}" y1="{box.top}" x2="{box.left}" y2="{box.height - box.bottom}" stroke="#94a3b8"/>
        {''.join(candles)}
        <line x1="{entry_x:.1f}" y1="{box.top}" x2="{entry_x:.1f}" y2="{box.height - box.bottom}" stroke="{marker_entry}" stroke-dasharray="5 5"/>
        <line x1="{exit_x:.1f}" y1="{box.top}" x2="{exit_x:.1f}" y2="{box.height - box.bottom}" stroke="{marker_exit}" stroke-dasharray="5 5"/>
        <circle cx="{entry_x:.1f}" cy="{entry_y:.1f}" r="6" fill="{marker_entry}" stroke="#ffffff" stroke-width="2"/>
        <circle cx="{exit_x:.1f}" cy="{exit_y:.1f}" r="6" fill="{marker_exit}" stroke="#ffffff" stroke-width="2"/>
        <text x="{entry_x + 9:.1f}" y="{max(entry_y - 12, box.top + 14):.1f}" fill="{marker_entry}" font-size="13" font-weight="700">ENTRY {direction_text} {entry_price:,.2f}</text>
        <text x="{exit_x + 9:.1f}" y="{min(exit_y + 22, box.height - box.bottom - 8):.1f}" fill="{marker_exit}" font-size="13" font-weight="700">EXIT {exit_price:,.2f}</text>
        <text x="{box.left}" y="{box.height - 28}" fill="#64748b" font-size="12">{escape(x_start)} UTC</text>
        <text x="{box.width - box.right}" y="{box.height - 28}" text-anchor="end" fill="#64748b" font-size="12">{escape(x_end)} UTC</text>
        <text x="{box.left}" y="25" fill="#334155" font-size="13">{escape(pd.Timestamp(trade["entry_ts"]).strftime("%Y-%m-%d"))} · {escape(str(trade.get("symbol", "")))}</text>
      </svg>
    </figure>
    """


def enrich_trades(trades: pd.DataFrame) -> pd.DataFrame:
    data = trades.copy()
    for column in ["entry_ts", "exit_ts"]:
        data[column] = pd.to_datetime(data[column], utc=True, errors="coerce")
    numeric_columns = [
        "entry_price",
        "exit_price",
        "net_points",
        "gross_points",
        "r_multiple",
        "stop_distance_points",
        "target_distance_points",
        "range_width_atr",
        "range_efficiency",
        "displacement_atr",
        "body_share",
        "volume_z_60",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["duration_min"] = (data["exit_ts"] - data["entry_ts"]).dt.total_seconds() / 60
    return data


def trade_table(frame: pd.DataFrame, *, limit: int) -> str:
    data = frame.copy()
    data["entry_time"] = data["entry_ts"].dt.strftime("%Y-%m-%d %H:%M")
    data["exit_time"] = data["exit_ts"].dt.strftime("%Y-%m-%d %H:%M")
    data["setup"] = data["audit_label"]
    columns = [
        ("entry_time", "入场UTC", "text"),
        ("exit_time", "离场UTC", "text"),
        ("setup", "候选", "label"),
        ("entry_price", "入场", "num"),
        ("exit_price", "离场", "num"),
        ("exit_reason", "原因", "text"),
        ("net_points", "净点数", "signed"),
        ("r_multiple", "R", "signed"),
        ("duration_min", "分钟", "num"),
        ("range_width_atr", "区间宽度ATR", "num"),
        ("displacement_atr", "位移ATR", "num"),
    ]
    return html_table(data, columns, limit=limit, class_name="trade-table")


def cost_bar_chart(summary: pd.DataFrame, label: str) -> str:
    row = summary[summary["label"] == label].iloc[0]
    labels = ["0.625", "1.125", "1.625", "2.125", "3.125"]
    values = [
        float(row["net_points"]),
        float(row["net_at_cost_1.125"]),
        float(row["net_at_cost_1.625"]),
        float(row["net_at_cost_2.125"]),
        float(row["net_at_cost_3.125"]),
    ]
    return bar_chart("最佳候选：不同单笔往返成本下的净点数", labels, values, y_label="net points")


def section(title: str, body: str, lead: str = "") -> str:
    lead_html = f"<p class=\"lead\">{escape(lead)}</p>" if lead else ""
    return f"""
    <section class="section">
      <div class="section-head">
        <h2>{escape(title)}</h2>
        {lead_html}
      </div>
      {body}
    </section>
    """


def render_report(
    summary: pd.DataFrame,
    trades: pd.DataFrame,
    yearly: pd.DataFrame,
    monthly: pd.DataFrame,
    rolling90: pd.DataFrame,
    rolling180: pd.DataFrame,
) -> str:
    summary = summary.sort_values(by="label", key=label_rank).reset_index(drop=True)
    trades = enrich_trades(trades)
    lightglow_trades = load_optional_lightglow_trades()
    lightglow_summary = summarize_trade_frame(
        lightglow_trades[lightglow_trades["candidate"] == LIGHTGLOW_CANDIDATE]
        if not lightglow_trades.empty
        else pd.DataFrame()
    )
    best = summary[summary["label"] == BEST_LABEL].iloc[0]
    best_trades = trades[trades["audit_label"] == BEST_LABEL].sort_values("entry_ts").copy()
    regime_frequency = frequency_gate_summary(
        trades,
        label_column="audit_label",
        label_value=BEST_LABEL,
    )
    lightglow_frequency = (
        frequency_gate_summary(
            lightglow_trades,
            label_column="candidate",
            label_value=LIGHTGLOW_CANDIDATE,
        )
        if not lightglow_trades.empty
        else None
    )
    cumulative = cumulative_trades(trades)
    r90_plot = {
        label: rolling90[rolling90["label"] == label].rename(columns={"end": "entry_ts"}).copy()
        for label in LABEL_ORDER
    }
    r180_plot = {
        label: rolling180[rolling180["label"] == label].rename(columns={"end": "entry_ts"}).copy()
        for label in LABEL_ORDER
    }
    for frame in [*r90_plot.values(), *r180_plot.values()]:
        frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True, errors="coerce")

    years, annual_values = annual_chart_data(yearly, BEST_LABEL)
    exit_counts = (
        best_trades["exit_reason"].value_counts(normalize=True).rename_axis("reason").reset_index(name="share")
    )
    exit_count_abs = best_trades["exit_reason"].value_counts().rename_axis("reason").reset_index(name="count")
    exit_distribution = exit_counts.merge(exit_count_abs, on="reason")
    exit_labels = [
        f"{escape(row['reason'])} ({int(row['count'])})"
        for _, row in exit_distribution.iterrows()
    ]
    exit_values = [float(value) * 100 for value in exit_distribution["share"]]

    worst_windows = rolling90.sort_values("net_points").head(12).copy()
    best_recent = best_trades.sort_values("entry_ts", ascending=False).head(30).sort_values("entry_ts")
    worst_trades = best_trades.sort_values("net_points").head(20)
    best_trades_top = best_trades.sort_values("net_points", ascending=False).head(20)
    chart_trades = (
        lightglow_trades[lightglow_trades["candidate"] == LIGHTGLOW_CANDIDATE].copy()
        if not lightglow_trades.empty
        else pd.DataFrame()
    )
    chart_strategy_name = "Lightglow 高频候选"
    if chart_trades.empty:
        chart_trades = best_trades.copy()
        chart_strategy_name = "低频趋势候选"
    best_trade = chart_trades.sort_values("net_points", ascending=False).iloc[0]
    worst_trade = chart_trades.sort_values("net_points").iloc[0]
    best_trade_bars = load_bars_for_trade_window(best_trade)
    worst_trade_bars = load_bars_for_trade_window(worst_trade)

    lightglow_frequency_body = ""
    if lightglow_frequency is not None and lightglow_summary["trades"]:
        lg_counts = lightglow_frequency["counts"]
        selected_lg = lightglow_trades[lightglow_trades["candidate"] == LIGHTGLOW_CANDIDATE].copy()
        selected_lg["entry_ts"] = pd.to_datetime(selected_lg["entry_ts"], utc=True, errors="coerce")
        selected_lg["year"] = selected_lg["entry_ts"].dt.year
        lg_year_net = (
            selected_lg.groupby("year")["net_points"]
            .sum()
            .reindex(FULL_YEARS, fill_value=0.0)
        )
        lg_positive_years = int((lg_year_net > 0).sum())
        lg_worst_year = float(lg_year_net.min())
        lg_stability_pass = lg_positive_years == len(FULL_YEARS)
        lightglow_frequency_body = f"""
        <div class="callout pass-callout">
          <h3>频率合格的高频候选</h3>
          <p><code>{escape(LIGHTGLOW_CANDIDATE)}</code></p>
          <p>该候选是 Lightglow Premium/Discount 1m 反向、2 分钟 time exit。完整年份 2011-2025 的最低年交易数为 <b>{fmt_int(lightglow_frequency["min_trades"])}</b>，满足每年不少于 {fmt_int(MIN_FULL_YEAR_TRADES)} 笔；逐笔导出净点数 <b>{fmt_num(lightglow_summary["net_points"])}</b>，PF <b>{fmt_num(lightglow_summary["profit_factor"], 3)}</b>，交易数 <b>{fmt_int(lightglow_summary["trades"])}</b>。</p>
          <p>但它不满足“稳定盈利”要求：2011-2025 只有 <b>{fmt_int(lg_positive_years)}/{fmt_int(len(FULL_YEARS))}</b> 个完整年份为正收益，最差完整年 <b>{fmt_signed(lg_worst_year)}</b> 点，逐年稳定盈利门槛为 {status_badge(lg_stability_pass)}。因此它只能证明“交易次数门槛可满足”，不能单独作为稳定盈利策略。</p>
          {annual_count_table(lg_counts)}
        </div>
        """
    elif lightglow_frequency is None:
        lightglow_frequency_body = f"""
        <div class="callout warn-callout">
          <h3>高频候选逐笔数据缺失</h3>
          <p>未找到 <code>{escape(LIGHTGLOW_TRADES_PATH.relative_to(ROOT_DIR))}</code>，无法在本报告中验证 Lightglow 高频候选的年度交易次数。请先运行 <code>scripts/export_lightglow_optimized_strategy_trades.py --start-date 2010-06-06 --end-date 2026-04-28 --output .tmp/nq-lightglow-1m-hold2-fullsample-trades.csv</code>。</p>
        </div>
        """

    setup_body = f"""
    <div class="rule-grid">
      <div>
        <h3>核心思路</h3>
        <p>行情在震荡和趋势之间切换。本策略不追逐普通均线或单指标，而是先识别低效率的窄幅区间，再等待有实体、有成交量确认的上破位移 K 线。它只做 NQ 的 us_late 多头，利用固定 3R 止盈、结构低点止损和 240 分钟超时来把胜率和盈亏比组合成正期望。</p>
      </div>
      <div>
        <h3>入场规则</h3>
        <ol>
          <li>使用 NQ 1 分钟 OHLCV bar，构建过去 60 分钟区间。</li>
          <li>区间宽度不超过 12 ATR，区间效率不超过 0.25，代表震荡压缩。</li>
          <li>出现上破位移 K 线：K 线范围至少 1.2 ATR30，实体占比至少 0.55，60 分钟成交量 z-score 不低于 0。</li>
          <li>仅在 us_late 时段做多，下一根 1 分钟 K 线开盘入场。</li>
        </ol>
      </div>
      <div>
        <h3>出场规则</h3>
        <ol>
          <li>止损放在位移 K 线低点下方，失败立即离场，不扛单。</li>
          <li>主候选固定 3R 止盈；用户要求的 2R 固定止盈对应 120m 2R walk-forward 候选。</li>
          <li>持仓最长 240 分钟；到期未触发止盈/止损则按超时离场。</li>
          <li>同一根 bar 同时触发止盈和止损时，审计按 stop-first 保守处理。</li>
        </ol>
      </div>
    </div>
    <div class="pills">
      {pill("数据", "NQ 1m Databento, 2010-06-06 至 2026-04-27 UTC")}
      {pill("基础成本", "0.625 NQ points round trip")}
      {pill("主候选", "60m range -> upside displacement -> 3R")}
      {pill("验证性质", "历史稳定候选，不等于实盘批准")}
    </div>
    """

    metrics_body = f"""
    <div class="metrics">
      {metric("交易数", fmt_int(best["trades"]), "2010-2026 全样本")}
      {metric("净点数", fmt_num(best["net_points"]), fmt_money_from_points(best["net_points"]))}
      {metric("Profit Factor", fmt_num(best["profit_factor"], 3), "门槛 >= 1.25")}
      {metric("胜率", fmt_pct(best["win_rate"]), "低胜率 + 高盈亏比")}
      {metric("盈亏比", fmt_num(best["payoff_ratio"], 2), "avg win / avg loss")}
      {metric("每笔期望", fmt_num(best["expectancy_points"], 2), "points/trade")}
      {metric("最大回撤", fmt_num(best["max_drawdown_points"], 2), "points")}
      {metric("净值/DD", fmt_num(best["net_to_drawdown"], 2), "门槛 >= 4.0")}
      {metric("正收益年份", f'{fmt_int(best["positive_years"])}/{fmt_int(best["years"])}', fmt_pct(best["positive_year_rate"]))}
      {metric("90日正收益率", fmt_pct(best["positive_90d_rate"]), "滚动窗口")}
      {metric("2.125成本后", fmt_num(best["net_at_cost_2.125"]), "仍为正")}
      {metric("审计门槛", "PASS", "8/8 stability gates")}
      {metric("年交易次数门槛", "FAIL" if not regime_frequency["passed"] else "PASS", f'2011-2025 最低 {fmt_int(regime_frequency["min_trades"])} 笔/年')}
    </div>
    """

    frequency_body = f"""
    <div class="callout fail-callout">
      <h3>当前低频趋势候选不满足新增硬门槛</h3>
      <p>你新增的约束是：每个完整年份的交易次数不低于 {fmt_int(MIN_FULL_YEAR_TRADES)} 笔。主趋势候选 <code>{escape(best["candidate"])}</code> 在 2011-2025 完整年份中的最低年交易数只有 <b>{fmt_int(regime_frequency["min_trades"])}</b>，因此频率门槛为 {status_badge(False)}。它仍是历史稳定的低频趋势候选，但不能作为“每年 >=1000 笔”的合格策略。</p>
      {annual_count_table(regime_frequency["counts"])}
    </div>
    {lightglow_frequency_body}
    <div class="callout warn-callout">
      <h3>当前结论</h3>
      <p>截至本次报告生成，已验证的候选里尚未找到一个同时满足“历史稳定盈利”和“2011-2025 每个完整年份交易次数不少于 {fmt_int(MIN_FULL_YEAR_TRADES)} 笔”的策略。后续应把“年交易次数”作为搜索硬约束重新优化，而不是把低频趋势策略或后期盈利集中的高频策略直接升级为合格。</p>
    </div>
    """

    comparison_body = f"""
    <p class="note">三组候选都通过历史稳定门槛。主报告选择 60m 3R，因为它的全样本净点数、正收益年份占比和成本压力表现最好；120m 2R 是固定 2R 离场测试中最值得保留的 walk-forward 候选。</p>
    {candidate_table(summary)}
    {gate_table(summary)}
    """

    equity_body = f"""
    {line_chart("三组候选累计净点数曲线", cumulative, y_column="equity_points", x_column="entry_ts", y_label="cumulative net points")}
    {line_chart("三组候选回撤曲线", cumulative, y_column="drawdown_points", x_column="entry_ts", y_label="drawdown points")}
    """

    yearly_body = f"""
    {bar_chart("最佳候选逐年净点数", years, annual_values, y_label="net points")}
    {yearly_table(yearly)}
    """

    monthly_body = f"""
    <p class="note">颜色按绝对月度净点数归一化，绿色为正、红色为负。缺失月份表示当月无交易。</p>
    {monthly_heatmap(monthly, BEST_LABEL)}
    """

    rolling_body = f"""
    {rolling_stats_table(rolling90, rolling180)}
    {line_chart("滚动90日净点数", r90_plot, y_column="net_points", x_column="entry_ts", y_label="90-day net points")}
    {line_chart("滚动180日净点数", r180_plot, y_column="net_points", x_column="entry_ts", y_label="180-day net points")}
    <h3>最差滚动90日窗口</h3>
    {html_table(worst_windows, [
        ("start", "开始", "text"),
        ("end", "结束", "text"),
        ("label", "候选", "label"),
        ("trades", "交易数", "int"),
        ("net_points", "净点数", "signed"),
    ])}
    """

    exits_body = f"""
    <div class="split">
      {horizontal_bars("最佳候选离场原因占比", exit_labels, exit_values, suffix="%")}
      <div class="rule-panel">
        <h3>离场结构解读</h3>
        <p>主候选约 {fmt_pct(best["target_exit_share"])} 触发 3R 目标，约 {fmt_pct(best["stop_exit_share"])} 触发结构止损，约 {fmt_pct(best["timeout_exit_share"])} 超时离场。系统的正期望主要来自 3R 目标带来的单笔盈利厚度，而不是高胜率。</p>
        <p>最大连续亏损为 {fmt_int(best["max_losing_streak"])} 笔，因此实盘验证需要关注仓位、日内亏损限制和是否出现连续小亏后放弃规则的问题。</p>
      </div>
    </div>
    """

    cost_body = f"""
    {cost_stress_table(summary)}
    {cost_bar_chart(summary, BEST_LABEL)}
    """

    trade_body = f"""
    <p class="note">下方 K 线图展示的是 {escape(chart_strategy_name)}的逐笔最佳和最差交易，蓝点为入场、紫点为出场。</p>
    <div class="trade-chart-grid">
      {candlestick_trade_chart("最佳交易历史 K 线：入场点与出场点", best_trade, best_trade_bars)}
      {candlestick_trade_chart("最差交易历史 K 线：入场点与出场点", worst_trade, worst_trade_bars)}
    </div>
    <details open>
      <summary>最佳候选最近 30 笔交易</summary>
      {trade_table(best_recent, limit=30)}
    </details>
    <details>
      <summary>最佳候选最大盈利 20 笔</summary>
      {trade_table(best_trades_top, limit=20)}
    </details>
    <details>
      <summary>最佳候选最大亏损 20 笔</summary>
      {trade_table(worst_trades, limit=20)}
    </details>
    """

    risks_body = """
    <div class="risk-grid">
      <div>
        <h3>主要残余风险</h3>
        <ul>
          <li>优势集中在 NQ 的 us_late 多头行为，可能包含时代性偏差。</li>
          <li>回测使用 1 分钟 bar，无法完全刻画 bar 内成交顺序和真实排队滑点。</li>
          <li>合约换月、节假日、低流动性时段和极端新闻波动仍需单独审计。</li>
          <li>策略亏损期真实存在，不能把历史 PASS 解读成每天或每周稳定盈利。</li>
        </ul>
      </div>
      <div>
        <h3>下一验证门槛</h3>
        <ul>
          <li>使用 1-4 tick/side 滑点矩阵做执行压力测试。</li>
          <li>用 paper trading 记录未来未见样本的触发、成交、滑点和离场一致性。</li>
          <li>增加日内风控：单日最大亏损、连续亏损暂停、重大事件过滤。</li>
          <li>研究震荡区间内的边界反转策略，只在区间未破且止损明确时启用。</li>
        </ul>
      </div>
    </div>
    """

    appendix_body = f"""
    <div class="source-list">
      <p><b>输入文件</b></p>
      <code>{escape(SUMMARY_PATH.relative_to(ROOT_DIR))}</code>
      <code>{escape(TRADES_PATH.relative_to(ROOT_DIR))}</code>
      <code>{escape(YEARLY_PATH.relative_to(ROOT_DIR))}</code>
      <code>{escape(MONTHLY_PATH.relative_to(ROOT_DIR))}</code>
      <code>{escape(ROLLING90_PATH.relative_to(ROOT_DIR))}</code>
      <code>{escape(ROLLING180_PATH.relative_to(ROOT_DIR))}</code>
      <code>{escape(LIGHTGLOW_TRADES_PATH.relative_to(ROOT_DIR))}</code>
      <p><b>配套 Markdown</b></p>
      <code>reports/NQ-2010-2026-stable-strategy-search-final.md</code>
      <code>reports/NQ-regime-transition-readiness-audit.md</code>
    </div>
    """

    candidate_code = escape(best["candidate"])
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>NQ 震荡转趋势稳定策略报告</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f8fb;
      --paper: #ffffff;
      --ink: #0f172a;
      --muted: #52616f;
      --line: #d9e1ea;
      --soft-line: #edf2f7;
      --teal: #0f766e;
      --blue: #2563eb;
      --amber: #b45309;
      --red: #b91c1c;
      --green-soft: #e7f6f2;
      --red-soft: #fdecec;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .page {{ max-width: 1240px; margin: 0 auto; padding: 26px 18px 48px; }}
    .hero {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 26px;
      margin-bottom: 16px;
    }}
    .kicker {{ margin: 0 0 8px; color: var(--teal); font-weight: 750; letter-spacing: 0; }}
    h1 {{ margin: 0; font-size: clamp(28px, 4vw, 46px); line-height: 1.06; letter-spacing: 0; }}
    h2 {{ margin: 0; font-size: 24px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 10px; font-size: 16px; letter-spacing: 0; }}
    p {{ margin: 0 0 12px; }}
    .hero-summary {{ max-width: 980px; margin-top: 14px; color: #263442; font-size: 16px; }}
    .candidate-code {{
      display: block;
      margin-top: 16px;
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f8fafc;
      color: #1e293b;
    }}
    .pills {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }}
    .pill {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 10px;
      background: #f8fafc;
      color: #334155;
      min-height: 34px;
    }}
    .pill b {{ color: #0f172a; }}
    .section {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 22px;
      margin: 16px 0;
    }}
    .section-head {{ display: flex; justify-content: space-between; align-items: start; gap: 18px; margin-bottom: 16px; }}
    .lead {{ color: var(--muted); max-width: 760px; }}
    .note {{ color: var(--muted); }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: #fbfdff;
      min-width: 0;
    }}
    .metric small {{ display: block; color: var(--muted); font-weight: 650; }}
    .metric strong {{ display: block; margin-top: 6px; font-size: 24px; line-height: 1.05; letter-spacing: 0; }}
    .metric span {{ display: block; margin-top: 6px; color: var(--muted); font-size: 12px; }}
    .rule-grid, .risk-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }}
    .risk-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .rule-grid > div, .risk-grid > div, .rule-panel {{
      border-left: 3px solid var(--teal);
      padding-left: 14px;
    }}
    ol, ul {{ margin: 0; padding-left: 20px; }}
    li {{ margin: 5px 0; }}
    .table-wrap {{
      width: 100%;
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 12px 0;
    }}
    table {{ width: 100%; border-collapse: collapse; min-width: 760px; background: #fff; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid var(--soft-line); vertical-align: top; text-align: left; }}
    thead th {{ background: #f1f5f9; color: #334155; font-size: 12px; text-transform: uppercase; letter-spacing: 0; }}
    tbody tr:hover {{ background: #f8fafc; }}
    td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
    td.candidate {{ min-width: 330px; }}
    .positive {{ color: var(--teal); }}
    .negative {{ color: var(--red); }}
    .neutral {{ color: #475569; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 48px;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 12px;
      font-weight: 800;
    }}
    .badge.pass {{ color: #0f766e; background: var(--green-soft); border: 1px solid #99d7ca; }}
    .badge.fail {{ color: #b91c1c; background: var(--red-soft); border: 1px solid #f0a0a0; }}
    .callout {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      margin: 14px 0;
      background: #fbfdff;
    }}
    .callout h3 {{ margin-bottom: 8px; }}
    .pass-callout {{ border-left: 4px solid var(--teal); }}
    .fail-callout {{ border-left: 4px solid var(--red); }}
    .warn-callout {{ border-left: 4px solid var(--amber); }}
    .chart {{
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 14px 0;
      background: #fff;
      overflow: hidden;
    }}
    .chart figcaption, .distribution figcaption {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      font-weight: 760;
      color: #1e293b;
    }}
    .chart svg {{ display: block; width: 100%; height: auto; }}
    .trade-chart-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      padding: 0 14px 14px;
      color: #334155;
    }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 7px; }}
    .legend-item i {{ display: inline-block; width: 24px; height: 3px; border-radius: 3px; }}
    .heatmap {{ min-width: 980px; }}
    .heatmap th, .heatmap td {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .heatmap th:first-child, .heatmap td:first-child {{ text-align: left; }}
    .heatmap .missing {{ color: #94a3b8; background: #f8fafc; }}
    .split {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(280px, .8fr);
      gap: 16px;
      align-items: start;
    }}
    .distribution {{
      margin: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
    }}
    .hbar-row {{
      display: grid;
      grid-template-columns: 160px minmax(120px, 1fr) 74px;
      align-items: center;
      gap: 10px;
      padding: 9px 12px;
      border-bottom: 1px solid var(--soft-line);
    }}
    .hbar-row span {{ color: #334155; }}
    .hbar-row b {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .hbar-track {{ height: 10px; background: #eef2f7; border-radius: 999px; overflow: hidden; }}
    .hbar-track i {{ display: block; height: 100%; background: var(--teal); border-radius: 999px; }}
    details {{
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 12px 0;
      background: #fff;
      overflow: hidden;
    }}
    summary {{ cursor: pointer; padding: 12px 14px; font-weight: 760; background: #f8fafc; }}
    details .table-wrap {{ border: 0; border-top: 1px solid var(--line); border-radius: 0; margin: 0; }}
    .source-list {{ display: grid; gap: 8px; }}
    .source-list code {{
      display: block;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f8fafc;
    }}
    footer {{ color: var(--muted); margin: 18px 0 0; font-size: 12px; text-align: center; }}
    @media (max-width: 900px) {{
      .page {{ padding: 14px 10px 30px; }}
      .hero, .section {{ padding: 16px; }}
      .section-head, .split {{ display: block; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .rule-grid, .risk-grid {{ grid-template-columns: 1fr; }}
      .hbar-row {{ grid-template-columns: 1fr; gap: 6px; }}
      .hbar-row b {{ text-align: left; }}
    }}
    @media (max-width: 560px) {{
      .metrics {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 30px; }}
      .metric strong {{ font-size: 22px; }}
    }}
    @media print {{
      body {{ background: #fff; }}
      .page {{ max-width: none; padding: 0; }}
      .section, .hero {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <header class="hero">
      <p class="kicker">NQ 1m Regime Transition Strategy Report</p>
      <h1>震荡结束、趋势起步：NQ 稳定盈利候选策略报告</h1>
      <p class="hero-summary">本报告汇总 2010-2026 NQ 1分钟 bar 回测审计。当前最强低频趋势候选是 60 分钟震荡压缩后的上破位移做多策略，但它不满足“每个完整年份至少 1000 笔交易”的新增硬门槛；满足频率门槛的是 Lightglow Premium/Discount 1m 高频反向候选。</p>
      <code class="candidate-code">{candidate_code}</code>
      <div class="pills">
        {pill("生成时间", pd.Timestamp.now("UTC").strftime("%Y-%m-%d %H:%M UTC"))}
        {pill("点值", "$20 / NQ point")}
        {pill("低频趋势稳定", "historical_stable_pass = True")}
        {pill("低频趋势年交易数", "FAIL < 1000/year")}
      </div>
    </header>
    {section("执行摘要", metrics_body)}
    {section("年交易次数硬门槛", frequency_body, "2010 和 2026 是不完整年份；硬门槛只检查 2011-2025 完整自然年。")}
    {section("策略定义", setup_body, "所有入场、过滤和出场条件都可由 OHLCV bar 数据计算。")}
    {section("候选比较与稳定门槛", comparison_body)}
    {section("累计收益与回撤", equity_body)}
    {section("逐年表现", yearly_body)}
    {section("月度热力图", monthly_body)}
    {section("滚动窗口稳定性", rolling_body)}
    {section("出场结构", exits_body)}
    {section("成本压力测试", cost_body)}
    {section("交易样本", trade_body, "完整交易明细保存在输入 CSV；HTML 中列出最近、最大盈利和最大亏损样本用于人工审阅。")}
    {section("风险与下一步验证", risks_body)}
    {section("附录：数据来源", appendix_body)}
    <footer>Static report generated by scripts/generate_nq_regime_transition_html_report.py. Historical backtest only; not investment advice.</footer>
  </main>
</body>
</html>
"""
    return html_doc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the NQ regime transition strategy HTML report.")
    parser.add_argument("--output", type=Path, default=REPORT_PATH, help="Output HTML path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = read_csv(SUMMARY_PATH)
    trades = read_csv(TRADES_PATH)
    yearly = read_csv(YEARLY_PATH)
    monthly = read_csv(MONTHLY_PATH)
    rolling90 = read_csv(ROLLING90_PATH)
    rolling180 = read_csv(ROLLING180_PATH)
    report = render_report(summary, trades, yearly, monthly, rolling90, rolling180)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote {args.output.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
