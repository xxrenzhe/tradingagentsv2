from __future__ import annotations

import argparse
import html
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"
for path in (ROOT_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtest_lightglow_nq_bars import build_lightglow_signals
from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.dataflows.databento import _bar_zip_path


BULLISH = 1
BEARISH = -1


@dataclass(frozen=True)
class StrategyConfig:
    session: str = "ldn_ny"
    max_hold_bars: int = 45
    stop_atr_mult: float = 1.25
    target_atr_mult: float = 2.4
    min_stop_points: float = 8.0
    min_target_points: float = 12.0
    sweep_lookback: int = 60
    zone_recent_bars: int = 15
    sweep_recent_bars: int = 12
    trend_lookback: int = 30
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9


def true_range(frame: pd.DataFrame) -> pd.Series:
    high = frame["High"].astype(float)
    low = frame["Low"].astype(float)
    close = frame["Close"].astype(float)
    previous_close = close.shift(1)
    return pd.concat([high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1).max(axis=1)


def add_macd(frame: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    out = frame.copy()
    close = out["Close"].astype(float)
    fast = close.ewm(span=config.macd_fast, adjust=False, min_periods=config.macd_fast).mean()
    slow = close.ewm(span=config.macd_slow, adjust=False, min_periods=config.macd_slow).mean()
    out["macd"] = fast - slow
    out["macd_signal"] = out["macd"].ewm(span=config.macd_signal, adjust=False, min_periods=config.macd_signal).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    out["atr_30"] = true_range(out).rolling(30, min_periods=10).mean()
    return out


def session_mask(frame: pd.DataFrame, session: str) -> pd.Series:
    minute = frame["minute_of_day"]
    if session == "all":
        return pd.Series(True, index=frame.index)
    if session == "europe":
        return (minute >= 7 * 60) & (minute < 13 * 60 + 30)
    if session == "us_rth":
        return (minute >= 13 * 60 + 30) & (minute < 20 * 60)
    if session == "us_late":
        return (minute >= 20 * 60) & (minute < 23 * 60)
    if session == "ldn_ny":
        return (minute >= 7 * 60) & (minute < 20 * 60)
    if session == "asia":
        return (minute < 7 * 60) | (minute >= 23 * 60)
    raise ValueError(f"unknown session: {session}")


def build_strategy_signals(frame: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    out = add_macd(build_lightglow_signals(frame), config)
    high = out["High"].astype(float)
    low = out["Low"].astype(float)
    close = out["Close"].astype(float)
    open_price = out["Open"].astype(float)

    prior_high = high.rolling(config.sweep_lookback, min_periods=config.sweep_lookback).max().shift(1)
    prior_low = low.rolling(config.sweep_lookback, min_periods=config.sweep_lookback).min().shift(1)
    bottom_sweep = (low < prior_low) & (close > prior_low)
    top_sweep = (high > prior_high) & (close < prior_high)

    pd_signal = out["premium_discount_reversal"].astype(int)
    bullish_zone = (pd_signal == BULLISH).rolling(config.zone_recent_bars, min_periods=1).max().shift(1).fillna(False).astype(bool)
    bearish_zone = (pd_signal == BEARISH).rolling(config.zone_recent_bars, min_periods=1).max().shift(1).fillna(False).astype(bool)
    recent_bottom_sweep = bottom_sweep.rolling(config.sweep_recent_bars, min_periods=1).max().shift(1).fillna(False).astype(bool)
    recent_top_sweep = top_sweep.rolling(config.sweep_recent_bars, min_periods=1).max().shift(1).fillna(False).astype(bool)

    internal_choch = out["internal_choch"].astype(int)
    internal_bos = out["internal_bos"].astype(int)
    swing_bos = out["swing_bos"].astype(int)
    macd_hist = out["macd_hist"].astype(float)
    macd = out["macd"].astype(float)
    trend_delta = close - close.shift(config.trend_lookback)
    body = close - open_price
    body_share = body.abs() / (high - low).replace(0, np.nan)

    long_reversal = (
        bullish_zone
        & recent_bottom_sweep
        & ((internal_choch == BULLISH) | (internal_bos == BULLISH))
        & (macd_hist > macd_hist.shift(1))
        & (macd > out["macd_signal"])
    )
    short_reversal = (
        bearish_zone
        & recent_top_sweep
        & ((internal_choch == BEARISH) | (internal_bos == BEARISH))
        & (macd_hist < macd_hist.shift(1))
        & (macd < out["macd_signal"])
    )

    continuation_long = (
        (swing_bos == BULLISH)
        & (trend_delta > 0)
        & (macd_hist > 0)
        & (body > 0)
        & (body_share >= 0.45)
    )
    continuation_short = (
        (swing_bos == BEARISH)
        & (trend_delta < 0)
        & (macd_hist < 0)
        & (body < 0)
        & (body_share >= 0.45)
    )

    raw_signal = np.select(
        [long_reversal | continuation_long, short_reversal | continuation_short],
        [BULLISH, BEARISH],
        default=0,
    ).astype(np.int8)
    out["strategy_signal"] = raw_signal
    out["signal_family"] = np.select(
        [long_reversal | short_reversal, continuation_long | continuation_short],
        ["sweep_choch_reversal", "bos_momentum_continuation"],
        default="",
    )
    out.loc[~session_mask(out, config.session), "strategy_signal"] = 0
    out["strategy_signal"] = out["strategy_signal"].where(out["strategy_signal"] != out["strategy_signal"].shift(1), 0).astype(np.int8)
    return out


def backtest(frame: pd.DataFrame, config: StrategyConfig, costs: BacktestCosts) -> pd.DataFrame:
    signal = frame["strategy_signal"].to_numpy(dtype=np.int8)
    signal_indexes = np.flatnonzero(signal != 0)
    if len(signal_indexes) == 0:
        return pd.DataFrame()

    open_prices = frame["Open"].to_numpy(dtype=float)
    high_prices = frame["High"].to_numpy(dtype=float)
    low_prices = frame["Low"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    atr = frame["atr_30"].to_numpy(dtype=float)
    timestamps = frame["ts"].to_numpy()
    symbols = frame["symbol"].astype(str).to_numpy()
    families = frame["signal_family"].astype(str).to_numpy()

    rows: list[dict[str, Any]] = []
    next_available_index = 0
    for signal_index in signal_indexes:
        entry_index = int(signal_index) + 1
        if entry_index <= next_available_index or entry_index >= len(frame):
            continue
        direction = int(signal[signal_index])
        entry_price = float(open_prices[entry_index])
        if not np.isfinite(entry_price):
            continue
        stop_distance = max(config.min_stop_points, float(atr[signal_index]) * config.stop_atr_mult if np.isfinite(atr[signal_index]) else config.min_stop_points)
        target_distance = max(config.min_target_points, float(atr[signal_index]) * config.target_atr_mult if np.isfinite(atr[signal_index]) else config.min_target_points)
        stop_price = entry_price - stop_distance if direction > 0 else entry_price + stop_distance
        target_price = entry_price + target_distance if direction > 0 else entry_price - target_distance
        planned_exit = min(entry_index + config.max_hold_bars, len(frame) - 1)
        exit_index = planned_exit
        exit_price = float(close_prices[planned_exit])
        exit_reason = "time"

        for path_index in range(entry_index, planned_exit + 1):
            if symbols[path_index] != symbols[signal_index]:
                exit_index = max(entry_index, path_index - 1)
                exit_price = float(close_prices[exit_index])
                exit_reason = "symbol_change"
                break
            if direction > 0:
                stop_hit = low_prices[path_index] <= stop_price
                target_hit = high_prices[path_index] >= target_price
            else:
                stop_hit = high_prices[path_index] >= stop_price
                target_hit = low_prices[path_index] <= target_price
            if stop_hit:
                exit_index = path_index
                exit_price = float(stop_price)
                exit_reason = "stop_loss"
                break
            if target_hit:
                exit_index = path_index
                exit_price = float(target_price)
                exit_reason = "take_profit"
                break

        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points
        rows.append(
            {
                "signal_ts": timestamps[signal_index],
                "entry_ts": timestamps[entry_index],
                "exit_ts": timestamps[exit_index],
                "symbol": symbols[signal_index],
                "direction": direction,
                "family": families[signal_index],
                "entry_price": entry_price,
                "exit_price": exit_price,
                "stop_price": float(stop_price),
                "target_price": float(target_price),
                "exit_reason": exit_reason,
                "gross_points": float(gross_points),
                "net_points": float(net_points),
                "net_dollars": float(net_points * costs.point_value),
                "entry_index": int(entry_index),
                "exit_index": int(exit_index),
                "signal_index": int(signal_index),
            }
        )
        next_available_index = exit_index + 1
    return pd.DataFrame(rows)


def summarize_trades(trades: pd.DataFrame, costs: BacktestCosts) -> dict[str, Any]:
    if trades.empty:
        return {"trades": 0}
    net = trades["net_points"].astype(float)
    gross = trades["gross_points"].astype(float)
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    wins = net[net > 0].sum()
    losses = abs(net[net < 0].sum())
    return {
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "net_dollars": float(net.sum() * costs.point_value),
        "gross_points": float(gross.sum()),
        "win_rate": float((net > 0).mean()),
        "profit_factor": float(wins / losses) if losses else 999.0,
        "avg_points": float(net.mean()),
        "median_points": float(net.median()),
        "max_drawdown_points": float(abs(drawdown.min())),
        "best_trade_points": float(net.max()),
        "worst_trade_points": float(net.min()),
        "take_profit_rate": float((trades["exit_reason"] == "take_profit").mean()),
        "stop_loss_rate": float((trades["exit_reason"] == "stop_loss").mean()),
    }


def yearly_summary(trades: pd.DataFrame, costs: BacktestCosts) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    data = trades.copy()
    data["year"] = pd.to_datetime(data["entry_ts"], utc=True).dt.year
    rows = []
    for year, group in data.groupby("year"):
        summary = summarize_trades(group, costs)
        rows.append({"year": int(year), **summary})
    return pd.DataFrame(rows)


def best_trade_windows(trades: pd.DataFrame, count: int = 3) -> pd.DataFrame:
    if trades.empty:
        return trades
    return trades.sort_values("net_points", ascending=False).head(count).copy()


def make_trade_chart(frame: pd.DataFrame, trade: pd.Series, title: str) -> str:
    entry_index = int(trade["entry_index"])
    exit_index = int(trade["exit_index"])
    start = max(0, entry_index - 90)
    end = min(len(frame), exit_index + 90)
    data = frame.iloc[start:end].copy()
    entry_ts = pd.to_datetime(trade["entry_ts"], utc=True)
    exit_ts = pd.to_datetime(trade["exit_ts"], utc=True)
    direction = int(trade["direction"])

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.72, 0.28])
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
        ),
        row=1,
        col=1,
    )
    fig.add_trace(go.Bar(x=data["ts"], y=data["macd_hist"], name="MACD hist", marker_color=np.where(data["macd_hist"] >= 0, "#14b8a6", "#ef4444")), row=2, col=1)
    fig.add_trace(go.Scatter(x=data["ts"], y=data["macd"], name="MACD", line={"color": "#22c55e", "width": 2}), row=2, col=1)
    fig.add_trace(go.Scatter(x=data["ts"], y=data["macd_signal"], name="Signal", line={"color": "#eab308", "width": 1.5}), row=2, col=1)

    marker_color = "#22c55e" if direction > 0 else "#ef4444"
    marker_symbol = "triangle-up" if direction > 0 else "triangle-down"
    fig.add_trace(
        go.Scatter(
            x=[entry_ts],
            y=[trade["entry_price"]],
            mode="markers+text",
            marker={"size": 14, "color": marker_color, "symbol": marker_symbol},
            text=["ENTRY"],
            textposition="top center",
            name="Entry",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=[exit_ts],
            y=[trade["exit_price"]],
            mode="markers+text",
            marker={"size": 14, "color": "#38bdf8", "symbol": "x"},
            text=["EXIT"],
            textposition="bottom center",
            name="Exit",
        ),
        row=1,
        col=1,
    )
    fig.add_hline(y=float(trade["stop_price"]), line_dash="dot", line_color="#ef4444", annotation_text="Stop", row=1, col=1)
    fig.add_hline(y=float(trade["target_price"]), line_dash="dot", line_color="#22c55e", annotation_text="Target", row=1, col=1)
    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=620,
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
        xaxis_rangeslider_visible=False,
        legend={"orientation": "h", "y": 1.02},
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def fmt(value: Any, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "N/A"
    if isinstance(value, (float, np.floating)):
        return f"{value:,.{digits}f}"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    return html.escape(str(value))


def pct(value: Any) -> str:
    if value is None or not np.isfinite(float(value)):
        return "N/A"
    return f"{float(value):.2%}"


def table_html(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for _, row in frame[columns].iterrows():
        cells = []
        for column in columns:
            value = row[column]
            cells.append(f"<td>{fmt(value, 3) if isinstance(value, float) else html.escape(str(value))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_report(
    frame: pd.DataFrame,
    trades: pd.DataFrame,
    summary: dict[str, Any],
    yearly: pd.DataFrame,
    best_trades: pd.DataFrame,
    charts: list[str],
    config: StrategyConfig,
    costs: BacktestCosts,
    args: argparse.Namespace,
) -> str:
    best_rows = best_trades.copy()
    if not best_rows.empty:
        best_rows["entry_ts"] = pd.to_datetime(best_rows["entry_ts"], utc=True).astype(str)
        best_rows["exit_ts"] = pd.to_datetime(best_rows["exit_ts"], utc=True).astype(str)
        best_rows["side"] = np.where(best_rows["direction"] > 0, "LONG", "SHORT")
    yearly_rows = yearly.copy()

    metric_cards = [
        ("交易次数", fmt(summary.get("trades", 0), 0)),
        ("净点数", fmt(summary.get("net_points", 0.0), 2)),
        ("净美元(NQ)", fmt(summary.get("net_dollars", 0.0), 2)),
        ("胜率", pct(summary.get("win_rate", 0.0))),
        ("Profit Factor", fmt(summary.get("profit_factor", 0.0), 3)),
        ("最大回撤点数", fmt(summary.get("max_drawdown_points", 0.0), 2)),
        ("平均每笔点数", fmt(summary.get("avg_points", 0.0), 3)),
        ("止盈/止损率", f"{pct(summary.get('take_profit_rate', 0.0))} / {pct(summary.get('stop_loss_rate', 0.0))}"),
    ]
    cards = "".join(f"<div class='card'><span>{label}</span><strong>{value}</strong></div>" for label, value in metric_cards)
    chart_html = "\n".join(f"<section class='chart'>{chart}</section>" for chart in charts)
    best_table = table_html(
        best_rows,
        ["entry_ts", "exit_ts", "side", "family", "entry_price", "exit_price", "net_points", "exit_reason"],
    ) if not best_rows.empty else "<p>No best trades.</p>"
    yearly_table = table_html(
        yearly_rows,
        ["year", "trades", "net_points", "net_dollars", "win_rate", "profit_factor", "max_drawdown_points"],
    ) if not yearly_rows.empty else "<p>No yearly rows.</p>"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>NQ Lightglow SMC Strategy Backtest</title>
  <style>
    body {{ margin: 0; background: #0b1020; color: #e5edf7; font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 24px 64px; }}
    h1 {{ font-size: 34px; margin: 0 0 8px; }}
    h2 {{ margin-top: 34px; border-bottom: 1px solid #243044; padding-bottom: 8px; }}
    p, li {{ color: #b8c4d6; line-height: 1.65; }}
    code {{ color: #93c5fd; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 24px 0; }}
    .card {{ background: linear-gradient(145deg, #111827, #172033); border: 1px solid #263246; border-radius: 14px; padding: 16px; }}
    .card span {{ display: block; color: #8ea0b9; font-size: 13px; }}
    .card strong {{ display: block; margin-top: 8px; font-size: 24px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; font-size: 13px; }}
    th, td {{ border: 1px solid #263246; padding: 8px 10px; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #162033; color: #dbeafe; }}
    .note {{ background: #111827; border-left: 4px solid #38bdf8; padding: 12px 16px; border-radius: 8px; }}
    .warn {{ background: #1f1712; border-left: 4px solid #f97316; padding: 12px 16px; border-radius: 8px; }}
    .chart {{ margin-top: 22px; border: 1px solid #263246; border-radius: 14px; overflow: hidden; background: #111827; }}
  </style>
</head>
<body>
<main>
  <h1>NQ 2020+ Lightglow / SMC 策略回测</h1>
  <p>数据源：<code>{html.escape(str(_bar_zip_path()))}</code>，区间：<code>{args.start_date}</code> 到 <code>{args.end_date}</code>，实际加载：<code>{frame['ts'].min()}</code> 到 <code>{frame['ts'].max()}</code>，共 <code>{len(frame):,}</code> 根 1 分钟 K 线。</p>
  <div class="cards">{cards}</div>
  <h2>策略原理</h2>
  <p>策略来自截图和 <code>docs/Strategy/lightglow.md</code> 的共同特征：只交易两类形态。第一类是扫流动性后的反转：价格先处在确认后的 discount/premium 区，随后扫前低/前高并收回，再由 internal CHoCH/BOS 和 MACD 动能转向确认。第二类是趋势延续：swing BOS 发生在同向短趋势和 MACD 柱体扩张时，下一根开盘进场。</p>
  <ul>
    <li>入场：信号 K 线收盘后确认，下一根 1 分钟 K 线开盘成交。</li>
    <li>出场：ATR 动态止损/止盈，或最多持仓 <code>{config.max_hold_bars}</code> 根 K 线。</li>
    <li>成本：<code>{costs.round_trip_cost_points:.3f}</code> NQ 点/往返，含每边 1 tick 滑点和佣金。</li>
    <li>交易时段：<code>{config.session}</code>。</li>
  </ul>
  <div class="warn">无未来数据约束：pivot 使用右侧确认后的时点才更新；BOS/CHoCH 只在收盘突破已确认结构位后触发；所有入场延迟到下一根开盘；rolling high/low 全部 <code>shift(1)</code>；未使用 TradingView <code>lookahead_on</code> 或已知未来日内高低点。</div>
  <h2>年度结果</h2>
  {yearly_table}
  <h2>最佳入场/出场点</h2>
  <p>下表和 K 线图展示净收益最高的交易。绿色/红色三角是入场，蓝色 X 是出场，虚线为当笔止损/止盈。</p>
  {best_table}
  {chart_html}
  <h2>结论</h2>
  <p class="note">这是一份历史研究回测，不是实盘承诺。若结果为正，下一步应做参数稳定性、走前验证、成本压力测试和 IBKR paper trading；若结果不稳定，优先把该策略当作过滤器，而不是独立交易系统。</p>
</main>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest a causal Lightglow/SMC NQ strategy and render an HTML report.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-2020-lightglow-smc-cache.pkl")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--report", default="reports/NQ-2020-lightglow-smc-strategy-backtest.html")
    parser.add_argument("--trades-output", default=".tmp/nq-2020-lightglow-smc-trades.csv")
    parser.add_argument("--best-trades", type=int, default=3)
    args = parser.parse_args()

    config = StrategyConfig()
    costs = BacktestCosts()
    frame = load_continuous_nq_bars(args)
    frame = build_strategy_signals(frame, config)
    trades = backtest(frame, config, costs)
    summary = summarize_trades(trades, costs)
    yearly = yearly_summary(trades, costs)
    best = best_trade_windows(trades, args.best_trades)

    Path(args.trades_output).parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(args.trades_output, index=False)

    charts = [
        make_trade_chart(frame, row, f"Best Trade #{index}: {row['net_points']:.2f} pts")
        for index, (_, row) in enumerate(best.iterrows(), start=1)
    ]
    report = build_report(frame, trades, summary, yearly, best, charts, config, costs, args)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"wrote {report_path}")
    print(f"wrote {args.trades_output}")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
