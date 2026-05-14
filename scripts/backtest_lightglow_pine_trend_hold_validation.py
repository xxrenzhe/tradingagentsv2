from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from tradingagents.backtesting.short_patterns import BacktestCosts


@dataclass(frozen=True)
class LightglowPineConfig:
    range_length: int = 100
    premium_threshold: float = 0.90
    discount_threshold: float = 0.10
    reverse_lightglow_signal: bool = True
    rearm_mode: str = "equilibrium"
    cooldown_bars: int = 10
    ema_fast_length: int = 20
    ema_mid_length: int = 60
    use_ema_trend_filter: bool = True
    fixed_hold_bars: int = 2
    trend_max_hold_bars: int = 120
    atr_length: int = 14
    initial_stop_atr: float = 1.8
    trail_stop_atr: float = 2.4
    breakeven_trigger_atr: float = 1.2
    exit_on_ema_break: bool = True


def load_nq_1m_bars(args: argparse.Namespace) -> pd.DataFrame:
    loader_args = argparse.Namespace(
        start_date=args.start_date,
        end_date=args.end_date,
        cache=args.cache,
        chunk_size=args.chunk_size,
        min_volume=args.min_volume,
    )
    bars = load_continuous_nq_bars(loader_args)
    bars = bars.sort_values("ts").reset_index(drop=True)
    return bars[["ts", "symbol", "Open", "High", "Low", "Close", "Volume", "minute_of_day"]].copy()


def add_pine_proxy_features(bars: pd.DataFrame, config: LightglowPineConfig) -> pd.DataFrame:
    frame = bars.copy().reset_index(drop=True)
    high = pd.to_numeric(frame["High"], errors="coerce")
    low = pd.to_numeric(frame["Low"], errors="coerce")
    close = pd.to_numeric(frame["Close"], errors="coerce")
    frame["range_high"] = high.rolling(config.range_length, min_periods=config.range_length).max()
    frame["range_low"] = low.rolling(config.range_length, min_periods=config.range_length).min()
    frame["range_size"] = frame["range_high"] - frame["range_low"]
    frame["premium_level"] = frame["range_low"] + frame["range_size"] * config.premium_threshold
    frame["discount_level"] = frame["range_low"] + frame["range_size"] * config.discount_threshold
    frame["equilibrium"] = (frame["range_high"] + frame["range_low"]) * 0.5
    frame["ema_fast"] = close.ewm(span=config.ema_fast_length, adjust=False, min_periods=config.ema_fast_length).mean()
    frame["ema_mid"] = close.ewm(span=config.ema_mid_length, adjust=False, min_periods=config.ema_mid_length).mean()
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    frame["atr"] = true_range.ewm(span=config.atr_length, adjust=False, min_periods=config.atr_length).mean()
    frame["trend_20_60"] = frame["ema_fast"] - frame["ema_mid"]
    frame["dist_ema60"] = close - frame["ema_mid"]
    return frame


def build_armed_signals(frame: pd.DataFrame, config: LightglowPineConfig) -> pd.Series:
    close = pd.to_numeric(frame["Close"], errors="coerce").to_numpy(dtype=float)
    premium_level = frame["premium_level"].to_numpy(dtype=float)
    discount_level = frame["discount_level"].to_numpy(dtype=float)
    equilibrium = frame["equilibrium"].to_numpy(dtype=float)
    range_size = frame["range_size"].to_numpy(dtype=float)

    premium_armed = True
    discount_armed = True
    directions = np.zeros(len(frame), dtype=np.int8)

    for index in range(len(frame)):
        if not np.isfinite(range_size[index]) or range_size[index] <= 0:
            continue
        in_premium = close[index] >= premium_level[index]
        in_discount = close[index] <= discount_level[index]

        if config.rearm_mode == "outside_zone":
            if not in_premium:
                premium_armed = True
            if not in_discount:
                discount_armed = True
        elif config.rearm_mode == "every_flat_bar":
            premium_armed = True
            discount_armed = True
        else:
            if close[index] <= equilibrium[index]:
                premium_armed = True
            if close[index] >= equilibrium[index]:
                discount_armed = True

        raw_direction = 0
        if in_discount and discount_armed:
            raw_direction = 1
            discount_armed = False
        elif in_premium and premium_armed:
            raw_direction = -1
            premium_armed = False

        if raw_direction:
            directions[index] = -raw_direction if config.reverse_lightglow_signal else raw_direction

    return pd.Series(directions, index=frame.index, name="armed_trade_direction")


def _cost_points(costs: BacktestCosts) -> float:
    return float(costs.round_trip_cost_points)


def _summarize(trades: pd.DataFrame, costs: BacktestCosts) -> dict[str, Any]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "net_dollars": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_points": 0.0,
            "avg_bars_held": 0.0,
            "max_drawdown_points": 0.0,
            "worst_trade_points": 0.0,
        }
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    wins = net[net > 0].sum()
    losses = abs(net[net < 0].sum())
    return {
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "net_dollars": float(net.sum() * costs.point_value),
        "profit_factor": float(wins / losses) if losses else (999.0 if wins > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "avg_points": float(net.mean()),
        "avg_bars_held": float(pd.to_numeric(trades["bars_held"], errors="coerce").mean()),
        "max_drawdown_points": float(drawdown.max()),
        "worst_trade_points": float(net.min()),
    }


def _exit_trade(
    rows: list[dict[str, Any]],
    *,
    frame: pd.DataFrame,
    signal_index: int,
    entry_index: int,
    exit_index: int,
    direction: int,
    entry_price: float,
    exit_price: float,
    exit_reason: str,
    costs: BacktestCosts,
) -> None:
    gross_points = (exit_price - entry_price) * direction
    net_points = gross_points - _cost_points(costs)
    rows.append(
        {
            "entry_signal_ts": frame["ts"].iat[signal_index],
            "entry_ts": frame["ts"].iat[entry_index],
            "exit_ts": frame["ts"].iat[exit_index],
            "symbol": frame["symbol"].iat[entry_index],
            "direction": int(direction),
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "exit_reason": exit_reason,
            "bars_held": int(exit_index - entry_index),
            "gross_points": float(gross_points),
            "net_points": float(net_points),
            "net_dollars": float(net_points * costs.point_value),
            "signal_index": int(signal_index),
            "entry_index": int(entry_index),
            "exit_index": int(exit_index),
        }
    )


def backtest_fixed_bars(frame: pd.DataFrame, signals: pd.Series, config: LightglowPineConfig, costs: BacktestCosts) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    open_prices = frame["Open"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    symbols = frame["symbol"].astype(str).to_numpy()
    last_exit_index = -10**9
    index = 0
    signal_values = signals.to_numpy(dtype=int)
    while index < len(frame) - config.fixed_hold_bars - 1:
        direction = int(signal_values[index])
        if direction == 0:
            index += 1
            continue
        entry_index = index + 1
        exit_index = entry_index + config.fixed_hold_bars
        if entry_index <= last_exit_index + config.cooldown_bars or exit_index >= len(frame):
            index += 1
            continue
        if symbols[entry_index] != symbols[index] or symbols[exit_index] != symbols[entry_index]:
            index += 1
            continue
        if config.use_ema_trend_filter and direction > 0:
            if frame["dist_ema60"].iat[index] < 0 and frame["trend_20_60"].iat[index] < 0:
                index += 1
                continue
        _exit_trade(
            rows,
            frame=frame,
            signal_index=index,
            entry_index=entry_index,
            exit_index=exit_index,
            direction=direction,
            entry_price=float(open_prices[entry_index]),
            exit_price=float(close_prices[exit_index]),
            exit_reason="fixed_bars",
            costs=costs,
        )
        last_exit_index = exit_index
        index = exit_index + 1
    return pd.DataFrame(rows)


def backtest_trend_hold(frame: pd.DataFrame, signals: pd.Series, config: LightglowPineConfig, costs: BacktestCosts) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    open_prices = frame["Open"].to_numpy(dtype=float)
    high_prices = frame["High"].to_numpy(dtype=float)
    low_prices = frame["Low"].to_numpy(dtype=float)
    close_prices = frame["Close"].to_numpy(dtype=float)
    atr = frame["atr"].to_numpy(dtype=float)
    ema_fast = frame["ema_fast"].to_numpy(dtype=float)
    ema_mid = frame["ema_mid"].to_numpy(dtype=float)
    dist_ema60 = frame["dist_ema60"].to_numpy(dtype=float)
    trend_20_60 = frame["trend_20_60"].to_numpy(dtype=float)
    symbols = frame["symbol"].astype(str).to_numpy()
    signal_values = signals.to_numpy(dtype=int)

    last_exit_index = -10**9
    index = 0
    while index < len(frame) - 2:
        direction = int(signal_values[index])
        if direction == 0:
            index += 1
            continue
        entry_index = index + 1
        if entry_index <= last_exit_index + config.cooldown_bars or entry_index >= len(frame):
            index += 1
            continue
        if symbols[entry_index] != symbols[index]:
            index += 1
            continue
        if config.use_ema_trend_filter and direction > 0 and dist_ema60[index] < 0 and trend_20_60[index] < 0:
            index += 1
            continue
        entry_price = float(open_prices[entry_index])
        risk_atr = float(atr[entry_index]) if np.isfinite(atr[entry_index]) and atr[entry_index] > 0 else float(
            np.nanmedian(atr[max(0, entry_index - 100) : entry_index + 1])
        )
        if not np.isfinite(risk_atr) or risk_atr <= 0:
            index += 1
            continue

        if direction > 0:
            protective_stop = entry_price - risk_atr * config.initial_stop_atr
            best_favorable_price = float(high_prices[entry_index])
        else:
            protective_stop = entry_price + risk_atr * config.initial_stop_atr
            best_favorable_price = float(low_prices[entry_index])

        exit_index = entry_index
        exit_price = float(close_prices[entry_index])
        exit_reason = "end_of_data"
        path_end = min(len(frame) - 1, entry_index + config.trend_max_hold_bars)
        for path_index in range(entry_index, path_end + 1):
            if symbols[path_index] != symbols[entry_index]:
                exit_index = path_index - 1
                exit_price = float(close_prices[exit_index])
                exit_reason = "contract_roll"
                break

            if direction > 0 and low_prices[path_index] <= protective_stop:
                exit_index = path_index
                exit_price = float(protective_stop)
                exit_reason = "atr_protective_stop"
                break
            if direction < 0 and high_prices[path_index] >= protective_stop:
                exit_index = path_index
                exit_price = float(protective_stop)
                exit_reason = "atr_protective_stop"
                break

            bars_held = path_index - entry_index
            if bars_held >= config.trend_max_hold_bars:
                exit_index = path_index
                exit_price = float(close_prices[path_index])
                exit_reason = "max_hold"
                break

            if config.exit_on_ema_break and bars_held > 0:
                if direction > 0 and close_prices[path_index] < ema_mid[path_index] and ema_fast[path_index] < ema_mid[path_index]:
                    exit_index = path_index
                    exit_price = float(close_prices[path_index])
                    exit_reason = "ema_break"
                    break
                if direction < 0 and close_prices[path_index] > ema_mid[path_index] and ema_fast[path_index] > ema_mid[path_index]:
                    exit_index = path_index
                    exit_price = float(close_prices[path_index])
                    exit_reason = "ema_break"
                    break

            if direction > 0:
                best_favorable_price = max(best_favorable_price, float(high_prices[path_index]))
                initial_stop = entry_price - risk_atr * config.initial_stop_atr
                trail_stop = best_favorable_price - risk_atr * config.trail_stop_atr
                breakeven_stop = entry_price if best_favorable_price - entry_price >= risk_atr * config.breakeven_trigger_atr else initial_stop
                protective_stop = max(initial_stop, trail_stop, breakeven_stop)
            else:
                best_favorable_price = min(best_favorable_price, float(low_prices[path_index]))
                initial_stop = entry_price + risk_atr * config.initial_stop_atr
                trail_stop = best_favorable_price + risk_atr * config.trail_stop_atr
                breakeven_stop = entry_price if entry_price - best_favorable_price >= risk_atr * config.breakeven_trigger_atr else initial_stop
                protective_stop = min(initial_stop, trail_stop, breakeven_stop)
        else:
            exit_index = path_end
            exit_price = float(close_prices[exit_index])
            exit_reason = "max_hold"

        _exit_trade(
            rows,
            frame=frame,
            signal_index=index,
            entry_index=entry_index,
            exit_index=exit_index,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            exit_reason=exit_reason,
            costs=costs,
        )
        last_exit_index = exit_index
        index = exit_index + 1
    return pd.DataFrame(rows)


def yearly_summary(trades: pd.DataFrame, costs: BacktestCosts) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    frame = trades.copy()
    frame["year"] = pd.to_datetime(frame["entry_ts"], utc=True).dt.year
    rows = []
    for year, group in frame.groupby("year"):
        row = {"year": int(year)}
        row.update(_summarize(group, costs))
        rows.append(row)
    return pd.DataFrame(rows)


def exit_reason_summary(trades: pd.DataFrame, costs: BacktestCosts) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows = []
    for reason, group in trades.groupby("exit_reason"):
        row = {"exit_reason": reason}
        row.update(_summarize(group, costs))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("net_points", ascending=False)


def fmt(value: object) -> str:
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, float):
        if np.isfinite(value) and value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.4f}"
    return str(value)


def html_table(frame: pd.DataFrame, columns: list[str], *, limit: int | None = None) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    data = frame[columns].head(limit) if limit else frame[columns]
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    rows = []
    for _, row in data.iterrows():
        rows.append("<tr>" + "".join(f"<td>{html.escape(fmt(row[column]))}</td>" for column in columns) + "</tr>")
    return f"<div class=\"table-wrap\"><table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"


def write_html_report(
    path: Path,
    *,
    fixed: pd.DataFrame,
    trend: pd.DataFrame,
    fixed_yearly: pd.DataFrame,
    trend_yearly: pd.DataFrame,
    trend_reasons: pd.DataFrame,
    config: LightglowPineConfig,
    costs: BacktestCosts,
    args: argparse.Namespace,
) -> None:
    fixed_summary = _summarize(fixed, costs)
    trend_summary = _summarize(trend, costs)
    comparison = pd.DataFrame(
        [
            {"variant": "fixed_2_bar", **fixed_summary},
            {"variant": "trend_hold_atr_ema", **trend_summary},
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Lightglow PD Reversal v1 Trend-Hold Validation</title>
  <style>
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:#f8fafc; color:#111827; }}
    header, main {{ max-width:1180px; margin:0 auto; padding:24px; }}
    header {{ background:#111827; color:white; max-width:none; }}
    header > * {{ max-width:1180px; margin-left:auto; margin-right:auto; }}
    section {{ background:white; border:1px solid #e5e7eb; border-radius:8px; padding:20px; margin:16px 0; }}
    table {{ border-collapse:collapse; width:100%; font-size:13px; }}
    th, td {{ border-bottom:1px solid #e5e7eb; padding:8px; text-align:left; }}
    th {{ background:#f1f5f9; }}
    .table-wrap {{ overflow-x:auto; }}
    .note {{ border-left:4px solid #2563eb; background:#eff6ff; padding:12px 14px; border-radius:6px; }}
    code {{ background:#e5e7eb; padding:2px 4px; border-radius:4px; }}
  </style>
</head>
<body>
  <header>
    <h1>Lightglow PD Reversal v1 - Trend-Hold 回测验证</h1>
    <p>数据：NQ 1m Databento bars，区间 {html.escape(args.start_date)} 到 {html.escape(args.end_date)}。成本：{costs.round_trip_cost_points:.4f} NQ points / round trip。</p>
  </header>
  <main>
    <section>
      <h2>结论</h2>
      <div class="note">
        <p>本报告验证 TradingView Pine 的执行层改动：从固定 <code>{config.fixed_hold_bars}</code> 根 K 线退出，改为 <code>Trend Hold</code>，包含 ATR 初始止损、ATR trailing、保本、EMA 趋势破坏退出和最大持仓。</p>
        <p>该验证只使用当前及历史 bar，入场信号在信号 bar 收盘确认，下一根 bar 开盘成交；不读取未来 bar 生成信号。</p>
      </div>
    </section>
    <section>
      <h2>总体对比</h2>
      {html_table(comparison, ["variant", "trades", "net_points", "net_dollars", "profit_factor", "win_rate", "avg_points", "avg_bars_held", "max_drawdown_points", "worst_trade_points"])}
    </section>
    <section>
      <h2>Trend-Hold 年度表现</h2>
      {html_table(trend_yearly, ["year", "trades", "net_points", "net_dollars", "profit_factor", "win_rate", "avg_points", "avg_bars_held", "max_drawdown_points", "worst_trade_points"])}
    </section>
    <section>
      <h2>Fixed 2-Bar 年度表现</h2>
      {html_table(fixed_yearly, ["year", "trades", "net_points", "net_dollars", "profit_factor", "win_rate", "avg_points", "avg_bars_held", "max_drawdown_points", "worst_trade_points"])}
    </section>
    <section>
      <h2>Trend-Hold 退出原因</h2>
      {html_table(trend_reasons, ["exit_reason", "trades", "net_points", "net_dollars", "profit_factor", "win_rate", "avg_points", "avg_bars_held", "max_drawdown_points", "worst_trade_points"])}
    </section>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    config = LightglowPineConfig(
        range_length=args.range_length,
        premium_threshold=args.premium_threshold,
        discount_threshold=args.discount_threshold,
        reverse_lightglow_signal=not args.direct_pd_signal,
        cooldown_bars=args.cooldown_bars,
        fixed_hold_bars=args.fixed_hold_bars,
        trend_max_hold_bars=args.trend_max_hold_bars,
        initial_stop_atr=args.initial_stop_atr,
        trail_stop_atr=args.trail_stop_atr,
        breakeven_trigger_atr=args.breakeven_trigger_atr,
    )
    costs = BacktestCosts()
    bars = add_pine_proxy_features(load_nq_1m_bars(args), config)
    signals = build_armed_signals(bars, config)
    fixed = backtest_fixed_bars(bars, signals, config, costs)
    trend = backtest_trend_hold(bars, signals, config, costs)
    fixed_yearly = yearly_summary(fixed, costs)
    trend_yearly = yearly_summary(trend, costs)
    trend_reasons = exit_reason_summary(trend, costs)

    for output, frame in (
        (args.fixed_trades_output, fixed),
        (args.trend_trades_output, trend),
        (args.fixed_yearly_output, fixed_yearly),
        (args.trend_yearly_output, trend_yearly),
        (args.trend_exit_reasons_output, trend_reasons),
    ):
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output_path, index=False)

    summary = {
        "strategy_name": "Lightglow PD Reversal v1 - Armed Trend-Hold Validation",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "config": config.__dict__,
        "cost_points": costs.round_trip_cost_points,
        "fixed_2_bar": _summarize(fixed, costs),
        "trend_hold": _summarize(trend, costs),
        "outputs": {
            "fixed_trades": args.fixed_trades_output,
            "trend_trades": args.trend_trades_output,
            "fixed_yearly": args.fixed_yearly_output,
            "trend_yearly": args.trend_yearly_output,
            "trend_exit_reasons": args.trend_exit_reasons_output,
            "report": args.report,
            "summary": args.summary_output,
        },
    }
    Path(args.summary_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary_output).write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    write_html_report(
        Path(args.report),
        fixed=fixed,
        trend=trend,
        fixed_yearly=fixed_yearly,
        trend_yearly=trend_yearly,
        trend_reasons=trend_reasons,
        config=config,
        costs=costs,
        args=args,
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest the TradingView Lightglow Pine trend-hold validation logic.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-lightglow-pine-trend-hold-bars.pkl")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--range-length", type=int, default=100)
    parser.add_argument("--premium-threshold", type=float, default=0.90)
    parser.add_argument("--discount-threshold", type=float, default=0.10)
    parser.add_argument("--direct-pd-signal", action="store_true")
    parser.add_argument("--cooldown-bars", type=int, default=10)
    parser.add_argument("--fixed-hold-bars", type=int, default=2)
    parser.add_argument("--trend-max-hold-bars", type=int, default=120)
    parser.add_argument("--initial-stop-atr", type=float, default=1.8)
    parser.add_argument("--trail-stop-atr", type=float, default=2.4)
    parser.add_argument("--breakeven-trigger-atr", type=float, default=1.2)
    parser.add_argument("--fixed-trades-output", default=".tmp/lightglow-pine-fixed-2bar-trades.csv")
    parser.add_argument("--trend-trades-output", default=".tmp/lightglow-pine-trend-hold-trades.csv")
    parser.add_argument("--fixed-yearly-output", default=".tmp/lightglow-pine-fixed-2bar-yearly.csv")
    parser.add_argument("--trend-yearly-output", default=".tmp/lightglow-pine-trend-hold-yearly.csv")
    parser.add_argument("--trend-exit-reasons-output", default=".tmp/lightglow-pine-trend-hold-exit-reasons.csv")
    parser.add_argument("--summary-output", default=".tmp/lightglow-pine-trend-hold-summary.json")
    parser.add_argument("--report", default="reports/NQ-lightglow-pine-trend-hold-validation.html")
    args = parser.parse_args()
    summary = run(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
