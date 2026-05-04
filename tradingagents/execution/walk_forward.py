from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd

from .agent_gate import AgentGateConfig, PaperTradeOutcome, record_agent_gate_outcome
from .gate_backtest import GateReplayConfig, replay_gate_on_trades


@dataclass(frozen=True)
class WalkForwardConfig:
    train_days: int = 15
    test_days: int = 5
    step_days: int = 5
    audit_dir: Path = Path(".tmp/walk-forward-agent-gate")
    sizing_mode: str = "scale"
    contract_month: str = "202606"


def walk_forward_gate_replay(
    trades: pd.DataFrame,
    *,
    config: WalkForwardConfig | None = None,
    gate_config: AgentGateConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = config or WalkForwardConfig()
    gate_config = gate_config or AgentGateConfig()
    data = trades.copy()
    data["trade_date"] = pd.to_datetime(data["trade_date"]).dt.date
    unique_dates = sorted(data["trade_date"].dropna().unique())
    fold_rows: list[dict[str, Any]] = []
    decision_frames: list[pd.DataFrame] = []
    fold_index = 0
    start = 0
    while start + config.train_days < len(unique_dates):
        train_dates = unique_dates[start : start + config.train_days]
        test_dates = unique_dates[start + config.train_days : start + config.train_days + config.test_days]
        if not test_dates:
            break
        train = data[data["trade_date"].isin(train_dates)].copy()
        test = data[data["trade_date"].isin(test_dates)].copy()
        if test.empty:
            start += config.step_days
            continue
        audit_path = config.audit_dir / f"fold-{fold_index:03d}.jsonl"
        if audit_path.exists():
            audit_path.unlink()
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        _seed_training_outcomes(train, audit_path)
        replay_config = GateReplayConfig(
            mode="offline",
            sizing_mode=config.sizing_mode,
            contract_month=config.contract_month,
            audit_path=audit_path,
            record_shadow_outcomes=True,
            reset_audit=False,
        )
        fold_gate_config = replace(gate_config, audit_path=audit_path, learning_context_enabled=False)
        decisions, summary = replay_gate_on_trades(test, replay_config=replay_config, gate_config=fold_gate_config)
        decisions["fold"] = fold_index
        decision_frames.append(decisions)
        raw = summary[summary["label"].eq("raw")].iloc[0].to_dict()
        gate = summary[summary["label"].eq("gate")].iloc[0].to_dict()
        fold_rows.append(
            {
                "fold": fold_index,
                "train_start": str(train_dates[0]),
                "train_end": str(train_dates[-1]),
                "test_start": str(test_dates[0]),
                "test_end": str(test_dates[-1]),
                "train_trades": int(len(train)),
                "test_trades": int(len(test)),
                "allowed": int(decisions["allowed"].sum()) if not decisions.empty else 0,
                "blocked": int((~decisions["allowed"]).sum()) if not decisions.empty else 0,
                "raw_net_points": float(raw["net_points"]),
                "gate_net_points": float(gate["net_points"]),
                "raw_max_drawdown_points": float(raw["max_drawdown_points"]),
                "gate_max_drawdown_points": float(gate["max_drawdown_points"]),
                "raw_profit_factor": float(raw["profit_factor"]),
                "gate_profit_factor": float(gate["profit_factor"]),
                "net_delta_points": float(gate["net_points"] - raw["net_points"]),
                "drawdown_delta_points": float(raw["max_drawdown_points"] - gate["max_drawdown_points"]),
            }
        )
        fold_index += 1
        start += config.step_days
    decisions_all = pd.concat(decision_frames, ignore_index=True) if decision_frames else pd.DataFrame()
    return decisions_all, pd.DataFrame(fold_rows)


def _seed_training_outcomes(train: pd.DataFrame, audit_path: Path) -> None:
    for _, trade in train.sort_values("entry_ts").iterrows():
        record_agent_gate_outcome(
            PaperTradeOutcome(
                strategy_id=str(trade.get("portfolio_rule", "adaptive_portfolio")),
                action="BUY" if float(trade.get("direction", 1)) > 0 else "SELL",
                entry_time=str(trade.get("entry_ts", "")),
                exit_time=str(trade.get("exit_ts", "")),
                entry_price=_optional_float(trade.get("entry_price")),
                exit_price=_optional_float(trade.get("exit_price")),
                points=_optional_float(trade.get("net_points")) or 0.0,
                exit_reason=str(trade.get("exit_reason", "")),
                source="walk_forward_train",
            ),
            audit_path=audit_path,
        )


def _optional_float(value: Any) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
