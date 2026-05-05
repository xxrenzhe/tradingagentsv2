from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd

from tradingagents.backtesting.short_patterns import BacktestCosts, StrategySpec, summarize_trades

from .agent_gate import AgentGateConfig, AgentStrategyGate, PaperTradeOutcome, record_agent_gate_outcome
from .paper_validation import build_paper_intent_from_trade


@dataclass(frozen=True)
class GateReplayConfig:
    mode: str = "offline"
    sizing_mode: str = "scale"
    contract_month: str = "202606"
    quantity: int = 1
    stop_loss_points: float = 16.0
    take_profit_points: float = 24.0
    audit_path: Path = Path(".tmp/agent-gate-backtest-audit.jsonl")
    decision_output: Path = Path(".tmp/mbp-agent-gate-backtest-decisions.csv")
    summary_output: Path = Path(".tmp/mbp-agent-gate-backtest-summary.csv")
    max_trades: int | None = None
    record_shadow_outcomes: bool = True
    reset_audit: bool = True


def replay_gate_on_trades(
    trades: pd.DataFrame,
    *,
    replay_config: GateReplayConfig | None = None,
    gate_config: AgentGateConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    replay_config = replay_config or GateReplayConfig()
    gate_config = gate_config or AgentGateConfig(audit_path=replay_config.audit_path)
    gate_config = replace(gate_config, audit_path=replay_config.audit_path, learning_context_enabled=False)
    rows = []
    sorted_trades = trades.sort_values("entry_ts").reset_index(drop=True)
    if replay_config.max_trades is not None:
        sorted_trades = sorted_trades.head(replay_config.max_trades)
    replay_config.audit_path.parent.mkdir(parents=True, exist_ok=True)
    if replay_config.reset_audit and replay_config.audit_path.exists():
        replay_config.audit_path.unlink()

    for row_index, trade in sorted_trades.iterrows():
        intent = build_paper_intent_from_trade(
            trade,
            contract_month=replay_config.contract_month,
            quantity=replay_config.quantity,
            stop_loss_points=replay_config.stop_loss_points,
            take_profit_points=replay_config.take_profit_points,
            strategy_id=str(trade.get("portfolio_rule", "adaptive_portfolio")),
        )
        decision = _offline_decision(intent.strategy_id, gate_config, replay_config.audit_path)
        if replay_config.mode == "agent" and decision["passed"]:
            decision = AgentStrategyGate(gate_config).review(
                intent,
                trade_date=str(trade.get("trade_date", "")),
                selected_trade=trade.to_dict(),
            )
        guard = decision.get("performance_guard", {})
        position_scale = _position_scale(decision, replay_config.sizing_mode)
        allowed = position_scale > 0
        net_points = float(trade.get("net_points", 0.0))
        if allowed or replay_config.record_shadow_outcomes:
            record_agent_gate_outcome(
                PaperTradeOutcome(
                    strategy_id=intent.strategy_id,
                    intent_id=intent.normalized().intent_id,
                    action=intent.action,
                    entry_time=str(trade.get("entry_ts", "")),
                    exit_time=str(trade.get("exit_ts", "")),
                    entry_price=_optional_float(trade.get("entry_price")),
                    exit_price=_optional_float(trade.get("exit_price")),
                    points=net_points,
                    exit_reason=str(trade.get("exit_reason", "")),
                    source="paper" if allowed else "shadow_backtest",
                ),
                audit_path=replay_config.audit_path,
                update_memory=False,
            )
        rows.append(
            {
                "row_index": row_index,
                "entry_ts": trade.get("entry_ts"),
                "exit_ts": trade.get("exit_ts"),
                "trade_date": trade.get("trade_date"),
                "strategy_id": intent.strategy_id,
                "selected_alias": trade.get("selected_alias"),
                "direction": trade.get("direction"),
                "net_points": net_points,
                "allowed": allowed,
                "position_scale": position_scale,
                "gate_status": decision.get("status"),
                "gate_reasons": ",".join(decision.get("reasons", [])),
                "gate_severity": guard.get("severity", "normal"),
                "gate_net_points": net_points * position_scale,
            }
        )

    decisions = pd.DataFrame(rows)
    summary = pd.DataFrame([_summary_row("raw", sorted_trades), _summary_row("gate", _scaled_trades(sorted_trades, decisions))])
    return decisions, summary


def _offline_decision(strategy_id: str, gate_config: AgentGateConfig, audit_path: Path) -> dict[str, Any]:
    guard = AgentStrategyGate(gate_config)._performance_guard(strategy_id)
    reasons = list(guard.get("reasons", [])) if not guard.get("passed", True) else []
    return {
        "status": "offline_approved" if not reasons else "offline_rejected",
        "passed": not reasons,
        "reasons": reasons,
        "performance_guard": guard,
    }


def _summary_row(label: str, trades: pd.DataFrame) -> dict[str, Any]:
    normalized = trades.copy()
    if not normalized.empty and "entry_index" not in normalized.columns:
        normalized["entry_index"] = range(len(normalized))
    metrics = summarize_trades(StrategySpec(name=label, family="agent_gate", lookback=0, threshold=0.0, holding_minutes=0), normalized, BacktestCosts())
    metrics["label"] = label
    return metrics


def _scaled_trades(trades: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    if decisions.empty:
        return trades.head(0)
    scaled = trades.reset_index(drop=True).copy()
    scaled["net_points"] = decisions["gate_net_points"].astype(float).values
    return scaled.loc[decisions["position_scale"].astype(float) > 0].copy()


def _position_scale(decision: dict[str, Any], sizing_mode: str) -> float:
    if sizing_mode == "block":
        return 1.0 if decision.get("passed") else 0.0
    if sizing_mode != "scale":
        raise ValueError(f"Unsupported sizing_mode: {sizing_mode}")
    if not decision.get("passed"):
        return 0.0
    guard = decision.get("performance_guard", {})
    return float(guard.get("position_scale", 1.0))


def _optional_float(value: Any) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
