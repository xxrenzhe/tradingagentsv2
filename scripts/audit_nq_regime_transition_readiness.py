from __future__ import annotations

import argparse
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
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from search_nq_regime_transition_systems import (
    RegimeCandidate,
    build_breakout_events,
    compute_outcomes,
    prepare_features,
    select_candidate_trades,
)
from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.dataflows.databento import _bar_zip_path


@dataclass(frozen=True)
class AuditCandidate:
    label: str
    candidate: RegimeCandidate


def default_candidates() -> list[AuditCandidate]:
    return [
        AuditCandidate(
            "best_wf_2r",
            RegimeCandidate(
                lookback=120,
                width_atr_max=12.0,
                efficiency_max=0.25,
                displacement_atr_min=1.2,
                body_share_min=0.55,
                volume_z_min=0.0,
                session="us_late",
                direction_filter="long",
                stop_mode="break_bar",
                reward_risk=2.0,
                horizon_minutes=240,
            ),
        ),
        AuditCandidate(
            "best_wf_3r",
            RegimeCandidate(
                lookback=120,
                width_atr_max=12.0,
                efficiency_max=0.25,
                displacement_atr_min=1.0,
                body_share_min=0.55,
                volume_z_min=-0.5,
                session="us_late",
                direction_filter="long",
                stop_mode="break_bar",
                reward_risk=3.0,
                horizon_minutes=240,
            ),
        ),
        AuditCandidate(
            "highest_fullsample_3r_neighbor",
            RegimeCandidate(
                lookback=60,
                width_atr_max=12.0,
                efficiency_max=0.25,
                displacement_atr_min=1.2,
                body_share_min=0.55,
                volume_z_min=0.0,
                session="us_late",
                direction_filter="long",
                stop_mode="break_bar",
                reward_risk=3.0,
                horizon_minutes=240,
            ),
        ),
    ]


def summarize_trades(trades: pd.DataFrame, costs: BacktestCosts) -> dict[str, Any]:
    if trades.empty:
        return {}
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    wins = net[net > 0]
    losses = net[net < 0]
    gross_profit = float(wins.sum())
    gross_loss = float((-losses).sum())
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)
    split = entry_ts.median()
    yearly = period_stats(trades, "YE")
    monthly = period_stats(trades, "ME")
    rolling_90d = rolling_stats(trades, 90)
    rolling_180d = rolling_stats(trades, 180)
    first = net[entry_ts <= split]
    second = net[entry_ts > split]
    losing_streak = max_losing_streak(net)
    return {
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "net_dollars": float(net.sum() * costs.point_value),
        "gross_profit_points": gross_profit,
        "gross_loss_points": gross_loss,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else (999.0 if gross_profit > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "avg_win_points": float(wins.mean()) if not wins.empty else 0.0,
        "avg_loss_points": float((-losses).mean()) if not losses.empty else 0.0,
        "payoff_ratio": float(wins.mean() / (-losses).mean()) if not wins.empty and not losses.empty else 0.0,
        "expectancy_points": float(net.mean()),
        "max_drawdown_points": float(drawdown.max()) if not drawdown.empty else 0.0,
        "net_to_drawdown": float(net.sum() / max(float(drawdown.max()), 1.0)) if not drawdown.empty else 0.0,
        "first_half_points": float(first.sum()) if not first.empty else 0.0,
        "second_half_points": float(second.sum()) if not second.empty else 0.0,
        "positive_years": int((yearly["net_points"] > 0).sum()) if not yearly.empty else 0,
        "years": int(len(yearly)),
        "positive_year_rate": float((yearly["net_points"] > 0).mean()) if not yearly.empty else 0.0,
        "worst_year_points": float(yearly["net_points"].min()) if not yearly.empty else 0.0,
        "positive_month_rate": float((monthly["net_points"] > 0).mean()) if not monthly.empty else 0.0,
        "worst_month_points": float(monthly["net_points"].min()) if not monthly.empty else 0.0,
        "positive_90d_rate": float((rolling_90d["net_points"] > 0).mean()) if not rolling_90d.empty else 0.0,
        "worst_90d_points": float(rolling_90d["net_points"].min()) if not rolling_90d.empty else 0.0,
        "positive_180d_rate": float((rolling_180d["net_points"] > 0).mean()) if not rolling_180d.empty else 0.0,
        "worst_180d_points": float(rolling_180d["net_points"].min()) if not rolling_180d.empty else 0.0,
        "max_losing_streak": int(losing_streak),
        "target_exit_share": float((trades["exit_reason"].astype(str) == "take_profit").mean()),
        "stop_exit_share": float((trades["exit_reason"].astype(str) == "stop_loss").mean()),
        "timeout_exit_share": float((trades["exit_reason"].astype(str) == "timeout").mean()),
    }


def period_stats(trades: pd.DataFrame, frequency: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["period", "trades", "net_points"])
    frame = trades.copy()
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    frame = frame.set_index("entry_ts")
    grouped = frame["net_points"].resample(frequency).agg(["count", "sum"]).reset_index()
    grouped = grouped.rename(columns={"entry_ts": "period", "count": "trades", "sum": "net_points"})
    return grouped[grouped["trades"] > 0].reset_index(drop=True)


def rolling_stats(trades: pd.DataFrame, days: int) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["start", "end", "trades", "net_points"])
    frame = trades.copy()
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    start = frame["entry_ts"].min().normalize()
    end = frame["entry_ts"].max().normalize()
    rows: list[dict[str, Any]] = []
    cursor = start
    while cursor + pd.Timedelta(days=days) <= end:
        stop = cursor + pd.Timedelta(days=days)
        selected = frame[(frame["entry_ts"] >= cursor) & (frame["entry_ts"] < stop)]
        rows.append(
            {
                "start": str(cursor.date()),
                "end": str(stop.date()),
                "trades": int(len(selected)),
                "net_points": float(pd.to_numeric(selected["net_points"], errors="coerce").fillna(0.0).sum()),
            }
        )
        cursor += pd.Timedelta(days=days)
    return pd.DataFrame(rows)


def max_losing_streak(net: pd.Series) -> int:
    streak = 0
    worst = 0
    for value in net:
        if value < 0:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
    return worst


def add_cost_stress(summary: dict[str, Any], trades: pd.DataFrame, costs: BacktestCosts, stress_costs: list[float]) -> None:
    for cost in stress_costs:
        summary[f"net_at_cost_{cost:g}"] = float(summary["net_points"] - (cost - costs.round_trip_cost_points) * len(trades))


def gate_summary(row: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    checks = {
        "net_positive": row["net_points"] > 0,
        "profit_factor": row["profit_factor"] >= args.gate_profit_factor,
        "net_to_drawdown": row["net_to_drawdown"] >= args.gate_net_to_drawdown,
        "positive_year_rate": row["positive_year_rate"] >= args.gate_positive_year_rate,
        "positive_90d_rate": row["positive_90d_rate"] >= args.gate_positive_90d_rate,
        "first_half_positive": row["first_half_points"] > 0,
        "second_half_positive": row["second_half_points"] > 0,
        "cost_stress_positive": row[f"net_at_cost_{args.gate_cost_points:g}"] > 0,
    }
    passed = all(checks.values())
    return {f"gate_{key}": bool(value) for key, value in checks.items()} | {"historical_stable_pass": bool(passed)}


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


def write_report(
    path: Path,
    frame: pd.DataFrame,
    events: pd.DataFrame,
    summary: pd.DataFrame,
    yearly: pd.DataFrame,
    rolling_90d: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    best = summary.sort_values(["historical_stable_pass", "net_to_drawdown", "net_points"], ascending=[False, False, False]).iloc[0]
    lines = [
        "# NQ Regime Transition Readiness Audit",
        "",
        "## Objective Audit",
        "",
        "| Requirement | Evidence | Status |",
        "| --- | --- | --- |",
        f"| NQ 1m bars under `data/raw/databento` | `{_bar_zip_path()}`, `{len(frame):,}` rows, `{frame['ts'].min()}` to `{frame['ts'].max()}` | covered |",
        f"| Trend strategy, not simple indicator-only | Range compression followed by displacement breakout; direction is long after upside range break | covered |",
        f"| Bar-computable factors only | OHLCV-derived range width, efficiency, ATR, candle body, volume z, session, structural bar stop | covered |",
        f"| Profitability and payoff tested | Full trade export plus PF, win rate, payoff, expectancy, R target, cost stress | covered |",
        f"| Stability tested | Yearly, monthly, rolling 90/180-day, first/second half, net/DD gates | covered |",
        f"| Conservative exits | Same-bar ambiguity resolves stop-first in source backtest; stop below displacement bar low | covered |",
        "",
        "## Historical Stability Gates",
        "",
        f"- PF >= `{args.gate_profit_factor}`.",
        f"- Net/DD >= `{args.gate_net_to_drawdown}`.",
        f"- Positive years >= `{args.gate_positive_year_rate:.0%}`.",
        f"- Positive 90-day windows >= `{args.gate_positive_90d_rate:.0%}`.",
        f"- First and second half both positive.",
        f"- Net remains positive at `{args.gate_cost_points}` NQ points round trip.",
        "",
        "## Verdict",
        "",
    ]
    if bool(best["historical_stable_pass"]):
        lines.append(
            f"Best audited candidate `{best['candidate']}` passes the historical stability gate. "
            f"It is a historical stable trend candidate, not a production approval."
        )
    else:
        lines.append(
            f"No audited candidate passes all historical stability gates. Best candidate by net/DD is `{best['candidate']}`."
        )
    lines.extend(
        [
            "",
            "## Candidate Summary",
            "",
            markdown_table(
                summary[
                    [
                        "label",
                        "candidate",
                        "historical_stable_pass",
                        "trades",
                        "net_points",
                        "profit_factor",
                        "win_rate",
                        "payoff_ratio",
                        "expectancy_points",
                        "max_drawdown_points",
                        "net_to_drawdown",
                        "positive_year_rate",
                        "positive_90d_rate",
                        "first_half_points",
                        "second_half_points",
                        f"net_at_cost_{args.gate_cost_points:g}",
                    ]
                ]
            ),
            "",
            "## Gate Detail",
            "",
            markdown_table(
                summary[
                    [
                        "label",
                        "gate_net_positive",
                        "gate_profit_factor",
                        "gate_net_to_drawdown",
                        "gate_positive_year_rate",
                        "gate_positive_90d_rate",
                        "gate_first_half_positive",
                        "gate_second_half_positive",
                        "gate_cost_stress_positive",
                    ]
                ]
            ),
            "",
            "## Yearly Net Points",
            "",
            markdown_table(yearly.pivot_table(index="label", columns="year", values="net_points", aggfunc="sum").reset_index()),
            "",
            "## Worst Rolling 90-Day Windows",
            "",
            markdown_table(rolling_90d.sort_values("net_points").head(20)),
            "",
            "## Interpretation",
            "",
            "- Passing this audit means the candidate is historically stable under the defined gates.",
            "- It still needs paper trading and execution validation before live deployment.",
            "- The edge remains concentrated in the `us_late` long-side NQ behavior, so regime drift is the main residual risk.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit NQ regime-transition candidates for historical stability readiness.")
    parser.add_argument("--start-date", default="2010-06-06")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-short-trend-2010-adx-cache.pkl")
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--output-prefix", default=".tmp/nq-regime-transition-readiness")
    parser.add_argument("--report", default="reports/NQ-regime-transition-readiness-audit.md")
    parser.add_argument("--gate-profit-factor", type=float, default=1.25)
    parser.add_argument("--gate-net-to-drawdown", type=float, default=4.0)
    parser.add_argument("--gate-positive-year-rate", type=float, default=0.70)
    parser.add_argument("--gate-positive-90d-rate", type=float, default=0.55)
    parser.add_argument("--gate-cost-points", type=float, default=2.125)
    parser.add_argument("--lookbacks", type=int, nargs="+", default=[60, 120])
    parser.add_argument("--width-atr-max", type=float, nargs="+", default=[12.0])
    parser.add_argument("--efficiency-max", type=float, nargs="+", default=[0.35])
    parser.add_argument("--displacement-atr-min", type=float, nargs="+", default=[1.0])
    parser.add_argument("--body-share-min", type=float, nargs="+", default=[0.55])
    parser.add_argument("--volume-z-min", type=float, nargs="+", default=[-0.5])
    parser.add_argument("--sessions", nargs="+", default=["us_late"])
    parser.add_argument("--direction-filters", nargs="+", default=["long"])
    parser.add_argument("--stop-modes", nargs="+", default=["break_bar"])
    parser.add_argument("--reward-risks", type=float, nargs="+", default=[2.0, 3.0])
    parser.add_argument("--horizon-minutes", type=int, nargs="+", default=[240])
    parser.add_argument("--breakout-buffer-atr", type=float, default=0.05)
    parser.add_argument("--min-buffer-points", type=float, default=0.25)
    parser.add_argument("--stop-buffer-atr", type=float, default=0.10)
    parser.add_argument("--stop-atr-mult", type=float, default=2.0)
    parser.add_argument("--min-stop-points", type=float, default=4.0)
    parser.add_argument("--max-stop-points", type=float, default=80.0)
    args = parser.parse_args()

    costs = BacktestCosts()
    base = load_continuous_nq_bars(args)
    frame = prepare_features(base, args)
    events = build_breakout_events(frame, args)

    candidates = default_candidates()
    outcome_cache: dict[tuple[str, float, int], pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    trade_frames: list[pd.DataFrame] = []
    yearly_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    rolling_frames: list[pd.DataFrame] = []
    rolling_180_frames: list[pd.DataFrame] = []

    for audited in candidates:
        candidate = audited.candidate
        key = (candidate.stop_mode, float(candidate.reward_risk), int(candidate.horizon_minutes))
        if key not in outcome_cache:
            print(f"computing outcomes {key}", flush=True)
            outcome_cache[key] = compute_outcomes(
                frame,
                events,
                stop_mode=candidate.stop_mode,
                reward_risk=float(candidate.reward_risk),
                horizon=int(candidate.horizon_minutes),
                args=args,
                costs=costs,
            )
        trades = select_candidate_trades(outcome_cache[key], candidate)
        if not trades.empty:
            trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
            trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
            trades["audit_label"] = audited.label
            trade_frames.append(trades)
        summary = summarize_trades(trades, costs)
        add_cost_stress(summary, trades, costs, [1.125, 1.625, 2.125, 3.125])
        summary.update(gate_summary(summary, args))
        summary["label"] = audited.label
        summary["candidate"] = candidate.name
        rows.append(summary)

        yearly = period_stats(trades, "YE")
        if not yearly.empty:
            yearly["label"] = audited.label
            yearly["year"] = pd.to_datetime(yearly["period"], utc=True).dt.year
            yearly_frames.append(yearly)
        monthly = period_stats(trades, "ME")
        if not monthly.empty:
            monthly["label"] = audited.label
            monthly_frames.append(monthly)
        rolling = rolling_stats(trades, 90)
        if not rolling.empty:
            rolling["label"] = audited.label
            rolling_frames.append(rolling)
        rolling_180 = rolling_stats(trades, 180)
        if not rolling_180.empty:
            rolling_180["label"] = audited.label
            rolling_180_frames.append(rolling_180)

    summary_frame = pd.DataFrame(rows).sort_values(
        ["historical_stable_pass", "net_to_drawdown", "net_points"],
        ascending=[False, False, False],
    )
    trades_frame = pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame()
    yearly_frame = pd.concat(yearly_frames, ignore_index=True, sort=False) if yearly_frames else pd.DataFrame()
    monthly_frame = pd.concat(monthly_frames, ignore_index=True, sort=False) if monthly_frames else pd.DataFrame()
    rolling_frame = pd.concat(rolling_frames, ignore_index=True, sort=False) if rolling_frames else pd.DataFrame()
    rolling_180_frame = pd.concat(rolling_180_frames, ignore_index=True, sort=False) if rolling_180_frames else pd.DataFrame()

    prefix = Path(args.output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    summary_frame.to_csv(f"{prefix}-summary.csv", index=False)
    trades_frame.to_csv(f"{prefix}-trades.csv", index=False)
    yearly_frame.to_csv(f"{prefix}-yearly.csv", index=False)
    monthly_frame.to_csv(f"{prefix}-monthly.csv", index=False)
    rolling_frame.to_csv(f"{prefix}-rolling90.csv", index=False)
    rolling_180_frame.to_csv(f"{prefix}-rolling180.csv", index=False)
    pd.DataFrame({"events": [len(events)], "rows": [len(frame)], "source": [str(_bar_zip_path())]}).to_csv(
        f"{prefix}-metadata.csv", index=False
    )
    write_report(Path(args.report), frame, events, summary_frame, yearly_frame, rolling_frame, args)

    print(
        json.dumps(
            {
                "rows": int(len(frame)),
                "events": int(len(events)),
                "summary": f"{prefix}-summary.csv",
                "trades": f"{prefix}-trades.csv",
                "report": args.report,
                "stable_passes": int(summary_frame["historical_stable_pass"].sum()),
                "best": summary_frame.iloc[0].to_dict() if not summary_frame.empty else None,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
