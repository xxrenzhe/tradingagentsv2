from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.dataflows.databento import _bar_zip_path
from tradingagents.evolution.nq_data import load_continuous_nq_bars


CHOSEN_TEMPLATE = (
    "lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_"
    "bracket_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff3_be0.75"
)
STAGED_TEMPLATE = (
    "lab_reversal_reclaim_fast_rally_fade_us_rth_next_open_event_extreme_"
    "staged_rr1_h30_c2_pb0.25_atr1.25_ctxvwap_volume_ff5_be0.75"
)


def summarize(trades: pd.DataFrame) -> dict[str, Any]:
    costs = BacktestCosts()
    if trades.empty:
        return {}
    net = trades["net_points"].astype(float)
    gross = trades["gross_points"].astype(float)
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    wins = net[net > 0].sum()
    losses = abs(net[net < 0].sum())
    return {
        "trades": int(len(trades)),
        "gross_points": float(gross.sum()),
        "net_points": float(net.sum()),
        "net_dollars": float(net.sum() * costs.point_value),
        "profit_factor": float(wins / losses) if losses else 999.0,
        "win_rate": float((net > 0).mean()),
        "avg_points": float(net.mean()),
        "median_points": float(net.median()),
        "max_drawdown_points": float(abs(drawdown.min())),
        "best_trade_points": float(net.max()),
        "worst_trade_points": float(net.min()),
    }


def yearly(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    data = trades.copy()
    data["year"] = pd.to_datetime(data["entry_ts"], utc=True).dt.year
    rows = []
    for year, group in data.groupby("year"):
        rows.append({"year": int(year), **summarize(group)})
    return pd.DataFrame(rows)


def recompute_no_same_bar_exits(bars: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    """Reprice exits from the bar after entry to avoid 1m intrabar path ambiguity."""
    if trades.empty:
        return trades.copy()

    costs = BacktestCosts()
    bars = bars.reset_index(drop=True)
    ts_to_index = pd.Series(np.arange(len(bars), dtype=int), index=pd.to_datetime(bars["ts"], utc=True))
    high = bars["High"].to_numpy(dtype=float)
    low = bars["Low"].to_numpy(dtype=float)
    close = bars["Close"].to_numpy(dtype=float)
    symbols = bars["symbol"].astype(str).to_numpy()
    timestamps = bars["ts"].to_numpy()

    rows: list[dict[str, Any]] = []
    for _, trade in trades.iterrows():
        entry_ts = pd.Timestamp(trade["entry_ts"])
        if entry_ts not in ts_to_index.index:
            continue
        entry_index = int(ts_to_index.loc[entry_ts])
        first_exit_check = entry_index + 1
        if first_exit_check >= len(bars):
            continue

        direction = int(trade["direction"])
        entry_symbol = symbols[entry_index]
        entry_price = float(trade["entry_price"])
        stop_distance = float(trade["stop_distance_points"])
        target_distance = float(trade["target_distance_points"])
        horizon = int(trade["horizon_minutes"])
        planned_exit = min(entry_index + horizon, len(bars) - 1)
        stop_price = entry_price + stop_distance if direction < 0 else entry_price - stop_distance
        target_price = entry_price - target_distance if direction < 0 else entry_price + target_distance
        exit_index = planned_exit
        exit_price = float(close[planned_exit])
        exit_reason = "time_no_same_bar"

        for path_index in range(first_exit_check, planned_exit + 1):
            if symbols[path_index] != entry_symbol:
                exit_index = max(first_exit_check, path_index - 1)
                exit_price = float(close[exit_index])
                exit_reason = "symbol_change"
                break
            if direction < 0:
                stop_hit = high[path_index] >= stop_price
                target_hit = low[path_index] <= target_price
            else:
                stop_hit = low[path_index] <= stop_price
                target_hit = high[path_index] >= target_price
            if stop_hit:
                exit_index = path_index
                exit_price = stop_price
                exit_reason = "stop_loss"
                break
            if target_hit:
                exit_index = path_index
                exit_price = target_price
                exit_reason = "take_profit"
                break

        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points
        row = trade.to_dict()
        row.update(
            {
                "original_exit_ts": trade["exit_ts"],
                "original_exit_price": trade["exit_price"],
                "original_exit_reason": trade["exit_reason"],
                "original_gross_points": trade["gross_points"],
                "original_net_points": trade["net_points"],
                "exit_ts": timestamps[exit_index],
                "exit_index": int(exit_index),
                "exit_price": float(exit_price),
                "exit_reason": exit_reason,
                "gross_points": float(gross_points),
                "net_points": float(net_points),
                "net_dollars": float(net_points * costs.point_value),
                "no_same_bar_exit": True,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return html.escape(str(value))
    if not np.isfinite(number):
        return "N/A"
    return f"{number:,.{digits}f}"


def pct(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"
    return f"{number:.2%}"


def table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    rows = []
    for _, row in frame[columns].iterrows():
        cells = []
        for column in columns:
            value = row[column]
            if isinstance(value, (float, np.floating)):
                text = fmt(value, 3)
            else:
                text = html.escape(str(value))
            cells.append(f"<td>{text}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def chart_for_trade(bars: pd.DataFrame, trade: pd.Series, title: str) -> str:
    entry_ts = pd.Timestamp(trade["entry_ts"])
    exit_ts = pd.Timestamp(trade["exit_ts"])
    start_ts = entry_ts - pd.Timedelta(minutes=90)
    end_ts = exit_ts + pd.Timedelta(minutes=90)
    data = bars[(bars["ts"] >= start_ts) & (bars["ts"] <= end_ts)].copy()
    direction = int(trade["direction"])
    side = "SHORT" if direction < 0 else "LONG"

    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=data["ts"],
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name="NQ 1m",
            increasing_line_color="#089981",
            decreasing_line_color="#f23645",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[entry_ts],
            y=[trade["entry_price"]],
            mode="markers+text",
            marker={"size": 15, "symbol": "triangle-down" if direction < 0 else "triangle-up", "color": "#f97316"},
            text=[f"{side} entry"],
            textposition="top center",
            name="Entry",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[exit_ts],
            y=[trade["exit_price"]],
            mode="markers+text",
            marker={"size": 14, "symbol": "x", "color": "#38bdf8"},
            text=["Exit"],
            textposition="bottom center",
            name="Exit",
        )
    )
    stop = float(trade["entry_price"]) + float(trade["stop_distance_points"]) if direction < 0 else float(trade["entry_price"]) - float(trade["stop_distance_points"])
    target = float(trade["entry_price"]) - float(trade["target_distance_points"]) if direction < 0 else float(trade["entry_price"]) + float(trade["target_distance_points"])
    fig.add_hline(y=stop, line_dash="dot", line_color="#ef4444", annotation_text="stop")
    fig.add_hline(y=target, line_dash="dot", line_color="#22c55e", annotation_text="target")
    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=560,
        margin={"l": 40, "r": 20, "t": 58, "b": 36},
        xaxis_rangeslider_visible=False,
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate final NQ lightglow strategy HTML report.")
    parser.add_argument("--bars-cache", default=".tmp/nq-2020-final-report-bars.pkl")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--trades", default=".tmp/nq-2020-causal-evolution-trades.csv")
    parser.add_argument("--aggregate", default=".tmp/nq-2020-causal-evolution-aggregate.csv")
    parser.add_argument("--pressure", default=".tmp/nq-2020-causal-evolution-pressure.csv")
    parser.add_argument("--smc-trades", default=".tmp/nq-2020-lightglow-smc-trades.csv")
    parser.add_argument("--report", default="reports/NQ-2020-lightglow-smc-final-strategy-report.html")
    args = parser.parse_args()

    costs = BacktestCosts()
    all_trades = pd.read_csv(args.trades, parse_dates=["event_ts", "entry_ts", "exit_ts"])
    trades = all_trades[all_trades["template"] == CHOSEN_TEMPLATE].copy()
    trades = trades.sort_values("entry_ts").reset_index(drop=True)
    aggregate = pd.read_csv(args.aggregate)
    pressure = pd.read_csv(args.pressure)
    chosen_agg = aggregate[aggregate["template"] == CHOSEN_TEMPLATE].head(1)
    staged_agg = aggregate[aggregate["template"] == STAGED_TEMPLATE].head(1)
    chosen_pressure = pressure[pressure["template"] == CHOSEN_TEMPLATE].head(1)
    smc_trades = pd.read_csv(args.smc_trades) if Path(args.smc_trades).exists() else pd.DataFrame()

    bars = load_continuous_nq_bars(
        start_date=args.start_date,
        end_date=args.end_date,
        cache_path=Path(args.bars_cache),
    )
    original_summary = summarize(trades)
    trades = recompute_no_same_bar_exits(bars, trades)
    summary = summarize(trades)
    full_smc = summarize(smc_trades) if not smc_trades.empty else {}
    year = yearly(trades)
    best = trades.sort_values("net_points", ascending=False).head(5).copy()
    best["side"] = np.where(best["direction"] < 0, "SHORT", "LONG")
    best["entry_ts_text"] = best["entry_ts"].astype(str)
    best["exit_ts_text"] = best["exit_ts"].astype(str)

    charts = []
    for rank, (_, trade) in enumerate(best.head(3).iterrows(), start=1):
        charts.append(chart_for_trade(bars, trade, f"Best OOS Trade #{rank}: {trade['net_points']:.2f} net points"))

    cards = [
        ("OOS Trades", fmt(summary.get("trades"), 0)),
        ("OOS Net Points", fmt(summary.get("net_points"))),
        ("OOS Net Dollars", fmt(summary.get("net_dollars"))),
        ("OOS PF", fmt(summary.get("profit_factor"), 3)),
        ("OOS Win Rate", pct(summary.get("win_rate", 0))),
        ("OOS Max DD", fmt(summary.get("max_drawdown_points"))),
        ("3x Cost Net", fmt(chosen_pressure.iloc[0]["cost_3x_net_points"] if not chosen_pressure.empty else None)),
        ("Positive Years", pct(chosen_pressure.iloc[0]["positive_year_rate"] if not chosen_pressure.empty else 0)),
    ]
    card_html = "".join(f"<div class='card'><span>{label}</span><strong>{value}</strong></div>" for label, value in cards)
    original_compare = pd.DataFrame(
        [
            {"mode": "original_intrabar_bracket", **original_summary},
            {"mode": "no_same_bar_exit", **summary},
        ]
    )
    agg_html = table(
        pd.concat([chosen_agg, staged_agg], ignore_index=True),
        ["feature_id", "exit_mode", "selected_folds", "test_trades", "test_net_points", "test_profit_factor", "test_win_rate", "positive_test_fold_rate"],
    )
    pressure_html = table(
        chosen_pressure,
        ["oos_trades", "oos_net_points", "oos_profit_factor", "cost_1x_net_points", "cost_2x_net_points", "cost_3x_net_points", "positive_year_rate", "positive_rolling_rate"],
    )
    yearly_html = table(year, ["year", "trades", "net_points", "net_dollars", "profit_factor", "win_rate", "max_drawdown_points"])
    best_html = table(best, ["entry_ts_text", "exit_ts_text", "side", "entry_price", "exit_price", "net_points", "exit_reason"])
    chart_html = "\n".join(f"<section class='chart'>{chart}</section>" for chart in charts)

    report = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>NQ 2020+ Lightglow/SMC Strategy Final Report</title>
  <style>
    body {{ margin:0; background:#08111f; color:#e5edf7; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ max-width:1200px; margin:0 auto; padding:32px 24px 72px; }}
    h1 {{ font-size:34px; margin:0 0 8px; }}
    h2 {{ margin-top:34px; padding-bottom:8px; border-bottom:1px solid #263246; }}
    p, li {{ color:#b8c4d6; line-height:1.65; }}
    code {{ color:#93c5fd; }}
    .cards {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin:24px 0; }}
    .card {{ background:linear-gradient(145deg,#111827,#172033); border:1px solid #263246; border-radius:14px; padding:16px; }}
    .card span {{ display:block; color:#8ea0b9; font-size:13px; }}
    .card strong {{ display:block; margin-top:8px; font-size:23px; }}
    .warn {{ background:#201511; border-left:4px solid #f97316; padding:14px 16px; border-radius:10px; }}
    .note {{ background:#0f1d2d; border-left:4px solid #38bdf8; padding:14px 16px; border-radius:10px; }}
    table {{ border-collapse:collapse; width:100%; margin:12px 0 24px; font-size:13px; }}
    th,td {{ border:1px solid #263246; padding:8px 10px; text-align:right; }}
    th:first-child,td:first-child {{ text-align:left; }}
    th {{ background:#162033; color:#dbeafe; }}
    .chart {{ margin-top:22px; border:1px solid #263246; border-radius:14px; overflow:hidden; background:#111827; }}
  </style>
</head>
<body>
<main>
  <h1>NQ 2020+ Lightglow / SMC 策略回测报告</h1>
  <p>数据源：<code>{html.escape(str(_bar_zip_path()))}</code>；回测区间：<code>{args.start_date}</code> 到 <code>{args.end_date}</code>；交易品种：Databento GLBX.MDP3 连续 NQ 1分钟 K线。</p>
  <div class="cards">{card_html}</div>

  <h2>核心结论</h2>
  <p class="warn">直接把 lightglow/SMC 截图规则翻译成“PD 区 + sweep + CHoCH/BOS + MACD”的策略，在 2020+ 全样本为负：{fmt(full_smc.get("trades", 0), 0)} 笔，净 {fmt(full_smc.get("net_points", 0))} 点，PF {fmt(full_smc.get("profit_factor", 0), 3)}。因此最终不采用直译策略。</p>
  <p class="note">最终采用通过 walk-forward 与成本压力测试的变体：<code>fast_rally_fade_us_rth</code>。它本质上是“急涨扫流动性后衰竭做空”：US RTH 中价格快速上冲、远离 VWAP/成交量放大，随后确认失败，下一根开盘做空，止损放在事件极值外，RR=1，最多 30 分钟。本报告已重新计算为更保守的 <code>no-same-bar-exit</code>：入场所在 1分钟 K 线内不允许止盈/止损，至少从下一根 K 线才检查出场。</p>

  <h2>策略原理</h2>
  <ul>
    <li>行情特征：NQ 在 RTH 急速拉升后，若上冲无法延续，经常出现短线流动性回补和均值回归。</li>
    <li>入场：事件 K 线收盘确认后，下一根 K 线开盘入场，不使用当根未来高低点成交。</li>
    <li>止损：事件高点外加 ATR 缓冲，避免把未来回撤最低/最高当作止损依据。</li>
    <li>出场：RR=1 固定 bracket，或 30 分钟超时。</li>
    <li>过滤：只做 US RTH，且要求 VWAP/成交量上下文支持“急涨衰竭”。</li>
  </ul>

  <h2>无未来数据说明</h2>
  <ul>
    <li>所有 entry 都是 <code>next_open</code>，事件确认后下一根开盘成交。</li>
    <li>本报告的最终指标禁止 entry bar 内出场，规避 1分钟 OHLC 无法判断开盘后路径的问题。</li>
    <li>rolling/结构类条件只使用事件时刻之前已完成 K 线。</li>
    <li>同一根 K 线同时触及止盈/止损时，回测框架按保守路径处理。</li>
    <li>不使用 TradingView <code>lookahead_on</code>、未来日内高低点、未来 pivot 或事后绘制结构线。</li>
  </ul>

  <h2>Walk-Forward 与压力测试</h2>
  <p>下表第一张是原始 walk-forward 候选选择结果，第二张是原始 intrabar bracket 与本报告 no-same-bar-exit 重算后的对比。</p>
  {agg_html}
  {table(original_compare, ["mode", "trades", "net_points", "net_dollars", "profit_factor", "win_rate", "max_drawdown_points", "best_trade_points", "worst_trade_points"])}
  {pressure_html}

  <h2>年度 OOS 结果</h2>
  {yearly_html}

  <h2>最佳入场点与出场点</h2>
  <p>以下是 OOS 交易中净收益最高的交易。橙色三角为做空入场，蓝色 X 为出场，红/绿虚线为止损和目标位。</p>
  {best_html}
  {chart_html}
</main>
</body>
</html>"""
    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
