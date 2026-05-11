from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from tradingagents.backtesting.short_patterns import BacktestCosts

from .rules import TradingRule, condition_mask, direction_for_row
from .segmentation import Segment


@dataclass(frozen=True)
class ValidationResult:
    validation_id: str
    rule_id: str
    rule_signature: str
    analysis_segment_id: str
    validation_segment_id: str
    trades: int
    net_points: float
    gross_points: float
    max_drawdown_points: float
    profit_factor: float
    win_rate: float
    avg_win_points: float
    avg_loss_points: float
    expectancy_points: float
    exit_reason_json: str
    validation_status: str
    failure_reason: str = ""
    trade_rows: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("trade_rows", None)
        return data


def validate_rule_on_segment(
    *,
    rule: TradingRule,
    rule_id: str,
    signature: str,
    analysis_segment_id: str,
    validation_segment: Segment,
    features: pd.DataFrame,
    costs: BacktestCosts | None = None,
) -> ValidationResult:
    costs = costs or BacktestCosts()
    validation_end = min(validation_segment.end_index, validation_segment.start_index + int(rule.validation_bars))
    frame = features.iloc[validation_segment.start_index : validation_end].reset_index(drop=True).copy()
    validation_id = f"val_{signature}_{validation_segment.segment_id}"
    if len(frame) < rule.max_hold_bars + 2:
        return _empty_result(validation_id, rule_id, signature, analysis_segment_id, validation_segment.segment_id, "insufficient_bars")

    mask = condition_mask(frame, rule)
    signal_indexes = [int(index) for index in frame.index[mask]]
    rows: list[dict] = []
    next_available = 0
    for signal_index in signal_indexes:
        if len(rows) >= rule.max_trades_per_validation:
            break
        entry_index = signal_index + 1
        if entry_index < next_available or entry_index >= len(frame):
            continue
        direction = direction_for_row(frame.iloc[signal_index], rule)
        exit_index = min(entry_index + int(rule.max_hold_bars), len(frame) - 1)
        if exit_index <= entry_index:
            continue
        if "symbol" in frame.columns:
            path_symbols = frame.loc[entry_index:exit_index, "symbol"].astype(str)
            if not path_symbols.eq(str(frame.at[entry_index, "symbol"])).all():
                continue
        entry_price = float(frame.at[entry_index, "Open"])
        stop_price = entry_price - rule.stop_points if direction > 0 else entry_price + rule.stop_points
        target_price = entry_price + rule.target_points if direction > 0 else entry_price - rule.target_points
        exit_price = float(frame.at[exit_index, "Close"])
        exit_reason = "timeout"
        realized_exit_index = exit_index
        for path_index in range(entry_index, exit_index + 1):
            high = float(frame.at[path_index, "High"])
            low = float(frame.at[path_index, "Low"])
            if direction > 0:
                stop_hit = low <= stop_price
                target_hit = high >= target_price
            else:
                stop_hit = high >= stop_price
                target_hit = low <= target_price
            if stop_hit:
                exit_price = stop_price
                exit_reason = "stop_loss_ambiguous" if target_hit else "stop_loss"
                realized_exit_index = path_index
                break
            if target_hit:
                exit_price = target_price
                exit_reason = "take_profit"
                realized_exit_index = path_index
                break

        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points
        rows.append(
            {
                "trade_id": f"trade_{validation_id}_{len(rows):03d}",
                "validation_id": validation_id,
                "rule_signature": signature,
                "entry_ts": str(frame.at[entry_index, "ts"]),
                "exit_ts": str(frame.at[realized_exit_index, "ts"]),
                "direction": int(direction),
                "entry_price": entry_price,
                "exit_price": float(exit_price),
                "gross_points": float(gross_points),
                "net_points": float(net_points),
                "exit_reason": exit_reason,
            }
        )
        next_available = realized_exit_index + 1

    if not rows:
        return _empty_result(validation_id, rule_id, signature, analysis_segment_id, validation_segment.segment_id, "no_trades")
    return _summarize_rows(validation_id, rule_id, signature, analysis_segment_id, validation_segment.segment_id, rows)


def _summarize_rows(
    validation_id: str,
    rule_id: str,
    signature: str,
    analysis_segment_id: str,
    validation_segment_id: str,
    rows: list[dict],
) -> ValidationResult:
    net = pd.Series([float(row["net_points"]) for row in rows], dtype=float)
    gross = pd.Series([float(row["gross_points"]) for row in rows], dtype=float)
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    wins = net[net > 0].sum()
    losses = -net[net < 0].sum()
    win_values = net[net > 0]
    loss_values = net[net < 0]
    exit_reasons = pd.Series([str(row["exit_reason"]) for row in rows], dtype=str).value_counts().sort_index().to_dict()
    return ValidationResult(
        validation_id=validation_id,
        rule_id=rule_id,
        rule_signature=signature,
        analysis_segment_id=analysis_segment_id,
        validation_segment_id=validation_segment_id,
        trades=int(len(rows)),
        net_points=float(net.sum()),
        gross_points=float(gross.sum()),
        max_drawdown_points=float(drawdown.max()) if not drawdown.empty else 0.0,
        profit_factor=float(wins / losses) if losses else (999.0 if wins > 0 else 0.0),
        win_rate=float((net > 0).mean()),
        avg_win_points=float(win_values.mean()) if not win_values.empty else 0.0,
        avg_loss_points=float(loss_values.mean()) if not loss_values.empty else 0.0,
        expectancy_points=float(net.mean()),
        exit_reason_json=pd.Series(exit_reasons).to_json(),
        validation_status="validated",
        trade_rows=rows,
    )


def _empty_result(
    validation_id: str,
    rule_id: str,
    signature: str,
    analysis_segment_id: str,
    validation_segment_id: str,
    reason: str,
) -> ValidationResult:
    return ValidationResult(
        validation_id=validation_id,
        rule_id=rule_id,
        rule_signature=signature,
        analysis_segment_id=analysis_segment_id,
        validation_segment_id=validation_segment_id,
        trades=0,
        net_points=0.0,
        gross_points=0.0,
        max_drawdown_points=0.0,
        profit_factor=0.0,
        win_rate=0.0,
        avg_win_points=0.0,
        avg_loss_points=0.0,
        expectancy_points=0.0,
        exit_reason_json="{}",
        validation_status="skipped",
        failure_reason=reason,
        trade_rows=[],
    )
