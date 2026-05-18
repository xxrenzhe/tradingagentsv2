from __future__ import annotations

import argparse
import html
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"
for path in (ROOT_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtest_nq_three_trend_lightglow_ict import cost_stress, setup_name, summarize_trades
from tradingagents.backtesting.short_patterns import BacktestCosts


@dataclass(frozen=True)
class CellPolicy:
    name: str
    train_years: int
    min_cell_trades: int
    min_cell_pf: float
    min_cell_avg_points: float
    min_cell_win_rate: float
    min_cells_selected: int = 1
    mode: str = "select"
    max_bad_cell_pf: float = 0.75
    max_bad_cell_avg_points: float = -2.0


POLICIES = [
    CellPolicy("balanced_pf1_avg0", train_years=3, min_cell_trades=5, min_cell_pf=1.0, min_cell_avg_points=0.0, min_cell_win_rate=0.34),
    CellPolicy("strict_pf1.15_avg0.5", train_years=3, min_cell_trades=8, min_cell_pf=1.15, min_cell_avg_points=0.5, min_cell_win_rate=0.38),
    CellPolicy("loose_pf0.95_avg-0.25", train_years=3, min_cell_trades=5, min_cell_pf=0.95, min_cell_avg_points=-0.25, min_cell_win_rate=0.33),
    CellPolicy("expanding_pf1_avg0", train_years=99, min_cell_trades=6, min_cell_pf=1.0, min_cell_avg_points=0.0, min_cell_win_rate=0.34),
    CellPolicy("exclude_bad_pf0.75_avg-2", train_years=3, min_cell_trades=7, min_cell_pf=0.0, min_cell_avg_points=-999.0, min_cell_win_rate=0.0, mode="exclude_bad", max_bad_cell_pf=0.75, max_bad_cell_avg_points=-2.0),
    CellPolicy("exclude_bad_expanding_pf0.8_avg-1.5", train_years=99, min_cell_trades=7, min_cell_pf=0.0, min_cell_avg_points=-999.0, min_cell_win_rate=0.0, mode="exclude_bad", max_bad_cell_pf=0.8, max_bad_cell_avg_points=-1.5),
]


def add_time_columns(trades: pd.DataFrame) -> pd.DataFrame:
    out = trades.copy()
    out["entry_ts"] = pd.to_datetime(out["entry_ts"], utc=True)
    out["exit_ts"] = pd.to_datetime(out["exit_ts"], utc=True)
    out["year"] = out["entry_ts"].dt.year
    out["hour"] = out["entry_ts"].dt.hour
    out["cell"] = out["setup"].astype(str) + " @ " + out["hour"].astype(str).str.zfill(2) + ":00 UTC"
    return out


def profit_factor(points: pd.Series) -> float:
    wins = points[points > 0].sum()
    losses = abs(points[points < 0].sum())
    return float(wins / losses) if losses else 999.0


def cell_stats(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for (setup, hour), group in trades.groupby(["setup", "hour"], sort=True):
        net = group["net_points"].astype(float)
        rows.append(
            {
                "setup": setup,
                "setup_name": setup_name(setup),
                "hour": int(hour),
                "cell": f"{setup} @ {int(hour):02d}:00 UTC",
                "trades": int(len(group)),
                "net_points": float(net.sum()),
                "avg_points": float(net.mean()),
                "win_rate": float((net > 0).mean()),
                "profit_factor": profit_factor(net),
            }
        )
    return pd.DataFrame(rows).sort_values(["net_points", "profit_factor"], ascending=[False, False])


def select_cells(train: pd.DataFrame, policy: CellPolicy) -> pd.DataFrame:
    stats = cell_stats(train)
    if stats.empty:
        return stats
    selected = stats[
        (stats["trades"] >= policy.min_cell_trades)
        & (stats["profit_factor"] >= policy.min_cell_pf)
        & (stats["avg_points"] >= policy.min_cell_avg_points)
        & (stats["win_rate"] >= policy.min_cell_win_rate)
    ].copy()
    if len(selected) < policy.min_cells_selected:
        return selected
    return selected


def walk_forward_policy(trades: pd.DataFrame, policy: CellPolicy, start_test_year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    selected_frames: list[pd.DataFrame] = []
    selected_trades: list[pd.DataFrame] = []
    years = sorted(int(year) for year in trades["year"].unique())
    for test_year in years:
        if test_year < start_test_year:
            continue
        train_start = min(years) if policy.train_years >= 90 else test_year - policy.train_years
        train = trades[(trades["year"] >= train_start) & (trades["year"] < test_year)]
        test = trades[trades["year"] == test_year]
        selected = select_cells(train, policy)
        excluded = pd.DataFrame()
        if policy.mode == "exclude_bad":
            stats = cell_stats(train)
            excluded = stats[
                (stats["trades"] >= policy.min_cell_trades)
                & ((stats["profit_factor"] <= policy.max_bad_cell_pf) | (stats["avg_points"] <= policy.max_bad_cell_avg_points))
            ].copy()
            selected = stats.merge(excluded[["setup", "hour"]], on=["setup", "hour"], how="left", indicator=True)
            selected = selected[selected["_merge"] == "left_only"].drop(columns=["_merge"])
        selected["test_year"] = test_year
        selected["train_start"] = train_start
        selected["train_end"] = test_year - 1
        selected_frames.append(selected)
        cells = set(zip(selected["setup"], selected["hour"]))
        if policy.mode == "exclude_bad":
            bad_cells = set(zip(excluded["setup"], excluded["hour"])) if not excluded.empty else set()
            mask = ~test.apply(lambda row: (row["setup"], row["hour"]) in bad_cells, axis=1)
            year_trades = test[mask].copy()
        elif cells:
            mask = test.apply(lambda row: (row["setup"], row["hour"]) in cells, axis=1)
            year_trades = test[mask].copy()
        else:
            year_trades = test.iloc[0:0].copy()
        year_trades["policy"] = policy.name
        year_trades["test_year"] = test_year
        selected_trades.append(year_trades)
        summary = summarize_trades(year_trades, BacktestCosts())
        rows.append(
            {
                "policy": policy.name,
                "test_year": test_year,
                "train_start": train_start,
                "train_end": test_year - 1,
                "selected_cells": int(len(selected)),
                "train_trades": int(len(train)),
                **summary,
            }
        )
    yearly = pd.DataFrame(rows)
    selected_cells = pd.concat(selected_frames, ignore_index=True) if selected_frames else pd.DataFrame()
    selected_trade_frame = pd.concat(selected_trades, ignore_index=True) if selected_trades else trades.iloc[0:0].copy()
    return yearly, selected_cells, selected_trade_frame


def drawdown(points: pd.Series) -> float:
    if points.empty:
        return 0.0
    equity = points.astype(float).cumsum()
    return float(abs((equity - equity.cummax()).min()))


def policy_summary(trades_by_policy: dict[str, pd.DataFrame], costs: BacktestCosts) -> pd.DataFrame:
    rows = []
    for policy_name, trades in trades_by_policy.items():
        summary = summarize_trades(trades, costs)
        rows.append({"policy": policy_name, **summary})
    return pd.DataFrame(rows).sort_values(["profit_factor", "net_points"], ascending=[False, False])


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(float(value)):
            return "N/A"
        return f"{float(value):,.{digits}f}"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    return html.escape(str(value))


def pct(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if not np.isfinite(number):
        return "N/A"
    return f"{number:.2%}"


def table_html(frame: pd.DataFrame, columns: list[str], percent_columns: set[str] | None = None) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    percent_columns = percent_columns or set()
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    rows = []
    for _, row in frame[columns].iterrows():
        cells = []
        for column in columns:
            value = row[column]
            rendered = pct(value) if column in percent_columns else fmt(value, 3 if isinstance(value, float) else 2)
            cells.append(f"<td>{rendered}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def build_report(
    base: pd.DataFrame,
    policy_rows: pd.DataFrame,
    yearly_rows: pd.DataFrame,
    selected_cells: pd.DataFrame,
    best_policy: str,
    best_trades: pd.DataFrame,
    stress: pd.DataFrame,
    args: argparse.Namespace,
) -> str:
    costs = BacktestCosts()
    base_oos = base[base["year"] >= args.start_test_year]
    base_summary = summarize_trades(base_oos, costs)
    best_summary = summarize_trades(best_trades, costs)
    selected_cells_view = selected_cells[selected_cells["test_year"] >= args.start_test_year].copy()
    if not selected_cells_view.empty:
        selected_cells_view = selected_cells_view.sort_values(["test_year", "net_points"], ascending=[True, False]).head(40)
    cards = "".join(
        f"<div class='card'><span>{label}</span><strong>{value}</strong></div>"
        for label, value in [
            ("Base OOS 净点数", fmt(base_summary["net_points"], 2)),
            ("Optimized OOS 净点数", fmt(best_summary["net_points"], 2)),
            ("Base PF", fmt(base_summary["profit_factor"], 3)),
            ("Optimized PF", fmt(best_summary["profit_factor"], 3)),
            ("Optimized 交易数", fmt(best_summary["trades"], 0)),
            ("Optimized 胜率", pct(best_summary["win_rate"])),
            ("Optimized 最大回撤", fmt(best_summary["max_drawdown_points"], 2)),
            ("Best Policy", best_policy),
        ]
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>NQ 三段趋势 Walk-forward 优化报告</title>
  <style>
    body {{ margin: 0; background: #09111f; color: #e8eef8; font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 34px 24px 70px; }}
    h1 {{ margin: 0 0 8px; font-size: 34px; letter-spacing: -0.03em; }}
    h2 {{ margin-top: 34px; border-bottom: 1px solid #27364f; padding-bottom: 8px; }}
    p, li {{ color: #b8c5d8; line-height: 1.65; }}
    code {{ color: #93c5fd; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 24px 0; }}
    .card {{ background: linear-gradient(145deg, #101a2c, #15243b); border: 1px solid #2a3a55; border-radius: 14px; padding: 16px; }}
    .card span {{ display: block; color: #8ea0bb; font-size: 13px; }}
    .card strong {{ display: block; margin-top: 8px; font-size: 22px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; font-size: 13px; }}
    th, td {{ border: 1px solid #2a3a55; padding: 8px 10px; text-align: right; }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
    th {{ background: #14223a; color: #dbeafe; }}
    .warn {{ background: #211911; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 8px; }}
    .note {{ background: #0f1b2e; border-left: 4px solid #38bdf8; padding: 12px 16px; border-radius: 8px; }}
  </style>
</head>
<body>
<main>
  <h1>NQ 三段趋势 Walk-forward 优化报告</h1>
  <p>输入交易：<code>{html.escape(args.trades)}</code>。测试从 <code>{args.start_test_year}</code> 年开始；每个测试年只使用之前年份训练 setup-hour 交易单元。</p>
  <div class="cards">{cards}</div>

  <h2>方法</h2>
  <p>优化只做一件事：选择过去训练期表现合格的 <code>setup + UTC hour</code> 单元，并应用到下一测试年。没有用测试年结果选择交易单元，因此这是 OOS walk-forward 过滤，不是全样本挑小时。</p>
  <div class="warn">注意：这里优化的是交易过滤器，不是最终生产策略。最佳 policy 是从预先定义的少量 policy 中比较出来的，仍需进一步做更长训练期、成本压力和结构止损验证。</div>

  <h2>Policy 汇总</h2>
  {table_html(policy_rows, ["policy", "trades", "net_points", "win_rate", "profit_factor", "avg_points", "max_drawdown_points", "take_profit_rate", "stop_loss_rate"], {"win_rate", "take_profit_rate", "stop_loss_rate"})}

  <h2>最佳 Policy 年度 OOS</h2>
  {table_html(yearly_rows[yearly_rows["policy"] == best_policy], ["test_year", "selected_cells", "train_trades", "trades", "net_points", "win_rate", "profit_factor", "avg_points", "max_drawdown_points"], {"win_rate"})}

  <h2>最佳 Policy 成本压力</h2>
  {table_html(stress, ["cost_multiplier", "net_points", "profit_factor", "avg_points"])}

  <h2>训练期选中的交易单元样例</h2>
  {table_html(selected_cells_view, ["test_year", "train_start", "train_end", "setup_name", "hour", "trades", "net_points", "win_rate", "profit_factor", "avg_points"], {"win_rate"}) if not selected_cells_view.empty else "<p>No selected cells.</p>"}

  <h2>下一步</h2>
  <ul>
    <li>把最佳 policy 固化后，在参数网格上只用训练期优化结构止损/止盈，测试期只验证。</li>
    <li>针对 <code>eqh_distribution_short</code> 增加强趋势禁空过滤，避免把趋势延续误识别成扫高反转。</li>
    <li>替换 ATR 止损为结构止损：扫高做空用 sweep high 外侧，突破做多用箱体另一侧，吸收反弹用吸收区低点外侧。</li>
  </ul>
</main>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Walk-forward optimize three-trend setup/hour filters.")
    parser.add_argument("--trades", default="reports/NQ-three-trend-lightglow-ict-trades.csv")
    parser.add_argument("--report", default="reports/NQ-three-trend-walkforward-optimization.html")
    parser.add_argument("--output-trades", default="reports/NQ-three-trend-walkforward-optimized-trades.csv")
    parser.add_argument("--start-test-year", type=int, default=2022)
    args = parser.parse_args()

    costs = BacktestCosts()
    trades = add_time_columns(pd.read_csv(args.trades))
    policy_trade_frames: dict[str, pd.DataFrame] = {}
    yearly_frames: list[pd.DataFrame] = []
    selected_frames: list[pd.DataFrame] = []
    for policy in POLICIES:
        yearly, selected, selected_trades = walk_forward_policy(trades, policy, args.start_test_year)
        policy_trade_frames[policy.name] = selected_trades
        yearly_frames.append(yearly)
        selected_frames.append(selected)
    policy_rows = policy_summary(policy_trade_frames, costs)
    yearly_rows = pd.concat(yearly_frames, ignore_index=True) if yearly_frames else pd.DataFrame()
    selected_cells = pd.concat(selected_frames, ignore_index=True) if selected_frames else pd.DataFrame()
    best_policy = str(policy_rows.iloc[0]["policy"])
    best_trades = policy_trade_frames[best_policy].copy()
    stress = cost_stress(best_trades, costs)

    Path(args.output_trades).parent.mkdir(parents=True, exist_ok=True)
    best_trades.to_csv(args.output_trades, index=False)
    report = build_report(trades, policy_rows, yearly_rows, selected_cells, best_policy, best_trades, stress, args)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(report, encoding="utf-8")

    print(f"wrote {args.report}")
    print(f"wrote {args.output_trades}")
    print(policy_rows.to_string(index=False))
    print("\\nBest yearly:")
    print(yearly_rows[yearly_rows["policy"] == best_policy].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
