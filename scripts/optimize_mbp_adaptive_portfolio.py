from __future__ import annotations

import argparse
import html
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from generate_mbp_history_report import _equity_curve_summary, _load_features, _svg_line_chart
from generate_mbp_live_ready_report import _advanced_spec_from_row
from mine_mbp_advanced_patterns import AdvancedStrategySpec, build_advanced_trades
from optimize_mbp_robust_top10 import Candidate, _fold_metrics, _window_metrics
from tradingagents.backtesting.short_patterns import BacktestCosts


SEED_NAMES = [
    "adv_top8_enhanced_mean_reversion_lb9_thr0.6_min1_max5_reverse_all_high_imb0.35",
    "adv_refined_mean_reversion_lb7_thr0.65_min1_max6_reverse_europe_not_low_imb0.3",
    "adv_top6_enhanced_vwap_reclaim_lb10_thr0.0002_min1_max10_time_all_not_low_imb0.35",
]

OPTIMIZED_NAMES = [
    "adv_stable_stable_yield_mean_reversion_lb6_thr0.6_min1_max4_reverse_all_high_imb0.35",
    "adv_stable_refined_defensive_mean_reversion_lb5_thr0.75_min1_max6_reverse_europe_not_low_imb0.3",
    "adv_stable_vwap_aggressive_vwap_reclaim_lb8_thr0.0002_min1_max13_time_all_not_low_imb0.35",
]


@dataclass(frozen=True)
class PortfolioRule:
    name: str
    risk_first: str
    trend_high: str
    mean_high: str
    fallback: str
    use_us_rth_trend: bool
    use_europe_defensive: bool
    min_gap_minutes: int
    max_trades_per_day: int | None


def _fmt(value: float, decimals: int = 4) -> str:
    return f"{value:,.{decimals}f}"


def _load_strategy_rows(paths: list[Path], names: list[str]) -> pd.DataFrame:
    frames = []
    for path in paths:
        if path.exists():
            frame = pd.read_csv(path)
            if not frame.empty:
                frames.append(frame)
    if not frames:
        raise SystemExit("No strategy result files found.")
    all_rows = pd.concat(frames, ignore_index=True, sort=False)
    rows = []
    for name in names:
        match = all_rows[all_rows["name"].eq(name)]
        if match.empty:
            raise SystemExit(f"Missing strategy row: {name}")
        rows.append(match.iloc[0])
    return pd.DataFrame(rows).reset_index(drop=True)


def _strategy_alias(name: str) -> str:
    if "vwap" in name and "vwap_reclaim" in name:
        return "trend_vwap"
    if "refined_defensive" in name or "adv_refined" in name:
        return "defensive_mr"
    if "stable_yield" in name or "top8_enhanced" in name:
        return "stable_mr"
    return name


def _build_strategy_trades(features: pd.DataFrame, rows: pd.DataFrame) -> dict[str, pd.DataFrame]:
    trades_by_alias = {}
    for _, row in rows.iterrows():
        spec = _advanced_spec_from_row(row)
        if spec is None:
            raise SystemExit(f"Cannot build spec: {row['name']}")
        trades = build_advanced_trades(features, spec)
        if trades.empty:
            raise SystemExit(f"No trades for strategy: {row['name']}")
        alias = _strategy_alias(str(row["name"]))
        enriched = trades.copy()
        enriched["strategy_alias"] = alias
        enriched["strategy_name"] = row["name"]
        enriched["actual_entry_index"] = (enriched["entry_index"].astype(int) + 1).clip(upper=len(features) - 1)
        enriched["actual_entry_ts"] = enriched["actual_entry_index"].map(features["ts"])
        enriched["trade_date"] = pd.to_datetime(enriched["actual_entry_ts"], utc=True).dt.date
        trades_by_alias[alias] = enriched
    return trades_by_alias


def _attach_regime(features: pd.DataFrame) -> pd.DataFrame:
    data = features.copy().reset_index(drop=True)
    data["ts"] = pd.to_datetime(data["ts"], utc=True)
    data["return_1m"] = pd.to_numeric(data["Close"], errors="coerce").pct_change()
    data["realized_vol_30"] = data["return_1m"].rolling(30).std()
    data["vol_low_cutoff"] = data["realized_vol_30"].quantile(0.33)
    data["vol_high_cutoff"] = data["realized_vol_30"].quantile(0.67)
    data["vol_bucket"] = "mid"
    data.loc[data["realized_vol_30"] <= data["vol_low_cutoff"], "vol_bucket"] = "low"
    data.loc[data["realized_vol_30"] >= data["vol_high_cutoff"], "vol_bucket"] = "high"
    minute = data["minute_of_day"]
    data["session_bucket"] = "other"
    data.loc[(minute >= 7 * 60) & (minute < 13 * 60 + 30), "session_bucket"] = "europe"
    data.loc[(minute >= 13 * 60 + 30) & (minute < 20 * 60), "session_bucket"] = "us_rth"
    data.loc[(minute >= 20 * 60) | (minute < 7 * 60), "session_bucket"] = "asia_late"
    data["vwap_distance"] = (pd.to_numeric(data["Close"], errors="coerce") - pd.to_numeric(data["vwap"], errors="coerce")) / pd.to_numeric(
        data["vwap"], errors="coerce"
    )
    return data


def _eligible_aliases(row: pd.Series, rule: PortfolioRule) -> list[str]:
    session = row["session_bucket"]
    vol = row["vol_bucket"]
    aliases = []
    if rule.use_europe_defensive and session == "europe" and vol != "low":
        aliases.append(rule.risk_first)
    if rule.use_us_rth_trend and session == "us_rth" and vol == "high":
        aliases.append(rule.trend_high)
    if vol == "high":
        aliases.append(rule.mean_high)
    if vol != "low":
        aliases.append(rule.fallback)
    deduped = []
    for alias in aliases:
        if alias not in deduped:
            deduped.append(alias)
    return deduped


def _build_portfolio_trades(
    features: pd.DataFrame,
    trades_by_alias: dict[str, pd.DataFrame],
    rule: PortfolioRule,
    costs: BacktestCosts,
    entry_lookup: dict[int, dict[str, pd.Series]] | None = None,
) -> pd.DataFrame:
    if entry_lookup is None:
        entry_lookup = {}
        for alias, trades in trades_by_alias.items():
            for _, trade in trades.iterrows():
                entry_lookup.setdefault(int(trade["entry_index"]), {})[alias] = trade

    rows = []
    next_available_index = 0
    daily_counts: dict[object, int] = {}
    for entry_index in sorted(entry_lookup):
        if entry_index < next_available_index:
            continue
        regime = features.iloc[entry_index]
        trade_date = regime["ts"].date()
        if rule.max_trades_per_day is not None and daily_counts.get(trade_date, 0) >= rule.max_trades_per_day:
            continue
        selected_trade = None
        selected_alias = None
        available = entry_lookup[entry_index]
        for alias in _eligible_aliases(regime, rule):
            if alias in available:
                selected_trade = available[alias].copy()
                selected_alias = alias
                break
        if selected_trade is None:
            continue
        adjusted = selected_trade.copy()
        cost_delta = costs.round_trip_cost_points - BacktestCosts().round_trip_cost_points
        adjusted["net_points"] = float(adjusted["gross_points"]) - costs.round_trip_cost_points
        adjusted["net_dollars"] = float(adjusted["net_points"]) * costs.point_value
        adjusted["cost_delta_points"] = cost_delta
        adjusted["selected_alias"] = selected_alias
        adjusted["portfolio_rule"] = rule.name
        adjusted["session_bucket"] = regime["session_bucket"]
        adjusted["vol_bucket"] = regime["vol_bucket"]
        adjusted["realized_vol_30"] = regime["realized_vol_30"]
        adjusted["vwap_distance"] = regime["vwap_distance"]
        rows.append(adjusted)
        daily_counts[trade_date] = daily_counts.get(trade_date, 0) + 1
        next_available_index = int(adjusted["exit_index"]) + max(1, rule.min_gap_minutes)
    if not rows:
        return pd.DataFrame()
    portfolio = pd.DataFrame(rows).reset_index(drop=True)
    portfolio["cumulative_net_points"] = portfolio["net_points"].cumsum()
    return portfolio


def _summarize_trades(name: str, trades: pd.DataFrame, costs: BacktestCosts) -> dict:
    if trades.empty:
        return {
            "name": name,
            "trades": 0,
            "net_points": 0.0,
            "net_dollars": 0.0,
            "max_drawdown_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "stability": 0.0,
            "score": 0.0,
        }
    net = pd.to_numeric(trades["net_points"], errors="coerce")
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    wins = net[net > 0].sum()
    losses = abs(net[net < 0].sum())
    split_index = int(trades["entry_index"].median())
    first = float(net[trades["entry_index"] <= split_index].sum())
    second = float(net[trades["entry_index"] > split_index].sum())
    if first > 0 and second > 0:
        stability = min(first, second) / max(first, second)
    elif first + second > 0:
        stability = 0.25
    else:
        stability = 0.0
    max_dd = float(abs(drawdown.min()))
    tail_loss = abs(float(net.quantile(0.05)))
    risk = max(max_dd, tail_loss, 1.0)
    score = float((equity.iloc[-1] / risk) * (0.75 + 0.25 * stability))
    return {
        "name": name,
        "trades": int(len(trades)),
        "net_points": float(equity.iloc[-1]),
        "net_dollars": float(equity.iloc[-1] * costs.point_value),
        "max_drawdown_points": max_dd,
        "profit_factor": float(wins / losses) if losses else float("inf"),
        "win_rate": float((net > 0).mean()),
        "stability": float(stability),
        "first_half_points": first,
        "second_half_points": second,
        "tail_loss_p05": float(net.quantile(0.05)),
        "worst_trade_points": float(net.min()),
        "score": score,
    }


def _candidate_from_portfolio(name: str, trades_by_cost: dict[str, pd.DataFrame]) -> Candidate:
    return Candidate("portfolio", name, PortfolioBacktestSpec(name, trades_by_cost))


@dataclass(frozen=True)
class PortfolioBacktestSpec:
    name: str
    trades_by_cost: dict[str, pd.DataFrame]
    family: str = "adaptive_portfolio"
    lookback: int = 0
    threshold: float = 0.0
    imbalance_threshold: float | None = None
    max_spread_quantile: float | None = None
    min_depth_quantile: float | None = None
    holding_minutes: int = 0


def _portfolio_fold_metrics(trades: pd.DataFrame, features: pd.DataFrame, fold_count: int, costs: BacktestCosts) -> dict:
    dates = pd.Series(sorted(features["ts"].dt.date.unique()))
    fold_count = max(1, min(fold_count, len(dates)))
    fold_ids = pd.qcut(pd.RangeIndex(len(dates)), q=fold_count, labels=False, duplicates="drop")
    nets = []
    drawdowns = []
    scores = []
    positives = 0
    for fold_id in sorted(set(fold_ids)):
        fold_dates = set(dates[fold_ids == fold_id])
        fold_trades = trades[trades["trade_date"].isin(fold_dates)].reset_index(drop=True)
        summary = _summarize_trades("fold", fold_trades, costs)
        nets.append(summary["net_points"])
        drawdowns.append(summary["max_drawdown_points"])
        scores.append(summary["score"])
        positives += int(summary["net_points"] > 0)
    return {
        "fold_count": len(nets),
        "positive_fold_count": positives,
        "positive_fold_rate": positives / len(nets),
        "min_fold_net_points": min(nets),
        "median_fold_net_points": float(pd.Series(nets).median()),
        "avg_fold_score": float(pd.Series(scores).mean()),
        "min_fold_score": min(scores),
        "max_fold_drawdown_points": max(drawdowns),
    }


def _portfolio_window_metrics(
    trades: pd.DataFrame,
    features: pd.DataFrame,
    costs: BacktestCosts,
    window_days: int,
    step_days: int,
) -> dict:
    if trades.empty:
        return {
            "window_count": 0,
            "positive_window_count": 0,
            "positive_window_rate": 0.0,
            "min_window_net_points": 0.0,
            "median_window_net_points": 0.0,
            "max_window_drawdown_points": 0.0,
            "min_window_score": 0.0,
            "min_window_trades": 0,
        }
    first_trade_date = min(trades["trade_date"])
    dates = [date for date in sorted(features["ts"].dt.date.unique()) if date >= first_trade_date]
    masks = []
    for start in range(0, len(dates) - window_days + 1, step_days):
        masks.append(set(dates[start : start + window_days]))
    if not masks:
        masks = [set(dates)]
    nets = []
    drawdowns = []
    scores = []
    trade_counts = []
    for window_dates in masks:
        window_trades = trades[trades["trade_date"].isin(window_dates)].reset_index(drop=True)
        summary = _summarize_trades("window", window_trades, costs)
        nets.append(summary["net_points"])
        drawdowns.append(summary["max_drawdown_points"])
        scores.append(summary["score"])
        trade_counts.append(summary["trades"])
    positive = sum(value > 0 for value in nets)
    return {
        "window_count": len(nets),
        "positive_window_count": positive,
        "positive_window_rate": positive / len(nets),
        "min_window_net_points": min(nets),
        "median_window_net_points": float(pd.Series(nets).median()),
        "max_window_drawdown_points": max(drawdowns),
        "min_window_score": min(scores),
        "min_window_trades": min(trade_counts),
    }


def _rule_grid() -> list[PortfolioRule]:
    templates = [
        ("defensive_mr", "trend_vwap", "stable_mr", "defensive_mr", True, True),
        ("defensive_mr", "trend_vwap", "stable_mr", "stable_mr", True, True),
        ("defensive_mr", "stable_mr", "stable_mr", "defensive_mr", False, True),
        ("stable_mr", "trend_vwap", "stable_mr", "defensive_mr", True, True),
        ("stable_mr", "trend_vwap", "defensive_mr", "stable_mr", True, False),
        ("defensive_mr", "trend_vwap", "defensive_mr", "stable_mr", True, True),
    ]
    rules = []
    for risk_first, trend_high, mean_high, fallback, use_us_rth_trend, use_europe_defensive in templates:
        for min_gap_minutes in [1, 3]:
            for max_trades_per_day in [None, 24]:
                name = (
                    f"adaptive_{risk_first}_trend{trend_high}_mean{mean_high}_fallback{fallback}"
                    f"_us{int(use_us_rth_trend)}_eu{int(use_europe_defensive)}"
                    f"_gap{min_gap_minutes}_cap{max_trades_per_day or 0}"
                )
                rules.append(
                    PortfolioRule(
                        name,
                        risk_first,
                        trend_high,
                        mean_high,
                        fallback,
                        use_us_rth_trend,
                        use_europe_defensive,
                        min_gap_minutes,
                        max_trades_per_day,
                    )
                )
    return rules


def optimize_portfolios(
    features: pd.DataFrame,
    trades_by_alias: dict[str, pd.DataFrame],
    fold_count: int,
    window_days: int,
    window_step_days: int,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    rows = []
    trades_by_rule = {}
    base_costs = BacktestCosts()
    stress_costs = BacktestCosts(slippage_ticks_per_side=3.0)
    entry_lookup: dict[int, dict[str, pd.Series]] = {}
    for alias, trades in trades_by_alias.items():
        for _, trade in trades.iterrows():
            entry_lookup.setdefault(int(trade["entry_index"]), {})[alias] = trade
    for rule in _rule_grid():
        trades = _build_portfolio_trades(features, trades_by_alias, rule, base_costs, entry_lookup)
        if trades.empty or len(trades) < 200:
            continue
        full = _summarize_trades(rule.name, trades, base_costs)
        stress_trades = _build_portfolio_trades(features, trades_by_alias, rule, stress_costs, entry_lookup)
        stress = _summarize_trades(rule.name, stress_trades, stress_costs)
        folds = _portfolio_fold_metrics(trades, features, fold_count, base_costs)
        windows = _portfolio_window_metrics(stress_trades, features, stress_costs, window_days, window_step_days)
        live_ready = (
            stress["net_points"] > 0
            and folds["positive_fold_rate"] >= 0.80
            and windows["positive_window_rate"] >= 0.70
            and windows["min_window_trades"] >= 5
            and full["profit_factor"] >= 1.25
        )
        score = (
            full["net_points"] * 0.22
            - full["max_drawdown_points"] * 0.95
            + full["profit_factor"] * 420
            + full["stability"] * 1600
            + folds["positive_fold_rate"] * 520
            + windows["positive_window_rate"] * 620
            + max(windows["min_window_net_points"], -500) * 0.55
            + stress["net_points"] * 0.16
        )
        alias_counts = trades["selected_alias"].value_counts(normalize=True).to_dict()
        rows.append(
            {
                "name": rule.name,
                "full_trades": full["trades"],
                "full_net_points": full["net_points"],
                "full_max_drawdown_points": full["max_drawdown_points"],
                "full_profit_factor": full["profit_factor"],
                "full_win_rate": full["win_rate"],
                "full_stability": full["stability"],
                "first_half_points": full["first_half_points"],
                "second_half_points": full["second_half_points"],
                "cost_3x_net_points": stress["net_points"],
                "cost_3x_max_drawdown_points": stress["max_drawdown_points"],
                "cost_3x_profit_factor": stress["profit_factor"],
                **folds,
                **windows,
                "stable_mr_share": alias_counts.get("stable_mr", 0.0),
                "defensive_mr_share": alias_counts.get("defensive_mr", 0.0),
                "trend_vwap_share": alias_counts.get("trend_vwap", 0.0),
                "live_ready": live_ready,
                "portfolio_score": score,
                "risk_first": rule.risk_first,
                "trend_high": rule.trend_high,
                "mean_high": rule.mean_high,
                "fallback": rule.fallback,
                "use_us_rth_trend": rule.use_us_rth_trend,
                "use_europe_defensive": rule.use_europe_defensive,
                "min_gap_minutes": rule.min_gap_minutes,
                "max_trades_per_day": rule.max_trades_per_day or 0,
            }
        )
        trades_by_rule[rule.name] = trades
    if not rows:
        return pd.DataFrame(), trades_by_rule
    ranked = pd.DataFrame(rows).sort_values(
        ["live_ready", "portfolio_score", "full_net_points", "full_max_drawdown_points"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    return ranked, trades_by_rule


def _equity_points(trades: pd.DataFrame, start_ts: pd.Timestamp) -> list[tuple[pd.Timestamp, float]]:
    equity = trades["net_points"].cumsum().round(4)
    timestamps = pd.to_datetime(trades["actual_entry_ts"], utc=True)
    return [(start_ts, 0.0), *zip(timestamps, equity)]


def _metrics_table(rows: pd.DataFrame) -> str:
    columns = [
        "name",
        "full_trades",
        "full_net_points",
        "full_max_drawdown_points",
        "full_profit_factor",
        "full_stability",
        "positive_fold_rate",
        "positive_window_rate",
        "min_window_net_points",
        "cost_3x_net_points",
        "stable_mr_share",
        "defensive_mr_share",
        "trend_vwap_share",
        "portfolio_score",
    ]
    display = rows[columns].copy()
    for column in ["positive_fold_rate", "positive_window_rate", "stable_mr_share", "defensive_mr_share", "trend_vwap_share"]:
        display[column] = display[column].map(lambda value: f"{float(value):.2%}")
    for column in [
        "full_net_points",
        "full_max_drawdown_points",
        "full_profit_factor",
        "full_stability",
        "min_window_net_points",
        "cost_3x_net_points",
        "portfolio_score",
    ]:
        display[column] = display[column].map(lambda value: _fmt(float(value)))
    display.columns = [
        "Portfolio",
        "Trades",
        "Net",
        "Max DD",
        "PF",
        "Stability",
        "Positive Folds",
        "Positive Windows",
        "Worst Window",
        "3x Cost Net",
        "Stable MR",
        "Defensive MR",
        "Trend VWAP",
        "Score",
    ]
    return display.to_html(index=False, classes="metrics", border=0, escape=True)


def _trade_table(trades: pd.DataFrame, rows: int = 40) -> str:
    display = pd.concat([trades.head(rows // 2), trades.tail(rows // 2)], ignore_index=True).drop_duplicates()
    display = display[
        [
            "actual_entry_ts",
            "exit_ts",
            "selected_alias",
            "session_bucket",
            "vol_bucket",
            "direction",
            "entry_price",
            "exit_price",
            "exit_reason",
            "net_points",
            "cumulative_net_points",
        ]
    ].copy()
    for column in ["actual_entry_ts", "exit_ts"]:
        display[column] = pd.to_datetime(display[column], utc=True).dt.strftime("%Y-%m-%d %H:%M UTC")
    for column in ["entry_price", "exit_price", "net_points", "cumulative_net_points"]:
        display[column] = display[column].map(lambda value: _fmt(float(value)))
    display.columns = ["Entry", "Exit", "Strategy", "Session", "Vol", "Dir", "Entry Px", "Exit Px", "Reason", "Net", "Cum Net"]
    return display.to_html(index=False, classes="metrics compact", border=0, escape=True)


def _trade_coverage_summary(trades: pd.DataFrame) -> str:
    daily = trades.groupby(trades["actual_entry_ts"].dt.date).size().reset_index(name="Trades")
    daily.columns = ["Trade Date", "Trades"]
    if len(daily) > 12:
        preview = pd.concat([daily.head(6), daily.tail(6)], ignore_index=True).drop_duplicates()
    else:
        preview = daily
    preview["Trade Date"] = preview["Trade Date"].astype(str)
    return preview.to_html(index=False, classes="metrics compact", border=0, escape=True)


def _write_report(
    output: Path,
    features: pd.DataFrame,
    ranked: pd.DataFrame,
    best_trades: pd.DataFrame,
    comparison_curves: dict[str, list[tuple[pd.Timestamp, float]]],
    trades_output: Path,
) -> None:
    best = ranked.iloc[0]
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NQM6 Adaptive MBP Portfolio</title>
  <style>
    body {{ margin: 0; padding: 28px; background: #07110f; color: #edf8f1; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 1240px; margin: 0 auto; }}
    .card {{ background: rgba(13, 31, 24, .94); border: 1px solid #254338; border-radius: 18px; padding: 20px; margin-bottom: 18px; box-shadow: 0 16px 50px rgba(0,0,0,.28); overflow-x: auto; }}
    h1, h2 {{ margin: 0 0 12px; }}
    p {{ color: #b2c8bd; line-height: 1.65; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #254338; text-align: left; vertical-align: top; }}
    th {{ color: #d8eadf; text-transform: uppercase; letter-spacing: .04em; font-size: 12px; }}
    svg {{ width: 100%; height: auto; border-radius: 14px; overflow: hidden; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px; }}
    .metric {{ border: 1px solid #254338; border-radius: 12px; padding: 12px; background: rgba(7, 19, 15, .46); }}
    .metric strong {{ display: block; margin-bottom: 6px; color: #f6fbf8; }}
    .metric span {{ color: #b2c8bd; line-height: 1.55; }}
    .compact {{ font-size: 12px; }}
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
      <h1>NQM6 自适应组合交易策略报告</h1>
      <p>目标：根据行情特征在均值回归防守、均值回归稳定收益和 VWAP 趋势策略之间切换，同一时刻只允许一个持仓，降低重叠风险。</p>
    </section>
    <section class="card">
      <h2>最佳组合摘要</h2>
      <div class="metric-grid">
        <div class="metric"><strong>Portfolio</strong><span>{html.escape(best['name'])}</span></div>
        <div class="metric"><strong>Net Points</strong><span>{_fmt(float(best['full_net_points']))}</span></div>
        <div class="metric"><strong>Max DD</strong><span>{_fmt(float(best['full_max_drawdown_points']))}</span></div>
        <div class="metric"><strong>PF</strong><span>{_fmt(float(best['full_profit_factor']))}</span></div>
        <div class="metric"><strong>Stability</strong><span>{_fmt(float(best['full_stability']))}</span></div>
        <div class="metric"><strong>3x Cost Net</strong><span>{_fmt(float(best['cost_3x_net_points']))}</span></div>
        <div class="metric"><strong>Worst Window</strong><span>{_fmt(float(best['min_window_net_points']))}</span></div>
        <div class="metric"><strong>Live Ready</strong><span>{bool(best['live_ready'])}</span></div>
      </div>
    </section>
    <section class="card">
      <h2>Top 10 自适应组合</h2>
      {_metrics_table(ranked.head(10))}
    </section>
    <section class="card">
      <h2>资金曲线对比</h2>
      <p>对比最佳自适应组合和参与构建的单策略。组合曲线是单持仓路由结果，不是简单等权相加。</p>
      {_svg_line_chart(comparison_curves, "Adaptive portfolio equity by trade sequence (net points)", "sequence")}
      {_svg_line_chart(comparison_curves, "Adaptive portfolio equity by trading date (net points)", "date")}
      {_equity_curve_summary(comparison_curves)}
    </section>
    <section class="card">
      <h2>路由逻辑</h2>
      <p>行情特征来自每分钟特征：交易时段分为 Europe、US RTH、Asia/Late；波动率使用 realized_vol_30 分为 low/mid/high。组合优先在 Europe 非低波动使用防守均值回归，在 US RTH 高波动时可切换 VWAP 趋势，其余非低波动环境使用稳定均值回归或 fallback。若已有持仓，新信号会被跳过。</p>
    </section>
    <section class="card">
      <h2>组合逐笔样本</h2>
      <p>下面的表是预览，不是完整逐笔明细。完整逐笔输出：<code>{html.escape(str(trades_output))}</code>。由于表格只展示前后各一段，所以中间日期会被省略；实际完整 CSV 覆盖从 {best_trades['actual_entry_ts'].dt.date.min()} 到 {best_trades['actual_entry_ts'].dt.date.max()} 共 {best_trades['actual_entry_ts'].dt.date.nunique()} 个交易日。</p>
      {_trade_table(best_trades)}
    </section>
    <section class="card">
      <h2>交易日覆盖摘要</h2>
      <p>这张表说明组合逐笔交易在各交易日上的分布，便于确认样本并非缺失，而是页面只做了前后抽样。</p>
      {_trade_coverage_summary(best_trades)}
    </section>
  </div>
  <div class="chart-tooltip" id="chart-tooltip"></div>
  <script>
    const tooltip = document.getElementById("chart-tooltip");
    function moveTooltip(event) {{
      const padding = 16;
      const rect = tooltip.getBoundingClientRect();
      let left = event.clientX + 14;
      let top = event.clientY + 14;
      if (left + rect.width + padding > window.innerWidth) left = event.clientX - rect.width - 14;
      if (top + rect.height + padding > window.innerHeight) top = event.clientY - rect.height - 14;
      tooltip.style.left = `${{Math.max(padding, left)}}px`;
      tooltip.style.top = `${{Math.max(padding, top)}}px`;
    }}
    document.querySelectorAll(".chart-point").forEach((point) => {{
      point.addEventListener("mouseenter", () => {{
        if (point.classList.contains("is-hidden")) return;
        document.querySelectorAll(`.series-line[data-series="${{CSS.escape(point.dataset.series)}}"]`).forEach((element) => element.classList.add("highlighted"));
        point.classList.add("active-point");
        tooltip.textContent = [point.dataset.name || "", `Time: ${{point.dataset.time || ""}}`, `Trade: ${{point.dataset.trade || ""}}`, `Equity: ${{point.dataset.equity || ""}}`].join("\\n");
        tooltip.style.display = "block";
      }});
      point.addEventListener("mousemove", moveTooltip);
      point.addEventListener("mouseleave", () => {{
        document.querySelectorAll(`.series-line[data-series="${{CSS.escape(point.dataset.series)}}"]`).forEach((element) => element.classList.remove("highlighted"));
        point.classList.remove("active-point");
        tooltip.style.display = "none";
      }});
    }});
    document.querySelectorAll(".legend-item").forEach((button) => {{
      button.addEventListener("click", () => {{
        const series = button.dataset.series;
        const nextHidden = button.getAttribute("aria-pressed") === "true";
        document.querySelectorAll(`.legend-item[data-series="${{CSS.escape(series)}}"]`).forEach((item) => {{
          item.setAttribute("aria-pressed", String(!nextHidden));
          item.classList.toggle("is-muted", nextHidden);
        }});
        document.querySelectorAll(`.series-line[data-series="${{CSS.escape(series)}}"], .chart-point[data-series="${{CSS.escape(series)}}"]`).forEach((element) => {{
          element.classList.toggle("dimmed", nextHidden);
          element.classList.toggle("is-hidden", nextHidden);
          if (element.classList.contains("chart-point")) element.style.pointerEvents = nextHidden ? "none" : "all";
        }});
        tooltip.style.display = "none";
      }});
    }});
  </script>
</body>
</html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_doc, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Optimize adaptive MBP portfolio strategy by market regime.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--enhanced-results", default=".tmp/mbp-enhanced-top10.csv")
    parser.add_argument("--refined-results", default=".tmp/mbp-refined-mean-reversion.csv")
    parser.add_argument("--stability-results", default=".tmp/mbp-selected-stability-optimized.csv")
    parser.add_argument("--output", default=".tmp/mbp-adaptive-portfolio.csv")
    parser.add_argument("--trades-output", default=".tmp/mbp-adaptive-portfolio-trades.csv")
    parser.add_argument("--report", default="reports/NQM6-mbp-adaptive-portfolio.html")
    parser.add_argument("--folds", type=int, default=6)
    parser.add_argument("--window-days", type=int, default=10)
    parser.add_argument("--window-step-days", type=int, default=5)
    args = parser.parse_args()

    features = _attach_regime(_load_features(Path(args.features_cache)))
    strategy_rows = _load_strategy_rows(
        [Path(args.enhanced_results), Path(args.refined_results), Path(args.stability_results)],
        OPTIMIZED_NAMES,
    )
    trades_by_alias = _build_strategy_trades(features, strategy_rows)
    ranked, trades_by_rule = optimize_portfolios(features, trades_by_alias, args.folds, args.window_days, args.window_step_days)
    if ranked.empty:
        raise SystemExit("No adaptive portfolio candidates found.")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(output, index=False)
    best_name = ranked.iloc[0]["name"]
    best_trades = trades_by_rule[best_name].copy()
    trades_output = Path(args.trades_output)
    trades_output.parent.mkdir(parents=True, exist_ok=True)
    best_trades.to_csv(trades_output, index=False)

    curves = {f"Adaptive portfolio: {best_name}": _equity_points(best_trades, features["ts"].min())}
    for alias, trades in trades_by_alias.items():
        curves[f"Single: {alias}"] = _equity_points(trades, features["ts"].min())
    _write_report(Path(args.report), features, ranked, best_trades, curves, trades_output)
    print(output)
    print(trades_output)
    print(args.report)
    print(
        ranked.head(10)[
            [
                "name",
                "live_ready",
                "full_trades",
                "full_net_points",
                "full_max_drawdown_points",
                "full_profit_factor",
                "full_stability",
                "positive_fold_rate",
                "positive_window_rate",
                "min_window_net_points",
                "cost_3x_net_points",
                "portfolio_score",
            ]
        ].to_string(index=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
