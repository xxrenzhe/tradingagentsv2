from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


POINT_VALUE_BY_SYMBOL = {"MNQ": 2.0, "NQ": 20.0}


@dataclass(frozen=True)
class PromotedCandidate:
    priority: int
    label: str
    strategy_id: str
    lookback: int
    width_atr_max: float
    efficiency_max: float
    displacement_atr_min: float
    body_share_min: float
    volume_z_min: float
    session: str
    direction: str
    stop_mode: str
    reward_risk: float
    horizon_minutes: int
    trades: int
    net_points: float
    profit_factor: float
    win_rate: float
    max_drawdown_points: float
    net_to_drawdown: float
    positive_year_rate: float
    positive_90d_rate: float
    cost_stress_net_points: float
    note: str


PROMOTED_CANDIDATES = [
    PromotedCandidate(
        priority=1,
        label="optimized50_2r5_quality",
        strategy_id="regime_breakout_lb50_w8_eff0.15_disp1.8_body0.6_vol0.5_us_late_long_break_bar_rr2.5_h180",
        lookback=50,
        width_atr_max=8.0,
        efficiency_max=0.15,
        displacement_atr_min=1.8,
        body_share_min=0.60,
        volume_z_min=0.50,
        session="us_late",
        direction="long",
        stop_mode="break_bar",
        reward_risk=2.5,
        horizon_minutes=180,
        trades=442,
        net_points=3479.6521,
        profit_factor=1.9677,
        win_rate=0.4276,
        max_drawdown_points=210.7504,
        net_to_drawdown=16.5108,
        positive_year_rate=0.7647,
        positive_90d_rate=0.6508,
        cost_stress_net_points=2816.6521,
        note="Best risk-adjusted readiness-audit candidate; use as primary paper candidate.",
    ),
    PromotedCandidate(
        priority=2,
        label="defensive45_2r5_loweff",
        strategy_id="regime_breakout_lb45_w10_eff0.1_disp1.6_body0.55_vol0_us_late_long_break_bar_rr2.5_h180",
        lookback=45,
        width_atr_max=10.0,
        efficiency_max=0.10,
        displacement_atr_min=1.6,
        body_share_min=0.55,
        volume_z_min=0.0,
        session="us_late",
        direction="long",
        stop_mode="break_bar",
        reward_risk=2.5,
        horizon_minutes=180,
        trades=593,
        net_points=3398.3338,
        profit_factor=1.7051,
        win_rate=0.3912,
        max_drawdown_points=230.0867,
        net_to_drawdown=14.7698,
        positive_year_rate=0.8750,
        positive_90d_rate=0.6333,
        cost_stress_net_points=2508.8338,
        note="Most year-stable promoted candidate; use as second paper candidate after primary dry run.",
    ),
    PromotedCandidate(
        priority=3,
        label="short45_2r25_netdd",
        strategy_id="regime_breakout_lb45_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2.25_h240",
        lookback=45,
        width_atr_max=12.0,
        efficiency_max=0.25,
        displacement_atr_min=1.2,
        body_share_min=0.55,
        volume_z_min=0.0,
        session="us_late",
        direction="long",
        stop_mode="break_bar",
        reward_risk=2.25,
        horizon_minutes=240,
        trades=1166,
        net_points=4118.2479,
        profit_factor=1.4229,
        win_rate=0.3842,
        max_drawdown_points=333.1319,
        net_to_drawdown=12.3622,
        positive_year_rate=0.7059,
        positive_90d_rate=0.6190,
        cost_stress_net_points=2369.2479,
        note="Higher-frequency promoted candidate; keep behind the two cleaner 2.5R variants.",
    ),
]


def build_rows(*, symbol: str, contract_month: str, quantity: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    point_value = POINT_VALUE_BY_SYMBOL.get(symbol.upper(), 20.0)
    for candidate in PROMOTED_CANDIDATES:
        candidate_dict = asdict(candidate)
        stop_loss_instruction = (
            "At signal close, enter next 1m bar open. For long trades, stop is signal bar low minus "
            "max(0.25 points, 0.10 * ATR30). Reject if entry-stop distance is outside 4-80 NQ points."
        )
        rows.append(
            {
                **candidate_dict,
                "symbol": symbol.upper(),
                "contract_month": contract_month,
                "quantity": quantity,
                "point_value": point_value,
                "session_utc": "20:00-22:59 UTC",
                "session_china": "04:00-06:59 Asia/Shanghai next calendar day during UTC+8",
                "entry_rule": (
                    "Prior rolling range is compressed and inefficient; signal candle closes above prior range high "
                    "plus max(0.25 points, 0.05 * ATR30), closes green, and meets displacement/body/volume filters. "
                    "Entry is next 1m open."
                ),
                "stop_rule": stop_loss_instruction,
                "target_rule": "Take profit at entry + stop_distance * reward_risk.",
                "timeout_rule": "Exit at max horizon if neither stop nor target is hit.",
                "same_bar_rule": "If stop and target are both touched in the same 1m bar, count stop first.",
                "non_overlap_rule": "Do not open a new candidate trade until the previous candidate trade has exited.",
                "paper_stage": "historical_ohlcv_adapter_ready_dry_run_parity_required",
                "min_paper_outcomes": 30,
                "min_paper_net_points": 0.0,
                "min_paper_profit_factor": 1.20,
                "min_paper_win_rate": 0.35,
                "max_consecutive_losses": 4,
                "max_daily_loss_points": 80.0,
                "max_weekly_loss_points": 160.0,
                "max_open_positions": 1,
                "halt_rule": (
                    "Halt on 4 consecutive losses, -80 points daily, -160 points weekly, adapter mismatch, "
                    "real account detection, existing exposure conflict, or bracket rejection."
                ),
                "promotion_rule": (
                    "Only consider live after adapter dry-run parity is clean, at least 30 paper outcomes are recorded, "
                    "paper net is positive, paper PF >= 1.20, and no halt rule fired."
                ),
                "implementation_status": "live_ohlcv_adapter_ready_needs_parity_validation",
                "adapter_gap": (
                    "run_ibkr_live_paper_trader accepts regime_transition strategy IDs and requests IBKR historical 1m "
                    "TRADES bars for OHLCV/volume. Before submit, run one session in dry-run and compare generated "
                    "signals against the same minute bars exported from Databento/IBKR."
                ),
                "dry_run_command_after_adapter": paper_command(candidate, symbol, contract_month, quantity, submit=False),
                "submit_command_after_adapter": paper_command(candidate, symbol, contract_month, quantity, submit=True),
            }
        )
    return pd.DataFrame(rows)


def build_config(plan: pd.DataFrame) -> dict[str, Any]:
    return {
        "package": "nq_regime_transition_paper_validation",
        "version": 1,
        "data_granularity": "1min OHLCV",
        "timezone": "UTC for rule evaluation; Asia/Shanghai only for operator scheduling",
        "global_rules": {
            "breakout_buffer": "max(0.25 NQ points, 0.05 * ATR30)",
            "stop_buffer": "max(0.25 NQ points, 0.10 * ATR30)",
            "atr_windows": {"atr30": 30, "atr120": 120},
            "volume_z_window": 60,
            "min_stop_points": 4.0,
            "max_stop_points": 80.0,
            "round_trip_cost_points_assumed_in_backtest": 0.625,
            "stress_cost_points_passed": 2.125,
            "same_bar_ambiguity": "stop_first",
            "position_overlap": "single_position_per_candidate_family",
        },
        "paper_gate": {
            "trade_one_candidate_at_a_time": True,
            "min_outcomes": 30,
            "min_net_points": 0.0,
            "min_profit_factor": 1.20,
            "min_win_rate": 0.35,
            "max_consecutive_losses": 4,
            "max_daily_loss_points": 80.0,
            "max_weekly_loss_points": 160.0,
        },
        "candidates": plan.to_dict(orient="records"),
    }


def paper_command(candidate: PromotedCandidate, symbol: str, contract_month: str, quantity: int, *, submit: bool) -> str:
    parts = [
        ".venv/bin/python scripts/run_ibkr_live_paper_trader.py",
        "--signal-mode strategy",
        "--strategy-family regime_transition",
        f"--strategy-id {candidate.label}",
        f"--selected-alias {candidate.label}",
        f"--symbol {symbol.upper()}",
        f"--contract-month {contract_month}",
        f"--quantity {quantity}",
        f"--max-hold-minutes {candidate.horizon_minutes}",
        f"--min-bars {candidate.lookback + 121}",
        "--paper-validation-accrual-mode",
        "--min-paper-outcomes 30",
        "--min-paper-net-points 0",
        "--min-paper-win-rate 35",
        "--max-consecutive-losses 4",
        "--daemon",
        "--interval-seconds 30",
        "--max-iterations 0",
    ]
    if submit:
        parts.append("--submit")
    return " ".join(parts)


def write_report(path: Path, plan: pd.DataFrame, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    top = plan.iloc[0]
    lines = [
        "# NQ Regime-Transition Paper Validation Package",
        "",
        "## Decision",
        "",
        "Stop optimizing the screenshot three-trend strategy as a standalone system. Its best clean holdout result is too small versus the promoted regime-transition candidates. The next useful step is paper validation of the stronger range-compression to displacement-breakout family.",
        "",
        f"- Primary paper candidate: `{top['label']}`.",
        f"- Historical sample: `2010-2026`, `{int(top['trades']):,}` trades, `{top['net_points']:.2f}` NQ points, PF `{top['profit_factor']:.3f}`, max DD `{top['max_drawdown_points']:.2f}` points.",
        f"- Execution symbol: `{args.symbol.upper()}` `{args.contract_month}`, quantity `{args.quantity}`.",
        f"- Machine config: `{args.config_output}`.",
        f"- Candidate CSV: `{args.output}`.",
        "",
        "## Market Feature",
        "",
        "The promoted setup is not a generic indicator signal. It is a `compression -> displacement -> trend start` pattern:",
        "",
        "- Compression: prior rolling range width is small relative to ATR120 and directional efficiency is low.",
        "- Displacement: the signal candle expands to at least the configured ATR30 multiple with a large real body.",
        "- Breakout: close must exceed the prior range high plus `max(0.25, 0.05 * ATR30)`.",
        "- Participation: optional volume z-score filter keeps the cleanest candidate away from low-participation breakouts.",
        "- Timing: only `us_late`, meaning `20:00-22:59 UTC`.",
        "",
        "## Strategy Rules",
        "",
        "- Direction is long only.",
        "- Entry is next 1-minute bar open after the qualifying breakout candle.",
        "- Stop is the breakout candle low minus `max(0.25, 0.10 * ATR30)`; reject trades with stop distance below `4` or above `80` NQ points.",
        "- Target is fixed R from actual stop distance; top candidates use `2.5R`, the higher-frequency fallback uses `2.25R`.",
        "- Timeout exit is `180` or `240` minutes depending on candidate.",
        "- Same-bar stop/target ambiguity is resolved stop-first; no overlapping trades inside this candidate family.",
        "",
        "## Paper Gate",
        "",
        "- Run only one candidate at a time, starting with `optimized50_2r5_quality`.",
        "- Start dry-run with the IBKR historical 1-minute OHLCV adapter; submit only after one clean session of signal parity.",
        "- Minimum paper sample is `30` outcomes, positive net points, PF `>= 1.20`, win rate `>= 35%`, and no more than `4` consecutive losses.",
        "- Halt immediately at `-80` NQ points daily, `-160` weekly, any bracket/order rejection, existing exposure conflict, adapter mismatch, or real-account detection.",
        "",
        "## Adapter Gap",
        "",
        "`run_ibkr_live_paper_trader.py` now accepts `--strategy-family regime_transition` and uses IBKR historical `1 min` TRADES bars for OHLCV/volume. The remaining blocker is parity, not implementation: run dry-run for one session and compare signals against the same minute bars before enabling `--submit`.",
        "",
        "## Candidate Plan",
        "",
        markdown_table(
            plan[
                [
                    "priority",
                    "label",
                    "trades",
                    "net_points",
                    "profit_factor",
                    "win_rate",
                    "max_drawdown_points",
                    "net_to_drawdown",
                    "positive_year_rate",
                    "positive_90d_rate",
                    "implementation_status",
                ]
            ]
        ),
        "",
        "## Commands After Adapter",
        "",
    ]
    for _, row in plan.iterrows():
        lines.extend(
            [
                f"### {row['label']}",
                "",
                "Dry run:",
                "",
                "```bash",
                str(row["dry_run_command_after_adapter"]),
                "```",
                "",
                "Submit:",
                "",
                "```bash",
                str(row["submit_command_after_adapter"]),
                "```",
                "",
            ]
        )
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Build paper validation package for promoted NQ regime-transition strategies.")
    parser.add_argument("--output", default="reports/NQ-regime-transition-paper-validation-plan.csv")
    parser.add_argument("--config-output", default="reports/NQ-regime-transition-paper-validation-config.json")
    parser.add_argument("--report", default="reports/NQ-regime-transition-paper-validation-plan.md")
    parser.add_argument("--symbol", default="MNQ")
    parser.add_argument("--contract-month", default="202606")
    parser.add_argument("--quantity", type=int, default=1)
    args = parser.parse_args()

    plan = build_rows(symbol=args.symbol, contract_month=args.contract_month, quantity=args.quantity)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    plan.to_csv(output, index=False)

    config = build_config(plan)
    config_output = Path(args.config_output)
    config_output.parent.mkdir(parents=True, exist_ok=True)
    config_output.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")

    write_report(Path(args.report), plan, args)
    print(
        json.dumps(
            {
                "candidates": plan["label"].tolist(),
                "output": str(output),
                "config_output": str(config_output),
                "report": args.report,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
