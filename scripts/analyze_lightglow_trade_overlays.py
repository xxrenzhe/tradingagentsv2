from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_CANDIDATES = [
    "lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time",
    "lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time",
]


@dataclass(frozen=True)
class Overlay:
    extra_cost_points: float
    max_trades_per_day: int | None
    daily_stop_points: float | None

    @property
    def name(self) -> str:
        cap = "none" if self.max_trades_per_day is None else str(self.max_trades_per_day)
        stop = "none" if self.daily_stop_points is None else f"{self.daily_stop_points:g}"
        return f"cost{self.extra_cost_points:g}_cap{cap}_dstop{stop}"


def overlay_pool(args: argparse.Namespace) -> list[Overlay]:
    overlays: list[Overlay] = []
    caps = [None if value <= 0 else int(value) for value in args.max_trades_per_day]
    stops = [None if value <= 0 else float(value) for value in args.daily_stop_points]
    for cost in args.extra_cost_points:
        for cap in caps:
            for stop in stops:
                overlays.append(Overlay(float(cost), cap, stop))
    return overlays


def apply_overlay(trades: pd.DataFrame, overlay: Overlay) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    data = trades.sort_values("entry_ts").copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True)
    data["trade_date"] = data["entry_ts"].dt.date.astype(str)
    data["day_trade_number"] = data.groupby("trade_date").cumcount() + 1
    if overlay.max_trades_per_day is not None:
        data = data[data["day_trade_number"] <= overlay.max_trades_per_day].copy()
    if data.empty:
        return data
    data["overlay_net_points"] = pd.to_numeric(data["net_points"], errors="coerce").fillna(0.0) - overlay.extra_cost_points
    data["overlay_gross_points"] = pd.to_numeric(data["gross_points"], errors="coerce").fillna(0.0)
    if overlay.daily_stop_points is not None:
        day_cumulative = data.groupby("trade_date")["overlay_net_points"].cumsum()
        previous_day_cumulative = day_cumulative.groupby(data["trade_date"]).shift(1).fillna(0.0)
        data = data[previous_day_cumulative > -abs(overlay.daily_stop_points)].copy()
    data["overlay_name"] = overlay.name
    return data


def summarize(trades: pd.DataFrame, *, point_value: float) -> dict[str, Any]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "net_dollars": 0.0,
            "max_drawdown_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "positive_days": 0,
            "total_days": 0,
            "positive_day_rate": 0.0,
            "worst_day_points": 0.0,
            "avg_trades_per_day": 0.0,
            "net_to_drawdown": 0.0,
        }
    net = pd.to_numeric(trades["overlay_net_points"], errors="coerce").fillna(0.0)
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    wins = net[net > 0].sum()
    losses = abs(net[net < 0].sum())
    day_net = trades.assign(_net=net).groupby("trade_date")["_net"].sum()
    max_drawdown = float(abs(drawdown.min()))
    return {
        "trades": int(len(net)),
        "net_points": float(net.sum()),
        "net_dollars": float(net.sum() * point_value),
        "max_drawdown_points": max_drawdown,
        "profit_factor": float(wins / losses) if losses else (999.0 if wins > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "positive_days": int((day_net > 0).sum()),
        "total_days": int(len(day_net)),
        "positive_day_rate": float((day_net > 0).mean()) if len(day_net) else 0.0,
        "worst_day_points": float(day_net.min()) if len(day_net) else 0.0,
        "avg_trades_per_day": float(len(net) / len(day_net)) if len(day_net) else 0.0,
        "net_to_drawdown": float(net.sum() / max(max_drawdown, 1.0)),
    }


def analyze(args: argparse.Namespace) -> pd.DataFrame:
    trades = pd.read_csv(args.trades)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    candidates = args.candidates or DEFAULT_CANDIDATES
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_trades = trades[trades["candidate"].astype(str).eq(candidate)].copy()
        for overlay in overlay_pool(args):
            overlaid = apply_overlay(candidate_trades, overlay)
            row = {
                "candidate": candidate,
                "overlay": overlay.name,
                "extra_cost_points": overlay.extra_cost_points,
                "max_trades_per_day": overlay.max_trades_per_day if overlay.max_trades_per_day is not None else 0,
                "daily_stop_points": overlay.daily_stop_points if overlay.daily_stop_points is not None else 0,
                **summarize(overlaid, point_value=args.point_value),
            }
            rows.append(row)
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["controlled_score"] = (
        result["net_points"].clip(lower=0) * 0.001
        + result["profit_factor"].clip(upper=5) * 10.0
        + result["net_to_drawdown"].clip(upper=100)
        + result["positive_day_rate"] * 10.0
        - result["max_drawdown_points"] * 0.002
    )
    return result.sort_values(["controlled_score", "net_points", "profit_factor"], ascending=[False, False, False])


def markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "_No rows._"
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame[columns].iterrows():
        values = []
        for value in row:
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def write_report(path: Path, ranked: pd.DataFrame, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "candidate",
        "overlay",
        "trades",
        "net_points",
        "max_drawdown_points",
        "net_to_drawdown",
        "profit_factor",
        "positive_day_rate",
        "worst_day_points",
        "avg_trades_per_day",
        "controlled_score",
    ]
    lines = [
        "# Lightglow Trade Overlay Optimization",
        "",
        "## Scope",
        "",
        f"- Trades source: `{args.trades}`.",
        f"- Candidates: `{', '.join(args.candidates or DEFAULT_CANDIDATES)}`.",
        f"- Extra costs tested: `{', '.join(str(value) for value in args.extra_cost_points)}`.",
        f"- Daily caps tested: `{', '.join(str(value) for value in args.max_trades_per_day)}` where `0` means no cap.",
        f"- Daily stops tested: `{', '.join(str(value) for value in args.daily_stop_points)}` where `0` means no daily stop.",
        "",
        "## Ranked Overlays",
        "",
        markdown_table(ranked.head(args.top), columns),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze fast overlays on existing Lightglow trade streams.")
    parser.add_argument("--trades", default=".tmp/nq-lightglow-5y-walkforward-trades.csv")
    parser.add_argument("--output", default=".tmp/nq-lightglow-overlay-ranking.csv")
    parser.add_argument("--report", default="reports/NQ-lightglow-overlay-optimization.md")
    parser.add_argument("--candidates", nargs="+", default=None)
    parser.add_argument("--extra-cost-points", type=float, nargs="+", default=[0.0, 0.25, 0.5, 1.0])
    parser.add_argument("--max-trades-per-day", type=int, nargs="+", default=[0, 40, 80, 120])
    parser.add_argument("--daily-stop-points", type=float, nargs="+", default=[0.0, 200.0, 300.0, 400.0])
    parser.add_argument("--point-value", type=float, default=20.0)
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()

    ranked = analyze(args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(output, index=False)
    write_report(Path(args.report), ranked, args)
    result = {
        "status": "written",
        "rows": int(len(ranked)),
        "output": str(output),
        "report": args.report,
        "top": ranked.iloc[0].to_dict() if not ranked.empty else None,
    }
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
