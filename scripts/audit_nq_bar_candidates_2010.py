from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from search_nq_bar_best_strategy_walkforward import prepare_bar_strategy_features, session_features
from tradingagents.backtesting.short_patterns import BacktestCosts, StrategySpec, build_trades
from tradingagents.dataflows.databento import _bar_zip_path


@dataclass(frozen=True)
class AuditCandidate:
    name: str
    session: str
    spec: StrategySpec


def candidates() -> list[AuditCandidate]:
    rows = [
        (
            "bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late",
            "us_late",
            StrategySpec(
                name="mean_reversion_lb30_thr1.4_hold60_long",
                family="mean_reversion",
                lookback=30,
                threshold=1.4,
                holding_minutes=60,
                direction_filter="long",
            ),
        ),
        (
            "bar_best_momentum_lb60_thr0.0006_hold30_long_us_late",
            "us_late",
            StrategySpec(
                name="momentum_lb60_thr0.0006_hold30_long",
                family="momentum",
                lookback=60,
                threshold=0.0006,
                holding_minutes=30,
                direction_filter="long",
            ),
        ),
        (
            "bar_best_mean_reversion_lb10_thr1_hold30_long_us_late",
            "us_late",
            StrategySpec(
                name="mean_reversion_lb10_thr1_hold30_long",
                family="mean_reversion",
                lookback=10,
                threshold=1.0,
                holding_minutes=30,
                direction_filter="long",
            ),
        ),
        (
            "bar_best_support_reclaim_lb15_thr0.0002_hold30_long_us_late",
            "us_late",
            StrategySpec(
                name="support_reclaim_lb15_thr0.0002_hold30_long",
                family="support_reclaim",
                lookback=15,
                threshold=0.0002,
                holding_minutes=30,
                direction_filter="long",
            ),
        ),
        (
            "bar_best_support_reclaim_lb15_thr0.0002_hold60_short_us_late",
            "us_late",
            StrategySpec(
                name="support_reclaim_lb15_thr0.0002_hold60_short",
                family="support_reclaim",
                lookback=15,
                threshold=0.0002,
                holding_minutes=60,
                direction_filter="short",
            ),
        ),
    ]
    return [AuditCandidate(name=name, session=session, spec=spec) for name, session, spec in rows]


def summarize(trades: pd.DataFrame, costs: BacktestCosts) -> dict[str, Any]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "net_dollars": 0.0,
            "max_drawdown_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_points": 0.0,
            "first_half_points": 0.0,
            "second_half_points": 0.0,
        }
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    wins = net[net > 0].sum()
    losses = -net[net < 0].sum()
    entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)
    split = entry_ts.median()
    first = net[entry_ts <= split]
    second = net[entry_ts > split]
    return {
        "trades": int(len(net)),
        "net_points": float(net.sum()),
        "net_dollars": float(net.sum() * costs.point_value),
        "max_drawdown_points": float(drawdown.max()) if not drawdown.empty else 0.0,
        "profit_factor": float(wins / losses) if losses else (999.0 if wins > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "avg_points": float(net.mean()),
        "first_half_points": float(first.sum()) if not first.empty else 0.0,
        "second_half_points": float(second.sum()) if not second.empty else 0.0,
    }


def rolling_windows(trades: pd.DataFrame, candidate: str, days: int) -> list[dict[str, Any]]:
    if trades.empty:
        return []
    frame = trades.copy()
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    start = frame["entry_ts"].min().normalize()
    end = frame["entry_ts"].max().normalize()
    rows: list[dict[str, Any]] = []
    cursor = start
    while cursor + pd.Timedelta(days=days) <= end:
        stop = cursor + pd.Timedelta(days=days)
        selected = frame[(frame["entry_ts"] >= cursor) & (frame["entry_ts"] < stop)]
        net = pd.to_numeric(selected["net_points"], errors="coerce").fillna(0.0)
        wins = net[net > 0].sum()
        losses = -net[net < 0].sum()
        rows.append(
            {
                "candidate": candidate,
                "start": str(cursor.date()),
                "end": str(stop.date()),
                "trades": int(len(net)),
                "net_points": float(net.sum()),
                "profit_factor": float(wins / losses) if losses else (999.0 if wins > 0 else 0.0),
            }
        )
        cursor += pd.Timedelta(days=days)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit selected NQ bar-only candidates on 2010-2026 history.")
    parser.add_argument("--start-date", default="2010-06-06")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-short-trend-2010-adx-cache.pkl")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--summary-output", default=".tmp/nq-bar-2010-selected-summary.csv")
    parser.add_argument("--yearly-output", default=".tmp/nq-bar-2010-selected-yearly.csv")
    parser.add_argument("--rolling-output", default=".tmp/nq-bar-2010-selected-90d.csv")
    parser.add_argument("--recent-output", default=".tmp/nq-bar-2010-selected-recent.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-bar-2010-selected-trades.csv")
    parser.add_argument("--report", default="reports/NQ-bar-2010-selected-candidate-audit.md")
    args = parser.parse_args()

    costs = BacktestCosts()
    features = prepare_bar_strategy_features(load_continuous_nq_bars(args))
    summary_rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    trade_frames: list[pd.DataFrame] = []

    for candidate in candidates():
        frame = session_features(features, candidate.session).reset_index(drop=True)
        trades = build_trades(frame, candidate.spec, costs)
        if trades.empty:
            continue
        trades = trades.copy()
        trades["candidate"] = candidate.name
        trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
        trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
        trade_frames.append(trades)
        summary_rows.append({"candidate": candidate.name, "session": candidate.session, **summarize(trades, costs)})
        yearly = pd.to_numeric(trades["net_points"], errors="coerce").groupby(trades["entry_ts"].dt.year).sum()
        for year, net_points in yearly.items():
            yearly_rows.append({"candidate": candidate.name, "year": int(year), "net_points": float(net_points)})
        rolling_rows.extend(rolling_windows(trades, candidate.name, 90))
        for label, start in [
            ("recent_3y", "2023-01-01"),
            ("recent_1y", "2025-04-28"),
            ("post_2021", "2021-04-28"),
        ]:
            selected = trades[trades["entry_ts"] >= pd.Timestamp(start, tz="UTC")]
            recent_rows.append({"candidate": candidate.name, "sample": label, "start": start, **summarize(selected, costs)})

    summary = pd.DataFrame(summary_rows)
    yearly = pd.DataFrame(yearly_rows)
    rolling = pd.DataFrame(rolling_rows)
    recent = pd.DataFrame(recent_rows)
    all_trades = pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame()

    for path, frame in [
        (args.summary_output, summary),
        (args.yearly_output, yearly),
        (args.rolling_output, rolling),
        (args.recent_output, recent),
        (args.trades_output, all_trades),
    ]:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output, index=False)

    write_report(Path(args.report), features, summary, yearly, rolling, recent, args)
    print(
        json.dumps(
            {
                "source": str(_bar_zip_path()),
                "feature_rows": int(len(features)),
                "summary_rows": int(len(summary)),
                "trades": int(len(all_trades)),
                "summary_output": args.summary_output,
                "report": args.report,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def write_report(
    path: Path,
    features: pd.DataFrame,
    summary: pd.DataFrame,
    yearly: pd.DataFrame,
    rolling: pd.DataFrame,
    recent: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NQ Bar-Only 2010 Candidate Audit",
        "",
        f"- Source: `{_bar_zip_path()}`.",
        f"- Span: `{features['ts'].min()}` to `{features['ts'].max()}`.",
        f"- Rows: `{len(features):,}`.",
        f"- Candidates: `{len(summary):,}` selected from prior 5y bar-only research.",
        "",
        "## Full Sample",
        "",
        markdown_table(summary.sort_values("net_points", ascending=False)),
        "",
        "## Yearly Stability",
        "",
        markdown_table(yearly.pivot_table(index="candidate", columns="year", values="net_points", aggfunc="sum").reset_index()),
        "",
        "## Rolling 90d Summary",
        "",
        markdown_table(
            rolling.groupby("candidate", as_index=False).agg(
                windows=("net_points", "count"),
                positive_rate=("net_points", lambda values: float((values > 0).mean())),
                min_window_points=("net_points", "min"),
                total_window_points=("net_points", "sum"),
            )
        ),
        "",
        "## Recent",
        "",
        markdown_table(recent.sort_values(["candidate", "sample"])),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    rows = ["| " + " | ".join(str(column) for column in frame.columns) + " |"]
    rows.append("| " + " | ".join(["---"] * len(frame.columns)) + " |")
    for _, row in frame.iterrows():
        values = []
        for value in row.tolist():
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


if __name__ == "__main__":
    raise SystemExit(main())
