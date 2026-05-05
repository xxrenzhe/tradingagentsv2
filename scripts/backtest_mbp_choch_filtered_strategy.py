from __future__ import annotations

import argparse
import html
import sys
from dataclasses import dataclass
from math import sqrt
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_mbp_history_report import _load_features, _svg_line_chart
from mine_mbp_advanced_patterns import AdvancedStrategySpec, build_advanced_trades, summarize_advanced_trades
from tradingagents.backtesting.short_patterns import BacktestCosts


BEST_STRATEGY_NAME = "adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3"


@dataclass(frozen=True)
class ChochConfig:
    name: str
    session: str
    trend_mode: str
    volatility_mode: str
    swing_left: int = 3
    swing_right: int = 2
    stop_loss_points: float = 16.0
    reward_risk: float = 1.5
    max_hold_minutes: int = 10
    min_hold_minutes: int = 1
    imbalance_threshold: float = 0.2
    max_spread_quantile: float = 0.75
    min_depth_quantile: float = 0.25
    max_extension_atr: float = 0.45
    max_extension_points: float = 12.0
    max_impulse_atr: float = 1.8
    bos_cooldown_bars: int = 8

    @property
    def take_profit_points(self) -> float:
        return self.stop_loss_points * self.reward_risk


def _best_strategy_spec() -> AdvancedStrategySpec:
    return AdvancedStrategySpec(
        name=BEST_STRATEGY_NAME,
        family="mean_reversion",
        lookback=6,
        threshold=0.8,
        min_hold=1,
        max_hold=6,
        exit_mode="reverse",
        session="europe",
        volatility_filter="all",
        imbalance_threshold=0.3,
        max_spread_quantile=0.75,
        min_depth_quantile=0.25,
        stop_loss_points=None,
        take_profit_points=None,
    )


def _prepare_features(features: pd.DataFrame) -> pd.DataFrame:
    data = features.copy().sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    data["ts"] = pd.to_datetime(data["ts"], utc=True)
    data["trade_date"] = data["ts"].dt.date
    data["minute_of_day"] = data["ts"].dt.hour * 60 + data["ts"].dt.minute
    has_spread = "spread_mean" in data.columns
    has_imbalance = "imbalance_mean" in data.columns or "imbalance_last" in data.columns
    has_depth = "depth_mean" in data.columns
    data["_has_spread"] = has_spread
    data["_has_imbalance"] = has_imbalance
    data["_has_depth"] = has_depth
    if "spread_mean" not in data.columns:
        data["spread_mean"] = 0.0
    if "imbalance_mean" not in data.columns:
        data["imbalance_mean"] = 0.0
    if "imbalance_last" not in data.columns:
        data["imbalance_last"] = data["imbalance_mean"]
    if "depth_mean" not in data.columns:
        data["depth_mean"] = 1.0
    for column in [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "spread_mean",
        "imbalance_mean",
        "imbalance_last",
        "depth_mean",
    ]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    previous_close = data["Close"].shift(1)
    true_range = pd.concat(
        [
            data["High"] - data["Low"],
            (data["High"] - previous_close).abs(),
            (data["Low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    data["atr_14"] = true_range.rolling(14).mean()
    data["return_1m"] = data["Close"].pct_change()
    data["realized_vol_30"] = data["return_1m"].rolling(30).std()
    data["ema_20"] = data["Close"].ewm(span=20, adjust=False).mean()
    data["ema_60"] = data["Close"].ewm(span=60, adjust=False).mean()
    data["ema_20_slope"] = data["ema_20"].diff(5)
    data["ema_60_slope"] = data["ema_60"].diff(10)
    data["bar_range"] = data["High"] - data["Low"]
    return data.dropna(subset=["Open", "High", "Low", "Close"]).reset_index(drop=True)


def _detect_structure(features: pd.DataFrame, *, left: int, right: int) -> pd.DataFrame:
    data = features.copy()
    window = left + right + 1
    pivot_high_raw = data["High"].eq(data["High"].rolling(window, center=True).max())
    pivot_low_raw = data["Low"].eq(data["Low"].rolling(window, center=True).min())
    confirmed_high = data["High"].where(pivot_high_raw).shift(right)
    confirmed_low = data["Low"].where(pivot_low_raw).shift(right)
    data["last_swing_high"] = confirmed_high.ffill()
    data["last_swing_low"] = confirmed_low.ffill()

    structure_dir = []
    break_type = []
    broken_level = []
    last_bos_dir = 0
    bars_since_bos = 10_000
    trend_state = 0
    prev_close = float("nan")
    prev_high_level = float("nan")
    prev_low_level = float("nan")

    for row in data.itertuples():
        close = float(row.Close)
        high_level = row.last_swing_high
        low_level = row.last_swing_low
        signal_dir = 0
        label = "none"
        level = float("nan")
        broke_high = (
            pd.notna(high_level)
            and pd.notna(prev_close)
            and pd.notna(prev_high_level)
            and prev_close <= float(high_level)
            and close > float(high_level)
        )
        broke_low = (
            pd.notna(low_level)
            and pd.notna(prev_close)
            and pd.notna(prev_low_level)
            and prev_close >= float(low_level)
            and close < float(low_level)
        )
        if broke_high and broke_low:
            broke_high = broke_low = False

        if broke_high:
            signal_dir = 1
            label = "choch" if trend_state <= 0 else "bos"
            level = float(high_level)
            trend_state = 1
        elif broke_low:
            signal_dir = -1
            label = "choch" if trend_state >= 0 else "bos"
            level = float(low_level)
            trend_state = -1

        if label == "bos":
            last_bos_dir = signal_dir
            bars_since_bos = 0
        else:
            bars_since_bos += 1

        structure_dir.append(signal_dir)
        break_type.append(label)
        broken_level.append(level)
        data.at[row.Index, "last_bos_dir"] = last_bos_dir
        data.at[row.Index, "bars_since_bos"] = bars_since_bos
        prev_close = close
        prev_high_level = float(high_level) if pd.notna(high_level) else prev_high_level
        prev_low_level = float(low_level) if pd.notna(low_level) else prev_low_level

    data["structure_dir"] = structure_dir
    data["break_type"] = break_type
    data["broken_level"] = broken_level
    return data


def _session_mask(features: pd.DataFrame, session: str) -> pd.Series:
    minute = features["minute_of_day"]
    if session == "all":
        return pd.Series(True, index=features.index)
    if session == "europe":
        return (minute >= 7 * 60) & (minute < 13 * 60 + 30)
    if session == "us_rth":
        return (minute >= 13 * 60 + 30) & (minute < 20 * 60)
    raise ValueError(f"Unknown session: {session}")


def _trend_mask(features: pd.DataFrame, direction: pd.Series, mode: str) -> pd.Series:
    if mode == "reversal":
        return ((direction > 0) & (features["ema_20"] <= features["ema_60"])) | (
            (direction < 0) & (features["ema_20"] >= features["ema_60"])
        )
    if mode == "confirmed":
        return (
            (direction > 0)
            & (features["Close"] >= features["ema_20"])
            & (features["ema_20_slope"] > 0)
        ) | (
            (direction < 0)
            & (features["Close"] <= features["ema_20"])
            & (features["ema_20_slope"] < 0)
        )
    if mode == "hybrid":
        return (
            (direction > 0)
            & (features["ema_20"] <= features["ema_60"])
            & (features["Close"] >= features["ema_20"])
        ) | (
            (direction < 0)
            & (features["ema_20"] >= features["ema_60"])
            & (features["Close"] <= features["ema_20"])
        )
    raise ValueError(f"Unknown trend mode: {mode}")


def _volatility_mask(features: pd.DataFrame, mode: str) -> pd.Series:
    vol = pd.to_numeric(features["realized_vol_30"], errors="coerce")
    if mode == "not_low":
        return vol >= vol.quantile(0.33)
    if mode == "balanced":
        return (vol >= vol.quantile(0.25)) & (vol <= vol.quantile(0.90))
    if mode == "not_extreme":
        return vol <= vol.quantile(0.90)
    raise ValueError(f"Unknown volatility mode: {mode}")


def _choch_signal(features: pd.DataFrame, config: ChochConfig) -> pd.Series:
    direction = features["structure_dir"].astype(int)
    base = (features["break_type"].eq("choch")) & direction.ne(0)
    session_ok = _session_mask(features, config.session)
    trend_ok = _trend_mask(features, direction, config.trend_mode)
    volatility_ok = _volatility_mask(features, config.volatility_mode)

    imbalance = pd.to_numeric(features["imbalance_last"].fillna(features["imbalance_mean"]), errors="coerce")
    if bool(features.get("_has_imbalance", pd.Series(False, index=features.index)).any()):
        imbalance_ok = ((direction > 0) & (imbalance >= config.imbalance_threshold)) | (
            (direction < 0) & (imbalance <= -config.imbalance_threshold)
        )
    else:
        imbalance_ok = pd.Series(True, index=features.index)

    spread = pd.to_numeric(features["spread_mean"], errors="coerce")
    if bool(features.get("_has_spread", pd.Series(False, index=features.index)).any()):
        spread_ok = spread <= spread.quantile(config.max_spread_quantile)
    else:
        spread_ok = pd.Series(True, index=features.index)

    depth = pd.to_numeric(features["depth_mean"], errors="coerce")
    if bool(features.get("_has_depth", pd.Series(False, index=features.index)).any()):
        depth_ok = depth >= depth.quantile(config.min_depth_quantile)
    else:
        depth_ok = pd.Series(True, index=features.index)

    extension = (features["Close"] - features["broken_level"]).abs()
    atr = pd.to_numeric(features["atr_14"], errors="coerce")
    extension_ok = (extension <= config.max_extension_points) & (extension <= atr * config.max_extension_atr)
    impulse_ok = features["bar_range"] <= atr * config.max_impulse_atr
    no_recent_same_bos = ~(
        (features["last_bos_dir"].astype(int) == direction)
        & (features["bars_since_bos"].astype(float) <= config.bos_cooldown_bars)
    )

    signal = direction.where(
        base
        & session_ok
        & trend_ok
        & volatility_ok
        & imbalance_ok
        & spread_ok
        & depth_ok
        & extension_ok
        & impulse_ok
        & no_recent_same_bos,
        0,
    )
    return signal.fillna(0).astype(int)


def build_choch_trades(features: pd.DataFrame, config: ChochConfig, costs: BacktestCosts | None = None) -> pd.DataFrame:
    costs = costs or BacktestCosts()
    data = _detect_structure(features, left=config.swing_left, right=config.swing_right)
    signal = _choch_signal(data, config)
    signal = signal.where(signal != signal.shift(1), 0)

    rows = []
    next_available_index = 0
    for entry_index in signal.index[signal.ne(0)]:
        if entry_index < next_available_index or entry_index + 1 >= len(data):
            continue
        direction = int(signal.at[entry_index])
        entry_price = float(data.at[entry_index + 1, "Open"])
        stop_price = entry_price - config.stop_loss_points if direction > 0 else entry_price + config.stop_loss_points
        target_price = entry_price + config.take_profit_points if direction > 0 else entry_price - config.take_profit_points
        max_exit_index = min(entry_index + config.max_hold_minutes, len(data) - 1)
        exit_index = max_exit_index
        exit_price = float(data.at[exit_index, "Close"])
        exit_reason = "time"

        for path_index in range(entry_index + 1, max_exit_index + 1):
            high = float(data.at[path_index, "High"])
            low = float(data.at[path_index, "Low"])
            if direction > 0:
                stop_hit = low <= stop_price
                target_hit = high >= target_price
            else:
                stop_hit = high >= stop_price
                target_hit = low <= target_price
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
            if path_index - entry_index >= config.min_hold_minutes:
                opposite_choch = data.at[path_index, "break_type"] == "choch" and int(data.at[path_index, "structure_dir"]) == -direction
                if opposite_choch:
                    exit_index = path_index
                    exit_price = float(data.at[path_index, "Close"])
                    exit_reason = "opposite_choch"
                    break

        gross_points = (exit_price - entry_price) * direction
        rows.append(
            {
                "strategy": config.name,
                "entry_ts": data.at[entry_index, "ts"],
                "exit_ts": data.at[exit_index, "ts"],
                "trade_date": data.at[entry_index, "trade_date"],
                "direction": direction,
                "entry_price": entry_price,
                "exit_price": float(exit_price),
                "gross_points": float(gross_points),
                "net_points": float(gross_points - costs.round_trip_cost_points),
                "net_dollars": float((gross_points - costs.round_trip_cost_points) * costs.point_value),
                "exit_reason": exit_reason,
                "entry_index": int(entry_index),
                "exit_index": int(exit_index),
                "holding_minutes": int(exit_index - entry_index),
                "broken_level": float(data.at[entry_index, "broken_level"]),
                "atr_14": float(data.at[entry_index, "atr_14"]),
                "extension_points": float(abs(data.at[entry_index, "Close"] - data.at[entry_index, "broken_level"])),
                "imbalance": float(data.at[entry_index, "imbalance_last"]),
                "trend_mode": config.trend_mode,
                "volatility_mode": config.volatility_mode,
                "session": config.session,
                "stop_loss_points": config.stop_loss_points,
                "take_profit_points": config.take_profit_points,
            }
        )
        next_available_index = exit_index + 1
    return pd.DataFrame(rows)


def _max_drawdown(net: pd.Series) -> float:
    if net.empty:
        return 0.0
    equity = net.cumsum()
    return float((equity.cummax() - equity).max())


def _profit_factor(net: pd.Series) -> float:
    wins = float(net[net > 0].sum())
    losses = abs(float(net[net < 0].sum()))
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return wins / losses


def _fold_metrics(trades: pd.DataFrame, fold_count: int = 6) -> dict[str, float | int]:
    if trades.empty:
        return {"positive_fold_rate": 0.0, "min_fold_net_points": 0.0, "fold_count": 0}
    dates = pd.Series(sorted(pd.to_datetime(trades["entry_ts"], utc=True).dt.date.unique()))
    fold_count = max(1, min(fold_count, len(dates)))
    fold_ids = pd.qcut(pd.RangeIndex(len(dates)), q=fold_count, labels=False, duplicates="drop")
    nets = []
    for fold_id in sorted(set(fold_ids)):
        fold_dates = set(dates[fold_ids == fold_id])
        nets.append(float(trades.loc[pd.to_datetime(trades["entry_ts"], utc=True).dt.date.isin(fold_dates), "net_points"].sum()))
    return {
        "positive_fold_rate": sum(value > 0 for value in nets) / len(nets),
        "min_fold_net_points": min(nets),
        "fold_count": len(nets),
    }


def _rolling_window_metrics(trades: pd.DataFrame, window_days: int = 10) -> dict[str, float | int]:
    if trades.empty:
        return {"positive_window_rate": 0.0, "min_window_net_points": 0.0, "window_count": 0}
    daily = trades.groupby(pd.to_datetime(trades["entry_ts"], utc=True).dt.date)["net_points"].sum().sort_index()
    daily.index = pd.to_datetime(daily.index)
    full_index = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(full_index, fill_value=0.0)
    windows = daily.rolling(window_days).sum().dropna()
    if windows.empty:
        windows = pd.Series([float(daily.sum())])
    return {
        "positive_window_rate": float((windows > 0).mean()),
        "min_window_net_points": float(windows.min()),
        "window_count": int(len(windows)),
    }


def summarize_trades(name: str, trades: pd.DataFrame) -> dict[str, float | int | str]:
    if trades.empty:
        return {
            "name": name,
            "trades": 0,
            "net_points": 0.0,
            "max_drawdown_points": 0.0,
            "net_to_drawdown": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_points": 0.0,
            "worst_trade_points": 0.0,
            "avg_holding_minutes": 0.0,
            "positive_fold_rate": 0.0,
            "positive_window_rate": 0.0,
            "min_window_net_points": 0.0,
            "score": 0.0,
        }
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    net_points = float(net.sum())
    max_drawdown = _max_drawdown(net)
    folds = _fold_metrics(trades)
    windows = _rolling_window_metrics(trades)
    score = (
        net_points
        - max_drawdown * 1.5
        + min(_profit_factor(net), 3.0) * 250
        + folds["positive_fold_rate"] * 350
        + windows["positive_window_rate"] * 450
        + min(float(windows["min_window_net_points"]), 500.0) * 0.25
    )
    return {
        "name": name,
        "trades": int(len(trades)),
        "net_points": net_points,
        "max_drawdown_points": max_drawdown,
        "net_to_drawdown": net_points / max(max_drawdown, 1.0),
        "profit_factor": _profit_factor(net),
        "win_rate": float((net > 0).mean()),
        "avg_points": float(net.mean()),
        "worst_trade_points": float(net.min()),
        "avg_holding_minutes": float(pd.to_numeric(trades["holding_minutes"], errors="coerce").mean()),
        "positive_fold_rate": float(folds["positive_fold_rate"]),
        "positive_window_rate": float(windows["positive_window_rate"]),
        "min_window_net_points": float(windows["min_window_net_points"]),
        "score": float(score),
    }


def _candidate_configs() -> list[ChochConfig]:
    configs = []
    for session in ["europe", "all"]:
        for trend_mode in ["reversal", "hybrid", "confirmed"]:
            for volatility_mode in ["balanced", "not_low"]:
                for stop_loss, reward_risk, max_hold in [(12.0, 1.5, 8), (16.0, 1.5, 10), (16.0, 2.0, 12)]:
                    name = (
                        f"choch_{trend_mode}_{volatility_mode}_{session}"
                        f"_sl{stop_loss:g}_rr{reward_risk:g}_max{max_hold}_no_bos_chase"
                    )
                    configs.append(
                        ChochConfig(
                            name=name,
                            session=session,
                            trend_mode=trend_mode,
                            volatility_mode=volatility_mode,
                            stop_loss_points=stop_loss,
                            reward_risk=reward_risk,
                            max_hold_minutes=max_hold,
                        )
                    )
    return configs


def _equity_points(trades: pd.DataFrame, start_ts: pd.Timestamp) -> list[tuple[pd.Timestamp, float]]:
    if trades.empty:
        return [(start_ts, 0.0)]
    equity = trades["net_points"].cumsum().round(4)
    timestamps = pd.to_datetime(trades["entry_ts"], utc=True)
    return [(start_ts, 0.0), *zip(timestamps, equity)]


def _summary_table(rows: pd.DataFrame) -> str:
    columns = [
        "name",
        "trades",
        "net_points",
        "max_drawdown_points",
        "net_to_drawdown",
        "profit_factor",
        "win_rate",
        "positive_fold_rate",
        "positive_window_rate",
        "min_window_net_points",
        "score",
    ]
    display = rows[columns].copy()
    for column in ["win_rate", "positive_fold_rate", "positive_window_rate"]:
        display[column] = display[column].map(lambda value: f"{float(value):.2%}")
    for column in ["net_points", "max_drawdown_points", "net_to_drawdown", "profit_factor", "min_window_net_points", "score"]:
        display[column] = display[column].map(lambda value: f"{float(value):,.4f}")
    display.columns = [
        "Strategy",
        "Trades",
        "Net Points",
        "Max DD",
        "Net/DD",
        "PF",
        "Win Rate",
        "Positive Folds",
        "Positive Windows",
        "Worst 10D",
        "Score",
    ]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def _write_report(
    *,
    output: Path,
    features: pd.DataFrame,
    summary: pd.DataFrame,
    curves: dict[str, list[tuple[pd.Timestamp, float]]],
    best_choch: pd.Series,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    has_microstructure = bool(
        features.get("_has_spread", pd.Series(False, index=features.index)).any()
        and features.get("_has_imbalance", pd.Series(False, index=features.index)).any()
        and features.get("_has_depth", pd.Series(False, index=features.index)).any()
    )
    microstructure_note = (
        "本次缓存包含 spread / imbalance / depth，盘口过滤已启用。"
        if has_microstructure
        else "本次缓存缺少 spread / imbalance / depth，盘口过滤已自动旁路；结果代表 bar-only 两个月回测，不等同于完整 MBP 盘口过滤效果。"
    )
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>NQM6 CHoCH Filtered Strategy Backtest</title>
  <style>
    body {{ margin: 0; padding: 28px; background: #0b1110; color: #eef7f2; font: 15px/1.58 "Avenir Next", "Trebuchet MS", sans-serif; }}
    .wrap {{ max-width: 1240px; margin: 0 auto; }}
    .card {{ background: rgba(17, 28, 25, .9); border: 1px solid #29433b; border-radius: 20px; padding: 20px; margin-bottom: 18px; box-shadow: 0 18px 50px rgba(0,0,0,.25); overflow-x: auto; }}
    h1 {{ margin: 0 0 10px; font-size: clamp(30px, 5vw, 54px); line-height: 1; letter-spacing: -1.5px; }}
    h2 {{ margin: 0 0 12px; }}
    p {{ color: #a9bdb6; }}
    code {{ color: #f5c76b; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid #29433b; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; max-width: 440px; overflow-wrap: anywhere; }}
    th {{ color: #d6eee5; background: rgba(41,67,59,.45); font-size: 11px; text-transform: uppercase; }}
    .kpi {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .kpi div {{ border: 1px solid #29433b; border-radius: 16px; padding: 14px; background: rgba(10,20,17,.6); }}
    .kpi strong {{ display: block; font-size: 24px; color: #f5c76b; }}
    svg {{ width: 100%; height: auto; border-radius: 14px; overflow: hidden; }}
    .legend-bar {{ display: flex; flex-wrap: wrap; align-content: flex-start; align-items: center; gap: 8px; height: 106px; overflow-y: auto; padding: 2px 0 8px; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 6px; border: 1px solid #34445f; border-radius: 999px; background: rgba(8, 17, 31, .72); color: #d7e1ea; padding: 5px 9px; font: 11px/1.2 "Avenir Next", sans-serif; }}
    .legend-swatch {{ width: 10px; height: 10px; border-radius: 999px; }}
    .chart-tooltip {{ display: none; }}
  </style>
</head>
<body>
<main class="wrap">
  <section class="card">
    <h1>CHoCH + 过滤版两个月回测</h1>
    <p>数据范围：<code>{features['ts'].min()}</code> 至 <code>{features['ts'].max()}</code>；样本共 {len(features):,} 行。新策略只允许 CHoCH 入场，显式禁止顺趋势 BOS 追高，并加入趋势、波动、固定止损/止盈过滤。{html.escape(microstructure_note)}</p>
  </section>
  <section class="card">
    <h2>最佳 CHoCH 版本</h2>
    <div class="kpi">
      <div><strong>{int(best_choch['trades'])}</strong><span>Trades</span></div>
      <div><strong>{float(best_choch['net_points']):,.2f}</strong><span>Net Points</span></div>
      <div><strong>{float(best_choch['max_drawdown_points']):,.2f}</strong><span>Max DD</span></div>
      <div><strong>{float(best_choch['profit_factor']):.3f}</strong><span>Profit Factor</span></div>
    </div>
    <p>最佳 CHoCH 版本：<code>{html.escape(str(best_choch['name']))}</code>。</p>
  </section>
  <section class="card">
    <h2>策略对比</h2>
    {_summary_table(summary.head(16))}
  </section>
  <section class="card">
    <h2>资金曲线</h2>
    {_svg_line_chart(curves, "Current best vs CHoCH filtered variants", "date")}
  </section>
  <section class="card">
    <h2>规则定义</h2>
    <p>CHoCH 定义：价格收盘突破已确认的相反方向 swing high/low，且结构状态发生反转；同方向突破只标记为 BOS，不作为入场。</p>
    <p>禁止追高 BOS：不允许顺趋势 BOS 入场；CHoCH 突破后的扩展距离必须同时小于固定点数阈值和 ATR 阈值，且信号 K 线不能是过大 impulse bar。</p>
    <p>固定风险：所有 CHoCH 候选均使用固定 stop loss 和 reward/risk take profit，并保留最长持仓时间和反向 CHoCH 提前退出。</p>
  </section>
</main>
</body>
</html>
"""
    output.write_text(html_doc, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest CHoCH filtered MBP strategy variants.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--summary-output", default=".tmp/mbp-choch-filtered-summary.csv")
    parser.add_argument("--trades-output", default=".tmp/mbp-choch-filtered-trades.csv")
    parser.add_argument("--report", default="reports/NQM6-mbp-choch-filtered-backtest.html")
    args = parser.parse_args()

    features = _prepare_features(_load_features(Path(args.features_cache)))
    costs = BacktestCosts()

    best_spec = _best_strategy_spec()
    best_trades = build_advanced_trades(features, best_spec, costs)
    best_trades = best_trades.copy()
    best_trades["strategy"] = BEST_STRATEGY_NAME
    summaries = [summarize_trades(BEST_STRATEGY_NAME, best_trades)]
    all_trades = [best_trades]

    for config in _candidate_configs():
        trades = build_choch_trades(features, config, costs)
        summaries.append(summarize_trades(config.name, trades))
        if not trades.empty:
            all_trades.append(trades)

    summary = pd.DataFrame(summaries).sort_values(
        ["score", "net_points", "profit_factor", "max_drawdown_points"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)

    trades_output = pd.concat(all_trades, ignore_index=True, sort=False) if all_trades else pd.DataFrame()
    trades_path = Path(args.trades_output)
    trades_path.parent.mkdir(parents=True, exist_ok=True)
    trades_output.to_csv(trades_path, index=False)

    top_choch = summary[summary["name"].astype(str).str.startswith("choch_")].head(3)
    selected = pd.concat([summary[summary["name"].eq(BEST_STRATEGY_NAME)].head(1), top_choch], ignore_index=True)
    curves = {}
    for name in selected["name"]:
        frame = trades_output[trades_output["strategy"].astype(str).eq(str(name))].copy()
        curves[str(name)] = _equity_points(frame, features["ts"].min())

    best_choch = top_choch.iloc[0] if not top_choch.empty else summary.iloc[0]
    _write_report(
        output=Path(args.report),
        features=features,
        summary=summary,
        curves=curves,
        best_choch=best_choch,
    )

    print(f"Features: {len(features):,} {features['ts'].min()} -> {features['ts'].max()}")
    print(f"Summary: {summary_path}")
    print(f"Trades: {trades_path}")
    print(f"Report: {args.report}")
    print(summary.head(12).to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
