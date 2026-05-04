from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from generate_mbp_history_report import _equity_curve_summary, _load_features, _svg_line_chart
from generate_mbp_live_ready_report import _advanced_spec_from_row
from mine_mbp_advanced_patterns import build_advanced_trades


SELECTED_NAMES = [
    "adv_top8_enhanced_mean_reversion_lb9_thr0.6_min1_max5_reverse_all_high_imb0.35",
    "adv_refined_mean_reversion_lb7_thr0.65_min1_max6_reverse_europe_not_low_imb0.3",
    "adv_top6_enhanced_vwap_reclaim_lb10_thr0.0002_min1_max10_time_all_not_low_imb0.35",
]

STRATEGY_LABELS = {
    SELECTED_NAMES[0]: "稳定收益首选",
    SELECTED_NAMES[1]: "低回撤稳健基准",
    SELECTED_NAMES[2]: "高收益进攻策略",
}

STRATEGY_PRINCIPLES = {
    SELECTED_NAMES[0]: (
        "均值回归策略。用最近 9 根 1m K 的收盘价计算 z-score；价格相对短期均值低于 -0.6 时做多，"
        "高于 +0.6 时做空。只在高波动状态交易，并要求盘口不平衡方向与交易方向一致、点差不过宽、深度不太薄。"
        "至少持有 1 分钟，最多持有 5 分钟；出现反向信号时提前退出。"
    ),
    SELECTED_NAMES[1]: (
        "更保守的均值回归策略。用最近 7 根 1m K 的 z-score，阈值提高到 0.65，"
        "只交易 Europe 时段且排除低波动环境。盘口过滤要求降到 0.3，因此信号更平滑。"
        "至少持有 1 分钟，最多持有 6 分钟；出现反向信号时退出。"
    ),
    SELECTED_NAMES[2]: (
        "VWAP reclaim 趋势确认策略。价格偏离 VWAP 超过 0.02% 且最近 10 分钟动量同向时入场，"
        "本质是在价格重新站回/跌破 VWAP 后跟随短线趋势。全时段可交易，但排除低波动环境，"
        "并要求盘口不平衡与方向一致；持仓 1 到 10 分钟，按时间退出。"
    ),
}

METRIC_EXPLANATIONS = [
    ("Net Points", "累计净点数，已扣除单笔往返成本；越大越好。"),
    ("Max DD", "资金曲线从峰值到低谷的最大回撤点数；越小越好。"),
    ("PF", "Profit Factor，盈利交易总额 / 亏损交易绝对值；越大越好，通常 >1 才有正期望。"),
    ("Win Rate", "盈利交易占比；越大越好，但必须结合盈亏比和 PF 看。"),
    ("Stability", "前后半段收益均衡度，越接近 1 说明收益分布越均匀；越大越好。"),
    ("Positive Folds", "分段回测中盈利分段占比；越大越好。"),
    ("Positive Windows", "滚动 10 交易日窗口盈利占比；越大越好。"),
    ("Worst Window", "最差滚动窗口净收益；越大越好，负数表示某段历史明显失效。"),
    ("3x Cost Net", "按 3 倍交易成本压力测试后的净点数；越大越好。"),
]


def _fmt(value: float, decimals: int = 4) -> str:
    return f"{value:,.{decimals}f}"


def _load_selected_rows(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        if path.exists():
            frame = pd.read_csv(path)
            if not frame.empty:
                frame["_source_file"] = str(path)
                frames.append(frame)
    if not frames:
        raise SystemExit("No strategy result files found.")

    candidates = pd.concat(frames, ignore_index=True, sort=False)
    rows = []
    for name in SELECTED_NAMES:
        matches = candidates[candidates["name"].eq(name)]
        if matches.empty:
            raise SystemExit(f"Missing selected strategy in result files: {name}")
        rows.append(matches.iloc[0])
    return pd.DataFrame(rows).reset_index(drop=True)


def _equity_points(trades: pd.DataFrame, start_ts: pd.Timestamp) -> list[tuple[pd.Timestamp, float]]:
    equity = trades["net_points"].cumsum().round(4)
    timestamps = pd.to_datetime(trades["actual_entry_ts"], utc=True)
    return [(start_ts, 0.0), *zip(timestamps, equity)]


def _enrich_trades(features: pd.DataFrame, strategy_label: str, strategy_name: str, trades: pd.DataFrame) -> pd.DataFrame:
    enriched = trades.copy()
    enriched.insert(0, "strategy_label", strategy_label)
    enriched.insert(1, "strategy_name", strategy_name)
    enriched["signal_ts"] = pd.to_datetime(enriched["entry_ts"], utc=True)
    enriched["actual_entry_index"] = (enriched["entry_index"].astype(int) + 1).clip(upper=len(features) - 1)
    enriched["actual_entry_ts"] = enriched["actual_entry_index"].map(features["ts"])
    enriched["exit_ts"] = pd.to_datetime(enriched["exit_ts"], utc=True)
    enriched["direction_label"] = enriched["direction"].map({1: "Long", -1: "Short"})
    enriched["cumulative_net_points"] = enriched["net_points"].cumsum()
    return enriched


def _direction_text(row: pd.Series) -> str:
    direction = "做多" if int(row["direction"]) > 0 else "做空"
    return (
        f"{direction} @ {float(row['entry_price']):,.2f}, "
        f"{pd.Timestamp(row['actual_entry_ts']).strftime('%Y-%m-%d %H:%M UTC')}"
    )


def _exit_text(row: pd.Series) -> str:
    return (
        f"平仓 @ {float(row['exit_price']):,.2f}, "
        f"{pd.Timestamp(row['exit_ts']).strftime('%Y-%m-%d %H:%M UTC')}, "
        f"原因 {row['exit_reason']}"
    )


def _metrics_table(rows: pd.DataFrame) -> str:
    columns = [
        "label",
        "name",
        "full_trades",
        "full_net_points",
        "full_max_drawdown_points",
        "full_profit_factor",
        "full_win_rate",
        "full_stability",
        "positive_fold_rate",
        "positive_window_rate",
        "min_window_net_points",
        "worst_cost_net_points",
    ]
    display = rows[columns].copy()
    for column in ["full_win_rate", "positive_fold_rate", "positive_window_rate"]:
        display[column] = display[column].map(lambda value: f"{float(value):.2%}")
    for column in [
        "full_net_points",
        "full_max_drawdown_points",
        "full_profit_factor",
        "full_stability",
        "min_window_net_points",
        "worst_cost_net_points",
    ]:
        display[column] = display[column].map(lambda value: _fmt(float(value)))
    display.columns = [
        "定位",
        "策略",
        "交易数",
        "Net Points",
        "Max DD",
        "PF",
        "Win Rate",
        "Stability",
        "Positive Folds",
        "Positive Windows",
        "Worst Window",
        "3x Cost Net",
    ]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def _trade_table(trades: pd.DataFrame, rows_per_strategy: int) -> str:
    samples = []
    for _, group in trades.groupby("strategy_name", sort=False):
        head = group.head(rows_per_strategy)
        tail = group.tail(rows_per_strategy)
        sample = pd.concat([head, tail], ignore_index=False).drop_duplicates()
        samples.append(sample)
    display = pd.concat(samples, ignore_index=True)
    display = display[
        [
            "strategy_label",
            "strategy_name",
            "signal_ts",
            "actual_entry_ts",
            "exit_ts",
            "direction_label",
            "entry_price",
            "exit_price",
            "exit_reason",
            "gross_points",
            "net_points",
            "cumulative_net_points",
            "holding_minutes",
        ]
    ].copy()
    for column in ["signal_ts", "actual_entry_ts", "exit_ts"]:
        display[column] = pd.to_datetime(display[column], utc=True).dt.strftime("%Y-%m-%d %H:%M UTC")
    for column in ["entry_price", "exit_price", "gross_points", "net_points", "cumulative_net_points"]:
        display[column] = display[column].map(lambda value: _fmt(float(value)))
    display.columns = [
        "定位",
        "策略",
        "信号时间",
        "真实入场时间",
        "真实出场时间",
        "方向",
        "入场价",
        "出场价",
        "出场原因",
        "Gross Points",
        "Net Points",
        "累计净点数",
        "持仓分钟",
    ]
    return display.to_html(index=False, classes="metrics compact", border=0, escape=True)


def _principles_section(rows: pd.DataFrame) -> str:
    cards = []
    for _, row in rows.iterrows():
        name = str(row["name"])
        cards.append(
            f"""
        <div class="principle">
          <h3>{html.escape(row['label'])}</h3>
          <p><code>{html.escape(name)}</code></p>
          <p>{html.escape(STRATEGY_PRINCIPLES[name])}</p>
        </div>
"""
        )
    return "".join(cards)


def _metric_explanations() -> str:
    return "".join(
        f"<tr><td>{html.escape(metric)}</td><td>{html.escape(description)}</td></tr>"
        for metric, description in METRIC_EXPLANATIONS
    )


def _key_trade_points(trades: pd.DataFrame) -> str:
    rows = []
    for _, group in trades.groupby("strategy_name", sort=False):
        best = group.loc[group["net_points"].idxmax()]
        worst = group.loc[group["net_points"].idxmin()]
        first = group.iloc[0]
        last = group.iloc[-1]
        for tag, trade in [("第一笔", first), ("最大盈利", best), ("最大亏损", worst), ("最后一笔", last)]:
            rows.append(
                {
                    "strategy_label": trade["strategy_label"],
                    "tag": tag,
                    "entry": _direction_text(trade),
                    "exit": _exit_text(trade),
                    "net_points": trade["net_points"],
                    "cumulative_net_points": trade["cumulative_net_points"],
                }
            )
    display = pd.DataFrame(rows)
    for column in ["net_points", "cumulative_net_points"]:
        display[column] = display[column].map(lambda value: _fmt(float(value)))
    display.columns = ["策略定位", "交易点", "真实入场点", "真实出场点", "本笔净点数", "当时累计净点数"]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def _market_trade_chart(features: pd.DataFrame, trade: pd.Series, title: str, window_minutes: int = 30) -> str:
    width = 1100
    height = 430
    left = 74
    right = 32
    top = 44
    bottom = 72
    plot_width = width - left - right
    plot_height = height - top - bottom

    signal_index = int(trade["entry_index"])
    entry_index = int(trade["actual_entry_index"])
    exit_index = int(trade["exit_index"])
    start_index = max(0, min(signal_index, entry_index, exit_index) - window_minutes)
    end_index = min(len(features) - 1, max(signal_index, entry_index, exit_index) + window_minutes)
    window = features.iloc[start_index : end_index + 1].copy().reset_index(drop=False).rename(columns={"index": "feature_index"})
    if window.empty:
        return ""

    price_columns = ["Open", "High", "Low", "Close", "vwap"]
    for column in price_columns:
        window[column] = pd.to_numeric(window[column], errors="coerce")
    min_price = float(window[["Low", "vwap"]].min(skipna=True).min())
    max_price = float(window[["High", "vwap"]].max(skipna=True).max())
    if min_price == max_price:
        min_price -= 1
        max_price += 1
    padding = max((max_price - min_price) * 0.08, 2.0)
    min_price -= padding
    max_price += padding
    count = len(window)
    candle_slot = plot_width / max(count - 1, 1)
    candle_width = max(3.0, min(9.0, candle_slot * 0.55))

    def x_for(feature_index: int) -> float:
        offset = feature_index - start_index
        return left if count <= 1 else left + offset / (count - 1) * plot_width

    def y_for(price: float) -> float:
        return top + (max_price - price) / (max_price - min_price) * plot_height

    y_ticks = [min_price + (max_price - min_price) * index / 4 for index in range(5)]
    grid = []
    for tick in y_ticks:
        y = y_for(tick)
        grid.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#243744" stroke-width="1"/>'
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#adc4cc">{tick:,.2f}</text>'
        )

    x_tick_count = min(6, count)
    for tick_number in range(x_tick_count):
        row = window.iloc[round((count - 1) * tick_number / max(x_tick_count - 1, 1))]
        x = x_for(int(row["feature_index"]))
        label = pd.Timestamp(row["ts"]).strftime("%m-%d %H:%M")
        grid.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" stroke="#243744" stroke-width="1"/>'
            f'<text x="{x:.1f}" y="{top + plot_height + 26}" text-anchor="middle" font-size="11" fill="#adc4cc">{html.escape(label)}</text>'
        )

    candles = []
    for _, bar in window.iterrows():
        feature_index = int(bar["feature_index"])
        open_price = float(bar["Open"])
        high_price = float(bar["High"])
        low_price = float(bar["Low"])
        close_price = float(bar["Close"])
        x = x_for(feature_index)
        color = "#22c55e" if close_price >= open_price else "#ef4444"
        body_top = y_for(max(open_price, close_price))
        body_bottom = y_for(min(open_price, close_price))
        body_height = max(body_bottom - body_top, 1.0)
        candles.append(
            f'<line x1="{x:.1f}" y1="{y_for(high_price):.1f}" x2="{x:.1f}" y2="{y_for(low_price):.1f}" stroke="{color}" stroke-width="1.2"/>'
            f'<rect x="{x - candle_width / 2:.1f}" y="{body_top:.1f}" width="{candle_width:.1f}" height="{body_height:.1f}" fill="{color}" opacity=".78"/>'
        )

    vwap_points = " ".join(
        f'{x_for(int(row["feature_index"])):.1f},{y_for(float(row["vwap"])):.1f}'
        for _, row in window.dropna(subset=["vwap"]).iterrows()
    )
    vwap_line = f'<polyline fill="none" stroke="#facc15" stroke-width="1.8" opacity=".9" points="{vwap_points}"/>' if vwap_points else ""

    entry_price = float(trade["entry_price"])
    exit_price = float(trade["exit_price"])
    signal_x = x_for(signal_index)
    entry_x = x_for(entry_index)
    exit_x = x_for(exit_index)
    entry_y = y_for(entry_price)
    exit_y = y_for(exit_price)
    is_long = int(trade["direction"]) > 0
    entry_color = "#38bdf8" if is_long else "#f97316"
    exit_color = "#e879f9"
    pnl_color = "#22c55e" if float(trade["net_points"]) >= 0 else "#ef4444"
    direction = "Long" if is_long else "Short"

    return f"""
<div class="trade-chart">
  <h3>{html.escape(title)}</h3>
  <p>{html.escape(trade['strategy_label'])} · {direction} · Net {_fmt(float(trade['net_points']))} points · Entry {entry_price:,.2f} · Exit {exit_price:,.2f}</p>
  <svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
    <rect x="0" y="0" width="{width}" height="{height}" fill="#0d1820"/>
    {''.join(grid)}
    <line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#66818c"/>
    <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#66818c"/>
    {''.join(candles)}
    {vwap_line}
    <line x1="{signal_x:.1f}" y1="{top}" x2="{signal_x:.1f}" y2="{top + plot_height}" stroke="#94a3b8" stroke-width="1.4" stroke-dasharray="5 5"/>
    <line x1="{entry_x:.1f}" y1="{top}" x2="{entry_x:.1f}" y2="{top + plot_height}" stroke="{entry_color}" stroke-width="1.7"/>
    <line x1="{exit_x:.1f}" y1="{top}" x2="{exit_x:.1f}" y2="{top + plot_height}" stroke="{exit_color}" stroke-width="1.7"/>
    <line x1="{entry_x:.1f}" y1="{entry_y:.1f}" x2="{exit_x:.1f}" y2="{exit_y:.1f}" stroke="{pnl_color}" stroke-width="2.4"/>
    <circle cx="{entry_x:.1f}" cy="{entry_y:.1f}" r="6" fill="{entry_color}" stroke="#ffffff" stroke-width="1.5"/>
    <circle cx="{exit_x:.1f}" cy="{exit_y:.1f}" r="6" fill="{exit_color}" stroke="#ffffff" stroke-width="1.5"/>
    <text x="{entry_x + 8:.1f}" y="{entry_y - 10:.1f}" font-size="12" fill="#eaf7fb">Entry {entry_price:,.2f}</text>
    <text x="{exit_x + 8:.1f}" y="{exit_y + 18:.1f}" font-size="12" fill="#eaf7fb">Exit {exit_price:,.2f}</text>
    <text x="{signal_x + 6:.1f}" y="{top + 16}" font-size="12" fill="#cbd5e1">Signal</text>
    <text x="{left}" y="24" font-size="15" fill="#f6fbfc">{html.escape(title)}</text>
    <text x="{left + plot_width - 182}" y="24" font-size="12" fill="#facc15">VWAP</text>
    <line x1="{left + plot_width - 220}" y1="20" x2="{left + plot_width - 188}" y2="20" stroke="#facc15" stroke-width="2"/>
  </svg>
</div>
"""


def _best_worst_trade_charts(features: pd.DataFrame, trades: pd.DataFrame) -> str:
    charts = []
    for _, group in trades.groupby("strategy_name", sort=False):
        best = group.loc[group["net_points"].idxmax()]
        worst = group.loc[group["net_points"].idxmin()]
        charts.append(_market_trade_chart(features, best, f"{best['strategy_label']} · 最佳交易真实行情"))
        charts.append(_market_trade_chart(features, worst, f"{worst['strategy_label']} · 最差交易真实行情"))
    return "".join(charts)


def _cards(rows: pd.DataFrame, trades: pd.DataFrame, features: pd.DataFrame) -> str:
    best_net = rows.sort_values("full_net_points", ascending=False).iloc[0]
    best_stable = rows.sort_values(
        ["positive_window_rate", "min_window_net_points", "full_max_drawdown_points"],
        ascending=[False, False, True],
    ).iloc[0]
    return f"""
      <div class="metric-grid">
        <div class="metric"><strong>数据范围</strong><span>{features['ts'].min()} 至 {features['ts'].max()}</span></div>
        <div class="metric"><strong>策略数量</strong><span>3 条独立策略曲线，无组合资金曲线</span></div>
        <div class="metric"><strong>总逐笔记录</strong><span>{len(trades):,} 笔，完整 CSV 已输出</span></div>
        <div class="metric"><strong>收益最高</strong><span>{html.escape(best_net['label'])}: {_fmt(float(best_net['full_net_points']))} points</span></div>
        <div class="metric"><strong>稳定性首选</strong><span>{html.escape(best_stable['label'])}: Worst Window {_fmt(float(best_stable['min_window_net_points']))}</span></div>
        <div class="metric"><strong>交易成本</strong><span>净点数已扣除当前回测设置的往返滑点和手续费</span></div>
      </div>
"""


def _chart_script() -> str:
    return """
  <div class="chart-tooltip" id="chart-tooltip"></div>
  <script>
    const tooltip = document.getElementById("chart-tooltip");
    function moveTooltip(event) {
      const padding = 16;
      const rect = tooltip.getBoundingClientRect();
      let left = event.clientX + 14;
      let top = event.clientY + 14;
      if (left + rect.width + padding > window.innerWidth) left = event.clientX - rect.width - 14;
      if (top + rect.height + padding > window.innerHeight) top = event.clientY - rect.height - 14;
      tooltip.style.left = `${Math.max(padding, left)}px`;
      tooltip.style.top = `${Math.max(padding, top)}px`;
    }
    document.querySelectorAll(".chart-point").forEach((point) => {
      point.addEventListener("mouseenter", () => {
        if (point.classList.contains("is-hidden")) return;
        document.querySelectorAll(`.series-line[data-series="${CSS.escape(point.dataset.series)}"]`).forEach((element) => element.classList.add("highlighted"));
        point.classList.add("active-point");
        tooltip.textContent = [
          point.dataset.name || "",
          `Time: ${point.dataset.time || ""}`,
          `Trade: ${point.dataset.trade || ""}`,
          `Equity: ${point.dataset.equity || ""}`,
        ].join("\\n");
        tooltip.style.borderColor = point.dataset.color || "#476b5e";
        tooltip.style.display = "block";
      });
      point.addEventListener("mousemove", moveTooltip);
      point.addEventListener("mouseleave", () => {
        document.querySelectorAll(`.series-line[data-series="${CSS.escape(point.dataset.series)}"]`).forEach((element) => element.classList.remove("highlighted"));
        point.classList.remove("active-point");
        tooltip.style.display = "none";
      });
    });
    document.querySelectorAll(".legend-item").forEach((button) => {
      button.addEventListener("click", () => {
        const series = button.dataset.series;
        const nextHidden = button.getAttribute("aria-pressed") === "true";
        document.querySelectorAll(`.legend-item[data-series="${CSS.escape(series)}"]`).forEach((item) => {
          item.setAttribute("aria-pressed", String(!nextHidden));
          item.classList.toggle("is-muted", nextHidden);
        });
        document.querySelectorAll(`.series-line[data-series="${CSS.escape(series)}"], .chart-point[data-series="${CSS.escape(series)}"]`).forEach((element) => {
          element.classList.toggle("dimmed", nextHidden);
          element.classList.toggle("is-hidden", nextHidden);
          if (element.classList.contains("chart-point")) element.style.pointerEvents = nextHidden ? "none" : "all";
        });
        tooltip.style.display = "none";
      });
    });
  </script>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate selected MBP strategy integration report.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--enhanced-results", default=".tmp/mbp-enhanced-top10.csv")
    parser.add_argument("--refined-results", default=".tmp/mbp-refined-mean-reversion.csv")
    parser.add_argument("--trades-output", default=".tmp/mbp-selected-strategies-trades.csv")
    parser.add_argument("--output", default="reports/NQM6-mbp-selected-strategies.html")
    parser.add_argument("--rows-per-strategy", type=int, default=8)
    args = parser.parse_args()

    features = _load_features(Path(args.features_cache))
    rows = _load_selected_rows([Path(args.enhanced_results), Path(args.refined_results)])
    rows["label"] = rows["name"].map(STRATEGY_LABELS)

    curves: dict[str, list[tuple[pd.Timestamp, float]]] = {}
    trade_frames = []
    for _, row in rows.iterrows():
        spec = _advanced_spec_from_row(row)
        if spec is None:
            raise SystemExit(f"Cannot build advanced spec from row: {row['name']}")
        raw_trades = build_advanced_trades(features, spec)
        if raw_trades.empty:
            raise SystemExit(f"No trades rebuilt for selected strategy: {row['name']}")
        trades = _enrich_trades(features, str(row["label"]), str(row["name"]), raw_trades)
        trade_frames.append(trades)
        curves[f"{row['label']}: {row['name']}"] = _equity_points(trades, features["ts"].min())

    all_trades = pd.concat(trade_frames, ignore_index=True)
    output_columns = [
        "strategy_label",
        "strategy_name",
        "signal_ts",
        "actual_entry_ts",
        "exit_ts",
        "exit_reason",
        "direction",
        "direction_label",
        "entry_price",
        "exit_price",
        "gross_points",
        "net_points",
        "net_dollars",
        "cumulative_net_points",
        "entry_index",
        "actual_entry_index",
        "exit_index",
        "holding_minutes",
    ]
    trades_output = Path(args.trades_output)
    trades_output.parent.mkdir(parents=True, exist_ok=True)
    all_trades[output_columns].to_csv(trades_output, index=False)

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NQM6 Selected MBP Strategies</title>
  <style>
    body {{ margin: 0; padding: 28px; background: #0b1115; color: #edf5f7; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 1240px; margin: 0 auto; }}
    .card {{ background: rgba(17, 27, 34, .94); border: 1px solid #2a4650; border-radius: 18px; padding: 20px; margin-bottom: 18px; box-shadow: 0 16px 50px rgba(0,0,0,.28); overflow-x: auto; }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    p {{ color: #b8cbd1; line-height: 1.68; }}
    code {{ color: #d6f3ff; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #2a4650; text-align: left; vertical-align: top; }}
    th {{ color: #d7edf4; text-transform: uppercase; letter-spacing: .04em; font-size: 12px; }}
    svg {{ width: 100%; height: auto; border-radius: 14px; overflow: hidden; }}
    .badge {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: rgba(45, 212, 191, .13); color: #99f6e4; margin-bottom: 10px; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px; }}
    .metric, .principle {{ border: 1px solid #2a4650; border-radius: 12px; padding: 12px; background: rgba(11, 17, 21, .46); }}
    .metric strong {{ display: block; margin-bottom: 6px; color: #f6fbfc; }}
    .metric span {{ color: #b8cbd1; line-height: 1.55; }}
    .principles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); gap: 12px; }}
    .compact {{ font-size: 12px; }}
    .trade-chart {{ border: 1px solid #2a4650; border-radius: 14px; padding: 14px; margin: 14px 0; background: rgba(8, 15, 19, .52); }}
    .trade-chart h3 {{ font-size: 16px; }}
    .trade-chart p {{ margin-top: -4px; }}
    .chart-tooltip {{ position: fixed; z-index: 50; display: none; max-width: 360px; padding: 10px 12px; border: 1px solid #476b5e; border-radius: 10px; background: rgba(7, 19, 15, .96); color: #f6fbf8; font-size: 12px; line-height: 1.5; white-space: pre-line; pointer-events: none; box-shadow: 0 14px 36px rgba(0,0,0,.35); }}
    .legend-bar {{ display: flex; flex-wrap: wrap; align-content: flex-start; align-items: center; gap: 8px; height: 106px; overflow-y: auto; padding: 2px 0 8px; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 6px; flex: 0 1 auto; max-width: 310px; border: 1px solid #365a4d; border-radius: 999px; background: rgba(7, 19, 15, .72); color: #dcece4; padding: 5px 9px; font: 11px/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; cursor: pointer; }}
    .legend-item span:last-child {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .legend-item.is-muted {{ opacity: .38; text-decoration: line-through; }}
    .legend-swatch {{ width: 10px; height: 10px; border-radius: 999px; box-shadow: 0 0 0 1px rgba(255,255,255,.18) inset; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <span class="badge">Selected MBP Strategies · NQM6</span>
      <h1>NQM6 三策略整合报告</h1>
      <p>本报告整合 3 条独立策略：稳定收益首选、低回撤稳健基准、高收益进攻策略。资金曲线不做等权组合，每张图只展示这 3 条策略各自的累计净点数。</p>
    </section>
    <section class="card">
      <h2>结论摘要</h2>
      {_cards(rows, all_trades, features)}
    </section>
    <section class="card">
      <h2>策略指标对比</h2>
      {_metrics_table(rows)}
    </section>
    <section class="card">
      <h2>交易原理</h2>
      <div class="principles">{_principles_section(rows)}</div>
    </section>
    <section class="card">
      <h2>资金曲线对比</h2>
      <p>第一张图横坐标为交易次数，第二张图横坐标为真实交易日期。图例可点击隐藏/恢复策略，鼠标悬浮只显示当前数据点。</p>
      {_svg_line_chart(curves, "Selected strategies equity by trade sequence (net points)", "sequence")}
      {_svg_line_chart(curves, "Selected strategies equity by trading date (net points)", "date")}
      {_equity_curve_summary(curves)}
    </section>
    <section class="card">
      <h2>关键真实入场点与出场点</h2>
      <p>真实入场时间使用信号后下一分钟 Open 成交时间；出场时间使用回测实际平仓 K 线时间。完整逐笔明细：<code>{html.escape(str(trades_output))}</code>。</p>
      {_key_trade_points(all_trades)}
    </section>
    <section class="card">
      <h2>最佳/最差交易行情图示</h2>
      <p>每条策略展示最佳交易和最差交易在真实 1m 行情中的位置。K 线为真实 OHLC，黄线为 VWAP，灰色虚线为信号时间，蓝/橙色为实际入场，紫色为实际出场。</p>
      {_best_worst_trade_charts(features, all_trades)}
    </section>
    <section class="card">
      <h2>逐笔交易样本</h2>
      <p>每条策略展示开头和结尾各 {args.rows_per_strategy} 笔；完整数据见 CSV。</p>
      {_trade_table(all_trades, args.rows_per_strategy)}
    </section>
    <section class="card">
      <h2>指标含义</h2>
      <table class="metrics"><thead><tr><th>指标</th><th>含义与方向</th></tr></thead><tbody>{_metric_explanations()}</tbody></table>
    </section>
  </div>
  {_chart_script()}
</body>
</html>
"""
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_doc, encoding="utf-8")
    print(output)
    print(trades_output)
    print(rows[["label", "name", "full_trades", "full_net_points", "full_max_drawdown_points", "full_profit_factor", "min_window_net_points", "worst_cost_net_points"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
